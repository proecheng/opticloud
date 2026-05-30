"""Topup policy helpers — Story 5.A.6."""

from __future__ import annotations

from decimal import Decimal
from typing import Final

SUPPORTED_TOPUP_AMOUNTS: Final[frozenset[Decimal]] = frozenset(
    {
        Decimal("10.00"),
        Decimal("50.00"),
        Decimal("100.00"),
        Decimal("500.00"),
    }
)


def normalize_topup_amount(amount: Decimal) -> Decimal:
    """Return a 2-decimal topup amount if it matches a supported pack."""
    normalized = Decimal(str(amount)).quantize(Decimal("0.01"))
    if amount != normalized or normalized not in SUPPORTED_TOPUP_AMOUNTS:
        allowed = ", ".join(f"{value:.2f}" for value in sorted(SUPPORTED_TOPUP_AMOUNTS))
        raise ValueError(f"unsupported topup amount {amount}; allowed packs: {allowed}")
    return normalized


__all__ = ["SUPPORTED_TOPUP_AMOUNTS", "normalize_topup_amount"]
