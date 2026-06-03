"""Story 8.C.2 - public-safe provider routing history tests."""

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
from solver_orchestrator.billing_client import BillingResult
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

_LP_BODY = {
    "task_type": "lp",
    "minimize": {"c": [1.0, 1.0]},
    "st": {"A": [[1.0, 1.0]], "b": [10.0]},
}


def _make_api_key() -> tuple[str, str, int]:
    random_part = f"t8c2{uuid.uuid4().hex}"
    full = f"sk-{random_part}"
    pepper_version = 1
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    key_hash = hmac.new(pepper, full.encode("utf-8"), hashlib.sha256).hexdigest()
    return full, key_hash, pepper_version


def _result(
    status: str,
    *,
    solve_seconds: float,
    objective: float | None = None,
    solution: dict[str, list[float]] | None = None,
    error_constraint: str | None = None,
) -> solvers.LPSolveResult:
    return solvers.LPSolveResult(
        status=status,
        objective=objective,
        solution=solution,
        solve_seconds=solve_seconds,
        error_field_path="options.max_solve_seconds" if status == "timeout" else None,
        error_constraint=error_constraint or status,
    )


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def api_key(db_engine: AsyncEngine) -> AsyncIterator[tuple[str, uuid.UUID, uuid.UUID]]:
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
                "email": f"8-c-2-{user_id}@example.com",
                "phone": f"+865{user_id.int % 10**10:010d}",
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
                "label": "8-c-2-test",
                "prefix": key_prefix,
                "hash": key_hash,
                "v": version,
                "now": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(days=365),
            },
        )
        await s.commit()

    yield (f"Bearer {full}", user_id, key_id)


