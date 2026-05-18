"""Per-formula charging math — Story 5.A.4 (B4).

Pure functions only — no DB, no side effects, no logging. Easy to unit test
deterministically across the boundary cases described in AC7.

Reading order:
- `compute_charge_amount` is the single public entry point
- All inputs are normalised to Decimal early via `Decimal(str(float))` to dodge
  binary-rep noise (D2 fix from review round 2)

Reasoning behind the per-second rate (¥0.10/sec for LP):
  0.10 ¥/sec × 60s = ¥6.00 — exactly the 5.A.1 demo hardcoded amount, so the
  existing /demo/charge UI keeps working with no change.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def compute_charge_amount(
    elapsed_seconds: float,
    max_solve_seconds: float,
    rate_per_second: Decimal,
    min_amount: Decimal,
    reserved_amount: Decimal,
) -> Decimal:
    """Per-formula charge, quantised to 2 decimals, clamped to [min, reserved].

    Args:
        elapsed_seconds: actual solver wall-time from LPSolveResult.solve_seconds
        max_solve_seconds: cap recorded on the Saga at reserve time
        rate_per_second: CNY/sec — Decimal for precision
        min_amount: floor to prevent zero-charge from sub-cent solves
        reserved_amount: defensive cap so we never exceed what we reserved

    Returns:
        Decimal('X.XX') in range [min_amount, reserved_amount], ROUND_HALF_UP.

    Behaviour:
        - elapsed clamped to [0, max_solve_seconds]
        - amount = elapsed_clamped × rate, quantised HALF_UP to 0.01
        - if amount < min_amount → return min_amount
        - if amount > reserved_amount → return reserved_amount
    """
    elapsed = Decimal(str(max(0.0, elapsed_seconds)))
    cap = Decimal(str(max(0.0, max_solve_seconds)))
    clamped = min(elapsed, cap)

    raw = clamped * rate_per_second
    quantised = raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if quantised < min_amount:
        return min_amount
    if quantised > reserved_amount:
        return reserved_amount
    return quantised


__all__ = ["compute_charge_amount"]
