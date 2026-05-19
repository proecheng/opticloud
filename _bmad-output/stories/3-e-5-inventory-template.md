---
story_key: 3-e-5-inventory-template
epic_num: 3.E
story_num: 3.E.5
epic_name: Console Excel Upload-Download UX
status: ready-for-dev
priority: 🟠 High (closes 3.E template-stub trilogy from PMR6; **rule-of-three trigger** to extract excel-helpers)
sizing: M (~2-3 hours; FE mapper + helper extraction + Console card + tests; backend already routes inventory → 501 via 3.E.3 /demo)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L1488-1490 (Story 3.E.5 spec)
  - _bmad-output/stories/3-e-4-schedule-template.md (immediate predecessor — same pattern)
  - _bmad-output/stories/3-e-3-vrptw-template.md (original reference)
  - apps/web/src/lib/task-type-detect.ts L71-85 (inventory sheet/header signals: 出货/sku/库存/季节 + 日期/sku/销量/库存/季节性/date/qty/sales/stock/season)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py L419-518 (existing /v1/optimizations/demo — non-LP already returns 501)
  - apps/web/src/lib/vrptw-template.ts + schedule-template.ts (twin mapper modules to refactor against)
  - e2e/tests/console-excel.spec.ts:189-208 (the override-coverage E2E that needs re-pointing)
dependencies:
  upstream:
    - 3-e-4-schedule-template (done) — confirms the /demo + ConfirmedCard-branch pattern; gives us TWO mapper occurrences to refactor against
    - 3-e-3-vrptw-template (done) — original /demo route + parseExcel `{includeRows}` flag + submitOptimizationDemo helper
    - 3-e-2-excel-task-type-detect (done) — `taskType === "inventory"` already a confirmed branch
  downstream:
    - 3-e-6-excel-result-download — needs solve/prediction result; v1 we only prove the request fires
    - 3-e-9-laozhang-vertical-slice-e2e — this PR closes the template-stub trilogy
    - Real inventory prediction (Story 3.2 — `/v1/predictions` endpoint M2-M3 backend work)
---

# Story 3.E.5 — Inventory Template Mapping + excel-helpers Refactor (PMR6)

## User Story

