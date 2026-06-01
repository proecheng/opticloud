---
story_key: 5-d-7-invoice-budget-tier2-component
baseline_commit: 8b4c46e
epic_num: 5
story_num: D.7
epic_name: Billing - Invoices + Templates + Budget + Notifications
status: ready-for-dev
priority: High
type: invoice and budget Tier 2 UI components
created_by: bmad-create-story
created_at: 2026-06-01
sources:
  - _bmad-output/planning/epics.md (Epic 5.D / Story 5.D.7 / UX-DR1)
  - _bmad-output/planning/ux-design-specification.md (Tier 2 component and cross-service UI rules)
  - _bmad-output/stories/5-d-1-bilingual-invoices.md
  - _bmad-output/stories/5-d-2-7d-30d-sparkline-trends.md
  - _bmad-output/stories/5-d-5-monthly-budget-alert.md
  - _bmad-output/stories/5-d-6-notification-preferences.md
  - packages/ui/src/index.ts
  - packages/ui/src/components/SparklineKPI/index.tsx
  - packages/ui/src/components/VoucherCard/index.tsx
  - packages/ui/src/components/ChatInterface/index.tsx
  - apps/web/src/lib/api.ts
  - apps/web/src/app/console/billing/invoices/page.tsx
  - apps/web/src/app/console/billing/invoices/page.test.tsx
---

# Story 5.D.7 - InvoiceCard + BudgetAlertCard Tier 2 Component

Status: code-review

## Story

**As** an authenticated OptiCloud billing user,
**I want** the billing Console to use reusable Tier 2 invoice and budget cards,
**so that** monthly statements, usage spend, budget status, and pause controls are presented consistently with the design system and remain accessible across web surfaces.

## Context

Stories 5.D.1, 5.D.2, 5.D.5, and 5.D.6 shipped the backend contracts and an inline Console implementation for billing statements, usage trends, monthly budget control, and notification channel filtering. Story 5.D.7 is the UI-system closure story for Epic 5.D: move the reusable invoice and budget presentation into `packages/ui`, export it from the single-source UI package, add Storybook/a11y coverage, and replace the web Console inline panels with the new components.

Planning has a naming tension: UX-DR1 lists `InvoiceCard` as Tier 2 and `BudgetAlertCard` as Tier 3, while Story 5.D.7 explicitly names `InvoiceCard + BudgetAlertCard Tier 2 Component`. For this story, implement both as billing-domain components in `packages/ui` and document Storybook under Tier 2. Do not change backend APIs or create a new budget/notification service.

## Scope

1. Add `InvoiceCard` in `packages/ui` as a presentation-only component for the existing billing invoice contract.
2. Add `BudgetAlertCard` in `packages/ui` as a presentation-only component for the existing monthly budget status/update contract.
3. Export both components and public prop/model types from `@opticloud/ui`.
4. Add Storybook stories, focused unit tests, and axe a11y tests for both components.
5. Replace the inline invoice summary/detail and budget panel on `/console/billing/invoices` with the new components.
6. Preserve existing API calls, auth/session behavior, budget save/disable behavior, invoice PDF download behavior, and independent invoice/trend/budget loading/error state.
7. Preserve the existing trend cards on the page; this story does not move `SparklineKPI` or trend loading into either new billing card.
8. Run post-implementation code review, fix findings, pass gates, and sync GitHub.

## Out Of Scope

- New billing-service endpoints, schemas, SQL migrations, spend formulas, budget event semantics, invoice PDF generation, or notification preference rules.
- SMTP, webhook dispatch, notification inbox, digest schedules, or provider delivery status.
- New charting libraries, ECharts integration, analytics tables, pagination/filtering, print layout, or export redesign.
- Changing `SparklineKPI`, `StatusCard`, `ChargeModal`, or existing Tier 1 components except for imports needed by the new cards.
- Storing invoice, budget, notification, JWT, webhook URL, PDF, ledger metadata, solver payload, or payment reference data in browser storage.
- A new route, marketing page, dashboard redesign, nested cards, or broad Console navigation changes.

## Acceptance Criteria

