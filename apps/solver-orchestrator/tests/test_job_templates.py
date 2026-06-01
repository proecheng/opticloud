"""Story 5.D.3 — job template save route tests."""

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

MODEL_VERSION = {
    "provider_id": "test-provider",
    "kind": "open_source",
    "version": "test-v1",
    "provider_url": "https://example.test/provider",
}


def _make_api_key(prefix: str = "t5d3") -> tuple[str, str, int]:
    random_part = f"{prefix}{uuid.uuid4().hex}"
    full = f"sk-{random_part}"
    pepper_version = 1
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    key_hash = hmac.new(pepper, full.encode("utf-8"), hashlib.sha256).hexdigest()
    return full, key_hash, pepper_version


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    await _ensure_job_template_table(eng)
    yield eng
    await eng.dispose()


async def _ensure_job_template_table(db_engine: AsyncEngine) -> None:
    async with db_engine.begin() as conn:
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
        await conn.execute(
            text(
                """
                ALTER TABLE job_templates
                    ADD COLUMN IF NOT EXISTS payload_schema_version VARCHAR(64) NOT NULL
                    DEFAULT 'prediction_request_v1'
                """
            )
        )
        await conn.execute(
            text("ALTER TABLE job_templates ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL")
        )
        await conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'ck_job_templates_source_kind'
                    ) THEN
                        ALTER TABLE job_templates
                            ADD CONSTRAINT ck_job_templates_source_kind
                            CHECK (source_kind IN ('optimization', 'prediction'));
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'ck_job_templates_payload_schema_version'
                    ) THEN
                        ALTER TABLE job_templates
                            ADD CONSTRAINT ck_job_templates_payload_schema_version
                            CHECK (
                                payload_schema_version IN (
                                    'optimization_request_v1',
                                    'prediction_request_v1'
                                )
                            );
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'ck_job_templates_version_positive'
                    ) THEN
                        ALTER TABLE job_templates
                            ADD CONSTRAINT ck_job_templates_version_positive
                            CHECK (version >= 1);
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'fk_job_templates_root_template_id'
                    ) THEN
                        ALTER TABLE job_templates
                            ADD CONSTRAINT fk_job_templates_root_template_id
                            FOREIGN KEY (root_template_id) REFERENCES job_templates(id);
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'fk_job_templates_parent_template_id'
                    ) THEN
                        ALTER TABLE job_templates
                            ADD CONSTRAINT fk_job_templates_parent_template_id
                            FOREIGN KEY (parent_template_id) REFERENCES job_templates(id);
                    END IF;
                END
                $$;
                """
            )
        )
        await conn.execute(
            text(
                """
                DROP INDEX IF EXISTS uq_job_templates_active_source_name
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_job_templates_active_root_source_name
                ON job_templates(user_id, source_kind, source_id, name)
                WHERE deleted_at IS NULL AND parent_template_id IS NULL
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_job_templates_active_root_version
                ON job_templates(user_id, root_template_id, version)
                WHERE deleted_at IS NULL
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_job_templates_user_created_at
                ON job_templates(user_id, created_at DESC)
                WHERE deleted_at IS NULL
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_job_templates_root_version
                ON job_templates(user_id, root_template_id, version)
                """
            )
        )


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
                "email": f"5-d-3-{label}-{user_id}@example.com",
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
                "label": f"5-d-3-{label}",
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


async def _insert_prediction(
    db_engine: AsyncEngine,
    *,
    user_id: uuid.UUID,
    api_key_id: uuid.UUID,
    status: str = "completed",
    input_payload: dict | None = None,  # type: ignore[type-arg]
) -> uuid.UUID:
    prediction_id = uuid.uuid4()
    payload = input_payload or {
        "family": "arima",
        "data": [1.0, 2.0, 3.0, 4.0],
        "horizon": 3,
        "_system": {
            "provider_route": {"selected_solver": "arima"},
            "billing": {"charge_id": str(uuid.uuid4())},
        },
    }
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                """
                INSERT INTO predictions
                    (id, user_id, api_key_id, family, status, input_payload,
                     prediction, drift_score, model_version, predict_seconds,
                     created_at, completed_at)
                VALUES
                    (:id, :uid, :api_key_id, 'arima', :status, CAST(:input_payload AS jsonb),
                     CAST(:prediction AS jsonb), 0.12, CAST(:model_version AS jsonb),
                     0.02, :now, :completed_at)
                """
            ),
            {
                "id": prediction_id,
                "uid": user_id,
                "api_key_id": api_key_id,
                "status": status,
                "input_payload": json.dumps(payload),
                "prediction": json.dumps({"p10": [1, 2, 3], "p50": [2, 3, 4], "p90": [3, 4, 5]}),
                "model_version": json.dumps(MODEL_VERSION),
                "now": datetime.now(UTC),
                "completed_at": datetime.now(UTC) if status == "completed" else None,
            },
        )
        await s.commit()
    return prediction_id


async def _insert_optimization(
    db_engine: AsyncEngine,
    *,
    user_id: uuid.UUID,
    api_key_id: uuid.UUID,
    status: str = "completed",
    input_payload: dict | None = None,  # type: ignore[type-arg]
) -> uuid.UUID:
    optimization_id = uuid.uuid4()
    payload = input_payload or {
        "task_type": "lp",
        "minimize": {"c": [1.0, 1.0]},
        "st": {"a": [[1.0, 1.0]], "b": [10.0]},
        "options": {"max_solve_seconds": 30.0},
        "fallback_chain": ["highs"],
        "_system": {
            "provider_route": {"selected_solver": "highs"},
            "reproducibility": {"request_fingerprint": "secret"},
            "billing": {"charge_id": str(uuid.uuid4())},
        },
    }
    payload["options"]["_system"] = {"internal": True}
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                """
                INSERT INTO optimizations
                    (id, user_id, api_key_id, task_type, status, input_payload,
                     solution, objective, model_version, solve_seconds,
                     created_at, completed_at)
                VALUES
                    (:id, :uid, :api_key_id, 'lp', :status, CAST(:input_payload AS jsonb),
                     CAST(:solution AS jsonb), 2.0, CAST(:model_version AS jsonb),
                     0.03, :now, :completed_at)
                """
            ),
            {
                "id": optimization_id,
                "uid": user_id,
                "api_key_id": api_key_id,
                "status": status,
                "input_payload": json.dumps(payload),
                "solution": json.dumps({"x": [1.0, 1.0]}),
                "model_version": json.dumps(MODEL_VERSION),
                "now": datetime.now(UTC),
                "completed_at": datetime.now(UTC) if status == "completed" else None,
            },
        )
        await s.commit()
    return optimization_id


async def _counts(db_engine: AsyncEngine, user_id: uuid.UUID) -> dict[str, int]:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        optional_tables = {}
        for key, table in {
            "vouchers": "reproduction_vouchers",
            "outbox": "outbox",
            "credit_transactions": "credit_transactions",
        }.items():
            exists = (
                await s.execute(text("SELECT to_regclass(:table_name)"), {"table_name": table})
            ).scalar_one()
            if exists is None:
                optional_tables[key] = 0
                continue
            if table == "outbox":
                optional_tables[key] = int(
                    (await s.execute(text("SELECT COUNT(*) FROM outbox"))).scalar_one()
                )
            elif table == "credit_transactions":
                optional_tables[key] = int(
                    (
                        await s.execute(
                            text("SELECT COUNT(*) FROM credit_transactions WHERE user_id = :uid"),
                            {"uid": user_id},
                        )
                    ).scalar_one()
                )
            else:
                optional_tables[key] = int(
                    (
                        await s.execute(
                            text("SELECT COUNT(*) FROM reproduction_vouchers WHERE user_id = :uid"),
                            {"uid": user_id},
                        )
                    ).scalar_one()
                )
        return {
            "optimizations": int(
                (
                    await s.execute(
                        text("SELECT COUNT(*) FROM optimizations WHERE user_id = :uid"),
                        {"uid": user_id},
                    )
                ).scalar_one()
            ),
            "predictions": int(
                (
                    await s.execute(
                        text("SELECT COUNT(*) FROM predictions WHERE user_id = :uid"),
                        {"uid": user_id},
                    )
                ).scalar_one()
            ),
            "optimization_idempotency_keys": int(
                (
                    await s.execute(
                        text("SELECT COUNT(*) FROM idempotency_keys WHERE user_id = :uid"),
                        {"uid": user_id},
                    )
                ).scalar_one()
            ),
            "prediction_idempotency_keys": int(
                (
                    await s.execute(
                        text(
                            "SELECT COUNT(*) FROM prediction_idempotency_keys WHERE user_id = :uid"
                        ),
                        {"uid": user_id},
                    )
                ).scalar_one()
            ),
            "job_templates": int(
                (
                    await s.execute(
                        text(
                            "SELECT COUNT(*) FROM job_templates "
                            "WHERE user_id = :uid AND deleted_at IS NULL"
                        ),
                        {"uid": user_id},
                    )
                ).scalar_one()
            ),
            **optional_tables,
        }


def _hash_envelope(source_kind: str, payload_schema_version: str, payload: dict) -> str:  # type: ignore[type-arg]
    envelope = {
        "payload_json": payload,
        "payload_schema_version": payload_schema_version,
        "source_kind": source_kind,
    }
    canon = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def test_local_init_schema_contains_job_templates_contract() -> None:
    schema = Path("infra/local-init/02-solver-schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS job_templates" in schema
    assert "payload_schema_version" in schema
    assert "uq_job_templates_active_root_source_name" in schema
    assert "uq_job_templates_active_root_version" in schema
    assert "ck_job_templates_source_kind" in schema


async def test_save_prediction_template_sanitizes_hashes_and_replays_duplicate(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    prediction_id = await _insert_prediction(db_engine, user_id=user_id, api_key_id=api_key_id)
    before = await _counts(db_engine, user_id)

    response = await client_with_db.post(
        "/v1/job-templates",
        json={
            "name": "  月度销量基线  ",
            "description": "  saved from completed prediction  ",
            "source_kind": "prediction",
            "source_id": str(prediction_id),
        },
        headers={"Authorization": auth},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "月度销量基线"
    assert body["description"] == "saved from completed prediction"
    assert body["source_kind"] == "prediction"
    assert body["source_id"] == str(prediction_id)
    assert body["task_type"] == "forecast"
    assert body["payload_schema_version"] == "prediction_request_v1"
    assert body["payload_json"] == {"family": "arima", "data": [1.0, 2.0, 3.0, 4.0], "horizon": 3}
    assert body["payload_sha256"] == _hash_envelope(
        "prediction", "prediction_request_v1", body["payload_json"]
    )
    assert body["version"] == 1
    assert body["root_template_id"] == body["id"]
    assert body["parent_template_id"] is None
    assert "_system" not in response.text
    assert "charge_id" not in response.text
    assert "prediction" not in json.dumps(body["payload_json"]).lower()
    assert auth not in response.text

    duplicate = await client_with_db.post(
        "/v1/job-templates",
        json={
            "name": "月度销量基线",
            "source_kind": "prediction",
            "source_id": str(prediction_id),
        },
        headers={"Authorization": auth},
    )

    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["id"] == body["id"]
    after = await _counts(db_engine, user_id)
    assert after == {
        **before,
        "job_templates": before["job_templates"] + 1,
    }


async def test_create_template_rejects_client_supplied_payload_and_lineage_fields(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    prediction_id = await _insert_prediction(db_engine, user_id=user_id, api_key_id=api_key_id)

    response = await client_with_db.post(
        "/v1/job-templates",
        json={
            "name": "malicious-template",
            "source_kind": "prediction",
            "source_id": str(prediction_id),
            "payload_json": {"family": "arima", "data": [9], "horizon": 1},
            "version": 99,
            "root_template_id": str(uuid.uuid4()),
            "parent_template_id": str(uuid.uuid4()),
        },
        headers={"Authorization": auth},
    )

    assert response.status_code == 422, response.text
    body = response.json()
    rejected_fields = {error["field_path"] for error in body["errors"]}
    assert {"payload_json", "version", "root_template_id", "parent_template_id"}.issubset(
        rejected_fields
    )
    assert (await _counts(db_engine, user_id))["job_templates"] == 0


async def test_duplicate_template_save_race_returns_existing_row(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    prediction_id = await _insert_prediction(db_engine, user_id=user_id, api_key_id=api_key_id)
    before = await _counts(db_engine, user_id)

    first, second = await asyncio.gather(
        client_with_db.post(
            "/v1/job-templates",
            json={
                "name": "并发保存模板",
                "source_kind": "prediction",
                "source_id": str(prediction_id),
            },
            headers={"Authorization": auth},
        ),
        client_with_db.post(
            "/v1/job-templates",
            json={
                "name": "并发保存模板",
                "source_kind": "prediction",
                "source_id": str(prediction_id),
            },
            headers={"Authorization": auth},
        ),
    )

    statuses = sorted([first.status_code, second.status_code])
    bodies = [first.json(), second.json()]
    assert statuses == [200, 201]
    assert bodies[0]["id"] == bodies[1]["id"]
    after = await _counts(db_engine, user_id)
    assert after["job_templates"] == before["job_templates"] + 1


async def test_template_version_creation_updates_prediction_payload_and_history(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    prediction_id = await _insert_prediction(db_engine, user_id=user_id, api_key_id=api_key_id)
    root = await client_with_db.post(
        "/v1/job-templates",
        json={
            "name": "预测版本链",
            "source_kind": "prediction",
            "source_id": str(prediction_id),
        },
        headers={"Authorization": auth},
    )
    assert root.status_code == 201, root.text
    before = await _counts(db_engine, user_id)

    version = await client_with_db.post(
        f"/v1/job-templates/{root.json()['id']}/versions",
        json={"parameter_path": "horizon", "value": 5, "description": "horizon v2"},
        headers={"Authorization": auth},
    )

    assert version.status_code == 201, version.text
    body = version.json()
    assert body["id"] != root.json()["id"]
    assert body["version"] == 2
    assert body["root_template_id"] == root.json()["id"]
    assert body["parent_template_id"] == root.json()["id"]
    assert body["description"] == "horizon v2"
    assert body["payload_json"] == {
        "family": "arima",
        "data": [1.0, 2.0, 3.0, 4.0],
        "horizon": 5,
    }
    assert body["payload_sha256"] == _hash_envelope(
        "prediction", "prediction_request_v1", body["payload_json"]
    )

    history = await client_with_db.get(
        f"/v1/job-templates/{body['id']}/versions",
        headers={"Authorization": auth},
    )

    assert history.status_code == 200, history.text
    items = history.json()["items"]
    assert [item["version"] for item in items] == [1, 2]
    assert "payload_json" not in items[0]
    assert [item["id"] for item in items] == [root.json()["id"], body["id"]]
    after = await _counts(db_engine, user_id)
    assert after == {**before, "job_templates": before["job_templates"] + 1}


async def test_template_version_concurrent_creation_allocates_unique_versions(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    prediction_id = await _insert_prediction(db_engine, user_id=user_id, api_key_id=api_key_id)
    root = await client_with_db.post(
        "/v1/job-templates",
        json={
            "name": "并发版本链",
            "source_kind": "prediction",
            "source_id": str(prediction_id),
        },
        headers={"Authorization": auth},
    )
    assert root.status_code == 201, root.text
    root_id = root.json()["id"]

    responses = await asyncio.gather(
        *(
            client_with_db.post(
                f"/v1/job-templates/{root_id}/versions",
                json={"parameter_path": "horizon", "value": value},
                headers={"Authorization": auth},
            )
            for value in (4, 5, 6, 7)
        )
    )

    assert all(response.status_code == 201 for response in responses), [
        response.text for response in responses
    ]
    bodies = [response.json() for response in responses]
    assert sorted(body["version"] for body in bodies) == [2, 3, 4, 5]
    assert len({body["version"] for body in bodies}) == 4
    assert len({body["id"] for body in bodies}) == 4

    history = await client_with_db.get(
        f"/v1/job-templates/{root_id}/versions",
        headers={"Authorization": auth},
    )

    assert history.status_code == 200, history.text
    assert [item["version"] for item in history.json()["items"]] == [1, 2, 3, 4, 5]


async def test_template_version_creation_updates_optimization_payload(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    optimization_id = await _insert_optimization(
        db_engine,
        user_id=user_id,
        api_key_id=api_key_id,
        input_payload={
            "task_type": "lp",
            "minimize": {"c": [1.0, 1.0]},
            "st": {"A": [[1.0, 1.0]], "b": [10.0]},
            "options": {"max_solve_seconds": 30.0, "top_k_alternatives": 1},
            "solver": "highs",
        },
    )
    root = await client_with_db.post(
        "/v1/job-templates",
        json={
            "name": "LP 版本链",
            "source_kind": "optimization",
            "source_id": str(optimization_id),
        },
        headers={"Authorization": auth},
    )
    assert root.status_code == 201, root.text

    version = await client_with_db.post(
        f"/v1/job-templates/{root.json()['id']}/versions",
        json={"parameter_path": "options.max_solve_seconds", "value": 45.0},
        headers={"Authorization": auth},
    )

    assert version.status_code == 201, version.text
    body = version.json()
    assert body["version"] == 2
    assert body["payload_json"] == {
        "task_type": "lp",
        "st": {"A": [[1.0, 1.0]], "b": [10.0]},
        "options": {"max_solve_seconds": 45.0, "top_k_alternatives": 1},
        "minimize": {"c": [1.0, 1.0]},
        "solver": "highs",
    }
    assert body["payload_sha256"] == _hash_envelope(
        "optimization", "optimization_request_v1", body["payload_json"]
    )


async def test_template_version_rejects_invalid_paths_values_and_cross_user_access(
    client_with_db: AsyncClient,
    api_key,
    second_api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    second_auth, _, _ = second_api_key
    prediction_id = await _insert_prediction(db_engine, user_id=user_id, api_key_id=api_key_id)
    root = await client_with_db.post(
        "/v1/job-templates",
        json={
            "name": "非法版本路径",
            "source_kind": "prediction",
            "source_id": str(prediction_id),
        },
        headers={"Authorization": auth},
    )
    assert root.status_code == 201, root.text
    root_id = root.json()["id"]
    before = await _counts(db_engine, user_id)

    invalid_path = await client_with_db.post(
        f"/v1/job-templates/{root_id}/versions",
        json={"parameter_path": "_system.billing", "value": {"charge_id": "leak"}},
        headers={"Authorization": auth},
    )
    invalid_value = await client_with_db.post(
        f"/v1/job-templates/{root_id}/versions",
        json={"parameter_path": "horizon", "value": 0},
        headers={"Authorization": auth},
    )
    cross_user = await client_with_db.post(
        f"/v1/job-templates/{root_id}/versions",
        json={"parameter_path": "horizon", "value": 4},
        headers={"Authorization": second_auth},
    )
    forbidden_fields = await client_with_db.post(
        f"/v1/job-templates/{root_id}/versions",
        json={
            "parameter_path": "horizon",
            "value": 4,
            "payload_json": {"horizon": 4},
            "version": 99,
            "root_template_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
        },
        headers={"Authorization": auth},
    )

    assert invalid_path.status_code == 422, invalid_path.text
    assert invalid_path.json()["errors"][0]["field_path"] == "parameter_path"
    assert invalid_value.status_code == 422, invalid_value.text
    assert invalid_value.json()["errors"][0]["field_path"] == "horizon"
    assert cross_user.status_code == 404, cross_user.text
    cross_user_body = cross_user.json()
    assert cross_user_body["errors"] == [
        {
            "field_path": "$",
            "value": None,
            "constraint": "resource must exist and be visible to the caller",
            "remediation_hint_key": "errors.404.not_found",
        }
    ]
    assert forbidden_fields.status_code == 422, forbidden_fields.text
    rejected_fields = {error["field_path"] for error in forbidden_fields.json()["errors"]}
    assert {"payload_json", "version", "root_template_id", "user_id"}.issubset(rejected_fields)
    assert await _counts(db_engine, user_id) == before


async def test_template_version_soft_delete_hides_only_selected_version(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    prediction_id = await _insert_prediction(db_engine, user_id=user_id, api_key_id=api_key_id)
    root = await client_with_db.post(
        "/v1/job-templates",
        json={
            "name": "删除版本链",
            "source_kind": "prediction",
            "source_id": str(prediction_id),
        },
        headers={"Authorization": auth},
    )
    assert root.status_code == 201, root.text
    version = await client_with_db.post(
        f"/v1/job-templates/{root.json()['id']}/versions",
        json={"parameter_path": "horizon", "value": 4},
        headers={"Authorization": auth},
    )
    assert version.status_code == 201, version.text

    deleted = await client_with_db.delete(
        f"/v1/job-templates/{version.json()['id']}",
        headers={"Authorization": auth},
    )
    history = await client_with_db.get(
        f"/v1/job-templates/{root.json()['id']}/versions",
        headers={"Authorization": auth},
    )
    next_version = await client_with_db.post(
        f"/v1/job-templates/{root.json()['id']}/versions",
        json={"parameter_path": "horizon", "value": 5},
        headers={"Authorization": auth},
    )

    assert deleted.status_code == 204, deleted.text
    assert [item["version"] for item in history.json()["items"]] == [1]
    assert next_version.status_code == 201, next_version.text
    assert next_version.json()["version"] == 3


async def test_save_optimization_template_keeps_submit_compatible_payload_shape(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    optimization_id = await _insert_optimization(db_engine, user_id=user_id, api_key_id=api_key_id)

    response = await client_with_db.post(
        "/v1/job-templates",
        json={
            "name": "LP baseline",
            "source_kind": "optimization",
            "source_id": str(optimization_id),
        },
        headers={"Authorization": auth},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["task_type"] == "lp"
    assert body["payload_schema_version"] == "optimization_request_v1"
    assert body["payload_json"] == {
        "task_type": "lp",
        "minimize": {"c": [1.0, 1.0]},
        "st": {"A": [[1.0, 1.0]], "b": [10.0]},
        "options": {"max_solve_seconds": 30.0},
        "fallback_chain": ["highs"],
    }
    assert body["payload_sha256"] == _hash_envelope(
        "optimization", "optimization_request_v1", body["payload_json"]
    )
    assert "_system" not in response.text
    assert "solution" not in response.text
    assert "reproducibility" not in response.text
    assert "charge_id" not in response.text


async def test_optimization_template_rebuilds_payload_from_allowed_request_fields(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    optimization_id = await _insert_optimization(
        db_engine,
        user_id=user_id,
        api_key_id=api_key_id,
        input_payload={
            "task_type": "lp",
            "maximize": {"c": [2.0, 3.0], "shadow": "drop"},
            "st": {"a": [[1.0, 0.0]], "b": [5.0], "dual": "drop"},
            "options": {
                "max_solve_seconds": 10.0,
                "top_k_alternatives": 2,
                "internal_timeout": "drop",
            },
            "solver": "highs",
            "fallback_chain": ["scipy"],
            "solution": {"x": [1.0, 2.0]},
            "objective": 8.0,
            "billing": {"charge_id": str(uuid.uuid4())},
            "idempotency_key": "idem-secret",
            "api_key": "sk-secret",
            "raw_file_bytes": "AA==",
        },
    )

    response = await client_with_db.post(
        "/v1/job-templates",
        json={
            "name": "LP whitelist",
            "source_kind": "optimization",
            "source_id": str(optimization_id),
        },
        headers={"Authorization": auth},
    )

    assert response.status_code == 201, response.text
    assert response.json()["payload_json"] == {
        "task_type": "lp",
        "st": {"A": [[1.0, 0.0]], "b": [5.0]},
        "options": {"max_solve_seconds": 10.0, "top_k_alternatives": 2},
        "maximize": {"c": [2.0, 3.0]},
        "solver": "highs",
        "fallback_chain": ["scipy"],
    }
    response_text = response.text
    assert "solution" not in response_text
    assert "objective" not in response_text
    assert "billing" not in response_text
    assert "idempotency_key" not in response_text
    assert "sk-secret" not in response_text
    assert "raw_file_bytes" not in response_text


@pytest.mark.parametrize(
    "status_value", ["queued", "in_progress", "failed", "timeout", "cancelled"]
)
async def test_save_rejects_non_completed_sources(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    status_value: str,
) -> None:
    auth, user_id, api_key_id = api_key
    prediction_id = await _insert_prediction(
        db_engine, user_id=user_id, api_key_id=api_key_id, status=status_value
    )

    response = await client_with_db.post(
        "/v1/job-templates",
        json={
            "name": f"bad-{status_value}",
            "source_kind": "prediction",
            "source_id": str(prediction_id),
        },
        headers={"Authorization": auth},
    )

    assert response.status_code == 422, response.text
    body = response.json()
    assert body["title"] == "Source Task Not Completed"
    assert body["errors"][0]["field_path"] == "source_id"
    assert body["errors"][0]["value"] == str(prediction_id)


async def test_template_source_and_template_access_are_owner_scoped(
    client_with_db: AsyncClient,
    api_key,
    second_api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    second_auth, _, _ = second_api_key
    prediction_id = await _insert_prediction(db_engine, user_id=user_id, api_key_id=api_key_id)

    cross_save = await client_with_db.post(
        "/v1/job-templates",
        json={
            "name": "cross-user",
            "source_kind": "prediction",
            "source_id": str(prediction_id),
        },
        headers={"Authorization": second_auth},
    )
    assert cross_save.status_code == 404, cross_save.text
    assert str(prediction_id) not in cross_save.text

    saved = await client_with_db.post(
        "/v1/job-templates",
        json={
            "name": "owner template",
            "source_kind": "prediction",
            "source_id": str(prediction_id),
        },
        headers={"Authorization": auth},
    )
    assert saved.status_code == 201, saved.text
    template_id = saved.json()["id"]

    owner_detail = await client_with_db.get(
        f"/v1/job-templates/{template_id}",
        headers={"Authorization": auth},
    )
    cross_detail = await client_with_db.get(
        f"/v1/job-templates/{template_id}",
        headers={"Authorization": second_auth},
    )
    cross_delete = await client_with_db.delete(
        f"/v1/job-templates/{template_id}",
        headers={"Authorization": second_auth},
    )

    assert owner_detail.status_code == 200, owner_detail.text
    assert owner_detail.json()["payload_json"]["family"] == "arima"
    assert cross_detail.status_code == 404, cross_detail.text
    assert cross_delete.status_code == 404, cross_delete.text

    deleted = await client_with_db.delete(
        f"/v1/job-templates/{template_id}",
        headers={"Authorization": auth},
    )
    second_delete = await client_with_db.delete(
        f"/v1/job-templates/{template_id}",
        headers={"Authorization": auth},
    )
    detail_after_delete = await client_with_db.get(
        f"/v1/job-templates/{template_id}",
        headers={"Authorization": auth},
    )
    list_after_delete = await client_with_db.get(
        "/v1/job-templates",
        headers={"Authorization": auth},
    )

    assert deleted.status_code == 204, deleted.text
    assert second_delete.status_code == 404, second_delete.text
    assert detail_after_delete.status_code == 404, detail_after_delete.text
    assert all(item["id"] != template_id for item in list_after_delete.json()["items"])


async def test_list_templates_is_owner_scoped_newest_first_and_compact(
    client_with_db: AsyncClient,
    api_key,
    second_api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    second_auth, second_user_id, second_api_key_id = second_api_key
    first_source = await _insert_prediction(db_engine, user_id=user_id, api_key_id=api_key_id)
    second_source = await _insert_prediction(db_engine, user_id=user_id, api_key_id=api_key_id)
    other_source = await _insert_prediction(
        db_engine, user_id=second_user_id, api_key_id=second_api_key_id
    )

    first = await client_with_db.post(
        "/v1/job-templates",
        json={"name": "first", "source_kind": "prediction", "source_id": str(first_source)},
        headers={"Authorization": auth},
    )
    second = await client_with_db.post(
        "/v1/job-templates",
        json={"name": "second", "source_kind": "prediction", "source_id": str(second_source)},
        headers={"Authorization": auth},
    )
    other = await client_with_db.post(
        "/v1/job-templates",
        json={"name": "other", "source_kind": "prediction", "source_id": str(other_source)},
        headers={"Authorization": second_auth},
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert other.status_code == 201, other.text

    listed = await client_with_db.get("/v1/job-templates", headers={"Authorization": auth})

    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    ids = [item["id"] for item in items]
    assert ids.index(second.json()["id"]) < ids.index(first.json()["id"])
    assert other.json()["id"] not in ids
    assert "payload_json" not in items[0]
    assert "data" not in listed.text
