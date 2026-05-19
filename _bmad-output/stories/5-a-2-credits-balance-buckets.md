---
story_key: 5-a-2-credits-balance-buckets
epic_num: 5
story_num: A.2
epic_name: Billing — Credits & Saga
status: ready-for-dev
priority: 🟢 High (FR B1 必上; UX-DR1 prerequisite for showing the 4-bucket CreditsBalanceBucket component in the demo)
sizing: M (~4 hours; schema migration + balance route extension + tests; no orchestrator change)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L1629 (Story 5.A.2 — Credits 余额按桶 B1)
  - _bmad-output/planning/prd.md L1505 (FR B1 — 用户 can view Credits 余额按桶 月度/注册/教育/加油包)
  - packages/ui/src/components/CreditsBalanceBucket/index.tsx (Tier 1 component — already takes `buckets: CreditsBucket[]`)
  - apps/billing-service/src/billing_service/routes.py L80 (existing `_balance_for` + `_seed_demo_balance` to extend)
  - apps/billing-service/src/billing_service/models.py (CreditTransaction — needs new `bucket` column)
  - infra/local-init/03-billing-schema.sql (existing credit_transactions DDL — extends with bucket column)
dependencies:
  upstream:
    - 5-a-0a-saga-implementation (done) — credit_transactions table + Saga orchestrator
    - 5-a-1-j1-credits-charge-modal (done) — lazy-seed `j1_demo_seed` rows; existing balance endpoint
    - 5-a-4-per-formula-charging-capped (done) — new ledger kinds refund_partial / refund_reversal — they default to monthly bucket here
    - 0-9-ui-tier1-stubs (done) — CreditsBalanceBucket component scaffolded
  downstream:
    - 5-a-3-preview-cap-warning — uses per-bucket balance for "balance < estimate" calc nuance
    - 5-a-6-topup-flow — writes to bucket="topup" with never-expires semantics
    - 5-b-1-five-plans — monthly bucket refilled by plan tier
    - 5-b-2-edu-tier-starter-permanent-free — writes to bucket="edu"
---

# Story 5.A.2 — Credits 余额按桶 (B1)

## User Story

**As** a paying user viewing my Credits balance
**I want** the dashboard / demo page to show my balance broken down into 4 buckets (**月度 / 注册 / 教育 / 加油包**) with a total, instead of a single opaque number
**so that** I can see at a glance what's expiring soon (monthly), what's permanent (topup), what came from signup vs paid promo — and trust the billing system because nothing is hidden in a single sum.

## Why this story

FR B1 is **v1 必上**. The UI component `CreditsBalanceBucket` (Tier 1, already scaffolded in Story 0.9) takes a `buckets: CreditsBucket[]` prop. Today the only billing endpoint is `GET /v1/billing/balance` which returns a single `balance` string — there's nothing to feed `buckets`.

