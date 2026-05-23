---
story_key: 1-10-language-switch-zh
epic_num: 1
story_num: 1.10
epic_name: Account & Identity
status: done
priority: 🔴 Critical (FR A3 v1 必上；i18n 框架与语言偏好基础能力)
sizing: M (~1 day; web i18n foundation + locale preference + key page fallback + tests)
type: implementation + i18n + ui + test
created_by: bmad-create-story
created_at: 2026-05-23
sources:
  - [Source: _bmad-output/planning/epics.md:44]
  - [Source: _bmad-output/planning/epics.md:160]
  - [Source: _bmad-output/planning/epics.md:1335]
  - [Source: _bmad-output/planning/prd.md:1257]
  - [Source: _bmad-output/planning/prd.md:1777]
  - [Source: _bmad-output/planning/prd.md:1781]
  - [Source: _bmad-output/planning/prd.md:1786]
  - [Source: _bmad-output/planning/architecture.md:335]
  - [Source: _bmad-output/planning/architecture.md:678]
  - [Source: _bmad-output/planning/architecture.md:1637]
  - [Source: _bmad-output/planning/ux-design-specification.md:119]
  - [Source: _bmad-output/planning/ux-design-specification.md:132]
  - [Source: _bmad-output/planning/ux-design-specification.md:3156]
  - [Source: _bmad-output/stories/1-9-under-14-block.md]
dependencies:
  upstream:
    - 1-8-onboarding-wizard-5steps (done) — signup / welcome now use SignupWizard and onboarding state helpers
    - 1-9-under-14-block (done) — signup has age-gate copy and union signup result handling
    - 2-1-j1-algorithms-public-list (done) — algorithm catalog already exposes zh/en descriptions
    - 6-a-1-citation-bibtex (done) — citation UI has known zh-only labels to keep as v1 fallback unless touched
  downstream:
    - 1-11-geo-anomaly-risk — auth risk/error surfaces should use current locale header later
    - 3-e-8-zh-ux-friendly-voice — zh copy polish should consume the same message keys
    - 8-b-5-error-i18n-eslint — future hard enforcement of error string single source
---

# Story 1.10 — 语言切换 zh-CN（FR A3）

## User Story

**As** an OptiCloud user who may read Chinese or English,
**I want** to choose a preferred interface language and have requests carry that preference,
**so that** v1 remains zh-CN complete while key pages and backend-facing errors have an en-US fallback path.

## Why this story

FR A3 requires configurable preferred language. PRD and Architecture both narrow v1 to a practical scope: zh-CN is complete, en-US is only a key-page fallback, and the technical foundation must use `next-intl` plus `Accept-Language`.

The current web app hardcodes `<html lang="zh-CN">`, hardcodes `"Accept-Language": "zh-CN"` in the API client, and renders Landing / signup / welcome / docs copy directly in page components. Landing already links to `/pricing`, and signup links to `/legal/tos` and `/legal/privacy`; those routes are part of the key-page fallback surface even if legal-content finalization remains blocked. This story introduces the i18n foundation and preference contract without attempting full-site English translation.

## Out of Scope

- Full-site en-US translation for every route, console workflow, and package UI component.
- Backend user-profile persistence for language preference.
- Backend error catalog migration or ESLint single-source enforcement; those are later FG1.3 / 8.B.5 work.
- Final legal-document authoring, legal review, or legal signoff. Minimal legal route shells may be added only to make existing links reachable and bilingual; they must not claim final legal approval.
- Rewriting all existing Chinese business copy or changing brand voice outside touched message keys.
- Locale-prefixed URLs such as `/zh-CN/...` or `/en-US/...`; existing routes must remain stable for current E2E and docs.
- Changing algorithm catalog response contracts. Use existing `description_zh` / `description_en` fields.

## Acceptance Criteria

### AC1: i18n framework is installed and wired without route churn

- `apps/web` depends on `next-intl` and uses its Next.js App Router integration.
- Supported locales are exactly `zh-CN` and `en-US`; default locale is `zh-CN`.
- Existing routes stay unchanged (`/`, `/auth/signup`, `/welcome`, `/docs/quickstart`, `/algorithms`, etc.). Do not require locale path prefixes in this story.
- `RootLayout` sets `<html lang>` from the resolved locale, not a hardcoded string.
- Missing en-US messages fall back to zh-CN instead of throwing or showing raw message ids.
- Middleware, if added, must exclude `/_next`, static assets, API-like paths, and file-extension requests. It must not redirect existing page routes.

