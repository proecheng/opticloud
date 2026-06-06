---
story_key: 6-c-2-30d-exit-notification
baseline_commit: f8b8d8e8a19e546792ec39012528ef8654648d12
epic_num: 6
story_num: C.2
epic_name: Auto-migration + Provider Exit v2
status: code-review
priority: High
type: provider exit pre-notification
created_by: bmad-create-story
created_at: 2026-06-06
sources:
  - _bmad-output/planning/epics.md (Epic 6.C / Story 6.C.2 / R7)
  - _bmad-output/planning/prd.md (FR R7 and compliance Provider exit pre-notification)
  - _bmad-output/planning/architecture.md (Repro 5y SLA, Provider routing, public status page)
  - _bmad-output/stories/6-c-1-auto-migrate-provider.md
  - _bmad-output/stories/5-d-6-notification-preferences.md
  - _bmad-output/stories/8-a-1-public-status-page.md
  - _bmad-output/stories/8-a-2-incident-subscribe.md
  - apps/solver-orchestrator/src/solver_orchestrator/models.py
  - apps/solver-orchestrator/src/solver_orchestrator/provider_migration.py
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py
  - apps/auth-service/src/auth_service/admin_routes.py
  - apps/web/src/lib/status-page.ts
---

# Story 6.C.2 - >=30d Provider Exit Pre-Notification

Status: code-review

## Story

**作为** 持有受 Provider 退出影响复现凭证的用户，
**我希望** 在 Provider 退出生效至少 30 天前收到邮件、站内信和公开状态页公告，
**从而** 我能在 5 年 Repro SLA 仍可执行时看到退出计划、迁移路径和后续 rerun 预期，而不是等到 rerun 失败才发现 Provider 已退出。

## Context

Epic 6.C 的 R7 要求：Provider 提退出申请时，voucher holders 必须在退出前 >=30 天收到邮件、站内信和状态页公告。Story 6.C.1 已在 `solver-orchestrator` 完成 rerun 时的 Provider auto-migration preflight，但明确排除 30 天通知。现有通知能力分布如下：

- `solver-orchestrator` 拥有 `reproduction_vouchers` 和 locked provider metadata，是唯一能精确找出受影响 voucher holders 的服务。
- `auth-service` 已有 notification preferences 和 incident fan-out，但其偏好事件合同只有 billing 与 status incident，不应为了本 story 修改 account settings 全量替换合同。
- `apps/web` status page 是 public typed model/RSS，不接数据库、不拉 live API；本 story只能输出可被状态页消费的公开公告合同，不能假装已经有 status page 自动化平台。
- `outbox` 是 shared Postgres generic event sink，`solver-orchestrator` CI 只加载 `01-schema.sql` 和 `02-solver-schema.sql`，因此本 story 的 solver-owned tables 必须在 `02-solver-schema.sql` 中自包含。

本 story 交付一个 provider exit notification control-plane：受保护的内部/admin endpoint 创建 Provider exit plan，强制校验退出生效时间 >=30 天；按 issued vouchers 去重生成每个受影响用户的通知请求；为每个新增通知请求写 generic outbox rows，channels 固定包含 `email` 与 `in_app`；同时生成一条 public status page announcement 事件/记录。真实 SMTP、站内信 inbox、status page live automation 和 Provider capability/equivalent matching 不在本 story。

## Scope

1. 在 `solver-orchestrator` 新增 Provider exit plan 与 voucher-holder notification request 持久化合同。
2. 新增 admin-secret 保护的 Provider exit plan 创建 endpoint，拒绝 `effective_at < now + 30 days`。
3. 只选中 `reproduction_vouchers.status='issued'` 且 `locked_model_version.provider_id` 等于退出 Provider 的 vouchers。
4. 对同一 `(exit_plan_id, user_id)` 去重，生成用户级 notification request；同一用户多个 vouchers 只发一组通知请求。
5. 对每个新增 request 写 pointer-safe outbox rows，channels 必含 `email` 与 `in_app`。
6. 生成一条 public status page announcement 记录和 outbox event，供后续 status page automation/静态导入使用。
7. 覆盖 edge cases、数据一致性、隐私边界、CI schema 顺序、post-implementation review 和 GitHub closure。

