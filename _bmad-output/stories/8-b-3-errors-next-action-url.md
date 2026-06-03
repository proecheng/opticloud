---
story_key: 8-b-3-errors-next-action-url
epic_num: 8
story_num: B.3
epic_name: AIGC Filter + Rate Limit + Error Codes RFC 7807
status: code-review
baseline_commit: 6d1b9c33eeedfa1cdf1dfe3d1ec52bb0a37dd457
priority: High
type: error contract closure
created_by: bmad-create-story
created_at: 2026-06-03
sources:
  - _bmad-output/planning/epics.md (Epic 8.B / Story 8.B.3)
  - _bmad-output/planning/prd.md (Error Codes RFC 7807 / FR O7 / FG1.3)
  - _bmad-output/planning/architecture.md (P29 Error Handling / RFC 7807 shape)
  - _bmad-output/stories/3-7-rfc7807-errors-detail.md
  - _bmad-output/stories/8-b-2-rate-limit-per-plan.md
  - packages/shared-py/opticloud_shared/schemas/errors.py
  - packages/shared-py/opticloud_shared/errors/rfc7807.py
  - apps/billing-service/src/billing_service/routes.py
  - apps/solver-orchestrator/src/solver_orchestrator/error_catalog.py
  - apps/solver-orchestrator/src/solver_orchestrator/error_responses.py
  - packages/python-sdk/src/opticloud/errors.py
---

# Story 8.B.3 - 4xx/402/429 errors[] + next_action_url

Status: code-review

## Story

**作为** API/SDK 用户、Console 用户和平台集成方，
**我希望** 4xx、402 Credits 不足、429 限流等可恢复错误统一返回 RFC 7807 `errors[]` detail 和 `next_action_url`，
**从而** 客户端能直接定位字段、读取 i18n remediation key，并把用户引导到充值、升级计划或排错文档，而不是解析不一致的 `next_action` / 422 旧错误。

## Context

FR O7 要求系统对 `4xx/402/429` 返回 `next_action_url`；FG1.3 要求 `errors[]` detail object 保留 `field_path`、`value`、`constraint`、`remediation_hint_key`。PRD 的 402 示例固定为：

- status: `402`
- type: `https://api.opticloud.cn/errors/insufficient_credits`
- remediation key: `errors.402.topup`
- `next_action_url`: `https://console.opticloud.cn/topup?suggested_amount=10`

当前仓库已经有多处基础能力：

- `packages/shared-py/opticloud_shared/schemas/errors.py` 定义 `ErrorResponse.next_action_url` 和 `errors[]`。
- `solver-orchestrator` 的 Story 3.7/8.B.2 代码已使用 `next_action_url`，并对多数 4xx/429 catalog entries 提供 non-empty URL。
- `packages/python-sdk/src/opticloud/errors.py` 已保留 `errors[]` 和 `next_action_url`，测试已有 402 解析用例。

当前缺口主要在实际服务闭环：

- shared legacy helper `opticloud_shared.errors.rfc7807_error` 仍把 remediation URL 序列化为 legacy key `next_action`，而不是 PRD/Schema 要求的 `next_action_url`。
- `billing-service` 使用该 helper；`POST /v1/billing/charges` 的余额不足路径当前返回 `422 Insufficient balance` + `errors.422.insufficient_balance`，与 PRD 的 `402 Insufficient Credits` + `errors.402.topup` + topup URL 不一致。
- `billing-service` 的 `_problem_response` wrapper 当前没有 `next_action_url` 参数，导致其他 4xx billing problem responses 无法按 O7 补充 remediation URL。

## Scope

1. 修正 shared RFC7807 helper：
   - 对外响应字段必须是 `next_action_url`。
   - 不得再序列化 legacy `next_action`。
   - 保留调用兼容性，避免既有使用 `next_action=` 的调用点立刻崩溃；如果新增 `next_action_url=`，两者冲突时必须有确定优先级或显式错误。
