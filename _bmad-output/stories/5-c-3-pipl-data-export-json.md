---
story_key: 5-c-3-pipl-data-export-json
epic_num: 5
story_num: C.3
epic_name: Billing - Refunds + PIPL Export
status: ready-for-dev
priority: High
type: PIPL JSON data portability export
created_by: bmad-create-story
created_at: 2026-05-30
sources:
  - _bmad-output/planning/epics.md (Story 5.C.3 / FR B10)
  - _bmad-output/planning/architecture.md (api-gateway data-export actor; cross-service batch read boundary)
  - _bmad-output/planning/prd.md (PIPL privacy constraints)
  - _bmad-output/stories/1-6-pipl-account-delete.md
  - _bmad-output/stories/5-c-2-user-cancel-refund.md
  - apps/auth-service/src/auth_service/models.py
  - apps/auth-service/src/auth_service/routes.py
  - apps/solver-orchestrator/src/solver_orchestrator/models.py
  - apps/billing-service/src/billing_service/models.py
  - infra/local-init/01-schema.sql
  - infra/local-init/02-solver-schema.sql
  - infra/local-init/03-billing-schema.sql
external_references:
  - 中国政府网《中华人民共和国个人信息保护法》 第四十五条: https://www.gov.cn/xinwen/2021-08/20/content_5632486.htm
---

# Story 5.C.3 - PIPL Data Export JSON

Status: done

## Story

**As** an authenticated OptiCloud user,
**I want** to request a JSON export of the personal data and product history OptiCloud holds about me,
**so that** I can exercise my PIPL access/copy right and retain a portable record before deletion, support review, or migration.

## Context

Epic 5.C defines B10 as "用户 can export all data + history (JSON/CSV)" and names JSON as the first slice. The architecture assigns the long-term owner to an `api-gateway data-export Dramatiq actor`, because the export must aggregate across Auth, Solver, Chat, and Billing stores without letting ordinary business services pull each other's data.

The current repository does not yet contain an online `api-gateway` implementation; `apps/api-gateway` is only a placeholder. Story 1.6 already put PIPL account deletion lifecycle in `auth-service`, including durable request records, soft-delete compatibility, and compliance audit logs. For this story, implement the v1 export actor shape in `auth-service` while preserving the future `api-gateway` boundary:

- keep the export orchestration in a dedicated module, not spread across routes;
- use raw SQL read-only aggregation for non-auth tables instead of importing solver or billing ORM models;
- tolerate optional cross-domain tables being absent in partial test deployments;
- expose only authenticated self-service request/status/download endpoints;
- produce JSON only; CSV remains Story 5.C.4.

PIPL Article 45 requires timely access/copy support and transfer paths when regulatory conditions are met. Existing project docs use a 7-day compliance SLA. Do not claim "7 days" is itself the statutory text; treat it as OptiCloud's product SLA.

## Scope

1. Add a durable `data_export_requests` lifecycle table for JSON export requests.
2. Add authenticated user endpoints to request an export, inspect status, and download the completed JSON package.
3. Add a service-local actor/worker function plus CLI that completes pending JSON export requests.
4. Aggregate user-owned Auth, Solver, Prediction, Billing, and available Chat data into a deterministic JSON package.
5. Redact secrets and raw credentials while preserving user data, product inputs/results, billing history, and compliance audit traces.
6. Write compliance audit logs and outbox events for request and completion.
7. Keep the implementation compatible with Story 1.6 account deletion tombstones and future `api-gateway` migration.
8. Represent the "email link" requirement as a pointer-safe notification outbox event plus a stable authenticated download URL; do not integrate a real email provider in this story.
9. Track failures on the request row so a failed export is visible and retryable by a later worker run or new request after operator remediation.

## Out of Scope

- CSV export, spreadsheets, or zip bundles.
- Full Console self-service portal UI; Story 5.C.5 owns portal UX.
- Actual email/SMS delivery provider integration. v1 records a download URL and outbox event that a future notification worker can send.
- A legal guarantee that every possible future processor/store is included. v1 covers the tables present in this repository and marks absent domains explicitly.
- New standalone `api-gateway` service scaffolding.
- Cross-border transfer to another processor.
- Admin export of another user's data.
- Exporting secrets: API key hashes, full API keys, OTPs, JWTs, token hashes, peppers, idempotency body hashes, internal shared secrets, or Authorization headers.
- Rewriting account deletion, billing refund, or chat persistence models.

