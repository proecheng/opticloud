---
story_key: 3-4-max-solve-seconds-cap
epic_num: 3
story_num: 3.4
epic_name: Optimization & Prediction Execution
status: done
priority: High (FR E4 v1 must-have; closes user-visible runtime and billing cap)
sizing: M (~4-6 hours; solver wrapper + sync route timeout response/persistence + fallback budget + focused tests)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-27
sources:
  - _bmad-output/planning/epics.md:69 (FR E4 max_solve_seconds v1 must-have)
  - _bmad-output/planning/epics.md:1421-1423 (Story 3.4 AC)
  - _bmad-output/planning/prd.md:960 (Credits cap and true-up)
  - _bmad-output/planning/prd.md:1121-1137 (options.max_solve_seconds API and error field_path)
  - _bmad-output/planning/prd.md:1471 (E4 must-have)
  - _bmad-output/planning/architecture.md:1622 (E4 owned by solver-orchestrator + billing-service)
  - _bmad-output/stories/5-a-4-per-formula-charging-capped.md (billing cap math and finalize contract)
  - _bmad-output/stories/2-7-fallback-execution.md (fallback aggregate solve_seconds and metadata)
  - _bmad-output/stories/3-3-sync-async-mode.md (sync/async routing, compact status, idempotency replay)
  - apps/solver-orchestrator/src/solver_orchestrator/solvers.py (HiGHS time_limit and LPSolveResult)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py (POST/GET optimization, billing finalize, fallback execution)
dependencies:
  upstream:
    - 3-1-j1-lp-solve (done) - LP solve, persistence, RFC 7807 timeout response.
    - 2-7-fallback-execution (done) - fallback loop and aggregate solver seconds.
    - 3-3-sync-async-mode (done) - sync effective mode, async side-effect boundary, compact GET for timeout rows.
    - 5-a-4-per-formula-charging-capped (done) - billing finalize clamps elapsed by Saga max_solve_seconds.
    - m2-3-cost-attribution (done) - solver_second attribution uses terminal LPSolveResult.solve_seconds.
  downstream:
    - 3-8-cancel-refund - async cancellation/refund policy.
    - 3-9-status-progress-eta - richer progress/ETA for running async rows.
    - 3-14-mock-real-divergence-test - broader timeout contract parity.
---

# Story 3.4 - max_solve_seconds 封顶 (FR E4)

## User Story

作为 API 用户，
我希望在 `POST /v1/optimizations` 的 `options.max_solve_seconds` 中设置本次求解的最长运行时间，
以便求解超过该上限时系统自动停止、返回当前可用 best solution，并且 Credits 不会超过封顶预算。

## Why This Story

当前 schema 已经接受 `options.max_solve_seconds`，solver wrapper 也把它传给 HiGHS `time_limit`，billing-service 的 `compute_charge_amount()` 也会按 Saga 中的 max 值 clamp 金额。但 E4 还没有完整闭环：

- HiGHS timeout 分支丢弃了可能存在的 incumbent/current solution。
- Authenticated timeout 行不会把 best solution/objective 持久化或返回给用户。
- Fallback loop 每个 attempt 都拿完整 `max_solve_seconds`，多次 timeout 可能把用户声明的请求级时间预算放大为 `(1 + fallback_count) * max_solve_seconds`。
- Timeout/error 分支没有像 infeasible 一样写入 idempotency mapping，重试同 key 可能再次求解。

本 story 把 `max_solve_seconds` 从“字段和底层 time_limit”升级为同步 LP 请求的请求级封顶合同：同一个 optimization 的所有 fallback attempts 共享一个剩余时间预算；超时后返回/持久化当前 best solution（如果 solver 提供）；billing finalize、cost attribution、public `solve_seconds`、GET/idempotency replay 使用同一个终端结果语义。

## Out of Scope

- 不实现 async worker、队列执行、async cancel/refund 或 SSE progress。
- 不改变 `mode=async` queued-only 行为；queued async 仍不执行 solver，也不计费。
- 不改变 billing-service 金额公式；`compute_charge_amount()` 继续是金额 clamp 的 source of truth。
- 不为 non-LP task types 新增求解器。
- 不为 reproducibility timeout runs 签发 voucher；voucher 仍只给 completed runs。
- 不改变 rerun 的成功前置条件；rerun timeout 继续不创建 child voucher。
- 不新增 DB column；复用 `optimizations.solution/objective/solve_seconds/error/input_payload`.

## Acceptance Criteria

### AC1: max_solve_seconds schema and sync path remain explicit

