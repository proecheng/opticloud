---
story_key: 8-a-2-incident-subscribe
baseline_commit: cff1617cd13cb9548922444ba27a7390de8fdda7
epic_num: 8
story_num: A.2
epic_name: Public Status + Audit + Vuln Response
status: done
priority: High
type: Authenticated incident notification subscription
created_by: bmad-create-story
created_at: 2026-06-02
sources:
  - _bmad-output/planning/epics.md (Epic 8.A / Story 8.A.2)
  - _bmad-output/planning/prd.md (FR O1; Webhook delivery v2 boundary)
  - _bmad-output/planning/architecture.md (SA7 Webhook Secret Rotation v2; OP8 Status Page automation deferred)
  - _bmad-output/planning/ux-design-specification.md (Status Page public trust surface)
  - _bmad-output/stories/8-a-1-public-status-page.md
  - _bmad-output/stories/5-d-6-notification-preferences.md
  - apps/auth-service/src/auth_service/routes.py
  - apps/auth-service/src/auth_service/schemas.py
  - apps/auth-service/src/auth_service/models.py
  - infra/local-init/13-notification-preferences.sql
  - apps/web/src/app/auth/account/page.tsx
  - apps/web/src/app/status/StatusPageView.tsx
---

# Story 8.A.2 - Incident Subscribe

Status: done

## Story

**作为** 已登录 OptiCloud 用户，
**我希望** 可以为公开 incident 订阅邮件、Webhook 和站内通知渠道，
**从而** 后续 incident 发布时，系统会按我的订阅偏好生成可投递的通知请求，而不是依赖我手动刷新公开 status page。

## Context

Story 8.A.1 已交付公开 `/status` 和 `/status/rss.xml`，并把 email/Webhook 入口留给本 story。Story 5.D.6 已交付 auth-service owned `notification_preferences`、严格 Webhook URL 验证、全量替换 API、账户页通知偏好面板、audit log 和 pointer-safe outbox 事件。

本 story 复用 5.D.6 的偏好系统，新增 incident 事件类型 `status.incident.published` 和一个内部 incident notification fan-out 合同。真实 SMTP、站内通知中心、HTTP Webhook delivery、HMAC 签名、重试、退信和 Webhook Secret Rotation 仍不在 v1 范围内；PRD 和 Architecture 将完整 Webhook 回调能力放在 v2/Growth。闭环定义为：incident publisher 触发内部 fan-out 后，auth-service 为显式订阅用户写入去重的 `status_incident_notification_requests` 记录和通用 outbox 通知请求，后续 provider/relayer 可消费该请求。

## Scope

1. 扩展现有 `notification_preferences` 支持 `status.incident.published`。
2. Incident 事件默认全渠道关闭；只有显式保存偏好后才参与 incident fan-out。
3. 新增持久化表记录每个 `(incident_id, user_id)` 的通知请求，保证重试不会重复推送。
4. 新增受 `X-Admin-Secret` 保护的内部/admin fan-out endpoint，用于 incident 发布时生成通知请求。
5. Outbox payload 只包含 pointer-safe incident metadata、channel snapshot 和 `webhook_url_configured` 布尔值，不复制原始 Webhook URL、email、JWT、API key 或账号数据。
6. 账户设置页展示 incident 事件订阅；公开 Status Page 的订阅区链接到登录后的通知偏好面板。
7. 增加 backend/web tests，完成 post-implementation review、local gates 和 GitHub sync。

## Out Of Scope

- 真实 email provider、SMTP、SMS、站内通知 inbox、HTTP Webhook dispatch、HMAC signing、retry/backoff、secret rotation、delivery status、bounce handling。
- 新 notification microservice、外部 Statuspage/Uptime Kuma/Grafana/Prometheus 接入、incident automation vendor 决策。
- P0 24h Postmortem、`/status/incidents/{id}`、Mermaid timeline、管理员 postmortem 发布流程。
- 修改 billing budget notification semantics、预算事件默认值、outbox-relayer generic behavior、Saga、credits/refund、provider health console。
- 将 Webhook URL、用户 email、JWT、API key、solver payload、事故内部 root cause 或非公开 incident body 写入 outbox。
- 匿名访客 email capture；本 story 只支持 authenticated user subscription。

## Supported Event Defaults

- `billing.budget.alerted`: default `email=true`, `in_app=true`, `webhook=false`
- `billing.budget.paused`: default `email=true`, `in_app=true`, `webhook=false`
- `status.incident.published`: default `email=false`, `in_app=false`, `webhook=false`

