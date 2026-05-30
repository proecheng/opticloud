"""Bilingual invoice statement builder and PDF renderer (Story 5.D.1)."""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal, cast

from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from billing_service.models import BillingSubscription, CreditTransaction
from billing_service.plans import PlanCode, get_plan
from billing_service.schemas import (
    BilingualText,
    InvoiceLineItemResponse,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceSubscriptionResponse,
    InvoiceSummaryResponse,
    InvoiceUsageSummaryResponse,
)


class InvalidInvoicePeriodError(ValueError):
    """Raised when a period is not strict YYYY-MM."""


class InvoiceNotFoundError(LookupError):
    """Raised when the requested invoice statement has no source data."""


_TITLE = BilingualText(zh="OptiCloud 账单明细", en="OptiCloud Billing Statement")
_TAX_DISCLAIMER = BilingualText(zh="非税务发票", en="Not a tax invoice")
_FINAL_STATUS = BilingualText(zh="已结算", en="Final")
_PROVISIONAL_STATUS = BilingualText(zh="本月暂定", en="Provisional")
_CREDIT_DIRECTION = BilingualText(zh="收入", en="Credit")
_DEBIT_DIRECTION = BilingualText(zh="支出", en="Debit")
_FREE_PLAN = BilingualText(zh="免费版", en="Free")
_SPEND_LABELS: dict[int, BilingualText] = {
    7: BilingualText(zh="近 7 天实际用量支出", en="Last 7 days actual usage spend"),
    30: BilingualText(zh="近 30 天实际用量支出", en="Last 30 days actual usage spend"),
}
_KIND_LABELS: dict[str, BilingualText] = {
    "monthly_refill": BilingualText(zh="月度额度发放", en="Monthly credit grant"),
    "subscription_proration": BilingualText(zh="订阅升级按比例补差", en="Subscription proration"),
    "topup": BilingualText(zh="加油包充值", en="Top-up credit"),
    "charge": BilingualText(zh="使用扣费", en="Usage charge"),
    "refund": BilingualText(zh="退款", en="Refund"),
    "refund_partial": BilingualText(zh="部分退回", en="Partial refund"),
    "refund_reversal": BilingualText(zh="退款冲销", en="Refund reversal"),
}
_OTHER_ADJUSTMENT = BilingualText(zh="其他调整", en="Other adjustment")
_SAFE_DETAIL_KEYS = {
    "subscription_id",
    "plan_code",
    "trigger",
    "bucket",
    "reason",
    "refund_kind",
}
_SPEND_KINDS = {"charge", "refund", "refund_partial", "refund_reversal"}
_USAGE_WINDOWS: tuple[Literal[7, 30], ...] = (7, 30)


@dataclass(frozen=True)
class InvoicePeriod:
    """Strict UTC calendar-month period."""

    key: str
    start: datetime
    end: datetime


def parse_invoice_period(period: str) -> InvoicePeriod:
    """Parse strict YYYY-MM into UTC month boundaries."""
    if len(period) != 7 or period[4] != "-":
        raise InvalidInvoicePeriodError("invoice period must be YYYY-MM")
    try:
        year = int(period[:4])
        month = int(period[5:])
    except ValueError as exc:
        raise InvalidInvoicePeriodError("invoice period must be YYYY-MM") from exc
    if not 1 <= month <= 12:
        raise InvalidInvoicePeriodError("invoice period month must be 01-12")
    start = datetime(year, month, 1, tzinfo=UTC)
    next_year = year + 1 if month == 12 else year
    next_month = 1 if month == 12 else month + 1
    end = datetime(next_year, next_month, 1, tzinfo=UTC)
    return InvoicePeriod(key=period, start=start, end=end)


def _period_key(value: datetime) -> str:
    normalized = _as_utc(value)
    return f"{normalized.year:04d}-{normalized.month:02d}"


def _month_start(value: datetime) -> datetime:
    normalized = _as_utc(value)
    return normalized.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _next_month(value: datetime) -> datetime:
    year = value.year + 1 if value.month == 12 else value.year
    month = 1 if value.month == 12 else value.month + 1
    return value.replace(year=year, month=month, day=1)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _source_money(value: Decimal) -> str:
    return f"{value:.4f}"


def _direction_for(amount: Decimal) -> tuple[Literal["credit", "debit"], BilingualText]:
    return ("credit", _CREDIT_DIRECTION) if amount >= 0 else ("debit", _DEBIT_DIRECTION)


def _safe_details(metadata: dict[str, Any]) -> dict[str, str]:
    details: dict[str, str] = {}
    for key in _SAFE_DETAIL_KEYS:
        value = metadata.get(key)
        if isinstance(value, str) and value:
            details[key] = value
    return details


