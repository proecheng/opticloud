"""Critical scenarios — transition matrix coverage (M2.2a T2).

18 scenarios: 7 happy-path + 7 wrong-state + 4 terminal.
Each scenario maps to CRITICAL_SCENARIOS.md row.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from billing_service.exceptions import (
    InvalidSagaTransitionError,
    SagaTerminalError,
)
from billing_service.models import CreditTransaction, OutboxEvent, SagaInstance
from billing_service.saga_orchestrator import SagaOrchestrator
from opticloud_shared.saga import TERMINAL_STATES, TRANSITIONS, State
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def orch(session: AsyncSession) -> SagaOrchestrator:
    return SagaOrchestrator(session)


async def _drive_to_state(
    orch: SagaOrchestrator,
    user_id: uuid.UUID,
    target_state: State,
    amount: Decimal = Decimal("5"),
) -> SagaInstance:
    """Helper: create a Saga and step through valid transitions to reach `target_state`."""
    saga = await orch.start(
        "solve_charge", user_id, f"to-{target_state.value}-{uuid.uuid4()}", {}, amount=amount
    )
    if target_state == State.PENDING:
        return saga
    if target_state == State.FAILED:
        return await orch.apply(saga.id, "balance_insufficient")
    saga = await orch.apply(saga.id, "reserve")
    if target_state == State.RESERVED:
        return saga
    if target_state == State.REFUNDED:
        return await orch.apply(saga.id, "user_cancel")
    saga = await orch.apply(saga.id, "service_success")
    if target_state == State.CHARGED:
        return saga
    if target_state == State.COMPLETED:
        return await orch.apply(saga.id, "outbox_delivered")
    if target_state == State.ROLLED_BACK:
        return await orch.apply(saga.id, "downstream_reject_late")
    raise AssertionError(f"unreachable: {target_state}")


# ===== AC2 — happy-path transitions (7 scenarios via parametrize) =====


@pytest.mark.parametrize(
    "from_state,trigger,to_state",
    [(t.from_state, t.trigger, t.to_state) for t in TRANSITIONS],
    ids=[f"{t.from_state.value}->{t.to_state.value}:{t.trigger}" for t in TRANSITIONS],
)
async def test_happy_transition(
    orch: SagaOrchestrator,
    test_user_id: uuid.UUID,
    session: AsyncSession,
    from_state: State,
    trigger: str,
    to_state: State,
) -> None:
    """Each row of the transition matrix advances state and writes 1 outbox row."""
    saga = await _drive_to_state(orch, test_user_id, from_state, amount=Decimal("6"))
    starting_outbox = (
        await session.execute(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.aggregate_id == saga.id)
        )
    ).scalar_one()

    saga = await orch.apply(saga.id, trigger)
    assert saga.current_state == to_state.value

    # D: outbox row written with expected event_type
    ev = (
        await session.execute(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == saga.id,
                OutboxEvent.event_type == f"billing.saga.{trigger}",
            )
        )
    ).scalar_one_or_none()
    assert ev is not None
    assert ev.payload["from_state"] == from_state.value
    assert ev.payload["to_state"] == to_state.value

    # E: outbox count increased by exactly 1
    new_outbox = (
        await session.execute(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.aggregate_id == saga.id)
        )
    ).scalar_one()
    assert new_outbox == starting_outbox + 1


# ===== Wrong-state — 7 scenarios =====


@pytest.mark.parametrize(
    "wrong_state,trigger",
    [
        (State.CHARGED, "reserve"),
        (State.PENDING, "service_success"),
        (State.PENDING, "user_cancel"),
        (State.CHARGED, "user_cancel"),
        (State.PENDING, "outbox_delivered"),
        (State.RESERVED, "outbox_delivered"),
        (State.RESERVED, "downstream_reject_late"),
    ],
    ids=lambda v: v if isinstance(v, str) else v.value,
)
async def test_wrong_state_raises(
    orch: SagaOrchestrator,
    test_user_id: uuid.UUID,
    wrong_state: State,
    trigger: str,
) -> None:
    """Applying a trigger when current_state can't accept it raises (or no-ops if terminal-stickiness applies)."""
    saga = await _drive_to_state(orch, test_user_id, wrong_state)
    with pytest.raises((InvalidSagaTransitionError, SagaTerminalError)):
        await orch.apply(saga.id, trigger)


