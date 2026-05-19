"""Credit bucket constants — Story 5.A.2 (FR B1).

Four canonical buckets per user. `bucket` column on `credit_transactions`
tags each ledger row with its source category so the dashboard can break
the total balance down for the user (FR B1).

Bucket-specific business rules deferred:
- MONTHLY refill schedule         → 5.B.1 plan-based pricing
- TOPUP never-expires enforcement → 5.A.6 topup flow
- EDU tier lifecycle              → 5.B.2 教育版

In v1 the orchestrator writes all charge/refund rows to MONTHLY by default
(ORM/DB column default). Lazy-seed (Story 5.A.1) writes to SIGNUP.
"""

from __future__ import annotations

from typing import Final

BUCKET_MONTHLY: Final[str] = "monthly"
BUCKET_SIGNUP: Final[str] = "signup"
BUCKET_EDU: Final[str] = "edu"
BUCKET_TOPUP: Final[str] = "topup"

ALL_BUCKETS: Final[tuple[str, ...]] = (
    BUCKET_MONTHLY,
    BUCKET_SIGNUP,
    BUCKET_EDU,
    BUCKET_TOPUP,
)

BUCKET_LABELS_ZH: Final[dict[str, str]] = {
    BUCKET_MONTHLY: "月度",
    BUCKET_SIGNUP: "注册",
    BUCKET_EDU: "教育",
    BUCKET_TOPUP: "加油包",
}

# FR B9 — 加油包永不过期 visible commitment.
BUCKET_EXPIRES_HINT_ZH: Final[dict[str, str | None]] = {
    BUCKET_MONTHLY: "月度刷新",
    BUCKET_SIGNUP: "首次充值前有效",
    BUCKET_EDU: "教育版有效",
    BUCKET_TOPUP: "永不过期",
}


__all__ = [
    "ALL_BUCKETS",
    "BUCKET_EDU",
    "BUCKET_EXPIRES_HINT_ZH",
    "BUCKET_LABELS_ZH",
    "BUCKET_MONTHLY",
    "BUCKET_SIGNUP",
    "BUCKET_TOPUP",
]
