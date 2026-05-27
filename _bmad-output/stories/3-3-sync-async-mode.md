---
story_key: 3-3-sync-async-mode
epic_num: 3
story_num: 3.3
epic_name: Optimization & Prediction Execution
status: done
priority: High (FR E3 v1 must-have; establishes long-running task contract before cancel/status stories)
sizing: M (~4-6 hours; API contract + deterministic estimate + persistence/status shape + focused tests; no real worker)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-27
sources:
  - _bmad-output/planning/epics.md:68 (FR E3 sync/async v1 must-have)
  - _bmad-output/planning/epics.md:1417-1419 (Story 3.3 AC)
  - _bmad-output/planning/prd.md:1096-1106 (default async, 202 + Location, sync auto-turn)
  - _bmad-output/planning/prd.md:1174-1188 (long-running task status response)
  - _bmad-output/planning/prd.md:1470 (E3 must-have)
  - _bmad-output/planning/prd.md:1597 (async queue P95 < 30s NFR)
  - _bmad-output/planning/architecture.md:105 (sync <=5s / async 202 + Location)
  - _bmad-output/planning/architecture.md:513-514 (future Dramatiq + outbox direction)
  - _bmad-output/planning/architecture.md:1636 (sync/async concern location)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py:658 (current POST /v1/optimizations sync path)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py:276 (current GET success-only response helper)
  - apps/solver-orchestrator/src/solver_orchestrator/models.py:38 (Optimization model status fields)
  - infra/local-init/02-solver-schema.sql:4 (optimizations table queued/in_progress status contract)
  - _bmad-output/stories/3-2-prediction-submission.md (previous story review and validation learnings)
dependencies:
  upstream:
    - 3-1-j1-lp-solve (done) - synchronous LP execution, optimization persistence, idempotency, billing, voucher and GET patterns.
    - 2-6-multi-provider-routing (done) - provider routing must remain before side effects.
    - 2-7-fallback-execution (done) - fallback metadata and final route handling must remain intact for sync execution.
    - 2-8-unaudited-block (done) - unaudited self algorithms must still block before persistence/idempotency/execution.
    - 3-2-prediction-submission (done) - previous story established exact review discipline and compact pending/failed GET shape pattern for predictions.
  downstream:
    - 3-4-max-solve-seconds-cap - can enforce runtime cancellation/best-solution behavior.
    - 3-8-cancel-refund - can add DELETE/cancel and refund policy for async rows.
    - 3-9-status-progress-eta - can deepen progress/eta and SSE/status polling.
    - 3-13-batch-endpoint - can fan out async jobs later.
    - Future worker/outbox story - can attach Dramatiq/Redis/outbox execution to queued rows.
---

# Story 3.3 - Sync vs Async + 5s Auto-Turn (FR E3)

## User Story

作为 API 用户，
我希望通过 `POST /v1/optimizations?mode=sync` 请求同步结果，或通过 `mode=async`/超 5 秒估算自动得到异步任务引用，
以便轻任务仍然 200 返回结果，长任务不会占用 HTTP 连接并能通过 `Location` 查询状态。

## Why This Story

Story 3.1 已经把 LP 同步求解串通，但当前 `POST /v1/optimizations` 没有公开 `mode` 合同，也没有在估算超 5 秒时返回 `202 Accepted + Location`。PRD/Architecture 已经明确 v1 需要同/异步混合：默认异步、`mode=sync` 仅允许 <=5 秒规模，超限自动转 async。

本 story 交付 **API 合同和持久状态最小闭环**：接受 `mode=sync|async` query，基于确定性估算判断是否同步执行；异步路径只创建 queued optimization row 并返回 status stub，不启动真实 worker。真实后台执行、SSE、取消退款、精确 progress/eta 由后续 story 接管。这样可以先稳定客户端/SDK/前端对 202 + Location 的依赖，并避免在没有 worker 基础设施时假装任务会后台完成。

## Out of Scope

- 不引入 Dramatiq、Celery、Redis queue、outbox event、worker 进程、APScheduler 或 FastAPI BackgroundTasks。
- 不执行 queued async 任务，也不自动把 queued 转 completed。
- 不实现 SSE、邮件、站内信、webhook。
- 不实现 `DELETE /v1/optimizations/{id}`、取消、退款或 billing finalize for async queued rows。
- 不支持 async queued rows 的 `X-Billing-Charge-Id`；若请求最终进入 async，必须显式 422 拒绝而不是静默忽略。
- 不改变 `/v1/predictions`；预测 async 可在独立 story 处理。
- 不改 demo endpoint `/v1/optimizations/demo`，demo 继续同步。
- 不改变现有 LP 同步成功、fallback、reproducibility voucher、billing reserve/finalize 行为。

