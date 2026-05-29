from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ChatLocale = Literal["zh-CN", "en-US", "mixed"]
TaskType = Literal["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"]
RouterPreviewSource = Literal["heuristic_internal_beta", "llm_router_internal_beta"]
FormulatorPreviewStatus = Literal["extracted", "needs_clarification", "skipped"]
FormulatorPreviewSource = Literal[
    "llm_formulator_internal_beta", "heuristic_formulator_internal_beta"
]
CoderPreviewStatus = Literal["generated", "needs_clarification", "skipped"]
CoderPreviewSource = Literal[
    "llm_coder_internal_beta",
    "template_coder_internal_beta",
    "heuristic_coder_internal_beta",
]


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


class FormulatorValidationError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_path: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=160)
    remediation_hint_key: str | None = Field(default=None, min_length=1, max_length=128)


class FormulatorPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: FormulatorPreviewStatus
    source: FormulatorPreviewSource
    task_type: TaskType
    confidence: float = Field(ge=0.0, le=1.0)
    variables: dict[str, object]
    objective: dict[str, object]
    constraints: dict[str, object]
    validation_errors: list[FormulatorValidationError] = Field(default_factory=list, max_length=10)
    supported_task_types: list[TaskType]


class CoderValidationError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_path: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=160)
    remediation_hint_key: str | None = Field(default=None, min_length=1, max_length=128)


class CoderCodeArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Literal["python"]
    code: str = Field(min_length=1, max_length=8000)
    entrypoint: str = Field(min_length=1, max_length=128)
    input_model: str = Field(min_length=1, max_length=128)
    output_model: str = Field(min_length=1, max_length=128)
    imports: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("entrypoint", "input_model", "output_model")
    @classmethod
    def validate_python_identifier(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped.isidentifier():
            raise ValueError("field must be a valid Python identifier")
        return stripped

    @field_validator("imports")
    @classmethod
    def validate_import_names(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for module in value:
            module_name = module.strip()
            if not module_name or not module_name.replace("_", "").replace(".", "").isalnum():
                raise ValueError("imports must contain module names")
            normalized.append(module_name)
        return normalized


class CoderPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CoderPreviewStatus
    source: CoderPreviewSource
    task_type: TaskType
    artifact: CoderCodeArtifact | None
    validation_errors: list[CoderValidationError] = Field(default_factory=list, max_length=10)
    supported_task_types: list[TaskType]

    @model_validator(mode="after")
    def validate_artifact_status(self) -> CoderPreview:
        if self.status == "generated" and self.artifact is None:
            raise ValueError("generated coder preview requires an artifact")
        if self.status != "generated" and self.artifact is not None:
            raise ValueError("non-generated coder preview must not include an artifact")
        return self


class ChatInternalBetaMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["internal_beta"]
    public_access: Literal[False]
    message_id: str
    message_excerpt: str
    locale: ChatLocale
    router_preview: RouterPreview
    formulator_preview: FormulatorPreview
    coder_preview: CoderPreview
    aigc_gate: AigcGate
    llm_invoked: bool
    provider_request_sent: Literal[False]
    solver_invoked: Literal[False]
    sandbox_invoked: Literal[False]
