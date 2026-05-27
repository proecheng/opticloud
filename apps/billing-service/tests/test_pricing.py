"""Per-formula charge math — Story 5.A.4 AC7 boundary tests.

Pure-function tests, no DB, no fixtures beyond pytest.parametrize.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from billing_service.pricing import compute_charge_amount

# Defaults match settings — kept inline so tests are isolated from config changes.
_RATE = Decimal("0.10")
_MIN = Decimal("0.01")
_RESERVED = Decimal("6.00")
_MAX = 60.0


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        pytest.param(5.0, Decimal("0.50"), id="typical_5s"),
        pytest.param(60.0, Decimal("6.00"), id="at_cap_60s"),
        pytest.param(70.0, Decimal("6.00"), id="over_cap_clamped_to_reserved"),
        pytest.param(0.0, Decimal("0.01"), id="zero_elapsed_floors_to_min"),
        pytest.param(0.05, Decimal("0.01"), id="sub_cent_005_floors_to_min"),
        pytest.param(0.04, Decimal("0.01"), id="sub_cent_004_floors_to_min"),
        pytest.param(7.5, Decimal("0.75"), id="exact_75_cent"),
        pytest.param(2.45, Decimal("0.25"), id="half_up_245_to_25"),
        pytest.param(2.44, Decimal("0.24"), id="half_up_244_to_24"),
    ],
)
def test_compute_charge_amount(elapsed: float, expected: Decimal) -> None:
    """AC7 rows 1-9 — deterministic boundary math."""
    result = compute_charge_amount(
        elapsed_seconds=elapsed,
        max_solve_seconds=_MAX,
        rate_per_second=_RATE,
        min_amount=_MIN,
        reserved_amount=_RESERVED,
    )
    assert result == expected, f"elapsed={elapsed} → {result} != {expected}"


def test_negative_elapsed_clamps_to_zero_then_floors_to_min() -> None:
    """Defensive: even with bad input (negative elapsed) we floor to min, never go negative."""
    result = compute_charge_amount(
        elapsed_seconds=-5.0,
        max_solve_seconds=_MAX,
        rate_per_second=_RATE,
        min_amount=_MIN,
        reserved_amount=_RESERVED,
    )
    assert result == _MIN


def test_zero_reserved_returns_zero_when_min_is_zero() -> None:
    """Edge: if both reserved and min are 0, output is 0 (no charge)."""
    result = compute_charge_amount(
        elapsed_seconds=5.0,
        max_solve_seconds=_MAX,
        rate_per_second=_RATE,
        min_amount=Decimal("0.00"),
        reserved_amount=Decimal("0.00"),
    )
    assert result == Decimal("0.00")


def test_discount_multiplier_halves_raw_amount_before_floor_and_reserved_clamp() -> None:
    """Story 3.10 — backtest discount applies after seconds cap and before clamps."""
    result = compute_charge_amount(
        elapsed_seconds=5.0,
        max_solve_seconds=_MAX,
        rate_per_second=_RATE,
        min_amount=_MIN,
        reserved_amount=_RESERVED,
        discount_multiplier=Decimal("0.5"),
    )
    assert result == Decimal("0.25")


def test_discount_multiplier_still_honors_min_floor() -> None:
    """Story 3.10 — a discounted sub-cent charge still floors to CHARGE_MIN_AMOUNT."""
    result = compute_charge_amount(
        elapsed_seconds=0.05,
        max_solve_seconds=_MAX,
        rate_per_second=_RATE,
        min_amount=_MIN,
        reserved_amount=_RESERVED,
        discount_multiplier=Decimal("0.5"),
    )
    assert result == _MIN
