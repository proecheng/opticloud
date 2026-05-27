"""Story 3.3 - sync/async execution mode tests."""

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

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from solver_orchestrator import billing_client, solvers
from solver_orchestrator.billing_client import BillingResult
from solver_orchestrator.config import settings
from solver_orchestrator.db import get_session
from solver_orchestrator.main import app
from solver_orchestrator.models import Optimization
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

SMALL_LP_BODY = {
    "task_type": "lp",
    "minimize": {"c": [1.0, 1.0]},
    "st": {"A": [[1.0, 1.0]], "b": [10.0]},
}


def _large_lp_body(size: int = 200) -> dict:
    return {
        "task_type": "lp",
        "minimize": {"c": [1.0] * size},
        "st": {
            "A": [[1.0] * size for _ in range(size)],
            "b": [float(size)] * size,
        },
    }


def _make_api_key() -> tuple[str, str, int]:
    random_part = f"t33{uuid.uuid4().hex}"
    full = f"sk-{random_part}"
    pepper_version = 1
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    key_hash = hmac.new(pepper, full.encode("utf-8"), hashlib.sha256).hexdigest()
    return full, key_hash, pepper_version


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def api_key(db_engine: AsyncEngine) -> AsyncIterator[tuple[str, uuid.UUID]]:
    user_id = uuid.uuid4()
    key_id = uuid.uuid4()
    full, key_hash, version = _make_api_key()
    key_prefix = full[:6]

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
                "email": f"3-3-{user_id}@example.com",
                "phone": f"+863{user_id.int % 10**10:010d}",
                "now": datetime.now(UTC),
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
                "label": "3-3-test",
                "prefix": key_prefix,
                "hash": key_hash,
                "v": version,
                "now": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(days=365),
            },
        )
        await s.commit()

    yield (f"Bearer {full}", user_id)


@pytest_asyncio.fixture(loop_scope="session")
async def second_api_key(db_engine: AsyncEngine) -> AsyncIterator[tuple[str, uuid.UUID]]:
    user_id = uuid.uuid4()
    key_id = uuid.uuid4()
    full, key_hash, version = _make_api_key()
    key_prefix = full[:6]

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
                "email": f"3-3-b-{user_id}@example.com",
                "phone": f"+864{user_id.int % 10**10:010d}",
                "now": datetime.now(UTC),
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
                "label": "3-3-test-b",
                "prefix": key_prefix,
                "hash": key_hash,
                "v": version,
                "now": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(days=365),
            },
        )
        await s.commit()

    yield (f"Bearer {full}", user_id)


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


