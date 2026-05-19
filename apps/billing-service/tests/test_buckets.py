"""Unit tests for bucket constants (Story 5.A.2 AC10)."""

from __future__ import annotations

from billing_service.buckets import (
    ALL_BUCKETS,
    BUCKET_EXPIRES_HINT_ZH,
    BUCKET_LABELS_ZH,
    BUCKET_TOPUP,
)


def test_all_buckets_has_four_entries() -> None:
    """FR B1 — exactly 4 buckets (monthly / signup / edu / topup)."""
    assert len(ALL_BUCKETS) == 4
    assert set(ALL_BUCKETS) == {"monthly", "signup", "edu", "topup"}


def test_every_bucket_has_zh_label() -> None:
    """Each bucket has a Chinese label for UI display."""
    for name in ALL_BUCKETS:
        assert name in BUCKET_LABELS_ZH
        assert BUCKET_LABELS_ZH[name]  # non-empty


def test_topup_expires_hint_is_never_expire() -> None:
    """FR B9 visible commitment — topup bucket carries 永不过期 hint."""
    assert BUCKET_EXPIRES_HINT_ZH[BUCKET_TOPUP] == "永不过期"
