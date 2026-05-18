"""Critical scenarios — outbox + audit verification (M2.2a T6).

6 scenarios verifying outbox events are correctly written, structured, and
named for M2.1 relayer consumption.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest_asyncio
from billing_service.models import OutboxEvent
from billing_service.saga_orchestrator import SagaOrchestrator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def orch(session: AsyncSession) -> SagaOrchestrator:
    return SagaOrchestrator(session)


# Scenario 1: each successful apply produces exactly 1 outbox row
async def test_each_apply_produces_one_outbox_row(
    orch: SagaOrchestrator, test_user_id: uuid.UUID, session: AsyncSession
) -> None:
    saga = await orch.start(
        "solve_charge", test_user_id, f"audit1-{uuid.uuid4()}", {}, amount=Decimal("3")
    )
    await orch.apply(saga.id, "reserve")
    count1 = (
        await session.execute(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.aggregate_id == saga.id)
        )
    ).scalar_one()
    assert count1 == 1

    await orch.apply(saga.id, "service_success")
    count2 = (
        await session.execute(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.aggregate_id == saga.id)
        )
    ).scalar_one()
    assert count2 == 2


# Scenario 2: multi-step happy path = exactly 3 outbox rows in order
async def test_happy_path_produces_three_outbox_rows_in_order(
    orch: SagaOrchestrator, test_user_id: uuid.UUID, session: AsyncSession
) -> None:
    saga = await orch.start(
        "solve_charge", test_user_id, f"audit2-{uuid.uuid4()}", {}, amount=Decimal("3")
    )
    await orch.apply(saga.id, "reserve")
    await orch.apply(saga.id, "service_success")
    await orch.apply(saga.id, "outbox_delivered")

    events = list(
        (
            await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.aggregate_id == saga.id)
                .order_by(OutboxEvent.occurred_at)
            )
        ).scalars()
    )
    assert len(events) == 3
    assert [e.event_type for e in events] == [
        "billing.saga.reserve",
        "billing.saga.service_success",
        "billing.saga.outbox_delivered",
    ]


# Scenario 3: refund path produces 1 outbox row for user_cancel transition
async def test_refund_produces_user_cancel_outbox(
    orch: SagaOrchestrator, test_user_id: uuid.UUID, session: AsyncSession
) -> None:
    saga = await orch.start(
        "solve_charge", test_user_id, f"audit3-{uuid.uuid4()}", {}, amount=Decimal("3")
    )
    await orch.apply(saga.id, "reserve")
    await orch.apply(saga.id, "user_cancel")

    cancel_event = (
        await session.execute(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == saga.id,
                OutboxEvent.event_type == "billing.saga.user_cancel",
            )
        )
    ).scalar_one_or_none()
    assert cancel_event is not None


# Scenario 4: outbox payload has saga_id / from_state / to_state / trigger; no PII
async def test_outbox_payload_no_pii(
    orch: SagaOrchestrator, test_user_id: uuid.UUID, session: AsyncSession
) -> None:
    saga = await orch.start(
        "solve_charge", test_user_id, f"audit4-{uuid.uuid4()}", {}, amount=Decimal("3")
    )
    await orch.apply(saga.id, "reserve")
    ev = (
        await session.execute(
            select(OutboxEvent).where(OutboxEvent.aggregate_id == saga.id).limit(1)
        )
    ).scalar_one()
    p = ev.payload
    assert {"saga_id", "from_state", "to_state", "trigger"}.issubset(p.keys())
    forbidden = {"amount", "phone", "email", "credit_card", "password"}
    assert not (forbidden & set(p.keys()))


# Scenario 5: outbox.headers carries compensation enum
async def test_outbox_headers_compensation_enum_value(
    orch: SagaOrchestrator, test_user_id: uuid.UUID, session: AsyncSession
) -> None:
    saga = await orch.start(
        "solve_charge", test_user_id, f"audit5-{uuid.uuid4()}", {}, amount=Decimal("3")
    )
    await orch.apply(saga.id, "balance_insufficient")  # PENDING -> FAILED, compensation=none
    ev = (
        await session.execute(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == saga.id,
                OutboxEvent.event_type == "billing.saga.balance_insufficient",
            )
        )
    ).scalar_one()
    # compensation values are lowercase strings from the Compensation enum
    assert ev.headers.get("compensation") in {
        "none",
        "mark_failed",
        "refund_auto",
        "retry_outbox",
        "escalate_ops",
    }


# Scenario 6: channel naming convention works for M2.1 relayer compatibility (A1 loose-match)
async def test_outbox_event_type_starts_with_billing_saga(
    orch: SagaOrchestrator, test_user_id: uuid.UUID, session: AsyncSession
) -> None:
    """Relayer derives channel as opticloud.{aggregate_type}.{event_type};
    event_type prefix `billing.saga.` is the contract for chat/audit consumers."""
    saga = await orch.start(
        "solve_charge", test_user_id, f"audit6-{uuid.uuid4()}", {}, amount=Decimal("3")
    )
    await orch.apply(saga.id, "reserve")
    ev = (
        await session.execute(
            select(OutboxEvent).where(OutboxEvent.aggregate_id == saga.id).limit(1)
        )
    ).scalar_one()
    assert ev.event_type.startswith("billing.saga.")
    assert ev.aggregate_type == "saga_instance"
