"""Critical scenarios — per-formula pricing math integration (Story 5.A.4).

3 scenarios exercising the full route → orchestrator → ledger chain for the
amount math (T-PRICING-001 / 002 / 003).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path

import jwt
import pytest_asyncio
from billing_service.auth_dep import _loader as _jwt_loader  # noqa: PLC2701
from billing_service.db import get_session
from billing_service.main import app
from billing_service.models import CreditTransaction
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_TEST_KEY_DIR = Path("tests/_keys")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def pricing_token_factory() -> AsyncIterator[tuple[Ed25519PrivateKey, object]]:
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

    def token_for(user_id: uuid.UUID) -> str:
        now = int(time.time())
        return jwt.encode(
            {"sub": str(user_id), "iat": now, "exp": now + 3600, "type": "access"},
            private,
            algorithm="EdDSA",
        )

    yield (private, token_for)


@pytest_asyncio.fixture
async def pricing_http_client(engine, pricing_token_factory) -> AsyncIterator[AsyncClient]:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _override() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            try:
                yield s
            finally:
                try:
                    await s.commit()
                except Exception:
                    await s.rollback()

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _ledger_sum_for(session_maker, saga_id: str, kind: str) -> Decimal:
    """Return sum(amount) for kind tied to saga_id."""
    async with session_maker() as s:
        stmt = select(CreditTransaction).where(
            CreditTransaction.saga_id == uuid.UUID(saga_id),
            CreditTransaction.kind == kind,
        )
        rows = (await s.execute(stmt)).scalars().all()
        return sum((r.amount for r in rows), start=Decimal("0"))


async def _do_charge_reserve_finalize(
    client: AsyncClient, headers: dict[str, str], *, elapsed: float, max_secs: float = 60.0
) -> dict:
    """Full happy-path: create → reserve → finalize(success). Returns final response body."""
    r = await client.post(
        "/v1/billing/charges",
        json={
            "amount": "6.00",
            "currency": "CNY",
            "purpose": "solve",
            "reference_id": str(uuid.uuid4()),
            "max_solve_seconds": max_secs,
            "confirmed": True,  # 5.A.5 pre-charge guard
        },
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r.status_code == 201, r.text
    charge_id = r.json()["charge_id"]

    rr = await client.post(f"/v1/billing/charges/{charge_id}/reserve", headers=headers)
    assert rr.status_code == 200, rr.text

    rf = await client.post(
        f"/v1/billing/charges/{charge_id}/finalize",
        headers=headers,
        json={"elapsed_seconds": elapsed, "status": "success", "failure_reason": None},
    )
    assert rf.status_code == 200, rf.text
    return rf.json()


async def test_pricing_001_elapsed_zero_floors_to_min(
    pricing_http_client: AsyncClient, test_user_id: uuid.UUID, pricing_token_factory, engine
) -> None:
    """T-PRICING-001: reserved=6, elapsed=0 → actual=0.01, refund_partial=5.99."""
    _, token_for = pricing_token_factory
    headers = {"Authorization": f"Bearer {token_for(test_user_id)}"}

    body = await _do_charge_reserve_finalize(pricing_http_client, headers, elapsed=0.0)

    assert body["actual_amount"] == "0.01"
    assert body["refund_partial_amount"] == "5.99"
    assert body["reserved_amount"] == "6.00"

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    charge_sum = await _ledger_sum_for(maker, body["charge_id"], "charge")
    refund_partial_sum = await _ledger_sum_for(maker, body["charge_id"], "refund_partial")
    # Net debit = -(charge_sum + refund_partial_sum) = -(-6 + 5.99) = 0.01
    assert -(charge_sum + refund_partial_sum) == Decimal("0.01")


async def test_pricing_002_elapsed_at_cap_no_refund_partial(
    pricing_http_client: AsyncClient, test_user_id: uuid.UUID, pricing_token_factory, engine
) -> None:
    """T-PRICING-002: reserved=6, elapsed=60 → actual=6.00, no refund_partial row."""
    _, token_for = pricing_token_factory
    headers = {"Authorization": f"Bearer {token_for(test_user_id)}"}

    body = await _do_charge_reserve_finalize(pricing_http_client, headers, elapsed=60.0)

    assert body["actual_amount"] == "6.00"
    assert body["refund_partial_amount"] == "0.00"

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    refund_partial_sum = await _ledger_sum_for(maker, body["charge_id"], "refund_partial")
    assert refund_partial_sum == Decimal("0")  # no rows = sum is zero


async def test_pricing_003_elapsed_over_cap_clamped_to_reserved(
    pricing_http_client: AsyncClient, test_user_id: uuid.UUID, pricing_token_factory, engine
) -> None:
    """T-PRICING-003: reserved=6, elapsed=100 → capped to 6.00; no refund_partial."""
    _, token_for = pricing_token_factory
    headers = {"Authorization": f"Bearer {token_for(test_user_id)}"}

    body = await _do_charge_reserve_finalize(pricing_http_client, headers, elapsed=100.0)

    assert body["actual_amount"] == "6.00"
    assert body["refund_partial_amount"] == "0.00"

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    charge_sum = await _ledger_sum_for(maker, body["charge_id"], "charge")
    assert charge_sum == Decimal("-6.0000")  # full reserved debited, no over-charge
