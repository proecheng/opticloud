---
story_key: 2-3-tier-based-browse
epic_num: 2
story_num: 2.3
epic_name: Algorithm Catalog & Solver Selection
status: ready-for-dev
priority: 🟢 Medium (FR C3 v1 必上; light follow-up to 2.1/2.2 — pushes Epic 2 to 3/8 done)
sizing: S (~1.5-2 hours; backend gets one query param, FE refactors filter UI, +2 backend tests + 2-3 Playwright)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L57 (FR C3 — browse by tier T1-T6 / P1-P5)
  - _bmad-output/planning/epics.md L1370-1372 (Story 2.3 spec)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py:63-68 (existing list_algorithms — has task_type filter, no tier filter)
  - apps/solver-orchestrator/src/solver_orchestrator/catalog.py (8 SKUs with tier ∈ {T1, T2, T3, T4, T5, P1, P2, P3})
  - apps/web/src/app/algorithms/page.tsx:96-116 (existing 3-button optimization/prediction/all filter)
dependencies:
  upstream:
    - 2-1-j1-algorithms-public-list (done) — list page + lib/api.ts client
    - 2-2-algorithm-details (done) — card → detail page Link wiring
  downstream:
    - 8-c-5-algorithm-capability-card — Tier 2 CapabilityCard component (v1 末); will replace the simple `<li>` cards with richer cards but tier filter UI stays
    - 6-a-1-citation-bibtex — detail-page additions, independent
---

# Story 2.3 — Tier-based Algorithm Browse (FR C3)

## User Story

**As** a sales engineer / academic evaluator scanning the catalog,
**I want** to filter the algorithm list by specific tier (e.g., T1 / T3 / P2) — not just the broad optimization-vs-prediction split — so I can quickly answer "what does OptiCloud offer at the highest-quality tier in my domain" without manually skimming all 8 cards (more in future),
**so that** an enterprise buyer evaluating us alongside Gurobi can immediately see our T-tier coverage; an academic looking for forecasting can land on P-tier in one click.

## Why this story

The list page (2.1) currently has a 3-button toggle — `全部 / 优化 (T1-T6) / 预测 (P1-P5)`. That's binary — it doesn't let users zoom in on a specific tier. As the catalog grows from 8 SKUs to 20+ in M2-M3, the binary split scales poorly:

- A power user looking for "best-quality LP" (T1 = HiGHS open-source vs T2 = HiGHS MILP commercial) needs per-tier filtering to compare
- The backend `GET /v1/algorithms` accepts `?task_type=` but NOT `?tier=` — FR C3 explicitly requires the latter

This story is a tight loop:

1. Backend: add `?tier=T3` query param to `list_algorithms`
2. FE: replace the 3-button toggle with a tier multi-select chip group (T1-T6 / P1-P5 chips, multi-toggle), keeping the "全部" reset behavior
3. URL query sync (`/algorithms?tier=T1,T3`) so the filtered view is bookmarkable / shareable in demos

**Out of scope** (each pointed at owning story):
- **CapabilityCard component** — Tier 2 component, Story 8.C.5 v1 末
- **Combined filters** (tier + task_type + status) — could be future polish; this story does ONLY tier
- **Tier provenance text** (what "T3 means") — defer to algorithm detail page (2.2) per-card
- **Sort order** — current implicit insertion order is fine; alpha-sort by k_algo could be a follow-up
- **Pagination** — 8 SKUs today; not needed until catalog > 50

## Acceptance Criteria

### AC1: Backend — `?tier=` query param

In `apps/solver-orchestrator/src/solver_orchestrator/routes.py:list_algorithms`:

```python
async def list_algorithms(
    task_type: str | None = None,
    tier: str | None = None,
) -> list[AlgorithmSchema]:
    items = CATALOG
    if task_type:
        items = [a for a in items if a["task_type"] == task_type]
    if tier:
        wanted = {t.strip() for t in tier.split(",") if t.strip()}
        items = [a for a in items if a["tier"] in wanted]
    return [AlgorithmSchema.model_validate(a) for a in items]
```

Behavior:
- `?tier=T1` → only T1 SKUs (1 result: highs-lp)
- `?tier=T1,T2` → T1 + T2 (2 results: highs-lp + highs-milp)
- `?tier=T9` (unknown) → empty list (NOT 422; matches `?task_type=garbage` behavior — list endpoints are permissive)
- `?tier=` (empty after split) → falls through to no filter (same as omitting)
- Combinable with `task_type`: `?task_type=forecast&tier=P1` → 1 result (arima-forecast)

Update OpenAPI summary/description note: "FR C1 + C3 — public algorithm list, optional `task_type` and/or `tier` (comma-separated multi) filters."

### AC2: Backend tests

