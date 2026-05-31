"""Story 5.D.2 — billing usage trends route tests."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from pathlib import Path

import jwt
import pytest
import pytest_asyncio
from billing_service.auth_dep import _loader as _jwt_loader  # noqa: PLC2701
from billing_service.db import get_session
from billing_service.main import app
from billing_service.usage_trends import build_usage_trends
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

_TEST_KEY_DIR = Path("tests/_keys")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def token_factory() -> AsyncIterator[tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]]]:
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
    engine: AsyncEngine,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
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
            "phone": f"+86trend{user_id.hex[:10]}",
            "email": f"trend-{user_id.hex[:10]}@opticloud.test",
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
) -> uuid.UUID:
    transaction_id = uuid.uuid4()
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
            "id": transaction_id,
            "user_id": user_id,
            "amount": amount,
            "kind": kind,
            "bucket": bucket,
            "metadata": metadata,
            "created_at": created_at,
        },
    )
    await session.commit()
    return transaction_id


async def _counts(session: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
    row = (
        (
            await session.execute(
                text(
                    """
                SELECT
                    (SELECT COUNT(*) FROM credit_transactions WHERE user_id = :user_id) AS tx,
                    (SELECT COUNT(*) FROM billing_subscriptions WHERE user_id = :user_id) AS subs,
                    (SELECT COUNT(*) FROM billing_idempotency_keys WHERE user_id = :user_id) AS idem,
                    (SELECT COUNT(*) FROM outbox) AS outbox
                """
                ),
                {"user_id": user_id},
            )
        )
        .mappings()
        .one()
    )
    return {key: int(row[key]) for key in ("tx", "subs", "idem", "outbox")}


def _window(body: dict[str, object], days: int) -> dict[str, object]:
    windows = body["windows"]
    assert isinstance(windows, list)
    for window in windows:
        assert isinstance(window, dict)
        if window["window_days"] == days:
            return window
    pytest.fail(f"missing {days}d window")


def _points_by_date(window: dict[str, object]) -> dict[str, str]:
    points = window["points"]
    assert isinstance(points, list)
    result: dict[str, str] = {}
    for point in points:
        assert isinstance(point, dict)
        result[str(point["date"])] = str(point["actual_spend"])
    return result


async def test_usage_trends_route_is_owner_scoped_zero_filled_and_read_only(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    other_id, _other_headers = await _create_user(session, token_factory)
    today = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0)
    await _insert_ledger(
        session,
        user_id,
        amount="-6.00",
        kind="charge",
        created_at=today,
        metadata='{"raw_body":"must-not-leak","api_key":"sk-test"}',
    )
    await _insert_ledger(
        session,
        other_id,
        amount="-99.00",
        kind="charge",
        created_at=today,
        metadata='{"payment_ref":"other-secret"}',
    )
    before = await _counts(session, user_id)

    response = await http_client.get("/v1/billing/usage-trends", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["trend_contract"] == "billing_usage_trends_v1"
    assert [window["window_days"] for window in body["windows"]] == [7, 30]
    seven = _window(body, 7)
    assert len(seven["points"]) == 7
    assert seven["total_actual_spend"] == "6.00"
    assert seven["average_daily_spend"] == "0.86"
    body_text = str(body).lower()
    assert "99.00" not in body_text
    assert "raw_body" not in body_text
    assert "sk-test" not in body_text
    assert "other-secret" not in body_text
    assert await _counts(session, user_id) == before


async def test_usage_trends_builder_uses_utc_boundaries_and_spend_math(
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, _headers = await _create_user(session, token_factory)
    now = datetime(2026, 5, 31, 12, 0, tzinfo=UTC)
    await _insert_ledger(
        session,
        user_id,
        amount="-10.00",
        kind="charge",
        created_at=datetime(2026, 5, 25, 0, 0, tzinfo=UTC),
    )
    await _insert_ledger(
        session,
        user_id,
        amount="3.00",
        kind="refund_partial",
        created_at=datetime(2026, 5, 25, 23, 59, tzinfo=UTC),
    )
    await _insert_ledger(
        session,
        user_id,
        amount="2.00",
        kind="refund",
        created_at=datetime(2026, 5, 26, 1, 0, tzinfo=UTC),
    )
    await _insert_ledger(
        session,
        user_id,
        amount="-1.00",
        kind="refund_reversal",
        created_at=datetime(2026, 5, 26, 2, 0, tzinfo=UTC),
    )
    await _insert_ledger(
        session,
        user_id,
        amount="-100.00",
        kind="charge",
        created_at=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
    )
    await _insert_ledger(
        session,
        user_id,
        amount="-100.00",
        kind="charge",
        created_at=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
    )
    await _insert_ledger(
        session,
        user_id,
        amount="2000.00",
        kind="monthly_refill",
        created_at=datetime(2026, 5, 27, 0, 0, tzinfo=UTC),
    )
    await _insert_ledger(
        session,
        user_id,
        amount="50.00",
        kind="topup",
        created_at=datetime(2026, 5, 28, 0, 0, tzinfo=UTC),
    )
    await _insert_ledger(
        session,
        user_id,
        amount="-9.00",
        kind="adjustment",
        created_at=datetime(2026, 5, 29, 0, 0, tzinfo=UTC),
    )

    trends = await build_usage_trends(session, user_id, now_utc=now)
    body = trends.model_dump(mode="json")
    seven = _window(body, 7)
    points = _points_by_date(seven)

    assert seven["window_start"] == "2026-05-25T00:00:00Z"
    assert seven["window_end"] == "2026-06-01T00:00:00Z"
    assert list(points) == [
        "2026-05-25",
        "2026-05-26",
        "2026-05-27",
        "2026-05-28",
        "2026-05-29",
        "2026-05-30",
        "2026-05-31",
    ]
    assert points["2026-05-25"] == "7.00"
    assert points["2026-05-26"] == "0.00"
    assert points["2026-05-27"] == "0.00"
    assert points["2026-05-28"] == "0.00"
    assert points["2026-05-29"] == "0.00"
    assert seven["total_actual_spend"] == "7.00"
    assert seven["average_daily_spend"] == "1.00"


async def test_usage_trends_returns_zero_windows_for_new_users(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    _user_id, headers = await _create_user(session, token_factory)

    response = await http_client.get("/v1/billing/usage-trends", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["trend_contract"] == "billing_usage_trends_v1"
    for days in (7, 30):
        window = _window(body, days)
        assert len(window["points"]) == days
        assert window["total_actual_spend"] == "0.00"
        assert window["average_daily_spend"] == "0.00"
        assert {point["actual_spend"] for point in window["points"]} == {"0.00"}
