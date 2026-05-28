---
story_key: 3-e-7-excel-chart-embedding
epic_num: 3.E
epic_name: Console Excel Upload-Download UX
story_num: 3.E.7
status: done
priority: 🟠 High (FR E11 chart preview closure for 老张 Excel workbook)
sizing: M (~3-4 hours; client workbook exporter + tests; no backend)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-28
sources:
  - _bmad-output/planning/epics.md:1492 (3.E.6 result download defers chart to v1 end)
  - _bmad-output/planning/epics.md:1496 (3.E.7 asks for chart embedding via xlsx-style)
  - _bmad-output/planning/prd.md:1478 (FR E11 requires result Excel with input sheets, results sheet, chart preview)
  - _bmad-output/planning/architecture.md:3284 (老张 Excel surface maps to web/api-gateway + download chart)
  - _bmad-output/planning/ux-design-specification.md:2467 (老张 flow ends with downloadable Excel for boss review)
  - _bmad-output/stories/3-e-6-excel-result-download.md (predecessor exporter contract and download wiring)
  - apps/web/src/lib/excel-export.ts (current client-side workbook writer)
  - apps/web/src/lib/excel-export.test.ts (current workbook round-trip tests)
  - apps/web/src/app/console/excel/page.tsx (download button selectors and card wiring)
  - e2e/tests/console-excel.spec.ts and e2e/tests/laozhang-excel-vertical-slice.spec.ts (download E2E coverage)
dependencies:
  upstream:
    - 3-e-6-excel-result-download (done) - workbook export with input sheets, Results and Summary
    - 3-e-3-vrptw-template / 3-e-4-schedule-template / 3-e-5-inventory-template (done) - payloads used as chart data source
  downstream:
    - 3-e-8-zh-ux-friendly-voice - copy/voice polish only; must not be forced by this story
    - 3-e-9-laozhang-vertical-slice-e2e (done) - should be extended to assert chart preview workbook content
---

# Story 3.E.7 - Excel Chart Preview Embedding (老张-1)

## User Story

**As** 老张（制造排程工程师，Excel 是主工具），
**I want** the downloaded result workbook to include an immediately readable **Chart Preview** sheet for routes, schedules, or forecast bands,
**so that** I can send one `.xlsx` to my boss/team and they can see both the raw output rows and a visual preview without opening a web dashboard or writing code.

## Why This Story

Story 3.E.6 closed the upload -> solve/demo -> download loop, but explicitly left chart preview to 3.E.7. FR E11 and the 老张 UX flow both require the workbook to be boss-readable, not just a table dump.

Important technical discovery for this story:

- The planning artifact says "via xlsx-style".
- The current repo has only `xlsx@0.18.5`; no `xlsx-style` dependency exists.
- `xlsx-style@0.8.13` is an old SheetJS fork for cell formatting. It writes styles, but it is not a native Excel chart or image embedding library.
- `xlsx-js-style@1.2.0` is the maintained style fork aligned with SheetJS `0.18.5`; it supports basic cell styles, not native chart objects.

Therefore, this story must **not** falsely claim native Excel Chart XML, SVG image embedding, or full OOXML DrawingML support. The shippable v1 closure is a spreadsheet-native `Chart Preview` sheet: styled cells, data tables, scatter/grid previews, gantt-like timelines, and forecast bands generated from the same data as `Results`. Native Excel chart objects remain a future ExcelJS/OOXML story if required.

## Scope

This story does:

1. Extend `apps/web/src/lib/excel-export.ts` so every exported workbook includes a `Chart Preview` sheet between `Results` and `Summary`.
2. Use a SheetJS-compatible style writer (`xlsx-js-style`) through dynamic import on download only.
3. Generate visual previews from the existing payload/results data:
   - VRPTW: route scatter grid plus stop timeline/gantt preview.
   - Schedule: resource gantt preview.
   - Inventory: P10/P50/P90 forecast band preview.
4. Keep existing input sheets, `Results`, `Summary`, filenames, and download button selectors stable.
5. Add workbook round-trip tests and E2E assertions that the downloaded workbook contains `Chart Preview`.

This story does not:

- Add backend Excel generation.
- Add a web chart UI, dashboard, ECharts component, or canvas rendering.
- Add native Excel chart objects, SVG files, macros, formulas, or embedded images.
- Change task detection, mapping, submit endpoints, or solver behavior.
- Change user-facing copy outside workbook contents.

## Acceptance Criteria

### AC1: Runtime dependency and import boundary

- Add `xlsx-js-style@^1.2.0` as an `apps/web` runtime dependency.
- `excel-export.ts` must dynamically import the writer inside `buildResultWorkbook`; no top-level `xlsx`, `xlsx-js-style`, ExcelJS, canvas, or charting-library import.
- The initial `/console/excel` bundle must not statically include the writer.
- Keep `xlsx@^0.18.5` available for tests/E2E workbook reading.
- Do not add `xlsx-style@0.8.13`; it is an old style fork and would duplicate SheetJS internals with weaker TypeScript/browser ergonomics.