# ===== Terminal stickiness — 4 scenarios =====


@pytest.mark.parametrize("terminal_state", list(TERMINAL_STATES), ids=lambda s: s.value)
async def test_terminal_state_rejects_any_trigger(
    orch: SagaOrchestrator,
    test_user_id: uuid.UUID,
    terminal_state: State,
) -> None:
    """All 4 terminal states reject any further apply()."""
    saga = await _drive_to_state(orch, test_user_id, terminal_state)
    with pytest.raises(SagaTerminalError):
        await orch.apply(saga.id, "reserve")


# ===== Edge value tests (AC6) =====


async def test_amount_equal_to_balance_succeeds(
    orch: SagaOrchestrator, test_user_id: uuid.UUID, session: AsyncSession
) -> None:
    """Charge of exactly available balance reaches CHARGED."""
    # Use a fresh user so balance is predictable
    fresh_user = uuid.uuid4()
    # Insert seed: 7.00 CNY
    await session.execute(
        select(CreditTransaction).limit(0)  # warm up
    )
    from sqlalchemy import text

    await session.execute(
        text(
            "INSERT INTO users (id, phone, email, created_at, updated_at) "
            "VALUES (:id, :phone, :email, NOW(), NOW())"
        ),
        {
            "id": fresh_user,
            "phone": f"+86-test-{fresh_user.hex[:10]}",
            "email": f"test-{fresh_user.hex[:10]}@opticloud.test",
        },
    )
    session.add(
        CreditTransaction(
            user_id=fresh_user,
            saga_id=None,
            amount=Decimal("7.00"),
            kind="topup",
            currency="CNY",
            metadata_json={"src": "test"},
            created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        )
    )
    await session.commit()

    saga = await orch.start(
        "solve_charge", fresh_user, f"eq-{uuid.uuid4()}", {}, amount=Decimal("7.00")
    )
    await orch.apply(saga.id, "reserve")
    saga = await orch.apply(saga.id, "service_success")
    assert saga.current_state == State.CHARGED.value


async def test_amount_at_max_numeric_precision(
    orch: SagaOrchestrator, test_user_id: uuid.UUID
) -> None:
    """NUMERIC(12,4) accepts up to 99999999.9999 — orchestrator does not reject."""
    saga = await orch.start(
        "solve_charge",
        test_user_id,
        f"max-{uuid.uuid4()}",
        {},
        amount=Decimal("99999999.9999"),
    )
    # Saga starts PENDING — orchestrator doesn't check balance until reserve
    assert saga.current_state == State.PENDING.value
    assert saga.amount == Decimal("99999999.9999")


async def test_amount_minimum_positive(orch: SagaOrchestrator, test_user_id: uuid.UUID) -> None:
    """Decimal('0.0001') is the smallest valid amount (1 of 4 fractional digits)."""
    saga = await orch.start(
        "solve_charge", test_user_id, f"min-{uuid.uuid4()}", {}, amount=Decimal("0.0001")
    )
    assert saga.amount == Decimal("0.0001")


async def test_idempotent_replay_reserved_reserve_is_noop(
    orch: SagaOrchestrator, test_user_id: uuid.UUID, session: AsyncSession
) -> None:
    """AC10: re-applying `reserve` after Saga is already RESERVED is a no-op."""
    saga = await _drive_to_state(orch, test_user_id, State.RESERVED, amount=Decimal("1"))
    same = await orch.apply(saga.id, "reserve")
    assert same.current_state == State.RESERVED.value
    # Only ONE outbox row for "reserve"
    count = (
        await session.execute(
            select(func.count())
            .select_from(OutboxEvent)
            .where(
                OutboxEvent.aggregate_id == saga.id,
                OutboxEvent.event_type == "billing.saga.reserve",
            )
        )
    ).scalar_one()
    assert count == 1


async def test_saga_created_at_less_than_updated_at(
    orch: SagaOrchestrator, test_user_id: uuid.UUID
) -> None:
    """saga.created_at <= saga.updated_at after any apply() (monotonic timestamps)."""
    saga = await orch.start(
        "solve_charge", test_user_id, f"ts-{uuid.uuid4()}", {}, amount=Decimal("1")
    )
    initial_created = saga.created_at
    initial_updated = saga.updated_at
    assert initial_created == initial_updated

    saga = await orch.apply(saga.id, "balance_insufficient")
    assert saga.updated_at >= initial_updated
