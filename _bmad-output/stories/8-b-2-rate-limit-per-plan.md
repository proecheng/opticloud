---
story_key: 8-b-2-rate-limit-per-plan
epic_num: 8
story_num: B.2
epic_name: AIGC Filter + Rate Limit + Error Codes RFC 7807
status: code-review
baseline_commit: c01afdddb2a9eb88ed9437e103e6cd029c1acddf
priority: High
type: rate limit enforcement
created_by: bmad-create-story
created_at: 2026-06-03
sources:
  - _bmad-output/planning/epics.md (Epic 8.B / Story 8.B.2)
  - _bmad-output/planning/prd.md (Rate Limits / FR O6)
  - _bmad-output/planning/architecture.md (D9 Redis sliding-window-counter + Lua)
  - _bmad-output/planning/ux-design-specification.md (429 retry/upgrade guidance)
  - _bmad-output/stories/5-b-1-five-plans-subscription.md
  - _bmad-output/stories/3-7-rfc7807-errors-detail.md
  - apps/billing-service/src/billing_service/plans.py
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py
  - apps/solver-orchestrator/src/solver_orchestrator/error_responses.py
---

# Story 8.B.2 - Rate limit per plan + 429

Status: code-review

## Story

**作为** API/SDK 用户和平台 SRE，
**我希望** authenticated execution 写路径按用户当前 plan 执行 Redis sliding-window 限流，并在超限时返回 429 + `X-RateLimit-*` + `Retry-After`，
**从而** Free/Starter/Pro/Team/Enterprise 的请求吞吐边界能被服务端实际执行，且超限请求不会创建任务、不会 reserve/finalize billing、不会扣 Credits。

## Context

FR O6 要求系统按计划限流并返回 429 headers。PRD 的 plan 表定义：

- Free: RPS 3, requests/min 30, concurrent solves 1
- Starter: RPS 5, requests/min 200, concurrent solves 3
- Pro: RPS 20, requests/min 1000, concurrent solves 10
- Team: RPS 100, requests/min 5000, concurrent solves 30
- Enterprise: custom

Story 5.B.1 已在 `apps/billing-service/src/billing_service/plans.py` 建立五计划 catalog，并包含同一份 rate-limit 元数据。`billing_subscriptions` 是 plan 状态来源；没有 active subscription 的用户应按 implicit Free 处理。当前 `solver-orchestrator` 的 authenticated routes 会直接验证 API key 并进入 provider/idempotency/billing/DB side effect，尚未执行 Redis 限流。

Architecture D9 指定 Redis 7+ sliding-window-counter + Lua，key prefix 使用 `ratelimit:`。仓库已有 `REDIS_URL` 环境变量和 docker-compose Redis，但 `solver-orchestrator` 当前没有 Redis dependency/settings。Story 3.7 已为 solver 提供 RFC7807 `ErrorResponse` builder 与 error catalog，8.B.2 应复用它新增 429 path，而不是重写错误系统或抢 8.B.3 的全局 O7 收尾。

## Scope

1. 在 `solver-orchestrator` 中新增 plan-aware rate-limit 模块：
   - 读取 `REDIS_URL`。
   - 使用 Redis Lua 原子执行 sliding-window-counter。
   - key 使用 `ratelimit:{plan}:{user_id}:{scope}:{window}` 或等价的 bounded key，必须包含 `ratelimit:` 前缀。
   - 同时检查 per-second 和 per-minute 窗口；以最紧的 exceeded window 决定 `Retry-After` / reset。
2. 在 authenticated execution 写路径插入限流：
   - `/v1/optimizations`
   - `/v1/optimizations/batch`
   - `/v1/predictions`
   - `/v1/reproduce/{voucher_id}/rerun`
   - job-template create/version/delete 等会写入用户状态的 authenticated route，如果实现复杂度过大，可先覆盖 execution submit/rerun 并在 story 中记录 deferred boundary；不得误称全站限流完成。
3. 限流必须发生在 billing reserve/finalize、Optimization/Prediction/Batch 持久化、solver execution、cost telemetry 之前。
4. Plan resolution:
   - 查询 `billing_subscriptions` 当前 active row；没有 active row 时使用 `free`。
   - 只读取 bounded `plan_code`，不读取/暴露 subscription metadata。
   - 若遇到 unknown/corrupt plan，fail closed 为 Free 或 500 sanitized operator error；不得放宽为 Enterprise。
