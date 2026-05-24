---
story_key: 3-e-7-excel-chart-embedding
epic_num: 3.E
story_num: 3.E.7
epic_name: Console Excel Upload-Download UX
status: done
priority: 🟠 High (老张-1; VRPTW chart preview inside exported workbook)
sizing: M (~4-6 hours; export-path refactor + chart image generation + focused tests)
type: implementation + test + chart embedding
created_by: bmad-create-story
created_at: 2026-05-24
sources:
  - _bmad-output/planning/epics.md:384 (Epic 3.E goal - upload -> solve -> download Excel with chart preview)
  - _bmad-output/planning/epics.md:817 (老张-1 chart embedding via xlsx-style)
  - _bmad-output/planning/epics.md:1496-1498 (Story 3.E.7 stub and AC)
  - _bmad-output/planning/prd.md:1258 (Excel ability uses xlsx-style + ExcelJS)
  - _bmad-output/planning/prd.md:1478 (FR E11 includes chart preview)
  - _bmad-output/planning/architecture.md:156,529,3284 (Console Frontend Stack / ECharts / 老张 mapping)
  - _bmad-output/planning/ux-design-specification.md:666,695,767,820,1055,1214,1394,1558,3214 (Sparkline/ECharts/Excel surface/voice/a11y)
  - _bmad-output/stories/3-e-6-excel-result-download.md (download workbook contract and chart-later boundary)
  - _bmad-output/stories/3-e-8-zh-ux-friendly-voice.md (voice copy stays factual; chart story must not reintroduce hype)
  - apps/web/src/lib/excel.ts:7-9 (write path belongs on the download route only)
  - apps/web/src/lib/excel-export.ts:255 (current workbook builder entry point)
  - apps/web/src/app/console/excel/page.tsx:260,338,594,853 (DownloadResultCard and three preview cards)
  - apps/web/package.json:21 (xlsx runtime dep already present; chart libs should be added here)
dependencies:
  upstream:
    - 3-e-6-excel-result-download (done) - workbook download contract and dynamic import pattern
    - 3-e-3-vrptw-template (done) - VRPTW payload and demo data shape
  related_not_blocking:
    - 3-e-8-zh-ux-friendly-voice (done) - copy polish must remain intact
    - 3-e-9-laozhang-vertical-slice-e2e (done) - keep the Excel arc green; optional focused regression if needed
    - 3.2 prediction backend (future) - real route geometry can plug into the same chart input contract later
---

# Story 3.E.7 - VRPTW Chart Preview Embedding in Excel Workbook

## User Story

**As** 老张（制造排程工程师，Excel 是主工具，老板通常先看图再看表），
**I want** VRPTW 导出的结果工作簿里带上一个可直接打开的 chart preview sheet，
**so that** 我能在 Excel 里直接看客户散点图 / 路线时间轴，而不是把结果再切回网页或手工截图。

## Why This Story

3.E.6 已经把 upload -> solve/demo -> download 的闭环打通，但导出的 workbook 仍然是数据表为主。Epic / PRD 对 E11 都明确写了 chart preview；老张-1 这条需求的核心不是再做一个页面，而是把可视化一起写进 Excel 文件里。

这里有一个必须先收口的边界：当前 VRPTW payload 还没有稳定的真实 route geometry。这个 story 不等未来 solver 结构，先用当前 payload 生成一个**可追溯、可标注的 derived preview**，同时保留未来真实 route 数据的接入点。这样 feature 能 ship，且不会伪装成真实 solver 输出。

## Scope

### This story does

1. 只为 **VRPTW** 导出开启 chart embedding。
2. 继续复用 3.E.6 的 workbook 结构：`输入 — *`、`Results`、`Summary`。
3. 新增一个 `Chart Preview` worksheet，里面嵌入至少两张图：
   - 客户散点 / depot / vehicle legend
   - 路线时间轴或 Gantt-like preview
4. 使用 `echarts` 生成图像快照，使用 `exceljs` 把图像写进 workbook。
5. `Summary` 里记录 chart 的来源模式：`derived_preview` 或 `solver_route`。
6. Schedule / Inventory 保持 chart-free，不改现有下载体验。

### This story does not

- 不新增后端接口。
- 不引入服务端图片生成。
- 不做网页内 chart dashboard。
- 不把 chart embedding 扩到 Schedule / Inventory。
- 不等待 3.2 真实 route geometry 才 ship。
- 不改 3.E.8 的中文 voice polish。

## Acceptance Criteria

### AC1: VRPTW chart embedding is opt-in and download-only

