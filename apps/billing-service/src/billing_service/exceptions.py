"""Saga orchestrator exceptions (Story 5.A.0a — DR4 fix)."""

from __future__ import annotations

from uuid import UUID


class SagaError(Exception):
    """Base class for all Saga errors."""


class InvalidSagaTransitionError(SagaError):
    """Attempted a transition not allowed by the state machine.

    Args:
        from_state: current Saga state name
        to_state: requested target state (or None if trigger unknown)
        trigger: the trigger name passed to apply()
    """

    def __init__(self, from_state: str, to_state: str | None, trigger: str) -> None:
        self.from_state = from_state
        self.to_state = to_state
        self.trigger = trigger
        super().__init__(f"invalid transition: {from_state} --{trigger}--> {to_state or 'unknown'}")


class SagaTerminalError(SagaError):
    """Saga is in a terminal state; no further transitions allowed."""

    def __init__(self, saga_id: UUID, current_state: str) -> None:
        self.saga_id = saga_id
        self.current_state = current_state
        super().__init__(f"saga {saga_id} is terminal ({current_state})")


class IdempotencyConflictError(SagaError):
    """Same idempotency key reused with different request body."""

    def __init__(self, key: str, existing_hash: str, new_hash: str) -> None:
        self.key = key
        self.existing_hash = existing_hash
        self.new_hash = new_hash
        super().__init__(
            f"idempotency key {key!r} reused with different body: "
            f"existing={existing_hash[:8]}... new={new_hash[:8]}..."
        )


class SagaNotFoundError(SagaError):
    """Saga ID does not exist."""

    def __init__(self, saga_id: UUID) -> None:
        self.saga_id = saga_id
        super().__init__(f"saga {saga_id} not found")
