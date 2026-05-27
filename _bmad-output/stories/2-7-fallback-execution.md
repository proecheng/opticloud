---
story_key: 2-7-fallback-execution
epic_num: 2
story_num: 2.7
epic_name: Algorithm Catalog
status: done
priority: High (FR C7 v1 must-have; completes the solver/fallback/provider contract)
sizing: M (~4-6 hours; helper + route integration + focused tests; no external providers)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-27
sources:
  - _bmad-output/planning/epics.md:1386
  - _bmad-output/planning/epics.md:1388
  - _bmad-output/planning/prd.md:1114
  - _bmad-output/planning/prd.md:1167
  - _bmad-output/planning/prd.md:1459
  - _bmad-output/planning/architecture.md:516
  - _bmad-output/planning/architecture.md:1324
  - _bmad-output/planning/architecture.md:1621
dependencies:
  upstream:
    - 2-5-fallback-chain (done) - validates `fallback_chain` shape and supported solver membership.
    - 2-6-multi-provider-routing (done) - provides `select_provider_route()` and internal provider route metadata.
    - 3-1-j1-lp-solve (done) - current synchronous LP/HiGHS execution path.
    - m2-3-cost-attribution (done) - records solver-second cost attribution from persisted Optimization rows.
    - 6-b-1..6-b-4 reproducibility/voucher stories (done) - reproducibility locks and vouchers must reflect actual executed route.
  downstream:
    - 2-8-unaudited-block - may reject self algorithms before execution.
    - 3-9-status-progress-eta - may later surface fallback attempt history in status.
    - 7-a-1-capability-registry-v1-schema - later replaces static catalog/provider routing source.
---

# Story 2.7 - Fallback Chain Execution (FR C7)

## User Story

As an API user submitting an optimization request with a fallback chain,
I want the solver orchestrator to automatically try the next configured solver when the selected primary route times out or fails as provider infrastructure,
so that transient solver/provider failures can recover without changing my request while the final response and persisted audit truth show the actual executed provider.

## Why This Story

Story 2.5 accepts and validates `fallback_chain`; Story 2.6 resolves provider routes for the primary solver. The current authenticated and demo LP paths still call `solvers.solve_from_request()` exactly once. FR C7 requires the orchestrator to execute the ordered chain after a primary timeout, bounded to the existing <=3 fallback elements.

This story adds the execution loop and attempt metadata while staying inside the M1-M2 static catalog boundary. The only real solver engine available today is LP/HiGHS, so this work must be a deterministic LP execution orchestration contract, not an early Provider HTTP integration.

## Out of Scope

- No capability-registry service, Redis cache, Provider HTTP client, external/commercial credentials, or circuit-breaker library implementation.
- No new database tables, migrations, async workers, or provider history UI.
- No cross-task fallback. A request keeps its `task_type`; each fallback candidate is resolved against that same task type.
- No pricing model changes or per-provider billing rates.
- No public response shape change except preserving the existing final success/error contract; internal attempt history remains under `_system` / `opt.error`.
- No rerun endpoint fallback behavior. Voucher reruns continue to use the locked solver/model version.
- No non-LP execution change. Authenticated non-LP requests keep the current 501 path; demo non-LP preview keeps the current 501 short-circuit.

## Acceptance Criteria

### AC1: Fallback attempt helper exists

- Add a small helper in `apps/solver-orchestrator/src/solver_orchestrator/fallback_execution.py`.
- The helper builds an ordered attempt plan from:
  - the primary `ProviderRouteResult`,
  - `task_type`,
  - requested primary `solver`,
  - `fallback_chain`.
- Attempt 1 is always the already-selected primary route from Story 2.6.
- Fallback attempts are created by calling `select_provider_route(task_type, candidate)` for each chain element in request order.
- Each planned attempt must carry both:
  - `requested_solver`: the value used to route that attempt (`payload.solver` for primary, chain element for fallback; may be `None` for omitted primary solver),
  - `selected_solver`: the resolved executable solver from the route.