## Acceptance Criteria

1. `POST /v1/auth/data-exports` creates or reuses one active JSON export request for the authenticated user and returns request id, status, requested time, 7-day SLA deadline, and eventual download fields.
2. `GET /v1/auth/data-exports/{export_id}` returns status only for the owner; another user receives 404 without learning the request exists.
3. `GET /v1/auth/data-exports/{export_id}/download` returns the completed JSON package only for the owner; queued/processing exports return 409, expired packages return 410, and cross-tenant access returns 404.
4. Requests are idempotent under repeated calls while an active queued/processing/completed-not-expired JSON export exists. No duplicate active rows, audit logs, or outbox request events are created.
5. The worker/actor claims queued requests with row locking, marks them processing, and completes them by producing a deterministic JSON document with schema version, generated timestamp, subject pointer, section manifest, and `data` sections.
6. The JSON package includes, when tables exist, Auth profile/deletion/merge/freeze/API-key/audit/risk data, Solver optimization and batch history, Prediction history, Billing saga/credit/subscription history, and a Chat section that is explicit about unavailable non-persisted v1 chat data. "All data" for v1 means these repository-owned stores and sections, not an open-ended crawl of external processors.
7. Optional cross-domain tables that are absent in partial deployments are represented as unavailable sections, not 500s.
8. Export content never includes full API keys, key hashes, OTP values, JWTs, token hashes, pepper values, request body hashes, Authorization headers, internal service secrets, or raw email delivery credentials. Metadata and arbitrary JSON payloads are recursively sanitized.
9. Completion stores package payload, byte size, SHA-256 digest, completion timestamp, expiry timestamp, and download URL on the request row.
10. Request and completion both write `audit_logs` rows; completion also emits pointer-safe outbox evidence with `data_export_id`, `user_id_snapshot`, `format`, `package_sha256`, `package_bytes`, and section counts.
11. Soft-deleted-but-not-purged users with a still-valid JWT can still request and download their export; hard-deleted/tombstoned users receive only retained tombstone/compliance data if available.
12. The export implementation does not import solver-orchestrator or billing-service ORM models into auth-service.
13. Worker failures set `status="failed"` with a bounded pointer-safe `last_error`, write no package payload, and do not emit completion outbox.
14. Existing account deletion, account merge, API key, billing, solver, and refund behavior remains unchanged.
15. Quality gates pass:
    - focused auth-service data export tests;
    - existing auth-service tests;
    - ruff check / format check for changed Python code;
    - mypy for changed Python apps;
    - `git diff --check`.

## Tasks / Subtasks

- [x] T1: Define durable JSON export request lifecycle (AC: 1, 4, 9-10)
  - [x] Add `data_export_requests` schema to `infra/local-init/01-schema.sql`.
  - [x] Add `DataExportRequest` ORM model in auth-service.
  - [x] Add response schemas for request/status.

- [x] T2: Add self-service request/status/download endpoints (AC: 1-4, 11)
  - [x] Add `POST /v1/auth/data-exports`.
  - [x] Add `GET /v1/auth/data-exports/{export_id}`.
  - [x] Add `GET /v1/auth/data-exports/{export_id}/download`.
  - [x] Enforce owner-only access with cross-tenant 404.

- [x] T3: Implement export actor package builder (AC: 5-9, 12)
  - [x] Create a dedicated `auth_service.data_export` module.
  - [x] Aggregate auth-owned data through ORM or raw SQL.
  - [x] Aggregate solver and billing tables through read-only raw SQL without cross-service model imports.
  - [x] Mark absent optional tables as unavailable sections.
  - [x] Recursively sanitize arbitrary JSON and metadata.

- [x] T4: Implement completion worker/CLI and audit evidence (AC: 5, 9-10)
  - [x] Add an idempotent `complete_pending_data_export_requests` worker function.
  - [x] Use `FOR UPDATE SKIP LOCKED` or equivalent row-locking claim semantics so concurrent workers cannot complete the same request twice.
  - [x] Add a small CLI runner for local/cron invocation.
  - [x] Store package payload, SHA-256, byte size, expiry, and download URL.
  - [x] Write audit logs and outbox completion event in the same transaction.

