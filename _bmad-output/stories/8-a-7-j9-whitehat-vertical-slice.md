---
story_key: 8-a-7-j9-whitehat-vertical-slice
baseline_commit: a6ab8741dd92f7b31bdd4d59afa40a5ce5d0846e
epic_num: 8
story_num: A.7
epic_name: Public Status + Audit + Vuln Response
status: done
priority: High
type: J9 whitehat responsible disclosure vertical slice
created_by: bmad-create-story
created_at: 2026-06-03
sources:
  - _bmad-output/planning/epics.md (Epic 8.A / Story 8.A.7)
  - _bmad-output/planning/prd.md (Journey 9; FR O4)
  - _bmad-output/planning/ux-design-specification.md (UX-DR7 J9 Mermaid flow)
  - _bmad-output/planning/architecture.md (J9 -> O4; cross-cut concerns 4 and 10)
  - _bmad-output/stories/8-a-6-vuln-submission.md
  - apps/web/src/lib/security-disclosure.ts
  - apps/web/src/app/security/SecurityDisclosurePageView.tsx
---

# Story 8.A.7 - J9 白帽 Vertical Slice Mermaid Flow

Status: done

## Story

**作为** 安全研究者、内部安全负责人和客户 SRE，
**我希望** 公开 `/security` 页面不仅给出 disclosure mailbox，还能展示 J9 白帽负责任披露端到端路径、Mermaid flow、SOP 步骤和 22 项 hardening checklist，
**从而** 研究者可以理解从 `security.txt` 到回执、分级、修复、致谢/奖励的闭环，同时团队可以用静态合同验证 v1 J9 路径不会漂移或过度宣称未上线自动化。

## Context

Story 8.A.6 已交付 `/.well-known/security.txt`、`/security`、共享 `SecurityDisclosurePolicy`、48h acknowledgement、CVSS >= 7 7d remediation target、safe-harbor boundary、以及“不声称 SMTP/ticket/CVE/bounty/PGP 已上线”的硬边界。本 story 是 Epic 8.A 的收尾 story，承接 UX-DR7 J9 白帽 Mermaid Flow，补齐“端到端路径可读、SOP 可跑通、22 hardenings 可验证”的静态 vertical slice。

UX J9 原始图包含 security.txt、security@、5 披露通道、48h 自动 ticket、email 收到/失败、PGP fallback、漏洞分级、24h/7d patch、公开致谢、重复披露裁定、奖励 ¥500-2000。当前代码库仍没有真实邮箱 intake、ticket system、PGP key、reward payment、CVE automation 或法律条款上线。因此本 story 必须把“vertical slice”定义为 deterministic public model + Mermaid + SOP dry-run contract + page/tests，而不是伪造生产自动化。

## Scope

1. 扩展 `apps/web/src/lib/security-disclosure.ts`，为 J9 增加 typed flow、SOP steps、hardening checklist 和 deterministic Mermaid builder。
2. J9 flow 必须覆盖 UX-DR7 主路径和分支：
   - researcher discovers `/api/v1/*`
   - reads `security.txt`
   - contacts `security@opticloud.cn`
   - disclosure type branch: responsible security, ordinary bug report, academic/student, national/APT, future HackerOne-like platform
   - responsible disclosure sends email + PoC + CVSS
   - 48h acknowledgement/ticket contract
   - email receipt failure fallback (PGP/key + internal alert) as planned/not-active boundary
   - triage and CVSS branches
   - CVSS >= 7 hotfix path and CVSS 4-6.9 7d path
   - public acknowledgement/reward duplicate disclosure branch as planned/manual boundary
3. Add exactly 22 hardening items with stable IDs, owners, stage, status, and public-safe descriptions.
4. Extend `/security` page to render J9 flow, Mermaid source, SOP steps, and 22 hardenings without auth, storage, fetch, or new dependencies.
5. Add tests for flow order, Mermaid sanitization, exact hardening count/IDs, no unsupported active-automation claims, page render, and status/security discoverability.
6. Add a runbook under `docs/runbooks/` for J9 whitehat SOP dry-run, matching the same model stages and explicitly listing non-active automation boundaries.

## Out Of Scope

