---
story_key: 5-b-1-five-plans-subscription
epic_num: 5
story_num: B.1
epic_name: Billing — Subscriptions + Education
status: done
priority: Critical
type: billing subscription + monthly credits refill
created_by: bmad-create-story
created_at: 2026-05-30
sources:
  - _bmad-output/planning/epics.md (Epic 5.B / Story 5.B.1)
  - _bmad-output/planning/prd.md (FR B3 / billing P0 risk / plan rate-limit table)
  - _bmad-output/planning/architecture.md (billing-service ownership / outbox / subscription DB topology / P23)
  - _bmad-output/planning/ux-design-specification.md (pricing dark-pattern guardrails)
  - _bmad-output/stories/5-a-9-charge-idempotency.md
  - apps/billing-service/src/billing_service/routes.py
  - apps/billing-service/src/billing_service/models.py
  - apps/billing-service/src/billing_service/schemas.py
  - apps/billing-service/src/billing_service/buckets.py
  - infra/local-init/03-billing-schema.sql
---

# Story 5.B.1 — 5 计划订阅

Status: done

## Story

**As** an authenticated OptiCloud user,
**I want** to select one of the five subscription plans: Free, Starter, Pro, Team, or Enterprise,
**so that** my active plan is persisted and the plan's monthly Credits are refilled into the monthly bucket exactly once per billing period.

## Context

Epic 5.A has already shipped the billing ledger, four credit buckets, charge/topup flows, and P23-style cached response behavior for charge creation. This story opens Epic 5.B by adding the subscription layer owned by billing-service.

The planning docs only define the five plan names and the high-level BDD acceptance criterion. They do not define final public prices or signed Enterprise terms. Therefore this story must not create buyer-facing pricing promises or real payment collection. It must create a runtime subscription contract that future payment, education, proration, invoice, and frontend stories can build on without corrupting the Credits ledger.

## Scope

1. Add a billing-service plan catalog for exactly five plan codes: `free`, `starter`, `pro`, `team`, `enterprise`.
2. Add persistent active subscription state for one active subscription per user.
3. Add authenticated APIs to list plans, read the current subscription, and create the first active subscription.
4. Add an idempotent monthly refill mechanism that writes positive `credit_transactions` rows with `bucket="monthly"` and `kind="monthly_refill"`.
5. Add an internal-only refill-due endpoint/function that advances due active subscriptions by monthly periods and refills once per period.
6. Emit billing outbox events when a subscription is activated and when monthly Credits are refilled.
7. Add focused tests proving five-plan coverage, cross-tenant/idempotency behavior, no duplicate refill, due-period refill, and existing charge/topup regression safety.

## Out of Scope

- Education permanent Starter and education Pro trial; those are Stories 5.B.2 and 5.B.3.
- Upgrade/downgrade and prorated billing; that is Story 5.B.4.
- Stripe, WeChat, Alipay, invoices, refunds, tax, VAT, PO, cancellation, or real payment gateway capture.
- Frontend pricing page or Console subscription UI.
- Public SLA promises, Enterprise legal terms, or buyer-facing price copy.
- Reworking existing charge/topup Saga IDs or the whole billing ID scheme to `sub_` ULIDs.

## Acceptance Criteria

1. `GET /v1/billing/plans` returns exactly five catalog items in stable order: Free, Starter, Pro, Team, Enterprise. Each item includes plan code, display labels, monthly Credits amount, rate-limit metadata copied from PRD, and whether commercial review/payment is external to this story.
2. `GET /v1/billing/subscriptions/current` is a pure read. A user with no persisted subscription receives an implicit Free current-plan response without creating a subscription row or credit transaction.
3. `POST /v1/billing/subscriptions` with a valid `Idempotency-Key` and one of the five plan codes creates the user's first active subscription, sets `current_period_start` to UTC now, sets `current_period_end` to one calendar month later, and returns the active subscription response.
4. Creating a paid/non-zero-credit subscription writes exactly one positive `credit_transactions` row:
   - `kind="monthly_refill"`;
   - `bucket="monthly"`;
   - `amount == plan.monthly_credits`;
   - metadata includes `subscription_id`, `plan_code`, `period_start`, `period_end`, and `trigger`.
