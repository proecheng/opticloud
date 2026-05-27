---
story_key: 2-8-unaudited-block
epic_num: 2
story_num: 2.8
epic_name: Algorithm Catalog
status: done
priority: High (FR C8 v1 must-have; prevents unaudited self-developed algorithms from being published or routed)
sizing: M (~4-6 hours; catalog metadata + route guard + focused backend regressions; no new service)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-27
sources:
  - _bmad-output/planning/epics.md:62
  - _bmad-output/planning/epics.md:360
  - _bmad-output/planning/epics.md:1390
  - _bmad-output/planning/prd.md:236
  - _bmad-output/planning/prd.md:246
  - _bmad-output/planning/prd.md:1460
  - _bmad-output/planning/prd.md:1765
  - _bmad-output/planning/architecture.md:119
  - _bmad-output/planning/architecture.md:1321
  - _bmad-output/planning/architecture.md:1621
  - _bmad-output/planning/architecture.md:1646
  - _bmad-output/planning/architecture.md:3228
  - 网站方案.md:222
  - 网站方案.md:232
  - 网站方案.md:1531
dependencies:
  upstream:
    - 2-1-j1-algorithms-public-list (done) - public `/v1/algorithms` publish surface currently reads the static catalog.
    - 2-2-algorithm-details (done) - public `/v1/algorithms/{k_algo}` detail surface currently exposes self-developed rows.
    - 2-4-solver-enum (done) - solver-aware catalog lookup and public `supported_solvers`.
    - 2-6-multi-provider-routing (done) - `select_provider_route()` is the routing choke point.
    - 2-7-fallback-execution (done) - fallback attempts reuse provider routing and must inherit the unaudited block.
    - 6-a-1 / 6-a-5 (done) - citation and IP attribution currently include AQGS metadata and must not bypass publish gating.
  downstream:
    - 3-2/3-3+ execution stories - can enable audited self algorithms only after audit metadata is all green.
    - 7-a-1-capability-registry-v1-schema - later moves this static metadata into the service-backed registry.
    - 8-c-2-provider-routing-history - may surface blocked/self-audit events later.
---

# Story 2.8 - Unaudited Self Algorithm Block (FR C8)

## User Story

As a platform operator and API user,
I want self-developed algorithms to be hidden from the public catalog and rejected by routing until every §4.5 self-audit hard rule is green,
so that v1 never publishes or executes a self algorithm whose packaging, license, example, schema, or reproduction evidence is incomplete.

## Why This Story

The catalog currently contains `aqgs-acopf` with `model_version.kind == "self"` and `status == "v1"`. That means public catalog endpoints publish it and `select_provider_route("nlp", "aqgs")` can select it even though §4.5 / Appendix E.4 still show AQGS-ACOPF as unchecked. FR C8 requires the system to prevent unaudited self-developed algorithms until all five hard rules are green.

In this repo, the current M1-M2 capability registry is the static solver-orchestrator catalog. Architecture says the standalone `capability-registry` service starts M3+. Therefore this story must implement the v1 guard in the static catalog/publish/routing layer and must not create the future service early.

## Out of Scope

- No new `capability-registry` service, Redis cache, admin console, provider marketplace, shadow validation, or rollout state machine.
- No new self-developed solver engine and no attempt to execute AQGS/Trust-Tech/CPSOTJUTT/TT-KMeans.
- No database migration unless needed for a minimal local audit-ticket record; prefer deterministic ticket metadata in the block response for this story.
- No frontend redesign. If public catalog counts change, adjust only brittle text/type assumptions needed to keep existing pages/tests accurate.
- No legal approval workflow or document signing. This story records and enforces audit status only.
- No change to open-source HiGHS/OR-Tools/ARIMA/Chronos/LSTM publication or execution behavior.

## Acceptance Criteria

### AC1: Static self-audit metadata exists and is explicit

- Add a small typed metadata model to `apps/solver-orchestrator/src/solver_orchestrator/catalog.py` for §4.5 self-audit state.
- Add the metadata as an optional/internal field on `Algorithm` (for example `NotRequired[SelfAuditStatus]`) so non-self rows do not need placeholder audit data.
- Required five rule keys, matching §4.5 / Appendix E.4:
  - `package_or_runnable`
  - `license_approved`
  - `minimal_example_30m`
  - `readme_schema`
  - `paper_reproduction_result`
