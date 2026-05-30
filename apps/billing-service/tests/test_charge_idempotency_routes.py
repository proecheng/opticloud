"""Story 5.A.9 — charge creation idempotency response-cache tests."""

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
            {"sub": str(user_id), "iat": now, "exp": now + ttl_seconds, "type": "access"},
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


async def _counts_for(
    session: AsyncSession, *, user_id: uuid.UUID, idem_key: str
) -> dict[str, int]:
    result = (
        (
            await session.execute(
                text(
                    """
                SELECT
                  (SELECT COUNT(*) FROM saga_instances WHERE idempotency_key = :idem_key) AS sagas,
                  (SELECT COUNT(*) FROM billing_idempotency_keys WHERE key = :idem_key) AS idem_rows,
                  (SELECT COUNT(*) FROM credit_transactions
                   WHERE user_id = :user_id AND metadata ->> 'source' = 'j1_demo_seed') AS seeds
                """
                ),
                {"idem_key": idem_key, "user_id": user_id},
            )
        )
        .mappings()
        .one()
    )
    return {key: int(result[key]) for key in ("sagas", "idem_rows", "seeds")}


async def _stored_response_body(session: AsyncSession, idem_key: str) -> dict | None:
    return (
        await session.execute(
            text("SELECT response_body FROM billing_idempotency_keys WHERE key = :key"),
            {"key": idem_key},
        )
    ).scalar_one_or_none()


async def _charge_ledger_count(session: AsyncSession, charge_id: str) -> int:
    return int(
        (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM credit_transactions "
                    "WHERE saga_id = :charge_id "
                    "AND kind IN ('charge', 'refund', 'refund_partial', 'refund_reversal')"
                ),
                {"charge_id": uuid.UUID(charge_id)},
            )
        ).scalar_one()
    )


async def _insert_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        text(
            "INSERT INTO users (id, phone, email, created_at, updated_at) "
            "VALUES (:id, :phone, :email, NOW(), NOW()) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {
            "id": user_id,
            "phone": f"+86idem{user_id.hex[:10]}",
            "email": f"idem-{user_id.hex[:10]}@opticloud.test",
        },
    )
    await session.commit()


async def test_charge_replay_returns_cached_creation_response_after_finalize(
    http_client: AsyncClient,
    auth_headers: dict[str, str],
    session: AsyncSession,
) -> None:
    idem_key = str(uuid.uuid4())
    request_body = {
        "amount": "6.00",
        "currency": "CNY",
        "purpose": "solve",
        "reference_id": str(uuid.uuid4()),
        "confirmed": True,
    }

    first = await http_client.post(
        "/v1/billing/charges",
        json=request_body,
        headers={**auth_headers, "Idempotency-Key": idem_key},
    )
    assert first.status_code == 201, first.text
    first_body = first.json()
    charge_id = first_body["charge_id"]

    reserve = await http_client.post(
        f"/v1/billing/charges/{charge_id}/reserve", headers=auth_headers
    )
    assert reserve.status_code == 200, reserve.text
    finalize = await http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize",
        headers=auth_headers,
        json={"elapsed_seconds": 5.0, "status": "success", "failure_reason": None},
    )
    assert finalize.status_code == 200, finalize.text
    assert finalize.json()["current_state"] == "charged"
    ledger_rows_after_finalize = await _charge_ledger_count(session, charge_id)

    replay = await http_client.post(
        "/v1/billing/charges",
        json=request_body,
        headers={**auth_headers, "Idempotency-Key": idem_key},
    )

    assert replay.status_code == 201, replay.text
    assert replay.json() == first_body
    assert replay.json()["current_state"] == "pending"
    assert await _stored_response_body(session, idem_key) == first_body
    assert await _charge_ledger_count(session, charge_id) == ledger_rows_after_finalize


async def test_charge_replay_does_not_duplicate_seed_saga_or_idempotency_rows(
    http_client: AsyncClient,
    auth_headers: dict[str, str],
    session: AsyncSession,
    test_user_id: uuid.UUID,
) -> None:
    idem_key = str(uuid.uuid4())
    request_body = {
        "amount": "1.00",
        "currency": "CNY",
        "purpose": "demo",
        "reference_id": str(uuid.uuid4()),
    }

    first = await http_client.post(
        "/v1/billing/charges",
        json=request_body,
        headers={**auth_headers, "Idempotency-Key": idem_key},
    )
    replay = await http_client.post(
        "/v1/billing/charges",
        json=request_body,
        headers={**auth_headers, "Idempotency-Key": idem_key},
    )

    assert first.status_code == 201, first.text
    assert replay.status_code == 201, replay.text
    assert replay.json() == first.json()
    assert await _counts_for(session, user_id=test_user_id, idem_key=idem_key) == {
        "sagas": 1,
        "idem_rows": 1,
        "seeds": 1,
    }


