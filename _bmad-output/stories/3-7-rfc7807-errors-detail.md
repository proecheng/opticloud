---
story_key: 3-7-rfc7807-errors-detail
epic_num: 3
story_num: 3.7
epic_name: Optimization & Prediction Execution
status: done
priority: Critical (FR E7 + FG1.3 M1 SDK recovery contract)
sizing: M (~5-8 hours; shared error catalog + route sweep + contract tests)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-27
sources:
  - _bmad-output/planning/epics.md:373 (Epic 3 goal includes RFC 7807 errors[] detail + next_action_url)
  - _bmad-output/planning/epics.md:1433-1435 (Story 3.7 AC)
  - _bmad-output/planning/prd.md:1125-1170 (RFC 7807 + FG1.3 errors[] detail object schema + next_action_url)
  - _bmad-output/planning/prd.md:1242 (actionable error recovery URLs)
  - _bmad-output/planning/prd.md:1474 (FR E7 v1 must-have)
  - _bmad-output/planning/architecture.md:673-678 (RFC 7807 and Accept-Language patterns)
  - _bmad-output/planning/architecture.md:874-893 (OptiCloudError/RFC 7807 middleware pattern)
  - _bmad-output/planning/ux-design-specification.md:1688-1770 (Retry Inline + SDK error detail/next_action_url)
  - _bmad-output/stories/3-6-prediction-quantiles.md (current prediction error paths and review process)
  - packages/shared-py/opticloud_shared/schemas/errors.py (canonical ErrorDetail/ErrorResponse schema)
  - packages/python-sdk/src/opticloud/errors.py (SDK preserves errors[] and next_action_url)
  - apps/web/src/lib/api.ts (web client preserves errors[] and next_action_url)
  - packages/ui/src/components/ErrorBoundary/index.tsx (RFC7807Panel consumes errors[] and next_action_url)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py (current inline _rfc7807_error and route error sites)
  - apps/solver-orchestrator/tests (current solver error regressions)
dependencies:
  upstream:
    - 3-1-j1-lp-solve (done) - established POST /v1/optimizations and first RFC 7807 shape.
    - 2-4-solver-enum (done) - unsupported solver validation already returns ErrorDetail.
    - 2-5-fallback-chain (done) - fallback_chain[i] field_path pattern already exists.
    - 2-6-multi-provider-routing (done) - provider route error helpers already produce route-specific error details.
    - 2-8-unaudited-block (done) - unaudited self route already uses next_action_url.
    - 3-6-prediction-quantiles (done) - prediction invalid-data and compact failed-row paths are current baseline.
    - packages/python-sdk error helpers (present) - SDK contract depends on preserving errors[] shape.
  downstream:
    - 3-8-cancel-refund - must reuse the same error catalog for cancel/refund errors.
    - 3-9-status-progress-eta - status/progress errors must preserve next_action_url and request_id.
    - 3-11-j2-lina-csv-vertical-slice - CSV recovery UX depends on precise field_path/value/constraint.
    - 8-b-5-error-i18n-eslint - later ESLint/static enforcement can audit the catalog created here.
    - 8-b-6-sdk-contract-preserve-errors - SDK contract should already pass with this story.
---

# Story 3.7 - RFC 7807 errors[] detail + next_action_url (FR E7 + FG1.3)

## User Story

作为 SDK/API 用户和前端错误恢复界面，
我希望 `solver-orchestrator` 的可恢复错误统一返回 RFC 7807 Problem Details、结构化 `errors[]`、`next_action_url` 和由 `Accept-Language` 控制的单语 `title/detail`，
以便 SDK 的 `error.locate()`、Console 的 Retry Inline 和后续 J2 错误恢复流程能稳定定位字段、提示修复动作，而不是拿到漂移的字符串或空错误数组。

## Why This Story

Story 3.1 已经在 `solver-orchestrator` 里引入 `_rfc7807_error()`，部分路径也已经返回 `ErrorDetail`。但当前实现仍有明显缺口：若调用点没有显式传 `errors` 或 `next_action`，响应会出现空 `errors[]` 或缺失 `next_action_url`；`title/detail` 多数是调用点硬编码英文；FastAPI/Pydantic 请求体校验默认 422 还可能绕开项目的 FG1.3 结构。

