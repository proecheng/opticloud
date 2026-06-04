"""Pytest fixtures for billing-service tests.

Strategy (simplified after asyncio + teardown-order debugging):
- Session-scoped engine + ONE shared test user across the whole test session.
- Per-test fresh session; commits at end-of-test.
- No teardown DELETE — CI databases are ephemeral; uuid4-based saga IDs +
  unique idempotency keys per test avoid collisions.
- Windows: force SelectorEventLoopPolicy for asyncpg compatibility.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from billing_service.config import settings
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


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    """Session-scoped async engine."""
    eng = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_user_id(engine: AsyncEngine) -> uuid.UUID:
    """Single user shared across all tests in the session."""
    user_id = uuid.uuid4()
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as setup_session:
        await setup_session.execute(
            text(
                "INSERT INTO users (id, phone, email, created_at, updated_at) "
                "VALUES (:id, :phone, :email, NOW(), NOW())"
            ),
            {
                "id": user_id,
                "phone": f"+86-test-{user_id.hex[:10]}",
                "email": f"test-{user_id.hex[:10]}@opticloud.test",
            },
        )
        await setup_session.commit()
    return user_id


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _ensure_notification_preferences_schema(engine: AsyncEngine) -> None:
    """Local DBs may predate Story 5.D.6; CI applies 13-notification-preferences.sql."""
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as setup_session:
        await setup_session.execute(
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
        await setup_session.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_notification_preferences_user_event "
                "ON notification_preferences(user_id, event_type)"
            )
        )
        await setup_session.commit()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _ensure_legal_inquiries_schema(engine: AsyncEngine) -> None:
    """Local DBs may predate Story 8.C.3; CI applies 15-legal-inquiries.sql."""
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as setup_session:
        await setup_session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS legal_inquiries (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    subscription_id UUID NULL REFERENCES billing_subscriptions(id) ON DELETE SET NULL,
                    plan_code VARCHAR(32) NOT NULL,
                    category VARCHAR(32) NOT NULL,
                    contact_email VARCHAR(254) NOT NULL,
                    company_name VARCHAR(160) NULL,
                    subject VARCHAR(160) NOT NULL,
                    message TEXT NOT NULL,
                    urgency VARCHAR(16) NOT NULL DEFAULT 'normal',
                    status VARCHAR(32) NOT NULL DEFAULT 'submitted',
                    ticket_key VARCHAR(32) NOT NULL,
                    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    sla_due_at TIMESTAMPTZ NOT NULL,
                    responded_at TIMESTAMPTZ NULL,
                    closed_at TIMESTAMPTZ NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await setup_session.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_legal_inquiries_ticket_key "
                "ON legal_inquiries(ticket_key)"
            )
        )
        await setup_session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_legal_inquiries_user_submitted "
                "ON legal_inquiries(user_id, submitted_at)"
            )
        )
        await setup_session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_legal_inquiries_status_sla "
                "ON legal_inquiries(status, sla_due_at)"
            )
        )
        await setup_session.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conrelid = 'legal_inquiries'::regclass
                          AND conname = 'ck_legal_inquiries_plan_code'
                    ) THEN
                        ALTER TABLE legal_inquiries ADD CONSTRAINT ck_legal_inquiries_plan_code
                            CHECK (plan_code IN ('team', 'enterprise')) NOT VALID;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conrelid = 'legal_inquiries'::regclass
                          AND conname = 'ck_legal_inquiries_category'
                    ) THEN
                        ALTER TABLE legal_inquiries ADD CONSTRAINT ck_legal_inquiries_category
                            CHECK (
                                category IN (
                                    'pipl',
                                    'gdpr',
                                    'graded_protection',
                                    'data_export',
                                    'dpa',
                                    'license',
                                    'security',
                                    'other'
                                )
                            ) NOT VALID;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conrelid = 'legal_inquiries'::regclass
                          AND conname = 'ck_legal_inquiries_urgency'
                    ) THEN
                        ALTER TABLE legal_inquiries ADD CONSTRAINT ck_legal_inquiries_urgency
                            CHECK (urgency IN ('normal', 'urgent')) NOT VALID;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conrelid = 'legal_inquiries'::regclass
                          AND conname = 'ck_legal_inquiries_status'
                    ) THEN
                        ALTER TABLE legal_inquiries ADD CONSTRAINT ck_legal_inquiries_status
                            CHECK (
                                status IN ('submitted', 'triage_pending', 'responded', 'closed')
                            ) NOT VALID;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conrelid = 'legal_inquiries'::regclass
                          AND conname = 'ck_legal_inquiries_contact_email'
                    ) THEN
                        ALTER TABLE legal_inquiries ADD CONSTRAINT ck_legal_inquiries_contact_email
                            CHECK (
                                length(contact_email) BETWEEN 3 AND 254
                                AND position('@' IN contact_email) > 1
                            ) NOT VALID;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conrelid = 'legal_inquiries'::regclass
                          AND conname = 'ck_legal_inquiries_company_name'
                    ) THEN
                        ALTER TABLE legal_inquiries ADD CONSTRAINT ck_legal_inquiries_company_name
                            CHECK (
                                company_name IS NULL
                                OR length(btrim(company_name)) BETWEEN 1 AND 160
                            ) NOT VALID;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conrelid = 'legal_inquiries'::regclass
                          AND conname = 'ck_legal_inquiries_subject'
                    ) THEN
                        ALTER TABLE legal_inquiries ADD CONSTRAINT ck_legal_inquiries_subject
                            CHECK (length(btrim(subject)) BETWEEN 3 AND 160) NOT VALID;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conrelid = 'legal_inquiries'::regclass
                          AND conname = 'ck_legal_inquiries_message'
                    ) THEN
                        ALTER TABLE legal_inquiries ADD CONSTRAINT ck_legal_inquiries_message
                            CHECK (length(btrim(message)) BETWEEN 10 AND 4000) NOT VALID;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conrelid = 'legal_inquiries'::regclass
                          AND conname = 'ck_legal_inquiries_ticket_key'
                    ) THEN
                        ALTER TABLE legal_inquiries ADD CONSTRAINT ck_legal_inquiries_ticket_key
                            CHECK (ticket_key ~ '^OPTI-LEGAL-[0-9]{8}-[A-F0-9]{6}$') NOT VALID;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conrelid = 'legal_inquiries'::regclass
                          AND conname = 'ck_legal_inquiries_sla_due'
                    ) THEN
                        ALTER TABLE legal_inquiries ADD CONSTRAINT ck_legal_inquiries_sla_due
                            CHECK (sla_due_at = submitted_at + INTERVAL '24 hours') NOT VALID;
                    END IF;
                END $$;
                """
            )
        )
        await setup_session.commit()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Per-test session — always commit-or-rollback in finally to release locks."""
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        try:
            yield s
        finally:
            try:
                await s.commit()
            except Exception:
                await s.rollback()
