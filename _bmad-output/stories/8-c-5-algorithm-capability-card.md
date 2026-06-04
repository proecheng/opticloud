---
story_key: 8-c-5-algorithm-capability-card
epic_num: 8
story_num: C.5
epic_name: Teaching + Provider Routing + Legal + Algorithm Library
status: in-progress
baseline_commit: 0e2137c8285daec224074ef7c603f3be16ee8cfb
priority: High
type: UX-DR1 CapabilityCard component for benchmark library
created_by: bmad-create-story
created_at: 2026-06-04
sources:
  - _bmad-output/planning/epics.md (Epic 8.C / Story 8.C.5 / UX-DR1 CapabilityCard)
  - _bmad-output/planning/prd.md (FR O11 / J4 academic user path)
  - _bmad-output/planning/architecture.md (O11 service mapping / packages/ui single-source discipline)
  - _bmad-output/stories/2-2-algorithm-details.md
  - _bmad-output/stories/2-3-tier-based-browse.md
  - _bmad-output/stories/8-c-4-algorithm-library-browse.md
  - apps/web/src/lib/api.ts
  - apps/web/src/lib/api-benchmark-library.test.ts
  - apps/web/src/app/algorithms/page.tsx
  - apps/web/src/app/algorithms/benchmarks/page.tsx
  - apps/web/src/app/algorithms/benchmarks/page.test.tsx
  - packages/ui/src/index.ts
  - packages/ui/src/components/VoucherCard/index.tsx
  - packages/ui/src/components/InvoiceCard/index.tsx
---

# Story 8.C.5 - CapabilityCard for 算例库

Status: in-progress

## Story

**作为** 学术用户、教学用户或算法评估用户，
**我希望** 经典算例库列表使用 `packages/ui` 中可复用、可访问的 `CapabilityCard`，
**从而** 在浏览、筛选和一键 import benchmark 模板时获得一致的能力呈现，并让后续算法目录能力卡也能复用同一个 UI 单源。

## Context

Story 8.C.4 已交付 O11 经典算例库最小闭环：公开 `GET /v1/benchmark-library`、无副作用 import payload、优化任务 benchmark-library 50% billing discount，以及 `/algorithms/benchmarks` 公开页面。8.C.4 明确不实现 `CapabilityCard`、不修改 `packages/ui`；8.C.5 正是这个 UI-system closure story。

规划源 `_bmad-output/planning/epics.md` 对 8.C.5 的原始 AC 是：Given `packages/ui CapabilityCard` / When 算例库列表 / Then 显示 + filter + a11y。早期 Story 2.2 / 2.3 也把 full capability card/schema rendering 留给 8.C.5，但本 story 的直接闭环是经典算例库列表，不是重做算法详情页或后端 capability registry。

当前 `/algorithms/benchmarks` 已有 inline `<li>` 卡片、suite/domain/task filters、loading/error/empty states 和 import payload aside。`apps/web/src/lib/api.ts` 已有 `BenchmarkLibraryItem` 与 `BenchmarkImportResponse` 类型，字段为 backend snake_case。`packages/ui` 已有 Tier 2/3 组件模式：组件目录 `index.tsx`、`index.test.tsx`、`index.a11y.test.tsx`、`index.stories.tsx`，从 `src/index.ts` 单源导出，组件 presentation-only，父页面拥有 API、router 和 storage。

## Scope

1. Add `CapabilityCard` under `packages/ui/src/components/CapabilityCard/`.
   - Component is presentation-only and data-driven.
   - Component renders benchmark capability metadata already present on `BenchmarkLibraryItem`.
   - Component prop model uses backend snake_case field names so `apps/web/src/lib/api.ts` `BenchmarkLibraryItem` can be passed directly without lossy adapters or `any` casts.
   - Component may accept `sample_payload` for structural compatibility, but must never render it in the card body.
   - Component exposes callback props for user actions such as import and source link handling remains native anchor.
2. Export `CapabilityCard` and public prop/model types from `packages/ui/src/index.ts`.
3. Add Storybook, focused unit tests, and axe a11y tests for `CapabilityCard`.
4. Add the new a11y test file to `packages/ui/package.json` `test:a11y` without dropping any existing a11y test files.
5. Replace the inline benchmark `<li>` card body on `/algorithms/benchmarks` with `CapabilityCard`.
6. Preserve existing page-owned behavior from 8.C.4:
   - `listBenchmarkLibrary()` filtering.
   - `importBenchmarkLibraryItem()` one-click import.
   - Loading/error/empty states.
   - Import payload aside.
   - No auto-submit to optimization/prediction endpoints.
   - No localStorage/sessionStorage writes.
   - Prediction entries visibly distinguish template availability from actual billing support.
