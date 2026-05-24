"""Story 1.12 — frozen appeals lifecycle tests."""

from __future__ import annotations

import uuid

from auth_service.models import AccountFreezeAppeal, AuditLog, User
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def _phone() -> str:
    return f"+8613{uuid.uuid4().int % 10**10:010d}"


def _email() -> str:
    return f"frozen-{uuid.uuid4().hex[:10]}@example.com"


async def _signup(http_client: AsyncClient, *, domain: str = "example.com") -> tuple[uuid.UUID, str]:
    r = await http_client.post(
        "/v1/auth/signup",
        json={"phone": _phone(), "email": f"appeal-{uuid.uuid4().hex[:10]}@{domain}", "age_years": 18},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return uuid.UUID(body["user_id"]), body["jwt_access"]


async def _freeze_user(engine: AsyncEngine, user_id: uuid.UUID) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(text("UPDATE users SET is_frozen = true WHERE id = :uid"), {"uid": user_id})
        await s.commit()


async def _seed_user(
    engine: AsyncEngine,
    *,
    email: str | None = None,
    phone: str | None = None,
    frozen: bool = True,
) -> uuid.UUID:
    user_id = uuid.uuid4()
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO users (id, phone, email, age_verified, is_frozen, risk_score) "
                "VALUES (:id, :phone, :email, true, :is_frozen, 0.35)"
            ),
            {
                "id": user_id,
                "phone": phone or _phone(),
                "email": email or _email(),
                "is_frozen": frozen,
            },
        )
        await s.commit()
    return user_id


def _unique_email(tag: str) -> str:
    return f"{tag}-{uuid.uuid4().hex[:10]}@example.com"


async def _seed_risk_flag(
    engine: AsyncEngine, user_id: uuid.UUID, rule_code: str = "ip_24_share"
) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO risk_flags (user_id, rule_code, source, metadata) "
                "VALUES (:uid, :rule_code, 'auto', CAST(:metadata AS jsonb))"
            ),
            {
                "uid": user_id,
                "rule_code": rule_code,
                "metadata": '{"note":"test"}',
            },
        )
        await s.commit()


async def _seed_merge_proposal(
    engine: AsyncEngine,
    *,
    requester_user_id: uuid.UUID,
    primary_user_id: uuid.UUID,
    duplicate_user_id: uuid.UUID,
    status: str = "auto_approved",
) -> uuid.UUID:
    proposal_id = uuid.uuid4()
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                """
                INSERT INTO account_merge_proposals (
                    id, requester_user_id, primary_user_id, duplicate_user_ids, evidence,
                    status, review_mode, auto_score, review_due_at, created_at, updated_at
                ) VALUES (
                    :id, :requester_user_id, :primary_user_id, ARRAY[:duplicate_user_id]::uuid[],
                    CAST(:evidence AS jsonb), :status, 'auto', 0.90,
                    NOW() + INTERVAL '1 hour', NOW(), NOW()
                )
                """
            ),
            {
                "id": proposal_id,
                "requester_user_id": requester_user_id,
                "primary_user_id": primary_user_id,
                "duplicate_user_id": duplicate_user_id,
                "evidence": '{"reason":"我帮室友注册","contact_email":"review@example.com"}',
                "status": status,
            },
        )
        await s.commit()
    return proposal_id


async def _get_appeal(engine: AsyncEngine, appeal_id: uuid.UUID) -> AccountFreezeAppeal:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        return (
            await s.execute(select(AccountFreezeAppeal).where(AccountFreezeAppeal.id == appeal_id))
        ).scalar_one()


async def _audit_actions(engine: AsyncEngine, user_id: uuid.UUID) -> list[str]:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        result = await s.execute(select(AuditLog.action).where(AuditLog.user_id == user_id))
        return [row[0] for row in result.all()]


