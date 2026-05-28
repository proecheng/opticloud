"""Story 3.13 - async optimization batch endpoint tests."""

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
from pytest import MonkeyPatch
from solver_orchestrator import billing_client, solvers
from solver_orchestrator.config import settings
from solver_orchestrator.db import get_session
from solver_orchestrator.main import app
from solver_orchestrator.routes import _hash_batch_body
from solver_orchestrator.schemas import OptimizationBatchRequest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
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


def _lp_tasks(count: int) -> list[dict[str, Any]]:
    return [
        {
            "task_type": "lp",
            "minimize": {"c": [1.0 + (idx / 1000.0), 1.0]},
            "st": {"A": [[1.0, 1.0]], "b": [10.0]},
        }
        for idx in range(count)
    ]


def _make_api_key(prefix: str = "t313") -> tuple[str, str, int]:
    random_part = f"{prefix}{uuid.uuid4().hex}"
    full = f"sk-{random_part}"
    pepper_version = 1
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    key_hash = hmac.new(pepper, full.encode("utf-8"), hashlib.sha256).hexdigest()
    return full, key_hash, pepper_version


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    await _ensure_batch_tables(eng)
    yield eng
    await eng.dispose()


async def _seed_api_key(
    db_engine: AsyncEngine,
    *,
    label: str,
) -> tuple[str, uuid.UUID, uuid.UUID]:
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
                "email": f"3-13-{label}-{user_id}@example.com",
                "phone": f"+867{user_id.int % 10**10:010d}",
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
                "label": f"3-13-{label}",
                "prefix": key_prefix,
                "hash": key_hash,
                "v": version,
                "now": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(days=365),
            },
        )
        await s.commit()
    return f"Bearer {full}", user_id, key_id


@pytest_asyncio.fixture(loop_scope="session")
async def api_key(db_engine: AsyncEngine) -> AsyncIterator[tuple[str, uuid.UUID, uuid.UUID]]:
    yield await _seed_api_key(db_engine, label="primary")


@pytest_asyncio.fixture(loop_scope="session")
async def second_api_key(
    db_engine: AsyncEngine,
) -> AsyncIterator[tuple[str, uuid.UUID, uuid.UUID]]:
    yield await _seed_api_key(db_engine, label="secondary")


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


async def test_batch_100_lp_tasks_creates_ordered_queued_children_without_side_effects(
    client_with_db: AsyncClient,
    api_key: tuple[str, uuid.UUID, uuid.UUID],
    db_engine: AsyncEngine,
    monkeypatch: MonkeyPatch,
) -> None:
    auth, user_id, _ = api_key
    before = await _counts(db_engine, user_id)
    calls = {"reserve": 0, "finalize": 0, "solve": 0, "cost": 0}

    async def _billing_should_not_run(*args, **kwargs):
        calls["reserve"] += 1
        raise AssertionError("batch create must not call billing")

    async def _finalize_should_not_run(*args, **kwargs):
        calls["finalize"] += 1
        raise AssertionError("batch create must not call billing")

    def _solve_should_not_run(*args, **kwargs):
        calls["solve"] += 1
        raise AssertionError("batch create must not call solver")

    async def _cost_should_not_run(*args, **kwargs):
        calls["cost"] += 1
        raise AssertionError("batch create must not record cost attribution")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _finalize_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", _solve_should_not_run)
    monkeypatch.setattr(
        "solver_orchestrator.routes._record_solver_cost_attribution",
        _cost_should_not_run,
    )

    resp = await client_with_db.post(
        "/v1/optimizations/batch",
        json={"tasks": _lp_tasks(100)},
        headers={"Authorization": auth},
    )

    assert resp.status_code == 202, resp.text
    body = resp.json()
    batch_id = uuid.UUID(body["batch_id"])
    optimization_ids = [uuid.UUID(value) for value in body["optimization_ids"]]
    assert resp.headers["location"] == f"/v1/optimizations/batch/{batch_id}"
    assert body["batch_status"] == "queued"
    assert body["task_count"] == 100
    assert len(optimization_ids) == 100
    assert [item["index"] for item in body["items"]] == list(range(100))
    assert [uuid.UUID(item["optimization_id"]) for item in body["items"]] == optimization_ids
    assert {item["status"] for item in body["items"]} == {"queued"}
    assert "_system" not in resp.text
    assert calls == {"reserve": 0, "finalize": 0, "solve": 0, "cost": 0}

    after = await _counts(db_engine, user_id)
    assert after["batches"] == before["batches"] + 1
    assert after["batch_items"] == before["batch_items"] + 100
    assert after["optimizations"] == before["optimizations"] + 100
    rows = await _batch_child_rows(db_engine, batch_id)
    assert [row["item_index"] for row in rows] == list(range(100))
    assert [row["optimization_id"] for row in rows] == optimization_ids
    assert all(row["status"] == "queued" for row in rows)
    first_payload = rows[0]["input_payload"]
    assert first_payload["_system"]["execution_mode"] == {
        "requested_mode": "async",
        "effective_mode": "async",
        "auto_async": False,
        "estimated_seconds": pytest.approx(0.0506),
        "threshold_seconds": 5.0,
    }
    assert first_payload["_system"]["provider_route"]["provider_id"] == "highs"
    assert first_payload["_system"]["batch"] == {
        "batch_id": str(batch_id),
        "item_index": 0,
        "task_count": 100,
    }


