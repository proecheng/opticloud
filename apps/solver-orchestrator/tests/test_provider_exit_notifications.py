"""Story 6.C.2 - Provider exit >=30d notification fan-out tests."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from solver_orchestrator.config import settings
from solver_orchestrator.db import get_session
from solver_orchestrator.main import app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


DATABASE_URL = os.getenv("DATABASE_URL", settings.database_url)
ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 6, 6, 8, 0, tzinfo=UTC)
EXIT_AT = NOW + timedelta(days=31)
PROVIDER_ID = "exit-fixture-highs"


def _make_api_key() -> tuple[str, str, int]:
    full = f"sk-{uuid.uuid4().hex}"
    pepper_version = 1
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    key_hash = hmac.new(pepper, full.encode("utf-8"), hashlib.sha256).hexdigest()
    return full, key_hash, pepper_version


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    await _apply_schema(eng)
    yield eng
    await eng.dispose()


async def _apply_schema(db_engine: AsyncEngine) -> None:
    async with db_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    phone VARCHAR(20) NOT NULL UNIQUE,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    edu_tier BOOLEAN NOT NULL DEFAULT FALSE,
                    age_verified BOOLEAN NOT NULL DEFAULT FALSE,
                    risk_score NUMERIC(3, 2) NOT NULL DEFAULT 0.00,
                    is_frozen BOOLEAN NOT NULL DEFAULT FALSE,
                    merged_into_user_id UUID NULL,
                    merged_at TIMESTAMPTZ NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    deleted_at TIMESTAMPTZ NULL
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    key_hash TEXT NOT NULL,
                    key_prefix VARCHAR(10) NOT NULL,
                    pepper_version INTEGER NOT NULL DEFAULT 1,
                    label VARCHAR(255) NOT NULL,
                    description TEXT NULL,
                    scope TEXT[] NOT NULL DEFAULT '{}',
                    expires_at TIMESTAMPTZ NULL,
                    last_used_at TIMESTAMPTZ NULL,
                    last_used_ip INET NULL,
                    last_used_geo_bucket VARCHAR(64) NULL,
                    geo_risk_score NUMERIC(3, 2) NOT NULL DEFAULT 0.00,
                    geo_anomaly_at TIMESTAMPTZ NULL,
                    geo_anomaly_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    revoked_at TIMESTAMPTZ NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS outbox (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    aggregate_type VARCHAR(255) NOT NULL,
                    aggregate_id UUID NOT NULL,
                    event_type VARCHAR(255) NOT NULL,
                    event_version INTEGER NOT NULL DEFAULT 1,
                    payload JSONB NOT NULL,
                    headers JSONB NOT NULL DEFAULT '{}'::jsonb,
                    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    sent_at TIMESTAMPTZ NULL
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS optimizations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL,
                    api_key_id UUID NOT NULL,
                    task_type VARCHAR(50) NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'queued',
                    input_payload JSONB NOT NULL,
                    solution JSONB NULL,
                    objective NUMERIC NULL,
                    model_version JSONB NULL,
                    error JSONB NULL,
                    solve_seconds NUMERIC NULL,
                    idempotency_key VARCHAR(255) NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMPTZ NULL
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS reproduction_vouchers (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    voucher_id VARCHAR(32) NOT NULL UNIQUE,
                    optimization_id UUID NOT NULL UNIQUE REFERENCES optimizations(id) ON DELETE CASCADE,
                    user_id UUID NOT NULL,
                    api_key_id UUID NOT NULL,
                    request_fingerprint TEXT NOT NULL,
                    locked_model_version JSONB NOT NULL,
                    locked_solver VARCHAR(64) NOT NULL,
                    seed_locked BOOLEAN NOT NULL,
                    seed INTEGER NULL,
                    anonymous BOOLEAN NOT NULL DEFAULT FALSE,
                    status VARCHAR(32) NOT NULL DEFAULT 'issued',
                    parent_voucher_id UUID NULL,
                    rerun_depth INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS provider_exit_plans (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    provider_id VARCHAR(96) NOT NULL,
                    effective_at TIMESTAMPTZ NOT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'scheduled',
                    reason VARCHAR(255) NOT NULL,
                    replacement_provider_id VARCHAR(96) NULL,
                    public_message VARCHAR(500) NULL,
                    created_by VARCHAR(64) NOT NULL DEFAULT 'admin-secret',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_exit_plans_provider_effective
                ON provider_exit_plans(provider_id, effective_at)
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS provider_exit_notification_requests (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    exit_plan_id UUID NOT NULL REFERENCES provider_exit_plans(id) ON DELETE CASCADE,
                    user_id UUID NOT NULL,
                    provider_id VARCHAR(96) NOT NULL,
                    status_url TEXT NOT NULL,
                    affected_voucher_count INTEGER NOT NULL,
                    channels TEXT[] NOT NULL DEFAULT ARRAY['email', 'in_app']::TEXT[],
                    email_requested BOOLEAN NOT NULL DEFAULT TRUE,
                    in_app_requested BOOLEAN NOT NULL DEFAULT TRUE,
                    webhook_requested BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_exit_notification_requests_plan_user
                ON provider_exit_notification_requests(exit_plan_id, user_id)
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS provider_exit_status_announcements (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    exit_plan_id UUID NOT NULL REFERENCES provider_exit_plans(id) ON DELETE CASCADE,
                    announcement_id VARCHAR(128) NOT NULL,
                    provider_id VARCHAR(96) NOT NULL,
                    effective_at TIMESTAMPTZ NOT NULL,
                    status_url TEXT NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    summary VARCHAR(500) NOT NULL,
                    severity VARCHAR(16) NOT NULL,
                    announcement_status VARCHAR(32) NOT NULL,
                    affected_user_count INTEGER NOT NULL DEFAULT 0,
                    affected_voucher_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_exit_status_announcements_plan
                ON provider_exit_status_announcements(exit_plan_id)
                """
            )
        )


