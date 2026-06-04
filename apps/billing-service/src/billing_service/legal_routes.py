"""Team+ legal inquiry routes — Story 8.C.3."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, status
from opticloud_shared.errors import ErrorDetail
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from billing_service.auth_dep import require_user
from billing_service.config import settings
from billing_service.db import get_session
from billing_service.models import (
    BillingSubscription,
    IdempotencyKeyRow,
    LegalInquiry,
    OutboxEvent,
)
from billing_service.problem_details import billing_problem_response
from billing_service.saga_orchestrator import hash_body
from billing_service.schemas import (
    LegalInquiryRequest,
    LegalInquiryResponse,
    LegalTicketResponse,
    validate_idempotency_key,
)

legal_router = APIRouter(prefix="/v1/legal", tags=["legal"])
TEAM_PLUS_PLANS = {"team", "enterprise"}
LEGAL_SLA_HOURS = 24


def _problem_response(
    *,
    title: str,
    status_code: int,
    detail: str,
    errors: list[ErrorDetail] | None = None,
) -> Response:
    return billing_problem_response(
        title=title,
        status_code=status_code,
        detail=detail,
        errors=errors,
    )


def _legal_request_hash(body: LegalInquiryRequest) -> str:
    return hash_body(
        {
            "operation": "legal_inquiry_create",
            "body": body.model_dump(mode="json"),
        }
    )


def _legal_response_json(response: LegalInquiryResponse) -> dict[str, Any]:
    return response.model_dump(mode="json")


def _legal_response(
    *,
    inquiry_id: uuid.UUID,
    submitted_at: datetime,
    sla_due_at: datetime,
    ticket_key: str,
) -> LegalInquiryResponse:
    return LegalInquiryResponse(
        inquiry_id=str(inquiry_id),
        status="submitted",
        submitted_at=submitted_at,
        sla_due_at=sla_due_at,
        linear_ticket=LegalTicketResponse(reference=ticket_key),
    )


def _ticket_key(now: datetime) -> str:
    return f"OPTI-LEGAL-{now:%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"


async def _idempotency_row_by_key(
    session: AsyncSession,
    idempotency_key: str,
) -> IdempotencyKeyRow | None:
    return await session.get(IdempotencyKeyRow, idempotency_key)


async def _active_team_subscription_for(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    now: datetime,
) -> BillingSubscription | None:
    stmt = (
        select(BillingSubscription)
        .where(
            BillingSubscription.user_id == user_id,
            BillingSubscription.status == "active",
            BillingSubscription.plan_code.in_(TEAM_PLUS_PLANS),
            BillingSubscription.current_period_end > now,
        )
        .with_for_update()
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _outbox_payload(inquiry: LegalInquiry) -> dict[str, str | int]:
    return {
        "inquiry_id": str(inquiry.id),
        "ticket_key": inquiry.ticket_key,
        "plan_code": inquiry.plan_code,
        "category": inquiry.category,
        "urgency": inquiry.urgency,
        "status": inquiry.status,
        "submitted_at": inquiry.submitted_at.isoformat(),
        "sla_due_at": inquiry.sla_due_at.isoformat(),
        "sla_hours": LEGAL_SLA_HOURS,
    }


async def _upsert_legal_idempotency_row(
    session: AsyncSession,
    *,
    existing: IdempotencyKeyRow | None,
    idempotency_key: str,
    user_id: uuid.UUID,
    request_body_hash: str,
    response: LegalInquiryResponse,
    now: datetime,
) -> None:
    expires_at = now + timedelta(hours=settings.saga_idempotency_ttl_hours)
    response_body = _legal_response_json(response)
    if existing is not None:
        existing.user_id = user_id
        existing.request_body_hash = request_body_hash
        existing.response_body = response_body
        existing.saga_id = None
        existing.expires_at = expires_at
        existing.created_at = now
        await session.flush()
        return

    session.add(
        IdempotencyKeyRow(
            key=idempotency_key,
            user_id=user_id,
            request_body_hash=request_body_hash,
            response_body=response_body,
            saga_id=None,
            expires_at=expires_at,
            created_at=now,
        )
    )
    await session.flush()


async def _legal_replay_response_after_idempotency_race(
    session: AsyncSession,
    *,
    idempotency_key: str,
    user_id: uuid.UUID,
    request_body_hash: str,
) -> Response | LegalInquiryResponse | None:
    await session.rollback()
    existing = await _idempotency_row_by_key(session, idempotency_key)
    if existing is None:
        return None
    now = datetime.now(UTC)
    if existing.expires_at <= now:
        return None
    if existing.user_id != user_id:
        return _problem_response(
            title="Cross-tenant key reuse forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Idempotency-Key belongs to another tenant",
        )
    if existing.request_body_hash != request_body_hash:
        return _problem_response(
            title="Idempotency Conflict",
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency-Key was reused with a different request body",
        )
    if existing.response_body is not None:
        return LegalInquiryResponse.model_validate(existing.response_body)
    return _problem_response(
        title="Idempotency Conflict",
        status_code=status.HTTP_409_CONFLICT,
        detail="Idempotency-Key is linked to an incomplete legal inquiry submission",
    )


@legal_router.post(
    "/inquiry",
    response_model=LegalInquiryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_legal_inquiry(
    body: LegalInquiryRequest,
    user_id: Annotated[uuid.UUID, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> Response | LegalInquiryResponse:
    """Accept a Team+ legal inquiry and create a Linear-ready internal ticket pointer."""
    try:
        validate_idempotency_key(idempotency_key)
    except ValueError as exc:
        return _problem_response(
            title="Invalid Idempotency-Key",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    request_body_hash = _legal_request_hash(body)
    now = datetime.now(UTC)
    existing = await _idempotency_row_by_key(session, idempotency_key)
    existing_is_active = existing is not None and existing.expires_at > now
    if existing_is_active and existing is not None:
        if existing.user_id != user_id:
            await session.rollback()
            return _problem_response(
                title="Cross-tenant key reuse forbidden",
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Idempotency-Key belongs to another tenant",
            )
        if existing.request_body_hash != request_body_hash:
            await session.rollback()
            return _problem_response(
                title="Idempotency Conflict",
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency-Key was reused with a different request body",
            )
        if existing.response_body is not None:
            return LegalInquiryResponse.model_validate(existing.response_body)
        await session.rollback()
        return _problem_response(
            title="Idempotency Conflict",
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency-Key is linked to an incomplete legal inquiry submission",
        )

    subscription = await _active_team_subscription_for(session, user_id, now=now)
    if subscription is None:
        await session.rollback()
        return _problem_response(
            title="Team plan required",
            status_code=status.HTTP_403_FORBIDDEN,
            detail="legal inquiry SLA is available only to active Team or Enterprise plans",
        )

    submitted_at = now
    sla_due_at = submitted_at + timedelta(hours=LEGAL_SLA_HOURS)
    inquiry = LegalInquiry(
        id=uuid.uuid4(),
        user_id=user_id,
        subscription_id=subscription.id,
        plan_code=subscription.plan_code,
        category=body.category,
        contact_email=body.contact_email,
        company_name=body.company_name,
        subject=body.subject,
        message=body.message,
        urgency=body.urgency,
        status="submitted",
        ticket_key=_ticket_key(now),
        submitted_at=submitted_at,
        sla_due_at=sla_due_at,
        created_at=now,
        updated_at=now,
    )
    response = _legal_response(
        inquiry_id=inquiry.id,
        submitted_at=submitted_at,
        sla_due_at=sla_due_at,
        ticket_key=inquiry.ticket_key,
    )
    session.add(inquiry)
    session.add(
        OutboxEvent(
            aggregate_type="legal_inquiry",
            aggregate_id=inquiry.id,
            event_type="legal.inquiry.submitted",
            event_version=1,
            payload=_outbox_payload(inquiry),
            headers={"compensation": "none"},
            occurred_at=now,
        )
    )
    try:
        await _upsert_legal_idempotency_row(
            session,
            existing=existing if existing is not None and not existing_is_active else None,
            idempotency_key=idempotency_key,
            user_id=user_id,
            request_body_hash=request_body_hash,
            response=response,
            now=now,
        )
    except IntegrityError:
        replay = await _legal_replay_response_after_idempotency_race(
            session,
            idempotency_key=idempotency_key,
            user_id=user_id,
            request_body_hash=request_body_hash,
        )
        if replay is not None:
            return replay
        raise
    await session.commit()
    return response


__all__ = ["legal_router"]
