---
story_key: 3-5-top-k-alternatives
epic_num: 3
story_num: 3.5
epic_name: Optimization & Prediction Execution
status: done
priority: High (FR E5 v1 must-have; user-visible alternative solution contract)
sizing: M (~4-6 hours; schema + LP candidate generation + persistence/replay + focused tests)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-27
sources:
  - _bmad-output/planning/epics.md:70 (FR E5 top_k_alternatives v1 must-have)
  - _bmad-output/planning/epics.md:373 (Epic 3 goal includes top_k)
  - _bmad-output/planning/epics.md:1425-1427 (Story 3.5 AC)
  - _bmad-output/planning/prd.md:1472 (E5 user can request top_k_alternatives)
  - _bmad-output/planning/architecture.md:1622 (E-domain owned by solver-orchestrator + billing-service)
  - _bmad-output/stories/3-3-sync-async-mode.md (sync/async routing, idempotency, compact GET)
  - _bmad-output/stories/3-4-max-solve-seconds-cap.md (fallback budget, timeout response, terminal persistence)
  - apps/solver-orchestrator/src/solver_orchestrator/schemas.py (OptimizationOptions/OptimizationResponse)
  - apps/solver-orchestrator/src/solver_orchestrator/solvers.py (LP solve wrapper and LPSolveResult)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py (POST/GET optimization, fallback, idempotency)
dependencies:
  upstream:
    - 3-1-j1-lp-solve (done) - LP solve, persistence, success response and GET success shape.
    - 2-7-fallback-execution (done) - terminal fallback attempt semantics.
    - 3-3-sync-async-mode (done) - effective sync/async boundary and idempotency hash/replay.
    - 3-4-max-solve-seconds-cap (done) - shared request time budget, timeout best-solution contract.
  downstream:
    - 3-7-rfc7807-errors-detail - can deepen validation messages and i18n next_action_url.
    - 3-9-status-progress-eta - can expose alternative-generation progress for async workers later.
    - 3-14-mock-real-divergence-test - can add broad contract parity for mock/real top-k responses.
---

# Story 3.5 - top_k_alternatives (FR E5)

## User Story

作为 API 用户，
我希望在 `POST /v1/optimizations` 的 `options.top_k_alternatives` 中请求多个候选解，
以便一次求解返回主解之外的可行替代方案，并且每个候选解都带有可排序的 score。

## Why This Story

Epic 3 要求优化执行支持 `top_k`，Story 3.5 的原始 AC 是：`top_k_alternatives: 3` 时返回 top 3 解且每个带 score。当前 API 只返回一个 `solution/objective`，用户无法比较替代方案。

连续 LP 不存在像 MILP 那样天然离散的全局第 1/2/3 个解；同一最优面上还可能有无限多个解。因此本 story 把 v1 合同收敛为 **LP 顶点候选解排序**：

- 对 LP 同步成功结果，返回最多 K 个可行顶点候选。
- 候选按原始目标函数排序；rank 1 是主解或同等最优候选。
- 每个候选包含 `rank`, `score`, `objective`, `solution`, `source`。
- 若可证明/可枚举的候选不足 K 个，如实返回可用数量，不伪造解。

这满足 v1 用户比较替代方案的需求，同时不谎称已经实现 MILP/CP-SAT 的 k-best enumeration。

## Out of Scope

- 不实现 MILP/CP-SAT/VRPTW/schedule 的 k-best enumeration。
- 不为 async queued row 启动后台求解或生成 alternatives；async 仍只排队。
- 不引入新 solver、商业 solver API 或外部依赖。
- 不新增 DB column；alternatives 作为成功求解的 `_system.top_k_alternatives` 元数据持久化。
- 不改变 `solution` 字段语义；`solution` 仍是主解。
- 不改变 billing 金额公式、reserve/finalize 生命周期或 cost attribution 计量单位。
- 不为 timeout/infeasible/unbounded/error 返回 alternatives。
- 不把连续 LP 的无限最优面完整采样作为 v1 范围。

## Acceptance Criteria

### AC1: request schema exposes bounded top_k_alternatives

- Add `OptimizationOptions.top_k_alternatives: int = Field(default=1, ge=1, le=10)`.
- Canonical request location is `options.top_k_alternatives`.
- Omitted value keeps current single-solution behavior and response compatibility.
- Invalid values fail at schema validation before provider routing, billing reserve, persistence, solver execution, cost attribution, voucher issuance, or idempotency insert.
- `options.top_k_alternatives` participates in existing idempotency hash because `body_dict = payload.model_dump(by_alias=True)` includes normalized options.

