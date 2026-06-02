---
story_key: 8-a-5-audit-log-table
baseline_commit: 3c10beace3cc3839aba62a221250b9bd5c44a125
epic_num: 8
story_num: A.5
epic_name: Public Status + Audit + Vuln Response
status: code-review
priority: High
type: UI audit log table and Console history page
created_by: bmad-create-story
created_at: 2026-06-02
sources:
  - _bmad-output/planning/epics.md (Epic 8.A / Story 8.A.5)
  - _bmad-output/planning/architecture.md (Console-History; audit-log; Trust-Forward)
  - _bmad-output/stories/8-a-4-user-audit-logs.md
  - packages/shared-ts/openapi/auth-service.json (/v1/me/audit-logs)
  - apps/web/src/lib/api.ts
  - apps/web/src/app/console/billing/invoices/page.tsx
  - apps/web/src/app/console/data-exports/page.tsx
  - packages/ui/src/index.ts
  - packages/ui/src/components/InvoiceCard/index.tsx
  - packages/ui/src/components/BudgetAlertCard/index.a11y.test.tsx
---

# Story 8.A.5 - AuditLogTable Component

Status: code-review

## Story

**作为** 已登录 Console 用户，
**我希望** 在 Console 中用可筛选、可翻页、可访问的审计日志表格查看自己的账号活动，
**从而** 可以快速核对 API Key、登录、数据导出、风控、账单等关键动作，并确认没有异常活动。

## Context

Story 8.A.4 已交付后端契约：`GET /v1/me/audit-logs` 在 `auth-service` 中实现，使用 Bearer access JWT、只返回当前用户自己的 `audit_logs` 行，支持 `from`、`to`、`limit`、`cursor`，响应 shape 为 `{ items, next_cursor, limit, from, to }`。每个 item 包含 `id`、`actor`、`action`、`resource_type`、`resource_id`、`metadata`、`ip_address`、`user_agent`、`created_at`，且后端已递归脱敏 metadata。

本 story 是 8.A.4 的前端消费层：在 `packages/ui` 新增可复用 `AuditLogTable`，在 `apps/web` 增加 Console 审计日志页面与 API helper。不得改后端契约，不得新增 audit-service/api-gateway，不得引入 TanStack Table/Virtual 等新运行时依赖；当前数据规模用语义化表格、横向滚动和分页足够。

## Scope

1. 在 `packages/ui` 新增 `AuditLogTable` 组件，负责表格、筛选控件、分页控件、loading/error/empty 状态和 metadata 安全摘要展示。
2. 在 `apps/web/src/lib/api.ts` 新增 `listMyAuditLogs(jwtAccess, filters)` 类型与 helper，调用 `AUTH_SERVICE_URL /v1/me/audit-logs`。
3. 新增 Console 页面 `/console/audit-logs`，读取 `sessionStorage.jwt_access`；未登录时跳转 `/auth/login`。
4. 页面默认加载最近 30 天审计日志，使用后端返回的 `from`/`to` 作为当前窗口事实来源。
5. 时间筛选用 `datetime-local` 控件收集用户输入，提交时转换为 timezone-aware ISO string；清空筛选时回到后端默认窗口。
6. 表格筛选包括 action/resource/actor/search 的前端筛选，仅作用于当前已加载页；`from`/`to` 是服务端筛选。
7. 翻页使用后端 `next_cursor`；切换时间筛选时必须清空 cursor 与已加载页，避免混合窗口。
8. UI 必须防止长 action/resource/user_agent/metadata 值撑破布局；移动端至少通过 `overflow-x-auto` 或等价布局保持内容可访问。
9. metadata 展示必须保持后端 `[REDACTED]`，并做前端防御性 masking：若 metadata 键或字符串值疑似 secret/token/password/authorization/cookie/webhook/raw payload，不展示原值。
10. 添加 UI 单元测试、UI a11y 测试、Web API helper 测试和 Console 页面测试。
11. 更新 `packages/ui` 导出；如修改 package manifest，只允许把新 a11y 测试加入已有 `test:a11y` 脚本，不允许新增依赖。
12. 完成 post-implementation code review、本地 gates、GitHub CI/PR/merge/remote branch cleanup/local main sync 后，才允许标记 story/sprint `done`。