@pytest_asyncio.fixture(autouse=True)
async def _clean_provider_exit_tables(db_engine: AsyncEngine) -> None:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "DELETE FROM outbox WHERE event_type IN "
                "('provider.exit.notification_requested', "
                "'provider.exit.status_announcement_requested')"
            )
        )
        await s.execute(text("DELETE FROM provider_exit_notification_requests"))
        await s.execute(text("DELETE FROM provider_exit_status_announcements"))
        await s.execute(text("DELETE FROM provider_exit_plans"))
        await s.execute(
            text(
                """
                DELETE FROM reproduction_vouchers
                WHERE user_id IN (SELECT id FROM users WHERE email LIKE '6-c-2-%')
                """
            )
        )
        await s.execute(
            text(
                """
                DELETE FROM optimizations
                WHERE user_id IN (SELECT id FROM users WHERE email LIKE '6-c-2-%')
                """
            )
        )
        await s.execute(
            text(
                """
                DELETE FROM api_keys
                WHERE user_id IN (SELECT id FROM users WHERE email LIKE '6-c-2-%')
                """
            )
        )
        await s.execute(text("DELETE FROM users WHERE email LIKE '6-c-2-%'"))
        await s.commit()


@pytest_asyncio.fixture
async def admin_secret() -> AsyncIterator[str]:
    header_value = "provider-exit-admin-fixture"
    original = settings.admin_secret
    settings.admin_secret = header_value
    yield header_value
    settings.admin_secret = original


