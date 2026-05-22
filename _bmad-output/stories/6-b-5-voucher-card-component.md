# Story 6.B.5: VoucherCard Tier 3 Component

Status: done

## Story

As a user managing reproducible optimization evidence,
I want a clear VoucherCard on a Repro Dashboard with one-click rerun,
so that I can recognize durable vouchers, understand their 5-year reuse promise, and rerun them without copying API calls manually.

## Acceptance Criteria

1. `packages/ui` exports a reusable Tier 3 `VoucherCard` component.
   - Add `packages/ui/src/components/VoucherCard/index.tsx`.
   - Export `VoucherCard` and its props/types from `packages/ui/src/index.ts`.
   - Add Storybook stories under `packages/ui/src/components/VoucherCard/index.stories.tsx`.
   - Keep the component presentation-only: it receives voucher data and callbacks from parents; it must not import `apps/web` code, call HTTP APIs, read API keys, or own routing.
   - Use the existing component-library style: React client component, Tailwind token classes, `cn`, `useA11y` where useful, `data-testid` hooks, and no new design dependency.

2. The card renders the voucher contract clearly and without PII.
   - Show `voucher_id`, `created_at`, `status`, locked solver/model version, request fingerprint short form, seed lock status, optional `anonymous: true`, and rerun lineage when provided.
   - Non-anonymous cards must not render `anonymous: false` or `anonymous: null`.
   - The card must not accept or render owner profile fields such as email, phone, legal name, account ID, API key, or raw input payload.
   - Use mode/status differentiation with text plus icon/shape, not color alone.
   - Voucher ID must be copyable through a callback or clipboard-aware button that remains accessible.

3. The card supports one-click rerun without hiding backend state.
   - Provide a primary rerun action when `canRerun` is true.
   - Disable the rerun action when `canRerun` is false, when the card is already rerunning, or when status is not rerunnable.
   - Show rerun progress and error states from parent props.
   - Do not invent a new endpoint. The app integration must use the existing `rerunReproductionVoucher(apiKey, voucherId, idempotencyKey?)` client.
   - Successful rerun display must surface the child `reproducibility.voucher_id`, `rerun_of_voucher_id`, and `source_optimization_id`.

4. A user-facing Repro Dashboard exists in `apps/web`.
   - Add a route under the existing console area, recommended path `apps/web/src/app/console/repro/page.tsx`.
   - The page demonstrates VoucherCard against typed fixture data and wires the rerun action through the existing web API client.
   - The page must avoid promising a full voucher search/list API because no voucher listing endpoint exists yet.
   - It can use local fixture/demo state for issued vouchers and use a user-entered API key for rerun, matching current console/demo patterns.
   - Add a lightweight navigation entry only if a local console navigation pattern exists; otherwise keep the page directly routable.

5. Accessibility and interaction behavior are covered.
   - Card heading/region semantics identify the voucher.
   - Buttons have stable accessible names.
   - Copy and rerun actions are keyboard reachable.
   - Rerun status changes use polite live-region semantics.
   - Add `jest-axe` coverage for the component's default, anonymous, rerunning, and disabled/expired states.

6. Tests and type checks prove the contract.
   - Add `packages/ui` unit tests for render shape, no false/null anonymous leakage, copy callback, rerun callback, disabled states, lineage display, and error/progress display.
   - Add component a11y tests in `packages/ui`.
   - Add web-level tests for Repro Dashboard behavior if existing Vitest setup can cover the route/component without excessive mocking; otherwise document why coverage remains component-level.
   - Run `pnpm --filter @opticloud/ui test`, `pnpm --filter @opticloud/ui typecheck`, `pnpm --filter @opticloud/web typecheck`, and `git diff --check`.

7. Scope stays inside the UI/dashboard layer.
   - Do not add a backend voucher listing endpoint.
   - Do not change voucher issuance, rerun semantics, idempotency hashing, voucher ID format, anonymity persistence, or 5-year expiry logic.
   - Do not add database columns or migrations.
   - Do not expose raw solver payloads in the UI.

## Tasks / Subtasks

- [x] Build the `VoucherCard` package component. (AC: 1, 2, 3, 5)
  - [x] Define a narrow `VoucherCardVoucher` / `VoucherCardProps` type that mirrors the public UI contract, not the database row.
  - [x] Render voucher metadata with stable labels and compact responsive layout.
  - [x] Add copy, rerun, rerunning, error, disabled, anonymous, and lineage states.
  - [x] Keep callback ownership in the parent: `onCopyVoucherId`, `onRerun`, optional `onViewDetails`.
- [x] Add Storybook and exports. (AC: 1)
  - [x] Add default, anonymous blind-review, child rerun, rerunning, expired/disabled, and error stories.
  - [x] Export `VoucherCard` and types from `packages/ui/src/index.ts`.
- [x] Add component tests. (AC: 2, 3, 5, 6)
  - [x] Test visible voucher ID, status/mode labels, model/solver metadata, fingerprint short form, seed lock, and no owner fields.
  - [x] Test anonymous rendering only when true.
  - [x] Test copy/rerun callbacks and disabled behavior.
  - [x] Test successful child rerun summary and error/progress states.
  - [x] Add axe tests for key visual states.
