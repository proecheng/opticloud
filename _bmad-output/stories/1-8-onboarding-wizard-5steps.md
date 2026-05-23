---
story_key: 1-8-onboarding-wizard-5steps
epic_num: 1
story_num: 1.8
epic_name: Account & Identity
status: done
priority: 🟠 High (FR A9 complete; closes the onboarding gap for J1 and reduces drop-off after signup)
sizing: M-L (~6 hours; shared SignupWizard component + route wiring + support timer + tests)
type: implementation + ui + test
created_by: bmad-create-story
created_at: 2026-05-23
sources:
  - [Source: D:/优化预测网站/_bmad-output/planning/epics.md:351]
  - [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1268]
  - [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1325]
  - [Source: D:/优化预测网站/_bmad-output/planning/prd.md:469]
  - [Source: D:/优化预测网站/_bmad-output/planning/prd.md:476]
  - [Source: D:/优化预测网站/_bmad-output/planning/prd.md:588]
  - [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1231]
  - [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1389]
  - [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1444]
  - [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:1251]
  - [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:3108]
  - [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:3155]
  - [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:3282]
  - [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:158]
  - [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:303]
  - [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:425]
  - [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:562]
  - [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:1681]
  - [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:3004]
  - [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:3107]
dependencies:
  upstream:
    - 0-9-ui-tier1-stubs (done) — Tier 1 patterns already exist for modal, status, empty state, and loading
    - 0-10-tailwind-brand-tokens (done) — visual tokens already exist
    - 0-13-playwright-e2e (done) — browser smoke harness already exists
    - 1-1a-j1-signup-api-key (done) — signup entry and welcome handoff already exist
    - 1-1b-j1-confirmation-modal-postman (done) — Postman import / API key reveal patterns already exist
    - 1-2-user-login (done) — OTP login flow exists for verification/resume
    - 1-3-api-keys-crud-complete (done) — key management UI and API helpers already exist
    - 3-1-j1-lp-solve (done) — Hello World solve path already exists
  downstream:
    - 1-9-under-14-block — onboarding shell should remain compatible with age-gate handling
    - 1-10-language-switch-zh — wizard copy and progress rail should support zh-only baseline
    - 1-11-geo-anomaly-risk — onboarding shell should not hard-code a route structure that blocks future risk prompts
---

# Story 1.8 — Onboarding Wizard <= 5 步（FR A9 完整版）

## User Story

**As** a new user
**I want** a 5-step onboarding wizard that guides me through 注册 → 验证 → 拿 API Key → Postman 导入 → Hello World 跑通
**so that** I can reach first value in under 3 minutes without having to infer the product flow from multiple pages.

## Why this story

FR A9 is marked v1 必上, but the current product still exposes the flow as separate pages: `/auth/signup` gets the user in, `/welcome` shows the key, and the rest is only implied. That is functional, but not a wizard.

This story does not add new backend capability. It turns the existing J1 surfaces into one coherent onboarding flow with:
1. a shared wizard shell,
2. explicit step progress,
3. route handoff between existing pages,
4. a skip/resume path, and
5. a 5-minute rescue prompt if the user stalls.

The implementation should reuse existing auth, API-key, Postman, and LP solve helpers instead of inventing new versions of those flows.

## Out of scope

- New auth-service endpoints or new signup/login semantics
- New API-key or Postman-generation logic
- New billing/credits behavior
- Real customer-support ticketing or CRM integration
- Forcing every user through all 5 steps
- New landing page or marketing funnel redesign
- Analytics backend instrumentation beyond local completion state and UI hooks

## Acceptance Criteria

### AC1: Shared wizard shell exists

- A new `SignupWizard` shared component exists in `packages/ui`
- It is a client component and may read browser storage / timers
- It is exported from `packages/ui/src/index.ts`
- It renders a 5-step progress model with current, completed, pending, and skipped states
- It uses the existing `useA11y` baseline and does not introduce nested modals
- It is route-agnostic so the same shell can be mounted on `/auth/signup` and `/welcome`

### AC2: The J1 onboarding journey is visible as 5 steps

- The wizard labels the journey as:
  1. 注册
  2. 验证
  3. 拿 API Key
  4. Postman 导入
  5. Hello World 跑通
- `/auth/signup` starts the wizard at step 1
- Step 2 is the existing verification / authenticated-session checkpoint; when a user needs to resume or re-verify, the wizard can hand off to `/auth/login`
- `/welcome` continues the same wizard at steps 3-5
- The wizard explains progress without blocking the existing success path
- Step completion is derived from existing auth/session state and page transitions: signup success = step 1, authenticated session = step 2, API key visible = step 3, Postman export triggered = step 4, LP success visible = step 5
- No new backend state machine is required

