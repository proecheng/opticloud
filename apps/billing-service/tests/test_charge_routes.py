"""HTTP route tests for billing-service (Story 5.A.1 AC7).

Uses FastAPI TestClient with DI override — no live HTTP server needed.
"""

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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_TEST_KEY_DIR = Path("tests/_keys")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def token_factory() -> AsyncIterator[tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]]]:
    """Generate test keypair + return (private, token_for(user_id)) helper."""
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


@pytest_asyncio.fixture
async def auth_headers(test_user_id: uuid.UUID, token_factory) -> dict[str, str]:
    _, token_for = token_factory
    return {"Authorization": f"Bearer {token_for(test_user_id)}"}


# ===== AC7 tests =====


async def test_create_charge_without_auth_returns_401(http_client: AsyncClient) -> None:
    response = await http_client.post(
        "/v1/billing/charges",
        json={
            "amount": "6.00",
            "currency": "CNY",
            "purpose": "demo",
            "reference_id": str(uuid.uuid4()),
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 401


async def test_get_balance_without_auth_returns_401(http_client: AsyncClient) -> None:
    response = await http_client.get("/v1/billing/balance")
    assert response.status_code == 401


async def test_create_charge_seeds_balance_then_charges(
    http_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """First POST should lazy-seed +50 CNY then create the charge."""
    response = await http_client.post(
        "/v1/billing/charges",
        json={
            "amount": "6.00",
            "currency": "CNY",
            "purpose": "demo",
            "reference_id": str(uuid.uuid4()),
        },
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["amount"] == "6.00"
    # Balance after start (before confirm) still equals balance_before
    assert body["balance_before"] == body["balance_after"]
    assert body["current_state"] == "pending"


async def test_get_balance_pure_no_seed(http_client: AsyncClient, token_factory) -> None:
    """A2: GET balance for a new user does NOT seed (returns 0.00)."""
    _, token_for = token_factory
    new_user = uuid.uuid4()
    response = await http_client.get(
        "/v1/billing/balance",
        headers={"Authorization": f"Bearer {token_for(new_user)}"},
    )
    assert response.status_code == 200
    assert response.json()["balance"] == "0.00"


async def test_idempotent_create_returns_same_charge(
    http_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    key = str(uuid.uuid4())
    ref_id = str(uuid.uuid4())
    body = {
        "amount": "6.00",
        "currency": "CNY",
        "purpose": "demo",
        "reference_id": ref_id,
    }
    r1 = await http_client.post(
        "/v1/billing/charges", json=body, headers={**auth_headers, "Idempotency-Key": key}
    )
    assert r1.status_code == 201
    r2 = await http_client.post(
        "/v1/billing/charges", json=body, headers={**auth_headers, "Idempotency-Key": key}
    )
    assert r2.status_code == 201
    assert r1.json()["charge_id"] == r2.json()["charge_id"]


async def test_idempotency_conflict_on_body_change(
    http_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    key = str(uuid.uuid4())
    r1 = await http_client.post(
        "/v1/billing/charges",
        json={
            "amount": "6.00",
            "currency": "CNY",
            "purpose": "demo",
            "reference_id": str(uuid.uuid4()),
        },
        headers={**auth_headers, "Idempotency-Key": key},
    )
    assert r1.status_code == 201
    r2 = await http_client.post(
        "/v1/billing/charges",
        json={
            "amount": "7.00",
            "currency": "CNY",
            "purpose": "demo",
            "reference_id": str(uuid.uuid4()),
        },
        headers={**auth_headers, "Idempotency-Key": key},
    )
    assert r2.status_code == 409


async def test_invalid_idempotency_key_format(
    http_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """S3: non-UUID Idempotency-Key → 400."""
    response = await http_client.post(
        "/v1/billing/charges",
        json={
            "amount": "6.00",
            "currency": "CNY",
            "purpose": "demo",
            "reference_id": str(uuid.uuid4()),
        },
        headers={**auth_headers, "Idempotency-Key": "not-a-uuid"},
    )
    assert response.status_code == 400


async def test_confirm_charge_transitions_to_charged(
    http_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Happy path: create + confirm → state=charged, balance debited."""
    create = await http_client.post(
        "/v1/billing/charges",
        json={
            "amount": "6.00",
            "currency": "CNY",
            "purpose": "demo",
            "reference_id": str(uuid.uuid4()),
        },
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert create.status_code == 201
    charge_id = create.json()["charge_id"]
    balance_before = float(create.json()["balance_before"])

    confirm = await http_client.post(
        f"/v1/billing/charges/{charge_id}/confirm", headers=auth_headers
    )
    assert confirm.status_code == 200, confirm.text
    body = confirm.json()
    assert body["current_state"] == "charged"

    bal_after = float(body["balance_after"])
    # Balance should have decreased by exactly 6
    assert bal_after == balance_before - 6.0


async def test_insufficient_balance_returns_422(
    http_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await http_client.post(
        "/v1/billing/charges",
        json={
            "amount": "9999.00",
            "currency": "CNY",
            "purpose": "demo",
            "reference_id": str(uuid.uuid4()),
        },
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["title"] == "Insufficient balance"
    assert body["errors"][0]["constraint"] == "amount > balance"
