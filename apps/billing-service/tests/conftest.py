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
