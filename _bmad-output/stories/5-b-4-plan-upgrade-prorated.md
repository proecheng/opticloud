---
story_key: 5-b-4-plan-upgrade-prorated
epic_num: 5
story_num: B.4
epic_name: Billing - Subscriptions + Education
status: done
priority: Critical
type: billing plan upgrade + prorated credit adjustment
created_by: bmad-create-story
created_at: 2026-05-30
sources:
  - _bmad-output/planning/epics.md (FR B3 / Epic 5.B / Story 5.B.4)
  - _bmad-output/planning/prd.md (FR B3 / five plan subscriptions)
  - _bmad-output/planning/architecture.md (billing-service ownership / ledger / outbox / idempotency)
  - _bmad-output/stories/5-b-1-five-plans-subscription.md
  - _bmad-output/stories/5-b-2-edu-tier-starter-free.md
  - _bmad-output/stories/5-b-3-edu-pro-30d-trial.md
  - apps/billing-service/src/billing_service/routes.py
  - apps/billing-service/src/billing_service/plans.py
  - apps/billing-service/src/billing_service/schemas.py
  - apps/billing-service/src/billing_service/models.py
  - apps/billing-service/tests/test_subscription_routes.py
baseline_commit: ff17b0907c9cf52b1ff4c1003161f78968efe0ff
---

# Story 5.B.4 - 计划升降级 + prorated 计费

Status: done

## Story

**As** an authenticated non-education Starter subscriber,
**I want** to upgrade to Pro during the current billing period with a prorated remaining-period adjustment,
**so that** I receive only the incremental Pro allowance for the unused part of the current period and then renew as Pro in later periods.

## Context

Story 5.B.1 created the five-plan catalog, one-active-subscription model, subscription idempotency cache, monthly refill ledger rows, and internal `refill-due` scheduler. It deliberately returned `409 Plan change deferred` for different-plan active subscriptions so 5.B.4 could define the proration rules.

Story 5.B.2 and 5.B.3 added education-specific Starter and Pro trial semantics using `BillingSubscription.metadata_json`, `bucket="edu"`, and metadata-based trial detection. This story must not reinterpret those education subscriptions as paid plan changes.

The planning AC only names `Starter -> Pro` mid-period proration. Public prices, gateway capture, invoices, tax, cancellation, downgrades, Team/Enterprise upgrades, and refund flows are not yet defined. Therefore this story implements the backend credit-accounting adjustment for the supported upgrade path, not a real payment provider integration.

## Scope

1. Enable `POST /v1/billing/subscriptions {"plan_code":"pro"}` to upgrade one active non-education `starter` subscription to `pro`.
2. Keep the same active subscription row; do not insert a second active subscription.
3. Keep the current billing period boundaries during the upgrade.
4. Compute a prorated adjustment from the remaining days in the current period:
   - `credit_delta = pro.monthly_credits - starter.monthly_credits`;
   - `remaining_days = ceil((current_period_end - now) / 1 day)`;
   - `total_days = ceil((current_period_end - current_period_start) / 1 day)`;
   - `proration_amount = credit_delta * remaining_days / total_days`, rounded to 2 decimal places.
5. Write exactly one positive `credit_transactions` row for the prorated adjustment with `kind="subscription_proration"` and `bucket="monthly"`.
6. Return the upgraded subscription response with optional proration details for the successful upgrade response and cached idempotency replay.
7. Preserve normal monthly refill behavior: the current period receives only the prorated delta; the next scheduled refill grants full Pro monthly Credits.
8. Keep unsupported plan changes deferred with no ledger, outbox, idempotency response-body, or subscription mutation.

## Out of Scope

- Downgrades, Pro -> Starter, Pro -> Team, Team -> Enterprise, Free -> paid upgrade, or Enterprise custom-contract changes.
- Education Starter -> paid Pro and education Pro trial plan changes; those remain governed by education-specific endpoints/metadata.
- Payment gateway capture, invoices, taxes, receipt PDFs, charge authorization, or buyer-facing price copy.
- Refunds or negative proration credits; refund stories are under Epic 5.C.
- Frontend pricing or Console subscription UI.
- New plan codes, new balance tables, or schema migrations unless implementation discovers a hard persistence need.

## Acceptance Criteria

