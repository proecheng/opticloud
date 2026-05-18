"""Billing HTTP routes (Story 5.A.1 + 5.A.4).

Endpoints (all require Bearer JWT or X-Internal-Service-Auth):
- GET  /v1/billing/balance               — read current credits balance (pure)
- POST /v1/billing/charges               — create a Saga + lazy-seed if first call
- POST /v1/billing/charges/{id}/reserve  — 5.A.4: PENDING → RESERVED only
- POST /v1/billing/charges/{id}/finalize — 5.A.4: RESERVED → CHARGED (per-formula) or REFUNDED
- POST /v1/billing/charges/{id}/confirm  — DEPRECATED 5.A.1 (reserve + service_success in one)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from opticloud_shared.errors import ErrorDetail, rfc7807_error
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from billing_service.auth_dep import require_user
from billing_service.config import settings
from billing_service.db import get_session
from billing_service.exceptions import (
    CrossTenantKeyError,
    IdempotencyConflictError,
    InvalidSagaTransitionError,
    SagaNotFoundError,
    SagaTerminalError,
)
from billing_service.models import CreditTransaction, SagaInstance
from billing_service.pricing import compute_charge_amount
from billing_service.saga_orchestrator import SagaOrchestrator
from billing_service.schemas import (
    BalanceResponse,
    ChargeCreateRequest,
    ChargeResponse,
    FinalizeChargeRequest,
    FinalizeChargeResponse,
    ReserveChargeResponse,
    validate_idempotency_key,
)

billing_router = APIRouter(prefix="/v1/billing", tags=["billing"])


async def _balance_for(session: AsyncSession, user_id: uuid.UUID) -> Decimal:
    """Sum credit_transactions.amount for user; returns Decimal('0.00') if none."""
    stmt = select(func.coalesce(func.sum(CreditTransaction.amount), Decimal("0"))).where(
        CreditTransaction.user_id == user_id
    )
    result = await session.execute(stmt)
    total = result.scalar_one()
    return Decimal(str(total)).quantize(Decimal("0.0001"))


async def _has_any_transactions(session: AsyncSession, user_id: uuid.UUID) -> bool:
    stmt = (
        select(func.count())
        .select_from(CreditTransaction)
        .where(CreditTransaction.user_id == user_id)
    )
    result = await session.execute(stmt)
    return bool(result.scalar_one())


async def _seed_demo_balance(session: AsyncSession, user_id: uuid.UUID) -> None:
    """A2: lazy-seed first-time user with J1 demo balance (POST only)."""
    seed_amount = Decimal(settings.j1_demo_seed_amount)
    session.add(
        CreditTransaction(
            user_id=user_id,
            saga_id=None,
            amount=seed_amount,
            kind="topup",
            currency="CNY",
            metadata_json={"source": "j1_demo_seed"},
            created_at=datetime.now(UTC),
        )
    )
    await session.flush()


@billing_router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> BalanceResponse:
    """AC2: pure read — no seeding side effect."""
    balance = await _balance_for(session, user_id)
    last_stmt = (
        select(CreditTransaction.created_at)
        .where(CreditTransaction.user_id == user_id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(1)
    )
    last = (await session.execute(last_stmt)).scalar_one_or_none()
    return BalanceResponse(
        user_id=str(user_id),
        balance=f"{balance:.2f}",
        currency="CNY",
        last_transaction_at=last,
    )


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
        return rfc7807_error(
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

    orch = SagaOrchestrator(session)
    try:
        saga = await orch.start(
            saga_type=f"{body.purpose}_charge",
            user_id=user_id,
            idempotency_key=idempotency_key,
            payload={
                "reference_id": body.reference_id,
                "purpose": body.purpose,
                # Story 5.A.4 (AC6) — finalize reads max from here to compute capped amount
                "max_solve_seconds": body.max_solve_seconds,
                "rate_per_second": str(settings.lp_rate_per_second),
            },
            amount=body.amount,
        )
    except CrossTenantKeyError as e:
        await session.rollback()
        return rfc7807_error(
            title="Cross-tenant key reuse forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except IdempotencyConflictError as e:
        await session.rollback()
        return rfc7807_error(
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
        return rfc7807_error(
            title="Charge Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    if saga.user_id != user_id:
        await session.rollback()
        return rfc7807_error(
            title="Forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            detail="charge belongs to another user",
        )

    try:
        saga = await orch.apply(charge_id, "reserve")
    except (InvalidSagaTransitionError, SagaTerminalError) as e:
        await session.rollback()
        return rfc7807_error(
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
    """DR1: payload_ref may omit max_solve_seconds for legacy 5.A.1 sagas."""
    raw = saga.payload_ref.get("max_solve_seconds") if saga.payload_ref else None
    if raw is None:
        return settings.charge_max_solve_seconds_default
    return float(raw)


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
        return rfc7807_error(
            title="Charge Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    if saga.user_id != user_id:
        await session.rollback()
        return rfc7807_error(
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
                },
            )
        except (InvalidSagaTransitionError, SagaTerminalError) as e:
            await session.rollback()
            return rfc7807_error(
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
        return rfc7807_error(
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
        return rfc7807_error(
            title="Charge Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    if saga.user_id != user_id:
        await session.rollback()
        return rfc7807_error(
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
        return rfc7807_error(
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
