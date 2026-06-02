"""SQLAlchemy models for capability-registry tables."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Index, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Per-service declarative base."""


class CapabilityProvider(Base):
    """Provider contract row.

    `tenant_id=NULL` is the global catalog scope; non-null reserves a tenant
    override. Partial unique indexes in SQL enforce both scopes.
    """

    __tablename__ = "capability_providers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    openapi_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    openapi_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_digest: Mapped[str | None] = mapped_column(Text, nullable=True)
    cosign_bundle: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_capability_providers_global_provider_id",
            "provider_id",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
        ),
        Index(
            "uq_capability_providers_tenant_provider_id",
            "tenant_id",
            "provider_id",
            unique=True,
            postgresql_where=text("tenant_id IS NOT NULL"),
        ),
    )


class Capability(Base):
    """Algorithm capability contract row."""

    __tablename__ = "capabilities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    k_algo: Mapped[str] = mapped_column(String(64), nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    tier: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    supported_solvers: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    description_zh: Mapped[str] = mapped_column(Text, nullable=False)
    description_en: Mapped[str] = mapped_column(Text, nullable=False)
    examples: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    capability_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_capabilities_global_k_algo",
            "k_algo",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
        ),
        Index(
            "uq_capabilities_tenant_k_algo",
            "tenant_id",
            "k_algo",
            unique=True,
            postgresql_where=text("tenant_id IS NOT NULL"),
        ),
    )


class CapabilityTag(Base):
    """Normalized capability vocabulary tag."""

    __tablename__ = "capability_tags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    capability_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tag: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("uq_capability_tags_capability_tag", "capability_id", "tag", unique=True),
    )


class ProviderOAuthFlow(Base):
    """Provider OAuth metadata stub.

    Fields intentionally store references only. Raw OAuth tokens/secrets are out of scope.
    """

    __tablename__ = "provider_oauth_flows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    authorization_url: Mapped[str] = mapped_column(Text, nullable=False)
    token_url: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    client_id_ref: Mapped[str] = mapped_column(Text, nullable=False)
    client_secret_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    vault_secret_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    flow_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_provider_oauth_flows_global_provider_id",
            "provider_id",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
        ),
        Index(
            "uq_provider_oauth_flows_tenant_provider_id",
            "tenant_id",
            "provider_id",
            unique=True,
            postgresql_where=text("tenant_id IS NOT NULL"),
        ),
    )


class RevenueSharePolicy(Base):
    """Future v2 revenue-share policy reservation.

    This table stores split ratios and identifiers only. It does not compute or
    settle payout amounts.
    """

    __tablename__ = "revenue_share_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    policy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_share_ratio: Mapped[Decimal] = mapped_column(Numeric(7, 6), nullable=False)
    provider_share_ratio: Mapped[Decimal] = mapped_column(Numeric(7, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="reserved")
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    policy_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_revenue_share_policies_global_policy_id",
            "policy_id",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
        ),
        Index(
            "uq_revenue_share_policies_tenant_policy_id",
            "tenant_id",
            "policy_id",
            unique=True,
            postgresql_where=text("tenant_id IS NOT NULL"),
        ),
    )


class RevenueShareHook(Base):
    """Immutable future revenue-share capture hook.

    Billing fields are opaque references. Amounts and payout lifecycle state are
    deliberately out of scope for the v1 reservation.
    """

    __tablename__ = "revenue_share_hooks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    k_algo: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_service: Mapped[str] = mapped_column(String(64), nullable=False)
    source_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    billing_saga_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    billing_ledger_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    period_month: Mapped[str] = mapped_column(String(7), nullable=False)
    gross_amount_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="reserved")
    hook_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_revenue_share_hooks_source_event",
            "source_service",
            "source_event_id",
            unique=True,
        ),
        Index(
            "idx_revenue_share_hooks_lookup",
            "tenant_id",
            "provider_id",
            "k_algo",
            "period_month",
        ),
    )


