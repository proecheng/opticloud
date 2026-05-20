"""Account deletion worker CLI — Story 1.6.

Usage:
    uv run python -m auth_service.account_deletion_cli

M3 can wrap this module in a K8s CronJob, systemd timer, or Dramatiq cron actor.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from auth_service.account_deletion import complete_due_deletion_requests
from auth_service.config import settings


def _json_default(obj: object) -> object:
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"unserializable: {type(obj).__name__}")


async def _run(now: datetime | None = None) -> int:
    engine = create_async_engine(settings.database_url, future=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            completed = await complete_due_deletion_requests(session, now=now)
            await session.commit()
    finally:
        await engine.dispose()

    payload = {
        "event": "account_deletion.worker.report",
        "completed_count": len(completed),
        "completed_user_ids": completed,
    }
    sys.stdout.write(json.dumps(payload, default=_json_default, ensure_ascii=False) + "\n")
    sys.stderr.write(f"[account-deletion] completed={len(completed)}\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="PIPL account deletion hard-delete worker")
    parser.add_argument(
        "--now",
        type=lambda s: datetime.fromisoformat(s).astimezone(UTC),
        default=None,
        help="ISO 8601 timestamp override for tests / one-off replays.",
    )
    args = parser.parse_args()
    return asyncio.run(_run(now=args.now))


if __name__ == "__main__":
    sys.exit(main())