5. 429 response:
   - status `429`
   - `Content-Type: application/problem+json`
   - headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`
   - body 复用 solver RFC7807 `ErrorResponse`，包含 non-empty `errors[]` 和 `next_action_url`。
6. Drift guard:
   - solver 侧 plan limit 数值不得静默漂移；可通过共享 helper、importable shared module、或 tests/static guard 对齐 `billing_service.plans`.
   - 不新增前端限流、客户端自限流、gateway stub 或 public pricing claims。

## Out Of Scope

- 不实现真实 API Gateway；`apps/api-gateway` 仍为空壳。
- 不实现 concurrent solves cap；PRD 表中并发求解是后续 queue/depth story 的边界，本 story 只覆盖 RPS + requests/min。
- 不改变 billing subscription 创建、充值、扣费、refund、invoice、budget 或 payment 逻辑。
- 不扣 Credits，不创建 billing charge，不调用 billing reserve/finalize 来记录 429。
- 不限流无鉴权 `/v1/optimizations/demo`；该 route 当前明确注释 v1 无限制，IP/demo 限流留到单独 story。
- 不实现 Enterprise 自定义合同读取；Enterprise 可暂按 unlimited/custom bypass 或 capped static policy，但必须记录边界，不得伪造合同配置。
- 不新增浏览器 UI、toast、SDK retry helper；这些属于 8.B.3/8.B.4/8.B.6 后续错误恢复面。
- 不泄露 user id、API key、subscription id、Redis key、stack trace、billing metadata 或 raw request body。

## Acceptance Criteria

1. Plan limit contract is explicit and tested.
   - Free resolves to limit 3/sec and 30/min.
   - Starter resolves to 5/sec and 200/min.
   - Pro resolves to 20/sec and 1000/min.
   - Team resolves to 100/sec and 5000/min.
   - Enterprise/custom does not accidentally inherit Free because of missing code; the chosen v1 behavior is explicit in code and tests.
   - Tests guard solver-side limits against drift from the billing plan catalog or from the PRD-backed canonical table used by billing-service.

2. Active plan resolution is correct.
   - User with no `billing_subscriptions` row is treated as Free.
   - User with active Starter/Pro/Team subscription receives that plan's limits.
   - Canceled/expired subscription rows are ignored.
   - Plan lookup never exposes subscription metadata or PII.

3. Redis sliding-window limiter is atomic and key-bounded.
   - Limiter uses Redis Lua/EVAL or EVALSHA for check+increment.
   - Redis keys start with `ratelimit:`.
   - Per-second and per-minute windows are both checked.
   - Headers are calculated from the exceeded/tightest window and are deterministic under tests.
   - Unit tests cover allow, exact boundary, exceeded boundary, and reset/retry-after calculation without requiring a live Redis service.

4. `/v1/optimizations` 429 path closes billing and persistence side effects.
   - For Free user, first 3 requests inside one second are allowed, the 4th returns 429.
   - 429 response contains `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, and `Retry-After`.
   - 429 body is `application/problem+json` and includes `errors[]`, `request_id`, and `next_action_url`.
   - On 429, `billing_client.reserve`, `billing_client.finalize`, solver execution, Optimization insert, idempotency insert, and cost telemetry do not run.

5. Additional authenticated execution writes use the same limiter contract.
   - Batch submit and prediction submit are checked before their DB side effects.
   - Rerun submit is checked before voucher lookup side effects that can create linked work.
   - GET/status reads are not counted unless explicitly documented.
   - Job-template write routes are either covered or explicitly deferred in implementation notes with no false completion claim.

6. Failure modes are safe and observable.
   - Missing Redis URL or Redis unavailable does not silently disable production limit enforcement.
   - In tests/dev, the limiter can be injected or disabled only through an explicit test hook/settings path.
   - Redis failure returns sanitized RFC7807 503 or fail-closed 429 according to code policy; it must not proceed to billing/solve as if allowed.
   - No secrets, raw Redis keys, user ids, API keys, or stack traces appear in errors/logged public payloads.

