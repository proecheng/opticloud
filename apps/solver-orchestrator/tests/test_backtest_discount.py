"""Story 3.10 - backtest 50% billing discount tests."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from solver_orchestrator import billing_client, solvers
from solver_orchestrator.billing_client import BillingResult
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

LP_BODY = {
    "task_type": "lp",
    "minimize": {"c": [1.0, 1.0]},
    "st": {"A": [[1.0, 1.0]], "b": [10.0]},
}


def _make_api_key() -> tuple[str, str, int]:
    random_part = f"t310{uuid.uuid4().hex}"
    full = f"sk-{random_part}"
    pepper_version = 1
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    key_hash = hmac.new(pepper, full.encode("utf-8"), hashlib.sha256).hexdigest()
    return full, key_hash, pepper_version


def _optimal_result(*, solve_seconds: float = 10.0) -> solvers.LPSolveResult:
    return solvers.LPSolveResult(
        status="optimal",
        objective=10.0,
        solution={"x": [0.0, 10.0]},
        solve_seconds=solve_seconds,
    )


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def api_key(db_engine: AsyncEngine) -> AsyncIterator[tuple[str, uuid.UUID]]:
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
                "email": f"3-10-{user_id}@example.com",
                "phone": f"+86310{user_id.int % 10**8:08d}",
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
                "label": "3-10-test",
                "prefix": key_prefix,
                "hash": key_hash,
                "v": version,
                "now": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(days=365),
            },
        )
        await s.commit()

    yield (f"Bearer {full}", user_id)


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


async def test_backtest_option_schema_default_and_true() -> None:
    from solver_orchestrator.schemas import OptimizationOptions

    assert OptimizationOptions().backtest is False
    assert OptimizationOptions(backtest=True).backtest is True


async def test_sync_billing_backtest_passes_discount_and_keeps_true_solve_seconds(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    charge_id = uuid.uuid4()
    finalize_args: dict[str, object] = {}

    async def _reserve(cid, uid, *, client=None):
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    async def _finalize(
        cid,
        uid,
        *,
        elapsed_seconds,
        status,
        failure_reason=None,
        client=None,
        discount_multiplier=None,
    ):
        finalize_args.update(
            {
                "cid": cid,
                "uid": uid,
                "elapsed_seconds": elapsed_seconds,
                "status": status,
                "failure_reason": failure_reason,
                "discount_multiplier": discount_multiplier,
            }
        )
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)
    monkeypatch.setattr(solvers, "solve_from_request", lambda *_args, **_kwargs: _optimal_result())

    resp = await client_with_db.post(
        "/v1/optimizations",
        json={**LP_BODY, "options": {"backtest": True}},
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["solve_seconds"] == pytest.approx(10.0)
    assert finalize_args == {
        "cid": charge_id,
        "uid": user_id,
        "elapsed_seconds": pytest.approx(10.0),
        "status": "success",
        "failure_reason": None,
        "discount_multiplier": pytest.approx(0.5),
    }
    row = await _optimization_row(db_engine, uuid.UUID(body["optimization_id"]))
    assert row["input_payload"]["options"]["backtest"] is True
    assert float(row["solve_seconds"]) == pytest.approx(10.0)
    assert "billing" not in body
    assert "_system" not in resp.text


async def test_sync_billing_non_backtest_keeps_existing_finalize_call_shape(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _ = api_key
    charge_id = uuid.uuid4()
    finalize_seen: dict[str, object] = {}

    async def _reserve(*args, **kwargs):
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    async def _finalize(cid, uid, *, elapsed_seconds, status, failure_reason=None, client=None):
        finalize_seen.update(
            {
                "cid": cid,
                "elapsed_seconds": elapsed_seconds,
                "status": status,
                "failure_reason": failure_reason,
            }
        )
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)
    monkeypatch.setattr(solvers, "solve_from_request", lambda *_args, **_kwargs: _optimal_result())

    resp = await client_with_db.post(
        "/v1/optimizations",
        json=LP_BODY,
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )

    assert resp.status_code == 200, resp.text
    assert finalize_seen["cid"] == charge_id
    assert finalize_seen["elapsed_seconds"] == pytest.approx(10.0)
    assert finalize_seen["status"] == "success"
    assert "discount_multiplier" not in finalize_seen


async def test_backtest_without_billing_header_persists_option_without_billing_calls(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, _ = api_key

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("billing should not run without X-Billing-Charge-Id")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", lambda *_args, **_kwargs: _optimal_result())

    resp = await client_with_db.post(
        "/v1/optimizations",
        json={**LP_BODY, "options": {"backtest": True}},
        headers={"Authorization": auth},
    )

    assert resp.status_code == 200, resp.text
    row = await _optimization_row(db_engine, uuid.UUID(resp.json()["optimization_id"]))
    assert row["input_payload"]["options"]["backtest"] is True


async def test_backtest_finalize_failure_persists_discount_retry_context(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, _ = api_key
    charge_id = uuid.uuid4()

    async def _reserve(*args, **kwargs):
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    async def _finalize(*args, **kwargs):
        return BillingResult(ok=False, status_code=503, body=None, error_message="HTTP 503")

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)
    monkeypatch.setattr(solvers, "solve_from_request", lambda *_args, **_kwargs: _optimal_result())

    resp = await client_with_db.post(
        "/v1/optimizations",
        json={**LP_BODY, "options": {"backtest": True}},
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )

    assert resp.status_code == 200, resp.text
    row = await _optimization_row(db_engine, uuid.UUID(resp.json()["optimization_id"]))
    error = row["error"]
    assert error["billing_finalize_failed"] is True
    assert error["billing_charge_id"] == str(charge_id)
    assert error["billing_elapsed_seconds"] == pytest.approx(10.0)
    assert error["billing_discount_multiplier"] == pytest.approx(0.5)
    assert error["billing_discount_kind"] == "backtest"


async def test_async_backtest_with_billing_reserves_only_and_persists_discount_metadata(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    charge_id = uuid.uuid4()
    reserve_calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def _reserve(cid, uid, *, client=None):
        reserve_calls.append((cid, uid))
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    async def _finalize_should_not_run(*args, **kwargs):
        raise AssertionError("async queued backtest must not finalize")

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize_should_not_run)
    monkeypatch.setattr(
        solvers,
        "solve_from_request",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no solve")),
    )

    resp = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json={**LP_BODY, "options": {"backtest": True}},
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )

    assert resp.status_code == 202, resp.text
    assert reserve_calls == [(charge_id, user_id)]
    row = await _optimization_row(db_engine, uuid.UUID(resp.json()["optimization_id"]))
    billing = row["input_payload"]["_system"]["billing"]
    assert billing["charge_id"] == str(charge_id)
    assert billing["reserved"] is True
    assert billing["discount_kind"] == "backtest"
    assert billing["discount_multiplier"] == pytest.approx(0.5)


async def test_prediction_billing_header_still_rejected_for_story_3_10(
    client_with_db: AsyncClient,
    api_key,
) -> None:
    auth, _ = api_key

    resp = await client_with_db.post(
        "/v1/predictions",
        json={"family": "arima", "data": [1, 2, 3, 4]},
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(uuid.uuid4())},
    )

    assert resp.status_code == 422, resp.text
    assert resp.json()["title"] == "Billing Not Supported For Predictions"


async def test_completed_backtest_idempotency_replay_does_not_bill_twice(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _ = api_key
    idem_key = f"3-10-replay-{uuid.uuid4()}"
    calls = {"reserve": 0, "finalize": 0}

    async def _reserve(*args, **kwargs):
        calls["reserve"] += 1
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    async def _finalize(*args, **kwargs):
        calls["finalize"] += 1
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)
    monkeypatch.setattr(solvers, "solve_from_request", lambda *_args, **_kwargs: _optimal_result())

    headers = {
        "Authorization": auth,
        "Idempotency-Key": idem_key,
        "X-Billing-Charge-Id": str(uuid.uuid4()),
    }
    payload = {**LP_BODY, "options": {"backtest": True}}
    first = await client_with_db.post("/v1/optimizations", json=payload, headers=headers)
    second = await client_with_db.post("/v1/optimizations", json=payload, headers=headers)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["optimization_id"] == first.json()["optimization_id"]
    assert calls == {"reserve": 1, "finalize": 1}


async def test_same_idempotency_key_backtest_true_false_conflicts(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _ = api_key
    idem_key = f"3-10-conflict-{uuid.uuid4()}"

    async def _reserve(*args, **kwargs):
        raise AssertionError("no billing header should avoid reserve")

    async def _finalize(*args, **kwargs):
        raise AssertionError("no billing header should avoid finalize")

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)
    monkeypatch.setattr(solvers, "solve_from_request", lambda *_args, **_kwargs: _optimal_result())

    headers = {"Authorization": auth, "Idempotency-Key": idem_key}
    first = await client_with_db.post(
        "/v1/optimizations",
        json={**LP_BODY, "options": {"backtest": True}},
        headers=headers,
    )
    second = await client_with_db.post(
        "/v1/optimizations",
        json={**LP_BODY, "options": {"backtest": False}},
        headers=headers,
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 409, second.text
    assert second.json()["title"] == "Idempotency Conflict"


async def _optimization_row(db_engine: AsyncEngine, optimization_id: uuid.UUID) -> dict:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (
            (
                await s.execute(
                    text(
                        "SELECT input_payload, solve_seconds, error "
                        "FROM optimizations WHERE id = :id"
                    ),
                    {"id": optimization_id},
                )
            )
            .mappings()
            .one()
        )
    return dict(row)