class ProviderRevenuePayoutEntry(Base):
    """Provider revenue/pending-payout read projection entry.

    The gross amount is supplied by an internal producer, while provider and
    platform amounts are derived from policy ratio snapshots at read time.
    """

    __tablename__ = "provider_revenue_payout_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    entry_id: Mapped[str] = mapped_column(String(64), nullable=False)
    hook_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    k_algo: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_service: Mapped[str] = mapped_column(String(64), nullable=False)
    source_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period_month: Mapped[str] = mapped_column(String(7), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    platform_share_ratio: Mapped[Decimal] = mapped_column(Numeric(7, 6), nullable=False)
    provider_share_ratio: Mapped[Decimal] = mapped_column(Numeric(7, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    recognized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_provider_revenue_payout_entries_global_entry_id",
            "entry_id",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
        ),
        Index(
            "uq_provider_revenue_payout_entries_tenant_entry_id",
            "tenant_id",
            "entry_id",
            unique=True,
            postgresql_where=text("tenant_id IS NOT NULL"),
        ),
        Index("uq_provider_revenue_payout_entries_hook", "hook_row_id", unique=True),
        Index(
            "idx_provider_revenue_payout_entries_dashboard",
            "tenant_id",
            "provider_id",
            "period_month",
            "status",
            "currency",
        ),
    )


class ProviderMonthlyRevenueShareBatch(Base):
    """Monthly provider revenue-share calculation snapshot.

    This is an auditable calculation batch only. It does not settle payment,
    mutate payout entry state, or create external transfer artifacts.
    """

    __tablename__ = "provider_monthly_revenue_share_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    period_month: Mapped[str] = mapped_column(String(7), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_count: Mapped[int] = mapped_column(nullable=False, default=0)
    provider_count: Mapped[int] = mapped_column(nullable=False, default=0)
    currency_totals: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    provider_summaries: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    policy_ratio_summaries: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    excluded_entries: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    source_entry_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    calculation_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    notes_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    batch_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    record_version: Mapped[int] = mapped_column(nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_provider_monthly_revenue_share_batches_global_batch_id",
            "batch_id",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
        ),
        Index(
            "uq_provider_monthly_revenue_share_batches_tenant_batch_id",
            "tenant_id",
            "batch_id",
            unique=True,
            postgresql_where=text("tenant_id IS NOT NULL"),
        ),
        Index(
            "idx_provider_monthly_revenue_share_batches_list",
            "tenant_id",
            "period_month",
            "status",
            "calculated_at",
        ),
    )


class ProviderApplication(Base):
    """Provider Marketplace v2 application intake record.

    This is not the live provider catalog. Applications reserve references for
    later review and shadow validation stories.
    """

    __tablename__ = "provider_applications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    organization_name: Mapped[str] = mapped_column(String(160), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(254), nullable=False)
    homepage_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    openapi_url: Mapped[str] = mapped_column(Text, nullable=False)
    openapi_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    image_digest: Mapped[str] = mapped_column(Text, nullable=False)
    cosign_bundle: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    evaluation_profile: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    application_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_provider_applications_global_application_id",
            "application_id",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
        ),
        Index(
            "uq_provider_applications_tenant_application_id",
            "tenant_id",
            "application_id",
            unique=True,
            postgresql_where=text("tenant_id IS NOT NULL"),
        ),
        Index(
            "uq_provider_applications_global_requested_provider_id",
            "requested_provider_id",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
        ),
        Index(
            "uq_provider_applications_tenant_requested_provider_id",
            "tenant_id",
            "requested_provider_id",
            unique=True,
            postgresql_where=text("tenant_id IS NOT NULL"),
        ),
    )


class ProviderApplicationEvaluationRequest(Base):
    """Evaluation intake request for a submitted provider application."""

    __tablename__ = "provider_application_evaluation_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    application_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    benchmark_suite: Mapped[str] = mapped_column(String(64), nullable=False)
    sample_count: Mapped[int] = mapped_column(nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="requested")
    dataset_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    report_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_provider_application_evaluations_global_eval_id",
            "application_row_id",
            "evaluation_id",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
        ),
        Index(
            "uq_provider_application_evaluations_tenant_eval_id",
            "tenant_id",
            "application_row_id",
            "evaluation_id",
            unique=True,
            postgresql_where=text("tenant_id IS NOT NULL"),
        ),
    )


