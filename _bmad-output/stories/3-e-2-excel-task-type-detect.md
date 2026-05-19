---
story_key: 3-e-2-excel-task-type-detect
epic_num: 3.E
story_num: 3.E.2
epic_name: Console Excel Upload-Download UX
status: ready-for-dev
priority: 🟠 High (PMR6; continues 3.E pipeline from 3.E.1; opens routing to 3.E.3-5 templates)
sizing: M (~4-5 hours focused scope; lib install + parse module + heuristic detect + Confirm Modal + tests)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L391-392 (PMR6 — Excel→task_type detect)
  - _bmad-output/planning/epics.md L1476-1478 (Story 3.E.2 spec)
  - apps/web/src/app/console/excel/page.tsx (current 3.E.1 entry — File handoff to next story)
  - packages/ui/src/components/ConfirmationModal/index.tsx (existing Tier 1 modal — reused for confirm)
dependencies:
  upstream:
    - 3-e-1-excel-drop-zone (done) — Console route + File handoff via onFile
    - 0-9-ui-tier1-stubs (done) — ConfirmationModal in packages/ui
  downstream:
    - 3-e-3-vrptw-template + 3-e-4-schedule-template + 3-e-5-inventory-template — consume the detected task_type
    - 3-e-6-excel-result-download — round-trip uses the same parse output
    - 3-e-9-laozhang-vertical-slice-e2e — end-to-end uses this story's detect → template routing
---

# Story 3.E.2 — Excel → task_type Detection (PMR6)

## User Story

**As** 老张 (just dropped a .xlsx via 3.E.1),
**I want** the page to read my sheet names + first-row headers, recommend **what kind of optimization problem this looks like** (VRPTW / Schedule / Inventory / 通用 LP), and **ask me to confirm** with a one-click Modal before doing anything heavy,
**so that** I trust the system's judgment (it shows me WHY: "I saw sheets called 客户/车辆/时间窗 — looks like VRPTW") and I can override with "不对，我的是排班" before wasting compute.

## Why this story

3.E.1 only catches the File and shows a friendly "✅ 已收到". The placeholder text says "3.E.2 将自动识别 task_type". This is that story.

Two technical choices upfront:

### Tech choice 1: Where to parse — browser or backend?

**Decision: parse client-side in the browser.**

Reasoning:
- **Privacy (老张-specific concern)**: 制造业 .xlsx files routinely contain client names / pricing / labor cost. Uploading to a backend even for parse-only creates an audit / data-residency liability that we don't need until M3 sandbox-io is in place.
- **Latency**: Browser parse is instant for 5MB files (~100ms with `read-excel-file`). Round-trip would add ~300ms even on a fast LAN, ~1s on cell connections.
- **Backend complexity**: No new endpoint, no new auth path, no upload bandwidth budget needed.
- **Future migration**: `parseExcel()` is a pure function in `apps/web/src/lib/excel.ts`. If M3 needs server-side parse for chart embedding (3.E.7) or audit (8.A.4), we can swap implementations without changing call sites.

Trade-off accepted: bundle size grows by ~50KB gzipped (`read-excel-file` only).

### Tech choice 2: Which parser library?

Candidates:
- **`xlsx` (SheetJS)** — ~600KB unminified, ~200KB gzipped; full read/write; everyone knows it
- **`exceljs`** — ~1.5MB; richer (formulas, styles); overkill for our scope
- **`read-excel-file`** — ~50KB gzipped; read-only; minimal API; no formula/style support

**Decision: `read-excel-file`.**

Reasoning: this story only needs sheet names + first-row headers + maybe sample column types. `read-excel-file` does exactly that with the smallest footprint. When 3.E.6 needs WRITE for download (xlsx-style + chart embedding), we can switch to `xlsx` lazily for that route only. For now, save ~150KB on the most-trafficked landing page.

## Out of scope

- **Write Excel** (download path) → 3.E.6 + 3.E.7
- **Sandbox upload to backend** → M3 (sandbox-io / 3.E.6)
- **Full schema validation per template** → 3.E.3 (VRPTW) / 3.E.4 (Schedule) / 3.E.5 (Inventory) own the per-template schema mapping
- **Solving** → triggered by template stories after Confirm
- **Cell-level pattern detection** (currency, date format) — v1 uses sheet+header heuristics only; cell patterns deferred to 3.E.3-5 if needed
- **Multi-sheet alternative ranking** (e.g., "this could be VRPTW OR Schedule, here are both") — v1 returns ONE recommendation + offers manual override via a "其它" dropdown in the Confirm Modal
- **Internationalized headers** — current heuristics assume zh-CN headers per 老张 persona; English-header workbooks fall through to "通用 LP / 手动选择" — note in the Modal