- The helper must not mutate `ProviderRouteResult`, `CATALOG`, request payloads, or database objects.
- The chain length remains bounded by Story 2.5 (`<=3` fallbacks); the helper may defensively cap at 3 but must not silently add more.
- Repeated solvers are allowed and attempted as repeated retries. This preserves Story 2.5's self-include decision and makes `["highs", "highs"]` a real retry path.
- `fallback_chain is None` and `fallback_chain == []` both produce a one-attempt plan containing only the primary route.
- If a fallback candidate cannot be routed despite prior validation, return a typed route-invalid outcome so the route can return an RFC 7807 error before execution.
- Route-invalid fallback candidates should use the existing 400 `Unsupported Fallback Solver` shape with `field_path == "fallback_chain[i]"`.

### AC2: Only retryable outcomes advance the chain

- Retry the next fallback attempt only when a solve result status is retryable infrastructure/provider failure:
  - `timeout`
  - `error`
- Do not retry mathematical/model terminal outcomes:
  - `optimal` ends successfully.
  - `infeasible` and `unbounded` remain 422 terminal outcomes and do not fall back.
- The helper should expose a pure predicate such as `is_retryable_solver_result(result)` so tests can lock the boundary.
- The final HTTP status remains aligned with existing behavior:
  - final `optimal` -> 200
  - final `infeasible` / `unbounded` -> 422
  - final `timeout` after exhausting attempts -> 504
  - final `error` after exhausting attempts -> 422 `Validation Error`

### AC3: Authenticated route executes the chain and persists final truth

- `POST /v1/optimizations` must execute LP attempts in order until success, non-retryable terminal outcome, or chain exhaustion.
- Authenticated `task_type != "lp"` continues to return the existing 501 response and must not call the fallback execution loop.
- For each attempt, call `solvers.solve_from_request(attempt_body, max_solve_seconds=payload.options.max_solve_seconds)` where `attempt_body` is a copy of the original body with only `solver` replaced by that attempt's `selected_solver`. Do not mutate the persisted user body or LP math payload.
- For each attempt, resolve and store that attempt's provider route using Story 2.6 route metadata fields.
- `Optimization.model_version` must be set from the final executed attempt, not always from the primary route.
- `Optimization.solve_seconds` must be non-null for every executed terminal LP row, including terminal failures.
- `reproducibility.locked_model_version`, `reproducibility.locked_solver`, vouchers, and success responses must reflect the final successful attempt.
- If all attempts fail, persisted `Optimization.model_version` should still reflect the final executed attempt so cost attribution and audit data are truthful.
- Idempotency request hashes must continue to use the original request `body_dict`, not per-attempt bodies or `_system` metadata.
- `Optimization.solve_seconds`, public `solve_seconds`, billing finalize elapsed seconds, and cost attribution value must use the total solver seconds consumed across all executed attempts, not only the final attempt's elapsed time.
- M2.3 `_record_solver_cost_attribution()` must be called once for the terminal aggregate result only, with:
  - final attempt result
  - final selected solver
  - final provider id from `Optimization.model_version`
- Existing billing reserve/finalize order is preserved:
  - reserve remains before solving when `X-Billing-Charge-Id` is present.
  - finalize is called once after the terminal result, using terminal result status and total elapsed solver seconds.
  - terminal failure after fallback finalizes as `failure`.

### AC4: Internal fallback metadata is persisted without leaking

- Authenticated requests persist attempt history under `Optimization.input_payload["_system"]["fallback_execution"]`.
- Required fields:
  - `max_fallback_retries`
  - `attempts`
  - `terminal_status`
  - `terminal_attempt`
  - `exhausted`
