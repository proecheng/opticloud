---
story_key: 5-d-6-notification-preferences
baseline_commit: 2d682bcabb3156839f0a4700de5873891d0e5252
epic_num: 5
story_num: D.6
epic_name: Billing - Invoices + Templates + Budget + Notifications
status: ready-for-dev
priority: High
type: notification preferences for billable events
created_by: bmad-create-story
created_at: 2026-06-01
sources:
  - _bmad-output/planning/epics.md (Epic 5.D / Story 5.D.6 / FR B13)
  - _bmad-output/planning/prd.md (FR B13 v1 required, simplified profile can cut to v2)
  - _bmad-output/planning/architecture.md (P51 notification channels / shared-py notification planned for v2)
  - _bmad-output/stories/5-d-5-monthly-budget-alert.md
  - infra/local-init/01-schema.sql
  - infra/local-init/12-billing-budget.sql
  - apps/auth-service/src/auth_service/models.py
  - apps/auth-service/src/auth_service/routes.py
  - apps/auth-service/src/auth_service/schemas.py
  - apps/billing-service/src/billing_service/budget.py
  - apps/billing-service/src/billing_service/models.py
  - apps/billing-service/tests/test_budget_routes.py
  - apps/web/src/lib/api.ts
  - apps/web/src/app/auth/account/page.tsx
---

# Story 5.D.6 - Notification preferences

Status: ready-for-dev

## Story

**As** an authenticated OptiCloud user,
**I want** to configure notification channels per supported billing event,
**so that** budget alerts and automatic pause notifications reach me only through channels I have opted into.

## Context

Story 5.D.5 emits pointer-safe `billing.budget.alerted` and `billing.budget.paused` budget events with candidate channels. This story closes FR B13 for the shipped notification surface by adding user-owned notification preferences and applying those preferences when budget notification events are emitted.

There is no deployable notification service in v1. Architecture reserves `shared-py/notification` for v2 and P51 describes UI notification surfaces, not a provider integration requirement. This story must not implement SMTP, webhook delivery workers, a full notification center, or a new notification microservice. The v1 loop is: authenticated user configures preferences in auth-service, billing-service reads those preferences when writing budget outbox payloads, and the Console exposes the settings.

## Scope

1. Add durable user-level notification preferences for supported per-event channels.
2. Expose authenticated get/update APIs from auth-service.
3. Apply preferences to Story 5.D.5 budget alert/pause outbox payload channels.
4. Add typed web API helpers and a compact account settings panel.
5. Keep event payloads pointer-safe and delivery-provider independent.
6. Run post-implementation code review, fix findings, pass gates, and sync GitHub.

## Out Of Scope

- SMTP, SMS, webhook HTTP dispatch, retries, bounces, provider callbacks, or delivery status.
- A standalone notification service, shared-py notification package, notification inbox, digest scheduler, or admin broadcast UI.
- Changing billing budget thresholds, budget event idempotency, Saga states, charge lifecycle semantics, invoice UI, or the future Tier 2 invoice/budget component story.
- Storing raw emails, phone numbers, API keys, JWTs, payment refs, source payload bodies, solver outputs, or arbitrary user blobs in notification preference or budget notification payloads.
- Cross-event wildcards, organization-level preferences, tenant admin defaults, quiet hours, locale templates, or marketing notification categories.

## Supported Events And Channels

Supported event types for this story:

- `billing.budget.alerted`
- `billing.budget.paused`

Supported channels for preferences:

- `email`
- `webhook`
- `in_app`

Default behavior for users without explicit preference rows:

- `email=true`
- `in_app=true`
- `webhook=false`
- `webhook_url=null`

## Acceptance Criteria

