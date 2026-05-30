"""Saga orchestrator — Story 5.A.0a (ADR-0001).

Hybrid Saga orchestration for OptiCloud billing. Drives the 7-state machine
defined in `opticloud_shared.saga`. Single transactional dual-write (P33):
saga_instances + credit_transactions + outbox all written in one DB session.

Public API (AC3):
    orch = SagaOrchestrator(session)
    saga = await orch.start(saga_type, user_id, idempotency_key, payload)
    saga = await orch.apply(saga_id, trigger, context={...})
    saga = await orch.get(saga_id)

Invariants enforced (ADR-0001):
- I3: terminal state rejects all transitions (SagaTerminal raised)
- I4: same idempotency key + same body → identical saga_id (AC4)
- AC10: transition-idempotent — re-applying the same trigger that has already
  moved Saga to its target state is a no-op (no double-charge)

Security (ADR-0001 §Security):
- payload_ref contains POINTERS only (optimization_id, task_type); never amounts
- request_body_hash is SHA-256 hex; raw body never persisted
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from opentelemetry import trace
from opticloud_shared.saga import (
    TERMINAL_STATES,
    Compensation,
    State,
    Transition,
    valid_transitions_from,
    validate_payload_ref_safety,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from billing_service.config import settings
from billing_service.exceptions import (
    CrossTenantKeyError,
    IdempotencyConflictError,
    InvalidSagaTransitionError,
    SagaNotFoundError,
    SagaTerminalError,
    UnsafeSagaPayloadRefError,
)
from billing_service.models import (
    CreditTransaction,
    IdempotencyKeyRow,
    OutboxEvent,
    SagaInstance,
)

_tracer = trace.get_tracer(__name__)

# Triggers that move credits — used by apply() to write CreditTransaction rows.
# (trigger → kind, sign): sign +1 means credits returned to user, -1 means debit.
_CHARGE_TRIGGERS: dict[str, tuple[str, int]] = {
    "service_success": ("charge", -1),  # RESERVED → CHARGED: debit
    "user_cancel": ("refund", +1),  # RESERVED → REFUNDED: return reservation
    "downstream_reject_late": ("refund", +1),  # CHARGED → ROLLED_BACK: refund completed charge
}


def hash_body(body: dict[str, Any]) -> str:
    """Stable SHA-256 hex of request body (sorted keys, compact separators)."""
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SagaOrchestrator:
    """DB-backed Saga orchestrator. One instance per request / unit-of-work."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def start(
        self,
        saga_type: str,
        user_id: UUID,
        idempotency_key: str,
        payload: dict[str, Any],
        amount: Decimal | None = None,
    ) -> SagaInstance:
        """Create a new Saga or return existing one (P23 idempotency).

        Args:
            saga_type: e.g. "solve_charge", "topup"
            user_id: owning user UUID
            idempotency_key: caller-provided unique key (P23)
            payload: pointers + non-monetary metadata (NEVER amounts)
            amount: charge amount in CNY (separate arg — kept out of payload)

        Returns: SagaInstance in PENDING state (or existing one if key reused).

        Raises:
            IdempotencyConflict: same key + different body hash.
        """
        try:
            validate_payload_ref_safety(payload, fixture_id=f"saga:{saga_type}")
        except ValueError as exc:
            raise UnsafeSagaPayloadRefError(str(exc)) from exc

        body_hash = hash_body(
            {"saga_type": saga_type, "payload": payload, "amount": str(amount) if amount else None}
        )

        existing_key = await self.session.get(IdempotencyKeyRow, idempotency_key)
        now = datetime.now(UTC)
        if existing_key is not None and existing_key.expires_at > now:
            # S1 security fix (M2.2a): prevent cross-tenant key reuse
            if existing_key.user_id != user_id:
                raise CrossTenantKeyError(idempotency_key, existing_key.user_id, user_id)
            if existing_key.request_body_hash != body_hash:
                raise IdempotencyConflictError(
                    idempotency_key, existing_key.request_body_hash, body_hash
                )
            if existing_key.saga_id is not None:
                saga = await self.session.get(SagaInstance, existing_key.saga_id)
                if saga is not None:
                    return saga

        saga = SagaInstance(
            saga_type=saga_type,
            current_state=State.PENDING.value,
            user_id=user_id,
            idempotency_key=idempotency_key,
            amount=amount,
            retries=0,
            payload_ref=payload,
            created_at=now,
            updated_at=now,
        )
        self.session.add(saga)
        await self.session.flush()  # populate saga.id

        try:
            self.session.add(
                IdempotencyKeyRow(
                    key=idempotency_key,
                    user_id=user_id,
                    request_body_hash=body_hash,
                    saga_id=saga.id,
                    expires_at=now + timedelta(hours=settings.saga_idempotency_ttl_hours),
                    created_at=now,
                )
            )
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            row = await self.session.get(IdempotencyKeyRow, idempotency_key)
            if row is None or row.saga_id is None:
                raise
            existing_saga = await self.session.get(SagaInstance, row.saga_id)
            if existing_saga is None:
                raise SagaNotFoundError(row.saga_id) from None
            return existing_saga

        return saga

    async def get(self, saga_id: UUID) -> SagaInstance:
        """Read-only fetch."""
        saga = await self.session.get(SagaInstance, saga_id)
        if saga is None:
            raise SagaNotFoundError(saga_id)
        return saga

    async def apply(
        self,
        saga_id: UUID,
        trigger: str,
        context: dict[str, Any] | None = None,
    ) -> SagaInstance:
        """Apply a transition via `trigger`. Idempotent for retry-safety (AC10).

        Args:
            saga_id: existing Saga
            trigger: must match a Transition in opticloud_shared.saga.TRANSITIONS
            context: optional caller context (e.g. failure_reason); merged into
                outbox event payload and audit metadata

        Returns: updated SagaInstance

        Raises:
            SagaNotFound: saga_id doesn't exist
            SagaTerminal: saga is already in a terminal state
            InvalidSagaTransition: trigger not valid from current state
        """
        with _tracer.start_as_current_span("saga.apply") as span:
            span.set_attribute("saga.id", str(saga_id))
            span.set_attribute("saga.trigger", trigger)

            stmt = select(SagaInstance).where(SagaInstance.id == saga_id).with_for_update()
            result = await self.session.execute(stmt)
            saga = result.scalar_one_or_none()
            if saga is None:
                raise SagaNotFoundError(saga_id)
            span.set_attribute("saga.from_state", saga.current_state)

            transition = self._find_transition(saga.current_state, trigger)
            if transition is None:
                # AC10: idempotent retry — if any prior transition with same trigger
                # already moved us to the matching target, return no-op.
                if self._is_idempotent_replay(saga, trigger):
                    return saga
                # Otherwise either terminal or genuinely invalid.
                if State(saga.current_state) in TERMINAL_STATES:
                    raise SagaTerminalError(saga_id, saga.current_state)
                raise InvalidSagaTransitionError(saga.current_state, None, trigger)

            span.set_attribute("saga.to_state", transition.to_state.value)
            now = datetime.now(UTC)
            saga.current_state = transition.to_state.value
            saga.updated_at = now

            if trigger in _CHARGE_TRIGGERS:
                kind, sign = _CHARGE_TRIGGERS[trigger]
                amount = self._read_amount(saga)
                if amount is not None and amount != Decimal(0):
                    self.session.add(
                        CreditTransaction(
                            user_id=saga.user_id,
                            saga_id=saga.id,
                            amount=amount * sign,
                            kind=kind,
                            currency="CNY",
                            metadata_json={"trigger": trigger, **(context or {})},
                            created_at=now,
                        )
                    )

            self.session.add(
                OutboxEvent(
                    aggregate_type="saga_instance",
                    aggregate_id=saga.id,
                    event_type=f"billing.saga.{trigger}",
                    event_version=1,
                    payload={
                        "saga_id": str(saga.id),
                        "saga_type": saga.saga_type,
                        "from_state": transition.from_state.value,
                        "to_state": transition.to_state.value,
                        "trigger": trigger,
                        **(context or {}),
                    },
                    headers={"compensation": transition.compensation.value},
                    occurred_at=now,
                )
            )

            await self.session.flush()
            return saga

    @staticmethod
    def _find_transition(current_state: str, trigger: str) -> Transition | None:
        """Find the Transition matching (current_state, trigger), or None."""
        try:
            state = State(current_state)
        except ValueError:
            return None
        for t in valid_transitions_from(state):
            if t.trigger == trigger:
                return t
        return None

    def _is_idempotent_replay(self, saga: SagaInstance, trigger: str) -> bool:
        """AC10: was this trigger's target already reached? Then replay is a no-op."""
        # We can't look up by trigger from a terminal state (Transition matrix only
        # indexes from `from_state`). Idempotent replay = current_state matches what
        # a transition with this trigger WOULD HAVE produced. Approximation: check
        # all known transitions for one whose to_state == current_state AND
        # whose trigger == trigger.
        try:
            current = State(saga.current_state)
        except ValueError:
            return False
        from opticloud_shared.saga import TRANSITIONS  # local import — keeps top tidy

        for t in TRANSITIONS:
            if t.trigger == trigger and t.to_state == current:
                return True
        return False

    @staticmethod
    def _read_amount(saga: SagaInstance) -> Decimal | None:
        """Return the declared saga amount, or None for amount-less sagas."""
        return saga.amount


__all__ = [
    "SagaOrchestrator",
    "Compensation",  # re-export for caller convenience
    "hash_body",
]
