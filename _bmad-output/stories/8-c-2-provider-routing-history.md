---
story_key: 8-c-2-provider-routing-history
epic_num: 8
story_num: C.2
epic_name: Teaching + Provider Routing + Legal + Algorithm Library
status: done
baseline_commit: 333cf75798eb83039563cb2a732898eb38849feb
priority: High
type: FR O9 provider routing history
created_by: bmad-create-story
created_at: 2026-06-04
sources:
  - _bmad-output/planning/epics.md (Epic 8.C / Story 8.C.2)
  - _bmad-output/planning/prd.md (FR O9)
  - _bmad-output/planning/implementation-readiness-report-2026-05-17-v2.md (O9 service mapping)
  - _bmad-output/stories/2-7-fallback-execution.md
  - _bmad-output/stories/7-b-9-provider-console-tier3.md
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py
  - apps/solver-orchestrator/src/solver_orchestrator/provider_routing.py
  - apps/solver-orchestrator/src/solver_orchestrator/fallback_execution.py
  - apps/solver-orchestrator/tests/test_fallback_execution.py
  - apps/web/src/lib/api.ts
  - apps/web/src/app/console/providers/page.tsx
---

# Story 8.C.2 - Provider Routing History

Status: done

## Story

**作为** Console 用户，
**我希望** 能在 Console 中输入自己的 optimization ID 查看该次任务的 Provider routing tree、最终执行 Provider 和 fallback attempt history，
**从而** 可以解释为什么任务被路由到某个 Provider、是否发生 fallback，以及每次 attempt 的状态和耗时，而不泄露内部诊断、账单、凭据或其他用户数据。

## Context

PRD/epics 对 FR O9 的定义是：用户 can view Provider routing history in Console。Story 7.B.9 已经实现 `/console/providers`，但它是 Provider Marketplace v2 的只读聚合页面，消费 capability-registry 的 application/route-share/KPI/revenue/version/monthly batch dashboard；该 story 明确排除了完整 ProviderRoutingHistory。Story 2.7 已经在 solver-orchestrator 持久化了单次 optimization 的 `_system.provider_route`、`_system.executed_provider_route` 和 `_system.fallback_execution`，但 public response 和 Console 目前不暴露这些 routing history。

因此本 story 的最小闭环不是新增 Provider Marketplace dashboard，也不是读取 capability-registry raw dashboard；而是把用户自己的 optimization routing history 以安全、只读、可解释的 public contract 暴露，并在 Console 中渲染。

注意：`_bmad-output/planning/ux-design-specification.md` 的 O9 行写成了 Credits 过期约束，这与 PRD/epics 的 O9 冲突。本 story 以 PRD/epics/implementation-readiness 的 Provider routing history 为准，并在审查中锁定该漂移风险。

## Scope

1. Backend public-safe routing history contract。
   - 在 solver-orchestrator 中新增 public-safe `routing_history` metadata builder。
   - completed optimization 的 `POST /v1/optimizations` sync response、idempotency replay、`GET /v1/optimizations/{id}` response 都可返回 `routing_history`。
   - queued/in_progress/cancelled/timeout/failed status response 也应返回可用的 safe routing fields；对于还未执行的 async queued 任务，至少返回 primary planned route 和 attempt count 0。
   - Batch response 不在本 story 暴露 child routing history，避免 batch 列表响应体膨胀和把 per-item 诊断默认推送给批量轮询端。
   - 必须只读取当前 authenticated user 自己的 optimization；沿用现有 GET ownership check。
2. Console routing history 页面。
   - 新增 `/console/routing-history` 页面。
   - 允许未登录页面直接显示查询表单；若现有 Console shell 后续要求 JWT，可只把 JWT 用作页面访问门槛，不得把 auth-service JWT 当 solver API credential。
   - 用户输入 API key 和 optimization ID 后调用 solver GET endpoint；API key 只保存在 React 内存态，不写入任何 browser storage。
   - 渲染 primary route、executed route、routing tree/attempt timeline、summary stats 和 empty/error states。
3. Web API contract。
   - 在 `apps/web/src/lib/api.ts` 为 `routing_history` 增加类型。
   - 新增 `getOptimization(apiKey, optimizationId)` client，使用 solver-orchestrator 既有 `Authorization: Bearer sk-...` API key 语义，只发 GET，不带 body、billing header、internal service auth 或 idempotency key。
   - `getOptimization()` 返回类型必须覆盖 completed 和 status/polling responses；不要把 queued/failed/timeout/cancelled 响应强行套进只表示 completed success 的 `OptimizationResponse`。