本 story 不重写业务求解、预测或 SDK。目标是把 FR E7 从“有一些 RFC 7807 响应”加固为“所有 solver-orchestrator 可恢复错误都有同一合同、同一 i18n 来源、同一客户端可定位结构”。

## Out of Scope

- 不迁移到新 API 版本，不改变成功响应 schema。
- 不实现 Node/Go SDK；仅保证现有 Python SDK 和 Web client 能继续无损消费 `errors[]` / `next_action_url`。
- 不做全仓库所有服务的错误治理；本 story 只覆盖 `apps/solver-orchestrator`，共享 schema/catalog 可放在 `packages/shared-py` 以便复用。
- 不引入数据库 migration、Redis、Sentry 或 OpenTelemetry trace wiring；`trace_id` 可继续为 `null`，但字段不得破坏。
- 不实现后续 `bmad-testarch` 或 ESLint 规则；可增加轻量 CI/test guard，后续 Story 8.B.5 再做跨语言静态 enforcement。
- 不把预测 compact failed status payload 改成错误 HTTP；3.6 的 failed-row 200 语义保持不变。
- 不把所有 5xx 都强行加 `errors[]`。平台未知 500 可保持安全通用，但显式可恢复的 4xx/402/403/404/409/410/422/429 和已知 501/504 路径必须闭环。
- 不使用外部网络服务、模型服务或新 runtime 依赖；若读取 YAML，优先使用仓库已有 PyYAML/stdlib可行方案。

## Acceptance Criteria

### AC1: canonical error catalog and Accept-Language resolution

- Add a single source of truth for solver-orchestrator error message templates and default remediation metadata.
- The catalog must contain at least every error key used by solver-orchestrator after this story, for `zh-CN` and `en-US`.
- Each catalog entry includes:
  - stable problem slug/type suffix, for example `invalid_prediction_data`;
  - localized `title`;
  - localized `detail` template;
  - default `constraint` template when practical;
  - default `remediation_hint_key`;
  - default `next_action_url` for every explicit 4xx/402/403/404/409/410/422/429 solver-orchestrator error key.
- `Accept-Language` controls only `title` and `detail`; do not return `detail_zh/detail_en` dual fields.
- Supported language selection:
  - `zh-CN`, `zh`, and weighted header values containing Chinese resolve to `zh-CN`;
  - `en-US`, `en`, and unsupported/missing language fallback resolve to `en-US` unless an existing test explicitly expects Chinese for a Chinese-only path.
- Dynamic details may interpolate safe values such as `field_path`, `task_type`, `solver`, `supported_solvers`, or `prediction_id`; never interpolate API keys, user ids, billing ids, stack traces, raw request bodies, `_system`, or secrets.
- Keep all public catalog keys stable and machine-readable; tests must assert key names, not only prose.
- Story data source uses the project-required Problem Details top-level fields from RFC 7807/PRD. RFC 9457 supersedes RFC 7807 in the wider standards track, but this story must not rename or remove the PRD-required fields.

### AC2: `_rfc7807_error` becomes the single response builder for route errors

- Move the effective builder into a small non-route module, for example `apps/solver-orchestrator/src/solver_orchestrator/error_responses.py`, then import it from both `routes.py` and `main.py`.
- Keep a thin `_rfc7807_error(...)` wrapper in `routes.py` only if it reduces call-site churn; the wrapper must delegate to the single builder and must not contain separate response construction logic.
- The builder must emit an `ErrorResponse` shape with:
  - `type`, `title`, `status`, `detail`, `errors`, `instance`, `request_id`, `trace_id`, `next_action_url`;
  - `Content-Type: application/problem+json` for error responses;
  - `instance` defaulting to the request path when a `Request` is supplied;
  - `request_id` from `X-Request-Id` or generated UUID as current routes do;
  - `trace_id` included as `null` if unavailable.
- All explicit solver-orchestrator route errors should go through this builder; do not introduce a second ad hoc error helper.
- Preserve the existing public field name `next_action_url`, not `next_action`; `packages/shared-py/opticloud_shared/errors/rfc7807.py` currently emits `next_action` and must not be used unchanged for solver responses.
- Do not regress existing tests that assert current titles/status codes unless the story deliberately updates those tests to the catalog-localized title for the same language.
- Add app-level `HTTPException` handling or migrate existing solver-orchestrator `HTTPException` raises so auth/catalog 401/403/404 errors also return the same `ErrorResponse` shape. Current `verify_api_key()`, `require_scope()`, and algorithm detail routes raise `HTTPException` before `_rfc7807_error()` can run.
- Avoid circular imports: `main.py` must not import `routes.py` only to build error responses, because `main.py` already imports `router` from `routes.py`.

