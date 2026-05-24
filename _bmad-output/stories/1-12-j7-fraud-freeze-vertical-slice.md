---
story_key: 1-12-j7-fraud-freeze-vertical-slice
epic_num: 1
story_num: 1.12
epic_name: Account & Identity
status: done
priority: High (J7 / FR A5+A7+A8; frozen-account recovery path)
sizing: M-L (~1 day; auth appeal token + web appeal page + focused tests + E2E)
type: implementation + ux + security + test
created_by: bmad-create-story
created_at: 2026-05-24
sources:
  - _bmad-output/planning/epics.md:1343
  - _bmad-output/planning/prd.md:595
  - _bmad-output/planning/prd.md:1440
  - _bmad-output/planning/prd.md:1442
  - _bmad-output/planning/prd.md:1443
  - _bmad-output/planning/ux-design-specification.md:2497
  - _bmad-output/stories/1-5-risk-control-freeze.md
  - _bmad-output/stories/1-7-account-merge-proposal.md
  - _bmad-output/stories/1-11-geo-anomaly-risk.md
dependencies:
  upstream:
    - 1-5-risk-control-freeze (done) — provides users.is_frozen, risk_flags, admin unfreeze, and frozen login/OTP behavior
    - 1-7-account-merge-proposal (done) — provides account_merge_proposals, deterministic auto-score, admin queue/review, accept transition
    - 1-11-geo-anomaly-risk (done) — provides safe API-key risk warning/evidence data and geo_anomaly risk_flags
  downstream:
    - 8-a-4-user-audit-logs — can expose appeal/proposal status history to users
    - 5-b-1-five-plans-subscription — can turn the J7 "Starter ¥39" recommendation into a real plan upgrade
---

# Story 1.12 — J7 风控冻结申诉 Vertical Slice

## User Story

**As** a frozen user,
**I want** login to explain why access is blocked and guide me into a short self-service appeal flow,
**so that** I can submit evidence, track review status without logging in, and recover access through the existing account-merge proposal path.

## Why this story

Journey 7 requires a complete user-visible recovery path: friendly freeze message, appeal form, 48h human review for teams, 24h/auto review for solo users, status tracking via email-style link, account-merge proposal, and access recovery. Stories 1.5 and 1.7 shipped the backend freeze and merge mechanics, but the user still has no clear no-login recovery path when `/otp/request` or `/login` returns `account frozen`.

This story closes the Epic 1 J7 vertical slice by adding:

1. frozen-login errors with a `next_action_url` pointing to the appeal page;
2. a short-lived tracking-token record for no-login appeal status;
3. public-but-token-gated appeal endpoints that reuse Story 1.7 merge proposal logic;
4. a dedicated `/auth/frozen-appeal` page with concise zh-CN copy;
5. focused backend, frontend, and Playwright coverage for the path.

## Out of Scope

- New fraud detection rules. Story 1.12 consumes `is_frozen` and `risk_flags`; it does not alter freeze thresholds.
- Admin RBAC or a new admin dashboard. Story 1.7's existing `X-Admin-Secret` admin review endpoints remain the admin surface.
- Real email delivery. v1 returns a tracking URL/token in the API response so the web flow can work locally; production email handoff is a later notification story.
- Real Starter ¥39 billing upgrade. Acceptance records/reuses the existing `starter_upgrade_recommended=true` metadata only.
- Deleting duplicate accounts or modifying billing/solver history.
- Changing API-key geo anomaly scoring.
- Creating a marketing landing page.

## Acceptance Criteria

### AC1: Frozen auth failures include recovery guidance

- `POST /v1/auth/otp/request` and `POST /v1/auth/login` still return 403 for frozen accounts.
- For `account frozen`, the response body uses the existing web-client-compatible RFC 7807 shape:
  - `status: 403`
  - `title: "账户已冻结"`
  - `detail: "account frozen"`
  - `next_action_url: "/auth/frozen-appeal"`
  - `errors[0].remediation_hint_key: "auth.frozen.appeal"`
- Existing tests that assert `"frozen" in response.json()["detail"]` must keep passing.
- Missing, deleted, merged, invalid OTP, and non-frozen failures keep their current behavior.
- Login UI shows a clear zh-CN appeal action for frozen errors instead of the current "contact support" dead end.

### AC2: Appeal tracking persistence is added without replacing merge proposals

