---
story_key: 5-d-5-monthly-budget-alert
baseline_commit: 65af760799d17f01afe4edd1861c55c0be553ce4
epic_num: 5
story_num: D.5
epic_name: Billing - Invoices + Templates + Budget + Notifications
status: done
priority: High
type: billing monthly budget alert and automatic pause
created_by: bmad-create-story
created_at: 2026-06-01
sources:
  - _bmad-output/planning/epics.md (Epic 5.D / Story 5.D.5 / FR B12)
  - _bmad-output/planning/prd.md (FR B12 v1 required, simplified profile can cut to balance warning)
  - _bmad-output/planning/architecture.md (billing-service ownership / outbox / Saga budget-pause gap)
  - _bmad-output/stories/5-d-1-bilingual-invoices.md
  - _bmad-output/stories/5-d-2-7d-30d-sparkline-trends.md
  - _bmad-output/stories/5-a-0a-saga-implementation.md
  - _bmad-output/stories/5-a-0b-saga-contract-fixtures.md
  - infra/local-init/03-billing-schema.sql
  - infra/local-init/11-billing-subscriptions.sql
  - apps/billing-service/src/billing_service/models.py
  - apps/billing-service/src/billing_service/routes.py
  - apps/billing-service/src/billing_service/schemas.py
  - apps/billing-service/tests/test_charge_routes.py
  - apps/billing-service/tests/test_usage_trends_routes.py
  - apps/web/src/lib/api.ts
  - apps/web/src/app/console/billing/invoices/page.tsx
---

# Story 5.D.5 - Monthly budget alert + 自动暂停

Status: done

## Story

**As** an authenticated OptiCloud billing user,
**I want** to set a monthly usage budget that alerts me at 80% and automatically pauses new billable usage at 100%,
**so that** I can control monthly Credits spend without discovering overruns after the fact.

## Context

Stories 5.D.1 and 5.D.2 established the ledger-derived monthly statement and 7d/30d usage-spend formulas. Story 5.D.5 must reuse that source of truth: monthly budget consumption is actual usage spend from charge-related ledger rows, not balance, topups, subscription refills, proration, or grants.

Planning references `paused_by_budget`, but Story 5.A.0a currently ships a 7-state Saga and Story 5.A.0b keeps `paused_by_budget` as a non-executable stub. This story must close the user-facing budget-pause loop without destabilizing the Saga state machine: budget pause is a billing-service user budget state that blocks new charge creation, emits notification/outbox events, and is visible in the Console. It must not add an eighth Saga state unless a separate Saga ADR/update story is created.

## Scope

1. Add billing-service persistence for one current monthly budget control per user plus period-scoped budget events.
2. Add authenticated budget settings/status APIs.
3. Compute current-month actual spend from ledger rows using the same charge/refund formula as invoices and usage trends.
4. Emit one idempotent 80% alert event per user/month and one idempotent 100% pause event per user/month.
5. Block new `POST /v1/billing/charges` while the user's current budget is paused for the current month.
6. Re-evaluate budget after charge confirmation/finalization paths that create charge-related ledger rows.
7. Add typed web API helpers and a compact Console budget panel on the existing billing Console page; do not implement the future Tier 2 BudgetAlertCard component.
8. Run post-implementation code review, fix findings, pass gates, and sync GitHub.

## Out Of Scope

- Notification preferences, per-channel opt-in/out, webhooks, or digest rules (Story 5.D.6).
- A reusable Tier 2 `BudgetAlertCard` package component (Story 5.D.7).
- Actual SMTP/provider delivery. This story emits pointer-safe notification/outbox events with `channel="email"` / `channel="in_app"` contracts for downstream delivery.
- Editing the shared Saga state machine or adding an executable `paused_by_budget` state.
- Pausing already reserved or already running work; automatic pause blocks new charge creation after the threshold is reached.
- Annual, weekly, per-project, per-template, or per-API-key budgets.
- Billing address, tax invoice, payment-method, pricing-catalog, or subscription-plan changes.
- Exposing raw ledger metadata, emails, phones, JWTs, API keys, payment refs, source payload bodies, or solver result payloads.

## Acceptance Criteria

