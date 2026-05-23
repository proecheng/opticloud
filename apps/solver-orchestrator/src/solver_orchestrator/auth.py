"""API Key Bearer auth — verify against auth-service's api_keys table.

Architecture references:
- D7 HMAC-SHA256 with Vault pepper (shared with auth-service)
- CRG4 pepper rotation (multi-pepper grace 30d)
- Sprint 0: query shared Postgres directly via raw SQL (avoid metadata conflict).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from solver_orchestrator.config import settings
from solver_orchestrator.geo_risk import (
    DETECTOR_VERSION,
    bucket_for_ip,
    is_geo_anomaly,
    label_for_bucket_code,
    next_risk_score,
    normalize_ip,
)


def _hmac_sha256(full_key: str, pepper_version: int) -> str:
    """HMAC-SHA256(pepper, full_key) → hex digest.

    pepper_version: 1 = current dev; production lookup from Vault by version (CRG4).
    """
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    return hmac.new(pepper, full_key.encode("utf-8"), hashlib.sha256).hexdigest()


async def verify_api_key(
    authorization: str | None,
    session: AsyncSession,
    client_ip: str | None = None,
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
            SELECT
                id,
                user_id,
                key_hash,
                pepper_version,
                scope,
                revoked_at,
                expires_at,
                host(last_used_ip)::text AS last_used_ip,
                last_used_geo_bucket,
                geo_risk_score
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
        (
            key_id,
            user_id_val,
            key_hash,
            pepper_version,
            scope,
            revoked_at,
            expires_at,
            last_used_ip,
            last_used_geo_bucket,
            geo_risk_score,
        ) = row
        if revoked_at is not None:
            continue
        if expires_at is not None and expires_at < now:
            continue
        computed = _hmac_sha256(full_key, pepper_version)
        if hmac.compare_digest(computed, key_hash):
            await _record_api_key_use(
                session,
                key_id=key_id,
                user_id=user_id_val,
                client_ip=client_ip,
                previous_ip=str(last_used_ip) if last_used_ip is not None else None,
                previous_bucket=last_used_geo_bucket,
                current_geo_risk_score=geo_risk_score,
            )
            return user_id_val, key_id, list(scope or [])

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="API Key invalid or revoked",
    )


async def _record_api_key_use(
    session: AsyncSession,
    *,
    key_id: uuid.UUID,
    user_id: uuid.UUID,
    client_ip: str | None,
    previous_ip: str | None,
    previous_bucket: str | None,
    current_geo_risk_score: Decimal | float | str | None,
) -> None:
    """Track successful API-key use and record geo anomaly evidence when deterministic."""
    normalized_ip = normalize_ip(client_ip)
    bucket = bucket_for_ip(normalized_ip)
    current_bucket = bucket.code if bucket else None

    update_values: dict[str, object] = {
        "id": key_id,
        "has_ip": normalized_ip is not None,
        "last_used_ip": normalized_ip,
        "has_geo_bucket": current_bucket is not None,
        "last_used_geo_bucket": current_bucket,
        "is_anomaly": False,
        "geo_risk_score": current_geo_risk_score or Decimal("0.00"),
        "geo_anomaly_metadata": "{}",
    }

    if is_geo_anomaly(previous_bucket, current_bucket):
        new_score = next_risk_score(current_geo_risk_score)
        metadata = {
            "event_kind": "geo_anomaly",
            "api_key_id": str(key_id),
            "previous_geo_bucket": previous_bucket,
            "previous_geo_label_zh": label_for_bucket_code(previous_bucket),
            "current_geo_bucket": current_bucket,
            "current_geo_label_zh": bucket.label_zh if bucket else None,
            "previous_ip": previous_ip,
            "current_ip": normalized_ip,
            "risk_delta": "0.35",
            "geo_risk_score": str(new_score),
            "detector_version": DETECTOR_VERSION,
        }
        update_values["is_anomaly"] = True
        update_values["geo_risk_score"] = new_score
        update_values["geo_anomaly_metadata"] = json.dumps(metadata)
        await session.execute(
            text(
                """
                INSERT INTO risk_flags (user_id, rule_code, source, metadata)
                VALUES (:user_id, 'geo_anomaly', 'auto', CAST(:metadata AS jsonb))
                """
            ),
            {"user_id": user_id, "metadata": update_values["geo_anomaly_metadata"]},
        )
        await session.execute(
            text(
                """
                INSERT INTO audit_logs
                    (user_id, actor, action, resource_type, resource_id, metadata, ip_address)
                VALUES
                    (
                        :user_id,
                        'system',
                        'api_keys.geo_anomaly',
                        'api_key',
                        :key_id,
                        CAST(:metadata AS jsonb),
                        CAST(:ip_address AS inet)
                    )
                """
            ),
            {
                "user_id": user_id,
                "key_id": key_id,
                "metadata": update_values["geo_anomaly_metadata"],
                "ip_address": normalized_ip,
            },
        )
        await session.execute(
            text(
                """
                UPDATE users
                SET risk_score = GREATEST(risk_score, :geo_risk_score)
                WHERE id = :user_id
                """
            ),
            {"user_id": user_id, "geo_risk_score": new_score},
        )

    await session.execute(
        text(
            """
            UPDATE api_keys
            SET
                last_used_at = NOW(),
                last_used_ip = CASE
                    WHEN :has_ip THEN CAST(:last_used_ip AS inet)
                    ELSE last_used_ip
                END,
                last_used_geo_bucket = CASE
                    WHEN :has_geo_bucket THEN :last_used_geo_bucket
                    ELSE last_used_geo_bucket
                END,
                geo_risk_score = CASE
                    WHEN :is_anomaly THEN :geo_risk_score
                    ELSE geo_risk_score
                END,
                geo_anomaly_at = CASE
                    WHEN :is_anomaly THEN NOW()
                    ELSE geo_anomaly_at
                END,
                geo_anomaly_metadata = CASE
                    WHEN :is_anomaly THEN CAST(:geo_anomaly_metadata AS jsonb)
                    ELSE geo_anomaly_metadata
                END
            WHERE id = :id
            """
        ),
        update_values,
    )


def require_scope(required: str, scopes: list[str]) -> None:
    """Enforce scope check (FR A2 scoped permissions)."""
    if required not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"insufficient scope (required: {required}, have: {scopes})",
        )