- Add `account_freeze_appeals` to `infra/local-init/01-schema.sql` and an idempotent migration `infra/local-init/10-freeze-appeals.sql`.
- Required columns:
  - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
  - `proposal_id UUID NULL REFERENCES account_merge_proposals(id) ON DELETE SET NULL`
  - `tracking_token_hash TEXT NOT NULL UNIQUE`
  - `status VARCHAR(32) NOT NULL DEFAULT 'started'`
  - `contact_email VARCHAR(255) NOT NULL`
  - `expires_at TIMESTAMPTZ NOT NULL`
  - `last_viewed_at TIMESTAMPTZ NULL`
  - `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  - `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- Allowed appeal statuses: `started`, `proposal_submitted`, `accepted`, `expired`.
- Add indexes:
  - `idx_account_freeze_appeals_user_created_at`
  - `idx_account_freeze_appeals_proposal`
  - `idx_account_freeze_appeals_expires_at`
- Add matching SQLAlchemy model and local test-schema bootstrap for old dev databases.
- Wire `10-freeze-appeals.sql` into auth-service CI schema setup and the auth-service path filter. Do not add it to solver-orchestrator schema setup because solver does not read this table.

### AC3: No-login appeal start endpoint identifies eligible frozen accounts

- Add `POST /v1/auth/frozen-appeals/start`.
- Request body: `{ phone: string, email: string }` using the same phone/email validation as login.
- Behavior:
  - lookup by exact phone + normalized email;
  - reject deleted or merged accounts with current account-state error semantics;
  - if user is not found, return 404 `user not found` to match current `/otp/request`;
  - if user is not frozen, return 409 `account is not frozen`;
  - for frozen users, create a fresh appeal row with `expires_at = now + 24h`;
  - if the user already has a non-terminal merge proposal (`pending_review`, `approved`, or `auto_approved`), link the new appeal row to that proposal so a user who lost the prior tracking link can recover status with phone+email;
  - generate a URL-safe tracking token and store only an HMAC-SHA256 hash using a dedicated `FREEZE_APPEAL_TOKEN_PEPPER_DEV` setting;
  - write `audit_logs` action `freeze_appeal.started`.
- Response includes:
  - `appeal_id`
  - `status`
  - `user_id` as the read-only primary account id for the proposal form
  - `tracking_token`
  - `tracking_url`
  - `expires_at`
  - `risk_summary` with only safe fields: total flag count, latest rule codes, latest flag timestamp, and current `risk_score`.
  - `proposal` and `next_action` if an existing non-terminal proposal was linked.
- Never expose raw risk flag metadata, full IPs, API key hashes, or full API keys.

### AC4: Token-gated appeal proposal submission reuses Story 1.7 merge logic

- Add `POST /v1/auth/frozen-appeals/{appeal_id}/proposal`.
- Request body:
  - `tracking_token: string`
  - `duplicate_user_ids: UUID[]`
  - `reason: string` (`min_length=4`, `max_length=500`)
  - `contact_email: EmailStr`
  - `supporting_note?: string | null` (`max_length=1000`)
  - `team_size?: int | null` (`ge=1`, `le=50`)
- Validate the appeal id + tracking token with constant-time comparison.
- Reject expired appeals with 403 and mark status `expired`.
- Use `appeal.user_id` as `primary_user_id`; the request must not accept a typed primary id.
- If the appeal is already linked to a proposal, return 409 `appeal already has proposal` instead of creating a duplicate proposal.
- Call `account_merge.create_merge_proposal()` with the existing request schema and rules.
- Store `proposal_id`, set appeal status to `proposal_submitted`, update `contact_email`, and write `audit_logs` action `freeze_appeal.proposal_submitted`.
- Return an appeal status response that includes the embedded account merge proposal response.
- Auto-score and human-review behavior must remain exactly Story 1.7's behavior.

### AC5: Token-gated status and accept endpoints complete the recovery loop

- Add:
  - `GET /v1/auth/frozen-appeals/{appeal_id}?tracking_token=...`
  - `POST /v1/auth/frozen-appeals/{appeal_id}/accept`
- Both validate token, expiry, and appeal ownership.
- Token validation must recompute the HMAC hash and use `secrets.compare_digest`; never query by or compare the raw token.
- GET updates `last_viewed_at` and returns:
  - appeal id/status/expires_at/last_viewed_at;
  - safe risk summary;
  - proposal response if a proposal exists;
  - `next_action` derived from proposal status: `submit_proposal`, `await_review`, `accept_merge`, `completed`, or `contact_support`.
- Accept:
  - requires a linked proposal in `approved` or `auto_approved`;
  - calls existing `account_merge.accept_merge_proposal(session, appeal.user_id, proposal_id)`;
  - sets appeal status `accepted`;
  - writes `audit_logs` action `freeze_appeal.accepted`;
  - is idempotent if the linked proposal is already accepted.