- Each attempt record includes:
  - `attempt`
  - `role` (`primary` or `fallback`)
  - `requested_solver`
  - `selected_solver`
  - `provider_id`
  - `provider_kind`
  - `provider_url`
  - `routing_reason`
  - `status`
  - `retryable`
  - `solve_seconds`
  - optional `error_field_path`
  - optional `error_constraint`
- Existing `_system.provider_route` remains the primary route metadata for backward compatibility with Story 2.6.
- Add `_system.executed_provider_route` for the terminal executed attempt.
- Public `OptimizationResponse` and `GET /v1/optimizations/{id}` success responses must not expose `provider_route`, `executed_provider_route`, or `fallback_execution`.
- On terminal failure, `Optimization.error` must include a compact internal `fallback_execution` copy or reference-equivalent payload so failed rows are diagnosable even though public RFC 7807 responses keep their existing shape.
- Each failed-attempt `error_constraint` value should be bounded to a short string representation. Do not persist exception objects, stack traces, request bodies, authorization headers, billing charge IDs, or API keys inside fallback metadata.

### AC5: Demo route mirrors execution semantics without persistence

- `POST /v1/optimizations/demo` must use the same attempt execution helper for LP.
- Demo non-LP preview still returns 501 before LP Pydantic validation.
- Demo does not persist `_system` metadata.
- Demo success `model_version`, citation/IP attribution, and reproducibility lock must use the final successful attempt.
- Demo `solve_seconds` must report total solver seconds consumed across attempts.
- Demo must also call the solver with an attempt-local body whose `solver` field is the attempt's `selected_solver`.
- Demo terminal failures must preserve current public RFC 7807 error semantics.

### AC6: Tests cover success, boundaries, and regressions

Add focused tests, preferably in `apps/solver-orchestrator/tests/test_fallback_execution.py`:

1. Pure helper builds primary + repeated fallback attempts in request order.
2. Pure retry predicate returns true for `timeout`/`error` and false for `optimal`/`infeasible`/`unbounded`.
3. Pure helper builds a one-attempt plan for `fallback_chain=None` and `fallback_chain=[]`.
4. Demo LP timeout on primary followed by fallback success returns 200 and final model_version/locked_solver from final attempt.
5. Demo LP infeasible primary does not execute fallback and returns 422.
6. Demo LP repeated timeout exhausts attempts and returns 504 with terminal timeout semantics.
7. Authenticated fallback success persists `_system.fallback_execution`, `_system.executed_provider_route`, and keeps public response free of internal metadata.
8. Authenticated fallback success sends attempt-local solver values to `solve_from_request`, preserving the original idempotency hash and persisted request body.
9. Authenticated fallback success records exactly one cost attribution row with total solver seconds and final-attempt metadata.
10. Authenticated fallback terminal failure with billing header finalizes billing once with `status="failure"` and total solver seconds after attempts are exhausted.
11. Authenticated fallback terminal failure stores bounded fallback diagnostics without sensitive values.
12. Existing provider-routing and fallback-chain tests still pass.

### AC7: Quality gates pass

Run before commit:

- `uv run pytest apps/solver-orchestrator/tests/test_fallback_execution.py -q`
- `uv run pytest apps/solver-orchestrator/tests/test_fallback_chain.py apps/solver-orchestrator/tests/test_provider_routing.py -q`
- `uv run pytest apps/solver-orchestrator/tests -q`
- `uv run mypy apps packages`
- `uv tool run pre-commit run --all-files --show-diff-on-failure`
- `git diff --check`

## Tasks / Subtasks

- [x] Task 1: Add fallback execution helper (AC: 1, 2)
  - [x] Create `fallback_execution.py` with typed attempt plan/result metadata helpers.
  - [x] Reuse `select_provider_route()` for fallback candidates.
  - [x] Add pure retryability predicate.
  - [x] Preserve repeated fallback solvers as repeated attempts.
  - [x] Carry requested-vs-selected solver separately in each planned attempt.
  - [x] Cover `None`/empty chain as primary-only attempt plans.

