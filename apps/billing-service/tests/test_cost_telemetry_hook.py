"""Story 5.A.8 — billing Saga cost telemetry hook tests."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import jwt
import pytest_asyncio
from billing_service.auth_dep import _loader as _jwt_loader  # noqa: PLC2701
from billing_service.db import get_session
from billing_service.main import app
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

_TEST_KEY_DIR = Path("tests/_keys")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def token_factory() -> AsyncIterator[tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]]]:
    _TEST_KEY_DIR.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240
    private = Ed25519PrivateKey.generate()
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pub_path = _TEST_KEY_DIR / "jwt_public.pem"
    pub_path.write_bytes(public_pem)  # noqa: ASYNC230
    _jwt_loader._path = pub_path
    _jwt_loader._key = None

    def token_for(user_id: uuid.UUID, ttl_seconds: int = 3600) -> str:
        now = int(time.time())
        return jwt.encode(
            {
                "sub": str(user_id),
                "iat": now,
                "exp": now + ttl_seconds,
                "type": "access",
            },
            private,
            algorithm="EdDSA",
        )

    yield (private, token_for)


@pytest_asyncio.fixture
async def http_client(
    engine: AsyncEngine, token_factory: tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]]
) -> AsyncIterator[AsyncClient]:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            try:
                yield s
            finally:
                try:
                    await s.commit()
                except Exception:
                    await s.rollback()

    app.dependency_overrides[get_session] = _override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(
    test_user_id: uuid.UUID,
    token_factory: tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]],
) -> dict[str, str]:
    _, token_for = token_factory
    return {"Authorization": f"Bearer {token_for(test_user_id)}"}


async def _create_charge(
    http_client: AsyncClient,
    auth_headers: dict[str, str],
    *,
    amount: str = "6.00",
) -> str:
    response = await http_client.post(
        "/v1/billing/charges",
        json={
            "amount": amount,
            "currency": "CNY",
            "purpose": "solve",
            "reference_id": str(uuid.uuid4()),
            "confirmed": True,
        },
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["charge_id"])


async def _reserve_charge(
    http_client: AsyncClient,
    auth_headers: dict[str, str],
    charge_id: str,
) -> None:
    response = await http_client.post(
        f"/v1/billing/charges/{charge_id}/reserve",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text


async def _cost_rows_for(session: AsyncSession, charge_id: str) -> list[dict[str, object]]:
    rows = (
        await session.execute(
            text(
                "SELECT tenant_id, service, cost_unit, value, source_id, metadata "
                "FROM cost_attribution WHERE source_id = :source_id "
                "ORDER BY recorded_at ASC"
            ),
            {"source_id": uuid.UUID(charge_id)},
        )
    ).mappings()
    return [dict(row) for row in rows]


async def _ledger_sum_for(session: AsyncSession, charge_id: str) -> str:
    total = (
        await session.execute(
            text(
                "SELECT COALESCE(SUM(amount), 0) FROM credit_transactions WHERE saga_id = :saga_id"
            ),
            {"saga_id": uuid.UUID(charge_id)},
        )
    ).scalar_one()
    return f"{total:.4f}"


async def test_successful_finalize_records_one_billing_solver_second_cost_row(
    http_client: AsyncClient,
    auth_headers: dict[str, str],
    session: AsyncSession,
    test_user_id: uuid.UUID,
) -> None:
    charge_id = await _create_charge(http_client, auth_headers)
    await _reserve_charge(http_client, auth_headers, charge_id)

    response = await http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize",
        headers=auth_headers,
        json={"elapsed_seconds": 5.25, "status": "success", "failure_reason": None},
    )

    assert response.status_code == 200, response.text
    assert response.json()["current_state"] == "charged"
    rows = await _cost_rows_for(session, charge_id)
    assert len(rows) == 1
    row = rows[0]
    assert row["tenant_id"] == test_user_id
    assert row["service"] == "billing-service"
    assert row["cost_unit"] == "solver_second"
    assert f"{row['value']:.6f}" == "5.250000"
    assert row["source_id"] == uuid.UUID(charge_id)
    assert row["metadata"] == {
        "saga_type": "solve_charge",
        "charge_state": "charged",
        "finalize_status": "success",
        "purpose": "solve",
    }


async def test_finalize_replay_does_not_duplicate_billing_cost_row(
    http_client: AsyncClient,
    auth_headers: dict[str, str],
    session: AsyncSession,
) -> None:
    charge_id = await _create_charge(http_client, auth_headers)
    await _reserve_charge(http_client, auth_headers, charge_id)
    payload = {"elapsed_seconds": 5.0, "status": "success", "failure_reason": None}

    first = await http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize",
        headers=auth_headers,
        json=payload,
    )
    second = await http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize",
        headers=auth_headers,
        json=payload,
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert await _cost_rows_for(session, charge_id) != []
    assert len(await _cost_rows_for(session, charge_id)) == 1


async def test_failure_finalize_does_not_record_billing_cost_row(
    http_client: AsyncClient,
    auth_headers: dict[str, str],
    session: AsyncSession,
) -> None:
    charge_id = await _create_charge(http_client, auth_headers)
    await _reserve_charge(http_client, auth_headers, charge_id)

    response = await http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize",
        headers=auth_headers,
        json={
            "elapsed_seconds": 5.0,
            "status": "failure",
            "failure_reason": "infeasible",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["current_state"] == "refunded"
    assert await _cost_rows_for(session, charge_id) == []


async def test_cost_hook_failure_preserves_successful_billing_finalize(
    http_client: AsyncClient,
    auth_headers: dict[str, str],
    session: AsyncSession,
    monkeypatch,
) -> None:
    from billing_service import routes

    charge_id = await _create_charge(http_client, auth_headers)
    await _reserve_charge(http_client, auth_headers, charge_id)

    async def _broken_record(*args, **kwargs) -> object:
        raise ValueError("synthetic cost hook failure")

    monkeypatch.setattr(routes, "record_cost_event", _broken_record)

    response = await http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize",
        headers=auth_headers,
        json={"elapsed_seconds": 5.0, "status": "success", "failure_reason": None},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["current_state"] == "charged"
    assert body["actual_amount"] == "0.50"
    assert body["refund_partial_amount"] == "5.50"
    assert await _cost_rows_for(session, charge_id) == []
    assert await _ledger_sum_for(session, charge_id) == "-0.5000"


async def test_cost_hook_query_failure_savepoint_preserves_successful_finalize(
    http_client: AsyncClient,
    auth_headers: dict[str, str],
    session: AsyncSession,
    monkeypatch,
) -> None:
    from billing_service import routes

    charge_id = await _create_charge(http_client, auth_headers)
    await _reserve_charge(http_client, auth_headers, charge_id)

    async def _broken_exists(db: AsyncSession, charge_id: uuid.UUID) -> bool:
        await db.execute(text("SELECT 1 FROM cost_attribution_missing_table"))
        return False

    monkeypatch.setattr(routes, "_billing_cost_attribution_exists", _broken_exists)

    response = await http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize",
        headers=auth_headers,
        json={"elapsed_seconds": 5.0, "status": "success", "failure_reason": None},
    )

    assert response.status_code == 200, response.text
    assert response.json()["current_state"] == "charged"
    assert await _ledger_sum_for(session, charge_id) == "-0.5000"


async def test_billing_cost_metadata_does_not_expose_blocked_fields(
    http_client: AsyncClient,
    auth_headers: dict[str, str],
    session: AsyncSession,
) -> None:
    charge_id = await _create_charge(http_client, auth_headers)
    await _reserve_charge(http_client, auth_headers, charge_id)

    response = await http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize",
        headers=auth_headers,
        json={"elapsed_seconds": 5.0, "status": "success", "failure_reason": None},
    )

    assert response.status_code == 200, response.text
    rows = await _cost_rows_for(session, charge_id)
    metadata = rows[0]["metadata"]
    assert isinstance(metadata, dict)
    blocked_fragments: tuple[str, ...] = (
        "amount",
        "balance",
        "bank",
        "bearer",
        "credit",
        "email",
        "input",
        "jwt",
        "password",
        "payment",
        "phone",
        "prompt",
        "secret",
        "token",
    )
    for key in metadata:
        lowered = key.lower()
        assert all(fragment not in lowered for fragment in blocked_fragments)
