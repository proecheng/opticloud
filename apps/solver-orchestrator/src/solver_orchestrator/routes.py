"""Endpoints — FR C1-C8 + E1-E10 (Sprint 0 subset: Story 2.1 + 3.1)."""

from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from opticloud_shared.cost_telemetry import CostTelemetryEvent, CostUnit, record_cost_event
from opticloud_shared.schemas.errors import ErrorDetail, ErrorResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from solver_orchestrator import billing_client, solvers
from solver_orchestrator.auth import require_scope, verify_api_key
from solver_orchestrator.catalog import (
    CATALOG,
    Citation,
    IPAttribution,
    find_by_k_algo,
    publishable_catalog_items,
    self_audit_passed,
)
from solver_orchestrator.db import get_session
from solver_orchestrator.fallback_execution import (
    FallbackAttempt,
    FallbackAttemptPlan,
    FallbackPlanStatus,
    attempt_route_metadata,
    build_fallback_attempts,
    build_fallback_execution_metadata,
    fallback_attempt_to_metadata,
    is_retryable_solver_result,
)
from solver_orchestrator.forecasting import predict_quantiles
from solver_orchestrator.models import (
    CostAttribution,
    IdempotencyKey,
    Optimization,
    Prediction,
    PredictionIdempotencyKey,
    ReproductionVoucher,
)
from solver_orchestrator.provider_routing import (
    ProviderRouteResult,
    ProviderRouteStatus,
    provider_route_to_system_metadata,
    select_provider_route,
)
from solver_orchestrator.repro import (
    VOUCHER_ID_PATTERN,
    attach_existing_voucher_id,
    build_rerun_lineage_payload,
    get_reproduction_voucher,
    get_reproduction_voucher_by_pk,
    issue_reproduction_voucher,
)
from solver_orchestrator.schemas import (
    AlgorithmSchema,
    CitationSchema,
    IPAttributionSchema,
    ModelVersionSchema,
    OptimizationRequest,
    OptimizationResponse,
    PredictionDisclaimer,
    PredictionQuantiles,
    PredictionRequest,
    PredictionResponse,
    ReproducibilitySchema,
)

router = APIRouter(prefix="/v1")
health_router = APIRouter()
logger: Any = structlog.get_logger("solver_orchestrator.routes")


# ===== Story 0.7: Health =====


@health_router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@health_router.get("/readyz")
async def readyz(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    try:
        await session.execute(select(1))
        return {"status": "ready", "deps": {"db": "ok"}}
    except Exception as e:
        return {"status": "not-ready", "deps": {"db": f"error: {type(e).__name__}"}}


# ===== Story 2.1: Algorithms catalog (FR C1, no auth) =====


@router.get(
    "/algorithms",
    response_model=list[AlgorithmSchema],
    tags=["catalog"],
    summary="列出所有支持的算法（公开免鉴权 FR C1 + C3）",
    description=(
        "FR C1 + C3: 任何访客 can list algorithms via `GET /v1/algorithms`.\n\n"
        "Optional filters (combinable):\n"
        "- `task_type=lp` — exact match\n"
        "- `tier=T1` or `tier=T1,P2` — comma-separated multi-tier OR\n\n"
        "Unknown filter values return an empty list (permissive, no 422)."
    ),
)
async def list_algorithms(
    task_type: str | None = None,
    tier: str | None = None,
) -> list[AlgorithmSchema]:
    """FR C1 + C3 — public algorithm list, optional task_type + tier filters."""
    items = publishable_catalog_items()
    if task_type:
        items = [a for a in items if a["task_type"] == task_type]
    if tier:
        wanted = {t.strip() for t in tier.split(",") if t.strip()}
        if wanted:
            items = [a for a in items if a["tier"] in wanted]
    return [AlgorithmSchema.model_validate(a) for a in items]


@router.get(
    "/algorithms/{k_algo}",
    response_model=AlgorithmSchema,
    tags=["catalog"],
    summary="算法详情 (FR C2)",
)
async def get_algorithm(k_algo: str) -> AlgorithmSchema:
    """FR C2 — algorithm details by k_algo."""
    algo = find_by_k_algo(k_algo)
    if algo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown k_algo: {k_algo}"
        )
    if not self_audit_passed(algo):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"k_algo is not published: {k_algo}"
        )
    return AlgorithmSchema.model_validate(algo)


# ===== Story 3.1: POST /v1/optimizations =====


def _hash_body(body: dict) -> str:  # type: ignore[type-arg]
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _hash_rerun_request(voucher_id: str) -> str:
    canon = json.dumps(
        {"voucher_id": voucher_id},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


_RERUN_BODY_NOT_EMPTY = object()


def _model_json_dict(model_json: str) -> dict[str, object]:
    payload = json.loads(model_json)
    if not isinstance(payload, dict):
        raise ValueError("model JSON did not encode an object")
    return payload


def _build_reproducibility_payload(
    *,
    request_body: dict,  # type: ignore[type-arg]
    model_version: dict,  # type: ignore[type-arg]
    locked_solver: str,
    anonymous: bool = False,
) -> dict[str, object]:
    """Story 6.B.1 — build the opt-in reproducibility handoff.

    The fingerprint is computed from the original request body before any
    `_system` metadata is attached, so it remains stable for later voucher
    minting.
    """
    payload = ReproducibilitySchema(
        requested=True,
        request_fingerprint=f"sha256:{_hash_body(request_body)}",
        locked_model_version=ModelVersionSchema.model_validate(model_version),
        locked_solver=locked_solver,
        seed_locked=True,
        seed=None,
        anonymous=True if anonymous else None,
    )
    result = _model_json_dict(payload.model_dump_json())
    if not anonymous:
        result.pop("anonymous", None)
    return result


def _anonymous_without_reproducible_error(*, request_id: str | None = None) -> JSONResponse:
    return _rfc7807_error(
        title="Invalid Anonymous Option",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="options.anonymous requires options.reproducible=true",
        errors=[
            ErrorDetail(
                field_path="options.anonymous",
                value=True,
                constraint="requires options.reproducible=true",
                remediation_hint_key="errors.422.anonymous_requires_reproducible",
            )
        ],
        request_id=request_id,
    )


def _add_calendar_years_utc(value: datetime, years: int) -> datetime:
    value_utc = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    value_utc = value_utc.astimezone(UTC)
    try:
        return value_utc.replace(year=value_utc.year + years)
    except ValueError:
        if value_utc.month == 2 and value_utc.day == 29:
            return value_utc.replace(year=value_utc.year + years, month=2, day=28)
        raise


def _voucher_expiry_utc(created_at: datetime) -> datetime:
    return _add_calendar_years_utc(created_at, 5)


def _is_rerun_voucher_expired(created_at: datetime, *, now: datetime | None = None) -> bool:
    now_utc = now if now is not None else datetime.now(UTC)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=UTC)
    else:
        now_utc = now_utc.astimezone(UTC)
    return now_utc >= _voucher_expiry_utc(created_at)


def _strip_system_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    clean = dict(payload)
    clean.pop("_system", None)
    return clean


