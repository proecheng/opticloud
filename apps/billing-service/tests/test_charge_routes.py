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
from sqlalchemy import text
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
            "confirmed": True,  # 5.A.5 pre-charge guard (6.00 ≥ p5_threshold 3.00)
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
        "confirmed": True,  # 5.A.5 pre-charge guard
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
            "confirmed": True,  # 5.A.5
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
            "confirmed": True,  # 5.A.5
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
            "confirmed": True,
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
            "confirmed": True,
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


# ===== Story 5.A.4 — split-phase reserve + finalize (AC7 rows 10-14) =====


async def _create_charge(
    http_client: AsyncClient, auth_headers: dict[str, str], *, amount: str = "6.00"
) -> str:
    """Helper: POST /charges and return charge_id. confirmed=True so the 5.A.5 guard accepts."""
    r = await http_client.post(
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
    assert r.status_code == 201, r.text
    return r.json()["charge_id"]


async def test_reserve_happy_path(http_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """AC7 row 10: POST /reserve → state=reserved, balance unchanged."""
    charge_id = await _create_charge(http_client, auth_headers)
    bal_before = (await http_client.get("/v1/billing/balance", headers=auth_headers)).json()[
        "balance"
    ]

    r = await http_client.post(f"/v1/billing/charges/{charge_id}/reserve", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["current_state"] == "reserved"
    assert body["amount_reserved"] == "6.00"
    assert body["balance_after_reserve"] == bal_before


async def test_reserve_on_missing_charge_returns_404(
    http_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """AC7 row 11: POST /reserve on non-existent charge → 404 RFC 7807."""
    r = await http_client.post(f"/v1/billing/charges/{uuid.uuid4()}/reserve", headers=auth_headers)
    assert r.status_code == 404, r.text
    assert r.json()["title"] == "Charge Not Found"


async def test_finalize_success_5s_writes_charge_and_refund_partial(
    http_client: AsyncClient, auth_headers: dict[str, str], session: AsyncSession
) -> None:
    """AC7 row 12: finalize success elapsed=5s → -0.50 charge + +5.50 refund_partial; net -0.50."""
    charge_id = await _create_charge(http_client, auth_headers)
    await http_client.post(f"/v1/billing/charges/{charge_id}/reserve", headers=auth_headers)
    bal_before = float(
        (await http_client.get("/v1/billing/balance", headers=auth_headers)).json()["balance"]
    )

    r = await http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize",
        headers=auth_headers,
        json={"elapsed_seconds": 5.0, "status": "success", "failure_reason": None},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["current_state"] == "charged"
    assert body["reserved_amount"] == "6.00"
    assert body["actual_amount"] == "0.50"
    assert body["refund_partial_amount"] == "5.50"
    bal_after = float(body["balance_after"])
    # Net effect: -0.50 (charge) + 5.50 (refund_partial) − 6.00 (apply writes -reserved) wait...
    # Apply writes -saga.amount = -6.00 row (kind=charge). Then route writes +5.50 (refund_partial).
    # Net change to balance = -6.00 + 5.50 = -0.50. ✅
    assert abs(bal_after - (bal_before - 0.50)) < 1e-6
    metadata = (
        await session.execute(
            text(
                "SELECT metadata FROM credit_transactions "
                "WHERE saga_id = :saga_id AND kind = 'refund_partial'"
            ),
            {"saga_id": uuid.UUID(charge_id)},
        )
    ).scalar_one()
    assert "discount_multiplier" not in metadata


async def test_finalize_success_backtest_discount_halves_actual_charge(
    http_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Story 3.10: finalize success elapsed=5s with 0.5 discount charges 0.25."""
    charge_id = await _create_charge(http_client, auth_headers)
    await http_client.post(f"/v1/billing/charges/{charge_id}/reserve", headers=auth_headers)
    bal_before = float(
        (await http_client.get("/v1/billing/balance", headers=auth_headers)).json()["balance"]
    )

    r = await http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize",
        headers=auth_headers,
        json={
            "elapsed_seconds": 5.0,
            "status": "success",
            "failure_reason": None,
            "discount_multiplier": 0.5,
        },
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["current_state"] == "charged"
    assert body["reserved_amount"] == "6.00"
    assert body["actual_amount"] == "0.25"
    assert body["refund_partial_amount"] == "5.75"
    bal_after = float(body["balance_after"])
    assert abs(bal_after - (bal_before - 0.25)) < 1e-6


async def test_finalize_rejects_invalid_discount_multiplier(
    http_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Story 3.10: discount multiplier must be in (0, 1]."""
    charge_id = await _create_charge(http_client, auth_headers)
    await http_client.post(f"/v1/billing/charges/{charge_id}/reserve", headers=auth_headers)

    r = await http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize",
        headers=auth_headers,
        json={
            "elapsed_seconds": 5.0,
            "status": "success",
            "failure_reason": None,
            "discount_multiplier": 1.5,
        },
    )

    assert r.status_code == 422, r.text


async def test_finalize_failure_writes_net_zero_ledger(
    http_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """AC7 row 13: finalize failure → +amount refund + -amount refund_reversal; balance unchanged."""
    charge_id = await _create_charge(http_client, auth_headers)
    await http_client.post(f"/v1/billing/charges/{charge_id}/reserve", headers=auth_headers)
    bal_before = float(
        (await http_client.get("/v1/billing/balance", headers=auth_headers)).json()["balance"]
    )

    r = await http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize",
        headers=auth_headers,
        json={"elapsed_seconds": 3.0, "status": "failure", "failure_reason": "infeasible"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["current_state"] == "refunded"
    assert body["actual_amount"] == "0.00"
    assert body["refund_partial_amount"] == "0.00"
    bal_after = float(body["balance_after"])
    # +6 refund (from apply user_cancel) + -6 refund_reversal (R1.1) = 0 net
    assert abs(bal_after - bal_before) < 1e-6


async def test_finalize_idempotent_replay_returns_same_response(
    http_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """AC7 row 14: replay finalize on already-CHARGED saga returns rebuilt response, no dup rows."""
    charge_id = await _create_charge(http_client, auth_headers)
    await http_client.post(f"/v1/billing/charges/{charge_id}/reserve", headers=auth_headers)

    body = {"elapsed_seconds": 5.0, "status": "success", "failure_reason": None}
    r1 = await http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize", headers=auth_headers, json=body
    )
    assert r1.status_code == 200, r1.text
    bal_after_first = float(r1.json()["balance_after"])

    # Replay — same body, state already terminal
    r2 = await http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize", headers=auth_headers, json=body
    )
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["current_state"] == "charged"
    assert body2["actual_amount"] == "0.50"
    assert body2["refund_partial_amount"] == "5.50"
    bal_after_second = float(body2["balance_after"])
    # No duplicate ledger rows means balance unchanged across replays
    assert abs(bal_after_second - bal_after_first) < 1e-6


# ===== Story 5.A.5 — pre-charge guard (AC8 rows 7-10) =====


async def test_estimate_no_warnings_with_high_balance(
    http_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """AC8 row 7: estimate happy path, no warnings, requires_explicit_confirm=false."""
    # Seed the user first via a tiny charge so balance is healthy
    await _create_charge(http_client, auth_headers, amount="0.50")

    r = await http_client.post(
        "/v1/billing/charges/estimate",
        json={"purpose": "demo", "max_solve_seconds": 5.0},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["estimated_amount"] == "0.50"  # 5s × 0.10/s
    assert body["warnings"] == []
    assert body["requires_explicit_confirm"] is False


async def test_estimate_low_balance_returns_warning(
    http_client: AsyncClient, auth_headers: dict[str, str], token_factory
) -> None:
    """AC8 row 8: estimate with insufficient balance → balance_low warning, no error."""
    # Fresh user (no seed) — balance is 0.00, estimate is 6.00 → both p5_call + balance_low
    _, token_for = token_factory
    fresh_user = uuid.uuid4()
    fresh_headers = {"Authorization": f"Bearer {token_for(fresh_user)}"}

    r = await http_client.post(
        "/v1/billing/charges/estimate",
        json={"purpose": "solve", "max_solve_seconds": 60.0},
        headers=fresh_headers,
    )
    assert r.status_code == 200, r.text  # Pure preview — NEVER errors on balance
    body = r.json()
    assert body["estimated_amount"] == "6.00"
    assert body["balance"] == "0.00"
    assert body["requires_explicit_confirm"] is True
    assert len(body["warnings"]) == 1
    # 6.00 >= 3.00 AND 0.00 < 6.00 → both → merged
    assert body["warnings"][0]["kind"] == "p5_call_and_balance_low"


async def test_create_charge_blocked_when_confirmed_false_with_warnings(
    http_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """AC8 row 9: POST /charges with warnings + confirmed=false → 422 explicit confirmation required."""
    # Default amount=6.00 with seed balance=50.00 → estimate 6.00 ≥ 3.00 → p5_call warning
    r = await http_client.post(
        "/v1/billing/charges",
        json={
            "amount": "6.00",
            "currency": "CNY",
            "purpose": "solve",
            "reference_id": str(uuid.uuid4()),
            "max_solve_seconds": 60.0,
            # confirmed defaults to False
        },
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["title"] == "Explicit Confirmation Required"
    assert body["errors"][0]["field_path"] == "body.confirmed"
    assert body["errors"][0]["constraint"] == "warnings exist, confirmed must be true"


async def test_create_charge_accepts_confirmed_true_with_warnings(
    http_client: AsyncClient, auth_headers: dict[str, str], engine
) -> None:
    """AC8 row 10: POST /charges with confirmed=true → 201 + payload_ref.user_explicitly_confirmed_at persisted."""
    ref_id = str(uuid.uuid4())
    r = await http_client.post(
        "/v1/billing/charges",
        json={
            "amount": "6.00",
            "currency": "CNY",
            "purpose": "solve",
            "reference_id": ref_id,
            "max_solve_seconds": 60.0,
            "confirmed": True,
        },
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r.status_code == 201, r.text
    charge_id = uuid.UUID(r.json()["charge_id"])

    # Verify payload_ref has the flag (R1.3 — read SagaInstance, not credit_transactions)
    # 5.A.5 uses a boolean flag (not a timestamp) so idempotent body-hashes still match.
    # The "when" comes from saga.created_at.
    from billing_service.models import SagaInstance  # local import keeps top tidy

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        saga = await s.get(SagaInstance, charge_id)
        assert saga is not None
        assert saga.payload_ref.get("user_explicitly_confirmed") is True
        assert saga.created_at is not None


# ===== Story 5.A.2 — Credits balance buckets (FR B1) =====


def _buckets_by_name(body: dict) -> dict[str, dict]:
    return {b["name"]: b for b in body["buckets"]}


async def _create_user_row(engine, user_id: uuid.UUID) -> None:
    """Insert a fresh user row so credit_transactions FK passes."""
    from sqlalchemy import text

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
                "phone": f"+86b{user_id.hex[:12]}",  # ≤20 chars
                "email": f"bucket-{user_id.hex[:10]}@opticloud.test",
            },
        )
        await s.commit()


async def test_balance_returns_all_four_buckets_zero_for_new_user(
    http_client: AsyncClient, token_factory
) -> None:
    """5.A.2 AC10 #1: fresh user → 4 buckets all zero, total 0.00."""
    _, token_for = token_factory
    fresh_user = uuid.uuid4()
    r = await http_client.get(
        "/v1/billing/balance",
        headers={"Authorization": f"Bearer {token_for(fresh_user)}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["balance"] == "0.00"
    by_name = _buckets_by_name(body)
    assert set(by_name) == {"monthly", "signup", "edu", "topup"}
    for name in ("monthly", "signup", "edu", "topup"):
        assert by_name[name]["balance"] == "0.00", f"bucket {name} not zero"


async def test_balance_after_seed_signup_bucket_50_others_zero(
    http_client: AsyncClient, token_factory, engine
) -> None:
    """5.A.2 AC10 #2: lazy-seed lands in signup; monthly/edu/topup stay zero."""
    _, token_for = token_factory
    fresh_user = uuid.uuid4()
    await _create_user_row(engine, fresh_user)
    headers = {"Authorization": f"Bearer {token_for(fresh_user)}"}

    # Trigger lazy-seed via POST /charges (estimate is too cheap to warn)
    await http_client.post(
        "/v1/billing/charges",
        json={
            "amount": "1.00",  # below p5 threshold (3.00) → no warning gate
            "currency": "CNY",
            "purpose": "demo",
            "reference_id": str(uuid.uuid4()),
        },
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )

    r = await http_client.get("/v1/billing/balance", headers=headers)
    body = r.json()
    by_name = _buckets_by_name(body)
    # Seed wrote +50 to signup; monthly stayed at 0 (charge is still PENDING — debit happens on /confirm)
    assert by_name["signup"]["balance"] == "50.00"
    assert by_name["monthly"]["balance"] == "0.00"
    assert by_name["edu"]["balance"] == "0.00"
    assert by_name["topup"]["balance"] == "0.00"
    assert body["balance"] == "50.00"


async def test_balance_after_confirm_signup_50_monthly_minus6(
    http_client: AsyncClient, token_factory, engine
) -> None:
    """5.A.2 AC10 #3: after seed + charge confirm, signup=50, monthly=-6, total=44."""
    _, token_for = token_factory
    fresh_user = uuid.uuid4()
    await _create_user_row(engine, fresh_user)
    headers = {"Authorization": f"Bearer {token_for(fresh_user)}"}

    create = await http_client.post(
        "/v1/billing/charges",
        json={
            "amount": "6.00",
            "currency": "CNY",
            "purpose": "demo",
            "reference_id": str(uuid.uuid4()),
            "confirmed": True,  # 5.A.5 — amount 6 ≥ p5 threshold 3, need explicit confirm
        },
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert create.status_code == 201, create.text
    charge_id = create.json()["charge_id"]

    confirm = await http_client.post(f"/v1/billing/charges/{charge_id}/confirm", headers=headers)
    assert confirm.status_code == 200, confirm.text

    r = await http_client.get("/v1/billing/balance", headers=headers)
    body = r.json()
    by_name = _buckets_by_name(body)
    assert by_name["signup"]["balance"] == "50.00"
    assert by_name["monthly"]["balance"] == "-6.00"
    assert by_name["edu"]["balance"] == "0.00"
    assert by_name["topup"]["balance"] == "0.00"
    assert body["balance"] == "44.00"


async def test_bucket_labels_zh_and_topup_never_expire(
    http_client: AsyncClient, token_factory
) -> None:
    """5.A.2 AC10 #4: response carries correct zh labels + FR B9 commitment."""
    _, token_for = token_factory
    fresh_user = uuid.uuid4()
    r = await http_client.get(
        "/v1/billing/balance",
        headers={"Authorization": f"Bearer {token_for(fresh_user)}"},
    )
    by_name = _buckets_by_name(r.json())
    assert by_name["monthly"]["label_zh"] == "月度"
    assert by_name["signup"]["label_zh"] == "注册"
    assert by_name["edu"]["label_zh"] == "教育"
    assert by_name["topup"]["label_zh"] == "加油包"
    # FR B9 visible commitment — topup bucket carries 永不过期 hint
    assert by_name["topup"]["expires_hint"] == "永不过期"
