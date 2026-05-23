"""Story 1.7 — account merge proposal lifecycle tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import pytest_asyncio
from auth_service import security
from auth_service.config import settings
from auth_service.models import AuditLog, User
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def _phone() -> str:
    return f"+8613{uuid.uuid4().int % 10**10:010d}"


def _email(domain: str = "example.com") -> str:
    return f"merge-{uuid.uuid4().hex[:10]}@{domain}"


@pytest_asyncio.fixture
async def admin_secret() -> AsyncIterator[str]:
    secret = "test-admin-secret-not-for-prod"  # noqa: S105
    original = settings.admin_secret
    settings.admin_secret = secret
    yield secret
    settings.admin_secret = original


async def _signup(
    http_client: AsyncClient, *, domain: str = "example.com"
) -> tuple[uuid.UUID, str]:
    r = await http_client.post(
        "/v1/auth/signup",
        json={"phone": _phone(), "email": _email(domain), "age_years": 18},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return uuid.UUID(body["user_id"]), body["jwt_access"]


async def _freeze_user(engine: AsyncEngine, user_id: uuid.UUID) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(text("UPDATE users SET is_frozen = true WHERE id = :uid"), {"uid": user_id})
        await s.commit()


async def _seed_user(engine: AsyncEngine, *, domain: str = "example.com") -> uuid.UUID:
    user_id = uuid.uuid4()
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO users (id, phone, email, age_verified) "
                "VALUES (:id, :phone, :email, true)"
            ),
            {"id": user_id, "phone": _phone(), "email": _email(domain)},
        )
        await s.commit()
    return user_id


async def _seed_risk_flag(engine: AsyncEngine, user_id: uuid.UUID) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO risk_flags (user_id, rule_code, source, metadata) "
                "VALUES (:uid, 'ip_24_share', 'auto', CAST('{}' AS jsonb))"
            ),
            {"uid": user_id},
        )
        await s.commit()


async def _create_key(http_client: AsyncClient, jwt: str) -> str:
    r = await http_client.post(
        "/v1/auth/api_keys",
        json={"label": "merge-test", "scope": ["optimize:write"]},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _proposal_body(
    primary: uuid.UUID,
    duplicate: uuid.UUID,
    *,
    team_size: int = 2,
    reason: str = "我帮室友注册，需要合并重复账户",
) -> dict[str, object]:
    return {
        "primary_user_id": str(primary),
        "duplicate_user_ids": [str(duplicate)],
        "evidence": {
            "reason": reason,
            "contact_email": "review@example.com",
            "team_size": team_size,
        },
    }


async def test_frozen_requester_can_create_auto_approved_proposal(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    requester, jwt = await _signup(http_client, domain="same.edu")
    duplicate, _ = await _signup(http_client, domain="same.edu")
    await _freeze_user(engine, requester)
    await _seed_risk_flag(engine, requester)
    await _seed_risk_flag(engine, duplicate)

    r = await http_client.post(
        "/v1/auth/account-merge-proposals",
        json=_proposal_body(requester, duplicate),
        headers={"Authorization": f"Bearer {jwt}"},
    )

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "auto_approved"
    assert body["review_mode"] == "auto"
    assert body["auto_score"] >= 0.7
    assert body["next_action"] == "accept_merge"


async def test_non_frozen_requester_receives_409(
    http_client: AsyncClient,
) -> None:
    requester, jwt = await _signup(http_client)
    duplicate, _ = await _signup(http_client)

    r = await http_client.post(
        "/v1/auth/account-merge-proposals",
        json=_proposal_body(requester, duplicate),
        headers={"Authorization": f"Bearer {jwt}"},
    )

    assert r.status_code == 409
    assert r.json()["detail"] == "account is not frozen"


async def test_rejects_deleted_duplicate_account(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    requester, jwt = await _signup(http_client, domain="same.edu")
    duplicate, _ = await _signup(http_client, domain="same.edu")
    await _freeze_user(engine, requester)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text("UPDATE users SET deleted_at = NOW(), email = :email WHERE id = :uid"),
            {"uid": duplicate, "email": f"deleted-{duplicate.hex[:12]}@invalid.local"},
        )
        await s.commit()

    r = await http_client.post(
        "/v1/auth/account-merge-proposals",
        json=_proposal_body(requester, duplicate),
        headers={"Authorization": f"Bearer {jwt}"},
    )

    assert r.status_code == 409
    assert "deleted" in r.json()["detail"]


async def test_rejects_duplicate_without_merge_signal(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    requester = await _seed_user(engine, domain="a.example")
    duplicate = await _seed_user(engine, domain="b.example")
    jwt = security.create_access_token(requester)
    await _freeze_user(engine, requester)

    r = await http_client.post(
        "/v1/auth/account-merge-proposals",
        json=_proposal_body(requester, duplicate),
        headers={"Authorization": f"Bearer {jwt}"},
    )

    assert r.status_code == 422
    assert "no allowed merge signal" in r.json()["detail"]


async def test_human_mode_proposal_appears_in_admin_queue_with_48h_due(
    http_client: AsyncClient, engine: AsyncEngine, admin_secret: str
) -> None:
    requester, jwt = await _signup(http_client, domain="same.edu")
    duplicate, _ = await _signup(http_client, domain="same.edu")
    await _freeze_user(engine, requester)

    r = await http_client.post(
        "/v1/auth/account-merge-proposals",
        json=_proposal_body(requester, duplicate, team_size=3),
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending_review"
    assert body["review_mode"] == "human"
    due = datetime.fromisoformat(body["review_due_at"])
    created = datetime.fromisoformat(body["created_at"])
    assert timedelta(hours=47, minutes=59) < due - created < timedelta(hours=48, minutes=1)

    q = await http_client.get(
        "/v1/admin/account-merge-proposals?status=pending_review",
        headers={"X-Admin-Secret": admin_secret},
    )
    assert q.status_code == 200, q.text
    assert any(row["id"] == body["id"] for row in q.json())


async def test_admin_approve_then_accept_unfreezes_primary_and_retires_duplicate(
    http_client: AsyncClient, engine: AsyncEngine, admin_secret: str
) -> None:
    requester, jwt = await _signup(http_client, domain="same.edu")
    duplicate, duplicate_jwt = await _signup(http_client, domain="same.edu")
    await _freeze_user(engine, requester)
    key_id = await _create_key(http_client, duplicate_jwt)
    proposal = await http_client.post(
        "/v1/auth/account-merge-proposals",
        json=_proposal_body(requester, duplicate, team_size=3),
        headers={"Authorization": f"Bearer {jwt}"},
    )
    proposal_id = proposal.json()["id"]

    review = await http_client.post(
        f"/v1/admin/account-merge-proposals/{proposal_id}/review",
        json={"decision": "approve", "reason": "证据足够"},
        headers={"X-Admin-Secret": admin_secret},
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "approved"

    accepted = await http_client.post(
        f"/v1/auth/account-merge-proposals/{proposal_id}/accept",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        primary = (await s.execute(select(User).where(User.id == requester))).scalar_one()
        dup = (await s.execute(select(User).where(User.id == duplicate))).scalar_one()
        revoked_at = (
            await s.execute(
                text("SELECT revoked_at FROM api_keys WHERE id = :kid"), {"kid": key_id}
            )
        ).scalar_one()
    assert primary.is_frozen is False
    assert dup.is_frozen is True
    assert dup.merged_into_user_id == requester
    assert dup.merged_at is not None
    assert revoked_at is not None


async def test_admin_reject_prevents_accept(
    http_client: AsyncClient, engine: AsyncEngine, admin_secret: str
) -> None:
    requester, jwt = await _signup(http_client, domain="same.edu")
    duplicate, _ = await _signup(http_client, domain="same.edu")
    await _freeze_user(engine, requester)
    proposal = await http_client.post(
        "/v1/auth/account-merge-proposals",
        json=_proposal_body(requester, duplicate, team_size=3),
        headers={"Authorization": f"Bearer {jwt}"},
    )
    proposal_id = proposal.json()["id"]

    review = await http_client.post(
        f"/v1/admin/account-merge-proposals/{proposal_id}/review",
        json={"decision": "reject", "reason": "证据不足"},
        headers={"X-Admin-Secret": admin_secret},
    )
    assert review.status_code == 200
    assert review.json()["status"] == "rejected"

    accepted = await http_client.post(
        f"/v1/auth/account-merge-proposals/{proposal_id}/accept",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert accepted.status_code == 409


async def test_accept_is_idempotent(http_client: AsyncClient, engine: AsyncEngine) -> None:
    requester, jwt = await _signup(http_client, domain="same.edu")
    duplicate, _ = await _signup(http_client, domain="same.edu")
    await _freeze_user(engine, requester)
    await _seed_risk_flag(engine, requester)
    await _seed_risk_flag(engine, duplicate)
    proposal = await http_client.post(
        "/v1/auth/account-merge-proposals",
        json=_proposal_body(requester, duplicate),
        headers={"Authorization": f"Bearer {jwt}"},
    )
    proposal_id = proposal.json()["id"]

    first = await http_client.post(
        f"/v1/auth/account-merge-proposals/{proposal_id}/accept",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    second = await http_client.post(
        f"/v1/auth/account-merge-proposals/{proposal_id}/accept",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["accepted_at"] == first.json()["accepted_at"]


async def test_proposal_and_accept_write_audit_logs(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    requester, jwt = await _signup(http_client, domain="same.edu")
    duplicate, _ = await _signup(http_client, domain="same.edu")
    await _freeze_user(engine, requester)
    await _seed_risk_flag(engine, requester)
    await _seed_risk_flag(engine, duplicate)
    proposal = await http_client.post(
        "/v1/auth/account-merge-proposals",
        json=_proposal_body(requester, duplicate),
        headers={"Authorization": f"Bearer {jwt}"},
    )
    await http_client.post(
        f"/v1/auth/account-merge-proposals/{proposal.json()['id']}/accept",
        headers={"Authorization": f"Bearer {jwt}"},
    )

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        actions = {
            row.action
            for row in (
                await s.execute(select(AuditLog.action).where(AuditLog.user_id == requester))
            ).all()
        }
    assert "account_merge.proposed" in actions
    assert "account_merge.auto_approved" in actions
    assert "account_merge.accepted" in actions


async def test_proposal_cannot_claim_another_primary_account(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    requester, jwt = await _signup(http_client, domain="same.edu")
    other_primary, _ = await _signup(http_client, domain="same.edu")
    duplicate, _ = await _signup(http_client, domain="same.edu")
    await _freeze_user(engine, requester)

    r = await http_client.post(
        "/v1/auth/account-merge-proposals",
        json=_proposal_body(other_primary, duplicate),
        headers={"Authorization": f"Bearer {jwt}"},
    )

    assert r.status_code == 403


async def test_retired_duplicate_cannot_be_reused_or_create_new_keys(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    requester, jwt = await _signup(http_client, domain="same.edu")
    duplicate, duplicate_jwt = await _signup(http_client, domain="same.edu")
    await _freeze_user(engine, requester)
    await _seed_risk_flag(engine, requester)
    await _seed_risk_flag(engine, duplicate)
    proposal = await http_client.post(
        "/v1/auth/account-merge-proposals",
        json=_proposal_body(requester, duplicate),
        headers={"Authorization": f"Bearer {jwt}"},
    )
    await http_client.post(
        f"/v1/auth/account-merge-proposals/{proposal.json()['id']}/accept",
        headers={"Authorization": f"Bearer {jwt}"},
    )

    requester_2, jwt_2 = await _signup(http_client, domain="same.edu")
    await _freeze_user(engine, requester_2)
    r = await http_client.post(
        "/v1/auth/account-merge-proposals",
        json=_proposal_body(requester_2, duplicate),
        headers={"Authorization": f"Bearer {jwt_2}"},
    )

    assert r.status_code == 409
    assert "already merged" in r.json()["detail"]

    new_key = await http_client.post(
        "/v1/auth/api_keys",
        json={"label": "retired-account", "scope": ["optimize:read"]},
        headers={"Authorization": f"Bearer {duplicate_jwt}"},
    )
    assert new_key.status_code == 403
    assert new_key.json()["detail"] == "account merged"

    duplicate_as_requester = await http_client.post(
        "/v1/auth/account-merge-proposals",
        json=_proposal_body(duplicate, requester_2),
        headers={"Authorization": f"Bearer {duplicate_jwt}"},
    )
    assert duplicate_as_requester.status_code == 403
    assert duplicate_as_requester.json()["detail"] == "account merged"