async def _load_owner_visible_voucher(
    session: AsyncSession, *, voucher_id: str, user_id: uuid.UUID
) -> ReproductionVoucher | None:
    result = await session.execute(
        select(ReproductionVoucher).where(
            ReproductionVoucher.voucher_id == voucher_id,
            ReproductionVoucher.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _load_source_optimization_for_voucher(
    session: AsyncSession,
    *,
    voucher: ReproductionVoucher,
    user_id: uuid.UUID,
) -> Optimization | None:
    opt = await session.get(Optimization, voucher.optimization_id)
    if opt is None or opt.user_id != user_id or opt.status != "completed":
        return None
    return opt


def _build_response_content(opt: Optimization) -> dict[str, Any]:
    algo_citation: Citation | None = None
    algo_attribution: IPAttribution | None = None
    if isinstance(opt.model_version, dict):
        provider_id = opt.model_version.get("provider_id")
        if isinstance(provider_id, str):
            for a in CATALOG:
                if (
                    a["model_version"]["provider_id"] == provider_id
                    and a["task_type"] == opt.task_type
                ):
                    algo_citation = a.get("citation")
                    algo_attribution = a.get("ip_attribution")
                    break

    citation_payload: CitationSchema | None = None
    if algo_citation is not None:
        try:
            citation_payload = CitationSchema.model_validate(algo_citation)
        except Exception:
            citation_payload = None

    attribution_payload: IPAttributionSchema | None = None
    if algo_attribution is not None:
        try:
            attribution_payload = IPAttributionSchema.model_validate(algo_attribution)
        except Exception:
            attribution_payload = None

    payload = OptimizationResponse(
        optimization_id=opt.id,
        status="completed",
        solution=opt.solution,
        objective=float(opt.objective) if opt.objective is not None else None,
        model_version=opt.model_version,  # type: ignore[arg-type]
        solve_seconds=float(opt.solve_seconds) if opt.solve_seconds is not None else 0.0,
        created_at=opt.created_at,
        completed_at=opt.completed_at or opt.created_at,
        citation=citation_payload,
        ip_attribution=attribution_payload,
    )
    content: dict[str, Any] = json.loads(payload.model_dump_json())
    if isinstance(opt.input_payload, dict):
        system_payload = opt.input_payload.get("_system")
        if isinstance(system_payload, dict):
            reproducibility = system_payload.get("reproducibility")
            if isinstance(reproducibility, dict):
                content["reproducibility"] = reproducibility
    return content


def _build_rerun_response_content(
    opt: Optimization,
    *,
    rerun_of_voucher_id: str,
    source_optimization_id: uuid.UUID,
    archive_restore: dict[str, Any] | None = None,
) -> dict[str, Any]:
    content = _build_response_content(opt)
    content.update(
        build_rerun_lineage_payload(
            rerun_of_voucher_id=rerun_of_voucher_id,
            source_optimization_id=source_optimization_id,
            archive_restore=archive_restore,
        )
    )
    return content


def _build_rerun_success_response(
    opt: Optimization,
    *,
    rerun_of_voucher_id: str,
    source_optimization_id: uuid.UUID,
    archive_restore: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        content=_build_rerun_response_content(
            opt,
            rerun_of_voucher_id=rerun_of_voucher_id,
            source_optimization_id=source_optimization_id,
            archive_restore=archive_restore,
        ),
        status_code=status.HTTP_200_OK,
    )


def _build_archive_restore_metadata() -> dict[str, Any]:
    return {
        "mode": "live_solver_image_reuse",
        "status": "used",
        "detail": "live solver image reuse used for current LP support",
    }


async def _read_empty_rerun_body(request: Request) -> object | None:
    raw = await request.body()
    if not raw or not raw.strip():
        return None
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"rerun request body must be empty or {{}}: {exc.msg}",
        ) from exc
    if isinstance(body, dict) and not body:
        return None
    return _RERUN_BODY_NOT_EMPTY


def _attach_reproducibility_metadata(
    body: dict,  # type: ignore[type-arg]
    reproducibility: dict[str, object] | None,
) -> dict:  # type: ignore[type-arg]
    """Return a copy of the user payload with namespaced system metadata."""
    return _attach_system_metadata(body, reproducibility=reproducibility)


def _attach_system_metadata(body: dict, **metadata: object | None) -> dict:  # type: ignore[type-arg]
    """Return a copy of the user payload with merged `_system` metadata."""
    if not metadata:
        return body
    payload = dict(body)
    existing_system = payload.get("_system")
    system_payload: dict[str, object] = (
        dict(existing_system) if isinstance(existing_system, dict) else {}
    )
    for key, value in metadata.items():
        if value is not None:
            system_payload[key] = value
    if system_payload:
        payload["_system"] = system_payload
    return payload


def _merge_optimization_error(opt: Optimization, updates: dict[str, Any]) -> dict[str, Any]:
    """Assign a fresh merged error payload so JSONB changes are persisted."""
    existing = dict(opt.error) if isinstance(opt.error, dict) else {}
    existing.update(updates)
    opt.error = existing
    return existing


def _rfc7807_error(
    *,
    title: str,
    status_code: int,
    detail: str,
    errors: list[ErrorDetail] | None = None,
    next_action: str | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    """Build RFC 7807 + errors[] response (FG1.3)."""
    body = ErrorResponse(
        type=f"https://api.opticloud.cn/errors/{title.lower().replace(' ', '_')}",
        title=title,
        status=status_code,
        detail=detail,
        errors=errors or [],
        next_action_url=next_action,
        request_id=request_id,
    )
    return JSONResponse(content=body.model_dump(), status_code=status_code)


def _unaudited_self_algorithm_error(
    route: ProviderRouteResult | FallbackAttemptPlan,
    *,
    field_path: str,
    request_id: str | None = None,
) -> JSONResponse:
    missing_rules = list(route.missing_self_audit_rules or [])
    constraint = ", ".join(missing_rules)
    ticket_id = route.audit_ticket_id or "self-audit-unknown-unknown"
    k_algo = route.blocked_k_algo or "unknown"
    provider_id = route.blocked_provider_id or "unknown"
    return _rfc7807_error(
        title="Unaudited Self Algorithm",
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"self-developed algorithm '{k_algo}' from provider '{provider_id}' "
            f"is blocked until §4.5 self-audit passes; audit_ticket_id={ticket_id}"
        ),
        errors=[
            ErrorDetail(
                field_path=field_path,
                value=k_algo,
                constraint=f"missing self-audit rules: {constraint}",
                remediation_hint_key="errors.403.unaudited_self_algorithm",
            )
        ],
        next_action=f"https://console.opticloud.cn/admin/self-audit/{ticket_id}",
        request_id=request_id,
    )


def _provider_route_error_response(
    route: ProviderRouteResult,
    *,
    task_type: str,
    requested_solver: str | None,
    request_id: str | None,
) -> JSONResponse | None:
    if route.status is ProviderRouteStatus.UNSUPPORTED_TASK_TYPE:
        return _rfc7807_error(
            title="Unsupported Task Type",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"task_type '{task_type}' not in catalog",
            errors=[
                ErrorDetail(
                    field_path="task_type",
                    value=task_type,
                    constraint="must be one of catalog k_algo.task_type",
                    remediation_hint_key="errors.422.unsupported_task_type",
                )
            ],
            next_action="https://api.opticloud.cn/v1/algorithms",
            request_id=request_id,
        )
    if route.status is ProviderRouteStatus.UNSUPPORTED_SOLVER:
        return _rfc7807_error(
            title="Unsupported Solver",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"solver '{requested_solver}' is not supported for task_type "
                f"'{task_type}'. Supported: {', '.join(route.supported_solvers)}"
            ),
            errors=[
                ErrorDetail(
                    field_path="solver",
                    value=requested_solver,
                    constraint=f"must be one of: {', '.join(route.supported_solvers)}",
                    remediation_hint_key="errors.400.unsupported_solver",
                )
            ],
            next_action="https://api.opticloud.cn/v1/algorithms",
            request_id=request_id,
        )
    if route.status is ProviderRouteStatus.UNAUDITED_SELF_ALGORITHM:
        return _unaudited_self_algorithm_error(
            route,
            field_path="solver" if requested_solver is not None else "task_type",
            request_id=request_id,
        )
    return None


