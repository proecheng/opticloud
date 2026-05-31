---
story_key: 5-d-2-7d-30d-sparkline-trends
baseline_commit: e11d64dd2c1a94b4ef10ce6387809a4a29142ad5
epic_num: 5
story_num: D.2
epic_name: Billing - Invoices + Templates + Budget + Notifications
status: done
priority: High
type: billing usage trends API and Console SparklineKPI
created_by: bmad-create-story
created_at: 2026-05-31
sources:
  - _bmad-output/planning/epics.md (Epic 5.D / Story 5.D.2 / FR B7)
  - _bmad-output/planning/prd.md (FR B7 v1 required)
  - _bmad-output/planning/architecture.md (billing-service owner; Next.js Console; UX-DR1 SparklineKPI)
  - _bmad-output/stories/5-d-1-bilingual-invoices.md
  - apps/billing-service/src/billing_service/routes.py
  - apps/billing-service/src/billing_service/invoices.py
  - apps/billing-service/src/billing_service/schemas.py
  - apps/web/src/lib/api.ts
  - apps/web/src/app/console/billing/invoices/page.tsx
  - packages/ui/src/components/SparklineKPI/index.tsx
---

# Story 5.D.2 - 7d/30d usage trends SparklineKPI

Status: done

## Story

**As** an authenticated OptiCloud billing user,
**I want** to see 7-day and 30-day usage-spend trends in the Console,
**so that** I can quickly understand recent Credits consumption without reading every invoice line item.

## Context

FR B7 requires bilingual invoices plus 7d/30d usage trends. Story 5.D.1 shipped the bilingual billing statement and intentionally kept only an invoice-scoped summary payload with `trend_contract="invoice_summary"`. This story owns the reusable dashboard trend contract and Console visualization using the existing Tier 1 `SparklineKPI` component.

Billing data remains ledger-derived from `credit_transactions`; no analytics table is required for v1. The trend is usage spend only, not balance, topups, grants, subscriptions, budget alerts, notifications, saved templates, or tax invoice data.

## Scope

1. Add a read-only authenticated billing usage trends API under `billing-service`.
2. Return a reusable dashboard contract for 7d and 30d daily UTC buckets.
3. Zero-fill missing days and order points oldest to newest.
4. Use the same charge-related spend semantics established by 5.D.1.
5. Add typed web API helpers against `BILLING_SERVICE_URL`.
6. Show the trend data on the existing billing Console surface with `SparklineKPI`.
7. Harden `SparklineKPI` only as needed for empty/zero data, stable dimensions, and accessible labels.
8. Add focused backend, web API, Console page, and UI component tests.
9. Run post-implementation code review, fix findings, pass gates, and sync GitHub.

## Out Of Scope

- Budget thresholds, monthly budget alerts, notification preferences, email/push delivery, or alert history.
- Job template save/version flows.
- New invoice PDF behavior, tax/VAT/fapiao claims, or legal invoice semantics.
- Payment provider integration or payment receipt rendering.
- Persisted trend snapshots or a new analytics table unless implementation proves the ledger query cannot satisfy v1.
- Cross-user/admin trend lookup.
- New charting dependency; use `@opticloud/ui` `SparklineKPI`.
- Changing charge, refund, subscription, topup, monthly refill, or education grant ledger semantics.

## Acceptance Criteria

