---
story_key: 3-e-8-zh-ux-friendly-voice
epic_num: 3.E
story_num: 3.E.8
epic_name: Console Excel Upload-Download UX
status: done
priority: 🟠 High (老张-2; converts the completed Excel arc from "functional" to consistently trustworthy)
sizing: S-M (~2-3 hours; copy audit + loading/progress polish + light motion + focused tests; no backend, no schema, no new dependency)
type: implementation + ux polish + test
created_by: bmad-create-story
created_at: 2026-05-24
sources:
  - _bmad-output/planning/epics.md:1467 (Epic 3.E goal: Console Excel upload-download UX for 老张)
  - _bmad-output/planning/epics.md:1500 (Story 3.E.8: 中文 UX 微调 Brand Voice 友好版)
  - _bmad-output/planning/epics.md:818 (老张-2: "已收到您的 Excel 文件" + 加载进度条 + Brand Voice)
  - _bmad-output/planning/prd.md:1292 (FR E11 Console Excel upload-download v1 end)
  - _bmad-output/planning/prd.md:1425 (老张 Excel surface maps to E11/E7/B1)
  - _bmad-output/planning/ux-design-specification.md:590 (Brand Voice base: 实证克制)
  - _bmad-output/planning/ux-design-specification.md:604 (M3 modifier: Console / Notification 友好不滥情)
  - _bmad-output/planning/ux-design-specification.md:614 (Console voice rule: factual success text, no over-celebration)
  - _bmad-output/planning/ux-design-specification.md:713 (Loading state taxonomy: skeleton/spinner/progress/optimistic)
  - _bmad-output/planning/ux-design-specification.md:2467 (老张 Console Excel flow)
  - apps/web/src/app/console/excel/page.tsx:73 (ReceivedCard current copy and parser loading state)
  - apps/web/src/app/console/excel/page.tsx:193 (DownloadResultCard current generation state)
  - apps/web/src/app/console/excel/page.tsx:263 (VRPTW preview state pattern)
  - apps/web/src/app/console/excel/page.tsx:510 (Schedule preview state pattern)
  - apps/web/src/app/console/excel/page.tsx:760 (Inventory preview state pattern)
  - e2e/tests/console-excel.spec.ts (existing full Excel arc browser coverage)
  - packages/ui/src/components/LoadingShimmer/index.tsx (existing loading primitive)
  - packages/ui/src/tokens.css:50 (global reduced-motion guard)
dependencies:
  upstream:
    - 3-e-1-excel-drop-zone (done) - `/console/excel` entry, ExcelDropZone, initial received/rejected states
    - 3-e-2-excel-task-type-detect (done) - parser/detection states and modal handoff
    - 3-e-3-vrptw-template (done) - VRPTW preview card and 501 path
    - 3-e-4-schedule-template (done) - Schedule preview card and 501 path
    - 3-e-5-inventory-template (done) - Inventory preview card and 501 path
    - 3-e-6-excel-result-download (done) - DownloadResultCard and xlsx export path
  downstream:
    - 3-e-9-laozhang-vertical-slice-e2e - should assert the polished end-to-end 老张 journey after this story
    - 3-e-7-excel-chart-embedding - may add chart-specific copy later; must follow this story's voice rules
---

# Story 3.E.8 - 中文 UX 微调 Brand Voice 友好版（老张-2）

## User Story

**As** 老张（制造排程工程师，Excel 是主工具，几乎不读 API 文档），
**I want** `/console/excel` 在上传、解析、确认、试跑、下载、错误恢复每一步都用清楚、克制、可操作的中文提示，
**so that** 我能判断系统当前在做什么、下一步该点哪里、失败时怎么修，而不会被英文术语、夸张语气或静默 loading 劝退。

## Why This Story

3.E.1-6 已经把 Excel arc 做通：上传、自动识别、3 个模板映射、501 友好卡、下载结果 Excel 都存在。现在的问题不是能力缺失，而是体验不均匀：

