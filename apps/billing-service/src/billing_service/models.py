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

from sqlalchemy import DateTime, Index, Integer, Numeric, String, Text
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
    """Double-entry credit ledger (NFR-R4 = 0 source of truth)."""

    __tablename__ = "credit_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    saga_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
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
