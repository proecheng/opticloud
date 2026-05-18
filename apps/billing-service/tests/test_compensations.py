"""Compensation spec unit tests (no DB)."""

from __future__ import annotations

from billing_service.compensations import COMPENSATION_SPECS, spec_for
from opticloud_shared.saga import Compensation


def test_all_4_compensations_have_specs() -> None:
    """Each Compensation enum value (except NONE) has a spec."""
    expected = {
        Compensation.MARK_FAILED,
        Compensation.REFUND_AUTO,
        Compensation.RETRY_OUTBOX,
        Compensation.ESCALATE_OPS,
    }
    actual = {s.enum_value for s in COMPENSATION_SPECS}
    assert actual == expected


def test_spec_for_known_compensation() -> None:
    """spec_for returns the right spec."""
    spec = spec_for(Compensation.REFUND_AUTO)
    assert spec is not None
    assert spec.invoking_trigger == "user_cancel"
    assert spec.creates_credit_tx is True


def test_spec_for_unknown_returns_none() -> None:
    """spec_for returns None for Compensation.NONE (no spec)."""
    assert spec_for(Compensation.NONE) is None
