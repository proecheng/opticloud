from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Literal

from chat_service.schemas import (
    ChatWhatIfContext,
    ChatWhatIfDiffItem,
    ChatWhatIfPreview,
    ChatWhatIfSolutionPreview,
    ModelPreview,
)

PROMPT_SUMMARY_MAX_CHARS = 700
FILTERED_VALUE = "[filtered]"
_NO_LEAK_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{4,}|api[_\s-]?key|bearer\s+[A-Za-z0-9._-]+|"
    r"authorization|cookie|password|token|raw[_ -]?(?:response|request|row|value)|"
    r"provider[_ -]?(?:request|response|payload)?|prompt|traceback|"
    r"generated[_ -]?code|sandbox[_ -]?output|"
    r"solver[_ -]?(?:result|response|payload)|route[_ -]?rows?|assignment[_ -]?table|"
    r"full[_ -]?time[_ -]?series|result[_ -]?file[_ -]?path|"
    r"charge[_ -]?id|optimization[_ -]?id|prediction[_ -]?id|callback[_ -]?url|"
    r"[A-Za-z]:\\|/tmp/|/var/|queue[_ -]?payload)",
    re.IGNORECASE,
)
_VEHICLE_DELTA_PATTERN = re.compile(
    r"(车辆数|车数量|vehicles?|vehicle[_\s-]?count).{0,24}?(?P<delta>[+-]\s*\d+)",
    re.IGNORECASE,
)
_VEHICLE_KEYS = ("vehicle_count", "vehicles", "车辆数", "车数量")
_MAX_ABS_DELTA = 1000


def sanitize_what_if_context(context: ChatWhatIfContext | None) -> ChatWhatIfContext | None:
    if context is None:
        return None
    solution = None
    if context.base_solution_preview is not None:
        solution = ChatWhatIfSolutionPreview(
            status=context.base_solution_preview.status,
            objective_value=context.base_solution_preview.objective_value,
            objective_unit=_safe_text(context.base_solution_preview.objective_unit, max_chars=40),
            summary=_safe_text(context.base_solution_preview.summary, max_chars=240) or "",
        )
    return ChatWhatIfContext(
        source=context.source,
        base_message_id=context.base_message_id,
        base_model_preview_id=context.base_model_preview_id,
        task_type=context.task_type,
        variables=_safe_mapping(context.variables, max_keys=40),
        objective=_safe_mapping(context.objective, max_keys=20),
        constraints=_safe_mapping(context.constraints, max_keys=40),
        sandbox_status=context.sandbox_status,
        summary=_safe_text(context.summary, max_chars=360) or "",
        base_solution_preview=solution,
    )