### AC2: User can explicitly switch language preference

- A compact language switch appears on key entry surfaces: Landing header, signup page, welcome page, quickstart docs page, pricing page, and legal page shells.
- The switch offers `中文` and `English` options and stores the preference in a cookie usable by server components and browser code.
- Cookie contract: `opticloud-locale=<zh-CN|en-US>`, `path=/`, `SameSite=Lax`, non-HttpOnly so browser fetch code can read it, and a long but explicit max-age (for example 180 days).
- The switch updates the current page without losing the current route.
- If no explicit preference exists, the app may use `Accept-Language` negotiation; invalid cookie/header values fall back to `zh-CN`.
- The UI labels and ARIA labels for the switch come from i18n messages.

### AC3: API client sends the current locale through `Accept-Language`

- `apps/web/src/lib/api.ts` no longer hardcodes `"Accept-Language": "zh-CN"`.
- Browser calls use the saved locale cookie/preference; server or test calls fall back to `zh-CN`.
- Callers can still override `Accept-Language` through `init.headers` for focused tests.
- Header value must be normalized to one supported locale (`zh-CN` or `en-US`), not the raw multi-value browser header.
- Existing auth, solver, and billing API functions preserve their request bodies and error handling.

### AC4: zh-CN remains the complete baseline on key flows

- Landing, signup, welcome, quickstart, pricing, legal shells, and not-found route copy renders through message keys for all user-visible labels touched in this story.
- Existing J1 happy-path Chinese assertions remain valid when locale is `zh-CN`.
- Story 1.9 age-gate copy remains clear, professional, and free of patronizing terms such as "亲" / "哦" or emoji-heavy consumer SaaS voice.

### AC5: en-US fallback exists for key v1 pages

- en-US messages cover at least Landing, Pricing, Docs/Quickstart, Error/Not Found, Legal Terms, Privacy, EULA shell, Signup/onboarding, and Welcome.
- The English experience is a fallback, not a full product promise. It is acceptable for algorithm examples, backend catalog data, and deep console pages to remain mixed or zh-CN where not in the key-page list.
- Pricing and legal pages can be minimal route shells if no full page exists yet; the acceptance bar is reachable bilingual fallback plus stable links, not final pricing strategy or final legal terms.
- When locale is `en-US`, signup still completes adult J1 flow and welcome still allows API-key generation and LP demo solve.

### AC6: Onboarding and route behavior are not regressed

- Onboarding state keys, step ids, and storage behavior stay compatible with Story 1.8.
- The SignupWizard display labels can localize, but its state machine and completed/skipped semantics do not change.
- If `SignupWizard` status labels are needed in English, add optional label override props with zh-CN defaults so existing package consumers and Storybook remain compatible.
- Adult signup, guardian-pending signup, and under-14 policy errors continue to behave as Story 1.9 defined.
- Existing links keep their destination paths and do not introduce redirects that break Playwright tests.

### AC7: Tests prove language selection and API header behavior

- Add focused unit tests for locale detection/persistence helpers and API `Accept-Language` header behavior.
- Add or update web tests so default zh-CN remains stable and en-US preference can be read without browser-only globals crashing in Vitest.
- Update Playwright J1 smoke only if selectors need a stable zh-CN default; do not make the smoke depend on English text.
- Add a small Playwright coverage path for switching to English on Landing and verifying at least one English key-page heading plus the cookie/header state; keep the full J1 smoke in default zh-CN.
- `pnpm --filter @opticloud/web test`, `pnpm --filter @opticloud/web typecheck`, and relevant Playwright smoke pass.

## Tasks / Subtasks

- [x] Task 1: Add locale configuration and `next-intl` wiring (AC: 1)
  - [x] Add `next-intl` dependency to `apps/web/package.json` / lockfile.
  - [x] Add locale constants and message loading helpers under `apps/web/src/i18n` or `apps/web/src/lib/i18n`.
  - [x] Wire Next.js config and request configuration for App Router.
  - [x] Add middleware only if needed for cookie/header negotiation; configure matcher exclusions so static assets and data files are untouched.
  - [x] Update `RootLayout` to resolve locale and provide messages to descendants.