1. `GET /v1/billing/usage-trends` returns an authenticated, owner-scoped response; no route, query, or body accepts `user_id`.
2. The endpoint is read-only: it must not seed demo credits, create subscriptions, create idempotency rows, write outbox events, or mutate ledger rows.
3. The response contains `trend_contract: "billing_usage_trends_v1"` and must not reuse `invoice_summary`.
4. The response contains exactly two windows: 7 days and 30 days.
5. Each window contains `window_days`, `window_start`, `window_end`, `label`, `currency`, `total_actual_spend`, `average_daily_spend`, and `points`.
6. Each point contains `date` as a UTC calendar date, `actual_spend` as a two-decimal string, and `currency: "CNY"`.
7. Window semantics are fixed to UTC days and include the current UTC day plus the previous N-1 days; `window_end` is exclusive at the next UTC midnight.
8. Missing days are zero-filled, and points are ordered ascending by date.
9. Daily actual spend is computed from charge-related ledger rows only: `charge`, `refund`, `refund_partial`, and `refund_reversal`; topups, monthly refills, education grants, subscription proration, and unknown adjustment kinds are excluded from spend.
10. For each day, `actual_spend = max(0, -sum(charge_related_amounts_for_that_day))`, serialized with two decimal places.
11. `total_actual_spend` equals the sum of the returned daily point spends; `average_daily_spend` equals that total divided by `window_days`, rounded to two decimal places.
12. Rows exactly at `window_start` are included; rows exactly at `window_end` are excluded.
13. The API is safe for new users with no ledger rows: it returns zero-filled 7d and 30d windows rather than 404.
14. The API response does not expose raw `metadata_json`, payment references, JWTs, API keys, emails, phone numbers, source payload bodies, or invoice line item details.
15. The implementation should share or centralize the actual-spend ledger formula with invoice code, so 5.D.1 and 5.D.2 cannot drift silently.
16. Web API helpers in `apps/web/src/lib/api.ts` expose typed `getBillingUsageTrends(jwt)` against `BILLING_SERVICE_URL` and preserve bearer auth plus existing error handling.
17. The Console billing page reads `sessionStorage.getItem("jwt_access")`, redirects unauthenticated users to `/auth/login`, and does not write trends, PDF bytes, or bearer tokens to storage.
18. The Console page shows 7d and 30d trend charts using `SparklineKPI` on the first billing screen, with bilingual labels and accessible aria labels that name the window and usage-spend metric.
19. The UI handles empty/zero trend data without blank charts, layout shift, text overflow, or NaN/Infinity display.
20. Trend loading/error state is independent from invoice period loading; a trend failure must not mask invoice data, and an invoice failure must not erase a successful trend chart.
21. The implementation reuses `@opticloud/ui` and does not add a charting library or duplicate `SparklineKPI` logic in the web app.
22. Tests cover owner scoping, UTC day boundaries, zero-filled windows, refund/partial-refund/reversal spend math, read-only behavior, no raw metadata leakage, API helper URL/auth typing, unauthenticated redirect, Console rendering of both SparklineKPI charts, and storage hygiene.
23. Quality gates pass:
    - focused billing usage trend tests;
    - focused web trend/API/page tests;
    - focused `SparklineKPI` tests if the component changes;
    - relevant billing-service regression;
    - web/ui test suites and typecheck;
    - ruff/format/mypy for touched Python files;
    - `git diff --check`.

## Tasks / Subtasks

- [x] T1: Add shared ledger spend helper (AC: 9-15)
  - [x] Centralize charge-related spend kinds and the actual-spend calculation used by invoices and trends.
  - [x] Keep the helper pure and independent of HTTP, Pydantic, or route concerns.
  - [x] Preserve 5.D.1 invoice semantics while removing formula duplication/drift risk.

- [x] T2: Add billing usage trends schema and builder (AC: 3-15)
  - [x] Define Pydantic response models in `apps/billing-service/src/billing_service/schemas.py`.
  - [x] Add a builder module or focused helper that returns 7d/30d UTC daily buckets.
  - [x] Accept optional `now_utc` in the builder for deterministic tests.
  - [x] Zero-fill missing days and serialize money as two-decimal strings.
  - [x] Ensure raw metadata never leaves the service.

- [x] T3: Add billing usage trends route (AC: 1-3, 13-15)
  - [x] Add `GET /v1/billing/usage-trends`.
  - [x] Use `require_user`; never accept client-provided `user_id`.
  - [x] Keep the route read-only and status-safe.

- [x] T4: Add backend tests (AC: 1-15, 22-23)
  - [x] Test owner scoping and no cross-user leakage.
  - [x] Test UTC window start/end inclusivity.
  - [x] Test zero-filled 7d/30d windows for users with sparse or no rows.
  - [x] Test charge/refund/refund_partial/refund_reversal spend math.
  - [x] Test read-only counts before/after endpoint calls.
  - [x] Test forbidden metadata/PII/payment fields are not present.

- [x] T5: Add web API helper tests (AC: 16, 22)
  - [x] Add typed trend interfaces and `getBillingUsageTrends(jwt)`.
  - [x] Assert URL, Authorization header, and contract field.
  - [x] Assert RFC7807-style error handling remains preserved.

