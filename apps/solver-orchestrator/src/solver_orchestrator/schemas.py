"""Pydantic schemas for solver-orchestrator endpoints (Story 2.1 + 3.1)."""

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


class AlgorithmSchema(BaseModel):
    k_algo: str
    task_type: str
    tier: str
    status: str
    model_version: ModelVersionSchema
    description_zh: str
    description_en: str
    examples: list[dict[str, Any]] = []


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
    reproducible: bool = Field(default=False, description="FR R1 lock version/seed")


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

    @model_validator(mode="after")
    def check_objective(self) -> OptimizationRequest:
        if self.minimize is None and self.maximize is None:
            raise ValueError("must specify either 'minimize' or 'maximize'")
        if self.minimize is not None and self.maximize is not None:
            raise ValueError("cannot specify both 'minimize' and 'maximize'")
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
