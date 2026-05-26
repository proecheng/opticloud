---
story_key: 2-6-multi-provider-routing
epic_num: 2
story_num: 2.6
epic_name: Algorithm Catalog
status: done
priority: High (FR C6 v1 must-have; closes the gap between solver enum and provider transparency)
sizing: M (~4-6 hours; routing helper + route integration + regression tests; no new service)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-27
sources:
  - _bmad-output/planning/epics.md:1351
  - _bmad-output/planning/epics.md:1374
  - _bmad-output/planning/epics.md:1378
  - _bmad-output/planning/epics.md:1382
  - _bmad-output/planning/epics.md:1386
  - _bmad-output/planning/prd.md:1114
  - _bmad-output/planning/prd.md:1451
  - _bmad-output/planning/architecture.md:1321
  - _bmad-output/planning/architecture.md:1621
  - _bmad-output/planning/architecture.md:1642
  - _bmad-output/planning/architecture.md:1646
  - _bmad-output/planning/architecture.md:3228
dependencies:
  upstream:
    - 2-1-j1-algorithms-public-list (done) - static catalog and model_version provider metadata
    - 2-4-solver-enum (done) - supported_solvers plus solver-aware lookup helper
    - 2-5-fallback-chain (done) - validated fallback_chain field, stored only
    - 3-1-j1-lp-solve (done) - sync LP solve path and model_version response
    - m2-3-cost-attribution (done) - solver-second attribution uses Optimization.model_version provider metadata after solve
  downstream:
    - 2-7-fallback-execution - consumes the selected provider route and fallback_chain ordering
    - 3-9-status-progress-eta - surfaces model_version on status responses
    - 7.A.1-capability-registry-v1-schema - later replaces static routing source with service-backed capability lookup
---

# Story 2.6 - Multi-provider Routing (FR C6)

## User Story

As an API user submitting an optimization request,
I want the platform to choose the correct provider implementation from the catalog when I specify a task and optional solver,
so that the response and persisted run truthfully identify the selected self / open-source / external / commercial provider before fallback execution is added.

## Why This Story

Story 2.4 validates `solver`; Story 2.5 validates `fallback_chain`. The current route still treats provider selection as an inline side effect: it receives `algo` from `find_by_task_type_and_solver()` and later copies `algo["model_version"]`. That works for LP, but it leaves no explicit routing contract for Story 2.7 to reuse when it starts trying alternate providers.

This story creates a small, deterministic provider-routing layer inside `solver-orchestrator` using the current M1-M2 static catalog. It must not introduce the M3 `capability-registry` service early.

## Out of Scope

- No fallback execution loop. Story 2.7 will try the fallback chain after timeout/provider failure.
- No new Provider HTTP integrations, commercial provider credentials, or external calls.
- No new database tables, migrations, Redis cache, or capability-registry service.
- No billing price differentiation by provider.
- No UI route, provider dashboard, or "Why this solver?" tooltip. This story is backend contract work.
- No broad RFC 7807/i18n cleanup beyond errors directly touched by this routing code.

## Acceptance Criteria

### AC1: Explicit routing helper exists

- Add a small routing helper in `apps/solver-orchestrator/src/solver_orchestrator/provider_routing.py`.
- The helper must use the existing `CATALOG` / `find_by_task_type_and_solver` data model; do not duplicate the catalog.
- It returns a typed route object with at least:
  - `algorithm`
  - `selected_solver`
  - `model_version`
  - `supported_solvers`
  - `provider_kind`
  - `routing_reason`
- `selected_solver` is:
  - the requested `payload.solver` when supplied and valid,
  - otherwise the first solver on the selected algorithm's `supported_solvers`.
- If the task type is unknown, return a typed "unsupported task type" result.
- If the task type exists but the solver is invalid, return a typed "unsupported solver" result with the supported solver list.
- The public helper signature should be explicit, e.g. `select_provider_route(task_type: str, solver: str | None) -> ProviderRouteResult`, so Story 2.7 can call it with each fallback candidate without depending on FastAPI request objects.

### AC2: Provider kind routing is deterministic

- For a known `task_type`, provider selection follows the existing static catalog order and solver match semantics:
  - no explicit solver: first catalog algorithm for that task type,
  - explicit solver: first catalog algorithm whose `supported_solvers` contains that solver.
