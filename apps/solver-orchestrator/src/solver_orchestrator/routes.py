"""Endpoints — FR C1-C8 + E1-E10 (Sprint 0 subset: Story 2.1 + 3.1)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from opticloud_shared.schemas.errors import ErrorDetail, ErrorResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from solver_orchestrator import billing_client, solvers
from solver_orchestrator.auth import require_scope, verify_api_key
from solver_orchestrator.catalog import (
    CATALOG,
    find_by_k_algo,
    find_by_task_type_and_solver,
)
from solver_orchestrator.db import get_session
from solver_orchestrator.models import IdempotencyKey, Optimization
from solver_orchestrator.schemas import (
    AlgorithmSchema,
    OptimizationRequest,
    OptimizationResponse,
)

router = APIRouter(prefix="/v1")
health_router = APIRouter()


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
    items = CATALOG
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
    return AlgorithmSchema.model_validate(algo)


# ===== Story 3.1: POST /v1/optimizations =====


def _hash_body(body: dict) -> str:  # type: ignore[type-arg]
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


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
    user_id, api_key_id, scopes = await verify_api_key(authorization, session)
    require_scope("optimize:write", scopes)

    body_dict = payload.model_dump(by_alias=True)
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

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
            select(IdempotencyKey).where(IdempotencyKey.key == idempotency_key)
        )
        existing = idem_query.scalar_one_or_none()
        if existing is not None:
            if existing.user_id != user_id:
                return _rfc7807_error(
                    title="Idempotency Conflict",
                    status_code=status.HTTP_409_CONFLICT,
                    detail="idempotency key in use by a different user",
                    request_id=request_id,
                )
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
                return _build_success_response(opt)

    # ----- Lookup algorithm catalog (Story 2.1 + 2.4 integration) -----
    algo, supported_solvers = find_by_task_type_and_solver(payload.task_type, payload.solver)
    if algo is None and not supported_solvers:
        # task_type itself unknown
        return _rfc7807_error(
            title="Unsupported Task Type",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"task_type '{payload.task_type}' not in catalog",
            errors=[
                ErrorDetail(
                    field_path="task_type",
                    value=payload.task_type,
                    constraint="must be one of catalog k_algo.task_type",
                    remediation_hint_key="errors.422.unsupported_task_type",
                )
            ],
            next_action="https://api.opticloud.cn/v1/algorithms",
            request_id=request_id,
        )
    if algo is None:
        # task_type known but solver not in any matching algorithm — Story 2.4 FR C4
        return _rfc7807_error(
            title="Unsupported Solver",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"solver '{payload.solver}' is not supported for task_type "
                f"'{payload.task_type}'. Supported: {', '.join(supported_solvers)}"
            ),
            errors=[
                ErrorDetail(
                    field_path="solver",
                    value=payload.solver,
                    constraint=f"must be one of: {', '.join(supported_solvers)}",
                    remediation_hint_key="errors.400.unsupported_solver",
                )
            ],
            next_action="https://api.opticloud.cn/v1/algorithms",
            request_id=request_id,
        )

    # Story 2.4 — solver-routing logic deferred (FR C6 / Story 2.6).
    # v1 catalog has 1 primary solver per algorithm; multi-solver routing is M2-M3.
    # Validation above ensures only allowed solver names reach here.

    # ----- Persist input -----
    opt = Optimization(
        user_id=user_id,
        api_key_id=api_key_id,
        task_type=payload.task_type,
        status="in_progress",
        input_payload=body_dict,
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

    result = solvers.solve_from_request(
        body_dict, max_solve_seconds=payload.options.max_solve_seconds
    )
    opt.solve_seconds = result.solve_seconds
    opt.model_version = dict(algo["model_version"])

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
            existing_error = opt.error or {}
            existing_error["billing_finalize_failed"] = True
            existing_error["billing_finalize_error"] = finalize_outcome.error_message
            existing_error["billing_charge_id"] = str(billing_uuid)
            existing_error["billing_elapsed_seconds"] = result.solve_seconds
            existing_error["billing_status"] = finalize_status
            existing_error["billing_failure_reason"] = failure_reason
            existing_error["billing_retry_count"] = 0
            opt.error = existing_error

    if result.status == "optimal":
        opt.status = "completed"
        opt.solution = result.solution
        opt.objective = result.objective
        opt.completed_at = datetime.now(UTC)
    elif result.status in ("infeasible", "unbounded"):
        opt.status = "failed"
        opt.completed_at = datetime.now(UTC)
        opt.error = {
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
        }
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
        opt.error = {"detail": result.error_constraint}
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
        opt.error = {"detail": result.error_constraint}
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


def _build_success_response(opt: Optimization) -> JSONResponse:
    """FR E1 + E9 — success response."""
    payload = OptimizationResponse(
        optimization_id=opt.id,
        status="completed",
        solution=opt.solution,
        objective=float(opt.objective) if opt.objective is not None else None,
        model_version=opt.model_version,  # type: ignore[arg-type]
        solve_seconds=float(opt.solve_seconds) if opt.solve_seconds is not None else 0.0,
        created_at=opt.created_at,
        completed_at=opt.completed_at or opt.created_at,
    )
    return JSONResponse(
        content=json.loads(payload.model_dump_json()),
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
    # Story 2.4 — solver validation (FR C4) on /demo as well
    algo, supported_solvers = find_by_task_type_and_solver("lp", payload.solver)
    if algo is None and not supported_solvers:
        return _rfc7807_error(
            title="Catalog Error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LP algorithm missing from catalog",
            request_id=request_id,
        )
    if algo is None:
        return _rfc7807_error(
            title="Unsupported Solver",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"solver '{payload.solver}' is not supported for task_type 'lp'. "
                f"Supported: {', '.join(supported_solvers)}"
            ),
            errors=[
                ErrorDetail(
                    field_path="solver",
                    value=payload.solver,
                    constraint=f"must be one of: {', '.join(supported_solvers)}",
                    remediation_hint_key="errors.400.unsupported_solver",
                )
            ],
            next_action="https://api.opticloud.cn/v1/algorithms",
            request_id=request_id,
        )

    result = solvers.solve_from_request(
        body_dict, max_solve_seconds=payload.options.max_solve_seconds
    )

    if result.status == "optimal":
        return JSONResponse(
            content={
                "status": "completed",
                "solution": result.solution,
                "objective": result.objective,
                "model_version": dict(algo["model_version"]),
                "solve_seconds": result.solve_seconds,
                "demo": True,
            },
            status_code=status.HTTP_200_OK,
        )
    if result.status in ("infeasible", "unbounded"):
        return _rfc7807_error(
            title=f"LP {result.status.capitalize()}",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.error_constraint or result.status,
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
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    user_id, _api_key_id, _scopes = await verify_api_key(authorization, session)
    opt = await session.get(Optimization, optimization_id)
    if opt is None or opt.user_id != user_id:
        return _rfc7807_error(
            title="Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"optimization {optimization_id} not found",
        )
    if opt.status == "completed":
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
