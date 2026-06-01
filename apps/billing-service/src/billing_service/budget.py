"""Monthly budget controls — Story 5.D.5."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, cast

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from billing_service.models import (
    BillingBudgetControl,
    BillingBudgetEvent,
    CreditTransaction,
    OutboxEvent,
)
from billing_service.schemas import (
    BudgetEventSummaryResponse,
    BudgetStatusResponse,
)
from billing_service.spend import SPEND_KINDS, actual_spend_from_signed_total

DEFAULT_ALERT_THRESHOLD_RATIO = Decimal("0.8000")
BUDGET_EVENT_CONFIGURED = "billing.budget.configured"
BUDGET_EVENT_DISABLED = "billing.budget.disabled"
BUDGET_EVENT_ALERTED = "billing.budget.alerted"
BUDGET_EVENT_PAUSED = "billing.budget.paused"
BudgetNotificationChannel = Literal["email", "webhook", "in_app"]
BUDGET_CHANNELS: list[BudgetNotificationChannel] = ["email", "in_app"]
BUDGET_NOTIFICATION_CHANNEL_ORDER: tuple[BudgetNotificationChannel, ...] = (
    "email",
    "webhook",
    "in_app",
)


@dataclass(frozen=True)
class BudgetPeriod:
    """UTC calendar-month budget period."""

    start: datetime
    end: datetime


@dataclass(frozen=True)
class BudgetNotificationPreference:
    """Delivery channel selection read from auth-owned notification preferences."""

    channels: list[BudgetNotificationChannel]
    webhook_url_configured: bool


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def current_budget_period(now: datetime | None = None) -> BudgetPeriod:
    current = as_utc(now or datetime.now(UTC))
    start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return BudgetPeriod(start=start, end=end)


def money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def ratio(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP):.4f}"


def percent_used(actual_spend: Decimal, budget_amount: Decimal | None) -> Decimal:
    if budget_amount is None or budget_amount <= Decimal("0"):
        return Decimal("0")
    return actual_spend / budget_amount


async def monthly_actual_spend(
    session: AsyncSession,
    user_id: uuid.UUID,
    period: BudgetPeriod,
) -> Decimal:
    stmt = select(func.coalesce(func.sum(CreditTransaction.amount), Decimal("0"))).where(
        CreditTransaction.user_id == user_id,
        CreditTransaction.kind.in_(SPEND_KINDS),
        CreditTransaction.created_at >= period.start,
        CreditTransaction.created_at < period.end,
    )
    signed_total = Decimal(str((await session.execute(stmt)).scalar_one()))
    return actual_spend_from_signed_total(signed_total).quantize(Decimal("0.0001"))


async def lock_budget_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Serialize budget control creation/evaluation per user."""
    await session.execute(
        text("SELECT id FROM users WHERE id = :user_id FOR UPDATE"), {"user_id": user_id}
    )


