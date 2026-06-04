"""Story 8.C.4 - classic benchmark library browse/import and discount tests."""

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
OPTIMIZATION_BENCHMARK_ID = "or-lib-afiro-lp"
PREDICTION_BENCHMARK_ID = "m5-walmart-forecast"

LP_BODY = {
    "task_type": "lp",
    "minimize": {"c": [1.0, 1.0]},
    "st": {"A": [[1.0, 1.0]], "b": [10.0]},
}


def _make_api_key() -> tuple[str, str, int]:
    random_part = f"t8c4{uuid.uuid4().hex}"
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
                "email": f"8-c-4-{user_id}@example.com",
                "phone": f"+8684{user_id.int % 10**8:08d}",
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
                "label": "8-c-4-test",
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


@pytest_asyncio.fixture(loop_scope="session")
async def public_client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_public_benchmark_library_list_filters_and_redacts_raw_data(
    public_client: AsyncClient,
) -> None:
    resp = await public_client.get("/v1/benchmark-library")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    suites = {item["suite"] for item in body}
    assert suites == {"ieee", "cvrplib", "or-lib", "m5", "uci", "nab"}
    assert len(body) >= 6
    for item in body:
        assert item["dataset_ref"].startswith("benchmark://")
        assert item["discount"] == {
            "kind": "benchmark_library",
            "label_zh": "50% Credits 折扣",
            "discount_multiplier": 0.5,
            "billing_supported": item["import_kind"] == "optimization_request",
        }
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True)
    assert "raw_rows" not in raw
    assert "file_content" not in raw
    assert "full_dataset" not in raw

    by_suite = await public_client.get("/v1/benchmark-library?suite=cvrplib")
    assert by_suite.status_code == 200, by_suite.text
    assert {item["suite"] for item in by_suite.json()} == {"cvrplib"}

    composed = await public_client.get("/v1/benchmark-library?domain=forecast&task_type=forecast")
    assert composed.status_code == 200, composed.text
    assert composed.json()
    assert all(
        item["domain"] == "forecast" and item["task_type"] == "forecast" for item in composed.json()
    )

    unknown = await public_client.get("/v1/benchmark-library?suite=unknown")
    assert unknown.status_code == 200, unknown.text
    assert unknown.json() == []


