"""SQLAlchemy ORM models for solver-orchestrator.

Tables added by infra/local-init/02-solver-schema.sql:
- optimizations
- idempotency_keys (P23 dedup)
- optimization_batches
- optimization_batch_items
- optimization_batch_idempotency_keys
- predictions
- prediction_idempotency_keys
- provider_exit_plans
- provider_exit_notification_requests
- provider_exit_status_announcements
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
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


class OptimizationBatch(Base):
    """Story 3.13 — batch grouping row, with status derived from children."""

    __tablename__ = "optimization_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    api_key_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_optimization_batches_user_id_created_at", "user_id", text("created_at DESC")),
    )


class OptimizationBatchItem(Base):
    """Story 3.13 — stable ordering from batch item index to child optimization."""

    __tablename__ = "optimization_batch_items"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("optimization_batches.id", ondelete="CASCADE"),
        primary_key=True,
    )
    item_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    optimization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("optimizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_optimization_batch_items_batch_id_item_index", "batch_id", "item_index"),
    )


class OptimizationBatchIdempotencyKey(Base):
    """Story 3.13 — whole-batch Idempotency-Key mapping."""

    __tablename__ = "optimization_batch_idempotency_keys"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("optimization_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    request_body_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("idx_optimization_batch_idempotency_keys_expires_at", "expires_at"),)


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


class JobTemplate(Base):
    """Story 5.D.3 — owner-scoped saved execution request template."""

    __tablename__ = "job_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    root_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_templates.id"), nullable=False
    )
    parent_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_templates.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "source_kind IN ('optimization', 'prediction')",
            name="ck_job_templates_source_kind",
        ),
        CheckConstraint(
            "payload_schema_version IN ('optimization_request_v1', 'prediction_request_v1')",
            name="ck_job_templates_payload_schema_version",
        ),
        CheckConstraint("version >= 1", name="ck_job_templates_version_positive"),
        Index(
            "uq_job_templates_active_root_source_name",
            "user_id",
            "source_kind",
            "source_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND parent_template_id IS NULL"),
        ),
        Index(
            "uq_job_templates_active_root_version",
            "user_id",
            "root_template_id",
            "version",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_job_templates_user_created_at",
            "user_id",
            text("created_at DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("idx_job_templates_root_version", "user_id", "root_template_id", "version"),
    )


class TeachingGradingBatch(Base):
    """Story 8.C.9 — owner-scoped teaching grading batch."""

    __tablename__ = "teaching_grading_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    api_key_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    assignment_ref: Mapped[str] = mapped_column(String(80), nullable=False)
    rubric_version: Mapped[str] = mapped_column(String(64), nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    graded_count: Mapped[int] = mapped_column(Integer, nullable=False)
    not_gradable_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_teaching_grading_batches_user_created", "user_id", text("created_at DESC")),
    )


class TeachingGradingItem(Base):
    """Story 8.C.9 — per-submission teaching grading result."""

    __tablename__ = "teaching_grading_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    grading_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teaching_grading_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    item_index: Mapped[int] = mapped_column(Integer, nullable=False)
    student_ref: Mapped[str] = mapped_column(String(80), nullable=False)
    optimization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    gradable_optimization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("optimizations.id"), nullable=True
    )
    grading_status: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    max_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    criteria: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    feedback_zh: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "idx_teaching_grading_items_user_batch_index",
            "user_id",
            "grading_batch_id",
            "item_index",
        ),
        Index(
            "uq_teaching_grading_items_batch_index",
            "grading_batch_id",
            "item_index",
            unique=True,
        ),
        Index(
            "uq_teaching_grading_items_batch_student",
            "grading_batch_id",
            "student_ref",
            unique=True,
        ),
        Index(
            "uq_teaching_grading_items_batch_optimization",
            "grading_batch_id",
            "optimization_id",
            unique=True,
        ),
    )


class TeachingGradingIdempotencyKey(Base):
    """Story 8.C.9 — per-user idempotency for teaching grading batches."""

    __tablename__ = "teaching_grading_idempotency_keys"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False)
    grading_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teaching_grading_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    request_body_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("idx_teaching_grading_idempotency_expires_at", "expires_at"),)


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


class OutboxEvent(Base):
    """Generic outbox row published by the shared sidecar relayer."""

    __tablename__ = "outbox"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    aggregate_type: Mapped[str] = mapped_column(String(255), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    headers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_outbox_unsent", "occurred_at", postgresql_where=text("sent_at IS NULL")),
        Index("idx_outbox_aggregate", "aggregate_type", "aggregate_id", text("occurred_at DESC")),
    )


class ProviderExitPlan(Base):
    """Story 6.C.2 — Provider exit plan that drives voucher-holder notification."""

    __tablename__ = "provider_exit_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    provider_id: Mapped[str] = mapped_column(String(96), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    replacement_provider_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    public_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="admin-secret")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "provider_id ~ '^[a-z0-9][a-z0-9_.:-]{1,94}$'",
            name="ck_provider_exit_plans_provider_id",
        ),
        CheckConstraint(
            "replacement_provider_id IS NULL OR "
            "replacement_provider_id ~ '^[a-z0-9][a-z0-9_.:-]{1,94}$'",
            name="ck_provider_exit_plans_replacement_provider_id",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'cancelled', 'completed')",
            name="ck_provider_exit_plans_status",
        ),
        Index(
            "uq_provider_exit_plans_provider_effective",
            "provider_id",
            "effective_at",
            unique=True,
        ),
        Index("idx_provider_exit_plans_provider_status", "provider_id", "status"),
    )


class ProviderExitNotificationRequest(Base):
    """Story 6.C.2 — one SLA notification request per affected user and exit plan."""

    __tablename__ = "provider_exit_notification_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    exit_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provider_exit_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(96), nullable=False)
    status_url: Mapped[str] = mapped_column(Text, nullable=False)
    affected_voucher_count: Mapped[int] = mapped_column(Integer, nullable=False)
    channels: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    email_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    in_app_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    webhook_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "provider_id ~ '^[a-z0-9][a-z0-9_.:-]{1,94}$'",
            name="ck_provider_exit_notification_requests_provider_id",
        ),
        CheckConstraint(
            "affected_voucher_count >= 1",
            name="ck_provider_exit_notification_requests_voucher_count",
        ),
        CheckConstraint(
            "channels = ARRAY['email', 'in_app']::text[]",
            name="ck_provider_exit_notification_requests_channels",
        ),
        CheckConstraint(
            "email_requested = TRUE AND in_app_requested = TRUE AND webhook_requested = FALSE",
            name="ck_provider_exit_notification_requests_channel_flags",
        ),
        Index(
            "uq_provider_exit_notification_requests_plan_user",
            "exit_plan_id",
            "user_id",
            unique=True,
        ),
        Index("idx_provider_exit_notification_requests_user_created", "user_id", "created_at"),
    )


class ProviderExitStatusAnnouncement(Base):
    """Story 6.C.2 — public status-page announcement request for a Provider exit."""

    __tablename__ = "provider_exit_status_announcements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    exit_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provider_exit_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    announcement_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(96), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    announcement_status: Mapped[str] = mapped_column(String(32), nullable=False)
    affected_user_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    affected_voucher_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "announcement_id ~ '^provider-exit-[a-z0-9][a-z0-9_.:-]{1,110}$'",
            name="ck_provider_exit_status_announcements_id",
        ),
        CheckConstraint(
            "provider_id ~ '^[a-z0-9][a-z0-9_.:-]{1,94}$'",
            name="ck_provider_exit_status_announcements_provider_id",
        ),
        CheckConstraint(
            "severity IN ('minor', 'major')",
            name="ck_provider_exit_status_announcements_severity",
        ),
        CheckConstraint(
            "announcement_status IN ('identified', 'monitoring')",
            name="ck_provider_exit_status_announcements_status",
        ),
        CheckConstraint(
            "affected_user_count >= 0",
            name="ck_provider_exit_status_announcements_user_count",
        ),
        CheckConstraint(
            "affected_voucher_count >= 0",
            name="ck_provider_exit_status_announcements_voucher_count",
        ),
        Index(
            "uq_provider_exit_status_announcements_plan",
            "exit_plan_id",
            unique=True,
        ),
        Index(
            "uq_provider_exit_status_announcements_announcement_id",
            "announcement_id",
            unique=True,
        ),
    )