4. Discoverability。
   - 在现有 Console 导航中增加 `/console/routing-history` 可发现入口，避免使用泛化 `/console/history` 与 audit/repro history 混淆。

## Out Of Scope

- 不新增数据库表、migration、后台 worker、capability-registry endpoint、Provider Marketplace dashboard 或 route-share/KPI/revenue 聚合。
- 不实现 8.C.6 Provider Console Tier 3、更完整 Command Palette、ConsoleSearch、Grafana dashboard 或 provider ownership system。
- 不展示 raw `_system`、raw `fallback_execution`、raw `input_payload`、request body、solution payload、billing charge id、reserve/finalize metadata、cost attribution metadata、stack trace、authorization header、API key、API-key prefix/hash、tenant/user identifiers、provider credentials 或 exception object。
- 不改变 solver routing/fallback execution 决策；本 story 只展示既有 persisted routing metadata。
- 不给 anonymous reproducibility/voucher 增加特殊可见性；匿名只影响 reproduction metadata，不改变 routing ownership。
- 不承诺 demo endpoint routing history；Console 使用 authenticated persisted optimization。
- 不承诺 `GET /v1/optimizations/batch/{batch_id}` 返回 child routing history；批量详情若需要 routing tree，应由用户进入单个 optimization ID 查询。

## Acceptance Criteria

