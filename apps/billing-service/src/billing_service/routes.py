"""Billing HTTP routes (Story 5.A.1).

Endpoints (all require Bearer JWT):
- GET  /v1/billing/balance               — read current credits balance (pure)
- POST /v1/billing/charges               — create a Saga + lazy-seed if first call
- POST /v1/billing/charges/{id}/confirm  — apply reserve + service_success (5.A.1 simplified)
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
    IdempotencyConflictError,
    InvalidSagaTransitionError,
    SagaNotFoundError,
    SagaTerminalError,
)
from billing_service.models import CreditTransaction
from billing_service.saga_orchestrator import SagaOrchestrator
from billing_service.schemas import (
    BalanceResponse,
    ChargeCreateRequest,
    ChargeResponse,
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
            payload={"reference_id": body.reference_id, "purpose": body.purpose},
            amount=body.amount,
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


@billing_router.post("/charges/{charge_id}/confirm", response_model=ChargeResponse)
async def confirm_charge(
    charge_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> Response | ChargeResponse:
    """AC1 simplified — apply reserve + service_success in one call."""
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
