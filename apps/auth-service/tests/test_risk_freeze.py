"""Story 1.5 — FR A5 risk-control auto-freeze tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from auth_service.config import settings
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def _phone() -> str:
    return f"+8613{uuid.uuid4().int % 10**10:010d}"


def _email() -> str:
    return f"u-{uuid.uuid4().hex[:10]}@example.com"


@pytest_asyncio.fixture
async def admin_secret() -> AsyncIterator[str]:
    """Set ADMIN_SECRET for the duration of one test (otherwise endpoints 403)."""
    secret = "test-admin-secret-not-for-prod"  # noqa: S105 (test fixture; not a real credential)
    original = settings.admin_secret
    settings.admin_secret = secret
    yield secret
    settings.admin_secret = original


async def _seed_prior_signup(
    engine: AsyncEngine, user_id: uuid.UUID, phone: str, email: str, ip: str
) -> None:
    """Insert a user + an auth.signup audit_log row with the given IP. Bypasses /signup."""
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text("INSERT INTO users (id, phone, email) VALUES (:id, :p, :e)"),
            {"id": user_id, "p": phone, "e": email},
        )
        await s.execute(
            text(
                "INSERT INTO audit_logs (user_id, actor, action, resource_type, "
                "resource_id, ip_address, metadata) "
                "VALUES (:uid, 'user', 'auth.signup', 'user', :uid, "
                "CAST(:ip AS inet), CAST('{}' AS jsonb))"
            ),
            {"uid": user_id, "ip": ip},
        )
        await s.commit()


async def _is_frozen(engine: AsyncEngine, user_id: uuid.UUID) -> bool:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        result = await s.execute(
            text("SELECT is_frozen FROM users WHERE id = :uid"), {"uid": user_id}
        )
        return bool(result.scalar_one())


async def _count_risk_flags(engine: AsyncEngine, user_id: uuid.UUID) -> int:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        result = await s.execute(
            text("SELECT COUNT(*) FROM risk_flags WHERE user_id = :uid"),
            {"uid": user_id},
        )
        return int(result.scalar_one())


# ===== AC7 #1 =====


async def test_seed_risk_rules_loaded(engine: AsyncEngine) -> None:
    """AC7 #1 — migration seeded all 5 rules; only ip_24_share is enabled."""
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        result = await s.execute(text("SELECT code, enabled FROM risk_rules ORDER BY code"))
        rows = {r.code: r.enabled for r in result}
    assert set(rows.keys()) == {
        "fingerprint_high",
        "ip_24_share",
        "calls_24h_over_20",
        "payment_reused",
        "phone_reused",
    }
    assert rows["ip_24_share"] is True
    assert all(v is False for k, v in rows.items() if k != "ip_24_share")


# ===== AC7 #2 =====


async def test_signup_alone_does_not_freeze(http_client: AsyncClient, engine: AsyncEngine) -> None:
    """AC7 #2 — single signup → no /24 prior history → no flag → not frozen."""
    r = await http_client.post(
        "/v1/auth/signup",
        json={"phone": _phone(), "email": _email()},
    )
    assert r.status_code == 201, r.text
    user_id = uuid.UUID(r.json()["user_id"])
    assert await _is_frozen(engine, user_id) is False


# ===== AC7 #3 =====


async def test_signup_then_admin_flag_freezes(
    http_client: AsyncClient, engine: AsyncEngine, admin_secret: str
) -> None:
    """AC7 #3 — signup (R3 may or may not auto-fire) + admin flag of a different enabled rule
    pushes count to 2 → user frozen + login 403."""
    # Step 1: real signup so we have a user
    r = await http_client.post("/v1/auth/signup", json={"phone": _phone(), "email": _email()})
    assert r.status_code == 201
    user_id = uuid.UUID(r.json()["user_id"])

    # Step 2: directly seed an ip_24_share flag (simulating R3 having fired on a prior signup)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO risk_flags (user_id, rule_code, source, metadata) "
                "VALUES (:uid, 'ip_24_share', 'auto', '{}'::jsonb)"
            ),
            {"uid": user_id},
        )
        await s.commit()

    # Step 3: admin enables a SECOND rule to make it count by flipping phone_reused.enabled
    # (we need 2 DISTINCT ENABLED rules; ip_24_share is enabled by default, phone_reused isn't)
    async with maker() as s:
        await s.execute(text("UPDATE risk_rules SET enabled = true WHERE code = 'phone_reused'"))
        await s.commit()

    try:
        # Step 4: admin posts a phone_reused flag → distinct enabled count becomes 2 → freeze
        r2 = await http_client.post(
            "/v1/admin/risk-flags",
            json={
                "user_id": str(user_id),
                "rule_code": "phone_reused",
                "metadata": {"note": "test"},
            },
            headers={"X-Admin-Secret": admin_secret},
        )
        assert r2.status_code == 201, r2.text
        body = r2.json()
        assert body["user_frozen"] is True
        assert body["distinct_enabled_triggers"] == 2
        assert await _is_frozen(engine, user_id) is True

        # Step 5: any login attempt for the frozen user → 403
        async with maker() as s:
            row = (
                await s.execute(
                    text("SELECT phone, email FROM users WHERE id = :uid"),
                    {"uid": user_id},
                )
            ).one()
        r4 = await http_client.post(
            "/v1/auth/otp/request",
            json={"phone": row.phone, "email": row.email},
        )
        assert r4.status_code == 403
        assert "frozen" in r4.json()["detail"]
    finally:
        # Cleanup: restore phone_reused.enabled = false so other tests aren't affected
        async with maker() as s:
            await s.execute(
                text("UPDATE risk_rules SET enabled = false WHERE code = 'phone_reused'")
            )
            await s.commit()