async def get_budget_control(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> BillingBudgetControl | None:
    stmt = select(BillingBudgetControl).where(BillingBudgetControl.user_id == user_id)
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def budget_notification_preference(
    session: AsyncSession,
    user_id: uuid.UUID,
    event_type: str,
) -> BudgetNotificationPreference:
    """Read auth-owned notification preferences with raw SQL across the service boundary."""
    row = (
        (
            await session.execute(
                text(
                    """
                    SELECT email_enabled, webhook_enabled, in_app_enabled, webhook_url
                      FROM notification_preferences
                     WHERE user_id = :user_id
                       AND event_type = :event_type
                    """
                ),
                {"user_id": user_id, "event_type": event_type},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return BudgetNotificationPreference(
            channels=list(BUDGET_CHANNELS),
            webhook_url_configured=False,
        )

    enabled = {
        "email": bool(row["email_enabled"]),
        "webhook": bool(row["webhook_enabled"]),
        "in_app": bool(row["in_app_enabled"]),
    }
    return BudgetNotificationPreference(
        channels=[channel for channel in BUDGET_NOTIFICATION_CHANNEL_ORDER if enabled[channel]],
        webhook_url_configured=bool(row["webhook_enabled"] and row["webhook_url"]),
    )


def _event_payload(
    control: BillingBudgetControl,
    *,
    event_type: str,
    period: BudgetPeriod,
    actual_spend: Decimal,
    notification_preference: BudgetNotificationPreference | None = None,
) -> dict[str, str | list[str] | bool]:
    used = percent_used(actual_spend, control.monthly_budget_amount)
    payload: dict[str, str | list[str] | bool] = {
        "budget_control_id": str(control.id),
        "user_id": str(control.user_id),
        "period_start": period.start.isoformat(),
        "period_end": period.end.isoformat(),
        "event_type": event_type,
        "monthly_budget_amount": money(control.monthly_budget_amount),
        "actual_spend": money(actual_spend),
        "percent_used": ratio(used),
        "alert_threshold_ratio": ratio(control.alert_threshold_ratio),
        "currency": "CNY",
    }
    if event_type in {BUDGET_EVENT_ALERTED, BUDGET_EVENT_PAUSED}:
        preference = notification_preference or BudgetNotificationPreference(
            channels=list(BUDGET_CHANNELS),
            webhook_url_configured=False,
        )
        payload["channels"] = list(preference.channels)
        if preference.webhook_url_configured:
            payload["webhook_url_configured"] = True
    return payload


async def _write_budget_event_once(
    session: AsyncSession,
    control: BillingBudgetControl,
    *,
    event_type: str,
    period: BudgetPeriod,
    actual_spend: Decimal,
) -> bool:
    """Insert a budget event and matching outbox row once per user/month/type."""
    now = datetime.now(UTC)
    notification_preference = None
    if event_type in {BUDGET_EVENT_ALERTED, BUDGET_EVENT_PAUSED}:
        notification_preference = await budget_notification_preference(
            session,
            control.user_id,
            event_type,
        )
    payload = _event_payload(
        control,
        event_type=event_type,
        period=period,
        actual_spend=actual_spend,
        notification_preference=notification_preference,
    )
    statement = """
        INSERT INTO billing_budget_events
            (user_id, budget_control_id, period_start, period_end, event_type, payload, occurred_at)
        VALUES
            (:user_id, :budget_control_id, :period_start, :period_end, :event_type,
             CAST(:payload AS jsonb), :occurred_at)
    """
    if event_type in {BUDGET_EVENT_ALERTED, BUDGET_EVENT_PAUSED}:
        statement += """
            ON CONFLICT (user_id, period_start, event_type)
            WHERE event_type IN ('billing.budget.alerted', 'billing.budget.paused')
            DO NOTHING
        """
    statement += " RETURNING id"
    result = await session.execute(
        text(statement),
        {
            "user_id": control.user_id,
            "budget_control_id": control.id,
            "period_start": period.start,
            "period_end": period.end,
            "event_type": event_type,
            "payload": json.dumps(payload, sort_keys=True, separators=(",", ":")),
            "occurred_at": now,
        },
    )
    event_id = result.scalar_one_or_none()
    if event_id is None:
        return False
    session.add(
        OutboxEvent(
            aggregate_type="billing_budget_control",
            aggregate_id=control.id,
            event_type=event_type,
            event_version=1,
            payload={**payload, "budget_event_id": str(event_id)},
            headers={"compensation": "none"},
            occurred_at=now,
        )
    )
    await session.flush()
    return True


async def evaluate_budget_thresholds(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
    control: BillingBudgetControl | None = None,
) -> BillingBudgetControl | None:
    """Evaluate current-period alert/pause thresholds idempotently."""
    period = current_budget_period(now)
    if control is None:
        control = await get_budget_control(session, user_id, for_update=True)
    if control is None or not control.enabled:
        return control

    spend = await monthly_actual_spend(session, user_id, period)
    used = percent_used(spend, control.monthly_budget_amount)
    if control.status == "paused" and control.pause_period_start != period.start:
        control.status = "active"
        control.paused_at = None
        control.pause_period_start = None
        control.updated_at = as_utc(now or datetime.now(UTC))
    if used >= control.alert_threshold_ratio:
        await _write_budget_event_once(
            session,
            control,
            event_type=BUDGET_EVENT_ALERTED,
            period=period,
            actual_spend=spend,
        )
    if used >= Decimal("1"):
        now_utc = as_utc(now or datetime.now(UTC))
        if control.status != "paused" or control.pause_period_start != period.start:
            control.status = "paused"
            control.paused_at = now_utc
            control.pause_period_start = period.start
            control.updated_at = now_utc
        await _write_budget_event_once(
            session,
            control,
            event_type=BUDGET_EVENT_PAUSED,
            period=period,
            actual_spend=spend,
        )
        await session.flush()
    return control


async def configure_budget(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    monthly_budget_amount: Decimal | None,
    enabled: bool,
    now: datetime | None = None,
) -> BillingBudgetControl:
    """Create/update current budget control and evaluate thresholds."""
    now_utc = as_utc(now or datetime.now(UTC))
    period = current_budget_period(now_utc)
    await lock_budget_user(session, user_id)
    control = await get_budget_control(session, user_id, for_update=True)
    if control is None:
        control = BillingBudgetControl(
            user_id=user_id,
            monthly_budget_amount=monthly_budget_amount or Decimal("1.00"),
            alert_threshold_ratio=DEFAULT_ALERT_THRESHOLD_RATIO,
            enabled=enabled,
            status="active",
            paused_at=None,
            pause_period_start=None,
            created_at=now_utc,
            updated_at=now_utc,
        )
        session.add(control)
        await session.flush()

    if not enabled:
        control.enabled = False
        control.status = "active"
        control.paused_at = None
        control.pause_period_start = None
        control.updated_at = now_utc
        spend = await monthly_actual_spend(session, user_id, period)
        await _write_budget_event_once(
            session,
            control,
            event_type=BUDGET_EVENT_DISABLED,
            period=period,
            actual_spend=spend,
        )
        await session.flush()
        return control

    assert monthly_budget_amount is not None
    control.enabled = True
    control.monthly_budget_amount = monthly_budget_amount
    control.status = "active"
    control.paused_at = None
    control.pause_period_start = None
    control.updated_at = now_utc
    spend = await monthly_actual_spend(session, user_id, period)
    await _write_budget_event_once(
        session,
        control,
        event_type=BUDGET_EVENT_CONFIGURED,
        period=period,
        actual_spend=spend,
    )
    await evaluate_budget_thresholds(session, user_id, now=now_utc, control=control)
    await session.flush()
    return control


async def current_budget_is_paused(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> BillingBudgetControl | None:
    period = current_budget_period(now)
    control = await get_budget_control(session, user_id, for_update=True)
    if control is None or not control.enabled:
        return None
    if control.status == "paused" and control.pause_period_start == period.start:
        return control
    return None


async def recent_budget_events(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 5,
) -> list[BillingBudgetEvent]:
    stmt = (
        select(BillingBudgetEvent)
        .where(BillingBudgetEvent.user_id == user_id)
        .order_by(BillingBudgetEvent.occurred_at.desc(), BillingBudgetEvent.id.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


def event_summary(event: BillingBudgetEvent) -> BudgetEventSummaryResponse:
    payload = event.payload
    raw_channels = payload.get("channels", [])
    channels: list[BudgetNotificationChannel] = [
        cast(BudgetNotificationChannel, channel)
        for channel in raw_channels
        if channel in {"email", "webhook", "in_app"}
    ]
    return BudgetEventSummaryResponse(
        id=str(event.id),
        event_type=cast(AnyBudgetEventType, event.event_type),
        period_start=event.period_start,
        period_end=event.period_end,
        occurred_at=event.occurred_at,
        budget_amount=str(payload.get("monthly_budget_amount", "0.00")),
        actual_spend=str(payload.get("actual_spend", "0.00")),
        percent_used=str(payload.get("percent_used", "0.0000")),
        channels=channels,
    )


AnyBudgetEventType = Literal[
    "billing.budget.configured",
    "billing.budget.disabled",
    "billing.budget.alerted",
    "billing.budget.paused",
]


async def budget_status_response(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> BudgetStatusResponse:
    period = current_budget_period(now)
    control = await get_budget_control(session, user_id)
    spend = await monthly_actual_spend(session, user_id, period)
    events = await recent_budget_events(session, user_id)
    if control is None:
        return BudgetStatusResponse(
            budget_control_id=None,
            enabled=False,
            status="not_configured",
            monthly_budget_amount=None,
            alert_threshold_ratio=ratio(DEFAULT_ALERT_THRESHOLD_RATIO),
            period_start=period.start,
            period_end=period.end,
            actual_spend=money(spend),
            percent_used="0.0000",
            alert_threshold_reached=False,
            paused=False,
            recent_events=[event_summary(event) for event in events],
        )

    used = percent_used(spend, control.monthly_budget_amount)
    current_pause = bool(
        control.enabled
        and control.status == "paused"
        and control.pause_period_start == period.start
    )
    status: Literal["disabled", "active", "paused"] = (
        "disabled" if not control.enabled else "paused" if current_pause else "active"
    )
    return BudgetStatusResponse(
        budget_control_id=str(control.id),
        enabled=control.enabled,
        status=status,
        monthly_budget_amount=money(control.monthly_budget_amount),
        alert_threshold_ratio=ratio(control.alert_threshold_ratio),
        period_start=period.start,
        period_end=period.end,
        actual_spend=money(spend),
        percent_used=ratio(used),
        alert_threshold_reached=bool(control.enabled and used >= control.alert_threshold_ratio),
        paused=current_pause,
        paused_at=control.paused_at if current_pause else None,
        pause_period_start=control.pause_period_start if current_pause else None,
        recent_events=[event_summary(event) for event in events],
    )


__all__ = [
    "BUDGET_EVENT_ALERTED",
    "BUDGET_EVENT_PAUSED",
    "budget_status_response",
    "configure_budget",
    "current_budget_is_paused",
    "current_budget_period",
    "evaluate_budget_thresholds",
    "monthly_actual_spend",
]
