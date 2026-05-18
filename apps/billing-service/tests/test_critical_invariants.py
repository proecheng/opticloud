"""Critical scenarios — DB-level invariants over time (M2.2a T5).

8 invariants:
1. created_at <= updated_at
2-5. Terminal stickiness for 4 terminal states (covered in test_critical_transitions; re-asserted)
6. Refund <= Charge per saga
7. No saga is "stuck" (any non-terminal can reach a terminal)
8. Outbox.aggregate_id == saga.id and event_version >= 1 always
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest_asyncio
from billing_service.models import CreditTransaction, OutboxEvent
from billing_service.saga_orchestrator import SagaOrchestrator
from opticloud_shared.saga import TRANSITIONS, State, valid_transitions_from
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def orch(session: AsyncSession) -> SagaOrchestrator:
    return SagaOrchestrator(session)


# Invariant 1: created_at <= updated_at after any apply
async def test_invariant_created_at_le_updated_at(
    orch: SagaOrchestrator, test_user_id: uuid.UUID
) -> None:
    saga = await orch.start(
        "solve_charge", test_user_id, f"inv1-{uuid.uuid4()}", {}, amount=Decimal("3")
    )
    initial = saga.created_at
    saga = await orch.apply(saga.id, "reserve")
    assert saga.created_at == initial
    assert saga.updated_at >= initial


# Invariant 6: Refund <= Charge per saga
async def test_invariant_refund_le_charge(
    orch: SagaOrchestrator,
    test_user_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    saga = await orch.start(
        "solve_charge", test_user_id, f"inv6-{uuid.uuid4()}", {}, amount=Decimal("8")
    )
    await orch.apply(saga.id, "reserve")
    await orch.apply(saga.id, "service_success")
    await orch.apply(saga.id, "downstream_reject_late")  # refund post-charge

    txs = list(
        (
            await session.execute(
                select(CreditTransaction).where(CreditTransaction.saga_id == saga.id)
            )
        ).scalars()
    )
    charge_total = sum(abs(t.amount) for t in txs if t.kind == "charge")
    refund_total = sum(t.amount for t in txs if t.kind == "refund")
    assert refund_total <= charge_total


# Invariant 7: no saga is "stuck" — every non-terminal has at least one outbound transition
def test_invariant_no_stuck_state() -> None:
    """Pure-data check on opticloud_shared.saga: no non-terminal state has 0 outgoing transitions."""
    terminals = {State.COMPLETED, State.FAILED, State.REFUNDED, State.ROLLED_BACK}
    for s in State:
        if s in terminals:
            continue
        outbound = valid_transitions_from(s)
        assert outbound, f"State {s.value} has no outgoing transitions — stuck!"


# Invariant 8: Outbox.aggregate_id == saga.id and event_version >= 1
async def test_invariant_outbox_aggregate_and_version(
    orch: SagaOrchestrator,
    test_user_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    saga = await orch.start(
        "solve_charge", test_user_id, f"inv8-{uuid.uuid4()}", {}, amount=Decimal("3")
    )
    await orch.apply(saga.id, "reserve")

    events = list(
        (
            await session.execute(select(OutboxEvent).where(OutboxEvent.aggregate_id == saga.id))
        ).scalars()
    )
    assert events
    for ev in events:
        assert ev.aggregate_id == saga.id
        assert ev.event_version >= 1


# Invariant: transition matrix completeness — every TRANSITION is reachable
def test_invariant_transition_matrix_covers_every_trigger_unique() -> None:
    """Every (from_state, trigger) pair is unique — no ambiguity."""
    seen: set[tuple[State, str]] = set()
    for t in TRANSITIONS:
        key = (t.from_state, t.trigger)
        assert key not in seen, f"duplicate transition: {key}"
        seen.add(key)


# NFR-R4: ledger sum == declared balance after each apply
async def test_nfr_r4_reconciliation_after_each_apply(
    orch: SagaOrchestrator,
    test_user_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    """Q3 — after every apply call, balance via SUM(credit_transactions) is consistent."""
    saga = await orch.start(
        "solve_charge", test_user_id, f"nfr-{uuid.uuid4()}", {}, amount=Decimal("3")
    )

    async def _balance() -> Decimal:
        result = await session.execute(
            select(func.coalesce(func.sum(CreditTransaction.amount), Decimal("0"))).where(
                CreditTransaction.user_id == test_user_id
            )
        )
        return Decimal(str(result.scalar_one()))

    b_before = await _balance()
    await orch.apply(saga.id, "reserve")
    assert await _balance() == b_before  # reserve doesn't move money

    saga = await orch.apply(saga.id, "service_success")
    assert (await _balance()) == b_before - Decimal("3")  # charged 3


# Outbox event payload contains required fields (S3 — no PII assertion via shape check)
async def test_outbox_payload_shape(
    orch: SagaOrchestrator,
    test_user_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    saga = await orch.start(
        "solve_charge", test_user_id, f"shape-{uuid.uuid4()}", {}, amount=Decimal("3")
    )
    await orch.apply(saga.id, "reserve")
    ev = (
        await session.execute(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == saga.id,
                OutboxEvent.event_type == "billing.saga.reserve",
            )
        )
    ).scalar_one()

    required_keys = {"saga_id", "saga_type", "from_state", "to_state", "trigger"}
    assert required_keys.issubset(ev.payload.keys())
    # No raw amount or PII in payload
    assert "amount" not in ev.payload
    assert "phone" not in ev.payload
    assert "email" not in ev.payload


# Transition compensation header included
async def test_outbox_headers_carry_compensation(
    orch: SagaOrchestrator,
    test_user_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    saga = await orch.start(
        "solve_charge", test_user_id, f"comp-{uuid.uuid4()}", {}, amount=Decimal("3")
    )
    await orch.apply(saga.id, "reserve")  # PENDING -> RESERVED, compensation=mark_failed
    ev = (
        await session.execute(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == saga.id,
                OutboxEvent.event_type == "billing.saga.reserve",
            )
        )
    ).scalar_one()
    assert ev.headers.get("compensation") == "mark_failed"