## Acceptance Criteria

### AC1: `mode` query contract is explicit and validated

`POST /v1/optimizations` accepts optional query parameter:

- `mode=sync` - request synchronous execution.
- `mode=async` - request queued async response.
- omitted mode defaults to `sync` for backward compatibility with existing tests and J1 clients, even though PRD long-term default is async.
- Mode normalization is lowercase and strict. Omitted mode and explicit `mode=sync` are equivalent for execution and idempotency.

Invalid values return RFC 7807:

- status `422`
- title `Invalid Execution Mode`
- `errors[0].field_path == "query.mode"`
- no `Optimization` row, no `IdempotencyKey`, no billing reserve/finalize, no solver execution.

Do not add `mode` to `OptimizationRequest` body; it is query-only. Idempotency hashes for this endpoint must use a wrapper containing the normalized query mode and JSON body, not `_system` metadata.

### AC2: deterministic sync eligibility estimate controls auto-turn

Add a small local helper in `routes.py` or a focused module such as `execution_mode.py`.

Required behavior:

- Function may be `estimate_optimization_seconds(payload: OptimizationRequest) -> float`.
- Estimate must be deterministic, dependency-free, and fast.
- For LP, use a fixed formula so tests are stable:
  `0.05 + rows * cols * 0.0002 + nonzero_count * 0.0001`, rounded to 6 decimals.
- Existing small J1 LP examples must estimate `<= 5.0` and continue sync 200.
- A dense 200x200 LP must estimate `> 5.0` and auto-turn to async when `mode=sync`.
- Non-LP task types must estimate `10.0` so they queue for effective async instead of returning the current sync 501; explicit/effective sync for non-LP can still follow existing sync behavior if not auto-turned.
- The estimate must be stored in `_system.execution_mode.estimated_seconds`.

### AC3: async response shape and headers are stable

For `mode=async`, or `mode=sync` with estimate `> 5.0`, return:

- HTTP `202 Accepted`
- `Location: /v1/optimizations/{optimization_id}`
- JSON body:

```json
{
  "optimization_id": "<uuid>",
  "status": "queued",
  "mode": "async",
  "requested_mode": "sync|async",
  "auto_async": true,
  "estimated_seconds": 12.34,
  "progress_pct": 0,
  "eta_seconds": null,
  "message": "Task queued; background execution is not enabled in Story 3.3",
  "model_version": {
    "provider_id": "highs",
    "kind": "open_source",
    "version": "...",
    "provider_url": "https://highs.dev/"
  },
  "created_at": "..."
}
```

Rules:

- `requested_mode` is the raw normalized mode requested by query/default.
- `auto_async` is `true` only when `mode=sync` auto-turns due estimate `> 5.0`; explicit `mode=async` returns `false`.
- `progress_pct` is always `0` in this story.
- `eta_seconds` is `null` in this story; Story 3.9 can make it non-null.
- `message` must make clear that this row is queued only and background execution is not enabled in Story 3.3.
- `model_version` uses the existing `ModelVersionSchema` keys: `provider_id`, `kind`, `version`, and `provider_url`; do not introduce `provider_kind` in new response JSON.
- Response must not expose `_system`, user id, api key id, billing charge id, fallback internals, or idempotency hash.

### AC4: async queued row is persisted without execution side effects

Async path persists an `Optimization` row with:

- `status="queued"`
- `task_type` from request
- `input_payload` containing the original normalized request body plus `_system.provider_route` and `_system.execution_mode`
- `model_version` from the selected provider route
- `solution`, `objective`, `solve_seconds`, `completed_at`, `error` all null
- `idempotency_key` if provided

Execution ordering after auth/scope:

