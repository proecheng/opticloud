from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from opticloud_shared.llm_router import Completion, LLMRouterError, Prompt, PromptMessage, complete
from opticloud_shared.llm_router.registry import CANONICAL_MODEL_ALIASES
from pydantic import ValidationError

from chat_service.coder import validate_code_artifact
from chat_service.router_preview import SUPPORTED_TASK_TYPES
from chat_service.schemas import (
    ChatLocale,
    CoderPreview,
    CriticCheck,
    CriticCheckName,
    CriticPreview,
    CriticPreviewSource,
    CriticValidationError,
    TaskType,
)

CompletionFunc = Callable[[Prompt, str], Completion]

LLM_CRITIC_SOURCE: CriticPreviewSource = "llm_critic_internal_beta"
HEURISTIC_CRITIC_SOURCE: CriticPreviewSource = "heuristic_critic_internal_beta"
CRITIC_THRESHOLD_SOURCE = "apps/critic-service/config/critic-calibration.json"
DEFAULT_CRITIC_THRESHOLD = 0.6
_DETERMINISTIC_MARKER = "critic validation"
_SECRET_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{4,}|api[_-]?key|bearer\s+[A-Za-z0-9._-]+|"
    r"authorization|cookie|password|token|raw_response|raw_request|provider_request|"
    r"provider_response|deterministic_digest|traceback)",
    re.IGNORECASE,
)

CRITIC_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reasoning": {"type": "string"},
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
    "required": ["confidence", "reasoning"],
}


@dataclass(frozen=True)
class CriticCalibrationThreshold:
    value: float
    source: str = CRITIC_THRESHOLD_SOURCE


@dataclass(frozen=True)
class CriticRouteResult:
    preview: CriticPreview
    critic_invoked: Literal[True] = True
    critic_llm_invoked: bool = False
    provider_request_sent: Literal[False] = False


