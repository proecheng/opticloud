"""Pytest fixtures for auth-service HTTP tests (Story 1.2 +).

Mirrors the billing-service pattern: session-scoped engine + per-test client.
"""

# ruff: noqa: E402

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

APP_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
ROOT_DIR = Path(__file__).resolve().parents[3]
SHARED_PKG_DIR = ROOT_DIR / "packages" / "shared-py"
SOLVER_SRC_DIR = ROOT_DIR / "apps" / "solver-orchestrator" / "src"
for path in (APP_SRC_DIR, SHARED_PKG_DIR, SOLVER_SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from auth_service import security
from auth_service.config import settings
from auth_service.db import get_session
from auth_service.main import app
from httpx import ASGITransport, AsyncClient
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


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def _ensure_jwt_keys(tmp_path_factory) -> AsyncIterator[None]:
    """Generate test JWT keys once per session in a tmp dir."""
    tmpdir = tmp_path_factory.mktemp("auth-jwt-keys")
    key_path = tmpdir / "jwt.key"
    pub_path = tmpdir / "jwt.pub"
    # Reset module-level cache so security.py loads from tmp paths
    security._jwt_private_key = None
    security._jwt_public_key = None
    original_priv = settings.jwt_private_key_path
    original_pub = settings.jwt_public_key_path
    settings.jwt_private_key_path = str(key_path)
    settings.jwt_public_key_path = str(pub_path)
    # Trigger key generation (creates files on first call)
    security._load_jwt_keys()
    yield
    settings.jwt_private_key_path = original_priv
    settings.jwt_public_key_path = original_pub


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def _ensure_account_merge_schema(engine: AsyncEngine) -> None:
    """Local DBs may predate Story 1.7; CI applies updated 01-schema.sql."""
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "ALTER TABLE users "
                "ADD COLUMN IF NOT EXISTS merged_into_user_id UUID NULL REFERENCES users(id) "
                "ON DELETE SET NULL"
            )
        )
        await s.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS merged_at TIMESTAMPTZ NULL")
        )
        await s.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_users_merged_into "
                "ON users(merged_into_user_id) WHERE merged_into_user_id IS NOT NULL"
            )
        )
        await s.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS account_merge_proposals (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    requester_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    primary_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    duplicate_user_ids UUID[] NOT NULL,
                    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
                    status VARCHAR(32) NOT NULL DEFAULT 'pending_review',
                    review_mode VARCHAR(16) NOT NULL,
                    auto_score NUMERIC(4, 2) NULL,
                    review_due_at TIMESTAMPTZ NOT NULL,
                    reviewed_at TIMESTAMPTZ NULL,
                    reviewed_by VARCHAR(255) NULL,
                    decision_reason TEXT NULL,
                    accepted_at TIMESTAMPTZ NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await s.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_account_merge_proposals_requester_created_at "
                "ON account_merge_proposals(requester_user_id, created_at DESC)"
            )
        )
        await s.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_account_merge_proposals_status_due "
                "ON account_merge_proposals(status, review_due_at)"
            )
        )
        await s.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS account_freeze_appeals (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    proposal_id UUID NULL REFERENCES account_merge_proposals(id) ON DELETE SET NULL,
                    tracking_token_hash TEXT NOT NULL UNIQUE,
                    status VARCHAR(32) NOT NULL DEFAULT 'started',
                    contact_email VARCHAR(255) NOT NULL,
                    expires_at TIMESTAMPTZ NOT NULL,
                    last_viewed_at TIMESTAMPTZ NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await s.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_account_freeze_appeals_user_created_at "
                "ON account_freeze_appeals(user_id, created_at DESC)"
            )
        )
        await s.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_account_freeze_appeals_proposal "
                "ON account_freeze_appeals(proposal_id) WHERE proposal_id IS NOT NULL"
            )
        )
        await s.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_account_freeze_appeals_expires_at "
                "ON account_freeze_appeals(expires_at)"
            )
        )
        await s.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS guardian_consent_requests (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    phone VARCHAR(20) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    age_years INTEGER NOT NULL CHECK (age_years BETWEEN 14 AND 17),
                    guardian_email VARCHAR(255) NOT NULL,
                    token_hash TEXT NOT NULL,
                    expires_at TIMESTAMPTZ NOT NULL,
                    confirmed_at TIMESTAMPTZ NULL,
                    user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await s.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_guardian_consent_requests_token_hash "
                "ON guardian_consent_requests(token_hash)"
            )
        )
        await s.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_guardian_consent_requests_pending_contacts "
                "ON guardian_consent_requests(phone, email, guardian_email, expires_at) "
                "WHERE confirmed_at IS NULL"
            )
        )
        await s.execute(
            text(
                "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS last_used_geo_bucket VARCHAR(64) NULL"
            )
        )
        await s.execute(
            text(
                "ALTER TABLE api_keys "
                "ADD COLUMN IF NOT EXISTS geo_risk_score NUMERIC(3, 2) NOT NULL DEFAULT 0.00"
            )
        )
        await s.execute(
            text("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS geo_anomaly_at TIMESTAMPTZ NULL")
        )
        await s.execute(
            text(
                "ALTER TABLE api_keys "
                "ADD COLUMN IF NOT EXISTS geo_anomaly_metadata JSONB NOT NULL DEFAULT '{}'::jsonb"
            )
        )
        await s.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_api_keys_geo_anomaly_user "
                "ON api_keys(user_id, geo_anomaly_at DESC) "
                "WHERE geo_anomaly_at IS NOT NULL"
            )
        )
        await s.execute(
            text(
                """
                INSERT INTO risk_rules (code, label_zh, description, enabled) VALUES
                    (
                        'geo_anomaly',
                        'API Key 异常地理使用',
                        'Story 1.11 — API Key known geo bucket changes unexpectedly; v1 scores and warns only',
                        false
                    )
                ON CONFLICT (code) DO NOTHING
                """
            )
        )
        await s.commit()


@pytest_asyncio.fixture
async def http_client(engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """ASGI test client with DI override for DB session."""
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