## Out Of Scope

- 真实 SMTP/Resend/Mailgun delivery、站内信 inbox UI、Web Push/SMS、退信、重试、delivery status、模板渲染服务。
- 修改 auth-service notification preferences、account settings 全量替换事件列表、incident fan-out、auth admin route。
- 修改 public `/status` live rendering、RSS 自动读取数据库、Statuspage/Uptime Kuma/Grafana/Prometheus 接入。
- 实现 Story 6.C.3 capability vocab governance 或 Story 6.C.4 broader equivalent matching algorithm。
- 改变 Story 6.C.1 rerun migration resolver、voucher ID 格式、5 年 SLA clock、rerun endpoint 行为、normal optimization response schema。
- 创建新的 deployable microservice、scheduler、worker、external API call、capability-registry network dependency。

## Acceptance Criteria

1. `infra/local-init/02-solver-schema.sql` idempotently creates solver-owned `provider_exit_plans`, `provider_exit_notification_requests`, and `provider_exit_status_announcements` tables.
2. SQLAlchemy models in `apps/solver-orchestrator/src/solver_orchestrator/models.py` match the SQL schema, including checks, indexes, FK relationships, and JSON/array column shapes.
3. Schema is self-contained for solver CI: it may depend on `01-schema.sql` for `users`, `api_keys`, and `outbox`, but must not require `13-notification-preferences.sql`.
4. Provider exit plan create endpoint is internal/admin only and protected by an `X-Admin-Secret` fail-closed pattern. Empty `ADMIN_SECRET` returns 403; missing/invalid header returns 401.
5. Solver config exposes `admin_secret` with the same empty-fail-closed semantics; public optimizer, rerun, catalog, and job-template routes do not require this secret.
6. Request body validates `provider_id`, `effective_at`, `reason`, optional `replacement_provider_id`, and optional public message with bounded lengths and safe character patterns.
7. `effective_at` must be at least 30 * 24h after server-side UTC `now`; 29d23h59m59s and past timestamps return 422/409 without any DB mutation or outbox row.
8. A valid request creates exactly one provider exit plan row with status `scheduled`, UTC timestamps, public-safe provider metadata, and no raw provider request payload.
9. Creating the same provider/effective_at plan twice is idempotent or conflict-safe: it must not create duplicate plans, duplicate user requests, or duplicate outbox rows.
10. Affected voucher selection includes only `reproduction_vouchers.status='issued'` whose `locked_model_version->>'provider_id'` equals the requested Provider.
11. Revoked vouchers, expired 5-year vouchers, vouchers for other providers, and optimizations without vouchers are excluded from notification request creation.
12. Anonymous vouchers are included by owner `user_id`, but notification payloads must not reveal anonymous mode, source optimization payloads, voucher IDs, request fingerprints, or API key IDs.
13. Multiple affected vouchers for one user collapse into one `provider_exit_notification_requests` row keyed by `(exit_plan_id, user_id)`.
14. Notification request rows store `affected_voucher_count`, provider id, exit plan id, `status_url`, channel snapshot, `email_requested=true`, `in_app_requested=true`, and `webhook_requested=false`.
15. Notification request rows do not store user email, phone, webhook URL, raw voucher IDs, source optimization payloads, solver input, solution, billing IDs, API key IDs, JWTs, or provider secrets.
16. For every newly-created user notification request, one generic outbox row is inserted with event type `provider.exit.notification_requested`.
17. Outbox notification payload includes only `exit_plan_id`, `provider_id`, `effective_at`, `status_url`, `channels`, `user_id`, `notification_request_id`, `affected_voucher_count`, and public reason/message fields.
18. Outbox notification payload must contain channels exactly `["email", "in_app"]`; users cannot opt out of this SLA-critical Provider exit notice through existing preferences.
19. Users whose account row is deleted, merged, or frozen are not newly enqueued for notification requests.
20. A public status announcement row is created once per plan and emits one generic outbox row with event type `provider.exit.status_announcement_requested`.
21. Status announcement payload includes only public fields: `announcement_id`, `exit_plan_id`, `provider_id`, `effective_at`, `status_url`, `title`, `summary`, `severity`, `status`, and affected voucher holder count.
22. Status announcement payload uses status page compatible semantics: incident-like id/anchor, bounded title/summary, severity no higher than `major` unless explicitly supplied by contract, and status `identified` or `monitoring`.
23. If no issued vouchers are affected, the plan and status announcement still exist, but no user notification request rows and no per-user outbox rows are created.
24. The response returns counts only: plan id, provider id, effective_at, affected users, affected vouchers, notification requests created, status_url, and announcement id. It must not return voucher ids or user emails.
25. Endpoint and helper logic are deterministic and offline; tests must not call email providers, auth-service HTTP, capability-registry HTTP, status page HTTP, or external network.
26. Existing Story 6.C.1 provider migration resolver and rerun tests continue to pass unchanged.
27. Existing `POST /v1/reproduce/{voucher_id}/rerun` behavior and response shape do not gain Provider exit notification fields.
28. Existing `/status` public static page behavior is not modified unless a tiny type-safe helper/test is required for announcement payload compatibility; no live fetch is added.
29. Tests cover 30-day boundary, admin-secret failure modes, affected voucher selection, anonymous privacy, user de-dupe, no affected vouchers, idempotency/retry, frozen/deleted/merged user exclusion, and pointer-safe outbox/status announcement payloads.
30. Focused tests, solver-orchestrator regression tests as feasible, ruff, mypy, OpenAPI drift if route schemas change, and `git diff --check` pass locally.
31. Post-implementation code review is run after implementation; findings are fixed or explicitly documented in this story.
32. GitHub PR CI must pass, PR must be merged, remote feature branch deleted, and local `main` synced before this story or sprint status is marked `done`.
33. The final `done` status update must be a separate status-sync commit after GitHub merge/sync.

