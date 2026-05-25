---
story_key: 1-12-j7-fraud-freeze-vertical-slice
epic_num: 1
story_num: 1.12
epic_name: Account & Identity
status: done
priority: High (J7 v1 必上；承接 Story 1.5 / 1.10 / 1.11，补冻结申诉闭环)
sizing: L (~10-14 hours; auth-service appeal lifecycle + admin review + Web appeal/status + tests)
type: implementation + security + ux + test
created_by: bmad-create-story
created_at: 2026-05-25
sources:
  - [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1319-1324]
  - [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1343-1347]
  - [Source: D:/优化预测网站/_bmad-output/planning/prd.md:595-612]
  - [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1440-1443]
  - [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:184]
  - [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:1616-1620]
  - [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:2497-2530]
  - [Source: D:/优化预测网站/_bmad-output/stories/1-5-risk-control-freeze.md]
  - [Source: D:/优化预测网站/_bmad-output/stories/1-10-language-switch-zh.md]
  - [Source: D:/优化预测网站/_bmad-output/stories/1-11-geo-anomaly-risk.md]
  - [Source: D:/优化预测网站/apps/auth-service/src/auth_service/risk.py]
  - [Source: D:/优化预测网站/apps/auth-service/src/auth_service/admin_routes.py]
  - [Source: D:/优化预测网站/apps/auth-service/src/auth_service/routes.py]
  - [Source: D:/优化预测网站/apps/web/src/app/auth/login/page.tsx]
dependencies:
  upstream:
    - 1-5-risk-control-freeze (done) - `risk_rules` / `risk_flags` / `users.is_frozen` / admin unfreeze
    - 1-10-language-switch-zh (done) - Web locale helper 与 `Accept-Language`
    - 1-11-geo-anomaly-risk (done) - `geo_anomaly` evidence-only 风险证据
  contextual:
    - 1-3-api-keys-crud-complete (done) - API Key ownership and revoke patterns
    - 1-7-account-merge-proposal (backlog) - 完整账号合并系统未实现；本 story 只做 J7 最小恢复/合并提议闭环
  downstream:
    - 3-7-rfc7807-errors-detail - 后续可统一冻结错误面板与 `next_action_url`
    - 8-a-4-user-audit-logs - 后续可把申诉/复核事件展示给用户
---

# Story 1.12 - J7 风控冻结申诉 Vertical Slice

Status: done

## User Story

**As** a frozen account user,
**I want** a clear appeal form, status tracking link, and review/recovery decision,
**so that** a risk freeze is transparent, reviewable, and recoverable without support guesswork.

## Why

J7 要求第 4 次注册被风控拦截后，用户能在友好提示中 1 分钟自助申诉，并通过团队规模进入 48h 人工复核或 auto-score 复审。当前代码的可执行底座是 Story 1.5 在 signup/login 后把既有 `users` 账户标记为 `is_frozen=true`，而不是为不存在的预注册身份建立申诉。因此本 story 把 J7 v1 vertical slice 收敛为“已存在账户被冻结后的申诉闭环”。现有系统已经有 `users.is_frozen`、`risk_rules`、`risk_flags`、管理员 unfreeze，以及 Story 1.11 的 `geo_anomaly` 风险证据；缺口是用户可进入的申诉、状态追踪、管理员复核、通过后解冻、维持原判后的最小合并/恢复提议。

Story 1.7 仍在 backlog，所以本 story 不能假设完整 account merge 平台已存在。本 story 的目标是 J7 vertical slice：用 auth-service 内最小数据模型和 Web 页面完成“冻结提示 -> 申诉 -> 复审 -> 解冻或最小合并提议 -> 恢复访问”的闭环，并把完整账号合并工具作为后续 Story 1.7 的扩展面。

## Out Of Scope

