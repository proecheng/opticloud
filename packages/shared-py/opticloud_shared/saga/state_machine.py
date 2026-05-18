"""Saga state machine skeleton — ADR-0001 specification.

This is the **single source of truth** for billing Saga states + transitions.
Story 5.A.0a implementation imports State / Transition / TRANSITIONS from here.

Do not add business logic (DB writes, side effects) here. This module is:
1. Pure data definitions (enum + dataclass + matrix)
2. Pure functions (is_terminal, next_states)
3. Hypothesis property test target (see tests/test_saga_state_machine.py)

Extension guide:
- Add a new State → add to State enum + update TRANSITIONS matrix
- Add a new Transition → append to TRANSITIONS list with timeout / retries / compensation
- New ADR required if changing State enum cardinality or terminal-state set
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class State(StrEnum):
    """Saga states per ADR-0001. String-valued for JSONB / audit log readability."""

    PENDING = "pending"  # Initial; idempotency check in flight
    RESERVED = "reserved"  # Credits reserved; awaiting downstream confirmation
    CHARGED = "charged"  # Downstream service success; ledger debited
    COMPLETED = "completed"  # Outbox event delivered + Saga done (terminal)
    FAILED = "failed"  # Pre-charge guard rejected (terminal — no money moved)
    REFUNDED = "refunded"  # User-cancelled or pre-charge fail with refund (terminal)
    ROLLED_BACK = "rolled_back"  # Post-charge downstream reject (terminal; money refunded)


TERMINAL_STATES: Final[frozenset[State]] = frozenset(
    {State.COMPLETED, State.FAILED, State.REFUNDED, State.ROLLED_BACK}
)


class Compensation(StrEnum):
    """Compensation strategy names — referenced by Transition.compensation.

    CR3 fix: replaced free-form string with enum to prevent typos.
    Adding a new compensation = add enum value + implement in 5.A.0a handler.
    """

    NONE = "none"
    MARK_FAILED = "mark_failed"  # PENDING → FAILED on reserve timeout
    REFUND_AUTO = "refund_auto"  # RESERVED → REFUNDED on charge fail
    RETRY_OUTBOX = "retry_outbox"  # CHARGED → COMPLETED on outbox fail (loop)
    ESCALATE_OPS = "escalate_ops"  # CHARGED → ROLLED_BACK requires manual review


@dataclass(frozen=True)
class Transition:
    """Allowed Saga transition with operational semantics (ADR-0001 transition matrix).

    Fields:
      timeout_ms / max_retries: enforced by 5.A.0a runtime; 0 retries = no auto-retry
      compensation: typed enum (CR3 fix from M2.0 design review)
      median_latency_ms: ESTIMATE based on similar Postgres+Redis systems; refine in
        M3 with real production traces (CR4 fix). Used for NFR-P SLO budget allocation.
    """

    from_state: State
    to_state: State
    trigger: str  # human-readable event name (logs / audit)
    timeout_ms: int  # max time for transition to complete; on exceed → compensate
    max_retries: int  # exponential backoff up to this many times
    compensation: Compensation  # typed compensation strategy
    median_latency_ms: int  # operational SLO baseline (NFR-P), refine M3 with traces


# Transition matrix — ADR-0001 §"Transition matrix"
# Order matters only for documentation readability; lookups use index dict below.
TRANSITIONS: Final[tuple[Transition, ...]] = (
    Transition(State.PENDING, State.RESERVED, "reserve", 500, 5, Compensation.MARK_FAILED, 5),
    Transition(State.PENDING, State.FAILED, "balance_insufficient", 0, 0, Compensation.NONE, 2),
    Transition(
        State.RESERVED, State.CHARGED, "service_success", 2_000, 3, Compensation.REFUND_AUTO, 10
    ),
    Transition(State.RESERVED, State.REFUNDED, "user_cancel", 500, 3, Compensation.NONE, 5),
    Transition(State.RESERVED, State.FAILED, "pre_charge_guard_reject", 0, 0, Compensation.NONE, 3),
    Transition(
        State.CHARGED,
        State.COMPLETED,
        "outbox_delivered",
        500,
        1_000_000,
        Compensation.RETRY_OUTBOX,
        3,
    ),
    Transition(
        State.CHARGED,
        State.ROLLED_BACK,
        "downstream_reject_late",
        1_000,
        1,
        Compensation.ESCALATE_OPS,
        10,
    ),
)


# Fast lookup: (from_state) → tuple of valid Transitions
_NEXT_STATES: Final[dict[State, tuple[Transition, ...]]] = {}


def _build_index() -> None:
    """Build (from_state) → allowed transitions index."""
    by_from: dict[State, list[Transition]] = {state: [] for state in State}
    for t in TRANSITIONS:
        by_from[t.from_state].append(t)
    for k, v in by_from.items():
        _NEXT_STATES[k] = tuple(v)


_build_index()


def is_terminal(state: State) -> bool:
    """Return True iff state is a terminal state (no further transitions allowed)."""
    return state in TERMINAL_STATES


def next_states(state: State) -> tuple[State, ...]:
    """Return tuple of states reachable from `state` via a single Transition."""
    return tuple(t.to_state for t in _NEXT_STATES.get(state, ()))


def valid_transitions_from(state: State) -> tuple[Transition, ...]:
    """Return all Transition records starting from `state`."""
    return _NEXT_STATES.get(state, ())