- [x] Task 2: Add language preference UI (AC: 2, 4, 5)
  - [x] Create a reusable `LanguageSwitcher` client component.
  - [x] Persist locale in a cookie shared by client and server rendering.
  - [x] Add the switch to Landing, signup, welcome, quickstart, pricing, and legal shell pages.
  - [x] Keep styling compact and consistent with existing headers/forms.

- [x] Task 3: Move key-page copy to messages (AC: 4, 5, 6)
  - [x] Add `zh-CN` and `en-US` message files.
  - [x] Migrate Landing, signup, welcome, quickstart, pricing, legal shells, and not-found visible copy touched by the story to message keys.
  - [x] Add minimal `/pricing`, `/legal/tos`, `/legal/privacy`, and `/legal/eula` route shells if missing, with explicit non-final/legal-review-pending copy.
  - [x] Localize SignupWizard step labels via the web onboarding helper rather than changing step ids.
  - [x] If required for en-US key pages, add optional SignupWizard state-label props in `packages/ui/src/components/SignupWizard/index.tsx` with tests proving default zh-CN remains unchanged.
  - [x] Preserve current zh-CN text where tests depend on it.

- [x] Task 4: Localize API language header (AC: 3)
  - [x] Replace hardcoded API `Accept-Language` with resolved locale helper.
  - [x] Preserve caller header override order.
  - [x] Add unit tests for default, saved preference, invalid preference, and override behavior.

- [x] Task 5: Regression tests and E2E checks (AC: 6, 7)
  - [x] Add locale helper tests.
  - [x] Add/update signup API-client tests for language header.
  - [x] Add/update `packages/ui` tests if SignupWizard receives optional localized state labels.
  - [x] Run web unit tests and typecheck.
  - [x] Run package UI tests/typecheck if package UI is modified.
  - [x] Run J1 Playwright smoke after implementation.
  - [x] Run the focused language-switch Playwright check.

- [x] Task 6: Story tracking and review completion (AC: 7)
  - [x] Keep Dev Agent Record updated with commands and file list.
  - [x] Move story to code-review only after implementation and tests.
  - [x] Move sprint status to done only after code review passes.

## Dev Notes

- Prefer `next-intl` because PRD and Architecture explicitly name it. Do not hand-roll a parallel translation framework unless `next-intl` cannot be installed.
- Use a stable cookie name such as `opticloud-locale`. Valid values only: `zh-CN`, `en-US`.
- Implement locale normalization once and reuse it from request config, middleware, the language switcher, and API header logic. Avoid duplicating ad hoc parsing in page components.
- Route stability is important. Use non-locale-prefixed routing or middleware that does not redirect existing paths to prefixed paths.
- If using `next-intl` navigation helpers, keep exported `Link` behavior compatible with current unprefixed URLs.
- Keep `zh-CN` default deterministic for tests. Browser `navigator.language` should not make CI unexpectedly switch to English.
- Use `Intl.DateTimeFormat` / `Intl.NumberFormat` through helper functions where touched; do not globally rewrite unrelated date/currency formatting in this story.
- For server components, load locale from cookie/request headers. For client fetch calls, read the cookie directly and fall back to `zh-CN`.
- Existing `request<T>()` in `apps/web/src/lib/api.ts` merges default headers before `init.headers`. Preserve this so explicit test/caller headers can override defaults.
- Be careful with `Headers` instances in `init.headers`; tests should cover plain objects and caller override at minimum. If using `new Headers(init.headers)`, preserve all existing headers.
- `apps/web/src/lib/postman.ts` may continue to default Postman collections to `zh-CN` unless this story touches it; UX spec explicitly calls Postman M1 default zh-CN.
- `packages/ui` components currently contain Chinese internal state text such as SignupWizard state labels. It is acceptable to make these configurable props only if needed for key-page English fallback; avoid broad package-level i18n rewrites.
- If `packages/ui` is changed, update `packages/ui/src/components/SignupWizard/index.test.tsx` or add focused tests. Do not regress existing `SignupWizard` default text because current Storybook and J1 tests assume zh-CN defaults.
- Avoid using "亲", "哦", or casual emoji-heavy phrasing in zh-CN messages.

### Project Structure Notes