- [x] Task 2: Integrate authenticated route (AC: 3, 4)
  - [x] Replace the single `solvers.solve_from_request()` call with ordered attempt execution.
  - [x] Use per-attempt body copies with the attempt selected solver.
  - [x] Persist primary `provider_route`, final `executed_provider_route`, and `fallback_execution` under `_system`.
  - [x] Move reproducibility payload creation until final successful attempt is known.
  - [x] Keep billing finalize and cost attribution single-terminal-result only.
  - [x] Preserve existing RFC 7807 error response shapes.
  - [x] Bound internal failure diagnostics and avoid sensitive data.

- [x] Task 3: Integrate demo route (AC: 5)
  - [x] Use the same ordered attempt execution in demo LP path.
  - [x] Use per-attempt body copies with the attempt selected solver.
  - [x] Preserve demo non-LP 501 short-circuit.
  - [x] Use final attempt algorithm for citation/IP attribution.
  - [x] Use final attempt route for reproducibility lock.

- [x] Task 4: Add tests (AC: 6)
  - [x] Add pure helper tests.
  - [x] Add demo success/no-fallback/exhaustion tests via monkeypatched solver outcomes.
  - [x] Add authenticated persistence/cost/billing regressions.
  - [x] Add a regression that captures solver values passed to the monkeypatched solver.
  - [x] Run existing 2.5/2.6 regression tests.

- [x] Task 5: Run quality gates and update records (AC: 7)
  - [x] Run all local validation commands.
  - [x] Record command outcomes in Dev Agent Record.
  - [x] Update sprint status only after code review passes.

## Dev Notes

### Current Implementation Facts

- `routes.py` authenticates, optionally reserves billing, checks idempotency, selects the primary route, validates `fallback_chain`, persists `Optimization`, calls `solvers.solve_from_request()` once, then finalizes billing and records cost attribution.
- `provider_routing.py` returns copied route data and exposes `provider_route_to_system_metadata()`.
- `solvers.solve_from_request()` only implements LP/HiGHS today and returns `LPSolveResult(status=...)`.
- Current authenticated non-LP requests persist a failed optimization row and return 501 before calling the solver; preserve that behavior unless a later execution story changes it.
- Demo route accepts raw JSON so non-LP preview payloads can return 501 before strict LP validation.
- `_build_response_content()` only exposes reproducibility metadata from `_system`; keep that boundary.
- Cost attribution reads `Optimization.model_version["provider_id"]`; set `opt.model_version` before calling `_record_solver_cost_attribution()`.
- Voucher issuance reads reproducibility metadata from the persisted optimization payload; build/attach it only after the final successful route is known.

### Implementation Guidance

- Keep the helper synchronous and small; do not add async abstractions unless route code requires it.
- A dataclass such as `FallbackAttempt(route, requested_solver, role, attempt)` is sufficient.
- Route integration can keep billing/idempotency validation before the attempt loop.
- Store attempt metadata after execution, not before, so each record includes result status and elapsed time.
- Use `dataclasses.replace()` or a tiny local aggregate result object when the terminal result needs total `solve_seconds`; do not mutate frozen `LPSolveResult`.
- Build attempt-local bodies with `dict(body_dict)` and `attempt_body["solver"] = attempt.route.selected_solver`; never use those bodies for idempotency hashing or persisted `input_payload`.
- The final route metadata can reuse `provider_route_to_system_metadata(final_route, task_type=payload.task_type, requested_solver=attempt.requested_solver)`.
- For testability, route code may accept a tiny local loop over attempt plans instead of hiding solver calls inside a helper.
- Preserve the existing Pydantic and RFC 7807 error wording where possible to avoid broad test churn.
- Do not expose internal attempt metadata publicly in this story; Story 8.C.2 can decide routing-history UI later.
- Keep failure diagnostics operationally useful but small: status, field path, constraint string, elapsed seconds, and route metadata are enough.

### Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Reproducibility locks primary route after fallback success | AC3 requires building reproducibility from final successful attempt. |
| Cost attribution records multiple rows or undercounts retries | AC3 and AC6 require exactly one terminal aggregate cost attribution row with total solver seconds. |
| Infeasible/unbounded fall back incorrectly and hide model errors | AC2 classifies mathematical outcomes as terminal, non-retryable. |
| Public API leaks internal route history | AC4/AC5 require internal metadata to stay under `_system` and tests assert non-leakage. |
| Story drifts into external provider/circuit breaker work | Out-of-scope and AC1 require static catalog + existing solver engine only. |
| Billing finalizes per retry | AC3 requires reserve once and finalize once after terminal result. |
| Duplicate fallback solvers are unexpectedly deduped | AC1 preserves repeated retries to honor Story 2.5 self-include behavior. |
| Attempt execution ignores selected fallback solver because it reuses the original request body | AC3/AC5 require an attempt-local body whose `solver` is replaced with `selected_solver`, while idempotency and persistence keep the original body. |
| Fallback metadata becomes a sensitive-data dumping ground | AC4 bounds failure diagnostics and forbids request bodies, credentials, billing IDs, and stack traces. |

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- `uv run pytest apps/solver-orchestrator/tests/test_fallback_execution.py -q` -> RED before route integration (`4 failed, 4 passed`), confirming single-solve route behavior.
- `uv run pytest apps/solver-orchestrator/tests/test_fallback_execution.py -q` -> PASS after fallback helper and route integration (`8 passed`).
- `uv run pytest apps/solver-orchestrator/tests/test_fallback_chain.py apps/solver-orchestrator/tests/test_provider_routing.py -q` -> PASS (`19 passed`).
- `uv run pytest apps/solver-orchestrator/tests -q` -> PASS after implementation and code-review fix (`146 passed`, 11 FastAPI deprecation warnings).
- `uv run mypy apps packages` -> PASS (`Success: no issues found in 87 source files`).
- `uv tool run pre-commit run --all-files --show-diff-on-failure` -> PASS after ruff-format normalization.
- `git diff --check` -> PASS.
- Post-implementation code review found terminal failure branches overwrote existing `billing_finalize_failed` reconciliation flags; fixed by merging `Optimization.error` and adding a regression test.
- Stabilized existing `test_solver_auth_updates_last_used_at` by selecting the seeded API key by `key_prefix + key_hash`, avoiding stale local DB prefix collisions.

### Completion Notes List

- Added `fallback_execution.py` with typed attempt planning, requested-vs-selected solver tracking, retryability predicate, bounded attempt metadata, and aggregate fallback execution metadata.
- Authenticated LP execution now retries `timeout`/`error` outcomes through the validated fallback chain, preserves infeasible/unbounded as terminal model outcomes, and records final executed route truth.
- Reproducibility locks, vouchers, public success model_version, cost attribution, and billing finalize elapsed seconds now use the final executed attempt and aggregate solve seconds.
- Demo LP route mirrors fallback semantics while preserving the non-LP 501 preview path and stateless behavior.
- Internal route/fallback metadata is persisted under `_system` and failure rows, while public responses remain free of provider/fallback internals.
- Code review fix preserved billing finalize failure flags on terminal solver failures while still adding fallback diagnostics.

### File List

- `_bmad-output/stories/2-7-fallback-execution.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/fallback_execution.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/test_fallback_execution.py`
- `apps/solver-orchestrator/tests/test_billing_integration.py`

### Change Log

