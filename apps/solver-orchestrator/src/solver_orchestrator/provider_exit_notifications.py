"""Provider exit >=30d notification fan-out contract (Story 6.C.2)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from solver_orchestrator.models import (
    OutboxEvent,
    ProviderExitNotificationRequest,
    ProviderExitPlan,
    ProviderExitStatusAnnouncement,
)

PROVIDER_EXIT_NOTICE_DAYS = 30
PROVIDER_EXIT_NOTICE_DELTA = timedelta(days=PROVIDER_EXIT_NOTICE_DAYS)
PROVIDER_EXIT_CHANNELS: tuple[str, str] = ("email", "in_app")
PROVIDER_EXIT_NOTIFICATION_EVENT = "provider.exit.notification_requested"
PROVIDER_EXIT_STATUS_EVENT = "provider.exit.status_announcement_requested"
PROVIDER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.:-]{1,94}$")


@dataclass(frozen=True)
class ProviderExitPlanInput:
    provider_id: str
    effective_at: datetime
    reason: str
    replacement_provider_id: str | None = None
    public_message: str | None = None
    severity: Literal["minor", "major"] = "major"
    announcement_status: Literal["identified", "monitoring"] = "identified"
    now: datetime | None = None


@dataclass(frozen=True)
class ProviderExitPlanResult:
    exit_plan_id: uuid.UUID
    provider_id: str
    effective_at: datetime
    affected_users: int
    affected_vouchers: int
    notification_requests_created: int
    status_url: str
    announcement_id: str


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def validate_notice_window(*, effective_at: datetime, now: datetime | None = None) -> None:
    now_utc = as_utc(now or utc_now())
    effective_utc = as_utc(effective_at)
    if effective_utc < now_utc + PROVIDER_EXIT_NOTICE_DELTA:
        raise ValueError("effective_at must be at least 30 days after server UTC now")


def status_url_for_provider_exit(provider_id: str, effective_at: datetime) -> str:
    return f"/status#provider-exit-{provider_id}-{as_utc(effective_at):%Y%m%d}"


def announcement_id_for_provider_exit(provider_id: str, effective_at: datetime) -> str:
    return f"provider-exit-{provider_id}-{as_utc(effective_at):%Y%m%d}"


def _public_summary(
    *,
    provider_id: str,
    effective_at: datetime,
    reason: str,
    replacement_provider_id: str | None,
    public_message: str | None,
) -> str:
    if public_message:
        return public_message
    replacement = (
        f" Replacement provider: {replacement_provider_id}."
        if replacement_provider_id is not None
        else ""
    )
    return (
        f"Provider {provider_id} is scheduled to exit on "
        f"{as_utc(effective_at).isoformat()}. Reason: {reason}.{replacement}"
    )[:500]


def _notification_payload(
    *,
    request_id: uuid.UUID,
    exit_plan: ProviderExitPlan,
    status_url: str,
    user_id: uuid.UUID,
    affected_voucher_count: int,
) -> dict[str, object]:
    return {
        "exit_plan_id": str(exit_plan.id),
        "provider_id": exit_plan.provider_id,
        "effective_at": as_utc(exit_plan.effective_at).isoformat(),
        "status_url": status_url,
        "channels": list(PROVIDER_EXIT_CHANNELS),
        "user_id": str(user_id),
        "notification_request_id": str(request_id),
        "affected_voucher_count": affected_voucher_count,
        "reason": exit_plan.reason,
        "public_message": exit_plan.public_message,
    }


def _announcement_payload(
    *,
    announcement: ProviderExitStatusAnnouncement,
    exit_plan: ProviderExitPlan,
) -> dict[str, object]:
    return {
        "announcement_id": announcement.announcement_id,
        "exit_plan_id": str(exit_plan.id),
        "provider_id": exit_plan.provider_id,
        "effective_at": as_utc(exit_plan.effective_at).isoformat(),
        "status_url": announcement.status_url,
        "title": announcement.title,
        "summary": announcement.summary,
        "severity": announcement.severity,
        "status": announcement.announcement_status,
        "affected_user_count": announcement.affected_user_count,
        "affected_voucher_count": announcement.affected_voucher_count,
    }


async def _affected_voucher_rows(
    session: AsyncSession,
    *,
    provider_id: str,
    as_of: datetime,
) -> list[Mapping[str, object]]:
    result = await session.execute(
        text(
            """
            SELECT rv.user_id, COUNT(*)::int AS affected_voucher_count
              FROM reproduction_vouchers rv
              JOIN users u ON u.id = rv.user_id
             WHERE rv.status = 'issued'
               AND rv.locked_model_version->>'provider_id' = :provider_id
               AND rv.created_at + INTERVAL '5 years' > :as_of
               AND u.deleted_at IS NULL
               AND u.merged_at IS NULL
               AND u.is_frozen = FALSE
             GROUP BY rv.user_id
             ORDER BY rv.user_id
            """
        ),
        {"provider_id": provider_id, "as_of": as_utc(as_of)},
    )
    return [dict(row) for row in result.mappings().all()]


async def create_provider_exit_plan(
    session: AsyncSession,
    payload: ProviderExitPlanInput,
) -> ProviderExitPlanResult:
    provider_id = payload.provider_id
    effective_at = as_utc(payload.effective_at)
    now = as_utc(payload.now or utc_now())
    validate_notice_window(effective_at=effective_at, now=now)

    insert_plan = (
        pg_insert(ProviderExitPlan)
        .values(
            provider_id=provider_id,
            effective_at=effective_at,
            status="scheduled",
            reason=payload.reason,
            replacement_provider_id=payload.replacement_provider_id,
            public_message=payload.public_message,
            created_by="admin-secret",
            updated_at=now,
        )
        .on_conflict_do_nothing(
            index_elements=["provider_id", "effective_at"],
        )
        .returning(ProviderExitPlan.id)
    )
    inserted_plan_id = (await session.execute(insert_plan)).scalar_one_or_none()
    if inserted_plan_id is None:
        exit_plan = (
            await session.execute(
                select(ProviderExitPlan).where(
                    ProviderExitPlan.provider_id == provider_id,
                    ProviderExitPlan.effective_at == effective_at,
                )
            )
        ).scalar_one()
    else:
        inserted_exit_plan = await session.get(ProviderExitPlan, inserted_plan_id)
        if inserted_exit_plan is None:
            raise RuntimeError("provider exit plan insert did not return a visible row")
        exit_plan = inserted_exit_plan

    status_url = status_url_for_provider_exit(provider_id, effective_at)
    announcement_id = announcement_id_for_provider_exit(provider_id, effective_at)
    affected_rows = await _affected_voucher_rows(session, provider_id=provider_id, as_of=now)
    affected_users = len(affected_rows)
    affected_vouchers = sum(cast(int, row["affected_voucher_count"]) for row in affected_rows)

    created_requests = 0
    for row in affected_rows:
        user_id = row["user_id"]
        if not isinstance(user_id, uuid.UUID):
            user_id = uuid.UUID(str(user_id))
        affected_voucher_count = cast(int, row["affected_voucher_count"])
        insert_request = (
            pg_insert(ProviderExitNotificationRequest)
            .values(
                exit_plan_id=exit_plan.id,
                user_id=user_id,
                provider_id=provider_id,
                status_url=status_url,
                affected_voucher_count=affected_voucher_count,
                channels=list(PROVIDER_EXIT_CHANNELS),
                email_requested=True,
                in_app_requested=True,
                webhook_requested=False,
                updated_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=["exit_plan_id", "user_id"],
            )
            .returning(ProviderExitNotificationRequest.id)
        )
        request_id = (await session.execute(insert_request)).scalar_one_or_none()
        if request_id is None:
            continue
        created_requests += 1
        session.add(
            OutboxEvent(
                aggregate_type="provider_exit_notification_request",
                aggregate_id=request_id,
                event_type=PROVIDER_EXIT_NOTIFICATION_EVENT,
                event_version=1,
                payload=_notification_payload(
                    request_id=request_id,
                    exit_plan=exit_plan,
                    status_url=status_url,
                    user_id=user_id,
                    affected_voucher_count=affected_voucher_count,
                ),
                headers={},
                occurred_at=now,
            )
        )

    title = f"Provider {provider_id} scheduled exit"
    summary = _public_summary(
        provider_id=provider_id,
        effective_at=effective_at,
        reason=payload.reason,
        replacement_provider_id=payload.replacement_provider_id,
        public_message=payload.public_message,
    )
    insert_announcement = (
        pg_insert(ProviderExitStatusAnnouncement)
        .values(
            exit_plan_id=exit_plan.id,
            announcement_id=announcement_id,
            provider_id=provider_id,
            effective_at=effective_at,
            status_url=status_url,
            title=title,
            summary=summary,
            severity=payload.severity,
            announcement_status=payload.announcement_status,
            affected_user_count=affected_users,
            affected_voucher_count=affected_vouchers,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=["exit_plan_id"])
        .returning(ProviderExitStatusAnnouncement.id)
    )
    announcement_row_id = (await session.execute(insert_announcement)).scalar_one_or_none()
    announcement = (
        await session.execute(
            select(ProviderExitStatusAnnouncement).where(
                ProviderExitStatusAnnouncement.exit_plan_id == exit_plan.id
            )
        )
    ).scalar_one()
    if announcement_row_id is not None:
        session.add(
            OutboxEvent(
                aggregate_type="provider_exit_status_announcement",
                aggregate_id=announcement.id,
                event_type=PROVIDER_EXIT_STATUS_EVENT,
                event_version=1,
                payload=_announcement_payload(announcement=announcement, exit_plan=exit_plan),
                headers={},
                occurred_at=now,
            )
        )
    else:
        await session.execute(
            text(
                """
                UPDATE provider_exit_status_announcements
                   SET affected_user_count = :affected_user_count,
                       affected_voucher_count = :affected_voucher_count
                 WHERE id = :announcement_id
                """
            ),
            {
                "announcement_id": announcement.id,
                "affected_user_count": affected_users,
                "affected_voucher_count": affected_vouchers,
            },
        )

    return ProviderExitPlanResult(
        exit_plan_id=exit_plan.id,
        provider_id=provider_id,
        effective_at=effective_at,
        affected_users=affected_users,
        affected_vouchers=affected_vouchers,
        notification_requests_created=created_requests,
        status_url=status_url,
        announcement_id=announcement_id,
    )


async def provider_exit_plan_row_count(session: AsyncSession) -> int:
    return int(
        (await session.execute(select(func.count()).select_from(ProviderExitPlan))).scalar_one()
    )