- Web config: `apps/web/next.config.mjs`
- Root layout: `apps/web/src/app/layout.tsx`
- Key pages: `apps/web/src/app/page.tsx`, `apps/web/src/app/auth/signup/page.tsx`, `apps/web/src/app/welcome/page.tsx`, `apps/web/src/app/docs/quickstart/page.tsx`, `apps/web/src/app/pricing/page.tsx`, `apps/web/src/app/legal/tos/page.tsx`, `apps/web/src/app/legal/privacy/page.tsx`, `apps/web/src/app/legal/eula/page.tsx`, `apps/web/src/app/not-found.tsx`
- API client: `apps/web/src/lib/api.ts`
- Onboarding helper: `apps/web/src/lib/onboarding.ts`
- Existing web tests: `apps/web/src/lib/signup.test.ts`, `apps/web/src/lib/onboarding.test.ts`
- UI package if touched: `packages/ui/src/components/SignupWizard/index.tsx`, `packages/ui/src/components/SignupWizard/index.test.tsx`
- J1 smoke: `e2e/tests/j1-happy-path.spec.ts`
- Language switch E2E: add a focused spec such as `e2e/tests/language-switch.spec.ts`

### Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Locale-prefixed routing breaks existing links and E2E | Keep current paths stable; do not require `/zh-CN` or `/en-US` prefixes |
| Full en-US translation scope explodes | Limit en-US to key pages; document mixed deep pages as acceptable v1 fallback |
| Legal page route shells are mistaken for final legal deliverables | Include explicit legal-review-pending copy and keep final legal authoring out of scope |
| Server/client locale mismatch causes hydration warnings | Use the same cookie-backed locale for layout, switcher, and API client |
| Middleware captures static assets or causes page redirects | Use a narrow matcher/exclusions and never redirect unprefixed page routes |
| API tests become environment-dependent | Default to `zh-CN` unless explicit valid cookie/header exists |
| Existing Chinese selectors fail | Preserve zh-CN message text for J1-critical strings |
| Signup pending guardian state advances onboarding | Keep Story 1.9 branch logic unchanged; only replace display strings |
| next-intl message lookup throws on missing key | Provide zh-CN fallback messages for en-US gaps |
| Package UI i18n change breaks existing consumers | Add optional props with zh-CN defaults and run package UI tests/typecheck |

### References

- FR A3 summary: `_bmad-output/planning/epics.md:44`
- Story 1.10 AC: `_bmad-output/planning/epics.md:1335-1337`
- PRD i18n framework: `_bmad-output/planning/prd.md:1257`
- PRD Localization & i18n v1 scope: `_bmad-output/planning/prd.md:1777-1786`
- Architecture stack: `_bmad-output/planning/architecture.md:335`, `_bmad-output/planning/architecture.md:1637`
- Architecture Accept-Language contract: `_bmad-output/planning/architecture.md:678`
- UX key en-US page clarification: `_bmad-output/planning/ux-design-specification.md:119`
- UX user preference override: `_bmad-output/planning/ux-design-specification.md:132`
- UX zh-CN voice constraint: `_bmad-output/planning/ux-design-specification.md:3156`
- Previous story note: `_bmad-output/stories/1-9-under-14-block.md`
- Current API hardcoded language header: `apps/web/src/lib/api.ts`
- Current root hardcoded html lang: `apps/web/src/app/layout.tsx`

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- `pnpm add next-intl@^4.12.0 --filter @opticloud/web` — dependency added; existing Storybook peer warning only.
- `pnpm install` — workspace node_modules links restored for this worktree.
- `pnpm --filter @opticloud/web test -- locales signup onboarding` — 18 passed.
- `pnpm --filter @opticloud/ui test -- SignupWizard` — 5 passed.
- `pnpm --filter @opticloud/ui typecheck` — passed.
- `pnpm --filter @opticloud/web typecheck` — passed.
- `pnpm --filter @opticloud/web test` — 62 passed.
- `pnpm --filter @opticloud/ui test` — 50 passed.
- `$env:PLAYWRIGHT_PYTHON='D:\优化预测网站\.venv\Scripts\python.exe'; pnpm --dir e2e exec playwright test tests/language-switch.spec.ts --project=chromium` — 1 passed.
- `$env:PLAYWRIGHT_PYTHON='D:\优化预测网站\.venv\Scripts\python.exe'; pnpm --dir e2e exec playwright test tests/j1-happy-path.spec.ts --project=chromium` — 1 passed.
- `git diff --check` — passed.
- `pnpm --filter @opticloud/web typecheck` — initially failed before `pnpm install` because the new worktree did not have root/package UI node_modules links.
- `pnpm --dir e2e exec playwright test ...` — initially failed before setting `PLAYWRIGHT_PYTHON` because this worktree has no `.venv`; rerun used the existing main workspace venv path.
- Parallel Playwright run of both specs failed due port contention; rerun sequentially passed.

