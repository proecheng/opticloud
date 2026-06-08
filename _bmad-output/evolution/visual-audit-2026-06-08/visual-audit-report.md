# Visual Audit Report - 2026-06-08

## Executive Summary

The product is functionally broad but visually inconsistent. Public pages and Console pages look like accumulated story outputs rather than one coherent product system. The highest-impact immediate fixes are mobile layout stability and shared shell consistency.

This audit used Playwright screenshots and DOM metrics across desktop `1440x1000` and mobile `390x844`. All audited public routes returned HTTP 200. The measurable P0/P1 layout failures are horizontal overflow on `/algorithms/highs-lp`, `/security`, and authenticated `/console/providers`.

## Evidence

- Public audit data: `_bmad-output/evolution/visual-audit-2026-06-08/visual-audit-results.json`
- Authenticated Console audit data: `_bmad-output/evolution/visual-audit-2026-06-08/visual-audit-console-auth-results.json`
- Key screenshots:
  - `_bmad-output/evolution/visual-audit-2026-06-08/screenshots/landing-desktop.png`
  - `_bmad-output/evolution/visual-audit-2026-06-08/screenshots/algorithm-detail-mobile.png`
  - `_bmad-output/evolution/visual-audit-2026-06-08/screenshots/security-mobile.png`
  - `_bmad-output/evolution/visual-audit-2026-06-08/screenshots/console-providers-mobile-auth.png`
  - `_bmad-output/evolution/visual-audit-2026-06-08/screenshots/console-excel-desktop-auth.png`

## Priority Findings

### P0 - Mobile horizontal overflow

- `/algorithms/highs-lp`: document width `551px` on `390px` viewport.
- `/security`: document width `587px` on `390px` viewport.
- Authenticated `/console/providers`: document width `620px` on `390px` viewport.

The first two are public-page regressions and should be fixed before broader redesign. The third belongs in the next ConsoleShell/data-page story because provider console has a larger information architecture problem.

### P1 - Console lacks a unified work surface

Console pages use different headers, navigation density, empty states, and action placement. Provider Console mobile wraps awkwardly, shows filter controls before useful content, and creates a long stack of low-value cards. Excel Console is cleaner but still feels like a single upload demo, not a task workflow with history, templates, and results.

### P1 - Public pages lack consistent information architecture

Public pages use repeated card stacks, inconsistent page headers, and navigation that changes across routes. The landing page presents a technical demo more than a mature product entry; `/algorithms` reads like an API list; `/security` exposes too much internal implementation detail in a long mobile stack.

### P2 - Internal story language leaks into user-facing UI

Several pages expose terms such as `Story`, `stub`, `FR`, and internal boundary labels. These are useful for engineering traceability but make the product feel unfinished to users.

## Recommended Story Sequence

1. `evo-1-mobile-overflow-hardening`: fix public mobile overflow in Algorithm Detail and Security, add Playwright overflow gate.
2. `evo-2-public-shell-docs-algorithms`: introduce `PublicShell`, normalize public navigation/page headers, and improve `/docs` + `/algorithms` scan structure.
3. `evo-3-console-shell-excel`: introduce `ConsoleShell`, page header/action bar, and improve `/console/excel` into a task workflow.
4. `evo-4-console-data-pages`: refactor Providers/Billing/Audit around dense data panels, filters, and mobile-first summaries.
5. `evo-5-console-workflows`: improve Chat/Classroom/Predictions workflow states.
6. `evo-6-mobile-polish`: final mobile pass for text fit, cards, tables, and navigation consistency.

## Target Layout Components

- `PublicShell`: shared public header/nav/footer, constrained content lanes, active nav state.
- `ConsoleShell`: sidebar or compact top nav, consistent page header, user context, responsive action area.
- `PageHeader`: title, description, primary action, secondary metadata.
- `ActionBar`: filters, search, export, refresh.
- `DataPanel`: table/list/card hybrid with consistent empty/loading/error states.
- `EmptyStatePanel`: action-oriented empty state with one next step.
- `ResponsiveCodeBlock`: shared code/source panel that never expands the document width.

## First Implementation Cycle

Implement `evo-1-mobile-overflow-hardening`.

Acceptance target:

- At `390x844`, `document.documentElement.scrollWidth <= window.innerWidth` for `/algorithms/highs-lp`.
- At `390x844`, `document.documentElement.scrollWidth <= window.innerWidth` for `/security`.
- Preserve existing content, routes, public no-auth behavior, copy buttons, and tests.
- Add an E2E regression test so future page work cannot reintroduce public mobile horizontal overflow.

## First Cycle Result

Implemented in branch `codex/ux-mobile-overflow-hardening`.

- `/algorithms/highs-lp` after fix: body/doc scroll width `390px` on `390px` viewport, no horizontal overflow.
- `/security` after fix: body/doc scroll width `390px` on `390px` viewport, no horizontal overflow.
- After screenshots:
  - `_bmad-output/evolution/visual-audit-2026-06-08/screenshots/algorithm-detail-mobile-after.png`
  - `_bmad-output/evolution/visual-audit-2026-06-08/screenshots/security-mobile-after.png`
- Regression test added: `e2e/tests/public-mobile-overflow.spec.ts`.