### AC3: 4xx/402/403/404/409/410/422/429 route errors always include errors[] and next_action_url

- For every explicit solver-orchestrator response with status 400, 401, 402, 403, 404, 409, 410, 422, or 429:
  - `errors` contains at least one object;
  - every object has non-empty `field_path`, JSON-safe `value`, non-empty `constraint`, and non-empty `remediation_hint_key`;
  - `remediation_hint_key` starts with `errors.<status>.`;
  - `next_action_url` is non-empty and absolute `https://...` or an accepted app-relative URL only where existing frontend/auth patterns already require relative URLs.
- If a route has no field-specific violation, use stable fallback field paths:
  - `"$"` for request/body-level issues;
  - `"path.<param_name>"` for path IDs;
  - `"query.<name>"` for query errors;
  - `"header.<Header-Name>"` for header errors;
  - `"task_type"`, `"solver"`, `"fallback_chain[i]"`, `"family"`, `"st"`, `"st.b[i]"`, or existing precise paths where available.
- For sensitive or large values, set `value` to `"[redacted]"`, `"[omitted]"`, `"[non-finite]"`, or a compact scalar; never echo Authorization, API keys, JWTs, full LP matrices, `_system`, or full uploaded payloads.
- Keep existing specific field paths already used by tests, such as `fallback_chain[i]`, `solver`, `family`, `data[i]`, `options.max_solve_seconds`, and `header.X-Billing-Charge-Id`.
- For 501/504 explicit route errors, include `next_action_url` and `errors[]` when the error is actionable or already has a known field; 504 solver timeout remains actionable.
- For explicit 500 platform/config errors, return sanitized RFC 7807 fields but do not claim user-remediable `next_action_url` unless there is a concrete operator/docs action. Do not expose catalog internals beyond a safe slug.
- Unknown authentication failures should not reveal whether a key was missing, malformed, revoked, expired, or nonexistent beyond the existing safe `detail` class. `errors[].value` for `Authorization` must always be `"[redacted]"`.

### AC4: FastAPI/Pydantic request validation failures are converted to FG1.3 shape

- Add a FastAPI exception handler in `solver_orchestrator/main.py` or equivalent app setup for `RequestValidationError`.
- The handler must return 422 `application/problem+json` with:
  - localized title/detail from the same catalog;
  - `errors[]` converted from Pydantic locations into dot/bracket `field_path`;
  - `value` redacted/compacted and JSON-safe;
  - `constraint` derived from Pydantic error type/message without leaking raw internal stack traces;
  - `remediation_hint_key`, `next_action_url`, `instance`, and `request_id`.
- Body locations must map consistently:
  - `("body", "st", "A", 2, 1)` -> `st.A[2][1]`;
  - `("body", "options", "max_solve_seconds")` -> `options.max_solve_seconds`;
  - `("query", "mode")` -> `query.mode`;
  - `("header", "Idempotency-Key")` -> `header.Idempotency-Key`.
- The handler must preserve user-facing status 422 for schema validation and not mask authentication failures.
- Add regression tests for malformed LP body and bad prediction body that currently would be handled by FastAPI before route code.
- If using middleware/contextvars for request metadata, the validation handler and `HTTPException` handler must read the same context so `Accept-Language`, `instance`, `request_id`, and `trace_id` are consistent with route-built errors.

### AC5: optimization invalid input and solver/business failures expose precise field paths

- LP infeasible/unbounded/invalid input responses must include a meaningful `errors[]` entry:
  - use `result.error_field_path` when available;
  - fall back to `st`, `st.b[0]`, or `"$"` only when no precise path exists;
  - include solver/business constraint in `constraint`;
  - keep status 422 for business validation failures.
- Unsupported task type, unsupported solver, unsupported fallback solver, unaudited self algorithm, invalid execution mode, invalid UUID/header, billing reserve failure, anonymous without reproducible, rerun body errors, not-found paths, and voucher-expired 410 paths must each have deterministic catalog keys and next actions.
- Auth failures from `verify_api_key()` and `require_scope()` must return 401/403 RFC 7807 with `field_path` of `header.Authorization` or `scope`, redacted values, and a login/API-key management next action.
- Idempotency conflict remains 409 and must include `header.Idempotency-Key` in `errors[]` with the submitted key redacted or compacted if needed.
- Demo endpoint errors (`/v1/optimizations/demo`) must be covered too, because Console Excel flows consume those responses.
- Existing successful optimization, fallback execution, billing, voucher, and top-k behavior must not change.

