---
story_key: 1-9-under-14-block
epic_num: 1
story_num: 1.9
epic_name: Account & Identity
status: done
priority: 🟠 High (FR A10 hard-gate; PIPL + signup compliance block for minors)
sizing: M (~8-10 hours; age gate request contract + guardian confirmation flow + UI gating + tests)
type: implementation + ui + test
created_by: bmad-create-story
created_at: 2026-05-24
sources:
  - [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1331-1333]
  - [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1445]
  - [Source: D:/优化预测网站/_bmad-output/planning/prd.md:756]
  - [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1444-1445]
  - [Source: D:/优化预测网站/网站方案.md:806-809]
  - [Source: D:/优化预测网站/docs/legal-templates.md:51-55]
  - [Source: D:/优化预测网站/infra/local-init/01-schema.sql:9-20]
  - [Source: D:/优化预测网站/apps/auth-service/src/auth_service/models.py:39-47]
  - [Source: D:/优化预测网站/apps/auth-service/src/auth_service/routes.py:85-157]
  - [Source: D:/优化预测网站/apps/auth-service/src/auth_service/schemas.py:18-79]
  - [Source: D:/优化预测网站/apps/auth-service/src/auth_service/risk.py:1-130]
  - [Source: D:/优化预测网站/apps/web/src/app/auth/signup/page.tsx:1-227]
  - [Source: D:/优化预测网站/apps/web/src/app/auth/login/page.tsx:1-275]
  - [Source: D:/优化预测网站/apps/web/src/lib/api.ts:1-290]
  - [Source: D:/优化预测网站/apps/web/src/lib/onboarding.ts:1-195]
  - [Source: D:/优化预测网站/apps/auth-service/tests/test_risk_freeze.py:1-430]
  - [Source: D:/优化预测网站/apps/auth-service/tests/test_login_routes.py:1-230]
  - [Source: D:/优化预测网站/apps/auth-service/tests/test_edu_signup.py:1-160]
dependencies:
  upstream:
    - 0-6-auth-scaffold (done) — users / JWT / signup baseline already exists
    - 1-1a-j1-signup-api-key (done) — `/auth/signup` and welcome handoff already exist
    - 1-2-user-login (done) — OTP login path already exists for resumed access
    - 1-5-risk-control-freeze (done) — `users.is_frozen` / risk gating pattern already exists
    - 1-8-onboarding-wizard-5steps (done) — wizard shell must remain age-gate compatible
  downstream:
    - 1-10-language-switch-zh — signup/login/error copy must remain zh-CN first
    - 1-11-geo-anomaly-risk — auth gating should remain route-compatible
    - 1-12-j7-fraud-freeze-vertical-slice — age gate should not collide with freeze copy
---

# Story 1.9 — <14 岁拦截 + 14-18 监护人确认（FR A10）

## User Story

**As** a new user
**I want** signup to reject users under 14 and require guardian email confirmation for users aged 14-18
**so that** registration follows the A10 legal gate before the product issues JWT access.

## Why this story

FR A10 is already declared v1 mandatory in PRD, but the current signup path still assumes every request can become a live user immediately. That is not compliant.

This story closes the gap by adding an explicit age gate to signup, a guardian-confirmation flow for minors, and a login-time block while the account is still pending confirmation. It must also stay compatible with the 1.8 onboarding shell so minors do not flow into `/welcome` prematurely.

## Out of scope

- Real identity/KYC verification beyond age gate
- Proof-of-age document upload
- Payment/充值实名核验 for `>= ¥500`
- New billing, solver, or API-key behavior
- Rewriting the onboarding wizard flow labels
- Any broad profile management UI beyond the signup/login paths

## Acceptance Criteria

### AC1: Signup accepts an explicit age field

- `POST /v1/auth/signup` accepts an age field in the request body
- The field is validated as an integer in a sane range
- The existing email/phone validation stays intact
- The web signup form shows the age field clearly and keeps the layout dense

### AC2: Users under 14 are rejected immediately

- If age is `< 14`, signup fails before a live user is created
- No JWT pair is returned
- No onboarding progress is advanced
- The response is a structured 4xx error with a clear age-gate message
- The web form shows the reason inline and does not redirect

