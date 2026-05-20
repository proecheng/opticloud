---
story_key: 1-6-pipl-account-delete
epic_num: 1
epic_name: Account & Identity
story_num: 1.6
status: done
priority: 🟠 High (FR A6 / PIPL hard-delete + J6 churn recovery arc; closes the compliance deletion gap for Epic 1)
sizing: M-L (~5 hours; delete-request flow + soft-delete mutation + purge worker design + tests + minimal user-facing entry)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-20
sources:
  - _bmad-output/planning/epics.md L1313-1317 (Story 1.6 — PIPL 7 day 账户删除)
  - _bmad-output/planning/prd.md L1441 (FR A6 definition — user can request account deletion + 7 day hard-delete)
  - _bmad-output/planning/prd.md L750-755 (PIPL privacy constraints — soft delete <= 7 days then hard delete incl. backups)
  - _bmad-output/planning/prd.md L583-591 (Journey 6 churn note — deletion UX is part of retention / support loop)
  - _bmad-output/planning/architecture.md L2004 (G8 PIPL data delete actor design — dry-run + soft + 7d hard + 4 store cascade)
  - _bmad-output/planning/architecture.md L1322 (api-gateway owns data-export Dramatiq actor pattern; reuse the gateway for delete orchestration)
  - _bmad-output/planning/architecture.md L1561-L1574 (v1 audit_logs in-core, v2 later split; hard-delete must preserve audit trail)
  - apps/auth-service/src/auth_service/models.py L28-53 (User.deleted_at already exists; soft-delete marker is available)
  - apps/auth-service/src/auth_service/routes.py L77-139 (signup route pattern, audit log pattern, session pattern)
  - apps/auth-service/src/auth_service/admin_routes.py L1-220 (shared-secret admin pattern and audit logging style)
  - apps/auth-service/src/auth_service/risk.py L1-130 (single sink / one commit path pattern for state transitions)
  - apps/auth-service/tests/conftest.py L1-80 (async test harness + session override + Windows bootstrap pattern)
dependencies:
  upstream:
    - 1-2-user-login (done) — login/JWT flow exists so deletion can require authenticated self-service
    - 1-5-risk-control-freeze (done) — frozen users are already blocked and can be referenced by deletion/appeal handling
    - 0-6-auth-scaffold (done) — User.deleted_at column exists and audit logging pattern is established
  downstream:
    - 1-7-account-merge-proposal — soft-deleted / frozen records feed merge-vs-delete appeal logic
    - 1-12-j7-fraud-freeze-vertical-slice — appeal path will surface deletion state if the user chooses delete instead of merge
    - 5-c-3-pipl-data-export-json — delete lifecycle and export lifecycle must stay consistent for PIPL
    - 5-c-5-pipl-self-service-portal — this story likely becomes one tab/flow inside the broader compliance portal
---

# Story 1.6 — PIPL 7 day 账户删除 (FR A6)

## User Story

**As** a 用户 who wants to leave the platform,
**I want** to request account deletion and have the account soft-deleted immediately, then hard-deleted within 7 days,
**so that** OptiCloud meets the PIPL deletion expectation and retains only the audit trail required for compliance.

## Why this story

FR A6 is explicitly marked v1 必上. The current codebase already has the ingredients for the first half of the flow: `users.deleted_at` exists, `audit_logs` exists, and the auth stack already uses a single DB session + audit-log pattern.

What is missing is the deletion lifecycle itself:
1. A user-facing deletion request endpoint / action plus a status lookup
2. A consistent soft-delete mutation on the user row
3. A durable delete-request record that survives the later user purge
4. Immediate revocation / rejection of all auth-service entry points tied to that user
5. A hard-delete worker / actor that finishes the purge after the 7 day SLA
6. A minimal user-facing entry so the request can be created and inspected

The important design constraint from the architecture gap is that the final purge must be expressed as a **data-delete actor** shape, not ad hoc deletes scattered through services. For v1, the implementation should start in `auth-service`; keep the request / worker shape compatible with the future `api-gateway` delete actor so G8 can absorb it later without rewriting the request model.

## Out of scope

- Full 4-store cascade implementation across every downstream store — Story G8 / M5 owns the multi-store completion
- GDPR / CCPA portability exports — separate compliance story in Epic 5.C
- Anonymous account recovery after deletion — once hard-deleted, the record is gone
- Immediate physical delete with no soft window — v1 keeps the 7 day grace period
- Customer support manual SQL cleanup — the flow must be encapsulated in application code / actor code
- UI-heavy compliance portal — this story only needs a minimal entry path and status visibility, not a full console rebuild

## Acceptance Criteria

### AC1: Deletion request is authenticated and creates a soft-delete marker

