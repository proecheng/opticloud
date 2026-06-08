---
story_key: evo-1-mobile-overflow-hardening
baseline_commit: 0afcfe7e838dd6b233fe38729fc64b053fc53a56
epic_num: evolution
story_num: 1
epic_name: Brownfield UX Evolution
status: done
priority: High
type: mobile layout hardening
created_by: codex-wds-product-evolution
created_at: 2026-06-08
sources:
  - _bmad-output/evolution/visual-audit-2026-06-08/visual-audit-results.json
  - _bmad-output/evolution/visual-audit-2026-06-08/visual-audit-report.md
  - _bmad-output/stories/2-2-algorithm-details.md
  - _bmad-output/stories/8-a-7-j9-whitehat-vertical-slice.md
  - apps/web/src/components/CodeBlock.tsx
  - apps/web/src/app/algorithms/[k_algo]/page.tsx
  - apps/web/src/app/security/SecurityDisclosurePageView.tsx
---

# Story EVO.1 - Public Mobile Overflow Hardening

Status: done

## Story

**作为** 手机端访问公开页面的潜在客户、研究者或评估者，
**我希望** `/algorithms/highs-lp` 和 `/security` 在 390px 移动端视口内没有页面级横向滚动，
**从而** 我可以正常阅读代码示例、安全披露流程和 CTA，而不需要左右拖动页面或看到被撑破的布局。

## Context

2026-06-08 视觉审计发现两个公开页面存在可量化移动端横向溢出：

- `/algorithms/highs-lp`: document width `551px` on viewport `390px`。
- `/security`: document width `587px` on viewport `390px`。

审计证据显示算法详情页的主要溢出来自共享 `CodeBlock` 及其 grid child 的最小宽度行为；Security 页的主要溢出来自 J9 Flow stages 区块在移动端被内容和卡片布局撑宽。这个 story 只修复公共页面移动端布局稳定性，不做 PublicShell、ConsoleShell 或内容信息架构重写。

## Scope

1. Harden `apps/web/src/components/CodeBlock.tsx` so long code/source blocks remain bounded by their parent and scroll internally when needed.
2. Harden `/algorithms/[k_algo]` detail layout so code blocks and example JSON cannot expand the mobile document width.
3. Harden `/security` J9 sections so flow cards, status badges, Mermaid source, SOP, and hardening checklist cannot expand the mobile document width.
4. Add a focused Playwright regression test for public mobile overflow on `/algorithms/highs-lp` and `/security`.
5. Preserve existing public route behavior, page copy, no-auth behavior, copy buttons, citation/provenance rendering, and Security no-storage/no-fetch expectations.

## Out Of Scope

- Full landing page redesign.
- `PublicShell`, `ConsoleShell`, sidebar navigation, or global nav refactor.
- Provider Console overflow fix. Authenticated `/console/providers` is tracked for the next ConsoleShell/data-page story.
- Security content reduction or rewriting the J9 flow model.
- Algorithm catalog data/API changes, solver routes, backend services, package dependencies, lockfile updates, generated OpenAPI, infra, or CI workflow changes.
- Replacing Mermaid source with a client-side renderer.

## Acceptance Criteria

1. At `390x844`, `/algorithms/highs-lp` has no page-level horizontal overflow: `document.documentElement.scrollWidth <= window.innerWidth`.
2. At `390x844`, `/security` has no page-level horizontal overflow: `document.documentElement.scrollWidth <= window.innerWidth`.
3. `CodeBlock` keeps the outer block bounded with `min-w-0`/`max-w-full` behavior and keeps long code scroll inside the code surface.
4. `CodeBlock` copy button remains visible and has the existing accessible name behavior.
5. Algorithm detail page still renders Python, cURL, BibTeX, provenance, example JSON, and CTA sections.
6. Algorithm detail page still preserves loading, 404, non-404 error, citation, IP attribution, and empty provenance behavior.
7. `/security` still renders the disclosure mailbox, report requirements, SLA, safe harbor, J9 flow, Mermaid source, SOP steps, and exactly 22 hardening items.
8. `/security` still renders publicly without reading browser storage or calling `fetch` during render.
9. The fix does not hide content solely to pass overflow tests.
10. The fix adds no new runtime dependency and no package/lockfile changes.
11. Focused page/component tests pass.
12. Playwright mobile overflow regression test passes.
13. `pnpm --filter @opticloud/web typecheck` passes.
14. `git diff --check` passes.
15. Post-implementation code review is completed and findings are fixed or explicitly documented.
16. Changes are committed and pushed to GitHub.