@pytest_asyncio.fixture(loop_scope="session")
async def client_with_db(db_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            try:
                yield session
            finally:
                try:
                    await session.commit()
                except Exception:
                    await session.rollback()

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
    app.dependency_overrides.clear()


def _assert_public_history_is_safe(history: dict[str, Any]) -> None:
    serialized = json.dumps(history, sort_keys=True)
    forbidden = [
        "error_constraint",
        "error_field_path",
        "billing_charge_id",
        "Authorization",
        "api_key",
        "key_hash",
        "stack",
        "_system",
    ]
    for token in forbidden:
        assert token not in serialized


async def test_completed_fallback_success_exposes_safe_routing_history_and_replay_parity(
    client_with_db: AsyncClient,
    api_key: tuple[str, uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth, _user_id, _key_id = api_key
    results = [
        _result("timeout", solve_seconds=0.125, error_constraint="raw timeout detail"),
        _result("optimal", solve_seconds=0.25, objective=10.0, solution={"x": [0.0, 10.0]}),
    ]

    async def _billing_should_not_run(*args: object, **kwargs: object) -> BillingResult:
        raise AssertionError("billing should not run")

    def _solve(payload: dict[str, Any], *, max_solve_seconds: float = 30.0):
        return results.pop(0)

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", _solve)

    headers = {"Authorization": auth, "Idempotency-Key": "8-c-2-routing-success"}
    first = await client_with_db.post(
        "/v1/optimizations",
        json={**_LP_BODY, "fallback_chain": ["highs"]},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    body = first.json()
    history = body["routing_history"]
    _assert_public_history_is_safe(history)
    assert history["summary"] == {
        "attempt_count": 2,
        "fallback_used": True,
        "terminal_status": "optimal",
        "terminal_attempt": 2,
        "exhausted": False,
        "solve_seconds": pytest.approx(0.375),
    }
    assert history["primary_route"]["provider_id"] == "highs"
    assert history["executed_route"]["provider_id"] == "highs"
    assert [attempt["role"] for attempt in history["attempts"]] == ["primary", "fallback"]
    assert [attempt["status"] for attempt in history["attempts"]] == ["timeout", "optimal"]

    get_resp = await client_with_db.get(
        f"/v1/optimizations/{body['optimization_id']}",
        headers={"Authorization": auth},
    )
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["routing_history"] == history

    replay = await client_with_db.post(
        "/v1/optimizations",
        json={**_LP_BODY, "fallback_chain": ["highs"]},
        headers=headers,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["routing_history"] == history


async def test_async_queued_response_exposes_planned_primary_route_only(
    client_with_db: AsyncClient,
    api_key: tuple[str, uuid.UUID, uuid.UUID],
) -> None:
    auth, _user_id, _key_id = api_key
    resp = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=_LP_BODY,
        headers={"Authorization": auth},
    )

    assert resp.status_code == 202, resp.text
    history = resp.json()["routing_history"]
    assert history["primary_route"]["provider_id"] == "highs"
    assert history["executed_route"] is None
    assert history["attempts"] == []
    assert history["summary"] == {
        "attempt_count": 0,
        "fallback_used": False,
        "terminal_status": None,
        "terminal_attempt": None,
        "exhausted": False,
        "solve_seconds": 0.0,
    }


async def test_timeout_status_response_exposes_safe_history_without_raw_diagnostics(
    client_with_db: AsyncClient,
    api_key: tuple[str, uuid.UUID, uuid.UUID],
    db_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth, user_id, _key_id = api_key

    def _solve(payload: dict[str, Any], *, max_solve_seconds: float = 30.0):
        return _result(
            "timeout",
            solve_seconds=0.125,
            error_constraint="raw provider timeout diagnostics",
        )

    monkeypatch.setattr(solvers, "solve_from_request", _solve)
    resp = await client_with_db.post(
        "/v1/optimizations",
        json={**_LP_BODY, "fallback_chain": ["highs"]},
        headers={"Authorization": auth},
    )
    assert resp.status_code == 504, resp.text

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        opt_id = (
            await s.execute(
                text(
                    "SELECT id FROM optimizations "
                    "WHERE user_id = :uid ORDER BY created_at DESC LIMIT 1"
                ),
                {"uid": user_id},
            )
        ).scalar_one()

    get_resp = await client_with_db.get(
        f"/v1/optimizations/{opt_id}",
        headers={"Authorization": auth},
    )
    assert get_resp.status_code == 200, get_resp.text
    history = get_resp.json()["routing_history"]
    _assert_public_history_is_safe(history)
    assert history["summary"]["terminal_status"] == "timeout"
    assert history["summary"]["exhausted"] is True
    assert [attempt["status"] for attempt in history["attempts"]] == ["timeout", "timeout"]


async def test_historical_provider_route_without_fallback_metadata_has_single_attempt_history(
    client_with_db: AsyncClient,
    api_key: tuple[str, uuid.UUID, uuid.UUID],
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, key_id = api_key
    opt_id = uuid.uuid4()
    payload = {
        **_LP_BODY,
        "_system": {
            "provider_route": {
                "task_type": "lp",
                "requested_solver": None,
                "selected_solver": "highs",
                "provider_id": "highs",
                "provider_kind": "open_source",
                "provider_url": "https://highs.dev/",
                "routing_reason": "default_solver",
            }
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
                "INSERT INTO optimizations "
                "(id, user_id, api_key_id, task_type, status, input_payload, model_version, "
                "solution, objective, solve_seconds, completed_at) "
                "VALUES (:id, :uid, :key_id, 'lp', 'completed', CAST(:payload AS jsonb), "
                "CAST(:model_version AS jsonb), CAST(:solution AS jsonb), 10.0, 0.25, :done_at)"
            ),
            {
                "id": opt_id,
                "uid": user_id,
                "key_id": key_id,
                "payload": json.dumps(payload),
                "model_version": json.dumps(model_version),
                "solution": json.dumps({"x": [0.0, 10.0]}),
                "done_at": datetime.now(UTC),
            },
        )
        await s.commit()

    resp = await client_with_db.get(f"/v1/optimizations/{opt_id}", headers={"Authorization": auth})
    assert resp.status_code == 200, resp.text
    history = resp.json()["routing_history"]
    assert history["summary"]["attempt_count"] == 1
    assert history["summary"]["fallback_used"] is False
    assert history["attempts"][0]["role"] == "primary"
    assert history["attempts"][0]["status"] == "completed"


async def test_completed_row_without_route_metadata_omits_routing_history(
    client_with_db: AsyncClient,
    api_key: tuple[str, uuid.UUID, uuid.UUID],
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, key_id = api_key
    opt_id = uuid.uuid4()
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
                "INSERT INTO optimizations "
                "(id, user_id, api_key_id, task_type, status, input_payload, model_version, "
                "solution, objective, solve_seconds, completed_at) "
                "VALUES (:id, :uid, :key_id, 'lp', 'completed', CAST(:payload AS jsonb), "
                "CAST(:model_version AS jsonb), CAST(:solution AS jsonb), 10.0, 0.25, :done_at)"
            ),
            {
                "id": opt_id,
                "uid": user_id,
                "key_id": key_id,
                "payload": json.dumps(_LP_BODY),
                "model_version": json.dumps(model_version),
                "solution": json.dumps({"x": [0.0, 10.0]}),
                "done_at": datetime.now(UTC),
            },
        )
        await s.commit()

    resp = await client_with_db.get(f"/v1/optimizations/{opt_id}", headers={"Authorization": auth})
    assert resp.status_code == 200, resp.text
    assert "routing_history" not in resp.json()


async def test_batch_items_do_not_include_routing_history(
    client_with_db: AsyncClient,
    api_key: tuple[str, uuid.UUID, uuid.UUID],
) -> None:
    auth, _user_id, _key_id = api_key
    resp = await client_with_db.post(
        "/v1/optimizations/batch",
        json={"tasks": [_LP_BODY]},
        headers={"Authorization": auth},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    item = body["items"][0]
    assert "routing_history" not in item

    get_resp = await client_with_db.get(
        f"/v1/optimizations/batch/{body['batch_id']}",
        headers={"Authorization": auth},
    )
    assert get_resp.status_code == 200, get_resp.text
    assert "routing_history" not in get_resp.json()["items"][0]
