"""Story 1.6 — account deletion lifecycle helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.models import AccountDeletionRequest, APIKey, AuditLog, User, UserOTP

DELETE_GRACE_PERIOD_DAYS = 7


def _now() -> datetime:
    return datetime.now(UTC)


async def get_active_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Return the user only if it exists and is not soft-deleted."""
    stmt = select(User).where(and_(User.id == user_id, User.deleted_at.is_(None)))
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_deletion_request_by_user(
    session: AsyncSession, user_id: uuid.UUID
) -> AccountDeletionRequest | None:
    stmt = select(AccountDeletionRequest).where(AccountDeletionRequest.user_id_snapshot == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_deletion_request_status(
    session: AsyncSession, user_id: uuid.UUID
) -> AccountDeletionRequest | None:
    return await get_deletion_request_by_user(session, user_id)


async def request_account_deletion(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> AccountDeletionRequest:
    user = await get_active_user(session, user_id)
    now = _now()

    if user is None:
        existing = await get_deletion_request_by_user(session, user_id)
        if existing is None:
            raise LookupError("user not found")
        return existing

    existing = await get_deletion_request_by_user(session, user_id)
    if existing is not None:
        return existing

    user.deleted_at = now
    due_at = now + timedelta(days=DELETE_GRACE_PERIOD_DAYS)
    request = AccountDeletionRequest(
        user_id_snapshot=user.id,
        user_id=user.id,
        status="scheduled",
        requested_at=now,
        hard_delete_at=due_at,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )
    session.add(request)

    await session.execute(
        update(APIKey).where(APIKey.user_id == user.id, APIKey.revoked_at.is_(None)).values(
            revoked_at=now
        )
    )
    session.add(
        AuditLog(
            user_id=user.id,
            actor="user",
            action="account_deletion.requested",
            resource_type="user",
            resource_id=user.id,
            audit_metadata={
                "requested_at": now.isoformat(),
                "hard_delete_at": due_at.isoformat(),
            },
        )
    )
    await session.flush()
    return request


async def complete_due_deletion_requests(
    session: AsyncSession, *, now: datetime | None = None
) -> list[uuid.UUID]:
    """Hard-delete due account deletion requests and keep audit trail / request rows."""
    current_time = now or _now()
    result = await session.execute(
        select(AccountDeletionRequest).where(
            AccountDeletionRequest.status == "scheduled",
            AccountDeletionRequest.hard_delete_at <= current_time,
        )
    )
    requests = result.scalars().all()
    completed: list[uuid.UUID] = []

    for request in requests:
        user_id = request.user_id_snapshot
        request.user_id = None
        request.status = "completed"
        request.completed_at = current_time
        request.updated_at = current_time

        await session.execute(delete(APIKey).where(APIKey.user_id == user_id))
        await session.execute(delete(UserOTP).where(UserOTP.user_id == user_id))
        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                phone=f"deleted-{user_id.hex[:12]}",
                email=f"deleted-{user_id.hex[:12]}@invalid.local",
                edu_tier=False,
                age_verified=False,
                risk_score=0,
                is_frozen=False,
                deleted_at=current_time,
            )
        )
        session.add(
            AuditLog(
                user_id=None,
                actor="system",
                action="account_deletion.completed",
                resource_type="user",
                resource_id=user_id,
                audit_metadata={
                    "user_id_snapshot": str(user_id),
                    "hard_delete_at": request.hard_delete_at.isoformat(),
                    "completed_at": current_time.isoformat(),
                },
            )
        )
        completed.append(user_id)

    await session.flush()
    return completed