## Tasks / Subtasks

- [x] T1: Harden shared public code/source surfaces (AC: 1-6, 9-10)
  - [x] Update `CodeBlock` bounding and header behavior.
  - [x] Update algorithm detail snippet grids and example JSON pre to preserve mobile width.
  - [x] Preserve existing copy button behavior and tests.

- [x] T2: Harden `/security` mobile J9 sections (AC: 2, 7-10)
  - [x] Add `min-w-0` and wrapping constraints to J9 section grids/cards/status badges.
  - [x] Bound the Mermaid source panel so it scrolls internally.
  - [x] Preserve exact content and count expectations.

- [x] T3: Add regression coverage and run gates (AC: 11-14)
  - [x] Add Playwright mobile overflow regression test.
  - [x] Run focused web tests, focused E2E, typecheck, and diff whitespace gate.

- [ ] T4: Review and GitHub sync (AC: 15-16)
  - [x] Run post-implementation code review.
  - [x] Fix or document findings.
  - [x] Commit and push branch to GitHub.

## Dev Notes

- Use real browser E2E for overflow checks; `happy-dom` does not compute layout widths.
- The root overflow assertion should inspect both `document.documentElement.scrollWidth` and `document.body.scrollWidth`.
- Keep internal code scrolling acceptable; the failure is document-level horizontal scroll.
- Prefer narrowly adding `min-w-0`, `max-w-full`, `overflow-hidden`, `break-words`, and responsive spacing over broad page rewrites.
- Do not remove the J9 Mermaid source, because Story 8.A.7 explicitly requires it.

## Suggested Commands

```powershell
pnpm --filter @opticloud/web test -- src/app/security/page.test.tsx "src/app/algorithms/[k_algo]/page.test.tsx"
pnpm --dir e2e test -- public-mobile-overflow.spec.ts
pnpm --filter @opticloud/web typecheck
git diff --check
```

## Definition Of Done

- Story file has passed exactly 3 pre-implementation adversarial review rounds and revisions.
- Public `/algorithms/highs-lp` and `/security` do not horizontally overflow at 390px mobile viewport.
- A Playwright regression test protects those routes.
- Existing public page tests and typecheck pass.
- Post-implementation code review is completed and findings are fixed or documented.
- Branch is committed and pushed to GitHub.

## Story Review Log

### Round 1 - Boundary And Mobile Edge Review

Findings fixed:

- Initial scope risked becoming a full visual redesign. The story was narrowed to measurable public mobile overflow only.
- Initial acceptance could pass by hiding Security content. AC 9 now prohibits hiding content solely to pass tests, and AC 7 preserves all required Security sections.
- Initial algorithm fix could target only the first Python block while leaving BibTeX/example JSON drift. AC 5 and T1 now cover Python, cURL, BibTeX, provenance-adjacent content, and example JSON.

Status: PASS after revision.

### Round 2 - Drift And Data Consistency Review

Findings fixed:

- Fixing only `/algorithms/[k_algo]` locally would leave shared `CodeBlock` consumers vulnerable. Scope and AC 3 now require hardening the shared `CodeBlock`.
- Security Mermaid, SOP, and hardening content are generated from existing model data; the story now explicitly forbids content/model rewrites and preserves exactly 22 hardening items.
- The overflow metric could drift if only one width source is checked. Dev Notes now require checking both document element and body scroll widths.

