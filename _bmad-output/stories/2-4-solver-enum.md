---
story_key: 2-4-solver-enum
epic_num: 2
story_num: 2.4
epic_name: Algorithm Catalog
status: ready-for-dev
priority: 🟢 Easy (Epic 2 quick-win; ~1-2h; small Epic 2 push 3/8 → 4/8)
sizing: S (~1-2 hours; backend-only; catalog field + validation + tests)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L1374-1376 (Story 2.4 spec)
  - _bmad-output/planning/prd.md FR C4 ("用户 can specify `solver` (枚举)（v1 必上）")
  - apps/solver-orchestrator/src/solver_orchestrator/schemas.py L55-73 (OptimizationRequest.solver field already exists, currently unused)
  - apps/solver-orchestrator/src/solver_orchestrator/catalog.py (CATALOG TypedDict — need new supported_solvers field)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py L225-242 (find_by_task_type lookup — validation goes after this)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py L432-518 (/optimizations/demo route — must mirror validation)
dependencies:
  upstream:
    - 2-1-j1-algorithms-public-list (done) — catalog + OptimizationRequest schema
    - 3-1-j1-lp-solve (done) — /v1/optimizations endpoint
  downstream:
    - 2-5-fallback-chain (FR C5) — same validation pattern extended to `fallback_chain` array
    - 2-6-multi-provider-routing (FR C6)
---

# Story 2.4 — Solver Enum Selection (FR C4)

## User Story

**As** an API user submitting an optimization,
**I want** to specify which solver to use via the `solver` field (e.g., `solver: "highs"` vs `solver: "or-tools"`),
**so that** I can pick a specific implementation when multiple solvers cover my task_type — and get a clear 400 error with the list of allowed solvers when I typo a name.

## Why this story

The `solver: str | None` field already exists on `OptimizationRequest` (apps/solver-orchestrator/src/solver_orchestrator/schemas.py:65) — it has been silently ignored since Sprint 0. Users currently can:
- Send `solver: "garbage"` → request succeeds anyway (LP solves with HiGHS regardless)
- No way to discover which solvers ARE supported
- No 400 differentiation for "wrong solver" vs "wrong task_type"

Story 2.4 closes this gap:
1. Catalog declares which solver names are valid per algorithm (`supported_solvers`)
2. Backend validates `payload.solver` against catalog; unknown → RFC 7807 400 with the allowed list
3. AlgorithmSchema exposes `supported_solvers` so the algorithm details page (Story 2.2) and `/v1/algorithms` listing surface this info to users
4. Same enforcement on `/v1/optimizations/demo` (consistency with 3.E.3-5)

**Why now**: small, contained, no FE work; nudges Epic 2 from 3/8 → 4/8 in <2h; unblocks Story 2.5 (fallback_chain) which uses the same validation pattern. Per memory `feedback_actionable_work`: prefer small landings over big stalls.

## Out of scope

- **FE changes** — algorithm details page (2.2) and catalog list (2.1/2.3) will get auto-updated typing via the new field, but no visual updates in this PR. A v1 polish story can add a "Supported solvers" chip group.
- **`fallback_chain` validation** — Story 2.5 (FR C5)
- **Multi-provider routing** — Story 2.6 (FR C6)
- **Solver capability metadata** (max problem size, license terms, etc.) — Story 7.A.1 capability registry
- **Per-tier pricing differentiation by solver** — billing-service (5.A.4) currently uses uniform pricing
- **Adding new solver implementations** — this story only adds METADATA + VALIDATION; actual solver code (e.g., wiring or-tools-lp) is M2-M3 backend work

## Acceptance Criteria

### AC1: Catalog gains `supported_solvers` field

Update `apps/solver-orchestrator/src/solver_orchestrator/catalog.py`:

```python
class Algorithm(TypedDict):
    k_algo: str
    task_type: str
    tier: Literal[...]
    status: Literal[...]
    model_version: ModelVersion
    description_zh: str
    description_en: str
    examples: list[dict[str, object]]
    supported_solvers: list[str]   # NEW — FR C4
```

Populate for each catalog entry. v1 values:

| k_algo | supported_solvers |
|---|---|
| `highs-lp` | `["highs"]` |
| `highs-milp` | `["highs"]` |
| `or-tools-vrptw` | `["or-tools"]` |
| `or-tools-cp-sat` | `["or-tools-cp-sat", "or-tools"]` |
| `chronos-t5-forecast` | `["chronos-t5"]` |
| `arima-forecast` | `["statsmodels-arima", "arima"]` (alias `"arima"` accepted) |
| `lstm-forecast` | `["tensorflow-lstm", "lstm"]` |
| `aqgs-acopf` | `["aqgs"]` |

