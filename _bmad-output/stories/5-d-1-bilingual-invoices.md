---
story_key: 5-d-1-bilingual-invoices
baseline_commit: 4b17edd4341db41a137446f2cea5cb85c4544c55
epic_num: 5
story_num: D.1
epic_name: Billing - Invoices + Templates + Budget + Notifications
status: done
priority: High
type: bilingual invoice API, PDF download, and Console view
created_by: bmad-create-story
created_at: 2026-05-30
sources:
  - _bmad-output/planning/epics.md (Epic 5.D / Story 5.D.1 / Story 5.D.2 split)
  - _bmad-output/planning/prd.md (FR B7; v1 zh-CN primary with reserved i18n)
  - _bmad-output/planning/architecture.md (billing-service owner; web Console; i18n concern)
  - _bmad-output/stories/5-c-5-pipl-self-service-portal.md
  - apps/billing-service/src/billing_service/routes.py
  - apps/billing-service/src/billing_service/schemas.py
  - apps/billing-service/src/billing_service/models.py
  - apps/billing-service/src/billing_service/plans.py
  - apps/web/src/lib/api.ts
  - apps/web/src/app/console/data-exports/page.tsx
  - packages/ui/src/components/SparklineKPI/index.tsx
---

# Story 5.D.1 - 双语 Invoices

Status: done

## Story

**As** an authenticated OptiCloud billing user,
**I want** to view and download a monthly bilingual billing invoice,
**so that** I can audit my subscription credits, usage charges, refunds, and month-to-date spending in Chinese and English.

## Context

FR B7 says users can view bilingual invoices plus 7d/30d usage trends. Epic 5.D splits this into Story 5.D.1 "双语 invoices" and Story 5.D.2 "7d/30d usage trends SparklineKPI". Therefore this story owns invoice data, bilingual rendering, PDF download, and a minimal invoice-embedded usage summary. It must not implement the full dashboard trend feature that 5.D.2 owns.

Existing billing data is already in `billing-service`: `credit_transactions` is the ledger source of truth, `billing_subscriptions` tracks the active monthly plan/period, and charge/refund sagas already write pointer-safe ledger metadata. There is no invoice model or endpoint today.

In this story, "invoice" means an OptiCloud billing statement for product usage and credits. UI/PDF copy must not imply a legal tax invoice, VAT invoice, or Chinese fapiao.

The repository has no PDF dependency in `apps/billing-service/pyproject.toml`. This story permits adding one focused Python PDF dependency for backend PDF generation. Do not fake a PDF by serving HTML with `application/pdf`.

## Scope

1. Add read-only monthly invoice APIs to `billing-service`.
2. Aggregate invoice rows from the authenticated user's existing ledger and subscription rows; no user id is accepted in query/path/body.
3. Return bilingual zh-CN/en-US invoice fields in JSON.
4. Generate a real PDF download from the same invoice view model.
5. Add a Console page where the current user can view the invoice and download the PDF.
6. Include a minimal 7d/30d usage summary in invoice JSON and UI using existing ledger amounts; full reusable trend dashboard remains 5.D.2.
7. Add focused backend, web API, and page tests.
8. Run post-implementation code review, fix findings, pass gates, and sync GitHub.

## Out Of Scope

- Legal tax/VAT/fapiao claims, payment-provider receipts, tax IDs, or official accounting invoice status.
- Editing legal footer copy outside this page/PDF.
- Persisting invoice rows unless implementation proves it is required; v1 may derive deterministic monthly statements from immutable ledger rows.
- New payment provider integrations.
- New user/profile PII fields, billing addresses, email delivery, or notification preferences.
- Full 7d/30d Sparkline dashboard, reusable trend analytics endpoint, or `InvoiceCard` Tier 2 component. Those are Stories 5.D.2 and 5.D.7.
- Changing charge, topup, refund, subscription, or monthly refill semantics.
- Cross-user/admin invoice lookup.

## Acceptance Criteria

