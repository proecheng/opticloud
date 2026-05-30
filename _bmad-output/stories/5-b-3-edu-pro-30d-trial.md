---
story_key: 5-b-3-edu-pro-30d-trial
epic_num: 5
story_num: B.3
epic_name: Billing - Subscriptions + Education
status: done
priority: Critical
type: billing education Pro trial + automatic fallback
created_by: bmad-create-story
created_at: 2026-05-30
sources:
  - _bmad-output/planning/epics.md (FR B8 / Epic 5.B / Story 5.B.3)
  - _bmad-output/planning/prd.md (FR B8 / education Starter 2K/month + Pro 30d trial)
  - _bmad-output/planning/architecture.md (billing-service ownership / outbox / idempotency / service boundaries)
  - _bmad-output/stories/1-4-edu-tier-auto-activation.md
  - _bmad-output/stories/5-b-1-five-plans-subscription.md
  - _bmad-output/stories/5-b-2-edu-tier-starter-free.md
  - apps/billing-service/src/billing_service/routes.py
  - apps/billing-service/src/billing_service/plans.py
  - apps/billing-service/src/billing_service/schemas.py
  - apps/billing-service/src/billing_service/models.py
  - apps/billing-service/tests/test_subscription_routes.py
---

# Story 5.B.3 - 教育版 Pro 30d trial

Status: done

## Story

**As** a verified education user with `users.edu_tier=true`,
**I want** to activate one free Pro trial that lasts exactly 30 days,
**so that** I can evaluate Pro limits and Credits without payment, and then automatically return to my permanent free Starter entitlement.

## Context

Story 1.4 detects `.edu` / `.ac.cn` users and writes the first education credit seed into `bucket="edu"`. Story 5.B.1 added the five-plan subscription table, first subscription activation, idempotent POST behavior, and the internal refill-due scheduler. Story 5.B.2 materialized permanent education Starter by marking the existing `starter` plan through `BillingSubscription.metadata_json` with `source="edu_tier"` and `education_entitlement="starter_free"`, and made education refills use `bucket="edu"`.

This story adds only the Pro trial part of FR B8. It must not implement general plan upgrade/downgrade, proration, payment capture, pricing UI, or revocation of education status. Trial activation and fallback should reuse the existing one-active-subscription row model and ledger/outbox patterns.

## Scope

1. Add an authenticated billing-service endpoint for the current eligible education user to activate a one-time Pro 30-day trial.
2. Store the trial state on the active `billing_subscriptions` row using `metadata_json`; do not add a new plan code.
3. Grant the Pro trial Credits exactly once into `bucket="edu"` with pointer-safe metadata and outbox payloads.
4. Make `GET /v1/billing/subscriptions/current` identify the active education Pro trial and its trial end/fallback data.
5. Extend the internal refill-due scheduler so an expired education Pro trial automatically falls back to education Starter.
6. On fallback, start a fresh Starter period, grant one Starter refill into `bucket="edu"`, and preserve one-time trial history so the user cannot activate another Pro trial.
7. Preserve existing 5.B.1 and 5.B.2 behavior for non-education users, normal paid subscriptions, education Starter, idempotency, and refill replay.

## Out of Scope

- General plan upgrade/downgrade and prorated paid billing; Story 5.B.4.
- Payment gateway capture, invoices, refunds, cancellation, taxes, or buyer-facing price copy.
- Frontend pricing/console UI.
- Email lifecycle re-verification or revocation when an education email later becomes invalid.
- New `edu_pro`, `trial_pro`, or `education` plan codes.
- Removing or expiring existing ledger balances when trial starts or ends.

## Acceptance Criteria

1. `POST /v1/billing/subscriptions/edu-pro-trial` requires Bearer user auth and a valid `Idempotency-Key`; it has no request body contract and must not accept or trust `user_id`, `edu_tier`, plan code, trial duration, or fallback plan from the client.
2. Billing-service determines eligibility from `users.edu_tier=true`. A non-education user receives 403 RFC 7807 and no subscription, ledger, outbox, or idempotency response mutation.
3. An eligible education user with no active subscription can activate the trial. Billing creates one active `pro` subscription with a 30-day period (`current_period_end = current_period_start + 30 days`) and metadata:
   - `source="edu_tier"`;
   - `education_entitlement="pro_30d_trial"`;
   - `education_pro_trial_used=true`;
   - `trial_started_at`, `trial_ends_at`;
   - `education_pro_trial_started_at`, `education_pro_trial_ends_at`;
   - `fallback_plan_code="starter"`;
   - `fallback_entitlement="starter_free"`;
   - `external_payment_required=false`.