- Each rule value must be boolean.
- The helper must expose pure functions such as:
  - `is_self_algorithm(algo) -> bool`
  - `self_audit_missing_rules(algo) -> list[str]`
  - `self_audit_passed(algo) -> bool`
  - `publishable_catalog_items(items=CATALOG) -> list[Algorithm]`
- Non-self algorithms are publishable by default and must not require audit metadata.
- Self algorithms without metadata, malformed metadata, or any false rule must be treated as not publishable / not routable.
- Current `aqgs-acopf` must be marked unaudited in metadata because §4.5 source documents show AQGS-ACOPF unchecked. Do not mark it `audited` or all-green in this story.
- Keep the public `AlgorithmSchema` shape stable; self-audit metadata is internal and must not be returned by `/v1/algorithms`.

### AC2: Public catalog publish surface excludes unaudited self algorithms

- `GET /v1/algorithms` must return only `publishable_catalog_items()`.
- `task_type` and `tier` filters must apply after or together with publishability filtering so `?task_type=nlp`, `?tier=T5`, or `?tier=T1,T5` cannot leak unaudited `aqgs-acopf`.
- `GET /v1/algorithms/aqgs-acopf` must return 404 while AQGS remains unaudited.
- The 404 detail should not claim the algorithm does not exist; use a blocked/unpublished wording such as `k_algo is not published`.
- Citation/IP attribution paths must not re-publish unaudited rows through the public catalog. Internal tests may still inspect raw `CATALOG` for citation correctness.
- Existing open-source details continue to return 200 with citation and IP attribution.

### AC3: Provider routing blocks unaudited self algorithms

- Extend `ProviderRouteStatus` with `UNAUDITED_SELF_ALGORITHM`.
- `select_provider_route(task_type, solver)` must reject a selected algorithm when:
  - `model_version.kind == "self"` and
  - `self_audit_passed(algorithm) is False`.
- The route result must carry enough typed data to render an RFC 7807 response:
  - `blocked_k_algo`
  - `blocked_provider_id`
  - `audit_ticket_id`
  - `missing_self_audit_rules`
  - `supported_solvers`
- The guard must run for both default and explicit solver selection. If a task type has multiple algorithms and one self row is unaudited, explicit solver for that self row must block; a valid open-source solver for the same task type must still route.
- Unsupported task type and unsupported solver semantics from Story 2.6 must remain unchanged.
- Returned route and block metadata must be copied values, not mutable references into `CATALOG`.

### AC4: Authenticated optimization route rejects before billing, DB persistence, fallback, and solving

- `POST /v1/optimizations` must render `UNAUDITED_SELF_ALGORITHM` as an RFC 7807 error before:
  - billing reserve/finalize,
  - idempotency row creation,
  - `Optimization` row persistence,
  - fallback plan creation,
  - `solvers.solve_from_request()`,
  - cost attribution.
- Status code: `403 Forbidden`.
- Title: `Unaudited Self Algorithm`.
- Error detail must include `k_algo`, provider id, and audit ticket id.
- `errors[0].field_path` should be `"solver"` when the request explicitly names the blocked solver and `"task_type"` when the default route chooses a blocked self algorithm.
- `errors[0].constraint` must include the missing rule keys in a stable comma-separated order.
- `next_action_url` must point to an operator-facing audit path, e.g. `https://console.opticloud.cn/admin/self-audit/{audit_ticket_id}`.
- No request body, API key, billing charge id, stack trace, or user id may be included in the public response.

### AC5: Demo route and fallback planning inherit the same block

- `POST /v1/optimizations/demo` must render the same 403 block if a demo path ever routes to an unaudited self algorithm.
- Current demo non-LP preview still returns 501 before LP validation, so existing `task_type="nlp"` demo payloads may keep returning 501 until non-LP demo routing exists.
- The fallback attempt planner must distinguish:
  - unsupported fallback solver -> existing `INVALID_FALLBACK_SOLVER` / `Unsupported Fallback Solver`,
  - unaudited self fallback solver -> new typed status such as `UNAUDITED_SELF_ALGORITHM` and the same block metadata.
- For the current LP-only catalog, open-source LP fallback behavior remains unchanged.
- No public response exposes internal provider/fallback metadata.

### AC6: Admin ticket identity is deterministic and non-sensitive

