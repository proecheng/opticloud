"""Story 6.B.2 — reproduction voucher ID contract tests."""

from __future__ import annotations

import asyncio
import os
import re
import sys
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from solver_orchestrator.config import settings
from solver_orchestrator.models import Optimization, ReproductionVoucher
from solver_orchestrator.repro import (
    VOUCHER_ID_PATTERN,
    generate_reproduction_voucher_id,
    issue_reproduction_voucher,
)
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


DATABASE_URL = os.getenv("DATABASE_URL", settings.database_url)


def _fresh_voucher_id(issued_at: datetime, *, used: set[str] | None = None) -> str:
    used = used if used is not None else set()
    voucher_id = generate_reproduction_voucher_id(issued_at)
    while voucher_id in used:
        voucher_id = generate_reproduction_voucher_id(issued_at)
    used.add(voucher_id)
    return voucher_id


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine():
    eng = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    yield eng
    await eng.dispose()


def _completed_repro_optimization() -> Optimization:
    now = datetime.now(UTC)
    opt = Optimization(
        user_id=uuid.uuid4(),
        api_key_id=uuid.uuid4(),
        task_type="lp",
        status="completed",
        input_payload={
            "task_type": "lp",
            "_system": {
                "reproducibility": {
                    "requested": True,
                    "request_fingerprint": f"sha256:{uuid.uuid4().hex}",
                    "locked_model_version": {
                        "provider_id": "highs",
                        "kind": "open_source",
                        "version": "1.7.0",
                        "provider_url": "https://highs.dev/",
                    },
                    "locked_solver": "highs",
                    "seed_locked": True,
                    "seed": None,
                }
            },
        },
        solution={"x": [0.0]},
        objective=0.0,
        model_version={
            "provider_id": "highs",
            "kind": "open_source",
            "version": "1.7.0",
            "provider_url": "https://highs.dev/",
        },
        solve_seconds=0.01,
        created_at=now,
        completed_at=now,
    )
    opt.id = uuid.uuid4()
    return opt


def _voucher_row(
    *,
    opt: Optimization,
    voucher_id: str,
    created_at: datetime,
    status: str = "issued",
    request_fingerprint: str = "sha256:test",
    parent_voucher_id: uuid.UUID | None = None,
    rerun_depth: int = 0,
) -> ReproductionVoucher:
    return ReproductionVoucher(
        voucher_id=voucher_id,
        optimization_id=opt.id,
        parent_voucher_id=parent_voucher_id,
        rerun_depth=rerun_depth,
        user_id=opt.user_id,
        api_key_id=opt.api_key_id,
        request_fingerprint=request_fingerprint,
        locked_model_version=dict(opt.model_version or {}),
        locked_solver="highs",
        seed_locked=True,
        seed=None,
        status=status,
        created_at=created_at,
    )


def test_generate_reproduction_voucher_id_uses_contract_format() -> None:
    voucher_id = generate_reproduction_voucher_id(datetime(2026, 5, 21, tzinfo=UTC))

    assert VOUCHER_ID_PATTERN.fullmatch(voucher_id)
    assert voucher_id.startswith("repro-2026-")
    suffix = voucher_id.removeprefix("repro-2026-")
    assert len(suffix) == 6
    assert re.fullmatch(r"[0123456789ABCDEFGHJKMNPQRSTVWXYZ]{6}", suffix)
    assert not (set(suffix) & {"I", "L", "O", "U"})


async def test_issue_reproduction_voucher_retries_on_voucher_id_collision(db_engine) -> None:
    issued_at = datetime(2026, 5, 21, tzinfo=UTC)
    used_ids: set[str] = set()
    duplicate_id = _fresh_voucher_id(issued_at, used=used_ids)
    replacement_id = _fresh_voucher_id(issued_at, used=used_ids)
    calls: list[str] = []

    def _factory(_: datetime) -> str:
        calls.append("call")
        return duplicate_id if len(calls) == 1 else replacement_id

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        existing_opt = _completed_repro_optimization()
        target_opt = _completed_repro_optimization()
        session.add_all([existing_opt, target_opt])
        await session.flush()
        session.add(
            _voucher_row(
                opt=existing_opt,
                voucher_id=duplicate_id,
                created_at=issued_at,
                request_fingerprint="sha256:existing",
            )
        )
        await session.flush()

        voucher_id = await issue_reproduction_voucher(
            session,
            target_opt,
            issued_at=issued_at,
            voucher_id_factory=_factory,
        )
        await session.commit()

    assert voucher_id == replacement_id
    assert len(calls) == 2

    async with maker() as session:
        row = (
            await session.execute(
                text(
                    "SELECT voucher_id FROM reproduction_vouchers "
                    "WHERE optimization_id = :optimization_id"
                ),
                {"optimization_id": target_opt.id},
            )
        ).scalar_one()
    assert row == replacement_id


async def test_reproduction_vouchers_enforce_database_constraints(db_engine) -> None:
    """Story 6.B.2 — the table itself rejects invalid voucher shape and status."""
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    issued_at = datetime(2026, 5, 21, tzinfo=UTC)

    async with maker() as session:
        opt = _completed_repro_optimization()
        session.add(opt)
        await session.flush()
        session.add(_voucher_row(opt=opt, voucher_id="repro-2026-IL0OU1", created_at=issued_at))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    async with maker() as session:
        opt = _completed_repro_optimization()
        session.add(opt)
        await session.flush()
        session.add(
            _voucher_row(
                opt=opt,
                voucher_id=_fresh_voucher_id(issued_at),
                created_at=issued_at,
                status="revoked",
            )
        )
        await session.flush()
        await session.rollback()

    async with maker() as session:
        opt = _completed_repro_optimization()
        session.add(opt)
        await session.flush()
        session.add(
            _voucher_row(
                opt=opt,
                voucher_id=_fresh_voucher_id(issued_at),
                created_at=issued_at,
                rerun_depth=-1,
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()