- [x] Add Repro Dashboard page. (AC: 3, 4)
  - [x] Create `apps/web/src/app/console/repro/page.tsx`.
  - [x] Use typed fixture voucher data derived from `Reproducibility` / `ReproductionRerunResponse` shapes in `apps/web/src/lib/api.ts`.
  - [x] Wire rerun to `rerunReproductionVoucher()` using a user-provided API key and selected voucher ID.
  - [x] Display child rerun voucher metadata after success without altering backend behavior.
- [x] Validate and update story status after implementation. (AC: 6, 7)
  - [x] Run package UI tests and a11y tests.
  - [x] Run UI/web typechecks.
  - [x] Run `git diff --check`.
  - [x] Update sprint status and story Dev Agent Record after implementation.

## Dev Notes

### Context

- Story 6.B.1 added the optional `reproducibility` response object for opt-in runs.
- Story 6.B.2 added durable authenticated voucher IDs in the form `repro-{YYYY}-{6 Crockford base32}`.
- Story 6.B.3 added `POST /v1/reproduce/{voucher_id}/rerun` and `ReproductionRerunResponse`.
- Story 6.B.4 added optional `reproducibility.anonymous: true` and durable anonymous inheritance across child vouchers.
- Story 6.B.5 is the first user-facing UI layer for this voucher chain. It should consume the existing contract rather than creating a new backend capability.

### Source Anchors

- Epic requirement: `_bmad-output/planning/epics.md`, Story `6.B.5: VoucherCard Tier 3 Component`.
- UX component requirement: `_bmad-output/planning/ux-design-specification.md`, Layer 4 / Tier 3 `VoucherCard`.
- API client shapes: `apps/web/src/lib/api.ts`, `Reproducibility`, `OptimizationResponse`, `ReproductionRerunResponse`, and `rerunReproductionVoucher()`.
- Previous voucher behavior: `_bmad-output/stories/6-b-1-mark-reproducible.md` through `_bmad-output/stories/6-b-4-anonymous-voucher.md`.
- UI component patterns: `packages/ui/src/components/ChargeModal`, `StatusCard`, `ConfidenceLabel`, `SparklineKPI`, and `Tier1.a11y.test.tsx`.
- Console page patterns: `apps/web/src/app/console/excel/page.tsx` and `apps/web/src/app/console/academic-attribution/page.tsx`.

### Data Contract Guidance

Recommended component data type:

```ts
export type VoucherStatus = "issued" | "expired" | "revoked" | "rerun_child";

export interface VoucherCardVoucher {
  voucherId: string;
  status: VoucherStatus;
  createdAt: string;
  expiresAt?: string;
  lockedSolver: string;
  lockedModelVersion: {
    provider_id: string;
    name: string;
    version: string;
  };
  requestFingerprint: string;
  seedLocked: boolean;
  seed: number | null;
  anonymous?: true;
  rerunOfVoucherId?: string;
  sourceOptimizationId?: string;
  childVoucherId?: string;
}
```

Notes:
- This type is intentionally UI-facing. Do not pass raw database rows or raw optimization payloads into the component.
- `anonymous` must remain optional-true only; do not model it as generic boolean unless the render path explicitly omits false.
- If a real expiry date is not available yet, compute or label the 5-year SLA carefully as "based on voucher creation date" without hard-coding legal finality beyond Story 6.B.6.

### UX / Visual Guardrails

- This is an operational console component, not a marketing hero. Keep it dense, scannable, and quiet.
- Use cards only for the voucher item itself; do not nest the card in another decorative card.
- Use icons from `lucide-react` where helpful for copy, rerun, lock, shield/anonymous, and status.
- Keep border radius at the existing component-library scale (`rounded-md` / `rounded-lg` if already used locally).
- Avoid one-hue decoration. Status must be readable by text and icon even without color.
- Long voucher IDs and fingerprints must not overflow on mobile; use monospace, wrapping/truncation, and copy affordances.

### API / Rerun Integration Guardrails

- The only backend action in scope is the existing rerun client:
  `rerunReproductionVoucher(apiKey, voucherId, idempotencyKey?)`.
- The dashboard cannot list real vouchers yet because there is no list endpoint. Use fixture/demo cards or data returned from a just-completed optimization flow if integrated locally.
- Do not store API keys in localStorage. Keep user-entered key in component state for the current page session.
- Parent owns idempotency key generation through the existing API client default unless the page has a clear reason to pass one.
- Backend may return RFC 7807 errors; the page should show a concise error string without dumping raw payloads.

### Testing / Validation Notes

- Use `@testing-library/react`, `vitest`, and `jest-axe`, following existing `packages/ui` tests.
- Suggested commands:
  - `pnpm --filter @opticloud/ui test`
  - `pnpm --filter @opticloud/ui typecheck`
  - `pnpm --filter @opticloud/web typecheck`
  - `git diff --check`
