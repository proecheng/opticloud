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
    # Reserved for Story 1.11 (geo-anomaly risk-scoring). Story 1.5 uses the
    # discrete COUNT threshold defined in `risk.FREEZE_THRESHOLD = 2` instead.
    risk_freeze_threshold: float = 0.9

    # Story 1.5 — admin shared-secret for /v1/admin/* endpoints (FR A5 manual flag + unfreeze).
    # Empty default → admin endpoints return 403 (fail-closed). v1 only; M2+ uses real RBAC.
    admin_secret: str = Field(
        default="",
        alias="ADMIN_SECRET",
        description="X-Admin-Secret header value for admin endpoints; empty → endpoints 403.",
    )

    # ----- Story 1.2 — OTP login (FR A1 双因素) -----
    otp_dev_mode_return: bool = Field(default=True, alias="OTP_DEV_MODE_RETURN")
    otp_ttl_seconds: int = Field(default=300, alias="OTP_TTL_SECONDS")

    # ----- Story 1.9 — guardian consent for 14-17 signup (FR A10) -----
    guardian_consent_dev_mode_return: bool = Field(
        default=True,
        alias="GUARDIAN_CONSENT_DEV_MODE_RETURN",
        description="Return dev guardian consent token in signup 202 response for local tests.",
    )
    guardian_consent_ttl_seconds: int = Field(
        default=86_400,
        gt=0,
        alias="GUARDIAN_CONSENT_TTL_SECONDS",
        description="Guardian consent token validity window in seconds.",
    )
    guardian_consent_token_pepper_dev: str = Field(
        default="dev-guardian-consent-pepper-do-not-use-in-prod-32-bytes",
        alias="GUARDIAN_CONSENT_TOKEN_PEPPER_DEV",
        description="Dev HMAC pepper for guardian consent token hashes.",
    )

    # ----- Story 1.4 — edu tier auto-activation (FR A4 + B8) -----
    edu_signup_seed_amount: str = Field(
        default="2000.00",
        alias="EDU_SIGNUP_SEED_AMOUNT",
        description="CNY credited to bucket='edu' on .edu/.ac.cn signup",
    )


settings = AuthSettings()