1. `packages/ui` adds `InvoiceCard` under `src/components/InvoiceCard/` and exports the component plus prop/model types from `src/index.ts`.
2. `packages/ui` adds `BudgetAlertCard` under `src/components/BudgetAlertCard/` and exports the component plus prop/model types from `src/index.ts`.
3. Both components are presentation-only: no `fetch`, no router access, no local/session storage access, no direct billing/auth imports, and no business-side persistence.
4. `InvoiceCard` renders the existing invoice contract: title, bilingual tax disclaimer, period/status, owner suffix, subscription plan, billing period dates, net credit movement, actual usage spend, credit/debit subtotals, usage summary, and line items.
5. `InvoiceCard` accepts optional `onDownloadPdf` / `isDownloading` props and fires the callback without creating object URLs itself.
6. `InvoiceCard` handles empty line items and missing optional subscription dates without `NaN`, `Invalid Date`, blank critical labels, or layout collapse.
7. `InvoiceCard` does not expose raw line-item `details` JSON by default; only safe labels, kinds, dates, directions, and amounts are rendered.
8. `BudgetAlertCard` renders the existing budget status contract: enabled/status, monthly budget amount, actual spend, percent used, threshold ratio, period dates, paused state, paused timestamp, and recent safe event summaries.
9. `BudgetAlertCard` accepts controlled `amountValue`, `onAmountChange`, `onSave`, `onDisable`, `isLoading`, `isSaving`, `message`, and `error` props; parent pages own API calls and state.
10. `BudgetAlertCard` disables save when saving or the trimmed amount is empty, and disables budget disable when saving or no budget control exists.
11. `BudgetAlertCard` shows warning/error/success/info status with icon plus text, not color alone.
12. `BudgetAlertCard` preserves failed-save form edits because the component is controlled and never resets `amountValue` internally.
13. `BudgetAlertCard` formats `percent_used` as a bounded user-facing percent: non-finite values render as `0%`, normal values round consistently, and values over 100% may display overage without throwing or resizing controls.
14. `BudgetAlertCard` handles `budget=null` or `status="not_configured"` as an explicit empty state with usable amount input and disabled disable action.
15. Both cards support Chinese-first operational copy and enough English labels where the invoice contract already provides bilingual labels.
16. Both cards use `useA11y` with stable region/status semantics, accessible names, touch-friendly buttons, visible focusable controls, and `aria-live` for user-facing save/error messages.
17. Both cards use existing design tokens and local UI utilities; no new runtime dependency is added.
18. Both cards avoid nested card-inside-card composition. Repeated rows/line items may use tables/lists, but the page section itself must not become a stack of decorative cards.
19. Both cards are responsive: no horizontal text overflow on long bilingual labels, long user suffixes, long event ids, or large currency values.
20. Storybook stories exist for normal, loading/empty, paused/error, and long-label/large-amount states as applicable.
21. Dedicated unit tests cover rendering, callback wiring, safe empty/malformed boundary handling, disabled states, controlled-message/error rendering, and absence of raw sensitive payload rendering.
22. Dedicated axe tests cover default and stressed states for both cards with zero violations.
23. `packages/ui` `test:a11y` includes the new card a11y tests.
24. Storybook/Chromatic work is limited to adding stories for existing package Storybook discovery. Do not add Chromatic tokens, workflow secrets, external snapshots, or CI provider changes in this story.
25. Unit test fixtures include intentionally sensitive `line_item.details`, event ids, and long labels to prove the cards do not render raw metadata or overflow.
26. `InvoiceCard` is only rendered when an invoice object exists. Page-owned invoice empty, invoice loading, and invoice error surfaces remain page-owned and are not moved into the component.
27. `BudgetAlertCard` owns budget-specific loading/message/error display because budget state is already independent from invoice/trend state; it must not affect invoice or trend visibility.
28. `/console/billing/invoices` imports and uses `InvoiceCard` and `BudgetAlertCard` from `@opticloud/ui` for the main statement and budget surfaces.
29. The web page keeps invoice list loading, invoice detail loading, usage trend loading, and budget loading/saving/errors independent after component extraction.
30. The web page keeps budget save/disable callbacks wired to `putBillingBudget` with the same request bodies as Story 5.D.5.
31. The web page keeps PDF download behavior in the page layer: `downloadBillingInvoicePdf`, object URL creation/revocation, filename, and existing error handling remain parent-owned.
32. The web page preserves the existing usage trend section and `SparklineKPI` behavior; `InvoiceCard` must not make a second trend API call or duplicate trend state.
33. The web page does not write invoice, budget, event, PDF, notification, or token data to browser storage beyond reading the existing `jwt_access`.
34. Existing billing Console page tests are updated to assert the new component-backed UI still renders invoices, trends, budget status, budget update/disable, period switching, PDF download, navigation, and storage hygiene.
35. `packages/ui` public types remain structurally assignable from the current `apps/web/src/lib/api.ts` invoice and budget response types without `any` adapters in the page.
36. `packages/ui` source and tests must not import from `apps/web`, `@/lib/api`, `next/*`, billing-service, or auth-service. The dependency direction is web app -> UI package only.
37. Focused tests must include a no-duplicate-state regression: a budget API failure still shows invoice and trend content, and an invoice API failure does not hide the budget card.
38. No new Playwright/E2E test is required for this component extraction unless existing unit/a11y/page tests cannot prove the changed behavior. Do not add brittle authenticated E2E setup solely for the extraction.
39. `git diff --check`, focused `packages/ui` tests/a11y tests, focused web page tests, package type checks, post-implementation code review, GitHub CI, PR merge, branch deletion, and local `main` sync complete before the story is marked `done`.