## Tasks / Subtasks

- [x] T1: Add solver-owned Provider exit notification schema. (AC: 1-3, 14-15, 20-22)
  - [x] Add idempotent SQL to `infra/local-init/02-solver-schema.sql`.
  - [x] Add ORM models and indexes/checks in `apps/solver-orchestrator/src/solver_orchestrator/models.py`.
  - [x] Include solver tests that assert the schema contract is present without requiring `13-notification-preferences.sql`.

- [x] T2: Add protected Provider exit plan endpoint. (AC: 4-9, 23-24)
  - [x] Add solver config `ADMIN_SECRET` and local `require_admin_secret` helper.
  - [x] Add request/response schemas with 30-day UTC boundary validation.
  - [x] Add endpoint under `/v1/admin/provider-exits` or equivalent existing router prefix.
  - [x] Make duplicate provider/effective_at submission idempotent or conflict-safe.

- [x] T3: Implement affected voucher holder selection and notification request fan-out. (AC: 10-19, 23-25, 27)
  - [x] Query issued vouchers by locked provider with owner account filters.
  - [x] Exclude revoked/expired/other-provider rows and inactive account rows.
  - [x] Collapse multiple vouchers per user into one request with `affected_voucher_count`.
  - [x] Insert per-user notification requests idempotently.
  - [x] Insert pointer-safe `provider.exit.notification_requested` outbox rows only for newly-created requests.

- [x] T4: Implement public status announcement contract. (AC: 20-24, 28)
  - [x] Insert one `provider_exit_status_announcements` row per plan.
  - [x] Insert one pointer-safe `provider.exit.status_announcement_requested` outbox row per new announcement.
  - [x] Keep announcement payload compatible with public status page incident semantics without making `/status` live-fetch.

- [x] T5: Add focused tests and local validation. (AC: 25-31)
  - [x] Add `apps/solver-orchestrator/tests/test_provider_exit_notifications.py`.
  - [x] Cover boundary, de-dupe, privacy, account status, no-affected-voucher, and outbox cases.
  - [x] Run focused tests plus Story 6.C.1 provider migration/rerun regressions.
  - [x] Run static/type gates and OpenAPI drift check if endpoint schemas affect generated contract.

