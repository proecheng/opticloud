"""Story 2.2 AC7 — GET /v1/algorithms/{k_algo} regression tests.

The route shipped in Story 0.6 (`routes.py:71-84`) without dedicated coverage —
this file closes that gap. No auth, no DB needed; the catalog is in-process.
"""

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


async def test_get_algorithm_returns_full_detail(client: AsyncClient) -> None:
    """AC1 #1 — highs-lp 详情含 examples + provider_url."""
    resp = await client.get("/v1/algorithms/highs-lp")
    assert resp.status_code == 200
    body = resp.json()
    assert body["k_algo"] == "highs-lp"
    assert body["task_type"] == "lp"
    assert body["tier"] == "T1"
    assert body["status"] == "v1"
    assert body["model_version"]["provider_id"] == "highs"
    assert body["model_version"]["provider_url"] == "https://highs.dev/"
    assert len(body["examples"]) >= 1
    assert body["examples"][0]["name"] == "Hello World LP"
    assert body["examples"][0]["input"]["task_type"] == "lp"


async def test_get_algorithm_404_for_unknown_k_algo(client: AsyncClient) -> None:
    """AC1 #2 — 未知 k_algo 返回 404 + detail 含原 k_algo 字符串。

    NB: 现在返回的是 FastAPI 默认 HTTPException 形 `{"detail": "..."}` (FG1.3
    RFC7807 重写见 Story 3.7, DR2). 本测试 lock 当前 shape — 3.7 落地时需同步更新.
    """
    resp = await client.get("/v1/algorithms/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert "does-not-exist" in body["detail"]
    assert "unknown k_algo" in body["detail"]


async def test_get_algorithm_empty_examples_still_200(client: AsyncClient) -> None:
    """AC1 #3 — examples=[] 的 SKU 仍 200 (FE 空态路径回归保护)."""
    resp = await client.get("/v1/algorithms/highs-milp")
    assert resp.status_code == 200
    body = resp.json()
    assert body["k_algo"] == "highs-milp"
    assert body["task_type"] == "milp"
    assert body["examples"] == []
