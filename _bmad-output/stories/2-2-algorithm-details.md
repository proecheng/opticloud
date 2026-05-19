---
story_key: 2-2-algorithm-details
epic_num: 2
story_num: 2.2
epic_name: Algorithm Catalog & Solver Selection
status: ready-for-dev
priority: 🟢 Medium (FR C2; demo content polish; unblocks J1 SDK on-ramp + 学界/投资人 deep-dive page)
sizing: S (~2-3 hours; backend route already exists, FE detail page + 2 examples + E2E + 1 solver test)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L1366-1368 (Story 2.2 — Algorithm Details FR C2)
  - _bmad-output/planning/prd.md §FR.2 (Algorithm Catalog C1-C8)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py L71-84 (GET /v1/algorithms/{k_algo} — already shipped in 0.6)
  - apps/solver-orchestrator/src/solver_orchestrator/catalog.py (8 SKU catalog with examples[])
  - apps/web/src/app/algorithms/page.tsx (existing list page from Story 2.1)
  - apps/web/src/lib/api.ts L133-159 (listAlgorithms + Algorithm interface)
  - e2e/tests/algorithms-catalog.spec.ts (existing list-page E2E pattern)
dependencies:
  upstream:
    - 0-6-auth-scaffold (done) — catalog module + `GET /v1/algorithms/{k_algo}` route shipped
    - 2-1-j1-algorithms-public-list (done) — list page + lib/api.ts catalog client
    - 0-13-playwright-e2e (done) — E2E harness + fixtures + `algorithms-catalog.spec.ts` pattern
  downstream:
    - 2-3-tier-based-browse — adds tier filter (will reuse the detail page link)
    - 6-a-1-citation-bibtex — academic citations rendered on the detail page (v1 必上 FR R5)
    - 8-c-8-algorithm-provenance-page — v1 末; deeper "Algorithm Provenance" page (论文 + 配置参数 + 适用场景) extending this v1 detail page
---

# Story 2.2 — Algorithm Details Page (FR C2)

## User Story

**As** a developer / sales engineer / academic evaluator who landed on `/algorithms` and clicked an algorithm card,
**I want** a public, no-login detail page that shows me the algorithm's full schema, copy-pasteable Python + cURL examples, provider transparency (kind / version / provider_url), and a one-click path to "try it now",
**so that** I can decide within 30 seconds whether this SKU fits my problem, paste the example into my terminal to feel the API ergonomics, and convert into a signup if I want my own API key — without ever needing to read the OpenAPI spec.

## Why this story

The list page (Story 2.1) shows 8 SKUs as one-line cards. A user who wants to dig in has nowhere to go — they have to read the OpenAPI spec via `/docs` (developer-only) or guess at the request shape. This is a J1 conversion leak: "interested → confused" instead of "interested → tried it".

The detail page closes that gap. The backend already returns the full `AlgorithmSchema` (incl. `examples[]` with name / input / description) at `GET /v1/algorithms/{k_algo}` — only `highs-lp` has a real example today, but the contract is locked. The FE renders that payload into a copy-pasteable Python snippet + cURL snippet (synthesized from the example.input + a placeholder API key), plus tier / status / provider metadata.

