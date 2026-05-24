"""Story 1.9 — age gate and guardian confirmation tests."""

from __future__ import annotations

import uuid

from auth_service.models import GuardianConfirmation, User
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def _phone() -> str:
    return f"+8613{uuid.uuid4().int % 10**10:010d}"


def _email() -> str:
    return f"age-{uuid.uuid4().hex[:10]}@example.com"


async def _signup(
    http_client: AsyncClient,
    *,
    age: int,
    phone: str | None = None,
    email: str | None = None,
    guardian_email: str | None = None,
):
    payload = {"phone": phone or _phone(), "email": email or _email(), "age": age}
    if guardian_email is not None:
        payload["guardian_email"] = guardian_email
    return await http_client.post("/v1/auth/signup", json=payload)


async def _user_by_id(engine: AsyncEngine, user_id: uuid.UUID) -> User:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        return (await s.execute(select(User).where(User.id == user_id))).scalar_one()


async def _confirmation_by_user(engine: AsyncEngine, user_id: uuid.UUID) -> GuardianConfirmation:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        return (
            await s.execute(
                select(GuardianConfirmation).where(GuardianConfirmation.user_id == user_id)
            )
        ).scalar_one()


async def test_under_14_signup_rejected(http_client: AsyncClient) -> None:
    r = await _signup(http_client, age=13)
    assert r.status_code == 403, r.text
    body = r.json()
    assert body["title"] == "Age Gate Rejected"
    assert body["errors"][0]["field_path"] == "body.age"


async def test_14_requires_guardian_email(http_client: AsyncClient) -> None:
    r = await _signup(http_client, age=14)
    assert r.status_code == 422, r.text
    assert r.json()["title"] == "Guardian Email Required"


async def test_14_signup_creates_pending_guardian_confirmation(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    guardian_email = f"guardian-{uuid.uuid4().hex[:8]}@example.com"
    r = await _signup(http_client, age=14, guardian_email=guardian_email)
    assert r.status_code == 201, r.text
    body = r.json()
    user_id = uuid.UUID(body["user_id"])

    assert body["account_status"] == "pending_guardian_confirmation"
    assert body["age_verified"] is False
    assert body["jwt_access"] is None
    assert body["guardian_email"] == guardian_email
    assert body["guardian_confirmation_url"].startswith("/auth/guardian-confirmation?token=")

    user = await _user_by_id(engine, user_id)
    confirmation = await _confirmation_by_user(engine, user_id)
    assert user.age_verified is False
    assert confirmation.guardian_email == guardian_email
    assert confirmation.confirmed_at is None


async def test_18_signup_creates_pending_guardian_confirmation(http_client: AsyncClient) -> None:
    guardian_email = f"guardian-{uuid.uuid4().hex[:8]}@example.com"
    r = await _signup(http_client, age=18, guardian_email=guardian_email)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["account_status"] == "pending_guardian_confirmation"
    assert body["age_verified"] is False
    assert body["jwt_access"] is None


async def test_19_signup_returns_verified_tokens(http_client: AsyncClient) -> None:
    r = await _signup(http_client, age=19)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["account_status"] == "verified"
    assert body["age_verified"] is True
    assert body["jwt_access"]
    assert body["jwt_refresh"]


async def test_pending_user_cannot_request_otp(http_client: AsyncClient) -> None:
    phone = _phone()
    email = _email()
    guardian_email = f"guardian-{uuid.uuid4().hex[:8]}@example.com"
    signup = await _signup(
        http_client,
        age=14,
        phone=phone,
        email=email,
        guardian_email=guardian_email,
    )
    assert signup.status_code == 201

    otp = await http_client.post("/v1/auth/otp/request", json={"phone": phone, "email": email})
    assert otp.status_code == 403
    assert "age gate pending" in otp.json()["detail"]


async def test_pending_user_cannot_login_before_confirmation(http_client: AsyncClient) -> None:
    phone = _phone()
    email = _email()
    guardian_email = f"guardian-{uuid.uuid4().hex[:8]}@example.com"
    signup = await _signup(
        http_client,
        age=14,
        phone=phone,
        email=email,
        guardian_email=guardian_email,
    )
    assert signup.status_code == 201

    login = await http_client.post(
        "/v1/auth/login",
        json={
            "phone": phone,
            "email": email,
            "phone_otp": "000000",
            "email_otp": "000000",
        },
    )
    assert login.status_code == 403
    assert "age gate pending" in login.json()["detail"]


async def test_guardian_confirmation_flips_age_verified_and_is_idempotent(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    guardian_email = f"guardian-{uuid.uuid4().hex[:8]}@example.com"
    signup = await _signup(http_client, age=14, guardian_email=guardian_email)
    body = signup.json()
    user_id = uuid.UUID(body["user_id"])
    token = body["guardian_confirmation_url"].split("token=")[1]

    confirm = await http_client.post(
        "/v1/auth/guardian-confirmation/confirm",
        json={"token": token},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["confirmation_status"] == "confirmed"
    assert (await _user_by_id(engine, user_id)).age_verified is True

    repeat = await http_client.post(
        "/v1/auth/guardian-confirmation/confirm",
        json={"token": token},
    )
    assert repeat.status_code == 200, repeat.text
    assert repeat.json()["confirmation_status"] == "already_confirmed"


async def test_pending_signup_preserves_signup_risk_evaluation_path(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    for _ in range(3):
        async with maker() as s:
            prior_id = uuid.uuid4()
            await s.execute(
                text(
                    "INSERT INTO users (id, phone, email, age_verified) "
                    "VALUES (:id, :phone, :email, true)"
                ),
                {
                    "id": prior_id,
                    "phone": _phone(),
                    "email": _email(),
                },
            )
            await s.execute(
                text(
                    "INSERT INTO audit_logs (user_id, actor, action, resource_type, "
                    "resource_id, ip_address, metadata) "
                    "VALUES (:id, 'user', 'auth.signup', 'user', :id, "
                    "CAST('127.0.0.1' AS inet), CAST('{}' AS jsonb))"
                ),
                {"id": prior_id},
            )
            await s.commit()

    guardian_email = f"guardian-{uuid.uuid4().hex[:8]}@example.com"
    signup = await _signup(http_client, age=14, guardian_email=guardian_email)
    assert signup.status_code == 201, signup.text
    user_id = uuid.UUID(signup.json()["user_id"])

    async with maker() as s:
        risk_flag_count = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM risk_flags "
                    "WHERE user_id = :uid AND rule_code = 'ip_24_share'"
                ),
                {"uid": user_id},
            )
        ).scalar_one()
    assert risk_flag_count == 1
