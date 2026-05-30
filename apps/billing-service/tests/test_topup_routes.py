"""HTTP route tests for Story 5.A.6 topup never-expires."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import jwt
import pytest
import pytest_asyncio
from billing_service.auth_dep import _loader as _jwt_loader  # noqa: PLC2701
from billing_service.config import settings
from billing_service.db import get_session
from billing_service.main import app
from billing_service.models import CreditTransaction, SagaInstance
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_TEST_KEY_DIR = Path("tests/_keys")
_INTERNAL_SECRET = "test-topup-internal-secret"  # noqa: S105


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def token_factory() -> AsyncIterator[tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]]]:
    """Generate test keypair and return (private, token_for(user_id)) helper."""
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
async def http_client(engine, token_factory) -> AsyncIterator[AsyncClient]:
    """ASGI test client with DI override for DB session."""
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


async def _create_user_row(engine, user_id: uuid.UUID) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO users (id, phone, email, created_at, updated_at) "
                "VALUES (:id, :phone, :email, NOW(), NOW()) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {
                "id": user_id,
                "phone": f"+86t{user_id.hex[:13]}",
                "email": f"topup-{user_id.hex[:10]}@opticloud.test",
            },
        )
        await s.commit()


@pytest_asyncio.fixture
async def fresh_headers(engine, token_factory) -> tuple[uuid.UUID, dict[str, str]]:
    _, token_for = token_factory
    user_id = uuid.uuid4()
    await _create_user_row(engine, user_id)
    return user_id, {"Authorization": f"Bearer {token_for(user_id)}"}


@pytest.fixture(autouse=True)
def _internal_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "internal_service_secret", SecretStr(_INTERNAL_SECRET))


def _internal_headers(secret: str = _INTERNAL_SECRET) -> dict[str, str]:
    return {"X-Internal-Service-Auth": secret}


def _topup_body(amount: str = "10.00") -> dict[str, str]:
    return {
        "amount": amount,
        "currency": "CNY",
        "reference_id": str(uuid.uuid4()),
    }


def _buckets_by_name(body: dict) -> dict[str, dict]:
    return {bucket["name"]: bucket for bucket in body["buckets"]}


async def _create_topup(
    http_client: AsyncClient,
    headers: dict[str, str],
    *,
    body: dict[str, str] | None = None,
    key: str | None = None,
) -> dict:
    response = await http_client.post(
        "/v1/billing/topups",
        json=body or _topup_body(),
        headers={**headers, "Idempotency-Key": key or str(uuid.uuid4())},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _ledger_count(session: AsyncSession, saga_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(CreditTransaction)
        .where(CreditTransaction.saga_id == saga_id)
    )
    return int(result.scalar_one())


async def test_create_topup_is_idempotent_and_does_not_credit_balance(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
) -> None:
    """Public topup initiation creates a pending request but mints no Credits."""
    _user_id, headers = fresh_headers
    key = str(uuid.uuid4())
    body = _topup_body("10.00")

    first = await http_client.post(
        "/v1/billing/topups",
        json=body,
        headers={**headers, "Idempotency-Key": key},
    )
    second = await http_client.post(
        "/v1/billing/topups",
        json=body,
        headers={**headers, "Idempotency-Key": key},
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json()["topup_id"] == first.json()["topup_id"]
    assert first.json()["current_state"] == "pending"
    assert first.json()["amount"] == "10.00"
    assert first.json()["bucket"] == "topup"
    assert first.json()["expires_at"] is None
    assert first.json()["expires_hint"] == "永不过期"

    balance = await http_client.get("/v1/billing/balance", headers=headers)
    by_name = _buckets_by_name(balance.json())
    assert balance.json()["balance"] == "0.00"
    assert by_name["topup"]["balance"] == "0.00"


async def test_create_topup_rejects_unsupported_pack_and_conflicting_replay(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
) -> None:
    """Topup amount is pack-limited and idempotency includes amount."""
    _user_id, headers = fresh_headers
    bad_pack = await http_client.post(
        "/v1/billing/topups",
        json=_topup_body("11.00"),
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert bad_pack.status_code == 422

    key = str(uuid.uuid4())
    ok = await http_client.post(
        "/v1/billing/topups",
        json=_topup_body("10.00"),
        headers={**headers, "Idempotency-Key": key},
    )
    assert ok.status_code == 201
    conflict = await http_client.post(
        "/v1/billing/topups",
        json=_topup_body("50.00"),
        headers={**headers, "Idempotency-Key": key},
    )
    assert conflict.status_code == 409


async def test_create_topup_rejects_rounded_or_unsafe_pointer_values(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
) -> None:
    """Review fix — amount rounding and unsafe reference values must not pass."""
    _user_id, headers = fresh_headers

    rounded_pack = await http_client.post(
        "/v1/billing/topups",
        json=_topup_body("9.999"),
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert rounded_pack.status_code == 422

    unsafe_ref = await http_client.post(
        "/v1/billing/topups",
        json={
            "amount": "10.00",
            "currency": "CNY",
            "reference_id": "user@example.com",
        },
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert unsafe_ref.status_code == 422


async def test_confirm_topup_requires_internal_auth_and_secret_configuration(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Payment confirmation is internal-only and fails closed when no secret is configured."""
    _user_id, headers = fresh_headers
    topup = await _create_topup(http_client, headers)

    missing = await http_client.post(
        f"/v1/billing/topups/{topup['topup_id']}/confirm",
        json={"provider": "manual", "payment_ref": str(uuid.uuid4())},
    )
    assert missing.status_code == 401

    wrong = await http_client.post(
        f"/v1/billing/topups/{topup['topup_id']}/confirm",
        json={"provider": "manual", "payment_ref": str(uuid.uuid4())},
        headers=_internal_headers("wrong-secret"),
    )
    assert wrong.status_code == 401

    monkeypatch.setattr(settings, "internal_service_secret", SecretStr(""))
    unset = await http_client.post(
        f"/v1/billing/topups/{topup['topup_id']}/confirm",
        json={"provider": "manual", "payment_ref": str(uuid.uuid4())},
        headers=_internal_headers(),
    )
    assert unset.status_code == 503


