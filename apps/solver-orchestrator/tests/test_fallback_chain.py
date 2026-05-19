"""Story 2.5 — FR C5 fallback_chain validation tests."""

from __future__ import annotations

import asyncio
import sys

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from solver_orchestrator.main import app

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


_LP_BODY: dict[str, object] = {
    "task_type": "lp",
    "minimize": {"c": [1.0]},
    "st": {"A": [[1.0]], "b": [1.0]},
}


async def test_demo_lp_with_valid_fallback_chain_succeeds(client: AsyncClient) -> None:
    """AC5 #1 — solver='highs' + fallback_chain=['highs'] → 200."""
    resp = await client.post(
        "/v1/optimizations/demo",
        json={**_LP_BODY, "solver": "highs", "fallback_chain": ["highs"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "completed"


async def test_demo_lp_with_invalid_fallback_element_returns_400(client: AsyncClient) -> None:
    """AC5 #2 — fallback_chain=['highs', 'garbage'] → 400 RFC 7807."""
    resp = await client.post(
        "/v1/optimizations/demo",
        json={**_LP_BODY, "fallback_chain": ["highs", "garbage"]},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["title"] == "Unsupported Fallback Solver"
    assert "[1]" in body["detail"]
    assert "garbage" in body["detail"]
    assert body["errors"][0]["field_path"] == "fallback_chain[1]"


async def test_demo_lp_with_empty_fallback_chain_succeeds(client: AsyncClient) -> None:
    """AC5 #3 — fallback_chain=[] is no-op → 200."""
    resp = await client.post(
        "/v1/optimizations/demo",
        json={**_LP_BODY, "fallback_chain": []},
    )
    assert resp.status_code == 200, resp.text


async def test_demo_lp_with_null_fallback_chain_succeeds(client: AsyncClient) -> None:
    """AC5 #4 — body omits fallback_chain → 200 (existing behavior preserved)."""
    resp = await client.post("/v1/optimizations/demo", json=_LP_BODY)
    assert resp.status_code == 200, resp.text


async def test_demo_lp_fallback_chain_too_long_returns_422(client: AsyncClient) -> None:
    """AC5 #5 — length 4 → 422 (Pydantic length cap, not 400)."""
    resp = await client.post(
        "/v1/optimizations/demo",
        json={**_LP_BODY, "fallback_chain": ["highs", "highs", "highs", "highs"]},
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    # /demo wraps Pydantic ValidationError into "Invalid LP body" 422 with str(e) detail
    assert "fallback_chain" in body["detail"]


async def test_demo_lp_fallback_chain_self_solver_succeeds(client: AsyncClient) -> None:
    """AC5 #6 — solver='highs' + fallback_chain=['highs'] (self-include) → 200."""
    resp = await client.post(
        "/v1/optimizations/demo",
        json={**_LP_BODY, "solver": "highs", "fallback_chain": ["highs"]},
    )
    assert resp.status_code == 200, resp.text


async def test_demo_lp_fallback_first_element_bad_returns_400_index_0(client: AsyncClient) -> None:
    """AC5 #7 — first-failure short-circuit; fallback_chain[0] reported."""
    resp = await client.post(
        "/v1/optimizations/demo",
        json={**_LP_BODY, "fallback_chain": ["garbage", "highs"]},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["title"] == "Unsupported Fallback Solver"
    assert body["errors"][0]["field_path"] == "fallback_chain[0]"


async def test_demo_lp_bad_primary_solver_wins_over_bad_chain(client: AsyncClient) -> None:
    """AC5 #8 — when both solver and chain are bad, primary solver check wins (ordering lock)."""
    resp = await client.post(
        "/v1/optimizations/demo",
        json={**_LP_BODY, "solver": "garbage", "fallback_chain": ["alsobad"]},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["title"] == "Unsupported Solver"  # NOT "Unsupported Fallback Solver"
    assert body["errors"][0]["field_path"] == "solver"
