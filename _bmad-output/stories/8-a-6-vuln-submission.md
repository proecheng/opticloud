---
story_key: 8-a-6-vuln-submission
baseline_commit: 935dfff5004875b7c696108cc239c5b8a88ae274
epic_num: 8
story_num: A.6
epic_name: Public Status + Audit + Vuln Response
status: done
priority: High
type: Public vulnerability disclosure submission surface
created_by: bmad-create-story
created_at: 2026-06-03
sources:
  - _bmad-output/planning/epics.md (Epic 8.A / Story 8.A.6)
  - _bmad-output/planning/prd.md (FR O4; Journey 9; vulnerability response SLA tension with NFR-R)
  - _bmad-output/planning/architecture.md (J9 -> O4, cross-cut concerns 4 and 10)
  - _bmad-output/planning/ux-design-specification.md (J9 security.txt + security@opticloud.cn)
  - _bmad-output/stories/8-a-1-public-status-page.md
  - _bmad-output/stories/8-a-2-incident-subscribe.md
  - _bmad-output/stories/8-a-3-24h-postmortem.md
  - RFC 9116 security.txt (https://www.rfc-editor.org/rfc/rfc9116.html)
  - apps/web/src/app/status/StatusPageView.tsx
  - apps/web/src/lib/status-page.ts
---

# Story 8.A.6 - 安全研究者 Vuln Submission

Status: done

## Story

**作为** 安全研究者或白帽报告者，
**我希望** 可以通过 `/.well-known/security.txt` 和公开安全披露政策页快速找到 `security@opticloud.cn`、提交材料要求、响应 SLA、修复目标和安全测试边界，
**从而** 在发现 OptiCloud `/api/v1/*` 或相关公开服务漏洞时，能够负责任披露并获得 48 小时内确认与 CVSS >= 7 漏洞 7 天内修复目标的明确承诺。

## Context

Story 8.A.1-8.A.3 已交付公开 status / RSS / incident subscription / P0 Postmortem 表面。8.A.4-8.A.5 已交付用户审计日志查询与 Console AuditLogTable。本 story 是 O4/J9 的第一段：建立研究者发现入口和可测试披露政策合同。

PRD 与 UX 同时提到 `security.txt`、`security@opticloud.cn`、48h 响应、7d 修复、奖励、致谢页和自动 CVE tracking；但 Epic 8.A.7 才是 J9 白帽 vertical slice，UX 中的自动 ticket、PGP 备用、奖励/反诈、公开致谢完整流程、国安级/学术/HackerOne-like 多通道都属于后续 SOP/硬化扩展。本 story 不实现邮箱接收、SMTP 自动回复、工单系统、奖励支付、CVE 自动化或后台 triage UI；它必须公开且准确地给出 submission surface 和响应承诺，不能伪装已有运行中的邮件自动化。

PRD NFR-R 章节写有 CVSS >= 7 关键漏洞 24h 补丁部署，而 Story 8.A.6 AC 写的是 CVSS >= 7 patch <= 7d。为避免降低内部 NFR，本 story 对外页面必须至少承诺 CVSS >= 7 的 7 天内修复目标，同时说明已被主动利用或平台关键路径风险可进入更严格的内部 24h hotfix 路径；测试只锁定公开 O4 的 <=7d 目标，不削弱后续 NFR-R 证据。

## Scope

1. 在 `apps/web` 新增公开 `/.well-known/security.txt` route，返回 RFC 9116 风格的 UTF-8 plain text。
2. 新增公开 `/security` 披露政策页，无鉴权、无 storage、无 render-time network fetch。
3. 新增 typed security disclosure policy model，统一派生 `security.txt` 和页面内容。
4. 页面展示：
   - 披露邮箱 `security@opticloud.cn` 和 `mailto:` 链接
   - 需要包含的报告字段：受影响端点、影响说明、PoC/复现步骤、CVSS 估计、研究者联系方式
   - 响应 SLA：48h 内确认；CVSS >= 7 修复目标 <= 7 天
   - 安全测试边界与 safe harbor 条件
   - 普通 bug report、学术披露、国安级/APT、奖励/致谢/CVE automation 的边界说明
5. 更新公开导航入口，使 Security 页面可发现。
6. 增加 web Vitest 覆盖 model、route、page、导航、无鉴权/无 storage/无 fetch、SLA 数值和 overclaim 防线。

## Out Of Scope

- 真实邮箱收件、SMTP/IMAP provider、邮件自动回复、邮箱 webhook、ticket 创建、Telegram/DingTalk bot、PagerDuty、on-call paging。
- 后端数据库表、migration、OpenAPI route、admin triage UI、report CRUD、CVE automation、漏洞扫描器、依赖扫描集成。
- 奖励支付、白帽反诈协议、公开 thanks page 列表、重复披露裁定；这些留给 8.A.7 或 v1.5+ legal/SOP。
- PGP key 发布和加密报告接收；本 story 可以说明未来会补 PGP，但不得在 `security.txt` 写不存在的 Encryption 字段。
- 国安级/APT escalate SOP 的可执行流程；本 story 只在页面上明确需要走独立 escalation，不把它伪装成已自动化。
- 普通产品 bug report 工单系统或匿名 visitor form；安全邮箱只用于安全漏洞。
- 新 npm/package dependency、外部服务、运行时环境变量。

## Acceptance Criteria

1. `/.well-known/security.txt` returns status 200 and `Content-Type` including `text/plain; charset=utf-8`.
2. `security.txt` contains `Contact: mailto:security@opticloud.cn`.
3. `security.txt` contains `Policy: https://opticloud.cn/security`.
4. `security.txt` contains `Canonical: https://opticloud.cn/.well-known/security.txt`.
5. `security.txt` contains `Preferred-Languages: zh, en`.
6. `security.txt` contains an RFC3339 `Expires:` timestamp less than one year after the policy `updated_at`.
7. `security.txt` does not contain an `Encryption:` field until a real public PGP key URL exists.
8. `security.txt` is generated from the same typed policy model used by `/security`, not hand-authored separately.
9. `/security` is public and renders without reading `sessionStorage`, `localStorage`, cookies, JWT, API keys, or account state.
10. `/security` must not redirect unauthenticated visitors to `/auth/login`.
11. `/security` render does not call `fetch` or any external network service.
12. The page presents `security@opticloud.cn` as the responsible disclosure mailbox with a `mailto:` link.
13. The page lists required report fields: affected endpoint/service, vulnerability class/impact, reproduction steps or PoC, CVSS estimate, and reporter contact.
14. The page states initial acknowledgement target as <= 48 hours.
15. The page states CVSS >= 7 remediation target as <= 7 days.
16. The page does not claim that SMTP auto-reply, ticket automation, CVE tracking, bounty payment, PGP encrypted intake, or provider delivery is active.
17. The page separates responsible security disclosure from ordinary product bug reports and support requests.
18. The page states safe harbor boundaries: no data exfiltration, no destructive testing, no persistence/backdoors, no social engineering, no DDoS/load testing, and stop after minimal proof.
19. The page states that privacy-impacting findings must use synthetic or researcher-owned test data where possible.
20. The page states duplicate disclosure, reward eligibility, public acknowledgement, PGP fallback, and CVE tracking are handled by later policy/SOP, not this static submission surface.
21. Public navigation includes a discoverable link to `/security`.
22. No new runtime dependency or environment variable is added.
23. Focused tests cover security policy model, security.txt route, public page rendering, no storage/no fetch, SLA values, required fields, safe harbor, and overclaim absence.
24. Local gates pass: focused web tests, `pnpm --filter @opticloud/web test`, `pnpm --filter @opticloud/web typecheck`, and `git diff --check`.
25. Implementation record includes post-implementation code review findings and fixes.
26. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done`.

## Tasks / Subtasks

- [x] T1: Add shared disclosure policy model (AC: 2-8, 12-20, 22-23)
  - [x] Define typed contact, SLA, required-fields, safe-harbor, and boundary contracts under `apps/web/src/lib`.
  - [x] Implement deterministic `buildSecurityTxt()` from the shared policy model.
  - [x] Add model tests for RFC fields, Expires freshness, SLA values, required report fields, safe-harbor items, and no unsupported Encryption field.

- [x] T2: Add `/.well-known/security.txt` route (AC: 1-8, 16, 22-23)
  - [x] Add Next App Router route handler under `apps/web/src/app/.well-known/security.txt/route.ts`.
  - [x] Return UTF-8 plain text with no network or auth dependency.
  - [x] Add route tests for status, content type, fields, and overclaim absence.

- [x] T3: Add public `/security` disclosure page (AC: 9-21, 23)
  - [x] Add route page and injectable view component following the `/status` testability pattern.
  - [x] Render contact, report requirements, SLA, safe harbor, boundaries, and future policy items.
  - [x] Add navigation link from landing and public page header.
  - [x] Add happy-dom page tests for public/no-auth/no-storage/no-fetch rendering and required copy.

- [x] T4: Review, gates, and GitHub sync (AC: 22-26)
  - [x] Confirm `apps/web/package.json` has no dependency change.
  - [x] Run focused tests before broader gates.
  - [x] Run post-implementation code review and fix findings.
  - [x] Record review findings and fixes in this story.
  - [x] Run local gates.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [x] Mark story and sprint status `done` only after merge/sync.

## Dev Notes

### Service Boundary

- Implement only in `apps/web`, this story file, and `sprint-status.yaml` unless tests require a narrowly scoped shared message update.
- Keep `apps/web/src/lib/security-disclosure.ts` as the single source for `/.well-known/security.txt` and `/security`.
- Use `apps/web/src/app/.well-known/security.txt/route.ts` for the route handler.
- Use an adjacent `SecurityDisclosurePageView.tsx` for testability; do not export non-Next fields from `page.tsx`.
- Prefer server/static components. This story does not need `"use client"`.

### Existing Patterns To Reuse

- Reuse public header/nav structure from `StatusPageView` and landing page.
- Reuse the route test style from `/status/rss.xml`.
- Reuse public/no-auth/no-storage/no-fetch test pattern from `apps/web/src/app/status/page.test.tsx`.
- Keep copy operational and direct. This is a Trust-Forward security surface, not a marketing landing page.

### Data Semantics

- `security.txt` is a discovery file, not evidence that unlimited testing is authorized.
- `Expires` should be a fixed ISO timestamp in the policy model and within one year after `updated_at` so tests are deterministic.
- Do not include `Encryption` until a real public PGP key URL exists.
- Do not use mutable current time during render/tests for SLA or Expires checks.
- The public 7-day CVSS >= 7 patch target is an external O4 promise; the stricter PRD NFR 24h critical hotfix path remains a future/internal evidence requirement.

### Cross-Story Boundaries

- Story 8.A.1 owns public `/status` and RSS.
- Story 8.A.2 owns authenticated incident subscriptions and fan-out.
- Story 8.A.3 owns public P0 postmortem details.
- Story 8.A.7 owns full J9 vertical slice, SOP execution, hardenings, PGP fallback, duplicate disclosure handling, public acknowledgements, reward/anti-fraud workflow, and any mailbox/ticket automation.
- Epic 9 owns broader governance/audits.

### Suggested Commands

```powershell
pnpm --filter @opticloud/web test -- security-disclosure security/page.test.tsx security.txt
pnpm --filter @opticloud/web test
pnpm --filter @opticloud/web typecheck
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Public `security.txt` and `/security` page satisfy O4 discovery/submission surface without authentication and without claiming unimplemented automation.
- SLA and safety boundaries are test-covered from a shared typed policy model.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-a-6-vuln-submission`.
- Baseline commit: `935dfff5004875b7c696108cc239c5b8a88ae274`.
- Story creation used Epic 8.A / PRD O4+J9, Architecture J9 mapping, UX J9 flow, prior stories 8.A.1-8.A.3, current public status implementation patterns, and RFC 9116.
- Customization resolver script was absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base `bmad-create-story/customize.toml`, found no team/user overrides, and loaded no `project-context.md` files.
- Implementation started; story and sprint status moved to in-progress.
- RED confirmed before implementation: focused security disclosure tests failed because the policy model, `/.well-known/security.txt` route, and `/security` page did not exist.
- Focused security tests after implementation: `pnpm --filter @opticloud/web test -- security-disclosure security/page.test.tsx security.txt` -> 7 passed.
- Local gates before review fixes: `pnpm --filter @opticloud/web test` -> 202 passed; `pnpm --filter @opticloud/web typecheck` -> passed; `git diff --check` -> passed; package/lockfile diff empty.
- Post-implementation code review found 2 patch findings: landing nav could overflow after adding another public nav item, and public status page did not expose the new Security trust surface in its header. Both were fixed.
- Focused tests after review fixes: `pnpm --filter @opticloud/web test -- security-disclosure security/page.test.tsx security.txt status/page.test.tsx` -> 10 passed.
- Final gates after review fixes: `pnpm --filter @opticloud/web test` -> 202 passed; `pnpm --filter @opticloud/web typecheck` -> passed; `pnpm -C apps/web build` -> passed; `git diff --check` -> passed; package/lockfile diff empty.
- Story and sprint status moved to `code-review` after local gates; final `done` remains gated on GitHub CI, PR merge, remote branch cleanup, local `main` sync, and post-merge status sync.
- GitHub sync: PR #150 passed checks including `changes`, `lint`, `ts-typecheck`, `e2e`, `matrix-detect`, `build-and-sbom (auth-service)`, and `gtm-toolkit-validation`; PR squash-merged to `main` at `112d3281e7523668517a5382d6ae67db3bac9b8f`; remote branch `codex/8-a-6-vuln-submission` was deleted; local `main` is synced to `origin/main`.

### Completion Notes List

- Story created for public vulnerability disclosure submission surface.
- Completed 3 pre-implementation adversarial review rounds and revised the story after each round.
- Implemented shared `security.txt` / `/security` public disclosure surface, report requirements, SLA copy, safe-harbor boundaries, and overclaim protections.
- GitHub sync completed: PR #150 passed CI, merged, remote branch deleted, local `main` synced, and story/sprint status marked done.

### File List

- `_bmad-output/stories/8-a-6-vuln-submission.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/src/lib/security-disclosure.ts`
- `apps/web/src/lib/security-disclosure.test.ts`
- `apps/web/src/app/.well-known/security.txt/route.ts`
- `apps/web/src/app/.well-known/security.txt/route.test.ts`
- `apps/web/src/app/security/page.tsx`
- `apps/web/src/app/security/SecurityDisclosurePageView.tsx`
- `apps/web/src/app/security/page.test.tsx`
- `apps/web/src/app/page.tsx`
- `apps/web/src/app/status/StatusPageView.tsx`
- `apps/web/src/app/status/page.test.tsx`
- `apps/web/src/i18n/messages/en-US.json`
- `apps/web/src/i18n/messages/zh-CN.json`

## Change Log

- 2026-06-03 - Story created for public security disclosure surface.
- 2026-06-03 - Completed 3 pre-implementation adversarial review rounds; story marked ready for development.
- 2026-06-03 - Implementation started; story and sprint status moved to in-progress.
- 2026-06-03 - Implemented shared security disclosure policy model, `/.well-known/security.txt`, `/security` page, public navigation link, and focused tests.
- 2026-06-03 - Completed post-implementation code review; fixed public nav wrap and Status Page Security discoverability; final local gates passed and story moved to code-review pending GitHub sync.
- 2026-06-03 - PR #150 passed GitHub CI, merged to main, remote branch deleted, local main synced; story marked done.

## Post-Implementation Code Review

### Review Layers

- Blind Hunter: reviewed raw change for public surface regressions, dependency drift, and route/header behavior.
- Edge Case Hunter: reviewed narrow-view navigation, public/no-auth/no-fetch behavior, RFC 9116 field consistency, and overclaim boundaries.
- Acceptance Auditor: checked implementation against AC 1-26 in this story.

### Findings And Fixes

1. [Review][Patch][Fixed] Landing header used a non-wrapping `flex`/`nav`; adding the new Security nav item increased mobile overflow risk.
   - Fix: allowed the landing header and nav to wrap with gap controls, matching the public Status Page header pattern.
2. [Review][Patch][Fixed] The existing `/status` public trust surface did not expose the new Security page in its header, making discovery dependent on the landing page only.
   - Fix: added a `/security` link to `StatusPageView` and a regression assertion in `status/page.test.tsx`.

### Review Result

- Decision-needed: 0
- Patch findings: 2 fixed
- Deferred: 0
- Dismissed: 0

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary, Product Scope, And Automation Claims

Findings:

1. Epic AC says automatic acknowledgement, but the repo has no SMTP/IMAP intake, mailbox webhook, ticketing system, or provider delivery path; claiming live auto-reply would be false.
2. UX J9 includes PGP fallback, Telegram bot, reward, public thanks page, duplicate disclosure, and national/APT escalation, but Story 8.A.7 explicitly owns the full vertical slice and hardenings.
3. `security.txt` can be misread as permission for broad testing unless the policy page states explicit safe-harbor boundaries.
4. Publishing an `Encryption:` field without a real PGP key URL would violate the trust surface.
5. Adding a web form would introduce unauthenticated PII/security-report storage without architecture or privacy review.

Revision after Round 1:

- Scoped the story to public discovery/submission contract: `security.txt`, `/security`, typed policy model, and tests.
- Added hard out-of-scope for mailbox automation, ticketing, PGP key, bounty payment, thanks page list, CVE automation, and web report form.
- Added ACs preventing claims that unimplemented automation is active.
- Added safe-harbor, minimal-proof, and no-destructive-testing ACs.

### Round 2 - SLA Drift, Data Consistency, And RFC Correctness

Findings:

1. PRD NFR-R says CVSS >= 7 critical vulnerabilities get 24h patch deployment, while Epic Story 8.A.6 says CVSS >= 7 patch <= 7d.
2. `security.txt` and `/security` can drift if they are hand-authored separately.
3. `Expires` can become stale or flaky if calculated from current time during tests.
4. RFC 9116 requires `Contact` and recommends canonical/policy/expires conventions; incorrect content type or top-level-only path would weaken interoperability.
5. The policy must separate product bug reports from security vulnerabilities to reduce triage noise.

Revision after Round 2:

- Defined public O4 target as <=7d for CVSS >= 7 while preserving stricter internal 24h hotfix as future/NFR evidence.
- Required a shared typed policy model for route and page.
- Required deterministic fixed `updated_at` and `expires_at`, with tests for less-than-one-year freshness.
- Added RFC field/content-type ACs and no unsupported `Encryption` AC.
- Added separate responsible disclosure vs product bug/support language.

### Round 3 - Dependency, Test Closure, And GitHub Lifecycle

Findings:

1. A client component or auth/account import could accidentally introduce browser storage reads on a public page.
2. Tests could verify visible text but miss the critical no-fetch/no-storage/no-auth guarantees.
3. Adding a package for RFC formatting, markdown, or date handling would be unnecessary dependency drift.
4. Next App Router `page.tsx` should not export extra testing helpers; prior story learned this can break builds.
5. Story completion must not be marked `done` until post-review, local gates, GitHub CI, merge, branch deletion, local main sync, and status sync are complete.

Revision after Round 3:

- Required server/static page and route implementation, no runtime dependencies, no env vars.
- Added tests for no storage reads/writes and no render-time fetch.
- Required adjacent injectable view component instead of extra `page.tsx` exports.
- Added local gate and GitHub lifecycle ACs/tasks, with final `done` only after merge/sync.
