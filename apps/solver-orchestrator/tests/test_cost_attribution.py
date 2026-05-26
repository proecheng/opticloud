"""Story M2.3 — solver cost attribution integration tests."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from opticloud_shared.cost_telemetry import CostTelemetryEvent
from solver_orchestrator import billing_client
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


def _make_api_key() -> tuple[str, str, int]:
    random_part = uuid.uuid4().hex
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
                "email": f"m23-{user_id}@example.com",
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
                "label": "m2-3-test",
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


_LP_BODY = {
    "task_type": "lp",
    "minimize": {"c": [1.0, 1.0]},
    "st": {"A": [[1.0, 1.0]], "b": [10.0]},
}


async def _count_cost_rows(
    engine: AsyncEngine,
    *,
    user_id: uuid.UUID | None = None,
    source_id: uuid.UUID | None = None,
) -> int:
    params: dict[str, object] = {}
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        if user_id is not None and source_id is not None:
            params["uid"] = user_id
            params["sid"] = source_id
            query = text(
                "SELECT COUNT(*) FROM cost_attribution WHERE tenant_id = :uid AND source_id = :sid"
            )
        elif user_id is not None:
            params["uid"] = user_id
            query = text("SELECT COUNT(*) FROM cost_attribution WHERE tenant_id = :uid")
        elif source_id is not None:
            params["sid"] = source_id
            query = text("SELECT COUNT(*) FROM cost_attribution WHERE source_id = :sid")
        else:
            query = text("SELECT COUNT(*) FROM cost_attribution")
        return int((await s.execute(query, params)).scalar_one())


async def _fetch_cost_row(engine: AsyncEngine, source_id: uuid.UUID) -> dict[str, object]:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (
            (
                await s.execute(
                    text(
                        "SELECT tenant_id, service, cost_unit, value, source_id, metadata "
                        "FROM cost_attribution WHERE source_id = :sid"
                    ),
                    {"sid": source_id},
                )
            )
            .mappings()
            .one()
        )
        return dict(row)


async def test_authenticated_success_records_solver_second_cost(
    client_with_db: AsyncClient, api_key, db_engine: AsyncEngine, monkeypatch
) -> None:
    """M2.3 AC5 — completed authenticated solve inserts one solver_second row."""
    auth, user_id = api_key

    async def _reserve(*args, **kwargs):
        raise AssertionError("no billing header should avoid reserve")

    async def _finalize(*args, **kwargs):
        raise AssertionError("no billing header should avoid finalize")

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)

    response = await client_with_db.post(
        "/v1/optimizations",
        json=_LP_BODY,
        headers={"Authorization": auth},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    source_id = uuid.UUID(body["optimization_id"])
    row = await _fetch_cost_row(db_engine, source_id)
    assert row["tenant_id"] == user_id
    assert row["service"] == "solver-orchestrator"
    assert row["cost_unit"] == "solver_second"
    assert row["source_id"] == source_id
    assert row["value"] >= 0
    assert row["metadata"]["task_type"] == "lp"
    assert row["metadata"]["status"] == "optimal"


async def test_infeasible_solve_records_one_cost_row(
    client_with_db: AsyncClient, api_key, db_engine: AsyncEngine, monkeypatch
) -> None:
    """M2.3 AC7 — persisted infeasible terminal result is attributed once."""
    auth, user_id = api_key

    async def _reserve(*args, **kwargs):
        raise AssertionError("no billing header should avoid reserve")

    async def _finalize(*args, **kwargs):
        raise AssertionError("no billing header should avoid finalize")

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)
    before = await _count_cost_rows(db_engine, user_id=user_id)

    response = await client_with_db.post(
        "/v1/optimizations",
        json={
            "task_type": "lp",
            "minimize": {"c": [1.0]},
            "st": {"A": [[1.0]], "b": [-1.0]},
        },
        headers={"Authorization": auth},
    )

    assert response.status_code == 422, response.text
    after = await _count_cost_rows(db_engine, user_id=user_id)
    assert after == before + 1


async def test_idempotency_replay_does_not_duplicate_cost_rows(
    client_with_db: AsyncClient, api_key, db_engine: AsyncEngine, monkeypatch
) -> None:
    """M2.3 AC7 — cached successful replay returns same opt without a second row."""
    auth, _ = api_key

    async def _reserve(*args, **kwargs):
        raise AssertionError("no billing header should avoid reserve")

    async def _finalize(*args, **kwargs):
        raise AssertionError("no billing header should avoid finalize")

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)
    idem_key = f"m23-cost-{uuid.uuid4()}"
    headers = {"Authorization": auth, "Idempotency-Key": idem_key}

    first = await client_with_db.post("/v1/optimizations", json=_LP_BODY, headers=headers)
    second = await client_with_db.post("/v1/optimizations", json=_LP_BODY, headers=headers)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["optimization_id"] == first.json()["optimization_id"]
    source_id = uuid.UUID(first.json()["optimization_id"])
    assert await _count_cost_rows(db_engine, source_id=source_id) == 1


async def test_demo_route_writes_zero_cost_rows(
    client_with_db: AsyncClient, db_engine: AsyncEngine
) -> None:
    """M2.3 AC8 — unauthenticated demo remains stateless for cost attribution."""
    before = await _count_cost_rows(db_engine)

    response = await client_with_db.post("/v1/optimizations/demo", json=_LP_BODY)

    assert response.status_code == 200, response.text
    assert await _count_cost_rows(db_engine) == before


async def test_cost_insert_failure_does_not_block_success_response(
    client_with_db: AsyncClient, api_key, monkeypatch
) -> None:
    """M2.3 AC6 — attribution failure logs and preserves the solve response."""
    auth, _ = api_key

    async def _reserve(*args, **kwargs):
        raise AssertionError("no billing header should avoid reserve")

    async def _finalize(*args, **kwargs):
        raise AssertionError("no billing header should avoid finalize")

    def _broken_kwargs(self):
        raise ValueError("synthetic attribution failure")

    monkeypatch.setattr(billing_client, "reserve", _reserve)
    monkeypatch.setattr(billing_client, "finalize", _finalize)
    monkeypatch.setattr(CostTelemetryEvent, "as_record_kwargs", _broken_kwargs)

    response = await client_with_db.post(
        "/v1/optimizations",
        json=_LP_BODY,
        headers={"Authorization": auth},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"
