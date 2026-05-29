from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

REQUIRED_SIGNOFF = "founder-legal-approved"
DEFAULT_INTERNAL_BETA_TENANT = "research-staging"
MAX_INTERNAL_BETA_USERS = 5


@dataclass(frozen=True)
class InternalBetaConfig:
    enabled: bool
    signoff: str
    tenant: str
    users: tuple[str, ...]
    token: str
    max_users: int = MAX_INTERNAL_BETA_USERS

    @property
    def access_configured(self) -> bool:
        return (
            self.enabled
            and self.signoff == REQUIRED_SIGNOFF
            and self.tenant != ""
            and 0 < len(self.users) <= self.max_users
            and self.token != ""
        )


def load_internal_beta_config(env: Mapping[str, str] | None = None) -> InternalBetaConfig:
    env_map = os.environ if env is None else env
    return InternalBetaConfig(
        enabled=_env_flag(env_map.get("CHAT_INTERNAL_BETA_ENABLED", "")),
        signoff=env_map.get("CHAT_INTERNAL_BETA_SIGNOFF", "").strip(),
        tenant=env_map.get("CHAT_INTERNAL_BETA_TENANT", DEFAULT_INTERNAL_BETA_TENANT).strip(),
        users=_split_csv(env_map.get("CHAT_INTERNAL_BETA_USERS", "")),
        token=env_map.get("CHAT_INTERNAL_BETA_TOKEN", "").strip(),
    )


def _env_flag(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())