5. The Free plan is valid. Its monthly refill amount is `0.00`; activation must not create a zero-value ledger row, but the subscription period is still tracked.
6. Same user + same `Idempotency-Key` + same body within TTL returns the cached subscription response and does not create another subscription, outbox event, or monthly refill row.
7. Same user + same `Idempotency-Key` + different body returns 409 RFC 7807 and leaves the original subscription/ledger untouched.
8. A different user reusing another tenant's `Idempotency-Key` returns 403 and never exposes the owner user's subscription response.
9. If a user already has an active subscription with the same plan, a later POST with a new idempotency key returns the existing active subscription without another refill.
10. If a user already has an active subscription with a different plan, POST returns 409 "plan change deferred" and does not mutate plan, period, ledger, or outbox. Plan change/proration remains Story 5.B.4.
11. The internal refill-due path requires `X-Internal-Service-Auth`, selects only active subscriptions whose `current_period_end <= as_of`, advances them by calendar-month periods, and writes at most one monthly refill ledger row for each new period.
12. Replaying the internal refill-due path for the same `as_of` is idempotent: no duplicate monthly refill rows, no period drift, and no extra outbox refill events.
13. Subscription activation and refill outbox payloads contain pointer-safe identifiers and accounting fields only; no JWT, phone/email, raw request body, payment token, or personal contact data is stored in subscription metadata or outbox payload.
14. Existing billing behavior remains unchanged: balance endpoint still returns the four canonical buckets, charges still debit the monthly bucket by default, signup lazy seed remains in signup, and topup remains never-expiring.
15. Quality gates pass:
    - focused subscription route tests;
    - existing charge idempotency, charge route, topup route, bucket, reconciler, and billing regression tests;
    - `uv run ruff check apps/billing-service`;
    - `uv run ruff format --check apps/billing-service`;
    - `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run mypy apps/billing-service`;
    - `git diff --check`.

## Tasks / Subtasks

- [x] T1: Add subscription schema and model (AC: 2-5, 9-13)
  - [x] Add idempotent SQL migration under `infra/local-init/`.
  - [x] Add `BillingSubscription` SQLAlchemy model with one active subscription per user.
  - [x] Keep raw SQL as schema owner; ORM only maps existing tables.

- [x] T2: Add plan catalog and period/refill helpers (AC: 1, 3-5, 11-12)
  - [x] Add `plans.py` with five plan definitions and PRD rate-limit metadata.
  - [x] Add calendar-month period advancement helper using stdlib only.
  - [x] Add reusable helper to apply monthly refill once per period.

- [x] T3: Add Pydantic schemas (AC: 1-13)
  - [x] Add plan catalog list response.
  - [x] Add subscribe request and subscription response.
  - [x] Add internal refill-due request/response.

- [x] T4: Add routes and idempotency behavior (AC: 2-13)
  - [x] Add `GET /plans`, `GET /subscriptions/current`, `POST /subscriptions`.
  - [x] Reuse `billing_idempotency_keys` with `response_body` for subscription POST caching.
  - [x] Check tenant ownership before returning cached response.
  - [x] Reject same key/different body as 409.
  - [x] Reject different-plan active subscription as 409.
  - [x] Add internal `POST /subscriptions/refill-due`.

- [x] T5: Preserve ledger and outbox consistency (AC: 4, 11-14)
  - [x] Refills write only to `bucket="monthly"`.
  - [x] Free zero refill writes no ledger row.
  - [x] Activation and refill emit outbox events in the same transaction.
  - [x] No sensitive fields in subscription metadata or outbox payloads.

