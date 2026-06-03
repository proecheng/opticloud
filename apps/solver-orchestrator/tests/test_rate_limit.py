"""Story 8.B.2 - plan-aware rate limit + 429 tests."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from solver_orchestrator import billing_client, solvers
from solver_orchestrator.config import settings
from solver_orchestrator.db import get_session
from solver_orchestrator.main import app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


DATABASE_URL = os.getenv("DATABASE_URL", settings.database_url)

LP_BODY = {
    "task_type": "lp",
    "minimize": {"c": [1.0, 1.0]},
    "st": {"A": [[1.0, 1.0]], "b": [10.0]},
}
PREDICTION_BODY = {"family": "arima", "data": [1, 2, 3, 4], "horizon": 3}


def _make_api_key() -> tuple[str, str, int]:
    random_part = f"t8b2{uuid.uuid4().hex}"
    full = f"sk-{random_part}"
    pepper_version = 1
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    key_hash = hmac.new(pepper, full.encode("utf-8"), hashlib.sha256).hexdigest()
    return full, key_hash, pepper_version


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    await _ensure_tables(eng)
    yield eng
    await eng.dispose()


async def _ensure_tables(db_engine: AsyncEngine) -> None:
    async with db_engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS billing_subscriptions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    plan_code VARCHAR(32) NOT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'active',
                    current_period_start TIMESTAMPTZ NOT NULL,
                    current_period_end TIMESTAMPTZ NOT NULL,
                    last_refilled_period_start TIMESTAMPTZ NULL,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS job_templates (
                    id UUID PRIMARY KEY,
                    user_id UUID NOT NULL,
                    name VARCHAR(120) NOT NULL,
                    description TEXT NULL,
                    source_kind VARCHAR(32) NOT NULL,
                    source_id UUID NOT NULL,
                    task_type VARCHAR(64) NOT NULL,
                    payload_schema_version VARCHAR(64) NOT NULL,
                    payload_json JSONB NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    root_template_id UUID NOT NULL,
                    parent_template_id UUID NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    deleted_at TIMESTAMPTZ NULL
                )
                """
            )
        )


