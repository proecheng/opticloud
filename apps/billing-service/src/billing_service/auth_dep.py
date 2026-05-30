"""FastAPI auth dependency — extracts user_id from JWT (Story 5.A.1 T1).

Uses the shared verifier in opticloud_shared.auth. User ID always comes from
the JWT `sub` claim (S2 lock — never from path/query/body).

Story 5.A.4: optionally also accepts an internal-service header pair
(X-Internal-Service-Auth + X-Internal-User-Id) when enabled. Solver-orchestrator
uses this to call billing on behalf of a verified API-Key holder. Constant-time
comparison via hmac.compare_digest (S1).
"""

from __future__ import annotations

import hmac
import uuid

from fastapi import Header, HTTPException, status
from opticloud_shared.auth import JWTVerifyError, PublicKeyLoader, verify_jwt
from opticloud_shared.errors import rfc7807_error

from billing_service.config import settings

_loader = PublicKeyLoader(settings.jwt_public_key_path)


async def require_user(
    authorization: str | None = Header(default=None),
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    x_internal_user_id: str | None = Header(default=None, alias="X-Internal-User-Id"),
) -> uuid.UUID:
    """Extract user_id from Bearer JWT, OR from internal-service bridge (5.A.4).

    Order: internal-service first (cheaper, no key load), then JWT fallback.
    Returns the trusted user_id UUID.
    """
    if settings.internal_service_auth_enabled and x_internal_service_auth is not None:
        expected = settings.internal_service_secret.get_secret_value()
        if expected and hmac.compare_digest(x_internal_service_auth, expected):
            if not x_internal_user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="X-Internal-User-Id required with X-Internal-Service-Auth",
                )
            try:
                return uuid.UUID(x_internal_user_id)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="X-Internal-User-Id is not a UUID",
                ) from e

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or malformed Authorization header",
        )
    token = authorization.removeprefix("Bearer ").strip()

    try:
        public_key = _loader.load()
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e

    try:
        claims = verify_jwt(token, public_key)
    except JWTVerifyError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {e}",
        ) from e

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token missing sub claim",
        )
    try:
        return uuid.UUID(sub)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token sub is not a UUID",
        ) from e


async def require_internal_service(
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
) -> None:
    """Require the billing internal shared secret for payment-confirmation routes."""
    expected = settings.internal_service_secret.get_secret_value()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="billing internal service secret is not configured",
        )
    if x_internal_service_auth is None or not hmac.compare_digest(
        x_internal_service_auth, expected
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid internal service auth",
        )


async def require_internal_user(
    x_internal_service_auth: str | None = Header(default=None, alias="X-Internal-Service-Auth"),
    x_internal_user_id: str | None = Header(default=None, alias="X-Internal-User-Id"),
) -> uuid.UUID:
    """Require service auth and return the acting user id without JWT fallback."""
    await require_internal_service(x_internal_service_auth)
    if not x_internal_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Internal-User-Id required with X-Internal-Service-Auth",
        )
    try:
        return uuid.UUID(x_internal_user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Internal-User-Id is not a UUID",
        ) from e


__all__ = ["require_internal_service", "require_internal_user", "require_user", "rfc7807_error"]
