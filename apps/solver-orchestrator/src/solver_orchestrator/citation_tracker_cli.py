"""CLI runner for Story 6.A.3 citation tracking."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from solver_orchestrator.citation_tracker import (
    build_tracking_report,
    create_linear_issues,
    extract_citation_targets,
    fetch_semantic_scholar_citations,
    load_google_scholar_import,
    load_previous_state,
    write_markdown_report,
    write_report,
    write_state,
)
from solver_orchestrator.config import settings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OptiCloud citation tracker (Story 6.A.3)")
    parser.add_argument(
        "--state",
        type=Path,
        default=Path(".cache/citation-tracking/state.json"),
        help="Snapshot state JSON path",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("_bmad-output/reports/citation-tracking/latest.json"),
        help="JSON report output path",
    )
    parser.add_argument("--markdown", type=Path, help="Optional Markdown dashboard output path")
    parser.add_argument(
        "--semantic-scholar",
        action="store_true",
        help="Enable Semantic Scholar API lookup; default is off",
    )
    parser.add_argument(
        "--google-scholar-import",
        type=Path,
        action="append",
        default=[],
        help="CSV or JSON Google Scholar-derived import file; can be repeated",
    )
    parser.add_argument(
        "--create-linear",
        action="store_true",
        help="Create Linear issues for new hits; requires env keys",
    )
    args = parser.parse_args(argv)

    if args.create_linear and (not settings.linear_api_key or not settings.linear_team_key):
        sys.stderr.write("LINEAR_API_KEY and LINEAR_TEAM_KEY are required for --create-linear\n")
        return 2

    try:
        return asyncio.run(_run(args))
    except ValueError as exc:
        sys.stderr.write(f"[citation-tracker] invalid configuration: {exc}\n")
        return 2
    except RuntimeError as exc:
        sys.stderr.write(f"[citation-tracker] Linear creation failed: {exc}\n")
        return 2


async def _run(args: argparse.Namespace) -> int:
    generated_at = datetime.now(UTC)
    targets = extract_citation_targets()
    previous_seen_hit_ids, previous_hits = load_previous_state(args.state)

    hits = []
    scan_notes: list[dict[str, str]] = []
    source_failures: list[dict[str, str]] = []
    unmatched_imports: list[dict[str, str]] = []
    malformed_imports: list[dict[str, str]] = []

    if args.semantic_scholar:
        s2_result = await fetch_semantic_scholar_citations(
            targets,
            observed_at=generated_at,
            api_key=settings.semantic_scholar_api_key,
            min_interval_seconds=settings.semantic_scholar_min_interval_seconds,
            timeout_seconds=settings.semantic_scholar_timeout_seconds,
        )
        hits.extend(s2_result.hits)
        scan_notes.extend(s2_result.scan_notes)
        source_failures.extend(s2_result.source_failures)

    for import_path in args.google_scholar_import:
        try:
            parse_result = load_google_scholar_import(
                import_path, targets, observed_at=generated_at
            )
        except (OSError, json.JSONDecodeError) as exc:
            malformed_imports.append(
                {
                    "path": str(import_path),
                    "reason": "unreadable_import",
                    "message": type(exc).__name__,
                }
            )
            continue
        hits.extend(parse_result.hits)
        unmatched_imports.extend(parse_result.unmatched_imports)
        malformed_imports.extend(parse_result.malformed_rows)

    report = build_tracking_report(
        targets=targets,
        hits=hits,
        previous_seen_hit_ids=previous_seen_hit_ids,
        previous_hits=previous_hits,
        generated_at=generated_at,
        scan_notes=scan_notes,
        source_failures=source_failures,
        unmatched_imports=unmatched_imports,
        malformed_imports=malformed_imports,
    )

    write_report(args.out, report)
    if args.markdown is not None:
        write_markdown_report(args.markdown, report)

    if args.create_linear:
        await create_linear_issues(
            report.linear_issue_payloads,
            api_key=settings.linear_api_key,
            team_key=settings.linear_team_key,
        )

    write_state(args.state, report)

    stdout_payload = {
        "event": "citation.tracker.report",
        "targets_scanned": report.targets_scanned,
        "hits_total": report.hits_total,
        "hits_new": report.hits_new,
        "source_failures": len(report.source_failures),
        "malformed_imports": len(report.malformed_imports),
        "out": str(args.out),
        "markdown": str(args.markdown) if args.markdown is not None else None,
        "state": str(args.state),
    }
    sys.stdout.write(json.dumps(stdout_payload, ensure_ascii=False, sort_keys=True) + "\n")
    sys.stderr.write(
        "[citation-tracker] "
        f"targets={report.targets_scanned} hits={report.hits_total} new={report.hits_new} "
        f"failures={len(report.source_failures)} malformed={len(report.malformed_imports)}\n"
    )

    if report.source_failures or report.malformed_imports:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