## Tasks / Subtasks

- [x] T1: Add `InvoiceCard` component (AC: 1, 3-7, 15-19, 31)
  - [x] Define package-local invoice model types that mirror `apps/web/src/lib/api.ts` without importing app code.
  - [x] Render safe statement header, summary metrics, subscription/period metadata, usage summary, and line-item table/list.
  - [x] Add optional download callback and downloading state.
  - [x] Guard date and amount formatting against invalid or missing values.

- [x] T2: Add `BudgetAlertCard` component (AC: 2-3, 8-19, 31)
  - [x] Define package-local budget status/event model types that mirror `apps/web/src/lib/api.ts`.
  - [x] Render status, period, spend, threshold, recent events, controlled amount input, save, and disable controls.
  - [x] Render parent-provided loading, success, and error messages without mutating controlled input value.
  - [x] Keep all API, persistence, and state reset decisions in the parent.
  - [x] Use icons plus text for status semantics.
  - [x] Normalize percent/date/amount display defensively.

- [x] T3: Add exports, stories, and UI tests (AC: 20-25, 33-34)
  - [x] Export both components and public types from `packages/ui/src/index.ts`.
  - [x] Add Storybook stories for default/loading/paused/error/long-content states.
  - [x] Add unit tests for rendering, callbacks, disabled states, boundaries, and sensitive-data omission.
  - [x] Add dedicated axe tests and include them in `test:a11y`.

- [x] T4: Integrate cards into billing Console (AC: 26-34, 37-38)
  - [x] Replace inline budget panel with `BudgetAlertCard`.
  - [x] Replace inline invoice header/summary/usage/line item rendering with `InvoiceCard`.
  - [x] Keep page-owned API calls, object URL download, state isolation, trend section, and error normalization unchanged.
  - [x] Update focused page tests for the component-backed surface.

- [ ] T5: Review, gates, and GitHub sync (AC: 39)
  - [x] Run focused package/web tests and static gates.
  - [x] Run post-implementation code review and fix findings.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [ ] Mark story and sprint status `done` only after merge/sync.

## Dev Notes

### Component Boundaries

- `packages/ui` is the cross-service UI source of truth (P72). Components must be adapter/data driven and must not import `apps/web`, auth-service, or billing-service code.
- Mirror only the response shapes needed by the card props. This avoids a package dependency on the web app while keeping data contracts explicit.
- Keep actions as callbacks: `InvoiceCard` may call `onDownloadPdf`; `BudgetAlertCard` may call `onSave` and `onDisable`. Parent pages own API calls, object URLs, token reads, and error normalization.
- Do not render `BillingInvoiceLineItem.details`; prior invoice stories intentionally keep raw ledger metadata out of the user surface.
- `BudgetAlertCard` is controlled. It receives `amountValue` and emits `onAmountChange`; it must not overwrite local edits after failures.
- Expose `message` and `error` as strings from the parent rather than deriving API errors inside the component. Existing `normalizeBudgetError(...)` stays in the page.
- Ensure prop model types intentionally allow the current web API response objects to pass directly. The page should not need lossy mapping functions or `as any` casts.

