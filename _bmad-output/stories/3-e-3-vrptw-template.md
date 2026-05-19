---
story_key: 3-e-3-vrptw-template
epic_num: 3.E
story_num: 3.E.3
epic_name: Console Excel Upload-Download UX
status: ready-for-dev
priority: 🟠 High (continues 3.E pipeline 3.E.2 → 3.E.6; first vertical template stub; pattern for 3.E.4 + 3.E.5)
sizing: M (~3-4 hours; FE mapper + JSON construction + API wire + 501 graceful handling + tests)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L1480-1482 (Story 3.E.3 spec)
  - apps/web/src/lib/excel.ts (3.E.2 parser — extend to optionally return rows)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py:258 (current `task_type != lp → 501` stub)
  - apps/solver-orchestrator/src/solver_orchestrator/schemas.py:55 (OptimizationRequest already accepts vrptw in Literal)
dependencies:
  upstream:
    - 3-e-2-excel-task-type-detect (done) — confirms taskType, has ExcelWorkbookSummary + file
    - 3-1-j1-lp-solve (done) — `POST /v1/optimizations` endpoint exists
  downstream:
    - 3-e-4-schedule-template — same pattern, different schema
    - 3-e-5-inventory-template — same pattern, prediction (E2) not optimization
    - 3-e-9-laozhang-vertical-slice-e2e — this story's pattern is the spine
    - Real VRPTW solver implementation (M2-M3 backend work, NOT in scope here)
---

# Story 3.E.3 — VRPTW Template Mapping (PMR6)

## User Story