- `OptimizationOptions.max_solve_seconds` remains a float with existing bounds `ge=1.0`, `le=600.0`.
- Omitted `options.max_solve_seconds` keeps current default `30.0`.
- Effective sync LP execution passes the current remaining budget to `solvers.solve_from_request(..., max_solve_seconds=...)`.
- Effective async queued path does not execute solver and does not change because of this story.
- Invalid schema values continue to fail before provider route, billing reserve, persistence, solver execution, cost attribution, or voucher issuance.

### AC2: HiGHS timeout exposes current best solution when available

When `solve_lp()` receives `HighsModelStatus.kTimeLimit`:

- It must return `LPSolveResult(status="timeout", solve_seconds=elapsed, error_field_path="options.max_solve_seconds")`.
- It must attempt to read `h.getSolution()` and `h.getInfo().objective_function_value`.
- If solution vector length matches the number of columns and all values are finite, return `solution={"x": [...]}`.
- If objective is finite, return `objective=<float>`; otherwise leave `objective=None`.
- If no reliable solution/objective is available, keep `solution=None`/`objective=None`; do not fabricate zeros or mark timeout as completed.
- Existing optimal/infeasible/unbounded/error behavior remains unchanged.

### AC3: timeout response returns best solution payload without pretending success

For authenticated `POST /v1/optimizations` effective sync LP where terminal result is `timeout`:

- HTTP status remains `504`.
- RFC 7807 `title` remains `Solver Timeout`.
- `errors[0].field_path == "options.max_solve_seconds"`.
- Response includes:
  - `optimization_status: "timeout"`
  - `solve_seconds`
  - `max_solve_seconds`
  - `best_solution_available: true|false`
  - `best_solution` only when `result.solution` is not null
  - `objective` only when `result.objective` is not null
- It must not return `status="completed"` and must not issue reproducibility vouchers.

### AC4: timeout rows persist best solution and compact GET exposes it

For timeout rows:

- `optimizations.status == "timeout"`.
- `optimizations.solve_seconds` is the request aggregate solver seconds.
- `optimizations.solution` stores the best solution if available; otherwise null.
- `optimizations.objective` stores the timeout objective if available; otherwise null.
- `optimizations.error` stores timeout detail plus `fallback_execution`.
- Owner-visible `GET /v1/optimizations/{id}` returns compact status with `status="timeout"`, `error`, `solve_seconds`, and optional `best_solution`/`objective`.
- Cross-user GET remains 404.

### AC5: fallback attempts share one request-level time budget

For shared sync LP fallback execution (`_execute_fallback_attempts()`, used by authenticated POST and demo POST):

- The first attempt receives `payload.options.max_solve_seconds`.
- Each later fallback attempt receives `max(payload.options.max_solve_seconds - total_solve_seconds_so_far, 0.0)`.
- If total solver seconds already reached or exceeded the requested cap after a retryable timeout/error, do not execute another fallback attempt.
- Persisted `_system.fallback_execution` must record only attempts that actually ran.
- `terminal_status`, `terminal_attempt`, `exhausted`, and aggregate `solve_seconds` must remain consistent with Story 2.7 metadata.
- Existing fallback success behavior remains green when total time is below the cap.
- Demo path receives the same remaining-budget behavior because it calls the same helper, but demo still has no DB persistence, billing, voucher issuance, or idempotency side effects.

### AC6: billing, cost attribution, and timeout state use the same terminal result

For authenticated sync LP timeout with `X-Billing-Charge-Id`:

- Billing reserve still occurs before solving.
- Billing finalize is called once with `status="success"`, `failure_reason=None`, and `elapsed_seconds=result.solve_seconds`.
- Rationale: E4 timeout is the max-solve-seconds cap completing as designed and must charge actual elapsed solver seconds. In billing-service today, `status="failure"` refunds to net zero, which would violate PRD "Credits 按实际秒数扣费".
- billing-service remains responsible for amount clamp via Saga `max_solve_seconds`; solver-orchestrator must not compute money.
- If billing finalize fails, existing `billing_finalize_failed` metadata is preserved and also keeps timeout/fallback/best-solution information.
- Cost attribution records one `solver_second` row for the timeout terminal result using the same `result.solve_seconds`.

### AC7: idempotency closes timeout replay

For a timeout/error terminal row created with `Idempotency-Key`:

- The idempotency mapping is persisted before returning the terminal error response.
- If idempotency insert fails after solver execution, return existing 409 conflict and do not issue voucher; the already-persisted terminal optimization row may remain for audit, matching current success/infeasible behavior.
- Repeating the same request with the same key and same normalized mode/body returns the persisted compact status response instead of re-executing solver.
- Replay exposes the persisted `best_solution`/`objective` for timeout rows when present.
- Same key with different mode/body still returns existing 409 conflict.

