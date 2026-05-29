from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence

from chat_service.schemas import (
    CoderPreview,
    CriticPreview,
    FormulatorPreview,
    HumanReviewPreview,
    ModelPreview,
    ModelPreviewAction,
    ModelPreviewDisabledReasonCode,
    ModelPreviewStatus,
    ModelPreviewValidationError,
    SandboxPreview,
    TaskType,
)

_NO_LEAK_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{4,}|api[_\s-]?key|bearer\s+[A-Za-z0-9._-]+|"
    r"authorization|cookie|password|token|raw[_ -]?(?:response|request)|"
    r"provider[_ -]?(?:request|response|payload)?|prompt|traceback|"
    r"generated[_ -]?code|sandbox[_ -]?output|"
    r"[A-Za-z]:\\|/tmp/|/var/|queue[_ -]?payload)",
    re.IGNORECASE,
)

_ERROR_ORDER = (
    "formulator_preview",
    "coder_preview",
    "critic_preview",
    "human_review",
    "sandbox_preview",
    "model_preview",
)


def generate_model_preview(
    *,
    prompt_id: str,
    formulator_preview: FormulatorPreview,
    coder_preview: CoderPreview,
    critic_preview: CriticPreview,
    sandbox_preview: SandboxPreview,
    human_review: HumanReviewPreview,
    sandbox_invoked: bool,
) -> ModelPreview:
    status, reason = _resolve_status_and_confirm_reason(
        formulator_preview=formulator_preview,
        coder_preview=coder_preview,
        critic_preview=critic_preview,
        sandbox_preview=sandbox_preview,
        human_review=human_review,
        sandbox_invoked=sandbox_invoked,
    )
    validation_errors = _collect_validation_errors(
        formulator_preview=formulator_preview,
        coder_preview=coder_preview,
        critic_preview=critic_preview,
        sandbox_preview=sandbox_preview,
        human_review=human_review,
        sandbox_invoked=sandbox_invoked,
    )
    return ModelPreview(
        preview_id=_preview_id(
            prompt_id=prompt_id,
            task_type=formulator_preview.task_type,
            formulator_preview=formulator_preview,
            coder_preview=coder_preview,
            critic_preview=critic_preview,
            sandbox_preview=sandbox_preview,
            confirm_enabled=status == "ready_to_confirm",
        ),
        status=status,
        source="chat_model_preview_internal_beta",
        task_type=formulator_preview.task_type,
        variables=dict(formulator_preview.variables),
        objective=dict(formulator_preview.objective),
        constraints=dict(formulator_preview.constraints),
        code_artifact=coder_preview.artifact if coder_preview.status == "generated" else None,
        actions=_actions(confirm_enabled=status == "ready_to_confirm", reason=reason),
        requires_human_review=human_review.escalated,
        critic_confidence=critic_preview.confidence,
        sandbox_status=sandbox_preview.status,
        validation_errors=validation_errors,
    )


def _resolve_status_and_confirm_reason(
    *,
    formulator_preview: FormulatorPreview,
    coder_preview: CoderPreview,
    critic_preview: CriticPreview,
    sandbox_preview: SandboxPreview,
    human_review: HumanReviewPreview,
    sandbox_invoked: bool,
) -> tuple[ModelPreviewStatus, ModelPreviewDisabledReasonCode | None]:
    if _has_dependency_drift(formulator_preview, coder_preview, critic_preview, sandbox_preview):
        return "blocked", "dependency_drift"
    if formulator_preview.task_type == "unknown":
        return "needs_clarification", "task_type_unknown"
    if human_review.escalated:
        return "blocked", "human_review_required"
    if critic_preview.status != "validated" or not all(
        check.passed for check in critic_preview.checks.values()
    ):
        return "blocked", "safety_gate_blocked"
    if sandbox_preview.status != "succeeded" or not sandbox_invoked:
        return "blocked", "sandbox_not_succeeded"
    if formulator_preview.status != "extracted" or coder_preview.status != "generated":
        return "needs_clarification", "needs_clarification"
    if coder_preview.artifact is None:
        return "needs_clarification", "model_not_ready"
    return "ready_to_confirm", None


def _has_dependency_drift(
    formulator_preview: FormulatorPreview,
    coder_preview: CoderPreview,
    critic_preview: CriticPreview,
    sandbox_preview: SandboxPreview,
) -> bool:
    task_types = [
        formulator_preview.task_type,
        coder_preview.task_type,
        critic_preview.task_type,
        sandbox_preview.task_type,
    ]
    known = [task_type for task_type in task_types if task_type != "unknown"]
    return bool(known) and any(task_type != known[0] for task_type in known)


