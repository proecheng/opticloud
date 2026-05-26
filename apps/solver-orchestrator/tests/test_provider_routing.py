"""Story 2.6 - FR C6 provider routing contract tests."""

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
from solver_orchestrator import billing_client
from solver_orchestrator.catalog import CATALOG
from solver_orchestrator.config import settings
from solver_orchestrator.db import get_session
from solver_orchestrator.main import app
from solver_orchestrator.provider_routing import (
    ProviderRouteStatus,
    provider_route_to_system_metadata,
    select_provider_route,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


DATABASE_URL = os.getenv("DATABASE_URL", settings.database_url)

_LP_BODY = {
    "task_type": "lp",
    "minimize": {"c": [1.0, 1.0]},
    "st": {"A": [[1.0, 1.0]], "b": [10.0]},
}


def _make_api_key() -> tuple[str, str, int]:
    random_part = uuid.uuid4().hex
    full = f"sk-{random_part}"
    pepper_version = 1
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    key_hash = hmac.new(pepper, full.encode("utf-8"), hashlib.sha256).hexdigest()
    return full, key_hash, pepper_version


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine():
    eng = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def api_key(db_engine) -> AsyncIterator[tuple[str, uuid.UUID]]:
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
                "email": f"2-6-{user_id}@example.com",
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
                "label": "2-6-test",
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
async def client_with_db(db_engine) -> AsyncIterator[AsyncClient]:
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


def test_helper_routes_lp_default_to_highs() -> None:
    route = select_provider_route("lp", None)

    assert route.status is ProviderRouteStatus.OK
    assert route.algorithm is not None
    assert route.algorithm["k_algo"] == "highs-lp"
    assert route.selected_solver == "highs"
    assert route.model_version["provider_id"] == "highs"
    assert route.provider_kind == "open_source"


def test_helper_routes_forecast_explicit_solver_to_matching_algorithm() -> None:
    route = select_provider_route("forecast", "arima")

    assert route.status is ProviderRouteStatus.OK
    assert route.algorithm is not None
    assert route.algorithm["k_algo"] == "arima-forecast"
    assert route.selected_solver == "arima"
    assert route.model_version["provider_id"] == "statsmodels-arima"


def test_helper_routes_self_provider() -> None:
    route = select_provider_route("nlp", "aqgs")

    assert route.status is ProviderRouteStatus.OK
    assert route.algorithm is not None
    assert route.algorithm["k_algo"] == "aqgs-acopf"
    assert route.provider_kind == "self"


def test_helper_returns_unsupported_task_type() -> None:
    route = select_provider_route("unknown-task", None)

    assert route.status is ProviderRouteStatus.UNSUPPORTED_TASK_TYPE
    assert route.algorithm is None
    assert route.supported_solvers == []


def test_helper_returns_unsupported_solver_with_union_supported() -> None:
    route = select_provider_route("forecast", "does-not-exist")

    assert route.status is ProviderRouteStatus.UNSUPPORTED_SOLVER
    assert route.algorithm is None
    assert "arima" in route.supported_solvers
    assert "lstm" in route.supported_solvers
    assert "chronos-t5" in route.supported_solvers


def test_helper_returns_copied_model_version_metadata() -> None:
    route = select_provider_route("lp", None)
    assert route.status is ProviderRouteStatus.OK
    assert route.algorithm is not None

    metadata = provider_route_to_system_metadata(
        route,
        task_type="lp",
        requested_solver=None,
    )
    metadata["provider_id"] = "mutated"
    route.model_version["provider_id"] = "mutated-too"
    route.algorithm["model_version"]["provider_id"] = "mutated-algorithm"
    route.algorithm["supported_solvers"].append("mutated-solver")

    catalog_highs = next(a for a in CATALOG if a["k_algo"] == "highs-lp")
    assert catalog_highs["model_version"]["provider_id"] == "highs"
    assert catalog_highs["supported_solvers"] == ["highs"]


async def test_demo_lp_uses_routed_model_version_and_locked_solver(
    demo_client: AsyncClient,
) -> None:
    resp = await demo_client.post(
        "/v1/optimizations/demo",
        json={**_LP_BODY, "solver": "highs", "options": {"reproducible": True}},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["model_version"]["provider_id"] == "highs"
    assert body["model_version"]["kind"] == "open_source"
    assert body["reproducibility"]["locked_model_version"] == body["model_version"]
    assert body["reproducibility"]["locked_solver"] == "highs"


async def test_demo_invalid_solver_still_returns_unsupported_solver(
    demo_client: AsyncClient,
) -> None:
    resp = await demo_client.post(
        "/v1/optimizations/demo",
        json={**_LP_BODY, "solver": "garbage"},
    )

    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["title"] == "Unsupported Solver"
    assert body["errors"][0]["field_path"] == "solver"


async def test_demo_non_lp_preview_still_short_circuits_before_lp_validation(
    demo_client: AsyncClient,
) -> None:
    resp = await demo_client.post(
        "/v1/optimizations/demo",
        json={"task_type": "vrptw", "vehicles": [], "customers": []},
    )

    assert resp.status_code == 501, resp.text
    assert resp.json()["title"] == "Not Implemented"


async def test_authenticated_route_persists_provider_route_with_reproducibility(
    client_with_db: AsyncClient,
    api_key,
    db_engine,
    monkeypatch,
) -> None:
    auth, _ = api_key

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("billing should not run without X-Billing-Charge-Id")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)

    resp = await client_with_db.post(
        "/v1/optimizations",
        json={**_LP_BODY, "solver": "highs", "options": {"reproducible": True}},
        headers={"Authorization": auth},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reproducibility"]["locked_solver"] == "highs"
    assert "provider_route" not in body

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (
            await s.execute(
                text("SELECT input_payload FROM optimizations WHERE id = :id"),
                {"id": uuid.UUID(body["optimization_id"])},
            )
        ).scalar_one()

    system = row["_system"]
    assert system["reproducibility"]["locked_solver"] == "highs"
    provider_route = system["provider_route"]
    assert provider_route["task_type"] == "lp"
    assert provider_route["requested_solver"] == "highs"
    assert provider_route["selected_solver"] == "highs"
    assert provider_route["provider_id"] == "highs"
    assert provider_route["provider_kind"] == "open_source"
    assert provider_route["provider_url"] == "https://highs.dev/"
    assert provider_route["routing_reason"] == "explicit_solver"


async def test_authenticated_route_omitted_solver_records_selected_solver_cost_metadata(
    client_with_db: AsyncClient,
    api_key,
    db_engine,
    monkeypatch,
) -> None:
    auth, _ = api_key

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("billing should not run without X-Billing-Charge-Id")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)

    resp = await client_with_db.post(
        "/v1/optimizations",
        json=_LP_BODY,
        headers={"Authorization": auth},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "provider_route" not in body

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (
            await s.execute(
                text("SELECT metadata FROM cost_attribution WHERE source_id = :id"),
                {"id": uuid.UUID(body["optimization_id"])},
            )
        ).scalar_one()

    assert row["solver"] == "highs"
    assert row["model_provider"] == "highs"