## Out Of Scope

- 修改 `GET /v1/me/audit-logs` 后端行为、字段、分页算法、默认窗口或 redaction 规则。
- 新建或实现 `apps/api-gateway`、独立 `audit-service`、audit export worker、audit partition、90d+ 异步导出。
- 管理员跨用户审计搜索、企业审计导出、PIPL 数据导出复用。
- 8.A.6 vuln submission、8.A.7 J9、8.B AIGC/rate-limit/RFC7807 面板、8.C provider routing history。
- 引入 TanStack Table、虚拟列表、状态管理库或新的运行时依赖。
- 在浏览器存储 raw audit payload、JWT、API key、metadata 原始快照或下载文件。

## Acceptance Criteria

1. `packages/ui` 导出 `AuditLogTable` 及其公开类型，组件可被 `apps/web` 直接消费。
2. `AuditLogTable` 是 presentation-only：不直接 fetch、不读取 storage、不做路由跳转；父组件拥有数据加载和鉴权。
3. 表格使用 semantic `<table>`、`<thead>`、`<tbody>`、`<th>`；主要区域有明确 `aria-label` 或 `aria-labelledby`。
4. 表格列至少展示时间、动作、actor、resource、来源 IP、user agent、metadata 摘要。
5. `created_at`、`from`、`to` 等无效日期不会渲染 `Invalid Date` 或 `NaN`。
6. 空值字段显示 `-` 或等价占位，不让 `null`/`undefined` 泄露到 UI。
7. 长 action/resource/user_agent/metadata 值会换行或被约束，不造成布局重叠。
8. `metadata` 的对象/数组/标量能稳定摘要；循环对象不是 API 合法值，可不支持，但普通 JSON 嵌套必须可展示。
9. metadata 摘要最多展示有限条目，避免单行超长 JSON 压垮表格。
10. metadata 中的 `[REDACTED]` 原样保留。
11. 若 metadata 键名匹配 `api_key`、`key_hash`、`token`、`authorization`、`jwt`、`password`、`secret`、`cookie`、`webhook_url`、`provider_payload`、`raw_request`、`raw_response`、`otp` 等敏感模式，前端显示 `[REDACTED]`。
12. 若 metadata 字符串值匹配 Bearer token、`sk-...` API key、JWT-like token 或 obvious secret-like value，前端显示 `[REDACTED]`。
13. `ip_address` 和 `user_agent` 可显示，但不能参与 metadata secret bypass。
14. 筛选控件包含服务端时间范围 `from`/`to`，提交时触发父组件回调并清空 cursor。
15. 筛选控件包含至少一个前端文本搜索或 action/resource 筛选，能按当前页的 action、actor、resource_type、resource_id、metadata 摘要过滤。
16. 筛选控件均有可见 label 或 `aria-label`，可键盘操作。
17. loading 状态用 `role="status"` 或等价方式暴露给辅助技术。
18. error 状态显示父组件传入的错误信息，不吞掉 RFC7807 归一化后的标题/详情。
19. empty 状态区分“无审计日志”和“当前筛选无结果”。
20. pagination 展示当前页计数，并在没有 `next_cursor` 时禁用“下一页”。
21. 点击“下一页”时调用父组件 `onLoadNext(nextCursor)`；组件不得自行拼 URL。
22. `/console/audit-logs` 未发现 `sessionStorage.jwt_access` 时跳转 `/auth/login`。
23. `/console/audit-logs` 有 JWT 时调用 `listMyAuditLogs(jwt, { limit, from, to })`，默认不发送 action/resource/user_id 参数。
24. 页面用 `Authorization: Bearer <jwt_access>` 调用 8.A.4 端点；不得使用 API key。
25. 页面提交时间筛选时重新请求第一页，并不会把旧 `cursor` 与新 `from`/`to` 混用。
26. 页面点击下一页时使用后端 `next_cursor` 请求下一页，并追加或替换为明确的下一页视图；不得伪造 cursor。
27. API helper 只发送非空的 `from`、`to`、`limit`、`cursor` query 参数。
28. API helper 使用 `AUTH_SERVICE_URL` 和现有 `request<T>()` 错误处理，不复制一套错误归一化。
29. 页面能展示 loading、error、empty、data、filtered-empty 和 pagination 状态。
30. Console 导航中能从现有 Console 页面发现“审计日志”入口，且不破坏已有账单、数据导出、Provider、Repro 链接。
31. `packages/ui` focused tests 覆盖 rendering、filtering、pagination callback、metadata masking、empty/error/loading。
32. `packages/ui` a11y test 对默认数据、error/empty、loading 状态无 axe violations。
33. `apps/web` API helper tests 覆盖 query 参数、Authorization header、cursor、空值省略、错误透传。
34. `apps/web` page tests 覆盖未登录跳转、初始加载、时间筛选重载、下一页、错误状态、导航入口、不会写入 sensitive storage。
35. `packages/ui/package.json` 不新增 dependency；如更新 `test:a11y`，只追加 `AuditLogTable/index.a11y.test.tsx`。
36. 本地 gates 至少通过：UI focused tests、UI a11y focused test、UI typecheck、Web focused tests、Web typecheck、`git diff --check`。
37. Post-implementation code review completed；所有 Patch/Decision-needed findings 已修复或明确记录。
38. GitHub CI passes，PR merged，remote branch deleted，local `main` synced 后，story 和 sprint status 才能标记 `done`。

