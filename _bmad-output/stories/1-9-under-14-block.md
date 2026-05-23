---
story_key: 1-9-under-14-block
epic_num: 1
story_num: 1.9
epic_name: Account & Identity
status: done
priority: 🔴 Critical (FR A10 v1 必上；注册入口合规硬门)
sizing: L (~1 day; auth API contract + consent persistence + signup UI + regression updates)
type: implementation + compliance + ui + test
created_by: bmad-create-story
created_at: 2026-05-23
sources:
  - [Source: D:/优化预测网站-1-9-under-14-block/_bmad-output/planning/epics.md:51]
  - [Source: D:/优化预测网站-1-9-under-14-block/_bmad-output/planning/epics.md:1268]
  - [Source: D:/优化预测网站-1-9-under-14-block/_bmad-output/planning/epics.md:1331]
  - [Source: D:/优化预测网站-1-9-under-14-block/_bmad-output/planning/prd.md:1445]
  - [Source: D:/优化预测网站-1-9-under-14-block/_bmad-output/planning/architecture.md:1323]
  - [Source: D:/优化预测网站-1-9-under-14-block/_bmad-output/planning/architecture.md:1736]
  - [Source: D:/优化预测网站-1-9-under-14-block/_bmad-output/planning/architecture.md:3282]
  - [Source: D:/优化预测网站-1-9-under-14-block/_bmad-output/planning/ux-design-specification.md:303]
  - [Source: D:/优化预测网站-1-9-under-14-block/_bmad-output/planning/ux-design-specification.md:1681]
  - [External: 中国政府网《儿童个人信息网络保护规定》, https://www.gov.cn/zhengce/2019-10/08/content_5728947.htm]
  - [External: 中国人大网《中华人民共和国个人信息保护法》, https://www.npc.gov.cn/npc/c2/c30834/202108/t20210820_313088.html]
dependencies:
  upstream:
    - 1-1a-j1-signup-api-key (done) — signup endpoint and welcome handoff exist
    - 1-2-user-login (done) — auth schema / JWT patterns exist
    - 1-4-edu-tier-email-whitelist (done) — signup already contains conditional side effects and audit metadata
    - 1-5-risk-control-freeze (done) — signup already writes risk/audit metadata
    - 1-8-onboarding-wizard-5steps (done) — `/auth/signup` is now wired into SignupWizard
  downstream:
    - 1-10-language-switch-zh — age-gate copy must stay zh-CN baseline and easy to localize later
    - 1-11-geo-anomaly-risk — signup audit metadata should remain compatible with risk signals
    - 1-12-j7-fraud-freeze-vertical-slice — rejected / pending auth paths should not look like fraud freezes
---

# Story 1.9 — <14 岁拦截 + 14-18 监护人确认（FR A10）

## User Story

**As** the OptiCloud compliance owner,
**I want** signup to collect an age declaration, reject users under 14, and require guardian email confirmation for users aged 14-17,
**so that** the account system satisfies FR A10 before issuing JWTs, API keys, or onboarding progress.

## Why this story

FR A10 is a v1 must-have for the registration boundary. The current signup path accepts only `phone` and `email`, creates a user immediately, issues JWTs, and starts onboarding. The `users.age_verified` column already exists, but it is never set by signup and there is no guardian-consent state.

This story turns age verification into a server-side gate. UI fields are required for usability, but the backend remains authoritative:

- `<14`: reject before creating a `users` row.
- `14-17`: create a short-lived guardian-consent request; do not create a user or issue JWTs until the guardian confirmation token is supplied.
- `>=18`: create the user normally and set `age_verified=true`.

Use minimum necessary data. Do not collect date of birth, ID number, school, parent name, or document images in this story.

## Out of Scope

- Real SMS/email provider integration; local/dev may return a dev confirmation token like OTP dev mode.
- KYC, national identity verification, ID card OCR, or proof upload.
- Legal-document rewriting beyond existing privacy/TOS links.
- Post-signup parental dashboard or account delegation.
- Blocking existing adult signup behind an asynchronous email flow.
- Changing login, API-key creation, billing, solver, or onboarding steps beyond handling the signup result.

## Acceptance Criteria

### AC1: Signup request includes an age declaration

- `POST /v1/auth/signup` requires `age_years` as an integer age declaration.
- Valid range is `0..120`; invalid values return validation error and create no user.
- The request uses age in years, not date of birth, to minimize PII.
- Existing adult callers/tests must be updated to send `age_years: 18` or higher.

### AC2: Users under 14 are blocked server-side

- If `age_years < 14`, signup returns a policy rejection (`403` preferred; `422` acceptable only if it preserves field-level detail).
- No `users`, `api_keys`, `credit_transactions`, `guardian_consent_requests`, or JWTs are created.
- The response detail is user-safe and does not invite repeated probing.
- The rejection path may write an audit event with no `user_id`, but must not persist raw phone/email for a blocked child.

### AC3: Ages 14-17 require guardian email confirmation before account creation

- If `14 <= age_years < 18` and no valid guardian confirmation token is supplied, signup returns `202 Accepted` with a pending guardian-consent response.
- The route contract explicitly models both completed and pending outcomes: `SignupResponse` for `201 Created`, `GuardianConsentPendingResponse` for `202 Accepted`. Do not leave OpenAPI claiming only `SignupResponse`.
- The pending response includes `status="guardian_consent_required"`, a request id, expiry seconds, and the guardian email destination.
- Local/dev mode may include `dev_guardian_consent_token`; production must be able to hide it via config.
- No `users` row, JWT, edu credit seed, risk flag, or onboarding completion is created while guardian consent is pending.
- Guardian email is required for this age band and must be a valid email address.
- Repeating the same pending minor signup may replace the previous unconfirmed token or return the still-valid request, but there must be only one active unconfirmed request per normalized `(phone, email, guardian_email)` tuple.

### AC4: Guardian confirmation completes signup exactly once

- Supplying a valid unexpired guardian confirmation token with the same phone/email/age/guardian email completes signup and returns the normal `SignupResponse`.
- The resulting user has `age_verified=true`.
- The guardian consent request records `confirmed_at` and the created `user_id`.
- Token replay, expired token, mismatched request id/email/phone/age/guardian email, or already-consumed token returns `403` or `409` and creates no extra user.
- Token material is never stored in plaintext; persist only an HMAC hash using server-side config, not a bare SHA digest.

### AC5: Adult signup remains the current happy path

- If `age_years >= 18`, signup creates the user immediately, returns `201`, sets `age_verified=true`, and preserves existing behavior:
  - `.edu` / `.ac.cn` auto-detect still sets `edu_tier=true`.
  - edu signup still seeds the `edu` credit bucket.
  - audit log `auth.signup` still records existing metadata.
  - risk evaluation still runs after the user and audit log exist.
  - onboarding still redirects to `/welcome`.

### AC6: Signup audit metadata is sufficient but privacy-preserving

- `auth.signup` audit metadata includes `age_band` (`adult` or `minor_14_17`), `age_verified=true`, and guardian consent request id for minors.
- Under-14 rejection audit, if implemented, stores only an age band/reason and not raw child contact data.
- Do not store guardian full email in `audit_logs.metadata`; use request id and optional email domain if needed.

### AC7: Web signup UI handles all age-gate states

- `/auth/signup` adds an age field with numeric input constraints and clear zh-CN copy.
- Guardian email input appears only when entered age is 14-17.
- Under-14 attempts show a non-blocking `StatusCard` / `RFC7807Panel` style error and do not advance onboarding.
- Pending guardian consent shows a clear waiting state; in dev mode the token can be entered to complete signup.
- Adult signup and confirmed-minor signup store JWT/session state and continue the existing Story 1.8 onboarding handoff.

### AC8: API client and smoke path are updated

- `apps/web/src/lib/api.ts` types model the adult `SignupResponse` and pending guardian-consent response without dropping RFC 7807 errors.
- J1 happy-path E2E fills `age_years >= 18` and still reaches `/welcome`.
- Existing signup helper tests in auth-service are updated to include adult age so unrelated stories do not fail.
- Known backend test helpers/call sites to migrate include `test_login_routes.py`, `test_api_keys_routes.py`, `test_account_deletion.py`, `test_account_merge.py`, `test_edu_signup.py`, and the direct signup path in `test_risk_freeze.py`.
- Known non-backend callers to migrate include `apps/web/src/app/auth/signup/page.tsx`, `e2e/fixtures/api.ts`, `e2e/tests/j1-happy-path.spec.ts`, and documentation snippets that POST to `/v1/auth/signup`.

### AC9: Tests cover the compliance boundary

- Auth-service tests cover:
  - adult signup succeeds and sets `age_verified=true`;
  - `<14` rejected with no user row;
  - `14-17` without guardian email/token returns pending/no user;
  - valid guardian token completes signup and marks request consumed;
  - token replay/mismatch/expiry fails with no duplicate user;
  - edu-tier adult behavior still seeds credits.
- Web tests cover API-client request/response typing for age-gated signup and pending response.
- E2E happy path remains green for adult signup.

### AC10: Quality gates

- `uv run pytest apps/auth-service/tests -q` passes, or any pre-existing unrelated blocker is recorded.
- `uv run mypy apps packages` passes, or focused auth-service mypy blocker is recorded.
- `pnpm --filter @opticloud/web test` passes.
- `pnpm --filter @opticloud/web typecheck` passes.
- Relevant Playwright J1 smoke passes after adding the age field.

## Tasks / Subtasks

- [x] Task 1: Define backend age-gate schemas and validation (AC: 1, 2, 3, 4, 5)
  - [x] Add `age_years`, `guardian_email`, and `guardian_consent_token` to `SignupRequest`.
  - [x] Add a pending guardian-consent response schema for `202 Accepted`.
  - [x] Update FastAPI route metadata so OpenAPI documents both `201` completed signup and `202` pending consent responses.
  - [x] Keep phone/email validators and existing `SignupResponse` compatibility for completed signups.

- [x] Task 2: Add guardian consent persistence and token utilities (AC: 3, 4, 6)
  - [x] Add `guardian_consent_requests` model and `infra/local-init` SQL.
  - [x] Persist at least: `id`, `phone`, `email`, `age_years`, `guardian_email`, `token_hash`, `expires_at`, `confirmed_at`, `user_id`, `created_at`, `updated_at`.
  - [x] Add indexes for token lookup and stale pending lookup; do not add uniqueness that prevents a user from requesting a replacement token after expiry.
  - [x] Normalize email and guardian email with the same canonical lower-case value before storing and before matching token confirmation.
  - [x] Ensure one active unconfirmed request per normalized `(phone, email, guardian_email)` by expiring/replacing old pending rows or reusing the current still-valid row.
  - [x] Add test bootstrap DDL in auth-service `conftest.py` for local DBs that predate the migration.
  - [x] Update CI schema application for auth-service and any E2E job that applies auth schema so fresh CI databases include `guardian_consent_requests`.
  - [x] Generate URL-safe tokens, persist only an HMAC hash with a server-side pepper, enforce expiry and one-time consumption.
  - [x] Add config for consent TTL and dev token exposure.

- [x] Task 3: Wire age-gate behavior into `POST /v1/auth/signup` (AC: 2, 3, 4, 5, 6)
  - [x] Reject `<14` before creating user-side effects.
  - [x] Return pending consent for `14-17` without a valid token.
  - [x] Complete signup only after valid guardian token.
  - [x] Preserve edu-tier seed, audit log, risk evaluation, and JWT issuance for adult/confirmed signups.

- [x] Task 4: Update web signup flow and API client (AC: 7, 8)
  - [x] Update `SignupRequest` / response union in `apps/web/src/lib/api.ts`.
  - [x] Add age and conditional guardian email/token controls to `/auth/signup`.
  - [x] Ensure pending and rejected states do not mark onboarding steps complete.
  - [x] Ensure completed adult/confirmed-minor signup still redirects to `/welcome`.

- [x] Task 5: Add and update tests (AC: 8, 9, 10)
  - [x] Add auth-service age-gate tests.
  - [x] Update existing auth-service signup calls to include adult age.
  - [x] Add/update web API-client tests for age-gated signup.
  - [x] Update E2E API fixture and J1 Playwright signup flow to send/fill adult age.
  - [x] Update README/Landing cURL snippets that show signup JSON so docs do not teach a now-invalid request.
  - [x] Run quality gates and record commands in Dev Agent Record.

- [x] Task 6: Update story and sprint tracking (AC: 10)
  - [x] Keep File List current.
  - [x] Move story to code-review only after all ACs and tests are satisfied.
  - [x] Move sprint status to done only after implementation code review passes.

## Dev Notes

- Backend is authoritative. Client-side form validation is only usability; never rely on it for age enforcement.
- Use `age_years`, not DOB. This avoids introducing a new sensitive long-term identifier.
- Existing `users.age_verified` is the right completion marker. Set it `true` for adult and guardian-confirmed minor signups. Do not create a user for pending guardian consent.
- Keep under-14 paths free of child PII persistence. If an audit event is required, store `actor="system"`, action such as `auth.signup.age_gate_rejected`, and metadata like `{ "age_band": "under_14", "reason": "policy" }` only.
- Guardian consent token should mirror OTP dev-mode ergonomics: production can send/hide it later; local tests can receive it deterministically from the response when config allows.
- Add separate config values such as `guardian_consent_ttl_seconds`, `guardian_consent_dev_mode_return`, and `guardian_consent_token_pepper_dev`; do not reuse the API key pepper unless intentionally documented.
- Reuse constant-time comparison (`secrets.compare_digest`) when checking token hashes.
- FastAPI implementation will likely need either a union response model or an explicit `JSONResponse`/`Response.status_code` branch for `202`. The completed branch must continue returning `201`.
- Do not create a separate guardian account, parental dashboard, or admin review queue in this story.
- Do not reuse OTP rows for guardian consent. OTP verifies login factors for an existing user; guardian consent precedes user creation and needs separate one-time consumption.
- Keep edu-credit seeding after the final user create only. A pending minor must not receive credits.
- Keep risk evaluation after the `auth.signup` audit log flush, matching Story 1.5's dependency on signup audit metadata.
- Existing `/auth/signup` uses Story 1.8 onboarding helpers. Pending/rejected age-gate states must not call `markOnboardingStep(..., "signup", "complete")`.
- Web `signup()` should return a discriminated union. UI code must check `status === "guardian_consent_required"` before reading JWT fields; do not use optional JWT fields on a single loose type.
- Current web Vitest config excludes `src/app/**/page.tsx`; route behavior is covered mainly by API-client unit tests and Playwright smoke unless the config is intentionally changed.
- Existing `request<T>()` treats all 2xx responses as success, so `202` pending responses will flow through normally; the caller must branch on the returned shape.

### Project Structure Notes

- Backend schemas: `apps/auth-service/src/auth_service/schemas.py`
- Backend route: `apps/auth-service/src/auth_service/routes.py`
- Backend models: `apps/auth-service/src/auth_service/models.py`
- Backend config: `apps/auth-service/src/auth_service/config.py`
- Local schema: `infra/local-init/01-schema.sql`; add a numbered incremental SQL file and wire it into `.github/workflows/ci.yml` wherever auth-service schema is applied.
- Auth tests: `apps/auth-service/tests/test_age_gate_signup.py` plus existing signup tests/helpers.
- Web API client: `apps/web/src/lib/api.ts`
- Web signup page: `apps/web/src/app/auth/signup/page.tsx`
- Web tests: `apps/web/src/lib/*test.ts`
- E2E: `e2e/tests/j1-happy-path.spec.ts`
- E2E API helper: `e2e/fixtures/api.ts`
- Signup snippets: `apps/auth-service/README.md`, `apps/web/src/app/page.tsx`

### Risks & Mitigations

| Risk | Mitigation |
|---|---|
| UI-only age gate can be bypassed | Enforce all age bands in `auth-service` before side effects |
| Pending minor accidentally gets a user/JWT/credits | Return `202` before user creation; test DB row absence |
| Token replay creates duplicate users | Store one-time hash with `confirmed_at` and matching contact fields |
| Multiple pending rows create ambiguous confirmation | Keep one active pending request per normalized contact tuple |
| Bare token hash is brute-forceable if DB leaks | HMAC token hashes with a server-side pepper and constant-time compare |
| Under-14 PII is persisted | Reject before user/consent rows; audit only age band/reason |
| Existing tests break silently | Update every signup helper/call to send `age_years` explicitly |
| Story 1.8 onboarding advances on pending consent | Keep onboarding step completion only after normal `SignupResponse` |
| Pending response is mistaken for success in web code | Use a discriminated union and branch before reading JWT fields |
| Email provider absence blocks implementation | Use dev-mode token response and config; leave real provider integration out of scope |

### References

- FR A10 summary: `_bmad-output/planning/epics.md:51`
- Epic 1 story list and Story 1.9 AC: `_bmad-output/planning/epics.md:1268-1333`
- PRD FR table A10: `_bmad-output/planning/prd.md:1430-1445`
- Auth-service owns A1-A10: `_bmad-output/planning/architecture.md:1323`
- Boundary rules: `_bmad-output/planning/architecture.md:1736-1755`
- J1 persona surface uses SignupWizard/Auth pages: `_bmad-output/planning/architecture.md:3282`
- UX registration path and onboarding expectations: `_bmad-output/planning/ux-design-specification.md:303`
- UX error/recovery patterns: `_bmad-output/planning/ux-design-specification.md:1681`
- Current signup route: `apps/auth-service/src/auth_service/routes.py`
- Current signup schema: `apps/auth-service/src/auth_service/schemas.py`
- Existing `users.age_verified`: `apps/auth-service/src/auth_service/models.py`
- Current web signup page: `apps/web/src/app/auth/signup/page.tsx`

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- `uv run python -m py_compile apps/auth-service/src/auth_service/config.py apps/auth-service/src/auth_service/models.py apps/auth-service/src/auth_service/routes.py apps/auth-service/src/auth_service/schemas.py apps/auth-service/src/auth_service/security.py` — passed.
- `uv run pytest apps/auth-service/tests/test_age_gate_signup.py -q` — 6 passed.
- `uv run pytest apps/auth-service/tests/test_age_gate_signup.py apps/auth-service/tests/test_login_routes.py apps/auth-service/tests/test_edu_signup.py -q` — 20 passed.
- `uv run pytest apps/auth-service/tests -q` — 59 passed.
- `pnpm --filter @opticloud/web test -- signup` — 2 passed.
- `pnpm --filter @opticloud/web test` — 56 passed.
- `pnpm --filter @opticloud/web typecheck` — passed.
- `pnpm --filter @opticloud/ui test` — 49 passed.
- `pnpm --filter @opticloud/ui typecheck` — passed.
- `uv run mypy apps packages` — passed, 70 source files checked.
- `git diff --check` — passed.
- `pnpm --dir e2e exec playwright test tests/j1-happy-path.spec.ts --project=chromium` — 1 passed.
- `uv run pytest apps/auth-service/tests/test_age_gate_signup.py -q` — failed before explicit `PYTHONPATH`; local shell did not include `auth_service`.
- `$env:PYTHONPATH='<repo>/apps/auth-service/src;<repo>/packages/shared-py'; uv run pytest apps/auth-service/tests/test_age_gate_signup.py -q` — 7 passed.
- `uv run ruff check apps/auth-service/src/auth_service/config.py apps/auth-service/src/auth_service/routes.py apps/auth-service/tests/test_age_gate_signup.py` — passed.
- `$env:PYTHONPATH='<repo>/apps/auth-service/src;<repo>/packages/shared-py'; uv run pytest apps/auth-service/tests -q` — failed due missing `solver_orchestrator` on local `PYTHONPATH`; 58 passed, 2 import errors.
- `$env:PYTHONPATH='<repo>/apps/auth-service/src;<repo>/apps/solver-orchestrator/src;<repo>/packages/shared-py'; uv run pytest apps/auth-service/tests -q` — 60 passed.
- `uv run mypy apps packages` — passed, 70 source files checked.
- `pnpm --filter @opticloud/web test` — 56 passed.
- `pnpm --filter @opticloud/web typecheck` — passed.
- `pnpm --filter @opticloud/ui test` — 49 passed.
- `pnpm --filter @opticloud/ui typecheck` — passed.
- `pnpm --dir e2e exec playwright test tests/j1-happy-path.spec.ts --project=chromium` — 1 passed.

### Completion Notes List

- Added server-side age declaration gate to signup: `<14` is rejected before user-side effects, `14-17` creates pending guardian consent only, and adult / confirmed minor signup returns the existing completed signup response.
- Added guardian consent persistence with HMAC token hashing, expiry, one-time consumption, and one active pending request per normalized contact tuple.
- Code review fixed pending-consent duplicate active request risk by adding a transaction-scoped advisory lock per normalized contact tuple and a regression test for repeated pending signup reuse.
- Preserved existing adult signup side effects including edu-tier credit seeding, audit metadata, risk evaluation, JWT issuance, and onboarding handoff.
- Updated web signup UI and API types to handle adult success, pending guardian consent, dev token confirmation, and under-14 policy errors.
- Migrated backend tests, web tests, E2E fixtures, J1 smoke, and signup documentation snippets to include `age_years`.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/stories/1-9-under-14-block.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/auth-service/README.md`
- `apps/auth-service/src/auth_service/config.py`
- `apps/auth-service/src/auth_service/models.py`
- `apps/auth-service/src/auth_service/routes.py`
- `apps/auth-service/src/auth_service/schemas.py`
- `apps/auth-service/src/auth_service/security.py`
- `apps/auth-service/tests/conftest.py`
- `apps/auth-service/tests/test_account_deletion.py`
- `apps/auth-service/tests/test_account_merge.py`
- `apps/auth-service/tests/test_age_gate_signup.py`
- `apps/auth-service/tests/test_api_keys_routes.py`
- `apps/auth-service/tests/test_edu_signup.py`
- `apps/auth-service/tests/test_login_routes.py`
- `apps/auth-service/tests/test_risk_freeze.py`
- `apps/web/src/app/auth/signup/page.tsx`
- `apps/web/src/app/page.tsx`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/signup.test.ts`
- `e2e/fixtures/api.ts`
- `e2e/tests/j1-happy-path.spec.ts`
- `infra/local-init/01-schema.sql`
- `infra/local-init/08-guardian-consent.sql`

### Change Log

- 2026-05-23 — Created story context for FR A10 age gate and guardian confirmation flow.
- 2026-05-23 — Implemented backend signup age gate, guardian consent table/token flow, web signup handling, tests, docs, and E2E adult signup update.
- 2026-05-23 — Code review completed: fixed 1 patch finding, added repeated pending consent regression coverage, reran final quality gates, and moved story to done.

## Senior Developer Review (AI)

### Review Date

2026-05-23

### Review Result

Approved after fixes. No unresolved decision-needed, patch, or deferred findings remain.

### Review Findings

- [x] [Review][Patch] Repeated/concurrent minor signup could create more than one active pending guardian consent request for the same normalized contact tuple — fixed by taking a transaction-scoped PostgreSQL advisory lock before lookup/create/refresh and adding regression coverage that repeated pending signup reuses the same request id.

### Verification

- `$env:PYTHONPATH='<repo>/apps/auth-service/src;<repo>/packages/shared-py'; uv run pytest apps/auth-service/tests/test_age_gate_signup.py -q` — pass, 7 tests.
- `uv run ruff check apps/auth-service/src/auth_service/config.py apps/auth-service/src/auth_service/routes.py apps/auth-service/tests/test_age_gate_signup.py` — pass.
- `pnpm --filter @opticloud/web test -- signup` — pass, 2 tests.
- `git diff --check` — pass.
- `$env:PYTHONPATH='<repo>/apps/auth-service/src;<repo>/apps/solver-orchestrator/src;<repo>/packages/shared-py'; uv run pytest apps/auth-service/tests -q` — pass, 60 tests.
- `uv run mypy apps packages` — pass, 70 source files.
- `pnpm --filter @opticloud/web test` — pass, 56 tests.
- `pnpm --filter @opticloud/web typecheck` — pass.
- `pnpm --filter @opticloud/ui test` — pass, 49 tests.
- `pnpm --filter @opticloud/ui typecheck` — pass.
- `pnpm --dir e2e exec playwright test tests/j1-happy-path.spec.ts --project=chromium` — pass, 1 test.

## Story Review Log

### Round 1 — API/Architecture Contract Review

- [x] Clarified `/v1/auth/signup` must document both `201 SignupResponse` and `202 GuardianConsentPendingResponse` instead of silently returning a second shape.
- [x] Specified minimum `guardian_consent_requests` columns and indexing expectations so implementation does not invent an incompatible table.
- [x] Added CI schema wiring requirement so fresh CI databases include the new consent table.

### Round 2 — Security/Privacy Review

- [x] Required one active pending guardian request per normalized contact tuple to avoid ambiguous confirmation state.
- [x] Required guardian token hashes to use HMAC with server-side pepper and constant-time comparison.
- [x] Added email canonicalization guidance so guardian confirmation does not fail on case-only differences.

### Round 3 — Implementation Readiness Review

- [x] Listed known signup call sites that must be migrated to include `age_years`.
- [x] Required the web API client to expose a discriminated union so pending consent cannot be treated as a successful JWT-bearing signup.
- [x] Added E2E fixture and docs snippet updates to prevent CI and docs drift.