1. Validate `mode` query.
2. Validate request body via existing `OptimizationRequest`.
3. Reject invalid `options.anonymous` before side effects.
4. Resolve provider route and unaudited-self governance before billing/idempotency/persistence/execution.
5. Validate fallback_chain and build the fallback attempt plan with existing helpers before queued persistence; do not queue invalid or unaudited fallback chains.
6. Estimate runtime and decide sync vs async.
7. If effective mode is async and `X-Billing-Charge-Id` is present, return RFC 7807 `422` title `Billing Not Supported For Async Optimizations`; do not reserve billing and do not persist a row.
8. For async path, do **not** call `billing_client.reserve`, `billing_client.finalize`, `solvers.solve_from_request`, fallback execution, cost attribution, or voucher issuance.
9. Persist row, then persist idempotency key if supplied, then return 202.

If async idempotency-key insert races on `(user_id, key)`, return 409 `Idempotency Conflict` rather than surfacing a DB error.
The row and idempotency-key insert must be atomic: after an idempotency insert failure, do not leave an orphan queued optimization row and do not return a `Location` for a rolled-back row.
Async queued rows must store provider route metadata using `attempt_route_metadata(attempt_plan.attempts[0], task_type=payload.task_type)`, not a hand-built metadata shape.

### AC5: idempotency covers sync and async modes without duplicate rows

The idempotency hash must include normalized execution mode decision input so the same JSON body with different query modes is not replayed incorrectly:

- same `Idempotency-Key` + same body + same `mode=async` returns the same `optimization_id` and no duplicate rows.
- same `Idempotency-Key` + same body + same `mode=sync` that auto-turned async returns the same queued `optimization_id`.
- same `Idempotency-Key` + same body + omitted mode and explicit `mode=sync` are treated as the same normalized mode.
- same `Idempotency-Key` + same body but different mode returns 409 `Idempotency Conflict`.
- if an existing idempotency key points to a queued/in_progress/timeout/failed row with the same hash, return the matching status response instead of executing again.
- if an existing idempotency key points to a missing row, return 409 `Idempotency Conflict`.
- expired optimization idempotency behavior is currently pre-existing and not changed in this story; do not broaden scope unless tests already require it.

### AC6: GET `/v1/optimizations/{optimization_id}` supports queued/non-completed rows

Current GET only returns completed success shape. Extend it so owner-visible queued/in_progress/failed/timeout rows return compact task status.

Queued/in_progress response:

```json
{
  "optimization_id": "<uuid>",
  "status": "queued",
  "mode": "async",
  "progress_pct": 0,
  "eta_seconds": null,
  "message": "Task queued; background execution is not enabled in Story 3.3",
  "model_version": {...},
  "created_at": "...",
  "completed_at": null
}
```

Failed/timeout response:

- Keep HTTP `200` for owner-visible persisted task status, matching prediction GET compact status style from Story 3.2.
- Include `optimization_id`, `status`, `error`, `model_version`, `created_at`, `completed_at`.
- Do not require `solution` or `objective`.

Missing/cross-user ids still return RFC 7807 `404 Not Found`.

### AC7: sync path remains backward compatible

For existing small LP requests with omitted `mode` or `mode=sync`:

- still return 200 completed response.
- still call billing reserve/finalize only when `X-Billing-Charge-Id` is present.
- still issue reproducibility voucher for `options.reproducible=true` completed sync runs.
- still record solver cost attribution.
- still preserve provider route/fallback execution metadata.
- existing optimization, routing, fallback, billing, voucher, unaudited-self tests remain green.

### AC8: tests cover mode validation, auto-turn, persistence, idempotency, no-side-effect async, and GET status

Add focused tests, preferably `apps/solver-orchestrator/tests/test_sync_async_mode.py`:

1. omitted mode small LP returns existing 200 completed response.
2. `mode=sync` small LP returns 200 completed response.
3. invalid `mode` returns 422 RFC 7807 and no DB/billing/solver side effects.
4. `mode=async` returns 202 with Location header, queued response shape, persisted queued row, model_version, and execution_mode metadata.
5. `mode=async` does not call billing reserve/finalize, solver execution, cost attribution, or voucher issuance.
6. `mode=async` or sync auto-turn with `X-Billing-Charge-Id` returns 422 and no queued row.
7. `mode=async` with invalid fallback_chain returns the existing fallback RFC 7807 error and no queued row.
8. `mode=sync` large LP estimate auto-turns async with `auto_async=true`.
9. GET queued optimization returns compact async status for owner; cross-user returns 404.
10. Async idempotency replay returns same queued row without duplicate rows.
11. Omitted mode and explicit `mode=sync` use the same idempotency hash.
12. Same key + same body + different mode returns 409.
13. Idempotency row pointing to a missing optimization returns 409.
14. A simulated idempotency insert race returns 409 and does not leave an orphan queued optimization row.
15. Existing sync/fallback/billing/repro tests still pass.