async def test_charge_same_key_different_body_keeps_cached_response_untouched(
    http_client: AsyncClient,
    auth_headers: dict[str, str],
    session: AsyncSession,
) -> None:
    idem_key = str(uuid.uuid4())
    first_body = {
        "amount": "1.00",
        "currency": "CNY",
        "purpose": "demo",
        "reference_id": str(uuid.uuid4()),
    }

    first = await http_client.post(
        "/v1/billing/charges",
        json=first_body,
        headers={**auth_headers, "Idempotency-Key": idem_key},
    )
    assert first.status_code == 201, first.text

    conflict = await http_client.post(
        "/v1/billing/charges",
        json={**first_body, "amount": "2.00"},
        headers={**auth_headers, "Idempotency-Key": idem_key},
    )

    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["title"] == "Idempotency Conflict"
    assert await _stored_response_body(session, idem_key) == first.json()


async def test_charge_cross_tenant_replay_never_returns_cached_response(
    http_client: AsyncClient,
    auth_headers: dict[str, str],
    token_factory: tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]],
    session: AsyncSession,
) -> None:
    _, token_for = token_factory
    idem_key = str(uuid.uuid4())
    request_body = {
        "amount": "1.00",
        "currency": "CNY",
        "purpose": "demo",
        "reference_id": str(uuid.uuid4()),
    }
    first = await http_client.post(
        "/v1/billing/charges",
        json=request_body,
        headers={**auth_headers, "Idempotency-Key": idem_key},
    )
    assert first.status_code == 201, first.text

    other_user_id = uuid.uuid4()
    await _insert_user(session, other_user_id)
    other_headers = {"Authorization": f"Bearer {token_for(other_user_id)}"}
    replay = await http_client.post(
        "/v1/billing/charges",
        json=request_body,
        headers={**other_headers, "Idempotency-Key": idem_key},
    )

    assert replay.status_code == 403, replay.text
    assert first.json()["charge_id"] not in replay.text
    assert await _stored_response_body(session, idem_key) == first.json()


async def test_legacy_null_response_body_is_backfilled_without_new_saga(
    http_client: AsyncClient,
    auth_headers: dict[str, str],
    session: AsyncSession,
    test_user_id: uuid.UUID,
) -> None:
    idem_key = str(uuid.uuid4())
    request_body = {
        "amount": "1.00",
        "currency": "CNY",
        "purpose": "demo",
        "reference_id": str(uuid.uuid4()),
    }
    first = await http_client.post(
        "/v1/billing/charges",
        json=request_body,
        headers={**auth_headers, "Idempotency-Key": idem_key},
    )
    assert first.status_code == 201, first.text
    await session.execute(
        text("UPDATE billing_idempotency_keys SET response_body = NULL WHERE key = :key"),
        {"key": idem_key},
    )
    await session.commit()

    replay = await http_client.post(
        "/v1/billing/charges",
        json=request_body,
        headers={**auth_headers, "Idempotency-Key": idem_key},
    )

    assert replay.status_code == 201, replay.text
    assert replay.json() == first.json()
    assert await _stored_response_body(session, idem_key) == first.json()
    assert await _counts_for(session, user_id=test_user_id, idem_key=idem_key) == {
        "sagas": 1,
        "idem_rows": 1,
        "seeds": 1,
    }


async def test_unsuccessful_charge_create_does_not_cache_response_body(
    http_client: AsyncClient,
    auth_headers: dict[str, str],
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]],
) -> None:
    insufficient_key = str(uuid.uuid4())

    insufficient = await http_client.post(
        "/v1/billing/charges",
        json={
            "amount": "9999.00",
            "currency": "CNY",
            "purpose": "solve",
            "reference_id": str(uuid.uuid4()),
        },
        headers={**auth_headers, "Idempotency-Key": insufficient_key},
    )

    assert insufficient.status_code == 422, insufficient.text
    assert await _stored_response_body(session, insufficient_key) is None

    _, token_for = token_factory
    warning_user_id = uuid.uuid4()
    await _insert_user(session, warning_user_id)
    warning_key = str(uuid.uuid4())
    warning_required = await http_client.post(
        "/v1/billing/charges",
        json={
            "amount": "6.00",
            "currency": "CNY",
            "purpose": "solve",
            "reference_id": str(uuid.uuid4()),
        },
        headers={
            "Authorization": f"Bearer {token_for(warning_user_id)}",
            "Idempotency-Key": warning_key,
        },
    )

    assert warning_required.status_code == 422, warning_required.text
    assert warning_required.json()["title"] == "Explicit Confirmation Required"
    assert await _stored_response_body(session, warning_key) is None
