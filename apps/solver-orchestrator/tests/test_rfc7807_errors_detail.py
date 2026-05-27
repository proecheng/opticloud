"""Story 3.7 - RFC 7807 errors[] detail + next_action_url contract tests."""

from __future__ import annotations

import asyncio
import ast
import hashlib
import hmac
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

ROOT_DIR = Path(__file__).resolve().parents[3]
PYTHON_SDK_SRC_DIR = ROOT_DIR / "packages" / "python-sdk" / "src"
if str(PYTHON_SDK_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_SDK_SRC_DIR))

from opticloud.errors import OptiCloudHTTPError
from solver_orchestrator.config import settings
from solver_orchestrator.db import get_session
from solver_orchestrator.main import app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


DATABASE_URL = os.getenv("DATABASE_URL", settings.database_url)


def _make_api_key() -> tuple[str, str, int]:
    random_part = f"t37{uuid.uuid4().hex}"
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
                "email": f"3-7-{user_id}@example.com",
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
                "label": "3-7-test",
                "prefix": full[:6],
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
async def demo_client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _assert_problem_shape(
    response: Any,
    *,
    status_code: int,
    field_path: str,
    remediation_prefix: str,
    next_action_required: bool = True,
) -> dict[str, Any]:
    assert response.status_code == status_code, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["status"] == status_code
    assert body["type"].startswith("https://api.opticloud.cn/errors/")
    assert body["instance"]
    assert body["request_id"]
    assert "trace_id" in body
    assert "next_action" not in body
    if next_action_required:
        assert body["next_action_url"]
    detail = body["errors"][0]
    assert detail["field_path"] == field_path
    assert detail["constraint"]
    assert detail["remediation_hint_key"].startswith(remediation_prefix)
    return body


def test_error_catalog_has_required_locales_and_remediation_keys() -> None:
    from solver_orchestrator.error_catalog import ERROR_CATALOG

    assert ERROR_CATALOG
    for key, entry in ERROR_CATALOG.items():
        assert entry.slug
        assert entry.remediation_hint_key.startswith(f"errors.{entry.status}.")
        assert entry.title["en-US"]
        assert entry.title["zh-CN"]
        assert entry.detail["en-US"]
        assert entry.detail["zh-CN"]
        if 400 <= entry.status < 500:
            assert entry.next_action_url, key


def test_error_response_code_does_not_serialize_next_action_key() -> None:
    root = Path(__file__).resolve().parents[1]
    checked = [
        root / "src" / "solver_orchestrator" / "error_responses.py",
        root / "src" / "solver_orchestrator" / "routes.py",
    ]
    for path in checked:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key in node.keys:
                    if isinstance(key, ast.Constant) and key.value == "next_action":
                        raise AssertionError(f"{path} serializes forbidden response key next_action")


async def test_demo_invalid_solver_has_complete_problem_shape_and_sdk_locate(
    demo_client: AsyncClient,
) -> None:
    response = await demo_client.post(
        "/v1/optimizations/demo",
        json={
            "task_type": "lp",
            "solver": "garbage",
            "minimize": {"c": [1.0, 1.0]},
            "st": {"A": [[1.0, 1.0]], "b": [10.0]},
        },
        headers={"X-Request-Id": "req-test-3-7"},
    )

    body = _assert_problem_shape(
        response,
        status_code=400,
        field_path="solver",
        remediation_prefix="errors.400.",
    )
    assert body["title"] == "Unsupported Solver"
    assert body["request_id"] == "req-test-3-7"
    sdk_error = OptiCloudHTTPError.from_response(response.status_code, body)
    assert sdk_error.locate("solver") == "garbage"
    assert sdk_error.next_action_url == body["next_action_url"]
    assert sdk_error.raw == body


async def test_accept_language_zh_localizes_title_and_detail_only(
    demo_client: AsyncClient,
) -> None:
    response = await demo_client.post(
        "/v1/optimizations/demo",
        json={
            "task_type": "lp",
            "solver": "garbage",
            "minimize": {"c": [1.0, 1.0]},
            "st": {"A": [[1.0, 1.0]], "b": [10.0]},
        },
        headers={"Accept-Language": "zh-CN,zh;q=0.9"},
    )

    body = _assert_problem_shape(
        response,
        status_code=400,
        field_path="solver",
        remediation_prefix="errors.400.",
    )
    assert body["title"] == "不支持的求解器"
    assert "garbage" in body["detail"]
    assert "detail_zh" not in body
    assert "detail_en" not in body


async def test_fastapi_body_validation_error_is_problem_details(
    client_with_db: AsyncClient,
    api_key: tuple[str, uuid.UUID],
) -> None:
    auth, _ = api_key
    response = await client_with_db.post(
        "/v1/optimizations",
        json={"task_type": "lp", "minimize": {"c": [1.0, 1.0]}, "st": {"A": [[1.0]]}},
        headers={"Authorization": auth},
    )

    body = _assert_problem_shape(
        response,
        status_code=422,
        field_path="st.b",
        remediation_prefix="errors.422.",
    )
    assert body["title"] == "Invalid Request Body"


async def test_missing_authorization_is_rfc7807_and_redacted(
    demo_client: AsyncClient,
) -> None:
    response = await demo_client.post(
        "/v1/predictions",
        json={"family": "arima", "data": [1, 2, 3]},
    )

    body = _assert_problem_shape(
        response,
        status_code=401,
        field_path="header.Authorization",
        remediation_prefix="errors.401.",
    )
    assert body["errors"][0]["value"] == "[redacted]"
    assert "sk-" not in str(body)


async def test_idempotency_conflict_redacts_submitted_key(
    client_with_db: AsyncClient,
    api_key: tuple[str, uuid.UUID],
) -> None:
    auth, _ = api_key
    key = f"idem-sensitive-{uuid.uuid4()}"
    payload = {"family": "arima", "data": [1, 2, 3]}
    first = await client_with_db.post(
        "/v1/predictions",
        json=payload,
        headers={"Authorization": auth, "Idempotency-Key": key},
    )
    assert first.status_code == 200, first.text

    response = await client_with_db.post(
        "/v1/predictions",
        json={**payload, "horizon": 4},
        headers={"Authorization": auth, "Idempotency-Key": key},
    )

    body = _assert_problem_shape(
        response,
        status_code=409,
        field_path="header.Idempotency-Key",
        remediation_prefix="errors.409.",
    )
    assert body["errors"][0]["value"] == "[redacted]"
    assert key not in str(body)


async def test_prediction_validation_keeps_precise_field_path_and_next_action(
    client_with_db: AsyncClient,
    api_key: tuple[str, uuid.UUID],
) -> None:
    auth, _ = api_key
    response = await client_with_db.post(
        "/v1/predictions",
        json={"family": "arima", "data": [1, 2, 1.0e13]},
        headers={"Authorization": auth},
    )

    body = _assert_problem_shape(
        response,
        status_code=422,
        field_path="data[2]",
        remediation_prefix="errors.422.",
    )
    assert body["title"] == "Invalid Prediction Data"


async def test_demo_non_lp_501_is_actionable_problem(
    demo_client: AsyncClient,
) -> None:
    response = await demo_client.post(
        "/v1/optimizations/demo",
        json={"task_type": "vrptw", "vehicles": [], "customers": []},
    )

    _assert_problem_shape(
        response,
        status_code=501,
        field_path="task_type",
        remediation_prefix="errors.501.",
    )
