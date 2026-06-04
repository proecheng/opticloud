"""Endpoints — FR C1-C8 + E1-E10 (Sprint 0 subset: Story 2.1 + 3.1)."""

from __future__ import annotations

import hashlib
import json
import math
import numbers
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal, cast

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, Response
from opticloud_shared.cost_telemetry import CostTelemetryEvent, CostUnit, record_cost_event
from opticloud_shared.schemas.errors import ErrorDetail
from sqlalchemy import Table, select, text
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from solver_orchestrator import billing_client, rate_limit, solvers
from solver_orchestrator.auth import require_scope, verify_api_key
from solver_orchestrator.benchmark_library import (
    BENCHMARK_LIBRARY_DISCOUNT_KIND,
    BENCHMARK_LIBRARY_DISCOUNT_MULTIPLIER,
    build_import_response,
    find_benchmark_library_item,
    list_benchmark_library,
)
from solver_orchestrator.catalog import (
    CATALOG,
    Citation,
    IPAttribution,
    find_by_k_algo,
    publishable_catalog_items,
    self_audit_passed,
)
from solver_orchestrator.db import get_session
from solver_orchestrator.error_responses import PROBLEM_JSON, build_problem_response
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
from solver_orchestrator.job_templates import (
    TemplateParameterError,
    apply_template_parameter_override,
    build_optimization_template_payload,
    build_prediction_template_payload,
    build_template_payload_from_version_payload,
)
from solver_orchestrator.models import (
    CostAttribution,
    IdempotencyKey,
    JobTemplate,
    Optimization,
    OptimizationBatch,
    OptimizationBatchIdempotencyKey,
    OptimizationBatchItem,
    Prediction,
    PredictionIdempotencyKey,
    ReproductionVoucher,
    TeachingGradingBatch,
    TeachingGradingIdempotencyKey,
    TeachingGradingItem,
)
from solver_orchestrator.provider_routing import (
    ProviderRouteMetadata,
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
    BenchmarkImportResponseSchema,
    BenchmarkLibraryItemSchema,
    CitationSchema,
    IPAttributionSchema,
    JobTemplateCreateRequest,
    JobTemplateDetail,
    JobTemplateListResponse,
    JobTemplateSummary,
    JobTemplateVersionCreateRequest,
    JobTemplateVersionsResponse,
    ModelVersionSchema,
    OptimizationBatchRequest,
    OptimizationRequest,
    OptimizationResponse,
    PredictionQuantiles,
    PredictionRequest,
    PredictionResponse,
    ReproducibilitySchema,
    TeachingGradingBatchCreateRequest,
    TeachingGradingBatchResponse,
    TeachingGradingCriterionResult,
    TeachingGradingItemResponse,
    prediction_disclaimer,
)

router = APIRouter(prefix="/v1")
health_router = APIRouter()
logger: Any = structlog.get_logger("solver_orchestrator.routes")
ASYNC_QUEUE_MESSAGE = "Task queued; background execution is not enabled in Story 3.3"
SYNC_ASYNC_THRESHOLD_SECONDS = 5.0
SOLVER_BUDGET_EPSILON_SECONDS = 1e-9
BACKTEST_DISCOUNT_MULTIPLIER = 0.5
BACKTEST_DISCOUNT_KIND = "backtest"
TEACHING_DISCOUNT_MULTIPLIER = 0.5
TEACHING_DISCOUNT_KIND = "teaching"
TEACHING_NOTEBOOK_REPO_PATH = "docs/notebooks/teaching-lp.ipynb"
TEACHING_NOTEBOOK_COLAB_URL = (
    "https://colab.research.google.com/github/proecheng/opticloud/blob/main/"
    f"{TEACHING_NOTEBOOK_REPO_PATH}"
)
PREDICTION_MAX_ABS_DATA_VALUE = 1_000_000_000_000.0
BATCH_TERMINAL_STATUSES = {"completed", "failed", "timeout", "cancelled"}
BATCH_COUNT_STATUSES = ("queued", "in_progress", "completed", "failed", "timeout", "cancelled")
TEACHING_GRADING_RUBRIC_VERSION = "teaching-grading-v1"
TEACHING_GRADING_MAX_SCORE = Decimal("100.00")
TEACHING_GRADING_CRITERION_POINTS = Decimal("25.00")


@dataclass(frozen=True)
class _PredictionContractViolationError(Exception):
    field: str
    detail: str


@dataclass(frozen=True)
class _BatchValidatedTask:
    body: dict[str, Any]
    model_version: dict[str, Any]
    provider_route: ProviderRouteMetadata
    execution_mode: dict[str, object]


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


# ===== Story 8.C.4: Classic benchmark library (FR O11, no auth) =====


@router.get(
    "/benchmark-library",
    response_model=list[BenchmarkLibraryItemSchema],
    tags=["catalog"],
    summary="列出经典算例库模板（公开免鉴权 FR O11）",
    description=(
        "FR O11: 公开浏览 IEEE/CVRPLIB/OR-Lib/M5/UCI/NAB 经典算例模板。\n\n"
        "Optional filters (combinable): suite, domain, task_type. Unknown filter "
        "values return an empty list."
    ),
)
async def list_benchmark_library_entries(
    suite: str | None = None,
    domain: str | None = None,
    task_type: str | None = None,
) -> list[BenchmarkLibraryItemSchema]:
    items = list_benchmark_library(suite=suite, domain=domain, task_type=task_type)
    return [BenchmarkLibraryItemSchema.model_validate(item) for item in items]


@router.get(
    "/benchmark-library/{benchmark_id}",
    response_model=BenchmarkLibraryItemSchema,
    tags=["catalog"],
    summary="经典算例库详情 (FR O11)",
)
async def get_benchmark_library_entry(benchmark_id: str) -> BenchmarkLibraryItemSchema:
    item = find_benchmark_library_item(benchmark_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown benchmark_id: {benchmark_id}",
        )
    return BenchmarkLibraryItemSchema.model_validate(item)


@router.post(
    "/benchmark-library/{benchmark_id}/import",
    response_model=BenchmarkImportResponseSchema,
    tags=["catalog"],
    summary="生成经典算例库 import payload (FR O11)",
)
async def import_benchmark_library_entry(benchmark_id: str) -> BenchmarkImportResponseSchema:
    imported = build_import_response(benchmark_id)
    if imported is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown benchmark_id: {benchmark_id}",
        )
    return BenchmarkImportResponseSchema.model_validate(imported)


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


def _hash_optimization_body(
    body: dict[str, Any],
    mode: str,
    *,
    billing_charge_id: str | None = None,
) -> str:
    payload: dict[str, Any] = {"body": body, "mode": mode}
    if billing_charge_id is not None:
        payload["billing_charge_id"] = billing_charge_id
    return _hash_body(payload)


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


_PUBLIC_ROUTE_FIELDS = (
    "task_type",
    "requested_solver",
    "selected_solver",
    "provider_id",
    "provider_kind",
    "provider_url",
    "routing_reason",
)
_PUBLIC_ATTEMPT_FIELDS = (
    "attempt",
    "role",
    "requested_solver",
    "selected_solver",
    "provider_id",
    "provider_kind",
    "provider_url",
    "routing_reason",
    "status",
    "retryable",
    "solve_seconds",
)


def _optimization_system_payload(opt: Optimization) -> dict[str, Any]:
    if isinstance(opt.input_payload, dict):
        system_payload = opt.input_payload.get("_system")
        if isinstance(system_payload, dict):
            return system_payload
    return {}