### AC2: Workbook contract

For every exported workbook:

1. User input sheets still appear first with the existing `输入 — {sheet}` naming and truncation behavior.
2. `Results` remains the same sheet name and data contract as Story 3.E.6.
3. `Chart Preview` is appended after `Results`.
4. `Summary` remains the final summary sheet.
5. `sheetNames` returned by `buildResultWorkbook()` includes `Chart Preview`.
6. `Summary` includes a row `chart_preview_sheet | Chart Preview`.
7. Sheet names remain within Excel's 31-character limit.

### AC3: VRPTW chart preview

Given a VRPTW payload:

- `Chart Preview` contains a section titled `VRPTW 路线散点图`.
- It includes a bounded cell-grid scatter preview derived from customer `lat/lng`.
- The scatter grid must be capped at a small fixed size (recommended: <= 20 columns x 12 rows) so a 50K-row workbook does not create a 50K-cell visual explosion.
- It includes a section titled `VRPTW 停靠顺序 / 甘特预览`.
- The timeline rows are derived from the same route/stop rows used by `Results`.
- If export status is `demo`, the chart sheet visibly includes `🚧 mock (M2-M3)`.
- Degenerate coordinates (all customers have the same lat/lng), empty optional time windows, and one-customer workbooks still produce a valid chart sheet, not division-by-zero or blank output.

### AC4: Schedule and Inventory chart preview

Given a Schedule payload:

- `Chart Preview` contains `Schedule 资源甘特预览`.
- Each task row appears once, with start/end/duration derived from the same deterministic demo rows as `Results`.
- The visual timeline is capped to a bounded width and uses labels/numeric values that still survive `xlsx.read`.

Given an Inventory payload:

- `Chart Preview` contains `Inventory 预测带预览`.
- Each SKU row appears once with P10/P50/P90 derived from the same deterministic forecast rows as `Results`.
- Demo status is explicit with `🚧 mock (M2-M3)`.
- Negative or zero forecast values should not break the preview scale; clamp the visual scale start at 0 while keeping raw values visible in cells.

### AC5: Data consistency and no drift

- `buildResultWorkbook()` must generate `resultsRows = buildResultsRows(payload)` once and use the same `resultsRows` for both the `Results` sheet and `Chart Preview` builders.
- Chart preview data must be derived from `resultsRows`, not independent ad-hoc calculations that could drift.
- Exception: VRPTW scatter-grid coordinates may read `lat/lng` from `payload.customers` because those fields are not written to `Results`; VRPTW stop timeline/gantt rows must still read route/order/timing values from `resultsRows`.
- Primary counts match:
  - VRPTW chart customer/timeline row count = `payload.customers.length`.
  - Schedule chart task row count = `payload.tasks.length`.
  - Inventory chart SKU row count = `payload.skus.length`.
- No formula cells are required; values should remain readable after parsing the workbook back with `xlsx`.
- Existing `Results` tests continue to assert row counts and demo markers.

### AC6: Console integration stays stable

- Do not change `vrptw-download-button`, `schedule-download-button`, or `inventory-download-button`.
- Do not change preview card state machines except as needed to call the updated exporter.
- Do not add new visible UI controls for charts in `/console/excel`.
- Do not move export generation to an API route or server action; 老张 workbook bytes remain browser-local as in 3.E.2/3.E.6.
- `console-excel.spec.ts` should parse the downloaded workbook for Inventory and assert `Chart Preview` exists.
- `laozhang-excel-vertical-slice.spec.ts` should assert the full 老张 downloaded workbook contains `Chart Preview`.

### AC7: Tests

Update or add Vitest coverage in `apps/web/src/lib/excel-export.test.ts`:

1. Existing VRPTW workbook test expects `Chart Preview` in sheet order.
2. New VRPTW chart test asserts route scatter and timeline section labels exist.
3. Schedule test asserts `Schedule 资源甘特预览` exists and task count is represented.
4. Inventory test asserts `Inventory 预测带预览` exists and P10/P50/P90 labels survive round-trip.
5. VRPTW degenerate-coordinate test asserts same lat/lng does not produce a blank chart sheet.
6. Existing sheet-name truncation, filename, solved-summary, and rows-required guard tests remain.

Update E2E:

- Inventory download E2E saves and parses the workbook, then asserts `Chart Preview`.
- 老张 vertical slice E2E asserts `Chart Preview` and an Inventory chart label.

### AC8: Quality gates

Run and record:

