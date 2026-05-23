"""Story 1.5 — FR A5 admin surface for /v1/admin/* (manual risk-flag + unfreeze + list).

Authentication: shared-secret `X-Admin-Secret` header (constant-time compare against
`settings.admin_secret`). Empty env → endpoints 403 (fail-closed). v1 only; admin
RBAC + admin-user table is M2+ (see DR-1.5 in story 1.5 risks).

All admin actions write to `audit_logs` for forensic trail.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service import account_merge, risk
from auth_service.config import settings
from auth_service.db import get_session
from auth_service.models import AuditLog, RiskFlag, RiskRule, User
from auth_service.schemas import AccountMergeAdminReviewRequest, AccountMergeProposalResponse

_log = structlog.get_logger("auth_service.admin")

admin_router = APIRouter(prefix="/v1/admin", tags=["admin"])


def require_admin_secret(x_admin_secret: str | None = Header(default=None)) -> None:
    """Gate all admin endpoints. Empty config → 403; bad/missing header → 401."""
    if not settings.admin_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin endpoints disabled (ADMIN_SECRET not configured)",
        )
    if x_admin_secret is None or not secrets.compare_digest(x_admin_secret, settings.admin_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid X-Admin-Secret",
        )


# ===== Schemas =====


class AdminFlagRequest(BaseModel):
    user_id: uuid.UUID
    rule_code: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdminFlagResponse(BaseModel):
    flag_id: uuid.UUID
    user_frozen: bool
    distinct_enabled_triggers: int


class AdminUnfreezeRequest(BaseModel):
    reason: str | None = None


class AdminUnfreezeResponse(BaseModel):
    user_id: uuid.UUID
    is_frozen: bool


class RiskFlagItem(BaseModel):
    id: uuid.UUID
    rule_code: str
    source: str
    metadata: dict[str, Any]
    created_at: datetime


class RiskRuleItem(BaseModel):
    code: str
    label_zh: str
    description: str
    enabled: bool
    created_at: datetime


# ===== Endpoints =====


@admin_router.post(
    "/risk-flags",
    response_model=AdminFlagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a manual risk flag against a user (FR A5)",
    description=(
        "Admin records a risk flag for a user against a known rule_code. Counts toward the "
        "≥2-distinct-enabled-rules freeze threshold. Flags for disabled rules are recorded "
        "(audit trail) but do NOT contribute to freeze."
    ),
)
async def admin_add_risk_flag(
    body: AdminFlagRequest,
    _auth: None = Depends(require_admin_secret),
    session: AsyncSession = Depends(get_session),
) -> AdminFlagResponse:
    # Validate rule exists
    rule = (
        await session.execute(select(RiskRule).where(RiskRule.code == body.rule_code))
    ).scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown rule_code: {body.rule_code}",
        )

    # Validate user exists
    user = (await session.execute(select(User).where(User.id == body.user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"user not found: {body.user_id}",
        )

    new_flag = RiskFlag(
        user_id=body.user_id,
        rule_code=body.rule_code,
        source="admin",
        flag_metadata=body.metadata,
    )
    session.add(new_flag)
    session.add(
        AuditLog(
            user_id=body.user_id,
            actor="admin",
            action="risk.flag.add",
            resource_type="user",
            resource_id=body.user_id,
            audit_metadata={"rule_code": body.rule_code, "source": "admin"},
        )
    )
    await session.flush()

    # Evaluate freeze threshold using the same sink as auto-detection.
    # We pass an empty new_flags list — the flag is already persisted; the
    # evaluator's count query sees it and decides whether to freeze.
    distinct = await risk._distinct_enabled_triggers(session, body.user_id)
    user_frozen_now = False
    if len(distinct) >= risk.FREEZE_THRESHOLD:
        # Use the same path as evaluate to maintain a single freeze code-path.
        # Pass empty new_flags so it doesn't double-insert; the existing flag is in distinct already.
        user_frozen_now = await risk.apply_flags_and_maybe_freeze(session, body.user_id, [])
        # apply_flags returns False if already frozen — fold that into the "is frozen now" view.
        if not user_frozen_now:
            current = (
                await session.execute(select(User.is_frozen).where(User.id == body.user_id))
            ).scalar_one()
            user_frozen_now = bool(current)

    await session.commit()
    await session.refresh(new_flag)
    _log.info(
        "admin.risk.flag.added",
        user_id=str(body.user_id),
        rule_code=body.rule_code,
        froze=user_frozen_now,
    )
    return AdminFlagResponse(
        flag_id=new_flag.id,
        user_frozen=user_frozen_now,
        distinct_enabled_triggers=len(distinct),
    )


@admin_router.post(
    "/users/{user_id}/unfreeze",
    response_model=AdminUnfreezeResponse,
    summary="Clear is_frozen for a user (FR A5 appeal path)",
    description=(
        "Admin lifts a freeze. Does NOT delete `risk_flags` rows — audit trail preserved. "
        "Idempotent: unfreezing an already-unfrozen user returns 200 cleanly."
    ),
)
async def admin_unfreeze_user(
    user_id: uuid.UUID,
    body: AdminUnfreezeRequest,
    _auth: None = Depends(require_admin_secret),
    session: AsyncSession = Depends(get_session),
) -> AdminUnfreezeResponse:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"user not found: {user_id}",
        )

    await session.execute(update(User).where(User.id == user_id).values(is_frozen=False))
    session.add(
        AuditLog(
            user_id=user_id,
            actor="admin",
            action="user.unfreeze",
            resource_type="user",
            resource_id=user_id,
            audit_metadata={"reason": body.reason} if body.reason else {},
        )
    )
    await session.commit()
    _log.info("admin.user.unfreeze", user_id=str(user_id), reason=body.reason)
    return AdminUnfreezeResponse(user_id=user_id, is_frozen=False)


@admin_router.get(
    "/risk-flags",
    response_model=list[RiskFlagItem],
    summary="List risk flags for a user (FR A5 audit)",
)
async def admin_list_risk_flags(
    user_id: uuid.UUID,
    _auth: None = Depends(require_admin_secret),
    session: AsyncSession = Depends(get_session),
) -> list[RiskFlagItem]:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"user not found: {user_id}",
        )

    result = await session.execute(
        select(RiskFlag).where(RiskFlag.user_id == user_id).order_by(RiskFlag.created_at.desc())
    )
    flags = result.scalars().all()
    return [
        RiskFlagItem(
            id=f.id,
            rule_code=f.rule_code,
            source=f.source,
            metadata=f.flag_metadata,
            created_at=f.created_at or datetime.now(UTC),
        )
        for f in flags
    ]


@admin_router.get(
    "/risk-rules",
    response_model=list[RiskRuleItem],
    summary="List all risk rules + enabled state (FR A5 ops convenience)",
)
async def admin_list_risk_rules(
    _auth: None = Depends(require_admin_secret),
    session: AsyncSession = Depends(get_session),
) -> list[RiskRuleItem]:
    result = await session.execute(select(RiskRule).order_by(RiskRule.code.asc()))
    rules = result.scalars().all()
    return [
        RiskRuleItem(
            code=r.code,
            label_zh=r.label_zh,
            description=r.description,
            enabled=r.enabled,
            created_at=r.created_at or datetime.now(UTC),
        )
        for r in rules
    ]


@admin_router.get(
    "/account-merge-proposals",
    response_model=list[AccountMergeProposalResponse],
    summary="List account-merge proposals awaiting review (FR A7)",
)
async def admin_list_account_merge_proposals(
    status_filter: str | None = None,
    status: str | None = None,
    _auth: None = Depends(require_admin_secret),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    # FastAPI reserves no special meaning for the query name "status"; keep
    # status_filter as a backward-compatible alias if internal callers prefer it.
    selected_status = status if status is not None else status_filter
    proposals = await account_merge.list_admin_merge_proposals(session, selected_status)
    return [account_merge.proposal_to_response(p) for p in proposals]


@admin_router.post(
    "/account-merge-proposals/{proposal_id}/review",
    response_model=AccountMergeProposalResponse,
    summary="Approve or reject an account-merge proposal (FR A7)",
)
async def admin_review_account_merge_proposal(
    proposal_id: uuid.UUID,
    body: AccountMergeAdminReviewRequest,
    x_admin_secret: str | None = Header(default=None),
    _auth: None = Depends(require_admin_secret),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    proposal = await account_merge.review_merge_proposal(
        session,
        proposal_id,
        decision=body.decision,
        reason=body.reason,
        reviewed_by="admin-secret",
    )
    await session.commit()
    await session.refresh(proposal)
    _log.info(
        "admin.account_merge.reviewed",
        proposal_id=str(proposal_id),
        decision=body.decision,
        authenticated=bool(x_admin_secret),
    )
    return account_merge.proposal_to_response(proposal)