### AC6: prediction validation errors use the same contract without regressing 3.6

- `POST /v1/predictions` invalid family, invalid data length/value/range, invalid horizon, billing-header rejection, and idempotency conflict must all use the catalog-backed RFC 7807 builder.
- Existing 3.6 behavior for malformed helper output and historical malformed completed rows remains compact 200 failed status payload; do not convert those into HTTP errors.
- Prediction validation tests must still assert:
  - precise `data[i]` field paths;
  - `family` for unsupported family;
  - `header.X-Billing-Charge-Id` for unsupported billing;
  - no raw `_system` exposure.
- Valid completed prediction POST/GET/idempotency replay remains byte-compatible except for unrelated headers.

### AC7: SDK/Web/UI consumer contract is preserved and tested

- Python SDK `OptiCloudHTTPError.from_response()` continues to preserve `errors[]`, `next_action_url`, `request_id`, `trace_id`, and raw body.
- `error.locate(field_path)`, `locate_all()`, `find_constraint()`, and `remediation_keys()` remain green with the new response examples.
- Web API client `apps/web/src/lib/api.ts` continues to preserve `errors[]` and `next_action_url`; no renaming to `next_action`.
- `packages/ui` `RFC7807Panel` can render every ErrorDetail field without assuming `value` is always scalar.
- Add at least one backend-to-SDK fixture-style test or static sample that proves a real solver-orchestrator error body can be consumed by the Python SDK without dropping fields.

### AC8: static drift guard prevents empty errors[] and hard-coded response drift

- Add focused tests or a small static contract test that scans solver-orchestrator route error responses/call sites enough to prevent regressions:
  - no explicit 4xx route response uses `_rfc7807_error` without an ErrorDetail or catalog default;
  - every used `remediation_hint_key` exists in the catalog for both supported languages;
  - every catalog entry used by routes has non-empty `title/detail` for `zh-CN` and `en-US`;
  - no solver-orchestrator route/error response helper emits a response field named `next_action` instead of `next_action_url`.
- The guard must avoid brittle full-file string policing where it would block legitimate non-error strings; focus on response builder/call-site contract.
- Static checks must ignore `next_action` variable names, comments, external docs, and SDK/UI code that discuss the concept; the forbidden drift is the serialized response key `next_action`.
- Do not add a heavyweight ESLint/plugin framework in this story; leave cross-language lint enforcement to Story 8.B.5.

### AC9: quality gates pass

Run before commit:

- `uv run pytest apps/solver-orchestrator/tests -q`
- `uv run pytest packages/python-sdk/tests/test_error_locate.py -q`
- `uv run pytest packages/shared-py/tests -q`
- `uv run mypy apps packages`
- `uv tool run pre-commit run --all-files --show-diff-on-failure`
- `git diff --check`

## Tasks / Subtasks

- [x] Task 1: Catalog and builder foundation (AC: 1, 2, 3)
  - [x] Add catalog-backed i18n resolution for solver-orchestrator errors.
  - [x] Move response construction to a non-route helper module and keep `_rfc7807_error` as a delegating wrapper if needed.
  - [x] Extend the builder to fill default ErrorDetail, next_action_url, instance, trace_id, media type, and localized title/detail.
  - [x] Add middleware/context handling or explicit request plumbing for `Accept-Language`, `instance`, `request_id`, and `trace_id`.
  - [x] Keep `ErrorResponse` / `ErrorDetail` canonical schema from `packages/shared-py/opticloud_shared/schemas/errors.py`.

- [x] Task 2: FastAPI validation handler (AC: 4)
  - [x] Convert `RequestValidationError` locations to dot/bracket `field_path`.
  - [x] Compact/redact invalid values and preserve request_id/instance.
  - [x] Add tests for malformed optimization and prediction payloads.

- [x] Task 3: Route error sweep for optimization/demo/rerun/prediction (AC: 3, 5, 6)
  - [x] Update all explicit route errors currently missing `errors[]` or `next_action_url`.
  - [x] Preserve existing precise field paths and status codes.
  - [x] Keep 3.6 compact failed-row response behavior unchanged.