async def test_omitted_mode_small_lp_stays_sync_completed(
    client_with_db: AsyncClient, api_key
) -> None:
    auth, _ = api_key

    resp = await client_with_db.post(
        "/v1/optimizations",
        json=SMALL_LP_BODY,
        headers={"Authorization": auth},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["model_version"]["provider_id"] == "highs"


async def test_explicit_sync_small_lp_stays_sync_completed(
    client_with_db: AsyncClient, api_key
) -> None:
    auth, _ = api_key

    resp = await client_with_db.post(
        "/v1/optimizations?mode=sync",
        json=SMALL_LP_BODY,
        headers={"Authorization": auth},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "completed"


async def test_invalid_mode_is_rfc7807_and_side_effect_free(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    before = await _optimization_count(db_engine, user_id)

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("billing should not run for invalid mode")

    def _solver_should_not_run(*args, **kwargs):
        raise AssertionError("solver should not run for invalid mode")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", _solver_should_not_run)

    resp = await client_with_db.post(
        "/v1/optimizations?mode=later",
        json=SMALL_LP_BODY,
        headers={"Authorization": auth},
    )

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["title"] == "Invalid Execution Mode"
    assert body["errors"][0]["field_path"] == "query.mode"
    assert await _optimization_count(db_engine, user_id) == before


async def test_async_mode_returns_202_queued_row_and_metadata(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, _ = api_key

    resp = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers={"Authorization": auth},
    )

    assert resp.status_code == 202, resp.text
    body = resp.json()
    optimization_id = uuid.UUID(body["optimization_id"])
    assert resp.headers["location"] == f"/v1/optimizations/{optimization_id}"
    assert body["status"] == "queued"
    assert body["mode"] == "async"
    assert body["requested_mode"] == "async"
    assert body["auto_async"] is False
    assert body["progress_pct"] == 0
    assert body["eta_seconds"] is None
    assert body["message"] == "Task queued; background execution is not enabled in Story 3.3"
    assert body["model_version"]["provider_id"] == "highs"
    assert "_system" not in resp.text

    row = await _optimization_row(db_engine, optimization_id)
    assert row["status"] == "queued"
    assert row["solution"] is None
    assert row["objective"] is None
    assert row["solve_seconds"] is None
    assert row["completed_at"] is None
    execution_mode = row["input_payload"]["_system"]["execution_mode"]
    assert execution_mode["requested_mode"] == "async"
    assert execution_mode["effective_mode"] == "async"
    assert execution_mode["auto_async"] is False
    assert execution_mode["threshold_seconds"] == 5.0
    assert row["input_payload"]["_system"]["provider_route"]["provider_id"] == "highs"


async def test_async_mode_does_not_call_billing_solver_cost_or_voucher_side_effects(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _ = api_key

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("billing should not run for async queued path")

    def _solver_should_not_run(*args, **kwargs):
        raise AssertionError("solver should not run for async queued path")

    async def _cost_should_not_run(*args, **kwargs):
        raise AssertionError("cost attribution should not run for async queued path")

    async def _voucher_should_not_run(*args, **kwargs):
        raise AssertionError("voucher issuance should not run for async queued path")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", _solver_should_not_run)
    monkeypatch.setattr(
        "solver_orchestrator.routes._record_solver_cost_attribution", _cost_should_not_run
    )
    monkeypatch.setattr(
        "solver_orchestrator.routes.issue_reproduction_voucher", _voucher_should_not_run
    )

    resp = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json={**SMALL_LP_BODY, "options": {"reproducible": True}},
        headers={"Authorization": auth},
    )

    assert resp.status_code == 202, resp.text


async def test_async_effective_mode_reserves_billing_and_queues_row(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    before = await _optimization_count(db_engine, user_id)
    charge_id = uuid.uuid4()
    calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def _reserve(cid, uid, *, client=None):
        calls.append((cid, uid))
        return BillingResult(
            ok=True,
            status_code=200,
            body={"current_state": "reserved"},
            error_message=None,
        )

    async def _finalize_should_not_run(*args, **kwargs):
        raise AssertionError("billing finalize should not run for async queued path")

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize_should_not_run)

    resp = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )

    assert resp.status_code == 202, resp.text
    assert calls == [(charge_id, user_id)]
    assert await _optimization_count(db_engine, user_id) == before + 1
    row = await _optimization_row(db_engine, uuid.UUID(resp.json()["optimization_id"]))
    billing = row["input_payload"]["_system"]["billing"]
    assert billing["charge_id"] == str(charge_id)
    assert billing["reserved"] is True
    assert billing["reserve_status_code"] == 200


async def test_async_idempotency_replay_same_billing_header_does_not_reserve_twice(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    idem_key = f"3-3-async-billing-replay-{uuid.uuid4()}"
    charge_id = uuid.uuid4()
    calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def _reserve(cid, uid, *, client=None):
        calls.append((cid, uid))
        return BillingResult(
            ok=True,
            status_code=200,
            body={"current_state": "reserved"},
            error_message=None,
        )

    monkeypatch.setattr(billing_client, "reserve", _reserve)

    headers = {
        "Authorization": auth,
        "Idempotency-Key": idem_key,
        "X-Billing-Charge-Id": str(charge_id),
    }
    first = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers=headers,
    )
    assert first.status_code == 202, first.text

    replay = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers=headers,
    )

    assert replay.status_code == 202, replay.text
    assert replay.json()["optimization_id"] == first.json()["optimization_id"]
    assert calls == [(charge_id, user_id)]


async def test_sync_auto_turn_async_reserves_billing_and_queues_row(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    before = await _optimization_count(db_engine, user_id)
    charge_id = uuid.uuid4()
    calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def _reserve(cid, uid, *, client=None):
        calls.append((cid, uid))
        return BillingResult(
            ok=True,
            status_code=200,
            body={"current_state": "reserved"},
            error_message=None,
        )

    async def _finalize_should_not_run(*args, **kwargs):
        raise AssertionError("billing finalize should not run for sync auto-turned async path")

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize_should_not_run)

    resp = await client_with_db.post(
        "/v1/optimizations?mode=sync",
        json=_large_lp_body(),
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )

    assert resp.status_code == 202, resp.text
    assert resp.json()["auto_async"] is True
    assert calls == [(charge_id, user_id)]
    assert await _optimization_count(db_engine, user_id) == before + 1


async def test_async_mode_validates_fallback_chain_before_queuing(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id = api_key
    before = await _optimization_count(db_engine, user_id)
    payload = {**SMALL_LP_BODY, "fallback_chain": ["not-a-solver"]}

    resp = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=payload,
        headers={"Authorization": auth},
    )

    assert resp.status_code == 400, resp.text
    assert resp.json()["title"] == "Unsupported Fallback Solver"
    assert await _optimization_count(db_engine, user_id) == before


async def test_sync_large_lp_auto_turns_async(
    client_with_db: AsyncClient,
    api_key,
) -> None:
    auth, _ = api_key

    resp = await client_with_db.post(
        "/v1/optimizations?mode=sync",
        json=_large_lp_body(),
        headers={"Authorization": auth},
    )

    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body["requested_mode"] == "sync"
    assert body["auto_async"] is True
    assert body["estimated_seconds"] > 5.0


async def test_get_queued_optimization_returns_compact_owner_status(
    client_with_db: AsyncClient,
    api_key,
    second_api_key,
) -> None:
    auth, _ = api_key
    second_auth, _ = second_api_key
    created = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers={"Authorization": auth},
    )
    assert created.status_code == 202, created.text
    optimization_id = created.json()["optimization_id"]

    fetched = await client_with_db.get(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": auth},
    )
    assert fetched.status_code == 200, fetched.text
    body = fetched.json()
    assert body["optimization_id"] == optimization_id
    assert body["status"] == "queued"
    assert body["mode"] == "async"
    assert body["progress_pct"] == 0
    assert body["eta_seconds"] is None
    assert body["completed_at"] is None
    assert "solution" not in body

    cross_user = await client_with_db.get(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": second_auth},
    )
    assert cross_user.status_code == 404, cross_user.text