- 完整多账号合并平台、跨账号数据迁移、账单/credits 余额迁移、Starter ¥39 支付升级自动化
- 新建平行风控系统或新风险事件表；风险证据必须复用 `risk_flags` / `risk_rules` / `users.risk_score`
- 外部客服系统、邮件供应商、真实邮件发送；v1 返回可测试 tracking URL/token
- 管理员 RBAC / admin-user 表；沿用 Story 1.5 `X-Admin-Secret`
- 设备指纹采集、VPN 识别、24h 调用计数、支付方式复用检测的全量实现
- 删除/篡改历史 `risk_flags`；复核只写新 audit log 和 appeal 状态
- 被删除账户恢复；PIPL 删除流程优先于申诉流程
- 不存在 `users` 记录的预注册身份申诉；v1 只支持可用 phone+email 定位到的冻结账户

## Acceptance Criteria

1. `infra/local-init/09-risk-appeals.sql` idempotently creates a `risk_appeals` table for J7 with UUID PK, `user_id` FK, `status`, `reason`, `evidence JSONB NOT NULL DEFAULT '{}'`, `team_size INTEGER NOT NULL CHECK (team_size >= 1)`, `review_mode`, `decision`, `decision_reason`, `tracking_token_hash`, `tracking_token_expires_at`, `merge_offer JSONB NOT NULL DEFAULT '{}'`, `created_at`, `updated_at`, and `decided_at`, plus indexes for `(user_id, status)`, `tracking_token_hash`, and pending review.
2. Auth-service ORM/Pydantic schemas expose the appeal lifecycle with snake_case fields and no camelCase drift. Allowed statuses are `pending`, `approved`, `rejected`, `merge_offered`, and `merge_accepted`; allowed review modes are `auto_score` and `manual_48h`; allowed decisions are `approved`, `maintained`, `rejected`, and `merge_accepted`.
3. A frozen user can submit an appeal without a JWT via phone+email verification fields already known to the user: `POST /v1/auth/risk-appeals` accepts `phone`, `email`, `reason`, optional `evidence`, and `team_size`. It only creates an appeal when the matching user exists, is not deleted, and `users.is_frozen=true`; otherwise it returns RFC7807-style 403/404 without leaking another user's risk details.
4. Duplicate active appeals are idempotent per user: if the same frozen user already has `status IN ('pending','merge_offered')`, the endpoint returns the existing appeal status and rotates to a fresh tracking URL/token without inserting a second active row. Token rotation invalidates the previous token hash.
5. Submitting an appeal writes an `audit_logs` row `risk.appeal.submitted` and returns `appeal_id`, `status`, `review_mode`, `submitted_at`, `sla_due_at`, and `tracking_url`. `team_size >= 3` uses `manual_48h` with `sla_due_at = created_at + 48h`; `team_size <= 2` uses deterministic `auto_score`.
6. Auto-score review is local and deterministic. It must not call an LLM or external service. It bases the decision on existing `risk_flags`, `users.risk_score`, and user evidence fields. Passing auto-score approves and unfreezes the user; failing auto-score moves the appeal to `merge_offered` with a minimal `merge_offer`.
7. Tracking endpoint `GET /v1/auth/risk-appeals/status?token=...` returns appeal status, review mode, SLA, decision summary, visible risk evidence summary, and optional `merge_offer`; invalid/expired/replaced tokens return 404 or 401 without exposing user existence.
8. Admin endpoints under `/v1/admin/risk-appeals` reuse `X-Admin-Secret`: list pending/manual appeals, inspect one appeal with risk flag summaries, decide approve/reject. Approve uses a shared unfreeze helper also used by Story 1.5 direct admin unfreeze, and writes `risk.appeal.approved` plus `user.unfreeze`; reject/maintain moves to `merge_offered` and writes `risk.appeal.merge_offered`.
9. The minimal merge offer lets the user accept through `POST /v1/auth/risk-appeals/{appeal_id}/merge-offer/accept` using the tracking token. Accepting sets `status='merge_accepted'`, `decision='merge_accepted'`, final decision fields, unfreezes the user, writes `risk.appeal.merge_accepted`, and returns a localized next action pointing to login. Accept is idempotent for an already accepted offer and never migrates other accounts, credits, jobs, or payments.
10. Existing OTP request/login frozen checks return a RFC7807-style `application/problem+json` 403 with `type`, `title`, `detail`, and `next_action_url="/auth/appeal"` so Web can send frozen users directly into the appeal flow. Route return annotations may include `JSONResponse`, but success response models must stay unchanged.
11. Web adds `/auth/appeal` with localized zh-CN/en-US copy, a compact appeal form, and a status panel reachable from the returned tracking URL. Login frozen errors show a focused CTA to `/auth/appeal` only when the RFC7807 payload has the freeze `type` or `next_action_url`; other 403 cases such as age gate keep their current copy.
12. Web status UI covers pending/manual 48h, approved/unfrozen, merge_offered with accept action, rejected/final, invalid token, network error, and locale switching. It uses existing locale helpers and shared UI components; no browser `alert()` / `confirm()`.
13. Security boundaries are covered: tracking tokens are high-entropy random values and only hashes are stored; status responses never include raw phone/email, JWTs, API keys, or full `risk_flags.metadata` values; users cannot inspect or decide another user's appeal.
14. Tests cover auth-service migration/model, appeal submission, duplicate active idempotency plus old-token invalidation, auto-score approve, auto-score merge offer, manual 48h pending/list/detail/decision, admin approve/unfreeze, admin reject/merge offer, idempotent merge accept, token invalid/expired, deleted/non-frozen users, risk evidence summary using 1.5/1.11 data, Web frozen login CTA, appeal form/status/merge accept UI, zh-CN/en-US copy, and existing auth/web regressions.

