"""Shared ledger-derived usage spend helpers for billing views."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Protocol


class SpendLedgerRow(Protocol):
    """Minimal ledger row shape required for usage-spend aggregation."""

    amount: Decimal
    kind: str


SPEND_KINDS: frozenset[str] = frozenset({"charge", "refund", "refund_partial", "refund_reversal"})


def actual_spend_from_signed_total(total: Decimal) -> Decimal:
    """Convert a signed charge-related ledger total into positive usage spend."""
    return max(Decimal("0"), -total)


def actual_spend(rows: Iterable[SpendLedgerRow]) -> Decimal:
    """Compute positive usage spend from charge-related ledger rows only."""
    total = sum((row.amount for row in rows if row.kind in SPEND_KINDS), start=Decimal("0"))
    return actual_spend_from_signed_total(total)


__all__ = ["SPEND_KINDS", "SpendLedgerRow", "actual_spend", "actual_spend_from_signed_total"]