### AC2: LP solver result can carry deterministic alternatives

When `solve_lp(..., top_k_alternatives=K)` returns `status="optimal"` and `K > 1`:

- It returns `LPSolveResult.alternatives` as a list of up to K alternative payloads.
- Each alternative has:
  - `rank`: 1-based integer after sorting.
  - `score`: finite float in `(0, 1]`, with rank 1 score `1.0`.
  - `objective`: original objective value for that candidate, not a perturbed/tie-break objective.
  - `solution`: `{"x": [...]}` with finite values matching the number of decision variables.
  - `source`: one of `"primary"` or `"lp_vertex_enumeration_v1"`.
- Candidate solutions are feasible under `A·x ≤ b`, `x_lower`, and `x_upper` within numeric tolerance.
- Duplicate solutions are removed using a numeric tolerance so the same point is not returned twice.
- Sorting is deterministic:
  - minimize: lower objective first.
  - maximize: higher objective first.
  - ties: lexicographic `x` order.
- Rank 1 must always match the primary solver result returned by HiGHS. If deterministic enumeration finds an objective-equivalent lexicographically earlier vertex, keep the primary result at rank 1 and sort the remaining candidates after it. This preserves the existing top-level `solution/objective` contract.
- If candidate enumeration cannot safely run because the LP is too large or underdetermined for the v1 cap, return the primary solution only and record that returned count is less than requested.
- If the LP is unbounded, infeasible, timeout, or error, do not generate alternatives.
- If the primary solution is missing or non-finite despite optimal status, return no alternatives metadata and let existing success/error safeguards handle the primary response.

### AC3: response includes alternatives only when requested

For authenticated effective sync LP success with `options.top_k_alternatives > 1`:

- HTTP remains `200`.
- Existing top-level fields remain unchanged: `status`, `solution`, `objective`, `model_version`, `solve_seconds`, `created_at`, `completed_at`, optional citation/IP/reproducibility.
- Response adds:
  - `top_k_alternatives_requested`
  - `top_k_alternatives_returned`
  - `alternatives`
- `alternatives[0].solution` equals the top-level `solution`.
- `alternatives[0].objective` equals the top-level `objective`.
- Each returned alternative includes a score.
- If fewer than K candidates are available, `top_k_alternatives_returned < top_k_alternatives_requested` and no synthetic rows are added.
- If `top_k_alternatives == 1`, omit `alternatives` and the count fields to preserve current response shape.
- Implementation must not add nullable `alternatives=null` or null count fields to default success responses. Attach these fields manually only when K > 1, or serialize optional response fields with `exclude_none=True` and test the default response shape.

### AC4: persisted completed rows replay alternatives consistently

For completed authenticated rows with requested top K:

- Persist alternatives in `Optimization.input_payload._system.top_k_alternatives`.
- Metadata must include:
  - `strategy: "lp_vertex_enumeration_v1"`
  - `requested`
  - `returned`
  - `alternatives`
- Persist this metadata only when requested K is greater than 1. Default K=1 rows should keep the existing `_system` shape except for already-established provider/execution/fallback/reproducibility metadata.
- Owner-visible `GET /v1/optimizations/{id}` returns the same alternatives/count fields as the original POST success response.
- Idempotency replay for the same body/mode/key returns the persisted alternatives without executing the solver again.
- Cross-user GET remains 404.

### AC5: fallback and demo share the same top-k behavior

- `_execute_fallback_attempts()` returns alternatives from the terminal successful attempt only.
- The aggregate `LPSolveResult` created by `_execute_fallback_attempts()` must copy `terminal_result.alternatives`; otherwise terminal fallback alternatives would be lost before route persistence/response.
- If primary attempt fails but fallback succeeds, alternatives are computed from the fallback result and persisted with the executed provider route.
- Fallback metadata remains under `_system.fallback_execution`; top-k metadata must not overwrite it.
- `/v1/optimizations/demo` accepts the same `options.top_k_alternatives` LP option.
- Demo success returns `alternatives` and count fields when K > 1.
- Demo continues to have no DB persistence, billing, voucher issuance, or idempotency side effects.

### AC6: timeout, async, billing, cost, and reproducibility boundaries do not drift