Incident 默认全关是硬约束：未显式订阅的用户不能因为默认值收到 incident 通知请求。

## Acceptance Criteria

1. Local schema idempotently upgrades `notification_preferences` so its event-type constraint accepts exactly `billing.budget.alerted`, `billing.budget.paused`, and `status.incident.published`.
2. Auth-service SQLAlchemy model check metadata matches the local init schema for all supported event types.
3. `GET /v1/auth/notification-preferences` returns all three supported events in stable order.
4. Billing event defaults remain unchanged: no persisted row returns `["email", "in_app"]`.
5. Incident event default is all channels disabled and returns `channels=[]`, `webhook_url=null`, `webhook_url_configured=false`.
6. `PUT /v1/auth/notification-preferences` remains a full-replacement contract and now requires exactly one item for each of the three supported events.
7. Missing, duplicate, unknown, or extra fields still return 422 without mutating existing rows.
8. Webhook URL validation rules from Story 5.D.6 remain unchanged for incident subscriptions.
9. Updating incident preferences upserts at most one `(user_id, event_type)` row and does not duplicate rows under retries.
10. Preference update audit log and `auth.notification_preferences.updated` outbox payload include the incident event channel summary, but never raw Webhook URLs.
11. Cross-user preference access remains impossible because `user_id` is resolved only from the active-user JWT.
12. Deleted, merged, or frozen users cannot read or update incident preferences.
13. A new `status_incident_notification_requests` table persists one row per `(incident_id, user_id)` with channel snapshot, `webhook_url_configured`, status URL, and timestamps.
14. The request table has a uniqueness guard on `(incident_id, user_id)` so retried fan-out cannot enqueue duplicate notification requests for the same user and incident.
15. Fan-out reads only explicit `status.incident.published` preference rows; users with no incident row are not notified.
16. Fan-out ignores active users whose incident channels are all disabled.
17. Fan-out ignores deleted, merged, and frozen users.
18. Fan-out writes one generic outbox row per newly-created incident notification request.
19. Outbox event type is stable and specific, e.g. `status.incident.notification_requested`.
20. Fan-out outbox payload includes `incident_id`, `status_url`, `title`, `severity`, `status`, `channels`, `webhook_url_configured`, `user_id`, and `notification_request_id`.
21. Fan-out outbox payload does not include raw Webhook URLs, email addresses, phone numbers, JWTs, API keys, arbitrary incident body, root-cause details, or private operator notes.
22. The fan-out endpoint is not public; it is protected by the existing admin secret pattern and fails closed when `ADMIN_SECRET` is empty.
23. Fan-out validates incident input with bounded fields and a safe incident id pattern, deriving `status_url` as `/status#{incident_id}`.
24. Repeating fan-out with the same `incident_id` reports zero newly-created requests after the first successful call.
25. Existing budget alert/pause preference filtering continues to pass and keeps the same default channels.
26. Account settings notification panel includes the incident event with clear operational label text.
27. Account settings can save all three event preferences in one full-replacement request.
28. Preference save failure still preserves the user's in-progress form values.
29. Preferences and Webhook URLs are not written to `localStorage` or `sessionStorage`.
30. Public `/status` subscription area links authenticated subscription management to `/auth/account#notification-preferences`.
31. Public `/status` copy does not claim real provider delivery, signed Webhook callbacks, retry, or secret rotation is implemented.
32. Web API helper types include `status.incident.published` and tests cover the new full-replacement body shape.
33. Backend tests cover defaults, PUT full replacement, incident webhook validation inheritance, user scoping, inactive user rejection, fan-out eligibility, idempotency, and pointer-safe outbox payload.
34. Web tests cover account page incident controls, status page subscription link, storage hygiene, and API helper body/error behavior.
35. No new runtime dependency is added.
36. Focused tests, service regressions, type checks, `git diff --check`, post-implementation code review, GitHub CI, PR merge, remote branch deletion, and local `main` sync all complete before this story is marked `done`.

## Tasks / Subtasks

- [x] T1: Extend notification preference event contract (AC: 1-12, 25, 32-33)
  - [x] Add `status.incident.published` to backend schemas, ORM check constraint, local init SQL, and TypeScript event types.
  - [x] Add event-specific default handling so incident defaults are disabled while billing defaults stay unchanged.
  - [x] Update auth-service preference tests for three-event full replacement and pointer-safe update outbox.
  - [x] Preserve existing Webhook URL validation behavior.