- Introduce a small pure helper, e.g. `self_audit_ticket_id(k_algo, provider_id) -> str`.
- Ticket id format must be stable and safe to expose, e.g. `self-audit-{k_algo}-{provider_id}` with lowercase ASCII slug components.
- The ticket id is not a database primary key and must not include user id, request id, API key, billing id, or raw request payload.
- The same unaudited algorithm must produce the same ticket id across routing metadata and any RFC 7807 block response that exposes the ticket.
- This story does not need an admin endpoint; the ticket id is the handoff contract for a future admin queue.

### AC7: Tests cover publish, routing, execution, and regressions

Add focused tests, preferably in `apps/solver-orchestrator/tests/test_unaudited_self_block.py`:

1. `aqgs-acopf` has self-audit metadata with at least one missing §4.5 rule and `self_audit_passed(...) is False`.
2. `publishable_catalog_items()` excludes unaudited self algorithms and retains open-source algorithms.
3. `GET /v1/algorithms` and `GET /v1/algorithms?task_type=nlp` do not include `aqgs-acopf`.
4. `GET /v1/algorithms/aqgs-acopf` returns 404 unpublished/blocked wording.
5. `select_provider_route("nlp", "aqgs")` returns `UNAUDITED_SELF_ALGORITHM` with missing rule keys and deterministic ticket id.
6. Existing `select_provider_route("lp", None)` and `select_provider_route("forecast", "arima")` still return OK.
7. Authenticated `POST /v1/optimizations` with `task_type="nlp", solver="aqgs"` and an otherwise schema-valid LP-shaped body returns 403 and does not create an `optimizations` row, billing calls, or solver calls.
8. A route-level fallback candidate that would select unaudited self returns the typed block before execution. If the static catalog has no mixed open/self task, use a scoped monkeypatch/local catalog mutation in the test; do not ship fake catalog rows.
9. Public RFC 7807 block response does not contain API keys, billing charge ids, user ids, request bodies, or `_system`.
10. Existing provider routing, fallback execution, algorithm detail, citation, and solver enum tests still pass after catalog publish filtering; public-list count assertions must no longer assume raw `CATALOG` length when unaudited rows are hidden.

### AC8: Quality gates pass

Run before commit:

- `uv run pytest apps/solver-orchestrator/tests/test_unaudited_self_block.py -q`
- `uv run pytest apps/solver-orchestrator/tests/test_algorithm_details.py apps/solver-orchestrator/tests/test_provider_routing.py apps/solver-orchestrator/tests/test_fallback_execution.py apps/solver-orchestrator/tests/test_solver_enum.py -q`
- `uv run pytest apps/solver-orchestrator/tests -q`
- `uv run mypy apps packages`
- `uv tool run pre-commit run --all-files --show-diff-on-failure`
- `git diff --check`

## Tasks / Subtasks

- [x] Task 1: Add self-audit metadata and helpers (AC: 1, 6)
  - [x] Extend catalog typing with internal self-audit metadata.
  - [x] Mark `aqgs-acopf` unaudited using the §4.5 unchecked rule state.
  - [x] Add pure helpers for self/audit/pass/missing/publishable/ticket id.
  - [x] Ensure helpers do not mutate or return mutable catalog internals.

- [x] Task 2: Gate public catalog publication (AC: 2)
  - [x] Use `publishable_catalog_items()` in `list_algorithms`.
  - [x] Make detail route return 404 unpublished/blocked wording for unaudited self rows.
  - [x] Preserve citation/IP attribution for publishable open-source rows.
  - [x] Update brittle tests expecting the old full catalog count.

- [x] Task 3: Gate provider routing and fallback planning (AC: 3, 5)
  - [x] Add `UNAUDITED_SELF_ALGORITHM` to `ProviderRouteStatus`.
  - [x] Carry block metadata in `ProviderRouteResult`.
  - [x] Reject unaudited self routes before returning OK.
  - [x] Update fallback planning to propagate unaudited self separately from unsupported fallback solver.

- [x] Task 4: Integrate route-level RFC 7807 block (AC: 4, 5, 6)
  - [x] Add a small `_unaudited_self_algorithm_error(...)` renderer in `routes.py`.
  - [x] Call it in authenticated route before billing reserve and DB persistence.
  - [x] Call it in demo LP/fallback invalid handling where applicable.
  - [x] Ensure public response contains ticket id and missing rules but no sensitive data.

