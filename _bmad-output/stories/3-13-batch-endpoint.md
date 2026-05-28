# Story 3.13: Batch endpoint `POST /v1/optimizations/batch`

Status: done

owner: Solver Lead / API

## Story

作为物流工程师李工，
我希望一次提交最多 100 个 LP optimization tasks 并拿到一个 `batch_id`，
以便批量任务可以进入现有 async execution/status 体系，客户端只轮询 `batch_status` 就能知道整批进度和逐项结果。

## Acceptance Criteria

1. `POST /v1/optimizations/batch` 是 authenticated backend API，固定异步。
   - 使用现有 `Authorization: Bearer sk-...` API Key 鉴权，并要求 `optimize:write` scope。
   - 不提供 demo batch endpoint，不接入 Console/CSV/Excel/UI。
   - 请求不接受同步执行：`mode` query 缺省或 `async` 时有效；`mode=sync` 或其他值返回 RFC 7807 `422`，且无 DB side effects。
   - 成功创建返回 `202 Accepted`，`Location: /v1/optimizations/batch/{batch_id}`。
   - 响应必须一次返回 `batch_id`、`batch_status="queued"`、`task_count`、`optimization_ids` 和按输入顺序排列的 `items`。

2. Batch request schema 精确定义，且只支持 LP tasks。
   - 新增 Pydantic schema，例如 `OptimizationBatchRequest`，根字段为 `tasks: list[OptimizationRequest]`。
   - `tasks` 长度为 `1..100`；`0` 个或 `101+` 个返回 RFC 7807 `422`，无任何 batch/child row。
   - Story 3.13 只支持 `task_type="lp"`。任一 `tasks[i].task_type != "lp"` 返回 RFC 7807 `422`，`errors[].field_path` 必须定位到 `tasks[i].task_type`。
   - 每个 task 复用现有 `OptimizationRequest` schema，包括 `minimize/maximize`、`st`、`options`、`solver`、`fallback_chain`、`options.anonymous requires reproducible` 等现有规则。
   - 任一 task schema/provider/fallback validation 失败时，整批请求 fail-fast，不能创建部分 rows。

3. 成功创建必须用现有 optimization async row 表达子任务，不同步求解。
   - 每个 task 创建一条 `optimizations` child row，`status="queued"`，`task_type="lp"`，`model_version` 使用现有 provider route public shape。
   - 每个 child row 的 `input_payload._system.execution_mode` 固定为 `requested_mode="async"`、`effective_mode="async"`、`auto_async=false`，并保留 `threshold_seconds=5.0` 等现有 async metadata。
   - 每个 child row 的 `input_payload._system.provider_route` 必须复用现有 `attempt_route_metadata(...)` / provider routing 结果，不手写另一套 provider shape。
   - 每个 child row 增加内部 `input_payload._system.batch = {"batch_id": "<uuid>", "item_index": i, "task_count": n}`，不得暴露 `_system` 到 public response。
   - 创建 batch 与全部 child rows 必须在同一 DB transaction 中完成；任何 persistence/idempotency race 都 rollback 整批。
   - 不调用 `solvers.solve_from_request()`、fallback execution、billing finalize、cost attribution、voucher issuance 或 worker job enqueue。

4. Batch persistence 使用明确的 batch grouping，不污染单任务 idempotency。
   - 新增 `optimization_batches` table/model：`id UUID PK`、`user_id`、`api_key_id`、`created_at`。不要在 batch row 存 counters/status/result，以免与 child rows drift。
   - 新增 `optimization_batch_items` table/model：`batch_id`、`item_index`、`optimization_id`、`created_at`，`PRIMARY KEY(batch_id,item_index)` 且 `optimization_id UNIQUE`。
   - 新增 `optimization_batch_idempotency_keys` table/model：`user_id`、`key`、`batch_id`、`request_body_hash`、`expires_at`、`created_at`，`PRIMARY KEY(user_id,key)`。
   - 更新 `infra/local-init/02-solver-schema.sql`，DDL 必须 idempotent，并为 `optimization_batches(user_id, created_at DESC)`、`optimization_batch_items(batch_id, item_index)`、`optimization_batch_idempotency_keys(expires_at)` 建索引。
   - `batch_id` 使用当前 repo 的 UUID string 风格，不引入 ULID/base32 新依赖。