Notes:
- Always at least one entry (a "default" solver per algorithm)
- Aliases (`"arima"`, `"lstm"`) are convenience names that resolve to the canonical provider_id
- Naming convention: lowercase, hyphen-separated; matches provider_id but distinct so future solvers can share a provider

### AC2: AlgorithmSchema exposes the new field

`apps/solver-orchestrator/src/solver_orchestrator/schemas.py`:

```python
class AlgorithmSchema(BaseModel):
    k_algo: str
    task_type: str
    tier: str
    status: str
    model_version: ModelVersionSchema
    description_zh: str
    description_en: str
    examples: list[dict[str, Any]] = []
    supported_solvers: list[str]   # NEW — FR C4
```

`GET /v1/algorithms` and `GET /v1/algorithms/{k_algo}` automatically surface the field via `AlgorithmSchema.model_validate(algo_dict)`.

### AC3: Validation in `POST /v1/optimizations`

After the `find_by_task_type(payload.task_type)` lookup (currently routes.py:226), BEFORE persisting the Optimization row, add:

```python
if payload.solver is not None:
    supported = algo["supported_solvers"]
    if payload.solver not in supported:
        return _rfc7807_error(
            title="Unsupported Solver",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"solver '{payload.solver}' is not supported for task_type "
                f"'{payload.task_type}'. Supported: {', '.join(supported)}"
            ),
            errors=[
                ErrorDetail(
                    field_path="solver",
                    value=payload.solver,
                    constraint=f"must be one of: {', '.join(supported)}",
                    remediation_hint_key="errors.400.unsupported_solver",
                )
            ],
            next_action=f"https://api.opticloud.cn/v1/algorithms/{algo['k_algo']}",
            request_id=request_id,
        )
```

Key choices:
- **400, NOT 422**: this is client mistake (bad enum value with a clear set of valid alternatives) — 400 is appropriate. 422 is reserved for "request shape OK but semantically infeasible" cases.
- Validation runs BEFORE persist + billing — no wasted ledger/optimization rows on a 400
- `next_action_url` points at the algorithm detail endpoint so the user can see valid choices

### AC4: Same validation in `POST /v1/optimizations/demo`

Mirror the check at the appropriate point in `post_optimization_demo` (routes.py:432-518). Since the demo route is non-LP → short-circuit 501, the validation only matters for LP (or whatever lands as a real solver via /demo). Apply it AFTER the LP body validates via OptimizationRequest, BEFORE the actual solve. Same 400 shape.

### AC5: Pass solver through to actual solve

Currently `solve_from_request(body_dict, max_solve_seconds=...)` (routes.py:269) ignores the solver field. v1 implementation: the existing LP solver IS HiGHS, so the only valid solver for `task_type=lp` IS `"highs"`. The validation in AC3 already ensures the user can only specify `"highs"`. **No solver-routing logic needed in this story** — just validation. A no-op pass-through is sufficient.

Document in a comment in `routes.py`: "Story 2.4 — solver-routing logic deferred (FR C6 / Story 2.6). v1 catalog has 1 solver per algorithm; multi-solver routing is M2-M3."

### AC6: Backend tests

Add to `apps/solver-orchestrator/tests/test_solver_enum.py` (new file):

1. `test_post_optimization_with_valid_solver_succeeds` — POST `/v1/optimizations` LP body with `solver: "highs"` → 200 + solution
2. `test_post_optimization_with_invalid_solver_returns_400` — POST LP body with `solver: "garbage"` → 400 + detail mentions "Supported: highs"
3. `test_post_optimization_with_null_solver_succeeds` — POST LP body without `solver` field → 200 (current default behavior preserved)
4. `test_post_optimization_demo_with_invalid_solver_returns_400` — same on /demo route
5. `test_get_algorithms_returns_supported_solvers_field` — `GET /v1/algorithms` → all entries have `supported_solvers` non-empty array
6. `test_get_algorithm_detail_returns_supported_solvers` — `GET /v1/algorithms/highs-lp` → `supported_solvers: ["highs"]`

Also: regression on existing test files — `test_algorithm_details.py` + `test_demo_optimizations.py` should still pass (response shape EXTENDS, no breaking change).

solver-orchestrator 32 → **38** (+6).

### AC7: TypeScript client surfacing (FE typing only)

Update `apps/web/src/lib/api.ts`:

```ts
export interface Algorithm {
  k_algo: string;
  task_type: string;
  tier: string;
  status: string;
  model_version: ModelVersion;
  description_zh: string;
  description_en: string;
  examples: Array<{...}>;
  supported_solvers: string[];  // NEW — FR C4 (Story 2.4)
}
```