- `pnpm --filter @opticloud/web test`
- `pnpm --filter @opticloud/web typecheck`
- `pnpm --filter @opticloud/web build`
- `pnpm --filter @opticloud/ui test`
- `pnpm --filter @opticloud/ui typecheck`
- `pnpm --dir e2e exec playwright test tests/console-excel.spec.ts --project=chromium --workers=1`
- `pnpm --dir e2e exec playwright test tests/laozhang-excel-vertical-slice.spec.ts --project=chromium --workers=1`
- `git diff --check`

## Implementation Tasks

- [x] Add `xlsx-js-style` dependency for `apps/web`.
- [x] Update `excel-export.ts` writer import from `xlsx` to dynamic `xlsx-js-style`.
- [x] Refactor `buildResultWorkbook()` so it builds `resultsRows` exactly once and passes them into the chart-preview builder.
- [x] Add chart-preview row builders:
   - `buildVrptwChartPreviewRows`
   - `buildScheduleChartPreviewRows`
   - `buildInventoryChartPreviewRows`
   - shared styled-cell helpers and bounded grid helpers.
- [x] Append `Chart Preview` sheet in `buildResultWorkbook()`.
- [x] Add `chart_preview_sheet` to `Summary`.
- [x] Update unit tests and E2E tests.
- [x] Run quality gates.
- [x] Run post-implementation code review and apply fixes.
- [x] Update sprint status and sync GitHub.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Planning says `xlsx-style`, but package does not support native charts | Use `xlsx-js-style` for styled spreadsheet-native chart previews; document native chart objects as out of scope. |
| Chart preview data drifts from `Results` | Reuse existing result-row helpers for chart tables wherever possible. |
| Large workbooks cause heavy export | Existing 5MB / 50K input gates still bound client export. Chart preview is summarized and bounded. |
| Same lat/lng or one-row data makes grid blank | Clamp spans and place at least one visible marker. |
| Style writer changes workbook parse behavior | Round-trip every workbook through `xlsx.read` in Vitest/E2E. |
| Existing E2E download selectors break | Explicitly preserve all three `*-download-button` test IDs. |

## Definition of Done

- Three pre-implementation story review rounds completed and amendments applied.
- Workbook includes `Chart Preview` for VRPTW, Schedule, and Inventory.
- Existing result workbook contract remains compatible except the intentional new sheet.
- Unit/E2E tests prove `Chart Preview` survives real download and parse.
- Post-implementation code review completed; fixes applied.
- Branch pushed and PR created.

---

## Story Review Round 1 - Data Consistency

### Findings

1. **Potential drift between `Results` and `Chart Preview`**: the initial draft said chart rows should be derived from payload/result helpers, but did not force the implementation to reuse the exact `Results` rows already written to the workbook.
2. **VRPTW coordinate exception needed**: `Results` contains route/vehicle/stop/order data but does not contain `lat/lng`, so the route scatter grid cannot be derived only from `Results` without expanding the Results contract.
3. **Summary closure needed**: `Summary` should explicitly name the chart preview sheet so workbook consumers can detect support without relying only on `SheetNames`.

### Amendments Applied

- AC5 now requires `buildResultWorkbook()` to call `buildResultsRows(payload)` once and pass that same `resultsRows` matrix to the chart-preview builder.
- VRPTW scatter source is explicitly allowed to read coordinates from `payload.customers`; VRPTW timeline/gantt rows must read from `resultsRows`.
- Schedule and Inventory chart rows must read from `resultsRows`, not re-run independent calculations.
- Task list now includes the `resultsRows` refactor before chart builders.

### Round 1 Decision

PASS after amendments. The story now prevents data drift while preserving the only required payload-only data source for VRPTW scatter coordinates.

---

## Story Review Round 2 - Function Consistency and Drift

### Findings

1. **Dependency drift risk**: the epic says `xlsx-style`, but adding the old `xlsx-style@0.8.13` would introduce a stale SheetJS fork and duplicate spreadsheet writer behavior already covered by `xlsx@0.18.5`.
2. **Import-boundary risk**: the first draft said dynamic import for the style writer but did not explicitly prohibit top-level `xlsx`/ExcelJS/canvas/chart imports.
3. **Architecture drift risk**: story scope could be misread as "add chart UI to Console" or "server-generate workbook".
4. **Function contract risk**: `buildResultWorkbook()` is already the single public exporter; adding a separate export path would break 3.E.6 tests and page wiring.

### Amendments Applied

- AC1 now explicitly chooses `xlsx-js-style@^1.2.0` and prohibits adding old `xlsx-style@0.8.13`.
- AC1 now prohibits top-level spreadsheet/chart/canvas imports.
- AC6 now explicitly keeps export generation browser-local and forbids API route/server action generation.
- Implementation tasks keep `buildResultWorkbook()` as the only public export path.

### Round 2 Decision

PASS after amendments. The story now preserves the 3.E.6 function boundary and avoids dependency/API drift.

---

