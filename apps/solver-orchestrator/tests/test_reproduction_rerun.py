"""Story 6.B.3 — rerun within 5 years regression tests."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from solver_orchestrator import billing_client
from solver_orchestrator.config import settings
from solver_orchestrator.db import get_session
from solver_orchestrator.main import app
from solver_orchestrator.models import IdempotencyKey, Optimization, ReproductionVoucher
from solver_orchestrator.repro import generate_reproduction_voucher_id
from solver_orchestrator.routes import (
    _add_calendar_years_utc,
    _is_rerun_voucher_expired,
    _voucher_expiry_utc,
)
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


DATABASE_URL = os.getenv("DATABASE_URL", settings.database_url)

_LP_BODY = {
    "task_type": "lp",
    "minimize": {"c": [1.0, 1.0]},
    "st": {"A": [[1.0, 1.0]], "b": [10.0]},
}


def _make_api_key() -> tuple[str, str, int]:
    random_part = uuid.uuid4().hex
    full = f"sk-{random_part}"
    pepper_version = 1
    pepper = settings.api_key_hmac_pepper_dev.encode("utf-8")
    key_hash = hmac.new(pepper, full.encode("utf-8"), hashlib.sha256).hexdigest()
    return full, key_hash, pepper_version


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine():
    eng = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def api_key(db_engine) -> AsyncIterator[tuple[str, uuid.UUID]]:
    user_id = uuid.uuid4()
    key_id = uuid.uuid4()
    full, key_hash, version = _make_api_key()
    key_prefix = full[:6]

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO users(id, email, phone, created_at, updated_at) "
                "VALUES (:id, :email, :phone, :now, :now) "
                "ON CONFLICT(id) DO NOTHING"
            ),
            {
                "id": user_id,
                "email": f"6b3-{user_id}@example.com",
                "phone": f"+861{user_id.int % 10**10:010d}",
                "now": datetime.now(UTC),
            },
        )
        await s.execute(
            text(
                "INSERT INTO api_keys(id, user_id, label, key_prefix, key_hash, pepper_version, "
                "scope, created_at, expires_at) VALUES "
                "(:id, :uid, :label, :prefix, :hash, :v, ARRAY['optimize:write'], :now, :exp)"
            ),
            {
                "id": key_id,
                "uid": user_id,
                "label": "6b3-test",
                "prefix": key_prefix,
                "hash": key_hash,
                "v": version,
                "now": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(days=365),
            },
        )
        await s.commit()

    yield (f"Bearer {full}", user_id)


@pytest_asyncio.fixture(loop_scope="session")
async def client_with_db(db_engine) -> AsyncIterator[AsyncClient]:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)

    async def _override() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            try:
                yield s
            finally:
                try:
                    await s.commit()
                except Exception:
                    await s.rollback()

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _lp_payload() -> dict[str, object]:
    return {
        **_LP_BODY,
        "options": {"reproducible": True},
    }


def _anonymous_lp_payload() -> dict[str, object]:
    return {
        **_LP_BODY,
        "options": {"reproducible": True, "anonymous": True},
    }


def _disable_billing(monkeypatch) -> None:
    async def _boom(*args, **kwargs):
        raise AssertionError("billing helper should not be called")

    monkeypatch.setattr(billing_client, "reserve", _boom)
    monkeypatch.setattr(billing_client, "finalize", _boom)


async def _count_rows(db_engine) -> dict[str, int]:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        optimizations = (
            await s.execute(select(func.count()).select_from(Optimization))
        ).scalar_one()
        vouchers = (
            await s.execute(select(func.count()).select_from(ReproductionVoucher))
        ).scalar_one()
        idempotency = (
            await s.execute(select(func.count()).select_from(IdempotencyKey))
        ).scalar_one()
    return {
        "optimizations": optimizations,
        "vouchers": vouchers,
        "idempotency": idempotency,
    }


async def _seed_reproducible_run(
    client_with_db: AsyncClient,
    auth: str,
    monkeypatch,
) -> dict[str, object]:
    _disable_billing(monkeypatch)
    resp = await client_with_db.post(
        "/v1/optimizations",
        json=_lp_payload(),
        headers={"Authorization": auth},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert "reproducibility" in body
    return body


async def _seed_anonymous_reproducible_run(
    client_with_db: AsyncClient,
    auth: str,
    monkeypatch,
) -> dict[str, object]:
    _disable_billing(monkeypatch)
    resp = await client_with_db.post(
        "/v1/optimizations",
        json=_anonymous_lp_payload(),
        headers={"Authorization": auth},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["reproducibility"]["anonymous"] is True
    return body


async def _seed_user(
    db_engine,
    *,
    label: str,
) -> tuple[str, uuid.UUID, uuid.UUID]:
    user_id = uuid.uuid4()
    key_id = uuid.uuid4()
    full, key_hash, version = _make_api_key()
    key_prefix = full[:6]

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                "INSERT INTO users(id, email, phone, created_at, updated_at) "
                "VALUES (:id, :email, :phone, :now, :now)"
            ),
            {
                "id": user_id,
                "email": f"{label}-{user_id}@example.com",
                "phone": f"+861{user_id.int % 10**10:010d}",
                "now": datetime.now(UTC),
            },
        )
        await s.execute(
            text(
                "INSERT INTO api_keys(id, user_id, label, key_prefix, key_hash, pepper_version, "
                "scope, created_at, expires_at) VALUES "
                "(:id, :uid, :label, :prefix, :hash, :v, ARRAY['optimize:write'], :now, :exp)"
            ),
            {
                "id": key_id,
                "uid": user_id,
                "label": label,
                "prefix": key_prefix,
                "hash": key_hash,
                "v": version,
                "now": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(days=365),
            },
        )
        await s.commit()

    return f"Bearer {full}", user_id, key_id


async def _seed_manual_rerun_candidate(
    db_engine,
    *,
    auth_user_id: uuid.UUID,
    auth_key_id: uuid.UUID,
    task_type: str = "lp",
    optimization_status: str = "completed",
    voucher_status: str = "issued",
    created_at: datetime | None = None,
    locked_solver: str | None = None,
) -> tuple[Optimization, ReproductionVoucher]:
    now = created_at or datetime.now(UTC)
    opt = Optimization(
        user_id=auth_user_id,
        api_key_id=auth_key_id,
        task_type=task_type,
        status=optimization_status,
        input_payload={
            "task_type": task_type,
            "st": {"A": [[1.0]], "b": [1.0]},
            "minimize": {"c": [1.0]},
        },
        model_version={
            "provider_id": "highs" if task_type == "lp" else "chronos-t5",
            "kind": "open_source",
            "version": "1.7.0",
            "provider_url": "https://highs.dev/",
        },
        solution={"x": [0.0]},
        objective=0.0,
        solve_seconds=0.01,
        created_at=now,
        completed_at=now if optimization_status == "completed" else None,
    )
    opt.id = uuid.uuid4()

    voucher = ReproductionVoucher(
        voucher_id=generate_reproduction_voucher_id(now),
        optimization_id=opt.id,
        parent_voucher_id=None,
        rerun_depth=0,
        user_id=auth_user_id,
        api_key_id=auth_key_id,
        request_fingerprint=f"sha256:{uuid.uuid4().hex}",
        locked_model_version=dict(opt.model_version or {}),
        locked_solver=locked_solver or ("highs" if task_type == "lp" else "chronos-t5"),
        seed_locked=True,
        seed=None,
        status=voucher_status,
        created_at=now,
    )
    if voucher_status != "issued":
        voucher.status = voucher_status

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        s.add(opt)
        await s.flush()
        s.add(voucher)
        await s.commit()

    return opt, voucher


async def test_rerun_success_creates_linked_voucher_and_preserves_source(
    client_with_db: AsyncClient, api_key, db_engine, monkeypatch
) -> None:
    auth, _user_id = api_key
    source = await _seed_reproducible_run(client_with_db, auth, monkeypatch)
    source_voucher_id = source["reproducibility"]["voucher_id"]
    source_opt_id = source["optimization_id"]

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        before_source = (
            await s.execute(
                text("SELECT input_payload, status FROM optimizations WHERE id = :id"),
                {"id": uuid.UUID(source_opt_id)},
            )
        ).one()
        counts_before = await _count_rows(db_engine)

    resp = await client_with_db.post(
        f"/v1/reproduce/{source_voucher_id}/rerun",
        headers={"Authorization": auth},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rerun_of_voucher_id"] == source_voucher_id
    assert body["source_optimization_id"] == source_opt_id
    assert body["reproducibility"]["voucher_id"] != source_voucher_id
    assert body["archive_restore"]["mode"] == "live_solver_image_reuse"

    rerun_voucher_id = body["reproducibility"]["voucher_id"]

    async with maker() as s:
        rerun_opt = (
            await s.execute(
                select(Optimization).where(Optimization.id == uuid.UUID(body["optimization_id"]))
            )
        ).scalar_one()
        rerun_voucher = (
            await s.execute(
                select(ReproductionVoucher).where(
                    ReproductionVoucher.voucher_id == rerun_voucher_id
                )
            )
        ).scalar_one()
        source_after = (
            await s.execute(
                text("SELECT input_payload, status FROM optimizations WHERE id = :id"),
                {"id": uuid.UUID(source_opt_id)},
            )
        ).one()
        counts_after = await _count_rows(db_engine)

    assert rerun_opt.status == "completed"
    assert rerun_voucher.parent_voucher_id is not None
    assert rerun_voucher.rerun_depth == 1
    assert rerun_voucher.optimization_id == rerun_opt.id
    assert rerun_voucher.voucher_id == rerun_voucher_id
    assert before_source[0] == source_after[0]
    assert before_source[1] == source_after[1]
    assert counts_after["optimizations"] == counts_before["optimizations"] + 1
    assert counts_after["vouchers"] == counts_before["vouchers"] + 1


async def test_rerun_of_anonymous_voucher_preserves_anonymous_lineage(
    client_with_db: AsyncClient, api_key, db_engine, monkeypatch
) -> None:
    """Story 6.B.4 — rerun child vouchers inherit anonymous mode."""
    auth, _user_id = api_key
    source = await _seed_anonymous_reproducible_run(client_with_db, auth, monkeypatch)
    source_voucher_id = source["reproducibility"]["voucher_id"]

    resp = await client_with_db.post(
        f"/v1/reproduce/{source_voucher_id}/rerun",
        headers={"Authorization": auth},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    repro = body["reproducibility"]
    assert repro["anonymous"] is True
    assert body["rerun_of_voucher_id"] == source_voucher_id
    assert "email" not in str(body).lower()
    assert "phone" not in str(body).lower()
    assert "bank_account" not in str(body).lower()
    assert "id_card" not in str(body).lower()

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        child = (
            await s.execute(
                select(ReproductionVoucher).where(
                    ReproductionVoucher.voucher_id == repro["voucher_id"]
                )
            )
        ).scalar_one()
        source_voucher = (
            await s.execute(
                select(ReproductionVoucher).where(
                    ReproductionVoucher.voucher_id == source_voucher_id
                )
            )
        ).scalar_one()
    assert source_voucher.anonymous is True
    assert child.anonymous is True
    assert child.parent_voucher_id == source_voucher.id
    assert child.rerun_depth == source_voucher.rerun_depth + 1


async def test_rerun_idempotency_replays_same_voucher_and_rejects_other_target(
    client_with_db: AsyncClient, api_key, db_engine, monkeypatch
) -> None:
    auth, _user_id = api_key
    source_a = await _seed_reproducible_run(client_with_db, auth, monkeypatch)
    source_b = await _seed_reproducible_run(client_with_db, auth, monkeypatch)
    key = f"rerun-{uuid.uuid4()}"
    headers = {"Authorization": auth, "Idempotency-Key": key}

    first = await client_with_db.post(
        f"/v1/reproduce/{source_a['reproducibility']['voucher_id']}/rerun",
        headers=headers,
    )
    assert first.status_code == 200, first.text
    first_body = first.json()
    counts_after_first = await _count_rows(db_engine)

    second = await client_with_db.post(
        f"/v1/reproduce/{source_a['reproducibility']['voucher_id']}/rerun",
        headers=headers,
    )
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert second_body["optimization_id"] == first_body["optimization_id"]
    assert (
        second_body["reproducibility"]["voucher_id"] == first_body["reproducibility"]["voucher_id"]
    )

    third = await client_with_db.post(
        f"/v1/reproduce/{source_b['reproducibility']['voucher_id']}/rerun",
        headers=headers,
    )
    assert third.status_code == 409, third.text
    assert third.json()["title"] == "Idempotency Conflict"

    counts_after_third = await _count_rows(db_engine)
    assert counts_after_third == counts_after_first


async def test_rerun_idempotency_key_is_scoped_per_user(
    client_with_db: AsyncClient, api_key, db_engine, monkeypatch
) -> None:
    auth_a, _ = api_key
    auth_b, _, _ = await _seed_user(db_engine, label="6b3-same-idem")
    source_a = await _seed_reproducible_run(client_with_db, auth_a, monkeypatch)
    source_b = await _seed_reproducible_run(client_with_db, auth_b, monkeypatch)
    key = f"rerun-shared-{uuid.uuid4()}"
    counts_before = await _count_rows(db_engine)

    first = await client_with_db.post(
        f"/v1/reproduce/{source_a['reproducibility']['voucher_id']}/rerun",
        headers={"Authorization": auth_a, "Idempotency-Key": key},
    )
    assert first.status_code == 200, first.text

    second = await client_with_db.post(
        f"/v1/reproduce/{source_b['reproducibility']['voucher_id']}/rerun",
        headers={"Authorization": auth_b, "Idempotency-Key": key},
    )
    assert second.status_code == 200, second.text
    assert second.json()["optimization_id"] != first.json()["optimization_id"]

    counts_after = await _count_rows(db_engine)
    assert counts_after["optimizations"] == counts_before["optimizations"] + 2
    assert counts_after["vouchers"] == counts_before["vouchers"] + 2
    assert counts_after["idempotency"] == counts_before["idempotency"] + 2


async def test_rerun_returns_404_for_unknown_and_cross_user_vouchers(
    client_with_db: AsyncClient, api_key, db_engine, monkeypatch
) -> None:
    auth, _ = api_key
    await _seed_reproducible_run(client_with_db, auth, monkeypatch)

    unknown = await client_with_db.post(
        "/v1/reproduce/repro-2026-AAAAAA/rerun",
        headers={"Authorization": auth},
    )
    assert unknown.status_code == 404, unknown.text

    other_auth, _, _ = await _seed_user(db_engine, label="6b3-other")
    other_source = await _seed_reproducible_run(client_with_db, other_auth, monkeypatch)
    cross_user = await client_with_db.post(
        f"/v1/reproduce/{other_source['reproducibility']['voucher_id']}/rerun",
        headers={"Authorization": auth},
    )
    assert cross_user.status_code == 404, cross_user.text


async def test_rerun_expired_and_boundary_helpers(
    client_with_db: AsyncClient, api_key, db_engine, monkeypatch
) -> None:
    auth, user_id = api_key
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row = (
            await s.execute(
                text("SELECT id FROM api_keys WHERE user_id = :uid LIMIT 1"), {"uid": user_id}
            )
        ).first()
        assert row is not None
        key_id = row[0]

    _, expired_voucher = await _seed_manual_rerun_candidate(
        db_engine,
        auth_user_id=user_id,
        auth_key_id=key_id,
        created_at=datetime(2020, 5, 21, tzinfo=UTC),
    )
    expired = await client_with_db.post(
        f"/v1/reproduce/{expired_voucher.voucher_id}/rerun",
        headers={"Authorization": auth},
    )
    assert expired.status_code == 410, expired.text
    assert expired.json()["title"] == "Voucher Expired"

    boundary = datetime(2026, 5, 21, tzinfo=UTC)
    expiry = _voucher_expiry_utc(boundary)
    assert expiry == datetime(2031, 5, 21, tzinfo=UTC)
    assert _is_rerun_voucher_expired(boundary, now=expiry.replace(microsecond=0)) is True
    assert _is_rerun_voucher_expired(boundary, now=expiry - datetime.resolution) is False
    assert _add_calendar_years_utc(datetime(2024, 2, 29, 12, tzinfo=UTC), 5) == datetime(
        2029, 2, 28, 12, tzinfo=UTC
    )


async def test_rerun_rejects_non_empty_body_and_does_not_write_rows(
    client_with_db: AsyncClient, api_key, db_engine, monkeypatch
) -> None:
    auth, _ = api_key
    source = await _seed_reproducible_run(client_with_db, auth, monkeypatch)
    counts_before = await _count_rows(db_engine)

    resp = await client_with_db.post(
        f"/v1/reproduce/{source['reproducibility']['voucher_id']}/rerun",
        json={"unexpected": True},
        headers={"Authorization": auth},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["title"] == "Invalid Rerun Body"

    counts_after = await _count_rows(db_engine)
    assert counts_after == counts_before


async def test_rerun_rejects_revoked_and_non_completed_source_rows(
    client_with_db: AsyncClient, api_key, db_engine, monkeypatch
) -> None:
    auth, user_id = api_key
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        key_id = (
            await s.execute(
                text("SELECT id FROM api_keys WHERE user_id = :uid LIMIT 1"), {"uid": user_id}
            )
        ).scalar_one()

    _, revoked_voucher = await _seed_manual_rerun_candidate(
        db_engine,
        auth_user_id=user_id,
        auth_key_id=key_id,
        voucher_status="revoked",
    )
    before_revoked = await _count_rows(db_engine)
    revoked = await client_with_db.post(
        f"/v1/reproduce/{revoked_voucher.voucher_id}/rerun",
        headers={"Authorization": auth},
    )
    assert revoked.status_code == 409, revoked.text
    assert revoked.json()["title"] == "Rerun Not Allowed"
    assert await _count_rows(db_engine) == before_revoked

    _, pending_voucher = await _seed_manual_rerun_candidate(
        db_engine,
        auth_user_id=user_id,
        auth_key_id=key_id,
        optimization_status="failed",
    )
    before_pending = await _count_rows(db_engine)
    pending = await client_with_db.post(
        f"/v1/reproduce/{pending_voucher.voucher_id}/rerun",
        headers={"Authorization": auth},
    )
    assert pending.status_code == 409, pending.text
    assert pending.json()["title"] == "Rerun Not Allowed"
    assert await _count_rows(db_engine) == before_pending

    _, unsupported_voucher = await _seed_manual_rerun_candidate(
        db_engine,
        auth_user_id=user_id,
        auth_key_id=key_id,
        task_type="forecast",
    )
    before_unsupported = await _count_rows(db_engine)
    unsupported = await client_with_db.post(
        f"/v1/reproduce/{unsupported_voucher.voucher_id}/rerun",
        headers={"Authorization": auth},
    )
    assert unsupported.status_code == 501, unsupported.text
    assert unsupported.json()["title"] == "Not Implemented"
    assert await _count_rows(db_engine) == before_unsupported


async def test_rerun_rejects_unavailable_locked_solver_without_new_rows(
    client_with_db: AsyncClient, api_key, db_engine
) -> None:
    auth, user_id = api_key
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        key_id = (
            await s.execute(
                text("SELECT id FROM api_keys WHERE user_id = :uid LIMIT 1"), {"uid": user_id}
            )
        ).scalar_one()

    _, voucher = await _seed_manual_rerun_candidate(
        db_engine,
        auth_user_id=user_id,
        auth_key_id=key_id,
        locked_solver="custom-lp-solver",
    )
    before = await _count_rows(db_engine)

    resp = await client_with_db.post(
        f"/v1/reproduce/{voucher.voucher_id}/rerun",
        headers={"Authorization": auth},
    )
    assert resp.status_code == 501, resp.text
    assert resp.json()["title"] == "Not Implemented"
    assert await _count_rows(db_engine) == before


async def test_rerun_does_not_call_billing_helpers(
    client_with_db: AsyncClient, api_key, monkeypatch
) -> None:
    auth, _ = api_key
    source = await _seed_reproducible_run(client_with_db, auth, monkeypatch)

    _disable_billing(monkeypatch)
    resp = await client_with_db.post(
        f"/v1/reproduce/{source['reproducibility']['voucher_id']}/rerun",
        headers={"Authorization": auth},
    )
    assert resp.status_code == 200, resp.text


async def test_rerun_rejects_billing_header_without_writing_rows(
    client_with_db: AsyncClient, api_key, db_engine, monkeypatch
) -> None:
    auth, _ = api_key
    source = await _seed_reproducible_run(client_with_db, auth, monkeypatch)
    counts_before = await _count_rows(db_engine)

    _disable_billing(monkeypatch)
    resp = await client_with_db.post(
        f"/v1/reproduce/{source['reproducibility']['voucher_id']}/rerun",
        headers={
            "Authorization": auth,
            "X-Billing-Charge-Id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["title"] == "Invalid X-Billing-Charge-Id"
    assert await _count_rows(db_engine) == counts_before