1. `GET /v1/billing/invoices` returns an authenticated, user-scoped list of available monthly invoice summaries, ordered newest first.
2. `GET /v1/billing/invoices/{period}` returns a single invoice for `YYYY-MM` in UTC month boundaries `[month_start, next_month_start)`.
3. `GET /v1/billing/invoices/{period}/download` returns a real PDF with `Content-Type: application/pdf` and a deterministic filename such as `opticloud-invoice-2026-05.pdf`.
4. Missing or malformed periods return status-safe RFC 7807-style errors; cross-tenant lookup is impossible because the authenticated user is the only owner input and no route accepts `user_id`.
5. Invoice JSON contains bilingual labels/text for billing statement title, period, plan, credit grants, topups, usage charges, refunds, net credit movement, actual spend, usage summary fields, and a "not a tax invoice / 非税务发票" disclaimer.
6. The invoice line items are derived from `credit_transactions` for the current user and period, including monthly refill, subscription proration, topup confirmation, charge, refund, refund_partial, and refund_reversal rows when present; unknown user-owned kinds are shown as bilingual "Other adjustment / 其他调整" rows rather than silently dropped.
7. Amounts are serialized as decimal strings with two places for display totals; line items may expose a dedicated `source_amount` four-decimal string, but must not expose raw `metadata_json`.
8. `net_credit_movement` equals the signed sum of included ledger rows for the period. `actual_spend` is a separate positive usage-spend number derived only from charge-related rows, so topups/monthly grants are not misreported as spend.
9. Subscription metadata for the period is shown when a subscription overlaps the requested month; users without an overlapping subscription still get a valid Free/implicit invoice statement if ledger rows exist.
10. Invoice generation is read-only: it must not seed demo credits, create subscriptions, create idempotency rows, write outbox events, or mutate ledger rows.
11. 7d/30d usage summary uses ledger-derived actual spend for the latest 7 and 30 days ending at the invoice period end or now, whichever is earlier; it is bounded to the invoice owner and does not require a new analytics table.
12. The API response explicitly marks the trend payload as invoice summary data, not the full 5.D.2 dashboard trend contract.
13. PDF generation uses the same invoice view model as JSON so totals, line items, period, and bilingual labels cannot drift.
14. PDF content includes Chinese and English labels and enough extractable or otherwise verifiable text for automated tests to verify title, period, user id suffix, totals, tax-disclaimer, and at least one line item.
15. PDF content must not contain JWTs, API keys, phone numbers, emails, payment references, raw payload bodies, or arbitrary `metadata_json` dumps.
16. Web API helpers in `apps/web/src/lib/api.ts` expose typed invoice list/detail/download functions against `BILLING_SERVICE_URL`.
17. A new Console route, proposed as `/console/billing/invoices`, reads `sessionStorage.getItem("jwt_access")`, redirects unauthenticated users to `/auth/login`, and never stores downloaded PDF bytes or bearer tokens in browser storage.
18. The Console page first screen is the invoice tool: period selector/list, bilingual invoice summary, ledger line items, usage summary, tax-disclaimer, and PDF download action in a dense operational layout.
19. PDF download uses authenticated fetch, object URL creation, generated anchor click, and object URL revocation; no naked download URL is rendered.
20. The page links from at least one existing Console navigation area so invoices are discoverable.
21. The implementation updates dependency manifests and locks consistently: any Python PDF dependency added to `apps/billing-service/pyproject.toml` must also update root `uv.lock`; no untracked generated artifacts or platform-local font files are committed unless explicitly required and documented.
22. Tests cover owner scoping, malformed/missing periods, UTC month boundaries, read-only behavior, line-item classification, refund/partial refund representation, PDF content/security, web API helper calls, unauthenticated redirect, UI rendering, download revocation, and storage hygiene.
23. Quality gates pass:
    - focused billing invoice tests;
    - focused web invoice tests;
    - relevant billing-service regression;
    - web test suite and typecheck;
    - ruff/format/mypy for touched Python files;
    - `git diff --check`.

## Tasks / Subtasks

- [x] T1: Add invoice schema and service logic (AC: 1-15)
  - [x] Define Pydantic response models in `apps/billing-service/src/billing_service/schemas.py`.
  - [x] Add a small invoice builder module or route-local helpers that aggregate ledger rows for a user and UTC period.
  - [x] Classify known ledger kinds into bilingual line-item labels without dumping raw metadata.
  - [x] Compute signed net credit movement, credit/debit subtotals, positive actual spend, latest 7d/30d spend summary values, and subscription/plan display fields.
  - [x] Add explicit billing-statement/not-tax-invoice bilingual disclaimer fields.
  - [x] Ensure the builder is pure read-only and deterministic for the same database snapshot.

