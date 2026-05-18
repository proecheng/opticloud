"""Configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Drop the +asyncpg suffix — asyncpg uses postgres:// not the SQLAlchemy dialect prefix.
    # Default also points at localhost; docker-compose overrides to "postgres" hostname.
    database_url: str = Field(
        default="postgresql://opticloud:opticloud_dev@localhost:5432/opticloud_dev",  # pragma: allowlist secret
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")
    health_port: int = Field(default=9101, alias="HEALTH_PORT")

    poll_interval_seconds: float = Field(default=0.1, alias="POLL_INTERVAL_SECONDS")
    batch_size: int = Field(default=100, alias="BATCH_SIZE")
    max_retries: int = Field(default=10, alias="MAX_RETRIES")
    listen_channel: str = Field(default="outbox_new", alias="LISTEN_CHANNEL")


settings = Settings()