2. 修正 billing insufficient credits path：
   - `POST /v1/billing/charges` 当 `amount > balance_before` 时返回 402。
   - `Content-Type` 为 `application/problem+json`。
   - body 包含 non-empty `errors[]`，remediation key 为 `errors.402.topup`。
   - body 包含 `next_action_url=https://console.opticloud.cn/topup?suggested_amount=10`。
   - body 不包含 legacy `next_action`。
   - 失败路径不得创建 charge saga、不得缓存 idempotency response、不得扣减 ledger。
3. 为 billing 4xx problem wrapper 增加默认/显式 `next_action_url`：
   - 402 使用充值 URL。
   - 409 budget pause 引导预算设置。
   - 409 idempotency 引导幂等文档。
   - 403/404/422 等已有 `_problem_response` 调用至少能显式或默认带一个可恢复 URL。
   - 5xx 不强制 `next_action_url`。
4. 增加 solver catalog guard：
   - 所有 4xx 以及 429 `ERROR_CATALOG` entries 必须有 non-empty `next_action_url`。
   - `rate_limit_exceeded` 必须仍指向 `https://console.opticloud.cn/billing/plans`。
   - 不重写 solver error builder，只补 guard/缺口。
5. 更新测试，先 RED 后 GREEN：
   - shared helper 序列化 `next_action_url` 且不含 `next_action`。
   - billing insufficient credits 返回 402 + topup URL + `errors.402.topup`。
   - idempotency 失败路径仍不缓存。
   - solver 4xx/429 catalog guard。

## Out Of Scope

- 不实现 `RFC7807ErrorPanel`、Toast、aria-live 或前端按钮；这是 Story 8.B.4。
- 不实现 ESLint `error-message-i18n-single-source`；这是 Story 8.B.5。
- 不扩展 SDK parser；Python SDK 已有 preservation 测试，完整 SDK contract 是 Story 8.B.6。
- 不新增真实 `apps/api-gateway` runtime；当前请求处理在 service routes。
- 不改 rate-limit Redis 逻辑或 429 header 语义；8.B.2 已完成。
- 不把所有历史 4xx 调用一次性国际化成真正的 i18n 字典查表；本 story 只闭合响应 shape、status、remediation key 和 URL。

## Acceptance Criteria

1. Shared RFC7807 helper emits the correct O7 field.
   - `rfc7807_error(..., next_action=...)` response body contains `next_action_url`.
   - `rfc7807_error(..., next_action_url=...)` response body contains `next_action_url`.
   - Response body never contains legacy `next_action`.
   - Existing callers without remediation URL keep current behavior.

2. Billing insufficient credits path matches PRD.
   - Given authenticated user balance is lower than requested charge amount.
   - When `POST /v1/billing/charges` is called.
   - Then status is `402`.
   - Then body title is `Insufficient Credits`.
   - Then body type is `https://api.opticloud.cn/errors/insufficient_credits`.
   - Then body includes `errors[]` with `field_path="body.amount"`, non-empty constraint, and `remediation_hint_key="errors.402.topup"`.
   - Then body includes `next_action_url="https://console.opticloud.cn/topup?suggested_amount=10"`.
   - Then body does not include `next_action`.

3. Billing failed charge creation remains closed-loop.
   - 402 insufficient credits does not persist a charge saga.
   - 402 insufficient credits does not persist a cached idempotency response body.
   - 402 insufficient credits does not debit any Credits ledger row.
   - Existing explicit-confirmation warning path remains 422 and still does not cache unsuccessful response bodies.

4. Billing 4xx problem responses can carry remediation URLs consistently.
   - `_problem_response` accepts explicit `next_action_url`.
   - For known 4xx statuses where no explicit URL is passed, wrapper provides a bounded default URL instead of omitting O7.
   - 5xx responses are not forced to carry a `next_action_url`.
   - Wrapper still returns `application/problem+json`.