### AC9: Quality gates pass

Run before commit:

- `uv run pytest apps/solver-orchestrator/tests/test_sync_async_mode.py -q`
- `uv run pytest apps/solver-orchestrator/tests/test_billing_integration.py apps/solver-orchestrator/tests/test_fallback_execution.py apps/solver-orchestrator/tests/test_provider_routing.py apps/solver-orchestrator/tests/test_unaudited_self_block.py -q`
- `uv run pytest apps/solver-orchestrator/tests -q`
- `uv run mypy apps packages`
- `uv tool run pre-commit run --all-files --show-diff-on-failure`
- `git diff --check`

## Tasks / Subtasks

- [x] Task 1: Add execution mode schemas/helpers (AC: 1, 2, 3)
  - [x] Add query-mode validation helper and RFC 7807 invalid-mode response.
  - [x] Add deterministic estimate helper for LP and non-LP.
  - [x] Add response-content helper for queued/compact optimization status.

- [x] Task 2: Implement async 202 path in POST `/v1/optimizations` (AC: 3, 4, 7)
  - [x] Accept `mode` as query-only parameter with backward-compatible omitted default.
  - [x] Preserve provider route and unaudited-self ordering before persistence/execution.
  - [x] Validate fallback_chain with existing helpers before queued persistence.
  - [x] Reject async effective mode with `X-Billing-Charge-Id` before persistence.
  - [x] Persist queued optimization rows with `_system.execution_mode`.
  - [x] Return 202 + Location without billing/solver/cost/voucher side effects.
  - [x] Preserve existing sync execution path.

- [x] Task 3: Update idempotency for sync/async mode (AC: 5)
  - [x] Include normalized mode in idempotency hash input.
  - [x] Replay queued/non-completed rows as compact status instead of re-executing.
  - [x] Return 409 for mode mismatch, missing cached row, and insert races.

- [x] Task 4: Extend GET `/v1/optimizations/{id}` compact status (AC: 6)
  - [x] Return completed rows with existing success shape.
  - [x] Return queued/in_progress compact status with progress fields.
  - [x] Return failed/timeout compact status with error payload.
  - [x] Preserve owner-only 404 behavior.

- [x] Task 5: Add focused tests and run gates (AC: 8, 9)
  - [x] Add sync/async mode tests.
  - [x] Add idempotency replay/mismatch/missing-row tests.
  - [x] Add no-side-effect async assertions.
  - [x] Run AC9 commands and record results in Dev Agent Record.

### Review Findings

- [x] [Review][Patch] Add coverage for sync auto-turn async with `X-Billing-Charge-Id` — AC8 requires both explicit async and sync auto-turn effective async billing rejection to be tested. Added `test_sync_auto_turn_rejects_billing_header_without_row`.
- [x] [Review][Patch] Reject billing header before async idempotency replay — AC4 requires effective async requests with `X-Billing-Charge-Id` to return 422 before persistence/billing side effects. Moved billing-header rejection ahead of async idempotency replay and added `test_async_idempotency_replay_with_billing_header_is_rejected`.

## Dev Notes

### Current Implementation Facts

- `routes.py` currently handles `POST /v1/optimizations` as sync-only and persists `status="in_progress"` immediately before solving.
- Existing GET helper `_build_response_content(opt)` assumes completed rows and hard-codes `status="completed"`; it must not be used for queued rows.
- `models.Optimization` and `02-solver-schema.sql` already support `status="queued"` and `idx_optimizations_status WHERE status IN ('queued', 'in_progress')`.
- Existing `IdempotencyKey` is scoped by `(user_id, key)` and references `optimizations`.
- Existing sync idempotency currently only replays completed rows. Story 3.3 must close queued/non-completed replay for optimization mode rows.
- `_attach_system_metadata(...)` already merges `_system` metadata; reuse it for `execution_mode`.
- `attempt_route_metadata(...)` and fallback execution metadata already define provider route storage for optimization sync path.
- `select_provider_route(...)`, `_provider_route_error_response(...)`, `_unaudited_self_algorithm_error(...)`, `build_fallback_attempts(...)`, and `attempt_route_metadata(...)` are existing governance/metadata choke points; do not bypass them or hand-build route metadata.
- Billing reserve/finalize happens only in sync path after provider routing. Async queued rows must avoid billing calls in this story because there is no worker/finalize lifecycle.
- Existing sync billing with `X-Billing-Charge-Id` must remain unchanged for effective sync; effective async must reject the header with 422 to avoid an unfinalized reserve.
- Prediction Story 3.2 established compact GET status style for failed rows; mirror that style for optimization queued/failed/timeout.

