"""Story 3.2 - FR E2 prediction submission tests."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import sys
import uuid
from collections.abc import AsyncIterator
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from solver_orchestrator import billing_client
from solver_orchestrator import catalog as catalog_module
from solver_orchestrator.catalog import CATALOG
from solver_orchestrator.config import settings
from solver_orchestrator.db import get_session
from solver_orchestrator.forecasting import predict_quantiles
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


def _hash_body(body: dict) -> str:
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _make_api_key() -> tuple[str, str, int]:
    random_part = f"t32{uuid.uuid4().hex}"
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
                "email": f"3-2-{user_id}@example.com",
                "phone": f"+861{user_id.int % 10**10:010d}",
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
                "label": "3-2-test",
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
                "email": f"3-2-b-{user_id}@example.com",
                "phone": f"+862{user_id.int % 10**10:010d}",
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
                "label": "3-2-test-b",
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


def _assert_quantiles(body: dict, horizon: int) -> None:
    prediction = body["prediction"]
    assert set(prediction) == {"p10", "p50", "p90"}
    assert len(prediction["p10"]) == horizon
    assert len(prediction["p50"]) == horizon
    assert len(prediction["p90"]) == horizon
    for p10, p50, p90 in zip(prediction["p10"], prediction["p50"], prediction["p90"], strict=True):
        assert p10 <= p50 <= p90


@pytest.mark.parametrize(
    "series",
    [
        [5.0, 5.0, 5.0, 5.0],
        [1.0, 2.0, 3.0, 4.0],
        [4.0, 3.0, 2.0, 1.0],
        [1.0, 3.0, 2.0, 5.0, 4.0],
    ],
)
def test_forecast_helper_is_deterministic_and_ordered(series: list[float]) -> None:
    first = predict_quantiles(series, horizon=5)
    second = predict_quantiles(series, horizon=5)

    assert first == second
    assert 0.0 <= first.drift_score <= 1.0
    assert len(first.p10) == len(first.p50) == len(first.p90) == 5
    for p10, p50, p90 in zip(first.p10, first.p50, first.p90, strict=True):
        assert p10 <= p50 <= p90


async def test_post_prediction_arima_returns_completed_quantiles_and_persists_route(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, _ = api_key

    resp = await client_with_db.post(
        "/v1/predictions",
        json={"family": "arima", "data": [1, 2, 3, 4]},
        headers={"Authorization": auth},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["family"] == "arima"
    assert body["horizon"] == 3
    assert body["model_version"]["provider_id"] == "statsmodels-arima"
    assert 0.0 <= body["drift_score"] <= 1.0
    assert body["disclaimer"] == {
        "zh": "本预测仅供参考",
        "en": "This forecast is for reference only",
        "bilingual": "本预测仅供参考 / This forecast is for reference only",
    }
    _assert_quantiles(body, horizon=3)
    assert "_system" not in resp.text

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (
            await s.execute(
                text("SELECT input_payload FROM predictions WHERE id = :id"),
                {"id": uuid.UUID(body["prediction_id"])},
            )
        ).scalar_one()

    provider_route = row["_system"]["provider_route"]
    assert provider_route["task_type"] == "forecast"
    assert provider_route["requested_solver"] == "arima"
    assert provider_route["selected_solver"] == "arima"
    assert provider_route["provider_id"] == "statsmodels-arima"
    assert row["horizon"] == 3


async def test_post_prediction_chronos_uses_catalog_model_without_gpu_dependency(
    client_with_db: AsyncClient,
    api_key,
) -> None:
    auth, _ = api_key

    resp = await client_with_db.post(
        "/v1/predictions",
        json={"family": "chronos", "data": [10, 9, 8, 7], "horizon": 2},
        headers={"Authorization": auth},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["family"] == "chronos"
    assert body["model_version"]["provider_id"] == "chronos-t5"
    _assert_quantiles(body, horizon=2)


async def test_get_prediction_returns_same_completed_response_for_owner(
    client_with_db: AsyncClient,
    api_key,
    second_api_key,
) -> None:
    auth, _ = api_key
    second_auth, _ = second_api_key

    created = await client_with_db.post(
        "/v1/predictions",
        json={"family": "arima", "data": [2, 4, 6, 8]},
        headers={"Authorization": auth},
    )
    assert created.status_code == 200, created.text
    prediction_id = created.json()["prediction_id"]

    fetched = await client_with_db.get(
        f"/v1/predictions/{prediction_id}",
        headers={"Authorization": auth},
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json() == created.json()

    cross_user = await client_with_db.get(
        f"/v1/predictions/{prediction_id}",
        headers={"Authorization": second_auth},
    )
    assert cross_user.status_code == 404, cross_user.text


async def test_prediction_idempotency_replays_completed_row_without_duplicate(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id = api_key
    idem_key = f"3-2-replay-{uuid.uuid4()}"
    payload = {"family": "arima", "data": [1, 2, 3, 4], "horizon": 3}
    headers = {"Authorization": auth, "Idempotency-Key": idem_key}

    first = await client_with_db.post("/v1/predictions", json=payload, headers=headers)
    second = await client_with_db.post("/v1/predictions", json=payload, headers=headers)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["prediction_id"] == first.json()["prediction_id"]

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        count = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM predictions "
                    "WHERE user_id = :uid AND idempotency_key = :idempotency_key"
                ),
                {"uid": user_id, "idempotency_key": idem_key},
            )
        ).scalar_one()
        idem_count = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM prediction_idempotency_keys "
                    "WHERE user_id = :uid AND key = :idempotency_key"
                ),
                {"uid": user_id, "idempotency_key": idem_key},
            )
        ).scalar_one()
    assert count == 1
    assert idem_count == 1


async def test_prediction_expired_idempotency_key_allows_new_execution(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id = api_key
    idem_key = f"3-2-expired-{uuid.uuid4()}"
    payload = {"family": "arima", "data": [1, 2, 3, 4]}
    headers = {"Authorization": auth, "Idempotency-Key": idem_key}

    first = await client_with_db.post("/v1/predictions", json=payload, headers=headers)
    assert first.status_code == 200, first.text

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "UPDATE prediction_idempotency_keys "
                "SET expires_at = :expired_at "
                "WHERE user_id = :uid AND key = :idempotency_key"
            ),
            {
                "expired_at": datetime.now(UTC) - timedelta(seconds=1),
                "uid": user_id,
                "idempotency_key": idem_key,
            },
        )
        await s.commit()

    second = await client_with_db.post("/v1/predictions", json=payload, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["prediction_id"] != first.json()["prediction_id"]

    async with maker() as s:
        active_mapping = (
            await s.execute(
                text(
                    "SELECT prediction_id FROM prediction_idempotency_keys "
                    "WHERE user_id = :uid AND key = :idempotency_key"
                ),
                {"uid": user_id, "idempotency_key": idem_key},
            )
        ).scalar_one()
    assert str(active_mapping) == second.json()["prediction_id"]


async def test_prediction_idempotency_reuses_default_horizon_hash(
    client_with_db: AsyncClient,
    api_key,
) -> None:
    auth, _ = api_key
    idem_key = f"3-2-default-horizon-{uuid.uuid4()}"
    headers = {"Authorization": auth, "Idempotency-Key": idem_key}

    first = await client_with_db.post(
        "/v1/predictions",
        json={"family": "arima", "data": [1, 2, 3, 4]},
        headers=headers,
    )
    second = await client_with_db.post(
        "/v1/predictions",
        json={"family": "arima", "data": [1, 2, 3, 4], "horizon": 3},
        headers=headers,
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["prediction_id"] == first.json()["prediction_id"]


async def test_prediction_idempotency_conflicts_on_different_body(
    client_with_db: AsyncClient,
    api_key,
) -> None:
    auth, _ = api_key
    idem_key = f"3-2-conflict-{uuid.uuid4()}"
    headers = {"Authorization": auth, "Idempotency-Key": idem_key}

    first = await client_with_db.post(
        "/v1/predictions",
        json={"family": "arima", "data": [1, 2, 3, 4]},
        headers=headers,
    )
    second = await client_with_db.post(
        "/v1/predictions",
        json={"family": "arima", "data": [1, 2, 3, 5]},
        headers=headers,
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 409, second.text
    assert second.json()["title"] == "Idempotency Conflict"


async def test_incomplete_prediction_idempotency_row_returns_409_without_execution(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    idem_key = f"3-2-stale-{uuid.uuid4()}"
    stale_prediction_id = uuid.uuid4()
    request_hash = _hash_body({"data": [1.0, 2.0, 3.0, 4.0], "family": "arima", "horizon": 3})

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO predictions "
                "(id, user_id, api_key_id, family, status, input_payload, idempotency_key) "
                "SELECT :prediction_id, :uid, id, 'arima', 'queued', "
                "CAST(:payload AS jsonb), :idempotency_key "
                "FROM api_keys WHERE user_id = :uid LIMIT 1"
            ),
            {
                "prediction_id": stale_prediction_id,
                "uid": user_id,
                "payload": '{"family":"arima","data":[1.0,2.0,3.0,4.0],"horizon":3}',
                "idempotency_key": idem_key,
            },
        )
        await s.execute(
            text(
                "INSERT INTO prediction_idempotency_keys "
                "(user_id, key, prediction_id, request_body_hash, expires_at) "
                "VALUES (:uid, :key, :prediction_id, :body_hash, :expires_at)"
            ),
            {
                "uid": user_id,
                "key": idem_key,
                "prediction_id": stale_prediction_id,
                "body_hash": request_hash,
                "expires_at": datetime.now(UTC) + timedelta(hours=24),
            },
        )
        await s.commit()

    def _should_not_execute(*args, **kwargs):
        raise AssertionError("forecasting should not run for stale idempotency row")

    monkeypatch.setattr("solver_orchestrator.routes.predict_quantiles", _should_not_execute)

    resp = await client_with_db.post(
        "/v1/predictions",
        json={"family": "arima", "data": [1, 2, 3, 4]},
        headers={"Authorization": auth, "Idempotency-Key": idem_key},
    )

    assert resp.status_code == 409, resp.text
    assert resp.json()["title"] == "Idempotency Conflict"


@pytest.mark.parametrize(
    ("payload", "field_path"),
    [
        ({"family": "timesfm", "data": [1, 2, 3]}, "family"),
        ({"family": "arima", "data": [1, 2]}, "data"),
        ({"family": "arima", "data": [1, 2, 3], "horizon": 0}, "horizon"),
    ],
)
async def test_prediction_invalid_requests_are_rfc7807_and_side_effect_free(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    payload: dict,
    field_path: str,
) -> None:
    auth, user_id = api_key
    before = await _prediction_count(db_engine, user_id)

    resp = await client_with_db.post(
        "/v1/predictions",
        json=payload,
        headers={"Authorization": auth},
    )

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["errors"][0]["field_path"] == field_path
    assert await _prediction_count(db_engine, user_id) == before


async def test_prediction_non_finite_data_is_rfc7807_and_side_effect_free(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id = api_key
    before = await _prediction_count(db_engine, user_id)

    resp = await client_with_db.post(
        "/v1/predictions",
        content='{"family":"arima","data":[1,NaN,3]}',
        headers={"Authorization": auth, "Content-Type": "application/json"},
    )

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["title"] == "Invalid Prediction Data"
    assert body["errors"][0]["field_path"] == "data[1]"
    assert await _prediction_count(db_engine, user_id) == before


async def test_prediction_billing_header_is_rejected_without_billing_calls_or_rows(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    before = await _prediction_count(db_engine, user_id)
    charge_id = uuid.uuid4()

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("billing should not run for predictions")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)

    resp = await client_with_db.post(
        "/v1/predictions",
        json={"family": "arima", "data": [1, 2, 3, 4]},
        headers={"Authorization": auth, "X-Billing-Charge-Id": str(charge_id)},
    )

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["title"] == "Billing Not Supported For Predictions"
    assert str(charge_id) not in str(body)
    assert await _prediction_count(db_engine, user_id) == before


async def test_prediction_unaudited_self_forecast_blocks_before_side_effects(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    before = await _prediction_count(db_engine, user_id)
    idempotency_key = f"3-2-unaudited-{uuid.uuid4()}"

    unaudited_forecast = deepcopy(
        next(item for item in CATALOG if item["k_algo"] == "arima-forecast")
    )
    unaudited_forecast["k_algo"] = "test-self-arima-forecast"
    unaudited_forecast["model_version"] = {
        "provider_id": "test-self-arima",
        "kind": "self",
        "version": "0.1.0",
        "provider_url": "https://example.invalid/test-self-arima",
    }
    unaudited_forecast["supported_solvers"] = ["arima"]
    unaudited_forecast["self_audit"] = {
        "package_or_runnable": False,
        "license_approved": False,
        "minimal_example_30m": False,
        "readme_schema": False,
        "paper_reproduction_result": False,
    }
    other_rows = [deepcopy(item) for item in CATALOG if item["k_algo"] != "arima-forecast"]
    monkeypatch.setattr(catalog_module, "CATALOG", [unaudited_forecast, *other_rows])

    def _should_not_execute(*args, **kwargs):
        raise AssertionError("forecasting should not run for unaudited self forecast")

    monkeypatch.setattr("solver_orchestrator.routes.predict_quantiles", _should_not_execute)

    resp = await client_with_db.post(
        "/v1/predictions",
        json={"family": "arima", "data": [1, 2, 3, 4]},
        headers={"Authorization": auth, "Idempotency-Key": idempotency_key},
    )

    assert resp.status_code == 403, resp.text
    body = resp.json()
    assert body["title"] == "Unaudited Self Algorithm"
    assert body["errors"][0]["field_path"] == "family"
    assert await _prediction_count(db_engine, user_id) == before
    assert await _prediction_idempotency_count(db_engine, user_id, idempotency_key) == 0


async def test_get_prediction_failed_row_returns_compact_status_payload(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id = api_key
    prediction_id = uuid.uuid4()
    error_payload = {"title": "Forecast Failed", "detail": "synthetic failure"}
    model_version = {
        "provider_id": "statsmodels-arima",
        "kind": "third_party",
        "version": "0.1.0",
        "provider_url": "https://example.com/statsmodels",
    }

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO predictions "
                "(id, user_id, api_key_id, family, status, input_payload, error, "
                "model_version, completed_at) "
                "SELECT :prediction_id, :uid, id, 'arima', 'failed', "
                "CAST(:payload AS jsonb), CAST(:error AS jsonb), "
                "CAST(:model_version AS jsonb), :completed_at "
                "FROM api_keys WHERE user_id = :uid LIMIT 1"
            ),
            {
                "prediction_id": prediction_id,
                "uid": user_id,
                "payload": json.dumps({"family": "arima", "data": [1, 2, 3], "horizon": 3}),
                "error": json.dumps(error_payload),
                "model_version": json.dumps(model_version),
                "completed_at": datetime.now(UTC),
            },
        )
        await s.commit()

    resp = await client_with_db.get(
        f"/v1/predictions/{prediction_id}",
        headers={"Authorization": auth},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["prediction_id"] == str(prediction_id)
    assert body["status"] == "failed"
    assert body["error"] == error_payload
    assert body["model_version"] == model_version
    assert "prediction" not in body


async def _prediction_count(db_engine: AsyncEngine, user_id: uuid.UUID) -> int:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        return int(
            (
                await s.execute(
                    text("SELECT COUNT(*) FROM predictions WHERE user_id = :uid"),
                    {"uid": user_id},
                )
            ).scalar_one()
        )


async def _prediction_idempotency_count(
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
                        "SELECT COUNT(*) FROM prediction_idempotency_keys "
                        "WHERE user_id = :uid AND key = :idempotency_key"
                    ),
                    {"uid": user_id, "idempotency_key": idempotency_key},
                )
            ).scalar_one()
        )