### Frontend Patterns To Reuse

- Follow `VoucherCard` and `ChatInterface` patterns for Tier component structure: `index.tsx`, `index.test.tsx`, `index.a11y.test.tsx`, `index.stories.tsx`, `useA11y`, `cn`, lucide icons, and Storybook titles under `Tier 2/...`.
- Storybook stories are static examples only. Do not modify `.github/workflows`, Chromatic project setup, or external visual-regression credentials.
- Use 8px-or-less radii (`rounded-md`), existing token classes, stable grid/table dimensions, and compact operational layout.
- Use icon plus text for budget statuses. Do not rely on red/green alone.
- Keep the billing Console page first-screen operational. Do not add a landing page or explanatory marketing content.

### Existing Contracts To Preserve

- Invoice API types live in `apps/web/src/lib/api.ts`: `BillingInvoiceResponse`, `BillingInvoiceUsageSummary`, `BillingInvoiceLineItem`, and related bilingual labels.
- Budget API types live in `apps/web/src/lib/api.ts`: `BillingBudgetStatusResponse`, `BillingBudgetEventSummary`, and `BillingBudgetUpdateRequest`.
- The page reads `jwt_access` from `sessionStorage` only to authenticate existing API calls. This story must not add storage writes.
- Existing `saveBlob(...)` in `/console/billing/invoices/page.tsx` owns object URL lifecycle and should remain page-layer behavior.
- Existing independent state fields are intentional: `loading`, `trendsLoading`, `budgetLoading`, `budgetSaving`, `error`, `trendsError`, `budgetError`, and `budgetMessage`.
- Existing `SparklineKPI` trend cards remain a separate page section fed by `getBillingUsageTrends(...)`.
- Keep invoice-level empty/loading/error affordances outside `InvoiceCard`; keep budget-specific loading/message/error affordances inside `BudgetAlertCard` via props.

### Suggested Commands

```powershell
pnpm --filter @opticloud/ui test -- src/components/InvoiceCard/index.test.tsx src/components/BudgetAlertCard/index.test.tsx
pnpm --filter @opticloud/ui test:a11y
pnpm --filter @opticloud/ui typecheck
pnpm --filter @opticloud/web test -- src/app/console/billing/invoices/page.test.tsx
pnpm --filter @opticloud/web typecheck
pnpm --filter @opticloud/web test
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Implementation satisfies every Acceptance Criterion without backend/API drift.
- Existing invoice, trend, budget, notification preference, account, and PDF download behaviors remain compatible.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/5-d-7-invoice-budget-tier2-component`.
- Baseline commit: `8b4c46e`.
- Focused UI component tests: `pnpm --filter @opticloud/ui test -- src/components/InvoiceCard/index.test.tsx src/components/BudgetAlertCard/index.test.tsx` -> 8 passed.
- UI a11y gate: `pnpm --filter @opticloud/ui test:a11y` -> 25 passed.
- Type checks: `pnpm --filter @opticloud/ui typecheck` and `pnpm --filter @opticloud/web typecheck` passed.
- Focused web page test: `pnpm --filter @opticloud/web test -- src/app/console/billing/invoices/page.test.tsx` -> 9 passed.
- UI package regression gate: `pnpm --filter @opticloud/ui test` -> 96 passed.
- Web package regression gate: `pnpm --filter @opticloud/web test` -> 164 passed.
- Whitespace gate: `git diff --check` passed.

### Completion Notes List

- Added presentation-only `InvoiceCard` and `BudgetAlertCard` components with package-local API-compatible model types, Storybook stories, focused unit tests, and axe coverage.
- Replaced the billing Console inline invoice/budget surfaces with `@opticloud/ui` components while preserving page-owned API calls, PDF object URL handling, trend cards, and isolated loading/error states.
- Post-implementation review found and fixed two patch items: threshold-alert budget status now uses warning semantics, and InvoiceCard no longer nests card-like bordered panels inside the outer card.

### File List