def _public_route_metadata(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    public: dict[str, Any] = {}
    for field in _PUBLIC_ROUTE_FIELDS:
        if field not in value:
            return None
        public[field] = value[field]
    return public


def _public_attempt_metadata(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    public: dict[str, Any] = {}
    for field in _PUBLIC_ATTEMPT_FIELDS:
        if field not in value:
            return None
        public[field] = value[field]
    return public


def _routing_history_metadata(opt: Optimization) -> dict[str, Any] | None:
    system_payload = _optimization_system_payload(opt)
    primary_route = _public_route_metadata(system_payload.get("provider_route"))
    executed_route = _public_route_metadata(system_payload.get("executed_provider_route"))
    fallback_execution = system_payload.get("fallback_execution")
    solve_seconds = float(opt.solve_seconds) if opt.solve_seconds is not None else 0.0

    if isinstance(fallback_execution, dict):
        attempts = [
            public_attempt
            for attempt in fallback_execution.get("attempts", [])
            if (public_attempt := _public_attempt_metadata(attempt)) is not None
        ]
        terminal_attempt_raw = fallback_execution.get("terminal_attempt")
        terminal_attempt = terminal_attempt_raw if isinstance(terminal_attempt_raw, int) else None
        attempt_count = len(attempts)
        if terminal_attempt is not None:
            attempt_count = max(attempt_count, terminal_attempt)
        return {
            "primary_route": primary_route,
            "executed_route": executed_route,
            "summary": {
                "attempt_count": attempt_count,
                "fallback_used": any(attempt.get("role") == "fallback" for attempt in attempts)
                or (terminal_attempt is not None and terminal_attempt > 1),
                "terminal_status": fallback_execution.get("terminal_status")
                if isinstance(fallback_execution.get("terminal_status"), str)
                else None,
                "terminal_attempt": terminal_attempt,
                "exhausted": bool(fallback_execution.get("exhausted", False)),
                "solve_seconds": solve_seconds,
            },
            "attempts": attempts,
        }

    if primary_route is None and executed_route is None:
        return None
    terminal_route = executed_route or primary_route
    if opt.status in {"queued", "in_progress"}:
        return {
            "primary_route": primary_route,
            "executed_route": None,
            "summary": {
                "attempt_count": 0,
                "fallback_used": False,
                "terminal_status": None,
                "terminal_attempt": None,
                "exhausted": False,
                "solve_seconds": 0.0,
            },
            "attempts": [],
        }
    attempts = []
    if terminal_route is not None:
        attempts.append(
            {
                "attempt": 1,
                "role": "primary",
                "requested_solver": terminal_route["requested_solver"],
                "selected_solver": terminal_route["selected_solver"],
                "provider_id": terminal_route["provider_id"],
                "provider_kind": terminal_route["provider_kind"],
                "provider_url": terminal_route["provider_url"],
                "routing_reason": terminal_route["routing_reason"],
                "status": opt.status,
                "retryable": False,
                "solve_seconds": solve_seconds,
            }
        )
    return {
        "primary_route": primary_route,
        "executed_route": executed_route,
        "summary": {
            "attempt_count": len(attempts),
            "fallback_used": False,
            "terminal_status": opt.status,
            "terminal_attempt": 1 if attempts else None,
            "exhausted": False,
            "solve_seconds": solve_seconds,
        },
        "attempts": attempts,
    }


def _build_response_content(
    opt: Optimization,
    *,
    include_routing_history: bool = True,
) -> dict[str, Any]:
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

    public_model_version = _public_model_version(opt.model_version)
    if public_model_version is not None:
        payload = OptimizationResponse(
            optimization_id=opt.id,
            status="completed",
            solution=opt.solution,
            objective=float(opt.objective) if opt.objective is not None else None,
            model_version=public_model_version,  # type: ignore[arg-type]
            solve_seconds=float(opt.solve_seconds) if opt.solve_seconds is not None else 0.0,
            created_at=opt.created_at,
            completed_at=opt.completed_at or opt.created_at,
            citation=citation_payload,
            ip_attribution=attribution_payload,
        )
        content: dict[str, Any] = json.loads(payload.model_dump_json())
    else:
        content = {
            "optimization_id": str(opt.id),
            "status": "completed",
            "solution": opt.solution,
            "objective": float(opt.objective) if opt.objective is not None else None,
            "model_version": None,
            "solve_seconds": float(opt.solve_seconds) if opt.solve_seconds is not None else 0.0,
            "created_at": _status_datetime(opt.created_at),
            "completed_at": _status_datetime(opt.completed_at or opt.created_at),
            "citation": (
                json.loads(citation_payload.model_dump_json())
                if citation_payload is not None
                else None
            ),
            "ip_attribution": (
                json.loads(attribution_payload.model_dump_json())
                if attribution_payload is not None
                else None
            ),
        }
    content["model_version"] = public_model_version
    content.update(_status_progress_fields(opt))
    system_payload = _optimization_system_payload(opt)
    reproducibility = system_payload.get("reproducibility")
    if isinstance(reproducibility, dict):
        content["reproducibility"] = reproducibility
    top_k = system_payload.get("top_k_alternatives")
    if isinstance(top_k, dict):
        alternatives = top_k.get("alternatives")
        requested = top_k.get("requested")
        returned = top_k.get("returned")
        if isinstance(alternatives, list) and isinstance(requested, int):
            content["top_k_alternatives_requested"] = requested
            content["top_k_alternatives_returned"] = (
                returned if isinstance(returned, int) else len(alternatives)
            )
            content["alternatives"] = alternatives
    teaching = system_payload.get("teaching")
    if isinstance(teaching, dict):
        content["teaching"] = teaching
    if include_routing_history:
        routing_history = _routing_history_metadata(opt)
        if routing_history is not None:
            content["routing_history"] = routing_history
    return content


def _status_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _optimization_execution_mode(opt: Optimization) -> dict[str, Any]:
    if isinstance(opt.input_payload, dict):
        system_payload = opt.input_payload.get("_system")
        if isinstance(system_payload, dict):
            execution_mode = system_payload.get("execution_mode")
            if isinstance(execution_mode, dict):
                return execution_mode
    return {}


def _optimization_billing_metadata(opt: Optimization) -> dict[str, Any]:
    if isinstance(opt.input_payload, dict):
        system_payload = opt.input_payload.get("_system")
        if isinstance(system_payload, dict):
            billing_metadata = system_payload.get("billing")
            if isinstance(billing_metadata, dict):
                return dict(billing_metadata)
    return {}


def _optimization_teaching_metadata(opt: Optimization) -> dict[str, Any]:
    if isinstance(opt.input_payload, dict):
        system_payload = opt.input_payload.get("_system")
        if isinstance(system_payload, dict):
            teaching_metadata = system_payload.get("teaching")
            if isinstance(teaching_metadata, dict):
                return dict(teaching_metadata)
    return {}


def _backtest_billing_discount_metadata(payload: OptimizationRequest) -> dict[str, Any] | None:
    if not payload.options.backtest:
        return None
    return {
        "discount_kind": BACKTEST_DISCOUNT_KIND,
        "discount_multiplier": BACKTEST_DISCOUNT_MULTIPLIER,
    }


def _optimization_billing_discount_metadata(
    payload: OptimizationRequest,
    *,
    teaching_enabled: bool,
) -> dict[str, Any] | None:
    if teaching_enabled:
        return {
            "discount_kind": TEACHING_DISCOUNT_KIND,
            "discount_multiplier": TEACHING_DISCOUNT_MULTIPLIER,
        }
    if payload.options.benchmark_library:
        return {
            "discount_kind": BENCHMARK_LIBRARY_DISCOUNT_KIND,
            "discount_multiplier": BENCHMARK_LIBRARY_DISCOUNT_MULTIPLIER,
        }
    return _backtest_billing_discount_metadata(payload)


def _invalid_benchmark_library_option_response(
    *,
    detail: str,
    field_path: str,
    value: Any,
    constraint: str,
    request_id: str | None = None,
) -> JSONResponse:
    return _rfc7807_error(
        title="Invalid Benchmark Library Option",
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
        errors=[
            ErrorDetail(
                field_path=field_path,
                value=value,
                constraint=constraint,
                remediation_hint_key="errors.400.invalid_benchmark_library_option",
            )
        ],
        next_action="https://api.opticloud.cn/v1/benchmark-library",
        request_id=request_id,
    )


def _validate_benchmark_library_options(
    payload: OptimizationRequest,
    *,
    request_id: str | None,
) -> JSONResponse | None:
    benchmark_id = payload.options.benchmark_id
    if not payload.options.benchmark_library:
        if benchmark_id is not None:
            return _invalid_benchmark_library_option_response(
                detail="options.benchmark_id requires options.benchmark_library=true",
                field_path="options.benchmark_id",
                value=benchmark_id,
                constraint="must be omitted unless benchmark_library is true",
                request_id=request_id,
            )
        return None

    if benchmark_id is None or not benchmark_id.strip():
        return _invalid_benchmark_library_option_response(
            detail="options.benchmark_library=true requires a non-empty options.benchmark_id",
            field_path="options.benchmark_id",
            value=benchmark_id,
            constraint="must reference a published optimization benchmark library entry",
            request_id=request_id,
        )

    entry = find_benchmark_library_item(benchmark_id)
    if entry is None:
        return _invalid_benchmark_library_option_response(
            detail=f"unknown benchmark library id: {benchmark_id}",
            field_path="options.benchmark_id",
            value=benchmark_id,
            constraint="must reference a published benchmark library entry",
            request_id=request_id,
        )
    if (
        entry["import_kind"] != "optimization_request"
        or entry["target_endpoint"] != "/v1/optimizations"
    ):
        return _invalid_benchmark_library_option_response(
            detail=f"benchmark library id '{benchmark_id}' is not eligible for optimization billing",
            field_path="options.benchmark_id",
            value=benchmark_id,
            constraint="must be an optimization_request entry targeting /v1/optimizations",
            request_id=request_id,
        )
    if entry["task_type"] != payload.task_type:
        return _invalid_benchmark_library_option_response(
            detail=(
                f"benchmark library id '{benchmark_id}' has task_type "
                f"'{entry['task_type']}', not '{payload.task_type}'"
            ),
            field_path="options.benchmark_id",
            value=benchmark_id,
            constraint=f"must match request task_type '{payload.task_type}'",
            request_id=request_id,
        )
    return None


def _teaching_metadata(
    *,
    task_type: str,
    selected_solver: str | None,
) -> dict[str, Any]:
    solver_label = selected_solver or "platform-default"
    if task_type == "lp":
        principle = {
            "title_zh": "线性规划教学模式",
            "summary_zh": (
                "线性规划通过线性目标函数和线性约束描述资源分配问题，"
                f"当前示例使用 {solver_label} 求解标准 LP。"
            ),
            "modeling_steps_zh": [
                "定义决策变量，例如每个产品、路线或资源的取值。",
                "写出线性目标函数，说明需要最小化成本或最大化收益。",
                "把业务限制写成线性不等式或等式约束，并检查量纲一致性。",
                "求解后验证最优解是否满足约束，再解释影子价格或松弛量。",
            ],
            "limitations_zh": [
                "教学模式只解释线性模型，不替代对非线性、整数变量或真实生产约束的建模审查。",
                "小规模教材算例适合课堂演示；真实生产数据仍应使用生产模式和标准计费边界。",
            ],
        }
    else:
        principle = {
            "title_zh": "优化任务教学模式",
            "summary_zh": (
                f"教学模式返回算法原理、折扣资格和 Notebook 入口；当前任务类型为 {task_type}。"
            ),
            "modeling_steps_zh": [
                "明确决策变量和输入数据边界。",
                "写出目标函数和业务约束。",
                "用小规模算例先验证模型含义，再扩大到真实数据。",
            ],
            "limitations_zh": [
                "当前教学 Notebook 首先覆盖 LP 示例；其他任务类型的专用 Notebook 会在后续 story 扩展。"
            ],
        }
    return {
        "mode": "teaching",
        "principle_explanation": principle,
        "credits_discount": {
            "kind": TEACHING_DISCOUNT_KIND,
            "label_zh": "50% Credits 折扣",
            "discount_multiplier": TEACHING_DISCOUNT_MULTIPLIER,
        },
        "notebook": {
            "label_zh": "LP 教学 Notebook",
            "repo_path": TEACHING_NOTEBOOK_REPO_PATH,
            "colab_url": TEACHING_NOTEBOOK_COLAB_URL,
        },
    }


def _optimization_progress_metadata(opt: Optimization) -> dict[str, Any]:
    if isinstance(opt.input_payload, dict):
        system_payload = opt.input_payload.get("_system")
        if isinstance(system_payload, dict):
            progress_metadata = system_payload.get("progress")
            if isinstance(progress_metadata, dict):
                return dict(progress_metadata)
    return {}


def _normalize_progress_pct(value: Any, *, max_value: int = 100) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        return 0
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        return 0
    return max(0, min(max_value, int(numeric_value)))


def _normalize_eta_seconds(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        return None
    numeric_value = float(value)
    if not math.isfinite(numeric_value) or numeric_value < 0:
        return None
    return int(numeric_value)


def _public_model_version(value: Any) -> dict[str, Any] | None:
    try:
        payload = ModelVersionSchema.model_validate(value)
    except Exception:
        return None
    public_payload = json.loads(payload.model_dump_json())
    if not isinstance(public_payload, dict):
        return None
    return public_payload


def _status_progress_fields(opt: Optimization) -> dict[str, int | None]:
    progress = _optimization_progress_metadata(opt)
    if opt.status == "completed":
        return {"progress_pct": 100, "eta_seconds": 0}
    if opt.status == "in_progress":
        return {
            "progress_pct": _normalize_progress_pct(progress.get("progress_pct"), max_value=99),
            "eta_seconds": _normalize_eta_seconds(progress.get("eta_seconds")),
        }
    if opt.status in {"failed", "timeout", "cancelled"}:
        return {
            "progress_pct": _normalize_progress_pct(progress.get("progress_pct")),
            "eta_seconds": None,
        }
    return {"progress_pct": 0, "eta_seconds": None}


def _set_optimization_billing_metadata(
    opt: Optimization,
    updates: dict[str, Any],
) -> dict[str, Any]:
    existing = _optimization_billing_metadata(opt)
    existing.update(updates)
    opt.input_payload = _attach_system_metadata(opt.input_payload, billing=existing)
    return existing


def _redact_status_error(error: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(error, dict):
        return error
    redacted = dict(error)
    if "billing_charge_id" in redacted:
        redacted["billing_charge_id"] = "[redacted]"
    return redacted


def _refund_status_from_optimization(opt: Optimization) -> str:
    billing_metadata = _optimization_billing_metadata(opt)
    raw = billing_metadata.get("refund_status")
    if isinstance(raw, str) and raw:
        return raw
    if opt.error and isinstance(opt.error, dict):
        raw = opt.error.get("refund_status")
        if isinstance(raw, str) and raw:
            return raw
    return "not_applicable" if not billing_metadata.get("reserved") else "pending_reconciliation"


def _build_optimization_status_response_content(
    opt: Optimization,
    *,
    include_routing_history: bool = True,
) -> dict[str, Any]:
    execution_mode = _optimization_execution_mode(opt)
    teaching = _optimization_teaching_metadata(opt)
    content: dict[str, Any] = {
        "optimization_id": str(opt.id),
        "status": opt.status,
        "model_version": _public_model_version(opt.model_version),
        "created_at": _status_datetime(opt.created_at),
        "completed_at": _status_datetime(opt.completed_at),
    }
    if teaching:
        content["teaching"] = teaching
    if include_routing_history:
        routing_history = _routing_history_metadata(opt)
        if routing_history is not None:
            content["routing_history"] = routing_history
    content.update(_status_progress_fields(opt))
    effective_mode = execution_mode.get("effective_mode")
    if effective_mode is not None:
        content["mode"] = effective_mode
    if opt.status in {"queued", "in_progress"}:
        content.update(
            {
                "mode": effective_mode or "async",
                "message": ASYNC_QUEUE_MESSAGE,
            }
        )
    else:
        content["error"] = _redact_status_error(opt.error)
        if opt.status == "timeout":
            content["solve_seconds"] = (
                float(opt.solve_seconds) if opt.solve_seconds is not None else 0.0
            )
            content["best_solution_available"] = opt.solution is not None
            if opt.solution is not None:
                content["best_solution"] = opt.solution
            if opt.objective is not None:
                content["objective"] = float(opt.objective)
        elif opt.status == "cancelled":
            content["mode"] = effective_mode or "async"
            content["refund_status"] = _refund_status_from_optimization(opt)
            content["message"] = "Optimization cancelled"
    return content


def _build_async_accepted_response(opt: Optimization) -> JSONResponse:
    content = _build_optimization_status_response_content(opt)
    execution_mode = _optimization_execution_mode(opt)
    content.pop("completed_at", None)
    content.update(
        {
            "mode": "async",
            "requested_mode": execution_mode.get("requested_mode", "async"),
            "auto_async": bool(execution_mode.get("auto_async", False)),
            "estimated_seconds": float(execution_mode.get("estimated_seconds", 0.0)),
        }
    )
    return JSONResponse(
        content=content,
        status_code=status.HTTP_202_ACCEPTED,
        headers={"Location": f"/v1/optimizations/{opt.id}"},
    )


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


def _top_k_metadata_from_result(
    result: solvers.LPSolveResult,
    *,
    requested: int,
) -> dict[str, Any] | None:
    if requested <= 1 or result.status != "optimal" or not result.alternatives:
        return None
    return {
        "strategy": solvers.TOP_K_STRATEGY,
        "requested": int(requested),
        "returned": len(result.alternatives),
        "alternatives": result.alternatives,
    }


def _attach_top_k_metadata(
    opt: Optimization,
    result: solvers.LPSolveResult,
    *,
    requested: int,
) -> None:
    metadata = _top_k_metadata_from_result(result, requested=requested)
    if metadata is not None:
        opt.input_payload = _attach_system_metadata(
            opt.input_payload,
            top_k_alternatives=metadata,
        )


def _add_top_k_to_content(
    content: dict[str, Any],
    result: solvers.LPSolveResult,
    *,
    requested: int,
) -> None:
    metadata = _top_k_metadata_from_result(result, requested=requested)
    if metadata is None:
        return
    content["top_k_alternatives_requested"] = metadata["requested"]
    content["top_k_alternatives_returned"] = metadata["returned"]
    content["alternatives"] = metadata["alternatives"]


def _rfc7807_error(
    *,
    title: str,
    status_code: int,
    detail: str,
    errors: list[ErrorDetail] | None = None,
    next_action: str | None = None,
    request_id: str | None = None,
    headers: dict[str, str] | None = None,
    error_key: str | None = None,
) -> JSONResponse:
    """Build RFC 7807 + errors[] response (FG1.3)."""
    return build_problem_response(
        title=title,
        status_code=status_code,
        detail=detail,
        errors=errors,
        next_action=next_action,
        request_id=request_id,
        headers=headers,
        error_key=error_key,
    )


def _rate_limit_headers(decision: rate_limit.RateLimitDecision) -> dict[str, str]:
    return {
        "X-RateLimit-Limit": str(decision.limit),
        "X-RateLimit-Remaining": str(decision.remaining),
        "X-RateLimit-Reset": str(decision.reset_epoch_seconds),
        "Retry-After": str(decision.retry_after_seconds),
    }


def _rate_limit_response(
    decision: rate_limit.RateLimitDecision, *, request_id: str | None = None
) -> JSONResponse:
    return _rfc7807_error(
        title="Rate Limit Exceeded",
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"current {decision.plan_code} plan allows {decision.limit} requests per {decision.window_seconds}s window",
        error_key="rate_limit_exceeded",
        errors=[
            ErrorDetail(
                field_path="rate_limit",
                value=decision.plan_code,
                constraint=f"limit {decision.limit} requests per {decision.window_seconds}s",
                remediation_hint_key="errors.429.rate_limit_exceeded",
            )
        ],
        request_id=request_id,
        headers=_rate_limit_headers(decision),
    )


def _rate_limit_unavailable_response(*, request_id: str | None = None) -> JSONResponse:
    return _rfc7807_error(
        title="Rate Limit Unavailable",
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="rate limit backend is unavailable",
        error_key="rate_limit_unavailable",
        errors=[
            ErrorDetail(
                field_path="rate_limit",
                value="[omitted]",
                constraint="rate limit backend must be available before execution",
                remediation_hint_key="errors.503.rate_limit_unavailable",
            )
        ],
        request_id=request_id,
    )


async def _rate_limit_or_response(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    request_id: str | None = None,
) -> JSONResponse | None:
    try:
        await rate_limit.enforce_rate_limit(session=session, user_id=user_id)
    except rate_limit.RateLimitExceededError as exc:
        return _rate_limit_response(exc.decision, request_id=request_id)
    except rate_limit.RateLimitUnavailableError:
        return _rate_limit_unavailable_response(request_id=request_id)
    return None


def _idempotency_conflict_response(
    *,
    idempotency_key: str,
    detail: str = "same idempotency key with different request body (P23)",
    constraint: str = "reused with different body",
    request_id: str | None = None,
) -> JSONResponse:
    return _rfc7807_error(
        title="Idempotency Conflict",
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
        errors=[
            ErrorDetail(
                field_path="header.Idempotency-Key",
                value=idempotency_key,
                constraint=constraint,
                remediation_hint_key="errors.409.idempotency_body_mismatch",
            )
        ],
        request_id=request_id,
    )


def _job_template_summary_model(template: JobTemplate) -> JobTemplateSummary:
    return JobTemplateSummary(
        id=template.id,
        name=template.name,
        description=template.description,
        source_kind=template.source_kind,  # type: ignore[arg-type]
        source_id=template.source_id,
        task_type=template.task_type,
        payload_schema_version=template.payload_schema_version,  # type: ignore[arg-type]
        payload_sha256=template.payload_sha256,
        version=template.version,
        root_template_id=template.root_template_id,
        parent_template_id=template.parent_template_id,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _job_template_detail_model(template: JobTemplate) -> JobTemplateDetail:
    return JobTemplateDetail(
        **_job_template_summary_model(template).model_dump(),
        payload_json=template.payload_json,
    )


def _job_template_response(template: JobTemplate, *, detail: bool) -> dict[str, Any]:
    model = (
        _job_template_detail_model(template) if detail else _job_template_summary_model(template)
    )
    content = json.loads(model.model_dump_json())
    if not isinstance(content, dict):
        raise ValueError("job template response did not encode an object")
    return content


async def _find_active_job_template(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    source_kind: str,
    source_id: uuid.UUID,
    name: str,
) -> JobTemplate | None:
    result = await session.execute(
        select(JobTemplate).where(
            JobTemplate.user_id == user_id,
            JobTemplate.source_kind == source_kind,
            JobTemplate.source_id == source_id,
            JobTemplate.name == name,
            JobTemplate.parent_template_id.is_(None),
            JobTemplate.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def _insert_job_template_or_existing(
    session: AsyncSession,
    *,
    values: dict[str, Any],
    user_id: uuid.UUID,
    source_kind: str,
    source_id: uuid.UUID,
    name: str,
) -> tuple[JobTemplate, bool]:
    table = cast(Table, JobTemplate.__table__)
    for _attempt in range(2):
        insert_result = await session.execute(
            postgresql_insert(table)
            .values(**values)
            .on_conflict_do_nothing(
                index_elements=[
                    table.c.user_id,
                    table.c.source_kind,
                    table.c.source_id,
                    table.c.name,
                ],
                index_where=table.c.deleted_at.is_(None) & table.c.parent_template_id.is_(None),
            )
            .returning(table.c.id)
        )
        inserted_id = insert_result.scalar_one_or_none()
        if inserted_id is not None:
            inserted = await session.get(JobTemplate, inserted_id)
            if inserted is None:
                raise RuntimeError("inserted job template row could not be loaded")
            return inserted, True

        existing = await _find_active_job_template(
            session,
            user_id=user_id,
            source_kind=source_kind,
            source_id=source_id,
            name=name,
        )
        if existing is not None:
            return existing, False

    raise RuntimeError("job template insert conflict could not be resolved")


async def _get_owned_active_job_template(
    session: AsyncSession,
    *,
    template_id: uuid.UUID,
    user_id: uuid.UUID,
) -> JobTemplate | None:
    result = await session.execute(
        select(JobTemplate).where(
            JobTemplate.id == template_id,
            JobTemplate.user_id == user_id,
            JobTemplate.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def _next_job_template_version(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    root_template_id: uuid.UUID,
) -> int:
    result = await session.execute(
        select(JobTemplate.version)
        .where(
            JobTemplate.user_id == user_id,
            JobTemplate.root_template_id == root_template_id,
        )
        .order_by(JobTemplate.version.desc())
        .limit(1)
    )
    current = result.scalar_one_or_none()
    return int(current or 0) + 1


def _job_template_lineage_lock_keys(
    *, user_id: uuid.UUID, root_template_id: uuid.UUID
) -> tuple[int, int]:
    value = user_id.int ^ root_template_id.int
    first = (value >> 32) & 0xFFFFFFFF
    second = value & 0xFFFFFFFF

    def _signed_32(part: int) -> int:
        return part - 0x100000000 if part >= 0x80000000 else part

    return _signed_32(first), _signed_32(second)


async def _insert_job_template_version(
    session: AsyncSession,
    *,
    values: dict[str, Any],
    user_id: uuid.UUID,
    root_template_id: uuid.UUID,
) -> JobTemplate:
    table = cast(Table, JobTemplate.__table__)
    lock_key_1, lock_key_2 = _job_template_lineage_lock_keys(
        user_id=user_id, root_template_id=root_template_id
    )
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key_1, :lock_key_2)"),
        {"lock_key_1": lock_key_1, "lock_key_2": lock_key_2},
    )
    for _attempt in range(3):
        next_version = await _next_job_template_version(
            session, user_id=user_id, root_template_id=root_template_id
        )
        row_values = {**values, "version": next_version}
        insert_result = await session.execute(
            postgresql_insert(table)
            .values(**row_values)
            .on_conflict_do_nothing(
                index_elements=[table.c.user_id, table.c.root_template_id, table.c.version],
                index_where=table.c.deleted_at.is_(None),
            )
            .returning(table.c.id)
        )
        inserted_id = insert_result.scalar_one_or_none()
        if inserted_id is None:
            continue
        inserted = await session.get(JobTemplate, inserted_id)
        if inserted is None:
            raise RuntimeError("inserted job template version row could not be loaded")
        return inserted
    raise RuntimeError("job template version insert conflict could not be resolved")


def _validate_template_optimization_payload(
    payload_json: dict[str, Any],
    *,
    request_id: str | None,
) -> JSONResponse | None:
    try:
        payload = OptimizationRequest.model_validate(payload_json)
    except Exception as exc:
        return _invalid_job_template_response(
            field_path="value",
            value="[omitted]",
            constraint=f"resulting optimization payload is invalid: {exc}",
            request_id=request_id,
        )

    if payload.options.anonymous and not payload.options.reproducible:
        return _anonymous_without_reproducible_error(request_id=request_id)

    route = select_provider_route(payload.task_type, payload.solver)
    route_error = _provider_route_error_response(
        route,
        task_type=payload.task_type,
        requested_solver=payload.solver,
        request_id=request_id,
    )
    if route_error is not None:
        return route_error

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
    return None


def _validate_template_version_payload(
    *,
    source_kind: str,
    payload_json: dict[str, Any],
    request_id: str | None,
) -> JSONResponse | None:
    if source_kind == "prediction":
        try:
            payload = PredictionRequest.model_validate(payload_json)
        except Exception as exc:
            return _invalid_job_template_response(
                field_path="value",
                value="[omitted]",
                constraint=f"resulting prediction payload is invalid: {exc}",
                request_id=request_id,
            )
        _, validation_error = _validate_prediction_payload(payload, request_id=request_id)
        return validation_error
    if source_kind == "optimization":
        return _validate_template_optimization_payload(payload_json, request_id=request_id)
    return _invalid_job_template_response(
        field_path="source_kind",
        value=source_kind,
        constraint="source_kind must be optimization or prediction",
        request_id=request_id,
    )


def _job_template_not_found_response(*, request_id: str | None = None) -> JSONResponse:
    return _rfc7807_error(
        title="Not Found",
        status_code=status.HTTP_404_NOT_FOUND,
        detail="job template or source task not found",
        request_id=request_id,
    )


def _source_task_not_completed_response(
    *,
    source_id: uuid.UUID,
    source_status: str,
    request_id: str | None,
) -> JSONResponse:
    return _rfc7807_error(
        title="Source Task Not Completed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"source task status is '{source_status}', expected 'completed'",
        errors=[
            ErrorDetail(
                field_path="source_id",
                value=str(source_id),
                constraint="source task status must be completed",
                remediation_hint_key="errors.422.source_task_not_completed",
            )
        ],
        request_id=request_id,
    )


def _invalid_job_template_response(
    *,
    field_path: str,
    value: object,
    constraint: str,
    request_id: str | None,
) -> JSONResponse:
    return _rfc7807_error(
        title="Invalid Request Body",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=constraint,
        errors=[
            ErrorDetail(
                field_path=field_path,
                value=value,
                constraint=constraint,
                remediation_hint_key="errors.422.invalid_request_body",
            )
        ],
        request_id=request_id,
    )


def _normalized_template_name(
    payload: JobTemplateCreateRequest, *, request_id: str | None
) -> tuple[str | None, JSONResponse | None]:
    name = payload.name.strip()
    if not name:
        return None, _invalid_job_template_response(
            field_path="name",
            value=payload.name,
            constraint="name must not be blank",
            request_id=request_id,
        )
    return name, None


def _normalized_template_description(description: str | None) -> str | None:
    if description is None:
        return None
    normalized = description.strip()
    return normalized or None


def _hash_teaching_grading_body(payload: TeachingGradingBatchCreateRequest) -> str:
    return _hash_body(json.loads(payload.model_dump_json()))


def _teaching_grading_not_found_response(*, request_id: str | None = None) -> JSONResponse:
    return _rfc7807_error(
        title="Not Found",
        status_code=status.HTTP_404_NOT_FOUND,
        detail="teaching grading batch not found",
        request_id=request_id,
    )


async def _load_teaching_grading_batch(
    session: AsyncSession,
    *,
    batch_id: uuid.UUID,
    user_id: uuid.UUID,
) -> TeachingGradingBatch | None:
    result = await session.execute(
        select(TeachingGradingBatch).where(
            TeachingGradingBatch.id == batch_id,
            TeachingGradingBatch.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _load_teaching_grading_items(
    session: AsyncSession,
    *,
    batch_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[TeachingGradingItem]:
    result = await session.execute(
        select(TeachingGradingItem)
        .where(
            TeachingGradingItem.grading_batch_id == batch_id,
            TeachingGradingItem.user_id == user_id,
        )
        .order_by(TeachingGradingItem.item_index.asc())
    )
    return list(result.scalars().all())


def _teaching_grading_item_model(item: TeachingGradingItem) -> TeachingGradingItemResponse:
    return TeachingGradingItemResponse(
        index=item.item_index,
        student_ref=item.student_ref,
        optimization_id=item.optimization_id,
        grading_status=cast(Any, item.grading_status),
        score=float(item.score),
        max_score=float(item.max_score),
        criteria=[
            TeachingGradingCriterionResult.model_validate(criterion) for criterion in item.criteria
        ],
        feedback_zh=item.feedback_zh,
    )


async def _teaching_grading_response(
    session: AsyncSession,
    *,
    batch: TeachingGradingBatch,
) -> dict[str, Any]:
    items = await _load_teaching_grading_items(session, batch_id=batch.id, user_id=batch.user_id)
    model = TeachingGradingBatchResponse(
        grading_batch_id=batch.id,
        assignment_ref=batch.assignment_ref,
        rubric_version=cast(Any, batch.rubric_version),
        item_count=batch.item_count,
        graded_count=batch.graded_count,
        not_gradable_count=batch.not_gradable_count,
        created_at=batch.created_at,
        items=[_teaching_grading_item_model(item) for item in items],
    )
    content = json.loads(model.model_dump_json())
    if not isinstance(content, dict):
        raise ValueError("teaching grading response did not encode an object")
    return content


def _criterion_result(
    *,
    code: str,
    label_zh: str,
    passed: bool,
    points: Decimal,
) -> dict[str, Any]:
    return {
        "code": code,
        "label_zh": label_zh,
        "passed": passed,
        "points": float(points),
        "max_points": float(TEACHING_GRADING_CRITERION_POINTS),
    }


def _build_teaching_grading_result(
    opt: Optimization | None,
) -> tuple[str, Decimal, list[dict[str, Any]], str, uuid.UUID | None]:
    teaching = _optimization_teaching_metadata(opt) if opt is not None else {}
    teaching_mode = bool(teaching.get("mode") == "teaching")
    completed_status = bool(opt is not None and opt.status == "completed")
    solution_available = bool(opt is not None and opt.solution is not None)
    explanation = teaching.get("principle_explanation") if isinstance(teaching, dict) else None
    explanation_ready = bool(
        isinstance(explanation, dict)
        and isinstance(explanation.get("summary_zh"), str)
        and explanation["summary_zh"].strip()
    )
    can_grade = teaching_mode and completed_status and solution_available and explanation_ready
    if not can_grade:
        criteria = [
            _criterion_result(
                code="teaching_mode",
                label_zh="Teaching Mode 元数据",
                passed=False,
                points=Decimal("0.00"),
            ),
            _criterion_result(
                code="completed_status",
                label_zh="任务已完成",
                passed=False,
                points=Decimal("0.00"),
            ),
            _criterion_result(
                code="solution_available",
                label_zh="解结果可用",
                passed=False,
                points=Decimal("0.00"),
            ),
            _criterion_result(
                code="explanation_ready",
                label_zh="教学解释可复核",
                passed=False,
                points=Decimal("0.00"),
            ),
        ]
        return (
            "not_gradable",
            Decimal("0.00"),
            criteria,
            "该 opaque student_ref 对应的提交当前不可自动评分。",
            opt.id if opt is not None else None,
        )

    flags = (
        ("teaching_mode", "Teaching Mode 元数据", teaching_mode),
        ("completed_status", "任务已完成", completed_status),
        ("solution_available", "解结果可用", solution_available),
        ("explanation_ready", "教学解释可复核", explanation_ready),
    )
    criteria = [
        _criterion_result(
            code=code,
            label_zh=label,
            passed=passed,
            points=TEACHING_GRADING_CRITERION_POINTS if passed else Decimal("0.00"),
        )
        for code, label, passed in flags
    ]
    score = sum(
        (Decimal(str(criterion["points"])) for criterion in criteria),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))
    assert opt is not None
    return (
        "graded",
        score,
        criteria,
        "已按 teaching-grading-v1 自动评分；仅记录评分摘要，不含原始提交或解向量。",
        opt.id,
    )


async def _load_owner_optimization(
    session: AsyncSession,
    *,
    optimization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Optimization | None:
    opt = await session.get(Optimization, optimization_id)
    if opt is None or opt.user_id != user_id:
        return None
    return opt


async def _load_teaching_grading_idempotency_replay(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    idempotency_key: str,
    request_body_hash: str,
) -> tuple[TeachingGradingBatch | None, bool]:
    result = await session.execute(
        select(TeachingGradingIdempotencyKey).where(
            TeachingGradingIdempotencyKey.user_id == user_id,
            TeachingGradingIdempotencyKey.key == idempotency_key,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        return None, False
    if existing.request_body_hash != request_body_hash:
        return None, True
    batch = await _load_teaching_grading_batch(
        session, batch_id=existing.grading_batch_id, user_id=user_id
    )
    return batch, False


@router.post(
    "/teaching/grading-batches",
    tags=["execution"],
    summary="创建 Teaching Mode grading batch (Story 8.C.9)",
)
async def create_teaching_grading_batch(
    payload: TeachingGradingBatchCreateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    client_ip = request.client.host if request.client else None
    user_id, api_key_id, scopes = await verify_api_key(authorization, session, client_ip=client_ip)
    require_scope("optimize:write", scopes)
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request_body_hash = _hash_teaching_grading_body(payload)
    if idempotency_key:
        replay_batch, conflict = await _load_teaching_grading_idempotency_replay(
            session,
            user_id=user_id,
            idempotency_key=idempotency_key,
            request_body_hash=request_body_hash,
        )
        if conflict:
            return _idempotency_conflict_response(
                idempotency_key=idempotency_key,
                request_id=request_id,
            )
        if replay_batch is not None:
            return JSONResponse(
                content=await _teaching_grading_response(session, batch=replay_batch),
                status_code=status.HTTP_200_OK,
            )

    batch = TeachingGradingBatch(
        user_id=user_id,
        api_key_id=api_key_id,
        assignment_ref=payload.assignment_ref,
        rubric_version=payload.rubric_version,
        item_count=len(payload.submissions),
        graded_count=0,
        not_gradable_count=0,
    )
    session.add(batch)
    await session.flush()

    graded_count = 0
    not_gradable_count = 0
    for index, submission in enumerate(payload.submissions):
        opt = await _load_owner_optimization(
            session,
            optimization_id=submission.optimization_id,
            user_id=user_id,
        )
        grading_status, score, criteria, feedback_zh, gradable_optimization_id = (
            _build_teaching_grading_result(opt)
        )
        if grading_status == "graded":
            graded_count += 1
        else:
            not_gradable_count += 1
        session.add(
            TeachingGradingItem(
                grading_batch_id=batch.id,
                user_id=user_id,
                item_index=index,
                student_ref=submission.student_ref,
                optimization_id=submission.optimization_id,
                gradable_optimization_id=gradable_optimization_id,
                grading_status=grading_status,
                score=score,
                max_score=TEACHING_GRADING_MAX_SCORE,
                criteria=criteria,
                feedback_zh=feedback_zh,
            )
        )

    batch.graded_count = graded_count
    batch.not_gradable_count = not_gradable_count
    if idempotency_key:
        session.add(
            TeachingGradingIdempotencyKey(
                key=idempotency_key,
                user_id=user_id,
                grading_batch_id=batch.id,
                request_body_hash=request_body_hash,
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
        )

    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return _idempotency_conflict_response(
            idempotency_key=idempotency_key or "",
            detail="failed to persist teaching grading batch atomically",
            constraint="batch, items and idempotency key must be unique",
            request_id=request_id,
        )
    await session.refresh(batch)
    return JSONResponse(
        content=await _teaching_grading_response(session, batch=batch),
        status_code=status.HTTP_201_CREATED,
    )


@router.get(
    "/teaching/grading-batches/{grading_batch_id}",
    tags=["execution"],
    summary="读取 Teaching Mode grading batch (Story 8.C.9)",
)
async def get_teaching_grading_batch(
    grading_batch_id: uuid.UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    client_ip = request.client.host if request.client else None
    user_id, _api_key_id, scopes = await verify_api_key(authorization, session, client_ip=client_ip)
    require_scope("optimize:write", scopes)
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    batch = await _load_teaching_grading_batch(
        session,
        batch_id=grading_batch_id,
        user_id=user_id,
    )
    if batch is None:
        return _teaching_grading_not_found_response(request_id=request_id)
    return JSONResponse(
        content=await _teaching_grading_response(session, batch=batch),
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/job-templates",
    tags=["execution"],
    summary="保存成功任务为 job template (FR B11 / Story 5.D.3)",
)
async def create_job_template(
    payload: JobTemplateCreateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    client_ip = request.client.host if request.client else None
    user_id, _api_key_id, scopes = await verify_api_key(authorization, session, client_ip=client_ip)
    require_scope("optimize:write", scopes)
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    rate_limit_error = await _rate_limit_or_response(
        session=session, user_id=user_id, request_id=request_id
    )
    if rate_limit_error is not None:
        return rate_limit_error

    name, name_error = _normalized_template_name(payload, request_id=request_id)
    if name_error is not None:
        return name_error
    assert name is not None
    description = _normalized_template_description(payload.description)

    existing = await _find_active_job_template(
        session,
        user_id=user_id,
        source_kind=payload.source_kind,
        source_id=payload.source_id,
        name=name,
    )
    if existing is not None:
        return JSONResponse(
            content=_job_template_response(existing, detail=True),
            status_code=status.HTTP_200_OK,
        )

    template_payload = None
    if payload.source_kind == "optimization":
        optimization_source = await session.get(Optimization, payload.source_id)
        if optimization_source is None or optimization_source.user_id != user_id:
            return _job_template_not_found_response(request_id=request_id)
        if optimization_source.status != "completed":
            return _source_task_not_completed_response(
                source_id=payload.source_id,
                source_status=optimization_source.status,
                request_id=request_id,
            )
        try:
            template_payload = build_optimization_template_payload(
                optimization_source.input_payload
            )
        except Exception as exc:
            return _invalid_job_template_response(
                field_path="source_id",
                value=str(payload.source_id),
                constraint=f"source optimization payload is not templateable: {exc}",
                request_id=request_id,
            )
    else:
        prediction_source = await session.get(Prediction, payload.source_id)
        if prediction_source is None or prediction_source.user_id != user_id:
            return _job_template_not_found_response(request_id=request_id)
        if prediction_source.status != "completed":
            return _source_task_not_completed_response(
                source_id=payload.source_id,
                source_status=prediction_source.status,
                request_id=request_id,
            )
        try:
            template_payload = build_prediction_template_payload(prediction_source.input_payload)
        except Exception as exc:
            return _invalid_job_template_response(
                field_path="source_id",
                value=str(payload.source_id),
                constraint=f"source prediction payload is not templateable: {exc}",
                request_id=request_id,
            )
    assert template_payload is not None

    template_id = uuid.uuid4()
    now = datetime.now(UTC)
    template, created = await _insert_job_template_or_existing(
        session,
        values={
            "id": template_id,
            "user_id": user_id,
            "name": name,
            "description": description,
            "source_kind": payload.source_kind,
            "source_id": payload.source_id,
            "task_type": template_payload.task_type,
            "payload_schema_version": template_payload.payload_schema_version,
            "payload_json": template_payload.payload_json,
            "payload_sha256": template_payload.payload_sha256,
            "version": 1,
            "root_template_id": template_id,
            "parent_template_id": None,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        },
        user_id=user_id,
        source_kind=payload.source_kind,
        source_id=payload.source_id,
        name=name,
    )
    return JSONResponse(
        content=_job_template_response(template, detail=True),
        status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@router.get(
    "/job-templates",
    tags=["execution"],
    summary="列出当前 API key 用户的 job templates (Story 5.D.3)",
)
async def list_job_templates(
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    client_ip = request.client.host if request.client else None
    user_id, _api_key_id, scopes = await verify_api_key(authorization, session, client_ip=client_ip)
    require_scope("optimize:write", scopes)
    result = await session.execute(
        select(JobTemplate)
        .where(JobTemplate.user_id == user_id, JobTemplate.deleted_at.is_(None))
        .order_by(JobTemplate.created_at.desc(), JobTemplate.id.desc())
    )
    items = [_job_template_summary_model(item) for item in result.scalars().all()]
    content = json.loads(JobTemplateListResponse(items=items).model_dump_json())
    if not isinstance(content, dict):
        raise ValueError("job template list response did not encode an object")
    return JSONResponse(content=content, status_code=status.HTTP_200_OK)


@router.get(
    "/job-templates/{template_id}",
    tags=["execution"],
    summary="读取当前 API key 用户的 job template (Story 5.D.3)",
)
async def get_job_template(
    template_id: uuid.UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    client_ip = request.client.host if request.client else None
    user_id, _api_key_id, scopes = await verify_api_key(authorization, session, client_ip=client_ip)
    require_scope("optimize:write", scopes)
    result = await session.execute(
        select(JobTemplate).where(
            JobTemplate.id == template_id,
            JobTemplate.user_id == user_id,
            JobTemplate.deleted_at.is_(None),
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        return _job_template_not_found_response(
            request_id=request.headers.get("x-request-id") or str(uuid.uuid4())
        )
    return JSONResponse(
        content=_job_template_response(template, detail=True),
        status_code=status.HTTP_200_OK,
    )


@router.get(
    "/job-templates/{template_id}/versions",
    tags=["execution"],
    summary="列出当前 API key 用户的 job template 版本历史 (Story 5.D.4)",
)
async def list_job_template_versions(
    template_id: uuid.UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    client_ip = request.client.host if request.client else None
    user_id, _api_key_id, scopes = await verify_api_key(authorization, session, client_ip=client_ip)
    require_scope("optimize:write", scopes)
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    template = await _get_owned_active_job_template(
        session, template_id=template_id, user_id=user_id
    )
    if template is None:
        return _job_template_not_found_response(request_id=request_id)

    result = await session.execute(
        select(JobTemplate)
        .where(
            JobTemplate.user_id == user_id,
            JobTemplate.root_template_id == template.root_template_id,
            JobTemplate.deleted_at.is_(None),
        )
        .order_by(JobTemplate.version.asc(), JobTemplate.created_at.asc(), JobTemplate.id.asc())
    )
    items = [_job_template_summary_model(item) for item in result.scalars().all()]
    content = json.loads(JobTemplateVersionsResponse(items=items).model_dump_json())
    if not isinstance(content, dict):
        raise ValueError("job template versions response did not encode an object")
    return JSONResponse(content=content, status_code=status.HTTP_200_OK)


@router.post(
    "/job-templates/{template_id}/versions",
    tags=["execution"],
    summary="基于当前 API key 用户的 job template 创建新版本 (Story 5.D.4)",
)
async def create_job_template_version(
    template_id: uuid.UUID,
    payload: JobTemplateVersionCreateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    client_ip = request.client.host if request.client else None
    user_id, _api_key_id, scopes = await verify_api_key(authorization, session, client_ip=client_ip)
    require_scope("optimize:write", scopes)
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    rate_limit_error = await _rate_limit_or_response(
        session=session, user_id=user_id, request_id=request_id
    )
    if rate_limit_error is not None:
        return rate_limit_error
    parent = await _get_owned_active_job_template(session, template_id=template_id, user_id=user_id)
    if parent is None:
        return _job_template_not_found_response(request_id=request_id)

    try:
        merged_payload = apply_template_parameter_override(
            parent.payload_json,
            source_kind=parent.source_kind,  # type: ignore[arg-type]
            parameter_path=payload.parameter_path,
            value=payload.value,
        )
    except TemplateParameterError as exc:
        return _invalid_job_template_response(
            field_path=exc.field_path,
            value=payload.parameter_path if exc.field_path == "parameter_path" else payload.value,
            constraint=exc.detail,
            request_id=request_id,
        )

    validation_error = _validate_template_version_payload(
        source_kind=parent.source_kind,
        payload_json=merged_payload,
        request_id=request_id,
    )
    if validation_error is not None:
        return validation_error

    try:
        template_payload = build_template_payload_from_version_payload(
            source_kind=parent.source_kind,  # type: ignore[arg-type]
            payload_json=merged_payload,
        )
    except (ValueError, TemplateParameterError) as exc:
        return _invalid_job_template_response(
            field_path="value",
            value="[omitted]",
            constraint=str(exc),
            request_id=request_id,
        )

    now = datetime.now(UTC)
    version_id = uuid.uuid4()
    description = _normalized_template_description(payload.description)
    if description is None:
        description = parent.description
    version = await _insert_job_template_version(
        session,
        values={
            "id": version_id,
            "user_id": user_id,
            "name": parent.name,
            "description": description,
            "source_kind": parent.source_kind,
            "source_id": parent.source_id,
            "task_type": template_payload.task_type,
            "payload_schema_version": template_payload.payload_schema_version,
            "payload_json": template_payload.payload_json,
            "payload_sha256": template_payload.payload_sha256,
            "root_template_id": parent.root_template_id,
            "parent_template_id": parent.id,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        },
        user_id=user_id,
        root_template_id=parent.root_template_id,
    )
    return JSONResponse(
        content=_job_template_response(version, detail=True),
        status_code=status.HTTP_201_CREATED,
    )


@router.delete(
    "/job-templates/{template_id}",
    tags=["execution"],
    summary="软删除当前 API key 用户的 job template (Story 5.D.3)",
)
async def delete_job_template(
    template_id: uuid.UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> Response:
    client_ip = request.client.host if request.client else None
    user_id, _api_key_id, scopes = await verify_api_key(authorization, session, client_ip=client_ip)
    require_scope("optimize:write", scopes)
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    rate_limit_error = await _rate_limit_or_response(
        session=session, user_id=user_id, request_id=request_id
    )
    if rate_limit_error is not None:
        return rate_limit_error
    result = await session.execute(
        select(JobTemplate).where(
            JobTemplate.id == template_id,
            JobTemplate.user_id == user_id,
            JobTemplate.deleted_at.is_(None),
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        return _job_template_not_found_response(request_id=request_id)
    now = datetime.now(UTC)
    template.deleted_at = now
    template.updated_at = now
    await session.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _prefix_problem_response_errors(response: JSONResponse, prefix: str) -> JSONResponse:
    content = json.loads(bytes(response.body))
    errors = content.get("errors")
    if isinstance(errors, list):
        for item in errors:
            if not isinstance(item, dict):
                continue
            field_path = item.get("field_path")
            if isinstance(field_path, str):
                item["field_path"] = f"{prefix}.{field_path}"
    return JSONResponse(
        content=content,
        status_code=response.status_code,
        media_type=PROBLEM_JSON,
    )


def _batch_invalid_mode_response(*, mode: str, request_id: str | None) -> JSONResponse:
    return _rfc7807_error(
        title="Invalid Execution Mode",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="batch endpoint only accepts async execution mode",
        errors=[
            ErrorDetail(
                field_path="query.mode",
                value=mode,
                constraint="must be omitted or async for batch endpoint",
                remediation_hint_key="errors.422.invalid_execution_mode",
            )
        ],
        request_id=request_id,
    )


def _batch_billing_not_supported_response(
    *, billing_charge_id: str, request_id: str | None
) -> JSONResponse:
    return _rfc7807_error(
        title="Billing Not Supported For Batch Optimizations",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="X-Billing-Charge-Id is not supported for /v1/optimizations/batch",
        errors=[
            ErrorDetail(
                field_path="header.X-Billing-Charge-Id",
                value=billing_charge_id,
                constraint="batch billing requires a future per-item or batch reservation contract",
                remediation_hint_key="errors.422.billing_not_supported_for_async_optimizations",
            )
        ],
        request_id=request_id,
    )


def _batch_not_found_response(*, request_id: str | None) -> JSONResponse:
    response = _rfc7807_error(
        title="Not Found",
        status_code=status.HTTP_404_NOT_FOUND,
        detail="batch not found",
        request_id=request_id,
    )
    content = json.loads(bytes(response.body))
    content["instance"] = "/v1/optimizations/batch/{batch_id}"
    return JSONResponse(
        content=content,
        status_code=status.HTTP_404_NOT_FOUND,
        media_type=PROBLEM_JSON,
    )


def _batch_task_type_response(
    *, index: int, task_type: str, request_id: str | None
) -> JSONResponse:
    return _rfc7807_error(
        title="Unsupported Task Type",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="batch endpoint only supports task_type 'lp' in Story 3.13",
        errors=[
            ErrorDetail(
                field_path=f"tasks[{index}].task_type",
                value=task_type,
                constraint="must be lp",
                remediation_hint_key="errors.422.unsupported_task_type",
            )
        ],
        request_id=request_id,
    )


def _batch_attempt_plan_error_response(
    attempt_plan: FallbackAttemptPlan,
    *,
    task_type: str,
    index: int,
    request_id: str | None,
) -> JSONResponse | None:
    if attempt_plan.status is FallbackPlanStatus.UNAUDITED_SELF_ALGORITHM:
        response = _unaudited_self_algorithm_error(
            attempt_plan,
            field_path=(
                f"fallback_chain[{attempt_plan.invalid_index}]"
                if attempt_plan.invalid_index is not None
                else "fallback_chain"
            ),
            request_id=request_id,
        )
        return _prefix_problem_response_errors(response, f"tasks[{index}]")
    if attempt_plan.status is FallbackPlanStatus.INVALID_FALLBACK_SOLVER:
        invalid_idx = attempt_plan.invalid_index if attempt_plan.invalid_index is not None else 0
        supported = attempt_plan.supported_solvers or []
        invalid_candidate = attempt_plan.invalid_candidate
        return _rfc7807_error(
            title="Unsupported Fallback Solver",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"fallback_chain[{invalid_idx}]='{invalid_candidate}' is not supported for "
                f"task_type '{task_type}'. Supported: {', '.join(supported)}"
            ),
            errors=[
                ErrorDetail(
                    field_path=f"tasks[{index}].fallback_chain[{invalid_idx}]",
                    value=invalid_candidate,
                    constraint=f"must be one of: {', '.join(supported)}",
                    remediation_hint_key="errors.400.unsupported_fallback_solver",
                )
            ],
            next_action="https://api.opticloud.cn/v1/algorithms",
            request_id=request_id,
        )
    return None


def _validate_batch_task(
    payload: OptimizationRequest,
    *,
    index: int,
    request_id: str | None,
) -> tuple[_BatchValidatedTask | None, JSONResponse | None]:
    if payload.task_type != "lp":
        return None, _batch_task_type_response(
            index=index,
            task_type=payload.task_type,
            request_id=request_id,
        )
    if payload.options.anonymous and not payload.options.reproducible:
        return None, _rfc7807_error(
            title="Invalid Anonymous Option",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="options.anonymous requires options.reproducible=true",
            errors=[
                ErrorDetail(
                    field_path=f"tasks[{index}].options.anonymous",
                    value=True,
                    constraint="requires options.reproducible=true",
                    remediation_hint_key="errors.422.anonymous_requires_reproducible",
                )
            ],
            request_id=request_id,
        )
    route = select_provider_route(payload.task_type, payload.solver)
    route_error = _provider_route_error_response(
        route,
        task_type=payload.task_type,
        requested_solver=payload.solver,
        request_id=request_id,
    )
    if route_error is not None:
        return None, _prefix_problem_response_errors(route_error, f"tasks[{index}]")
    assert route.algorithm is not None
    assert route.selected_solver is not None
    attempt_plan = build_fallback_attempts(
        primary_route=route,
        task_type=payload.task_type,
        requested_solver=payload.solver,
        fallback_chain=payload.fallback_chain,
    )
    attempt_plan_error = _batch_attempt_plan_error_response(
        attempt_plan,
        task_type=payload.task_type,
        index=index,
        request_id=request_id,
    )
    if attempt_plan_error is not None:
        return None, attempt_plan_error
    primary_route_metadata = attempt_route_metadata(
        attempt_plan.attempts[0], task_type=payload.task_type
    )
    estimated_seconds = _estimate_optimization_seconds(payload)
    _effective_mode, _auto_async, execution_mode_metadata = _execution_mode_metadata(
        requested_mode="async",
        estimated_seconds=estimated_seconds,
    )
    return (
        _BatchValidatedTask(
            body=payload.model_dump(by_alias=True),
            model_version=dict(route.model_version),
            provider_route=primary_route_metadata,
            execution_mode=execution_mode_metadata,
        ),
        None,
    )


def _hash_batch_body(body: dict[str, Any]) -> str:
    return _hash_body({"body": body, "mode": "async"})


def _batch_status_from_counts(counts: dict[str, int]) -> str:
    total = sum(counts.values())
    if total == 0:
        return "queued"
    active = counts["queued"] + counts["in_progress"]
    failures = counts["failed"] + counts["timeout"] + counts["cancelled"]
    if counts["queued"] == total:
        return "queued"
    if active > 0:
        return "in_progress"
    if counts["completed"] == total:
        return "completed"
    if counts["cancelled"] == total:
        return "cancelled"
    if counts["completed"] > 0 and failures > 0:
        return "partial_failed"
    if counts["completed"] == 0 and failures > 0:
        return "failed"
    return "failed"


def _batch_completed_at(status_value: str, children: list[Optimization]) -> datetime | None:
    if status_value in {"queued", "in_progress"}:
        return None
    completed_values: list[datetime] = []
    for opt in children:
        if opt.status in BATCH_TERMINAL_STATUSES and opt.completed_at is not None:
            completed_values.append(opt.completed_at)
    if not completed_values:
        return None
    return max(completed_values)


def _batch_eta_seconds(status_value: str, child_payloads: list[dict[str, Any]]) -> int | None:
    if status_value == "completed":
        return 0
    if status_value not in {"queued", "in_progress"}:
        return None
    values: list[int] = []
    for payload in child_payloads:
        eta_seconds = payload.get("eta_seconds")
        if payload.get("status") in {"queued", "in_progress"} and isinstance(eta_seconds, int):
            values.append(eta_seconds)
    return max(values) if values else None


def _batch_progress_pct(batch_status: str, child_payloads: list[dict[str, Any]]) -> int:
    task_count = len(child_payloads)
    if task_count == 0:
        return 0
    raw_progress = int(
        math.floor(sum(int(item.get("progress_pct") or 0) for item in child_payloads) / task_count)
    )
    if batch_status == "completed":
        return 100
    return min(raw_progress, 99)


def _build_batch_response_content(
    batch: OptimizationBatch,
    ordered_children: list[tuple[int, Optimization]],
) -> dict[str, Any]:
    counts = dict.fromkeys(BATCH_COUNT_STATUSES, 0)
    child_payloads: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    optimization_ids: list[str] = []
    children: list[Optimization] = []
    for index, opt in ordered_children:
        children.append(opt)
        optimization_ids.append(str(opt.id))
        if opt.status in counts:
            counts[opt.status] += 1
        if opt.status == "completed":
            content = _build_response_content(opt, include_routing_history=False)
        else:
            content = _build_optimization_status_response_content(
                opt, include_routing_history=False
            )
        child_payloads.append(content)
        item = {"index": index, **content}
        items.append(item)
        if opt.status in {"failed", "timeout", "cancelled"}:
            errors.append(
                {
                    "index": index,
                    "optimization_id": str(opt.id),
                    "status": opt.status,
                    "error": _redact_status_error(opt.error),
                }
            )
    batch_status = _batch_status_from_counts(counts)
    task_count = len(items)
    return {
        "batch_id": str(batch.id),
        "batch_status": batch_status,
        "task_count": task_count,
        "counts": counts,
        "progress_pct": _batch_progress_pct(batch_status, child_payloads),
        "eta_seconds": _batch_eta_seconds(batch_status, child_payloads),
        "optimization_ids": optimization_ids,
        "items": items,
        "errors": errors,
        "created_at": _status_datetime(batch.created_at),
        "completed_at": _status_datetime(_batch_completed_at(batch_status, children)),
    }


async def _load_batch_children(
    session: AsyncSession,
    *,
    batch_id: uuid.UUID,
) -> list[tuple[int, Optimization]]:
    rows = (
        (
            await session.execute(
                select(OptimizationBatchItem.item_index, Optimization)
                .join(Optimization, Optimization.id == OptimizationBatchItem.optimization_id)
                .where(OptimizationBatchItem.batch_id == batch_id)
                .order_by(OptimizationBatchItem.item_index.asc())
            )
        )
        .tuples()
        .all()
    )
    return [(index, opt) for index, opt in rows]


async def _build_batch_response(
    session: AsyncSession,
    *,
    batch: OptimizationBatch,
    status_code: int = status.HTTP_200_OK,
) -> JSONResponse:
    ordered_children = await _load_batch_children(session, batch_id=batch.id)
    return JSONResponse(
        content=_build_batch_response_content(batch, ordered_children),
        status_code=status_code,
        headers={"Location": f"/v1/optimizations/batch/{batch.id}"}
        if status_code == status.HTTP_202_ACCEPTED
        else None,
    )


async def _load_owner_batch(
    session: AsyncSession,
    *,
    batch_id: uuid.UUID,
    user_id: uuid.UUID,
) -> OptimizationBatch | None:
    result = await session.execute(
        select(OptimizationBatch).where(
            OptimizationBatch.id == batch_id,
            OptimizationBatch.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _load_batch_idempotency_replay(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    idempotency_key: str,
    request_body_hash: str,
) -> tuple[OptimizationBatch | None, bool]:
    existing_query = await session.execute(
        select(OptimizationBatchIdempotencyKey).where(
            OptimizationBatchIdempotencyKey.user_id == user_id,
            OptimizationBatchIdempotencyKey.key == idempotency_key,
        )
    )
    existing = existing_query.scalar_one_or_none()
    if existing is None:
        return None, False
    if existing.request_body_hash != request_body_hash:
        return None, True
    existing_batch = await _load_owner_batch(
        session,
        batch_id=existing.batch_id,
        user_id=user_id,
    )
    return existing_batch, False


async def _add_optimization_idempotency_key(
    session: AsyncSession,
    *,
    key: str | None,
    user_id: uuid.UUID,
    optimization_id: uuid.UUID,
    request_body_hash: str,
    request_id: str | None,
) -> JSONResponse | None:
    if not key:
        return None
    session.add(
        IdempotencyKey(
            key=key,
            user_id=user_id,
            optimization_id=optimization_id,
            request_body_hash=request_body_hash,
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
    )
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return _idempotency_conflict_response(
            idempotency_key=key,
            detail="idempotency key already exists",
            constraint="must be unique per user",
            request_id=request_id,
        )
    return None


def _validate_execution_mode(
    mode: str | None, *, request_id: str | None
) -> tuple[str, bool, None] | tuple[None, bool, JSONResponse]:
    if mode is None:
        return "sync", False, None
    normalized = mode.strip().lower()
    if normalized in {"sync", "async"}:
        return normalized, False, None
    if normalized == "teaching":
        return "sync", True, None
    return (
        None,
        False,
        _rfc7807_error(
            title="Invalid Execution Mode",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="query parameter mode must be one of 'sync', 'async', or 'teaching'",
            errors=[
                ErrorDetail(
                    field_path="query.mode",
                    value=mode,
                    constraint="must be one of: sync, async, teaching",
                    remediation_hint_key="errors.422.invalid_execution_mode",
                )
            ],
            request_id=request_id,
        ),
    )


def _estimate_optimization_seconds(payload: OptimizationRequest) -> float:
    if payload.task_type != "lp":
        return 10.0
    rows = len(payload.st.a)
    objective = payload.minimize if payload.minimize is not None else payload.maximize
    cols = len(objective.c) if objective is not None else 0
    nonzero_count = sum(1 for row in payload.st.a for value in row if value != 0)
    return round(0.05 + rows * cols * 0.0002 + nonzero_count * 0.0001, 6)


def _execution_mode_metadata(
    *,
    requested_mode: str,
    estimated_seconds: float,
) -> tuple[str, bool, dict[str, object]]:
    auto_async = requested_mode == "sync" and estimated_seconds > SYNC_ASYNC_THRESHOLD_SECONDS
    effective_mode = "async" if requested_mode == "async" or auto_async else "sync"
    return (
        effective_mode,
        auto_async,
        {
            "requested_mode": requested_mode,
            "effective_mode": effective_mode,
            "auto_async": auto_async,
            "estimated_seconds": estimated_seconds,
            "threshold_seconds": SYNC_ASYNC_THRESHOLD_SECONDS,
        },
    )


def _billing_not_supported_for_async_response(
    *, billing_charge_id: str, request_id: str | None
) -> JSONResponse:
    return _rfc7807_error(
        title="Billing Not Supported For Async Optimizations",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="X-Billing-Charge-Id is not supported when optimization execution mode is async",
        errors=[
            ErrorDetail(
                field_path="header.X-Billing-Charge-Id",
                value=billing_charge_id,
                constraint="billing is not supported for async optimizations in Story 3.3",
                remediation_hint_key="errors.422.billing_not_supported_for_async_optimizations",
            )
        ],
        request_id=request_id,
    )


def _invalid_billing_charge_id_response(
    *, billing_charge_id: str, request_id: str | None
) -> JSONResponse:
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


def _billing_reserve_failed_response(
    *,
    billing_charge_id: str,
    reserve_result: billing_client.BillingResult,
    request_id: str | None,
) -> JSONResponse:
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


def _cancellation_not_allowed_response(
    *,
    opt: Optimization,
    request_id: str | None,
) -> JSONResponse:
    return _rfc7807_error(
        title="Cancellation Not Allowed",
        status_code=status.HTTP_409_CONFLICT,
        detail=f"optimization status '{opt.status}' cannot be cancelled",
        errors=[
            ErrorDetail(
                field_path="path.optimization_id",
                value="[redacted]",
                constraint="status must be queued or in_progress",
                remediation_hint_key="errors.409.cancellation_not_allowed",
            )
        ],
        request_id=request_id,
    )


def _solver_timeout_response(
    *,
    opt: Optimization,
    result: solvers.LPSolveResult,
    max_solve_seconds: float,
    request_id: str | None,
) -> JSONResponse:
    response = _rfc7807_error(
        title="Solver Timeout",
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        detail=result.error_constraint or "solver exceeded max_solve_seconds",
        errors=[
            ErrorDetail(
                field_path=result.error_field_path or "options.max_solve_seconds",
                value=max_solve_seconds,
                constraint=result.error_constraint or "timeout",
                remediation_hint_key="errors.504.solver_timeout",
            )
        ],
        request_id=request_id,
    )
    content = json.loads(bytes(response.body))
    content.update(
        {
            "optimization_id": str(opt.id),
            "optimization_status": "timeout",
            "solve_seconds": result.solve_seconds,
            "max_solve_seconds": max_solve_seconds,
            "best_solution_available": result.solution is not None,
        }
    )
    if result.solution is not None:
        content["best_solution"] = result.solution
    if result.objective is not None:
        content["objective"] = result.objective
    return JSONResponse(
        content=content,
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        media_type=PROBLEM_JSON,
    )


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
        remaining_budget = max(max_solve_seconds - total_solve_seconds, 0.0)
        if remaining_budget <= SOLVER_BUDGET_EPSILON_SECONDS:
            exhausted = True
            break
        if attempt.route.selected_solver is None:
            raise ValueError("fallback attempt requires selected solver")
        attempt_body = dict(body_dict)
        attempt_body["solver"] = attempt.route.selected_solver
        result = solvers.solve_from_request(
            attempt_body,
            max_solve_seconds=remaining_budget,
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
        if total_solve_seconds + SOLVER_BUDGET_EPSILON_SECONDS >= max_solve_seconds:
            exhausted = True
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
        alternatives=terminal_result.alternatives,
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
    mode: str | None = Query(default=None),
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
    rate_limit_error = await _rate_limit_or_response(
        session=session, user_id=user_id, request_id=request_id
    )
    if rate_limit_error is not None:
        return rate_limit_error

    normalized_mode, teaching_enabled, mode_error = _validate_execution_mode(
        mode, request_id=request_id
    )
    if mode_error is not None:
        return mode_error
    assert normalized_mode is not None

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

    benchmark_error = _validate_benchmark_library_options(payload, request_id=request_id)
    if benchmark_error is not None:
        return benchmark_error

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
    teaching_metadata = (
        _teaching_metadata(task_type=payload.task_type, selected_solver=route.selected_solver)
        if teaching_enabled
        else None
    )

    estimated_seconds = _estimate_optimization_seconds(payload)
    effective_mode, _auto_async, execution_mode_metadata = _execution_mode_metadata(
        requested_mode=normalized_mode,
        estimated_seconds=estimated_seconds,
    )
    billing_uuid: uuid.UUID | None = None
    normalized_billing_charge_id: str | None = None
    if effective_mode == "async" and billing_charge_id:
        try:
            billing_uuid = uuid.UUID(billing_charge_id)
        except ValueError:
            return _invalid_billing_charge_id_response(
                billing_charge_id=billing_charge_id,
                request_id=request_id,
            )
        normalized_billing_charge_id = str(billing_uuid)
    body_hash = _hash_optimization_body(
        body_dict,
        "teaching" if teaching_enabled else normalized_mode,
        billing_charge_id=normalized_billing_charge_id if effective_mode == "async" else None,
    )

    existing_completed: Optimization | None = None
    if idempotency_key:
        idem_query = await session.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.user_id == user_id,
                IdempotencyKey.key == idempotency_key,
            )
        )
        existing = idem_query.scalar_one_or_none()
        if existing is not None:
            if existing.request_body_hash != body_hash:
                return _idempotency_conflict_response(
                    idempotency_key=idempotency_key,
                    request_id=request_id,
                )
            cached_opt = await session.get(Optimization, existing.optimization_id)
            if cached_opt is None:
                return _idempotency_conflict_response(
                    idempotency_key=idempotency_key,
                    detail="idempotency key points to a missing optimization",
                    constraint="cached optimization must exist",
                    request_id=request_id,
                )
            if cached_opt.status == "completed":
                if effective_mode == "async":
                    return _idempotency_conflict_response(
                        idempotency_key=idempotency_key,
                        detail="same idempotency key already completed synchronously",
                        constraint="cannot replay completed sync result as async status",
                        request_id=request_id,
                    )
                existing_completed = cached_opt
            elif cached_opt.status in {"queued", "in_progress"}:
                return _build_async_accepted_response(cached_opt)
            else:
                return JSONResponse(
                    content=_build_optimization_status_response_content(cached_opt),
                    status_code=status.HTTP_200_OK,
                )

    if effective_mode == "async":
        billing_metadata: dict[str, Any] | None = None
        if billing_uuid is not None:
            billing_metadata = (
                _optimization_billing_discount_metadata(
                    payload,
                    teaching_enabled=teaching_enabled,
                )
                or {}
            )
            billing_metadata = {
                **billing_metadata,
                "charge_id": str(billing_uuid),
                "reserved": False,
                "reserve_status_code": None,
                "cancel_finalize_attempted": False,
                "cancel_finalize_status": None,
                "refund_status": None,
            }
        opt = Optimization(
            user_id=user_id,
            api_key_id=api_key_id,
            task_type=payload.task_type,
            status="queued",
            input_payload=_attach_system_metadata(
                body_dict,
                provider_route=primary_route_metadata,
                execution_mode=execution_mode_metadata,
                billing=billing_metadata,
                teaching=teaching_metadata,
            ),
            model_version=dict(route.model_version),
            idempotency_key=idempotency_key,
        )
        session.add(opt)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            return _idempotency_conflict_response(
                idempotency_key=idempotency_key or "",
                detail="failed to persist async optimization",
                constraint="optimization persistence must be atomic",
                request_id=request_id,
            )
        idempotency_error = await _add_optimization_idempotency_key(
            session,
            key=idempotency_key,
            user_id=user_id,
            optimization_id=opt.id,
            request_body_hash=body_hash,
            request_id=request_id,
        )
        if idempotency_error is not None:
            return idempotency_error
        if billing_uuid is not None:
            reserve_result = await billing_client.reserve(billing_uuid, user_id)
            if not reserve_result.ok:
                await session.rollback()
                return _billing_reserve_failed_response(
                    billing_charge_id=str(billing_uuid),
                    reserve_result=reserve_result,
                    request_id=request_id,
                )
            _set_optimization_billing_metadata(
                opt,
                {
                    **(
                        _optimization_billing_discount_metadata(
                            payload,
                            teaching_enabled=teaching_enabled,
                        )
                        or {}
                    ),
                    "charge_id": str(billing_uuid),
                    "reserved": True,
                    "reserve_status_code": reserve_result.status_code,
                    "cancel_finalize_attempted": False,
                    "cancel_finalize_status": None,
                    "refund_status": None,
                },
            )
        return _build_async_accepted_response(opt)

    # ----- Story 5.A.4 — pre-solve billing reserve (opt-in via X-Billing-Charge-Id) -----
    if billing_charge_id:
        if existing_completed is not None:
            await attach_existing_voucher_id(session, existing_completed)
            return _build_success_response(existing_completed)
        try:
            billing_uuid = uuid.UUID(billing_charge_id)
        except ValueError:
            return _invalid_billing_charge_id_response(
                billing_charge_id=billing_charge_id,
                request_id=request_id,
            )
        reserve_result = await billing_client.reserve(billing_uuid, user_id)
        if not reserve_result.ok:
            return _billing_reserve_failed_response(
                billing_charge_id=str(billing_uuid),
                reserve_result=reserve_result,
                request_id=request_id,
            )

    if existing_completed is not None:
        await attach_existing_voucher_id(session, existing_completed)
        return _build_success_response(existing_completed)

    # ----- Persist input -----
    opt = Optimization(
        user_id=user_id,
        api_key_id=api_key_id,
        task_type=payload.task_type,
        status="in_progress",
        input_payload=_attach_system_metadata(
            body_dict,
            provider_route=primary_route_metadata,
            execution_mode=execution_mode_metadata,
            teaching=teaching_metadata,
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
        finalize_status = "success" if result.status in {"optimal", "timeout"} else "failure"
        failure_reason: str | None = (
            None if finalize_status == "success" else (result.error_constraint or result.status)
        )
        billing_discount_metadata = _optimization_billing_discount_metadata(
            payload,
            teaching_enabled=teaching_enabled,
        )
        if billing_discount_metadata is None:
            finalize_outcome = await billing_client.finalize(
                billing_uuid,
                user_id,
                elapsed_seconds=result.solve_seconds,
                status=finalize_status,
                failure_reason=failure_reason,
            )
        else:
            finalize_outcome = await billing_client.finalize(
                billing_uuid,
                user_id,
                elapsed_seconds=result.solve_seconds,
                status=finalize_status,
                failure_reason=failure_reason,
                discount_multiplier=float(billing_discount_metadata["discount_multiplier"]),
            )
        if not finalize_outcome.ok:
            # Q4 — solve result is NOT held hostage by billing; mark + log + continue.
            # M2.2c — persist retry context so the billing reconciler can replay.
            retry_context: dict[str, Any] = {
                "billing_finalize_failed": True,
                "billing_finalize_error": finalize_outcome.error_message,
                "billing_charge_id": str(billing_uuid),
                "billing_elapsed_seconds": result.solve_seconds,
                "billing_status": finalize_status,
                "billing_failure_reason": failure_reason,
                "billing_retry_count": 0,
            }
            if billing_discount_metadata is not None:
                retry_context.update(
                    {
                        "billing_discount_multiplier": billing_discount_metadata[
                            "discount_multiplier"
                        ],
                        "billing_discount_kind": billing_discount_metadata["discount_kind"],
                    }
                )
            _merge_optimization_error(opt, retry_context)

    if result.status == "optimal":
        opt.status = "completed"
        opt.solution = result.solution
        opt.objective = result.objective
        opt.completed_at = datetime.now(UTC)
        _attach_top_k_metadata(
            opt,
            result,
            requested=payload.options.top_k_alternatives,
        )
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
        idempotency_error = await _add_optimization_idempotency_key(
            session,
            key=idempotency_key,
            user_id=user_id,
            optimization_id=opt.id,
            request_body_hash=body_hash,
            request_id=request_id,
        )
        if idempotency_error is not None:
            return idempotency_error
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
        opt.solution = result.solution
        opt.objective = result.objective
        opt.completed_at = datetime.now(UTC)
        _merge_optimization_error(
            opt,
            {
                "title": "Solver Timeout",
                "detail": result.error_constraint,
                "fallback_execution": execution.fallback_execution,
            },
        )
        await _record_solver_cost_attribution(
            session, opt=opt, result=result, solver_name=final_selected_solver
        )
        idempotency_error = await _add_optimization_idempotency_key(
            session,
            key=idempotency_key,
            user_id=user_id,
            optimization_id=opt.id,
            request_body_hash=body_hash,
            request_id=request_id,
        )
        if idempotency_error is not None:
            return idempotency_error
        return _solver_timeout_response(
            opt=opt,
            result=result,
            max_solve_seconds=payload.options.max_solve_seconds,
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
        idempotency_error = await _add_optimization_idempotency_key(
            session,
            key=idempotency_key,
            user_id=user_id,
            optimization_id=opt.id,
            request_body_hash=body_hash,
            request_id=request_id,
        )
        if idempotency_error is not None:
            return idempotency_error
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
    idempotency_error = await _add_optimization_idempotency_key(
        session,
        key=idempotency_key,
        user_id=user_id,
        optimization_id=opt.id,
        request_body_hash=body_hash,
        request_id=request_id,
    )
    if idempotency_error is not None:
        return idempotency_error

    return _build_success_response(opt)


@router.post(
    "/optimizations/batch",
    tags=["execution"],
    summary="批量提交异步优化任务 (Story 3.13)",
)
async def post_optimization_batch(
    payload: OptimizationBatchRequest,
    request: Request,
    mode: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    billing_charge_id: str | None = Header(default=None, alias="X-Billing-Charge-Id"),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    client_ip = request.client.host if request.client else None
    user_id, api_key_id, scopes = await verify_api_key(authorization, session, client_ip=client_ip)
    require_scope("optimize:write", scopes)
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    rate_limit_error = await _rate_limit_or_response(
        session=session, user_id=user_id, request_id=request_id
    )
    if rate_limit_error is not None:
        return rate_limit_error

    if mode is not None and mode.strip().lower() != "async":
        return _batch_invalid_mode_response(mode=mode, request_id=request_id)
    if billing_charge_id:
        return _batch_billing_not_supported_response(
            billing_charge_id=billing_charge_id,
            request_id=request_id,
        )

    validated_tasks: list[_BatchValidatedTask] = []
    for index, task in enumerate(payload.tasks):
        validated, validation_error = _validate_batch_task(
            task,
            index=index,
            request_id=request_id,
        )
        if validation_error is not None:
            return validation_error
        assert validated is not None
        validated_tasks.append(validated)

    body_dict = payload.model_dump(by_alias=True)
    body_hash = _hash_batch_body(body_dict)
    if idempotency_key:
        existing_batch, body_conflict = await _load_batch_idempotency_replay(
            session,
            user_id=user_id,
            idempotency_key=idempotency_key,
            request_body_hash=body_hash,
        )
        if body_conflict:
            return _idempotency_conflict_response(
                idempotency_key=idempotency_key,
                request_id=request_id,
            )
        if existing_batch is not None:
            return await _build_batch_response(
                session,
                batch=existing_batch,
                status_code=status.HTTP_202_ACCEPTED,
            )

    batch = OptimizationBatch(user_id=user_id, api_key_id=api_key_id)
    session.add(batch)
    try:
        await session.flush()
        task_count = len(validated_tasks)
        for index, validated_task in enumerate(validated_tasks):
            opt = Optimization(
                user_id=user_id,
                api_key_id=api_key_id,
                task_type="lp",
                status="queued",
                input_payload=_attach_system_metadata(
                    validated_task.body,
                    provider_route=validated_task.provider_route,
                    execution_mode=validated_task.execution_mode,
                    batch={
                        "batch_id": str(batch.id),
                        "item_index": index,
                        "task_count": task_count,
                    },
                ),
                model_version=validated_task.model_version,
                idempotency_key=None,
            )
            session.add(opt)
            await session.flush()
            session.add(
                OptimizationBatchItem(
                    batch_id=batch.id,
                    item_index=index,
                    optimization_id=opt.id,
                )
            )
        if idempotency_key:
            session.add(
                OptimizationBatchIdempotencyKey(
                    key=idempotency_key,
                    user_id=user_id,
                    batch_id=batch.id,
                    request_body_hash=body_hash,
                    expires_at=datetime.now(UTC) + timedelta(hours=24),
                )
            )
        await session.flush()
    except IntegrityError:
        await session.rollback()
        if idempotency_key:
            replay_session = session
            replay_batch, body_conflict = await _load_batch_idempotency_replay(
                replay_session,
                user_id=user_id,
                idempotency_key=idempotency_key,
                request_body_hash=body_hash,
            )
            if body_conflict:
                return _idempotency_conflict_response(
                    idempotency_key=idempotency_key,
                    request_id=request_id,
                )
            if replay_batch is not None:
                return await _build_batch_response(
                    replay_session,
                    batch=replay_batch,
                    status_code=status.HTTP_202_ACCEPTED,
                )
        return _idempotency_conflict_response(
            idempotency_key=idempotency_key or "",
            detail="failed to persist batch atomically",
            constraint="batch, children, items and idempotency key must be unique",
            request_id=request_id,
        )

    return await _build_batch_response(
        session,
        batch=batch,
        status_code=status.HTTP_202_ACCEPTED,
    )


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
    rate_limit_error = await _rate_limit_or_response(
        session=session, user_id=user_id, request_id=request_id
    )
    if rate_limit_error is not None:
        return rate_limit_error

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
    row_input_payload = _attach_system_metadata(body_dict, provider_route=route_metadata)

    started = time.perf_counter()
    try:
        forecast_result = predict_quantiles(
            [float(value) for value in body_dict["data"]],
            int(body_dict["horizon"]),
        )
        prediction_payload, drift_score = _validated_forecast_payload(
            forecast_result=forecast_result,
            horizon=int(body_dict["horizon"]),
        )
        elapsed = _prediction_runtime_seconds(started, forecast_result.predict_seconds)
        completed_at = datetime.now(UTC)
    except _PredictionContractViolationError as exc:
        logger.warning(
            "prediction.contract_violation",
            user_id=str(user_id),
            family=family,
            field=exc.field,
            message=exc.detail,
        )
        prediction_row = Prediction(
            user_id=user_id,
            api_key_id=api_key_id,
            family=family,
            status="failed",
            input_payload=row_input_payload,
            error=_prediction_contract_violation_payload(exc),
            model_version=dict(route.model_version),
            predict_seconds=_prediction_runtime_seconds(started),
            idempotency_key=idempotency_key,
            completed_at=datetime.now(UTC),
        )
        session.add(prediction_row)
        await session.flush()
        return _build_prediction_success_response(prediction_row)
    except Exception as exc:
        logger.warning(
            "prediction.execution_failed",
            user_id=str(user_id),
            family=family,
            exception_type=type(exc).__name__,
        )
        prediction_row = Prediction(
            user_id=user_id,
            api_key_id=api_key_id,
            family=family,
            status="failed",
            input_payload=row_input_payload,
            error=_prediction_execution_failed_payload(),
            model_version=dict(route.model_version),
            predict_seconds=_prediction_runtime_seconds(started),
            idempotency_key=idempotency_key,
            completed_at=datetime.now(UTC),
        )
        session.add(prediction_row)
        await session.flush()
        return _build_prediction_success_response(prediction_row)

    prediction_row = Prediction(
        user_id=user_id,
        api_key_id=api_key_id,
        family=family,
        status="completed",
        input_payload=row_input_payload,
        prediction=prediction_payload,
        drift_score=drift_score,
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
    rate_limit_error = await _rate_limit_or_response(
        session=session, user_id=user_id, request_id=request_id
    )
    if rate_limit_error is not None:
        return rate_limit_error
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
        clean_payload_dict,
        max_solve_seconds=clean_payload.options.max_solve_seconds,
    )
    rerun_opt.solve_seconds = result.solve_seconds
    rerun_opt.model_version = dict(voucher.locked_model_version)

    if result.status == "optimal":
        rerun_opt.status = "completed"
        rerun_opt.solution = result.solution
        rerun_opt.objective = result.objective
        rerun_opt.completed_at = datetime.now(UTC)
        _attach_top_k_metadata(
            rerun_opt,
            result,
            requested=clean_payload.options.top_k_alternatives,
        )
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


PREDICTION_FAMILY_SOLVERS: dict[str, str] = {
    "arima": "arima",
    "chronos": "chronos-t5",
}


def _prediction_family_to_solver(family: str) -> str | None:
    return PREDICTION_FAMILY_SOLVERS.get(family.strip().lower())


def _prediction_public_error(
    *,
    title: Literal["Prediction Contract Violation", "Prediction Execution Failed"],
    detail: str,
    field: str | None = None,
) -> dict[str, str]:
    payload = {"title": title, "detail": detail}
    if field is not None:
        payload["field"] = field
    return payload


def _prediction_contract_violation_payload(
    violation: _PredictionContractViolationError,
) -> dict[str, str]:
    return _prediction_public_error(
        title="Prediction Contract Violation",
        detail=f"invalid {violation.field}: {violation.detail}",
        field=violation.field,
    )


def _prediction_execution_failed_payload() -> dict[str, str]:
    return _prediction_public_error(
        title="Prediction Execution Failed",
        detail="prediction execution failed",
    )


def _iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _safe_prediction_model_version(model_version: object) -> dict[str, Any] | None:
    try:
        parsed = ModelVersionSchema.model_validate(model_version)
    except Exception:
        return None
    content = json.loads(parsed.model_dump_json())
    if not isinstance(content, dict):
        return None
    return content


def _prediction_compact_status_content(
    prediction: Prediction,
    *,
    status_override: str | None = None,
    error_override: dict[str, Any] | None = None,
    validate_model_version: bool = False,
) -> dict[str, Any]:
    completed_at = prediction.completed_at or prediction.created_at
    if validate_model_version:
        model_version: object = _safe_prediction_model_version(prediction.model_version)
    else:
        model_version = prediction.model_version
    return {
        "prediction_id": str(prediction.id),
        "status": status_override or prediction.status,
        "error": error_override if error_override is not None else prediction.error,
        "model_version": model_version,
        "created_at": _iso_or_none(prediction.created_at),
        "completed_at": _iso_or_none(completed_at),
    }


def _prediction_horizon_from_payload(input_payload: object) -> int:
    if not isinstance(input_payload, dict):
        raise _PredictionContractViolationError("horizon", "input payload is not an object")
    public_payload = _strip_system_metadata(input_payload)
    raw_horizon = public_payload.get("horizon")
    if isinstance(raw_horizon, bool) or not isinstance(raw_horizon, int):
        raise _PredictionContractViolationError("horizon", "horizon is missing or not an integer")
    if raw_horizon < 1 or raw_horizon > 90:
        raise _PredictionContractViolationError("horizon", "horizon must be between 1 and 90")
    return raw_horizon


def _finite_prediction_float(value: object, *, field: str) -> float:
    if isinstance(value, bool):
        raise _PredictionContractViolationError(field, "value must be a finite number")
    if not isinstance(value, int | float | Decimal):
        raise _PredictionContractViolationError(field, "value must be a finite number")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise _PredictionContractViolationError(field, "value must be a finite number") from exc
    if not math.isfinite(number):
        raise _PredictionContractViolationError(field, "value must be finite")
    return number


def _validate_prediction_quantiles(
    raw_prediction: object, *, horizon: int
) -> dict[str, list[float]]:
    if not isinstance(raw_prediction, dict):
        raise _PredictionContractViolationError("prediction", "prediction must be an object")
    if set(raw_prediction) != {"p10", "p50", "p90"}:
        raise _PredictionContractViolationError(
            "prediction", "prediction must contain p10, p50, p90"
        )

    normalized: dict[str, list[float]] = {}
    for key in ("p10", "p50", "p90"):
        values = raw_prediction[key]
        if not isinstance(values, list):
            raise _PredictionContractViolationError(f"prediction.{key}", "quantile must be a list")
        if len(values) != horizon:
            raise _PredictionContractViolationError(
                "prediction",
                f"quantile length must equal horizon {horizon}",
            )
        normalized[key] = [
            _finite_prediction_float(value, field=f"prediction.{key}[{idx}]")
            for idx, value in enumerate(values)
        ]

    for idx, (p10, p50, p90) in enumerate(
        zip(normalized["p10"], normalized["p50"], normalized["p90"], strict=True)
    ):
        if not p10 <= p50 <= p90:
            raise _PredictionContractViolationError(
                "prediction",
                f"quantiles must satisfy p10 <= p50 <= p90 at index {idx}",
            )
    return normalized


def _validate_prediction_drift_score(raw_drift_score: object) -> float:
    drift_score = _finite_prediction_float(raw_drift_score, field="drift_score")
    if drift_score < 0.0 or drift_score > 1.0:
        raise _PredictionContractViolationError("drift_score", "must be between 0.0 and 1.0")
    return drift_score


def _prediction_safe_seconds(value: object | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool) or not isinstance(value, int | float | Decimal):
        return 0.0
    try:
        seconds = float(value)
    except (ValueError, OverflowError):
        return 0.0
    if not math.isfinite(seconds) or seconds < 0.0:
        return 0.0
    return seconds


def _prediction_runtime_seconds(started: float, helper_seconds: object | None = None) -> float:
    elapsed = max(time.perf_counter() - started, 0.0)
    if helper_seconds is None:
        return elapsed
    helper_elapsed = _prediction_safe_seconds(helper_seconds)
    return max(elapsed, helper_elapsed)


def _validated_forecast_payload(
    *,
    forecast_result: Any,
    horizon: int,
) -> tuple[dict[str, list[float]], float]:
    prediction_payload = {
        "p10": forecast_result.p10,
        "p50": forecast_result.p50,
        "p90": forecast_result.p90,
    }
    return (
        _validate_prediction_quantiles(prediction_payload, horizon=horizon),
        _validate_prediction_drift_score(forecast_result.drift_score),
    )


def _validated_prediction_response(prediction: Prediction) -> PredictionResponse:
    horizon = _prediction_horizon_from_payload(prediction.input_payload)
    quantiles = _validate_prediction_quantiles(prediction.prediction, horizon=horizon)
    drift_score = _validate_prediction_drift_score(prediction.drift_score)
    if prediction.created_at is None:
        raise _PredictionContractViolationError("created_at", "created_at is missing")
    if prediction.completed_at is None:
        raise _PredictionContractViolationError("completed_at", "completed_at is missing")
    if prediction.model_version is None:
        raise _PredictionContractViolationError("model_version", "model_version is missing")
    try:
        model_version = ModelVersionSchema.model_validate(prediction.model_version)
    except Exception as exc:
        raise _PredictionContractViolationError(
            "model_version", "model_version is invalid"
        ) from exc

    return PredictionResponse(
        prediction_id=prediction.id,
        status="completed",
        family=prediction.family,
        horizon=horizon,
        prediction=PredictionQuantiles.model_validate(quantiles),
        drift_score=drift_score,
        disclaimer=prediction_disclaimer(),
        model_version=model_version,
        predict_seconds=_prediction_safe_seconds(prediction.predict_seconds),
        created_at=prediction.created_at,
        completed_at=prediction.completed_at,
    )


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
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            return None, _prediction_validation_error(
                field_path=f"data[{idx}]",
                value="[non-finite]",
                constraint="data values must be finite numbers",
                request_id=request_id,
            )
        if abs(numeric_value) > PREDICTION_MAX_ABS_DATA_VALUE:
            return None, _prediction_validation_error(
                field_path=f"data[{idx}]",
                value=numeric_value,
                constraint=f"abs(data value) must be <= {PREDICTION_MAX_ABS_DATA_VALUE:g}",
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
        return _prediction_compact_status_content(prediction)

    try:
        payload = _validated_prediction_response(prediction)
    except _PredictionContractViolationError as exc:
        return _prediction_compact_status_content(
            prediction,
            status_override="failed",
            error_override=_prediction_contract_violation_payload(exc),
            validate_model_version=True,
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
        _add_top_k_to_content(
            content,
            result,
            requested=payload.options.top_k_alternatives,
        )
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
    "/optimizations/batch/{batch_id}",
    tags=["execution"],
    summary="查询批量优化状态 (Story 3.13)",
)
async def get_optimization_batch(
    batch_id: uuid.UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    client_ip = request.client.host if request.client else None
    user_id, _api_key_id, _scopes = await verify_api_key(
        authorization, session, client_ip=client_ip
    )
    batch = await _load_owner_batch(session, batch_id=batch_id, user_id=user_id)
    if batch is None:
        return _batch_not_found_response(
            request_id=request.headers.get("x-request-id") or str(uuid.uuid4())
        )
    return await _build_batch_response(session, batch=batch)


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
        content=_build_optimization_status_response_content(opt),
        status_code=status.HTTP_200_OK,
    )


async def _finalize_cancelled_billing(
    *,
    opt: Optimization,
    user_id: uuid.UUID,
) -> str:
    billing_metadata = _optimization_billing_metadata(opt)
    raw_charge_id = billing_metadata.get("charge_id")
    if not billing_metadata.get("reserved") or not raw_charge_id:
        _set_optimization_billing_metadata(opt, {"refund_status": "not_applicable"})
        return "not_applicable"
    if billing_metadata.get("cancel_finalize_attempted"):
        return _refund_status_from_optimization(opt)

    elapsed_seconds = float(opt.solve_seconds or 0.0)
    try:
        charge_id = uuid.UUID(str(raw_charge_id))
    except ValueError:
        _set_optimization_billing_metadata(
            opt,
            {
                "cancel_finalize_attempted": True,
                "cancel_finalize_status": "invalid_charge_id",
                "refund_status": "pending_reconciliation",
            },
        )
        _merge_optimization_error(
            opt,
            {
                "billing_cancel_finalize_failed": True,
                "billing_finalize_failed": True,
                "billing_finalize_error": "invalid billing charge id in metadata",
                "billing_charge_id": str(raw_charge_id),
                "billing_elapsed_seconds": elapsed_seconds,
                "billing_status": "failure",
                "billing_failure_reason": "user_cancelled",
                "billing_retry_count": 0,
                "refund_status": "pending_reconciliation",
            },
        )
        return "pending_reconciliation"

    refund_outcome = await billing_client.refund_user_cancel(
        charge_id,
        user_id,
        source_ref=str(opt.id),
        elapsed_seconds=elapsed_seconds,
    )
    if refund_outcome.ok:
        current_state = (
            refund_outcome.body.get("current_state")
            if isinstance(refund_outcome.body, dict)
            else None
        )
        refund_status = "refunded" if current_state in {"refunded", "rolled_back"} else "finalized"
        _set_optimization_billing_metadata(
            opt,
            {
                "cancel_finalize_attempted": True,
                "cancel_finalize_status": refund_outcome.status_code,
                "refund_status": refund_status,
            },
        )
        _merge_optimization_error(
            opt,
            {
                "billing_status": "failure",
                "billing_failure_reason": "user_cancelled",
                "refund_status": refund_status,
            },
        )
        return refund_status

    _set_optimization_billing_metadata(
        opt,
        {
            "cancel_finalize_attempted": True,
            "cancel_finalize_status": refund_outcome.status_code,
            "refund_status": "pending_reconciliation",
        },
    )
    _merge_optimization_error(
        opt,
        {
            "billing_operation": "user_cancel_refund",
            "billing_user_cancel_refund_failed": True,
            "billing_cancel_finalize_failed": True,
            "billing_finalize_failed": True,
            "billing_finalize_error": refund_outcome.error_message,
            "billing_charge_id": str(charge_id),
            "billing_source_ref": str(opt.id),
            "billing_elapsed_seconds": elapsed_seconds,
            "billing_status": "failure",
            "billing_failure_reason": "user_cancelled",
            "billing_retry_count": 0,
            "refund_status": "pending_reconciliation",
        },
    )
    return "pending_reconciliation"


@router.delete(
    "/optimizations/{optimization_id}",
    tags=["execution"],
    summary="取消 async optimization (FR E8)",
)
async def delete_optimization(
    optimization_id: uuid.UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    client_ip = request.client.host if request.client else None
    user_id, _api_key_id, scopes = await verify_api_key(authorization, session, client_ip=client_ip)
    require_scope("optimize:write", scopes)
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

    result = await session.execute(
        select(Optimization).where(Optimization.id == optimization_id).with_for_update()
    )
    opt = result.scalar_one_or_none()
    if opt is None or opt.user_id != user_id:
        return _rfc7807_error(
            title="Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"optimization {optimization_id} not found",
            request_id=request_id,
        )
    if opt.status == "cancelled":
        return JSONResponse(
            content=_build_optimization_status_response_content(opt),
            status_code=status.HTTP_200_OK,
        )
    if opt.status not in {"queued", "in_progress"}:
        return _cancellation_not_allowed_response(opt=opt, request_id=request_id)

    opt.status = "cancelled"
    opt.completed_at = datetime.now(UTC)
    _merge_optimization_error(
        opt,
        {
            "title": "Optimization Cancelled",
            "detail": "cancelled by user request",
            "billing_status": "failure",
            "billing_failure_reason": "user_cancelled",
        },
    )
    refund_status = await _finalize_cancelled_billing(opt=opt, user_id=user_id)
    _merge_optimization_error(opt, {"refund_status": refund_status})

    return JSONResponse(
        content=_build_optimization_status_response_content(opt),
        status_code=status.HTTP_200_OK,
    )