- [x] Task 5: Add tests and run quality gates (AC: 7, 8)
  - [x] Add `test_unaudited_self_block.py`.
  - [x] Update existing tests that assumed `aqgs-acopf` is publicly visible or that public list length equals raw catalog length.
  - [x] Run all AC8 commands.
  - [x] Record command outcomes in Dev Agent Record.

## Dev Notes

### Current Implementation Facts

- `apps/solver-orchestrator/src/solver_orchestrator/catalog.py` is the current M1-M2 capability registry. It already includes `aqgs-acopf` as `kind="self"` and `status="v1"`.
- Public catalog routes in `routes.py` currently read raw `CATALOG`, so unaudited self rows are published today.
- `AlgorithmSchema` does not include self-audit fields. Keep it that way for this story.
- `provider_routing.py` is the execution choke point used by authenticated route, demo LP route, and fallback planning.
- `fallback_execution.py` calls `select_provider_route()` for each fallback candidate. It currently only knows unsupported fallback solver, so it must be extended to preserve an unaudited-self block.
- `routes.py` currently performs billing reserve before route selection. For this story, unaudited-self blocking must happen before billing to avoid charging or creating reserve attempts for a request that is forbidden by catalog governance.
- `OptimizationRequest` allows `task_type="nlp"` and `solver="aqgs"`, but authenticated non-LP routes currently persist a failed row and return 501. Story 2.8 must reject unaudited self before that 501 persistence path.
- The authenticated test body for `task_type="nlp"` must still satisfy the existing `OptimizationRequest` schema (`st` plus objective), otherwise FastAPI/Pydantic returns 422 before the route-level governance guard can run.
- Demo non-LP intentionally short-circuits to 501 before strict LP validation. Preserve that behavior unless later demo routing is added.

### Implementation Guidance

- Prefer a compact `SelfAuditStatus` / `SelfAuditRuleSet` `TypedDict` in `catalog.py`; avoid a separate package until 7-a-1.
- Use `NotRequired` for the internal self-audit field on `Algorithm`; otherwise mypy will require self-audit data on all existing open-source catalog rows.
- Use exactly the five rule keys listed in AC1. `package_or_runnable` intentionally covers §4.5 item 1 ("有 Python 包 / Docker 镜像 / 可调脚本") and Appendix E.4's first two columns as one FR C8 hard rule.
- Keep missing-rule ordering stable by defining one canonical tuple of rule keys.
- Do not change `model_version.kind` values or public TypeScript `ModelVersion.kind` union.
- Public catalog filtering may make UI text such as "Browse 8 algorithms" stale. Only update if tests or visible hard-coded counts require it; do not redesign pages.
- Existing citation tests can still inspect raw `CATALOG` for AQGS citation because internal metadata remains present. Public API tests must expect AQGS hidden while unaudited.
- In authenticated route, move route selection above billing reserve. Preserve existing anonymous option validation and request body validation.
- If billing/idempotency ordering must change, keep idempotency conflict semantics unchanged for publishable algorithms.
- Use `_rfc7807_error()` and `ErrorDetail`; do not introduce a second error schema.
- Treat missing/malformed audit metadata as fail-closed.

### Risks & Mitigations

| Risk | Mitigation |
|---|---|
| AQGS remains publicly visible through list/detail even if execution is blocked | AC2 requires publish filtering and detail 404. |
| Billing reserve happens before governance rejection | AC4 requires route/audit guard before billing. |
| Self-audit metadata leaks into public API | AC1 keeps AlgorithmSchema stable and AC7 asserts no leak. |
| Open-source algorithms are accidentally hidden by audit gating | AC1 and AC7 require non-self algorithms publish by default. |
| Fallback path bypasses the guard | AC5 requires fallback planning to propagate unaudited-self invalid routes. |
| Future service boundary is overbuilt too early | Out-of-scope and Dev Notes require static catalog only. |
| Block response becomes sensitive-data leak | AC4/AC6/AC7 forbid credentials, user ids, billing ids, request bodies, and `_system`. |
| Existing AQGS citation/IP tests conflict with public hide behavior | Keep raw catalog metadata intact; update only public API expectations. |

### References

