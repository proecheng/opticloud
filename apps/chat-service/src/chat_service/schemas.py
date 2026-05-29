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
CriticPreviewStatus = Literal["validated", "needs_clarification", "skipped"]
CriticPreviewSource = Literal["llm_critic_internal_beta", "heuristic_critic_internal_beta"]
CriticCheckName = Literal["schema", "safety", "business_logic"]
SandboxPreviewStatus = Literal["succeeded", "failed", "policy_blocked", "skipped"]
SandboxPreviewSource = Literal[
    "sandbox_runner_local_contract_internal_beta",
    "heuristic_sandbox_internal_beta",
]
SandboxPreviewErrorCode = Literal[
    "invalid_input_path",
    "llm_self_loop_blocked",
    "network_disabled",
    "result_budget_exceeded",
    "unsupported_binary_payload",
]
HumanReviewPreviewSource = Literal[
    "critic_threshold_internal_beta",
    "heuristic_human_review_internal_beta",
]
HumanReviewReasonCode = Literal[
    "critic_confidence_below_threshold",
    "critic_not_validated_below_threshold",
    "critic_skipped_below_threshold",
    "not_escalated",
]
CriticConfidenceDisplayTier = Literal["high", "mid", "low"]
LanguagePreviewStatus = Literal["generated", "fallback"]
LanguagePreviewSource = Literal["llm_language_internal_beta", "heuristic_language_internal_beta"]


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


class CriticValidationError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_path: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=160)
    remediation_hint_key: str | None = Field(default=None, min_length=1, max_length=128)


class CriticCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    message: str = Field(min_length=1, max_length=160)
    field_path: str | None = Field(default=None, min_length=1, max_length=128)


class CriticPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CriticPreviewStatus
    source: CriticPreviewSource
    task_type: TaskType
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=1, max_length=280)
    checks: dict[CriticCheckName, CriticCheck]
    validation_errors: list[CriticValidationError] = Field(default_factory=list, max_length=10)
    supported_task_types: list[TaskType]
    calibration_threshold: float = Field(ge=0.0, le=1.0)
    threshold_source: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def validate_critic_contract(self) -> CriticPreview:
        expected_checks = {"schema", "safety", "business_logic"}
        if set(self.checks) != expected_checks:
            raise ValueError("critic checks must cover schema, safety, and business_logic")
        if self.status == "validated" and self.source != "llm_critic_internal_beta":
            raise ValueError("validated critic preview requires LLM source")
        if self.status != "validated" and self.source != "heuristic_critic_internal_beta":
            raise ValueError("non-validated critic preview requires heuristic source")
        if self.supported_task_types != [
            "lp",
            "vrptw",
            "prediction",
            "schedule",
            "inventory",
            "unknown",
        ]:
            raise ValueError("supported_task_types must use the canonical order")
        return self


class SandboxValidationError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_path: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=160)
    remediation_hint_key: str | None = Field(default=None, min_length=1, max_length=128)


class SandboxResultFilePreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=256)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)

    @field_validator("path")
    @classmethod
    def validate_relative_result_path(cls, value: str) -> str:
        normalized = value.strip()
        if (
            not normalized
            or normalized.startswith("/")
            or normalized.startswith("\\")
            or ":" in normalized
            or ".." in normalized.replace("\\", "/").split("/")
        ):
            raise ValueError("result file path must be relative")
        return normalized


class SandboxLimitsPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu_vcpu: Literal[1]
    memory_mb: Literal[1024]
    soft_timeout_seconds: Literal[30]
    hard_timeout_seconds: Literal[90]
    network_disabled: Literal[True]
    read_only_filesystem: Literal[True]
    result_file_budget_bytes: Literal[104857600]


class SandboxPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SandboxPreviewStatus
    source: SandboxPreviewSource
    task_type: TaskType
    stdout_excerpt: str = Field(max_length=512)
    stderr_excerpt: str = Field(max_length=512)
    exit_code: int | None = Field(default=None, ge=0, le=255)
    result_files: list[SandboxResultFilePreview] = Field(default_factory=list, max_length=20)
    error_code: SandboxPreviewErrorCode | None = None
    limits: SandboxLimitsPreview
    validation_errors: list[SandboxValidationError] = Field(default_factory=list, max_length=10)
    contract_version: Literal["sandbox-runner-p58-p62-local-v1"]

    @model_validator(mode="after")
    def validate_sandbox_contract(self) -> SandboxPreview:
        if self.status == "skipped" and self.source != "heuristic_sandbox_internal_beta":
            raise ValueError("skipped sandbox preview requires heuristic source")
        if (
            self.status != "skipped"
            and self.source != "sandbox_runner_local_contract_internal_beta"
        ):
            raise ValueError("non-skipped sandbox preview requires sandbox-runner source")
        if self.status == "skipped" and (
            self.exit_code is not None
            or self.result_files
            or self.error_code is not None
            or self.stdout_excerpt
            or self.stderr_excerpt
        ):
            raise ValueError("skipped sandbox preview must not include execution output")
        if self.status == "policy_blocked" and (
            self.exit_code is not None or self.result_files or self.stdout_excerpt
        ):
            raise ValueError("policy-blocked sandbox preview must not include execution output")
        if self.status == "policy_blocked" and self.error_code is None:
            raise ValueError("policy-blocked sandbox preview requires error_code")
        if self.status in {"succeeded", "failed"} and self.error_code is not None:
            raise ValueError("completed sandbox preview must not include error_code")
        if self.status == "succeeded" and self.exit_code != 0:
            raise ValueError("succeeded sandbox preview requires exit_code 0")
        if self.status == "failed" and self.exit_code in (None, 0):
            raise ValueError("failed sandbox preview requires non-zero exit_code")
        return self


class HumanReviewNotice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zh: Literal["AI 不确定，已转人工复核。"]
    en: Literal["AI is uncertain; this has been routed for human review."]


class HumanReviewValidationError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_path: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=160)
    remediation_hint_key: str | None = Field(default=None, min_length=1, max_length=128)


class HumanReviewPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    escalated: bool
    source: HumanReviewPreviewSource
    queue: Literal["events.critic"]
    event_type: Literal["critic.review.escalated"]
    review_id: str = Field(min_length=28, max_length=28, pattern=r"^hrv_[0-9a-f]{24}$")
    reason_code: HumanReviewReasonCode
    critic_confidence: float = Field(ge=0.0, le=1.0)
    calibration_threshold: float = Field(ge=0.0, le=1.0)
    threshold_source: str = Field(min_length=1, max_length=160)
    user_notice: HumanReviewNotice | None
    validation_errors: list[HumanReviewValidationError] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_human_review_contract(self) -> HumanReviewPreview:
        if self.escalated:
            if self.source != "critic_threshold_internal_beta":
                raise ValueError("escalated human review requires critic threshold source")
            if self.critic_confidence >= self.calibration_threshold:
                raise ValueError("escalated human review requires confidence below threshold")
            if self.reason_code == "not_escalated":
                raise ValueError("escalated human review requires escalation reason code")
            if self.user_notice is None:
                raise ValueError("escalated human review requires user_notice")
        else:
            if self.source != "heuristic_human_review_internal_beta":
                raise ValueError("non-escalated human review requires heuristic source")
            if self.critic_confidence < self.calibration_threshold:
                raise ValueError(
                    "non-escalated human review requires confidence at or above threshold"
                )
            if self.reason_code != "not_escalated":
                raise ValueError("non-escalated human review requires not_escalated reason code")
            if self.user_notice is not None:
                raise ValueError("non-escalated human review must not include user_notice")
        return self


class CriticConfidenceDisplayValidationError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_path: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=160)
    remediation_hint_key: str | None = Field(default=None, min_length=1, max_length=128)


class CriticConfidenceDisplayPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0.0, le=1.0)
    tier: CriticConfidenceDisplayTier
    label_zh: str = Field(min_length=1, max_length=64)
    label_en: str = Field(min_length=1, max_length=96)
    reasoning_zh: str = Field(min_length=1, max_length=240)
    reasoning_en: str = Field(min_length=1, max_length=240)
    aria_label: str = Field(min_length=1, max_length=160)
    calibration_threshold: float = Field(ge=0.0, le=1.0)
    human_review_escalated: bool
    validation_errors: list[CriticConfidenceDisplayValidationError] = Field(
        default_factory=list,
        max_length=10,
    )

    @model_validator(mode="after")
    def validate_display_contract(self) -> CriticConfidenceDisplayPreview:
        expected_tier = _confidence_display_tier(self.score)
        if self.tier != expected_tier:
            raise ValueError("critic confidence display tier must match score brackets")
        expected_labels = {
            "high": ("高置信", "High confidence"),
            "mid": ("中置信", "Medium confidence"),
            "low": ("低置信请人工 review", "Low confidence; human review recommended"),
        }[expected_tier]
        if (self.label_zh, self.label_en) != expected_labels:
            raise ValueError("critic confidence display labels must match tier")
        expected_aria_label = f"Confidence: {self.score:.2f} - {self.label_en}"
        if self.aria_label != expected_aria_label:
            raise ValueError("critic confidence display aria_label must match score and label")
        return self


def _confidence_display_tier(score: float) -> CriticConfidenceDisplayTier:
    if score >= 0.85:
        return "high"
    if score >= 0.6:
        return "mid"
    return "low"


class LanguageValidationError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_path: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=160)
    remediation_hint_key: str | None = Field(default=None, min_length=1, max_length=128)


class ChatDisclaimer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zh: Literal["AI 生成内容仅供参考，请在提交求解前核对。"]
    en: Literal["AI-generated content is for reference only. Review it before submitting a solve."]
    bilingual: Literal[
        "AI 生成内容仅供参考，请在提交求解前核对。 / "
        "AI-generated content is for reference only. Review it before submitting a solve."
    ]


class LanguagePreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: LanguagePreviewStatus
    source: LanguagePreviewSource
    response_locale: ChatLocale
    summary: str = Field(min_length=1, max_length=360)
    disclaimer: ChatDisclaimer
    validation_errors: list[LanguageValidationError] = Field(default_factory=list, max_length=10)
    supported_locales: list[ChatLocale]

    @model_validator(mode="after")
    def validate_status_source(self) -> LanguagePreview:
        if self.status == "generated" and self.source != "llm_language_internal_beta":
            raise ValueError("generated language preview requires LLM source")
        if self.status == "fallback" and self.source != "heuristic_language_internal_beta":
            raise ValueError("fallback language preview requires heuristic source")
        if self.supported_locales != ["zh-CN", "en-US", "mixed"]:
            raise ValueError("supported_locales must use the canonical order")
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
    critic_preview: CriticPreview
    sandbox_preview: SandboxPreview
    human_review: HumanReviewPreview
    critic_confidence_display: CriticConfidenceDisplayPreview
    language_preview: LanguagePreview
    aigc_gate: AigcGate
    llm_invoked: bool
    critic_invoked: bool
    critic_llm_invoked: bool
    provider_request_sent: Literal[False]
    solver_invoked: Literal[False]
    sandbox_invoked: bool

    @model_validator(mode="after")
    def validate_sandbox_invocation_flag(self) -> ChatInternalBetaMessageResponse:
        if self.sandbox_preview.status == "skipped" and self.sandbox_invoked:
            raise ValueError("skipped sandbox preview must set sandbox_invoked=false")
        if self.sandbox_preview.status != "skipped" and not self.sandbox_invoked:
            raise ValueError("non-skipped sandbox preview must set sandbox_invoked=true")
        if self.critic_confidence_display.score != self.critic_preview.confidence:
            raise ValueError("critic confidence display score must match critic preview")
        if (
            self.critic_confidence_display.calibration_threshold
            != self.critic_preview.calibration_threshold
        ):
            raise ValueError("critic confidence display threshold must match critic preview")
        if self.critic_confidence_display.human_review_escalated != self.human_review.escalated:
            raise ValueError("critic confidence display escalation flag must match human review")
        return self