1. Local schema is idempotently upgraded with `billing_budget_controls` and `billing_budget_events`.
2. There is at most one current budget control per user. The control stores `monthly_budget_amount`, `alert_threshold_ratio=0.80`, `status`, `paused_at`, `pause_period_start`, and timestamps.
3. Budget events are unique per `(user_id, period_start, event_type)` so retries/concurrent threshold checks do not duplicate alert/pause events.
4. SQLAlchemy model/index metadata matches the local init schema.
5. `GET /v1/billing/budget` requires auth and returns a pure read of the user's budget control, current UTC calendar-month period, current actual spend, percent used, alert/paused flags, and recent safe event summaries.
6. `PUT /v1/billing/budget` requires auth and accepts only `monthly_budget_amount` and optional `enabled`; it never accepts `user_id`, status, event fields, timestamps, or raw notification payloads.
7. Valid budget amounts are decimal CNY strings between `1.00` and `9999999.99`, quantized to cents. Invalid values return RFC 7807 422 with field-specific errors and no mutation.
8. Disabling budget control sets `enabled=false`, `status="active"`, clears current pause fields, emits a pointer-safe `billing.budget.disabled` outbox event, and allows future charge creation.
9. Increasing or setting the budget above current-month actual spend sets `status="active"`, clears current pause fields, emits a pointer-safe `billing.budget.configured` outbox event, and allows future charge creation.
10. Setting a budget at or below current-month actual spend immediately evaluates thresholds in the same transaction; if spend is already >=80% it emits the alert event, and if spend is >=100% it pauses.
11. Current-month actual spend is computed from `credit_transactions` for the current user and UTC month using only charge-related rows: `charge`, `refund`, `refund_partial`, and `refund_reversal`. Topups, monthly refills, education grants, subscription proration, and unknown adjustments are excluded.
12. Spend math treats debits as positive spend and refunds as spend reduction, never below zero for the month.
13. When actual spend reaches or exceeds 80% and is below 100%, one `billing.budget.alerted` budget event and one outbox event are created for the user/month. Payload is pointer-safe and contains budget id, period, budget amount, actual spend, percent used, threshold ratio, and `channels=["email","in_app"]`.
14. When actual spend reaches or exceeds 100%, the budget control becomes `status="paused"` with `paused_at` and `pause_period_start`; one `billing.budget.paused` budget event and one outbox event are created for the user/month.
15. Replaying threshold evaluation, retrying finalize/confirm, or calling `GET /budget` after thresholds have been crossed does not create duplicate events or outbox rows.
16. `POST /v1/billing/charges` rejects new charges with RFC 7807 409 when the current user is paused by budget for the current month. It must not seed demo credits, create Saga rows, create idempotency rows, or write ledger rows in that rejected path.
17. Charge creation for users without a budget, disabled budget, or active budget below threshold preserves existing 5.A behavior including lazy seed, idempotency, pre-charge guard, and insufficient-balance responses.
18. Budget threshold evaluation is invoked after the legacy confirm path and split finalize success path create charge-related ledger rows. Failure/refund paths must not pause unless net current-month actual spend reaches the threshold.
19. Cross-user access is impossible because `user_id` is taken only from JWT/internal auth dependencies, never from path/query/body.
20. Budget response and event payloads do not expose raw ledger metadata, payment references, JWTs, API keys, emails, phones, source payload bodies, solver outputs, or arbitrary user-provided blobs.
21. Web API helpers in `apps/web/src/lib/api.ts` expose typed `getBillingBudget` and `putBillingBudget` helpers against `BILLING_SERVICE_URL` with bearer auth and existing RFC 7807 error handling.
22. The existing billing Console page displays a compact budget panel with current spend, budget amount, percent used, status, and recent event labels.
23. The Console budget panel lets the user set/update a monthly budget and disable budget control. It keeps invoice/trend content visible when budget API calls fail.
24. The Console does not store budget settings, event payloads, JWT copies beyond the existing login token, invoice data, or trend data in `localStorage`/`sessionStorage`.
25. Tests cover schema/model contract, budget get/put validation, owner scoping by auth, 80% alert, 100% pause, idempotent event/outbox behavior, charge creation block with no side effects, existing charge behavior preserved, finalize/confirm threshold evaluation, web helper URL/auth/error behavior, Console success/error/storage hygiene, and `git diff --check`.

## Tasks / Subtasks

- [x] T1: Add budget persistence and spend helpers (AC: 1-4, 11-15, 20)
  - [x] Add idempotent local init SQL for `billing_budget_controls` and `billing_budget_events`.
  - [x] Update billing CI/e2e schema setup to apply the new local init file.
  - [x] Add ORM models and indexes.
  - [x] Add pure helpers for UTC month boundaries, actual spend math, percent math, idempotent event/outbox writes, and pause transitions.

- [x] T2: Add budget schemas and routes (AC: 5-10, 13-16, 19-20)
  - [x] Add request/response/event summary schemas.
  - [x] Add `GET /v1/billing/budget`.
  - [x] Add `PUT /v1/billing/budget`.
  - [x] Reuse RFC 7807 error patterns and pointer-safe outbox payload style.

- [x] T3: Wire automatic pause into charge lifecycle (AC: 16-18)
  - [x] Check current budget pause before lazy seed/idempotency side effects in `POST /charges`.
  - [x] Evaluate thresholds after legacy `/confirm`.
  - [x] Evaluate thresholds after split `/finalize` success and failure/refund paths.
  - [x] Preserve idempotent terminal replay behavior.

