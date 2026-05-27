"""Story 3.9 - optimization status/progress/ETA contract tests."""

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

SMALL_LP_BODY = {
    "task_type": "lp",
    "minimize": {"c": [1.0, 1.0]},
    "st": {"A": [[1.0, 1.0]], "b": [10.0]},
}

MODEL_VERSION = {
    "provider_id": "highs",
    "kind": "open_source",
    "version": "test",
    "provider_url": "https://highs.dev/",
}


def _make_api_key(prefix: str = "t39") -> tuple[str, str, int]:
    random_part = f"{prefix}{uuid.uuid4().hex}"
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
                "email": f"3-9-{label}-{user_id}@example.com",
                "phone": f"+866{user_id.int % 10**10:010d}",
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
                "label": f"3-9-{label}",
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
async def second_api_key(db_engine: AsyncEngine) -> AsyncIterator[tuple[str, uuid.UUID, uuid.UUID]]:
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


async def test_get_queued_status_includes_default_progress_eta_and_model_version(
    client_with_db: AsyncClient,
    api_key,
) -> None:
    auth, _, _ = api_key
    created = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers={"Authorization": auth},
    )
    assert created.status_code == 202, created.text

    fetched = await client_with_db.get(
        f"/v1/optimizations/{created.json()['optimization_id']}",
        headers={"Authorization": auth},
    )

    assert fetched.status_code == 200, fetched.text
    body = fetched.json()
    assert body["status"] == "queued"
    assert body["progress_pct"] == 0
    assert body["eta_seconds"] is None
    assert body["mode"] == "async"
    assert body["completed_at"] is None
    assert set(body["model_version"]) == {"provider_id", "kind", "version", "provider_url"}
    assert body["model_version"]["kind"] == "open_source"
    assert "provider_kind" not in body["model_version"]
    assert "_system" not in fetched.text


