---
story_key: 1-10-language-switch-zh
epic_num: 1
story_num: 1.10
epic_name: Account & Identity
status: done
priority: 🟠 High (FR A3 v1 必上；NFR-8 i18n 框架 hard-gate)
sizing: M (~8-10 hours; next-intl scaffold + locale preference + key-page fallback + tests)
type: implementation + ui + test
created_by: bmad-create-story
created_at: 2026-05-25
sources:
  - [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1335-1337]
  - [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1438]
  - [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1777-1786]
  - [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:114]
  - [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:140]
  - [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:331-335]
  - [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:678]
  - [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:1637]
  - [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:3620]
  - [Source: D:/优化预测网站/apps/web/src/app/layout.tsx:1-20]
  - [Source: D:/优化预测网站/apps/web/src/lib/api.ts:1-455]
  - [Source: D:/优化预测网站/apps/web/src/lib/postman.ts:1-141]
  - [Source: D:/优化预测网站/apps/web/src/app/page.tsx:1-111]
  - [Source: D:/优化预测网站/apps/web/src/app/auth/signup/page.tsx:1-294]
  - [Source: D:/优化预测网站/apps/web/src/app/auth/login/page.tsx:1-277]
  - [Source: D:/优化预测网站/_bmad-output/stories/1-9-under-14-block.md:1-267]
  - [Source: https://next-intl.dev/docs/getting-started/app-router]
  - [Source: https://nextjs.org/docs/app/guides/internationalization]
dependencies:
  upstream:
    - 0-9-ui-tier1-stubs (done) — shared UI primitives already exist
    - 0-10-tailwind-brand-tokens (done) — visual styling should reuse existing tokens
    - 1-2-user-login (done) — login page is a key fallback page
    - 1-8-onboarding-wizard-5steps (done) — signup/welcome onboarding copy must remain coherent
    - 1-9-under-14-block (done) — signup/login age-gate copy must stay distinct and localizable
  downstream:
    - 1-11-geo-anomaly-risk — risk modal copy and API language header should reuse locale preference
    - 3-7-rfc7807-errors-detail — error panels should consume `Accept-Language`
    - 5-d-1-bilingual-invoices — later bilingual invoice work should reuse locale primitives
    - 8-b-5-error-i18n-eslint — later error i18n audit should find a single locale source
---

# Story 1.10 — 语言切换 zh-CN（FR A3）

Status: done

## User Story

**As** an authenticated or anonymous user
**I want** to choose my preferred interface language between `zh-CN` and `en-US`
**so that** core OptiCloud pages, request headers, and fallback error surfaces honor one consistent locale.

## Why this story

FR A3 says users can configure preferred language. NFR-8 says v1 must have an i18n framework, complete `zh-CN`, and `en-US` fallback for key pages. The current web app hard-codes `<html lang="zh-CN">` and sends `Accept-Language: zh-CN` from the API client, so user preference cannot influence UI, backend error language, or generated Postman examples.

This story installs the minimal v1 i18n foundation: a locale preference source, a small next-intl scaffold, a visible switcher on key pages, synchronized `Accept-Language`, and `en-US` fallback copy for critical first-run/auth/error pages.

## Out of Scope

- Full translation of every console, academic, billing, Excel, and algorithm-detail surface
- URL locale prefixes such as `/zh-CN/...` or `/en-US/...`
- Database persistence of user language preference
- Browser geolocation or IP-based language detection
- Machine translation workflow, Crowdin, or translation management automation
- Backend message-catalog implementation beyond consuming `Accept-Language`
- Currency conversion; only locale formatting hooks are introduced

## Acceptance Criteria

### AC1: Locale model is explicit and bounded

- Supported locales are exactly `zh-CN` and `en-US`
- Default locale is `zh-CN`
- Unsupported, missing, or malformed locale values fall back to `zh-CN`
- Locale constants are exported from one web-local module and reused by UI, API client, and tests

### AC2: next-intl framework is present without route churn

- `next-intl` is added to `apps/web`
- The app defines local message files for `zh-CN` and `en-US`
- Request configuration reads the selected locale from a cookie or local preference bridge and loads matching messages
- `RootLayout` wraps children in `NextIntlClientProvider`
- Existing routes remain unchanged; no `[locale]` dynamic route or route-prefix migration is introduced in this story

### AC3: User can switch preferred language on key pages

- A reusable language switcher is available to client pages
- The switcher persists the selected locale in `localStorage` and a cookie
- The switcher updates `document.documentElement.lang` immediately on the client
- The switcher labels use native names: `中文` and `English`
- Key pages include the switcher without adding marketing-layout churn:
  - `/`
  - `/auth/signup`
  - `/auth/login`
  - `/auth/guardian-confirmation`
  - `/welcome`
  - `not-found`

### AC4: Key-page copy has zh-CN primary and en-US fallback

- `zh-CN` messages cover the key pages listed in AC3
- `en-US` messages cover the same message keys for fallback
- Signup/login age-gate, OTP, onboarding, welcome, and not-found copy stay semantically equivalent across locales
- Chinese remains the default visible language for first load

### AC5: API client honors preferred language

- All calls through `apps/web/src/lib/api.ts` send `Accept-Language` from the current locale preference
- Invalid or unavailable browser storage falls back to `zh-CN`
- Existing per-request headers still override or merge correctly with the locale header
- Node/test environments do not crash when `window`, `document`, or `localStorage` are absent

### AC6: Postman collection defaults to the preferred language

- `generatePostmanCollection` accepts an optional locale or reads the shared default
- Generated request headers use the chosen `Accept-Language`
- Existing default remains `zh-CN`
- Tests cover the default and `en-US` generated headers

### AC7: Hydration and SSR/CSR boundaries are stable

- Server-rendered `<html lang>` starts at `zh-CN`
- Client-side locale changes update the DOM without hydration errors
- The switcher works after route navigation because preference is stored outside component state
- Components that use browser-only storage are client components only

### AC8: Tests close data, function, and boundary paths

- Unit tests cover locale normalization and storage fallback
- API client tests cover `Accept-Language` for default, `en-US`, unsupported values, and explicit header merge behavior
- Component tests cover language switch rendering and `document.documentElement.lang` update
- Page-level tests cover at least signup or login English fallback copy
- Existing web typecheck and Vitest suites pass

## Tasks / Subtasks

- [x] Task 1: Add locale primitives and next-intl scaffold (AC: 1, 2, 7)
  - [x] Add `next-intl` to `apps/web`
  - [x] Create locale constants, type guards, and normalization helper
  - [x] Add `messages/zh-CN.json` and `messages/en-US.json`
  - [x] Add `src/i18n/request.ts` using cookie-backed locale resolution
  - [x] Wrap the root layout with `NextIntlClientProvider`

- [x] Task 2: Build reusable language preference UI (AC: 3, 7)
  - [x] Create a client-side language switcher component
  - [x] Persist selection to `localStorage` and cookie
  - [x] Update `document.documentElement.lang` on load and selection
  - [x] Keep control compact, accessible, and consistent with existing Tailwind tokens

- [x] Task 3: Localize key pages without route restructuring (AC: 3, 4, 7)
  - [x] Wire switcher and message lookup into `/`
  - [x] Wire switcher and message lookup into `/auth/signup`
  - [x] Wire switcher and message lookup into `/auth/login`
  - [x] Wire switcher and message lookup into `/auth/guardian-confirmation`
  - [x] Wire switcher and message lookup into `/welcome`
  - [x] Wire switcher and fallback copy into `not-found`

- [x] Task 4: Synchronize outbound request language (AC: 5, 6)
  - [x] Update `apps/web/src/lib/api.ts` to read normalized locale for `Accept-Language`
  - [x] Preserve caller-provided headers and Authorization / Idempotency-Key behavior
  - [x] Update Postman collection generation to use locale option/default
  - [x] Keep server/test environments storage-safe

- [x] Task 5: Add tests and run validation (AC: 1, 3, 5, 6, 8)
  - [x] Unit-test locale normalization and persistence fallback
  - [x] Unit-test API `Accept-Language` selection and override behavior
  - [x] Unit-test Postman locale header generation
  - [x] Component-test language switcher DOM update
  - [x] Update existing signup/login tests for localized copy where needed
  - [x] Run `pnpm --dir apps/web test`
  - [x] Run `pnpm --dir apps/web typecheck`
  - [x] Run `git diff --check`

- [x] Task 6: Update story and sprint tracking (AC: 8)
  - [x] Fill Dev Agent Record with implementation notes and validation outputs
  - [x] Update File List with every touched file
  - [x] Move story status to `review` after implementation
  - [x] Move sprint status to `review` after implementation

## Dev Notes

- Use `next-intl` because architecture explicitly locks it as the frontend i18n framework. The official next-intl App Router setup requires message files, `i18n/request.ts`, plugin wiring, and `NextIntlClientProvider`; for apps without locale-specific paths, its docs support cookie-based locale selection. [Source: https://next-intl.dev/docs/getting-started/app-router]
- Current app is Next.js 15 App Router with flat routes. Next.js App Router i18n guidance supports locale-aware rendering, but this story must avoid a `[locale]` route migration because it would touch every route and create onboarding/link regressions. [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:331-335] [Source: https://nextjs.org/docs/app/guides/internationalization]
- Use `zh-CN` and `en-US` strings exactly. Do not introduce aliases such as `zh`, `en`, `cn`, or `english` outside normalization tests.
- Source of truth should be web-local, for example `apps/web/src/lib/locale.ts`. Do not put browser storage logic inside `api.ts` directly if a small helper can isolate SSR/test behavior.
- Current hard-coded header is in `apps/web/src/lib/api.ts`; replacing it must not break Authorization, Idempotency-Key, or service base URL behavior.
- Current Postman generator has one hard-coded `Accept-Language: zh-CN` header. Update generation without changing collection ownership or endpoint examples.
- `RootLayout` currently hard-codes `<html lang="zh-CN">`; keep the server default as `zh-CN` and let the client preference bridge update the DOM after hydration.
- The first translation pass should prioritize user-visible text on key pages. Leave specialized pages like `/console/excel`, `/academic`, and algorithm detail pages untouched unless a reused component needs locale-safe behavior.
- Keep auth age-gate semantics from Story 1.9 intact: pending guardian copy must remain distinct from frozen-account copy.
- UI should stay work-focused and dense. The language switcher should be a compact segmented control or small select/menu, not a marketing banner.

### Project Structure Notes

- Locale primitives: `apps/web/src/lib/locale.ts`
- next-intl request config: `apps/web/src/i18n/request.ts`
- Message files: `apps/web/messages/zh-CN.json`, `apps/web/messages/en-US.json`
- Provider / root lang: `apps/web/src/app/layout.tsx`
- Switcher component: `apps/web/src/components/LanguageSwitcher.tsx`
- API language header: `apps/web/src/lib/api.ts`
- Postman language header: `apps/web/src/lib/postman.ts`
- Key pages: `apps/web/src/app/{page.tsx,not-found.tsx,welcome/page.tsx,auth/signup/page.tsx,auth/login/page.tsx,auth/guardian-confirmation/page.tsx}`
- Tests should follow current Vitest + React Testing Library patterns in `apps/web/src/app/auth/*/*.test.tsx` and pure lib tests in `apps/web/src/lib/*.test.ts`

### References

- [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1335-1337]
- [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1438]
- [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1777-1786]
- [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:114]
- [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:140]
- [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:331-335]
- [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:678]
- [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:1637]
- [Source: D:/优化预测网站/_bmad-output/planning/ux-design-specification.md:3620]
- [Source: D:/优化预测网站/apps/web/src/app/layout.tsx:1-20]
- [Source: D:/优化预测网站/apps/web/src/lib/api.ts:1-455]
- [Source: D:/优化预测网站/apps/web/src/lib/postman.ts:1-141]
- [Source: D:/优化预测网站/apps/web/src/app/page.tsx:1-111]
- [Source: D:/优化预测网站/apps/web/src/app/auth/signup/page.tsx:1-294]
- [Source: D:/优化预测网站/apps/web/src/app/auth/login/page.tsx:1-277]
- [Source: D:/优化预测网站/_bmad-output/stories/1-9-under-14-block.md:1-267]
- [Source: https://next-intl.dev/docs/getting-started/app-router]
- [Source: https://nextjs.org/docs/app/guides/internationalization]

## Three-Round Story Review

### Round 1: Data Consistency Review

Scope: locale enum, persistence keys, message-key shape, `html lang`, and `Accept-Language`.

Findings and fixes:

- [x] Locale value drift risk: planning docs mention zh/en casually, while API contracts require `zh-CN` / `en-US`. Fixed by making exact supported locale values an AC and requiring normalization tests.
- [x] Header/storage divergence risk: API, Postman, DOM, and UI could each invent their own locale source. Fixed by requiring one locale module reused by API, switcher, and tests.
- [x] Message-key mismatch risk: `zh-CN` and `en-US` could diverge during manual translation. Fixed by requiring both files cover the same key-page message keys.
- [x] SSR/client mismatch risk: root `html lang` cannot know `localStorage` during SSR. Fixed by keeping SSR default `zh-CN` and requiring client-side DOM update after hydration.

Round 1 result: PASS after story corrections.

### Round 2: Function Consistency / Drift Review

Scope: Next.js App Router behavior, next-intl setup, auth/onboarding pages, API client behavior, and Postman generation.

Findings and fixes:

- [x] Route-churn risk: implementing `[locale]` segments would force broad link and page migration. Fixed by explicitly forbidding route-prefix migration in this story.
- [x] Dependency ambiguity: architecture requires `next-intl`, but package.json currently lacks it. Fixed by making `next-intl` an explicit story task, so dev-story can add it without treating it as scope creep.
- [x] Auth copy regression risk: age-gate pending copy from Story 1.9 could collapse into generic frozen-account copy. Fixed by naming signup/login age-gate semantics in AC4 and Dev Notes.
- [x] Request override risk: updating `api.ts` could drop Authorization or Idempotency headers. Fixed by requiring header merge and explicit tests.

Round 2 result: PASS after story corrections.

### Round 3: Boundary / Closure Review

Scope: unsupported locales, unavailable browser APIs, hydration, test closure, and no full-i18n scope creep.

Findings and fixes:

- [x] Unsupported locale boundary was initially implicit. Fixed by requiring malformed/missing/unsupported fallback to `zh-CN`.
- [x] Browser-only API risk: tests and server components can crash if locale helpers assume `window`. Fixed by requiring storage-safe helpers for Node/test environments.
- [x] Scope creep risk: full console/Excel/academic translation is too large and not required by FR A3. Fixed by narrowing `en-US` fallback to key pages.
- [x] Closure gap: tests must prove data consistency, function consistency, and boundary behavior. Fixed by requiring locale helper, API header, Postman, switcher, and page-level tests.

Round 3 result: PASS after story corrections; story is ready for dev implementation.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- Story authoring and source inspection completed on 2026-05-25.
- Implementation started on 2026-05-25.
- Validation: `pnpm --dir apps/web test` → 14 files / 71 tests passed.
- Validation: `pnpm --dir apps/web typecheck` → passed.
- Validation: `git diff --check` → passed.

### Completion Notes List

- Created Story 1.10 for FR A3 language preference and i18n foundation.
- Completed three story review rounds and applied corrections before implementation.
- Added `next-intl` App Router scaffold without `[locale]` route migration.
- Added bounded locale primitives for `zh-CN` / `en-US`, storage/cookie persistence, DOM `html lang` sync, and safe server/test fallback behavior.
- Added reusable compact `LanguageSwitcher` and wired it into landing, signup, login, guardian confirmation, welcome, and not-found surfaces.
- Added key-page `zh-CN` primary and `en-US` fallback messages while keeping auth age-gate semantics distinct.
- Updated web API client and Postman collection generation to use the normalized preferred locale for `Accept-Language`.
- Added regression tests for locale normalization, API headers, Postman headers, switcher DOM sync, and signup English fallback.

### File List

- `_bmad-output/stories/1-10-language-switch-zh.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/package.json`
- `pnpm-lock.yaml`
- `apps/web/next.config.mjs`
- `apps/web/messages/zh-CN.json`
- `apps/web/messages/en-US.json`
- `apps/web/src/i18n/request.ts`
- `apps/web/src/components/LocaleProvider.tsx`
- `apps/web/src/components/LanguageSwitcher.tsx`
- `apps/web/src/components/LanguageSwitcher.test.tsx`
- `apps/web/src/lib/locale.ts`
- `apps/web/src/lib/locale.test.ts`
- `apps/web/src/lib/messages.ts`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/api-locale.test.ts`
- `apps/web/src/lib/account-deletion.test.ts`
- `apps/web/src/lib/postman.ts`
- `apps/web/src/lib/postman.test.ts`
- `apps/web/src/app/layout.tsx`
- `apps/web/src/app/page.tsx`
- `apps/web/src/app/not-found.tsx`
- `apps/web/src/app/auth/signup/page.tsx`
- `apps/web/src/app/auth/signup/page.test.tsx`
- `apps/web/src/app/auth/login/page.tsx`
- `apps/web/src/app/auth/guardian-confirmation/page.tsx`
- `apps/web/src/app/welcome/page.tsx`
- `apps/web/src/lib/onboarding.ts`
- `packages/ui/src/components/SignupWizard/index.tsx`
- `packages/ui/src/components/SignupWizard/index.test.tsx`

### Implementation Plan

- Add bounded `zh-CN` / `en-US` locale primitives first, then wire next-intl and the provider.
- Build a small client-side switcher that persists locale and updates `html lang`.
- Localize only the critical auth/landing/welcome/error surfaces required by this story.
- Route all API/Postman `Accept-Language` behavior through the same normalized locale source.

### Change Log

- 2026-05-25: Created and three-round reviewed Story 1.10; status set to ready-for-dev.
- 2026-05-25: Started dev-story implementation; status set to in-progress.
- 2026-05-25: Implemented language preference foundation, key-page fallback messages, locale-aware API/Postman headers, and tests; status set to review.
- 2026-05-25: Completed implementation code review and fixed uncovered API-key revoke header, Headers merge/test assertions, guardian fallback copy, and localized onboarding wizard labels; status set to done.

### Senior Developer Review (AI)

Outcome: Approve after fixes

Review date: 2026-05-25

Findings and fixes:

- [x] Medium: `revokeAPIKey` still used direct `fetch` without `Accept-Language`, leaving one auth API path outside the locale contract. Fixed by adding the normalized language header to the revoke call.
- [x] Medium: Header merge in the shared API client used object spread, which is brittle for `Headers` instances and arrays. Fixed by normalizing through `new Headers(init.headers)` and setting defaults only when missing.
- [x] Medium: `SignupWizard` still rendered Chinese state/action labels inside English key pages. Fixed by adding optional localized `stateText` and `actionLabels` props, plus web-side localized onboarding step labels.
- [x] Low: Guardian confirmation Suspense fallback stayed hard-coded in Chinese. Fixed by reading the preferred locale in the page wrapper and using localized fallback copy.
- [x] Low: Existing tests asserted plain object headers after the client switched to standard `Headers`. Fixed tests to inspect `Headers.get()` directly.

Validation after review fixes:

- `pnpm --dir apps/web test` → 14 files / 71 tests passed.
- `pnpm --dir apps/web typecheck` → passed.
- `pnpm --dir packages/ui test` → 8 files / 50 tests passed.
- `pnpm --dir packages/ui typecheck` → passed.
- `git diff --check` → passed.

Residual risk:

- Specialized console/Excel/academic pages remain zh-only by scope; this is intentional per Story 1.10 and should be expanded by later i18n stories.