- [x] T2: Add billing invoice HTTP routes (AC: 1-15)
  - [x] Add `GET /v1/billing/invoices`.
  - [x] Add `GET /v1/billing/invoices/{period}`.
  - [x] Add `GET /v1/billing/invoices/{period}/download`.
  - [x] Return status-safe errors for malformed period and not-found/no-ledger cases.
  - [x] Ensure all routes use `require_user` and never accept `user_id` from client input.

- [x] T3: Add real PDF generation (AC: 3, 13-15, 21)
  - [x] Add one focused Python PDF dependency to `apps/billing-service/pyproject.toml` and refresh `uv.lock`.
  - [x] Keep the PDF generator in a dedicated module, e.g. `billing_service/invoices.py` or `billing_service/pdf.py`; routes should only call it.
  - [x] Generate the PDF server-side from the invoice view model.
  - [x] Include bilingual title, period, totals, usage summary, and line items.
  - [x] Include the not-tax-invoice disclaimer in both languages.
  - [x] Keep PDF text/content verification testable in Linux CI without relying on Windows-local fonts or GUI/browser rendering.
  - [x] Add security tests proving forbidden tokens/PII/raw metadata do not appear in PDF bytes/text.

- [x] T4: Add billing-service invoice tests (AC: 1-15, 21-23)
  - [x] Test list/detail happy path with mixed ledger rows.
  - [x] Test UTC month boundaries with rows exactly at start/end.
  - [x] Test malformed period and missing invoice behavior.
  - [x] Test owner scoping with another user's ledger rows.
  - [x] Test read-only behavior by comparing counts before/after invoice reads.
  - [x] Test refund and refund_partial classification.
  - [x] Test PDF headers, filename, extractable bilingual content, and forbidden-field absence.

- [x] T5: Add web API helpers (AC: 16, 19, 22)
  - [x] Add TypeScript invoice response/download types to `apps/web/src/lib/api.ts`.
  - [x] Add `listBillingInvoices(jwt)`, `getBillingInvoice(jwt, period)`, and `downloadBillingInvoicePdf(jwt, period)`.
  - [x] Parse non-OK PDF downloads as problem JSON when possible, otherwise return status-safe fallback errors.
  - [x] Add focused Vitest coverage for URLs, Authorization, response typing, PDF filename, and error handling.

- [x] T6: Add Console invoice page (AC: 17-20, 22)
  - [x] Create `/console/billing/invoices` page.
  - [x] Use the existing sessionStorage login pattern and redirect unauthenticated users to `/auth/login`.
  - [x] Render actual invoice data as the first screen; avoid a marketing/landing page.
  - [x] Show period selector, bilingual totals, line items, and invoice summary trend values.
  - [x] Download PDFs through the authenticated helper and revoke object URLs.
  - [x] Add discoverability link from an adjacent Console header.
  - [x] Add component tests for redirect, render, period selection, download, object URL revocation, and no storage writes.

- [x] T7: Run review, gates, and GitHub sync (AC: 23)
  - [x] Run focused backend tests and billing regression.
  - [x] Run focused web tests, full web tests, and web typecheck.
  - [x] Run ruff, format check, mypy for touched Python code.
  - [x] Run post-implementation code review and fix findings.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.

## Dev Notes

### Existing Backend Patterns To Reuse

- Router owner: `apps/billing-service/src/billing_service/routes.py` under `billing_router = APIRouter(prefix="/v1/billing")`.
- Auth owner scoping: use `user_id: uuid.UUID = Depends(require_user)` and never client-provided `user_id`.
- Read-only balance behavior: `GET /balance` is pure and must not call `_seed_demo_balance`; invoices must follow this pattern.
- Ledger source: `CreditTransaction` with `user_id`, `saga_id`, signed `amount`, `kind`, `bucket`, `currency`, pointer-safe `metadata_json`, `created_at`.
- Subscription source: `BillingSubscription` plus `get_plan()`/`_implicit_free_subscription_response()` patterns.
- Error pattern: existing routes return `_problem_response(...)` for RFC 7807-style status-safe errors.
- Decimal output pattern: existing responses serialize money as strings, normally `f"{amount:.2f}"`.

### Period And Data Rules

