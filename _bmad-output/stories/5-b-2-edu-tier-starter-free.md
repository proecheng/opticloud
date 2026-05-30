---
story_key: 5-b-2-edu-tier-starter-free
epic_num: 5
story_num: B.2
epic_name: Billing — Subscriptions + Education
status: done
priority: Critical
type: billing education entitlement + recurring edu refill
created_by: bmad-create-story
created_at: 2026-05-30
sources:
  - _bmad-output/planning/epics.md (FR B8 / Epic 5.B / Story 5.B.2 / SC2)
  - _bmad-output/planning/prd.md (FR B8 / education Starter 2K/month / billing buckets)
  - _bmad-output/planning/architecture.md (billing-service ownership / outbox / idempotency / service boundaries)
  - _bmad-output/stories/1-4-edu-tier-auto-activation.md
  - _bmad-output/stories/5-b-1-five-plans-subscription.md
  - apps/auth-service/src/auth_service/routes.py
  - apps/billing-service/src/billing_service/routes.py
  - apps/billing-service/src/billing_service/plans.py
  - apps/billing-service/src/billing_service/buckets.py
  - infra/local-init/11-billing-subscriptions.sql
---

# Story 5.B.2 — 教育版 Starter 2K/月永久免费

Status: done

## Story

**As** a verified education user with `users.edu_tier=true`,
**I want** my account to receive a permanent free Starter entitlement with 2,000 Credits per month,
**so that** the Story 1.4 education signup promise becomes a durable subscription/refill contract without requiring payment.

## Context

Story 1.4 already detects `.edu` / `.ac.cn` signup, stores `users.edu_tier=true`, and seeds one `credit_transactions` row of `+2000.00` into `bucket="edu"` with metadata `{"source": "edu_tier_signup"}`. Story 5.B.1 added the five-plan catalog, `billing_subscriptions`, idempotent first subscription creation, and the internal refill-due scheduler.

This story must connect those two shipped surfaces. It must not duplicate the signup seed, must not implement the Pro trial that belongs to Story 5.B.3, and must not treat education Starter as a paid Starter subscription.

## Scope

1. Add billing-service logic to recognize `users.edu_tier=true` as eligibility for permanent free Starter.
2. Add an internal event/sync endpoint that materializes the education Starter entitlement from a user-id pointer.
3. Allow eligible education users who explicitly subscribe to `starter` to receive the same education Starter entitlement instead of a paid Starter activation.
4. Refill education Starter periods into `bucket="edu"` with `kind="monthly_refill"` and `amount=2000.00`.
5. Preserve Story 1.4's signup seed as the first-period education credit when it exists; do not mint an extra initial 2,000 Credits for the same education activation.
6. Expose current subscription responses that let callers distinguish education entitlement source and refill bucket.
7. Emit pointer-safe outbox events for education entitlement activation and education monthly refill.
8. Add focused regression tests for eligibility, no duplicate seed, recurring refill, idempotent internal sync, non-edu rejection, and existing 5.B.1 behavior.

## Out of Scope

- Pro 30-day education trial; Story 5.B.3.
- Trial fallback from Pro back to Starter; Story 5.B.3.
- General plan upgrade/downgrade and proration; Story 5.B.4.
- Rewriting Story 1.4 signup to make a synchronous billing-service HTTP call.
- New payment gateway, invoices, refunds, tax, or buyer-facing price copy.
- Frontend pricing/console UI.
- Email lifecycle revocation when an education email later becomes invalid; architecture marks this as v1.5+ ADR.

## Acceptance Criteria

