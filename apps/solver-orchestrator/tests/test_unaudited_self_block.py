"""Story 2.8 - FR C8 unaudited self-developed algorithm block tests."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import sys
import uuid
from collections.abc import AsyncIterator
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from solver_orchestrator import billing_client, solvers
from solver_orchestrator import catalog as catalog_module
from solver_orchestrator.catalog import (
    CATALOG,
    publishable_catalog_items,
    self_audit_missing_rules,
    self_audit_passed,
)
from solver_orchestrator.config import settings
from solver_orchestrator.db import get_session
from solver_orchestrator.fallback_execution import FallbackPlanStatus, build_fallback_attempts
from solver_orchestrator.main import app
from solver_orchestrator.provider_routing import ProviderRouteStatus, select_provider_route
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

_LP_SHAPED_NLP_BODY = {
    "task_type": "nlp",
    "solver": "aqgs",
    "minimize": {"c": [1.0, 1.0]},
    "st": {"A": [[1.0, 1.0]], "b": [10.0]},
}


def _make_api_key() -> tuple[str, str, int]:
    random_part = f"t28{uuid.uuid4().hex}"
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
                "email": f"2-8-{user_id}@example.com",
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
                "label": "2-8-test",
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


def test_aqgs_has_missing_self_audit_rules() -> None:
    aqgs = next(item for item in CATALOG if item["k_algo"] == "aqgs-acopf")

    missing = self_audit_missing_rules(aqgs)

    assert missing
    assert "paper_reproduction_result" in missing
    assert self_audit_passed(aqgs) is False


def test_publishable_catalog_excludes_unaudited_self_and_keeps_open_source() -> None:
    items = publishable_catalog_items()
    k_algos = {item["k_algo"] for item in items}

    assert "aqgs-acopf" not in k_algos
    assert "highs-lp" in k_algos


def test_malformed_self_audit_metadata_fails_closed() -> None:
    aqgs = deepcopy(next(item for item in CATALOG if item["k_algo"] == "aqgs-acopf"))
    aqgs["self_audit"] = {
        "package_or_runnable": True,
        "license_approved": True,
        "minimal_example_30m": True,
        "readme_schema": True,
        "paper_reproduction_result": True,
        "unexpected_rule": True,  # type: ignore[typeddict-unknown-key]
    }

    assert self_audit_missing_rules(aqgs) == [
        "package_or_runnable",
        "license_approved",
        "minimal_example_30m",
        "readme_schema",
        "paper_reproduction_result",
    ]
    assert self_audit_passed(aqgs) is False


async def test_public_algorithm_list_hides_unaudited_self(
    public_client: AsyncClient,
) -> None:
    all_resp = await public_client.get("/v1/algorithms")
    nlp_resp = await public_client.get("/v1/algorithms?task_type=nlp")

    assert all_resp.status_code == 200
    assert nlp_resp.status_code == 200
    assert "aqgs-acopf" not in {item["k_algo"] for item in all_resp.json()}
    assert all("self_audit" not in item for item in all_resp.json())
    assert nlp_resp.json() == []


async def test_public_algorithm_detail_for_unaudited_self_is_unpublished(
    public_client: AsyncClient,
) -> None:
    resp = await public_client.get("/v1/algorithms/aqgs-acopf")

    assert resp.status_code == 404
    assert "not published" in resp.json()["detail"]


def test_provider_routing_blocks_unaudited_self_with_ticket() -> None:
    route = select_provider_route("nlp", "aqgs")

    assert route.status is ProviderRouteStatus.UNAUDITED_SELF_ALGORITHM
    assert route.algorithm is None
    assert route.blocked_k_algo == "aqgs-acopf"
    assert route.blocked_provider_id == "aqgs"
    assert route.audit_ticket_id == "self-audit-aqgs-acopf-aqgs"
    assert "paper_reproduction_result" in route.missing_self_audit_rules


def test_provider_routing_still_allows_open_source_routes() -> None:
    lp_route = select_provider_route("lp", None)
    forecast_route = select_provider_route("forecast", "arima")

    assert lp_route.status is ProviderRouteStatus.OK
    assert lp_route.selected_solver == "highs"
    assert forecast_route.status is ProviderRouteStatus.OK
    assert forecast_route.model_version["provider_id"] == "statsmodels-arima"


async def test_authenticated_unaudited_self_blocks_before_side_effects(
    client_with_db: AsyncClient,
    api_key,
    db_engine: AsyncEngine,
    monkeypatch,
) -> None:
    auth, user_id = api_key
    charge_id = uuid.uuid4()
    idempotency_key = f"2-8-unaudited-{uuid.uuid4()}"

    async def _billing_should_not_run(*args, **kwargs):
        raise AssertionError("billing should not run for unaudited self block")

    def _solve_should_not_run(*args, **kwargs):
        raise AssertionError("solver should not run for unaudited self block")

    monkeypatch.setattr(billing_client, "reserve", _billing_should_not_run)
    monkeypatch.setattr(billing_client, "finalize", _billing_should_not_run)
    monkeypatch.setattr(solvers, "solve_from_request", _solve_should_not_run)

    resp = await client_with_db.post(
        "/v1/optimizations",
        json=_LP_SHAPED_NLP_BODY,
        headers={
            "Authorization": auth,
            "X-Billing-Charge-Id": str(charge_id),
            "Idempotency-Key": idempotency_key,
        },
    )

    assert resp.status_code == 403, resp.text
    body = resp.json()
    serialized = str(body)
    assert body["title"] == "Unaudited Self Algorithm"
    assert body["errors"][0]["field_path"] == "solver"
    assert body["next_action_url"].endswith("/admin/self-audit/self-audit-aqgs-acopf-aqgs")
    assert "paper_reproduction_result" in body["errors"][0]["constraint"]
    assert "sk-" not in serialized
    assert str(charge_id) not in serialized
    assert str(user_id) not in serialized
    assert "_system" not in serialized

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        count = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM optimizations WHERE user_id = :uid AND task_type = 'nlp'"
                ),
                {"uid": user_id},
            )
        ).scalar_one()
        idempotency_count = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM idempotency_keys "
                    "WHERE user_id = :uid AND key = :idempotency_key"
                ),
                {"uid": user_id, "idempotency_key": idempotency_key},
            )
        ).scalar_one()
    assert count == 0
    assert idempotency_count == 0


async def test_authenticated_default_unaudited_self_uses_task_type_field_path(
    client_with_db: AsyncClient,
    api_key,
) -> None:
    auth, _ = api_key
    payload = dict(_LP_SHAPED_NLP_BODY)
    payload.pop("solver")

    resp = await client_with_db.post(
        "/v1/optimizations",
        json=payload,
        headers={"Authorization": auth},
    )

    assert resp.status_code == 403, resp.text
    body = resp.json()
    assert body["title"] == "Unaudited Self Algorithm"
    assert body["errors"][0]["field_path"] == "task_type"
    assert body["errors"][0]["value"] == "aqgs-acopf"


def test_fallback_planner_propagates_same_task_unaudited_self_block(monkeypatch) -> None:
    open_source = deepcopy(next(item for item in CATALOG if item["k_algo"] == "highs-lp"))
    open_source["k_algo"] = "test-mixed-open"
    open_source["task_type"] = "test-mixed"
    open_source["supported_solvers"] = ["highs"]
    unaudited_self = deepcopy(next(item for item in CATALOG if item["k_algo"] == "aqgs-acopf"))
    unaudited_self["k_algo"] = "test-mixed-self"
    unaudited_self["task_type"] = "test-mixed"
    unaudited_self["supported_solvers"] = ["aqgs"]
    monkeypatch.setattr(catalog_module, "CATALOG", [open_source, unaudited_self])

    primary = select_provider_route("test-mixed", None)

    plan = build_fallback_attempts(
        primary_route=primary,
        task_type="test-mixed",
        requested_solver=None,
        fallback_chain=["aqgs"],
    )

    assert plan.status is FallbackPlanStatus.UNAUDITED_SELF_ALGORITHM
    assert plan.audit_ticket_id == "self-audit-test-mixed-self-aqgs"
    assert plan.invalid_candidate == "aqgs"
    assert plan.supported_solvers == ["highs", "aqgs"]