5. Solver O7 guard remains green.
   - Every 4xx and 429 entry in `solver_orchestrator.error_catalog.ERROR_CATALOG` has non-empty `next_action_url`.
   - 429 `rate_limit_exceeded` still points to the plan-upgrade URL from Story 8.B.2.
   - Solver response builder still serializes only `next_action_url`, never `next_action`.

6. Regression coverage and quality gates.
   - RED tests are added first and observed failing for the 422/legacy field defects.
   - Focused billing tests pass.
   - Focused shared-py tests pass.
   - Focused solver RFC7807 tests pass.
   - Required gates: `uv run ruff check` on touched Python packages, `uv run ruff format --check` on touched Python packages, relevant mypy checks where already feasible, and `git diff --check`.

7. Workflow and GitHub closure.
   - Story records three pre-implementation adversarial review rounds and revisions.
   - Implementation starts only after story status reaches `ready-for-dev`.
   - During implementation sprint status moves to `in-progress`, then `code-review` after local gates.
   - Post-implementation code review covers boundary issues, drift, data consistency, dependency consistency, closed-loop behavior, and tests.
   - Only after PR merge, remote branch deletion, and local `main` sync may story/sprint status be marked `done` and pushed as a status-sync commit.

## Tasks / Subtasks

- [x] T1: Add RED tests for the O7 defects (AC: 1, 2, 3, 5, 6)
  - [x] Shared helper test for `next_action_url` serialization and no `next_action`.
  - [x] Billing insufficient credits test updated to 402 + topup URL.
  - [x] Idempotency unsuccessful charge test updated to 402 while preserving no-cache assertion.
  - [x] Solver 4xx/429 catalog guard expanded if needed.

- [x] T2: Fix shared RFC7807 helper (AC: 1, 4)
  - [x] Add/accept `next_action_url` parameter while preserving `next_action` call compatibility.
  - [x] Serialize only `next_action_url`.
  - [x] Add conflict handling or deterministic precedence for both parameters supplied.

- [x] T3: Fix billing problem response wrapper and insufficient credits path (AC: 2, 3, 4)
  - [x] Add bounded remediation URL constants.
  - [x] Thread `next_action_url` through `_problem_response`.
  - [x] Change insufficient balance response to 402 Insufficient Credits with `errors.402.topup`.
  - [x] Set `type_uri` for insufficient credits.
  - [x] Keep unsuccessful charge creation side effects closed.

- [x] T4: Add/confirm solver and SDK contract guards (AC: 5)
  - [x] Ensure solver 4xx and 429 catalog entries have URLs.
  - [x] Ensure no legacy `next_action` is serialized.
  - [x] Reuse existing SDK preservation tests; add only if a defect is found.

- [x] T5: Run local validation gates (AC: 6)
  - [x] Focused shared-py tests.
  - [x] Focused billing tests.
  - [x] Focused solver RFC7807 tests.
  - [x] Ruff check / format-check for touched Python paths.
  - [x] Mypy where feasible for touched packages/services.
  - [x] `git diff --check`.

- [ ] T6: Review and GitHub sync (AC: 7)
  - [x] Complete post-implementation code review and fix findings.
  - [ ] Commit, push, create PR, wait CI, merge, delete remote branch, sync local main.
  - [ ] After merge/sync, mark story/sprint status done and push status-sync commit.

## Dev Notes

### Current Repository Reality

- `apps/api-gateway` is still an empty/stub runtime; do not implement O7 there.
- Billing routes use `from opticloud_shared.errors import ErrorDetail, rfc7807_error`.
- Billing `_problem_response` currently only forwards title/status/detail/errors and cannot pass type URI or remediation URL.
- Billing insufficient balance currently returns 422 with title `Insufficient balance` and `errors.422.insufficient_balance`.
- Shared helper currently emits `next_action` if `next_action` is supplied; this conflicts with PRD, shared schema, solver tests, and SDK expectations.
- Solver catalog already has `rate_limit_exceeded` 429 with `https://console.opticloud.cn/billing/plans`.
- Python SDK already reads `body.get("next_action_url")`; no SDK code change is expected unless tests reveal a regression.