- [x] T6: Wire Console billing page to SparklineKPI (AC: 17-21)
  - [x] Load trends independently from invoice list/detail.
  - [x] Render two SparklineKPI charts on the first billing screen.
  - [x] Show clear zero/empty and error states without hiding invoice data.
  - [x] Keep the existing authenticated download and invoice flows intact.
  - [x] Add page tests for unauth redirect, trend rendering, independent error state, and storage hygiene.

- [x] T7: Harden SparklineKPI only where required (AC: 18-21)
  - [x] Avoid NaN/Infinity for empty or non-finite values.
  - [x] Preserve stable dimensions for chart SVG and value display.
  - [x] Ensure aria label/description are coherent and testable.
  - [x] Add focused component tests if code changes.

- [x] T8: Review, gates, and GitHub sync (AC: 22-23)
  - [x] Run focused backend/web/ui tests.
  - [x] Run backend regression and static checks for touched Python.
  - [x] Run web/ui typecheck and relevant test suites.
  - [x] Run post-implementation code review and fix findings.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.

## Dev Notes

### Backend Patterns To Reuse

- Router owner: `apps/billing-service/src/billing_service/routes.py` under `billing_router = APIRouter(prefix="/v1/billing")`.
- Auth owner scoping: use `user_id: uuid.UUID = Depends(require_user)` and never client-provided `user_id`.
- Read-only pattern: `GET /balance` and invoice reads are pure and must not call `_seed_demo_balance`.
- Ledger source: `CreditTransaction` with signed `amount`, `kind`, `bucket`, `currency`, pointer-safe `metadata_json`, and `created_at`.
- Error pattern: existing routes use `_problem_response(...)` for RFC 7807-style errors, but this route should normally return zero-filled success for no rows.
- Decimal output pattern: money is serialized as strings with two places.

### Trend Contract Rules

- Contract name: `billing_usage_trends_v1`.
- Public route: `GET /v1/billing/usage-trends`.
- Windows: exactly `7` and `30`.
- UTC window for `N`: current UTC date plus previous `N-1` dates; `window_start = 00:00 UTC` of first date; `window_end = 00:00 UTC` of the day after the current UTC date.
- Point order: ascending by date.
- Point count: exactly `window_days`.
- Daily spend formula: `max(0, -sum(amount for charge-related rows in that UTC day))`.
- Charge-related kinds: `charge`, `refund`, `refund_partial`, `refund_reversal`.
- Excluded from spend: `topup`, `monthly_refill`, `subscription_proration`, education grants, unknown adjustments.
- `total_actual_spend` is sum of returned point spends so the chart and total cannot disagree.
- Use optional `now_utc` for deterministic tests; production callers use current UTC.

### Frontend Patterns To Reuse

- `apps/web/src/lib/api.ts` already defines `BILLING_SERVICE_URL`, `request<T>()`, `OptiCloudClientError`, and billing invoice helpers.
- Existing Console billing route `/console/billing/invoices` already reads `sessionStorage.getItem("jwt_access")`, redirects unauthenticated users, and uses a dense operational layout.
- Use `SparklineKPI` from `@opticloud/ui`; do not add a chart library.
- Keep trend state separate from invoice state to avoid stale/error coupling.
- Use bilingual visible labels and explicit aria labels for both windows.

