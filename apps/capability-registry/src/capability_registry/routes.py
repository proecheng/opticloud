"""Capability-registry API routes."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from math import ceil
from typing import Annotated, Any, Protocol, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from starlette.responses import Response

from capability_registry.cache import CAPABILITY_CACHE_PREFIX, CapabilityCache, cache_key
from capability_registry.config import settings
from capability_registry.db import get_session
from capability_registry.models import (
    Capability,
    CapabilityProvider,
    CapabilityTag,
    ProviderApplication,
    ProviderApplicationEvaluationRequest,
    ProviderGradientRollout,
    ProviderOAuthFlow,
    ProviderShadowValidationRun,
    ProviderShadowValidationSample,
    RevenueShareHook,
    RevenueSharePolicy,
)
from capability_registry.schemas import (
    CapabilityResponse,
    CapabilityUpsertRequest,
    ModelVersion,
    OAuthFlowResponse,
    OAuthFlowUpsertRequest,
    ProviderApplicationResponse,
    ProviderApplicationStatus,
    ProviderApplicationUpsertRequest,
    ProviderEvaluationResponse,
    ProviderEvaluationStatus,
    ProviderEvaluationUpsertRequest,
    ProviderKpiAggregateMetrics,
    ProviderKpiDashboardResponse,
    ProviderKpiRolloutSummary,
    ProviderKpiRunMetric,
    ProviderKpiRunStatusCounts,
    ProviderKpiTimelinePoint,
    ProviderResponse,
    ProviderRolloutActionRequest,
    ProviderRolloutResponse,
    ProviderRolloutStage,
    ProviderRolloutStatus,
    ProviderRolloutUpsertRequest,
    ProviderRouteShareAction,
    ProviderRouteShareCurrentRollout,
    ProviderRouteShareDashboardResponse,
    ProviderRouteShareScopeSource,
    ProviderRouteShareStatusCounts,
    ProviderRouteShareTimelinePoint,
    ProviderShadowCoverageClass,
    ProviderShadowRunResponse,
    ProviderShadowRunStatus,
    ProviderShadowRunSummary,
    ProviderShadowRunUpsertRequest,
    ProviderShadowSampleResponse,
    ProviderShadowSampleUpsertRequest,
    ProviderUpsertRequest,
    RevenueShareHookCreateRequest,
    RevenueShareHookResponse,
    RevenueSharePolicyResponse,
    RevenueSharePolicyUpsertRequest,
    ScopeSource,
)

router = APIRouter(prefix="/v1")
health_router = APIRouter(tags=["health"])
cache = CapabilityCache(settings.redis_url, settings.cache_ttl_seconds)
_PATH_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{0,63}$"
_SHADOW_REQUIRED_COVERAGE_CLASSES: tuple[ProviderShadowCoverageClass, ...] = (
    "platform_standard",
    "provider_supplied",
    "adversarial",
    "desensitized_real",
)
_SHADOW_MIN_OBSERVED_DAYS = 14
_SHADOW_MIN_SAMPLE_COUNT = 500
_SHADOW_MIN_SAMPLES_PER_COVERAGE_CLASS = 1
_SHADOW_MIN_SUCCESS_RATE = Decimal("0.980000")
_SHADOW_MAX_AVERAGE_DEVIATION = Decimal("0.020000")
_SHADOW_MAX_P95_LATENCY_RATIO = Decimal("1.500000")
_ROLLOUT_STAGES: tuple[ProviderRolloutStage, ...] = (0, 5, 50, 100)
_RATIO_QUANT = Decimal("0.000001")


class CacheBackend(Protocol):
    async def get_json(self, key: str) -> Any | None: ...

    async def set_json(self, key: str, value: Any) -> None: ...

    async def delete_pattern(self, pattern: str) -> None: ...


async def get_cache() -> CacheBackend:
    return cache


@health_router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@health_router.get("/readyz")
async def readyz(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    try:
        await session.execute(select(1))
    except Exception as exc:
        return {"status": "not-ready", "deps": {"db": f"error: {type(exc).__name__}"}}
    return {"status": "ready", "deps": {"db": "ok"}}


@health_router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _secret_value() -> str:
    return settings.internal_secret.get_secret_value()


def _require_write_auth(header_value: str | None) -> None:
    expected = _secret_value()
    if not expected:
        return
    if not header_value or not secrets.compare_digest(header_value, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid internal auth"
        )


def _scope_source(
    row_tenant_id: uuid.UUID | None, requested_tenant_id: uuid.UUID | None
) -> ScopeSource:
    if row_tenant_id is None and requested_tenant_id is not None:
        return "global_fallback"
    if row_tenant_id is None:
        return "global"
    return "tenant"


async def _cached(cache_backend: CacheBackend, key: str) -> Any | None:
    try:
        return await cache_backend.get_json(key)
    except Exception:
        return None


async def _cache_set(cache_backend: CacheBackend, key: str, value: Any) -> None:
    try:
        await cache_backend.set_json(key, value)
    except Exception:
        return


async def _invalidate_cache(cache_backend: CacheBackend) -> None:
    try:
        await cache_backend.delete_pattern(f"{CAPABILITY_CACHE_PREFIX}*")
    except Exception:
        return


async def _load_provider_row(
    session: AsyncSession,
    *,
    provider_id: str,
    tenant_id: uuid.UUID | None,
    allow_global_fallback: bool,
) -> CapabilityProvider | None:
    if tenant_id is not None:
        row = (
            await session.execute(
                select(CapabilityProvider).where(
                    CapabilityProvider.provider_id == provider_id,
                    CapabilityProvider.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is not None or not allow_global_fallback:
            return row
    return (
        await session.execute(
            select(CapabilityProvider).where(
                CapabilityProvider.provider_id == provider_id,
                CapabilityProvider.tenant_id.is_(None),
            )
        )
    ).scalar_one_or_none()


async def _load_capability_row(
    session: AsyncSession,
    *,
    k_algo: str,
    tenant_id: uuid.UUID | None,
    allow_global_fallback: bool,
) -> Capability | None:
    if tenant_id is not None:
        row = (
            await session.execute(
                select(Capability).where(
                    Capability.k_algo == k_algo,
                    Capability.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is not None or not allow_global_fallback:
            return row
    return (
        await session.execute(
            select(Capability).where(Capability.k_algo == k_algo, Capability.tenant_id.is_(None))
        )
    ).scalar_one_or_none()


async def _provider_response(
    row: CapabilityProvider,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderResponse:
    return ProviderResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        provider_id=row.provider_id,
        kind=cast(Any, row.kind),
        display_name=row.display_name,
        provider_url=row.provider_url,
        status=cast(Any, row.status),
        openapi_url=row.openapi_url,
        openapi_sha256=row.openapi_sha256,
        image_digest=row.image_digest,
        cosign_bundle=dict(row.cosign_bundle),
        scope_source=_scope_source(row.tenant_id, requested_tenant_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _capability_tags(session: AsyncSession, capability_id: uuid.UUID) -> list[str]:
    rows = (
        await session.execute(
            select(CapabilityTag.tag)
            .where(CapabilityTag.capability_id == capability_id)
            .order_by(CapabilityTag.tag)
        )
    ).scalars()
    return list(rows)


async def _capability_response(
    session: AsyncSession,
    row: Capability,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> CapabilityResponse:
    provider = await _load_provider_row(
        session,
        provider_id=row.provider_id,
        tenant_id=row.tenant_id,
        allow_global_fallback=True,
    )
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"provider {row.provider_id} is not configured",
        )
    tags = await _capability_tags(session, row.id)
    return CapabilityResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        k_algo=row.k_algo,
        task_type=row.task_type,
        tier=row.tier,
        status=cast(Any, row.status),
        provider_id=row.provider_id,
        model_version=ModelVersion(
            provider_id=row.provider_id,
            kind=cast(Any, provider.kind),
            version=row.model_version,
            provider_url=provider.provider_url,
        ),
        supported_solvers=list(row.supported_solvers),
        description_zh=row.description_zh,
        description_en=row.description_en,
        examples=list(row.examples),
        metadata=dict(row.capability_metadata),
        tags=tags,
        scope_source=_scope_source(row.tenant_id, requested_tenant_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _oauth_response(
    row: ProviderOAuthFlow,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> OAuthFlowResponse:
    return OAuthFlowResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        provider_id=row.provider_id,
        authorization_url=row.authorization_url,
        token_url=row.token_url,
        scopes=list(row.scopes),
        status=cast(Any, row.status),
        client_id_ref=row.client_id_ref,
        client_secret_ref=row.client_secret_ref,
        vault_secret_ref=row.vault_secret_ref,
        metadata=dict(row.flow_metadata),
        scope_source=_scope_source(row.tenant_id, requested_tenant_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _assert_path_id(body_value: str | None, path_value: str, field_name: str) -> None:
    if body_value is not None and body_value != path_value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must match path",
        )


@router.get("/providers", response_model=list[ProviderResponse], tags=["providers"])
async def list_providers(
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    cache_backend: CacheBackend = Depends(get_cache),
) -> list[ProviderResponse]:
    key = cache_key("providers:list", tenant_id=tenant_id or "global")
    cached = await _cached(cache_backend, key)
    if isinstance(cached, list):
        return [ProviderResponse.model_validate(item) for item in cached]

    global_rows = (
        await session.execute(
            select(CapabilityProvider)
            .where(CapabilityProvider.tenant_id.is_(None))
            .order_by(CapabilityProvider.provider_id)
        )
    ).scalars()
    rows_by_provider = {row.provider_id: row for row in global_rows}
    if tenant_id is not None:
        tenant_rows = (
            await session.execute(
                select(CapabilityProvider)
                .where(CapabilityProvider.tenant_id == tenant_id)
                .order_by(CapabilityProvider.provider_id)
            )
        ).scalars()
        for row in tenant_rows:
            rows_by_provider[row.provider_id] = row
    responses = [
        await _provider_response(row, requested_tenant_id=tenant_id)
        for row in sorted(rows_by_provider.values(), key=lambda item: item.provider_id)
    ]
    await _cache_set(
        cache_backend,
        key,
        [item.model_dump(mode="json") for item in responses],
    )
    return responses


@router.get("/providers/{provider_id}", response_model=ProviderResponse, tags=["providers"])
async def get_provider(
    provider_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    cache_backend: CacheBackend = Depends(get_cache),
) -> ProviderResponse:
    key = cache_key("providers:detail", provider_id=provider_id, tenant_id=tenant_id or "global")
    cached = await _cached(cache_backend, key)
    if isinstance(cached, dict):
        return ProviderResponse.model_validate(cached)
    row = await _load_provider_row(
        session,
        provider_id=provider_id,
        tenant_id=tenant_id,
        allow_global_fallback=tenant_id is not None,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="provider not found")
    response = await _provider_response(row, requested_tenant_id=tenant_id)
    await _cache_set(cache_backend, key, response.model_dump(mode="json"))
    return response


@router.put("/providers/{provider_id}", response_model=ProviderResponse, tags=["providers"])
async def upsert_provider(
    provider_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    body: ProviderUpsertRequest,
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
    cache_backend: CacheBackend = Depends(get_cache),
) -> ProviderResponse:
    _require_write_auth(x_internal_service_auth)
    _assert_path_id(body.provider_id, provider_id, "provider_id")
    row = await _load_provider_row(
        session,
        provider_id=provider_id,
        tenant_id=body.tenant_id,
        allow_global_fallback=False,
    )
    now = datetime.now(UTC)
    if row is None:
        row = CapabilityProvider(
            tenant_id=body.tenant_id,
            provider_id=provider_id,
            kind=body.kind,
            display_name=body.display_name,
            provider_url=body.provider_url,
            status=body.status,
            openapi_url=body.openapi_url,
            openapi_sha256=body.openapi_sha256,
            image_digest=body.image_digest,
            cosign_bundle=body.cosign_bundle,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.kind = body.kind
        row.display_name = body.display_name
        row.provider_url = body.provider_url
        row.status = body.status
        row.openapi_url = body.openapi_url
        row.openapi_sha256 = body.openapi_sha256
        row.image_digest = body.image_digest
        row.cosign_bundle = body.cosign_bundle
        row.updated_at = now
    await session.flush()
    await _invalidate_cache(cache_backend)
    return await _provider_response(row, requested_tenant_id=body.tenant_id)


@router.get("/capabilities", response_model=list[CapabilityResponse], tags=["capabilities"])
async def list_capabilities(
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    cache_backend: CacheBackend = Depends(get_cache),
) -> list[CapabilityResponse]:
    key = cache_key("capabilities:list", tenant_id=tenant_id or "global")
    cached = await _cached(cache_backend, key)
    if isinstance(cached, list):
        return [CapabilityResponse.model_validate(item) for item in cached]
    global_rows = (
        await session.execute(
            select(Capability).where(Capability.tenant_id.is_(None)).order_by(Capability.k_algo)
        )
    ).scalars()
    rows_by_algo = {row.k_algo: row for row in global_rows}
    if tenant_id is not None:
        tenant_rows = (
            await session.execute(
                select(Capability)
                .where(Capability.tenant_id == tenant_id)
                .order_by(Capability.k_algo)
            )
        ).scalars()
        for row in tenant_rows:
            rows_by_algo[row.k_algo] = row
    responses = [
        await _capability_response(session, row, requested_tenant_id=tenant_id)
        for row in sorted(rows_by_algo.values(), key=lambda item: item.k_algo)
    ]
    await _cache_set(cache_backend, key, [item.model_dump(mode="json") for item in responses])
    return responses


@router.get("/capabilities/{k_algo}", response_model=CapabilityResponse, tags=["capabilities"])
async def get_capability(
    k_algo: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    cache_backend: CacheBackend = Depends(get_cache),
) -> CapabilityResponse:
    key = cache_key("capabilities:detail", k_algo=k_algo, tenant_id=tenant_id or "global")
    cached = await _cached(cache_backend, key)
    if isinstance(cached, dict):
        return CapabilityResponse.model_validate(cached)
    row = await _load_capability_row(
        session,
        k_algo=k_algo,
        tenant_id=tenant_id,
        allow_global_fallback=tenant_id is not None,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="capability not found")
    response = await _capability_response(session, row, requested_tenant_id=tenant_id)
    await _cache_set(cache_backend, key, response.model_dump(mode="json"))
    return response


@router.put("/capabilities/{k_algo}", response_model=CapabilityResponse, tags=["capabilities"])
async def upsert_capability(
    k_algo: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    body: CapabilityUpsertRequest,
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
    cache_backend: CacheBackend = Depends(get_cache),
) -> CapabilityResponse:
    _require_write_auth(x_internal_service_auth)
    _assert_path_id(body.k_algo, k_algo, "k_algo")
    provider = await _load_provider_row(
        session,
        provider_id=body.provider_id,
        tenant_id=body.tenant_id,
        allow_global_fallback=True,
    )
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="provider not found"
        )
    row = await _load_capability_row(
        session,
        k_algo=k_algo,
        tenant_id=body.tenant_id,
        allow_global_fallback=False,
    )
    now = datetime.now(UTC)
    if row is None:
        row = Capability(
            tenant_id=body.tenant_id,
            k_algo=k_algo,
            task_type=body.task_type,
            tier=body.tier,
            status=body.status,
            provider_id=body.provider_id,
            model_version=body.model_version,
            supported_solvers=body.supported_solvers,
            description_zh=body.description_zh,
            description_en=body.description_en,
            examples=body.examples,
            capability_metadata=body.metadata,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.flush()
    else:
        row.task_type = body.task_type
        row.tier = body.tier
        row.status = body.status
        row.provider_id = body.provider_id
        row.model_version = body.model_version
        row.supported_solvers = body.supported_solvers
        row.description_zh = body.description_zh
        row.description_en = body.description_en
        row.examples = body.examples
        row.capability_metadata = body.metadata
        row.updated_at = now
        await session.flush()
    await session.execute(delete(CapabilityTag).where(CapabilityTag.capability_id == row.id))
    for tag in body.tags:
        session.add(CapabilityTag(capability_id=row.id, tag=tag, created_at=now))
    await session.flush()
    await _invalidate_cache(cache_backend)
    return await _capability_response(session, row, requested_tenant_id=body.tenant_id)


async def _load_oauth_row(
    session: AsyncSession,
    *,
    provider_id: str,
    tenant_id: uuid.UUID | None,
    allow_global_fallback: bool,
) -> ProviderOAuthFlow | None:
    if tenant_id is not None:
        row = (
            await session.execute(
                select(ProviderOAuthFlow).where(
                    ProviderOAuthFlow.provider_id == provider_id,
                    ProviderOAuthFlow.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is not None or not allow_global_fallback:
            return row
    return (
        await session.execute(
            select(ProviderOAuthFlow).where(
                ProviderOAuthFlow.provider_id == provider_id,
                ProviderOAuthFlow.tenant_id.is_(None),
            )
        )
    ).scalar_one_or_none()


@router.get(
    "/providers/{provider_id}/oauth-flow",
    response_model=OAuthFlowResponse,
    tags=["provider-oauth"],
)
async def get_oauth_flow(
    provider_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> OAuthFlowResponse:
    row = await _load_oauth_row(
        session,
        provider_id=provider_id,
        tenant_id=tenant_id,
        allow_global_fallback=tenant_id is not None,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="oauth flow not found")
    return await _oauth_response(row, requested_tenant_id=tenant_id)


@router.put(
    "/providers/{provider_id}/oauth-flow",
    response_model=OAuthFlowResponse,
    tags=["provider-oauth"],
)
async def upsert_oauth_flow(
    provider_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    body: OAuthFlowUpsertRequest,
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> OAuthFlowResponse:
    _require_write_auth(x_internal_service_auth)
    _assert_path_id(body.provider_id, provider_id, "provider_id")
    provider = await _load_provider_row(
        session,
        provider_id=provider_id,
        tenant_id=body.tenant_id,
        allow_global_fallback=True,
    )
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="provider not found"
        )
    row = await _load_oauth_row(
        session,
        provider_id=provider_id,
        tenant_id=body.tenant_id,
        allow_global_fallback=False,
    )
    now = datetime.now(UTC)
    if row is None:
        row = ProviderOAuthFlow(
            tenant_id=body.tenant_id,
            provider_id=provider_id,
            authorization_url=body.authorization_url,
            token_url=body.token_url,
            scopes=body.scopes,
            status=body.status,
            client_id_ref=body.client_id_ref,
            client_secret_ref=body.client_secret_ref,
            vault_secret_ref=body.vault_secret_ref,
            flow_metadata=body.metadata,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.authorization_url = body.authorization_url
        row.token_url = body.token_url
        row.scopes = body.scopes
        row.status = body.status
        row.client_id_ref = body.client_id_ref
        row.client_secret_ref = body.client_secret_ref
        row.vault_secret_ref = body.vault_secret_ref
        row.flow_metadata = body.metadata
        row.updated_at = now
    await session.flush()
    return await _oauth_response(row, requested_tenant_id=body.tenant_id)


@router.post("/providers/{provider_id}/oauth-flow/execute", tags=["provider-oauth"])
async def execute_oauth_flow(
    provider_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"OAuth execution for provider {provider_id} is reserved for v2",
    )


async def _load_revenue_policy_row(
    session: AsyncSession,
    *,
    policy_id: str,
    tenant_id: uuid.UUID | None,
    allow_global_fallback: bool,
) -> RevenueSharePolicy | None:
    if tenant_id is not None:
        row = (
            await session.execute(
                select(RevenueSharePolicy).where(
                    RevenueSharePolicy.policy_id == policy_id,
                    RevenueSharePolicy.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is not None or not allow_global_fallback:
            return row
    return (
        await session.execute(
            select(RevenueSharePolicy).where(
                RevenueSharePolicy.policy_id == policy_id,
                RevenueSharePolicy.tenant_id.is_(None),
            )
        )
    ).scalar_one_or_none()


async def _revenue_policy_response(
    row: RevenueSharePolicy,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> RevenueSharePolicyResponse:
    return RevenueSharePolicyResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        policy_id=row.policy_id,
        provider_kind=cast(Any, row.provider_kind),
        platform_share_ratio=row.platform_share_ratio,
        provider_share_ratio=row.provider_share_ratio,
        status=cast(Any, row.status),
        effective_from=row.effective_from,
        effective_until=row.effective_until,
        metadata=dict(row.policy_metadata),
        scope_source=_scope_source(row.tenant_id, requested_tenant_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.put(
    "/revenue-share/policies/{policy_id}",
    response_model=RevenueSharePolicyResponse,
    tags=["revenue-share"],
)
async def upsert_revenue_share_policy(
    policy_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    body: RevenueSharePolicyUpsertRequest,
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> RevenueSharePolicyResponse:
    _require_write_auth(x_internal_service_auth)
    _assert_path_id(body.policy_id, policy_id, "policy_id")
    row = await _load_revenue_policy_row(
        session,
        policy_id=policy_id,
        tenant_id=body.tenant_id,
        allow_global_fallback=False,
    )
    now = datetime.now(UTC)
    if row is None:
        row = RevenueSharePolicy(
            tenant_id=body.tenant_id,
            policy_id=policy_id,
            provider_kind=body.provider_kind,
            platform_share_ratio=body.platform_share_ratio,
            provider_share_ratio=body.provider_share_ratio,
            status=body.status,
            effective_from=body.effective_from,
            effective_until=body.effective_until,
            policy_metadata=body.metadata,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.provider_kind = body.provider_kind
        row.platform_share_ratio = body.platform_share_ratio
        row.provider_share_ratio = body.provider_share_ratio
        row.status = body.status
        row.effective_from = body.effective_from
        row.effective_until = body.effective_until
        row.policy_metadata = body.metadata
        row.updated_at = now
    await session.flush()
    return await _revenue_policy_response(row, requested_tenant_id=body.tenant_id)


@router.get(
    "/revenue-share/policies/{policy_id}",
    response_model=RevenueSharePolicyResponse,
    tags=["revenue-share"],
)
async def get_revenue_share_policy(
    policy_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> RevenueSharePolicyResponse:
    row = await _load_revenue_policy_row(
        session,
        policy_id=policy_id,
        tenant_id=tenant_id,
        allow_global_fallback=tenant_id is not None,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="policy not found")
    return await _revenue_policy_response(row, requested_tenant_id=tenant_id)


@router.get(
    "/revenue-share/policies",
    response_model=list[RevenueSharePolicyResponse],
    tags=["revenue-share"],
)
async def list_revenue_share_policies(
    tenant_id: uuid.UUID | None = Query(default=None),
    provider_kind: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[RevenueSharePolicyResponse]:
    conditions: list[ColumnElement[bool]] = [RevenueSharePolicy.tenant_id.is_(None)]
    if tenant_id is not None:
        tenant_rows = (
            await session.execute(
                select(RevenueSharePolicy).where(RevenueSharePolicy.tenant_id == tenant_id)
            )
        ).scalars()
        rows_by_policy = {row.policy_id: row for row in tenant_rows}
    else:
        rows_by_policy = {}
    if provider_kind is not None:
        conditions.append(RevenueSharePolicy.provider_kind == provider_kind)
    global_rows = (
        await session.execute(
            select(RevenueSharePolicy).where(*conditions).order_by(RevenueSharePolicy.policy_id)
        )
    ).scalars()
    for row in global_rows:
        rows_by_policy.setdefault(row.policy_id, row)
    rows = sorted(rows_by_policy.values(), key=lambda item: item.policy_id)
    if provider_kind is not None:
        rows = [row for row in rows if row.provider_kind == provider_kind]
    return [await _revenue_policy_response(row, requested_tenant_id=tenant_id) for row in rows]


async def _revenue_hook_response(
    row: RevenueShareHook,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> RevenueShareHookResponse:
    return RevenueShareHookResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        provider_id=row.provider_id,
        k_algo=row.k_algo,
        policy_id=row.policy_id,
        source_service=row.source_service,
        source_event_id=row.source_event_id,
        billing_saga_id=row.billing_saga_id,
        billing_ledger_id=row.billing_ledger_id,
        period_month=row.period_month,
        gross_amount_ref=row.gross_amount_ref,
        currency=row.currency,
        status=cast(Any, row.status),
        metadata=dict(row.hook_metadata),
        scope_source=_scope_source(row.tenant_id, requested_tenant_id),
        created_at=row.created_at,
    )


async def _validate_revenue_share_hook_references(
    session: AsyncSession,
    body: RevenueShareHookCreateRequest,
) -> None:
    provider = await _load_provider_row(
        session,
        provider_id=body.provider_id,
        tenant_id=body.tenant_id,
        allow_global_fallback=True,
    )
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="provider not found",
        )
    capability = await _load_capability_row(
        session,
        k_algo=body.k_algo,
        tenant_id=body.tenant_id,
        allow_global_fallback=True,
    )
    if capability is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="capability not found",
        )
    if capability.provider_id != body.provider_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="capability provider mismatch",
        )
    policy = await _load_revenue_policy_row(
        session,
        policy_id=body.policy_id,
        tenant_id=body.tenant_id,
        allow_global_fallback=True,
    )
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="policy not found",
        )


async def _load_revenue_hook_by_source_event(
    session: AsyncSession,
    *,
    source_service: str,
    source_event_id: uuid.UUID,
) -> RevenueShareHook | None:
    return (
        await session.execute(
            select(RevenueShareHook).where(
                RevenueShareHook.source_service == source_service,
                RevenueShareHook.source_event_id == source_event_id,
            )
        )
    ).scalar_one_or_none()


async def _load_provider_application_row(
    session: AsyncSession,
    *,
    application_id: str,
    tenant_id: uuid.UUID | None,
    allow_global_fallback: bool,
) -> ProviderApplication | None:
    if tenant_id is not None:
        row = (
            await session.execute(
                select(ProviderApplication).where(
                    ProviderApplication.application_id == application_id,
                    ProviderApplication.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is not None or not allow_global_fallback:
            return row
    return (
        await session.execute(
            select(ProviderApplication).where(
                ProviderApplication.application_id == application_id,
                ProviderApplication.tenant_id.is_(None),
            )
        )
    ).scalar_one_or_none()


async def _load_provider_application_by_requested_provider(
    session: AsyncSession,
    *,
    requested_provider_id: str,
    tenant_id: uuid.UUID | None,
) -> ProviderApplication | None:
    return (
        await session.execute(
            select(ProviderApplication).where(
                ProviderApplication.requested_provider_id == requested_provider_id,
                (
                    ProviderApplication.tenant_id.is_(None)
                    if tenant_id is None
                    else ProviderApplication.tenant_id == tenant_id
                ),
            )
        )
    ).scalar_one_or_none()


async def _provider_application_response(
    row: ProviderApplication,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderApplicationResponse:
    return ProviderApplicationResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        application_id=row.application_id,
        requested_provider_id=row.requested_provider_id,
        provider_kind=cast(Any, row.provider_kind),
        display_name=row.display_name,
        organization_name=row.organization_name,
        contact_email=row.contact_email,
        homepage_url=row.homepage_url,
        openapi_url=row.openapi_url,
        openapi_sha256=row.openapi_sha256,
        image_digest=row.image_digest,
        cosign_bundle=dict(row.cosign_bundle),
        evaluation_profile=dict(row.evaluation_profile),
        status=cast(Any, row.status),
        submitted_at=row.submitted_at,
        metadata=dict(row.application_metadata),
        scope_source=_scope_source(row.tenant_id, requested_tenant_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _material_application_values(body: ProviderApplicationUpsertRequest) -> dict[str, Any]:
    return {
        "requested_provider_id": body.requested_provider_id,
        "provider_kind": body.provider_kind,
        "openapi_url": body.openapi_url,
        "openapi_sha256": body.openapi_sha256,
        "image_digest": body.image_digest,
        "cosign_bundle": body.cosign_bundle,
        "evaluation_profile": body.evaluation_profile,
    }


def _assert_submitted_application_immutable(
    row: ProviderApplication,
    body: ProviderApplicationUpsertRequest,
) -> None:
    existing = {
        "requested_provider_id": row.requested_provider_id,
        "provider_kind": row.provider_kind,
        "openapi_url": row.openapi_url,
        "openapi_sha256": row.openapi_sha256,
        "image_digest": row.image_digest,
        "cosign_bundle": dict(row.cosign_bundle),
        "evaluation_profile": dict(row.evaluation_profile),
    }
    incoming = _material_application_values(body)
    changed = sorted(key for key, value in incoming.items() if existing[key] != value)
    if changed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"submitted application fields are immutable: {', '.join(changed)}",
        )


async def _load_provider_evaluation_row(
    session: AsyncSession,
    *,
    application_row_id: uuid.UUID,
    evaluation_id: str,
    tenant_id: uuid.UUID | None,
) -> ProviderApplicationEvaluationRequest | None:
    return (
        await session.execute(
            select(ProviderApplicationEvaluationRequest).where(
                ProviderApplicationEvaluationRequest.application_row_id == application_row_id,
                ProviderApplicationEvaluationRequest.evaluation_id == evaluation_id,
                (
                    ProviderApplicationEvaluationRequest.tenant_id.is_(None)
                    if tenant_id is None
                    else ProviderApplicationEvaluationRequest.tenant_id == tenant_id
                ),
            )
        )
    ).scalar_one_or_none()


async def _provider_evaluation_response(
    row: ProviderApplicationEvaluationRequest,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderEvaluationResponse:
    return ProviderEvaluationResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        application_id=row.application_id,
        evaluation_id=row.evaluation_id,
        requested_provider_id=row.requested_provider_id,
        benchmark_suite=row.benchmark_suite,
        sample_count=row.sample_count,
        timeout_seconds=row.timeout_seconds,
        status=cast(Any, row.status),
        dataset_refs=list(row.dataset_refs),
        report_ref=row.report_ref,
        metadata=dict(row.evaluation_metadata),
        scope_source=_scope_source(row.tenant_id, requested_tenant_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _material_evaluation_values(body: ProviderEvaluationUpsertRequest) -> dict[str, Any]:
    return {
        "benchmark_suite": body.benchmark_suite,
        "sample_count": body.sample_count,
        "timeout_seconds": body.timeout_seconds,
        "status": body.status,
        "dataset_refs": body.dataset_refs,
        "report_ref": body.report_ref,
        "metadata": body.metadata,
    }


def _assert_locked_evaluation_unchanged(
    row: ProviderApplicationEvaluationRequest,
    body: ProviderEvaluationUpsertRequest,
) -> None:
    if row.status == "requested":
        return
    existing = {
        "benchmark_suite": row.benchmark_suite,
        "sample_count": row.sample_count,
        "timeout_seconds": row.timeout_seconds,
        "status": row.status,
        "dataset_refs": list(row.dataset_refs),
        "report_ref": row.report_ref,
        "metadata": dict(row.evaluation_metadata),
    }
    incoming = _material_evaluation_values(body)
    changed = sorted(key for key, value in incoming.items() if existing[key] != value)
    if changed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{row.status} evaluation request fields are immutable: {', '.join(changed)}",
        )


@router.post(
    "/revenue-share/hooks",
    response_model=RevenueShareHookResponse,
    tags=["revenue-share"],
)
async def create_revenue_share_hook(
    body: RevenueShareHookCreateRequest,
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> RevenueShareHookResponse:
    _require_write_auth(x_internal_service_auth)
    existing = await _load_revenue_hook_by_source_event(
        session,
        source_service=body.source_service,
        source_event_id=body.source_event_id,
    )
    if existing is not None:
        return await _revenue_hook_response(
            existing,
            requested_tenant_id=existing.tenant_id,
        )
    await _validate_revenue_share_hook_references(session, body)
    row = RevenueShareHook(
        tenant_id=body.tenant_id,
        provider_id=body.provider_id,
        k_algo=body.k_algo,
        policy_id=body.policy_id,
        source_service=body.source_service,
        source_event_id=body.source_event_id,
        billing_saga_id=body.billing_saga_id,
        billing_ledger_id=body.billing_ledger_id,
        period_month=body.period_month,
        gross_amount_ref=body.gross_amount_ref,
        currency=body.currency,
        status=body.status,
        hook_metadata=body.metadata,
        created_at=datetime.now(UTC),
    )
    try:
        async with session.begin_nested():
            session.add(row)
            await session.flush()
    except IntegrityError:
        existing = await _load_revenue_hook_by_source_event(
            session,
            source_service=body.source_service,
            source_event_id=body.source_event_id,
        )
        if existing is not None:
            return await _revenue_hook_response(existing, requested_tenant_id=existing.tenant_id)
        raise
    return await _revenue_hook_response(row, requested_tenant_id=body.tenant_id)


@router.get(
    "/revenue-share/hooks/{hook_id}",
    response_model=RevenueShareHookResponse,
    tags=["revenue-share"],
)
async def get_revenue_share_hook(
    hook_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> RevenueShareHookResponse:
    row = (
        await session.execute(select(RevenueShareHook).where(RevenueShareHook.id == hook_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="hook not found")
    return await _revenue_hook_response(row, requested_tenant_id=row.tenant_id)


@router.get(
    "/revenue-share/hooks",
    response_model=list[RevenueShareHookResponse],
    tags=["revenue-share"],
)
async def list_revenue_share_hooks(
    tenant_id: uuid.UUID | None = Query(default=None),
    provider_id: Annotated[str | None, Query(pattern=_PATH_ID_PATTERN)] = None,
    k_algo: Annotated[str | None, Query(pattern=_PATH_ID_PATTERN)] = None,
    period_month: Annotated[str | None, Query(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")] = None,
    session: AsyncSession = Depends(get_session),
) -> list[RevenueShareHookResponse]:
    conditions: list[ColumnElement[bool]] = []
    if tenant_id is None:
        conditions.append(RevenueShareHook.tenant_id.is_(None))
    else:
        conditions.append(RevenueShareHook.tenant_id == tenant_id)
    if provider_id is not None:
        conditions.append(RevenueShareHook.provider_id == provider_id)
    if k_algo is not None:
        conditions.append(RevenueShareHook.k_algo == k_algo)
    if period_month is not None:
        conditions.append(RevenueShareHook.period_month == period_month)
    rows = (
        await session.execute(
            select(RevenueShareHook).where(*conditions).order_by(RevenueShareHook.created_at.desc())
        )
    ).scalars()
    return [await _revenue_hook_response(row, requested_tenant_id=tenant_id) for row in rows]


@router.put(
    "/provider-applications/{application_id}",
    response_model=ProviderApplicationResponse,
    tags=["provider-applications"],
)
async def upsert_provider_application(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    body: ProviderApplicationUpsertRequest,
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> ProviderApplicationResponse:
    _require_write_auth(x_internal_service_auth)
    _assert_path_id(body.application_id, application_id, "application_id")
    row = await _load_provider_application_row(
        session,
        application_id=application_id,
        tenant_id=body.tenant_id,
        allow_global_fallback=False,
    )
    provider_conflict = await _load_provider_application_by_requested_provider(
        session,
        requested_provider_id=body.requested_provider_id,
        tenant_id=body.tenant_id,
    )
    if provider_conflict is not None and (row is None or provider_conflict.id != row.id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="requested_provider_id already has an application",
        )
    now = datetime.now(UTC)
    submitted_at = body.submitted_at
    if body.status == "submitted" and submitted_at is None:
        submitted_at = now
    if row is None:
        row = ProviderApplication(
            tenant_id=body.tenant_id,
            application_id=application_id,
            requested_provider_id=body.requested_provider_id,
            provider_kind=body.provider_kind,
            display_name=body.display_name,
            organization_name=body.organization_name,
            contact_email=body.contact_email,
            homepage_url=body.homepage_url,
            openapi_url=body.openapi_url,
            openapi_sha256=body.openapi_sha256,
            image_digest=body.image_digest,
            cosign_bundle=body.cosign_bundle,
            evaluation_profile=body.evaluation_profile,
            status=body.status,
            submitted_at=submitted_at,
            application_metadata=body.metadata,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        if body.tenant_id != row.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="tenant_id is immutable",
            )
        if row.status == "submitted":
            if body.status == "draft":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="submitted application cannot return to draft",
                )
            _assert_submitted_application_immutable(row, body)
            submitted_at = row.submitted_at or submitted_at or now
        row.requested_provider_id = body.requested_provider_id
        row.provider_kind = body.provider_kind
        row.display_name = body.display_name
        row.organization_name = body.organization_name
        row.contact_email = body.contact_email
        row.homepage_url = body.homepage_url
        row.openapi_url = body.openapi_url
        row.openapi_sha256 = body.openapi_sha256
        row.image_digest = body.image_digest
        row.cosign_bundle = body.cosign_bundle
        row.evaluation_profile = body.evaluation_profile
        row.status = body.status
        row.submitted_at = submitted_at
        row.application_metadata = body.metadata
        row.updated_at = now
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="provider application identity already exists",
        ) from exc
    return await _provider_application_response(row, requested_tenant_id=body.tenant_id)


@router.get(
    "/provider-applications/{application_id}",
    response_model=ProviderApplicationResponse,
    tags=["provider-applications"],
)
async def get_provider_application(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> ProviderApplicationResponse:
    row = await _load_provider_application_row(
        session,
        application_id=application_id,
        tenant_id=tenant_id,
        allow_global_fallback=tenant_id is not None,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider application not found",
        )
    return await _provider_application_response(row, requested_tenant_id=tenant_id)


@router.get(
    "/provider-applications",
    response_model=list[ProviderApplicationResponse],
    tags=["provider-applications"],
)
async def list_provider_applications(
    tenant_id: uuid.UUID | None = Query(default=None),
    requested_provider_id: Annotated[str | None, Query(pattern=_PATH_ID_PATTERN)] = None,
    status_filter: ProviderApplicationStatus | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
) -> list[ProviderApplicationResponse]:
    conditions: list[ColumnElement[bool]] = [ProviderApplication.tenant_id.is_(None)]
    if requested_provider_id is not None:
        conditions.append(ProviderApplication.requested_provider_id == requested_provider_id)
    if status_filter is not None:
        conditions.append(ProviderApplication.status == status_filter)
    global_rows = (await session.execute(select(ProviderApplication).where(*conditions))).scalars()
    rows_by_application = {row.application_id: row for row in global_rows}
    if tenant_id is not None:
        tenant_conditions: list[ColumnElement[bool]] = [ProviderApplication.tenant_id == tenant_id]
        if requested_provider_id is not None:
            tenant_conditions.append(
                ProviderApplication.requested_provider_id == requested_provider_id
            )
        if status_filter is not None:
            tenant_conditions.append(ProviderApplication.status == status_filter)
        tenant_rows = (
            await session.execute(select(ProviderApplication).where(*tenant_conditions))
        ).scalars()
        for row in tenant_rows:
            rows_by_application[row.application_id] = row
    rows = sorted(rows_by_application.values(), key=lambda item: item.application_id)
    return [
        await _provider_application_response(row, requested_tenant_id=tenant_id) for row in rows
    ]


@router.post(
    "/provider-applications/{application_id}/submit",
    response_model=ProviderApplicationResponse,
    tags=["provider-applications"],
)
async def submit_provider_application(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> ProviderApplicationResponse:
    _require_write_auth(x_internal_service_auth)
    row = await _load_provider_application_row(
        session,
        application_id=application_id,
        tenant_id=tenant_id,
        allow_global_fallback=False,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider application not found",
        )
    if row.status != "submitted":
        now = datetime.now(UTC)
        row.status = "submitted"
        row.submitted_at = row.submitted_at or now
        row.updated_at = now
        await session.flush()
    return await _provider_application_response(row, requested_tenant_id=tenant_id)


@router.put(
    "/provider-applications/{application_id}/evaluation-requests/{evaluation_id}",
    response_model=ProviderEvaluationResponse,
    tags=["provider-applications"],
)
async def upsert_provider_application_evaluation(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    evaluation_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    body: ProviderEvaluationUpsertRequest,
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> ProviderEvaluationResponse:
    _require_write_auth(x_internal_service_auth)
    _assert_path_id(body.application_id, application_id, "application_id")
    _assert_path_id(body.evaluation_id, evaluation_id, "evaluation_id")
    application = await _load_provider_application_row(
        session,
        application_id=application_id,
        tenant_id=body.tenant_id,
        allow_global_fallback=body.tenant_id is not None,
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider application not found",
        )
    if application.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="provider application must be submitted before evaluation",
        )
    row = await _load_provider_evaluation_row(
        session,
        application_row_id=application.id,
        evaluation_id=evaluation_id,
        tenant_id=body.tenant_id,
    )
    now = datetime.now(UTC)
    if row is None:
        row = ProviderApplicationEvaluationRequest(
            tenant_id=body.tenant_id,
            application_row_id=application.id,
            application_id=application.application_id,
            evaluation_id=evaluation_id,
            requested_provider_id=application.requested_provider_id,
            benchmark_suite=body.benchmark_suite,
            sample_count=body.sample_count,
            timeout_seconds=body.timeout_seconds,
            status=body.status,
            dataset_refs=body.dataset_refs,
            report_ref=body.report_ref,
            evaluation_metadata=body.metadata,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        _assert_locked_evaluation_unchanged(row, body)
        row.benchmark_suite = body.benchmark_suite
        row.sample_count = body.sample_count
        row.timeout_seconds = body.timeout_seconds
        row.status = body.status
        row.dataset_refs = body.dataset_refs
        row.report_ref = body.report_ref
        row.evaluation_metadata = body.metadata
        row.updated_at = now
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="provider evaluation identity already exists",
        ) from exc
    return await _provider_evaluation_response(row, requested_tenant_id=body.tenant_id)


@router.get(
    "/provider-applications/{application_id}/evaluation-requests/{evaluation_id}",
    response_model=ProviderEvaluationResponse,
    tags=["provider-applications"],
)
async def get_provider_application_evaluation(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    evaluation_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> ProviderEvaluationResponse:
    application = await _load_provider_application_row(
        session,
        application_id=application_id,
        tenant_id=tenant_id,
        allow_global_fallback=tenant_id is not None,
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider application not found",
        )
    row = await _load_provider_evaluation_row(
        session,
        application_row_id=application.id,
        evaluation_id=evaluation_id,
        tenant_id=tenant_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider evaluation request not found",
        )
    return await _provider_evaluation_response(row, requested_tenant_id=tenant_id)


@router.get(
    "/provider-applications/{application_id}/evaluation-requests",
    response_model=list[ProviderEvaluationResponse],
    tags=["provider-applications"],
)
async def list_provider_application_evaluations(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    status_filter: ProviderEvaluationStatus | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
) -> list[ProviderEvaluationResponse]:
    application = await _load_provider_application_row(
        session,
        application_id=application_id,
        tenant_id=tenant_id,
        allow_global_fallback=tenant_id is not None,
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider application not found",
        )
    conditions: list[ColumnElement[bool]] = [
        ProviderApplicationEvaluationRequest.application_row_id == application.id,
        (
            ProviderApplicationEvaluationRequest.tenant_id.is_(None)
            if tenant_id is None
            else ProviderApplicationEvaluationRequest.tenant_id == tenant_id
        ),
    ]
    if status_filter is not None:
        conditions.append(ProviderApplicationEvaluationRequest.status == status_filter)
    rows = (
        await session.execute(
            select(ProviderApplicationEvaluationRequest)
            .where(*conditions)
            .order_by(ProviderApplicationEvaluationRequest.evaluation_id)
        )
    ).scalars()
    return [await _provider_evaluation_response(row, requested_tenant_id=tenant_id) for row in rows]


async def _resolve_shadow_evaluation(
    session: AsyncSession,
    *,
    application_id: str,
    evaluation_id: str,
    tenant_id: uuid.UUID | None,
) -> tuple[ProviderApplication, ProviderApplicationEvaluationRequest]:
    application = await _load_provider_application_row(
        session,
        application_id=application_id,
        tenant_id=tenant_id,
        allow_global_fallback=tenant_id is not None,
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider application not found",
        )
    if application.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="provider application must be submitted before shadow validation",
        )
    evaluation = await _load_provider_evaluation_row(
        session,
        application_row_id=application.id,
        evaluation_id=evaluation_id,
        tenant_id=tenant_id,
    )
    if evaluation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider evaluation request not found",
        )
    if evaluation.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="cancelled provider evaluation cannot be shadow validated",
        )
    return application, evaluation


async def _load_shadow_run_row(
    session: AsyncSession,
    *,
    evaluation_row_id: uuid.UUID,
    run_id: str,
    tenant_id: uuid.UUID | None,
) -> ProviderShadowValidationRun | None:
    return (
        await session.execute(
            select(ProviderShadowValidationRun).where(
                ProviderShadowValidationRun.evaluation_row_id == evaluation_row_id,
                ProviderShadowValidationRun.run_id == run_id,
                (
                    ProviderShadowValidationRun.tenant_id.is_(None)
                    if tenant_id is None
                    else ProviderShadowValidationRun.tenant_id == tenant_id
                ),
            )
        )
    ).scalar_one_or_none()


async def _lock_shadow_run_row(
    session: AsyncSession,
    row: ProviderShadowValidationRun,
) -> ProviderShadowValidationRun:
    locked = (
        await session.execute(
            select(ProviderShadowValidationRun)
            .where(ProviderShadowValidationRun.id == row.id)
            .with_for_update()
        )
    ).scalar_one()
    return locked


async def _load_shadow_sample_row(
    session: AsyncSession,
    *,
    run_row_id: uuid.UUID,
    sample_id: str,
    tenant_id: uuid.UUID | None,
) -> ProviderShadowValidationSample | None:
    return (
        await session.execute(
            select(ProviderShadowValidationSample).where(
                ProviderShadowValidationSample.run_row_id == run_row_id,
                ProviderShadowValidationSample.sample_id == sample_id,
                (
                    ProviderShadowValidationSample.tenant_id.is_(None)
                    if tenant_id is None
                    else ProviderShadowValidationSample.tenant_id == tenant_id
                ),
            )
        )
    ).scalar_one_or_none()


def _sample_passed(row: ProviderShadowValidationSample) -> bool:
    return (
        200 <= row.provider_status_code <= 299
        and not row.timed_out
        and row.deviation_ratio <= _SHADOW_MAX_AVERAGE_DEVIATION
    )


def _shadow_thresholds() -> dict[str, object]:
    return {
        "min_observed_days": _SHADOW_MIN_OBSERVED_DAYS,
        "min_sample_count": _SHADOW_MIN_SAMPLE_COUNT,
        "required_coverage_classes": list(_SHADOW_REQUIRED_COVERAGE_CLASSES),
        "min_samples_per_coverage_class": _SHADOW_MIN_SAMPLES_PER_COVERAGE_CLASS,
        "min_success_rate": f"{_SHADOW_MIN_SUCCESS_RATE:.6f}",
        "max_average_deviation_ratio": f"{_SHADOW_MAX_AVERAGE_DEVIATION:.6f}",
        "max_p95_latency_ratio": f"{_SHADOW_MAX_P95_LATENCY_RATIO:.6f}",
    }


def _nearest_rank_p95(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def _decimal_ratio(numerator: int, denominator: int) -> Decimal:
    if denominator <= 0:
        return Decimal("0.000000")
    return (Decimal(numerator) / Decimal(denominator)).quantize(_RATIO_QUANT)


def _shadow_summary_from_samples(
    run: ProviderShadowValidationRun,
    samples: list[ProviderShadowValidationSample],
) -> ProviderShadowRunSummary:
    sample_count = len(samples)
    coverage_class_counts: dict[ProviderShadowCoverageClass, int] = dict.fromkeys(
        _SHADOW_REQUIRED_COVERAGE_CLASSES, 0
    )
    for sample in samples:
        coverage_class = cast(ProviderShadowCoverageClass, sample.coverage_class)
        coverage_class_counts[coverage_class] = coverage_class_counts.get(coverage_class, 0) + 1

    if samples:
        observed_dates = [sample.observed_at for sample in samples]
        observed_day_span = (max(observed_dates) - min(observed_dates)).days
        success_count = sum(1 for sample in samples if _sample_passed(sample))
        average_deviation = (
            sum((sample.deviation_ratio for sample in samples), Decimal("0.000000"))
            / Decimal(sample_count)
        ).quantize(_RATIO_QUANT)
        provider_p95 = _nearest_rank_p95([sample.provider_latency_ms for sample in samples])
        baseline_p95 = _nearest_rank_p95([sample.baseline_latency_ms for sample in samples])
        p95_ratio = (
            (Decimal(provider_p95) / Decimal(baseline_p95)).quantize(_RATIO_QUANT)
            if baseline_p95 > 0
            else Decimal("999999.999999")
        )
    else:
        observed_day_span = 0
        success_count = 0
        average_deviation = Decimal("0.000000")
        provider_p95 = 0
        baseline_p95 = 0
        p95_ratio = Decimal("999999.999999")

    success_rate = _decimal_ratio(success_count, sample_count)
    coverage_classes = [
        coverage_class
        for coverage_class in _SHADOW_REQUIRED_COVERAGE_CLASSES
        if coverage_class_counts.get(coverage_class, 0) >= _SHADOW_MIN_SAMPLES_PER_COVERAGE_CLASS
    ]
    failed_reasons: list[str] = []
    if run.evaluation_sample_count != _SHADOW_MIN_SAMPLE_COUNT:
        failed_reasons.append("evaluation_sample_count_below_required")
    if sample_count != run.evaluation_sample_count or sample_count != _SHADOW_MIN_SAMPLE_COUNT:
        failed_reasons.append("sample_count_mismatch")
    if observed_day_span < _SHADOW_MIN_OBSERVED_DAYS:
        failed_reasons.append("observed_day_span_below_threshold")
    missing_coverage = [
        coverage_class
        for coverage_class in _SHADOW_REQUIRED_COVERAGE_CLASSES
        if coverage_class_counts.get(coverage_class, 0) < _SHADOW_MIN_SAMPLES_PER_COVERAGE_CLASS
    ]
    if missing_coverage:
        failed_reasons.append("coverage_class_missing")
    if success_rate < _SHADOW_MIN_SUCCESS_RATE:
        failed_reasons.append("success_rate_below_threshold")
    if average_deviation > _SHADOW_MAX_AVERAGE_DEVIATION:
        failed_reasons.append("average_deviation_above_threshold")
    if baseline_p95 <= 0 or p95_ratio > _SHADOW_MAX_P95_LATENCY_RATIO:
        failed_reasons.append("p95_latency_ratio_above_threshold")

    return ProviderShadowRunSummary(
        sample_count=sample_count,
        evaluation_sample_count=run.evaluation_sample_count,
        observed_day_span=observed_day_span,
        coverage_classes=coverage_classes,
        coverage_class_counts=coverage_class_counts,
        success_count=success_count,
        success_rate=success_rate,
        average_deviation_ratio=average_deviation,
        provider_p95_latency_ms=provider_p95,
        baseline_p95_latency_ms=baseline_p95,
        p95_latency_ratio=p95_ratio,
        thresholds=_shadow_thresholds(),
        failed_reasons=failed_reasons,
    )


async def _shadow_run_response(
    row: ProviderShadowValidationRun,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderShadowRunResponse:
    summary: ProviderShadowRunSummary | dict[str, Any]
    if row.summary:
        summary = ProviderShadowRunSummary.model_validate(row.summary)
    else:
        summary = {}
    return ProviderShadowRunResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        application_id=row.application_id,
        evaluation_id=row.evaluation_id,
        run_id=row.run_id,
        requested_provider_id=row.requested_provider_id,
        benchmark_suite=row.benchmark_suite,
        evaluation_sample_count=row.evaluation_sample_count,
        baseline_provider_id=row.baseline_provider_id,
        status=cast(Any, row.status),
        started_at=row.started_at,
        ended_at=row.ended_at,
        summary=summary,
        evidence_refs=list(row.evidence_refs),
        metadata=dict(row.run_metadata),
        scope_source=_scope_source(row.tenant_id, requested_tenant_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _shadow_sample_response(
    run: ProviderShadowValidationRun,
    row: ProviderShadowValidationSample,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderShadowSampleResponse:
    return ProviderShadowSampleResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        run_id=run.run_id,
        sample_id=row.sample_id,
        coverage_class=cast(Any, row.coverage_class),
        dataset_ref=row.dataset_ref,
        case_ref=row.case_ref,
        observed_at=row.observed_at,
        provider_status_code=row.provider_status_code,
        provider_latency_ms=row.provider_latency_ms,
        baseline_latency_ms=row.baseline_latency_ms,
        deviation_ratio=row.deviation_ratio,
        timed_out=row.timed_out,
        passed=_sample_passed(row),
        metadata=dict(row.sample_metadata),
        scope_source=_scope_source(row.tenant_id, requested_tenant_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _resolve_shadow_run_for_rollout(
    session: AsyncSession,
    *,
    application_id: str,
    evaluation_id: str,
    run_id: str,
    tenant_id: uuid.UUID | None,
) -> tuple[
    ProviderApplication,
    ProviderApplicationEvaluationRequest,
    ProviderShadowValidationRun,
]:
    application, evaluation = await _resolve_shadow_evaluation(
        session,
        application_id=application_id,
        evaluation_id=evaluation_id,
        tenant_id=tenant_id,
    )
    run = await _load_shadow_run_row(
        session,
        evaluation_row_id=evaluation.id,
        run_id=run_id,
        tenant_id=tenant_id,
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider shadow validation run not found",
        )
    return application, evaluation, run


async def _load_rollout_row(
    session: AsyncSession,
    *,
    shadow_run_row_id: uuid.UUID,
    rollout_id: str,
    tenant_id: uuid.UUID | None,
) -> ProviderGradientRollout | None:
    return (
        await session.execute(
            select(ProviderGradientRollout).where(
                ProviderGradientRollout.shadow_run_row_id == shadow_run_row_id,
                ProviderGradientRollout.rollout_id == rollout_id,
                (
                    ProviderGradientRollout.tenant_id.is_(None)
                    if tenant_id is None
                    else ProviderGradientRollout.tenant_id == tenant_id
                ),
            )
        )
    ).scalar_one_or_none()


async def _lock_rollout_row(
    session: AsyncSession,
    row: ProviderGradientRollout,
) -> ProviderGradientRollout:
    return (
        await session.execute(
            select(ProviderGradientRollout)
            .where(ProviderGradientRollout.id == row.id)
            .with_for_update()
        )
    ).scalar_one()


def _next_rollout_stage(stage: int) -> ProviderRolloutStage | None:
    try:
        index = _ROLLOUT_STAGES.index(cast(ProviderRolloutStage, stage))
    except ValueError:
        return None
    if index + 1 >= len(_ROLLOUT_STAGES):
        return None
    return _ROLLOUT_STAGES[index + 1]


def _stage_history_entry(
    *,
    stage_percent: int,
    changed_at: datetime,
    from_status: str,
    to_status: str,
    reason_ref: str,
    action: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "action": action,
        "stage_percent": stage_percent,
        "changed_at": changed_at.isoformat(),
        "from_status": from_status,
        "to_status": to_status,
        "reason_ref": reason_ref,
    }
    if metadata:
        entry["metadata"] = metadata
    return entry


def _append_stage_history(
    row: ProviderGradientRollout,
    entry: dict[str, Any],
) -> None:
    row.stage_history = [*list(row.stage_history), entry]


def _assert_rollout_body_matches_path(
    body: ProviderRolloutUpsertRequest,
    *,
    application_id: str,
    evaluation_id: str,
    run_id: str,
    rollout_id: str,
) -> None:
    _assert_path_id(body.application_id, application_id, "application_id")
    _assert_path_id(body.evaluation_id, evaluation_id, "evaluation_id")
    _assert_path_id(body.run_id, run_id, "run_id")
    _assert_path_id(body.rollout_id, rollout_id, "rollout_id")


async def _rollout_response(
    row: ProviderGradientRollout,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderRolloutResponse:
    return ProviderRolloutResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        application_id=row.application_id,
        evaluation_id=row.evaluation_id,
        run_id=row.run_id,
        rollout_id=row.rollout_id,
        requested_provider_id=row.requested_provider_id,
        baseline_provider_id=row.baseline_provider_id,
        benchmark_suite=row.benchmark_suite,
        status=cast(Any, row.status),
        current_stage_percent=cast(Any, row.current_stage_percent),
        stage_history=list(row.stage_history),
        shadow_summary_snapshot=dict(row.shadow_summary_snapshot),
        started_at=row.started_at,
        completed_at=row.completed_at,
        paused_at=row.paused_at,
        cancelled_at=row.cancelled_at,
        evidence_refs=list(row.evidence_refs),
        metadata=dict(row.rollout_metadata),
        scope_source=_scope_source(row.tenant_id, requested_tenant_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _route_share_conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _require_aware_datetime(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must be timezone-aware",
        )
    return value


def _parse_route_share_history_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise _route_share_conflict("rollout stage history changed_at must be a string")
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise _route_share_conflict("rollout stage history changed_at is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _route_share_conflict("rollout stage history changed_at must be timezone-aware")
    return parsed


def _coerce_route_share_status(value: Any, *, field_name: str) -> ProviderRolloutStatus:
    allowed: set[str] = {"draft", "active", "paused", "completed", "cancelled"}
    if not isinstance(value, str) or value not in allowed:
        raise _route_share_conflict(f"rollout {field_name} is invalid")
    return cast(ProviderRolloutStatus, value)


def _coerce_route_share_stage(value: Any, *, field_name: str) -> ProviderRolloutStage:
    if not isinstance(value, int) or value not in _ROLLOUT_STAGES:
        raise _route_share_conflict(f"rollout {field_name} is invalid")
    return value


def _coerce_route_share_action(value: Any) -> ProviderRouteShareAction:
    allowed: set[str] = {"created", "advance", "pause", "cancel"}
    if not isinstance(value, str) or value not in allowed:
        raise _route_share_conflict("rollout stage history action is invalid")
    return cast(ProviderRouteShareAction, value)


def _route_share_scope_source(
    row: ProviderGradientRollout,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderRouteShareScopeSource:
    source = _scope_source(row.tenant_id, requested_tenant_id)
    if source == "global_fallback":
        raise _route_share_conflict("route-share dashboard cannot use global fallback scope")
    return source


def _route_share_current_rollout(
    row: ProviderGradientRollout,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderRouteShareCurrentRollout:
    rollout_status = _coerce_route_share_status(row.status, field_name="status")
    stage = _coerce_route_share_stage(row.current_stage_percent, field_name="current_stage_percent")
    return ProviderRouteShareCurrentRollout(
        application_id=row.application_id,
        evaluation_id=row.evaluation_id,
        run_id=row.run_id,
        rollout_id=row.rollout_id,
        status=rollout_status,
        current_stage_percent=stage,
        started_at=row.started_at,
        completed_at=row.completed_at,
        paused_at=row.paused_at,
        cancelled_at=row.cancelled_at,
        updated_at=row.updated_at,
        scope_source=_route_share_scope_source(row, requested_tenant_id=requested_tenant_id),
    )


def _route_share_created_point(
    row: ProviderGradientRollout,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderRouteShareTimelinePoint:
    rollout_status = _coerce_route_share_status(row.status, field_name="status")
    to_status: ProviderRolloutStatus = "draft" if rollout_status != "draft" else rollout_status
    return ProviderRouteShareTimelinePoint(
        application_id=row.application_id,
        evaluation_id=row.evaluation_id,
        run_id=row.run_id,
        rollout_id=row.rollout_id,
        provider_id=row.requested_provider_id,
        baseline_provider_id=row.baseline_provider_id,
        benchmark_suite=row.benchmark_suite,
        action="created",
        stage_percent=0,
        from_status=None,
        to_status=to_status,
        observed_at=row.created_at,
        scope_source=_route_share_scope_source(row, requested_tenant_id=requested_tenant_id),
    )


def _route_share_history_point(
    row: ProviderGradientRollout,
    entry: Any,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderRouteShareTimelinePoint:
    if not isinstance(entry, dict):
        raise _route_share_conflict("rollout stage history entries must be objects")
    required = {"action", "stage_percent", "changed_at", "from_status", "to_status"}
    missing = sorted(required - set(entry))
    if missing:
        raise _route_share_conflict(f"rollout stage history entry is missing: {', '.join(missing)}")
    return ProviderRouteShareTimelinePoint(
        application_id=row.application_id,
        evaluation_id=row.evaluation_id,
        run_id=row.run_id,
        rollout_id=row.rollout_id,
        provider_id=row.requested_provider_id,
        baseline_provider_id=row.baseline_provider_id,
        benchmark_suite=row.benchmark_suite,
        action=_coerce_route_share_action(entry["action"]),
        stage_percent=_coerce_route_share_stage(entry["stage_percent"], field_name="stage_percent"),
        from_status=_coerce_route_share_status(entry["from_status"], field_name="from_status"),
        to_status=_coerce_route_share_status(entry["to_status"], field_name="to_status"),
        observed_at=_parse_route_share_history_time(entry["changed_at"]),
        scope_source=_route_share_scope_source(row, requested_tenant_id=requested_tenant_id),
    )


def _route_share_timeline_points(
    row: ProviderGradientRollout,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> list[ProviderRouteShareTimelinePoint]:
    points = [_route_share_created_point(row, requested_tenant_id=requested_tenant_id)]
    for entry in row.stage_history:
        points.append(
            _route_share_history_point(row, entry, requested_tenant_id=requested_tenant_id)
        )
    return points


def _route_share_status_counts(
    rows: list[ProviderGradientRollout],
) -> ProviderRouteShareStatusCounts:
    counts = dict.fromkeys(("draft", "active", "paused", "completed", "cancelled"), 0)
    for row in rows:
        counts[_coerce_route_share_status(row.status, field_name="status")] += 1
    return ProviderRouteShareStatusCounts(**counts)


def _route_share_timeline_sort_key(
    point: ProviderRouteShareTimelinePoint,
) -> tuple[datetime, str, str, str, str, str, int]:
    return (
        point.observed_at,
        point.application_id,
        point.evaluation_id,
        point.run_id,
        point.rollout_id,
        point.action,
        point.stage_percent,
    )


def _kpi_conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _coerce_kpi_run_status(value: Any) -> ProviderShadowRunStatus:
    allowed: set[str] = {"draft", "running", "passed", "failed", "cancelled"}
    if not isinstance(value, str) or value not in allowed:
        raise _kpi_conflict("shadow run status is invalid")
    return cast(ProviderShadowRunStatus, value)


def _coerce_kpi_coverage_class(value: Any) -> ProviderShadowCoverageClass:
    if not isinstance(value, str) or value not in _SHADOW_REQUIRED_COVERAGE_CLASSES:
        raise _kpi_conflict("shadow sample coverage_class is invalid")
    return value


def _kpi_scope_source(
    row_tenant_id: uuid.UUID | None,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderRouteShareScopeSource:
    source = _scope_source(row_tenant_id, requested_tenant_id)
    if source == "global_fallback":
        raise _kpi_conflict("provider KPI dashboard cannot use global fallback scope")
    return source


def _validate_kpi_sample(
    sample: ProviderShadowValidationSample,
    *,
    run_tenant_id: uuid.UUID | None,
) -> None:
    _coerce_kpi_coverage_class(sample.coverage_class)
    if sample.tenant_id != run_tenant_id:
        raise _kpi_conflict("shadow sample tenant scope does not match run tenant scope")
    if sample.observed_at.tzinfo is None or sample.observed_at.utcoffset() is None:
        raise _kpi_conflict("shadow sample observed_at must be timezone-aware")
    if not 100 <= sample.provider_status_code <= 599:
        raise _kpi_conflict("shadow sample provider_status_code is invalid")
    if sample.provider_latency_ms <= 0:
        raise _kpi_conflict("shadow sample provider_latency_ms is invalid")
    if sample.baseline_latency_ms <= 0:
        raise _kpi_conflict("shadow sample baseline_latency_ms is invalid")
    if sample.deviation_ratio < 0:
        raise _kpi_conflict("shadow sample deviation_ratio is invalid")


def _kpi_metrics(samples: list[ProviderShadowValidationSample]) -> ProviderKpiAggregateMetrics:
    sample_count = len(samples)
    success_count = sum(1 for sample in samples if _sample_passed(sample))
    failed_count = sample_count - success_count
    timeout_count = sum(1 for sample in samples if sample.timed_out)
    provider_error_count = sum(
        1 for sample in samples if not 200 <= sample.provider_status_code <= 299
    )
    average_deviation = (
        (
            sum((sample.deviation_ratio for sample in samples), Decimal("0.000000"))
            / Decimal(sample_count)
        ).quantize(_RATIO_QUANT)
        if samples
        else Decimal("0.000000")
    )
    provider_p95 = _nearest_rank_p95([sample.provider_latency_ms for sample in samples])
    baseline_p95 = _nearest_rank_p95([sample.baseline_latency_ms for sample in samples])
    p95_ratio = (
        (Decimal(provider_p95) / Decimal(baseline_p95)).quantize(_RATIO_QUANT)
        if baseline_p95 > 0
        else Decimal("0.000000")
    )
    return ProviderKpiAggregateMetrics(
        sample_count=sample_count,
        success_count=success_count,
        failed_count=failed_count,
        timeout_count=timeout_count,
        provider_error_count=provider_error_count,
        success_rate=_decimal_ratio(success_count, sample_count),
        average_deviation_ratio=average_deviation,
        provider_p95_latency_ms=provider_p95,
        baseline_p95_latency_ms=baseline_p95,
        p95_latency_ratio=p95_ratio,
    )


def _kpi_coverage_counts(
    samples: list[ProviderShadowValidationSample],
) -> dict[ProviderShadowCoverageClass, int]:
    counts: dict[ProviderShadowCoverageClass, int] = dict.fromkeys(
        _SHADOW_REQUIRED_COVERAGE_CLASSES, 0
    )
    for sample in samples:
        coverage_class = _coerce_kpi_coverage_class(sample.coverage_class)
        counts[coverage_class] += 1
    return counts


def _kpi_observed_day_span(samples: list[ProviderShadowValidationSample]) -> int:
    if not samples:
        return 0
    observed_dates = [sample.observed_at for sample in samples]
    return (max(observed_dates) - min(observed_dates)).days


def _kpi_threshold_violations(
    metrics: ProviderKpiAggregateMetrics,
    coverage_counts: dict[ProviderShadowCoverageClass, int],
    *,
    observed_day_span: int,
) -> list[str]:
    violations: list[str] = []
    if metrics.sample_count != _SHADOW_MIN_SAMPLE_COUNT:
        violations.append("sample_count_mismatch")
    if observed_day_span < _SHADOW_MIN_OBSERVED_DAYS:
        violations.append("observed_day_span_below_threshold")
    if any(
        coverage_counts.get(coverage_class, 0) < _SHADOW_MIN_SAMPLES_PER_COVERAGE_CLASS
        for coverage_class in _SHADOW_REQUIRED_COVERAGE_CLASSES
    ):
        violations.append("coverage_class_missing")
    if metrics.success_rate < _SHADOW_MIN_SUCCESS_RATE:
        violations.append("success_rate_below_threshold")
    if metrics.average_deviation_ratio > _SHADOW_MAX_AVERAGE_DEVIATION:
        violations.append("average_deviation_above_threshold")
    if (
        metrics.baseline_p95_latency_ms <= 0
        or metrics.p95_latency_ratio > _SHADOW_MAX_P95_LATENCY_RATIO
    ):
        violations.append("p95_latency_ratio_above_threshold")
    return violations


def _kpi_filter_samples_by_window(
    samples: list[ProviderShadowValidationSample],
    *,
    from_at: datetime | None,
    to_at: datetime | None,
) -> list[ProviderShadowValidationSample]:
    return [
        sample
        for sample in samples
        if (from_at is None or sample.observed_at >= from_at)
        and (to_at is None or sample.observed_at <= to_at)
    ]


def _kpi_run_metric(
    run: ProviderShadowValidationRun,
    samples: list[ProviderShadowValidationSample],
    *,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderKpiRunMetric:
    run_status = _coerce_kpi_run_status(run.status)
    coverage_counts = _kpi_coverage_counts(samples)
    coverage_classes = [
        coverage_class
        for coverage_class in _SHADOW_REQUIRED_COVERAGE_CLASSES
        if coverage_counts.get(coverage_class, 0) >= _SHADOW_MIN_SAMPLES_PER_COVERAGE_CLASS
    ]
    metrics = _kpi_metrics(samples)
    observed_from = min((sample.observed_at for sample in samples), default=None)
    observed_to = max((sample.observed_at for sample in samples), default=None)
    return ProviderKpiRunMetric(
        application_id=run.application_id,
        evaluation_id=run.evaluation_id,
        run_id=run.run_id,
        provider_id=run.requested_provider_id,
        baseline_provider_id=run.baseline_provider_id,
        benchmark_suite=run.benchmark_suite,
        status=run_status,
        started_at=run.started_at,
        ended_at=run.ended_at,
        updated_at=run.updated_at,
        observed_from=observed_from,
        observed_to=observed_to,
        coverage_classes=coverage_classes,
        coverage_class_counts=coverage_counts,
        threshold_violations=_kpi_threshold_violations(
            metrics,
            coverage_counts,
            observed_day_span=_kpi_observed_day_span(samples),
        ),
        metrics=metrics,
        scope_source=_kpi_scope_source(run.tenant_id, requested_tenant_id),
    )


def _kpi_bucket_start(observed_at: datetime) -> datetime:
    return observed_at.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def _kpi_timeline_points(
    run: ProviderShadowValidationRun,
    samples: list[ProviderShadowValidationSample],
    *,
    requested_tenant_id: uuid.UUID | None,
) -> list[ProviderKpiTimelinePoint]:
    buckets: dict[datetime, list[ProviderShadowValidationSample]] = {}
    for sample in samples:
        buckets.setdefault(_kpi_bucket_start(sample.observed_at), []).append(sample)
    return [
        ProviderKpiTimelinePoint(
            application_id=run.application_id,
            evaluation_id=run.evaluation_id,
            run_id=run.run_id,
            provider_id=run.requested_provider_id,
            benchmark_suite=run.benchmark_suite,
            bucket_start=bucket_start,
            metrics=_kpi_metrics(bucket_samples),
            scope_source=_kpi_scope_source(run.tenant_id, requested_tenant_id),
        )
        for bucket_start, bucket_samples in sorted(buckets.items(), key=lambda item: item[0])
    ]


def _kpi_run_status_counts(
    runs: list[ProviderShadowValidationRun],
) -> ProviderKpiRunStatusCounts:
    counts = dict.fromkeys(("draft", "running", "passed", "failed", "cancelled"), 0)
    for run in runs:
        counts[_coerce_kpi_run_status(run.status)] += 1
    return ProviderKpiRunStatusCounts(**counts)


def _kpi_rollout_summary(
    rows: list[ProviderGradientRollout],
    *,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderKpiRolloutSummary:
    current_rollouts = [
        _route_share_current_rollout(row, requested_tenant_id=requested_tenant_id) for row in rows
    ]
    highest_stage = max(
        (rollout.current_stage_percent for rollout in current_rollouts),
        default=0,
    )
    return ProviderKpiRolloutSummary(
        total_rollouts=len(rows),
        highest_current_stage_percent=cast(ProviderRolloutStage, highest_stage),
        status_counts=_route_share_status_counts(rows),
    )


def _material_shadow_run_values(body: ProviderShadowRunUpsertRequest) -> dict[str, Any]:
    return {
        "baseline_provider_id": body.baseline_provider_id,
        "started_at": body.started_at,
        "evidence_refs": body.evidence_refs,
        "metadata": body.metadata,
    }


def _assert_locked_shadow_run_unchanged(
    row: ProviderShadowValidationRun,
    body: ProviderShadowRunUpsertRequest,
) -> None:
    existing = {
        "baseline_provider_id": row.baseline_provider_id,
        "status": row.status,
        "started_at": row.started_at,
        "evidence_refs": list(row.evidence_refs),
        "metadata": dict(row.run_metadata),
    }
    incoming = _material_shadow_run_values(body)
    if body.status is not None and body.status != row.status:
        incoming["status"] = body.status
        existing["status"] = row.status
    changed = sorted(key for key, value in incoming.items() if existing[key] != value)
    if changed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{row.status} shadow run fields are immutable: {', '.join(changed)}",
        )


@router.put(
    "/provider-applications/{application_id}/evaluation-requests/{evaluation_id}"
    "/shadow-runs/{run_id}",
    response_model=ProviderShadowRunResponse,
    tags=["provider-shadow-validation"],
)
async def upsert_provider_shadow_run(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    evaluation_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    run_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    body: ProviderShadowRunUpsertRequest,
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> ProviderShadowRunResponse:
    _require_write_auth(x_internal_service_auth)
    _assert_path_id(body.application_id, application_id, "application_id")
    _assert_path_id(body.evaluation_id, evaluation_id, "evaluation_id")
    _assert_path_id(body.run_id, run_id, "run_id")
    application, evaluation = await _resolve_shadow_evaluation(
        session,
        application_id=application_id,
        evaluation_id=evaluation_id,
        tenant_id=body.tenant_id,
    )
    row = await _load_shadow_run_row(
        session,
        evaluation_row_id=evaluation.id,
        run_id=run_id,
        tenant_id=body.tenant_id,
    )
    now = datetime.now(UTC)
    requested_status = body.status or (row.status if row is not None else "draft")
    started_at = body.started_at
    if requested_status == "running" and started_at is None:
        started_at = now
    if row is None:
        row = ProviderShadowValidationRun(
            tenant_id=body.tenant_id,
            application_row_id=application.id,
            evaluation_row_id=evaluation.id,
            application_id=application.application_id,
            evaluation_id=evaluation.evaluation_id,
            run_id=run_id,
            requested_provider_id=evaluation.requested_provider_id,
            benchmark_suite=evaluation.benchmark_suite,
            evaluation_sample_count=evaluation.sample_count,
            baseline_provider_id=body.baseline_provider_id,
            status=requested_status,
            started_at=started_at,
            summary={},
            evidence_refs=body.evidence_refs,
            run_metadata=body.metadata,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row = await _lock_shadow_run_row(session, row)
        if body.tenant_id != row.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="tenant_id is immutable",
            )
        if row.status in {"passed", "failed", "cancelled"}:
            _assert_locked_shadow_run_unchanged(row, body)
        elif row.status == "running":
            if requested_status == "draft":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="running shadow run cannot return to draft",
                )
            if body.baseline_provider_id != row.baseline_provider_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="baseline_provider_id is immutable after running",
                )
        if row.status not in {"passed", "failed", "cancelled"}:
            row.baseline_provider_id = body.baseline_provider_id
            row.status = requested_status
            row.started_at = row.started_at or started_at
            row.evidence_refs = body.evidence_refs
            row.run_metadata = body.metadata
            row.updated_at = now
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="provider shadow run identity already exists",
        ) from exc
    return await _shadow_run_response(row, requested_tenant_id=body.tenant_id)


@router.get(
    "/provider-applications/{application_id}/evaluation-requests/{evaluation_id}"
    "/shadow-runs/{run_id}",
    response_model=ProviderShadowRunResponse,
    tags=["provider-shadow-validation"],
)
async def get_provider_shadow_run(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    evaluation_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    run_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> ProviderShadowRunResponse:
    _, evaluation = await _resolve_shadow_evaluation(
        session,
        application_id=application_id,
        evaluation_id=evaluation_id,
        tenant_id=tenant_id,
    )
    row = await _load_shadow_run_row(
        session,
        evaluation_row_id=evaluation.id,
        run_id=run_id,
        tenant_id=tenant_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider shadow validation run not found",
        )
    return await _shadow_run_response(row, requested_tenant_id=tenant_id)


@router.get(
    "/provider-applications/{application_id}/evaluation-requests/{evaluation_id}/shadow-runs",
    response_model=list[ProviderShadowRunResponse],
    tags=["provider-shadow-validation"],
)
async def list_provider_shadow_runs(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    evaluation_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    status_filter: ProviderShadowRunStatus | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
) -> list[ProviderShadowRunResponse]:
    _, evaluation = await _resolve_shadow_evaluation(
        session,
        application_id=application_id,
        evaluation_id=evaluation_id,
        tenant_id=tenant_id,
    )
    conditions: list[ColumnElement[bool]] = [
        ProviderShadowValidationRun.evaluation_row_id == evaluation.id,
        (
            ProviderShadowValidationRun.tenant_id.is_(None)
            if tenant_id is None
            else ProviderShadowValidationRun.tenant_id == tenant_id
        ),
    ]
    if status_filter is not None:
        conditions.append(ProviderShadowValidationRun.status == status_filter)
    rows = (
        await session.execute(
            select(ProviderShadowValidationRun)
            .where(*conditions)
            .order_by(ProviderShadowValidationRun.run_id)
        )
    ).scalars()
    return [await _shadow_run_response(row, requested_tenant_id=tenant_id) for row in rows]


@router.put(
    "/provider-applications/{application_id}/evaluation-requests/{evaluation_id}"
    "/shadow-runs/{run_id}/samples/{sample_id}",
    response_model=ProviderShadowSampleResponse,
    tags=["provider-shadow-validation"],
)
async def upsert_provider_shadow_sample(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    evaluation_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    run_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    sample_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    body: ProviderShadowSampleUpsertRequest,
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> ProviderShadowSampleResponse:
    _require_write_auth(x_internal_service_auth)
    _assert_path_id(body.sample_id, sample_id, "sample_id")
    _, evaluation = await _resolve_shadow_evaluation(
        session,
        application_id=application_id,
        evaluation_id=evaluation_id,
        tenant_id=body.tenant_id,
    )
    run = await _load_shadow_run_row(
        session,
        evaluation_row_id=evaluation.id,
        run_id=run_id,
        tenant_id=body.tenant_id,
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider shadow validation run not found",
        )
    run = await _lock_shadow_run_row(session, run)
    if run.status != "running":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="shadow samples can only be written while run is running",
        )
    if body.tenant_id != run.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="sample tenant_id must match shadow run tenant_id",
        )
    row = await _load_shadow_sample_row(
        session,
        run_row_id=run.id,
        sample_id=sample_id,
        tenant_id=body.tenant_id,
    )
    if row is None:
        existing_count = (
            await session.execute(
                select(ProviderShadowValidationSample.id).where(
                    ProviderShadowValidationSample.run_row_id == run.id,
                    (
                        ProviderShadowValidationSample.tenant_id.is_(None)
                        if body.tenant_id is None
                        else ProviderShadowValidationSample.tenant_id == body.tenant_id
                    ),
                )
            )
        ).scalars()
        if len(list(existing_count)) >= run.evaluation_sample_count:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="shadow sample count exceeds evaluation sample_count",
            )
        now = datetime.now(UTC)
        row = ProviderShadowValidationSample(
            tenant_id=body.tenant_id,
            run_row_id=run.id,
            sample_id=sample_id,
            coverage_class=body.coverage_class,
            dataset_ref=body.dataset_ref,
            case_ref=body.case_ref,
            observed_at=body.observed_at,
            provider_status_code=body.provider_status_code,
            provider_latency_ms=body.provider_latency_ms,
            baseline_latency_ms=body.baseline_latency_ms,
            deviation_ratio=body.deviation_ratio,
            timed_out=body.timed_out,
            sample_metadata=body.metadata,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        now = datetime.now(UTC)
        row.coverage_class = body.coverage_class
        row.dataset_ref = body.dataset_ref
        row.case_ref = body.case_ref
        row.observed_at = body.observed_at
        row.provider_status_code = body.provider_status_code
        row.provider_latency_ms = body.provider_latency_ms
        row.baseline_latency_ms = body.baseline_latency_ms
        row.deviation_ratio = body.deviation_ratio
        row.timed_out = body.timed_out
        row.sample_metadata = body.metadata
        row.updated_at = now
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="provider shadow sample identity already exists",
        ) from exc
    return await _shadow_sample_response(run, row, requested_tenant_id=body.tenant_id)


@router.get(
    "/provider-applications/{application_id}/evaluation-requests/{evaluation_id}"
    "/shadow-runs/{run_id}/samples/{sample_id}",
    response_model=ProviderShadowSampleResponse,
    tags=["provider-shadow-validation"],
)
async def get_provider_shadow_sample(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    evaluation_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    run_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    sample_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> ProviderShadowSampleResponse:
    _, evaluation = await _resolve_shadow_evaluation(
        session,
        application_id=application_id,
        evaluation_id=evaluation_id,
        tenant_id=tenant_id,
    )
    run = await _load_shadow_run_row(
        session,
        evaluation_row_id=evaluation.id,
        run_id=run_id,
        tenant_id=tenant_id,
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider shadow validation run not found",
        )
    row = await _load_shadow_sample_row(
        session,
        run_row_id=run.id,
        sample_id=sample_id,
        tenant_id=tenant_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider shadow validation sample not found",
        )
    return await _shadow_sample_response(run, row, requested_tenant_id=tenant_id)


@router.get(
    "/provider-applications/{application_id}/evaluation-requests/{evaluation_id}"
    "/shadow-runs/{run_id}/samples",
    response_model=list[ProviderShadowSampleResponse],
    tags=["provider-shadow-validation"],
)
async def list_provider_shadow_samples(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    evaluation_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    run_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    coverage_class: ProviderShadowCoverageClass | None = Query(default=None),
    passed: bool | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[ProviderShadowSampleResponse]:
    _, evaluation = await _resolve_shadow_evaluation(
        session,
        application_id=application_id,
        evaluation_id=evaluation_id,
        tenant_id=tenant_id,
    )
    run = await _load_shadow_run_row(
        session,
        evaluation_row_id=evaluation.id,
        run_id=run_id,
        tenant_id=tenant_id,
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider shadow validation run not found",
        )
    conditions: list[ColumnElement[bool]] = [
        ProviderShadowValidationSample.run_row_id == run.id,
        (
            ProviderShadowValidationSample.tenant_id.is_(None)
            if tenant_id is None
            else ProviderShadowValidationSample.tenant_id == tenant_id
        ),
    ]
    if coverage_class is not None:
        conditions.append(ProviderShadowValidationSample.coverage_class == coverage_class)
    rows = list(
        (
            await session.execute(
                select(ProviderShadowValidationSample)
                .where(*conditions)
                .order_by(ProviderShadowValidationSample.sample_id)
            )
        ).scalars()
    )
    if passed is not None:
        rows = [row for row in rows if _sample_passed(row) is passed]
    return [await _shadow_sample_response(run, row, requested_tenant_id=tenant_id) for row in rows]


@router.post(
    "/provider-applications/{application_id}/evaluation-requests/{evaluation_id}"
    "/shadow-runs/{run_id}/finalize",
    response_model=ProviderShadowRunResponse,
    tags=["provider-shadow-validation"],
)
async def finalize_provider_shadow_run(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    evaluation_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    run_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> ProviderShadowRunResponse:
    _require_write_auth(x_internal_service_auth)
    _, evaluation = await _resolve_shadow_evaluation(
        session,
        application_id=application_id,
        evaluation_id=evaluation_id,
        tenant_id=tenant_id,
    )
    run = await _load_shadow_run_row(
        session,
        evaluation_row_id=evaluation.id,
        run_id=run_id,
        tenant_id=tenant_id,
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider shadow validation run not found",
        )
    run = await _lock_shadow_run_row(session, run)
    if run.status in {"passed", "failed"}:
        return await _shadow_run_response(run, requested_tenant_id=tenant_id)
    if run.status != "running":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="only running shadow validation runs can be finalized",
        )
    samples = list(
        (
            await session.execute(
                select(ProviderShadowValidationSample)
                .where(ProviderShadowValidationSample.run_row_id == run.id)
                .order_by(ProviderShadowValidationSample.sample_id)
            )
        ).scalars()
    )
    summary = _shadow_summary_from_samples(run, samples)
    run.summary = summary.model_dump(mode="json")
    run.status = "passed" if not summary.failed_reasons else "failed"
    now = datetime.now(UTC)
    run.ended_at = run.ended_at or now
    run.updated_at = now
    await session.flush()
    return await _shadow_run_response(run, requested_tenant_id=tenant_id)


@router.put(
    "/provider-applications/{application_id}/evaluation-requests/{evaluation_id}"
    "/shadow-runs/{run_id}/rollouts/{rollout_id}",
    response_model=ProviderRolloutResponse,
    tags=["provider-gradient-rollout"],
)
async def upsert_provider_rollout(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    evaluation_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    run_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    rollout_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    body: ProviderRolloutUpsertRequest,
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> ProviderRolloutResponse:
    _require_write_auth(x_internal_service_auth)
    _assert_rollout_body_matches_path(
        body,
        application_id=application_id,
        evaluation_id=evaluation_id,
        run_id=run_id,
        rollout_id=rollout_id,
    )
    application, evaluation, run = await _resolve_shadow_run_for_rollout(
        session,
        application_id=application_id,
        evaluation_id=evaluation_id,
        run_id=run_id,
        tenant_id=body.tenant_id,
    )
    if run.status != "passed" or not run.summary:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="provider rollout requires a passed shadow validation run with summary",
        )
    shadow_summary = ProviderShadowRunSummary.model_validate(run.summary)
    if shadow_summary.failed_reasons:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="provider rollout requires a clean passed shadow summary",
        )
    row = await _load_rollout_row(
        session,
        shadow_run_row_id=run.id,
        rollout_id=rollout_id,
        tenant_id=body.tenant_id,
    )
    now = datetime.now(UTC)
    if row is None:
        row = ProviderGradientRollout(
            tenant_id=body.tenant_id,
            application_row_id=application.id,
            evaluation_row_id=evaluation.id,
            shadow_run_row_id=run.id,
            application_id=application.application_id,
            evaluation_id=evaluation.evaluation_id,
            run_id=run.run_id,
            rollout_id=rollout_id,
            requested_provider_id=run.requested_provider_id,
            baseline_provider_id=run.baseline_provider_id,
            benchmark_suite=run.benchmark_suite,
            status="draft",
            current_stage_percent=0,
            stage_history=[],
            shadow_summary_snapshot=shadow_summary.model_dump(mode="json"),
            evidence_refs=body.evidence_refs,
            rollout_metadata=body.metadata,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row = await _lock_rollout_row(session, row)
        if body.tenant_id != row.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="tenant_id is immutable",
            )
        if row.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{row.status} rollout fields are immutable",
            )
        row.evidence_refs = body.evidence_refs
        row.rollout_metadata = body.metadata
        row.updated_at = now
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="provider rollout identity already exists",
        ) from exc
    return await _rollout_response(row, requested_tenant_id=body.tenant_id)


@router.get(
    "/provider-applications/{application_id}/evaluation-requests/{evaluation_id}"
    "/shadow-runs/{run_id}/rollouts/{rollout_id}",
    response_model=ProviderRolloutResponse,
    tags=["provider-gradient-rollout"],
)
async def get_provider_rollout(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    evaluation_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    run_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    rollout_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> ProviderRolloutResponse:
    _, _, run = await _resolve_shadow_run_for_rollout(
        session,
        application_id=application_id,
        evaluation_id=evaluation_id,
        run_id=run_id,
        tenant_id=tenant_id,
    )
    row = await _load_rollout_row(
        session,
        shadow_run_row_id=run.id,
        rollout_id=rollout_id,
        tenant_id=tenant_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider gradient rollout not found",
        )
    return await _rollout_response(row, requested_tenant_id=tenant_id)


@router.get(
    "/provider-applications/{application_id}/evaluation-requests/{evaluation_id}"
    "/shadow-runs/{run_id}/rollouts",
    response_model=list[ProviderRolloutResponse],
    tags=["provider-gradient-rollout"],
)
async def list_provider_rollouts(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    evaluation_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    run_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    status_filter: ProviderRolloutStatus | None = Query(default=None, alias="status"),
    stage_percent: int | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[ProviderRolloutResponse]:
    if stage_percent is not None and stage_percent not in _ROLLOUT_STAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="stage_percent must be one of 0, 5, 50, or 100",
        )
    _, _, run = await _resolve_shadow_run_for_rollout(
        session,
        application_id=application_id,
        evaluation_id=evaluation_id,
        run_id=run_id,
        tenant_id=tenant_id,
    )
    conditions: list[ColumnElement[bool]] = [
        ProviderGradientRollout.shadow_run_row_id == run.id,
        (
            ProviderGradientRollout.tenant_id.is_(None)
            if tenant_id is None
            else ProviderGradientRollout.tenant_id == tenant_id
        ),
    ]
    if status_filter is not None:
        conditions.append(ProviderGradientRollout.status == status_filter)
    if stage_percent is not None:
        conditions.append(ProviderGradientRollout.current_stage_percent == stage_percent)
    rows = (
        await session.execute(
            select(ProviderGradientRollout)
            .where(*conditions)
            .order_by(ProviderGradientRollout.rollout_id)
        )
    ).scalars()
    return [await _rollout_response(row, requested_tenant_id=tenant_id) for row in rows]


@router.get(
    "/providers/{provider_id}/route-share-dashboard",
    response_model=ProviderRouteShareDashboardResponse,
    tags=["provider-route-share-dashboard"],
)
async def get_provider_route_share_dashboard(
    provider_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    status_filter: ProviderRolloutStatus | None = Query(default=None, alias="status"),
    stage_percent: int | None = Query(default=None, json_schema_extra={"enum": [0, 5, 50, 100]}),
    session: AsyncSession = Depends(get_session),
) -> ProviderRouteShareDashboardResponse:
    if from_at is not None:
        _require_aware_datetime(from_at, field_name="from")
    if to_at is not None:
        _require_aware_datetime(to_at, field_name="to")
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="from must be before or equal to to",
        )
    if stage_percent is not None and stage_percent not in _ROLLOUT_STAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="stage_percent must be one of 0, 5, 50, or 100",
        )
    conditions: list[ColumnElement[bool]] = [
        ProviderGradientRollout.requested_provider_id == provider_id,
        (
            ProviderGradientRollout.tenant_id.is_(None)
            if tenant_id is None
            else ProviderGradientRollout.tenant_id == tenant_id
        ),
    ]
    if status_filter is not None:
        conditions.append(ProviderGradientRollout.status == status_filter)
    if stage_percent is not None:
        conditions.append(ProviderGradientRollout.current_stage_percent == stage_percent)

    rows = list(
        (
            await session.execute(
                select(ProviderGradientRollout)
                .where(*conditions)
                .order_by(
                    ProviderGradientRollout.application_id,
                    ProviderGradientRollout.evaluation_id,
                    ProviderGradientRollout.run_id,
                    ProviderGradientRollout.rollout_id,
                )
            )
        ).scalars()
    )
    current_rollouts = [
        _route_share_current_rollout(row, requested_tenant_id=tenant_id) for row in rows
    ]
    status_counts = _route_share_status_counts(rows)
    highest_stage = max(
        (rollout.current_stage_percent for rollout in current_rollouts),
        default=0,
    )
    timeline = [
        point
        for row in rows
        for point in _route_share_timeline_points(row, requested_tenant_id=tenant_id)
        if (from_at is None or point.observed_at >= from_at)
        and (to_at is None or point.observed_at <= to_at)
    ]
    timeline.sort(key=_route_share_timeline_sort_key)
    return ProviderRouteShareDashboardResponse(
        provider_id=provider_id,
        tenant_id=tenant_id,
        from_at=from_at,
        to_at=to_at,
        status_counts=status_counts,
        total_rollouts=len(rows),
        highest_current_stage_percent=cast(ProviderRolloutStage, highest_stage),
        current_rollouts=current_rollouts,
        timeline=timeline,
    )


@router.get(
    "/providers/{provider_id}/kpi-dashboard",
    response_model=ProviderKpiDashboardResponse,
    tags=["provider-kpi-dashboard"],
)
async def get_provider_kpi_dashboard(
    provider_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    run_status: ProviderShadowRunStatus | None = Query(default=None),
    benchmark_suite: str | None = Query(
        default=None,
        pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$",
    ),
    session: AsyncSession = Depends(get_session),
) -> ProviderKpiDashboardResponse:
    if from_at is not None:
        _require_aware_datetime(from_at, field_name="from")
    if to_at is not None:
        _require_aware_datetime(to_at, field_name="to")
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="from must be before or equal to to",
        )

    run_conditions: list[ColumnElement[bool]] = [
        ProviderShadowValidationRun.requested_provider_id == provider_id,
        (
            ProviderShadowValidationRun.tenant_id.is_(None)
            if tenant_id is None
            else ProviderShadowValidationRun.tenant_id == tenant_id
        ),
    ]
    if run_status is not None:
        run_conditions.append(ProviderShadowValidationRun.status == run_status)
    if benchmark_suite is not None:
        run_conditions.append(ProviderShadowValidationRun.benchmark_suite == benchmark_suite)

    runs = list(
        (
            await session.execute(
                select(ProviderShadowValidationRun)
                .where(*run_conditions)
                .order_by(
                    ProviderShadowValidationRun.application_id,
                    ProviderShadowValidationRun.evaluation_id,
                    ProviderShadowValidationRun.run_id,
                )
            )
        ).scalars()
    )

    raw_run_samples: dict[str, list[ProviderShadowValidationSample]] = {
        str(run.id): [] for run in runs
    }
    for run in runs:
        _coerce_kpi_run_status(run.status)
    if runs:
        run_tenant_ids = {str(run.id): run.tenant_id for run in runs}
        all_samples = list(
            (
                await session.execute(
                    select(ProviderShadowValidationSample)
                    .where(ProviderShadowValidationSample.run_row_id.in_([run.id for run in runs]))
                    .order_by(
                        ProviderShadowValidationSample.run_row_id,
                        ProviderShadowValidationSample.observed_at,
                        ProviderShadowValidationSample.sample_id,
                    )
                )
            ).scalars()
        )
        for sample in all_samples:
            run_key = str(sample.run_row_id)
            if run_key not in run_tenant_ids:
                raise _kpi_conflict("shadow sample does not belong to a selected run")
            run_tenant_id = run_tenant_ids[run_key]
            _validate_kpi_sample(sample, run_tenant_id=run_tenant_id)
            raw_run_samples[run_key].append(sample)
    run_samples: dict[uuid.UUID, list[ProviderShadowValidationSample]] = {}
    for run in runs:
        run_samples[run.id] = _kpi_filter_samples_by_window(
            raw_run_samples[str(run.id)], from_at=from_at, to_at=to_at
        )

    run_metrics = [
        _kpi_run_metric(run, run_samples[run.id], requested_tenant_id=tenant_id) for run in runs
    ]
    run_metrics.sort(key=lambda item: (item.application_id, item.evaluation_id, item.run_id))
    timeline = [
        point
        for run in runs
        for point in _kpi_timeline_points(
            run,
            run_samples[run.id],
            requested_tenant_id=tenant_id,
        )
    ]
    timeline.sort(
        key=lambda item: (item.bucket_start, item.application_id, item.evaluation_id, item.run_id)
    )
    aggregate_samples = [sample for samples in run_samples.values() for sample in samples]

    rollout_rows: list[ProviderGradientRollout] = []
    if runs:
        rollout_conditions: list[ColumnElement[bool]] = [
            ProviderGradientRollout.requested_provider_id == provider_id,
            ProviderGradientRollout.shadow_run_row_id.in_([run.id for run in runs]),
            (
                ProviderGradientRollout.tenant_id.is_(None)
                if tenant_id is None
                else ProviderGradientRollout.tenant_id == tenant_id
            ),
        ]
        rollout_rows = list(
            (
                await session.execute(
                    select(ProviderGradientRollout)
                    .where(*rollout_conditions)
                    .order_by(
                        ProviderGradientRollout.application_id,
                        ProviderGradientRollout.evaluation_id,
                        ProviderGradientRollout.run_id,
                        ProviderGradientRollout.rollout_id,
                    )
                )
            ).scalars()
        )

    return ProviderKpiDashboardResponse(
        provider_id=provider_id,
        tenant_id=tenant_id,
        from_at=from_at,
        to_at=to_at,
        run_status_counts=_kpi_run_status_counts(runs),
        total_runs=len(runs),
        aggregate=_kpi_metrics(aggregate_samples),
        rollout_summary=_kpi_rollout_summary(rollout_rows, requested_tenant_id=tenant_id),
        run_metrics=run_metrics,
        timeline=timeline,
    )


@router.post(
    "/provider-applications/{application_id}/evaluation-requests/{evaluation_id}"
    "/shadow-runs/{run_id}/rollouts/{rollout_id}/advance",
    response_model=ProviderRolloutResponse,
    tags=["provider-gradient-rollout"],
)
async def advance_provider_rollout(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    evaluation_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    run_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    rollout_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    body: ProviderRolloutActionRequest,
    tenant_id: uuid.UUID | None = Query(default=None),
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> ProviderRolloutResponse:
    _require_write_auth(x_internal_service_auth)
    _, _, run = await _resolve_shadow_run_for_rollout(
        session,
        application_id=application_id,
        evaluation_id=evaluation_id,
        run_id=run_id,
        tenant_id=tenant_id,
    )
    row = await _load_rollout_row(
        session,
        shadow_run_row_id=run.id,
        rollout_id=rollout_id,
        tenant_id=tenant_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider gradient rollout not found",
        )
    row = await _lock_rollout_row(session, row)
    if row.status == "completed":
        if body.target_stage_percent not in {None, 100}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="completed rollout can only replay completion",
            )
        return await _rollout_response(row, requested_tenant_id=tenant_id)
    if row.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="cancelled rollout cannot be advanced",
        )
    if row.status not in {"draft", "active", "paused"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="rollout cannot be advanced from current status",
        )
    next_stage = _next_rollout_stage(row.current_stage_percent)
    if next_stage is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="rollout has no next stage",
        )
    if body.target_stage_percent is not None and body.target_stage_percent != next_stage:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="target_stage_percent must be the next rollout stage",
        )
    now = datetime.now(UTC)
    from_status = row.status
    to_status = "completed" if next_stage == 100 else "active"
    row.status = to_status
    row.current_stage_percent = next_stage
    row.started_at = row.started_at or now
    if next_stage == 100:
        row.completed_at = row.completed_at or now
    if from_status == "paused":
        row.paused_at = row.paused_at or now
    _append_stage_history(
        row,
        _stage_history_entry(
            stage_percent=next_stage,
            changed_at=now,
            from_status=from_status,
            to_status=to_status,
            reason_ref=body.reason_ref,
            action="advance",
            metadata=body.metadata,
        ),
    )
    row.updated_at = now
    await session.flush()
    return await _rollout_response(row, requested_tenant_id=tenant_id)


@router.post(
    "/provider-applications/{application_id}/evaluation-requests/{evaluation_id}"
    "/shadow-runs/{run_id}/rollouts/{rollout_id}/pause",
    response_model=ProviderRolloutResponse,
    tags=["provider-gradient-rollout"],
)
async def pause_provider_rollout(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    evaluation_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    run_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    rollout_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    body: ProviderRolloutActionRequest,
    tenant_id: uuid.UUID | None = Query(default=None),
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> ProviderRolloutResponse:
    _require_write_auth(x_internal_service_auth)
    _, _, run = await _resolve_shadow_run_for_rollout(
        session,
        application_id=application_id,
        evaluation_id=evaluation_id,
        run_id=run_id,
        tenant_id=tenant_id,
    )
    row = await _load_rollout_row(
        session,
        shadow_run_row_id=run.id,
        rollout_id=rollout_id,
        tenant_id=tenant_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider gradient rollout not found",
        )
    row = await _lock_rollout_row(session, row)
    if body.target_stage_percent is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="pause does not accept target_stage_percent",
        )
    if row.status != "active" or row.current_stage_percent not in {5, 50}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="only active rollout at 5 or 50 percent can be paused",
        )
    now = datetime.now(UTC)
    from_status = row.status
    row.status = "paused"
    row.paused_at = row.paused_at or now
    _append_stage_history(
        row,
        _stage_history_entry(
            stage_percent=row.current_stage_percent,
            changed_at=now,
            from_status=from_status,
            to_status="paused",
            reason_ref=body.reason_ref,
            action="pause",
            metadata=body.metadata,
        ),
    )
    row.updated_at = now
    await session.flush()
    return await _rollout_response(row, requested_tenant_id=tenant_id)


@router.post(
    "/provider-applications/{application_id}/evaluation-requests/{evaluation_id}"
    "/shadow-runs/{run_id}/rollouts/{rollout_id}/cancel",
    response_model=ProviderRolloutResponse,
    tags=["provider-gradient-rollout"],
)
async def cancel_provider_rollout(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    evaluation_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    run_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    rollout_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    body: ProviderRolloutActionRequest,
    tenant_id: uuid.UUID | None = Query(default=None),
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> ProviderRolloutResponse:
    _require_write_auth(x_internal_service_auth)
    _, _, run = await _resolve_shadow_run_for_rollout(
        session,
        application_id=application_id,
        evaluation_id=evaluation_id,
        run_id=run_id,
        tenant_id=tenant_id,
    )
    row = await _load_rollout_row(
        session,
        shadow_run_row_id=run.id,
        rollout_id=rollout_id,
        tenant_id=tenant_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider gradient rollout not found",
        )
    row = await _lock_rollout_row(session, row)
    if body.target_stage_percent is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="cancel does not accept target_stage_percent",
        )
    if row.status == "cancelled":
        return await _rollout_response(row, requested_tenant_id=tenant_id)
    if row.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="completed rollout cannot be cancelled",
        )
    now = datetime.now(UTC)
    from_status = row.status
    row.status = "cancelled"
    row.cancelled_at = row.cancelled_at or now
    _append_stage_history(
        row,
        _stage_history_entry(
            stage_percent=row.current_stage_percent,
            changed_at=now,
            from_status=from_status,
            to_status="cancelled",
            reason_ref=body.reason_ref,
            action="cancel",
            metadata=body.metadata,
        ),
    )
    row.updated_at = now
    await session.flush()
    return await _rollout_response(row, requested_tenant_id=tenant_id)