## Tasks / Subtasks

- [x] T1: Add UI AuditLogTable contract and tests (AC: 1-21, 31-32, 35)
  - [x] Create `packages/ui/src/components/AuditLogTable/index.tsx`.
  - [x] Define exported item/filter/props types aligned with 8.A.4 response fields.
  - [x] Implement semantic table, filter controls, pagination controls, loading/error/empty states.
  - [x] Implement defensive metadata summary and masking without mutating props.
  - [x] Add `index.test.tsx` and `index.a11y.test.tsx`.
  - [x] Export component/types from `packages/ui/src/index.ts`.
  - [x] Add the new a11y test to `packages/ui/package.json` `test:a11y` script without adding dependencies.

- [x] T2: Add Web audit logs API helper (AC: 23-28, 33)
  - [x] Add audit log response/filter interfaces in `apps/web/src/lib/api.ts`.
  - [x] Add `listMyAuditLogs(jwtAccess, filters)` using existing `request<T>()` and `AUTH_SERVICE_URL`.
  - [x] Add focused `apps/web/src/lib/audit-logs.test.ts`.

- [x] T3: Add Console audit logs page (AC: 22-30, 34)
  - [x] Create `apps/web/src/app/console/audit-logs/page.tsx`.
  - [x] Reuse existing Console auth pattern: `sessionStorage.jwt_access`, redirect to `/auth/login` when absent.
  - [x] Load initial page, handle server time-window filters, and handle `next_cursor` pagination.
  - [x] Add Console navigation link to “审计日志” while preserving existing links.
  - [x] Add `page.test.tsx` covering auth, loading/data/error/empty/filter/pagination/nav/storage behavior.

- [ ] T4: Gates, review, and GitHub sync (AC: 36-38)
  - [x] Run focused UI tests and a11y tests.
  - [x] Run UI typecheck.
  - [x] Run focused Web tests.
  - [x] Run Web typecheck.
  - [x] Run `git diff --check`.
  - [x] Run post-implementation adversarial code review and apply fixes.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, sync local `main`.
  - [ ] Mark story and sprint status `done` only after merge/sync.

