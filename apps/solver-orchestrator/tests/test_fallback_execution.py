"""Story 2.7 - FR C7 fallback execution tests."""

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
from solver_orchestrator.fallback_execution import (
    FallbackPlanStatus,
    build_fallback_attempts,
    is_retryable_solver_result,
)
from solver_orchestrator.main import app
from solver_orchestrator.provider_routing import select_provider_route
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

_LP_BODY = {
    "task_type": "lp",
    "minimize": {"c": [1.0, 1.0]},
    "st": {"A": [[1.0, 1.0]], "b": [10.0]},
}


def _make_api_key() -> tuple[str, str, int]:
    random_part = f"t27{uuid.uuid4().hex}"
    full = f"sk-{random_part}"
    pepper_version = 1
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    key_hash = hmac.new(pepper, full.encode("utf-8"), hashlib.sha256).hexdigest()
    return full, key_hash, pepper_version


def _result(
    status: str,
    *,
    solve_seconds: float,
    objective: float | None = None,
    solution: dict[str, list[float]] | None = None,
    error_constraint: str | None = None,
) -> solvers.LPSolveResult:
    return solvers.LPSolveResult(
        status=status,
        objective=objective,
        solution=solution,
        solve_seconds=solve_seconds,
        error_field_path="options.max_solve_seconds" if status == "timeout" else "st",
        error_constraint=error_constraint or status,
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
                "email": f"2-7-{user_id}@example.com",
                "phone": f"+861{user_id.int % 10**10:010d}",
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
                "label": "2-7-test",
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


@pytest_asyncio.fixture(loop_scope="session")
async def demo_client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def test_helper_builds_primary_and_repeated_fallback_attempts() -> None:
    primary = select_provider_route("lp", None)

    plan = build_fallback_attempts(
        primary_route=primary,
        task_type="lp",
        requested_solver=None,
        fallback_chain=["highs", "highs"],
    )

    assert plan.status is FallbackPlanStatus.OK
    assert [
        (attempt.attempt, attempt.role, attempt.requested_solver, attempt.route.selected_solver)
        for attempt in plan.attempts
    ] == [
        (1, "primary", None, "highs"),
        (2, "fallback", "highs", "highs"),
        (3, "fallback", "highs", "highs"),
    ]


def test_retry_predicate_only_retries_infrastructure_failures() -> None:
    assert is_retryable_solver_result(_result("timeout", solve_seconds=0.1)) is True
    assert is_retryable_solver_result(_result("error", solve_seconds=0.1)) is True
    assert is_retryable_solver_result(_result("optimal", solve_seconds=0.1)) is False
    assert is_retryable_solver_result(_result("infeasible", solve_seconds=0.1)) is False
    assert is_retryable_solver_result(_result("unbounded", solve_seconds=0.1)) is False


def test_helper_builds_primary_only_for_null_and_empty_chain() -> None:
    primary = select_provider_route("lp", "highs")

    null_plan = build_fallback_attempts(
        primary_route=primary,
        task_type="lp",
        requested_solver="highs",
        fallback_chain=None,
    )
    empty_plan = build_fallback_attempts(
        primary_route=primary,
        task_type="lp",
        requested_solver="highs",
        fallback_chain=[],
    )

    assert [attempt.role for attempt in null_plan.attempts] == ["primary"]
    assert [attempt.role for attempt in empty_plan.attempts] == ["primary"]


async def test_demo_timeout_falls_back_to_success_with_final_repro_lock(
    demo_client: AsyncClient,
    monkeypatch,
) -> None:
    solver_payloads: list[str | None] = []
    results = [
        _result("timeout", solve_seconds=0.125, error_constraint="primary timeout"),
        _result(
            "optimal",
            solve_seconds=0.25,
            objective=10.0,
            solution={"x": [0.0, 10.0]},
        ),
    ]

    def _solve(payload, *, max_solve_seconds=30.0):
        solver_payloads.append(payload.get("solver"))
        return results.pop(0)

    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    resp = await demo_client.post(
        "/v1/optimizations/demo",
        json={
            **_LP_BODY,
            "fallback_chain": ["highs"],
            "options": {"reproducible": True},
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert solver_payloads == ["highs", "highs"]
    assert body["status"] == "completed"
    assert body["solve_seconds"] == pytest.approx(0.375)
    assert body["model_version"]["provider_id"] == "highs"
    assert body["reproducibility"]["locked_solver"] == "highs"
    assert body["reproducibility"]["locked_model_version"] == body["model_version"]


async def test_demo_infeasible_does_not_execute_fallback(
    demo_client: AsyncClient,
    monkeypatch,
) -> None:
    calls = 0

    def _solve(payload, *, max_solve_seconds=30.0):
        nonlocal calls
        calls += 1
        return _result("infeasible", solve_seconds=0.2, error_constraint="LP is infeasible")

    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    resp = await demo_client.post(
        "/v1/optimizations/demo",
        json={**_LP_BODY, "fallback_chain": ["highs"]},
    )

    assert resp.status_code == 422, resp.text
    assert calls == 1


async def test_demo_repeated_timeout_exhausts_attempts(
    demo_client: AsyncClient,
    monkeypatch,
) -> None:
    calls = 0

    def _solve(payload, *, max_solve_seconds=30.0):
        nonlocal calls
        calls += 1
        return _result("timeout", solve_seconds=0.1 * calls, error_constraint=f"timeout {calls}")

    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    resp = await demo_client.post(
        "/v1/optimizations/demo",
        json={**_LP_BODY, "fallback_chain": ["highs", "highs"]},
    )

    assert resp.status_code == 504, resp.text
    assert resp.json()["title"] == "Solver Timeout"
    assert calls == 3


async def test_authenticated_fallback_success_persists_internal_metadata_and_cost(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, _ = api_key
    solver_payloads: list[str | None] = []
    results = [
        _result("timeout", solve_seconds=0.125, error_constraint="primary timeout"),
        _result(
            "optimal",
            solve_seconds=0.25,
            objective=10.0,
            solution={"x": [0.0, 10.0]},
        ),
    ]

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("billing should not run without X-Billing-Charge-Id")

    def _solve(payload, *, max_solve_seconds=30.0):
        solver_payloads.append(payload.get("solver"))
        return results.pop(0)

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    resp = await client_with_db.post(
        "/v1/optimizations",
        json={
            **_LP_BODY,
            "fallback_chain": ["highs"],
            "options": {"reproducible": True},
        },
        headers={"Authorization": auth},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert solver_payloads == ["highs", "highs"]
    assert body["solve_seconds"] == pytest.approx(0.375)
    assert "provider_route" not in body
    assert "executed_provider_route" not in body
    assert "fallback_execution" not in body
    assert body["reproducibility"]["locked_solver"] == "highs"

    opt_id = uuid.UUID(body["optimization_id"])
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        opt_row = (
            (
                await s.execute(
                    text(
                        "SELECT input_payload, model_version, solve_seconds "
                        "FROM optimizations WHERE id = :id"
                    ),
                    {"id": opt_id},
                )
            )
            .mappings()
            .one()
        )
        cost_rows = (
            (
                await s.execute(
                    text(
                        "SELECT value, metadata FROM cost_attribution "
                        "WHERE source_id = :id ORDER BY recorded_at"
                    ),
                    {"id": opt_id},
                )
            )
            .mappings()
            .all()
        )

    system = opt_row["input_payload"]["_system"]
    assert opt_row["input_payload"]["solver"] is None
    assert opt_row["input_payload"]["fallback_chain"] == ["highs"]
    assert system["provider_route"]["selected_solver"] == "highs"
    assert system["executed_provider_route"]["selected_solver"] == "highs"
    fallback_execution = system["fallback_execution"]
    assert fallback_execution["terminal_status"] == "optimal"
    assert fallback_execution["terminal_attempt"] == 2
    assert fallback_execution["exhausted"] is False
    assert [attempt["status"] for attempt in fallback_execution["attempts"]] == [
        "timeout",
        "optimal",
    ]
    assert float(opt_row["solve_seconds"]) == pytest.approx(0.375)
    assert len(cost_rows) == 1
    assert float(cost_rows[0]["value"]) == pytest.approx(0.375)
    assert cost_rows[0]["metadata"]["solver"] == "highs"
    assert cost_rows[0]["metadata"]["status"] == "optimal"
    assert cost_rows[0]["metadata"]["model_provider"] == "highs"


async def test_authenticated_exhausted_timeout_charges_elapsed_and_bounds_metadata(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    charge_id = uuid.uuid4()
    finalize_args: dict[str, object] = {}
    calls = 0

    async def _reserve(*args, **kwargs):
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    async def _finalize(cid, uid, *, elapsed_seconds, status, failure_reason=None, client=None):
        finalize_args.update(
            {
                "cid": cid,
                "uid": uid,
                "elapsed_seconds": elapsed_seconds,
                "status": status,
                "failure_reason": failure_reason,
            }
        )
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    def _solve(payload, *, max_solve_seconds=30.0):
        nonlocal calls
        calls += 1
        return _result(
            "timeout",
            solve_seconds=0.125 * calls,
            error_constraint=f"synthetic timeout {calls}",
        )

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)
    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    resp = await client_with_db.post(
        "/v1/optimizations",
        json={**_LP_BODY, "fallback_chain": ["highs"]},
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )

    assert resp.status_code == 504, resp.text
    assert calls == 2
    assert finalize_args["cid"] == charge_id
    assert finalize_args["uid"] == user_id
    assert finalize_args["status"] == "success"
    assert finalize_args["elapsed_seconds"] == pytest.approx(0.375)
    assert finalize_args["failure_reason"] is None

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (
            (
                await s.execute(
                    text(
                        "SELECT input_payload, error, solve_seconds FROM optimizations "
                        "WHERE user_id = :uid ORDER BY created_at DESC LIMIT 1"
                    ),
                    {"uid": user_id},
                )
            )
            .mappings()
            .one()
        )

    assert float(row["solve_seconds"]) == pytest.approx(0.375)
    assert row["error"]["fallback_execution"]["terminal_status"] == "timeout"
    assert row["error"]["fallback_execution"]["exhausted"] is True
    serialized = str(row["error"]["fallback_execution"])
    assert "sk-" not in serialized
    assert str(charge_id) not in serialized
    assert "Authorization" not in serialized
    assert row["input_payload"]["_system"]["fallback_execution"]["terminal_status"] == "timeout"


async def test_authenticated_terminal_failure_preserves_billing_finalize_failure_flag(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    charge_id = uuid.uuid4()

    async def _reserve(*args, **kwargs):
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    async def _finalize(*args, **kwargs):
        return BillingResult(ok=False, status_code=503, body=None, error_message="HTTP 503")

    def _solve(payload, *, max_solve_seconds=30.0):
        return _result("timeout", solve_seconds=0.25, error_constraint="terminal timeout")

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)
    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    resp = await client_with_db.post(
        "/v1/optimizations",
        json={**_LP_BODY, "fallback_chain": ["highs"]},
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )

    assert resp.status_code == 504, resp.text
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (
            (
                await s.execute(
                    text(
                        "SELECT error FROM optimizations "
                        "WHERE user_id = :uid ORDER BY created_at DESC LIMIT 1"
                    ),
                    {"uid": user_id},
                )
            )
            .mappings()
            .one()
        )

    error = row["error"]
    assert error["billing_finalize_failed"] is True
    assert error["billing_finalize_error"] == "HTTP 503"
    assert error["billing_charge_id"] == str(charge_id)
    assert error["fallback_execution"]["terminal_status"] == "timeout"