- 部分文本仍是工程内部术语，例如 `task_type`、`demo`、`M2-M3`、`501`。
- 加载态有 `LoadingShimmer`，但没有统一的阶段说明和进度感。
- 三个 preview card 的文案相似但不一致，后续 3.E.9 做完整老张 vertical slice 时会放大这种不一致。
- UX Spec 已明确 Console voice = "实证克制 + M3 友好不滥情"，要专业、直接、带下一步，不要像营销页。

这条 story 只做 polish，不扩功能。目标是把已经存在的 `/console/excel` 状态机整理成一致的产品语言和加载反馈。

## Out of Scope

- 不新增解析、检测、映射、求解或导出能力。
- 不改 `parseExcel`、`detectTaskType`、VRPTW/Schedule/Inventory mapper、`buildResultWorkbook` 的业务逻辑。
- 不新增后端接口、数据库、环境变量或运行时依赖。
- 不做 chart embedding，仍归 3.E.7。
- 不做完整老张 vertical slice E2E，仍归 3.E.9。
- 不引入 next-intl 或全站 i18n 框架；v1 保持中文硬编码，但要集中管理在本页面或小 helper，便于 1.10 接手。
- 不重构三个 preview card 为通用抽象；3.E.6 已记录这是未来候选，当前只做局部整理。

## Acceptance Criteria

### AC1: `/console/excel` has a small copy map for state text

In `apps/web/src/app/console/excel/page.tsx`, define a local copy map or a tiny helper module such as `apps/web/src/lib/excel-voice.ts`.

Preferred if only used by the page:

```ts
const EXCEL_COPY = {
  receivedTitle: "已收到您的 Excel 文件",
  parsing: "正在读取工作表和表头",
  detecting: "正在判断业务类型",
  // ...
} as const;
```

Requirements:

- Keep copy close to `/console/excel`; do not introduce a global i18n system.
- Replace repeated literal strings only when it improves consistency.
- Copy must follow "实证克制 + M3 友好不滥情":
  - Good: "已收到文件。正在读取工作表和表头。"
  - Good: "已识别为库存预测。请确认是否继续。"
  - Bad: "恭喜你太棒啦！"
  - Bad: "亲，马上为您处理哦。"
- Keep user-visible task names clear:
  - `vrptw` -> "车辆路径 / 时间窗"
  - `schedule` -> "排程"
  - `inventory` -> "库存预测"
  - `task_type` can remain only in code/JSON preview labels, not primary user guidance.

### AC2: Received and parsing state gives staged, concrete progress

Update `ReceivedCard` in `apps/web/src/app/console/excel/page.tsx`.

Current state:

- `StatusCard` title: "✅ 已收到您的 Excel 文件"
- Loading text: "解析中... 正在识别 task_type"
- two line shimmers

Target behavior:

- Keep `data-testid="excel-received-card"`.
- Title should be plain and factual: "已收到您的 Excel 文件".
- Description should include filename and size as today.
- The loading area should show 2-3 short stages. Example:
  - "1. 读取工作表"
  - "2. 识别表头"
  - "3. 判断业务类型"
- Use existing `LoadingShimmer`; optionally add a lightweight determinate-looking bar with CSS only.
- Avoid fake percentages unless tied to actual state. If a progress bar is visual only, copy must not claim an exact percent.
- `aria-live="polite"` or existing `StatusCard`/`LoadingShimmer` semantics must remain intact.

### AC3: Detection modal copy avoids raw implementation terms

Update `DetectedModal` copy in `apps/web/src/app/console/excel/page.tsx`.

Requirements:

- Modal title should be user-facing, not implementation-facing.
  - Prefer: `系统判断：排程`
  - Avoid: `自动检测：schedule`
- Confidence text remains visible but clearer:
  - Prefer: `判断可信度 82%`
  - Avoid only `可信度 82%` if the surrounding copy is unclear.
- Manual override label should avoid `task_type`:
  - Prefer: "不对？手动选择业务类型"
- Confirm/cancel labels should make the action clear:
  - Confirm: "确认并继续"
  - Cancel: "重新选择文件" or existing reset behavior if cancel resets.
- Do not change detection logic, confidence calculation, or option values.

### AC4: Template preview cards use consistent ready/loading/success/error copy

