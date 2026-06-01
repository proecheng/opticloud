"""Pydantic schemas for capability-registry."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ProviderKind = Literal["self", "open_source", "external", "commercial"]
ProviderStatus = Literal["active", "inactive", "deprecated"]
CapabilityStatus = Literal["v1", "v1_late", "v2", "audited", "shadow"]
OAuthFlowStatus = Literal["draft", "configured", "disabled"]
ScopeSource = Literal["global", "tenant", "global_fallback"]

_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{0,63}$"
_TIER_PATTERN = r"^(T[1-6]|P[1-5])$"
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_DIGEST_PATTERN = re.compile(r"sha256:[0-9a-fA-F]{64}")
_TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


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
