"""Per-tenant cost attribution helpers (Story M2.3).

This module is intentionally service-agnostic. Callers pass their local ORM
model class so shared-py does not import service packages or own DB metadata.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CostUnit(StrEnum):
    """Canonical cost attribution units locked by the DB constraint."""

    LLM_TOKEN = "llm_token"  # noqa: S105 - cost unit name, not a secret token
    GPU_SECOND = "gpu_second"
    SOLVER_SECOND = "solver_second"


_BLOCKED_METADATA_KEYS = {
    "prompt",
    "completion",
    "api_key",
    "authorization",
    "jwt",
    "phone",
    "email",
    "password",
    "token",
}


class CostTelemetryEvent(BaseModel):
    """Validated cost event that can be inserted by any service."""

    model_config = ConfigDict(use_enum_values=True)

    tenant_id: uuid.UUID
    service: str = Field(min_length=1, max_length=64)
    cost_unit: CostUnit
    value: Decimal = Field(ge=Decimal("0"))
    source_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    recorded_at: datetime | None = None

    @field_validator("service")
    @classmethod
    def _service_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("service must not be blank")
        return stripped

    @field_validator("value", mode="before")
    @classmethod
    def _decimal_from_string(cls, value: object) -> object:
        if isinstance(value, float):
            return Decimal(str(value))
        return value

    @model_validator(mode="after")
    def _metadata_is_safe(self) -> CostTelemetryEvent:
        blocked = _find_blocked_metadata_key(self.metadata)
        if blocked is not None:
            raise ValueError(f"metadata contains blocked key: {blocked}")
        return self

    def as_record_kwargs(self) -> dict[str, Any]:
        """Return kwargs matching the shared `cost_attribution` table columns."""
        payload: dict[str, Any] = {
            "tenant_id": self.tenant_id,
            "service": self.service,
            "cost_unit": self.cost_unit,
            "value": self.value,
            "source_id": self.source_id,
            "metadata_json": self.metadata,
        }
        if self.recorded_at is not None:
            payload["recorded_at"] = self.recorded_at
        return payload


def _find_blocked_metadata_key(value: Mapping[str, Any]) -> str | None:
    for key, item in value.items():
        if key.lower() in _BLOCKED_METADATA_KEYS:
            return key
        if isinstance(item, Mapping):
            nested = _find_blocked_metadata_key(item)
            if nested is not None:
                return nested
    return None


def validate_cost_event(event: CostTelemetryEvent | Mapping[str, Any]) -> CostTelemetryEvent:
    """Validate an incoming event mapping or return the already validated event."""
    if isinstance(event, CostTelemetryEvent):
        return event
    return CostTelemetryEvent.model_validate(event)


class CostSession(Protocol):
    """Minimal async session protocol used by `record_cost_event`."""

    def add(self, instance: object, _warn: bool = True) -> None: ...

    def flush(self) -> Awaitable[None]: ...


ModelFactory = Callable[..., object]


async def record_cost_event(
    session: CostSession,
    model_cls: ModelFactory,
    event: CostTelemetryEvent | Mapping[str, Any],
) -> object:
    """Insert one cost row and flush without committing."""
    validated = validate_cost_event(event)
    row = model_cls(**validated.as_record_kwargs())
    session.add(row)
    await session.flush()
    return row


__all__ = [
    "CostTelemetryEvent",
    "CostUnit",
    "record_cost_event",
    "validate_cost_event",
]