### AC3: Ages 14-18 enter a guardian-confirmation flow

- If age is `14-18` inclusive, signup creates a pending account state instead of a fully usable account
- A guardian email is required for this band
- The backend creates a durable pending-confirmation record
- The response is a pending status, not a JWT pair
- The signup page shows a non-blocking pending state and keeps the user on the auth surface

### AC4: Guardian confirmation activates the account

- A guardian confirmation link/token can be verified from the web
- On success, the pending record is closed and `users.age_verified` becomes `true`
- After confirmation, the user can log in through the existing OTP flow
- The confirmation flow must be idempotent and safe to retry

### AC5: Adults 19+ behave like the current signup fast path

- If age is `>= 19`, signup behaves like the current happy path
- `users.age_verified` is set for the created user
- JWT pair issuance and onboarding handoff continue as they do today

### AC6: Age gate blocks downstream auth surfaces until confirmed

- `login` refuses access for users whose age gate is still pending
- The error copy must be distinct from freeze/account-deletion copy
- API-key and other JWT-gated auth surfaces must not become usable before confirmation

### AC7: Web UX stays compatible with onboarding

- `/auth/signup` shows age-aware inputs and helper text
- `14-18` users see a guardian email field
- The pending state explains what happens next and offers a re-open path
- `/auth/login` tells a pending user to finish guardian confirmation first
- `/welcome` is only reached after the age gate clears

### AC8: Tests cover boundaries and closure

- `<14` is rejected
- `14` and `18` require guardian confirmation
- `19` signs up normally
- Pending users cannot log in
- Guardian confirmation flips `age_verified` and unblocks login
- Onboarding state does not advance early

### AC9: Scope guard

- No new billing or solver behavior is added
- No new KYC document workflow is added
- No user-facing route outside auth is required
- The implementation may add one small confirmation route/page if needed, but should not expand the auth surface beyond the age-gate flow

## Tasks / Subtasks

- [x] Task 1: Define the age-gate request/response contract and persistence model (AC: 1, 2, 3, 4, 5, 9)
  - [x] Add the age field and guardian-email validation to the signup schema
  - [x] Decide the pending-confirmation record shape and token lifecycle
  - [x] Keep `users.age_verified` as the runtime gate

- [x] Task 2: Implement the auth-service age-gate backend (AC: 2, 3, 4, 5, 6)
  - [x] Branch signup by age band
  - [x] Reject `<14` before user creation
  - [x] Create pending guardian confirmation for `14-18`
  - [x] Mark adults `>=19` as verified immediately
  - [x] Block login while `age_verified=false`

- [x] Task 3: Wire the web auth surfaces (AC: 1, 3, 4, 6, 7)
  - [x] Update `/auth/signup` with the age field and conditional guardian email field
  - [x] Add pending-state copy and confirmation actions
  - [x] Update `/auth/login` to explain the guardian-confirmation block
  - [x] Add a minimal guardian-confirmation route/page if the token flow needs one

- [x] Task 4: Add tests for boundaries and pending-state closure (AC: 2, 3, 4, 5, 6, 8)
  - [x] Backend tests for 13 / 14 / 18 / 19 boundaries
  - [x] Backend tests for confirmation token success and idempotency
  - [x] Backend tests for login rejection before confirmation
  - [x] Web tests for conditional fields and pending-state messaging

- [x] Task 5: Update docs and sprint tracking (AC: 7, 8, 9)
  - [x] Update auth README or flow notes if needed
  - [x] Update sprint status to `ready-for-dev` now and `done` after implementation review passes

## Dev Notes

- Follow the existing auth-service patterns in `routes.py`, `schemas.py`, `models.py`, `risk.py`, and `security.py`
- Reuse `users.age_verified` as the actual access gate instead of inventing a second long-lived status flag
- Keep PII minimal; prefer a pending-confirmation record over storing extra user profile data on `users`
- The signup flow should not redirect to `/welcome` until the age gate clears
- Use the existing RFC 7807 / `StatusCard` / `RFC7807Panel` patterns for blocked states
- Keep the guardian-confirmation copy distinct from `is_frozen` copy so the user does not get a misleading security message
- The web signup form should remain route-compatible with Story 1.8 onboarding shell behavior
- The confirmation flow should be deterministic in tests; avoid real-time waits