## Tasks / Subtasks

- [x] Task 1: Add appeal persistence and schemas (AC: 1, 2)
  - [x] Add `infra/local-init/09-risk-appeals.sql`
  - [x] Add `RiskAppeal` ORM model to `apps/auth-service/src/auth_service/models.py`
  - [x] Add request/response schemas in `apps/auth-service/src/auth_service/schemas.py`
  - [x] Wire migration into auth-service CI schema setup and path filter

- [x] Task 2: Implement public appeal lifecycle (AC: 3, 4, 5, 6, 7, 9, 13)
  - [x] Add appeal routes under existing `/v1/auth`
  - [x] Verify phone+email to locate the user without issuing JWT for frozen accounts
  - [x] Generate/hash tracking tokens and return only raw token in response URL
  - [x] Rotate tracking token on duplicate active submission and invalidate the old token
  - [x] Build deterministic auto-score review and minimal merge-offer creation
  - [x] Implement token status and idempotent merge-offer accept endpoints
  - [x] Write audit log events for submit, auto decision, merge offer, and merge accept

- [x] Task 3: Implement admin review endpoints (AC: 8, 13)
  - [x] Add `/v1/admin/risk-appeals` list/detail endpoints
  - [x] Add approve/reject decision endpoint using existing `require_admin_secret`
  - [x] Ensure manual 48h appeals remain pending until explicit admin decision, with status page showing `sla_due_at`
  - [x] Reuse existing unfreeze semantics and preserve `risk_flags`
  - [x] Return summarized risk evidence only

- [x] Task 4: Improve frozen auth errors (AC: 10)
  - [x] Replace plain frozen `HTTPException` in OTP request/login with RFC7807 JSON response
  - [x] Include `next_action_url="/auth/appeal"`
  - [x] Preserve existing deleted/age-gate/login behavior

- [x] Task 5: Add Web appeal and status experience (AC: 11, 12)
  - [x] Add API client types/functions for risk appeal submit/status/merge accept
  - [x] Add `/auth/appeal` page and tracking-token status panel
  - [x] Update `/auth/login` frozen error state with CTA
  - [x] Add zh-CN/en-US messages
  - [x] Use existing `StatusCard`, `RFC7807Panel`, `ConfirmationModal`, and locale provider patterns

