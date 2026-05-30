from __future__ import annotations

from collections import Counter

import opticloud_shared.saga as saga
from opticloud_shared.saga.contract_fixtures import (
    CONTRACT_FIXTURE_MANIFEST,
    SAGA_CONTRACT_VERSION,
    validate_contract_fixture_manifest,
)


def test_saga_contract_fixture_public_exports() -> None:
    """The cross-epic fixture API is importable without service or DB dependencies."""
    for name in (
        "SAGA_CONTRACT_VERSION",
        "SagaFixtureStep",
        "SagaContractFixture",
        "SagaFixtureManifest",
        "CONTRACT_FIXTURE_MANIFEST",
        "build_saga_contract_fixtures",
        "canonical_body_hash",
        "validate_contract_fixture_manifest",
    ):
        assert hasattr(saga, name)


def test_saga_contract_fixture_manifest_snapshot() -> None:
    """Lock the static contract surface consumed by 5.A.0c dry-run."""
    assert SAGA_CONTRACT_VERSION == "2026-05-30.saga-fixtures.v1"
    assert len(CONTRACT_FIXTURE_MANIFEST.fixtures) >= 50
    counts = Counter(f.category for f in CONTRACT_FIXTURE_MANIFEST.fixtures)
    assert counts["charge"] >= 10
    assert counts["refund"] >= 8
    assert counts["rollback"] >= 8
    assert counts["idempotency"] >= 8
    assert counts["timeout"] >= 8
    assert counts["cost_telemetry"] >= 8
    assert counts["budget_pause_stub"] >= 2
    validate_contract_fixture_manifest(CONTRACT_FIXTURE_MANIFEST)