5. Batch idempotency 以整批请求为单位。
   - `Idempotency-Key` 可选；缺失时不去重，重复 POST 创建新 batch。
   - 同一 user + same `Idempotency-Key` + same canonical body hash 返回原 `batch_id`、原 `optimization_ids` 和当前 batch status，不创建新 rows，不调用 billing/solver。
   - 同一 user + same `Idempotency-Key` + different body hash 返回 RFC 7807 `409 Idempotency Conflict`，无新 rows。
   - Body hash 必须包含任务顺序；同样 tasks 但顺序不同视为不同请求。
   - Batch idempotency 独立于现有 single optimization `idempotency_keys` 和 prediction idempotency tables，避免把一个 batch key 映射到某个 child optimization。

6. Billing/credits 行为边界必须显式且 side-effect-free。
   - Story 3.13 不新增 batch billing charge model，也不接受一个 header 代表 100 个 child charges。
   - `X-Billing-Charge-Id` 出现在 batch POST 时返回 RFC 7807 `422`，`errors[].field_path="header.X-Billing-Charge-Id"`，无 batch/child rows。
   - 无 billing header 时与现有 no-header single optimization 行为一致：不调用 `billing_client.reserve()` / `billing_client.finalize()`。
   - Child task 的 `options.backtest` 可以随原 request payload 保存，但 batch create 阶段不产生折扣扣费、refund 或 reconciler retry context。
   - Future per-item charge IDs 或 server-created batch reservations 必须另起 story，不能塞进 3.13。

7. `GET /v1/optimizations/batch/{batch_id}` 提供 owner-scoped `batch_status` polling。
   - 使用现有 API Key 鉴权和 owner isolation；missing 或 cross-tenant batch 返回 RFC 7807 `404`，不得泄露 task_count、child ids、status、billing metadata 或 progress。
   - Response top-level fields：`batch_id`、`batch_status`、`task_count`、`counts`、`progress_pct`、`eta_seconds`、`optimization_ids`、`items`、`errors`、`created_at`、`completed_at`。
   - `items` 必须按 `item_index ASC` 返回，且每项是 `{"index": i, **existing child GET/status content}`；completed children 复用 `_build_response_content(...)`，非-completed children 复用 `_build_optimization_status_response_content(...)`。
   - `optimization_ids` 顺序必须与 `items[].optimization_id` 和原输入顺序一致。
   - `errors` 是失败 child 的 ordered aggregate，元素含 `index`、`optimization_id`、`status`、`error`；错误必须复用现有 redaction，不能暴露 `_system.billing` 或 raw charge ids。
   - GET 必须只读：不调用 solver、billing、cost attribution、idempotency insert、voucher issuance 或 worker enqueue。现有 completed GET 的 `attach_existing_voucher_id()` lookup 仅在复用 child helper 时允许，不得创建新 voucher。

8. Batch status/count/progress 语义闭环。
   - `counts` 固定包含 `queued`、`in_progress`、`completed`、`failed`、`timeout`、`cancelled` 六个 keys；repo 使用 `completed`，不得新增 `succeeded` alias。
   - `task_count == len(items) == len(optimization_ids) == sum(counts.values())`。
   - `batch_status` derivation:
     - all queued -> `queued`
     - any queued/in_progress and not all queued -> `in_progress`
     - all completed -> `completed`
     - all cancelled -> `cancelled`
     - no active tasks, at least one completed and at least one failed/timeout/cancelled -> `partial_failed`
     - no active tasks, zero completed, at least one failed/timeout/cancelled -> `failed`
   - `progress_pct` is `floor(avg(child.progress_pct))` over all children; it may be `100` only when all children are terminal completed.
   - `eta_seconds` is max non-null child ETA while active; `0` when `batch_status="completed"`; `null` for non-completed terminal batch statuses.
   - `completed_at` is `null` while active; once all children terminal, it is the max child `completed_at` if available.

