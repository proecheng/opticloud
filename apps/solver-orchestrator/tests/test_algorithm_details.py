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


# ===== Story 2.3 — list filter by ?tier= (FR C3) =====


async def test_list_filters_by_single_tier(client: AsyncClient) -> None:
    """Story 2.3 AC2 #1 — `?tier=T1` 仅返回 T1 SKU."""
    resp = await client.get("/v1/algorithms?tier=T1")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["k_algo"] == "highs-lp"
    assert body[0]["tier"] == "T1"


async def test_list_filters_by_comma_separated_tiers(client: AsyncClient) -> None:
    """Story 2.3 AC2 #2 — `?tier=T1,P1` 返回 2 个 SKU (OR 语义)."""
    resp = await client.get("/v1/algorithms?tier=T1,P1")
    assert resp.status_code == 200
    body = resp.json()
    k_algos = {b["k_algo"] for b in body}
    assert k_algos == {"highs-lp", "arima-forecast"}


async def test_list_unknown_tier_returns_empty_list(client: AsyncClient) -> None:
    """Story 2.3 AC2 #3 — 未知 tier 返回 [] + 200 (permissive 语义, 不抛 422)."""
    resp = await client.get("/v1/algorithms?tier=T9")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_combines_task_type_and_tier(client: AsyncClient) -> None:
    """Story 2.3 AC2 #4 — task_type + tier AND 组合."""
    resp = await client.get("/v1/algorithms?task_type=forecast&tier=P1")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["k_algo"] == "arima-forecast"


async def test_list_with_empty_tier_param_returns_all(client: AsyncClient) -> None:
    """Story 2.3 AC2 #5 — 空 tier 参数 (?tier=) 等价于无 filter."""
    resp = await client.get("/v1/algorithms?tier=")
    assert resp.status_code == 200
    body = resp.json()
    # Catalog currently has 8 SKUs (see catalog.py); use >= 1 to stay resilient
    # if catalog grows during M2.
    assert len(body) >= 8


async def test_algorithm_detail_includes_citation(client: AsyncClient) -> None:
    """Story 6.A.1 AC8 #8 — GET /v1/algorithms/{k_algo} returns citation."""
    resp = await client.get("/v1/algorithms/highs-lp")
    assert resp.status_code == 200
    body = resp.json()
    citation = body.get("citation")
    assert citation is not None
    assert citation["bibtex"].startswith("@article{huangfu2018parallelizing,")
    assert citation["year"] == 2018
    assert citation["doi"] == "10.1007/s12532-017-0130-5"
    assert citation["authors_label_zh"] == "Huangfu & Hall (2018)"


async def test_algorithm_list_includes_citation_for_every_row(client: AsyncClient) -> None:
    """Story 6.A.1 AC8 #9 — every list row has citation populated."""
    resp = await client.get("/v1/algorithms")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 8
    for item in body:
        assert item.get("citation") is not None, (
            f"{item['k_algo']} missing citation in list response"
        )
    # at least one recent paper (Chronos / OR-Tools 2024)
    assert any(item["citation"]["year"] >= 2024 for item in body)


async def test_algorithm_detail_includes_ip_attribution(client: AsyncClient) -> None:
    """Story 6.A.5 — GET /v1/algorithms/{k_algo} returns IP attribution metadata."""
    resp = await client.get("/v1/algorithms/aqgs-acopf")
    assert resp.status_code == 200
    body = resp.json()
    attribution = body.get("ip_attribution")
    assert attribution is not None
    assert attribution["tier"] == "L1"
    assert attribution["visibility"] == "full_visible"
    assert "OptiCloud / Trust-Tech" in attribution["display_name_zh"]
    assert "docs/legal-templates.md" in attribution["contract_anchor"]


async def test_algorithm_list_includes_ip_attribution_for_every_row(
    client: AsyncClient,
) -> None:
    """Story 6.A.5 — every catalog row has non-null IP attribution metadata."""
    resp = await client.get("/v1/algorithms")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 8
    for item in body:
        attribution = item.get("ip_attribution")
        assert attribution is not None, f"{item['k_algo']} missing ip_attribution in list response"
        assert attribution["tier"] in {"L1", "L2", "L3"}
        assert attribution["visibility"] in {"full_visible", "bibtex", "license_only"}

    highs_lp = next(item for item in body if item["k_algo"] == "highs-lp")
    assert highs_lp["ip_attribution"]["tier"] == "L3"
    assert highs_lp["ip_attribution"]["visibility"] == "license_only"
