"""Story 1.12 — J7 risk freeze appeal helpers."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service import risk
from auth_service.models import AuditLog, RiskAppeal, RiskFlag, RiskRule, User
from auth_service.schemas import RiskEvidenceSummary, RiskMergeOffer

TOKEN_TTL_DAYS = 7
MANUAL_REVIEW_HOURS = 48

ACTIVE_STATUSES = ("pending", "merge_offered")


def now_utc() -> datetime:
    return datetime.now(UTC)


def tracking_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_tracking_token() -> tuple[str, str, datetime]:
    token = secrets.token_urlsafe(32)
    return token, tracking_token_hash(token), now_utc() + timedelta(days=TOKEN_TTL_DAYS)


def tracking_url(token: str) -> str:
    return f"/auth/appeal?token={token}"


def sla_due_at(appeal: RiskAppeal) -> datetime | None:
    if appeal.review_mode != "manual_48h":
        return None
    return appeal.created_at + timedelta(hours=MANUAL_REVIEW_HOURS)


def merge_offer_payload() -> dict[str, str]:
    return {
        "offer_type": "keep_one_account",
        "title": "保留 1 个账号并恢复访问",
        "description": "接受后当前冻结账号会恢复访问；完整跨账号数据合并将在后续账号合并工具中处理。",
        "next_action": "accept_merge_to_resume",
    }


def parse_merge_offer(value: dict[str, Any] | None) -> RiskMergeOffer | None:
    if not value:
        return None
    try:
        return RiskMergeOffer.model_validate(value)
    except ValueError:
        return None


async def rotate_tracking_token(appeal: RiskAppeal) -> str:
    token, token_hash, expires_at = new_tracking_token()
    appeal.tracking_token_hash = token_hash
    appeal.tracking_token_expires_at = expires_at
    appeal.updated_at = now_utc()
    return token


async def get_active_appeal(session: AsyncSession, user_id: uuid.UUID) -> RiskAppeal | None:
    result = await session.execute(
        select(RiskAppeal)
        .where(and_(RiskAppeal.user_id == user_id, RiskAppeal.status.in_(ACTIVE_STATUSES)))
        .order_by(RiskAppeal.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_appeal_by_token(session: AsyncSession, token: str) -> RiskAppeal | None:
    token_hash = tracking_token_hash(token)
    result = await session.execute(
        select(RiskAppeal).where(RiskAppeal.tracking_token_hash == token_hash)
    )
    appeal = result.scalar_one_or_none()
    if appeal is None:
        return None
    if appeal.tracking_token_expires_at <= now_utc():
        return None
    return appeal


async def _enabled_trigger_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    return len(await risk._distinct_enabled_triggers(session, user_id))


def _evidence_is_meaningful(reason: str, evidence: dict[str, Any]) -> bool:
    if len(reason.strip()) < 20:
        return False
    return any(bool(str(value).strip()) for value in evidence.values())


async def should_auto_approve(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    reason: str,
    evidence: dict[str, Any],
) -> bool:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    enabled_trigger_count = await _enabled_trigger_count(session, user_id)
    return (
        enabled_trigger_count < risk.FREEZE_THRESHOLD
        and float(user.risk_score) < 0.90
        and _evidence_is_meaningful(reason, evidence)
    )


async def unfreeze_user_with_audit(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    actor: str,
    reason: str | None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Clear `users.is_frozen` and write the Story 1.5 unfreeze audit event.

    Returns True when the user transitioned from frozen to unfrozen.
    """
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise LookupError(f"user not found: {user_id}")
    was_frozen = bool(user.is_frozen)
    await session.execute(update(User).where(User.id == user_id).values(is_frozen=False))
    audit_metadata = dict(metadata or {})
    if reason:
        audit_metadata["reason"] = reason
    session.add(
        AuditLog(
            user_id=user_id,
            actor=actor,
            action="user.unfreeze",
            resource_type="user",
            resource_id=user_id,
            audit_metadata=audit_metadata,
        )
    )
    await session.flush()
    return was_frozen


async def evidence_summary(session: AsyncSession, user_id: uuid.UUID) -> list[RiskEvidenceSummary]:
    result = await session.execute(
        select(RiskFlag, RiskRule)
        .join(RiskRule, RiskRule.code == RiskFlag.rule_code)
        .where(RiskFlag.user_id == user_id)
        .order_by(RiskFlag.created_at.desc())
        .limit(10)
    )
    items: list[RiskEvidenceSummary] = []
    for flag, rule in result.all():
        items.append(
            RiskEvidenceSummary(
                rule_code=flag.rule_code,
                label_zh=rule.label_zh,
                source=flag.source,
                created_at=flag.created_at,
                summary=_safe_metadata_summary(flag.flag_metadata),
            )
        )
    return items


def _safe_metadata_summary(metadata: dict[str, Any]) -> str | None:
    for key in ("reason", "category", "signup_ip", "score"):
        value = metadata.get(key)
        if isinstance(value, str) and value:
            return f"{key}: {value}"
        if isinstance(value, int | float):
            return f"{key}: {value}"
    return None


