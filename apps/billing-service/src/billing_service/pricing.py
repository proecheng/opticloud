"""Per-formula charging math — Story 5.A.4 (B4) + 5.A.5 (B6).

Pure functions only — no DB, no side effects, no logging. Easy to unit test
deterministically across the boundary cases described in AC7 / 5.A.5 AC8.

Public surface:
- `compute_charge_amount`  — per-formula amount math (5.A.4)
- `classify_warnings`      — pre-charge guard rules (5.A.5)
- `Warning`                — dataclass returned by classify_warnings
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


def compute_charge_amount(
    elapsed_seconds: float,
    max_solve_seconds: float,
    rate_per_second: Decimal,
    min_amount: Decimal,
    reserved_amount: Decimal,
    discount_multiplier: Decimal = Decimal("1.0"),
) -> Decimal:
    """Per-formula charge, quantised to 2 decimals, clamped to [min, reserved].

    Args:
        elapsed_seconds: actual solver wall-time from LPSolveResult.solve_seconds
        max_solve_seconds: cap recorded on the Saga at reserve time
        rate_per_second: CNY/sec — Decimal for precision
        min_amount: floor to prevent zero-charge from sub-cent solves
        reserved_amount: defensive cap so we never exceed what we reserved
        discount_multiplier: Story 3.10 backtest discount, defaults to no discount

    Returns:
        Decimal('X.XX') in range [min_amount, reserved_amount], ROUND_HALF_UP.

    Behaviour:
        - elapsed clamped to [0, max_solve_seconds]
        - amount = elapsed_clamped × rate × discount_multiplier, quantised HALF_UP to 0.01
        - if amount < min_amount → return min_amount
        - if amount > reserved_amount → return reserved_amount
    """
    elapsed = Decimal(str(max(0.0, elapsed_seconds)))
    cap = Decimal(str(max(0.0, max_solve_seconds)))
    clamped = min(elapsed, cap)

    raw = clamped * rate_per_second * discount_multiplier
    quantised = raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if quantised < min_amount:
        return min_amount
    if quantised > reserved_amount:
        return reserved_amount
    return quantised


@dataclass(frozen=True)
class Warning:
    """Pre-charge guard warning — surfaces in /estimate response (Story 5.A.5)."""

    kind: str  # "balance_low" | "p5_call" | "p5_call_and_balance_low"
    message: str
    remediation_hint_key: str  # "warnings.{kind}"


_MESSAGE_TEMPLATES: dict[str, str] = {
    "balance_low": "Balance ¥{balance:.2f} is below estimated max charge ¥{estimated:.2f}",
    "p5_call": (
        "Estimated max charge ¥{estimated:.2f} exceeds the high-cost threshold ¥{threshold:.2f}"
    ),
    "p5_call_and_balance_low": (
        "Estimated max charge ¥{estimated:.2f} exceeds the high-cost threshold ¥{threshold:.2f} "
        "AND your balance ¥{balance:.2f} is insufficient"
    ),
}


def classify_warnings(
    estimated_amount: Decimal,
    balance: Decimal,
    *,
    p5_call_threshold: Decimal,
    balance_low_ratio: Decimal,
) -> list[Warning]:
    """Pre-charge guard classifier (Story 5.A.5 AC2).

    Returns 0 or 1 Warnings (never 2 — combined case is merged into a single
    `p5_call_and_balance_low` warning so the UI shows one warning row).

    Conditions:
      - p5_call:    estimated >= p5_call_threshold (inclusive)
      - balance_low: balance < (estimated × balance_low_ratio) (exclusive)
    """
    is_p5 = estimated_amount >= p5_call_threshold
    is_low = balance < (estimated_amount * balance_low_ratio)

    if is_p5 and is_low:
        kind = "p5_call_and_balance_low"
    elif is_p5:
        kind = "p5_call"
    elif is_low:
        kind = "balance_low"
    else:
        return []

    message = _MESSAGE_TEMPLATES[kind].format(
        balance=balance, estimated=estimated_amount, threshold=p5_call_threshold
    )
    return [Warning(kind=kind, message=message, remediation_hint_key=f"warnings.{kind}")]


__all__ = ["Warning", "classify_warnings", "compute_charge_amount"]