- [x] T2: Add incident notification request fan-out contract (AC: 13-24, 33)
  - [x] Add local init SQL and ORM model for `status_incident_notification_requests`.
  - [x] Add strict admin/internal request/response schemas.
  - [x] Add admin-secret protected fan-out route.
  - [x] Load eligible users from explicit incident preferences only, filtering inactive/deleted/merged/frozen users.
  - [x] Insert request rows idempotently and write one generic outbox row per new row.
  - [x] Add backend tests for fan-out eligibility, idempotency, and pointer-safe payloads.

- [x] T3: Extend web subscription UI and status entry points (AC: 26-32, 34-35)
  - [x] Add the incident event to the account notification panel with stable labels.
  - [x] Add `id="notification-preferences"` to the account notification section.
  - [x] Update account page tests for three event groups, successful save, failed-save preservation, and storage hygiene.
  - [x] Update `/status` subscription copy and link to `/auth/account#notification-preferences`.
  - [x] Update status page tests for the authenticated subscription link and no provider-delivery overclaim.

- [x] T4: Review, gates, and GitHub sync (AC: 36)
  - [x] Run focused backend/web tests before broader gates.
  - [x] Run post-implementation code review and fix findings.
  - [x] Run local gates and record results.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [x] Mark story and sprint status `done` only after merge/sync.

## Dev Notes

### Existing Patterns To Reuse

- Reuse `notification_preferences` from Story 5.D.6 rather than creating a separate subscription table for user preferences.
- Keep auth-service as owner because it already owns active/deleted/merged/frozen user checks and account settings APIs.
- Use existing `admin_routes.require_admin_secret` behavior for internal/admin fan-out protection.
- Use existing `OutboxEvent` generic outbox model. Do not change outbox-relayer; it publishes generic rows.
- Use the account settings notification panel in `apps/web/src/app/auth/account/page.tsx`; do not create a marketing subscription page.
- Keep `/status` public and unauthenticated. Its only change should be subscription management discovery/linking.

### Data Consistency Rules

- Incident preferences are explicit opt-in. Do not fan out based on the default disabled incident item returned by GET.
- Store a channel snapshot on `status_incident_notification_requests` so later preference changes do not rewrite already-queued requests.
- Do not store raw Webhook URL in notification request rows or outbox. The future delivery provider can dereference current user preference by `user_id` and event type if needed.
- Unique `(incident_id, user_id)` is required; duplicate fan-out calls must not duplicate outbox rows.
- If a user disables all incident channels, no request row and no outbox row should be created for that user.
- If `webhook=true`, `webhook_url_configured=true` may appear in the request/outbox, but the raw URL must stay only in `notification_preferences.webhook_url`.

### Boundary Rules

- Do not implement provider delivery, HMAC signatures, retry queues, or secret rotation.
- Do not extend public incident history beyond the current `/status` static model.
- Do not add `/status/incidents/{id}` or Postmortem content.
- Do not modify budget notification filtering except where test expectations must include the new supported event in full-replacement preference payloads.

