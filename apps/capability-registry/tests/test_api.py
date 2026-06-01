"""Capability-registry API and schema tests."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import asyncpg
import capability_registry.routes as registry_routes
import pytest
import pytest_asyncio
from capability_registry.config import settings
from capability_registry.db import get_session
from capability_registry.main import app
from capability_registry.routes import get_cache
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

DATABASE_URL = os.getenv("DATABASE_URL", settings.database_url)
ASYNCPG_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
ROOT_DIR = Path(__file__).resolve().parents[3]
SCHEMA_PATH = ROOT_DIR / "infra" / "local-init" / "14-capability-registry.sql"
SCHEMA_SQL = SCHEMA_PATH.read_text()
OPENAPI_PATH = ROOT_DIR / "packages" / "shared-ts" / "openapi" / "capability-registry.json"
SHA = "a" * 64
DIGEST = f"registry.example.com/solver@sha256:{'b' * 64}"


class FakeCache:
    def __init__(self, *, unavailable: bool = False) -> None:
        self.store: dict[str, Any] = {}
        self.unavailable = unavailable
        self.get_count = 0

    async def get_json(self, key: str) -> Any | None:
        self.get_count += 1
        if self.unavailable:
            raise ConnectionError("redis unavailable")
        return self.store.get(key)

    async def set_json(self, key: str, value: Any) -> None:
        if self.unavailable:
            raise ConnectionError("redis unavailable")
        self.store[key] = value

    async def delete_pattern(self, pattern: str) -> None:
        if self.unavailable:
            raise ConnectionError("redis unavailable")
        prefix = pattern.removesuffix("*")
        for key in list(self.store):
            if key.startswith(prefix):
                del self.store[key]


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    conn = await asyncpg.connect(ASYNCPG_URL)
    try:
        await conn.execute(SCHEMA_SQL)
        await conn.execute(SCHEMA_SQL)
    finally:
        await conn.close()
    eng = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(engine: AsyncEngine) -> AsyncIterator[None]:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await session.execute(
            text(
                "TRUNCATE provider_application_evaluation_requests, provider_applications, "
                "revenue_share_hooks, revenue_share_policies, "
                "provider_oauth_flows, capability_tags, capabilities, "
                "capability_providers RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()
    yield


@pytest_asyncio.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    fake_cache = FakeCache()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_cache() -> FakeCache:
        return fake_cache

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_cache] = override_cache
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        test_client.fake_cache = fake_cache  # type: ignore[attr-defined]
        yield test_client
    app.dependency_overrides.clear()


def provider_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": "open_source",
        "display_name": "HiGHS",
        "provider_url": "https://highs.dev/",
        "status": "active",
        "openapi_url": "https://example.com/openapi.json",
        "openapi_sha256": SHA,
        "image_digest": DIGEST,
        "cosign_bundle": {"bundle_ref": "vault://cosign/highs"},
    }
    payload.update(overrides)
    return payload


def capability_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "task_type": "lp",
        "tier": "T1",
        "status": "v1",
        "provider_id": "highs",
        "model_version": "1.7.0",
        "supported_solvers": ["highs"],
        "description_zh": "线性规划",
        "description_en": "Linear programming",
        "examples": [{"name": "hello"}],
        "metadata": {"source": "test"},
        "tags": ["LP", "linear programming"],
    }
    payload.update(overrides)
    return payload


def policy_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "provider_kind": "external",
        "platform_share_ratio": "0.600000",
        "provider_share_ratio": "0.400000",
        "status": "reserved",
        "metadata": {"source": "test"},
    }
    payload.update(overrides)
    return payload


def hook_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "provider_id": "highs",
        "k_algo": "highs-lp",
        "policy_id": "external-default",
        "source_service": "billing-service",
        "source_event_id": str(uuid.uuid4()),
        "billing_saga_id": str(uuid.uuid4()),
        "period_month": "2026-06",
        "gross_amount_ref": "credit-ledger:gross:v1",
        "currency": "CNY",
        "status": "reserved",
        "metadata": {"source": "test"},
    }
    payload.update(overrides)
    return payload


def provider_application_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "requested_provider_id": "professor-lu",
        "provider_kind": "external",
        "display_name": "Professor Lu VRPTW",
        "organization_name": "Lu Lab",
        "contact_email": "provider@example.edu",
        "homepage_url": "https://lab.example.edu/provider",
        "openapi_url": "https://lab.example.edu/openapi.json",
        "openapi_sha256": SHA,
        "image_digest": DIGEST,
        "cosign_bundle": {"bundle_ref": "oss://provider-applications/professor-lu/cosign.json"},
        "evaluation_profile": {"suite_ref": "benchmark://provider-intake/lp-standard"},
        "status": "draft",
        "metadata": {"source": "test"},
    }
    payload.update(overrides)
    return payload


def provider_evaluation_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "benchmark_suite": "lp_standard_500",
        "sample_count": 500,
        "timeout_seconds": 60,
        "status": "requested",
        "dataset_refs": ["benchmark://provider-intake/lp-standard-v1"],
        "report_ref": "oss://provider-evaluations/app-professor-lu/eval-001/report.json",
        "metadata": {"source": "test"},
    }
    payload.update(overrides)
    return payload


async def test_provider_upsert_read_cache_and_invalidation(
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    put_resp = await client.put("/v1/providers/highs", json=provider_payload())
    assert put_resp.status_code == 200, put_resp.text
    assert put_resp.json()["provider_id"] == "highs"
    assert put_resp.json()["scope_source"] == "global"

    first = await client.get("/v1/providers/highs")
    assert first.status_code == 200, first.text
    assert first.json()["display_name"] == "HiGHS"
    assert len(client.fake_cache.store) >= 1  # type: ignore[attr-defined]

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await session.execute(
            text(
                "UPDATE capability_providers SET display_name = 'DB mutated' WHERE provider_id = 'highs'"
            )
        )
        await session.commit()

    cached = await client.get("/v1/providers/highs")
    assert cached.json()["display_name"] == "HiGHS"

    update_resp = await client.put(
        "/v1/providers/highs",
        json=provider_payload(display_name="HiGHS updated"),
    )
    assert update_resp.status_code == 200, update_resp.text
    assert client.fake_cache.store == {}  # type: ignore[attr-defined]

    fresh = await client.get("/v1/providers/highs")
    assert fresh.json()["display_name"] == "HiGHS updated"


async def test_capability_tenant_scope_and_global_fallback(client: AsyncClient) -> None:
    await client.put("/v1/providers/highs", json=provider_payload())
    await client.put("/v1/capabilities/highs-lp", json=capability_payload())

    tenant_id = str(uuid.uuid4())
    fallback = await client.get(f"/v1/capabilities/highs-lp?tenant_id={tenant_id}")
    assert fallback.status_code == 200, fallback.text
    assert fallback.json()["scope_source"] == "global_fallback"
    assert fallback.json()["model_version"] == {
        "provider_id": "highs",
        "kind": "open_source",
        "version": "1.7.0",
        "provider_url": "https://highs.dev/",
    }
    assert fallback.json()["tags"] == ["linear_programming", "lp"]

    tenant_cap = await client.put(
        "/v1/capabilities/highs-lp",
        json=capability_payload(tenant_id=tenant_id, model_version="1.8.0"),
    )
    assert tenant_cap.status_code == 200, tenant_cap.text
    assert tenant_cap.json()["scope_source"] == "tenant"

    tenant_read = await client.get(f"/v1/capabilities/highs-lp?tenant_id={tenant_id}")
    assert tenant_read.json()["scope_source"] == "tenant"
    assert tenant_read.json()["model_version"]["version"] == "1.8.0"


async def test_schema_constraints_prevent_duplicate_global_rows(engine: AsyncEngine) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await session.execute(
            text(
                "INSERT INTO capability_providers(provider_id, kind, display_name, provider_url) "
                "VALUES ('highs', 'open_source', 'HiGHS', 'https://highs.dev/')"
            )
        )
        await session.commit()
    async with maker() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    "INSERT INTO capability_providers(provider_id, kind, display_name, provider_url) "
                    "VALUES ('highs', 'open_source', 'HiGHS again', 'https://highs.dev/')"
                )
            )
            await session.commit()


async def test_oauth_flow_is_reference_only_and_execute_is_not_implemented(
    client: AsyncClient,
) -> None:
    await client.put("/v1/providers/highs", json=provider_payload())
    bad = await client.put(
        "/v1/providers/highs/oauth-flow",
        json={
            "authorization_url": "https://provider.example/oauth/authorize",
            "token_url": "https://provider.example/oauth/token",
            "client_id_ref": "vault://providers/highs/client-id",
            "client_secret": "raw-secret",
        },
    )
    assert bad.status_code == 422

    good = await client.put(
        "/v1/providers/highs/oauth-flow",
        json={
            "authorization_url": "https://provider.example/oauth/authorize",
            "token_url": "https://provider.example/oauth/token",
            "scopes": ["capability.read", "capability.write"],
            "status": "configured",
            "client_id_ref": "vault://providers/highs/client-id",
            "client_secret_ref": "vault://providers/highs/client-secret",
            "vault_secret_ref": "vault://providers/highs/oauth",
        },
    )
    assert good.status_code == 200, good.text
    body = good.json()
    assert "client_secret" not in body
    assert "access_token" not in body
    assert body["client_secret_ref"].startswith("vault://")

    execute = await client.post("/v1/providers/highs/oauth-flow/execute")
    assert execute.status_code == 501


async def test_write_protection_when_internal_secret_configured(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "capability_registry.routes.settings.internal_secret",
        SecretStr("internal-test-secret"),
    )

    missing = await client.put("/v1/providers/highs", json=provider_payload())
    assert missing.status_code == 401

    wrong = await client.put(
        "/v1/providers/highs",
        json=provider_payload(),
        headers={"X-Internal-Service-Auth": "wrong"},
    )
    assert wrong.status_code == 401

    ok = await client.put(
        "/v1/providers/highs",
        json=provider_payload(),
        headers={"X-Internal-Service-Auth": "internal-test-secret"},
    )
    assert ok.status_code == 200, ok.text


async def test_redis_unavailable_falls_back_to_database(
    engine: AsyncEngine,
) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    unavailable_cache = FakeCache(unavailable=True)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            yield session
            await session.commit()

    async def override_cache() -> FakeCache:
        return unavailable_cache

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_cache] = override_cache
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as test_client:
            create = await test_client.put("/v1/providers/highs", json=provider_payload())
            assert create.status_code == 200, create.text
            read = await test_client.get("/v1/providers/highs")
            assert read.status_code == 200, read.text
            assert read.json()["provider_id"] == "highs"
    finally:
        app.dependency_overrides.clear()


async def test_path_body_mismatch_and_missing_resources(client: AsyncClient) -> None:
    mismatch = await client.put(
        "/v1/providers/highs",
        json=provider_payload(provider_id="or-tools"),
    )
    assert mismatch.status_code == 422

    invalid_path = await client.put("/v1/providers/Invalid!", json=provider_payload())
    assert invalid_path.status_code == 422

    missing = await client.get("/v1/providers/does-not-exist")
    assert missing.status_code == 404

    missing_provider = await client.put(
        "/v1/capabilities/highs-lp",
        json=capability_payload(provider_id="does-not-exist"),
    )
    assert missing_provider.status_code == 422

    invalid_capability_path = await client.put(
        "/v1/capabilities/Invalid!",
        json=capability_payload(),
    )
    assert invalid_capability_path.status_code == 422


async def test_revenue_share_policy_ratios_scope_and_constraints(
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    defaults = {
        "self-default": ("self", "1.000000", "0.000000"),
        "open-source-default": ("open_source", "1.000000", "0.000000"),
        "external-default": ("external", "0.600000", "0.400000"),
        "commercial-default": ("commercial", "0.500000", "0.500000"),
    }
    for policy_id, (provider_kind, platform_ratio, provider_ratio) in defaults.items():
        response = await client.put(
            f"/v1/revenue-share/policies/{policy_id}",
            json=policy_payload(
                provider_kind=provider_kind,
                platform_share_ratio=platform_ratio,
                provider_share_ratio=provider_ratio,
            ),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["policy_id"] == policy_id
        assert body["provider_kind"] == provider_kind
        assert str(body["platform_share_ratio"]) == platform_ratio
        assert str(body["provider_share_ratio"]) == provider_ratio
        assert body["scope_source"] == "global"

    bad_ratio = await client.put(
        "/v1/revenue-share/policies/bad-ratio",
        json=policy_payload(platform_share_ratio="0.700000", provider_share_ratio="0.400000"),
    )
    assert bad_ratio.status_code == 422

    tenant_id = str(uuid.uuid4())
    tenant_policy = await client.put(
        "/v1/revenue-share/policies/external-default",
        json=policy_payload(
            tenant_id=tenant_id,
            platform_share_ratio="0.550000",
            provider_share_ratio="0.450000",
        ),
    )
    assert tenant_policy.status_code == 200, tenant_policy.text
    assert tenant_policy.json()["scope_source"] == "tenant"

    tenant_read = await client.get(
        f"/v1/revenue-share/policies/external-default?tenant_id={tenant_id}"
    )
    assert tenant_read.status_code == 200, tenant_read.text
    assert str(tenant_read.json()["platform_share_ratio"]) == "0.550000"

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    """
                    INSERT INTO revenue_share_policies(
                        policy_id,
                        provider_kind,
                        platform_share_ratio,
                        provider_share_ratio
                    )
                    VALUES ('external-default', 'external', 0.600000, 0.400000)
                    """
                )
            )
            await session.commit()
        await session.rollback()
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    """
                    INSERT INTO revenue_share_policies(
                        policy_id,
                        provider_kind,
                        platform_share_ratio,
                        provider_share_ratio
                    )
                    VALUES ('broken-sum', 'external', 0.700000, 0.400000)
                    """
                )
            )
            await session.commit()


async def test_revenue_share_hook_creation_idempotency_and_validation(
    client: AsyncClient,
) -> None:
    await client.put("/v1/providers/highs", json=provider_payload(kind="external"))
    await client.put("/v1/capabilities/highs-lp", json=capability_payload())
    await client.put("/v1/revenue-share/policies/external-default", json=policy_payload())

    event_id = str(uuid.uuid4())
    create = await client.post(
        "/v1/revenue-share/hooks",
        json=hook_payload(source_event_id=event_id),
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert body["provider_id"] == "highs"
    assert body["k_algo"] == "highs-lp"
    assert body["source_event_id"] == event_id
    assert body["period_month"] == "2026-06"
    assert body["scope_source"] == "global"

    replay = await client.post(
        "/v1/revenue-share/hooks",
        json=hook_payload(
            provider_id="different-provider",
            k_algo="different-capability",
            source_event_id=event_id,
        ),
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == body["id"]
    assert replay.json()["provider_id"] == "highs"

    invalid_month = await client.post(
        "/v1/revenue-share/hooks",
        json=hook_payload(source_event_id=str(uuid.uuid4()), period_month="2026-13"),
    )
    assert invalid_month.status_code == 422

    forbidden = await client.post(
        "/v1/revenue-share/hooks",
        json=hook_payload(source_event_id=str(uuid.uuid4()), provider_amount="12.34"),
    )
    assert forbidden.status_code == 422

    forbidden_metadata = await client.post(
        "/v1/revenue-share/hooks",
        json=hook_payload(
            source_event_id=str(uuid.uuid4()),
            metadata={"safe_ref": "ok", "nested": {"payment_ref": "pay-secret"}},
        ),
    )
    assert forbidden_metadata.status_code == 422

    missing_policy = await client.post(
        "/v1/revenue-share/hooks",
        json=hook_payload(source_event_id=str(uuid.uuid4()), policy_id="missing-policy"),
    )
    assert missing_policy.status_code == 422
    assert "policy not found" in missing_policy.text


async def test_revenue_share_hook_idempotency_recovers_from_unique_race(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await client.put("/v1/providers/highs", json=provider_payload(kind="external"))
    await client.put("/v1/capabilities/highs-lp", json=capability_payload())
    await client.put("/v1/revenue-share/policies/external-default", json=policy_payload())

    event_id = str(uuid.uuid4())
    first = await client.post(
        "/v1/revenue-share/hooks",
        json=hook_payload(source_event_id=event_id),
    )
    assert first.status_code == 200, first.text

    original_loader = registry_routes._load_revenue_hook_by_source_event
    calls = 0

    async def race_loader(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        return await original_loader(*args, **kwargs)

    monkeypatch.setattr(registry_routes, "_load_revenue_hook_by_source_event", race_loader)
    replay = await client.post(
        "/v1/revenue-share/hooks",
        json=hook_payload(source_event_id=event_id),
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == first.json()["id"]
    assert calls >= 2


async def test_revenue_share_hook_tenant_resolution_and_mismatch(
    client: AsyncClient,
) -> None:
    tenant_id = str(uuid.uuid4())
    await client.put("/v1/providers/highs", json=provider_payload(kind="external"))
    await client.put(
        "/v1/providers/or-tools",
        json=provider_payload(
            tenant_id=tenant_id,
            kind="external",
            display_name="OR-Tools",
            provider_url="https://developers.google.com/optimization",
        ),
    )
    await client.put("/v1/capabilities/highs-lp", json=capability_payload())
    await client.put(
        "/v1/capabilities/routing",
        json=capability_payload(
            tenant_id=tenant_id,
            provider_id="or-tools",
            task_type="vrptw",
            model_version="9.10",
        ),
    )
    await client.put("/v1/revenue-share/policies/external-default", json=policy_payload())

    tenant_hook = await client.post(
        "/v1/revenue-share/hooks",
        json=hook_payload(
            tenant_id=tenant_id,
            provider_id="or-tools",
            k_algo="routing",
            source_event_id=str(uuid.uuid4()),
        ),
    )
    assert tenant_hook.status_code == 200, tenant_hook.text
    assert tenant_hook.json()["scope_source"] == "tenant"

    mismatch = await client.post(
        "/v1/revenue-share/hooks",
        json=hook_payload(
            tenant_id=tenant_id,
            provider_id="highs",
            k_algo="routing",
            source_event_id=str(uuid.uuid4()),
        ),
    )
    assert mismatch.status_code == 422
    assert "capability provider mismatch" in mismatch.text


async def test_revenue_share_write_protection_when_internal_secret_configured(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "capability_registry.routes.settings.internal_secret",
        SecretStr("internal-test-secret"),
    )

    missing_policy_auth = await client.put(
        "/v1/revenue-share/policies/external-default",
        json=policy_payload(),
    )
    assert missing_policy_auth.status_code == 401

    ok_policy = await client.put(
        "/v1/revenue-share/policies/external-default",
        json=policy_payload(),
        headers={"X-Internal-Service-Auth": "internal-test-secret"},
    )
    assert ok_policy.status_code == 200, ok_policy.text

    await client.put(
        "/v1/providers/highs",
        json=provider_payload(kind="external"),
        headers={"X-Internal-Service-Auth": "internal-test-secret"},
    )
    await client.put(
        "/v1/capabilities/highs-lp",
        json=capability_payload(),
        headers={"X-Internal-Service-Auth": "internal-test-secret"},
    )

    missing_hook_auth = await client.post("/v1/revenue-share/hooks", json=hook_payload())
    assert missing_hook_auth.status_code == 401

    ok_hook = await client.post(
        "/v1/revenue-share/hooks",
        json=hook_payload(),
        headers={"X-Internal-Service-Auth": "internal-test-secret"},
    )
    assert ok_hook.status_code == 200, ok_hook.text


def test_revenue_share_openapi_omits_unsafe_fields() -> None:
    spec = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    revenue_schemas = {
        name: schema
        for name, schema in spec["components"]["schemas"].items()
        if name.startswith("RevenueShare")
    }
    assert revenue_schemas
    forbidden_terms = {
        "provider_amount",
        "platform_amount",
        "payout_status",
        "paid_at",
        "settlement_id",
        "bank_account",
        "tax_id",
        "access_token",
        "refresh_token",
        "client_secret",
    }
    for schema in revenue_schemas.values():
        properties = set(schema.get("properties", {}))
        assert properties.isdisjoint(forbidden_terms)


async def test_provider_application_upsert_read_submit_and_no_catalog_side_effect(
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    create = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(),
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert body["application_id"] == "app-professor-lu"
    assert body["requested_provider_id"] == "professor-lu"
    assert body["status"] == "draft"
    assert body["submitted_at"] is None

    read = await client.get("/v1/provider-applications/app-professor-lu")
    assert read.status_code == 200, read.text
    assert read.json()["scope_source"] == "global"

    submit = await client.post("/v1/provider-applications/app-professor-lu/submit")
    assert submit.status_code == 200, submit.text
    submitted = submit.json()
    assert submitted["status"] == "submitted"
    assert submitted["submitted_at"] is not None

    replay = await client.post("/v1/provider-applications/app-professor-lu/submit")
    assert replay.status_code == 200, replay.text
    assert replay.json()["submitted_at"] == submitted["submitted_at"]

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        provider_count = (
            await session.execute(
                text("SELECT count(*) FROM capability_providers WHERE provider_id = 'professor-lu'")
            )
        ).scalar_one()
    assert provider_count == 0


async def test_provider_application_validation_scope_and_immutability(
    client: AsyncClient,
) -> None:
    bad_kind = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(provider_kind="open_source"),
    )
    assert bad_kind.status_code == 422

    bad_url = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(openapi_url="file:///tmp/openapi.json"),
    )
    assert bad_url.status_code == 422

    bad_secret_metadata = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(metadata={"nested": {"api_key": "raw"}}),
    )
    assert bad_secret_metadata.status_code == 422

    bad_pii_metadata = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(
            metadata={"nested": {"contact_email": "leak@example.edu"}}
        ),
    )
    assert bad_pii_metadata.status_code == 422

    bad_camel_secret = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(cosign_bundle={"registryPassword": "raw"}),
    )
    assert bad_camel_secret.status_code == 422

    create = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(status="submitted"),
    )
    assert create.status_code == 200, create.text
    submitted_at = create.json()["submitted_at"]

    mutate_artifact = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(openapi_sha256="b" * 64, status="submitted"),
    )
    assert mutate_artifact.status_code == 422
    assert "immutable" in mutate_artifact.text

    back_to_draft = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(status="draft"),
    )
    assert back_to_draft.status_code == 422

    keep_non_material = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(
            display_name="Professor Lu Updated",
            status="submitted",
            submitted_at=submitted_at,
        ),
    )
    assert keep_non_material.status_code == 200, keep_non_material.text
    assert keep_non_material.json()["display_name"] == "Professor Lu Updated"
    assert keep_non_material.json()["submitted_at"] == submitted_at

    tenant_id = str(uuid.uuid4())
    tenant_read = await client.get(
        f"/v1/provider-applications/app-professor-lu?tenant_id={tenant_id}"
    )
    assert tenant_read.status_code == 200, tenant_read.text
    assert tenant_read.json()["scope_source"] == "global_fallback"

    tenant_application = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(
            tenant_id=tenant_id,
            requested_provider_id="professor-lu-tenant",
        ),
    )
    assert tenant_application.status_code == 200, tenant_application.text
    assert tenant_application.json()["scope_source"] == "tenant"

    tenant_mutation = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(
            tenant_id=str(uuid.uuid4()),
            requested_provider_id="professor-lu-other-tenant",
        ),
    )
    assert tenant_mutation.status_code == 200, tenant_mutation.text


async def test_provider_application_duplicate_requested_provider_returns_422(
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    first = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(),
    )
    assert first.status_code == 200, first.text

    duplicate_provider = await client.put(
        "/v1/provider-applications/app-professor-lu-copy",
        json=provider_application_payload(),
    )
    assert duplicate_provider.status_code == 422
    assert "requested_provider_id" in duplicate_provider.text

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    """
                    INSERT INTO provider_applications(
                        application_id,
                        requested_provider_id,
                        provider_kind,
                        display_name,
                        organization_name,
                        contact_email,
                        openapi_url,
                        openapi_sha256,
                        image_digest
                    )
                    VALUES (
                        'app-professor-lu-db',
                        'professor-lu',
                        'external',
                        'Professor Lu',
                        'Lu Lab',
                        'provider@example.edu',
                        'https://lab.example.edu/openapi.json',
                        :sha,
                        :digest
                    )
                    """
                ),
                {"sha": SHA, "digest": DIGEST},
            )
            await session.commit()


async def test_provider_evaluation_requires_submitted_application_and_valid_refs(
    client: AsyncClient,
) -> None:
    draft = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(),
    )
    assert draft.status_code == 200, draft.text

    draft_eval = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001",
        json=provider_evaluation_payload(),
    )
    assert draft_eval.status_code == 422
    assert "submitted" in draft_eval.text

    await client.post("/v1/provider-applications/app-professor-lu/submit")

    bad_dataset = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001",
        json=provider_evaluation_payload(dataset_refs=["raw,dataset,row"]),
    )
    assert bad_dataset.status_code == 422

    body_with_provider = provider_evaluation_payload()
    body_with_provider["requested_provider_id"] = "spoofed"
    spoofed_provider = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001",
        json=body_with_provider,
    )
    assert spoofed_provider.status_code == 422

    create = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001",
        json=provider_evaluation_payload(status="queued"),
    )
    assert create.status_code == 200, create.text
    evaluation = create.json()
    assert evaluation["application_id"] == "app-professor-lu"
    assert evaluation["evaluation_id"] == "eval-001"
    assert evaluation["requested_provider_id"] == "professor-lu"
    assert evaluation["status"] == "queued"

    read = await client.get(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
    )
    assert read.status_code == 200, read.text
    assert read.json()["scope_source"] == "global"

    listed = await client.get(
        "/v1/provider-applications/app-professor-lu/evaluation-requests?status=queued"
    )
    assert listed.status_code == 200, listed.text
    assert [item["evaluation_id"] for item in listed.json()] == ["eval-001"]

    locked_mutation = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001",
        json=provider_evaluation_payload(status="queued", sample_count=10),
    )
    assert locked_mutation.status_code == 422
    assert "immutable" in locked_mutation.text

    locked_status_mutation = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001",
        json=provider_evaluation_payload(status="cancelled"),
    )
    assert locked_status_mutation.status_code == 422
    assert "immutable" in locked_status_mutation.text

    idempotent = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001",
        json=provider_evaluation_payload(status="queued"),
    )
    assert idempotent.status_code == 200, idempotent.text
    assert idempotent.json()["id"] == evaluation["id"]


async def test_provider_evaluation_tenant_global_fallback_and_cross_application_scope(
    client: AsyncClient,
) -> None:
    tenant_id = str(uuid.uuid4())
    await client.put(
        "/v1/provider-applications/app-global",
        json=provider_application_payload(status="submitted"),
    )
    await client.put(
        "/v1/provider-applications/app-tenant",
        json=provider_application_payload(
            tenant_id=tenant_id,
            requested_provider_id="tenant-provider",
            status="submitted",
        ),
    )

    fallback_eval = await client.put(
        f"/v1/provider-applications/app-global/evaluation-requests/eval-001?tenant_id={tenant_id}",
        json=provider_evaluation_payload(tenant_id=tenant_id),
    )
    assert fallback_eval.status_code == 200, fallback_eval.text
    assert fallback_eval.json()["scope_source"] == "tenant"
    assert fallback_eval.json()["requested_provider_id"] == "professor-lu"

    tenant_eval = await client.put(
        "/v1/provider-applications/app-tenant/evaluation-requests/eval-001",
        json=provider_evaluation_payload(
            tenant_id=tenant_id,
            benchmark_suite="vrptw_standard_500",
        ),
    )
    assert tenant_eval.status_code == 200, tenant_eval.text
    assert tenant_eval.json()["requested_provider_id"] == "tenant-provider"

    global_list = await client.get("/v1/provider-applications/app-global/evaluation-requests")
    assert global_list.status_code == 200, global_list.text
    assert global_list.json() == []

    tenant_list = await client.get(
        f"/v1/provider-applications/app-global/evaluation-requests?tenant_id={tenant_id}"
    )
    assert tenant_list.status_code == 200, tenant_list.text
    assert [item["evaluation_id"] for item in tenant_list.json()] == ["eval-001"]


async def test_provider_application_write_protection_when_internal_secret_configured(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "capability_registry.routes.settings.internal_secret",
        SecretStr("internal-test-secret"),
    )

    missing = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(),
    )
    assert missing.status_code == 401

    ok = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(status="submitted"),
        headers={"X-Internal-Service-Auth": "internal-test-secret"},
    )
    assert ok.status_code == 200, ok.text

    missing_eval_auth = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001",
        json=provider_evaluation_payload(),
    )
    assert missing_eval_auth.status_code == 401

    ok_eval = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001",
        json=provider_evaluation_payload(),
        headers={"X-Internal-Service-Auth": "internal-test-secret"},
    )
    assert ok_eval.status_code == 200, ok_eval.text


def test_provider_application_openapi_omits_unsafe_fields() -> None:
    spec = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    provider_application_schemas = {
        name: schema
        for name, schema in spec["components"]["schemas"].items()
        if name.startswith("ProviderApplication") or name.startswith("ProviderEvaluation")
    }
    assert provider_application_schemas
    forbidden_terms = {
        "api_key",
        "password",
        "client_secret",
        "access_token",
        "refresh_token",
        "registry_password",
        "docker_password",
        "bank_account",
        "tax_id",
        "raw_dataset",
    }
    request_properties = set(
        provider_application_schemas["ProviderEvaluationUpsertRequest"].get("properties", {})
    )
    assert "requested_provider_id" not in request_properties
    for name, schema in provider_application_schemas.items():
        properties = set(schema.get("properties", {}))
        if name != "ProviderEvaluationResponse":
            assert properties.isdisjoint(forbidden_terms)
