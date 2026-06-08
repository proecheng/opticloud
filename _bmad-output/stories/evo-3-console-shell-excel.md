# Story EVO.3: Console Shell and Excel Workflow IA

Status: done
Date: 2026-06-08
Branch: `codex/ux-console-shell-excel`

## Story

As an operations user using the Console Excel workflow,
I want the console to have a coherent workbench shell and a clearer Excel task flow,
so that I can understand where I am, move to adjacent console tools, upload a workbook, confirm the detected task type, preview the mapped request, run the demo path, and download results without the page feeling like a disconnected public landing page.

## Scope

- Add a reusable `ConsoleShell` for console workbench pages.
- Add a compact `ConsolePageHeader` for console title, description, status metadata, and actions.
- Apply the shell to `/console/excel`.
- Restructure `/console/excel` into a task workflow layout with:
  - persistent console navigation,
  - compact page header,
  - workflow stage rail,
  - primary upload/result work area,
  - bounded context panels for privacy, limits, and outputs.
- Preserve the current Excel state machine, browser-local parsing, task detection, confirmation modal, task preview cards, demo submit behavior, result downloads, and all E2E selectors.
- Add focused regression coverage for the console shell and mobile overflow on `/console/excel`.

## Out of Scope

- Rewriting Excel parsing, template mapping, task-type detection, solver submission, or workbook export logic.
- Changing backend API behavior or adding authentication gates.
- Refactoring all console pages to `ConsoleShell`.
- Adding a command palette, global search, user menu, or persisted console preferences.
- Introducing icon libraries or new UI package components.
- Changing existing public `PublicShell`.

## Current Evidence

- Prior UX concern from user: current web layout and structure are not good enough.
- Existing `/console/excel`: `apps/web/src/app/console/excel/page.tsx`
- Existing public shell pattern: `apps/web/src/components/PublicShell.tsx`
- Existing Excel E2E: `e2e/tests/console-excel.spec.ts`
- Existing 老张 vertical slice E2E: `e2e/tests/laozhang-excel-vertical-slice.spec.ts`
- Planning references:
  - PRD FR E11: Console Excel upload-download.
  - Epics Epic 3.E: 老张 Console Excel Upload-Download UX.
  - UX spec: Console, Excel, and critical journey coverage.

## Acceptance Criteria

1. `/console/excel` renders a shared console header with brand link, console navigation, active Excel state, and a public/docs/algorithm escape path.
2. `/console/excel` keeps the heading matching `/上传 Excel/` and keeps `data-testid="excel-drop-zone"` visible in the idle state.
3. Existing Excel selectors remain compatible:
   - `excel-received-card`
   - `confirmation-modal`
   - `detection-confidence`
   - `detection-override-select`
   - `excel-confirmed-card`
   - `vrptw-preview-card`
   - `schedule-preview-card`
   - `inventory-preview-card`
   - `*-payload-json`
   - `*-submit-button`
   - `*-501-card`
   - `*-download-button`
   - `excel-reset-button`
4. The current local privacy promise remains visible: original Excel files are parsed in the browser and not uploaded during detection.
5. The 5 MB / 50K rows limits remain visible in the page structure before upload and in rejection paths.
6. The workflow stage rail reflects at least upload, detection, preview, and result/download stages without becoming a second state machine.
7. The layout is workbench-style: dense, scannable, and quiet; no marketing hero, decorative gradients, nested page cards, or one-note palette.
8. At `390x844`, `/console/excel` does not introduce document-level horizontal overflow.
9. Existing Console Excel and 老张 vertical-slice E2E still pass.
10. Focused web typecheck and console shell unit coverage pass.

## Implementation Notes

- Prefer `apps/web/src/components/ConsoleShell.tsx`.
- Keep `ConsoleShell` free of router hooks; use an explicit `active` prop.
- Do not require authentication in this story; `/console/excel` is already reachable from welcome/public E2E flows.
- Preserve all existing state transitions and helper functions inside `/console/excel`.
- Keep text wrapping defensive: `min-w-0`, `break-words`, bounded grids, and no fixed wide panels on mobile.
- Reuse existing Tailwind tokens; do not add dependencies.
- Keep `ExcelDropZone` as the idle primary call to action.
- Use stage text as status support only; do not mutate state from the stage rail.

## Three-Round Pre-Implementation Adversarial Review

### Round 1: Boundary Issues

Findings:

1. A console shell can accidentally imply authentication/session controls that do not exist on `/console/excel`.
2. Converting the page into a dashboard can hide the upload zone below the fold, breaking 老张’s first action.
3. New nav can destabilize tests if accessible link names collide with existing links.
4. A shared shell with router hooks would force more client behavior and test setup.
5. Refactoring the large Excel page risks touching business logic by accident.
6. Moving the received card behind layout wrappers can break E2E visibility timing.
7. Stage indicators can drift from the real state machine if modeled separately.
8. Side panels can introduce mobile overflow if fixed widths are used.
9. Adding icons/dependencies for shell polish would widen blast radius.
10. Applying the shell to all console pages in one story would make review too broad.

Revision after Round 1:

- Limit shell application to `/console/excel`.
- Keep `ConsoleShell` prop-driven and hook-free.
- Keep `ExcelDropZone` in the first workflow view and preserve all test IDs.
- Derive stage label from existing `ExcelState.kind`; do not introduce independent workflow state.
- Avoid new dependencies and avoid auth/user menu claims.

### Round 2: Drift, Data Consistency, and Dependency Consistency

Findings:

