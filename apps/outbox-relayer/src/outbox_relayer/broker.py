"""Redis pub/sub publisher (v1 — outbox table is the persistence layer).

v2+ migration to Redis Streams or Kafka adds consumer groups + replay.
"""

from __future__ import annotations

import json

import redis.asyncio as redis_async

from outbox_relayer.config import settings
from outbox_relayer.db import OutboxRow


def channel_for(row: OutboxRow) -> str:
    """Channel naming: opticloud.{aggregate_type}.{event_type}"""
    return f"opticloud.{row.aggregate_type}.{row.event_type}"


async def connect() -> redis_async.Redis:
    """Open a Redis client (auto-pool inside redis-py)."""
    return redis_async.from_url(settings.redis_url, decode_responses=True)


async def publish(client: redis_async.Redis, row: OutboxRow) -> None:
    """Publish a single event envelope as JSON."""
    envelope = {
        "event_id": str(row.id),
        "aggregate_type": row.aggregate_type,
        "aggregate_id": str(row.aggregate_id),
        "event_type": row.event_type,
        "event_version": row.event_version,
        "payload": row.payload,
        "headers": row.headers,
        "occurred_at": row.occurred_at.isoformat(),
    }
    await client.publish(channel_for(row), json.dumps(envelope))


async def ping(client: redis_async.Redis) -> bool:
    """Cheap reachability check for /readyz."""
    try:
        result = await client.ping()  # type: ignore[misc]
        return bool(result)
    except Exception:  # noqa: BLE001
        return False


__all__ = ["channel_for", "connect", "publish", "ping"]
