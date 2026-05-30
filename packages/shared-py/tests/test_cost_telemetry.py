"""Story M2.3 — shared cost_telemetry validation tests."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from opticloud_shared.cost_telemetry import CostTelemetryEvent, CostUnit, validate_cost_event
from pydantic import ValidationError


def test_validates_all_three_cost_units() -> None:
    """M2.3 AC9 — future services can emit all canonical units without imports."""
    tenant_id = uuid.uuid4()
    events = [
        CostTelemetryEvent(
            tenant_id=tenant_id,
            service="chat",
            cost_unit=CostUnit.LLM_TOKEN,
            value=1234,
            metadata={"model_provider": "deepseek"},
        ),
        CostTelemetryEvent(
            tenant_id=tenant_id,
            service="sandbox-runner",
            cost_unit=CostUnit.GPU_SECOND,
            value=Decimal("2.500000"),
            metadata={"gpu_class": "t4"},
        ),
        CostTelemetryEvent(
            tenant_id=tenant_id,
            service="solver-orchestrator",
            cost_unit=CostUnit.SOLVER_SECOND,
            value=0.125,
            metadata={"solver": "highs"},
        ),
    ]

    assert [e.cost_unit for e in events] == ["llm_token", "gpu_second", "solver_second"]
    assert events[2].value == Decimal("0.125")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("value", Decimal("-0.000001")),
        ("service", " "),
        ("cost_unit", "invalid_unit"),
        ("metadata", ["not", "an", "object"]),
    ],
)
def test_rejects_invalid_event_fields(field: str, value: object) -> None:
    """M2.3 AC11 — invalid unit/service/value/metadata are rejected."""
    payload: dict[str, object] = {
        "tenant_id": uuid.uuid4(),
        "service": "solver-orchestrator",
        "cost_unit": "solver_second",
        "value": Decimal("1.0"),
        "metadata": {},
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        validate_cost_event(payload)


@pytest.mark.parametrize(
    "blocked_key",
    [
        "prompt",
        "completion",
        "input_payload",
        "raw_payload",
        "amount",
        "balance",
        "credit",
        "api_key",
        "authorization",
        "jwt",
        "phone",
        "email",
        "password",
        "token",
    ],
)
def test_rejects_blocked_metadata_keys(blocked_key: str) -> None:
    """M2.3 AC3 — metadata cannot carry common PII or secret-bearing keys."""
    with pytest.raises(ValidationError, match="metadata contains blocked key"):
        CostTelemetryEvent(
            tenant_id=uuid.uuid4(),
            service="chat",
            cost_unit=CostUnit.LLM_TOKEN,
            value=10,
            metadata={"safe": {"nested": {blocked_key: "secret"}}},
        )


def test_rejects_deeply_nested_sensitive_cost_metadata() -> None:
    """5.A.0 — cost metadata guard catches raw payload and monetary leakage."""
    with pytest.raises(ValidationError, match="metadata contains blocked key"):
        CostTelemetryEvent(
            tenant_id=uuid.uuid4(),
            service="solver-orchestrator",
            cost_unit=CostUnit.SOLVER_SECOND,
            value=Decimal("0.25"),
            metadata={"safe": {"nested": {"raw_payload": {"amount": "6.00"}}}},
        )


def test_rejects_sensitive_metadata_key_fragments() -> None:
    """5.A.0 — monetary/auth fields are rejected even when embedded in longer keys."""
    with pytest.raises(ValidationError, match="metadata contains blocked key"):
        CostTelemetryEvent(
            tenant_id=uuid.uuid4(),
            service="solver-orchestrator",
            cost_unit=CostUnit.SOLVER_SECOND,
            value=Decimal("0.25"),
            metadata={"billing_amount_cny": "6.00"},
        )


def test_as_record_kwargs_matches_table_columns() -> None:
    """M2.3 AC3 — helper output matches shared ORM column names."""
    source_id = uuid.uuid4()
    event = CostTelemetryEvent(
        tenant_id=uuid.uuid4(),
        service="solver-orchestrator",
        cost_unit=CostUnit.SOLVER_SECOND,
        value=Decimal("0.250000"),
        source_id=source_id,
        metadata={"task_type": "lp"},
    )

    kwargs = event.as_record_kwargs()

    assert kwargs["cost_unit"] == "solver_second"
    assert kwargs["metadata_json"] == {"task_type": "lp"}
    assert kwargs["source_id"] == source_id
