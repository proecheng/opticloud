"""API Key Bearer auth — verify against auth-service's api_keys table.

Architecture references:
- D7 HMAC-SHA256 with Vault pepper (shared with auth-service)
- CRG4 pepper rotation (multi-pepper grace 30d)
- Sprint 0: query shared Postgres directly via raw SQL (avoid metadata conflict).
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from solver_orchestrator.config import settings
from solver_orchestrator.geo_risk import (
    GEO_ANOMALY_RULE_CODE,
    GeoAnomaly,
    assess_geo_anomaly,
)


def _hmac_sha256(full_key: str, pepper_version: int) -> str:
    """HMAC-SHA256(pepper, full_key) → hex digest.

    pepper_version: 1 = current dev; production lookup from Vault by version (CRG4).
    """
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    return hmac.new(pepper, full_key.encode("utf-8"), hashlib.sha256).hexdigest()


def _normalized_inet_value(ip_value: str | None) -> str | None:
    if not ip_value:
        return None
    try:
        return str(ipaddress.ip_address(ip_value))
    except ValueError:
        return None


def _geo_anomaly_metadata(api_key_id: uuid.UUID, anomaly: GeoAnomaly) -> dict[str, object]:
    return {
        "api_key_id": str(api_key_id),
        "previous_ip": anomaly.previous_ip,
        "current_ip": anomaly.current_ip,
        "previous_geo": {
            "code": anomaly.previous_geo.code,
            "label_zh": anomaly.previous_geo.label_zh,
        },
        "current_geo": {
            "code": anomaly.current_geo.code,
            "label_zh": anomaly.current_geo.label_zh,
        },
        "reason": anomaly.reason,
        "score": anomaly.score,
    }


async def _record_successful_key_use(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    key_id: uuid.UUID,
    previous_ip: object | None,
    caller_ip: str | None,
) -> None:
    """Update last-used fields and persist geo anomaly score evidence when applicable."""
    normalized_caller_ip = _normalized_inet_value(caller_ip)
    anomaly = assess_geo_anomaly(
        str(previous_ip) if previous_ip is not None else None,
        normalized_caller_ip,
    )
    if normalized_caller_ip is None:
        await session.execute(
            text("UPDATE api_keys SET last_used_at = NOW() WHERE id = :id"),
            {"id": key_id},
        )
    else:
        await session.execute(
            text(
                "UPDATE api_keys "
                "SET last_used_at = NOW(), last_used_ip = CAST(:caller_ip AS inet) "
                "WHERE id = :id"
            ),
            {"id": key_id, "caller_ip": normalized_caller_ip},
        )
    if anomaly is None:
        return

    metadata = _geo_anomaly_metadata(key_id, anomaly)
    await session.execute(
        text(
            "INSERT INTO risk_flags (user_id, rule_code, source, metadata) "
            "VALUES (:uid, :rule_code, 'auto', CAST(:metadata AS jsonb))"
        ),
        {
            "uid": user_id,
            "rule_code": GEO_ANOMALY_RULE_CODE,
            "metadata": json.dumps(metadata, ensure_ascii=False),
        },
    )
    await session.execute(
        text(
            "UPDATE users "
            "SET risk_score = GREATEST(risk_score, CAST(:score AS numeric)) "
            "WHERE id = :uid"
        ),
        {"uid": user_id, "score": anomaly.score},
    )


async def verify_api_key(
    authorization: str | None, session: AsyncSession, caller_ip: str | None = None
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
            SELECT id, user_id, key_hash, pepper_version, scope, revoked_at, expires_at,
                   last_used_ip
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
        # row: (id, user_id, key_hash, pepper_version, scope, revoked_at, expires_at, last_used_ip)
        (
            key_id,
            user_id_val,
            key_hash,
            pepper_version,
            scope,
            revoked_at,
            expires_at,
            last_used_ip,
        ) = row
        if revoked_at is not None:
            continue
        if expires_at is not None and expires_at < now:
            continue
        computed = _hmac_sha256(full_key, pepper_version)
        if hmac.compare_digest(computed, key_hash):
            # Story 1.3 + 1.11 — track last-used fields and geo anomaly score evidence.
            await _record_successful_key_use(
                session,
                user_id=user_id_val,
                key_id=key_id,
                previous_ip=last_used_ip,
                caller_ip=caller_ip,
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
