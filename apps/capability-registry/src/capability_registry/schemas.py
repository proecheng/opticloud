"""Pydantic schemas for capability-registry."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
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
ProviderRevenuePayoutEntryStatus = Literal["pending", "held", "paid", "voided"]
ProviderApplicationStatus = Literal["draft", "submitted"]
ProviderEvaluationStatus = Literal["requested", "queued", "cancelled"]
ProviderVersionChangeKind = Literal["patch", "minor", "major"]
ProviderVersionUpdateStatus = Literal[
    "draft",
    "submitted",
    "under_review",
    "approved",
    "rejected",
    "cancelled",
]
ProviderShadowRunStatus = Literal["draft", "running", "passed", "failed", "cancelled"]
ProviderShadowRunUpsertStatus = Literal["draft", "running", "cancelled"]
ProviderShadowCoverageClass = Literal[
    "platform_standard",
    "provider_supplied",
    "adversarial",
    "desensitized_real",
]
ProviderRolloutStatus = Literal["draft", "active", "paused", "completed", "cancelled"]
ProviderRolloutStage = Literal[0, 5, 50, 100]
ProviderRouteShareAction = Literal["created", "advance", "pause", "cancel"]
ScopeSource = Literal["global", "tenant", "global_fallback"]
ProviderDashboardScopeSource = Literal["global", "tenant"]
ProviderRouteShareScopeSource = ProviderDashboardScopeSource

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
_SEMVER_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_RATIO_QUANT = Decimal("0.000001")
_MONEY_QUANT = Decimal("0.0001")
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
    "provider_request",
    "provider_response",
    "raw_body",
    "raw_dataset",
    "raw_request",
    "raw_response",
    "refresh_token",
    "registry_password",
    "routing_payload",
    "secret",
    "tax_id",
    "token",
    "customer_payload",
}
_FORBIDDEN_REVENUE_SHARE_FIELDS = _FORBIDDEN_REFERENCE_FIELDS | {
    "provider_amount",
    "platform_amount",
    "payout_status",
    "provider_revenue_amount",
    "paid_at",
    "pending_payout_amount",
    "platform_revenue_amount",
    "settlement_id",
    "payment_account",
    "payment_ref",
    "raw_billing_payload",
}

_FORBIDDEN_REVENUE_SHARE_MARKERS = tuple(
    key.replace("_", "") for key in _FORBIDDEN_REVENUE_SHARE_FIELDS
)


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
        present = sorted(key for key in data if _is_forbidden_revenue_share_key(str(key)))
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
            "rawrequest",
            "rawresponse",
            "providerrequest",
            "providerresponse",
            "routingpayload",
            "customerpayload",
            "rawbody",
            "jwt",
            "secret",
            "token",
        )
    )


def _is_forbidden_revenue_share_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")
    compact = normalized.replace("_", "")
    if normalized in _FORBIDDEN_REVENUE_SHARE_FIELDS:
        return True
    return compact in _FORBIDDEN_REVENUE_SHARE_MARKERS or _is_forbidden_reference_key(key)


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


def normalize_money(value: Decimal) -> Decimal:
    if value < 0:
        raise ValueError("amount must be non-negative")
    return value.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)


def provider_revenue_amount(gross_amount: Decimal, provider_share_ratio: Decimal) -> Decimal:
    return normalize_money(gross_amount * provider_share_ratio)


def platform_revenue_amount(gross_amount: Decimal, provider_amount: Decimal) -> Decimal:
    return normalize_money(gross_amount - provider_amount)


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


class ProviderRevenuePayoutEntryUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID | None = None
    entry_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    hook_id: uuid.UUID
    gross_amount: Decimal = Field(..., max_digits=12, decimal_places=4)
    currency: str = Field(default="CNY", pattern=r"^[A-Z]{3}$")
    recognized_at: datetime
    status: ProviderRevenuePayoutEntryStatus = "pending"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def reject_payout_fields(cls, data: Any) -> Any:
        _reject_forbidden_revenue_share_fields(data)
        return data

    @field_validator("gross_amount")
    @classmethod
    def validate_gross_amount(cls, value: Decimal) -> Decimal:
        return normalize_money(value)

    @field_validator("recognized_at")
    @classmethod
    def validate_recognized_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("recognized_at must be timezone-aware")
        return value


class ProviderRevenuePayoutEntryRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str = Field(..., pattern=_ID_PATTERN)
    hook_id: uuid.UUID
    provider_id: str = Field(..., pattern=_ID_PATTERN)
    k_algo: str = Field(..., pattern=_ID_PATTERN)
    policy_id: str = Field(..., pattern=_ID_PATTERN)
    source_service: str = Field(..., pattern=_SOURCE_SERVICE_PATTERN)
    source_event_id: uuid.UUID
    period_month: str = Field(..., pattern=_PERIOD_MONTH_PATTERN)
    currency: str = Field(..., pattern=r"^[A-Z]{3}$")
    gross_amount: Decimal = Field(..., ge=0)
    provider_share_ratio: Decimal = Field(..., ge=0, le=1)
    platform_share_ratio: Decimal = Field(..., ge=0, le=1)
    provider_revenue_amount: Decimal = Field(..., ge=0)
    platform_revenue_amount: Decimal = Field(..., ge=0)
    status: ProviderRevenuePayoutEntryStatus
    recognized_at: datetime
    scope_source: ProviderDashboardScopeSource

    @field_serializer(
        "gross_amount",
        "provider_revenue_amount",
        "platform_revenue_amount",
    )
    def serialize_money(self, value: Decimal) -> str:
        return f"{value.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP):.4f}"

    @field_serializer("provider_share_ratio", "platform_share_ratio")
    def serialize_ratio(self, value: Decimal) -> str:
        return f"{value.quantize(_RATIO_QUANT):.6f}"


class ProviderRevenuePayoutEntryResponse(ProviderRevenuePayoutEntryRow):
    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class ProviderRevenuePayoutStatusCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pending: int = Field(default=0, ge=0)
    held: int = Field(default=0, ge=0)
    paid: int = Field(default=0, ge=0)
    voided: int = Field(default=0, ge=0)


class ProviderRevenuePayoutCurrencyTotal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str = Field(..., pattern=r"^[A-Z]{3}$")
    entry_count: int = Field(..., ge=0)
    gross_amount: Decimal = Field(..., ge=0)
    provider_revenue_amount: Decimal = Field(..., ge=0)
    platform_revenue_amount: Decimal = Field(..., ge=0)
    pending_payout_amount: Decimal = Field(..., ge=0)
    held_payout_amount: Decimal = Field(..., ge=0)
    paid_amount: Decimal = Field(..., ge=0)
    voided_gross_amount: Decimal = Field(..., ge=0)

    @field_serializer(
        "gross_amount",
        "provider_revenue_amount",
        "platform_revenue_amount",
        "pending_payout_amount",
        "held_payout_amount",
        "paid_amount",
        "voided_gross_amount",
    )
    def serialize_money(self, value: Decimal) -> str:
        return f"{value.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP):.4f}"


class ProviderRevenuePayoutPeriodSummary(ProviderRevenuePayoutCurrencyTotal):
    period_month: str = Field(..., pattern=_PERIOD_MONTH_PATTERN)


class ProviderRevenuePayoutDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(..., pattern=_ID_PATTERN)
    tenant_id: uuid.UUID | None = None
    from_at: datetime | None = None
    to_at: datetime | None = None
    period_month: str | None = Field(default=None, pattern=_PERIOD_MONTH_PATTERN)
    status: ProviderRevenuePayoutEntryStatus | None = None
    k_algo: str | None = Field(default=None, pattern=_ID_PATTERN)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    status_counts: ProviderRevenuePayoutStatusCounts
    total_entries: int = Field(..., ge=0)
    currency_totals: list[ProviderRevenuePayoutCurrencyTotal]
    period_summaries: list[ProviderRevenuePayoutPeriodSummary]
    entries: list[ProviderRevenuePayoutEntryRow]


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


def _parse_semver(value: str, *, field_name: str) -> tuple[int, int, int]:
    match = _SEMVER_PATTERN.match(value)
    if not match:
        raise ValueError(f"{field_name} must be strict MAJOR.MINOR.PATCH semver")
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _validate_version_delta(
    *,
    current_version: str,
    proposed_version: str,
    change_kind: str,
) -> None:
    current = _parse_semver(current_version, field_name="current_version")
    proposed = _parse_semver(proposed_version, field_name="proposed_version")
    if proposed <= current:
        raise ValueError("proposed_version must be greater than current_version")
    current_major, current_minor, current_patch = current
    proposed_major, proposed_minor, proposed_patch = proposed
    if change_kind == "patch":
        valid = (
            proposed_major == current_major
            and proposed_minor == current_minor
            and proposed_patch > current_patch
        )
    elif change_kind == "minor":
        valid = (
            proposed_major == current_major
            and proposed_minor > current_minor
            and proposed_patch == 0
        )
    elif change_kind == "major":
        valid = proposed_major > current_major and proposed_minor == 0 and proposed_patch == 0
    else:
        valid = False
    if not valid:
        raise ValueError("change_kind does not match current_version/proposed_version delta")


class ProviderVersionUpdateUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID | None = None
    application_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    version_update_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    current_version: str = Field(..., min_length=5, max_length=64)
    proposed_version: str = Field(..., min_length=5, max_length=64)
    change_kind: ProviderVersionChangeKind
    openapi_url: str = Field(..., min_length=1)
    openapi_sha256: str = Field(..., pattern=r"^[0-9a-fA-F]{64}$")
    image_digest: str = Field(..., min_length=1)
    cosign_bundle: dict[str, Any] = Field(default_factory=dict)
    sbom_ref: str | None = None
    release_notes_ref: str | None = None
    status: Literal["draft", "submitted"] = "draft"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def reject_derived_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            forbidden = {
                "requested_provider_id",
                "review_notes_ref",
                "submitted_at",
                "reviewed_at",
                "record_version",
                "created_at",
                "updated_at",
            }
            present = sorted(forbidden.intersection(data))
            if present:
                raise ValueError(f"version update derived fields are not allowed: {present}")
        return data

    @field_validator("current_version", "proposed_version")
    @classmethod
    def validate_semver(cls, value: str) -> str:
        _parse_semver(value, field_name="version")
        return value

    @field_validator("openapi_url")
    @classmethod
    def validate_openapi_url(cls, value: str) -> str:
        return str(_validate_http_url(value, field_name="openapi_url"))

    @field_validator("image_digest")
    @classmethod
    def validate_image_digest(cls, value: str) -> str:
        if not _DIGEST_PATTERN.search(value):
            raise ValueError("image_digest must include sha256:<64 hex>")
        return value

    @field_validator("sbom_ref", "release_notes_ref")
    @classmethod
    def validate_optional_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_reference(value, field_name="reference")

    @field_validator("cosign_bundle", "metadata")
    @classmethod
    def validate_reference_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        _reject_forbidden_reference_fields(value)
        return value

    @model_validator(mode="after")
    def validate_change_kind(self) -> ProviderVersionUpdateUpsertRequest:
        _validate_version_delta(
            current_version=self.current_version,
            proposed_version=self.proposed_version,
            change_kind=self.change_kind,
        )
        return self


class ProviderVersionUpdateStatusPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ProviderVersionUpdateStatus
    review_notes_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def reject_artifact_or_derived_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            forbidden = {
                "application_id",
                "version_update_id",
                "requested_provider_id",
                "current_version",
                "proposed_version",
                "change_kind",
                "openapi_url",
                "openapi_sha256",
                "image_digest",
                "cosign_bundle",
                "sbom_ref",
                "release_notes_ref",
                "submitted_at",
                "reviewed_at",
                "record_version",
                "created_at",
                "updated_at",
            }
            present = sorted(forbidden.intersection(data))
            if present:
                raise ValueError(f"version update status fields are not allowed: {present}")
        return data

    @field_validator("review_notes_ref")
    @classmethod
    def validate_review_notes_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_reference(value, field_name="review_notes_ref")

    @field_validator("metadata")
    @classmethod
    def validate_status_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        _reject_forbidden_reference_fields(value)
        return value


class ProviderVersionUpdateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    application_id: str = Field(..., pattern=_ID_PATTERN)
    version_update_id: str = Field(..., pattern=_ID_PATTERN)
    requested_provider_id: str = Field(..., pattern=_ID_PATTERN)
    current_version: str
    proposed_version: str
    change_kind: ProviderVersionChangeKind
    openapi_url: str
    openapi_sha256: str = Field(..., pattern=r"^[0-9a-fA-F]{64}$")
    image_digest: str
    cosign_bundle: dict[str, Any]
    sbom_ref: str | None = None
    release_notes_ref: str | None = None
    status: ProviderVersionUpdateStatus
    review_notes_ref: str | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    record_version: int = Field(..., ge=1)
    metadata: dict[str, Any]
    scope_source: ProviderDashboardScopeSource
    created_at: datetime
    updated_at: datetime


class ProviderShadowRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_count: int = Field(..., ge=0)
    evaluation_sample_count: int = Field(..., ge=1, le=500)
    observed_day_span: int = Field(..., ge=0)
    coverage_classes: list[ProviderShadowCoverageClass]
    coverage_class_counts: dict[ProviderShadowCoverageClass, int]
    success_count: int = Field(..., ge=0)
    success_rate: Decimal = Field(..., ge=0, le=1)
    average_deviation_ratio: Decimal = Field(..., ge=0)
    provider_p95_latency_ms: int = Field(..., ge=0)
    baseline_p95_latency_ms: int = Field(..., ge=0)
    p95_latency_ratio: Decimal = Field(..., ge=0)
    thresholds: dict[str, Any]
    failed_reasons: list[str]

    @field_serializer("success_rate", "average_deviation_ratio", "p95_latency_ratio")
    def serialize_summary_decimal(self, value: Decimal) -> str:
        return f"{value.quantize(_RATIO_QUANT):.6f}"


class ProviderShadowRunUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID | None = None
    application_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    evaluation_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    run_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    baseline_provider_id: str = Field(..., pattern=_ID_PATTERN)
    status: ProviderShadowRunUpsertStatus | None = None
    started_at: datetime | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def reject_derived_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            forbidden = {
                "summary",
                "requested_provider_id",
                "benchmark_suite",
                "evaluation_sample_count",
            }
            present = sorted(forbidden.intersection(data))
            if present:
                raise ValueError(f"shadow run derived fields are not allowed: {present}")
        return data

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, value: list[str]) -> list[str]:
        refs: list[str] = []
        for item in value:
            ref = _validate_reference(item, field_name="evidence_refs")
            if ref not in refs:
                refs.append(ref)
        return refs

    @field_validator("metadata")
    @classmethod
    def validate_shadow_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        _reject_forbidden_reference_fields(value)
        return value


class ProviderShadowRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    application_id: str = Field(..., pattern=_ID_PATTERN)
    evaluation_id: str = Field(..., pattern=_ID_PATTERN)
    run_id: str = Field(..., pattern=_ID_PATTERN)
    requested_provider_id: str = Field(..., pattern=_ID_PATTERN)
    benchmark_suite: str = Field(..., pattern=_BENCHMARK_SUITE_PATTERN)
    evaluation_sample_count: int = Field(..., ge=1, le=500)
    baseline_provider_id: str = Field(..., pattern=_ID_PATTERN)
    status: ProviderShadowRunStatus
    started_at: datetime | None = None
    ended_at: datetime | None = None
    summary: ProviderShadowRunSummary | dict[str, Any]
    evidence_refs: list[str]
    metadata: dict[str, Any]
    scope_source: ScopeSource
    created_at: datetime
    updated_at: datetime


class ProviderShadowSampleUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID | None = None
    sample_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    coverage_class: ProviderShadowCoverageClass
    dataset_ref: str = Field(..., min_length=1)
    case_ref: str = Field(..., min_length=1)
    observed_at: datetime
    provider_status_code: int = Field(..., ge=100, le=599)
    provider_latency_ms: int = Field(..., ge=1)
    baseline_latency_ms: int = Field(..., ge=1)
    deviation_ratio: Decimal = Field(..., ge=Decimal("0"), le=Decimal("999.999999"))
    timed_out: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def reject_derived_fields(cls, data: Any) -> Any:
        if isinstance(data, dict) and "passed" in data:
            raise ValueError("passed is derived by the service")
        return data

    @field_validator("dataset_ref")
    @classmethod
    def validate_dataset_ref(cls, value: str) -> str:
        return _validate_reference(value, field_name="dataset_ref")

    @field_validator("case_ref")
    @classmethod
    def validate_case_ref(cls, value: str) -> str:
        return _validate_reference(value, field_name="case_ref")

    @field_validator("deviation_ratio")
    @classmethod
    def normalize_deviation_ratio(cls, value: Decimal) -> Decimal:
        return value.quantize(_RATIO_QUANT)

    @field_validator("metadata")
    @classmethod
    def validate_sample_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        _reject_forbidden_reference_fields(value)
        return value


class ProviderShadowSampleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    run_id: str = Field(..., pattern=_ID_PATTERN)
    sample_id: str = Field(..., pattern=_ID_PATTERN)
    coverage_class: ProviderShadowCoverageClass
    dataset_ref: str
    case_ref: str
    observed_at: datetime
    provider_status_code: int = Field(..., ge=100, le=599)
    provider_latency_ms: int = Field(..., ge=1)
    baseline_latency_ms: int = Field(..., ge=1)
    deviation_ratio: Decimal = Field(..., ge=0)
    timed_out: bool
    passed: bool
    metadata: dict[str, Any]
    scope_source: ScopeSource
    created_at: datetime
    updated_at: datetime

    @field_serializer("deviation_ratio")
    def serialize_deviation_ratio(self, value: Decimal) -> str:
        return f"{value.quantize(_RATIO_QUANT):.6f}"


class ProviderRolloutUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID | None = None
    application_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    evaluation_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    run_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    rollout_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    evidence_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def reject_derived_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            forbidden = {
                "baseline_provider_id",
                "benchmark_suite",
                "current_stage_percent",
                "requested_provider_id",
                "shadow_summary_snapshot",
                "stage_history",
                "status",
            }
            present = sorted(forbidden.intersection(data))
            if present:
                raise ValueError(f"rollout derived fields are not allowed: {present}")
        return data

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, value: list[str]) -> list[str]:
        refs: list[str] = []
        for item in value:
            ref = _validate_reference(item, field_name="evidence_refs")
            if ref not in refs:
                refs.append(ref)
        return refs

    @field_validator("metadata")
    @classmethod
    def validate_rollout_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        _reject_forbidden_reference_fields(value)
        return value


class ProviderRolloutActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_stage_percent: ProviderRolloutStage | None = None
    reason_ref: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("reason_ref")
    @classmethod
    def validate_reason_ref(cls, value: str) -> str:
        return _validate_reference(value, field_name="reason_ref")

    @field_validator("metadata")
    @classmethod
    def validate_action_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        _reject_forbidden_reference_fields(value)
        return value


class ProviderRolloutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    application_id: str = Field(..., pattern=_ID_PATTERN)
    evaluation_id: str = Field(..., pattern=_ID_PATTERN)
    run_id: str = Field(..., pattern=_ID_PATTERN)
    rollout_id: str = Field(..., pattern=_ID_PATTERN)
    requested_provider_id: str = Field(..., pattern=_ID_PATTERN)
    baseline_provider_id: str = Field(..., pattern=_ID_PATTERN)
    benchmark_suite: str = Field(..., pattern=_BENCHMARK_SUITE_PATTERN)
    status: ProviderRolloutStatus
    current_stage_percent: ProviderRolloutStage
    stage_history: list[dict[str, Any]]
    shadow_summary_snapshot: dict[str, Any]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    paused_at: datetime | None = None
    cancelled_at: datetime | None = None
    evidence_refs: list[str]
    metadata: dict[str, Any]
    scope_source: ScopeSource
    created_at: datetime
    updated_at: datetime


class ProviderRouteShareStatusCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft: int = Field(default=0, ge=0)
    active: int = Field(default=0, ge=0)
    paused: int = Field(default=0, ge=0)
    completed: int = Field(default=0, ge=0)
    cancelled: int = Field(default=0, ge=0)


class ProviderRouteShareTimelinePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(..., pattern=_ID_PATTERN)
    evaluation_id: str = Field(..., pattern=_ID_PATTERN)
    run_id: str = Field(..., pattern=_ID_PATTERN)
    rollout_id: str = Field(..., pattern=_ID_PATTERN)
    provider_id: str = Field(..., pattern=_ID_PATTERN)
    baseline_provider_id: str = Field(..., pattern=_ID_PATTERN)
    benchmark_suite: str = Field(..., pattern=_BENCHMARK_SUITE_PATTERN)
    action: ProviderRouteShareAction
    stage_percent: ProviderRolloutStage
    from_status: ProviderRolloutStatus | None = None
    to_status: ProviderRolloutStatus
    observed_at: datetime
    scope_source: ProviderRouteShareScopeSource


class ProviderRouteShareCurrentRollout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(..., pattern=_ID_PATTERN)
    evaluation_id: str = Field(..., pattern=_ID_PATTERN)
    run_id: str = Field(..., pattern=_ID_PATTERN)
    rollout_id: str = Field(..., pattern=_ID_PATTERN)
    status: ProviderRolloutStatus
    current_stage_percent: ProviderRolloutStage
    started_at: datetime | None = None
    completed_at: datetime | None = None
    paused_at: datetime | None = None
    cancelled_at: datetime | None = None
    updated_at: datetime
    scope_source: ProviderRouteShareScopeSource


class ProviderRouteShareDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(..., pattern=_ID_PATTERN)
    tenant_id: uuid.UUID | None = None
    from_at: datetime | None = None
    to_at: datetime | None = None
    status_counts: ProviderRouteShareStatusCounts
    total_rollouts: int = Field(..., ge=0)
    highest_current_stage_percent: ProviderRolloutStage
    current_rollouts: list[ProviderRouteShareCurrentRollout]
    timeline: list[ProviderRouteShareTimelinePoint]


class ProviderKpiRunStatusCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft: int = Field(default=0, ge=0)
    running: int = Field(default=0, ge=0)
    passed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    cancelled: int = Field(default=0, ge=0)


class ProviderKpiAggregateMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_count: int = Field(..., ge=0)
    success_count: int = Field(..., ge=0)
    failed_count: int = Field(..., ge=0)
    timeout_count: int = Field(..., ge=0)
    provider_error_count: int = Field(..., ge=0)
    success_rate: Decimal = Field(..., ge=0, le=1)
    average_deviation_ratio: Decimal = Field(..., ge=0)
    provider_p95_latency_ms: int = Field(..., ge=0)
    baseline_p95_latency_ms: int = Field(..., ge=0)
    p95_latency_ratio: Decimal = Field(..., ge=0)

    @field_serializer("success_rate", "average_deviation_ratio", "p95_latency_ratio")
    def serialize_kpi_decimal(self, value: Decimal) -> str:
        return f"{value.quantize(_RATIO_QUANT):.6f}"


class ProviderKpiRunMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(..., pattern=_ID_PATTERN)
    evaluation_id: str = Field(..., pattern=_ID_PATTERN)
    run_id: str = Field(..., pattern=_ID_PATTERN)
    provider_id: str = Field(..., pattern=_ID_PATTERN)
    baseline_provider_id: str = Field(..., pattern=_ID_PATTERN)
    benchmark_suite: str = Field(..., pattern=_BENCHMARK_SUITE_PATTERN)
    status: ProviderShadowRunStatus
    started_at: datetime | None = None
    ended_at: datetime | None = None
    updated_at: datetime
    observed_from: datetime | None = None
    observed_to: datetime | None = None
    coverage_classes: list[ProviderShadowCoverageClass]
    coverage_class_counts: dict[ProviderShadowCoverageClass, int]
    threshold_violations: list[str]
    metrics: ProviderKpiAggregateMetrics
    scope_source: ProviderDashboardScopeSource


class ProviderKpiTimelinePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(..., pattern=_ID_PATTERN)
    evaluation_id: str = Field(..., pattern=_ID_PATTERN)
    run_id: str = Field(..., pattern=_ID_PATTERN)
    provider_id: str = Field(..., pattern=_ID_PATTERN)
    benchmark_suite: str = Field(..., pattern=_BENCHMARK_SUITE_PATTERN)
    bucket_start: datetime
    metrics: ProviderKpiAggregateMetrics
    scope_source: ProviderDashboardScopeSource


class ProviderKpiRolloutSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_rollouts: int = Field(..., ge=0)
    highest_current_stage_percent: ProviderRolloutStage
    status_counts: ProviderRouteShareStatusCounts


class ProviderKpiDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(..., pattern=_ID_PATTERN)
    tenant_id: uuid.UUID | None = None
    from_at: datetime | None = None
    to_at: datetime | None = None
    run_status_counts: ProviderKpiRunStatusCounts
    total_runs: int = Field(..., ge=0)
    aggregate: ProviderKpiAggregateMetrics
    rollout_summary: ProviderKpiRolloutSummary
    run_metrics: list[ProviderKpiRunMetric]
    timeline: list[ProviderKpiTimelinePoint]