### AC3: The wizard is resumable and skippable

- Users can dismiss or skip the wizard at any step
- Skipping does not erase already completed progress
- Returning users resume at the last incomplete step
- Progress persists across refresh via URL state plus browser storage keyed to the current user/session, including the last completed step and completion timestamp
- The wizard never becomes a dead end; the main app remains reachable

### AC4: The 5-minute rescue prompt exists

- If the user has not completed step 5 within 5 minutes of starting onboarding, the UI shows a proactive help prompt
- The prompt uses existing UI patterns (`ConfirmationModal` or `StatusCard`), is accessible, and can be dismissed
- The prompt offers actionable next steps such as resume, open quickstart, or skip for later
- The prompt must not appear on top of another modal; defer or downgrade to a banner if a modal is already open
- The prompt fires only once per onboarding session unless the user explicitly restarts the wizard

### AC5: Existing surfaces are reused, not duplicated

- Step 3 reuses the existing API-key reveal / copy-once patterns already present in `1.1b` and `APIKeyManager`
- Step 4 reuses the existing Postman download helper
- Step 5 reuses the existing Hello World LP solve path and existing success/result surfaces
- Step 4 is marked complete when the existing Postman download action succeeds without throwing
- Step 5 is marked complete only after `postOptimization()` resolves with `status="completed"` and a visible success/result state is rendered
- `/auth/signup`, `/auth/login`, and `/welcome` continue to use existing auth helpers and route patterns
- No duplicate Postman collection generator, no duplicate API-key modal, and no duplicate LP demo are introduced

### AC6: UI and accessibility fit the current product

- Wizard layout stays dense and utilitarian, not marketing-like
- Mobile and desktop layouts remain stable; text does not overflow containers
- Step controls, skip actions, and rescue prompt are keyboard accessible
- Wizard copy stays in the existing restrained product voice
- The implementation follows the current `packages/ui` component patterns and uses `lucide-react` where iconography is needed

### AC7: Tests and smoke coverage exist

- `packages/ui` has component-level coverage for the wizard shell and its states
- Web route tests cover progress handoff across `/auth/signup` and `/welcome`
- `/auth/login` covers the verify/resume branch for interrupted onboarding
- Timer behavior for the 5-minute rescue prompt is covered with fake timers or equivalent deterministic test control
- A browser smoke test covers the happy path from signup into the wizard and verifies the wizard renders completion state
- The web app builds cleanly after the route changes

### AC8: Quality gates

- `pnpm --filter @opticloud/ui test` passes
- `pnpm --filter @opticloud/ui typecheck` passes
- `pnpm --filter @opticloud/web test` passes
- `pnpm --filter @opticloud/web typecheck` passes
- Relevant Playwright onboarding smoke passes, or the blocker is documented in the Dev Agent Record
- No Python service test changes are expected for this UI-only story

### AC9: Scope guard

- No auth-service, solver-orchestrator, billing-service, or database schema changes are introduced
- No new runtime dependency is added to `apps/web`; `packages/ui` may use its existing dependencies only
- Existing `/auth/signup`, `/auth/login`, `/welcome`, Postman, and LP solve behaviors keep their current happy paths
- `sprint-status.yaml` is updated to `ready-for-dev` after story creation and to `done` only after implementation review passes

## Tasks / Subtasks

- [x] Task 1: Define the onboarding state contract and persistence model (AC: 1, 2, 3, 4)
  - [x] Add a small web helper for onboarding state, step ids, persisted keys, and timer lifecycle
  - [x] Decide the route/query contract for resuming a partially completed wizard
  - [x] Keep the state model compatible with existing `sessionStorage` / `localStorage` usage in auth flows

- [x] Task 2: Build `SignupWizard` as a shared UI component (AC: 1, 2, 6)
  - [x] Create `packages/ui/src/components/SignupWizard/index.tsx`
  - [x] Export it from `packages/ui/src/index.ts`
  - [x] Add Storybook coverage for the 5-step shell, completed state, skipped state, and help prompt state
  - [x] Reuse existing UI primitives rather than inventing new modal or card patterns

