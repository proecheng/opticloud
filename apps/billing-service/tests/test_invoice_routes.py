"""Story 5.D.1 — bilingual invoice route tests."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
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
    """Generate test keypair and return (private, token_for(user_id)) helper."""
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
            {
                "sub": str(user_id),
                "iat": now,
                "exp": now + ttl_seconds,
                "type": "access",
            },
            private,
            algorithm="EdDSA",
        )

    yield (private, token_for)


@pytest_asyncio.fixture
async def http_client(
    engine: AsyncEngine,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> AsyncIterator[AsyncClient]:
    """ASGI test client with DI override for DB session."""
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
            "phone": f"+86inv{user_id.hex[:10]}",
            "email": f"invoice-{user_id.hex[:10]}@opticloud.test",
        },
    )
    await session.commit()
    return user_id, {"Authorization": f"Bearer {token_for(user_id)}"}


async def _insert_subscription(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    plan_code: str = "starter",
    period_start: datetime = datetime(2026, 5, 1, tzinfo=UTC),
    period_end: datetime = datetime(2026, 6, 1, tzinfo=UTC),
) -> uuid.UUID:
    subscription_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO billing_subscriptions
                (id, user_id, plan_code, status, current_period_start, current_period_end,
                 last_refilled_period_start, metadata, created_at, updated_at)
            VALUES
                (:id, :user_id, :plan_code, 'active', :period_start, :period_end,
                 :period_start, '{}'::jsonb, NOW(), NOW())
            """
        ),
        {
            "id": subscription_id,
            "user_id": user_id,
            "plan_code": plan_code,
            "period_start": period_start,
            "period_end": period_end,
        },
    )
    await session.commit()
    return subscription_id


