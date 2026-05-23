from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest
from solver_orchestrator.citation_tracker import (
    CitationHit,
    CitationTarget,
    build_linear_issue_payload,
    build_tracking_report,
    create_linear_issues,
    deduplicate_hits,
    extract_citation_targets,
    fetch_semantic_scholar_citations,
    hit_identity,
    load_google_scholar_import,
    load_previous_state,
    render_markdown_report,
    write_state,
)
from solver_orchestrator.citation_tracker_cli import main

NOW = datetime(2026, 5, 20, tzinfo=UTC)


def _target(k_algo: str = "aqgs-acopf", citation_key: str = "aqgs2025opticloud") -> CitationTarget:
    return CitationTarget(
        k_algo=k_algo,
        citation_key=citation_key,
        title="AQGS-ACOPF",
        doi=None,
        url="https://example.test/aqgs",
        source="catalog",
    )


def _hit(
    *,
    source: str = "google_scholar_import",
    k_algo: str = "aqgs-acopf",
    citation_key: str = "aqgs2025opticloud",
    external_id: str = "https://example.test/paper",
    title: str = "A paper citing AQGS",
    url: str | None = "https://example.test/paper",
) -> CitationHit:
    return CitationHit(
        source=source,  # type: ignore[arg-type]
        k_algo=k_algo,
        citation_key=citation_key,
        external_id=external_id,
        title=title,
        url=url,
        year=2026,
        authors=["Li Wei", "Chen Ming"],
        observed_at=NOW,
    )


def test_extract_targets_from_catalog_keeps_duplicate_keys() -> None:
    targets = extract_citation_targets()

    assert len(targets) == 8
    assert "aqgs2025opticloud" in {target.citation_key for target in targets}
    duplicate_targets = [
        target for target in targets if target.citation_key == "huangfu2018parallelizing"
    ]
    assert [target.k_algo for target in duplicate_targets] == ["highs-lp", "highs-milp"]


@pytest.mark.asyncio
async def test_semantic_scholar_fetch_maps_citations_with_mock_transport() -> None:
    target = CitationTarget(
        k_algo="highs-lp",
        citation_key="huangfu2018parallelizing",
        title="Parallelizing the dual revised simplex method",
        doi="10.1007/s12532-017-0130-5",
        url="https://doi.org/10.1007/s12532-017-0130-5",
        source="catalog",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/citations")
        assert request.url.params["fields"] == (
            "citingPaper.paperId,citingPaper.title,citingPaper.url,citingPaper.year,"
            "citingPaper.authors,citingPaper.externalIds"
        )
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "citingPaper": {
                            "paperId": "paper-123",
                            "title": "Fast optimization systems",
                            "url": "https://example.edu/fast-optimization",
                            "year": 2026,
                            "authors": [{"name": "Ada Lovelace"}, {"name": "Grace Hopper"}],
                            "externalIds": {"DOI": "10.9999/example"},
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_semantic_scholar_citations(
            [target],
            client=client,
            observed_at=NOW,
            min_interval_seconds=0,
            api_key="test-s2-key",
        )

    assert result.source_failures == []
    assert result.hits == [
        CitationHit(
            source="semantic_scholar",
            k_algo="highs-lp",
            citation_key="huangfu2018parallelizing",
            external_id="paper-123",
            title="Fast optimization systems",
            url="https://example.edu/fast-optimization",
            year=2026,
            authors=["Ada Lovelace", "Grace Hopper"],
            observed_at=NOW,
        )
    ]


@pytest.mark.asyncio
async def test_semantic_scholar_404_is_not_failure() -> None:
    target = CitationTarget(
        k_algo="highs-lp",
        citation_key="huangfu2018parallelizing",
        title="Parallelizing the dual revised simplex method",
        doi="10.1007/s12532-017-0130-5",
        url=None,
        source="catalog",
    )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(404))
    ) as client:
        result = await fetch_semantic_scholar_citations(
            [target], client=client, observed_at=NOW, min_interval_seconds=0
        )

    assert result.hits == []
    assert result.source_failures == []
    assert result.scan_notes == [
        {"source": "semantic_scholar", "k_algo": "highs-lp", "status": "not_indexed"}
    ]


@pytest.mark.asyncio
async def test_semantic_scholar_429_records_source_failure() -> None:
    target = CitationTarget(
        k_algo="highs-lp",
        citation_key="huangfu2018parallelizing",
        title="Parallelizing the dual revised simplex method",
        doi="10.1007/s12532-017-0130-5",
        url=None,
        source="catalog",
    )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(429, text="slow down"))
    ) as client:
        result = await fetch_semantic_scholar_citations(
            [target], client=client, observed_at=NOW, min_interval_seconds=0
        )

    assert result.hits == []
    assert result.source_failures == [
        {
            "source": "semantic_scholar",
            "k_algo": "highs-lp",
            "status": "http_429",
            "message": "Semantic Scholar returned HTTP 429",
        }
    ]


