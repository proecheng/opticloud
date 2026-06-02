---
story_key: 8-a-4-user-audit-logs
baseline_commit: 1244d34c79718b2a206336b1aef0116932ccb335
epic_num: 8
story_num: A.4
epic_name: Public Status + Audit + Vuln Response
status: code-review
priority: High
type: User audit log query endpoint
created_by: bmad-create-story
created_at: 2026-06-02
sources:
  - _bmad-output/planning/epics.md (Epic 8.A / Story 8.A.4)
  - _bmad-output/planning/prd.md (FR O3; Usage & Audit endpoint surface)
  - _bmad-output/planning/architecture.md (C3 v1 audit_logs PG table; v1 no standalone audit-service)
  - _bmad-output/stories/8-a-3-24h-postmortem.md
  - apps/api-gateway/.gitkeep
  - apps/auth-service/src/auth_service/models.py
  - apps/auth-service/src/auth_service/routes.py
  - apps/auth-service/src/auth_service/schemas.py
  - apps/auth-service/src/auth_service/data_export.py
  - infra/local-init/01-schema.sql
  - apps/auth-service/tests/conftest.py
---

# Story 8.A.4 - 用户审计日志查询

Status: code-review

## Story

**作为** 已登录用户，
**我希望** 通过 `GET /v1/me/audit-logs?from=...&to=...` 查询自己的审计日志，
**从而** 可以核对账号、API Key、冻结/申诉、数据导出等关键活动是否由自己或系统按预期发生，并且不会看到其他用户或内部敏感数据。

## Context

FR O3 要求用户能查看 own activity audit logs。Architecture C3 定义 v1 审计为 Postgres `audit_logs` 单表，v2 末再拆独立 audit 库；同时架构文本提到 `api-gateway` 提供 audit query endpoint。但当前仓库中的 `apps/api-gateway` 只有 `.gitkeep`，没有可运行 FastAPI 服务；可运行认证与审计写入均在 `apps/auth-service`，并且现有 OpenAPI 只生成 `auth-service` 与 `capability-registry`。

因此本 story 的可交付实现落在 `auth-service`：新增同契约的 authenticated `GET /v1/me/audit-logs` 端点，直接查询现有 `audit_logs` 表。该端点使用产品层面的 `/v1/me/...` 路径，保持 future gateway 可转发的 URL 契约；不新建 `audit-service`，不脚手架 `api-gateway`，不做 8.A.5 的 AuditLogTable 组件。

## Scope

1. 在 `apps/auth-service` 暴露 `GET /v1/me/audit-logs`，使用 Bearer access JWT 鉴权并强制 active user。
2. 查询只返回 `audit_logs.user_id == current_user.id` 的行，不接受 `user_id` 查询参数。
3. 支持 `from`、`to` ISO 8601 UTC 时间过滤，默认时间窗为最近 30 天。
4. 支持 bounded pagination：`limit` 默认 50，最大 100；`cursor` 为服务端生成的不透明游标。
5. 排序稳定且确定：`created_at DESC, id DESC`；下一页使用同一复合键继续。
6. 返回用户安全字段：id、actor、action、resource_type、resource_id、metadata、ip_address、user_agent、created_at。
7. `metadata` 与 string 值递归脱敏明显 secret/token/key/password/authorization/webhook/cookie/otp/provider payload 等敏感内容。
8. 生成并提交更新后的 `packages/shared-ts/openapi/auth-service.json`，防止 OpenAPI drift。
9. 添加 focused backend tests 覆盖认证、隔离、时间窗、分页、cursor、脱敏、active-user 禁止访问。
10. 保持 API Key Bearer 不在本 story 的认证范围内；现有 `_resolve_user_from_jwt` 明确仅解析 JWT，本 endpoint 不引入第二种主体。
11. Cursor 必须绑定原始 `from`、`to` 和 `limit` 查询语义；使用 cursor 时若请求方改变这些参数，必须返回 422，而不是混合两个不同窗口。
12. 保持 schema 命名和 API 路径与 OpenAPI 生成器兼容；不要新增包依赖、不要修改 CI 过滤器，除非 drift check 证明必须。