- Accept must preserve Story 1.7 invariants: primary is unfrozen, duplicates are freeze-retired, duplicate API keys are revoked, no rows are deleted.

### AC6: Dedicated frozen appeal page provides the J7 user experience

- Add `/auth/frozen-appeal`.
- Page requirements:
  - prefill phone/email from query params when present, but do not require them;
  - keep the primary path to three compact steps so the self-service flow can be completed in about 1 minute when the user has duplicate account ids ready;
  - Step 1: phone + email, start appeal;
  - Step 2: show safe risk summary and submit duplicate account ids, reason, contact email, team size, and optional note;
  - Step 3: show proposal status, review mode, score, due time, and next action;
  - show "接受合并" only when proposal status is `approved` or `auto_approved`;
  - after accepted, show concise success copy and a link back to login.
- Copy must be factual and non-panic:
  - "账户已触发风控冻结"
  - "提交后可用此页面查看复审状态"
  - "接受后保留主账户，重复账户会保持冻结，审计与账单记录保留"
- Use existing `StatusCard`/plain form patterns; no new design system component is required.
- Use stable `data-testid` hooks for focused page tests.
- Login page 403 frozen state links to `/auth/frozen-appeal?phone=...&email=...`.
- Store the returned tracking token in `sessionStorage` only for the current browser session so refresh does not lose progress; never put it in `localStorage`.

### AC7: Tests cover backend lifecycle, web API, page behavior, and J7 E2E

- Backend tests in `apps/auth-service/tests/test_frozen_appeals.py` cover:
  1. frozen OTP/login responses include `next_action_url`;
  2. start appeal succeeds for frozen user and stores only token hash;
  3. start appeal rejects non-frozen user;
  4. invalid token cannot read/submit/accept;
  5. submit proposal creates/links an auto-approved proposal using existing merge scoring;
  6. status endpoint returns safe risk summary and proposal next action;
  7. accept via tracking token unfreezes primary, retires duplicate, revokes duplicate keys;
  8. expired appeal is rejected and marked expired;
  9. audit logs are written for start, submit, and accept.
- Frontend API client tests cover new helpers:
  - `startFrozenAppeal`
  - `getFrozenAppeal`
  - `submitFrozenAppealProposal`
  - `acceptFrozenAppeal`
- Web page tests cover:
  - login frozen error renders appeal CTA;
  - frozen appeal page start -> submit -> accept happy path with mocked API helpers.
- Add one Playwright test under `e2e/tests/j7-frozen-appeal.spec.ts` that exercises the user-facing page flow with route-level API mocks. It should validate UI behavior, not seed a real Postgres database.
- The Playwright test should be Chromium-only and route-mocked so it can run in the existing `@opticloud/e2e` package without seeded auth-service or solver services.
- Focused quality gates:
  - `uv run pytest apps/auth-service/tests/test_frozen_appeals.py -q`
  - `uv run pytest apps/auth-service/tests -q`
  - `uv run ruff check apps/auth-service/src/auth_service apps/auth-service/tests/test_frozen_appeals.py`
  - `pnpm --filter @opticloud/web test -- frozen-appeal login`
  - `pnpm --filter @opticloud/web test`
  - `pnpm --filter @opticloud/web typecheck`
  - `pnpm --filter @opticloud/e2e test -- j7-frozen-appeal.spec.ts`
  - `uv run mypy apps packages`
  - `git diff --check`

## Tasks / Subtasks

- [x] Task 1: Add appeal persistence and schema wiring (AC: 2)
  - [x] Add `account_freeze_appeals` to `01-schema.sql`.
  - [x] Add `10-freeze-appeals.sql`.
  - [x] Add `AccountFreezeAppeal` ORM model.
  - [x] Update auth-service test schema bootstrap for old local DBs.
  - [x] Wire migration into auth-service CI schema setup/path filters only.

- [x] Task 2: Add frozen-error and appeal API contracts (AC: 1, 3, 4, 5)
  - [x] Add Pydantic schemas for frozen appeal start/status/submit/accept.
  - [x] Add token generation/hash helpers using a dedicated freeze-appeal token pepper; store only token hash.
  - [x] Add a helper for RFC7807-compatible frozen auth responses.
  - [x] Add start/status/proposal/accept endpoints.
  - [x] Reuse `account_merge.create_merge_proposal()` and `accept_merge_proposal()`; do not duplicate merge logic.

- [x] Task 3: Add backend tests (AC: 7)
  - [x] Add `test_frozen_appeals.py`.
  - [x] Cover token security, expiry, safe risk summary, proposal linking, accept invariants, and audit logs.
  - [x] Update existing login/risk tests only if the frozen error body shape requires assertion changes.