- [x] T5: Add focused tests and run gates (AC: 1-14)
  - [x] Test request creation and active-request idempotency.
  - [x] Test owner-only status/download and cross-tenant 404.
  - [x] Test worker package content across auth/solver/billing rows.
  - [x] Test secret redaction in direct fields and nested JSON metadata.
  - [x] Test queued 409 and expired 410 download behavior.
  - [x] Test worker failure records bounded `last_error` without package/outbox completion.
  - [x] Run full auth-service regression plus static gates.

## Dev Notes

### Existing Patterns To Reuse

- JWT user resolution: `_resolve_user_from_jwt` in `auth_service.routes`.
- Deletion compatibility: Story 1.6 allows deletion status lookup with `_resolve_user_from_jwt` rather than active-account gating.
- Compliance audit: `AuditLog` rows with `actor="user"` / `actor="system"` and pointer-safe metadata.
- Worker shape: `auth_service.account_deletion` + `account_deletion_cli.py`.
- Cross-service boundary: do not import solver/billing ORM classes; use raw SQL and table-existence checks.
- Outbox table exists in `infra/local-init/01-schema.sql`; auth-service can add an ORM model or use raw SQL.

### Data Package Shape

The package should be deterministic and explicit:

```json
{
  "schema_version": "pipl_export_json_v1",
  "format": "json",
  "generated_at": "2026-05-30T00:00:00Z",
  "subject": {"user_id": "..."},
  "manifest": {
    "sections": {
      "auth.profile": {"status": "available", "count": 1},
      "solver.optimizations": {"status": "available", "count": 3},
      "chat.messages": {"status": "unavailable", "reason": "not_persisted_v1"}
    }
  },
  "data": {}
}
```

### Sanitization Rules

- Explicitly omit or redact: `key_hash`, `token_hash`, `tracking_token_hash`, `request_body_hash`, `api_key`, `jwt_access`, `jwt_refresh`, `password`, `phone_otp`, `email_otp`, `guardian_consent_token`, `tracking_token`, and `authorization`.
- Recursively sanitize dictionaries and lists from `input_payload`, `solution`, `error`, `metadata`, `payload_ref`, and audit metadata.
- `api_key_id`, `key_prefix`, `prefix`, resource ids, and user-owned business inputs/results are allowed.

### Data Consistency And Idempotency Rules

- One active request means `status in ('queued', 'processing', 'completed')` and `expires_at is null or expires_at > now`.
- A new request after expiry is allowed and creates a new row; expired rows remain as compliance trace without package downloads.
- Re-requesting while active returns the existing row and must not add another `data_export.requested` audit row.
- Worker completion is exactly-once per request from the user's perspective: repeated or concurrent worker runs return the already completed row and do not rewrite package hash, duplicate outbox, or change `completed_at`.
- Use stable section ordering and row ordering (`created_at`, `id`) so package hash is deterministic for the same database snapshot aside from `generated_at`.
- Store package JSON as JSONB for v1; object storage/S3 is deferred and must not be faked.

### Required `data_export_requests` Fields

- `id UUID PRIMARY KEY`
- `user_id_snapshot UUID NOT NULL`
- `user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL`
- `format VARCHAR(16) NOT NULL DEFAULT 'json'`
- `status VARCHAR(32) NOT NULL` with values `queued`, `processing`, `completed`, `failed`, `expired`
- `requested_at TIMESTAMPTZ NOT NULL`
- `sla_deadline_at TIMESTAMPTZ NOT NULL`
- `processing_started_at TIMESTAMPTZ NULL`
- `completed_at TIMESTAMPTZ NULL`
- `expires_at TIMESTAMPTZ NULL`
- `package_json JSONB NULL`
- `package_sha256 CHAR(64) NULL`
- `package_bytes INTEGER NULL`
- `download_url TEXT NULL`
- `last_error TEXT NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- `updated_at TIMESTAMPTZ NOT NULL`

Add indexes for `(user_id_snapshot, requested_at desc)`, queued work, and active request lookup. Use a partial unique index for one active JSON export per user where feasible.

### Suggested Test Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/solver-orchestrator/src;apps/billing-service/src'; uv run pytest apps/auth-service/tests/test_data_exports.py -q
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/solver-orchestrator/src;apps/billing-service/src'; uv run pytest apps/auth-service/tests/ -q
uv run ruff check apps/auth-service apps/solver-orchestrator apps/billing-service
uv run ruff format --check apps/auth-service apps/solver-orchestrator apps/billing-service
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/solver-orchestrator/src;apps/billing-service/src'; uv run mypy apps/auth-service apps/solver-orchestrator apps/billing-service
git diff --check
```