### AC8: focused tests cover cap, best-solution timeout, fallback budget, billing, and replay

Add focused tests, preferably `apps/solver-orchestrator/tests/test_max_solve_seconds_cap.py`:

1. `solve_lp` timeout branch can carry a best solution/objective when HiGHS reports one (unit-test via a small helper or monkeypatch-safe seam if direct HiGHS timeout is not deterministic).
2. Authenticated sync timeout with synthetic `LPSolveResult(status="timeout", solution=..., objective=...)` returns 504 with best solution fields.
3. Timeout row persists `solution`, `objective`, `solve_seconds`, and GET returns compact timeout status with `best_solution`.
4. Timeout with `X-Billing-Charge-Id` calls reserve once and finalize once with `status="success"`, `failure_reason=None`, and elapsed seconds from terminal result.
5. Cost attribution records one timeout solver_second row.
6. Fallback budget stops executing additional retries when aggregate seconds reaches cap.
7. Later fallback attempt receives remaining budget rather than the full original max.
8. Timeout idempotency replay does not call solver again and returns persisted compact status.
9. Timeout without best solution returns 504 with `best_solution_available=false` and GET omits `best_solution`.
10. Demo fallback path uses the same remaining budget and still has no persistence/billing side effects.
11. Async queued mode still avoids solver/billing side effects.
12. Existing sync/async, fallback, billing, routing, unaudited-self tests remain green.

### AC9: Quality gates pass

Run before commit:

- `uv run pytest apps/solver-orchestrator/tests/test_max_solve_seconds_cap.py -q`
- `uv run pytest apps/solver-orchestrator/tests/test_sync_async_mode.py apps/solver-orchestrator/tests/test_fallback_execution.py apps/solver-orchestrator/tests/test_billing_integration.py -q`
- `uv run pytest apps/solver-orchestrator/tests -q`
- `uv run mypy apps packages`
- `uv tool run pre-commit run --all-files --show-diff-on-failure`
- `git diff --check`

## Tasks / Subtasks

- [x] Task 1: Add solver timeout best-solution support (AC: 2)
  - [x] Extract a small helper that safely reads finite incumbent solution/objective from HiGHS.
  - [x] Populate timeout `LPSolveResult.solution/objective` only when reliable.
  - [x] Keep optimal/infeasible/unbounded/error behavior unchanged.

- [x] Task 2: Enforce request-level fallback time budget (AC: 1, 5)
  - [x] Pass remaining budget into each fallback attempt.
  - [x] Stop retrying once aggregate solve seconds reaches the cap.
  - [x] Preserve Story 2.7 metadata for attempts that actually ran.

- [x] Task 3: Persist and return timeout best-solution payload (AC: 3, 4)
  - [x] Add a focused timeout response helper that extends RFC 7807 without replacing HTTP `status`.
  - [x] Persist timeout best solution/objective on `Optimization`.
  - [x] Extend compact GET timeout response with `solve_seconds`, optional `best_solution`, and optional `objective`.

- [x] Task 4: Close timeout billing/cost/idempotency loop (AC: 6, 7)
  - [x] Keep billing finalize failure metadata while merging timeout metadata.
  - [x] Ensure timeout/error terminal rows write idempotency mappings before returning.
  - [x] Replay timeout/error idempotency rows as compact status without solver execution.
  - [x] Keep voucher issuance limited to completed runs.

- [x] Task 5: Add focused tests and run gates (AC: 8, 9)
  - [x] Add max_solve_seconds cap tests.
  - [x] Run focused and adjacent regression suites.
  - [x] Run full solver-orchestrator tests, mypy, pre-commit, and diff check.

### Review Findings

- [x] [Review][Patch] New untracked test file was not covered by `pre-commit run --all-files`; removed unused imports from `test_max_solve_seconds_cap.py` and reran validation after including the file in the working diff.
- [x] [Review][Patch] Timeout/error terminal rows should record solver-second cost attribution before a post-solve idempotency insert conflict can return 409, so audit rows are not left without cost attribution. Moved timeout/error cost recording before idempotency insertion.

## Dev Notes

### Current Implementation Facts

