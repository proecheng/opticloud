"""Story 8.C.1 - mode=teaching response, notebook and billing discount tests."""

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
from pathlib import Path

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
REPO_ROOT = Path(__file__).resolve().parents[3]
TEACHING_NOTEBOOK_REPO_PATH = "docs/notebooks/teaching-lp.ipynb"
TEACHING_COLAB_URL = (
    "https://colab.research.google.com/github/proecheng/opticloud/blob/main/"
    f"{TEACHING_NOTEBOOK_REPO_PATH}"
)

LP_BODY = {
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
    random_part = f"t8c1{uuid.uuid4().hex}"
    full = f"sk-{random_part}"
    pepper_version = 1
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    key_hash = hmac.new(pepper, full.encode("utf-8"), hashlib.sha256).hexdigest()
    return full, key_hash, pepper_version


def _optimal_result(*, solve_seconds: float = 10.0) -> solvers.LPSolveResult:
    return solvers.LPSolveResult(
        status="optimal",
        objective=10.0,
        solution={"x": [0.0, 10.0]},
        solve_seconds=solve_seconds,
    )


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
                "email": f"8-c-1-{user_id}@example.com",
                "phone": f"+8681{user_id.int % 10**8:08d}",
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
                "label": "8-c-1-test",
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


async def test_teaching_mode_sync_response_persists_and_get_replays(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, _ = api_key

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("teaching without billing header must not call billing")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", lambda *_args, **_kwargs: _optimal_result())

    resp = await client_with_db.post(
        "/v1/optimizations?mode=teaching",
        json=LP_BODY,
        headers={"Authorization": auth},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    teaching = body["teaching"]
    assert teaching["mode"] == "teaching"
    assert teaching["principle_explanation"]["title_zh"] == "线性规划教学模式"
    assert "线性目标函数" in teaching["principle_explanation"]["summary_zh"]
    assert len(teaching["principle_explanation"]["modeling_steps_zh"]) >= 3
    assert len(teaching["principle_explanation"]["limitations_zh"]) >= 1
    assert teaching["credits_discount"] == {
        "kind": "teaching",
        "label_zh": "50% Credits 折扣",
        "discount_multiplier": 0.5,
    }
    assert teaching["notebook"]["repo_path"] == TEACHING_NOTEBOOK_REPO_PATH
    assert teaching["notebook"]["colab_url"] == TEACHING_COLAB_URL
    assert "_system" not in resp.text
    assert "billing_charge_id" not in resp.text

    optimization_id = uuid.UUID(body["optimization_id"])
    row = await _optimization_row(db_engine, optimization_id)
    assert row["input_payload"]["_system"]["teaching"] == teaching

    fetched = await client_with_db.get(
        f"/v1/optimizations/{optimization_id}",
        headers={"Authorization": auth},
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["teaching"] == teaching
    assert "_system" not in fetched.text
    assert "billing_charge_id" not in fetched.text


async def test_teaching_mode_billing_finalize_passes_single_half_discount(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    charge_id = uuid.uuid4()
    finalize_args: dict[str, object] = {}

    async def _reserve(cid, uid, *, client=None):
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    async def _finalize(
        cid,
        uid,
        *,
        elapsed_seconds,
        status,
        failure_reason=None,
        client=None,
        discount_multiplier=None,
    ):
        finalize_args.update(
            {
                "cid": cid,
                "uid": uid,
                "elapsed_seconds": elapsed_seconds,
                "status": status,
                "failure_reason": failure_reason,
                "discount_multiplier": discount_multiplier,
            }
        )
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)
    monkeypatch.setattr(solvers, "solve_from_request", lambda *_args, **_kwargs: _optimal_result())

    resp = await client_with_db.post(
        "/v1/optimizations?mode=teaching",
        json=LP_BODY,
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["solve_seconds"] == pytest.approx(10.0)
    assert finalize_args == {
        "cid": charge_id,
        "uid": user_id,
        "elapsed_seconds": pytest.approx(10.0),
        "status": "success",
        "failure_reason": None,
        "discount_multiplier": pytest.approx(0.5),
    }


async def test_teaching_timeout_finalize_also_uses_single_half_discount(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _ = api_key
    charge_id = uuid.uuid4()
    finalize_args: dict[str, object] = {}

    async def _reserve(*args, **kwargs):
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    async def _finalize(*args, elapsed_seconds, status, failure_reason=None, **kwargs):
        finalize_args.update(
            {
                "elapsed_seconds": elapsed_seconds,
                "status": status,
                "failure_reason": failure_reason,
                "discount_multiplier": kwargs.get("discount_multiplier"),
            }
        )
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)
    monkeypatch.setattr(
        solvers,
        "solve_from_request",
        lambda *_args, **_kwargs: solvers.LPSolveResult(
            status="timeout",
            objective=None,
            solution=None,
            solve_seconds=30.0,
            error_constraint="solver exceeded max_solve_seconds",
            error_field_path="options.max_solve_seconds",
        ),
    )

    resp = await client_with_db.post(
        "/v1/optimizations?mode=teaching",
        json=LP_BODY,
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )

    assert resp.status_code == 504, resp.text
    assert finalize_args == {
        "elapsed_seconds": pytest.approx(30.0),
        "status": "success",
        "failure_reason": None,
        "discount_multiplier": pytest.approx(0.5),
    }


async def test_teaching_and_backtest_do_not_stack_discount(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _ = api_key
    charge_id = uuid.uuid4()
    finalize_multipliers: list[float | None] = []

    async def _reserve(*args, **kwargs):
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    async def _finalize(*args, discount_multiplier=None, **kwargs):
        finalize_multipliers.append(discount_multiplier)
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)
    monkeypatch.setattr(solvers, "solve_from_request", lambda *_args, **_kwargs: _optimal_result())

    resp = await client_with_db.post(
        "/v1/optimizations?mode=teaching",
        json={**LP_BODY, "options": {"backtest": True}},
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )

    assert resp.status_code == 200, resp.text
    assert finalize_multipliers == [pytest.approx(0.5)]
    assert resp.json()["teaching"]["credits_discount"]["kind"] == "teaching"


async def test_teaching_finalize_failure_persists_discount_retry_context(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, _ = api_key
    charge_id = uuid.uuid4()

    async def _reserve(*args, **kwargs):
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    async def _finalize(*args, **kwargs):
        return BillingResult(ok=False, status_code=503, body=None, error_message="HTTP 503")

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)
    monkeypatch.setattr(solvers, "solve_from_request", lambda *_args, **_kwargs: _optimal_result())

    resp = await client_with_db.post(
        "/v1/optimizations?mode=teaching",
        json={**LP_BODY, "options": {"backtest": True}},
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )

    assert resp.status_code == 200, resp.text
    row = await _optimization_row(db_engine, uuid.UUID(resp.json()["optimization_id"]))
    error = row["error"]
    assert error["billing_finalize_failed"] is True
    assert error["billing_charge_id"] == str(charge_id)
    assert error["billing_elapsed_seconds"] == pytest.approx(10.0)
    assert error["billing_discount_multiplier"] == pytest.approx(0.5)
    assert error["billing_discount_kind"] == "teaching"
    assert "0.25" not in json.dumps(error, sort_keys=True)


async def test_teaching_idempotency_replay_and_plain_sync_conflict(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _ = api_key
    idem_key = f"8-c-1-teaching-{uuid.uuid4()}"

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("no billing header should avoid billing")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", lambda *_args, **_kwargs: _optimal_result())

    headers = {"Authorization": auth, "Idempotency-Key": idem_key}
    first = await client_with_db.post(
        "/v1/optimizations?mode=teaching", json=LP_BODY, headers=headers
    )
    replay = await client_with_db.post(
        "/v1/optimizations?mode=teaching", json=LP_BODY, headers=headers
    )
    conflict = await client_with_db.post("/v1/optimizations", json=LP_BODY, headers=headers)

    assert first.status_code == 200, first.text
    assert replay.status_code == 200, replay.text
    assert replay.json()["optimization_id"] == first.json()["optimization_id"]
    assert replay.json()["teaching"] == first.json()["teaching"]
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["title"] == "Idempotency Conflict"


async def test_teaching_auto_async_keeps_execution_mode_and_teaching_metadata(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _ = api_key

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("no billing header should avoid billing")

    def _solver_should_not_run(*args, **kwargs):
        raise AssertionError("auto-async queued path must not solve inline")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", _solver_should_not_run)

    created = await client_with_db.post(
        "/v1/optimizations?mode=teaching",
        json=_large_lp_body(),
        headers={"Authorization": auth},
    )

    assert created.status_code == 202, created.text
    body = created.json()
    assert body["mode"] == "async"
    assert body["requested_mode"] == "sync"
    assert body["auto_async"] is True
    assert body["teaching"]["mode"] == "teaching"

    fetched = await client_with_db.get(
        f"/v1/optimizations/{body['optimization_id']}",
        headers={"Authorization": auth},
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["mode"] == "async"
    assert fetched.json()["teaching"] == body["teaching"]


def test_teaching_notebook_path_exists_and_matches_colab_url() -> None:
    notebook_path = REPO_ROOT / TEACHING_NOTEBOOK_REPO_PATH
    assert notebook_path.exists()
    assert TEACHING_COLAB_URL.endswith(TEACHING_NOTEBOOK_REPO_PATH)

    raw = json.loads(notebook_path.read_text(encoding="utf-8"))
    assert raw["nbformat"] == 4
    cells = raw["cells"]
    assert any(
        cell["cell_type"] == "markdown" and "线性规划教学模式" in "".join(cell["source"])
        for cell in cells
    )
    assert any(
        cell["cell_type"] == "code" and "mode=teaching" in "".join(cell["source"]) for cell in cells
    )


async def _optimization_row(db_engine: AsyncEngine, optimization_id: uuid.UUID) -> dict:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (
            (
                await s.execute(
                    text(
                        "SELECT input_payload, solve_seconds, error "
                        "FROM optimizations WHERE id = :id"
                    ),
                    {"id": optimization_id},
                )
            )
            .mappings()
            .one()
        )
    return dict(row)