1. Local schema is idempotently upgraded with a `notification_preferences` table keyed by `(user_id, event_type)`.
2. SQLAlchemy model/index/check metadata in auth-service matches the local init schema.
3. Billing-service reads the same table without importing auth-service models or creating a new service dependency.
4. Only the two supported event types are accepted in v1: `billing.budget.alerted` and `billing.budget.paused`.
5. `GET /v1/auth/notification-preferences` requires a valid active user JWT and returns both supported events, merging persisted rows with defaults.
6. `PUT /v1/auth/notification-preferences` requires a valid active user JWT and accepts a full list of supported event preferences; it never accepts `user_id`, audit fields, timestamps, raw delivery payloads, or unknown events.
7. Each event preference accepts boolean `email`, `webhook`, and `in_app` switches. `webhook_url` is optional when `webhook=false` and required when `webhook=true`.
8. Valid webhook URLs must be `https://` URLs, <=512 characters, and must not contain credentials, query strings, fragments, localhost-style hostnames, IPv4/IPv6 loopback literals, IPv4/IPv6 private/reserved/link-local literals, or `.local` / `.internal` host suffixes. Invalid values return 422 and do not mutate persisted rows.
9. PUT is a full-replacement contract: the request must include exactly one item for each supported event type and no duplicate event types. Missing, duplicate, or unknown event types return 422 with no mutation.
10. Updating preferences upserts one row per supported event in a single transaction and leaves no duplicate `(user_id, event_type)` rows under retries.
11. Updating preferences writes a pointer-safe audit log entry and a pointer-safe `auth.notification_preferences.updated` outbox event containing only user id, event types, enabled channel names, and a webhook URL presence flag.
12. Cross-user access is impossible because `user_id` is taken only from JWT auth dependencies, never from path/query/body.
13. Deleted, merged, or frozen users cannot read or update notification preferences through the authenticated endpoints.
14. Auth-service CORS allows the new authenticated PUT route for the local web app.
15. Budget threshold evaluation still creates idempotent `billing_budget_events` exactly as in Story 5.D.5.
16. Budget alert/pause outbox payloads use the user's current preferences for the matching event type. If no preference row exists, payload channels remain `["email","in_app"]`.
17. If a user disables a channel, the channel is absent from subsequent budget alert/pause outbox payloads. If all channels are disabled, the outbox row is still emitted with `channels=[]` for audit/event propagation, but no delivery channel is requested.
18. If `webhook=true`, budget alert/pause outbox payloads include `webhook_url_configured=true` and channel `webhook`; the raw webhook URL is not copied into billing outbox payloads.
19. Existing 5.D.5 configured/disabled budget events remain audit events and are not converted into notification preference-managed delivery events.
20. Auth-service and billing-service tests cover defaults, validation, full-replacement errors, upsert/idempotency, user scoping, inactive user rejection, audit/outbox safety, and budget channel filtering.
21. Web API helpers in `apps/web/src/lib/api.ts` expose typed `getNotificationPreferences` and `putNotificationPreferences` helpers against `AUTH_SERVICE_URL` with bearer auth and existing error handling.
22. The account settings page displays a compact notification preference panel with per-event email/webhook/in-app controls and an optional webhook URL input.
23. The page can load/save preferences independently of account deletion and merge sections; preference failures do not hide existing account settings content.
24. Preference save failures do not clear or overwrite the user's in-progress form values; a subsequent successful save rehydrates the form from the returned server state.
25. The page stores no notification preferences, webhook URLs, event payloads, JWT copies beyond existing login token, or account data in `localStorage`/`sessionStorage`.
26. Tests cover web helper URL/auth/body/error behavior and account page success, validation/error isolation, form value preservation, and storage hygiene.
27. The new schema file is applied after `01-schema.sql` and before billing budget tests in CI/e2e/local fixtures, because it depends on `users` and is read by billing budget threshold evaluation.
28. Billing-service does not silently ignore a missing `notification_preferences` table in production code. Tests/local fixtures must create the table; runtime schema drift should fail loudly.
29. Outbox-relayer behavior remains unchanged: it treats `auth.notification_preferences.updated` and filtered `billing.budget.*` events as ordinary outbox rows and does not need event-specific code.
30. `git diff --check`, focused backend/web tests, service regressions, type checks, post-implementation code review, GitHub CI, PR merge, branch deletion, and local `main` sync all complete before the story is marked `done`.

## Tasks / Subtasks