- Treat invoice period as UTC calendar month `YYYY-MM`.
- Include rows where `period_start <= CreditTransaction.created_at < period_end`.
- Sort line items by `created_at ASC`, then deterministic id/string fallback if timestamps tie.
- If a month has neither ledger rows nor a subscription overlapping that period, return 404 "Invoice Not Found".
- A current-month invoice is provisional/read-only and may change as new ledger rows arrive; expose this as a bilingual status field rather than persisting snapshots.
- For current month, 7d/30d summary window end is `min(now_utc, period_end)`.
- Make the invoice builder accept an optional `now_utc` for deterministic tests; production callers pass current UTC.
- `net_credit_movement`: signed sum of every included owner ledger row.
- `credit_subtotal`: positive sum of included rows where `amount > 0`.
- `debit_subtotal`: positive absolute sum of included rows where `amount < 0`.
- `actual_spend`: `max(0, -sum(amount for rows whose kind is one of charge, refund, refund_partial, refund_reversal))`. This handles partial refunds, full rollback refunds, and reserved net-zero refund/reversal pairs without double counting.
- 7d/30d usage summary uses the same `actual_spend` formula over the rolling window. It excludes topups, monthly refills, education grants, and subscription proration from spend, while those rows remain visible in the billing statement and net credit movement.
- Known kind label map must include at least `monthly_refill`, `subscription_proration`, `topup`, `charge`, `refund`, `refund_partial`, and `refund_reversal`. Unknown kinds get a safe "Other adjustment / 其他调整" label.
- Safe metadata extraction is allowlist-only. Permitted line-item detail keys are limited to non-PII pointers/labels such as `subscription_id`, `plan_code`, `trigger`, `bucket`, `reason`, and `refund_kind`; never return arbitrary `metadata_json`.
- Do not infer legal tax invoice status from credits ledger; use "billing statement / invoice" copy plus "非税务发票 / Not a tax invoice".

### PDF Dependency Guidance

- Use one backend PDF library only. Prefer a Python library that works in CI without browser/system rendering services.
- Do not add a Node PDF stack for this story; PDF generation belongs next to billing invoice data.
- If using ReportLab, keep the drawing code in a small module, not scattered across route handlers. Do not assume CI has Chinese system fonts; either use a dependency/built-in font path that works in Linux CI or use deterministic PDF content tests that prove the bilingual source text is represented without committing platform-local fonts.
- Do not use screenshots, headless browsers, or external PDF services.
- Update `uv.lock` with the dependency change and ensure CI's `uv sync --all-packages --extra dev` can install it.

### Frontend Patterns To Reuse

- `apps/web/src/lib/api.ts` already has `BILLING_SERVICE_URL`, generic JSON request handling, and authenticated billing helpers.
- Console pages are client components with compact headers; reuse the wrap-safe nav pattern from `/console/data-exports`, `/console/chat`, and `/console/repro`.
- Download pattern: use authenticated `fetch`, Blob, `URL.createObjectURL`, generated `<a>`, click, and revoke, as in Story 5.C.5.
- Token pattern: read `sessionStorage.getItem("jwt_access")`; do not introduce localStorage token writes.
- The page should be operational and dense, with cards only for individual repeated sections, not nested page cards.

### Testing Notes

- Billing route tests already create JWTs and ASGI clients in `apps/billing-service/tests/test_charge_routes.py` and `test_subscription_routes.py`; reuse those patterns.
- Insert test ledger rows directly with SQLAlchemy/text for deterministic periods.
- For PDF text checks, use only dependencies present in the project or added explicitly by this story. At minimum assert `%PDF`, `Content-Type`, filename, non-empty bytes, and deterministic text/security markers from the generated source model; do not rely on a local desktop PDF viewer.
- Web component tests should mock `next/navigation`, `next/link` if needed, API helpers, object URL methods, and generated anchor click.

### Previous Story Intelligence

- Story 5.C.5 established the safe browser download pattern, current-session-only state, no naked protected URLs, object URL revocation, and storage hygiene tests.
- 5.C.5 post-review fixed mobile Console header overflow by allowing wrap-safe brand/nav rows; reuse that pattern immediately.
- Local `pnpm lint` may prompt for first-time Next ESLint setup; do not treat it as a reliable local gate unless it is configured during this story.

