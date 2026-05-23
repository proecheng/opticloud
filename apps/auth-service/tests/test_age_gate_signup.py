"""Story 1.9 — FR A10 age gate and guardian consent signup tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from auth_service.config import settings
from auth_service.models import GuardianConsentRequest, User
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def _phone() -> str:
    return f"+8613{uuid.uuid4().int % 10**10:010d}"


def _email(prefix: str = "age") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


async def _count_users_by_email(engine: AsyncEngine, email: str) -> int:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        return int(
            (
                await s.execute(
                    text("SELECT COUNT(*) FROM users WHERE lower(email) = lower(:email)"),
                    {"email": email},
                )
            ).scalar_one()
        )


async def test_adult_signup_sets_age_verified(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    email = _email("adult")
    r = await http_client.post(
        "/v1/auth/signup",
        json={"phone": _phone(), "email": email, "age_years": 18},
    )

    assert r.status_code == 201, r.text
    user_id = uuid.UUID(r.json()["user_id"])

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        user = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        audit_metadata = (
            await s.execute(
                text(
                    "SELECT metadata FROM audit_logs WHERE user_id = :uid AND action = 'auth.signup'"
                ),
                {"uid": user_id},
            )
        ).scalar_one()

    assert user.age_verified is True
    assert audit_metadata["age_band"] == "adult"
    assert audit_metadata["age_verified"] is True


async def test_under_14_signup_rejected_without_persisting_pii(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    phone = _phone()
    email = _email("child")
    r = await http_client.post(
        "/v1/auth/signup",
        json={"phone": phone, "email": email, "age_years": 13},
    )

    assert r.status_code == 403, r.text
    assert await _count_users_by_email(engine, email) == 0

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        consent_count = (
            await s.execute(
                text("SELECT COUNT(*) FROM guardian_consent_requests WHERE email = :email"),
                {"email": email.lower()},
            )
        ).scalar_one()
        leaked_audit = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM audit_logs "
                    "WHERE metadata::text LIKE :phone OR metadata::text LIKE :email"
                ),
                {"phone": f"%{phone}%", "email": f"%{email}%"},
            )
        ).scalar_one()

    assert consent_count == 0
    assert leaked_audit == 0


async def test_minor_signup_without_guardian_email_returns_validation_error(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    email = _email("minor-no-guardian")
    r = await http_client.post(
        "/v1/auth/signup",
        json={"phone": _phone(), "email": email, "age_years": 16},
    )

    assert r.status_code == 422, r.text
    assert await _count_users_by_email(engine, email) == 0


async def test_minor_signup_returns_pending_without_creating_user(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    email = _email("minor")
    guardian = _email("guardian").upper()
    r = await http_client.post(
        "/v1/auth/signup",
        json={
            "phone": _phone(),
            "email": email.upper(),
            "age_years": 16,
            "guardian_email": guardian,
        },
    )

    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "guardian_consent_required"
    assert body["guardian_email"] == guardian.lower()
    assert body["expires_in_seconds"] == settings.guardian_consent_ttl_seconds
    assert body["dev_guardian_consent_token"]
    assert await _count_users_by_email(engine, email) == 0


async def test_repeated_minor_signup_reuses_single_active_pending_request(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    phone = _phone()
    email = _email("minor-repeat")
    guardian = _email("guardian-repeat")

    first = await http_client.post(
        "/v1/auth/signup",
        json={
            "phone": phone,
            "email": email,
            "age_years": 16,
            "guardian_email": guardian,
        },
    )
    assert first.status_code == 202, first.text

    second = await http_client.post(
        "/v1/auth/signup",
        json={
            "phone": phone,
            "email": email.upper(),
            "age_years": 16,
            "guardian_email": guardian.upper(),
        },
    )
    assert second.status_code == 202, second.text
    assert second.json()["request_id"] == first.json()["request_id"]
    assert second.json()["dev_guardian_consent_token"] != first.json()["dev_guardian_consent_token"]

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        pending_count = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM guardian_consent_requests "
                    "WHERE phone = :phone AND email = :email "
                    "AND guardian_email = :guardian_email "
                    "AND confirmed_at IS NULL AND expires_at > NOW()"
                ),
                {
                    "phone": phone,
                    "email": email.lower(),
                    "guardian_email": guardian.lower(),
                },
            )
        ).scalar_one()

    assert pending_count == 1


async def test_valid_guardian_token_completes_minor_signup_once(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    phone = _phone()
    email = _email("minor-complete")
    guardian = _email("guardian-complete")
    pending = await http_client.post(
        "/v1/auth/signup",
        json={
            "phone": phone,
            "email": email,
            "age_years": 15,
            "guardian_email": guardian,
        },
    )
    assert pending.status_code == 202, pending.text
    pending_body = pending.json()

    completed = await http_client.post(
        "/v1/auth/signup",
        json={
            "phone": phone,
            "email": email.upper(),
            "age_years": 15,
            "guardian_email": guardian.upper(),
            "guardian_consent_request_id": pending_body["request_id"],
            "guardian_consent_token": pending_body["dev_guardian_consent_token"],
        },
    )

    assert completed.status_code == 201, completed.text
    body = completed.json()
    user_id = uuid.UUID(body["user_id"])

    replay = await http_client.post(
        "/v1/auth/signup",
        json={
            "phone": phone,
            "email": email,
            "age_years": 15,
            "guardian_email": guardian,
            "guardian_consent_request_id": pending_body["request_id"],
            "guardian_consent_token": pending_body["dev_guardian_consent_token"],
        },
    )

    assert replay.status_code == 409, replay.text

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        user = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        consent = (
            await s.execute(
                select(GuardianConsentRequest).where(
                    GuardianConsentRequest.id == uuid.UUID(pending_body["request_id"])
                )
            )
        ).scalar_one()
        audit_metadata = (
            await s.execute(
                text(
                    "SELECT metadata FROM audit_logs WHERE user_id = :uid AND action = 'auth.signup'"
                ),
                {"uid": user_id},
            )
        ).scalar_one()

    assert user.age_verified is True
    assert consent.confirmed_at is not None
    assert consent.user_id == user_id
    assert audit_metadata["age_band"] == "minor_14_17"
    assert audit_metadata["guardian_consent_request_id"] == pending_body["request_id"]
    assert "guardian_email" not in audit_metadata


async def test_guardian_token_mismatch_and_expiry_do_not_create_user(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    phone = _phone()
    email = _email("minor-expired")
    guardian = _email("guardian-expired")
    pending = await http_client.post(
        "/v1/auth/signup",
        json={
            "phone": phone,
            "email": email,
            "age_years": 17,
            "guardian_email": guardian,
        },
    )
    assert pending.status_code == 202, pending.text
    pending_body = pending.json()

    wrong = await http_client.post(
        "/v1/auth/signup",
        json={
            "phone": phone,
            "email": email,
            "age_years": 17,
            "guardian_email": guardian,
            "guardian_consent_request_id": pending_body["request_id"],
            "guardian_consent_token": "wrong-token-000000",
        },
    )
    assert wrong.status_code == 403, wrong.text

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text("UPDATE guardian_consent_requests SET expires_at = :past WHERE id = :request_id"),
            {
                "past": datetime.now(UTC) - timedelta(seconds=1),
                "request_id": pending_body["request_id"],
            },
        )
        await s.commit()

    expired = await http_client.post(
        "/v1/auth/signup",
        json={
            "phone": phone,
            "email": email,
            "age_years": 17,
            "guardian_email": guardian,
            "guardian_consent_request_id": pending_body["request_id"],
            "guardian_consent_token": pending_body["dev_guardian_consent_token"],
        },
    )
    assert expired.status_code == 403, expired.text
    assert await _count_users_by_email(engine, email) == 0
