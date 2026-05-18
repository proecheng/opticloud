"""Auth endpoints — signup / api_keys CRUD / login (future) / health.

FR A1 / A2 implementation (Story 0.6).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service import security
from auth_service.db import get_session
from auth_service.models import APIKey, AuditLog, User
from auth_service.schemas import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyListItem,
    SignupRequest,
    SignupResponse,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


# ===== Story 0.7: Health & Readiness =====

health_router = APIRouter(tags=["health"])


@health_router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@health_router.get("/readyz")
async def readyz(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    """Readiness probe — check DB connectivity."""
    try:
        await session.execute(select(1))
        deps = {"db": "ok"}
    except Exception as e:
        return {
            "status": "not-ready",
            "deps": {"db": f"error: {type(e).__name__}"},
        }
    return {"status": "ready", "deps": deps}


# ===== FR A1: signup =====


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="注册新用户（手机+邮箱双因素）",
    description=(
        "FR A1: 任何访客 can register via 手机号+邮箱双因素验证. "
        "Returns user_id + JWT pair. Education tier auto-detected via .edu/.ac.cn email (FR A4)."
    ),
)
async def signup(
    body: SignupRequest,
    session: AsyncSession = Depends(get_session),
) -> SignupResponse:
    # FR A4: .edu / .ac.cn 邮箱自动激活教育版
    edu_tier = body.email.endswith((".edu", ".ac.cn")) or ".edu." in body.email

    # In a real Story 1.x, we'd send OTPs here. Story 0.6 stub assumes verified.
    user = User(phone=body.phone, email=body.email, edu_tier=edu_tier)
    session.add(user)

    try:
        await session.flush()
    except IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="phone or email already registered",
        ) from e

    # Audit log (FR O3 + C3)
    session.add(
        AuditLog(
            user_id=user.id,
            actor="user",
            action="auth.signup",
            resource_type="user",
            resource_id=user.id,
            audit_metadata={"edu_tier": edu_tier},
        )
    )

    access = security.create_access_token(user.id)
    refresh = security.create_refresh_token(user.id)

    return SignupResponse(
        user_id=user.id,
        jwt_access=access,
        jwt_refresh=refresh,
        edu_tier=edu_tier,
    )


# ===== FR A2: api_keys CRUD =====


async def _resolve_user_from_jwt(authorization: str | None) -> uuid.UUID:
    """Extract user_id from Bearer JWT (Story 0.6 stub).

    Production will support API Key Bearer too (D7); for Story 0.6 we focus on JWT.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or malformed Authorization header",
        )

    token = authorization.removeprefix("Bearer ")
    try:
        payload = security.verify_jwt(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {type(e).__name__}",
        ) from e

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not an access token",
        )

    return uuid.UUID(payload["sub"])


@router.post(
    "/api_keys",
    response_model=APIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建新 API Key",
    description=(
        "FR A2: 用户 can create API keys with scoped permissions, label, description, "
        "optional expiration. Returns FULL key ONCE — store it now. "
        "Architecture D7: HMAC-SHA256 with Vault pepper; only hash + prefix persisted."
    ),
)
async def create_api_key(
    body: APIKeyCreateRequest,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> APIKeyCreateResponse:
    user_id = await _resolve_user_from_jwt(authorization)

    # D7: HMAC-SHA256 generation
    full_key, prefix, hmac_hash = security.generate_api_key()

    api_key = APIKey(
        user_id=user_id,
        key_hash=hmac_hash,
        key_prefix=prefix,
        pepper_version=1,
        label=body.label,
        description=body.description,
        scope=body.scope,
        expires_at=body.expires_at,
    )
    session.add(api_key)
    await session.flush()

    # Audit log
    session.add(
        AuditLog(
            user_id=user_id,
            actor="user",
            action="api_keys.create",
            resource_type="api_key",
            resource_id=api_key.id,
            audit_metadata={"label": body.label, "scope": body.scope},
        )
    )

    return APIKeyCreateResponse(
        id=api_key.id,
        api_key=full_key,
        prefix=prefix,
        hash_preview=hmac_hash[:16] + "...",
        label=body.label,
        scope=body.scope,
        expires_at=body.expires_at,
        created_at=api_key.created_at or datetime.now(UTC),
    )


@router.get(
    "/api_keys",
    response_model=list[APIKeyListItem],
    summary="列出 own API Keys",
)
async def list_api_keys(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[APIKeyListItem]:
    user_id = await _resolve_user_from_jwt(authorization)

    result = await session.execute(
        select(APIKey).where(APIKey.user_id == user_id).order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        APIKeyListItem(
            id=k.id,
            prefix=k.key_prefix,
            label=k.label,
            description=k.description,
            scope=k.scope,
            expires_at=k.expires_at,
            last_used_at=k.last_used_at,
            revoked_at=k.revoked_at,
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.delete(
    "/api_keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="吊销 API Key (FR A2)",
)
async def revoke_api_key(
    key_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> None:
    user_id = await _resolve_user_from_jwt(authorization)

    result = await session.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user_id)
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    api_key.revoked_at = datetime.now(UTC)

    session.add(
        AuditLog(
            user_id=user_id,
            actor="user",
            action="api_keys.revoke",
            resource_type="api_key",
            resource_id=key_id,
            audit_metadata={},
        )
    )
