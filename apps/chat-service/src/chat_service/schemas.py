from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ChatLocale = Literal["zh-CN", "en-US", "mixed"]
TaskType = Literal["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"]
RouterPreviewSource = Literal["heuristic_internal_beta", "llm_router_internal_beta"]


class ChatInternalBetaMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2200)
    locale: ChatLocale | None = None
    client_request_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 2:
            raise ValueError("message must contain at least 2 non-whitespace characters")
        if len(trimmed) > 2000:
            raise ValueError("message must contain at most 2000 characters after trimming")
        return trimmed


class RouterPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: TaskType
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    source: RouterPreviewSource
    supported_task_types: list[TaskType]


class AigcGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["filing_pending"]
    public_surface: Literal["hidden"]


class ChatInternalBetaMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["internal_beta"]
    public_access: Literal[False]
    message_id: str
    message_excerpt: str
    locale: ChatLocale
    router_preview: RouterPreview
    aigc_gate: AigcGate
    llm_invoked: bool
    provider_request_sent: Literal[False]
    solver_invoked: Literal[False]
    sandbox_invoked: Literal[False]