- Timeout responses keep Story 3.4 behavior and do not include alternatives.
- Effective async queued path does not execute solver and does not include alternatives in the 202 response.
- Billing reserve/finalize remains exactly once for effective sync with `X-Billing-Charge-Id`.
- Billing finalize elapsed seconds uses terminal `result.solve_seconds`, including any top-k computation time reported by the solver wrapper.
- Cost attribution still records one `solver_second` row per terminal sync LP result, not one row per alternative.
- Reproducibility voucher issuance remains limited to completed sync runs; if `options.reproducible=true`, response may include both `reproducibility` and alternatives.
- The reproducibility fingerprint continues to use the original request body and therefore changes when `options.top_k_alternatives` changes.
- Rerun requests built from a reproducible source optimization must honor the locked `options.top_k_alternatives` value in that source payload and return/persist alternatives the same way as a fresh completed sync run.
- `rerun_reproduction()` currently calls `solvers.solve_from_request()` directly rather than `_execute_fallback_attempts()`. The implementation must pass `top_k_alternatives=clean_payload.options.top_k_alternatives` on that direct path and attach top-k metadata to the rerun row before `_build_rerun_response_content()`.
- `repro_bitwise_audit.py` may continue comparing the primary solution/objective digest only; Story 3.5 must not widen the bitwise audit digest contract.

### AC7: focused tests cover schema, solver alternatives, API response, persistence, replay, fallback, demo, and boundaries

Add focused tests, preferably `apps/solver-orchestrator/tests/test_top_k_alternatives.py`:

1. `OptimizationOptions` accepts omitted/default `top_k_alternatives == 1` and rejects `0`/`11`.
2. `solve_lp(..., top_k_alternatives=3)` on a bounded LP with at least three feasible vertices returns three ranked alternatives with finite scores.
3. Alternatives are feasible, deduplicated, deterministic, and sorted by objective for minimize/maximize.
4. Authenticated sync LP with `options.top_k_alternatives: 3` returns `200`, count fields, and three alternatives with rank/score/objective/solution.
5. Default sync LP response omits alternatives/count fields.
6. Completed row persists `_system.top_k_alternatives`; GET returns the same alternatives.
7. Idempotency replay with same key/body/mode returns persisted alternatives and does not call solver again.
8. Fallback success after a retryable failure returns terminal attempt alternatives and preserves fallback metadata.
9. Demo LP with top K returns alternatives and still has no persistence/billing side effects.
10. Timeout with top K returns Story 3.4 timeout payload without alternatives.
11. Async queued request with top K returns 202 queued-only payload without alternatives and without solver/billing side effects.
12. Existing sync/async, fallback, billing, max-solve-seconds, reproduction, and solver tests remain green.

### AC8: Quality gates pass

Run before commit:

- `uv run pytest apps/solver-orchestrator/tests/test_top_k_alternatives.py -q`
- `uv run pytest apps/solver-orchestrator/tests/test_sync_async_mode.py apps/solver-orchestrator/tests/test_fallback_execution.py apps/solver-orchestrator/tests/test_max_solve_seconds_cap.py apps/solver-orchestrator/tests/test_billing_integration.py -q`
- `uv run pytest apps/solver-orchestrator/tests -q`
- `uv run mypy apps packages`
- `uv tool run pre-commit run --all-files --show-diff-on-failure`
- `git diff --check`

## Tasks / Subtasks

- [x] Task 1: Add schema and response contracts (AC: 1, 3)
  - [x] Add bounded `OptimizationOptions.top_k_alternatives`.
  - [x] Add response builder support for optional alternatives and count fields without emitting null default fields.
  - [x] Keep default response shape unchanged when K is omitted or equals 1.

- [x] Task 2: Add LP top-k candidate generation (AC: 2)
  - [x] Extend `LPSolveResult` with optional alternatives.
  - [x] Implement bounded deterministic LP vertex enumeration for small/medium LPs.
  - [x] Score, rank, sort, and deduplicate alternatives.
  - [x] Return primary-only metadata when enumeration is capped or insufficient.

- [x] Task 3: Wire API persistence/replay/demo/fallback (AC: 4, 5)
  - [x] Persist success alternatives in `_system.top_k_alternatives`.
  - [x] Expose persisted alternatives in POST success, GET success, and idempotency replay.
  - [x] Copy terminal fallback alternatives into the aggregate result without changing fallback metadata.
  - [x] Add demo response alternatives for LP success.

- [x] Task 4: Preserve timeout/async/billing/cost/repro boundaries (AC: 6)
  - [x] Ensure timeout payloads omit alternatives.
  - [x] Ensure async queued path remains solver-free and alternatives-free.
  - [x] Keep billing/cost/voucher behavior unchanged except elapsed seconds including reported solver time.
  - [x] Update the direct reproducible rerun solve path to pass through locked top-k and response metadata without changing bitwise audit digest semantics.