- `OptimizationOptions.max_solve_seconds` already exists with default `30.0`, `ge=1.0`, `le=600.0`.
- `solvers.solve_lp()` sets HiGHS option `time_limit` from `max_solve_seconds`.
- `solvers.LPSolveResult` already has optional `objective` and `solution`, so no schema/dataclass expansion is required for timeout best solution.
- `routes._execute_fallback_attempts()` currently passes full `max_solve_seconds` to every attempt and aggregates `solve_seconds`.
- `routes._execute_fallback_attempts()` is called by both authenticated `POST /v1/optimizations` and unauthenticated `/v1/optimizations/demo`; implement remaining-budget logic inside the shared helper so the two paths cannot drift.
- `routes.post_optimization()` already calls billing reserve before solve and finalize after terminal result when `X-Billing-Charge-Id` is provided.
- Existing code currently maps every non-optimal terminal result to billing `status="failure"`; Story 3.4 must special-case `result.status == "timeout"` to billing `status="success"` so billing-service charges actual elapsed seconds instead of refunding to zero.
- billing-service `compute_charge_amount()` clamps elapsed to Saga `max_solve_seconds` and reserved amount; do not duplicate money math in solver-orchestrator.
- `routes._record_solver_cost_attribution()` records one best-effort `solver_second` event for terminal LP results.
- `routes._build_optimization_status_response_content()` already handles queued/in_progress/failed/timeout compact status but does not include timeout best solution.
- Timeout and error branches currently return before writing idempotency mappings; infeasible/unbounded and success paths do write mappings.

### Implementation Guidance

- Prefer helper names like `_best_timeout_solution_from_highs`, `_solver_timeout_response`, and `_add_optimization_idempotency_key` reuse.
- Avoid adding new response models if a small extra payload on the RFC 7807 response is enough.
- Do not override RFC 7807 integer `status` with optimization status. Use `optimization_status`.
- Store the best solution in `Optimization.solution`; return it as `best_solution` on timeout error/status payloads to avoid confusing it with completed `solution`.
- For fallback budget, guard against tiny float overrun with a small epsilon such as `1e-9`; do not run an extra fallback when remaining budget is effectively zero.
- If a synthetic test returns `solve_seconds` greater than the passed remaining budget, use the actual reported seconds for audit/cost/finalize but stop further attempts.
- If a retryable `error` consumes the entire budget before any timeout result exists, terminal status may remain `error`; do not rewrite it to `timeout`.
- Keep `attempt_metadata` bounded and secret-free; do not add auth headers, billing charge IDs, or raw payloads.
- If the timeout result has no best solution, preserve existing timeout error behavior plus `best_solution_available=false`; do not write empty `{}` into `Optimization.solution`.
- Do not change `mode=async` behavior from Story 3.3.
- Do not fork separate fallback loops for demo and authenticated routes; change the shared helper and update tests around both callers.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Timeout best solution is mistaken for optimal result | Keep HTTP 504, `optimization_status="timeout"`, and expose timeout payload as `best_solution`, not completed `solution`. |
| Fallback retries multiply user time budget | Share one request-level budget and stop once aggregate seconds reaches cap. |
| Billing/cost/public seconds drift | Use the terminal aggregate `LPSolveResult.solve_seconds` for persistence, billing finalize, cost attribution, and response. |
| Timeout billing accidentally refunds all Credits | For `result.status == "timeout"`, call billing finalize with `status="success"` while keeping optimization status `timeout`; this uses existing billing cap math without changing money code. |
| HiGHS returns no reliable incumbent on timeout | Return `best_solution_available=false`; do not fabricate a solution. |
| Timeout replay re-executes and charges again | Persist idempotency mapping for timeout/error terminal rows before returning. |
| Idempotency insert races after terminal solve | Return 409 and do not issue voucher; document that the terminal optimization audit row may remain, matching current non-atomic sync terminal behavior. |
| Async queued path accidentally starts solving | AC1/AC8 keep async side-effect-free. |

## Definition of Done

- Story file has passed three pre-implementation reviews and all resulting patches are applied.
- Sync LP `max_solve_seconds` is enforced as a request-level budget across fallback attempts.
- Timeout response/persistence/GET expose best solution when available without marking the run completed.
- Billing finalize, cost attribution, public solve seconds, and persisted rows remain consistent.
- Timeout/error idempotency replay is closed.
- Existing sync/async, fallback, billing, routing, unaudited-self, and reproduction behavior remains green.
- AC9 quality gates pass or any inability to run them is documented.
- Sprint status and Dev Agent Record are updated.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-27 - Wrote Story 3.4 focused tests first; initial red run showed missing HiGHS timeout incumbent helper, timeout response payload, fallback shared budget, timeout billing status, cost attribution id, and timeout idempotency replay.
- 2026-05-27 - Implemented `_timeout_result_from_highs`, request-level fallback remaining budget, timeout best-solution persistence/response/GET, timeout billing success finalize, and timeout/error idempotency mapping.
- 2026-05-27 - Updated adjacent fallback billing expectation: timeout is now E4 cap completion charged by elapsed seconds, not billing failure/refund.
- 2026-05-27 - Validation passed: focused Story 3.4 tests, adjacent sync/async/fallback/billing regressions, full solver-orchestrator tests, mypy, pre-commit, and diff whitespace check.
- 2026-05-27 - Post-implementation code review found two patch items: untracked test file lint coverage and timeout/error cost attribution ordering. Both were fixed.
- 2026-05-27 - Final validation passed after code-review patches: focused tests, adjacent regressions, full solver suite, mypy, pre-commit, and diff check.