### Suggested Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/solver-orchestrator/src;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_usage_trends_routes.py -q
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/solver-orchestrator/src;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_invoice_routes.py apps/billing-service/tests/test_usage_trends_routes.py -q
uv run ruff check apps/billing-service/src/billing_service apps/billing-service/tests/test_usage_trends_routes.py apps/billing-service/tests/test_invoice_routes.py
uv run ruff format --check apps/billing-service/src/billing_service apps/billing-service/tests/test_usage_trends_routes.py apps/billing-service/tests/test_invoice_routes.py
uv run mypy apps/billing-service/src/billing_service
pnpm --dir apps/web vitest run src/lib/billing-trends.test.ts src/app/console/billing/invoices/page.test.tsx
pnpm --dir packages/ui vitest run src/components/SparklineKPI/index.test.tsx src/components/Tier1.a11y.test.tsx
pnpm --dir apps/web test
pnpm --dir apps/web typecheck
pnpm --dir packages/ui test
pnpm --dir packages/ui typecheck
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Implementation satisfies every Acceptance Criterion without implementing 5.D.3-5.D.7 scope early.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review and gates.
- Branch is pushed, PR is created, merged to `main`, remote branch is deleted, and local `main` is synced.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline commit: `e11d64dd2c1a94b4ef10ce6387809a4a29142ad5`.
- Focused backend usage trends tests passed: `uv run pytest apps/billing-service/tests/test_usage_trends_routes.py -q` (3 tests).
- Focused invoice + trends backend tests passed: `uv run pytest apps/billing-service/tests/test_invoice_routes.py apps/billing-service/tests/test_usage_trends_routes.py -q` (9 tests).
- Billing-service regression passed: `uv run pytest apps/billing-service/tests -q` (280 tests, 5 existing FastAPI deprecation warnings).
- Focused web trend/page tests passed: `pnpm vitest run src/lib/billing-trends.test.ts src/app/console/billing/invoices/page.test.tsx` (8 tests).
- Focused UI SparklineKPI/a11y tests passed: `pnpm vitest run src/components/SparklineKPI/index.test.tsx src/components/Tier1.a11y.test.tsx` (16 tests).
- Web regression passed: `pnpm test` in `apps/web` (28 files, 137 tests).
- UI regression passed: `pnpm test` in `packages/ui` (12 files, 83 tests).
- Static gates passed: `uv run ruff check ...`, `uv run ruff format --check ...`, `uv run mypy apps/billing-service/src/billing_service`, `pnpm typecheck` in `apps/web`, `pnpm typecheck` in `packages/ui`, and `git diff --check`.
- GitHub PR #128 checks passed before merge: changes, billing-service-test, lint, mypy, ts-typecheck, e2e, chromatic, matrix-detect, gtm-toolkit-validation, and build-and-sbom.

### Completion Notes List

- Added read-only authenticated `GET /v1/billing/usage-trends` with `billing_usage_trends_v1` contract, exactly 7d/30d UTC day windows, zero-filled ordered points, and no client-provided `user_id`.
- Centralized charge-related actual-spend math in `billing_service.spend` and reused it from invoices and usage trends to avoid 5.D.1/5.D.2 formula drift.
- Implemented ledger-derived daily spend buckets using only `charge`, `refund`, `refund_partial`, and `refund_reversal`; topups, grants, proration, and unknown adjustments remain excluded from usage spend.
- Added typed web API helper `getBillingUsageTrends(jwt)` against `BILLING_SERVICE_URL`.
- Wired the billing Console first screen to load trends independently from invoice detail and render 7d/30d charts through shared `SparklineKPI`.
- Hardened `SparklineKPI` for empty/non-finite data, stable SVG dimensions, and coherent aria description linkage.
- Completed post-implementation code review; fixed trend-specific error copy and removed the large trend container card to keep the billing surface aligned with the app layout rules.

### File List