When a logged-in user requests deletion:
- `users.deleted_at` is set immediately to now
- a durable `account_deletion_requests` row is created or reused with `requested_at`, `hard_delete_at = now + 7 days`, `status`, `completed_at`, and a stable `user_id_snapshot`
- an `audit_logs` row is written for the request event
- all active API keys owned by the user are revoked at soft-delete time
- JWT-authenticated auth-service routes reject the deleted account, and `login` / `otp/request` / `api_keys` endpoints stop accepting the soft-deleted user
- the request endpoint returns the current request state so the UI can show the scheduled hard-delete time immediately after confirmation

### AC2: Hard-delete is deferred by 7 days

A background worker / actor:
- scans pending delete requests whose `hard_delete_at <= now`
- deletes the user record and any direct PII that belongs to the auth domain
- preserves `audit_logs` and the deletion request record
- marks the request as completed so reprocessing is idempotent
- tolerates a user that has already been removed from the auth table
- stores `completed_at` when the hard delete finishes

### AC3: Deletion flow is idempotent

- Re-requesting deletion on an already soft-deleted user returns the existing request state and does not create a duplicate row
- Re-running the hard-delete worker on the same request does nothing harmful
- The hard-delete path tolerates a user that is already gone from the auth table
- The status lookup stays stable while the request is pending, completed, or already purged, keyed by `user_id_snapshot`

### AC4: Compliance trace remains

- `audit_logs` preserves the request and completion events
- `GET /v1/auth/account-deletion` can show the original request time, scheduled hard-delete time, and completion state
- the deletion request record survives the user purge so the status remains queryable by support / internal tooling even after the user row is gone
- the implementation never deletes the audit trail as part of the user purge

### AC5: Minimal user-facing entry exists

- authenticated users can reach a deletion request action from `/auth/account` in the existing auth area
- the page shows the current deletion status via `GET /v1/auth/account-deletion`
- the user sees the 7 day grace-period explanation before confirming
- the action is clearly destructive and requires deliberate confirmation
- the page follows the existing auth-guard pattern used by `/auth/api-keys`

### AC6: Story-specific follow-up records are consistent

- the deletion flow references the same user identity used by login / API key ownership
- the request record stores `user_id_snapshot` so later merge/appeal flows can read deletion state even after hard delete
- the hard-delete worker is local to `auth-service` in v1 but shaped so Story 5.C and G8 can extend it rather than replace it

## Tasks / Subtasks

- [x] Task 1: Define the deletion request model and soft-delete semantics (AC: 1, 3, 4, 6)
  - [x] Add an `account_deletion_requests` table in `infra/local-init/01-schema.sql` and `apps/auth-service/src/auth_service/models.py` with requested / scheduled / completed state, `user_id_snapshot`, and an index on due work
  - [x] Reuse `users.deleted_at` as the immediate soft-delete marker
  - [x] Add request/status response schemas for the authenticated user

- [x] Task 2: Add authenticated deletion request/status flow in auth-service (AC: 1, 4, 5)
  - [x] Create `POST /v1/auth/account-deletion` for the current signed-in user
  - [x] Create `GET /v1/auth/account-deletion` for the current signed-in user
  - [x] Write audit log entries for request and completion events
  - [x] Block login / OTP / JWT-authenticated API-key actions once `deleted_at` is set via a shared active-account gate
  - [x] Revoke existing API keys when the soft delete is created

- [x] Task 3: Implement the deferred hard-delete worker shape (AC: 2, 3, 4, 6)
  - [x] Add a service-local background job / actor / CLI runner for due delete requests
  - [x] Delete auth-domain PII while preserving audit logs
  - [x] Preserve the request record after the user row is gone
  - [x] Make reruns safe and idempotent

- [x] Task 4: Add a minimal account-area entry point (AC: 5)
  - [x] Add `/auth/account` in the existing web auth area
  - [x] Require explicit confirmation and show the 7 day SLA copy
  - [x] Keep the UI minimal and utilitarian, reusing existing `ConfirmationModal` / `StatusCard` patterns

- [x] Task 5: Cover the lifecycle with tests (AC: 1-4, 6)
  - [x] Request creates soft-delete state, request row, audit log, and key revocation
  - [x] Soft-deleted user is blocked from login, OTP, and JWT-authenticated API-key actions
  - [x] Hard-delete worker purges due requests and is idempotent
  - [x] Audit trail and request record remain queryable after completion
  - [x] `GET /v1/auth/account-deletion` and `/auth/account` render the correct state before and after confirmation

- [x] Task 6: Wire any necessary CI/schema support (AC: 2, 4, 6)
  - [x] Add any needed migration / local-init / fixture support for the request table
  - [x] Ensure the auth test suite initializes the deletion flow safely
  - [x] Update sprint status when implementation is done