- [x] T6: Tests and gates (AC: 1-15)
  - [x] Add `test_subscription_routes.py`.
  - [x] Cover catalog, implicit Free read, all five initial subscriptions, idempotent replay, conflict replay, cross-tenant key, same-plan no-op, different-plan 409, internal auth, due refill, due refill replay, pointer-safe metadata/outbox, and balance bucket impact.
  - [x] Run focused and full billing quality gates.
  - [x] Update Dev Agent Record, File List, Change Log, and sprint status.

## Pre-Implementation Adversarial Review

### Round 1 — Boundary And Business-Scope Review

Findings:

1. The planning docs name five plans but do not provide final approved public prices for all tiers. Implementing public price claims would create GTM/legal drift.
2. Real gateway payment capture is not implemented in Epic 5.A; activating a plan must not pretend Stripe/WeChat/Alipay money has settled.
3. Education permanent Starter and Pro trial have explicit later stories and must not be partially hidden inside the base subscription story.
4. Upgrade/downgrade mid-period is a separate proration story. If this story lets users mutate active plans freely, it can create incorrect paid-plan/refill accounting.

Revision after Round 1:

- Story scope is backend billing runtime only: plan catalog, first active subscription, current subscription read, and monthly refill.
- API responses may expose commercial-review/payment-mode metadata, but must not claim final public prices or gateway capture.
- Education, trial, proration, cancellation, invoices, refunds, and UI are explicit out of scope.
- Active different-plan changes return 409 until Story 5.B.4.

### Round 2 — Data Consistency And Ledger Review

Findings:

1. Monthly refills must be ledger rows, not a mutable balance field, or they bypass Epic 5.A's double-entry source of truth.
2. The existing monthly bucket is already used by charge debits by default. Refill rows must use the same bucket to keep FR B1 bucket totals meaningful.
3. A retry or scheduler replay can easily mint duplicate monthly Credits unless the implementation tracks the period already refilled.
4. Free has zero monthly Credits. Writing zero ledger rows would pollute reconciliation without changing balance.

Revision after Round 2:

- Add subscription fields for `current_period_start`, `current_period_end`, and `last_refilled_period_start`.
- Refill helper writes a positive `credit_transactions` row only when plan credits are greater than zero and the period has not already been refilled.
- Free marks the period as refilled without writing a zero amount row.
- Tests must assert exact ledger row counts and balance bucket effects.

### Round 3 — Dependency, Closure, And Drift Review

Findings:

1. Billing POST routes now have an established idempotency cache pattern from Story 5.A.9; subscription activation should reuse it rather than invent a parallel table.
2. Existing billing SQL is raw SQL first; adding only ORM models would fail fresh local environments.
3. Architecture mentions `sub_` IDs, but existing billing APIs expose UUID strings. Introducing a new ULID/prefix subsystem inside one story would be larger than the requirement and risk drift.
4. Cross-service observability expects outbox events for billing state changes. Subscription activation/refill should produce outbox events even though no payment gateway is integrated.

Revision after Round 3:

- Reuse `billing_idempotency_keys.response_body` for `POST /subscriptions` cached response.
- Add an idempotent SQL migration and SQLAlchemy mapping.
- Keep UUID primary keys for subscription rows in this story and document `sub_` public ID prefix as deferred until a shared ID utility exists.
- Emit `billing.subscription.activated` and `billing.subscription.refilled` outbox events in the same DB transaction as state/ledger writes.

## Dev Notes

### Existing Patterns To Reuse

- `require_user()` and `require_internal_service()` in `billing_service.auth_dep`.
- `validate_idempotency_key()` and the `billing_idempotency_keys.response_body` cache pattern from Story 5.A.9.
- `CreditTransaction` ledger sign convention: positive rows add Credits; charge rows are negative.
- `BUCKET_MONTHLY` from `billing_service.buckets`.
- `_balance_for()` and `_problem_response()` route helpers in `routes.py`.
- Existing ASGI route-test fixtures and JWT helper patterns from `test_charge_routes.py`, `test_charge_idempotency_routes.py`, and `test_topup_routes.py`.

