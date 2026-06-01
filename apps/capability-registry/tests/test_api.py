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
                "TRUNCATE revenue_share_hooks, revenue_share_policies, "
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