## Dev Notes

- Prefer the existing auth-service patterns: SQLAlchemy ORM, async session, `AuditLog`, `HTTPException`, and the explicit route-style used in `routes.py`
- Reuse `deleted_at` on `User`; do not invent a second soft-delete field
- The background hard-delete should be expressed as a service-local worker or actor, but the story must keep the boundary compatible with the future `api-gateway` delete actor gap in architecture
- The request table must preserve the original user UUID snapshot after hard delete so status remains inspectable
- Preserve audit logs even after the user row is gone
- In v1, preserve the user row as a tombstone so cross-service billing / audit FKs do not lose history; delete auth-domain PII and revoke keys instead of cascading into billing data
- Soft delete should revoke active API keys and block JWT-authenticated auth-service routes for the deleted account
- Keep the delete request idempotent and safe to rerun
- User-facing copy should reflect the 7 day grace period; do not promise immediate permanent deletion

### Project Structure Notes

- Primary implementation surface is expected to be `apps/auth-service/src/auth_service/*`
- Worker / actor code may land in the service that owns the delete orchestration, but the auth domain remains the first consumer
- Keep the v1 implementation inside `auth-service`; do not scaffold the future `api-gateway` delete actor in this story
- Tests should follow the existing async pytest harness in `apps/auth-service/tests`
- If a UI entry is needed, keep it in the existing `apps/web` auth area rather than creating a new navigation system

### References

- [Source: _bmad-output/planning/epics.md#Story 1.6]
- [Source: _bmad-output/planning/prd.md#Compliance]
- [Source: _bmad-output/planning/architecture.md#Gap Analysis]
- [Source: apps/auth-service/src/auth_service/models.py]
- [Source: apps/auth-service/src/auth_service/routes.py]
- [Source: apps/auth-service/src/auth_service/admin_routes.py]
- [Source: apps/auth-service/src/auth_service/risk.py]
- [Source: apps/auth-service/tests/conftest.py]

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- `uv run pytest apps/auth-service/tests/test_account_deletion.py -v`
- `uv run pytest apps/auth-service/tests/ -v`
- `uv run pytest apps/auth-service/tests/ -q`
- `uv run ruff check apps/auth-service/src/auth_service apps/auth-service/tests/test_account_deletion.py`
- `pnpm --filter @opticloud/web test`
- `pnpm --filter @opticloud/web typecheck`

### Completion Notes List

- Completed 3 story-review rounds before implementation and tightened request/status model, API-key revocation boundary, hard-delete worker shape, and `/auth/account` UI entry.
- Implemented `account_deletion_requests`, authenticated GET/POST deletion endpoints, soft-delete + active-account gate, API key revocation, and a service-local hard-delete CLI.
- Added lifecycle tests covering soft delete, idempotent request, status lookup, hard-delete idempotency, audit/request preservation, and solver API-key rejection after deletion.
- Added minimal web account deletion page and API client coverage for the new endpoints.
- Code review finding resolved: hard-delete worker now tombstones the user row and removes auth-domain PII/API keys/OTP instead of deleting `users`, preventing billing/audit FK cascade loss.

### File List

- `_bmad-output/stories/1-6-pipl-account-delete.md`
- `_bmad-output/stories/sprint-status.yaml`
- `infra/local-init/01-schema.sql`
- `apps/auth-service/src/auth_service/account_deletion.py`
- `apps/auth-service/src/auth_service/account_deletion_cli.py`
- `apps/auth-service/src/auth_service/models.py`
- `apps/auth-service/src/auth_service/routes.py`
- `apps/auth-service/src/auth_service/schemas.py`
- `apps/auth-service/tests/test_account_deletion.py`
- `apps/web/src/app/auth/account/page.tsx`
- `apps/web/src/lib/account-deletion.test.ts`
- `apps/web/src/lib/api.ts`

## Senior Developer Review (AI)

### Review Outcome

Approve after changes.

### Findings

- High: Initial hard-delete path deleted `users`, which would cascade into billing tables with `ON DELETE CASCADE` and lose ledger / reconciliation history. Fixed by tombstoning the user row and deleting only auth-domain PII (`api_keys`, `user_otps`) while preserving audit and billing references.

### Verification

- `uv run pytest apps/auth-service/tests/test_account_deletion.py -q` — 5 passed
- `uv run pytest apps/auth-service/tests/ -q` — 42 passed
- `uv run ruff check apps/auth-service/src/auth_service apps/auth-service/tests/test_account_deletion.py` — passed
- `pnpm --filter @opticloud/web test` — 40 passed
- `pnpm --filter @opticloud/web typecheck` — passed