4. An eligible education user with an active education Starter, active Free, or active non-education Starter subscription can activate the trial by mutating the same active row in place. The implementation must not insert a second active subscription.
5. Trial activation writes exactly one positive `credit_transactions` row with `kind="monthly_refill"`, `bucket="edu"`, `amount=10000.00`, and metadata containing subscription id, `plan_code="pro"`, period start/end, `trigger="edu_pro_trial_activation"`, `bucket="edu"`, and `entitlement_source="edu_tier"`. The subscription's `last_refilled_period_start` is set to the trial `current_period_start` in the same transaction.
6. Trial activation emits pointer-safe outbox events for the trial activation and Pro credit refill. Payloads must not contain email, phone, JWT, raw request body, payment provider, or payment reference data.
7. Same user + same idempotency key + same empty-body operation returns the cached trial activation response and does not create a duplicate credit row or outbox event.
8. Same user + same idempotency key + different subscription operation returns the existing subscription idempotency conflict behavior and does not mutate trial state. Trial activation uses a distinct request hash such as `{"operation":"edu_pro_trial_activate"}` so it cannot be confused with `POST /subscriptions`.
9. If the user already has an active education Pro trial, repeating the trial activation with a new idempotency key returns the current trial subscription without issuing another Pro refill. The response may be cached under the new key only after verifying it is the same active trial.
10. If the user has already used and ended the Pro trial, a later activation attempt returns 409 RFC 7807 and does not grant another Pro refill.
11. If the user has an active non-trial Pro, Team, or Enterprise subscription, trial activation returns 409 "Plan change deferred" and does not downgrade, override payment metadata, grant trial Credits, or cache a misleading trial response. General plan changes remain Story 5.B.4.
12. `GET /v1/billing/subscriptions/current` during the trial returns `plan_code="pro"`, `monthly_credits="10000.00"`, `entitlement_source="edu_tier"`, `education_entitlement="pro_30d_trial"`, `refill_bucket="edu"`, `external_payment_required=false`, `trial_ends_at`, and `fallback_plan_code="starter"`. New response fields are optional/defaulted so old 5.B.1/5.B.2 cached `response_body` values still validate.
13. The internal `POST /v1/billing/subscriptions/refill-due` detects expired active education Pro trials (`current_period_end <= as_of`) before normal plan refill processing and automatically falls back to `starter` in the same active row. The fallback uses `education_entitlement="starter_free"`, preserves `education_pro_trial_used=true` plus historical start/end timestamps, clears active `trial_started_at` / `trial_ends_at` response fields, and sets `external_payment_required=false`.
14. Trial fallback writes exactly one Starter `monthly_refill` row into `bucket="edu"` for the new Starter period and emits pointer-safe outbox events for trial end / Starter fallback / refill. The fallback Starter period starts at the old Pro `current_period_end`, and `last_refilled_period_start` is initially `None` so the Starter fallback refill is applied once for that period.
15. Replaying `refill-due` for the same `as_of` after fallback is idempotent: no duplicate Pro or Starter refill rows, no extra trial-ended events, and no period drift. `RefillDueResponse.processed` includes the subscription once when fallback work occurs, and `refilled` includes the Starter fallback refill.
16. If an expired trial is multiple months overdue, refill-due first falls back to Starter at the trial end boundary, applies the first Starter refill, then catches up later Starter monthly periods using the existing calendar-month rules from Story 5.B.1.
17. Existing education Starter behavior from Story 5.B.2 remains unchanged: Starter sync remains idempotent, signup seed is not duplicated, education Starter refills continue to use `bucket="edu"`, and later Starter sync must preserve existing `education_pro_trial_used` / historical Pro trial metadata.
18. Existing non-education subscriptions from Story 5.B.1 remain unchanged: normal Pro/Team/Enterprise subscriptions still refill into `bucket="monthly"` and keep `external_payment_required=true`.
19. Quality gates pass:
    - focused subscription tests including Pro trial scenarios;
    - existing billing subscription regression tests;
    - existing auth education signup tests;
    - `uv run ruff check apps/billing-service apps/auth-service`;
    - `uv run ruff format --check apps/billing-service apps/auth-service`;
    - `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run mypy apps/billing-service apps/auth-service`;
    - `git diff --check`.

## Tasks / Subtasks

- [x] T1: Add education Pro trial metadata helpers (AC: 2-6, 9-14)
  - [x] Add helpers to detect active education Pro trial, trial-used history, active education entitlement, and education refill bucket.
  - [x] Add metadata builder for `pro_30d_trial` and fallback `starter_free` that preserves existing non-sensitive history and never drops `education_pro_trial_used`.
  - [x] Keep plan code `pro`; do not add a new plan catalog item.

