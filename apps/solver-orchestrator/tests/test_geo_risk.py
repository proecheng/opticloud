"""Story 1.11 — API Key geo-anomaly risk scoring tests."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import HTTPException
from solver_orchestrator.auth import verify_api_key
from solver_orchestrator.config import settings
from solver_orchestrator.geo_risk import bucket_for_ip, next_risk_score, normalize_ip
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


def _make_api_key() -> tuple[str, str, int]:
    random_part = uuid.uuid4().hex
    full = f"sk-{random_part}"
    pepper_version = 1
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    key_hash = hmac.new(pepper, full.encode("utf-8"), hashlib.sha256).hexdigest()
    return full, key_hash, pepper_version


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def maker(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    maker_ = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker_() as s:
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
    return maker_


async def _seed_key(
    maker: async_sessionmaker[AsyncSession],
    *,
    revoked: bool = False,
) -> tuple[str, uuid.UUID, uuid.UUID]:
    user_id = uuid.uuid4()
    key_id = uuid.uuid4()
    full, key_hash, version = _make_api_key()
    key_prefix = full[:6]
    now = datetime.now(UTC)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO users(id, email, phone, created_at, updated_at) "
                "VALUES (:id, :email, :phone, :now, :now)"
            ),
            {
                "id": user_id,
                "email": f"geo-{user_id}@example.com",
                "phone": f"+861{user_id.int % 10**10:010d}",
                "now": now,
            },
        )
        await s.execute(
            text(
                "INSERT INTO api_keys(id, user_id, label, key_prefix, key_hash, pepper_version, "
                "scope, created_at, expires_at, revoked_at) VALUES "
                "(:id, :uid, :label, :prefix, :hash, :v, ARRAY['optimize:write'], "
                ":now, :exp, :revoked_at)"
            ),
            {
                "id": key_id,
                "uid": user_id,
                "label": "geo-risk-test",
                "prefix": key_prefix,
                "hash": key_hash,
                "v": version,
                "now": now,
                "exp": now + timedelta(days=365),
                "revoked_at": now if revoked else None,
            },
        )
        await s.commit()
    return f"Bearer {full}", user_id, key_id


async def _key_row(maker: async_sessionmaker[AsyncSession], key_id: uuid.UUID):
    async with maker() as s:
        return (
            await s.execute(
                text(
                    """
                    SELECT host(last_used_ip)::text AS last_used_ip,
                           last_used_geo_bucket, geo_risk_score,
                           geo_anomaly_at, geo_anomaly_metadata
                    FROM api_keys
                    WHERE id = :key_id
                    """
                ),
                {"key_id": key_id},
            )
        ).one()


async def _risk_flag_count(maker: async_sessionmaker[AsyncSession], user_id: uuid.UUID) -> int:
    async with maker() as s:
        return int(
            (
                await s.execute(
                    text(
                        "SELECT COUNT(*) FROM risk_flags "
                        "WHERE user_id = :user_id AND rule_code = 'geo_anomaly'"
                    ),
                    {"user_id": user_id},
                )
            ).scalar_one()
        )


def test_geo_risk_helpers_are_conservative() -> None:
    assert normalize_ip("127.0.0.1") == "127.0.0.1"
    assert bucket_for_ip("127.0.0.1") is None
    assert bucket_for_ip("101.6.6.6") is not None
    assert bucket_for_ip("101.6.6.6").code == "CN-BJ"  # type: ignore[union-attr]
    assert bucket_for_ip("139.59.10.10") is not None
    assert bucket_for_ip("139.59.10.10").code == "SG-SG"  # type: ignore[union-attr]
    assert next_risk_score(Decimal("0.80")) == Decimal("1.00")


async def test_first_known_bucket_use_records_baseline_without_anomaly(
    maker: async_sessionmaker[AsyncSession],
) -> None:
    auth, user_id, key_id = await _seed_key(maker)
    async with maker() as s:
        resolved_user_id, resolved_key_id, scopes = await verify_api_key(
            auth,
            s,
            client_ip="101.6.6.6",
        )
        await s.commit()

    assert resolved_user_id == user_id
    assert resolved_key_id == key_id
    assert scopes == ["optimize:write"]
    row = await _key_row(maker, key_id)
    assert row.last_used_ip == "101.6.6.6"
    assert row.last_used_geo_bucket == "CN-BJ"
    assert row.geo_risk_score == Decimal("0.00")
    assert row.geo_anomaly_at is None
    assert await _risk_flag_count(maker, user_id) == 0


async def test_known_bucket_change_raises_key_and_user_risk_and_records_flag(
    maker: async_sessionmaker[AsyncSession],
) -> None:
    auth, user_id, key_id = await _seed_key(maker)
    async with maker() as s:
        await verify_api_key(auth, s, client_ip="101.6.6.6")
        await s.commit()

    async with maker() as s:
        await verify_api_key(auth, s, client_ip="139.59.10.10")
        await s.commit()

    row = await _key_row(maker, key_id)
    assert row.last_used_ip == "139.59.10.10"
    assert row.last_used_geo_bucket == "SG-SG"
    assert row.geo_risk_score == Decimal("0.35")
    assert row.geo_anomaly_at is not None
    assert row.geo_anomaly_metadata["previous_geo_bucket"] == "CN-BJ"
    assert row.geo_anomaly_metadata["current_geo_bucket"] == "SG-SG"
    assert await _risk_flag_count(maker, user_id) == 1

    async with maker() as s:
        user_score = (
            await s.execute(text("SELECT risk_score FROM users WHERE id = :uid"), {"uid": user_id})
        ).scalar_one()
    assert user_score == Decimal("0.35")


async def test_repeated_same_bucket_use_does_not_add_anomaly_flags(
    maker: async_sessionmaker[AsyncSession],
) -> None:
    auth, user_id, key_id = await _seed_key(maker)
    async with maker() as s:
        await verify_api_key(auth, s, client_ip="101.6.6.6")
        await verify_api_key(auth, s, client_ip="139.59.10.10")
        await verify_api_key(auth, s, client_ip="139.59.11.11")
        await s.commit()

    row = await _key_row(maker, key_id)
    assert row.last_used_geo_bucket == "SG-SG"
    assert row.geo_risk_score == Decimal("0.35")
    assert await _risk_flag_count(maker, user_id) == 1


async def test_revoked_key_does_not_update_last_use_or_risk(
    maker: async_sessionmaker[AsyncSession],
) -> None:
    auth, user_id, key_id = await _seed_key(maker, revoked=True)
    async with maker() as s:
        with pytest.raises(HTTPException) as exc:
            await verify_api_key(auth, s, client_ip="101.6.6.6")
        await s.commit()

    assert exc.value.status_code == 401
    row = await _key_row(maker, key_id)
    assert row.last_used_ip is None
    assert row.last_used_geo_bucket is None
    assert row.geo_risk_score == Decimal("0.00")
    assert row.geo_anomaly_at is None
    assert await _risk_flag_count(maker, user_id) == 0