### Suggested Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/solver-orchestrator/src;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_invoice_routes.py -q
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/solver-orchestrator/src;apps/billing-service/src'; uv run pytest apps/billing-service/tests -q
uv run ruff check apps/billing-service/src/billing_service apps/billing-service/tests/test_invoice_routes.py
uv run ruff format --check apps/billing-service/src/billing_service apps/billing-service/tests/test_invoice_routes.py
uv run mypy apps/billing-service/src/billing_service
pnpm --dir apps/web vitest run src/lib/billing-invoices.test.ts src/app/console/billing/invoices/page.test.tsx
pnpm --dir apps/web test
pnpm --dir apps/web typecheck
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Implementation satisfies every Acceptance Criterion without implementing 5.D.2/5.D.7 scope early.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review and gates.
- Branch is pushed, PR is created, merged to `main`, remote branch is deleted, and local `main` is synced.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline commit: `4b17edd4341db41a137446f2cea5cb85c4544c55`.
- Focused backend invoice tests passed: `uv run pytest apps/billing-service/tests/test_invoice_routes.py -q` (6 tests).
- Billing-service regression passed: `uv run pytest apps/billing-service/tests -q` (277 tests, 5 existing FastAPI deprecation warnings).
- Focused web invoice tests passed: `pnpm vitest run src/lib/billing-invoices.test.ts src/app/console/billing/invoices/page.test.tsx` (9 tests).
- Web regression passed: `pnpm test` (27 files, 134 tests).
- Static gates passed: `uv run ruff check ...`, `uv run ruff format --check ...`, `uv run mypy apps/billing-service/src/billing_service`, `pnpm typecheck`, and `git diff --check`.

### Completion Notes List

- Added read-only, authenticated, owner-scoped monthly billing statement list/detail/download APIs under `/v1/billing/invoices`.
- Built invoice view models from `credit_transactions` and overlapping `billing_subscriptions`; no invoice table, demo seeding, idempotency rows, outbox writes, or client-provided `user_id` were introduced.
- Added bilingual JSON fields and UI/PDF copy for billing-statement title, line-item labels, plan display, status, 7d/30d invoice spend summaries, and `非税务发票 / Not a tax invoice`.
- Added ReportLab PDF generation from the same invoice view model, with deterministic filename, CJK-capable rendering, all line items across pages, and security tests preventing raw metadata/token/payment-reference leakage.
- Added typed web API helpers and `/console/billing/invoices` Console page with period selection, dense statement layout, usage summary, ledger rows, authenticated Blob download, object URL revocation, and storage hygiene tests.
- Added discoverability link from the existing Console data-export navigation.
- Completed post-implementation code review; fixed PDF line-item truncation risk, UTC period-key helper hardening, avoidable type ignores, negative amount display, and stale invoice data on period-load failure.

### File List