Apply a copy pass to the three preview cards in `apps/web/src/app/console/excel/page.tsx`:

- `VrptwPreviewCard`
- `SchedulePreviewCard`
- `InventoryPreviewCard`

Requirements:

- Parsing state:
  - Use one pattern across all three cards: "正在读取数据行..." is acceptable, but prefer task-specific second line such as "稍后会生成请求预览。"
  - Keep `LoadingShimmer variant="card"`.
- Ready state:
  - Include what was understood, with counts.
  - State the next action.
  - Example VRPTW: "已构建车辆路径请求 - 2 客户 / 1 车辆。可以先试跑，或查看 JSON 请求。"
- Invalid state:
  - Keep errors visible.
  - Tell user where to fix: "请在 Excel 中修正后重新上传。"
- 501 not-implemented state:
  - Keep honesty: current solver is not live.
  - Avoid raw `501` and avoid "即将上线" without context.
  - Recommended pattern: "这个模板已通过校验。当前版本返回演示结果；真实求解器将在 M2-M3 接入。"
- Solved state:
  - Include elapsed time and objective when available.
  - Do not over-celebrate; status icon is enough if kept.

### AC5: Download generation state is clearer and recoverable

Update `DownloadResultCard` in `apps/web/src/app/console/excel/page.tsx`.

Requirements:

- Button label while idle remains concise, e.g. "下载 Excel 结果".
- Button label while generating should be concrete:
  - Prefer: "正在生成 Excel..."
  - Avoid only "生成中..." if no context.
- Add `aria-busy={genState.kind === "generating"}` to the button or wrapper.
- Error text should be actionable:
  - Current fallback "下载失败" is too terse.
  - Prefer: "Excel 生成失败。请重新点击下载；如果仍失败，请重新上传文件。"
- Do not change `buildResultWorkbook` API or download event behavior.

### AC6: Light animation is added without creating visual noise

Add only small, purpose-bound motion to `/console/excel`.

Allowed:

- `motion-safe:transition`
- `motion-safe:animate-*` if already configured
- CSS-only subtle entrance on state cards
- progress shimmer or bar using existing Tailwind utilities

Not allowed:

- New animation library.
- Framer Motion.
- decorative orbs, blobs, gradients, or marketing-style hero treatment.
- animation that changes layout height after render.

Reduced motion must remain supported by existing `packages/ui/src/tokens.css` global media query. If custom animation classes are introduced, verify they are neutralized by that rule or guarded with `motion-safe:`.

### AC7: Existing E2E selectors and current Excel arc still pass

The implementation must preserve these selectors unless there is a strong reason and tests are updated in the same change:

- `excel-drop-zone`
- `excel-received-card`
- `confirmation-modal`
- `detection-confidence`
- `detection-override-select`
- `vrptw-preview-card`
- `schedule-preview-card`
- `inventory-preview-card`
- `vrptw-submit-button`
- `schedule-submit-button`
- `inventory-submit-button`
- `vrptw-501-card`
- `schedule-501-card`
- `inventory-501-card`
- `inventory-download-button`
- `excel-parse-error-card`
- `excel-reset-button`

Existing `e2e/tests/console-excel.spec.ts` should remain the primary smoke suite.

### AC8: Tests lock the new copy and loading expectations

Update browser or unit tests with focused assertions.

Minimum required:

- `e2e/tests/console-excel.spec.ts`:
  - received card contains "已收到您的 Excel 文件"
  - received/loading area contains at least two staged loading messages
  - detection modal uses "业务类型" instead of raw `task_type` in visible labels
  - download button generating state is still reachable through existing Inventory download test, or a smaller focused test if needed
- If extracting `EXCEL_COPY` to `apps/web/src/lib/excel-voice.ts`, add a small Vitest test that forbids banned phrases such as "亲", "恭喜", "太棒", and visible `task_type` in primary copy.

Do not over-test every string. Lock the user-facing patterns that prevent regression.

### AC9: Quality gates pass

Required gates:

