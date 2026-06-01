"""Redis read-through cache helpers for capability-registry."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

CAPABILITY_CACHE_PREFIX = "capability_cache:"


class CapabilityCache:
    """Small Redis wrapper that fails open for read paths."""

    def __init__(self, redis_url: str, ttl_seconds: int) -> None:
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._ttl_seconds = ttl_seconds

    async def get_json(self, key: str) -> Any | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set_json(self, key: str, value: Any) -> None:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        await self._redis.set(key, raw, ex=self._ttl_seconds)

    async def delete_pattern(self, pattern: str) -> None:
        keys = [key async for key in self._redis.scan_iter(match=pattern)]
        if keys:
            await self._redis.delete(*keys)


def cache_key(name: str, **params: object) -> str:
    """Build a deterministic capability cache key."""
    parts = [f"{key}={params[key]}" for key in sorted(params)]
    suffix = "|".join(parts)
    return f"{CAPABILITY_CACHE_PREFIX}{name}:{suffix}"
