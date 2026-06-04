"""Story 8.C.8 - algorithm provenance catalog/API tests."""

from __future__ import annotations

import asyncio
import json
import sys

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from solver_orchestrator.catalog import CATALOG, publishable_catalog_items
from solver_orchestrator.main import app

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


ALLOWED_SOURCES = {"catalog_field", "request_schema", "runtime_policy", "documentation"}
PLACEHOLDER_MARKERS = ("TBD", "TODO", "coming soon", "待补充", "unknown", "N/A", "???")
FORBIDDEN_DUPLICATE_KEYS = {
    "bibtex",
    "doi",
    "url",
    "provider_id",
    "provider_url",
    "task_type",
    "tier",
    "status",
    "supported_solvers",
}


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def test_all_catalog_rows_have_complete_provenance_metadata() -> None:
    for algo in CATALOG:
        provenance = algo["provenance"]
        assert provenance["theory_zh"].strip(), algo["k_algo"]
        assert provenance["theory_en"].strip(), algo["k_algo"]
        assert provenance["citation_source"] == "catalog_citation"
        assert len(provenance["configuration_parameters"]) >= 3, algo["k_algo"]
        assert len(provenance["applicable_scenarios_zh"]) >= 3, algo["k_algo"]
        assert len(provenance["limitations_zh"]) >= 2, algo["k_algo"]

        names = [param["name"] for param in provenance["configuration_parameters"]]
        assert len(names) == len(set(names)), algo["k_algo"]
        for param in provenance["configuration_parameters"]:
            assert param["name"].strip(), algo["k_algo"]
            assert param["value_zh"].strip(), algo["k_algo"]
            assert param["description_zh"].strip(), algo["k_algo"]
            assert param["source"] in ALLOWED_SOURCES, algo["k_algo"]


def test_provenance_does_not_duplicate_base_fields_or_citations() -> None:
    for algo in CATALOG:
        raw = json.dumps(algo["provenance"], ensure_ascii=False, sort_keys=True)
        lower = raw.lower()
        for key in FORBIDDEN_DUPLICATE_KEYS:
            assert key not in lower, f"{algo['k_algo']} duplicated {key}"
        assert algo["model_version"]["provider_id"] not in raw
        assert algo["model_version"]["provider_url"] not in raw
        assert algo["model_version"]["version"] not in raw
        assert algo["task_type"] not in raw
        assert algo["tier"] not in raw
        assert algo["status"] not in raw
        for solver in algo["supported_solvers"]:
            assert solver not in raw
        citation = algo.get("citation")
        if citation is not None:
            assert citation["bibtex"] not in raw
            if citation["doi"]:
                assert citation["doi"] not in raw
            if citation["url"]:
                assert citation["url"] not in raw


def test_provenance_has_no_placeholder_markers() -> None:
    for algo in CATALOG:
        raw = json.dumps(algo["provenance"], ensure_ascii=False)
        for marker in PLACEHOLDER_MARKERS:
            assert marker not in raw, f"{algo['k_algo']} contains placeholder {marker}"


async def test_public_algorithm_list_includes_provenance(client: AsyncClient) -> None:
    resp = await client.get("/v1/algorithms")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == len(publishable_catalog_items())
    assert body
    for item in body:
        provenance = item.get("provenance")
        assert provenance is not None, item["k_algo"]
        assert provenance["citation_source"] == "catalog_citation"
        assert len(provenance["configuration_parameters"]) >= 3


async def test_public_algorithm_detail_includes_provenance(client: AsyncClient) -> None:
    resp = await client.get("/v1/algorithms/highs-lp")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    provenance = body["provenance"]
    assert "线性规划" in provenance["theory_zh"]
    assert "Linear programming" in provenance["theory_en"]
    assert {param["source"] for param in provenance["configuration_parameters"]} <= ALLOWED_SOURCES
    assert "bibtex" not in json.dumps(provenance, ensure_ascii=False).lower()


async def test_hidden_self_algorithm_stays_unpublished_despite_internal_provenance(
    client: AsyncClient,
) -> None:
    internal = next(algo for algo in CATALOG if algo["k_algo"] == "aqgs-acopf")
    assert internal["provenance"]["citation_source"] == "catalog_citation"

    resp = await client.get("/v1/algorithms/aqgs-acopf")

    assert resp.status_code == 404, resp.text
    assert "not published" in resp.json()["detail"]