- [x] Task 4: Consumer contract and drift tests (AC: 7, 8)
  - [x] Add backend tests for Accept-Language and complete error object shape.
  - [x] Add SDK fixture/sample test using a real solver-orchestrator-shaped error body.
  - [x] Add catalog/static drift guard for keys, remediation hints, and `next_action_url`.

### Review Findings

- [x] [Review][Patch] Sensitive header values in caller-provided `ErrorDetail` bypassed builder redaction. The shared builder now normalizes all supplied details, redacts `header.Authorization`, `header.Idempotency-Key`, and `header.X-Billing-Charge-Id`, maps remediation keys back to catalog entries, and adds a regression proving idempotency conflicts do not echo the submitted key. [apps/solver-orchestrator/src/solver_orchestrator/error_responses.py]

- [x] Task 5: Validation gates and status updates (AC: 9)
  - [x] Run focused and full backend tests.
  - [x] Run SDK/shared-py tests, mypy, pre-commit, and diff-check.
  - [x] Update Dev Agent Record, File List, Change Log, and sprint status.

## Dev Notes

### Current Implementation Facts

- `packages/shared-py/opticloud_shared/schemas/errors.py` already defines the canonical `ErrorDetail` and `ErrorResponse` schema with `next_action_url`.
- `packages/shared-py/opticloud_shared/errors/rfc7807.py` is an older reusable helper that emits `next_action`, not `next_action_url`; do not reuse it unchanged for solver-orchestrator.
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py` imports `ErrorDetail` and `ErrorResponse` from the canonical schema module and has an inline `_rfc7807_error()`.
- Current `_rfc7807_error()` fills `type/title/status/detail/errors/next_action_url/request_id`, but defaults `errors` to `[]`, does not set meaningful `instance`/`trace_id`, and does not set `application/problem+json`.
- Many route call sites already pass useful ErrorDetail objects. Some still call `_rfc7807_error()` with no `errors`, especially not-found, invalid JSON/body, not implemented, LP infeasible/unbounded, solver error, and some idempotency/missing-resource paths.
- `apps/solver-orchestrator/src/solver_orchestrator/auth.py` raises `HTTPException` for 401/403. Without an app-level handler, those responses will remain FastAPI `{"detail": ...}` and fail FR E7.
- `routes.py` also raises `HTTPException` for unpublished/missing algorithm detail routes and internal status parsing. These must either be converted to the builder or normalized by a handler.
- `apps/solver-orchestrator/src/solver_orchestrator/main.py` already allows `Accept-Language` through CORS; use the request header rather than adding a new public header.
- `apps/web/src/lib/api.ts`, `packages/python-sdk/src/opticloud/errors.py`, and `packages/ui/src/components/ErrorBoundary/index.tsx` already consume `errors[]` and `next_action_url`; preserve those names and shapes.
- Existing tests assert some English titles such as `"Unsupported Solver"` and `"Invalid Prediction Data"` without setting `Accept-Language`; keep missing-language fallback stable or update tests intentionally.

### Implementation Guidance

- Prefer a small module such as `apps/solver-orchestrator/src/solver_orchestrator/error_catalog.py` for catalog data and language/template helpers.
- Prefer a separate response builder module such as `apps/solver-orchestrator/src/solver_orchestrator/error_responses.py` so `main.py` exception handlers and `routes.py` route helpers share code without circular imports.
- Consider a lightweight middleware/contextvars module, for example `error_context.py`, that records `Accept-Language`, request path, request id, and trace id for the current request. This avoids threading `accept_language` through every existing helper. If explicit parameters are used instead, tests must cover enough nested helper paths to prove language is not silently dropped.
- Suggested helper names:
  - `SUPPORTED_ERROR_LOCALES = {"en-US", "zh-CN"}`
  - `resolve_error_locale(accept_language: str | None) -> Literal["en-US", "zh-CN"]`
  - `get_error_request_context() -> ErrorRequestContext`
  - `build_error_detail(...) -> ErrorDetail`
  - `build_problem_response(...) -> JSONResponse`
  - `pydantic_loc_to_field_path(loc: tuple[Any, ...]) -> str`
  - `json_safe_error_value(value: Any) -> Any`
- Keep route-side dynamic values explicit. Do not let a catalog template inspect raw request bodies.
- If adding YAML files under `packages/i18n/errors.en-US.yaml` and `packages/i18n/errors.zh-CN.yaml`, load them through a typed wrapper and add tests that fail when keys drift. If this is too heavy, a typed Python dict in `error_catalog.py` is acceptable for this story, but document that Story 8.B.5 will externalize/enforce cross-language lint.
- Do not add PyYAML as a new app dependency. It is present in `uv.lock` indirectly, but `apps/solver-orchestrator/pyproject.toml` does not declare it. Prefer typed Python constants in this story unless adding YAML is paired with an explicit dependency decision.
- Use `json.loads(ErrorResponse(...).model_dump_json())` or equivalent to guarantee JSON-safe body values; avoid returning Pydantic/Decimal/datetime objects directly inside error bodies.
- For `next_action_url`, prefer stable URLs:
  - algorithms/schema docs: `https://api.opticloud.cn/v1/algorithms`
  - forecast algorithms: `https://api.opticloud.cn/v1/algorithms?task_type=forecast`
  - docs root: `https://docs.opticloud.cn/errors/<slug>`
  - self-audit: existing `https://console.opticloud.cn/admin/self-audit/<ticket_id>`
  - top-up/upgrade only when billing/credits/rate-limit paths exist.