async def _record_solver_cost_attribution(
    session: AsyncSession,
    *,
    opt: Optimization,
    result: solvers.LPSolveResult,
    solver_name: str | None,
) -> None:
    """Best-effort G3 solver-second attribution for persisted optimization rows."""
    try:
        provider_id: str | None = None
        if isinstance(opt.model_version, dict):
            raw_provider = opt.model_version.get("provider_id")
            if isinstance(raw_provider, str):
                provider_id = raw_provider

        event = CostTelemetryEvent(
            tenant_id=opt.user_id,
            service="solver-orchestrator",
            cost_unit=CostUnit.SOLVER_SECOND,
            value=Decimal(str(result.solve_seconds)),
            source_id=opt.id,
            metadata={
                "task_type": opt.task_type,
                "solver": solver_name or "default",
                "status": result.status,
                "model_provider": provider_id or "unknown",
            },
        )
        async with session.begin_nested():
            await record_cost_event(session, CostAttribution, event)
    except Exception as exc:
        logger.warning(
            "cost_attribution.record_failed",
            optimization_id=str(opt.id),
            user_id=str(opt.user_id),
            exception_type=type(exc).__name__,
            message=str(exc),
        )


@dataclass(frozen=True)
class _FallbackExecutionOutcome:
    result: solvers.LPSolveResult
    terminal_attempt: FallbackAttempt
    total_solve_seconds: float
    fallback_execution: dict[str, object]


def _execute_fallback_attempts(
    *,
    attempts: list[FallbackAttempt],
    task_type: str,
    body_dict: dict[str, Any],
    max_solve_seconds: float,
    max_fallback_retries: int,
) -> _FallbackExecutionOutcome:
    attempt_metadata: list[dict[str, object]] = []
    total_solve_seconds = 0.0
    terminal_result: solvers.LPSolveResult | None = None
    terminal_attempt: FallbackAttempt | None = None
    exhausted = False

    for index, attempt in enumerate(attempts):
        if attempt.route.selected_solver is None:
            raise ValueError("fallback attempt requires selected solver")
        attempt_body = dict(body_dict)
        attempt_body["solver"] = attempt.route.selected_solver
        result = solvers.solve_from_request(
            attempt_body,
            max_solve_seconds=max_solve_seconds,
        )
        total_solve_seconds += result.solve_seconds
        retryable = is_retryable_solver_result(result)
        has_next = index < len(attempts) - 1
        attempt_metadata.append(
            fallback_attempt_to_metadata(
                attempt,
                result,
                task_type=task_type,
                retryable=retryable,
            )
        )
        terminal_result = result
        terminal_attempt = attempt
        if result.status == "optimal" or not retryable:
            break
        if not has_next:
            exhausted = True
            break

    if terminal_result is None or terminal_attempt is None:
        raise ValueError("fallback execution requires at least one attempt")

    aggregate_result = solvers.LPSolveResult(
        status=terminal_result.status,
        objective=terminal_result.objective,
        solution=terminal_result.solution,
        solve_seconds=total_solve_seconds,
        error_field_path=terminal_result.error_field_path,
        error_constraint=terminal_result.error_constraint,
    )
    fallback_execution = build_fallback_execution_metadata(
        attempt_metadata=attempt_metadata,
        terminal_result=aggregate_result,
        terminal_attempt=terminal_attempt,
        total_solve_seconds=total_solve_seconds,
        max_fallback_retries=max_fallback_retries,
        exhausted=exhausted,
    )
    return _FallbackExecutionOutcome(
        result=aggregate_result,
        terminal_attempt=terminal_attempt,
        total_solve_seconds=total_solve_seconds,
        fallback_execution=fallback_execution,
    )