**As** 老张 (just confirmed "VRPTW" in 3.E.2's Modal),
**I want** the page to read my 客户 / 车辆 / 时间窗 sheets, **automatically map** the columns to OptiCloud's VRPTW schema, show me a **preview** ("here's what I built — 12 customers, 3 vehicles, ready to solve"), and let me click **试跑** to send the request to the solver,
**so that** even though the VRPTW solver itself is still M2-M3 (returns 501 today), I have **proof** that my Excel was understood — I see the structured JSON, and I'm not blocked from validating the pipeline end-to-end for 3.E.9 vertical slice.

## Why this story

3.E.2 confirms WHICH problem the user has (VRPTW). It does NOT yet:
- Read the actual data rows
- Map headers → schema fields
- Build the API request body
- Call the solver

This story does ALL of that for the VRPTW case. Without it, 3.E.2's "confirmed" state is a dead end (just a "下一步：3.E.3" placeholder card).

**Why now (vs deferring to vertical slice 3.E.9)**: 老张 is the persona we're validating. If we don't show him a real "I got 12 customers, 3 vehicles, here's the JSON" preview soon, the 3.E.1 + 3.E.2 work feels like it leads nowhere. This story is the first "I see the system understood my file" moment.

## Out of scope

- **Real VRPTW solver implementation** — backend returns 501 today. This is M2-M3 backend work (or-tools-vrptw wiring in `solver-orchestrator/src/solvers.py`). When that ships, this story's API call automatically starts returning real results — no FE change needed.
- **3.E.4 / 3.E.5 templates** — same pattern, different schemas; separate stories
- **Manual column-mapping UI** — v1 uses automatic header→field mapping based on the same signal set 3.E.2 uses. If automatic mapping fails (missing required column), v1 shows a validation error with the missing fields listed; manual override is a v1.5 polish (track as deferred backlog item)
- **Large-file streaming** — v1 reads all rows into memory (5MB cap + 50K row cap from 3.E.1/2 keeps this safe)
- **Result rendering** — 3.E.6 owns result download; 3.E.3 only proves the request fires + handles the response (success / 501 / error)
- **Solve cost / Credits charging** — 5.A.4 (Saga charging) is wired for LP via `X-Billing-Charge-Id` header; VRPTW would inherit the same pattern when implemented backend-side. This story does NOT pass that header for the unauthenticated /console/excel demo path (no API key in Console; this is the demo-only entry — paid solving requires signup + API key flow which is in Epic 1)

## Acceptance Criteria

### AC1: Extend `parseExcel` to optionally include rows

In `apps/web/src/lib/excel.ts`:

```ts
export interface ExcelSheetSummary {
  name: string;
  headers: string[];
  rowCount: number;
  /** Story 3.E.3 — only populated when parseExcel called with {includeRows: true} */
  rows?: unknown[][];
}

export async function parseExcel(
  file: File,
  options?: { includeRows?: boolean },
): Promise<ExcelWorkbookSummary>;
```

Behavior:
- `includeRows: undefined | false` — current behavior (headers + rowCount only, ~10x smaller payload)
- `includeRows: true` — populates `sheets[i].rows` with the full row matrix (each row is `unknown[]`; first row = header row)

Backward-compat: 3.E.2 detect path calls without the flag → no behavior change.

### AC2: New module `apps/web/src/lib/vrptw-template.ts`

Pure function that takes the workbook summary (with rows) and returns either a structured payload OR a list of errors.

```ts
export interface VRPTWCustomer {
  id: string;
  lat: number;
  lng: number;
  demand: number;
  time_window_start: string | null;  // "HH:MM" or null
  time_window_end: string | null;
  service_minutes: number | null;
}

export interface VRPTWVehicle {
  id: string;
  capacity: number;
}

export interface VRPTWPayload {
  task_type: "vrptw";
  customers: VRPTWCustomer[];
  vehicles: VRPTWVehicle[];
  options?: { max_solve_seconds?: number };
}

export interface VRPTWMappingResult {
  ok: true;
  payload: VRPTWPayload;
  customer_count: number;
  vehicle_count: number;
  warnings: string[];
} | {
  ok: false;
  errors: Array<{ sheet: string; field?: string; message: string }>;
}

export function buildVrptwPayload(summary: ExcelWorkbookSummary): VRPTWMappingResult;
```

Column-mapping heuristic (case-insensitive header substring):

| OptiCloud field | Customer sheet headers (any match) |
|---|---|
| `id` | 客户名 / 名称 / id / customer / name |
| `lat` | 纬度 / lat / latitude |
| `lng` | 经度 / lng / lon / longitude |
| `demand` | 需求 / demand / 数量 / qty |
| `service_minutes` | 服务时间 / service_time / service_minutes |

| OptiCloud field | Vehicle sheet headers |
|---|---|
| `id` | 编号 / id / vehicle / name |
| `capacity` | 容量 / capacity |

| OptiCloud field | Time-window sheet headers |
|---|---|
| (joins on `customer_id`) | 客户名 / customer |
| `time_window_start` | 开始 / start |
| `time_window_end` | 结束 / end |

Required:
- 客户 sheet with at least `id`, `lat`, `lng`, `demand` columns — missing → error
- 车辆 sheet with `id` + `capacity` — missing → error
- 时间窗 sheet OPTIONAL — if present, must have `customer_id` + `start` + `end`; per-customer time windows attach by matching id

Validations (per row):
- lat in [-90, 90]; lng in [-180, 180]
- demand >= 0
- capacity > 0
- empty/blank id rows → skipped (with a warning "skipped N blank rows")

Warnings (returned in `warnings: []`):
- "Skipped N empty customer rows"
- "Time-window sheet has M rows that did not match any customer"
- "Customer X has no time window — will default to all-day"

### AC3: Console page integration

In `apps/web/src/app/console/excel/page.tsx`, extend the `confirmed` state:

When `state.kind === "confirmed"` AND `state.taskType === "vrptw"`:
1. Replace the placeholder card with a new `VrptwPreviewCard` (or render alongside)
2. Internally, re-parse the file with `includeRows: true`, then call `buildVrptwPayload(summary)`
3. If mapping fails: show errors in a StatusCard variant="error" + list each `{sheet, field, message}` + a "返回手动选择" button
4. If mapping succeeds:
   - Summary "✅ 已构建求解请求 — N 客户 / M 车辆"
   - `<details>` block showing the JSON payload (collapsed by default)
   - "🚀 试跑" button — click → POST `/v1/optimizations`
5. After click:
   - Loading spinner during fetch
   - On 200 (when VRPTW solver eventually lands): show success card with solution summary
   - On 501 (current expected): show info card "VRPTW 求解器将在 M2-M3 上线 — 您的数据已通过格式校验，可在 M2 末重试" + a link to subscribe (stub to `/`)
   - On other errors (422 / 5xx): show error StatusCard with detail
6. "重新选择文件" button always available to reset

For non-VRPTW confirmed taskType (schedule / inventory / lp / unknown): keep the existing placeholder card (3.E.4 / 3.E.5 will extend separately).

### AC4: API call helper in lib/api.ts

Add `submitOptimization(payload)` that POSTs to `/v1/optimizations` on the solver-orchestrator. Important: this is the **unauthenticated demo path** — does NOT include `Authorization` or `X-Billing-Charge-Id` headers (since Console is no-auth). The backend currently REQUIRES auth on this endpoint — expect 401.

**Wait — re-check backend**: `verify_api_key(authorization, session)` is called at the top of `post_optimization`. Without an Authorization header, it returns 401.

→ Need backend to either expose a `/v1/optimizations/demo` route OR allow unauthenticated calls when a special header (`X-Demo-Mode: 1`) is set.

**Decision**: simpler path = new backend route `POST /v1/optimizations/demo` that:
- Skips auth (no api_key needed)
- Skips Credits billing entirely
- Skips persistence (no DB write) — pure stateless solve, returns the result
- Has the same `OptimizationRequest` body schema
- For `task_type=vrptw` (and other non-LP): returns the same 501 stub
- For `task_type=lp`: actually solves (so /console/excel could eventually demo LP end-to-end without signup)

Rate-limited by IP in M3; v1 just runs. Add a "demo" route prefix at `routes.py`.

Backend tests:
- `test_optimizations_demo_lp_returns_solution` — POST /v1/optimizations/demo with lp body → 200 + solution
- `test_optimizations_demo_vrptw_returns_501` — POST with vrptw body → 501 (matches current non-LP stub)
- `test_optimizations_demo_does_not_require_auth` — no Authorization header → 200/501 (NOT 401)

### AC5: FE handles 501 friendly

In the page, when `submitOptimization` returns 501 (parsed via OptiCloudClientError.status check):

- StatusCard variant="info", title "VRPTW 求解器 M2-M3 上线"
- description: "您的数据已通过格式校验（{N} 客户 / {M} 车辆）。求解器将在 M2 末（2026-06）上线。"
- Show the constructed JSON payload below — proof to the user the system understood
- "返回算法目录看其它求解器" link → `/algorithms?tier=T4` (VRPTW is T4)

### AC6: Vitest — vrptw-template mapper

New `apps/web/src/lib/vrptw-template.test.ts`:

1. `buildVrptwPayload — happy path: 3 sheets complete → ok=true, customers/vehicles count correct`
2. `buildVrptwPayload — missing customer sheet → ok=false with error`
3. `buildVrptwPayload — missing required column (lat) → ok=false with field-level error`
4. `buildVrptwPayload — invalid lat (out of range) → ok=false with row-level error`
5. `buildVrptwPayload — time-window sheet absent → ok=true with warning + customers default to null windows`
6. `buildVrptwPayload — empty rows skipped with warning`

apps/web Vitest 9 → **15** (+6).

### AC7: Backend tests for /demo route

Add to `apps/solver-orchestrator/tests/` (new file `test_demo_optimizations.py`):

1. `test_demo_lp_solves_without_auth` — POST `/v1/optimizations/demo` lp body, no Authorization → 200 + objective
2. `test_demo_vrptw_returns_501` — POST vrptw body → 501 with friendly detail
3. `test_demo_with_invalid_lp_returns_422` — bad body → 422

solver-orchestrator 27 → **30** (+3).

### AC8: Playwright E2E

Extend `console-excel.spec.ts` with 1 new test:

`test("VRPTW confirm → 试跑 → 501 'M2-M3' 友好卡片")`:
- Drop a VRPTW workbook (reuse VRPTW_BUFFER from 3.E.2 tests, but extend to have more rows for realism)
- Confirm "VRPTW" in Modal
- Expect VrptwPreviewCard visible with "N 客户" text
- Click "🚀 试跑" button
- Expect the 501 friendly card visible with "M2-M3 上线" text
- Expect the constructed JSON visible in a `<pre>` or `<code>` block

Playwright total ~19 → 20 (+1).

### AC9: Quality gates

Standard set (ruff / format / mypy / typecheck × 3 / web vitest / ui vitest / build / e2e via CI).

### AC10: NFR alignment

- **PMR6** ✅ first vertical template stub shipped (3.E.4 / 3.E.5 will follow same pattern)
- **NFR-S** Demo route is unauthenticated — explicit; rate-limit M3
- **NFR-P1** Re-parsing with includeRows on confirm = one extra parse pass (~100ms for 5MB). Could cache the first parse's File reference — v2 polish.
- **FR E1** — POST /v1/optimizations contract reused (Story 3.1)

## Tasks

### T1 — Backend `/demo` route + tests (0.5h)
1. Add `POST /v1/optimizations/demo` to `routes.py` — copy `post_optimization` flow, strip auth/billing/persist, return solver result
2. Add 3 tests per AC7

### T2 — Extend parseExcel with `includeRows` flag (0.2h)
1. Update `apps/web/src/lib/excel.ts` per AC1 — add option, populate `rows` when set
2. Existing 3.E.2 tests unchanged (call without flag)

### T3 — VRPTW mapper module + tests (1h)
1. Create `apps/web/src/lib/vrptw-template.ts` per AC2
2. Create `apps/web/src/lib/vrptw-template.test.ts` — 6 cases per AC6

### T4 — lib/api.ts submitOptimization helper (0.15h)
1. Add `submitOptimization(payload, opts: {demo?: boolean})` that POSTs to `/demo` or regular endpoint
2. Reuses existing `OptiCloudClientError` for error path

### T5 — Console page VrptwPreviewCard (1h)
1. Refactor `confirmed` state branch to special-case `taskType === "vrptw"`
2. New `VrptwPreviewCard` inline component per AC3 — re-parse with includeRows, build payload, render preview + 试跑 button
3. Handle submit → loading → success/501/error states
4. Add `data-testid` for E2E: `vrptw-preview-card`, `vrptw-submit-button`, `vrptw-501-card`

### T6 — E2E test (0.3h)
1. Add 1 test per AC8 to `console-excel.spec.ts`

### T7 — Quality gates + sprint sync + PR (0.4h)

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Backend `/demo` route bypasses auth — security concern | Documented as intentional for demo flow; M3 will add IP rate limiting; current scope: marketing demo only, no PII or billing exposure |
| Re-parsing file with includeRows when user navigates from received → confirmed → preview = parse twice | v1 acceptable (~100ms); v2 cache the parse result in state object {summary, file, fullSummary?} |
| Column mapping heuristics false-positive (sheet "供应商" mistakenly mapped as customers) | AC2 requires REQUIRED columns to all match; partial matches → error not silent acceptance |
| Time-window sheet's "客户名" column has typos that don't join | AC2 warning "M rows did not match" gives user a count; manual fixup in Excel |
| User's customer sheet has Chinese header `客户编号` not `客户名` | Add `客户编号` to the id signal list |
| 501 message says "M2 末" but that's a moving deadline | Keep copy generic — "求解器即将上线" without specific date; remove date from final shipping copy |
| `includeRows: true` for 50K-row file = ~50K × ~10 columns × 30 bytes = 15MB in memory | 5MB file cap from 3.E.1 + 50K row cap from 3.E.2 limit this; parser holds at most ~20MB peak, well within browser tab budget |

## Definition of Ready

- ✅ 3.E.2 confirmed state has `{taskType, summary, file}`
- ✅ Backend `/v1/optimizations` exists (3.1)
- ✅ apps/web Vitest infra exists (3.E.2)
- ✅ Catalog has VRPTW SKU (or-tools-vrptw, T4)

## Definition of Done

- 10 ACs pass
- apps/web Vitest 9 → 15 (+6); solver tests 27 → 30 (+3); Playwright +1
- CI all green
- sprint-status updated
- Manual smoke: drop VRPTW xlsx → confirm → preview shows N customers + JSON → 试跑 → 501 friendly card

## Sign-off

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| 3.E Lead | TBA | ☐ | — |
| Backend Lead | TBA | ☐ | — |

> Owner committee deferred per M0 skip.