- The route must preserve `model_version.kind`, including all allowed categories: `self`, `open_source`, `external`, `commercial`.
- The route must include `provider_url` because the existing `ModelVersionSchema` requires it.
- The implementation must be deterministic and side-effect free so Story 2.7 can call it repeatedly during fallback selection.
- Add a pure metadata helper, e.g. `provider_route_to_system_metadata(route, task_type, requested_solver)`, so route selection and JSON persistence stay separately testable.
- The helper must copy `model_version` into a plain dict when returning/persisting metadata. Do not expose a mutable reference to the global `CATALOG` entry.

### AC3: Authenticated optimization route uses routing helper

- `POST /v1/optimizations` must call the routing helper once after billing/idempotency checks and before fallback_chain validation.
- Call the helper before building reproducibility metadata, but after request body validation. It must not reserve billing, mutate DB, or call a solver.
- Existing error semantics are preserved:
  - unknown task type remains 422 with title `Unsupported Task Type`,
  - invalid solver remains 400 with title `Unsupported Solver`,
  - `errors[0].field_path == "solver"` for invalid solver.
- Fallback-chain validation must reuse the helper's `supported_solvers`.
- `reproducibility.locked_model_version`, `reproducibility.locked_solver`, `Optimization.model_version`, and success response `model_version` must all use the selected route.
- `locked_solver` must use `route.selected_solver`, not `algo["supported_solvers"][0]`, so an explicit valid solver is preserved for reproducibility vouchers and idempotency replay.
- Existing M2.3 cost attribution must continue to record solver-second events with the routed provider id from `Optimization.model_version`; this story must not bypass or remove `_record_solver_cost_attribution()`.
- Existing M2.3 cost attribution must pass `route.selected_solver` to `_record_solver_cost_attribution()` so omitted-solver requests record the resolved solver (`highs` for LP) instead of `"default"`.
- For LP with `solver="highs"` or omitted solver, the user-visible output remains byte-compatible except for any intentional routing metadata only stored under `_system`.

### AC4: Demo optimization route uses routing helper

- `POST /v1/optimizations/demo` must use the same routing helper for the LP path.
- Demo LP success still returns `model_version` from the selected route.
- Demo LP reproducibility still uses selected `model_version` and selected solver.
- Non-LP demo bodies still short-circuit to 501 before Pydantic LP validation; this story must not break Excel VRPTW / schedule / inventory preview behavior.
- Demo route does not need to persist `_system.provider_route`, because it is stateless; it only needs to use the same selected route for response and reproducibility preview.

### AC5: Routing metadata is persisted without changing public response shape

- Persist a namespaced system entry in `Optimization.input_payload["_system"]["provider_route"]` for authenticated requests.
- Required fields:
  - `task_type`
  - `requested_solver`
  - `selected_solver`
  - `provider_id`
  - `provider_kind`
  - `provider_url`
  - `routing_reason`
- This metadata is internal and must not be included in public `OptimizationResponse` unless a future story explicitly exposes it.
- Existing `_attach_reproducibility_metadata()` behavior must be preserved; provider route metadata and reproducibility metadata must coexist under `_system`.
- Prefer replacing `_attach_reproducibility_metadata(body, reproducibility)` with a generic `_attach_system_metadata(body, **metadata)` helper that merges keys under `_system` without mutating the caller's original request dict.

### AC6: Tests cover routing decisions and regressions

Add focused tests, preferably in a new `apps/solver-orchestrator/tests/test_provider_routing.py`:

1. Helper routes `task_type="lp", solver=None` to HiGHS and `selected_solver == "highs"`.
2. Helper routes `task_type="forecast", solver="arima"` to `arima-forecast`, not the first forecast catalog row.
3. Helper routes `task_type="nlp", solver="aqgs"` to provider kind `self`.
4. Helper returns unsupported task type for an unknown task.
5. Helper returns unsupported solver with the union supported list for known task type.
6. Demo LP success uses the routed model_version and reproducibility locked solver.
7. Demo invalid solver still returns 400 `Unsupported Solver`.
8. Demo non-LP preview still returns 501 before LP validation.
9. Authenticated route persists `_system.provider_route` alongside reproducibility metadata.
10. Authenticated route with explicit valid solver preserves `reproducibility.locked_solver == selected_solver`.
11. Mutating the returned route metadata in a test does not mutate `CATALOG`.
12. Authenticated public response does not include internal `provider_route`.
13. Authenticated omitted-solver LP request records M2.3 cost attribution metadata with `solver == "highs"`.