- [ ] T6: Post-implementation review and GitHub closure. (AC: 31-33)
  - [x] Run adversarial code review after implementation.
  - [x] Fix/document findings.
  - [ ] Commit implementation, push branch, create PR, wait for CI.
  - [ ] Merge PR, delete remote branch, sync local `main`.
  - [ ] Only after sync, make separate status commit marking story/sprint done.

### Review Findings

- [x] [Review][Patch] Expired leap-day vouchers could be included by cutoff approximation [`apps/solver-orchestrator/src/solver_orchestrator/provider_exit_notifications.py:153`] — Fixed by replacing `now - 5 calendar years` cutoff filtering with per-voucher `rv.created_at + INTERVAL '5 years' > as_of` evaluation and adding a 2024-02-29 boundary regression test.

## Dev Notes

### Service Boundary

- Implement runtime changes in `apps/solver-orchestrator`; it owns vouchers and can select affected voucher holders without cross-service calls.
- Use the shared `outbox` table created by `01-schema.sql`; add an ORM model only if needed locally or use raw SQL consistently. If adding an ORM model, keep it table-compatible with `01-schema.sql`.
- Do not import auth-service models or schemas into solver-orchestrator.
- Do not call auth-service HTTP to read notification preferences. R7 requires email + in-app for all eligible voucher holders; this is SLA-critical, not preference-managed marketing.
- Do not call `apps/web` or capability-registry at runtime.

### Data Model Guidance

- Suggested tables:
  - `provider_exit_plans`: `id`, `provider_id`, `effective_at`, `status`, `reason`, `replacement_provider_id`, `public_message`, `created_by`, `created_at`, `updated_at`.
  - `provider_exit_notification_requests`: `id`, `exit_plan_id`, `user_id`, `provider_id`, `status_url`, `affected_voucher_count`, `channels`, `email_requested`, `in_app_requested`, `webhook_requested`, `created_at`, `updated_at`.
  - `provider_exit_status_announcements`: `id`, `exit_plan_id`, `announcement_id`, `provider_id`, `effective_at`, `status_url`, `title`, `summary`, `severity`, `announcement_status`, `affected_user_count`, `affected_voucher_count`, `created_at`, `updated_at`.
- Required uniqueness:
  - `(provider_id, effective_at)` for plans.
  - `(exit_plan_id, user_id)` for notification requests.
  - `exit_plan_id` and `announcement_id` for status announcements.
- `status_url` can be deterministic, e.g. `/status#provider-exit-{provider_id}-{YYYYMMDD}`.
- Use UTC-aware server time only. Tests may monkeypatch a local clock helper.

### Privacy And Safety

- Do not expose voucher IDs in outbox, status announcement, logs, or endpoint response. Counts are enough.
- Do not expose anonymous voucher flags; notifying the owning account is allowed, revealing anonymous review metadata is not.
- Do not include source optimization payload, solution, request fingerprint, API key id, billing id, webhook URL, email, phone, or JWT in any new payload.
- Public status announcement copy should identify the Provider and exit effective time, not affected user identities or voucher details.

### Existing Patterns To Reuse

- Reuse admin secret semantics from `apps/auth-service/src/auth_service/admin_routes.py`: empty secret disables endpoint with 403; bad/missing header returns 401 using constant-time compare.
- Reuse voucher/account filtering patterns from rerun tests and raw SQL user joins used across services.
- Reuse Story 8.A.2 outbox style: one request row plus one generic outbox event per new request, with pointer-safe payload.
- Keep `provider_migration.py` untouched unless tests reveal a real shared helper is needed.

### Suggested Commands