- If adding a web route test is too expensive under current Next/Vitest setup, record the reason in Dev Agent Record and keep coverage in `packages/ui` plus web typecheck.

### Risks / Decisions

- Risk: inventing a voucher listing API. Avoid it; this story is a component and dashboard surface only.
- Risk: leaking `anonymous: false` or owner identity. Keep anonymous optional-true and exclude owner fields from props.
- Risk: making the package component depend on app-level API/client code. Keep `packages/ui` presentation-only.
- Risk: over-promising 5-year archival detail before Story 6.B.6. Phrase SLA display as creation-date-based and implementation roadmap aware.
- Risk: rerun button appearing enabled for expired/revoked cards. Gate with `canRerun` and status.

## Story Review Log

### Round 1: Requirements Completeness Review

Findings fixed:
- Added an explicit `packages/ui` export requirement so the story cannot be satisfied by an app-local card only.
- Added Repro Dashboard acceptance criteria while clarifying that no voucher listing endpoint exists yet.
- Added one-click rerun behavior, including disabled/progress/error states and child voucher display.
- Added no-PII and optional-true anonymous rendering requirements.

Status: PASS after fixes.

### Round 2: Architecture / Testability Review

Findings fixed:
- Made `VoucherCard` presentation-only and moved HTTP ownership to the parent page.
- Bound rerun integration to the existing `rerunReproductionVoucher()` client.
- Added a narrow UI-facing prop type to prevent raw DB rows or solver payloads from reaching the card.
- Added package-level unit and a11y test requirements.

Status: PASS after fixes.

### Round 3: Acceptance / Scope Audit

Findings fixed:
- Explicitly excluded backend endpoints, migrations, voucher issuance changes, and expiry logic changes.
- Added Storybook state coverage for default, anonymous, child rerun, rerunning, disabled, and error modes.
- Added accessibility live-region and keyboard requirements.
- Clarified 5-year SLA wording must not overtake Story 6.B.6.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

1. Add a presentation-only `VoucherCard` component with copy/rerun/lineage states and Storybook stories.
2. Export the new UI types from `packages/ui/src/index.ts` and cover the card with unit/a11y tests.
3. Add a `/console/repro` dashboard that uses fixture vouchers, a session-only API key, and the existing rerun client.
4. Validate `packages/ui` and `apps/web`, then update the story and sprint status for code review.

### Debug Log References

- 2026-05-22 — Created story from Epic 6.B.5, UX Tier 3 component requirement, existing `packages/ui` component patterns, and 6.B.1-6.B.4 voucher contracts.

### Completion Notes List

- Implemented a reusable Tier 3 `VoucherCard` with public UI-facing contract types, status/lineage display, accessible copy and rerun actions, and Storybook coverage.
- Added unit tests and axe coverage for default, anonymous, rerunning, disabled, and lineage/error states.
- Added `/console/repro` as a fixture-driven dashboard wired to `rerunReproductionVoucher()` with session-only API key handling.
- Added a lightweight web smoke test for the dashboard rerun flow.
- Validation completed: `pnpm --filter @opticloud/ui test`, `pnpm --filter @opticloud/ui typecheck`, `pnpm --filter @opticloud/web typecheck`, and `git diff --check` all passed.

### File List

Created:
- `_bmad-output/stories/6-b-5-voucher-card-component.md`
- `apps/web/src/app/console/repro/page.tsx`
- `apps/web/src/app/console/repro/page.test.tsx`
- `packages/ui/src/components/VoucherCard/index.tsx`
- `packages/ui/src/components/VoucherCard/index.test.tsx`
- `packages/ui/src/components/VoucherCard/index.a11y.test.tsx`
- `packages/ui/src/components/VoucherCard/index.stories.tsx`

Modified:
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/vitest.config.ts`
- `packages/ui/src/index.ts`
- `packages/ui/src/test-setup.ts`
- `packages/ui/src/components/SparklineKPI/index.tsx`
- `packages/ui/src/components/Tier1.a11y.test.tsx`
- `packages/ui/src/hooks/useA11y.test.tsx`

### Change Log

- 2026-05-22 — Created Story 6.B.5 and completed 3 story-review rounds before implementation.
- 2026-05-22 — Implemented VoucherCard, Storybook exports, component tests, and the Repro Dashboard page.
- 2026-05-22 — Added dashboard smoke test, fixed shared a11y test setup, and validated UI/web typechecks plus `git diff --check`.
- 2026-05-22 — Addressed post-implementation code review findings and finalized the story as done.

### Post-Implementation Code Review

Status: pass

Findings addressed:
- [x] Rerun success mapping now surfaces the actual child voucher ID and keeps source optimization lineage separate.
- [x] Rerun eligibility is limited to issued vouchers only.
- [x] Copy action now falls back to clipboard or disables itself when neither callback nor clipboard support exists.
- [x] Added a web-level smoke test for the Repro Dashboard rerun flow.
- [x] Updated this story record and sprint status to reflect implementation completion.