## Dev Notes

### Backend Contract From 8.A.4

- Endpoint: `GET /v1/me/audit-logs`.
- Auth: `Authorization: Bearer <access JWT>` only; API key Bearer is rejected by backend.
- Query params: `from`, `to`, `limit`, `cursor`.
- Response: `{ items, next_cursor, limit, from, to }`.
- Item fields: `id`, `actor`, `action`, `resource_type`, `resource_id`, `metadata`, `ip_address`, `user_agent`, `created_at`.
- Ordering: backend returns `created_at DESC, id DESC`.
- Cursor is opaque and bound to original `(from, to, limit, user_id)` by 8.A.4; UI must treat it as an opaque token.
- Metadata is backend-redacted, but UI still applies defense-in-depth masking before rendering metadata values.

### Existing Frontend Patterns

- `apps/web/src/lib/api.ts` keeps `request<T>()` internal and existing auth helpers pass `headers: { Authorization: \`Bearer ${jwtAccess}\` }`.
- Console pages use `"use client"`, `useRouter`, `sessionStorage.getItem("jwt_access")`, and redirect to `/auth/login` when missing.
- Existing Console pages use constrained `max-w-6xl`, border-bottom header, `StatusCard`, and simple Tailwind layout rather than nested dashboard cards.
- `packages/ui` components are presentation-owned, exported from `packages/ui/src/index.ts`, and covered with Vitest/Testing Library; a11y coverage uses `jest-axe`.
- `packages/ui` already has `lucide-react`; use it for button icons if adding icons.

### Route Decision

- Use `/console/audit-logs` rather than `/console/history`. Architecture names the page direction “Console-History”, but the URL should be explicit to avoid future collision with provider routing history or reproducibility history pages.

### Filter Semantics

- `from`/`to` are server filters and require a new first-page request.
- action/resource/actor/search are local filters over the currently loaded page. Do not add server query params that 8.A.4 does not support.
- Changing `from`/`to` must clear any stored `next_cursor` and page rows.
- `datetime-local` values are local browser times; convert with `new Date(value).toISOString()` and avoid passing naive strings to the backend.

### Security And Privacy Guardrails

- Never write audit rows, metadata, JWT, API key, cursor, or downloaded audit data to `localStorage`/`sessionStorage`; only read existing `jwt_access`.
- Do not display raw values from sensitive metadata keys even if a backend regression returns them.
- Do not display raw Authorization headers, API keys, JWTs, OTPs, webhook URLs, provider payloads, raw requests/responses, cookies, or password-like fields.
- Metadata display is for inspection, not export; no copy/download action in this story.

### Suggested Commands