def canonical_what_if_context_digest(context: ChatWhatIfContext | None) -> str:
    sanitized = sanitize_what_if_context(context)
    if sanitized is None:
        return ""
    canonical = json.dumps(
        sanitized.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_what_if_prompt_summary(context: ChatWhatIfContext | None) -> str:
    sanitized = sanitize_what_if_context(context)
    if sanitized is None:
        return ""
    variables = ", ".join(sorted(sanitized.variables)[:8])
    constraints = ", ".join(sorted(sanitized.constraints)[:8])
    objective = ", ".join(sorted(sanitized.objective)[:6])
    solution = ""
    if sanitized.base_solution_preview is not None:
        solution = (
            f", solution_status={sanitized.base_solution_preview.status}, "
            f"objective_value={sanitized.base_solution_preview.objective_value}"
        )
    return (
        f"what_if base model {sanitized.base_model_preview_id}: "
        f"task={sanitized.task_type}, sandbox={sanitized.sandbox_status}, "
        f"variables=[{variables}], objective=[{objective}], constraints=[{constraints}]"
        f"{solution}, summary={sanitized.summary}"
    )[:PROMPT_SUMMARY_MAX_CHARS]


def build_message_with_what_if_context(
    message: str,
    context: ChatWhatIfContext | None,
) -> str:
    summary = build_what_if_prompt_summary(context)
    if not summary:
        return message
    return f"{message}\n\n[what_if_context]\n{summary}"


def build_what_if_preview(
    context: ChatWhatIfContext | None,
    *,
    message: str,
    model_preview: ModelPreview,
) -> ChatWhatIfPreview | None:
    sanitized = sanitize_what_if_context(context)
    if sanitized is None:
        return None

    adjusted_variables = _apply_safe_delta(sanitized.variables, message)
    diff = _build_diff("variables", sanitized.variables, adjusted_variables)
    can_compare_current_preview = (
        model_preview.status == "ready_to_confirm" and model_preview.task_type == sanitized.task_type
    )
    if not diff and can_compare_current_preview:
        diff = _build_diff("objective", sanitized.objective, model_preview.objective)
    if not diff and can_compare_current_preview:
        diff = _build_diff("constraints", sanitized.constraints, model_preview.constraints)

    status: Literal["previewed", "needs_clarification"] = (
        "previewed" if diff else "needs_clarification"
    )
    return ChatWhatIfPreview(
        source="chat_what_if_preview_internal_beta",
        base_message_id=sanitized.base_message_id,
        base_model_preview_id=sanitized.base_model_preview_id,
        status=status,
        task_type=sanitized.task_type,
        change_summary=_change_summary(message, diff_count=len(diff), status=status),
        changed_fields=[item.field_path for item in diff],
        diff=diff,
    )


def _apply_safe_delta(variables: dict[str, object], message: str) -> dict[str, object]:
    adjusted = deepcopy(variables)
    match = _VEHICLE_DELTA_PATTERN.search(message)
    if match is None:
        return adjusted
    delta = int(match.group("delta").replace(" ", ""))
    if abs(delta) > _MAX_ABS_DELTA:
        return adjusted
    for key in _VEHICLE_KEYS:
        current = adjusted.get(key)
        if isinstance(current, int | float) and not isinstance(current, bool):
            adjusted[key] = current + delta
            return adjusted
    return adjusted


def _build_diff(
    prefix: str,
    before: dict[str, object],
    after: dict[str, object],
) -> list[ChatWhatIfDiffItem]:
    items: list[ChatWhatIfDiffItem] = []
    for key in sorted(set(before) | set(after)):
        if len(items) >= 12:
            break
        old = before.get(key)
        new = after.get(key)
        if old == new:
            continue
        field_path = f"{prefix}.{key}"
        if key not in before:
            change_type: Literal["added", "removed", "modified"] = "added"
        elif key not in after:
            change_type = "removed"
        else:
            change_type = "modified"
        items.append(
            ChatWhatIfDiffItem(
                field_path=field_path,
                before=_preview_value(old),
                after=_preview_value(new),
                change_type=change_type,
            )
        )
    return items


def _change_summary(message: str, *, diff_count: int, status: str) -> str:
    if status != "previewed":
        return "What-if follow-up needs a bounded numeric change before previewing a diff."
    if "车辆数" in message or "车数量" in message:
        return f"已根据车辆数变更生成 preview diff，共 {diff_count} 项。"
    return f"Generated bounded what-if preview diff with {diff_count} changed field(s)."


def _safe_mapping(value: dict[str, object], *, max_keys: int) -> dict[str, object]:
    output: dict[str, object] = {}
    for key in sorted(value)[:max_keys]:
        safe_key = _safe_key(str(key))
        if safe_key == FILTERED_VALUE:
            continue
        output[safe_key] = _safe_value(value[key])
    return output


def _safe_key(value: str) -> str:
    clean = value.strip()[:64]
    if (
        not clean
        or _NO_LEAK_PATTERN.search(clean)
        or any(char in clean for char in "\r\n\t")
        or "/" in clean
        or "\\" in clean
        or ":" in clean
        or ".." in clean
    ):
        return FILTERED_VALUE
    return clean


def _safe_value(value: object, *, depth: int = 0) -> object:
    if depth > 4:
        return FILTERED_VALUE
    if isinstance(value, str):
        return _safe_text(value, max_chars=120) or FILTERED_VALUE
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int | float):
        return value
    if isinstance(value, dict):
        return {
            safe_key: _safe_value(child, depth=depth + 1)
            for key, child in sorted(value.items())
            if (safe_key := _safe_key(str(key))) != FILTERED_VALUE
        }
    if isinstance(value, list):
        return [_safe_value(child, depth=depth + 1) for child in value[:40]]
    return FILTERED_VALUE


def _safe_text(value: str | None, *, max_chars: int) -> str | None:
    if value is None:
        return None
    clean = value.strip()[:max_chars]
    if not clean or _NO_LEAK_PATTERN.search(clean) or any(char in clean for char in "\r\n\t"):
        return None
    return clean


def _preview_value(value: object) -> object | None:
    if value is None:
        return None
    safe = _safe_value(value)
    if safe == FILTERED_VALUE:
        return None
    return safe