NO UI work — just keep the type aligned with the backend so future FE stories can `algorithm.supported_solvers.map(...)`. This is the documented FE typing rule.

### AC8: Quality gates

Per `feedback_full_quality_gates`:
- `uv run ruff check .` + `ruff format --check .`
- `uv run mypy apps packages`
- `pnpm -C apps/web typecheck` (verifies the Algorithm interface update is consistent)
- `pnpm -C apps/web test` (no test change expected; 31 baseline preserved)
- `pnpm -C apps/web build`
- solver-orchestrator pytest (CI authoritative per DR5)

### AC9: NFR alignment

- **FR C4** ✅ — primary deliverable
- **NFR-S** — input validation expands; 400 is a typed RFC 7807 response (no info leak)
- No new external dependencies, env vars, DB migrations, or auth changes

## Tasks

### T1 — Catalog field + values (0.2h)
1. Add `supported_solvers: list[str]` to Algorithm TypedDict in `catalog.py`
2. Populate per AC1 table for all 8 entries
3. Type-check: `uv run mypy apps/solver-orchestrator`

### T2 — Schema expose (0.1h)
1. Add `supported_solvers: list[str]` to AlgorithmSchema in `schemas.py`

### T3 — Backend validation (0.3h)
1. Add 400 validation block to `post_optimization` per AC3
2. Mirror in `post_optimization_demo` per AC4
3. Add the "solver-routing deferred" comment per AC5

### T4 — Backend tests (0.4h)
1. Create `test_solver_enum.py` with 6 cases per AC6

### T5 — TS typing only (0.05h)
1. Add `supported_solvers: string[]` to Algorithm interface in `apps/web/src/lib/api.ts`

### T6 — Quality gates + PR (0.4h)

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Adding required field to AlgorithmSchema breaks existing consumers that don't supply it | All 8 CATALOG entries populated in T1 simultaneously. AlgorithmSchema field has no default — type-checker enforces no entry forgets it. |
| `supported_solvers` alias list (`["arima", "statsmodels-arima"]`) lets users specify alias but billing tracks differently | v1 doesn't gate billing on solver name — only on task_type. Alias is purely API convenience. Future: 5.A.4 may charge differently per solver, at which point we canonicalize alias → provider_id BEFORE billing emit. |
| 400 vs 422 inconsistency: task_type uses 422 but solver uses 400 | Documented in AC3: 422 = semantically infeasible after-shape-validates; 400 = enum violation with discoverable correct values. Both are RFC 7807. Story 3.7 will sweep RFC 7807 consistency. |
| Existing Playwright/Vitest tests breaking from AlgorithmSchema field extension | Field is ADDED, not changed; existing tests don't assert on `supported_solvers` absence. Verified in T6 via full test run. |
| `find_by_task_type` returns first matching algorithm but multiple algorithms can have same task_type (e.g., forecast has 3 — chronos / arima / lstm) | Pre-existing M1 behavior (catalog.py:166-171 returns first match). Solver validation needs to check the FOUND algorithm's supported_solvers — if user wants `solver: "lstm"` but find returned arima, validation fails. **Fix in this story**: when `payload.solver` is set AND `find_by_task_type` returns a non-matching algo, scan the whole catalog for an algorithm with matching task_type + supported_solvers. Implementation note in T3. |
| Solver alias collision: `"arima"` lists under arima-forecast only — but if a future provider also calls something "arima", validation could mis-route | Aliases are scoped per-algorithm; the validation only checks one algorithm's `supported_solvers` list, never global. Safe. |
| FR C4 spec mentions "or-tools" as the example, but `highs-lp` doesn't list "or-tools" — example may surprise users testing the API doc | Spec language is illustrative; "or-tools" is valid for vrptw + cp-sat task_types. Docs (later story) should call out the example uses VRPTW. |

## Definition of Ready

- ✅ OptimizationRequest.solver field exists in schema (Story 3.1)
- ✅ Catalog has well-formed Algorithm entries (Story 2.1)
- ✅ RFC 7807 error helper available (`_rfc7807_error` in routes.py)
- ✅ AlgorithmSchema serialization in place

## Definition of Done

- 9 ACs pass
- solver-orchestrator 32 → 38 (+6 tests in new test_solver_enum.py)
- All 8 catalog entries have `supported_solvers` populated
- AlgorithmSchema response includes the field
- 400 returned for typo'd solver names; supported list in detail
- TypeScript `Algorithm` interface aligned
- CI all green
- sprint-status updated

