"""SQLAlchemy ORM models for solver-orchestrator.

Tables added by infra/local-init/02-solver-schema.sql:
- optimizations
- idempotency_keys (P23 dedup)
- predictions
- prediction_idempotency_keys
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Optimization(Base):
    """FR E1-E10 — optimization tasks (sync + async)."""

    __tablename__ = "optimizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    api_key_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    solution: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    objective: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    model_version: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    solve_seconds: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReproductionVoucher(Base):
    """Story 6.B.2 — permanent voucher for reproducible optimization runs."""

    __tablename__ = "reproduction_vouchers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    voucher_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    optimization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("optimizations.id", ondelete="CASCADE"), nullable=False
    )
    parent_voucher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reproduction_vouchers.id"),
        nullable=True,
    )
    rerun_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    api_key_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    locked_model_version: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    locked_solver: Mapped[str] = mapped_column(String(64), nullable=False)
    seed_locked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anonymous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="issued")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "voucher_id ~ '^repro-[0-9]{4}-[0123456789ABCDEFGHJKMNPQRSTVWXYZ]{6}$'",
            name="ck_reproduction_vouchers_voucher_id_format",
        ),
        CheckConstraint(
            "status IN ('issued', 'revoked')",
            name="ck_reproduction_vouchers_status",
        ),
        CheckConstraint("rerun_depth >= 0", name="ck_reproduction_vouchers_rerun_depth"),
        Index(
            "uq_reproduction_vouchers_optimization_id",
            "optimization_id",
            unique=True,
        ),
        Index("idx_reproduction_vouchers_user_id_created_at", "user_id", "created_at"),
        Index("idx_reproduction_vouchers_parent_voucher_id", "parent_voucher_id"),
    )


class IdempotencyKey(Base):
    """P23 Idempotency-Key dedup (24h TTL)."""

    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False)
    optimization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("optimizations.id"), nullable=False
    )
    request_body_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Prediction(Base):
    """FR E2-E6 — prediction tasks (sync subset for Story 3.2)."""

    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    api_key_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    family: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    prediction: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    drift_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    model_version: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    predict_seconds: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_predictions_user_id_created_at", "user_id", text("created_at DESC")),
        Index(
            "idx_predictions_status",
            "status",
            postgresql_where=text("status IN ('queued', 'in_progress')"),
        ),
    )


class PredictionIdempotencyKey(Base):
    """P23 Idempotency-Key dedup for prediction submissions."""

    __tablename__ = "prediction_idempotency_keys"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False)
    prediction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False
    )
    request_body_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("idx_prediction_idempotency_keys_expires_at", "expires_at"),)


class CostAttribution(Base):
    """Story M2.3 — shared G3 cost attribution table."""

    __tablename__ = "cost_attribution"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    service: Mapped[str] = mapped_column(String(64), nullable=False)
    cost_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "cost_unit IN ('llm_token', 'gpu_second', 'solver_second')",
            name="ck_cost_attribution_cost_unit",
        ),
        CheckConstraint("value >= 0", name="ck_cost_attribution_value_nonnegative"),
        Index(
            "idx_cost_attr_tenant_service_unit_recorded",
            "tenant_id",
            "service",
            "cost_unit",
            "recorded_at",
        ),
        Index(
            "idx_cost_attr_source_id",
            "source_id",
            postgresql_where=text("source_id IS NOT NULL"),
        ),
    )
