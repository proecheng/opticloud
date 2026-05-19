---
story_key: 3-e-6-excel-result-download
epic_num: 3.E
epic_name: Console Excel Upload-Download UX
story_num: 3.E.6
status: ready-for-dev
priority: 🟠 High (closes upload→solve→download Excel arc; first non-stub Epic 3.E story; ~3-4h)
sizing: M (~3-4 hours; pure FE — exporter util + Vitest + 3-card wiring + 1 Playwright; backend untouched)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L1492-1494 (Story 3.E.6 spec — input sheets + results + summary stats + chart-later)
  - _bmad-output/stories/3-e-5-inventory-template.md (predecessor — InventoryPreviewCard shape; excel-helpers refactor)
  - _bmad-output/stories/3-e-3-vrptw-template.md (original /demo route + parseExcel includeRows)
  - apps/web/src/app/console/excel/page.tsx L187-854 (3 preview cards — Vrptw / Schedule / Inventory; all hit `submitState.kind === "not_implemented"` path today)
  - apps/web/src/lib/excel.ts L7-9 (the design note that anticipated this exact story: "If we ever need WRITE (download path 3.E.6) we'll add `xlsx` (SheetJS) on the download route only")
  - apps/web/package.json L26-39 (`xlsx ^0.18.5` already in devDependencies — needs promotion to dependencies for runtime use)
  - apps/web/src/lib/vrptw-template.ts + schedule-template.ts + inventory-template.ts (mappers produce structured payloads — exporter reads these)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py L461-567 (/v1/optimizations/demo — LP returns 200 with solution; non-LP returns 501 with friendly detail)