## Story Review Round 3 - Boundary, Edge Cases, and Closure

### Findings

1. **Large workbook boundary**: a literal scatter/gantt cell per source row could make export too large under the 50K-row cap.
2. **Degenerate chart boundary**: same-coordinate VRPTW inputs, one-customer VRPTW, empty optional time windows, and narrow forecast ranges can create divide-by-zero or blank scales.
3. **Workbook closure**: the first draft did not explicitly preserve the 31-character sheet-name rule for the new sheet, although `Chart Preview` is safe.
4. **Test closure**: E2E only checking sheet existence could miss a blank chart sheet; unit tests should assert label/content survival.

### Amendments Applied

- AC2 now restates the sheet-name length invariant.
- AC3 caps VRPTW scatter grid size and requires degenerate-coordinate/one-customer handling.
- AC4 caps Schedule visual width and handles non-positive forecast scaling.
- AC7 adds a VRPTW degenerate-coordinate test and keeps content-label assertions for every task type.
- Definition of Done now explicitly says three pre-implementation review rounds are complete.

### Round 3 Decision

PASS after amendments. The story is ready for implementation.

## Final Story Status

`done`

---

## Dev Agent Record

### Debug Log

- 2026-05-28: Added `xlsx-js-style@^1.2.0` to `apps/web` and lockfile.
- 2026-05-28: Extended `buildResultWorkbook()` to generate `Results` once, append `Chart Preview`, and add `chart_preview_sheet` to Summary.
- 2026-05-28: Added VRPTW scatter/timeline, Schedule gantt, and Inventory forecast-band preview rows with fixed-size visual output.
- 2026-05-28: Updated Vitest and Playwright download assertions to parse generated workbooks and verify `Chart Preview`.
- 2026-05-28: First parallel Playwright attempt was invalid because two specs started webServer concurrently and collided on ports 3000/8001/8002; reran specs sequentially.
- 2026-05-28: Initial build failed during concurrent run with stale `.next` type output; removed `apps/web/.next` after workspace path verification and reran build successfully.

### Completion Notes

- Workbook contract now writes sheets in order: input sheets, `Results`, `Chart Preview`, `Summary`.
- `Chart Preview` is spreadsheet-native and style-based, not native Excel Chart XML or embedded SVG, matching the three story review decisions.
- Existing download button test IDs remain unchanged.
- Post-implementation review found and fixed VRPTW scatter scaling: coordinates now scale from actual customer bounds rather than including zero.
- Post-implementation review also removed unused forecast style constants and added a regression test for VRPTW customer-bound scaling.

### File List

- `_bmad-output/stories/3-e-7-excel-chart-embedding.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/package.json`
- `pnpm-lock.yaml`
- `apps/web/src/lib/excel-export.ts`
- `apps/web/src/lib/excel-export.test.ts`
- `e2e/tests/console-excel.spec.ts`
- `e2e/tests/laozhang-excel-vertical-slice.spec.ts`

### Change Log

- 2026-05-28: Created story 3.E.7 with three pre-implementation review rounds.
- 2026-05-28: Implemented Chart Preview workbook sheet and tests.
- 2026-05-28: Ran quality gates and implementation review; applied review fixes.

## Senior Developer Review (AI)

Outcome: Approved after fixes.

### Review Layers

- Blind Hunter equivalent: reviewed diff-only behavior for workbook contract and dependency impact.
- Edge Case Hunter equivalent: reviewed exporter boundaries for coordinate scaling, degenerate VRPTW coordinates, fixed visual dimensions, and stale style constants.
- Acceptance Auditor equivalent: checked implementation against AC1-AC8 in this story.

### Findings and Fixes

- [x] **Medium - VRPTW scatter used zero in coordinate bounds**: This compressed normal China-local coordinates into a corner of the grid. Fixed by scaling against customer min/max bounds and using zero only for empty inputs.
- [x] **Low - Unused forecast style constants**: Removed unused `forecastLow` / `forecastHigh` constants to avoid misleading future maintainers.
- [x] **Low - Missing explicit regression for coordinate-bound scaling**: Added Vitest assertion for `lat 31.2000..31.4000` and `lng 121.1000..121.3000`.

### Validation

- `pnpm --filter @opticloud/web test` - pass (90 tests)
- `pnpm --filter @opticloud/web typecheck` - pass
- `pnpm --filter @opticloud/web build` - pass after sequential rerun
- `pnpm --filter @opticloud/ui test` - pass (50 tests)
- `pnpm --filter @opticloud/ui typecheck` - pass
- `pnpm --dir e2e exec playwright test tests/console-excel.spec.ts --project=chromium --workers=1` - pass (13 tests)
- `pnpm --dir e2e exec playwright test tests/laozhang-excel-vertical-slice.spec.ts --project=chromium --workers=1` - pass (1 test)
- `git diff --check` - pass
