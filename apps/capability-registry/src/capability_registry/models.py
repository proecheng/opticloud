"""SQLAlchemy models for capability-registry tables."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Text, func, text
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
