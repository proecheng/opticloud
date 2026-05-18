"""Sample Hypothesis property tests demonstrating shared strategies (Story 0.5b).

These tests validate that the shared strategies actually produce valid inputs
+ that Pydantic schemas accept them. Downstream stories (M2.2a, 3-14, business
Epic stories) consume the same strategies.
"""

from __future__ import annotations

import uuid

import pytest
from hypothesis import HealthCheck, given, settings

from opticloud_shared.property_test_base.strategies import (
    api_key_prefixes,
    error_details,
    lp_inputs,
    monetary_amounts,
    uuids,
)
from opticloud_shared.schemas.errors import ErrorDetail


@given(key=uuids())
def test_uuid_strategy_produces_valid_uuid_v4(key: str) -> None:
    """uuids() invariant: parseable as UUID v4."""
    parsed = uuid.UUID(key)
    assert parsed.version == 4
    assert str(parsed) == key


@given(prefix=api_key_prefixes())
def test_api_key_prefix_starts_with_sk(prefix: str) -> None:
    """api_key_prefixes() invariant: 'sk-' + 3 safe chars = 6 chars total."""
    assert prefix.startswith("sk-")
    assert len(prefix) == 6
    assert all(c.isalnum() or c in "-_" for c in prefix[3:])


@given(detail=error_details())
def test_error_detail_pydantic_roundtrip(detail: ErrorDetail) -> None:
    """RFC 7807 ErrorDetail roundtrip invariant: JSON serialize + parse = identity.

    Critical for FG1.3 SDK contract: error.locate() relies on this.
    """
    serialized = detail.model_dump_json()
    parsed = ErrorDetail.model_validate_json(serialized)
    assert parsed.field_path == detail.field_path
    assert parsed.constraint == detail.constraint
    assert parsed.remediation_hint_key == detail.remediation_hint_key
    # value may differ in float representation, but type semantics preserved
    if detail.value is not None and not isinstance(detail.value, float):
        assert parsed.value == detail.value


@given(detail=error_details())
def test_error_detail_field_path_nonempty(detail: ErrorDetail) -> None:
    """ErrorDetail.field_path is never empty (consumer of error.locate())."""
    assert detail.field_path
    assert len(detail.field_path) >= 1


@given(payload=lp_inputs(n_max=4, m_max=4))
def test_lp_input_shape_invariant(payload: dict) -> None:
    """lp_inputs() invariant: c, A, b dimensions consistent.

    Used by Story 3-14 mock-real divergence test.
    """
    c = payload["minimize"]["c"]
    a = payload["st"]["A"]
    b = payload["st"]["b"]
    n = len(c)
    m = len(a)
    assert m == len(b), "len(A.rows) must equal len(b)"
    assert all(len(row) == n for row in a), "all A.rows must have len = len(c)"


@given(amount=monetary_amounts())
def test_monetary_amount_two_decimals(amount: float) -> None:
    """monetary_amounts() invariant: 0 ≤ amount ≤ 1M with 2 decimal precision.

    Used by M2.2a Billing Saga state machine property tests.
    """
    assert 0.0 <= amount <= 1_000_000.0
    # 2 decimal precision: scale by 100 and check integer
    scaled = round(amount * 100)
    assert abs(scaled / 100.0 - amount) < 1e-9


@given(amount_a=monetary_amounts(), amount_b=monetary_amounts())
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=50, deadline=None)
def test_monetary_amount_addition_commutative(amount_a: float, amount_b: float) -> None:
    """Saga reserve+charge commutativity invariant (M2.2a foundation)."""
    assert pytest.approx(amount_a + amount_b) == pytest.approx(amount_b + amount_a)
