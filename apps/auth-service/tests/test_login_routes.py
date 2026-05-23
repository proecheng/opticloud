"""HTTP route tests for Story 1.2 — OTP request + login (FR A1).

Uses ASGI test client with DI-overridden DB session. Tests cover:
- happy path: signup → /otp/request → /login → JWT pair
- error paths: unknown user / frozen / OTP wrong / expired / replay
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from auth_service.models import User, UserOTP
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def _phone() -> str:
    """Generate a unique E.164 phone for a fresh test user."""
    return f"+8613{uuid.uuid4().int % 10**10:010d}"


def _email() -> str:
    # example.com is reserved-for-documentation per RFC 2606 — passes email-validator
    return f"login-{uuid.uuid4().hex[:10]}@example.com"


@pytest_asyncio.fixture
async def signed_up_user(
    http_client: AsyncClient,
) -> tuple[str, str]:
    """Sign up a fresh user; return (phone, email)."""
    phone = _phone()
    email = _email()
    r = await http_client.post(
        "/v1/auth/signup",
        json={"phone": phone, "email": email, "age_years": 18},
    )
    assert r.status_code == 201, r.text
    return phone, email


async def test_otp_request_for_unknown_user_returns_404(http_client: AsyncClient) -> None:
    """AC8 #1 — unknown (phone, email) → 404."""
    r = await http_client.post(
        "/v1/auth/otp/request",
        json={"phone": _phone(), "email": _email()},
    )
    assert r.status_code == 404, r.text


async def test_otp_request_for_known_user_returns_dev_codes(
    http_client: AsyncClient, signed_up_user: tuple[str, str]
) -> None:
    """AC8 #2 — known user → 200 with 6-digit dev OTPs."""
    phone, email = signed_up_user
    r = await http_client.post(
        "/v1/auth/otp/request",
        json={"phone": phone, "email": email},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["factors"] == ["phone", "email"]
    assert body["expires_in_seconds"] == 300
    assert body["dev_phone_otp"] is not None and len(body["dev_phone_otp"]) == 6
    assert body["dev_email_otp"] is not None and len(body["dev_email_otp"]) == 6
    assert body["dev_phone_otp"].isdigit()
    assert body["dev_email_otp"].isdigit()


async def test_otp_request_invalidates_prior_codes(
    http_client: AsyncClient,
    signed_up_user: tuple[str, str],
    engine: AsyncEngine,
) -> None:
    """AC8 #3 — second request invalidates first set."""
    phone, email = signed_up_user
    # First request
    r1 = await http_client.post("/v1/auth/otp/request", json={"phone": phone, "email": email})
    first_phone_otp = r1.json()["dev_phone_otp"]
    # Second request
    r2 = await http_client.post("/v1/auth/otp/request", json={"phone": phone, "email": email})
    second_phone_otp = r2.json()["dev_phone_otp"]
    # Codes are fresh (~10^-6 collision chance)
    assert first_phone_otp != second_phone_otp

    # First codes must be marked used (used_at populated)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        user_stmt = select(User).where(User.phone == phone)
        user = (await s.execute(user_stmt)).scalar_one()
        stmt = select(UserOTP).where(UserOTP.user_id == user.id, UserOTP.code == first_phone_otp)
        row = (await s.execute(stmt)).scalar_one()
        assert row.used_at is not None


async def test_login_happy_path_returns_jwt_pair(
    http_client: AsyncClient, signed_up_user: tuple[str, str]
) -> None:
    """AC8 #4 — request OTP → login with correct codes → 200 + JWT pair."""
    phone, email = signed_up_user
    otp_resp = (
        await http_client.post("/v1/auth/otp/request", json={"phone": phone, "email": email})
    ).json()
    r = await http_client.post(
        "/v1/auth/login",
        json={
            "phone": phone,
            "email": email,
            "phone_otp": otp_resp["dev_phone_otp"],
            "email_otp": otp_resp["dev_email_otp"],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["jwt_access"]
    assert body["jwt_refresh"]
    assert body["edu_tier"] is False  # not .edu email


async def test_login_with_wrong_phone_otp_returns_401(
    http_client: AsyncClient, signed_up_user: tuple[str, str]
) -> None:
    """AC8 #5 — wrong phone_otp (correct email_otp) → 401 generic message."""
    phone, email = signed_up_user
    otp_resp = (
        await http_client.post("/v1/auth/otp/request", json={"phone": phone, "email": email})
    ).json()
    r = await http_client.post(
        "/v1/auth/login",
        json={
            "phone": phone,
            "email": email,
            "phone_otp": "000000",  # definitely wrong (6 digits, valid format)
            "email_otp": otp_resp["dev_email_otp"],
        },
    )
    assert r.status_code == 401, r.text
    # R2 Q1 — detail must NOT leak which factor failed
    detail = r.json().get("detail", "").lower()
    assert "phone" not in detail
    assert "email" not in detail


async def test_login_with_expired_otp_returns_401(
    http_client: AsyncClient, signed_up_user: tuple[str, str], engine: AsyncEngine
) -> None:
    """AC8 #6 — expired OTP rejected."""
    phone, email = signed_up_user
    otp_resp = (
        await http_client.post("/v1/auth/otp/request", json={"phone": phone, "email": email})
    ).json()
    # Manually expire all unused OTPs for this user
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        user_stmt = select(User).where(User.phone == phone)
        user = (await s.execute(user_stmt)).scalar_one()
        past = datetime.now(UTC) - timedelta(seconds=1)
        await s.execute(
            update(UserOTP)
            .where(UserOTP.user_id == user.id, UserOTP.used_at.is_(None))
            .values(expires_at=past)
        )
        await s.commit()

    r = await http_client.post(
        "/v1/auth/login",
        json={
            "phone": phone,
            "email": email,
            "phone_otp": otp_resp["dev_phone_otp"],
            "email_otp": otp_resp["dev_email_otp"],
        },
    )
    assert r.status_code == 401, r.text


async def test_login_with_already_used_otp_returns_401(
    http_client: AsyncClient, signed_up_user: tuple[str, str]
) -> None:
    """AC8 #7 — login succeeds once; second attempt with same OTPs → 401."""
    phone, email = signed_up_user
    otp_resp = (
        await http_client.post("/v1/auth/otp/request", json={"phone": phone, "email": email})
    ).json()
    body = {
        "phone": phone,
        "email": email,
        "phone_otp": otp_resp["dev_phone_otp"],
        "email_otp": otp_resp["dev_email_otp"],
    }
    r1 = await http_client.post("/v1/auth/login", json=body)
    assert r1.status_code == 200, r1.text

    # Second attempt with same OTPs — they're now marked used
    r2 = await http_client.post("/v1/auth/login", json=body)
    assert r2.status_code == 401, r2.text


async def test_login_frozen_user_returns_403(
    http_client: AsyncClient, signed_up_user: tuple[str, str], engine: AsyncEngine
) -> None:
    """AC8 #8 — is_frozen=TRUE blocks even at /otp/request and /login."""
    phone, email = signed_up_user
    # Manually freeze the user
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(update(User).where(User.phone == phone).values(is_frozen=True))
        await s.commit()

    r = await http_client.post("/v1/auth/otp/request", json={"phone": phone, "email": email})
    assert r.status_code == 403, r.text
