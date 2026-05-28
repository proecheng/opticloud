---
story_key: 3-e-8-zh-ux-friendly-voice
epic_num: 3.E
epic_name: Console Excel Upload-Download UX
story_num: 3.E.8
status: done
priority: 🟠 High (老张-2 friendly Chinese UX polish before Excel vertical slice is considered complete)
sizing: S (~1.5-2.5 hours; copy/state polish + focused tests; no backend)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-28
sources:
  - _bmad-output/planning/epics.md:1496-1502 (3.E.7/3.E.8 requirements; 老张-2 Brand Voice)
  - _bmad-output/planning/epics.md:817-818 (老张-1/老张-2 additions)
  - _bmad-output/planning/ux-design-specification.md:590-619 (Brand Voice = 实证克制)
  - _bmad-output/planning/ux-design-specification.md:3124-3133 (Console voice = 实证克制 + 友好不滥情)
  - _bmad-output/planning/architecture.md:3284 (老张 Excel surface maps to ExcelDropZone + LoadingShimmer + StatusCard)
  - _bmad-output/stories/3-e-1-excel-drop-zone.md (original 老张-2 entry/copy risk framing)
  - _bmad-output/stories/3-e-6-excel-result-download.md (download button/status behavior)
  - _bmad-output/stories/3-e-7-excel-chart-embedding.md (download workbook now contains Chart Preview; do not change file contract)
  - apps/web/src/app/console/excel/page.tsx (current Excel state machine and visible copy)
  - packages/ui/src/components/ExcelDropZone/index.tsx (dropzone copy and FilePicker label)
  - e2e/tests/console-excel.spec.ts (existing /console/excel regression surface)
  - e2e/tests/laozhang-excel-vertical-slice.spec.ts (老张 full journey expectations)
