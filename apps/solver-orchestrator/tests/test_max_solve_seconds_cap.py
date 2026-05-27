"""Story 3.4 - max_solve_seconds cap and timeout best-solution tests."""

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
    "options": {"max_solve_seconds": 1.0},
}


def _make_api_key() -> tuple[str, str, int]:
    random_part = f"t34{uuid.uuid4().hex}"
    full = f"sk-{random_part}"
    pepper_version = 1
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    key_hash = hmac.new(pepper, full.encode("utf-8"), hashlib.sha256).hexdigest()
    return full, key_hash, pepper_version


def _timeout_result(
    *,
    solve_seconds: float = 0.75,
    solution: dict[str, list[float]] | None = None,
    objective: float | None = None,
    error_constraint: str = "solver timed out after 1.0s",
) -> solvers.LPSolveResult:
    return solvers.LPSolveResult(
        status="timeout",
        objective=objective,
        solution=solution,
        solve_seconds=solve_seconds,
        error_field_path="options.max_solve_seconds",
        error_constraint=error_constraint,
    )


def _error_result(*, solve_seconds: float = 0.75) -> solvers.LPSolveResult:
    return solvers.LPSolveResult(
        status="error",
        objective=None,
        solution=None,
        solve_seconds=solve_seconds,
        error_field_path="st",
        error_constraint="synthetic provider error",
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
                "email": f"3-4-{user_id}@example.com",
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
                "label": "3-4-test",
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


def test_timeout_result_from_highs_extracts_finite_best_solution() -> None:
    class _Solution:
        col_value = [3.0, 7.0]

    class _Info:
        objective_function_value = 10.0

    class _FakeHighs:
        def getSolution(self):  # noqa: N802 - mirrors highspy API
            return _Solution()

        def getInfo(self):  # noqa: N802 - mirrors highspy API
            return _Info()

    result = solvers._timeout_result_from_highs(  # noqa: SLF001
        _FakeHighs(),
        num_columns=2,
        elapsed=1.25,
        max_solve_seconds=1.0,
    )

    assert result.status == "timeout"
    assert result.solution == {"x": [3.0, 7.0]}
    assert result.objective == pytest.approx(10.0)
    assert result.error_field_path == "options.max_solve_seconds"


def test_timeout_result_from_highs_omits_unreliable_solution() -> None:
    class _Solution:
        col_value = [float("nan"), 7.0]

    class _FakeHighs:
        def getSolution(self):  # noqa: N802 - mirrors highspy API
            return _Solution()

        def getInfo(self):  # noqa: N802 - mirrors highspy API
            raise RuntimeError("no objective")

    result = solvers._timeout_result_from_highs(  # noqa: SLF001
        _FakeHighs(),
        num_columns=2,
        elapsed=1.25,
        max_solve_seconds=1.0,
    )

    assert result.status == "timeout"
    assert result.solution is None
    assert result.objective is None


async def test_sync_timeout_returns_and_persists_best_solution(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("billing should not run without X-Billing-Charge-Id")

    def _solve(payload, *, max_solve_seconds=30.0):
        assert max_solve_seconds == pytest.approx(1.0)
        return _timeout_result(
            solution={"x": [2.0, 8.0]},
            objective=10.0,
        )

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    resp = await client_with_db.post(
        "/v1/optimizations?mode=sync",
        json=LP_BODY,
        headers={"Authorization": auth},
    )

    assert resp.status_code == 504, resp.text
    body = resp.json()
    assert body["title"] == "Solver Timeout"
    assert body["optimization_status"] == "timeout"
    assert body["best_solution_available"] is True
    assert body["best_solution"] == {"x": [2.0, 8.0]}
    assert body["objective"] == pytest.approx(10.0)
    assert body["solve_seconds"] == pytest.approx(0.75)
    assert body["max_solve_seconds"] == pytest.approx(1.0)
    optimization_id = uuid.UUID(body["optimization_id"])

    row = await _optimization_row(db_engine, optimization_id)
    assert row["status"] == "timeout"
    assert row["solution"] == {"x": [2.0, 8.0]}
    assert float(row["objective"]) == pytest.approx(10.0)
    assert float(row["solve_seconds"]) == pytest.approx(0.75)

    fetched = await client_with_db.get(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": auth},
    )
    assert fetched.status_code == 200, fetched.text
    fetched_body = fetched.json()
    assert fetched_body["status"] == "timeout"
    assert fetched_body["best_solution_available"] is True
    assert fetched_body["best_solution"] == {"x": [2.0, 8.0]}
    assert fetched_body["objective"] == pytest.approx(10.0)
    assert fetched_body["solve_seconds"] == pytest.approx(0.75)

    assert await _voucher_count(db_engine, user_id) == 0


async def test_sync_timeout_without_best_solution_omits_solution(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, _ = api_key

    def _solve(payload, *, max_solve_seconds=30.0):
        return _timeout_result(solution=None, objective=None)

    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    resp = await client_with_db.post(
        "/v1/optimizations?mode=sync",
        json=LP_BODY,
        headers={"Authorization": auth},
    )

    assert resp.status_code == 504, resp.text
    body = resp.json()
    assert body["best_solution_available"] is False
    assert "best_solution" not in body
    assert "objective" not in body
    optimization_id = uuid.UUID(body["optimization_id"])

    row = await _optimization_row(db_engine, optimization_id)
    assert row["solution"] is None
    assert row["objective"] is None


async def test_timeout_with_billing_finalizes_success_for_elapsed_charge(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    charge_id = uuid.uuid4()
    calls: list[tuple[str, dict[str, object]]] = []

    async def _reserve(cid, uid, *, client=None):
        calls.append(("reserve", {"cid": cid, "uid": uid}))
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    async def _finalize(cid, uid, *, elapsed_seconds, status, failure_reason=None, client=None):
        calls.append(
            (
                "finalize",
                {
                    "cid": cid,
                    "uid": uid,
                    "elapsed_seconds": elapsed_seconds,
                    "status": status,
                    "failure_reason": failure_reason,
                },
            )
        )
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    def _solve(payload, *, max_solve_seconds=30.0):
        return _timeout_result(solve_seconds=0.8, solution={"x": [1.0, 9.0]}, objective=10.0)

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)
    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    resp = await client_with_db.post(
        "/v1/optimizations?mode=sync",
        json=LP_BODY,
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )

    assert resp.status_code == 504, resp.text
    assert [call[0] for call in calls] == ["reserve", "finalize"]
    assert calls[0][1]["cid"] == charge_id
    assert calls[0][1]["uid"] == user_id
    assert calls[1][1]["cid"] == charge_id
    assert calls[1][1]["uid"] == user_id
    assert calls[1][1]["elapsed_seconds"] == pytest.approx(0.8)
    assert calls[1][1]["status"] == "success"
    assert calls[1][1]["failure_reason"] is None


async def test_timeout_records_one_cost_attribution_row(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, _ = api_key

    def _solve(payload, *, max_solve_seconds=30.0):
        return _timeout_result(solve_seconds=0.65, solution={"x": [4.0, 6.0]}, objective=10.0)

    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    resp = await client_with_db.post(
        "/v1/optimizations?mode=sync",
        json=LP_BODY,
        headers={"Authorization": auth},
    )

    assert resp.status_code == 504, resp.text
    optimization_id = uuid.UUID(resp.json()["optimization_id"])
    cost_rows = await _cost_rows(db_engine, optimization_id)
    assert len(cost_rows) == 1
    assert float(cost_rows[0]["value"]) == pytest.approx(0.65)
    assert cost_rows[0]["metadata"]["status"] == "timeout"


async def test_fallback_budget_stops_after_cap_without_extra_retry(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _ = api_key
    budgets: list[float] = []

    def _solve(payload, *, max_solve_seconds=30.0):
        budgets.append(max_solve_seconds)
        return _timeout_result(solve_seconds=1.0, error_constraint="cap reached")

    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    resp = await client_with_db.post(
        "/v1/optimizations?mode=sync",
        json={**LP_BODY, "fallback_chain": ["highs", "highs"]},
        headers={"Authorization": auth},
    )

    assert resp.status_code == 504, resp.text
    assert budgets == [pytest.approx(1.0)]
    assert resp.json()["solve_seconds"] == pytest.approx(1.0)


async def test_fallback_later_attempt_receives_remaining_budget(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _ = api_key
    budgets: list[float] = []
    results = [
        _error_result(solve_seconds=0.4),
        _timeout_result(solve_seconds=0.55, error_constraint="remaining cap reached"),
    ]

    def _solve(payload, *, max_solve_seconds=30.0):
        budgets.append(max_solve_seconds)
        return results.pop(0)

    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    resp = await client_with_db.post(
        "/v1/optimizations?mode=sync",
        json={**LP_BODY, "fallback_chain": ["highs"]},
        headers={"Authorization": auth},
    )

    assert resp.status_code == 504, resp.text
    assert budgets[0] == pytest.approx(1.0)
    assert budgets[1] == pytest.approx(0.6)
    assert resp.json()["solve_seconds"] == pytest.approx(0.95)


async def test_timeout_idempotency_replay_returns_status_without_resolve(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _ = api_key
    calls = 0
    idem_key = f"3-4-timeout-replay-{uuid.uuid4()}"

    def _solve(payload, *, max_solve_seconds=30.0):
        nonlocal calls
        calls += 1
        return _timeout_result(solve_seconds=0.7, solution={"x": [5.0, 5.0]}, objective=10.0)

    monkeypatch.setattr(solvers, "solve_from_request", _solve)
    headers = {"Authorization": auth, "Idempotency-Key": idem_key}

    first = await client_with_db.post("/v1/optimizations?mode=sync", json=LP_BODY, headers=headers)
    second = await client_with_db.post("/v1/optimizations?mode=sync", json=LP_BODY, headers=headers)

    assert first.status_code == 504, first.text
    assert second.status_code == 200, second.text
    assert calls == 1
    assert second.json()["status"] == "timeout"
    assert second.json()["best_solution"] == {"x": [5.0, 5.0]}
    assert second.json()["objective"] == pytest.approx(10.0)
    assert second.json()["solve_seconds"] == pytest.approx(0.7)


async def test_async_queued_mode_still_avoids_solver_and_billing(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _ = api_key

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("billing should not run for async queued path")

    def _solver_should_not_run(*args, **kwargs):
        raise AssertionError("solver should not run for async queued path")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", _solver_should_not_run)

    resp = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=LP_BODY,
        headers={"Authorization": auth},
    )

    assert resp.status_code == 202, resp.text
    assert resp.json()["status"] == "queued"


async def _optimization_row(db_engine: AsyncEngine, optimization_id: uuid.UUID) -> dict:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (
            (
                await s.execute(
                    text(
                        "SELECT status, solution, objective, solve_seconds, error "
                        "FROM optimizations WHERE id = :id"
                    ),
                    {"id": optimization_id},
                )
            )
            .mappings()
            .one()
        )
    return dict(row)


async def _cost_rows(db_engine: AsyncEngine, optimization_id: uuid.UUID) -> list[dict]:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        rows = (
            (
                await s.execute(
                    text(
                        "SELECT value, metadata FROM cost_attribution "
                        "WHERE source_id = :id ORDER BY recorded_at"
                    ),
                    {"id": optimization_id},
                )
            )
            .mappings()
            .all()
        )
    return [dict(row) for row in rows]


async def _voucher_count(db_engine: AsyncEngine, user_id: uuid.UUID) -> int:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        return int(
            (
                await s.execute(
                    text("SELECT COUNT(*) FROM reproduction_vouchers WHERE user_id = :user_id"),
                    {"user_id": user_id},
                )
            ).scalar_one()
        )