- `_bmad-output/stories/5-d-2-7d-30d-sparkline-trends.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/billing-service/src/billing_service/invoices.py`
- `apps/billing-service/src/billing_service/routes.py`
- `apps/billing-service/src/billing_service/schemas.py`
- `apps/billing-service/src/billing_service/spend.py`
- `apps/billing-service/src/billing_service/usage_trends.py`
- `apps/billing-service/tests/test_usage_trends_routes.py`
- `apps/web/src/app/console/billing/invoices/page.tsx`
- `apps/web/src/app/console/billing/invoices/page.test.tsx`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/billing-trends.test.ts`
- `packages/ui/src/components/SparklineKPI/index.tsx`
- `packages/ui/src/components/SparklineKPI/index.test.tsx`

## Change Log

- 2026-05-31 - Story created for read-only billing usage trends API, Console SparklineKPI integration, and drift guards from 5.D.1 invoice summary.
- 2026-05-31 - Implemented usage trends API, web helper, billing Console charts, SparklineKPI hardening, tests, post-review fixes, and local quality gates; status set to done.

## Senior Developer Review (AI)

Findings:

- [x] [Review][Patch] Trend API errors in the Console reused invoice-specific normalization, so a trend 404/400 could show "账单月份" copy. Patched a dedicated trend error normalizer and added coverage through the independent trend-failure page test path.
- [x] [Review][Patch] The trend area was introduced as a large bordered page card, which risked a card-heavy nested billing surface. Patched it into an unframed section while keeping individual chart cards for repeated items.
- [x] [Review][Patch] `SparklineKPI` computed the aria description string twice after hardening. Consolidated the description before calling `useA11y`.

Additional review notes:

- Owner scoping is bounded to `require_user`; no route accepts `user_id`.
- Trend generation is read-only and queries only charge-related ledger rows.
- The `billing_usage_trends_v1` contract remains distinct from invoice `invoice_summary`.
- No raw ledger metadata, payment references, JWTs, API keys, emails, phones, or payload bodies are exposed.
- No new charting dependency was added.

Decision: Approved after patch.

## Pre-Implementation Adversarial Review

### Round 1 - Boundary, Scope Creep, Auth Isolation, And Read-Only Behavior

Findings:

1. The trend dashboard could accidentally become a budget or notification feature.
2. A route accepting `user_id` would create cross-tenant lookup risk.
3. New-user/no-ledger behavior was ambiguous and could return 404, making the dashboard look broken.
4. The endpoint could mutate state by sharing charge/balance code that seeds demo credits.
5. The trend contract could reuse `invoice_summary`, causing 5.D.1 and 5.D.2 clients to drift.
6. The page could render charts on a marketing-style landing surface instead of the operational Console.
7. The implementation could add a chart dependency instead of using Tier 1 `SparklineKPI`.

Revision after Round 1:

- Explicitly limited scope to usage-spend trends only and excluded budget/template/notification work.
- Required `require_user` owner scoping and forbade any client-provided `user_id`.
- Required zero-filled success for users with no rows.
- Added read-only mutation prohibitions.
- Required `billing_usage_trends_v1` and forbade `invoice_summary` reuse.
- Required existing Console billing page plus `@opticloud/ui` `SparklineKPI`.

### Round 2 - Drift, UTC Boundaries, Data Consistency, And Spend Semantics

Findings:

1. "Usage trend" could be interpreted as balance movement, topups, grants, or total ledger movement.
2. 7d/30d windows could drift between rolling 24-hour windows and UTC calendar-day buckets.
3. Missing days could be omitted, changing the chart length and making 7d/30d comparisons unstable.
4. Refund and partial refund rows could be double-counted or ignored.
5. `total_actual_spend` could disagree with the points shown in the chart.
6. Rows at exact boundaries needed explicit inclusive/exclusive rules.
7. Raw metadata could leak if the endpoint reused invoice line-item serialization.
8. Invoice and trend actual-spend formulas could silently diverge.

Revision after Round 2:

- Defined the metric as actual usage spend from charge-related ledger kinds only.
- Fixed UTC calendar-day semantics and point counts.
- Required zero-filled ordered points.
- Locked the daily formula and included refund/refund_partial/refund_reversal.
- Defined `total_actual_spend` as the sum of returned point spends.
- Added boundary inclusion/exclusion rules.
- Forbade raw metadata exposure.
- Required shared or centralized formula code with 5.D.1.

### Round 3 - Dependency Closure, UI A11y, Error Independence, And Test Closure

Findings:

1. `SparklineKPI` currently has limited coverage for empty/zero arrays.
2. The chart could display NaN/Infinity or collapse when values are empty.
3. `ariaLabel` alone may not give screen-reader users enough metric context.
4. Trend loading errors could block invoice loading or leave stale invoice state.
5. Invoice errors could hide successful trend charts.
6. Web tests could mock only invoice helpers and miss the new trend contract.
7. Adding chart dependencies would expand dependency and CI surface unnecessarily.
8. Gates must include both `apps/web` and `packages/ui` when the shared UI component changes.

Revision after Round 3:

- Added explicit SparklineKPI hardening and focused component tests.
- Required stable dimensions, no NaN/Infinity, and coherent aria labels/descriptions.
- Required independent trend and invoice state/error handling.
- Added web API/page test requirements for the trend helper and both charts.
- Forbade chart dependencies and added `packages/ui` gates.
