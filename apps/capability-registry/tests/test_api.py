"""Capability-registry API and schema tests."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
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
                "TRUNCATE provider_gradient_rollouts, "
                "provider_shadow_validation_samples, provider_shadow_validation_runs, "
                "provider_version_update_requests, "
                "provider_application_evaluation_requests, provider_applications, "
                "provider_revenue_payout_entries, "
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


def payout_entry_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "hook_id": str(uuid.uuid4()),
        "gross_amount": "100.0000",
        "currency": "CNY",
        "recognized_at": "2026-06-15T12:00:00Z",
        "status": "pending",
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


def shadow_run_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "baseline_provider_id": "highs",
        "status": "running",
        "started_at": "2026-06-01T00:00:00Z",
        "evidence_refs": ["oss://shadow-validation/app-professor-lu/run-001/evidence.json"],
        "metadata": {"source": "test"},
    }
    payload.update(overrides)
    return payload


def shadow_sample_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "coverage_class": "platform_standard",
        "dataset_ref": "benchmark://provider-shadow/lp-standard-v1",
        "case_ref": "fixture://provider-shadow/case-001",
        "observed_at": "2026-06-01T00:00:00Z",
        "provider_status_code": 200,
        "provider_latency_ms": 100,
        "baseline_latency_ms": 100,
        "deviation_ratio": "0.010000",
        "timed_out": False,
        "metadata": {"source": "test"},
    }
    payload.update(overrides)
    return payload


def rollout_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "evidence_refs": ["oss://provider-rollouts/app-professor-lu/run-001/rollout-001.json"],
        "metadata": {"source": "test"},
    }
    payload.update(overrides)
    return payload


def rollout_action_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "reason_ref": "oss://provider-rollouts/app-professor-lu/run-001/reason.json",
        "metadata": {"source": "test"},
    }
    payload.update(overrides)
    return payload


def version_update_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "current_version": "1.2.3",
        "proposed_version": "1.2.4",
        "change_kind": "patch",
        "openapi_url": "https://lab.example.edu/openapi-v1.2.4.json",
        "openapi_sha256": SHA,
        "image_digest": DIGEST,
        "cosign_bundle": {"bundle_ref": "oss://provider-versions/app-professor-lu/cosign.json"},
        "sbom_ref": "oss://provider-versions/app-professor-lu/sbom.spdx.json",
        "release_notes_ref": "oss://provider-versions/app-professor-lu/release-notes.md",
        "status": "draft",
        "metadata": {"source": "test"},
    }
    payload.update(overrides)
    return payload


def assert_json_key_absent(value: Any, key: str) -> None:
    if isinstance(value, dict):
        assert key not in value
        for item in value.values():
            assert_json_key_absent(item, key)
    elif isinstance(value, list):
        for item in value:
            assert_json_key_absent(item, key)


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


async def _create_revenue_share_hook(
    client: AsyncClient,
    **hook_overrides: Any,
) -> dict[str, Any]:
    await client.put("/v1/providers/highs", json=provider_payload(kind="external"))
    await client.put("/v1/capabilities/highs-lp", json=capability_payload())
    await client.put("/v1/revenue-share/policies/external-default", json=policy_payload())
    hook = await client.post(
        "/v1/revenue-share/hooks",
        json=hook_payload(**hook_overrides),
    )
    assert hook.status_code == 200, hook.text
    return hook.json()


async def test_provider_revenue_payout_entry_amounts_status_and_validation(
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    hook = await _create_revenue_share_hook(client)

    create = await client.put(
        "/v1/revenue-share/payout-entries/entry-001",
        json=payout_entry_payload(hook_id=hook["id"], gross_amount="123.4567"),
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert body["entry_id"] == "entry-001"
    assert body["hook_id"] == hook["id"]
    assert body["provider_id"] == "highs"
    assert body["k_algo"] == "highs-lp"
    assert body["period_month"] == "2026-06"
    assert body["gross_amount"] == "123.4567"
    assert body["provider_share_ratio"] == "0.400000"
    assert body["platform_share_ratio"] == "0.600000"
    assert body["provider_revenue_amount"] == "49.3827"
    assert body["platform_revenue_amount"] == "74.0740"
    assert body["status"] == "pending"
    assert body["scope_source"] == "global"
    assert "metadata" not in body

    held = await client.put(
        "/v1/revenue-share/payout-entries/entry-001",
        json=payout_entry_payload(hook_id=hook["id"], gross_amount="123.4567", status="held"),
    )
    assert held.status_code == 200, held.text
    assert held.json()["status"] == "held"

    paid = await client.put(
        "/v1/revenue-share/payout-entries/entry-001",
        json=payout_entry_payload(hook_id=hook["id"], gross_amount="123.4567", status="paid"),
    )
    assert paid.status_code == 200, paid.text

    invalid_terminal_transition = await client.put(
        "/v1/revenue-share/payout-entries/entry-001",
        json=payout_entry_payload(hook_id=hook["id"], gross_amount="123.4567", status="pending"),
    )
    assert invalid_terminal_transition.status_code == 422

    changed_amount = await client.put(
        "/v1/revenue-share/payout-entries/entry-001",
        json=payout_entry_payload(hook_id=hook["id"], gross_amount="200.0000", status="paid"),
    )
    assert changed_amount.status_code == 422

    forbidden = await client.put(
        "/v1/revenue-share/payout-entries/entry-002",
        json=payout_entry_payload(
            hook_id=hook["id"],
            providerAmount="49.3827",
        ),
    )
    assert forbidden.status_code == 422

    forbidden_metadata = await client.put(
        "/v1/revenue-share/payout-entries/entry-002",
        json=payout_entry_payload(
            hook_id=hook["id"],
            metadata={"nested": {"settlementId": "secret-settlement"}},
        ),
    )
    assert forbidden_metadata.status_code == 422

    duplicate_hook = await client.put(
        "/v1/revenue-share/payout-entries/entry-002",
        json=payout_entry_payload(hook_id=hook["id"]),
    )
    assert duplicate_hook.status_code == 422

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    """
                    INSERT INTO provider_revenue_payout_entries (
                        entry_id, hook_row_id, provider_id, k_algo, policy_id,
                        source_service, source_event_id, period_month, currency,
                        gross_amount, platform_share_ratio, provider_share_ratio,
                        status, recognized_at
                    )
                    SELECT
                        'entry-001', id, provider_id, k_algo, policy_id,
                        source_service, gen_random_uuid(), period_month, currency,
                        1.0000, 0.600000, 0.400000, 'pending', NOW()
                    FROM revenue_share_hooks
                    WHERE id = :hook_id
                    """
                ),
                {"hook_id": hook["id"]},
            )
            await session.commit()


async def test_provider_revenue_payout_entry_tenant_exact_scope_and_auth(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = str(uuid.uuid4())
    await client.put(
        "/v1/providers/highs",
        json=provider_payload(tenant_id=tenant_id, kind="external"),
    )
    await client.put(
        "/v1/capabilities/highs-lp",
        json=capability_payload(tenant_id=tenant_id),
    )
    await client.put("/v1/revenue-share/policies/external-default", json=policy_payload())
    tenant_hook = await client.post(
        "/v1/revenue-share/hooks",
        json=hook_payload(tenant_id=tenant_id),
    )
    assert tenant_hook.status_code == 200, tenant_hook.text

    global_scope_attempt = await client.put(
        "/v1/revenue-share/payout-entries/tenant-entry",
        json=payout_entry_payload(hook_id=tenant_hook.json()["id"]),
    )
    assert global_scope_attempt.status_code == 422

    tenant_entry = await client.put(
        "/v1/revenue-share/payout-entries/tenant-entry",
        json=payout_entry_payload(tenant_id=tenant_id, hook_id=tenant_hook.json()["id"]),
    )
    assert tenant_entry.status_code == 200, tenant_entry.text
    assert tenant_entry.json()["tenant_id"] == tenant_id
    assert tenant_entry.json()["scope_source"] == "tenant"

    global_list = await client.get("/v1/revenue-share/payout-entries")
    assert global_list.status_code == 200, global_list.text
    assert global_list.json() == []

    tenant_list = await client.get(
        "/v1/revenue-share/payout-entries",
        params={"tenant_id": tenant_id},
    )
    assert tenant_list.status_code == 200, tenant_list.text
    assert [item["entry_id"] for item in tenant_list.json()] == ["tenant-entry"]

    monkeypatch.setattr(
        "capability_registry.routes.settings.internal_secret",
        SecretStr("internal-test-secret"),
    )
    blocked = await client.put(
        "/v1/revenue-share/payout-entries/blocked-entry",
        json=payout_entry_payload(tenant_id=tenant_id, hook_id=tenant_hook.json()["id"]),
    )
    assert blocked.status_code == 401


async def test_provider_revenue_payout_dashboard_totals_filters_and_no_side_effects(
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    hook_one = await _create_revenue_share_hook(client, source_event_id=str(uuid.uuid4()))
    hook_two = await client.post(
        "/v1/revenue-share/hooks",
        json=hook_payload(source_event_id=str(uuid.uuid4()), period_month="2026-07"),
    )
    assert hook_two.status_code == 200, hook_two.text
    hook_three = await client.post(
        "/v1/revenue-share/hooks",
        json=hook_payload(source_event_id=str(uuid.uuid4()), period_month="2026-07"),
    )
    assert hook_three.status_code == 200, hook_three.text
    hook_other_provider = await client.post(
        "/v1/revenue-share/hooks",
        json=hook_payload(
            provider_id="other-provider",
            k_algo="other-capability",
            source_event_id=str(uuid.uuid4()),
        ),
    )
    assert hook_other_provider.status_code == 422

    pending = await client.put(
        "/v1/revenue-share/payout-entries/entry-pending",
        json=payout_entry_payload(hook_id=hook_one["id"], gross_amount="100.0000"),
    )
    held = await client.put(
        "/v1/revenue-share/payout-entries/entry-held",
        json=payout_entry_payload(
            hook_id=hook_two.json()["id"],
            gross_amount="50.0000",
            status="held",
            recognized_at="2026-07-01T00:00:00Z",
        ),
    )
    voided = await client.put(
        "/v1/revenue-share/payout-entries/entry-voided",
        json=payout_entry_payload(
            hook_id=hook_three.json()["id"],
            gross_amount="25.0000",
            status="voided",
            recognized_at="2026-07-02T00:00:00Z",
        ),
    )
    assert pending.status_code == 200, pending.text
    assert held.status_code == 200, held.text
    assert voided.status_code == 200, voided.text

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        before_rows = (
            (
                await session.execute(
                    text(
                        "SELECT entry_id, status, gross_amount FROM provider_revenue_payout_entries "
                        "ORDER BY entry_id"
                    )
                )
            )
            .mappings()
            .all()
        )

    dashboard = await client.get("/v1/providers/highs/revenue-payout-dashboard")
    assert dashboard.status_code == 200, dashboard.text
    body = dashboard.json()
    assert body["provider_id"] == "highs"
    assert body["status_counts"] == {"pending": 1, "held": 1, "paid": 0, "voided": 1}
    assert body["total_entries"] == 3
    assert body["currency_totals"] == [
        {
            "currency": "CNY",
            "entry_count": 3,
            "gross_amount": "150.0000",
            "provider_revenue_amount": "60.0000",
            "platform_revenue_amount": "90.0000",
            "pending_payout_amount": "40.0000",
            "held_payout_amount": "20.0000",
            "paid_amount": "0.0000",
            "voided_gross_amount": "25.0000",
        }
    ]
    assert [(item["period_month"], item["currency"]) for item in body["period_summaries"]] == [
        ("2026-06", "CNY"),
        ("2026-07", "CNY"),
    ]
    assert [item["entry_id"] for item in body["entries"]] == [
        "entry-voided",
        "entry-held",
        "entry-pending",
    ]
    assert "metadata" not in json.dumps(body)
    assert "settlement_id" not in json.dumps(body)

    filtered = await client.get(
        "/v1/providers/highs/revenue-payout-dashboard",
        params={
            "from": "2026-07-01T00:00:00Z",
            "to": "2026-07-01T23:59:59Z",
            "period_month": "2026-07",
            "status": "held",
            "k_algo": "highs-lp",
            "currency": "CNY",
        },
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["total_entries"] == 1
    assert filtered.json()["entries"][0]["entry_id"] == "entry-held"

    empty = await client.get("/v1/providers/no-revenue-provider/revenue-payout-dashboard")
    assert empty.status_code == 200, empty.text
    assert empty.json()["status_counts"] == {"pending": 0, "held": 0, "paid": 0, "voided": 0}
    assert empty.json()["currency_totals"] == []
    assert empty.json()["period_summaries"] == []
    assert empty.json()["entries"] == []

    reversed_window = await client.get(
        "/v1/providers/highs/revenue-payout-dashboard",
        params={"from": "2026-07-02T00:00:00Z", "to": "2026-07-01T00:00:00Z"},
    )
    assert reversed_window.status_code == 422

    naive_window = await client.get(
        "/v1/providers/highs/revenue-payout-dashboard",
        params={"from": "2026-07-01T00:00:00"},
    )
    assert naive_window.status_code == 422

    async with maker() as session:
        after_rows = (
            (
                await session.execute(
                    text(
                        "SELECT entry_id, status, gross_amount FROM provider_revenue_payout_entries "
                        "ORDER BY entry_id"
                    )
                )
            )
            .mappings()
            .all()
        )
    assert before_rows == after_rows


async def test_provider_revenue_payout_dashboard_fails_closed_on_stored_drift(
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    hook = await _create_revenue_share_hook(client)
    create = await client.put(
        "/v1/revenue-share/payout-entries/entry-drift",
        json=payout_entry_payload(hook_id=hook["id"]),
    )
    assert create.status_code == 200, create.text
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with maker() as session:
        await session.execute(
            text(
                "ALTER TABLE provider_revenue_payout_entries "
                "DROP CONSTRAINT ck_provider_revenue_payout_entries_status"
            )
        )
        await session.execute(
            text(
                """
                UPDATE provider_revenue_payout_entries
                SET status = 'manual-drift'
                WHERE entry_id = 'entry-drift'
                """
            )
        )
        await session.commit()

    status_drift = await client.get("/v1/providers/highs/revenue-payout-dashboard")
    assert status_drift.status_code == 409
    assert "status" in status_drift.text

    async with maker() as session:
        await session.execute(
            text(
                """
                UPDATE provider_revenue_payout_entries
                SET status = 'pending'
                WHERE entry_id = 'entry-drift'
                """
            )
        )
        await session.execute(
            text(
                """
                ALTER TABLE provider_revenue_payout_entries
                ADD CONSTRAINT ck_provider_revenue_payout_entries_status
                CHECK (status IN ('pending', 'held', 'paid', 'voided'))
                """
            )
        )
        await session.execute(
            text(
                """
                UPDATE provider_revenue_payout_entries
                SET provider_id = 'other-provider'
                WHERE entry_id = 'entry-drift'
                """
            )
        )
        await session.commit()

    hook_drift = await client.get("/v1/revenue-share/payout-entries/entry-drift")
    assert hook_drift.status_code == 409
    assert "hook drift" in hook_drift.text


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


def test_provider_revenue_payout_openapi_contract_is_safe() -> None:
    spec = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    payout_schemas = {
        name: schema
        for name, schema in spec["components"]["schemas"].items()
        if name.startswith("ProviderRevenuePayout")
    }
    assert payout_schemas
    unsafe_terms = {
        "metadata",
        "payout_status",
        "paid_at",
        "settlement_id",
        "bank_account",
        "tax_id",
        "access_token",
        "refresh_token",
        "client_secret",
        "raw_billing_payload",
        "raw_request",
        "raw_response",
        "provider_request",
        "provider_response",
        "routing_payload",
        "customer_payload",
        "email",
        "phone",
    }
    for schema_name, schema in payout_schemas.items():
        properties = set(schema.get("properties", {}))
        if schema_name == "ProviderRevenuePayoutEntryUpsertRequest":
            properties.discard("metadata")
        assert properties.isdisjoint(unsafe_terms)

    request_props = set(
        payout_schemas["ProviderRevenuePayoutEntryUpsertRequest"].get("properties", {})
    )
    assert {
        "provider_amount",
        "platform_amount",
        "provider_revenue_amount",
        "platform_revenue_amount",
        "pending_payout_amount",
    }.isdisjoint(request_props)

    endpoint = spec["paths"]["/v1/providers/{provider_id}/revenue-payout-dashboard"]["get"]
    parameters = {parameter["name"]: parameter for parameter in endpoint["parameters"]}
    assert {
        "provider_id",
        "tenant_id",
        "from",
        "to",
        "period_month",
        "status",
        "k_algo",
        "currency",
    }.issubset(set(parameters))


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


async def test_provider_version_update_lifecycle_etag_and_no_catalog_side_effect(
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    await client.put(
        "/v1/providers/highs",
        json=provider_payload(),
    )
    await client.put(
        "/v1/capabilities/highs-lp",
        json=capability_payload(),
    )
    app_resp = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(status="submitted"),
    )
    assert app_resp.status_code == 200, app_resp.text

    create = await client.put(
        "/v1/provider-applications/app-professor-lu/version-updates/update-001",
        json=version_update_payload(),
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert body["version_update_id"] == "update-001"
    assert body["requested_provider_id"] == "professor-lu"
    assert body["record_version"] == 1
    assert body["scope_source"] == "global"
    assert create.headers["etag"] == '"update-001:1"'

    missing_if_match = await client.put(
        "/v1/provider-applications/app-professor-lu/version-updates/update-001",
        json=version_update_payload(metadata={"source": "changed"}),
    )
    assert missing_if_match.status_code == 428

    mismatch = await client.put(
        "/v1/provider-applications/app-professor-lu/version-updates/update-001",
        json=version_update_payload(metadata={"source": "changed"}),
        headers={"If-Match": '"update-001:999"'},
    )
    assert mismatch.status_code == 412

    draft_update = await client.put(
        "/v1/provider-applications/app-professor-lu/version-updates/update-001",
        json=version_update_payload(metadata={"source": "changed"}),
        headers={"If-Match": create.headers["etag"]},
    )
    assert draft_update.status_code == 200, draft_update.text
    assert draft_update.json()["record_version"] == 2
    assert draft_update.headers["etag"] == '"update-001:2"'

    submitted = await client.patch(
        "/v1/provider-applications/app-professor-lu/version-updates/update-001/status",
        json={"status": "submitted", "metadata": {"review": "queued"}},
        headers={"If-Match": draft_update.headers["etag"]},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["submitted_at"] is not None
    assert submitted.json()["record_version"] == 3

    immutable = await client.put(
        "/v1/provider-applications/app-professor-lu/version-updates/update-001",
        json=version_update_payload(proposed_version="1.2.5"),
        headers={"If-Match": submitted.headers["etag"]},
    )
    assert immutable.status_code == 422

    under_review = await client.patch(
        "/v1/provider-applications/app-professor-lu/version-updates/update-001/status",
        json={"status": "under_review", "metadata": {"review": "started"}},
        headers={"If-Match": submitted.headers["etag"]},
    )
    assert under_review.status_code == 200, under_review.text

    missing_review_note = await client.patch(
        "/v1/provider-applications/app-professor-lu/version-updates/update-001/status",
        json={"status": "approved", "metadata": {"review": "approved"}},
        headers={"If-Match": under_review.headers["etag"]},
    )
    assert missing_review_note.status_code == 422

    approved = await client.patch(
        "/v1/provider-applications/app-professor-lu/version-updates/update-001/status",
        json={
            "status": "approved",
            "review_notes_ref": "oss://provider-versions/app-professor-lu/review.md",
            "metadata": {"review": "approved"},
        },
        headers={"If-Match": under_review.headers["etag"]},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["reviewed_at"] is not None
    assert approved.json()["record_version"] == 5

    terminal_change = await client.patch(
        "/v1/provider-applications/app-professor-lu/version-updates/update-001/status",
        json={"status": "cancelled", "metadata": {"review": "cancel"}},
        headers={"If-Match": approved.headers["etag"]},
    )
    assert terminal_change.status_code == 422

    get_resp = await client.get(
        "/v1/provider-applications/app-professor-lu/version-updates/update-001"
    )
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.headers["etag"] == approved.headers["etag"]

    listed = await client.get(
        "/v1/provider-applications/app-professor-lu/version-updates"
        "?status=approved&change_kind=patch&requested_provider_id=professor-lu"
    )
    assert listed.status_code == 200, listed.text
    assert [item["version_update_id"] for item in listed.json()] == ["update-001"]

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        provider_count = (
            await session.execute(text("SELECT COUNT(*) FROM capability_providers"))
        ).scalar_one()
        capability_version = (
            await session.execute(
                text("SELECT model_version FROM capabilities WHERE k_algo = 'highs-lp'")
            )
        ).scalar_one()
        rollout_count = (
            await session.execute(text("SELECT COUNT(*) FROM provider_gradient_rollouts"))
        ).scalar_one()
    assert provider_count == 1
    assert capability_version == "1.7.0"
    assert rollout_count == 0


async def test_provider_version_update_validation_tenant_scope_and_auth(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = str(uuid.uuid4())
    draft_app = await client.put(
        "/v1/provider-applications/app-draft",
        json=provider_application_payload(),
    )
    assert draft_app.status_code == 200, draft_app.text
    draft_update = await client.put(
        "/v1/provider-applications/app-draft/version-updates/update-001",
        json=version_update_payload(),
    )
    assert draft_update.status_code == 422

    tenant_app = await client.put(
        "/v1/provider-applications/app-tenant",
        json=provider_application_payload(
            tenant_id=tenant_id,
            requested_provider_id="tenant-provider",
            status="submitted",
        ),
    )
    assert tenant_app.status_code == 200, tenant_app.text

    global_attempt = await client.put(
        "/v1/provider-applications/app-tenant/version-updates/update-001",
        json=version_update_payload(),
    )
    assert global_attempt.status_code == 404

    tenant_update = await client.put(
        "/v1/provider-applications/app-tenant/version-updates/update-001",
        json=version_update_payload(tenant_id=tenant_id),
    )
    assert tenant_update.status_code == 200, tenant_update.text
    assert tenant_update.json()["scope_source"] == "tenant"

    semver_cases = [
        version_update_payload(current_version="1.2.3", proposed_version="1.2.3"),
        version_update_payload(current_version="1.2.3", proposed_version="1.2.2"),
        version_update_payload(
            current_version="1.2.3", proposed_version="1.3.1", change_kind="minor"
        ),
        version_update_payload(
            current_version="1.2.3", proposed_version="2.1.0", change_kind="major"
        ),
        version_update_payload(current_version="1.2", proposed_version="1.2.4"),
    ]
    for index, payload in enumerate(semver_cases, start=1):
        response = await client.put(
            f"/v1/provider-applications/app-tenant/version-updates/bad-{index}",
            json={**payload, "tenant_id": tenant_id},
        )
        assert response.status_code == 422

    forbidden_requested_provider = await client.put(
        "/v1/provider-applications/app-tenant/version-updates/bad-requested-provider",
        json={**version_update_payload(tenant_id=tenant_id), "requested_provider_id": "raw"},
    )
    assert forbidden_requested_provider.status_code == 422

    forbidden_metadata = await client.put(
        "/v1/provider-applications/app-tenant/version-updates/bad-secret",
        json=version_update_payload(
            tenant_id=tenant_id,
            metadata={"nested": {"registryPassword": "raw"}},
        ),
    )
    assert forbidden_metadata.status_code == 422

    forbidden_ref = await client.put(
        "/v1/provider-applications/app-tenant/version-updates/bad-ref",
        json=version_update_payload(tenant_id=tenant_id, release_notes_ref="inline release notes"),
    )
    assert forbidden_ref.status_code == 422

    monkeypatch.setattr(
        "capability_registry.routes.settings.internal_secret",
        SecretStr("internal-test-secret"),
    )
    missing_auth = await client.put(
        "/v1/provider-applications/app-tenant/version-updates/auth-blocked",
        json=version_update_payload(tenant_id=tenant_id),
    )
    assert missing_auth.status_code == 401

    ok_auth = await client.put(
        "/v1/provider-applications/app-tenant/version-updates/auth-ok",
        json=version_update_payload(tenant_id=tenant_id),
        headers={"X-Internal-Service-Auth": "internal-test-secret"},
    )
    assert ok_auth.status_code == 200, ok_auth.text


async def test_provider_version_update_fails_closed_on_stored_drift(
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    app_resp = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(status="submitted"),
    )
    assert app_resp.status_code == 200, app_resp.text
    created = await client.put(
        "/v1/provider-applications/app-professor-lu/version-updates/update-drift",
        json=version_update_payload(),
    )
    assert created.status_code == 200, created.text

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await session.execute(
            text(
                "ALTER TABLE provider_version_update_requests "
                "DROP CONSTRAINT ck_provider_version_updates_status"
            )
        )
        await session.execute(
            text(
                "UPDATE provider_version_update_requests "
                "SET status = 'mystery' WHERE version_update_id = 'update-drift'"
            )
        )
        await session.commit()

    status_drift = await client.get(
        "/v1/provider-applications/app-professor-lu/version-updates/update-drift"
    )
    assert status_drift.status_code == 409
    assert "status drift" in status_drift.text

    async with maker() as session:
        await session.execute(
            text(
                "UPDATE provider_version_update_requests "
                "SET status = 'draft', requested_provider_id = 'other-provider' "
                "WHERE version_update_id = 'update-drift'"
            )
        )
        await session.execute(
            text(
                "ALTER TABLE provider_version_update_requests "
                "ADD CONSTRAINT ck_provider_version_updates_status "
                "CHECK (status IN ('draft', 'submitted', 'under_review', 'approved', 'rejected', 'cancelled'))"
            )
        )
        await session.commit()

    provider_drift = await client.get(
        "/v1/provider-applications/app-professor-lu/version-updates/update-drift"
    )
    assert provider_drift.status_code == 409
    assert "requested_provider_id drift" in provider_drift.text

    async with maker() as session:
        await session.execute(
            text(
                "UPDATE provider_version_update_requests "
                "SET requested_provider_id = 'professor-lu', "
                'metadata = \'{"nested": {"accessToken": "raw"}}\'::jsonb '
                "WHERE version_update_id = 'update-drift'"
            )
        )
        await session.commit()

    unsafe_metadata = await client.get(
        "/v1/provider-applications/app-professor-lu/version-updates/update-drift"
    )
    assert unsafe_metadata.status_code == 409
    assert "unsafe metadata drift" in unsafe_metadata.text


def test_provider_version_update_openapi_contract_is_safe() -> None:
    spec = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    version_schemas = {
        name: schema
        for name, schema in spec["components"]["schemas"].items()
        if name.startswith("ProviderVersion")
    }
    assert version_schemas
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
        "raw_request",
        "raw_response",
        "provider_request",
        "provider_response",
        "routing_payload",
        "customer_payload",
        "payout_status",
        "settlement_id",
    }
    upsert_properties = set(
        version_schemas["ProviderVersionUpdateUpsertRequest"].get("properties", {})
    )
    patch_properties = set(
        version_schemas["ProviderVersionUpdateStatusPatchRequest"].get("properties", {})
    )
    assert "requested_provider_id" not in upsert_properties
    assert "record_version" not in upsert_properties
    assert "submitted_at" not in upsert_properties
    assert "reviewed_at" not in upsert_properties
    assert "current_version" not in patch_properties
    assert "record_version" not in patch_properties
    assert "submitted_at" not in patch_properties
    assert "reviewed_at" not in patch_properties
    for schema in version_schemas.values():
        properties = set(schema.get("properties", {}))
        assert properties.isdisjoint(forbidden_terms)

    endpoint = spec["paths"][
        "/v1/provider-applications/{application_id}/version-updates/{version_update_id}"
    ]["put"]
    parameters = {parameter["name"]: parameter for parameter in endpoint["parameters"]}
    assert {"application_id", "version_update_id", "If-Match", "X-Internal-Service-Auth"}.issubset(
        set(parameters)
    )


async def _create_submitted_application_and_evaluation(
    client: AsyncClient,
    *,
    evaluation_overrides: dict[str, Any] | None = None,
) -> None:
    app_resp = await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(status="submitted"),
    )
    assert app_resp.status_code == 200, app_resp.text
    eval_payload = provider_evaluation_payload()
    if evaluation_overrides:
        eval_payload.update(evaluation_overrides)
    eval_resp = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001",
        json=eval_payload,
    )
    assert eval_resp.status_code == 200, eval_resp.text


async def test_provider_shadow_run_requires_submitted_non_cancelled_evaluation(
    client: AsyncClient,
) -> None:
    missing = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001",
        json=shadow_run_payload(),
    )
    assert missing.status_code == 404

    await client.put(
        "/v1/provider-applications/app-professor-lu",
        json=provider_application_payload(),
    )
    draft_app = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001",
        json=shadow_run_payload(),
    )
    assert draft_app.status_code == 422

    await client.post("/v1/provider-applications/app-professor-lu/submit")
    cancelled_eval = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001",
        json=provider_evaluation_payload(status="cancelled"),
    )
    assert cancelled_eval.status_code == 200, cancelled_eval.text
    cancelled_shadow = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001",
        json=shadow_run_payload(),
    )
    assert cancelled_shadow.status_code == 422


async def test_provider_shadow_run_state_validation_and_no_catalog_side_effect(
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    await _create_submitted_application_and_evaluation(client)

    forbidden_summary = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001",
        json={**shadow_run_payload(), "summary": {"sample_count": 500}},
    )
    assert forbidden_summary.status_code == 422

    forged_pass = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001",
        json=shadow_run_payload(status="passed"),
    )
    assert forged_pass.status_code == 422

    create = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001",
        json=shadow_run_payload(),
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert body["run_id"] == "run-001"
    assert body["requested_provider_id"] == "professor-lu"
    assert body["benchmark_suite"] == "lp_standard_500"
    assert body["evaluation_sample_count"] == 500
    assert body["status"] == "running"
    assert body["summary"] == {}

    mutate_baseline = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001",
        json=shadow_run_payload(baseline_provider_id="or-tools"),
    )
    assert mutate_baseline.status_code == 422
    assert "baseline_provider_id" in mutate_baseline.text

    listed = await client.get(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs?status=running"
    )
    assert listed.status_code == 200, listed.text
    assert [item["run_id"] for item in listed.json()] == ["run-001"]

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        provider_count = (
            await session.execute(
                text("SELECT count(*) FROM capability_providers WHERE provider_id = 'professor-lu'")
            )
        ).scalar_one()
    assert provider_count == 0


async def test_provider_shadow_samples_validate_scope_cap_and_derived_passed(
    client: AsyncClient,
) -> None:
    await _create_submitted_application_and_evaluation(
        client,
        evaluation_overrides={"sample_count": 1},
    )
    run_resp = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001",
        json=shadow_run_payload(),
    )
    assert run_resp.status_code == 200, run_resp.text

    bad_raw_payload = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/samples/sample-001",
        json=shadow_sample_payload(metadata={"providerResponse": {"raw": True}}),
    )
    assert bad_raw_payload.status_code == 422

    forged_passed = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/samples/sample-001",
        json={**shadow_sample_payload(), "passed": True},
    )
    assert forged_passed.status_code == 422

    sample = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/samples/sample-001",
        json=shadow_sample_payload(),
    )
    assert sample.status_code == 200, sample.text
    assert sample.json()["passed"] is True

    timeout_update = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/samples/sample-001",
        json=shadow_sample_payload(timed_out=True),
    )
    assert timeout_update.status_code == 200, timeout_update.text
    assert timeout_update.json()["passed"] is False

    over_cap = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/samples/sample-002",
        json=shadow_sample_payload(),
    )
    assert over_cap.status_code == 422
    assert "sample_count" in over_cap.text

    running_to_cancelled = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001",
        json=shadow_run_payload(status="cancelled"),
    )
    assert running_to_cancelled.status_code == 200, running_to_cancelled.text

    locked_sample = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/samples/sample-001",
        json=shadow_sample_payload(),
    )
    assert locked_sample.status_code == 422


async def test_provider_shadow_sample_cap_rechecked_under_run_lock(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _create_submitted_application_and_evaluation(
        client,
        evaluation_overrides={"sample_count": 1},
    )
    await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001",
        json=shadow_run_payload(),
    )

    first = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/samples/sample-001",
        json=shadow_sample_payload(),
    )
    assert first.status_code == 200, first.text

    calls = 0
    original_loader = registry_routes._load_shadow_sample_row

    async def race_loader(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        return await original_loader(*args, **kwargs)

    monkeypatch.setattr(registry_routes, "_load_shadow_sample_row", race_loader)
    over_cap = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/samples/sample-002",
        json=shadow_sample_payload(),
    )
    assert over_cap.status_code == 422
    assert "sample_count" in over_cap.text


async def test_provider_shadow_finalize_fails_closed_for_under_budget_run(
    client: AsyncClient,
) -> None:
    await _create_submitted_application_and_evaluation(
        client,
        evaluation_overrides={"sample_count": 2},
    )
    await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001",
        json=shadow_run_payload(),
    )
    base_time = datetime(2026, 6, 1, tzinfo=UTC)
    for index, coverage_class in enumerate(("platform_standard", "provider_supplied")):
        response = await client.put(
            "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
            f"/shadow-runs/run-001/samples/sample-00{index + 1}",
            json=shadow_sample_payload(
                coverage_class=coverage_class,
                case_ref=f"fixture://provider-shadow/case-00{index + 1}",
                observed_at=(base_time + timedelta(days=index)).isoformat(),
            ),
        )
        assert response.status_code == 200, response.text

    finalize = await client.post(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/finalize"
    )
    assert finalize.status_code == 200, finalize.text
    body = finalize.json()
    assert body["status"] == "failed"
    summary = body["summary"]
    assert summary["sample_count"] == 2
    assert summary["evaluation_sample_count"] == 2
    assert "evaluation_sample_count_below_required" in summary["failed_reasons"]
    assert "coverage_class_missing" in summary["failed_reasons"]

    replay = await client.post(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/finalize"
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["ended_at"] == body["ended_at"]


async def test_provider_shadow_finalize_passes_with_500_sample_gate(
    client: AsyncClient,
) -> None:
    await _create_submitted_application_and_evaluation(client)
    run_resp = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001",
        json=shadow_run_payload(),
    )
    assert run_resp.status_code == 200, run_resp.text
    base_time = datetime(2026, 6, 1, tzinfo=UTC)
    coverage_classes = [
        "platform_standard",
        "provider_supplied",
        "adversarial",
        "desensitized_real",
    ]
    for index in range(500):
        coverage_class = coverage_classes[index % len(coverage_classes)]
        response = await client.put(
            "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
            f"/shadow-runs/run-001/samples/sample-{index:03d}",
            json=shadow_sample_payload(
                coverage_class=coverage_class,
                case_ref=f"fixture://provider-shadow/case-{index:03d}",
                observed_at=(base_time + timedelta(days=index % 15)).isoformat(),
                provider_latency_ms=100 + (index % 10),
                baseline_latency_ms=100,
                deviation_ratio="0.010000",
            ),
        )
        assert response.status_code == 200, response.text

    finalize = await client.post(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/finalize"
    )
    assert finalize.status_code == 200, finalize.text
    body = finalize.json()
    assert body["status"] == "passed"
    summary = body["summary"]
    assert summary["sample_count"] == 500
    assert summary["evaluation_sample_count"] == 500
    assert summary["observed_day_span"] == 14
    assert summary["success_count"] == 500
    assert summary["success_rate"] == "1.000000"
    assert summary["average_deviation_ratio"] == "0.010000"
    assert summary["baseline_p95_latency_ms"] == 100
    assert summary["p95_latency_ratio"] <= "1.500000"
    assert summary["failed_reasons"] == []

    passed_filter = await client.get(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/samples?passed=true&coverage_class=adversarial"
    )
    assert passed_filter.status_code == 200, passed_filter.text
    assert all(item["coverage_class"] == "adversarial" for item in passed_filter.json())
    assert all(item["passed"] is True for item in passed_filter.json())

    idempotent_upsert = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001",
        json=shadow_run_payload(status=None),
    )
    assert idempotent_upsert.status_code == 200, idempotent_upsert.text
    assert idempotent_upsert.json()["id"] == body["id"]


async def test_provider_shadow_tenant_scope_requires_tenant_evaluation(
    client: AsyncClient,
) -> None:
    tenant_id = str(uuid.uuid4())
    await client.put(
        "/v1/provider-applications/app-global",
        json=provider_application_payload(status="submitted"),
    )
    await client.put(
        "/v1/provider-applications/app-global/evaluation-requests/eval-001",
        json=provider_evaluation_payload(status="queued"),
    )

    tenant_against_global_eval = await client.put(
        "/v1/provider-applications/app-global/evaluation-requests/eval-001/shadow-runs/run-001",
        json=shadow_run_payload(tenant_id=tenant_id),
    )
    assert tenant_against_global_eval.status_code == 404

    tenant_eval = await client.put(
        f"/v1/provider-applications/app-global/evaluation-requests/eval-tenant?tenant_id={tenant_id}",
        json=provider_evaluation_payload(
            tenant_id=tenant_id,
            evaluation_id="eval-tenant",
            status="queued",
        ),
    )
    assert tenant_eval.status_code == 200, tenant_eval.text

    tenant_run = await client.put(
        "/v1/provider-applications/app-global/evaluation-requests/eval-tenant/shadow-runs/run-001",
        json=shadow_run_payload(tenant_id=tenant_id),
    )
    assert tenant_run.status_code == 200, tenant_run.text
    assert tenant_run.json()["scope_source"] == "tenant"


async def test_provider_shadow_write_protection_when_internal_secret_configured(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _create_submitted_application_and_evaluation(client)
    monkeypatch.setattr(
        "capability_registry.routes.settings.internal_secret",
        SecretStr("internal-test-secret"),
    )

    missing_run_auth = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001",
        json=shadow_run_payload(),
    )
    assert missing_run_auth.status_code == 401

    ok_run = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001",
        json=shadow_run_payload(),
        headers={"X-Internal-Service-Auth": "internal-test-secret"},
    )
    assert ok_run.status_code == 200, ok_run.text

    missing_sample_auth = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/samples/sample-001",
        json=shadow_sample_payload(),
    )
    assert missing_sample_auth.status_code == 401

    ok_sample = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/samples/sample-001",
        json=shadow_sample_payload(),
        headers={"X-Internal-Service-Auth": "internal-test-secret"},
    )
    assert ok_sample.status_code == 200, ok_sample.text


def test_provider_shadow_openapi_omits_unsafe_fields() -> None:
    spec = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    shadow_schemas = {
        name: schema
        for name, schema in spec["components"]["schemas"].items()
        if name.startswith("ProviderShadow")
    }
    assert shadow_schemas
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
        "raw_request",
        "raw_response",
        "provider_request",
        "provider_response",
    }
    sample_request_properties = set(
        shadow_schemas["ProviderShadowSampleUpsertRequest"].get("properties", {})
    )
    run_request_properties = set(
        shadow_schemas["ProviderShadowRunUpsertRequest"].get("properties", {})
    )
    assert "passed" not in sample_request_properties
    assert "summary" not in run_request_properties
    status_schema = shadow_schemas["ProviderShadowRunUpsertRequest"]["properties"]["status"][
        "anyOf"
    ][0]
    assert set(status_schema["enum"]) == {
        "draft",
        "running",
        "cancelled",
    }
    for schema in shadow_schemas.values():
        properties = set(schema.get("properties", {}))
        assert properties.isdisjoint(forbidden_terms)


async def _create_passed_shadow_run(
    client: AsyncClient,
    *,
    application_id: str = "app-professor-lu",
    evaluation_id: str = "eval-001",
    run_id: str = "run-001",
    requested_provider_id: str = "professor-lu",
    tenant_id: str | None = None,
) -> dict[str, Any]:
    query = f"?tenant_id={tenant_id}" if tenant_id is not None else ""
    body_tenant = {"tenant_id": tenant_id} if tenant_id is not None else {}
    app_resp = await client.put(
        f"/v1/provider-applications/{application_id}",
        json=provider_application_payload(
            **body_tenant,
            requested_provider_id=requested_provider_id,
            status="submitted",
        ),
    )
    assert app_resp.status_code == 200, app_resp.text
    eval_resp = await client.put(
        f"/v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}",
        json=provider_evaluation_payload(**body_tenant, evaluation_id=evaluation_id),
    )
    assert eval_resp.status_code == 200, eval_resp.text
    run_resp = await client.put(
        f"/v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}"
        f"/shadow-runs/{run_id}",
        json=shadow_run_payload(**body_tenant),
    )
    assert run_resp.status_code == 200, run_resp.text
    base_time = datetime(2026, 6, 1, tzinfo=UTC)
    coverage_classes = [
        "platform_standard",
        "provider_supplied",
        "adversarial",
        "desensitized_real",
    ]
    for index in range(500):
        response = await client.put(
            f"/v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}"
            f"/shadow-runs/{run_id}/samples/sample-{index:03d}",
            json=shadow_sample_payload(
                **body_tenant,
                coverage_class=coverage_classes[index % len(coverage_classes)],
                case_ref=f"fixture://provider-shadow/case-{index:03d}",
                observed_at=(base_time + timedelta(days=index % 15)).isoformat(),
            ),
        )
        assert response.status_code == 200, response.text
    finalize = await client.post(
        f"/v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}"
        f"/shadow-runs/{run_id}/finalize{query}"
    )
    assert finalize.status_code == 200, finalize.text
    assert finalize.json()["status"] == "passed"
    return finalize.json()


async def test_provider_rollout_requires_passed_shadow_and_snapshots_summary(
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    await _create_submitted_application_and_evaluation(client)
    run_resp = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001",
        json=shadow_run_payload(),
    )
    assert run_resp.status_code == 200, run_resp.text

    not_passed = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001",
        json=rollout_payload(),
    )
    assert not_passed.status_code == 422
    assert "passed shadow" in not_passed.text

    await client.post(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/finalize"
    )
    failed_shadow = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001",
        json=rollout_payload(),
    )
    assert failed_shadow.status_code == 422

    passed_shadow = await _create_passed_shadow_run(
        client,
        application_id="app-professor-lu-passed",
        evaluation_id="eval-passed",
        run_id="run-passed",
        requested_provider_id="professor-lu-passed",
    )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await session.execute(
            text(
                "UPDATE provider_shadow_validation_runs "
                "SET summary = jsonb_set(summary, '{failed_reasons}', '[\"manual_drift\"]'::jsonb) "
                "WHERE run_id = 'run-passed'"
            )
        )
        await session.commit()
    drifted_shadow = await client.put(
        "/v1/provider-applications/app-professor-lu-passed/evaluation-requests/eval-passed"
        "/shadow-runs/run-passed/rollouts/rollout-001",
        json=rollout_payload(),
    )
    assert drifted_shadow.status_code == 422
    assert "clean passed shadow summary" in drifted_shadow.text
    async with maker() as session:
        await session.execute(
            text(
                "UPDATE provider_shadow_validation_runs "
                "SET summary = jsonb_set(summary, '{failed_reasons}', '[]'::jsonb) "
                "WHERE run_id = 'run-passed'"
            )
        )
        await session.commit()

    forbidden_derived = await client.put(
        "/v1/provider-applications/app-professor-lu-passed/evaluation-requests/eval-passed"
        "/shadow-runs/run-passed/rollouts/rollout-001",
        json={**rollout_payload(), "stage_history": []},
    )
    assert forbidden_derived.status_code == 422

    raw_payload = await client.put(
        "/v1/provider-applications/app-professor-lu-passed/evaluation-requests/eval-passed"
        "/shadow-runs/run-passed/rollouts/rollout-001",
        json=rollout_payload(metadata={"routingPayload": {"customer_id": "raw"}}),
    )
    assert raw_payload.status_code == 422

    create = await client.put(
        "/v1/provider-applications/app-professor-lu-passed/evaluation-requests/eval-passed"
        "/shadow-runs/run-passed/rollouts/rollout-001",
        json=rollout_payload(),
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert body["status"] == "draft"
    assert body["current_stage_percent"] == 0
    assert body["requested_provider_id"] == "professor-lu-passed"
    assert body["baseline_provider_id"] == "highs"
    assert body["benchmark_suite"] == "lp_standard_500"
    assert body["stage_history"] == []
    assert body["shadow_summary_snapshot"] == passed_shadow["summary"]

    async with maker() as session:
        provider_count = (
            await session.execute(
                text(
                    "SELECT count(*) FROM capability_providers "
                    "WHERE provider_id = 'professor-lu-passed'"
                )
            )
        ).scalar_one()
        shadow_status = (
            await session.execute(
                text(
                    "SELECT status FROM provider_shadow_validation_runs WHERE run_id = 'run-passed'"
                )
            )
        ).scalar_one()
    assert provider_count == 0
    assert shadow_status == "passed"


async def test_provider_rollout_stage_progression_pause_cancel_and_listing(
    client: AsyncClient,
) -> None:
    await _create_passed_shadow_run(
        client,
        application_id="app-professor-lu",
        requested_provider_id="professor-lu-rollout",
    )
    create = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001",
        json=rollout_payload(),
    )
    assert create.status_code == 200, create.text

    skip = await client.post(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001/advance",
        json=rollout_action_payload(target_stage_percent=50),
    )
    assert skip.status_code == 422

    first = await client.post(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001/advance",
        json=rollout_action_payload(target_stage_percent=5),
    )
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["status"] == "active"
    assert first_body["current_stage_percent"] == 5
    assert first_body["started_at"] is not None
    assert [item["stage_percent"] for item in first_body["stage_history"]] == [5]

    pause = await client.post(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001/pause",
        json=rollout_action_payload(reason_ref="oss://provider-rollouts/reason-pause.json"),
    )
    assert pause.status_code == 200, pause.text
    assert pause.json()["status"] == "paused"
    assert pause.json()["paused_at"] is not None

    resume = await client.post(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001/advance",
        json=rollout_action_payload(target_stage_percent=50),
    )
    assert resume.status_code == 200, resume.text
    assert resume.json()["status"] == "active"
    assert resume.json()["current_stage_percent"] == 50
    assert resume.json()["started_at"] == first_body["started_at"]

    complete = await client.post(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001/advance",
        json=rollout_action_payload(target_stage_percent=100),
    )
    assert complete.status_code == 200, complete.text
    complete_body = complete.json()
    assert complete_body["status"] == "completed"
    assert complete_body["current_stage_percent"] == 100
    assert complete_body["completed_at"] is not None
    assert [item["action"] for item in complete_body["stage_history"]] == [
        "advance",
        "pause",
        "advance",
        "advance",
    ]

    replay = await client.post(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001/advance",
        json=rollout_action_payload(target_stage_percent=100),
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["completed_at"] == complete_body["completed_at"]
    assert replay.json()["stage_history"] == complete_body["stage_history"]

    cannot_cancel_completed = await client.post(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001/cancel",
        json=rollout_action_payload(reason_ref="oss://provider-rollouts/reason-cancel.json"),
    )
    assert cannot_cancel_completed.status_code == 422

    await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-002",
        json=rollout_payload(
            evidence_refs=["oss://provider-rollouts/app-professor-lu/run-001/rollout-002.json"]
        ),
    )
    cancel = await client.post(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-002/cancel",
        json=rollout_action_payload(reason_ref="oss://provider-rollouts/reason-cancel.json"),
    )
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "cancelled"
    cancel_replay = await client.post(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-002/cancel",
        json=rollout_action_payload(reason_ref="oss://provider-rollouts/reason-cancel.json"),
    )
    assert cancel_replay.status_code == 200, cancel_replay.text
    assert cancel_replay.json()["stage_history"] == cancel.json()["stage_history"]

    cancelled_advance = await client.post(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-002/advance",
        json=rollout_action_payload(target_stage_percent=5),
    )
    assert cancelled_advance.status_code == 422

    pause_with_target = await client.post(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-002/pause",
        json=rollout_action_payload(target_stage_percent=50),
    )
    assert pause_with_target.status_code == 422

    listed = await client.get(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts?status=completed&stage_percent=100"
    )
    assert listed.status_code == 200, listed.text
    assert [item["rollout_id"] for item in listed.json()] == ["rollout-001"]


async def test_provider_rollout_tenant_scope_and_write_auth(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = str(uuid.uuid4())
    await client.put(
        "/v1/provider-applications/app-global",
        json=provider_application_payload(status="submitted"),
    )
    await client.put(
        f"/v1/provider-applications/app-global/evaluation-requests/eval-tenant?tenant_id={tenant_id}",
        json=provider_evaluation_payload(
            tenant_id=tenant_id,
            evaluation_id="eval-tenant",
            status="queued",
        ),
    )
    tenant_run = await client.put(
        "/v1/provider-applications/app-global/evaluation-requests/eval-tenant/shadow-runs/run-001",
        json=shadow_run_payload(tenant_id=tenant_id),
    )
    assert tenant_run.status_code == 200, tenant_run.text

    global_rollout_against_tenant = await client.put(
        "/v1/provider-applications/app-global/evaluation-requests/eval-tenant"
        "/shadow-runs/run-001/rollouts/rollout-001",
        json=rollout_payload(),
    )
    assert global_rollout_against_tenant.status_code == 404

    async with client.stream(
        "POST",
        "/v1/provider-applications/app-global/evaluation-requests/eval-tenant"
        f"/shadow-runs/run-001/finalize?tenant_id={tenant_id}",
    ) as finalize:
        assert finalize.status_code == 200
    tenant_failed_rollout = await client.put(
        "/v1/provider-applications/app-global/evaluation-requests/eval-tenant"
        "/shadow-runs/run-001/rollouts/rollout-001",
        json=rollout_payload(tenant_id=tenant_id),
    )
    assert tenant_failed_rollout.status_code == 422

    await _create_passed_shadow_run(
        client,
        application_id="app-professor-lu",
        requested_provider_id="professor-lu-auth",
    )
    monkeypatch.setattr(
        "capability_registry.routes.settings.internal_secret",
        SecretStr("internal-test-secret"),
    )
    missing_auth = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001",
        json=rollout_payload(),
    )
    assert missing_auth.status_code == 401
    ok = await client.put(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001",
        json=rollout_payload(),
        headers={"X-Internal-Service-Auth": "internal-test-secret"},
    )
    assert ok.status_code == 200, ok.text
    missing_advance_auth = await client.post(
        "/v1/provider-applications/app-professor-lu/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001/advance",
        json=rollout_action_payload(target_stage_percent=5),
    )
    assert missing_advance_auth.status_code == 401


async def test_provider_route_share_dashboard_projection_filters_and_no_side_effects(
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    await _create_passed_shadow_run(
        client,
        application_id="app-route-share",
        requested_provider_id="professor-lu-route",
    )
    create = await client.put(
        "/v1/provider-applications/app-route-share/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001",
        json=rollout_payload(),
    )
    assert create.status_code == 200, create.text
    for target in (5, 50, 100):
        advance = await client.post(
            "/v1/provider-applications/app-route-share/evaluation-requests/eval-001"
            "/shadow-runs/run-001/rollouts/rollout-001/advance",
            json=rollout_action_payload(target_stage_percent=target),
        )
        assert advance.status_code == 200, advance.text
    draft = await client.put(
        "/v1/provider-applications/app-route-share/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-002",
        json=rollout_payload(
            evidence_refs=["oss://provider-rollouts/app-route-share/run-001/rollout-002.json"]
        ),
    )
    assert draft.status_code == 200, draft.text

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await session.execute(
            text(
                """
                INSERT INTO provider_gradient_rollouts (
                    application_row_id, evaluation_row_id, shadow_run_row_id,
                    application_id, evaluation_id, run_id, rollout_id,
                    requested_provider_id, baseline_provider_id, benchmark_suite,
                    status, current_stage_percent, stage_history,
                    shadow_summary_snapshot, evidence_refs, metadata,
                    created_at, updated_at
                )
                SELECT
                    application_row_id, evaluation_row_id, shadow_run_row_id,
                    application_id, evaluation_id, run_id, 'rollout-other-provider',
                    'baseline-only', baseline_provider_id, benchmark_suite,
                    'completed', 100, '[]'::jsonb,
                    shadow_summary_snapshot, '[]'::jsonb, '{}'::jsonb,
                    created_at, updated_at
                FROM provider_gradient_rollouts
                WHERE rollout_id = 'rollout-001'
                """
            )
        )
        before_rows = (
            (
                await session.execute(
                    text(
                        "SELECT rollout_id, status, current_stage_percent, stage_history "
                        "FROM provider_gradient_rollouts ORDER BY rollout_id"
                    )
                )
            )
            .mappings()
            .all()
        )
        await session.commit()

    response = await client.get("/v1/providers/professor-lu-route/route-share-dashboard")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider_id"] == "professor-lu-route"
    assert body["tenant_id"] is None
    assert body["total_rollouts"] == 2
    assert body["highest_current_stage_percent"] == 100
    assert body["status_counts"] == {
        "draft": 1,
        "active": 0,
        "paused": 0,
        "completed": 1,
        "cancelled": 0,
    }
    assert [item["rollout_id"] for item in body["current_rollouts"]] == [
        "rollout-001",
        "rollout-002",
    ]
    assert {item["scope_source"] for item in body["current_rollouts"]} == {"global"}
    assert "rollout-other-provider" not in json.dumps(body)
    assert "stage_history" not in json.dumps(body)
    assert "shadow_summary_snapshot" not in json.dumps(body)
    assert "reason_ref" not in json.dumps(body)

    timeline_by_rollout: dict[str, list[dict[str, Any]]] = {}
    for point in body["timeline"]:
        timeline_by_rollout.setdefault(point["rollout_id"], []).append(point)
    assert [point["action"] for point in timeline_by_rollout["rollout-001"]] == [
        "created",
        "advance",
        "advance",
        "advance",
    ]
    assert timeline_by_rollout["rollout-001"][0]["from_status"] is None
    assert timeline_by_rollout["rollout-001"][0]["to_status"] == "draft"
    assert timeline_by_rollout["rollout-001"][-1]["stage_percent"] == 100
    assert [point["action"] for point in timeline_by_rollout["rollout-002"]] == ["created"]

    filtered = await client.get(
        "/v1/providers/professor-lu-route/route-share-dashboard",
        params={"status": "completed", "stage_percent": "100"},
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["total_rollouts"] == 1
    assert filtered.json()["current_rollouts"][0]["rollout_id"] == "rollout-001"

    future = await client.get(
        "/v1/providers/professor-lu-route/route-share-dashboard",
        params={"from": "2999-01-01T00:00:00Z"},
    )
    assert future.status_code == 200, future.text
    assert future.json()["total_rollouts"] == 2
    assert future.json()["current_rollouts"]
    assert future.json()["timeline"] == []

    empty = await client.get("/v1/providers/provider-with-no-rollouts/route-share-dashboard")
    assert empty.status_code == 200, empty.text
    assert empty.json()["status_counts"] == {
        "draft": 0,
        "active": 0,
        "paused": 0,
        "completed": 0,
        "cancelled": 0,
    }
    assert empty.json()["highest_current_stage_percent"] == 0
    assert empty.json()["current_rollouts"] == []
    assert empty.json()["timeline"] == []

    async with maker() as session:
        after_rows = (
            (
                await session.execute(
                    text(
                        "SELECT rollout_id, status, current_stage_percent, stage_history "
                        "FROM provider_gradient_rollouts ORDER BY rollout_id"
                    )
                )
            )
            .mappings()
            .all()
        )
    assert before_rows == after_rows


async def test_provider_route_share_dashboard_tenant_scope_and_query_validation(
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    tenant_id = str(uuid.uuid4())
    await _create_passed_shadow_run(
        client,
        application_id="app-tenant-route-share",
        requested_provider_id="professor-lu-tenant",
    )
    create = await client.put(
        "/v1/provider-applications/app-tenant-route-share/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001",
        json=rollout_payload(),
    )
    assert create.status_code == 200, create.text

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await session.execute(
            text(
                """
                INSERT INTO provider_gradient_rollouts (
                    tenant_id, application_row_id, evaluation_row_id, shadow_run_row_id,
                    application_id, evaluation_id, run_id, rollout_id,
                    requested_provider_id, baseline_provider_id, benchmark_suite,
                    status, current_stage_percent, stage_history,
                    shadow_summary_snapshot, evidence_refs, metadata,
                    created_at, updated_at
                )
                SELECT
                    CAST(:tenant_id AS uuid), application_row_id, evaluation_row_id,
                    shadow_run_row_id, application_id, evaluation_id, run_id,
                    'rollout-tenant', requested_provider_id, baseline_provider_id,
                    benchmark_suite, 'active', 5,
                    jsonb_build_array(
                        jsonb_build_object(
                            'action', 'advance',
                            'stage_percent', 5,
                            'changed_at', '2026-06-01T00:00:00+00:00',
                            'from_status', 'draft',
                            'to_status', 'active'
                        )
                    ),
                    shadow_summary_snapshot, '[]'::jsonb, '{}'::jsonb,
                    created_at, updated_at
                FROM provider_gradient_rollouts
                WHERE rollout_id = 'rollout-001'
                """
            ),
            {"tenant_id": tenant_id},
        )
        await session.commit()

    global_dashboard = await client.get("/v1/providers/professor-lu-tenant/route-share-dashboard")
    assert global_dashboard.status_code == 200, global_dashboard.text
    assert global_dashboard.json()["total_rollouts"] == 1
    assert global_dashboard.json()["current_rollouts"][0]["scope_source"] == "global"
    assert global_dashboard.json()["current_rollouts"][0]["rollout_id"] == "rollout-001"

    tenant_dashboard = await client.get(
        "/v1/providers/professor-lu-tenant/route-share-dashboard",
        params={"tenant_id": tenant_id},
    )
    assert tenant_dashboard.status_code == 200, tenant_dashboard.text
    assert tenant_dashboard.json()["tenant_id"] == tenant_id
    assert tenant_dashboard.json()["total_rollouts"] == 1
    assert tenant_dashboard.json()["highest_current_stage_percent"] == 5
    assert tenant_dashboard.json()["current_rollouts"][0]["scope_source"] == "tenant"
    assert tenant_dashboard.json()["current_rollouts"][0]["rollout_id"] == "rollout-tenant"
    assert {point["scope_source"] for point in tenant_dashboard.json()["timeline"]} == {"tenant"}

    bad_stage = await client.get(
        "/v1/providers/professor-lu-tenant/route-share-dashboard",
        params={"stage_percent": "10"},
    )
    assert bad_stage.status_code == 422

    reversed_window = await client.get(
        "/v1/providers/professor-lu-tenant/route-share-dashboard",
        params={"from": "2026-06-02T00:00:00Z", "to": "2026-06-01T00:00:00Z"},
    )
    assert reversed_window.status_code == 422

    naive_window = await client.get(
        "/v1/providers/professor-lu-tenant/route-share-dashboard",
        params={"from": "2026-06-01T00:00:00"},
    )
    assert naive_window.status_code == 422


async def test_provider_route_share_dashboard_fails_closed_on_stage_history_drift(
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    await _create_passed_shadow_run(
        client,
        application_id="app-drift-route-share",
        requested_provider_id="professor-lu-drift",
    )
    create = await client.put(
        "/v1/provider-applications/app-drift-route-share/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001",
        json=rollout_payload(),
    )
    assert create.status_code == 200, create.text
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await session.execute(
            text(
                """
                UPDATE provider_gradient_rollouts
                SET stage_history = jsonb_build_array(
                    jsonb_build_object(
                        'action', 'advance',
                        'stage_percent', 75,
                        'changed_at', '2026-06-01T00:00:00+00:00',
                        'from_status', 'draft',
                        'to_status', 'active'
                    )
                )
                WHERE rollout_id = 'rollout-001'
                """
            )
        )
        await session.commit()

    drifted = await client.get("/v1/providers/professor-lu-drift/route-share-dashboard")
    assert drifted.status_code == 409
    assert "stage_percent" in drifted.text


async def test_provider_kpi_dashboard_projection_filters_timeline_and_no_side_effects(
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    await _create_passed_shadow_run(
        client,
        application_id="app-kpi",
        requested_provider_id="professor-lu-kpi",
    )
    create = await client.put(
        "/v1/provider-applications/app-kpi/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001",
        json=rollout_payload(),
    )
    assert create.status_code == 200, create.text
    advance = await client.post(
        "/v1/provider-applications/app-kpi/evaluation-requests/eval-001"
        "/shadow-runs/run-001/rollouts/rollout-001/advance",
        json=rollout_action_payload(target_stage_percent=5),
    )
    assert advance.status_code == 200, advance.text

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await session.execute(
            text(
                """
                UPDATE provider_shadow_validation_samples
                SET provider_status_code = 500,
                    provider_latency_ms = 300,
                    baseline_latency_ms = 100,
                    deviation_ratio = 0.010000
                WHERE sample_id = 'sample-000'
                """
            )
        )
        await session.execute(
            text(
                """
                UPDATE provider_shadow_validation_samples
                SET timed_out = true,
                    provider_latency_ms = 400,
                    baseline_latency_ms = 100,
                    deviation_ratio = 0.010000
                WHERE sample_id = 'sample-015'
                """
            )
        )
        await session.execute(
            text(
                """
                UPDATE provider_shadow_validation_samples
                SET deviation_ratio = 0.050000,
                    provider_latency_ms = 500,
                    baseline_latency_ms = 100
                WHERE sample_id = 'sample-030'
                """
            )
        )
        await session.execute(
            text(
                """
                INSERT INTO provider_shadow_validation_runs (
                    application_row_id, evaluation_row_id, application_id, evaluation_id,
                    run_id, requested_provider_id, benchmark_suite, evaluation_sample_count,
                    baseline_provider_id, status, started_at, ended_at, summary,
                    evidence_refs, metadata, created_at, updated_at
                )
                SELECT
                    application_row_id, evaluation_row_id, application_id, evaluation_id,
                    'run-baseline-only', baseline_provider_id, benchmark_suite,
                    evaluation_sample_count, baseline_provider_id, 'passed', started_at,
                    ended_at, summary, '[]'::jsonb, '{}'::jsonb, created_at, updated_at
                FROM provider_shadow_validation_runs
                WHERE run_id = 'run-001'
                """
            )
        )
        before_rows = (
            (
                await session.execute(
                    text(
                        "SELECT run_id, status, summary FROM provider_shadow_validation_runs "
                        "ORDER BY run_id"
                    )
                )
            )
            .mappings()
            .all()
        )
        await session.commit()

    response = await client.get("/v1/providers/professor-lu-kpi/kpi-dashboard")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider_id"] == "professor-lu-kpi"
    assert body["tenant_id"] is None
    assert body["total_runs"] == 1
    assert body["run_status_counts"] == {
        "draft": 0,
        "running": 0,
        "passed": 1,
        "failed": 0,
        "cancelled": 0,
    }
    assert body["aggregate"]["sample_count"] == 500
    assert body["aggregate"]["success_count"] == 497
    assert body["aggregate"]["failed_count"] == 3
    assert body["aggregate"]["timeout_count"] == 1
    assert body["aggregate"]["provider_error_count"] == 1
    assert body["aggregate"]["success_rate"] == "0.994000"
    assert body["aggregate"]["provider_p95_latency_ms"] == 100
    assert body["aggregate"]["baseline_p95_latency_ms"] == 100
    assert body["aggregate"]["p95_latency_ratio"] == "1.000000"
    assert body["rollout_summary"] == {
        "total_rollouts": 1,
        "highest_current_stage_percent": 5,
        "status_counts": {
            "draft": 0,
            "active": 1,
            "paused": 0,
            "completed": 0,
            "cancelled": 0,
        },
    }
    assert [item["run_id"] for item in body["run_metrics"]] == ["run-001"]
    run_metric = body["run_metrics"][0]
    assert run_metric["provider_id"] == "professor-lu-kpi"
    assert run_metric["baseline_provider_id"] == "highs"
    assert run_metric["metrics"]["failed_count"] == 3
    assert run_metric["threshold_violations"] == []
    assert set(run_metric["coverage_class_counts"]) == {
        "platform_standard",
        "provider_supplied",
        "adversarial",
        "desensitized_real",
    }
    assert "run-baseline-only" not in json.dumps(body)
    assert_json_key_absent(body, "summary")
    assert "stage_history" not in json.dumps(body)
    assert "shadow_summary_snapshot" not in json.dumps(body)
    assert "evidence_refs" not in json.dumps(body)
    assert "metadata" not in json.dumps(body)
    assert {point["scope_source"] for point in body["timeline"]} == {"global"}

    windowed = await client.get(
        "/v1/providers/professor-lu-kpi/kpi-dashboard",
        params={
            "from": "2026-06-01T00:00:00Z",
            "to": "2026-06-01T23:59:59Z",
            "run_status": "passed",
            "benchmark_suite": "lp_standard_500",
        },
    )
    assert windowed.status_code == 200, windowed.text
    windowed_body = windowed.json()
    assert windowed_body["total_runs"] == 1
    assert windowed_body["run_status_counts"]["passed"] == 1
    assert windowed_body["rollout_summary"]["total_rollouts"] == 1
    assert windowed_body["aggregate"]["sample_count"] == 34
    assert windowed_body["aggregate"]["success_count"] == 31
    assert len(windowed_body["timeline"]) == 1
    assert windowed_body["timeline"][0]["bucket_start"] == "2026-06-01T00:00:00Z"

    future = await client.get(
        "/v1/providers/professor-lu-kpi/kpi-dashboard",
        params={"from": "2999-01-01T00:00:00Z"},
    )
    assert future.status_code == 200, future.text
    assert future.json()["total_runs"] == 1
    assert future.json()["run_metrics"][0]["metrics"]["sample_count"] == 0
    assert future.json()["aggregate"]["sample_count"] == 0
    assert future.json()["timeline"] == []

    empty = await client.get("/v1/providers/provider-with-no-shadow-runs/kpi-dashboard")
    assert empty.status_code == 200, empty.text
    assert empty.json()["run_status_counts"] == {
        "draft": 0,
        "running": 0,
        "passed": 0,
        "failed": 0,
        "cancelled": 0,
    }
    assert empty.json()["aggregate"]["sample_count"] == 0
    assert empty.json()["rollout_summary"]["highest_current_stage_percent"] == 0
    assert empty.json()["run_metrics"] == []
    assert empty.json()["timeline"] == []

    async with maker() as session:
        after_rows = (
            (
                await session.execute(
                    text(
                        "SELECT run_id, status, summary FROM provider_shadow_validation_runs "
                        "ORDER BY run_id"
                    )
                )
            )
            .mappings()
            .all()
        )
    assert before_rows == after_rows


async def test_provider_kpi_dashboard_tenant_scope_and_query_validation(
    client: AsyncClient,
) -> None:
    tenant_id = str(uuid.uuid4())
    await _create_passed_shadow_run(
        client,
        application_id="app-kpi-global",
        requested_provider_id="professor-lu-kpi-tenant",
    )
    await _create_passed_shadow_run(
        client,
        application_id="app-kpi-tenant",
        requested_provider_id="professor-lu-kpi-tenant",
        tenant_id=tenant_id,
    )

    global_dashboard = await client.get("/v1/providers/professor-lu-kpi-tenant/kpi-dashboard")
    assert global_dashboard.status_code == 200, global_dashboard.text
    assert global_dashboard.json()["tenant_id"] is None
    assert global_dashboard.json()["total_runs"] == 1
    assert global_dashboard.json()["run_metrics"][0]["application_id"] == "app-kpi-global"
    assert global_dashboard.json()["run_metrics"][0]["scope_source"] == "global"

    tenant_dashboard = await client.get(
        "/v1/providers/professor-lu-kpi-tenant/kpi-dashboard",
        params={"tenant_id": tenant_id},
    )
    assert tenant_dashboard.status_code == 200, tenant_dashboard.text
    assert tenant_dashboard.json()["tenant_id"] == tenant_id
    assert tenant_dashboard.json()["total_runs"] == 1
    assert tenant_dashboard.json()["run_metrics"][0]["application_id"] == "app-kpi-tenant"
    assert tenant_dashboard.json()["run_metrics"][0]["scope_source"] == "tenant"
    assert {point["scope_source"] for point in tenant_dashboard.json()["timeline"]} == {"tenant"}

    reversed_window = await client.get(
        "/v1/providers/professor-lu-kpi-tenant/kpi-dashboard",
        params={"from": "2026-06-02T00:00:00Z", "to": "2026-06-01T00:00:00Z"},
    )
    assert reversed_window.status_code == 422

    naive_window = await client.get(
        "/v1/providers/professor-lu-kpi-tenant/kpi-dashboard",
        params={"from": "2026-06-01T00:00:00"},
    )
    assert naive_window.status_code == 422

    bad_benchmark = await client.get(
        "/v1/providers/professor-lu-kpi-tenant/kpi-dashboard",
        params={"benchmark_suite": "Bad Suite"},
    )
    assert bad_benchmark.status_code == 422


async def test_provider_kpi_dashboard_fails_closed_on_stored_drift(
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    await _create_passed_shadow_run(
        client,
        application_id="app-kpi-drift",
        requested_provider_id="professor-lu-kpi-drift",
    )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await session.execute(
            text(
                "ALTER TABLE provider_shadow_validation_runs "
                "DROP CONSTRAINT ck_provider_shadow_runs_status"
            )
        )
        await session.execute(
            text(
                """
                UPDATE provider_shadow_validation_runs
                SET status = 'manual-drift'
                WHERE run_id = 'run-001'
                """
            )
        )
        await session.commit()

    drifted_run = await client.get("/v1/providers/professor-lu-kpi-drift/kpi-dashboard")
    assert drifted_run.status_code == 409
    assert "status" in drifted_run.text

    async with maker() as session:
        await session.execute(
            text(
                """
                UPDATE provider_shadow_validation_runs
                SET status = 'passed'
                WHERE run_id = 'run-001'
                """
            )
        )
        await session.execute(
            text(
                """
                ALTER TABLE provider_shadow_validation_runs
                ADD CONSTRAINT ck_provider_shadow_runs_status
                CHECK (status IN ('draft', 'running', 'passed', 'failed', 'cancelled'))
                """
            )
        )
        await session.commit()

    async with maker() as session:
        await session.execute(
            text(
                "ALTER TABLE provider_shadow_validation_samples DROP CONSTRAINT ck_provider_shadow_samples_coverage_class"
            )
        )
        await session.execute(
            text(
                """
                UPDATE provider_shadow_validation_samples
                SET coverage_class = 'unknown'
                WHERE sample_id = 'sample-000'
                """
            )
        )
        await session.commit()

    drifted_sample = await client.get("/v1/providers/professor-lu-kpi-drift/kpi-dashboard")
    assert drifted_sample.status_code == 409
    assert "coverage_class" in drifted_sample.text

    async with maker() as session:
        await session.execute(
            text(
                """
                UPDATE provider_shadow_validation_samples
                SET coverage_class = 'platform_standard'
                WHERE sample_id = 'sample-000'
                """
            )
        )
        await session.execute(
            text(
                """
                ALTER TABLE provider_shadow_validation_samples
                ADD CONSTRAINT ck_provider_shadow_samples_coverage_class
                CHECK (coverage_class IN (
                    'platform_standard',
                    'provider_supplied',
                    'adversarial',
                    'desensitized_real'
                ))
                """
            )
        )
        await session.execute(
            text(
                """
                UPDATE provider_shadow_validation_samples
                SET tenant_id = gen_random_uuid()
                WHERE sample_id = 'sample-001'
                """
            )
        )
        await session.commit()

    tenant_mismatch = await client.get("/v1/providers/professor-lu-kpi-drift/kpi-dashboard")
    assert tenant_mismatch.status_code == 409
    assert "tenant scope" in tenant_mismatch.text

    async with maker() as session:
        await session.execute(
            text(
                """
                UPDATE provider_shadow_validation_samples
                SET tenant_id = NULL
                WHERE sample_id = 'sample-001'
                """
            )
        )
        await session.execute(
            text(
                "ALTER TABLE provider_gradient_rollouts DROP CONSTRAINT ck_provider_gradient_rollouts_stage"
            )
        )
        await session.execute(
            text(
                """
                INSERT INTO provider_gradient_rollouts (
                    application_row_id, evaluation_row_id, shadow_run_row_id,
                    application_id, evaluation_id, run_id, rollout_id,
                    requested_provider_id, baseline_provider_id, benchmark_suite,
                    status, current_stage_percent, stage_history,
                    shadow_summary_snapshot, evidence_refs, metadata,
                    created_at, updated_at
                )
                SELECT
                    application_row_id, evaluation_row_id, id,
                    application_id, evaluation_id, run_id, 'rollout-drift',
                    requested_provider_id, baseline_provider_id, benchmark_suite,
                    'active', 75, '[]'::jsonb, summary, '[]'::jsonb, '{}'::jsonb,
                    created_at, updated_at
                FROM provider_shadow_validation_runs
                WHERE run_id = 'run-001'
                """
            )
        )
        await session.commit()

    rollout_drift = await client.get("/v1/providers/professor-lu-kpi-drift/kpi-dashboard")
    assert rollout_drift.status_code == 409
    assert "current_stage_percent" in rollout_drift.text

    async with maker() as session:
        await session.execute(
            text(
                """
                UPDATE provider_gradient_rollouts
                SET current_stage_percent = 5
                WHERE rollout_id = 'rollout-drift'
                """
            )
        )
        await session.execute(
            text(
                """
                ALTER TABLE provider_gradient_rollouts
                ADD CONSTRAINT ck_provider_gradient_rollouts_stage
                CHECK (current_stage_percent IN (0, 5, 50, 100))
                """
            )
        )
        await session.commit()


def test_provider_kpi_dashboard_openapi_contract_is_safe() -> None:
    spec = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    dashboard_schemas = {
        name: schema
        for name, schema in spec["components"]["schemas"].items()
        if name.startswith("ProviderKpi")
    }
    assert dashboard_schemas
    forbidden_terms = {
        "summary",
        "stage_history",
        "shadow_summary_snapshot",
        "evidence_refs",
        "metadata",
        "reason_ref",
        "api_key",
        "password",
        "client_secret",
        "access_token",
        "refresh_token",
        "registry_password",
        "docker_password",
        "bank_account",
        "tax_id",
        "payout_status",
        "settlement_id",
        "raw_dataset",
        "raw_request",
        "raw_response",
        "provider_request",
        "provider_response",
        "routing_payload",
        "customer_payload",
    }
    for schema in dashboard_schemas.values():
        properties = set(schema.get("properties", {}))
        assert properties.isdisjoint(forbidden_terms)

    for schema_name in ("ProviderKpiRunMetric", "ProviderKpiTimelinePoint"):
        scope_enum = dashboard_schemas[schema_name]["properties"]["scope_source"]["enum"]
        assert scope_enum == ["global", "tenant"]

    endpoint = spec["paths"]["/v1/providers/{provider_id}/kpi-dashboard"]["get"]
    parameters = {parameter["name"]: parameter for parameter in endpoint["parameters"]}
    assert {"provider_id", "tenant_id", "from", "to", "run_status", "benchmark_suite"}.issubset(
        set(parameters)
    )


def test_provider_rollout_openapi_omits_unsafe_fields() -> None:
    spec = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    rollout_schemas = {
        name: schema
        for name, schema in spec["components"]["schemas"].items()
        if name.startswith("ProviderRollout")
    }
    assert rollout_schemas
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
        "raw_request",
        "raw_response",
        "provider_request",
        "provider_response",
        "routing_payload",
        "customer_payload",
    }
    request_properties = set(rollout_schemas["ProviderRolloutUpsertRequest"].get("properties", {}))
    action_properties = set(rollout_schemas["ProviderRolloutActionRequest"].get("properties", {}))
    response_properties = set(rollout_schemas["ProviderRolloutResponse"].get("properties", {}))
    assert "stage_history" not in request_properties
    assert "shadow_summary_snapshot" not in request_properties
    assert "current_stage_percent" not in request_properties
    assert "target_stage_percent" in action_properties
    assert "stage_history" in response_properties
    assert "shadow_summary_snapshot" in response_properties
    for schema in rollout_schemas.values():
        properties = set(schema.get("properties", {}))
        assert properties.isdisjoint(forbidden_terms)


def test_provider_route_share_dashboard_openapi_contract_is_safe() -> None:
    spec = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    dashboard_schemas = {
        name: schema
        for name, schema in spec["components"]["schemas"].items()
        if name.startswith("ProviderRouteShare")
    }
    assert dashboard_schemas
    forbidden_terms = {
        "stage_history",
        "shadow_summary_snapshot",
        "evidence_refs",
        "metadata",
        "reason_ref",
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
        "raw_request",
        "raw_response",
        "provider_request",
        "provider_response",
        "routing_payload",
        "customer_payload",
    }
    for schema in dashboard_schemas.values():
        properties = set(schema.get("properties", {}))
        assert properties.isdisjoint(forbidden_terms)

    for schema_name in (
        "ProviderRouteShareCurrentRollout",
        "ProviderRouteShareTimelinePoint",
    ):
        scope_enum = dashboard_schemas[schema_name]["properties"]["scope_source"]["enum"]
        assert scope_enum == ["global", "tenant"]

    endpoint = spec["paths"]["/v1/providers/{provider_id}/route-share-dashboard"]["get"]
    parameters = {parameter["name"]: parameter for parameter in endpoint["parameters"]}
    parameter_names = set(parameters)
    assert {"provider_id", "tenant_id", "from", "to", "status", "stage_percent"}.issubset(
        parameter_names
    )
    assert parameters["stage_percent"]["schema"]["enum"] == [0, 5, 50, 100]
