"""Story 1.4 — edu-tier auto-activation tests (FR A4).

Covers .edu / .ac.cn auto-activation + bucket="edu" seed + audit log.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from auth_service.config import settings
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def _phone() -> str:
    return f"+8613{uuid.uuid4().int % 10**10:010d}"


async def _balance_edu_bucket_for(engine: AsyncEngine, user_id: uuid.UUID) -> Decimal:
    """Direct DB sum of credit_transactions for (user_id, bucket='edu')."""
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        result = await s.execute(
            text(
                "SELECT COALESCE(SUM(amount), 0) FROM credit_transactions "
                "WHERE user_id = :uid AND bucket = 'edu'"
            ),
            {"uid": user_id},
        )
        return Decimal(str(result.scalar_one()))


async def _audit_log_metadata_for(engine: AsyncEngine, user_id: uuid.UUID) -> dict:  # type: ignore[type-arg]
    """Return the auth.signup audit_log metadata for the user."""
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        result = await s.execute(
            text("SELECT metadata FROM audit_logs WHERE user_id = :uid AND action = 'auth.signup'"),
            {"uid": user_id},
        )
        return result.scalar_one()


# ===== AC6 tests =====


async def test_edu_dotedu_email_creates_user_with_edu_tier_true_and_seed(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    """AC6 #1 — student@stanford.edu → edu_tier=true; edu bucket = 2000.00."""
    email = f"student-{uuid.uuid4().hex[:10]}@stanford.edu"
    r = await http_client.post(
        "/v1/auth/signup",
        json={"phone": _phone(), "email": email, "age_years": 18},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["edu_tier"] is True
    user_id = uuid.UUID(body["user_id"])

    edu_balance = await _balance_edu_bucket_for(engine, user_id)
    assert edu_balance == Decimal("2000.00"), f"got {edu_balance}"


async def test_edu_dotaccn_email_creates_user_with_edu_tier_true_and_seed(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    """AC6 #2 — prof@pku.ac.cn → edu_tier=true; edu bucket = 2000.00."""
    email = f"prof-{uuid.uuid4().hex[:10]}@pku.ac.cn"
    r = await http_client.post(
        "/v1/auth/signup",
        json={"phone": _phone(), "email": email, "age_years": 18},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["edu_tier"] is True
    user_id = uuid.UUID(body["user_id"])

    edu_balance = await _balance_edu_bucket_for(engine, user_id)
    assert edu_balance == Decimal("2000.00")


async def test_edu_subdomain_dotedu_also_activates(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    """AC6 #3 — student@cs.mit.edu (note: TLD is .edu, but with subdomain) → activates.

    The existing 0.6 logic uses `endswith((".edu", ".ac.cn"))` plus `".edu." in email`.
    `cs.mit.edu` ends with `.edu` → activates.
    """
    email = f"student-{uuid.uuid4().hex[:10]}@cs.mit.edu"
    r = await http_client.post(
        "/v1/auth/signup",
        json={"phone": _phone(), "email": email, "age_years": 18},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["edu_tier"] is True
    user_id = uuid.UUID(body["user_id"])

    edu_balance = await _balance_edu_bucket_for(engine, user_id)
    assert edu_balance == Decimal("2000.00")


async def test_regular_signup_no_edu_no_seed(http_client: AsyncClient, engine: AsyncEngine) -> None:
    """AC6 #4 — user@example.com → edu_tier=false; NO edu bucket row."""
    email = f"user-{uuid.uuid4().hex[:10]}@example.com"
    r = await http_client.post(
        "/v1/auth/signup",
        json={"phone": _phone(), "email": email, "age_years": 18},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["edu_tier"] is False
    user_id = uuid.UUID(body["user_id"])

    edu_balance = await _balance_edu_bucket_for(engine, user_id)
    assert edu_balance == Decimal("0"), f"non-edu user got edu seed: {edu_balance}"


async def test_edu_seed_amount_matches_config(
    http_client: AsyncClient,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC6 #5 — EDU_SIGNUP_SEED_AMOUNT env override flows through."""
    monkeypatch.setattr(settings, "edu_signup_seed_amount", "500.00")

    email = f"halfedu-{uuid.uuid4().hex[:10]}@stanford.edu"
    r = await http_client.post(
        "/v1/auth/signup",
        json={"phone": _phone(), "email": email, "age_years": 18},
    )
    assert r.status_code == 201, r.text
    user_id = uuid.UUID(r.json()["user_id"])

    edu_balance = await _balance_edu_bucket_for(engine, user_id)
    assert edu_balance == Decimal("500.00")


async def test_edu_signup_audit_log_includes_seed_amount(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    """AC6 #6 — audit_logs.metadata captures edu_signup_seed_amount on edu signup."""
    email = f"audit-{uuid.uuid4().hex[:10]}@stanford.edu"
    r = await http_client.post(
        "/v1/auth/signup",
        json={"phone": _phone(), "email": email, "age_years": 18},
    )
    user_id = uuid.UUID(r.json()["user_id"])

    metadata = await _audit_log_metadata_for(engine, user_id)
    assert metadata.get("edu_tier") is True
    assert metadata.get("edu_signup_seed_amount") == "2000.00"
