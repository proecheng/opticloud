"""Story 6.A.1 — FR R5 citation tests.

Catalog invariants + response-surface tests for the BibTeX citation field.
"""

from __future__ import annotations

import asyncio
import re
import sys
from collections import Counter

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from solver_orchestrator.catalog import CATALOG
from solver_orchestrator.main import app

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ===== Catalog invariants (sync, no fixtures needed) =====


def test_all_catalog_rows_have_citation() -> None:
    """AC8 #1 — v1 invariant: every catalog row has a populated citation."""
    for algo in CATALOG:
        assert algo.get("citation") is not None, (
            f"{algo['k_algo']} missing citation — all v1 rows must have one"
        )


def test_bibtex_strings_have_valid_entry_signature() -> None:
    """AC8 #2 — every bibtex starts with @entrytype{key,."""
    sig = re.compile(r"^@(article|software|inproceedings|book|misc)\{[A-Za-z0-9_]+,")
    for algo in CATALOG:
        citation = algo["citation"]
        assert citation is not None
        assert sig.match(citation["bibtex"]), (
            f"{algo['k_algo']} bibtex has bad signature: {citation['bibtex'][:80]!r}"
        )


def test_bibtex_strings_balance_braces() -> None:
    """AC8 #3 — { count equals } count in every bibtex entry."""
    for algo in CATALOG:
        citation = algo["citation"]
        assert citation is not None
        bibtex = citation["bibtex"]
        open_count = bibtex.count("{")
        close_count = bibtex.count("}")
        assert open_count == close_count, (
            f"{algo['k_algo']} unbalanced braces: {open_count} '{{' vs {close_count} '}}'"
        )


def test_bibtex_keys_appear_at_most_in_shared_papers() -> None:
    """AC8 #4 — keys unique except deliberately shared (huangfu2018 covers LP+MILP).

    Use Counter not set: the table-driven design intentionally shares 1 key across
    2 algorithms (highs-lp + highs-milp both derive from huangfu2018parallelizing).
    Anything sharing more than that is a typo.
    """
    key_re = re.compile(r"^@\w+\{([A-Za-z0-9_]+),")
    keys: list[str] = []
    for algo in CATALOG:
        citation = algo["citation"]
        assert citation is not None
        m = key_re.match(citation["bibtex"])
        assert m, f"{algo['k_algo']} bibtex key not parsable"
        keys.append(m.group(1))
    counts = Counter(keys)
    # Allow up to 2 algorithms to share a key (the highs-lp / highs-milp case).
    over_shared = {k: c for k, c in counts.items() if c > 2}
    assert not over_shared, f"citation keys over-shared (>2 algos): {over_shared}"


def test_aqgs_self_developed_uses_software_entry() -> None:
    """AC1 — the AQGS-ACOPF self-developed algorithm uses @software entry type.

    This is the Innovation #3 anchor citation; protect its shape.
    """
    aqgs = next(a for a in CATALOG if a["k_algo"] == "aqgs-acopf")
    citation = aqgs["citation"]
    assert citation is not None
    assert citation["bibtex"].startswith("@software{aqgs2025opticloud,"), (
        "AQGS citation must be @software (FORCE11 software-citation guideline)"
    )
    assert "Apache-2.0" in citation["bibtex"]
    assert citation["year"] == 2025
    assert citation["doi"] is None
    assert citation["url"] == "https://github.com/opticloud/aqgs"


# ===== Response-surface tests (async, ASGI client) =====


async def test_lp_demo_response_includes_citation(client: AsyncClient) -> None:
    """AC8 #6 — /v1/optimizations/demo LP success embeds citation.

    Uses /demo because it bypasses auth + DB; same citation-lookup path as
    authenticated route.
    """
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
    citation = body.get("citation")
    assert citation is not None, "LP demo response must include citation (FR R5)"
    assert citation["bibtex"].startswith("@article{huangfu2018parallelizing,"), (
        f"unexpected citation key: {citation['bibtex'][:60]!r}"
    )
    assert citation["authors_label_zh"] == "Huangfu & Hall (2018)"
    assert citation["year"] == 2018
    assert citation["doi"] == "10.1007/s12532-017-0130-5"


async def test_failed_lp_demo_does_not_include_citation(client: AsyncClient) -> None:
    """AC8 #7 — infeasible LP on /demo returns 422 without citation field.

    Citations only ship on completed responses; failures don't get them.
    """
    resp = await client.post(
        "/v1/optimizations/demo",
        json={
            "task_type": "lp",
            "minimize": {"c": [1.0]},
            "st": {"A": [[1.0]], "b": [-1.0]},  # x ≥ 0 ∧ x ≤ -1 → infeasible
        },
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "citation" not in body, "failed responses must NOT include citation (AC3 design)"
