"""Capability-registry service settings."""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://opticloud:opticloud_dev@localhost:5432/opticloud_dev",  # pragma: allowlist secret
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")
    cache_ttl_seconds: int = Field(default=60, alias="CAPABILITY_CACHE_TTL_SECONDS")
    service_port: int = Field(default=8006, alias="CAPABILITY_REGISTRY_PORT")
    internal_secret: SecretStr = Field(
        default=SecretStr(""),
        alias="CAPABILITY_REGISTRY_INTERNAL_SECRET",
        description="Shared secret for X-Internal-Service-Auth write protection.",
    )


settings = Settings()
