"""Property tests for pricing math — Story 5.A.3 (FR B2 — preview cap ≥ actual).

Two layers:
1. Pure-function invariant: compute_charge_amount honors `actual ≤ reserved`
   under any inputs (AC1 + AC1a).
2. HTTP end-to-end invariant: GET /estimate → POST /charges → /reserve →
   /finalize round-trip preserves `actual_amount ≤ estimated_amount` (AC2).

Strategy aliases live here (locally) rather than in the shared strategies
module because they encode billing-specific bounds.
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
from billing_service.pricing import compute_charge_amount
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import ASGITransport, AsyncClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_TEST_KEY_DIR = Path("tests/_keys")

_PURE_FAST = settings(
    max_examples=50,
    deadline=2000,
    derandomize=True,
)

_HTTP_FAST = settings(
    max_examples=20,
    deadline=4000,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


# ===== AC1 + AC1a: pure-function invariants =====


@given(
    elapsed=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    max_solve_seconds=st.floats(
        min_value=0.1, max_value=600.0, allow_nan=False, allow_infinity=False
    ),
    rate_str=st.sampled_from(["0.01", "0.05", "0.10", "0.50", "1.00"]),
)
@_PURE_FAST
def test_actual_le_estimated_strict_no_floor(
    elapsed: float, max_solve_seconds: float, rate_str: str
) -> None:
    """AC1 — strict FR B2: actual ≤ estimated (with min_amount=0 so floor doesn't lift)."""
    rate = Decimal(rate_str)
    reserved = Decimal(str(max_solve_seconds)) * rate  # what /estimate would return
    actual = compute_charge_amount(
        elapsed_seconds=elapsed,
        max_solve_seconds=max_solve_seconds,
        rate_per_second=rate,
        min_amount=Decimal("0.00"),  # floor disabled — isolate the rate × cap invariant
        reserved_amount=reserved,
    )
    assert actual <= reserved, (
        f"actual={actual} > reserved={reserved} "
        f"(elapsed={elapsed}, max={max_solve_seconds}, rate={rate})"
    )


@given(
    elapsed=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    max_solve_seconds=st.floats(
        min_value=0.1, max_value=600.0, allow_nan=False, allow_infinity=False
    ),
)
@_PURE_FAST
def test_actual_le_cap_with_floor(elapsed: float, max_solve_seconds: float) -> None:
    """AC1a — practical FR B2: actual ≤ max(estimated, min_floor).

    The user-visible cap shown in the modal is whichever is greater:
    rate × max_solve_seconds, or the min_floor (¥0.01).
    """
    rate = Decimal("0.10")
    min_floor = Decimal("0.01")
    reserved = Decimal(str(max_solve_seconds)) * rate
    actual = compute_charge_amount(
        elapsed_seconds=elapsed,
        max_solve_seconds=max_solve_seconds,
        rate_per_second=rate,
        min_amount=min_floor,
        reserved_amount=reserved,
    )
    cap = max(reserved, min_floor)
    assert actual <= cap, (
        f"actual={actual} > cap={cap} (elapsed={elapsed}, max={max_solve_seconds})"
    )


# ===== AC2: HTTP-chain invariant =====


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


async def _create_user(engine, user_id: uuid.UUID) -> None:
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
                "phone": f"+86p{user_id.hex[:12]}",
                "email": f"price-{user_id.hex[:10]}@opticloud.test",
            },
        )
        await s.commit()


@given(
    elapsed_seconds=st.floats(min_value=0.1, max_value=120.0, allow_nan=False, allow_infinity=False)
)
@_HTTP_FAST
async def test_estimate_amount_ge_finalize_actual(
    pricing_http_client: AsyncClient,
    pricing_token_factory,
    engine,
    elapsed_seconds: float,
) -> None:
    """AC2 — full HTTP chain: estimate.estimated_amount >= finalize.actual_amount."""
    _, token_for = pricing_token_factory
    user_id = uuid.uuid4()
    await _create_user(engine, user_id)
    headers = {"Authorization": f"Bearer {token_for(user_id)}"}

    # 1. Estimate
    est_resp = await pricing_http_client.post(
        "/v1/billing/charges/estimate",
        json={"purpose": "solve", "max_solve_seconds": 60.0},
        headers=headers,
    )
    assert est_resp.status_code == 200, est_resp.text
    estimated = Decimal(est_resp.json()["estimated_amount"])

    # 2. Reserve (create charge first; estimate triggered p5 warning since 6.00 ≥ 3.00 threshold)
    create_resp = await pricing_http_client.post(
        "/v1/billing/charges",
        json={
            "amount": str(estimated),
            "currency": "CNY",
            "purpose": "solve",
            "reference_id": str(uuid.uuid4()),
            "max_solve_seconds": 60.0,
            "confirmed": True,
        },
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert create_resp.status_code == 201, create_resp.text
    charge_id = create_resp.json()["charge_id"]

    reserve_resp = await pricing_http_client.post(
        f"/v1/billing/charges/{charge_id}/reserve", headers=headers
    )
    assert reserve_resp.status_code == 200, reserve_resp.text

    # 3. Finalize with the Hypothesis-generated elapsed time
    fin_resp = await pricing_http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize",
        headers=headers,
        json={
            "elapsed_seconds": elapsed_seconds,
            "status": "success",
            "failure_reason": None,
        },
    )
    assert fin_resp.status_code == 200, fin_resp.text
    actual = Decimal(fin_resp.json()["actual_amount"])

    # FR B2 invariant — actual NEVER exceeds estimated
    assert actual <= estimated, (
        f"FR B2 violation: actual={actual} > estimated={estimated} (elapsed={elapsed_seconds})"
    )