1. Billing-service can determine education eligibility from the existing `users.edu_tier` column. The request body must not be trusted for this flag.
2. `POST /v1/billing/subscriptions/edu-starter/sync` is internal-only (`X-Internal-Service-Auth`) and accepts a `user_id` pointer. For an eligible user with no active subscription, it creates an active `starter` subscription marked as `source="edu_tier"` / `education_entitlement="starter_free"`.
3. For an eligible user with an active `free` subscription, the internal sync endpoint upgrades the existing active row in place to education Starter. It must not insert a second active subscription row, and it must reset the row to a fresh education Starter period so Free's zero-credit `last_refilled_period_start` cannot suppress Starter credits.
4. The internal sync endpoint is idempotent. Repeating it for the same eligible user returns the same active education Starter subscription and does not create another subscription, refill ledger row, or activation outbox event.
5. If the eligible user has the Story 1.4 signup seed (`bucket="edu"`, metadata source `edu_tier_signup`), education Starter activation treats that seed as the first-period allowance: it sets the subscription period and `last_refilled_period_start`, but does not write another initial `+2000.00` ledger row.
6. If an eligible imported/manual education user lacks a signup seed, education Starter activation writes exactly one initial `credit_transactions` row with `kind="monthly_refill"`, `bucket="edu"`, `amount=2000.00`, and metadata containing `subscription_id`, `plan_code`, `period_start`, `period_end`, `trigger`, and `entitlement_source`.
7. If an eligible user already has an active non-education `starter` subscription, education sync marks the existing row as education Starter without duplicating the current period's already-granted monthly Credits. Future refill-due runs must refill into `bucket="edu"`.
8. `POST /v1/billing/subscriptions` with `plan_code="starter"` for an eligible education user creates or returns the same education Starter entitlement. Its response has `plan_code="starter"`, `monthly_credits="2000.00"`, `entitlement_source="edu_tier"`, `refill_bucket="edu"`, and `external_payment_required=false`.
9. Non-education users calling the internal education sync endpoint receive 403 RFC 7807 and no subscription, ledger, or outbox mutation.
10. Non-education users subscribing to `starter` keep existing Story 5.B.1 behavior: paid/external-payment Starter semantics, initial refill in `bucket="monthly"`, and `external_payment_required=true`.
11. The internal refill-due path refills due education Starter subscriptions into `bucket="edu"`, not `bucket="monthly"`, and advances periods with the same calendar-month rules from Story 5.B.1.
12. Replaying refill-due for the same `as_of` remains idempotent: no duplicate education refill rows and no extra outbox events.
13. `GET /v1/billing/subscriptions/current` for a persisted education Starter subscription returns the education metadata fields. A user with no persisted subscription and no sync still follows Story 5.B.1 implicit Free read behavior.
14. Outbox payloads for education activation/refill contain only pointer-safe fields: subscription id, plan code, period boundaries, trigger, bucket, amount, and entitlement source. They must not contain email, phone, JWT, raw request body, payment ref, or provider data.
15. Existing charge/topup/balance behavior remains unchanged. The balance API still reports four canonical buckets, and education monthly credits appear under `bucket="edu"`.
16. Quality gates pass:
    - focused subscription tests including new education scenarios;
    - existing billing regression tests;
    - existing auth education signup tests;
    - `uv run ruff check apps/billing-service apps/auth-service`;
    - `uv run ruff format --check apps/billing-service apps/auth-service`;
    - `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run mypy apps/billing-service apps/auth-service`;
    - `git diff --check`.

## Tasks / Subtasks

- [x] T1: Add education entitlement helpers in billing-service (AC: 1-7, 10-13)
  - [x] Query `users.edu_tier` from billing-service using raw SQL, not request body input.
  - [x] Detect Story 1.4 signup seed by `bucket="edu"` and metadata source `edu_tier_signup`.
  - [x] Add a helper that creates or returns the active education Starter subscription under a per-user row lock.
  - [x] When upgrading active Free, reset `current_period_start`, `current_period_end`, and `last_refilled_period_start` before applying seed/no-seed logic.
  - [x] Mark education subscriptions via `BillingSubscription.metadata_json`.

- [x] T2: Add/extend response and request schemas (AC: 2, 8, 13)
  - [x] Add an internal education sync request/response schema or reuse `SubscriptionResponse` with a user-id request wrapper.
  - [x] Extend `SubscriptionResponse` with `entitlement_source`, `refill_bucket`, and `external_payment_required` while keeping existing plan fields stable.
  - [x] New response fields must have backward-compatible defaults so cached 5.B.1 `billing_idempotency_keys.response_body` rows still validate.