## Sign-off

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Catalog Lead | TBA | ☐ | — |
| Backend Lead | TBA | ☐ | — |

> Owner committee deferred per M0 skip.

---

## Round 1: BMad Checklist Review

| # | Item | Status | Note |
|---|---|:-:|---|
| 1 | User story has As/I want/so that | ✅ | API user persona |
| 2 | ACs testable & BDD-shaped | ✅ | Each AC has concrete test or signature |
| 3 | Scope explicit (in/out) | ✅ | FE UI explicitly deferred; only typing change |
| 4 | Dependencies declared | ✅ | upstream 2.1 + 3.1; downstream 2.5 + 2.6 |
| 5 | Sizing estimate | ✅ | S (~1-2h) |
| 6 | Risks identified with mitigations | ✅ | 7 risks |
| 7 | Quality gates listed | ✅ | AC8 |
| 8 | Test plan | ✅ | 6 backend tests; regression on existing |
| 9 | Backwards compat | ✅ | Field ADDED; existing clients still work without solver |
| 10 | Sources cited | ✅ | Top frontmatter |

Round 1: **PASS**

---

## Round 2: 5-Perspective Review

### 🏗️ Architect

- ✅ Catalog metadata is the right place for supported_solvers — keeps capability info colocated with algorithm identity
- ✅ Validation in routes.py (not Pydantic) — correct because validation depends on catalog lookup; Pydantic can't see CATALOG
- ⚠️ Forecast task_type has 3 algorithms (chronos/arima/lstm). `find_by_task_type` returns the FIRST — this is pre-existing weakness, not a 2.4 regression. But solver validation EXPOSES it: user with `task_type: "forecast", solver: "lstm"` gets validated against chronos's solver list → 400. **Fix in T3**: scan all algorithms with matching task_type, prefer one whose supported_solvers contains the user's solver. Documented in risks.
- ✅ No new ADR needed

### 👨‍💻 Dev

- ✅ Implementation is concentrated in 4 files: catalog.py, schemas.py, routes.py, api.ts
- ✅ Test file new but follows established conftest pattern (`AsyncClient` + `ASGITransport`)
- ✅ The forecast multi-algorithm edge case needs a helper `find_by_task_type_and_solver(task_type, solver)` — refine in T3

### 🧪 QA

- ✅ 6 tests cover happy + 4 error paths + 2 schema-shape regressions
- ⚠️ Add a 7th case for the forecast multi-algorithm scenario: `test_post_optimization_with_forecast_lstm_solver_routes_to_lstm` — even though /optimizations only supports LP today, the validation logic must handle the forecast catalog correctly. **Decision: skip the runtime test** (forecast task_type returns 501 in current code so the routing never executes), but add a unit test for the new `find_by_task_type_and_solver` helper specifically.

### 🔐 Security

- ✅ Solver name is validated against a fixed allowlist; no injection risk
- ✅ 400 error message reveals the allowed solvers — by design (this is the discoverability feature)
- ✅ No PII / auth changes

### 🛠️ SRE

- ✅ Trivial change; no metrics / alerting impact
- ✅ Existing 4xx counters cover the new 400 case

Round 2: **PASS** (1 medium item: forecast multi-algorithm needs helper)

---

## Round 3: Dev-Readiness

- ✅ File paths absolute; method signatures concrete
- ✅ Test names enumerated (6 + 1 helper-unit)
- ✅ Reference implementations: routes.py existing 422 task_type validation (line 226-242) is the shape to mirror at 400
- ✅ Sizing realistic
- ✅ Sprint-status update path declared

Round 3: **PASS — READY FOR DEV**

---

## Implementation Notes

- Add helper to `catalog.py`:
  ```python
  def find_by_task_type_and_solver(
      task_type: str, solver: str | None
  ) -> tuple[Algorithm | None, list[str] | None]:
      """Return (matching algo, full supported list for first task_type match).
      When solver is None, returns the first algorithm matching task_type.
      When solver is given, returns the algorithm whose supported_solvers contains it;
      if none match but task_type exists, returns (None, full_supported_list_from_first_match).
      """
  ```
  Then routes.py uses this single helper for both lookup + validation.
- Comment in routes.py for AC5: don't introduce solver-routing logic; just validate. Avoid premature abstraction.
- TypeScript `Algorithm` interface change should be additive; existing `algorithms[k_algo]/page.tsx` shouldn't break since it doesn't iterate over fields.
- Don't add 'supported_solvers' rendering to the algorithm detail FE — that's a separate v1 polish.

Completion note: "Ultimate context engine analysis complete — small but precise scope; catalog field + per-task validation + new helper to handle multi-algorithm task_types correctly."