### Completion Notes List

- Added finite incumbent extraction for HiGHS time-limit results; unreliable incumbent/objective values are omitted instead of fabricated.
- Enforced `max_solve_seconds` as a request-level sync fallback budget by passing remaining seconds to later attempts and stopping once exhausted.
- Extended authenticated timeout responses with `optimization_id`, `optimization_status`, `solve_seconds`, `max_solve_seconds`, and optional `best_solution`/`objective`.
- Persisted timeout best solution/objective on the `Optimization` row and exposed the same data through owner-visible compact GET.
- Changed timeout billing finalize semantics to `status="success"` with elapsed seconds so billing-service charges actual elapsed time under its existing cap math.
- Closed timeout/error idempotency replay so repeated same-key terminal failures return persisted status instead of re-solving.
- Validation passed after code-review patches: `test_max_solve_seconds_cap.py` 10 passed; adjacent regression suite 38 passed; full solver-orchestrator suite 202 passed; mypy/pre-commit/diff-check passed.
- Completed post-implementation code review and fixed all patch findings: new test lint hygiene and terminal failure cost-attribution ordering.

### File List

- `_bmad-output/stories/3-4-max-solve-seconds-cap.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/src/solver_orchestrator/solvers.py`
- `apps/solver-orchestrator/tests/test_fallback_execution.py`
- `apps/solver-orchestrator/tests/test_max_solve_seconds_cap.py`

### Change Log

- 2026-05-27 - Initial Story 3.4 draft created from Epics/PRD/Architecture/current solver-orchestrator and billing-service implementation.
- 2026-05-27 - Implemented Story 3.4 max_solve_seconds cap closure, timeout best-solution payload, request-level fallback budget, timeout billing/cost/idempotency loop, and focused regression tests.
- 2026-05-27 - Marked Story 3.4 implementation ready for code review after all AC9 gates passed.
- 2026-05-27 - Code review patch pass completed; terminal failure cost ordering and new-test lint hygiene fixed.
- 2026-05-27 - Final AC9 validation passed; Story 3.4 marked done.

## Story Review Round 1 - Data Consistency (2026-05-27)

### Findings

- [x] [Patch] Timeout billing semantics contradicted PRD E4. The draft inherited the old "non-optimal = billing failure" mapping, but billing-service `status="failure"` refunds net zero. The story now requires timeout finalize `status="success"` with `elapsed_seconds=result.solve_seconds`, while the optimization row/API status remains `timeout`.

### Result

Round 1 passed after patch. The public timeout status, persisted solver result, billing elapsed seconds, and cost attribution now share one data contract without turning timeout into a completed optimization.

## Story Review Round 2 - Function / Dependency Consistency and Drift (2026-05-27)

### Findings

- [x] [Patch] The draft described fallback budget enforcement as an authenticated sync API concern, but the implementation choke point `_execute_fallback_attempts()` is shared by authenticated and demo routes. The story now requires remaining-budget behavior in the shared helper, while preserving demo's no-persistence/no-billing boundary.

### Result

Round 2 passed after patch. The story now reuses the existing fallback helper instead of inviting a duplicate route-specific loop, and it prevents demo/authenticated timeout budget drift.

## Story Review Round 3 - Boundary / Edge Cases / Closure (2026-05-27)

### Findings

- [x] [Patch] The draft did not specify the closure behavior when timeout has no incumbent solution. The story now requires `best_solution_available=false`, no fabricated solution, and no empty solution object in persistence.
- [x] [Patch] The draft implied timeout/error idempotency insertion must happen, but did not define the post-solve insert race behavior. The story now preserves the current sync-terminal pattern: return 409, do not issue voucher, and allow the terminal audit row to remain.
- [x] [Patch] The draft could accidentally rewrite a budget-exhausted retryable `error` into `timeout`. The story now keeps the actual terminal solver status and only stops further attempts when the shared budget is exhausted.

### Result

Round 3 passed after patches. Timeout-without-best-solution, idempotency race, and budget-exhausted retryable-error behavior are now closed.