- [x] T4: Add backend tests (AC: 1-20, 25)
  - [x] Cover set/get/disable, validation, and current-month spend formula.
  - [x] Cover 80% alert and 100% pause with one event/outbox each.
  - [x] Cover replay/idempotency and concurrent-like duplicate prevention.
  - [x] Cover paused charge creation side-effect-free rejection.
  - [x] Cover existing charge create/confirm/finalize behavior remains compatible.

- [x] T5: Add web API helpers and tests (AC: 21, 24-25)
  - [x] Add TypeScript types and helper functions.
  - [x] Assert URL, Authorization header, request body shape, and RFC 7807 preservation.

- [x] T6: Add compact Console budget panel (AC: 22-24)
  - [x] Extend `/console/billing/invoices` with budget status loading independent of invoices/trends.
  - [x] Add monthly budget input/update and disable action.
  - [x] Keep budget failures isolated from invoices/trends.
  - [x] Add focused page tests for success, error isolation, pause state, and storage hygiene.

- [ ] T7: Review, gates, and GitHub sync (AC: 25)
  - [x] Run focused backend/web tests and static gates.
  - [x] Run post-implementation code review and fix findings.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.

## Dev Notes

### Backend Patterns To Reuse

- `billing-service` owns budget controls because it owns Credits ledger, invoice/trend spend formulas, charge creation, and billing outbox events.
- Keep the shared Saga state machine unchanged. `paused_by_budget` remains a budget-control status, not a new `SagaInstance.current_state`.
- Reuse `_problem_response(...)` and `ErrorDetail` in `routes.py`.
- Reuse `_balance_for(...)`, `CreditTransaction`, and existing outbox model style.
- Use auth dependencies already in `billing_service.auth_dep`; never accept client-provided `user_id`.
- Outbox payloads should follow existing subscription/refund pointer-safe style: IDs, periods, amounts, ratios, booleans, and event labels only.
- If threshold evaluation is called from a route that may replay terminal state, it must be idempotent through the event table unique constraint before outbox insert.

### Spend Formula

- UTC calendar month: `[YYYY-MM-01T00:00:00Z, next_month_start)`.
- Include `kind IN ('charge', 'refund', 'refund_partial', 'refund_reversal')`.
- Convert signed ledger to spend contribution with `-amount`; clamp the monthly total at `0.00`.
- This yields: charge `-100` -> spend `100`; refund `+20` -> spend reduction `20`; refund reversal `-20` -> spend increase `20`.

### Frontend Patterns To Reuse

- `apps/web/src/lib/api.ts` already owns `BILLING_SERVICE_URL`, `request<T>()`, `OptiCloudClientError`, invoice helpers, and trend helpers.
- The existing `/console/billing/invoices` page already reads `jwt_access` from `sessionStorage` and keeps invoice/trend loading states separate. Add a third independent budget state instead of making one combined loading/error state.
- Keep UI operational and compact. Do not add a marketing page or reusable Tier 2 component.
- Do not write budget response data to storage.

