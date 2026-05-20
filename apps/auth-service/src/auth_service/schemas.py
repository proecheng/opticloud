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

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not PHONE_PATTERN.match(v):
            raise ValueError("phone must be E.164 format (e.g. +8613800138000)")
        return v


class SignupResponse(BaseModel):
    """FR A1 signup response."""

    user_id: uuid.UUID
    jwt_access: str
    jwt_refresh: str
    edu_tier: bool = Field(default=False, description="FR A4 .edu/.ac.cn auto-detected")


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
class LoginResponse(SignupResponse):
    """POST /v1/auth/login response — same shape as SignupResponse."""


# ===== Story 1.6: account deletion =====


class AccountDeletionStatusResponse(BaseModel):
    """Authenticated account deletion status."""

    status: Literal["none", "scheduled", "completed"]
    user_id_snapshot: uuid.UUID | None = None
    requested_at: datetime | None = None
    hard_delete_at: datetime | None = None
    completed_at: datetime | None = None
    grace_period_days: int = 7


# ===== Story 1.7: account merge proposals =====


class AccountMergeEvidence(BaseModel):
    """Evidence collected for FR A7 account-merge review."""

    reason: str = Field(..., min_length=4, max_length=500)
    contact_email: EmailStr
    supporting_note: str | None = Field(default=None, max_length=1000)
    team_size: int | None = Field(default=None, ge=1, le=50)


class AccountMergeProposalCreateRequest(BaseModel):
    primary_user_id: uuid.UUID
    duplicate_user_ids: list[uuid.UUID] = Field(..., min_length=1)
    evidence: AccountMergeEvidence

    @field_validator("duplicate_user_ids")
    @classmethod
    def validate_duplicate_user_ids(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(v)) != len(v):
            raise ValueError("duplicate_user_ids must be unique")
        return v

    @model_validator(mode="after")
    def validate_primary_not_duplicate(self) -> AccountMergeProposalCreateRequest:
        if self.primary_user_id in self.duplicate_user_ids:
            raise ValueError("duplicate_user_ids must not include primary_user_id")
        return self


class AccountMergeProposalResponse(BaseModel):
    id: uuid.UUID
    requester_user_id: uuid.UUID
    primary_user_id: uuid.UUID
    duplicate_user_ids: list[uuid.UUID]
    evidence: dict[str, object]
    status: Literal[
        "pending_review",
        "approved",
        "rejected",
        "auto_approved",
        "accepted",
        "cancelled",
    ]
    review_mode: Literal["human", "auto"]
    auto_score: float | None
    review_due_at: datetime
    reviewed_at: datetime | None
    reviewed_by: str | None
    decision_reason: str | None
    accepted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    next_action: str


class AccountMergeAdminReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(..., min_length=1, max_length=1000)


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
