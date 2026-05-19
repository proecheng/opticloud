"""Auth endpoints — signup / login (Story 1.2) / api_keys CRUD / health.

FR A1 / A2 implementation (Story 0.6 + 1.2).
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import and_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service import risk, security
from auth_service.config import settings
from auth_service.db import get_session
from auth_service.models import APIKey, AuditLog, User, UserOTP
from auth_service.schemas import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyListItem,
    LoginRequest,
    LoginResponse,
    OTPRequestBody,
    OTPRequestResponse,
    SignupRequest,
    SignupResponse,
)

_log = structlog.get_logger("auth_service.routes")

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
    request: Request,
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

    # Story 1.4 — FR A4: seed edu bucket on edu_tier=true signup.
    # Raw SQL because auth-service doesn't import billing's ORM models (clean service
    # boundary). Same session as the user INSERT → transactional atomicity.
    edu_seed_amount: str | None = None
    if edu_tier:
        edu_seed_amount = settings.edu_signup_seed_amount
        await session.execute(
            text(
                "INSERT INTO credit_transactions "
                "(user_id, saga_id, amount, kind, bucket, currency, metadata, created_at) "
                "VALUES (:uid, NULL, :amt, 'topup', 'edu', 'CNY', "
                "CAST(:meta AS jsonb), NOW())"
            ),
            {
                "uid": user.id,
                "amt": edu_seed_amount,
                "meta": '{"source": "edu_tier_signup"}',
            },
        )

    # Audit log (FR O3 + C3). ip_address feeds Story 1.5's R3 ip_24_share detector.
    signup_ip = request.client.host if request.client else None
    session.add(
        AuditLog(
            user_id=user.id,
            actor="user",
            action="auth.signup",
            resource_type="user",
            resource_id=user.id,
            ip_address=signup_ip,
            audit_metadata={
                "edu_tier": edu_tier,
                "edu_signup_seed_amount": edu_seed_amount,
            },
        )
    )
    await session.flush()  # AuditLog must be queryable by risk.evaluate_signup below

    # FR A5 — risk evaluation. With only ip_24_share enabled in v1 a single
    # signup never freezes (count<2); admin manual flag is the v1 second slot.
    triggered = await risk.evaluate_signup(session, user.id, signup_ip)
    if triggered:
        new_flags = [(code, "auto", {"signup_ip": signup_ip}) for code in triggered]
        await risk.apply_flags_and_maybe_freeze(session, user.id, new_flags)

    access = security.create_access_token(user.id)
    refresh = security.create_refresh_token(user.id)

    return SignupResponse(
        user_id=user.id,
        jwt_access=access,
        jwt_refresh=refresh,
        edu_tier=edu_tier,
    )


# ===== Story 1.2: OTP login (FR A1 双因素) =====


async def _lookup_user(session: AsyncSession, phone: str, email: str) -> User | None:
    stmt = select(User).where(and_(User.phone == phone, User.email == email))
    return (await session.execute(stmt)).scalar_one_or_none()


def _generate_otp() -> str:
    """6-digit numeric OTP, zero-padded."""
    return f"{secrets.randbelow(1_000_000):06d}"


async def _invalidate_unused_otps(session: AsyncSession, user_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    await session.execute(
        update(UserOTP)
        .where(and_(UserOTP.user_id == user_id, UserOTP.used_at.is_(None)))
        .values(used_at=now)
    )


@router.post(
    "/otp/request",
    response_model=OTPRequestResponse,
    summary="请求登录 OTP 双因素验证码",
    description=(
        "FR A1: 请求登录所需的双 OTP（phone + email）。每个 factor 一个 6 位数字 OTP，"
        "TTL 5 分钟。响应中 `dev_phone_otp` / `dev_email_otp` 仅在 `OTP_DEV_MODE_RETURN=true` "
        "（local dev 默认）时返回；生产环境通过 logs 派发到 SMS/Email provider（M3 集成）。"
    ),
)
async def request_otp(
    body: OTPRequestBody,
    session: AsyncSession = Depends(get_session),
) -> OTPRequestResponse:
    user = await _lookup_user(session, body.phone, body.email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )
    if user.is_frozen:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account frozen",
        )

    await _invalidate_unused_otps(session, user.id)

    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=settings.otp_ttl_seconds)
    phone_otp = _generate_otp()
    email_otp = _generate_otp()
    session.add_all(
        [
            UserOTP(
                user_id=user.id,
                factor="phone",
                code=phone_otp,
                expires_at=expires_at,
                used_at=None,
                created_at=now,
            ),
            UserOTP(
                user_id=user.id,
                factor="email",
                code=email_otp,
                expires_at=expires_at,
                used_at=None,
                created_at=now,
            ),
        ]
    )
    await session.commit()

    _log.info(
        "auth.otp.requested",
        user_id=str(user.id),
        factors=["phone", "email"],
        ttl_s=settings.otp_ttl_seconds,
    )

    return OTPRequestResponse(
        expires_in_seconds=settings.otp_ttl_seconds,
        factors=["phone", "email"],
        dev_phone_otp=phone_otp if settings.otp_dev_mode_return else None,
        dev_email_otp=email_otp if settings.otp_dev_mode_return else None,
    )


async def _verify_otp(
    session: AsyncSession, user_id: uuid.UUID, factor: str, provided_code: str
) -> bool:
    """Return True iff a valid unused-and-unexpired OTP for (user, factor) matches."""
    now = datetime.now(UTC)
    stmt = (
        select(UserOTP)
        .where(
            and_(
                UserOTP.user_id == user_id,
                UserOTP.factor == factor,
                UserOTP.used_at.is_(None),
                UserOTP.expires_at > now,
            )
        )
        .order_by(UserOTP.created_at.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return False
    return secrets.compare_digest(row.code, provided_code)


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="OTP 双因素登录",
    description=(
        "FR A1: 已注册用户用 phone + email + 两个 6 位 OTP 登录。两个 OTP 任一错误 / 过期 / 已使用 "
        "→ 401 且 detail 不指明哪个 factor（防 enumeration）。"
    ),
)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    user = await _lookup_user(session, body.phone, body.email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )
    if user.is_frozen:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account frozen",
        )

    # Verify BOTH OTPs without short-circuit (S1 — don't leak which failed first via timing).
    phone_ok = await _verify_otp(session, user.id, "phone", body.phone_otp)
    email_ok = await _verify_otp(session, user.id, "email", body.email_otp)
    if not (phone_ok and email_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired OTP",
        )

    # Both verified — invalidate ALL unused OTPs for this user (prevents replay).
    await _invalidate_unused_otps(session, user.id)

    session.add(
        AuditLog(
            user_id=user.id,
            actor="user",
            action="auth.login",
            resource_type="user",
            resource_id=user.id,
            audit_metadata={"factors": ["phone", "email"]},
        )
    )
    await session.commit()

    _log.info("auth.login.success", user_id=str(user.id))

    return LoginResponse(
        user_id=user.id,
        jwt_access=security.create_access_token(user.id),
        jwt_refresh=security.create_refresh_token(user.id),
        edu_tier=user.edu_tier,
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
