"""Story 1.12 — frozen appeal lifecycle helpers."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service import account_merge, security
from auth_service.db import get_session
from auth_service.models import AccountFreezeAppeal, AccountMergeProposal, AuditLog, RiskFlag, User
from auth_service.schemas import (
    AccountMergeEvidence,
    AccountMergeProposalCreateRequest,
    AccountMergeProposalResponse,
    FrozenAppealAcceptRequest,
    FrozenAppealAcceptResponse,
    FrozenAppealProposalRequest,
    FrozenAppealRiskSummary,
    FrozenAppealStartRequest,
    FrozenAppealStartResponse,
    FrozenAppealStatusResponse,
)

APPEAL_TTL_HOURS = 24
PUBLIC_APPEAL_BASE_URL = "/auth/frozen-appeal"
FrozenAppealStatus = Literal["started", "proposal_submitted", "accepted", "expired"]
FrozenAppealNextAction = Literal[
    "submit_proposal",
    "await_review",
    "accept_merge",
    "completed",
    "contact_support",
]

router = APIRouter(prefix="/v1/auth/frozen-appeals", tags=["auth"])


def _now() -> datetime:
    return datetime.now(UTC)


def _appeal_status(value: str) -> FrozenAppealStatus:
    statuses: dict[str, FrozenAppealStatus] = {
        "started": "started",
        "proposal_submitted": "proposal_submitted",
        "accepted": "accepted",
        "expired": "expired",
    }
    if value in statuses:
        return statuses[value]
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="invalid appeal status"
    )


def _next_action_for_proposal(
    proposal: AccountMergeProposalResponse | None,
) -> FrozenAppealNextAction:
    if proposal is None:
        return "submit_proposal"
    if proposal.status in {"approved", "auto_approved"}:
        return "accept_merge"
    if proposal.status == "pending_review":
        return "await_review"
    if proposal.status == "accepted":
        return "completed"
    return "contact_support"


def _safe_risk_summary_from_user(user: User, flags: list[RiskFlag]) -> FrozenAppealRiskSummary:
    latest_flag_at = max((flag.created_at for flag in flags), default=None)
    latest_rule_codes: list[str] = []
    if flags:
        latest_timestamp = latest_flag_at
        latest_rule_codes = sorted(
            {
                flag.rule_code
                for flag in flags
                if latest_timestamp is not None and flag.created_at == latest_timestamp
            }
        )
    return FrozenAppealRiskSummary(
        total_flag_count=len(flags),
        latest_rule_codes=latest_rule_codes,
        latest_flag_at=latest_flag_at,
        risk_score=float(user.risk_score),
    )


async def _load_user_by_phone_email(session: AsyncSession, phone: str, email: str) -> User | None:
    stmt = select(User).where(User.phone == phone, User.email == email)
    return (await session.execute(stmt)).scalar_one_or_none()


async def _load_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return user


def _is_tombstoned(user: User) -> bool:
    return bool(user.deleted_at is not None or user.email.endswith("@invalid.local"))


def _tracking_token_hash(token: str) -> str:
    return security.hash_freeze_appeal_token(token)


async def _lookup_appeal_by_token(
    session: AsyncSession, appeal_id: uuid.UUID, tracking_token: str
) -> AccountFreezeAppeal | None:
    token_hash = _tracking_token_hash(tracking_token)
    appeal = (
        await session.execute(
            select(AccountFreezeAppeal).where(AccountFreezeAppeal.id == appeal_id)
        )
    ).scalar_one_or_none()
    if appeal is None:
        return None
    if not secrets.compare_digest(appeal.tracking_token_hash, token_hash):
        return None
    return appeal


async def _fetch_proposal_response(
    session: AsyncSession, proposal_id: uuid.UUID | None
) -> AccountMergeProposalResponse | None:
    if proposal_id is None:
        return None
    proposal = (
        await session.execute(
            select(AccountMergeProposal).where(AccountMergeProposal.id == proposal_id)
        )
    ).scalar_one_or_none()
    if proposal is None:
        return None
    return AccountMergeProposalResponse.model_validate(account_merge.proposal_to_response(proposal))


async def _latest_non_terminal_proposal(
    session: AsyncSession, user_id: uuid.UUID
) -> AccountMergeProposal | None:
    stmt = (
        select(AccountMergeProposal)
        .where(
            AccountMergeProposal.requester_user_id == user_id,
            AccountMergeProposal.status.in_(["pending_review", "approved", "auto_approved"]),
        )
        .order_by(AccountMergeProposal.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _user_risk_flags(session: AsyncSession, user_id: uuid.UUID) -> list[RiskFlag]:
    result = await session.execute(
        select(RiskFlag).where(RiskFlag.user_id == user_id).order_by(RiskFlag.created_at.asc())
    )
    return list(result.scalars().all())


async def _write_audit(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    actor: str,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID,
    metadata: dict[str, Any],
) -> None:
    session.add(
        AuditLog(
            user_id=user_id,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            audit_metadata=metadata,
        )
    )


def build_frozen_auth_error() -> dict[str, object]:
    return {
        "status": 403,
        "title": "账户已冻结",
        "detail": "account frozen",
        "next_action_url": PUBLIC_APPEAL_BASE_URL,
        "errors": [
            {
                "field_path": "account",
                "value": None,
                "constraint": "frozen",
                "remediation_hint_key": "auth.frozen.appeal",
            }
        ],
    }


@router.post(
    "/start",
    response_model=FrozenAppealStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a frozen-account appeal",
)
async def start_frozen_appeal_route(
    body: FrozenAppealStartRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> FrozenAppealStartResponse:
    return await start_frozen_appeal(session, body)


@router.get(
    "/{appeal_id}",
    response_model=FrozenAppealStatusResponse,
    summary="View a frozen appeal status",
)
async def get_frozen_appeal_route(
    appeal_id: uuid.UUID,
    tracking_token: str = Query(..., min_length=16, max_length=255),
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> FrozenAppealStatusResponse:
    return await get_frozen_appeal_status(session, appeal_id, tracking_token)


@router.post(
    "/{appeal_id}/proposal",
    response_model=FrozenAppealStatusResponse,
    summary="Submit a merge proposal for a frozen appeal",
)
async def submit_frozen_appeal_proposal_route(
    appeal_id: uuid.UUID,
    body: FrozenAppealProposalRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> FrozenAppealStatusResponse:
    return await submit_frozen_appeal_proposal(session, appeal_id, body)


@router.post(
    "/{appeal_id}/accept",
    response_model=FrozenAppealAcceptResponse,
    summary="Accept an approved frozen appeal merge",
)
async def accept_frozen_appeal_route(
    appeal_id: uuid.UUID,
    body: FrozenAppealAcceptRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> FrozenAppealAcceptResponse:
    return await accept_frozen_appeal(session, appeal_id, body)


async def start_frozen_appeal(
    session: AsyncSession,
    body: FrozenAppealStartRequest,
) -> FrozenAppealStartResponse:
    user = await _load_user_by_phone_email(session, body.phone, str(body.email))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    if user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account deleted")
    if user.merged_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account merged")
    if not user.is_frozen:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="account is not frozen")

    now = _now()
    token = security.generate_freeze_appeal_token()
    appeal = AccountFreezeAppeal(
        user_id=user.id,
        tracking_token_hash=_tracking_token_hash(token),
        status="started",
        contact_email=str(body.email),
        expires_at=now + timedelta(hours=APPEAL_TTL_HOURS),
        created_at=now,
        updated_at=now,
    )
    proposal = await _latest_non_terminal_proposal(session, user.id)
    if proposal is not None:
        appeal.proposal_id = proposal.id
    session.add(appeal)
    await session.flush()

    flags = await _user_risk_flags(session, user.id)
    summary = _safe_risk_summary_from_user(user, flags)
    proposal_response = (
        await _fetch_proposal_response(session, proposal.id) if proposal is not None else None
    )
    response = FrozenAppealStartResponse(
        appeal_id=appeal.id,
        status="started",
        user_id=user.id,
        tracking_token=token,
        tracking_url=f"{PUBLIC_APPEAL_BASE_URL}?appeal_id={appeal.id}&tracking_token={token}",
        expires_at=appeal.expires_at,
        risk_summary=summary,
        proposal=proposal_response,
        next_action=_next_action_for_proposal(proposal_response),
    )
    await _write_audit(
        session,
        user_id=user.id,
        actor="user",
        action="freeze_appeal.started",
        resource_type="account_freeze_appeal",
        resource_id=appeal.id,
        metadata={
            "proposal_id": str(proposal.id) if proposal is not None else None,
            "expires_at": appeal.expires_at.isoformat(),
        },
    )
    return response


async def _load_appeal_or_404(
    session: AsyncSession, appeal_id: uuid.UUID, tracking_token: str
) -> AccountFreezeAppeal:
    appeal = await _lookup_appeal_by_token(session, appeal_id, tracking_token)
    if appeal is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid tracking token")
    now = _now()
    if appeal.expires_at <= now:
        if appeal.status != "expired":
            appeal.status = "expired"
            appeal.updated_at = now
            await session.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="appeal expired")
    return appeal


async def get_frozen_appeal_status(
    session: AsyncSession,
    appeal_id: uuid.UUID,
    tracking_token: str,
) -> FrozenAppealStatusResponse:
    appeal = await _load_appeal_or_404(session, appeal_id, tracking_token)
    user = await _load_user(session, appeal.user_id)
    appeal.last_viewed_at = _now()
    appeal.updated_at = appeal.last_viewed_at
    proposal = await _fetch_proposal_response(session, appeal.proposal_id)
    summary = _safe_risk_summary_from_user(user, await _user_risk_flags(session, user.id))
    next_action = _next_action_for_proposal(proposal)
    return FrozenAppealStatusResponse(
        appeal_id=appeal.id,
        status=_appeal_status(appeal.status),
        expires_at=appeal.expires_at,
        last_viewed_at=appeal.last_viewed_at,
        risk_summary=summary,
        proposal=proposal,
        next_action=next_action,
    )


async def submit_frozen_appeal_proposal(
    session: AsyncSession,
    appeal_id: uuid.UUID,
    body: FrozenAppealProposalRequest,
) -> FrozenAppealStatusResponse:
    appeal = await _load_appeal_or_404(session, appeal_id, body.tracking_token)
    if appeal.proposal_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="appeal already has proposal"
        )

    user = await _load_user(session, appeal.user_id)
    proposal_request = AccountMergeProposalCreateRequest(
        primary_user_id=user.id,
        duplicate_user_ids=body.duplicate_user_ids,
        evidence=AccountMergeEvidence(
            reason=body.reason,
            contact_email=body.contact_email,
            supporting_note=body.supporting_note,
            team_size=body.team_size,
        ),
    )
    proposal = await account_merge.create_merge_proposal(session, user.id, proposal_request)
    appeal.proposal_id = proposal.id
    appeal.status = "proposal_submitted"
    appeal.contact_email = str(body.contact_email)
    appeal.updated_at = _now()
    await _write_audit(
        session,
        user_id=user.id,
        actor="user",
        action="freeze_appeal.proposal_submitted",
        resource_type="account_freeze_appeal",
        resource_id=appeal.id,
        metadata={
            "proposal_id": str(proposal.id),
            "duplicate_user_ids": [str(v) for v in body.duplicate_user_ids],
        },
    )
    proposal_response = AccountMergeProposalResponse.model_validate(
        account_merge.proposal_to_response(proposal)
    )
    summary = _safe_risk_summary_from_user(user, await _user_risk_flags(session, user.id))
    return FrozenAppealStatusResponse(
        appeal_id=appeal.id,
        status=_appeal_status(appeal.status),
        expires_at=appeal.expires_at,
        last_viewed_at=appeal.last_viewed_at,
        risk_summary=summary,
        proposal=proposal_response,
        next_action=_next_action_for_proposal(proposal_response),
    )


async def accept_frozen_appeal(
    session: AsyncSession,
    appeal_id: uuid.UUID,
    body: FrozenAppealAcceptRequest,
) -> FrozenAppealAcceptResponse:
    appeal = await _load_appeal_or_404(session, appeal_id, body.tracking_token)
    if appeal.proposal_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="appeal has no proposal")
    proposal = (
        await session.execute(
            select(AccountMergeProposal).where(AccountMergeProposal.id == appeal.proposal_id)
        )
    ).scalar_one_or_none()
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="proposal not found")
    if proposal.status not in {"approved", "auto_approved", "accepted"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="proposal not approved")
    already_accepted = appeal.status == "accepted"
    proposal = await account_merge.accept_merge_proposal(session, appeal.user_id, proposal.id)
    appeal.status = "accepted"
    appeal.updated_at = _now()
    if not already_accepted:
        await _write_audit(
            session,
            user_id=appeal.user_id,
            actor="user",
            action="freeze_appeal.accepted",
            resource_type="account_freeze_appeal",
            resource_id=appeal.id,
            metadata={"proposal_id": str(proposal.id)},
        )
    await session.flush()
    proposal_response = AccountMergeProposalResponse.model_validate(
        account_merge.proposal_to_response(proposal)
    )
    return FrozenAppealAcceptResponse(
        appeal_id=appeal.id,
        status=_appeal_status(appeal.status),
        proposal=proposal_response,
        next_action="completed",
    )