- [Source: _bmad-output/planning/epics.md:62] FR C8 v1 requirement.
- [Source: _bmad-output/planning/epics.md:1390] Story 2.8 AC summary.
- [Source: _bmad-output/planning/prd.md:236] Self-developed algorithms require Apache 2.0 and Appendix E.4 self-audit.
- [Source: _bmad-output/planning/prd.md:1460] FR C8 is v1 must-have.
- [Source: 网站方案.md:222] §4.5 self-audit checklist.
- [Source: 网站方案.md:232] §4.5 pass threshold.
- [Source: 网站方案.md:1531] Appendix E.4 table state.
- [Source: _bmad-output/planning/architecture.md:1324] solver-orchestrator owns M1-M2 static capability lookup.
- [Source: _bmad-output/planning/architecture.md:1646] M1-M2 static capability registry boundary and M3 service handoff.
- [Source: apps/solver-orchestrator/src/solver_orchestrator/catalog.py] Current static catalog and `aqgs-acopf` row.
- [Source: apps/solver-orchestrator/src/solver_orchestrator/provider_routing.py] Story 2.6 route choke point.
- [Source: apps/solver-orchestrator/src/solver_orchestrator/fallback_execution.py] Story 2.7 fallback route reuse.
- [Source: apps/solver-orchestrator/src/solver_orchestrator/routes.py] Public catalog, authenticated route, demo route, RFC 7807 renderer.
- [Source: _bmad-output/stories/2-6-multi-provider-routing.md] Provider routing selected-solver and metadata contract.
- [Source: _bmad-output/stories/2-7-fallback-execution.md] Fallback execution boundaries and final-route truth.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- `uv run pytest apps/solver-orchestrator/tests/test_unaudited_self_block.py -q` -> RED (`ImportError: cannot import name 'publishable_catalog_items'`) before implementation.
- `uv run pytest apps/solver-orchestrator/tests/test_unaudited_self_block.py -q` -> PASS (`8 passed`) after catalog audit helpers, route guard, and fallback propagation.
- `uv run pytest apps/solver-orchestrator/tests/test_algorithm_details.py apps/solver-orchestrator/tests/test_provider_routing.py apps/solver-orchestrator/tests/test_fallback_execution.py apps/solver-orchestrator/tests/test_solver_enum.py -q` -> RED on old public AQGS/count/self-route assumptions; patched tests to Story 2.8 behavior.
- `uv run pytest apps/solver-orchestrator/tests/test_unaudited_self_block.py apps/solver-orchestrator/tests/test_algorithm_details.py apps/solver-orchestrator/tests/test_provider_routing.py apps/solver-orchestrator/tests/test_fallback_execution.py apps/solver-orchestrator/tests/test_solver_enum.py -q` -> PASS (`48 passed`, 1 FastAPI deprecation warning).
- `uv run pytest apps/solver-orchestrator/tests -q` -> PASS (`155 passed`, 11 FastAPI deprecation warnings).
- `uv run mypy apps packages` -> RED once (`FallbackAttemptPlan` import missing), then PASS (`Success: no issues found in 87 source files`).
- Post-review `uv run pytest apps/solver-orchestrator/tests/test_unaudited_self_block.py -q` -> PASS (`10 passed`) after fail-closed/test-closure patches.
- Post-review `uv run pytest apps/solver-orchestrator/tests/test_algorithm_details.py apps/solver-orchestrator/tests/test_provider_routing.py apps/solver-orchestrator/tests/test_fallback_execution.py apps/solver-orchestrator/tests/test_solver_enum.py -q` -> PASS (`40 passed`, 1 FastAPI deprecation warning).
- Post-review `uv run pytest apps/solver-orchestrator/tests -q` -> PASS (`157 passed`, 11 FastAPI deprecation warnings).
- Post-review `uv run mypy apps packages` -> PASS (`Success: no issues found in 87 source files`).
- Post-review `pnpm --filter @opticloud/web typecheck` -> PASS.
- Post-review `uv tool run pre-commit run --all-files --show-diff-on-failure` -> PASS.
- Post-review `git diff --check` -> PASS.

### Completion Notes List

- Added internal §4.5 self-audit metadata and fail-closed helpers in the static M1-M2 catalog.
- Marked `aqgs-acopf` unaudited and hid it from public `/v1/algorithms` list/detail while keeping raw catalog citation/IP metadata available internally.
- Extended provider routing and fallback planning with a distinct `UNAUDITED_SELF_ALGORITHM` status and deterministic `self-audit-aqgs-acopf-aqgs` ticket id.
- Authenticated optimization requests for `task_type=nlp, solver=aqgs` now return 403 before billing, idempotency persistence, optimization persistence, fallback planning, solver calls, or cost attribution.
- Added regression coverage for publish filtering, route block metadata, sensitive-data non-leakage, side-effect-free auth rejection, and fallback planner propagation.
- Post-implementation review patched visible public-catalog count drift, malformed self-audit fail-closed behavior, idempotency no-side-effect coverage, and same-task fallback closure.

