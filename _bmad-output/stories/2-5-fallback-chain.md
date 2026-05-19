---
story_key: 2-5-fallback-chain
epic_num: 2
story_num: 2.5
epic_name: Algorithm Catalog
status: ready-for-dev
priority: 🟢 Easy (Epic 2 quick-win; ~2-3h; small Epic 2 push 4/8 → 5/8; direct extension of 2.4)
sizing: S (~2-3 hours; backend-only; schema field + per-element validation + helper unit + tests)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L1378-1380 (Story 2.5 spec)
  - _bmad-output/planning/prd.md FR C5 ("用户 can specify `fallback_chain`（v1 必上 / 精简档可砍）")
  - _bmad-output/planning/prd.md L1117-1122 (example body shape: `"fallback_chain": ["or-tools","tt_minlp","ipopt"]`)
  - apps/solver-orchestrator/src/solver_orchestrator/schemas.py L56-74 (OptimizationRequest — extend with `fallback_chain`)
  - apps/solver-orchestrator/src/solver_orchestrator/catalog.py L192-225 (find_by_task_type_and_solver — reuse for chain element validation)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py L229-272 (post_optimization solver validation block — extend with chain check)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py L509-537 (post_optimization_demo solver validation block — mirror)
  - apps/solver-orchestrator/tests/test_solver_enum.py (2.4 test file — pattern to follow for 2.5)
  - _bmad-output/stories/2-4-solver-enum.md (immediate predecessor — validation pattern source-of-truth)