### Implementation Guidance

- Prefer helper names such as `_validate_execution_mode`, `_normalized_execution_mode`, `_estimate_optimization_seconds`, `_build_optimization_status_response_content`, and `_build_async_accepted_response`.
- Suggested hash input for idempotency: `{ "mode": normalized_mode, "body": body_dict }`, where omitted mode normalizes to `"sync"`.
- For auto-turn response, persist `_system.execution_mode`:

```json
{
  "requested_mode": "sync",
  "effective_mode": "async",
  "auto_async": true,
  "estimated_seconds": 12.34,
  "threshold_seconds": 5.0
}
```

- For explicit async, use `requested_mode="async"`, `effective_mode="async"`, `auto_async=false`.
- For sync execution, it is useful but not mandatory to store `_system.execution_mode` after estimate. If stored, ensure it does not alter reproducibility fingerprint logic unexpectedly; `_build_reproducibility_payload` must continue using the original request body without `_system`.
- If reusing existing `_hash_body`, pass a separate normalized wrapper instead of mutating `body_dict` with `_system`.
- For async idempotency insertion, prefer `async with session.begin_nested()` or another atomic pattern already accepted by SQLAlchemy async usage in this codebase; if an `IntegrityError` occurs, rollback the failed unit and return 409 without a persisted orphan row.
- Keep `Location` relative (`/v1/optimizations/{id}`) to match PRD examples and tests.
- Do not add `progress_pct` or `eta_seconds` to completed `OptimizationResponse`; compact status responses can include them.
- If `model_version` is missing on a legacy queued row, return `model_version: null` rather than 500.
- Be careful with SQLAlchemy rollback after `IntegrityError`; return RFC 7807 and avoid continuing with a dirty session.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Developer implements fake async completion without worker | Out of Scope and AC4 require queued-only persistence and no solver execution. |
| Existing clients break because PRD says default async | AC1 requires omitted mode remain sync for backward compatibility; explicit async establishes new contract first. |
| Billing reserve is called for async queued rows and never finalized | AC4/AC8 require no billing calls on async path. |
| Async row queues invalid fallback_chain | AC4/AC8 require reusing existing fallback validation and attempt-plan helpers before persistence. |
| Idempotency replays sync result for async request | AC5 requires mode included in hash input and mismatch 409. |
| Idempotency insert race returns Location for a rolled-back row | AC4 requires atomic row/key persistence and no orphan/phantom Location after IntegrityError. |
| GET queued row crashes because success schema requires solution/objective/completed_at | AC6 requires compact non-completed status payload. |
| Provider governance bypassed by queue shortcut | AC4 requires provider route/unaudited-self checks before queued persistence. |
| Users think queued means background execution is live | AC3/AC6 require an explicit Story 3.3 queued-only message until worker execution exists. |
| Story drifts into 3.9 progress/eta/SSE | AC3 fixes progress at 0 and eta null; SSE/progress depth remains downstream. |

## Definition of Done

- Story file has passed three pre-implementation reviews and all resulting patches are applied.
- `POST /v1/optimizations` supports `mode=sync`, `mode=async`, invalid mode handling, and sync auto-turn to 202.
- Async queued response includes `Location`, stable response body, persisted queued row, model_version and execution_mode metadata.
- Async path is side-effect-free for billing, solver execution, cost attribution, and voucher issuance.
- GET owner-visible queued/non-completed optimizations returns compact status without crashing.
- Existing sync behavior and regression tests remain green.
- AC9 quality gates pass or any inability to run them is documented.
- Sprint status and Dev Agent Record are updated.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-27 - Wrote focused Story 3.3 tests first; initial red run showed missing mode validation, async branch, queued GET, async idempotency replay, and race handling.
- 2026-05-27 - Implemented execution mode helpers, async queued persistence, mode-aware idempotency, and compact non-completed optimization status responses.
- 2026-05-27 - Adjusted the missing cached optimization test to simulate ORM cache miss because the database FK uses `ON DELETE CASCADE`, making a real dangling idempotency row unseedable.
- 2026-05-27 - Ran full AC9 validation suite successfully.
- 2026-05-27 - Post-implementation code review found two patch items around effective-async billing coverage/replay ordering; both were fixed and revalidated.