This story closes the gap:
1. Adds a `bucket` column to `credit_transactions` (default `"monthly"`)
2. Backfills/tags the existing lazy-seed rows (Story 5.A.1's `j1_demo_seed`) to `bucket="signup"`
3. Extends `GET /v1/billing/balance` to compute and return per-bucket sums
4. Wires the demo page (and future Dashboard) to consume the new shape

This is **VIEW-only** scope. Debit-priority logic (which bucket to drain first) is deferred to 5.A.3+ — for v1 all debits hit `bucket="monthly"`, which can go negative if signup or topup balances are positive. Total balance check in `/charges` still enforces the overall ≥ 0 rule via the existing `_balance_for` sum.

## Out of scope

- **Debit priority** (drain monthly first, then signup, then edu, then topup) → 5.A.3 / 5.A.6 — for v1, all debits land in `monthly`
- **Bucket expiry** (monthly resets at refill, edu refills on tier; topup never expires) → 5.B.1 plans + 5.A.6 topup; v1 just shows the buckets, doesn't enforce expiry
- **Topup writes** (purchasing a top-up creates `bucket="topup"` rows) → 5.A.6 real-money topup flow; v1 has no topup endpoint
- **Edu tier writes** → 5.B.2 教育版 Starter permanent-free; v1 has no edu lifecycle
- **Plan-based monthly refill cron** → 5.B.1; v1 has no monthly refill
- **Bucket-aware reconciliation** — daily diff job per bucket → 5.A.7
- **CreditsBalanceBucket UI integration** into a Dashboard page — v1 only updates the existing `/demo/charge` page to render the buckets (simpler, doesn't require a new route)

## Acceptance Criteria

### AC1: Schema — new `bucket` column

`infra/local-init/05-bucket-backfill.sql` (new file; idempotent so re-running is safe):

```sql
-- Story 5.A.2 — add bucket column for FR B1 (4 buckets per user).
ALTER TABLE credit_transactions
    ADD COLUMN IF NOT EXISTS bucket VARCHAR(32) NOT NULL DEFAULT 'monthly';

-- Backfill: tag the existing lazy-seed rows from Story 5.A.1.
UPDATE credit_transactions
   SET bucket = 'signup'
 WHERE bucket = 'monthly'
   AND metadata ->> 'source' = 'j1_demo_seed';

-- Index for fast per-bucket balance computation (B1 query path).
CREATE INDEX IF NOT EXISTS idx_credit_tx_user_bucket
    ON credit_transactions(user_id, bucket);
```

- `ADD COLUMN IF NOT EXISTS` makes the migration idempotent on existing DBs
- Backfill is bounded: only updates rows where `bucket='monthly'` (default) AND metadata identifies them as J1 seed
- New index supports the per-bucket GROUP BY query

### AC2: ORM model — `bucket: Mapped[str]`

Add to `CreditTransaction` in `models.py`:
```python
bucket: Mapped[str] = mapped_column(String(32), nullable=False, default="monthly")
```

The model default is `"monthly"` matching the DB default. Existing rows construct CreditTransaction without `bucket=...` arg → ORM uses the default → DB also has the default. Back-compat.

### AC3: 4 canonical bucket names + i18n labels

In a new constant module `apps/billing-service/src/billing_service/buckets.py`:
```python
from typing import Final

BUCKET_MONTHLY: Final[str] = "monthly"
BUCKET_SIGNUP: Final[str] = "signup"
BUCKET_EDU: Final[str] = "edu"
BUCKET_TOPUP: Final[str] = "topup"

ALL_BUCKETS: Final[tuple[str, ...]] = (BUCKET_MONTHLY, BUCKET_SIGNUP, BUCKET_EDU, BUCKET_TOPUP)

BUCKET_LABELS_ZH: Final[dict[str, str]] = {
    BUCKET_MONTHLY: "月度",
    BUCKET_SIGNUP: "注册",
    BUCKET_EDU: "教育",
    BUCKET_TOPUP: "加油包",
}

BUCKET_EXPIRES_HINT_ZH: Final[dict[str, str | None]] = {
    BUCKET_MONTHLY: "月度刷新",
    BUCKET_SIGNUP: "首次充值前有效",
    BUCKET_EDU: "教育版有效",
    BUCKET_TOPUP: "永不过期",  # FR B9
}
```

Always returning all 4 buckets (even with zero balance) keeps the UI stable — `CreditsBalanceBucket` always renders 4 rows.

### AC4: BalanceResponse extended (back-compat)

Schema additions in `schemas.py`:
```python
class BucketBalance(BaseModel):
    """One per-bucket balance row in the response."""
    name: Literal["monthly", "signup", "edu", "topup"]
    label_zh: str
    balance: str                    # Decimal-as-string, 2 decimals
    expires_hint: str | None = None

class BalanceResponse(BaseModel):
    user_id: str
    balance: str                    # total — UNCHANGED (existing tests pass)
    currency: str = "CNY"
    last_transaction_at: datetime | None = None
    buckets: list[BucketBalance]    # NEW — always exactly 4 entries in canonical order
```

The `buckets` field is additive. Existing `BalanceResponse` consumers that don't read it ignore it (Pydantic is permissive on outbound).

### AC5: `_balance_for` extension — per-bucket sums

New helper in `routes.py`:
```python
async def _balance_buckets_for(session, user_id) -> dict[str, Decimal]:
    """Returns dict keyed by all 4 bucket names; missing buckets get 0.00."""
    stmt = (
        select(CreditTransaction.bucket, func.sum(CreditTransaction.amount))
        .where(CreditTransaction.user_id == user_id)
        .group_by(CreditTransaction.bucket)
    )
    rows = await session.execute(stmt)
    by_bucket = {row[0]: Decimal(str(row[1])) for row in rows.all()}
    return {name: by_bucket.get(name, Decimal("0")) for name in ALL_BUCKETS}
```

Single SELECT with GROUP BY — index in AC1 keeps it fast (< 10ms for typical user). Always returns all 4 keys (defaulting to 0).

### AC6: GET /v1/billing/balance returns buckets

Update `get_balance` route to include the buckets array:
```python
@billing_router.get("/balance", response_model=BalanceResponse)
async def get_balance(...):
    total = await _balance_for(session, user_id)
    by_bucket = await _balance_buckets_for(session, user_id)
    last = ...
    buckets_resp = [
        BucketBalance(
            name=name,
            label_zh=BUCKET_LABELS_ZH[name],
            balance=f"{by_bucket[name]:.2f}",
            expires_hint=BUCKET_EXPIRES_HINT_ZH[name],
        )
        for name in ALL_BUCKETS
    ]
    return BalanceResponse(
        user_id=str(user_id),
        balance=f"{total:.2f}",
        currency="CNY",
        last_transaction_at=last,
        buckets=buckets_resp,
    )
```

Total balance computed via existing `_balance_for` (sum of ALL kinds, ALL buckets) — keeps existing 0/422 logic untouched.

### AC7: Lazy-seed tagged as `bucket="signup"`

Update `_seed_demo_balance`:
```python
session.add(
    CreditTransaction(
        user_id=user_id,
        saga_id=None,
        amount=seed_amount,
        kind="topup",
        currency="CNY",
        bucket="signup",   # NEW — was implicit 'monthly' via default
        metadata_json={"source": "j1_demo_seed"},
        created_at=datetime.now(UTC),
    )
)
```

Reasoning: the J1 demo seed is conceptually a "first-time signup gift", so `bucket="signup"` is correct. The `kind="topup"` label is legacy from 5.A.1 (it predates buckets) — leaving as-is to avoid orchestrator regression; the dimension that matters for v1 display is `bucket`.

### AC8: Orchestrator-written rows default to `bucket="monthly"`

NO orchestrator code change in this story. The ORM default `bucket="monthly"` flows naturally:
- `service_success` writes `kind="charge", bucket="monthly"` — debit hits monthly
- `user_cancel` writes `kind="refund", bucket="monthly"` — refund credits monthly
- `downstream_reject_late` writes `kind="refund", bucket="monthly"`
- 5.A.4 route-written `refund_partial` / `refund_reversal` rows also default to monthly

Consequence: in v1 with a fresh demo user who has signup=¥50, the flow `POST /charges (¥6) → /confirm` produces:
  - signup: 50.00 (lazy-seed)
  - monthly: -6.00 (charge)
  - total: 44.00 ✅

After 5.A.6 ships, topup purchase will write `bucket="topup"` and total stays sound.

### AC9: Web demo wiring — render the bucket card

Update `apps/web/src/app/demo/charge/page.tsx`:
1. Update `BalanceResponse` TS interface in `lib/api.ts` to include `buckets: BucketBalance[]`
2. Import `CreditsBalanceBucket` from `@opticloud/ui`
3. Replace the simple `<p>¥{balance.toFixed(2)}</p>` "Your balance" section with:
   ```tsx
   <CreditsBalanceBucket
     buckets={balance.buckets.map(b => ({
       name: b.name,
       labelZh: b.label_zh,
       balance: Number(b.balance),
       expiresHint: b.expires_hint ?? undefined,
     }))}
   />
   ```
4. Keep total as a separate display for context

### AC10: Backend tests

**Extend `test_charge_routes.py`** with 4 new cases — each uses a **fresh `uuid.uuid4()` user** via `token_factory` to avoid cross-test state pollution (R2 Q2):
1. `test_balance_returns_all_four_buckets_zero_for_new_user` — GET /balance for fresh user returns all 4 buckets with balance="0.00" each (mirrors existing `test_get_balance_pure_no_seed` isolation pattern)
2. `test_balance_after_seed_signup_bucket_50_others_zero` — fresh user; POST /charges (amount=6, confirmed=True) triggers lazy-seed; subsequent GET /balance shows signup=50.00, monthly=0.00, edu=0.00, topup=0.00, total=50.00
3. `test_balance_after_confirm_signup_50_monthly_minus6` — fresh user; POST /charges + /confirm with amount=6, confirmed=True; subsequent GET /balance has signup=50.00, monthly=-6.00, edu=0, topup=0, total=44.00 (negative monthly is OK per AC8 reasoning)
4. `test_bucket_labels_zh_present_in_response` — any user; assert each bucket has the right `label_zh` ("月度" / "注册" / "教育" / "加油包") and that topup has `expires_hint="永不过期"` (FR B9 visible commitment)

**New `apps/billing-service/tests/test_buckets.py`** — pure-function unit tests:
1. `test_all_buckets_has_4_entries` — len(ALL_BUCKETS) == 4
2. `test_all_buckets_in_label_map` — every bucket has a zh label
3. `test_topup_expires_hint_is_never_expire` — assert BUCKET_EXPIRES_HINT_ZH["topup"] == "永不过期"

### AC11: Quality gates

- `uv run ruff check apps packages` → 0 errors
- `uv run ruff format --check apps packages` → 0 changes needed
- `uv run mypy apps packages` → 0 errors
- `pnpm -C apps/web build` → 0 errors (web demo refactored)
- ALL Python tests pass; billing 117 → 124 (+7 = 4 routes + 3 unit)

### AC12: NFR alignment

- **FR B1** (用户 can view Credits 余额按桶): AC4 + AC6 + AC9
- **FR B9** (加油包永不过期 visible commitment): AC3 expires_hint includes "永不过期" for topup
- **NFR-P1** (HTTP P95 < 300ms): GET /balance with bucket GROUP BY adds < 5ms (indexed); still well under 50ms target
- **NFR-A1** (PIPL): no new PII in bucket data
- **UX-DR1** (CreditsBalanceBucket Tier 1 component utilized): AC9 puts it on a real page

## Tasks

### T1: Schema migration + index (0.5h)
1. Create `infra/local-init/05-bucket-backfill.sql` per AC1 (idempotent ALTER + UPDATE + INDEX)
2. Test locally: `docker compose down -v && docker compose up -d`, verify the column appears via psql

### T2: ORM model + constants module (0.5h)
1. Add `bucket: Mapped[str]` to `CreditTransaction` model with `default="monthly"`
2. Create `apps/billing-service/src/billing_service/buckets.py` with the 4 constants + label/hint maps per AC3
3. Re-export from `__init__.py` for clean test imports

### T3: Schemas + routes update (1h)
1. Add `BucketBalance` Pydantic model to `schemas.py`
2. Extend `BalanceResponse` with `buckets: list[BucketBalance]`
3. New helper `_balance_buckets_for(session, user_id) -> dict[str, Decimal]` per AC5
4. Update `get_balance` route per AC6
5. Update `_seed_demo_balance` to write `bucket="signup"` per AC7
6. mypy strict pass

### T4: Backend tests (1h)
1. New `test_buckets.py` per AC10 — 3 unit tests
2. Extend `test_charge_routes.py` per AC10 — 4 route tests
3. Re-run billing suite — 117 → 124

### T5: Web demo wiring (0.5h)
1. Update `BalanceResponse` TS interface in `lib/api.ts`
2. Refactor `/demo/charge` page to render `CreditsBalanceBucket` per AC9
3. `pnpm build` regression guard

### T6: Quality gates + sprint sync + PR (0.5h)
1. Run AC11 quality gates
2. Update sprint-status.yaml
3. Update memory file
4. Commit + push + PR
5. Wait CI green; merge with squash

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Existing local DB has no `bucket` column; migration only runs on fresh init | `IF NOT EXISTS` in DDL; idempotent. CI is always fresh. Local devs: `docker compose down -v && docker compose up -d`; documented in commit body. |
| Backfill UPDATE could lock the table on a hot DB | v1 has < 1k rows; lock is sub-millisecond. M3 cutover plan (if billing volume grows): run in batches via `WHERE id < X` chunks; out-of-scope here. |
| Tests assume default `bucket="monthly"` from ORM — but if DB column lacks the DEFAULT, INSERT without explicit bucket fails | DDL says `NOT NULL DEFAULT 'monthly'`; ORM model also says `default="monthly"`. Dual safety. |
| Buckets array order matters for stable UI rendering | `ALL_BUCKETS` is a `tuple` constant; iteration order is fixed. Frontend doesn't sort. Documented. |
| Debit always hits monthly — user with signup=50 + monthly=0 sees monthly go negative after charge | **Accepted** for v1 — the per-bucket balance can be negative; the TOTAL balance (sum across buckets) is what's enforced in `/charges` 422 check. UI shows monthly=-6 + signup=50 = total 44. Clear to user. Debit priority logic (drain signup first) is 5.A.3+. |
| Hardcoded label_zh strings — i18n later | Yes; for v1 the Chinese strings are correct and consistent with prd/epics. i18n key migration is M3 scope. |

## Non-Functional Requirements Mapping

- **FR B1** ✅ AC1-AC9 implement the 4-bucket view end-to-end
- **FR B9** ✅ AC3 expires_hint surfaces "永不过期" for topup
- **NFR-P1** ✅ AC5 single SELECT with index; <10ms
- **UX-DR1** ✅ Tier 1 CreditsBalanceBucket actually used in the demo

## Definition of Ready

- ✅ CreditsBalanceBucket Tier 1 component exists from Story 0.9
- ✅ credit_transactions table exists from 5.A.0a
- ✅ /balance endpoint exists from 5.A.1
- ✅ All 3 review rounds applied (next step)

## Definition of Done

- All 12 ACs pass
- Test counts: billing 117 → 124 (+7)
- CI green on PR
- sprint-status.yaml updated; 5-a-2-credits-balance-buckets: done
- Memory updated
- Local demo: visit /demo/charge, see 4-bucket card with signup=50 + monthly/edu/topup=0 after seed
- Code review with full quality gates documented in commit body

## Sign-off (story-level)

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Architect | proposed by AI | ☐ | — |
| Billing Lead | TBA | ☐ | — |
| UX Lead | TBA | ☐ | — |

> Owner committee deferred per M0 skip.