async def _insert_ledger(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    amount: str,
    kind: str,
    created_at: datetime,
    bucket: str = "monthly",
    metadata: str = "{}",
) -> uuid.UUID:
    transaction_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO credit_transactions
                (id, user_id, saga_id, amount, kind, bucket, currency, metadata, created_at)
            VALUES
                (:id, :user_id, NULL, :amount, :kind, :bucket, 'CNY',
                 CAST(:metadata AS jsonb), :created_at)
            """
        ),
        {
            "id": transaction_id,
            "user_id": user_id,
            "amount": amount,
            "kind": kind,
            "bucket": bucket,
            "metadata": metadata,
            "created_at": created_at,
        },
    )
    await session.commit()
    return transaction_id


async def _counts(session: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
    row = (
        (
            await session.execute(
                text(
                    """
                SELECT
                    (SELECT COUNT(*) FROM credit_transactions WHERE user_id = :user_id) AS tx,
                    (SELECT COUNT(*) FROM billing_subscriptions WHERE user_id = :user_id) AS subs,
                    (SELECT COUNT(*) FROM billing_idempotency_keys WHERE user_id = :user_id) AS idem,
                    (SELECT COUNT(*) FROM outbox) AS outbox
                """
                ),
                {"user_id": user_id},
            )
        )
        .mappings()
        .one()
    )
    return {key: int(row[key]) for key in ("tx", "subs", "idem", "outbox")}


async def test_invoice_detail_aggregates_bilingual_statement_and_safe_ledger(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    subscription_id = await _insert_subscription(session, user_id)
    await _insert_ledger(
        session,
        user_id,
        amount="2000.00",
        kind="monthly_refill",
        created_at=datetime(2026, 5, 1, 0, 0, tzinfo=UTC),
        metadata=f'{{"subscription_id":"{subscription_id}","plan_code":"starter","trigger":"activation"}}',
    )
    await _insert_ledger(
        session,
        user_id,
        amount="-6.00",
        kind="charge",
        created_at=datetime(2026, 5, 10, 3, 0, tzinfo=UTC),
        metadata='{"reason":"solver_success","raw_body":"must-not-leak"}',
    )
    await _insert_ledger(
        session,
        user_id,
        amount="5.50",
        kind="refund_partial",
        created_at=datetime(2026, 5, 10, 3, 1, tzinfo=UTC),
        metadata='{"reason":"elapsed < cap","payment_ref":"must-not-leak"}',
    )
    await _insert_ledger(
        session,
        user_id,
        amount="10.00",
        kind="topup",
        bucket="topup",
        created_at=datetime(2026, 5, 20, 4, 0, tzinfo=UTC),
        metadata='{"payment_ref":"pay_secret_001","provider":"manual","email":"bad@example.test"}',
    )
    await _insert_ledger(
        session,
        user_id,
        amount="1.25",
        kind="adjustment",
        created_at=datetime(2026, 5, 21, 4, 0, tzinfo=UTC),
        metadata='{"reason":"manual-review"}',
    )

    response = await http_client.get("/v1/billing/invoices/2026-05", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["period"] == "2026-05"
    assert body["owner_user_id_suffix"] == str(user_id)[-8:]
    assert body["title"]["zh"] == "OptiCloud 账单明细"
    assert body["title"]["en"] == "OptiCloud Billing Statement"
    assert body["tax_disclaimer"]["zh"] == "非税务发票"
    assert body["tax_disclaimer"]["en"] == "Not a tax invoice"
    assert body["subscription"]["plan_code"] == "starter"
    assert body["net_credit_movement"] == "2010.75"
    assert body["credit_subtotal"] == "2016.75"
    assert body["debit_subtotal"] == "6.00"
    assert body["actual_spend"] == "0.50"
    assert body["trend_contract"] == "invoice_summary"
    assert [item["kind"] for item in body["line_items"]] == [
        "monthly_refill",
        "charge",
        "refund_partial",
        "topup",
        "adjustment",
    ]
    assert body["line_items"][-1]["label"]["en"] == "Other adjustment"
    body_text = str(body).lower()
    assert "raw_body" not in body_text
    assert "pay_secret_001" not in body_text
    assert "bad@example.test" not in body_text


async def test_invoice_period_boundaries_are_utc_and_owner_scoped(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    owner_id, owner_headers = await _create_user(session, token_factory)
    other_id, _other_headers = await _create_user(session, token_factory)
    await _insert_ledger(
        session,
        owner_id,
        amount="1.00",
        kind="monthly_refill",
        created_at=datetime(2026, 5, 1, 0, 0, tzinfo=UTC),
    )
    await _insert_ledger(
        session,
        owner_id,
        amount="9.00",
        kind="monthly_refill",
        created_at=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
    )
    await _insert_ledger(
        session,
        other_id,
        amount="99.00",
        kind="monthly_refill",
        created_at=datetime(2026, 5, 15, 0, 0, tzinfo=UTC),
    )

    response = await http_client.get("/v1/billing/invoices/2026-05", headers=owner_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["net_credit_movement"] == "1.00"
    assert len(body["line_items"]) == 1
    assert body["line_items"][0]["source_amount"] == "1.0000"
    assert "99.00" not in str(body)


async def test_invoice_errors_and_reads_are_status_safe_and_read_only(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    await _insert_ledger(
        session,
        user_id,
        amount="2.00",
        kind="monthly_refill",
        created_at=datetime(2026, 5, 2, 0, 0, tzinfo=UTC),
    )
    before = await _counts(session, user_id)

    malformed = await http_client.get("/v1/billing/invoices/2026-13", headers=headers)
    missing = await http_client.get("/v1/billing/invoices/2026-04", headers=headers)
    ok = await http_client.get("/v1/billing/invoices/2026-05", headers=headers)
    after = await _counts(session, user_id)

    assert malformed.status_code == 400, malformed.text
    assert malformed.json()["title"] == "Invalid Invoice Period"
    assert missing.status_code == 404, missing.text
    assert missing.json()["title"] == "Invoice Not Found"
    assert ok.status_code == 200, ok.text
    assert after == before


async def test_invoice_list_orders_available_periods_newest_first(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    await _insert_ledger(
        session,
        user_id,
        amount="1.00",
        kind="monthly_refill",
        created_at=datetime(2026, 4, 15, tzinfo=UTC),
    )
    await _insert_ledger(
        session,
        user_id,
        amount="2.00",
        kind="monthly_refill",
        created_at=datetime(2026, 5, 15, tzinfo=UTC),
    )

    response = await http_client.get("/v1/billing/invoices", headers=headers)

    assert response.status_code == 200, response.text
    assert [item["period"] for item in response.json()["items"]][:2] == ["2026-05", "2026-04"]


async def test_invoice_pdf_download_is_real_pdf_and_does_not_leak_forbidden_fields(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    await _insert_ledger(
        session,
        user_id,
        amount="-6.00",
        kind="charge",
        created_at=datetime(2026, 5, 10, tzinfo=UTC),
        metadata='{"raw_payload":"secret","jwt":"token","api_key":"sk-test","payment_ref":"pay-secret"}',
    )

    response = await http_client.get("/v1/billing/invoices/2026-05/download", headers=headers)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    assert 'filename="opticloud-invoice-2026-05.pdf"' in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")
    assert b"Billing Statement" in response.content
    assert b"Not a tax invoice" in response.content
    assert b"2026-05" in response.content
    assert b"secret" not in response.content.lower()
    assert b"sk-test" not in response.content
    assert b"pay-secret" not in response.content


async def test_invoice_pdf_download_includes_all_line_items_across_pages(
    http_client: AsyncClient,
    session: AsyncSession,
    token_factory: tuple[Ed25519PrivateKey, Callable[[uuid.UUID], str]],
) -> None:
    user_id, headers = await _create_user(session, token_factory)
    start = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    for index in range(60):
        await _insert_ledger(
            session,
            user_id,
            amount="-0.10",
            kind="charge",
            created_at=start + timedelta(minutes=index),
        )

    response = await http_client.get("/v1/billing/invoices/2026-05/download", headers=headers)

    assert response.status_code == 200, response.text
    assert response.content.startswith(b"%PDF")
    assert response.content.count(b"Usage charge") == 60
    assert b"net=-6.00" in response.content