### AC7: No accidental fallback execution

- `fallback_chain` stays validation-only in this story.
- The solver call remains a single execution call for the selected primary solver.
- No retry loop, timeout fallback, circuit breaker, or fallback path logging is added here.
- Add or preserve a code comment at the route integration point stating that fallback execution belongs to Story 2.7.

### AC8: Quality gates pass

Run before commit:

- `uv run pytest apps/solver-orchestrator/tests/test_provider_routing.py -q`
- `uv run pytest apps/solver-orchestrator/tests -q`
- If a fresh worktree cannot import `solver_orchestrator`, use the workspace-scoped form: `uv run --package opticloud-solver-orchestrator pytest apps/solver-orchestrator/tests/test_provider_routing.py -q`.
- `uv run mypy apps packages`
- `uv tool run pre-commit run --all-files --show-diff-on-failure`
- `git diff --check`

## Tasks / Subtasks

- [x] Task 1: Add provider routing helper (AC: 1, 2)
  - [x] Create `provider_routing.py` with typed success/error route results.
  - [x] Reuse `find_by_task_type_and_solver`; do not scan or duplicate `CATALOG` independently unless the existing helper cannot supply the needed data.
  - [x] Convert selected route to internal metadata with a small pure function.
  - [x] Ensure returned `model_version` and metadata are copies, not references into `CATALOG`.

- [x] Task 2: Integrate authenticated route (AC: 3, 5, 7)
  - [x] Replace inline `algo, supported_solvers = find_by_task_type_and_solver(...)` route logic with the helper.
  - [x] Preserve the current 422/400 error response shape.
  - [x] Store provider route metadata under `_system.provider_route`.
  - [x] Keep reproducibility metadata and provider route metadata together under `_system`.
  - [x] Preserve M2.3 cost attribution calls and ensure they use the routed model provider and `route.selected_solver`.
  - [x] Generalize `_attach_reproducibility_metadata()` to a non-mutating `_attach_system_metadata()` helper, or prove the existing helper can merge both keys without overwrite.

- [x] Task 3: Integrate demo route (AC: 4, 7)
  - [x] Use the same helper in LP demo route.
  - [x] Preserve non-LP 501 preview short-circuit.
  - [x] Preserve citation and IP attribution response behavior.

- [x] Task 4: Add tests (AC: 6)
  - [x] Add helper unit coverage for default, explicit solver, self-provider, unknown task, and bad solver paths.
  - [x] Add demo route regressions.
  - [x] Add authenticated persistence test for `_system.provider_route`; reuse the `test_billing_integration.py` API-key and `get_session` override pattern.
  - [x] Add no-leak assertion for public responses and omitted-solver cost attribution coverage.

- [x] Task 5: Run quality gates and update story record (AC: 8)
  - [x] Run all quality gates listed in AC8.
  - [x] Record commands and outcomes in the Dev Agent Record.
  - [x] Move sprint status to `done` only after implementation code review passes.

## Dev Notes

### Current Implementation Facts

- `apps/solver-orchestrator/src/solver_orchestrator/catalog.py` is the current M1-M2 capability source. Architecture says M3+ moves lookup to `capability-registry`; do not create that service in this story.
- `find_by_task_type_and_solver(task_type, solver)` already returns `(algorithm, union_supported_solvers)` and correctly handles shared task types such as `forecast`.
- `OptimizationRequest.solver` and `fallback_chain` already exist from Stories 2.4 and 2.5.
- `routes.py` currently uses `algo["model_version"]` directly in authenticated and demo success paths. This story should make that choice explicit and reusable, not change the LP solver engine.
- `solvers.solve_from_request()` only implements LP/HiGHS today. Other task types can route at metadata level but still return 501 until their execution stories land.
- M2.3 added `CostAttribution` and `_record_solver_cost_attribution()` in `routes.py`; provider routing must preserve those imports/calls and keep `Optimization.model_version` populated before attribution records are written.

### Implementation Guidance