- [x] Task 6: Tests and validation (AC: 14)
  - [x] Add `apps/auth-service/tests/test_risk_appeals.py`
  - [x] Extend frozen login tests for RFC7807 `next_action_url`
  - [x] Add Web tests for login CTA, appeal form/status, merge accept, and locale copy
  - [x] Run auth-service tests, web tests/typecheck, UI tests/typecheck if touched, ruff/mypy relevant scopes, and `git diff --check`

- [x] Task 7: Story tracking and release hygiene
  - [x] Complete Dev Agent Record, File List, and Change Log
  - [x] Move story/sprint through `in-progress`, `code-review`, and `done`
  - [ ] Commit, push branch, and open/sync PR

## Dev Notes

- Reuse Story 1.5 risk infrastructure. Do not create `appeal_risk_flags`, `fraud_events`, or a second risk score source.
- `risk_appeals` is process state, not risk evidence. It should reference `users.id` and summarize evidence from `risk_flags`.
- Story 1.7 is backlog. Keep merge support minimal: a structured offer and accept action that unfreezes access. Do not move data, payments, credits, solver jobs, or API keys across accounts.
- Keep `risk_flags` immutable. Admin approval/unfreeze does not delete flags; it records decision/audit entries.
- Public appeal lookup uses phone+email only to identify the frozen account for appeal submission. It must not return detailed risk evidence until the caller has a valid tracking token.
- Tracking token storage must follow guardian-confirmation style: store SHA-256 hash, return raw token once, compare hashes. Use `secrets.token_urlsafe(32)` or stronger.
- Only one active appeal per user should exist for `pending` or `merge_offered`; completed terminal statuses (`approved`, `rejected`, `merge_accepted`) may remain as history.
- Duplicate active submissions should rotate the tracking token, update `tracking_token_expires_at`, and make the prior token unusable.
- Request validation should bound `team_size` to a practical range such as 1-500 and keep `reason` non-empty with a maximum length. Store arbitrary user evidence only under an allowlisted JSON object shape, not raw form blobs.
- Auto-score must be deterministic and testable. Suggested v1 policy:
  - `team_size >= 3` -> `manual_48h`
  - `team_size <= 2` -> `auto_score`
  - approve auto-score when reason length is meaningful, evidence has an allowed field, and the user has fewer than 2 enabled distinct risk rule flags after excluding disabled evidence-only `geo_anomaly`
  - otherwise produce `merge_offered`
- Manual 48h appeals must not auto-approve in this story. They stay `pending` until admin decision; the SLA is shown to user/admin and covered by tests.
- Visible evidence summaries should include rule code, label, source, created_at, and safe reason/category fields. Do not return raw `metadata` wholesale.
- Use existing `admin_routes.require_admin_secret`; do not add a second admin auth mechanism.
- Extract a shared async helper such as `_unfreeze_user_with_audit(session, user_id, actor, reason, metadata)` inside `admin_routes.py` or a small auth-service module. Both `admin_unfreeze_user` and appeal approval/merge accept must call it so audit semantics do not fork.
- Frozen OTP/login errors should be RFC7807-compatible JSONResponse, not bare string details, so Web can render consistent next action.
- Web login must not treat every 403 as frozen. Use `next_action_url === "/auth/appeal"` or a stable frozen error type/title to select the appeal CTA.
- Web `/auth/appeal` must work without JWT because frozen users cannot log in.
- Locale behavior must follow Story 1.10: API client sends `Accept-Language`; Web copy comes from `apps/web/messages/*.json`.
- Keep UI compact and task-focused. This is an operational recovery flow, not a marketing page.

### Project Structure Notes

- Migration: `infra/local-init/09-risk-appeals.sql`
- Auth models/schemas/routes: `apps/auth-service/src/auth_service/models.py`, `schemas.py`, `routes.py`, `admin_routes.py`
- Auth tests: `apps/auth-service/tests/test_risk_appeals.py`, `test_login_routes.py`
- Web API client: `apps/web/src/lib/api.ts`
- Web pages/tests: `apps/web/src/app/auth/appeal/page.tsx`, `apps/web/src/app/auth/appeal/page.test.tsx`, `apps/web/src/app/auth/login/page.tsx`, `page.test.tsx`
- Locale copy: `apps/web/messages/zh-CN.json`, `apps/web/messages/en-US.json`
- CI: `.github/workflows/ci.yml`

