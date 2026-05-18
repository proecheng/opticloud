"""Integration tests for SagaOrchestrator (Story 5.A.0a AC7 + AC8 + AC10).

Requires a running Postgres with 03-billing-schema.sql applied.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from billing_service.exceptions import (
    IdempotencyConflictError,
    InvalidSagaTransitionError,
    SagaNotFoundError,
    SagaTerminalError,
)
from billing_service.models import CreditTransaction, OutboxEvent
from billing_service.saga_orchestrator import SagaOrchestrator
from opticloud_shared.saga import State
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def orch(session: AsyncSession) -> SagaOrchestrator:
    return SagaOrchestrator(session)


# ===== AC7: Happy path PENDING → RESERVED → CHARGED → COMPLETED =====


async def test_happy_path_full_lifecycle(
    orch: SagaOrchestrator,
    test_user_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    """AC7 happy path."""
    saga = await orch.start(
        saga_type="solve_charge",
        user_id=test_user_id,
        idempotency_key=f"happy-{uuid.uuid4()}",
        payload={"optimization_id": str(uuid.uuid4()), "task_type": "lp"},
        amount=Decimal("6.00"),
    )
    assert saga.current_state == State.PENDING.value

    saga = await orch.apply(saga.id, "reserve")
    assert saga.current_state == State.RESERVED.value

    saga = await orch.apply(saga.id, "service_success")
    assert saga.current_state == State.CHARGED.value

    saga = await orch.apply(saga.id, "outbox_delivered")
    assert saga.current_state == State.COMPLETED.value

    # 1 charge row in ledger (RESERVED -> CHARGED)
    result = await session.execute(
        select(CreditTransaction).where(CreditTransaction.saga_id == saga.id)
    )
    txs = list(result.scalars())
    assert len(txs) == 1
    assert txs[0].kind == "charge"
    assert txs[0].amount == Decimal("-6.0000")  # debit = negative

    # 4 outbox rows (reserve, service_success, outbox_delivered) — actually 4 includes reserve
    result = await session.execute(
        select(func.count()).select_from(OutboxEvent).where(OutboxEvent.aggregate_id == saga.id)
    )
    n = result.scalar_one()
    assert n == 3  # reserve + service_success + outbox_delivered


# ===== AC7 negative cases =====


async def test_invalid_trigger_raises(orch: SagaOrchestrator, test_user_id: uuid.UUID) -> None:
    saga = await orch.start("solve_charge", test_user_id, f"inv-{uuid.uuid4()}", {"x": 1})
    with pytest.raises(InvalidSagaTransitionError):
        await orch.apply(saga.id, "this_trigger_does_not_exist")


async def test_wrong_state_transition_raises(
    orch: SagaOrchestrator, test_user_id: uuid.UUID
) -> None:
    saga = await orch.start("solve_charge", test_user_id, f"wrong-{uuid.uuid4()}", {"x": 1})
    # PENDING does not accept "service_success" (that's RESERVED → CHARGED)
    with pytest.raises(InvalidSagaTransitionError):
        await orch.apply(saga.id, "service_success")


async def test_saga_not_found_raises(orch: SagaOrchestrator) -> None:
    with pytest.raises(SagaNotFoundError):
        await orch.apply(uuid.uuid4(), "reserve")


async def test_terminal_state_rejects_apply(
    orch: SagaOrchestrator, test_user_id: uuid.UUID
) -> None:
    saga = await orch.start("solve_charge", test_user_id, f"term-{uuid.uuid4()}", {"x": 1})
    await orch.apply(saga.id, "balance_insufficient")  # PENDING → FAILED (terminal)

    with pytest.raises(SagaTerminalError):
        await orch.apply(saga.id, "reserve")


# ===== AC8: Refund compensation =====


async def test_refund_compensation_writes_ledger_row(
    orch: SagaOrchestrator,
    test_user_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    saga = await orch.start(
        "solve_charge",
        test_user_id,
        f"refund-{uuid.uuid4()}",
        {"opt": "x"},
        amount=Decimal("10.00"),
    )
    await orch.apply(saga.id, "reserve")
    saga = await orch.apply(saga.id, "user_cancel")  # RESERVED → REFUNDED

    assert saga.current_state == State.REFUNDED.value

    result = await session.execute(
        select(CreditTransaction).where(CreditTransaction.saga_id == saga.id)
    )
    txs = list(result.scalars())
    assert len(txs) == 1
    assert txs[0].kind == "refund"
    assert txs[0].amount == Decimal("10.0000")  # refund = positive

    # Outbox event recorded
    result = await session.execute(
        select(OutboxEvent).where(
            OutboxEvent.aggregate_id == saga.id,
            OutboxEvent.event_type == "billing.saga.user_cancel",
        )
    )
    assert result.scalar_one_or_none() is not None


# ===== AC4: Idempotency =====


async def test_same_key_same_body_returns_same_saga(
    orch: SagaOrchestrator, test_user_id: uuid.UUID
) -> None:
    key = f"idem-{uuid.uuid4()}"
    body = {"optimization_id": "x", "task_type": "lp"}
    s1 = await orch.start("solve_charge", test_user_id, key, body, amount=Decimal("6"))
    s2 = await orch.start("solve_charge", test_user_id, key, body, amount=Decimal("6"))
    assert s1.id == s2.id


async def test_same_key_diff_body_raises_conflict(
    orch: SagaOrchestrator, test_user_id: uuid.UUID
) -> None:
    key = f"conf-{uuid.uuid4()}"
    await orch.start("solve_charge", test_user_id, key, {"a": 1}, amount=Decimal("6"))
    with pytest.raises(IdempotencyConflictError):
        await orch.start("solve_charge", test_user_id, key, {"a": 2}, amount=Decimal("6"))


# ===== AC10: apply() transition-idempotent =====


async def test_replaying_same_trigger_is_noop(
    orch: SagaOrchestrator,
    test_user_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    saga = await orch.start(
        "solve_charge",
        test_user_id,
        f"idem-apply-{uuid.uuid4()}",
        {"x": 1},
        amount=Decimal("6"),
    )
    await orch.apply(saga.id, "reserve")
    saga_again = await orch.apply(saga.id, "reserve")  # already RESERVED → no-op

    assert saga_again.current_state == State.RESERVED.value

    # Only 1 outbox row for "reserve" (not 2)
    result = await session.execute(
        select(func.count())
        .select_from(OutboxEvent)
        .where(
            OutboxEvent.aggregate_id == saga.id,
            OutboxEvent.event_type == "billing.saga.reserve",
        )
    )
    assert result.scalar_one() == 1
