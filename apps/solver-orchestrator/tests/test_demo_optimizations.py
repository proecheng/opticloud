"""Story 3.E.3 AC7 — /v1/optimizations/demo unauthenticated tests."""

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


async def test_demo_lp_solves_without_auth(client: AsyncClient) -> None:
    """AC7 #1 — LP via /demo returns 200 + solution without Authorization header."""
    resp = await client.post(
        "/v1/optimizations/demo",
        json={
            "task_type": "lp",
            "minimize": {"c": [1.0, 1.0]},
            "st": {"A": [[1.0, 1.0]], "b": [10.0]},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert "objective" in body
    assert body["demo"] is True
    assert "reproducibility" not in body


async def test_demo_lp_reproducible_returns_locked_context(client: AsyncClient) -> None:
    """Story 6.B.1 — reproducible demo LP returns a downstream handoff envelope."""
    payload = {
        "task_type": "lp",
        "minimize": {"c": [1.0, 1.0]},
        "st": {"A": [[1.0, 1.0]], "b": [10.0]},
        "options": {"reproducible": True},
    }
    resp = await client.post("/v1/optimizations/demo", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    repro = body.get("reproducibility")
    assert repro is not None
    assert repro["requested"] is True
    assert repro["request_fingerprint"].startswith("sha256:")
    assert repro["locked_model_version"] == body["model_version"]
    assert repro["locked_solver"] == "highs"
    assert repro["seed_locked"] is True
    assert repro["seed"] is None
    assert "voucher_id" not in repro


async def test_demo_vrptw_returns_501(client: AsyncClient) -> None:
    """AC7 #2 — VRPTW returns 501 with friendly 'M2-M3' detail."""
    resp = await client.post(
        "/v1/optimizations/demo",
        json={
            "task_type": "vrptw",
            "minimize": {"c": [1.0]},
            "st": {"A": [[1.0]], "b": [1.0]},
        },
    )
    assert resp.status_code == 501
    body = resp.json()
    assert "M2-M3" in body["detail"]
    assert "vrptw" in body["detail"]


async def test_demo_with_invalid_lp_body_returns_422(client: AsyncClient) -> None:
    """AC7 #3 — Pydantic catches malformed bodies → 422."""
    resp = await client.post(
        "/v1/optimizations/demo",
        json={"task_type": "lp"},  # missing required minimize/maximize + st
    )
    assert resp.status_code == 422


async def test_demo_schedule_returns_501(client: AsyncClient) -> None:
    """Story 3.E.4 — schedule body returns 501 with friendly 'M2-M3' detail."""
    resp = await client.post(
        "/v1/optimizations/demo",
        json={
            "task_type": "schedule",
            "tasks": [{"id": "T1", "duration": 4}],
            "resources": [{"id": "R1", "capacity": 1}],
            "precedences": [],
        },
    )
    assert resp.status_code == 501
    body = resp.json()
    assert "M2-M3" in body["detail"]
    assert "schedule" in body["detail"]


async def test_demo_inventory_returns_501(client: AsyncClient) -> None:
    """Story 3.E.5 — inventory body returns 501 with friendly 'M2-M3' detail."""
    resp = await client.post(
        "/v1/optimizations/demo",
        json={
            "task_type": "inventory",
            "skus": [{"sku": "S1"}],
            "history": [{"sku": "S1", "date": "2026-01-01", "qty": 10}],
            "seasonality": [],
        },
    )
    assert resp.status_code == 501
    body = resp.json()
    assert "M2-M3" in body["detail"]
    assert "inventory" in body["detail"]