- `buildResultWorkbook` 仍是单一导出入口。
- VRPTW 路径开启 chart embedding，其他 task_type 默认关闭。
- `echarts` 和 `exceljs` 只允许在 download click 后动态加载。
- `/console/excel` 首屏 bundle 不应被 chart libs 拉大。
- `apps/web/package.json` 需要新增 `echarts` 和 `exceljs` runtime deps，`pnpm-lock.yaml` 同步更新。

### AC2: Workbook gains a `Chart Preview` sheet for VRPTW

- VRPTW 导出时，sheet order 保持为：输入 sheets -> `Results` -> `Summary` -> `Chart Preview`.
- `Chart Preview` 至少包含 2 个 workbook-embedded image。
- 图像必须是 workbook 里的嵌入媒体，不是外链，不是截图占位。
- derived preview 需要来自当前 VRPTW payload 的确定性转换：
  - scatter: customers.lat / customers.lng + depot / vehicle legend
  - timeline: customer order + time window / service duration when present
- 图表标题和备注要明确区分 `derived_preview` 与未来 `solver_route`.

### AC3: Chart source contract resolves the ambiguity

- 若未来 solver route 数据可用，chart builder 直接消费真实 route / stop / time data.
- 若没有真实 route 数据，chart builder 必须从当前 VRPTW payload 生成 deterministic derived preview.
- derived preview 必须标注为 preview，不得暗示它就是 solver 真结果。
- 不允许把 chart embedding 写成“等后端补齐再做”的阻塞项。

### AC4: Summary sheet records chart metadata

`Summary` 需要新增至少以下键值：

- `chart_mode` (`derived_preview` | `solver_route`)
- `chart_source` (`vrptw_payload` | `solver_route_data`)
- `chart_sheet_name`

保留 3.E.6 已有的：
- `status`
- `source_filename`
- `objective_value`
- `solve_seconds`
- `generated_by`
- `generated_at`

### AC5: Download UI stays stable

- `DownloadResultCard` 仍使用原按钮和 loading/error 语义。
- VRPTW download 只是在内部启用 chart mode。
- Schedule / Inventory 的下载行为和 sheet contract 不变化。
- 不要加新的下载按钮或新的页面控件。

### AC6: Tests prove chart insertion, not just download success

新增或扩展测试，至少覆盖：

1. VRPTW derived preview 生成 `Chart Preview` sheet。
2. workbook 里能读到至少 2 个嵌入 image。
3. `Summary.chart_mode` / `Summary.chart_source` 正确。
4. non-VRPTW 仍无 chart sheet，且 sheet contract 不回退。
5. VRPTW workbook 仍保留 `Results` 和 `Summary` 的 3.E.6 结构。
- 验证方式必须能证明媒体确实写进了 xlsx zip，例如用 `exceljs` readback 的 `workbook.model.media` / `worksheet.getImages()`，或检查 `xl/media/*`，而不是只看 sheet name。

### AC7: Quality gates pass

- `pnpm install`
- `pnpm --filter @opticloud/web test`
- `pnpm --filter @opticloud/web typecheck`
- `pnpm --filter @opticloud/web build`
- `pnpm --filter @opticloud/ui test`
- `pnpm --filter @opticloud/ui typecheck`
- `pnpm --dir e2e exec playwright test tests/console-excel.spec.ts --project=chromium`
- `git diff --check`

## Tasks / Subtasks

- [x] T1: Lock chart source contract (AC: 1, 3, 4)
  - [x] Extend `ExportRequest` with the minimal chart flag / source hook.
  - [x] Define `derived_preview` vs `solver_route` as the only supported modes.
  - [x] Keep non-VRPTW exports on the current path.

- [x] T2: Add VRPTW chart helper (AC: 2, 3)
  - [x] Create a small helper under `apps/web/src/lib/` for chart data derivation and ECharts snapshot generation.
  - [x] Use fixed offscreen dimensions so `echarts.getDataURL()` is deterministic.
  - [x] Turn animation off for export snapshots.
  - [x] Generate a scatter chart and a timeline/Gantt-like preview.

- [x] T3: Refactor workbook writer for chart-enabled VRPTW only (AC: 1, 2, 4, 5)
  - [x] Keep the existing SheetJS flow for non-VRPTW.
  - [x] Add the ExcelJS path only when chart embedding is enabled.
  - [x] Insert the `Chart Preview` sheet and workbook images.
  - [x] Preserve `Results` / `Summary` / filename contract from 3.E.6.