- [x] T3: Add routes and preserve existing subscription behavior (AC: 2-10, 13)
  - [x] Add `POST /v1/billing/subscriptions/edu-starter/sync` behind `require_internal_service`.
  - [x] Route education users' `POST /subscriptions {"plan_code":"starter"}` through the entitlement helper.
  - [x] Upgrade an active `free` subscription row in place for eligible education users.
  - [x] Mark an active non-education `starter` row as education-entitled without backfilling a duplicate first-period credit.
  - [x] Keep non-edu Starter behavior unchanged.
  - [x] Keep active Pro/Team/Enterprise users out of this story's mutation path; do not downgrade paid or future trial plans.

- [x] T4: Adjust refill behavior for education Starter (AC: 4-6, 11-12, 15)
  - [x] Make `_apply_monthly_refill_once` choose `BUCKET_EDU` for education Starter subscriptions and `BUCKET_MONTHLY` otherwise.
  - [x] Ensure first activation with existing signup seed does not write a duplicate refill row.
  - [x] Preserve existing Free zero-credit behavior.

- [x] T5: Outbox and metadata safety (AC: 5-6, 12, 14)
  - [x] Emit `billing.subscription.edu_starter.activated` or a clearly distinguished education activation event.
  - [x] Education refill outbox payloads include `bucket="edu"` and `entitlement_source="edu_tier"`.
  - [x] Tests assert no contact/payment/raw-body fields appear in metadata/outbox payloads.

- [x] T6: Tests and gates (AC: 1-16)
  - [x] Extend `apps/billing-service/tests/test_subscription_routes.py` or add a focused education subscription test file.
  - [x] Cover eligible sync, idempotent sync, seed no-dup, imported edu no-seed initial refill, non-edu rejection, explicit Starter subscribe for edu, normal Starter subscribe for non-edu, due refill to edu bucket, replay idempotency, and response metadata.
  - [x] Run focused and full regression gates.
  - [x] Update Dev Agent Record, File List, Change Log, and sprint status.

## Pre-Implementation Adversarial Review

### Round 1 — Boundary And Story-Scope Review

Findings:

1. The planning line for 5.B.2 mentions both permanent Starter and Pro 30-day trial, but sprint status splits Pro trial into 5.B.3. Combining both here would collapse two stories and make fallback/proration ambiguous.
2. Story 1.4 already grants the first 2,000 education Credits. Re-granting 2,000 on subscription activation would silently double the first month.
3. Education Starter is not a paid Starter plan. Reusing normal Starter metadata with `external_payment_required=true` would contradict "永久免费".
4. Auto-mutating `GET /subscriptions/current` would violate Story 5.B.1's pure-read contract and hide an implicit write behind a read endpoint.

Revision after Round 1:

- This story implements only permanent free Starter, not Pro trial.
- Activation must preserve Story 1.4 signup seed as the first period when present.
- Education Starter uses metadata `source="edu_tier"` and `education_entitlement="starter_free"` and surfaces `external_payment_required=false`.
- Materialization happens through an internal sync endpoint or explicit Starter subscribe, not through GET current.
- Existing active Free rows are upgraded in place to avoid violating the one-active-subscription-per-user index.

### Round 2 — Data Consistency, Credits Bucket, And Replay Review

Findings:

1. Education refill belongs in `bucket="edu"`; putting it into `bucket="monthly"` would make the education bucket a one-time signup artifact and break FR B1's bucket semantics.
2. The existing refill helper only tracks `last_refilled_period_start`; that remains valid only if education activation sets it correctly when the signup seed is reused and resets stale Free zero-refill state during Free-to-Starter upgrade.
3. The internal sync endpoint can be retried after auth event delivery or operator repair. It must be idempotent without requiring a client-provided idempotency key.
4. Eligibility must come from the database, not from an internal request body flag, or any internal caller can mint education entitlements.

Revision after Round 2:

- `_apply_monthly_refill_once` must derive refill bucket from subscription metadata.
- Signup-seed reuse sets `last_refilled_period_start=current_period_start` without ledger write.
- Free-to-education Starter upgrade starts a fresh education Starter period and clears or resets `last_refilled_period_start` according to whether the signup seed is reused.
- Existing paid/non-education Starter rows can be marked as education-entitled for future periods, but must not get a duplicate current-period grant.
- Internal sync is idempotent under a per-user row lock and active-subscription lookup.
- Sync request carries only `user_id`; billing-service reads `users.edu_tier`.

### Round 3 — Dependency, Drift, And Closure Review

Findings:

1. There is no implemented auth-to-billing event receiver from Story 1.4 despite SC2's intent. A billing-side internal sync endpoint is the smallest closed-loop receiver for this story and can later be called by an outbox consumer.
2. `billing_subscriptions` currently has no explicit entitlement columns. Adding columns for one education case would expand migration scope; metadata is enough if response helpers normalize it.
3. Active non-Starter subscriptions should not be downgraded by education sync. Pro trial and plan fallback belong to 5.B.3.
4. Extending `SubscriptionResponse` can break cached idempotency replays if new fields are required and old `response_body` JSON lacks them.
5. Existing CI path filters already include billing-service from 5.B.1; avoid unrelated workflow churn unless tests prove a gap.

Revision after Round 3:

- Add the internal sync route as the event-receiver seam; no auth-service HTTP call in this story.
- Use `metadata_json` for `source`, `education_entitlement`, and `external_payment_required=false`; no migration required unless implementation discovers an index/constraint need.
- If active plan is `starter`, sync can mark/return education Starter. If active plan is `free`, sync upgrades that row in place. If no active plan exists, sync creates education Starter. If active plan is `pro`, `team`, or `enterprise`, sync returns the active plan without downgrading and relies on 5.B.3/5.B.4 for fallback/change.
- New response fields are optional/defaulted and response builders always populate them for current rows.
- Keep workflow changes scoped to files required by implementation/tests.

## Dev Notes

### Existing Patterns To Reuse

- `require_user()` and `require_internal_service()` from `billing_service.auth_dep`.
- `_lock_user_for_subscription()` to serialize subscription creation per user.
- `_active_subscription_for(..., for_update=True)` for active subscription mutation.
- `BillingSubscription.metadata_json` for entitlement/source markers.
- `BUCKET_EDU` and `BUCKET_MONTHLY` from `billing_service.buckets`.
- `get_plan("starter")` from `billing_service.plans`; Starter monthly Credits are already `2000.00`.
- `_problem_response()` for RFC 7807 errors.
- Existing ASGI subscription test fixtures and direct SQL helper style in `test_subscription_routes.py`.

### Architecture Compliance

- billing-service owns subscription state and monthly refill ledger behavior.
- auth-service remains source of truth for `users.edu_tier`; billing-service reads it from DB.
- No raw email/phone/JWT/payment data in billing metadata or outbox payload.
- Cross-service state changes use pointer-safe outbox events.
- POST operations are idempotent by explicit key (`/subscriptions`) or by natural key (`user_id` + active subscription) for internal sync.

### Implementation Guardrails

- Do not add another plan code such as `edu_starter`; plan remains `starter`.
- Do not add a mutable balance table.
- Do not change normal non-edu Starter refill bucket or payment metadata.
- Do not write a second initial 2,000 Credits row when Story 1.4's signup seed exists.
- Do not mutate active Pro/Team/Enterprise subscriptions in this story.
- Do not make `GET /subscriptions/current` create rows or ledger entries.

### Suggested Test Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/test_subscription_routes.py -q
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/auth-service/tests/test_edu_signup.py apps/billing-service/tests/test_subscription_routes.py -q
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

- Red phase: `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/test_subscription_routes.py -q` failed 5 education tests with missing sync endpoint / missing response fields.
- Green phase: focused subscription route suite passed after implementing education sync, response metadata, and edu-bucket refill behavior.
- Auth + billing cross-epic verification had to run as separate pytest invocations because `apps/auth-service/tests` and `apps/billing-service/tests` both expose `tests.conftest`; combined invocation hits Pytest ImportPathMismatch.
- Full billing regression passed with 238 tests and 4 existing FastAPI deprecation warnings after code-review fixes.

### Completion Notes List

