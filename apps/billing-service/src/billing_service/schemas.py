"""Pydantic schemas for billing-service HTTP API (Story 5.A.1)."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from billing_service.topups import normalize_topup_amount

_IDEMPOTENCY_KEY_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_POINTER_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


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


class AutoRefundRequest(BaseModel):
    """POST /v1/billing/charges/{id}/refund-auto body — Story 5.C.1."""

    reason: Literal["failed", "cancelled", "infeasible"]
    source: str = Field(
        default="solver_orchestrator",
        min_length=1,
        max_length=64,
        pattern=_POINTER_REF_RE.pattern,
        description="Trusted detector label; pointer only, never a raw payload",
    )
    source_ref: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=_POINTER_REF_RE.pattern,
        description="Downstream task/status pointer; never a raw payload",
    )
    elapsed_seconds: float | None = Field(default=None, ge=0)


class AutoRefundResponse(BaseModel):
    """Automatic refund result — Story 5.C.1."""

    charge_id: str
    current_state: str
    refund_mode: Literal["reserved_net_zero", "charged_rollback"]
    reserved_amount: str
    refunded_amount: str
    balance_before: str
    balance_after: str
    currency: str = "CNY"


class UserCancelRefundRequest(BaseModel):
    """POST /v1/billing/charges/{id}/refund-user-cancel body — Story 5.C.2."""

    source: str = Field(
        default="solver_orchestrator",
        min_length=1,
        max_length=64,
        pattern=_POINTER_REF_RE.pattern,
        description="Trusted cancellation source label; pointer only",
    )
    source_ref: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=_POINTER_REF_RE.pattern,
        description="Optimization/task pointer; never a raw payload",
    )
    elapsed_seconds: float | None = Field(default=None, ge=0)


class UserCancelRefundResponse(BaseModel):
    """User-initiated cancel refund result — Story 5.C.2."""

    charge_id: str
    current_state: str
    refund_mode: Literal["reserved_net_zero", "charged_rollback"]
    reserved_amount: str
    refunded_amount: str
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


class BilingualText(BaseModel):
    """Small bilingual label used by invoice responses."""

    zh: str
    en: str


class InvoiceSubscriptionResponse(BaseModel):
    """Subscription snapshot shown on a billing statement."""

    plan_code: str
    plan_label: str
    plan_label_zh: str
    status: str
    current_period_start: datetime | None
    current_period_end: datetime | None


class InvoiceLineItemResponse(BaseModel):
    """One safe ledger-derived billing statement row."""

    id: str
    created_at: datetime
    kind: str
    bucket: str
    label: BilingualText
    direction: Literal["credit", "debit"]
    direction_label: BilingualText
    amount: str
    source_amount: str
    currency: str = "CNY"
    details: dict[str, str] = Field(default_factory=dict)


class InvoiceUsageSummaryResponse(BaseModel):
    """Invoice-scoped usage summary; not the full Story 5.D.2 dashboard contract."""

    window_days: Literal[7, 30]
    actual_spend: str
    currency: str = "CNY"
    label: BilingualText


class InvoiceSummaryResponse(BaseModel):
    """One row returned by GET /v1/billing/invoices."""

    period: str
    period_start: datetime
    period_end: datetime
    status: Literal["final", "provisional"]
    status_label: BilingualText
    net_credit_movement: str
    actual_spend: str
    currency: str = "CNY"
    line_item_count: int


class InvoiceListResponse(BaseModel):
    """GET /v1/billing/invoices response."""

    items: list[InvoiceSummaryResponse]


class InvoiceResponse(InvoiceSummaryResponse):
    """GET /v1/billing/invoices/{period} response."""

    title: BilingualText
    tax_disclaimer: BilingualText
    owner_user_id_suffix: str
    subscription: InvoiceSubscriptionResponse
    credit_subtotal: str
    debit_subtotal: str
    trend_contract: Literal["invoice_summary"]
    usage_summary: list[InvoiceUsageSummaryResponse]
    line_items: list[InvoiceLineItemResponse]


class UsageTrendPointResponse(BaseModel):
    """One UTC daily point in the reusable billing usage trend contract."""

    date: date
    actual_spend: str
    currency: str = "CNY"


class UsageTrendWindowResponse(BaseModel):
    """One 7d or 30d usage-spend trend window."""

    window_days: Literal[7, 30]
    window_start: datetime
    window_end: datetime
    label: BilingualText
    currency: str = "CNY"
    total_actual_spend: str
    average_daily_spend: str
    points: list[UsageTrendPointResponse]


class UsageTrendsResponse(BaseModel):
    """GET /v1/billing/usage-trends response."""

    trend_contract: Literal["billing_usage_trends_v1"]
    generated_at: datetime
    windows: list[UsageTrendWindowResponse]


class BudgetUpdateRequest(BaseModel):
    """PUT /v1/billing/budget body — Story 5.D.5."""

    model_config = ConfigDict(extra="forbid")

    monthly_budget_amount: Decimal | None = Field(
        default=None,
        description='Monthly CNY budget as a string, e.g. "100.00"',
    )
    enabled: bool = True

    @field_validator("monthly_budget_amount", mode="before")
    @classmethod
    def _coerce_amount(cls, v: object) -> Decimal | None:
        if v is None:
            return None
        try:
            amount = Decimal(str(v)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("monthly_budget_amount must be a decimal CNY amount") from exc
        if amount < Decimal("1.00") or amount > Decimal("9999999.99"):
            raise ValueError("monthly_budget_amount must be between 1.00 and 9999999.99")
        return amount

    @model_validator(mode="after")
    def _require_amount_when_enabled(self) -> BudgetUpdateRequest:
        if self.enabled and self.monthly_budget_amount is None:
            raise ValueError("monthly_budget_amount is required when enabled=true")
        return self


class BudgetEventSummaryResponse(BaseModel):
    """Safe, compact monthly budget event summary."""

    id: str
    event_type: Literal[
        "billing.budget.configured",
        "billing.budget.disabled",
        "billing.budget.alerted",
        "billing.budget.paused",
    ]
    period_start: datetime
    period_end: datetime
    occurred_at: datetime
    budget_amount: str
    actual_spend: str
    percent_used: str
    channels: list[Literal["email", "in_app"]] = Field(default_factory=list)


class BudgetStatusResponse(BaseModel):
    """GET/PUT /v1/billing/budget response."""

    budget_control_id: str | None
    enabled: bool
    status: Literal["not_configured", "disabled", "active", "paused"]
    monthly_budget_amount: str | None
    alert_threshold_ratio: str
    period_start: datetime
    period_end: datetime
    actual_spend: str
    percent_used: str
    currency: str = "CNY"
    alert_threshold_reached: bool
    paused: bool
    paused_at: datetime | None = None
    pause_period_start: datetime | None = None
    recent_events: list[BudgetEventSummaryResponse] = Field(default_factory=list)


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
    "AutoRefundRequest",
    "AutoRefundResponse",
    "BalanceResponse",
    "BudgetEventSummaryResponse",
    "BudgetStatusResponse",
    "BudgetUpdateRequest",
    "BucketBalance",
    "ChargeCreateRequest",
    "ChargeResponse",
    "EduStarterSyncRequest",
    "EstimateRequest",
    "EstimateResponse",
    "FinalizeChargeRequest",
    "FinalizeChargeResponse",
    "InvoiceLineItemResponse",
    "InvoiceListResponse",
    "InvoiceResponse",
    "InvoiceSubscriptionResponse",
    "InvoiceSummaryResponse",
    "InvoiceUsageSummaryResponse",
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
    "UsageTrendPointResponse",
    "UsageTrendWindowResponse",
    "UsageTrendsResponse",
    "UserCancelRefundRequest",
    "UserCancelRefundResponse",
    "WarningResponse",
    "validate_idempotency_key",
]
