---
story_key: 1-7-account-merge-proposal
epic_num: 1
epic_name: Account & Identity
story_num: 1.7
status: done
priority: High (FR A7/A8 / J7 fraud-freeze recovery bridge)
sizing: M-L (~5 hours; backend state model + user/admin endpoints + minimal account-page panel + tests)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-20
sources:
  - _bmad-output/planning/epics.md L1319-L1323 (Story 1.7 — account merge proposal + 48h review)
  - _bmad-output/planning/prd.md L595-L612 (Journey 7 — frozen user appeal, 48h review, merge proposal, resume access)
  - _bmad-output/planning/prd.md L1442-L1443 (FR A7/A8 definitions)
  - _bmad-output/planning/ux-design-specification.md L99 (J7 persona surface: 申诉表单 + 48h 复审 + 账号合并)
  - _bmad-output/planning/ux-design-specification.md L2519-L2530 (J7 flow: review pass => unfreeze; uphold => merge proposal)
  - _bmad-output/stories/1-5-risk-control-freeze.md (risk_flags, is_frozen, admin shared-secret, unfreeze pattern)
  - _bmad-output/stories/1-6-pipl-account-delete.md (deleted/tombstoned users; preserve audit/billing references)
  - apps/auth-service/src/auth_service/models.py (User, RiskFlag, AuditLog, AccountDeletionRequest)
  - apps/auth-service/src/auth_service/admin_routes.py (X-Admin-Secret admin endpoint pattern)
  - apps/auth-service/src/auth_service/routes.py (JWT auth, active-account gate, login/frozen checks)
  - apps/web/src/app/auth/account/page.tsx (minimal account-area UI pattern)
dependencies:
  upstream:
    - 1-5-risk-control-freeze (done) — provides risk_flags evidence, users.is_frozen, and admin unfreeze pattern
    - 1-6-pipl-account-delete (done) — defines deleted/tombstoned user boundary to avoid merging deleted accounts
    - 1-2-user-login (done) — login/OTP already block frozen users, so merge acceptance must unfreeze the kept account
  downstream:
    - 1-12-j7-fraud-freeze-vertical-slice — will surface this flow inside the full appeal UX
    - 5-b-1-five-plans-subscription — may later turn "Starter ¥39" into real billing/subscription upgrade
---

# Story 1.7 — Account Merge Proposal + 48h Review (FR A7/A8)

## User Story

**As** a frozen user who may have triggered fraud controls while helping teammates or classmates register,
**I want** to submit an account merge proposal and receive either a 48-hour human review or deterministic auto-score decision,
**so that** a false-positive freeze can be resolved by keeping one account, retiring duplicate accounts, and restoring access to the kept account.

## Why this story

Story 1.5 gives the platform the freeze mechanism and evidence log (`risk_flags`). Story 1.6 defines a deletion/tombstone boundary that must not be confused with account recovery. The missing J7 bridge is the recovery state machine:

1. A frozen user can submit a merge proposal that names the account to keep and duplicate accounts to retire.
2. The proposal records evidence and a review SLA.
3. Standard mode (`team_size >= 3`) queues the proposal for admin review due within 48 hours.
4. Solo/lean mode (`team_size <= 2`) computes an auto-score; score >= 0.70 can auto-approve.
5. Accepting an approved merge unfreezes the kept account and freezes/retire-marks duplicate accounts without deleting audit or billing history.

This story is intentionally smaller than the full J7 vertical slice: it creates the backend + minimal account page entry point that Story 1.12 can later wrap in a complete appeal UX.

## Out of scope

- Full J7申诉表单, no-login email tracking link, and one-minute guided appeal UX — Story 1.12 owns it.
- Real billing upgrade to Starter ¥39 — this story only records `starter_upgrade_recommended=true` in metadata; billing plans ship under Epic 5.B.
- Admin RBAC / admin user table — v1 continues the Story 1.5 `X-Admin-Secret` shared-secret pattern.
- Cross-service merge of billing ledgers, solver history, chat history, files, or invoices — v1 preserves references and records merge intent; later service-specific migrations can consume the audit trail.
- Physical deletion of duplicate accounts — duplicate user rows are freeze-retired, not deleted, to preserve audit/billing references.
- Merging soft-deleted or PIPL hard-deleted tombstone accounts — these are rejected.

## Acceptance Criteria

### AC1: Merge proposal data model

Add `account_merge_proposals` to `infra/local-init/01-schema.sql` and `apps/auth-service/src/auth_service/models.py`.
Also extend `users` with merge-retirement markers:
- `merged_into_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL`
- `merged_at TIMESTAMPTZ NULL`

