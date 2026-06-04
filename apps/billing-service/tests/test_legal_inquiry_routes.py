"""Story 8.C.3 — Team+ legal inquiry SLA route tests."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
import pytest
import pytest_asyncio
from billing_service.auth_dep import _loader as _jwt_loader  # noqa: PLC2701
from billing_service.db import get_session
from billing_service.main import app
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

_TEST_KEY_DIR = Path("tests/_keys")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def token_factory() -> AsyncIterator[tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]]]:
    _TEST_KEY_DIR.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240
    private = Ed25519PrivateKey.generate()
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pub_path = _TEST_KEY_DIR / "jwt_public.pem"
    pub_path.write_bytes(public_pem)  # noqa: ASYNC230
    _jwt_loader._path = pub_path
    _jwt_loader._key = None

    def token_for(user_id: uuid.UUID, ttl_seconds: int = 3600) -> str:
        now = int(time.time())
        return jwt.encode(
            {"sub": str(user_id), "iat": now, "exp": now + ttl_seconds, "type": "access"},
            private,
            algorithm="EdDSA",
        )

    yield (private, token_for)


@pytest_asyncio.fixture
async def http_client(
    engine: AsyncEngine,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> AsyncIterator[AsyncClient]:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            try:
                yield s
            finally:
                try:
                    await s.commit()
                except Exception:
                    await s.rollback()

    app.dependency_overrides[get_session] = _override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


def _body(**overrides: Any) -> dict[str, Any]:
    return {
        "category": "pipl",
        "contact_email": "legal-contact@example.com",
        "company_name": "ACME Optimization",
        "subject": "PIPL DPA review",
        "message": "Please review our data processing and export obligations for procurement.",
        "urgency": "normal",
        **overrides,
    }


async def _create_user(
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> tuple[uuid.UUID, dict[str, str]]:
    _, token_for = token_factory
    user_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO users (id, phone, email, created_at, updated_at)
            VALUES (:id, :phone, :email, NOW(), NOW())
            """
        ),
        {
            "id": user_id,
            "phone": f"+86legal{user_id.hex[:8]}",
            "email": f"legal-{user_id.hex[:10]}@opticloud.test",
        },
    )
    await session.commit()
    return user_id, {"Authorization": f"Bearer {token_for(user_id)}"}


async def _subscribe(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    plan_code: str,
    status: str = "active",
    period_end: datetime | None = None,
) -> uuid.UUID:
    subscription_id = uuid.uuid4()
    now = datetime.now(UTC).replace(microsecond=0)
    resolved_period_end = period_end or now + timedelta(days=29)
    period_start = now - timedelta(days=1)
    if resolved_period_end <= period_start:
        period_start = resolved_period_end - timedelta(days=30)
    await session.execute(
        text(
            """
            INSERT INTO billing_subscriptions
                (id, user_id, plan_code, status, current_period_start, current_period_end,
                 metadata, created_at, updated_at)
            VALUES
                (:id, :user_id, :plan_code, :status, :period_start, :period_end,
                 '{}'::jsonb, NOW(), NOW())
            """
        ),
        {
            "id": subscription_id,
            "user_id": user_id,
            "plan_code": plan_code,
            "status": status,
            "period_start": period_start,
            "period_end": resolved_period_end,
        },
    )
    await session.commit()
    return subscription_id


async def _post_inquiry(
    http_client: AsyncClient,
    headers: dict[str, str],
    *,
    body: dict[str, Any] | None = None,
    key: str | None = None,
) -> tuple[int, dict[str, Any]]:
    response = await http_client.post(
        "/v1/legal/inquiry",
        json=body or _body(),
        headers={**headers, "Idempotency-Key": key or str(uuid.uuid4())},
    )
    return response.status_code, response.json()


