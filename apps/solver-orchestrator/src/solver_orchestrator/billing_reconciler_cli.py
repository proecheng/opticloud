"""Billing reconciler CLI — Story M2.2c.

Usage:
    uv run python -m solver_orchestrator.billing_reconciler_cli
    uv run python -m solver_orchestrator.billing_reconciler_cli --max-retries 3 --batch-limit 50

Exit codes:
    0 — pending_count == 0 OR all retries succeeded (healthy)
    1 — at least one transient failure (will retry next cycle)
    2 — at least one row gave up after max_retries (ops attention)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from solver_orchestrator.billing_reconciler import retry_pending_finalizes
from solver_orchestrator.config import settings


def _json_default(obj: object) -> object:
    if isinstance(obj, (UUID, Decimal)):
        return str(obj)
    raise TypeError(f"unserializable: {type(obj).__name__}")


async def _run(max_retries: int, batch_limit: int) -> int:
    engine = create_async_engine(settings.database_url, future=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            report = await retry_pending_finalizes(
                session, max_retries=max_retries, batch_limit=batch_limit
            )
    finally:
        await engine.dispose()

    payload = {
        "event": "billing.reconciler.report",
        "pending": report.pending_count,
        "succeeded": report.succeeded_count,
        "failed": report.failed_count,
        "exhausted": report.exhausted_count,
        "results": [asdict(r) for r in report.results],
    }
    sys.stdout.write(json.dumps(payload, default=_json_default, ensure_ascii=False) + "\n")

    sys.stderr.write(
        f"[billing-reconciler] pending={report.pending_count} "
        f"succeeded={report.succeeded_count} failed={report.failed_count} "
        f"exhausted={report.exhausted_count}\n"
    )

    if report.exhausted_count > 0:
        return 2
    if report.failed_count > 0:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Billing finalize retry reconciler (M2.2c)")
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Max retries before giving up on a row (default 5)",
    )
    parser.add_argument(
        "--batch-limit",
        type=int,
        default=100,
        help="Max rows processed per run (default 100)",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.max_retries, args.batch_limit))


if __name__ == "__main__":
    sys.exit(main())
