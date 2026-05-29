from __future__ import annotations

import re
from typing import Literal

import aigc_filter
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
AigcWatermarkTier = Literal["strict", "loose"]

_AIGC_TRACE_ID_PATTERN = r"^trc_[0-9a-f]{16}$"
_AIGC_REASON_CODE_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")
_AIGC_SAFE_VERSION_PATTERN = r"^[0-9A-Za-z][0-9A-Za-z._-]{0,31}$"
_AIGC_ALLOWED_METADATA_KEYS = {"self_loop_bypass"}
_AIGC_NO_LEAK_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{4,}|api[_\s-]?key|bearer\s+[A-Za-z0-9._-]+|"
    r"authorization|cookie|password|token|raw[_ -]?(?:response|request)|"
    r"raw[_ -]?(?:summary|user[_ -]?message)|"
    r"provider[_ -]?(?:request|response|payload)?|prompt|traceback|"
    r"generated[_ -]?code|sandbox[_ -]?output|"
    r"[A-Za-z]:\\|/tmp/|/var/|queue[_ -]?payload)",
    re.IGNORECASE,
)


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


class AigcWatermarkPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aria_label: str = Field(min_length=1, max_length=64)
    visible_marker: str = Field(min_length=1, max_length=64)
    trace_id: str = Field(pattern=_AIGC_TRACE_ID_PATTERN)
    provider: str = Field(min_length=1, max_length=64)
    module_version: str = Field(min_length=1, max_length=32, pattern=_AIGC_SAFE_VERSION_PATTERN)
    tier: AigcWatermarkTier
    blocked: bool
    reason_codes: list[str] = Field(default_factory=list, max_length=8)
    metadata: dict[str, object] = Field(default_factory=dict, max_length=4)

    @field_validator("reason_codes")
    @classmethod
    def validate_reason_codes(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for code in value:
            clean = code.strip()
            if (
                clean != code
                or not _AIGC_REASON_CODE_PATTERN.fullmatch(clean)
                or _AIGC_NO_LEAK_PATTERN.search(clean)
            ):
                raise ValueError("aigc reason_codes must be bounded policy codes")
            normalized.append(clean)
        if len(set(normalized)) != len(normalized):
            raise ValueError("aigc reason_codes must not contain duplicates")
        return normalized

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        if set(value) - _AIGC_ALLOWED_METADATA_KEYS:
            raise ValueError("aigc metadata contains unsupported keys")
        for key, raw_value in value.items():
            if _AIGC_NO_LEAK_PATTERN.search(key):
                raise ValueError("aigc metadata keys must not leak internals")
            if key == "self_loop_bypass" and not isinstance(raw_value, bool):
                raise ValueError("aigc self_loop_bypass metadata must be boolean")
        return value

    @model_validator(mode="after")
    def validate_blocked_reason_consistency(self) -> AigcWatermarkPreview:
        if self.aria_label != aigc_filter.AIGC_ARIA_LABEL:
            raise ValueError("aigc aria_label must match shared module")
        if self.visible_marker != aigc_filter.AIGC_VISIBLE_MARKER:
            raise ValueError("aigc visible_marker must match shared module")
        if self.provider != aigc_filter.PROVIDER_MARKER:
            raise ValueError("aigc provider must match shared module")
        if self.blocked and "blocked_content" not in self.reason_codes:
            raise ValueError("blocked aigc output requires blocked_content reason")
        if not self.blocked and self.reason_codes:
            raise ValueError("unblocked aigc output must not include reason_codes")
        return self


class LanguagePreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: LanguagePreviewStatus
    source: LanguagePreviewSource
    response_locale: ChatLocale
    summary: str = Field(min_length=1, max_length=1800)
    aigc_watermark: AigcWatermarkPreview
    disclaimer: ChatDisclaimer
    validation_errors: list[LanguageValidationError] = Field(default_factory=list, max_length=10)
    supported_locales: list[ChatLocale]

    @model_validator(mode="after")
    def validate_status_source_and_watermark(self) -> LanguagePreview:
        if self.status == "generated" and self.source != "llm_language_internal_beta":
            raise ValueError("generated language preview requires LLM source")
        if self.status == "fallback" and self.source != "heuristic_language_internal_beta":
            raise ValueError("fallback language preview requires heuristic source")
        if self.supported_locales != ["zh-CN", "en-US", "mixed"]:
            raise ValueError("supported_locales must use the canonical order")
        if aigc_filter.AIGC_VISIBLE_MARKER not in self.summary:
            raise ValueError("language summary requires shared AIGC visible marker")
        detected = aigc_filter.detect_watermark(self.summary)
        if not detected.present:
            raise ValueError("language summary requires detectable AIGC watermark metadata")
        if detected.trace_id != self.aigc_watermark.trace_id:
            raise ValueError("language summary watermark trace_id must match preview")
        if detected.provider != self.aigc_watermark.provider:
            raise ValueError("language summary watermark provider must match preview")
        if detected.module_version != self.aigc_watermark.module_version:
            raise ValueError("language summary watermark module_version must match preview")
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
