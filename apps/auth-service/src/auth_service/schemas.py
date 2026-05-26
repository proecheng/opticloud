"""Pydantic request/response schemas for auth endpoints."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

PHONE_PATTERN = re.compile(r"^\+\d{6,15}$")  # E.164 international format


# ===== signup =====


class SignupRequest(BaseModel):
    """FR A1 signup request body."""

    phone: str = Field(..., description="E.164 phone number (e.g. +8613800138000)")
    email: EmailStr = Field(..., description="Valid email address")
    age: int = Field(
        ...,
        ge=0,
        le=120,
        strict=True,
        description="User age in years. 14-18 requires guardian_email; <14 is rejected.",
    )
    guardian_email: EmailStr | None = Field(
        default=None,
        description="Required for ages 14-18 inclusive.",
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not PHONE_PATTERN.match(v):
            raise ValueError("phone must be E.164 format (e.g. +8613800138000)")
        return v


class SignupResponse(BaseModel):
    """FR A1 signup response."""

    account_status: Literal["verified", "pending_guardian_confirmation"]
    user_id: uuid.UUID
    jwt_access: str | None = None
    jwt_refresh: str | None = None
    edu_tier: bool = Field(default=False, description="FR A4 .edu/.ac.cn auto-detected")
    age_verified: bool
    guardian_email: EmailStr | None = None
    guardian_confirmation_url: str | None = None


class AuthTokenResponse(BaseModel):
    """Verified auth response shape shared by login and adult signup."""

    account_status: Literal["verified"]
    user_id: uuid.UUID
    jwt_access: str
    jwt_refresh: str
    edu_tier: bool = Field(default=False, description="FR A4 .edu/.ac.cn auto-detected")
    age_verified: Literal[True] = True


# ===== Story 1.2: login (OTP 2FA) =====


class OTPRequestBody(BaseModel):
    """POST /v1/auth/otp/request body."""

    phone: str = Field(..., description="E.164 phone (e.g. +8613800138000)")
    email: EmailStr

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        if not PHONE_PATTERN.match(v):
            raise ValueError("phone must be E.164 format (e.g. +8613800138000)")
        return v


class OTPRequestResponse(BaseModel):
    """POST /v1/auth/otp/request response.

    `dev_phone_otp` / `dev_email_otp` populated only when
    OTP_DEV_MODE_RETURN=true (default in `.env.example` for local dev).
    Production sets the env to false; codes only reach operators via logs.
    """

    expires_in_seconds: int = 300
    factors: list[Literal["phone", "email"]]
    dev_phone_otp: str | None = None
    dev_email_otp: str | None = None


class LoginRequest(OTPRequestBody):
    """POST /v1/auth/login body — phone + email + 2 OTP codes."""

    phone_otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    email_otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


# LoginResponse shares the SignupResponse shape (same JWT pair + edu_tier).
# Distinct subclass keeps OpenAPI schemas separate per A1 architect review.
class LoginResponse(AuthTokenResponse):
    """POST /v1/auth/login response — verified token response."""


class GuardianConfirmationRequest(BaseModel):
    """POST /v1/auth/guardian-confirmation/confirm body."""

    token: str = Field(..., min_length=16, max_length=512)


class GuardianConfirmationResponse(BaseModel):
    """Guardian confirmation verification response."""

    confirmation_status: Literal["confirmed", "already_confirmed"]
    account_status: Literal["verified"] = "verified"
    user_id: uuid.UUID
    guardian_email: EmailStr
    age_verified: Literal[True] = True
    confirmed_at: datetime


# ===== Story 1.6: account deletion =====


class AccountDeletionStatusResponse(BaseModel):
    """Authenticated account deletion status."""

    status: Literal["none", "scheduled", "completed"]
    user_id_snapshot: uuid.UUID | None = None
    requested_at: datetime | None = None
    hard_delete_at: datetime | None = None
    completed_at: datetime | None = None
    grace_period_days: int = 7


# ===== api_keys =====

VALID_SCOPES = {
    "optimize:read",
    "optimize:write",
    "predict:read",
    "predict:write",
    "chat:read",
    "chat:write",
    "billing:read",
    "reproduce:read",
}


class APIKeyCreateRequest(BaseModel):
    """FR A2 api_keys.create body.

    Story 1.3: `expires_in_days` is a convenience that resolves server-side to
    `expires_at = NOW + days`. Sending both → 422.
    """

    label: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    scope: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, v: list[str]) -> list[str]:
        invalid = set(v) - VALID_SCOPES
        if invalid:
            raise ValueError(f"invalid scopes: {invalid}; allowed: {sorted(VALID_SCOPES)}")
        return v

    @model_validator(mode="after")
    def _resolve_expiration(self) -> APIKeyCreateRequest:
        if self.expires_in_days is not None and self.expires_at is not None:
            raise ValueError("set either expires_at OR expires_in_days, not both")
        if self.expires_in_days is not None:
            self.expires_at = datetime.now(UTC) + timedelta(days=self.expires_in_days)
        return self


class APIKeyCreateResponse(BaseModel):
    """FR A2 api_keys.create response (full key returned ONCE)."""

    id: uuid.UUID
    api_key: str = Field(
        ..., description="Full key, e.g. 'sk-XXXXX...' — copy now, never shown again"
    )
    prefix: str = Field(..., description="First 6 chars visible for identification")
    hash_preview: str = Field(..., description="SHA256 hash preview (debugging)")
    label: str
    scope: list[str]
    expires_at: datetime | None
    created_at: datetime


class APIKeyRiskGeo(BaseModel):
    code: str
    label_zh: str


class APIKeyRiskWarning(BaseModel):
    risk_score: float
    detected_at: datetime
    previous_geo: APIKeyRiskGeo
    current_geo: APIKeyRiskGeo
    previous_ip: str
    current_ip: str
    reason: str


class APIKeyListItem(BaseModel):
    """FR A2 api_keys list item."""

    id: uuid.UUID
    prefix: str
    label: str
    description: str | None
    scope: list[str]
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    risk_warning: APIKeyRiskWarning | None = None


# ===== Story 1.12: risk freeze appeals =====

AppealStatus = Literal["pending", "approved", "rejected", "merge_offered", "merge_accepted"]
AppealReviewMode = Literal["auto_score", "manual_48h"]
AppealDecision = Literal["approved", "maintained", "rejected", "merge_accepted"]

ALLOWED_APPEAL_EVIDENCE_KEYS = {
    "team_context",
    "shared_device",
    "roommate_registration",
    "business_reason",
    "contact_note",
}


class RiskAppealSubmitRequest(BaseModel):
    phone: str = Field(..., description="E.164 phone for the frozen account")
    email: EmailStr
    reason: str = Field(..., min_length=10, max_length=2000)
    evidence: dict[str, str] = Field(default_factory=dict)
    team_size: int = Field(..., ge=1, le=500)

    @field_validator("phone")
    @classmethod
    def _validate_appeal_phone(cls, v: str) -> str:
        if not PHONE_PATTERN.match(v):
            raise ValueError("phone must be E.164 format (e.g. +8613800138000)")
        return v

    @field_validator("evidence")
    @classmethod
    def _validate_evidence(cls, v: dict[str, str]) -> dict[str, str]:
        invalid = set(v) - ALLOWED_APPEAL_EVIDENCE_KEYS
        if invalid:
            raise ValueError(
                "invalid evidence keys: "
                f"{sorted(invalid)}; allowed: {sorted(ALLOWED_APPEAL_EVIDENCE_KEYS)}"
            )
        for key, value in v.items():
            if not isinstance(value, str):
                raise ValueError(f"evidence.{key} must be a string")
            if len(value) > 500:
                raise ValueError(f"evidence.{key} must be <= 500 characters")
        return v


class RiskEvidenceSummary(BaseModel):
    rule_code: str
    label_zh: str
    source: str
    created_at: datetime
    summary: str | None = None


class RiskMergeOffer(BaseModel):
    offer_type: Literal["keep_one_account"]
    title: str
    description: str
    next_action: Literal["accept_merge_to_resume"]


class RiskAppealSubmitResponse(BaseModel):
    appeal_id: uuid.UUID
    status: AppealStatus
    review_mode: AppealReviewMode
    submitted_at: datetime
    sla_due_at: datetime | None
    tracking_url: str
    merge_offer: RiskMergeOffer | None = None


class RiskAppealStatusResponse(BaseModel):
    appeal_id: uuid.UUID
    status: AppealStatus
    review_mode: AppealReviewMode
    submitted_at: datetime
    sla_due_at: datetime | None
    decided_at: datetime | None
    decision: AppealDecision | None
    decision_reason: str | None
    evidence_summary: list[RiskEvidenceSummary]
    merge_offer: RiskMergeOffer | None = None
    next_action_url: str | None = None


class RiskAppealMergeAcceptRequest(BaseModel):
    token: str = Field(..., min_length=16, max_length=512)


class RiskAppealMergeAcceptResponse(BaseModel):
    appeal_id: uuid.UUID
    status: Literal["merge_accepted"]
    decision: Literal["merge_accepted"]
    is_frozen: Literal[False]
    next_action_url: str


class AdminRiskAppealDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(..., min_length=1, max_length=1000)


class AdminRiskAppealItem(BaseModel):
    appeal_id: uuid.UUID
    user_id: uuid.UUID
    status: AppealStatus
    review_mode: AppealReviewMode
    team_size: int
    submitted_at: datetime
    sla_due_at: datetime | None
    decided_at: datetime | None


class AdminRiskAppealDetail(AdminRiskAppealItem):
    reason: str
    evidence: dict[str, str]
    decision: AppealDecision | None
    decision_reason: str | None
    evidence_summary: list[RiskEvidenceSummary]
    merge_offer: RiskMergeOffer | None = None