## Acceptance Criteria

### AC1: `read-excel-file` installed in `apps/web`

`pnpm -C apps/web add read-excel-file` — verify package.json + lockfile updated. Bundle impact reported in build output.

### AC2: `apps/web/src/lib/excel.ts` — parse module

```ts
export interface ExcelSheetSummary {
  name: string;
  headers: string[]; // first non-empty row
  rowCount: number; // including header
}

export interface ExcelWorkbookSummary {
  sheets: ExcelSheetSummary[];
  totalRows: number; // sum across sheets, excluding headers
}

export async function parseExcel(file: File): Promise<ExcelWorkbookSummary>;
```

Implementation:
- Use `read-excel-file` lib; iterate `sheetNames`, parse each into rows, extract row[0] as headers
- Empty sheets → included with `rowCount: 0, headers: []`
- Throws `Error("workbook empty")` if 0 sheets

### AC3: `apps/web/src/lib/task-type-detect.ts` — heuristic detect

```ts
export type DetectedTaskType = "vrptw" | "schedule" | "inventory" | "lp" | "unknown";

export interface DetectionResult {
  taskType: DetectedTaskType;
  confidence: number; // 0..1
  reasoning: string; // zh-CN, 1-2 sentences for the Modal
  alternatives: DetectedTaskType[]; // sorted by score desc, excluding the winner
}

export function detectTaskType(summary: ExcelWorkbookSummary): DetectionResult;
```

Heuristics (sum scores per task_type, return max):

| Task | Sheet-name signals | Header-text signals | Score per match |
|---|---|---|---|
| **vrptw** | 客户 / 车辆 / 路线 / 时间窗 / customer / vehicle / route | 客户名 / 经度 / 纬度 / 需求 / 时间窗 / 服务时间 / lat / lng / lon / demand / time_window / service_time | 1.0 per sheet match; 0.5 per header match |
| **schedule** | 任务 / 资源 / 工序 / task / resource / shift | 任务名 / 工期 / 截止 / 资源 / 工序 / duration / deadline / resource / shift / employee | 1.0 / 0.5 |
| **inventory** | 出货 / SKU / 库存 / 季节 / sales / inventory | 日期 / SKU / 销量 / 库存 / 季节性 / date / qty / sales / stock / season | 1.0 / 0.5 |
| **lp** (fallback) | (any single-sheet workbook with mostly numeric column headers like x1, x2, c, A, b) | x / c / A / b | 0.3 — weak fallback |

Confidence = `winner_score / (winner_score + max(0.5, runner_up_score))` (squashed to [0.2, 1]). If `winner_score < 1.0` → return `unknown` with reasoning "未匹配到任何模板的特征 sheets / headers — 请手动选择".

Reasoning template: `检测到 ${matched_signals.join(" / ")} — 推荐 ${TASK_LABEL[winner]}`.

### AC4: Console page integration (state machine extension)

In `/console/excel/page.tsx`, extend the state machine added in 3.E.1:

```
idle → received (3.E.1)
received → detecting (call parseExcel + detectTaskType, replaces the 2s mock setTimeout from 3.E.1)
detecting → detected({summary, detection}) — show ConfirmationModal
detected → confirmed(taskType) — placeholder card "下一步：3.E.3-5 模板路由"
detected → cancelled — back to idle (with file kept? no — back to idle, drop file)
```

Replace the 2s `setTimeout` mock in `ReceivedCard` with a real call to `parseExcel(file)` then `detectTaskType(summary)`. On error (corrupt file / not xlsx despite the extension check from 3.E.1), show `<StatusCard variant="error" />` with "无法解析此文件" + retry button.

**50K row enforcement (FR E11)**: if `summary.totalRows > 50000`, render rejection card with "文件 X 行超过 50K 上限。请：① 按时间段拆分 ② 按地区/客户拆分 ③ 截取关键时段" (same actionable-hint pattern as 3.E.1 too_large).

### AC5: ConfirmationModal — recommendation + alternatives

Use the existing `ConfirmationModal` from `@opticloud/ui` (Tier 1, already shipped). Props:

- title: `自动检测：${TASK_LABEL[result.taskType]}`
- body: `<p>{result.reasoning}</p>` + 一个 "其它" dropdown listing the 4 alternatives + "确认" / "取消" buttons
- confidence indicator: small text "可信度 X%" (computed from result.confidence)

When confirmed: store `{taskType, file, summary}` in component state, render a "下一步：3.E.3 (VRPTW) 将在 PR #20+ 接管" placeholder card so the user sees the handoff but isn't dropped on a 404. data-testid="excel-confirmed-card".

If user picks "其它" alternative: override the taskType but keep the original reasoning visible ("您选择了 X，覆盖系统推荐 Y").

