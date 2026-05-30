"""Saga state machine — skeleton from M2.0 spike (ADR-0001).

Downstream consumers:
- Story 5.A.0a/b/c: full Saga state machine implementation
- Story M2.2a: Billing 50 critical scenario tests
- Story 3-14: mock-real divergence (reuses Saga state types)

This module defines the **State enum + Transition matrix + invariants only**.
Business wiring (DB writes, Outbox emits, compensations) is intentionally
deferred to 5.A.0a.

See docs/adr/0001-saga-pattern.md for design rationale.
"""

from opticloud_shared.saga.contract_fixtures import (
    CONTRACT_FIXTURE_MANIFEST,
    SAGA_CONTRACT_VERSION,
    SagaContractFixture,
    SagaFixtureManifest,
    SagaFixtureStep,
    build_saga_contract_fixtures,
    canonical_body_hash,
    validate_contract_fixture_manifest,
    validate_payload_ref_safety,
)
from opticloud_shared.saga.state_machine import (
    TERMINAL_STATES,
    TRANSITIONS,
    Compensation,
    State,
    Transition,
    is_terminal,
    next_states,
    valid_transitions_from,
)

__all__ = [
    "CONTRACT_FIXTURE_MANIFEST",
    "Compensation",
    "SAGA_CONTRACT_VERSION",
    "SagaContractFixture",
    "SagaFixtureManifest",
    "SagaFixtureStep",
    "State",
    "Transition",
    "TRANSITIONS",
    "TERMINAL_STATES",
    "build_saga_contract_fixtures",
    "canonical_body_hash",
    "is_terminal",
    "next_states",
    "validate_contract_fixture_manifest",
    "validate_payload_ref_safety",
    "valid_transitions_from",
]