@pytest_asyncio.fixture
async def client_with_db(db_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)

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
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _seed_user(
    db_engine: AsyncEngine,
    *,
    label: str,
    deleted: bool = False,
    frozen: bool = False,
    merged: bool = False,
) -> tuple[uuid.UUID, uuid.UUID]:
    user_id = uuid.uuid4()
    key_id = uuid.uuid4()
    full, key_hash, pepper_version = _make_api_key()
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                """
                INSERT INTO users(
                    id, email, phone, is_frozen, merged_at, deleted_at, created_at, updated_at
                )
                VALUES(
                    :user_id, :email, :phone, :is_frozen, :merged_at, :deleted_at, :now, :now
                )
                """
            ),
            {
                "user_id": user_id,
                "email": f"6-c-2-{label}-{user_id}@example.com",
                "phone": f"+861{user_id.int % 10**10:010d}",
                "is_frozen": frozen,
                "merged_at": NOW if merged else None,
                "deleted_at": NOW if deleted else None,
                "now": NOW,
            },
        )
        await s.execute(
            text(
                """
                INSERT INTO api_keys(
                    id, user_id, label, key_prefix, key_hash, pepper_version,
                    scope, created_at, expires_at
                )
                VALUES(
                    :key_id, :user_id, :label, :prefix, :key_hash, :pepper_version,
                    ARRAY['optimize:write'], :now, :expires_at
                )
                """
            ),
            {
                "key_id": key_id,
                "user_id": user_id,
                "label": label,
                "prefix": full[:6],
                "key_hash": key_hash,
                "pepper_version": pepper_version,
                "now": NOW,
                "expires_at": NOW + timedelta(days=365),
            },
        )
        await s.commit()
    return user_id, key_id


async def _seed_voucher(
    db_engine: AsyncEngine,
    *,
    user_id: uuid.UUID,
    api_key_id: uuid.UUID,
    provider_id: str = PROVIDER_ID,
    voucher_status: str = "issued",
    created_at: datetime = NOW,
    anonymous: bool = False,
) -> str:
    optimization_id = uuid.uuid4()
    voucher_id = f"repro-{created_at.year}-{uuid.uuid4().hex[:6].upper()}"
    locked_model_version = {
        "provider_id": provider_id,
        "kind": "open_source",
        "version": "1.7.0",
        "provider_url": f"https://providers.example/{provider_id}",
    }
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                """
                INSERT INTO optimizations(
                    id, user_id, api_key_id, task_type, status, input_payload,
                    solution, objective, model_version, solve_seconds, created_at, completed_at
                )
                VALUES(
                    :optimization_id, :user_id, :api_key_id, 'lp', 'completed',
                    CAST(:input_payload AS jsonb), CAST(:solution AS jsonb), 2.0,
                    CAST(:model_version AS jsonb), 0.01, :created_at, :created_at
                )
                """
            ),
            {
                "optimization_id": optimization_id,
                "user_id": user_id,
                "api_key_id": api_key_id,
                "input_payload": json.dumps(
                    {
                        "task_type": "lp",
                        "minimize": {"c": [1.0, 1.0]},
                        "st": {"A": [[1.0, 1.0]], "b": [10.0]},
                    }
                ),
                "solution": json.dumps({"x": [1.0, 1.0]}),
                "model_version": json.dumps(locked_model_version),
                "created_at": created_at,
            },
        )
        await s.execute(
            text(
                """
                INSERT INTO reproduction_vouchers(
                    voucher_id, optimization_id, user_id, api_key_id, request_fingerprint,
                    locked_model_version, locked_solver, seed_locked, seed, anonymous,
                    status, created_at
                )
                VALUES(
                    :voucher_id, :optimization_id, :user_id, :api_key_id,
                    'fingerprint-secret', CAST(:locked_model_version AS jsonb),
                    'highs', TRUE, NULL, :anonymous, :voucher_status, :created_at
                )
                """
            ),
            {
                "voucher_id": voucher_id,
                "optimization_id": optimization_id,
                "user_id": user_id,
                "api_key_id": api_key_id,
                "locked_model_version": json.dumps(locked_model_version),
                "anonymous": anonymous,
                "voucher_status": voucher_status,
                "created_at": created_at,
            },
        )
        await s.commit()
    return voucher_id


def _payload(effective_at: datetime = EXIT_AT) -> dict[str, object]:
    return {
        "provider_id": PROVIDER_ID,
        "effective_at": effective_at.isoformat(),
        "reason": "provider contract exit",
        "replacement_provider_id": "replacement-highs",
        "public_message": "Provider exit-fixture-highs will exit; reruns remain covered by Repro SLA.",
    }