Extend `apps/solver-orchestrator/tests/test_algorithm_details.py` (or new file `test_algorithm_list.py` — implementer's choice; the test_algorithm_details file is short and topic-adjacent):

1. `test_list_filters_by_single_tier` — GET `/v1/algorithms?tier=T1` → [highs-lp]
2. `test_list_filters_by_comma_separated_tiers` — `?tier=T1,P1` → exactly 2 results (highs-lp + arima-forecast)
3. `test_list_unknown_tier_returns_empty_list` — `?tier=T9` → `[]` + 200
4. `test_list_combines_task_type_and_tier` — `?task_type=forecast&tier=P1` → [arima-forecast]
5. `test_list_with_empty_tier_param_returns_all` — `?tier=` (empty string) → returns all 8 (no filter applied)

Solver test count: 22 → **27** (+5).

### AC3: lib/api.ts — extend `listAlgorithms` signature

```ts
export interface ListAlgorithmsOptions {
  taskType?: string;
  tier?: string[]; // ["T1", "P2"] — joined client-side
}

export async function listAlgorithms(
  options: ListAlgorithmsOptions = {},
): Promise<Algorithm[]> {
  const params = new URLSearchParams();
  if (options.taskType) params.set("task_type", options.taskType);
  if (options.tier && options.tier.length > 0) params.set("tier", options.tier.join(","));
  const qs = params.toString();
  const path = qs ? `/v1/algorithms?${qs}` : "/v1/algorithms";
  return request<Algorithm[]>(path, {}, SOLVER_SERVICE_URL);
}
```

Note: existing call sites (`apps/web/src/app/algorithms/page.tsx`) use `listAlgorithms()` with no args — backwards-compatible since `options = {}` defaults.

### AC4: FE — tier chip group + URL sync

In `apps/web/src/app/algorithms/page.tsx`:

1. **Replace** the existing 3-button toggle (`全部 / 优化 / 预测`) with a 2-row tier chip group:
   - Row 1: 优化 — `[T1] [T2] [T3] [T4] [T5] [T6]`
   - Row 2: 预测 — `[P1] [P2] [P3] [P4] [P5]`
   - Each chip = `<button>` with selected/unselected styles; click toggles in/out of a `Set<string>` state
   - A "全部" reset button on the right (or a "清除筛选" button when any chip selected)
2. **Server-side filtering**: when chip set changes, re-fetch via `listAlgorithms({ tier: [...chipSet] })` (or pass empty when set is empty)
3. **URL query sync**: when chip set changes, update URL via `router.replace('/algorithms?tier=T1,T3', { scroll: false })`. On mount, read `searchParams.get("tier")` to hydrate the initial chip set.
4. Visual: keep the existing TIER_COLOR map (already defined at the top of the file) so chips and card badges use the same color tokens
5. Empty result state: keep the existing `EmptyState` rendering — "此分类暂无算法" is appropriate for empty filter results

### AC5: Filter behavior — server-side, not client

Today the page filters client-side (filters the already-fetched 8 cards). This story switches to **server-side** filtering (re-fetch on chip change), which:

- Matches FR C3 contract: `GET /v1/algorithms?tier=T3` is the canonical filter
- Scales when catalog grows past 50 SKUs (M3+)
- Trade-off: small extra latency (~50ms per chip click); acceptable for sub-second LAN/CDN; CN users likely <200ms

Mitigation for poor UX during refetch: render `<LoadingShimmer>` while `algos === null` between fetches (existing behavior, no change needed).

### AC6: E2E tests (Playwright)

Add to `e2e/tests/algorithms-catalog.spec.ts` (extend existing file):

1. `test("点击 T1 chip 只显示 T1 SKU")` — goto `/algorithms`; click chip with text `T1`; assert exactly 1 card visible; assert that card contains `highs-lp`
2. `test("点击 T1 + P1 chip 显示两个 SKU")` — click T1 then P1 chips; assert exactly 2 cards visible (highs-lp + arima-forecast)
3. `test("URL ?tier=T1,T3 hydrates 初始 chip 选中状态")` — `goto('/algorithms?tier=T1,T3')`; assert T1 chip has selected styles (background color); assert cards shown match the filter; assert URL still contains `tier=T1,T3` after page settles

Playwright total: 12 → **15** (+3).

### AC7: Quality gates

- `uv run ruff check apps packages` → 0
- `uv run ruff format --check apps packages` → 0
- `uv run mypy apps packages` → 0
- `pnpm -C apps/web build` → 0
- `pnpm -C apps/web typecheck` → 0
- `pnpm -C e2e typecheck` → 0
- `pnpm -C packages/ui test` → 22 pass + 12 pre-existing a11y fails (unchanged)
- Solver tests via CI (local Chinese-path .pth blocker still in effect)

### AC8: NFR alignment

- **FR C3** ✅ AC1 backend + AC4 FE
- **FR C1** preserved (route still public no-auth)
- **NFR-A1** chip buttons keep `min-h-touch`, use existing color tokens (a11y-audited)
- **NFR-P1** server-side filter adds one round-trip per chip toggle; backend in-process catalog scan (no DB) → <10ms backend; total <200ms on LAN
- **NFR-S** N/A (catalog is static)

## Tasks

### T1 — Backend `?tier=` param (0.2h)
1. Edit `routes.py:list_algorithms` per AC1
2. Update docstring + OpenAPI description

### T2 — Backend tests (0.3h)
1. Add 5 tests per AC2 into `test_algorithm_details.py` (file becomes "algorithm details + list tests" in spirit; or split into `test_algorithm_list.py` — implementer's choice)

### T3 — lib/api.ts (0.15h)
1. Refactor `listAlgorithms` signature per AC3 (kept backward-compatible)
2. Verify existing callers still compile

### T4 — FE chip group + URL sync (0.7h)
1. In `apps/web/src/app/algorithms/page.tsx`:
   - Import `useSearchParams` + `useRouter` from `next/navigation`
   - **Next.js 15 Suspense requirement**: `useSearchParams` requires the consuming component to be inside `<Suspense>`. Refactor the page: extract the body into an inner `AlgorithmsContent` client component; the default export becomes a thin wrapper rendering `<Suspense fallback={<LoadingShimmer />}><AlgorithmsContent /></Suspense>`. Without this, Next 15 build errors with "useSearchParams() should be wrapped in a suspense boundary at page ..."
   - Replace 3-button toggle with the chip group per AC4
   - Add `selectedTiers: Set<string>` state, hydrated from URL on mount via `useMemo(() => new Set(searchParams.get("tier")?.split(",").filter(Boolean) ?? []), [])` (empty dep array — hydrate ONCE)
   - `useEffect`: on `selectedTiers` change → call `listAlgorithms({ tier: [...selectedTiers] })` AND update URL via `router.replace`
   - Add `data-testid` attributes on chips: `tier-chip-T1` / `tier-chip-P1` etc. for E2E selectors
2. Remove the now-unused client-side `filtered` filter logic — server returns already-filtered list

### T5 — Playwright E2E (0.3h)
1. Add 3 tests per AC6 into `algorithms-catalog.spec.ts`

### T6 — Quality gates + sprint sync + PR (0.4h)
1. Run AC7 gates
2. sprint-status: `2-3-tier-based-browse: done`
3. memory update
4. commit + PR + CI wait + merge

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Switching from client-side to server-side filter means rapid chip toggling spawns many fetches | Mitigation 1: each fetch is <100ms; spam-clicking is rare in real use. Mitigation 2 (defer): debounce by 100ms if needed in 2.3.5; v1 no debounce — keep simple |
| URL query sync triggers `useEffect` re-fetch loop (URL update → searchParams change → re-fetch → re-set URL) | Hydrate URL ONCE on mount; on chip change, `router.replace` (no reload). Track `isHydrated` ref to ignore the initial `searchParams` echo |
| `?tier=` empty string parsing | AC1: explicitly handles via `split(",").filter(Boolean)`; AC2 #5 locks this in a test |
| Backwards-compat of `listAlgorithms()` callers (no args today) | New signature defaults `options = {}`; existing callers unchanged. T3 verifies via pnpm build |
| Backend semantics for comma list — what if user does `?tier=T1&tier=T2` (duplicate query)? | FastAPI default: only the last `tier=` wins. Story only documents the comma-separated form. Duplicate-query-param semantics out of scope (consistent with `task_type` behavior) |
| Selected chip color clash — T5/P5 use warning/danger tokens which on selected state may look harsh | Inherit existing TIER_COLOR map; for selected state add `ring-2 ring-primary/40` to give a subtle "selected" outline without changing the tier's own color. Story does NOT redesign tier color tokens |
| Multi-row chip layout overflow on mobile | Use `flex flex-wrap gap-2` — wraps naturally on narrow viewports |

## Non-Functional Requirements Mapping

- **FR C3** ✅ AC1 + AC4
- **FR C1** preserved (public no-auth)
- **NFR-A1** chip buttons keep touch-target + a11y semantics
- **NFR-P1** in-process catalog scan + 1 fetch per chip click — well within budget
- **NFR-S** N/A

## Definition of Ready

- ✅ Backend catalog data has `tier` field on every SKU
- ✅ List page exists + uses lib/api.ts client (2.1)
- ✅ TIER_COLOR map exists on the page
- ✅ Playwright `algorithms-catalog.spec.ts` exists — easy to extend

## Definition of Done

- All 8 ACs pass
- Solver tests 22 → 27 (+5)
- Playwright 12 → 15 (+3)
- CI 全绿
- sprint-status: `2-3-tier-based-browse: done`
- Memory updated
- Manual smoke: `/algorithms?tier=T1,P1` → 2 cards shown + URL preserved

## Sign-off

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Catalog Lead | TBA | ☐ | — |
| FE Lead | TBA | ☐ | — |

> Owner committee deferred per M0 skip.