# ===== AC7 #4 =====


async def test_admin_flag_unknown_rule_returns_404(
    http_client: AsyncClient, admin_secret: str
) -> None:
    """AC7 #4 — admin posts flag with unknown rule_code → 404."""
    r = await http_client.post(
        "/v1/admin/risk-flags",
        json={
            "user_id": str(uuid.uuid4()),
            "rule_code": "does_not_exist",
            "metadata": {},
        },
        headers={"X-Admin-Secret": admin_secret},
    )
    assert r.status_code == 404
    assert "unknown rule_code" in r.json()["detail"]


# ===== AC7 #5 =====


async def test_admin_flag_missing_secret_returns_401(
    http_client: AsyncClient, admin_secret: str
) -> None:
    """AC7 #5 — admin secret configured but missing header → 401."""
    r = await http_client.post(
        "/v1/admin/risk-flags",
        json={
            "user_id": str(uuid.uuid4()),
            "rule_code": "ip_24_share",
            "metadata": {},
        },
        # no X-Admin-Secret header
    )
    assert r.status_code == 401


# ===== AC7 #6 =====


async def test_admin_flag_disabled_rule_does_not_count_toward_freeze(
    http_client: AsyncClient, engine: AsyncEngine, admin_secret: str
) -> None:
    """AC7 #6 — flag for a DISABLED rule is recorded but doesn't push toward freeze."""
    r = await http_client.post("/v1/auth/signup", json={"phone": _phone(), "email": _email()})
    user_id = uuid.UUID(r.json()["user_id"])

    # Seed an enabled flag first (ip_24_share)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO risk_flags (user_id, rule_code, source, metadata) "
                "VALUES (:uid, 'ip_24_share', 'auto', '{}'::jsonb)"
            ),
            {"uid": user_id},
        )
        await s.commit()

    # Admin adds a flag for fingerprint_high which is DISABLED
    r2 = await http_client.post(
        "/v1/admin/risk-flags",
        json={
            "user_id": str(user_id),
            "rule_code": "fingerprint_high",
            "metadata": {"note": "manual review"},
        },
        headers={"X-Admin-Secret": admin_secret},
    )
    assert r2.status_code == 201
    body = r2.json()
    # Flag recorded but count is still 1 (only ip_24_share is enabled)
    assert body["distinct_enabled_triggers"] == 1
    assert body["user_frozen"] is False
    assert await _is_frozen(engine, user_id) is False
    # But the row IS in the DB
    assert await _count_risk_flags(engine, user_id) == 2


# ===== AC7 #7 =====