1. Console nav can drift from actual routes if it includes planned pages that do not exist.
2. Labels like "结果" can overclaim real solver completion when VRPTW/Schedule/Inventory still return 501 demo cards.
3. Privacy copy must remain exact enough: browser parsing happens locally, but demo submit still sends mapped payload.
4. The page should not claim CSV support as an Excel page even though one rejection hint mentions future CSV.
5. Side panels must not duplicate rejection remediation in a way that creates conflicting limits.
6. Existing `Link` mock tests expect no new Next runtime dependencies.
7. `PublicShell` and `ConsoleShell` should stay separate to avoid public/console IA coupling.
8. Using `max-w-4xl` from the old page underuses desktop workbench space; using unbounded width risks unreadable lines.
9. Unit tests should assert shell/nav structure but not parse real workbooks.
10. E2E should remain the source of truth for upload/confirm/download flows.

Revision after Round 2:

- Include only existing console routes in nav.
- Phrase result stage as "结果/下载" and keep demo/501 honesty in existing cards.
- Keep privacy copy scoped to detection; avoid saying nothing ever leaves the browser.
- Add a focused idle-render unit test and keep workbook flows in Playwright.
- Separate `ConsoleShell` from `PublicShell`.

### Round 3: Closure and Regression Risk

Findings:

1. A layout story is incomplete unless it gives measurable navigation and overflow evidence.
2. The shell must give closed navigation among adjacent console workflows without burying public docs/algorithm escape links.
3. The Excel page must remain usable after every terminal state: too large, parse error, rejected file, unknown/LP handoff, and preview submit.
4. Status metadata should be bounded and not resize the header unpredictably.
5. The mobile header must wrap without forcing horizontal scroll.
6. Existing public mobile overflow coverage does not include `/console/excel`.
7. Post-implementation review should inspect changed lines for business logic drift, not just visual structure.
8. Sprint status should track EVO.3 through ready-for-dev, code-review, and done.
9. CI failures from external downloads should be separated from code failures.
10. Story should not be marked done until tests, review, PR, CI, merge, and local sync complete.

Revision after Round 3:

- Add `/console/excel` to mobile overflow E2E.
- Keep stage rail and context panels as layout-only support.
- Preserve reset controls and existing terminal cards.
- Require post-implementation review before `done`.

## Implementation Checklist

- [x] Create `ConsoleShell` / `ConsolePageHeader`.
- [x] Refactor `/console/excel` to use the console shell and workflow layout.
- [x] Preserve existing Excel state machine and selectors.
- [x] Add focused shell/page unit test.
- [x] Extend mobile overflow E2E to `/console/excel`.
- [x] Run focused web tests.
- [x] Run focused E2E tests.
- [x] Run typechecks and `git diff --check`.
- [x] Run post-implementation code review and apply required fixes.
- [x] Commit, push, open PR, verify CI, merge/sync if clean.

## Dev Agent Record

### Debug Log

- 2026-06-08: Created story after EVO.2 merge. BMAD resolver script was absent in this repository, so workflow customization fallback used repository config and existing artifacts directly.
- 2026-06-08: Implemented `ConsoleShell` as a hook-free reusable shell and applied it only to `/console/excel`.
- 2026-06-08: Refactored `/console/excel` layout into a workbench header, stage rail, primary workflow area, and bounded context panels while keeping the Excel state machine and E2E selectors unchanged.
- 2026-06-08: Initial 老张 vertical-slice E2E run failed before reaching `/console/excel` because the homepage signup click did not navigate; immediate rerun passed, so it was treated as unrelated homepage/test flake rather than a story regression.

### Completion Notes

- `ConsoleShell` / `ConsolePageHeader` added at `apps/web/src/components/ConsoleShell.tsx`.
- `/console/excel` now renders in a console workbench shell with active Excel nav, docs/algorithm support links, workflow stages, and privacy/limit/output context panels.
- Existing upload, parse, detect, override, preview, submit, 501 demo, reset, and workbook download behavior is preserved.
- Main work area outer framing was removed during review to avoid card-inside-card layout around `ExcelDropZone` and status cards.
- Post-implementation review completed with 0 decision-needed / 1 patch applied / 0 defer.

### File List

- `_bmad-output/stories/evo-3-console-shell-excel.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/src/components/ConsoleShell.tsx`
- `apps/web/src/app/console/excel/page.tsx`
- `apps/web/src/app/console/excel/page.test.tsx`
- `e2e/tests/public-mobile-overflow.spec.ts`

### Change Log

- 2026-06-08: Story created with three pre-implementation adversarial review rounds.
- 2026-06-08: Console shell and Excel workflow IA implemented, reviewed, and verified.

## Post-Implementation Code Review

Completed 2026-06-08.

Review target: uncommitted branch diff for `codex/ux-console-shell-excel`, including new story/test/shell files.

Layers:

- Blind Hunter: found one visual-structure issue where the new primary workflow wrapper created card-inside-card framing around `ExcelDropZone` and status cards.
- Edge Case Hunter: no changed-line state-machine, selector, reset, terminal-state, or mobile overflow regressions after patch.
- Acceptance Auditor: no remaining AC violations after patch.

Triage:

- Decision-needed: 0
- Patch: 1 applied — removed the bordered primary workflow wrapper so the DropZone/status cards are not nested inside another card.
- Defer: 0
- Dismissed/noise: 0

Verification evidence:

- `pnpm --filter @opticloud/web test -- src/app/console/excel/page.test.tsx src/app/docs/page.test.tsx`: 2 passed.
- `pnpm --filter @opticloud/web typecheck`: passed.
- `pnpm --dir e2e typecheck`: passed.
- `pnpm --dir e2e exec playwright test public-mobile-overflow.spec.ts console-excel.spec.ts --workers=1`: 18 passed.
- `pnpm --dir e2e exec playwright test laozhang-excel-vertical-slice.spec.ts --workers=1`: passed on rerun.
- `git diff --check`: passed.
