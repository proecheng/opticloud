"""Story 5.D.5 — monthly budget alert and automatic pause route tests."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import jwt
import pytest_asyncio
from billing_service.auth_dep import _loader as _jwt_loader  # noqa: PLC2701
from billing_service.budget import current_budget_period, monthly_actual_spend
from billing_service.db import get_session
from billing_service.main import app
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

_TEST_KEY_DIR = Path("tests/_keys")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def token_factory() -> AsyncIterator[tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]]]:
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
    engine: AsyncEngine,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
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


async def _create_user(
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> tuple[uuid.UUID, dict[str, str]]:
    _, token_for = token_factory
    user_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO users (id, phone, email, created_at, updated_at)
            VALUES (:id, :phone, :email, NOW(), NOW())
            """
        ),
        {
            "id": user_id,
            "phone": f"+86budget{user_id.hex[:8]}",
            "email": f"budget-{user_id.hex[:10]}@opticloud.test",
        },
    )
    await session.commit()
    return user_id, {"Authorization": f"Bearer {token_for(user_id)}"}


async def _insert_ledger(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    amount: str,
    kind: str,
    created_at: datetime,
    bucket: str = "monthly",
    metadata: str = "{}",
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO credit_transactions
                (id, user_id, saga_id, amount, kind, bucket, currency, metadata, created_at)
            VALUES
                (:id, :user_id, NULL, :amount, :kind, :bucket, 'CNY',
                 CAST(:metadata AS jsonb), :created_at)
            """
        ),
        {
            "id": uuid.uuid4(),
            "user_id": user_id,
            "amount": amount,
            "kind": kind,
            "bucket": bucket,
            "metadata": metadata,
            "created_at": created_at,
        },
    )
    await session.commit()


async def _budget_event_rows(session: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    rows = (
        (
            await session.execute(
                text(
                    """
                    SELECT event_type, payload
                      FROM billing_budget_events
                     WHERE user_id = :user_id
                     ORDER BY occurred_at ASC, event_type ASC
                    """
                ),
                {"user_id": user_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


async def _budget_outbox_rows(session: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    rows = (
        (
            await session.execute(
                text(
                    """
                    SELECT o.event_type, o.payload
                      FROM outbox o
                      JOIN billing_budget_controls c
                        ON c.id = o.aggregate_id
                     WHERE c.user_id = :user_id
                     ORDER BY o.occurred_at ASC, o.event_type ASC
                    """
                ),
                {"user_id": user_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


async def _counts(session: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
    row = (
        (
            await session.execute(
                text(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM billing_budget_controls
                         WHERE user_id = :user_id) AS controls,
                        (SELECT COUNT(*) FROM billing_budget_events
                         WHERE user_id = :user_id) AS events,
                        (SELECT COUNT(*) FROM credit_transactions
                         WHERE user_id = :user_id) AS tx,
                        (SELECT COUNT(*) FROM saga_instances
                         WHERE user_id = :user_id) AS sagas,
                        (SELECT COUNT(*) FROM billing_idempotency_keys
                         WHERE user_id = :user_id) AS idem
                    """
                ),
                {"user_id": user_id},
            )
        )
        .mappings()
        .one()
    )
    return {key: int(row[key]) for key in ("controls", "events", "tx", "sagas", "idem")}