### Project Structure Notes

- Backend request/response logic: `apps/auth-service/src/auth_service/{routes.py,schemas.py,models.py}`
- Age-gate gatekeeping: `apps/auth-service/src/auth_service/routes.py` and `apps/auth-service/src/auth_service/risk.py` if you reuse a shared guard
- Web signup/login UX: `apps/web/src/app/auth/signup/page.tsx`, `apps/web/src/app/auth/login/page.tsx`
- Shared client contract: `apps/web/src/lib/api.ts`
- Onboarding compatibility: `apps/web/src/lib/onboarding.ts`

### References

- [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1331-1333]
- [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1445]
- [Source: D:/优化预测网站/_bmad-output/planning/prd.md:756]
- [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1444-1445]
- [Source: D:/优化预测网站/网站方案.md:806-809]
- [Source: D:/优化预测网站/docs/legal-templates.md:51-55]
- [Source: D:/优化预测网站/infra/local-init/01-schema.sql:9-20]
- [Source: D:/优化预测网站/apps/auth-service/src/auth_service/models.py:39-47]
- [Source: D:/优化预测网站/apps/auth-service/src/auth_service/routes.py:85-157]
- [Source: D:/优化预测网站/apps/auth-service/src/auth_service/routes.py:164-351]
- [Source: D:/优化预测网站/apps/auth-service/src/auth_service/schemas.py:18-79]
- [Source: D:/优化预测网站/apps/auth-service/src/auth_service/risk.py:1-130]
- [Source: D:/优化预测网站/apps/web/src/app/auth/signup/page.tsx:1-227]
- [Source: D:/优化预测网站/apps/web/src/app/auth/login/page.tsx:1-275]
- [Source: D:/优化预测网站/apps/web/src/lib/api.ts:1-290]
- [Source: D:/优化预测网站/apps/web/src/lib/onboarding.ts:1-195]
- [Source: D:/优化预测网站/apps/auth-service/tests/test_risk_freeze.py:1-430]
- [Source: D:/优化预测网站/apps/auth-service/tests/test_login_routes.py:1-230]
- [Source: D:/优化预测网站/apps/auth-service/tests/test_edu_signup.py:1-160]

## Three-Round Story Review

### Round 1: Data Consistency Review

Scope: age field naming, `users.age_verified`, pending confirmation record, and boundary handling for `13 / 14 / 18 / 19`.

Findings and fixes:

- [x] Boundary ambiguity: the story initially implied a vague "age gate" without explicit inclusive bounds. Fixed by making the bands explicit: `<14` reject, `14-18` pending guardian confirmation, `>=19` normal signup.
- [x] Persistence drift: the story could have suggested storing raw age on `users`, which is unnecessary and expands PII. Fixed by keeping `users.age_verified` as the runtime gate and using a small pending-confirmation record for the temporary state.
- [x] Onboarding drift: the story now states that `/welcome` is unreachable until the gate clears, preventing accidental advancement of Story 1.8 state.

Round 1 result: PASS after patch.

### Round 2: Function Consistency / Drift Review

Scope: signup/login route behavior, web API contract, guardian confirmation flow, and reuse of existing auth helpers.

Findings and fixes:

- [x] Signup needed a real branch by age band. Fixed by specifying explicit adult, minor-pending, and under-14 behaviors in AC2-AC5.
- [x] Login needed a distinct age-gate block, not a freeze message. Fixed by requiring a separate login error copy for `age_verified=false`.
- [x] The web flow needed a place for guardian confirmation to land. Fixed by allowing a minimal confirmation route/page only if needed, instead of forcing a broad auth redesign.
- [x] The shared client contract needs a pending response shape. Fixed by writing the story around a pending status instead of pretending every signup returns the same JWT pair.

Round 2 result: PASS after patch.

### Round 3: Boundary / Closure Review

Scope: legal closure, route closure, retry behavior, and no-scope creep into billing/KYC.

Findings and fixes:

- [x] Under-14 rejection is now explicit and closed before user creation.
- [x] Guardian confirmation is idempotent and retry-safe.
- [x] The story no longer leaks into billing, solver, or broad KYC work.
- [x] The acceptance criteria now require tests for all boundary ages and for the login-block closure path.

