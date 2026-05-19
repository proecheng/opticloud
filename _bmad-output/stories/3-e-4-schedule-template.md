---
story_key: 3-e-4-schedule-template
epic_num: 3.E
story_num: 3.E.4
epic_name: Console Excel Upload-Download UX
status: ready-for-dev
priority: 🟠 High (continues 3.E pipeline 3.E.3 → 3.E.5; second vertical template stub; reuses 3.E.3 backend /demo route)
sizing: M (~2-3 hours; FE mapper + Console card + tests; backend already routes schedule → 501 via 3.E.3 /demo)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L1484-1486 (Story 3.E.4 spec)
  - _bmad-output/stories/3-e-3-vrptw-template.md (reference implementation pattern)
  - apps/web/src/lib/task-type-detect.ts L56-70 (schedule sheet/header signals: 任务/资源/工序 + 工期/截止/duration/deadline/resource/shift/employee)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py L419-518 (existing /v1/optimizations/demo — non-LP already returns 501)
  - apps/web/src/lib/vrptw-template.ts (mapper shape to copy)
  - apps/web/src/app/console/excel/page.tsx (ConfirmedCard branching point at L417)
dependencies:
  upstream:
    - 3-e-3-vrptw-template (done) — `/v1/optimizations/demo` route + parseExcel `{includeRows}` flag + submitOptimizationDemo helper
    - 3-e-2-excel-task-type-detect (done) — `taskType === "schedule"` already a confirmed branch
  downstream:
    - 3-e-5-inventory-template — same pattern, prediction (E2) not optimization
    - 3-e-6-excel-result-download — needs solve result; v1 we only prove the request fires
    - Real schedule solver implementation (M2-M3 backend; or-tools cp-sat or custom RCPSP)
---

# Story 3.E.4 — Schedule Template Mapping (PMR6)

## User Story