@pytest.mark.parametrize(
    ("path", "payload", "expected_status", "field_path"),
    [
        ("/v1/optimizations/batch", {"tasks": []}, 422, "tasks"),
        ("/v1/optimizations/batch", {"tasks": _lp_tasks(101)}, 422, "tasks"),
        (
            "/v1/optimizations/batch",
            {"tasks": [{**SMALL_LP_BODY, "task_type": "milp"}]},
            422,
            "tasks[0].task_type",
        ),
        (
            "/v1/optimizations/batch",
            {"tasks": [{**SMALL_LP_BODY, "fallback_chain": ["not-a-solver"]}]},
            400,
            "tasks[0].fallback_chain[0]",
        ),
        (
            "/v1/optimizations/batch",
            {"tasks": [{**SMALL_LP_BODY, "options": {"anonymous": True}}]},
            422,
            "tasks[0].options.anonymous",
        ),
        ("/v1/optimizations/batch?mode=sync", {"tasks": _lp_tasks(1)}, 422, "query.mode"),
    ],
)
async def test_batch_validation_failures_are_side_effect_free(
    client_with_db: AsyncClient,
    api_key: tuple[str, uuid.UUID, uuid.UUID],
    db_engine: AsyncEngine,
    path: str,
    payload: dict[str, Any],
    expected_status: int,
    field_path: str,
    monkeypatch: MonkeyPatch,
) -> None:
    auth, user_id, _ = api_key
    before = await _counts(db_engine, user_id)

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("billing should not run for invalid batch")

    def _solver_should_not_run(*args, **kwargs):
        raise AssertionError("solver should not run for invalid batch")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", _solver_should_not_run)

    resp = await client_with_db.post(path, json=payload, headers={"Authorization": auth})

    assert resp.status_code == expected_status, resp.text
    assert resp.json()["errors"][0]["field_path"] == field_path
    assert await _counts(db_engine, user_id) == before


async def test_batch_billing_header_is_rejected_side_effect_free(
    client_with_db: AsyncClient,
    api_key: tuple[str, uuid.UUID, uuid.UUID],
    db_engine: AsyncEngine,
    monkeypatch: MonkeyPatch,
) -> None:
    auth, user_id, _ = api_key
    before = await _counts(db_engine, user_id)

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("batch must reject billing before billing calls")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)

    resp = await client_with_db.post(
        "/v1/optimizations/batch",
        json={"tasks": _lp_tasks(1)},
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(uuid.uuid4())},
    )

    assert resp.status_code == 422, resp.text
    assert resp.json()["errors"][0]["field_path"] == "header.X-Billing-Charge-Id"
    assert await _counts(db_engine, user_id) == before