Required fields:
- `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
- `requester_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
- `primary_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
- `duplicate_user_ids UUID[] NOT NULL`
- `evidence JSONB NOT NULL DEFAULT '{}'::jsonb`
- `status VARCHAR(32) NOT NULL DEFAULT 'pending_review'`
- `review_mode VARCHAR(16) NOT NULL` with values `human` or `auto`
- `auto_score NUMERIC(4, 2) NULL`
- `review_due_at TIMESTAMPTZ NOT NULL`
- `reviewed_at TIMESTAMPTZ NULL`
- `reviewed_by VARCHAR(255) NULL`
- `decision_reason TEXT NULL`
- `accepted_at TIMESTAMPTZ NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

Indexes:
- `idx_account_merge_proposals_requester_created_at`
- `idx_account_merge_proposals_status_due`
- `idx_users_merged_into` on `users(merged_into_user_id)` where `merged_into_user_id IS NOT NULL`

Allowed statuses:
- `pending_review`
- `approved`
- `rejected`
- `auto_approved`
- `accepted`
- `cancelled`

### AC2: Frozen users can submit proposals

Add authenticated `POST /v1/auth/account-merge-proposals`.

Request:
```json
{
  "primary_user_id": "uuid",
  "duplicate_user_ids": ["uuid"],
  "evidence": {
    "reason": "我帮室友注册",
    "contact_email": "user@example.com",
    "supporting_note": "optional short note",
    "team_size": 2
  }
}
```

Pydantic validation:
- `primary_user_id: UUID`
- `duplicate_user_ids: list[UUID]` with `min_length=1`
- `evidence.reason: str` with `min_length=4`, `max_length=500`
- `evidence.contact_email: EmailStr`
- `evidence.supporting_note: str | None` with `max_length=1000`
- `evidence.team_size: int | None` with `ge=1`, `le=50`

Behavior:
- Requires Bearer access JWT.
- Requester must exist, must not be `deleted_at`, and should normally be frozen.
- If requester is not frozen, return `409` with detail `"account is not frozen"`.
- `primary_user_id` must equal the requester in v1. This avoids privilege escalation where one frozen account tries to claim another user's identity.
- `duplicate_user_ids` must be non-empty, unique, and must not include `primary_user_id`.
- Every duplicate user must exist, must not be soft-deleted/tombstoned, and must share at least one merge signal with the requester: same email domain, both sides have `risk_flags`, or existing `risk_flags.metadata` evidence naming the duplicate user id.
- Reject any proposal involving a deleted account or an already retired duplicate account (`users.merged_at IS NOT NULL`).
- Create one proposal row and write `audit_logs` action `account_merge.proposed`.
- Return proposal status, review mode, due time, score if any, and next action.

### AC3: Review mode and auto-score decision

Review mode is determined from `evidence.team_size`:
- `team_size >= 3` => `review_mode="human"`, `status="pending_review"`, `review_due_at = now + 48 hours`
- `team_size <= 2` or omitted => `review_mode="auto"`, `review_due_at = now + 24 hours`

Auto-score is deterministic and local:
- Start from `0.50`
- Add `0.20` if requester and every duplicate share the same email domain.
- Add `0.20` if requester and every duplicate have at least one `risk_flags` row.
- Add `0.10` if evidence reason length is >= 8 characters.
- Cap at `1.00`.

If auto-score >= `0.70`, proposal becomes `auto_approved` immediately and writes `audit_logs` action `account_merge.auto_approved`.
If auto-score < `0.70`, proposal remains `pending_review` for admin review.

### AC4: Users can inspect and accept approved proposals

Add:
- `GET /v1/auth/account-merge-proposals`
- `POST /v1/auth/account-merge-proposals/{proposal_id}/accept`

Behavior:
- GET lists proposals where the authenticated user is `requester_user_id`, newest first.
- Accept is allowed only for `approved` or `auto_approved` proposals owned by the requester.
- Accept is idempotent: accepting an already accepted proposal returns the accepted state.
- Accepting a proposal:
  - sets proposal `status="accepted"` and `accepted_at=now`
  - clears `users.is_frozen=false` on `primary_user_id`
  - keeps duplicate users present but sets `is_frozen=true`
  - sets duplicate users' `merged_into_user_id=primary_user_id` and `merged_at=now`
  - revokes all active API keys owned by duplicate users (`api_keys.revoked_at=now`) so retired duplicate accounts cannot continue solver access through pre-existing keys
  - writes `audit_logs` action `account_merge.accepted`
  - records metadata with `primary_user_id`, `duplicate_user_ids`, and `starter_upgrade_recommended=true`