### Completion Notes List

- Added `next-intl` App Router integration without locale-prefixed URLs. Locale is resolved from explicit request locale, `opticloud-locale` cookie, `Accept-Language`, then zh-CN fallback.
- Added shared locale helpers for normalization, cookie parsing/building, and client-side API locale resolution.
- Added `LanguageSwitcher` and wired it into Landing, signup, welcome, quickstart, pricing, and legal shell pages.
- Added zh-CN and en-US messages for key v1 pages: Landing, Signup/onboarding, Welcome, Quickstart, Pricing, Legal Terms/Privacy/EULA shells, and Not Found.
- Updated API client to send normalized `Accept-Language` from the saved locale while preserving caller header overrides.
- Added optional localized state/control labels to `SignupWizard` with zh-CN defaults, preserving existing consumers.
- Kept full J1 smoke in zh-CN by explicitly setting the locale cookie, and added a focused English language-switch E2E.

### File List

- `_bmad-output/stories/1-10-language-switch-zh.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/next.config.mjs`
- `apps/web/package.json`
- `apps/web/src/app/auth/signup/page.tsx`
- `apps/web/src/app/docs/quickstart/page.tsx`
- `apps/web/src/app/layout.tsx`
- `apps/web/src/app/legal/eula/page.tsx`
- `apps/web/src/app/legal/privacy/page.tsx`
- `apps/web/src/app/legal/tos/page.tsx`
- `apps/web/src/app/not-found.tsx`
- `apps/web/src/app/page.tsx`
- `apps/web/src/app/pricing/page.tsx`
- `apps/web/src/app/welcome/page.tsx`
- `apps/web/src/components/LanguageSwitcher.tsx`
- `apps/web/src/components/LegalShell.tsx`
- `apps/web/src/i18n/locales.test.ts`
- `apps/web/src/i18n/locales.ts`
- `apps/web/src/i18n/messages/en-US.json`
- `apps/web/src/i18n/messages/zh-CN.json`
- `apps/web/src/i18n/request.ts`
- `apps/web/src/i18n/routing.ts`
- `apps/web/src/lib/account-deletion.test.ts`
- `apps/web/src/lib/account-merge.test.ts`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/onboarding.ts`
- `apps/web/src/lib/signup.test.ts`
- `e2e/tests/j1-happy-path.spec.ts`
- `e2e/tests/language-switch.spec.ts`
- `packages/ui/src/components/SignupWizard/index.test.tsx`
- `packages/ui/src/components/SignupWizard/index.tsx`
- `pnpm-lock.yaml`

### Change Log

- 2026-05-23 — Created Story 1.10 and completed three story review rounds.
- 2026-05-23 — Implemented web i18n foundation, locale switch, key-page zh/en messages, API `Accept-Language`, SignupWizard label overrides, and tests.

## Story Review Log

### Round 1 — Product Scope / Key-Page Fallback Review

- [x] Tightened en-US fallback scope to match PRD/UX key pages instead of only the currently implemented pages.
- [x] Added `/pricing` and legal route shell expectations because existing UI already links to those paths.
- [x] Clarified that legal route shells are bilingual placeholders only and do not replace blocked legal review/signoff work.

### Round 2 — Architecture / i18n Contract Review

- [x] Added a concrete locale cookie contract and normalization requirement so server rendering, client switcher, and API fetches agree.
- [x] Added middleware matcher guardrails to prevent static assets or existing routes from being redirected/broken.
- [x] Clarified `Accept-Language` must send a single supported locale and preserve caller header overrides.

### Round 3 — Implementation Readiness Review

- [x] Added explicit guidance for optional `SignupWizard` localized status labels without breaking existing package consumers.
- [x] Added focused English language-switch Playwright coverage while keeping full J1 smoke in default zh-CN.
- [x] Added `packages/ui` test/typecheck requirements if implementation touches shared UI.