### Architecture Compliance

- billing-service owns subscriptions and Credits ledger.
- Schema changes go into `infra/local-init/*.sql`; SQLAlchemy only maps them.
- Public responses remain naked objects or `{items: [...]}` for list endpoints.
- Authenticated user identity comes only from JWT/internal bridge, never from request body.
- Cross-service state notifications use outbox rows.
- Do not store raw request bodies, JWTs, phone/email, or payment secrets in DB JSON metadata.

### Suggested Plan Catalog

Use an internal runtime catalog, not buyer-facing final pricing:

| Code | Label | Monthly Credits | PRD Rate Limit Metadata |
|---|---|---:|---|
| `free` | Free | 0 | 3 RPS / 30 per min / 1 concurrent |
| `starter` | Starter | 2000 | 5 RPS / 200 per min / 3 concurrent |
| `pro` | Pro | 10000 | 20 RPS / 1000 per min / 10 concurrent |
| `team` | Team | 50000 | 100 RPS / 5000 per min / 30 concurrent |
| `enterprise` | Enterprise | 200000 | custom RPS / custom per min / custom concurrent |

Rationale: the only explicit monthly Credits value in planning is education Starter 2K/month. This story uses 2K as the base Starter runtime allowance and conservative higher internal allowances for Pro/Team/Enterprise. These values are implementation defaults, not public pricing/legal copy.

### File Structure Requirements

- `apps/billing-service/src/billing_service/plans.py`
- `apps/billing-service/src/billing_service/models.py`
- `apps/billing-service/src/billing_service/schemas.py`
- `apps/billing-service/src/billing_service/routes.py`
- `infra/local-init/11-billing-subscriptions.sql`
- `apps/billing-service/tests/test_subscription_routes.py`
- `_bmad-output/stories/sprint-status.yaml`

### Hard Boundaries

- Do not change existing charge, reserve, finalize, topup, or balance API behavior except adding subscription data where explicitly required by this story.
- Do not add a mutable balance table.
- Do not write zero-amount credit transactions.
- Do not allow different-plan changes in this story.
- Do not add a new payment provider dependency.
- Do not add frontend UI.
- Do not promise production SLA or approved public prices.