- [x] T4: Wire VRPTW download to chart mode (AC: 1, 5)
  - [x] Enable chart mode only for the VRPTW `DownloadResultCard`.
  - [x] Leave Schedule / Inventory as chart-free exports.
  - [x] Keep button text, loading state, and error state unchanged.

- [x] T5: Tests (AC: 6)
  - [x] Expand `apps/web/src/lib/excel-export.test.ts` with chart-sheet and embedded-media coverage.
  - [x] Verify `Chart Preview` sheet and embedded images using workbook readback that can inspect media.
  - [x] Preserve all 3.E.6 assertions.

- [x] T6: Quality gates and sprint tracking (AC: 7)
  - [x] Run the listed gates.
  - [x] Update `_bmad-output/stories/sprint-status.yaml` for the implementation handoff.
  - [x] Do not mark `done` before review.

## Dev Notes

### Implementation guidance

- Keep `buildResultWorkbook` as the one entry point. Do not create a parallel “chart download” route.
- Use browser-only dynamic imports for `echarts` and `exceljs`.
- Use the browser-compatible ExcelJS entry only; do not rely on Node-only workbook code in the client bundle.
- `xlsx-style` is a planning-doc reference only; it is not the implementation target for chart embedding.
- ECharts snapshot rendering should use `getDataURL()` after the chart has finished rendering; for export, use `animation: false` so the image is deterministic.
- ECharts container must have explicit width/height before `init()`.
- ExcelJS should be used only for the VRPTW chart-enabled path where workbook images are needed.
- `Chart Preview` should be a real worksheet, not a hidden metadata hack.
- The chart preview must be labelled as preview when the source is derived, so we do not mislead the user.
- If future solver route data appears later, the contract can accept it without changing the sheet shape.
- Preserve the existing `ExportedWorkbook` return shape (`blob`, `filename`, `sheetNames`) so `DownloadResultCard` does not change.

### File boundaries

Likely touched files:
- `apps/web/src/lib/excel-export.ts`
- `apps/web/src/lib/vrptw-chart.ts` (new)
- `apps/web/src/lib/excel-export.test.ts` or `apps/web/src/lib/vrptw-chart.test.ts`
- `apps/web/src/app/console/excel/page.tsx`
- `apps/web/package.json`
- `pnpm-lock.yaml`
- `e2e/tests/console-excel.spec.ts` (only if a focused smoke is needed)

### Current code shape to preserve

- `apps/web/src/lib/excel.ts` already warns that write path belongs on the download route only.
- `apps/web/src/lib/excel-export.ts` currently owns the workbook download contract and uses dynamic `import("xlsx")`.
- `apps/web/src/app/console/excel/page.tsx` already holds the three template preview cards and `DownloadResultCard`.
- `3.E.6` already established `Results` + `Summary` sheet contract, so this story must extend rather than replace it.

### Voice / UX guardrails

- No new marketing copy.
- No “恭喜”, “太棒”, or other over-friendly phrasing in workbook metadata.
- `Summary` should stay factual and terse.
- Do not add page-level chart explanations unless a regression forces it; the workbook should carry the feature.

### Previous story intelligence

From 3.E.6:
- Workbook download is already client-side and dynamic-imported.
- The sheet naming contract is already stable.
- `DownloadResultCard` is already wired into each preview card.

From 3.E.8:
- Existing Chinese copy and loading states are already polished.
- Do not touch the voice just because charts are added.

### Risks & mitigations

| Risk | Mitigation |
|---|---|
| Chart libs bloat the initial bundle | Keep `echarts` and `exceljs` behind dynamic imports inside the download path. |
| Workbook images are flaky in Excel/LibreOffice | Use fixed sheet dimensions, deterministic export size, and a dedicated `Chart Preview` sheet. |
| Preview could be mistaken for true solver output | Always record `derived_preview` in `Summary` when route data is synthesized. |
| Sheet readers may not expose embedded images | Use workbook readback that can inspect media, not only `xlsx.read`. |
| Non-VRPTW exports regress | Keep the existing SheetJS path for schedule/inventory. |

## Definition of Ready

- 3.E.6 exists and is the current workbook baseline.
- VRPTW payload shape is stable in `vrptw-template.ts`.
- The team accepts that the first chart preview can be derived from current payload data instead of waiting for new backend route geometry.
- No backend route geometry API is required to start.

## Definition of Done

- VRPTW exports include a `Chart Preview` sheet with embedded chart images.
- Summary metadata tells users whether the preview is derived or solver-backed.
- Non-VRPTW exports still match the 3.E.6 workbook contract.
- Required tests and build gates pass.
- Sprint tracking is updated in the same change set.

