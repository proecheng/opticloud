"""LLM provider implementations for the offline M3.8 router contract."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from opticloud_shared.llm_router.registry import ModelConfig
from opticloud_shared.llm_router.schemas import Completion, CompletionUsage, FinishReason, Prompt

OpenAIEnvelope = Mapping[str, Any]
Transport = Callable[[Prompt, ModelConfig], OpenAIEnvelope]
ApiKeyProvider = Callable[[], str]


class LLMRouterError(RuntimeError):
    """Raised when router/provider completion fails closed."""


class LLMProvider(Protocol):
    """Provider interface shared by all implementations."""

    provider_id: str
    implementation_id: str

    def complete(self, prompt: Prompt, model_config: ModelConfig) -> Completion: ...


_FINISH_REASON_MAP = {
    "stop": "stop",
    "length": "length",
    "max_tokens": "length",
    "content_filter": "content_filter",
    "safety": "content_filter",
    "error": "error",
}
_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{4,}|api[_-]?key\s*[:=]\s*\S+|bearer\s+[A-Za-z0-9._-]+|"
    r"authorization\s*:\s*\S+(?:\s+\S+)?|cookie\s*=\s*\S+|password\s*[:=]\s*\S+)",
    re.IGNORECASE,
)


class MockLLMProvider:
    """Deterministic local provider used for tests and fallback-free contracts."""

    provider_id = "mock"
    implementation_id = "mock-deterministic"

    def complete(self, prompt: Prompt, model_config: ModelConfig) -> Completion:
        text = deterministic_completion_text(prompt, model_config.alias, style="mock")
        return Completion(
            text=text,
            model=model_config.alias,
            provider=self.provider_id,
            finish_reason="stop",
            usage=_estimate_usage(prompt, text),
            raw_response_redacted=_diagnostics(prompt, model_config, self.provider_id),
        )


class OpenAICompatibleProvider:
    """Base class for OpenAI-compatible deterministic adapters."""

    provider_id: str
    implementation_id: str
    _style: str

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key_provider: ApiKeyProvider | None = None,
        transport: Transport | None = None,
    ) -> None:
        self.base_url = base_url
        self._api_key_provider = api_key_provider
        self._transport = transport or self._offline_transport

    def complete(self, prompt: Prompt, model_config: ModelConfig) -> Completion:
        try:
            envelope = self._transport(prompt, model_config)
        except Exception as exc:  # noqa: BLE001 - provider boundary must fail closed.
            raise LLMRouterError(
                f"{self.provider_id} completion failed: {_redact(str(exc))}"
            ) from exc

        try:
            text, finish_reason = _extract_openai_choice(envelope)
            usage = _normalize_usage(envelope.get("usage"), prompt, text)
        except Exception as exc:  # noqa: BLE001 - convert provider payload errors to router errors.
            raise LLMRouterError(f"{self.provider_id} returned malformed envelope") from exc

        return Completion(
            text=text,
            model=model_config.alias,
            provider=self.provider_id,
            finish_reason=finish_reason,
            usage=usage,
            raw_response_redacted=_diagnostics(prompt, model_config, self.provider_id),
        )

    def _offline_transport(self, prompt: Prompt, model_config: ModelConfig) -> OpenAIEnvelope:
        text = deterministic_completion_text(prompt, model_config.alias, style=self._style)
        usage = _estimate_usage(prompt, text)
        return {
            "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
            "usage": usage.model_dump(),
        }


class DeepSeekCompatibleProvider(OpenAICompatibleProvider):
    """DeepSeek OpenAI-compatible adapter with deterministic offline default."""

    provider_id = "deepseek-compatible"
    implementation_id = "deepseek-openai-compatible"
    _style = "deepseek"


class QwenCompatibleProvider(OpenAICompatibleProvider):
    """Qwen/DashScope OpenAI-compatible adapter with deterministic offline default."""

    provider_id = "qwen-compatible"
    implementation_id = "qwen-openai-compatible"
    _style = "qwen"


def deterministic_completion_text(prompt: Prompt, alias: str, *, style: str) -> str:
    """Generate task-aware deterministic text from prompt content."""
    prompt_text = " ".join(message.content for message in prompt.messages)
    digest = hashlib.sha256(
        json.dumps(prompt.model_dump(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    task = prompt.task
    locale = prompt.locale
    summary = _summarize_prompt(prompt_text)
    shared_contract_terms = (
        "provider agnostic schema completion usage normalized prompt task offline deterministic "
        "parity validation routing reasoning constraints objective confidence safety"
    )
    task_outputs = {
        "router_intent": (
            "router decision task_type=vrptw confidence=0.92 reasoning="
            f"{summary} deterministic_digest={digest}"
        ),
        "formulator_extraction": (
            "formulator extraction variables constraints objective normalized_model="
            f"{summary} deterministic_digest={digest}"
        ),
        "coder_generation": (
            "coder generation python function validation deterministic implementation "
            f"{summary} deterministic_digest={digest}"
        ),
        "critic_validation": (
            "critic validation schema logic safety confidence calibrated review "
            f"{summary} deterministic_digest={digest}"
        ),
        "mixed_language_summary": (
            "mixed language summary 中文 English concise business result "
            f"{summary} deterministic_digest={digest}"
        ),
    }
    base = task_outputs.get(task, f"generic llm response {summary} deterministic_digest={digest}")
    return f"{base} {shared_contract_terms} locale={locale} provider_variant={style} alias={alias}"


def _extract_openai_choice(envelope: OpenAIEnvelope) -> tuple[str, FinishReason]:
    choices = envelope.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("missing choices")
    first = choices[0]
    if not isinstance(first, Mapping):
        raise ValueError("choice must be mapping")

    raw_text: Any
    message = first.get("message")
    if isinstance(message, Mapping):
        raw_text = message.get("content")
    else:
        raw_text = first.get("text")

    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ValueError("missing normalized text")

    raw_finish = first.get("finish_reason", "stop")
    finish_reason = _FINISH_REASON_MAP.get(str(raw_finish), "error")
    return raw_text.strip(), finish_reason  # type: ignore[return-value]


def _normalize_usage(value: object, prompt: Prompt, text: str) -> CompletionUsage:
    estimated = _estimate_usage(prompt, text)
    if not isinstance(value, Mapping):
        return estimated
    prompt_tokens = _coerce_non_negative_int(value.get("prompt_tokens"), estimated.prompt_tokens)
    completion_tokens = _coerce_non_negative_int(
        value.get("completion_tokens"), estimated.completion_tokens
    )
    total_raw = value.get("total_tokens")
    total_tokens = (
        _coerce_non_negative_int(total_raw, prompt_tokens + completion_tokens)
        if total_raw is not None
        else prompt_tokens + completion_tokens
    )
    return CompletionUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def _coerce_non_negative_int(value: object, fallback: int) -> int:
    if isinstance(value, int) and value >= 0:
        return value
    return fallback


def _estimate_usage(prompt: Prompt, text: str) -> CompletionUsage:
    prompt_tokens = sum(_token_count(message.content) for message in prompt.messages)
    completion_tokens = _token_count(text)
    return CompletionUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )


def _token_count(text: str) -> int:
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    return max(len(tokens), 1)


def _summarize_prompt(text: str) -> str:
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    selected = tokens[:12] or ["empty"]
    return "_".join(selected)


def _diagnostics(prompt: Prompt, model_config: ModelConfig, provider_id: str) -> dict[str, str]:
    prompt_digest = hashlib.sha256(
        json.dumps(prompt.model_dump(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "logical_alias": model_config.alias,
        "provider_id": provider_id,
        "implementation_id": model_config.implementation_id,
        "provider_model": model_config.provider_model,
        "finish_reason": "stop",
        "prompt_sha256": prompt_digest,
        "transport": "offline-deterministic",
    }


def _redact(message: str) -> str:
    return _SECRET_RE.sub("[redacted]", message)


__all__ = [
    "DeepSeekCompatibleProvider",
    "LLMProvider",
    "LLMRouterError",
    "MockLLMProvider",
    "OpenAICompatibleProvider",
    "QwenCompatibleProvider",
    "Transport",
    "deterministic_completion_text",
]