dependencies:
  upstream:
    - 2-4-solver-enum (done, PR #24) — `supported_solvers` field, `find_by_task_type_and_solver` helper, 400 RFC 7807 pattern
    - 2-1-j1-algorithms-public-list (done) — CATALOG + AlgorithmSchema
    - 3-1-j1-lp-solve (done) — /v1/optimizations + /demo routes
  downstream:
    - 2-6-multi-provider-routing (FR C6) — provider routing logic that consumes solver + fallback_chain
    - 2-7-fallback-execution (FR C7) — actual ≤3-retry fallback execution loop (this story only stores+validates the chain; execution is 2.7)
---

# Story 2.5 — Fallback Chain Specification (FR C5)

## User Story

**As** an API user submitting an optimization,
**I want** to specify a `fallback_chain: ["solver_a", "solver_b", ...]` in my request,
**so that** the system has an ordered list of solvers to try when my primary `solver` fails — and I get a clear 400 error with the supported solvers list if any chain element is a typo, BEFORE my request consumes any compute or billing budget.

## Why this story

Story 2.4 (PR #24) shipped FR C4: the catalog now declares `supported_solvers` per algorithm and the backend rejects bad `solver` values with RFC 7807 400. Story 2.5 directly extends that pattern to the `fallback_chain: list[str]` array.

What this story DOES:
1. Add `fallback_chain: list[str] | None` to `OptimizationRequest` (Pydantic schema)
2. Validate every element against the resolved algorithm's `supported_solvers` (same allowlist, same 400 shape)
3. Mirror the validation on `/v1/optimizations/demo`
4. Mirror in TypeScript `LPRequest` for FE typing consistency
5. Add ~6 backend tests covering: happy path / unknown element / empty list / duplicates / primary missing / mirror on /demo

What this story does NOT do (deferred to 2.6/2.7):
- **Provider routing logic** — Story 2.6 (FR C6)
- **Actual fallback execution** — Story 2.7 (FR C7): trying chain[0] → chain[1] on failure with ≤3 retries; we only STORE the chain in `Optimization.input_payload` here
- **Per-element status reporting** — when 2.7 lands, `Optimization.error` will record which chain element ran and the path; out of scope here
- **Circuit breaker integration** (D13) — 2.7 dependency
- **FE UI for chain editing** — separate v1 polish

Per memory `feedback_actionable_work`: a small, contained, mechanical extension of the 2.4 hammer; pushes Epic 2 4/8 → 5/8 with no architectural risk.

## Out of scope

- Provider routing logic / multi-provider selection — Story 2.6
- Actual fallback retry loop with ≤3 attempts — Story 2.7
- Cross-algorithm fallback (e.g., fall from VRPTW to a generic MILP solver) — would require capability metadata; deferred to Story 7.A.1
- Chain element rate-limiting or per-element pricing — deferred to billing (5.A.4 currently uses per-second uniform)
- Persisting chain provenance in `Optimization.error` — 2.7
- FE UI to display / edit fallback chain — v1 polish

## Acceptance Criteria

### AC1: Schema field

Update `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`:

```python
class OptimizationRequest(BaseModel):
    """FR E1 — submit optimization task."""

    task_type: Literal[...]
    minimize: LPObjective | None = None
    maximize: LPObjective | None = None
    st: LPConstraints
    options: OptimizationOptions = Field(default_factory=OptimizationOptions)
    solver: str | None = Field(default=None, description="FR C4 explicit solver enum")
    fallback_chain: list[str] | None = Field(
        default=None,
        description="FR C5 ordered list of solvers to try after `solver` fails (≤3 attempts; execution in Story 2.7)",
    )

    @model_validator(mode="after")
    def check_objective(self) -> OptimizationRequest:
        # ... existing minimize/maximize check unchanged ...

        # Story 2.5 — fallback_chain length cap aligned to FR C7 (≤3 retries)
        if self.fallback_chain is not None and len(self.fallback_chain) > 3:
            raise ValueError("fallback_chain length must be ≤3 (FR C7)")
        return self
```

Length cap is enforced at the schema layer so a 5-element chain returns 422 (Pydantic validation), not 400. This is consistent with how `OptimizationOptions.max_solve_seconds` uses `ge=1.0, le=600.0`.

`None` and `[]` are both accepted (treated equivalently as "no chain"); explicit empty list is allowed for forward-compat with FE clients that always send the field.

### AC2: Backend validation in `POST /v1/optimizations`

In `post_optimization` (routes.py), AFTER the existing solver validation block (line ~272, where the `# Story 2.4 — solver-routing logic deferred` comment lives), add:

```python
# Story 2.5 — FR C5 fallback_chain per-element validation
if payload.fallback_chain:
    for idx, candidate in enumerate(payload.fallback_chain):
        if candidate not in supported_solvers:
            return _rfc7807_error(
                title="Unsupported Fallback Solver",
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"fallback_chain[{idx}]='{candidate}' is not supported for "
                    f"task_type '{payload.task_type}'. Supported: {', '.join(supported_solvers)}"
                ),
                errors=[
                    ErrorDetail(
                        field_path=f"fallback_chain[{idx}]",
                        value=candidate,
                        constraint=f"must be one of: {', '.join(supported_solvers)}",
                        remediation_hint_key="errors.400.unsupported_fallback_solver",
                    )
                ],
                next_action="https://api.opticloud.cn/v1/algorithms",
                request_id=request_id,
            )
```

Key design decisions:
- **400, NOT 422**: same reasoning as 2.4 — enum violation with a discoverable allowlist
- **First-failure short-circuit**: report the first bad element with index, not a batched list. Simpler error surface; common case is 1 typo.
- **`supported_solvers` reused from the existing helper call**: we already computed it for the primary `solver` validation; no second lookup needed
- **Validation runs BEFORE billing reserve + persist** — already true because solver validation is also pre-persist; same block stays atomic
- **No dedup / no reordering**: if user sends `["highs", "highs", "highs"]` we accept it (each element still validates). 2.7 will deduplicate at execution time. This keeps the schema layer dumb.
- **Self-include is permitted**: `solver: "highs", fallback_chain: ["highs"]` is allowed (effectively retry-same-solver); 2.7 may emit a warning, but 2.5 does not.

### AC3: Same validation in `POST /v1/optimizations/demo`

Mirror the per-element validation block in `post_optimization_demo` (routes.py line ~537), AFTER the existing solver validation and BEFORE the solve. Same shape; demo route only handles LP today so the chain is realistically `["highs"]`-only — but the validation still needs to exist for consistency (and to lock the 400 contract for future M2-M3 task_types).

### AC4: No execution change (chain is stored only)

`payload.fallback_chain` IS now part of `body_dict` (via `model_dump(by_alias=True)`), so it gets persisted into `Optimization.input_payload`. **No solver-routing code runs in this story.** The existing v1 LP path solves with HiGHS regardless.

Document this with an inline comment near the validation block:

```python
# Story 2.5 — fallback_chain stored in input_payload only (via model_dump).
# Actual fallback execution (try chain[0] → chain[1] on failure, ≤3 retries) is Story 2.7.
```

### AC5: Backend tests

Add to `apps/solver-orchestrator/tests/test_fallback_chain.py` (new file, parallels test_solver_enum.py):

1. `test_demo_lp_with_valid_fallback_chain_succeeds` — `solver: "highs", fallback_chain: ["highs"]` → 200
2. `test_demo_lp_with_invalid_fallback_element_returns_400` — `fallback_chain: ["highs", "garbage"]` → 400 RFC 7807; detail mentions index `[1]` and `garbage`
3. `test_demo_lp_with_empty_fallback_chain_succeeds` — `fallback_chain: []` → 200 (empty is no-op)
4. `test_demo_lp_with_null_fallback_chain_succeeds` — body omits `fallback_chain` → 200 (existing default behavior preserved)
5. `test_demo_lp_fallback_chain_too_long_returns_422` — `fallback_chain: ["highs", "highs", "highs", "highs"]` (length 4) → 422 (Pydantic length cap)
6. `test_demo_lp_fallback_chain_persists_self_solver` — `solver: "highs", fallback_chain: ["highs"]` → 200 (self-include allowed)
7. `test_demo_lp_fallback_first_element_bad_returns_400_index_0` — `fallback_chain: ["garbage", "highs"]` → 400 with `fallback_chain[0]` in error path; first-failure short-circuit

Regression: existing `test_solver_enum.py` (6 cases) + `test_demo_optimizations.py` + `test_algorithm_details.py` must still pass — `fallback_chain` is purely additive at the schema layer.

solver-orchestrator: **38 → 45** (+7 new test cases). No existing tests change.

### AC6: TypeScript client typing

Update `apps/web/src/lib/api.ts` LPRequest:

```ts
export interface LPRequest {
  task_type: "lp";
  minimize?: { c: number[] };
  maximize?: { c: number[] };
  st: { A: number[][]; b: number[]; x_lower?: number[]; x_upper?: number[] };
  options?: { max_solve_seconds?: number; reproducible?: boolean };
  /** Story 2.4 — FR C4 explicit solver enum. */
  solver?: string;
  /** Story 2.5 — FR C5 ordered fallback solvers (≤3); execution in 2.7. */
  fallback_chain?: string[];
}
```

NO UI changes — just keeps the type aligned with the backend so future FE stories can populate the chain.

### AC7: Quality gates (per `feedback_full_quality_gates`)

Run BEFORE pushing the PR:
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy apps packages`
- `pnpm -C apps/web typecheck`
- `pnpm -C apps/web test` (31 baseline preserved — no Vitest change)
- `pnpm -C apps/web build`
- solver-orchestrator pytest (CI authoritative per DR5; local Python is blocked by Windows CP936 issue)

### AC8: NFR alignment

- **FR C5** ✅ — primary deliverable (specification + per-element validation; execution in 2.7)
- **NFR-S** — validation expands input checking; 400 is a typed RFC 7807 response; no info leak
- **NFR-R4** — no billing path changes (chain stored as data only)
- No new env vars, DB migrations, dependencies, or auth changes
- No new ADR needed

## Tasks

### T1 — Schema field (0.2h)
1. Add `fallback_chain: list[str] | None = Field(...)` to `OptimizationRequest`
2. Extend `check_objective` model_validator with length-≤3 cap (or add a second `@model_validator(mode="after")` named `check_fallback_chain` — pick whichever keeps cleaner; AC1 suggests single combined validator)
3. Type-check: `uv run mypy apps/solver-orchestrator`

### T2 — Backend validation in /v1/optimizations (0.3h)
1. Add per-element loop after existing solver validation block per AC2
2. Add the "stored only" comment per AC4

### T3 — Backend validation in /v1/optimizations/demo (0.2h)
1. Mirror the per-element loop in `post_optimization_demo` per AC3

### T4 — Backend tests (0.5h)
1. Create `test_fallback_chain.py` with 7 cases per AC5
2. Use same fixture pattern as `test_solver_enum.py` (ASGITransport + AsyncClient, no auth needed for /demo)

### T5 — TS typing (0.05h)
1. Add `solver?: string` and `fallback_chain?: string[]` to `LPRequest` interface per AC6
2. Note: `solver` was missing from TS LPRequest after 2.4 — adding both fields now closes the gap

### T6 — Quality gates + PR (0.5h)
1. Run all gates per AC7
2. Create feature branch `feature/2-5-fallback-chain`
3. Commit, push, open PR; CI watch per `feedback_actionable_work` CI watch gotcha (`gh pr checks N --watch` background, no `until` wrapper)
4. Squash-merge after green; reset local main; update `sprint-status.yaml`

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Pydantic length validation surfaces as 422 but other chain-element errors surface as 400 — inconsistent | Documented in AC1: 422 = "request shape invalid" (length is shape); 400 = "enum violation". Two different failure modes, two different status codes — by design. Story 3.7 will sweep RFC 7807 consistency at the platform layer. |
| Forecast multi-algorithm case: `task_type=forecast` has 3 algos (chronos/arima/lstm). `find_by_task_type_and_solver` returns the FIRST matching `(algo, supported)`. If user sends `solver: "chronos-t5", fallback_chain: ["lstm"]`, the chain element validates against chronos's supported_solvers, NOT the union | We re-use the SAME `supported_solvers` list returned by the existing 2.4 helper call. That list is the UNION of all algos with matching task_type (see catalog.py:212-216 — `union_supported`). So `"lstm"` IS in the union for `task_type=forecast`. Cross-algo chain validation works correctly via the union. Unit test in AC5 #2 covers this implicitly via the LP-only catalog; add a 2nd helper-level unit if needed. **No new code needed — this is a free property of the 2.4 design.** |
| Existing 2.4 routes computed `supported_solvers` via the helper; if user omits `solver` AND provides `fallback_chain`, the validation block must still run | The helper call is unchanged — when `payload.solver is None`, the helper returns `(first_algo, union_supported_list)` so `supported_solvers` is still populated. The 2.4 solver validation simply skips (because `payload.solver is None`); the new 2.5 block runs independently. Verified by AC5 test #1. |
| Schema length validator order: existing `check_objective` validates `minimize` XOR `maximize`. Adding a length check in the same validator could mask the objective error if the chain length triggers first | Pydantic raises on the first ValueError, so add length check AFTER the objective XOR check (existing logic comes first). Order tested explicitly in AC5 #5 (length=4 with valid objective → length error wins). |
| Backward-compat: existing clients sending no `fallback_chain` field at all | Field is optional with default `None`. Existing `body_dict` from `model_dump(by_alias=True)` will include `fallback_chain: None` — verified safe by /demo unauth path which already accepts arbitrary extra keys via raw JSON. AC5 #4 covers this. |
| Idempotency: adding `fallback_chain` changes `_hash_body(body_dict)`. Two requests with same `Idempotency-Key` but different chains hit the existing 409 conflict path | Correct behavior — chain is part of the request semantically, so two different chains SHOULD trigger 409 ("same idempotency key with different body"). Pre-existing P23 logic at routes.py:209-223 already handles this; no change needed. |
| Empty list `[]` vs `None`: subtle FE confusion | Treated equivalently per AC1 (`if payload.fallback_chain:` evaluates `None` and `[]` both as falsy). Test case #3 locks this. |
| Future Story 2.6/2.7 may need to mutate the chain order (e.g., dedup, capability filter) — making it `list[str]` not `tuple[str, ...]` keeps it mutable | Acceptable. Pydantic returns a new list per request; no shared state. |

## Definition of Ready

- ✅ `supported_solvers` field exists on every catalog entry (Story 2.4)
- ✅ `find_by_task_type_and_solver` helper exists and returns union list (Story 2.4)
- ✅ RFC 7807 `_rfc7807_error` helper available (routes.py:108)
- ✅ Solver validation block already in place at routes.py:248-272 — extension point
- ✅ Test pattern established in `test_solver_enum.py`
- ✅ Pydantic 2 model_validator already used in OptimizationRequest

## Definition of Done

- 8 ACs pass
- solver-orchestrator 38 → 45 (+7 cases in new `test_fallback_chain.py`)
- `OptimizationRequest.fallback_chain` field added with length-≤3 schema validation
- Per-element validation on both `/v1/optimizations` and `/v1/optimizations/demo` returns RFC 7807 400 with index in `field_path`
- TypeScript `LPRequest` interface aligned (`solver?` + `fallback_chain?`)
- All quality gates green (ruff / format / mypy / pnpm typecheck / pnpm test / pnpm build)
- CI all green
- `sprint-status.yaml` updated: `2-5-fallback-chain: done`
- Squash-merged to main

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
| 1 | User story has As/I want/so that | ✅ | API user persona; explicit "BEFORE compute / billing" outcome |
| 2 | ACs testable & BDD-shaped | ✅ | Each AC has concrete code block + test name |
| 3 | Scope explicit (in/out) | ✅ | Out-of-scope enumerates 2.6 / 2.7 / 7.A.1 boundaries |
| 4 | Dependencies declared | ✅ | upstream 2.4 / 2.1 / 3.1; downstream 2.6 / 2.7 |
| 5 | Sizing estimate | ✅ | S (~2-3h); same shape as 2.4 (which took ~2h) |
| 6 | Risks identified with mitigations | ✅ | 7 risks, each with mitigation referencing concrete AC# |
| 7 | Quality gates listed | ✅ | AC7 enumerates all 7 commands |
| 8 | Test plan | ✅ | 7 new backend tests; regression on existing solver_enum suite |
| 9 | Backwards compat | ✅ | Optional field, None default; existing clients unchanged |
| 10 | Sources cited | ✅ | Top frontmatter — 9 source lines incl. predecessor story |

Round 1: **PASS**

---

## Round 2: 5-Perspective Review

### 🏗️ Architect

- ✅ Pydantic length-cap at schema layer is correct — keeps the route handler dumb; 422 vs 400 separation is principled
- ✅ Reusing `find_by_task_type_and_solver`'s already-computed `supported_solvers` union avoids a second catalog scan and ALSO automatically handles the forecast cross-algorithm case (chronos + arima + lstm all flatten into the union for `task_type=forecast`)
- ✅ "Store only, execute later" is the right v1/v2 split — keeps this story sub-3h and unblocks 2.7 cleanly
- ⚠️ Question: should the route enforce `fallback_chain` cannot include the primary `solver`? **Decision: NO** — keep schema dumb. 2.7 can dedupe at execution time, or emit a warning. Documented in AC2.
- ✅ No new ADR needed

### 👨‍💻 Dev

- ✅ Implementation lives in 3 files: schemas.py, routes.py, api.ts (+1 new test file). Tight scope.
- ✅ Validation loop pattern is a 12-line copy/adapt from the existing 2.4 block (routes.py:248-272) — mechanical
- ✅ Test fixture reuse: ASGITransport + AsyncClient with `loop_scope="session"` (same pattern as test_solver_enum.py)
- ⚠️ The model_validator currently handles `minimize/maximize` XOR. Adding length check inside it works, but a separate `check_fallback_chain` validator is cleaner. **Decision: ONE combined validator with the length check at the end** — saves a Pydantic round-trip. Matches AC1 code block.

### 🧪 QA

- ✅ 7 tests cover: 1 happy (#1) + 4 error paths (#2 unknown / #5 length / #7 first-failure index) + 2 edge cases (#3 empty / #4 null) + 1 sneaky case (#6 self-include allowed)
- ⚠️ Add an 8th case to lock the model_dump round-trip: `test_demo_lp_fallback_chain_persists_through_body_dict` — verifies the field survives `OptimizationRequest.model_validate → model_dump(by_alias=True)`. **Decision: SKIP** — Pydantic 2's round-trip is contract-tested by upstream; would only verify Pydantic itself. Drop.
- ⚠️ Should we add a test that sends both `solver: "garbage"` AND `fallback_chain: ["highs"]`? Currently: solver validation fails first → 400 on solver, not chain. **Decision: ADD as test #8** to lock ordering. ← **UPDATED: AC5 grows from 7 to 8.** See below.

Adjusted AC5 (final): **8 tests**, +8 = solver-orchestrator 38 → 46.

### 🔐 Security

- ✅ Chain elements validated against fixed allowlist; no injection risk
- ✅ 400 error message reveals supported solvers — by design (same discoverability stance as 2.4)
- ✅ No PII; no auth changes; no new env vars
- ✅ Length cap (≤3) prevents resource exhaustion via huge chain submissions
- ✅ Validation runs BEFORE billing reserve — no compute/credit waste on bad input

### 🛠️ SRE

- ✅ Trivial; reuses existing 4xx counters
- ✅ No new metrics, alerts, or dashboards
- ✅ No DB migration; field added to JSONB `input_payload` blob

Round 2: **PASS** with 1 adjustment (QA's test #8 ordering case) — AC5 updated to 8 tests.

---

## Round 3: Dev-Readiness

- ✅ All file paths absolute; method signatures concrete
- ✅ Test names enumerated (8 cases, AC5 final)
- ✅ Reference implementation: 2.4's routes.py:248-272 + test_solver_enum.py are the pattern source-of-truth — both already on main
- ✅ Sizing realistic (~2-3h); 2.4 took ~2h with comparable scope so this is a confident estimate
- ✅ Sprint-status update path declared (`development_status[2-5-fallback-chain] = "done"` after merge)
- ✅ Branch name decided (`feature/2-5-fallback-chain`)
- ✅ CI watch gotcha called out (`gh pr checks N --watch` background, no `until` wrapper)

Round 3: **PASS — READY FOR DEV**

---

## Implementation Notes

- Re-use the existing `supported_solvers` variable computed at routes.py:230 — don't call `find_by_task_type_and_solver` twice. The variable is in scope for the rest of the function.
- For the model_validator: keep one combined `check_objective` and append the fallback_chain length check at the end (returns `self`). Don't introduce a second validator just for one line.
- For TS `LPRequest`: also add the previously-missing `solver?: string` field. This is "free fix" piggybacking on 2.5 since 2.4 added the field to Pydantic but never to TypeScript LPRequest (only Algorithm interface). Document it in PR description.
- Test file uses ASGITransport for /demo path (unauthenticated) — no need to spin up the auth fixture chain. Mirror test_solver_enum.py exactly.
- For test #8 (ordering), assert 400 + `body["title"] == "Unsupported Solver"` (not "Unsupported Fallback Solver") to lock that primary-solver check wins.

Completion note: "Ultimate context engine analysis complete — mechanical extension of 2.4's solver validation to a list-field; reuses the same union helper output; 8 tests; backend-only; sub-3h scope."

### AC5 (final, after Round 2 QA adjustment): 8 backend tests

1. `test_demo_lp_with_valid_fallback_chain_succeeds` — `solver: "highs", fallback_chain: ["highs"]` → 200
2. `test_demo_lp_with_invalid_fallback_element_returns_400` — `fallback_chain: ["highs", "garbage"]` → 400; detail mentions `[1]` and `garbage`; title `"Unsupported Fallback Solver"`
3. `test_demo_lp_with_empty_fallback_chain_succeeds` — `fallback_chain: []` → 200
4. `test_demo_lp_with_null_fallback_chain_succeeds` — body omits `fallback_chain` → 200
5. `test_demo_lp_fallback_chain_too_long_returns_422` — length 4 → 422 (Pydantic cap)
6. `test_demo_lp_fallback_chain_self_solver_succeeds` — `solver: "highs", fallback_chain: ["highs"]` → 200
7. `test_demo_lp_fallback_first_element_bad_returns_400_index_0` — `fallback_chain: ["garbage", "highs"]` → 400 with `fallback_chain[0]` in errors[].field_path
8. `test_demo_lp_bad_primary_solver_wins_over_bad_chain` — `solver: "garbage", fallback_chain: ["alsobad"]` → 400 title `"Unsupported Solver"` (not "Unsupported Fallback Solver"); locks ordering

solver-orchestrator: **38 → 46** (+8).
