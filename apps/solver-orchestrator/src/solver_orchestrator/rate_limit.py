"""Plan-aware Redis sliding-window rate limiting (Story 8.B.2)."""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal, cast

import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from solver_orchestrator.config import settings

PlanCode = Literal["free", "starter", "pro", "team", "enterprise"]
RateLimitScope = Literal["execution_write"]


@dataclass(frozen=True)
class PlanRateLimit:
    requests_per_second: int | None
    requests_per_minute: int | None
    custom: bool = False


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    plan_code: PlanCode
    scope: RateLimitScope
    limit: int
    remaining: int
    reset_epoch_seconds: int
    retry_after_seconds: int
    window_seconds: int


class RateLimitExceededError(Exception):
    def __init__(self, decision: RateLimitDecision) -> None:
        super().__init__("rate limit exceeded")
        self.decision = decision


class RateLimitUnavailableError(Exception):
    pass


PLAN_RATE_LIMITS: dict[PlanCode, PlanRateLimit] = {
    "free": PlanRateLimit(requests_per_second=3, requests_per_minute=30),
    "starter": PlanRateLimit(requests_per_second=5, requests_per_minute=200),
    "pro": PlanRateLimit(requests_per_second=20, requests_per_minute=1000),
    "team": PlanRateLimit(requests_per_second=100, requests_per_minute=5000),
    "enterprise": PlanRateLimit(requests_per_second=None, requests_per_minute=None, custom=True),
}

_SLIDING_WINDOW_LUA = """
local now_ms = tonumber(ARGV[1])
local member = ARGV[2]
local window_count = tonumber(ARGV[3])

local exceeded = 0
local exceeded_limit = 0
local exceeded_reset_ms = 0
local exceeded_retry_ms = 0
local exceeded_window_ms = 0

for i = 1, window_count do
  local key = KEYS[i]
  local arg_index = 4 + ((i - 1) * 2)
  local window_ms = tonumber(ARGV[arg_index])
  local limit = tonumber(ARGV[arg_index + 1])
  redis.call('ZREMRANGEBYSCORE', key, 0, now_ms - window_ms)
  local count = redis.call('ZCARD', key)
  if count >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local oldest_score = now_ms
    if oldest[2] ~= nil then
      oldest_score = tonumber(oldest[2])
    end
    local reset_ms = oldest_score + window_ms
    local retry_ms = reset_ms - now_ms
    if retry_ms < 1 then
      retry_ms = 1
    end
    if exceeded == 0 or retry_ms < exceeded_retry_ms or
        (retry_ms == exceeded_retry_ms and window_ms < exceeded_window_ms) then
      exceeded = 1
      exceeded_limit = limit
      exceeded_reset_ms = reset_ms
      exceeded_retry_ms = retry_ms
      exceeded_window_ms = window_ms
    end
  end
end

if exceeded == 1 then
  return {0, exceeded_limit, 0, exceeded_reset_ms, exceeded_retry_ms, exceeded_window_ms}
end

for i = 1, window_count do
  local key = KEYS[i]
  local arg_index = 4 + ((i - 1) * 2)
  local window_ms = tonumber(ARGV[arg_index])
  redis.call('ZADD', key, now_ms, member .. ':' .. i)
  redis.call('PEXPIRE', key, window_ms)
end

return {1, 0, 0, 0, 0, 0}
"""

_redis_client: redis.Redis | None = None


def _client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=settings.rate_limit_redis_timeout_seconds,
            socket_connect_timeout=settings.rate_limit_redis_timeout_seconds,
        )
    return _redis_client


async def resolve_user_plan_code(session: AsyncSession, user_id: uuid.UUID) -> PlanCode:
    result = await session.execute(
        text(
            """
            SELECT plan_code
            FROM billing_subscriptions
            WHERE user_id = :user_id
              AND status = 'active'
              AND current_period_start <= NOW()
              AND current_period_end > NOW()
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"user_id": user_id},
    )
    raw = result.scalar_one_or_none()
    if raw in PLAN_RATE_LIMITS:
        return cast(PlanCode, raw)
    return "free"


async def enforce_rate_limit(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    scope: RateLimitScope = "execution_write",
) -> None:
    plan_code = await resolve_user_plan_code(session, user_id)
    limits = PLAN_RATE_LIMITS[plan_code]
    if limits.custom:
        return

    now = time.time()
    checks: list[tuple[int, int]] = []
    if limits.requests_per_second is not None:
        checks.append((1, limits.requests_per_second))
    if limits.requests_per_minute is not None:
        checks.append((60, limits.requests_per_minute))

    try:
        decision = await _check_sliding_windows(
            _client(),
            plan_code=plan_code,
            user_id=user_id,
            scope=scope,
            checks=checks,
            now=now,
        )
    except Exception as exc:
        raise RateLimitUnavailableError("rate limit backend unavailable") from exc

    if decision is not None:
        raise RateLimitExceededError(decision)


async def _check_sliding_windows(
    client: redis.Redis,
    *,
    plan_code: PlanCode,
    user_id: uuid.UUID,
    scope: RateLimitScope,
    checks: list[tuple[int, int]],
    now: float,
) -> RateLimitDecision | None:
    if not checks:
        return None
    now_ms = int(now * 1000)
    keys = [
        _window_key(
            plan_code=plan_code,
            user_id=user_id,
            scope=scope,
            window_seconds=window_seconds,
        )
        for window_seconds, _limit in checks
    ]
    args: list[int | str] = [now_ms, uuid.uuid4().hex, len(checks)]
    for window_seconds, limit in checks:
        args.extend((window_seconds * 1000, limit))
    try:
        raw = await cast(Any, client.eval)(_SLIDING_WINDOW_LUA, len(keys), *keys, *args)
    except Exception as exc:
        raise RateLimitUnavailableError("rate limit backend unavailable") from exc
    if not isinstance(raw, list | tuple) or len(raw) != 6:
        raise RateLimitUnavailableError("unexpected Redis script result")

    allowed = int(raw[0]) == 1
    if allowed:
        return None

    limit = int(raw[1])
    remaining = int(raw[2])
    reset_ms = int(raw[3])
    retry_ms = int(raw[4])
    window_ms = int(raw[5])
    if limit <= 0 or reset_ms <= 0 or retry_ms <= 0 or window_ms <= 0:
        raise RateLimitUnavailableError("invalid Redis script denial result")
    return RateLimitDecision(
        allowed=False,
        plan_code=plan_code,
        scope=scope,
        limit=limit,
        remaining=max(remaining, 0),
        reset_epoch_seconds=int(math.ceil(reset_ms / 1000)),
        retry_after_seconds=max(int(math.ceil(retry_ms / 1000)), 1),
        window_seconds=max(int(math.ceil(window_ms / 1000)), 1),
    )


def _window_key(
    *,
    plan_code: PlanCode,
    user_id: uuid.UUID,
    scope: RateLimitScope,
    window_seconds: int,
) -> str:
    return f"ratelimit:{plan_code}:{user_id}:{scope}:{window_seconds}"