- [ ] T1: Add notification preference persistence (AC: 1-4, 27-29)
  - [ ] Add idempotent local init SQL for `notification_preferences`.
  - [ ] Update CI/e2e schema setup and path filters for auth-service/billing-service.
  - [ ] Add auth-service ORM model with matching indexes and constraints.
  - [ ] Add auth-service `OutboxEvent` ORM model for the existing `outbox` table.
  - [ ] Ensure local test fixtures can run against databases missing the new table.

- [ ] T2: Add auth-service preference API (AC: 5-14)
  - [ ] Add request/response schemas and strict event/channel validation.
  - [ ] Add GET and PUT routes under `/v1/auth/notification-preferences`.
  - [ ] Add PUT to auth-service CORS allowed methods.
  - [ ] Add pointer-safe audit log and outbox event for updates.
  - [ ] Add tests for defaults, validation, upsert, inactive users, and cross-user isolation.

- [ ] T3: Apply preferences to billing budget notification payloads (AC: 15-19)
  - [ ] Add billing-service helper to read notification preferences by user/event via raw SQL.
  - [ ] Filter budget alert/pause `channels` using current preferences.
  - [ ] Include only a boolean webhook configured flag in billing outbox payloads.
  - [ ] Preserve 5.D.5 budget event idempotency and existing charge behavior.

- [ ] T4: Add web API helpers and tests (AC: 21, 26)
  - [ ] Add TypeScript request/response types and helpers.
  - [ ] Cover URL, Authorization, body shape, and RFC 7807/default error preservation.

- [ ] T5: Add account settings notification panel (AC: 22-26)
  - [ ] Load notification preferences independently of deletion/merge data.
  - [ ] Add per-event channel controls and webhook URL inputs.
  - [ ] Keep existing account settings visible on preference failures.
  - [ ] Add focused page tests for success, validation/error isolation, and storage hygiene.

- [ ] T6: Review, gates, and GitHub sync (AC: 30)
  - [ ] Run focused backend/web tests and static gates.
  - [ ] Run post-implementation code review and fix findings.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.

## Dev Notes

### Backend Ownership

- Auth-service owns user settings because it owns `users`, active/deleted/merged/frozen checks, and authenticated account settings APIs.
- Billing-service must not import auth-service code. Read `notification_preferences` with raw SQL in billing helpers, matching existing cross-service raw SQL patterns for users/subscriptions.
- Billing-service production code should not swallow missing-table errors. A missing table means deployment drift, not an acceptable default path.
- Keep the shared Saga state machine unchanged.
- Use existing `AuditLog` and `OutboxEvent` patterns from `infra/local-init/01-schema.sql`.

### Data Contract

- Table name: `notification_preferences`.
- Columns: `id`, `user_id`, `event_type`, `email_enabled`, `webhook_enabled`, `in_app_enabled`, `webhook_url`, `created_at`, `updated_at`.
- Unique index: one row per `(user_id, event_type)`.
- Check constraints should pin supported event types and require a webhook URL only when webhook is enabled.
- Schema file must be applied after `01-schema.sql` because it references `users(id)`.
- The PUT schema is full-replacement and must reject missing supported events, duplicates, unknown event types, and extra body fields.
- The auth outbox update payload may include `event_type`, `channels`, and `webhook_url_configured`; it must not include the raw webhook URL.

### Billing Integration

- Story 5.D.5 budget threshold events remain the source of truth for alert/pause idempotency.
- `billing.budget.alerted` and `billing.budget.paused` are the only budget outbox events whose channels are preference-filtered.
- Configured/disabled budget events can continue to repeat for auditability and should not be governed by notification preferences.
- If every channel is disabled, keep the budget event/outbox row but set `channels=[]`. Downstream delivery can interpret that as no requested delivery.
- Outbox-relayer already publishes rows generically from `outbox`; do not add event-specific relayer logic.

### Frontend Patterns

- `apps/web/src/lib/api.ts` already owns `AUTH_SERVICE_URL`, `request<T>()`, `OptiCloudClientError`, account deletion, merge, and billing helpers.
- `apps/web/src/app/auth/account/page.tsx` is the existing settings surface. Extend it with a compact notification preferences section rather than creating a marketing or standalone notification center page.
- Use checkboxes/toggles for boolean channel preferences and a normal URL input for webhook URL.
- Do not write preferences or webhook URLs to browser storage.