- Real SMTP/IMAP/email webhook intake, ticket creation, Telegram/DingTalk/PagerDuty bot, provider delivery, or automatic 48h acknowledgement dispatch.
- PGP key publication or encrypted intake until a real public key URL exists.
- Reward payout, anti-fraud/legal bounty agreement, tax/invoice handling, or production public thanks page database.
- CVE assignment, CNA workflow, CVE API integration, vulnerability scanner, dependency scanner, or live patch deployment automation.
- Backend database tables, admin triage UI, OpenAPI routes, migrations, queues, cron jobs, or external services.
- National/APT legal escalation execution; this story only documents and gates the branch.
- Any claim that planned/manual future items are active production automation.

## Acceptance Criteria

1. J9 flow is represented in a typed model under `apps/web/src/lib/security-disclosure.ts`.
2. Flow node IDs are stable and include discovery, `security.txt`, `security@opticloud.cn`, disclosure type, responsible disclosure, bug report, academic channel, national/APT escalation, future platform, acknowledgement, email received decision, fallback, triage, CVSS >= 7 patch, CVSS 4-6.9 patch, public acknowledgement, duplicate decision, reward, duplicate thanks.
3. Flow edges are generated from the typed model and preserve the UX-DR7 branch semantics.
4. Mermaid source is generated deterministically from the typed flow, not hand-authored in the page.
5. Mermaid labels are sanitized so quotes, brackets, braces, pipes, angle brackets, or newlines cannot break the source.
6. J9 SOP steps are represented as a typed ordered list and cover discovery, intake, acknowledgement, triage, remediation, disclosure coordination, acknowledgement/reward, and retrospective evidence.
7. The model includes exactly 22 hardening items.
8. Every hardening item has stable `id`, `owner`, `stage`, `status`, `title`, and `description`.
9. Hardening IDs are unique and ordered.
10. Hardening status vocabulary distinguishes `active`, `manual`, `planned`, and `blocked`.
11. Hardening items cover at least discovery, report completeness, safe-harbor, privacy, duplicate handling, severity/CVSS, SLA tracking, patch evidence, PGP fallback, national/APT escalation, reward anti-fraud, public acknowledgement, CVE coordination, and automation-overclaim guardrails.
12. `/security` displays the J9 flow section with the Mermaid source in a `<pre><code>` block.
13. `/security` displays the SOP steps in order.
14. `/security` displays all 22 hardening items.
15. `/security` still renders publicly without reading browser storage, cookies, JWT, API keys, account state, or calling `fetch`.
16. `/security` does not claim SMTP auto-reply, ticket automation, Telegram/DingTalk bot, PGP encrypted intake, CVE tracking, bounty payment, or HackerOne-like platform integration is active.
17. `/security` distinguishes ordinary product bug reports, academic/student disclosure, and national/APT escalation from responsible security disclosure.
18. `/.well-known/security.txt` remains unchanged except for policy page content; no unsupported `Encryption:` field is added.
19. Runbook `docs/runbooks/j9-whitehat-disclosure.md` documents the same stages, dry-run evidence expectations, redaction rules, and inactive automation boundaries.
20. No new runtime dependency or environment variable is added.
21. Focused tests cover model, Mermaid, hardening count/IDs, `/security` page render, and security.txt non-regression.
22. Local gates pass: focused web tests, `pnpm --filter @opticloud/web test`, `pnpm --filter @opticloud/web typecheck`, `pnpm -C apps/web build`, and `git diff --check`.
23. Implementation record includes post-implementation code review findings and fixes.
24. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done`.

## Tasks / Subtasks

- [x] T1: Extend J9 typed model and Mermaid builder (AC: 1-11, 16, 18, 20-21)
  - [x] Add J9 flow node/edge, SOP step, and hardening item types.
  - [x] Add deterministic model data and Mermaid builder.
  - [x] Add model tests for flow nodes/edges, Mermaid sanitization, exact 22 hardenings, unique ordered IDs, and status vocabulary.

- [x] T2: Extend `/security` public page (AC: 12-18, 21)
  - [x] Render J9 overview, Mermaid source, SOP ordered steps, and 22 hardening checklist.
  - [x] Preserve public/no-auth/no-storage/no-fetch behavior.
  - [x] Add page tests for visible flow, SOP, hardenings, and no overclaim.

- [x] T3: Add J9 runbook (AC: 19)
  - [x] Add `docs/runbooks/j9-whitehat-disclosure.md`.
  - [x] Align runbook stages with the typed model and document evidence/redaction boundaries.
  - [x] Add lightweight test coverage or content assertions through web/model tests when practical.

- [x] T4: Review, gates, and GitHub sync (AC: 20-24)
  - [x] Confirm no dependency or env var change.
  - [x] Run focused tests and local gates.
  - [x] Run post-implementation code review and fix findings.
  - [x] Record review findings and fixes in this story.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [x] Mark story and sprint status `done` only after merge/sync.

## Dev Notes

### Service Boundary

- Prefer extending `apps/web/src/lib/security-disclosure.ts` rather than creating a second J9 fixture.
- Keep `/security` server/static; do not add `"use client"`.
- Keep `security.txt` RFC fields stable; do not add `Encryption` until a real key exists.
- The public page should remain operational/trust-forward, not a marketing hero.

### Implementation Shape

- Suggested model names:
  - `J9_WHITEHAT_FLOW`
  - `buildJ9WhitehatMermaid()`
  - `J9_WHITEHAT_SOP_STEPS`
  - `J9_WHITEHAT_HARDENINGS`
- Suggested route/page change:
  - Extend `SecurityDisclosurePageView` with sections after existing disclosure/safe harbor content.
- Suggested runbook:
  - `docs/runbooks/j9-whitehat-disclosure.md`

### Boundary Language

- Use words like `planned`, `manual`, `handoff`, and `dry-run contract` for non-active automation.
- Avoid phrases that imply active production automation: "auto-reply is active", "ticket automation is active", "CVE tracking is active", "bounty payment is active", "PGP encrypted intake is active".

### Suggested Commands

```powershell
pnpm --filter @opticloud/web test -- security-disclosure security/page.test.tsx security.txt
pnpm --filter @opticloud/web test
pnpm --filter @opticloud/web typecheck
pnpm -C apps/web build
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- J9 whitehat vertical slice is represented by a shared typed model, deterministic Mermaid, SOP steps, and exactly 22 hardenings.
- Public `/security` renders the full J9 flow without authentication or unsupported automation claims.
- J9 runbook documents dry-run evidence, redaction, and inactive automation boundaries.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-a-7-j9-whitehat-vertical-slice`.
- Baseline commit: `a6ab8741dd92f7b31bdd4d59afa40a5ce5d0846e`.
- Story creation used Epic 8.A / PRD Journey 9 / UX-DR7 J9 Mermaid flow / Story 8.A.6 security disclosure implementation.
- Customization resolver script was absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base skill customization files and found no `project-context.md`.
- Implementation started; story and sprint status moved to in-progress.
- Added shared J9 typed flow, SOP steps, exactly 22 hardenings, and deterministic Mermaid builder in `apps/web/src/lib/security-disclosure.ts`.
- Extended `/security` to render J9 flow stages, Mermaid source, SOP steps, and hardening checklist from the shared model.
- Added J9 runbook at `docs/runbooks/j9-whitehat-disclosure.md` with stage-aligned dry-run evidence, redaction rules, and inactive automation boundaries.
- Focused tests passed: `pnpm --filter @opticloud/web test -- security-disclosure security/page.test.tsx security.txt` (3 files, 12 tests).
- Full web tests passed: `pnpm --filter @opticloud/web test` (43 files, 207 tests).
- Typecheck passed: `pnpm --filter @opticloud/web typecheck`.
- Production build passed: `pnpm -C apps/web build`.
- Diff whitespace check passed: `git diff --check`.
- Post-implementation review completed manually without subagents per user constraint; fixed page copy/test drift and added model edge/field consistency assertions.
- Implementation commit pushed: `6b6f38c feat(web): add J9 whitehat disclosure slice`.
- PR #151 created at `https://github.com/proecheng/opticloud/pull/151`; GitHub CI passed (`changes`, `lint`, `ts-typecheck`, `e2e`, `matrix-detect`, `gtm-toolkit-validation`, `build-and-sbom (auth-service)`).
- PR #151 squash-merged to `main` as `10620b442a4f66810a33ae63fd26b67875c0814f`; remote branch `codex/8-a-7-j9-whitehat-vertical-slice` deleted and local `main` synced.

