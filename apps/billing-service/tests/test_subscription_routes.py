"""Story 5.B.1/5.B.2 — subscription and education Starter route tests."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
import pytest_asyncio
from billing_service.auth_dep import _loader as _jwt_loader  # noqa: PLC2701
from billing_service.config import settings
from billing_service.db import get_session
from billing_service.main import app
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

_TEST_KEY_DIR = Path("tests/_keys")
_INTERNAL_SECRET = "test-subscription-internal-secret"  # noqa: S105


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
async def http_client(
    engine: AsyncEngine, token_factory: tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]]
) -> AsyncIterator[AsyncClient]:
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


@pytest.fixture(autouse=True)
def _internal_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "internal_service_secret", SecretStr(_INTERNAL_SECRET))


def _internal_headers(secret: str = _INTERNAL_SECRET) -> dict[str, str]:
    return {"X-Internal-Service-Auth": secret}


async def _create_user_row(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    edu_tier: bool = False,
    with_edu_signup_seed: bool = False,
) -> None:
    await session.execute(
        text(
            "INSERT INTO users (id, phone, email, edu_tier, created_at, updated_at) "
            "VALUES (:id, :phone, :email, :edu_tier, NOW(), NOW()) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {
            "id": user_id,
            "phone": f"+86sub{user_id.hex[:10]}",
            "email": (
                f"sub-{user_id.hex[:10]}@stanford.edu"
                if edu_tier
                else f"sub-{user_id.hex[:10]}@opticloud.test"
            ),
            "edu_tier": edu_tier,
        },
    )
    if with_edu_signup_seed:
        await session.execute(
            text(
                """
                INSERT INTO credit_transactions
                    (user_id, saga_id, amount, kind, bucket, currency, metadata, created_at)
                VALUES
                    (:user_id, NULL, 2000.00, 'topup', 'edu', 'CNY',
                     '{"source":"edu_tier_signup"}'::jsonb, NOW())
                """
            ),
            {"user_id": user_id},
        )
    await session.commit()


@pytest_asyncio.fixture
async def fresh_headers(
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]],
) -> tuple[uuid.UUID, dict[str, str]]:
    _, token_for = token_factory
    user_id = uuid.uuid4()
    await _create_user_row(session, user_id)
    return user_id, {"Authorization": f"Bearer {token_for(user_id)}"}


def _subscribe_body(plan_code: str = "starter") -> dict[str, str]:
    return {"plan_code": plan_code}


async def _subscribe(
    http_client: AsyncClient,
    headers: dict[str, str],
    *,
    plan_code: str = "starter",
    key: str | None = None,
) -> dict:
    response = await http_client.post(
        "/v1/billing/subscriptions",
        json=_subscribe_body(plan_code),
        headers={**headers, "Idempotency-Key": key or str(uuid.uuid4())},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _counts(session: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
    row = (
        (
            await session.execute(
                text(
                    """
                SELECT
                    (SELECT COUNT(*) FROM billing_subscriptions
                     WHERE user_id = :user_id) AS subscriptions,
                    (SELECT COUNT(*) FROM credit_transactions
                     WHERE user_id = :user_id AND kind = 'monthly_refill') AS refills,
                    (SELECT COUNT(*) FROM outbox
                     WHERE aggregate_type = 'billing_subscription'
                       AND aggregate_id IN (
                           SELECT id FROM billing_subscriptions WHERE user_id = :user_id
                       )) AS outbox_events
                """
                ),
                {"user_id": user_id},
            )
        )
        .mappings()
        .one()
    )
    return {key: int(row[key]) for key in ("subscriptions", "refills", "outbox_events")}


async def _monthly_balance(http_client: AsyncClient, headers: dict[str, str]) -> str:
    balance = await http_client.get("/v1/billing/balance", headers=headers)
    assert balance.status_code == 200, balance.text
    buckets = {bucket["name"]: bucket for bucket in balance.json()["buckets"]}
    return str(buckets["monthly"]["balance"])


async def _bucket_balance(
    http_client: AsyncClient, headers: dict[str, str], bucket_name: str
) -> str:
    balance = await http_client.get("/v1/billing/balance", headers=headers)
    assert balance.status_code == 200, balance.text
    buckets = {bucket["name"]: bucket for bucket in balance.json()["buckets"]}
    return str(buckets[bucket_name]["balance"])


async def _stored_response_body(session: AsyncSession, idem_key: str) -> dict | None:
    return (
        await session.execute(
            text("SELECT response_body FROM billing_idempotency_keys WHERE key = :key"),
            {"key": idem_key},
        )
    ).scalar_one_or_none()


async def _edu_refill_rows(session: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    rows = (
        (
            await session.execute(
                text(
                    """
                    SELECT amount, bucket, kind, metadata
                      FROM credit_transactions
                     WHERE user_id = :user_id
                       AND kind = 'monthly_refill'
                       AND bucket = 'edu'
                     ORDER BY created_at ASC
                    """
                ),
                {"user_id": user_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


async def _subscription_metadata(session: AsyncSession, subscription_id: str) -> dict:
    return (
        await session.execute(
            text("SELECT metadata FROM billing_subscriptions WHERE id = :subscription_id"),
            {"subscription_id": uuid.UUID(subscription_id)},
        )
    ).scalar_one()


async def _subscription_outbox_payloads(session: AsyncSession, subscription_id: str) -> list[dict]:
    rows = (
        (
            await session.execute(
                text(
                    """
                    SELECT event_type, payload
                      FROM outbox
                     WHERE aggregate_type = 'billing_subscription'
                       AND aggregate_id = :subscription_id
                     ORDER BY occurred_at ASC
                    """
                ),
                {"subscription_id": uuid.UUID(subscription_id)},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


async def test_plan_catalog_returns_five_stable_plans(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
) -> None:
    _user_id, headers = fresh_headers
    response = await http_client.get("/v1/billing/plans", headers=headers)

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [item["code"] for item in items] == ["free", "starter", "pro", "team", "enterprise"]
    assert [item["monthly_credits"] for item in items] == [
        "0.00",
        "2000.00",
        "10000.00",
        "50000.00",
        "200000.00",
    ]
    assert items[0]["rate_limits"]["rps"] == 3
    assert items[1]["rate_limits"]["requests_per_minute"] == 200
    assert items[-1]["rate_limits"]["custom"] is True
    assert items[-1]["commercial_review_required"] is True


async def test_current_subscription_is_implicit_free_and_pure_read(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
    session: AsyncSession,
) -> None:
    user_id, headers = fresh_headers

    response = await http_client.get("/v1/billing/subscriptions/current", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["subscription_id"] is None
    assert body["plan_code"] == "free"
    assert body["status"] == "implicit_free"
    assert body["current_period_start"] is None
    assert body["current_period_end"] is None
    assert await _counts(session, user_id) == {
        "subscriptions": 0,
        "refills": 0,
        "outbox_events": 0,
    }


@pytest.mark.parametrize(
    ("plan_code", "expected_monthly"),
    [
        ("free", "0.00"),
        ("starter", "2000.00"),
        ("pro", "10000.00"),
        ("team", "50000.00"),
        ("enterprise", "200000.00"),
    ],
)
async def test_subscribe_all_five_plans_apply_initial_period_and_refill_once(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]],
    plan_code: str,
    expected_monthly: str,
) -> None:
    _, token_for = token_factory
    user_id = uuid.uuid4()
    await _create_user_row(session, user_id)
    headers = {"Authorization": f"Bearer {token_for(user_id)}"}

    body = await _subscribe(http_client, headers, plan_code=plan_code)

    assert body["plan_code"] == plan_code
    assert body["status"] == "active"
    assert body["current_period_start"] is not None
    assert body["current_period_end"] is not None
    assert body["monthly_credits"] == expected_monthly
    assert await _monthly_balance(http_client, headers) == expected_monthly
    counts = await _counts(session, user_id)
    assert counts["subscriptions"] == 1
    assert counts["refills"] == (0 if plan_code == "free" else 1)
    assert counts["outbox_events"] == (1 if plan_code == "free" else 2)


async def test_subscribe_replay_returns_cached_response_without_duplicate_refill(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
    session: AsyncSession,
) -> None:
    user_id, headers = fresh_headers
    key = str(uuid.uuid4())
    request_body = _subscribe_body("starter")

    first = await http_client.post(
        "/v1/billing/subscriptions",
        json=request_body,
        headers={**headers, "Idempotency-Key": key},
    )
    replay = await http_client.post(
        "/v1/billing/subscriptions",
        json=request_body,
        headers={**headers, "Idempotency-Key": key},
    )

    assert first.status_code == 201, first.text
    assert replay.status_code == 201, replay.text
    assert replay.json() == first.json()
    assert await _stored_response_body(session, key) == first.json()
    counts = await _counts(session, user_id)
    assert counts["subscriptions"] == 1
    assert counts["refills"] == 1


async def test_subscribe_same_key_different_body_conflicts_without_mutation(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
    session: AsyncSession,
) -> None:
    user_id, headers = fresh_headers
    key = str(uuid.uuid4())
    first = await http_client.post(
        "/v1/billing/subscriptions",
        json=_subscribe_body("starter"),
        headers={**headers, "Idempotency-Key": key},
    )
    assert first.status_code == 201, first.text

    conflict = await http_client.post(
        "/v1/billing/subscriptions",
        json=_subscribe_body("pro"),
        headers={**headers, "Idempotency-Key": key},
    )

    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["title"] == "Idempotency Conflict"
    assert await _stored_response_body(session, key) == first.json()
    counts = await _counts(session, user_id)
    assert counts["subscriptions"] == 1
    assert counts["refills"] == 1


async def test_subscribe_cross_tenant_key_reuse_never_returns_owner_response(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
    token_factory: tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]],
    session: AsyncSession,
) -> None:
    _owner_id, owner_headers = fresh_headers
    key = str(uuid.uuid4())
    first = await http_client.post(
        "/v1/billing/subscriptions",
        json=_subscribe_body("starter"),
        headers={**owner_headers, "Idempotency-Key": key},
    )
    assert first.status_code == 201, first.text

    other_user_id = uuid.uuid4()
    await _create_user_row(session, other_user_id)
    _, token_for = token_factory
    other_headers = {"Authorization": f"Bearer {token_for(other_user_id)}"}
    replay = await http_client.post(
        "/v1/billing/subscriptions",
        json=_subscribe_body("starter"),
        headers={**other_headers, "Idempotency-Key": key},
    )

    assert replay.status_code == 403, replay.text
    assert first.json()["subscription_id"] not in replay.text


async def test_existing_same_plan_is_noop_and_different_plan_is_deferred(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
    session: AsyncSession,
) -> None:
    user_id, headers = fresh_headers
    first = await _subscribe(http_client, headers, plan_code="starter")

    same = await http_client.post(
        "/v1/billing/subscriptions",
        json=_subscribe_body("starter"),
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert same.status_code == 201, same.text
    assert same.json() == first

    different = await http_client.post(
        "/v1/billing/subscriptions",
        json=_subscribe_body("pro"),
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert different.status_code == 409, different.text
    assert different.json()["title"] == "Plan change deferred"
    counts = await _counts(session, user_id)
    assert counts["subscriptions"] == 1
    assert counts["refills"] == 1
    assert await _monthly_balance(http_client, headers) == "2000.00"


async def test_edu_sync_reuses_signup_seed_without_duplicate_initial_refill(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]],
) -> None:
    _, token_for = token_factory
    user_id = uuid.uuid4()
    await _create_user_row(session, user_id, edu_tier=True, with_edu_signup_seed=True)
    headers = {"Authorization": f"Bearer {token_for(user_id)}"}

    first = await http_client.post(
        "/v1/billing/subscriptions/edu-starter/sync",
        json={"user_id": str(user_id)},
        headers=_internal_headers(),
    )
    replay = await http_client.post(
        "/v1/billing/subscriptions/edu-starter/sync",
        json={"user_id": str(user_id)},
        headers=_internal_headers(),
    )

    assert first.status_code == 200, first.text
    assert replay.status_code == 200, replay.text
    assert replay.json() == first.json()
    body = first.json()
    assert body["plan_code"] == "starter"
    assert body["monthly_credits"] == "2000.00"
    assert body["entitlement_source"] == "edu_tier"
    assert body["refill_bucket"] == "edu"
    assert body["external_payment_required"] is False
    assert await _bucket_balance(http_client, headers, "edu") == "2000.00"
    assert await _edu_refill_rows(session, user_id) == []
    counts = await _counts(session, user_id)
    assert counts["subscriptions"] == 1
    assert counts["outbox_events"] == 1


async def test_edu_sync_imported_user_without_seed_gets_initial_edu_refill(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]],
) -> None:
    _, token_for = token_factory
    user_id = uuid.uuid4()
    await _create_user_row(session, user_id, edu_tier=True)
    headers = {"Authorization": f"Bearer {token_for(user_id)}"}

    response = await http_client.post(
        "/v1/billing/subscriptions/edu-starter/sync",
        json={"user_id": str(user_id)},
        headers=_internal_headers(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["plan_code"] == "starter"
    assert body["entitlement_source"] == "edu_tier"
    assert body["refill_bucket"] == "edu"
    assert body["external_payment_required"] is False
    assert await _bucket_balance(http_client, headers, "edu") == "2000.00"
    rows = await _edu_refill_rows(session, user_id)
    assert len(rows) == 1
    assert str(rows[0]["amount"]) == "2000.0000"
    assert rows[0]["metadata"]["entitlement_source"] == "edu_tier"
    assert rows[0]["metadata"]["trigger"] == "activation"


async def test_edu_user_starter_subscribe_uses_edu_bucket_and_payment_free(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]],
) -> None:
    _, token_for = token_factory
    user_id = uuid.uuid4()
    await _create_user_row(session, user_id, edu_tier=True)
    headers = {"Authorization": f"Bearer {token_for(user_id)}"}

    body = await _subscribe(http_client, headers, plan_code="starter")

    assert body["plan_code"] == "starter"
    assert body["entitlement_source"] == "edu_tier"
    assert body["refill_bucket"] == "edu"
    assert body["external_payment_required"] is False
    assert await _bucket_balance(http_client, headers, "edu") == "2000.00"
    assert await _bucket_balance(http_client, headers, "monthly") == "0.00"
    metadata = await _subscription_metadata(session, body["subscription_id"])
    assert metadata["education_entitlement"] == "starter_free"


async def test_edu_sync_upgrades_active_free_in_place_and_resets_zero_refill_state(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]],
) -> None:
    _, token_for = token_factory
    user_id = uuid.uuid4()
    await _create_user_row(session, user_id, edu_tier=True)
    headers = {"Authorization": f"Bearer {token_for(user_id)}"}
    free = await _subscribe(http_client, headers, plan_code="free")
    subscription_id = free["subscription_id"]

    response = await http_client.post(
        "/v1/billing/subscriptions/edu-starter/sync",
        json={"user_id": str(user_id)},
        headers=_internal_headers(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["subscription_id"] == subscription_id
    assert body["plan_code"] == "starter"
    assert body["entitlement_source"] == "edu_tier"
    assert body["refill_bucket"] == "edu"
    assert await _bucket_balance(http_client, headers, "edu") == "2000.00"
    rows = await _edu_refill_rows(session, user_id)
    assert len(rows) == 1
    counts = await _counts(session, user_id)
    assert counts["subscriptions"] == 1


async def test_edu_sync_marks_existing_starter_and_emits_activation_event(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]],
) -> None:
    _, token_for = token_factory
    user_id = uuid.uuid4()
    await _create_user_row(session, user_id, edu_tier=False)
    headers = {"Authorization": f"Bearer {token_for(user_id)}"}
    starter = await _subscribe(http_client, headers, plan_code="starter")
    await session.execute(
        text("UPDATE users SET edu_tier = TRUE WHERE id = :user_id"),
        {"user_id": user_id},
    )
    await session.commit()

    response = await http_client.post(
        "/v1/billing/subscriptions/edu-starter/sync",
        json={"user_id": str(user_id)},
        headers=_internal_headers(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["subscription_id"] == starter["subscription_id"]
    assert body["entitlement_source"] == "edu_tier"
    assert body["refill_bucket"] == "edu"
    outbox = await _subscription_outbox_payloads(session, starter["subscription_id"])
    assert [row["event_type"] for row in outbox].count(
        "billing.subscription.edu_starter.activated"
    ) == 1
    assert outbox[-1]["payload"]["entitlement_source"] == "edu_tier"
    forbidden = {"token", "jwt", "email", "phone", "payment_ref", "provider", "raw_body"}
    for row in outbox:
        payload_text = str(row["payload"]).lower()
        assert forbidden.isdisjoint(payload_text.split())


async def test_edu_starter_subscribe_does_not_cache_non_starter_active_plan(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]],
) -> None:
    _, token_for = token_factory
    user_id = uuid.uuid4()
    await _create_user_row(session, user_id, edu_tier=True)
    headers = {"Authorization": f"Bearer {token_for(user_id)}"}
    pro = await _subscribe(http_client, headers, plan_code="pro")
    key = str(uuid.uuid4())

    response = await http_client.post(
        "/v1/billing/subscriptions",
        json=_subscribe_body("starter"),
        headers={**headers, "Idempotency-Key": key},
    )

    assert response.status_code == 409, response.text
    assert response.json()["title"] == "Plan change deferred"
    assert await _stored_response_body(session, key) is None
    current = await http_client.get("/v1/billing/subscriptions/current", headers=headers)
    assert current.status_code == 200, current.text
    assert current.json()["subscription_id"] == pro["subscription_id"]
    assert current.json()["plan_code"] == "pro"


async def test_non_edu_sync_rejected_without_mutation(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
    session: AsyncSession,
) -> None:
    user_id, _headers = fresh_headers

    response = await http_client.post(
        "/v1/billing/subscriptions/edu-starter/sync",
        json={"user_id": str(user_id)},
        headers=_internal_headers(),
    )

    assert response.status_code == 403, response.text
    assert response.json()["title"] == "Education entitlement not available"
    assert await _counts(session, user_id) == {
        "subscriptions": 0,
        "refills": 0,
        "outbox_events": 0,
    }


async def test_edu_refill_due_uses_edu_bucket_and_replay_is_idempotent(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, callable[[uuid.UUID], str]],
) -> None:
    _, token_for = token_factory
    user_id = uuid.uuid4()
    await _create_user_row(session, user_id, edu_tier=True, with_edu_signup_seed=True)
    headers = {"Authorization": f"Bearer {token_for(user_id)}"}
    created = await http_client.post(
        "/v1/billing/subscriptions/edu-starter/sync",
        json={"user_id": str(user_id)},
        headers=_internal_headers(),
    )
    assert created.status_code == 200, created.text
    subscription_id = uuid.UUID(created.json()["subscription_id"])
    due_end = datetime.now(UTC) - timedelta(days=1)
    due_start = due_end - timedelta(days=31)
    await session.execute(
        text(
            """
            UPDATE billing_subscriptions
               SET current_period_start = :period_start,
                   current_period_end = :period_end,
                   last_refilled_period_start = :period_start
             WHERE id = :subscription_id
            """
        ),
        {
            "period_start": due_start,
            "period_end": due_end,
            "subscription_id": subscription_id,
        },
    )
    await session.commit()

    as_of = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    first = await http_client.post(
        "/v1/billing/subscriptions/refill-due",
        json={"as_of": as_of},
        headers=_internal_headers(),
    )
    replay = await http_client.post(
        "/v1/billing/subscriptions/refill-due",
        json={"as_of": as_of},
        headers=_internal_headers(),
    )

    assert first.status_code == 200, first.text
    assert replay.status_code == 200, replay.text
    assert first.json()["processed"] == 1
    assert first.json()["refilled"] == 1
    assert replay.json()["processed"] == 0
    assert replay.json()["refilled"] == 0
    assert await _bucket_balance(http_client, headers, "edu") == "4000.00"
    assert await _bucket_balance(http_client, headers, "monthly") == "0.00"
    rows = await _edu_refill_rows(session, user_id)
    assert len(rows) == 1
    assert rows[0]["metadata"]["trigger"] == "scheduled_refill"


async def test_refill_due_requires_internal_auth(
    http_client: AsyncClient,
) -> None:
    missing = await http_client.post("/v1/billing/subscriptions/refill-due", json={})
    wrong = await http_client.post(
        "/v1/billing/subscriptions/refill-due",
        json={},
        headers=_internal_headers("wrong-secret"),
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401


async def test_refill_due_advances_period_once_and_replay_is_idempotent(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
    session: AsyncSession,
) -> None:
    user_id, headers = fresh_headers
    subscription = await _subscribe(http_client, headers, plan_code="starter")
    subscription_id = uuid.UUID(subscription["subscription_id"])
    due_end = datetime.now(UTC) - timedelta(days=1)
    due_start = due_end - timedelta(days=31)
    await session.execute(
        text(
            """
            UPDATE billing_subscriptions
               SET current_period_start = :period_start,
                   current_period_end = :period_end,
                   last_refilled_period_start = :period_start
             WHERE id = :subscription_id
            """
        ),
        {
            "period_start": due_start,
            "period_end": due_end,
            "subscription_id": subscription_id,
        },
    )
    await session.commit()

    as_of = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    first = await http_client.post(
        "/v1/billing/subscriptions/refill-due",
        json={"as_of": as_of},
        headers=_internal_headers(),
    )
    replay = await http_client.post(
        "/v1/billing/subscriptions/refill-due",
        json={"as_of": as_of},
        headers=_internal_headers(),
    )

    assert first.status_code == 200, first.text
    assert replay.status_code == 200, replay.text
    assert first.json()["processed"] == 1
    assert first.json()["refilled"] == 1
    assert replay.json()["processed"] == 0
    assert replay.json()["refilled"] == 0
    counts = await _counts(session, user_id)
    assert counts["subscriptions"] == 1
    assert counts["refills"] == 2
    assert await _monthly_balance(http_client, headers) == "4000.00"


async def test_refill_due_catches_up_multiple_due_periods(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
    session: AsyncSession,
) -> None:
    user_id, headers = fresh_headers
    subscription = await _subscribe(http_client, headers, plan_code="starter")
    subscription_id = uuid.UUID(subscription["subscription_id"])
    due_end = datetime.now(UTC) - timedelta(days=65)
    due_start = due_end - timedelta(days=31)
    await session.execute(
        text(
            """
            UPDATE billing_subscriptions
               SET current_period_start = :period_start,
                   current_period_end = :period_end,
                   last_refilled_period_start = :period_start
             WHERE id = :subscription_id
            """
        ),
        {
            "period_start": due_start,
            "period_end": due_end,
            "subscription_id": subscription_id,
        },
    )
    await session.commit()

    response = await http_client.post(
        "/v1/billing/subscriptions/refill-due",
        json={"as_of": datetime.now(UTC).isoformat().replace("+00:00", "Z")},
        headers=_internal_headers(),
    )

    assert response.status_code == 200, response.text
    assert response.json()["processed"] == 1
    assert response.json()["refilled"] >= 2
    counts = await _counts(session, user_id)
    assert counts["refills"] == 1 + response.json()["refilled"]
    assert await _monthly_balance(http_client, headers) == f"{counts['refills'] * 2000:.2f}"


async def test_subscription_metadata_and_outbox_are_pointer_safe(
    http_client: AsyncClient,
    fresh_headers: tuple[uuid.UUID, dict[str, str]],
    session: AsyncSession,
) -> None:
    _user_id, headers = fresh_headers
    body = await _subscribe(http_client, headers, plan_code="starter")
    subscription_id = uuid.UUID(body["subscription_id"])

    ledger_metadata = (
        await session.execute(
            text(
                """
                SELECT metadata FROM credit_transactions
                 WHERE user_id = :user_id
                   AND kind = 'monthly_refill'
                   AND metadata ->> 'subscription_id' = :subscription_id
                """
            ),
            {"user_id": _user_id, "subscription_id": str(subscription_id)},
        )
    ).scalar_one()
    assert ledger_metadata["subscription_id"] == str(subscription_id)
    assert ledger_metadata["plan_code"] == "starter"
    assert ledger_metadata["trigger"] == "activation"
    assert ledger_metadata["period_start"]
    assert ledger_metadata["period_end"]

    rows = (
        (
            await session.execute(
                text(
                    """
                SELECT payload FROM outbox
                 WHERE aggregate_id = :subscription_id
                   AND aggregate_type = 'billing_subscription'
                 ORDER BY occurred_at ASC
                """
                ),
                {"subscription_id": subscription_id},
            )
        )
        .scalars()
        .all()
    )

    assert rows
    forbidden = {"token", "jwt", "email", "phone", "payment_ref", "provider", "raw_body"}
    for payload in rows:
        payload_text = str(payload).lower()
        assert forbidden.isdisjoint(payload_text.split())
        assert payload["subscription_id"] == str(subscription_id)
        assert payload["plan_code"] == "starter"
