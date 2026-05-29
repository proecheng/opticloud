from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from opticloud_shared.llm_router import Completion, LLMRouterError, Prompt, PromptMessage, complete
from opticloud_shared.llm_router.registry import CANONICAL_MODEL_ALIASES
from pydantic import ValidationError

from chat_service.router_preview import SUPPORTED_TASK_TYPES
from chat_service.schemas import (
    ChatLocale,
    FormulatorPreview,
    FormulatorPreviewSource,
    FormulatorPreviewStatus,
    FormulatorValidationError,
    RouterPreview,
    TaskType,
)

CompletionFunc = Callable[[Prompt, str], Completion]

LLM_FORMULATOR_SOURCE: FormulatorPreviewSource = "llm_formulator_internal_beta"
HEURISTIC_FORMULATOR_SOURCE: FormulatorPreviewSource = "heuristic_formulator_internal_beta"
_MAX_VARIABLES = 50
_MAX_CONSTRAINT_KEYS = 20
_MAX_NESTED_LIST_ITEMS = 50
_MAX_NESTED_DICT_KEYS = 50
_DETERMINISTIC_MARKER = "formulator extraction"
_SECRET_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{4,}|api[_-]?key|bearer\s+[A-Za-z0-9._-]+|"
    r"authorization|cookie|password|token|raw_response|provider_request|provider_response|"
    r"deterministic_digest)",
    re.IGNORECASE,
)

FORMULATOR_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "task_type": {"type": "string", "enum": list(SUPPORTED_TASK_TYPES)},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "variables": {"type": "object"},
        "objective": {"type": "object"},
        "constraints": {"type": "object"},
        "validation_errors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field_path": {"type": "string"},
                    "message": {"type": "string"},
                    "remediation_hint_key": {"type": "string"},
                },
                "required": ["field_path", "message"],
            },
        },
    },
    "required": ["task_type", "confidence", "variables", "objective", "constraints"],
}


@dataclass(frozen=True)
class FormulatorRouteResult:
    preview: FormulatorPreview
    formulator_invoked: bool
    provider_request_sent: Literal[False] = False


def build_formulator_prompt(
    *,
    message: str,
    locale: ChatLocale,
    prompt_id: str,
    router_preview: RouterPreview,
) -> Prompt:
    return Prompt(
        prompt_id=prompt_id,
        task="formulator_extraction",
        locale=locale,
        messages=[
            PromptMessage(
                role="system",
                content=(
                    "Extract a structured OptiCloud task preview for the routed task. "
                    "Return JSON with task_type, confidence, variables, objective, "
                    "constraints, and validation_errors. Do not invent missing data."
                ),
            ),
            PromptMessage(role="user", content=message),
        ],
        response_schema=FORMULATOR_RESPONSE_SCHEMA,
        metadata={"router_task_type": router_preview.task_type},
    )


def parse_formulator_completion(
    text: str,
    *,
    router_preview: RouterPreview,
    original_message: str | None = None,
) -> FormulatorPreview | None:
    if _looks_like_deterministic_text(text):
        return _clarification_preview(
            router_preview.task_type,
            confidence=0.4,
            field_path="variables",
            message="structured variables missing from deterministic completion",
            remediation_hint_key="chat.formulator.variables_required",
        )

    payload = _parse_json_payload(text)
    if payload is None:
        return None

    task_type = payload.get("task_type")
    confidence = payload.get("confidence")
    variables = payload.get("variables")
    objective = payload.get("objective")
    constraints = payload.get("constraints")
    validation_errors = payload.get("validation_errors", [])

    if task_type not in SUPPORTED_TASK_TYPES:
        return None
    if task_type != router_preview.task_type:
        return None
    if not isinstance(confidence, int | float) or not 0.0 <= float(confidence) <= 1.0:
        return None
    if not isinstance(variables, dict) or not isinstance(objective, dict):
        return None
    if not isinstance(constraints, dict):
        return None
    if _mapping_too_large(variables, max_keys=_MAX_VARIABLES):
        return None
    if _mapping_too_large(constraints, max_keys=_MAX_CONSTRAINT_KEYS):
        return None
    if _nested_payload_too_large(variables, objective, constraints):
        return None
    if _contains_unsafe_text(
        variables,
        objective,
        constraints,
        original_message=original_message,
    ):
        return None

    errors = _coerce_validation_errors(validation_errors, original_message=original_message)
    if errors is None:
        return None

    status: FormulatorPreviewStatus = (
        "extracted"
        if _has_minimum_extracted_content(variables, objective, constraints)
        else "needs_clarification"
    )
    if status == "needs_clarification" and not errors:
        errors = [
            FormulatorValidationError(
                field_path="variables",
                message="structured variables are required",
                remediation_hint_key="chat.formulator.variables_required",
            )
        ]

    return FormulatorPreview(
        status=status,
        source=LLM_FORMULATOR_SOURCE if status == "extracted" else HEURISTIC_FORMULATOR_SOURCE,
        task_type=task_type,
        confidence=float(confidence) if status == "extracted" else min(float(confidence), 0.5),
        variables=dict(variables),
        objective=dict(objective),
        constraints=dict(constraints),
        validation_errors=errors,
        supported_task_types=list(SUPPORTED_TASK_TYPES),
    )