- Accept never deletes users, API keys, risk flags, deletion requests, audit logs, or billing rows.

### AC5: Admin queue and review endpoints

Extend `apps/auth-service/src/auth_service/admin_routes.py` using the existing `require_admin_secret`.

Add:
- `GET /v1/admin/account-merge-proposals?status=pending_review`
- `POST /v1/admin/account-merge-proposals/{proposal_id}/review`

Review request:
```json
{
  "decision": "approve",
  "reason": "证据足够，保留主账户"
}
```

Behavior:
- Queue endpoint returns proposal rows with requester, primary, duplicate ids, evidence, status, review mode, score, due time, and created time.
- Review accepts `decision="approve"` or `decision="reject"`.
- Approve moves `pending_review` to `approved`.
- Reject moves `pending_review` to `rejected`.
- Admin review writes `audit_logs` action `account_merge.reviewed`.
- Reviewing an already terminal proposal returns `409`.

### AC6: Minimal account-area UI

Extend `apps/web/src/app/auth/account/page.tsx` instead of creating a new navigation area.

UI requirements:
- Uses the existing sessionStorage JWT guard.
- Shows a compact "账户合并" section below account deletion.
- Uses `sessionStorage.user_id` as the read-only primary account id. Do not ask the user to type their own primary id.
- Lets the user submit comma-separated duplicate ids, reason, contact email, and team size.
- Lists existing proposals with status, review mode, score, and due time.
- Shows an "接受合并" action only for `approved` / `auto_approved` proposals.
- Keeps copy factual: "接受后保留主账户，重复账户会保持冻结，审计与账单记录保留。"

### AC7: Tests cover lifecycle and security boundaries

Backend tests in `apps/auth-service/tests/test_account_merge.py`:
1. frozen requester can create auto-approved proposal when score >= 0.70
2. non-frozen requester receives 409
3. proposal rejects deleted/tombstoned duplicate accounts
4. proposal rejects duplicates that do not share an allowed merge signal
5. human-mode proposal appears in admin queue with a 48-hour due time
6. admin approve enables user accept; accept unfreezes primary and freezes duplicates
7. admin reject prevents accept
8. accept is idempotent
9. proposal creation and accept write audit logs
10. proposal cannot claim another primary account (`primary_user_id != requester_user_id` => 403/422)
11. accepting a proposal revokes duplicate users' active API keys
12. accepted duplicate users get `merged_into_user_id` and `merged_at`, and retired users cannot be used in a second proposal

Frontend API client tests in `apps/web/src/lib/account-merge.test.ts`:
- POST proposal includes Bearer token and request body.
- GET proposals includes Bearer token.
- POST accept uses proposal id path and Bearer token.

### AC8: Quality gates

Run and pass:
- `uv run pytest apps/auth-service/tests/test_account_merge.py -q`
- `uv run pytest apps/auth-service/tests/ -q`
- `uv run ruff check apps/auth-service/src/auth_service apps/auth-service/tests/test_account_merge.py`
- `pnpm --filter @opticloud/web test`
- `pnpm --filter @opticloud/web typecheck`

## Tasks / Subtasks

- [x] Task 1: Add merge proposal schema and models (AC: 1)
  - [x] Add `account_merge_proposals` table and indexes to `infra/local-init/01-schema.sql`
  - [x] Add `users.merged_into_user_id` and `users.merged_at` with an idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
  - [x] Add `AccountMergeProposal` ORM model
  - [x] Add Pydantic request/response schemas

- [x] Task 2: Implement merge service logic (AC: 2, 3, 4)
  - [x] Create `apps/auth-service/src/auth_service/account_merge.py`
  - [x] Validate requester/primary/duplicate boundaries
  - [x] Implement deterministic auto-score
  - [x] Implement accept transition without deleting any rows

- [x] Task 3: Add auth-service user endpoints (AC: 2, 4)
  - [x] Add `POST /v1/auth/account-merge-proposals`
  - [x] Add `GET /v1/auth/account-merge-proposals`
  - [x] Add `POST /v1/auth/account-merge-proposals/{proposal_id}/accept`
  - [x] Write proposal/auto-approval/accept audit logs

- [x] Task 4: Add admin review surface (AC: 5)
  - [x] Add admin queue endpoint
  - [x] Add admin review endpoint
  - [x] Reuse `X-Admin-Secret` and constant-time gate
  - [x] Write admin review audit log

- [x] Task 5: Add minimal account UI and TS client helpers (AC: 6)
  - [x] Add TS interfaces and functions in `apps/web/src/lib/api.ts`
  - [x] Extend `/auth/account` with merge proposal form/list/accept action
  - [x] Add frontend API client tests