- [x] T2: Extend subscription response schema safely (AC: 12)
  - [x] Add backward-compatible optional fields for `education_entitlement`, `trial_ends_at`, and `fallback_plan_code`.
  - [x] Ensure old cached 5.B.1/5.B.2 subscription responses still validate.

- [x] T3: Add authenticated trial activation endpoint (AC: 1-11)
  - [x] Add `POST /v1/billing/subscriptions/edu-pro-trial`.
  - [x] Require `Idempotency-Key` and use the existing `billing_idempotency_keys.response_body` cache pattern with a distinct operation hash.
  - [x] Treat same key reused across charge/subscription/trial operations as an idempotency conflict unless the stored request hash matches the trial operation hash.
  - [x] Keep the authenticated subject as the only user pointer; reject non-empty request bodies.
  - [x] Read education eligibility from `users.edu_tier`; do not trust client input.
  - [x] Mutate no-active, Free, Starter, and education Starter cases into one active Pro trial row under the existing per-user lock.
  - [x] Reject active non-trial Pro/Team/Enterprise cases with 409.
  - [x] Reject trial reuse after fallback with 409.

- [x] T4: Add trial credit grant and outbox behavior (AC: 5-7, 14-15)
  - [x] Reuse the ledger monthly refill helper with `trigger="edu_pro_trial_activation"`.
  - [x] Ensure education Pro trial refill goes to `bucket="edu"`.
  - [x] Ensure `last_refilled_period_start` is trial start after Pro grant and Starter period start after fallback grant.
  - [x] Emit pointer-safe `billing.subscription.edu_pro_trial.activated`, trial-ended, Starter fallback, and refill events.

- [x] T5: Extend refill-due for automatic fallback (AC: 13-16)
  - [x] Detect expired active education Pro trial before the normal monthly-period advancement loop.
  - [x] Switch the same row to education Starter at the trial end boundary.
  - [x] Apply one Starter edu-bucket refill for fallback, then let existing catch-up logic handle later overdue Starter periods.
  - [x] Make replay after fallback no-op for the same `as_of`.
  - [x] Keep response counters meaningful: one processed subscription, fallback refill counted in `refilled`, normal Free zero-credit count unchanged.

- [x] T6: Tests and gates (AC: 1-19)
  - [x] Extend `apps/billing-service/tests/test_subscription_routes.py`.
  - [x] Cover no-active edu activation, education Starter activation, Free activation, active non-education Starter activation, idempotent replay, active trial replay, trial-used rejection, non-edu rejection, paid Pro/Team/Enterprise rejection, current response fields, fallback at 30 days, fallback replay, overdue catch-up, pointer-safe payloads, and non-education regressions.
  - [x] Run focused and full verification gates.
  - [x] Update Dev Agent Record, File List, Change Log, and sprint status.

## Pre-Implementation Adversarial Review

### Round 1 - Boundary And Story-Scope Review

Findings:

1. The initial endpoint wording allowed a request-body interpretation. That would create a forged-user boundary because trial activation should use only the authenticated subject.
2. "Paid/non-education Pro" was too narrow. The implementation can reliably distinguish active education Pro trial by metadata, so every active non-trial Pro/Team/Enterprise row must be treated as out of scope.
3. Repeating activation while a trial is active needs a clear idempotency rule. It can return/cache the same active trial only after proving no new Pro credit is minted.
4. Refill-due must detect expired education Pro trials before the generic monthly refill loop. Otherwise an expired Pro trial could receive another Pro monthly refill instead of falling back.
5. Trial duration and fallback plan must be server constants. Letting the client submit them would turn a billing entitlement into a client-controlled upgrade.

Revision after Round 1:

- Trial activation uses the authenticated user only and has no client-controlled body contract.
- Active non-trial Pro/Team/Enterprise rows return 409 without idempotency response-body caching.
- Active-trial repeat activation can return the same row but cannot issue another refill.
- Refill-due must branch expired education Pro trial handling before normal refill processing.
- The 30-day duration and fallback-to-Starter behavior are fixed server-side constants.

### Round 2 - Drift, Data Consistency, And Idempotency Review

Findings:

