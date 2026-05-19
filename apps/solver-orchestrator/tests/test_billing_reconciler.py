"""Story M2.2c — billing finalize retry reconciler tests.

Seeds optimizations rows with `error.billing_finalize_failed=true` directly
in the DB (no need to drive through the full HTTP signup→solve→finalize
chain — that's covered by 5.A.4 tests). Mocks billing_client.finalize via
monkeypatch to simulate billing's response.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest_asyncio
from solver_orchestrator import billing_client
from solver_orchestrator.billing_client import BillingResult
from solver_orchestrator.billing_reconciler import retry_pending_finalizes
from solver_orchestrator.config import settings
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
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """Session-scoped async engine for reconciler tests."""
    eng = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Per-test session."""
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s


async def _seed_failed_optimization(
    session: AsyncSession,
    *,
    retry_count: int = 0,
    has_succeeded: bool = False,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """INSERT an optimization row with billing_finalize_failed=true.

    Returns (optimization_id, user_id, billing_charge_id).
    """
    user_id = uuid.uuid4()
    api_key_id = uuid.uuid4()
    billing_charge_id = uuid.uuid4()
    error_blob: dict = {
        "billing_finalize_failed": True,
        "billing_finalize_error": "HTTP 503",
        "billing_charge_id": str(billing_charge_id),
        "billing_elapsed_seconds": 5.0,
        "billing_status": "success",
        "billing_failure_reason": None,
        "billing_retry_count": retry_count,
    }
    if has_succeeded:
        error_blob["billing_finalize_succeeded_at"] = datetime.now(UTC).isoformat()

    # Create user (FK from api_keys → users handled via solver schema; optimizations
    # only references user_id without FK in current schema, but we still create one
    # for cleanliness)
    await session.execute(
        text(
            "INSERT INTO users (id, phone, email, created_at, updated_at) "
            "VALUES (:id, :phone, :email, NOW(), NOW()) ON CONFLICT (id) DO NOTHING"
        ),
        {
            "id": user_id,
            "phone": f"+86r{user_id.hex[:12]}",
            "email": f"recon-{user_id.hex[:10]}@example.com",
        },
    )

    opt_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO optimizations
              (id, user_id, api_key_id, task_type, status, input_payload, error, created_at)
            VALUES
              (:id, :uid, :kid, 'lp', 'completed', CAST('{}' AS jsonb), CAST(:err AS jsonb), NOW())
            """
        ),
        {
            "id": opt_id,
            "uid": user_id,
            "kid": api_key_id,
            "err": json.dumps(error_blob),
        },
    )
    await session.commit()
    return opt_id, user_id, billing_charge_id


async def _fetch_error(session: AsyncSession, opt_id: uuid.UUID) -> dict:  # type: ignore[type-arg]
    row = await session.execute(
        text("SELECT error FROM optimizations WHERE id = :id"), {"id": opt_id}
    )
    return row.scalar_one()


# ===== AC5 tests =====


async def test_retry_no_pending_rows_returns_zero_report(db_session: AsyncSession) -> None:
    """AC5 #1 — empty DB (no flagged rows) → all counts zero."""
    # Drain any pre-existing rows to a high retry count so they're filtered out
    await db_session.execute(
        text(
            "UPDATE optimizations SET error = error || jsonb_build_object('billing_retry_count', 999) "
            "WHERE error ->> 'billing_finalize_failed' = 'true'"
        )
    )
    await db_session.commit()

    report = await retry_pending_finalizes(db_session, max_retries=5)
    assert report.pending_count == 0
    assert report.succeeded_count == 0
    assert report.failed_count == 0
    assert report.exhausted_count == 0


async def test_retry_succeeds_clears_flag(db_session: AsyncSession, monkeypatch) -> None:
    """AC5 #2 — mock billing returns 200; flag cleared + succeeded_at set."""
    opt_id, user_id, charge_id = await _seed_failed_optimization(db_session)

    async def _fake_finalize(*args, **kwargs):
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    monkeypatch.setattr(billing_client, "finalize", _fake_finalize)

    report = await retry_pending_finalizes(db_session, max_retries=5)
    assert report.succeeded_count >= 1
    matches = [r for r in report.results if r.optimization_id == opt_id]
    assert len(matches) == 1
    assert matches[0].succeeded is True

    err_after = await _fetch_error(db_session, opt_id)
    assert "billing_finalize_failed" not in err_after
    assert "billing_finalize_succeeded_at" in err_after


async def test_retry_failure_increments_retry_count(db_session: AsyncSession, monkeypatch) -> None:
    """AC5 #3 — mock billing returns 5xx; retry_count bumped to 1; flag still true."""
    opt_id, _, _ = await _seed_failed_optimization(db_session, retry_count=0)

    async def _fake_finalize(*args, **kwargs):
        return BillingResult(ok=False, status_code=503, body=None, error_message="HTTP 503")

    monkeypatch.setattr(billing_client, "finalize", _fake_finalize)

    report = await retry_pending_finalizes(db_session, max_retries=5)
    matches = [r for r in report.results if r.optimization_id == opt_id]
    assert len(matches) == 1
    assert matches[0].succeeded is False

    err_after = await _fetch_error(db_session, opt_id)
    assert err_after["billing_finalize_failed"] is True
    assert err_after["billing_retry_count"] == 1
    assert err_after["billing_finalize_last_error"] == "HTTP 503"


async def test_retry_exhausted_after_max_attempts(db_session: AsyncSession, monkeypatch) -> None:
    """AC5 #4 — retry_count=4, max=5, one more failure → billing_given_up_at set."""
    opt_id, _, _ = await _seed_failed_optimization(db_session, retry_count=4)

    async def _fake_finalize(*args, **kwargs):
        return BillingResult(ok=False, status_code=500, body=None, error_message="persistent")

    monkeypatch.setattr(billing_client, "finalize", _fake_finalize)

    report = await retry_pending_finalizes(db_session, max_retries=5)
    matches = [r for r in report.results if r.optimization_id == opt_id]
    assert len(matches) == 1
    assert matches[0].succeeded is False
    assert report.exhausted_count >= 1

    err_after = await _fetch_error(db_session, opt_id)
    assert "billing_given_up_at" in err_after


async def test_retry_respects_batch_limit(db_session: AsyncSession, monkeypatch) -> None:
    """AC5 #5 — seed 5 rows; batch_limit=2; only 2 processed in one cycle."""
    opt_ids = []
    for _ in range(5):
        opt_id, _, _ = await _seed_failed_optimization(db_session)
        opt_ids.append(opt_id)

    async def _fake_finalize(*args, **kwargs):
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    monkeypatch.setattr(billing_client, "finalize", _fake_finalize)

    report = await retry_pending_finalizes(db_session, max_retries=5, batch_limit=2)
    assert report.pending_count == 2


async def test_retry_ignores_already_succeeded(db_session: AsyncSession, monkeypatch) -> None:
    """AC5 #6 — row with billing_finalize_succeeded_at already set → not processed."""
    opt_id, _, _ = await _seed_failed_optimization(db_session, has_succeeded=True)

    called = {"count": 0}

    async def _fake_finalize(*args, **kwargs):
        called["count"] += 1
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    monkeypatch.setattr(billing_client, "finalize", _fake_finalize)

    report = await retry_pending_finalizes(db_session, max_retries=5)
    matches = [r for r in report.results if r.optimization_id == opt_id]
    assert matches == []