@pytest.mark.asyncio
async def test_semantic_scholar_invalid_json_records_source_failure() -> None:
    target = CitationTarget(
        k_algo="highs-lp",
        citation_key="huangfu2018parallelizing",
        title="Parallelizing the dual revised simplex method",
        doi="10.1007/s12532-017-0130-5",
        url=None,
        source="catalog",
    )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, text="not-json"))
    ) as client:
        result = await fetch_semantic_scholar_citations(
            [target], client=client, observed_at=NOW, min_interval_seconds=0
        )

    assert result.hits == []
    assert result.source_failures == [
        {
            "source": "semantic_scholar",
            "k_algo": "highs-lp",
            "status": "invalid_json",
            "message": "Semantic Scholar returned invalid JSON",
        }
    ]


def test_google_scholar_csv_import_matches_targets(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import_path = tmp_path / "google.csv"
    import_path.write_text(
        "citation_key,title,url,year,authors\n"
        "huangfu2018parallelizing,Operations paper,https://example.edu/ops,2026,Ada; Grace\n",
        encoding="utf-8",
    )
    targets = [
        _target("highs-lp", "huangfu2018parallelizing"),
        _target("highs-milp", "huangfu2018parallelizing"),
    ]

    result = load_google_scholar_import(import_path, targets, observed_at=NOW)

    assert result.unmatched_imports == []
    assert result.malformed_rows == []
    assert [(hit.k_algo, hit.citation_key, hit.authors) for hit in result.hits] == [
        ("highs-lp", "huangfu2018parallelizing", ["Ada", "Grace"]),
        ("highs-milp", "huangfu2018parallelizing", ["Ada", "Grace"]),
    ]


def test_google_scholar_import_unknown_key_goes_to_unmatched(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import_path = tmp_path / "google.json"
    import_path.write_text(
        json.dumps(
            [
                {
                    "citation_key": "unknown2026paper",
                    "title": "Unknown paper",
                    "url": "https://example.edu/unknown",
                    "authors": ["Ada"],
                }
            ]
        ),
        encoding="utf-8",
    )

    result = load_google_scholar_import(import_path, [_target()], observed_at=NOW)

    assert result.hits == []
    assert result.unmatched_imports == [
        {
            "row_number": "1",
            "citation_key": "unknown2026paper",
            "reason": "unknown_citation_key",
        }
    ]


def test_snapshot_diff_marks_only_new_hits() -> None:
    old_hit = _hit(external_id="old", url="https://example.test/old")
    new_hit = _hit(external_id="new", title="New paper", url="https://example.test/new")
    report = build_tracking_report(
        targets=[_target()],
        hits=[old_hit, new_hit],
        previous_seen_hit_ids={hit_identity(old_hit)},
        generated_at=NOW,
    )

    assert report.hits_total == 2
    assert report.hits_new == 1
    assert report.new_hits == [new_hit]
    assert report.linear_issue_payloads[0]["metadata"]["external_id"] == "new"


def test_snapshot_diff_uses_previous_url_signature_across_sources() -> None:
    previous_google_hit = _hit(
        source="google_scholar_import",
        external_id="https://example.test/paper",
        url="https://example.test/paper",
    )
    current_semantic_hit = _hit(
        source="semantic_scholar",
        external_id="paper-123",
        url="https://example.test/paper/",
    )

    report = build_tracking_report(
        targets=[_target()],
        hits=[current_semantic_hit],
        previous_seen_hit_ids={hit_identity(previous_google_hit)},
        previous_hits=[previous_google_hit],
        generated_at=NOW,
    )

    assert report.hits_total == 1
    assert report.hits_new == 0
    assert report.new_hits == []


def test_dedup_same_url_same_algo_across_sources() -> None:
    semantic_hit = _hit(
        source="semantic_scholar",
        external_id="paper-123",
        url="https://Example.edu/Paper/",
    )
    google_hit = _hit(
        source="google_scholar_import",
        external_id="https://example.edu/Paper",
        url="https://example.edu/Paper",
    )

    assert deduplicate_hits([google_hit, semantic_hit]) == [semantic_hit]


def test_linear_payload_contains_followup_checklist() -> None:
    payload = build_linear_issue_payload(_hit(), _target())

    assert payload["title"] == "[Citation] aqgs-acopf: A paper citing AQGS"
    assert payload["labels"] == ["academic", "citation-tracking", "story-6-a-3"]
    description = str(payload["description"])
    assert "verify paper actually cites OptiCloud/BibTeX entry" in description
    assert "reply/thank author if appropriate" in description
    assert payload["metadata"] == {
        "k_algo": "aqgs-acopf",
        "citation_key": "aqgs2025opticloud",
        "source": "google_scholar_import",
        "external_id": "https://example.test/paper",
    }


def test_markdown_dashboard_contains_new_hits_and_payloads() -> None:
    report = build_tracking_report(
        targets=[_target()],
        hits=[_hit()],
        previous_seen_hit_ids=set(),
        generated_at=NOW,
    )

    markdown = render_markdown_report(report)

    assert "# Citation Tracking Dashboard" in markdown
    assert (
        "| aqgs-acopf | aqgs2025opticloud | A paper citing AQGS | 2026 | google_scholar_import | https://example.test/paper |"
        in markdown
    )
    assert "## Linear Issue Payloads" in markdown
    assert '"citation_key": "aqgs2025opticloud"' in markdown


def test_cli_dry_run_writes_json_and_markdown(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    import_path = tmp_path / "google.csv"
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "latest.json"
    markdown_path = tmp_path / "latest.md"
    import_path.write_text(
        "citation_key,title,url,year,authors\n"
        "aqgs2025opticloud,AQGS adoption study,https://example.edu/aqgs,2026,Li Wei\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--state",
            str(state_path),
            "--out",
            str(report_path),
            "--markdown",
            str(markdown_path),
            "--google-scholar-import",
            str(import_path),
        ]
    )

    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stdout_payload["event"] == "citation.tracker.report"
    assert stdout_payload["hits_new"] == 1
    assert report_payload["hits_new"] == 1
    assert "AQGS adoption study" in markdown_path.read_text(encoding="utf-8")
    assert state_path.exists()


def test_state_write_uses_story_tmp_path_shape(tmp_path) -> None:  # type: ignore[no-untyped-def]
    state_path = tmp_path / "state.json"
    report = build_tracking_report(
        targets=[_target()],
        hits=[_hit()],
        previous_seen_hit_ids=set(),
        generated_at=NOW,
    )

    write_state(state_path, report)
    seen_ids, hits = load_previous_state(state_path)

    assert state_path.exists()
    assert not (tmp_path / "state.json.tmp").exists()
    assert hit_identity(_hit()) in seen_ids
    assert hits == [_hit()]


def test_cli_create_linear_requires_env(tmp_path, capsys, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import solver_orchestrator.config as config

    monkeypatch.setattr(config.settings, "linear_api_key", "")
    monkeypatch.setattr(config.settings, "linear_team_key", "")
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "latest.json"

    exit_code = main(
        [
            "--state",
            str(state_path),
            "--out",
            str(report_path),
            "--create-linear",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "LINEAR_API_KEY and LINEAR_TEAM_KEY are required" in captured.err
    assert "test-linear-key" not in captured.err


def test_cli_create_linear_failure_keeps_reports(tmp_path, capsys, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import solver_orchestrator.citation_tracker_cli as cli
    import solver_orchestrator.config as config

    import_path = tmp_path / "google.csv"
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "latest.json"
    markdown_path = tmp_path / "latest.md"
    import_path.write_text(
        "citation_key,title,url,year,authors\n"
        "aqgs2025opticloud,AQGS adoption study,https://example.edu/aqgs,2026,Li Wei\n",
        encoding="utf-8",
    )

    async def fail_linear(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        raise RuntimeError("Linear issueCreate was not successful")

    monkeypatch.setattr(config.settings, "linear_api_key", "test-linear-key")
    monkeypatch.setattr(config.settings, "linear_team_key", "team-key")
    monkeypatch.setattr(cli, "create_linear_issues", fail_linear)

    exit_code = main(
        [
            "--state",
            str(state_path),
            "--out",
            str(report_path),
            "--markdown",
            str(markdown_path),
            "--google-scholar-import",
            str(import_path),
            "--create-linear",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "test-linear-key" not in captured.err
    assert report_path.exists()
    assert markdown_path.exists()
    assert not state_path.exists()


@pytest.mark.asyncio
async def test_linear_create_success_false_raises() -> None:
    payload = build_linear_issue_payload(_hit(), _target())

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"data": {"issueCreate": {"success": False, "issue": None}}},
            )
        )
    ) as client:
        with pytest.raises(RuntimeError, match="Linear issueCreate was not successful"):
            await create_linear_issues(
                [payload],
                api_key="test-linear-key",
                team_key="team-key",
                client=client,
            )
