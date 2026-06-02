"""Story 5.D.6 - notification preference route tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from auth_service.config import settings
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

SUPPORTED_EVENTS = [
    "billing.budget.alerted",
    "billing.budget.paused",
    "status.incident.published",
]


def _phone() -> str:
    return f"+8613{uuid.uuid4().int % 10**10:010d}"


def _email() -> str:
    return f"notify-{uuid.uuid4().hex[:10]}@example.com"


@pytest_asyncio.fixture(autouse=True)
async def _ensure_notification_schema(engine: AsyncEngine) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS notification_preferences (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    event_type VARCHAR(64) NOT NULL,
                    email_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    webhook_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    in_app_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    webhook_url TEXT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await s.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_notification_preferences_user_event "
                "ON notification_preferences(user_id, event_type)"
            )
        )
        await s.execute(
            text(
                "ALTER TABLE notification_preferences "
                "DROP CONSTRAINT IF EXISTS ck_notification_preferences_event_type"
            )
        )
        await s.execute(
            text(
                """
                ALTER TABLE notification_preferences
                    ADD CONSTRAINT ck_notification_preferences_event_type
                    CHECK (
                        event_type IN (
                            'billing.budget.alerted',
                            'billing.budget.paused',
                            'status.incident.published'
                        )
                    )
                """
            )
        )
        await s.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS status_incident_notification_requests (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    incident_id VARCHAR(96) NOT NULL,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    status_url TEXT NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    severity VARCHAR(16) NOT NULL,
                    incident_status VARCHAR(32) NOT NULL,
                    channels TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
                    webhook_url_configured BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await s.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "idx_status_incident_notification_requests_incident_user "
                "ON status_incident_notification_requests(incident_id, user_id)"
            )
        )
        await s.execute(text("DELETE FROM status_incident_notification_requests"))
        await s.execute(text("DELETE FROM notification_preferences"))
        await s.execute(
            text("DELETE FROM outbox WHERE event_type = 'auth.notification_preferences.updated'")
        )
        await s.execute(
            text("DELETE FROM outbox WHERE event_type = 'status.incident.notification_requested'")
        )
        await s.execute(
            text("DELETE FROM audit_logs WHERE action = 'auth.notification_preferences.updated'")
        )
        await s.commit()


@pytest_asyncio.fixture
async def admin_secret() -> AsyncIterator[str]:
    header_value = "incident-admin-fixture"
    original = settings.admin_secret
    settings.admin_secret = header_value
    yield header_value
    settings.admin_secret = original


async def _signup(http_client: AsyncClient) -> tuple[uuid.UUID, str]:
    response = await http_client.post(
        "/v1/auth/signup",
        json={"phone": _phone(), "email": _email(), "age_years": 18},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return uuid.UUID(body["user_id"]), body["jwt_access"]


def _headers(jwt: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jwt}"}


def _preference(
    event_type: str,
    *,
    email: bool = True,
    webhook: bool = False,
    in_app: bool = True,
    webhook_url: str | None = None,
) -> dict[str, object]:
    return {
        "event_type": event_type,
        "email": email,
        "webhook": webhook,
        "in_app": in_app,
        "webhook_url": webhook_url,
    }


async def _row_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    return int(
        (
            await session.execute(
                text("SELECT count(*) FROM notification_preferences WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
        ).scalar_one()
    )


async def test_get_defaults_returns_supported_events(http_client: AsyncClient) -> None:
    _, jwt = await _signup(http_client)

    response = await http_client.get(
        "/v1/auth/notification-preferences",
        headers=_headers(jwt),
    )

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [item["event_type"] for item in items] == SUPPORTED_EVENTS
    assert all(item["webhook"] is False for item in items)
    assert all(item["webhook_url"] is None for item in items)
    assert items[0]["email"] is True
    assert items[0]["in_app"] is True
    assert items[0]["channels"] == ["email", "in_app"]
    assert items[1]["email"] is True
    assert items[1]["in_app"] is True
    assert items[1]["channels"] == ["email", "in_app"]
    assert items[2]["email"] is False
    assert items[2]["in_app"] is False
    assert items[2]["channels"] == []


async def test_put_upserts_full_replacement_and_writes_safe_audit_outbox(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    user_id, jwt = await _signup(http_client)
    payload = {
        "items": [
            _preference("billing.budget.alerted", email=False, in_app=True),
            _preference(
                "billing.budget.paused",
                email=True,
                webhook=True,
                in_app=False,
                webhook_url="https://hooks.example.com/opticloud",
            ),
            _preference(
                "status.incident.published",
                email=False,
                webhook=True,
                in_app=True,
                webhook_url="https://incident-hooks.example.com/opticloud",
            ),
        ]
    }

    first = await http_client.put(
        "/v1/auth/notification-preferences",
        headers=_headers(jwt),
        json=payload,
    )
    second = await http_client.put(
        "/v1/auth/notification-preferences",
        headers=_headers(jwt),
        json=payload,
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    items = {item["event_type"]: item for item in second.json()["items"]}
    assert items["billing.budget.alerted"]["channels"] == ["in_app"]
    assert items["billing.budget.paused"]["channels"] == ["email", "webhook"]
    assert items["billing.budget.paused"]["webhook_url_configured"] is True
    assert items["billing.budget.paused"]["webhook_url"] == "https://hooks.example.com/opticloud"
    assert items["status.incident.published"]["channels"] == ["webhook", "in_app"]
    assert items["status.incident.published"]["webhook_url_configured"] is True

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        assert await _row_count(session, user_id) == 3
        audit_count = (
            await session.execute(
                text(
                    "SELECT count(*) FROM audit_logs "
                    "WHERE user_id = :user_id "
                    "AND action = 'auth.notification_preferences.updated'"
                ),
                {"user_id": user_id},
            )
        ).scalar_one()
        outbox_rows = (
            (
                await session.execute(
                    text(
                        "SELECT payload FROM outbox "
                        "WHERE aggregate_id = :user_id "
                        "AND event_type = 'auth.notification_preferences.updated'"
                    ),
                    {"user_id": user_id},
                )
            )
            .mappings()
            .all()
        )
    assert audit_count == 2
    assert len(outbox_rows) == 2
    serialized = str([dict(row) for row in outbox_rows])
    assert "hooks.example.com" not in serialized
    assert "incident-hooks.example.com" not in serialized
    assert "status.incident.published" in serialized
    assert "webhook_url_configured" in serialized


async def test_put_rejects_missing_duplicate_and_unknown_events_without_mutation(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    user_id, jwt = await _signup(http_client)
    valid = {
        "items": [
            _preference("billing.budget.alerted", email=False, in_app=True),
            _preference("billing.budget.paused", email=True, in_app=False),
            _preference("status.incident.published", email=False, in_app=True),
        ]
    }
    saved = await http_client.put(
        "/v1/auth/notification-preferences", headers=_headers(jwt), json=valid
    )
    assert saved.status_code == 200, saved.text

    invalid_payloads = [
        {"items": [_preference("billing.budget.alerted")]},
        {
            "items": [
                _preference("billing.budget.alerted"),
                _preference("billing.budget.alerted", email=False),
                _preference("status.incident.published"),
            ]
        },
        {
            "items": [
                _preference("billing.budget.alerted"),
                _preference("billing.invoice.ready"),
                _preference("status.incident.published"),
            ]
        },
    ]
    for payload in invalid_payloads:
        response = await http_client.put(
            "/v1/auth/notification-preferences",
            headers=_headers(jwt),
            json=payload,
        )
        assert response.status_code == 422, response.text

    current = await http_client.get("/v1/auth/notification-preferences", headers=_headers(jwt))
    assert current.status_code == 200, current.text
    items = {item["event_type"]: item for item in current.json()["items"]}
    assert items["billing.budget.alerted"]["email"] is False
    assert items["billing.budget.paused"]["in_app"] is False
    assert items["status.incident.published"]["in_app"] is True

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        assert await _row_count(session, user_id) == 3


async def test_put_incident_item_without_channel_fields_stays_disabled(
    http_client: AsyncClient,
) -> None:
    _, jwt = await _signup(http_client)

    response = await http_client.put(
        "/v1/auth/notification-preferences",
        headers=_headers(jwt),
        json={
            "items": [
                _preference("billing.budget.alerted"),
                _preference("billing.budget.paused"),
                {"event_type": "status.incident.published"},
            ]
        },
    )

    assert response.status_code == 200, response.text
    items = {item["event_type"]: item for item in response.json()["items"]}
    assert items["status.incident.published"]["email"] is False
    assert items["status.incident.published"]["in_app"] is False
    assert items["status.incident.published"]["webhook"] is False
    assert items["status.incident.published"]["channels"] == []


@pytest.mark.parametrize(
    "webhook_url",
    [
        "http://hooks.example.com/opticloud",
        "https://hooks.example.com/opticloud?token=secret",
        "https://user:pass@hooks.example.com/opticloud",
        "https://127.0.0.1/opticloud",
        "https://10.0.0.5/opticloud",
        "https://service.internal/opticloud",
    ],
)
async def test_put_rejects_unsafe_webhook_urls_without_mutation(
    http_client: AsyncClient,
    engine: AsyncEngine,
    webhook_url: str,
) -> None:
    user_id, jwt = await _signup(http_client)

    response = await http_client.put(
        "/v1/auth/notification-preferences",
        headers=_headers(jwt),
        json={
            "items": [
                _preference(
                    "status.incident.published",
                    webhook=True,
                    webhook_url=webhook_url,
                ),
                _preference("billing.budget.alerted"),
                _preference("billing.budget.paused"),
            ]
        },
    )

    assert response.status_code == 422, response.text
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        assert await _row_count(session, user_id) == 0


async def test_preferences_are_user_scoped(http_client: AsyncClient) -> None:
    _, jwt_a = await _signup(http_client)
    _, jwt_b = await _signup(http_client)
    saved = await http_client.put(
        "/v1/auth/notification-preferences",
        headers=_headers(jwt_a),
        json={
            "items": [
                _preference("billing.budget.alerted", email=False, in_app=False),
                _preference("billing.budget.paused", email=False, in_app=False),
                _preference("status.incident.published", email=True, in_app=True),
            ]
        },
    )
    assert saved.status_code == 200, saved.text

    b_defaults = await http_client.get("/v1/auth/notification-preferences", headers=_headers(jwt_b))

    assert b_defaults.status_code == 200, b_defaults.text
    items = {item["event_type"]: item for item in b_defaults.json()["items"]}
    assert items["billing.budget.alerted"]["channels"] == ["email", "in_app"]
    assert items["billing.budget.paused"]["channels"] == ["email", "in_app"]
    assert items["status.incident.published"]["channels"] == []


async def test_frozen_user_cannot_read_or_update_preferences(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    user_id, jwt = await _signup(http_client)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await session.execute(
            text("UPDATE users SET is_frozen = true WHERE id = :user_id"),
            {"user_id": user_id},
        )
        await session.commit()

    read = await http_client.get("/v1/auth/notification-preferences", headers=_headers(jwt))
    write = await http_client.put(
        "/v1/auth/notification-preferences",
        headers=_headers(jwt),
        json={
            "items": [
                _preference("billing.budget.alerted", email=False),
                _preference("billing.budget.paused", email=False),
                _preference("status.incident.published", email=True),
            ]
        },
    )

    assert read.status_code == 403, read.text
    assert write.status_code == 403, write.text


async def test_incident_fanout_creates_pointer_safe_requests_for_explicit_subscribers_only(
    http_client: AsyncClient,
    engine: AsyncEngine,
    admin_secret: str,
) -> None:
    subscribed_user_id, subscribed_jwt = await _signup(http_client)
    unsubscribed_user_id, unsubscribed_jwt = await _signup(http_client)
    frozen_user_id, frozen_jwt = await _signup(http_client)

    subscribed_payload = {
        "items": [
            _preference("billing.budget.alerted"),
            _preference("billing.budget.paused"),
            _preference(
                "status.incident.published",
                email=True,
                webhook=True,
                in_app=False,
                webhook_url="https://incident-hooks.example.com/opticloud",
            ),
        ]
    }
    unsubscribed_payload = {
        "items": [
            _preference("billing.budget.alerted"),
            _preference("billing.budget.paused"),
            _preference("status.incident.published", email=False, webhook=False, in_app=False),
        ]
    }
    frozen_payload = {
        "items": [
            _preference("billing.budget.alerted"),
            _preference("billing.budget.paused"),
            _preference("status.incident.published", email=True, in_app=True),
        ]
    }
    for jwt, payload in [
        (subscribed_jwt, subscribed_payload),
        (unsubscribed_jwt, unsubscribed_payload),
        (frozen_jwt, frozen_payload),
    ]:
        response = await http_client.put(
            "/v1/auth/notification-preferences",
            headers=_headers(jwt),
            json=payload,
        )
        assert response.status_code == 200, response.text

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await session.execute(
            text("UPDATE users SET is_frozen = true WHERE id = :user_id"),
            {"user_id": frozen_user_id},
        )
        await session.commit()

    payload = {
        "incident_id": "inc-2026-06-02-solver-latency",
        "title": "Solver queue latency above target",
        "severity": "minor",
        "status": "monitoring",
    }
    first = await http_client.post(
        "/v1/admin/status/incidents/fanout",
        headers={"X-Admin-Secret": admin_secret},
        json=payload,
    )
    second = await http_client.post(
        "/v1/admin/status/incidents/fanout",
        headers={"X-Admin-Secret": admin_secret},
        json=payload,
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json() == {
        "incident_id": "inc-2026-06-02-solver-latency",
        "eligible_subscribers": 1,
        "created_requests": 1,
        "status_url": "/status#inc-2026-06-02-solver-latency",
    }
    assert second.json()["created_requests"] == 0

    async with maker() as session:
        request_rows = (
            (
                await session.execute(
                    text(
                        "SELECT user_id, channels, webhook_url_configured, status_url "
                        "FROM status_incident_notification_requests"
                    )
                )
            )
            .mappings()
            .all()
        )
        outbox_rows = (
            (
                await session.execute(
                    text(
                        "SELECT payload FROM outbox "
                        "WHERE event_type = 'status.incident.notification_requested'"
                    )
                )
            )
            .mappings()
            .all()
        )

    assert len(request_rows) == 1
    assert request_rows[0]["user_id"] == subscribed_user_id
    assert list(request_rows[0]["channels"]) == ["email", "webhook"]
    assert request_rows[0]["webhook_url_configured"] is True
    assert request_rows[0]["status_url"] == "/status#inc-2026-06-02-solver-latency"
    assert len(outbox_rows) == 1
    serialized = str([dict(row) for row in outbox_rows])
    assert str(subscribed_user_id) in serialized
    assert str(unsubscribed_user_id) not in serialized
    assert str(frozen_user_id) not in serialized
    assert "incident-hooks.example.com" not in serialized
    assert "webhook_url_configured" in serialized


async def test_incident_fanout_fails_closed_without_admin_secret(
    http_client: AsyncClient,
) -> None:
    original = settings.admin_secret
    settings.admin_secret = ""
    try:
        response = await http_client.post(
            "/v1/admin/status/incidents/fanout",
            json={
                "incident_id": "inc-2026-06-02-solver-latency",
                "title": "Solver queue latency above target",
                "severity": "minor",
                "status": "monitoring",
            },
        )
    finally:
        settings.admin_secret = original

    assert response.status_code == 403, response.text