- [x] Task 3: Wire the existing auth pages into the wizard flow (AC: 2, 3, 5)
  - [x] Update `apps/web/src/app/auth/signup/page.tsx` to mount step 1-2 wizard content
  - [x] Update `apps/web/src/app/auth/login/page.tsx` so interrupted onboarding can resume at step 2 and return to the wizard after successful auth
  - [x] Update `apps/web/src/app/welcome/page.tsx` to continue steps 3-5
  - [x] Keep the current signup/login/API-key/LP helpers as the source of truth
  - [x] Preserve direct page access for users who skip the wizard

- [x] Task 4: Add the 5-minute help prompt and resume behavior (AC: 3, 4)
  - [x] Start the timer when onboarding begins
  - [x] Cancel or complete the timer when the wizard is finished or dismissed
  - [x] Ensure the prompt is non-blocking if a modal is already on screen
  - [x] Provide a way to re-open the wizard from the help state

- [x] Task 5: Cover the flow with tests (AC: 6, 7)
  - [x] Add unit tests for state transitions and persistence
  - [x] Add route-level tests for signup → welcome handoff
  - [x] Add deterministic coverage for the 5-minute prompt
  - [x] Add or update a Playwright smoke for the happy path
  - [x] Run the Story 1.8 quality gates and record commands in the Dev Agent Record

- [x] Task 6: Update docs and sprint tracking (AC: 7, 8, 9)
  - [x] Update `apps/web/README.md` with the onboarding flow summary if needed
  - [x] Update `sprint-status.yaml` to `ready-for-dev` now and `done` after implementation

## Dev Notes

- Prefer the existing auth-service and web patterns already in the repo; this story is composition, not a new backend capability
- The onboarding shell should reuse the existing route split:
  - `/auth/signup` for entry
  - `/auth/login` for verification/resume when needed
  - `/welcome` for API key, Postman, and Hello World completion
- Do not reimplement API-key display or Postman export logic; reuse the helpers already used by `welcome`
- Do not reimplement the LP demo; reuse the existing `postOptimization` happy path
- Use the existing `ConfirmationModal`, `StatusCard`, `APIKeyManager`, `LoadingShimmer`, and `EmptyState` primitives as building blocks
- Keep the rescue prompt separate from any other modal to avoid the nested-modal anti-pattern
- The wizard should feel like a progress guide, not a hard gate; the user can still reach the app if they dismiss it
- Route state should be stable enough that a refresh does not reset the current step
- Persist wizard state under a stable per-user/session key and store the last completed step plus completion marker
- If a step needs an icon, use `lucide-react` from the existing UI dependency set instead of hand-drawn SVGs
- Do not add a new state-management package for this story; local React state plus the small onboarding helper is sufficient
- Tests should prefer deterministic fake timers for the 5-minute prompt instead of waiting in real time
- This story should not edit Python services or SQL migrations. If implementation finds a backend gap, stop and record it as a follow-up instead of expanding scope.

### Project Structure Notes

- Shared wizard component: `packages/ui/src/components/SignupWizard/*`
- Shared exports: `packages/ui/src/index.ts`
- Web onboarding helper: likely `apps/web/src/lib/onboarding.ts` or equivalent
- Route wiring: `apps/web/src/app/auth/signup/page.tsx`, `apps/web/src/app/welcome/page.tsx`
- Possible verification handoff touchpoint: `apps/web/src/app/auth/login/page.tsx`
- No new service, DB table, or auth endpoint is expected for this story

### Risks & Mitigations

| Risk | Mitigation |
|---|---|
| The wizard becomes a second copy of signup/login/welcome | Keep the wizard as a shell that composes the existing pages and helpers |
| Step 2 verification conflicts with the current signup fast path | Treat verification as a progress checkpoint, not a new backend flow |
| The 5-minute help prompt pops over another modal | Defer it or downgrade it to a banner until the modal closes |
| Persistence drifts across refresh or tabs | Use URL state plus browser storage keyed by user/session |
| The flow feels forced | Every step must have a skip/dismiss path and the app must remain usable |
| Postman download cannot be observed in jsdom | Wrap the existing helper call and assert the wizard marks completion when the click handler returns |
| LP success is faked by UI state only | Mark completion only from the resolved `postOptimization()` response, not from button click |
| UI story expands into backend work | Keep backend/schema edits out of scope and open a follow-up story if a real gap appears |

### References

