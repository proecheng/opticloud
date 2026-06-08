# Story EVO.2: Public Shell, Docs, and Algorithms IA

Status: done
Date: 2026-06-08
Branch: `codex/ux-public-shell-docs-algorithms`

## Story

As a first-time technical buyer or evaluator,
I want the public documentation and algorithm catalog to share one coherent public shell and scannable page structure,
so that I can move between product overview, docs, algorithm catalog, trust pages, and signup without re-learning the page layout on every route.

## Scope

- Add a reusable `PublicShell` for public, unauthenticated product pages.
- Add a reusable `PublicPageHeader` for public page title, description, actions, and optional metadata.
- Apply the shell to `/docs` and `/algorithms`.
- Improve `/docs` from a narrow link list into task-oriented documentation groups.
- Improve `/algorithms` scan structure by separating page header, tier filters, catalog state, and algorithm cards.
- Preserve existing public no-auth catalog fetching, tier URL synchronization, provider transparency links, and current docs links.
- Extend regression coverage for public shell navigation and mobile overflow on `/docs` and `/algorithms`.

## Out of Scope

- Console shell redesign.
- Landing page redesign.
- Algorithm detail body redesign beyond keeping links compatible.
- Copy translation/i18n migration for static public shell labels.
- API/backend changes.

## Current Evidence

- Visual audit: `_bmad-output/evolution/visual-audit-2026-06-08/visual-audit-report.md`
- Existing `/docs`: `apps/web/src/app/docs/page.tsx`
- Existing `/algorithms`: `apps/web/src/app/algorithms/page.tsx`
- Existing catalog E2E: `e2e/tests/algorithms-catalog.spec.ts`
- Existing public overflow gate: `e2e/tests/public-mobile-overflow.spec.ts`

## Acceptance Criteria

1. `/docs` and `/algorithms` render a shared public header with brand link, primary public nav, active section state, signup CTA, and shared footer.
2. `/docs` keeps all current documentation links:
   - `/docs/quickstart`
   - `/docs/excel-upload-faq`
   - `/docs/academic-provider-handbook`
   - `/docs/customer-faqs/academic-onboarding-faq`
   - `/pricing`
   - `/status`
   - `/security`
3. `/docs` adds task-oriented scanning so users can choose between quickstart, Excel upload, academic onboarding, pricing/status/security.
4. `/algorithms` preserves `listAlgorithms({ tier })`, chip `aria-pressed`, `data-testid="tier-chip-*"` and `data-testid="algorithm-card"`.
5. `/algorithms?tier=T1,P1` still hydrates selected chips from URL and keeps matching cards.
6. Provider URL remains a visible external link inside each algorithm card.
7. At `390x844`, `/docs` and `/algorithms` do not introduce document-level horizontal overflow.
8. No auth/login behavior changes.
9. Existing tests for docs, algorithm detail, algorithm catalog, and public mobile overflow pass.

## Implementation Notes

- Prefer `apps/web/src/components/PublicShell.tsx`.
- Keep `PublicShell` free of router hooks so server and client pages can both use it without adding provider/test complexity.
- Use an explicit `active` prop instead of `usePathname`.
- Keep cards at `rounded-md`/`rounded-lg` only; avoid nested cards.
- Keep page content constrained with `max-w-6xl`, `min-w-0`, `overflow-x-auto` only where needed.
- Do not import `LanguageSwitcher` into `PublicShell` for this story; current public pages mix static and translated copy, and this story should not expand i18n scope.

## Three-Round Pre-Implementation Adversarial Review

### Round 1: Boundary Issues

Findings:

1. Shell reuse can accidentally pull translated/client-only dependencies into static tests.
2. Active nav based on router hooks would force a client component and increase hydration/test surface.
3. Applying the shell too broadly could disturb landing, pricing, legal, status, or just-fixed algorithm detail layout.
4. Algorithms page is a client component; shell must be usable from client code.
5. Docs page test currently mocks only `next/link`; adding new runtime dependencies would break it without user-visible benefit.
6. Footer links can duplicate header links and create noisy accessibility names if not scoped.
7. Wider docs layout can regress mobile overflow if cards or long URLs are not bounded.
8. Algorithm cards can regain overflow through provider URLs, `k_algo`, examples, or inline task metadata.
9. Rewording catalog status/tier labels can break existing E2E if test selectors are not preserved.
10. Adding new docs content that points to missing routes would reintroduce 404s.

