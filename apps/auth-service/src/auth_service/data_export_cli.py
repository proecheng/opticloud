"""PIPL JSON/CSV data export worker CLI — Story 5.C.3 / 5.C.4.

Usage:
    uv run python -m auth_service.data_export_cli
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from auth_service.config import settings
from auth_service.data_export import complete_pending_data_export_requests


def _json_default(obj: object) -> object:
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"unserializable: {type(obj).__name__}")


async def _run(now: datetime | None = None, limit: int = 10) -> int:
    engine = create_async_engine(settings.database_url, future=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            completed = await complete_pending_data_export_requests(session, now=now, limit=limit)
            await session.commit()
    finally:
        await engine.dispose()

    payload = {
        "event": "data_export.worker.report",
        "completed_count": len(completed),
        "completed_export_ids": completed,
    }
    sys.stdout.write(json.dumps(payload, default=_json_default, ensure_ascii=False) + "\n")
    sys.stderr.write(f"[data-export] completed={len(completed)}\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="PIPL JSON/CSV data export worker")
    parser.add_argument(
        "--now",
        type=lambda s: datetime.fromisoformat(s).astimezone(UTC),
        default=None,
        help="ISO 8601 timestamp override for tests / one-off replays.",
    )
    parser.add_argument("--limit", type=int, default=10, help="Max queued exports to process.")
    args = parser.parse_args()
    return asyncio.run(_run(now=args.now, limit=args.limit))


if __name__ == "__main__":
    sys.exit(main())
