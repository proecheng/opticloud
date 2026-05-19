"""Pydantic schemas for billing-service HTTP API (Story 5.A.1)."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

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
    Story 5.A.4 — added max_solve_seconds so finalize can cap actual amount.
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


class BalanceResponse(BaseModel):
    """GET /v1/billing/balance response."""

    user_id: str
    balance: str  # Decimal as str
    currency: str = "CNY"
    last_transaction_at: datetime | None = None


__all__ = [
    "BalanceResponse",
    "ChargeCreateRequest",
    "ChargeResponse",
    "EstimateRequest",
    "EstimateResponse",
    "FinalizeChargeRequest",
    "FinalizeChargeResponse",
    "ReserveChargeResponse",
    "WarningResponse",
    "validate_idempotency_key",
]