class ProviderVersionUpdateRequest(Base):
    """Provider version update review contract.

    Version approvals are review records only. They do not mutate the live
    provider catalog or routing state.
    """

    __tablename__ = "provider_version_update_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    application_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version_update_id: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    current_version: Mapped[str] = mapped_column(String(64), nullable=False)
    proposed_version: Mapped[str] = mapped_column(String(64), nullable=False)
    change_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    openapi_url: Mapped[str] = mapped_column(Text, nullable=False)
    openapi_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    image_digest: Mapped[str] = mapped_column(Text, nullable=False)
    cosign_bundle: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    sbom_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    release_notes_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    review_notes_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    record_version: Mapped[int] = mapped_column(nullable=False, default=1)
    update_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_provider_version_updates_global_update_id",
            "application_row_id",
            "version_update_id",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
        ),
        Index(
            "uq_provider_version_updates_tenant_update_id",
            "tenant_id",
            "application_row_id",
            "version_update_id",
            unique=True,
            postgresql_where=text("tenant_id IS NOT NULL"),
        ),
        Index(
            "idx_provider_version_updates_application",
            "application_row_id",
            "status",
            "change_kind",
        ),
    )


class ProviderShadowValidationRun(Base):
    """Shadow validation run gate for a provider application evaluation."""

    __tablename__ = "provider_shadow_validation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    application_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evaluation_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    benchmark_suite: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluation_sample_count: Mapped[int] = mapped_column(nullable=False)
    baseline_provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    evidence_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    run_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_provider_shadow_runs_global_run_id",
            "evaluation_row_id",
            "run_id",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
        ),
        Index(
            "uq_provider_shadow_runs_tenant_run_id",
            "tenant_id",
            "evaluation_row_id",
            "run_id",
            unique=True,
            postgresql_where=text("tenant_id IS NOT NULL"),
        ),
    )


class ProviderShadowValidationSample(Base):
    """Reference-only shadow validation sample result."""

    __tablename__ = "provider_shadow_validation_samples"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    run_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sample_id: Mapped[str] = mapped_column(String(64), nullable=False)
    coverage_class: Mapped[str] = mapped_column(String(32), nullable=False)
    dataset_ref: Mapped[str] = mapped_column(Text, nullable=False)
    case_ref: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider_status_code: Mapped[int] = mapped_column(nullable=False)
    provider_latency_ms: Mapped[int] = mapped_column(nullable=False)
    baseline_latency_ms: Mapped[int] = mapped_column(nullable=False)
    deviation_ratio: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    timed_out: Mapped[bool] = mapped_column(nullable=False, default=False)
    sample_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_provider_shadow_samples_global_sample_id",
            "run_row_id",
            "sample_id",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
        ),
        Index(
            "uq_provider_shadow_samples_tenant_sample_id",
            "tenant_id",
            "run_row_id",
            "sample_id",
            unique=True,
            postgresql_where=text("tenant_id IS NOT NULL"),
        ),
    )


class ProviderGradientRollout(Base):
    """Auditable staged rollout contract derived from a passed shadow run."""

    __tablename__ = "provider_gradient_rollouts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    application_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evaluation_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    shadow_run_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rollout_id: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    baseline_provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    benchmark_suite: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    current_stage_percent: Mapped[int] = mapped_column(nullable=False, default=0)
    stage_history: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    shadow_summary_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    rollout_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_provider_gradient_rollouts_global_rollout_id",
            "shadow_run_row_id",
            "rollout_id",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
        ),
        Index(
            "uq_provider_gradient_rollouts_tenant_rollout_id",
            "tenant_id",
            "shadow_run_row_id",
            "rollout_id",
            unique=True,
            postgresql_where=text("tenant_id IS NOT NULL"),
        ),
    )