### Suggested Test Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_subscription_routes.py -q
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_subscription_routes.py apps/billing-service/tests/test_charge_idempotency_routes.py apps/billing-service/tests/test_charge_routes.py apps/billing-service/tests/test_topup_routes.py apps/billing-service/tests/test_buckets.py -q
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/ -q
uv run ruff check apps/billing-service
uv run ruff format --check apps/billing-service
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run mypy apps/billing-service
git diff --check
```

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Red phase: `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_subscription_routes.py -q` failed 14/14 with `404 Not Found` for missing subscription endpoints.
- Applied local migration: `$env:PGPASSWORD='opticloud_dev'; psql -h localhost -U opticloud -d opticloud_dev -f infra/local-init/11-billing-subscriptions.sql` succeeded.
- Green phase: focused subscription tests reached 14 passed, then expanded to 15 passed after multi-period refill edge coverage.
- Focused regression: subscription + charge idempotency + charge routes + topup routes + bucket tests passed, 57 passed / 4 FastAPI deprecation warnings.
- Full billing regression: `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/ -q` passed, 230 passed / 4 FastAPI deprecation warnings.
- Static gates: `uv run ruff check apps/billing-service`, `uv run ruff format --check apps/billing-service`, mypy, and `git diff --check` passed.

### Completion Notes List

- Added the 5-plan runtime catalog (`free`, `starter`, `pro`, `team`, `enterprise`) with PRD rate-limit metadata and internal monthly Credits defaults.
- Added `billing_subscriptions` raw SQL migration and ORM mapping with one active subscription per user.
- Added authenticated plan catalog/current subscription/subscribe APIs and internal-only refill-due API.
- Initial subscription activation writes monthly refill ledger rows only for non-zero plans and stores Free as active without zero-value ledger pollution.
- Subscription creation reuses `billing_idempotency_keys.response_body` for same user/key/body cached replay, rejects cross-tenant reuse, rejects same-key/different-body, and defers different-plan changes to 5.B.4.
- Refill-due advances due periods by calendar months and catches up multiple overdue periods without duplicate refill rows on replay.
- Post-implementation review fixed CI mypy trigger drift, authenticated the plan catalog endpoint per story scope, serialized first-subscription creation with a user-row lock, removed an unused helper, and strengthened metadata tests.

### File List

- `.github/workflows/ci.yml`
- `.github/workflows/e2e.yml`
- `_bmad-output/stories/5-b-1-five-plans-subscription.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/billing-service/src/billing_service/models.py`
- `apps/billing-service/src/billing_service/plans.py`
- `apps/billing-service/src/billing_service/routes.py`
- `apps/billing-service/src/billing_service/schemas.py`
- `apps/billing-service/tests/test_subscription_routes.py`
- `infra/local-init/11-billing-subscriptions.sql`

## Change Log

- 2026-05-30 — Story created and revised through three pre-implementation adversarial review rounds; status set to ready-for-dev.
- 2026-05-30 — Implemented five-plan subscription catalog, active subscription persistence, idempotent activation, monthly refill ledger writes, internal refill-due path, migration/CI wiring, and focused tests; status set to code-review.
- 2026-05-30 — Completed post-implementation code review; fixed CI mypy trigger drift, plan-catalog auth boundary, first-subscription concurrency guard, Free zero-refill outbox pollution, and multi-period refill catch-up; status set to done.

## Senior Developer Review (AI)

Outcome: Approved after patch.

Review layers:

- Blind Hunter: diff-level correctness, migration/CI wiring, route contracts, and transaction ordering.
- Edge Case Hunter: month-boundary refill behavior, Free zero-credit handling, replay/idempotency, cross-tenant key reuse, and concurrent first subscription attempts.
- Acceptance Auditor: checked implementation against AC1-AC15 and story out-of-scope boundaries.

Findings and resolution:

- [x] [Medium] Billing-only PRs could skip the CI mypy job because `billing_service` was missing from the mypy job path-filter condition. Fixed `.github/workflows/ci.yml`.
- [x] [Medium] `GET /v1/billing/plans` was public even though the story scoped subscription APIs as authenticated. Added `require_user` dependency and updated tests.
- [x] [Medium] Two concurrent first-subscription POSTs for the same user could race to the partial unique index and surface as a 500. Added a per-user row lock before active-subscription lookup.
- [x] [Low] Free activation marked the period refilled but emitted a refill outbox event with `amount=0.00`. Fixed so Free writes no zero ledger row and no refill outbox.
- [x] [Low] Refill-due initially jumped overdue subscriptions to the current period with one refill. Fixed to catch up period-by-period and added regression coverage.
- [x] [Low] Unused subscription response persistence helper left from an earlier refactor. Removed.

Residual risk:

- Plan monthly Credits are internal runtime defaults because planning artifacts do not contain final approved commercial pricing for all tiers. The code intentionally avoids buyer-facing price claims or payment capture.

## Verification

- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_subscription_routes.py -q` — 15 passed.
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_subscription_routes.py apps/billing-service/tests/test_charge_idempotency_routes.py apps/billing-service/tests/test_charge_routes.py apps/billing-service/tests/test_topup_routes.py apps/billing-service/tests/test_buckets.py -q` — 57 passed, 4 warnings.
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/ -q` — 230 passed, 4 warnings.
- `uv run ruff check apps/billing-service` — passed.
- `uv run ruff format --check apps/billing-service` — passed.
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run mypy apps/billing-service` — passed.
- `git diff --check` — passed.