- [x] Task 6: Add lifecycle tests and run quality gates (AC: 7, 8)
  - [x] Add backend lifecycle/security tests
  - [x] Run targeted and full auth-service tests
  - [x] Run web tests and typecheck
  - [x] Update sprint status after implementation and code review

### Review Findings

- [x] [Review][Patch] Retired duplicate accounts could use pre-existing JWTs to create new API keys after merge acceptance [apps/auth-service/src/auth_service/routes.py] — fixed by making `_require_active_user` reject `users.merged_at IS NOT NULL` and `users.is_frozen=true`, while keeping merge proposal endpoints on the frozen-account-compatible JWT resolver.

## Dev Notes

- Keep implementation in `auth-service`; account identity owns freeze/merge state in v1.
- Reuse `admin_routes.require_admin_secret`; do not introduce a second admin auth mechanism.
- Reuse `_resolve_user_from_jwt` / `_resolve_active_user_from_jwt` patterns in `routes.py`, but proposal creation must allow a frozen account. Do not use a helper that rejects `is_frozen` for this endpoint.
- Deleted users are not mergeable. Check `deleted_at IS NULL` and reject tombstone emails like `deleted-...@invalid.local`.
- Do not delete duplicate users. Freeze-retire them and preserve references. This follows the 1.6 code-review finding that deleting `users` risks cascading into billing/audit history.
- Freeze alone does not stop existing API keys in `solver-orchestrator.auth.verify_api_key`; accept must revoke duplicate users' active keys in the same transaction.
- `users.merged_at` is the authoritative v1 marker that a duplicate account has already been retired into another primary account; do not infer this solely from old proposal rows.
- Keep all transitions idempotent where possible. `accept` should be safe to retry.
- The first v1 auto-score is deliberately simple and deterministic. Do not call external fraud/LLM services.
- Store evidence as JSONB but avoid relying on free-form evidence for authorization except the explicitly allowed duplicate-id metadata signal.
- UI must read primary id from `sessionStorage.user_id`, matching login/signup storage behavior. If it is missing, show a compact error asking the user to log in again rather than accepting a typed primary id.
- Frontend should stay utilitarian and compact inside `/auth/account`; no new landing page or full appeal wizard.

### Project Structure Notes

- Primary backend files:
  - `apps/auth-service/src/auth_service/models.py`
  - `apps/auth-service/src/auth_service/schemas.py`
  - `apps/auth-service/src/auth_service/routes.py`
  - `apps/auth-service/src/auth_service/admin_routes.py`
  - `apps/auth-service/src/auth_service/account_merge.py`
- Primary test files:
  - `apps/auth-service/tests/test_account_merge.py`
  - `apps/web/src/lib/account-merge.test.ts`
- Primary frontend files:
  - `apps/web/src/lib/api.ts`
  - `apps/web/src/app/auth/account/page.tsx`
- Schema file:
  - `infra/local-init/01-schema.sql`

### References

