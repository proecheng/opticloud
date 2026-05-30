from __future__ import annotations

import hashlib
import json
from collections import Counter
from decimal import Decimal

import pytest
from opticloud_shared.saga import State
from opticloud_shared.saga.contract_fixtures import (
    CONTRACT_FIXTURE_MANIFEST,
    SAGA_CONTRACT_VERSION,
    canonical_body_hash,
    validate_contract_fixture_manifest,
    validate_payload_ref_safety,
)


def test_manifest_has_required_count_and_categories() -> None:
    """The shared manifest is the canonical 50+ cross-epic fixture catalog."""
    manifest = CONTRACT_FIXTURE_MANIFEST
    assert SAGA_CONTRACT_VERSION == "2026-05-30.saga-fixtures.v1"
    assert len(manifest.fixtures) >= 50

    counts = Counter(f.category for f in manifest.fixtures)
    for category, minimum in manifest.category_minimums.items():
        assert counts[category] >= minimum, f"{category} has {counts[category]} fixtures"


def test_manifest_validates_without_errors() -> None:
    """Validation locks transition parity, ledger expectations, and data-safety rules."""
    validate_contract_fixture_manifest(CONTRACT_FIXTURE_MANIFEST)


def test_fixture_ids_are_unique_and_deterministic() -> None:
    """Fixture IDs and generated user/idempotency values must be stable."""
    ids = [f.fixture_id for f in CONTRACT_FIXTURE_MANIFEST.fixtures]
    assert len(ids) == len(set(ids))
    assert ids[:5] == [
        "charge-001",
        "charge-002",
        "charge-003",
        "charge-004",
        "charge-005",
    ]


def test_executable_steps_match_expected_final_state() -> None:
    """Executable fixtures derive final state from the shared state-machine path."""
    for fixture in CONTRACT_FIXTURE_MANIFEST.executable_fixtures:
        expected = fixture.steps[-1].to_state if fixture.steps else State.PENDING
        assert fixture.expected_final_state == expected


def test_canonical_body_hash_is_sorted_compact_and_amount_aware() -> None:
    """Hash format matches 5.A.0a idempotency body hashing without billing imports."""
    payload_a = {"task_type": "lp", "reference_id": "ref-2", "purpose": "solve"}
    payload_b = {"purpose": "solve", "reference_id": "ref-2", "task_type": "lp"}
    first = canonical_body_hash("solve_charge", payload_a, Decimal("6.00"))
    second = canonical_body_hash("solve_charge", payload_b, Decimal("6.00"))
    assert first == second

    canonical = json.dumps(
        {
            "saga_type": "solve_charge",
            "payload": payload_a,
            "amount": "6.00",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    assert first == hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_idempotency_fixtures_cover_replay_and_conflict() -> None:
    """P23 cases must include both cache replay and conflict semantics."""
    cases = {
        f.idempotency_case
        for f in CONTRACT_FIXTURE_MANIFEST.fixtures
        if f.category == "idempotency"
    }
    assert "same_body_replay" in cases
    assert "different_body_conflict" in cases


def test_payload_refs_contain_no_amounts_or_pii() -> None:
    """Fixture payloads stay pointer-only and privacy-safe."""
    forbidden_fragments = (
        "amount",
        "price",
        "phone",
        "email",
        "token",
        "secret",
        "api_key",
        "bearer",
        "prompt",
        "input",
        "payload",
        "@",
        "sk-",
    )
    for fixture in CONTRACT_FIXTURE_MANIFEST.fixtures:
        encoded = json.dumps(fixture.payload_ref, sort_keys=True).lower()
        for fragment in forbidden_fragments:
            assert fragment not in encoded, f"{fixture.fixture_id} leaked {fragment}"


def test_budget_pause_stubs_are_documented_but_not_executable() -> None:
    """paused_by_budget remains an explicit non-executable contract gap."""
    stubs = [f for f in CONTRACT_FIXTURE_MANIFEST.fixtures if f.category == "budget_pause_stub"]
    assert len(stubs) >= 2
    for fixture in stubs:
        assert fixture.executable is False
        assert fixture.unsupported_state == "paused_by_budget"
        assert fixture.steps == ()


def test_validation_rejects_relaxed_category_minimums() -> None:
    """Callers cannot weaken the required category minimums inside a custom manifest."""
    manifest = CONTRACT_FIXTURE_MANIFEST.model_copy(update={"category_minimums": {}})
    with pytest.raises(ValueError, match="category_minimums"):
        validate_contract_fixture_manifest(manifest)


def test_validation_rejects_step_from_state_drift() -> None:
    """A step's explicit from_state must match the shared transition matrix."""
    fixture = CONTRACT_FIXTURE_MANIFEST.executable_fixtures[0]
    bad_step = fixture.steps[0].model_copy(update={"from_state": State.CHARGED})
    bad_fixture = fixture.model_copy(update={"steps": (bad_step, *fixture.steps[1:])})
    manifest = CONTRACT_FIXTURE_MANIFEST.model_copy(
        update={"fixtures": (bad_fixture, *CONTRACT_FIXTURE_MANIFEST.fixtures[1:])}
    )
    with pytest.raises(ValueError, match="from_state"):
        validate_contract_fixture_manifest(manifest)


def test_validation_rejects_budget_stub_side_effect_expectations() -> None:
    """paused_by_budget stubs must stay non-executable and side-effect-free."""
    stub_index = next(
        i
        for i, fixture in enumerate(CONTRACT_FIXTURE_MANIFEST.fixtures)
        if fixture.category == "budget_pause_stub"
    )
    stub = CONTRACT_FIXTURE_MANIFEST.fixtures[stub_index]
    bad_stub = stub.model_copy(update={"expected_outbox_count": 1})
    fixtures = list(CONTRACT_FIXTURE_MANIFEST.fixtures)
    fixtures[stub_index] = bad_stub
    manifest = CONTRACT_FIXTURE_MANIFEST.model_copy(update={"fixtures": tuple(fixtures)})
    with pytest.raises(ValueError, match="expected_outbox_count"):
        validate_contract_fixture_manifest(manifest)


@pytest.mark.parametrize(
    "payload_ref",
    [
        {"amount": "6.00"},
        {"max_solve_seconds": "60"},
        {"rate_per_second": "0.10"},
        {"prompt_ref": "raw prompt"},
        {"reference_id": "user@example.com"},
        {"reference_id": "Bearer sk-test-token"},
        {"reference_id": "13800138000"},
    ],
)
def test_public_payload_ref_validator_rejects_unsafe_refs(
    payload_ref: dict[str, object],
) -> None:
    """5.A.0 — runtime and fixtures share the same pointer-only safety rule."""
    with pytest.raises(ValueError):
        validate_payload_ref_safety(payload_ref, fixture_id="unit")


def test_public_payload_ref_validator_rejects_non_string_values() -> None:
    """JSON payload refs must store pointers as strings, not numbers/bools/raw objects."""
    with pytest.raises(ValueError, match="must be a string"):
        validate_payload_ref_safety({"reference_id": 123}, fixture_id="unit")


def test_public_payload_ref_validator_allows_empty_and_safe_pointer_refs() -> None:
    """Legacy empty refs and string pointer refs stay valid."""
    validate_payload_ref_safety({}, fixture_id="unit")
    validate_payload_ref_safety(
        {
            "reference_id": "4bca6785-92e4-4734-b1f4-451c4d5033da",
            "purpose": "solve",
            "confirmation_ref": "precharge-confirmed",
        },
        fixture_id="unit",
    )
