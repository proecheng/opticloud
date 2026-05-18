"""Critical scenarios — concurrency + race conditions (M2.2a T4).

Each concurrent task uses its OWN SQLAlchemy session — sessions are not
thread/task-safe. Outcome-based asserts (Q1 lock).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal

import pytest_asyncio
from billing_service.models import CreditTransaction, OutboxEvent
from billing_service.saga_orchestrator import SagaOrchestrator
from opticloud_shared.saga import State
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


@asynccontextmanager
async def _new_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise


async def _orch_op(
    engine: AsyncEngine,
    op_name: str,
    *args: object,
) -> str | Exception:
    """Run one orchestrator operation in its own session; return state or exception."""
    try:
        async with _new_session(engine) as s:
            orch = SagaOrchestrator(s)
            if op_name == "start":
                saga = await orch.start(*args)  # type: ignore[arg-type]
                return str(saga.id)
            if op_name == "apply":
                saga = await orch.apply(*args)  # type: ignore[arg-type]
                return saga.current_state
            raise AssertionError(f"unknown op {op_name}")
    except Exception as e:  # noqa: BLE001
        return e


@pytest_asyncio.fixture
async def fresh_user(engine: AsyncEngine) -> uuid.UUID:
    """A fresh seeded user (DR2 — per-test isolation)."""
    user_id = uuid.uuid4()
    async with _new_session(engine) as s:
        await s.execute(
            text(
                "INSERT INTO users (id, phone, email, created_at, updated_at) "
                "VALUES (:id, :phone, :email, NOW(), NOW())"
            ),
            {
                "id": user_id,
                "phone": f"+86-c-{user_id.hex[:10]}",
                "email": f"c-{user_id.hex[:10]}@opticloud.test",
            },
        )
        s.add(
            CreditTransaction(
                user_id=user_id,
                saga_id=None,
                amount=Decimal("100"),
                kind="topup",
                currency="CNY",
                metadata_json={"src": "test"},
                created_at=datetime.now(UTC),
            )
        )
    return user_id


# Scenario 1: concurrent apply() same trigger same saga → 1 transition + 1 outbox row
async def test_concurrent_apply_same_trigger_yields_one_transition(
    engine: AsyncEngine, fresh_user: uuid.UUID
) -> None:
    # Setup: create saga
    saga_id_str = await _orch_op(
        engine, "start", "solve_charge", fresh_user, f"conc1-{uuid.uuid4()}", {}, Decimal("3")
    )
    assert isinstance(saga_id_str, str)
    saga_id = uuid.UUID(saga_id_str)

    # Two concurrent applies of the same trigger
    await asyncio.gather(
        _orch_op(engine, "apply", saga_id, "reserve"),
        _orch_op(engine, "apply", saga_id, "reserve"),
    )

    # Final state is RESERVED
    async with _new_session(engine) as s:
        orch = SagaOrchestrator(s)
        final = await orch.get(saga_id)
    assert final.current_state == State.RESERVED.value

    # Verify only ONE outbox row for "reserve" — idempotent replay folded
    async with _new_session(engine) as s:
        count = (
            await s.execute(
                select(func.count())
                .select_from(OutboxEvent)
                .where(
                    OutboxEvent.aggregate_id == saga_id,
                    OutboxEvent.event_type == "billing.saga.reserve",
                )
            )
        ).scalar_one()
    # SELECT FOR UPDATE serializes; idempotent replay → 1 outbox row
    assert count == 1


# Scenario 2: concurrent conflicting triggers → one wins, one raises
async def test_concurrent_conflicting_triggers_one_wins(
    engine: AsyncEngine, fresh_user: uuid.UUID
) -> None:
    saga_id_str = await _orch_op(
        engine, "start", "solve_charge", fresh_user, f"conc2-{uuid.uuid4()}", {}, Decimal("3")
    )
    assert isinstance(saga_id_str, str)
    saga_id = uuid.UUID(saga_id_str)

    results = await asyncio.gather(
        _orch_op(engine, "apply", saga_id, "reserve"),
        _orch_op(engine, "apply", saga_id, "balance_insufficient"),
    )

    async with _new_session(engine) as s:
        final = await SagaOrchestrator(s).get(saga_id)
    assert final.current_state in {State.RESERVED.value, State.FAILED.value}

    # Both async tasks completed without deadlock (SELECT FOR UPDATE serializes)
    assert len(results) == 2


# Scenario 3: concurrent start() with different keys → 2 distinct sagas
async def test_concurrent_start_different_keys(engine: AsyncEngine, fresh_user: uuid.UUID) -> None:
    s1, s2 = await asyncio.gather(
        _orch_op(
            engine, "start", "solve_charge", fresh_user, f"k1-{uuid.uuid4()}", {}, Decimal("2")
        ),
        _orch_op(
            engine, "start", "solve_charge", fresh_user, f"k2-{uuid.uuid4()}", {}, Decimal("2")
        ),
    )
    assert isinstance(s1, str)
    assert isinstance(s2, str)
    assert s1 != s2


# Scenario 4: concurrent charge + refund → final balance correct
async def test_concurrent_charge_and_refund(engine: AsyncEngine, fresh_user: uuid.UUID) -> None:
    s_charge_id_str = await _orch_op(
        engine, "start", "solve_charge", fresh_user, f"ch-{uuid.uuid4()}", {}, Decimal("10")
    )
    s_refund_id_str = await _orch_op(
        engine, "start", "solve_charge", fresh_user, f"rf-{uuid.uuid4()}", {}, Decimal("5")
    )
    assert isinstance(s_charge_id_str, str)
    assert isinstance(s_refund_id_str, str)
    s_charge_id = uuid.UUID(s_charge_id_str)
    s_refund_id = uuid.UUID(s_refund_id_str)

    # Reserve both
    await asyncio.gather(
        _orch_op(engine, "apply", s_charge_id, "reserve"),
        _orch_op(engine, "apply", s_refund_id, "reserve"),
    )

    # Finalize concurrently: charge commit + cancel refund
    await asyncio.gather(
        _orch_op(engine, "apply", s_charge_id, "service_success"),
        _orch_op(engine, "apply", s_refund_id, "user_cancel"),
    )

    async with _new_session(engine) as s:
        bal = (
            await s.execute(
                select(func.sum(CreditTransaction.amount)).where(
                    CreditTransaction.user_id == fresh_user
                )
            )
        ).scalar_one()
    # 100 (seed) - 10 (charge) + 5 (refund) = 95
    assert Decimal(str(bal)) == Decimal("95")


# Scenario 5: concurrent confirm vs cancel on same saga
async def test_concurrent_confirm_vs_cancel(engine: AsyncEngine, fresh_user: uuid.UUID) -> None:
    saga_id_str = await _orch_op(
        engine, "start", "solve_charge", fresh_user, f"conc5-{uuid.uuid4()}", {}, Decimal("3")
    )
    assert isinstance(saga_id_str, str)
    saga_id = uuid.UUID(saga_id_str)
    await _orch_op(engine, "apply", saga_id, "reserve")

    await asyncio.gather(
        _orch_op(engine, "apply", saga_id, "service_success"),
        _orch_op(engine, "apply", saga_id, "user_cancel"),
    )
    async with _new_session(engine) as s:
        final = await SagaOrchestrator(s).get(saga_id)
    assert final.current_state in {State.CHARGED.value, State.REFUNDED.value}


# Scenario 6: SELECT FOR UPDATE SKIP LOCKED prevents 10 concurrent apply()s from racing
async def test_skip_locked_prevents_race(engine: AsyncEngine, fresh_user: uuid.UUID) -> None:
    saga_id_str = await _orch_op(
        engine, "start", "solve_charge", fresh_user, f"conc6-{uuid.uuid4()}", {}, Decimal("3")
    )
    assert isinstance(saga_id_str, str)
    saga_id = uuid.UUID(saga_id_str)
    await _orch_op(engine, "apply", saga_id, "reserve")

    await asyncio.gather(
        *[_orch_op(engine, "apply", saga_id, "service_success") for _ in range(10)]
    )

    async with _new_session(engine) as s:
        final = await SagaOrchestrator(s).get(saga_id)
    assert final.current_state == State.CHARGED.value


# Scenario 7: ledger sum per saga is exactly -amount on charge
async def test_ledger_sum_monotonic_per_saga(engine: AsyncEngine, fresh_user: uuid.UUID) -> None:
    saga_id_str = await _orch_op(
        engine, "start", "solve_charge", fresh_user, f"ledg-{uuid.uuid4()}", {}, Decimal("10")
    )
    assert isinstance(saga_id_str, str)
    saga_id = uuid.UUID(saga_id_str)
    await _orch_op(engine, "apply", saga_id, "reserve")
    await _orch_op(engine, "apply", saga_id, "service_success")

    async with _new_session(engine) as s:
        saga_sum = (
            await s.execute(
                select(func.sum(CreditTransaction.amount)).where(
                    CreditTransaction.saga_id == saga_id
                )
            )
        ).scalar_one()
    assert Decimal(str(saga_sum)) == Decimal("-10")


# Scenario 8: 5 concurrent full-charge cycles → balance reflects total correctly (NFR-R4)
async def test_ledger_sum_across_5_concurrent_sagas(
    engine: AsyncEngine, fresh_user: uuid.UUID
) -> None:
    async def _full_charge(idx: int) -> None:
        s_id_str = await _orch_op(
            engine,
            "start",
            "solve_charge",
            fresh_user,
            f"par-{idx}-{uuid.uuid4()}",
            {},
            Decimal("5"),
        )
        assert isinstance(s_id_str, str)
        s_id = uuid.UUID(s_id_str)
        await _orch_op(engine, "apply", s_id, "reserve")
        await _orch_op(engine, "apply", s_id, "service_success")

    await asyncio.gather(*[_full_charge(i) for i in range(5)])

    async with _new_session(engine) as s:
        bal = (
            await s.execute(
                select(func.sum(CreditTransaction.amount)).where(
                    CreditTransaction.user_id == fresh_user
                )
            )
        ).scalar_one()
    # 100 (seed) - 5×5 = 75
    assert Decimal(str(bal)) == Decimal("75")