### AC6: Vitest — parse module + detect heuristics

Add `apps/web/src/lib/__tests__/excel.test.ts` (or just `excel.test.ts` sibling — match repo convention):

1. parse + detect VRPTW from synthesized workbook (build via `read-excel-file`-friendly fixture OR use a manually-constructed in-memory File)
2. parse + detect Schedule
3. parse + detect Inventory
4. unknown / no-match fallback returns `unknown` with reasoning explaining the absence
5. Confidence in `[0.2, 1]` for matched cases
6. Empty workbook throws `workbook empty`
7. `totalRows` sums correctly across sheets

**Decision: Option A — add Vitest to apps/web**. Reasoning:
- Files stay where they're used (`apps/web/src/lib/excel.ts`); no need to invent a new packages/ui surface for app-specific UI logic
- Setup is small (~30 min): copy `packages/ui/vitest.config.ts` + create `apps/web/src/lib/__tests__` dir + add `test` script + add devDeps (`vitest`, `@vitejs/plugin-react`, `@testing-library/react`, `happy-dom`)
- Establishes the apps/web test pattern for future Console pages (3.E.3/4/5 will all want unit tests for their template mappers)

Final paths:
- `apps/web/src/lib/excel.ts`
- `apps/web/src/lib/task-type-detect.ts`
- `apps/web/src/lib/excel.test.ts` (covers both)
- `apps/web/vitest.config.ts`

Vitest count (web + ui combined): 22 → **29** (+7 new tests in apps/web).

### AC7: Playwright E2E — real .xlsx fixture

Add to `e2e/tests/console-excel.spec.ts`:

1. `test("拖入 VRPTW workbook → 显示 confirm modal + 推荐 vrptw")` — `setInputFiles` with a Buffer of a real .xlsx generated inline via Node-side `xlsx` lib in a beforeAll hook (e2e is Node, can use `xlsx` for fixture generation without bundle cost). After upload, expect Modal visible, contains "VRPTW", contains "确认".
2. `test("点击确认 → 展示 placeholder handoff card")` — sequel to #1; click "确认"; expect `getByTestId("excel-confirmed-card")` with `vrptw` text.
3. `test("点击 '其它' 切换到 schedule → 确认后 handoff 展示 schedule")` — sequel; select alternative; assert override applied.
4. `test("解析失败的文件显示 error StatusCard")` — `setInputFiles` with a 200-byte garbage Buffer naming it `.xlsx` (passes 3.E.1 size + suffix checks but fails parse); expect parse-error card visible.
5. `test(">50K rows 文件触发 50K rejection card")` — generate workbook with 50001 rows via inline xlsx in beforeAll; expect rejection card "超过 50K 上限".

Playwright total: 15 → **20** (+5). Note: tests #1, #2, #3, #5 share a beforeAll that pre-builds the fixtures via the `xlsx` npm package (added to `e2e/package.json` devDeps — keeps it out of the web bundle).

### AC8: 50K-row enforcement

After `parseExcel(file)`, if `summary.totalRows > 50000`:
- Skip detect entirely
- Render rejection card (variant="warning") — title "文件行数过多", description `共 ${totalRows} 行 > 50,000 行上限`, three actionable bullets, plus the `/docs/excel-upload-faq` link
- "重试" button returns to idle

The 5MB size cap stays in 3.E.1 (component); the 50K row cap is owned here in the page (parse is needed to know rows). This is what FR E11 means by "≤5 MB / 50K rows".

### AC9: Quality gates

- `uv run ruff check apps packages` → 0 (no Python changes)
- `uv run ruff format --check apps packages` → 0
- `uv run mypy apps packages` → 0
- `pnpm -C apps/web build` → 0 (bundle delta reported in PR)
- `pnpm -C apps/web typecheck` → 0
- `pnpm -C e2e typecheck` → 0
- `pnpm -C packages/ui test` → 29 passing (was 22; +7), 12 pre-existing a11y fails unchanged
- `pnpm -C packages/ui typecheck` → only pre-existing 3 errors (test-setup + useA11y.test, unrelated)

### AC10: NFR alignment

- **FR E11** ✅ 50K rows now enforced (this story) on top of 5MB size (3.E.1) → both v1 limits live
- **PMR6** ✅ task_type detect heuristics shipped
- **Privacy** ✅ Client-side parse — no .xlsx ever uploaded to backend in 3.E surface
- **NFR-A1** ConfirmationModal already a11y-audited (Story 0.12); confidence text uses aria-live="polite"
- **NFR-S** No new backend; no auth/SSRF concerns
- **NFR-P1** Parse is sync-in-worker-equivalent (~100ms for 5MB on average laptop); UI shows a real `LoadingShimmer` during parse

## Tasks