- `pnpm --filter @opticloud/web test`
- `pnpm --filter @opticloud/web typecheck`
- `pnpm --filter @opticloud/ui test`
- `pnpm --filter @opticloud/ui typecheck`
- `pnpm --dir e2e exec playwright test tests/console-excel.spec.ts --project=chromium`

No Python service tests are expected because this story is front-end only. If implementation touches Python, treat that as scope creep and stop for review.

### AC10: Sprint tracking is bundled

- Update `_bmad-output/stories/sprint-status.yaml` from `3-e-8-zh-ux-friendly-voice: backlog` to `ready-for-dev` when this story is created.
- During implementation, move to `done` only after review and the gates above pass.
- Bundle sprint-status changes with the story/implementation commit; do not leave it as a follow-up.

## Tasks / Subtasks

- [x] Task 1: Copy audit and local copy map (AC: 1)
  - [x] Inventory every visible string in `/console/excel`.
  - [x] Create a local copy map or helper only if it reduces duplication.
  - [x] Remove raw implementation terms from primary user guidance.

- [x] Task 2: Received/loading state polish (AC: 2, 6)
  - [x] Update `ReceivedCard` title and loading text.
  - [x] Add staged loading messages.
  - [x] Keep `LoadingShimmer` and a11y semantics.
  - [x] Add only motion-safe, layout-stable visual polish.

- [x] Task 3: Detection modal copy (AC: 3)
  - [x] Reword modal title, confidence label, override label, and buttons.
  - [x] Keep detection option values and logic unchanged.

- [x] Task 4: Preview card copy pass (AC: 4)
  - [x] Apply consistent parsing, ready, invalid, 501/demo, solved, and retry copy to VRPTW.
  - [x] Repeat for Schedule.
  - [x] Repeat for Inventory.
  - [x] Keep JSON preview, submit, reset, and download behavior unchanged.

- [x] Task 5: Download generation state (AC: 5)
  - [x] Clarify generating label.
  - [x] Add `aria-busy`.
  - [x] Improve error text.

- [x] Task 6: Tests (AC: 7, 8)
  - [x] Update `e2e/tests/console-excel.spec.ts` assertions for received/loading/detection copy.
  - [x] Add a small Vitest copy guard only if a helper module is extracted.
  - [x] Preserve existing selectors and browser flow coverage.

- [x] Task 7: Quality gates and tracking (AC: 9, 10)
  - [x] Run the required gates.
  - [x] Record commands and outcomes in Dev Agent Record.
  - [x] Keep sprint-status update bundled.

### Review Findings

- [x] [Review][Patch] Download button accessible name must reflect generating state [apps/web/src/app/console/excel/page.tsx:320] — fixed by deriving the button label once and using it for both visible text and `aria-label`.
- [x] [Review][Patch] AC8 should lock the download generating state [e2e/tests/console-excel.spec.ts:385] — fixed by delaying the dynamic SheetJS chunk in the Inventory download E2E and asserting `正在生成 Excel...` plus `aria-busy="true"`.

## Dev Notes

### Implementation Guidance

- Primary file: `apps/web/src/app/console/excel/page.tsx`.
- Likely optional helper: `apps/web/src/lib/excel-voice.ts` only if page-local constants become noisy.
- Existing UI primitives are sufficient:
  - `StatusCard`
  - `LoadingShimmer`
  - `ConfirmationModal`
  - `ExcelDropZone`
- Do not add new dependencies.
- Do not alter API helpers or service URLs.
- Do not change the SheetJS export path in `apps/web/src/lib/excel-export.ts`.
- Keep JSON preview labels technical if needed; the restriction is on primary user guidance, not developer-oriented JSON content.

### Current State Map

The existing page state machine in `apps/web/src/app/console/excel/page.tsx`:

- `idle` -> `ExcelDropZone`
- `received` -> `ReceivedCard`, parse + detect
- `detected` -> `DetectedModal`
- `confirmed` -> one of the template preview cards
- `too_many_rows` -> `TooManyRowsCard`
- `parse_error` -> `ParseErrorCard`
- `rejected` -> `RejectedCard`

Do not introduce a parallel state machine. Polish the existing one.

### Voice Rules

Use this quick rubric for every visible string:

- factual first: what happened?
- concrete next: what can the user do?
- no patronizing words: "亲", "恭喜", "太棒", "马上为您"
- no unexplained raw implementation detail in primary copy: `task_type`, `501`, `demo_marker`
- emoji only as status shorthand if already present; do not add decorative emoji density
- numbers are useful when real: rows, file size, customer count, vehicle count, solve seconds

### Testing Notes

`e2e/tests/console-excel.spec.ts` already builds valid workbooks in memory using `xlsx`. Prefer extending those tests instead of adding fixture files.

Playwright drag-drop with File payload is intentionally avoided. Keep using:

```ts
await page.locator('input[type="file"]').setInputFiles({
  name: "vrptw.xlsx",
  mimeType: XLSX_MIME,
  buffer: VRPTW_BUFFER,
});
```

### Project Structure Notes

- Keep business page code under `apps/web/src/app/console/excel/page.tsx`.
- Keep generic UI primitives in `packages/ui` unchanged unless a tiny prop is clearly needed. This story should not require package-level component changes.
- If adding `apps/web/src/lib/excel-voice.ts`, keep it pure data/functions and no React imports.
- Do not create a new route.

### Previous Story Intelligence

From 3.E.6:

- The Excel export path is already complete and uses dynamic-imported `xlsx`.
- The three preview cards are repetitive by design; do not refactor them in this story.
- `summary` with `rows` is already held in state for the download path.
- The Inventory Playwright arc is the broadest coverage path and should remain the main smoke for download behavior.
- Sprint status must be bundled with the story/implementation commit.

From 3.E.1:

- `ExcelDropZone` and `FilePicker` already moved away from `alert()` to parent-controlled rejection handling.
- Rejection copy already has actionable hints. This story may polish wording but must not remove the hints or FAQ link.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Copy polish accidentally changes logic or selectors | Restrict edits to visible copy, CSS classes, and tests. Preserve data-testids listed in AC7. |
| "Friendly" becomes marketing-like | Apply the voice rubric: factual, direct, no hype, no patronizing terms. |
| Loading progress implies precision the app does not have | Use staged labels, not fake percentages. |
| Animation creates accessibility issues | Use existing `LoadingShimmer`, `motion-safe`, and the global reduced-motion guard. |
| Tests become too brittle by asserting every sentence | Assert key phrases and banned terms, not complete paragraphs. |
| Future i18n story has to unwind scattered strings | Use a small page-local copy map or helper for recurring copy. |

## Definition of Ready

- `/console/excel` exists and covers upload, detect, preview, submit, 501, parse error, too many rows, rejection, and download states.
- Existing `console-excel.spec.ts` covers the full arc and is the right place for browser assertions.
- UX Spec defines the voice rules and loading-state taxonomy.
- No backend dependency is needed.

## Definition of Done

- AC1-AC10 pass.
- Primary `/console/excel` copy follows "实证克制 + M3 友好不滥情".
- Received/loading state shows staged progress without fake precision.
- Detection modal avoids raw `task_type` in visible primary labels.
- VRPTW/Schedule/Inventory preview cards use consistent success, loading, error, demo, and solved copy.
- Download generation state is clear and accessible.
- Required gates pass.
- Dev Agent Record lists changed files and verification commands.

## References

- [Source: _bmad-output/planning/epics.md:1500]
- [Source: _bmad-output/planning/epics.md:818]
- [Source: _bmad-output/planning/prd.md:1292]
- [Source: _bmad-output/planning/ux-design-specification.md:590]
- [Source: _bmad-output/planning/ux-design-specification.md:614]
- [Source: _bmad-output/planning/ux-design-specification.md:713]
- [Source: apps/web/src/app/console/excel/page.tsx:73]
- [Source: apps/web/src/app/console/excel/page.tsx:193]
- [Source: e2e/tests/console-excel.spec.ts]
- [Source: packages/ui/src/components/LoadingShimmer/index.tsx]
- [Source: packages/ui/src/tokens.css:50]

## Three-Round Story Review

### Round 1: Data Consistency Review

