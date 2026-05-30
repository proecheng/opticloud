---
story_key: 5-a-6-topup-never-expire
epic_num: 5
story_num: A.6
epic_name: Billing — Credits & Topup
status: done
priority: Critical
type: billing ledger + payment-confirmation contract
created_by: bmad-create-story
created_at: 2026-05-30
sources:
  - _bmad-output/planning/epics.md (Story 5.A.6 / FR B9)
  - _bmad-output/planning/prd.md (FR B9, 402 topup recovery)
  - _bmad-output/planning/architecture.md (billing-service owns Credits / topup)
  - _bmad-output/stories/5-a-2-credits-balance-buckets.md
  - _bmad-output/stories/5-a-5-p5-warning-modal.md
  - _bmad-output/stories/5-a-7-reconciliation-cron.md
  - apps/billing-service/src/billing_service/routes.py
  - apps/billing-service/src/billing_service/saga_orchestrator.py
  - apps/billing-service/src/billing_service/reconciler.py
  - apps/billing-service/src/billing_service/buckets.py
---

# Story 5.A.6 — 加油包永不过期

## Story

**As** a paid OptiCloud user,
**I want** to buy a top-up pack that is credited into the topup bucket and never expires,
**so that** I can recover from insufficient Credits without worrying that paid top-up value silently disappears.

## Context

FR B9 requires "用户 can purchase top-up 永不过期". Story 5.A.2 already made the topup bucket visible and labeled "永不过期", but it intentionally deferred real topup writes. The current code has:

- `credit_transactions.bucket` with canonical bucket `topup`
- `GET /v1/billing/balance` returning bucket balances and `expires_hint`
- no topup endpoint
- no payment-gateway adapter in the repo

This story closes the ledger-side contract without pretending that Stripe / 微信支付 / 支付宝 are already integrated. The public user endpoint creates a pending topup request. Only an internal payment-confirmation endpoint may credit money into `credit_transactions(bucket='topup')`.

## Scope Decision

Implement a backend-first topup contract:

1. Public user path: `POST /v1/billing/topups` creates an idempotent pending topup request.
2. Internal payment path: `POST /v1/billing/topups/{topup_id}/confirm` credits the topup after trusted payment confirmation.
3. Ledger path: confirmed topups write `kind='topup'`, `bucket='topup'`, positive amount, and no expiry timestamp.
4. Balance path: one-year-old topup rows still contribute to balance and keep `expires_hint='永不过期'`.

Out of scope:

- Real Stripe / 微信支付 / 支付宝 checkout sessions.
- Payment webhook signature schemes beyond the existing internal shared-secret pattern.
- Subscription plans, monthly refill, refund UI, invoice UI, debit-priority rules.
- Turning `payment_reused` risk rule on; this story only preserves provider/payment refs for later risk work.

## Acceptance Criteria

1. Users can initiate a topup request.
   - `POST /v1/billing/topups` requires Bearer JWT.
   - Request body accepts `amount`, `currency='CNY'`, and a pointer-safe `reference_id`.
   - Amount is limited to supported CNY packs: 10, 50, 100, 500.
   - The route requires UUID `Idempotency-Key`, reuses existing billing idempotency semantics, and returns the same `topup_id` on exact replay.
   - Initiation does not credit the user balance.

2. Users cannot self-credit by calling the public endpoint.
   - Public topup initiation writes no `credit_transactions` row.
   - The only route that writes positive topup ledger rows requires internal shared-secret auth.
   - Missing or incorrect internal auth returns 401 or 503 and writes no ledger row.

3. Trusted payment confirmation credits the topup bucket exactly once.
   - `POST /v1/billing/topups/{topup_id}/confirm` accepts `payment_ref` and `provider`.
   - The route locks the topup Saga row, writes exactly one positive ledger row with `kind='topup'`, `bucket='topup'`, and amount equal to the requested pack.
   - Replaying the same confirmation returns success without adding a second ledger row.
   - Replaying with a different `payment_ref` after crediting returns 409 and does not add a row.

4. Topup value never expires.
   - Confirmed topup ledger metadata records `expires_at: null`.
   - Backdating the topup row by more than 365 days does not remove it from `GET /v1/billing/balance`.
   - The topup bucket response still includes `expires_hint='永不过期'`.

5. Reconciliation remains consistent.
   - Completed topup sagas reconcile as expected positive ledger delta `[amount, amount]`.
   - Existing solve-charge reconciliation bounds remain unchanged.
   - Reconciler does not flag confirmed topups as negative-charge drift.

