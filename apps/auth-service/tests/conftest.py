"""Pytest fixtures for auth-service HTTP tests (Story 1.2 +).

Mirrors the billing-service pattern: session-scoped engine + per-test client.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

ROOT = Path(__file__).resolve().parents[3]
for path in (
    ROOT / "apps" / "auth-service" / "src",
    ROOT / "apps" / "solver-orchestrator" / "src",
    ROOT / "packages" / "shared-py",
    ROOT / "packages" / "python-sdk" / "src",
):
    sys.path.insert(0, str(path))

from auth_service import security  # noqa: E402
from auth_service.config import settings  # noqa: E402
from auth_service.db import get_session  # noqa: E402
from auth_service.main import app  # noqa: E402

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