async def test_frozen_auth_responses_include_next_action_url(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    user_id = await _seed_user(engine, frozen=True)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (await s.execute(select(User).where(User.id == user_id))).scalar_one()

    for path, body in [
        ("/v1/auth/otp/request", {"phone": row.phone, "email": row.email}),
        ("/v1/auth/login", {"phone": row.phone, "email": row.email, "phone_otp": "000000", "email_otp": "000000"}),
    ]:
        r = await http_client.post(path, json=body)
        assert r.status_code == 403, r.text
        payload = r.json()
        assert payload["detail"] == "account frozen"
        assert payload["title"] == "账户已冻结"
        assert payload["next_action_url"] == "/auth/frozen-appeal"
        assert payload["errors"][0]["remediation_hint_key"] == "auth.frozen.appeal"


async def test_frozen_user_with_existing_jwt_still_cannot_use_protected_routes(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    user_id, jwt = await _signup(http_client)
    await _freeze_user(engine, user_id)

    r = await http_client.post(
        "/v1/auth/api_keys",
        json={"label": "blocked", "scope": ["optimize:read"]},
        headers={"Authorization": f"Bearer {jwt}"},
    )

    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "account frozen"


async def test_start_appeal_succeeds_and_stores_hash_only(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    user_id = await _seed_user(engine, frozen=True)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (await s.execute(select(User).where(User.id == user_id))).scalar_one()

    r = await http_client.post(
        "/v1/auth/frozen-appeals/start",
        json={"phone": row.phone, "email": row.email},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["tracking_token"]
    assert body["tracking_url"].startswith("/auth/frozen-appeal?")

    appeal = await _get_appeal(engine, uuid.UUID(body["appeal_id"]))
    assert appeal.tracking_token_hash != body["tracking_token"]
    assert len(appeal.tracking_token_hash) == 64
    assert appeal.status == "started"


async def test_start_appeal_rejects_non_frozen_user(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    user_id = await _seed_user(engine, frozen=False)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (await s.execute(select(User).where(User.id == user_id))).scalar_one()

    r = await http_client.post(
        "/v1/auth/frozen-appeals/start",
        json={"phone": row.phone, "email": row.email},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "account is not frozen"


async def test_invalid_token_cannot_read_submit_or_accept(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    user_id = await _seed_user(engine, frozen=True)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
    start = await http_client.post(
        "/v1/auth/frozen-appeals/start",
        json={"phone": row.phone, "email": row.email},
    )
    appeal_id = start.json()["appeal_id"]

    bad_token = "appeal-token-" + "invalid-0000"
    read = await http_client.get(
        f"/v1/auth/frozen-appeals/{appeal_id}",
        params={"tracking_token": bad_token},
    )
    submit = await http_client.post(
        f"/v1/auth/frozen-appeals/{appeal_id}/proposal",
        json={
            "tracking_token": bad_token,
            "duplicate_user_ids": [str(uuid.uuid4())],
            "reason": "我帮室友注册",
            "contact_email": "review@example.com",
        },
    )
    accept = await http_client.post(
        f"/v1/auth/frozen-appeals/{appeal_id}/accept",
        json={"tracking_token": bad_token},
    )
    assert read.status_code == 403
    assert submit.status_code == 403
    assert accept.status_code == 403


async def test_submit_proposal_creates_auto_approved_merge(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    requester = await _seed_user(engine, frozen=True, email=_unique_email("primary-edu"))
    duplicate = await _seed_user(engine, frozen=False, email=_unique_email("dup-edu"))
    await _seed_risk_flag(engine, requester)
    await _seed_risk_flag(engine, duplicate)
    await _freeze_user(engine, requester)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (await s.execute(select(User).where(User.id == requester))).scalar_one()
    start = await http_client.post(
        "/v1/auth/frozen-appeals/start",
        json={"phone": row.phone, "email": row.email},
    )
    appeal = start.json()

    submit = await http_client.post(
        f"/v1/auth/frozen-appeals/{appeal['appeal_id']}/proposal",
        json={
            "tracking_token": appeal["tracking_token"],
            "duplicate_user_ids": [str(duplicate)],
            "reason": "我帮室友注册",
            "contact_email": "review@example.com",
            "team_size": 2,
        },
    )
    assert submit.status_code == 200, submit.text
    body = submit.json()
    assert body["proposal"]["status"] == "auto_approved"
    assert body["next_action"] == "accept_merge"


async def test_status_endpoint_returns_safe_risk_summary(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    requester = await _seed_user(engine, frozen=True)
    duplicate = await _seed_user(engine, frozen=False)
    await _seed_risk_flag(engine, requester)
    await _seed_risk_flag(engine, duplicate)
    await _freeze_user(engine, requester)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (await s.execute(select(User).where(User.id == requester))).scalar_one()
    start = await http_client.post(
        "/v1/auth/frozen-appeals/start",
        json={"phone": row.phone, "email": row.email},
    )
    appeal = start.json()

    status_resp = await http_client.get(
        f"/v1/auth/frozen-appeals/{appeal['appeal_id']}",
        params={"tracking_token": appeal["tracking_token"]},
    )
    assert status_resp.status_code == 200, status_resp.text
    body = status_resp.json()
    assert body["risk_summary"]["total_flag_count"] >= 1
    assert "metadata" not in str(body["risk_summary"])
    assert body["next_action"] == "submit_proposal"
    assert body["last_viewed_at"] is not None


async def test_accept_via_tracking_token_unfreezes_primary_and_retire_duplicate(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    requester = await _seed_user(engine, frozen=True, email=_unique_email("primary-log"))
    duplicate = await _seed_user(engine, frozen=False, email=_unique_email("dup-log"))
    await _seed_risk_flag(engine, requester)
    await _seed_risk_flag(engine, duplicate)
    await _freeze_user(engine, requester)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (await s.execute(select(User).where(User.id == requester))).scalar_one()
    start = await http_client.post(
        "/v1/auth/frozen-appeals/start",
        json={"phone": row.phone, "email": row.email},
    )
    appeal = start.json()
    submit = await http_client.post(
        f"/v1/auth/frozen-appeals/{appeal['appeal_id']}/proposal",
        json={
            "tracking_token": appeal["tracking_token"],
            "duplicate_user_ids": [str(duplicate)],
            "reason": "我帮室友注册",
            "contact_email": "review@example.com",
        },
    )
    assert submit.status_code == 200, submit.text

    accept = await http_client.post(
        f"/v1/auth/frozen-appeals/{appeal['appeal_id']}/accept",
        json={"tracking_token": appeal["tracking_token"]},
    )
    assert accept.status_code == 200, accept.text
    assert accept.json()["status"] == "accepted"

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        primary = (await s.execute(select(User).where(User.id == requester))).scalar_one()
        dup = (await s.execute(select(User).where(User.id == duplicate))).scalar_one()
    assert primary.is_frozen is False
    assert dup.is_frozen is True
    assert dup.merged_into_user_id == requester
    assert dup.merged_at is not None


async def test_expired_appeal_is_rejected_and_marked_expired(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    user_id = await _seed_user(engine, frozen=True)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
    start = await http_client.post(
        "/v1/auth/frozen-appeals/start",
        json={"phone": row.phone, "email": row.email},
    )
    appeal = start.json()

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text("UPDATE account_freeze_appeals SET expires_at = NOW() - INTERVAL '1 second' WHERE id = :id"),
            {"id": appeal["appeal_id"]},
        )
        await s.commit()

    r = await http_client.get(
        f"/v1/auth/frozen-appeals/{appeal['appeal_id']}",
        params={"tracking_token": appeal["tracking_token"]},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "appeal expired"
    expired = await _get_appeal(engine, uuid.UUID(appeal["appeal_id"]))
    assert expired.status == "expired"


async def test_frozen_appeal_audit_logs_are_written(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    requester = await _seed_user(engine, frozen=True, email=_unique_email("primary-audit"))
    duplicate = await _seed_user(engine, frozen=False, email=_unique_email("dup-audit"))
    await _seed_risk_flag(engine, requester)
    await _seed_risk_flag(engine, duplicate)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (await s.execute(select(User).where(User.id == requester))).scalar_one()
    start = await http_client.post(
        "/v1/auth/frozen-appeals/start",
        json={"phone": row.phone, "email": row.email},
    )
    appeal = start.json()
    await http_client.post(
        f"/v1/auth/frozen-appeals/{appeal['appeal_id']}/proposal",
        json={
            "tracking_token": appeal["tracking_token"],
            "duplicate_user_ids": [str(duplicate)],
            "reason": "我帮室友注册",
            "contact_email": "review@example.com",
        },
    )
    await http_client.post(
        f"/v1/auth/frozen-appeals/{appeal['appeal_id']}/accept",
        json={"tracking_token": appeal["tracking_token"]},
    )

    actions = await _audit_actions(engine, requester)
    assert "freeze_appeal.started" in actions
    assert "freeze_appeal.proposal_submitted" in actions
    assert "freeze_appeal.accepted" in actions
