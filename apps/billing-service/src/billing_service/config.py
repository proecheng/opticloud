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


settings = Settings()
