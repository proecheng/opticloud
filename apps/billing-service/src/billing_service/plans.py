"""Plan catalog and monthly period helpers — Story 5.B.1."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

PlanCode = Literal["free", "starter", "pro", "team", "enterprise"]


@dataclass(frozen=True)
class RateLimits:
    """PRD rate-limit metadata for a plan."""

    rps: int | None
    requests_per_minute: int | None
    concurrent_solves: int | None
    t5_t6_p5: str
    custom: bool = False


@dataclass(frozen=True)
class Plan:
    """Runtime billing plan definition.

    `monthly_credits` are internal runtime defaults, not public pricing claims.
    """

    code: PlanCode
    label: str
    label_zh: str
    monthly_credits: Decimal
    rate_limits: RateLimits
    commercial_review_required: bool
    external_payment_required: bool


PLANS: tuple[Plan, ...] = (
    Plan(
        code="free",
        label="Free",
        label_zh="免费版",
        monthly_credits=Decimal("0.00"),
        rate_limits=RateLimits(
            rps=3,
            requests_per_minute=30,
            concurrent_solves=1,
            t5_t6_p5="单次小规模",
        ),
        commercial_review_required=False,
        external_payment_required=False,
    ),
    Plan(
        code="starter",
        label="Starter",
        label_zh="入门版",
        monthly_credits=Decimal("2000.00"),
        rate_limits=RateLimits(
            rps=5,
            requests_per_minute=200,
            concurrent_solves=3,
            t5_t6_p5="日 10 次",
        ),
        commercial_review_required=False,
        external_payment_required=True,
    ),
    Plan(
        code="pro",
        label="Pro",
        label_zh="专业版",
        monthly_credits=Decimal("10000.00"),
        rate_limits=RateLimits(
            rps=20,
            requests_per_minute=1000,
            concurrent_solves=10,
            t5_t6_p5="不限",
        ),
        commercial_review_required=False,
        external_payment_required=True,
    ),
    Plan(
        code="team",
        label="Team",
        label_zh="团队版",
        monthly_credits=Decimal("50000.00"),
        rate_limits=RateLimits(
            rps=100,
            requests_per_minute=5000,
            concurrent_solves=30,
            t5_t6_p5="不限",
        ),
        commercial_review_required=True,
        external_payment_required=True,
    ),
    Plan(
        code="enterprise",
        label="Enterprise",
        label_zh="企业版",
        monthly_credits=Decimal("200000.00"),
        rate_limits=RateLimits(
            rps=None,
            requests_per_minute=None,
            concurrent_solves=None,
            t5_t6_p5="不限",
            custom=True,
        ),
        commercial_review_required=True,
        external_payment_required=True,
    ),
)

PLAN_BY_CODE: dict[PlanCode, Plan] = {plan.code: plan for plan in PLANS}


def get_plan(plan_code: PlanCode) -> Plan:
    """Return a plan by code."""
    return PLAN_BY_CODE[plan_code]


def add_one_calendar_month(value: datetime) -> datetime:
    """Advance by one calendar month, clamping day to month end."""
    year = value.year
    month = value.month + 1
    if month == 13:
        year += 1
        month = 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


__all__ = [
    "PLAN_BY_CODE",
    "PLANS",
    "Plan",
    "PlanCode",
    "RateLimits",
    "add_one_calendar_month",
    "get_plan",
]