- For not-found resources, use `path.optimization_id`, `path.prediction_id`, or `path.voucher_id`, and avoid revealing whether another user owns the resource.
- For voucher expiry, use status 410 with `field_path="path.voucher_id"`, redacted or compact voucher value, and a next action that points to reproducibility/rerun documentation rather than implying the same voucher can be revived.
- For explicit platform/config 500 such as a missing LP catalog entry, prefer `field_path="$"` and `value="[omitted]"`; `errors[]` may be present for operator diagnostics, but user-facing next action should be omitted or docs-only.
- For idempotency key conflicts, returning the raw idempotency key is not useful; prefer `"[redacted]"` unless an existing test requires the exact key.
- Keep broad `except Exception` only where already used for safe input parsing or 3.6 helper failure boundaries; do not expand broad catches in business logic.

### Previous Story Intelligence

- Story 3.6 established that response-boundary hardening should fail closed without exposing `_system`, stack traces, API keys, user ids, or billing ids.
- Story 3.6 also showed that idempotency and historical-row replay semantics are fragile; this story must not change prediction failed-row replay or completed prediction response content.
- Story 2.5/2.6/2.8 already created precise error fields for `fallback_chain[i]`, provider routing, and unaudited self algorithms. Reuse and catalog these paths instead of replacing them with generic `"$"`.
- Recent solver stories validate focused tests first, adjacent suites second, full solver-orchestrator suite third, then mypy/pre-commit/diff-check.

### Project Structure Notes

- Keep backend route code in `apps/solver-orchestrator/src/solver_orchestrator/`.
- Keep canonical shared schemas in `packages/shared-py/opticloud_shared/schemas/errors.py`; do not duplicate Pydantic schema classes in routes.
- Keep tests under `apps/solver-orchestrator/tests/`, `packages/python-sdk/tests/`, or `packages/shared-py/tests/`.
- Follow Python `snake_case.py` file naming and existing async pytest patterns.
- Do not create sibling worktree directories. All implementation happens inside `D:\优化预测网站`.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Error catalog breaks existing tests that expect English by default | Missing/unsupported Accept-Language defaults to `en-US`; add explicit zh-CN tests. |
| Some route errors still return empty `errors[]` | Add static/contract guard and route sweep tests for representative endpoints. |
| Pydantic validation handler leaks raw body or huge matrices | Compact/redact values and cap serialized value size. |
| Reusing old shared helper emits `next_action` | Keep using canonical `ErrorResponse` with `next_action_url`; add test rejecting `next_action`. |
| i18n catalog becomes another unsynchronized source | Tests assert every used key exists in both supported languages; later Story 8.B.5 can add ESLint/static enforcement. |
| Prediction 3.6 compact status semantics regress | Explicit AC6 and regression tests keep failed-row 200 payload unchanged. |
| Over-broad 5xx changes hide platform errors | Scope mandatory `errors[]` to explicit actionable route errors; unknown platform 500 remains sanitized. |

## Definition of Done