async def test_get_in_progress_status_reads_normalized_progress_metadata(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    optimization_id = await _insert_optimization(
        db_engine,
        user_id=user_id,
        api_key_id=api_key_id,
        status="in_progress",
        input_payload={
            **SMALL_LP_BODY,
            "_system": {
                "execution_mode": {"effective_mode": "async"},
                "progress": {"progress_pct": 45.8, "eta_seconds": 23.9, "source": "worker"},
            },
        },
    )

    fetched = await client_with_db.get(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": auth},
    )

    assert fetched.status_code == 200, fetched.text
    body = fetched.json()
    assert body["status"] == "in_progress"
    assert body["progress_pct"] == 45
    assert body["eta_seconds"] == 23
    assert body["model_version"]["provider_url"] == "https://highs.dev/"
    assert "worker" not in fetched.text
    assert "_system" not in fetched.text


async def test_get_status_handles_invalid_progress_metadata_without_leaking_system(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    optimization_id = await _insert_optimization(
        db_engine,
        user_id=user_id,
        api_key_id=api_key_id,
        status="in_progress",
        input_payload={
            **SMALL_LP_BODY,
            "_system": {
                "execution_mode": {"effective_mode": "async"},
                "progress": {
                    "progress_pct": 150,
                    "eta_seconds": -10,
                    "debug": {"secret": "do-not-leak"},
                },
            },
        },
    )

    fetched = await client_with_db.get(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": auth},
    )

    assert fetched.status_code == 200, fetched.text
    body = fetched.json()
    assert body["progress_pct"] == 99
    assert body["eta_seconds"] is None
    assert "do-not-leak" not in fetched.text
    assert "_system" not in fetched.text


async def test_completed_get_preserves_success_body_and_adds_progress_closure(
    client_with_db: AsyncClient,
    api_key,
) -> None:
    auth, _, _ = api_key
    created = await client_with_db.post(
        "/v1/optimizations",
        json=SMALL_LP_BODY,
        headers={"Authorization": auth},
    )
    assert created.status_code == 200, created.text

    fetched = await client_with_db.get(
        f"/v1/optimizations/{created.json()['optimization_id']}",
        headers={"Authorization": auth},
    )

    assert fetched.status_code == 200, fetched.text
    body = fetched.json()
    assert body["status"] == "completed"
    assert body["progress_pct"] == 100
    assert body["eta_seconds"] == 0
    assert "solution" in body
    assert "objective" in body
    assert set(body["model_version"]) == {"provider_id", "kind", "version", "provider_url"}


async def test_get_status_tolerates_historical_malformed_model_version(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    optimization_id = await _insert_optimization(
        db_engine,
        user_id=user_id,
        api_key_id=api_key_id,
        status="completed",
        input_payload=SMALL_LP_BODY,
        model_version={"provider_id": "legacy-without-url"},
    )

    fetched = await client_with_db.get(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": auth},
    )

    assert fetched.status_code == 200, fetched.text
    body = fetched.json()
    assert body["status"] == "completed"
    assert body["model_version"] is None
    assert body["progress_pct"] == 100
    assert body["eta_seconds"] == 0


async def test_get_status_tolerates_historical_invalid_model_version_kind(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    optimization_id = await _insert_optimization(
        db_engine,
        user_id=user_id,
        api_key_id=api_key_id,
        status="completed",
        input_payload=SMALL_LP_BODY,
        model_version={
            "provider_id": "legacy",
            "kind": "provider_kind_alias",
            "version": "legacy",
            "provider_url": "https://legacy.example.com/",
        },
    )

    fetched = await client_with_db.get(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": auth},
    )

    assert fetched.status_code == 200, fetched.text
    body = fetched.json()
    assert body["model_version"] is None
    assert body["progress_pct"] == 100
    assert body["eta_seconds"] == 0


async def test_failed_timeout_and_cancelled_statuses_include_terminal_progress_contract(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    failed_id = await _insert_optimization(
        db_engine,
        user_id=user_id,
        api_key_id=api_key_id,
        status="failed",
        input_payload={
            **SMALL_LP_BODY,
            "_system": {"progress": {"progress_pct": 72, "eta_seconds": 99}},
        },
        error={"title": "Solver Error", "detail": "failed"},
    )
    timeout_id = await _insert_optimization(
        db_engine,
        user_id=user_id,
        api_key_id=api_key_id,
        status="timeout",
        input_payload={
            **SMALL_LP_BODY,
            "_system": {"progress": {"progress_pct": 88, "eta_seconds": 42}},
        },
        error={"title": "Solver Timeout", "detail": "timeout"},
        solve_seconds=30.0,
    )
    cancelled_id = await _insert_optimization(
        db_engine,
        user_id=user_id,
        api_key_id=api_key_id,
        status="cancelled",
        input_payload={**SMALL_LP_BODY, "_system": {"execution_mode": {"effective_mode": "async"}}},
        error={"title": "Optimization Cancelled", "detail": "cancelled by user request"},
    )

    for optimization_id, expected_status, expected_progress in (
        (failed_id, "failed", 72),
        (timeout_id, "timeout", 88),
        (cancelled_id, "cancelled", 0),
    ):
        fetched = await client_with_db.get(
            f"/v1/optimizations/{optimization_id}",
            headers={"Authorization": auth},
        )
        assert fetched.status_code == 200, fetched.text
        body = fetched.json()
        assert body["status"] == expected_status
        assert body["progress_pct"] == expected_progress
        assert body["eta_seconds"] is None
        assert body["model_version"]["kind"] == "open_source"


async def test_cross_tenant_status_404_does_not_leak_progress_or_billing(
    client_with_db: AsyncClient,
    api_key,
    second_api_key,
    db_engine: AsyncEngine,
) -> None:
    _auth, user_id, api_key_id = api_key
    second_auth, _, _ = second_api_key
    charge_id = str(uuid.uuid4())
    optimization_id = await _insert_optimization(
        db_engine,
        user_id=user_id,
        api_key_id=api_key_id,
        status="in_progress",
        input_payload={
            **SMALL_LP_BODY,
            "_system": {
                "progress": {"progress_pct": 61, "eta_seconds": 12},
                "billing": {"charge_id": charge_id, "reserved": True},
            },
        },
    )

    fetched = await client_with_db.get(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": second_auth},
    )

    assert fetched.status_code == 404, fetched.text
    assert fetched.headers["content-type"].startswith("application/problem+json")
    assert "in_progress" not in fetched.text
    assert "progress_pct" not in fetched.text
    assert charge_id not in fetched.text


async def test_get_status_does_not_trigger_post_delete_side_effects(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _, _ = api_key
    created = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=SMALL_LP_BODY,
        headers={"Authorization": auth},
    )
    assert created.status_code == 202, created.text

    async def _should_not_run(*args, **kwargs):
        raise AssertionError("GET status must not call this side-effect helper")

    def _solver_should_not_run(*args, **kwargs):
        raise AssertionError("GET status must not call solver")

    monkeypatch.setattr(billing_client, "reserve", _should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", _solver_should_not_run)
    monkeypatch.setattr(
        "solver_orchestrator.routes._record_solver_cost_attribution",
        _should_not_run,
    )
    monkeypatch.setattr("solver_orchestrator.routes.issue_reproduction_voucher", _should_not_run)

    fetched = await client_with_db.get(
        f"/v1/optimizations/{created.json()['optimization_id']}",
        headers={"Authorization": auth},
    )

    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["status"] == "queued"


async def _insert_optimization(
    db_engine: AsyncEngine,
    *,
    user_id: uuid.UUID,
    api_key_id: uuid.UUID,
    status: str,
    input_payload: dict,
    model_version: dict | None = None,
    error: dict | None = None,
    solve_seconds: float | None = None,
) -> uuid.UUID:
    optimization_id = uuid.uuid4()
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO optimizations "
                "(id, user_id, api_key_id, task_type, status, input_payload, "
                "model_version, error, solve_seconds) "
                "VALUES ("
                ":id, :uid, :api_key_id, 'lp', :status, "
                "CAST(:input_payload AS jsonb), CAST(:model_version AS jsonb), "
                "CAST(:error AS jsonb), :solve_seconds"
                ")"
            ),
            {
                "id": optimization_id,
                "uid": user_id,
                "api_key_id": api_key_id,
                "status": status,
                "input_payload": json.dumps(input_payload),
                "model_version": json.dumps(model_version or MODEL_VERSION),
                "error": json.dumps(error) if error is not None else None,
                "solve_seconds": solve_seconds,
            },
        )
        await s.commit()
    return optimization_id