1. `POST /v1/billing/subscriptions` remains authenticated and requires a valid `Idempotency-Key`.
2. A user with no active subscription keeps existing Story 5.B.1 first-subscription behavior for all five plan codes.
3. A user with an active non-education `starter` subscription can post `{"plan_code":"pro"}` mid-period. Billing mutates the same row to `plan_code="pro"` and preserves `current_period_start`, `current_period_end`, and `last_refilled_period_start`.
4. The upgrade computes `proration_amount` from remaining days over total days in the current period using the current plan catalog values. With Starter `2000.00`, Pro `10000.00`, and exactly 15 remaining days in a 30-day period, the adjustment is `4000.00`.
5. The upgrade writes exactly one positive `credit_transactions` row:
   - `kind="subscription_proration"`;
   - `bucket="monthly"`;
   - `amount == proration_amount`;
   - metadata includes subscription id, from/to plan codes, period start/end, proration timestamp, remaining days, total days, monthly credit delta, trigger, and bucket.
6. The upgrade emits a pointer-safe billing subscription outbox event, such as `billing.subscription.plan_changed`, with subscription id, from/to plan codes, period boundaries, proration amount, and day counts. Payloads must not contain email, phone, JWT, raw request body, payment provider, or payment reference data.
7. The successful upgrade response includes `plan_code="pro"`, unchanged period boundaries, `monthly_credits="10000.00"`, `refill_bucket="monthly"`, `external_payment_required=true`, and optional `proration` details containing from plan, to plan, amount, currency, remaining days, and total days.
8. Same user + same `Idempotency-Key` + same `{"plan_code":"pro"}` body after a successful upgrade returns the cached response and does not create another proration row or outbox event.
9. Same user + same `Idempotency-Key` + different subscription body still returns 409 idempotency conflict and leaves subscription, ledger, and outbox unchanged.
10. Repeating `POST /subscriptions {"plan_code":"pro"}` after the user is already on Pro returns the existing Pro subscription without another proration adjustment.
11. If the active Starter period is already due (`current_period_end <= now`), the upgrade returns 409 RFC 7807 and does not mutate state. Operators must run `refill-due` first so proration is based on a current period.
12. Unsupported active-plan changes still return `409 Plan change deferred` with no state mutation and no idempotency response-body caching. This includes Free -> Pro, Starter -> Team/Enterprise, Pro -> Starter, Pro -> Team, Team/Enterprise changes, and any downgrade.
13. Education subscriptions are not upgraded by this story. If the active subscription has `source="edu_tier"` or `education_entitlement` metadata, or the user currently has `users.edu_tier=true`, Starter -> Pro via the generic subscription endpoint returns 409 without losing education metadata, trial-used history, edu refill bucket behavior, or Pro trial fallback semantics.
14. After a successful Starter -> Pro upgrade, the next `POST /v1/billing/subscriptions/refill-due` at period end advances the same subscription into a new Pro period and grants exactly one full Pro monthly refill (`10000.00`) into `bucket="monthly"`.
15. Existing education Starter, education Pro trial activation/fallback, ordinary non-education first subscriptions, same-plan no-op, balance buckets, charge, topup, and refill-due replay behavior remain unchanged.
16. Quality gates pass:
    - focused subscription tests including proration scenarios;
    - existing billing subscription regression tests;
    - existing auth education signup tests;
    - `uv run ruff check apps/billing-service apps/auth-service`;
    - `uv run ruff format --check apps/billing-service apps/auth-service`;
    - `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run mypy apps/billing-service apps/auth-service`;
    - `git diff --check`.

## Tasks / Subtasks

- [x] T1: Add backward-compatible proration response schema (AC: 7-9)
  - [x] Add optional nested `proration` details to `SubscriptionResponse`.
  - [x] Keep all new fields optional/defaulted so old cached subscription responses still validate.

- [x] T2: Add proration calculation and metadata helpers (AC: 3-6, 11-13)
  - [x] Calculate remaining/total days with deterministic ceiling-day rules.
  - [x] Round prorated credit adjustment to 2 decimal places.
  - [x] Build pointer-safe ledger metadata and outbox payloads.
  - [x] Preserve existing subscription metadata and education trial-used history by rejecting education paths, not rewriting them.

- [x] T3: Implement supported plan-change path in `POST /subscriptions` (AC: 1-3, 7-13)
  - [x] Reuse existing idempotency hash and response cache for `SubscriptionCreateRequest(plan_code="pro")`.
  - [x] Under the existing per-user lock, route only active non-education Starter -> Pro through proration.
  - [x] Leave unsupported plan changes as `409 Plan change deferred` without idempotency response caching.
  - [x] Keep current-period boundaries and `last_refilled_period_start` unchanged.

- [x] T4: Add proration ledger and outbox writes (AC: 4-6, 14)
  - [x] Insert one `credit_transactions` row with `kind="subscription_proration"` and `bucket="monthly"`.
  - [x] Emit a subscription plan-change outbox event in the same transaction.
  - [x] Ensure idempotent replay does not duplicate ledger/outbox rows.