### Suggested Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/billing-service/src'; uv run pytest apps/auth-service/tests/test_notification_preferences.py apps/billing-service/tests/test_budget_routes.py -q
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/billing-service/src'; uv run pytest apps/auth-service/tests/ apps/billing-service/tests/ -q
uv run ruff check apps/auth-service/src/auth_service apps/auth-service/tests/test_notification_preferences.py apps/billing-service/src/billing_service apps/billing-service/tests/test_budget_routes.py
uv run ruff format --check apps/auth-service/src/auth_service apps/auth-service/tests/test_notification_preferences.py apps/billing-service/src/billing_service apps/billing-service/tests/test_budget_routes.py
uv run mypy apps/auth-service/src/auth_service apps/billing-service/src/billing_service
pnpm vitest run src/lib/notification-preferences.test.ts src/app/auth/account/page.test.tsx
pnpm typecheck
pnpm test
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Implementation satisfies every Acceptance Criterion without implementing a delivery provider or full notification service early.
- Existing account deletion, account merge, budget alert/pause, charge lifecycle, invoice, trend, subscription, topup, refund, and Saga behaviors remain compatible.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/5-d-6-notification-preferences`.
- Baseline commit: `2d682bcabb3156839f0a4700de5873891d0e5252`.

### Completion Notes List

### File List

- `_bmad-output/stories/5-d-6-notification-preferences.md`
- `_bmad-output/stories/sprint-status.yaml`

## Change Log

- 2026-06-01 - Story created for user notification preferences, budget notification channel filtering, and account settings UI.

## Pre-Implementation Adversarial Review

### Round 1 - Boundary, Validation, And Route Integration

Findings:

1. Auth-service CORS currently allows `GET`, `POST`, `DELETE`, and `OPTIONS`, so a browser `PUT /notification-preferences` would fail preflight unless CORS is updated.
2. Auth-service has the SQL `outbox` table but no ORM model; requiring an outbox write without specifying that model invites ad hoc raw inserts or omission.
3. The initial PUT contract said "full list" but did not define missing, duplicate, or unknown event behavior.
4. Webhook URL validation needed stronger SSRF boundaries, including query strings, IPv4/IPv6 private literals, and local/internal suffixes.
5. AC numbering and task mappings needed to reflect the added route/security requirements.

Revision after Round 1:

- Added ACs for CORS, full-replacement semantics, duplicate/missing/unknown event rejection, auth-service `OutboxEvent` ORM, and stricter webhook URL validation.
- Updated task mappings so persistence/API work explicitly includes CORS, auth outbox model, and full-replacement tests.

### Round 2 - Drift, Data Consistency, And Outbox Integration

Findings:

1. The story needed to state schema application order because `notification_preferences.user_id` depends on `users(id)`.
2. Billing-service could accidentally hide deployment drift by catching missing-table errors and falling back to defaults.
3. CI path filters and schema setup must include the new SQL for both auth-service and billing-service, otherwise one side passes while budget channel filtering fails.
4. The generic outbox-relayer does not need event-type changes; adding special-case relayer logic would be scope creep and a regression risk.
5. Default preference behavior must preserve 5.D.5 existing payload channels for users with no rows.

Revision after Round 2:

- Added ACs and Dev Notes for schema order, production missing-table failure, unchanged outbox-relayer behavior, and explicit default behavior preservation.
- Tightened task mapping so persistence work includes both auth and billing test schema setup.

### Round 3 - Closure, Dependency Consistency, And UI State

Findings:

1. AC numbering duplicated `26`, which would make task/coverage traceability ambiguous.
2. The existing account settings page has no page-level test, so this story must add one rather than only extending helper tests.
3. Notification preference state must not share the account deletion/merge loading and error state, or a failed preferences request could hide unrelated account controls.
4. A failed save must preserve the user's current form edits so validation errors are actionable.
5. The story needed an explicit UI rehydration rule after successful save to keep frontend state consistent with server normalization.

Revision after Round 3:

- Fixed AC numbering and task mappings.
- Added ACs for independent account-page tests, preference state isolation, failed-save form preservation, and successful-save rehydration from server state.
