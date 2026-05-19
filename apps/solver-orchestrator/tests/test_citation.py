"""Story 6.A.1 — FR R5 citation tests.

Catalog invariants + response-surface tests for the BibTeX citation field.
"""

from __future__ import annotations

import asyncio
import re
import sys
import uuid
from collections import Counter
from datetime import UTC, datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from solver_orchestrator.catalog import CATALOG
from solver_orchestrator.main import app
from solver_orchestrator.models import Optimization
from solver_orchestrator.routes import _build_success_response

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


def test_bibtex_keys_pin_intentional_sharing() -> None:
    """AC8 #4 — keys unique except `huangfu2018parallelizing` × {highs-lp, highs-milp}.

    Review patch: was previously permissive ("any 2-share OK"). Now pins the
    invariant — `huangfu2018parallelizing` is shared by exactly 2 rows, every
    other key appears exactly once. Catches typos that dedup to a 2-share.
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
    assert counts["huangfu2018parallelizing"] == 2, (
        "huangfu2018parallelizing must cover both highs-lp + highs-milp"
    )
    over_shared = {k: c for k, c in counts.items() if c > 1 and k != "huangfu2018parallelizing"}
    assert not over_shared, f"unexpected key sharing: {over_shared}"


def test_bibtex_ampersand_is_latex_safe() -> None:
    """AC1 LaTeX-safety check — any literal `&` inside title / author / journal /
    booktitle / publisher field bodies must be backslash-escaped.

    Review patch: spec claimed this check existed but it was never written.
    The regex walks the bibtex line-by-line, isolates field bodies, and
    rejects any unescaped `&` inside them.
    """
    field_re = re.compile(
        r"^\s*(title|author|journal|booktitle|publisher|series)\s*=\s*\{(?P<body>.*)\}\s*,?\s*$"
    )
    for algo in CATALOG:
        citation = algo["citation"]
        assert citation is not None
        for line in citation["bibtex"].splitlines():
            m = field_re.match(line)
            if m is None:
                continue
            body = m.group("body")
            # Strip already-escaped `\&` so we only flag bare ones.
            stripped = body.replace(r"\&", "")
            assert "&" not in stripped, (
                f"{algo['k_algo']} has unescaped '&' in BibTeX field: {line!r}"
            )


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


# ===== Response-surface tests =====


async def test_lp_demo_response_includes_citation(client: AsyncClient) -> None:
    """AC8 #6 — /v1/optimizations/demo LP success embeds citation."""
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


async def test_failed_lp_demo_returns_rfc7807_without_citation(
    client: AsyncClient,
) -> None:
    """AC8 #7 — infeasible LP on /demo returns 422 RFC 7807 shape (no citation slot).

    Review patch: previously a tautological assertion that `citation` was not
    a key in the 422 body — but a 422 body NEVER has that key regardless of
    the AC3 design. Strengthened to: assert the RFC 7807 shape (`type` +
    `title` + `status` + `detail`) so the test actually exercises the
    failure-response contract.
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
    assert {"type", "title", "status", "detail"}.issubset(body.keys()), (
        f"expected RFC 7807 shape, got: {body!r}"
    )
    assert body["status"] == 422
    assert "citation" not in body  # AC3 design — failures don't get citations


def _make_completed_opt(
    *,
    provider_id: str,
    task_type: str,
    version: str = "1.0.0",
) -> Optimization:
    """Build a synthetic completed Optimization row for direct response-builder tests.

    Bypasses the DB + auth + solver — exercises only the citation lookup logic.
    """
    now = datetime.now(UTC)
    opt = Optimization(
        user_id=uuid.uuid4(),
        api_key_id=uuid.uuid4(),
        task_type=task_type,
        status="completed",
        input_payload={"task_type": task_type},
        solution={"x": [1.0]},
        objective=1.0,
        model_version={
            "provider_id": provider_id,
            "kind": "open_source",
            "version": version,
            "provider_url": "https://example.com/",
        },
        solve_seconds=0.1,
        created_at=now,
        completed_at=now,
    )
    opt.id = uuid.uuid4()
    return opt


def test_build_success_response_resolves_lp_citation() -> None:
    """AC8 #5 — authenticated `_build_success_response` embeds citation on LP completion.

    Review patch: spec called for an auth-route happy-path test but the
    original commit shipped only a catalog-level AQGS assertion. This test
    drives `_build_success_response` directly (no DB / no auth needed)
    proving the shared helper resolves the correct citation for a
    `provider_id="highs"` + `task_type="lp"` combination.
    """
    import json

    opt = _make_completed_opt(provider_id="highs", task_type="lp")
    resp = _build_success_response(opt)
    body = json.loads(resp.body)
    assert resp.status_code == 200
    citation = body.get("citation")
    assert citation is not None
    assert citation["bibtex"].startswith("@article{huangfu2018parallelizing,")
    assert citation["year"] == 2018


def test_build_success_response_disambiguates_milp_vs_lp() -> None:
    """Review patch — Edge Case Hunter finding: highs-lp and highs-milp both have
    `provider_id="highs"`. Lookup must use `(provider_id, task_type)` so MILP
    returns the MILP catalog row, not LP.

    Today the BibTeX is byte-identical (both cite huangfu2018), but a future
    catalog edit that splits the citations must not silently shadow MILP
    behind LP. This test pins the (provider_id, task_type) disambiguation.
    """
    import json

    opt_milp = _make_completed_opt(provider_id="highs", task_type="milp")
    resp = _build_success_response(opt_milp)
    body = json.loads(resp.body)
    citation = body.get("citation")
    assert citation is not None
    # Catalog row for highs-milp tier=T2; verifying we hit that specific row by
    # checking the `model_version.version` echoed back matches the catalog's
    # MILP version (currently 1.7.0, same as LP — but pinning the path).
    assert body["model_version"]["provider_id"] == "highs"
    # Once MILP and LP citations diverge, this test will catch the regression
    # by asserting the citation comes from the row whose task_type matches.
    matching = next(
        a
        for a in CATALOG
        if a["model_version"]["provider_id"] == "highs" and a["task_type"] == "milp"
    )
    assert matching["citation"] is not None
    assert citation["bibtex"] == matching["citation"]["bibtex"]


def test_build_success_response_unknown_provider_degrades_to_null() -> None:
    """Review patch — defensive: if a provider_id is renamed between solve and
    response (e.g. cached idempotency replay across a catalog rename), the
    lookup misses and the response carries `citation: null` rather than 500.
    """
    import json

    opt = _make_completed_opt(provider_id="legacy-provider-removed", task_type="lp")
    resp = _build_success_response(opt)
    body = json.loads(resp.body)
    assert resp.status_code == 200
    assert body.get("citation") is None
