"""Story 3.5 - top_k_alternatives tests."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from solver_orchestrator import billing_client, solvers
from solver_orchestrator.config import settings
from solver_orchestrator.db import get_session
from solver_orchestrator.main import app
from solver_orchestrator.schemas import OptimizationOptions
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
    "maximize": {"c": [1.0, 1.0, 1.0]},
    "st": {"A": [[1.0, 1.0, 1.0]], "b": [10.0]},
}

BOUNDED_MINIMIZE_BODY = {
    "task_type": "lp",
    "minimize": {"c": [1.0, 2.0]},
    "st": {
        "A": [[1.0, 1.0]],
        "b": [5.0],
        "x_lower": [0.0, 0.0],
        "x_upper": [5.0, 5.0],
    },
}


def _make_api_key() -> tuple[str, str, int]:
    random_part = f"t35{uuid.uuid4().hex}"
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
    alternatives: list[dict[str, Any]] | None = None,
    error_constraint: str | None = None,
) -> solvers.LPSolveResult:
    return solvers.LPSolveResult(
        status=status,
        objective=objective,
        solution=solution,
        alternatives=alternatives,
        solve_seconds=solve_seconds,
        error_field_path="options.max_solve_seconds" if status == "timeout" else "st",
        error_constraint=error_constraint or status,
    )


def _three_alternatives() -> list[dict[str, Any]]:
    return [
        {
            "rank": 1,
            "score": 1.0,
            "objective": 10.0,
            "solution": {"x": [10.0, 0.0, 0.0]},
            "source": "primary",
        },
        {
            "rank": 2,
            "score": 1.0,
            "objective": 10.0,
            "solution": {"x": [0.0, 10.0, 0.0]},
            "source": "lp_vertex_enumeration_v1",
        },
        {
            "rank": 3,
            "score": 1.0,
            "objective": 10.0,
            "solution": {"x": [0.0, 0.0, 10.0]},
            "source": "lp_vertex_enumeration_v1",
        },
    ]


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
                "email": f"3-5-{user_id}@example.com",
                "phone": f"+867{user_id.int % 10**10:010d}",
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
                "label": "3-5-test",
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


@pytest_asyncio.fixture
async def demo_client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def test_options_top_k_schema_bounds() -> None:
    assert OptimizationOptions().top_k_alternatives == 1
    assert OptimizationOptions(top_k_alternatives=3).top_k_alternatives == 3
    with pytest.raises(ValidationError):
        OptimizationOptions(top_k_alternatives=0)
    with pytest.raises(ValidationError):
        OptimizationOptions(top_k_alternatives=11)


def test_solve_lp_returns_ranked_feasible_top_three_alternatives() -> None:
    result = solvers.solve_lp(
        c=[1.0, 1.0, 1.0],
        a_constraints=[[1.0, 1.0, 1.0]],
        b_rhs=[10.0],
        sense="maximize",
        top_k_alternatives=3,
    )

    assert result.status == "optimal"
    assert result.alternatives is not None
    assert len(result.alternatives) == 3
    assert result.alternatives[0]["source"] == "primary"
    assert result.alternatives[0]["solution"] == result.solution
    assert result.alternatives[0]["objective"] == pytest.approx(result.objective)
    assert [item["rank"] for item in result.alternatives] == [1, 2, 3]
    assert all(0.0 < item["score"] <= 1.0 for item in result.alternatives)
    seen: set[tuple[float, ...]] = set()
    for item in result.alternatives:
        x = item["solution"]["x"]
        assert len(x) == 3
        assert all(value >= -1e-7 for value in x)
        assert sum(x) <= 10.0 + 1e-7
        key = tuple(round(value, 7) for value in x)
        assert key not in seen
        seen.add(key)


def test_solve_lp_sorts_non_primary_minimize_candidates_by_objective() -> None:
    result = solvers.solve_from_request(
        {**BOUNDED_MINIMIZE_BODY, "options": {"top_k_alternatives": 4}}
    )

    assert result.status == "optimal"
    assert result.alternatives is not None
    assert result.alternatives[0]["solution"] == result.solution
    trailing_objectives = [item["objective"] for item in result.alternatives[1:]]
    assert trailing_objectives == sorted(trailing_objectives)


def test_solve_lp_returns_available_count_without_padding_duplicates() -> None:
    result = solvers.solve_lp(
        c=[1.0],
        a_constraints=[[1.0]],
        b_rhs=[5.0],
        x_lower=[0.0],
        x_upper=[5.0],
        top_k_alternatives=3,
    )

    assert result.status == "optimal"
    assert result.alternatives is not None
    assert len(result.alternatives) == 2
    assert {tuple(item["solution"]["x"]) for item in result.alternatives} == {(0.0,), (5.0,)}


def test_solve_from_request_invalid_top_k_returns_error_result() -> None:
    result = solvers.solve_from_request(
        {**LP_BODY, "options": {"top_k_alternatives": "not-an-int"}}
    )

    assert result.status == "error"
    assert result.error_field_path == "options.top_k_alternatives"


async def test_authenticated_sync_top_k_response_persists_get_and_replays(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, _ = api_key
    calls = 0

    def _solve(payload, *, max_solve_seconds=30.0):
        nonlocal calls
        calls += 1
        assert payload["options"]["top_k_alternatives"] == 3
        return _result(
            "optimal",
            solve_seconds=0.2,
            objective=10.0,
            solution={"x": [10.0, 0.0, 0.0]},
            alternatives=_three_alternatives(),
        )

    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    resp = await client_with_db.post(
        "/v1/optimizations?mode=sync",
        json={**LP_BODY, "options": {"top_k_alternatives": 3}},
        headers={"Authorization": auth, "Idempotency-Key": "story-3-5-top-k"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert calls == 1
    assert body["top_k_alternatives_requested"] == 3
    assert body["top_k_alternatives_returned"] == 3
    assert body["alternatives"] == _three_alternatives()
    assert body["alternatives"][0]["solution"] == body["solution"]
    optimization_id = uuid.UUID(body["optimization_id"])

    row = await _optimization_row(db_engine, optimization_id)
    top_k_metadata = row["input_payload"]["_system"]["top_k_alternatives"]
    assert top_k_metadata["strategy"] == "lp_vertex_enumeration_v1"
    assert top_k_metadata["requested"] == 3
    assert top_k_metadata["returned"] == 3
    assert top_k_metadata["alternatives"] == _three_alternatives()

    fetched = await client_with_db.get(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": auth},
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["alternatives"] == _three_alternatives()

    def _solver_should_not_run(payload, *, max_solve_seconds=30.0):
        raise AssertionError("idempotency replay must not call solver")

    monkeypatch.setattr(solvers, "solve_from_request", _solver_should_not_run)
    replay = await client_with_db.post(
        "/v1/optimizations?mode=sync",
        json={**LP_BODY, "options": {"top_k_alternatives": 3}},
        headers={"Authorization": auth, "Idempotency-Key": "story-3-5-top-k"},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["optimization_id"] == str(optimization_id)
    assert replay.json()["alternatives"] == _three_alternatives()


async def test_default_sync_response_omits_top_k_fields(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _ = api_key

    def _solve(payload, *, max_solve_seconds=30.0):
        return _result(
            "optimal",
            solve_seconds=0.1,
            objective=0.0,
            solution={"x": [0.0, 0.0, 0.0]},
            alternatives=None,
        )

    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    resp = await client_with_db.post(
        "/v1/optimizations?mode=sync",
        json=LP_BODY,
        headers={"Authorization": auth},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "alternatives" not in body
    assert "top_k_alternatives_requested" not in body
    assert "top_k_alternatives_returned" not in body


async def test_fallback_success_returns_terminal_alternatives_and_metadata(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, _ = api_key
    results = [
        _result("timeout", solve_seconds=0.1, error_constraint="primary timeout"),
        _result(
            "optimal",
            solve_seconds=0.2,
            objective=10.0,
            solution={"x": [10.0, 0.0, 0.0]},
            alternatives=_three_alternatives(),
        ),
    ]

    def _solve(payload, *, max_solve_seconds=30.0):
        return results.pop(0)

    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    resp = await client_with_db.post(
        "/v1/optimizations?mode=sync",
        json={**LP_BODY, "options": {"top_k_alternatives": 3}, "fallback_chain": ["highs"]},
        headers={"Authorization": auth},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["alternatives"] == _three_alternatives()
    row = await _optimization_row(db_engine, uuid.UUID(body["optimization_id"]))
    system = row["input_payload"]["_system"]
    assert system["fallback_execution"]["terminal_status"] == "optimal"
    assert system["top_k_alternatives"]["alternatives"] == _three_alternatives()


async def test_demo_top_k_returns_alternatives_without_side_effects(
    demo_client: AsyncClient,
    monkeypatch,
) -> None:
    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("demo must not call billing")

    def _solve(payload, *, max_solve_seconds=30.0):
        assert payload["options"]["top_k_alternatives"] == 3
        return _result(
            "optimal",
            solve_seconds=0.15,
            objective=10.0,
            solution={"x": [10.0, 0.0, 0.0]},
            alternatives=_three_alternatives(),
        )

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    resp = await demo_client.post(
        "/v1/optimizations/demo",
        json={**LP_BODY, "options": {"top_k_alternatives": 3}},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["demo"] is True
    assert body["top_k_alternatives_requested"] == 3
    assert body["alternatives"] == _three_alternatives()


async def test_timeout_and_async_do_not_include_alternatives(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _ = api_key

    def _timeout(payload, *, max_solve_seconds=30.0):
        return _result(
            "timeout",
            solve_seconds=0.5,
            objective=None,
            solution=None,
            alternatives=_three_alternatives(),
            error_constraint="solver timed out after 30.0s",
        )

    monkeypatch.setattr(solvers, "solve_from_request", _timeout)
    timeout_resp = await client_with_db.post(
        "/v1/optimizations?mode=sync",
        json={**LP_BODY, "options": {"top_k_alternatives": 3}},
        headers={"Authorization": auth},
    )
    assert timeout_resp.status_code == 504, timeout_resp.text
    assert "alternatives" not in timeout_resp.json()

    def _solver_should_not_run(payload, *, max_solve_seconds=30.0):
        raise AssertionError("async queued path must not call solver")

    monkeypatch.setattr(solvers, "solve_from_request", _solver_should_not_run)
    async_resp = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json={**LP_BODY, "options": {"top_k_alternatives": 3}},
        headers={"Authorization": auth},
    )
    assert async_resp.status_code == 202, async_resp.text
    async_body = async_resp.json()
    assert async_body["status"] == "queued"
    assert "alternatives" not in async_body


async def _optimization_row(db_engine: AsyncEngine, optimization_id: uuid.UUID) -> dict[str, Any]:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (
            (
                await s.execute(
                    text(
                        "SELECT status, input_payload, solution, objective, solve_seconds, error "
                        "FROM optimizations WHERE id = :id"
                    ),
                    {"id": optimization_id},
                )
            )
            .mappings()
            .one()
        )
    return dict(row)