### References

- [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1319-1324]
- [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1343-1347]
- [Source: D:/优化预测网站/_bmad-output/planning/prd.md:595-612]
- [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1440-1443]
- [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:184]
- [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:2497-2530]
- [Source: D:/优化预测网站/_bmad-output/stories/1-5-risk-control-freeze.md]
- [Source: D:/优化预测网站/_bmad-output/stories/1-10-language-switch-zh.md]
- [Source: D:/优化预测网站/_bmad-output/stories/1-11-geo-anomaly-risk.md]

## Three-Round Story Review

### Round 1: Data Consistency Review

Scope: `risk_appeals` schema, status/decision enums, user identity, team size, evidence JSON, tracking token, and freeze state.

Findings and fixes:

- [x] Status lifecycle gap: initial ACs had no terminal status for accepting a merge offer. Fixed by adding `merge_accepted` to allowed statuses and requiring merge accept to set `status='merge_accepted'` and `decision='merge_accepted'`.
- [x] User identity drift: initial user story mentioned registration-blocked users, but current code can only identify existing `users` and freeze through `users.is_frozen`. Fixed by scoping v1 to frozen existing accounts and making pre-user appeal out of scope.
- [x] JSON shape ambiguity: `evidence` and `merge_offer` did not define JSONB defaults. Fixed by requiring non-null JSONB defaults and allowlisted evidence shape.
- [x] `team_size` data ambiguity: review routing depends on team size, but no numeric bounds were stated. Fixed by requiring `team_size >= 1` in DB and practical request validation bounds.
- [x] Decision/status mismatch risk: reject/maintain, approve, and merge accept could drift. Fixed by explicitly listing allowed decisions separate from allowed statuses.

Round 1 result: PASS after story corrections.

### Round 2: Function Consistency / Drift Review

Scope: existing auth routes, admin routes, RFC7807 helper, Web API client, login error mapping, and shared UI components.

Findings and fixes:

- [x] Admin unfreeze drift risk: appeal approval could duplicate direct unfreeze logic and diverge from Story 1.5 audit behavior. Fixed by requiring a shared unfreeze helper used by both direct admin unfreeze and appeal approval/merge accept.
- [x] Frozen 403 overmatching risk: current Web login treats any 403 except age gate as frozen. Fixed by requiring frozen CTA selection from `next_action_url="/auth/appeal"` or stable frozen error type/title only.
- [x] Response contract regression risk: changing OTP/login success response models would break Story 1.2. Fixed by allowing `JSONResponse` only on frozen error paths and preserving existing success response models.
- [x] UI component drift risk: appeal flow could add browser dialogs or bespoke modal behavior. Fixed by requiring existing `StatusCard`, `RFC7807Panel`, and `ConfirmationModal` patterns.
- [x] Admin auth drift risk: a second admin auth mechanism would conflict with Story 1.5. Fixed by requiring reuse of `require_admin_secret`.

Round 2 result: PASS after story corrections.

### Round 3: Boundary / Closure Review

Scope: duplicate submissions, token lifecycle, manual 48h path, merge-offer closure, invalid/deleted/non-frozen accounts, and end-to-end recovery.

Findings and fixes:

- [x] Duplicate active appeal gap: only duplicate `pending` was covered, leaving `merge_offered` duplicate submissions ambiguous. Fixed by defining one active appeal per user for `pending` or `merge_offered`.
- [x] Token replacement risk: returning a fresh token without invalidating the old one would expand access. Fixed by requiring token rotation to replace the stored hash and invalidate previous tokens.
- [x] Manual 48h non-closure risk: manual appeals could sit pending with no explicit admin path. Fixed by requiring list/detail/decision admin endpoints and status page SLA visibility; no auto-approval is implied.
- [x] Merge accept repeat risk: repeated accept calls could duplicate audit/unfreeze effects. Fixed by requiring idempotent accept behavior for already accepted offers.
- [x] Test closure gap: old-token invalidation, manual 48h decision, and idempotent merge accept were not explicit test requirements. Fixed by adding them to AC 14.

