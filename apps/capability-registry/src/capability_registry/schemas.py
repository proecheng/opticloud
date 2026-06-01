"""Pydantic schemas for capability-registry."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

ProviderKind = Literal["self", "open_source", "external", "commercial"]
ProviderApplicationKind = Literal["external", "commercial"]
ProviderStatus = Literal["active", "inactive", "deprecated"]
CapabilityStatus = Literal["v1", "v1_late", "v2", "audited", "shadow"]
OAuthFlowStatus = Literal["draft", "configured", "disabled"]
RevenueSharePolicyStatus = Literal["reserved", "active", "deprecated"]
RevenueShareHookStatus = Literal["reserved", "captured", "voided"]
ProviderApplicationStatus = Literal["draft", "submitted"]
ProviderEvaluationStatus = Literal["requested", "queued", "cancelled"]
ScopeSource = Literal["global", "tenant", "global_fallback"]

_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{0,63}$"
_BENCHMARK_SUITE_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"
_SOURCE_SERVICE_PATTERN = r"^[a-z0-9][a-z0-9-]{0,63}$"
_TIER_PATTERN = r"^(T[1-6]|P[1-5])$"
_PERIOD_MONTH_PATTERN = r"^[0-9]{4}-(0[1-9]|1[0-2])$"
_HTTP_URL_PATTERN = re.compile(r"^https?://")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_REF_PATTERN = re.compile(r"^(s3|oss|fixture|benchmark|repro)://")
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_DIGEST_PATTERN = re.compile(r"sha256:[0-9a-fA-F]{64}")
_TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_RATIO_QUANT = Decimal("0.000001")
_FORBIDDEN_REFERENCE_FIELDS = {
    "api_key",
    "bank_account",
    "access_token",
    "client_secret",
    "docker_password",
    "email",
    "email_body",
    "jwt",
    "password",
    "phone",
    "provider_secret",
    "raw_body",
    "raw_dataset",
    "refresh_token",
    "registry_password",
    "secret",
    "tax_id",
    "token",
}
_FORBIDDEN_REVENUE_SHARE_FIELDS = _FORBIDDEN_REFERENCE_FIELDS | {
    "provider_amount",
    "platform_amount",
    "payout_status",
    "paid_at",
    "settlement_id",
    "payment_account",
    "payment_ref",
    "raw_billing_payload",
}


def normalize_tag(value: str) -> str:
    """Normalize a future capability vocabulary tag."""
    normalized = value.strip().lower().replace(" ", "_")
    normalized = re.sub(r"[^a-z0-9_-]+", "_", normalized)
    normalized = re.sub(r"[_-]{2,}", "_", normalized).strip("_-")
    if not normalized or not _TAG_PATTERN.match(normalized):
        raise ValueError("tag must normalize to [a-z0-9][a-z0-9_-]{0,63}")
    return normalized


class ModelVersion(BaseModel):
    """Public model_version parity with solver-orchestrator."""

    provider_id: str = Field(..., pattern=_ID_PATTERN)
    kind: ProviderKind
    version: str = Field(..., min_length=1, max_length=64)
    provider_url: str = Field(..., min_length=1)


class ProviderUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID | None = None
    provider_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    kind: ProviderKind
    display_name: str = Field(..., min_length=1, max_length=120)
    provider_url: str = Field(..., min_length=1)
    status: ProviderStatus = "active"
    openapi_url: str | None = None
    openapi_sha256: str | None = None
    image_digest: str | None = None
    cosign_bundle: dict[str, Any] = Field(default_factory=dict)

    @field_validator("openapi_sha256")
    @classmethod
    def validate_openapi_sha256(cls, value: str | None) -> str | None:
        if value is not None and not _SHA256_PATTERN.match(value):
            raise ValueError("openapi_sha256 must be 64 hex characters")
        return value

    @field_validator("image_digest")
    @classmethod
    def validate_image_digest(cls, value: str | None) -> str | None:
        if value is not None and not _DIGEST_PATTERN.search(value):
            raise ValueError("image_digest must include sha256:<64 hex>")
        return value


class ProviderResponse(ProviderUpsertRequest):
    id: uuid.UUID
    provider_id: str = Field(..., pattern=_ID_PATTERN)
    scope_source: ScopeSource
    created_at: datetime
    updated_at: datetime


class CapabilityUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID | None = None
    k_algo: str | None = Field(default=None, pattern=_ID_PATTERN)
    task_type: str = Field(..., min_length=1, max_length=64)
    tier: str = Field(..., pattern=_TIER_PATTERN)
    status: CapabilityStatus
    provider_id: str = Field(..., pattern=_ID_PATTERN)
    model_version: str = Field(..., min_length=1, max_length=64)
    supported_solvers: list[str] = Field(..., min_length=1, max_length=20)
    description_zh: str = Field(..., min_length=1)
    description_en: str = Field(..., min_length=1)
    examples: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    @field_validator("supported_solvers")
    @classmethod
    def validate_supported_solvers(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for solver in value:
            stripped = solver.strip()
            if not stripped:
                raise ValueError("supported_solvers cannot contain blank values")
            if stripped not in normalized:
                normalized.append(stripped)
        return normalized

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            tag = normalize_tag(item)
            if tag not in normalized:
                normalized.append(tag)
        return normalized


class CapabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    k_algo: str = Field(..., pattern=_ID_PATTERN)
    task_type: str = Field(..., min_length=1, max_length=64)
    tier: str = Field(..., pattern=_TIER_PATTERN)
    status: CapabilityStatus
    provider_id: str = Field(..., pattern=_ID_PATTERN)
    model_version: ModelVersion
    supported_solvers: list[str]
    description_zh: str
    description_en: str
    examples: list[dict[str, Any]]
    metadata: dict[str, Any]
    tags: list[str]
    scope_source: ScopeSource
    created_at: datetime
    updated_at: datetime


class OAuthFlowUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID | None = None
    provider_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    authorization_url: str = Field(..., min_length=1)
    token_url: str = Field(..., min_length=1)
    scopes: list[str] = Field(default_factory=list)
    status: OAuthFlowStatus = "draft"
    client_id_ref: str = Field(..., min_length=1)
    client_secret_ref: str | None = None
    vault_secret_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def reject_raw_oauth_secret_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            forbidden = {"client_secret", "access_token", "refresh_token", "authorization_code"}
            present = sorted(forbidden.intersection(data))
            if present:
                raise ValueError(f"raw OAuth fields are not allowed: {', '.join(present)}")
        return data

    @field_validator("scopes")
    @classmethod
    def normalize_scopes(cls, value: list[str]) -> list[str]:
        scopes: list[str] = []
        for scope in value:
            stripped = scope.strip()
            if not stripped:
                raise ValueError("scopes cannot contain blank values")
            if stripped not in scopes:
                scopes.append(stripped)
        return scopes


class OAuthFlowResponse(OAuthFlowUpsertRequest):
    id: uuid.UUID
    provider_id: str = Field(..., pattern=_ID_PATTERN)
    scope_source: ScopeSource
    created_at: datetime
    updated_at: datetime


def _reject_forbidden_revenue_share_fields(data: Any) -> None:
    if isinstance(data, dict):
        present = sorted(key for key in data if str(key).lower() in _FORBIDDEN_REVENUE_SHARE_FIELDS)
        if present:
            raise ValueError(f"computed payout or credential fields are not allowed: {present}")
        for value in data.values():
            _reject_forbidden_revenue_share_fields(value)
    elif isinstance(data, list):
        for item in data:
            _reject_forbidden_revenue_share_fields(item)


def _reject_forbidden_reference_fields(data: Any) -> None:
    if isinstance(data, dict):
        present = sorted(key for key in data if _is_forbidden_reference_key(str(key)))
        if present:
            raise ValueError(f"credential or raw payload fields are not allowed: {present}")
        for value in data.values():
            _reject_forbidden_reference_fields(value)
    elif isinstance(data, list):
        for item in data:
            _reject_forbidden_reference_fields(item)


def _is_forbidden_reference_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")
    compact = normalized.replace("_", "")
    if normalized in _FORBIDDEN_REFERENCE_FIELDS:
        return True
    return any(
        marker in compact
        for marker in (
            "apikey",
            "password",
            "clientsecret",
            "accesstoken",
            "refreshtoken",
            "registrypassword",
            "dockerpassword",
            "bankaccount",
            "taxid",
            "email",
            "phone",
            "rawdataset",
            "rawbody",
            "jwt",
            "secret",
            "token",
        )
    )


def _validate_http_url(value: str | None, *, field_name: str) -> str | None:
    if value is not None and not _HTTP_URL_PATTERN.match(value):
        raise ValueError(f"{field_name} must start with http:// or https://")
    return value


def _validate_reference(value: str, *, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} cannot be blank")
    if len(stripped) > 256:
        raise ValueError(f"{field_name} must be at most 256 characters")
    if not _REF_PATTERN.match(stripped):
        raise ValueError(f"{field_name} must start with an allowed reference prefix")
    return stripped


def _normalize_ratio(value: Decimal) -> Decimal:
    if value < 0 or value > 1:
        raise ValueError("ratio must be between 0 and 1")
    return value.quantize(_RATIO_QUANT)


class RevenueSharePolicyUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID | None = None
    policy_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    provider_kind: ProviderKind
    platform_share_ratio: Decimal = Field(..., max_digits=7, decimal_places=6)
    provider_share_ratio: Decimal = Field(..., max_digits=7, decimal_places=6)
    status: RevenueSharePolicyStatus = "reserved"
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def reject_payout_fields(cls, data: Any) -> Any:
        _reject_forbidden_revenue_share_fields(data)
        return data

    @field_validator("platform_share_ratio", "provider_share_ratio")
    @classmethod
    def validate_ratio(cls, value: Decimal) -> Decimal:
        return _normalize_ratio(value)

    @model_validator(mode="after")
    def validate_policy(self) -> RevenueSharePolicyUpsertRequest:
        if self.platform_share_ratio + self.provider_share_ratio != Decimal("1.000000"):
            raise ValueError("platform_share_ratio + provider_share_ratio must equal 1.000000")
        if (
            self.effective_from is not None
            and self.effective_until is not None
            and self.effective_until <= self.effective_from
        ):
            raise ValueError("effective_until must be after effective_from")
        return self


class RevenueSharePolicyResponse(RevenueSharePolicyUpsertRequest):
    id: uuid.UUID
    policy_id: str = Field(..., pattern=_ID_PATTERN)
    scope_source: ScopeSource
    created_at: datetime
    updated_at: datetime

    @field_serializer("platform_share_ratio", "provider_share_ratio")
    def serialize_ratio(self, value: Decimal) -> str:
        return f"{value.quantize(_RATIO_QUANT):.6f}"


class RevenueShareHookCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID | None = None
    provider_id: str = Field(..., pattern=_ID_PATTERN)
    k_algo: str = Field(..., pattern=_ID_PATTERN)
    policy_id: str = Field(..., pattern=_ID_PATTERN)
    source_service: str = Field(..., pattern=_SOURCE_SERVICE_PATTERN)
    source_event_id: uuid.UUID
    billing_saga_id: uuid.UUID | None = None
    billing_ledger_id: uuid.UUID | None = None
    period_month: str = Field(..., pattern=_PERIOD_MONTH_PATTERN)
    gross_amount_ref: str | None = Field(default=None, max_length=128)
    currency: str = Field(default="CNY", pattern=r"^[A-Z]{3}$")
    status: RevenueShareHookStatus = "reserved"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def reject_payout_fields(cls, data: Any) -> Any:
        _reject_forbidden_revenue_share_fields(data)
        return data


class RevenueShareHookResponse(RevenueShareHookCreateRequest):
    id: uuid.UUID
    scope_source: ScopeSource
    created_at: datetime


class ProviderApplicationUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID | None = None
    application_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    requested_provider_id: str = Field(..., pattern=_ID_PATTERN)
    provider_kind: ProviderApplicationKind
    display_name: str = Field(..., min_length=1, max_length=120)
    organization_name: str = Field(..., min_length=1, max_length=160)
    contact_email: str = Field(..., min_length=3, max_length=254)
    homepage_url: str | None = None
    openapi_url: str = Field(..., min_length=1)
    openapi_sha256: str = Field(..., pattern=r"^[0-9a-fA-F]{64}$")
    image_digest: str = Field(..., min_length=1)
    cosign_bundle: dict[str, Any] = Field(default_factory=dict)
    evaluation_profile: dict[str, Any] = Field(default_factory=dict)
    status: ProviderApplicationStatus = "draft"
    submitted_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("contact_email")
    @classmethod
    def validate_contact_email(cls, value: str) -> str:
        if not _EMAIL_PATTERN.match(value):
            raise ValueError("contact_email must be a valid email-like address")
        return value

    @field_validator("homepage_url")
    @classmethod
    def validate_homepage_url(cls, value: str | None) -> str | None:
        return _validate_http_url(value, field_name="homepage_url")

    @field_validator("openapi_url")
    @classmethod
    def validate_openapi_url(cls, value: str) -> str:
        return str(_validate_http_url(value, field_name="openapi_url"))

    @field_validator("image_digest")
    @classmethod
    def validate_application_image_digest(cls, value: str) -> str:
        if not _DIGEST_PATTERN.search(value):
            raise ValueError("image_digest must include sha256:<64 hex>")
        return value

    @field_validator("cosign_bundle", "evaluation_profile", "metadata")
    @classmethod
    def validate_reference_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        _reject_forbidden_reference_fields(value)
        return value


class ProviderApplicationResponse(ProviderApplicationUpsertRequest):
    id: uuid.UUID
    application_id: str = Field(..., pattern=_ID_PATTERN)
    scope_source: ScopeSource
    created_at: datetime
    updated_at: datetime


class ProviderEvaluationUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID | None = None
    application_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    evaluation_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    benchmark_suite: str = Field(..., pattern=_BENCHMARK_SUITE_PATTERN)
    sample_count: int = Field(..., ge=1, le=500)
    timeout_seconds: int = Field(..., ge=1, le=60)
    status: ProviderEvaluationStatus = "requested"
    dataset_refs: list[str] = Field(..., min_length=1)
    report_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def reject_requested_provider_id(cls, data: Any) -> Any:
        if isinstance(data, dict) and "requested_provider_id" in data:
            raise ValueError("requested_provider_id is derived from the application")
        return data

    @field_validator("dataset_refs")
    @classmethod
    def validate_dataset_refs(cls, value: list[str]) -> list[str]:
        refs: list[str] = []
        for item in value:
            ref = _validate_reference(item, field_name="dataset_refs")
            if ref not in refs:
                refs.append(ref)
        return refs

    @field_validator("report_ref")
    @classmethod
    def validate_report_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_reference(value, field_name="report_ref")

    @field_validator("metadata")
    @classmethod
    def validate_evaluation_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        _reject_forbidden_reference_fields(value)
        return value


class ProviderEvaluationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    application_id: str = Field(..., pattern=_ID_PATTERN)
    evaluation_id: str = Field(..., pattern=_ID_PATTERN)
    requested_provider_id: str = Field(..., pattern=_ID_PATTERN)
    benchmark_suite: str = Field(..., pattern=_BENCHMARK_SUITE_PATTERN)
    sample_count: int = Field(..., ge=1, le=500)
    timeout_seconds: int = Field(..., ge=1, le=60)
    status: ProviderEvaluationStatus
    dataset_refs: list[str]
    report_ref: str | None = None
    metadata: dict[str, Any]
    scope_source: ScopeSource
    created_at: datetime
    updated_at: datetime