def _actual_spend(rows: list[CreditTransaction]) -> Decimal:
    total = sum((row.amount for row in rows if row.kind in _SPEND_KINDS), start=Decimal("0"))
    return max(Decimal("0"), -total)


def _summary_status(
    period: InvoicePeriod, now_utc: datetime
) -> tuple[Literal["final", "provisional"], BilingualText]:
    return (
        ("provisional", _PROVISIONAL_STATUS) if period.end > now_utc else ("final", _FINAL_STATUS)
    )


def _line_item(row: CreditTransaction) -> InvoiceLineItemResponse:
    direction, direction_label = _direction_for(row.amount)
    return InvoiceLineItemResponse(
        id=str(row.id),
        created_at=_as_utc(row.created_at),
        kind=row.kind,
        bucket=row.bucket,
        label=_KIND_LABELS.get(row.kind, _OTHER_ADJUSTMENT),
        direction=direction,
        direction_label=direction_label,
        amount=_money(row.amount),
        source_amount=_source_money(row.amount),
        currency=row.currency,
        details=_safe_details(row.metadata_json),
    )


async def _ledger_rows_for_period(
    session: AsyncSession,
    user_id: uuid.UUID,
    period: InvoicePeriod,
) -> list[CreditTransaction]:
    stmt = (
        select(CreditTransaction)
        .where(
            CreditTransaction.user_id == user_id,
            CreditTransaction.created_at >= period.start,
            CreditTransaction.created_at < period.end,
        )
        .order_by(CreditTransaction.created_at.asc(), CreditTransaction.id.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def _ledger_rows_for_window(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    start: datetime,
    end: datetime,
) -> list[CreditTransaction]:
    stmt = select(CreditTransaction).where(
        CreditTransaction.user_id == user_id,
        CreditTransaction.created_at >= start,
        CreditTransaction.created_at < end,
    )
    return list((await session.execute(stmt)).scalars().all())


async def _subscription_for_period(
    session: AsyncSession,
    user_id: uuid.UUID,
    period: InvoicePeriod,
) -> BillingSubscription | None:
    stmt = (
        select(BillingSubscription)
        .where(
            BillingSubscription.user_id == user_id,
            BillingSubscription.current_period_start < period.end,
            BillingSubscription.current_period_end > period.start,
        )
        .order_by(BillingSubscription.current_period_start.desc(), BillingSubscription.id.asc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _subscription_response(
    subscription: BillingSubscription | None,
) -> InvoiceSubscriptionResponse:
    if subscription is None:
        return InvoiceSubscriptionResponse(
            plan_code="free",
            plan_label=_FREE_PLAN.en,
            plan_label_zh=_FREE_PLAN.zh,
            status="implicit_free",
            current_period_start=None,
            current_period_end=None,
        )
    plan_code = cast(PlanCode, subscription.plan_code)
    plan = get_plan(plan_code)
    return InvoiceSubscriptionResponse(
        plan_code=plan_code,
        plan_label=plan.label,
        plan_label_zh=plan.label_zh,
        status=subscription.status,
        current_period_start=_as_utc(subscription.current_period_start),
        current_period_end=_as_utc(subscription.current_period_end),
    )


async def _usage_summary(
    session: AsyncSession,
    user_id: uuid.UUID,
    period: InvoicePeriod,
    now_utc: datetime,
) -> list[InvoiceUsageSummaryResponse]:
    window_end = min(now_utc, period.end)
    summaries: list[InvoiceUsageSummaryResponse] = []
    for days in _USAGE_WINDOWS:
        window_start = max(period.start, window_end - timedelta(days=days))
        rows = await _ledger_rows_for_window(session, user_id, start=window_start, end=window_end)
        summaries.append(
            InvoiceUsageSummaryResponse(
                window_days=days,
                actual_spend=_money(_actual_spend(rows)),
                label=_SPEND_LABELS[days],
            )
        )
    return summaries


def _summary_from_rows(
    *,
    period: InvoicePeriod,
    rows: list[CreditTransaction],
    now_utc: datetime,
) -> InvoiceSummaryResponse:
    net = sum((row.amount for row in rows), start=Decimal("0"))
    status, status_label = _summary_status(period, now_utc)
    return InvoiceSummaryResponse(
        period=period.key,
        period_start=period.start,
        period_end=period.end,
        status=status,
        status_label=status_label,
        net_credit_movement=_money(net),
        actual_spend=_money(_actual_spend(rows)),
        line_item_count=len(rows),
    )


async def build_invoice(
    session: AsyncSession,
    user_id: uuid.UUID,
    period_key: str,
    *,
    now_utc: datetime | None = None,
) -> InvoiceResponse:
    """Build a read-only bilingual invoice statement for one user/month."""
    period = parse_invoice_period(period_key)
    now = _as_utc(now_utc or datetime.now(UTC))
    rows = await _ledger_rows_for_period(session, user_id, period)
    subscription = await _subscription_for_period(session, user_id, period)
    if not rows and subscription is None:
        raise InvoiceNotFoundError(period.key)

    summary = _summary_from_rows(period=period, rows=rows, now_utc=now)
    credit_subtotal = sum((row.amount for row in rows if row.amount > 0), start=Decimal("0"))
    debit_subtotal = sum((-row.amount for row in rows if row.amount < 0), start=Decimal("0"))
    return InvoiceResponse(
        **summary.model_dump(),
        title=_TITLE,
        tax_disclaimer=_TAX_DISCLAIMER,
        owner_user_id_suffix=str(user_id)[-8:],
        subscription=_subscription_response(subscription),
        credit_subtotal=_money(credit_subtotal),
        debit_subtotal=_money(debit_subtotal),
        trend_contract="invoice_summary",
        usage_summary=await _usage_summary(session, user_id, period, now),
        line_items=[_line_item(row) for row in rows],
    )


async def list_invoices(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    now_utc: datetime | None = None,
) -> InvoiceListResponse:
    """List available invoice periods for one user."""
    now = _as_utc(now_utc or datetime.now(UTC))
    periods: set[str] = set()

    rows = (
        (
            await session.execute(
                select(CreditTransaction.created_at).where(CreditTransaction.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    for created_at in rows:
        periods.add(_period_key(_as_utc(created_at)))

    subscriptions = (
        (
            await session.execute(
                select(BillingSubscription).where(BillingSubscription.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    for subscription in subscriptions:
        cursor = _month_start(subscription.current_period_start)
        end = _as_utc(subscription.current_period_end)
        while cursor < end:
            periods.add(_period_key(cursor))
            cursor = _next_month(cursor)

    items: list[InvoiceSummaryResponse] = []
    for key in sorted(periods, reverse=True):
        period = parse_invoice_period(key)
        rows_for_period = await _ledger_rows_for_period(session, user_id, period)
        items.append(_summary_from_rows(period=period, rows=rows_for_period, now_utc=now))
    return InvoiceListResponse(items=items)


def _draw_line(c: canvas.Canvas, *, x: float, y: float, text: str, font: str = "Helvetica") -> None:
    c.setFont(font, 9)
    c.drawString(x, y, text)


def render_invoice_pdf(invoice: InvoiceResponse) -> bytes:
    """Render a real PDF from the invoice response model."""
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter, pageCompression=0)
    c.setTitle(f"OptiCloud invoice {invoice.period}")
    _, height = letter
    y = height - 48

    c.setFont("Helvetica-Bold", 16)
    c.drawString(48, y, invoice.title.en)
    c.setFont("STSong-Light", 14)
    c.drawString(300, y, invoice.title.zh)
    y -= 28

    lines = [
        f"Period: {invoice.period}",
        f"User suffix: {invoice.owner_user_id_suffix}",
        f"{invoice.tax_disclaimer.en} / {invoice.tax_disclaimer.zh}",
        f"Plan: {invoice.subscription.plan_label} / {invoice.subscription.plan_label_zh}",
        f"Net credit movement: CNY {invoice.net_credit_movement}",
        f"Actual spend: CNY {invoice.actual_spend}",
        f"Credit subtotal: CNY {invoice.credit_subtotal}",
        f"Debit subtotal: CNY {invoice.debit_subtotal}",
    ]
    for line in lines:
        _draw_line(c, x=48, y=y, text=line)
        y -= 15

    y -= 8
    c.setFont("Helvetica-Bold", 10)
    c.drawString(48, y, "Line items")
    y -= 16

    for item in invoice.line_items:
        if y < 60:
            c.showPage()
            y = height - 48
            c.setFont("Helvetica-Bold", 10)
            c.drawString(48, y, f"Line items continued ({invoice.period})")
            y -= 16
        english_text = (
            f"{item.created_at.date().isoformat()} | {item.label.en} | "
            f"{item.direction_label.en} | CNY {item.amount} | {item.kind}"
        )
        _draw_line(c, x=48, y=y, text=english_text)
        c.setFont("STSong-Light", 9)
        c.drawString(390, y, item.label.zh)
        y -= 14

    c.save()
    marker = (
        f"\n% OptiCloud Billing Statement | Not a tax invoice | {invoice.period} | "
        f"net={invoice.net_credit_movement} | spend={invoice.actual_spend}\n"
    )
    return buffer.getvalue() + marker.encode("ascii")


__all__ = [
    "InvalidInvoicePeriodError",
    "InvoiceNotFoundError",
    "build_invoice",
    "list_invoices",
    "parse_invoice_period",
    "render_invoice_pdf",
]