Round 3 result: PASS after patch; story is ready for dev implementation.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- Story authoring and source inspection completed on 2026-05-24
- Implementation completed on 2026-05-24.
- Validation: `uv run pytest apps/auth-service/tests -q` → 51 passed.
- Validation: `uv run ruff check apps/auth-service/src/auth_service apps/auth-service/tests` → passed.
- Validation: `pnpm --dir apps/web typecheck` → passed.
- Validation: `pnpm --dir apps/web test` → 56 passed.

### Completion Notes List

- Added a dedicated age-gate story for FR A10.
- Aligned the story to the existing `users.age_verified` field and the current signup/login/web onboarding flow.
- Kept the scope narrow enough for a single implementation pass while still closing the legal and UX gap.
- Implemented signup age bands: `<14` structured 403, `14-18` pending guardian confirmation without JWT, `>=19` verified token response.
- Added durable `guardian_confirmations` persistence with token hash, expiry, confirmed timestamp, and idempotent confirmation.
- Blocked OTP request, login, and JWT-protected API-key routes while `age_verified=false`.
- Updated web signup/login/confirmation/welcome surfaces so pending users stay on auth surfaces and empty JWTs cannot reach `/welcome`.
- Added backend and web tests for age boundaries, pending closure, idempotent confirmation, login/OTP blocking, risk-evaluation continuity, and onboarding non-advancement.

### File List

- `_bmad-output/stories/1-9-under-14-block.md`
- `_bmad-output/stories/sprint-status.yaml`
- `infra/local-init/01-schema.sql`
- `apps/auth-service/src/auth_service/models.py`
- `apps/auth-service/src/auth_service/routes.py`
- `apps/auth-service/src/auth_service/schemas.py`
- `apps/auth-service/tests/conftest.py`
- `apps/auth-service/tests/test_account_deletion.py`
- `apps/auth-service/tests/test_age_gate.py`
- `apps/auth-service/tests/test_api_keys_routes.py`
- `apps/auth-service/tests/test_edu_signup.py`
- `apps/auth-service/tests/test_login_routes.py`
- `apps/auth-service/tests/test_risk_freeze.py`
- `apps/web/src/lib/api.ts`
- `apps/web/src/app/auth/signup/page.tsx`
- `apps/web/src/app/auth/signup/page.test.tsx`
- `apps/web/src/app/auth/login/page.tsx`
- `apps/web/src/app/auth/login/page.test.tsx`
- `apps/web/src/app/auth/guardian-confirmation/page.tsx`
- `apps/web/src/app/welcome/page.tsx`

### Implementation Plan

- Use `users.age_verified` as the single runtime gate and add only a temporary guardian-confirmation table for minor pending state.
- Keep under-14 rejection before user creation, preserve existing adult signup/JWT behavior, and reuse existing OTP/login/API-key guards.
- Add a minimal confirmation page rather than expanding the auth surface.

### Senior Developer Review (AI)

Outcome: Approve after fixes

Review date: 2026-05-24

Findings and fixes:

- [x] Medium: Pending `14-18` signup initially bypassed existing signup risk evaluation. Fixed by extracting `_apply_signup_risk` and calling it for both pending minors and verified adults after the signup audit row is flushed.
- [x] Medium: Pending signup initially advanced onboarding/session state too early. Fixed by keeping pending users on the auth surface without storing JWT/user onboarding completion; web test now asserts no onboarding step is completed.
- [x] Low: New confirmation page used `useSearchParams` without a `Suspense` boundary. Fixed by wrapping the page content in `Suspense`, matching the existing Next.js 15 pattern.
- [x] Low: Formatting and line-ending churn caused `git diff --check` noise. Fixed by formatting touched Python/TS files and normalizing line endings; `git diff --check` passes.

Residual risk:

- Guardian email delivery is intentionally out of scope for this story; local/dev flow returns a confirmation URL for deterministic testing.

### Change Log

- 2026-05-24: Created and three-round reviewed Story 1.9.
- 2026-05-24: Implemented age gate, guardian confirmation, auth-surface blocking, web UX, and regression tests.
- 2026-05-24: Completed implementation code review and fixed risk/onboarding/Suspense/format findings.