### Suggested Implementation Shape

- In `packages/shared-py/opticloud_shared/errors/rfc7807.py`, keep `next_action` as a deprecated compatibility argument but serialize it into `next_action_url`.
- Add `next_action_url` and `type_uri` support to billing `_problem_response`, then pass explicit topup metadata from the insufficient credits branch.
- Add small URL constants in billing routes rather than scattering string literals.
- Keep `errors[]` values non-sensitive: use the requested amount string and balance summary; never expose raw JWT, user id, idempotency key, or saga internals.
- Prefer focused tests in existing billing/shared/solver test files over creating broad integration suites.

## Definition Of Done

- Story has passed 3 pre-implementation adversarial review rounds with revisions recorded.
- Shared RFC7807 helper no longer serializes legacy `next_action`.
- Billing insufficient credits returns 402 RFC7807 with `errors.402.topup` and the fixed topup URL.
- Billing unsuccessful charge path remains no-cache and no-side-effect.
- Solver 4xx/429 `next_action_url` guard remains green.
- Local quality gates and GitHub CI pass.
- PR merge, remote branch deletion, and local `main` sync complete before marking story/sprint `done`.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-b-3-errors-next-action-url`.
- Baseline commit: `6d1b9c33eeedfa1cdf1dfe3d1ec52bb0a37dd457`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base `bmad-create-story/customize.toml`, found no project/user overrides, and no `project-context.md`.
- Story creation analyzed Epic 8.B / FR O7, PRD Error Codes RFC 7807, Architecture P29, Story 3.7, Story 8.B.2, shared schemas/helper, billing charge route, solver error catalog/builder, and Python SDK error parser.
- 2026-06-03 - Implementation started; story and sprint status moved to `in-progress`.
- 2026-06-03 - RED confirmed: shared RFC7807 helper emitted legacy `next_action` and rejected `next_action_url=...`; billing insufficient credits still returned 422 with `errors.422.insufficient_balance`.
- 2026-06-03 - Implemented shared `next_action_url` support with deprecated `next_action` compatibility, billing RFC7807 helper/default next-action mapping, billing 402 insufficient credits response, and FastAPI HTTPException/request-validation problem handlers.
- 2026-06-03 - Post-implementation review found FastAPI request validation errors were still default 422 JSON; fixed with `RequestValidationError` handler and missing `Idempotency-Key` problem-details test.
- 2026-06-03 - Local gates passed; story and sprint status moved to `code-review`. Final `done` remains gated on PR merge, remote branch deletion, and local `main` sync.

### Completion Notes List

- Shared RFC7807 helper now serializes remediation URLs as `next_action_url`; legacy `next_action` remains a deprecated input alias and is never serialized.
- Billing problem responses now share a billing-specific RFC7807 helper with bounded O7 next-action defaults for 4xx statuses.
- Billing `POST /v1/billing/charges` insufficient credits path now returns 402 `Insufficient Credits`, PRD type URI, `errors.402.topup`, and `https://console.opticloud.cn/topup?suggested_amount=10`.
- Billing HTTPException and request validation paths now return `application/problem+json` with non-empty `errors[]` and `next_action_url`.
- Solver RFC7807 tests now pin the 429 rate-limit next-action URL to the plan-upgrade URL.
- Local gates passed: shared-py focused tests (10 passed), billing focused tests (42 passed), solver RFC7807 tests (9 passed), ruff check/format-check, mypy for touched shared/billing modules, and `git diff --check`.

### Post-Implementation Code Review

Outcome: Approved after fixes.

Findings and fixes:

1. Request validation closure gap: FastAPI-generated 422 responses, such as missing required headers, bypassed billing `_problem_response` and would return default JSON without `errors[]` or `next_action_url`. Added a `RequestValidationError` handler in `billing_service.main` and a missing `Idempotency-Key` regression test.
2. HTTPException closure gap: dependency-layer 401/400 responses bypassed route wrappers. Added a billing HTTPException handler using the shared billing problem helper and covered missing auth / invalid idempotency key paths.
3. Drift guard gap: solver already required 4xx URLs but did not pin the 429 plan-upgrade URL. Added a direct guard for `rate_limit_exceeded`.