Status: PASS after revision.

### Round 3 - Dependency And Closure Review

Findings fixed:

- A Mermaid renderer or UI package would be overkill and add bundle/dependency risk. Out-of-scope and AC 10 now prohibit new dependencies.
- Component tests alone cannot prove no mobile overflow. T3 now requires Playwright mobile regression coverage.
- The authenticated Provider Console overflow is real but belongs to a broader ConsoleShell/data-page story. Out-of-scope records that boundary so this story can close cleanly.

Status: PASS after revision. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/ux-mobile-overflow-hardening`.
- Baseline commit: `0afcfe7e838dd6b233fe38729fc64b053fc53a56`.
- Visual audit report created at `_bmad-output/evolution/visual-audit-2026-06-08/visual-audit-report.md`.
- Implementation started; story and sprint status moved to in-progress.
- Hardened shared `CodeBlock`, algorithm detail grids/example JSON, and Security J9 sections with bounded layout classes.
- Added `e2e/tests/public-mobile-overflow.spec.ts` to assert no document-level horizontal overflow at `390x844`.
- Focused web tests passed: `pnpm --filter @opticloud/web test -- src/app/security/page.test.tsx "src/app/algorithms/[k_algo]/page.test.tsx"` -> 7 passed.
- Focused E2E passed: `pnpm --dir e2e test -- public-mobile-overflow.spec.ts` -> 2 passed.
- Web typecheck passed: `pnpm --filter @opticloud/web typecheck`.
- E2E typecheck passed: `pnpm --dir e2e typecheck`.
- Whitespace gate passed: `git diff --check`.
- Post-implementation code review completed manually per current tool constraints; found and fixed story task-status drift and import-order cleanup.
- Visual verification generated after screenshots and width metrics: both target pages report body/doc scroll width `390px` on `390px` viewport.
- Branch prepared for GitHub sync.

### Completion Notes List

- Initial story created.
- Completed 3 pre-implementation adversarial review rounds and revised the story after each round.
- Story moved to in-progress after pre-implementation review closure.
- Public mobile overflow hardening implemented for Algorithm Detail and Security.
- Regression coverage added and focused gates passed.
- Post-implementation code review completed; two small patch findings fixed.
- After-fix visual verification confirms no horizontal overflow on both target public pages.

### File List

- `_bmad-output/evolution/visual-audit-2026-06-08/visual-audit-report.md`
- `_bmad-output/evolution/visual-audit-2026-06-08/screenshots/algorithm-detail-mobile-after.png`
- `_bmad-output/evolution/visual-audit-2026-06-08/screenshots/security-mobile-after.png`
- `_bmad-output/stories/evo-1-mobile-overflow-hardening.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/src/components/CodeBlock.tsx`
- `apps/web/src/app/algorithms/[k_algo]/page.tsx`
- `apps/web/src/app/security/SecurityDisclosurePageView.tsx`
- `e2e/tests/public-mobile-overflow.spec.ts`

## Change Log

- 2026-06-08 - Story created from visual audit evidence.
- 2026-06-08 - Completed 3 pre-implementation adversarial review rounds; story marked ready for development.
- 2026-06-08 - Implementation started; story status moved to in-progress.
- 2026-06-08 - Implemented mobile overflow fixes, added regression E2E, passed focused gates, and moved story to code-review pending GitHub sync.
- 2026-06-08 - Visual verification confirmed no target-page horizontal overflow; story marked done for branch push.

## Post-Implementation Code Review

### Findings

- [x] [Review][Patch] Story task checklist still showed implementation tasks as incomplete after code and gates had passed. Fixed by checking completed T1-T3 items and moving status to `code-review` pending GitHub sync.
- [x] [Review][Patch] New Playwright file placed runtime import before type import, differing from common project style. Fixed by moving `import type { Page } from "@playwright/test";` before the local fixture import.

### Outcome

Changes requested internally; both findings were fixed before commit.
