"""Story 8.A.4 — self-service audit log query endpoint."""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from auth_service import security
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def _phone() -> str:
    return f"+8613{uuid.uuid4().int % 10**10:010d}"


def _email() -> str:
    return f"audit-{uuid.uuid4().hex[:10]}@example.com"


async def _signup(http_client: AsyncClient) -> tuple[uuid.UUID, str]:
    response = await http_client.post(
        "/v1/auth/signup",
        json={"phone": _phone(), "email": _email(), "age_years": 18},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return uuid.UUID(body["user_id"]), body["jwt_access"]


async def _insert_audit(
    engine: AsyncEngine,
    *,
    user_id: uuid.UUID | None,
    action: str,
    created_at: datetime,
    metadata: str = "{}",
    resource_id: uuid.UUID | None = None,
    actor: str = "user",
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> uuid.UUID:
    row_id = uuid.uuid4()
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await session.execute(
            text(
                """
                INSERT INTO audit_logs
                    (id, user_id, actor, action, resource_type, resource_id,
                     metadata, ip_address, user_agent, created_at)
                VALUES
                    (:id, :user_id, :actor, :action, 'test_resource', :resource_id,
                     CAST(:metadata AS jsonb), CAST(:ip_address AS inet),
                     :user_agent, :created_at)
                """
            ),
            {
                "id": row_id,
                "user_id": user_id,
                "actor": actor,
                "action": action,
                "resource_id": resource_id,
                "metadata": metadata,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "created_at": created_at,
            },
        )
        await session.commit()
    return row_id


async def _stored_metadata(engine: AsyncEngine, row_id: uuid.UUID) -> dict[str, object]:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        value = (
            await session.execute(
                text("SELECT metadata FROM audit_logs WHERE id = :id"),
                {"id": row_id},
            )
        ).scalar_one()
    assert isinstance(value, dict)
    return value


def _headers(jwt: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jwt}"}


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


async def test_audit_logs_require_access_jwt(http_client: AsyncClient) -> None:
    missing = await http_client.get("/v1/me/audit-logs")
    assert missing.status_code == 401

    user_id, _ = await _signup(http_client)
    refresh = security.create_refresh_token(user_id)
    refresh_result = await http_client.get(
        "/v1/me/audit-logs", headers={"Authorization": f"Bearer {refresh}"}
    )
    assert refresh_result.status_code == 401

    api_key_like = await http_client.get(
        "/v1/me/audit-logs", headers={"Authorization": "Bearer sk-not-a-jwt"}
    )
    assert api_key_like.status_code == 401


async def test_audit_logs_return_only_current_users_rows(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    user_a, jwt_a = await _signup(http_client)
    user_b, _ = await _signup(http_client)
    now = datetime(2026, 6, 2, 8, 0, tzinfo=UTC)
    own_id = await _insert_audit(
        engine,
        user_id=user_a,
        action="audit.own",
        created_at=now,
        metadata='{"label":"own"}',
        resource_id=user_a,
    )
    await _insert_audit(
        engine,
        user_id=user_b,
        action="audit.other",
        created_at=now + timedelta(seconds=1),
        metadata=f'{{"mentions_user":"{user_a}"}}',
        resource_id=user_a,
    )
    await _insert_audit(
        engine,
        user_id=None,
        action="audit.null_user",
        created_at=now + timedelta(seconds=2),
        metadata=f'{{"user_id_snapshot":"{user_a}"}}',
        resource_id=user_a,
    )

    response = await http_client.get(
        "/v1/me/audit-logs",
        params={"from": _iso(now - timedelta(days=1)), "to": _iso(now + timedelta(days=1))},
        headers=_headers(jwt_a),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    returned_ids = {item["id"] for item in body["items"]}
    assert str(own_id) in returned_ids
    assert {item["action"] for item in body["items"]} == {"audit.own", "auth.signup"}
    matched = next(item for item in body["items"] if item["id"] == str(own_id))
    assert matched["ip_address"] is None
    assert matched["metadata"] == {"label": "own"}


async def test_audit_logs_reject_user_id_query_param(
    http_client: AsyncClient,
) -> None:
    user_id, jwt = await _signup(http_client)
    response = await http_client.get(
        "/v1/me/audit-logs",
        params={"user_id": str(user_id)},
        headers=_headers(jwt),
    )
    assert response.status_code == 422
    assert "user_id" in response.text


async def test_audit_logs_time_filters_and_invalid_ranges(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    user_id, jwt = await _signup(http_client)
    base = datetime(2026, 6, 2, 9, 0, tzinfo=UTC)
    before_id = await _insert_audit(
        engine, user_id=user_id, action="audit.before", created_at=base - timedelta(hours=2)
    )
    start_id = await _insert_audit(
        engine, user_id=user_id, action="audit.start", created_at=base
    )
    end_id = await _insert_audit(
        engine, user_id=user_id, action="audit.end", created_at=base + timedelta(hours=2)
    )
    after_id = await _insert_audit(
        engine, user_id=user_id, action="audit.after", created_at=base + timedelta(hours=4)
    )

    response = await http_client.get(
        "/v1/me/audit-logs",
        params={"from": _iso(base), "to": _iso(base + timedelta(hours=2))},
        headers=_headers(jwt),
    )
    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()["items"]}
    assert str(start_id) in ids
    assert str(end_id) in ids
    assert str(before_id) not in ids
    assert str(after_id) not in ids

    invalid_range = await http_client.get(
        "/v1/me/audit-logs",
        params={"from": _iso(base + timedelta(hours=2)), "to": _iso(base)},
        headers=_headers(jwt),
    )
    assert invalid_range.status_code == 422

    naive = await http_client.get(
        "/v1/me/audit-logs",
        params={"from": "2026-06-02T09:00:00", "to": _iso(base + timedelta(hours=2))},
        headers=_headers(jwt),
    )
    assert naive.status_code == 422


async def test_audit_logs_limit_validation(http_client: AsyncClient) -> None:
    _, jwt = await _signup(http_client)
    for limit in (0, -1, 101):
        response = await http_client.get(
            "/v1/me/audit-logs",
            params={"limit": limit},
            headers=_headers(jwt),
        )
        assert response.status_code == 422


async def test_audit_logs_cursor_pagination_is_stable_and_bound_to_filters(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    user_id, jwt = await _signup(http_client)
    other_user_id, other_jwt = await _signup(http_client)
    same_time = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)
    inserted = [
        await _insert_audit(
            engine,
            user_id=user_id,
            action=f"audit.page.{idx}",
            created_at=same_time,
        )
        for idx in range(3)
    ]
    expected_order = [str(row_id) for row_id in sorted(inserted, reverse=True)]

    params = {
        "from": _iso(same_time - timedelta(minutes=1)),
        "to": _iso(same_time + timedelta(minutes=1)),
        "limit": 2,
    }
    first = await http_client.get("/v1/me/audit-logs", params=params, headers=_headers(jwt))
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert [item["id"] for item in first_body["items"]] == expected_order[:2]
    assert first_body["next_cursor"]

    second = await http_client.get(
        "/v1/me/audit-logs",
        params={"cursor": first_body["next_cursor"]},
        headers=_headers(jwt),
    )
    assert second.status_code == 200, second.text
    assert [item["id"] for item in second.json()["items"]] == expected_order[2:]

    drifted = await http_client.get(
        "/v1/me/audit-logs",
        params={**params, "limit": 3, "cursor": first_body["next_cursor"]},
        headers=_headers(jwt),
    )
    assert drifted.status_code == 422

    invalid = await http_client.get(
        "/v1/me/audit-logs",
        params={"cursor": "not-a-valid-cursor"},
        headers=_headers(jwt),
    )
    assert invalid.status_code == 422

    await _insert_audit(
        engine,
        user_id=other_user_id,
        action="audit.other.cursor",
        created_at=same_time,
    )
    wrong_user = await http_client.get(
        "/v1/me/audit-logs",
        params={"cursor": first_body["next_cursor"]},
        headers=_headers(other_jwt),
    )
    assert wrong_user.status_code == 422
    assert "current user" in wrong_user.text


async def test_audit_logs_redact_metadata_without_mutating_storage(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    user_id, jwt = await _signup(http_client)
    created_at = datetime(2026, 6, 2, 11, 0, tzinfo=UTC)
    metadata = {
        "label": "prod",
        "api_key": "sk-secret-value",
        "webhook_url_configured": True,
        "nested": {
            "authorization": "Bearer secret-token",
            "notes": ["safe", "jwt eyJabc.def.ghi"],
            "count": 2,
        },
        "events": [{"cookie": "session=secret"}, {"rule_code": "geo_anomaly"}],
    }
    expected_stored = copy.deepcopy(metadata)
    row_id = await _insert_audit(
        engine,
        user_id=user_id,
        action="audit.secret",
        created_at=created_at,
        metadata=(
            '{"label":"prod","api_key":"sk-secret-value",'
            '"webhook_url_configured":true,'
            '"nested":{"authorization":"Bearer secret-token",'
            '"notes":["safe","jwt eyJabc.def.ghi"],"count":2},'
            '"events":[{"cookie":"session=secret"},{"rule_code":"geo_anomaly"}]}'
        ),
        ip_address="203.0.113.9",
        user_agent="pytest",
    )

    response = await http_client.get(
        "/v1/me/audit-logs",
        params={
            "from": _iso(created_at - timedelta(minutes=1)),
            "to": _iso(created_at + timedelta(minutes=1)),
        },
        headers=_headers(jwt),
    )
    assert response.status_code == 200, response.text
    item = next(item for item in response.json()["items"] if item["id"] == str(row_id))
    assert item["ip_address"] == "203.0.113.9"
    assert item["user_agent"] == "pytest"
    assert item["metadata"] == {
        "label": "prod",
        "api_key": "[REDACTED]",
        "webhook_url_configured": True,
        "nested": {
            "authorization": "[REDACTED]",
            "notes": ["safe", "jwt [REDACTED]"],
            "count": 2,
        },
        "events": [{"cookie": "[REDACTED]"}, {"rule_code": "geo_anomaly"}],
    }
    assert await _stored_metadata(engine, row_id) == expected_stored


@pytest.mark.parametrize(
    ("column", "detail"),
    [
        ("deleted_at", "account deleted"),
        ("merged_at", "account merged"),
        ("is_frozen", "account frozen"),
    ],
)
async def test_audit_logs_forbid_inactive_accounts(
    http_client: AsyncClient,
    engine: AsyncEngine,
    column: str,
    detail: str,
) -> None:
    user_id, jwt = await _signup(http_client)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        if column == "is_frozen":
            await session.execute(
                text("UPDATE users SET is_frozen = true WHERE id = :uid"), {"uid": user_id}
            )
        else:
            await session.execute(
                text(f"UPDATE users SET {column} = NOW() WHERE id = :uid"),  # noqa: S608
                {"uid": user_id},
            )
        await session.commit()

    response = await http_client.get("/v1/me/audit-logs", headers=_headers(jwt))
    assert response.status_code == 403
    assert detail in response.text