1. Trial activation needs its own idempotency request hash. Reusing `SubscriptionCreateRequest(plan_code=...)` or an empty-body hash shared with other endpoints would allow same-key drift across subscription operations.
2. The fallback metadata requirements said "clears active trial fields" but did not name the durable history fields. A naive implementation could remove `education_pro_trial_used` and allow a second trial.
3. The ledger helper gates on `last_refilled_period_start == current_period_start`. Trial activation and fallback must explicitly set this field after successful refill or replay can mint duplicate credits.
4. Fallback period boundaries need to be deterministic. If fallback starts at scheduler `as_of` instead of the trial end, overdue catch-up and user-visible trial duration drift.
5. Pro trial ledger metadata must include the same bucket/source fields as education Starter refills so downstream bucket audits and outbox consumers do not need a special case.

Revision after Round 2:

- Trial activation uses a distinct `edu_pro_trial_activate` idempotency operation hash.
- Cross-operation idempotency key reuse is a conflict unless the stored hash matches trial activation.
- Metadata preserves `education_pro_trial_used=true` and historical start/end fields after fallback.
- Trial activation and fallback both define `last_refilled_period_start` behavior.
- Fallback starts at the old trial end boundary, not at scheduler execution time.

### Round 3 - Dependency, Scheduler, And Closure Review

Findings:

1. Story 5.B.2's `_edu_starter_metadata()` currently merges existing metadata, but this story must explicitly require future Starter sync/fallback paths to preserve trial-used history. Otherwise a repair sync could reopen trial eligibility.
2. Adding required response fields would break cached 5.B.1/5.B.2 idempotency rows because stored JSON lacks the new keys.
3. Refill-due response counters are part of the operational contract. Without specifying fallback counting, an expired trial could mutate state while returning ambiguous `processed` / `refilled` numbers.
4. The story must close the full FR B8 loop without depending on auth-service changes: activation is authenticated billing API; fallback is billing scheduler.
5. Existing non-education Pro must remain a normal monthly subscription. Trial detection must be metadata-based, not plan-code-only.

Revision after Round 3:

- Story status is `ready-for-dev`; implementation can begin.
- Starter sync and fallback paths must preserve `education_pro_trial_used` and historical Pro trial timestamps.
- New `SubscriptionResponse` fields are optional/defaulted.
- Refill-due fallback work increments processed/refilled consistently.
- Trial/fallback detection is metadata-based; `plan_code="pro"` alone is never treated as an education trial.

## Dev Notes

### Existing Patterns To Reuse

- `require_user()` for authenticated user identity; do not take `user_id` in the trial request.
- `validate_idempotency_key()` and `billing_idempotency_keys.response_body` for POST replay behavior.
- `_lock_user_for_subscription()` plus `_active_subscription_for(..., for_update=True)` for one-active-subscription mutation.
- `BillingSubscription.metadata_json` for education entitlement and trial markers.
- `get_plan("pro")` and `get_plan("starter")`; Pro monthly Credits are currently `10000.00`, Starter monthly Credits are `2000.00`.
- `_apply_monthly_refill_once()` for ledger/refill idempotency after extending refill-bucket detection.
- `_write_subscription_outbox()` and `_subscription_payload()` for pointer-safe subscription events.
- `add_one_calendar_month()` only after fallback to Starter; the Pro trial itself is exactly 30 days.

### Architecture Compliance

- billing-service owns subscription state and credit ledger mutations.
- auth-service remains source of truth for `users.edu_tier`; billing-service reads it from DB.
- No raw email/phone/JWT/payment data in subscription metadata, ledger metadata, idempotency response, or outbox payload.
- Cross-service state changes use pointer-safe outbox events.
- No schema migration is expected; `billing_subscriptions.metadata` is sufficient for trial state unless implementation discovers a real query/index need.

### Implementation Guardrails

- Do not add a sixth plan or change the five-plan catalog order.
- Do not mutate `GET /subscriptions/current`; it remains a pure read.
- Do not charge payment, create invoice records, or set `external_payment_required=true` for education trial.
- Do not delete or expire existing ledger credits when trial starts or ends.
- Do not implement generic proration or paid upgrade/downgrade.
- Do not downgrade active paid/non-education Pro/Team/Enterprise users.
- Do not let an expired Pro trial pass through normal Pro monthly refill.
- Do not accept client-provided trial duration, fallback plan, or target user.
- Do not duplicate Story 1.4 signup seed or Story 5.B.2 education Starter initial refill.
- Do not remove `education_pro_trial_used` during fallback or later education Starter sync.
- Do not make `plan_code="pro"` alone imply an education trial.
- Do not add required response fields that break cached subscription responses.

