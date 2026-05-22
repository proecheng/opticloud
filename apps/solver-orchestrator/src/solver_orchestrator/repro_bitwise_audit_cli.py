"""CLI runner for Story 6.B.7 voucher bitwise reproducibility audits."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from solver_orchestrator.config import settings
from solver_orchestrator.repro_bitwise_audit import (
    DEFAULT_EXECUTABLE_COVERAGE_THRESHOLD,
    DEFAULT_PASS_THRESHOLD,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SEED,
    AuditPolicy,
    run_repro_bitwise_audit,
    write_markdown_report,
    write_report,
)

DEFAULT_JSON_REPORT = Path("_bmad-output/reports/repro-bitwise/latest.json")
DEFAULT_MARKDOWN_REPORT = Path("_bmad-output/reports/repro-bitwise/latest.md")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Voucher bitwise reproducibility audit (Story 6.B.7)"
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument(
        "--markdown",
        type=Path,
        nargs="?",
        const=DEFAULT_MARKDOWN_REPORT,
        help="Optional Markdown report path. If passed without a value, uses the default path.",
    )
    parser.add_argument("--sample-rate", type=float, default=DEFAULT_SAMPLE_RATE)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument(
        "--as-of",
        help="UTC timestamp used for eligibility and deterministic sampling",
    )
    parser.add_argument("--pass-threshold", type=float, default=DEFAULT_PASS_THRESHOLD)
    parser.add_argument(
        "--executable-coverage-threshold",
        type=float,
        default=DEFAULT_EXECUTABLE_COVERAGE_THRESHOLD,
    )
    args = parser.parse_args(argv)

    try:
        as_of = _parse_as_of(args.as_of)
        policy = AuditPolicy(
            sample_rate=args.sample_rate,
            seed=args.seed,
            as_of=as_of,
            pass_threshold=args.pass_threshold,
            executable_coverage_threshold=args.executable_coverage_threshold,
        )
    except ValueError as exc:
        sys.stderr.write(f"[repro-bitwise-audit] invalid configuration: {exc}\n")
        return 2

    return asyncio.run(_run(args, policy))


def _parse_as_of(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


async def _run(args: argparse.Namespace, policy: AuditPolicy) -> int:
    engine = create_async_engine(settings.database_url, future=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            report = await run_repro_bitwise_audit(session, policy=policy)
    finally:
        await engine.dispose()

    write_report(args.out, report)
    if args.markdown is not None:
        write_markdown_report(args.markdown, report)

    payload = {
        "event": "repro.bitwise.audit.report",
        "status": report.status,
        "eligible_count": report.eligible_count,
        "sampled_count": report.sampled_count,
        "passed_count": report.passed_count,
        "failed_count": report.failed_count,
        "skipped_count": report.skipped_count,
        "pass_rate": report.pass_rate,
        "executable_coverage": report.executable_coverage,
        "out": str(args.out),
        "markdown": str(args.markdown) if args.markdown is not None else None,
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    sys.stderr.write(
        "[repro-bitwise-audit] "
        f"status={report.status} eligible={report.eligible_count} "
        f"sampled={report.sampled_count} passed={report.passed_count} "
        f"failed={report.failed_count} skipped={report.skipped_count}\n"
    )

    if report.status in ("failed", "insufficient_executable_coverage"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
