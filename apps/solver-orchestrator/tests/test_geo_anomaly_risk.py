"""Story 1.11 — API Key geo anomaly risk scoring tests."""

from __future__ import annotations

import hashlib
import hmac
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

ROOT = Path(__file__).resolve().parents[3]
for path in (
    ROOT / "apps" / "solver-orchestrator" / "src",
    ROOT / "packages" / "shared-py",
):
    sys.path.insert(0, str(path))

from fastapi import HTTPException  # noqa: E402
from solver_orchestrator.auth import verify_api_key  # noqa: E402
from solver_orchestrator.config import settings  # noqa: E402
from solver_orchestrator.geo_risk import assess_geo_anomaly, resolve_coarse_geo  # noqa: E402

DATABASE_URL = os.getenv("DATABASE_URL", settings.database_url)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    yield eng
    await eng.dispose()


def _make_api_key() -> tuple[str, str, int]:
    full = f"sk-{uuid.uuid4().hex}"
    pepper_version = 1
    key_hash = hmac.new(
        settings.api_key_hmac_pepper_dev.encode("utf-8"),
        full.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return full, key_hash, pepper_version


async def _seed_user_key(
    engine: AsyncEngine,
    *,
    last_used_ip: str | None = None,
    revoked: bool = False,
) -> tuple[uuid.UUID, uuid.UUID, str]:
    user_id = uuid.uuid4()
    key_id = uuid.uuid4()
    full_key, key_hash, pepper_version = _make_api_key()
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO users(id, email, phone, age_verified, risk_score, created_at, updated_at) "
                "VALUES (:id, :email, :phone, true, 0.00, :now, :now)"
            ),
            {
                "id": user_id,
                "email": f"geo-{user_id}@example.com",
                "phone": f"+861{user_id.int % 10**10:010d}",
                "now": datetime.now(UTC),
            },
        )
        await s.execute(
            text(
                "INSERT INTO api_keys("
                "id, user_id, label, key_prefix, key_hash, pepper_version, scope, "
                "last_used_ip, revoked_at, created_at, expires_at"
                ") VALUES ("
                ":id, :uid, 'geo-test', :prefix, :hash, :version, "
                "ARRAY['optimize:write'], CAST(:last_ip AS inet), :revoked_at, :now, :expires_at"
                ")"
            ),
            {
                "id": key_id,
                "uid": user_id,
                "prefix": full_key[:6],
                "hash": key_hash,
                "version": pepper_version,
                "last_ip": last_used_ip,
                "revoked_at": datetime.now(UTC) if revoked else None,
                "now": datetime.now(UTC),
                "expires_at": datetime.now(UTC) + timedelta(days=30),
            },
        )
        await s.commit()
    return user_id, key_id, full_key


async def _risk_flags_for_key(engine: AsyncEngine, key_id: uuid.UUID) -> list[dict]:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        rows = (
            await s.execute(
                text(
                    "SELECT metadata FROM risk_flags "
                    "WHERE rule_code = 'geo_anomaly' "
                    "AND metadata->>'api_key_id' = :kid "
                    "ORDER BY created_at DESC"
                ),
                {"kid": str(key_id)},
            )
        ).scalars()
        return list(rows)


def test_coarse_geo_resolver_boundaries() -> None:
    assert resolve_coarse_geo("101.6.10.1") is not None
    assert resolve_coarse_geo("13.250.1.1") is not None
    assert resolve_coarse_geo("10.0.0.1") is None
    assert resolve_coarse_geo("127.0.0.1") is None
    assert resolve_coarse_geo("not-an-ip") is None
    assert resolve_coarse_geo("2001:db8::1") is None
    assert assess_geo_anomaly("101.6.10.1", "101.6.10.9") is None
    assert assess_geo_anomaly("101.6.10.1", "13.250.1.1") is not None


async def test_verify_api_key_records_geo_anomaly_and_monotonic_score(engine: AsyncEngine) -> None:
    user_id, key_id, full_key = await _seed_user_key(engine, last_used_ip="101.6.10.1")
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        returned_user_id, returned_key_id, scopes = await verify_api_key(
            f"Bearer {full_key}",
            s,
            caller_ip="13.250.1.1",
        )
        assert returned_user_id == user_id
        assert returned_key_id == key_id
        assert scopes == ["optimize:write"]
        await s.commit()

    flags = await _risk_flags_for_key(engine, key_id)
    assert len(flags) == 1
    assert flags[0]["previous_geo"]["code"] == "CN-BJ"
    assert flags[0]["current_geo"]["code"] == "SG"
    assert flags[0]["previous_ip"] == "101.6.10.1"
    assert flags[0]["current_ip"] == "13.250.1.1"

    async with maker() as s:
        row = (
            await s.execute(
                text(
                    "SELECT risk_score, host(last_used_ip)::text AS last_used_ip "
                    "FROM users u JOIN api_keys k ON k.user_id = u.id WHERE k.id = :kid"
                ),
                {"kid": key_id},
            )
        ).one()
    assert float(row.risk_score) >= 0.70
    assert row.last_used_ip == "13.250.1.1"


async def test_same_region_and_unknown_ips_do_not_trigger(engine: AsyncEngine) -> None:
    _user_id, key_id, full_key = await _seed_user_key(engine, last_used_ip="101.6.10.1")
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with maker() as s:
        await verify_api_key(f"Bearer {full_key}", s, caller_ip="101.6.99.9")
        await s.commit()
    assert await _risk_flags_for_key(engine, key_id) == []

    async with maker() as s:
        await verify_api_key(f"Bearer {full_key}", s, caller_ip="10.0.0.1")
        await s.commit()
    assert await _risk_flags_for_key(engine, key_id) == []


async def test_first_use_and_revoked_key_do_not_trigger_geo_risk(engine: AsyncEngine) -> None:
    _user_id, key_id, full_key = await _seed_user_key(engine, last_used_ip=None)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await verify_api_key(f"Bearer {full_key}", s, caller_ip="13.250.1.1")
        await s.commit()
    assert await _risk_flags_for_key(engine, key_id) == []

    _revoked_user_id, revoked_key_id, revoked_full_key = await _seed_user_key(
        engine,
        last_used_ip="101.6.10.1",
        revoked=True,
    )
    async with maker() as s:
        with pytest.raises(HTTPException):
            await verify_api_key(f"Bearer {revoked_full_key}", s, caller_ip="13.250.1.1")
        await s.rollback()
    assert await _risk_flags_for_key(engine, revoked_key_id) == []