### Completion Notes List

- Added `mode=sync|async` query support with omitted mode normalized to `sync` for backward compatibility.
- Added deterministic runtime estimate and 5s auto-turn to async for large LP requests; non-LP effective async queues instead of reaching the sync 501 path.
- Added queued-only async 202 response with relative `Location`, stable model_version shape, execution_mode metadata, and explicit no-worker message.
- Preserved provider route, unaudited-self, and fallback-chain validation before persistence; async path avoids billing reserve/finalize, solver execution, cost attribution, and voucher issuance.
- Updated optimization idempotency to hash normalized mode plus body, replay queued/non-completed rows, and return 409 for mismatch, missing cached optimization, and insert races without orphan queued rows.
- Extended owner-visible GET `/v1/optimizations/{id}` to return compact status for queued/in_progress/failed/timeout while preserving completed success shape and cross-user 404.
- Completed post-implementation code review and fixed all patch findings: sync auto-turn billing rejection is covered, and effective async rejects billing headers before idempotency replay.

### File List

- `_bmad-output/stories/3-3-sync-async-mode.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/test_sync_async_mode.py`

### Change Log

- 2026-05-27 - Initial Story 3.3 draft created from Epics/PRD/Architecture/current solver-orchestrator implementation.
- 2026-05-27 - Implemented Story 3.3 sync/async execution mode contract, queued status persistence, mode-aware idempotency, compact optimization GET status, and focused regression tests.
- 2026-05-27 - Validation passed: Story 3.3 focused tests, adjacent solver-orchestrator regression tests, full solver-orchestrator tests, mypy, pre-commit, and diff whitespace check.
- 2026-05-27 - Code review patch pass completed; effective-async billing replay ordering and sync auto-turn billing coverage fixed.

## Story Review Round 1 - Data Consistency (2026-05-27)

### Findings

- [x] [Patch] The draft did not explicitly state whether omitted `mode` and `mode=sync` are the same idempotency value. The story now requires lowercase strict normalization and treats omitted mode as explicit `sync`.
- [x] [Patch] Async status response could drift into the PRD's older `provider_kind` spelling. The story now requires existing `ModelVersionSchema` keys: `provider_id`, `kind`, `version`, and `provider_url`.
- [x] [Patch] Idempotency wording could imply hashing mutated `_system` metadata. The story now requires hashing a wrapper of normalized query mode plus original JSON body.

### Result

Round 1 passed after patches. The mode normalization, response model version shape, and idempotency data contract are now explicit.

## Story Review Round 2 - Function / Dependency Consistency and Drift (2026-05-27)

### Findings

- [x] [Patch] The draft let async queued persistence happen after provider route but before fallback-chain validation. The story now requires existing fallback validation and `build_fallback_attempts(...)` before queued persistence, so invalid or unaudited fallback chains cannot be queued.
- [x] [Patch] The draft said async path makes no billing calls but did not say what to do if `X-Billing-Charge-Id` is present. The story now requires a 422 `Billing Not Supported For Async Optimizations` before persistence.
- [x] [Patch] Async provider metadata could drift into a hand-built shape. The story now requires `attempt_route_metadata(attempt_plan.attempts[0], task_type=payload.task_type)` for queued rows.

### Result

Round 2 passed after patches. Function reuse, billing lifecycle boundaries, and provider/fallback metadata reuse are aligned with the existing optimization route.

## Story Review Round 3 - Boundary / Edge Cases / Closure (2026-05-27)

### Findings

- [x] [Patch] The draft did not pin a concrete estimate formula, which could make the auto-turn test unstable. The story now requires a deterministic LP formula and a dense 200x200 case that must exceed 5 seconds.
- [x] [Patch] A queued response could be misread as a real background worker promise. The story now requires a clear `message` stating that background execution is not enabled in Story 3.3.
- [x] [Patch] Idempotency insert race handling did not explicitly forbid orphan queued rows or phantom `Location` headers after rollback. The story now requires atomic row/key persistence and a regression test for no orphan row.

### Result

Round 3 passed after patches. Estimation, queued-only semantics, and idempotency race closure are now explicit enough for implementation.
