# Story EVO.5: Console Data Pages and User Guide Closure

Status: done
Date: 2026-06-21
Branch: `codex/ux-console-shell-data-pages`
Pull Request: https://github.com/proecheng/opticloud/pull/185
Merge Commit: `4962d8e4cf08c1850ebb38797ca7c114b9d74a08`

## Story

As a technical evaluator or console operator,
I want data-heavy console pages to share a coherent console shell and the public docs to include a practical website operation guide,
so that I can navigate public documentation, task workflows, billing, audit, provider, routing, and support surfaces without each page feeling like a separate prototype.

## Scope

- Extend the console shell pattern from the Excel workflow to data-heavy console pages.
- Normalize navigation, headers, and responsive layout across:
  - `/console/providers`
  - `/console/predictions`
  - `/console/repro`
  - `/console/data-exports`
  - `/console/classroom`
  - `/console/routing-history`
  - `/console/legal-inquiry`
  - `/console/billing/invoices`
  - `/console/audit-logs`
- Add a public HTML operation manual at `/docs/user-guide`.
- Link the guide from `/docs`.
- Extend mobile overflow regression coverage for the user guide and console data pages.
- Preserve existing route behavior, test selectors, and no-auth/auth-session assumptions from prior stories.

## Out of Scope

- New backend APIs or data model changes.
- Rewriting solver, billing, provider, classroom, audit, or export business logic.
- Closing the four external Epic 0 process/legal/AIGC blocked items.
- Claiming full production readiness for routes that still document v1 stubs or manual processes.
- Committing local visual screenshot output that was generated as scratch evidence.

## Acceptance Criteria

1. Data-heavy console pages render in the shared `ConsoleShell` with active navigation and mobile-bounded layout.
2. Public docs expose `/docs/user-guide` from the docs index.
3. `/docs/user-guide` gives practical operating paths for signup/API key, quickstart, Excel workflow, algorithm catalog, console entries, and troubleshooting.
4. Existing console page unit tests pass after shell normalization.
5. Docs unit tests assert the user guide entry and route.
6. Mobile overflow regression coverage includes the user guide and console data pages.
7. At `390x844`, the covered public and console routes do not introduce document-level horizontal overflow.
8. PR #185 is merged to `main`, remote branch is deleted, and local `main` is synced.

## Implementation Summary

PR #185 was merged on 2026-06-21 as squash commit `4962d8e`.

Primary changes:

- Refactored data-heavy console pages into the shared console shell.
- Added `/docs/user-guide` as a public operation manual.
- Updated `/docs` to surface the operation guide in the starting path.
- Extended `e2e/tests/public-mobile-overflow.spec.ts` for the new user guide and console coverage.
- Removed untracked scratch screenshots from `_bmad-output/evolution/ui-redesign-2026-06-08/` rather than committing them as evidence.

## Verification Evidence

- `pnpm --dir apps/web exec vitest run src/app/docs/page.test.tsx src/app/docs/user-guide/page.test.tsx`: passed.
- `pnpm --dir apps/web typecheck`: passed.
- `pnpm --dir e2e exec playwright test tests/public-mobile-overflow.spec.ts --project=chromium --workers=1`: 15 passed.
- `git diff --check`: passed before commit.
- GitHub PR #185: merged.

Note: an initial parallel local Playwright run hit Next dev-server first-compile navigation timeouts. A single-worker rerun passed all overflow assertions and is the validation record for this closure.

## Remaining Work

No actionable UX evolution story remains open in the current BMAD ledger after PR #185.

The only remaining non-done concrete stories are external Epic 0 process/legal/AIGC blockers:

- `0-0-sprint0-calibration-week`
- `m0-legal-1-license-deliverable`
- `m0-legal-status-tracking`
- `m0-aigc-status-tracking`

## Change Log

- 2026-06-21 - Added closure story for PR #185 and synchronized the Evolution UX ledger.