**As** 老张 (just confirmed "Schedule (排班/调度)" in 3.E.2's Modal),
**I want** the page to read my 任务 / 资源 / 工序 sheets, **automatically map** the columns to OptiCloud's Schedule schema, show me a **preview** ("here's what I built — 24 tasks, 5 resources, 18 precedence links, ready to solve"), and let me click **试跑** to send the request to the solver,
**so that** even though the schedule solver itself is still M2-M3 (returns 501 today), I have **proof** that my Excel was understood — I see the structured JSON, and I'm not blocked from validating the pipeline end-to-end for 3.E.9 vertical slice.

## Why this story

3.E.3 proved the VRPTW pattern. 老张 doesn't only have routing problems — many manufacturing customers send排班 / 任务调度 workbooks first. Without 3.E.4:

- Schedule users hit the "下一步：3.E.4" placeholder card → dead end (same disappointment 3.E.3 fixed for VRPTW)
- The 3.E.2 detector's `schedule` branch is unreachable in practice → no E2E signal it works
- 3.E.5 inventory + 3.E.9 vertical slice each waste cycles re-discovering the mapper pattern

This story replicates 3.E.3 for the schedule case — by design. The mapper module is new code; the backend route, parseExcel signature, submit helper, and Console page scaffold are **already in place** from 3.E.3.

**Why now (vs deferring to 3.E.5)**: Schedule appears more often than Inventory in 老张 surveys (排班 is the #2 use case after routing). Shipping it next preserves the 3.E pipeline's weekly cadence and keeps the per-template-mapper pattern fresh in memory.

## Out of scope

- **Real schedule solver implementation** — backend returns 501 today (already wired via 3.E.3's `/v1/optimizations/demo` short-circuit). M2-M3 will add `or-tools` cp-sat or a custom RCPSP solver in `solver-orchestrator/src/solvers.py`. When that ships, this story's API call automatically starts returning real results — no FE change needed.
- **3.E.5 Inventory template** — same pattern, prediction schema (FR E2); separate story
- **Manual column-mapping UI** — v1 uses automatic header→field mapping. If automatic mapping fails (missing required column), v1 shows a validation error with the missing fields listed; manual override is a v1.5 polish.
- **Optional 工序 (precedence) sheet** — if absent, schedule has no precedences (treat all tasks as independent); v1 supports this.
- **Result rendering** — 3.E.6 owns result download; 3.E.4 only proves the request fires + handles the response (success / 501 / error).
- **Solve cost / Credits charging** — Console is unauthenticated demo path; 5.A.4 charging applies only to authenticated `/v1/optimizations`.

## Acceptance Criteria

### AC1: New module `apps/web/src/lib/schedule-template.ts`

Pure function that takes the workbook summary (with rows) and returns either a structured payload OR a list of errors. Mirror shape of `vrptw-template.ts`.

```ts
import type { ExcelWorkbookSummary } from "./excel";

export interface ScheduleTask {
  id: string;
  duration: number;            // hours (or whatever unit user supplied; we don't convert)
  deadline: string | null;     // ISO date-like; pass through user's string
  resource: string | null;     // resource id required (matches ScheduleResource.id)
  earliest_start: string | null;
}

export interface ScheduleResource {
  id: string;
  capacity: number;
  type: string | null;
}

export interface SchedulePrecedence {
  predecessor: string;   // task id
  successor: string;
}

export interface SchedulePayload {
  task_type: "schedule";
  tasks: ScheduleTask[];
  resources: ScheduleResource[];
  precedences: SchedulePrecedence[];   // empty array if no 工序 sheet
  options?: { max_solve_seconds?: number };
}

export interface ScheduleErrorDetail {
  sheet: string;
  field?: string;
  message: string;
}

export type ScheduleMappingResult =
  | {
      ok: true;
      payload: SchedulePayload;
      task_count: number;
      resource_count: number;
      precedence_count: number;
      warnings: string[];
    }
  | {
      ok: false;
      errors: ScheduleErrorDetail[];
    };

export function buildSchedulePayload(summary: ExcelWorkbookSummary): ScheduleMappingResult;
```

Column-mapping heuristic (case-insensitive substring match against headers; sheet detection by name substring):

| Sheet alias | Sheet-name tokens (case-insensitive substring) |
|---|---|
| 任务 (tasks) | `任务` / `task` |
| 资源 (resources) | `资源` / `resource` / `shift` / `employee` |
| 工序 (precedences) | `工序` / `precedence` / `dependency` |

| Task field | Headers (any match) |
|---|---|
| `id` | 任务名 / 任务编号 / 名称 / id / task / name |
| `duration` | 工期 / duration / 耗时 |
| `deadline` | 截止 / deadline / due |
| `resource` | 资源 / resource |
| `earliest_start` | 最早开始 / earliest / start |

| Resource field | Headers |
|---|---|
| `id` | 编号 / 名称 / id / resource / name |
| `capacity` | 容量 / capacity / 数量 |
| `type` | 类型 / type / kind |

| Precedence field | Headers |
|---|---|
| `predecessor` | 前驱 / predecessor / from |
| `successor` | 后继 / successor / to |

Required:
- 任务 sheet with at least `id` + `duration` columns → missing → error
- 资源 sheet with `id` + `capacity` → missing → error
- 工序 sheet OPTIONAL — if absent, returns empty `precedences: []` (with a warning)

Validations (per row):
- `duration > 0` (numeric)
- `capacity > 0` (numeric)
- Empty / blank id rows → skipped (with a warning "Skipped N empty rows")
- Precedence rows where either id doesn't match a known task → counted as `unmatched` warning, row skipped

Warnings (returned in `warnings: []`):
- "Skipped N empty task rows" / "Skipped N empty resource rows"
- "工序 sheet not found — 已默认无前驱后继约束"
- "工序 sheet has M rows referencing unknown task ids"
- "N tasks reference resource not in 资源 sheet — 已忽略" (when task.resource doesn't match any resource.id)

### AC2: Reuse the existing backend `/v1/optimizations/demo` route

The route from 3.E.3 already short-circuits non-LP task_types to 501. **No backend code changes required.**

**Backend test added** to lock the schedule case:

In `apps/solver-orchestrator/tests/test_demo_optimizations.py`:

```python
async def test_demo_schedule_returns_501(client: AsyncClient) -> None:
    """Story 3.E.4 — schedule body returns 501 with friendly 'M2-M3' detail."""
    resp = await client.post(
        "/v1/optimizations/demo",
        json={
            "task_type": "schedule",
            "tasks": [{"id": "T1", "duration": 4}],
            "resources": [{"id": "R1", "capacity": 1}],
            "precedences": [],
        },
    )
    assert resp.status_code == 501
    body = resp.json()
    assert "M2-M3" in body["detail"]
    assert "schedule" in body["detail"]
```

solver-orchestrator 30 → **31** (+1).

### AC3: Console page integration — extend `ConfirmedCard`

In `apps/web/src/app/console/excel/page.tsx`:

1. Replace the early-return `if (taskType === "vrptw") return <VrptwPreviewCard … />;` with a branch for schedule too:

```tsx
if (taskType === "vrptw") {
  return <VrptwPreviewCard file={file} onReset={onReset} />;
}
if (taskType === "schedule") {
  return <SchedulePreviewCard file={file} onReset={onReset} />;
}
```

2. Add new `SchedulePreviewCard` component in the same file (mirror `VrptwPreviewCard` shape; copy-paste-and-adapt is fine — keep components self-contained for now, no premature abstraction):
   - Internally, re-parse the file with `{includeRows: true}`, then call `buildSchedulePayload(summary)`
   - If mapping fails: StatusCard variant="error" + list each `{sheet, field, message}` + "重新选择文件" button
   - If mapping succeeds:
     - Summary "✅ 已构建求解请求 — N 任务 / M 资源 / K 前驱后继"
     - Warnings panel (when present)
     - `<details>` collapsible JSON payload preview
     - "🚀 试跑" button → POST `/v1/optimizations/demo` via `submitOptimizationDemo(payload)`
   - After click:
     - Loading state during fetch
     - On 200: success card with `objective` + `solve_seconds`
     - On 501 (current expected): info card "Schedule 求解器即将上线 (M2-M3)" + link `/algorithms?task_type=schedule`
     - On other errors (422 / 5xx): error StatusCard with detail
3. Update the fallback `ConfirmedCard` placeholder copy: change "下一步：3.E.4 (Schedule) / 3.E.5 (Inventory) 将在 PR #22+ 接管 — VRPTW 已在 3.E.3 落地" → "下一步：3.E.5 (Inventory) 将在 PR #23+ 接管 — VRPTW (3.E.3) + Schedule (3.E.4) 已落地。"

`data-testid` for E2E:
- `schedule-preview-card`
- `schedule-submit-button`
- `schedule-501-card`
- `schedule-payload-json`

### AC4: FE handles 501 friendly

Same shape as 3.E.3's 501 path:

- StatusCard variant="info", title "Schedule 求解器即将上线 (M2-M3)"
- description: "您的数据已通过格式校验（{N} 任务 / {M} 资源）。求解器将在后续版本上线，届时本页面将直接返回结果。"
- Show constructed JSON payload below
- "→ 看其它求解器" link → `/algorithms?task_type=schedule` (filter by task_type so user sees what's available now)

### AC5: Vitest — schedule-template mapper

New `apps/web/src/lib/schedule-template.test.ts`:

1. `buildSchedulePayload — happy path: 3 sheets (任务/资源/工序) complete → ok=true, counts correct, precedences populated`
2. `buildSchedulePayload — missing 任务 sheet → ok=false with error`
3. `buildSchedulePayload — missing 资源 sheet → ok=false with error`
4. `buildSchedulePayload — missing required column (duration) → ok=false with field-level error`
5. `buildSchedulePayload — invalid duration (<=0) → ok=false with row-level error`
6. `buildSchedulePayload — 工序 sheet absent → ok=true with warning + precedences=[]`
7. `buildSchedulePayload — precedence referencing unknown task → ok=true with "M rows unknown task ids" warning`
8. `buildSchedulePayload — empty rows skipped with warning`

apps/web Vitest 15 → **23** (+8).

### AC6: Playwright E2E

Extend `e2e/tests/console-excel.spec.ts` with 1 new test:

`test("Schedule confirm → 试跑 → 501 'M2-M3' 友好卡片")`:
- Build a Schedule workbook in-memory (xlsx devDep, mirror VRPTW_BUFFER pattern): sheets 任务 / 资源 / 工序 with realistic columns
- Drop it via `file_upload`
- Confirm "Schedule (排班/调度)" in Modal (or manually override if detector picks something else)
- Expect SchedulePreviewCard visible with "N 任务" text
- Click "🚀 试跑" button
- Expect the 501 friendly card visible with "M2-M3" text
- Expect the constructed JSON visible in the `schedule-payload-json` `<pre>` block

Playwright total ~20 → **21** (+1).

### AC7: Quality gates

Standard set per `feedback_full_quality_gates`:
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy apps packages`
- `pnpm -C apps/web typecheck`
- `pnpm -C apps/web test` (Vitest)
- `pnpm -C packages/ui test` (Vitest — must stay at same baseline as before)
- `pnpm -C apps/web build`
- Backend pytest in solver-orchestrator (must all pass; smoke regression billing-service + auth-service)
- Playwright runs in CI

### AC8: NFR alignment

- **PMR6** ✅ second vertical template shipped (3.E pipeline now 4/9)
- **NFR-S** Demo route is unauthenticated (already documented in 3.E.3 / DR3); no new attack surface — same payload shape, same backend handler.
- **NFR-P1** Re-parsing with `includeRows` on confirm = ~100ms (same as VRPTW; documented as DR4 in opticloud-project-status).
- **FR E1** — POST `/v1/optimizations/demo` reused.

## Tasks

### T1 — Schedule mapper module + tests (1h)
1. Create `apps/web/src/lib/schedule-template.ts` per AC1 — mirror `vrptw-template.ts` shape:
   - SIGNALS constant for sheets + columns (Chinese + English aliases per AC1 tables)
   - `buildSchedulePayload(summary)` pure function
   - Helpers: `findSheet`, `findColumn`, `toNumber` (copy from vrptw-template OR extract to a shared `lib/excel-helpers.ts` IF the diff is clean — otherwise inline is fine; no premature abstraction)
2. Create `apps/web/src/lib/schedule-template.test.ts` — 8 cases per AC5

### T2 — Backend schedule 501 test (0.1h)
1. Append `test_demo_schedule_returns_501` to `apps/solver-orchestrator/tests/test_demo_optimizations.py` per AC2

### T3 — Console page SchedulePreviewCard (0.8h)
1. Add `SchedulePreviewCard` to `apps/web/src/app/console/excel/page.tsx` (mirror `VrptwPreviewCard`; same parsing → mapping → submit flow)
2. Extend `ConfirmedCard` branching: add `if (taskType === "schedule") return <SchedulePreviewCard … />`
3. Update fallback placeholder copy
4. Add `data-testid` per AC3
5. **Fix collision in `e2e/tests/console-excel.spec.ts:189-207`**: change the override-test's target from `schedule` (now routed to SchedulePreviewCard, breaking the assertion) to `inventory` (still falls through to `excel-confirmed-card` until 3.E.5). Change `selectOption({ value: "schedule" })` → `selectOption({ value: "inventory" })` and `/Schedule/` → `/Inventory/` in the assertion.

### T4 — E2E test (0.3h)
1. Add 1 Playwright test per AC6 to `console-excel.spec.ts`
2. Build schedule .xlsx in-memory using xlsx devDep (already installed by 3.E.2)

### T5 — Quality gates + sprint sync + PR (0.4h)
1. Run full gates per AC7
2. Update sprint-status.yaml: `3-e-4-schedule-template: done` + last_updated date
3. Commit on feature branch `feature/3-e-4-schedule-template`, push, open PR squash-merge to main

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Code duplication with `vrptw-template.ts` (findSheet / findColumn / toNumber) | Acceptable v1 — 3.E.5 will add the third copy; if symmetry persists, 3.E.5 PR refactors to a `lib/excel-helpers.ts` module. Do NOT pre-extract in this PR (3 occurrences is the rule-of-three threshold, not 2). |
| Column-mapping heuristics mis-detect resource type column as id | AC1 requires REQUIRED columns to all match; partial → error not silent acceptance |
| User's 工序 sheet uses `from` / `to` in English but task ids are Chinese — id-string compare may fail on whitespace | Trim ids in both 任务 sheet read and precedence read (mirror VRPTW's `String(rawId).trim()`) |
| 任务 sheet has `工期(小时)` header — substring match catches "工期" before "小时" | Heuristic is substring — matches first column whose name CONTAINS "工期"; if the workbook also has a "工期类型" column appearing first, that would mis-match. Mitigated by ordering: column resolver returns the FIRST matching index; if user has both, they can rename. Documented as v1 limitation (v1.5 manual override fix). |
| Schedule submit body has `tasks` / `resources` / `precedences` arrays — backend OptimizationRequest schema doesn't validate those (it's LP-centric) | Demo route bypasses OptimizationRequest validation for non-LP types (line 461 short-circuits to 501 before validation). No 422 risk. |
| 501 detail string says "M2-M3" — copy already shipped in 3.E.3 | Keep generic; do not promise specific dates in user-facing copy |
| Renaming the placeholder text in `ConfirmedCard` causes 3.E.3 Playwright text-match assertion to fail | 3.E.3's Playwright matches "下一步：3.E.4 (Schedule)" — this story's copy update removes the "3.E.4" reference. Check `e2e/tests/console-excel.spec.ts` for matching strings; if any assertion depends on the old copy, update it in same PR. |
| **Existing E2E `'其它' 切换为 schedule → 确认后 handoff 展示 schedule`** (`e2e/tests/console-excel.spec.ts:189-207`) drops a VRPTW workbook, manually overrides to `schedule`, then asserts `excel-confirmed-card` shows "Schedule" + "覆盖系统推荐". After 3.E.4 ships, schedule routes to `SchedulePreviewCard` (NOT the fallback card). This test **WILL break**. | **Fix in same PR (part of T3):** Switch the override target from `schedule` to `inventory` (still a fallback `excel-confirmed-card` route until 3.E.5 ships). Update the option value `selectOption({ value: "schedule" })` → `selectOption({ value: "inventory" })` and the assertion text `/Schedule/` → `/Inventory/`. This preserves the override-coverage signal until inventory itself takes over in 3.E.5 (where the same fix will repeat for `lp`/`unknown`). |

## Definition of Ready

- ✅ 3.E.3 shipped: `/v1/optimizations/demo` route + `submitOptimizationDemo` helper + parseExcel `{includeRows}` flag + `VrptwPreviewCard` reference pattern
- ✅ 3.E.2 detector recognizes `schedule` task_type
- ✅ apps/web Vitest infra in place (3.E.2)
- ✅ xlsx devDep available in `apps/web/package.json` (3.E.2 / 3.E.3)
- ✅ Backend test pattern established (test_demo_optimizations.py from 3.E.3)

## Definition of Done

- 8 ACs pass
- apps/web Vitest 15 → 23 (+8); solver tests 30 → 31 (+1); Playwright +1
- CI all green
- sprint-status updated to `done`
- Manual smoke: drop Schedule .xlsx → confirm → preview shows N 任务 / M 资源 + JSON → 试跑 → 501 friendly card

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
| 2 | ACs are testable & BDD-shaped | ✅ | Given/When/Then implicit via test names |
| 3 | Scope explicit (in/out) | ✅ | Out-of-scope section |
| 4 | Dependencies declared | ✅ | upstream 3.E.2 + 3.E.3; downstream 3.E.5 |
| 5 | Sizing estimate | ✅ | M (~2-3h) |
| 6 | Risks identified with mitigations | ✅ | 7 risks |
| 7 | Quality gates listed | ✅ | AC7 |
| 8 | Test plan: unit + integration + E2E | ✅ | Vitest x8 + backend x1 + Playwright x1 |
| 9 | Backwards compatibility considered | ✅ | Reuses 3.E.3 backend, no breaking change to demo route |
| 10 | Sources cited with line numbers | ✅ | Top frontmatter |

Round 1 result: **PASS**

---

## Round 2: 5-Perspective Review

### 🏗️ Architect

- ✅ Reuses existing `/v1/optimizations/demo` short-circuit (no new endpoint, no Pydantic schema changes)
- ✅ Pure FE pattern: parser → mapper → submit; no shared state, no race conditions
- ⚠️ Code duplication risk noted; deferring abstraction to rule-of-three trigger (3.E.5) is correct — pre-extraction at 2 occurrences is premature
- ✅ Component composition: each PreviewCard is self-contained; no prop drilling

### 👨‍💻 Dev

- ✅ Mapper signature matches vrptw — drop-in mental model
- ✅ Helpers (findSheet / findColumn / toNumber) can be inlined or copied; refactor deferred
- ✅ data-testids consistent with vrptw pattern
- ⚠️ Need to verify `e2e/tests/console-excel.spec.ts` doesn't assert against the "3.E.4 (Schedule)" placeholder text (risk row 7) — must check during T3

### 🧪 QA

- ✅ 8 mapper tests cover happy / structural-failure / data-validation / optional-sheet / soft-warning branches
- ✅ Backend 501 test mirrors 3.E.3's vrptw 501 test
- ✅ Playwright 1 test mirrors 3.E.3's vrptw flow — sufficient given mapper is unit-tested
- ⚠️ No test for the case where 任务 sheet has resources references but 资源 sheet is missing — covered by AC1 "missing 资源 sheet → ok=false"

### 🔐 Security

- ✅ Demo route is unauthenticated (already documented as DR3 in opticloud-project-status; M3 will add IP rate limit)
- ✅ No new attack surface — same JSON body shape, same 501 handler
- ✅ FE: file never leaves browser (parseExcel browser-side); no exfiltration risk

### 🛠️ SRE

- ✅ No new external dependency
- ✅ No new env var
- ✅ No DB migration (demo route doesn't persist)
- ✅ Telemetry: 501 responses already counted in solver-orchestrator's HTTP metrics

Round 2 result: **PASS** (1 medium-risk item flagged: verify Playwright doesn't break from copy change)

---

## Round 3: Dev-Readiness

- ✅ File paths absolute (apps/web/src/lib/schedule-template.ts, etc.)
- ✅ Types defined in AC1 — directly copy-pasteable
- ✅ Test names enumerated (8 mapper + 1 backend + 1 Playwright)
- ✅ Reference implementation: 3-e-3-vrptw-template.md + apps/web/src/lib/vrptw-template.ts
- ✅ Sizing realistic (~2-3h based on 3.E.3 actual = 4h with 30% reduction from skipping backend route work)
- ✅ Sprint-status update path declared

Round 3 result: **PASS — READY FOR DEV**

---

## Implementation Notes

- The 3.E.3 mapper uses `String(rawId).trim()` for ids; mirror that consistently
- The 3.E.3 mapper validates ranges (lat/lng/demand); schedule's analog is `duration > 0` and `capacity > 0`
- `toNumber` returns `null` for blank cells; mapper treats `null` as "skip row" (for id) or "validation error" (for duration/capacity)
- Empty workbooks: if 任务 sheet has 0 data rows, mapper returns `ok: false` with "任务 sheet 没有任何有效数据行" — match vrptw behavior

Completion note: "Ultimate context engine analysis completed — comprehensive developer guide created (3.E.4 schedule template, mirrors 3.E.3 pattern; backend reuse; 8 mapper tests + 1 backend + 1 E2E)."