6. Saga payload-ref safety is preserved.
   - Topup request payload_ref stores only pointer-safe string fields.
   - No amount, payment token, balance, phone, email, bank, card, prompt, raw input, or raw payload is written to `saga_instances.payload_ref`.
   - Topup amount remains in `saga_instances.amount` and ledger rows, matching the 5.A.0 separation rule.

7. Quality gates pass.
   - Focused billing topup tests pass.
   - Existing billing route / bucket / reconciler tests pass.
   - Ruff check and format check pass for touched Python files.
   - Mypy passes for `apps/billing-service`.

## Tasks / Subtasks

- [x] T1: Add topup amount policy and schemas (AC: 1, 4)
  - [x] Add supported topup pack constants and validation helper.
  - [x] Add `TopupCreateRequest`, `TopupConfirmRequest`, and `TopupResponse`.
  - [x] Include `bucket='topup'`, `expires_at=null`, and `expires_hint='永不过期'` in responses.

- [x] T2: Add internal payment-confirmation auth guard (AC: 2)
  - [x] Add a dedicated `require_internal_service` dependency using `BILLING_SERVICE_SHARED_SECRET`.
  - [x] Fail closed when the secret is unset.
  - [x] Keep existing user JWT behavior unchanged.

- [x] T3: Implement topup routes (AC: 1, 2, 3, 4, 6)
  - [x] Add `POST /v1/billing/topups`.
  - [x] Add `POST /v1/billing/topups/{topup_id}/confirm`.
  - [x] Use existing `SagaOrchestrator.start()` for idempotent pending topup requests.
  - [x] Lock the topup Saga during confirmation.
  - [x] Write one positive `credit_transactions` row to `bucket='topup'` only after internal confirmation.
  - [x] Emit a bounded `billing.topup.confirmed` outbox event.

- [x] T4: Update reconciler for topup Saga semantics (AC: 5)
  - [x] Extend `expected_bounds()` with a `saga_type` parameter while preserving the existing default.
  - [x] Treat completed `saga_type='topup'` as expected positive delta `[amount, amount]`.
  - [x] Add regression coverage.

- [x] T5: Add tests (AC: 1-6)
  - [x] Test initiation is idempotent and does not credit balance.
  - [x] Test amount pack validation and idempotency conflict on changed amount.
  - [x] Test internal auth is required for confirmation.
  - [x] Test confirmation credits topup bucket exactly once.
  - [x] Test conflicting payment refs do not double-credit.
  - [x] Test topup remains available after one-year backdate.
  - [x] Test completed topup reconciles without drift.
  - [x] Test payload_ref contains no amount/payment/balance fields.

- [x] T6: Run quality gates and update tracking (AC: 7)
  - [x] Run focused pytest.
  - [x] Run billing regression pytest.
  - [x] Run ruff and mypy for touched surfaces.
  - [x] Update Dev Agent Record, File List, Change Log, and story/sprint status.

## Senior Developer Review (AI)

Outcome: Approved after patches.

Findings and resolution:

- [x] [High] Topup amount validator originally quantized before membership check; values like `9.999` could become `10.00`. Fixed by requiring the raw Decimal to equal its 2-decimal normalized value before pack membership.
- [x] [Medium] `payment_ref` length validation alone allowed token-like strings. Fixed with a bounded safe-character pattern and regression test.
- [x] [Medium] `reference_id` was described as pointer-safe but not route-schema constrained. Fixed by requiring UUID format before the request reaches Saga persistence.

## Pre-Implementation Adversarial Review

### Round 1 — Boundary And Security Review

Findings:

1. A naive `POST /topup` that immediately adds Credits lets any authenticated user mint paid balance.
2. Reusing the solve-charge Saga transitions for topup would write charge/refund signs incorrectly.
3. Storing `payment_ref`, pack price, or provider payload in `payload_ref` could violate the 5.A.0 pointer-only rule.
4. A payment confirm replay can double-credit unless the route locks and checks existing ledger rows.

Revision after Round 1:

- Split public initiation from internal payment confirmation.
- Do not use `reserve` / `service_success` transitions for topup.
- Store only `reference_id` and `purpose='topup'` in `payload_ref`; keep amount in `saga.amount`.
- Require row-level lock and existing-ledger check before writing the topup credit.

### Round 2 — Drift And Expiry Review

Findings:

1. "Never expires" can drift into a UI-only claim if there is no test using an old row.
2. Existing balance helpers do not filter by time, but a future cleanup could accidentally add expiry filtering.
3. `expires_hint='永不过期'` on an empty bucket is already covered by 5.A.2, but not after a real topup write.
4. A `created_at + 365 days` test is insufficient if it only checks the ledger row, not the public balance endpoint.

