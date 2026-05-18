"""Postgres async client — direct asyncpg, no SQLAlchemy.

D1 justification: relayer is batch-oriented SQL with no ORM benefit. Raw asyncpg
is faster + simpler than wrapping SQLAlchemy for SELECT FOR UPDATE batches.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg

from outbox_relayer.config import settings


@dataclass(frozen=True)
class OutboxRow:
    id: UUID
    aggregate_type: str
    aggregate_id: UUID
    event_type: str
    event_version: int
    payload: dict[str, Any]
    headers: dict[str, Any]
    occurred_at: datetime


def _asyncpg_dsn(url: str) -> str:
    """Strip the SQLAlchemy +asyncpg dialect suffix if present (asyncpg uses bare postgres://)."""
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def connect() -> asyncpg.Connection:
    """Open a single asyncpg connection."""
    return await asyncpg.connect(_asyncpg_dsn(settings.database_url))


async def fetch_unsent(conn: asyncpg.Connection, limit: int) -> list[OutboxRow]:
    """Pull a batch of unsent rows; FOR UPDATE SKIP LOCKED for multi-relayer safety.

    NOTE: callers MUST be inside an `async with conn.transaction()` block — the
    row locks release on transaction commit/rollback.
    """
    records = await conn.fetch(
        """
        SELECT id, aggregate_type, aggregate_id, event_type, event_version,
               payload, headers, occurred_at
          FROM outbox
         WHERE sent_at IS NULL
         ORDER BY occurred_at
         FOR UPDATE SKIP LOCKED
         LIMIT $1
        """,
        limit,
    )
    return [
        OutboxRow(
            id=r["id"],
            aggregate_type=r["aggregate_type"],
            aggregate_id=r["aggregate_id"],
            event_type=r["event_type"],
            event_version=r["event_version"],
            payload=json.loads(r["payload"])
            if isinstance(r["payload"], str)
            else dict(r["payload"]),
            headers=json.loads(r["headers"])
            if isinstance(r["headers"], str)
            else dict(r["headers"]),
            occurred_at=r["occurred_at"],
        )
        for r in records
    ]


async def mark_sent(conn: asyncpg.Connection, ids: list[UUID]) -> None:
    """Mark a batch of rows as published. No-op for empty list.

    Uses executemany() to avoid array-parameter quirks with FOR UPDATE locks.
    """
    if not ids:
        return
    await conn.executemany("UPDATE outbox SET sent_at = NOW() WHERE id = $1", [(i,) for i in ids])


async def get_oldest_unsent_age_seconds(conn: asyncpg.Connection) -> float | None:
    """SR3 lag metric — age of the oldest unsent row, in seconds; None if empty."""
    row = await conn.fetchrow(
        "SELECT EXTRACT(EPOCH FROM (NOW() - MIN(occurred_at))) AS age "
        "FROM outbox WHERE sent_at IS NULL"
    )
    if row is None or row["age"] is None:
        return None
    return float(row["age"])


__all__ = ["OutboxRow", "connect", "fetch_unsent", "mark_sent", "get_oldest_unsent_age_seconds"]
