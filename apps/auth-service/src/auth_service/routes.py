"""Auth endpoints — signup / login / guardian confirmation / api_keys CRUD / health."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import and_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service import account_deletion, appeals, risk, security
from auth_service.config import settings
from auth_service.db import get_session
from auth_service.models import APIKey, AuditLog, GuardianConfirmation, RiskAppeal, User, UserOTP
from auth_service.schemas import (
    AccountDeletionStatusResponse,
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyListItem,
    APIKeyRiskGeo,
    APIKeyRiskWarning,
    AppealDecision,
    AppealReviewMode,
    AppealStatus,
    GuardianConfirmationRequest,
    GuardianConfirmationResponse,
    LoginRequest,
    LoginResponse,
    OTPRequestBody,
    OTPRequestResponse,
    RiskAppealMergeAcceptRequest,
    RiskAppealMergeAcceptResponse,
    RiskAppealStatusResponse,
    RiskAppealSubmitRequest,
    RiskAppealSubmitResponse,
    RiskEvidenceSummary,
    SignupRequest,
    SignupResponse,
)

_log = structlog.get_logger("auth_service.routes")

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _deletion_status_value(status: str) -> Literal["scheduled", "completed"]:
    return "completed" if status == "completed" else "scheduled"


def _error_detail(
    *,
    field_path: str,
    value: object,
    constraint: str,
    remediation_hint_key: str,
) -> dict[str, object]:
    return {
        "field_path": field_path,
        "value": value,
        "constraint": constraint,
        "remediation_hint_key": remediation_hint_key,
    }


def _problem_response(
    *,
    status_code: int,
    title: str,
    detail: str,
    errors: list[dict[str, object]] | None = None,
    next_action_url: str | None = None,
    type_uri: str = "about:blank",
) -> JSONResponse:
    body: dict[str, object] = {
        "type": type_uri,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if errors:
        body["errors"] = errors
    if next_action_url:
        body["next_action_url"] = next_action_url
    return JSONResponse(
        status_code=status_code, content=body, media_type="application/problem+json"
    )


def _signup_age_error(age: int) -> JSONResponse:
    return _problem_response(
        status_code=status.HTTP_403_FORBIDDEN,
        title="Age Gate Rejected",
        detail="14 岁以下用户不可注册。",
        errors=[
            _error_detail(
                field_path="body.age",
                value=age,
                constraint="age must be >= 14",
                remediation_hint_key="errors.403.age_gate_under_14",
            )
        ],
        next_action_url="/auth/signup",
        type_uri="https://api.opticloud.cn/errors/age-gate-rejected",
    )


def _guardian_missing_error() -> JSONResponse:
    return _problem_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        title="Guardian Email Required",
        detail="14-18 岁用户需要填写监护人邮箱。",
        errors=[
            _error_detail(
                field_path="body.guardian_email",
                value=None,
                constraint="guardian_email is required for ages 14-18",
                remediation_hint_key="errors.422.guardian_email_required",
            )
        ],
        next_action_url="/auth/signup",
        type_uri="https://api.opticloud.cn/errors/guardian-email-required",
    )


def _pending_signup_response(
    *,
    user: User,
    edu_tier: bool,
    guardian_email: str,
    guardian_confirmation_url: str,
) -> SignupResponse:
    return SignupResponse(
        account_status="pending_guardian_confirmation",
        user_id=user.id,
        jwt_access=None,
        jwt_refresh=None,
        edu_tier=edu_tier,
        age_verified=False,
        guardian_email=guardian_email,
        guardian_confirmation_url=guardian_confirmation_url,
    )


def _verified_signup_response(*, user: User, edu_tier: bool) -> SignupResponse:
    return SignupResponse(
        account_status="verified",
        user_id=user.id,
        jwt_access=security.create_access_token(user.id),
        jwt_refresh=security.create_refresh_token(user.id),
        edu_tier=edu_tier,
        age_verified=True,
    )


def _age_gate_pending_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="age gate pending: finish guardian confirmation first",
    )


def _frozen_account_error() -> JSONResponse:
    return _problem_response(
        status_code=status.HTTP_403_FORBIDDEN,
        title="Account Frozen",
        detail="account frozen",
        next_action_url="/auth/appeal",
        type_uri="https://api.opticloud.cn/errors/account-frozen",
    )


async def _apply_signup_risk(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    signup_ip: str | None,
) -> None:
    triggered = await risk.evaluate_signup(session, user_id, signup_ip)
    if triggered:
        new_flags = [(code, "auto", {"signup_ip": signup_ip}) for code in triggered]
        await risk.apply_flags_and_maybe_freeze(session, user_id, new_flags)


# ===== Story 0.7: Health & Readiness =====

health_router = APIRouter(tags=["health"])


@health_router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@health_router.get("/readyz")
async def readyz(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    try:
        await session.execute(select(1))
        deps = {"db": "ok"}
    except Exception as e:
        return {"status": "not-ready", "deps": {"db": f"error: {type(e).__name__}"}}
    return {"status": "ready", "deps": deps}


# ===== FR A1: signup =====


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="注册新用户（手机+邮箱双因素）",
)
async def signup(
    body: SignupRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> SignupResponse | JSONResponse:
    if body.age < 14:
        return _signup_age_error(body.age)
    if 14 <= body.age <= 18 and body.guardian_email is None:
        return _guardian_missing_error()

    edu_tier = body.email.endswith((".edu", ".ac.cn")) or ".edu." in body.email
    user = User(phone=body.phone, email=body.email, edu_tier=edu_tier)
    session.add(user)

    try:
        await session.flush()
    except IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="phone or email already registered"
        ) from e

    edu_seed_amount: str | None = None
    if edu_tier:
        edu_seed_amount = settings.edu_signup_seed_amount
        await session.execute(
            text(
                "INSERT INTO credit_transactions "
                "(user_id, saga_id, amount, kind, bucket, currency, metadata, created_at) "
                "VALUES (:uid, NULL, :amt, 'topup', 'edu', 'CNY', CAST(:meta AS jsonb), NOW())"
            ),
            {"uid": user.id, "amt": edu_seed_amount, "meta": '{"source": "edu_tier_signup"}'},
        )

    signup_ip = request.client.host if request.client else None

    if 14 <= body.age <= 18:
        guardian_email = str(body.guardian_email)
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        confirmation = GuardianConfirmation(
            user_id=user.id,
            guardian_email=guardian_email,
            token_hash=token_hash,
            token_expires_at=datetime.now(UTC) + timedelta(days=7),
            confirmed_at=None,
        )
        session.add(confirmation)
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
                    "age": body.age,
                    "account_status": "pending_guardian_confirmation",
                },
            )
        )
        session.add(
            AuditLog(
                user_id=user.id,
                actor="user",
                action="auth.guardian_confirmation.requested",
                resource_type="user",
                resource_id=user.id,
                audit_metadata={
                    "guardian_email": guardian_email,
                    "token_expires_at": confirmation.token_expires_at.isoformat(),
                },
            )
        )
        await session.flush()
        await _apply_signup_risk(session, user_id=user.id, signup_ip=signup_ip)
        await session.commit()
        return _pending_signup_response(
            user=user,
            edu_tier=edu_tier,
            guardian_email=guardian_email,
            guardian_confirmation_url=f"/auth/guardian-confirmation?token={token}",
        )

    user.age_verified = True
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
                "age": body.age,
                "account_status": "verified",
            },
        )
    )
    await session.flush()
    await _apply_signup_risk(session, user_id=user.id, signup_ip=signup_ip)

    await session.commit()
    return _verified_signup_response(user=user, edu_tier=edu_tier)


# ===== Story 1.2: OTP login =====


async def _lookup_user(session: AsyncSession, phone: str, email: str) -> User | None:
    stmt = select(User).where(and_(User.phone == phone, User.email == email))
    return (await session.execute(stmt)).scalar_one_or_none()


def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def _invalidate_unused_otps(session: AsyncSession, user_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    await session.execute(
        update(UserOTP)
        .where(and_(UserOTP.user_id == user_id, UserOTP.used_at.is_(None)))
        .values(used_at=now)
    )


@router.post("/otp/request", response_model=OTPRequestResponse, summary="请求登录 OTP 双因素验证码")
async def request_otp(
    body: OTPRequestBody,
    session: AsyncSession = Depends(get_session),
) -> OTPRequestResponse | JSONResponse:
    user = await _lookup_user(session, body.phone, body.email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    if user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account deleted")
    if not user.age_verified:
        raise _age_gate_pending_error()
    if user.is_frozen:
        return _frozen_account_error()

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
    return OTPRequestResponse(
        expires_in_seconds=settings.otp_ttl_seconds,
        factors=["phone", "email"],
        dev_phone_otp=phone_otp if settings.otp_dev_mode_return else None,
        dev_email_otp=email_otp if settings.otp_dev_mode_return else None,
    )


async def _verify_otp(
    session: AsyncSession, user_id: uuid.UUID, factor: str, provided_code: str
) -> bool:
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
    return bool(row and secrets.compare_digest(row.code, provided_code))


@router.post("/login", response_model=LoginResponse, summary="OTP 双因素登录")
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> LoginResponse | JSONResponse:
    user = await _lookup_user(session, body.phone, body.email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    if user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account deleted")
    if not user.age_verified:
        raise _age_gate_pending_error()
    if user.is_frozen:
        return _frozen_account_error()

    phone_ok = await _verify_otp(session, user.id, "phone", body.phone_otp)
    email_ok = await _verify_otp(session, user.id, "email", body.email_otp)
    if not (phone_ok and email_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired OTP"
        )

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
    return LoginResponse(
        account_status="verified",
        user_id=user.id,
        jwt_access=security.create_access_token(user.id),
        jwt_refresh=security.create_refresh_token(user.id),
        edu_tier=user.edu_tier,
        age_verified=True,
    )


@router.post(
    "/guardian-confirmation/confirm",
    response_model=GuardianConfirmationResponse,
    summary="Verify guardian confirmation token",
)
async def confirm_guardian(
    body: GuardianConfirmationRequest,
    session: AsyncSession = Depends(get_session),
) -> GuardianConfirmationResponse:
    token_hash = hashlib.sha256(body.token.encode("utf-8")).hexdigest()
    confirmation = (
        await session.execute(
            select(GuardianConfirmation).where(GuardianConfirmation.token_hash == token_hash)
        )
    ).scalar_one_or_none()
    if confirmation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="guardian confirmation token not found"
        )
    if confirmation.confirmed_at is not None:
        user = await session.get(User, confirmation.user_id)
        if user is not None:
            user.age_verified = True
        await session.commit()
        return GuardianConfirmationResponse(
            confirmation_status="already_confirmed",
            user_id=confirmation.user_id,
            guardian_email=confirmation.guardian_email,
            age_verified=True,
            confirmed_at=confirmation.confirmed_at,
        )

    now = datetime.now(UTC)
    if confirmation.token_expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="guardian confirmation token expired"
        )

    user = await session.get(User, confirmation.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user not found for guardian confirmation"
        )

    user.age_verified = True
    confirmation.confirmed_at = now
    confirmation.updated_at = now
    session.add(
        AuditLog(
            user_id=user.id,
            actor="user",
            action="auth.guardian_confirmation.confirmed",
            resource_type="user",
            resource_id=user.id,
            audit_metadata={"guardian_email": confirmation.guardian_email},
        )
    )
    await session.commit()
    return GuardianConfirmationResponse(
        confirmation_status="confirmed",
        user_id=user.id,
        guardian_email=confirmation.guardian_email,
        age_verified=True,
        confirmed_at=now,
    )


# ===== Story 1.12: J7 risk freeze appeals =====


def _appeal_forbidden_response(detail: str) -> JSONResponse:
    return _problem_response(
        status_code=status.HTTP_403_FORBIDDEN,
        title="Risk Appeal Not Available",
        detail=detail,
        next_action_url="/auth/login",
        type_uri="https://api.opticloud.cn/errors/risk-appeal-not-available",
    )


def _appeal_status_response(
    *,
    appeal: RiskAppeal,
    evidence_summary: list[RiskEvidenceSummary],
) -> RiskAppealStatusResponse:
    return RiskAppealStatusResponse(
        appeal_id=appeal.id,
        status=cast(AppealStatus, appeal.status),
        review_mode=cast(AppealReviewMode, appeal.review_mode),
        submitted_at=appeal.created_at,
        sla_due_at=appeals.sla_due_at(appeal),
        decided_at=appeal.decided_at,
        decision=cast(AppealDecision | None, appeal.decision),
        decision_reason=appeal.decision_reason,
        evidence_summary=evidence_summary,
        merge_offer=appeals.parse_merge_offer(appeal.merge_offer),
        next_action_url="/auth/login" if appeal.status in {"approved", "merge_accepted"} else None,
    )


@router.post(
    "/risk-appeals",
    response_model=RiskAppealSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a risk freeze appeal (J7)",
)
async def submit_risk_appeal(
    body: RiskAppealSubmitRequest,
    session: AsyncSession = Depends(get_session),
) -> RiskAppealSubmitResponse | JSONResponse:
    user = await _lookup_user(session, body.phone, str(body.email))
    if user is None:
        return _problem_response(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Risk Appeal Account Not Found",
            detail="No matching frozen account was found for the submitted phone and email.",
            next_action_url="/auth/signup",
            type_uri="https://api.opticloud.cn/errors/risk-appeal-account-not-found",
        )
    if user.deleted_at is not None:
        return _appeal_forbidden_response("account deleted")
    if not user.is_frozen:
        return _appeal_forbidden_response("account is not frozen")

    appeal, token = await appeals.create_appeal(
        session,
        user=user,
        reason=body.reason,
        evidence=body.evidence,
        team_size=body.team_size,
    )
    await session.commit()
    await session.refresh(appeal)
    return RiskAppealSubmitResponse(
        appeal_id=appeal.id,
        status=cast(AppealStatus, appeal.status),
        review_mode=cast(AppealReviewMode, appeal.review_mode),
        submitted_at=appeal.created_at,
        sla_due_at=appeals.sla_due_at(appeal),
        tracking_url=appeals.tracking_url(token),
        merge_offer=appeals.parse_merge_offer(appeal.merge_offer),
    )


@router.get(
    "/risk-appeals/status",
    response_model=RiskAppealStatusResponse,
    summary="Track risk appeal status by secure token",
)
async def get_risk_appeal_status(
    token: str,
    session: AsyncSession = Depends(get_session),
) -> RiskAppealStatusResponse:
    appeal = await appeals.get_appeal_by_token(session, token)
    if appeal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="appeal not found")
    summary = await appeals.evidence_summary(session, appeal.user_id)
    return _appeal_status_response(appeal=appeal, evidence_summary=summary)


@router.post(
    "/risk-appeals/{appeal_id}/merge-offer/accept",
    response_model=RiskAppealMergeAcceptResponse,
    summary="Accept a minimal merge offer and resume access",
)
async def accept_risk_appeal_merge_offer(
    appeal_id: uuid.UUID,
    body: RiskAppealMergeAcceptRequest,
    session: AsyncSession = Depends(get_session),
) -> RiskAppealMergeAcceptResponse:
    appeal = await appeals.get_appeal_by_token(session, body.token)
    if appeal is None or appeal.id != appeal_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="appeal not found")
    if appeal.status not in {"merge_offered", "merge_accepted"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="appeal does not have an active merge offer",
        )
    await appeals.accept_merge_offer(session, appeal)
    await session.commit()
    return RiskAppealMergeAcceptResponse(
        appeal_id=appeal.id,
        status="merge_accepted",
        decision="merge_accepted",
        is_frozen=False,
        next_action_url="/auth/login",
    )


# ===== FR A2: api_keys CRUD =====


async def _resolve_user_from_jwt(authorization: str | None) -> uuid.UUID:
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
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"invalid token: {type(e).__name__}"
        ) from e

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not an access token")
    return uuid.UUID(payload["sub"])


async def _resolve_active_user_from_jwt(
    authorization: str | None,
    session: AsyncSession,
) -> uuid.UUID:
    user_id = await _resolve_user_from_jwt(authorization)
    user = await account_deletion.get_active_user(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account deleted")
    if not user.age_verified:
        raise _age_gate_pending_error()
    return user_id


@router.post(
    "/api_keys",
    response_model=APIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建新 API Key",
)
async def create_api_key(
    body: APIKeyCreateRequest,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> APIKeyCreateResponse:
    user_id = await _resolve_active_user_from_jwt(authorization, session)
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


@router.get("/api_keys", response_model=list[APIKeyListItem], summary="列出 own API Keys")
async def list_api_keys(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[APIKeyListItem]:
    user_id = await _resolve_active_user_from_jwt(authorization, session)
    result = await session.execute(
        select(APIKey).where(APIKey.user_id == user_id).order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()
    risk_warnings = await _latest_geo_risk_warnings(session, user_id)
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
            risk_warning=risk_warnings.get(k.id),
        )
        for k in keys
    ]


def _risk_geo_from_metadata(value: object) -> APIKeyRiskGeo | None:
    if not isinstance(value, dict):
        return None
    code = value.get("code")
    label_zh = value.get("label_zh")
    if not isinstance(code, str) or not isinstance(label_zh, str):
        return None
    return APIKeyRiskGeo(code=code, label_zh=label_zh)


def _risk_warning_from_row(
    *,
    metadata: object,
    created_at: datetime,
) -> tuple[uuid.UUID, APIKeyRiskWarning] | None:
    if not isinstance(metadata, dict):
        return None
    api_key_id = metadata.get("api_key_id")
    previous_ip = metadata.get("previous_ip")
    current_ip = metadata.get("current_ip")
    reason = metadata.get("reason")
    risk_score = metadata.get("score")
    previous_geo = _risk_geo_from_metadata(metadata.get("previous_geo"))
    current_geo = _risk_geo_from_metadata(metadata.get("current_geo"))
    if (
        not isinstance(api_key_id, str)
        or not isinstance(previous_ip, str)
        or not isinstance(current_ip, str)
        or not isinstance(reason, str)
        or previous_geo is None
        or current_geo is None
    ):
        return None
    if not isinstance(risk_score, int | float | str):
        return None
    try:
        parsed_risk_score = float(risk_score)
    except (TypeError, ValueError):
        return None
    try:
        parsed_key_id = uuid.UUID(api_key_id)
    except ValueError:
        return None
    return parsed_key_id, APIKeyRiskWarning(
        risk_score=parsed_risk_score,
        detected_at=created_at,
        previous_geo=previous_geo,
        current_geo=current_geo,
        previous_ip=previous_ip,
        current_ip=current_ip,
        reason=reason,
    )


async def _latest_geo_risk_warnings(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> dict[uuid.UUID, APIKeyRiskWarning]:
    rows = (
        await session.execute(
            text(
                "SELECT rf.metadata AS risk_metadata, rf.created_at "
                "FROM risk_flags rf "
                "WHERE rf.user_id = :uid "
                "AND rf.rule_code = 'geo_anomaly' "
                "ORDER BY rf.created_at DESC"
            ),
            {"uid": user_id},
        )
    ).all()
    warnings: dict[uuid.UUID, APIKeyRiskWarning] = {}
    for row in rows:
        parsed = _risk_warning_from_row(
            metadata=row.risk_metadata,
            created_at=row.created_at,
        )
        if parsed is None:
            continue
        key_id, warning = parsed
        warnings.setdefault(key_id, warning)
    return warnings


@router.delete(
    "/api_keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT, summary="吊销 API Key (FR A2)"
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
    "/account-deletion", response_model=AccountDeletionStatusResponse, summary="查看账户删除状态"
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