9. Existing single optimization APIs remain unchanged.
   - `POST /v1/optimizations` sync/async behavior, idempotency hash, billing reserve/finalize, fallback validation, status response and cancellation semantics must not change.
   - `GET /v1/optimizations/{optimization_id}` for a batch child still works exactly like any other child optimization and remains owner-scoped.
   - `DELETE /v1/optimizations/{optimization_id}` may cancel individual child rows using existing Story 3.8 behavior; Story 3.13 does not add batch cancel.
   - `/v1/optimizations/demo`, `/v1/predictions`, CSV/Excel flows, reproduction rerun, billing reconciler and mock-real divergence tests must not be modified for batch scope except for regression expectations if route ordering requires it.

10. Regression coverage proves 100-task async batch and drift guards.
   - Add `apps/solver-orchestrator/tests/test_batch_endpoint.py`.
   - Cover happy path with exactly 100 LP tasks: returns 202, one batch row, 100 child rows, ordered `optimization_ids`, all queued, no solver/billing/cost/voucher side effects.
   - Cover `tasks=[]`, `101` tasks, non-LP task, invalid fallback solver, `options.anonymous` without reproducible, `mode=sync`, and `X-Billing-Charge-Id`; each must be side-effect-free.
   - Cover idempotency replay and body/order conflict.
   - Cover GET aggregation by manually updating child statuses to queued/in_progress/completed/failed/timeout/cancelled and asserting counts, `batch_status`, progress, ETA, completed_at, ordered errors, and no `_system` leak.
   - Cover cross-tenant 404 no-leak and individual child GET compatibility.
   - Run focused, adjacent and full solver validation before implementation is marked code-review.

## Tasks / Subtasks

- [x] Task 1: Add batch schema and route skeleton. (AC: 1, 2, 6)
  - [x] Add `OptimizationBatchRequest` and response/item schemas in `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`.
  - [x] Add `POST /v1/optimizations/batch` and `GET /v1/optimizations/batch/{batch_id}` in `apps/solver-orchestrator/src/solver_orchestrator/routes.py`.
  - [x] Reject sync mode and `X-Billing-Charge-Id` before DB writes.
- [x] Task 2: Add batch persistence model and idempotent DDL. (AC: 4, 5)
  - [x] Add SQLAlchemy models for `OptimizationBatch`, `OptimizationBatchItem`, `OptimizationBatchIdempotencyKey`.
  - [x] Extend `infra/local-init/02-solver-schema.sql` with idempotent tables/indexes.
  - [x] Keep batch status/counts derived from child rows rather than stored counters.
- [x] Task 3: Implement side-effect-free async batch creation. (AC: 2, 3, 5, 6, 9)
  - [x] Validate all tasks with existing `OptimizationRequest` and prefix batch field paths as `tasks[i]`.
  - [x] Reuse provider/fallback validation helpers for every child before persistence.
  - [x] Create batch row, child `optimizations` rows, item rows and optional batch idempotency row in one transaction.
  - [x] Ensure no solver, billing, cost attribution, voucher or worker side effects happen on create.
- [x] Task 4: Implement batch status aggregation. (AC: 7, 8, 9)
  - [x] Load owner-scoped batch + ordered children through `optimization_batch_items`.
  - [x] Build child item payloads via existing optimization response/status builders.
  - [x] Compute counts, `batch_status`, progress, ETA, ordered errors and completed_at from children.
  - [x] Preserve individual child GET and DELETE semantics.
- [x] Task 5: Add focused tests and run validation. (AC: 10)
  - [x] Add `apps/solver-orchestrator/tests/test_batch_endpoint.py`.
  - [x] Run focused batch tests.
  - [x] Run adjacent solver tests for sync/async, status/progress, cancel/refund, billing integration, fallback execution and solver basics.
  - [x] Run full solver suite, type/lint/pre-commit and `git diff --check`.
- [x] Task 6: BMAD bookkeeping after implementation. (AC: 10)
  - [x] Move story status to `in-progress` when implementation starts.
  - [x] Update Dev Agent Record, File List and Change Log.
  - [x] After implementation, perform code review, apply fixes, then move to `code-review` / `done` only after validation passes.

### Review Findings

