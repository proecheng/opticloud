"""Provider-agnostic LLM router API for Story M3.8."""

from __future__ import annotations

from collections.abc import Mapping

from opticloud_shared.llm_router.providers import (
    DeepSeekCompatibleProvider,
    LLMProvider,
    LLMRouterError,
    MockLLMProvider,
    QwenCompatibleProvider,
)
from opticloud_shared.llm_router.registry import (
    ModelConfig,
    default_model_registry,
)
from opticloud_shared.llm_router.schemas import Completion, Prompt


class LLMRouter:
    """Route logical model aliases to provider implementations."""

    def __init__(
        self,
        *,
        providers: Mapping[str, LLMProvider],
        model_registry: Mapping[str, ModelConfig],
        unavailable_aliases: set[str] | None = None,
        fallback_map: Mapping[str, str] | None = None,
    ) -> None:
        self._providers = dict(providers)
        self._model_registry = dict(model_registry)
        self._unavailable_aliases = unavailable_aliases or set()
        self._fallback_map = dict(fallback_map or {"deepseek-v3.5": "qwen-max"})

    def complete(self, prompt: Prompt, model: str) -> Completion:
        alias = model.strip()
        if alias not in self._model_registry:
            raise LLMRouterError(f"unknown model alias: {alias}")

        effective_alias = self._effective_alias(alias)
        model_config = self._model_registry[effective_alias]
        provider = self._providers.get(model_config.provider_id)
        if provider is None:
            raise LLMRouterError(f"missing provider implementation: {model_config.provider_id}")

        completion = provider.complete(prompt, model_config)
        if effective_alias != alias:
            redacted = dict(completion.raw_response_redacted or {})
            redacted.update(
                {
                    "fallback_from": alias,
                    "fallback_to": effective_alias,
                    "fallback_reason": "primary_unavailable",
                }
            )
            completion = completion.model_copy(update={"raw_response_redacted": redacted})
        return completion

    def _effective_alias(self, alias: str) -> str:
        if alias not in self._unavailable_aliases:
            return alias
        fallback_alias = self._fallback_map.get(alias)
        if fallback_alias is None:
            raise LLMRouterError(f"no fallback configured for unavailable model alias: {alias}")
        fallback_config = self._model_registry.get(fallback_alias)
        if fallback_config is None or not fallback_config.is_fallback_eligible:
            raise LLMRouterError(f"fallback alias is not eligible: {fallback_alias}")
        return fallback_alias


def build_default_router(unavailable_aliases: set[str] | None = None) -> LLMRouter:
    """Build the deterministic offline default router."""
    return LLMRouter(
        providers={
            "mock": MockLLMProvider(),
            "deepseek-compatible": DeepSeekCompatibleProvider(),
            "qwen-compatible": QwenCompatibleProvider(),
        },
        model_registry=default_model_registry(),
        unavailable_aliases=unavailable_aliases,
    )


def complete(prompt: Prompt, model: str) -> Completion:
    """Complete a prompt through the default deterministic router."""
    return build_default_router().complete(prompt, model)


__all__ = ["LLMRouter", "build_default_router", "complete"]