def extract_formulation_with_llm(
    *,
    message: str,
    locale: ChatLocale,
    prompt_id: str,
    router_preview: RouterPreview,
    completion_func: CompletionFunc = complete,
    model_alias: str = "deepseek-v3.5",
) -> FormulatorRouteResult:
    if router_preview.task_type == "unknown":
        return FormulatorRouteResult(
            preview=_skipped_preview(),
            formulator_invoked=False,
        )
    if model_alias not in CANONICAL_MODEL_ALIASES:
        return FormulatorRouteResult(
            preview=_fallback_preview(router_preview.task_type),
            formulator_invoked=False,
        )

    try:
        prompt = build_formulator_prompt(
            message=message,
            locale=locale,
            prompt_id=prompt_id,
            router_preview=router_preview,
        )
    except ValidationError:
        return FormulatorRouteResult(
            preview=_fallback_preview(router_preview.task_type),
            formulator_invoked=False,
        )

    try:
        completion = completion_func(prompt, model_alias)
    except LLMRouterError:
        return FormulatorRouteResult(
            preview=_fallback_preview(router_preview.task_type),
            formulator_invoked=True,
        )

    if completion.finish_reason != "stop":
        return FormulatorRouteResult(
            preview=_fallback_preview(router_preview.task_type),
            formulator_invoked=True,
        )

    preview = parse_formulator_completion(
        completion.text,
        router_preview=router_preview,
        original_message=message,
    )
    if preview is None:
        preview = _fallback_preview(router_preview.task_type)

    return FormulatorRouteResult(preview=preview, formulator_invoked=True)


def _parse_json_payload(text: str) -> dict[str, object] | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _looks_like_deterministic_text(text: str) -> bool:
    return _DETERMINISTIC_MARKER in text.lower()


def _mapping_too_large(value: Mapping[str, object], *, max_keys: int) -> bool:
    return len(value) > max_keys


def _nested_payload_too_large(*values: object) -> bool:
    return any(_value_too_large(value) for value in values)


def _value_too_large(value: object) -> bool:
    if isinstance(value, Mapping):
        return len(value) > _MAX_NESTED_DICT_KEYS or any(
            _value_too_large(child) for child in value.values()
        )
    if isinstance(value, list):
        return len(value) > _MAX_NESTED_LIST_ITEMS or any(_value_too_large(child) for child in value)
    return False


def _contains_unsafe_text(
    *values: object,
    original_message: str | None,
) -> bool:
    original = original_message.strip() if original_message else None
    for value in values:
        if _value_contains_unsafe_text(value, original_message=original):
            return True
    return False


def _value_contains_unsafe_text(value: object, *, original_message: str | None) -> bool:
    if isinstance(value, str):
        if _SECRET_PATTERN.search(value):
            return True
        return bool(original_message and original_message in value)
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _value_contains_unsafe_text(str(key), original_message=original_message):
                return True
            if _value_contains_unsafe_text(item, original_message=original_message):
                return True
    if isinstance(value, list):
        return any(_value_contains_unsafe_text(item, original_message=original_message) for item in value)
    return False


def _coerce_validation_errors(
    value: object,
    *,
    original_message: str | None,
) -> list[FormulatorValidationError] | None:
    original = original_message.strip() if original_message else None
    if not isinstance(value, list) or len(value) > 10:
        return None
    errors: list[FormulatorValidationError] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        field_path = item.get("field_path")
        message = item.get("message")
        remediation_hint_key = item.get("remediation_hint_key")
        if not isinstance(field_path, str) or not isinstance(message, str):
            return None
        if remediation_hint_key is not None and not isinstance(remediation_hint_key, str):
            return None
        if _SECRET_PATTERN.search(field_path) or _SECRET_PATTERN.search(message):
            return None
        if remediation_hint_key is not None and _SECRET_PATTERN.search(remediation_hint_key):
            return None
        if original and (original in field_path or original in message):
            return None
        errors.append(
            FormulatorValidationError(
                field_path=field_path,
                message=message,
                remediation_hint_key=remediation_hint_key,
            )
        )
    return errors


def _has_minimum_extracted_content(
    variables: Mapping[str, object],
    objective: Mapping[str, object],
    constraints: Mapping[str, object],
) -> bool:
    return bool(variables) and (bool(objective) or bool(constraints))


def _fallback_preview(task_type: TaskType) -> FormulatorPreview:
    return _clarification_preview(
        task_type,
        confidence=0.35,
        field_path="variables",
        message="structured variables are required",
        remediation_hint_key="chat.formulator.variables_required",
    )


def _clarification_preview(
    task_type: TaskType,
    *,
    confidence: float,
    field_path: str,
    message: str,
    remediation_hint_key: str,
) -> FormulatorPreview:
    return FormulatorPreview(
        status="needs_clarification",
        source=HEURISTIC_FORMULATOR_SOURCE,
        task_type=task_type,
        confidence=confidence,
        variables={},
        objective=_default_objective(task_type),
        constraints={},
        validation_errors=[
            FormulatorValidationError(
                field_path=field_path,
                message=message,
                remediation_hint_key=remediation_hint_key,
            )
        ],
        supported_task_types=list(SUPPORTED_TASK_TYPES),
    )


def _skipped_preview() -> FormulatorPreview:
    return FormulatorPreview(
        status="skipped",
        source=HEURISTIC_FORMULATOR_SOURCE,
        task_type="unknown",
        confidence=0.0,
        variables={},
        objective={},
        constraints={},
        validation_errors=[
            FormulatorValidationError(
                field_path="task_type",
                message="router task_type is unknown",
                remediation_hint_key="chat.formulator.task_type_required",
            )
        ],
        supported_task_types=list(SUPPORTED_TASK_TYPES),
    )


def _default_objective(task_type: TaskType) -> dict[str, object]:
    defaults: dict[TaskType, dict[str, object]] = {
        "lp": {},
        "vrptw": {"kind": "minimize_total_distance"},
        "prediction": {"kind": "forecast"},
        "schedule": {"kind": "minimize_makespan"},
        "inventory": {"kind": "forecast_inventory"},
        "unknown": {},
    }
    return dict(defaults[task_type])