@router.post(
    "/optimizations",
    tags=["execution"],
    summary="提交优化任务 (FR E1, E3, E7, E9)",
    description=(
        "FR E1 + E3 + E7 + E9 + Story 3.1 J1 Vertical Slice.\n\n"
        "Auth: `Authorization: Bearer sk-xxx` (FR A2 scoped — requires `optimize:write`).\n"
        "Idempotency: `Idempotency-Key` header (P23, 24h dedup).\n"
        "Errors: RFC 7807 + errors[] (FG1.3) + next_action_url (FR O7).\n\n"
        "**CRG2 Performance**: cold-start P95 < 5s; warm-start P95 < 200ms."
    ),
)
async def post_optimization(
    payload: OptimizationRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    billing_charge_id: str | None = Header(default=None, alias="X-Billing-Charge-Id"),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    # ----- AuthN + scope -----
    client_ip = request.client.host if request.client else None
    user_id, api_key_id, scopes = await verify_api_key(authorization, session, client_ip=client_ip)
    require_scope("optimize:write", scopes)

    body_dict = payload.model_dump(by_alias=True)
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

    if payload.options.anonymous and not payload.options.reproducible:
        return _anonymous_without_reproducible_error(request_id=request_id)

    # ----- Lookup provider route before billing/idempotency side effects (Story 2.8) -----
    route = select_provider_route(payload.task_type, payload.solver)
    route_error = _provider_route_error_response(
        route,
        task_type=payload.task_type,
        requested_solver=payload.solver,
        request_id=request_id,
    )
    if route_error is not None:
        return route_error

    assert route.algorithm is not None
    assert route.selected_solver is not None

    # ----- Story 5.A.4 — pre-solve billing reserve (opt-in via X-Billing-Charge-Id) -----
    billing_uuid: uuid.UUID | None = None
    if billing_charge_id:
        try:
            billing_uuid = uuid.UUID(billing_charge_id)
        except ValueError:
            return _rfc7807_error(
                title="Invalid X-Billing-Charge-Id",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="X-Billing-Charge-Id must be a UUID",
                errors=[
                    ErrorDetail(
                        field_path="header.X-Billing-Charge-Id",
                        value=billing_charge_id,
                        constraint="must be a UUID",
                        remediation_hint_key="errors.422.invalid_uuid",
                    )
                ],
                request_id=request_id,
            )
        reserve_result = await billing_client.reserve(billing_uuid, user_id)
        if not reserve_result.ok:
            return _rfc7807_error(
                title="Billing Reserve Failed",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=reserve_result.error_message or "billing reserve declined",
                errors=[
                    ErrorDetail(
                        field_path="header.X-Billing-Charge-Id",
                        value=billing_charge_id,
                        constraint=f"billing returned {reserve_result.status_code}",
                        remediation_hint_key="errors.422.billing_reserve_failed",
                    )
                ],
                request_id=request_id,
            )

    # ----- Idempotency (P23) -----
    if idempotency_key:
        body_hash = _hash_body(body_dict)
        idem_query = await session.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.user_id == user_id,
                IdempotencyKey.key == idempotency_key,
            )
        )
        existing = idem_query.scalar_one_or_none()
        if existing is not None:
            if existing.request_body_hash != body_hash:
                return _rfc7807_error(
                    title="Idempotency Conflict",
                    status_code=status.HTTP_409_CONFLICT,
                    detail="same idempotency key with different request body (P23)",
                    errors=[
                        ErrorDetail(
                            field_path="header.Idempotency-Key",
                            value=idempotency_key,
                            constraint="reused with different body",
                            remediation_hint_key="errors.409.idempotency_body_mismatch",
                        )
                    ],
                    request_id=request_id,
                )
            # Return cached result
            opt = await session.get(Optimization, existing.optimization_id)
            if opt is not None and opt.status == "completed":
                await attach_existing_voucher_id(session, opt)
                return _build_success_response(opt)

    # ----- Story 2.5 — FR C5 fallback_chain per-element validation -----
    # Chain is stored in input_payload (via model_dump) only; actual fallback
    # execution (try chain[0] → chain[1] on failure, ≤3 retries) is Story 2.7.
    if payload.fallback_chain:
        for idx, candidate in enumerate(payload.fallback_chain):
            if candidate not in route.supported_solvers:
                return _rfc7807_error(
                    title="Unsupported Fallback Solver",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"fallback_chain[{idx}]='{candidate}' is not supported for "
                        f"task_type '{payload.task_type}'. "
                        f"Supported: {', '.join(route.supported_solvers)}"
                    ),
                    errors=[
                        ErrorDetail(
                            field_path=f"fallback_chain[{idx}]",
                            value=candidate,
                            constraint=f"must be one of: {', '.join(route.supported_solvers)}",
                            remediation_hint_key="errors.400.unsupported_fallback_solver",
                        )
                    ],
                    next_action="https://api.opticloud.cn/v1/algorithms",
                    request_id=request_id,
                )

    attempt_plan = build_fallback_attempts(
        primary_route=route,
        task_type=payload.task_type,
        requested_solver=payload.solver,
        fallback_chain=payload.fallback_chain,
    )
    if attempt_plan.status is FallbackPlanStatus.UNAUDITED_SELF_ALGORITHM:
        return _unaudited_self_algorithm_error(
            attempt_plan,
            field_path=(
                f"fallback_chain[{attempt_plan.invalid_index}]"
                if attempt_plan.invalid_index is not None
                else "fallback_chain"
            ),
            request_id=request_id,
        )
    if attempt_plan.status is FallbackPlanStatus.INVALID_FALLBACK_SOLVER:
        invalid_idx = attempt_plan.invalid_index if attempt_plan.invalid_index is not None else 0
        supported = attempt_plan.supported_solvers or route.supported_solvers
        invalid_candidate = attempt_plan.invalid_candidate
        return _rfc7807_error(
            title="Unsupported Fallback Solver",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"fallback_chain[{invalid_idx}]='{invalid_candidate}' is not supported for "
                f"task_type '{payload.task_type}'. Supported: {', '.join(supported)}"
            ),
            errors=[
                ErrorDetail(
                    field_path=f"fallback_chain[{invalid_idx}]",
                    value=invalid_candidate,
                    constraint=f"must be one of: {', '.join(supported)}",
                    remediation_hint_key="errors.400.unsupported_fallback_solver",
                )
            ],
            next_action="https://api.opticloud.cn/v1/algorithms",
            request_id=request_id,
        )
    primary_route_metadata = attempt_route_metadata(
        attempt_plan.attempts[0], task_type=payload.task_type
    )

    # ----- Persist input -----
    opt = Optimization(
        user_id=user_id,
        api_key_id=api_key_id,
        task_type=payload.task_type,
        status="in_progress",
        input_payload=_attach_system_metadata(
            body_dict,
            provider_route=primary_route_metadata,
        ),
        idempotency_key=idempotency_key,
    )
    session.add(opt)
    await session.flush()

    # ----- Solve (sync mode) -----
    # Sprint 0: only LP supported; other types return 501 stub.
    if payload.task_type != "lp":
        opt.status = "failed"
        opt.error = {"title": "Not Implemented", "detail": f"{payload.task_type} planned in M2-M5"}
        opt.completed_at = datetime.now(UTC)
        return _rfc7807_error(
            title="Not Implemented",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"task_type '{payload.task_type}' planned in M2-M5; Sprint 0 supports 'lp' only",
            request_id=request_id,
        )

    execution = _execute_fallback_attempts(
        attempts=attempt_plan.attempts,
        task_type=payload.task_type,
        body_dict=body_dict,
        max_solve_seconds=payload.options.max_solve_seconds,
        max_fallback_retries=len(payload.fallback_chain or []),
    )
    result = execution.result
    final_attempt = execution.terminal_attempt
    final_route = final_attempt.route
    final_selected_solver = final_route.selected_solver
    assert final_selected_solver is not None
    executed_provider_route_metadata = attempt_route_metadata(
        final_attempt,
        task_type=payload.task_type,
    )
    opt.solve_seconds = execution.total_solve_seconds
    opt.model_version = dict(final_route.model_version)
    opt.input_payload = _attach_system_metadata(
        opt.input_payload,
        provider_route=primary_route_metadata,
        executed_provider_route=executed_provider_route_metadata,
        fallback_execution=execution.fallback_execution,
    )

    # ----- Story 5.A.4 — post-solve billing finalize (single attempt, no retry per Q4) -----
    if billing_uuid is not None:
        finalize_status: Literal["success", "failure"]
        finalize_status = "success" if result.status == "optimal" else "failure"
        failure_reason: str | None = (
            None if finalize_status == "success" else (result.error_constraint or result.status)
        )
        finalize_outcome = await billing_client.finalize(
            billing_uuid,
            user_id,
            elapsed_seconds=result.solve_seconds,
            status=finalize_status,
            failure_reason=failure_reason,
        )
        if not finalize_outcome.ok:
            # Q4 — solve result is NOT held hostage by billing; mark + log + continue.
            # M2.2c — persist retry context so the billing reconciler can replay.
            _merge_optimization_error(
                opt,
                {
                    "billing_finalize_failed": True,
                    "billing_finalize_error": finalize_outcome.error_message,
                    "billing_charge_id": str(billing_uuid),
                    "billing_elapsed_seconds": result.solve_seconds,
                    "billing_status": finalize_status,
                    "billing_failure_reason": failure_reason,
                    "billing_retry_count": 0,
                },
            )

    if result.status == "optimal":
        opt.status = "completed"
        opt.solution = result.solution
        opt.objective = result.objective
        opt.completed_at = datetime.now(UTC)
        if payload.options.reproducible:
            reproducibility_payload = _build_reproducibility_payload(
                request_body=body_dict,
                model_version=dict(final_route.model_version),
                locked_solver=final_selected_solver,
                anonymous=payload.options.anonymous,
            )
            opt.input_payload = _attach_system_metadata(
                opt.input_payload,
                reproducibility=reproducibility_payload,
            )
            await issue_reproduction_voucher(session, opt, issued_at=opt.completed_at)
        await _record_solver_cost_attribution(
            session, opt=opt, result=result, solver_name=final_selected_solver
        )
    elif result.status in ("infeasible", "unbounded"):
        opt.status = "failed"
        opt.completed_at = datetime.now(UTC)
        _merge_optimization_error(
            opt,
            {
                "title": "Solver Result",
                "detail": result.error_constraint or result.status,
                "errors": [
                    {
                        "field_path": result.error_field_path or "st",
                        "value": None,
                        "constraint": result.error_constraint or result.status,
                        "remediation_hint_key": f"errors.422.{result.status}",
                    }
                ],
                "fallback_execution": execution.fallback_execution,
            },
        )
        # Persist + return error
        if idempotency_key:
            session.add(
                IdempotencyKey(
                    key=idempotency_key,
                    user_id=user_id,
                    optimization_id=opt.id,
                    request_body_hash=_hash_body(body_dict),
                    expires_at=datetime.now(UTC) + timedelta(hours=24),
                )
            )
        await _record_solver_cost_attribution(
            session, opt=opt, result=result, solver_name=final_selected_solver
        )
        return _rfc7807_error(
            title=f"LP {result.status.capitalize()}",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.error_constraint or result.status,
            errors=[
                ErrorDetail(
                    field_path=result.error_field_path or "st",
                    value=None,
                    constraint=result.error_constraint or result.status,
                    remediation_hint_key=f"errors.422.{result.status}",
                )
            ],
            next_action=f"https://docs.opticloud.cn/troubleshoot/{result.status}",
            request_id=request_id,
        )
    elif result.status == "timeout":
        opt.status = "timeout"
        opt.completed_at = datetime.now(UTC)
        _merge_optimization_error(
            opt,
            {
                "detail": result.error_constraint,
                "fallback_execution": execution.fallback_execution,
            },
        )
        await _record_solver_cost_attribution(
            session, opt=opt, result=result, solver_name=final_selected_solver
        )
        return _rfc7807_error(
            title="Solver Timeout",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=result.error_constraint or "solver exceeded max_solve_seconds",
            errors=[
                ErrorDetail(
                    field_path=result.error_field_path or "options.max_solve_seconds",
                    value=payload.options.max_solve_seconds,
                    constraint=result.error_constraint or "timeout",
                    remediation_hint_key="errors.504.solver_timeout",
                )
            ],
            request_id=request_id,
        )
    else:  # error
        opt.status = "failed"
        opt.completed_at = datetime.now(UTC)
        _merge_optimization_error(
            opt,
            {
                "detail": result.error_constraint,
                "fallback_execution": execution.fallback_execution,
            },
        )
        await _record_solver_cost_attribution(
            session, opt=opt, result=result, solver_name=final_selected_solver
        )
        return _rfc7807_error(
            title="Validation Error",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.error_constraint or "invalid LP input",
            errors=[
                ErrorDetail(
                    field_path=result.error_field_path or "$",
                    value=None,
                    constraint=result.error_constraint or "invalid input",
                    remediation_hint_key="errors.422.invalid_lp_input",
                )
            ],
            request_id=request_id,
        )

    # ----- Persist idempotency mapping (after success) -----
    if idempotency_key:
        session.add(
            IdempotencyKey(
                key=idempotency_key,
                user_id=user_id,
                optimization_id=opt.id,
                request_body_hash=_hash_body(body_dict),
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
        )

    return _build_success_response(opt)


@router.post(
    "/predictions",
    tags=["execution"],
    summary="提交预测任务 (FR E2, E6)",
    description=(
        "FR E2 + E6: submit a forecast family request and receive deterministic "
        "P10/P50/P90 quantiles, drift_score, and bilingual disclaimer."
    ),
)
async def post_prediction(
    payload: PredictionRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    billing_charge_id: str | None = Header(default=None, alias="X-Billing-Charge-Id"),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    client_ip = request.client.host if request.client else None
    user_id, api_key_id, scopes = await verify_api_key(authorization, session, client_ip=client_ip)
    require_scope("optimize:write", scopes)
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

    body_dict, validation_error = _validate_prediction_payload(payload, request_id=request_id)
    if validation_error is not None:
        return validation_error
    assert body_dict is not None

    family = str(body_dict["family"])
    mapped_solver = _prediction_family_to_solver(family)
    assert mapped_solver is not None

    route = select_provider_route("forecast", mapped_solver)
    if route.status is ProviderRouteStatus.UNAUDITED_SELF_ALGORITHM:
        return _unaudited_self_algorithm_error(route, field_path="family", request_id=request_id)
    route_error = _provider_route_error_response(
        route,
        task_type="forecast",
        requested_solver=mapped_solver,
        request_id=request_id,
    )
    if route_error is not None:
        return route_error
    assert route.algorithm is not None
    assert route.selected_solver is not None

    if billing_charge_id:
        return _rfc7807_error(
            title="Billing Not Supported For Predictions",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-Billing-Charge-Id is not supported for /v1/predictions in Story 3.2",
            errors=[
                ErrorDetail(
                    field_path="header.X-Billing-Charge-Id",
                    value="[redacted]",
                    constraint="billing is not supported for predictions yet",
                    remediation_hint_key="errors.422.billing_not_supported_for_predictions",
                )
            ],
            request_id=request_id,
        )

    body_hash = _hash_body(body_dict)
    if idempotency_key:
        now = datetime.now(UTC)
        idem_query = await session.execute(
            select(PredictionIdempotencyKey).where(
                PredictionIdempotencyKey.user_id == user_id,
                PredictionIdempotencyKey.key == idempotency_key,
            )
        )
        existing = idem_query.scalar_one_or_none()
        if existing is not None and _is_expired_at(existing.expires_at, now=now):
            await session.delete(existing)
            await session.flush()
            existing = None
        if existing is not None:
            if existing.request_body_hash != body_hash:
                return _rfc7807_error(
                    title="Idempotency Conflict",
                    status_code=status.HTTP_409_CONFLICT,
                    detail="same idempotency key with different request body (P23)",
                    errors=[
                        ErrorDetail(
                            field_path="header.Idempotency-Key",
                            value=idempotency_key,
                            constraint="reused with different body",
                            remediation_hint_key="errors.409.idempotency_body_mismatch",
                        )
                    ],
                    request_id=request_id,
                )
            cached_prediction = await session.get(Prediction, existing.prediction_id)
            if cached_prediction is None or cached_prediction.status != "completed":
                return _rfc7807_error(
                    title="Idempotency Conflict",
                    status_code=status.HTTP_409_CONFLICT,
                    detail="idempotency key already used by an incomplete prediction",
                    request_id=request_id,
                )
            return _build_prediction_success_response(cached_prediction)

    route_metadata = provider_route_to_system_metadata(
        route,
        task_type="forecast",
        requested_solver=mapped_solver,
    )

    started = time.perf_counter()
    forecast_result = predict_quantiles(
        [float(value) for value in body_dict["data"]],
        int(body_dict["horizon"]),
    )
    elapsed = max(time.perf_counter() - started, forecast_result.predict_seconds)
    completed_at = datetime.now(UTC)
    prediction_payload = {
        "p10": forecast_result.p10,
        "p50": forecast_result.p50,
        "p90": forecast_result.p90,
    }
    prediction_row = Prediction(
        user_id=user_id,
        api_key_id=api_key_id,
        family=family,
        status="completed",
        input_payload=_attach_system_metadata(body_dict, provider_route=route_metadata),
        prediction=prediction_payload,
        drift_score=forecast_result.drift_score,
        model_version=dict(route.model_version),
        predict_seconds=elapsed,
        idempotency_key=idempotency_key,
        completed_at=completed_at,
    )
    session.add(prediction_row)
    await session.flush()

    if idempotency_key:
        session.add(
            PredictionIdempotencyKey(
                key=idempotency_key,
                user_id=user_id,
                prediction_id=prediction_row.id,
                request_body_hash=body_hash,
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
        )
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            return _rfc7807_error(
                title="Idempotency Conflict",
                status_code=status.HTTP_409_CONFLICT,
                detail="idempotency key already exists",
                request_id=request_id,
            )

    return _build_prediction_success_response(prediction_row)


@router.get(
    "/predictions/{prediction_id}",
    tags=["execution"],
    summary="查 prediction 状态 (FR E9 subset)",
)
async def get_prediction(
    prediction_id: uuid.UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    client_ip = request.client.host if request.client else None
    user_id, _api_key_id, _scopes = await verify_api_key(
        authorization, session, client_ip=client_ip
    )
    pred = await session.get(Prediction, prediction_id)
    if pred is None or pred.user_id != user_id:
        return _rfc7807_error(
            title="Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"prediction {prediction_id} not found",
        )
    return JSONResponse(
        content=_build_prediction_response_content(pred),
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/reproduce/{voucher_id}/rerun",
    tags=["reproducibility"],
    summary="重新运行 durable voucher (FR R3)",
)
async def rerun_reproduction(
    voucher_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    client_ip = request.client.host if request.client else None
    user_id, api_key_id, scopes = await verify_api_key(authorization, session, client_ip=client_ip)
    require_scope("optimize:write", scopes)

    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    billing_charge_id = request.headers.get("x-billing-charge-id")
    if billing_charge_id:
        return _rfc7807_error(
            title="Invalid X-Billing-Charge-Id",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="rerun requests do not accept X-Billing-Charge-Id",
            errors=[
                ErrorDetail(
                    field_path="header.X-Billing-Charge-Id",
                    value=billing_charge_id,
                    constraint="not accepted for rerun",
                    remediation_hint_key="errors.422.billing_not_supported_for_rerun",
                )
            ],
            request_id=request_id,
        )

    try:
        rerun_body_marker = await _read_empty_rerun_body(request)
    except HTTPException as exc:
        return _rfc7807_error(
            title="Invalid JSON",
            status_code=exc.status_code,
            detail=str(exc.detail),
            request_id=request_id,
        )
    if rerun_body_marker is not None:
        return _rfc7807_error(
            title="Invalid Rerun Body",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="rerun request body must be empty or {}",
            errors=[
                ErrorDetail(
                    field_path="$",
                    value=None,
                    constraint="body must be empty",
                    remediation_hint_key="errors.422.invalid_body",
                )
            ],
            request_id=request_id,
        )

    if not VOUCHER_ID_PATTERN.fullmatch(voucher_id):
        return _rfc7807_error(
            title="Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"voucher {voucher_id} not found",
            request_id=request_id,
        )

    rerun_request_hash = _hash_rerun_request(voucher_id)
    if idempotency_key:
        idem_query = await session.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.user_id == user_id,
                IdempotencyKey.key == idempotency_key,
            )
        )
        existing = idem_query.scalar_one_or_none()
        if existing is not None:
            if existing.request_body_hash != rerun_request_hash:
                return _rfc7807_error(
                    title="Idempotency Conflict",
                    status_code=status.HTTP_409_CONFLICT,
                    detail="same idempotency key with different voucher",
                    errors=[
                        ErrorDetail(
                            field_path="header.Idempotency-Key",
                            value=idempotency_key,
                            constraint="reused with different voucher",
                            remediation_hint_key="errors.409.idempotency_body_mismatch",
                        )
                    ],
                    request_id=request_id,
                )

            cached_opt = await session.get(Optimization, existing.optimization_id)
            if cached_opt is None or cached_opt.status != "completed":
                return _rfc7807_error(
                    title="Idempotency Conflict",
                    status_code=status.HTTP_409_CONFLICT,
                    detail="idempotency key already used by an incomplete rerun",
                    request_id=request_id,
                )

            cached_voucher = await get_reproduction_voucher(session, cached_opt.id)
            if cached_voucher is None:
                return _rfc7807_error(
                    title="Idempotency Conflict",
                    status_code=status.HTTP_409_CONFLICT,
                    detail="cached rerun is missing voucher linkage",
                    request_id=request_id,
                )

            source_voucher_id = cached_voucher.voucher_id
            source_optimization_id = cached_opt.id
            if cached_voucher.parent_voucher_id is None:
                return _rfc7807_error(
                    title="Idempotency Conflict",
                    status_code=status.HTTP_409_CONFLICT,
                    detail="cached rerun voucher is missing parent lineage",
                    request_id=request_id,
                )
            parent_voucher = await get_reproduction_voucher_by_pk(
                session, cached_voucher.parent_voucher_id
            )
            if parent_voucher is None:
                return _rfc7807_error(
                    title="Idempotency Conflict",
                    status_code=status.HTTP_409_CONFLICT,
                    detail="cached rerun parent voucher is missing",
                    request_id=request_id,
                )
            source_voucher_id = parent_voucher.voucher_id
            source_optimization_id = parent_voucher.optimization_id

            await attach_existing_voucher_id(session, cached_opt)
            return _build_rerun_success_response(
                cached_opt,
                rerun_of_voucher_id=source_voucher_id,
                source_optimization_id=source_optimization_id,
                archive_restore=_build_archive_restore_metadata(),
            )

    voucher = await _load_owner_visible_voucher(session, voucher_id=voucher_id, user_id=user_id)
    if voucher is None:
        return _rfc7807_error(
            title="Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"voucher {voucher_id} not found",
            request_id=request_id,
        )

    if voucher.status != "issued":
        return _rfc7807_error(
            title="Rerun Not Allowed",
            status_code=status.HTTP_409_CONFLICT,
            detail=f"voucher {voucher_id} status '{voucher.status}' is not rerunnable",
            request_id=request_id,
        )

    if _is_rerun_voucher_expired(voucher.created_at):
        return _rfc7807_error(
            title="Voucher Expired",
            status_code=status.HTTP_410_GONE,
            detail=f"voucher {voucher_id} expired after 5 years",
            next_action="https://docs.opticloud.cn/reproducibility",
            request_id=request_id,
        )

    source_opt = await _load_source_optimization_for_voucher(
        session, voucher=voucher, user_id=user_id
    )
    if source_opt is None:
        return _rfc7807_error(
            title="Rerun Not Allowed",
            status_code=status.HTTP_409_CONFLICT,
            detail="source optimization is missing, not owned, or not completed",
            request_id=request_id,
        )

    if source_opt.task_type != "lp":
        return _rfc7807_error(
            title="Not Implemented",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"task_type '{source_opt.task_type}' planned in M2-M5; rerun supports 'lp' only",
            request_id=request_id,
        )

    if voucher.locked_solver != "highs":
        return _rfc7807_error(
            title="Not Implemented",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"locked_solver '{voucher.locked_solver}' is not available for rerun",
            request_id=request_id,
        )

    try:
        clean_payload = OptimizationRequest.model_validate(
            _strip_system_metadata(source_opt.input_payload)
        )
    except Exception:
        return _rfc7807_error(
            title="Rerun Not Allowed",
            status_code=status.HTTP_409_CONFLICT,
            detail="source optimization payload is invalid for rerun",
            request_id=request_id,
        )

    clean_payload_dict = clean_payload.model_dump(by_alias=True)
    rerun_reproducibility = _build_reproducibility_payload(
        request_body=clean_payload_dict,
        model_version=dict(voucher.locked_model_version),
        locked_solver=voucher.locked_solver,
        anonymous=voucher.anonymous,
    )

    rerun_tx = await session.begin_nested()
    rerun_opt = Optimization(
        user_id=user_id,
        api_key_id=api_key_id,
        task_type=clean_payload.task_type,
        status="in_progress",
        input_payload=_attach_reproducibility_metadata(clean_payload_dict, rerun_reproducibility),
        idempotency_key=idempotency_key,
    )
    session.add(rerun_opt)
    await session.flush()

    result = solvers.solve_from_request(
        clean_payload_dict, max_solve_seconds=clean_payload.options.max_solve_seconds
    )
    rerun_opt.solve_seconds = result.solve_seconds
    rerun_opt.model_version = dict(voucher.locked_model_version)

    if result.status == "optimal":
        rerun_opt.status = "completed"
        rerun_opt.solution = result.solution
        rerun_opt.objective = result.objective
        rerun_opt.completed_at = datetime.now(UTC)
        await issue_reproduction_voucher(
            session,
            rerun_opt,
            issued_at=rerun_opt.completed_at,
            parent_voucher_id=voucher.id,
            rerun_depth=voucher.rerun_depth + 1,
        )
        if idempotency_key:
            session.add(
                IdempotencyKey(
                    key=idempotency_key,
                    user_id=user_id,
                    optimization_id=rerun_opt.id,
                    request_body_hash=rerun_request_hash,
                    expires_at=datetime.now(UTC) + timedelta(hours=24),
                )
            )
        archive_restore = _build_archive_restore_metadata()
        await attach_existing_voucher_id(session, rerun_opt)
        content = _build_rerun_response_content(
            rerun_opt,
            rerun_of_voucher_id=voucher.voucher_id,
            source_optimization_id=source_opt.id,
            archive_restore=archive_restore,
        )
        await rerun_tx.commit()
        return JSONResponse(content=content, status_code=status.HTTP_200_OK)

    await rerun_tx.rollback()
    if result.status in ("infeasible", "unbounded"):
        return _rfc7807_error(
            title=f"LP {result.status.capitalize()}",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.error_constraint or result.status,
            errors=[
                ErrorDetail(
                    field_path=result.error_field_path or "st",
                    value=None,
                    constraint=result.error_constraint or result.status,
                    remediation_hint_key=f"errors.422.{result.status}",
                )
            ],
            next_action=f"https://docs.opticloud.cn/troubleshoot/{result.status}",
            request_id=request_id,
        )
    if result.status == "timeout":
        return _rfc7807_error(
            title="Solver Timeout",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=result.error_constraint or "solver exceeded max_solve_seconds",
            errors=[
                ErrorDetail(
                    field_path=result.error_field_path or "options.max_solve_seconds",
                    value=clean_payload.options.max_solve_seconds,
                    constraint=result.error_constraint or "timeout",
                    remediation_hint_key="errors.504.solver_timeout",
                )
            ],
            request_id=request_id,
        )
    return _rfc7807_error(
        title="Validation Error",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=result.error_constraint or "invalid LP input",
        errors=[
            ErrorDetail(
                field_path=result.error_field_path or "$",
                value=None,
                constraint=result.error_constraint or "invalid input",
                remediation_hint_key="errors.422.invalid_lp_input",
            )
        ],
        request_id=request_id,
    )


def _build_success_response(opt: Optimization) -> JSONResponse:
    """FR E1 + E9 — success response, with citation + IP attribution metadata."""
    content = _build_response_content(opt)

    return JSONResponse(
        content=content,
        status_code=status.HTTP_200_OK,
    )


PREDICTION_DISCLAIMER = PredictionDisclaimer(
    zh="本预测仅供参考",
    en="This forecast is for reference only",
    bilingual="本预测仅供参考 / This forecast is for reference only",
)

PREDICTION_FAMILY_SOLVERS: dict[str, str] = {
    "arima": "arima",
    "chronos": "chronos-t5",
}


def _prediction_family_to_solver(family: str) -> str | None:
    return PREDICTION_FAMILY_SOLVERS.get(family.strip().lower())


def _is_expired_at(expires_at: datetime, *, now: datetime) -> bool:
    expires_at_utc = (
        expires_at.replace(tzinfo=UTC) if expires_at.tzinfo is None else expires_at.astimezone(UTC)
    )
    now_utc = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return expires_at_utc <= now_utc.astimezone(UTC)


def _normalized_prediction_body(payload: PredictionRequest) -> dict[str, Any]:
    return {
        "family": payload.family.strip().lower(),
        "data": [float(value) for value in payload.data],
        "horizon": int(payload.horizon),
    }


def _prediction_validation_error(
    *,
    field_path: str,
    value: object,
    constraint: str,
    request_id: str | None,
) -> JSONResponse:
    return _rfc7807_error(
        title="Invalid Prediction Data",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=constraint,
        errors=[
            ErrorDetail(
                field_path=field_path,
                value=value,
                constraint=constraint,
                remediation_hint_key="errors.422.invalid_prediction_data",
            )
        ],
        request_id=request_id,
    )


def _validate_prediction_payload(
    payload: PredictionRequest,
    *,
    request_id: str | None,
) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    family = payload.family.strip().lower()
    if _prediction_family_to_solver(family) is None:
        return None, _rfc7807_error(
            title="Unsupported Prediction Family",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"family '{payload.family}' is not supported",
            errors=[
                ErrorDetail(
                    field_path="family",
                    value=payload.family,
                    constraint="must be one of: arima, chronos",
                    remediation_hint_key="errors.422.unsupported_prediction_family",
                )
            ],
            next_action="https://api.opticloud.cn/v1/algorithms?task_type=forecast",
            request_id=request_id,
        )
    if len(payload.data) < 3 or len(payload.data) > 10_000:
        return None, _prediction_validation_error(
            field_path="data",
            value=len(payload.data),
            constraint="data length must be between 3 and 10000",
            request_id=request_id,
        )
    for idx, value in enumerate(payload.data):
        if not math.isfinite(float(value)):
            return None, _prediction_validation_error(
                field_path=f"data[{idx}]",
                value="[non-finite]",
                constraint="data values must be finite numbers",
                request_id=request_id,
            )
    if payload.horizon < 1 or payload.horizon > 90:
        return None, _prediction_validation_error(
            field_path="horizon",
            value=payload.horizon,
            constraint="horizon must be between 1 and 90",
            request_id=request_id,
        )
    return _normalized_prediction_body(payload), None


def _build_prediction_response_content(prediction: Prediction) -> dict[str, Any]:
    if prediction.status != "completed":
        return {
            "prediction_id": str(prediction.id),
            "status": prediction.status,
            "error": prediction.error,
            "model_version": prediction.model_version,
            "created_at": prediction.created_at.isoformat() if prediction.created_at else None,
            "completed_at": (
                prediction.completed_at.isoformat() if prediction.completed_at else None
            ),
        }

    payload = PredictionResponse(
        prediction_id=prediction.id,
        status="completed",
        family=prediction.family,
        horizon=int(prediction.input_payload.get("horizon", 0)),
        prediction=PredictionQuantiles.model_validate(prediction.prediction),
        drift_score=float(prediction.drift_score) if prediction.drift_score is not None else 0.0,
        disclaimer=PREDICTION_DISCLAIMER,
        model_version=ModelVersionSchema.model_validate(prediction.model_version),
        predict_seconds=(
            float(prediction.predict_seconds) if prediction.predict_seconds is not None else 0.0
        ),
        created_at=prediction.created_at,
        completed_at=prediction.completed_at or prediction.created_at,
    )
    content = json.loads(payload.model_dump_json())
    if not isinstance(content, dict):
        raise ValueError("prediction response did not encode an object")
    return content


def _build_prediction_success_response(prediction: Prediction) -> JSONResponse:
    return JSONResponse(
        content=_build_prediction_response_content(prediction),
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/optimizations/demo",
    tags=["execution"],
    summary="无鉴权 demo solve（Story 3.E.3 — Console 老张 surface）",
    description=(
        "Story 3.E.3: 老张 Console 入口的 demo solve 路径。\n\n"
        "- 不需要 Authorization（公开 /console/excel 入口）\n"
        "- 不计费 / 不存 DB（纯无状态）\n"
        "- 对 LP: 正常求解返回结果\n"
        "- 对其它 task_type（vrptw / schedule / forecast 等）: 仍返回 501\n"
        "  直到对应求解器在 M2-M3 落地\n\n"
        "Rate limit: M3 内按 IP 限流；v1 无限制（无敏感数据暴露）"
    ),
)
async def post_optimization_demo(request: Request) -> JSONResponse:
    """Story 3.E.3 — unauthenticated marketing-demo solve.

    Accepts a free-form JSON body so VRPTW / Schedule / etc. payloads (which
    don't match the LP-centric OptimizationRequest schema) can reach the
    501 short-circuit instead of being rejected at Pydantic validation as 422.
    Only the LP path performs strict validation (via OptimizationRequest).
    """
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

    try:
        raw = await request.json()
    except Exception:
        return _rfc7807_error(
            title="Invalid JSON",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="request body is not valid JSON",
            request_id=request_id,
        )

    task_type = raw.get("task_type") if isinstance(raw, dict) else None
    if not task_type:
        return _rfc7807_error(
            title="Missing task_type",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="body must include `task_type`",
            request_id=request_id,
        )

    if task_type != "lp":
        return _rfc7807_error(
            title="Not Implemented",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(f"task_type '{task_type}' 求解器将在 M2-M3 落地。 您的数据已通过格式校验。"),
            request_id=request_id,
        )

    # LP path — now apply strict validation
    try:
        payload = OptimizationRequest.model_validate(raw)
    except Exception as e:
        return _rfc7807_error(
            title="Invalid LP body",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
            request_id=request_id,
        )

    body_dict = payload.model_dump(by_alias=True)
    if payload.options.anonymous and not payload.options.reproducible:
        return _anonymous_without_reproducible_error(request_id=request_id)
    # Story 2.4 — solver validation (FR C4) on /demo as well
    route = select_provider_route("lp", payload.solver)
    if route.status is ProviderRouteStatus.UNAUDITED_SELF_ALGORITHM:
        return _unaudited_self_algorithm_error(
            route,
            field_path="solver" if payload.solver is not None else "task_type",
            request_id=request_id,
        )
    if route.status is ProviderRouteStatus.UNSUPPORTED_TASK_TYPE:
        return _rfc7807_error(
            title="Catalog Error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LP algorithm missing from catalog",
            request_id=request_id,
        )
    if route.status is ProviderRouteStatus.UNSUPPORTED_SOLVER:
        return _rfc7807_error(
            title="Unsupported Solver",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"solver '{payload.solver}' is not supported for task_type 'lp'. "
                f"Supported: {', '.join(route.supported_solvers)}"
            ),
            errors=[
                ErrorDetail(
                    field_path="solver",
                    value=payload.solver,
                    constraint=f"must be one of: {', '.join(route.supported_solvers)}",
                    remediation_hint_key="errors.400.unsupported_solver",
                )
            ],
            next_action="https://api.opticloud.cn/v1/algorithms",
            request_id=request_id,
        )
    assert route.algorithm is not None
    assert route.selected_solver is not None

    # Story 2.5 — FR C5 fallback_chain per-element validation (mirror of authenticated route).
    # Chain is data-only on /demo today; actual fallback execution is Story 2.7.
    if payload.fallback_chain:
        for idx, candidate in enumerate(payload.fallback_chain):
            if candidate not in route.supported_solvers:
                return _rfc7807_error(
                    title="Unsupported Fallback Solver",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"fallback_chain[{idx}]='{candidate}' is not supported for "
                        f"task_type 'lp'. Supported: {', '.join(route.supported_solvers)}"
                    ),
                    errors=[
                        ErrorDetail(
                            field_path=f"fallback_chain[{idx}]",
                            value=candidate,
                            constraint=f"must be one of: {', '.join(route.supported_solvers)}",
                            remediation_hint_key="errors.400.unsupported_fallback_solver",
                        )
                    ],
                    next_action="https://api.opticloud.cn/v1/algorithms",
                    request_id=request_id,
                )

    attempt_plan = build_fallback_attempts(
        primary_route=route,
        task_type="lp",
        requested_solver=payload.solver,
        fallback_chain=payload.fallback_chain,
    )
    if attempt_plan.status is FallbackPlanStatus.UNAUDITED_SELF_ALGORITHM:
        return _unaudited_self_algorithm_error(
            attempt_plan,
            field_path=(
                f"fallback_chain[{attempt_plan.invalid_index}]"
                if attempt_plan.invalid_index is not None
                else "fallback_chain"
            ),
            request_id=request_id,
        )
    if attempt_plan.status is FallbackPlanStatus.INVALID_FALLBACK_SOLVER:
        invalid_idx = attempt_plan.invalid_index if attempt_plan.invalid_index is not None else 0
        supported = attempt_plan.supported_solvers or route.supported_solvers
        invalid_candidate = attempt_plan.invalid_candidate
        return _rfc7807_error(
            title="Unsupported Fallback Solver",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"fallback_chain[{invalid_idx}]='{invalid_candidate}' is not supported for "
                f"task_type 'lp'. Supported: {', '.join(supported)}"
            ),
            errors=[
                ErrorDetail(
                    field_path=f"fallback_chain[{invalid_idx}]",
                    value=invalid_candidate,
                    constraint=f"must be one of: {', '.join(supported)}",
                    remediation_hint_key="errors.400.unsupported_fallback_solver",
                )
            ],
            next_action="https://api.opticloud.cn/v1/algorithms",
            request_id=request_id,
        )

    execution = _execute_fallback_attempts(
        attempts=attempt_plan.attempts,
        task_type="lp",
        body_dict=body_dict,
        max_solve_seconds=payload.options.max_solve_seconds,
        max_fallback_retries=len(payload.fallback_chain or []),
    )
    result = execution.result
    final_attempt = execution.terminal_attempt
    final_route = final_attempt.route
    final_selected_solver = final_route.selected_solver
    assert final_selected_solver is not None

    if result.status == "optimal":
        selected_algorithm = final_route.algorithm
        assert selected_algorithm is not None
        # Story 6.A.1 review patch — route demo citation through CitationSchema
        # for byte-identical shape with the authenticated route.
        demo_citation_raw = selected_algorithm.get("citation")
        demo_citation: dict[str, object] | None = None
        if demo_citation_raw is not None:
            try:
                demo_citation = json.loads(
                    CitationSchema.model_validate(demo_citation_raw).model_dump_json()
                )
            except Exception:
                demo_citation = None
        demo_attribution_raw = selected_algorithm.get("ip_attribution")
        demo_attribution: dict[str, object] | None = None
        if demo_attribution_raw is not None:
            try:
                demo_attribution = json.loads(
                    IPAttributionSchema.model_validate(demo_attribution_raw).model_dump_json()
                )
            except Exception:
                demo_attribution = None
        content = {
            "status": "completed",
            "solution": result.solution,
            "objective": result.objective,
            "model_version": dict(final_route.model_version),
            "solve_seconds": result.solve_seconds,
            "demo": True,
            "citation": demo_citation,
            "ip_attribution": demo_attribution,
        }
        if payload.options.reproducible:
            content["reproducibility"] = _build_reproducibility_payload(
                request_body=body_dict,
                model_version=dict(final_route.model_version),
                locked_solver=final_selected_solver,
                anonymous=payload.options.anonymous,
            )
        return JSONResponse(
            content=content,
            status_code=status.HTTP_200_OK,
        )
    if result.status in ("infeasible", "unbounded"):
        return _rfc7807_error(
            title=f"LP {result.status.capitalize()}",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.error_constraint or result.status,
            request_id=request_id,
        )
    if result.status == "timeout":
        return _rfc7807_error(
            title="Solver Timeout",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=result.error_constraint or "solver exceeded max_solve_seconds",
            errors=[
                ErrorDetail(
                    field_path=result.error_field_path or "options.max_solve_seconds",
                    value=payload.options.max_solve_seconds,
                    constraint=result.error_constraint or "timeout",
                    remediation_hint_key="errors.504.solver_timeout",
                )
            ],
            request_id=request_id,
        )
    return _rfc7807_error(
        title="Solver Error",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=result.error_constraint or "solve failed",
        request_id=request_id,
    )


@router.get(
    "/optimizations/{optimization_id}",
    tags=["execution"],
    summary="查 optimization 状态 (FR E9)",
)
async def get_optimization(
    optimization_id: uuid.UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    client_ip = request.client.host if request.client else None
    user_id, _api_key_id, _scopes = await verify_api_key(
        authorization, session, client_ip=client_ip
    )
    opt = await session.get(Optimization, optimization_id)
    if opt is None or opt.user_id != user_id:
        return _rfc7807_error(
            title="Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"optimization {optimization_id} not found",
        )
    if opt.status == "completed":
        await attach_existing_voucher_id(session, opt)
        return _build_success_response(opt)
    return JSONResponse(
        content={
            "optimization_id": str(opt.id),
            "status": opt.status,
            "error": opt.error,
            "model_version": opt.model_version,
            "created_at": opt.created_at.isoformat() if opt.created_at else None,
            "completed_at": opt.completed_at.isoformat() if opt.completed_at else None,
        },
        status_code=status.HTTP_200_OK,
    )