- 2026-05-27 - Initial Story 2.7 draft created from Epics/PRD/Architecture plus Stories 2.5 and 2.6.
- 2026-05-27 - Story Review Round 1 data-consistency patch: clarified LP-only execution boundary and changed billing/cost/public solve seconds to aggregate all executed attempts.
- 2026-05-27 - Story Review Round 2 function-consistency patch: separated requested vs selected solver per attempt, required attempt-local solver bodies, preserved original idempotency/persistence hashes, and specified failed-row fallback diagnostics.
- 2026-05-27 - Story Review Round 3 boundary/closure patch: marked ready-for-dev, closed None/empty-chain behavior, required terminal solve_seconds, and bounded internal diagnostics.
- 2026-05-27 - Implemented fallback attempt helper, authenticated/demo route execution loops, final-route reproducibility/cost/billing handling, and focused regression tests.
- 2026-05-27 - Completed post-implementation code review; fixed billing-finalize failure flag preservation on terminal solver failure and marked story done.

## Senior Developer Review (AI) - 2026-05-27

### Review Scope

- Uncommitted branch diff against Story 2.7 spec.
- Layers covered manually in one pass due tool constraints: Blind Hunter, Edge Case Hunter, Acceptance Auditor.

### Findings

- [x] [Patch] Terminal failure branches assigned a fresh `opt.error` after billing finalize, which could discard `billing_finalize_failed`, `billing_charge_id`, and retry context needed by the billing reconciler.

### Fixes Applied

- Added `_merge_optimization_error()` so billing finalize flags and solver/fallback diagnostics coexist.
- Added `test_authenticated_terminal_failure_preserves_billing_finalize_failure_flag`.

### Result

Approved after patch. Local regression and quality gates passed.

## Story Review Round 1 - Data Consistency (2026-05-27)

### Findings

- [x] [Patch] The draft implied all task types would enter fallback execution, but current code only has a real LP/HiGHS execution engine; non-LP authenticated/demo paths must keep their existing 501 behavior.
- [x] [Patch] The draft said billing and cost attribution should use the terminal result elapsed seconds, which would undercount consumed solver seconds when one or more fallback attempts run.
- [x] [Patch] Demo `solve_seconds` needed the same aggregate semantics as authenticated execution to avoid response/persistence drift.

### Result

Patched Why/Out-of-Scope, AC3, AC5, AC6, Dev Notes, risks, and Change Log. Round 1 passed after fixes.

## Story Review Round 2 - Function / Dependency Consistency and Drift (2026-05-27)

### Findings

- [x] [Patch] The draft said every attempt should call the solver with the same request body. That would prevent a fallback attempt from actually carrying the fallback solver value into the existing solver dispatch boundary.
- [x] [Patch] The draft did not distinguish requested solver from selected solver per attempt, which would blur omitted primary solver (`None` -> `highs`) and fallback chain entries in metadata.
- [x] [Patch] Idempotency hashing could drift if attempt-local bodies or `_system` metadata were accidentally used instead of the original request body.
- [x] [Patch] Failed authenticated rows needed internal fallback diagnostics in `Optimization.error`, because success-only `_build_response_content()` will not expose `_system` and failed rows are otherwise hard to inspect.

### Result

Patched AC1, AC3, AC4, AC5, AC6, tasks, Dev Notes, risks, and Change Log. Round 2 passed after fixes.

## Story Review Round 3 - Boundary / Edge Cases / Closure (2026-05-27)

### Findings

- [x] [Patch] The draft did not explicitly close `fallback_chain=None` and `fallback_chain=[]`; both must be primary-only plans to preserve Story 2.5 behavior.
- [x] [Patch] Terminal failure rows needed non-null `Optimization.solve_seconds` so billing/cost/audit do not lose elapsed time on 4xx/5xx outcomes.
- [x] [Patch] Fallback diagnostics needed a sensitive-data boundary to prevent request bodies, credentials, billing IDs, or stack traces from being persisted under `_system` or `opt.error`.
- [x] [Patch] Story status was still `draft`; after three review/fix rounds it should move to `ready-for-dev` before implementation.

### Result

Patched frontmatter status, AC1, AC3, AC4, AC6, tasks, Dev Notes, risks, and Change Log. Round 3 passed after fixes. Story is ready for implementation.
