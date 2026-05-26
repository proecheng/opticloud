"""Story 1.12 — J7 risk freeze appeal lifecycle tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from auth_service.config import settings
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def _phone() -> str:
    return f"+8613{uuid.uuid4().int % 10**10:010d}"


def _email() -> str:
    return f"appeal-{uuid.uuid4().hex[:10]}@example.com"


@pytest_asyncio.fixture
async def admin_secret() -> AsyncIterator[str]:
    secret = "test-admin-secret-not-for-prod"  # noqa: S105
    original = settings.admin_secret
    settings.admin_secret = secret
    yield secret
    settings.admin_secret = original


async def _seed_frozen_user(
    engine: AsyncEngine,
    *,
    risk_score: str = "0.50",
    flags: list[str] | None = None,
) -> tuple[uuid.UUID, str, str]:
    user_id = uuid.uuid4()
    phone = _phone()
    email = _email()
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO users (id, phone, email, age_verified, is_frozen, risk_score) "
                "VALUES (:id, :p, :e, true, true, :score)"
            ),
            {"id": user_id, "p": phone, "e": email, "score": risk_score},
        )
        for rule_code in flags or []:
            await s.execute(
                text(
                    "INSERT INTO risk_flags (user_id, rule_code, source, metadata) "
                    "VALUES (:uid, :rule, 'auto', CAST(:meta AS jsonb))"
                ),
                {"uid": user_id, "rule": rule_code, "meta": '{"reason":"test"}'},
            )
        await s.commit()
    return user_id, phone, email


async def _is_frozen(engine: AsyncEngine, user_id: uuid.UUID) -> bool:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        result = await s.execute(
            text("SELECT is_frozen FROM users WHERE id = :uid"), {"uid": user_id}
        )
        return bool(result.scalar_one())


def _token_from_url(url: str) -> str:
    return url.split("token=", 1)[1]


async def test_manual_appeal_submission_and_tracking(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    user_id, phone, email = await _seed_frozen_user(engine, flags=["ip_24_share"])

    response = await http_client.post(
        "/v1/auth/risk-appeals",
        json={
            "phone": phone,
            "email": email,
            "reason": "我们是三人团队共用实验室网络，需要人工复核。",
            "evidence": {"team_context": "three teammates"},
            "team_size": 3,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["review_mode"] == "manual_48h"
    assert body["sla_due_at"] is not None

    token = _token_from_url(body["tracking_url"])
    status_response = await http_client.get(f"/v1/auth/risk-appeals/status?token={token}")
    assert status_response.status_code == 200, status_response.text
    status_body = status_response.json()
    assert status_body["appeal_id"] == body["appeal_id"]
    assert status_body["status"] == "pending"
    assert status_body["evidence_summary"][0]["rule_code"] == "ip_24_share"
    assert await _is_frozen(engine, user_id) is True
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        audit_resource_id = (
            await s.execute(
                text(
                    "SELECT resource_id FROM audit_logs "
                    "WHERE action = 'risk.appeal.submitted' AND user_id = :uid"
                ),
                {"uid": user_id},
            )
        ).scalar_one()
    assert str(audit_resource_id) == body["appeal_id"]


async def test_duplicate_active_appeal_rotates_token(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    _, phone, email = await _seed_frozen_user(engine)
    payload = {
        "phone": phone,
        "email": email,
        "reason": "我们是两人团队共享设备，提交说明用于自动复核。",
        "evidence": {"shared_device": "lab workstation"},
        "team_size": 3,
    }
    first = (await http_client.post("/v1/auth/risk-appeals", json=payload)).json()
    second = (await http_client.post("/v1/auth/risk-appeals", json=payload)).json()
    assert first["appeal_id"] == second["appeal_id"]
    old_token = _token_from_url(first["tracking_url"])
    new_token = _token_from_url(second["tracking_url"])
    assert old_token != new_token

    old_status = await http_client.get(f"/v1/auth/risk-appeals/status?token={old_token}")
    assert old_status.status_code == 404
    new_status = await http_client.get(f"/v1/auth/risk-appeals/status?token={new_token}")
    assert new_status.status_code == 200


async def test_auto_score_approves_and_unfreezes(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    user_id, phone, email = await _seed_frozen_user(engine, risk_score="0.40")
    response = await http_client.post(
        "/v1/auth/risk-appeals",
        json={
            "phone": phone,
            "email": email,
            "reason": "我是帮室友注册并共用一台电脑，账号用途可以合并说明。",
            "evidence": {"roommate_registration": "roommate asked for setup help"},
            "team_size": 2,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "approved"
    assert body["review_mode"] == "auto_score"
    assert await _is_frozen(engine, user_id) is False


async def test_auto_score_merge_offer_and_accept_is_idempotent(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    user_id, phone, email = await _seed_frozen_user(
        engine,
        risk_score="0.95",
        flags=["ip_24_share", "phone_reused"],
    )
    response = await http_client.post(
        "/v1/auth/risk-appeals",
        json={
            "phone": phone,
            "email": email,
            "reason": "请帮我复审账号冻结，当前需要恢复访问。",
            "evidence": {},
            "team_size": 1,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "merge_offered"
    assert body["merge_offer"]["offer_type"] == "keep_one_account"
    assert await _is_frozen(engine, user_id) is True

    token = _token_from_url(body["tracking_url"])
    accept_payload = {"token": token}
    accept_1 = await http_client.post(
        f"/v1/auth/risk-appeals/{body['appeal_id']}/merge-offer/accept",
        json=accept_payload,
    )
    assert accept_1.status_code == 200, accept_1.text
    assert accept_1.json()["status"] == "merge_accepted"
    assert await _is_frozen(engine, user_id) is False

    accept_2 = await http_client.post(
        f"/v1/auth/risk-appeals/{body['appeal_id']}/merge-offer/accept",
        json=accept_payload,
    )
    assert accept_2.status_code == 200, accept_2.text


async def test_admin_approve_manual_appeal_unfreezes(
    http_client: AsyncClient,
    engine: AsyncEngine,
    admin_secret: str,
) -> None:
    user_id, phone, email = await _seed_frozen_user(engine)
    appeal = (
        await http_client.post(
            "/v1/auth/risk-appeals",
            json={
                "phone": phone,
                "email": email,
                "reason": "三人团队共享办公室网络，请人工复核。",
                "evidence": {"team_context": "ops team"},
                "team_size": 3,
            },
        )
    ).json()

    listed = await http_client.get(
        "/v1/admin/risk-appeals",
        headers={"X-Admin-Secret": admin_secret},
    )
    assert listed.status_code == 200, listed.text
    assert any(row["appeal_id"] == appeal["appeal_id"] for row in listed.json())

    decided = await http_client.post(
        f"/v1/admin/risk-appeals/{appeal['appeal_id']}/decision",
        json={"decision": "approve", "reason": "appeal approved"},
        headers={"X-Admin-Secret": admin_secret},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "approved"
    assert await _is_frozen(engine, user_id) is False


async def test_admin_reject_manual_appeal_creates_merge_offer(
    http_client: AsyncClient,
    admin_secret: str,
    engine: AsyncEngine,
) -> None:
    _, phone, email = await _seed_frozen_user(engine)
    appeal = (
        await http_client.post(
            "/v1/auth/risk-appeals",
            json={
                "phone": phone,
                "email": email,
                "reason": "三人团队需要人工复审。",
                "evidence": {"team_context": "shared lab"},
                "team_size": 3,
            },
        )
    ).json()
    decided = await http_client.post(
        f"/v1/admin/risk-appeals/{appeal['appeal_id']}/decision",
        json={"decision": "reject", "reason": "risk maintained"},
        headers={"X-Admin-Secret": admin_secret},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "merge_offered"
    assert decided.json()["merge_offer"]["next_action"] == "accept_merge_to_resume"


async def test_non_frozen_deleted_and_expired_token_boundaries(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    user_id, phone, email = await _seed_frozen_user(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text("UPDATE users SET is_frozen = false WHERE id = :uid"), {"uid": user_id}
        )
        await s.commit()

    response = await http_client.post(
        "/v1/auth/risk-appeals",
        json={
            "phone": phone,
            "email": email,
            "reason": "账号没有冻结时不应允许申诉。",
            "evidence": {"contact_note": "not frozen"},
            "team_size": 1,
        },
    )
    assert response.status_code == 403

    async with maker() as s:
        await s.execute(
            text("UPDATE users SET is_frozen = true, deleted_at = NOW() WHERE id = :uid"),
            {"uid": user_id},
        )
        await s.commit()
    deleted = await http_client.post(
        "/v1/auth/risk-appeals",
        json={
            "phone": phone,
            "email": email,
            "reason": "账号删除后不应允许申诉。",
            "evidence": {"contact_note": "deleted"},
            "team_size": 1,
        },
    )
    assert deleted.status_code == 403

    async with maker() as s:
        await s.execute(
            text("UPDATE users SET deleted_at = NULL WHERE id = :uid"),
            {"uid": user_id},
        )
        await s.commit()
    created = (
        await http_client.post(
            "/v1/auth/risk-appeals",
            json={
                "phone": phone,
                "email": email,
                "reason": "生成一个 token 后手动过期。",
                "evidence": {"contact_note": "expire token"},
                "team_size": 3,
            },
        )
    ).json()
    token = _token_from_url(created["tracking_url"])
    async with maker() as s:
        await s.execute(
            text("UPDATE risk_appeals SET tracking_token_expires_at = :past WHERE id = :appeal_id"),
            {
                "past": datetime.now(UTC) - timedelta(seconds=1),
                "appeal_id": created["appeal_id"],
            },
        )
        await s.commit()
    expired = await http_client.get(f"/v1/auth/risk-appeals/status?token={token}")
    assert expired.status_code == 404
