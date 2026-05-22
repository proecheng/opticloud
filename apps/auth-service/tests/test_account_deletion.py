"""Story 1.6 — PIPL account deletion lifecycle tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from auth_service.account_deletion import complete_due_deletion_requests
from auth_service.models import AccountDeletionRequest, AuditLog, User
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def _phone() -> str:
    return f"+8613{uuid.uuid4().int % 10**10:010d}"


def _email() -> str:
    return f"delete-{uuid.uuid4().hex[:10]}@example.com"


@pytest_asyncio.fixture(autouse=True)
async def _ensure_account_deletion_table(engine: AsyncEngine) -> None:
    """Local DBs may predate Story 1.6; CI applies updated 01-schema.sql."""
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS account_deletion_requests (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id_snapshot UUID NOT NULL UNIQUE,
                    user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'scheduled',
                    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    hard_delete_at TIMESTAMPTZ NOT NULL,
                    completed_at TIMESTAMPTZ NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await s.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_account_deletion_requests_hard_delete_at "
                "ON account_deletion_requests(hard_delete_at)"
            )
        )
        await s.commit()


async def _signup(http_client: AsyncClient) -> tuple[uuid.UUID, str, str, str]:
    phone = _phone()
    email = _email()
    r = await http_client.post("/v1/auth/signup", json={"phone": phone, "email": email})
    assert r.status_code == 201, r.text
    body = r.json()
    return uuid.UUID(body["user_id"]), phone, email, body["jwt_access"]


async def _create_api_key(http_client: AsyncClient, jwt: str) -> tuple[str, str]:
    r = await http_client.post(
        "/v1/auth/api_keys",
        json={"label": "delete-me", "scope": ["optimize:write"]},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return body["id"], body["api_key"]


async def test_request_account_deletion_soft_deletes_and_revokes_keys(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    user_id, phone, email, jwt = await _signup(http_client)
    key_id, _ = await _create_api_key(http_client, jwt)

    r = await http_client.post(
        "/v1/auth/account-deletion",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "scheduled"
    assert body["user_id_snapshot"] == str(user_id)
    assert body["requested_at"] is not None
    assert body["hard_delete_at"] is not None
    requested_at = datetime.fromisoformat(body["requested_at"])
    hard_delete_at = datetime.fromisoformat(body["hard_delete_at"])
    assert (
        timedelta(days=6, hours=23) < hard_delete_at - requested_at < timedelta(days=7, minutes=1)
    )

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        user = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        assert user.deleted_at is not None
        revoked_at = (
            await s.execute(
                text("SELECT revoked_at FROM api_keys WHERE id = :kid"), {"kid": key_id}
            )
        ).scalar_one()
        assert revoked_at is not None
        audit_actions = {
            row.action
            for row in (
                await s.execute(select(AuditLog.action).where(AuditLog.user_id == user_id))
            ).all()
        }
    assert "account_deletion.requested" in audit_actions

    otp = await http_client.post("/v1/auth/otp/request", json={"phone": phone, "email": email})
    assert otp.status_code == 403
    assert otp.json()["detail"] == "account deleted"

    list_keys = await http_client.get(
        "/v1/auth/api_keys",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert list_keys.status_code == 403
    assert list_keys.json()["detail"] == "account deleted"


async def test_account_deletion_request_is_idempotent(http_client: AsyncClient) -> None:
    user_id, _, _, jwt = await _signup(http_client)
    first = await http_client.post(
        "/v1/auth/account-deletion",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    second = await http_client.post(
        "/v1/auth/account-deletion",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["user_id_snapshot"] == str(user_id)
    assert second.json()["requested_at"] == first.json()["requested_at"]
    assert second.json()["hard_delete_at"] == first.json()["hard_delete_at"]


async def test_account_deletion_status_endpoint(http_client: AsyncClient) -> None:
    _, _, _, jwt = await _signup(http_client)

    before = await http_client.get(
        "/v1/auth/account-deletion",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert before.status_code == 200
    assert before.json()["status"] == "none"

    await http_client.post(
        "/v1/auth/account-deletion",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    after = await http_client.get(
        "/v1/auth/account-deletion",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert after.status_code == 200
    assert after.json()["status"] == "scheduled"
    assert after.json()["hard_delete_at"] is not None


async def test_hard_delete_worker_purges_due_users_and_preserves_trace(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    user_id, _, _, jwt = await _signup(http_client)
    await _create_api_key(http_client, jwt)
    r = await http_client.post(
        "/v1/auth/account-deletion",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert r.status_code == 200

    due_at = datetime.now(UTC) - timedelta(seconds=1)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        request = (
            await s.execute(
                select(AccountDeletionRequest).where(
                    AccountDeletionRequest.user_id_snapshot == user_id
                )
            )
        ).scalar_one()
        await s.execute(
            text(
                "UPDATE account_deletion_requests "
                "SET hard_delete_at = NOW() + INTERVAL '30 days' "
                "WHERE user_id_snapshot != :uid AND status = 'scheduled'"
            ),
            {"uid": user_id},
        )
        request.hard_delete_at = due_at
        await s.commit()

    async with maker() as s:
        completed = await complete_due_deletion_requests(s, now=datetime.now(UTC))
        await s.commit()
    assert user_id in completed

    async with maker() as s:
        user = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        assert user.deleted_at is not None
        assert user.phone.startswith("deleted-")
        assert user.email.endswith("@invalid.local")
        request = (
            await s.execute(
                select(AccountDeletionRequest).where(
                    AccountDeletionRequest.user_id_snapshot == user_id
                )
            )
        ).scalar_one()
        assert request.status == "completed"
        assert request.completed_at is not None
        assert request.user_id is None
        completion_audit = (
            await s.execute(
                select(AuditLog).where(
                    AuditLog.action == "account_deletion.completed",
                    AuditLog.resource_id == user_id,
                )
            )
        ).scalar_one()
        assert completion_audit.audit_metadata["user_id_snapshot"] == str(user_id)

    async with maker() as s:
        rerun = await complete_due_deletion_requests(s, now=datetime.now(UTC))
        await s.commit()
    assert rerun == []


async def test_deleted_api_key_rejected_by_solver_auth(
    http_client: AsyncClient, engine: AsyncEngine
) -> None:
    from solver_orchestrator.auth import verify_api_key as solver_verify_api_key

    _, _, _, jwt = await _signup(http_client)
    _, full_key = await _create_api_key(http_client, jwt)
    await http_client.post(
        "/v1/auth/account-deletion",
        headers={"Authorization": f"Bearer {jwt}"},
    )

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        with pytest.raises(HTTPException) as exc:
            await solver_verify_api_key(f"Bearer {full_key}", s)
    assert exc.value.status_code == 401
