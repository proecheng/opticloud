"""Provider-agnostic LLM router schemas for Story M3.8."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PromptRole = Literal["system", "user", "assistant", "tool"]
FinishReason = Literal["stop", "length", "content_filter", "error"]

_BLOCKED_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "cookies",
    "password",
    "secret",
    "token",
    "provider_request",
    "provider_response",
    "raw_request",
    "raw_response",
    "customer_prompt",
    "user_prompt",
}
_SECRET_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{6,}|bearer\s+[A-Za-z0-9._-]+|api[_-]?key\s*[:=])",
    re.IGNORECASE,
)
_ALLOWED_RAW_RESPONSE_KEYS = {
    "logical_alias",
    "provider_id",
    "implementation_id",
    "provider_model",
    "finish_reason",
    "fallback_from",
    "fallback_to",
    "fallback_reason",
    "prompt_sha256",
    "completion_sha256",
    "transport",
}
_RAW_PAYLOAD_KEYS = {
    "choices",
    "message",
    "messages",
    "content",
    "text",
    "usage",
    "headers",
    "request",
    "response",
    "body",
}


class PromptMessage(BaseModel):
    """One chat-style prompt message."""

    model_config = ConfigDict(extra="forbid")

    role: PromptRole
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def _content_not_blank_or_secret(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message content must not be blank")
        _reject_secret_like_text(stripped, "message content")
        return stripped


class Prompt(BaseModel):
    """Provider-agnostic prompt payload."""

    model_config = ConfigDict(extra="forbid")

    prompt_id: str | None = Field(default=None, min_length=1, max_length=128)
    task: str = Field(min_length=1, max_length=64)
    locale: str = Field(default="zh-CN", min_length=2, max_length=16)
    messages: list[PromptMessage] = Field(min_length=1)
    response_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("prompt_id", "task", "locale")
    @classmethod
    def _text_fields_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank")
        _reject_secret_like_text(stripped, "prompt field")
        return stripped

    @model_validator(mode="after")
    def _metadata_safe(self) -> Prompt:
        _validate_safe_mapping(self.metadata, "metadata")
        if self.response_schema is not None:
            _validate_safe_mapping(self.response_schema, "response_schema")
        return self


class CompletionUsage(BaseModel):
    """Normalized token usage."""

    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def _total_matches_parts(self) -> CompletionUsage:
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ValueError("total_tokens must equal prompt_tokens + completion_tokens")
        return self


class Completion(BaseModel):
    """Provider-neutral completion object returned by the router."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    model: str = Field(min_length=1, max_length=128)
    provider: str = Field(min_length=1, max_length=128)
    finish_reason: FinishReason
    usage: CompletionUsage
    latency_ms: int = Field(default=0, ge=0)
    raw_response_redacted: dict[str, Any] | None = None

    @field_validator("text", "model", "provider")
    @classmethod
    def _text_not_blank_or_secret(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank")
        _reject_secret_like_text(stripped, "completion field")
        return stripped

    @model_validator(mode="after")
    def _raw_response_is_redacted(self) -> Completion:
        if self.raw_response_redacted is not None:
            _validate_redacted_response(self.raw_response_redacted)
        return self


def _reject_secret_like_text(value: str, location: str) -> None:
    if _SECRET_PATTERN.search(value):
        raise ValueError(f"{location} contains secret-like material")


def _validate_safe_mapping(value: dict[str, Any], location: str) -> None:
    for key, item in value.items():
        lowered = str(key).lower()
        if lowered in _BLOCKED_KEYS:
            raise ValueError(f"{location} contains blocked key: {key}")
        _reject_secret_like_text(str(key), location)
        if isinstance(item, str):
            _reject_secret_like_text(item, location)
        elif isinstance(item, dict):
            _validate_safe_mapping(item, f"{location}.{key}")
        elif isinstance(item, list):
            for index, child in enumerate(item):
                if isinstance(child, dict):
                    _validate_safe_mapping(child, f"{location}.{key}[{index}]")
                elif isinstance(child, str):
                    _reject_secret_like_text(child, f"{location}.{key}[{index}]")


def _validate_redacted_response(value: dict[str, Any]) -> None:
    for key, item in value.items():
        lowered = str(key).lower()
        if lowered not in _ALLOWED_RAW_RESPONSE_KEYS:
            raise ValueError(f"raw_response_redacted contains unsupported key: {key}")
        if lowered in _RAW_PAYLOAD_KEYS:
            raise ValueError(f"raw_response_redacted contains raw provider payload key: {key}")
        if isinstance(item, dict | list):
            raise ValueError("raw_response_redacted must not contain nested provider payloads")
        if isinstance(item, str):
            _reject_secret_like_text(item, "raw_response_redacted")


__all__ = [
    "Completion",
    "CompletionUsage",
    "FinishReason",
    "Prompt",
    "PromptMessage",
    "PromptRole",
]