async def create_appeal(
    session: AsyncSession,
    *,
    user: User,
    reason: str,
    evidence: dict[str, str],
    team_size: int,
) -> tuple[RiskAppeal, str]:
    active = await get_active_appeal(session, user.id)
    if active is not None:
        token = await rotate_tracking_token(active)
        await session.flush()
        return active, token

    token, token_hash, expires_at = new_tracking_token()
    review_mode = "manual_48h" if team_size >= 3 else "auto_score"
    appeal = RiskAppeal(
        user_id=user.id,
        status="pending",
        reason=reason,
        evidence=evidence,
        team_size=team_size,
        review_mode=review_mode,
        decision=None,
        decision_reason=None,
        tracking_token_hash=token_hash,
        tracking_token_expires_at=expires_at,
        merge_offer={},
        created_at=now_utc(),
        updated_at=now_utc(),
        decided_at=None,
    )
    session.add(appeal)
    await session.flush()
    session.add(
        AuditLog(
            user_id=user.id,
            actor="user",
            action="risk.appeal.submitted",
            resource_type="risk_appeal",
            resource_id=appeal.id,
            audit_metadata={
                "review_mode": review_mode,
                "team_size": team_size,
            },
        )
    )

    if review_mode == "auto_score":
        if await should_auto_approve(
            session,
            user_id=user.id,
            reason=reason,
            evidence=evidence,
        ):
            await approve_appeal(
                session,
                appeal=appeal,
                actor="system",
                reason="auto_score approved appeal",
            )
        else:
            await offer_merge(
                session,
                appeal=appeal,
                actor="system",
                reason="auto_score maintained freeze",
            )

    await session.flush()
    return appeal, token


async def approve_appeal(
    session: AsyncSession,
    *,
    appeal: RiskAppeal,
    actor: str,
    reason: str,
) -> None:
    current = now_utc()
    appeal.status = "approved"
    appeal.decision = "approved"
    appeal.decision_reason = reason
    appeal.decided_at = current
    appeal.updated_at = current
    await unfreeze_user_with_audit(
        session,
        user_id=appeal.user_id,
        actor=actor,
        reason=reason,
        metadata={"appeal_id": str(appeal.id), "event_kind": "risk_appeal_approved"},
    )
    session.add(
        AuditLog(
            user_id=appeal.user_id,
            actor=actor,
            action="risk.appeal.approved",
            resource_type="risk_appeal",
            resource_id=appeal.id,
            audit_metadata={"reason": reason},
        )
    )
    await session.flush()


async def offer_merge(
    session: AsyncSession,
    *,
    appeal: RiskAppeal,
    actor: str,
    reason: str,
) -> None:
    current = now_utc()
    appeal.status = "merge_offered"
    appeal.decision = "maintained"
    appeal.decision_reason = reason
    appeal.merge_offer = merge_offer_payload()
    appeal.decided_at = current
    appeal.updated_at = current
    session.add(
        AuditLog(
            user_id=appeal.user_id,
            actor=actor,
            action="risk.appeal.merge_offered",
            resource_type="risk_appeal",
            resource_id=appeal.id,
            audit_metadata={"reason": reason},
        )
    )
    await session.flush()


async def reject_appeal(
    session: AsyncSession,
    *,
    appeal: RiskAppeal,
    actor: str,
    reason: str,
) -> None:
    current = now_utc()
    appeal.status = "rejected"
    appeal.decision = "rejected"
    appeal.decision_reason = reason
    appeal.decided_at = current
    appeal.updated_at = current
    session.add(
        AuditLog(
            user_id=appeal.user_id,
            actor=actor,
            action="risk.appeal.rejected",
            resource_type="risk_appeal",
            resource_id=appeal.id,
            audit_metadata={"reason": reason},
        )
    )
    await session.flush()


async def accept_merge_offer(session: AsyncSession, appeal: RiskAppeal) -> None:
    if appeal.status == "merge_accepted":
        return
    if appeal.status != "merge_offered":
        raise ValueError("appeal does not have an active merge offer")
    current = now_utc()
    appeal.status = "merge_accepted"
    appeal.decision = "merge_accepted"
    appeal.decision_reason = "user accepted minimal merge offer"
    appeal.decided_at = current
    appeal.updated_at = current
    await unfreeze_user_with_audit(
        session,
        user_id=appeal.user_id,
        actor="user",
        reason="merge offer accepted",
        metadata={"appeal_id": str(appeal.id), "event_kind": "risk_appeal_merge_accepted"},
    )
    session.add(
        AuditLog(
            user_id=appeal.user_id,
            actor="user",
            action="risk.appeal.merge_accepted",
            resource_type="risk_appeal",
            resource_id=appeal.id,
            audit_metadata={"next_action_url": "/auth/login"},
        )
    )
    await session.flush()


async def ensure_risk_appeals_table(session: AsyncSession) -> None:
    """Test/local fallback for DBs that have not yet applied migration 09."""
    await session.execute(text("SELECT 1 FROM risk_appeals LIMIT 1"))