7. Do not change backend APIs, billing semantics, benchmark catalog data, or capability-registry runtime semantics.
8. Run post-implementation code review, fix findings, pass gates, and sync GitHub.

## Out Of Scope

- Backend endpoint/schema changes, solver-orchestrator benchmark catalog changes, billing discount changes, SQL migrations, workers, queues, or external dataset handling.
- New capability-registry runtime endpoint or Provider shadow/evaluation `benchmark_suite` semantic changes.
- Full algorithm details/schema rendering on `/algorithms/[k_algo]`; this story may define component props that could support future algorithm cards, but only `/algorithms/benchmarks` is integrated.
- New route, marketing page, broad `/algorithms` redesign, leaderboard/results/baseline/SOTA display, dataset mirror/download, or clipboard/download dependency.
- Storing benchmark payloads, credentials, imports, filters, or user data in browser storage.
- New npm runtime dependency, charting library, CSS framework, or Storybook/Chromatic workflow changes.

## Acceptance Criteria

1. `packages/ui` adds `CapabilityCard` under `src/components/CapabilityCard/`.
2. `CapabilityCard` and its public prop/model types are exported from `packages/ui/src/index.ts`.
3. `CapabilityCard` is presentation-only: no `fetch`, no `next/*`, no router access, no browser storage access, no direct imports from `apps/web`, solver-orchestrator, billing-service, auth-service, or capability-registry.
4. `CapabilityCard` prop model mirrors the benchmark item contract with backend snake_case field names and remains structurally assignable from `apps/web/src/lib/api.ts` `BenchmarkLibraryItem` without mapping functions or `as any`.
5. `CapabilityCard` renders benchmark capability metadata: suite, task type, domain, Chinese title, English title, benchmark id, dataset ref, target endpoint, source name/link, license note, and discount metadata.
6. `CapabilityCard` renders `discount.kind`, `discount.label_zh`, and multiplier as display/eligibility metadata, not as invoice proof.
7. `CapabilityCard` visibly distinguishes `discount.billing_supported=false` prediction entries from optimization entries without implying prediction billing discount is implemented.
8. `CapabilityCard` accepts `onImport(benchmarkId)` and per-card `isImporting` props; clicking the import action calls the callback with the card `benchmark_id`.
9. `CapabilityCard` disables the import action only for the card whose own `isImporting=true` and preserves an accessible loading label while importing.
10. `CapabilityCard` renders source links as safe external anchors with `target="_blank"` and `rel="noopener noreferrer"` only for `http:` or `https:` URLs.
11. If `source_url` is empty, malformed, or non-http(s), `CapabilityCard` renders the source name as text and does not create an unsafe link.
12. Long benchmark ids, dataset refs, titles, source names, target endpoints, and license notes wrap without horizontal overflow on mobile and desktop.
13. Status/discount semantics use icon plus text or explicit text, not color alone.
14. Buttons and links have accessible names, visible focus styles, and touch-friendly dimensions.
15. The component uses `useA11y` with stable region semantics and supports an optional `ariaLabel`.
16. The component uses a stable React-generated heading id, not raw `benchmark_id`, for `aria-labelledby`, so ids remain valid even if benchmark ids contain slashes, spaces, punctuation, or duplicates in tests.
17. The card avoids nested card-inside-card composition. Internal metadata may use plain `dl`, dividers, badges, or lists, but not stacked decorative card containers.
18. `CapabilityCard` uses existing design tokens, `cn`, and `lucide-react`; no new runtime dependency is added.
19. Storybook stories exist for optimization billing-supported, prediction billing-not-supported, importing, unsafe/missing source URL, and long-content states.
20. Unit tests cover metadata rendering, import callback wiring, per-card disabled importing state, prediction billing distinction, source link safety including unsafe URL fallback, valid heading/region semantics, direct `BenchmarkLibraryItem` structural compatibility, and long/sensitive text boundaries.
21. Unit tests assert raw `sample_payload` JSON or import request payload is not rendered by the card body.
22. Dedicated axe tests cover default optimization, prediction billing-not-supported, importing, and long-content states with zero violations.
23. `packages/ui` `test:a11y` includes `CapabilityCard/index.a11y.test.tsx` and retains every existing a11y test path.
24. `/algorithms/benchmarks` imports and uses `CapabilityCard` from `@opticloud/ui` for each benchmark list item.
25. The page keeps the benchmark results as a semantic list (`ul` with `li` per item) after replacing the inline card body.
26. The page passes API `BenchmarkLibraryItem` objects to `CapabilityCard` directly and does not add adapter functions, duplicate benchmark item state, or `any` casts.
27. The page passes `isImporting={importingId === item.benchmark_id}` so only the active card is disabled while import is pending.
28. The page keeps suite/domain/task filters page-owned and continues calling `listBenchmarkLibrary()` with the same query semantics as 8.C.4.
29. The page keeps one-click import page-owned and continues calling `importBenchmarkLibraryItem(benchmark_id)` with no automatic optimization/prediction submission.
30. The page keeps import payload display in the aside and does not move JSON rendering into `CapabilityCard`.
31. The page keeps loading, error, empty, import-error, and prior successful import payload states unchanged in behavior.
32. The page still renders all six suites: `ieee`, `cvrplib`, `or-lib`, `m5`, `uci`, and `nab`.
33. The page still shows filters and card list accessibly after component extraction.
34. Existing benchmark page tests are updated to prove rendering, filters, import payload display, import-error display, no auto-submit, no storage writes, semantic list rendering, and per-card importing disable behavior still pass through the component-backed UI.
35. Existing web API client tests remain unchanged in contract and pass.
36. No files under `apps/solver-orchestrator/**`, `apps/capability-registry/**`, billing-service, auth-service, or database migrations are modified.
37. Local gates pass: focused `packages/ui` tests, focused `packages/ui` a11y tests, `packages/ui` typecheck, focused web benchmark page tests, web API benchmark tests, web typecheck, and `git diff --check`.
38. Post-implementation code review is completed and findings are fixed or explicitly documented.
39. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done` through a separate status-sync commit.

## Tasks / Subtasks

- [x] T1: Add `CapabilityCard` UI package component (AC: 1-18)
  - [x] Define package-local benchmark capability model types that mirror `apps/web/src/lib/api.ts` without importing app code.
  - [x] Render safe suite/task/domain/status metadata, titles, ids, source/dataset/target details, license note, and discount distinction.
  - [x] Wire optional import callback and per-card importing state without owning API calls.
  - [x] Render only http(s) source URLs as links; fall back to text for unsafe/malformed URLs.
  - [x] Use React-generated ids for heading/region wiring instead of deriving DOM ids from benchmark ids.
  - [x] Accept direct benchmark items, including `sample_payload`, while omitting raw payload rendering.
  - [x] Guard long values and missing optional values against overflow or blank labels.

- [x] T2: Add exports, Storybook, unit tests, and a11y tests (AC: 19-23)
  - [x] Export component and prop/model types from `packages/ui/src/index.ts`.
  - [x] Add stories for optimization, prediction, importing, unsafe/missing source URL, and long-content states.
  - [x] Add unit tests for rendering, callbacks, disabled state, source link safety, billing distinction, and payload omission.
  - [x] Add axe tests and include them in `packages/ui` `test:a11y`.

- [x] T3: Integrate `CapabilityCard` into `/algorithms/benchmarks` (AC: 24-36)
  - [x] Replace inline benchmark card markup with `CapabilityCard`.
  - [x] Preserve `ul`/`li` list semantics around cards.
  - [x] Keep filters, import aside, import error state, API calls, no-submit, and storage hygiene page-owned.
  - [x] Update focused page tests for the component-backed card list.

- [ ] T4: Review, gates, and GitHub sync (AC: 37-39)
  - [x] Run local quality gates and fix failures.
  - [x] Run post-implementation code review and fix/document findings.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [ ] Mark story and sprint status `done` only after merge/sync through a separate status-sync commit.

## Dev Notes

### Component Boundaries

- `packages/ui` is the cross-service UI source of truth. `CapabilityCard` must be app-agnostic and parent-driven.
- Do not import `BenchmarkLibraryItem` from `apps/web`; define structurally compatible package-local types.
- Prefer a `capability` prop whose type uses the same snake_case field names as the API item, so the web page can pass `item` directly without drift-prone adapters.
- The card should display capability metadata only. JSON import payload rendering stays in `/algorithms/benchmarks` aside so the card remains reusable.
- `sample_payload` is present on `BenchmarkLibraryItem` but must not be dumped in the card body; it can contain implementation details and belongs in import payload flow after the user action.
- Action callbacks should receive `benchmark_id`; parent pages own API calls and state.
- Treat `isImporting` as a per-card prop. The benchmark page already owns `importingId`; pass equality, not a global `importingId !== null`.
- Validate `source_url` with `new URL(...)` and render an anchor only for `http:` / `https:` schemes.
- Use `useId()` or equivalent React-generated id for the card title and `aria-labelledby`; do not use `benchmark_id` as a DOM id.

### Frontend Patterns To Reuse

- Follow `VoucherCard`, `InvoiceCard`, and `BudgetAlertCard` conventions: `"use client"`, `useA11y`, `cn`, lucide icons, `rounded-md`, compact operational layout, no nested cards.
- Use existing page filter controls and import aside; do not create a new page-level design.
- Keep text wrapping robust with `min-w-0`, `break-words`, `break-all` for ids/refs, and responsive grid constraints.
- Prefer semantic `article`, `dl`, headings, buttons, and anchors over generic clickable divs.

### Existing Contracts To Preserve

- `apps/web/src/lib/api.ts` benchmark types use backend snake_case and helper names from 8.C.4.
- `/algorithms/benchmarks` is a static App Router route beside `/algorithms`; do not move it under `[k_algo]`.
- `discount.billing_supported=false` means browse/import template exists but actual prediction billing discount is not implemented.
- `Discount` on the card is display metadata only; actual billing discount remains backend finalize metadata when a user submits an optimization import.
- `apps/web/src/app/algorithms/benchmarks/page.test.tsx` already guards no auto-submit and no storage writes; preserve or strengthen those tests.

### Suggested Commands

```powershell
pnpm --filter @opticloud/ui test -- src/components/CapabilityCard/index.test.tsx
pnpm --filter @opticloud/ui test -- src/components/CapabilityCard/index.a11y.test.tsx
pnpm --filter @opticloud/ui test:a11y
pnpm --filter @opticloud/ui typecheck
pnpm --filter @opticloud/web test -- src/app/algorithms/benchmarks/page.test.tsx src/lib/api-benchmark-library.test.ts
pnpm --filter @opticloud/web typecheck
git diff --check
```

## Definition Of Done

- Story file has passed exactly 3 pre-implementation adversarial review rounds and revisions.
- `CapabilityCard` exists in `packages/ui`, is exported, and has Storybook/unit/a11y coverage.
- `/algorithms/benchmarks` uses `CapabilityCard` while preserving 8.C.4 filter/import/no-submit/storage behavior.
- No backend/API/billing/capability-registry drift is introduced.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, local `main` sync, and separate status-sync closure.

## Story Review Log

### Round 1: Boundary, Ownership, And UI Contract Review

Findings fixed:

- Initial story did not require `CapabilityCard` prop types to remain structurally assignable from `apps/web` `BenchmarkLibraryItem`, which could have produced page-level adapter functions and backend/UI field drift. Revised scope, ACs, tasks, and Dev Notes to require backend snake_case compatibility and direct item passing without `any` casts.
- Initial story said `sample_payload` should not render but did not clarify whether the UI prop may receive it for structural compatibility. Revised the story so the component may accept `sample_payload` but must never render raw sample or import payload JSON.

Status: PASS after fixes.

### Round 2: Data Consistency, Drift, And Dependency Review

Findings fixed:

- Initial story allowed `source_url` to become an external anchor whenever present. Revised ACs and Dev Notes so only `http:`/`https:` URLs are linked; malformed or unsafe URLs render as plain text.
- Initial story used `isImporting` but did not explicitly define it as per-card state, leaving room for one pending import to disable every card. Revised ACs and page integration requirements to pass `isImporting={importingId === item.benchmark_id}` and test this behavior.
- Initial story said to include the new a11y test in `test:a11y` but did not protect existing a11y coverage from being replaced. Revised scope and ACs to require appending while retaining every existing a11y test path.

Status: PASS after fixes.

### Round 3: Closure, Accessibility, And List Semantics Review

Findings fixed:

- Initial story allowed implementation to derive DOM ids from `benchmark_id`; benchmark ids can contain punctuation in tests and future catalog data. Revised ACs and Dev Notes to require React-generated heading ids for `aria-labelledby`.
- Initial story did not explicitly preserve `ul`/`li` semantics when replacing inline cards. Revised page ACs/tasks so the benchmark results remain a semantic list after component extraction.
- Initial story covered import payload display but not import-error and prior payload behavior. Revised page ACs/tests to preserve import-error display and prior successful import payload state.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-c-5-algorithm-capability-card`.
- Baseline commit: `0e2137c8285daec224074ef7c603f3be16ee8cfb`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base skill instructions and project config.
- Story creation analyzed Epic 8.C.5 source AC, PRD O11/J4, architecture O11/packages-ui mapping, prior Story 8.C.4 benchmark library browse boundaries, Story 2.2/2.3 deferred CapabilityCard references, current web benchmark page/tests, and existing `packages/ui` Tier 2 component patterns.
- 2026-06-04 - Completed pre-implementation adversarial review round 1 and revised prop-model compatibility, no-adapter, and `sample_payload` non-rendering boundaries.
- 2026-06-04 - Completed pre-implementation adversarial review round 2 and revised source URL safety, per-card importing state, and a11y gate preservation requirements.
- 2026-06-04 - Completed pre-implementation adversarial review round 3 and revised generated heading ids, list semantics, and import-error closure requirements.
- 2026-06-04 - Implemented `packages/ui` `CapabilityCard`, public exports, Storybook stories, unit tests, and axe coverage.
- 2026-06-04 - Integrated `CapabilityCard` into `/algorithms/benchmarks` while preserving page-owned filters, import payload aside, import errors, no-submit, and storage hygiene.
- 2026-06-04 - Local gates passed: `pnpm --filter @opticloud/ui test -- src/components/CapabilityCard/index.test.tsx`, `pnpm --filter @opticloud/ui test -- src/components/CapabilityCard/index.a11y.test.tsx`, `pnpm --filter @opticloud/ui test:a11y`, `pnpm --filter @opticloud/ui typecheck`, `pnpm --filter @opticloud/web test -- src/app/algorithms/benchmarks/page.test.tsx src/lib/api-benchmark-library.test.ts`, `pnpm --filter @opticloud/web typecheck`, and `git diff --check`.
- 2026-06-04 - Post-implementation code review found missing explicit missing/malformed `source_url` evidence; added unit/story coverage and reran gates successfully.

