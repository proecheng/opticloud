---
story_key: 1-4-edu-tier-auto-activation
epic_num: 1
story_num: 1.4
epic_name: Account & Identity
status: ready-for-dev
priority: 🟢 Medium-High (FR A4; 学界飞轮 #3 GTM hook; activation half — full Starter plan effect is 5.B.2)
sizing: S (~2 hours; small change to signup + tests; reuses 5.A.2 bucket infrastructure)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L1291 (Story 1.4 — 教育版邮箱白名单自动激活 FR A4)
  - _bmad-output/planning/epics.md L1671 (Story 5.B.2 — 教育版 Starter 2K/月永久免费 B8)
  - apps/auth-service/src/auth_service/routes.py L72 (existing edu_tier auto-detect)
  - apps/billing-service/src/billing_service/buckets.py (BUCKET_EDU constant)
  - infra/local-init/03-billing-schema.sql + 05-bucket-backfill.sql (credit_transactions table + bucket column)
dependencies:
  upstream:
    - 0-6-auth-scaffold (done) — signup detects edu_tier via email suffix
    - 5-a-2-credits-balance-buckets (done) — `bucket="edu"` slot available
  downstream:
    - 5-b-2-edu-starter-permanent-free — monthly refill mechanism (out of this story's scope)
---

# Story 1.4 — Edu Tier Email Whitelist Auto-Activation (FR A4)

## User Story

**As** a 大学生 / 学者 signing up with my `.edu` or `.ac.cn` email
**I want** the system to automatically grant me `edu_tier=true` AND seed my account with the equivalent of one month's Starter credits (¥2000 in `bucket="edu"`) so I can immediately try the product
**so that** I don't have to wait for verification or topup before solving my first LP — confirming the "免费 Starter 2K/月永久" promise on the marketing page within seconds of signup.

## Why this story

Signup (Story 0.6) already detects `edu_tier` via the email suffix and writes it to the `users` table. But the user receives NO credits — they hit the regular J1 demo flow which lazy-seeds ¥50 to `bucket="signup"` on first /charges call. From the academic user's perspective, the "永久免费 Starter 2K/月" promise is invisible.

This story adds the **value half**: on signup, if `edu_tier=true`, write a `credit_transactions` row of `+2000.00` to `bucket="edu"`. The user can then visit `/auth/api-keys` → create a key → use it → see ¥2000 of edu credits drain naturally as they solve.

Monthly refill (the "/月" part) is **5.B.2 scope** — requires the plan system. v1 seeds once, "permanent" means "won't be drained by month-end logic since 5.B.2 doesn't exist yet."

## Out of scope

- **Monthly refill cron** — 5.B.2; requires plan system + scheduled job (M3)
- **Pro 30d trial** — 5.B.3 (mentioned in 5.B.2 AC but separate story)
- **Email verification (OTP-style for first-signup proof)** — current 0.6 stub trusts the email at signup; M3 will add an OTP confirmation step
- **`.edu.cn` (Chinese .edu)** — only `.edu` and `.ac.cn` per the user story; future PR may broaden
- **Domain blocklist** (e.g., `student.edu` is suspicious) — risk control story 1.5
- **Web UX badge** — the response shape already returns `edu_tier: bool`; frontend can render a 教育版 badge whenever needed (defer to a UI polish PR)

## Acceptance Criteria

### AC1: Signup writes edu-bucket credit on edu_tier=true

In `apps/auth-service/src/auth_service/routes.py:signup`:
- After the existing `User(phone=..., email=..., edu_tier=edu_tier)` and audit log:
- If `edu_tier=True`: INSERT a row into `credit_transactions` with:
  - `user_id = user.id`
  - `saga_id = NULL`
  - `amount = 2000.00` (or `settings.edu_signup_seed_amount`, configurable)
  - `kind = "topup"` (legacy label — matches j1_demo_seed pattern; the bucket column carries the semantic)
  - `bucket = "edu"`
  - `currency = "CNY"`
  - `metadata = {"source": "edu_tier_signup"}`
  - `created_at = NOW()`

Implementation choice: **raw SQL INSERT** in auth-service. Reasoning: auth-service doesn't import billing's ORM models (clean service boundary). Same DB, same connection pool. The audit_logs table is already cross-table-written from auth-service, so this is consistent.

### AC2: Config — `edu_signup_seed_amount`

Add to auth-service `config.py`:
```python
edu_signup_seed_amount: str = Field(
    default="2000.00",
    alias="EDU_SIGNUP_SEED_AMOUNT",
    description="CNY credited to bucket='edu' on .edu/.ac.cn signup (FR A4)",
)
```

String type for Decimal precision (matches existing `j1_demo_seed_amount` pattern).

### AC3: Audit log captures the seed

Extend the existing AuditLog INSERT in signup to include the seed amount in metadata when edu_tier=true:
```python
audit_metadata={
    "edu_tier": edu_tier,
    "edu_signup_seed_amount": settings.edu_signup_seed_amount if edu_tier else None,
}
```

This lets ops trace edu account creation + value granted for audit + compliance.

### AC4: Non-edu signup unchanged

For users WITHOUT `.edu` or `.ac.cn` email:
- `edu_tier = False` (existing behavior)
- NO credit_transactions row written (no seed)
- The lazy-seed on first /charges call still gives them ¥50 to `bucket="signup"` (existing 5.A.1 behavior)

Verified by AC6 #5.

### AC5: Balance API reflects the edu seed

After an edu signup:
- `GET /v1/billing/balance` returns `total = "2000.00"`, `buckets[edu].balance = "2000.00"`, others = `"0.00"`
- This is automatic — no billing-service code change needed. The new credit_transactions row flows naturally into `_balance_buckets_for()` from 5.A.2.

### AC6: Backend tests

**Extend `apps/auth-service/tests/test_login_routes.py`** (or signup-focused file if preferred — at impl time):

1. `test_edu_dotedu_email_creates_user_with_edu_tier_true_and_seed` — signup with `student@stanford.edu` → user.edu_tier=true; balance API shows edu=2000.00
2. `test_edu_dotaccn_email_creates_user_with_edu_tier_true_and_seed` — `.ac.cn` variant (e.g. `prof@pku.ac.cn`) → same outcome
3. `test_dotedu_dot_in_subdomain_also_activates` — `student@cs.mit.edu` (`.edu.` in middle, not at end — current code uses `endswith()` so this won't activate; but FR A4 says ".edu / .ac.cn 邮箱" which CAN include subdomains). The existing code uses `".edu." in body.email` to catch this. Test verifies this branch.
4. `test_regular_signup_no_edu_no_seed` — `user@gmail.com` → edu_tier=false; balance API shows all buckets 0.00 (no seed)
5. `test_edu_seed_amount_matches_config` — change `EDU_SIGNUP_SEED_AMOUNT` env to `"500.00"` via monkeypatch; new signup gets ¥500 in edu bucket
6. `test_edu_signup_audit_log_includes_seed_amount` — query audit_logs for the signup action; metadata has `edu_signup_seed_amount = "2000.00"`

### AC7: Quality gates

- `uv run ruff check apps packages` → 0 errors
- `uv run ruff format --check apps packages` → 0 changes needed
- `uv run mypy apps packages` → 0 errors
- `pnpm -C apps/web build` → 0 errors (no FE changes; regression guard)
- All Python regression tests pass; auth-service 21 → 27 (+6)

### AC8: NFR alignment

- **FR A4** ✅ AC1 + AC6 implement + verify auto-activation
- **NFR-O3** (audit log): AC3 metadata extended
- **NFR-S** (cross-table write safety): raw SQL INSERT goes through the same SQLAlchemy session as the user INSERT → transactional atomicity (either both succeed or both rollback)
- **NFR-P1** (signup P95): +1 INSERT statement; <1ms added; no impact

## Tasks

### T1: Config + signup logic (0.5h)
1. Add `edu_signup_seed_amount` to `auth_service.config.AuthSettings`
2. In `routes.signup`, after creating the user and audit log:
   - If `edu_tier=True`: raw SQL INSERT into `credit_transactions` with the edu bucket fields per AC1
3. Extend audit_metadata per AC3

### T2: Tests (1h)
1. New test cases in `test_login_routes.py` (or new file `test_edu_signup.py` if scope grows)
2. Use existing `signed_in_jwt`-style helpers
3. Verify via direct DB query for the credit_transactions row (or via balance API)

### T3: Quality gates + sprint sync + PR (0.5h)
1. Run AC7 gates
2. Update sprint-status.yaml + memory
3. Commit + push + PR
4. CI green → squash merge

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Hardcoded ¥2000 may not match future plan structure | AC2 makes it configurable via env; M3 plan system will switch to monthly refill cron with this as the per-period amount |
| Edu user can spam-signup with disposable .edu emails to drain free credits | Story 1.5 risk control + future "email domain reputation" checks; v1 demo accepts the risk (no public exposure yet) |
| `.edu.` substring match (existing code in 0.6) is fuzzy — catches `something.edu.bogus.com` | The substring match is the existing 0.6 behavior; 1.4 doesn't change detection logic. Documented as a known soft spot; M3 hardens with explicit suffix list + DNS validation |
| Raw SQL INSERT bypasses ORM — if credit_transactions schema changes, this breaks silently | Risk is small (schema changes are reviewed) + AC6 #1/#2 tests would catch any mismatch immediately |
| Edu seed in `bucket="edu"` won't drain naturally because all debits hit `bucket="monthly"` (per 5.A.2 AC8) — user sees ¥2000 frozen | Documented in 5.A.2 as accepted v1 behavior; user's TOTAL balance shows ¥2000, charges go into monthly creating negative balance; total enforcement still works. Per-bucket debit priority is 5.A.3+ scope (deferred). |

## Non-Functional Requirements Mapping

- **FR A4** ✅ AC1 implements; AC6 verifies
- **FR B8** (partial) — activation half; monthly refill half is 5.B.2
- **NFR-O3** ✅ audit metadata in AC3
- **NFR-S** ✅ transactional via shared session

## Definition of Ready

- ✅ signup detects edu_tier from 0.6
- ✅ bucket column from 5.A.2 + BUCKET_EDU constant
- ✅ Auth test infrastructure from 1.2 (conftest.py)
- ✅ All 3 review rounds applied (next step)

## Definition of Done

- All 8 ACs pass
- Test counts: auth-service 21 → 27 (+6)
- CI green on PR
- sprint-status.yaml: `1-4-edu-tier-email-whitelist: done`
- Memory updated
- Manual smoke: signup with `student@example.edu` → call GET /v1/billing/balance → see edu=2000.00

## Sign-off

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Auth Lead | TBA | ☐ | — |
| Billing Lead | TBA | ☐ | — |
| Academic GTM | TBA | ☐ | — |

> Owner committee deferred per M0 skip.
