"""Reconciler CLI — Story 5.A.7.

Usage:
    uv run python -m billing_service.reconciler_cli --window 24h
    uv run python -m billing_service.reconciler_cli --since 2026-05-19T00:00:00Z \\
                                                    --until 2026-05-20T00:00:00Z

Exit codes:
    0 — all OK (no drift above 1 cent)
    1 — at least one MINOR drift detected
    2 — at least one MAJOR drift detected

M3 wraps this in a K8s CronJob / systemd timer / Dramatiq @cron; see RECONCILER.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from billing_service.config import settings
from billing_service.reconciler import DriftSeverity, reconcile_window

_WINDOW_PATTERN = re.compile(r"^(\d+)([hd])$")


def _parse_window(spec: str) -> timedelta:
    """Parse '24h' / '7d' style strings to timedelta."""
    match = _WINDOW_PATTERN.match(spec)
    if match is None:
        raise argparse.ArgumentTypeError(f"--window must match \\d+[hd]; got {spec!r}")
    n, unit = int(match.group(1)), match.group(2)
    return timedelta(hours=n) if unit == "h" else timedelta(days=n)


def _json_default(obj: object) -> object:
    if isinstance(obj, (UUID, Decimal)):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, DriftSeverity):
        return obj.value
    raise TypeError(f"unserializable: {type(obj).__name__}")


async def _run(window_start: datetime, window_end: datetime) -> int:
    """Run reconciliation and emit JSON report. Returns the CLI exit code."""
    engine = create_async_engine(settings.database_url, future=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            report = await reconcile_window(session, window_start, window_end)
    finally:
        await engine.dispose()

    payload = {
        "event": "billing.reconcile.report",
        "window_start": report.window_start.isoformat(),
        "window_end": report.window_end.isoformat(),
        "sagas_examined": report.sagas_examined,
        "diffs_found": report.diffs_found,
        "total_drift_magnitude": str(report.total_drift_magnitude),
        "results": [asdict(r) for r in report.results],
    }
    sys.stdout.write(json.dumps(payload, default=_json_default, ensure_ascii=False) + "\n")

    # Human-readable summary to stderr (cron-wrapper can suppress with `2>/dev/null`)
    sys.stderr.write(
        f"[reconcile] window={report.window_start.isoformat()}..{report.window_end.isoformat()} "
        f"examined={report.sagas_examined} diffs={report.diffs_found} "
        f"magnitude={report.total_drift_magnitude}\n"
    )

    if any(r.severity == DriftSeverity.MAJOR for r in report.results):
        return 2
    if any(r.severity == DriftSeverity.MINOR for r in report.results):
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Billing reconciler — daily drift scan")
    parser.add_argument(
        "--window",
        type=_parse_window,
        default=_parse_window("24h"),
        help="Window size (e.g. 24h, 7d). Ignored if --since/--until given.",
    )
    parser.add_argument(
        "--since",
        type=lambda s: datetime.fromisoformat(s),
        default=None,
        help="ISO 8601 window start. Overrides --window.",
    )
    parser.add_argument(
        "--until",
        type=lambda s: datetime.fromisoformat(s),
        default=None,
        help="ISO 8601 window end. Defaults to now if --since given but --until absent.",
    )
    args = parser.parse_args()

    now = datetime.now(UTC)
    if args.since is not None:
        window_start = args.since
        window_end = args.until or now
    else:
        window_end = now
        window_start = now - args.window

    return asyncio.run(_run(window_start, window_end))


if __name__ == "__main__":
    sys.exit(main())
