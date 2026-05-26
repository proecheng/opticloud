"""Canonical LLM provider and model registry for Story M3.8."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CANONICAL_PROVIDER_IDS = ("mock", "deepseek-compatible", "qwen-compatible")
CANONICAL_IMPLEMENTATION_IDS = (
    "mock-deterministic",
    "deepseek-openai-compatible",
    "qwen-openai-compatible",
)
CANONICAL_MODEL_ALIASES = ("deepseek-v3.5", "qwen-max", "mock-deterministic")

ProviderId = Literal["mock", "deepseek-compatible", "qwen-compatible"]


class ProviderConfig(BaseModel):
    """Provider-level adapter configuration."""

    model_config = ConfigDict(extra="forbid")

    provider_id: ProviderId
    implementation_id: str = Field(min_length=1)
    base_url: str | None = Field(default=None, max_length=256)
    offline_only: bool = True
    notes: str = Field(min_length=1)

    @field_validator("implementation_id", "notes")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank")
        return stripped


class ModelConfig(BaseModel):
    """Logical model alias mapping."""

    model_config = ConfigDict(extra="forbid")

    alias: str = Field(min_length=1, max_length=128)
    provider_id: ProviderId
    provider_model: str = Field(min_length=1, max_length=128)
    implementation_id: str = Field(min_length=1, max_length=128)
    request_timeout_ms: int = Field(gt=0, le=120_000)
    max_output_tokens: int = Field(gt=0, le=32_000)
    is_fallback_eligible: bool
    notes: str = Field(min_length=1)

    @field_validator("alias", "provider_model", "implementation_id", "notes")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank")
        return stripped

    @model_validator(mode="after")
    def _implementation_matches_alias(self) -> ModelConfig:
        expected = {
            "mock": "mock-deterministic",
            "deepseek-compatible": "deepseek-openai-compatible",
            "qwen-compatible": "qwen-openai-compatible",
        }[self.provider_id]
        if self.implementation_id != expected:
            raise ValueError("implementation_id does not match provider_id")
        return self


def default_provider_configs() -> dict[str, ProviderConfig]:
    """Return canonical provider configs in stable order."""
    return {
        "mock": ProviderConfig(
            provider_id="mock",
            implementation_id="mock-deterministic",
            base_url=None,
            offline_only=True,
            notes="Deterministic offline implementation for tests and local contracts.",
        ),
        "deepseek-compatible": ProviderConfig(
            provider_id="deepseek-compatible",
            implementation_id="deepseek-openai-compatible",
            base_url="https://api.deepseek.com",
            offline_only=True,
            notes="OpenAI-compatible DeepSeek adapter; offline transport by default in CI.",
        ),
        "qwen-compatible": ProviderConfig(
            provider_id="qwen-compatible",
            implementation_id="qwen-openai-compatible",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            offline_only=True,
            notes="OpenAI-compatible Qwen/DashScope adapter; offline transport by default in CI.",
        ),
    }


def default_model_registry() -> dict[str, ModelConfig]:
    """Return canonical logical aliases in stable order."""
    return {
        "deepseek-v3.5": ModelConfig(
            alias="deepseek-v3.5",
            provider_id="deepseek-compatible",
            provider_model="deepseek-chat",
            implementation_id="deepseek-openai-compatible",
            request_timeout_ms=30_000,
            max_output_tokens=2_048,
            is_fallback_eligible=False,
            notes=(
                "Project logical primary alias. Provider model names are configuration, not "
                "permanent business semantics."
            ),
        ),
        "qwen-max": ModelConfig(
            alias="qwen-max",
            provider_id="qwen-compatible",
            provider_model="qwen-max",
            implementation_id="qwen-openai-compatible",
            request_timeout_ms=30_000,
            max_output_tokens=2_048,
            is_fallback_eligible=True,
            notes="Project logical incident fallback alias for Qwen-compatible OpenAI envelopes.",
        ),
        "mock-deterministic": ModelConfig(
            alias="mock-deterministic",
            provider_id="mock",
            provider_model="mock-deterministic-v1",
            implementation_id="mock-deterministic",
            request_timeout_ms=1_000,
            max_output_tokens=1_024,
            is_fallback_eligible=False,
            notes="Deterministic local model for schema and contract tests.",
        ),
    }


__all__ = [
    "CANONICAL_IMPLEMENTATION_IDS",
    "CANONICAL_MODEL_ALIASES",
    "CANONICAL_PROVIDER_IDS",
    "ModelConfig",
    "ProviderConfig",
    "default_model_registry",
    "default_provider_configs",
]