async def test_confirm_topup_rejects_unsafe_payment_refs(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
) -> None:
    """Review fix — payment refs must stay bounded pointer strings."""
    _user_id, headers = fresh_headers
    topup = await _create_topup(http_client, headers)

    unsafe = await http_client.post(
        f"/v1/billing/topups/{topup['topup_id']}/confirm",
        json={"provider": "manual", "payment_ref": "Bearer sk-test-token"},
        headers=_internal_headers(),
    )

    assert unsafe.status_code == 422


async def test_confirm_topup_credits_topup_bucket_once_and_replays_idempotently(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
    session: AsyncSession,
) -> None:
    """Trusted confirmation writes exactly one positive topup ledger row."""
    _user_id, headers = fresh_headers
    topup = await _create_topup(http_client, headers, body=_topup_body("50.00"))
    topup_id = uuid.UUID(topup["topup_id"])
    body = {"provider": "manual", "payment_ref": str(uuid.uuid4())}

    first = await http_client.post(
        f"/v1/billing/topups/{topup_id}/confirm",
        json=body,
        headers=_internal_headers(),
    )
    replay = await http_client.post(
        f"/v1/billing/topups/{topup_id}/confirm",
        json=body,
        headers=_internal_headers(),
    )

    assert first.status_code == 200, first.text
    assert replay.status_code == 200, replay.text
    assert first.json()["current_state"] == "completed"
    assert first.json()["balance_after"] == "50.00"
    assert replay.json()["balance_after"] == "50.00"
    assert await _ledger_count(session, topup_id) == 1

    balance = await http_client.get("/v1/billing/balance", headers=headers)
    by_name = _buckets_by_name(balance.json())
    assert balance.json()["balance"] == "50.00"
    assert by_name["topup"]["balance"] == "50.00"
    assert by_name["topup"]["expires_hint"] == "永不过期"


async def test_confirm_topup_conflicting_payment_ref_does_not_double_credit(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
    session: AsyncSession,
) -> None:
    """A completed topup cannot be rebound to another payment reference."""
    _user_id, headers = fresh_headers
    topup = await _create_topup(http_client, headers)
    topup_id = uuid.UUID(topup["topup_id"])

    ok = await http_client.post(
        f"/v1/billing/topups/{topup_id}/confirm",
        json={"provider": "manual", "payment_ref": str(uuid.uuid4())},
        headers=_internal_headers(),
    )
    assert ok.status_code == 200, ok.text

    conflict = await http_client.post(
        f"/v1/billing/topups/{topup_id}/confirm",
        json={"provider": "manual", "payment_ref": str(uuid.uuid4())},
        headers=_internal_headers(),
    )
    assert conflict.status_code == 409
    assert await _ledger_count(session, topup_id) == 1


async def test_confirmed_topup_remains_available_after_one_year(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
    session: AsyncSession,
) -> None:
    """FR B9 — topup bucket is not filtered out after 365+ days."""
    _user_id, headers = fresh_headers
    topup = await _create_topup(http_client, headers)
    topup_id = uuid.UUID(topup["topup_id"])
    confirmed = await http_client.post(
        f"/v1/billing/topups/{topup_id}/confirm",
        json={"provider": "manual", "payment_ref": str(uuid.uuid4())},
        headers=_internal_headers(),
    )
    assert confirmed.status_code == 200, confirmed.text

    old_time = datetime.now(UTC) - timedelta(days=366)
    await session.execute(
        text("UPDATE credit_transactions SET created_at = :old_time WHERE saga_id = :saga_id"),
        {"old_time": old_time, "saga_id": topup_id},
    )
    await session.commit()

    balance = await http_client.get("/v1/billing/balance", headers=headers)
    by_name = _buckets_by_name(balance.json())
    assert balance.json()["balance"] == "10.00"
    assert by_name["topup"]["balance"] == "10.00"
    assert by_name["topup"]["expires_hint"] == "永不过期"


async def test_topup_payload_ref_remains_pointer_only(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
    session: AsyncSession,
) -> None:
    """Topup Saga payload_ref must not contain amount, payment, balance, or raw payload data."""
    _user_id, headers = fresh_headers
    topup = await _create_topup(http_client, headers)
    saga = await session.get(SagaInstance, uuid.UUID(topup["topup_id"]))
    assert saga is not None
    assert saga.amount == Decimal("10.0000")
    assert saga.payload_ref["purpose"] == "topup"
    assert "reference_id" in saga.payload_ref
    forbidden = {"amount", "payment_ref", "provider", "balance", "credit", "payload"}
    assert forbidden.isdisjoint(saga.payload_ref)