### File List

- `_bmad-output/stories/2-8-unaudited-block.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/catalog.py`
- `apps/solver-orchestrator/src/solver_orchestrator/provider_routing.py`
- `apps/solver-orchestrator/src/solver_orchestrator/fallback_execution.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/test_unaudited_self_block.py`
- `apps/solver-orchestrator/tests/test_algorithm_details.py`
- `apps/solver-orchestrator/tests/test_provider_routing.py`
- `apps/web/src/app/academic/page.tsx`
- `apps/web/src/i18n/messages/en-US.json`
- `apps/web/src/i18n/messages/zh-CN.json`

### Change Log

- 2026-05-27 - Initial Story 2.8 draft created from Epics/PRD/Architecture/§4.5 and latest 2.6/2.7 implementation.
- 2026-05-27 - Implemented unaudited self-algorithm publish/routing/optimization guard and focused regression tests; moved story to code review.
- 2026-05-27 - Addressed post-implementation code review findings; all backend, type, web, pre-commit, and diff-check gates pass; story marked done.

## Senior Developer Review (AI) - Post-Implementation (2026-05-27)

### Review Findings

- [x] [Review][Patch] Public web copy still hard-coded "8 algorithms" after AQGS became unpublished, creating visible catalog-count drift.
- [x] [Review][Patch] Self-audit helper treated all five true canonical rules plus extra unknown rule keys as passing; malformed metadata should fail closed.
- [x] [Review][Patch] Authenticated 403 regression did not pass `Idempotency-Key`, so it did not prove idempotency rows are untouched before the unaudited-self block.
- [x] [Review][Patch] Fallback planner unaudited-self test used an inconsistent LP primary route with NLP fallback task; replaced with same-task local catalog mutation coverage.

### Result

All review findings were patched. Re-ran focused Story 2.8 tests, related routing/catalog/fallback regressions, full solver suite, mypy, web typecheck, pre-commit, and diff check successfully. Review outcome: approved / done.

## Story Review Round 1 - Data Consistency (2026-05-27)

### Findings

- [x] [Patch] AC1 listed six rule keys even though FR C8 and §4.5 define five hard rules; Appendix E.4 splits package availability/installability into two columns, but the implementation contract should stay aligned to the five-rule threshold.

### Result

Patched AC1 and Dev Notes to use exactly five canonical rule keys, combining package availability and runnable/installable evidence into `package_or_runnable`. Round 1 passed after fixes.

## Story Review Round 2 - Function / Dependency Consistency and Drift (2026-05-27)

### Findings

- [x] [Patch] The draft said fallback planning should return the same invalid outcome for unaudited self candidates and unsupported fallback solvers; implementation needs a distinct typed status so route rendering can return 403 instead of the existing 400 `Unsupported Fallback Solver`.
- [x] [Patch] The draft did not specify that self-audit metadata is optional/internal on `Algorithm`; a total `TypedDict` field would force all non-self catalog rows to carry irrelevant audit placeholders.
- [x] [Patch] AC6 implied list/detail tests would always expose ticket ids, but list filtering hides blocked rows and detail can remain 404; the deterministic ticket contract belongs to route metadata and RFC 7807 block responses.

### Result

Patched AC1, AC5, AC6, AC7, Task 3, and Dev Notes. Round 2 passed after fixes.

## Story Review Round 3 - Boundary / Edge Cases / Closure (2026-05-27)

### Findings

- [x] [Patch] Authenticated route tests for `task_type="nlp"` could miss the governance guard if they omit `st`/objective fields, because FastAPI validates `OptimizationRequest` before route code runs.
- [x] [Patch] Existing public catalog tests include count assumptions (`>= 8`) that will be false once unaudited AQGS is hidden from public list responses.

### Result

Patched AC7, Task 5, and Dev Notes to require a schema-valid non-LP body for the 403 route test and to update public-list count assumptions. Round 3 passed after fixes. Story is ready for implementation.
