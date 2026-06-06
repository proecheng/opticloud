"""Capability-registry API routes."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from math import ceil
from typing import Annotated, Any, Protocol, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from starlette.responses import Response

from capability_registry.cache import CAPABILITY_CACHE_PREFIX, CapabilityCache, cache_key
from capability_registry.config import settings
from capability_registry.db import get_session
from capability_registry.equivalent_matching import (
    EquivalentCapabilitySnapshot,
    match_equivalent_capabilities,
)
from capability_registry.models import (
    Capability,
    CapabilityProvider,
    CapabilityTag,
    CapabilityVocabAlias,
    CapabilityVocabTerm,
    ProviderApplication,
    ProviderApplicationEvaluationRequest,
    ProviderGradientRollout,
    ProviderMonthlyRevenueShareBatch,
    ProviderOAuthFlow,
    ProviderRevenuePayoutEntry,
    ProviderShadowValidationRun,
    ProviderShadowValidationSample,
    ProviderVersionUpdateRequest,
    RevenueShareHook,
    RevenueSharePolicy,
)
from capability_registry.schemas import (
    CapabilityResponse,
    CapabilityUpsertRequest,
    CapabilityVocabAliasResponse,
    CapabilityVocabTermResponse,
    CapabilityVocabTermStatus,
    CapabilityVocabTermUpsertRequest,
    EquivalentCapabilityResponse,
    ModelVersion,
    OAuthFlowResponse,
    OAuthFlowUpsertRequest,
    ProviderApplicationResponse,
    ProviderApplicationStatus,
    ProviderApplicationUpsertRequest,
    ProviderDashboardScopeSource,
    ProviderEvaluationResponse,
    ProviderEvaluationStatus,
    ProviderEvaluationUpsertRequest,
    ProviderKpiAggregateMetrics,
    ProviderKpiDashboardResponse,
    ProviderKpiRolloutSummary,
    ProviderKpiRunMetric,
    ProviderKpiRunStatusCounts,
    ProviderKpiTimelinePoint,
    ProviderMonthlyRevenueShareBatchResponse,
    ProviderMonthlyRevenueShareBatchStatus,
    ProviderMonthlyRevenueShareBatchStatusPatchRequest,
    ProviderMonthlyRevenueShareBatchUpsertRequest,
    ProviderMonthlyRevenueShareCurrencyTotal,
    ProviderMonthlyRevenueShareExcludedEntry,
    ProviderMonthlyRevenueSharePolicyRatioSummary,
    ProviderMonthlyRevenueShareProviderSummary,
    ProviderResponse,
    ProviderRevenuePayoutCurrencyTotal,
    ProviderRevenuePayoutDashboardResponse,
    ProviderRevenuePayoutEntryResponse,
    ProviderRevenuePayoutEntryRow,
    ProviderRevenuePayoutEntryStatus,
    ProviderRevenuePayoutEntryUpsertRequest,
    ProviderRevenuePayoutPeriodSummary,
    ProviderRevenuePayoutStatusCounts,
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
    ProviderVersionChangeKind,
    ProviderVersionUpdateResponse,
    ProviderVersionUpdateStatus,
    ProviderVersionUpdateStatusPatchRequest,
    ProviderVersionUpdateUpsertRequest,
    RevenueShareHookCreateRequest,
    RevenueShareHookResponse,
    RevenueSharePolicyResponse,
    RevenueSharePolicyUpsertRequest,
    ScopeSource,
    _reject_forbidden_reference_fields,
    normalize_money,
    platform_revenue_amount,
    provider_revenue_amount,
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
_MONEY_QUANT = Decimal("0.0001")
_PAYOUT_ENTRY_STATUSES: tuple[ProviderRevenuePayoutEntryStatus, ...] = (
    "pending",
    "held",
    "paid",
    "voided",
)
_MONTHLY_BATCH_STATUSES: tuple[ProviderMonthlyRevenueShareBatchStatus, ...] = (
    "draft",
    "reviewed",
    "approved",
    "exported",
    "cancelled",
)
_MONTHLY_INCLUDED_STATUSES = {"pending", "held"}


@dataclass(frozen=True)
class PayoutEntryReferences:
    hooks_by_id: dict[uuid.UUID, RevenueShareHook]
    policies_by_scope_and_id: dict[tuple[uuid.UUID | None, str], RevenueSharePolicy]


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


async def _load_vocab_term_row(
    session: AsyncSession,
    *,
    tag: str,
    tenant_id: uuid.UUID | None,
    allow_global_fallback: bool,
) -> CapabilityVocabTerm | None:
    if tenant_id is not None:
        row = (
            await session.execute(
                select(CapabilityVocabTerm).where(
                    CapabilityVocabTerm.tag == tag,
                    CapabilityVocabTerm.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is not None or not allow_global_fallback:
            return row
    return (
        await session.execute(
            select(CapabilityVocabTerm).where(
                CapabilityVocabTerm.tag == tag,
                CapabilityVocabTerm.tenant_id.is_(None),
            )
        )
    ).scalar_one_or_none()


async def _load_vocab_alias_row(
    session: AsyncSession,
    *,
    alias: str,
    tenant_id: uuid.UUID | None,
    allow_global_fallback: bool,
) -> CapabilityVocabAlias | None:
    if tenant_id is not None:
        row = (
            await session.execute(
                select(CapabilityVocabAlias).where(
                    CapabilityVocabAlias.alias == alias,
                    CapabilityVocabAlias.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is not None or not allow_global_fallback:
            return row
    return (
        await session.execute(
            select(CapabilityVocabAlias).where(
                CapabilityVocabAlias.alias == alias,
                CapabilityVocabAlias.tenant_id.is_(None),
            )
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


def _vocab_alias_response(row: CapabilityVocabAlias) -> CapabilityVocabAliasResponse:
    return CapabilityVocabAliasResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        alias=row.alias,
        canonical_tag=row.canonical_tag,
        status=cast(Any, row.status),
        metadata=dict(row.alias_metadata),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _vocab_aliases_for_term(
    session: AsyncSession,
    row: CapabilityVocabTerm,
) -> list[CapabilityVocabAliasResponse]:
    conditions: list[ColumnElement[bool]] = [
        CapabilityVocabAlias.canonical_tag == row.tag,
        (
            CapabilityVocabAlias.tenant_id.is_(None)
            if row.tenant_id is None
            else CapabilityVocabAlias.tenant_id == row.tenant_id
        ),
    ]
    aliases = (
        await session.execute(
            select(CapabilityVocabAlias).where(*conditions).order_by(CapabilityVocabAlias.alias)
        )
    ).scalars()
    return [_vocab_alias_response(alias) for alias in aliases]


async def _vocab_term_response(
    session: AsyncSession,
    row: CapabilityVocabTerm,
    *,
    requested_tenant_id: uuid.UUID | None,
    include_aliases: bool,
) -> CapabilityVocabTermResponse:
    aliases = await _vocab_aliases_for_term(session, row) if include_aliases else []
    return CapabilityVocabTermResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        tag=row.tag,
        status=cast(Any, row.status),
        task_type=row.task_type,
        label_zh=row.label_zh,
        label_en=row.label_en,
        description_zh=row.description_zh,
        description_en=row.description_en,
        parent_tag=row.parent_tag,
        replaces_tag=row.replaces_tag,
        aliases=aliases,
        metadata=dict(row.term_metadata),
        scope_source=_scope_source(row.tenant_id, requested_tenant_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _resolve_vocab_reference(
    session: AsyncSession,
    *,
    tag: str,
    tenant_id: uuid.UUID | None,
    field_name: str,
) -> None:
    row = await _load_vocab_term_row(
        session,
        tag=tag,
        tenant_id=tenant_id,
        allow_global_fallback=tenant_id is not None,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} vocab term not found",
        )


async def _canonical_tag_for_capability_input(
    session: AsyncSession,
    *,
    tag: str,
    tenant_id: uuid.UUID | None,
) -> str:
    term = await _load_vocab_term_row(
        session,
        tag=tag,
        tenant_id=tenant_id,
        allow_global_fallback=tenant_id is not None,
    )
    alias = await _load_vocab_alias_row(
        session,
        alias=tag,
        tenant_id=tenant_id,
        allow_global_fallback=tenant_id is not None,
    )
    if term is not None and term.status != "active":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"capability vocab tag {tag} is not active",
        )
    if alias is not None and alias.status != "active":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"capability vocab alias {tag} is not active",
        )
    if term is not None and alias is not None and alias.canonical_tag != term.tag:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"capability vocab input {tag} resolves ambiguously",
        )
    if term is not None:
        return term.tag
    if alias is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"capability vocab tag {tag} not found",
        )
    canonical = await _load_vocab_term_row(
        session,
        tag=alias.canonical_tag,
        tenant_id=alias.tenant_id,
        allow_global_fallback=alias.tenant_id is not None,
    )
    if canonical is None or canonical.status != "active":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"canonical capability vocab tag {alias.canonical_tag} is not active",
        )
    return canonical.tag


async def _resolve_capability_vocab_tags(
    session: AsyncSession,
    *,
    tags: list[str],
    tenant_id: uuid.UUID | None,
) -> list[str]:
    canonical: set[str] = set()
    for tag in tags:
        canonical.add(
            await _canonical_tag_for_capability_input(
                session,
                tag=tag,
                tenant_id=tenant_id,
            )
        )
    return sorted(canonical)


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


async def _effective_capability_rows(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
) -> list[Capability]:
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
    return sorted(rows_by_algo.values(), key=lambda item: item.k_algo)


async def _equivalent_snapshot(
    session: AsyncSession,
    row: Capability,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> EquivalentCapabilitySnapshot:
    provider = await _load_provider_row(
        session,
        provider_id=row.provider_id,
        tenant_id=row.tenant_id,
        allow_global_fallback=True,
    )
    tags = await _capability_tags(session, row.id)
    return EquivalentCapabilitySnapshot(
        k_algo=row.k_algo,
        task_type=row.task_type,
        provider_id=row.provider_id,
        provider_kind=provider.kind if provider is not None else "",
        provider_url=provider.provider_url if provider is not None else "",
        provider_status=provider.status if provider is not None else None,
        model_version=row.model_version,
        capability_status=row.status,
        supported_solvers=tuple(row.supported_solvers),
        tags=tuple(tags),
        metadata=dict(row.capability_metadata),
        scope_source=_scope_source(row.tenant_id, requested_tenant_id),
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


@router.get(
    "/capability-vocab/terms",
    response_model=list[CapabilityVocabTermResponse],
    tags=["capability-vocab"],
)
async def list_capability_vocab_terms(
    tenant_id: uuid.UUID | None = Query(default=None),
    status_filter: CapabilityVocabTermStatus | None = Query(default=None, alias="status"),
    task_type: str | None = Query(default=None),
    include_aliases: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
    cache_backend: CacheBackend = Depends(get_cache),
) -> list[CapabilityVocabTermResponse]:
    normalized_task_type = task_type.strip() if task_type is not None else None
    if not normalized_task_type:
        normalized_task_type = None
    key = cache_key(
        "capability-vocab:terms:list",
        tenant_id=tenant_id or "global",
        status=status_filter or "all",
        task_type=normalized_task_type or "all",
        include_aliases=include_aliases,
    )
    cached = await _cached(cache_backend, key)
    if isinstance(cached, list):
        return [CapabilityVocabTermResponse.model_validate(item) for item in cached]

    global_rows = (
        await session.execute(
            select(CapabilityVocabTerm)
            .where(CapabilityVocabTerm.tenant_id.is_(None))
            .order_by(CapabilityVocabTerm.tag)
        )
    ).scalars()
    rows_by_tag = {row.tag: row for row in global_rows}
    if tenant_id is not None:
        tenant_rows = (
            await session.execute(
                select(CapabilityVocabTerm)
                .where(CapabilityVocabTerm.tenant_id == tenant_id)
                .order_by(CapabilityVocabTerm.tag)
            )
        ).scalars()
        for row in tenant_rows:
            rows_by_tag[row.tag] = row
    effective_rows = [
        row
        for row in rows_by_tag.values()
        if (status_filter is None or row.status == status_filter)
        and (normalized_task_type is None or row.task_type == normalized_task_type)
    ]
    responses = [
        await _vocab_term_response(
            session,
            row,
            requested_tenant_id=tenant_id,
            include_aliases=include_aliases,
        )
        for row in sorted(effective_rows, key=lambda item: item.tag)
    ]
    await _cache_set(cache_backend, key, [item.model_dump(mode="json") for item in responses])
    return responses


@router.get(
    "/capability-vocab/terms/{tag}",
    response_model=CapabilityVocabTermResponse,
    tags=["capability-vocab"],
)
async def get_capability_vocab_term(
    tag: Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")],
    tenant_id: uuid.UUID | None = Query(default=None),
    include_aliases: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
    cache_backend: CacheBackend = Depends(get_cache),
) -> CapabilityVocabTermResponse:
    key = cache_key(
        "capability-vocab:terms:detail",
        tag=tag,
        tenant_id=tenant_id or "global",
        include_aliases=include_aliases,
    )
    cached = await _cached(cache_backend, key)
    if isinstance(cached, dict):
        return CapabilityVocabTermResponse.model_validate(cached)
    row = await _load_vocab_term_row(
        session,
        tag=tag,
        tenant_id=tenant_id,
        allow_global_fallback=tenant_id is not None,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="capability vocab term not found",
        )
    response = await _vocab_term_response(
        session,
        row,
        requested_tenant_id=tenant_id,
        include_aliases=include_aliases,
    )
    await _cache_set(cache_backend, key, response.model_dump(mode="json"))
    return response


@router.put(
    "/capability-vocab/terms/{tag}",
    response_model=CapabilityVocabTermResponse,
    tags=["capability-vocab"],
)
async def upsert_capability_vocab_term(
    tag: Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")],
    body: CapabilityVocabTermUpsertRequest,
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
    cache_backend: CacheBackend = Depends(get_cache),
) -> CapabilityVocabTermResponse:
    _require_write_auth(x_internal_service_auth)
    _assert_path_id(body.tag, tag, "tag")
    if body.parent_tag == tag:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="parent_tag cannot equal tag",
        )
    if body.replaces_tag == tag:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="replaces_tag cannot equal tag",
        )
    if body.parent_tag is not None:
        await _resolve_vocab_reference(
            session,
            tag=body.parent_tag,
            tenant_id=body.tenant_id,
            field_name="parent_tag",
        )
    if body.replaces_tag is not None:
        await _resolve_vocab_reference(
            session,
            tag=body.replaces_tag,
            tenant_id=body.tenant_id,
            field_name="replaces_tag",
        )

    alias_inputs = body.aliases
    aliases_seen: set[str] = set()
    for alias in alias_inputs:
        if alias.alias == tag:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="alias cannot equal canonical tag",
            )
        if alias.alias in aliases_seen:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="duplicate alias in request",
            )
        aliases_seen.add(alias.alias)
        existing_alias = await _load_vocab_alias_row(
            session,
            alias=alias.alias,
            tenant_id=body.tenant_id,
            allow_global_fallback=False,
        )
        if existing_alias is not None and existing_alias.canonical_tag != tag:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="capability vocab alias already points to another canonical tag",
            )

    row = await _load_vocab_term_row(
        session,
        tag=tag,
        tenant_id=body.tenant_id,
        allow_global_fallback=False,
    )
    now = datetime.now(UTC)
    if row is None:
        row = CapabilityVocabTerm(
            tenant_id=body.tenant_id,
            tag=tag,
            status=body.status,
            task_type=body.task_type,
            label_zh=body.label_zh,
            label_en=body.label_en,
            description_zh=body.description_zh,
            description_en=body.description_en,
            parent_tag=body.parent_tag,
            replaces_tag=body.replaces_tag,
            term_metadata=body.metadata,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.status = body.status
        row.task_type = body.task_type
        row.label_zh = body.label_zh
        row.label_en = body.label_en
        row.description_zh = body.description_zh
        row.description_en = body.description_en
        row.parent_tag = body.parent_tag
        row.replaces_tag = body.replaces_tag
        row.term_metadata = body.metadata
        row.updated_at = now
    await session.flush()

    existing_aliases = {
        alias.alias: alias
        for alias in (
            await session.execute(
                select(CapabilityVocabAlias).where(
                    CapabilityVocabAlias.canonical_tag == tag,
                    (
                        CapabilityVocabAlias.tenant_id.is_(None)
                        if body.tenant_id is None
                        else CapabilityVocabAlias.tenant_id == body.tenant_id
                    ),
                )
            )
        ).scalars()
    }
    requested_aliases = {alias.alias for alias in alias_inputs}
    for alias_value, stale_alias_row in existing_aliases.items():
        if alias_value not in requested_aliases:
            await session.delete(stale_alias_row)
    for alias in alias_inputs:
        alias_row = existing_aliases.get(alias.alias)
        if alias_row is None:
            alias_row = CapabilityVocabAlias(
                tenant_id=body.tenant_id,
                alias=alias.alias,
                canonical_tag=tag,
                status=alias.status,
                alias_metadata=alias.metadata,
                created_at=now,
                updated_at=now,
            )
            session.add(alias_row)
        else:
            alias_row.status = alias.status
            alias_row.alias_metadata = alias.metadata
            alias_row.updated_at = now
    await session.flush()
    await _invalidate_cache(cache_backend)
    return await _vocab_term_response(
        session,
        row,
        requested_tenant_id=body.tenant_id,
        include_aliases=True,
    )


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


@router.get(
    "/capabilities/{k_algo}/equivalents",
    response_model=EquivalentCapabilityResponse,
    tags=["capabilities"],
)
async def get_capability_equivalents(
    k_algo: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    solver: str = Query(..., min_length=1),
    tenant_id: uuid.UUID | None = Query(default=None),
    max_results: int = Query(default=10, ge=1, le=50),
    include_source: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
    cache_backend: CacheBackend = Depends(get_cache),
) -> EquivalentCapabilityResponse:
    normalized_solver = solver.strip()
    if not normalized_solver:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="solver cannot be blank",
        )
    key = cache_key(
        "capabilities:equivalents",
        k_algo=k_algo,
        tenant_id=tenant_id or "global",
        solver=normalized_solver,
        max_results=max_results,
        include_source=include_source,
    )
    cached = await _cached(cache_backend, key)
    if isinstance(cached, dict):
        return EquivalentCapabilityResponse.model_validate(cached)

    source_row = await _load_capability_row(
        session,
        k_algo=k_algo,
        tenant_id=tenant_id,
        allow_global_fallback=tenant_id is not None,
    )
    if source_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="capability not found")
    if normalized_solver not in source_row.supported_solvers:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="solver is not supported by source capability",
        )

    effective_rows = await _effective_capability_rows(session, tenant_id=tenant_id)
    source_snapshot = await _equivalent_snapshot(
        session,
        source_row,
        requested_tenant_id=tenant_id,
    )
    if not source_snapshot.tags:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="source capability has no canonical tags",
        )
    candidate_snapshots = tuple(
        [
            await _equivalent_snapshot(
                session,
                row,
                requested_tenant_id=tenant_id,
            )
            for row in effective_rows
        ]
    )
    result = match_equivalent_capabilities(
        source=source_snapshot,
        candidates=candidate_snapshots,
        solver=normalized_solver,
        max_results=max_results,
        include_source=include_source,
    )
    response = EquivalentCapabilityResponse.model_validate(result.to_response())
    await _cache_set(cache_backend, key, response.model_dump(mode="json"))
    return response


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
    canonical_tags = await _resolve_capability_vocab_tags(
        session,
        tags=body.tags,
        tenant_id=body.tenant_id,
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
    for tag in canonical_tags:
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


async def _load_revenue_hook_by_id_exact_scope(
    session: AsyncSession,
    *,
    hook_id: uuid.UUID,
    tenant_id: uuid.UUID | None,
) -> RevenueShareHook | None:
    return (
        await session.execute(
            select(RevenueShareHook).where(
                RevenueShareHook.id == hook_id,
                (
                    RevenueShareHook.tenant_id.is_(None)
                    if tenant_id is None
                    else RevenueShareHook.tenant_id == tenant_id
                ),
            )
        )
    ).scalar_one_or_none()


async def _load_payout_entry_row(
    session: AsyncSession,
    *,
    entry_id: str,
    tenant_id: uuid.UUID | None,
) -> ProviderRevenuePayoutEntry | None:
    return (
        await session.execute(
            select(ProviderRevenuePayoutEntry).where(
                ProviderRevenuePayoutEntry.entry_id == entry_id,
                (
                    ProviderRevenuePayoutEntry.tenant_id.is_(None)
                    if tenant_id is None
                    else ProviderRevenuePayoutEntry.tenant_id == tenant_id
                ),
            )
        )
    ).scalar_one_or_none()


async def _load_payout_entry_by_hook(
    session: AsyncSession,
    *,
    hook_id: uuid.UUID,
) -> ProviderRevenuePayoutEntry | None:
    return (
        await session.execute(
            select(ProviderRevenuePayoutEntry).where(
                ProviderRevenuePayoutEntry.hook_row_id == hook_id
            )
        )
    ).scalar_one_or_none()


def _payout_conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _coerce_payout_status(value: str) -> ProviderRevenuePayoutEntryStatus:
    if value not in _PAYOUT_ENTRY_STATUSES:
        raise _payout_conflict("payout entry status drift")
    return value


def _validate_period_month(value: str) -> None:
    if re.fullmatch(r"^[0-9]{4}-(0[1-9]|1[0-2])$", value) is None:
        raise _payout_conflict("period_month drift")


def _validate_currency(value: str) -> None:
    if re.fullmatch(r"^[A-Z]{3}$", value) is None:
        raise _payout_conflict("currency drift")


def _validate_payout_path_id(value: str, *, field_name: str) -> None:
    if re.fullmatch(_PATH_ID_PATTERN, value) is None:
        raise _payout_conflict(f"{field_name} drift")


def _validate_payout_source_service(value: str) -> None:
    if re.fullmatch(r"^[a-z0-9][a-z0-9-]{0,63}$", value) is None:
        raise _payout_conflict("source_service drift")


def _coerce_money(value: Decimal, *, field_name: str) -> Decimal:
    if value < 0:
        raise _payout_conflict(f"{field_name} drift")
    return value.quantize(_MONEY_QUANT)


def _coerce_ratio(value: Decimal, *, field_name: str) -> Decimal:
    if value < 0 or value > 1:
        raise _payout_conflict(f"{field_name} drift")
    return value.quantize(_RATIO_QUANT)


def _require_payout_aware_datetime(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise _payout_conflict(f"{field_name} must be timezone-aware")


def _validate_payout_entry_matches_hook(
    row: ProviderRevenuePayoutEntry,
    hook: RevenueShareHook,
) -> None:
    if row.tenant_id != hook.tenant_id:
        raise _payout_conflict("payout entry tenant scope drift")
    expected = {
        "provider_id": hook.provider_id,
        "k_algo": hook.k_algo,
        "policy_id": hook.policy_id,
        "source_service": hook.source_service,
        "source_event_id": hook.source_event_id,
        "period_month": hook.period_month,
    }
    actual = {
        "provider_id": row.provider_id,
        "k_algo": row.k_algo,
        "policy_id": row.policy_id,
        "source_service": row.source_service,
        "source_event_id": row.source_event_id,
        "period_month": row.period_month,
    }
    changed = sorted(key for key, value in expected.items() if actual[key] != value)
    if changed:
        raise _payout_conflict(f"payout entry hook drift: {', '.join(changed)}")


async def _load_payout_entry_references(
    session: AsyncSession,
    rows: list[ProviderRevenuePayoutEntry],
) -> PayoutEntryReferences:
    if not rows:
        return PayoutEntryReferences(hooks_by_id={}, policies_by_scope_and_id={})

    hook_ids = {row.hook_row_id for row in rows}
    hooks = list(
        (
            await session.execute(select(RevenueShareHook).where(RevenueShareHook.id.in_(hook_ids)))
        ).scalars()
    )

    policy_ids = {row.policy_id for row in rows}
    tenant_ids = {row.tenant_id for row in rows if row.tenant_id is not None}
    policy_scope_condition: ColumnElement[bool]
    if tenant_ids:
        policy_scope_condition = or_(
            RevenueSharePolicy.tenant_id.is_(None),
            RevenueSharePolicy.tenant_id.in_(tenant_ids),
        )
    else:
        policy_scope_condition = RevenueSharePolicy.tenant_id.is_(None)
    policies = list(
        (
            await session.execute(
                select(RevenueSharePolicy).where(
                    RevenueSharePolicy.policy_id.in_(policy_ids),
                    policy_scope_condition,
                )
            )
        ).scalars()
    )
    return PayoutEntryReferences(
        hooks_by_id={hook.id: hook for hook in hooks},
        policies_by_scope_and_id={
            (policy.tenant_id, policy.policy_id): policy for policy in policies
        },
    )


def _validate_payout_policy_snapshot(
    row: ProviderRevenuePayoutEntry,
    references: PayoutEntryReferences,
) -> None:
    policy = references.policies_by_scope_and_id.get((row.tenant_id, row.policy_id))
    if policy is None and row.tenant_id is not None:
        policy = references.policies_by_scope_and_id.get((None, row.policy_id))
    if policy is None:
        raise _payout_conflict("payout entry policy drift")
    platform_ratio = _coerce_ratio(row.platform_share_ratio, field_name="platform_share_ratio")
    provider_ratio = _coerce_ratio(row.provider_share_ratio, field_name="provider_share_ratio")
    if platform_ratio + provider_ratio != Decimal("1.000000"):
        raise _payout_conflict("payout entry ratio drift")
    policy_platform_ratio = _coerce_ratio(
        policy.platform_share_ratio,
        field_name="policy platform_share_ratio",
    )
    policy_provider_ratio = _coerce_ratio(
        policy.provider_share_ratio,
        field_name="policy provider_share_ratio",
    )
    if policy_platform_ratio + policy_provider_ratio != Decimal("1.000000"):
        raise _payout_conflict("payout entry policy ratio drift")


def _validate_payout_entry(
    row: ProviderRevenuePayoutEntry,
    references: PayoutEntryReferences,
) -> None:
    _coerce_payout_status(row.status)
    _validate_payout_path_id(row.entry_id, field_name="entry_id")
    _validate_payout_path_id(row.provider_id, field_name="provider_id")
    _validate_payout_path_id(row.k_algo, field_name="k_algo")
    _validate_payout_path_id(row.policy_id, field_name="policy_id")
    _validate_payout_source_service(row.source_service)
    _validate_period_month(row.period_month)
    _validate_currency(row.currency)
    _coerce_money(row.gross_amount, field_name="gross_amount")
    _coerce_ratio(row.platform_share_ratio, field_name="platform_share_ratio")
    _coerce_ratio(row.provider_share_ratio, field_name="provider_share_ratio")
    _require_payout_aware_datetime(row.recognized_at, field_name="recognized_at")
    hook = references.hooks_by_id.get(row.hook_row_id)
    if hook is None:
        raise _payout_conflict("payout entry hook drift")
    _validate_payout_entry_matches_hook(row, hook)
    _validate_payout_policy_snapshot(row, references)


def _payout_amounts(row: ProviderRevenuePayoutEntry) -> tuple[Decimal, Decimal]:
    gross = normalize_money(row.gross_amount)
    provider_amount = provider_revenue_amount(gross, row.provider_share_ratio)
    platform_amount = platform_revenue_amount(gross, provider_amount)
    return provider_amount, platform_amount


def _payout_scope_source(
    row_tenant_id: uuid.UUID | None,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderDashboardScopeSource:
    source = _scope_source(row_tenant_id, requested_tenant_id)
    if source == "global_fallback":
        raise _payout_conflict("payout dashboard cannot use global fallback scope")
    return source


def _validated_payout_entry_response(
    row: ProviderRevenuePayoutEntry,
    references: PayoutEntryReferences,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderRevenuePayoutEntryResponse:
    _validate_payout_entry(row, references)
    provider_amount, platform_amount = _payout_amounts(row)
    return ProviderRevenuePayoutEntryResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        entry_id=row.entry_id,
        hook_id=row.hook_row_id,
        provider_id=row.provider_id,
        k_algo=row.k_algo,
        policy_id=row.policy_id,
        source_service=row.source_service,
        source_event_id=row.source_event_id,
        period_month=row.period_month,
        currency=row.currency,
        gross_amount=normalize_money(row.gross_amount),
        provider_share_ratio=row.provider_share_ratio,
        platform_share_ratio=row.platform_share_ratio,
        provider_revenue_amount=provider_amount,
        platform_revenue_amount=platform_amount,
        status=_coerce_payout_status(row.status),
        recognized_at=row.recognized_at,
        scope_source=_payout_scope_source(row.tenant_id, requested_tenant_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _payout_entry_response(
    session: AsyncSession,
    row: ProviderRevenuePayoutEntry,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderRevenuePayoutEntryResponse:
    references = await _load_payout_entry_references(session, [row])
    return _validated_payout_entry_response(
        row,
        references,
        requested_tenant_id=requested_tenant_id,
    )


def _payout_entry_row_from_response(
    response: ProviderRevenuePayoutEntryResponse,
) -> ProviderRevenuePayoutEntryRow:
    return ProviderRevenuePayoutEntryRow(
        entry_id=response.entry_id,
        hook_id=response.hook_id,
        provider_id=response.provider_id,
        k_algo=response.k_algo,
        policy_id=response.policy_id,
        source_service=response.source_service,
        source_event_id=response.source_event_id,
        period_month=response.period_month,
        currency=response.currency,
        gross_amount=response.gross_amount,
        provider_share_ratio=response.provider_share_ratio,
        platform_share_ratio=response.platform_share_ratio,
        provider_revenue_amount=response.provider_revenue_amount,
        platform_revenue_amount=response.platform_revenue_amount,
        status=response.status,
        recognized_at=response.recognized_at,
        scope_source=response.scope_source,
    )


def _assert_payout_entry_material_unchanged(
    row: ProviderRevenuePayoutEntry,
    body: ProviderRevenuePayoutEntryUpsertRequest,
) -> None:
    existing = {
        "hook_id": row.hook_row_id,
        "gross_amount": normalize_money(row.gross_amount),
        "currency": row.currency,
        "recognized_at": row.recognized_at,
    }
    incoming = {
        "hook_id": body.hook_id,
        "gross_amount": body.gross_amount,
        "currency": body.currency,
        "recognized_at": body.recognized_at,
    }
    changed = sorted(key for key, value in incoming.items() if existing[key] != value)
    if changed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"payout entry material fields are immutable: {', '.join(changed)}",
        )


def _assert_payout_status_transition(
    current_status: str,
    next_status: ProviderRevenuePayoutEntryStatus,
) -> None:
    current = _coerce_payout_status(current_status)
    if current == next_status:
        return
    allowed = {
        "pending": {"held", "paid", "voided"},
        "held": {"pending", "paid", "voided"},
        "paid": set(),
        "voided": set(),
    }
    if next_status not in allowed[current]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid payout entry status transition: {current} -> {next_status}",
        )


def _empty_payout_status_counts() -> ProviderRevenuePayoutStatusCounts:
    return ProviderRevenuePayoutStatusCounts(pending=0, held=0, paid=0, voided=0)


def _payout_status_counts(
    rows: list[ProviderRevenuePayoutEntryRow],
) -> ProviderRevenuePayoutStatusCounts:
    counts = dict.fromkeys(_PAYOUT_ENTRY_STATUSES, 0)
    for row in rows:
        counts[row.status] += 1
    return ProviderRevenuePayoutStatusCounts(**counts)


def _empty_payout_amounts() -> dict[str, Decimal]:
    return {
        "gross_amount": Decimal("0.0000"),
        "provider_revenue_amount": Decimal("0.0000"),
        "platform_revenue_amount": Decimal("0.0000"),
        "pending_payout_amount": Decimal("0.0000"),
        "held_payout_amount": Decimal("0.0000"),
        "paid_amount": Decimal("0.0000"),
        "voided_gross_amount": Decimal("0.0000"),
    }


def _add_payout_amounts(
    totals: dict[str, Decimal],
    row: ProviderRevenuePayoutEntryRow,
) -> None:
    gross = normalize_money(row.gross_amount)
    provider_amount = normalize_money(row.provider_revenue_amount)
    platform_amount = normalize_money(row.platform_revenue_amount)
    if row.status == "voided":
        totals["voided_gross_amount"] += gross
        return
    totals["gross_amount"] += gross
    totals["provider_revenue_amount"] += provider_amount
    totals["platform_revenue_amount"] += platform_amount
    if row.status == "pending":
        totals["pending_payout_amount"] += provider_amount
    elif row.status == "held":
        totals["held_payout_amount"] += provider_amount
    elif row.status == "paid":
        totals["paid_amount"] += provider_amount


def _payout_currency_totals(
    rows: list[ProviderRevenuePayoutEntryRow],
) -> list[ProviderRevenuePayoutCurrencyTotal]:
    grouped: dict[str, tuple[int, dict[str, Decimal]]] = {}
    for row in rows:
        count, totals = grouped.setdefault(row.currency, (0, _empty_payout_amounts()))
        _add_payout_amounts(totals, row)
        grouped[row.currency] = (count + 1, totals)
    return [
        ProviderRevenuePayoutCurrencyTotal(
            currency=currency,
            entry_count=count,
            **totals,
        )
        for currency, (count, totals) in sorted(grouped.items())
    ]


def _payout_period_summaries(
    rows: list[ProviderRevenuePayoutEntryRow],
) -> list[ProviderRevenuePayoutPeriodSummary]:
    grouped: dict[tuple[str, str], tuple[int, dict[str, Decimal]]] = {}
    for row in rows:
        key = (row.period_month, row.currency)
        count, totals = grouped.setdefault(key, (0, _empty_payout_amounts()))
        _add_payout_amounts(totals, row)
        grouped[key] = (count + 1, totals)
    return [
        ProviderRevenuePayoutPeriodSummary(
            period_month=period_month,
            currency=currency,
            entry_count=count,
            **totals,
        )
        for (period_month, currency), (count, totals) in sorted(grouped.items())
    ]


def _monthly_conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _coerce_monthly_status(value: str) -> ProviderMonthlyRevenueShareBatchStatus:
    if value not in _MONTHLY_BATCH_STATUSES:
        raise _monthly_conflict("monthly batch status drift")
    return value


def _validate_monthly_reference(value: str | None, *, field_name: str) -> None:
    if value is not None and not re.match(r"^(s3|oss|fixture|benchmark|repro)://", value):
        raise _monthly_conflict(f"{field_name} drift")


def _ratio_string(value: Decimal) -> str:
    return f"{value.quantize(_RATIO_QUANT):.6f}"


def _monthly_empty_amounts() -> dict[str, Decimal]:
    return {
        "gross_amount": Decimal("0.0000"),
        "provider_revenue_amount": Decimal("0.0000"),
        "platform_revenue_amount": Decimal("0.0000"),
        "pending_payout_amount": Decimal("0.0000"),
        "held_payout_amount": Decimal("0.0000"),
    }


def _monthly_add_amounts(
    totals: dict[str, Decimal],
    row: ProviderRevenuePayoutEntryRow,
) -> None:
    gross = normalize_money(row.gross_amount)
    provider_amount = normalize_money(row.provider_revenue_amount)
    platform_amount = normalize_money(row.platform_revenue_amount)
    totals["gross_amount"] += gross
    totals["provider_revenue_amount"] += provider_amount
    totals["platform_revenue_amount"] += platform_amount
    if row.status == "pending":
        totals["pending_payout_amount"] += provider_amount
    elif row.status == "held":
        totals["held_payout_amount"] += provider_amount


def _monthly_provider_summaries(
    rows: list[ProviderRevenuePayoutEntryRow],
) -> list[ProviderMonthlyRevenueShareProviderSummary]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row.provider_id, row.currency)
        item = grouped.setdefault(
            key,
            {
                "provider_id": row.provider_id,
                "currency": row.currency,
                "entry_count": 0,
                "pending_entry_count": 0,
                "held_entry_count": 0,
                "entry_ids": [],
                "scope_source": row.scope_source,
                **_monthly_empty_amounts(),
            },
        )
        item["entry_count"] += 1
        if row.status == "pending":
            item["pending_entry_count"] += 1
        elif row.status == "held":
            item["held_entry_count"] += 1
        item["entry_ids"].append(row.entry_id)
        _monthly_add_amounts(item, row)
    summaries: list[ProviderMonthlyRevenueShareProviderSummary] = []
    for item in grouped.values():
        item["entry_ids"] = sorted(item["entry_ids"])
        summaries.append(ProviderMonthlyRevenueShareProviderSummary(**item))
    return sorted(summaries, key=lambda item: (item.provider_id, item.currency))


def _monthly_currency_totals(
    rows: list[ProviderRevenuePayoutEntryRow],
) -> list[ProviderMonthlyRevenueShareCurrencyTotal]:
    grouped: dict[str, dict[str, Any]] = {}
    providers_by_currency: dict[str, set[str]] = {}
    for row in rows:
        item = grouped.setdefault(
            row.currency,
            {
                "currency": row.currency,
                "entry_count": 0,
                "provider_count": 0,
                **_monthly_empty_amounts(),
            },
        )
        item["entry_count"] += 1
        providers_by_currency.setdefault(row.currency, set()).add(row.provider_id)
        _monthly_add_amounts(item, row)
    totals: list[ProviderMonthlyRevenueShareCurrencyTotal] = []
    for currency, item in grouped.items():
        item["provider_count"] = len(providers_by_currency.get(currency, set()))
        totals.append(ProviderMonthlyRevenueShareCurrencyTotal(**item))
    return sorted(totals, key=lambda item: item.currency)


def _monthly_policy_ratio_summaries(
    rows: list[ProviderRevenuePayoutEntryRow],
) -> list[ProviderMonthlyRevenueSharePolicyRatioSummary]:
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            row.policy_id,
            _ratio_string(row.provider_share_ratio),
            _ratio_string(row.platform_share_ratio),
            row.currency,
        )
        item = grouped.setdefault(
            key,
            {
                "policy_id": row.policy_id,
                "provider_share_ratio": row.provider_share_ratio,
                "platform_share_ratio": row.platform_share_ratio,
                "currency": row.currency,
                "entry_count": 0,
                "gross_amount": Decimal("0.0000"),
                "provider_revenue_amount": Decimal("0.0000"),
                "platform_revenue_amount": Decimal("0.0000"),
            },
        )
        item["entry_count"] += 1
        item["gross_amount"] += normalize_money(row.gross_amount)
        item["provider_revenue_amount"] += normalize_money(row.provider_revenue_amount)
        item["platform_revenue_amount"] += normalize_money(row.platform_revenue_amount)
    summaries = [ProviderMonthlyRevenueSharePolicyRatioSummary(**item) for item in grouped.values()]
    return sorted(
        summaries,
        key=lambda item: (
            item.policy_id,
            item.currency,
            _ratio_string(item.provider_share_ratio),
            _ratio_string(item.platform_share_ratio),
        ),
    )


def _monthly_model_dump(item: Any) -> dict[str, Any]:
    return cast(dict[str, Any], item.model_dump(mode="json"))


def _monthly_checksum_payload(
    *,
    tenant_id: uuid.UUID | None,
    period_month: str,
    source_entry_ids: list[str],
    provider_summaries: list[ProviderMonthlyRevenueShareProviderSummary],
    currency_totals: list[ProviderMonthlyRevenueShareCurrencyTotal],
    policy_ratio_summaries: list[ProviderMonthlyRevenueSharePolicyRatioSummary],
    excluded_entries: list[ProviderMonthlyRevenueShareExcludedEntry],
) -> dict[str, Any]:
    return {
        "tenant_id": str(tenant_id) if tenant_id is not None else None,
        "period_month": period_month,
        "source_entry_ids": source_entry_ids,
        "provider_summaries": [_monthly_model_dump(item) for item in provider_summaries],
        "currency_totals": [_monthly_model_dump(item) for item in currency_totals],
        "policy_ratio_summaries": [_monthly_model_dump(item) for item in policy_ratio_summaries],
        "excluded_entries": [_monthly_model_dump(item) for item in excluded_entries],
    }


def _monthly_checksum(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _calculate_monthly_batch_snapshot(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    period_month: str,
    allow_drift_exclusions: bool,
) -> dict[str, Any]:
    rows = list(
        (
            await session.execute(
                select(ProviderRevenuePayoutEntry)
                .where(
                    ProviderRevenuePayoutEntry.period_month == period_month,
                    (
                        ProviderRevenuePayoutEntry.tenant_id.is_(None)
                        if tenant_id is None
                        else ProviderRevenuePayoutEntry.tenant_id == tenant_id
                    ),
                )
                .order_by(ProviderRevenuePayoutEntry.entry_id)
            )
        ).scalars()
    )
    references = await _load_payout_entry_references(session, rows)
    included_rows: list[ProviderRevenuePayoutEntryRow] = []
    excluded_entries: list[ProviderMonthlyRevenueShareExcludedEntry] = []
    for row in rows:
        try:
            response = _validated_payout_entry_response(
                row, references, requested_tenant_id=tenant_id
            )
        except HTTPException:
            if not allow_drift_exclusions:
                raise
            excluded_entries.append(
                ProviderMonthlyRevenueShareExcludedEntry(
                    entry_id=row.entry_id,
                    reason="stored_drift",
                )
            )
            continue
        if response.status in _MONTHLY_INCLUDED_STATUSES:
            included_rows.append(_payout_entry_row_from_response(response))
        elif response.status in {"paid", "voided"}:
            excluded_entries.append(
                ProviderMonthlyRevenueShareExcludedEntry(
                    entry_id=response.entry_id,
                    reason=cast(Any, response.status),
                )
            )
        else:
            excluded_entries.append(
                ProviderMonthlyRevenueShareExcludedEntry(
                    entry_id=response.entry_id,
                    reason="unsupported_status",
                )
            )
    included_rows.sort(key=lambda item: item.entry_id)
    excluded_entries.sort(key=lambda item: (item.entry_id, item.reason))
    source_entry_ids = [row.entry_id for row in included_rows]
    provider_summaries = _monthly_provider_summaries(included_rows)
    currency_totals = _monthly_currency_totals(included_rows)
    policy_ratio_summaries = _monthly_policy_ratio_summaries(included_rows)
    checksum_payload = _monthly_checksum_payload(
        tenant_id=tenant_id,
        period_month=period_month,
        source_entry_ids=source_entry_ids,
        provider_summaries=provider_summaries,
        currency_totals=currency_totals,
        policy_ratio_summaries=policy_ratio_summaries,
        excluded_entries=excluded_entries,
    )
    return {
        "entry_count": len(included_rows),
        "provider_count": len({row.provider_id for row in included_rows}),
        "currency_totals": [_monthly_model_dump(item) for item in currency_totals],
        "provider_summaries": [_monthly_model_dump(item) for item in provider_summaries],
        "policy_ratio_summaries": [_monthly_model_dump(item) for item in policy_ratio_summaries],
        "excluded_entries": [_monthly_model_dump(item) for item in excluded_entries],
        "source_entry_ids": source_entry_ids,
        "calculation_checksum": _monthly_checksum(checksum_payload),
    }


async def _load_monthly_batch_row(
    session: AsyncSession,
    *,
    batch_id: str,
    tenant_id: uuid.UUID | None,
) -> ProviderMonthlyRevenueShareBatch | None:
    return (
        await session.execute(
            select(ProviderMonthlyRevenueShareBatch).where(
                ProviderMonthlyRevenueShareBatch.batch_id == batch_id,
                (
                    ProviderMonthlyRevenueShareBatch.tenant_id.is_(None)
                    if tenant_id is None
                    else ProviderMonthlyRevenueShareBatch.tenant_id == tenant_id
                ),
            )
        )
    ).scalar_one_or_none()


async def _lock_monthly_batch_row(
    session: AsyncSession,
    row: ProviderMonthlyRevenueShareBatch,
) -> ProviderMonthlyRevenueShareBatch:
    return (
        await session.execute(
            select(ProviderMonthlyRevenueShareBatch)
            .where(ProviderMonthlyRevenueShareBatch.id == row.id)
            .with_for_update()
        )
    ).scalar_one()


def _validate_monthly_batch_json(row: ProviderMonthlyRevenueShareBatch) -> None:
    if not re.match(_PATH_ID_PATTERN, row.batch_id):
        raise _monthly_conflict("batch_id drift")
    _validate_period_month(row.period_month)
    _coerce_monthly_status(row.status)
    if row.record_version < 1:
        raise _monthly_conflict("record_version drift")
    if not re.match(r"^[0-9a-f]{64}$", row.calculation_checksum):
        raise _monthly_conflict("calculation_checksum drift")
    if row.calculated_at.tzinfo is None or row.calculated_at.utcoffset() is None:
        raise _monthly_conflict("calculated_at must be timezone-aware")
    if row.created_at.tzinfo is None or row.created_at.utcoffset() is None:
        raise _monthly_conflict("created_at must be timezone-aware")
    if row.updated_at.tzinfo is None or row.updated_at.utcoffset() is None:
        raise _monthly_conflict("updated_at must be timezone-aware")
    _validate_monthly_reference(row.notes_ref, field_name="notes_ref")
    _validate_monthly_reference(row.approved_by_ref, field_name="approved_by_ref")
    if not isinstance(row.batch_metadata, dict):
        raise _monthly_conflict("metadata drift")
    for field_name in (
        "currency_totals",
        "provider_summaries",
        "policy_ratio_summaries",
        "excluded_entries",
        "source_entry_ids",
    ):
        if not isinstance(getattr(row, field_name), list):
            raise _monthly_conflict(f"{field_name} drift")


async def _validate_monthly_batch_source_entries(
    session: AsyncSession,
    row: ProviderMonthlyRevenueShareBatch,
    *,
    source_entry_ids: list[str],
    provider_summaries: list[ProviderMonthlyRevenueShareProviderSummary],
    currency_totals: list[ProviderMonthlyRevenueShareCurrencyTotal],
    policy_ratio_summaries: list[ProviderMonthlyRevenueSharePolicyRatioSummary],
) -> None:
    if not source_entry_ids:
        if provider_summaries or currency_totals or policy_ratio_summaries:
            raise _monthly_conflict("monthly batch empty source drift")
        return
    for entry_id in source_entry_ids:
        _validate_payout_path_id(entry_id, field_name="source_entry_id")
    payout_rows = list(
        (
            await session.execute(
                select(ProviderRevenuePayoutEntry)
                .where(
                    ProviderRevenuePayoutEntry.entry_id.in_(source_entry_ids),
                    (
                        ProviderRevenuePayoutEntry.tenant_id.is_(None)
                        if row.tenant_id is None
                        else ProviderRevenuePayoutEntry.tenant_id == row.tenant_id
                    ),
                )
                .order_by(ProviderRevenuePayoutEntry.entry_id)
            )
        ).scalars()
    )
    if {item.entry_id for item in payout_rows} != set(source_entry_ids):
        raise _monthly_conflict("monthly batch source entry drift")
    references = await _load_payout_entry_references(session, payout_rows)
    validated_rows: list[ProviderRevenuePayoutEntryRow] = []
    for payout_row in payout_rows:
        response = _validated_payout_entry_response(
            payout_row,
            references,
            requested_tenant_id=row.tenant_id,
        )
        if response.period_month != row.period_month:
            raise _monthly_conflict("monthly batch source period drift")
        validated_rows.append(_payout_entry_row_from_response(response))
    validated_rows.sort(key=lambda item: item.entry_id)
    if [item.entry_id for item in validated_rows] != source_entry_ids:
        raise _monthly_conflict("monthly batch source entry drift")
    actual_provider_summaries = [
        {
            "provider_id": item.provider_id,
            "currency": item.currency,
            "entry_count": item.entry_count,
            "gross_amount": item.gross_amount,
            "provider_revenue_amount": item.provider_revenue_amount,
            "platform_revenue_amount": item.platform_revenue_amount,
            "entry_ids": item.entry_ids,
            "scope_source": item.scope_source,
        }
        for item in _monthly_provider_summaries(validated_rows)
    ]
    stored_provider_summaries = [
        {
            "provider_id": item.provider_id,
            "currency": item.currency,
            "entry_count": item.entry_count,
            "gross_amount": item.gross_amount,
            "provider_revenue_amount": item.provider_revenue_amount,
            "platform_revenue_amount": item.platform_revenue_amount,
            "entry_ids": item.entry_ids,
            "scope_source": item.scope_source,
        }
        for item in provider_summaries
    ]
    if actual_provider_summaries != stored_provider_summaries:
        raise _monthly_conflict("monthly batch provider summary source drift")
    actual_currency_totals = [
        {
            "currency": item.currency,
            "entry_count": item.entry_count,
            "provider_count": item.provider_count,
            "gross_amount": item.gross_amount,
            "provider_revenue_amount": item.provider_revenue_amount,
            "platform_revenue_amount": item.platform_revenue_amount,
        }
        for item in _monthly_currency_totals(validated_rows)
    ]
    stored_currency_totals = [
        {
            "currency": item.currency,
            "entry_count": item.entry_count,
            "provider_count": item.provider_count,
            "gross_amount": item.gross_amount,
            "provider_revenue_amount": item.provider_revenue_amount,
            "platform_revenue_amount": item.platform_revenue_amount,
        }
        for item in currency_totals
    ]
    if actual_currency_totals != stored_currency_totals:
        raise _monthly_conflict("monthly batch currency total source drift")
    if _monthly_policy_ratio_summaries(validated_rows) != policy_ratio_summaries:
        raise _monthly_conflict("monthly batch policy summary source drift")


def _monthly_batch_response(
    row: ProviderMonthlyRevenueShareBatch,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderMonthlyRevenueShareBatchResponse:
    _validate_monthly_batch_json(row)
    try:
        currency_totals = [
            ProviderMonthlyRevenueShareCurrencyTotal.model_validate(item)
            for item in row.currency_totals
        ]
        provider_summaries = [
            ProviderMonthlyRevenueShareProviderSummary.model_validate(item)
            for item in row.provider_summaries
        ]
        policy_ratio_summaries = [
            ProviderMonthlyRevenueSharePolicyRatioSummary.model_validate(item)
            for item in row.policy_ratio_summaries
        ]
        excluded_entries = [
            ProviderMonthlyRevenueShareExcludedEntry.model_validate(item)
            for item in row.excluded_entries
        ]
        source_entry_ids = [str(item) for item in row.source_entry_ids]
    except ValueError as exc:
        raise _monthly_conflict("monthly batch snapshot drift") from exc
    if source_entry_ids != sorted(source_entry_ids) or len(source_entry_ids) != len(
        set(source_entry_ids)
    ):
        raise _monthly_conflict("source_entry_ids drift")
    if excluded_entries != sorted(excluded_entries, key=lambda item: (item.entry_id, item.reason)):
        raise _monthly_conflict("excluded_entries drift")
    if provider_summaries != sorted(
        provider_summaries, key=lambda item: (item.provider_id, item.currency)
    ):
        raise _monthly_conflict("provider_summaries drift")
    if currency_totals != sorted(currency_totals, key=lambda item: item.currency):
        raise _monthly_conflict("currency_totals drift")
    if policy_ratio_summaries != sorted(
        policy_ratio_summaries,
        key=lambda item: (
            item.policy_id,
            item.currency,
            _ratio_string(item.provider_share_ratio),
            _ratio_string(item.platform_share_ratio),
        ),
    ):
        raise _monthly_conflict("policy_ratio_summaries drift")
    source_entry_ids = sorted(source_entry_ids)
    if row.entry_count != len(source_entry_ids):
        raise _monthly_conflict("entry_count drift")
    if row.provider_count != len({item.provider_id for item in provider_summaries}):
        raise _monthly_conflict("provider_count drift")
    payload = _monthly_checksum_payload(
        tenant_id=row.tenant_id,
        period_month=row.period_month,
        source_entry_ids=source_entry_ids,
        provider_summaries=sorted(
            provider_summaries, key=lambda item: (item.provider_id, item.currency)
        ),
        currency_totals=sorted(currency_totals, key=lambda item: item.currency),
        policy_ratio_summaries=sorted(
            policy_ratio_summaries,
            key=lambda item: (
                item.policy_id,
                item.currency,
                _ratio_string(item.provider_share_ratio),
                _ratio_string(item.platform_share_ratio),
            ),
        ),
        excluded_entries=sorted(excluded_entries, key=lambda item: (item.entry_id, item.reason)),
    )
    if _monthly_checksum(payload) != row.calculation_checksum:
        raise _monthly_conflict("calculation_checksum drift")
    return ProviderMonthlyRevenueShareBatchResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        batch_id=row.batch_id,
        period_month=row.period_month,
        status=_coerce_monthly_status(row.status),
        calculated_at=row.calculated_at,
        entry_count=row.entry_count,
        provider_count=row.provider_count,
        currency_totals=currency_totals,
        provider_summaries=provider_summaries,
        policy_ratio_summaries=policy_ratio_summaries,
        excluded_entries=excluded_entries,
        source_entry_ids=source_entry_ids,
        calculation_checksum=row.calculation_checksum,
        notes_ref=row.notes_ref,
        approved_by_ref=row.approved_by_ref,
        record_version=row.record_version,
        scope_source=_payout_scope_source(row.tenant_id, requested_tenant_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _monthly_batch_response_with_source_validation(
    session: AsyncSession,
    row: ProviderMonthlyRevenueShareBatch,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderMonthlyRevenueShareBatchResponse:
    body = _monthly_batch_response(row, requested_tenant_id=requested_tenant_id)
    await _validate_monthly_batch_source_entries(
        session,
        row,
        source_entry_ids=body.source_entry_ids,
        provider_summaries=body.provider_summaries,
        currency_totals=body.currency_totals,
        policy_ratio_summaries=body.policy_ratio_summaries,
    )
    return body


def _monthly_etag(row: ProviderMonthlyRevenueShareBatch) -> str:
    return f'"{row.batch_id}:{row.record_version}"'


def _set_monthly_etag(response: Response, row: ProviderMonthlyRevenueShareBatch) -> None:
    response.headers["ETag"] = _monthly_etag(row)


def _require_matching_monthly_etag(
    *,
    if_match: str | None,
    row: ProviderMonthlyRevenueShareBatch,
) -> None:
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header required",
        )
    if if_match != _monthly_etag(row):
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="If-Match header does not match current resource version",
        )


def _assert_monthly_status_transition(
    current_status: str,
    next_status: ProviderMonthlyRevenueShareBatchStatus,
    *,
    approved_by_ref: str | None,
) -> bool:
    current = _coerce_monthly_status(current_status)
    if current == next_status:
        return False
    allowed = {
        "draft": {"reviewed", "cancelled"},
        "reviewed": {"approved", "cancelled"},
        "approved": {"exported", "cancelled"},
        "exported": set(),
        "cancelled": set(),
    }
    if next_status not in allowed[current]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid monthly batch status transition: {current} -> {next_status}",
        )
    if next_status in {"approved", "exported"} and approved_by_ref is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="approved_by_ref is required for approved/exported monthly batches",
        )
    return True


def _assert_terminal_monthly_patch_idempotent(
    row: ProviderMonthlyRevenueShareBatch,
    body: ProviderMonthlyRevenueShareBatchStatusPatchRequest,
) -> None:
    if row.status not in {"exported", "cancelled"}:
        return
    if (
        body.status != row.status
        or (body.notes_ref is not None and body.notes_ref != row.notes_ref)
        or (body.approved_by_ref is not None and body.approved_by_ref != row.approved_by_ref)
        or (body.metadata is not None and body.metadata != row.batch_metadata)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{row.status} monthly batch is immutable",
        )


def _assert_monthly_batch_matches_request(
    row: ProviderMonthlyRevenueShareBatch,
    body: ProviderMonthlyRevenueShareBatchUpsertRequest,
    snapshot: dict[str, Any],
) -> None:
    if row.period_month != body.period_month:
        raise _monthly_conflict("monthly batch create conflict: period_month mismatch")
    if row.calculation_checksum != snapshot["calculation_checksum"]:
        raise _monthly_conflict("monthly batch create conflict: checksum mismatch")
    if row.notes_ref != body.notes_ref or row.batch_metadata != body.metadata:
        raise _monthly_conflict("monthly batch create conflict: metadata mismatch")


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


async def _load_version_update_row(
    session: AsyncSession,
    *,
    application_row_id: uuid.UUID,
    version_update_id: str,
    tenant_id: uuid.UUID | None,
) -> ProviderVersionUpdateRequest | None:
    return (
        await session.execute(
            select(ProviderVersionUpdateRequest).where(
                ProviderVersionUpdateRequest.application_row_id == application_row_id,
                ProviderVersionUpdateRequest.version_update_id == version_update_id,
                (
                    ProviderVersionUpdateRequest.tenant_id.is_(None)
                    if tenant_id is None
                    else ProviderVersionUpdateRequest.tenant_id == tenant_id
                ),
            )
        )
    ).scalar_one_or_none()


def _version_conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _coerce_version_status(value: str) -> ProviderVersionUpdateStatus:
    if value not in {"draft", "submitted", "under_review", "approved", "rejected", "cancelled"}:
        raise _version_conflict("version update status drift")
    return cast(ProviderVersionUpdateStatus, value)


def _coerce_version_change_kind(value: str) -> ProviderVersionChangeKind:
    if value not in {"patch", "minor", "major"}:
        raise _version_conflict("version update change_kind drift")
    return cast(ProviderVersionChangeKind, value)


_SEMVER_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def _parse_stored_semver(value: str, *, field_name: str) -> tuple[int, int, int]:
    match = _SEMVER_PATTERN.match(value)
    if not match:
        raise _version_conflict(f"{field_name} drift")
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _validate_stored_version_delta(row: ProviderVersionUpdateRequest) -> None:
    current = _parse_stored_semver(row.current_version, field_name="current_version")
    proposed = _parse_stored_semver(row.proposed_version, field_name="proposed_version")
    if proposed <= current:
        raise _version_conflict("version update semver drift")
    current_major, current_minor, current_patch = current
    proposed_major, proposed_minor, proposed_patch = proposed
    change_kind = _coerce_version_change_kind(row.change_kind)
    if change_kind == "patch":
        valid = (
            proposed_major == current_major
            and proposed_minor == current_minor
            and proposed_patch > current_patch
        )
    elif change_kind == "minor":
        valid = (
            proposed_major == current_major
            and proposed_minor > current_minor
            and proposed_patch == 0
        )
    else:
        valid = proposed_major > current_major and proposed_minor == 0 and proposed_patch == 0
    if not valid:
        raise _version_conflict("version update change_kind drift")


def _validate_version_reference(value: str | None, *, field_name: str) -> None:
    if value is not None and not re.match(r"^(s3|oss|fixture|benchmark|repro)://", value):
        raise _version_conflict(f"{field_name} drift")


def _validate_version_path_id(value: str, *, field_name: str) -> None:
    if not re.match(_PATH_ID_PATTERN, value):
        raise _version_conflict(f"{field_name} drift")


def _require_version_aware_datetime(value: datetime | None, *, field_name: str) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise _version_conflict(f"{field_name} must be timezone-aware")


def _validate_version_update_row(
    row: ProviderVersionUpdateRequest,
    application: ProviderApplication,
    *,
    requested_tenant_id: uuid.UUID | None,
) -> None:
    if row.tenant_id != requested_tenant_id:
        raise _version_conflict("version update tenant scope drift")
    if application.tenant_id != requested_tenant_id:
        raise _version_conflict("version update application scope drift")
    if row.application_row_id != application.id or row.application_id != application.application_id:
        raise _version_conflict("version update application drift")
    if row.requested_provider_id != application.requested_provider_id:
        raise _version_conflict("version update requested_provider_id drift")
    _validate_version_path_id(row.application_id, field_name="application_id")
    _validate_version_path_id(row.version_update_id, field_name="version_update_id")
    _validate_version_path_id(row.requested_provider_id, field_name="requested_provider_id")
    _validate_stored_version_delta(row)
    _coerce_version_status(row.status)
    if not re.match(r"^https?://", row.openapi_url):
        raise _version_conflict("openapi_url drift")
    if not re.match(r"^[0-9a-fA-F]{64}$", row.openapi_sha256):
        raise _version_conflict("openapi_sha256 drift")
    if not re.search(r"sha256:[0-9a-fA-F]{64}", row.image_digest):
        raise _version_conflict("image_digest drift")
    if not isinstance(row.cosign_bundle, dict):
        raise _version_conflict("cosign_bundle drift")
    if not isinstance(row.update_metadata, dict):
        raise _version_conflict("metadata drift")
    try:
        _reject_forbidden_reference_fields(row.cosign_bundle)
        _reject_forbidden_reference_fields(row.update_metadata)
    except ValueError as exc:
        raise _version_conflict("version update unsafe metadata drift") from exc
    _validate_version_reference(row.sbom_ref, field_name="sbom_ref")
    _validate_version_reference(row.release_notes_ref, field_name="release_notes_ref")
    _validate_version_reference(row.review_notes_ref, field_name="review_notes_ref")
    _require_version_aware_datetime(row.submitted_at, field_name="submitted_at")
    _require_version_aware_datetime(row.reviewed_at, field_name="reviewed_at")
    _require_version_aware_datetime(row.created_at, field_name="created_at")
    _require_version_aware_datetime(row.updated_at, field_name="updated_at")
    if row.record_version < 1:
        raise _version_conflict("record_version drift")


def _version_scope_source(
    row_tenant_id: uuid.UUID | None,
    requested_tenant_id: uuid.UUID | None,
) -> ProviderDashboardScopeSource:
    if row_tenant_id is None and requested_tenant_id is None:
        return "global"
    if row_tenant_id == requested_tenant_id and requested_tenant_id is not None:
        return "tenant"
    raise _version_conflict("version update cannot use global fallback scope")


def _version_etag(row: ProviderVersionUpdateRequest) -> str:
    return f'"{row.version_update_id}:{row.record_version}"'


def _set_version_etag(response: Response, row: ProviderVersionUpdateRequest) -> None:
    response.headers["ETag"] = _version_etag(row)


def _require_matching_etag(
    *,
    if_match: str | None,
    row: ProviderVersionUpdateRequest,
) -> None:
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header required",
        )
    if if_match != _version_etag(row):
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="If-Match header does not match current resource version",
        )


async def _lock_version_update_row(
    session: AsyncSession,
    row: ProviderVersionUpdateRequest,
) -> ProviderVersionUpdateRequest:
    locked = (
        await session.execute(
            select(ProviderVersionUpdateRequest)
            .where(ProviderVersionUpdateRequest.id == row.id)
            .with_for_update()
        )
    ).scalar_one()
    return locked


def _version_update_response(
    row: ProviderVersionUpdateRequest,
    application: ProviderApplication,
    *,
    requested_tenant_id: uuid.UUID | None,
    response: Response | None,
) -> ProviderVersionUpdateResponse:
    _validate_version_update_row(row, application, requested_tenant_id=requested_tenant_id)
    if response is not None:
        _set_version_etag(response, row)
    return ProviderVersionUpdateResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        application_id=row.application_id,
        version_update_id=row.version_update_id,
        requested_provider_id=row.requested_provider_id,
        current_version=row.current_version,
        proposed_version=row.proposed_version,
        change_kind=_coerce_version_change_kind(row.change_kind),
        openapi_url=row.openapi_url,
        openapi_sha256=row.openapi_sha256,
        image_digest=row.image_digest,
        cosign_bundle=dict(row.cosign_bundle),
        sbom_ref=row.sbom_ref,
        release_notes_ref=row.release_notes_ref,
        status=_coerce_version_status(row.status),
        review_notes_ref=row.review_notes_ref,
        submitted_at=row.submitted_at,
        reviewed_at=row.reviewed_at,
        record_version=row.record_version,
        metadata=dict(row.update_metadata),
        scope_source=_version_scope_source(row.tenant_id, requested_tenant_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _version_material_values(body: ProviderVersionUpdateUpsertRequest) -> dict[str, Any]:
    return {
        "current_version": body.current_version,
        "proposed_version": body.proposed_version,
        "change_kind": body.change_kind,
        "openapi_url": body.openapi_url,
        "openapi_sha256": body.openapi_sha256,
        "image_digest": body.image_digest,
        "cosign_bundle": body.cosign_bundle,
        "sbom_ref": body.sbom_ref,
        "release_notes_ref": body.release_notes_ref,
    }


def _assert_submitted_version_material_unchanged(
    row: ProviderVersionUpdateRequest,
    body: ProviderVersionUpdateUpsertRequest,
) -> None:
    if row.status == "draft":
        return
    existing = {
        "current_version": row.current_version,
        "proposed_version": row.proposed_version,
        "change_kind": row.change_kind,
        "openapi_url": row.openapi_url,
        "openapi_sha256": row.openapi_sha256,
        "image_digest": row.image_digest,
        "cosign_bundle": dict(row.cosign_bundle),
        "sbom_ref": row.sbom_ref,
        "release_notes_ref": row.release_notes_ref,
    }
    incoming = _version_material_values(body)
    changed = sorted(key for key, value in incoming.items() if existing[key] != value)
    if changed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{row.status} version update fields are immutable: {', '.join(changed)}",
        )


def _assert_version_status_transition(
    current_status: str,
    next_status: ProviderVersionUpdateStatus,
    *,
    review_notes_ref: str | None,
) -> bool:
    current = _coerce_version_status(current_status)
    if current == next_status:
        return False
    allowed: dict[str, set[str]] = {
        "draft": {"submitted", "cancelled"},
        "submitted": {"under_review", "cancelled"},
        "under_review": {"approved", "rejected", "cancelled"},
        "approved": set(),
        "rejected": set(),
        "cancelled": set(),
    }
    if next_status not in allowed[current]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid version update status transition: {current} -> {next_status}",
        )
    if next_status in {"approved", "rejected"} and review_notes_ref is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="review_notes_ref is required for approved or rejected status",
        )
    return True


def _assert_terminal_version_patch_idempotent(
    row: ProviderVersionUpdateRequest,
    body: ProviderVersionUpdateStatusPatchRequest,
) -> None:
    if row.status not in {"approved", "rejected", "cancelled"}:
        return
    if (
        body.status != row.status
        or body.review_notes_ref != row.review_notes_ref
        or body.metadata != dict(row.update_metadata)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{row.status} version update is immutable",
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
    "/revenue-share/payout-entries/{entry_id}",
    response_model=ProviderRevenuePayoutEntryResponse,
    tags=["revenue-share"],
)
async def upsert_provider_revenue_payout_entry(
    entry_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    body: ProviderRevenuePayoutEntryUpsertRequest,
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> ProviderRevenuePayoutEntryResponse:
    _require_write_auth(x_internal_service_auth)
    _assert_path_id(body.entry_id, entry_id, "entry_id")
    row = await _load_payout_entry_row(
        session,
        entry_id=entry_id,
        tenant_id=body.tenant_id,
    )
    now = datetime.now(UTC)
    if row is not None:
        references = await _load_payout_entry_references(session, [row])
        _validate_payout_entry(row, references)
        _assert_payout_entry_material_unchanged(row, body)
        _assert_payout_status_transition(row.status, body.status)
        row.status = body.status
        row.entry_metadata = body.metadata
        row.updated_at = now
        await session.flush()
        return await _payout_entry_response(
            session,
            row,
            requested_tenant_id=body.tenant_id,
        )

    hook = await _load_revenue_hook_by_id_exact_scope(
        session,
        hook_id=body.hook_id,
        tenant_id=body.tenant_id,
    )
    if hook is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="hook not found"
        )
    existing_for_hook = await _load_payout_entry_by_hook(session, hook_id=body.hook_id)
    if existing_for_hook is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="payout entry already exists for hook",
        )
    policy = await _load_revenue_policy_row(
        session,
        policy_id=hook.policy_id,
        tenant_id=hook.tenant_id,
        allow_global_fallback=hook.tenant_id is not None,
    )
    if policy is None:
        raise _payout_conflict("policy not found for payout entry")
    platform_ratio = _coerce_ratio(policy.platform_share_ratio, field_name="platform_share_ratio")
    provider_ratio = _coerce_ratio(policy.provider_share_ratio, field_name="provider_share_ratio")
    if platform_ratio + provider_ratio != Decimal("1.000000"):
        raise _payout_conflict("policy ratio drift")
    row = ProviderRevenuePayoutEntry(
        tenant_id=body.tenant_id,
        entry_id=entry_id,
        hook_row_id=hook.id,
        provider_id=hook.provider_id,
        k_algo=hook.k_algo,
        policy_id=hook.policy_id,
        source_service=hook.source_service,
        source_event_id=hook.source_event_id,
        period_month=hook.period_month,
        currency=body.currency,
        gross_amount=body.gross_amount,
        platform_share_ratio=platform_ratio,
        provider_share_ratio=provider_ratio,
        status=body.status,
        recognized_at=body.recognized_at,
        entry_metadata=body.metadata,
        created_at=now,
        updated_at=now,
    )
    try:
        async with session.begin_nested():
            session.add(row)
            await session.flush()
    except IntegrityError as exc:
        existing = await _load_payout_entry_row(
            session,
            entry_id=entry_id,
            tenant_id=body.tenant_id,
        )
        if existing is not None:
            references = await _load_payout_entry_references(session, [existing])
            _validate_payout_entry(existing, references)
            _assert_payout_entry_material_unchanged(existing, body)
            _assert_payout_status_transition(existing.status, body.status)
            existing.status = body.status
            existing.entry_metadata = body.metadata
            existing.updated_at = now
            await session.flush()
            return await _payout_entry_response(
                session,
                existing,
                requested_tenant_id=body.tenant_id,
            )
        existing_for_hook = await _load_payout_entry_by_hook(session, hook_id=body.hook_id)
        if existing_for_hook is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="payout entry already exists for hook",
            ) from exc
        raise
    return await _payout_entry_response(session, row, requested_tenant_id=body.tenant_id)


@router.get(
    "/revenue-share/payout-entries/{entry_id}",
    response_model=ProviderRevenuePayoutEntryResponse,
    tags=["revenue-share"],
)
async def get_provider_revenue_payout_entry(
    entry_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> ProviderRevenuePayoutEntryResponse:
    row = await _load_payout_entry_row(session, entry_id=entry_id, tenant_id=tenant_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payout entry not found")
    return await _payout_entry_response(session, row, requested_tenant_id=tenant_id)


@router.get(
    "/revenue-share/payout-entries",
    response_model=list[ProviderRevenuePayoutEntryResponse],
    tags=["revenue-share"],
)
async def list_provider_revenue_payout_entries(
    tenant_id: uuid.UUID | None = Query(default=None),
    provider_id: Annotated[str | None, Query(pattern=_PATH_ID_PATTERN)] = None,
    period_month: Annotated[str | None, Query(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")] = None,
    status_filter: ProviderRevenuePayoutEntryStatus | None = Query(default=None, alias="status"),
    currency: Annotated[str | None, Query(pattern=r"^[A-Z]{3}$")] = None,
    session: AsyncSession = Depends(get_session),
) -> list[ProviderRevenuePayoutEntryResponse]:
    conditions: list[ColumnElement[bool]] = [
        (
            ProviderRevenuePayoutEntry.tenant_id.is_(None)
            if tenant_id is None
            else ProviderRevenuePayoutEntry.tenant_id == tenant_id
        )
    ]
    if provider_id is not None:
        conditions.append(ProviderRevenuePayoutEntry.provider_id == provider_id)
    if period_month is not None:
        conditions.append(ProviderRevenuePayoutEntry.period_month == period_month)
    if status_filter is not None:
        conditions.append(ProviderRevenuePayoutEntry.status == status_filter)
    if currency is not None:
        conditions.append(ProviderRevenuePayoutEntry.currency == currency)
    rows = list(
        (
            await session.execute(
                select(ProviderRevenuePayoutEntry)
                .where(*conditions)
                .order_by(
                    ProviderRevenuePayoutEntry.recognized_at.desc(),
                    ProviderRevenuePayoutEntry.entry_id,
                )
            )
        ).scalars()
    )
    references = await _load_payout_entry_references(session, rows)
    return [
        _validated_payout_entry_response(row, references, requested_tenant_id=tenant_id)
        for row in rows
    ]


@router.put(
    "/revenue-share/monthly-batches/{batch_id}",
    response_model=ProviderMonthlyRevenueShareBatchResponse,
    tags=["revenue-share"],
)
async def upsert_provider_monthly_revenue_share_batch(
    batch_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    body: ProviderMonthlyRevenueShareBatchUpsertRequest,
    response: Response,
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> ProviderMonthlyRevenueShareBatchResponse:
    _require_write_auth(x_internal_service_auth)
    _assert_path_id(body.batch_id, batch_id, "batch_id")
    snapshot = await _calculate_monthly_batch_snapshot(
        session,
        tenant_id=body.tenant_id,
        period_month=body.period_month,
        allow_drift_exclusions=body.allow_drift_exclusions,
    )
    now = datetime.now(UTC)
    row = await _load_monthly_batch_row(session, batch_id=batch_id, tenant_id=body.tenant_id)
    if row is None:
        row = ProviderMonthlyRevenueShareBatch(
            tenant_id=body.tenant_id,
            batch_id=batch_id,
            period_month=body.period_month,
            status="draft",
            calculated_at=now,
            notes_ref=body.notes_ref,
            batch_metadata=body.metadata,
            record_version=1,
            created_at=now,
            updated_at=now,
            **snapshot,
        )
        try:
            async with session.begin_nested():
                session.add(row)
                await session.flush()
        except IntegrityError as exc:
            existing = await _load_monthly_batch_row(
                session,
                batch_id=batch_id,
                tenant_id=body.tenant_id,
            )
            if existing is None:
                raise _monthly_conflict("monthly batch create conflict") from exc
            _assert_monthly_batch_matches_request(existing, body, snapshot)
            response_body = await _monthly_batch_response_with_source_validation(
                session,
                existing,
                requested_tenant_id=body.tenant_id,
            )
            _set_monthly_etag(response, existing)
            return response_body
    else:
        row = await _lock_monthly_batch_row(session, row)
        _validate_monthly_batch_json(row)
        if row.period_month != body.period_month:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="period_month is immutable for monthly batch",
            )
        changed_snapshot = row.calculation_checksum != snapshot["calculation_checksum"]
        if row.status != "draft":
            if changed_snapshot:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="non-draft monthly batch snapshot is immutable",
                )
            if row.notes_ref != body.notes_ref or row.batch_metadata != body.metadata:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="non-draft monthly batch metadata is immutable",
                )
        elif (
            changed_snapshot
            or row.notes_ref != body.notes_ref
            or row.batch_metadata != body.metadata
        ):
            row.entry_count = snapshot["entry_count"]
            row.provider_count = snapshot["provider_count"]
            row.currency_totals = snapshot["currency_totals"]
            row.provider_summaries = snapshot["provider_summaries"]
            row.policy_ratio_summaries = snapshot["policy_ratio_summaries"]
            row.excluded_entries = snapshot["excluded_entries"]
            row.source_entry_ids = snapshot["source_entry_ids"]
            row.calculation_checksum = snapshot["calculation_checksum"]
            row.notes_ref = body.notes_ref
            row.batch_metadata = body.metadata
            row.calculated_at = now
            row.updated_at = now
            row.record_version += 1
            await session.flush()
    response_body = await _monthly_batch_response_with_source_validation(
        session,
        row,
        requested_tenant_id=body.tenant_id,
    )
    _set_monthly_etag(response, row)
    return response_body


@router.get(
    "/revenue-share/monthly-batches/{batch_id}",
    response_model=ProviderMonthlyRevenueShareBatchResponse,
    tags=["revenue-share"],
)
async def get_provider_monthly_revenue_share_batch(
    batch_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    response: Response,
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> ProviderMonthlyRevenueShareBatchResponse:
    row = await _load_monthly_batch_row(session, batch_id=batch_id, tenant_id=tenant_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="monthly batch not found")
    body = await _monthly_batch_response_with_source_validation(
        session,
        row,
        requested_tenant_id=tenant_id,
    )
    _set_monthly_etag(response, row)
    return body


@router.get(
    "/revenue-share/monthly-batches",
    response_model=list[ProviderMonthlyRevenueShareBatchResponse],
    tags=["revenue-share"],
)
async def list_provider_monthly_revenue_share_batches(
    tenant_id: uuid.UUID | None = Query(default=None),
    period_month: Annotated[str | None, Query(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")] = None,
    status_filter: ProviderMonthlyRevenueShareBatchStatus | None = Query(
        default=None,
        alias="status",
    ),
    currency: Annotated[str | None, Query(pattern=r"^[A-Z]{3}$")] = None,
    session: AsyncSession = Depends(get_session),
) -> list[ProviderMonthlyRevenueShareBatchResponse]:
    conditions: list[ColumnElement[bool]] = [
        (
            ProviderMonthlyRevenueShareBatch.tenant_id.is_(None)
            if tenant_id is None
            else ProviderMonthlyRevenueShareBatch.tenant_id == tenant_id
        )
    ]
    if period_month is not None:
        conditions.append(ProviderMonthlyRevenueShareBatch.period_month == period_month)
    if status_filter is not None:
        conditions.append(ProviderMonthlyRevenueShareBatch.status == status_filter)
    rows = list(
        (
            await session.execute(
                select(ProviderMonthlyRevenueShareBatch)
                .where(*conditions)
                .order_by(
                    ProviderMonthlyRevenueShareBatch.period_month.desc(),
                    ProviderMonthlyRevenueShareBatch.calculated_at.desc(),
                    ProviderMonthlyRevenueShareBatch.batch_id,
                )
            )
        ).scalars()
    )
    responses = [
        await _monthly_batch_response_with_source_validation(
            session,
            row,
            requested_tenant_id=tenant_id,
        )
        for row in rows
    ]
    if currency is not None:
        responses = [
            item
            for item in responses
            if any(total.currency == currency for total in item.currency_totals)
        ]
    return responses


@router.patch(
    "/revenue-share/monthly-batches/{batch_id}/status",
    response_model=ProviderMonthlyRevenueShareBatchResponse,
    tags=["revenue-share"],
)
async def patch_provider_monthly_revenue_share_batch_status(
    batch_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    body: ProviderMonthlyRevenueShareBatchStatusPatchRequest,
    response: Response,
    tenant_id: uuid.UUID | None = Query(default=None),
    if_match: str | None = Header(default=None, alias="If-Match"),
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> ProviderMonthlyRevenueShareBatchResponse:
    _require_write_auth(x_internal_service_auth)
    row = await _load_monthly_batch_row(session, batch_id=batch_id, tenant_id=tenant_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="monthly batch not found")
    row = await _lock_monthly_batch_row(session, row)
    _require_matching_monthly_etag(if_match=if_match, row=row)
    _assert_terminal_monthly_patch_idempotent(row, body)
    transitioned = _assert_monthly_status_transition(
        row.status,
        body.status,
        approved_by_ref=body.approved_by_ref or row.approved_by_ref,
    )
    changed_refs = (
        (body.notes_ref is not None and body.notes_ref != row.notes_ref)
        or (body.approved_by_ref is not None and body.approved_by_ref != row.approved_by_ref)
        or (body.metadata is not None and body.metadata != row.batch_metadata)
    )
    if transitioned or changed_refs:
        row.status = body.status
        if body.notes_ref is not None:
            row.notes_ref = body.notes_ref
        if body.approved_by_ref is not None:
            row.approved_by_ref = body.approved_by_ref
        if body.metadata is not None:
            row.batch_metadata = body.metadata
        row.updated_at = datetime.now(UTC)
        row.record_version += 1
        await session.flush()
    body_response = await _monthly_batch_response_with_source_validation(
        session,
        row,
        requested_tenant_id=tenant_id,
    )
    _set_monthly_etag(response, row)
    return body_response


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


@router.put(
    "/provider-applications/{application_id}/version-updates/{version_update_id}",
    response_model=ProviderVersionUpdateResponse,
    tags=["provider-version-updates"],
)
async def upsert_provider_version_update(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    version_update_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    body: ProviderVersionUpdateUpsertRequest,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> ProviderVersionUpdateResponse:
    _require_write_auth(x_internal_service_auth)
    _assert_path_id(body.application_id, application_id, "application_id")
    _assert_path_id(body.version_update_id, version_update_id, "version_update_id")
    application = await _load_provider_application_row(
        session,
        application_id=application_id,
        tenant_id=body.tenant_id,
        allow_global_fallback=False,
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider application not found",
        )
    if application.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="provider application must be submitted before version update",
        )
    row = await _load_version_update_row(
        session,
        application_row_id=application.id,
        version_update_id=version_update_id,
        tenant_id=body.tenant_id,
    )
    now = datetime.now(UTC)
    if row is None:
        submitted_at = now if body.status == "submitted" else None
        row = ProviderVersionUpdateRequest(
            tenant_id=body.tenant_id,
            application_row_id=application.id,
            application_id=application.application_id,
            version_update_id=version_update_id,
            requested_provider_id=application.requested_provider_id,
            current_version=body.current_version,
            proposed_version=body.proposed_version,
            change_kind=body.change_kind,
            openapi_url=body.openapi_url,
            openapi_sha256=body.openapi_sha256,
            image_digest=body.image_digest,
            cosign_bundle=body.cosign_bundle,
            sbom_ref=body.sbom_ref,
            release_notes_ref=body.release_notes_ref,
            status=body.status,
            submitted_at=submitted_at,
            record_version=1,
            update_metadata=body.metadata,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row = await _lock_version_update_row(session, row)
        _validate_version_update_row(row, application, requested_tenant_id=body.tenant_id)
        _require_matching_etag(if_match=if_match, row=row)
        _assert_submitted_version_material_unchanged(row, body)
        changed = any(
            getattr(row, key) != value for key, value in _version_material_values(body).items()
        )
        changed = changed or row.status != body.status or dict(row.update_metadata) != body.metadata
        if row.status != body.status:
            transitioned = _assert_version_status_transition(
                row.status,
                cast(ProviderVersionUpdateStatus, body.status),
                review_notes_ref=row.review_notes_ref,
            )
            if transitioned and body.status == "submitted":
                row.submitted_at = row.submitted_at or now
        if changed:
            row.current_version = body.current_version
            row.proposed_version = body.proposed_version
            row.change_kind = body.change_kind
            row.openapi_url = body.openapi_url
            row.openapi_sha256 = body.openapi_sha256
            row.image_digest = body.image_digest
            row.cosign_bundle = body.cosign_bundle
            row.sbom_ref = body.sbom_ref
            row.release_notes_ref = body.release_notes_ref
            row.status = body.status
            row.update_metadata = body.metadata
            row.record_version += 1
            row.updated_at = now
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="provider version update identity already exists",
        ) from exc
    return _version_update_response(
        row,
        application,
        requested_tenant_id=body.tenant_id,
        response=response,
    )


@router.get(
    "/provider-applications/{application_id}/version-updates/{version_update_id}",
    response_model=ProviderVersionUpdateResponse,
    tags=["provider-version-updates"],
)
async def get_provider_version_update(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    version_update_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    response: Response,
    tenant_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> ProviderVersionUpdateResponse:
    application = await _load_provider_application_row(
        session,
        application_id=application_id,
        tenant_id=tenant_id,
        allow_global_fallback=False,
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider application not found",
        )
    row = await _load_version_update_row(
        session,
        application_row_id=application.id,
        version_update_id=version_update_id,
        tenant_id=tenant_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider version update not found",
        )
    return _version_update_response(
        row,
        application,
        requested_tenant_id=tenant_id,
        response=response,
    )


@router.get(
    "/provider-applications/{application_id}/version-updates",
    response_model=list[ProviderVersionUpdateResponse],
    tags=["provider-version-updates"],
)
async def list_provider_version_updates(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    requested_provider_id: Annotated[str | None, Query(pattern=_PATH_ID_PATTERN)] = None,
    status_filter: ProviderVersionUpdateStatus | None = Query(default=None, alias="status"),
    change_kind: ProviderVersionChangeKind | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[ProviderVersionUpdateResponse]:
    application = await _load_provider_application_row(
        session,
        application_id=application_id,
        tenant_id=tenant_id,
        allow_global_fallback=False,
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider application not found",
        )
    conditions: list[ColumnElement[bool]] = [
        ProviderVersionUpdateRequest.application_row_id == application.id,
        (
            ProviderVersionUpdateRequest.tenant_id.is_(None)
            if tenant_id is None
            else ProviderVersionUpdateRequest.tenant_id == tenant_id
        ),
    ]
    if requested_provider_id is not None:
        conditions.append(
            ProviderVersionUpdateRequest.requested_provider_id == requested_provider_id
        )
    if status_filter is not None:
        conditions.append(ProviderVersionUpdateRequest.status == status_filter)
    if change_kind is not None:
        conditions.append(ProviderVersionUpdateRequest.change_kind == change_kind)
    rows = list(
        (
            await session.execute(
                select(ProviderVersionUpdateRequest)
                .where(*conditions)
                .order_by(
                    ProviderVersionUpdateRequest.created_at.desc(),
                    ProviderVersionUpdateRequest.version_update_id,
                )
            )
        ).scalars()
    )
    return [
        _version_update_response(
            row,
            application,
            requested_tenant_id=tenant_id,
            response=None,
        )
        for row in rows
    ]


@router.patch(
    "/provider-applications/{application_id}/version-updates/{version_update_id}/status",
    response_model=ProviderVersionUpdateResponse,
    tags=["provider-version-updates"],
)
async def patch_provider_version_update_status(
    application_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    version_update_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    body: ProviderVersionUpdateStatusPatchRequest,
    response: Response,
    tenant_id: uuid.UUID | None = Query(default=None),
    if_match: str | None = Header(default=None, alias="If-Match"),
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    session: AsyncSession = Depends(get_session),
) -> ProviderVersionUpdateResponse:
    _require_write_auth(x_internal_service_auth)
    application = await _load_provider_application_row(
        session,
        application_id=application_id,
        tenant_id=tenant_id,
        allow_global_fallback=False,
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider application not found",
        )
    row = await _load_version_update_row(
        session,
        application_row_id=application.id,
        version_update_id=version_update_id,
        tenant_id=tenant_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider version update not found",
        )
    row = await _lock_version_update_row(session, row)
    _validate_version_update_row(row, application, requested_tenant_id=tenant_id)
    _require_matching_etag(if_match=if_match, row=row)
    _assert_terminal_version_patch_idempotent(row, body)
    transitioned = _assert_version_status_transition(
        row.status,
        body.status,
        review_notes_ref=body.review_notes_ref,
    )
    if (
        transitioned
        or body.review_notes_ref != row.review_notes_ref
        or body.metadata != row.update_metadata
    ):
        now = datetime.now(UTC)
        row.status = body.status
        if body.status == "submitted":
            row.submitted_at = row.submitted_at or now
        if body.status in {"approved", "rejected"}:
            row.reviewed_at = row.reviewed_at or now
        row.review_notes_ref = body.review_notes_ref
        row.update_metadata = body.metadata
        row.record_version += 1
        row.updated_at = now
        await session.flush()
    return _version_update_response(
        row,
        application,
        requested_tenant_id=tenant_id,
        response=response,
    )


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


@router.get(
    "/providers/{provider_id}/revenue-payout-dashboard",
    response_model=ProviderRevenuePayoutDashboardResponse,
    tags=["provider-revenue-payout-dashboard"],
)
async def get_provider_revenue_payout_dashboard(
    provider_id: Annotated[str, Path(pattern=_PATH_ID_PATTERN)],
    tenant_id: uuid.UUID | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    period_month: Annotated[str | None, Query(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")] = None,
    status_filter: ProviderRevenuePayoutEntryStatus | None = Query(default=None, alias="status"),
    k_algo: Annotated[str | None, Query(pattern=_PATH_ID_PATTERN)] = None,
    currency: Annotated[str | None, Query(pattern=r"^[A-Z]{3}$")] = None,
    session: AsyncSession = Depends(get_session),
) -> ProviderRevenuePayoutDashboardResponse:
    if from_at is not None:
        _require_aware_datetime(from_at, field_name="from")
    if to_at is not None:
        _require_aware_datetime(to_at, field_name="to")
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="from must be before or equal to to",
        )

    conditions: list[ColumnElement[bool]] = [
        ProviderRevenuePayoutEntry.provider_id == provider_id,
        (
            ProviderRevenuePayoutEntry.tenant_id.is_(None)
            if tenant_id is None
            else ProviderRevenuePayoutEntry.tenant_id == tenant_id
        ),
    ]
    if period_month is not None:
        conditions.append(ProviderRevenuePayoutEntry.period_month == period_month)
    if status_filter is not None:
        conditions.append(ProviderRevenuePayoutEntry.status == status_filter)
    if k_algo is not None:
        conditions.append(ProviderRevenuePayoutEntry.k_algo == k_algo)
    if currency is not None:
        conditions.append(ProviderRevenuePayoutEntry.currency == currency)
    if from_at is not None:
        conditions.append(ProviderRevenuePayoutEntry.recognized_at >= from_at)
    if to_at is not None:
        conditions.append(ProviderRevenuePayoutEntry.recognized_at <= to_at)

    payout_rows = list(
        (
            await session.execute(
                select(ProviderRevenuePayoutEntry)
                .where(*conditions)
                .order_by(
                    ProviderRevenuePayoutEntry.recognized_at.desc(),
                    ProviderRevenuePayoutEntry.entry_id,
                )
            )
        ).scalars()
    )
    references = await _load_payout_entry_references(session, payout_rows)
    responses = [
        _validated_payout_entry_response(row, references, requested_tenant_id=tenant_id)
        for row in payout_rows
    ]
    rows = [_payout_entry_row_from_response(response) for response in responses]
    return ProviderRevenuePayoutDashboardResponse(
        provider_id=provider_id,
        tenant_id=tenant_id,
        from_at=from_at,
        to_at=to_at,
        period_month=period_month,
        status=status_filter,
        k_algo=k_algo,
        currency=currency,
        status_counts=_payout_status_counts(rows),
        total_entries=len(rows),
        currency_totals=_payout_currency_totals(rows),
        period_summaries=_payout_period_summaries(rows),
        entries=rows,
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