- [x] Task 5: Add focused tests and run gates (AC: 7, 8)
  - [x] Add top-k tests.
  - [x] Run focused and adjacent regression suites.
  - [x] Run full solver-orchestrator tests, mypy, pre-commit, and diff check.

### Review Findings

- [x] [Review][Patch] `solve_from_request()` should keep malformed top_k option in the solver error-result contract instead of raising `ValueError` [apps/solver-orchestrator/src/solver_orchestrator/solvers.py] — added malformed top-k regression coverage and returned `LPSolveResult(status="error", error_field_path="options.top_k_alternatives")`.

## Dev Notes

### Current Implementation Facts

- `OptimizationOptions` currently has `max_solve_seconds`, `reproducible`, and `anonymous`.
- `OptimizationResponse` currently has no alternatives field.
- `solvers.LPSolveResult` currently carries one `objective` and one `solution`.
- `solvers.solve_from_request()` parses LP payloads and delegates to `solve_lp()`.
- `routes._execute_fallback_attempts()` is the shared sync fallback execution helper for authenticated and demo routes.
- `routes._build_response_content()` is the completed authenticated response builder used by POST, GET, and idempotency replay.
- `routes.post_optimization()` stores success rows in `optimizations.solution/objective/solve_seconds` and stores system metadata under `input_payload._system`.
- `routes.post_optimization_demo()` builds a separate LP success response and must be updated separately.
- `routes.rerun_reproduction()` validates the source payload as `OptimizationRequest` and calls `solvers.solve_from_request()` directly; it will not automatically inherit `_execute_fallback_attempts()` top-k wiring.
- `repro_bitwise_audit.py` also calls `solvers.solve_from_request()` directly but compares only primary `objective` and `solution` in the canonical digest.
- Story 3.4 timeout response is built by `_solver_timeout_response()` and should not grow alternatives.

### Implementation Guidance

- Prefer helper names like `_lp_top_k_alternatives`, `_enumerate_lp_vertices`, `_rank_lp_alternatives`, `_top_k_metadata_from_result`, and `_attach_top_k_metadata`.
- Keep the primary `solution` field stable as `{"x": [...]}`.
- Do not store alternatives in `Optimization.solution`; use `_system.top_k_alternatives`.
- Keep enumeration bounded with explicit constants, for example `MAX_TOP_K_VERTEX_VARIABLES` and `MAX_TOP_K_VERTEX_COMBINATIONS`.
- Use only `numpy` and standard library; `numpy` is already used by the solver wrapper.
- Candidate enumeration should include:
  - original `A·x ≤ b` rows,
  - finite lower bounds as active constraints,
  - finite upper bounds as active constraints.
- Validate feasibility with a small tolerance such as `1e-7`.
- Dedupe rounded coordinate tuples so equivalent numerical points do not produce duplicate alternatives.
- Sort non-primary candidates by original objective and lexicographic solution, not discovery order; keep the primary solver result as rank 1.
- Reject/skip non-finite candidate coordinates or objectives before scoring.
- Treat default HiGHS upper bound (`kHighsInf`) as no finite upper-bound active constraint; do not build fake active constraints from infinity.
- If active-constraint combinations produce singular systems, skip those combinations without failing the solve.
- If enumeration returns fewer than requested K candidates, surface the lower returned count instead of padding with duplicates or perturbing infeasible points.
- Score can be based on relative objective gap from the best returned objective:
  `normalizer = max(abs(best_objective), 1.0)`, `relative_gap = max(0, candidate_objective - best_objective) / normalizer` for minimize and `max(0, best_objective - candidate_objective) / normalizer` for maximize, then `score = 1 / (1 + relative_gap)`, with rank 1 forced to `1.0`.
- If top-k computation raises internally, degrade to primary-only alternatives rather than failing an otherwise optimal LP solve; add tests for normal path rather than relying on exception swallowing.
- `model_dump(by_alias=True)` will include the default top-k value, so omitted and explicit `top_k_alternatives: 1` may hash differently only if Pydantic serializes explicit/default fields differently. Confirm tests around idempotency use stable body shape expected by existing code.
- In current route code, `payload.model_dump(by_alias=True)` serializes defaults, so omitted and explicit `options.top_k_alternatives: 1` should normalize to the same hash input. Add/keep a focused test if implementation changes dump options.