### Completion Notes List

- Story created for J9 whitehat vertical slice.
- Completed 3 pre-implementation adversarial review rounds and revised the story after each round.
- Implemented static J9 vertical slice as shared typed model, deterministic Mermaid source, SOP steps, and exactly 22 hardening items.
- Extended public `/security` page without client runtime, auth, storage, fetch, new dependencies, or unsupported automation claims.
- Added J9 whitehat runbook and test coverage to keep runbook stage names and inactive automation boundaries aligned with the model.
- Post-implementation code review found and fixed two issues: a page display deviation introduced only to avoid duplicate test text, and missing edge/required-field consistency assertions in model tests.
- GitHub sync complete: PR #151 passed CI, merged to `main`, remote branch deleted, local `main` synced, and final status moved to `done`.

### File List

- `_bmad-output/stories/8-a-7-j9-whitehat-vertical-slice.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/src/lib/security-disclosure.ts`
- `apps/web/src/lib/security-disclosure.test.ts`
- `apps/web/src/app/security/SecurityDisclosurePageView.tsx`
- `apps/web/src/app/security/page.test.tsx`
- `docs/runbooks/j9-whitehat-disclosure.md`

## Change Log

- 2026-06-03 - Story created for J9 whitehat vertical slice.
- 2026-06-03 - Completed 3 pre-implementation adversarial review rounds; story marked ready for development.
- 2026-06-03 - Implementation started; story and sprint status moved to in-progress.
- 2026-06-03 - Implemented J9 typed model, Mermaid builder, SOP steps, 22 hardenings, `/security` rendering, and runbook.
- 2026-06-03 - Completed post-implementation code review, applied fixes, and passed local gates; story and sprint status moved to code-review pending GitHub sync.
- 2026-06-03 - PR #151 passed CI, merged to main, remote branch deleted, local main synced; story and sprint status marked done.

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary, Automation, And Product Scope