- Story file has passed three pre-implementation reviews and all resulting patches are applied.
- Solver-orchestrator explicit 4xx/402/403/404/409/422/429 errors return non-empty `errors[]` and `next_action_url`.
- Request validation errors are converted from FastAPI/Pydantic default 422 into FG1.3 RFC 7807 shape.
- `Accept-Language` selects single-language `title/detail` from a single catalog source.
- Python SDK/Web/UI consumer contracts continue preserving `errors[]` and `next_action_url`.
- Existing optimization/prediction success paths and 3.6 compact failed-row semantics remain unchanged.
- AC9 quality gates pass or any inability to run them is documented.
- Sprint status and Dev Agent Record are updated.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-27 - Story moved to in-progress after three pre-implementation review rounds; starting RED/GREEN implementation for RFC 7807 error detail contract.
- 2026-05-27 - RED phase confirmed: new Story 3.7 tests failed on missing `error_catalog`, `application/problem+json`, app-level validation/HTTPException handlers, and auth detail redaction.
- 2026-05-27 - GREEN phase: added catalog/context/response builder modules, app middleware + exception handlers, and delegated route `_rfc7807_error` to shared builder.
- 2026-05-27 - Focused Story 3.7 tests passed: `uv run pytest apps/solver-orchestrator/tests/test_rfc7807_errors_detail.py -q` -> 8 passed.
- 2026-05-27 - Adjacent solver regression passed: provider routing + unaudited self + prediction submission -> 54 passed.
- 2026-05-27 - Full solver-orchestrator suite passed: 234 passed.
- 2026-05-27 - Python SDK error tests passed with explicit SDK source path: 5 passed.
- 2026-05-27 - Shared-py tests passed: 32 passed.
- 2026-05-27 - `uv run mypy apps packages` passed.
- 2026-05-27 - 504 timeout wrapper boundary fixed to preserve `application/problem+json`; timeout/sync-async focused regression passed (34 passed).
- 2026-05-27 - Post-implementation code review found one patch item: caller-provided `ErrorDetail` values could bypass sensitive header redaction. Added builder-level normalization and idempotency-key redaction regression.
- 2026-05-27 - Final validation after code-review patch passed: solver-orchestrator suite 235 passed; Python SDK error tests 5 passed; shared-py tests 32 passed; mypy/pre-commit/diff-check passed.
- 2026-05-27 - PR #82 CI lint failed on `ContextVar` mutable default plus test import ordering after SDK path bootstrap. Patched request-context default to `None`, moved SDK source path bootstrap into solver test `conftest.py`, and reran local lint/regression checks successfully.

### Completion Notes List

- Added solver-orchestrator error catalog with zh-CN/en-US titles/details, stable slugs, remediation hint keys, default field paths, and next_action_url defaults.
- Added request-local error context and shared problem response builder that emits `application/problem+json` with `type/title/status/detail/errors/instance/request_id/trace_id/next_action_url`.
- Added app-level handlers for `RequestValidationError` and `HTTPException`, including redacted Authorization failures and Pydantic loc-to-field-path conversion.
- Converted route `_rfc7807_error` into a delegating wrapper, preserving existing route call sites while filling missing error details and next actions through the catalog.
- Added Story 3.7 tests for catalog completeness, Accept-Language, FastAPI validation errors, auth errors, prediction validation, 501 actionability, SDK consumption, and `next_action` drift guard.
- Full solver-orchestrator suite and focused SDK/shared-py/mypy checks passed before post-implementation code review.
- Post-implementation code review completed; sensitive header redaction now applies to both generated and caller-supplied `ErrorDetail` objects.
- Final validation passed after post-review patch: full backend tests, SDK/shared-py tests, mypy, pre-commit, and diff-check.
- CI lint follow-up completed: `ContextVar` now avoids mutable defaults, and SDK path bootstrap no longer forces test-file E402 exceptions.

### File List

- `_bmad-output/stories/3-7-rfc7807-errors-detail.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/error_catalog.py`
- `apps/solver-orchestrator/src/solver_orchestrator/error_context.py`
- `apps/solver-orchestrator/src/solver_orchestrator/error_responses.py`
- `apps/solver-orchestrator/src/solver_orchestrator/main.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/conftest.py`
- `apps/solver-orchestrator/tests/test_rfc7807_errors_detail.py`

### Change Log