async def test_admin_unfreeze_clears_is_frozen(
    http_client: AsyncClient, engine: AsyncEngine, admin_secret: str
) -> None:
    """AC7 #7 — unfreeze clears the flag and login is no longer 403."""
    # Setup: frozen user
    r = await http_client.post("/v1/auth/signup", json={"phone": _phone(), "email": _email()})
    user_id = uuid.UUID(r.json()["user_id"])
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text("UPDATE users SET is_frozen = true WHERE id = :uid"),
            {"uid": user_id},
        )
        await s.commit()
    assert await _is_frozen(engine, user_id) is True

    # Unfreeze
    r2 = await http_client.post(
        f"/v1/admin/users/{user_id}/unfreeze",
        json={"reason": "appeal approved"},
        headers={"X-Admin-Secret": admin_secret},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["is_frozen"] is False
    assert await _is_frozen(engine, user_id) is False

    # Verify the unfreeze audit log was written
    async with maker() as s:
        result = await s.execute(
            text(
                "SELECT metadata FROM audit_logs WHERE user_id = :uid AND action = 'user.unfreeze'"
            ),
            {"uid": user_id},
        )
        row = result.scalar_one()
    assert row.get("reason") == "appeal approved"


# ===== AC7 #8 =====


async def test_admin_unfreeze_preserves_risk_flags(
    http_client: AsyncClient, engine: AsyncEngine, admin_secret: str
) -> None:
    """AC7 #8 — unfreeze does NOT delete risk_flags rows (audit preserved)."""
    r = await http_client.post("/v1/auth/signup", json={"phone": _phone(), "email": _email()})
    user_id = uuid.UUID(r.json()["user_id"])
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO risk_flags (user_id, rule_code, source, metadata) "
                "VALUES (:uid, 'ip_24_share', 'auto', '{}'::jsonb)"
            ),
            {"uid": user_id},
        )
        await s.execute(
            text("UPDATE users SET is_frozen = true WHERE id = :uid"),
            {"uid": user_id},
        )
        await s.commit()

    pre = await _count_risk_flags(engine, user_id)
    assert pre == 1

    await http_client.post(
        f"/v1/admin/users/{user_id}/unfreeze",
        json={"reason": "test"},
        headers={"X-Admin-Secret": admin_secret},
    )
    post = await _count_risk_flags(engine, user_id)
    assert post == 1  # preserved


# ===== AC7 #9 =====


async def test_admin_list_flags_returns_history(
    http_client: AsyncClient, engine: AsyncEngine, admin_secret: str
) -> None:
    """AC7 #9 — GET /v1/admin/risk-flags?user_id=X returns rows DESC."""
    r = await http_client.post("/v1/auth/signup", json={"phone": _phone(), "email": _email()})
    user_id = uuid.UUID(r.json()["user_id"])

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO risk_flags (user_id, rule_code, source, metadata) "
                "VALUES (:uid, 'ip_24_share', 'auto', '{}'::jsonb)"
            ),
            {"uid": user_id},
        )
        await s.execute(
            text(
                "INSERT INTO risk_flags (user_id, rule_code, source, metadata) "
                "VALUES (:uid, 'fingerprint_high', 'admin', '{}'::jsonb)"
            ),
            {"uid": user_id},
        )
        await s.commit()

    r2 = await http_client.get(
        f"/v1/admin/risk-flags?user_id={user_id}",
        headers={"X-Admin-Secret": admin_secret},
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert len(body) == 2
    # DESC order — the second-inserted (fingerprint_high) comes first
    assert body[0]["rule_code"] == "fingerprint_high"


# ===== AC7 #10 =====


async def test_r3_ip24_share_triggers_when_3_priors_same_24(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    """AC7 #10 — seed 3 prior users with same /24 IP via audit_logs → R3 fires
    on new signup (single rule still < FREEZE_THRESHOLD so user not frozen)."""
    # Seed 3 prior users at 198.51.100.X
    for i in range(3):
        await _seed_prior_signup(
            engine,
            uuid.uuid4(),
            f"+8613{uuid.uuid4().int % 10**10:010d}",
            f"prior-{uuid.uuid4().hex[:10]}@example.com",
            f"198.51.100.{i + 1}",
        )

    # 4th signup via HTTP — the ASGI client.host defaults to 127.0.0.1 in
    # httpx ASGITransport so we can't trigger R3 via the HTTP path here.
    # Instead, evaluate the risk module directly to verify the algorithm works.
    from auth_service.risk import evaluate_ip_24_share

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        fake_user_id = uuid.uuid4()
        # Insert the 4th user (so the evaluator's user_id != exclusion catches the 3 priors)
        await s.execute(
            text("INSERT INTO users (id, phone, email) VALUES (:id, :p, :e)"),
            {"id": fake_user_id, "p": _phone(), "e": _email()},
        )
        await s.commit()

        triggered = await evaluate_ip_24_share(s, fake_user_id, "198.51.100.99")
    assert triggered is True

    # Verify negative case: different /24 → no trigger
    async with maker() as s:
        other_user_id = uuid.uuid4()
        await s.execute(
            text("INSERT INTO users (id, phone, email) VALUES (:id, :p, :e)"),
            {"id": other_user_id, "p": _phone(), "e": _email()},
        )
        await s.commit()
        triggered2 = await evaluate_ip_24_share(s, other_user_id, "203.0.113.5")
    assert triggered2 is False