- Added internal `POST /v1/billing/subscriptions/edu-starter/sync` that reads `users.edu_tier` from DB and materializes education Starter without trusting request-body eligibility.
- Extended subscription responses with backward-compatible `entitlement_source`, `refill_bucket`, and `external_payment_required` fields.
- Education Starter subscriptions are still `plan_code="starter"` and are marked via `BillingSubscription.metadata_json`.
- Story 1.4 signup seed is reused as the first-period education allowance when present; imported edu users without a seed receive one initial edu monthly refill.
- Refill-due now writes education Starter refills into `bucket="edu"` while preserving normal non-edu Starter monthly-bucket behavior.
- Added focused regression coverage for sync idempotency, no duplicate seed, imported edu refill, active Free upgrade, non-edu rejection, explicit edu Starter subscribe, and scheduled edu refill replay.
- Post-implementation review fixed explicit Starter idempotency cache pollution when an edu user already had a non-Starter active plan, ensured existing Starter-to-edu conversion emits an education activation event, fixed Free-to-edu control flow, and strengthened education outbox safety assertions.

### File List

- `_bmad-output/stories/5-b-2-edu-tier-starter-free.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/billing-service/src/billing_service/routes.py`
- `apps/billing-service/src/billing_service/schemas.py`
- `apps/billing-service/tests/test_subscription_routes.py`

## Change Log

- 2026-05-30 — Story created and revised through three pre-implementation adversarial review rounds; status set to ready-for-dev.
- 2026-05-30 — Implemented education Starter entitlement sync, edu-bucket refill behavior, response metadata, and focused regressions; status set to code-review.
- 2026-05-30 — Completed post-implementation code review; fixed non-Starter active-plan handling, existing Starter activation event emission, Free upgrade control flow, and education outbox safety coverage; status set to done.

## Senior Developer Review (AI)

Outcome: Approved after patch.

Review layers:

- Blind Hunter: route diff, transaction boundaries, idempotency cache behavior, schema compatibility, and import/static hygiene.
- Edge Case Hunter: active Free upgrade, existing paid Starter conversion, active non-Starter users, retry/replay, and refill bucket selection.
- Acceptance Auditor: checked implementation against AC1-AC16 and story out-of-scope boundaries.

Findings and resolution:

- [x] [High] Education users with an active Pro/Team/Enterprise subscription could explicitly POST `plan_code="starter"` and receive the existing non-Starter response cached under a Starter idempotency key. Fixed by returning 409 "Plan change deferred" for explicit Starter requests when a non-Starter active plan exists, and added regression coverage.
- [x] [Medium] Existing non-education Starter rows converted to education entitlement without emitting the required education activation outbox event. Fixed by emitting `billing.subscription.edu_starter.activated` during that state transition and added pointer-safe payload assertions.
- [x] [Medium] Free-to-education Starter upgrade path fell through into the active-plan passthrough branch before applying initial edu refill. Fixed branch control flow and covered with active Free upgrade regression.
- [x] [Low] `BUCKET_EDU` and `BUCKET_MONTHLY` imports became unused after Literal typing changes. Removed unused imports.

Residual risk:

- The internal sync endpoint is the receiver seam for Story 1.4's cross-epic contract. Auth-service does not call it synchronously in this story; a future outbox consumer can invoke the same endpoint.

## Verification

- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/test_subscription_routes.py -q` — 23 passed.
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/test_subscription_routes.py apps/billing-service/tests/test_charge_idempotency_routes.py apps/billing-service/tests/test_charge_routes.py apps/billing-service/tests/test_topup_routes.py apps/billing-service/tests/test_buckets.py -q` — 65 passed, 4 warnings.
- `$env:PYTHONPATH='packages/shared-py;apps/auth-service/src'; uv run pytest apps/auth-service/tests/test_edu_signup.py -q` — 6 passed.
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/ -q` — 238 passed, 4 warnings.
- `uv run ruff check apps/billing-service apps/auth-service` — passed.
- `uv run ruff format --check apps/billing-service apps/auth-service` — passed.
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run mypy apps/billing-service apps/auth-service` — passed.
- `git diff --check` — passed.