- 2026-05-27 - Initial Story 3.7 draft created from Epics/PRD/Architecture/UX, current solver-orchestrator error code, Python SDK, Web client, UI ErrorBoundary, and Story 3.6 learnings.
- 2026-05-27 - Applied Story Review Round 1 data-consistency patches for sprint status, auth/catalog HTTPException coverage, per-key next_action_url defaults, Authorization redaction, and RFC 7807/RFC 9457 naming boundary.
- 2026-05-27 - Applied Story Review Round 2 function/dependency patches for non-route response builder, context propagation, circular import avoidance, and no undeclared PyYAML dependency.
- 2026-05-27 - Applied Story Review Round 3 boundary/closure patches for 410 voucher expiry, 501/504 actionable boundaries, explicit 500 handling, and static drift guard scope.
- 2026-05-27 - Implemented Story 3.7 RFC 7807 error catalog, response builder, exception handlers, route delegation, and focused contract tests.
- 2026-05-27 - Addressed post-implementation code review finding for sensitive header redaction and marked Story 3.7 done after final validation.
- 2026-05-27 - Addressed PR #82 CI lint feedback for `ContextVar` default and test import ordering; validation re-run locally before pushing.

## Story Review Round 1 - Data Consistency (2026-05-27)

### Findings

- [x] [Patch] Story status said `ready-for-dev`, but sprint status still had `3-7-rfc7807-errors-detail: backlog`. Updated sprint status to `ready-for-dev`.
- [x] [Patch] AC3 required 401/403 coverage, but the draft only constrained route builder calls. AC2/AC5/Dev Notes now explicitly cover `HTTPException` raised by auth and catalog routes so those do not keep FastAPI's raw `{"detail": ...}` shape.
- [x] [Patch] Default `next_action_url` was described by broad status class, which could create inaccurate links. AC1 now scopes defaults to explicit solver-orchestrator error keys.
- [x] [Patch] Authorization error `value` handling was underspecified. AC3 now requires `"[redacted]"` for Authorization and avoids revealing key validity details.
- [x] [Patch] The story referenced RFC 7807 without noting current standards drift. AC1 now clarifies that the project remains locked to PRD/RFC 7807 field names even though RFC 9457 supersedes RFC 7807 externally.

### Result

Round 1 passed after patches. Story status, HTTP status coverage, `next_action_url` defaults, auth redaction, and Problem Details naming are now data-consistent.

## Story Review Round 2 - Function / Dependency Consistency and Drift (2026-05-27)

### Findings

- [x] [Patch] The draft allowed `main.py` exception handlers to reuse `routes.py::_rfc7807_error`, which would create a circular import because `main.py` already imports routers from `routes.py`. AC2 and Dev Notes now require a non-route `error_responses.py` builder.
- [x] [Patch] `_rfc7807_error` as the "single builder" was ambiguous: keeping route helper logic plus app handler logic could drift. AC2 now permits only a thin route wrapper that delegates to the shared builder.
- [x] [Patch] Accept-Language propagation was underspecified for nested helpers. AC4/Task 1/Dev Notes now require shared request context or explicit plumbing with tests for nested helper paths.
- [x] [Patch] YAML catalog guidance could accidentally rely on transitive PyYAML. Dev Notes now state PyYAML is not a declared solver-orchestrator dependency and typed Python constants are preferred unless dependency ownership is explicit.

### Result

Round 2 passed after patches. Error response ownership, import boundaries, request context propagation, and dependency usage are now aligned with the current FastAPI service structure.

## Story Review Round 3 - Boundary / Edge Cases / Closure (2026-05-27)

### Findings

- [x] [Patch] The draft omitted 410 Gone even though rerun voucher expiry uses `HTTP_410_GONE`. AC3/AC5/Dev Notes now require deterministic 410 voucher-expired error details and next action.
- [x] [Patch] The draft grouped 5xx/501/504 together, which could imply user-remediable links for platform 500s. AC3/Dev Notes now separate actionable 501/504 from sanitized explicit 500 platform/config errors.
- [x] [Patch] Static guard language could falsely flag variable names, comments, SDK helpers, or docs containing `next_action`. AC8 now scopes the ban to serialized route/error response keys named `next_action`.
- [x] [Patch] Voucher expiry next action could imply reviving an expired voucher. Dev Notes now require reproducibility/rerun documentation, not a misleading revive flow.

### Result

Round 3 passed after patches. Status-code coverage, 410 expiry semantics, platform-error boundaries, and static drift guard scope are now closed before implementation.
