"""Auth endpoints — signup / login (Story 1.2) / api_keys CRUD / health.

FR A1 / A2 implementation (Story 0.6 + 1.2).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import uuid
from binascii import Error as BinasciiError
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from ipaddress import IPv4Address, IPv6Address
from typing import Literal

import structlog
from fastapi import (
    APIRouter,
    Body,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy import and_, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service import (
    account_deletion,
    account_merge,
    data_export,
    frozen_appeals,
    risk,
    security,
)
from auth_service.config import settings
from auth_service.db import get_session
from auth_service.models import (
    APIKey,
    AuditLog,
    GuardianConsentRequest,
    NotificationPreference,
    OutboxEvent,
    User,
    UserOTP,
)
from auth_service.schemas import (
    SUPPORTED_NOTIFICATION_EVENTS,
    AccountDeletionStatusResponse,
    AccountMergeProposalCreateRequest,
    AccountMergeProposalResponse,
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyGeoAnomalyWarning,
    APIKeyListItem,
    AuditLogItem,
    DataExportCreateRequest,
    DataExportStatusResponse,
    GuardianConsentPendingResponse,
    LoginRequest,
    LoginResponse,
    NotificationPreferenceItem,
    NotificationPreferenceResponseItem,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdateRequest,
    OTPRequestBody,
    OTPRequestResponse,
    SignupRequest,
    SignupResponse,
    UserAuditLogsResponse,
    notification_channels,
    notification_event_defaults,
)

_log = structlog.get_logger("auth_service.routes")

router = APIRouter(prefix="/v1/auth", tags=["auth"])
me_router = APIRouter(prefix="/v1/me", tags=["me"])

_AUDIT_LOG_DEFAULT_WINDOW_DAYS = 30
_AUDIT_LOG_DEFAULT_LIMIT = 50
_AUDIT_LOG_MAX_LIMIT = 100
_AUDIT_LOG_CURSOR_VERSION = 1
_AUDIT_LOG_CURSOR_SIGNATURE_BYTES = 32
_AUDIT_SAFE_METADATA_KEYS = {"webhook_url_configured"}
_AUDIT_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|key[_-]?hash|token(?:[_-]?hash)?|tracking[_-]?token|"
    r"guardian[_-]?consent[_-]?token|authorization|jwt|password|pepper|otp|"
    r"secret|cookie|webhook(?:[_-]?url)?|provider[_-]?(?:payload|request|response)|"
    r"raw[_-]?(?:request|response|payload|body))",
    re.IGNORECASE,
)
_AUDIT_SECRET_VALUE_RE = re.compile(
    r"(Bearer\s+[A-Za-z0-9._~+/=-]+|sk-[A-Za-z0-9._~+/=-]+|"
    r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b|"
    r"secret-[A-Za-z0-9._~+/=-]+)",
    re.IGNORECASE,
)


def _deletion_status_value(status: str) -> Literal["scheduled", "completed"]:
    if status == "completed":
        return "completed"
    return "scheduled"


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
    responses={status.HTTP_202_ACCEPTED: {"model": GuardianConsentPendingResponse}},
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
) -> SignupResponse | JSONResponse:
    if body.age_years < 14:
        session.add(
            AuditLog(
                user_id=None,
                actor="system",
                action="auth.signup.age_gate_rejected",
                resource_type="signup",
                resource_id=None,
                audit_metadata={"age_band": "under_14", "reason": "policy"},
            )
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="registration is unavailable for this age band",
        )

    if body.age_years < 18:
        if body.guardian_consent_token and body.guardian_consent_request_id:
            return await _complete_guardian_confirmed_signup(body, request, session)
        return await _create_or_refresh_guardian_consent(body, session)

    return await _create_verified_user_signup(
        body=body,
        request=request,
        session=session,
        age_band="adult",
        guardian_consent_request_id=None,
    )


async def _create_or_refresh_guardian_consent(
    body: SignupRequest,
    session: AsyncSession,
) -> JSONResponse:
    assert body.guardian_email is not None

    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=settings.guardian_consent_ttl_seconds)
    token = security.generate_guardian_consent_token()
    token_hash = security.hash_guardian_consent_token(token)
    email = str(body.email).lower()
    guardian_email = str(body.guardian_email).lower()
    lock_key = f"guardian-consent:{body.phone}:{email}:{guardian_email}"
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": lock_key},
    )

    existing = (
        await session.execute(
            select(GuardianConsentRequest)
            .where(
                GuardianConsentRequest.phone == body.phone,
                GuardianConsentRequest.email == email,
                GuardianConsentRequest.guardian_email == guardian_email,
                GuardianConsentRequest.confirmed_at.is_(None),
                GuardianConsentRequest.expires_at > now,
            )
            .order_by(GuardianConsentRequest.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if existing is None:
        consent = GuardianConsentRequest(
            phone=body.phone,
            email=email,
            age_years=body.age_years,
            guardian_email=guardian_email,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        session.add(consent)
        await session.flush()
    else:
        existing.age_years = body.age_years
        existing.token_hash = token_hash
        existing.expires_at = expires_at
        consent = existing
        await session.flush()

    response = GuardianConsentPendingResponse(
        request_id=consent.id,
        expires_in_seconds=settings.guardian_consent_ttl_seconds,
        guardian_email=guardian_email,
        dev_guardian_consent_token=(token if settings.guardian_consent_dev_mode_return else None),
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED, content=response.model_dump(mode="json")
    )


async def _complete_guardian_confirmed_signup(
    body: SignupRequest,
    request: Request,
    session: AsyncSession,
) -> SignupResponse:
    assert body.guardian_email is not None
    assert body.guardian_consent_request_id is not None
    assert body.guardian_consent_token is not None

    email = str(body.email).lower()
    guardian_email = str(body.guardian_email).lower()
    consent = (
        await session.execute(
            select(GuardianConsentRequest).where(
                GuardianConsentRequest.id == body.guardian_consent_request_id
            )
        )
    ).scalar_one_or_none()
    if consent is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="invalid guardian consent"
        )
    if consent.confirmed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="guardian consent already used",
        )
    now = datetime.now(UTC)
    if consent.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="guardian consent expired",
        )
    if (
        consent.phone != body.phone
        or consent.email != email
        or consent.age_years != body.age_years
        or consent.guardian_email != guardian_email
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="guardian consent does not match signup request",
        )
    if not security.verify_guardian_consent_token(
        body.guardian_consent_token,
        consent.token_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="invalid guardian consent"
        )

    response = await _create_verified_user_signup(
        body=body,
        request=request,
        session=session,
        age_band="minor_14_17",
        guardian_consent_request_id=consent.id,
    )
    consent.confirmed_at = now
    consent.user_id = uuid.UUID(str(response.user_id))
    await session.flush()
    return response


async def _create_verified_user_signup(
    *,
    body: SignupRequest,
    request: Request,
    session: AsyncSession,
    age_band: Literal["adult", "minor_14_17"],
    guardian_consent_request_id: uuid.UUID | None,
) -> SignupResponse:
    email = str(body.email).lower()
    # FR A4: .edu / .ac.cn 邮箱自动激活教育版
    edu_tier = email.endswith((".edu", ".ac.cn")) or ".edu." in email

    # In a real Story 1.x, we'd send OTPs here. Story 0.6 stub assumes verified.
    user = User(phone=body.phone, email=email, edu_tier=edu_tier, age_verified=True)
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
                "age_band": age_band,
                "age_verified": True,
                "guardian_consent_request_id": (
                    str(guardian_consent_request_id)
                    if guardian_consent_request_id is not None
                    else None
                ),
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


async def _require_active_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await account_deletion.get_active_user(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account deleted",
        )
    if user.merged_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account merged",
        )
    if user.is_frozen:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account frozen",
        )
    return user


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
) -> OTPRequestResponse | JSONResponse:
    user = await _lookup_user(session, body.phone, body.email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )
    if user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account deleted",
        )
    if user.is_frozen:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=frozen_appeals.build_frozen_auth_error(),
            media_type="application/problem+json",
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
) -> LoginResponse | JSONResponse:
    user = await _lookup_user(session, body.phone, body.email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )
    if user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account deleted",
        )
    if user.is_frozen:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=frozen_appeals.build_frozen_auth_error(),
            media_type="application/problem+json",
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
    user_id = uuid.UUID(payload["sub"])
    return user_id


async def _resolve_active_user_from_jwt(
    authorization: str | None,
    session: AsyncSession,
) -> uuid.UUID:
    user_id = await _resolve_user_from_jwt(authorization)
    await _require_active_user(session, user_id)
    return user_id


def _audit_log_cursor_secret() -> bytes:
    material = f"{settings.api_key_hmac_pepper_dev}:audit-log-cursor:v1"
    return hashlib.sha256(material.encode("utf-8")).digest()


def _audit_log_time_key(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_audit_log_time(value: str, field_name: str) -> datetime:
    raw = value.strip()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must be a timezone-aware ISO 8601 datetime",
        )
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must be a timezone-aware ISO 8601 datetime",
        ) from e
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must include a timezone offset",
        )
    return parsed.astimezone(UTC)


def _cursor_payload_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _encode_audit_log_cursor(
    *,
    user_id: uuid.UUID,
    created_at: datetime,
    row_id: uuid.UUID,
    from_dt: datetime,
    to_dt: datetime,
    limit: int,
) -> str:
    payload: dict[str, object] = {
        "v": _AUDIT_LOG_CURSOR_VERSION,
        "user_id": str(user_id),
        "created_at": _audit_log_time_key(created_at),
        "id": str(row_id),
        "from": _audit_log_time_key(from_dt),
        "to": _audit_log_time_key(to_dt),
        "limit": limit,
    }
    body = _cursor_payload_bytes(payload)
    signature = hmac.new(_audit_log_cursor_secret(), body, hashlib.sha256).digest()
    token = signature + body
    return base64.urlsafe_b64encode(token).decode("ascii").rstrip("=")


def _decode_audit_log_cursor(cursor: str) -> dict[str, object]:
    padding = "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode((cursor + padding).encode("ascii"))
    except (BinasciiError, UnicodeEncodeError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid audit log cursor",
        ) from e
    if len(raw) <= _AUDIT_LOG_CURSOR_SIGNATURE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid audit log cursor",
        )
    signature = raw[:_AUDIT_LOG_CURSOR_SIGNATURE_BYTES]
    body = raw[_AUDIT_LOG_CURSOR_SIGNATURE_BYTES:]
    expected = hmac.new(_audit_log_cursor_secret(), body, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid audit log cursor",
        )
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid audit log cursor",
        ) from e
    if not isinstance(payload, dict) or payload.get("v") != _AUDIT_LOG_CURSOR_VERSION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="unsupported audit log cursor",
        )
    return payload


def _cursor_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid audit log cursor",
        )
    return value


def _cursor_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid audit log cursor",
        )
    return value


def _resolve_audit_log_window_and_cursor(
    *,
    user_id: uuid.UUID,
    from_param: str | None,
    to_param: str | None,
    limit_param: int | None,
    cursor: str | None,
    now: datetime | None = None,
) -> tuple[datetime, datetime, int, tuple[datetime, uuid.UUID] | None]:
    cursor_anchor: tuple[datetime, uuid.UUID] | None = None
    cursor_payload = _decode_audit_log_cursor(cursor) if cursor else None

    if cursor_payload is not None:
        try:
            cursor_user_id = uuid.UUID(_cursor_str(cursor_payload, "user_id"))
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="invalid audit log cursor",
            ) from e
        if cursor_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="audit log cursor does not belong to the current user",
            )
        cursor_from = _parse_audit_log_time(_cursor_str(cursor_payload, "from"), "cursor.from")
        cursor_to = _parse_audit_log_time(_cursor_str(cursor_payload, "to"), "cursor.to")
        cursor_limit = _cursor_int(cursor_payload, "limit")
        from_dt = _parse_audit_log_time(from_param, "from") if from_param is not None else cursor_from
        to_dt = _parse_audit_log_time(to_param, "to") if to_param is not None else cursor_to
        limit = limit_param if limit_param is not None else cursor_limit
        if (
            _audit_log_time_key(from_dt) != _audit_log_time_key(cursor_from)
            or _audit_log_time_key(to_dt) != _audit_log_time_key(cursor_to)
            or limit != cursor_limit
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="cursor parameters must match the original audit log query",
            )
        cursor_created_at = _parse_audit_log_time(
            _cursor_str(cursor_payload, "created_at"), "cursor.created_at"
        )
        try:
            cursor_id = uuid.UUID(_cursor_str(cursor_payload, "id"))
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="invalid audit log cursor",
            ) from e
        cursor_anchor = (cursor_created_at, cursor_id)
    else:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        to_dt = _parse_audit_log_time(to_param, "to") if to_param is not None else current
        from_dt = (
            _parse_audit_log_time(from_param, "from")
            if from_param is not None
            else to_dt - timedelta(days=_AUDIT_LOG_DEFAULT_WINDOW_DAYS)
        )
        limit = limit_param if limit_param is not None else _AUDIT_LOG_DEFAULT_LIMIT

    if limit < 1 or limit > _AUDIT_LOG_MAX_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"limit must be between 1 and {_AUDIT_LOG_MAX_LIMIT}",
        )
    if from_dt > to_dt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="from must be earlier than or equal to to",
        )
    return from_dt, to_dt, limit, cursor_anchor


def _audit_to_jsonable(value: object) -> object:
    if isinstance(value, datetime):
        return _audit_log_time_key(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, IPv4Address | IPv6Address):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _audit_to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_audit_to_jsonable(v) for v in value]
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)


def _sanitize_audit_metadata(value: object) -> object:
    if isinstance(value, Mapping):
        sanitized: dict[str, object] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if key.lower() not in _AUDIT_SAFE_METADATA_KEYS and _AUDIT_SECRET_KEY_RE.search(key):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = _sanitize_audit_metadata(raw_value)
        return sanitized
    if isinstance(value, list | tuple):
        return [_sanitize_audit_metadata(v) for v in value]
    if isinstance(value, str):
        return _AUDIT_SECRET_VALUE_RE.sub("[REDACTED]", value)
    return _audit_to_jsonable(value)


def _audit_log_item(row: AuditLog) -> AuditLogItem:
    metadata = _sanitize_audit_metadata(row.audit_metadata or {})
    if not isinstance(metadata, dict):
        metadata = {}
    return AuditLogItem(
        id=row.id,
        actor=row.actor,
        action=row.action,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        metadata=metadata,
        ip_address=str(row.ip_address) if row.ip_address is not None else None,
        user_agent=row.user_agent,
        created_at=row.created_at,
    )


@me_router.get(
    "/audit-logs",
    response_model=UserAuditLogsResponse,
    summary="查询当前用户审计日志",
    description=(
        "FR O3: returns only the authenticated user's audit_logs rows with UTC time "
        "filtering, bounded cursor pagination, and metadata redaction."
    ),
)
async def list_my_audit_logs(
    request: Request,
    from_param: str | None = Query(default=None, alias="from"),
    to_param: str | None = Query(default=None, alias="to"),
    limit: int | None = Query(default=None, ge=1, le=_AUDIT_LOG_MAX_LIMIT),
    cursor: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> UserAuditLogsResponse:
    if "user_id" in request.query_params:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_id query parameter is not supported",
        )

    user_id = await _resolve_active_user_from_jwt(authorization, session)
    from_dt, to_dt, resolved_limit, cursor_anchor = _resolve_audit_log_window_and_cursor(
        user_id=user_id,
        from_param=from_param,
        to_param=to_param,
        limit_param=limit,
        cursor=cursor,
    )

    conditions = [
        AuditLog.user_id == user_id,
        AuditLog.created_at >= from_dt,
        AuditLog.created_at <= to_dt,
    ]
    if cursor_anchor is not None:
        cursor_created_at, cursor_id = cursor_anchor
        conditions.append(
            or_(
                AuditLog.created_at < cursor_created_at,
                and_(AuditLog.created_at == cursor_created_at, AuditLog.id < cursor_id),
            )
        )

    result = await session.execute(
        select(AuditLog)
        .where(*conditions)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(resolved_limit + 1)
    )
    rows = list(result.scalars().all())
    visible_rows = rows[:resolved_limit]
    next_cursor = None
    if len(rows) > resolved_limit and visible_rows:
        last = visible_rows[-1]
        next_cursor = _encode_audit_log_cursor(
            user_id=user_id,
            created_at=last.created_at,
            row_id=last.id,
            from_dt=from_dt,
            to_dt=to_dt,
            limit=resolved_limit,
        )

    return UserAuditLogsResponse.model_validate(
        {
            "items": [_audit_log_item(row) for row in visible_rows],
            "next_cursor": next_cursor,
            "limit": resolved_limit,
            "from": from_dt,
            "to": to_dt,
        }
    )


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
    user_id = await _resolve_active_user_from_jwt(authorization, session)

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
    user_id = await _resolve_active_user_from_jwt(authorization, session)

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
            last_used_ip=str(k.last_used_ip) if k.last_used_ip is not None else None,
            last_used_geo_bucket=k.last_used_geo_bucket,
            geo_risk_score=float(k.geo_risk_score),
            geo_anomaly_at=k.geo_anomaly_at,
            geo_anomaly=(
                APIKeyGeoAnomalyWarning(
                    previous_geo_bucket=k.geo_anomaly_metadata.get("previous_geo_bucket"),
                    current_geo_bucket=k.geo_anomaly_metadata.get("current_geo_bucket"),
                    previous_geo_label_zh=k.geo_anomaly_metadata.get("previous_geo_label_zh"),
                    current_geo_label_zh=k.geo_anomaly_metadata.get("current_geo_label_zh"),
                    previous_ip=k.geo_anomaly_metadata.get("previous_ip"),
                    current_ip=k.geo_anomaly_metadata.get("current_ip"),
                    geo_risk_score=float(k.geo_risk_score),
                    detected_at=k.geo_anomaly_at,
                    detector_version=k.geo_anomaly_metadata.get("detector_version"),
                )
                if k.geo_anomaly_at is not None and k.revoked_at is None
                else None
            ),
            revoked_at=k.revoked_at,
            created_at=k.created_at,
        )
        for k in keys
    ]


def _notification_preference_response_item(
    event_type: str,
    preference: NotificationPreference | None,
) -> NotificationPreferenceResponseItem:
    default_email, default_webhook, default_in_app = notification_event_defaults(event_type)
    email = preference.email_enabled if preference is not None else default_email
    webhook = preference.webhook_enabled if preference is not None else default_webhook
    in_app = preference.in_app_enabled if preference is not None else default_in_app
    webhook_url = preference.webhook_url if preference is not None else None
    return NotificationPreferenceResponseItem(
        event_type=event_type,  # type: ignore[arg-type]
        email=email,
        webhook=webhook,
        in_app=in_app,
        webhook_url=webhook_url,
        webhook_url_configured=bool(webhook and webhook_url),
        channels=notification_channels(email=email, webhook=webhook, in_app=in_app),
    )


async def _load_notification_preferences_response(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> NotificationPreferencesResponse:
    rows = (
        (
            await session.execute(
                select(NotificationPreference).where(NotificationPreference.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    by_event = {row.event_type: row for row in rows}
    return NotificationPreferencesResponse(
        items=[
            _notification_preference_response_item(event_type, by_event.get(event_type))
            for event_type in SUPPORTED_NOTIFICATION_EVENTS
        ]
    )


def _notification_outbox_payload(
    user_id: uuid.UUID,
    items: list[NotificationPreferenceItem],
) -> dict[str, object]:
    ordered_items = sorted(
        items,
        key=lambda item: SUPPORTED_NOTIFICATION_EVENTS.index(item.event_type),
    )
    return {
        "user_id": str(user_id),
        "preferences": [
            {
                "event_type": item.event_type,
                "channels": notification_channels(
                    email=item.email,
                    webhook=item.webhook,
                    in_app=item.in_app,
                ),
                "webhook_url_configured": bool(item.webhook and item.webhook_url),
            }
            for item in ordered_items
        ],
    }


@router.get(
    "/notification-preferences",
    response_model=NotificationPreferencesResponse,
    summary="查看当前用户通知偏好",
)
async def get_notification_preferences(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> NotificationPreferencesResponse:
    user_id = await _resolve_active_user_from_jwt(authorization, session)
    return await _load_notification_preferences_response(session, user_id)


@router.put(
    "/notification-preferences",
    response_model=NotificationPreferencesResponse,
    summary="全量更新当前用户通知偏好",
)
async def update_notification_preferences(
    body: NotificationPreferencesUpdateRequest,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> NotificationPreferencesResponse:
    user_id = await _resolve_active_user_from_jwt(authorization, session)
    ordered_items = sorted(
        body.items,
        key=lambda item: SUPPORTED_NOTIFICATION_EVENTS.index(item.event_type),
    )
    for item in ordered_items:
        stmt = (
            pg_insert(NotificationPreference)
            .values(
                user_id=user_id,
                event_type=item.event_type,
                email_enabled=item.email,
                webhook_enabled=item.webhook,
                in_app_enabled=item.in_app,
                webhook_url=item.webhook_url,
                updated_at=datetime.now(UTC),
            )
            .on_conflict_do_update(
                index_elements=["user_id", "event_type"],
                set_={
                    "email_enabled": item.email,
                    "webhook_enabled": item.webhook,
                    "in_app_enabled": item.in_app,
                    "webhook_url": item.webhook_url,
                    "updated_at": datetime.now(UTC),
                },
            )
        )
        await session.execute(stmt)

    payload = _notification_outbox_payload(user_id, ordered_items)
    session.add(
        AuditLog(
            user_id=user_id,
            actor="user",
            action="auth.notification_preferences.updated",
            resource_type="user",
            resource_id=user_id,
            audit_metadata=payload,
        )
    )
    session.add(
        OutboxEvent(
            aggregate_type="user",
            aggregate_id=user_id,
            event_type="auth.notification_preferences.updated",
            event_version=1,
            payload=payload,
            headers={},
            occurred_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return await _load_notification_preferences_response(session, user_id)


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
    user_id = await _resolve_active_user_from_jwt(authorization, session)

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
    await session.commit()


@router.get(
    "/account-deletion",
    response_model=AccountDeletionStatusResponse,
    summary="查看账户删除状态",
)
async def get_account_deletion_status(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> AccountDeletionStatusResponse:
    user_id = await _resolve_user_from_jwt(authorization)
    request = await account_deletion.get_deletion_request_status(session, user_id)
    if request is None:
        return AccountDeletionStatusResponse(status="none")
    return AccountDeletionStatusResponse(
        status=_deletion_status_value(request.status),
        user_id_snapshot=request.user_id_snapshot,
        requested_at=request.requested_at,
        hard_delete_at=request.hard_delete_at,
        completed_at=request.completed_at,
    )


@router.post(
    "/account-deletion",
    response_model=AccountDeletionStatusResponse,
    summary="请求账户删除",
    status_code=status.HTTP_200_OK,
)
async def request_account_deletion(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> AccountDeletionStatusResponse:
    user_id = await _resolve_user_from_jwt(authorization)
    try:
        request = await account_deletion.request_account_deletion(session, user_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found") from e
    await session.commit()
    return AccountDeletionStatusResponse(
        status=_deletion_status_value(request.status),
        user_id_snapshot=request.user_id_snapshot,
        requested_at=request.requested_at,
        hard_delete_at=request.hard_delete_at,
        completed_at=request.completed_at,
    )


@router.post(
    "/data-exports",
    response_model=DataExportStatusResponse,
    summary="请求 PIPL JSON/CSV 数据导出",
    status_code=status.HTTP_200_OK,
)
async def request_data_export(
    body: DataExportCreateRequest | None = Body(default=None),
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> DataExportStatusResponse:
    user_id = await _resolve_user_from_jwt(authorization)
    export_format = body.format if body is not None else data_export.JSON_FORMAT
    export = await data_export.request_data_export(
        session,
        user_id=user_id,
        export_format=export_format,
    )
    await session.commit()
    return DataExportStatusResponse.model_validate(data_export.status_response(export))


@router.get(
    "/data-exports/{export_id}",
    response_model=DataExportStatusResponse,
    summary="查看 PIPL JSON/CSV 数据导出状态",
)
async def get_data_export_status(
    export_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> DataExportStatusResponse:
    user_id = await _resolve_user_from_jwt(authorization)
    export = await data_export.get_export_request_for_user(
        session,
        export_id=export_id,
        user_id=user_id,
    )
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="data export not found")
    return DataExportStatusResponse.model_validate(data_export.status_response(export))


@router.get(
    "/data-exports/{export_id}/download",
    summary="下载已完成的 PIPL JSON/CSV 数据导出包",
)
async def download_data_export(
    export_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> Response:
    user_id = await _resolve_user_from_jwt(authorization)
    export = await data_export.get_export_request_for_user(
        session,
        export_id=export_id,
        user_id=user_id,
    )
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="data export not found")
    if export.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="data export is not completed",
        )
    if export.expires_at is not None and export.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="data export expired")
    if export.package_json is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="data export package unavailable",
        )
    if export.format == data_export.CSV_FORMAT:
        archive = data_export.csv_download_bytes(export.package_json)
        if archive is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="data export package unavailable",
            )
        return Response(
            content=archive,
            media_type=data_export.CSV_MEDIA_TYPE,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{data_export.CSV_ARCHIVE_FILENAME}"'
                )
            },
        )
    return JSONResponse(content=export.package_json)


@router.post(
    "/account-merge-proposals",
    response_model=AccountMergeProposalResponse,
    summary="提交冻结账户合并提案",
    status_code=status.HTTP_201_CREATED,
)
async def create_account_merge_proposal(
    body: AccountMergeProposalCreateRequest,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    user_id = await _resolve_user_from_jwt(authorization)
    proposal = await account_merge.create_merge_proposal(session, user_id, body)
    await session.commit()
    await session.refresh(proposal)
    return account_merge.proposal_to_response(proposal)


@router.get(
    "/account-merge-proposals",
    response_model=list[AccountMergeProposalResponse],
    summary="列出当前用户的账户合并提案",
)
async def list_account_merge_proposals(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    user_id = await _resolve_user_from_jwt(authorization)
    proposals = await account_merge.list_user_merge_proposals(session, user_id)
    return [account_merge.proposal_to_response(p) for p in proposals]


@router.post(
    "/account-merge-proposals/{proposal_id}/accept",
    response_model=AccountMergeProposalResponse,
    summary="接受已批准的账户合并提案",
)
async def accept_account_merge_proposal(
    proposal_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    user_id = await _resolve_user_from_jwt(authorization)
    proposal = await account_merge.accept_merge_proposal(session, user_id, proposal_id)
    await session.commit()
    await session.refresh(proposal)
    return account_merge.proposal_to_response(proposal)
