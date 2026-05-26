"""Provider-agnostic LLM router contract (Story M3.8)."""

from opticloud_shared.llm_router.providers import (
    DeepSeekCompatibleProvider,
    LLMProvider,
    LLMRouterError,
    MockLLMProvider,
    QwenCompatibleProvider,
)
from opticloud_shared.llm_router.registry import (
    ModelConfig,
    ProviderConfig,
    default_model_registry,
    default_provider_configs,
)
from opticloud_shared.llm_router.router import LLMRouter, build_default_router, complete
from opticloud_shared.llm_router.schemas import (
    Completion,
    CompletionUsage,
    Prompt,
    PromptMessage,
)

__all__ = [
    "Completion",
    "CompletionUsage",
    "DeepSeekCompatibleProvider",
    "LLMProvider",
    "LLMRouter",
    "LLMRouterError",
    "MockLLMProvider",
    "ModelConfig",
    "Prompt",
    "PromptMessage",
    "ProviderConfig",
    "QwenCompatibleProvider",
    "build_default_router",
    "complete",
    "default_model_registry",
    "default_provider_configs",
]