## Out Of Scope

- 新建或实现 `apps/api-gateway` 服务、gateway routing/middleware、限流、idempotency、Dramatiq actor。
- 新建独立 `audit-service`、拆分 audit DB、audit partition、物化视图、90d+ 异步导出。
- 为其他 service 补全审计写入；本 story 只查询现有 `audit_logs`。
- 实现 Story 8.A.5 的 AuditLogTable、Console history 页面、虚拟列表、TanStack Table。
- 管理员审计搜索、跨用户审计查询、企业级导出、PIPL 数据导出包复用。
- O4 vuln submission、O6 rate limit、O7 next_action_url、8.B AIGC filter、Epic 9 governance。
- 暴露 raw JWT、API key、OTP、Webhook URL、cookie、provider payload、raw request/response、internal hostname、private operator notes。

## Acceptance Criteria

1. `GET /v1/me/audit-logs` requires `Authorization: Bearer <access JWT>` and returns 401 for missing, malformed, invalid, refresh-token, or expired credentials.
1a. API Key Bearer credentials are rejected with 401 until a later gateway/auth middleware story explicitly supports API-key user sessions.
2. The endpoint rejects deleted, merged, or frozen accounts consistently with existing active-user enforcement and returns 403.
3. The endpoint never accepts or trusts a `user_id` query parameter.
4. The endpoint returns only rows whose `audit_logs.user_id` equals the authenticated user id.
5. Rows with `user_id IS NULL`, including system tombstone/completion rows, are not returned by the self-service endpoint.
6. Cross-user audit rows are never returned, even when resource ids or metadata mention the current user.
6a. Audit rows whose `resource_id` equals the current user but whose `user_id` belongs to another user are not returned.
7. Default query window is last 30 days in UTC when `from` and `to` are omitted.
8. `from` filters rows with `created_at >= from`.
9. `to` filters rows with `created_at <= to`.
10. `from > to` returns 422 with a clear validation error.
11. Naive datetimes or non-ISO datetimes are rejected rather than interpreted in local time.
12. `limit` defaults to 50, must be 1..100, and rejects 0, negative, and >100 values.
13. Results are ordered by `created_at DESC, id DESC`.
14. Pagination is deterministic when multiple rows share the same `created_at`.
15. A response with more rows available includes a non-empty opaque `next_cursor`.
16. Supplying `cursor` returns the next page using the same ordering and does not duplicate or skip rows.
17. Invalid, malformed, expired-format, or drifted cursor values return 422 and do not broaden the query.
17a. A cursor generated for one `(from, to, limit)` query cannot be reused with a different `from`, `to`, or `limit`.
18. Cursor payloads are not plain user-editable JSON in the URL; they must be encoded opaquely enough for clients to treat them as tokens.
19. The response shape is stable: `{ items, next_cursor, limit, from, to }`.
20. Each item includes `id`, `actor`, `action`, `resource_type`, `resource_id`, `metadata`, `ip_address`, `user_agent`, and `created_at`.
21. UUID, IP, and datetime values serialize as JSON strings.
22. `metadata` is recursively JSON-safe and never exposes Python/SQLAlchemy objects.
23. `metadata` keys matching secret/token/key/hash/password/authorization/jwt/cookie/otp/pepper/webhook/provider payload patterns are replaced with `[REDACTED]`.
24. `metadata` string values containing `Bearer ...`, `sk-...`, JWT-like tokens, or secret-like values are redacted.
24a. Redaction applies recursively to nested dicts/lists and to non-string scalar values under sensitive keys.
24b. Redaction does not mutate the stored `audit_logs.metadata` value in the database.
25. User-visible `ip_address` and `user_agent` may be returned because they are direct account activity signals, but must not be used to bypass metadata redaction.
26. The endpoint performs a bounded indexed query against `idx_audit_logs_user_id_created_at`; no unbounded full-table scan path is introduced.
27. No new runtime dependency is added to auth-service.
28. OpenAPI generation includes `GET /v1/me/audit-logs` and the new response schemas in `packages/shared-ts/openapi/auth-service.json`.
28a. `scripts/check_openapi_drift.py` passes after regeneration.
29. Focused tests cover own logs, cross-user isolation, `user_id IS NULL`, time filters, invalid time ranges, pagination/tie ordering, cursor validation, metadata redaction, no-auth 401, and inactive account 403.
30. Local gates pass: focused auth-service tests, auth-service test suite or relevant auth route subset, OpenAPI generation/drift check, and `git diff --check`.
31. Implementation record includes post-implementation code review findings and fixes.
32. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done`.

## Tasks / Subtasks

- [x] T1: Define audit-log response contract and helpers (AC: 7-25, 27-28)
  - [x] Add Pydantic response models for audit log item/list response.
  - [x] Add strict UTC datetime parsing/validation for `from` and `to`.
  - [x] Add opaque cursor encode/decode based on `(created_at, id)`.
  - [x] Add recursive metadata redaction helper local to auth-service online response code.

- [x] T2: Implement `GET /v1/me/audit-logs` (AC: 1-6, 12-19, 26)
  - [x] Register route on a router that yields product path `/v1/me/audit-logs`.
  - [x] Reuse existing JWT and active-user checks; do not create a parallel auth path.
  - [x] Build SQLAlchemy query scoped by current user, time window, cursor, and bounded limit.
  - [x] Fetch `limit + 1` rows to compute `next_cursor`.

- [x] T3: Add focused backend tests (AC: 1-30)
  - [x] Add `apps/auth-service/tests/test_audit_logs.py`.
  - [x] Cover auth failure, own rows, cross-user isolation, null-user exclusion, active-user forbidden states.
  - [x] Cover API-key Bearer rejection and resource-id-only non-ownership.
  - [x] Cover default/from/to window, invalid datetimes, invalid range, limit validation.
  - [x] Cover deterministic pagination with duplicate timestamps, invalid cursor, and cursor reuse with changed filters.
  - [x] Cover metadata redaction for nested keys, list members, secret-like string values, and stored metadata non-mutation.

- [x] T4: OpenAPI and gates (AC: 28-32)
  - [x] Regenerate `packages/shared-ts/openapi/auth-service.json`.
  - [x] Verify no package/dependency manifests changed unless the final diff proves they are required.
  - [x] Run focused auth tests.
  - [x] Run auth-service regression subset/full suite as feasible.
  - [x] Run OpenAPI drift check and `git diff --check`.
  - [x] Run post-implementation code review, fix findings, and record result.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, sync local `main`.
  - [ ] Mark story and sprint status `done` only after merge/sync.

## Dev Notes

### Service Boundary

- `apps/api-gateway` is currently only `.gitkeep`; do not scaffold it in this story.
- Implement endpoint in `apps/auth-service` while preserving the product URL `/v1/me/audit-logs`.
- Existing `router = APIRouter(prefix="/v1/auth")` is not a good path fit for `/v1/me`; add a narrow `me_router = APIRouter(prefix="/v1/me", tags=["me"])` in `routes.py` and include it in `main.py`.
- Reuse `_resolve_active_user_from_jwt` so deleted, merged, and frozen users behave like API Key endpoints.
- Do not reuse API-key verification from solver/auth integration tests; FR O3 is a logged-in user self-service endpoint, not machine-to-machine API-key auth.

### Existing Data Model

- ORM model: `AuditLog` in `apps/auth-service/src/auth_service/models.py`.
- Table: `audit_logs` in `infra/local-init/01-schema.sql`.
- Columns: `id`, `user_id`, `actor`, `action`, `resource_type`, `resource_id`, `metadata`, `ip_address`, `user_agent`, `created_at`.
- Existing index: `idx_audit_logs_user_id_created_at ON audit_logs(user_id, created_at DESC)`.
- Existing audit writers include signup, OTP login, API key create/revoke, notification preferences, account deletion, account merge, frozen appeals, data export, risk freeze/unfreeze.

### Query Semantics

- Default `from` should be `now - 30 days`; default `to` should be request-time `now`.
- Treat all accepted datetimes as timezone-aware and normalize to UTC.
- Query should use `AuditLog.user_id == user_id`, `AuditLog.created_at >= from_dt`, `AuditLog.created_at <= to_dt`, optional cursor predicate, and `order_by(AuditLog.created_at.desc(), AuditLog.id.desc())`.
- Cursor predicate for next page: rows where `created_at < cursor_created_at OR (created_at == cursor_created_at AND id < cursor_id)`.
- Fetch `limit + 1`; return only first `limit`.
- Cursor should carry `created_at`, `id`, normalized `from`, normalized `to`, and `limit`; decoding must verify all non-cursor query parameters match before applying the predicate.
- Use a deterministic test clock by seeding explicit `created_at` values in tests; do not rely on wall-clock sleeps.

### Redaction Guidance

- Use the spirit of `data_export.sanitize_export_value` but keep online audit response helper local and explicitly tested.
- Redact keys matching secret material: `api_key`, `key_hash`, `token`, `token_hash`, `authorization`, `jwt`, `password`, `pepper`, `otp`, `secret`, `cookie`, `webhook_url`, `provider_payload`, `raw_request`, `raw_response`.
- Redact string values matching obvious bearer/API key/JWT/secret token patterns.
- Return a sanitized copy only; never assign the sanitized metadata back to the ORM row.
- Preserve benign metadata such as labels, scope arrays, rule codes, format, package byte counts, and timestamp strings.

### Cross-Story Boundaries

- Story 8.A.4 owns backend query contract and OpenAPI schema.
- Story 8.A.5 owns UI `AuditLogTable` component and Console history display.
- Story 5.C.3/5.C.4 owns PIPL data export packages; do not route this endpoint through export workers.
- Epic 9/G11 owns later audit-log SLA hardening, partitions, and 90d+ async export.

### Suggested Commands

```powershell
uv run pytest apps/auth-service/tests/test_audit_logs.py
uv run pytest apps/auth-service/tests/test_api_keys_routes.py apps/auth-service/tests/test_notification_preferences.py apps/auth-service/tests/test_account_deletion.py apps/auth-service/tests/test_account_merge.py apps/auth-service/tests/test_data_exports.py apps/auth-service/tests/test_risk_freeze.py apps/auth-service/tests/test_frozen_appeals.py
uv run python scripts/generate_openapi.py
uv run python scripts/check_openapi_drift.py
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- `GET /v1/me/audit-logs` satisfies FR O3 using current auth-service/audit_logs v1 architecture.
- Query is own-user scoped, bounded, deterministic, time-filtered, cursor-paginated, and metadata-redacted.
- Endpoint contract is present in generated OpenAPI.
- No unrelated package, CI, gateway, or frontend table dependency drift is introduced.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-a-4-user-audit-logs`.
- Baseline commit: `1244d34c79718b2a206336b1aef0116932ccb335`.
- Story creation used Epic 8.A / PRD O3, Architecture C3/O3, current `apps/api-gateway` placeholder state, current auth-service audit model/routes/schemas/tests, and previous Story 8.A.3 lifecycle pattern.
- Customization resolver script was absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base `bmad-create-story/customize.toml`, found no team/user overrides, and found no `project-context.md`.
- Focused audit tests after implementation: `uv run pytest apps/auth-service/tests/test_audit_logs.py` -> 10 passed.
- OpenAPI generated: `uv run python scripts/generate_openapi.py` -> auth-service spec generated with 25 paths.
- OpenAPI drift check after generation: `uv run python scripts/check_openapi_drift.py` -> passed.
- Auth-service related regression subset: `uv run pytest apps/auth-service/tests/test_api_keys_routes.py apps/auth-service/tests/test_notification_preferences.py apps/auth-service/tests/test_account_deletion.py apps/auth-service/tests/test_account_merge.py apps/auth-service/tests/test_data_exports.py apps/auth-service/tests/test_risk_freeze.py apps/auth-service/tests/test_frozen_appeals.py` -> 72 passed.
- Static checks before review fix: `uv run ruff check ...` found import ordering only; fixed with `ruff --fix`. `uv run mypy ...` found `from_` constructor alias mismatch; fixed with `UserAuditLogsResponse.model_validate({"from": ...})`.
- Full auth-service suite before review fix: `uv run pytest apps/auth-service/tests` -> 107 passed.
- Post-implementation code review found 2 patch findings: cursor was not bound to current user; redaction over-redacted `webhook_url_configured`.
- Focused audit tests after review fix: `uv run pytest apps/auth-service/tests/test_audit_logs.py` -> 10 passed.
- Static gates after review fix: `uv run ruff check apps/auth-service/src/auth_service/routes.py apps/auth-service/src/auth_service/schemas.py apps/auth-service/src/auth_service/main.py apps/auth-service/tests/test_audit_logs.py` -> passed; `uv run mypy apps/auth-service/src/auth_service/routes.py apps/auth-service/src/auth_service/schemas.py apps/auth-service/src/auth_service/main.py` -> passed.
- OpenAPI drift after review fix: `uv run python scripts/check_openapi_drift.py` -> passed.
- Final auth-service suite: `uv run pytest apps/auth-service/tests` -> 107 passed.
- Final diff-check: `git diff --check` -> passed.
- Story and sprint status moved to `code-review` after local gates and post-implementation review; final `done` remains gated on GitHub CI, PR merge, remote branch cleanup, and local `main` sync.

### Completion Notes List

- Story created for user audit log query endpoint.
- Completed pre-implementation adversarial review round 1 and revised story boundaries.
- Completed pre-implementation adversarial review round 2 and revised cursor/time/redaction consistency requirements.
- Completed pre-implementation adversarial review round 3 and marked story ready for development.
- Implementation started; story and sprint status moved to in-progress.
- Implemented authenticated `GET /v1/me/audit-logs` in auth-service with own-user scoping, strict UTC time windows, signed/bound cursor pagination, metadata redaction, and generated OpenAPI contract.
- Added focused audit log route tests for auth, isolation, time filters, limits, pagination, cursor drift/user binding, redaction, and inactive accounts.
- Completed post-implementation code review; fixed cursor user binding and safe metadata over-redaction.

### File List

- `_bmad-output/stories/8-a-4-user-audit-logs.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/auth-service/src/auth_service/main.py`
- `apps/auth-service/src/auth_service/routes.py`
- `apps/auth-service/src/auth_service/schemas.py`
- `apps/auth-service/tests/test_audit_logs.py`
- `packages/shared-ts/openapi/auth-service.json`

## Change Log

- 2026-06-02 - Story draft created for FR O3 user audit log query endpoint.
- 2026-06-02 - Pre-implementation review round 1 completed; revised auth/path/service-scope boundaries.
- 2026-06-02 - Pre-implementation review round 2 completed; revised cursor binding, time-window, and redaction non-mutation requirements.
- 2026-06-02 - Pre-implementation review round 3 completed; dependency/gate/GitHub closure requirements checked and story marked ready-for-dev.
- 2026-06-02 - Implementation started; story and sprint status moved to in-progress.
- 2026-06-02 - Implemented `/v1/me/audit-logs`, audit response schemas, signed cursor helpers, metadata redaction, focused tests, and OpenAPI contract.
- 2026-06-02 - Completed post-implementation code review; fixed cursor user binding and safe metadata key over-redaction; local gates passed and story moved to code-review pending GitHub sync.

## Post-Implementation Code Review

### Review Layers

- Blind Hunter: reviewed raw diff for auth/session boundary, query scope, route registration, OpenAPI drift, dependency drift, and accidental gateway/UI scope.
- Edge Case Hunter: reviewed pagination tie ordering, cursor drift/reuse, inactive users, null-user rows, metadata redaction recursion, and stored metadata integrity.
- Acceptance Auditor: checked implementation against AC 1-32 in this story.

### Findings And Fixes

1. [Review][Patch][Fixed] Cursor payload was signed and bound to `(from, to, limit)`, but not to `user_id`. Cross-user cursor reuse would not leak rows because the query remained user-scoped, but it could alter the second user's pagination anchor and hide rows unexpectedly.
   - Fix: included `user_id` in cursor payload, verified decoded cursor user matches the current JWT user, and added a cross-user cursor regression test.
2. [Review][Patch][Fixed] Metadata redaction matched `webhook_url_configured` because it contained `webhook`, removing a safe boolean that tells users whether a webhook destination was configured without exposing the URL.
   - Fix: added an explicit safe-key allowlist for `webhook_url_configured` and extended redaction tests.

### Review Result

- Decision-needed: 0
- Patch findings: 2 fixed
- Deferred: 0
- Dismissed: 0

## Pre-Implementation Adversarial Reviews

### Round 1 - Auth Boundary, Service Boundary, And Tenant Isolation

Findings:

1. The initial story said "Bearer" but did not explicitly exclude API Key Bearer credentials. Existing auth-service user-session endpoints use JWT-only helpers, while API keys are machine credentials used by solver-facing flows. Allowing API keys here would silently expand scope and may expose user audit history through long-lived keys.
2. The architecture says `api-gateway` owns the query endpoint, but the repo has no runnable gateway. The draft correctly placed implementation in auth-service, but needed a sharper note that this does not authorize scaffolding gateway or audit-service during implementation.
3. User isolation must be based solely on `audit_logs.user_id`, not `resource_id` or metadata. Some admin/system rows may reference a user as resource while being owned by another actor or having `user_id = NULL`.

Revisions applied:

- Added explicit JWT-only/API-key rejection AC and test requirement.
- Added resource-id-only non-ownership AC.
- Strengthened service boundary notes to prevent gateway/audit-service/UI drift.

### Round 2 - Pagination, Time Filtering, And Data Consistency

Findings:

1. The initial cursor contract encoded the last row but did not require the cursor to be bound to the original `from`, `to`, and `limit`. A client could reuse a cursor with a broader window and accidentally mix result sets, creating skips/duplicates or broader data exposure.
2. The draft required redaction but did not explicitly prevent sanitized metadata from being written back into the ORM object. Mutating stored audit evidence would violate audit integrity.
3. Tests relying on request-time defaults can be flaky around `now`; seeded timestamps and explicit windows are needed for pagination and boundary assertions.

Revisions applied:

- Added cursor binding to normalized `from`, `to`, and `limit`.
- Added ACs and tests for drifted cursor parameters.
- Added metadata non-mutation AC and deterministic timestamp test guidance.

### Round 3 - Dependency Drift, Scope Closure, And Delivery Gates

Findings:

1. OpenAPI generation is part of this endpoint's contract, but the initial story only said "generate OpenAPI"; it did not explicitly require the drift checker to pass.
2. The story touches backend schemas and route registration, so package/CI drift must be guarded. No new dependency should be required for cursor encoding or redaction.
3. The UI table story follows immediately after 8.A.4; dependency or frontend helper drift could accidentally pre-implement 8.A.5.

Revisions applied:

- Added explicit OpenAPI drift-check AC.
- Added no-dependency/package manifest verification task.
- Reconfirmed no AuditLogTable/frontend table scope in Definition of Done and delivery gates.