### Suggested Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src'; uv run pytest apps/auth-service/tests/test_notification_preferences.py -q
pnpm --filter @opticloud/web test -- notification-preferences account/page.test.tsx status/page.test.tsx
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src'; uv run pytest apps/auth-service/tests/ -q
pnpm --filter @opticloud/web test
pnpm --filter @opticloud/web typecheck
uv run ruff check apps/auth-service/src/auth_service apps/auth-service/tests/test_notification_preferences.py
uv run ruff format --check apps/auth-service/src/auth_service apps/auth-service/tests/test_notification_preferences.py
uv run mypy apps/auth-service/src/auth_service
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Incident subscriptions are explicit opt-in and persist through the existing preference system.
- Incident fan-out creates idempotent, pointer-safe notification request outbox rows for subscribed active users.
- The UI exposes incident subscription management without claiming v2 provider delivery.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-a-2-incident-subscribe`.
- Baseline commit: `cff1617cd13cb9548922444ba27a7390de8fdda7`.
- Story creation used Epic 8.A / PRD O1, Architecture SA7/OP8, Story 8.A.1 status page, and Story 5.D.6 notification preferences.
- Customization resolver script was absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base `bmad-create-story/customize.toml`, found no team/user overrides, and loaded no `project-context.md` files.
- Implementation started; story and sprint status moved to in-progress.
- RED confirmed before implementation: auth-service focused tests failed because only two notification events were supported and `/v1/admin/status/incidents/fanout` did not exist; web focused tests failed because the account page had no incident controls and `/status` had no account notification deep link.
- Focused backend after implementation: `uv run pytest apps/auth-service/tests/test_notification_preferences.py -q` with `PYTHONPATH='packages/shared-py;apps/auth-service/src'` -> 13 passed.
- Focused web after implementation: `pnpm --filter @opticloud/web test -- notification-preferences account/page.test.tsx status/page.test.tsx` -> 11 passed.
- OpenAPI generation/check: `uv run python scripts/generate_openapi.py` and `uv run python scripts/check_openapi_drift.py` -> no drift.
- Service regressions: `uv run pytest apps/auth-service/tests/ -q` -> 96 passed; `uv run pytest apps/billing-service/tests/test_budget_routes.py -q` -> 6 passed.
- Web regression/type gate: `pnpm --filter @opticloud/web test` -> 179 passed; `pnpm --filter @opticloud/web typecheck` -> passed.
- Static gates: `uv run ruff check ...`, `uv run ruff format --check ...`, `uv run mypy apps/auth-service/src/auth_service`, and `git diff --check` passed.
- Story and sprint status moved to `code-review` after implementation and local gates; final `done` remains gated on post-implementation review, GitHub CI, PR merge, remote branch cleanup, and local `main` sync.
- Post-implementation code review found 3 patch findings: incident PUT omitted-channel defaults could accidentally enable email/in-app; incident request SQL constraint drift was not repaired for pre-existing tables; fan-out helper used an unnecessary RowMapping-to-dict conversion. All 3 were fixed.
- Focused backend after review fixes: `uv run pytest apps/auth-service/tests/test_notification_preferences.py -q` -> 14 passed.
- Final local gates after review fixes: auth-service tests 97 passed; web tests 179 passed; billing budget focused tests 6 passed; OpenAPI drift, ruff check, ruff format check, mypy, web typecheck, and `git diff --check` passed.
- GitHub sync: PR #146 passed checks including `changes`, `lint`, `mypy`, `auth-service-test`, `billing-service-test`, `contract-test`, `ts-typecheck`, `openapi-drift`, `e2e`, `matrix-detect`, `build-and-sbom (auth-service)`, and `gtm-toolkit-validation`; PR squash-merged to `main` at `01aa3284d0f415a85568add20b3fc9c5a64afdad`; remote branch `codex/8-a-2-incident-subscribe` was deleted; local `main` is synced to `origin/main`.

### Completion Notes List

- Story created for authenticated incident subscriptions and internal fan-out contract.
- Completed 3 pre-implementation adversarial review rounds and revised the story after each round.
- Implemented explicit opt-in incident notification preference event `status.incident.published`, preserving billing defaults while incident defaults stay disabled.
- Added idempotent admin-secret protected incident fan-out that creates pointer-safe `status_incident_notification_requests` rows and `status.incident.notification_requested` outbox rows only for active explicit subscribers.
- Extended account notification preferences UI and public Status Page subscription discovery to link users to `/auth/account#notification-preferences` without claiming provider delivery is active.
- GitHub sync completed: PR #146 passed CI, merged, remote branch deleted, local `main` synced, and story/sprint status marked done.

### File List

- _bmad-output/stories/8-a-2-incident-subscribe.md
- _bmad-output/stories/sprint-status.yaml
- apps/auth-service/src/auth_service/admin_routes.py
- apps/auth-service/src/auth_service/models.py
- apps/auth-service/src/auth_service/routes.py
- apps/auth-service/src/auth_service/schemas.py
- apps/auth-service/tests/test_notification_preferences.py
- apps/web/src/app/auth/account/page.test.tsx
- apps/web/src/app/auth/account/page.tsx
- apps/web/src/app/status/StatusPageView.tsx
- apps/web/src/app/status/page.test.tsx
- apps/web/src/lib/api.ts
- apps/web/src/lib/notification-preferences.test.ts
- infra/local-init/13-notification-preferences.sql
- packages/shared-ts/openapi/auth-service.json

## Change Log

- 2026-06-02 - Story created for authenticated incident subscription preferences and pointer-safe incident notification fan-out.
- 2026-06-02 - Completed 3 pre-implementation adversarial review rounds; story marked ready for development.
- 2026-06-02 - Implementation started; story and sprint status moved to in-progress.
- 2026-06-02 - Implemented incident notification preference event, idempotent fan-out request/outbox contract, account UI controls, Status Page subscription link, focused tests, regressions, and static gates; story moved to code-review.
- 2026-06-02 - Completed post-implementation code review; fixed incident omitted-field defaults, SQL constraint idempotency, and fan-out RowMapping handling.
- 2026-06-02 - PR #146 passed GitHub CI, merged to main, remote branch deleted, local main synced; story marked done.