- [Source: D:/优化预测网站/_bmad-output/planning/epics.md:351]
- [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1268]
- [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1325]
- [Source: D:/优化预测网站/_bmad-output/planning/prd.md:469]
- [Source: D:/优化预测网站/_bmad-output/planning/prd.md:476]
- [Source: D:/优化预测网站/_bmad-output/planning/prd.md:588]
- [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1231]
- [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1389]
- [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1444]
- [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:1251]
- [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:3108]
- [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:3155]
- [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:3282]
- [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:158]
- [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:303]
- [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:425]
- [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:562]
- [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:1681]
- [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:3004]
- [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:3107]

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- `pnpm --filter @opticloud/ui test -- SignupWizard`
- `pnpm --filter @opticloud/web test -- onboarding`
- `pnpm --filter @opticloud/ui test`
- `pnpm --filter @opticloud/ui typecheck`
- `pnpm --filter @opticloud/web test`
- `pnpm --filter @opticloud/web typecheck`
- `pnpm --dir e2e exec playwright test tests/j1-happy-path.spec.ts --project=chromium`

### Completion Notes List

- Completed the shared `SignupWizard` component with five-step progress, skipped/completed/current states, support banner state, Storybook coverage, and Vitest coverage.
- Added `apps/web/src/lib/onboarding.ts` for deterministic onboarding state, per-user/session storage keys, step completion, skip/dismiss behavior, and 5-minute support prompt eligibility.
- Wired `/auth/signup`, `/auth/login`, and `/welcome` into the wizard without adding backend endpoints or schema changes.
- Reused existing API key, Postman export, and LP solve paths; Postman completion is marked after the download helper returns and Hello World completion is marked after a completed optimization response.
- Updated J1 Playwright happy path to assert wizard rendering and completion state.
- Fixed two existing UI quality-gate blockers surfaced by running Story 1.8 gates: `jest-axe` matcher registration for Vitest and missing accessible name on `SparklineKPI` SVG.
- Code review fixes added anonymous signup refresh persistence, signup-page 5-minute rescue prompt coverage, quickstart action/link support, a `/docs/quickstart` support page, and explicit completed-step tracking so skipped steps are not silently overwritten by later completion.

### File List

- `_bmad-output/stories/1-8-onboarding-wizard-5steps.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/README.md`
- `apps/web/src/app/auth/login/page.tsx`
- `apps/web/src/app/auth/signup/page.tsx`
- `apps/web/src/app/docs/quickstart/page.tsx`
- `apps/web/src/app/welcome/page.tsx`
- `apps/web/src/lib/onboarding.ts`
- `apps/web/src/lib/onboarding.test.ts`
- `e2e/playwright.config.ts`
- `e2e/tests/j1-happy-path.spec.ts`
- `packages/ui/src/components/SignupWizard/index.stories.tsx`
- `packages/ui/src/components/SignupWizard/index.test.tsx`
- `packages/ui/src/components/SignupWizard/index.tsx`
- `packages/ui/src/components/SparklineKPI/index.tsx`
- `packages/ui/src/hooks/useA11y.test.tsx`
- `packages/ui/src/index.ts`
- `packages/ui/src/test-setup.ts`

### Change Log

- 2026-05-23 — Story 1.8 implementation completed and moved to review: shared SignupWizard, web onboarding state helper, signup/login/welcome route wiring, tests, README update, E2E smoke update, and UI quality-gate fixes.
- 2026-05-23 — Code review completed: fixed 4 patch findings, reran all Story 1.8 quality gates, and moved story to done.

## Senior Developer Review (AI)

### Review Date

2026-05-23

### Review Result

Approved after fixes. No unresolved decision-needed, patch, or deferred findings remain.

### Review Findings

- [x] [Review][Patch] Signup onboarding did not reload anonymous persisted state after refresh — fixed by loading/saving anonymous onboarding state on `/auth/signup`.
- [x] [Review][Patch] The 5-minute rescue prompt only existed on `/welcome`, leaving users stalled on signup without help — fixed by adding the same non-blocking support prompt path to `/auth/signup`.
- [x] [Review][Patch] Support prompt copy promised a quickstart action, but the prompt did not expose one and `/docs/quickstart` was missing — fixed with a secondary quickstart action and a focused quickstart page.
- [x] [Review][Patch] Completing `hello-world` could visually imply skipped earlier steps were complete — fixed with explicit `completedSteps` tracking while preserving skipped steps.

### Verification

- `pnpm --filter @opticloud/ui test` — pass, 38 tests
- `pnpm --filter @opticloud/ui typecheck` — pass
- `pnpm --filter @opticloud/web test` — pass, 50 tests
- `pnpm --filter @opticloud/web typecheck` — pass
- `pnpm --dir e2e exec playwright test tests/j1-happy-path.spec.ts --project=chromium` — pass