- [Source: _bmad-output/planning/epics.md#Story 1.7]
- [Source: _bmad-output/planning/prd.md#Journey 7]
- [Source: _bmad-output/planning/ux-design-specification.md#J7]
- [Source: _bmad-output/stories/1-5-risk-control-freeze.md]
- [Source: _bmad-output/stories/1-6-pipl-account-delete.md]
- [Source: apps/auth-service/src/auth_service/admin_routes.py]
- [Source: apps/auth-service/src/auth_service/routes.py]
- [Source: apps/web/src/app/auth/account/page.tsx]

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-20: `$env:PYTHONPATH='apps/auth-service/src;packages/shared-py;apps/solver-orchestrator/src'; uv run --isolated --package opticloud-auth-service --extra dev python -m pytest apps/auth-service/tests/test_account_merge.py -q` -> 11 passed
- 2026-05-20: `$env:PYTHONPATH='apps/auth-service/src;packages/shared-py;apps/solver-orchestrator/src'; uv run --isolated --package opticloud-auth-service --extra dev python -m pytest apps/auth-service/tests/ -q` -> 53 passed
- 2026-05-20: `$env:PYTHONPATH='apps/auth-service/src;packages/shared-py;apps/solver-orchestrator/src'; uv run --isolated --package opticloud-auth-service --extra dev ruff check apps/auth-service/src/auth_service apps/auth-service/tests/test_account_merge.py` -> passed
- 2026-05-20: `pnpm --filter @opticloud/web test` -> 7 files / 43 tests passed
- 2026-05-20: `pnpm --filter @opticloud/web typecheck` -> passed

### Completion Notes List

- Added account merge proposal persistence, user retirement markers, and idempotent local schema bootstrap for older dev/test databases.
- Added user proposal lifecycle endpoints and admin review endpoints under the existing shared-secret admin surface.
- Implemented deterministic auto-score, 48h human review queue, accepted-state transition, duplicate account retirement, and duplicate API key revocation.
- Extended `/auth/account` with a compact account merge section that uses `sessionStorage.user_id` as the read-only primary account id.
- Post-implementation code review fixed a retired-account access-control gap: merged accounts can no longer use old JWTs to create/list/revoke API keys or submit new merge proposals.

### File List

- `_bmad-output/stories/1-7-account-merge-proposal.md`
- `_bmad-output/stories/sprint-status.yaml`
- `infra/local-init/01-schema.sql`
- `apps/auth-service/src/auth_service/account_merge.py`
- `apps/auth-service/src/auth_service/admin_routes.py`
- `apps/auth-service/src/auth_service/models.py`
- `apps/auth-service/src/auth_service/routes.py`
- `apps/auth-service/src/auth_service/schemas.py`
- `apps/auth-service/tests/conftest.py`
- `apps/auth-service/tests/test_account_merge.py`
- `apps/web/src/app/auth/account/page.tsx`
- `apps/web/src/lib/account-merge.test.ts`
- `apps/web/src/lib/api.ts`

## Senior Developer Review (AI)

### Review Date

2026-05-20

### Reviewed By

GPT-5

### Review Summary

- Decision-needed: 0
- Patch findings: 1 fixed
- Deferred: 0
- Dismissed: 2 candidate findings were rejected as already covered or out of scope.

### Findings and Actions

- Fixed: Accepting a merge revoked duplicate API keys but did not prevent a retired duplicate account from using an old JWT to create fresh API keys. `_require_active_user` now blocks merged and frozen users; merge proposal endpoints still use `_resolve_user_from_jwt` so frozen users can submit/accept proposals as intended.
- Verified: Fresh schema has `users.merged_into_user_id` as a real foreign key in `CREATE TABLE users`, plus idempotent `ALTER TABLE` compatibility for older local DBs.
- Verified: Admin review, proposal creation, auto-score, accepted transition, audit logging, duplicate key revocation, and frontend client helpers are covered by tests.

## Story Review Round 1

### Findings

- High: Accepting a merge only froze duplicate users. Existing solver API-key verification rejects revoked/expired keys but does not currently check `users.is_frozen`, so duplicate accounts could keep using old API keys after "retirement".
- Medium: "same phone" was listed as a merge signal, but `users.phone` is unique in the current schema. It is not a practical v1 duplicate signal unless future identity aliasing exists.

### Revisions Applied

- AC4 now requires revoking all active API keys for duplicate users during accept.
- AC7 adds an explicit backend test for duplicate API-key revocation.
- Dev Notes call out the solver-orchestrator boundary so implementation cannot rely on freeze alone.
- AC2 merge signals now use same email domain / bilateral risk flags / explicit risk metadata, not same phone.

## Story Review Round 2

### Findings

- High: The initial story said to reject "already accepted duplicate accounts" but did not define a reliable per-user marker. Scanning `account_merge_proposals.duplicate_user_ids` arrays would be fragile and easy to miss in future cross-service code.
- Medium: Without a per-user retirement marker, duplicate accounts could be included in multiple approved proposals, causing confusing audit history and repeated API-key revocation.

### Revisions Applied

- AC1 now adds `users.merged_into_user_id` and `users.merged_at` plus a partial index.
- AC2 now rejects duplicate users where `merged_at IS NOT NULL`.
- AC4 now requires accept to set the per-user retirement markers on duplicates.
- AC7 now includes a test that retired duplicate users cannot be reused in a second proposal.
- Dev Notes identify `users.merged_at` as the authoritative v1 retirement marker.

## Story Review Round 3

### Findings

- Medium: AC6 initially asked users to type `primary_user_id`, which is both poor UX and an avoidable source of incorrect proposals. The current auth pages already store `user_id` in sessionStorage after signup/login.
- Medium: The request schema allowed `evidence` to look like arbitrary JSON. Without explicit validation, implementation could accept empty reasons, malformed contact emails, or unrealistic team sizes.

### Revisions Applied

- AC6 now requires the UI to use `sessionStorage.user_id` as the read-only primary account id and to error if it is unavailable.
- AC2 now includes explicit Pydantic validation constraints for proposal evidence and duplicate ids.
- Dev Notes now instruct implementation not to accept a typed primary id from the account page.
