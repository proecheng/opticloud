"""API Key Bearer auth — verify against auth-service's api_keys table.

Architecture references:
- D7 HMAC-SHA256 with Vault pepper (shared with auth-service)
- CRG4 pepper rotation (multi-pepper grace 30d)
- Sprint 0: query shared Postgres directly via raw SQL (avoid metadata conflict).
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from solver_orchestrator.config import settings


def _hmac_sha256(full_key: str, pepper_version: int) -> str:
    """HMAC-SHA256(pepper, full_key) → hex digest.

    pepper_version: 1 = current dev; production lookup from Vault by version (CRG4).
    """
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    return hmac.new(pepper, full_key.encode("utf-8"), hashlib.sha256).hexdigest()


async def verify_api_key(
    authorization: str | None, session: AsyncSession
) -> tuple[uuid.UUID, uuid.UUID, list[str]]:
    """Verify Bearer API Key. Returns (user_id, api_key_id, scopes).

    Raises 401 if invalid / revoked / expired.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or malformed Authorization header (expected: Bearer sk-...)",
        )

    full_key = authorization.removeprefix("Bearer ").strip()
    if not full_key.startswith("sk-"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key must start with 'sk-'",
        )

    key_prefix = full_key[:6]

    # Look up candidate keys by prefix (cheap index scan)
    result = await session.execute(
        text(
            """
            SELECT id, user_id, key_hash, pepper_version, scope, revoked_at, expires_at
            FROM api_keys
            WHERE key_prefix = :prefix
            """
        ),
        {"prefix": key_prefix},
    )
    candidates = result.fetchall()

    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key not found",
        )

    now = datetime.now(UTC)
    for row in candidates:
        # row: (id, user_id, key_hash, pepper_version, scope, revoked_at, expires_at)
        key_id, user_id_val, key_hash, pepper_version, scope, revoked_at, expires_at = row
        if revoked_at is not None:
            continue
        if expires_at is not None and expires_at < now:
            continue
        computed = _hmac_sha256(full_key, pepper_version)
        if hmac.compare_digest(computed, key_hash):
            # Story 1.3 — track last_used_at; same session, rolls back if request fails downstream
            await session.execute(
                text("UPDATE api_keys SET last_used_at = NOW() WHERE id = :id"),
                {"id": key_id},
            )
            return user_id_val, key_id, list(scope or [])

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="API Key invalid or revoked",
    )


def require_scope(required: str, scopes: list[str]) -> None:
    """Enforce scope check (FR A2 scoped permissions)."""
    if required not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"insufficient scope (required: {required}, have: {scopes})",
        )