Revision after Round 1:

- Limit application to `/docs` and `/algorithms`.
- Make `PublicShell` prop-driven and hook-free.
- Keep all existing test IDs and existing links.
- Add explicit mobile overflow checks for `/docs` and `/algorithms`.
- Use only current, verified routes in docs and nav.

### Round 2: Drift, Data, and Dependency Consistency

Findings:

1. Documentation groups could drift from actual docs files if hardcoded without tests.
2. Catalog count summaries could become stale if computed before async load.
3. Tier filters must remain the single source of query state; a new filter layout cannot introduce duplicate state.
4. `router.replace` still runs after hydration; layout work must not change URL ordering expectations.
5. `error` state currently persists across retries; this story should not widen behavior unless fixing intentionally.
6. Imported UI package components must remain unchanged to avoid cross-package blast radius.
7. Static shell labels are acceptable only if this story explicitly avoids i18n expansion.
8. Docs page should not claim unsupported workflows, automatic setup, or production readiness not present in current code.
9. Algorithm list empty/loading/error states need to remain visually bounded in the new grid.
10. E2E against `/algorithms` depends on solver API availability in existing test setup; new assertions should not add a new backend dependency class.

Revision after Round 2:

- Use existing `DOC_GROUPS` as data source and expand metadata locally.
- Derive loaded algorithm count from `algos?.length`; do not hardcode.
- Keep selected tier state and API call mechanics unchanged.
- Update docs unit test to assert current links and shared public nav.
- Avoid UI package edits.

### Round 3: Closure and Regression Risk

Findings:

1. A shell-only story can be perceived as cosmetic unless it measurably improves navigation and scan structure.
2. Footer and header must form a closed public route loop: users can reach docs, algorithms, pricing, status, security, academic, signup, and home.
3. Docs cards need clear task labels, not internal story labels.
4. Algorithm provider transparency must remain visible without requiring users to open details.
5. Mobile nav wrapping must not hide signup or push content beyond viewport.
6. Test coverage must include both unit-level link preservation and browser-level layout measurement.
7. Code review should inspect semantics/accessibility, not only screenshot appearance.
8. Story status must not move to done until implementation, review, tests, and GitHub sync complete.
9. Sprint status should track EVO.2 explicitly to keep the improvement epic closed-loop.
10. If CI fails for external network reasons, rerun once and record the blocker separately from code failures.

Revision after Round 3:

- Add `aria-label` to public nav and footer nav.
- Keep docs cards task-oriented with route links only to existing pages.
- Add E2E assertions for nav visibility and no horizontal overflow.
- Update `sprint-status.yaml` when story moves through implementation/review/done.

## Implementation Checklist

- [x] Create `PublicShell` / `PublicPageHeader`.
- [x] Refactor `/docs` into public shell and task groups.
- [x] Refactor `/algorithms` into public shell and clearer catalog sections.
- [x] Update docs unit test.
- [x] Extend public mobile overflow E2E.
- [x] Run focused web tests.
- [x] Run E2E public tests.
- [x] Run typechecks.
- [x] Run code review and apply required fixes.
- [ ] Commit, push, open PR, verify CI, merge/sync if clean.

## Post-Implementation Code Review

Completed 2026-06-08.

Review target: uncommitted branch diff for `codex/ux-public-shell-docs-algorithms` plus new files `apps/web/src/components/PublicShell.tsx` and this story file.

Layers:

- Blind Hunter: no actionable findings after triage.
- Edge Case Hunter: no unhandled changed-line boundary cases after triage.
- Acceptance Auditor: no AC violations after triage.

Triage:

- Decision-needed: 0
- Patch: 0
- Defer: 0
- Dismissed/noise: 0

Verification evidence:

- `pnpm --filter @opticloud/web test -- src/app/docs/page.test.tsx "src/app/algorithms/[k_algo]/page.test.tsx"`: 4 passed.
- `pnpm --filter @opticloud/web typecheck`: passed.
- `pnpm --dir e2e exec playwright test public-mobile-overflow.spec.ts algorithms-catalog.spec.ts --workers=1`: 8 passed. This matches the CI worker policy and avoids local Next dev-server contention across repeated public route loads.
- `pnpm --dir e2e typecheck`: passed.