async def test_budget_get_is_pure_and_put_validates_body(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    before = await _counts(session, user_id)

    get_response = await http_client.get("/v1/billing/budget", headers=headers)
    invalid_low = await http_client.put(
        "/v1/billing/budget",
        headers=headers,
        json={"monthly_budget_amount": "0.99", "user_id": str(uuid.uuid4())},
    )
    invalid_decimal = await http_client.put(
        "/v1/billing/budget",
        headers=headers,
        json={"monthly_budget_amount": "not-a-number", "enabled": True},
    )

    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["status"] == "not_configured"
    assert await _counts(session, user_id) == before
    assert invalid_low.status_code == 422, invalid_low.text
    assert invalid_low.json()["title"] == "Invalid Budget Request"
    assert invalid_decimal.status_code == 422, invalid_decimal.text
    assert invalid_decimal.json()["errors"][0]["field_path"] == "body.monthly_budget_amount"
    assert await _counts(session, user_id) == before


async def test_budget_put_configures_alerts_and_pauses_idempotently(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    period = current_budget_period(datetime(2026, 6, 1, 12, tzinfo=UTC))
    await _insert_ledger(
        session,
        user_id,
        amount="-80.00",
        kind="charge",
        created_at=period.start.replace(day=3, hour=1),
        metadata='{"api_key":"sk-must-not-leak","raw_body":"secret"}',
    )
    await _insert_ledger(
        session,
        user_id,
        amount="10.00",
        kind="refund_partial",
        created_at=period.start.replace(day=3, hour=2),
    )
    await _insert_ledger(
        session,
        user_id,
        amount="2000.00",
        kind="monthly_refill",
        created_at=period.start.replace(day=1, hour=1),
    )

    alert = await http_client.put(
        "/v1/billing/budget",
        headers=headers,
        json={"monthly_budget_amount": "100.00", "enabled": True},
    )
    pause = await http_client.put(
        "/v1/billing/budget",
        headers=headers,
        json={"monthly_budget_amount": "70.00", "enabled": True},
    )
    replay = await http_client.put(
        "/v1/billing/budget",
        headers=headers,
        json={"monthly_budget_amount": "70.00", "enabled": True},
    )

    assert alert.status_code == 200, alert.text
    assert alert.json()["actual_spend"] == "70.00"
    assert alert.json()["percent_used"] == "0.7000"
    assert alert.json()["paused"] is False
    assert pause.status_code == 200, pause.text
    assert pause.json()["status"] == "paused"
    assert pause.json()["actual_spend"] == "70.00"
    assert pause.json()["percent_used"] == "1.0000"
    assert replay.status_code == 200, replay.text
    events = await _budget_event_rows(session, user_id)
    event_types = [row["event_type"] for row in events]
    assert event_types.count("billing.budget.configured") == 3
    assert event_types.count("billing.budget.alerted") == 1
    assert event_types.count("billing.budget.paused") == 1
    outbox_types = [row["event_type"] for row in await _budget_outbox_rows(session, user_id)]
    assert outbox_types.count("billing.budget.alerted") == 1
    assert outbox_types.count("billing.budget.paused") == 1
    serialized = str(events + await _budget_outbox_rows(session, user_id)).lower()
    assert "sk-must-not-leak" not in serialized
    assert "raw_body" not in serialized


async def test_budget_can_be_disabled_or_increased_to_resume_charges(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    await _insert_ledger(
        session,
        user_id,
        amount="-90.00",
        kind="charge",
        created_at=datetime.now(UTC),
    )
    await _insert_ledger(
        session,
        user_id,
        amount="200.00",
        kind="topup",
        created_at=datetime.now(UTC),
        bucket="topup",
    )
    paused = await http_client.put(
        "/v1/billing/budget",
        headers=headers,
        json={"monthly_budget_amount": "50.00", "enabled": True},
    )
    assert paused.json()["paused"] is True

    blocked = await http_client.post(
        "/v1/billing/charges",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "amount": "1.00",
            "currency": "CNY",
            "purpose": "demo",
            "reference_id": str(uuid.uuid4()),
        },
    )
    counts_after_block = await _counts(session, user_id)
    increased = await http_client.put(
        "/v1/billing/budget",
        headers=headers,
        json={"monthly_budget_amount": "200.00", "enabled": True},
    )
    allowed = await http_client.post(
        "/v1/billing/charges",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "amount": "1.00",
            "currency": "CNY",
            "purpose": "demo",
            "reference_id": str(uuid.uuid4()),
        },
    )
    disabled = await http_client.put(
        "/v1/billing/budget",
        headers=headers,
        json={"enabled": False},
    )

    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["title"] == "Monthly Budget Paused"
    assert counts_after_block["sagas"] == 0
    assert counts_after_block["idem"] == 0
    assert increased.status_code == 200, increased.text
    assert increased.json()["status"] == "active"
    assert increased.json()["paused"] is False
    assert allowed.status_code == 201, allowed.text
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["status"] == "disabled"
    assert disabled.json()["paused"] is False


async def test_confirm_and_finalize_evaluate_budget_thresholds_once(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    await http_client.put(
        "/v1/billing/budget",
        headers=headers,
        json={"monthly_budget_amount": "10.00", "enabled": True},
    )
    await _insert_ledger(
        session, user_id, amount="50.00", kind="topup", created_at=datetime.now(UTC)
    )

    confirm_create = await http_client.post(
        "/v1/billing/charges",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "amount": "8.00",
            "currency": "CNY",
            "purpose": "demo",
            "reference_id": str(uuid.uuid4()),
            "confirmed": True,
        },
    )
    assert confirm_create.status_code == 201, confirm_create.text
    confirm = await http_client.post(
        f"/v1/billing/charges/{confirm_create.json()['charge_id']}/confirm",
        headers=headers,
    )
    assert confirm.status_code == 200, confirm.text
    event_types = [row["event_type"] for row in await _budget_event_rows(session, user_id)]
    assert event_types.count("billing.budget.alerted") == 1
    assert "billing.budget.paused" not in event_types

    finalize_create = await http_client.post(
        "/v1/billing/charges",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "amount": "6.00",
            "currency": "CNY",
            "purpose": "solve",
            "reference_id": str(uuid.uuid4()),
            "confirmed": True,
        },
    )
    assert finalize_create.status_code == 201, finalize_create.text
    charge_id = finalize_create.json()["charge_id"]
    await http_client.post(f"/v1/billing/charges/{charge_id}/reserve", headers=headers)
    finalize = await http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize",
        headers=headers,
        json={"elapsed_seconds": 60.0, "status": "success", "failure_reason": None},
    )
    replay = await http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize",
        headers=headers,
        json={"elapsed_seconds": 60.0, "status": "success", "failure_reason": None},
    )

    assert finalize.status_code == 200, finalize.text
    assert replay.status_code == 200, replay.text
    event_types = [row["event_type"] for row in await _budget_event_rows(session, user_id)]
    assert event_types.count("billing.budget.alerted") == 1
    assert event_types.count("billing.budget.paused") == 1
    assert [row["event_type"] for row in await _budget_outbox_rows(session, user_id)].count(
        "billing.budget.paused"
    ) == 1
    spend = await monthly_actual_spend(session, user_id, current_budget_period())
    assert spend == Decimal("14.0000")