- `_bmad-output/stories/5-d-1-bilingual-invoices.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/billing-service/pyproject.toml`
- `apps/billing-service/src/billing_service/invoices.py`
- `apps/billing-service/src/billing_service/routes.py`
- `apps/billing-service/src/billing_service/schemas.py`
- `apps/billing-service/tests/test_invoice_routes.py`
- `apps/web/src/app/console/billing/invoices/page.tsx`
- `apps/web/src/app/console/billing/invoices/page.test.tsx`
- `apps/web/src/app/console/data-exports/page.tsx`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/billing-invoices.test.ts`
- `uv.lock`

## Change Log

- 2026-05-30 - Story created with invoice/PDF scope, 5.D.2 trend boundary, owner-scoped billing guardrails, and authenticated Console download requirements.
- 2026-05-31 - Implemented bilingual invoice APIs, PDF download, Console page, focused tests, post-review fixes, and local quality gates; status set to done.

## Senior Developer Review (AI)

Findings:

- [x] [Review][Patch] PDF rendering iterated only the first 24 line items, which could silently omit long monthly statements. Patched the renderer to paginate and include every line item, with a regression test that verifies 60 charge rows all appear in the generated PDF bytes.
- [x] [Review][Patch] Invoice helper typing and UTC boundaries had avoidable drift risk: `_period_key` relied on caller normalization and several literals used type ignores. Patched `_period_key` to normalize internally and replaced type ignores with typed literals/casts.
- [x] [Review][Patch] The Console page displayed negative amounts as `¥-0.50` and could retain a stale invoice while a selected period reload failed. Patched display to `-¥0.50`, cleared stale invoice state on period load, and added a focused UI assertion.

Additional review notes:

- Owner scoping remains bounded to `require_user`; no route accepts `user_id`.
- Invoice generation is read-only and derives statements from ledger/subscription rows without new persistence.
- PDF, JSON, and UI all use the billing-statement/not-tax-invoice disclaimer and avoid legal tax invoice claims.
- No raw ledger metadata, payment references, API keys, JWTs, emails, or arbitrary payload bodies are exposed in invoice JSON/PDF.

Decision: Approved after patch.

## Pre-Implementation Adversarial Review

### Round 1 - Boundary, Legal Copy, PDF Authenticity, Auth Isolation, And Scope Creep

Findings:

1. The word "invoice" could be implemented as a legal/tax invoice without supporting tax data.
2. The story did not require an explicit "not a tax invoice / 非税务发票" disclaimer in JSON, PDF, and UI.
3. PDF authenticity was stated, but PDF testability did not force bilingual text/disclaimer verification.
4. The route contract said owner-scoped, but did not explicitly forbid `user_id` on every route.
5. Subscription display said "active subscription" only, which misses historical overlap and current-month provisional behavior.
6. The story did not define current-month invoices as provisional, inviting fake persistence/snapshot work.
7. Empty-month handling could drift between "Free invoice" and 404 without a precise rule.
8. Legal footer changes could expand scope into unrelated legal pages.
9. The Console page could omit the tax-disclaimer while backend/PDF includes it.
10. PDF generation could pass byte/header tests while not verifying meaningful billing statement content.

Revision after Round 1:

- Defined invoice as an OptiCloud billing statement, not a tax/VAT/fapiao artifact.
- Required bilingual not-tax-invoice disclaimer in JSON, PDF, and UI.
- Tightened route owner scoping to forbid client-provided `user_id`.
- Clarified overlapping subscription semantics and current-month provisional status.
- Strengthened PDF verification requirements for title, period, user suffix, totals, disclaimer, and line item.

### Round 2 - Drift, Ledger Semantics, Refund Consistency, And Trend Split

Findings:

1. "Invoice total" could be mistaken for amount due, even though Credits ledger rows include grants, topups, charges, refunds, and reversals.
2. The story did not separate signed net credit movement from positive actual user spend.
3. The 7d/30d formula risked double-counting `refund_reversal` or treating monthly credits/topups as usage.
4. Preserving "four-place source precision in metadata" could encourage raw `metadata_json` exposure.
5. Unknown ledger kinds were not specified, so an implementation could silently omit owner rows.
6. Subscription proration and education/monthly grants need visible statement rows but must not become usage spend.
7. Current-month trend windows need deterministic `now_utc` injection for tests.
8. Line-item metadata needs an explicit allowlist because prior stories intentionally kept payloads pointer-safe.
9. Refund and partial refund behavior should be validated through the ledger sign formula, not special-case UI text only.
10. 5.D.2 trend scope remains at risk unless 5.D.1 names its trend payload as invoice summary spend only.

Revision after Round 2:

- Replaced ambiguous "total" language with `net_credit_movement`, credit/debit subtotals, and `actual_spend`.
- Defined actual-spend and 7d/30d formulas over charge/refund/refund_partial/refund_reversal rows only.
- Required unknown ledger kinds to appear as safe other-adjustment line items.
- Replaced raw metadata preservation with a dedicated `source_amount` field and metadata allowlist.
- Added deterministic `now_utc` guidance for tests.

### Round 3 - Dependency Closure, PDF CI Fit, Testability, And Web Discoverability

Findings:

1. The story allowed a new PDF dependency but did not explicitly require `uv.lock` to change with `pyproject.toml`.
2. PDF font guidance still assumed a developer might rely on Windows-local fonts that fail in Linux CI.
3. The PDF route could accumulate drawing logic inside `routes.py`, making review and testing harder.
4. PDF verification could rely on a desktop viewer or ad hoc manual inspection instead of automated CI checks.
5. Web test command examples used root `pnpm test`, but prior work showed app-local `pnpm --dir apps/web ...` is more reliable.
6. The dependency update could accidentally commit generated/local font files or other artifacts.
7. The story did not explicitly tie web helper/page tests to the new invoice filenames and object URL flow.
8. CI path filters will run both billing-service and web jobs; the story should make that expected instead of surprising.
9. A new dependency must install through CI's `uv sync --all-packages --extra dev`, not only the developer's local venv.
10. The Console route discoverability requirement needed a concrete adjacent-nav pattern in tests.

Revision after Round 3:

- Added dependency lock/update AC and explicit no-untracked-artifacts guidance.
- Required PDF generation in a dedicated module and Linux-CI-safe font/content verification strategy.
- Tightened PDF test guidance away from local viewers.
- Updated suggested web commands to app-local `pnpm --dir apps/web`.
- Linked dependency behavior to CI's `uv sync --all-packages --extra dev`.
