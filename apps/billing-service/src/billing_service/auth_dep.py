"""FastAPI auth dependency — extracts user_id from JWT (Story 5.A.1 T1).

Uses the shared verifier in opticloud_shared.auth. User ID always comes from
the JWT `sub` claim (S2 lock — never from path/query/body).
"""

from __future__ import annotations

import uuid

from fastapi import Header, HTTPException, status
from opticloud_shared.auth import JWTVerifyError, PublicKeyLoader, verify_jwt
from opticloud_shared.errors import rfc7807_error

from billing_service.config import settings

_loader = PublicKeyLoader(settings.jwt_public_key_path)


async def require_user(authorization: str | None = Header(default=None)) -> uuid.UUID:
    """Extract user_id from Bearer JWT. Raises 401/503 on failure."""
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


__all__ = ["require_user", "rfc7807_error"]
