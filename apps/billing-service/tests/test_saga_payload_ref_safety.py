from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from billing_service.exceptions import UnsafeSagaPayloadRefError
from billing_service.models import SagaInstance
from billing_service.saga_orchestrator import SagaOrchestrator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def orch(session: AsyncSession) -> SagaOrchestrator:
    return SagaOrchestrator(session)


async def test_start_rejects_unsafe_payload_ref_before_persisting(
    orch: SagaOrchestrator,
    test_user_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    """5.A.0 AC1 — unsafe refs fail before saga/idempotency rows are written."""
    key = f"unsafe-{uuid.uuid4()}"

    with pytest.raises(UnsafeSagaPayloadRefError):
        await orch.start(
            "solve_charge",
            test_user_id,
            key,
            {"reference_id": str(uuid.uuid4()), "amount": "6.00"},
            amount=Decimal("6.00"),
        )

    result = await session.execute(select(SagaInstance).where(SagaInstance.idempotency_key == key))
    assert result.scalar_one_or_none() is None


async def test_start_accepts_safe_pointer_payload_ref(
    orch: SagaOrchestrator,
    test_user_id: uuid.UUID,
) -> None:
    """5.A.0 AC1 — string pointer refs remain valid."""
    saga = await orch.start(
        "solve_charge",
        test_user_id,
        f"safe-{uuid.uuid4()}",
        {
            "reference_id": str(uuid.uuid4()),
            "purpose": "solve",
            "confirmation_ref": "precharge-confirmed",
        },
        amount=Decimal("6.00"),
    )

    assert saga.payload_ref["purpose"] == "solve"