def test_local_init_schema_contains_provider_exit_notification_contract() -> None:
    schema = (ROOT / "infra/local-init/02-solver-schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS provider_exit_plans" in schema
    assert "CREATE TABLE IF NOT EXISTS provider_exit_notification_requests" in schema
    assert "CREATE TABLE IF NOT EXISTS provider_exit_status_announcements" in schema
    assert "uq_provider_exit_plans_provider_effective" in schema
    assert "uq_provider_exit_notification_requests_plan_user" in schema
    assert "uq_provider_exit_status_announcements_plan" in schema
    assert "ARRAY['email', 'in_app']" in schema
    assert "notification_preferences" not in schema


async def test_provider_exit_requires_admin_secret(
    client_with_db: AsyncClient,
    admin_secret: str,
) -> None:
    original = settings.admin_secret
    settings.admin_secret = ""
    try:
        disabled = await client_with_db.post("/v1/admin/provider-exits", json=_payload())
    finally:
        settings.admin_secret = original

    assert disabled.status_code == 403, disabled.text

    missing = await client_with_db.post("/v1/admin/provider-exits", json=_payload())
    invalid = await client_with_db.post(
        "/v1/admin/provider-exits",
        headers={"X-Admin-Secret": f"{admin_secret}-wrong"},
        json=_payload(),
    )

    assert missing.status_code == 401, missing.text
    assert invalid.status_code == 401, invalid.text


async def test_provider_exit_rejects_control_characters_without_mutation(
    client_with_db: AsyncClient,
    db_engine: AsyncEngine,
    admin_secret: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("solver_orchestrator.provider_exit_notifications.utc_now", lambda: NOW)

    bad_reason = _payload()
    bad_reason["reason"] = "provider contract exit\x00hidden"
    bad_message = _payload()
    bad_message["public_message"] = "public update\x1fhidden"

    for payload in (bad_reason, bad_message):
        response = await client_with_db.post(
            "/v1/admin/provider-exits",
            headers={"X-Admin-Secret": admin_secret},
            json=payload,
        )
        assert response.status_code == 422, response.text

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        counts = (
            (
                await s.execute(
                    text(
                        """
                    SELECT
                        (SELECT COUNT(*) FROM provider_exit_plans) AS plans,
                        (SELECT COUNT(*) FROM provider_exit_notification_requests) AS requests,
                        (SELECT COUNT(*) FROM provider_exit_status_announcements) AS announcements,
                        (
                            SELECT COUNT(*) FROM outbox
                            WHERE event_type LIKE 'provider.exit.%'
                        ) AS outbox
                    """
                    )
                )
            )
            .mappings()
            .one()
        )
    assert dict(counts) == {"plans": 0, "requests": 0, "announcements": 0, "outbox": 0}


async def test_provider_exit_rejects_less_than_30d_without_mutation(
    client_with_db: AsyncClient,
    db_engine: AsyncEngine,
    admin_secret: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("solver_orchestrator.provider_exit_notifications.utc_now", lambda: NOW)

    response = await client_with_db.post(
        "/v1/admin/provider-exits",
        headers={"X-Admin-Secret": admin_secret},
        json=_payload(NOW + timedelta(days=30) - timedelta(seconds=1)),
    )

    assert response.status_code == 422, response.text
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        counts = (
            (
                await s.execute(
                    text(
                        """
                    SELECT
                        (SELECT COUNT(*) FROM provider_exit_plans) AS plans,
                        (SELECT COUNT(*) FROM provider_exit_notification_requests) AS requests,
                        (SELECT COUNT(*) FROM provider_exit_status_announcements) AS announcements,
                        (
                            SELECT COUNT(*) FROM outbox
                            WHERE event_type LIKE 'provider.exit.%'
                        ) AS outbox
                    """
                    )
                )
            )
            .mappings()
            .one()
        )
    assert dict(counts) == {"plans": 0, "requests": 0, "announcements": 0, "outbox": 0}


async def test_provider_exit_fans_out_to_unique_active_voucher_holders_only(
    client_with_db: AsyncClient,
    db_engine: AsyncEngine,
    admin_secret: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("solver_orchestrator.provider_exit_notifications.utc_now", lambda: NOW)
    user_a, key_a = await _seed_user(db_engine, label="active-a")
    user_b, key_b = await _seed_user(db_engine, label="active-b")
    frozen_user, frozen_key = await _seed_user(db_engine, label="frozen", frozen=True)
    deleted_user, deleted_key = await _seed_user(db_engine, label="deleted", deleted=True)
    merged_user, merged_key = await _seed_user(db_engine, label="merged", merged=True)

    await _seed_voucher(db_engine, user_id=user_a, api_key_id=key_a, anonymous=True)
    await _seed_voucher(db_engine, user_id=user_a, api_key_id=key_a)
    await _seed_voucher(db_engine, user_id=user_b, api_key_id=key_b)
    await _seed_voucher(db_engine, user_id=user_b, api_key_id=key_b, provider_id="other-provider")
    await _seed_voucher(db_engine, user_id=user_b, api_key_id=key_b, voucher_status="revoked")
    await _seed_voucher(
        db_engine,
        user_id=user_b,
        api_key_id=key_b,
        created_at=NOW.replace(year=2020),
    )
    await _seed_voucher(db_engine, user_id=frozen_user, api_key_id=frozen_key)
    await _seed_voucher(db_engine, user_id=deleted_user, api_key_id=deleted_key)
    await _seed_voucher(db_engine, user_id=merged_user, api_key_id=merged_key)

    response = await client_with_db.post(
        "/v1/admin/provider-exits",
        headers={"X-Admin-Secret": admin_secret},
        json=_payload(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider_id"] == PROVIDER_ID
    assert body["affected_users"] == 2
    assert body["affected_vouchers"] == 3
    assert body["notification_requests_created"] == 2
    assert body["status_url"] == "/status#provider-exit-exit-fixture-highs-20260707"
    assert body["announcement_id"] == "provider-exit-exit-fixture-highs-20260707"

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        request_rows = (
            (
                await s.execute(
                    text(
                        """
                        SELECT user_id, affected_voucher_count, channels, email_requested,
                               in_app_requested, webhook_requested, status_url
                        FROM provider_exit_notification_requests
                        ORDER BY affected_voucher_count DESC, user_id
                        """
                    )
                )
            )
            .mappings()
            .all()
        )
        outbox_payloads = (
            (
                await s.execute(
                    text(
                        """
                        SELECT event_type, payload
                        FROM outbox
                        WHERE event_type LIKE 'provider.exit.%'
                        ORDER BY event_type, occurred_at
                        """
                    )
                )
            )
            .mappings()
            .all()
        )

    assert len(request_rows) == 2
    by_user = {row["user_id"]: row for row in request_rows}
    assert by_user[user_a]["affected_voucher_count"] == 2
    assert by_user[user_b]["affected_voucher_count"] == 1
    for row in request_rows:
        assert list(row["channels"]) == ["email", "in_app"]
        assert row["email_requested"] is True
        assert row["in_app_requested"] is True
        assert row["webhook_requested"] is False
        assert row["status_url"] == "/status#provider-exit-exit-fixture-highs-20260707"

    assert [row["event_type"] for row in outbox_payloads].count(
        "provider.exit.notification_requested"
    ) == 2
    assert [row["event_type"] for row in outbox_payloads].count(
        "provider.exit.status_announcement_requested"
    ) == 1
    serialized = json.dumps([dict(row) for row in outbox_payloads], default=str)
    assert "fingerprint-secret" not in serialized
    assert "repro-" not in serialized
    assert "api_key_id" not in serialized
    assert "anonymous" not in serialized
    assert "provider.exit.notification_requested" in serialized
    assert '"channels": ["email", "in_app"]' in serialized
    assert str(frozen_user) not in serialized
    assert str(deleted_user) not in serialized
    assert str(merged_user) not in serialized


async def test_provider_exit_uses_per_voucher_5y_calendar_expiry_boundary(
    client_with_db: AsyncClient,
    db_engine: AsyncEngine,
    admin_secret: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary_now = datetime(2029, 2, 28, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        "solver_orchestrator.provider_exit_notifications.utc_now", lambda: boundary_now
    )
    expired_user, expired_key = await _seed_user(db_engine, label="leap-expired")
    active_user, active_key = await _seed_user(db_engine, label="leap-active")
    await _seed_voucher(
        db_engine,
        user_id=expired_user,
        api_key_id=expired_key,
        created_at=datetime(2024, 2, 29, 12, 0, tzinfo=UTC),
    )
    await _seed_voucher(
        db_engine,
        user_id=active_user,
        api_key_id=active_key,
        created_at=datetime(2024, 2, 29, 12, 0, 0, 1, tzinfo=UTC),
    )

    response = await client_with_db.post(
        "/v1/admin/provider-exits",
        headers={"X-Admin-Secret": admin_secret},
        json=_payload(boundary_now + timedelta(days=31)),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["affected_users"] == 1
    assert body["affected_vouchers"] == 1
    assert body["notification_requests_created"] == 1

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        notified_users = (
            (await s.execute(text("SELECT user_id FROM provider_exit_notification_requests")))
            .scalars()
            .all()
        )
    assert notified_users == [active_user]


async def test_provider_exit_duplicate_submission_does_not_duplicate_requests_or_outbox(
    client_with_db: AsyncClient,
    db_engine: AsyncEngine,
    admin_secret: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("solver_orchestrator.provider_exit_notifications.utc_now", lambda: NOW)
    user_id, key_id = await _seed_user(db_engine, label="duplicate")
    await _seed_voucher(db_engine, user_id=user_id, api_key_id=key_id)

    first = await client_with_db.post(
        "/v1/admin/provider-exits",
        headers={"X-Admin-Secret": admin_secret},
        json=_payload(),
    )
    second = await client_with_db.post(
        "/v1/admin/provider-exits",
        headers={"X-Admin-Secret": admin_secret},
        json=_payload(),
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["exit_plan_id"] == second.json()["exit_plan_id"]
    assert first.json()["notification_requests_created"] == 1
    assert second.json()["notification_requests_created"] == 0

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        counts = (
            (
                await s.execute(
                    text(
                        """
                    SELECT
                        (SELECT COUNT(*) FROM provider_exit_plans) AS plans,
                        (SELECT COUNT(*) FROM provider_exit_notification_requests) AS requests,
                        (SELECT COUNT(*) FROM provider_exit_status_announcements) AS announcements,
                        (
                            SELECT COUNT(*) FROM outbox
                            WHERE event_type = 'provider.exit.notification_requested'
                        ) AS request_outbox,
                        (
                            SELECT COUNT(*) FROM outbox
                            WHERE event_type = 'provider.exit.status_announcement_requested'
                        ) AS announcement_outbox
                    """
                    )
                )
            )
            .mappings()
            .one()
        )
    assert dict(counts) == {
        "plans": 1,
        "requests": 1,
        "announcements": 1,
        "request_outbox": 1,
        "announcement_outbox": 1,
    }


async def test_provider_exit_with_no_affected_vouchers_creates_status_announcement_only(
    client_with_db: AsyncClient,
    db_engine: AsyncEngine,
    admin_secret: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("solver_orchestrator.provider_exit_notifications.utc_now", lambda: NOW)

    response = await client_with_db.post(
        "/v1/admin/provider-exits",
        headers={"X-Admin-Secret": admin_secret},
        json=_payload(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["affected_users"] == 0
    assert body["affected_vouchers"] == 0
    assert body["notification_requests_created"] == 0

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        counts = (
            (
                await s.execute(
                    text(
                        """
                    SELECT
                        (SELECT COUNT(*) FROM provider_exit_notification_requests) AS requests,
                        (
                            SELECT COUNT(*) FROM outbox
                            WHERE event_type = 'provider.exit.notification_requested'
                        ) AS request_outbox,
                        (
                            SELECT COUNT(*) FROM outbox
                            WHERE event_type = 'provider.exit.status_announcement_requested'
                        ) AS announcement_outbox
                    """
                    )
                )
            )
            .mappings()
            .one()
        )
    assert dict(counts) == {"requests": 0, "request_outbox": 0, "announcement_outbox": 1}