- [x] [Review][Patch] Cap batch progress below 100 unless every child is completed [apps/solver-orchestrator/src/solver_orchestrator/routes.py] — fixed by `_batch_progress_pct(...)` and regression coverage for `partial_failed` with 100% child progress.
- [x] [Review][Patch] Replay same-body batch idempotency after insert race instead of returning conflict [apps/solver-orchestrator/src/solver_orchestrator/routes.py] — fixed by reloading `optimization_batch_idempotency_keys` after rollback and replaying the existing batch when hashes match.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md` Story 3.13 requires: Given 100 LP tasks, When batch endpoint, Then 100 tasks async concurrent + one `batch_id` + user polling `batch_status`.
- `_bmad-output/planning/epics.md` L2 customer-support decision added `POST /v1/optimizations/batch` for 李工.
- `_bmad-output/planning/prd.md` Execution FR E1/E3/E9 require optimization submit, sync/async execution and status/progress/ETA/model_version retrieval.
- `_bmad-output/planning/prd.md` API rules require JSON snake_case, `Idempotency-Key` for POST, RFC 7807 errors and API-key auth scopes.
- `_bmad-output/planning/architecture.md` maps Execution E1-E10 to `solver-orchestrator` with `billing-service` integration, and defines FastAPI/Pydantic/SQLAlchemy/Postgres stack.
- `_bmad-output/planning/architecture.md` defines worker topology as future real-time/batch/retry/scheduled queues. Story 3.13 must not add new worker infrastructure.
- `_bmad-output/planning/ux-design-specification.md` positions 李工 as cURL/API primary user and documents idempotency retry rules and long-running task progress.

### Current Repository Reality

- Existing `POST /v1/optimizations` lives in `apps/solver-orchestrator/src/solver_orchestrator/routes.py::post_optimization`.
- Existing async path creates `optimizations` rows with `status="queued"` and returns `_build_async_accepted_response(...)`; there is still no real background worker in this repo slice.
- Existing status path is `GET /v1/optimizations/{optimization_id}` and uses `_build_optimization_status_response_content(...)` for queued/in_progress/failed/timeout/cancelled and `_build_response_content(...)` for completed rows.
- Existing `OptimizationRequest` already validates objective, `fallback_chain <= 3`, solver enum compatibility and options. Batch should compose it, not fork it.
- Existing `idempotency_keys` maps user/key to one optimization row. Batch needs its own batch idempotency table rather than forcing a whole batch through the single-row mapping.
- Existing async single optimization can reserve billing when a single `X-Billing-Charge-Id` is present, but batch has no per-item charge contract. Rejecting the header is the safest v1 boundary.
- Existing `infra/local-init/02-solver-schema.sql` is the local schema source for solver tables; this repo does not have an app-local Alembic tree for solver-orchestrator.

### Implementation Guidance

- Prefer small helper extraction around existing route code:
  - validate mode/header side effects early;
  - build provider/fallback route metadata for one `OptimizationRequest`;
  - build one queued child `Optimization` from a validated task and `batch_id/index`;
  - aggregate child status content into batch response.
- Keep field path precision. Batch validation errors must prefix existing field paths with `tasks[i].` so SDK `error.locate(...)` can identify the failed child input.
- Use `session.flush()` once after adding batch/children/items when possible. If adding idempotency row raises `IntegrityError`, rollback the whole transaction and return 409.
- Do not duplicate the single-child response contract. Add `index` to each batch item and merge the existing child content.
- Keep `batch_status` as derived data. Stored counters/status look convenient but will drift as future workers update child rows.
- Add route definitions before the dynamic `GET /v1/optimizations/{optimization_id}` section or otherwise ensure `/optimizations/batch/{batch_id}` is not misrouted.

### Boundary Rules

- No frontend, Console page, CSV/Excel upload, file upload, Postman collection, SDK generation, webhook, SSE, station-message or email notification in 3.13.
- No batch cancellation endpoint. Users may cancel child optimizations one by one via existing `DELETE /v1/optimizations/{optimization_id}`.
- No real parallel worker, Dramatiq actor, Redis Stream, queue consumer or scheduler in 3.13.
- No batch billing model, per-item billing charge array, automatic charge creation, refunds, compensation, reconciler batch retry or credits preview.
- No change to LP solver math, mock-real divergence, provider catalog, fallback execution result semantics or completed single optimization response.
- No storage or response exposure of Authorization headers, API keys, billing charge ids, `_system` metadata or internal provider route metadata.

### Previous Story Intelligence

- Story 3.3 established async queue semantics and the explicit message that background execution is not enabled in that story. 3.13 must preserve queued-only semantics unless a future worker story exists.
- Story 3.8 established cancellation/refund status and billing metadata redaction. 3.13 must not leak billing metadata in aggregate `errors`.
- Story 3.9 established status/progress/ETA normalization and public/internal metadata separation. 3.13 should reuse its helpers and not invent another progress contract.
- Story 3.10 established async billing as reserve-only and warned not to add worker/finalize behavior in unrelated stories. 3.13 rejects batch billing rather than inventing a new charge model.
- Story 3.11 explicitly excluded backend batch endpoint from CSV recovery. 3.13 should remain backend API only and not reopen CSV/UI scope.
- Story 3.12 reinforced the process rule: story document first, three pre-implementation review rounds with fixes applied, then implementation and post-implementation code review.

### Testing Standards

Focused validation after implementation:

```bash
uv run pytest apps/solver-orchestrator/tests/test_batch_endpoint.py -q
```

Adjacent regression set:

```bash
uv run pytest apps/solver-orchestrator/tests/test_sync_async_mode.py apps/solver-orchestrator/tests/test_status_progress_eta.py apps/solver-orchestrator/tests/test_cancel_refund.py apps/solver-orchestrator/tests/test_billing_integration.py apps/solver-orchestrator/tests/test_fallback_execution.py apps/solver-orchestrator/tests/test_solvers.py -q
```

Final validation before code-review:

```bash
uv run pytest apps/solver-orchestrator/tests -q
uv run mypy apps packages
uv tool run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