Scope: copy map values, task labels, loading-stage text, download-state data, and E2E assertions.

Findings:

- [x] Task labels are consistent across detection modal and preview handoff: `vrptw` -> "车辆路径 / 时间窗", `schedule` -> "排程", `inventory` -> "库存预测", `lp` -> "线性规划".
- [x] Received/loading copy uses staged labels without fake percentages.
- [x] Download generation state uses the same label for visible text and accessible name.

Round 1 result: PASS; no story or code change required in this round.

### Round 2: Function Consistency / Drift Review

Scope: parser/detector/mapper/export functions versus story scope guards.

Findings:

- [x] `parseExcel`, `detectTaskType`, three mapper functions, `submitOptimizationDemo`, and `buildResultWorkbook` remain the source of truth; this story only changes copy, state presentation, and assertions.
- [x] Existing selectors listed in AC7 remain present.
- [x] No backend endpoint, schema, dependency, or global i18n framework was introduced.

Round 2 result: PASS; no story or code change required in this round.

### Round 3: Boundary / Closure Review

Scope: race conditions, a11y boundary, reduced-motion/noise boundary, and regression closure.

Findings:

- [x] Loading-stage assertions tolerate the fast parse path by keeping staged context visible once parsing completes.
- [x] Download generating state is explicitly reachable in E2E via delayed dynamic chunk route and checks `aria-busy="true"`.
- [x] Reduced-motion boundary is respected by using existing `motion-safe` utilities and `LoadingShimmer`.
- [x] Final verification remains the Story 3.E.8 gate set listed below and must be rerun after final bundle patches.

Round 3 result: PASS; proceed to final code review rerun.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-24 - Implemented `/console/excel` page-local copy map and business-facing task labels.
- 2026-05-24 - First Playwright run exposed a race where parsing completed before loading-stage assertions; kept the staged list visible as completed context behind the detection modal.
- 2026-05-24 - Normalized touched TypeScript files back to LF after `git diff --check` reported mixed line endings.
- 2026-05-24 - Code review found download button accessible-name drift during generation and missing AC8 coverage for generating state; both were patched.
- 2026-05-24 - Full post-review quality gates passed; story marked done.

### Completion Notes List

- Added `EXCEL_COPY`, `EXCEL_TASK_LABEL`, and small page-local helpers in `/console/excel` instead of introducing a global i18n system.
- Reworked received/parsing feedback to factual Chinese copy, staged progress text, `LoadingShimmer`, `aria-live`, and layout-stable `motion-safe` polish.
- Reworded detection modal, preview cards, demo-result states, solved states, LP fallback, and download generation/error states without changing parsing, mapping, submit, export, or selector behavior.
- Updated `console-excel.spec.ts` to lock the new received/loading/detection copy and download button accessibility expectations while preserving the existing Excel arc coverage.
- Kept copy constants inside `page.tsx`; no helper module was extracted, so the optional Vitest copy guard was not added.
- Resolved code review findings by syncing the download button accessible name with the visible generating label and adding a stable E2E assertion for the generating state.

### File List

- `apps/web/src/app/console/excel/page.tsx`
- `e2e/tests/console-excel.spec.ts`
- `_bmad-output/stories/3-e-8-zh-ux-friendly-voice.md`
- `_bmad-output/stories/sprint-status.yaml`

### Change Log

- 2026-05-24 - Story created and marked ready-for-dev.
- 2026-05-24 - Implemented Chinese UX/Brand Voice polish for `/console/excel`, updated focused E2E assertions, and marked story ready for code review.
- 2026-05-24 - Addressed code review findings for download accessibility and AC8 generating-state coverage.

### Verification

- `pnpm --filter @opticloud/web test` - passed (50 tests)
- `pnpm --filter @opticloud/web typecheck` - passed
- `pnpm --filter @opticloud/ui test` - passed (38 tests)
- `pnpm --filter @opticloud/ui typecheck` - passed
- `pnpm --dir e2e exec playwright test tests/console-excel.spec.ts --project=chromium` - passed (13 tests)
- `git diff --check` - passed
- Post-review rerun: all required gates passed again after review patches.
