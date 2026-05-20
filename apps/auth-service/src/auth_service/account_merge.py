"""Story 1.7 — account merge proposal lifecycle helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.models import AccountMergeProposal, APIKey, AuditLog, RiskFlag, User
from auth_service.schemas import AccountMergeProposalCreateRequest

AUTO_APPROVE_THRESHOLD = Decimal("0.70")


def _now() -> datetime:
    return datetime.now(UTC)


def _domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower()


def _next_action(proposal: AccountMergeProposal) -> str:
    if proposal.status in {"approved", "auto_approved"}:
        return "accept_merge"
    if proposal.status == "pending_review":
        return "await_review"
    if proposal.status == "accepted":
        return "completed"
    if proposal.status == "rejected":
        return "contact_support"
    return "none"


def proposal_to_response(proposal: AccountMergeProposal) -> dict[str, Any]:
    return {
        "id": proposal.id,
        "requester_user_id": proposal.requester_user_id,
        "primary_user_id": proposal.primary_user_id,
        "duplicate_user_ids": proposal.duplicate_user_ids,
        "evidence": proposal.evidence,
        "status": proposal.status,
        "review_mode": proposal.review_mode,
        "auto_score": float(proposal.auto_score) if proposal.auto_score is not None else None,
        "review_due_at": proposal.review_due_at,
        "reviewed_at": proposal.reviewed_at,
        "reviewed_by": proposal.reviewed_by,
        "decision_reason": proposal.decision_reason,
        "accepted_at": proposal.accepted_at,
        "created_at": proposal.created_at or _now(),
        "updated_at": proposal.updated_at or _now(),
        "next_action": _next_action(proposal),
    }


async def _load_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return user


def _is_tombstoned(user: User) -> bool:
    return bool(user.deleted_at is not None or user.email.endswith("@invalid.local"))


async def _has_risk_flag(session: AsyncSession, user_id: uuid.UUID) -> bool:
    flag = (
        await session.execute(select(RiskFlag.id).where(RiskFlag.user_id == user_id).limit(1))
    ).scalar_one_or_none()
    return flag is not None


async def _metadata_links_duplicate(
    session: AsyncSession,
    requester_user_id: uuid.UUID,
    duplicate_user_id: uuid.UUID,
) -> bool:
    result = await session.execute(
        select(RiskFlag.flag_metadata).where(RiskFlag.user_id == requester_user_id)
    )
    needle = str(duplicate_user_id)
    for metadata in result.scalars().all():
        if needle in str(metadata):
            return True
    return False


async def _has_merge_signal(session: AsyncSession, requester: User, duplicate: User) -> bool:
    if _domain(requester.email) == _domain(duplicate.email):
        return True
    if await _has_risk_flag(session, requester.id) and await _has_risk_flag(session, duplicate.id):
        return True
    return await _metadata_links_duplicate(session, requester.id, duplicate.id)


async def _calculate_auto_score(
    session: AsyncSession,
    requester: User,
    duplicates: list[User],
    reason: str,
) -> Decimal:
    score = Decimal("0.50")
    if duplicates and all(_domain(requester.email) == _domain(u.email) for u in duplicates):
        score += Decimal("0.20")
    if duplicates and await _has_risk_flag(session, requester.id):
        duplicate_flags = [await _has_risk_flag(session, u.id) for u in duplicates]
        if all(duplicate_flags):
            score += Decimal("0.20")
    if len(reason.strip()) >= 8:
        score += Decimal("0.10")
    return min(score, Decimal("1.00"))


async def create_merge_proposal(
    session: AsyncSession,
    requester_user_id: uuid.UUID,
    body: AccountMergeProposalCreateRequest,
) -> AccountMergeProposal:
    now = _now()
    requester = await _load_user(session, requester_user_id)
    if _is_tombstoned(requester):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account deleted")
    if requester.merged_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account merged")
    if not requester.is_frozen:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="account is not frozen")
    if body.primary_user_id != requester_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="primary_user_id must match authenticated user",
        )

    duplicates: list[User] = []
    for duplicate_id in body.duplicate_user_ids:
        duplicate = await _load_user(session, duplicate_id)
        if _is_tombstoned(duplicate):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="duplicate account is deleted",
            )
        if duplicate.merged_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="duplicate account already merged",
            )
        if not await _has_merge_signal(session, requester, duplicate):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="duplicate account has no allowed merge signal",
            )
        duplicates.append(duplicate)

    evidence = body.evidence.model_dump(mode="json")
    team_size = body.evidence.team_size or 2
    review_mode = "human" if team_size >= 3 else "auto"
    review_due_at = now + timedelta(hours=48 if review_mode == "human" else 24)
    auto_score: Decimal | None = None
    proposal_status = "pending_review"

    if review_mode == "auto":
        auto_score = await _calculate_auto_score(session, requester, duplicates, body.evidence.reason)
        if auto_score >= AUTO_APPROVE_THRESHOLD:
            proposal_status = "auto_approved"

    proposal = AccountMergeProposal(
        requester_user_id=requester_user_id,
        primary_user_id=body.primary_user_id,
        duplicate_user_ids=body.duplicate_user_ids,
        evidence=evidence,
        status=proposal_status,
        review_mode=review_mode,
        auto_score=auto_score,
        review_due_at=review_due_at,
        created_at=now,
        updated_at=now,
    )
    session.add(proposal)
    await session.flush()

    session.add(
        AuditLog(
            user_id=requester_user_id,
            actor="user",
            action="account_merge.proposed",
            resource_type="account_merge_proposal",
            resource_id=proposal.id,
            audit_metadata={
                "primary_user_id": str(body.primary_user_id),
                "duplicate_user_ids": [str(v) for v in body.duplicate_user_ids],
                "review_mode": review_mode,
            },
        )
    )
    if proposal_status == "auto_approved":
        session.add(
            AuditLog(
                user_id=requester_user_id,
                actor="system",
                action="account_merge.auto_approved",
                resource_type="account_merge_proposal",
                resource_id=proposal.id,
                audit_metadata={"auto_score": str(auto_score)},
            )
        )
    await session.flush()
    return proposal


async def list_user_merge_proposals(
    session: AsyncSession,
    requester_user_id: uuid.UUID,
) -> list[AccountMergeProposal]:
    result = await session.execute(
        select(AccountMergeProposal)
        .where(AccountMergeProposal.requester_user_id == requester_user_id)
        .order_by(AccountMergeProposal.created_at.desc())
    )
    return list(result.scalars().all())


async def accept_merge_proposal(
    session: AsyncSession,
    requester_user_id: uuid.UUID,
    proposal_id: uuid.UUID,
) -> AccountMergeProposal:
    proposal = (
        await session.execute(
            select(AccountMergeProposal).where(
                AccountMergeProposal.id == proposal_id,
                AccountMergeProposal.requester_user_id == requester_user_id,
            )
        )
    ).scalar_one_or_none()
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="proposal not found")
    if proposal.status == "accepted":
        return proposal
    if proposal.status not in {"approved", "auto_approved"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="proposal not approved")

    now = _now()
    primary = await _load_user(session, proposal.primary_user_id)
    if _is_tombstoned(primary) or primary.merged_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="primary account deleted")

    duplicate_users: list[User] = []
    for duplicate_id in proposal.duplicate_user_ids:
        duplicate = await _load_user(session, duplicate_id)
        if _is_tombstoned(duplicate) or duplicate.merged_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="duplicate account already retired",
            )
        duplicate_users.append(duplicate)

    await session.execute(
        update(User).where(User.id == proposal.primary_user_id).values(is_frozen=False)
    )
    await session.execute(
        update(User)
        .where(User.id.in_([u.id for u in duplicate_users]))
        .values(
            is_frozen=True,
            merged_into_user_id=proposal.primary_user_id,
            merged_at=now,
        )
    )
    await session.execute(
        update(APIKey)
        .where(APIKey.user_id.in_([u.id for u in duplicate_users]), APIKey.revoked_at.is_(None))
        .values(revoked_at=now)
    )

    proposal.status = "accepted"
    proposal.accepted_at = now
    proposal.updated_at = now
    session.add(
        AuditLog(
            user_id=requester_user_id,
            actor="user",
            action="account_merge.accepted",
            resource_type="account_merge_proposal",
            resource_id=proposal.id,
            audit_metadata={
                "primary_user_id": str(proposal.primary_user_id),
                "duplicate_user_ids": [str(v) for v in proposal.duplicate_user_ids],
                "starter_upgrade_recommended": True,
            },
        )
    )
    await session.flush()
    return proposal


async def list_admin_merge_proposals(
    session: AsyncSession,
    proposal_status: str | None = None,
) -> list[AccountMergeProposal]:
    stmt = select(AccountMergeProposal).order_by(
        AccountMergeProposal.review_due_at.asc(), AccountMergeProposal.created_at.asc()
    )
    if proposal_status:
        stmt = stmt.where(AccountMergeProposal.status == proposal_status)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def review_merge_proposal(
    session: AsyncSession,
    proposal_id: uuid.UUID,
    *,
    decision: str,
    reason: str,
    reviewed_by: str,
) -> AccountMergeProposal:
    proposal = (
        await session.execute(select(AccountMergeProposal).where(AccountMergeProposal.id == proposal_id))
    ).scalar_one_or_none()
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="proposal not found")
    if proposal.status != "pending_review":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="proposal is already terminal or approved",
        )

    now = _now()
    proposal.status = "approved" if decision == "approve" else "rejected"
    proposal.reviewed_at = now
    proposal.reviewed_by = reviewed_by
    proposal.decision_reason = reason
    proposal.updated_at = now
    session.add(
        AuditLog(
            user_id=proposal.requester_user_id,
            actor="admin",
            action="account_merge.reviewed",
            resource_type="account_merge_proposal",
            resource_id=proposal.id,
            audit_metadata={
                "decision": decision,
                "reason": reason,
                "reviewed_by": reviewed_by,
            },
        )
    )
    await session.flush()
    return proposal
