from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from opticloud_shared.llm_router import Completion, LLMRouterError, Prompt, PromptMessage, complete
from opticloud_shared.llm_router.registry import CANONICAL_MODEL_ALIASES
from pydantic import ValidationError

from chat_service.router_preview import SUPPORTED_TASK_TYPES, classify_message
from chat_service.schemas import ChatLocale, RouterPreview, RouterPreviewSource

CompletionFunc = Callable[[Prompt, str], Completion]

LLM_ROUTER_SOURCE: RouterPreviewSource = "llm_router_internal_beta"
REASONING_MAX_CHARS = 96
_CONFIDENCE_CONFLICT_THRESHOLD = 0.95
_DETERMINISTIC_PATTERN = re.compile(
    r"task_type=(?P<task_type>[a-z_]+)\s+confidence=(?P<confidence>[0-9.]+)\s+reasoning=(?P<reasoning>.*)",
    re.IGNORECASE,
)
_SECRET_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{4,}|api[_-]?key|bearer\s+[A-Za-z0-9._-]+|"
    r"authorization|cookie|password|token|raw_response|provider_request|provider_response)",
    re.IGNORECASE,
)

ROUTER_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "task_type": {"type": "string", "enum": list(SUPPORTED_TASK_TYPES)},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reasoning": {"type": "string"},
    },
    "required": ["task_type", "confidence", "reasoning"],
}


@dataclass(frozen=True)
class IntentRouteResult:
    preview: RouterPreview
    llm_invoked: bool
    provider_request_sent: Literal[False] = False


def build_router_prompt(*, message: str, locale: ChatLocale, prompt_id: str) -> Prompt:
    return Prompt(
        prompt_id=prompt_id,
        task="router_intent",
        locale=locale,
        messages=[
            PromptMessage(
                role="system",
                content=(
                    "Classify the optimization intent. Return only task_type, confidence, "
                    "and short reasoning."
                ),
            ),
            PromptMessage(role="user", content=message),
        ],
        response_schema=ROUTER_RESPONSE_SCHEMA,
        metadata={},
    )


def parse_router_completion(
    text: str, *, original_message: str | None = None
) -> RouterPreview | None:
    payload = _parse_json_payload(text) or _parse_deterministic_payload(text)
    if payload is None:
        return None

    task_type = payload.get("task_type")
    confidence = payload.get("confidence")
    reasoning = payload.get("reasoning")

    if task_type not in SUPPORTED_TASK_TYPES:
        return None
    if not isinstance(confidence, int | float) or not 0.0 <= float(confidence) <= 1.0:
        return None
    if not isinstance(reasoning, str):
        return None

    safe_reasoning = _safe_reasoning(reasoning, original_message=original_message)
    if safe_reasoning is None:
        return None

    return RouterPreview(
        task_type=task_type,
        confidence=float(confidence),
        reasoning=safe_reasoning,
        source=LLM_ROUTER_SOURCE,
        supported_task_types=list(SUPPORTED_TASK_TYPES),
    )


def route_intent_with_llm(
    *,
    message: str,
    locale: ChatLocale,
    prompt_id: str,
    completion_func: CompletionFunc = complete,
    model_alias: str = "deepseek-v3.5",
) -> IntentRouteResult:
    heuristic = classify_message(message)
    if model_alias not in CANONICAL_MODEL_ALIASES:
        return IntentRouteResult(preview=heuristic, llm_invoked=False)

    try:
        prompt = build_router_prompt(message=message, locale=locale, prompt_id=prompt_id)
    except ValidationError:
        return IntentRouteResult(preview=heuristic, llm_invoked=False)

    try:
        completion = completion_func(prompt, model_alias)
    except LLMRouterError:
        return IntentRouteResult(preview=heuristic, llm_invoked=True)

    if completion.finish_reason != "stop":
        return IntentRouteResult(preview=heuristic, llm_invoked=True)

    preview = parse_router_completion(completion.text, original_message=message)
    if preview is None or _should_fallback_to_heuristic(preview, heuristic):
        return IntentRouteResult(preview=heuristic, llm_invoked=True)

    return IntentRouteResult(preview=preview, llm_invoked=True)


def _parse_json_payload(text: str) -> dict[str, object] | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _parse_deterministic_payload(text: str) -> dict[str, object] | None:
    match = _DETERMINISTIC_PATTERN.search(text)
    if match is None:
        return None
    try:
        confidence = float(match.group("confidence"))
    except ValueError:
        return None
    return {
        "task_type": match.group("task_type"),
        "confidence": confidence,
        "reasoning": match.group("reasoning"),
    }


def _safe_reasoning(reasoning: str, *, original_message: str | None) -> str | None:
    cleaned = reasoning.strip()
    if not cleaned:
        return None
    if "deterministic_digest=" in cleaned:
        return "matched LLM router intent output"
    if (
        original_message is not None
        and original_message.strip()
        and original_message.strip() in cleaned
    ):
        return None
    if _SECRET_PATTERN.search(cleaned):
        return None
    return cleaned[:REASONING_MAX_CHARS]


def _should_fallback_to_heuristic(llm: RouterPreview, heuristic: RouterPreview) -> bool:
    if heuristic.task_type == "unknown":
        return llm.task_type != "unknown"
    if llm.task_type == "unknown":
        return True
    return llm.task_type != heuristic.task_type and llm.confidence < _CONFIDENCE_CONFLICT_THRESHOLD
