"""Capability-registry API routes."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
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
    ProviderOAuthFlow,
    RevenueShareHook,
    RevenueSharePolicy,
)
from capability_registry.schemas import (
    CapabilityResponse,
    CapabilityUpsertRequest,
    ModelVersion,
    OAuthFlowResponse,
    OAuthFlowUpsertRequest,
    ProviderResponse,
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