def _collect_validation_errors(
    *,
    formulator_preview: FormulatorPreview,
    coder_preview: CoderPreview,
    critic_preview: CriticPreview,
    sandbox_preview: SandboxPreview,
    human_review: HumanReviewPreview,
    sandbox_invoked: bool,
) -> list[ModelPreviewValidationError]:
    errors: list[ModelPreviewValidationError] = []

    errors.extend(
        _copy_errors(
            prefix="formulator_preview",
            errors=formulator_preview.validation_errors,
        )
    )
    errors.extend(_copy_errors(prefix="coder_preview", errors=coder_preview.validation_errors))
    errors.extend(_copy_errors(prefix="critic_preview", errors=critic_preview.validation_errors))
    if human_review.escalated:
        errors.append(
            _validation_error(
                "human_review.reason_code",
                "human review is required before model confirmation",
                "chat.model_preview.human_review_required",
            )
        )
    errors.extend(_copy_errors(prefix="sandbox_preview", errors=sandbox_preview.validation_errors))

    if _has_dependency_drift(formulator_preview, coder_preview, critic_preview, sandbox_preview):
        errors.append(
            _validation_error(
                "model_preview.task_type",
                "upstream preview task types must match before model confirmation",
                "chat.model_preview.dependency_drift",
            )
        )
    if formulator_preview.task_type == "unknown":
        errors.append(
            _validation_error(
                "model_preview.task_type",
                "known task type is required before model confirmation",
                "chat.model_preview.task_type_required",
            )
        )
    if sandbox_preview.status == "succeeded" and not sandbox_invoked:
        errors.append(
            _validation_error(
                "model_preview.sandbox_invoked",
                "succeeded sandbox preview must have sandbox invocation evidence",
                "chat.model_preview.sandbox_invocation_required",
            )
        )

    return _sort_and_limit_errors(errors)


def _copy_errors(
    *,
    prefix: str,
    errors: Sequence[object],
) -> list[ModelPreviewValidationError]:
    copied: list[ModelPreviewValidationError] = []
    for error in errors:
        field_path = str(getattr(error, "field_path", "validation_errors"))
        message = str(getattr(error, "message", "upstream preview requires attention"))
        remediation_hint_key = getattr(error, "remediation_hint_key", None)
        copied.append(
            _validation_error(
                f"{prefix}.{field_path}",
                message,
                str(remediation_hint_key) if remediation_hint_key else None,
            )
        )
    return copied


def _sort_and_limit_errors(
    errors: list[ModelPreviewValidationError],
) -> list[ModelPreviewValidationError]:
    def sort_key(error: ModelPreviewValidationError) -> tuple[int, str]:
        for index, prefix in enumerate(_ERROR_ORDER):
            if error.field_path == prefix or error.field_path.startswith(f"{prefix}."):
                return index, error.field_path
        return len(_ERROR_ORDER), error.field_path

    deduped: list[ModelPreviewValidationError] = []
    seen: set[tuple[str, str]] = set()
    for error in sorted(errors, key=sort_key):
        key = (error.field_path, error.message)
        if key not in seen:
            seen.add(key)
            deduped.append(error)
    return deduped[:10]


def _actions(
    *,
    confirm_enabled: bool,
    reason: ModelPreviewDisabledReasonCode | None,
) -> list[ModelPreviewAction]:
    return [
        ModelPreviewAction(
            kind="confirm",
            label_zh="确认模型",
            label_en="Confirm model",
            enabled=confirm_enabled,
            client_action="chat.model_preview.confirm",
            disabled_reason_code=None if confirm_enabled else reason or "model_not_ready",
        ),
        ModelPreviewAction(
            kind="edit",
            label_zh="编辑模型",
            label_en="Edit model",
            enabled=True,
            client_action="chat.model_preview.edit",
            disabled_reason_code=None,
        ),
        ModelPreviewAction(
            kind="cancel",
            label_zh="取消",
            label_en="Cancel",
            enabled=True,
            client_action="chat.model_preview.cancel",
            disabled_reason_code=None,
        ),
    ]


def _preview_id(
    *,
    prompt_id: str,
    task_type: TaskType,
    formulator_preview: FormulatorPreview,
    coder_preview: CoderPreview,
    critic_preview: CriticPreview,
    sandbox_preview: SandboxPreview,
    confirm_enabled: bool,
) -> str:
    code = coder_preview.artifact.code if coder_preview.artifact is not None else ""
    payload = {
        "prompt_id": prompt_id,
        "task_type": task_type,
        "variables": formulator_preview.variables,
        "objective": formulator_preview.objective,
        "constraints": formulator_preview.constraints,
        "code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest() if code else None,
        "critic_confidence": critic_preview.confidence,
        "sandbox_status": sandbox_preview.status,
        "confirm_enabled": confirm_enabled,
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return f"mpv_{digest[:16]}"


def _validation_error(
    field_path: str,
    message: str,
    remediation_hint_key: str | None,
) -> ModelPreviewValidationError:
    safe_message = _safe_text(message, fallback="model preview requires attention")
    safe_hint = _safe_text(remediation_hint_key, fallback=None) if remediation_hint_key else None
    return ModelPreviewValidationError(
        field_path=field_path,
        message=(safe_message or "model preview requires attention")[:160],
        remediation_hint_key=safe_hint[:128] if safe_hint else None,
    )


def _safe_text(value: str | None, *, fallback: str | None) -> str | None:
    if value is None:
        return fallback
    stripped = (
        value.strip()
        .replace("generated code artifact", "code artifact")
        .replace("generated code", "code")
    )
    if not stripped or _NO_LEAK_PATTERN.search(stripped):
        return fallback
    return stripped