- `_bmad-output/stories/5-d-7-invoice-budget-tier2-component.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/src/app/console/billing/invoices/page.tsx`
- `apps/web/src/app/console/billing/invoices/page.test.tsx`
- `packages/ui/package.json`
- `packages/ui/src/index.ts`
- `packages/ui/src/components/InvoiceCard/index.tsx`
- `packages/ui/src/components/InvoiceCard/index.test.tsx`
- `packages/ui/src/components/InvoiceCard/index.a11y.test.tsx`
- `packages/ui/src/components/InvoiceCard/index.stories.tsx`
- `packages/ui/src/components/BudgetAlertCard/index.tsx`
- `packages/ui/src/components/BudgetAlertCard/index.test.tsx`
- `packages/ui/src/components/BudgetAlertCard/index.a11y.test.tsx`
- `packages/ui/src/components/BudgetAlertCard/index.stories.tsx`

## Change Log

- 2026-06-01 - Story created for `InvoiceCard` and `BudgetAlertCard` Tier 2 components and billing Console integration.
- 2026-06-01 - Implemented Tier 2 billing cards, Storybook/a11y/unit coverage, Console integration, and post-review fixes.

## Post-Implementation Code Review

### Findings

- [x] [Review][Patch] Budget threshold warning state was visually reported as normal active/success. Fixed by adding a warning visual status when `alert_threshold_reached=true` and the budget is not paused.
- [x] [Review][Patch] `InvoiceCard` used nested bordered card-like panels for metadata and usage summaries, conflicting with the story's no nested cards constraint. Fixed by using section dividers and left-accent summary blocks inside the outer card.

### Outcome

Changes requested internally; all findings fixed and focused gates rerun.

## Pre-Implementation Adversarial Review

### Round 1 - Boundary, State Ownership, And UI Closure

Findings:

1. `BudgetAlertCard` needed explicit `message` and `error` props, otherwise the component might reimplement page-level API error normalization or hide save failures.
2. The story did not define `budget=null` / `not_configured` behavior, inviting a blank or disabled first-use budget UI.
3. Percent display boundaries were under-specified; `NaN`, `Infinity`, and over-100% values could leak into the UI or resize controls.
4. Type compatibility between `packages/ui` prop models and `apps/web/src/lib/api.ts` response types was implicit, leaving room for `any` adapters in the page.
5. The story did not clearly preserve the existing usage trend section, so implementation could accidentally duplicate trend state inside `InvoiceCard` or remove `SparklineKPI`.

Revision after Round 1:

- Added controlled `message`/`error` props, `budget=null` empty-state rules, percent formatting boundaries, structural type-compatibility requirements, and explicit trend-section preservation.

### Round 2 - Drift, Dependency Direction, And Test Executability

Findings:

1. The suggested web commands used `pnpm --filter web`, but the actual workspace package is `@opticloud/web`; that command would fail.
2. Storybook/Chromatic requirements could be misread as CI/provider setup work instead of static story additions.
3. The package-local type requirement still allowed accidental imports from `apps/web/src/lib/api.ts`, `@/lib/api`, or Next.js inside `packages/ui`.
4. Sensitive-data omission tests needed concrete fixtures, otherwise a test could pass without proving raw `details` and event identifiers are hidden/truncated safely.
5. AC/task numbering needed to keep the added dependency-direction and storybook boundaries traceable.

Revision after Round 2:

- Fixed web package commands, constrained Storybook/Chromatic scope, forbade reverse imports into `packages/ui`, and required sensitive fixture coverage for raw metadata and long labels.

### Round 3 - Closure, State Isolation, And Test Boundaries

Findings:

1. The story did not state whether invoice loading/empty/error states move into `InvoiceCard`; that ambiguity could break existing page-level invoice error handling.
2. Budget loading/message/error display needed a different boundary because budget state is already independently loaded and should remain visible even when invoices fail.
3. The page tests already cover budget failure with invoice/trend visibility, but not the inverse: invoice failure should not hide the budget card.
4. Adding Playwright solely for this extraction would create brittle authenticated setup unless a behavior cannot be proven by package/page tests.
5. The closure criteria needed an explicit regression for duplicate or merged state after component extraction.

Revision after Round 3:

- Locked invoice empty/loading/error as page-owned, budget status messages as component-rendered props, added inverse state-isolation regression coverage, and bounded E2E scope to avoid unnecessary brittle setup.
