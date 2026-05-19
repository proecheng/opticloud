"""Reconciler tests — Story 5.A.7 (NFR-R4 hardening)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest_asyncio
from billing_service.models import CreditTransaction
from billing_service.reconciler import (
    DriftSeverity,
    classify_drift,
    expected_bounds,
    reconcile_window,
)
from billing_service.saga_orchestrator import SagaOrchestrator
from sqlalchemy.ext.asyncio import AsyncSession

# ===== Pure-function tests (no DB) =====


def test_classify_drift_thresholds() -> None:
    """AC6 #1 — thresholds: 0.005 → OK, 0.50 → MINOR, 1.50 → MAJOR, -2.00 → MAJOR."""
    assert classify_drift(Decimal("0.005")) == DriftSeverity.OK
    assert classify_drift(Decimal("0.00")) == DriftSeverity.OK
    assert classify_drift(Decimal("0.01")) == DriftSeverity.MINOR
    assert classify_drift(Decimal("0.50")) == DriftSeverity.MINOR
    assert classify_drift(Decimal("0.99")) == DriftSeverity.MINOR
    assert classify_drift(Decimal("1.00")) == DriftSeverity.MAJOR
    assert classify_drift(Decimal("1.50")) == DriftSeverity.MAJOR
    assert classify_drift(Decimal("-2.00")) == DriftSeverity.MAJOR


def test_expected_bounds_failed_refunded_rolled_back_all_zero() -> None:
    """AC2 — net-zero states all expect sum exactly = 0."""
    for state in ("failed", "refunded", "rolled_back"):
        lo, hi = expected_bounds(state, Decimal("6.00"))
        assert lo == Decimal("0") and hi == Decimal("0"), f"{state} not zero"


def test_expected_bounds_charged_completed_use_partial_range() -> None:
    """AC2 — charged/completed: sum ∈ [-A, -0.01]."""
    for state in ("charged", "completed"):
        lo, hi = expected_bounds(state, Decimal("6.00"))
        assert lo == Decimal("-6.00")
        assert hi == Decimal("-0.01")


# ===== DB-backed tests =====


@pytest_asyncio.fixture
async def orch(session: AsyncSession) -> SagaOrchestrator:
    return SagaOrchestrator(session)


async def test_reconcile_empty_window_returns_zero_diffs(
    session: AsyncSession,
) -> None:
    """AC6 #2 — empty window → 0 sagas, 0 diffs."""
    future_start = datetime.now(UTC) + timedelta(days=365)
    future_end = future_start + timedelta(hours=1)
    report = await reconcile_window(session, future_start, future_end)
    assert report.sagas_examined == 0
    assert report.diffs_found == 0
    assert report.results == []


async def test_reconcile_clean_completed_saga_reports_ok(
    orch: SagaOrchestrator,
    session: AsyncSession,
    test_user_id: uuid.UUID,
) -> None:
    """AC6 #3 — clean COMPLETED saga: ledger = -A, within bounds, no drift reported."""
    start_window = datetime.now(UTC) - timedelta(seconds=5)
    saga = await orch.start(
        "solve_charge",
        test_user_id,
        f"reco-clean-{uuid.uuid4()}",
        {"x": 1},
        amount=Decimal("6"),
    )
    await orch.apply(saga.id, "reserve")
    await orch.apply(saga.id, "service_success")
    await orch.apply(saga.id, "outbox_delivered")
    await session.commit()
    end_window = datetime.now(UTC) + timedelta(seconds=5)

    report = await reconcile_window(session, start_window, end_window)
    # Other tests may have left orchestrator-only refunded sagas (+A without R1.1
    # compensation) — those get flagged correctly. We only assert OUR saga is clean.
    saga_in_diffs = [r for r in report.results if r.saga_id == saga.id]
    assert saga_in_diffs == [], f"clean completed saga flagged: {saga_in_diffs}"
    assert report.sagas_examined >= 1


