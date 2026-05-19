"""Auth service config (Pydantic Settings + env vars from .env)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    """Auth service settings — loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ----- Database -----
    database_url: str = Field(
        default="postgresql+asyncpg://opticloud:opticloud_dev@localhost:5432/opticloud_dev",
        alias="DATABASE_URL",
    )

    # ----- API Key HMAC (D7 + CRG4 pepper rotation) -----
    api_key_hmac_pepper_dev: str = Field(
        default="dev-pepper-do-not-use-in-prod-32-bytes-xxxxxxxx",
        alias="API_KEY_HMAC_PEPPER_DEV",
    )
    api_key_pepper_version: int = 1  # CRG4: 多 pepper grace period 支持

    # ----- JWT Ed25519 (D8) -----
    jwt_private_key_path: str = Field(
        default="./infra/local-init/dev-jwt-ed25519.key",
        alias="JWT_PRIVATE_KEY_PATH",
    )
    jwt_public_key_path: str = Field(
        default="./infra/local-init/dev-jwt-ed25519.pub",
        alias="JWT_PUBLIC_KEY_PATH",
    )
    jwt_access_ttl_minutes: int = Field(default=15, alias="JWT_ACCESS_TTL_MINUTES")
    jwt_refresh_ttl_days: int = Field(default=7, alias="JWT_REFRESH_TTL_DAYS")

    # ----- Service -----
    service_name: str = "auth-service"
    service_port: int = Field(default=8001, alias="AUTH_SERVICE_PORT")

    # ----- 风控 (FR A5) -----
    risk_freeze_threshold: float = 0.9  # 任 2 项触发冻结

    # ----- Story 1.2 — OTP login (FR A1 双因素) -----
    otp_dev_mode_return: bool = Field(default=True, alias="OTP_DEV_MODE_RETURN")
    otp_ttl_seconds: int = Field(default=300, alias="OTP_TTL_SECONDS")


settings = AuthSettings()
