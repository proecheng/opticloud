"""Pydantic schemas for solver-orchestrator endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

CONTROL_CHARACTERS = frozenset(chr(i) for i in range(32)) | {"\x7f"}


def reject_control_characters(value: str, field_name: str) -> None:
    if any(character in CONTROL_CHARACTERS for character in value):
        raise ValueError(f"{field_name} contains unsupported control characters")


# ===== Story 2.1: GET /v1/algorithms =====


class ModelVersionSchema(BaseModel):
    """FR E9 + A-S1 fix: provider_url field included."""

    provider_id: str
    kind: Literal["self", "open_source", "external", "commercial"]
    version: str
    provider_url: str = Field(..., description="Provider transparency (A-S1 fix)")


class CitationSchema(BaseModel):
    """Story 6.A.1 — FR R5 academic citation."""

    bibtex: str
    authors_label_zh: str
    year: int
    venue: str
    doi: str | None = None
    url: str | None = None


class IPAttributionSchema(BaseModel):
    """Story 6.A.5 — scholar / license IP attribution display contract."""

    tier: Literal["L1", "L2", "L3"]
    label_zh: str
    display_name_zh: str
    summary_zh: str
    visibility: Literal["full_visible", "bibtex", "license_only"]
    contract_anchor: str


class AlgorithmProvenanceParameterSchema(BaseModel):
    """Story 8.C.8 — catalog-facing provenance parameter."""

    name: str
    value_zh: str
    description_zh: str
    source: Literal["catalog_field", "request_schema", "runtime_policy", "documentation"]


class AlgorithmProvenanceSchema(BaseModel):
    """Story 8.C.8 — algorithm provenance detail metadata."""

    theory_zh: str
    theory_en: str
    configuration_parameters: list[AlgorithmProvenanceParameterSchema]
    applicable_scenarios_zh: list[str]
    limitations_zh: list[str]
    citation_source: Literal["catalog_citation"]


class ReproducibilitySchema(BaseModel):
    """Story 6.B.1 — opt-in reproducibility handoff for voucher minting."""

    requested: Literal[True]
    request_fingerprint: str
    locked_model_version: ModelVersionSchema
    locked_solver: str
    seed_locked: bool
    seed: int | None = None
    anonymous: Literal[True] | None = None


class AlgorithmSchema(BaseModel):
    k_algo: str
    task_type: str
    tier: str
    status: str
    model_version: ModelVersionSchema
    description_zh: str
    description_en: str
    examples: list[dict[str, Any]] = []
    supported_solvers: list[str]  # Story 2.4 — FR C4
    citation: CitationSchema | None = None  # Story 6.A.1 — FR R5
    ip_attribution: IPAttributionSchema  # Story 6.A.5 — L1/L2/L3 IP attribution
    provenance: AlgorithmProvenanceSchema | None = None  # Story 8.C.8


class BenchmarkDiscountSchema(BaseModel):
    """Story 8.C.4 — benchmark library discount metadata."""

    kind: Literal["benchmark_library"]
    label_zh: str
    discount_multiplier: float
    billing_supported: bool


class BenchmarkLibraryItemSchema(BaseModel):
    """Story 8.C.4 — public classic benchmark library entry."""

    benchmark_id: str
    suite: Literal["ieee", "cvrplib", "or-lib", "m5", "uci", "nab"]
    domain: str
    task_type: str
    title_zh: str
    title_en: str
    source_name: str
    source_url: str
    license_note_zh: str
    import_kind: Literal["optimization_request", "prediction_request"]
    target_endpoint: Literal["/v1/optimizations", "/v1/predictions"]
    discount: BenchmarkDiscountSchema
    dataset_ref: str
    sample_payload: dict[str, Any]


class BenchmarkImportResponseSchema(BaseModel):
    """Story 8.C.4 — side-effect-free one-click import payload."""

    benchmark_id: str
    import_kind: Literal["optimization_request", "prediction_request"]
    target_endpoint: Literal["/v1/optimizations", "/v1/predictions"]
    request_payload: dict[str, Any]
    discount: BenchmarkDiscountSchema
    dataset_ref: str
    disclaimer_zh: str
    disclaimer_en: str


# ===== Story 6.C.2: Provider exit notification admin contract =====


class ProviderExitPlanCreateRequest(BaseModel):
    """Internal Provider exit request that fans out >=30d voucher-holder notices."""

    provider_id: str = Field(
        ...,
        min_length=2,
        max_length=96,
        pattern=r"^[a-z0-9][a-z0-9_.:-]{1,94}$",
    )
    effective_at: datetime
    reason: str = Field(..., min_length=1, max_length=255)
    replacement_provider_id: str | None = Field(
        default=None,
        min_length=2,
        max_length=96,
        pattern=r"^[a-z0-9][a-z0-9_.:-]{1,94}$",
    )
    public_message: str | None = Field(default=None, max_length=500)
    severity: Literal["minor", "major"] = "major"
    status: Literal["identified", "monitoring"] = "identified"

    @field_validator("provider_id", "replacement_provider_id", mode="before")
    @classmethod
    def normalize_provider_id(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return value.strip().lower()

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        reject_control_characters(value, "reason")
        stripped = " ".join(value.strip().split())
        if not stripped:
            raise ValueError("reason must not be blank")
        return stripped

    @field_validator("public_message")
    @classmethod
    def normalize_public_message(cls, value: str | None) -> str | None:
        if value is None:
            return None
        reject_control_characters(value, "public_message")
        stripped = " ".join(value.strip().split())
        if not stripped:
            return None
        return stripped


class ProviderExitPlanCreateResponse(BaseModel):
    exit_plan_id: uuid.UUID
    provider_id: str
    effective_at: datetime
    affected_users: int
    affected_vouchers: int
    notification_requests_created: int
    status_url: str
    announcement_id: str


# ===== Story 3.1: POST /v1/optimizations =====


class LPObjective(BaseModel):
    c: list[float] = Field(..., description="Cost vector")


class LPConstraints(BaseModel):
    a: list[list[float]] = Field(alias="A", description="Constraint matrix A·x ≤ b")
    b: list[float] = Field(..., description="RHS vector")
    x_lower: list[float] | None = None
    x_upper: list[float] | None = None

    model_config = {"populate_by_name": True}


class OptimizationOptions(BaseModel):
    max_solve_seconds: float = Field(default=30.0, ge=1.0, le=600.0)
    top_k_alternatives: int = Field(
        default=1,
        ge=1,
        le=10,
        description="FR E5 number of ranked feasible alternatives to return for LP success",
    )
    reproducible: bool = Field(default=False, description="FR R1 lock version/seed")
    anonymous: bool = Field(default=False, description="FR R6 anonymous blind-review voucher")
    backtest: bool = Field(default=False, description="FR E10 backtest billing discount")
    benchmark_library: bool = Field(
        default=False,
        description="FR O11 benchmark library billing discount eligibility",
    )
    benchmark_id: str | None = Field(
        default=None,
        description="FR O11 stable benchmark library id when benchmark_library=true",
    )


class OptimizationRequest(BaseModel):
    """FR E1 — submit optimization task."""

    task_type: Literal[
        "lp", "milp", "qp", "socp", "sdp", "nlp", "minlp", "vrptw", "schedule", "cp_sat"
    ]
    minimize: LPObjective | None = None
    maximize: LPObjective | None = None
    st: LPConstraints
    options: OptimizationOptions = Field(default_factory=OptimizationOptions)
    solver: str | None = Field(default=None, description="FR C4 explicit solver enum")
    fallback_chain: list[str] | None = Field(
        default=None,
        description=(
            "FR C5 ordered list of solvers to try after `solver` fails "
            "(≤3 elements; execution in Story 2.7)"
        ),
    )

    @model_validator(mode="after")
    def check_objective(self) -> OptimizationRequest:
        if self.minimize is None and self.maximize is None:
            raise ValueError("must specify either 'minimize' or 'maximize'")
        if self.minimize is not None and self.maximize is not None:
            raise ValueError("cannot specify both 'minimize' and 'maximize'")
        # Story 2.5 — FR C5 length cap aligned to FR C7 (≤3 retries)
        if self.fallback_chain is not None and len(self.fallback_chain) > 3:
            raise ValueError("fallback_chain length must be ≤3 (FR C7)")
        return self


class OptimizationResponse(BaseModel):
    """FR E1, E9 — completed (sync mode) response."""

    optimization_id: uuid.UUID
    status: Literal["completed", "failed", "timeout"]
    solution: dict[str, Any] | None = None
    objective: float | None = None
    model_version: ModelVersionSchema
    solve_seconds: float
    created_at: datetime
    completed_at: datetime
    citation: CitationSchema | None = None  # Story 6.A.1 — FR R5
    ip_attribution: IPAttributionSchema | None = None  # Story 6.A.5


class OptimizationBatchRequest(BaseModel):
    """Story 3.13 — async batch optimization request."""

    tasks: list[OptimizationRequest] = Field(..., min_length=1, max_length=100)


class OptimizationBatchCounts(BaseModel):
    """Story 3.13 — derived batch child status counts."""

    queued: int = 0
    in_progress: int = 0
    completed: int = 0
    failed: int = 0
    timeout: int = 0
    cancelled: int = 0


class OptimizationBatchItemResponse(BaseModel):
    """Story 3.13 — child status/result plus stable batch item index."""

    index: int

    model_config = {"extra": "allow"}


class OptimizationBatchResponse(BaseModel):
    """Story 3.13 — batch polling response."""

    batch_id: uuid.UUID
    batch_status: str
    task_count: int
    counts: OptimizationBatchCounts | None = None
    progress_pct: int | None = None
    eta_seconds: int | None = None
    optimization_ids: list[uuid.UUID]
    items: list[OptimizationBatchItemResponse]
    errors: list[dict[str, Any]] = []
    created_at: datetime | None = None
    completed_at: datetime | None = None


# ===== Story 3.2: POST /v1/predictions =====


class PredictionRequest(BaseModel):
    """FR E2 — submit prediction family/algo request."""

    family: str
    data: list[float]
    horizon: int = 3


class PredictionQuantiles(BaseModel):
    p10: list[float]
    p50: list[float]
    p90: list[float]


class PredictionDisclaimer(BaseModel):
    zh: Literal["本预测仅供参考"]
    en: Literal["This forecast is for reference only"]
    bilingual: Literal["本预测仅供参考 / This forecast is for reference only"]


PREDICTION_DISCLAIMER_ZH: Literal["本预测仅供参考"] = "本预测仅供参考"
PREDICTION_DISCLAIMER_EN: Literal["This forecast is for reference only"] = (
    "This forecast is for reference only"
)
PREDICTION_DISCLAIMER_BILINGUAL: Literal["本预测仅供参考 / This forecast is for reference only"] = (
    "本预测仅供参考 / This forecast is for reference only"
)


def prediction_disclaimer() -> PredictionDisclaimer:
    """Return a fresh canonical FR E6 prediction disclaimer object."""
    return PredictionDisclaimer(
        zh=PREDICTION_DISCLAIMER_ZH,
        en=PREDICTION_DISCLAIMER_EN,
        bilingual=PREDICTION_DISCLAIMER_BILINGUAL,
    )


class PredictionResponse(BaseModel):
    """FR E2 + E6 — completed sync prediction response."""

    prediction_id: uuid.UUID
    status: Literal["completed"]
    family: str
    horizon: int
    prediction: PredictionQuantiles
    drift_score: float = Field(ge=0.0, le=1.0)
    disclaimer: PredictionDisclaimer
    model_version: ModelVersionSchema
    predict_seconds: float
    created_at: datetime
    completed_at: datetime


# ===== Story 5.D.3: Job templates save =====


class JobTemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    source_kind: Literal["optimization", "prediction"]
    source_id: uuid.UUID

    model_config = {"extra": "forbid"}


class JobTemplateSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    source_kind: Literal["optimization", "prediction"]
    source_id: uuid.UUID
    task_type: str
    payload_schema_version: Literal["optimization_request_v1", "prediction_request_v1"]
    payload_sha256: str
    version: int
    root_template_id: uuid.UUID
    parent_template_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class JobTemplateDetail(JobTemplateSummary):
    payload_json: dict[str, Any]


class JobTemplateListResponse(BaseModel):
    items: list[JobTemplateSummary]


class JobTemplateVersionCreateRequest(BaseModel):
    parameter_path: str = Field(..., min_length=1, max_length=120)
    value: Any
    description: str | None = Field(default=None, max_length=500)

    model_config = {"extra": "forbid"}


class JobTemplateVersionsResponse(BaseModel):
    items: list[JobTemplateSummary]


# ===== Story 8.C.9: Teaching Mode Grading API =====


OPAQUE_REF_PATTERN = r"^[A-Za-z0-9._:-]+$"
TEACHING_GRADING_RUBRIC_VERSION: Literal["teaching-grading-v1"] = "teaching-grading-v1"


def _validate_opaque_ref(value: str, *, field_name: str) -> str:
    import re

    if not re.fullmatch(OPAQUE_REF_PATTERN, value):
        raise ValueError(f"{field_name} must use opaque characters [A-Za-z0-9._:-] only")
    if not any(separator in value for separator in "._:-"):
        raise ValueError(f"{field_name} must be an opaque reference with a separator")
    if "@" in value or "/" in value or "\\" in value:
        raise ValueError(f"{field_name} must not contain email or path-like data")
    return value


class TeachingGradingSubmission(BaseModel):
    student_ref: str = Field(..., min_length=3, max_length=80)
    optimization_id: uuid.UUID

    model_config = {"extra": "forbid"}

    @field_validator("student_ref")
    @classmethod
    def validate_student_ref(cls, value: str) -> str:
        return _validate_opaque_ref(value, field_name="student_ref")


class TeachingGradingBatchCreateRequest(BaseModel):
    assignment_ref: str = Field(..., min_length=3, max_length=80)
    rubric_version: Literal["teaching-grading-v1"] = TEACHING_GRADING_RUBRIC_VERSION
    submissions: list[TeachingGradingSubmission] = Field(..., min_length=1, max_length=100)

    model_config = {"extra": "forbid"}

    @field_validator("assignment_ref")
    @classmethod
    def validate_assignment_ref(cls, value: str) -> str:
        return _validate_opaque_ref(value, field_name="assignment_ref")

    @model_validator(mode="after")
    def check_duplicates(self) -> TeachingGradingBatchCreateRequest:
        student_refs = [submission.student_ref for submission in self.submissions]
        if len(set(student_refs)) != len(student_refs):
            raise ValueError("duplicate student_ref values are not allowed")
        optimization_ids = [submission.optimization_id for submission in self.submissions]
        if len(set(optimization_ids)) != len(optimization_ids):
            raise ValueError("duplicate optimization_id values are not allowed")
        return self


class TeachingGradingCriterionResult(BaseModel):
    code: Literal["teaching_mode", "completed_status", "solution_available", "explanation_ready"]
    label_zh: str
    passed: bool
    points: float
    max_points: float


class TeachingGradingItemResponse(BaseModel):
    index: int
    student_ref: str
    optimization_id: uuid.UUID
    grading_status: Literal["graded", "not_gradable"]
    score: float
    max_score: float
    criteria: list[TeachingGradingCriterionResult]
    feedback_zh: str


class TeachingGradingBatchResponse(BaseModel):
    grading_batch_id: uuid.UUID
    assignment_ref: str
    rubric_version: Literal["teaching-grading-v1"]
    item_count: int
    graded_count: int
    not_gradable_count: int
    created_at: datetime
    items: list[TeachingGradingItemResponse]