dependencies:
  upstream:
    - 3-e-7-excel-chart-embedding (done, PR #90) - workbook output contract and E2E parsing must remain stable
    - 3-e-1..3-e-6 (done) - upload/detect/preview/submit/download state machine
  downstream:
    - 3-e-9-laozhang-vertical-slice-e2e - should continue to pass with final copy expectations
---

# Story 3.E.8 - 中文 UX 微调 Brand Voice 友好版（老张-2）

## User Story

**As** 老张（制造排程工程师，Excel 是主工具，不想读开发者术语），
**I want** `/console/excel` 的上传、识别、试跑、下载状态用清楚克制的中文告诉我“文件收到了、正在本地解析、系统判断是什么、下一步做什么”，
**so that** 我不会误以为文件丢了、上传到服务器了、或系统已经给了真实求解结果。

## Why This Story

3.E.1-3.E.7 已经打通 Excel 上传、识别、模板映射、501 demo、结果下载和 Chart Preview。剩余缺口不是功能，而是老张 surface 的“第一眼信任感”：

- 现有页面混用 `task_type`、`Schedule`、`Inventory`、`生成中...` 等偏工程词。
- Loading 文案没有持续强调“本地解析”，容易让制造业用户担心文件已上传。
- Modal 的主要动作是“确认”，但老张真正需要的是“确认并继续”。
- 下载阶段只写“生成中...”，没有说明正在生成 Excel 文件。
- 需要让文案符合 UX Spec 的“实证克制 + 友好不滥情”：讲事实、给下一步，不卖萌、不夸大、不隐藏 demo/M2-M3。

## Scope

This story does:

1. Polish visible Chinese copy in `apps/web/src/app/console/excel/page.tsx`.
2. Polish `packages/ui/src/components/ExcelDropZone/index.tsx` copy for the shared dropzone.
3. Keep all existing state-machine transitions, data-testid selectors, API calls, workbook contract, and file validation rules stable.
4. Add focused tests that lock the final 老张-2 copy expectations.

This story does not:

- Add i18n framework work or translation files.
- Change task-type detection heuristics.
- Change Excel parsing/exporting, workbook sheets, solver endpoints, or download filenames.
- Add authentication requirements to `/console/excel`.
- Redesign layout, colors, route structure, or component APIs.

## Acceptance Criteria

### AC1: Dropzone copy uses 老张-friendly Chinese

In `packages/ui/src/components/ExcelDropZone/index.tsx`:

- Main line should remain direct and action-oriented, e.g. `把 .xlsx 拖到这里`.
- Helper line should use Chinese row wording (`50K 行`, not `50K rows`) and state local handling, e.g. `≤5 MB / 50K 行 · 本地识别...`.
- FilePicker label remains a clear fallback action, e.g. `或点击选择文件`.
- Existing reject behavior (`wrong_type`, `too_large`) and `onReject` contract remain unchanged.

### AC2: Received/loading state closes the “did it upload?” gap

In `/console/excel`:

- `excel-received-card` still includes `已收到您的 Excel 文件` and the filename/MB.
- The loading block says the workbook is being parsed locally and file bytes do not leave the browser.
- The loading state still uses `LoadingShimmer`; no fake percentage is introduced.
- Existing parse success/error/too-many-rows flows remain unchanged.

### AC3: Detection modal uses “system judgment + confirm next step” language

- Modal title changes from engineering-style `自动检测：...` to user-facing `系统判断：...`.
- Confirm button changes to `确认并继续`.
- Manual override label avoids `task_type` jargon, e.g. `如果判断不对，可以手动选择类型`.
- Confidence remains visible and numeric.
- The select values and detection logic do not change.

### AC4: Preview/submit/download copy is consistent and honest

- Preview ready cards use task names meaningful to 老张:
  - VRPTW can keep `VRPTW` but must pair with route/客户/车辆 wording.
  - Schedule should use `排班/调度` in visible titles.
  - Inventory should use `库存预测` in visible titles.
- 501/demo cards keep `M2-M3` visible and do not imply real solving has completed.
- Download button keeps the existing test IDs:
  - `vrptw-download-button`
  - `schedule-download-button`
  - `inventory-download-button`
- Download loading text says `正在生成 Excel...` or equivalent explicit Excel wording.

### AC5: Errors stay actionable, not cute

- Too-large row and file-size errors keep three concrete next steps.
- Parse error tells the user to verify a valid `.xlsx` and “另存为 .xlsx”.
- Wrong-type and too-large behavior from `ExcelDropZone` remains unit-tested.
- Do not add extra emoji density beyond existing status icons.

### AC6: Regression tests

Update tests:

- `packages/ui/src/components/ExcelDropZone/index.test.tsx` asserts the dropzone renders final local-processing copy.
- `e2e/tests/console-excel.spec.ts` asserts:
  - received card/loading copy includes `本地解析`;
  - detection modal title uses `系统判断`;
  - confirm button is `确认并继续`;
  - Inventory download button loading state can show `正在生成 Excel...` without breaking download.
- `e2e/tests/laozhang-excel-vertical-slice.spec.ts` remains passing and can assert final copy if needed.

### AC7: Quality gates

Run and record:

- `pnpm --filter @opticloud/ui test`
- `pnpm --filter @opticloud/ui typecheck`
- `pnpm --filter @opticloud/web test`
- `pnpm --filter @opticloud/web typecheck`
- `pnpm --filter @opticloud/web build`
- `pnpm --dir e2e exec playwright test tests/console-excel.spec.ts --project=chromium --workers=1`
- `pnpm --dir e2e exec playwright test tests/laozhang-excel-vertical-slice.spec.ts --project=chromium --workers=1`
- `git diff --check`

## Implementation Tasks

- [x] Update `ExcelDropZone` visible copy and add unit assertion.
- [x] Update `/console/excel` received/loading and detection modal copy.
- [x] Update preview, 501/demo, submit, and download generation copy without changing test IDs or logic.
- [x] Update focused Playwright assertions for final 老张-2 copy.
- [x] Run quality gates.
- [x] Run post-implementation code review and apply fixes.
- [x] Update sprint status and sync GitHub.

## Dev Agent Record

### Implementation Plan

- Keep this story to visible Chinese copy and focused regression assertions only.
- Preserve all state-machine kinds, task type values, selectors, API calls, workbook contracts, and download filenames.
- Update tests first for final 老张-2 copy, then implement the smallest copy changes needed to pass.

### Debug Log

- 2026-05-28: Started implementation on branch `codex/3-e-8-zh-ux-friendly-voice-story`.
- 2026-05-28: Red phase confirmed target copy failures in `ExcelDropZone` unit test and focused `/console/excel` Playwright checks.
- 2026-05-28: Post-implementation review found two copy precision issues; fixed raw-file privacy wording and English `sheet/header` jargon in detection reasoning.

### Completion Notes

- Updated `ExcelDropZone` to say `把 .xlsx 拖到这里`, use `50K 行`, and state local recognition.
- Updated `/console/excel` received/loading, detection modal, preview, demo/501, fallback, and download generation copy while preserving state kinds, select values, data-test IDs, API calls, workbook sheets, and filenames.
- Updated task labels shown to users for schedule/inventory while keeping payload `task_type` values unchanged.
- Added/updated focused unit and Playwright assertions for 老张-2 final copy.
- Post-implementation code review completed; fixed two patch findings and reran all quality gates.
- Validation passed:
  - `pnpm --filter @opticloud/ui test` (51 passed)
  - `pnpm --filter @opticloud/ui typecheck`
  - `pnpm --filter @opticloud/web test` (90 passed)
  - `pnpm --filter @opticloud/web typecheck`
  - `pnpm --filter @opticloud/web build`
  - `pnpm --dir e2e exec playwright test tests/console-excel.spec.ts --project=chromium --workers=1` (13 passed)
  - `pnpm --dir e2e exec playwright test tests/laozhang-excel-vertical-slice.spec.ts --project=chromium --workers=1` (1 passed)
  - `git diff --check`

## File List

- `_bmad-output/stories/3-e-8-zh-ux-friendly-voice.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/src/app/console/excel/page.tsx`
- `apps/web/src/lib/excel.test.ts`
- `apps/web/src/lib/task-type-detect.ts`
- `e2e/tests/console-excel.spec.ts`
- `e2e/tests/laozhang-excel-vertical-slice.spec.ts`
- `packages/ui/src/components/ExcelDropZone/index.test.tsx`
- `packages/ui/src/components/ExcelDropZone/index.tsx`

## Change Log

- 2026-05-28: Story moved to in-progress after three pre-implementation review rounds.
- 2026-05-28: Implemented 老张-2 Chinese UX copy polish and focused regression coverage.
- 2026-05-28: Completed post-implementation code review; fixed privacy wording and detection-reasoning jargon; final validation passed.

## Senior Developer Review (AI) - Post-Implementation (2026-05-28)

### Outcome

Approved after fixes. No unresolved decision, patch, or deferred findings remain.

### Review Coverage

- Data consistency: payload `task_type`, select values, state kinds, download IDs, workbook sheet names, and filenames remain stable.
- Function consistency: parser, mapper, submit, download, and reset flows were not changed beyond visible copy.
- Drift check: no i18n migration, layout redesign, API change, route change, or workbook contract change was introduced.
- Boundary check: reject, parse-error, too-many-rows, 501/demo, solved/download, and vertical-slice paths remain covered.
- Closure check: all acceptance criteria have corresponding implementation and tests; final quality gates passed.

### Findings and Fixes

- [x] [Review][Patch] Privacy wording was too broad: `文件内容不会离开浏览器` could imply later demo submit never sends derived payload data. Fixed to `原始文件不会上传/未上传`.
- [x] [Review][Patch] Detection reasoning still exposed English `sheet/header` jargon. Fixed visible reasoning to use `工作表` and `表头` wording.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Copy change breaks existing E2E selectors | Keep `data-testid` unchanged; update role/name queries deliberately. |
| Friendly copy hides demo status | Require `M2-M3` to remain visible on 501/demo cards. |
| Scope drifts into layout redesign | Explicitly forbid layout/route/component API changes. |
| "Local parsing" claim becomes false | Current parser is browser-side (`read-excel-file/browser`); do not introduce network calls. |
| Button text changes break download test timing | Keep download test ID and use event-based `page.waitForEvent("download")`. |

## Definition of Done

- Three pre-implementation story review rounds completed and amendments applied.
- 老张-2 copy appears in dropzone, received/loading, detection modal, preview/501/download states.
- Existing Excel upload/detect/submit/download behavior remains stable.
- Tests and quality gates pass.
- Post-implementation code review completed and fixes applied.
- Branch pushed and PR created.

---

## Story Review Round 1 - Data Consistency

### Findings

1. The story could accidentally change semantic values such as `task_type`, select option values, status names, or download IDs while changing visible labels.
2. The “本地解析” copy is only true if no new network call is introduced before detection.
3. 501/demo copy must remain consistent with workbook demo markers and Summary status from 3.E.6/3.E.7.

### Amendments Applied

- AC3 explicitly preserves select values and detection logic.
- AC4 explicitly preserves download test IDs and `M2-M3` visibility.
- AC2/risks explicitly bind local-processing copy to current browser-side parser behavior.

### Round 1 Decision

PASS after amendments. Visible language can change, but data/status/contracts cannot drift.

---

## Story Review Round 2 - Function Consistency and Drift

### Findings

1. The story could become an i18n migration, but current Epic 3.E scope is Chinese-only Console Excel polish.
2. It could drift into changing `packages/ui` component API, which would affect other consumers.
3. It could duplicate loading components instead of reusing `LoadingShimmer`.

### Amendments Applied

- Scope explicitly says no i18n framework work or translation files.
- AC1 keeps `ExcelDropZone` API and reject contract unchanged.
- AC2 requires continued `LoadingShimmer` use and forbids fake percentages.

### Round 2 Decision

PASS after amendments. The story is a copy/state polish, not a component or architecture rewrite.

---

## Story Review Round 3 - Boundary, Edge Cases, and Closure

### Findings

1. Long filenames and high-row error states must remain readable after copy changes.
2. Download loading text is usually transient; tests should not become flaky by racing the download event.
3. Existing vertical slice must continue to pass even if exact button text changes.

### Amendments Applied

- AC5 preserves concrete recovery instructions for error states.
- AC6 keeps download verification event-based and only asserts loading copy where stable.
- Definition of Done requires both `console-excel.spec.ts` and 老张 vertical slice to pass.

### Round 3 Decision

PASS. Story is ready for dev.

## Final Story Status

`done`