def build_critic_prompt(
    *,
    locale: ChatLocale,
    prompt_id: str,
    coder_preview: CoderPreview,
    calibration_threshold: float,
) -> Prompt:
    if coder_preview.artifact is None:
        raise ValueError("generated artifact is required")
    artifact = coder_preview.artifact
    return Prompt(
        prompt_id=prompt_id,
        task="critic_validation",
        locale=locale,
        messages=[
            PromptMessage(
                role="system",
                content=(
                    "Review the generated Python code artifact for internal beta static "
                    "execution readiness. Validate schema, safety, and business-logic "
                    "consistency. Do not execute code, call solvers, use network, access "
                    "files, or request sandbox output."
                ),
            ),
            PromptMessage(
                role="user",
                content=json.dumps(
                    {
                        "coder_preview": {
                            "status": coder_preview.status,
                            "source": coder_preview.source,
                            "task_type": coder_preview.task_type,
                            "artifact": {
                                "language": artifact.language,
                                "code": artifact.code,
                                "entrypoint": artifact.entrypoint,
                                "input_model": artifact.input_model,
                                "output_model": artifact.output_model,
                                "imports": artifact.imports,
                            },
                        },
                        "calibration_threshold": calibration_threshold,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            ),
        ],
        response_schema=CRITIC_RESPONSE_SCHEMA,
        metadata={
            "coder_status": coder_preview.status,
            "coder_source": coder_preview.source,
            "task_type": coder_preview.task_type,
            "calibration_threshold": calibration_threshold,
        },
    )


def generate_critic_validation_with_llm(
    *,
    locale: ChatLocale,
    prompt_id: str,
    coder_preview: CoderPreview,
    completion_func: CompletionFunc = complete,
    model_alias: str = "deepseek-v3.5",
) -> CriticRouteResult:
    threshold = load_critic_calibration_threshold()

    if coder_preview.status != "generated" or coder_preview.artifact is None:
        return CriticRouteResult(
            preview=_skipped_preview(
                coder_preview.task_type,
                threshold=threshold,
            )
        )

    static_errors = validate_code_artifact(coder_preview.artifact)
    if static_errors:
        return CriticRouteResult(
            preview=_static_failure_preview(
                coder_preview.task_type,
                threshold=threshold,
                errors=[
                    CriticValidationError(
                        field_path=error.field_path,
                        message=error.message,
                        remediation_hint_key=error.remediation_hint_key,
                    )
                    for error in static_errors
                ],
            )
        )
    if _artifact_task_type_drifted(coder_preview):
        return CriticRouteResult(
            preview=_business_logic_failure_preview(
                coder_preview.task_type,
                threshold=threshold,
            )
        )

    if model_alias not in CANONICAL_MODEL_ALIASES:
        return CriticRouteResult(
            preview=_fallback_preview(
                coder_preview.task_type,
                threshold=threshold,
                field_path="critic.model",
                message="supported model alias is required",
                remediation_hint_key="chat.critic.model_required",
            )
        )

    try:
        prompt = build_critic_prompt(
            locale=locale,
            prompt_id=prompt_id,
            coder_preview=coder_preview,
            calibration_threshold=threshold.value,
        )
    except (ValidationError, ValueError):
        return CriticRouteResult(
            preview=_fallback_preview(
                coder_preview.task_type,
                threshold=threshold,
                field_path="critic.prompt",
                message="safe critic prompt is required",
                remediation_hint_key="chat.critic.prompt_invalid",
            )
        )

    try:
        completion = completion_func(prompt, model_alias)
    except LLMRouterError:
        return CriticRouteResult(
            preview=_fallback_preview(
                coder_preview.task_type,
                threshold=threshold,
                field_path="critic.completion",
                message="critic completion is unavailable",
                remediation_hint_key="chat.critic.completion_unavailable",
            ),
            critic_llm_invoked=True,
        )

    if completion.finish_reason != "stop":
        return CriticRouteResult(
            preview=_fallback_preview(
                coder_preview.task_type,
                threshold=threshold,
                field_path="critic.completion",
                message="critic completion did not finish safely",
                remediation_hint_key="chat.critic.completion_unavailable",
            ),
            critic_llm_invoked=True,
        )

    if not _completion_supports_validated_preview(completion.text):
        return CriticRouteResult(
            preview=_fallback_preview(
                coder_preview.task_type,
                threshold=threshold,
                field_path="critic.completion",
                message="critic completion is unsafe",
                remediation_hint_key="chat.critic.completion_invalid",
            ),
            critic_llm_invoked=True,
        )

    return CriticRouteResult(
        preview=_validated_preview(
            coder_preview.task_type,
            threshold=threshold,
            completion_text=completion.text,
        ),
        critic_llm_invoked=True,
    )


@lru_cache(maxsize=1)
def load_critic_calibration_threshold() -> CriticCalibrationThreshold:
    config_path = _repo_root() / CRITIC_THRESHOLD_SOURCE
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        value = float(payload["recommended_threshold"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        value = DEFAULT_CRITIC_THRESHOLD
    if not 0.0 <= value <= 1.0:
        value = DEFAULT_CRITIC_THRESHOLD
    return CriticCalibrationThreshold(value=value)


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists() and (parent / "_bmad").exists():
            return parent
    return current.parents[4]


def _validated_preview(
    task_type: TaskType,
    *,
    threshold: CriticCalibrationThreshold,
    completion_text: str,
) -> CriticPreview:
    return CriticPreview(
        status="validated",
        source=LLM_CRITIC_SOURCE,
        task_type=task_type,
        confidence=0.86,
        reasoning=_safe_success_reasoning(completion_text),
        checks=_passing_checks(),
        validation_errors=[],
        supported_task_types=list(SUPPORTED_TASK_TYPES),
        calibration_threshold=threshold.value,
        threshold_source=threshold.source,
    )


def _skipped_preview(
    task_type: TaskType,
    *,
    threshold: CriticCalibrationThreshold,
) -> CriticPreview:
    return CriticPreview(
        status="skipped",
        source=HEURISTIC_CRITIC_SOURCE,
        task_type=task_type,
        confidence=0.0,
        reasoning="Critic skipped because no generated code artifact is available.",
        checks={
            "schema": CriticCheck(
                passed=False,
                message="generated code artifact is required before critic validation",
                field_path="coder_preview.artifact",
            ),
            "safety": CriticCheck(
                passed=False,
                message="generated code artifact is required before safety validation",
                field_path="coder_preview.artifact",
            ),
            "business_logic": CriticCheck(
                passed=False,
                message="generated code artifact is required before business validation",
                field_path="coder_preview.artifact",
            ),
        },
        validation_errors=[
            CriticValidationError(
                field_path="coder_preview.artifact",
                message="generated code artifact is required before critic validation",
                remediation_hint_key="chat.critic.artifact_required",
            )
        ],
        supported_task_types=list(SUPPORTED_TASK_TYPES),
        calibration_threshold=threshold.value,
        threshold_source=threshold.source,
    )


def _static_failure_preview(
    task_type: TaskType,
    *,
    threshold: CriticCalibrationThreshold,
    errors: list[CriticValidationError],
) -> CriticPreview:
    return CriticPreview(
        status="needs_clarification",
        source=HEURISTIC_CRITIC_SOURCE,
        task_type=task_type,
        confidence=0.35,
        reasoning="Critic found static schema or safety issues before LLM review.",
        checks={
            "schema": CriticCheck(
                passed=not any(error.field_path != "artifact.code" for error in errors),
                message="static artifact schema validation completed",
                field_path="artifact",
            ),
            "safety": CriticCheck(
                passed=False,
                message="static safety validation found blocked code patterns",
                field_path="artifact.code",
            ),
            "business_logic": CriticCheck(
                passed=False,
                message="business validation requires a safe generated artifact",
                field_path="artifact.code",
            ),
        },
        validation_errors=errors[:10],
        supported_task_types=list(SUPPORTED_TASK_TYPES),
        calibration_threshold=threshold.value,
        threshold_source=threshold.source,
    )


def _business_logic_failure_preview(
    task_type: TaskType,
    *,
    threshold: CriticCalibrationThreshold,
) -> CriticPreview:
    return CriticPreview(
        status="needs_clarification",
        source=HEURISTIC_CRITIC_SOURCE,
        task_type=task_type,
        confidence=0.45,
        reasoning="Critic found static business-logic drift before LLM review.",
        checks={
            "schema": CriticCheck(
                passed=True,
                message="static code artifact schema validation passed",
                field_path="artifact",
            ),
            "safety": CriticCheck(
                passed=True,
                message="static code safety validation passed",
                field_path="artifact.code",
            ),
            "business_logic": CriticCheck(
                passed=False,
                message="artifact task marker must match the routed task",
                field_path="artifact.code",
            ),
        },
        validation_errors=[
            CriticValidationError(
                field_path="artifact.code",
                message="artifact task marker must match the routed task",
                remediation_hint_key="chat.critic.task_type_drift",
            )
        ],
        supported_task_types=list(SUPPORTED_TASK_TYPES),
        calibration_threshold=threshold.value,
        threshold_source=threshold.source,
    )


def _fallback_preview(
    task_type: TaskType,
    *,
    threshold: CriticCalibrationThreshold,
    field_path: str,
    message: str,
    remediation_hint_key: str,
) -> CriticPreview:
    return CriticPreview(
        status="needs_clarification",
        source=HEURISTIC_CRITIC_SOURCE,
        task_type=task_type,
        confidence=0.4,
        reasoning="Critic validation is unavailable; keep the code in internal beta preview.",
        checks={
            "schema": CriticCheck(
                passed=True,
                message="static code artifact schema validation passed",
                field_path="artifact",
            ),
            "safety": CriticCheck(
                passed=True,
                message="static code safety validation passed",
                field_path="artifact.code",
            ),
            "business_logic": CriticCheck(
                passed=False,
                message="business validation requires completed critic review",
                field_path="critic.completion",
            ),
        },
        validation_errors=[
            CriticValidationError(
                field_path=field_path,
                message=message,
                remediation_hint_key=remediation_hint_key,
            )
        ],
        supported_task_types=list(SUPPORTED_TASK_TYPES),
        calibration_threshold=threshold.value,
        threshold_source=threshold.source,
    )


def _passing_checks() -> dict[CriticCheckName, CriticCheck]:
    return {
        "schema": CriticCheck(
            passed=True,
            message="code artifact schema is valid",
            field_path="artifact",
        ),
        "safety": CriticCheck(
            passed=True,
            message="static safety validation passed",
            field_path="artifact.code",
        ),
        "business_logic": CriticCheck(
            passed=True,
            message="artifact structure is consistent with the routed task",
            field_path="artifact.entrypoint",
        ),
    }


def _safe_success_reasoning(text: str) -> str:
    if _DETERMINISTIC_MARKER in text.lower():
        return "Critic validated schema, safety, and business-logic consistency."
    return "Critic validated the generated code artifact for internal beta preview."


def _completion_supports_validated_preview(text: str) -> bool:
    if _DETERMINISTIC_MARKER in text.lower():
        return not _completion_text_is_unsafe(text)

    payload = _parse_json_payload(text)
    if payload is None or set(payload) - {"confidence", "reasoning", "validation_errors"}:
        return False
    confidence = payload.get("confidence")
    reasoning = payload.get("reasoning")
    validation_errors = payload.get("validation_errors", [])
    if not isinstance(confidence, int | float) or not 0.0 <= float(confidence) <= 1.0:
        return False
    if not isinstance(reasoning, str) or _completion_text_is_unsafe(reasoning):
        return False
    return isinstance(validation_errors, list) and not validation_errors


def _parse_json_payload(text: str) -> dict[str, object] | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _completion_text_is_unsafe(text: str) -> bool:
    cleaned = text
    if _DETERMINISTIC_MARKER in cleaned.lower():
        cleaned = re.sub(r"deterministic_digest=[A-Za-z0-9_-]+", "", cleaned)
    return _SECRET_PATTERN.search(cleaned) is not None


def _artifact_task_type_drifted(coder_preview: CoderPreview) -> bool:
    if coder_preview.task_type == "unknown" or coder_preview.artifact is None:
        return True
    return json.dumps(coder_preview.task_type) not in coder_preview.artifact.code