async def test_public_benchmark_detail_and_import_payload_contract(
    public_client: AsyncClient,
) -> None:
    detail = await public_client.get(f"/v1/benchmark-library/{OPTIMIZATION_BENCHMARK_ID}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["benchmark_id"] == OPTIMIZATION_BENCHMARK_ID

    imported = await public_client.post(f"/v1/benchmark-library/{OPTIMIZATION_BENCHMARK_ID}/import")
    assert imported.status_code == 200, imported.text
    body = imported.json()
    assert body["benchmark_id"] == OPTIMIZATION_BENCHMARK_ID
    assert body["import_kind"] == "optimization_request"
    assert body["target_endpoint"] == "/v1/optimizations"
    assert body["request_payload"]["options"]["benchmark_library"] is True
    assert body["request_payload"]["options"]["benchmark_id"] == OPTIMIZATION_BENCHMARK_ID
    assert body["discount"]["billing_supported"] is True
    assert "minimal template" in body["disclaimer_en"]
    assert "完整数据集镜像" in body["disclaimer_zh"]

    prediction_import = await public_client.post(
        f"/v1/benchmark-library/{PREDICTION_BENCHMARK_ID}/import"
    )
    assert prediction_import.status_code == 200, prediction_import.text
    prediction_body = prediction_import.json()
    assert prediction_body["target_endpoint"] == "/v1/predictions"
    assert prediction_body["discount"]["billing_supported"] is False
    assert "prediction billing discount is not implemented" in prediction_body["disclaimer_en"]

    missing = await public_client.get("/v1/benchmark-library/does-not-exist")
    assert missing.status_code == 404, missing.text


def test_benchmark_import_payloads_are_deep_copied() -> None:
    from solver_orchestrator.benchmark_library import build_import_response

    first = build_import_response(OPTIMIZATION_BENCHMARK_ID)
    assert first is not None
    first["request_payload"]["options"]["benchmark_id"] = "mutated"
    second = build_import_response(OPTIMIZATION_BENCHMARK_ID)
    assert second is not None
    assert second["request_payload"]["options"]["benchmark_id"] == OPTIMIZATION_BENCHMARK_ID


async def test_optimization_benchmark_discount_finalize_uses_single_half_multiplier(
    client_with_db: AsyncClient,
    public_client: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    charge_id = uuid.uuid4()
    finalize_args: dict[str, object] = {}
    imported = await public_client.post(f"/v1/benchmark-library/{OPTIMIZATION_BENCHMARK_ID}/import")
    payload = imported.json()["request_payload"]

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
        "/v1/optimizations",
        json=payload,
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )

    assert resp.status_code == 200, resp.text
    assert finalize_args == {
        "cid": charge_id,
        "uid": user_id,
        "elapsed_seconds": pytest.approx(10.0),
        "status": "success",
        "failure_reason": None,
        "discount_multiplier": pytest.approx(0.5),
    }


async def test_async_benchmark_discount_reserves_and_persists_metadata(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    charge_id = uuid.uuid4()
    reserve_calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def _reserve(cid, uid, *, client=None):
        reserve_calls.append((cid, uid))
        return BillingResult(ok=True, status_code=200, body={}, error_message=None)

    async def _finalize_should_not_run(*args, **kwargs):
        raise AssertionError("async queued benchmark import must not finalize")

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize_should_not_run)
    monkeypatch.setattr(
        solvers,
        "solve_from_request",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no solve")),
    )

    payload = {
        **LP_BODY,
        "options": {
            "benchmark_library": True,
            "benchmark_id": OPTIMIZATION_BENCHMARK_ID,
            "backtest": True,
        },
    }
    resp = await client_with_db.post(
        "/v1/optimizations?mode=async",
        json=payload,
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )

    assert resp.status_code == 202, resp.text
    assert reserve_calls == [(charge_id, user_id)]
    row = await _optimization_row(db_engine, uuid.UUID(resp.json()["optimization_id"]))
    billing = row["input_payload"]["_system"]["billing"]
    assert billing["discount_kind"] == "benchmark_library"
    assert billing["discount_multiplier"] == pytest.approx(0.5)
    assert "0.25" not in json.dumps(billing, sort_keys=True)


async def test_invalid_benchmark_option_fails_before_side_effects(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    idem_key = f"8-c-4-invalid-{uuid.uuid4()}"
    before = await _side_effect_counts(db_engine, user_id=user_id, idempotency_key=idem_key)

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("invalid benchmark option must fail before billing")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", lambda *_args, **_kwargs: _optimal_result())

    resp = await client_with_db.post(
        "/v1/optimizations",
        json={
            **LP_BODY,
            "options": {
                "benchmark_library": True,
                "benchmark_id": PREDICTION_BENCHMARK_ID,
            },
        },
        headers={
            "Authorization": auth,
            "Idempotency-Key": idem_key,
            "X-Billing-Charge-Id": str(uuid.uuid4()),
        },
    )

    assert resp.status_code == 400, resp.text
    assert resp.json()["title"] == "Invalid Benchmark Library Option"
    after = await _side_effect_counts(db_engine, user_id=user_id, idempotency_key=idem_key)
    assert after == before


async def test_benchmark_id_without_flag_is_rejected_before_side_effects(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    idem_key = f"8-c-4-ghost-{uuid.uuid4()}"
    before = await _side_effect_counts(db_engine, user_id=user_id, idempotency_key=idem_key)

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("ghost benchmark_id must fail before billing")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)

    resp = await client_with_db.post(
        "/v1/optimizations",
        json={
            **LP_BODY,
            "options": {
                "benchmark_library": False,
                "benchmark_id": OPTIMIZATION_BENCHMARK_ID,
            },
        },
        headers={"Authorization": auth, "Idempotency-Key": idem_key},
    )

    assert resp.status_code == 400, resp.text
    after = await _side_effect_counts(db_engine, user_id=user_id, idempotency_key=idem_key)
    assert after == before


@pytest.mark.parametrize(
    ("options", "expected_detail"),
    [
        ({"benchmark_library": True}, "requires a non-empty options.benchmark_id"),
        (
            {"benchmark_library": True, "benchmark_id": ""},
            "requires a non-empty options.benchmark_id",
        ),
        (
            {"benchmark_library": True, "benchmark_id": "unknown-benchmark"},
            "unknown benchmark library id",
        ),
    ],
)
async def test_missing_or_unknown_benchmark_id_fails_before_side_effects(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
    options: dict[str, object],
    expected_detail: str,
) -> None:
    auth, user_id = api_key
    idem_key = f"8-c-4-missing-{uuid.uuid4()}"
    before = await _side_effect_counts(db_engine, user_id=user_id, idempotency_key=idem_key)

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("invalid benchmark option must fail before billing")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", lambda *_args, **_kwargs: _optimal_result())

    resp = await client_with_db.post(
        "/v1/optimizations",
        json={**LP_BODY, "options": options},
        headers={
            "Authorization": auth,
            "Idempotency-Key": idem_key,
            "X-Billing-Charge-Id": str(uuid.uuid4()),
        },
    )

    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["title"] == "Invalid Benchmark Library Option"
    assert expected_detail in body["detail"]
    after = await _side_effect_counts(db_engine, user_id=user_id, idempotency_key=idem_key)
    assert after == before


async def test_task_type_mismatched_benchmark_id_fails_before_side_effects(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    idem_key = f"8-c-4-mismatch-{uuid.uuid4()}"
    before = await _side_effect_counts(db_engine, user_id=user_id, idempotency_key=idem_key)

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("task-type mismatch must fail before billing")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", lambda *_args, **_kwargs: _optimal_result())

    resp = await client_with_db.post(
        "/v1/optimizations",
        json={
            **LP_BODY,
            "task_type": "milp",
            "options": {
                "benchmark_library": True,
                "benchmark_id": OPTIMIZATION_BENCHMARK_ID,
            },
        },
        headers={
            "Authorization": auth,
            "Idempotency-Key": idem_key,
            "X-Billing-Charge-Id": str(uuid.uuid4()),
        },
    )

    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["title"] == "Invalid Benchmark Library Option"
    assert "not 'milp'" in body["detail"]
    after = await _side_effect_counts(db_engine, user_id=user_id, idempotency_key=idem_key)
    assert after == before


async def test_teaching_takes_precedence_over_benchmark_discount_retry_context(
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
        json={
            **LP_BODY,
            "options": {
                "benchmark_library": True,
                "benchmark_id": OPTIMIZATION_BENCHMARK_ID,
            },
        },
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )

    assert resp.status_code == 200, resp.text
    row = await _optimization_row(db_engine, uuid.UUID(resp.json()["optimization_id"]))
    error = row["error"]
    assert error["billing_discount_kind"] == "teaching"
    assert error["billing_discount_multiplier"] == pytest.approx(0.5)
    assert "0.25" not in json.dumps(error, sort_keys=True)


async def test_same_idempotency_key_benchmark_true_false_conflicts(
    client_with_db: AsyncClient,
    api_key,
    monkeypatch,
) -> None:
    auth, _ = api_key
    idem_key = f"8-c-4-conflict-{uuid.uuid4()}"

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("no billing header should avoid billing")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", lambda *_args, **_kwargs: _optimal_result())

    headers = {"Authorization": auth, "Idempotency-Key": idem_key}
    first = await client_with_db.post(
        "/v1/optimizations",
        json={
            **LP_BODY,
            "options": {
                "benchmark_library": True,
                "benchmark_id": OPTIMIZATION_BENCHMARK_ID,
            },
        },
        headers=headers,
    )
    second = await client_with_db.post(
        "/v1/optimizations",
        json=LP_BODY,
        headers=headers,
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 409, second.text
    assert second.json()["title"] == "Idempotency Conflict"


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


async def _side_effect_counts(
    db_engine: AsyncEngine, *, user_id: uuid.UUID, idempotency_key: str
) -> dict[str, int]:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (
            (
                await s.execute(
                    text(
                        "SELECT "
                        "(SELECT count(*) FROM optimizations WHERE user_id = :uid) AS optimizations, "
                        "(SELECT count(*) FROM idempotency_keys "
                        "WHERE user_id = :uid AND key = :idem) AS idempotency"
                    ),
                    {"uid": user_id, "idem": idempotency_key},
                )
            )
            .mappings()
            .one()
        )
    return {"optimizations": int(row["optimizations"]), "idempotency": int(row["idempotency"])}
