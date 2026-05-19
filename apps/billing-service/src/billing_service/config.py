"""Billing service configuration."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://opticloud:opticloud_dev@localhost:5432/opticloud_dev",  # pragma: allowlist secret
        alias="DATABASE_URL",
    )

    saga_idempotency_ttl_hours: int = Field(default=24, alias="SAGA_IDEMPOTENCY_TTL_HOURS")
    saga_lock_timeout_ms: int = Field(default=1000, alias="SAGA_LOCK_TIMEOUT_MS")

    # JWT — shared keypair with auth-service (DR2 lock: same path)
    jwt_public_key_path: str = Field(default="secrets/jwt_public.pem", alias="JWT_PUBLIC_KEY_PATH")

    # Demo seeding (Story 5.A.1 AC2)
    j1_demo_seed_amount: str = Field(default="50.00", alias="J1_DEMO_SEED_AMOUNT")
    default_charge_amount: str = Field(default="6.00", alias="DEFAULT_CHARGE_AMOUNT")

    # Story 5.A.4 — per-formula pricing
    lp_rate_per_second: Decimal = Field(
        default=Decimal("0.10"),
        alias="LP_RATE_PER_SECOND",
        description="CNY/sec for LP solves; 0.10 × 60s = 6.00 (5.A.1 baseline)",
    )
    charge_min_amount: Decimal = Field(
        default=Decimal("0.01"),
        alias="CHARGE_MIN_AMOUNT",
        description="Floor — prevents zero-charge from sub-cent solves",
    )
    charge_max_solve_seconds_default: float = Field(
        default=60.0,
        alias="CHARGE_MAX_SOLVE_SECONDS_DEFAULT",
        description="Fallback when saga.payload_ref lacks max_solve_seconds (DR1)",
    )

    # Story 5.A.5 — pre-charge guard thresholds (FR B6)
    p5_call_threshold: Decimal = Field(
        default=Decimal("3.00"),
        alias="P5_CALL_THRESHOLD",
        description="Estimated max charge >= this triggers p5_call warning (¥)",
    )
    balance_low_ratio: Decimal = Field(
        default=Decimal("1.00"),
        alias="BALANCE_LOW_RATIO",
        description="balance < (estimated × ratio) triggers balance_low warning",
    )

    # Story 5.A.4 — internal service auth (R1.2)
    # Solver→billing call uses constant-time-compared shared secret + user_id header.
    # If empty AND internal_service_auth_enabled=True at startup, billing fails fast.
    internal_service_secret: SecretStr = Field(
        default=SecretStr(""),
        alias="BILLING_SERVICE_SHARED_SECRET",
        description="64-char hex shared secret for X-Internal-Service-Auth bridge",
    )
    internal_service_auth_enabled: bool = Field(
        default=False,
        alias="INTERNAL_SERVICE_AUTH_ENABLED",
        description="Enable X-Internal-Service-Auth header path; off in v1 unit tests",
    )


settings = Settings()
