"""Billing service configuration."""

from __future__ import annotations

from pydantic import Field
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


settings = Settings()