7. Regression coverage and quality gates.
   - RED tests are added first and fail before implementation for missing 429 headers and no side-effect guard.
   - Focused tests cover `apps/solver-orchestrator/tests/test_rate_limit.py` or equivalent.
   - Existing billing integration tests still pass for non-limited requests.
   - Required gates: focused solver tests, `uv run ruff check apps/solver-orchestrator`, `uv run ruff format --check apps/solver-orchestrator`, mypy for solver-orchestrator with existing PYTHONPATH, and `git diff --check`.

8. Workflow and GitHub closure.
   - Story records three pre-implementation adversarial review rounds and revisions.
   - Implementation starts only after story status reaches `ready-for-dev`.
   - During implementation sprint status moves to `in-progress`, then `code-review` after local gates.
   - Post-implementation code review covers boundary issues, drift, data consistency, dependency consistency, closed-loop behavior, no-credit/no-side-effect, Redis failure, headers, and tests.
   - Only after PR merge, remote branch deletion, and local `main` sync may story/sprint status be marked `done` and pushed as a status-sync commit.

## Tasks / Subtasks

- [x] T1: Add plan limit and plan resolver contract (AC: 1, 2)
  - [x] Resolve active plan from `billing_subscriptions`; fallback to Free.
  - [x] Add drift guard against billing plan rate limits.
  - [x] Cover no active subscription, active subscription, and canceled/expired rows.

- [x] T2: Add Redis sliding-window limiter (AC: 3, 6)
  - [x] Add solver Redis setting/dependency.
  - [x] Implement Lua atomic check+increment.
  - [x] Add fake/injected limiter tests for boundaries and headers.

- [x] T3: Wire authenticated execution write paths (AC: 4, 5)
  - [x] Check `/v1/optimizations` before provider/idempotency/billing/DB side effects.
  - [x] Check `/v1/optimizations/batch`.
  - [x] Check `/v1/predictions`.
  - [x] Check `/v1/reproduce/{voucher_id}/rerun`.
  - [x] Decide and document job-template write coverage/defer.

- [x] T4: Add 429 RFC7807 response support (AC: 4, 6)
  - [x] Add rate-limit error catalog entry.
  - [x] Attach headers to the solver problem response.
  - [x] Ensure response values are bounded and no sensitive values leak.

- [x] T5: Regression tests and gates (AC: 4, 5, 7)
  - [x] Add RED tests first and confirm failure.
  - [x] Add green implementation tests.
  - [x] Run focused and package gates.

- [ ] T6: Review and GitHub sync (AC: 8)
  - [x] Complete post-implementation review and fix findings.
  - [ ] Commit, push, create PR, wait CI, merge, delete remote branch, sync local main.
  - [ ] After merge/sync, mark story/sprint status done and push status-sync commit.

## Dev Notes

### Current Repository Reality

- `apps/api-gateway` currently only contains `.gitkeep`; request handling is in service routes, not a real gateway layer.
- `docker-compose.yml`, `.env`, and `.env.example` already define Redis, but `apps/solver-orchestrator/src/solver_orchestrator/config.py` has no `redis_url`.
- `apps/solver-orchestrator/pyproject.toml` currently lacks `redis>=5.0`, while other services already use `redis` in the workspace lock.
- `apps/billing-service/src/billing_service/plans.py` owns the five plan definitions and PRD rate-limit metadata.
- `infra/local-init/11-billing-subscriptions.sql` creates `billing_subscriptions` with `plan_code` and one active subscription per user.
- `apps/solver-orchestrator/src/solver_orchestrator/auth.py` verifies API keys against `api_keys` and returns `(user_id, api_key_id, scopes)`.
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py` currently calls `verify_api_key(...)` in route handlers and then proceeds to validation, billing, DB inserts, and solve execution without rate-limit checks.
- `apps/solver-orchestrator/src/solver_orchestrator/error_responses.py` already builds solver RFC7807 `ErrorResponse` with `next_action_url`, `errors[]`, `request_id`, and localized title/detail.
- `/v1/optimizations/demo` is unauthenticated and explicitly says v1 has no rate limit; do not include it in per-plan authenticated limit.

### Suggested Implementation Shape

- Add a small `solver_orchestrator/rate_limit.py` module with:
  - `PLAN_RATE_LIMITS` or a shared import contract for plan limits.
  - `resolve_user_plan_code(session, user_id)`.
  - `RateLimitDecision` with `allowed`, `limit`, `remaining`, `reset_epoch_seconds`, `retry_after_seconds`, `plan_code`, and `window_seconds`.
  - Redis-backed limiter using Lua.
  - Test fake/injected limiter that implements the same interface.
- Add a lightweight helper in `routes.py`, e.g. `_enforce_rate_limit(...)`, called after auth/scope and before side effects.
- Add error catalog key `rate_limit_exceeded` with status 429 and upgrade/docs `next_action_url`, for example `https://console.opticloud.cn/billing/plans`.
- Keep route call sites simple; do not introduce middleware that re-parses API keys.

