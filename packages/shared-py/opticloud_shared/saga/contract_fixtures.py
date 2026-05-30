"""Deterministic Saga contract fixtures shared across Epic 0/3/5.A.

Story 5.A.0b owns this catalog. It is intentionally static, offline, and
service-agnostic: no billing-service imports, no DB access, no network calls.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from opticloud_shared.saga.state_machine import TRANSITIONS, Compensation, State, Transition

SAGA_CONTRACT_VERSION: Final[str] = "2026-05-30.saga-fixtures.v1"

SagaFixtureCategory = Literal[
    "charge",
    "refund",
    "rollback",
    "idempotency",
    "timeout",
    "cost_telemetry",
    "budget_pause_stub",
]
IdempotencyCase = Literal["same_body_replay", "different_body_conflict"]

_CATEGORY_MINIMUMS: Final[dict[SagaFixtureCategory, int]] = {
    "charge": 10,
    "refund": 8,
    "rollback": 8,
    "idempotency": 8,
    "timeout": 8,
    "cost_telemetry": 8,
    "budget_pause_stub": 2,
}

_TRANSITIONS_BY_FROM_TRIGGER: Final[dict[tuple[State, str], Transition]] = {
    (transition.from_state, transition.trigger): transition for transition in TRANSITIONS
}

_LEDGER_SIGNS: Final[dict[str, int]] = {
    "service_success": -1,
    "user_cancel": 1,
    "downstream_reject_late": 1,
}

_FIXTURE_NAMESPACE: Final[uuid.UUID] = uuid.UUID("286ad313-b57f-4a91-aa8c-82027e1bbac2")
_FIXTURE_EPOCH: Final[datetime] = datetime(2026, 5, 30, tzinfo=UTC)
_ALLOWED_PAYLOAD_KEYS: Final[frozenset[str]] = frozenset(
    {
        "reference_id",
        "task_type",
        "purpose",
        "scenario_id",
        "operation_id",
        "cost_telemetry_ref",
    }
)
_FORBIDDEN_KEY_FRAGMENTS: Final[tuple[str, ...]] = (
    "amount",
    "price",
    "credit",
    "balance",
    "phone",
    "email",
    "name",
    "address",
    "token",
    "secret",
    "api_key",
    "bearer",
    "prompt",
    "input",
    "payload",
    "bank",
    "id_card",
)
_FORBIDDEN_VALUE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(@|sk-[A-Za-z0-9]|bearer\s+|token|secret|api[_-]?key|\+?\d{11,}|身份证|银行卡)",
    re.IGNORECASE,
)


class SagaFixtureStep(BaseModel):
    """One executable step in a Saga fixture."""

    model_config = ConfigDict(frozen=True)

    trigger: str
    from_state: State
    to_state: State
    compensation: Compensation
    timeout_ms: int = Field(ge=0)
    max_retries: int = Field(ge=0)


class SagaContractFixture(BaseModel):
    """A deterministic Saga fixture for shared contract tests."""

    model_config = ConfigDict(frozen=True)

    fixture_id: str
    category: SagaFixtureCategory
    saga_type: str
    user_id: uuid.UUID
    idempotency_key: str
    payload_ref: dict[str, str]
    amount: Decimal
    created_at: datetime
    steps: tuple[SagaFixtureStep, ...]
    expected_final_state: State
    expected_ledger_delta: Decimal
    expected_outbox_count: int = Field(ge=0)
    executable: bool = True
    idempotency_case: IdempotencyCase | None = None
    expected_body_hash: str
    cost_telemetry: dict[str, str | bool] | None = None
    unsupported_state: str | None = None
    notes: str


class SagaFixtureManifest(BaseModel):
    """Versioned collection of Saga fixtures."""

    model_config = ConfigDict(frozen=True)

    version: str
    generated_at: datetime
    category_minimums: dict[SagaFixtureCategory, int]
    fixtures: tuple[SagaContractFixture, ...]

    @property
    def executable_fixtures(self) -> tuple[SagaContractFixture, ...]:
        """Fixtures that can be executed against SagaOrchestrator."""
        return tuple(fixture for fixture in self.fixtures if fixture.executable)


def canonical_body_hash(saga_type: str, payload: dict[str, str], amount: Decimal | None) -> str:
    """Stable SHA-256 over the same body shape used by billing Saga idempotency."""
    canonical = json.dumps(
        {
            "saga_type": saga_type,
            "payload": payload,
            "amount": str(amount) if amount else None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_saga_contract_fixtures() -> SagaFixtureManifest:
    """Build the deterministic 5.A.0b fixture manifest."""
    fixtures: list[SagaContractFixture] = []
    fixtures.extend(_build_category("charge", 10, _charge_path))
    fixtures.extend(_build_category("refund", 8, _refund_path))
    fixtures.extend(_build_category("rollback", 8, _rollback_path))
    fixtures.extend(_build_idempotency_fixtures())
    fixtures.extend(_build_category("timeout", 8, _timeout_path))
    fixtures.extend(_build_cost_telemetry_fixtures())
    fixtures.extend(_build_budget_pause_stubs())
    return SagaFixtureManifest(
        version=SAGA_CONTRACT_VERSION,
        generated_at=_FIXTURE_EPOCH,
        category_minimums=dict(_CATEGORY_MINIMUMS),
        fixtures=tuple(fixtures),
    )


def validate_contract_fixture_manifest(manifest: SagaFixtureManifest) -> None:
    """Validate fixture determinism, transition parity, and safety constraints."""
    errors: list[str] = []
    if manifest.version != SAGA_CONTRACT_VERSION:
        errors.append(f"manifest version {manifest.version!r} != {SAGA_CONTRACT_VERSION!r}")
    if manifest.category_minimums != _CATEGORY_MINIMUMS:
        errors.append("manifest category_minimums must match the canonical 5.A.0b minimums")
    if len(manifest.fixtures) < sum(_CATEGORY_MINIMUMS.values()):
        errors.append(
            f"manifest has {len(manifest.fixtures)} fixtures; "
            f"minimum is {sum(_CATEGORY_MINIMUMS.values())}"
        )

    ids = [fixture.fixture_id for fixture in manifest.fixtures]
    duplicates = sorted(fixture_id for fixture_id, count in Counter(ids).items() if count > 1)
    if duplicates:
        errors.append(f"duplicate fixture IDs: {duplicates}")

    category_counts = Counter(fixture.category for fixture in manifest.fixtures)
    for category, minimum in _CATEGORY_MINIMUMS.items():
        if category_counts[category] < minimum:
            errors.append(
                f"category {category!r} has {category_counts[category]} fixtures; "
                f"minimum is {minimum}"
            )

    idempotency_cases = {
        fixture.idempotency_case
        for fixture in manifest.fixtures
        if fixture.category == "idempotency"
    }
    if "same_body_replay" not in idempotency_cases:
        errors.append("idempotency fixtures missing same_body_replay case")
    if "different_body_conflict" not in idempotency_cases:
        errors.append("idempotency fixtures missing different_body_conflict case")

    for fixture in manifest.fixtures:
        errors.extend(_validate_fixture(fixture))

    if errors:
        raise ValueError("; ".join(errors))


def _build_category(
    category: SagaFixtureCategory,
    count: int,
    path_builder: Callable[[int], tuple[SagaFixtureStep, ...]],
) -> list[SagaContractFixture]:
    fixtures: list[SagaContractFixture] = []
    for index in range(1, count + 1):
        steps = path_builder(index)
        fixtures.append(_make_fixture(category, index, steps=steps))
    return fixtures


def _build_idempotency_fixtures() -> list[SagaContractFixture]:
    fixtures: list[SagaContractFixture] = []
    for index in range(1, 9):
        case: IdempotencyCase = "same_body_replay" if index <= 4 else "different_body_conflict"
        steps = _charge_path(index) if index % 2 else ()
        fixtures.append(
            _make_fixture(
                "idempotency",
                index,
                steps=steps,
                idempotency_case=case,
                notes=f"P23 idempotency contract: {case}",
            )
        )
    return fixtures


def _build_cost_telemetry_fixtures() -> list[SagaContractFixture]:
    fixtures: list[SagaContractFixture] = []
    for index in range(1, 9):
        steps = _charge_path(index) if index <= 4 else _rollback_path(index)
        fixture = _make_fixture(
            "cost_telemetry",
            index,
            steps=steps,
            payload_extra={
                "cost_telemetry_ref": str(
                    uuid.uuid5(_FIXTURE_NAMESPACE, f"cost-telemetry-ref-{index:03d}")
                )
            },
            cost_telemetry={
                "schema_version": "placeholder-v1",
                "hook_name": "billing.saga.cost_telemetry",
                "implemented": False,
            },
            notes="Schema-only cost telemetry hook placeholder; no runtime call.",
        )
        fixtures.append(fixture)
    return fixtures


def _build_budget_pause_stubs() -> list[SagaContractFixture]:
    fixtures: list[SagaContractFixture] = []
    for index in range(1, 3):
        fixtures.append(
            _make_fixture(
                "budget_pause_stub",
                index,
                steps=(),
                executable=False,
                unsupported_state="paused_by_budget",
                notes=(
                    "Planning references paused_by_budget, but current ADR-0001 implementation "
                    "has a 7-state machine. Stub kept non-executable for 5.D.5/5.A follow-up."
                ),
            )
        )
    return fixtures


def _charge_path(index: int) -> tuple[SagaFixtureStep, ...]:
    triggers: tuple[str, ...] = ("reserve", "service_success")
    if index % 2 == 0:
        triggers = ("reserve", "service_success", "outbox_delivered")
    return _steps_from_triggers(triggers)


def _refund_path(index: int) -> tuple[SagaFixtureStep, ...]:
    return _steps_from_triggers(("reserve", "user_cancel"))


def _rollback_path(index: int) -> tuple[SagaFixtureStep, ...]:
    return _steps_from_triggers(("reserve", "service_success", "downstream_reject_late"))


def _timeout_path(index: int) -> tuple[SagaFixtureStep, ...]:
    if index % 2:
        return _steps_from_triggers(("balance_insufficient",))
    return _steps_from_triggers(("reserve", "pre_charge_guard_reject"))


def _steps_from_triggers(triggers: tuple[str, ...]) -> tuple[SagaFixtureStep, ...]:
    state = State.PENDING
    steps: list[SagaFixtureStep] = []
    for trigger in triggers:
        transition = TRANSITION_LOOKUP[(state, trigger)]
        steps.append(
            SagaFixtureStep(
                trigger=transition.trigger,
                from_state=transition.from_state,
                to_state=transition.to_state,
                compensation=transition.compensation,
                timeout_ms=transition.timeout_ms,
                max_retries=transition.max_retries,
            )
        )
        state = transition.to_state
    return tuple(steps)


def _make_fixture(
    category: SagaFixtureCategory,
    index: int,
    *,
    steps: tuple[SagaFixtureStep, ...],
    executable: bool = True,
    idempotency_case: IdempotencyCase | None = None,
    payload_extra: dict[str, str] | None = None,
    cost_telemetry: dict[str, str | bool] | None = None,
    unsupported_state: str | None = None,
    notes: str | None = None,
) -> SagaContractFixture:
    fixture_id = f"{category.replace('_', '-')}-{index:03d}"
    amount = Decimal(f"{index + len(category)}.{index % 100:02d}")
    payload_ref = {
        "reference_id": str(uuid.uuid5(_FIXTURE_NAMESPACE, f"{fixture_id}:reference")),
        "task_type": "lp",
        "purpose": "solve",
        "scenario_id": fixture_id,
        "operation_id": str(uuid.uuid5(_FIXTURE_NAMESPACE, f"{fixture_id}:operation")),
        **(payload_extra or {}),
    }
    final_state = steps[-1].to_state if steps else State.PENDING
    fixture = SagaContractFixture(
        fixture_id=fixture_id,
        category=category,
        saga_type="solve_charge",
        user_id=uuid.uuid5(_FIXTURE_NAMESPACE, f"{fixture_id}:user"),
        idempotency_key=f"saga-fixture-{fixture_id}",
        payload_ref=payload_ref,
        amount=amount,
        created_at=_FIXTURE_EPOCH + timedelta(minutes=len(fixture_id) + index),
        steps=steps,
        expected_final_state=final_state,
        expected_ledger_delta=_expected_ledger_delta(amount, steps),
        expected_outbox_count=len(steps) if executable else 0,
        executable=executable,
        idempotency_case=idempotency_case,
        expected_body_hash=canonical_body_hash("solve_charge", payload_ref, amount),
        cost_telemetry=cost_telemetry,
        unsupported_state=unsupported_state,
        notes=notes or f"{category} contract fixture {index:03d}",
    )
    return fixture


def _expected_ledger_delta(amount: Decimal, steps: tuple[SagaFixtureStep, ...]) -> Decimal:
    total = Decimal("0")
    for step in steps:
        total += amount * _LEDGER_SIGNS.get(step.trigger, 0)
    return total.quantize(Decimal("0.0001"))


def _validate_fixture(fixture: SagaContractFixture) -> list[str]:
    errors: list[str] = []
    errors.extend(_validate_payload_ref(fixture))
    if fixture.expected_body_hash != canonical_body_hash(
        fixture.saga_type, fixture.payload_ref, fixture.amount
    ):
        errors.append(f"{fixture.fixture_id}: expected_body_hash is not canonical")

    if fixture.category == "budget_pause_stub":
        if fixture.executable:
            errors.append(f"{fixture.fixture_id}: budget_pause_stub must be non-executable")
        if fixture.unsupported_state != "paused_by_budget":
            errors.append(f"{fixture.fixture_id}: missing paused_by_budget unsupported_state")
        if fixture.steps:
            errors.append(f"{fixture.fixture_id}: budget_pause_stub must not define steps")
        if fixture.expected_final_state != State.PENDING:
            errors.append(f"{fixture.fixture_id}: budget_pause_stub final state must be pending")
        if fixture.expected_ledger_delta != Decimal("0.0000"):
            errors.append(f"{fixture.fixture_id}: budget_pause_stub ledger delta must be zero")
        if fixture.expected_outbox_count != 0:
            errors.append(
                f"{fixture.fixture_id}: budget_pause_stub expected_outbox_count must be 0"
            )
        return errors

    if not fixture.executable:
        errors.append(f"{fixture.fixture_id}: non-stub fixtures must be executable")

    current = State.PENDING
    ledger_delta = Decimal("0")
    for step in fixture.steps:
        if step.from_state != current:
            errors.append(
                f"{fixture.fixture_id}: step {step.trigger!r} from_state "
                f"{step.from_state.value!r} != derived {current.value!r}"
            )
        transition = _TRANSITIONS_BY_FROM_TRIGGER.get((current, step.trigger))
        if transition is None:
            errors.append(
                f"{fixture.fixture_id}: step {step.trigger!r} not valid from {current.value!r}"
            )
            continue
        if transition.from_state != step.from_state:
            errors.append(
                f"{fixture.fixture_id}: step {step.trigger!r} from_state "
                f"{step.from_state.value!r} != matrix {transition.from_state.value!r}"
            )
        if transition.to_state != step.to_state:
            errors.append(
                f"{fixture.fixture_id}: step {step.trigger!r} to_state "
                f"{step.to_state.value!r} != matrix {transition.to_state.value!r}"
            )
        if transition.compensation != step.compensation:
            errors.append(
                f"{fixture.fixture_id}: step {step.trigger!r} compensation "
                f"{step.compensation.value!r} != matrix {transition.compensation.value!r}"
            )
        ledger_delta += fixture.amount * _LEDGER_SIGNS.get(step.trigger, 0)
        current = transition.to_state

    if fixture.expected_final_state != current:
        errors.append(
            f"{fixture.fixture_id}: expected_final_state {fixture.expected_final_state.value!r} "
            f"!= derived {current.value!r}"
        )
    if fixture.expected_ledger_delta != ledger_delta.quantize(Decimal("0.0001")):
        errors.append(
            f"{fixture.fixture_id}: expected_ledger_delta {fixture.expected_ledger_delta} "
            f"!= derived {ledger_delta}"
        )
    if fixture.expected_outbox_count != len(fixture.steps):
        errors.append(
            f"{fixture.fixture_id}: expected_outbox_count {fixture.expected_outbox_count} "
            f"!= step count {len(fixture.steps)}"
        )
    if fixture.category == "idempotency" and fixture.idempotency_case is None:
        errors.append(f"{fixture.fixture_id}: idempotency fixture missing case")
    return errors


def _validate_payload_ref(fixture: SagaContractFixture) -> list[str]:
    errors: list[str] = []
    for key, value in fixture.payload_ref.items():
        lowered_key = key.lower()
        if key not in _ALLOWED_PAYLOAD_KEYS:
            errors.append(f"{fixture.fixture_id}: payload_ref key {key!r} is not pointer-safe")
        for fragment in _FORBIDDEN_KEY_FRAGMENTS:
            if fragment in lowered_key:
                errors.append(f"{fixture.fixture_id}: forbidden payload key fragment {fragment!r}")
        if not isinstance(value, str):
            errors.append(f"{fixture.fixture_id}: payload_ref value for {key!r} must be a string")
            continue
        if _FORBIDDEN_VALUE_PATTERN.search(value):
            errors.append(f"{fixture.fixture_id}: forbidden payload value under {key!r}")
    return errors


# Narrow typed transition lookup used by the deterministic builder.
TRANSITION_LOOKUP: Final[dict[tuple[State, str], Transition]] = _TRANSITIONS_BY_FROM_TRIGGER

CONTRACT_FIXTURE_MANIFEST: Final[SagaFixtureManifest] = build_saga_contract_fixtures()
validate_contract_fixture_manifest(CONTRACT_FIXTURE_MANIFEST)

__all__ = [
    "CONTRACT_FIXTURE_MANIFEST",
    "SAGA_CONTRACT_VERSION",
    "SagaContractFixture",
    "SagaFixtureManifest",
    "SagaFixtureStep",
    "build_saga_contract_fixtures",
    "canonical_body_hash",
    "validate_contract_fixture_manifest",
]