```powershell
pnpm --filter @opticloud/ui test -- src/components/AuditLogTable/index.test.tsx
pnpm --filter @opticloud/ui test -- src/components/AuditLogTable/index.a11y.test.tsx
pnpm --filter @opticloud/ui typecheck
pnpm --filter @opticloud/web test -- src/lib/audit-logs.test.ts src/app/console/audit-logs/page.test.tsx
pnpm --filter @opticloud/web typecheck
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- `AuditLogTable` is reusable from `packages/ui`, semantic, accessible, responsive, and defensively masks metadata.
- `/console/audit-logs` consumes 8.A.4 exactly, with JWT session auth, server time filters, opaque cursor pagination, and local current-page filters.
- No backend contract, dependency, gateway, audit-service, export, or unrelated Console feature drift.
- Focused UI/Web tests, a11y test, typechecks, and diff-check pass.
- Post-implementation code review completed and findings resolved.
- GitHub CI passes, PR is merged, remote branch deleted, local `main` synced.
- Story and sprint status are updated to `done` only after GitHub sync is complete.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-a-5-audit-log-table`.
- Baseline commit: `3c10beace3cc3839aba62a221250b9bd5c44a125`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base `customize.toml` files for `bmad-create-story`, `bmad-dev-story`, and `bmad-code-review`, found no team/user overrides, and found no `project-context.md`.
- Story creation used Epic 8.A / Story 8.A.5, Architecture Console-History direction, 8.A.4 final contract, OpenAPI `UserAuditLogsResponse`, current `apps/web` API helper pattern, current Console auth/page patterns, and current `packages/ui` component/a11y patterns.
- Implementation started; story and sprint status moved to in-progress.
- T1 focused UI tests: `pnpm --filter @opticloud/ui test -- src/components/AuditLogTable/index.test.tsx` -> 5 passed.
- T1 focused UI a11y tests: `pnpm --filter @opticloud/ui test -- src/components/AuditLogTable/index.a11y.test.tsx` -> 3 passed.
- T2 focused Web API tests: `pnpm --filter @opticloud/web test -- src/lib/audit-logs.test.ts` -> 3 passed.
- T3 focused Console audit page tests: `pnpm --filter @opticloud/web test -- src/app/console/audit-logs/page.test.tsx` -> 6 passed.
- T3 affected Console nav regressions: billing invoices 9 passed; data exports 6 passed; providers 5 passed; chat 2 passed.
- Pre-review local gates: UI focused tests/a11y -> 8 passed; UI typecheck -> passed; Web focused tests -> 9 passed; Web typecheck initially failed because `UserAuditLogItem.ip_address`/`user_agent` were incorrectly optional vs OpenAPI required nullable fields; fixed and reran -> passed; `git diff --check` -> passed.
- Post-implementation code review found 1 patch finding: stale initial audit-log response could overwrite a newer time-filter response. Fixed with request sequence guard and regression test.
- Final local gates after review fix: UI focused tests/a11y -> 8 passed; UI typecheck -> passed; Web focused tests -> 10 passed; Web typecheck -> passed; `git diff --check` -> passed.

### Completion Notes List

- Story created for AuditLogTable and Console audit log history page.
- Completed pre-implementation adversarial review round 1 and revised route/backend/session boundaries.
- Completed pre-implementation adversarial review round 2 and revised cursor/filter/time/metadata consistency requirements.
- Completed pre-implementation adversarial review round 3 and revised dependency/a11y/gate requirements.
- Implementation started; status moved to in-progress.
- Implemented `AuditLogTable` component with semantic table, filters, pagination callbacks, defensive metadata masking, focused tests, and a11y coverage.
- Added `listMyAuditLogs` Web API helper with typed 8.A.4 response contract, Authorization header, query param filtering, and focused tests.
- Added `/console/audit-logs` page with JWT session auth, server time filters, opaque cursor pagination, error/empty/loading states, storage safety test, and Console nav entries on existing Console pages.
- Completed post-implementation code review; fixed stale response overwrite risk with latest-request sequencing.

### File List

