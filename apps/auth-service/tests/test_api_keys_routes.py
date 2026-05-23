"""HTTP route tests for Story 1.3 — API Keys CRUD complete (FR A2).

Covers create / list / revoke + expires_in_days convenience + cross-tenant
isolation + cross-service "revoke 立即生效" via direct solver auth import.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def _phone() -> str:
    return f"+8613{uuid.uuid4().int % 10**10:010d}"


def _email() -> str:
    return f"key-{uuid.uuid4().hex[:10]}@example.com"


@pytest_asyncio.fixture
async def signed_in_jwt(http_client: AsyncClient) -> tuple[uuid.UUID, str]:
    """Sign up a fresh user; return (user_id, jwt_access)."""
    r = await http_client.post(
        "/v1/auth/signup", json={"phone": _phone(), "email": _email(), "age_years": 18}
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return uuid.UUID(body["user_id"]), body["jwt_access"]


# ===== AC3 cases 1-8 =====


async def test_create_api_key_returns_full_key_once(
    http_client: AsyncClient, signed_in_jwt: tuple[uuid.UUID, str]
) -> None:
    """AC3 #1 — POST returns full sk-... key; subsequent GET only shows prefix."""
    _, jwt = signed_in_jwt
    r = await http_client.post(
        "/v1/auth/api_keys",
        json={"label": "prod", "scope": ["optimize:write"]},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    full_key = body["api_key"]
    assert full_key.startswith("sk-")
    assert len(full_key) > 40
    assert body["prefix"] == full_key[:6]

    # List — full key NOT present
    list_r = await http_client.get("/v1/auth/api_keys", headers={"Authorization": f"Bearer {jwt}"})
    assert list_r.status_code == 200
    keys = list_r.json()
    assert len(keys) == 1
    assert "api_key" not in keys[0]
    assert keys[0]["prefix"] == body["prefix"]


async def test_create_api_key_without_auth_returns_401(http_client: AsyncClient) -> None:
    """AC3 #2 — no Bearer → 401."""
    r = await http_client.post(
        "/v1/auth/api_keys", json={"label": "x", "scope": ["optimize:write"]}
    )
    assert r.status_code == 401, r.text


async def test_create_api_key_with_invalid_scope_returns_422(
    http_client: AsyncClient, signed_in_jwt: tuple[uuid.UUID, str]
) -> None:
    """AC3 #3 — bogus scope value rejected by Pydantic validator."""
    _, jwt = signed_in_jwt
    r = await http_client.post(
        "/v1/auth/api_keys",
        json={"label": "bad", "scope": ["bogus:write"]},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert r.status_code == 422, r.text


async def test_create_api_key_with_expires_in_days_resolves_to_absolute(
    http_client: AsyncClient, signed_in_jwt: tuple[uuid.UUID, str]
) -> None:
    """AC3 #4 — expires_in_days=30 → expires_at ≈ now+30d."""
    _, jwt = signed_in_jwt
    r = await http_client.post(
        "/v1/auth/api_keys",
        json={"label": "30d", "scope": ["optimize:read"], "expires_in_days": 30},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert r.status_code == 201, r.text
    expires_at = datetime.fromisoformat(r.json()["expires_at"])
    expected = datetime.now(UTC) + timedelta(days=30)
    delta = abs((expires_at - expected).total_seconds())
    assert delta < 60, f"expires_at off by {delta}s"


async def test_create_api_key_with_both_expires_args_returns_422(
    http_client: AsyncClient, signed_in_jwt: tuple[uuid.UUID, str]
) -> None:
    """AC3 #5 — sending both expires_at AND expires_in_days → 422."""
    _, jwt = signed_in_jwt
    future = (datetime.now(UTC) + timedelta(days=10)).isoformat()
    r = await http_client.post(
        "/v1/auth/api_keys",
        json={
            "label": "conflict",
            "scope": ["optimize:write"],
            "expires_at": future,
            "expires_in_days": 30,
        },
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert r.status_code == 422, r.text


async def test_list_api_keys_returns_only_own_keys(http_client: AsyncClient) -> None:
    """AC3 #6 — cross-tenant isolation: User A sees only their own keys."""
    # User A
    r_a = await http_client.post(
        "/v1/auth/signup", json={"phone": _phone(), "email": _email(), "age_years": 18}
    )
    jwt_a = r_a.json()["jwt_access"]
    for label in ("a-prod", "a-dev"):
        await http_client.post(
            "/v1/auth/api_keys",
            json={"label": label, "scope": ["optimize:read"]},
            headers={"Authorization": f"Bearer {jwt_a}"},
        )

    # User B
    r_b = await http_client.post(
        "/v1/auth/signup", json={"phone": _phone(), "email": _email(), "age_years": 18}
    )
    jwt_b = r_b.json()["jwt_access"]
    await http_client.post(
        "/v1/auth/api_keys",
        json={"label": "b-prod", "scope": ["optimize:read"]},
        headers={"Authorization": f"Bearer {jwt_b}"},
    )

    # User A's list: own 2 keys only (NOT b-prod)
    list_a = await http_client.get(
        "/v1/auth/api_keys", headers={"Authorization": f"Bearer {jwt_a}"}
    )
    labels_a = {k["label"] for k in list_a.json()}
    assert labels_a == {"a-prod", "a-dev"}, f"got {labels_a}"


async def test_revoke_own_key_returns_204(
    http_client: AsyncClient, signed_in_jwt: tuple[uuid.UUID, str]
) -> None:
    """AC3 #7 — DELETE own key → 204; subsequent GET shows revoked_at populated."""
    _, jwt = signed_in_jwt
    create = await http_client.post(
        "/v1/auth/api_keys",
        json={"label": "to-revoke", "scope": ["optimize:read"]},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    key_id = create.json()["id"]

    rev = await http_client.delete(
        f"/v1/auth/api_keys/{key_id}", headers={"Authorization": f"Bearer {jwt}"}
    )
    assert rev.status_code == 204, rev.text

    listed = (
        await http_client.get("/v1/auth/api_keys", headers={"Authorization": f"Bearer {jwt}"})
    ).json()
    matched = [k for k in listed if k["id"] == key_id]
    assert len(matched) == 1
    assert matched[0]["revoked_at"] is not None


async def test_revoke_other_users_key_returns_404(http_client: AsyncClient) -> None:
    """AC3 #8 — User A cannot DELETE User B's key (404 not 403; no enum)."""
    # User A signup + create
    r_a = await http_client.post(
        "/v1/auth/signup", json={"phone": _phone(), "email": _email(), "age_years": 18}
    )
    jwt_a = r_a.json()["jwt_access"]
    create_a = await http_client.post(
        "/v1/auth/api_keys",
        json={"label": "a-only", "scope": ["optimize:read"]},
        headers={"Authorization": f"Bearer {jwt_a}"},
    )
    a_key_id = create_a.json()["id"]

    # User B signup
    r_b = await http_client.post(
        "/v1/auth/signup", json={"phone": _phone(), "email": _email(), "age_years": 18}
    )
    jwt_b = r_b.json()["jwt_access"]

    # B tries to delete A's key
    rev = await http_client.delete(
        f"/v1/auth/api_keys/{a_key_id}", headers={"Authorization": f"Bearer {jwt_b}"}
    )
    assert rev.status_code == 404, rev.text


# ===== AC4 case 9 — cross-service revoke takes effect immediately =====


async def test_revoke_invalidates_solver_calls_immediately(
    http_client: AsyncClient,
    signed_in_jwt: tuple[uuid.UUID, str],
    engine: AsyncEngine,
) -> None:
    """AC4 #9 — DB-level integration: revoke → solver.verify_api_key 立即 401."""
    from fastapi import HTTPException

    # Import solver's verify_api_key directly (DB-level integration, NOT HTTP)
    from solver_orchestrator.auth import verify_api_key as solver_verify_api_key

    _, jwt = signed_in_jwt
    create = await http_client.post(
        "/v1/auth/api_keys",
        json={"label": "cross-svc", "scope": ["optimize:write"]},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert create.status_code == 201
    full_key = create.json()["api_key"]
    key_id = create.json()["id"]

    # Use a fresh session for solver_verify_api_key (it expects an AsyncSession)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Before revoke: solver accepts the key
    async with maker() as s:
        user_id_v, returned_key_id, scopes = await solver_verify_api_key(f"Bearer {full_key}", s)
        assert str(returned_key_id) == key_id
        assert "optimize:write" in scopes
        await s.commit()

    # Revoke via auth-service
    rev = await http_client.delete(
        f"/v1/auth/api_keys/{key_id}", headers={"Authorization": f"Bearer {jwt}"}
    )
    assert rev.status_code == 204

    # After revoke: solver rejects immediately (no cache; queries DB on every call)
    async with maker() as s:
        try:
            await solver_verify_api_key(f"Bearer {full_key}", s)
            raise AssertionError("solver accepted revoked key — revoke not effective")
        except HTTPException as e:
            assert e.status_code == 401
            assert "invalid or revoked" in e.detail.lower()