Conversion path: each detail page CTAs to `/auth/signup` ("3 分钟拿 API Key") and to `/demo/charge` ("免登录试跑 Hello World LP" — only enabled when `task_type=lp` since that's the only thing /demo/charge supports today).

## Out of scope

- **Real academic citations / BibTeX** — that's Story 6.A.1 (FR R5 v1 必上); v1 detail page just shows `provider_url` as the citation anchor
- **Capability JSON Schema rendering** — full input/output JSON schema rendering (Monaco / RJSF) is 8.C.5 CapabilityCard; v1 just dumps `examples[0].input` as syntax-highlighted JSON
- **Multi-example carousel / tabs** — current catalog has at most 1 example per SKU; render `examples[0]` only with a "more examples coming" footnote when `examples.length === 0`
- **Algorithm Provenance (Innovation #6 论文 / 配置参数 / 适用场景)** — Story 8.C.8 v1 末; v1 just renders `description_zh` + `description_en`
- **Tier filter / browse-by-tier** — Story 2.3
- **i18n switch** — global zh/en toggle is Story 1.10; v1 detail page renders both languages side by side (consistent with list page)
- **Adding more `examples[]` to catalog SKUs** — most SKUs have `examples: []` today. v1 ships with an empty-state for them. Backfilling content for VRPTW / CP-SAT / Chronos / ARIMA / LSTM is a follow-up content task, not in this story (tracked as a non-blocking debt note in §Risks)
- **JWT-gated "try in console" run button** — v1 just renders the cURL/Python snippet for copy-paste; one-click execution from the page requires the in-browser API key flow (out of v1 scope)
- **SEO / og:image / structured data** — defer to a marketing polish PR

## Acceptance Criteria

### AC1: Backend route + 404 path verified

The route `GET /v1/algorithms/{k_algo}` already exists (`apps/solver-orchestrator/src/solver_orchestrator/routes.py:71-84`). This story adds a regression test asserting:

1. `GET /v1/algorithms/highs-lp` → 200; body has `k_algo == "highs-lp"`, `task_type == "lp"`, `tier == "T1"`, `model_version.provider_url == "https://highs.dev/"`, `examples[0].name == "Hello World LP"`
2. `GET /v1/algorithms/does-not-exist` → 404; body `detail` contains `"unknown k_algo: does-not-exist"`

No backend code change — just the missing test (gap revealed: 0.6 shipped the route without explicit coverage; `test_billing_integration.py` and `test_billing_reconciler.py` don't exercise it).

### AC2: New FE route `/algorithms/[k_algo]/page.tsx`

A Next.js dynamic route that:
- Reads `k_algo` from `params` (Next.js 15 app-router convention — `params` is a Promise in 15.x; resolve via `use(params)` or `await` in a server-side wrapper. Implementation may use a `"use client"` page + `useParams()` hook to stay parallel with the existing list page pattern, avoiding the params-promise complexity).
- Fetches `GET /v1/algorithms/{k_algo}` via a new `getAlgorithm(k_algo)` helper in `apps/web/src/lib/api.ts`.
- Renders **three sections**:
  1. **Header** — `<h1>{k_algo}</h1>` + tier badge + status badge + zh description + en description + `task_type` chip + Provider transparency row (provider_id / kind / version / provider_url link)
  2. **Try it now** — Python snippet + cURL snippet (see AC3). Two-column code blocks on desktop, stacked on mobile.
  3. **Example input JSON** — `<pre>` with `JSON.stringify(examples[0].input, null, 2)` when examples exist; empty-state card "示例输入即将上线（M2）" when `examples.length === 0`.
- 404 handling: if the API returns 404 (or `OptiCloudClientError` with `status === 404`), show a centered "未知算法：{k_algo}" card + "返回算法目录" link.
- Loading state: reuse `LoadingShimmer` (3 cards stacked) consistent with list page.
- Error state (non-404): reuse `StatusCard variant="error"` consistent with list page.

### AC3: Code snippet generation

**Python snippet** template (uses example.input as request body):
```python
import os
import requests

API_KEY = os.getenv("OPTICLOUD_API_KEY", "sk-...")
BASE_URL = os.getenv("OPTICLOUD_BASE_URL", "https://api.opticloud.cn")

# {{algo.description_zh}}
resp = requests.post(
    f"{BASE_URL}/v1/optimizations",
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Idempotency-Key": "demo-001",  # change per call (P23)
    },
    json={{JSON_PRETTY}},
    timeout=60,
)
resp.raise_for_status()
print(resp.json())
```

**cURL snippet** template:
```bash
curl -X POST https://api.opticloud.cn/v1/optimizations \
  -H "Authorization: Bearer ${OPTICLOUD_API_KEY:-sk-...}" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-001" \
  -d '{{JSON_COMPACT}}'
```

Each snippet has a "📋 Copy" button (uses `navigator.clipboard.writeText`) that flashes "已复制" for 1.5s. If `examples.length === 0`, render a single placeholder snippet that uses `{"task_type": "{{algo.task_type}}", ...}` and a "示例载荷待补充" inline note (degraded but still copyable).

### AC4: Link from list page → detail page

In `apps/web/src/app/algorithms/page.tsx`:
- Wrap each `<li className="rounded-lg ...">` card content (the entire card minus the existing `<details>` examples block) in `<Link href={`/algorithms/${algo.k_algo}`}>`. Use a `block` link style so the card stays clickable as a whole.
- Keep the `<details>` examples block OUTSIDE the link so users can expand it without navigating (preserves current UX).
- Add `aria-label={`查看 ${algo.k_algo} 详情`}` on the link for screen readers.
- The existing `data-testid="algorithm-card"` attribute stays on the `<li>` (E2E selector compatibility — `algorithms-catalog.spec.ts` depends on it).

### AC5: Detail-page CTA → try-it-now path

At the bottom of the detail page, two CTAs side-by-side:
1. **Primary** — `<Link href="/auth/signup">3 分钟注册拿 API Key</Link>` (always shown; matches list-page footer copy)
2. **Secondary** — `<Link href="/demo/charge">免登录试跑 ChargeModal (J1 路径)</Link>` (only when `algo.task_type === "lp"` — the only task /demo/charge currently supports)

### AC6: E2E tests (Playwright)

Add `e2e/tests/algorithm-details.spec.ts`:

1. `test("从列表页点击 highs-lp 跳转到详情页")` — visit `/algorithms`, locate the card via `page.locator('[data-testid="algorithm-card"]').filter({ hasText: "highs-lp" }).first()`, click its embedded `<a>` link, assert URL ends with `/algorithms/highs-lp`, assert h1 contains `highs-lp`, assert Provider row contains `https://highs.dev/`.
2. `test("详情页展示 Python + cURL 两个代码段 + 复制按钮")` — visit `/algorithms/highs-lp` directly; assert `getByTestId("snippet-python")` visible, contains `requests.post`, contains `"task_type": "lp"`; assert `getByTestId("snippet-curl")` visible, contains `curl -X POST`; assert at least 2 `getByRole("button", { name: /复制/ })`.
3. `test("未知 k_algo 显示 404 状态卡")` — visit `/algorithms/does-not-exist`, assert `getByTestId("algorithm-detail-404")` is visible AND its text contains `未知算法`; assert "返回算法目录" link is visible.
4. `test("空 examples 的 SKU 也能打开详情页")` — visit `/algorithms/highs-milp` (examples=[]); FIRST assert h1 contains `highs-milp` AND `getByTestId("algorithm-detail-404")` is NOT visible (success path); THEN assert `getByTestId("snippet-placeholder")` is visible AND its text contains `示例载荷待补充` (degraded-state path).

### AC7: Backend tests (solver-orchestrator)

Add to `apps/solver-orchestrator/tests/test_algorithm_details.py` (new file):

1. `test_get_algorithm_returns_full_detail` — async client GET `/v1/algorithms/highs-lp` → 200 + matches AC1 #1 expectations
2. `test_get_algorithm_404_for_unknown_k_algo` — async client GET `/v1/algorithms/zzz` → 404 + body matches AC1 #2
3. `test_get_algorithm_empty_examples_still_200` — async client GET `/v1/algorithms/highs-milp` → 200 + `examples == []` (regression guard for the empty-state UI path)

Test count: solver-orchestrator 19 → 22 (+3).

### AC8: Quality gates (per `feedback_full_quality_gates`)

- `uv run ruff check apps packages` → 0 errors
- `uv run ruff format --check apps packages` → 0 changes needed
- `uv run mypy apps packages` → 0 errors
- All Python regression tests pass (billing-service 135 + outbox-relayer 8 + shared-py 17 + python-sdk 5 + auth-service 27 + solver-orchestrator 22 = **214** Python)
- `pnpm -C apps/web build` → 0 errors
- `pnpm -C packages/ui test` → existing Vitest still passes (ChargeModal 8 + useA11y 4 = 12; 12 pre-existing a11y failures unchanged)
- E2E: optional local-run smoke (`pnpm -C e2e test --grep algorithm-details`) — CI runs full E2E suite anyway

### AC9: NFR alignment

- **FR C2** ✅ AC1 + AC6 implement + verify
- **NFR-A1** (a11y P0): list-page card links carry `aria-label`; detail page uses semantic `<h1>` / `<h2>` / `<code>` / `<pre>`; tier+status badges use the same color tokens as list page (already a11y-audited in Story 0.12)
- **NFR-S** (no auth bypass): detail route is public (FR C1 says catalog is unauthenticated); no PII or tenant data leaks because the catalog is static config
- **NFR-P1** (latency): detail page is one GET fetch with no DB hit (CATALOG is in-process Python list); P95 < 50ms backend; FE TTFB depends on Next.js dev/prod mode (irrelevant for v1 metric)
- **NFR-O7** (next_action_url): 404 response already includes implicit "next" via the 'list' CTA; no programmatic `next_action_url` field needed because the response is HTML, not JSON (FE controls the UX)

## Tasks

### T1 — Backend regression tests (0.3h)
1. Create `apps/solver-orchestrator/tests/test_algorithm_details.py`
2. Three tests per AC7 — reuse existing async test client pattern from `test_billing_integration.py`
3. Verify: `uv run --directory apps/solver-orchestrator pytest tests/test_algorithm_details.py -v` → 3 passed

### T2 — lib/api.ts `getAlgorithm()` helper (0.2h)
1. In `apps/web/src/lib/api.ts`, after `listAlgorithms()` (L157), add:
   ```ts
   export async function getAlgorithm(kAlgo: string): Promise<Algorithm> {
     return request<Algorithm>(
       `/v1/algorithms/${encodeURIComponent(kAlgo)}`,
       {},
       SOLVER_SERVICE_URL,
     );
   }
   ```
2. `pnpm -C apps/web typecheck` (or `pnpm -C apps/web build`) → no TS errors

### T3 — Detail page route (1h)
1. Create `apps/web/src/app/algorithms/[k_algo]/page.tsx` (Next.js dynamic route)
2. Use `"use client"` + `useParams()` hook to get `k_algo` (parallel to list-page pattern; avoids Next 15 params-promise complexity).
   - **Type-narrowing note**: `useParams()` returns `Record<string, string | string[]>`. Read with `const params = useParams<{ k_algo: string }>(); const kAlgo = Array.isArray(params.k_algo) ? params.k_algo[0] : params.k_algo;` (guards against TS strict-mode + catches the multi-segment catch-all case which we don't use but the type allows).
3. State machine: `loading` → fetch → `success | error(404) | error(other)` — switch on `OptiCloudClientError.status === 404` to pick the 404 card branch
4. Render three sections per AC2 + two CTAs per AC5
5. Add `data-testid` attributes used by AC6 E2E tests: `algorithm-detail-header`, `snippet-python`, `snippet-curl`, `algorithm-detail-404`, `snippet-placeholder`

### T4 — Code snippet generation + copy button (0.5h)
1. Implement two `<CodeBlock>` inline components (or one shared) that take `lang: "python" | "bash"` + `code: string` + render `<pre>` with `font-mono text-xs` + a "📋 复制" `<button>` in the top-right corner
2. Use `navigator.clipboard.writeText(code)` on click; show "已复制" toast inline for 1.5s via local state
3. Compose the Python snippet from the template in AC3 with `JSON.stringify(examples[0].input, null, 2)` indented; cURL snippet uses `JSON.stringify(examples[0].input)` (compact) inline
4. Empty-state: if `examples.length === 0`, generate a placeholder snippet with `{"task_type": algo.task_type, "minimize": {"c": [1]}, "st": {"A": [[1]], "b": [1]}}` and a `<p>示例载荷待补充（M2 内补齐其余 7 个 SKU）</p>` note

### T5 — Wire list-page cards to detail pages (0.2h)
1. In `apps/web/src/app/algorithms/page.tsx`, wrap the upper half of each card (`<div className="flex items-start ...">` through the Provider row) in `<Link href={`/algorithms/${algo.k_algo}`} aria-label={`查看 ${algo.k_algo} 详情`} className="block hover:opacity-90">`.
2. Keep the existing `<details>` block outside the link.
3. Keep `data-testid="algorithm-card"` on the `<li>` (existing E2E selector).

### T6 — E2E tests (0.5h)
1. Create `e2e/tests/algorithm-details.spec.ts` with the 4 tests from AC6
2. Use the existing `../fixtures` import pattern from `algorithms-catalog.spec.ts`
3. Local run: `pnpm -C e2e test --grep "algorithm-details"` → 4 passed (chromium only)

### T7 — Quality gates + sprint sync + PR (0.3h)
1. Run AC8 gates (ruff / format / mypy / Python tests / pnpm build / Vitest)
2. Update `_bmad-output/stories/sprint-status.yaml`: `2-2-algorithm-details: done`
3. Update memory `opticloud-project-status.md` with the new test counts + PR ref
4. Commit on `feature/2-2-algorithm-details` + push + `gh pr create`
5. Wait CI green → squash merge to main + local `git reset --hard origin/main`

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| 7/8 SKUs have `examples: []` — placeholder snippets look weak for sales demo | AC3 placeholder + footnote acknowledges; backfill is a non-blocking content task (file a separate "catalog-examples-backfill" backlog item — NOT in this story) |
| Next.js 15 `params` is a Promise — `useParams()` hook returns synchronously but is client-only | T3 chooses `"use client"` + `useParams()` to keep page parallel to list page (also client-side); both pages are public no-auth so SSR isn't required |
| Copy button needs `navigator.clipboard` (HTTPS only in modern browsers) | Local dev (http://localhost:3000) — Chrome treats localhost as secure context; production must be HTTPS (already the case per architecture); if `clipboard` API missing, fall back to `<textarea>` select+execCommand (deferred to follow-up if reported) |
| List-page wrapping in `<Link>` could break the existing `<details>` expand UX (clicks bubble to navigate) | T5 keeps `<details>` OUTSIDE the `<Link>`; explicit AC4 design |
| E2E test #2 asserts on specific snippet substrings — fragile if snippet template changes | Substrings chosen are the stable parts (`requests.post`, `"task_type": "lp"`, `curl -X POST`); template-internal whitespace/order changes won't break them |
| Adding 4 new E2E tests may push CI E2E time over budget | Existing E2E run is ~30s for 3 tests; +4 tests likely +40s = ~70s total. Well under any threshold |
| Backend route's 404 returns `HTTPException(detail=...)` — plain FastAPI shape, NOT RFC 7807 (FG1.3 inconsistency) | Documented as DR2 tech debt — Story 3.7 will sweep RFC7807 across all routes. Not in 2.2 scope. AC7 asserts current shape (`detail` substring) so the test guards regressions until 3.7 lands |

## Non-Functional Requirements Mapping

- **FR C2** ✅ AC1 + AC2 + AC6 + AC7
- **FR C1** ✅ no-auth assumption preserved (detail route is public, same as list)
- **NFR-A1 a11y P0** ✅ AC4 aria-label + semantic HTML
- **NFR-S** N/A (static catalog, no PII)
- **NFR-P1** ✅ in-process catalog, no DB hit
- **NFR-O7** N/A (HTML page, FE controls "next action" via CTAs)

## Definition of Ready

- ✅ Backend route already shipped in 0.6 — no API contract change needed
- ✅ List page (2.1) + lib/api.ts catalog client + Algorithm interface already exist
- ✅ E2E harness (0.13) + fixtures + existing `algorithms-catalog.spec.ts` pattern
- ✅ LoadingShimmer / EmptyState / StatusCard already in `@opticloud/ui`
- ✅ 3-pass review applied (next: review rounds 1-3)

## Definition of Done

- All 9 ACs pass
- Test counts: solver-orchestrator **19 → 22** (+3); Playwright E2E **3 → 7** (+4)
- CI green on PR (all 6 jobs: solver-orchestrator-test + billing-service-test + auth-service-test + outbox-relayer-test + shared-py-test + web-build + e2e)
- sprint-status.yaml: `2-2-algorithm-details: done`
- Memory `opticloud-project-status.md` updated with PR ref + new counts
- Manual smoke: visit `/algorithms` → click first card → land on `/algorithms/highs-lp` → see Python + cURL snippets → click 📋 复制 → snippet on clipboard

## Sign-off

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Catalog Lead | TBA | ☐ | — |
| FE Lead | TBA | ☐ | — |
| GTM (demo content) | TBA | ☐ | — |

> Owner committee deferred per M0 skip.