async def test_reconcile_clean_refunded_saga_reports_ok(
    orch: SagaOrchestrator,
    session: AsyncSession,
    test_user_id: uuid.UUID,
) -> None:
    """AC6 #4 — refunded saga: orchestrator wrote +A refund; without route's compensating -A, ledger nets to +A.

    BUT — this is what M2.2b discovered: orchestrator-only walks DON'T have the R1.1 compensating row
    (that's written by the /finalize route, not by apply("user_cancel")). So a saga that hits user_cancel
    via the orchestrator path has ledger = +A. This SHOULD be flagged as drift in the orchestrator-only case.

    To test the "clean refunded" path that actually exists in production, drive through /finalize.
    But /finalize is the HTTP route — too much fixture overhead. Instead, manually inject the
    compensating refund_reversal row to simulate the route's behavior.
    """
    start_window = datetime.now(UTC) - timedelta(seconds=5)
    amount = Decimal("6")
    saga = await orch.start(
        "solve_charge",
        test_user_id,
        f"reco-refunded-{uuid.uuid4()}",
        {"x": 1},
        amount=amount,
    )
    await orch.apply(saga.id, "reserve")
    await orch.apply(saga.id, "user_cancel")  # writes +A refund row
    # Manually add the R1.1 compensating refund_reversal row (what the /finalize route does)
    session.add(
        CreditTransaction(
            user_id=test_user_id,
            saga_id=saga.id,
            amount=-amount,
            kind="refund_reversal",
            currency="CNY",
            metadata_json={"test": "simulating /finalize compensation"},
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()
    end_window = datetime.now(UTC) + timedelta(seconds=5)

    report = await reconcile_window(session, start_window, end_window)
    # Our specific saga should NOT appear in non-OK results
    saga_in_diffs = [r for r in report.results if r.saga_id == saga.id]
    assert saga_in_diffs == [], f"clean refunded saga flagged: {saga_in_diffs}"


async def test_reconcile_detects_major_overcredit_drift(
    orch: SagaOrchestrator,
    session: AsyncSession,
    test_user_id: uuid.UUID,
) -> None:
    """AC6 #5 — inject +10 on COMPLETED saga → ledger sum = +4 (out of [-6, -0.01]) → MAJOR drift."""
    start_window = datetime.now(UTC) - timedelta(seconds=5)
    amount = Decimal("6")
    saga = await orch.start(
        "solve_charge",
        test_user_id,
        f"reco-major-{uuid.uuid4()}",
        {"x": 1},
        amount=amount,
    )
    await orch.apply(saga.id, "reserve")
    await orch.apply(saga.id, "service_success")  # -6
    await orch.apply(saga.id, "outbox_delivered")  # → COMPLETED
    session.add(
        CreditTransaction(
            user_id=test_user_id,
            saga_id=saga.id,
            amount=Decimal("10.00"),
            kind="adjustment",
            currency="CNY",
            metadata_json={"test": "out-of-bounds drift"},
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()
    end_window = datetime.now(UTC) + timedelta(seconds=5)

    report = await reconcile_window(session, start_window, end_window)
    matches = [r for r in report.results if r.saga_id == saga.id]
    assert len(matches) == 1
    result = matches[0]
    # actual = -6 + 10 = +4; bounds = [-6, -0.01]; drift = 4 - (-0.01) = 4.01 → MAJOR
    assert result.actual_sum == Decimal("4.00")
    assert result.severity == DriftSeverity.MAJOR
    assert result.drift > Decimal("4.00")


async def test_reconcile_partial_finalize_within_bounds(
    orch: SagaOrchestrator,
    session: AsyncSession,
    test_user_id: uuid.UUID,
) -> None:
    """AC6 #6 (D1 fix) — simulated /finalize partial: -A charge + +(A-actual) refund_partial.

    Net ledger = -actual_amount, must be in [-A, -min_floor] → OK.
    """
    start_window = datetime.now(UTC) - timedelta(seconds=5)
    amount = Decimal("6")
    actual = Decimal("0.50")  # like an elapsed=5s solve with rate=0.10
    refund_partial = amount - actual  # 5.50

    saga = await orch.start(
        "solve_charge",
        test_user_id,
        f"reco-partial-{uuid.uuid4()}",
        {"x": 1},
        amount=amount,
    )
    await orch.apply(saga.id, "reserve")
    await orch.apply(saga.id, "service_success")  # orchestrator's -6 charge row
    # Simulate /finalize route adding partial refund
    session.add(
        CreditTransaction(
            user_id=test_user_id,
            saga_id=saga.id,
            amount=refund_partial,
            kind="refund_partial",
            currency="CNY",
            metadata_json={"actual_amount": str(actual)},
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()
    end_window = datetime.now(UTC) + timedelta(seconds=5)

    report = await reconcile_window(session, start_window, end_window)
    saga_in_diffs = [r for r in report.results if r.saga_id == saga.id]
    assert saga_in_diffs == [], f"partial finalize within bounds was flagged: {saga_in_diffs}"
