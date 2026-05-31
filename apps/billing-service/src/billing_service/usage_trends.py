"""Billing usage trend builder (Story 5.D.2)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from billing_service.models import CreditTransaction
from billing_service.schemas import (
    BilingualText,
    UsageTrendPointResponse,
    UsageTrendsResponse,
    UsageTrendWindowResponse,
)
from billing_service.spend import SPEND_KINDS, actual_spend_from_signed_total

_TREND_CONTRACT: Literal["billing_usage_trends_v1"] = "billing_usage_trends_v1"
_WINDOWS: tuple[Literal[7, 30], ...] = (7, 30)
_LABELS: dict[int, BilingualText] = {
    7: BilingualText(zh="近 7 天实际用量支出趋势", en="Last 7 days actual usage spend trend"),
    30: BilingualText(zh="近 30 天实际用量支出趋势", en="Last 30 days actual usage spend trend"),
}


@dataclass(frozen=True)
class UsageTrendWindow:
    """UTC day window with exclusive end."""

    days: Literal[7, 30]
    start_date: date
    end_exclusive_date: date

    @property
    def start(self) -> datetime:
        return datetime.combine(self.start_date, time.min, tzinfo=UTC)

    @property
    def end(self) -> datetime:
        return datetime.combine(self.end_exclusive_date, time.min, tzinfo=UTC)

    @property
    def dates(self) -> list[date]:
        return [self.start_date + timedelta(days=offset) for offset in range(self.days)]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _window(days: Literal[7, 30], now_utc: datetime) -> UsageTrendWindow:
    current_date = _as_utc(now_utc).date()
    start_date = current_date - timedelta(days=days - 1)
    return UsageTrendWindow(
        days=days,
        start_date=start_date,
        end_exclusive_date=current_date + timedelta(days=1),
    )


async def _ledger_rows_for_trends(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    start: datetime,
    end: datetime,
) -> list[CreditTransaction]:
    stmt = (
        select(CreditTransaction)
        .where(
            CreditTransaction.user_id == user_id,
            CreditTransaction.kind.in_(SPEND_KINDS),
            CreditTransaction.created_at >= start,
            CreditTransaction.created_at < end,
        )
        .order_by(CreditTransaction.created_at.asc(), CreditTransaction.id.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


def _daily_spend(
    rows: list[CreditTransaction],
    dates: list[date],
) -> dict[date, Decimal]:
    signed_totals = {day: Decimal("0") for day in dates}
    for row in rows:
        day = _as_utc(row.created_at).date()
        if day in signed_totals:
            signed_totals[day] += row.amount
    return {
        day: actual_spend_from_signed_total(signed_total)
        for day, signed_total in signed_totals.items()
    }


def _window_response(
    window: UsageTrendWindow,
    rows: list[CreditTransaction],
) -> UsageTrendWindowResponse:
    dates = window.dates
    by_day = _daily_spend(rows, dates)
    points = [UsageTrendPointResponse(date=day, actual_spend=_money(by_day[day])) for day in dates]
    total = sum(by_day.values(), start=Decimal("0"))
    average = total / Decimal(window.days)
    return UsageTrendWindowResponse(
        window_days=window.days,
        window_start=window.start,
        window_end=window.end,
        label=_LABELS[window.days],
        total_actual_spend=_money(total),
        average_daily_spend=_money(average),
        points=points,
    )


async def build_usage_trends(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    now_utc: datetime | None = None,
) -> UsageTrendsResponse:
    """Build read-only owner-scoped 7d/30d usage spend trends."""
    now = _as_utc(now_utc or datetime.now(UTC))
    windows = [_window(days, now) for days in _WINDOWS]
    start = min(window.start for window in windows)
    end = max(window.end for window in windows)
    rows = await _ledger_rows_for_trends(session, user_id, start=start, end=end)
    return UsageTrendsResponse(
        trend_contract=_TREND_CONTRACT,
        generated_at=now,
        windows=[_window_response(window, rows) for window in windows],
    )


__all__ = ["build_usage_trends"]