1. Backend defines a public-safe `routing_history` response object assembled only from `_system.provider_route`, `_system.executed_provider_route`, `_system.fallback_execution`, `Optimization.model_version`, `Optimization.status`, `created_at`, `completed_at`, and `solve_seconds`.
2. `routing_history.primary_route` includes only `task_type`, `requested_solver`, `selected_solver`, `provider_id`, `provider_kind`, `provider_url`, and `routing_reason`.
3. `routing_history.executed_route` includes the same safe route fields when an executed route exists; for queued/in_progress rows it is `null` rather than guessed from `model_version`.
4. `routing_history.summary` includes `attempt_count`, `fallback_used`, `terminal_status`, `terminal_attempt`, `exhausted`, and `solve_seconds`.
5. `routing_history.attempts[]` includes only `attempt`, `role`, `requested_solver`, `selected_solver`, `provider_id`, `provider_kind`, `provider_url`, `routing_reason`, `status`, `retryable`, and `solve_seconds`.
6. Public `routing_history` never includes raw `error_constraint`, `error_field_path`, request payload, billing charge ID, billing metadata, API keys, auth headers, user IDs, tenant IDs, stack traces, exception objects, cost attribution metadata, raw `_system`, or raw fallback metadata.
7. For historical rows without `_system.fallback_execution`, backend returns a stable single-attempt history from available route metadata instead of failing; if neither primary nor executed route exists it omits `routing_history`.
8. For async queued rows, backend returns `attempt_count=0`, `fallback_used=false`, `terminal_status=null`, `terminal_attempt=null`, `exhausted=false`, `attempts=[]`, primary route populated, and executed route null.
9. For completed fallback success, sync response, idempotency replay and GET response expose identical `routing_history`.
10. For timeout/failed exhausted fallback rows, GET/status response exposes safe `routing_history` while preserving existing public error semantics and redaction.
11. `GET /v1/optimizations/batch/{batch_id}` child items must not include `routing_history` in this story, even though child items reuse optimization response builders internally.
12. Existing responses that do not have provider route metadata omit `routing_history`; they must not raise 500 or return partially malformed routing objects.
13. Web types include optional `routing_history` with exact snake_case fields from backend.
14. Web adds a `GetOptimizationResponse` union/broad status type that can represent at least `completed`, `queued`, `in_progress`, `failed`, `timeout`, and `cancelled` GET responses without unsafe casts.
15. Web adds `getOptimization(apiKey, optimizationId)` using `GET /v1/optimizations/{encodeURIComponent(optimizationId)}` against `SOLVER_SERVICE_URL`.
16. `getOptimization` sends only `Authorization: Bearer <apiKey>` plus existing Accept-Language behavior; it sends no body, no `X-Billing-Charge-Id`, no `X-Internal-Service-Auth`, and no `Idempotency-Key`.
17. `/console/routing-history` keeps API key and optimization ID in React memory state only and writes nothing to `localStorage` or `sessionStorage`.
18. The page requires non-empty API key and non-empty optimization ID before loading, and renders clear validation errors for empty inputs.
19. The page does not log, echo, mask-preview, copy, or otherwise render the API key or API-key prefix/hash.
20. The page handles completed and non-completed GET statuses; routing panels render from `routing_history` when present and status/model fields must not assume `solution`, `objective`, or completed-only timestamps exist.
21. The page displays primary route and executed route as separate safe summaries.
22. The page displays attempt timeline/tree in attempt order and clearly marks primary vs fallback, retryable vs terminal, and terminal attempt.
23. The page displays a fallback summary (`fallback_used`, `attempt_count`, `terminal_status`, `solve_seconds`).
24. Empty routing history renders an explicit empty state, not a crash or blank panel.
25. 404/403-style errors render safe user-facing errors without exposing raw backend payloads.
26. Layout remains dense Console UI, responsive on mobile, with stable table/card dimensions and no text overlap.
27. Existing `/console/providers` navigation adds a discoverable link to `/console/routing-history`.
28. Implementation introduces no new npm dependency, no new shared UI dependency, and no new backend runtime dependency.
29. Backend tests cover safe builder fallback behavior, completed fallback success, queued async planned route, timeout exhausted safe fields, idempotency replay parity, batch exclusion, and non-leakage of raw metadata.
30. Web tests cover API client URL encoding/auth/no-body/no-internal headers, successful routing timeline rendering, missing API key/input validation, empty/no-history state, non-completed status rendering, backend error state, and no storage writes.
31. Local gates pass: targeted solver tests, targeted web tests, web typecheck, solver ruff/format, solver mypy if touched, and `git diff --check`.
32. Post-implementation code review is completed and findings are fixed or explicitly documented.
33. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done` through a separate status-sync commit.

## Tasks / Subtasks

- [x] T1: Backend routing history contract (AC: 1-12, 27)
  - [x] Add typed/small helpers in `routes.py` or a focused helper module to build safe route and routing history payloads.
  - [x] Attach `routing_history` to `_build_response_content()` and `_build_optimization_status_response_content()`.
  - [x] Preserve existing public response fields and error/status semantics.
  - [x] Add solver-orchestrator tests for completed, queued, timeout/failed, historical and idempotency replay paths.

- [x] T2: Web API contract (AC: 13-16, 30)
  - [x] Add TypeScript interfaces for routing history.
  - [x] Add broad GET response type and `getOptimization()` solver client with encoded path segment.
  - [x] Add API client tests for GET URL encoding/auth/no-body/no-internal headers.

- [x] T3: Console page (AC: 17-27, 30)
  - [x] Add `/console/routing-history` page with API-key/optimization-id input validation.
  - [x] Render safe route summaries, attempt timeline/tree, summary metrics, loading/empty/error states.
  - [x] Add navigation link from `/console/providers`.
  - [x] Add page tests for success, empty validation, no-history, non-completed status, backend error and storage behavior.

- [x] T4: Review, gates and GitHub sync (AC: 28-33)
  - [x] Run post-implementation code review and fix/document findings.
  - [x] Run local quality gates.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, sync local `main`.
  - [x] Mark story/sprint status `done` only after merge/sync via separate status-sync commit.

## Dev Notes

### Existing Backend Facts

- `POST /v1/optimizations` already persists provider routing metadata under `_system.provider_route`.
- Story 2.7 persists final route under `_system.executed_provider_route` and attempt metadata under `_system.fallback_execution`.
- Public success response is assembled by `_build_response_content(opt)`.
- Public queued/failed/timeout/cancelled response is assembled by `_build_optimization_status_response_content(opt)`.
- `GET /v1/optimizations/{id}` already enforces `opt.user_id == user_id`; reuse that ownership boundary.
- Batch responses reuse `_build_response_content()` / `_build_optimization_status_response_content()` for children; any routing history added there must be safe for batch too.

### Existing Web Facts

- `apps/web/src/lib/api.ts` already has `SOLVER_SERVICE_URL`, `postOptimization()`, and `OptimizationResponse`.
- Current `postOptimization()` intentionally supports sync/teaching only, not async typed responses.
- `OptimizationResponse` currently models completed sync responses. `GET /v1/optimizations/{id}` can return status/polling shapes; add a separate GET response type rather than broadening completed-only fields unsafely.
- `/console/providers` already uses JWT from `sessionStorage.jwt_access`, redirects to `/auth/login`, uses dense Console layout, and has tests.
- Solver-orchestrator optimization endpoints verify API keys through `verify_api_key()` and require `sk-` bearer tokens, not auth-service JWTs. A Console page that queries solver optimization history must ask for an API key unless a future auth bridge exists.
- Use local React state and existing `StatusCard`, `EmptyState`, `LoadingShimmer`; do not add chart libraries or state libraries.

### Data Semantics

- Primary route is the initially selected Provider route.
- Executed route is the terminal route after fallback execution; it can equal primary.
- Attempt timeline is solver-orchestrator attempt history, not capability-registry route-share/traffic rollout history.
- `fallback_used=true` should mean an executed terminal attempt index greater than 1 or any fallback attempt was executed.
- Public `routing_history.summary.solve_seconds` must use the same aggregate elapsed seconds exposed as top-level `solve_seconds` for terminal rows; do not introduce a separate `total_solve_seconds` public field.
- `routing_reason` is a machine-safe reason string such as `default_solver` or `explicit_solver`; do not localize it in backend.
- Batch responses currently reuse response builders for children; implementation must add a switch or wrapper so single optimization responses can include routing history while batch list/detail responses do not.

### Review Constraints

- This story must pass exactly 3 pre-implementation adversarial review rounds before implementation.
- Each round must produce findings and story revisions before the next round starts.
- Do not move status to `in-progress` until all 3 rounds pass.
- Do not mark story/sprint `done` before PR CI, merge, remote branch deletion, local main sync, and separate status-sync commit.

## Definition Of Done

- Story has passed exactly 3 pre-implementation adversarial review rounds with revisions recorded after each round.
- Users can view their own optimization Provider routing history in Console.
- Backend exposes only a public-safe routing history contract and does not leak raw internal metadata.
- Existing Provider Console 7.B.9 behavior and solver fallback execution behavior remain compatible.
- Local gates and GitHub CI pass.
- Post-implementation code review completed and findings fixed or explicitly documented.
- Story and sprint status become `done` only after PR merge/sync/status-sync closure.

## Story Review Log

### Round 1: Boundary And Ownership Review

Findings fixed:

- Initial story incorrectly specified `sessionStorage.jwt_access` as the credential for `GET /v1/optimizations/{id}`. Solver-orchestrator optimization endpoints use API-key bearer auth (`sk-...`) via `verify_api_key()`, so using an auth-service JWT would fail or encourage a cross-service auth drift. Revised web client/page requirements to use a session-only API key input.
- Initial page requirement redirected to `/auth/login` on missing JWT, but that would not prove the user can query solver-owned optimization rows. Revised the page to keep API key and optimization ID in React memory only, with explicit validation and no storage writes.
- Initial non-leakage requirements mentioned API keys but not prefixes/hashes. Added explicit prohibition on rendering API key prefixes/hashes.

Status: PASS after fixes.

### Round 2: Data Consistency And Leakage Review

Findings fixed:

- Initial story used public `summary.total_solve_seconds` while existing internal fallback metadata and top-level optimization response use `solve_seconds`. This invited duplicate elapsed-time fields with drift risk. Revised the public contract to use `summary.solve_seconds` and explicitly match top-level aggregate `solve_seconds`.
- Initial story allowed batch child items to include `routing_history` through reused builders. That would expand batch polling payloads and expose per-item routing diagnostics by default. Revised scope and ACs to exclude batch routing history in this story; users should query the single optimization endpoint for routing details.
- Initial historical-row fallback was underspecified when no route metadata exists. Revised ACs to omit `routing_history` rather than returning malformed/null-internal objects.

Status: PASS after fixes.

### Round 3: Dependency And Closure Review

Findings fixed:

- Initial story asked `getOptimization()` to return the existing completed-only `OptimizationResponse`. The GET endpoint can return queued, in-progress, timeout, failed, and cancelled status shapes with different fields. Revised the web contract to add a separate broad `GetOptimizationResponse` and require page handling for non-completed statuses.
- Initial story did not state URL path encoding for user-entered optimization IDs. Revised the client AC to require `encodeURIComponent(optimizationId)` and tests for URL encoding, preventing path-shape drift from raw input.
- Initial test list did not explicitly cover batch exclusion after Round 2 changed the boundary. Added backend test coverage for batch responses not including `routing_history`.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-c-2-provider-routing-history`.
- Baseline commit: `333cf75798eb83039563cb2a732898eb38849feb`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base skill instructions and project config.
- Story creation analyzed Epic 8.C.2, PRD O9, implementation readiness O9 mapping, 2.7 fallback execution metadata, 7.B.9 Provider Console boundary, solver response builders, provider routing helper, fallback tests and web API/Console patterns.
- 2026-06-04 - Completed pre-implementation adversarial review round 1 and revised API-key/auth boundary for Console routing history.
- 2026-06-04 - Completed pre-implementation adversarial review round 2 and revised public elapsed-time naming, batch exclusion and historical-row fallback semantics.
- 2026-06-04 - Completed pre-implementation adversarial review round 3 and revised GET response typing, URL encoding and batch-exclusion test requirements; story is ready for implementation.
- 2026-06-04 - Moved story to in-progress after exactly three pre-implementation adversarial review rounds.
- 2026-06-04 - Implemented backend public-safe routing history builders, attached single optimization responses, excluded batch child routing history, and added routing history regressions.
- 2026-06-04 - Implemented `getOptimization()` broad GET response contract, `/console/routing-history` page, provider navigation link, and page/API tests.
- 2026-06-04 - Post-implementation code review findings fixed: GET client no longer sends JSON `Content-Type`, TS attempt type now matches backend AC5 shape, terminal attempt is explicitly marked in timeline, batch GET exclusion and missing-route omission have direct tests.
- 2026-06-04 - Local gates passed: solver targeted pytest 44 passed; web targeted Vitest 12 passed; web typecheck passed; solver mypy passed; ruff check passed; ruff format check passed; git diff --check passed.
- 2026-06-04 - PR #162 passed GitHub CI, squash-merged to `main` at `62dc7ea`, remote branch `codex/8-c-2-provider-routing-history` deleted, and local `main` synced.
- 2026-06-04 - Story and sprint status marked `done` via separate status-sync commit after merge/sync closure.

