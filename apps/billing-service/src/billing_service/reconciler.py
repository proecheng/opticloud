"""Daily billing reconciliation — Story 5.A.7 (NFR-R4 hardening).

Read-only scan of terminal Sagas + their ledger rows. Reports any drift
between expected and actual `SUM(credit_transactions.amount)` per Saga.

NEVER writes compensation rows — humans review and adjust. The whole point is
continuous-observation evidence that 对账误差 = 0 holds in production.

Public surface:
- `DriftSeverity`         — enum OK / MINOR / MAJOR
- `SagaReconciliationResult` — per-saga finding (only non-OK reported)
- `ReconciliationReport`  — window-level summary
- `classify_drift(d)`     — pure: maps Decimal drift to severity
- `expected_bounds(state, amount)` — pure: returns (lo, hi) for terminal state
- `reconcile_window(...)` — async: scans + returns Report
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from billing_service.config import settings
from billing_service.models import CreditTransaction, SagaInstance


class DriftSeverity(StrEnum):
    OK = "ok"
    MINOR = "minor"
    MAJOR = "major"


_DRIFT_OK_THRESHOLD = Decimal("0.01")  # < 1 cent absorbed as rounding noise
_DRIFT_MAJOR_THRESHOLD = Decimal("1.00")

_TERMINAL_STATES: frozenset[str] = frozenset({"completed", "failed", "refunded", "rolled_back"})


@dataclass(frozen=True)
class SagaReconciliationResult:
    """One Saga's reconciliation outcome — only emitted when non-OK."""

    saga_id: UUID
    user_id: UUID
    saga_type: str
    terminal_state: str
    reserved_amount: Decimal
    expected_low: Decimal
    expected_high: Decimal
    actual_sum: Decimal
    drift: Decimal  # signed: actual - midpoint(expected_low, expected_high)
    severity: DriftSeverity


@dataclass(frozen=True)
class ReconciliationReport:
    """Window-level summary."""

    window_start: datetime
    window_end: datetime
    sagas_examined: int
    diffs_found: int
    total_drift_magnitude: Decimal
    results: list[SagaReconciliationResult] = field(default_factory=list)


def classify_drift(drift: Decimal) -> DriftSeverity:
    """Pure: map absolute drift to severity."""
    abs_drift = abs(drift)
    if abs_drift < _DRIFT_OK_THRESHOLD:
        return DriftSeverity.OK
    if abs_drift < _DRIFT_MAJOR_THRESHOLD:
        return DriftSeverity.MINOR
    return DriftSeverity.MAJOR


def expected_bounds(
    state: str, reserved_amount: Decimal, *, saga_type: str = "solve_charge"
) -> tuple[Decimal, Decimal]:
    """Return (low, high) inclusive bounds for the ledger SUM at a terminal state.

    R2 D1 — reconciler can't see /finalize's actual_amount from saga.payload_ref
    (it lives in OutboxEvent.payload). For CHARGED/COMPLETED, we accept any
    sum in [-A, -charge_min_amount] as OK because the user paid SOMETHING ≤ cap.
    """
    a = reserved_amount
    if saga_type == "topup":
        if state == "completed":
            return (a, a)
        if state in ("failed", "refunded", "rolled_back"):
            return (Decimal("0"), Decimal("0"))
        raise ValueError(f"expected_bounds() called with non-terminal state {state!r}")

    floor = settings.charge_min_amount
    if state == "failed":
        return (Decimal("0"), Decimal("0"))
    if state == "refunded":
        return (Decimal("0"), Decimal("0"))
    if state == "rolled_back":
        return (Decimal("0"), Decimal("0"))
    if state in ("charged", "completed"):
        # debit at least 1 cent, at most the reserved amount
        return (-a, -floor)
    # Unknown state — shouldn't happen for a terminal scan, but fail loud.
    raise ValueError(f"expected_bounds() called with non-terminal state {state!r}")


def _drift_relative_to_bounds(actual: Decimal, lo: Decimal, hi: Decimal) -> Decimal:
    """If actual ∈ [lo, hi], drift = 0. Else, drift = signed distance to nearest bound."""
    if lo <= actual <= hi:
        return Decimal("0")
    if actual < lo:
        return actual - lo  # negative — too low
    return actual - hi  # positive — too high


async def reconcile_window(
    session: AsyncSession,
    window_start: datetime,
    window_end: datetime,
) -> ReconciliationReport:
    """Scan terminal Sagas in [window_start, window_end] and detect ledger drift.

    The window filter uses `saga_instances.updated_at` — terminal sagas have
    their `updated_at` set by the last `apply()` call.
    """
    stmt = (
        select(SagaInstance)
        .where(
            and_(
                SagaInstance.current_state.in_(_TERMINAL_STATES),
                SagaInstance.updated_at >= window_start,
                SagaInstance.updated_at < window_end,
            )
        )
        .order_by(SagaInstance.updated_at)
    )
    sagas = (await session.execute(stmt)).scalars().all()

    results: list[SagaReconciliationResult] = []
    total_drift_magnitude = Decimal("0")

    for saga in sagas:
        if saga.amount is None:
            # Sagas without an amount are out of scope (no money invariant to check)
            continue
        sum_stmt = select(func.coalesce(func.sum(CreditTransaction.amount), Decimal("0"))).where(
            CreditTransaction.saga_id == saga.id
        )
        actual_sum = Decimal(str((await session.execute(sum_stmt)).scalar_one()))

        lo, hi = expected_bounds(saga.current_state, saga.amount, saga_type=saga.saga_type)
        drift = _drift_relative_to_bounds(actual_sum, lo, hi)
        severity = classify_drift(drift)

        if severity != DriftSeverity.OK:
            total_drift_magnitude += abs(drift)
            results.append(
                SagaReconciliationResult(
                    saga_id=saga.id,
                    user_id=saga.user_id,
                    saga_type=saga.saga_type,
                    terminal_state=saga.current_state,
                    reserved_amount=saga.amount,
                    expected_low=lo,
                    expected_high=hi,
                    actual_sum=actual_sum,
                    drift=drift,
                    severity=severity,
                )
            )

    return ReconciliationReport(
        window_start=window_start,
        window_end=window_end,
        sagas_examined=len(sagas),
        diffs_found=len(results),
        total_drift_magnitude=total_drift_magnitude,
        results=results,
    )


__all__ = [
    "DriftSeverity",
    "ReconciliationReport",
    "SagaReconciliationResult",
    "classify_drift",
    "expected_bounds",
    "reconcile_window",
]
