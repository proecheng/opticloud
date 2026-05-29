from __future__ import annotations

import secrets

from chat_service.config import InternalBetaConfig


class InternalBetaAccessDeniedError(Exception):
    """Raised when the internal beta gate should fail closed."""


def validate_internal_beta_access(
    config: InternalBetaConfig,
    *,
    tenant: str | None,
    user: str | None,
    token: str | None,
) -> None:
    if not config.access_configured:
        raise InternalBetaAccessDeniedError
    if tenant != config.tenant:
        raise InternalBetaAccessDeniedError
    if user is None or user not in config.users:
        raise InternalBetaAccessDeniedError
    if token is None or not secrets.compare_digest(token, config.token):
        raise InternalBetaAccessDeniedError