**As** 老张 (just confirmed "Inventory (库存预测)" in 3.E.2's Modal),
**I want** the page to read my 历史出货 / SKU / 季节性 sheets, **automatically map** the columns to OptiCloud's Inventory prediction schema, show me a **preview** ("here's what I built — 124 SKUs, 8,640 历史出货 rows, 4 seasonality patterns, ready to forecast"), and let me click **试跑** to send the request to the prediction engine,
**so that** even though the prediction engine itself is still M2-M3 (returns 501 today), I have **proof** that my Excel was understood — I see the structured JSON, and the 3.E template-stub trilogy (VRPTW + Schedule + Inventory) is closed; 3.E.9 vertical slice can now build on top.

## Why this story

3.E.3 + 3.E.4 proved the pattern for optimization task_types (VRPTW + Schedule). Inventory is the third PMR6 template — but it's **prediction**, not optimization (Story 3.2 in epics.md, currently backlog). The pattern still works:

- Same /v1/optimizations/demo route's non-LP short-circuit returns 501 for `task_type=inventory`
- Same FE state machine: confirm → preview-card → submit → 501 friendly card
- Friendly-card copy customised: "预测引擎即将上线 (M2-M3)" not "求解器"

**Why the helper refactor now**: 3.E.3 + 3.E.4 each duplicated `findSheet` / `findColumn` / `toNumber` / `toCellString`. With 3.E.5 about to add the THIRD copy, we hit the rule-of-three: extracting `apps/web/src/lib/excel-helpers.ts` is now the cleaner option. (This is the explicit deferral called out in 3.E.4 risks; carrying it forward avoids accumulating skew across the three mappers.)

**Why now (vs deferring to 3.E.9)**: closing the template-stub trilogy gives Story 3.E.6 (result download) a stable surface to build on — its UI placement depends on knowing all three template variants exist.

## Out of scope

- **Real inventory prediction backend** — Story 3.2 `/v1/predictions` route is M2-M3 backend work. When it ships, this story's FE will need a one-line endpoint swap (currently submits to `/v1/optimizations/demo`; will move to `/v1/predictions/demo` or similar). Documented as DR-3E5 tech-debt.
- **3.E.6 Excel result download** — separate story; needs real prediction output
- **3.E.7 Chart embedding** — v1 末
- **Manual column-mapping UI** — automatic header→field mapping; missing required → error with field list; manual override is v1.5
- **Time-series interpolation / gap-filling** — mapper just passes raw rows through; the M2-M3 prediction engine handles preprocessing
- **Multi-warehouse SKU** — v1 assumes one warehouse; SKU id is unique per workbook

## Acceptance Criteria

### AC1: Extract `apps/web/src/lib/excel-helpers.ts`

Pure functions extracted from the duplicate copies in `vrptw-template.ts` and `schedule-template.ts`. These four are the rule-of-three hits:

```ts
import type { ExcelSheetSummary, ExcelWorkbookSummary } from "./excel";

/** Case-insensitive substring match against sheet names. Returns first match. */
export function findSheet(
  summary: ExcelWorkbookSummary,
  tokens: string[],
): ExcelSheetSummary | null;

/** Case-insensitive substring match against headers. Returns first matching column index, or -1. */
export function findColumn(headers: string[], tokens: string[]): number;

/** Parse a cell into a finite number, or null when blank/non-numeric. */
export function toNumber(cell: unknown): number | null;

/** Parse a cell into a trimmed non-empty string, or null. */
export function toCellString(cell: unknown): string | null;
```

NOT extracted (single-use, mapper-specific):
- `toTimeString` (VRPTW-only — Date → "HH:MM"; keep inline in vrptw-template.ts)
- `lower(s) → s.toLowerCase()` (trivial; inline `.toLowerCase()` calls are clearer than a wrapper)

Update `vrptw-template.ts` and `schedule-template.ts` to import from `./excel-helpers`. Delete the inline copies. **No behavioral change** — verified by existing tests passing unchanged.

### AC2: New module `apps/web/src/lib/inventory-template.ts`

Pure function that takes the workbook summary (with rows) and returns either a structured payload OR a list of errors. Mirror shape of vrptw / schedule mappers.

```ts
import type { ExcelWorkbookSummary } from "./excel";

export interface InventorySKU {
  sku: string;
  name: string | null;
  category: string | null;
  initial_stock: number | null;
}

export interface InventoryHistoryRecord {
  sku: string;
  date: string;   // pass-through user's string (ISO-ish); preprocessing is backend's job
  qty: number;
}

export interface InventorySeasonalityRecord {
  sku: string;
  season: string;   // e.g. "Q1" / "spring" / "2026-03"
  multiplier: number;
}

export interface InventoryPayload {
  task_type: "inventory";
  skus: InventorySKU[];
  history: InventoryHistoryRecord[];
  seasonality: InventorySeasonalityRecord[];   // empty array if 季节性 sheet absent
  options?: { forecast_horizon_days?: number };
}

export interface InventoryErrorDetail {
  sheet: string;
  field?: string;
  message: string;
}

export type InventoryMappingResult =
  | {
      ok: true;
      payload: InventoryPayload;
      sku_count: number;
      history_count: number;
      seasonality_count: number;
      warnings: string[];
    }
  | {
      ok: false;
      errors: InventoryErrorDetail[];
    };

export function buildInventoryPayload(summary: ExcelWorkbookSummary): InventoryMappingResult;
```

Column-mapping heuristic (case-insensitive substring; sheet detection by name substring):

| Sheet alias | Sheet-name tokens |
|---|---|
| SKU | `sku` / `商品` / `产品` |
| 历史出货 (history) | `出货` / `历史` / `销量` / `sales` / `history` |
| 季节性 (seasonality) | `季节` / `season` |

| SKU field | Headers |
|---|---|
| `sku` | sku / 编号 / id / 商品编号 |
| `name` | 名称 / name / 商品名 |
| `category` | 类别 / category / type |
| `initial_stock` | 期初库存 / 库存 / stock / initial |

| History field | Headers |
|---|---|
| `sku` | sku / 编号 / 商品编号 / id |
| `date` | 日期 / date |
| `qty` | 销量 / 数量 / qty / quantity |

| Seasonality field | Headers |
|---|---|
| `sku` | sku / 编号 / 商品编号 / id |
| `season` | 季节 / 周期 / season / period |
| `multiplier` | 系数 / 倍数 / multiplier / factor |

Required:
- SKU sheet with `sku` column → missing → error
- 历史出货 sheet with `sku` + `date` + `qty` columns → missing → error
- 季节性 sheet OPTIONAL — returns empty `seasonality: []` (with a warning)

Validations (per row):
- `qty >= 0` (numeric)
- `multiplier > 0` (numeric)
- `initial_stock >= 0` if present (else null)
- Empty / blank id rows → skipped (with warning)
- History rows referencing SKU not in SKU sheet → counted as `unknown_sku` warning, row skipped (does NOT fail mapping — common case where SKU table is curated subset)

Warnings:
- "Skipped N empty SKU rows" / "Skipped N empty 出货 rows"
- "季节性 sheet not found — 已默认无季节性约束"
- "历史出货 sheet has M rows referencing unknown sku id" (rows skipped)
- "季节性 sheet has K rows referencing unknown sku id" (rows skipped)

### AC3: Reuse the existing backend `/v1/optimizations/demo` route

No backend route code change. The route from 3.E.3 already short-circuits non-LP to 501. Add ONE test to lock inventory case:

In `apps/solver-orchestrator/tests/test_demo_optimizations.py`:

```python
async def test_demo_inventory_returns_501(client: AsyncClient) -> None:
    """Story 3.E.5 — inventory body returns 501 with friendly 'M2-M3' detail."""
    resp = await client.post(
        "/v1/optimizations/demo",
        json={
            "task_type": "inventory",
            "skus": [{"sku": "S1"}],
            "history": [{"sku": "S1", "date": "2026-01-01", "qty": 10}],
            "seasonality": [],
        },
    )
    assert resp.status_code == 501
    body = resp.json()
    assert "M2-M3" in body["detail"]
    assert "inventory" in body["detail"]
```

solver-orchestrator 31 → **32** (+1).

### AC4: Console page integration — extend `ConfirmedCard`

In `apps/web/src/app/console/excel/page.tsx`:

1. Add branch:
```tsx
if (taskType === "inventory") {
  return <InventoryPreviewCard file={file} onReset={onReset} />;
}
```
after the schedule branch.

2. Add new `InventoryPreviewCard` component (mirror Schedule/VRPTW shape):
   - Re-parse with `{includeRows: true}`, call `buildInventoryPayload`
   - Failure: error StatusCard + field-level errors list
   - Success: "✅ 已构建预测请求 — {N} SKU / {H} 历史行 / {S} 季节"
   - JSON preview in `<details>`
   - 试跑 button → `submitOptimizationDemo` → 501 friendly card
3. **Customise 501 copy for prediction** (NOT "求解器"):
   - Title: "📈 预测引擎即将上线 (M2-M3)"
   - Description: "您的数据已通过格式校验（{N} SKU / {H} 历史行）。预测引擎将在后续版本上线，届时本页面将直接返回 P10/P50/P90 + drift_score。"
   - Link: `/algorithms?task_type=forecast` → "→ 看其它预测算法"
4. Update fallback `ConfirmedCard` placeholder copy: now closes the trilogy:
   - "下一步：3.E.6 (结果下载) 将在 PR #24+ 接管 — VRPTW / Schedule / Inventory 三大模板已落地。"

`data-testid` for E2E:
- `inventory-preview-card`
- `inventory-submit-button`
- `inventory-501-card`
- `inventory-payload-json`

### AC5: Vitest — inventory-template mapper

New `apps/web/src/lib/inventory-template.test.ts` — 8 cases:

1. `buildInventoryPayload — happy path: 3 sheets (SKU / 历史出货 / 季节性) complete → ok=true with counts`
2. `buildInventoryPayload — missing SKU sheet → ok=false with error`
3. `buildInventoryPayload — missing 历史出货 sheet → ok=false with error`
4. `buildInventoryPayload — missing required column (qty) → ok=false with field-level error`
5. `buildInventoryPayload — invalid qty (negative) → ok=false with row-level error`
6. `buildInventoryPayload — 季节性 sheet absent → ok=true with warning + seasonality=[]`
7. `buildInventoryPayload — history referencing unknown sku → row skipped with warning (does NOT fail)`
8. `buildInventoryPayload — empty SKU rows skipped with warning`

Also: **regression tests for the vrptw + schedule mappers must continue passing unchanged** after the helper extraction (AC1).

apps/web Vitest 23 → **31** (+8).

### AC6: Playwright E2E

1. **Fix override-coverage collision (existing test at `console-excel.spec.ts:189-208`)**: this test was re-pointed from `schedule` → `inventory` in PR #22. Inventory now routes to its own preview card. Re-point AGAIN — this time to `lp` (which still falls through to placeholder `excel-confirmed-card`; lp is the final unbranded task_type). Change `selectOption({ value: "inventory" })` → `selectOption({ value: "lp" })` and `/Inventory/` → `/LP/` (or `/通用 LP/` matching the TASK_LABEL entry).

2. Add new test `test("Inventory confirm → 试跑 → 501 friendly card + JSON preview")`:
   - Build inventory .xlsx in-memory (sheets SKU / 历史出货 / 季节性)
   - Drop via setInputFiles
   - Confirm "Inventory (库存预测)" in Modal (force via override select for determinism)
   - Expect InventoryPreviewCard visible with /SKU/ + /历史/
   - Click 试跑 → expect `inventory-501-card` visible + "M2-M3"
   - Expect `inventory-payload-json` contains `"task_type": "inventory"`

Playwright total ~21 → **22** (+1).

### AC7: Quality gates

Per `feedback_full_quality_gates`:
- `pnpm -C apps/web test` (must show 31 passing, +8 over current 23)
- `pnpm -C apps/web typecheck`
- `pnpm -C apps/web build` (Console route bundle measured; expect ~1.5 KB growth)
- `pnpm -C packages/ui test` (22 baseline preserved)
- `uv run ruff check .` + `ruff format --check .`
- `uv run mypy apps packages`
- Backend pytest run via CI (DR5 local block unchanged)

### AC8: NFR alignment

- **PMR6** ✅ — closes the 3 PMR6 template stubs (VRPTW + Schedule + Inventory)
- **NFR-S** — Demo route still unauthenticated (DR3 unchanged); inventory adds no new attack surface
- **NFR-P1** — Re-parse with includeRows ~100ms (DR4 unchanged)
- **FR E2** — Prediction submission contract sketched in JSON payload; M2-M3 backend will accept this shape via `/v1/predictions` endpoint (Story 3.2)
- **FR E11** — Excel surface advances; trilogy complete

## Tasks

### T1 — Extract excel-helpers + refactor vrptw/schedule mappers (0.5h)
1. Create `apps/web/src/lib/excel-helpers.ts` with `findSheet`, `findColumn`, `toNumber`, `toCellString` per AC1
2. Delete the inline copies from `vrptw-template.ts` + `schedule-template.ts`; import from helpers
3. Verify existing tests still pass (`pnpm -C apps/web test -- --run src/lib/vrptw-template.test.ts src/lib/schedule-template.test.ts`)

### T2 — Inventory mapper module + tests (1h)
1. Create `apps/web/src/lib/inventory-template.ts` per AC2 (uses excel-helpers)
2. Create `apps/web/src/lib/inventory-template.test.ts` — 8 cases per AC5

### T3 — Backend inventory 501 test (0.1h)
1. Append `test_demo_inventory_returns_501` to `test_demo_optimizations.py` per AC3

### T4 — Console page InventoryPreviewCard (0.6h)
1. Add `InventoryPreviewCard` to `console/excel/page.tsx` (mirror Schedule)
2. Extend `ConfirmedCard` branching: add `if (taskType === "inventory")`
3. Customise 501 copy for "预测引擎" (not "求解器") per AC4
4. Update placeholder fallback copy per AC4
5. Add data-testids per AC4

### T5 — E2E: fix override + add inventory test (0.3h)
1. Re-point override test from `inventory` → `lp` per AC6.1
2. Add new "Inventory confirm → 试跑" test per AC6.2

### T6 — Quality gates + sprint sync + PR (0.4h)

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Helper extraction breaks vrptw/schedule existing tests | Run those test files BEFORE inventory work; if any test fails, signature/behavior of the helper drift. Helpers must be 100% drop-in replacements. |
| `toNumber` / `toCellString` have subtle behavioral diff between vrptw + schedule copies | Source-diff first: both files have IDENTICAL implementations (verified manually pre-story). Extraction is safe. |
| Inventory uses /optimizations/demo endpoint, but it's semantically a prediction (Story 3.2 territory) | Acceptable v1; documented as DR-3E5 tech-debt. When `/v1/predictions/demo` lands (M2-M3 backend), 3.E.5 FE changes ONE LINE: `submitOptimizationDemo` → `submitPredictionDemo`. |
| History sheet may have 50K rows on its own — the 50K cap is per-WORKBOOK not per-sheet | Already enforced in 3.E.2 at `totalRows > 50_000`. If inventory user hits this, the 50K-cap card fires before mapper runs. v1 OK. |
| 季节性 sheet's column "季节" could collide with 历史出货 "季节" header (same word) | Sheet detection uses sheet-NAME substring match; column detection uses HEADER substring within already-resolved sheet. No collision risk. |
| SKU id space mismatch between SKU sheet and history rows (typo / case / whitespace) | Trim both sides + case-insensitive compare? **No** — keep case-sensitive (mirrors VRPTW behavior); user typo surfaces as `unknown sku` warning count; they can clean in Excel. Soft warning, not error. |
| Override-coverage E2E will need re-pointing AGAIN in 3.E.6 if 3.E.6 adds an LP preview card | Unlikely — 3.E.6 is result download (post-solve), not pre-solve preview. LP path keeps falling through to `excel-confirmed-card`. If this assumption breaks, repeat the swap pattern. |
| Detector might pick "schedule" for a workbook with `季节` sheet (matches schedule's 排班 alias too — wait, "季节" ≠ "排班"; double-check signal table) | Detector signals: schedule={任务/资源/工序/排班/task/resource/shift}, inventory={出货/sku/库存/季节/sales/inventory}. No collision — different tokens. |
| Adding `forecast_horizon_days` to options without UI control | v1 omits from payload (key absent = backend default); UI control deferred to 3.E.6 or backend M3. |

## Definition of Ready

- ✅ 3.E.4 shipped: SchedulePreviewCard pattern + 2nd mapper occurrence (rule-of-three trigger)
- ✅ 3.E.2 detector recognizes `inventory` task_type
- ✅ apps/web Vitest infra in place
- ✅ xlsx devDep available in `apps/web/package.json`
- ✅ Backend /demo route handles non-LP → 501

## Definition of Done

- 8 ACs pass
- apps/web Vitest 23 → 31 (+8 inventory mapper); vrptw + schedule tests unchanged
- solver-orchestrator 31 → 32 (+1 inventory 501); Playwright +1
- excel-helpers.ts extracted; vrptw + schedule mappers use it; LOC reduction visible in mapper files
- CI all green
- sprint-status updated to `done`
- Manual smoke: drop Inventory .xlsx → confirm → preview shows N SKU / H 历史 + JSON → 试跑 → 501 friendly card with "预测引擎" copy

## Sign-off

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| 3.E Lead | TBA | ☐ | — |
| Backend Lead | TBA | ☐ | — |

> Owner committee deferred per M0 skip.

---

## Round 1: BMad Checklist Review

| # | Item | Status | Note |
|---|---|:-:|---|
| 1 | User story has As/I want/so that | ✅ | 老张 persona |
| 2 | ACs are testable & BDD-shaped | ✅ | Given/When/Then implicit |
| 3 | Scope explicit (in/out) | ✅ | Out-of-scope clear; real prediction backend deferred |
| 4 | Dependencies declared | ✅ | upstream 3.E.4 + 3.E.3 + 3.E.2; downstream 3.E.6, 3.E.9 |
| 5 | Sizing estimate | ✅ | M (~2-3h; helper refactor adds 0.5h over the schedule baseline) |
| 6 | Risks identified with mitigations | ✅ | 8 risks |
| 7 | Quality gates listed | ✅ | AC7 |
| 8 | Test plan: unit + integration + E2E | ✅ | +8 Vitest + 1 solver + 1 Playwright + override-fix |
| 9 | Backwards compatibility | ✅ | Helper extraction is no-op for existing mappers; demo route unchanged |
| 10 | Sources cited with line numbers | ✅ | Top frontmatter |

Round 1: **PASS**

---

## Round 2: 5-Perspective Review

### 🏗️ Architect

- ✅ Helper extraction triggered by rule-of-three (3 mappers about to share the helpers) — correct timing
- ✅ Demo route reuse keeps surface area small; no new endpoint
- ⚠️ The `/optimizations/demo` route now serves 4 task_types (lp/vrptw/schedule/inventory) — naming starts feeling off for the prediction case. Documented as DR-3E5; future `/predictions/demo` is acceptable but not blocking.
- ✅ InventoryPreviewCard is structurally identical to Schedule/VRPTW; the THREE preview cards share enough shape that a `<TemplatePreviewCard kind="..."/>` abstraction would now be defensible — but DEFER: each card has slightly different success-state copy and links; abstracting prematurely would re-introduce branching inside the component. Three concrete cards is fine.

### 👨‍💻 Dev

- ✅ Helper signatures are direct copy from current implementations — no API surprise
- ✅ Inventory mapper test cases enumerated; same 8-case shape as schedule
- ✅ data-testid pattern consistent
- ⚠️ The override E2E re-pointing must use a value that DOES fall through to `excel-confirmed-card` — `lp` is correct (no preview card for LP yet); flag this for verification during T5
- ✅ Helper extraction is a refactor — must be done FIRST (T1 before T2) so inventory writes against the helpers from day 1, not against re-extracted code post-fact

### 🧪 QA

- ✅ 8 mapper tests cover the same branches as schedule (happy / structural / data / optional-sheet / soft-warning / empty)
- ✅ Helper refactor verified by EXISTING vrptw + schedule tests staying green (no new helper test file — these helpers are tested transitively through the 3 mappers' tests; pure-function trivial enough)
- ✅ Backend 501 test mirrors schedule
- ✅ Playwright override-fix mitigates the same kind of test rot we saw in 3.E.4
- ⚠️ Consider adding ONE explicit test for `findSheet` / `findColumn` edge cases (empty sheets array, no matching tokens, multiple matches). **Decision: skip** — current usage is already exercised by 14 tests across vrptw+schedule mappers; pure-function helper failure modes are all covered indirectly. Adding direct tests is bookkeeping cost without coverage gain.

### 🔐 Security

- ✅ Demo route still unauthenticated (DR3 unchanged)
- ✅ No new attack surface — inventory is just a different task_type token through same handler
- ✅ FE: file never leaves browser; mapper is pure (no fetch / no eval)

### 🛠️ SRE

- ✅ No new env var
- ✅ No DB migration
- ✅ No new dependency
- ✅ The bundle-size growth (~1.5 KB est. for InventoryPreviewCard + mapper) is small; verify post-build

Round 2: **PASS** (1 medium item flagged: verify lp falls through to placeholder during T5)

---

## Round 3: Dev-Readiness

- ✅ File paths absolute (apps/web/src/lib/excel-helpers.ts, inventory-template.ts, .test.ts)
- ✅ Types fully defined in AC2 — copy-pasteable
- ✅ Test names enumerated (8 mapper + 1 backend + 1 Playwright + 1 override-fix)
- ✅ Reference implementations: 3-e-3 + 3-e-4 (twin pattern)
- ✅ Sizing realistic — 3.E.4 came in at ~1h actual coding + ~30min testing; helper refactor adds 0.5h
- ✅ Sprint-status update path declared

Round 3: **PASS — READY FOR DEV**

---

## Implementation Notes

- Run T1 (extract helpers) IN ISOLATION first, verify vrptw + schedule tests green, THEN proceed to T2 (inventory). This sequencing prevents helper-bugs from masquerading as inventory-mapper bugs.
- `lower()` is intentionally NOT extracted — inline `.toLowerCase()` is clearer than a wrapper for a 1-token operation.
- The 501 friendly-card copy must say "预测引擎" not "求解器" — this is a meaningful UX distinction for the inventory persona (forecasting is qualitatively different from solving).
- For inventory's history-row data: when SKU sheet's id space and history rows' SKU column disagree, history rows for unknown SKUs are SKIPPED, NOT errored. This matches real-world Excel hygiene (users often have aspirational SKU master tables that lag actual shipments).
- After this PR, 3 mapper files (`vrptw-template.ts`, `schedule-template.ts`, `inventory-template.ts`) all import from `excel-helpers.ts`. If a 4th template emerges (3.E.10 / RE2-5 expansion), the helper module is already in place — extension cost is just the SIGNALS constant + buildXyzPayload function.

Completion note: "Ultimate context engine analysis completed — 3.E.5 closes the 3.E template-stub trilogy; helper extraction triggered by rule-of-three (vrptw + schedule + inventory now share excel-helpers); 8 mapper tests + 1 backend test + 1 E2E + 1 override-fix."