Round 3 result: PASS after story corrections; story is ready for dev implementation.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- Story authoring started on 2026-05-25.
- `uv run ruff check apps/auth-service/src/auth_service apps/auth-service/tests` — passed.
- `uv run mypy apps/auth-service/src/auth_service` — passed; note only existing pyproject unused tests override notice.
- `uv run pytest apps/auth-service/tests -q` — 59 passed.
- `pnpm --dir apps/web test` — 16 files / 79 tests passed.
- `pnpm --dir apps/web typecheck` — passed.
- `git diff --check` — passed.

### Completion Notes List

- Created Story 1.12 from sprint backlog and scoped it as a self-contained J7 vertical slice because Story 1.7 remains backlog.
- Completed three-round story review before implementation.
- Added `risk_appeals` persistence with active-appeal uniqueness, token hash tracking, status/decision constraints, and CI schema wiring.
- Implemented public frozen-account appeal submit/status/merge-accept flow with phone+email lookup, token rotation, deterministic auto-score, minimal merge offer, and safe evidence summaries.
- Implemented admin appeal list/detail/decision endpoints using existing `X-Admin-Secret`; approval and merge accept reuse a shared unfreeze audit helper.
- Converted frozen OTP/login errors to RFC7807 with `next_action_url="/auth/appeal"` while preserving age-gate/deleted behavior.
- Added localized Web `/auth/appeal` form/status flow and login CTA, using existing locale and UI component patterns.
- Completed post-implementation code review; fixed missing appeal `audit_logs.resource_id`, added DB active-appeal uniqueness, corrected ORM partial indexes, and improved invalid-token UX.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/stories/1-12-j7-fraud-freeze-vertical-slice.md`
- `_bmad-output/stories/sprint-status.yaml`
- `infra/local-init/09-risk-appeals.sql`
- `apps/auth-service/src/auth_service/appeals.py`
- `apps/auth-service/src/auth_service/admin_routes.py`
- `apps/auth-service/src/auth_service/models.py`
- `apps/auth-service/src/auth_service/routes.py`
- `apps/auth-service/src/auth_service/schemas.py`
- `apps/auth-service/tests/conftest.py`
- `apps/auth-service/tests/test_login_routes.py`
- `apps/auth-service/tests/test_risk_appeals.py`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/api-locale.test.ts`
- `apps/web/src/app/auth/appeal/page.tsx`
- `apps/web/src/app/auth/appeal/page.test.tsx`
- `apps/web/src/app/auth/login/page.tsx`
- `apps/web/src/app/auth/login/page.test.tsx`
- `apps/web/messages/zh-CN.json`
- `apps/web/messages/en-US.json`

### Implementation Plan

- Add `risk_appeals` persistence and public/admin lifecycle endpoints.
- Convert frozen login/OTP errors into actionable RFC7807 responses.
- Add Web appeal/status flow with localized copy and tracking-token access.
- Cover lifecycle, security boundaries, and regression tests before code review.

### Change Log

- 2026-05-25: Created initial Story 1.12 draft; status set to ready-for-dev.
- 2026-05-25: Completed three-round story review and patched data consistency, function drift, boundary, and closure issues before implementation.
- 2026-05-25: Started dev-story implementation; status set to in-progress.
- 2026-05-25: Implemented J7 risk appeal lifecycle, admin review, frozen auth RFC7807, localized Web appeal/status UI, and regression tests.
- 2026-05-25: Completed post-implementation code review and fixed audit linkage, active appeal uniqueness, ORM index expressions, and invalid-token UX; final validation passed.
