"""Billing HTTP routes (Story 5.A.1 + 5.A.4 + 5.A.5 + 5.A.6).

Endpoints (all require Bearer JWT or X-Internal-Service-Auth):
- GET  /v1/billing/balance               — read current credits balance (pure)
- POST /v1/billing/topups                — create pending topup request
- POST /v1/billing/topups/{id}/confirm   — internal payment-confirmation credit
- POST /v1/billing/charges/estimate      — 5.A.5: pre-charge guard preview
- POST /v1/billing/charges               — create a Saga + lazy-seed if first call (5.A.5: gates on `confirmed` when warnings exist)
- POST /v1/billing/charges/{id}/reserve  — 5.A.4: PENDING → RESERVED only
- POST /v1/billing/charges/{id}/finalize — 5.A.4: RESERVED → CHARGED (per-formula) or REFUNDED
- POST /v1/billing/charges/{id}/confirm  — DEPRECATED 5.A.1 (reserve + service_success in one)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from fastapi import APIRouter, Depends, Header, HTTPException, status
from opticloud_shared.errors import ErrorDetail, rfc7807_error
from prometheus_client import Counter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from billing_service.auth_dep import require_internal_service, require_user
from billing_service.buckets import (
    ALL_BUCKETS,
    BUCKET_EXPIRES_HINT_ZH,
    BUCKET_LABELS_ZH,
    BUCKET_SIGNUP,
    BUCKET_TOPUP,
)
from billing_service.config import settings
from billing_service.db import get_session
from billing_service.exceptions import (
    CrossTenantKeyError,
    IdempotencyConflictError,
    InvalidSagaTransitionError,
    SagaNotFoundError,
    SagaTerminalError,
)
from billing_service.models import CreditTransaction, OutboxEvent, SagaInstance
from billing_service.pricing import classify_warnings, compute_charge_amount
from billing_service.saga_orchestrator import SagaOrchestrator
from billing_service.schemas import (
    BalanceResponse,
    BucketBalance,
    ChargeCreateRequest,
    ChargeResponse,
    EstimateRequest,
    EstimateResponse,
    FinalizeChargeRequest,
    FinalizeChargeResponse,
    ReserveChargeResponse,
    TopupConfirmRequest,
    TopupCreateRequest,
    TopupResponse,
    WarningResponse,
    validate_idempotency_key,
)

billing_router = APIRouter(prefix="/v1/billing", tags=["billing"])

# SRE1 — Story 5.A.5: pre-charge guard observability
ESTIMATE_TOTAL: Counter = Counter(
    "billing_estimate_total",
    "POST /v1/billing/charges/estimate calls labelled by warning shape",
    ["warnings_kind"],
)


def _problem_response(
    *,
    title: str,
    status_code: int,
    detail: str,
    errors: list[ErrorDetail] | None = None,
) -> Response:
    """Typed wrapper around the shared RFC 7807 helper for strict mypy."""
    return cast(
        Response,
        rfc7807_error(
            title=title,
            status_code=status_code,
            detail=detail,
            errors=errors,
        ),
    )


async def _balance_for(session: AsyncSession, user_id: uuid.UUID) -> Decimal:
    """Sum credit_transactions.amount for user; returns Decimal('0.00') if none."""
    stmt = select(func.coalesce(func.sum(CreditTransaction.amount), Decimal("0"))).where(
        CreditTransaction.user_id == user_id
    )
    result = await session.execute(stmt)
    total = result.scalar_one()
    return Decimal(str(total)).quantize(Decimal("0.0001"))


async def _balance_buckets_for(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Decimal]:
    """Per-bucket balance for a user (Story 5.A.2 FR B1).

    Always returns all 4 canonical bucket names; buckets with no rows get 0.
    """
    stmt = (
        select(CreditTransaction.bucket, func.sum(CreditTransaction.amount))
        .where(CreditTransaction.user_id == user_id)
        .group_by(CreditTransaction.bucket)
    )
    rows = (await session.execute(stmt)).all()
    by_bucket: dict[str, Decimal] = {row[0]: Decimal(str(row[1])) for row in rows}
    return {name: by_bucket.get(name, Decimal("0")) for name in ALL_BUCKETS}


async def _has_any_transactions(session: AsyncSession, user_id: uuid.UUID) -> bool:
    stmt = (
        select(func.count())
        .select_from(CreditTransaction)
        .where(CreditTransaction.user_id == user_id)
    )
    result = await session.execute(stmt)
    return bool(result.scalar_one())


async def _seed_demo_balance(session: AsyncSession, user_id: uuid.UUID) -> None:
    """A2: lazy-seed first-time user with J1 demo balance (POST only).

    Story 5.A.2: tagged as bucket="signup" so the dashboard shows the
    starter ¥50 in the 注册 bucket (not 月度).
    """
    seed_amount = Decimal(settings.j1_demo_seed_amount)
    session.add(
        CreditTransaction(
            user_id=user_id,
            saga_id=None,
            amount=seed_amount,
            kind="topup",
            bucket=BUCKET_SIGNUP,
            currency="CNY",
            metadata_json={"source": "j1_demo_seed"},
            created_at=datetime.now(UTC),
        )
    )
    await session.flush()


def _topup_response(saga: SagaInstance, *, balance_after: Decimal | None = None) -> TopupResponse:
    amount = saga.amount or Decimal("0")
    return TopupResponse(
        topup_id=str(saga.id),
        current_state=saga.current_state,
        amount=f"{amount:.2f}",
        bucket="topup",
        expires_at=None,
        expires_hint=BUCKET_EXPIRES_HINT_ZH[BUCKET_TOPUP] or "永不过期",
        balance_after=f"{balance_after:.2f}" if balance_after is not None else None,
    )


async def _topup_ledger_rows(session: AsyncSession, topup_id: uuid.UUID) -> list[CreditTransaction]:
    stmt = select(CreditTransaction).where(
        CreditTransaction.saga_id == topup_id,
        CreditTransaction.kind == "topup",
        CreditTransaction.bucket == BUCKET_TOPUP,
    )
    return list((await session.execute(stmt)).scalars().all())


def _ledger_payment_ref(row: CreditTransaction) -> str | None:
    raw = row.metadata_json.get("payment_ref")
    return raw if isinstance(raw, str) else None


def _classify_with_settings(estimated: Decimal, balance: Decimal) -> list[WarningResponse]:
    """Run classify_warnings with current config thresholds; convert to response shape."""
    warnings = classify_warnings(
        estimated_amount=estimated,
        balance=balance,
        p5_call_threshold=settings.p5_call_threshold,
        balance_low_ratio=settings.balance_low_ratio,
    )
    return [
        WarningResponse(
            kind=w.kind,  # type: ignore[arg-type]
            message=w.message,
            remediation_hint_key=w.remediation_hint_key,
        )
        for w in warnings
    ]


@billing_router.post(
    "/charges/estimate",
    response_model=EstimateResponse,
)
async def estimate_charge(
    body: EstimateRequest,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> EstimateResponse:
    """Story 5.A.5 — pre-charge guard preview.

    Pure read: no Saga, no seeding, no ledger write. Returns the estimated max
    amount, current balance, and 0-1 warnings based on the pre-charge guard
    rules in config (p5_call_threshold + balance_low_ratio).

    `purpose` is ignored for amount computation in v1 (LP-only pricing) but
    persisted in the metric label so M3 analytics can split by call type.
    """
    estimated = Decimal(str(body.max_solve_seconds)) * settings.lp_rate_per_second
    balance = await _balance_for(session, user_id)
    warnings = _classify_with_settings(estimated, balance)

    metric_label = warnings[0].kind if warnings else "none"
    ESTIMATE_TOTAL.labels(warnings_kind=metric_label).inc()

    return EstimateResponse(
        estimated_amount=f"{estimated:.2f}",
        currency="CNY",
        balance=f"{balance:.2f}",
        warnings=warnings,
        requires_explicit_confirm=bool(warnings),
    )


@billing_router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> BalanceResponse:
    """Story 5.A.1 AC2 + 5.A.2 FR B1: pure read — no seeding side effect.

    Returns total balance + 4-bucket breakdown (always all 4 buckets, zero if empty).
    """
    balance = await _balance_for(session, user_id)
    by_bucket = await _balance_buckets_for(session, user_id)
    last_stmt = (
        select(CreditTransaction.created_at)
        .where(CreditTransaction.user_id == user_id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(1)
    )
    last = (await session.execute(last_stmt)).scalar_one_or_none()

    buckets_resp = [
        BucketBalance(
            name=name,  # type: ignore[arg-type]
            label_zh=BUCKET_LABELS_ZH[name],
            balance=f"{by_bucket[name]:.2f}",
            expires_hint=BUCKET_EXPIRES_HINT_ZH[name],
        )
        for name in ALL_BUCKETS
    ]
    return BalanceResponse(
        user_id=str(user_id),
        balance=f"{balance:.2f}",
        currency="CNY",
        last_transaction_at=last,
        buckets=buckets_resp,
    )


@billing_router.post("/topups", response_model=TopupResponse, status_code=status.HTTP_201_CREATED)
async def create_topup(
    body: TopupCreateRequest,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> Response | TopupResponse:
    """Story 5.A.6 — create an idempotent pending topup request.

    This public route never credits the ledger. Credits are written only by the
    internal payment-confirmation route after a trusted payment callback.
    """
    try:
        validate_idempotency_key(idempotency_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    orch = SagaOrchestrator(session)
    try:
        saga = await orch.start(
            saga_type="topup",
            user_id=user_id,
            idempotency_key=idempotency_key,
            payload={
                "reference_id": body.reference_id,
                "purpose": "topup",
            },
            amount=body.amount,
        )
    except CrossTenantKeyError as e:
        await session.rollback()
        return _problem_response(
            title="Cross-tenant key reuse forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except IdempotencyConflictError as e:
        await session.rollback()
        return _problem_response(
            title="Idempotency Conflict",
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    await session.commit()
    return _topup_response(saga)


@billing_router.post("/topups/{topup_id}/confirm", response_model=TopupResponse)
async def confirm_topup(
    topup_id: uuid.UUID,
    body: TopupConfirmRequest,
    _internal: None = Depends(require_internal_service),
    session: AsyncSession = Depends(get_session),
) -> Response | TopupResponse:
    """Story 5.A.6 — internal payment confirmation writes topup Credits once."""
    stmt = select(SagaInstance).where(SagaInstance.id == topup_id).with_for_update()
    saga = (await session.execute(stmt)).scalar_one_or_none()
    if saga is None or saga.saga_type != "topup":
        await session.rollback()
        return _problem_response(
            title="Topup Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"topup {topup_id} not found",
        )

    amount = saga.amount or Decimal("0")
    existing_rows = await _topup_ledger_rows(session, topup_id)
    if existing_rows:
        existing_ref = _ledger_payment_ref(existing_rows[0])
        if existing_ref != body.payment_ref:
            await session.rollback()
            return _problem_response(
                title="Payment Reference Conflict",
                status_code=status.HTTP_409_CONFLICT,
                detail="topup has already been confirmed with a different payment_ref",
            )
        balance_after = await _balance_for(session, saga.user_id)
        return _topup_response(saga, balance_after=balance_after)

    if saga.current_state != "pending":
        await session.rollback()
        return _problem_response(
            title="Topup Already Finalized",
            status_code=status.HTTP_409_CONFLICT,
            detail=f"topup is already {saga.current_state}",
        )

    now = datetime.now(UTC)
    saga.current_state = "completed"
    saga.updated_at = now
    session.add(
        CreditTransaction(
            user_id=saga.user_id,
            saga_id=saga.id,
            amount=amount,
            kind="topup",
            bucket=BUCKET_TOPUP,
            currency="CNY",
            metadata_json={
                "provider": body.provider,
                "payment_ref": body.payment_ref,
                "expires_at": None,
            },
            created_at=now,
        )
    )
    session.add(
        OutboxEvent(
            aggregate_type="saga_instance",
            aggregate_id=saga.id,
            event_type="billing.topup.confirmed",
            event_version=1,
            payload={
                "saga_id": str(saga.id),
                "saga_type": saga.saga_type,
                "to_state": saga.current_state,
                "bucket": BUCKET_TOPUP,
                "provider": body.provider,
                "payment_ref": body.payment_ref,
            },
            headers={"compensation": "none"},
            occurred_at=now,
        )
    )

    await session.commit()
    balance_after = await _balance_for(session, saga.user_id)
    return _topup_response(saga, balance_after=balance_after)


@billing_router.post("/charges", response_model=ChargeResponse, status_code=status.HTTP_201_CREATED)
async def create_charge(
    body: ChargeCreateRequest,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> Response | ChargeResponse:
    """AC1 + AC2 lazy-seed + AC6 insufficient balance."""
    try:
        validate_idempotency_key(idempotency_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    if not await _has_any_transactions(session, user_id):
        await _seed_demo_balance(session, user_id)

    balance_before = await _balance_for(session, user_id)
    if body.amount > balance_before:
        await session.commit()
        return _problem_response(
            title="Insufficient balance",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Required: ¥{body.amount}, available: ¥{balance_before}",
            errors=[
                ErrorDetail(
                    field_path="body.amount",
                    value=str(body.amount),
                    constraint="amount > balance",
                    remediation_hint_key="errors.422.insufficient_balance",
                )
            ],
        )

    # Story 5.A.5 — pre-charge guard (FR B6): require explicit confirm when warnings exist
    warnings = _classify_with_settings(body.amount, balance_before)
    if warnings and not body.confirmed:
        await session.commit()
        return _problem_response(
            title="Explicit Confirmation Required",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=warnings[0].message,
            errors=[
                ErrorDetail(
                    field_path="body.confirmed",
                    value="false",
                    constraint="warnings exist, confirmed must be true",
                    remediation_hint_key=warnings[0].remediation_hint_key,
                )
            ],
        )

    # 5.A.5 — audit trail: deterministic flag (boolean, not timestamp, so idempotent replays
    # produce the same body hash). The "when" is saga.created_at; the user_id is saga.user_id.
    confirm_payload: dict[str, str] = {}
    if warnings and body.confirmed:
        confirm_payload["confirmation_ref"] = "precharge-confirmed"

    orch = SagaOrchestrator(session)
    try:
        saga = await orch.start(
            saga_type=f"{body.purpose}_charge",
            user_id=user_id,
            idempotency_key=idempotency_key,
            payload={
                "reference_id": body.reference_id,
                "purpose": body.purpose,
                # Story 5.A.5 — audit trail for pre-charge guard explicit confirm
                **confirm_payload,
            },
            amount=body.amount,
        )
    except CrossTenantKeyError as e:
        await session.rollback()
        return _problem_response(
            title="Cross-tenant key reuse forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except IdempotencyConflictError as e:
        await session.rollback()
        return _problem_response(
            title="Idempotency Conflict",
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    await session.commit()
    balance_after = await _balance_for(session, user_id)

    return ChargeResponse(
        charge_id=str(saga.id),
        current_state=saga.current_state,
        amount=f"{body.amount:.2f}",
        currency="CNY",
        balance_before=f"{balance_before:.2f}",
        balance_after=f"{balance_after:.2f}",  # unchanged until /confirm
    )


@billing_router.post(
    "/charges/{charge_id}/reserve",
    response_model=ReserveChargeResponse,
)
async def reserve_charge(
    charge_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> Response | ReserveChargeResponse:
    """Story 5.A.4 — split-phase reserve only (PENDING → RESERVED)."""
    orch = SagaOrchestrator(session)
    try:
        saga = await orch.get(charge_id)
    except SagaNotFoundError as e:
        await session.rollback()
        return _problem_response(
            title="Charge Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    if saga.user_id != user_id:
        await session.rollback()
        return _problem_response(
            title="Forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            detail="charge belongs to another user",
        )

    try:
        saga = await orch.apply(charge_id, "reserve")
    except (InvalidSagaTransitionError, SagaTerminalError) as e:
        await session.rollback()
        return _problem_response(
            title="Reserve Not Applicable",
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    await session.commit()
    balance_after = await _balance_for(session, user_id)

    return ReserveChargeResponse(
        charge_id=str(saga.id),
        current_state=saga.current_state,
        amount_reserved=f"{saga.amount:.2f}" if saga.amount else "0.00",
        balance_after_reserve=f"{balance_after:.2f}",
    )


async def _ledger_rows_for_saga(
    session: AsyncSession, saga_id: uuid.UUID
) -> list[CreditTransaction]:
    """Read all credit_transactions rows tied to one saga (R1.3 rebuild)."""
    stmt = select(CreditTransaction).where(CreditTransaction.saga_id == saga_id)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


def _max_solve_seconds_from(saga: SagaInstance) -> float:
    """Return finalization cap seconds.

    Legacy 5.A.4 rows may still contain `payload_ref.max_solve_seconds`. New
    5.A.0 rows keep payload_ref pointer-only, so derive cap from reserved amount
    and configured LP rate.
    """
    raw = saga.payload_ref.get("max_solve_seconds") if saga.payload_ref else None
    if raw is None:
        if saga.amount is not None and settings.lp_rate_per_second > 0:
            return float(saga.amount / settings.lp_rate_per_second)
        return settings.charge_max_solve_seconds_default
    return float(raw)


def _discount_context(discount_multiplier: Decimal) -> dict[str, str]:
    if discount_multiplier == Decimal("1.0"):
        return {}
    return {"discount_multiplier": f"{discount_multiplier:.4f}"}


def _rebuild_finalize_response(
    saga: SagaInstance,
    ledger_rows: list[CreditTransaction],
    balance_after: Decimal,
) -> FinalizeChargeResponse:
    """R1.3 — replay/idempotent rebuild from terminal-state ledger rows.

    Ledger sign convention:
      kind=charge          → -reserved (debit, written by orchestrator service_success)
      kind=refund_partial  → +(reserved - actual)
      kind=refund          → +reserved (written by orchestrator user_cancel)
      kind=refund_reversal → -reserved (R1.1 net-zero compensation)

    For a successful charge: net = (-reserved) + (reserved - actual) = -actual.
    For a failure:           net = (+reserved) + (-reserved) = 0.
    """
    reserved = saga.amount or Decimal("0")
    charge_sum = sum(
        (r.amount for r in ledger_rows if r.kind == "charge"),
        start=Decimal("0"),
    )
    refund_partial = sum(
        (r.amount for r in ledger_rows if r.kind == "refund_partial"),
        start=Decimal("0"),
    )
    # actual_amount is what the user effectively paid (positive number)
    actual = -(charge_sum + refund_partial) if charge_sum < 0 else Decimal("0")
    # balance_before = balance_after - net_change; net_change for success = -actual
    balance_before = balance_after + actual
    return FinalizeChargeResponse(
        charge_id=str(saga.id),
        current_state=saga.current_state,
        reserved_amount=f"{reserved:.2f}",
        actual_amount=f"{actual:.2f}",
        refund_partial_amount=f"{refund_partial:.2f}",
        balance_before=f"{balance_before:.2f}",
        balance_after=f"{balance_after:.2f}",
    )


@billing_router.post(
    "/charges/{charge_id}/finalize",
    response_model=FinalizeChargeResponse,
)
async def finalize_charge(
    charge_id: uuid.UUID,
    body: FinalizeChargeRequest,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> Response | FinalizeChargeResponse:
    """Story 5.A.4 — RESERVED → CHARGED (per-formula amount) or REFUNDED."""
    orch = SagaOrchestrator(session)
    try:
        saga = await orch.get(charge_id)
    except SagaNotFoundError as e:
        await session.rollback()
        return _problem_response(
            title="Charge Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    if saga.user_id != user_id:
        await session.rollback()
        return _problem_response(
            title="Forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            detail="charge belongs to another user",
        )

    # R1.3 — idempotent replay if already terminal
    if saga.current_state in ("charged", "completed", "refunded", "rolled_back"):
        ledger_rows = await _ledger_rows_for_saga(session, saga.id)
        balance_after = await _balance_for(session, user_id)
        return _rebuild_finalize_response(saga, ledger_rows, balance_after)

    reserved_amount = saga.amount or Decimal("0")
    balance_before = await _balance_for(session, user_id)

    if body.status == "success":
        max_seconds = _max_solve_seconds_from(saga)
        actual = compute_charge_amount(
            elapsed_seconds=body.elapsed_seconds,
            max_solve_seconds=max_seconds,
            rate_per_second=settings.lp_rate_per_second,
            min_amount=settings.charge_min_amount,
            reserved_amount=reserved_amount,
            discount_multiplier=body.discount_multiplier,
        )

        # Apply transition first — orchestrator writes the `-reserved kind=charge` row + outbox event
        try:
            saga = await orch.apply(
                charge_id,
                "service_success",
                context={
                    "reserved_amount": f"{reserved_amount:.4f}",
                    "actual_amount": f"{actual:.4f}",
                    "elapsed_seconds": body.elapsed_seconds,
                    **_discount_context(body.discount_multiplier),
                },
            )
        except (InvalidSagaTransitionError, SagaTerminalError) as e:
            await session.rollback()
            return _problem_response(
                title="Finalize Not Applicable",
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )

        # AC4 fix — orchestrator writes -reserved (i.e. saga.amount × -1) via service_success.
        # If actual < reserved, write a compensating +refund_partial row in same tx so the
        # ledger nets to -actual (the correct charge).
        refund_partial = Decimal("0")
        if actual < reserved_amount:
            refund_partial = reserved_amount - actual
            session.add(
                CreditTransaction(
                    user_id=user_id,
                    saga_id=saga.id,
                    amount=refund_partial,
                    kind="refund_partial",
                    currency="CNY",
                    metadata_json={
                        "reason": "elapsed < max_solve_seconds",
                        "elapsed_seconds": body.elapsed_seconds,
                        "actual_amount": f"{actual:.4f}",
                        **_discount_context(body.discount_multiplier),
                    },
                    created_at=datetime.now(UTC),
                )
            )

        await session.commit()
        balance_after = await _balance_for(session, user_id)
        return FinalizeChargeResponse(
            charge_id=str(saga.id),
            current_state=saga.current_state,
            reserved_amount=f"{reserved_amount:.2f}",
            actual_amount=f"{actual:.2f}",
            refund_partial_amount=f"{refund_partial:.2f}",
            balance_before=f"{balance_before:.2f}",
            balance_after=f"{balance_after:.2f}",
        )

    # status == "failure" — apply user_cancel; orchestrator writes +reserved kind=refund row.
    # R1.1: write compensating -reserved kind=refund_reversal row (net zero) since reserve
    # never wrote a debit. Both rows live in audit trail.
    try:
        saga = await orch.apply(
            charge_id,
            "user_cancel",
            context={
                "failure_reason": body.failure_reason or "unknown",
                "elapsed_seconds": body.elapsed_seconds,
            },
        )
    except (InvalidSagaTransitionError, SagaTerminalError) as e:
        await session.rollback()
        return _problem_response(
            title="Finalize Not Applicable",
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    session.add(
        CreditTransaction(
            user_id=user_id,
            saga_id=saga.id,
            amount=-reserved_amount,
            kind="refund_reversal",
            currency="CNY",
            metadata_json={
                "reason": "reservation never debited; net-zero compensation",
                "failure_reason": body.failure_reason or "unknown",
            },
            created_at=datetime.now(UTC),
        )
    )

    await session.commit()
    balance_after = await _balance_for(session, user_id)
    return FinalizeChargeResponse(
        charge_id=str(saga.id),
        current_state=saga.current_state,
        reserved_amount=f"{reserved_amount:.2f}",
        actual_amount="0.00",
        refund_partial_amount="0.00",
        balance_before=f"{balance_before:.2f}",
        balance_after=f"{balance_after:.2f}",
    )


@billing_router.post(
    "/charges/{charge_id}/confirm",
    response_model=ChargeResponse,
    deprecated=True,
)
async def confirm_charge(
    charge_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> Response | ChargeResponse:
    """DEPRECATED (5.A.1) — apply reserve + service_success in one call.

    Replaced by the 2-phase /reserve + /finalize endpoints (Story 5.A.4).
    Slated for removal in M3.
    """
    orch = SagaOrchestrator(session)
    try:
        saga = await orch.get(charge_id)
    except SagaNotFoundError as e:
        await session.rollback()
        return _problem_response(
            title="Charge Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    if saga.user_id != user_id:
        await session.rollback()
        return _problem_response(
            title="Forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            detail="charge belongs to another user",
        )

    balance_before = await _balance_for(session, user_id)

    try:
        saga = await orch.apply(charge_id, "reserve")
        saga = await orch.apply(charge_id, "service_success")
    except (InvalidSagaTransitionError, SagaTerminalError) as e:
        await session.rollback()
        return _problem_response(
            title="Charge Already Finalized",
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    await session.commit()
    balance_after = await _balance_for(session, user_id)

    return ChargeResponse(
        charge_id=str(saga.id),
        current_state=saga.current_state,
        amount=f"{saga.amount:.2f}" if saga.amount else "0.00",
        currency="CNY",
        balance_before=f"{balance_before:.2f}",
        balance_after=f"{balance_after:.2f}",
    )


__all__ = ["billing_router"]