- [x] Task 4: Add web API helpers and tests (AC: 6, 7)
  - [x] Extend `apps/web/src/lib/api.ts`.
  - [x] Add `apps/web/src/lib/frozen-appeal.test.ts`.
  - [x] Ensure `OptiCloudClientError` handles RFC7807 frozen body and legacy FastAPI detail bodies.

- [x] Task 5: Add J7 UI surfaces (AC: 1, 6, 7)
  - [x] Update login page frozen error copy and appeal CTA.
  - [x] Add `/auth/frozen-appeal` page.
  - [x] Add happy-dom page tests for login CTA and frozen appeal flow.
  - [x] Add route-mocked Chromium-only Playwright `j7-frozen-appeal.spec.ts` in the existing `@opticloud/e2e` package.

- [x] Task 6: Verification and story tracking (AC: 7)
  - [x] Run backend focused and full auth tests.
  - [x] Run web focused tests, full web tests, and typecheck.
  - [x] Run E2E focused test if route-mocked and locally feasible.
  - [x] Run mypy and diff-check.
  - [x] Update Dev Agent Record, File List, Change Log.
  - [x] Move sprint status to `review` only after implementation gates pass.

### Review Findings

- [x] [Review][Patch] Frozen users with existing JWTs could still reach protected routes [apps/auth-service/src/auth_service/routes.py:347] — Fixed `_require_active_user()` to raise `403 account frozen` for JWT-gated routes and added a regression test covering API-key creation with a pre-freeze JWT.

## Dev Notes

- This story must not invent a second merge implementation. Use `account_merge.create_merge_proposal()` and `account_merge.accept_merge_proposal()` as the source of truth.
- Public frozen-appeal endpoints are token-gated, not JWT-gated. Validate tokens with HMAC hash + constant-time compare.
- Add `freeze_appeal_token_pepper_dev` to `apps/auth-service/src/auth_service/config.py`; do not reuse API-key or guardian-consent peppers.
- Do not store or log the raw tracking token. Return it once so v1 can simulate an email tracking link.
- The tracking token is equivalent to an email-link bearer secret. Treat it like a password in logs and tests.
- Keep the appeal token TTL at 24h for v1. Admin human review can still take 48h; if the token expires, the user can start a new appeal and the old proposal remains in the admin queue.
- The page may keep the raw token in component state/sessionStorage, but never localStorage.
- Browser page tests can mock API helpers directly; the Playwright test should validate the route-mocked browser flow, not the database integration.
- Phone/email prefill from query params is convenience only. The backend must always look up the user by submitted phone/email.
- `risk_summary` must be safe: counts and rule codes only. Do not return raw `risk_flags.metadata` because Story 1.11 metadata may include IP addresses.
- Use `detail: "account frozen"` in frozen RFC7807 bodies to preserve existing tests and client logic.
- When an appeal is accepted, rely on Story 1.7 to revoke duplicate API keys. Do not reimplement API-key revocation in the appeal module.
- Expired appeal handling should be deterministic: if `expires_at <= now`, set status `expired`, flush, and return 403.
- For Playwright, route-mock the API calls from the browser. Do not require real auth-service, seeded users, or Postgres just to validate the UI journey.

### Project Structure Notes

- Backend:
  - `apps/auth-service/src/auth_service/models.py`
  - `apps/auth-service/src/auth_service/schemas.py`
  - `apps/auth-service/src/auth_service/routes.py`
  - `apps/auth-service/src/auth_service/account_merge.py` (reuse only)
  - new `apps/auth-service/src/auth_service/frozen_appeals.py`
- Backend tests:
  - new `apps/auth-service/tests/test_frozen_appeals.py`
  - update `apps/auth-service/tests/conftest.py`
- Web:
  - `apps/web/src/lib/api.ts`
  - `apps/web/src/app/auth/login/page.tsx`
  - new `apps/web/src/app/auth/frozen-appeal/page.tsx`
  - new page tests under matching app folders
- E2E:
  - `e2e/tests/j7-frozen-appeal.spec.ts`
- Schema:
  - `infra/local-init/01-schema.sql`
  - `infra/local-init/10-freeze-appeals.sql`
- CI:
  - `.github/workflows/ci.yml`

### References