## Pre-Implementation Adversarial Review

### Round 1 - Boundary, Scope, And Compliance Review

Findings:

1. The Epic text says "`api-gateway` data-export Dramatiq actor", but the repo only has `apps/api-gateway/.gitkeep`; scaffolding a full gateway now would create a hollow deployment surface.
2. "JSON 包邮件链接" can be misread as requiring real email delivery. There is no notification service integration in this repo, so the story must close with a download URL plus outbox event.
3. "all data" is too broad unless scoped to repository-owned stores; external processors, object storage, and future provider stores are not present.
4. PIPL Article 45 supports access/copy/transfer rights, but the story must not claim the project SLA of 7 days is direct statutory wording.
5. A public unauthenticated download URL would be risky; downloads must stay authenticated and owner-scoped.
6. Admin export of another user's data would create a new privilege surface and is outside self-service portability.
7. CSV, zip, portal UX, and email delivery are all named adjacent work but belong to later stories.
8. Chat data is currently not persisted as user history; pretending to export it would be fake completion.
9. Secrets and credentials can appear both as explicit columns and nested metadata; the scope must include recursive sanitization.
10. Account deletion and export lifecycles must coexist; export should work during soft-delete but must not resurrect hard-deleted PII.

Revision after Round 1:

- Story implementation is v1 `auth-service` actor shape with future `api-gateway` migration guardrails, not a new standalone gateway service.
- Email delivery is represented by a pointer-safe outbox event and authenticated download URL.
- V1 "all data" is scoped to present repository stores and explicit unavailable sections.
- PIPL language distinguishes legal access/copy basis from OptiCloud's 7-day SLA.
- Authenticated owner-only downloads, recursive redaction, soft-delete compatibility, and no fake chat persistence are now explicit.

### Round 2 - Drift, Data Consistency, And Idempotency Review

Findings:

1. Without a unique active-request rule, repeated POSTs can create multiple exports and multiple notification events.
2. Worker concurrency can double-complete the same row unless the request is claimed under row lock.
3. A completed package can drift if later worker retries rewrite `generated_at`, hash, and download URL.
4. "completed-not-expired" needs precise semantics; otherwise old packages either disappear too early or remain downloadable forever.
5. Sorting by database default order makes package hashes nondeterministic.
6. Returning queued/processing package placeholders from download would blur status and may leak partial payloads.
7. Missing cross-domain tables should produce unavailable manifest entries, but SQL errors from unexpected schema drift should still mark the request failed rather than silently producing incomplete success.
8. An export started before account deletion and completed after soft-delete must still be owner-scoped by `user_id_snapshot`.
9. Storing JSON package without size/hash makes later audit and notification unverifiable.
10. Request audit rows must not duplicate on idempotent POST replay.

Revision after Round 2:

- Active request semantics, expiry behavior, and one-active-row idempotency are explicit.
- Worker must claim rows with locking and treat completed rows as immutable replay.
- Package ordering, hash, byte size, and download status codes are specified.
- Missing optional tables are unavailable sections; true query failures should fail the request rather than masquerade as success.

### Round 3 - Dependency, Closure, And Audit Review

Findings:

1. The story named a durable table but did not specify enough columns for implementation consistency.
2. Failure handling was missing; a broken export could stay `processing` forever or falsely complete without payload.
3. Completion outbox must not be emitted on failure, or downstream notification would send a dead link.
4. The user deletion tombstone path means `user_id` can become null later; `user_id_snapshot` must be the stable owner/audit key.
5. Auth-service tests in CI do not apply solver schema, so focused export tests must create or tolerate optional solver/billing tables locally.
6. The worker must not import solver/billing models even for tests, or service boundaries drift.
7. A partial unique index is needed where Postgres can enforce one active JSON request; application-only idempotency is too weak under concurrent POST.
8. `last_error` can leak internals if full exception strings are persisted; keep it bounded and pointer-safe.
9. Story completion must include post-implementation code review and GitHub sync, not just local test success.
10. Sprint status must not move to `done` until review findings are resolved and CI/PR are green.

Revision after Round 3:

- Required request fields and indexes are specified.
- Failure semantics are explicit and no completion event is emitted on failure.
- `user_id_snapshot` is the stable identity for tombstone/download/audit paths.
- Tests must account for partial schemas without cross-service model imports.
- Definition of Done includes post-implementation code review, fixes, gates, commit, PR, CI, merge, and `main` sync.

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Implementation satisfies every Acceptance Criterion without adding out-of-scope API surfaces.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review and gates.
- Branch is pushed, PR is created, merged to `main`, remote branch is deleted, and local `main` is synced.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline commit: `0e1f4d846b7ea7311bb8b685d9cc51e49f50a18d`.
- Red phase: `test_data_exports.py` failed at collection because `auth_service.data_export` did not exist.
- Green phase: focused data export tests passed: 5 tests.
- Post-implementation code review found one high-priority concurrency/idempotency issue: concurrent direct export requests could race between active-row lookup and insert. Patched with a transaction-level advisory lock and added a direct concurrent request regression.
- Focused data export tests passed after review patch: 6 tests.
- Full auth-service regression passed: 78 tests.
- Full billing-service regression passed: 271 tests.
- Full solver-orchestrator regression passed: 283 tests.
- Static gates passed: ruff check, ruff format --check, mypy, Bandit pre-commit hook, and `git diff --check`.

### Completion Notes List

- Added durable `data_export_requests` schema/model and Pydantic status response.
- Added authenticated `POST /v1/auth/data-exports`, `GET /v1/auth/data-exports/{id}`, and owner-only download endpoint.
- Added service-local data export actor with row-lock claim, deterministic JSON package manifest, cross-domain raw SQL aggregation, absent-section handling, recursive redaction, package hash/size/expiry, audit logs, and outbox events.
- Added CLI runner for queued export completion.
- Covered request idempotency, cross-tenant 404, package content, secret redaction, queued/expired download behavior, and bounded failure state.
- Post-review patch added transaction-level advisory locking for same-user JSON export creation and a concurrent request regression test.
- CI lint follow-up added a targeted `# nosec B608` on the internally whitelisted export-table SQL builder; the table/query fragments are validated and all user values remain bound parameters.

### File List

- `_bmad-output/stories/5-c-3-pipl-data-export-json.md`
- `_bmad-output/stories/sprint-status.yaml`
- `infra/local-init/01-schema.sql`
- `apps/auth-service/src/auth_service/data_export.py`
- `apps/auth-service/src/auth_service/data_export_cli.py`
- `apps/auth-service/src/auth_service/models.py`
- `apps/auth-service/src/auth_service/routes.py`
- `apps/auth-service/src/auth_service/schemas.py`
- `apps/auth-service/tests/test_data_exports.py`

## Change Log

- 2026-05-30 - Story created with v1 JSON export scope, auth-service actor shape, and future api-gateway migration guardrails.
- 2026-05-30 - Implemented PIPL JSON export request/status/download endpoints, worker/CLI, schema/model, redaction, audit/outbox evidence, and focused tests; status set to review.
- 2026-05-30 - Completed post-implementation code review, patched concurrent request idempotency, ran regression/static gates, and marked story done.

## Senior Developer Review (AI)

Findings:

- [x] [Review][Patch] `POST /v1/auth/data-exports` used a lookup-then-insert idempotency path. Concurrent same-user requests could both miss the active row, then one would hit the partial unique index and surface as a 500. Patched `request_data_export` with a transaction-level advisory lock keyed by `(user_id, json)`, then added a direct concurrent request regression proving only one row and one request outbox event are created.

Decision: Approved after patch.
