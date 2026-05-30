from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from billing_service.exceptions import IdempotencyConflictError
from billing_service.models import CreditTransaction, OutboxEvent
from billing_service.saga_orchestrator import SagaOrchestrator
from opticloud_shared.saga.contract_fixtures import (
    CONTRACT_FIXTURE_MANIFEST,
    SagaContractFixture,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

EXECUTABLE_FIXTURES = CONTRACT_FIXTURE_MANIFEST.executable_fixtures


async def _ledger_delta(session: AsyncSession, saga_id: uuid.UUID) -> Decimal:
    result = await session.execute(
        select(func.coalesce(func.sum(CreditTransaction.amount), Decimal("0"))).where(
            CreditTransaction.saga_id == saga_id
        )
    )
    return Decimal(str(result.scalar_one())).quantize(Decimal("0.0001"))


async def _outbox_count(session: AsyncSession, saga_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count()).select_from(OutboxEvent).where(OutboxEvent.aggregate_id == saga_id)
    )
    return int(result.scalar_one())


@pytest.mark.parametrize("fixture", EXECUTABLE_FIXTURES, ids=lambda f: f.fixture_id)
async def test_executable_contract_fixture_runs_against_orchestrator(
    fixture: SagaContractFixture,
    session: AsyncSession,
    test_user_id: uuid.UUID,
) -> None:
    """Shared executable fixtures must match the DB-backed SagaOrchestrator."""
    orch = SagaOrchestrator(session)
    key = f"{fixture.idempotency_key}-{uuid.uuid4()}"

    saga = await orch.start(
        fixture.saga_type,
        test_user_id,
        key,
        fixture.payload_ref,
        amount=fixture.amount,
    )

    if fixture.idempotency_case == "same_body_replay":
        replay = await orch.start(
            fixture.saga_type,
            test_user_id,
            key,
            fixture.payload_ref,
            amount=fixture.amount,
        )
        assert replay.id == saga.id
    elif fixture.idempotency_case == "different_body_conflict":
        conflict_payload = {
            **fixture.payload_ref,
            "reference_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{fixture.fixture_id}:conflict")),
        }
        with pytest.raises(IdempotencyConflictError):
            await orch.start(
                fixture.saga_type,
                test_user_id,
                key,
                conflict_payload,
                amount=fixture.amount,
            )

    for step in fixture.steps:
        saga = await orch.apply(saga.id, step.trigger)

    assert saga.current_state == fixture.expected_final_state.value
    assert await _ledger_delta(session, saga.id) == fixture.expected_ledger_delta
    assert await _outbox_count(session, saga.id) == fixture.expected_outbox_count


def test_budget_pause_fixtures_are_not_executed_by_billing_service() -> None:
    """Unsupported paused_by_budget fixtures are documentation stubs for later stories."""
    stubs = [f for f in CONTRACT_FIXTURE_MANIFEST.fixtures if f.category == "budget_pause_stub"]
    assert stubs
    assert all(not f.executable for f in stubs)
