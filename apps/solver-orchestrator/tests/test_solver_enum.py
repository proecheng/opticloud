"""Story 2.4 — FR C4 solver enum validation tests."""

from __future__ import annotations

import asyncio
import sys

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from solver_orchestrator.catalog import CATALOG, find_by_task_type_and_solver
from solver_orchestrator.main import app

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ===== /v1/optimizations/demo path (unauthenticated, simpler to test) =====


async def test_demo_lp_with_valid_solver_succeeds(client: AsyncClient) -> None:
    """AC6 #1 — LP with solver='highs' → 200 + solution."""
    resp = await client.post(
        "/v1/optimizations/demo",
        json={
            "task_type": "lp",
            "minimize": {"c": [1.0, 1.0]},
            "st": {"A": [[1.0, 1.0]], "b": [10.0]},
            "solver": "highs",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"


async def test_demo_lp_with_invalid_solver_returns_400(client: AsyncClient) -> None:
    """AC6 #2 — LP with solver='garbage' → 400 RFC 7807."""
    resp = await client.post(
        "/v1/optimizations/demo",
        json={
            "task_type": "lp",
            "minimize": {"c": [1.0]},
            "st": {"A": [[1.0]], "b": [1.0]},
            "solver": "garbage",
        },
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert "highs" in body["detail"]  # supported solvers listed
    assert "garbage" in body["detail"]


async def test_demo_lp_with_null_solver_succeeds(client: AsyncClient) -> None:
    """AC6 #3 — LP without solver field → 200 (default behavior preserved)."""
    resp = await client.post(
        "/v1/optimizations/demo",
        json={
            "task_type": "lp",
            "minimize": {"c": [1.0]},
            "st": {"A": [[1.0]], "b": [1.0]},
        },
    )
    assert resp.status_code == 200, resp.text


# ===== Catalog response shape (no auth needed for /v1/algorithms) =====


async def test_get_algorithms_returns_supported_solvers_field(client: AsyncClient) -> None:
    """AC6 #5 — every catalog entry exposes supported_solvers in the response."""
    resp = await client.get("/v1/algorithms")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) > 0
    for algo in body:
        assert "supported_solvers" in algo
        assert isinstance(algo["supported_solvers"], list)
        assert len(algo["supported_solvers"]) > 0


async def test_get_algorithm_detail_returns_supported_solvers(client: AsyncClient) -> None:
    """AC6 #6 — algorithm detail endpoint exposes supported_solvers."""
    resp = await client.get("/v1/algorithms/highs-lp")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["supported_solvers"] == ["highs"]


# ===== find_by_task_type_and_solver helper unit tests =====


def test_helper_returns_first_algo_when_solver_none() -> None:
    """When solver is None, returns first matching algorithm + union of supported."""
    algo, supported = find_by_task_type_and_solver("lp", None)
    assert algo is not None
    assert algo["k_algo"] == "highs-lp"
    assert "highs" in supported


def test_helper_routes_forecast_to_correct_algo_by_solver() -> None:
    """When 3 algorithms share task_type=forecast, helper routes by solver name.

    This covers the architect-flagged risk: pre-2.4, find_by_task_type returned
    the first match (chronos) regardless of user's solver choice. With 2.4,
    solver='lstm' should resolve to the LSTM algorithm, not chronos.
    """
    forecasters = [a for a in CATALOG if a["task_type"] == "forecast"]
    assert len(forecasters) >= 2  # sanity: arima + chronos + lstm

    arima_algo, _ = find_by_task_type_and_solver("forecast", "arima")
    assert arima_algo is not None
    assert arima_algo["k_algo"] == "arima-forecast"

    lstm_algo, _ = find_by_task_type_and_solver("forecast", "lstm")
    assert lstm_algo is not None
    assert lstm_algo["k_algo"] == "lstm-forecast"

    # Unknown solver but known task_type → None + union list
    bad_algo, union = find_by_task_type_and_solver("forecast", "doesnt-exist")
    assert bad_algo is None
    assert "arima" in union
    assert "lstm" in union
