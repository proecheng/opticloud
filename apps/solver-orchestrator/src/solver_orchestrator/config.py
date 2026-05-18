"""Solver orchestrator config (Pydantic Settings)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SolverSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://opticloud:opticloud_dev@localhost:5432/opticloud_dev",  # pragma: allowlist secret
        alias="DATABASE_URL",
    )

    # Shared with auth-service for API Key HMAC verification (D7 + CRG4)
    api_key_hmac_pepper_dev: str = Field(
        default="dev-pepper-do-not-use-in-prod-32-bytes-xxxxxxxx",
        alias="API_KEY_HMAC_PEPPER_DEV",
    )

    # Service
    service_name: str = "solver-orchestrator"
    service_port: int = Field(default=8002, alias="SOLVER_ORCHESTRATOR_PORT")

    # Solver tuning (CRG2 — cold/warm start)
    highs_prewarm: bool = Field(default=True, description="Pre-warm HiGHS at startup")
    sync_max_seconds: float = Field(default=5.0, description="FR E3 sync mode threshold")

    # Story 5.A.4 — cross-service billing
    billing_base_url: str = Field(
        default="http://localhost:8003",
        alias="BILLING_BASE_URL",
        description="Billing-service base URL (host:port; no trailing slash)",
    )
    billing_service_shared_secret: str = Field(
        default="",
        alias="BILLING_SERVICE_SHARED_SECRET",
        description="Shared secret for X-Internal-Service-Auth (R1.2); empty disables integration",
    )
    billing_callback_timeout_seconds: float = Field(
        default=2.0,
        alias="BILLING_CALLBACK_TIMEOUT_SECONDS",
        description="Single-attempt timeout per billing call (Q4)",
    )


settings = SolverSettings()