async def _seed_api_key(
    db_engine: AsyncEngine, *, plan_code: str | None = None
) -> tuple[str, uuid.UUID, uuid.UUID]:
    user_id = uuid.uuid4()
    key_id = uuid.uuid4()
    full, key_hash, version = _make_api_key()
    now = datetime.now(UTC)
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO users(id, email, phone, created_at, updated_at) "
                "VALUES (:id, :email, :phone, :now, :now) "
                "ON CONFLICT(id) DO NOTHING"
            ),
            {
                "id": user_id,
                "email": f"8-b-2-{user_id}@example.com",
                "phone": f"+868{user_id.int % 10**10:010d}",
                "now": now,
            },
        )
        await s.execute(
            text(
                "INSERT INTO api_keys(id, user_id, label, key_prefix, key_hash, pepper_version, "
                "scope, created_at, expires_at) VALUES "
                "(:id, :uid, :label, :prefix, :hash, :v, ARRAY['optimize:write'], :now, :exp)"
            ),
            {
                "id": key_id,
                "uid": user_id,
                "label": "8-b-2-test",
                "prefix": full[:6],
                "hash": key_hash,
                "v": version,
                "now": now,
                "exp": now + timedelta(days=365),
            },
        )
        if plan_code is not None:
            await s.execute(
                text(
                    """
                    INSERT INTO billing_subscriptions
                        (id, user_id, plan_code, status, current_period_start, current_period_end)
                    VALUES (:id, :uid, :plan_code, 'active', :start, :end)
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "uid": user_id,
                    "plan_code": plan_code,
                    "start": now,
                    "end": now + timedelta(days=30),
                },
            )
        await s.commit()
    return f"Bearer {full}", user_id, key_id


@pytest_asyncio.fixture(loop_scope="session")
async def client_with_db(db_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)

    async def _override() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            try:
                yield s
            finally:
                try:
                    await s.commit()
                except Exception:
                    await s.rollback()

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _assert_429(response: Any) -> dict[str, Any]:
    assert response.status_code == 429, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["X-RateLimit-Limit"] == "3"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert int(response.headers["X-RateLimit-Reset"]) > 0
    assert response.headers["Retry-After"] == "1"
    body = response.json()
    assert body["status"] == 429
    assert body["type"].endswith("/rate_limit_exceeded")
    assert body["errors"][0]["field_path"] == "rate_limit"
    assert body["errors"][0]["remediation_hint_key"] == "errors.429.rate_limit_exceeded"
    assert body["next_action_url"] == "https://console.opticloud.cn/billing/plans"
    assert "ratelimit:" not in response.text
    return body


async def test_plan_limit_values_match_billing_catalog() -> None:
    from billing_service.plans import PLAN_BY_CODE
    from solver_orchestrator.rate_limit import PLAN_RATE_LIMITS

    for plan_code in ("free", "starter", "pro", "team"):
        assert PLAN_RATE_LIMITS[plan_code].requests_per_second == (
            PLAN_BY_CODE[plan_code].rate_limits.rps
        )
        assert PLAN_RATE_LIMITS[plan_code].requests_per_minute == (
            PLAN_BY_CODE[plan_code].rate_limits.requests_per_minute
        )
    assert PLAN_RATE_LIMITS["enterprise"].custom is True
    assert PLAN_RATE_LIMITS["enterprise"].requests_per_second is None
    assert PLAN_RATE_LIMITS["enterprise"].requests_per_minute is None


async def test_resolve_user_plan_defaults_to_free_and_ignores_inactive_rows(
    db_engine: AsyncEngine,
) -> None:
    from solver_orchestrator.rate_limit import resolve_user_plan_code

    auth, user_id, _ = await _seed_api_key(db_engine)
    del auth
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        assert await resolve_user_plan_code(s, user_id) == "free"
        now = datetime.now(UTC)
        expired_subscription_id = uuid.uuid4()
        await s.execute(
            text(
                """
                INSERT INTO billing_subscriptions
                    (id, user_id, plan_code, status, current_period_start, current_period_end)
                VALUES (:id, :uid, 'pro', 'canceled', :start, :end)
                """
            ),
            {
                "id": uuid.uuid4(),
                "uid": user_id,
                "start": now - timedelta(seconds=1),
                "end": now + timedelta(days=30),
            },
        )
        await s.flush()
        assert await resolve_user_plan_code(s, user_id) == "free"
        await s.execute(
            text(
                """
                INSERT INTO billing_subscriptions
                    (id, user_id, plan_code, status, current_period_start, current_period_end)
                VALUES (:id, :uid, 'pro', 'active', :start, :end)
                """
            ),
            {
                "id": expired_subscription_id,
                "uid": user_id,
                "start": now - timedelta(days=60),
                "end": now - timedelta(days=30),
            },
        )
        await s.flush()
        assert await resolve_user_plan_code(s, user_id) == "free"
        await s.execute(
            text("UPDATE billing_subscriptions SET status = 'canceled' WHERE id = :id"),
            {"id": expired_subscription_id},
        )
        await s.flush()
        await s.execute(
            text(
                """
                INSERT INTO billing_subscriptions
                    (id, user_id, plan_code, status, current_period_start, current_period_end)
                VALUES (:id, :uid, 'starter', 'active', :start, :end)
                """
            ),
            {
                "id": uuid.uuid4(),
                "uid": user_id,
                "start": now - timedelta(seconds=1),
                "end": now + timedelta(days=30),
            },
        )
        await s.flush()
        assert await resolve_user_plan_code(s, user_id) == "starter"


@pytest.mark.parametrize("plan_code", ["starter", "pro", "team"])
async def test_resolve_user_plan_returns_active_paid_plan(
    db_engine: AsyncEngine, plan_code: str
) -> None:
    from solver_orchestrator.rate_limit import resolve_user_plan_code

    auth, user_id, _ = await _seed_api_key(db_engine, plan_code=plan_code)
    del auth
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        assert await resolve_user_plan_code(s, user_id) == plan_code


class _FakeSlidingRedis:
    def __init__(self) -> None:
        self.zsets: dict[str, list[tuple[int, str]]] = {}
        self.scripts: list[str] = []

    async def eval(self, script: str, numkeys: int, *keys_and_args: object) -> list[int]:
        self.scripts.append(script)
        assert "ZREMRANGEBYSCORE" in script
        assert "ZCARD" in script
        assert "ZADD" in script
        keys = [str(key) for key in keys_and_args[:numkeys]]
        args = list(keys_and_args[numkeys:])
        now_ms = int(args[0])
        member = str(args[1])
        window_count = int(args[2])
        assert window_count == numkeys

        exceeded: tuple[int, int, int, int] | None = None
        for index, key in enumerate(keys):
            window_ms = int(args[3 + index * 2])
            limit = int(args[4 + index * 2])
            cutoff = now_ms - window_ms
            active = [(score, item) for score, item in self.zsets.get(key, []) if score > cutoff]
            self.zsets[key] = active
            count = len(active)
            if count >= limit:
                oldest = min(score for score, _ in active) if active else now_ms
                reset_ms = oldest + window_ms
                retry_ms = max(reset_ms - now_ms, 1)
                candidate = (retry_ms, window_ms, limit, reset_ms)
                if exceeded is None or candidate[:2] < exceeded[:2]:
                    exceeded = candidate

        if exceeded is not None:
            retry_ms, window_ms, limit, reset_ms = exceeded
            return [0, limit, 0, reset_ms, retry_ms, window_ms]

        for index, key in enumerate(keys):
            window_ms = int(args[3 + index * 2])
            self.zsets.setdefault(key, []).append((now_ms, f"{member}:{index}"))
            self.zsets[key].sort()
            del window_ms
        return [1, 0, 0, 0, 0, 0]


class _FailingRedis:
    async def eval(self, *_args: object, **_kwargs: object) -> object:
        raise OSError("redis unavailable")


async def test_sliding_window_allows_exact_boundary_and_denies_inside_window() -> None:
    from solver_orchestrator import rate_limit

    fake = _FakeSlidingRedis()
    user_id = uuid.uuid4()
    for offset in (0.0, 0.1, 0.2):
        assert (
            await rate_limit._check_sliding_windows(
                fake,
                plan_code="free",
                user_id=user_id,
                scope="execution_write",
                checks=[(1, 3)],
                now=1_000.0 + offset,
            )
            is None
        )

    denied = await rate_limit._check_sliding_windows(
        fake,
        plan_code="free",
        user_id=user_id,
        scope="execution_write",
        checks=[(1, 3)],
        now=1_000.5,
    )
    assert denied is not None
    assert denied.limit == 3
    assert denied.remaining == 0
    assert denied.retry_after_seconds == 1
    assert denied.reset_epoch_seconds == 1_001
    assert denied.window_seconds == 1
    assert all(key.startswith(f"ratelimit:free:{user_id}:execution_write:1") for key in fake.zsets)

    assert (
        await rate_limit._check_sliding_windows(
            fake,
            plan_code="free",
            user_id=user_id,
            scope="execution_write",
            checks=[(1, 3)],
            now=1_001.0,
        )
        is None
    )


async def test_minute_window_retry_after_uses_oldest_active_request() -> None:
    from solver_orchestrator import rate_limit

    fake = _FakeSlidingRedis()
    user_id = uuid.uuid4()
    for now in (2_000.0, 2_005.0):
        assert (
            await rate_limit._check_sliding_windows(
                fake,
                plan_code="starter",
                user_id=user_id,
                scope="execution_write",
                checks=[(60, 2)],
                now=now,
            )
            is None
        )

    denied = await rate_limit._check_sliding_windows(
        fake,
        plan_code="starter",
        user_id=user_id,
        scope="execution_write",
        checks=[(60, 2)],
        now=2_006.0,
    )
    assert denied is not None
    assert denied.limit == 2
    assert denied.retry_after_seconds == 54
    assert denied.reset_epoch_seconds == 2_060
    assert denied.window_seconds == 60


async def test_sliding_window_checks_second_and_minute_windows_atomically() -> None:
    from solver_orchestrator import rate_limit

    fake = _FakeSlidingRedis()
    user_id = uuid.uuid4()
    for now in (3_000.0, 3_001.1):
        assert (
            await rate_limit._check_sliding_windows(
                fake,
                plan_code="free",
                user_id=user_id,
                scope="execution_write",
                checks=[(1, 3), (60, 2)],
                now=now,
            )
            is None
        )

    counts_before = {key: len(values) for key, values in fake.zsets.items()}
    denied = await rate_limit._check_sliding_windows(
        fake,
        plan_code="free",
        user_id=user_id,
        scope="execution_write",
        checks=[(1, 3), (60, 2)],
        now=3_002.0,
    )
    counts_after = {key: len(values) for key, values in fake.zsets.items()}
    assert denied is not None
    assert denied.limit == 2
    assert denied.window_seconds == 60
    assert counts_after == counts_before
    assert sorted(key.rsplit(":", 1)[-1] for key in fake.zsets) == ["1", "60"]


async def test_sliding_window_redis_failure_is_rate_limit_unavailable() -> None:
    from solver_orchestrator import rate_limit

    with pytest.raises(rate_limit.RateLimitUnavailableError):
        await rate_limit._check_sliding_windows(
            _FailingRedis(),
            plan_code="free",
            user_id=uuid.uuid4(),
            scope="execution_write",
            checks=[(1, 3)],
            now=1_000.0,
        )


async def test_rate_limit_unavailable_response_uses_503_catalog() -> None:
    from solver_orchestrator.routes import _rate_limit_unavailable_response

    response = _rate_limit_unavailable_response(request_id="req-rate-limit-down")
    assert response.status_code == 503
    assert response.media_type == "application/problem+json"
    body = json.loads(response.body)
    assert body["status"] == 503
    assert body["type"].endswith("/rate_limit_unavailable")
    assert body["request_id"] == "req-rate-limit-down"
    assert body["errors"][0]["field_path"] == "rate_limit"
    assert body["errors"][0]["remediation_hint_key"] == "errors.503.rate_limit_unavailable"


async def test_free_fourth_optimization_returns_429_and_skips_side_effects(
    client_with_db: AsyncClient,
    db_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from solver_orchestrator import rate_limit
    from solver_orchestrator.rate_limit import RateLimitDecision, RateLimitExceededError

    auth, user_id, _ = await _seed_api_key(db_engine)
    calls = {"limit": 0, "reserve": 0, "finalize": 0, "solve": 0}

    async def _fake_enforce(*_args: object, **_kwargs: object) -> None:
        calls["limit"] += 1
        if calls["limit"] >= 4:
            raise RateLimitExceededError(
                RateLimitDecision(
                    allowed=False,
                    plan_code="free",
                    scope="execution_write",
                    limit=3,
                    remaining=0,
                    reset_epoch_seconds=1_900_000_001,
                    retry_after_seconds=1,
                    window_seconds=1,
                )
            )

    async def _billing_should_not_run(*_args: object, **_kwargs: object) -> None:
        calls["reserve"] += 1
        raise AssertionError("429 must not call billing")

    def _solve(*_args: object, **_kwargs: object) -> Any:
        calls["solve"] += 1
        return solvers.LPSolveResult(
            status="optimal",
            objective=0.0,
            solution={"x": [0.0, 0.0]},
            solve_seconds=0.01,
        )

    monkeypatch.setattr(rate_limit, "enforce_rate_limit", _fake_enforce)
    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    headers = {"Authorization": auth}
    for _ in range(3):
        allowed = await client_with_db.post("/v1/optimizations", json=LP_BODY, headers=headers)
        assert allowed.status_code == 200, allowed.text

    before_count = await _count_rows(db_engine, "optimizations", user_id)
    denied = await client_with_db.post(
        "/v1/optimizations",
        json=LP_BODY,
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(uuid.uuid4())},
    )
    _assert_429(denied)
    after_count = await _count_rows(db_engine, "optimizations", user_id)

    assert before_count == after_count
    assert calls["limit"] == 4
    assert calls["reserve"] == 0
    assert calls["finalize"] == 0
    assert calls["solve"] == 3


async def test_batch_prediction_rerun_and_template_writes_are_rate_limited(
    client_with_db: AsyncClient,
    db_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from solver_orchestrator import rate_limit
    from solver_orchestrator.rate_limit import RateLimitDecision, RateLimitExceededError

    auth, user_id, api_key_id = await _seed_api_key(db_engine)
    source_prediction_id = await _seed_prediction(db_engine, user_id=user_id, api_key_id=api_key_id)
    source_template_id = await _seed_job_template(
        db_engine,
        user_id=user_id,
        source_id=source_prediction_id,
    )

    async def _always_limited(*_args: object, **_kwargs: object) -> None:
        raise RateLimitExceededError(
            RateLimitDecision(
                allowed=False,
                plan_code="free",
                scope="execution_write",
                limit=3,
                remaining=0,
                reset_epoch_seconds=1_900_000_001,
                retry_after_seconds=1,
                window_seconds=1,
            )
        )

    monkeypatch.setattr(rate_limit, "enforce_rate_limit", _always_limited)

    headers = {"Authorization": auth}
    batch = await client_with_db.post(
        "/v1/optimizations/batch",
        json={"tasks": [LP_BODY]},
        headers=headers,
    )
    prediction = await client_with_db.post(
        "/v1/predictions",
        json=PREDICTION_BODY,
        headers=headers,
    )
    rerun = await client_with_db.post(
        "/v1/reproduce/repro-2026-ABCDEFG/rerun",
        json=LP_BODY,
        headers=headers,
    )
    create_template = await client_with_db.post(
        "/v1/job-templates",
        json={
            "name": "blocked",
            "source_kind": "prediction",
            "source_id": str(source_prediction_id),
        },
        headers=headers,
    )
    create_version = await client_with_db.post(
        f"/v1/job-templates/{source_template_id}/versions",
        json={"parameter_path": "horizon", "value": 4},
        headers=headers,
    )
    delete_template = await client_with_db.delete(
        f"/v1/job-templates/{source_template_id}",
        headers=headers,
    )

    for response in (
        batch,
        prediction,
        rerun,
        create_template,
        create_version,
        delete_template,
    ):
        _assert_429(response)


async def _count_rows(db_engine: AsyncEngine, table: str, user_id: uuid.UUID) -> int:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        return int(
            (
                await s.execute(
                    text(f"SELECT COUNT(*) FROM {table} WHERE user_id = :uid"),  # noqa: S608
                    {"uid": user_id},
                )
            ).scalar_one()
        )


async def _seed_prediction(
    db_engine: AsyncEngine, *, user_id: uuid.UUID, api_key_id: uuid.UUID
) -> uuid.UUID:
    prediction_id = uuid.uuid4()
    now = datetime.now(UTC)
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                """
                INSERT INTO predictions
                    (id, user_id, api_key_id, family, status, input_payload, prediction,
                     drift_score, model_version, predict_seconds, completed_at)
                VALUES
                    (:id, :uid, :kid, 'arima', 'completed',
                     CAST(:payload AS jsonb), CAST(:prediction AS jsonb),
                     0.1, CAST(:model_version AS jsonb), 0.01, :now)
                """
            ),
            {
                "id": prediction_id,
                "uid": user_id,
                "kid": api_key_id,
                "payload": '{"family":"arima","data":[1,2,3,4],"horizon":3}',
                "prediction": '{"p10":[1,2,3],"p50":[2,3,4],"p90":[3,4,5]}',
                "model_version": '{"provider_id":"arima","kind":"open_source","version":"test"}',
                "now": now,
            },
        )
        await s.commit()
    return prediction_id


async def _seed_job_template(
    db_engine: AsyncEngine, *, user_id: uuid.UUID, source_id: uuid.UUID
) -> uuid.UUID:
    template_id = uuid.uuid4()
    now = datetime.now(UTC)
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                """
                INSERT INTO job_templates
                    (id, user_id, name, source_kind, source_id, task_type,
                     payload_schema_version, payload_json, payload_sha256, version,
                     root_template_id, parent_template_id, created_at, updated_at, deleted_at)
                VALUES
                    (:id, :uid, 'existing', 'prediction', :source_id, 'forecast',
                     'prediction_request_v1', CAST(:payload AS jsonb), :sha, 1,
                     :id, NULL, :now, :now, NULL)
                """
            ),
            {
                "id": template_id,
                "uid": user_id,
                "source_id": source_id,
                "payload": '{"family":"arima","data":[1,2,3,4],"horizon":3}',
                "sha": "0" * 64,
                "now": now,
            },
        )
        await s.commit()
    return template_id