### Suggested Test LPs

- For maximize top 3, use `max x1 + x2 + x3` subject to `x1 + x2 + x3 ≤ 10`, `x ≥ 0`. The top three vertex candidates can be `[10,0,0]`, `[0,10,0]`, `[0,0,10]` with objective 10 and score 1.0.
- For minimize sorting, use a bounded simplex-like LP with finite upper bounds so second/third vertices have deterministic higher objectives.
- Include a primary-first assertion rather than assuming lexicographic order decides rank 1 when multiple optimal vertices exist.
- Include an insufficient-candidates case, for example a one-variable bounded LP with `top_k_alternatives: 3`, and assert returned count is less than requested.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Users mistake LP alternatives for exact global k-best over a continuous solution manifold | Document v1 as deterministic feasible LP vertex candidates, not MILP/CP-SAT k-best. |
| Default response breaks existing clients | Omit alternatives/count fields unless `top_k_alternatives > 1`. |
| Alternatives are persisted in the wrong field and corrupt `solution` | Store under `_system.top_k_alternatives`; keep `Optimization.solution` as main solution only. |
| Enumeration explodes combinatorially | Cap variables/combinations and return primary-only metadata when cap is exceeded. |
| Fallback alternatives come from the wrong attempt | Use terminal `execution.result` and final route only. |
| Async queued response implies work already happened | Keep async solver-free and alternatives-free in Story 3.5. |
| Billing/cost charges per alternative | Continue one terminal solver result and one cost event per optimization. |
| Timeout includes stale or partial alternatives | Only attach alternatives on `status="optimal"`. |
| Degenerate LP has many equivalent vertices and rank 1 drifts away from HiGHS primary solution | Pin rank 1 to the primary result and sort only the remaining candidates. |
| Singular active-constraint combinations fail enumeration | Skip singular combinations and return the candidates that remain. |
| Infinite upper bounds generate invalid vertices | Only finite upper bounds become active constraints. |

## Definition of Done

- Story file has passed three pre-implementation reviews and all resulting patches are applied.
- Sync LP requests accept `options.top_k_alternatives` and return ranked alternatives when K > 1.
- Alternatives are feasible, deterministic, scored, persisted, and replayed through GET/idempotency.
- Demo and fallback success paths share the same top-k behavior.
- Timeout, async, billing, cost attribution, and reproducibility boundaries remain intact.
- AC8 quality gates pass or any inability to run them is documented.
- Sprint status and Dev Agent Record are updated.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-27 - Story moved to in-progress after three pre-implementation review rounds; starting RED phase with focused top-k alternatives tests.
- 2026-05-27 - RED phase passed: focused top-k tests failed on missing schema field, solver parameter/result alternatives, response/persistence metadata, and demo fixture gap.
- 2026-05-27 - Implemented bounded LP vertex enumeration, top-k metadata persistence/response expansion, fallback aggregate copying, demo response support, and rerun metadata attachment.
- 2026-05-27 - Focused top-k tests passed: `uv run pytest apps/solver-orchestrator/tests/test_top_k_alternatives.py -q` -> 9 passed.
- 2026-05-27 - Adjacent regression suite passed: sync/async, fallback, max-solve-seconds, billing -> 48 passed.
- 2026-05-27 - Full validation passed before code review: solver-orchestrator suite 211 passed; `uv run mypy apps packages` passed; `uv tool run pre-commit run --all-files --show-diff-on-failure` passed; `git diff --check` passed.
- 2026-05-27 - Post-implementation code review found one patch item: malformed `options.top_k_alternatives` on direct solver dict input could raise instead of returning an error result. Added regression test and fixed.
- 2026-05-27 - Final validation passed after code-review patch: focused Story 3.5 tests 10 passed; full solver-orchestrator suite 212 passed; mypy/pre-commit/diff-check passed.

### Completion Notes List

- Added `options.top_k_alternatives` bounded to 1..10 with default 1.
- Added deterministic LP vertex alternatives for small LPs, with primary solution pinned to rank 1 and non-primary candidates ranked/scored after feasibility and dedupe.
- Persisted top-k success metadata under `_system.top_k_alternatives` only when K > 1, and exposed it through POST success, GET success, and idempotency replay.
- Propagated terminal fallback alternatives into the aggregate result and added demo top-k success payloads.
- Updated reproducible rerun success rows to attach top-k metadata while leaving bitwise audit primary digest scope unchanged.
- Validation passed before post-implementation review: focused Story 3.5 tests, adjacent regressions, full solver-orchestrator tests, mypy, pre-commit, and diff check.
- Completed post-implementation code review and fixed malformed direct top-k option handling in the solver wrapper.
- Final validation passed after review patch: `test_top_k_alternatives.py` 10 passed; full solver-orchestrator suite 212 passed; mypy/pre-commit/diff-check passed.