### Completion Notes List

- Initial story created.
- Round 1 pre-implementation review completed and story revised.
- Round 2 pre-implementation review completed and story revised.
- Round 3 pre-implementation review completed and story revised.
- Story is ready for implementation.
- Story moved to in-progress after exactly three pre-implementation review rounds.
- Added presentation-only `CapabilityCard` with backend snake_case prop model, safe source-link handling, per-card import callback/loading state, payload omission, Storybook, unit tests, and axe coverage.
- Replaced `/algorithms/benchmarks` inline benchmark card body with `CapabilityCard` while preserving semantic list structure, filters, import aside, import errors, no auto-submit, and storage hygiene.
- Post-implementation code review completed; source URL missing/malformed coverage gap was fixed.

### File List

- `_bmad-output/stories/8-c-5-algorithm-capability-card.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/src/app/algorithms/benchmarks/page.tsx`
- `apps/web/src/app/algorithms/benchmarks/page.test.tsx`
- `packages/ui/package.json`
- `packages/ui/src/index.ts`
- `packages/ui/src/components/CapabilityCard/index.tsx`
- `packages/ui/src/components/CapabilityCard/index.test.tsx`
- `packages/ui/src/components/CapabilityCard/index.a11y.test.tsx`
- `packages/ui/src/components/CapabilityCard/index.stories.tsx`

## Change Log

- 2026-06-04 - Initial story created for `CapabilityCard` UI package component and benchmark-library page integration.
- 2026-06-04 - Round 1 pre-implementation review revised package/web type compatibility and raw payload rendering boundaries.
- 2026-06-04 - Round 2 pre-implementation review revised source URL safety, per-card importing state, and a11y gate preservation.
- 2026-06-04 - Round 3 pre-implementation review revised generated heading ids, list semantics, and import-error closure.
- 2026-06-04 - Story status moved to in-progress after exactly three pre-implementation review rounds.
- 2026-06-04 - Implemented `CapabilityCard`, UI package tests/a11y/stories, benchmark page integration, focused page tests, local gates, and post-review source URL coverage fix.

## Post-Implementation Code Review

### Findings

- [x] [Review][Patch] `CapabilityCard` covered unsafe `source_url` fallback but did not explicitly cover missing and malformed source URLs despite the story requiring unsafe/missing source URL story/test evidence. Fixed by expanding the unit test to cover `null`, `javascript:...`, malformed strings, and a valid https URL, plus adding a `MissingSourceUrl` Storybook story.

### Outcome

Changes requested internally; all findings fixed and focused gates rerun.
