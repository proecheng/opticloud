"""Compensation strategies (ADR-0001 + Story 5.A.0a AC5).

Per DR3, compensations are NOT auto-invoked by the orchestrator. They are
triggered when the caller explicitly applies the compensating trigger
(e.g., `apply(saga_id, "user_cancel")` to invoke REFUND_AUTO).

This module documents the mapping `Compensation -> trigger name -> side effect`
and provides a small dispatch helper used in tests and in audit log enrichment.

Side effects are written by SagaOrchestrator.apply() — this module is
declarative metadata only.
"""

from __future__ import annotations

from dataclasses import dataclass

from opticloud_shared.saga import Compensation


@dataclass(frozen=True)
class CompensationSpec:
    """Declarative description of a compensation strategy."""

    enum_value: Compensation
    invoking_trigger: str  # trigger the caller passes to apply()
    creates_credit_tx: bool  # whether this transition writes credit_transactions
    side_effect_summary: str  # human description for audit logs


# Single source of truth for compensation dispatch metadata.
# Aligns with opticloud_shared.saga.TRANSITIONS + AC5 wording.
COMPENSATION_SPECS: tuple[CompensationSpec, ...] = (
    CompensationSpec(
        enum_value=Compensation.MARK_FAILED,
        invoking_trigger="balance_insufficient",
        creates_credit_tx=False,
        side_effect_summary="PENDING -> FAILED; no money moved",
    ),
    CompensationSpec(
        enum_value=Compensation.REFUND_AUTO,
        invoking_trigger="user_cancel",
        creates_credit_tx=True,
        side_effect_summary="RESERVED -> REFUNDED; refund credit_transaction row written",
    ),
    CompensationSpec(
        enum_value=Compensation.RETRY_OUTBOX,
        invoking_trigger="outbox_delivered",
        creates_credit_tx=False,
        side_effect_summary="CHARGED -> COMPLETED; sidecar owns retry on delivery failure",
    ),
    CompensationSpec(
        enum_value=Compensation.ESCALATE_OPS,
        invoking_trigger="downstream_reject_late",
        creates_credit_tx=True,
        side_effect_summary="CHARGED -> ROLLED_BACK; refund + SRE escalation",
    ),
)


def spec_for(compensation: Compensation) -> CompensationSpec | None:
    """Return the spec for a given Compensation enum value."""
    for s in COMPENSATION_SPECS:
        if s.enum_value == compensation:
            return s
    return None


__all__ = ["CompensationSpec", "COMPENSATION_SPECS", "spec_for"]