Residual boundaries:

- Full i18n single-source enforcement remains Story 8.B.5.
- SDK parser expansion remains Story 8.B.6; existing Python SDK preservation tests already cover 402 `next_action_url`.
- Final `done` remains gated on GitHub PR merge, remote branch deletion, local `main` sync, and status-sync commit.

### File List

- `_bmad-output/stories/8-b-3-errors-next-action-url.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/billing-service/src/billing_service/main.py`
- `apps/billing-service/src/billing_service/problem_details.py`
- `apps/billing-service/src/billing_service/routes.py`
- `apps/billing-service/tests/test_charge_idempotency_routes.py`
- `apps/billing-service/tests/test_charge_routes.py`
- `apps/solver-orchestrator/tests/test_rfc7807_errors_detail.py`
- `packages/shared-py/opticloud_shared/errors/rfc7807.py`
- `packages/shared-py/tests/test_rfc7807_helper.py`

## Change Log

- 2026-06-03 - Story created for 8.B.3 4xx/402/429 errors[] + next_action_url.
- 2026-06-03 - Implementation started; story and sprint status moved to in-progress.
- 2026-06-03 - Implementation completed with shared helper, billing 402/topup, billing problem handlers, solver guard, tests, and post-review fix; story moved to code-review pending GitHub sync.

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary And Placement Review

Findings:

1. Architecture service map assigns O7 partly to `api-gateway`, but this repo does not have a real gateway runtime; implementing there would create dead code and leave billing responses broken.
2. Story 8.B.4/8.B.5/8.B.6 are adjacent but separate. Pulling UI, ESLint, or SDK expansion into 8.B.3 would blur acceptance and increase regression risk.
3. Solver already has a mostly compliant error builder and catalog; rewriting it would risk breaking Story 3.7 and 8.B.2.
4. Billing insufficient credits is the explicit PRD example and currently violates both status code and remediation URL.

Revision after Round 1:

- Scoped implementation to shared helper + actual service route layers, primarily billing, with solver guard tests only.
- Added explicit out-of-scope for front-end panel, ESLint i18n enforcement, SDK expansion, and API Gateway fabrication.
- Added AC2 for the 402 topup response and AC5 for solver guard-only closure.

### Round 2 - Drift, Schema, And Data Consistency Review

Findings:

1. Shared schema says `next_action_url`, while shared legacy helper emits `next_action`; this creates contract drift between billing and solver/SDK.
2. Changing helper output without preserving the `next_action=` argument would break existing callers even though the response key should change.
3. `errors[]` must remain a list of structured detail objects, not a string or generic message.
4. Billing's idempotency cache must not persist unsuccessful 402 bodies, or a later valid retry could replay a failure.

Revision after Round 2:

- Added AC1 requiring helper compatibility while serializing only `next_action_url`.
- Added AC3 requiring no saga, no cached idempotency response, and no ledger debit on 402.
- Added task coverage for idempotency unsuccessful charge tests.

### Round 3 - Dependency, Closure, And Workflow Review

Findings:

1. `_problem_response` cannot currently pass `type_uri` or remediation URL, so only changing one route would leave a reusable wrapper inconsistent.
2. O7 requires 4xx/402/429, but not every 4xx path has a natural product CTA; wrapper needs bounded defaults and explicit overrides for important paths.
3. 5xx errors should not be forced into user remediation URLs because operator/system failures may need support/docs rather than action.
4. User workflow requires final `done` only after PR merge, remote branch deletion, local `main` sync, and status-sync push.

Revision after Round 3:

- Added AC4 for `_problem_response` URL threading and bounded 4xx defaults while exempting 5xx.
- Added workflow AC7 and DoD gating final `done` on GitHub merge/sync.
- Added post-implementation review expectations for boundary, drift, consistency, closed-loop behavior, and tests.