### Suggested Test Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/test_subscription_routes.py -q
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src'; uv run pytest apps/auth-service/tests/test_edu_signup.py -q
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/ -q
uv run ruff check apps/billing-service apps/auth-service
uv run ruff format --check apps/billing-service apps/auth-service
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run mypy apps/billing-service apps/auth-service
git diff --check
```

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Red phase: `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/test_subscription_routes.py -q` failed 7 new Pro trial tests with 404 for missing `/edu-pro-trial`.
- Green phase: focused subscription suite passed after adding Pro trial endpoint, metadata helpers, response fields, and refill-due fallback.
- Formatting phase: `ruff format --check` required formatting of billing routes and subscription tests; reruns passed after `ruff format`.
- Full billing regression passed with 250 tests and 5 existing FastAPI deprecation warnings.

### Completion Notes List

- Added authenticated `POST /v1/billing/subscriptions/edu-pro-trial` with no request body contract; the route uses the current JWT subject and reads `users.edu_tier` from DB.
- Education Pro trial remains `plan_code="pro"` and is distinguished by `BillingSubscription.metadata_json` (`source="edu_tier"`, `education_entitlement="pro_30d_trial"`, `education_pro_trial_used=true`).
- Trial activation grants one Pro monthly refill of `10000.00` into `bucket="edu"` and stores/caches the response through a distinct idempotency operation hash.
- Repeated activation during the active trial returns the same trial without another refill; after fallback, trial reuse returns 409.
- Refill-due detects expired education Pro trials before normal monthly refill, falls back in-place to education Starter at the trial end boundary, grants one Starter `bucket="edu"` refill, then catches up overdue Starter periods.
- Subscription responses now include optional `education_entitlement`, `trial_ends_at`, and `fallback_plan_code` fields while preserving cached response compatibility.
- Post-implementation review added regression coverage for pointer-safe trial/fallback outbox payloads, fallback history preservation through later Starter sync, active Free and active non-education Starter activation, and Team/Enterprise rejection.

### File List

- `_bmad-output/stories/5-b-3-edu-pro-30d-trial.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/billing-service/src/billing_service/routes.py`
- `apps/billing-service/src/billing_service/schemas.py`
- `apps/billing-service/tests/test_subscription_routes.py`

## Senior Developer Review (AI)

Outcome: Approved after patch.

Review layers:

- Blind Hunter: diff-level behavior, idempotency, route body contract, metadata and event semantics.
- Edge Case Hunter: no-active/Free/Starter/non-education Starter/higher-plan states, replay, fallback replay, and overdue scheduler paths.
- Acceptance Auditor: checked implementation against AC1-AC19 and story out-of-scope boundaries.

Findings and resolution:

- [x] [Medium] Trial/fallback outbox safety and event semantics needed stronger assertions. Added pointer-safe payload checks and explicit `ended_plan_code="pro"` / `ended_education_entitlement="pro_30d_trial"` in the trial-ended event.
- [x] [Medium] Fallback followed by education Starter sync could regress if trial history were overwritten. Added regression coverage proving `education_pro_trial_used` and historical timestamps survive later sync.
- [x] [Low] Active Free and active non-education Starter activation paths were accepted by code but not directly covered. Added focused regressions.
- [x] [Low] Team/Enterprise rejection was implied by the Pro test but not covered. Added parameterized higher-plan rejection coverage.

Residual risk:

- Trial activation is a billing-service API only. No frontend control or auth-service event call is added in this story.

## Change Log

- 2026-05-30 - Initial story created.
- 2026-05-30 - Round 1 adversarial review revised endpoint body, active non-trial plan, active-trial replay, and refill-due boundary requirements.
- 2026-05-30 - Round 2 adversarial review revised idempotency hashing, trial history preservation, refill markers, and fallback period boundaries.
- 2026-05-30 - Round 3 adversarial review revised Starter-sync metadata preservation, response compatibility, refill-due counters, and metadata-based trial detection; status set to ready-for-dev.
- 2026-05-30 - Implemented education Pro 30-day trial activation, edu-bucket Pro refill, automatic Starter fallback, and focused regressions; status set to code-review.
- 2026-05-30 - Completed post-implementation code review; patched event semantics and additional edge coverage; status set to done.

## Verification

- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/test_subscription_routes.py -q` - 35 passed, 1 FastAPI deprecation warning.
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/ -q` - 250 passed, 5 FastAPI deprecation warnings.
- `$env:PYTHONPATH='packages/shared-py;apps/auth-service/src'; uv run pytest apps/auth-service/tests/test_edu_signup.py -q` - 6 passed.
- `uv run ruff check apps/billing-service apps/auth-service` - passed.
- `uv run ruff format --check apps/billing-service apps/auth-service` - passed.
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run mypy apps/billing-service apps/auth-service` - passed.
- `git diff --check` - passed.