- [x] T5: Tests and gates (AC: 1-16)
  - [x] Extend `apps/billing-service/tests/test_subscription_routes.py`.
  - [x] Cover successful 15/30-day Starter -> Pro proration, idempotent replay, repeated Pro no-op, unsupported changes, due-period rejection, education rejection, next Pro refill, and pointer-safe payloads.
  - [x] Run focused and full verification gates.
  - [x] Update Dev Agent Record, File List, Change Log, and sprint status.

## Pre-Implementation Adversarial Review

### Round 1 - Boundary And Story-Scope Review

Findings:

1. The epic title says "升降级", but the only concrete AC names Starter -> Pro. Implementing downgrades or Team/Enterprise changes here would invent unreviewed refund and commercial-contract behavior.
2. "Prorated billing" can be misread as real payment capture. There is no gateway, invoice, tax, or approved public price model in the shipped billing code.
3. Free -> Pro is not the named path. Treating it as an upgrade would require deciding whether the user receives full Pro, prorated Pro, or a first-subscription path.
4. Education Starter is also `plan_code="starter"`. A plan-code-only implementation could silently convert free education entitlements into paid Pro and erase trial/fallback metadata.
5. Mid-period upgrade must not reset the billing period or it can create an extra full monthly refill on the next scheduler run.

Revision after Round 1:

- Scope narrowed to non-education Starter -> Pro only.
- The story implements a credit-accounting proration row and response details, not real gateway payment capture.
- Unsupported changes remain `409 Plan change deferred`.
- Education paths are explicitly rejected by metadata/eligibility checks.
- Current period boundaries and `last_refilled_period_start` must remain unchanged during upgrade.

### Round 2 - Data Consistency, Idempotency, And Drift Review

Findings:

1. If the prorated adjustment is applied through the existing monthly refill helper, it could be suppressed by `last_refilled_period_start` or confused with scheduled refills.
2. Reusing `kind="monthly_refill"` for proration would make refill counts, scheduler replay assertions, and operational reports ambiguous.
3. The upgrade response must be cached under the existing subscription idempotency row; otherwise retries can mint duplicate prorated credits.
4. Rounding and day-count rules need to be deterministic. Time-of-call drift can turn an expected 15/30 adjustment into a flaky near-15-day amount if seconds are used directly.
5. If a period is already due, proration over a stale period can create a zero or negative adjustment and leave the scheduler in an inconsistent state.

Revision after Round 2:

- Add a dedicated `subscription_proration` ledger kind.
- Proration writes directly to the ledger with pointer-safe metadata and does not use `_apply_monthly_refill_once`.
- Use the existing `SubscriptionCreateRequest(plan_code="pro")` idempotency hash and cache the successful upgrade response.
- Day counts use ceiling days and 2-decimal `ROUND_HALF_UP` rounding.
- Already-due periods return 409 and require `refill-due` before upgrade.

### Round 3 - Dependency, Education, And Closure Review

Findings:

1. Story 5.B.3 depends on metadata-based education Pro trial detection; `plan_code="pro"` alone must never imply paid or trial state.
2. Optional response fields are mandatory. Required proration fields would break cached 5.B.1/5.B.2/5.B.3 response bodies.
3. Changing subscription metadata after upgrade must not introduce sensitive payment or contact data into outbox payloads.
4. The story must prove closure past the upgrade moment: the next scheduler refill should grant full Pro and not replay the Starter amount.
5. Existing tests currently assert Starter -> Pro is deferred. That regression test must be split so unsupported changes remain deferred while the newly supported path is tested.

Revision after Round 3:

- Trial/education detection remains metadata-based; generic upgrade rejects education entitlements and education users.
- `SubscriptionResponse.proration` is optional and only populated for the upgrade response / cached replay.
- Outbox and ledger metadata are pointer-safe only.
- Tests must cover the subsequent Pro refill at period end.
- Existing "different plan deferred" tests will be updated to use unsupported paths such as Starter -> Team.

## Dev Notes

### Existing Patterns To Reuse

- `require_user()` and `validate_idempotency_key()` on `POST /v1/billing/subscriptions`.
- `_subscription_replay_response_if_cached()` and `_upsert_subscription_idempotency_row()` for response-cache idempotency.
- `_lock_user_for_subscription()` plus `_active_subscription_for(..., for_update=True)` for one-active-subscription mutation.
- `get_plan("starter")` and `get_plan("pro")`; Starter monthly Credits are `2000.00`, Pro monthly Credits are `10000.00`.
- `CreditTransaction` as the ledger source of truth. Positive rows add Credits; charges/debits remain separate Saga flows.
- `_write_subscription_outbox()` and `_subscription_payload()` for pointer-safe subscription events.
- `_subscription_has_edu_entitlement()`, `_subscription_is_edu_pro_trial()`, and `_user_is_edu_tier()` to keep education semantics out of this story.

