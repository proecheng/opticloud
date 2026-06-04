"""Story 8.C.9 - Teaching Mode Grading API tests."""

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
from solver_orchestrator import routes
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

MODEL_VERSION = {
    "provider_id": "highs",
    "kind": "open_source",
    "version": "1.7.0",
    "provider_url": "https://highs.dev/",
}

TEACHING_METADATA = {
    "mode": "teaching",
    "principle_explanation": {
        "title_zh": "线性规划教学模式",
        "summary_zh": "线性目标函数和约束解释",
        "modeling_steps_zh": ["定义变量", "写目标函数", "写约束"],
        "limitations_zh": ["仅覆盖教学算例"],
    },
    "credits_discount": {
        "kind": "teaching",
        "label_zh": "50% Credits 折扣",
        "discount_multiplier": 0.5,
    },
    "notebook": {
        "label_zh": "LP 教学 Notebook",
        "repo_path": "docs/notebooks/teaching-lp.ipynb",
        "colab_url": "https://example.test/teaching-lp.ipynb",
    },
}


def _make_api_key(prefix: str = "t8c9") -> tuple[str, str, int]:
    random_part = f"{prefix}{uuid.uuid4().hex}"
    full = f"sk-{random_part}"
    pepper_version = 1
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    key_hash = hmac.new(pepper, full.encode("utf-8"), hashlib.sha256).hexdigest()
    return full, key_hash, pepper_version


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    await _ensure_teaching_grading_tables(eng)
    yield eng
    await eng.dispose()