### File List

- `_bmad-output/stories/3-5-top-k-alternatives.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`
- `apps/solver-orchestrator/src/solver_orchestrator/solvers.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/test_top_k_alternatives.py`

### Change Log

- 2026-05-27 - Initial Story 3.5 draft created from Epics/PRD/Architecture/current solver-orchestrator implementation.
- 2026-05-27 - Story Review Round 1 patches applied for response-shape compatibility, metadata persistence boundaries, robust score normalization, stable default hashing, and reproducible rerun parity.
- 2026-05-27 - Story Review Round 2 patches applied for fallback aggregate result copying, direct rerun solve wiring, and bitwise audit boundary.
- 2026-05-27 - Story Review Round 3 patches applied for primary rank stability, non-optimal/no-primary closure, finite-bound handling, singular-combination handling, and insufficient-candidate tests.
- 2026-05-27 - Started Story 3.5 implementation after completing all required pre-implementation story reviews.
- 2026-05-27 - Implemented Story 3.5 top-k alternatives schema, solver candidate generation, API response/persistence/replay wiring, demo/fallback/rerun support, and focused tests.
- 2026-05-27 - Code review patch pass completed; malformed direct top-k option handling fixed and fully revalidated.

## Story Review Round 1 - Data Consistency (2026-05-27)

### Findings

- [x] [Patch] Adding nullable alternatives/count fields directly to `OptimizationResponse` could emit `null` keys for default K=1 responses and break the existing success response shape. The story now requires conditional attachment or `exclude_none=True`, plus default-shape tests.
- [x] [Patch] The first draft's score formula did not pin maximize, zero, or negative objective normalization. The story now defines direction-aware relative gap with `max(abs(best_objective), 1.0)`.
- [x] [Patch] Persisting top-k metadata for default K=1 rows would create unnecessary `_system` drift. The story now persists `_system.top_k_alternatives` only for requested K > 1.
- [x] [Patch] Reproducible rerun parity was underspecified. The story now requires reruns from locked source payloads to honor and return/persist the locked top-k value.

### Result

Round 1 passed after patches. Request normalization, public response fields, persisted metadata, scoring values, and reproducible rerun data contracts are now explicit.

## Story Review Round 2 - Function / Dependency Consistency and Drift (2026-05-27)

### Findings

- [x] [Patch] The first draft said fallback alternatives come from the terminal attempt but did not mention the aggregate `LPSolveResult` object created by `_execute_fallback_attempts()`. The story now requires copying terminal alternatives into that aggregate result.
- [x] [Patch] Reproducible reruns bypass the shared fallback helper and directly call `solvers.solve_from_request()`, so they would not inherit top-k behavior automatically. The story now requires direct rerun top-k parameter passing and metadata attachment.
- [x] [Patch] Bitwise audit also calls the solver directly, but its current digest contract is primary solution/objective only. The story now explicitly keeps that audit digest unchanged to avoid unplanned reproducibility scope creep.

### Result

Round 2 passed after patches. Shared fallback, demo/auth sync, reproducible rerun, and bitwise audit function boundaries are now aligned with the existing code paths.

## Story Review Round 3 - Boundary / Edge Cases / Closure (2026-05-27)

### Findings

- [x] [Patch] Multiple equivalent LP optima could let lexicographic sorting move HiGHS' primary solution away from rank 1 while the top-level `solution` still shows the primary result. The story now pins rank 1 to the primary solver result and sorts only the remaining candidates.
- [x] [Patch] Non-optimal terminal states and missing/non-finite primary solutions were not fully closed. The story now prohibits alternatives for unbounded/infeasible/timeout/error and requires no top-k metadata if the primary optimal solution is not reliable.
- [x] [Patch] Enumeration boundary handling was underspecified for infinite upper bounds and singular active-constraint systems. The story now requires finite upper-bound filtering and skip-on-singular behavior.
- [x] [Patch] Tests did not explicitly require insufficient-candidate behavior. The story now adds a returned-less-than-requested case and forbids duplicate padding.

### Result

Round 3 passed after patches. Primary-solution stability, non-optimal closure, finite-bound handling, singular systems, and insufficient candidate behavior are now specified before implementation.
