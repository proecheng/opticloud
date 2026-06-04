"""Billing service SQLAlchemy models — Saga + Credit ledger + Idempotency.

Story 5.A.0a — maps the 3 tables defined in `infra/local-init/03-billing-schema.sql`.

Per-service Base pattern (R1.7 decision — matches auth-service). Schema is owned
by raw SQL; SQLAlchemy here just maps existing tables.

Security:
- saga_instances.payload_ref contains POINTERS only (e.g., optimization_id).
  Amounts and PII never stored here — they live in credit_transactions.
- idempotency_keys.request_body_hash is SHA-256 hex; raw body never persisted.
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
    """Per-service declarative base (R1.7)."""


class SagaInstance(Base):
    """Saga state — single row per active or terminal Saga.

    AC2: tracks `current_state` (one of opticloud_shared.saga.State values).
    payload_ref holds reference IDs (optimization_id etc.); NEVER monetary amounts.
    """

    __tablename__ = "saga_instances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    saga_type: Mapped[str] = mapped_column(String(64), nullable=False)
    current_state: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_ref: Mapped[dict] = mapped_column(  # type: ignore[type-arg]
        JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("idx_saga_instances_user_state", "user_id", "current_state"),)


class CreditTransaction(Base):
    """Double-entry credit ledger (NFR-R4 = 0 source of truth).

    Story 5.A.2: `bucket` tags each ledger row with one of 4 categories
    (monthly / signup / edu / topup) for FR B1 per-bucket display.
    """

    __tablename__ = "credit_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    saga_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    bucket: Mapped[str] = mapped_column(String(32), nullable=False, default="monthly")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    metadata_json: Mapped[dict] = mapped_column(  # type: ignore[type-arg]
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IdempotencyKeyRow(Base):
    """P23 idempotency key (billing scope) — TTL 24h enforced by orchestrator on read.

    Maps to `billing_idempotency_keys` table. Separate from solver's
    `idempotency_keys` which is scoped to optimization_id FK.
    """

    __tablename__ = "billing_idempotency_keys"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    request_body_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_body: Mapped[dict | None] = mapped_column(  # type: ignore[type-arg]
        JSONB, nullable=True
    )
    saga_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OutboxEvent(Base):
    """P33 Outbox — orchestrator writes here; M2.1 sidecar publishes to broker.

    Maps to existing `outbox` table from 01-schema.sql.
    """

    __tablename__ = "outbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aggregate_type: Mapped[str] = mapped_column(String(255), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)  # type: ignore[type-arg]
    headers: Mapped[dict] = mapped_column(  # type: ignore[type-arg]
        JSONB, nullable=False, default=dict
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CostAttribution(Base):
    """Story M2.3 / 5.A.8 — shared G3 cost attribution table."""

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


class BillingSubscription(Base):
    """Story 5.B.1 — one active plan subscription per user."""

    __tablename__ = "billing_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_code: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_refilled_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "plan_code IN ('free', 'starter', 'pro', 'team', 'enterprise')",
            name="ck_billing_subscriptions_plan_code",
        ),
        CheckConstraint(
            "status IN ('active', 'canceled', 'expired')",
            name="ck_billing_subscriptions_status",
        ),
        CheckConstraint(
            "current_period_end > current_period_start",
            name="ck_billing_subscriptions_period_order",
        ),
        Index(
            "idx_billing_subscriptions_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("idx_billing_subscriptions_due", "status", "current_period_end"),
    )


class LegalInquiry(Base):
    """Story 8.C.3 — Team+ legal inquiry support record."""

    __tablename__ = "legal_inquiries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    plan_code: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(254), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    subject: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    urgency: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="submitted")
    ticket_key: Mapped[str] = mapped_column(String(32), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sla_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "plan_code IN ('team', 'enterprise')",
            name="ck_legal_inquiries_plan_code",
        ),
        CheckConstraint(
            "category IN ("
            "'pipl',"
            "'gdpr',"
            "'graded_protection',"
            "'data_export',"
            "'dpa',"
            "'license',"
            "'security',"
            "'other'"
            ")",
            name="ck_legal_inquiries_category",
        ),
        CheckConstraint("urgency IN ('normal', 'urgent')", name="ck_legal_inquiries_urgency"),
        CheckConstraint(
            "status IN ('submitted', 'triage_pending', 'responded', 'closed')",
            name="ck_legal_inquiries_status",
        ),
        CheckConstraint(
            "length(contact_email) BETWEEN 3 AND 254 AND position('@' IN contact_email) > 1",
            name="ck_legal_inquiries_contact_email",
        ),
        CheckConstraint(
            "company_name IS NULL OR length(btrim(company_name)) BETWEEN 1 AND 160",
            name="ck_legal_inquiries_company_name",
        ),
        CheckConstraint(
            "length(btrim(subject)) BETWEEN 3 AND 160",
            name="ck_legal_inquiries_subject",
        ),
        CheckConstraint(
            "length(btrim(message)) BETWEEN 10 AND 4000",
            name="ck_legal_inquiries_message",
        ),
        CheckConstraint(
            "ticket_key ~ '^OPTI-LEGAL-[0-9]{8}-[A-F0-9]{6}$'",
            name="ck_legal_inquiries_ticket_key",
        ),
        CheckConstraint(
            "sla_due_at = submitted_at + INTERVAL '24 hours'",
            name="ck_legal_inquiries_sla_due",
        ),
        Index("idx_legal_inquiries_ticket_key", "ticket_key", unique=True),
        Index("idx_legal_inquiries_user_submitted", "user_id", "submitted_at"),
        Index("idx_legal_inquiries_status_sla", "status", "sla_due_at"),
    )


class BillingBudgetControl(Base):
    """Story 5.D.5 — one current monthly budget control per user."""

    __tablename__ = "billing_budget_controls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    monthly_budget_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    alert_threshold_ratio: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.8000")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pause_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "monthly_budget_amount >= 1.00 AND monthly_budget_amount <= 9999999.99",
            name="ck_billing_budget_controls_amount",
        ),
        CheckConstraint(
            "alert_threshold_ratio > 0 AND alert_threshold_ratio < 1",
            name="ck_billing_budget_controls_alert_ratio",
        ),
        CheckConstraint(
            "status IN ('active', 'paused')",
            name="ck_billing_budget_controls_status",
        ),
        CheckConstraint(
            "(status = 'paused' AND paused_at IS NOT NULL AND pause_period_start IS NOT NULL) "
            "OR (status = 'active')",
            name="ck_billing_budget_controls_pause_fields",
        ),
        Index("idx_billing_budget_controls_one_per_user", "user_id", unique=True),
        Index(
            "idx_billing_budget_controls_status",
            "status",
            "pause_period_start",
            postgresql_where=text("enabled = TRUE"),
        ),
    )


class BillingBudgetEvent(Base):
    """Story 5.D.5 — period-scoped budget notification/pause events."""

    __tablename__ = "billing_budget_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    budget_control_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'billing.budget.configured',"
            "'billing.budget.disabled',"
            "'billing.budget.alerted',"
            "'billing.budget.paused'"
            ")",
            name="ck_billing_budget_events_type",
        ),
        CheckConstraint(
            "period_end > period_start",
            name="ck_billing_budget_events_period_order",
        ),
        Index(
            "idx_billing_budget_events_unique_threshold_period_type",
            "user_id",
            "period_start",
            "event_type",
            unique=True,
            postgresql_where=text(
                "event_type IN ('billing.budget.alerted', 'billing.budget.paused')"
            ),
        ),
        Index("idx_billing_budget_events_user_occurred", "user_id", "occurred_at"),
    )