### Risks / Decisions

- Data consistency risk: `batch_id`, item order, `optimization_ids`, counts and errors can drift if derived independently. Use `optimization_batch_items.item_index` as the single ordering source and derive counts from child rows.
- Function consistency risk: implementing a separate batch status schema could diverge from single optimization status. Reuse existing child builders and only add top-level aggregate fields.
- Billing risk: one `X-Billing-Charge-Id` cannot safely represent 100 child charges. Reject it now; future per-item billing requires a separate contract.
- Idempotency risk: existing `idempotency_keys` cannot represent a batch. Add a batch-specific idempotency table and ensure replay returns the same ordered children.
- Scope drift risk: "async concurrent" can tempt adding workers. In this repo slice it means 100 queued child rows ready for existing/future async processing, not synchronous solve or new worker infrastructure.

## Story Review Rounds

### Round 1 - Data Consistency (2026-05-28)

Findings applied:

- Replaced ambiguous `succeeded` wording with repo-canonical child status `completed`; `counts` now has fixed keys and no alias.
- Bound `optimization_ids`, `items[].optimization_id`, `task_count` and counts to `optimization_batch_items.item_index` so ordering and counts cannot be independently invented.
- Defined exact `batch_status` derivation and `progress_pct` / `eta_seconds` / `completed_at` rules for active, completed, partial failure, full failure and cancellation cases.
- Added top-level `errors` aggregate ordered by item index and using existing error redaction.

Result: batch id, child ids, status counts, progress, ETA, result ordering and error aggregation are data-consistent.

### Round 2 - Function / Dependency Consistency and Drift (2026-05-28)

Findings applied:

- Required `OptimizationBatchRequest` to compose existing `OptimizationRequest`; no forked LP schema.
- Required provider/fallback validation and public child payloads to reuse existing route helpers/builders rather than hand-written batch-only shapes.
- Added separate batch tables and batch idempotency table because existing single optimization idempotency maps to one child only.
- Explicitly rejected new workers, queues and batch billing; batch create uses existing queued `optimizations` rows.

Result: Story 3.13 builds on the existing solver-orchestrator contracts without duplicating async/status/provider/billing/idempotency logic.

### Round 3 - Boundary / Edge Cases / Closure (2026-05-28)

Findings applied:

- Added fail-fast no-side-effect coverage for empty batch, 101 tasks, non-LP task, invalid fallback solver, anonymous-without-reproducible, `mode=sync`, billing header and idempotency conflicts.
- Clarified cross-tenant 404 no-leak behavior for batch status and child rows.
- Clarified no batch cancel, no UI/CSV/Excel, no SDK/codegen, no SSE/webhook/notification and no production worker in this story.
- Added validation commands and adjacent regression list so implementation cannot be marked complete on focused tests alone.