## Definition Of Done

- Story has passed 3 pre-implementation adversarial review rounds with revisions recorded.
- Authenticated execution write paths enforce plan-aware Redis sliding-window RPS/minute limits.
- Free 4th request in one second returns 429 with required headers and RFC7807 body.
- 429 path does not call billing, solver, cost telemetry, or persist Optimization/Prediction/Batch rows.
- Plan limit values cannot drift silently from the billing plan catalog.
- Local quality gates and GitHub CI pass.
- PR merge, remote branch deletion, and local `main` sync complete before marking story/sprint `done`.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-b-2-rate-limit-per-plan`.
- Baseline commit: `c01afdddb2a9eb88ed9437e103e6cd029c1acddf`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base `bmad-create-story/customize.toml`, found no project/user overrides, and no `project-context.md`.
- Story creation analyzed Epic 8.B / FR O6, PRD Rate Limits, Architecture D9 and request pipeline, UX 429 guidance, Story 5.B.1 plan catalog, Story 3.7 RFC7807 builder, and current solver route/auth/billing behavior.
- 2026-06-03 - Implementation started; story and sprint status moved to `in-progress`.
- 2026-06-03 - RED confirmed: focused rate-limit tests initially failed for missing sliding-window helper, expired active subscription filtering, 503 catalog mapping, and focused billing catalog import path.
- 2026-06-03 - Implemented Redis sorted-set Lua sliding-window check for second/minute windows, bounded `ratelimit:` keys, fail-closed Redis error handling, plan resolver period filtering, 429/503 RFC7807 responses, and authenticated write-path wiring.
- 2026-06-03 - Post-implementation review found fixed-window drift and incomplete 503 catalog mapping; both were fixed before local gates.
- 2026-06-03 - Post-review evidence was strengthened for all plan drift fields, Starter/Pro/Team active plan resolution, and dual-window atomic no-write-on-deny behavior.
- 2026-06-03 - Story and sprint status moved to `code-review`; final `done` remains gated on PR merge, remote branch deletion, and local `main` sync.

### Completion Notes List

- Added `solver_orchestrator.rate_limit` with plan-aware Free/Starter/Pro/Team limits, explicit Enterprise custom/unlimited bypass, current-period active subscription resolution, and Redis Lua sliding-window enforcement.
- Wired authenticated execution write paths after API-key auth/scope and before billing, solver, idempotency, DB persistence, and template write side effects: optimizations, batch, predictions, rerun, job-template create/version/delete.
- Added 429 `rate_limit_exceeded` and 503 `rate_limit_unavailable` RFC7807 catalog entries; 429 includes `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`, non-empty `errors[]`, and plan upgrade URL without leaking Redis keys or user ids.
- Added rate-limit tests for plan drift, active/canceled/expired plan resolution, sliding-window boundary/reset behavior, Redis unavailable fail-closed behavior, route side-effect closure, and job-template/write-path coverage.
- Local gates passed: `uv run pytest apps/solver-orchestrator/tests/test_rate_limit.py -q` (12 passed), full solver tests (313 passed), `uv run ruff check apps/solver-orchestrator`, `uv run ruff format --check apps/solver-orchestrator`, solver mypy with PYTHONPATH, and `git diff --check`.

### Post-Implementation Code Review

Outcome: Approved after fixes.

Findings and fixes:

1. Fixed-window implementation risk: initial limiter used `INCR`/`EXPIRE` bucket keys despite D9 requiring Redis sliding-window-counter + Lua. Replaced with sorted-set Lua script using `ZREMRANGEBYSCORE`, `ZCARD`, `ZADD`, and `PEXPIRE`; script checks all configured windows first and writes to none if any window is exceeded.
2. 503 error mapping risk: `RateLimitUnavailableError` initially fell through to a generic title/status mapping. Added `rate_limit_unavailable` catalog entry and explicit `error_key` support in route RFC7807 wrapper.
3. Drift/data-consistency evidence gap: initial tests only sampled some plan fields and one paid plan. Added tests for all Free/Starter/Pro/Team RPS + minute limits, Enterprise custom behavior, Starter/Pro/Team active resolution, expired active rows, and dual-window atomic no-write-on-deny behavior.

Residual boundaries:

- `/v1/optimizations/demo` remains unauthenticated and intentionally out of scope.
- Concurrent solve caps remain out of scope for a later queue/depth story.
- Enterprise custom contract lookup remains out of scope; v1 behavior is explicit unlimited/custom bypass.

### File List

- `_bmad-output/stories/8-b-2-rate-limit-per-plan.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/pyproject.toml`
- `apps/solver-orchestrator/src/solver_orchestrator/config.py`
- `apps/solver-orchestrator/src/solver_orchestrator/error_catalog.py`
- `apps/solver-orchestrator/src/solver_orchestrator/error_responses.py`
- `apps/solver-orchestrator/src/solver_orchestrator/rate_limit.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/conftest.py`
- `apps/solver-orchestrator/tests/test_rate_limit.py`
- `uv.lock`

## Change Log

- 2026-06-03 - Story created for 8.B.2 rate limit per plan + 429.
- 2026-06-03 - Implementation started; story and sprint status moved to in-progress.
- 2026-06-03 - Implemented plan-aware Redis sliding-window limiter, 429/503 RFC7807 support, authenticated write-path enforcement, tests, and post-review fixes; story moved to code-review pending GitHub sync.

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary And Placement Review

Findings:

1. Architecture names API Gateway, but `apps/api-gateway` is currently empty; implementing a gateway story would fabricate a nonexistent runtime layer.
2. Solver routes already authenticate API keys and own billing/DB side effects, so the safe insertion point is after auth/scope and before provider/idempotency/billing/persistence.
3. `/v1/optimizations/demo` is unauthenticated and explicitly documented as v1 unlimited; applying per-plan logic there would be a different IP/demo limit story.
4. Rate limit should not be implemented in billing-service because 429 must prevent billing calls, not be caused by them.

Revision after Round 1:

- Scoped implementation to `solver-orchestrator` authenticated execution write paths.
- Added explicit out-of-scope for API Gateway and unauthenticated demo.
- Added AC4 requiring no billing/DB/solver/cost side effects on 429.

### Round 2 - Drift And Plan Consistency Review

Findings:

1. The plan rate-limit table already exists in `billing_service.plans`; copying constants into solver without a guard creates silent drift risk.
2. Users without active subscription should inherit implicit Free, matching Story 5.B.1 current subscription behavior.
3. Expired/canceled subscription rows must not grant higher limits.
4. Enterprise custom limits cannot be truthfully enforced until a contract/config source exists.

Revision after Round 2:

- Added plan resolver requirements and tests for no active row, active row, and canceled/expired rows.
- Added drift guard requirement against billing plan rate limits.
- Added explicit Enterprise/custom boundary requirement.

### Round 3 - Redis, Headers, Failure, And Workflow Review

Findings:

1. `REDIS_URL` exists in environment files, but solver lacks settings and dependency; story must include dependency/config work.
2. Redis failure cannot silently disable enforcement, or production would violate FR O6 under outage.
3. 429 response needs both HTTP headers and RFC7807 body; only one of them is insufficient for SDK/retry clients.
4. User workflow requires story/status to remain not-done until GitHub CI, PR merge, remote branch deletion, local main sync, and status-sync commit complete.

Revision after Round 3:

- Added solver Redis setting/dependency task and failure-mode AC.
- Required `X-RateLimit-*` and `Retry-After` headers plus RFC7807 `errors[]`/`next_action_url`.
- Added workflow AC8 and DoD gating final `done` on GitHub merge/sync.