```powershell
$env:PYTHONPATH='apps/solver-orchestrator/src;packages/shared-py'; uv run pytest apps/solver-orchestrator/tests/test_provider_exit_notifications.py -q
$env:PYTHONPATH='apps/solver-orchestrator/src;packages/shared-py'; uv run pytest apps/solver-orchestrator/tests/test_provider_migration.py apps/solver-orchestrator/tests/test_reproduction_rerun.py -q
$env:PYTHONPATH='apps/solver-orchestrator/src;packages/shared-py'; uv run pytest apps/solver-orchestrator/tests/ -q
uv run ruff check apps/solver-orchestrator/src/solver_orchestrator apps/solver-orchestrator/tests/test_provider_exit_notifications.py
uv run ruff format --check apps/solver-orchestrator/src/solver_orchestrator apps/solver-orchestrator/tests/test_provider_exit_notifications.py
uv run mypy apps/solver-orchestrator/src/solver_orchestrator
uv run python scripts/generate_openapi.py
uv run python scripts/check_openapi_drift.py
git diff --check
```

## Definition Of Done

- Story file has passed exactly three pre-implementation adversarial review rounds and has been revised after each round.
- Implementation satisfies R7 with >=30d Provider exit pre-notification requests for email + in-app and a public status announcement contract.
- No adjacent 6.C.3/6.C.4 matching/vocabulary work is implemented early.
- Existing rerun auto-migration and voucher behavior remain compatible.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local gates and GitHub CI pass.
- PR is merged, remote branch is deleted, and local `main` is synced before story/sprint status is marked `done`.
- Final done status is recorded in a separate post-merge status-sync commit.

## Pre-Implementation Adversarial Review

### Round 1 - Boundary, Scope, And Fake-Completion Review

Findings:

1. Initial R7 wording could be faked by only adding UI copy or a status-page static entry without proving affected voucher holders were identified.
2. Implementing this in `auth-service` would miss voucher ownership because auth-service does not own `reproduction_vouchers`.
3. Implementing real email delivery or inbox UI would over-scope the story and create a notification service not present in architecture.
4. The story could accidentally mutate 6.C.1 rerun behavior or pull in 6.C.3/6.C.4 matching work.

Revision after Round 1:

- Scoped the story to solver-owned Provider exit plans, affected voucher-holder selection, notification request rows, outbox events, and a status announcement contract.
- Added explicit anti-fake ACs requiring issued voucher selection and per-user de-dupe.
- Added out-of-scope boundaries for real delivery, notification center, rerun behavior, capability vocab, and equivalent matching.
- Required response/counts and tests proving user/voucher selection rather than mere status-page copy.

Status: PASS after revision.

### Round 2 - Drift, Data Consistency, Privacy, And Recipient Review

Findings:

1. Notification preferences default/event list could drift if this story adds a new preference event to auth-service; existing account PUT requires full replacement of exactly known events.
2. Multiple vouchers for one user could generate duplicate notices unless uniqueness is user-level per exit plan.
3. Anonymous vouchers need notification to the owner but must not leak anonymous review metadata or voucher IDs.
4. A Provider exit requested inside 30 days must fail atomically before creating status announcements or outbox rows.
5. Frozen/deleted/merged accounts should not receive newly-created notifications.

Revision after Round 2:

- Removed dependency on auth notification preferences and made Provider exit notices mandatory `email` + `in_app` SLA notices.
- Added uniqueness and count semantics for `(exit_plan_id, user_id)` with `affected_voucher_count`.
- Added strict pointer-safe payload allowlists and anonymous voucher privacy requirements.
- Added server-side UTC 30-day boundary and no-mutation failure requirements.
- Added account status filters for deleted, merged, and frozen users.

Status: PASS after revision.

### Round 3 - Dependency, CI, Status Page, And GitHub Closure Review

Findings:

1. Solver-orchestrator CI does not load `13-notification-preferences.sql`; any dependency on that schema would fail in CI or local focused tests.
2. The shared `outbox` table is in `01-schema.sql`, not solver schema; ORM/raw SQL must match the shared contract exactly.
3. Public `/status` is currently a static typed model and must not gain a fake live DB fetch.
4. Adding a protected admin route requires `ADMIN_SECRET` config in solver-orchestrator, not a hidden dependency on auth-service settings.
5. The user's process requires GitHub merge/delete/sync before marking story/sprint `done`.

Revision after Round 3:

- Required all new solver-owned tables to live in `02-solver-schema.sql` and depend only on `01-schema.sql`.
- Added explicit shared outbox compatibility and no `13-notification-preferences.sql` dependency.
- Defined status announcement as a public-safe contract/outbox event without modifying `/status` live behavior.
- Added solver-local `ADMIN_SECRET` fail-closed semantics.
- Added GitHub closure and separate status-sync commit ACs/DoD.

Status: PASS after revision. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-06-06 - Created Story 6.C.2 from Epic 6.C / PRD R7 / architecture Repro 5y + Status Page context / Story 6.C.1 boundary / existing notification and status-page implementations.
- 2026-06-06 - Completed exactly three pre-implementation adversarial review rounds and revised story after each round.
- 2026-06-06 - Implementation started; story and sprint status moved to in-progress.
- 2026-06-06 - Implemented solver-owned Provider exit plan schema, protected admin endpoint, voucher-holder fan-out, pointer-safe outbox events, and status announcement contract.
- 2026-06-06 - Fixed implementation-gate findings before review: added control-character rejection for public text fields, aligned local outbox ORM index ordering with shared SQL, and resolved mypy typing issues.
- 2026-06-06 - Local validation passed: focused provider-exit tests `7 passed`; Story 6.C.1 provider migration/rerun regression `22 passed`; solver-orchestrator suite `376 passed`; mypy passed; ruff check/format passed; OpenAPI drift passed; `git diff --check` passed.
- 2026-06-06 - Note: one parallel pytest run produced a rerun idempotency row-count failure due to concurrent shared local DB writes; the same regression suite passed when rerun serially.
- 2026-06-06 - Post-implementation adversarial code review found one patch finding: 5-year voucher expiry must be evaluated per voucher rather than by subtracting 5 calendar years from `now`.
- 2026-06-06 - Review finding fixed with SQL per-row expiry evaluation plus leap-day boundary regression; focused provider-exit tests now `8 passed`.
- 2026-06-06 - Final pre-PR validation passed serially: focused provider-exit tests `8 passed`; Story 6.C.1 provider migration/rerun regression `22 passed`; solver-orchestrator suite `377 passed`; mypy passed; ruff check/format passed; OpenAPI generation/drift passed; `git diff --check` passed.

### Completion Notes List

- Story context created and marked ready-for-dev.
- Implementation started after three pre-implementation adversarial review rounds.
- Added `POST /v1/admin/provider-exits`, gated by solver-local `ADMIN_SECRET` / `X-Admin-Secret` with empty-secret fail-closed behavior.
- Added solver-owned Provider exit plan, per-user notification request, and status announcement persistence in `02-solver-schema.sql` with ORM parity.
- Fan-out selects only issued, non-expired vouchers for the exiting provider, excludes deleted/merged/frozen accounts, deduplicates by user, and emits pointer-safe outbox payloads with channels exactly `["email", "in_app"]`.
- Status announcement is a public-safe contract/outbox request only; no live `/status` fetch, email provider, inbox, auth-service preference, or capability matching work was added.
- Implementation gates passed and story is ready for post-implementation code review; GitHub closure and final `done` status remain pending.
- Post-implementation review completed; one patch finding fixed and documented. GitHub PR/CI/merge closure and final separate status-sync commit remain pending.

### File List

- `_bmad-output/stories/6-c-2-30d-exit-notification.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/config.py`
- `apps/solver-orchestrator/src/solver_orchestrator/models.py`
- `apps/solver-orchestrator/src/solver_orchestrator/provider_exit_notifications.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`
- `apps/solver-orchestrator/tests/test_provider_exit_notifications.py`
- `infra/local-init/02-solver-schema.sql`

## Change Log

- 2026-06-06 - Created Story 6.C.2 and completed three pre-implementation adversarial review rounds.
- 2026-06-06 - Implementation started; story moved to in-progress.
- 2026-06-06 - Implemented Provider exit notification control-plane and moved story to code-review after local validation.
- 2026-06-06 - Completed post-implementation review; fixed per-voucher 5-year expiry boundary issue.