Result: boundary conditions, scope limits and completion evidence are closed before implementation starts.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-28 - Story 3.13 draft created from sprint status, Epics/PRD/Architecture/UX, existing solver-orchestrator routes/schemas/models/schema SQL, Story 3.3/3.8/3.9/3.10/3.11/3.12 learnings, and focused async/status/billing tests.
- 2026-05-28 - Story review Round 1 completed and applied: batch data consistency, child status vocabulary, counts, ordering, error aggregation, progress/ETA/completed_at.
- 2026-05-28 - Story review Round 2 completed and applied: helper reuse, DB grouping, idempotency separation, no new worker/queue/billing model.
- 2026-05-28 - Story review Round 3 completed and applied: fail-fast boundaries, owner isolation, no-leak rules, no UI/CSV/SDK/SSE scope, validation closure.
- 2026-05-28 - Dev implementation started; story and sprint status moved to in-progress.
- 2026-05-28 - RED phase completed: added `apps/solver-orchestrator/tests/test_batch_endpoint.py`; first focused run failed with 405 Method Not Allowed for missing batch endpoint.
- 2026-05-28 - GREEN/REFACTOR completed: added batch schemas/models/DDL/routes, side-effect-free create, batch idempotency and status aggregation.
- 2026-05-28 - Validation passed: focused batch tests `11 passed`; adjacent solver regression `62 passed`; full solver-orchestrator suite `274 passed`; `uv run mypy apps packages`; `uv tool run pre-commit run --all-files --show-diff-on-failure`; `git diff --check`.
- 2026-05-28 - Code review completed locally across Blind Hunter / Edge Case Hunter / Acceptance Auditor layers. Two patch findings were fixed: non-completed batch progress cap and idempotency race replay.
- 2026-05-28 - Post-review validation passed: focused batch tests `13 passed`; adjacent solver regression `62 passed`; full solver-orchestrator suite `276 passed`; `uv run mypy apps packages`; `uv tool run pre-commit run --all-files --show-diff-on-failure`; `git diff --check`.

### Implementation Plan

- Compose batch payloads from existing `OptimizationRequest`, then run per-item provider/fallback validation before any batch persistence so all validation/provider/fallback failures are fail-fast and side-effect-free.
- Persist `optimization_batches`, ordered `optimization_batch_items`, optional `optimization_batch_idempotency_keys` and queued child `optimizations` in one transaction; child rows carry `_system.batch`, `_system.execution_mode` and reused provider route metadata only.
- Build batch polling from ordered child rows using existing single-child response/status builders, deriving counts/status/progress/ETA/completed_at without stored counters.

### Completion Notes List

- Story 3.13 is ready for `bmad-dev-story` implementation.
- Three pre-implementation story review rounds were completed and reflected directly in ACs, tasks, Dev Notes and boundary rules.
- Implementation must not start by creating sibling worktrees; work remains in `D:\优化预测网站`.
- Implemented backend-only batch create/status endpoints with fixed async behavior, batch-specific persistence/idempotency, owner-scoped polling, ordered child aggregation and no solver/billing/cost/voucher side effects on create.
- Verified existing single optimization APIs through focused adjacent regression and full solver-orchestrator test suite.
- Code review patches applied and verified: `progress_pct` cannot report `100` unless batch status is `completed`, and same-body idempotency insert races replay the already-created batch rather than returning a spurious conflict.

### File List

- `_bmad-output/stories/3-13-batch-endpoint.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/models.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`
- `apps/solver-orchestrator/tests/test_batch_endpoint.py`
- `infra/local-init/02-solver-schema.sql`

### Change Log

- 2026-05-28 - Initial Story 3.13 created and reviewed through three pre-implementation rounds; sprint status moved from backlog to ready-for-dev.
- 2026-05-28 - Dev implementation started; status moved to in-progress.
- 2026-05-28 - Implemented Story 3.13 batch endpoint, persistence, idempotency, aggregation and focused/adjacent/full validation; status moved to code-review.
- 2026-05-28 - Applied post-implementation code review fixes for progress closure and idempotency race replay; final validation passed.