- Prefer a small dataclass/TypedDict based helper over adding a class hierarchy.
- Keep route error rendering in `routes.py` so existing RFC 7807 helper is reused.
- Keep provider route metadata internal; `_build_response_content()` currently exposes only reproducibility from `_system`, and that should remain true.
- If you need to adjust `_attach_reproducibility_metadata()`, generalize it to merge a `_system` dict rather than adding a one-off second mutator.
- Do not make selected solver depend on `fallback_chain`; fallback routing belongs to 2.7.
- Do not mutate the global `CATALOG`.
- The route object may contain the selected algorithm for internal code convenience, but any JSON-facing value (`model_version`, provider metadata) must be copied before being returned or stored.
- Authenticated route tests should seed `users` + `api_keys` the same way existing billing/repro tests do. Do not mock `verify_api_key`; the integration path is valuable because provider metadata is persisted only after real request handling.
- Demo success tests should prove citation/IP attribution are still sourced from the selected route algorithm after inline `algo` usage is removed.
- Authenticated tests should cover an omitted-solver LP request and assert cost attribution metadata records `solver == "highs"`.

### Project Structure Notes

- New backend helper: `apps/solver-orchestrator/src/solver_orchestrator/provider_routing.py`
- Route integration: `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- Tests: `apps/solver-orchestrator/tests/test_provider_routing.py`
- No expected frontend, auth-service, billing-service, SQL migration, or package dependency changes.

### Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Developer accidentally implements 2.7 fallback execution | AC7 explicitly forbids retry loops and fallback path logging. |
| Routing helper duplicates catalog semantics and diverges from 2.4 | AC1 requires reusing `find_by_task_type_and_solver`. |
| Reproducibility locks the first catalog solver instead of requested solver | AC3 requires `locked_solver` to use `selected_solver`. |
| Provider route metadata overwrites reproducibility metadata | AC5 requires both to coexist under `_system`. |
| Demo non-LP Excel preview breaks because LP validation moves earlier | AC4 and AC6 require non-LP 501 short-circuit before Pydantic validation. |
| Public response shape leaks internal routing metadata | AC5 keeps provider route out of public response. |
| Explicit solver is accepted but reproducibility records the default solver | AC3 and AC6 require `locked_solver == route.selected_solver`. |
| Helper leaks mutable catalog references | AC2 and AC6 require copied model_version/metadata and a mutation regression. |
| M2.3 cost attribution loses routed provider context | AC3 and Task 2 require preserving cost attribution calls after `Optimization.model_version` is set from the selected route. |

### References

- [Source: _bmad-output/planning/epics.md:1351] Epic 2 goal.
- [Source: _bmad-output/planning/epics.md:1382] Story 2.6 AC.
- [Source: _bmad-output/planning/prd.md:1114] Solver selection payload shape.
- [Source: _bmad-output/planning/prd.md:1458] FR C6 v1 requirement.
- [Source: _bmad-output/planning/architecture.md:1324] solver-orchestrator owns provider routing; M1-M2 static config, M3+ capability-registry.
- [Source: _bmad-output/planning/architecture.md:1646] capability registry boundary.
- [Source: _bmad-output/planning/architecture.md:3230] capability lookup evolution matrix.
- [Source: apps/solver-orchestrator/src/solver_orchestrator/catalog.py] Existing static catalog and solver-aware helper.
- [Source: apps/solver-orchestrator/src/solver_orchestrator/routes.py] Existing route integration points.
- [Source: _bmad-output/stories/2-5-fallback-chain.md] Immediate predecessor and fallback boundary.
- [Source: _bmad-output/stories/m2-3-cost-attribution.md] Cost attribution hook that must remain intact after route integration.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- `uv run pytest apps/solver-orchestrator/tests/test_provider_routing.py -q` -> RED after adding omitted-solver cost attribution regression (`row["solver"] == "default"` instead of `"highs"`).
- `uv run pytest apps/solver-orchestrator/tests/test_provider_routing.py -q` -> PASS (`11 passed`) after routing cost attribution through `route.selected_solver`.
- `uv run pytest apps/solver-orchestrator/tests -q` -> PASS (`137 passed`, 10 deprecation warnings for FastAPI `HTTP_422_UNPROCESSABLE_ENTITY`).
- Post-implementation code review found mutable `route.algorithm` catalog reference exposure; fixed with deep-copied algorithm route results and stricter metadata validation.
- `uv run pytest apps/solver-orchestrator/tests/test_provider_routing.py -q` -> PASS (`11 passed`) after code-review fix.
- `uv run mypy apps packages` -> PASS after removing redundant cast.
- `uv run pytest apps/solver-orchestrator/tests -q` -> PASS (`137 passed`, 10 deprecation warnings) after code-review fix.

### Completion Notes List

- Added explicit provider routing helper with typed OK / unsupported task / unsupported solver outcomes.
- Integrated authenticated and demo optimization routes with selected route model version, selected solver reproducibility locks, and copied internal provider route metadata.
- Preserved Story 2.7 boundary: fallback chain remains validation-only; no retry loop or circuit breaker was added.
- Preserved M2.3 cost attribution and fixed omitted-solver attribution to record the selected solver (`highs`) instead of `"default"`.
- Added regression coverage for helper routing, demo routing, authenticated persistence, public metadata non-leakage, mutable catalog protection, and omitted-solver cost attribution.
- Post-implementation code review tightened the no-mutable-catalog-reference boundary by deep-copying the selected algorithm before returning it from the route helper.

### File List

- `_bmad-output/stories/2-6-multi-provider-routing.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/provider_routing.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/conftest.py`
- `apps/solver-orchestrator/tests/test_provider_routing.py`

### Change Log

- 2026-05-27 - Story created/refreshed against latest main and marked ready-for-dev.
- 2026-05-27 - Implemented provider routing helper, authenticated/demo route integration, selected-solver cost attribution fix, and focused regression tests; moved story to code review.
- 2026-05-27 - Completed post-implementation code review; fixed mutable catalog route exposure and marked story done.

## Story Review Round 1

### Findings

- [x] [Patch] The story did not make the `_system` merge contract concrete enough; implementation could overwrite reproducibility metadata while adding provider route metadata.
- [x] [Patch] The story said `locked_solver` must use the route, but did not explicitly guard against the existing `algo["supported_solvers"][0]` pattern.
- [x] [Patch] Authenticated persistence test setup was under-specified and could lead to mocking away the API-key path.

### Result

Patched AC2, AC3, AC5, AC6, tasks, and Dev Notes. Round 1 passed after fixes.

## Story Review Refresh Round 1 - Data Consistency (2026-05-27)

### Findings

- [x] [Patch] The old draft predated latest `main` and did not list M2.3 cost attribution as an upstream constraint.
- [x] [Patch] AC3 and Task 2 did not state that provider routing must preserve `_record_solver_cost_attribution()` and its model-provider metadata.
- [x] [Patch] The change log still carried the old 2026-05-24 creation date even though the story is now refreshed after M4.5b merged.

### Result

Patched metadata, dependencies, AC3, Task 2, Dev Notes, risks, references, and change log. Refresh Round 1 passed after fixes.

## Story Review Round 2

### Findings

- [x] [Patch] The provider-routing helper API needed a concrete request-independent signature for Story 2.7 reuse.
- [x] [Patch] The story did not guard against returning mutable references into the global catalog.
- [x] [Patch] Demo route persistence expectations needed clarification; demo is stateless and should only reuse selection, not store `_system.provider_route`.

### Result

Patched AC1, AC2, AC3, AC4, AC6, tasks, Dev Notes, and risks. Round 2 passed after fixes.

## Story Review Refresh Round 2 - Function Consistency / Drift (2026-05-27)

### Findings

- [x] [Patch] The story preserved M2.3 attribution calls but did not require passing the resolved selected solver; omitted-solver LP requests could otherwise be recorded as `"default"`.
- [x] [Patch] The demo route integration can drift by removing inline `algo` for model version while still reading citation/IP attribution from the old variable.
- [x] [Patch] Test guidance did not require omitted-solver attribution coverage, leaving a gap between routing truth and persisted cost telemetry.

### Result

Patched AC3, Task 2, and Dev Notes with selected-solver attribution and demo selected-algorithm requirements. Refresh Round 2 passed after fixes.

## Story Review Round 3

### Findings

- [x] [Patch] Dev-readiness check found fresh worktrees may fail direct solver test collection with `ModuleNotFoundError` unless the uv workspace package context is selected.

### Result

Patched AC8 with the workspace-scoped pytest fallback. Round 3 passed after fixes. Story is ready for implementation.

## Story Review Refresh Round 3 - Boundary / Closure (2026-05-27)

### Findings

- [x] [Patch] Story status needed to reflect resumed implementation state after the old draft was restored onto latest `main`.
- [x] [Patch] AC6 did not explicitly close the internal metadata boundary: public responses must not expose `_system.provider_route`.
- [x] [Patch] AC6 did not explicitly close the omitted-solver cost attribution boundary introduced by Refresh Round 2.

### Result

Patched status, AC6, and Task 4. Refresh Round 3 passed after fixes. Story is ready for implementation continuation.
