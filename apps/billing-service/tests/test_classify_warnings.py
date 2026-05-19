"""classify_warnings boundary tests — Story 5.A.5 AC8 rows 1-6.

Pure-function tests, no DB, no fixtures beyond pytest.parametrize.
"""

from __future__ import annotations

from decimal import Decimal

from billing_service.pricing import Warning, classify_warnings

_P5 = Decimal("3.00")
_RATIO = Decimal("1.00")


def _classify(estimated: str, balance: str) -> list[Warning]:
    return classify_warnings(
        estimated_amount=Decimal(estimated),
        balance=Decimal(balance),
        p5_call_threshold=_P5,
        balance_low_ratio=_RATIO,
    )


def test_no_warnings_cheap_with_high_balance() -> None:
    """AC8 row 1: estimated 1.00, balance 50.00 → no warnings."""
    assert _classify("1.00", "50.00") == []


def test_p5_call_only_high_cost_balance_fine() -> None:
    """AC8 row 2: estimated 6.00, balance 50.00 → p5_call only."""
    warnings = _classify("6.00", "50.00")
    assert len(warnings) == 1
    assert warnings[0].kind == "p5_call"
    assert warnings[0].remediation_hint_key == "warnings.p5_call"
    assert "6.00" in warnings[0].message
    assert "3.00" in warnings[0].message


def test_balance_low_only_cheap_call_low_balance() -> None:
    """AC8 row 3: estimated 1.00, balance 0.50 → balance_low only."""
    warnings = _classify("1.00", "0.50")
    assert len(warnings) == 1
    assert warnings[0].kind == "balance_low"
    assert warnings[0].remediation_hint_key == "warnings.balance_low"


def test_combined_p5_and_balance_low_merges_into_one_warning() -> None:
    """AC8 row 4: estimated 6.00, balance 3.00 → p5_call_and_balance_low single warning."""
    warnings = _classify("6.00", "3.00")
    assert len(warnings) == 1
    assert warnings[0].kind == "p5_call_and_balance_low"


def test_at_threshold_inclusive_triggers_p5() -> None:
    """AC8 row 5: estimated == threshold (3.00) → p5_call (inclusive)."""
    warnings = _classify("3.00", "50.00")
    assert len(warnings) == 1
    assert warnings[0].kind == "p5_call"


def test_balance_equal_to_estimated_no_balance_low_exclusive() -> None:
    """AC8 row 6: balance == estimated → NO warnings (exclusive)."""
    assert _classify("0.50", "0.50") == []