### Completion Notes List

- Initial story created.
- Round 1 pre-implementation review completed and story revised.
- Round 2 pre-implementation review completed and story revised.
- Round 3 pre-implementation review completed and story revised.
- Story moved to in-progress for implementation.
- Backend `routing_history` contract implemented from safe `_system` provider/fallback metadata with missing-metadata omission and batch exclusion.
- Console `/console/routing-history` implemented with in-memory API key/optimization ID state, validation, safe error/empty states, route summaries, summary metrics and ordered attempt timeline.
- Post-implementation code review completed; all patch findings fixed.
- Local quality gates passed; story moved to `code-review` pending GitHub sync.
- GitHub CI passed; PR #162 merged; remote feature branch deleted; local `main` synced.
- Story closed as `done` after merge/sync in a separate status-sync commit.

### File List

- `_bmad-output/stories/8-c-2-provider-routing-history.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/test_routing_history.py`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/api-optimization.test.ts`
- `apps/web/src/app/console/routing-history/page.tsx`
- `apps/web/src/app/console/routing-history/page.test.tsx`
- `apps/web/src/app/console/providers/page.tsx`

## Change Log

- 2026-06-04 - Story created for 8.C.2 Provider routing history.
- 2026-06-04 - Round 1 pre-implementation review revised solver auth boundary and API-key storage constraints.
- 2026-06-04 - Round 2 pre-implementation review revised data consistency, batch-response boundary and missing-metadata behavior.
- 2026-06-04 - Round 3 pre-implementation review revised dependency closure for GET response typing, URL encoding and batch-exclusion coverage.
- 2026-06-04 - Story status moved to in-progress after pre-implementation review closure.
- 2026-06-04 - Implemented provider routing history backend contract, web client, Console page, tests, post-implementation review fixes and local gates; story status moved to code-review.
- 2026-06-04 - PR #162 passed CI, merged to main, remote branch deleted, local main synced; story status moved to done in separate status-sync commit.

## Post-Implementation Code Review (AI)

Outcome: Changes requested, then fixed.

Findings fixed:

- `getOptimization()` initially reused the generic JSON request helper, causing GET requests to send `Content-Type: application/json`. Fixed with a GET-specific fetch path that sends only `Authorization` and `Accept-Language`; API test now asserts no body, no `Content-Type`, no billing/internal/idempotency headers.
- `RoutingHistoryAttempt` initially inherited `RoutingHistoryRoute`, adding a `task_type` field that backend attempts do not expose and AC5 does not allow. Fixed the TypeScript type to match the backend snake_case attempt contract exactly.
- Attempt timeline displayed primary/fallback and retryable but did not explicitly mark the terminal attempt. Added a terminal column and page test coverage.
- Batch exclusion was tested on POST batch response only. Added batch GET assertion so `/v1/optimizations/batch/{batch_id}` child items also remain free of `routing_history`.
- Missing route metadata omission was implied but not directly tested. Added completed-row regression proving `routing_history` is omitted rather than malformed when provider route metadata is absent.

Status: PASS after fixes.
