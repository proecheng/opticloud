"""Pydantic schemas for solver-orchestrator endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

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