- [Source: _bmad-output/planning/epics.md:1343]
- [Source: _bmad-output/planning/prd.md:595]
- [Source: _bmad-output/planning/ux-design-specification.md:2497]
- [Source: _bmad-output/stories/1-5-risk-control-freeze.md]
- [Source: _bmad-output/stories/1-7-account-merge-proposal.md]
- [Source: _bmad-output/stories/1-11-geo-anomaly-risk.md]

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- `uv run pytest apps/auth-service/tests/test_frozen_appeals.py -q` — 10 passed.
- `uv run pytest apps/auth-service/tests/test_frozen_appeals.py apps/auth-service/tests/test_api_keys_routes.py -q` — 21 passed.
- `uv run pytest apps/auth-service/tests -q` — 72 passed.
- `uv run ruff check apps/auth-service/src/auth_service apps/auth-service/tests/test_frozen_appeals.py` — passed.
- `pnpm --dir apps/web test -- frozen-appeal login` — 3 files / 6 tests passed.
- `pnpm --dir apps/web test` — 15 files / 70 tests passed.
- `pnpm --dir apps/web typecheck` — passed.
- `pnpm --dir e2e exec playwright test j7-frozen-appeal.spec.ts --project=chromium` — 1 passed.
- `pnpm --dir e2e typecheck` — passed.
- `uv run mypy apps packages` — passed with existing pyproject unused-section note.
- `git diff --check` — passed.

### Completion Notes List

- Added token-gated frozen-account appeal lifecycle with 24h HMAC-tracked bearer tokens, safe risk summaries, audit events, and Story 1.7 merge proposal reuse.
- Updated frozen OTP/login failures to return RFC7807-compatible recovery metadata while preserving `detail: "account frozen"`.
- Added `/auth/frozen-appeal` three-step zh-CN page, login frozen CTA, sessionStorage-only tracking-token persistence, focused Vitest coverage, and route-mocked Chromium Playwright flow.
- Post-implementation code review fixed a JWT-gated frozen-account bypass regression and added coverage for protected routes after freeze.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/stories/1-12-j7-fraud-freeze-vertical-slice.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/auth-service/src/auth_service/config.py`
- `apps/auth-service/src/auth_service/frozen_appeals.py`
- `apps/auth-service/src/auth_service/main.py`
- `apps/auth-service/src/auth_service/models.py`
- `apps/auth-service/src/auth_service/routes.py`
- `apps/auth-service/src/auth_service/schemas.py`
- `apps/auth-service/src/auth_service/security.py`
- `apps/auth-service/tests/conftest.py`
- `apps/auth-service/tests/test_frozen_appeals.py`
- `apps/web/src/app/auth/frozen-appeal/page.test.tsx`
- `apps/web/src/app/auth/frozen-appeal/page.tsx`
- `apps/web/src/app/auth/login/page.test.tsx`
- `apps/web/src/app/auth/login/page.tsx`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/frozen-appeal.test.ts`
- `apps/web/tsconfig.json`
- `e2e/tests/j7-frozen-appeal.spec.ts`
- `infra/local-init/01-schema.sql`
- `infra/local-init/10-freeze-appeals.sql`

### Change Log

- 2026-05-24 — Created Story 1.12 draft with J7 frozen appeal scope, token-gated no-login recovery API, dedicated appeal page, and test plan.
- 2026-05-24 — Implemented Story 1.12 frozen appeal vertical slice across auth-service, web UI, tests, CI schema wiring, and route-mocked E2E.
- 2026-05-24 — Code review fixed protected-route freeze enforcement for existing JWTs and moved Story 1.12 to done.

## Story Review Log

### Round 1 — Product Scope / UX Acceptance Review

- [x] Added recovery behavior for users who lose the original tracking link: starting a new appeal links the latest non-terminal merge proposal when one exists.
- [x] Added duplicate-proposal guard so an appeal already linked to a proposal cannot submit another proposal.
- [x] Added a 3-step, about-1-minute self-service constraint and sessionStorage-only token persistence for the dedicated J7 page.

### Round 2 — Architecture / Security Contract Review

- [x] Required a dedicated freeze-appeal token HMAC pepper instead of reusing API-key or guardian-consent peppers.
- [x] Required token validation to recompute hash and use `secrets.compare_digest`, with no raw-token DB lookup or logging.
- [x] Scoped `10-freeze-appeals.sql` CI wiring to auth-service only; solver-orchestrator does not consume the appeal table.

### Round 3 — Implementation Readiness Review

- [x] Clarified that the Playwright check is Chromium-only and route-mocked, so it can run in the existing `@opticloud/e2e` package without seeded services.
- [x] Tightened the quality gate command list so the developer does not improvise a different Playwright invocation.
- [x] Clarified that browser page tests may mock API helpers directly, while the Playwright test validates the route-mocked browser flow.