### Architecture Compliance

- billing-service owns subscription state and Credits ledger mutations.
- No mutable balance table; balance remains derived from `credit_transactions`.
- No raw email/phone/JWT/payment data in subscription metadata, ledger metadata, idempotency response, or outbox payload.
- Cross-service state changes use pointer-safe outbox events.
- No schema migration is expected because `credit_transactions.kind` is open string and response changes are Pydantic-only.

### Implementation Guardrails

- Do not insert a second active subscription.
- Do not reset the current period during Starter -> Pro upgrade.
- Do not call `_apply_monthly_refill_once()` for proration.
- Do not write proration to `bucket="edu"`.
- Do not upgrade or rewrite education Starter / education Pro trial rows.
- Do not cache response bodies for rejected unsupported plan changes.
- Do not add public prices, payment providers, invoices, or taxes.
- Do not make `GET /subscriptions/current` create or mutate anything.
- Do not add `edu_pro`, `paid_pro`, or any sixth plan code.

### Suggested Test Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/test_subscription_routes.py -q
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/ -q
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src'; uv run pytest apps/auth-service/tests/test_edu_signup.py -q
uv run ruff check apps/billing-service apps/auth-service
uv run ruff format --check apps/billing-service apps/auth-service
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run mypy apps/billing-service apps/auth-service
git diff --check
```

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline commit: `ff17b0907c9cf52b1ff4c1003161f78968efe0ff`.
- Red phase: `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/test_subscription_routes.py -q -k "starter_to_pro_mid_period"` failed with existing `409 Plan change deferred`.
- Green phase: focused proration scenarios passed with 9 tests.
- Post-review patch: added conservative education metadata drift guard and regression coverage so generic proration rejects rows with `source="edu_tier"` or trial-used history even if `education_entitlement` is absent.
- Subscription regression: full `test_subscription_routes.py` passed with 45 tests and 1 existing FastAPI deprecation warning.
- Full billing regression: `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/ -q` passed with 260 tests and 5 existing FastAPI deprecation warnings.
- Auth education regression: `$env:PYTHONPATH='packages/shared-py;apps/auth-service/src'; uv run pytest apps/auth-service/tests/test_edu_signup.py -q` passed with 6 tests.
- Static gates passed: ruff check, ruff format --check, mypy, and `git diff --check`.

### Completion Notes List

- Added optional `SubscriptionResponse.proration` details for successful Starter -> Pro upgrade responses and idempotency replay.
- Implemented non-education Starter -> Pro in-place upgrade with deterministic ceiling-day proration and a dedicated `subscription_proration` ledger row in `bucket="monthly"`.
- Unsupported plan changes and education paths still return `409 Plan change deferred` without response-body caching.
- Education drift guard rejects generic proration when subscription metadata contains education source or Pro trial-used history, preserving 5.B.2/5.B.3 semantics.
- Next scheduled refill after upgrade grants full Pro monthly Credits.

### File List

- `_bmad-output/stories/5-b-4-plan-upgrade-prorated.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/billing-service/src/billing_service/routes.py`
- `apps/billing-service/src/billing_service/schemas.py`
- `apps/billing-service/tests/test_subscription_routes.py`

## Change Log

- 2026-05-30 - Story created and revised through three pre-implementation adversarial review rounds; status set to ready-for-dev.
- 2026-05-30 - Implemented Starter -> Pro prorated upgrade, response details, ledger/outbox writes, and focused regression tests; status set to code-review.
- 2026-05-30 - Completed post-implementation code review; fixed education metadata drift guard, reran full verification, and marked story done.

## Senior Developer Review (AI)

Findings:

1. Generic proration originally checked only normalized education entitlement. That missed metadata drift cases where `source="edu_tier"` or `education_pro_trial_used=true` remained but `education_entitlement` was absent. Fixed with `_subscription_has_education_metadata()` and a regression test.
2. The first post-review scheduler test assumed `refill-due` would process only one due subscription, but the billing test DB is intentionally session-scoped and not cleaned per test. Fixed by asserting target-user ledger effects and replay behavior instead of global processed count equality.
3. The initial proration test claimed new-key same-plan no-op coverage but only verified same-key replay. Fixed by adding a repeat `POST /subscriptions {"plan_code":"pro"}` with a new idempotency key and asserting no proration response/row duplication.

Decision: Approved after fixes and full verification.
