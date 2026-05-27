"""Story 3.8 - async cancellation + refund closure tests."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from solver_orchestrator import billing_client
from solver_orchestrator.billing_client import BillingResult
from solver_orchestrator.config import settings
from solver_orchestrator.db import get_session
from solver_orchestrator.main import app
from solver_orchestrator.models import Optimization
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

SMALL_LP_BODY = {
    "task_type": "lp",
    "minimize": {"c": [1.0, 1.0]},
    "st": {"A": [[1.0, 1.0]], "b": [10.0]},
}


def _make_api_key(prefix: str = "t38") -> tuple[str, str, int]:
    random_part = f"{prefix}{uuid.uuid4().hex}"
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


async def _seed_api_key(
    db_engine: AsyncEngine,
    *,
    label: str,
) -> tuple[str, uuid.UUID, uuid.UUID]:
    user_id = uuid.uuid4()
    key_id = uuid.uuid4()
    full, key_hash, version = _make_api_key()
    key_prefix = full[:6]
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO users(id, email, phone, created_at, updated_at) "
                "VALUES (:id, :email, :phone, :now, :now) "
                "ON CONFLICT(id) DO NOTHING"
            ),
            {
                "id": user_id,
                "email": f"3-8-{label}-{user_id}@example.com",
                "phone": f"+865{user_id.int % 10**10:010d}",
                "now": datetime.now(UTC),
            },
        )
        await s.execute(
            text(
                "INSERT INTO api_keys(id, user_id, label, key_prefix, key_hash, pepper_version, "
                "scope, created_at, expires_at) VALUES "
                "(:id, :uid, :label, :prefix, :hash, :v, ARRAY['optimize:write'], :now, :exp)"
            ),
            {
                "id": key_id,
                "uid": user_id,
                "label": f"3-8-{label}",
                "prefix": key_prefix,
                "hash": key_hash,
                "v": version,
                "now": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(days=365),
            },
        )
        await s.commit()
    return f"Bearer {full}", user_id, key_id


@pytest_asyncio.fixture(loop_scope="session")
async def api_key(db_engine: AsyncEngine) -> AsyncIterator[tuple[str, uuid.UUID, uuid.UUID]]:
    yield await _seed_api_key(db_engine, label="primary")


@pytest_asyncio.fixture(loop_scope="session")
async def second_api_key(db_engine: AsyncEngine) -> AsyncIterator[tuple[str, uuid.UUID, uuid.UUID]]:
    yield await _seed_api_key(db_engine, label="secondary")


@pytest_asyncio.fixture(loop_scope="session")
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


async def test_delete_queued_async_without_billing_cancels_no_refund(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, _, _ = api_key

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("billing should not run without async billing metadata")

    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    created = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers={"Authorization": auth},
    )
    assert created.status_code == 202, created.text
    optimization_id = uuid.UUID(created.json()["optimization_id"])

    cancelled = await client_with_db.delete(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": auth},
    )

    assert cancelled.status_code == 200, cancelled.text
    body = cancelled.json()
    assert body["status"] == "cancelled"
    assert body["mode"] == "async"
    assert body["refund_status"] == "not_applicable"
    assert body["message"] == "Optimization cancelled"
    fetched = await client_with_db.get(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": auth},
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["status"] == "cancelled"
    assert fetched.json()["refund_status"] == "not_applicable"
    row = await _optimization_row(db_engine, optimization_id)
    assert row["status"] == "cancelled"
    assert row["solution"] is None
    assert row["objective"] is None
    assert row["completed_at"] is not None


async def test_async_billing_cancel_finalizes_failure_refund_once(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id, _ = api_key
    charge_id = uuid.uuid4()
    reserve_calls: list[tuple[uuid.UUID, uuid.UUID]] = []
    finalize_calls: list[tuple[uuid.UUID, uuid.UUID, float, str, str | None]] = []

    async def _reserve(cid, uid, *, client=None):
        reserve_calls.append((cid, uid))
        return BillingResult(
            ok=True,
            status_code=200,
            body={"current_state": "reserved"},
            error_message=None,
        )

    async def _finalize(cid, uid, *, elapsed_seconds, status, failure_reason=None, client=None):
        finalize_calls.append((cid, uid, elapsed_seconds, status, failure_reason))
        return BillingResult(
            ok=True,
            status_code=200,
            body={"current_state": "refunded"},
            error_message=None,
        )

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)

    created = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )
    assert created.status_code == 202, created.text
    optimization_id = uuid.UUID(created.json()["optimization_id"])

    cancelled = await client_with_db.delete(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": auth},
    )
    repeated = await client_with_db.delete(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": auth},
    )

    assert cancelled.status_code == 200, cancelled.text
    assert repeated.status_code == 200, repeated.text
    assert cancelled.json()["refund_status"] == "refunded"
    assert repeated.json()["refund_status"] == "refunded"
    assert reserve_calls == [(charge_id, user_id)]
    assert finalize_calls == [(charge_id, user_id, 0.0, "failure", "user_cancelled")]
    row = await _optimization_row(db_engine, optimization_id)
    assert row["input_payload"]["_system"]["billing"]["cancel_finalize_attempted"] is True
    assert row["input_payload"]["_system"]["billing"]["refund_status"] == "refunded"
    assert row["error"]["billing_status"] == "failure"
    assert row["error"]["billing_failure_reason"] == "user_cancelled"


async def test_billing_finalize_failure_persists_reconciler_context_and_redacts_response(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, _, _ = api_key
    charge_id = uuid.uuid4()

    async def _reserve(*args, **kwargs):
        return BillingResult(
            ok=True,
            status_code=200,
            body={"current_state": "reserved"},
            error_message=None,
        )

    async def _finalize(*args, **kwargs):
        return BillingResult(ok=False, status_code=503, body=None, error_message="billing down")

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)

    created = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )
    optimization_id = uuid.UUID(created.json()["optimization_id"])

    cancelled = await client_with_db.delete(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": auth},
    )

    assert cancelled.status_code == 200, cancelled.text
    body = cancelled.json()
    assert body["refund_status"] == "pending_reconciliation"
    assert str(charge_id) not in cancelled.text
    assert body["error"]["billing_charge_id"] == "[redacted]"
    row = await _optimization_row(db_engine, optimization_id)
    assert row["status"] == "cancelled"
    assert row["error"]["billing_cancel_finalize_failed"] is True
    assert row["error"]["billing_finalize_failed"] is True
    assert row["error"]["billing_charge_id"] == str(charge_id)
    assert row["error"]["billing_elapsed_seconds"] == 0.0
    assert row["error"]["billing_retry_count"] == 0


async def test_delete_terminal_completed_returns_problem_409_without_billing(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _, _ = api_key

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("billing should not run for terminal cancellation")

    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    completed = await client_with_db.post(
        "/v1/optimizations",
        json=SMALL_LP_BODY,
        headers={"Authorization": auth},
    )
    assert completed.status_code == 200, completed.text
    optimization_id = completed.json()["optimization_id"]

    resp = await client_with_db.delete(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": auth},
    )

    assert resp.status_code == 409, resp.text
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.json()["title"] == "Cancellation Not Allowed"
    assert resp.json()["errors"][0]["remediation_hint_key"] == (
        "errors.409.cancellation_not_allowed"
    )


async def test_cross_tenant_delete_returns_404_without_billing_or_status_leak(
    client_with_db: AsyncClient,
    api_key,
    second_api_key,
    monkeypatch,
) -> None:
    auth, _, _ = api_key
    second_auth, _, _ = second_api_key

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("billing should not run for cross-tenant cancellation")

    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    created = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers={"Authorization": auth},
    )
    optimization_id = created.json()["optimization_id"]

    resp = await client_with_db.delete(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": second_auth},
    )

    assert resp.status_code == 404, resp.text
    assert resp.json()["title"] == "Not Found"
    assert "queued" not in resp.text
    assert "cancelled" not in resp.text


async def test_post_idempotency_replay_after_cancel_returns_200_cancelled(
    client_with_db: AsyncClient,
    api_key,
) -> None:
    auth, _, _ = api_key
    idem_key = f"3-8-cancel-replay-{uuid.uuid4()}"
    headers = {"Authorization": auth, "Idempotency-Key": idem_key}
    created = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers=headers,
    )
    assert created.status_code == 202, created.text
    optimization_id = created.json()["optimization_id"]
    cancelled = await client_with_db.delete(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": auth},
    )
    assert cancelled.status_code == 200, cancelled.text

    replay = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers=headers,
    )

    assert replay.status_code == 200, replay.text
    assert replay.json()["optimization_id"] == optimization_id
    assert replay.json()["status"] == "cancelled"


async def test_async_billing_reserve_failure_rolls_back_optimization_and_idempotency(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id, _ = api_key
    charge_id = uuid.uuid4()
    idem_key = f"3-8-reserve-fail-{uuid.uuid4()}"
    before = await _optimization_count(db_engine, user_id)

    async def _reserve(*args, **kwargs):
        return BillingResult(ok=False, status_code=503, body=None, error_message="reserve down")

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    resp = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers={
            "Authorization": auth,
            "Idempotency-Key": idem_key,
            "X-Billing-Charge-Id": str(charge_id),
        },
    )

    assert resp.status_code == 422, resp.text
    assert resp.json()["title"] == "Billing Reserve Failed"
    assert await _optimization_count(db_engine, user_id) == before
    assert await _idempotency_count(db_engine, user_id, idem_key) == 0


async def test_same_idempotency_key_different_async_charge_id_conflicts(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _, _ = api_key
    idem_key = f"3-8-charge-id-conflict-{uuid.uuid4()}"

    async def _reserve(*args, **kwargs):
        return BillingResult(
            ok=True,
            status_code=200,
            body={"current_state": "reserved"},
            error_message=None,
        )

    monkeypatch.setattr(billing_client, "reserve", _reserve)

    first = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers={
            "Authorization": auth,
            "Idempotency-Key": idem_key,
            "X-Billing-Charge-Id": str(uuid.uuid4()),
        },
    )
    second = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers={
            "Authorization": auth,
            "Idempotency-Key": idem_key,
            "X-Billing-Charge-Id": str(uuid.uuid4()),
        },
    )

    assert first.status_code == 202, first.text
    assert second.status_code == 409, second.text
    assert second.json()["title"] == "Idempotency Conflict"


async def _optimization_count(db_engine: AsyncEngine, user_id: uuid.UUID) -> int:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        return int(
            (
                await s.execute(
                    text("SELECT COUNT(*) FROM optimizations WHERE user_id = :uid"),
                    {"uid": user_id},
                )
            ).scalar_one()
        )


async def _idempotency_count(
    db_engine: AsyncEngine,
    user_id: uuid.UUID,
    idempotency_key: str,
) -> int:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        return int(
            (
                await s.execute(
                    text(
                        "SELECT COUNT(*) FROM idempotency_keys "
                        "WHERE user_id = :uid AND key = :idempotency_key"
                    ),
                    {"uid": user_id, "idempotency_key": idempotency_key},
                )
            ).scalar_one()
        )


async def _optimization_row(db_engine: AsyncEngine, optimization_id: uuid.UUID) -> dict:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = await s.get(Optimization, optimization_id)
        assert row is not None
        return {
            "status": row.status,
            "input_payload": row.input_payload,
            "solution": row.solution,
            "objective": row.objective,
            "error": row.error,
            "completed_at": row.completed_at,
        }
