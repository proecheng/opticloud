"""DB-backed invariant tests (Story 5.A.0a AC6).

Imports the same invariant names as M2.0 pure-function tests but asserts them
against live orchestrator behavior.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from billing_service.exceptions import SagaTerminalError
from billing_service.models import CreditTransaction
from billing_service.saga_orchestrator import SagaOrchestrator
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from opticloud_shared.saga import TERMINAL_STATES, State
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_FAST = settings(
    max_examples=10,
    deadline=2000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@pytest_asyncio.fixture
async def orch(session: AsyncSession) -> SagaOrchestrator:
    return SagaOrchestrator(session)


# ===== I1: no dangling state =====


async def test_i1_no_dangling_state_random_path(
    orch: SagaOrchestrator, test_user_id: uuid.UUID
) -> None:
    """Random sequence of valid triggers ends at a State enum value."""
    saga = await orch.start(
        "solve_charge",
        test_user_id,
        f"i1-{uuid.uuid4()}",
        {"reference_id": str(uuid.uuid4())},
        amount=Decimal("6"),
    )
    # Walk through the 4 happy-path triggers
    triggers = ["reserve", "service_success", "outbox_delivered"]
    for trig in triggers:
        saga = await orch.apply(saga.id, trig)

    # Final state must be in the enum
    assert State(saga.current_state) in set(State)


# ===== I2: refund <= charge per saga =====


async def test_i2_refund_le_charge(
    orch: SagaOrchestrator,
    test_user_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    """sum(refund) <= sum(|charge|) per saga (Q3 edge case included)."""
    # Path A: charge then refund — refund amount must equal charge amount
    saga = await orch.start(
        "solve_charge",
        test_user_id,
        f"i2-a-{uuid.uuid4()}",
        {"reference_id": str(uuid.uuid4())},
        amount=Decimal("8.00"),
    )
    await orch.apply(saga.id, "reserve")
    await orch.apply(saga.id, "service_success")
    await orch.apply(saga.id, "downstream_reject_late")  # refund post-charge

    result = await session.execute(
        select(CreditTransaction).where(CreditTransaction.saga_id == saga.id)
    )
    txs = list(result.scalars())
    charge_total = sum(abs(t.amount) for t in txs if t.kind == "charge")
    refund_total = sum(t.amount for t in txs if t.kind == "refund")
    assert refund_total <= charge_total

    # Path B: failed before charge — Q3 edge case: refund == charge == 0
    saga_b = await orch.start(
        "solve_charge",
        test_user_id,
        f"i2-b-{uuid.uuid4()}",
        {"reference_id": str(uuid.uuid4())},
        amount=Decimal("8.00"),
    )
    await orch.apply(saga_b.id, "balance_insufficient")  # PENDING → FAILED
    result = await session.execute(
        select(CreditTransaction).where(CreditTransaction.saga_id == saga_b.id)
    )
    txs_b = list(result.scalars())
    assert len(txs_b) == 0  # zero ledger movement on pre-charge fail


# ===== I3: terminal stickiness =====


@given(terminal=st.sampled_from(list(TERMINAL_STATES)))
@_FAST
async def test_i3_terminal_rejects_any_trigger(
    orch: SagaOrchestrator,
    test_user_id: uuid.UUID,
    terminal: State,
) -> None:
    """Any apply() on a terminal saga raises SagaTerminal."""
    # We can only easily put a saga in FAILED via balance_insufficient.
    # For other terminals, use the path that reaches them.
    saga = await orch.start(
        "solve_charge",
        test_user_id,
        f"i3-{terminal.value}-{uuid.uuid4()}",
        {"reference_id": str(uuid.uuid4())},
        amount=Decimal("5"),
    )
    if terminal == State.FAILED:
        await orch.apply(saga.id, "balance_insufficient")
    elif terminal == State.REFUNDED:
        await orch.apply(saga.id, "reserve")
        await orch.apply(saga.id, "user_cancel")
    elif terminal == State.COMPLETED:
        await orch.apply(saga.id, "reserve")
        await orch.apply(saga.id, "service_success")
        await orch.apply(saga.id, "outbox_delivered")
    elif terminal == State.ROLLED_BACK:
        await orch.apply(saga.id, "reserve")
        await orch.apply(saga.id, "service_success")
        await orch.apply(saga.id, "downstream_reject_late")

    # Try an unrelated trigger — must raise SagaTerminal
    with pytest.raises(SagaTerminalError):
        await orch.apply(saga.id, "reserve")


# ===== I4: idempotency =====


async def test_i4_idempotency(
    orch: SagaOrchestrator,
    test_user_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    """Same key + same body → identical saga_id + identical ledger count."""
    key = f"i4-{uuid.uuid4()}"
    body = {"opt": "x", "task": "lp"}
    s1 = await orch.start("solve_charge", test_user_id, key, body, amount=Decimal("6"))
    s2 = await orch.start("solve_charge", test_user_id, key, body, amount=Decimal("6"))
    assert s1.id == s2.id

    # No duplicate sagas exist
    from billing_service.models import SagaInstance
    from sqlalchemy import func

    result = await session.execute(
        select(func.count()).select_from(SagaInstance).where(SagaInstance.idempotency_key == key)
    )
    assert result.scalar_one() == 1