async def _ensure_teaching_grading_tables(db_engine: AsyncEngine) -> None:
    async with db_engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS teaching_grading_batches (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL,
                    api_key_id UUID NOT NULL,
                    assignment_ref VARCHAR(80) NOT NULL,
                    rubric_version VARCHAR(64) NOT NULL,
                    item_count INTEGER NOT NULL,
                    graded_count INTEGER NOT NULL,
                    not_gradable_count INTEGER NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS teaching_grading_items (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    grading_batch_id UUID NOT NULL
                        REFERENCES teaching_grading_batches(id) ON DELETE CASCADE,
                    user_id UUID NOT NULL,
                    item_index INTEGER NOT NULL,
                    student_ref VARCHAR(80) NOT NULL,
                    optimization_id UUID NOT NULL,
                    gradable_optimization_id UUID NULL REFERENCES optimizations(id),
                    grading_status VARCHAR(32) NOT NULL,
                    score NUMERIC(6, 2) NOT NULL,
                    max_score NUMERIC(6, 2) NOT NULL,
                    criteria JSONB NOT NULL,
                    feedback_zh TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS teaching_grading_idempotency_keys (
                    user_id UUID NOT NULL,
                    key VARCHAR(255) NOT NULL,
                    grading_batch_id UUID NOT NULL
                        REFERENCES teaching_grading_batches(id) ON DELETE CASCADE,
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
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_teaching_grading_items_batch_index
                ON teaching_grading_items(grading_batch_id, item_index)
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_teaching_grading_items_batch_student
                ON teaching_grading_items(grading_batch_id, student_ref)
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_teaching_grading_items_batch_optimization
                ON teaching_grading_items(grading_batch_id, optimization_id)
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_teaching_grading_batches_user_created
                ON teaching_grading_batches(user_id, created_at DESC)
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_teaching_grading_items_user_batch_index
                ON teaching_grading_items(user_id, grading_batch_id, item_index)
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
                "email": f"8-c-9-{label}-{user_id}@example.com",
                "phone": f"+8689{user_id.int % 10**8:08d}",
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
                "label": f"8-c-9-{label}",
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


async def _insert_optimization(
    db_engine: AsyncEngine,
    *,
    user_id: uuid.UUID,
    api_key_id: uuid.UUID,
    status: str = "completed",
    teaching: bool = True,
    solution: dict | None = None,  # type: ignore[type-arg]
) -> uuid.UUID:
    optimization_id = uuid.uuid4()
    system_payload = {
        "provider_route": {"selected_solver": "highs"},
        "billing": {"charge_id": str(uuid.uuid4())},
    }
    if teaching:
        system_payload["teaching"] = TEACHING_METADATA
    payload = {
        "task_type": "lp",
        "minimize": {"c": [1.0, 1.0]},
        "st": {"A": [[1.0, 1.0]], "b": [10.0]},
        "_system": system_payload,
    }
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
                     CAST(:solution AS jsonb), 10.0, CAST(:model_version AS jsonb),
                     0.03, :now, :completed_at)
                """
            ),
            {
                "id": optimization_id,
                "uid": user_id,
                "api_key_id": api_key_id,
                "status": status,
                "input_payload": json.dumps(payload),
                "solution": json.dumps(solution if solution is not None else {"x": [0.0, 10.0]}),
                "model_version": json.dumps(MODEL_VERSION),
                "now": datetime.now(UTC),
                "completed_at": datetime.now(UTC) if status == "completed" else None,
            },
        )
        await s.commit()
    return optimization_id


async def _grading_counts(db_engine: AsyncEngine, user_id: uuid.UUID) -> dict[str, int]:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        return {
            "batches": int(
                (
                    await s.execute(
                        text("SELECT COUNT(*) FROM teaching_grading_batches WHERE user_id = :uid"),
                        {"uid": user_id},
                    )
                ).scalar_one()
            ),
            "items": int(
                (
                    await s.execute(
                        text("SELECT COUNT(*) FROM teaching_grading_items WHERE user_id = :uid"),
                        {"uid": user_id},
                    )
                ).scalar_one()
            ),
            "idempotency": int(
                (
                    await s.execute(
                        text(
                            "SELECT COUNT(*) FROM teaching_grading_idempotency_keys "
                            "WHERE user_id = :uid"
                        ),
                        {"uid": user_id},
                    )
                ).scalar_one()
            ),
        }


async def test_create_grading_batch_persists_ordered_items_and_get_replays(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    gradable_id = await _insert_optimization(
        db_engine, user_id=user_id, api_key_id=api_key_id, teaching=True
    )
    non_teaching_id = await _insert_optimization(
        db_engine, user_id=user_id, api_key_id=api_key_id, teaching=False
    )
    missing_id = uuid.uuid4()

    response = await client_with_db.post(
        "/v1/teaching/grading-batches",
        json={
            "assignment_ref": "assign-001",
            "submissions": [
                {"student_ref": "stu-001", "optimization_id": str(gradable_id)},
                {"student_ref": "stu-002", "optimization_id": str(non_teaching_id)},
                {"student_ref": "stu-003", "optimization_id": str(missing_id)},
            ],
        },
        headers={"Authorization": auth, "Idempotency-Key": "8-c-9-create-1"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["assignment_ref"] == "assign-001"
    assert body["rubric_version"] == "teaching-grading-v1"
    assert body["item_count"] == 3
    assert body["graded_count"] == 1
    assert body["not_gradable_count"] == 2
    assert [item["student_ref"] for item in body["items"]] == ["stu-001", "stu-002", "stu-003"]
    assert body["items"][0]["grading_status"] == "graded"
    assert body["items"][0]["score"] == 100.0
    assert [criterion["code"] for criterion in body["items"][0]["criteria"]] == [
        "teaching_mode",
        "completed_status",
        "solution_available",
        "explanation_ready",
    ]
    assert body["items"][1]["grading_status"] == "not_gradable"
    assert body["items"][1]["score"] == 0.0
    assert body["items"][2]["grading_status"] == "not_gradable"
    assert body["items"][2]["feedback_zh"] == body["items"][1]["feedback_zh"]
    assert "_system" not in response.text
    assert "charge_id" not in response.text
    assert '"x"' not in response.text
    assert "example.com" not in response.text

    fetched = await client_with_db.get(
        f"/v1/teaching/grading-batches/{body['grading_batch_id']}",
        headers={"Authorization": auth},
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json() == body
    assert await _grading_counts(db_engine, user_id) == {
        "batches": 1,
        "items": 3,
        "idempotency": 1,
    }


async def test_grading_batch_idempotency_default_version_replay_and_conflict(
    client_with_db: AsyncClient,
    api_key,
    second_api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    second_auth, second_user_id, second_api_key_id = second_api_key
    optimization_id = await _insert_optimization(
        db_engine, user_id=user_id, api_key_id=api_key_id, teaching=True
    )
    second_optimization_id = await _insert_optimization(
        db_engine, user_id=second_user_id, api_key_id=second_api_key_id, teaching=True
    )
    first_body = {
        "assignment_ref": "assign-002",
        "submissions": [{"student_ref": "stu-010", "optimization_id": str(optimization_id)}],
    }
    explicit_default_body = {
        **first_body,
        "rubric_version": "teaching-grading-v1",
    }

    first = await client_with_db.post(
        "/v1/teaching/grading-batches",
        json=first_body,
        headers={"Authorization": auth, "Idempotency-Key": "8-c-9-idem"},
    )
    replay = await client_with_db.post(
        "/v1/teaching/grading-batches",
        json=explicit_default_body,
        headers={"Authorization": auth, "Idempotency-Key": "8-c-9-idem"},
    )
    conflict = await client_with_db.post(
        "/v1/teaching/grading-batches",
        json={
            "assignment_ref": "assign-002b",
            "submissions": [{"student_ref": "stu-010", "optimization_id": str(optimization_id)}],
        },
        headers={"Authorization": auth, "Idempotency-Key": "8-c-9-idem"},
    )
    cross_user = await client_with_db.post(
        "/v1/teaching/grading-batches",
        json={
            "assignment_ref": "assign-002",
            "submissions": [
                {"student_ref": "stu-010", "optimization_id": str(second_optimization_id)}
            ],
        },
        headers={"Authorization": second_auth, "Idempotency-Key": "8-c-9-idem"},
    )

    assert first.status_code == 201, first.text
    assert replay.status_code == 200, replay.text
    assert replay.json() == first.json()
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["title"] == "Idempotency Conflict"
    assert cross_user.status_code == 201, cross_user.text
    assert cross_user.json()["grading_batch_id"] != first.json()["grading_batch_id"]


async def test_concurrent_same_key_create_does_not_duplicate_batch(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    optimization_id = await _insert_optimization(
        db_engine, user_id=user_id, api_key_id=api_key_id, teaching=True
    )
    before = await _grading_counts(db_engine, user_id)

    responses = await asyncio.gather(
        *(
            client_with_db.post(
                "/v1/teaching/grading-batches",
                json={
                    "assignment_ref": "assign-concurrent",
                    "submissions": [
                        {"student_ref": "stu-concurrent", "optimization_id": str(optimization_id)}
                    ],
                },
                headers={"Authorization": auth, "Idempotency-Key": "8-c-9-concurrent"},
            )
            for _ in range(2)
        )
    )

    statuses = sorted(response.status_code for response in responses)
    assert statuses in ([200, 201], [201, 409]), [response.text for response in responses]
    assert await _grading_counts(db_engine, user_id) == {
        "batches": before["batches"] + 1,
        "items": before["items"] + 1,
        "idempotency": before["idempotency"] + 1,
    }


async def test_late_idempotency_integrity_error_rolls_back_partial_batch(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth, user_id, api_key_id = api_key
    optimization_id = await _insert_optimization(
        db_engine, user_id=user_id, api_key_id=api_key_id, teaching=True
    )
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        seed_batch_id = uuid.uuid4()
        await s.execute(
            text(
                """
                INSERT INTO teaching_grading_batches
                    (id, user_id, api_key_id, assignment_ref, rubric_version,
                     item_count, graded_count, not_gradable_count)
                VALUES
                    (:id, :uid, :api_key_id, 'assign-seed', 'teaching-grading-v1', 0, 0, 0)
                """
            ),
            {"id": seed_batch_id, "uid": user_id, "api_key_id": api_key_id},
        )
        await s.execute(
            text(
                """
                INSERT INTO teaching_grading_idempotency_keys
                    (user_id, key, grading_batch_id, request_body_hash, expires_at)
                VALUES
                    (:uid, '8-c-9-race', :batch_id, 'seed-hash', :expires_at)
                """
            ),
            {
                "uid": user_id,
                "batch_id": seed_batch_id,
                "expires_at": datetime.now(UTC) + timedelta(hours=1),
            },
        )
        await s.commit()

    before = await _grading_counts(db_engine, user_id)

    async def _pretend_no_replay(*args, **kwargs):
        return None, False

    monkeypatch.setattr(routes, "_load_teaching_grading_idempotency_replay", _pretend_no_replay)

    response = await client_with_db.post(
        "/v1/teaching/grading-batches",
        json={
            "assignment_ref": "assign-race",
            "submissions": [{"student_ref": "stu-race", "optimization_id": str(optimization_id)}],
        },
        headers={"Authorization": auth, "Idempotency-Key": "8-c-9-race"},
    )

    assert response.status_code == 409, response.text
    assert await _grading_counts(db_engine, user_id) == before


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("assignment_ref", "作业一"),
        ("assignment_ref", "assignment one"),
        ("student_ref", "student@example.edu"),
        ("student_ref", "stu/001"),
        ("student_ref", "zhangsan"),
    ],
)
async def test_grading_request_rejects_pii_like_refs_without_writes(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    field: str,
    value: str,
) -> None:
    auth, user_id, api_key_id = api_key
    optimization_id = await _insert_optimization(
        db_engine, user_id=user_id, api_key_id=api_key_id, teaching=True
    )
    before = await _grading_counts(db_engine, user_id)
    body = {
        "assignment_ref": "assign-003",
        "submissions": [{"student_ref": "stu-020", "optimization_id": str(optimization_id)}],
    }
    if field == "assignment_ref":
        body["assignment_ref"] = value
    else:
        body["submissions"][0]["student_ref"] = value

    response = await client_with_db.post(
        "/v1/teaching/grading-batches",
        json=body,
        headers={"Authorization": auth, "Idempotency-Key": f"8-c-9-invalid-{field}"},
    )

    assert response.status_code == 422, response.text
    errors = response.json()["errors"]
    assert errors
    assert errors[0]["value"] == "[redacted]"
    assert value not in response.text
    assert await _grading_counts(db_engine, user_id) == before


async def test_grading_rejects_duplicate_refs_unsupported_rubric_and_allows_assignment_reuse(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, user_id, api_key_id = api_key
    first_id = await _insert_optimization(
        db_engine, user_id=user_id, api_key_id=api_key_id, teaching=True
    )
    second_id = await _insert_optimization(
        db_engine, user_id=user_id, api_key_id=api_key_id, teaching=True
    )

    duplicate_student = await client_with_db.post(
        "/v1/teaching/grading-batches",
        json={
            "assignment_ref": "assign-004",
            "submissions": [
                {"student_ref": "stu-030", "optimization_id": str(first_id)},
                {"student_ref": "stu-030", "optimization_id": str(second_id)},
            ],
        },
        headers={"Authorization": auth},
    )
    unsupported_rubric = await client_with_db.post(
        "/v1/teaching/grading-batches",
        json={
            "assignment_ref": "assign-004",
            "rubric_version": "teaching-grading-v2",
            "submissions": [{"student_ref": "stu-031", "optimization_id": str(first_id)}],
        },
        headers={"Authorization": auth},
    )
    first = await client_with_db.post(
        "/v1/teaching/grading-batches",
        json={
            "assignment_ref": "assign-004",
            "submissions": [{"student_ref": "stu-032", "optimization_id": str(first_id)}],
        },
        headers={"Authorization": auth},
    )
    second = await client_with_db.post(
        "/v1/teaching/grading-batches",
        json={
            "assignment_ref": "assign-004",
            "submissions": [{"student_ref": "stu-033", "optimization_id": str(second_id)}],
        },
        headers={"Authorization": auth},
    )

    assert duplicate_student.status_code == 422, duplicate_student.text
    assert unsupported_rubric.status_code == 422, unsupported_rubric.text
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["grading_batch_id"] != second.json()["grading_batch_id"]


async def test_cross_owner_batch_and_optimization_are_masked(
    client_with_db: AsyncClient,
    api_key,
    second_api_key,
    db_engine: AsyncEngine,
) -> None:
    auth, _user_id, _api_key_id = api_key
    second_auth, second_user_id, second_api_key_id = second_api_key
    other_optimization_id = await _insert_optimization(
        db_engine, user_id=second_user_id, api_key_id=second_api_key_id, teaching=True
    )
    other_batch = await client_with_db.post(
        "/v1/teaching/grading-batches",
        json={
            "assignment_ref": "assign-005",
            "submissions": [
                {"student_ref": "stu-040", "optimization_id": str(other_optimization_id)}
            ],
        },
        headers={"Authorization": second_auth},
    )
    assert other_batch.status_code == 201, other_batch.text

    cross_get = await client_with_db.get(
        f"/v1/teaching/grading-batches/{other_batch.json()['grading_batch_id']}",
        headers={"Authorization": auth},
    )
    cross_optimization = await client_with_db.post(
        "/v1/teaching/grading-batches",
        json={
            "assignment_ref": "assign-006",
            "submissions": [
                {"student_ref": "stu-041", "optimization_id": str(other_optimization_id)}
            ],
        },
        headers={"Authorization": auth},
    )

    assert cross_get.status_code == 404, cross_get.text
    assert cross_optimization.status_code == 201, cross_optimization.text
    item = cross_optimization.json()["items"][0]
    assert item["grading_status"] == "not_gradable"
    assert item["score"] == 0.0
    assert "other" not in item["feedback_zh"].lower()


def test_local_init_schema_contains_teaching_grading_contract() -> None:
    schema = (REPO_ROOT / "infra/local-init/02-solver-schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS teaching_grading_batches" in schema
    assert "CREATE TABLE IF NOT EXISTS teaching_grading_items" in schema
    assert "CREATE TABLE IF NOT EXISTS teaching_grading_idempotency_keys" in schema
    assert "idx_teaching_grading_batches_user_created" in schema
    assert "idx_teaching_grading_items_user_batch_index" in schema
    assert "uq_teaching_grading_items_batch_index" in schema
    assert "uq_teaching_grading_items_batch_student" in schema
    assert "uq_teaching_grading_items_batch_optimization" in schema
    assert "PRIMARY KEY (user_id, key)" in schema