### Suggested Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_budget_routes.py apps/billing-service/tests/test_charge_routes.py -q
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/billing-service/src'; uv run pytest apps/billing-service/tests/ -q
uv run ruff check apps/billing-service/src/billing_service apps/billing-service/tests/test_budget_routes.py
uv run ruff format --check apps/billing-service/src/billing_service apps/billing-service/tests/test_budget_routes.py
uv run mypy apps/billing-service/src/billing_service
pnpm vitest run src/lib/billing-budget.test.ts src/app/console/billing/invoices/page.test.tsx
pnpm typecheck
pnpm test
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Implementation satisfies every Acceptance Criterion without implementing 5.D.6 or 5.D.7 early.
- Existing invoice, trend, subscription, topup, charge, refund, and Saga behaviors remain compatible.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/5-d-5-monthly-budget-alert`.
- Baseline commit: `65af760799d17f01afe4edd1861c55c0be553ce4`.
- 2026-06-01 - Story moved to implementation after three pre-implementation adversarial review rounds.
- Focused backend gate: `uv run pytest apps/billing-service/tests/test_budget_routes.py apps/billing-service/tests/test_charge_routes.py -q` -> 39 passed.
- Billing-service regression gate: `uv run pytest apps/billing-service/tests/ -q` -> 284 passed.
- Python static gates: `ruff check`, `ruff format --check`, and `mypy apps/billing-service/src/billing_service` passed.
- Focused web gate: `pnpm vitest run src/lib/billing-budget.test.ts src/app/console/billing/invoices/page.test.tsx` -> 11 passed.
- Web regression gates: `pnpm typecheck` passed; `pnpm test` -> 155 passed.
- Whitespace gate: `git diff --check` passed.
- GitHub sync: PR #131 passed CI, merged into `main` at `d1b53c34ac11b0c0c19d441d5f9734176200fa36`, remote story branch deleted, and local `main` synced.

### Completion Notes List

- Added billing budget controls/events persistence and idempotent threshold event/outbox emission.
- Added monthly actual spend evaluation using ledger-derived charge/refund spend math.
- Added `GET/PUT /v1/billing/budget` and budget pause rejection before new charge side effects.
- Wired confirm/finalize charge paths to evaluate 80% alert and 100% pause thresholds.
- Added web API helpers and a compact billing Console budget panel with isolated loading/error state.
- Post-implementation review found and fixed two patch items: non-decimal budget input now returns stable RFC 7807 validation, and configured/disabled events can be recorded more than once while alerted/paused remain unique per period.

### File List

- `_bmad-output/stories/5-d-5-monthly-budget-alert.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `.github/workflows/e2e.yml`
- `infra/local-init/12-billing-budget.sql`
- `apps/billing-service/src/billing_service/budget.py`
- `apps/billing-service/src/billing_service/models.py`
- `apps/billing-service/src/billing_service/routes.py`
- `apps/billing-service/src/billing_service/schemas.py`
- `apps/billing-service/tests/test_budget_routes.py`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/billing-budget.test.ts`
- `apps/web/src/app/console/billing/invoices/page.tsx`
- `apps/web/src/app/console/billing/invoices/page.test.tsx`

## Change Log

- 2026-06-01 - Story created for monthly budget alert, idempotent notification events, automatic budget pause, and compact billing Console panel.
- 2026-06-01 - Implemented budget persistence, API routes, charge lifecycle pause/evaluation, Console panel, tests, post-review fixes, and local gates.
- 2026-06-01 - PR #131 passed GitHub CI, merged to `main`, remote branch deleted, local `main` synced, and story marked done.

## Post-Implementation Code Review

### Findings

- [x] [Review][Patch] Non-decimal `monthly_budget_amount` could bypass the intended field-specific RFC 7807 shape through a raw `Decimal` conversion error. Fixed by catching `InvalidOperation`/`ValueError` in the schema validator and adding a regression assertion for `body.monthly_budget_amount`.
- [x] [Review][Patch] The initial budget-event uniqueness constraint made `billing.budget.configured` idempotent per month, which hid repeated user budget changes. Fixed by limiting the unique index and conflict handling to threshold events (`alerted` and `paused`) while allowing repeated configured/disabled audit events.

### Outcome

Changes requested internally; all findings fixed and local gates rerun successfully.

## Pre-Implementation Adversarial Review

### Round 1 - Budget Boundary, Spend Math, And Billing Consistency

Findings:

1. Budget consumption could drift if it uses total balance instead of actual usage spend.
2. Topups, monthly refills, education grants, and proration can dwarf usage and would create false alert/pause if included.
3. Refunds and partial refunds can make simple `SUM(charge)` overstate spend.
4. UTC month boundaries need to be explicit or tests and statements will drift across locales.

Revision after Round 1:

- Required budget spend to reuse the invoice/trend charge-related formula.
- Explicitly excluded non-usage ledger kinds.
- Required signed ledger conversion with clamped non-negative monthly spend.
- Required UTC calendar-month boundaries in API response and tests.

### Round 2 - Drift, Idempotency, And Notification Side Effects

Findings:

1. Threshold checks run from finalize/confirm and may be replayed; naive event creation would send duplicate alerts.
2. Implementing actual email delivery here would overlap Story 5.D.6 notification preferences and create an untestable external dependency.
3. A paused user must be blocked before `POST /charges` lazy-seeds, starts a Saga, or writes idempotency rows.
4. `GET /budget` should not mutate state, or merely viewing the page could send notifications.

Revision after Round 2:

- Added a period-scoped budget event table with a uniqueness constraint.
- Scoped this story to pointer-safe outbox/notification event contracts, not SMTP delivery.
- Required pause rejection before charge side effects.
- Required `GET /budget` to be pure read.

### Round 3 - Data Consistency, Dependency Boundaries, And UI Closure

Findings:

1. Planning mentions `paused_by_budget`, but changing the shared Saga enum would invalidate existing 5.A contracts and fixture assumptions.
2. A broad budget UI could become the future Tier 2 `BudgetAlertCard` or notification-preferences product.
3. Increasing a budget after pause needs a clear resume rule or users can get stuck until next month.
4. Browser storage hygiene must include budget payloads, not only invoices and API keys.

Revision after Round 3:

- Kept Saga unchanged and modeled pause as billing-service budget-control status.
- Limited frontend scope to a compact panel on the existing billing Console page.
- Required setting/increasing budget above current spend or disabling control to clear pause fields.
- Required page tests proving budget data is not written to browser storage and budget errors do not hide invoices/trends.
