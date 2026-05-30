"""Pydantic schemas for billing-service HTTP API (Story 5.A.1)."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from billing_service.topups import normalize_topup_amount

_IDEMPOTENCY_KEY_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def validate_idempotency_key(key: str) -> str:
    """S3: enforce UUID format on Idempotency-Key header."""
    if not _IDEMPOTENCY_KEY_RE.match(key):
        raise ValueError(f"Idempotency-Key must be a UUID; got {key!r}")
    return key


class ChargeCreateRequest(BaseModel):
    """POST /v1/billing/charges body.

    amount comes in as STRING (D3) for decimal precision; stored as Decimal.
    5.A.0 — max_solve_seconds remains an accepted client-side pricing hint;
    new Saga rows keep payload_ref pointer-only and finalize derives cap from
    the reserved amount plus configured rate.
    Story 5.A.5 — added `confirmed` for pre-charge guard explicit opt-in.
    """

    amount: Decimal = Field(..., gt=0, description='Amount in CNY, string "6.00"')
    currency: Literal["CNY"] = "CNY"
    purpose: Literal["solve", "predict", "chat", "demo"] = "demo"
    reference_id: str = Field(..., description="UUID identifying the source of this charge")
    max_solve_seconds: float = Field(
        default=60.0,
        gt=0,
        le=600.0,
        description="Cap for per-formula charging (5.A.4); matches solver options.max_solve_seconds",
    )
    confirmed: bool = Field(
        default=False,
        description=(
            "User has seen pre-charge warning Modal and confirmed (Story 5.A.5). "
            "MUST be true when the prior /estimate response had requires_explicit_confirm=true; "
            "ignored otherwise."
        ),
    )

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, v: object) -> Decimal:
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class WarningResponse(BaseModel):
    """One pre-charge warning, returned by /estimate (Story 5.A.5)."""

    kind: Literal["balance_low", "p5_call", "p5_call_and_balance_low"]
    message: str
    remediation_hint_key: str


class EstimateRequest(BaseModel):
    """POST /v1/billing/charges/estimate body (Story 5.A.5)."""

    purpose: Literal["solve", "predict", "chat", "demo"] = "demo"
    max_solve_seconds: float = Field(default=60.0, ge=0.1, le=600.0)


class EstimateResponse(BaseModel):
    """POST /v1/billing/charges/estimate response (Story 5.A.5)."""

    estimated_amount: str
    currency: str = "CNY"
    balance: str
    warnings: list[WarningResponse]
    requires_explicit_confirm: bool


class ChargeResponse(BaseModel):
    """POST /v1/billing/charges + /confirm response."""

    charge_id: str  # UUID as str
    current_state: str  # State enum value
    amount: str  # Decimal as str for precision
    currency: str = "CNY"
    balance_before: str
    balance_after: str


class TopupCreateRequest(BaseModel):
    """POST /v1/billing/topups body — Story 5.A.6."""

    amount: Decimal = Field(..., gt=0, description='Topup pack amount in CNY, string "10.00"')
    currency: Literal["CNY"] = "CNY"
    reference_id: str = Field(..., description="UUID or payment-intent pointer for this topup")

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_and_validate_amount(cls, v: object) -> Decimal:
        return normalize_topup_amount(Decimal(str(v)))

    @field_validator("reference_id")
    @classmethod
    def _validate_reference_id(cls, v: str) -> str:
        validate_idempotency_key(v)
        return v


class TopupConfirmRequest(BaseModel):
    """POST /v1/billing/topups/{id}/confirm body — internal payment callback."""

    provider: Literal["manual", "stripe", "wechat", "alipay"] = "manual"
    payment_ref: str = Field(
        ...,
        min_length=3,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$",
    )


class TopupResponse(BaseModel):
    """Topup request/confirmation response."""

    topup_id: str
    current_state: str
    amount: str
    currency: str = "CNY"
    bucket: Literal["topup"] = "topup"
    expires_at: None = None
    expires_hint: str = "永不过期"
    balance_after: str | None = None


class ReserveChargeResponse(BaseModel):
    """POST /v1/billing/charges/{id}/reserve response — 5.A.4 AC1."""

    charge_id: str
    current_state: str
    amount_reserved: str
    balance_after_reserve: str
    currency: str = "CNY"


class FinalizeChargeRequest(BaseModel):
    """POST /v1/billing/charges/{id}/finalize body — 5.A.4 AC1."""

    elapsed_seconds: float = Field(
        ..., ge=0, description="Actual solver wall-time from LPSolveResult.solve_seconds"
    )
    status: Literal["success", "failure"]
    failure_reason: str | None = Field(
        default=None, description="Required when status='failure'; null otherwise"
    )
    discount_multiplier: Decimal = Field(
        default=Decimal("1.0"),
        gt=0,
        le=1,
        description="Story 3.10 optional billing discount multiplier; 1.0 means no discount",
    )


class FinalizeChargeResponse(BaseModel):
    """POST /v1/billing/charges/{id}/finalize response — 5.A.4 AC1."""

    charge_id: str
    current_state: str
    reserved_amount: str
    actual_amount: str
    refund_partial_amount: str  # "0.00" if no partial refund
    balance_before: str
    balance_after: str
    currency: str = "CNY"


class BucketBalance(BaseModel):
    """One per-bucket entry in BalanceResponse.buckets[] (Story 5.A.2 FR B1)."""

    name: Literal["monthly", "signup", "edu", "topup"]
    label_zh: str
    balance: str  # Decimal as str, 2 decimals
    expires_hint: str | None = None


class BalanceResponse(BaseModel):
    """GET /v1/billing/balance response."""

    user_id: str
    balance: str  # Decimal as str — total across all buckets
    currency: str = "CNY"
    last_transaction_at: datetime | None = None
    # Story 5.A.2 — always exactly 4 entries in canonical order; missing buckets get 0.00
    buckets: list[BucketBalance] = Field(default_factory=list)


class PlanRateLimits(BaseModel):
    """Plan rate-limit metadata copied from PRD."""

    rps: int | None
    requests_per_minute: int | None
    concurrent_solves: int | None
    t5_t6_p5: str
    custom: bool = False


class PlanResponse(BaseModel):
    """One subscription plan catalog item."""

    code: Literal["free", "starter", "pro", "team", "enterprise"]
    label: str
    label_zh: str
    monthly_credits: str
    currency: str = "CNY"
    rate_limits: PlanRateLimits
    commercial_review_required: bool
    external_payment_required: bool


class PlanListResponse(BaseModel):
    """GET /v1/billing/plans response."""

    items: list[PlanResponse]


class SubscriptionCreateRequest(BaseModel):
    """POST /v1/billing/subscriptions body — Story 5.B.1."""

    plan_code: Literal["free", "starter", "pro", "team", "enterprise"]


class SubscriptionProrationResponse(BaseModel):
    """Prorated plan-change adjustment details."""

    from_plan_code: Literal["free", "starter", "pro", "team", "enterprise"]
    to_plan_code: Literal["free", "starter", "pro", "team", "enterprise"]
    amount: str
    currency: str = "CNY"
    remaining_days: int
    total_days: int


class SubscriptionResponse(BaseModel):
    """Current or newly-created subscription response."""

    subscription_id: str | None
    plan_code: Literal["free", "starter", "pro", "team", "enterprise"]
    status: Literal["implicit_free", "active", "canceled", "expired"]
    current_period_start: datetime | None
    current_period_end: datetime | None
    monthly_credits: str
    currency: str = "CNY"
    entitlement_source: str | None = None
    refill_bucket: Literal["monthly", "signup", "edu", "topup"] = "monthly"
    external_payment_required: bool | None = None
    education_entitlement: str | None = None
    trial_ends_at: datetime | None = None
    fallback_plan_code: Literal["starter"] | None = None
    proration: SubscriptionProrationResponse | None = None


class EduStarterSyncRequest(BaseModel):
    """Internal education Starter entitlement sync request."""

    user_id: str = Field(..., description="UUID pointer to a users.id row")


class RefillDueRequest(BaseModel):
    """Internal monthly refill scheduler request."""

    as_of: datetime | None = None


class RefillDueResponse(BaseModel):
    """Internal monthly refill scheduler response."""

    processed: int
    refilled: int
    skipped_zero_credit: int
    as_of: datetime


__all__ = [
    "BalanceResponse",
    "BucketBalance",
    "ChargeCreateRequest",
    "ChargeResponse",
    "EduStarterSyncRequest",
    "EstimateRequest",
    "EstimateResponse",
    "FinalizeChargeRequest",
    "FinalizeChargeResponse",
    "PlanListResponse",
    "PlanRateLimits",
    "PlanResponse",
    "RefillDueRequest",
    "RefillDueResponse",
    "ReserveChargeResponse",
    "SubscriptionCreateRequest",
    "SubscriptionProrationResponse",
    "SubscriptionResponse",
    "TopupConfirmRequest",
    "TopupCreateRequest",
    "TopupResponse",
    "WarningResponse",
    "validate_idempotency_key",
]