dependencies:
  upstream:
    - 3-e-5-inventory-template (done, PR #23) — closes the template trilogy; 3.E.6 builds the download surface on top of all 3 cards
    - 3-e-3-vrptw-template (done, PR #21) — `/v1/optimizations/demo` route + parseExcel `{includeRows}` flag
    - 3-e-2-excel-task-type-detect (done, PR #20) — `ExcelWorkbookSummary` shape with optional `rows: unknown[][]`
  downstream:
    - 3-e-7-excel-chart-embedding (v1 末) — extends exporter with chart sheets
    - 3-e-8-zh-ux-friendly-voice — Brand Voice polish across all 3.E surfaces
    - 3-e-9-laozhang-vertical-slice-e2e — needs the full upload→solve→download arc, which this story closes
    - Story 3.2 prediction backend (M2-M3) — when real solvers land, the "demo result" copy auto-clears (real solution surface)
---

# Story 3.E.6 — Excel Result Download (FR E11, closes upload→download arc)

## User Story

**As** 老张 (just clicked 试跑 on /console/excel and got the friendly "M2-M3" 501 card OR — when LP eventually has its own preview card — a real solve result),
**I want** to click a **"📥 下载 Excel 结果"** button and get back an `.xlsx` workbook that contains: my original input sheets (so I have a single file with input+output), a **results sheet** with either the real solution OR a clearly-labeled mock placeholder, and a **summary stats sheet** (counts, timing, status),
**so that** I can take the result back to my team in the SAME tool they sent it to me in (Excel) — no copy-paste, no API call, no "where did the input go?". And when real solvers land in M2-M3, the same button keeps working — the only change is that the results sheet fills with real numbers instead of placeholders.

## Why this story

3.E.1-5 shipped the **upload + detect + preview + 试跑** half of the Excel arc. Three preview cards (VRPTW / Schedule / Inventory) all wire `submitOptimizationDemo` → 501 friendly card (today; M2-M3 will be 200 real-solve for those task_types). 3.E.6 closes the **other half** — the artifact 老张 actually shows to their boss/team.

What this story DOES:
1. Promote `xlsx` (SheetJS) from devDep → runtime dep on `apps/web`
2. Build a pure utility `apps/web/src/lib/excel-export.ts` — `buildResultWorkbook({sourceFile, taskType, payload, result}) → Promise<Blob>`
3. Generate three sheets:
   - **Input — Sheet1, Input — Sheet2, ...** — copies of the user's original sheets (preserves what they sent)
   - **Results** — either real solution (when LP path 200) OR clearly-labeled mock rows (when 501; one row per primary entity with placeholder values + 🚧 marker)
   - **Summary** — counts (from the mapper result like `customer_count`), submitted-at timestamp, status (`solved` / `demo (M2-M3 待上线)`), task_type, demo flag
4. Add a **DownloadResultCard** subcomponent inside each of the 3 preview cards — visible when `submitState.kind === "not_implemented"` OR `"solved"`; triggers download via `URL.createObjectURL(blob)`
5. Use **dynamic `import('xlsx')`** so the writer code only ships when the user clicks download (preserves landing-bundle weight; see excel.ts:7-9 design note)
6. Vitest unit tests for the exporter (verify sheet names, row counts, mock-vs-real branch)
7. One Playwright E2E walking the full arc on one task type (Inventory chosen — predicates: largest payload + 3 sheets + already has 501 card test from 3.E.5)

What this story does NOT do:
- **Chart embedding** — Story 3.E.7 (v1 末)
- **Server-side Excel generation** — explicitly client-side per the privacy posture (file never leaves browser; 3.E.1-2 design)
- **Real solver results for non-LP** — they 501 today; M2-M3 backend will fill in
- **An LP preview card** — currently LP falls through to placeholder `excel-confirmed-card` (no submit/download surface). LP-specific UI would be a separate v1 polish; 3.E.6 supports all 3 EXISTING preview cards uniformly
- **Per-task-type results schema** — v1 uses ONE flexible shape (rows = primary entities; columns = key fields + mock values). M2-M3 will define real-output shapes per task_type.
- **i18n / English copy** — Chinese only (matches 3.E.1-5; 3.E.8 will polish)
- **Print / PDF export** — out of scope

Per memory `feedback_actionable_work`: closes a complete user-visible arc (upload → result file) in one story; doesn't wait on M2-M3 backend. Mock-result transparency makes the demo nature explicit so users aren't misled.

## Out of scope

- Chart embedding (3.E.7)
- LP-specific preview card / download
- Real solver implementations
- Server-side generation
- Sheet styling / colors / merged cells (plain text/number cells only)
- Conditional formatting / row highlighting
- File size cap on output (input cap is 50K rows = 3.E.2; output is bounded by input)
- "Save to cloud" / multi-format export (CSV / JSON)

## Acceptance Criteria

### AC1: Promote `xlsx` to runtime dependency

`apps/web/package.json`:
- Remove `xlsx` from `devDependencies`
- Add to `dependencies` at same version `^0.18.5`
- Run `pnpm install` to update lockfile

**Why dep, not devDep**: `xlsx` is now imported at runtime in the browser (download trigger). It was devDep previously because only Playwright test fixtures used it. The Next.js build will tree-shake unused parts; dynamic `import()` (AC4) ensures the ~600KB minified bundle only loads when the user clicks download.

### AC2: New module `apps/web/src/lib/excel-export.ts`

Pure utility (no side effects until called):

```ts
import type { ExcelWorkbookSummary } from "./excel";
import type { VrptwPayload } from "./vrptw-template";
import type { SchedulePayload } from "./schedule-template";
import type { InventoryPayload } from "./inventory-template";

export type ExportablePayload = VrptwPayload | SchedulePayload | InventoryPayload;

export type ExportResultStatus = "solved" | "demo";

export interface ExportRequest {
  /** User's original workbook summary (with rows from `parseExcel(file, {includeRows: true})`). */
  source: ExcelWorkbookSummary;
  /** The mapper-built payload (any of the 3 templates). */
  payload: ExportablePayload;
  /** "solved" when backend returned 200 + solution; "demo" when 501 (mock placeholder). */
  status: ExportResultStatus;
  /** Optional: real solve result (objective + solve_seconds). Required when status="solved". */
  realResult?: {
    objective: number | null;
    solveSeconds: number;
    solution?: { x?: number[] } | null;
  };
  /** ISO timestamp; defaults to new Date().toISOString(). */
  submittedAt?: string;
}

export interface ExportedWorkbook {
  blob: Blob;
  /** Suggested filename: `opticloud_{taskType}_{YYYYMMDD_HHmmss}.xlsx` (UTC). */
  filename: string;
  /** Sheet names actually written (useful for tests). */
  sheetNames: string[];
}

export async function buildResultWorkbook(req: ExportRequest): Promise<ExportedWorkbook>;
```

**Implementation strategy**:
- Top of function: `const XLSX = await import("xlsx");` — dynamic load
- `wb = XLSX.utils.book_new()`
- For each source sheet: `XLSX.utils.aoa_to_sheet(rows)` + `XLSX.utils.book_append_sheet(wb, sheet, "输入 — {name}")` (prefix to disambiguate from result sheets)
- Results sheet via `XLSX.utils.aoa_to_sheet([[...headers], ...dataRows])`
- Summary sheet via simple 2-column key/value matrix
- `const wbBlob = new Blob([XLSX.write(wb, {type: "array", bookType: "xlsx"})], {type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})`
- Filename suffix uses UTC to avoid TZ surprises across users

**Sheet name length cap**: Excel limits sheet names to 31 chars. Source sheet prefix "输入 — " is 4 chars; truncate `name` to 27 chars if needed. Document in code comment.

### AC3: Results sheet structure (per task_type)

The Results sheet header + rows depends on `payload.task_type`. v1 schema:

#### VRPTW Results (mock when status="demo")
| route_id | vehicle_id | stop_sequence | customer_id | arrival_time | departure_time | demand_served | demo_marker |
|---|---|---|---|---|---|---|---|
| ROUTE-001 | V1 | 1 | (first customer.id from payload) | 08:00 | 08:15 | (first customer.demand) | 🚧 mock (M2-M3) |
| ... | | | | | | | |

For demo: emit ONE row per customer (sequenced into pseudo-routes). Real solve (future M2-M3): the actual route plan.

#### Schedule Results
| task_id | resource_id | start_time | end_time | duration | demo_marker |
|---|---|---|---|---|---|
| (first task.id) | (first resource.id) | 0 | (task.duration) | (task.duration) | 🚧 mock (M2-M3) |
| ... | | | | | |

For demo: emit one row per task, assigning task[i] → resource[i % len(resources)] with serial start times.

#### Inventory Results
| sku | period | forecast_p10 | forecast_p50 | forecast_p90 | demo_marker |
|---|---|---|---|---|---|
| (first sku) | 2026-01 | 80 | 100 | 120 | 🚧 mock (M2-M3) |
| ... | | | | | |

For demo: 1 row per SKU at a single forecast period; numbers are deterministic placeholders (e.g., based on mean of qty in history).

When `status === "solved"` AND `payload.task_type === "lp"` (hypothetical future): emit `realResult.solution.x` into a single column. **NOTE**: today no preview card hits this path because LP has no preview card. Tests cover demo path only; real-result path is covered by the type contract.

### AC4: Summary sheet structure

Always 2 columns: Key | Value. Rows:

| Key | Value |
|---|---|
| task_type | (e.g. "vrptw") |
| status | "solved" / "demo (M2-M3 待上线)" |
| submitted_at | (ISO timestamp) |
| source_filename | (e.g. "我的VRPTW.xlsx" — sanitized for sheet display) |
| source_total_rows | (sum across input sheets) |
| primary_count | (customer_count / task_count / sku_count from mapper result) |
| secondary_count | (vehicle_count / resource_count / history_count) |
| objective_value | (realResult.objective ?? "(demo)") |
| solve_seconds | (realResult.solveSeconds ?? "(demo)") |
| generated_by | "OptiCloud /console/excel (3.E.6)" |
| generated_at | (new Date().toISOString()) |

Sheet name: "Summary"

### AC5: Console page integration — DownloadResultCard

In `apps/web/src/app/console/excel/page.tsx`:

1. New subcomponent `DownloadResultCard`:

```tsx
function DownloadResultCard<
  TPayload extends ExportablePayload,
>(props: {
  taskType: "vrptw" | "schedule" | "inventory";
  source: ExcelWorkbookSummary;
  payload: TPayload;
  status: ExportResultStatus;
  realResult?: ExportRequest["realResult"];
  dataTestId: string;
}): JSX.Element;
```

UI:
- 1 button: "📥 下载 Excel 结果"
- `data-testid={props.dataTestId}` (e.g. `inventory-download-button`)
- onClick: dynamic-import the export util → call `buildResultWorkbook` → create object URL → trigger `<a>` click → revoke URL
- While generating: button shows "生成中..." + disabled
- On error: small inline error text below button

2. Wire into each of the 3 preview cards:
   - VrptwPreviewCard: after the 501-or-solved StatusCard, render `<DownloadResultCard taskType="vrptw" source={summary} payload={result.payload} status={submitState.kind === "solved" ? "solved" : "demo"} dataTestId="vrptw-download-button" />` — but ONLY when submitState ∈ {solved, not_implemented}
   - Same for Schedule + Inventory cards
   - Need to keep `summary` in scope — currently the preview cards re-parse via parseExcel internally; refactor: store `summary` in state, pass through.

3. Subtle: the 3 preview cards each store `summary` returned from `parseExcel(file, {includeRows: true})` in their `state.kind === "mapped"` variant. Extend the `mapped` state shape to also carry `summary` so DownloadResultCard can read it.

### AC6: Filename + accessibility

- Default filename: `opticloud_{taskType}_{YYYYMMDDTHHmmssZ}.xlsx` (UTC; safe for all OS filesystems)
- Trigger: programmatic `<a download={filename}>` click (no native file picker — instant download per browser default behavior)
- Aria: `aria-label` on button mirrors the visible text + status
- Status announcement: when download completes, no toast needed (browser shows its own download indicator)

### AC7: Vitest — exporter util

New `apps/web/src/lib/excel-export.test.ts` — 6 cases:

1. `buildResultWorkbook — VRPTW demo: produces blob with input sheets + Results + Summary; Results row count = customer_count; demo_marker present`
2. `buildResultWorkbook — Schedule demo: Results row count = task_count; resource assigned by modulo`
3. `buildResultWorkbook — Inventory demo: Results row count = sku_count; forecast columns present`
4. `buildResultWorkbook — solved status: Summary objective_value reflects realResult.objective` (synthetic test — passes realResult; covers the type contract even though no live UI path hits this today)
5. `buildResultWorkbook — sheet name truncation: source sheet with 50-char name truncates to fit Excel's 31-char cap (with prefix); no crash`
6. `buildResultWorkbook — filename format: matches `opticloud_{taskType}_YYYYMMDDTHHmmssZ.xlsx` pattern`

Pattern: parse the resulting Blob back via `xlsx.read` (CI Node has Buffer; tests run with happy-dom + vitest already configured). Verify `wb.SheetNames` includes prefixed input sheets + "Results" + "Summary".

apps/web Vitest: **31 → 37** (+6).

### AC8: Playwright E2E — full arc on Inventory

In `e2e/tests/console-excel.spec.ts`, new test:

```ts
test("Inventory: 试跑 → 501 friendly card → 下载 Excel 结果 → file downloaded", async ({ page }) => {
  // 1) Build inventory .xlsx fixture in-memory (reuse 3.E.5 fixture pattern)
  // 2) Upload, confirm "Inventory", click 试跑
  // 3) Expect inventory-501-card visible
  // 4) Click inventory-download-button
  // 5) Expect download event triggered (page.waitForEvent("download"))
  // 6) Save downloaded file to temp; verify it's non-empty + filename matches opticloud_inventory_*.xlsx
});
```

Playwright total: ~22 → **23** (+1).

### AC9: Quality gates

Per `feedback_full_quality_gates`:
- `pnpm install` (lockfile updated for xlsx dep promotion)
- `pnpm -C apps/web typecheck`
- `pnpm -C apps/web test` (37 passing; +6 over baseline 31)
- `pnpm -C apps/web build` (Console route bundle measurement — should grow ~1-2 KB; xlsx itself loads dynamically so doesn't count toward initial chunk)
- `pnpm -C packages/ui test` (22 baseline preserved; no UI package change)
- `uv run ruff check .` + `ruff format --check .` (Python untouched but run anyway for hygiene)
- `uv run mypy apps packages` (Python untouched but verify)

### AC10: NFR alignment

- **FR E11** ✅ — Excel surface UX advances; closes upload→download arc
- **NFR-S** — exporter is pure client-side; file never leaves browser
- **NFR-P1** — dynamic import means xlsx (~600KB) doesn't bloat initial bundle; `/console/excel` initial chunk grows only by the small wrapper code
- **PMR6** ✅ — closes the user-visible loop the trilogy opened
- **CRG13** — tutorial link in faq stub stays; no new doc required for v1

## Tasks

### T1 — Promote `xlsx` to runtime dep + lockfile (0.1h)
1. Edit `apps/web/package.json`: move `xlsx` from devDependencies → dependencies
2. `pnpm install` (regenerates lockfile)
3. Verify `pnpm -C apps/web build` still passes

### T2 — Exporter util module (0.8h)
1. Create `apps/web/src/lib/excel-export.ts` per AC2/3/4
2. Use dynamic `import("xlsx")` at top of `buildResultWorkbook`
3. Implement per-task-type Results shape (3 branches)
4. Implement Summary sheet (deterministic key/value rows)
5. Implement filename helper

### T3 — Exporter Vitest (0.4h)
1. Create `apps/web/src/lib/excel-export.test.ts` with 6 cases per AC7
2. Verify can `xlsx.read(arrayBuffer)` back in happy-dom env

### T4 — DownloadResultCard subcomponent + 3 wirings (0.8h)
1. Add `DownloadResultCard` to `console/excel/page.tsx`
2. Refactor the 3 preview cards: `state.kind === "mapped"` variant carries `summary`
3. Render DownloadResultCard inside each card when `submitState ∈ {solved, not_implemented}`
4. Verify data-testids match AC5

### T5 — Playwright E2E (0.5h)
1. Add Inventory download test per AC8
2. Use `page.waitForEvent("download")` pattern
3. Save fixture to temp; assert non-empty + filename match

### T6 — Quality gates + bundled sprint-status + PR (0.5h)
1. Run all gates per AC9
2. **Bundle sprint-status update INTO this PR's commit** (lesson from 2.5/PR#26: don't ship sprint-status as follow-up)
3. Open PR; CI watch via background `gh pr checks N --watch`; merge after green

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `xlsx` (SheetJS) bundle is large (~600 KB minified) — could regress landing performance | Dynamic `import("xlsx")` inside `buildResultWorkbook` ensures it ships in a separate chunk that loads only on download click. `/console/excel` initial JS stays small. Verify via `pnpm build` output; bundle size of /console/excel route should grow ≤2 KB. The `xlsx` chunk loads as needed. |
| Dynamic import in a server component / static page causes build issues | The DownloadResultCard is inside the existing `"use client"` page; dynamic import is client-side only. No SSR path executes `xlsx`. Verified by AC9 build pass. |
| User's source sheet has unusual cell types (dates, formulas, errors) — `aoa_to_sheet` may serialize oddly | Per AC2: pass `summary.sheets[i].rows` (already-parsed `unknown[][]` from 3.E.2's parseExcel) directly. Cells are already coerced to JS primitives (number/string/Date/null) by read-excel-file. Edge: Date values may export as ISO string rather than Excel date number; acceptable for v1 (round-trip preservation is not the goal — readability is). |
| Sheet name collisions: user has a sheet literally named "Results" or "Summary" | We prefix INPUT sheets with "输入 — " precisely to avoid this. Results + Summary are reserved. If user's input had "输入 — XXX" already? Extreme edge; truncation may produce identical names — handle by appending " (2)" suffix on duplicate. Document the rule in code. |
| Filename special chars (Chinese characters, slashes) break OS download | Filename uses `opticloud_{taskType}_{ISO_UTC}.xlsx` — all ASCII safe. We do NOT embed the source filename. |
| Excel sheet name 31-char cap violation crashes write | Truncate input sheet names to 27 chars (4 reserved for "输入 — " prefix). Cap-truncation test in AC7 #5. |
| Mock results misleading users into thinking it's a real solve | Two safeguards: (1) "demo_marker" column in every results row with `🚧 mock (M2-M3)` literal; (2) Summary sheet's `status` row says `"demo (M2-M3 待上线)"` explicitly. Both fire automatically when status="demo". UI download button copy NOT modified (keeps the button neutral — context is in the file). |
| User runs out of memory on large workbooks (write-side) | 50K-row cap from 3.E.2 already constrains input. xlsx write is in-memory but bounded. v1 acceptable. |
| Bundle promotion (devDep→dep) could affect `pnpm install --frozen-lockfile` in CI | The lockfile change is part of this PR; CI's `pnpm install --frozen-lockfile` will succeed against the updated lock. Verified locally first. |
| Bundle promotion drops a different package version into the dep tree, breaking Playwright fixture builds | `xlsx` stays at same version `^0.18.5`. Playwright already imports from it; behavior identical post-promotion. |
| Storing `summary` (with `rows: unknown[][]`) in preview-card state increases React state size for large workbooks | The summary is already held in memory during the mapper call (`buildXyzPayload(summary)`); reusing the existing reference, not duplicating. Net zero. |

## Definition of Ready

- ✅ 3.E.5 shipped (closes preview trilogy; all 3 cards exist with submit + 501)
- ✅ `xlsx` already in devDeps at right version
- ✅ `ExcelWorkbookSummary` already carries optional `rows` field
- ✅ All 3 mapper modules export typed payloads (VrptwPayload / SchedulePayload / InventoryPayload)
- ✅ `/v1/optimizations/demo` route + 501 path established
- ✅ apps/web Vitest infra
- ✅ Playwright fixture pattern for Inventory exists (3.E.5)

## Definition of Done

- 10 ACs pass
- xlsx promoted to dep; pnpm-lock.yaml updated
- `excel-export.ts` + tests landed; 31 → 37 Vitest
- 3 preview cards each show download button on `solved` or `not_implemented` state
- Playwright Inventory download arc test passes
- CI all green
- **sprint-status update bundled INTO this PR's commit (not follow-up)**
- Manual smoke: drop Inventory .xlsx → confirm → 试跑 → 501 card → click download → file appears named `opticloud_inventory_*.xlsx` with 3+ sheets (Input — *, Results, Summary)

## Sign-off

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| 3.E Lead | TBA | ☐ | — |
| Frontend Lead | TBA | ☐ | — |

> Owner committee deferred per M0 skip.

---

## Round 1: BMad Checklist Review

| # | Item | Status | Note |
|---|---|:-:|---|
| 1 | User story has As/I want/so that | ✅ | 老张 persona; explicit "demo vs real solve" framing |
| 2 | ACs testable & BDD-shaped | ✅ | Each AC has concrete signatures or sheet specs |
| 3 | Scope explicit (in/out) | ✅ | Charts (3.E.7), LP card, server-side gen, real solvers all explicitly out |
| 4 | Dependencies declared | ✅ | upstream 3.E.5 / 3.E.3 / 3.E.2; downstream 3.E.7 / 3.E.8 / 3.E.9 / 3.2 |
| 5 | Sizing estimate | ✅ | M (~3-4h); breakdown adds to ~3.1h per Tasks |
| 6 | Risks identified with mitigations | ✅ | 10 risks; each has concrete mitigation |
| 7 | Quality gates listed | ✅ | AC9 — all 7 commands |
| 8 | Test plan | ✅ | 6 Vitest + 1 Playwright + manual smoke |
| 9 | Backwards compat | ✅ | New module + new sub-component; no API changes; xlsx version unchanged |
| 10 | Sources cited | ✅ | 10 source files with line numbers + design-note callout in excel.ts:7-9 |

Round 1: **PASS**

---

## Round 2: 5-Perspective Review

### 🏗️ Architect

- ✅ Dynamic `import("xlsx")` is the correct pattern for a heavy lib that's only needed on user action — matches Next.js code-splitting expectations
- ✅ Pure-function exporter keeps testability high (Vitest can verify roundtrip)
- ✅ Mock-result transparency (demo_marker column + Summary.status) is the right call to avoid misleading users in the M2-M3 gap
- ⚠️ Three-card duplication for the DownloadResultCard wiring is a known repetition — same as the 501-card pattern. With 3.E.6 the 3 preview cards now have ~80% identical state-machine code. **Future refactor candidate** (Story 3.E.10 / RE2-5): extract a `<TemplatePreviewCard kind="..." />` abstraction. NOT in 3.E.6 scope — prematurely abstracting now would re-introduce branch fan-out inside the component. Documented as DR-3E6.
- ✅ No new ADR needed
- ✅ Per excel.ts:7-9 design note from 3.E.2: this is the anticipated, scoped extension

### 👨‍💻 Dev

- ✅ Implementation focused on 4 files: excel-export.ts (+ test), page.tsx (+ DownloadResultCard), package.json (+ pnpm-lock.yaml change). Tight scope.
- ✅ Test pattern: roundtrip via `xlsx.read` works in happy-dom (already vitest env)
- ⚠️ `xlsx.utils.aoa_to_sheet` expects `unknown[][]` — but `ExcelSheetSummary.rows` is `unknown[][] | undefined`. Need a runtime guard. **Decision**: throw early if `source.sheets[i].rows` is undefined (the preview card should always pass `includeRows: true`; document in JSDoc + add a test for the failure mode). **Test #7 added**.
- ⚠️ Browser dynamic import path: `await import("xlsx")` — Next.js handles this via webpack code-splitting. The `xlsx` package has both ESM + CJS entries; Next 15 picks one automatically. Verified by build pass in T1.
- ✅ Filename construction must escape: only digits + letters; the regex pattern in AC6 already does

Adjusted AC7 (final): **7 tests** (was 6 — added rows-required guard test). solver-orchestrator unchanged. apps/web Vitest 31 → **38** (+7).

### 🧪 QA

- ✅ 7 cases (post Round 2 adjustment) cover happy path × 3 task_types + status=solved synthetic + name truncation + filename format + rows-undefined guard
- ✅ Playwright covers full E2E arc; choosing Inventory is right (largest payload + 3 sheets gives most coverage)
- ⚠️ Cross-browser: `xlsx` works in all modern browsers per SheetJS docs. Playwright runs Chromium by default which is sufficient for v1 verification.
- ⚠️ Should we test that the downloaded file CAN be RE-UPLOADED via the 3.E.1 dropzone path? **Decision: out of scope** — round-trip read of own output is a v1.5/3.E.7 concern (chart embedding may change cell types). For v1, single-write fidelity is enough. Document as DR-3E6-2.

### 🔐 Security

- ✅ All client-side; no PII / network calls in exporter
- ✅ Filename is ASCII-only (no path traversal risk)
- ✅ `xlsx` package has had vulns historically — current `^0.18.5` is the publisher's recommended version; lock to this and monitor (dependabot ON for repo per Story 0.5 setup)
- ✅ Dynamic import doesn't introduce eval/runtime-codegen surface
- ✅ User's source sheet content goes into output unchanged (echo-back) — no injection risk because output is XLSX format not HTML/SQL

### 🛠️ SRE

- ✅ No backend change → no deploy / migration / alerting impact
- ✅ Bundle size: monitor via build output — flag if /console/excel route bundle grows >2 KB (the xlsx chunk is separate; doesn't count)
- ✅ No new env var, secret, or config flag

Round 2: **PASS** with 1 adjustment (AC7 grows from 6 → 7 tests covering rows-undefined guard)

---

## Round 3: Dev-Readiness

- ✅ All file paths absolute
- ✅ Function signatures concrete (TypeScript-strict)
- ✅ Test names + counts enumerated (7 Vitest + 1 Playwright)
- ✅ Reference patterns: 3.E.5 InventoryPreviewCard for the wiring shape; excel.ts:7-9 for the dynamic-import-when-needed pattern
- ✅ Sizing realistic — ~3-4h matches the M estimate; 3.E.5 took ~2-3h with comparable surface area, +0.5-1h for the exporter util
- ✅ Sprint-status update will be bundled into the PR commit (lesson from 2.5/#26)
- ✅ Branch name: `feature/3-e-6-excel-result-download`
- ✅ CI watch: direct `gh pr checks N --watch` + run_in_background (per established gotcha-fix)

Round 3: **PASS — READY FOR DEV**

---

## Implementation Notes

- DO NOT inline import `xlsx` at module top of `excel-export.ts` — would defeat the dynamic-import bundle-splitting goal. Use `const XLSX = await import("xlsx")` inside the function body.
- For DownloadResultCard, the dynamic import happens TWICE indirectly (the page already imports the export util statically, then the util dynamically imports xlsx). Static import of `excel-export` is fine — the module itself is small; only `xlsx` is the heavy piece.
- The `summary` object held in preview-card state already exists post-3.E.5; we're just exposing it to DownloadResultCard. Pass via props, not context.
- Watch for: the `Promise<ExportedWorkbook>` return type means the button onClick needs `await` → handle loading state explicitly. Pattern: `setGenerating(true); try { await buildResultWorkbook(...) } finally { setGenerating(false) }`.
- For Playwright `page.waitForEvent("download")`: the standard pattern is `const [download] = await Promise.all([page.waitForEvent("download"), page.click("[data-testid=inventory-download-button]")])`. Then `await download.saveAs(path)` to validate.
- Per Risk #11 (extreme edge: user has a sheet literally named "输入 — XXX"): the dedup-by-appending-"(2)" rule lives in the helper; cover in test #5 only if natural — otherwise leave as documented behavior.

### AC7 (final, after Round 2 Dev adjustment): 7 Vitest tests

1. `buildResultWorkbook — VRPTW demo: produces blob with input sheets + Results + Summary; Results row count = customer_count; demo_marker present`
2. `buildResultWorkbook — Schedule demo: Results row count = task_count; resource assigned by modulo`
3. `buildResultWorkbook — Inventory demo: Results row count = sku_count; forecast columns present`
4. `buildResultWorkbook — solved status: Summary objective_value reflects realResult.objective`
5. `buildResultWorkbook — sheet name truncation: 50-char source name truncates to fit Excel's 31-char cap with "输入 — " prefix; no crash`
6. `buildResultWorkbook — filename format matches `opticloud_{taskType}_YYYYMMDDTHHmmssZ.xlsx``
7. `buildResultWorkbook — throws when source.sheets[i].rows is undefined (preview card always passes includeRows: true; this is a contract guard)`

apps/web Vitest: **31 → 38** (+7).

Completion note: "Ultimate context engine analysis complete — closes the upload→download Excel arc with pure-client export via dynamic-imported SheetJS; mock-result transparency via demo_marker + Summary.status fields; 7 Vitest + 1 Playwright; sprint-status bundled in PR per 2.5/PR#26 lesson."