async def _counts(session: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
    row = (
        (
            await session.execute(
                text(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM legal_inquiries WHERE user_id = :user_id) AS inquiries,
                        (SELECT COUNT(*) FROM outbox
                          WHERE aggregate_type = 'legal_inquiry'
                            AND aggregate_id IN (
                                SELECT id FROM legal_inquiries WHERE user_id = :user_id
                            )) AS outbox,
                        (SELECT COUNT(*) FROM billing_idempotency_keys
                          WHERE user_id = :user_id) AS idempotency
                    """
                ),
                {"user_id": user_id},
            )
        )
        .mappings()
        .one()
    )
    return {key: int(row[key]) for key in ("inquiries", "outbox", "idempotency")}


async def _stored_inquiry(session: AsyncSession, inquiry_id: str) -> dict[str, Any]:
    row = (
        (
            await session.execute(
                text(
                    """
                SELECT id, plan_code, category, contact_email, company_name, subject, message,
                       urgency, status, ticket_key, submitted_at, sla_due_at
                  FROM legal_inquiries
                 WHERE id = :id
                """
                ),
                {"id": uuid.UUID(inquiry_id)},
            )
        )
        .mappings()
        .one()
    )
    return dict(row)


async def _outbox_payload(session: AsyncSession, inquiry_id: str) -> dict[str, Any]:
    row = (
        (
            await session.execute(
                text(
                    """
                SELECT payload, headers
                  FROM outbox
                 WHERE aggregate_type = 'legal_inquiry'
                   AND aggregate_id = :id
                   AND event_type = 'legal.inquiry.submitted'
                """
                ),
                {"id": uuid.UUID(inquiry_id)},
            )
        )
        .mappings()
        .one()
    )
    return {"payload": row["payload"], "headers": row["headers"]}


async def test_team_plan_accepts_inquiry_with_24h_sla_and_safe_pointers(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    await _subscribe(session, user_id, plan_code="team")

    status_code, body = await _post_inquiry(http_client, headers)

    assert status_code == 201, body
    assert body["status"] == "submitted"
    assert body["sla_hours"] == 24
    assert body["linear_ticket"]["provider"] == "linear"
    assert body["linear_ticket"]["status"] == "pending"
    assert body["linear_ticket"]["reference"].startswith("OPTI-LEGAL-")
    forbidden_response_fields = {
        "subject",
        "message",
        "contact_email",
        "company_name",
        "user_id",
        "subscription_id",
        "request_body_hash",
    }
    assert forbidden_response_fields.isdisjoint(body)

    submitted_at = datetime.fromisoformat(body["submitted_at"].replace("Z", "+00:00"))
    sla_due_at = datetime.fromisoformat(body["sla_due_at"].replace("Z", "+00:00"))
    assert sla_due_at - submitted_at == timedelta(hours=24)

    inquiry = await _stored_inquiry(session, body["inquiry_id"])
    assert inquiry["plan_code"] == "team"
    assert inquiry["message"] == _body()["message"]
    assert inquiry["sla_due_at"] - inquiry["submitted_at"] == timedelta(hours=24)

    outbox = await _outbox_payload(session, body["inquiry_id"])
    assert outbox["payload"] == {
        "inquiry_id": body["inquiry_id"],
        "ticket_key": body["linear_ticket"]["reference"],
        "plan_code": "team",
        "category": "pipl",
        "urgency": "normal",
        "status": "submitted",
        "submitted_at": inquiry["submitted_at"].isoformat(),
        "sla_due_at": inquiry["sla_due_at"].isoformat(),
        "sla_hours": 24,
    }
    serialized_outbox = str(outbox).lower()
    for forbidden in (
        "please review",
        "pipl dpa",
        "legal-contact@example.com",
        "acme optimization",
        str(user_id),
        "jwt",
        "api_key",
        "phone",
    ):
        assert forbidden not in serialized_outbox
    assert await _counts(session, user_id) == {
        "inquiries": 1,
        "outbox": 1,
        "idempotency": 1,
    }


async def test_local_schema_backfill_keeps_legal_constraints_aligned(
    session: AsyncSession,
) -> None:
    rows = (
        (
            await session.execute(
                text(
                    """
                    SELECT conname
                      FROM pg_constraint
                     WHERE conrelid = 'legal_inquiries'::regclass
                       AND conname LIKE 'ck_legal_inquiries_%'
                    """
                )
            )
        )
        .scalars()
        .all()
    )

    assert set(rows) >= {
        "ck_legal_inquiries_plan_code",
        "ck_legal_inquiries_category",
        "ck_legal_inquiries_urgency",
        "ck_legal_inquiries_status",
        "ck_legal_inquiries_contact_email",
        "ck_legal_inquiries_company_name",
        "ck_legal_inquiries_subject",
        "ck_legal_inquiries_message",
        "ck_legal_inquiries_ticket_key",
        "ck_legal_inquiries_sla_due",
    }


async def test_enterprise_plan_accepts_urgent_inquiry(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    await _subscribe(session, user_id, plan_code="enterprise")

    status_code, body = await _post_inquiry(
        http_client,
        headers,
        body=_body(category="license", urgency="urgent"),
    )

    assert status_code == 201, body
    inquiry = await _stored_inquiry(session, body["inquiry_id"])
    assert inquiry["plan_code"] == "enterprise"
    assert inquiry["category"] == "license"
    assert inquiry["urgency"] == "urgent"


@pytest.mark.parametrize("plan_code", ["free", "starter", "pro"])
async def test_non_team_plus_plans_are_rejected_without_mutation(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
    plan_code: str,
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    await _subscribe(session, user_id, plan_code=plan_code)

    status_code, body = await _post_inquiry(http_client, headers)

    assert status_code == 403, body
    assert body["title"] == "Team plan required"
    assert await _counts(session, user_id) == {"inquiries": 0, "outbox": 0, "idempotency": 0}


async def test_implicit_free_without_subscription_is_rejected_without_mutation(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)

    status_code, body = await _post_inquiry(http_client, headers)

    assert status_code == 403, body
    assert body["title"] == "Team plan required"
    assert await _counts(session, user_id) == {"inquiries": 0, "outbox": 0, "idempotency": 0}


@pytest.mark.parametrize(
    ("status", "period_end"),
    [
        ("canceled", datetime.now(UTC) + timedelta(days=5)),
        ("expired", datetime.now(UTC) + timedelta(days=5)),
        ("active", datetime.now(UTC) - timedelta(days=1)),
    ],
)
async def test_inactive_or_period_expired_team_subscription_rejected(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
    status: str,
    period_end: datetime,
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    await _subscribe(session, user_id, plan_code="team", status=status, period_end=period_end)

    status_code, body = await _post_inquiry(http_client, headers)

    assert status_code == 403, body
    assert await _counts(session, user_id) == {"inquiries": 0, "outbox": 0, "idempotency": 0}


async def test_inquiry_idempotency_replay_returns_cached_response_without_duplicate_rows(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    await _subscribe(session, user_id, plan_code="team")
    key = str(uuid.uuid4())

    first_status, first_body = await _post_inquiry(http_client, headers, key=key)
    replay_status, replay_body = await _post_inquiry(http_client, headers, key=key)

    assert first_status == 201, first_body
    assert replay_status == 201, replay_body
    assert replay_body == first_body
    assert await _counts(session, user_id) == {"inquiries": 1, "outbox": 1, "idempotency": 1}


async def test_concurrent_same_key_replay_does_not_duplicate_or_500(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    await _subscribe(session, user_id, plan_code="team")
    key = str(uuid.uuid4())

    first, second = await asyncio.gather(
        http_client.post(
            "/v1/legal/inquiry",
            json=_body(),
            headers={**headers, "Idempotency-Key": key},
        ),
        http_client.post(
            "/v1/legal/inquiry",
            json=_body(),
            headers={**headers, "Idempotency-Key": key},
        ),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json() == second.json()
    assert await _counts(session, user_id) == {"inquiries": 1, "outbox": 1, "idempotency": 1}


async def test_inquiry_same_key_different_body_conflicts_without_mutation(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    await _subscribe(session, user_id, plan_code="team")
    key = str(uuid.uuid4())
    first_status, first_body = await _post_inquiry(http_client, headers, key=key)

    conflict_status, conflict_body = await _post_inquiry(
        http_client,
        headers,
        key=key,
        body=_body(subject="A different legal question"),
    )

    assert first_status == 201, first_body
    assert conflict_status == 409, conflict_body
    assert conflict_body["title"] == "Idempotency Conflict"
    assert await _counts(session, user_id) == {"inquiries": 1, "outbox": 1, "idempotency": 1}


async def test_cross_tenant_idempotency_key_reuse_never_returns_owner_response(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    owner_id, owner_headers = await _create_user(session, token_factory)
    await _subscribe(session, owner_id, plan_code="team")
    other_id, other_headers = await _create_user(session, token_factory)
    await _subscribe(session, other_id, plan_code="team")
    key = str(uuid.uuid4())
    first_status, first_body = await _post_inquiry(http_client, owner_headers, key=key)

    reuse_status, reuse_body = await _post_inquiry(http_client, other_headers, key=key)

    assert first_status == 201, first_body
    assert reuse_status == 403, reuse_body
    assert reuse_body["title"] == "Cross-tenant key reuse forbidden"
    assert first_body["inquiry_id"] not in str(reuse_body)
    assert await _counts(session, owner_id) == {"inquiries": 1, "outbox": 1, "idempotency": 1}
    assert await _counts(session, other_id) == {"inquiries": 0, "outbox": 0, "idempotency": 0}


async def test_expired_idempotency_row_can_be_replaced_by_new_inquiry(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    await _subscribe(session, user_id, plan_code="team")
    key = str(uuid.uuid4())
    first_status, first_body = await _post_inquiry(http_client, headers, key=key)
    await session.execute(
        text("UPDATE billing_idempotency_keys SET expires_at = :past WHERE key = :key"),
        {"past": datetime.now(UTC) - timedelta(seconds=1), "key": key},
    )
    await session.commit()

    second_status, second_body = await _post_inquiry(
        http_client,
        headers,
        key=key,
        body=_body(subject="Second accepted inquiry after idempotency expiry"),
    )

    assert first_status == 201, first_body
    assert second_status == 201, second_body
    assert second_body["inquiry_id"] != first_body["inquiry_id"]
    assert await _counts(session, user_id) == {"inquiries": 2, "outbox": 2, "idempotency": 1}


async def test_validation_rejects_extra_fields_bad_email_and_missing_idempotency_key(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    await _subscribe(session, user_id, plan_code="team")

    extra = await http_client.post(
        "/v1/legal/inquiry",
        json=_body(raw_body="forbidden"),
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    bad_email = await http_client.post(
        "/v1/legal/inquiry",
        json=_body(contact_email="not-an-email"),
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    missing_key = await http_client.post("/v1/legal/inquiry", json=_body(), headers=headers)
    invalid_key = await http_client.post(
        "/v1/legal/inquiry",
        json=_body(),
        headers={**headers, "Idempotency-Key": "not-a-uuid"},
    )
    trimmed_short_subject = await http_client.post(
        "/v1/legal/inquiry",
        json=_body(subject="  a  "),
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    trimmed_short_message = await http_client.post(
        "/v1/legal/inquiry",
        json=_body(message="   short  "),
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )

    assert extra.status_code == 422, extra.text
    assert bad_email.status_code == 422, bad_email.text
    assert missing_key.status_code == 422, missing_key.text
    assert invalid_key.status_code == 400, invalid_key.text
    assert invalid_key.json()["title"] == "Invalid Idempotency-Key"
    assert trimmed_short_subject.status_code == 422, trimmed_short_subject.text
    assert trimmed_short_message.status_code == 422, trimmed_short_message.text
    assert await _counts(session, user_id) == {"inquiries": 0, "outbox": 0, "idempotency": 0}


async def test_billing_prefixed_legal_path_is_not_registered(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    await _subscribe(session, user_id, plan_code="team")

    response = await http_client.post(
        "/v1/billing/legal/inquiry",
        json=_body(),
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )

    assert response.status_code == 404
    assert await _counts(session, user_id) == {"inquiries": 0, "outbox": 0, "idempotency": 0}
