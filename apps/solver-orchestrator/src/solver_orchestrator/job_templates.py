"""Job template payload helpers for Story 5.D.3."""

from __future__ import annotations

import hashlib
import json
import numbers
from dataclasses import dataclass
from typing import Any, Literal

SourceKind = Literal["optimization", "prediction"]
PayloadSchemaVersion = Literal["optimization_request_v1", "prediction_request_v1"]


@dataclass(frozen=True)
class TemplatePayload:
    source_kind: SourceKind
    task_type: str
    payload_schema_version: PayloadSchemaVersion
    payload_json: dict[str, Any]
    payload_sha256: str


def strip_system_metadata(value: Any) -> Any:
    """Return value with all `_system` keys recursively removed."""
    if isinstance(value, dict):
        return {key: strip_system_metadata(item) for key, item in value.items() if key != "_system"}
    if isinstance(value, list):
        return [strip_system_metadata(item) for item in value]
    return value


def canonical_payload_hash(
    *,
    source_kind: SourceKind,
    payload_schema_version: PayloadSchemaVersion,
    payload_json: dict[str, Any],
) -> str:
    envelope = {
        "payload_json": payload_json,
        "payload_schema_version": payload_schema_version,
        "source_kind": source_kind,
    }
    canon = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _as_object(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return value


def _normalize_objective(value: Any, *, field_name: str) -> dict[str, Any]:
    raw = _as_object(value, field_name=field_name)
    if "c" not in raw:
        raise ValueError(f"{field_name}.c is required")
    return {"c": raw["c"]}


def _normalize_constraints(value: Any) -> dict[str, Any]:
    raw = _as_object(value, field_name="st")
    matrix = raw.get("A", raw.get("a"))
    if matrix is None:
        raise ValueError("st.A is required")
    if "b" not in raw:
        raise ValueError("st.b is required")
    normalized = {"A": matrix, "b": raw["b"]}
    for optional_key in ("x_lower", "x_upper"):
        if optional_key in raw:
            normalized[optional_key] = raw[optional_key]
    return normalized


def _normalize_options(value: Any) -> dict[str, Any]:
    raw = _as_object(value, field_name="options")
    allowed_keys = (
        "max_solve_seconds",
        "top_k_alternatives",
        "reproducible",
        "anonymous",
        "backtest",
    )
    return {key: raw[key] for key in allowed_keys if key in raw}


def _normalize_optimization_payload(payload: dict[str, Any]) -> dict[str, Any]:
    clean = strip_system_metadata(payload)
    if not isinstance(clean, dict):
        raise ValueError("optimization payload must be an object")
    task_type = clean.get("task_type")
    if not isinstance(task_type, str) or not task_type:
        raise ValueError("optimization template requires task_type")
    has_minimize = clean.get("minimize") is not None
    has_maximize = clean.get("maximize") is not None
    if has_minimize == has_maximize:
        raise ValueError("optimization template requires exactly one objective")

    normalized: dict[str, Any] = {
        "task_type": task_type,
        "st": _normalize_constraints(clean.get("st")),
        "options": _normalize_options(clean.get("options", {})),
    }
    if has_minimize:
        normalized["minimize"] = _normalize_objective(clean["minimize"], field_name="minimize")
    else:
        normalized["maximize"] = _normalize_objective(clean["maximize"], field_name="maximize")

    solver = clean.get("solver")
    if solver is not None:
        if not isinstance(solver, str) or not solver:
            raise ValueError("solver must be a non-empty string")
        normalized["solver"] = solver

    fallback_chain = clean.get("fallback_chain")
    if fallback_chain is not None:
        if not isinstance(fallback_chain, list):
            raise ValueError("fallback_chain must be a list")
        normalized["fallback_chain"] = fallback_chain
    return normalized


def build_optimization_template_payload(input_payload: object) -> TemplatePayload:
    if not isinstance(input_payload, dict):
        raise ValueError("optimization input payload must be an object")
    payload_json = _normalize_optimization_payload(input_payload)
    payload_schema_version: PayloadSchemaVersion = "optimization_request_v1"
    return TemplatePayload(
        source_kind="optimization",
        task_type=payload_json["task_type"],
        payload_schema_version=payload_schema_version,
        payload_json=payload_json,
        payload_sha256=canonical_payload_hash(
            source_kind="optimization",
            payload_schema_version=payload_schema_version,
            payload_json=payload_json,
        ),
    )


def build_prediction_template_payload(input_payload: object) -> TemplatePayload:
    if not isinstance(input_payload, dict):
        raise ValueError("prediction input payload must be an object")
    clean = strip_system_metadata(input_payload)
    if not isinstance(clean, dict):
        raise ValueError("prediction payload must be an object")
    family = clean.get("family")
    data = clean.get("data")
    horizon = clean.get("horizon")
    if not isinstance(family, str) or not family:
        raise ValueError("prediction template requires family")
    if not isinstance(data, list) or any(
        not isinstance(point, numbers.Real) or isinstance(point, bool) for point in data
    ):
        raise ValueError("prediction template data must be numeric")
    if not isinstance(horizon, int) or isinstance(horizon, bool):
        raise ValueError("prediction template horizon must be an integer")
    payload_json = {
        "family": family,
        "data": data,
        "horizon": horizon,
    }
    payload_schema_version: PayloadSchemaVersion = "prediction_request_v1"
    return TemplatePayload(
        source_kind="prediction",
        task_type="forecast",
        payload_schema_version=payload_schema_version,
        payload_json=payload_json,
        payload_sha256=canonical_payload_hash(
            source_kind="prediction",
            payload_schema_version=payload_schema_version,
            payload_json=payload_json,
        ),
    )