- `_bmad-output/stories/8-a-5-audit-log-table.md`
- `_bmad-output/stories/sprint-status.yaml`
- `packages/ui/package.json`
- `packages/ui/src/components/AuditLogTable/index.tsx`
- `packages/ui/src/components/AuditLogTable/index.test.tsx`
- `packages/ui/src/components/AuditLogTable/index.a11y.test.tsx`
- `packages/ui/src/index.ts`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/audit-logs.test.ts`
- `apps/web/src/app/console/audit-logs/page.tsx`
- `apps/web/src/app/console/audit-logs/page.test.tsx`
- `apps/web/src/app/console/billing/invoices/page.tsx`
- `apps/web/src/app/console/data-exports/page.tsx`
- `apps/web/src/app/console/providers/page.tsx`
- `apps/web/src/app/console/repro/page.tsx`
- `apps/web/src/app/console/chat/page.tsx`

## Change Log

- 2026-06-02 - Story draft created for AuditLogTable and Console audit logs page.
- 2026-06-02 - Pre-implementation review round 1 completed; revised route, backend contract, and JWT session boundaries.
- 2026-06-02 - Pre-implementation review round 2 completed; revised cursor reset, time conversion, and metadata masking requirements.
- 2026-06-02 - Pre-implementation review round 3 completed; revised dependency, a11y, local gates, and GitHub closure requirements; story marked ready-for-dev.
- 2026-06-02 - Implementation started; story and sprint status moved to in-progress.
- 2026-06-02 - Implemented AuditLogTable, Web API helper, Console audit logs page, Console nav entries, focused tests, and a11y coverage.
- 2026-06-02 - Completed post-implementation code review; fixed stale request overwrite; local gates passed and story moved to code-review pending GitHub sync.

## Post-Implementation Code Review

### Review Layers

- Blind Hunter: reviewed diff for frontend-only scope, dependency drift, data leakage, navigation regressions, and API contract drift.
- Edge Case Hunter: reviewed async request ordering, cursor/time-filter reset, metadata masking recursion, loading/error/empty transitions, and storage side effects.
- Acceptance Auditor: checked implementation against AC 1-38 in this story.

### Findings And Fixes

1. [Review][Patch][Fixed] `/console/audit-logs` did not guard against stale responses. If the default initial request was still in flight and the user applied a time filter, the older response could arrive later and overwrite the filtered result, violating data consistency and cursor/time-window closure.
   - Fix: added a monotonic request sequence in `AuditLogsPage`; only the latest request can update state. Added a regression test where the initial request resolves after the filtered request and is ignored.

### Review Result

- Decision-needed: 0
- Patch findings: 1 fixed
- Deferred: 0
- Dismissed: 0

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary Issues: Route, Backend Contract, And Auth Identity

Findings:

1. The planning note names “Console-History” but does not specify a URL. A generic `/console/history` route could collide with later provider routing history or repro history surfaces.
2. “filter” could tempt implementation to add unsupported backend query params such as `action` or `resource_type`, which would drift from the 8.A.4 contract.
3. Existing Console pages read `sessionStorage.jwt_access`; using API keys or localStorage fallback would violate 8.A.4’s user-session contract.

Revisions applied:

- Chose explicit route `/console/audit-logs` and documented it as the Console-History implementation.
- Split filters into server `from`/`to` and current-page local search/action/resource filters.
- Added ACs requiring JWT access token usage only, no API key, and no unsupported backend params.

### Round 2 - Drift Issues: Cursor/Filter Consistency, Timezones, And Metadata Integrity

Findings:

1. If the page keeps `next_cursor` while changing `from`/`to`, the backend will reject cursor drift, but the UX would still produce confusing errors.
2. Browser `datetime-local` values are naive local strings; sending them directly would violate 8.A.4’s timezone-aware ISO requirement.
3. Backend redaction exists, but UI should still protect users if future audit writers accidentally include sensitive metadata values.

Revisions applied:

- Added requirements to clear cursor/page rows on server time-filter changes.
- Added explicit local-time to `toISOString()` conversion guidance.
- Added defense-in-depth metadata key/value masking ACs and tests.

### Round 3 - Dependency Consistency, A11y Closure, And Delivery Gates

Findings:

1. Architecture references table/virtualization concepts elsewhere, but current package manifests do not include TanStack Table/Virtual. Adding them for a bounded cursor table would be dependency drift.
2. A new UI component with filters and table semantics needs focused a11y coverage, not just render tests.
3. The required lifecycle must not mark `done` after local review; it must wait for GitHub CI, merge, branch cleanup, and local `main` sync.

Revisions applied:

- Added no-new-runtime-dependency AC and allowed only `test:a11y` script inclusion in package manifest.
- Added dedicated `AuditLogTable` axe coverage for default, loading, error, and empty states.
- Added GitHub closure AC and final status gating.