async def test_batch_idempotency_replays_same_body_and_conflicts_on_order_change(
    client_with_db: AsyncClient,
    api_key: tuple[str, uuid.UUID, uuid.UUID],
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, _ = api_key
    idem_key = f"batch-replay-{uuid.uuid4()}"
    headers = {"Authorization": auth, "Idempotency-Key": idem_key}
    body = {"tasks": _lp_tasks(3)}
    before = await _counts(db_engine, user_id)

    first = await client_with_db.post("/v1/optimizations/batch", json=body, headers=headers)
    second = await client_with_db.post("/v1/optimizations/batch", json=body, headers=headers)
    changed_order = {
        "tasks": [
            body["tasks"][1],
            body["tasks"][0],
            body["tasks"][2],
        ]
    }
    conflict = await client_with_db.post(
        "/v1/optimizations/batch", json=changed_order, headers=headers
    )

    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    assert second.json()["batch_id"] == first.json()["batch_id"]
    assert second.json()["optimization_ids"] == first.json()["optimization_ids"]
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["title"] == "Idempotency Conflict"
    after = await _counts(db_engine, user_id)
    assert after["batches"] == before["batches"] + 1
    assert after["batch_items"] == before["batch_items"] + 3
    assert after["optimizations"] == before["optimizations"] + 3
    assert await _batch_idempotency_count(db_engine, user_id, idem_key) == 1


async def test_batch_idempotency_insert_race_replays_same_body_without_orphan_rows(
    client_with_db: AsyncClient,
    api_key: tuple[str, uuid.UUID, uuid.UUID],
    db_engine: AsyncEngine,
    monkeypatch: MonkeyPatch,
) -> None:
    auth, user_id, api_key_id = api_key
    idem_key = f"batch-race-{uuid.uuid4()}"
    body = {"tasks": _lp_tasks(1)}
    before = await _counts(db_engine, user_id)
    seeded_batch_id: uuid.UUID | None = None
    seeded_optimization_ids: list[uuid.UUID] = []
    original_flush = AsyncSession.flush
    flush_calls = 0

    async def _raise_after_competing_idempotency_insert(self, *args, **kwargs):
        nonlocal flush_calls, seeded_batch_id, seeded_optimization_ids
        flush_calls += 1
        if flush_calls == 3:
            seeded_batch_id, seeded_optimization_ids = await _seed_batch_idempotency_replay(
                db_engine,
                user_id=user_id,
                api_key_id=api_key_id,
                idem_key=idem_key,
                body=body,
            )
            raise IntegrityError("insert", {}, Exception("duplicate"))
        return await original_flush(self, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "flush", _raise_after_competing_idempotency_insert)

    resp = await client_with_db.post(
        "/v1/optimizations/batch",
        json=body,
        headers={"Authorization": auth, "Idempotency-Key": idem_key},
    )

    assert resp.status_code == 202, resp.text
    assert resp.json()["batch_id"] == str(seeded_batch_id)
    assert resp.json()["optimization_ids"] == [str(value) for value in seeded_optimization_ids]
    after = await _counts(db_engine, user_id)
    assert after["batches"] == before["batches"] + 1
    assert after["batch_items"] == before["batch_items"] + 1
    assert after["optimizations"] == before["optimizations"] + 1
    assert await _batch_idempotency_count(db_engine, user_id, idem_key) == 1


async def test_batch_get_aggregates_status_progress_errors_and_preserves_order(
    client_with_db: AsyncClient,
    api_key: tuple[str, uuid.UUID, uuid.UUID],
    db_engine: AsyncEngine,
) -> None:
    auth, _, _ = api_key
    created = await client_with_db.post(
        "/v1/optimizations/batch",
        json={"tasks": _lp_tasks(6)},
        headers={"Authorization": auth},
    )
    assert created.status_code == 202, created.text
    batch_id = uuid.UUID(created.json()["batch_id"])
    optimization_ids = [uuid.UUID(value) for value in created.json()["optimization_ids"]]
    completed_at = datetime.now(UTC) - timedelta(minutes=3)
    failed_at = datetime.now(UTC) - timedelta(minutes=2)
    timeout_at = datetime.now(UTC) - timedelta(minutes=1)
    cancelled_at = datetime.now(UTC)

    await _set_child_status(
        db_engine,
        optimization_ids[0],
        status="queued",
        progress_pct=0,
    )
    await _set_child_status(
        db_engine,
        optimization_ids[1],
        status="in_progress",
        progress_pct=45.8,
        eta_seconds=23.9,
    )
    await _set_child_status(
        db_engine,
        optimization_ids[2],
        status="completed",
        solution={"x": [0.0, 10.0]},
        objective=10,
        solve_seconds=0.25,
        completed_at=completed_at,
    )
    await _set_child_status(
        db_engine,
        optimization_ids[3],
        status="failed",
        error={"title": "Solver Result", "detail": "infeasible"},
        completed_at=failed_at,
    )
    timeout_charge_id = uuid.uuid4()
    await _set_child_status(
        db_engine,
        optimization_ids[4],
        status="timeout",
        progress_pct=98,
        error={"title": "Solver Timeout", "billing_charge_id": str(timeout_charge_id)},
        solve_seconds=30,
        completed_at=timeout_at,
    )
    await _set_child_status(
        db_engine,
        optimization_ids[5],
        status="cancelled",
        error={"title": "Optimization Cancelled", "detail": "cancelled by user"},
        completed_at=cancelled_at,
    )

    active = await client_with_db.get(
        f"/v1/optimizations/batch/{batch_id}",
        headers={"Authorization": auth},
    )

    assert active.status_code == 200, active.text
    body = active.json()
    assert body["batch_id"] == str(batch_id)
    assert body["batch_status"] == "in_progress"
    assert body["task_count"] == 6
    assert body["counts"] == {
        "queued": 1,
        "in_progress": 1,
        "completed": 1,
        "failed": 1,
        "timeout": 1,
        "cancelled": 1,
    }
    assert body["progress_pct"] == 40
    assert body["eta_seconds"] == 23
    assert body["completed_at"] is None
    assert body["optimization_ids"] == [str(value) for value in optimization_ids]
    assert [item["index"] for item in body["items"]] == list(range(6))
    assert [item["optimization_id"] for item in body["items"]] == [
        str(value) for value in optimization_ids
    ]
    assert body["items"][2]["solution"] == {"x": [0.0, 10.0]}
    assert [error["index"] for error in body["errors"]] == [3, 4, 5]
    assert body["errors"][1]["error"]["billing_charge_id"] == "[redacted]"
    assert "_system" not in active.text
    assert str(timeout_charge_id) not in active.text

    await _set_child_status(
        db_engine,
        optimization_ids[0],
        status="completed",
        completed_at=failed_at,
    )
    await _set_child_status(
        db_engine,
        optimization_ids[1],
        status="failed",
        completed_at=timeout_at,
    )

    terminal = await client_with_db.get(
        f"/v1/optimizations/batch/{batch_id}",
        headers={"Authorization": auth},
    )

    assert terminal.status_code == 200, terminal.text
    terminal_body = terminal.json()
    assert terminal_body["batch_status"] == "partial_failed"
    assert terminal_body["eta_seconds"] is None
    assert terminal_body["completed_at"] == cancelled_at.isoformat()


async def test_batch_progress_caps_at_99_unless_all_children_completed(
    client_with_db: AsyncClient,
    api_key: tuple[str, uuid.UUID, uuid.UUID],
    db_engine: AsyncEngine,
) -> None:
    auth, _, _ = api_key
    created = await client_with_db.post(
        "/v1/optimizations/batch",
        json={"tasks": _lp_tasks(2)},
        headers={"Authorization": auth},
    )
    assert created.status_code == 202, created.text
    batch_id = uuid.UUID(created.json()["batch_id"])
    optimization_ids = [uuid.UUID(value) for value in created.json()["optimization_ids"]]

    await _set_child_status(
        db_engine,
        optimization_ids[0],
        status="completed",
        solution={"x": [10.0, 0.0]},
        objective=10,
        solve_seconds=0.2,
        completed_at=datetime.now(UTC),
    )
    await _set_child_status(
        db_engine,
        optimization_ids[1],
        status="failed",
        progress_pct=100,
        error={"title": "Solver Result", "detail": "failed after full worker progress"},
        completed_at=datetime.now(UTC),
    )

    fetched = await client_with_db.get(
        f"/v1/optimizations/batch/{batch_id}",
        headers={"Authorization": auth},
    )

    assert fetched.status_code == 200, fetched.text
    body = fetched.json()
    assert body["batch_status"] == "partial_failed"
    assert body["progress_pct"] == 99


async def test_batch_get_cross_tenant_404_no_leak_and_child_get_still_works(
    client_with_db: AsyncClient,
    api_key: tuple[str, uuid.UUID, uuid.UUID],
    second_api_key: tuple[str, uuid.UUID, uuid.UUID],
) -> None:
    auth, _, _ = api_key
    second_auth, _, _ = second_api_key
    created = await client_with_db.post(
        "/v1/optimizations/batch",
        json={"tasks": _lp_tasks(1)},
        headers={"Authorization": auth},
    )
    assert created.status_code == 202, created.text
    batch_id = created.json()["batch_id"]
    optimization_id = created.json()["optimization_ids"][0]

    cross_batch = await client_with_db.get(
        f"/v1/optimizations/batch/{batch_id}",
        headers={"Authorization": second_auth},
    )
    child_owner = await client_with_db.get(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": auth},
    )
    child_cross = await client_with_db.get(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": second_auth},
    )

    assert cross_batch.status_code == 404, cross_batch.text
    assert batch_id not in cross_batch.text
    assert optimization_id not in cross_batch.text
    assert "task_count" not in cross_batch.text
    assert child_owner.status_code == 200, child_owner.text
    assert child_owner.json()["optimization_id"] == optimization_id
    assert child_owner.json()["status"] == "queued"
    assert child_cross.status_code == 404, child_cross.text


async def _ensure_batch_tables(db_engine: AsyncEngine) -> None:
    async with db_engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS optimization_batches (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL,
                    api_key_id UUID NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS optimization_batch_items (
                    batch_id UUID NOT NULL REFERENCES optimization_batches(id) ON DELETE CASCADE,
                    item_index INTEGER NOT NULL,
                    optimization_id UUID NOT NULL UNIQUE REFERENCES optimizations(id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (batch_id, item_index)
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS optimization_batch_idempotency_keys (
                    user_id UUID NOT NULL,
                    key VARCHAR(255) NOT NULL,
                    batch_id UUID NOT NULL REFERENCES optimization_batches(id) ON DELETE CASCADE,
                    request_body_hash TEXT NOT NULL,
                    expires_at TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (user_id, key)
                )
                """
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_optimization_batches_user_id_created_at "
                "ON optimization_batches(user_id, created_at DESC)"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_optimization_batch_items_batch_id_item_index "
                "ON optimization_batch_items(batch_id, item_index)"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_optimization_batch_idempotency_keys_expires_at "
                "ON optimization_batch_idempotency_keys(expires_at)"
            )
        )


async def _counts(db_engine: AsyncEngine, user_id: uuid.UUID) -> dict[str, int]:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        return {
            "batches": int(
                (
                    await s.execute(
                        text("SELECT COUNT(*) FROM optimization_batches WHERE user_id = :uid"),
                        {"uid": user_id},
                    )
                ).scalar_one()
            ),
            "batch_items": int(
                (
                    await s.execute(
                        text(
                            "SELECT COUNT(*) FROM optimization_batch_items bi "
                            "JOIN optimization_batches b ON b.id = bi.batch_id "
                            "WHERE b.user_id = :uid"
                        ),
                        {"uid": user_id},
                    )
                ).scalar_one()
            ),
            "optimizations": int(
                (
                    await s.execute(
                        text("SELECT COUNT(*) FROM optimizations WHERE user_id = :uid"),
                        {"uid": user_id},
                    )
                ).scalar_one()
            ),
        }


async def _batch_child_rows(db_engine: AsyncEngine, batch_id: uuid.UUID) -> list[dict[str, Any]]:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        rows = (
            (
                await s.execute(
                    text(
                        "SELECT bi.item_index, bi.optimization_id, o.status, o.input_payload "
                        "FROM optimization_batch_items bi "
                        "JOIN optimizations o ON o.id = bi.optimization_id "
                        "WHERE bi.batch_id = :batch_id "
                        "ORDER BY bi.item_index ASC"
                    ),
                    {"batch_id": batch_id},
                )
            )
            .mappings()
            .all()
        )
    return [dict(row) for row in rows]


async def _batch_idempotency_count(
    db_engine: AsyncEngine,
    user_id: uuid.UUID,
    idem_key: str,
) -> int:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        return int(
            (
                await s.execute(
                    text(
                        "SELECT COUNT(*) FROM optimization_batch_idempotency_keys "
                        "WHERE user_id = :uid AND key = :key"
                    ),
                    {"uid": user_id, "key": idem_key},
                )
            ).scalar_one()
        )


async def _seed_batch_idempotency_replay(
    db_engine: AsyncEngine,
    *,
    user_id: uuid.UUID,
    api_key_id: uuid.UUID,
    idem_key: str,
    body: dict[str, Any],
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    batch_id = uuid.uuid4()
    optimization_id = uuid.uuid4()
    normalized_body = OptimizationBatchRequest.model_validate(body).model_dump(by_alias=True)
    body_hash = _hash_batch_body(normalized_body)
    task_body = normalized_body["tasks"][0]
    payload = {
        **task_body,
        "_system": {
            "execution_mode": {
                "requested_mode": "async",
                "effective_mode": "async",
                "auto_async": False,
                "estimated_seconds": 0.0506,
                "threshold_seconds": 5.0,
            },
            "provider_route": {
                "task_type": "lp",
                "requested_solver": None,
                "selected_solver": "highs",
                "provider_id": "highs",
                "provider_kind": "open_source",
                "provider_url": "https://highs.dev/",
                "routing_reason": "default_solver",
            },
            "batch": {
                "batch_id": str(batch_id),
                "item_index": 0,
                "task_count": 1,
            },
        },
    }
    model_version = {
        "provider_id": "highs",
        "kind": "open_source",
        "version": "1.7.0",
        "provider_url": "https://highs.dev/",
    }
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO optimization_batches(id, user_id, api_key_id) "
                "VALUES (:id, :uid, :api_key_id)"
            ),
            {"id": batch_id, "uid": user_id, "api_key_id": api_key_id},
        )
        await s.execute(
            text(
                "INSERT INTO optimizations "
                "(id, user_id, api_key_id, task_type, status, input_payload, model_version) "
                "VALUES (:id, :uid, :api_key_id, 'lp', 'queued', "
                "CAST(:input_payload AS jsonb), CAST(:model_version AS jsonb))"
            ),
            {
                "id": optimization_id,
                "uid": user_id,
                "api_key_id": api_key_id,
                "input_payload": json.dumps(payload),
                "model_version": json.dumps(model_version),
            },
        )
        await s.execute(
            text(
                "INSERT INTO optimization_batch_items(batch_id, item_index, optimization_id) "
                "VALUES (:batch_id, 0, :optimization_id)"
            ),
            {"batch_id": batch_id, "optimization_id": optimization_id},
        )
        await s.execute(
            text(
                "INSERT INTO optimization_batch_idempotency_keys "
                "(user_id, key, batch_id, request_body_hash, expires_at) "
                "VALUES (:uid, :key, :batch_id, :body_hash, :expires_at)"
            ),
            {
                "uid": user_id,
                "key": idem_key,
                "batch_id": batch_id,
                "body_hash": body_hash,
                "expires_at": datetime.now(UTC) + timedelta(hours=24),
            },
        )
        await s.commit()
    return batch_id, [optimization_id]


async def _set_child_status(
    db_engine: AsyncEngine,
    optimization_id: uuid.UUID,
    *,
    status: str,
    progress_pct: float | None = None,
    eta_seconds: float | None = None,
    solution: dict[str, Any] | None = None,
    objective: float | None = None,
    solve_seconds: float | None = None,
    error: dict[str, Any] | None = None,
    completed_at: datetime | None = None,
) -> None:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (
            await s.execute(
                text("SELECT input_payload FROM optimizations WHERE id = :id"),
                {"id": optimization_id},
            )
        ).scalar_one()
        payload = dict(row)
        system = dict(payload.get("_system") or {})
        if progress_pct is not None or eta_seconds is not None:
            system["progress"] = {
                "progress_pct": progress_pct,
                "eta_seconds": eta_seconds,
                "debug": {"secret": "do-not-leak"},
            }
        payload["_system"] = system
        await s.execute(
            text(
                "UPDATE optimizations "
                "SET status = :status, input_payload = CAST(:payload AS jsonb), "
                "solution = CAST(:solution AS jsonb), objective = :objective, "
                "solve_seconds = :solve_seconds, error = CAST(:error AS jsonb), "
                "completed_at = :completed_at "
                "WHERE id = :id"
            ),
            {
                "id": optimization_id,
                "status": status,
                "payload": json.dumps(payload),
                "solution": json.dumps(solution) if solution is not None else None,
                "objective": objective,
                "solve_seconds": solve_seconds,
                "error": json.dumps(error) if error is not None else None,
                "completed_at": completed_at,
            },
        )
        await s.commit()