## Post-Implementation Code Review

### Review Layers

- Blind Hunter: reviewed raw diff for data leaks, auth boundaries, duplicate fan-out, and schema drift.
- Edge Case Hunter: reviewed omitted fields, retry behavior, existing-table upgrades, and frontend subscription entry points.
- Acceptance Auditor: checked implementation against AC 1-36 in this story.

### Findings And Fixes

1. [Review][Patch][Fixed] `NotificationPreferenceItem` still used billing defaults when a PUT item only supplied `event_type: "status.incident.published"`, which could enable incident email/in-app without explicit channel fields.
   - Fix: added event-aware default correction in schema validation and a regression test proving omitted incident channel fields remain disabled.
2. [Review][Patch][Fixed] `status_incident_notification_requests` SQL checks were only present in `CREATE TABLE`, so rerunning local init against an older existing table would not repair constraint drift.
   - Fix: added idempotent `ALTER TABLE ... DROP CONSTRAINT IF EXISTS` / `ADD CONSTRAINT` blocks for incident id, severity, status, and channels.
3. [Review][Patch][Fixed] Fan-out channel helper converted `RowMapping` to `dict`, adding unnecessary runtime/type fragility.
   - Fix: changed the helper to accept `RowMapping` directly and reran focused backend/mypy gates.

### Review Result

- Decision-needed: 0
- Patch findings: 3 fixed
- Deferred: 0
- Dismissed: 0

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary, Product Scope, And Webhook Drift

Findings:

1. The original AC says email/Webhook automatic push, but PRD repeatedly places full Webhook callback delivery in v2/Growth.
2. Reusing Story 5.D.6 defaults blindly would notify all users by email/in-app without explicit incident opt-in.
3. Implementing SMTP, HTTP Webhook dispatch, HMAC signing, retry, or secret rotation now would violate Architecture SA7 and PRD v1 exclusions.
4. The story could drift into 8.A.3 Postmortem by adding `/status/incidents/{id}` or root-cause content.
5. A public status page email capture form would introduce unauthenticated PII collection not present in the current auth model.

Revision after Round 1:

- Scoped Webhook to subscription preference and pointer-safe notification request outbox only.
- Added hard incident defaults: all channels disabled unless explicitly saved.
- Added out-of-scope boundaries for delivery provider, HMAC, retries, secret rotation, Postmortem, and public email capture.
- Required `/status` to link to the authenticated account notification panel instead of capturing visitor email.

### Round 2 - Data Consistency, Idempotency, And Closure

Findings:

1. "Automatic push" would be fake if the story only added UI toggles and no incident event fan-out contract.
2. Fan-out without a uniqueness guard could duplicate notifications on incident publisher retries.
3. Fan-out based on default GET rows would notify unconfigured users.
4. Outbox payloads must be enough for downstream delivery routing without copying raw Webhook URLs.
5. Deleted, merged, or frozen users must not receive newly-created incident notification requests.

Revision after Round 2:

- Added `status_incident_notification_requests` with unique `(incident_id, user_id)`.
- Added admin/internal fan-out endpoint that writes one generic outbox row per newly-created request.
- Required fan-out to read only explicit `status.incident.published` preference rows with non-empty channels.
- Required active-user filtering and pointer-safe payload constraints.
- Defined duplicate fan-out behavior as zero newly-created requests after the first call.

### Round 3 - Dependency, Testing, And GitHub Closure

Findings:

1. Extending the preference event list changes the full-replacement PUT contract and can break existing web/account tests if all callers are not updated.
2. SQL constraint, ORM check constraint, tests, and TypeScript union types can drift unless all are updated together.
3. The account page needs a stable anchor so `/status` can deep-link to subscription management.
4. Status page copy can accidentally overclaim that real provider delivery is already implemented.
5. Marking the story `done` before PR merge/local main sync would violate the user's required process.

Revision after Round 3:

- Added ACs and tasks for backend schema/model/schema tests, TypeScript helper types, account page tests, and status page tests.
- Required `id="notification-preferences"` on the account notification section and `/auth/account#notification-preferences` link from `/status`.
- Added copy constraint preventing delivery-provider overclaim.
- Added Definition of Done and task gates requiring post-implementation review, local gates, GitHub CI, PR merge, remote branch deletion, and local main sync before marking `done`.
