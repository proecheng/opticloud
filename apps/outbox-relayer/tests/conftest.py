"""Fixtures for outbox-relayer tests.

Uses real Postgres + real Redis from docker-compose (CI brings them up as
service containers).
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator

import asyncpg
import pytest_asyncio
import redis.asyncio as redis_async
from outbox_relayer.config import settings
from outbox_relayer.db import _asyncpg_dsn

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def pg() -> AsyncIterator[asyncpg.Connection]:
    """One asyncpg connection for the test session."""
    dsn = _asyncpg_dsn(os.getenv("DATABASE_URL", settings.database_url))
    conn = await asyncpg.connect(dsn)
    yield conn
    await conn.close()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def redis_client() -> AsyncIterator[redis_async.Redis]:
    """Shared Redis client for tests."""
    client = redis_async.from_url(os.getenv("REDIS_URL", settings.redis_url), decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_outbox(pg: asyncpg.Connection) -> AsyncIterator[None]:
    """Wipe outbox + ensure clean state between tests."""
    await pg.execute("DELETE FROM outbox")
    yield
    await pg.execute("DELETE FROM outbox")