## Review Log

### Round 1 - Data Consistency

PASS.
- Clarified that chart embedding is VRPTW-only.
- Resolved the missing route-geometry ambiguity with a `derived_preview` fallback.
- Kept `Results` and `Summary` contract intact.

### Round 2 - Function Consistency

PASS.
- Kept non-VRPTW on the existing workbook path.
- Made `echarts`/`exceljs` download-only dynamic imports.
- Kept `DownloadResultCard` semantics unchanged.

### Round 3 - Boundary / Closed Loop

PASS.
- No backend dependency.
- Workbook-only feature, no new UI page.
- Tests cover chart media, not only file download.
- Ready for `dev-story`.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-24 - Added `apps/web/src/lib/vrptw-chart.ts` for derived preview chart modeling, browser-side ECharts snapshotting, and workbook image payloads.
- 2026-05-24 - Refactored `apps/web/src/lib/excel-export.ts` to keep SheetJS for non-VRPTW exports and route VRPTW through ExcelJS only when chart embedding is needed.
- 2026-05-24 - Wired `/console/excel` VRPTW download to pass chart mode internally while leaving Schedule / Inventory untouched.
- 2026-05-24 - Expanded `apps/web/src/lib/excel-export.test.ts` to validate `Chart Preview`, embedded workbook media, summary metadata, and non-VRPTW regression boundaries.
- 2026-05-24 - First Playwright run with default workers showed dev-server startup timeout on the earliest `/console/excel` navigations; reran the same spec with `--workers=1` and it passed cleanly.
- 2026-05-24 - Code review found a route-mode drift risk; tightened the helper so solver-backed mode requires explicit route data instead of silently reusing the derived fallback.
- 2026-05-24 - Ran `pnpm --filter @opticloud/web test`, `pnpm --filter @opticloud/web typecheck`, `pnpm --filter @opticloud/web build`, `pnpm --filter @opticloud/ui test`, `pnpm --filter @opticloud/ui typecheck`, `pnpm --dir e2e exec playwright test tests/console-excel.spec.ts --project=chromium --workers=1`, and `git diff --check` successfully.

### Completion Notes List

- Added a dedicated VRPTW chart helper that emits a `Chart Preview` worksheet plus two embedded PNG images for the scatter and timeline previews.
- Kept non-VRPTW workbook generation on the existing SheetJS path so Schedule and Inventory downloads stay chart-free.
- Recorded factual chart metadata in `Summary` and labeled derived previews explicitly as `derived_preview` / `vrptw_payload`.
- Preserved the existing `/console/excel` download UX and only switched the internal VRPTW export path to ExcelJS.
- Covered the workbook contract with readback-based Vitest assertions, including media inspection through ExcelJS.
- Kept the feature bounded to frontend export logic; no backend API or new page was introduced.

### File List

- `_bmad-output/stories/3-e-7-excel-chart-embedding.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/package.json`
- `apps/web/src/app/console/excel/page.tsx`
- `apps/web/src/lib/excel-export.ts`
- `apps/web/src/lib/excel-export.test.ts`
- `apps/web/src/lib/vrptw-chart.ts`
- `pnpm-lock.yaml`

### Change Log

- 2026-05-24 - Story remained ready-for-dev while implementation was in progress.
- 2026-05-24 - Implemented VRPTW workbook chart preview embedding, added workbook-media tests, and moved the story into review.
- 2026-05-24 - Applied post-implementation review fix to prevent solver-backed chart mode from reusing derived fallback data.

## Senior Developer Review (AI)

### Review Date

2026-05-24

### Review Result

Approved after one fix. The only meaningful review finding was a route-mode drift risk in `vrptw-chart.ts`; it was corrected by requiring explicit route data for solver-backed previews. No unresolved patch findings remain.

### Review Findings

- [x] [Patch] `solver_route` mode could be claimed without route data, which would overstate a derived preview as solver output — fixed by requiring explicit `routeData` for solver-backed charts and falling back to `derived_preview` otherwise.

### Verification

- `pnpm --filter @opticloud/web test` - passed (50 tests)
- `pnpm --filter @opticloud/web typecheck` - passed
- `pnpm --filter @opticloud/web build` - passed
- `pnpm --filter @opticloud/ui test` - passed (38 tests)
- `pnpm --filter @opticloud/ui typecheck` - passed
- `pnpm --dir e2e exec playwright test tests/console-excel.spec.ts --project=chromium --workers=1` - passed (13 tests)
- `git diff --check` - passed