Findings:

1. UX-DR7 says "48h SLA 自动 ticket", but current architecture has no ticketing service; active automation claims would be false.
2. PGP fallback appears in the UX flow, but 8.A.6 deliberately avoided `Encryption:` because there is no real PGP key.
3. Rewards and public thanks page need legal/anti-fraud handling; implementing payout or public researcher records now would exceed this story.
4. National/APT escalation cannot be represented as a casual product flow; it needs legal/regulatory handoff language.
5. A HackerOne-like platform is explicitly v2+ and must stay future/planned.

Revision after Round 1:

- Defined vertical slice as static model + Mermaid + SOP dry-run + hardening checklist.
- Added out-of-scope for active mailbox automation, PGP key, reward payout, public thanks DB, CVE automation, and external platform integration.
- Required status vocabulary and page copy to distinguish active/manual/planned/blocked.

### Round 2 - Data Consistency, Drift, And Closure

Findings:

1. Mermaid, SOP, hardening checklist, and page content can drift if authored separately.
2. "22 hardenings" can become a vague checklist unless exact count, IDs, owners, stages, statuses, and tests are required.
3. Flow branches must preserve UX semantics: ordinary bug report and academic/national channels are not the same as responsible disclosure.
4. Existing `security.txt` route must not regress by adding unsupported `Encryption`.
5. Runbook and model must agree on stages and evidence boundaries.

Revision after Round 2:

- Required a shared typed model as source for Mermaid and page rendering.
- Added exact 22 hardening count with unique ordered IDs.
- Added ACs for disclosure branch distinction and security.txt non-regression.
- Added runbook AC with dry-run evidence/redaction boundary alignment.

### Round 3 - Test, Dependency, And GitHub Lifecycle

Findings:

1. A client-side diagram renderer or Mermaid package would add unnecessary dependency and bundle risk.
2. Public page tests must keep no-auth/no-storage/no-fetch guard from 8.A.6.
3. Page text tests can miss overclaim regressions if they only assert happy-path labels.
4. The story must not be marked done before post-review, local gates, CI, merge, branch deletion, and local main sync.

Revision after Round 3:

- Required Mermaid source-only rendering with no new dependency.
- Required focused tests for no auth/storage/fetch, hardening count, Mermaid sanitization, and overclaim absence.
- Added local gate and GitHub lifecycle tasks, with final `done` only after merge/sync.