async def test_async_idempotency_replays_queued_row_without_duplicate(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id = api_key
    idem_key = f"3-3-async-replay-{uuid.uuid4()}"
    headers = {"Authorization": auth, "Idempotency-Key": idem_key}

    first = await client_with_db.post(
        "/v1/optimizations?mode=async", json=SMALL_LP_BODY, headers=headers
    )
    second = await client_with_db.post(
        "/v1/optimizations?mode=async", json=SMALL_LP_BODY, headers=headers
    )

    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    assert second.json()["optimization_id"] == first.json()["optimization_id"]
    assert await _idempotent_optimization_count(db_engine, user_id, idem_key) == 1


async def test_omitted_mode_and_explicit_sync_share_idempotency_hash(
    client_with_db: AsyncClient,
    api_key,
) -> None:
    auth, _ = api_key
    idem_key = f"3-3-sync-default-{uuid.uuid4()}"
    headers = {"Authorization": auth, "Idempotency-Key": idem_key}

    first = await client_with_db.post("/v1/optimizations", json=SMALL_LP_BODY, headers=headers)
    second = await client_with_db.post(
        "/v1/optimizations?mode=sync", json=SMALL_LP_BODY, headers=headers
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["optimization_id"] == first.json()["optimization_id"]


async def test_same_key_same_body_different_mode_conflicts(
    client_with_db: AsyncClient,
    api_key,
) -> None:
    auth, _ = api_key
    idem_key = f"3-3-mode-conflict-{uuid.uuid4()}"
    headers = {"Authorization": auth, "Idempotency-Key": idem_key}

    first = await client_with_db.post(
        "/v1/optimizations?mode=async", json=SMALL_LP_BODY, headers=headers
    )
    second = await client_with_db.post(
        "/v1/optimizations?mode=sync", json=SMALL_LP_BODY, headers=headers
    )

    assert first.status_code == 202, first.text
    assert second.status_code == 409, second.text
    assert second.json()["title"] == "Idempotency Conflict"


async def test_idempotency_row_pointing_to_missing_optimization_returns_409(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    idem_key = f"3-3-missing-{uuid.uuid4()}"
    optimization_id = uuid.uuid4()

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        api_key_id = (
            await s.execute(
                text("SELECT id FROM api_keys WHERE user_id = :uid LIMIT 1"),
                {"uid": user_id},
            )
        ).scalar_one()
        await s.execute(
            text(
                "INSERT INTO optimizations "
                "(id, user_id, api_key_id, task_type, status, input_payload, model_version) "
                "VALUES ("
                ":id, :uid, :api_key_id, 'lp', 'queued', "
                "CAST(:input_payload AS jsonb), CAST(:model_version AS jsonb)"
                ")"
            ),
            {
                "id": optimization_id,
                "uid": user_id,
                "api_key_id": api_key_id,
                "input_payload": json.dumps(SMALL_LP_BODY),
                "model_version": json.dumps(
                    {
                        "provider_id": "highs",
                        "kind": "open_source",
                        "version": "test",
                        "provider_url": "https://highs.dev/",
                    }
                ),
            },
        )
        await s.execute(
            text(
                "INSERT INTO idempotency_keys "
                "(user_id, key, optimization_id, request_body_hash, expires_at) "
                "VALUES (:uid, :key, :optimization_id, :body_hash, :expires_at)"
            ),
            {
                "uid": user_id,
                "key": idem_key,
                "optimization_id": optimization_id,
                "body_hash": _mode_hash(SMALL_LP_BODY, "async"),
                "expires_at": datetime.now(UTC) + timedelta(hours=24),
            },
        )
        await s.commit()

    original_get = AsyncSession.get

    async def _simulate_missing_optimization(self, entity, ident, *args, **kwargs):
        if entity is Optimization and ident == optimization_id:
            return None
        return await original_get(self, entity, ident, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "get", _simulate_missing_optimization)

    resp = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers={"Authorization": auth, "Idempotency-Key": idem_key},
    )

    assert resp.status_code == 409, resp.text
    assert resp.json()["title"] == "Idempotency Conflict"


async def test_idempotency_insert_race_returns_409_without_orphan_row(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    idem_key = f"3-3-race-{uuid.uuid4()}"
    before = await _optimization_count(db_engine, user_id)
    original_flush = AsyncSession.flush
    flush_calls = 0

    async def _raise_on_idempotency_flush(self, *args, **kwargs):
        nonlocal flush_calls
        from sqlalchemy.exc import IntegrityError

        flush_calls += 1
        if flush_calls == 2:
            raise IntegrityError("insert", {}, Exception("duplicate"))
        return await original_flush(self, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "flush", _raise_on_idempotency_flush)

    resp = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers={"Authorization": auth, "Idempotency-Key": idem_key},
    )

    assert resp.status_code == 409, resp.text
    assert resp.json()["title"] == "Idempotency Conflict"
    assert await _optimization_count(db_engine, user_id) == before


async def _optimization_count(db_engine: AsyncEngine, user_id: uuid.UUID) -> int:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        return int(
            (
                await s.execute(
                    text("SELECT COUNT(*) FROM optimizations WHERE user_id = :uid"),
                    {"uid": user_id},
                )
            ).scalar_one()
        )


async def _idempotent_optimization_count(
    db_engine: AsyncEngine,
    user_id: uuid.UUID,
    idempotency_key: str,
) -> int:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        return int(
            (
                await s.execute(
                    text(
                        "SELECT COUNT(*) FROM optimizations "
                        "WHERE user_id = :uid AND idempotency_key = :idempotency_key"
                    ),
                    {"uid": user_id, "idempotency_key": idempotency_key},
                )
            ).scalar_one()
        )


async def _optimization_row(db_engine: AsyncEngine, optimization_id: uuid.UUID) -> dict:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (
            (
                await s.execute(
                    text(
                        "SELECT status, input_payload, solution, objective, solve_seconds, "
                        "completed_at FROM optimizations WHERE id = :id"
                    ),
                    {"id": optimization_id},
                )
            )
            .mappings()
            .one()
        )
    return dict(row)


def _mode_hash(body: dict, mode: str) -> str:
    normalized = {
        **body,
        "maximize": body.get("maximize"),
        "options": {
            "anonymous": False,
            "max_solve_seconds": 30.0,
            "reproducible": False,
        },
        "solver": body.get("solver"),
        "fallback_chain": body.get("fallback_chain"),
    }
    canon = json.dumps({"body": normalized, "mode": mode}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()