### T1 — Move 3.E.1 mock + install lib (0.3h)
1. `pnpm -C apps/web add read-excel-file`
2. `pnpm -C e2e add -D xlsx` (for fixture generation in beforeAll)
3. Verify lockfile changes

### T2 — packages/ui lib modules (0.7h)
1. `packages/ui/src/lib/excel.ts` — `parseExcel()` + types per AC2
2. `packages/ui/src/lib/task-type-detect.ts` — `detectTaskType()` per AC3
3. Re-export from `packages/ui/src/index.ts`
4. The lib `read-excel-file` is added to `apps/web` only (where the parser runs in-browser); packages/ui imports it as a peer/devDep but the actual import is conditional… **simpler approach**: add `read-excel-file` to `packages/ui` package.json. It's transitively used by web anyway.

### T3 — Vitest tests (0.8h)
1. `packages/ui/src/lib/excel.test.ts` — 7 cases per AC6
2. Fixture workbook construction: use `xlsx` package on the **test side only** (devDep of `packages/ui`) to build small in-memory workbooks, write to a Buffer, then `new File([buffer], "test.xlsx")` for `parseExcel`. This mirrors what e2e will do.

### T4 — Console page state machine + Modal (1.5h)
1. Refactor `/console/excel/page.tsx` per AC4 — replace `ReceivedCard`'s `setTimeout` mock with real parse + detect
2. Add `ConfirmationModal` rendering on `detected` state per AC5
3. Add 50K-row rejection branch per AC8
4. Add `excel-confirmed-card` for the handoff placeholder

### T5 — Playwright E2E + fixtures (1h)
1. Add 5 tests per AC7
2. `beforeAll` hook in `e2e/tests/console-excel.spec.ts` uses `xlsx` to build in-memory .xlsx Buffers
3. Use `setInputFiles({name, mimeType, buffer})` pattern (already proven in 3.E.1 tests)

### T6 — Quality gates + sprint sync + PR (0.5h)

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `read-excel-file` bundle weight (~50KB gzipped) | Reported in PR description; acceptable for the /console/excel route (lazy-load is a v2 optimization if user complains) |
| Heuristics false-positive (e.g., a sheet named "客户预测" goes to VRPTW when it's actually inventory) | ConfirmationModal AC5 shows the reasoning AND offers manual override via "其它" dropdown — user always has the wheel |
| Workbook with empty first row but data starting at row 2 | `parseExcel` heuristic skips empty rows to find first non-empty as headers; document in JSDoc |
| Web page now imports a lib that's only used on /console/excel — bundle bloat on other routes | Next.js code-splits by route; `read-excel-file` only loads when `/console/excel` is navigated to. Verified via Next build output route-by-route sizes |
| `xlsx` devDep in `e2e/` may slow CI install | xlsx is ~1MB total; pnpm install delta < 2s; acceptable |
| Move `parseExcel` to packages/ui — circular concern (packages/ui imports lib only meant for browser) | `read-excel-file` IS browser-runtime; works in Node too (via blob polyfill). Plays well with `happy-dom` (vitest env in packages/ui). Verified locally in T3. |
| Modal-then-handoff UX: user clicks Confirm but next-story handoff is just a placeholder card → feels broken | Placeholder copy is explicit: "下一步：3.E.3-5 模板路由" + visible task_type → user sees the system understood; no false promise |
| Heuristic returns "unknown" for English-header workbooks | Documented out-of-scope; Modal shows "未匹配 — 请手动选择 task_type" with the dropdown enabled. AC3 covers this branch |
| .xlsx with formulas evaluating to empty → headers seem empty | `parseExcel` reads cell `value` (not formula); read-excel-file already returns the cached value. If cell is uncached, falls through to empty + downstream heuristic catches it |

## Definition of Ready

- ✅ 3.E.1 shipped — File handoff exists
- ✅ ConfirmationModal in packages/ui
- ✅ Vitest infra in packages/ui (3.E.1 added 9 tests successfully)
- ✅ Playwright xlsx fixture pattern proven (3.E.1 used Buffer.alloc for size tests; this story extends with real xlsx Buffers)

## Definition of Done

- 10 ACs pass
- Vitest 22 → 29 (+7); Playwright 15 → 20 (+5); solver tests unchanged (no Python this story)
- CI all green
- sprint-status: `3-e-2-excel-task-type-detect: done`
- Memory updated
- Manual smoke: drop a VRPTW-ish .xlsx → Modal shows "推荐 vrptw" + reasoning → confirm → handoff card visible

## Sign-off

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| 3.E Lead | TBA | ☐ | — |
| UX 老张 | TBA | ☐ | — |
| FE Lead | TBA | ☐ | — |

> Owner committee deferred per M0 skip.