Revision after Round 2:

- Add a test that confirms a topup, backdates the ledger row by more than 365 days, and reads `GET /balance`.
- Require response metadata `expires_at=null` and bucket hint `永不过期`.
- Keep no DB expiry column for topup; the invariant is "no expiry filter is applied to topup ledger rows".

### Round 3 — Data And Dependency Consistency Review

Findings:

1. Marking a topup Saga as `completed` would make the existing reconciler treat it like a negative charge and report false drift.
2. Leaving a confirmed topup Saga in `pending` would hide it from terminal-state reconciliation and break closure.
3. Adding a new state would conflict with ADR-0001 and 5.A.0c.
4. Payment provider data is not implemented, so the story must not claim real payment capture.

Revision after Round 3:

- Keep the 7-state machine unchanged.
- Mark confirmed topup Saga rows as `completed` manually only for the topup aggregate, with explicit reconciler support for `saga_type='topup'`.
- Add reconciler regression coverage for completed topups.
- Phrase the implementation as ledger-side payment-confirmation contract, not real external checkout integration.

## Dev Notes

### Existing Patterns To Reuse

- `validate_idempotency_key()` in `schemas.py`.
- `SagaOrchestrator.start()` for idempotent aggregate creation.
- `CreditTransaction` ledger as source of truth.
- `BUCKET_TOPUP` and `BUCKET_EXPIRES_HINT_ZH`.
- Existing RFC 7807 error response helper.
- Existing billing test client, JWT factory, and fresh-user helper pattern in `test_charge_routes.py`.

### Hard Boundaries

- Do not change `packages/shared-py/opticloud_shared/saga/state_machine.py`.
- Do not add a new topup state.
- Do not write topup amount into `payload_ref`.
- Do not credit balance from the public user-initiation route.
- Do not add external payment SDKs.
- Do not alter solve-charge ledger signs.

### Suggested Test Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_topup_routes.py apps/billing-service/tests/test_reconciler.py apps/billing-service/tests/test_charge_routes.py apps/billing-service/tests/test_buckets.py -q
uv run ruff check apps/billing-service
uv run ruff format --check apps/billing-service
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run mypy apps/billing-service
```

## Dev Agent Record

### Implementation Plan

1. Keep `POST /topups` as pending-only and non-crediting.
2. Add internal-only confirmation route that locks the topup Saga and writes a single positive `topup` ledger row.
3. Extend reconciler bounds for completed `saga_type='topup'` without changing charge bounds.
4. Cover idempotency, auth, no self-credit, no double-credit, one-year persistence, and payload-ref safety.

### Debug Log

- Initial red tests failed as expected on missing routes and missing reconciler topup semantics.
- Full billing suite passed after implementation.
- Post-review patches added strict amount precision, UUID `reference_id`, and safe-character `payment_ref` validation.

### Completion Notes

- Added ledger-side topup purchase contract with public pending request and internal payment-confirmation credit.
- Confirmed topup rows write `kind='topup'`, `bucket='topup'`, positive amount, and `expires_at=null`.
- Reconciler now treats completed topup sagas as positive exact-amount deltas.
- Existing charge, bucket, Saga, and reconciler behavior remains green.

### File List

- `_bmad-output/stories/5-a-6-topup-never-expire.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/billing-service/src/billing_service/auth_dep.py`
- `apps/billing-service/src/billing_service/reconciler.py`
- `apps/billing-service/src/billing_service/routes.py`
- `apps/billing-service/src/billing_service/schemas.py`
- `apps/billing-service/src/billing_service/topups.py`
- `apps/billing-service/tests/test_reconciler.py`
- `apps/billing-service/tests/test_topup_routes.py`

## Change Log

- 2026-05-30 — Story created with three adversarial review rounds and ready-for-dev scope.
- 2026-05-30 — Implemented topup ledger contract, post-implementation review patches, and validation; status set to done.

## Verification

- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_topup_routes.py apps/billing-service/tests/test_reconciler.py -q` — 19 passed
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/ -q` — 203 passed, 2 warnings
- `uv run ruff check apps/billing-service/src/billing_service apps/billing-service/tests/test_topup_routes.py apps/billing-service/tests/test_reconciler.py` — passed
- `uv run ruff format --check apps/billing-service/src/billing_service apps/billing-service/tests/test_topup_routes.py apps/billing-service/tests/test_reconciler.py` — passed
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run mypy apps/billing-service` — passed
