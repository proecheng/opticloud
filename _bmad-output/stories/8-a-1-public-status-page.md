---
story_key: 8-a-1-public-status-page
baseline_commit: 973bfb22a87fc4748899d0da38d76aca62362e9c
epic_num: 8
story_num: A.1
epic_name: Public Status + Audit + Vuln Response
status: code-review
priority: High
type: Public unauthenticated status page
created_by: bmad-create-story
created_at: 2026-06-02
sources:
  - _bmad-output/planning/epics.md (Epic 8.A; Story 8.A.1-8.A.3 ordering)
  - _bmad-output/planning/prd.md (FR O1; NFR-O3; v1 excludes full Webhook callbacks)
  - _bmad-output/planning/architecture.md (Status-Page -> web / SSR / unauthenticated / Trust-Forward; OP8 deferred)
  - _bmad-output/planning/ux-design-specification.md (Status Page public, Trust-Forward, mobile basic)
  - packages/ui/src/components/StatusCard/index.tsx
  - apps/web/src/app/page.tsx
  - apps/web/package.json
---

# Story 8.A.1 - Public Status Page

Status: code-review

## Story

**作为** 任何未登录访客、客户 SRE 或潜在集成方，
**我希望** 可以无鉴权打开公开状态页并看到当前服务状态、组件状态、incident history、RSS 入口和订阅入口，
**从而** 在 OptiCloud 出现服务波动时能独立核验平台状态，并建立后续 incident 通知闭环的公开入口。

## Context

Epic 8.A 的顺序明确是公开 status page -> incident subscribe -> 24h Postmortem -> audit -> vuln -> J9 vertical slice。本 story 是 8.A 的入口 story，只建立公开、无鉴权、可发现的 Status Page 和 RSS 合同，不实现后续真实 email/Webhook 投递，也不实现 P0 24h Postmortem 详情页。

PRD 同时声明 O1 需要“任何访客 can view status page without authentication；用户 can subscribe via email/Webhook”，但多处范围说明将“Webhook 回调”列为 v2/Growth 或 v1 不做能力。因此本 story 的 Webhook 范围必须收敛为公开订阅入口/后续登录订阅流的发现，不得声称已启用真实 Webhook delivery。Story 8.A.2 才负责登录用户订阅 email/Webhook 并自动推送后续 incident。

Architecture 将 Status-Page 标为 `web / SSR / 无鉴权 / Direction "Trust-Forward"`，OP8 “Status Page 自动化工具”延后到 v1.5 决策。本 story 应使用 `apps/web` 的静态/typed status model + Next route handler 提供最小闭环，不接入 Uptime Kuma、Atlassian Statuspage、数据库、Prometheus、Grafana、api-gateway deep health 或新后台服务。

## Scope

1. 在 `apps/web` 新增公开 `/status` 页面，无需登录、无 sessionStorage/localStorage 依赖、无 Console JWT gate。
2. 新增一个 typed public status model，统一派生：
   - overall status
   - component status
   - incident history
   - RSS item data
3. 新增 `/status/rss.xml` route handler，返回公开 RSS XML。
4. 页面显示：
   - 当前整体状态和最后更新时间
   - 组件状态列表
   - incident history
   - RSS 订阅链接
   - email/Webhook 订阅入口说明，明确真实投递由 8.A.2 登录订阅流承接
5. 增加 web Vitest 覆盖 status model、page 和 RSS route。
6. 更新公开导航入口，使 Status Page 可发现。

## Out Of Scope

- 真实 email/Webhook subscription persistence、Webhook delivery、HMAC signing、retry、secret rotation、用户订阅管理 UI/API。
- P0 24h Postmortem 详情页、`/status/incidents/{id}`、Mermaid timeline、管理员发布流程。
- 接入 Uptime Kuma、Atlassian Statuspage、Grafana Cloud、Prometheus、Loki、Sentry、api-gateway `/v1/system/health` 或任何新外部服务。
- 新数据库表、迁移、后端服务、OpenAPI codegen、cron、incident automation、oncall paging、补偿/退款逻辑。
- Console-only audit log、vulnerability submission、rate limit、RFC7807 error panel。
- 添加 npm 依赖、图标库、状态管理库或新的 shared UI package dependency。

## Acceptance Criteria

1. `/status` is public and renders without reading `sessionStorage.jwt_access`, `localStorage`, cookies, or auth client state.
2. `/status` must not redirect unauthenticated visitors to `/auth/login`.
3. The page presents OptiCloud status as a Trust-Forward operational surface, not a marketing landing page or Console card nest.
4. The page displays a derived overall status with stable labels for at least `operational`, `degraded_performance`, `partial_outage`, and `major_outage`.
5. Overall status is derived from component severities, not hardcoded independently from component data.
6. Component data includes stable component IDs and labels for API Gateway, Auth, Solver Orchestrator, Billing, Chat, and Capability Registry.
7. Every component row/card shows status, short description, and last checked/updated timestamp.
8. Incident history is shown in reverse chronological order by `started_at`.
9. Incident history includes stable incident ID, title, severity, status, started/resolved timestamps, and affected component IDs or labels.
10. The page handles an empty incident history with an explicit empty state.
11. The page includes an RSS link pointing to `/status/rss.xml`.
12. `/status/rss.xml` returns status 200, `Content-Type` including `application/rss+xml`, and a valid RSS 2.0 XML document.
13. RSS output includes channel metadata and incident items derived from the same status model used by `/status`.
14. RSS item ordering matches page incident ordering.
15. RSS XML escapes user-visible fields so titles/descriptions containing `&`, `<`, `>` or quotes cannot break XML.
16. The page includes email and Webhook subscription discovery entries without claiming real delivery is active in this story.
17. The Webhook entry must state that managed delivery and signed callbacks are handled by the follow-up authenticated subscription flow, not by this public page.
18. No network fetch is required for the initial status page render; page data comes from local typed model data.
19. No new environment variable is required for local tests or development.
20. Public navigation includes a discoverable link to `/status`.
21. No npm/package dependency is added.
22. Tests cover status derivation, incident ordering, RSS XML escaping, RSS content type, public/no-auth page rendering, subscription entries, and no browser storage reads/writes.
23. Focused tests pass before broader gates.
24. Local gates pass: `pnpm --filter @opticloud/web test`, `pnpm --filter @opticloud/web typecheck`, and `git diff --check`.
25. Implementation record includes post-implementation code review findings and fixes.
26. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done`.

## Tasks / Subtasks

- [x] T1: Add public status model (AC: 4-10, 13-15, 18, 22)
  - [x] Define typed component, incident, severity, and overall status contracts under `apps/web/src/lib`.
  - [x] Implement deterministic overall-status derivation from components.
  - [x] Implement deterministic reverse chronological incident ordering.
  - [x] Add model tests for severity derivation and incident ordering.

- [x] T2: Add `/status` public SSR page (AC: 1-11, 16-20, 22)
  - [x] Render operational header, overall status, component list, incident history, and subscription entries.
  - [x] Use existing `StatusCard` and simple responsive sections; avoid nested card layouts.
  - [x] Add a public navigation link to `/status`.
  - [x] Add page tests for public/no-auth rendering, RSS link, subscription entries, and no storage reads/writes.

- [x] T3: Add `/status/rss.xml` route (AC: 12-15, 22)
  - [x] Return RSS 2.0 XML from the shared status model.
  - [x] Escape XML fields explicitly.
  - [x] Add route tests for content type, incident items, ordering, and escaping.

- [ ] T4: Review, gates, and GitHub sync (AC: 21, 23-26)
  - [x] Confirm `apps/web/package.json` has no dependency change.
  - [x] Run post-implementation code review and fix findings.
  - [x] Record review findings and fixes in this story.
  - [x] Run focused tests, full web tests, typecheck, and diff-check.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [ ] Mark story and sprint status `done` only after merge/sync.

## Dev Notes

### Service Boundary

- Implement only in `apps/web`, this story file, and `sprint-status.yaml`.
- The public page must not import Console auth utilities, call `useRouter`, read `sessionStorage`, or inspect JWT/API keys.
- The RSS route should be a Next App Router route handler under `apps/web/src/app/status/rss.xml/route.ts`.
- Prefer static server rendering or simple server component behavior. Avoid `"use client"` unless a specific interaction requires it; this story does not need client interactivity.

### Existing Patterns To Reuse

- Reuse the landing/academic header style from `apps/web/src/app/page.tsx` and `apps/web/src/app/academic/page.tsx`.
- Reuse `StatusCard` from `@opticloud/ui`; its comment explicitly says it is used for Status Page (FR O1).
- Keep copy operational and direct. Do not use a marketing hero, oversized decorative cards, or one-note gradient backgrounds.
- Use plain tables/lists and responsive grids with stable dimensions so component/incident text does not overlap on mobile.

### Data Semantics

- Status model data is a public read model placeholder, not live Prometheus/Grafana truth.
- Timestamps should be explicit ISO strings in source data and rendered as readable absolute times.
- The page may show "last updated" for current model freshness, but must not imply automatic monitoring integration.
- Component status severity order should be: `operational < degraded_performance < partial_outage < major_outage`.
- Incident `status` values should distinguish `investigating`, `identified`, `monitoring`, and `resolved`.
- If no active incident exists, the page can state no active incident based on the public model only.

### Cross-Story Boundaries

- 8.A.2 owns authenticated email/Webhook subscription persistence and automatic delivery.
- 8.A.3 owns P0 24h Postmortem pages and Mermaid timelines.
- Epic 9 owns quarterly observability governance/audit.
- OP8 says Status Page automation vendor/tooling is a v1.5 decision; do not make that decision here.

### Testing Guidance

- Add pure tests for `apps/web/src/lib/status-page.ts`.
- Add happy-dom page tests for `apps/web/src/app/status/page.test.tsx` if the page imports `next/link`.
- Add route tests for `apps/web/src/app/status/rss.xml/route.test.ts` by importing `GET` and checking `await response.text()`.
- In no-auth tests, replace `window.sessionStorage.getItem`, `window.sessionStorage.setItem`, `window.localStorage.getItem`, and `window.localStorage.setItem` with throwing spies to prove the public route does not touch browser storage.
- For RSS escaping, include a test-only incident title/summary containing `&`, `<`, `>`, `"`, and `'` through exported pure helpers rather than mutating the production fixture.

### Suggested Commands

```powershell
pnpm --filter @opticloud/web test -- status-page status/page status/rss
pnpm --filter @opticloud/web test
pnpm --filter @opticloud/web typecheck
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Public Status Page satisfies FR O1 without authentication and without over-claiming Webhook delivery.
- RSS route is implemented from the same status model as the page.
- No backend, database, OpenAPI, external vendor, or package dependency is added.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-a-1-public-status-page`.
- Baseline commit: `973bfb22a87fc4748899d0da38d76aca62362e9c`.
- Story creation used local context from Epic 8.A, PRD O1/NFR-O3, architecture Status-Page mapping, UX Status Page notes, existing landing/academic page patterns, and `StatusCard`.
- Customization resolver script was absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base `bmad-create-story/customize.toml`, found no team/user overrides, and loaded no `project-context.md` files.
- Implementation started; story and sprint status moved to in-progress.
- RED confirmed before implementation: focused status tests failed because `status-page` model, `/status` page, and `/status/rss.xml` route did not exist.
- Focused status tests after implementation: `pnpm --filter @opticloud/web test -- status-page page.test.tsx route.test.ts` -> 51 passed.
- Post-implementation code review found 2 patch findings: empty incident-history AC was not directly testable through the page, and the no-network-render boundary was not directly asserted.
- Review fixes added injectable `StatusPageView`, empty incident-history page test, and no-fetch assertion for the public render path.
- Focused status tests after review fixes: `pnpm --filter @opticloud/web test -- status-page page.test.tsx route.test.ts` -> 52 passed.
- Type gate after review fixes: `pnpm --filter @opticloud/web typecheck` -> passed.
- Whitespace gate after review fixes: `git diff --check` -> passed.
- Full web regression after review fixes: `pnpm --filter @opticloud/web test` -> 179 passed.
- Story and sprint status moved to `code-review` after local review and gates; final `done` remains gated on GitHub CI, PR merge, remote branch cleanup, and local `main` sync.
- GitHub PR #145 first CI run failed in e2e build because `apps/web/src/app/status/page.tsx` exported non-Next page field `StatusPageView`.
- CI fix moved `StatusPageView` to `apps/web/src/app/status/StatusPageView.tsx`; reran focused status tests, typecheck, diff-check, and `pnpm -C apps/web build` successfully before pushing the fix.

### Completion Notes List

- Story created for public unauthenticated Status Page.
- Completed 3 pre-implementation adversarial review rounds and revised the story after each round.
- Added shared public status model, derived overall status, ordered incident history, RSS XML generation with escaping, public `/status` page, `/status/rss.xml` route, homepage navigation link, and focused tests.
- Post-review fixes added coverage for empty incident history and no network fetch during public status page render.

### File List

- `_bmad-output/stories/8-a-1-public-status-page.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/src/lib/status-page.ts`
- `apps/web/src/lib/status-page.test.ts`
- `apps/web/src/app/status/page.tsx`
- `apps/web/src/app/status/page.test.tsx`
- `apps/web/src/app/status/StatusPageView.tsx`
- `apps/web/src/app/status/rss.xml/route.ts`
- `apps/web/src/app/status/rss.xml/route.test.ts`
- `apps/web/src/app/page.tsx`
- `apps/web/src/i18n/messages/en-US.json`
- `apps/web/src/i18n/messages/zh-CN.json`

## Change Log

- 2026-06-02 - Story created for public unauthenticated Status Page.
- 2026-06-02 - Completed 3 pre-implementation adversarial review rounds; story marked ready for development.
- 2026-06-02 - Implementation started; story and sprint status moved to in-progress.
- 2026-06-02 - Implemented public status model, `/status`, `/status/rss.xml`, homepage navigation, and focused tests.
- 2026-06-02 - Completed post-implementation code review, fixed 2 patch findings, and reran local gates.
- 2026-06-02 - Story moved to code-review pending GitHub sync.
- 2026-06-02 - Fixed CI Next build export issue by moving `StatusPageView` out of `page.tsx`; local Next build passed.

## Post-Implementation Code Review

### Review Layers

- Blind Hunter: reviewed changed behavior for public/no-auth status surface, RSS output, and dependency drift.
- Edge Case Hunter: reviewed empty incident history, browser storage/network access, RSS ordering/escaping, and model/page consistency.
- Acceptance Auditor: checked implementation against AC 1-26 in this story.

### Findings And Fixes

1. [Review][Patch][Fixed] Empty incident history was specified but not directly exercised through page rendering.
   - Fix: exported `StatusPageView` with injectable `PublicStatusModel` and added a page test for `incidents: []`.
2. [Review][Patch][Fixed] The no-network-render boundary was implied by local model use but not directly locked by a test.
   - Fix: added a throwing `globalThis.fetch` spy in the public render test and asserted it is not called.

### Review Result

- Decision-needed: 0
- Patch findings: 2 fixed
- Deferred: 0
- Dismissed: 0

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary, Product Scope, And Authentication Review

Findings:

1. The original AC mentions "RSS / Webhook 订阅", which could be misread as real Webhook delivery in this story.
2. PRD repeatedly says full Webhook callback capability is v2/Growth or not v1, so implementing HMAC delivery now would violate scope.
3. Status Page could drift into 8.A.3 Postmortem pages and admin publishing.
4. "status.opticloud.cn" could lead to deployment/domain config work instead of app route implementation.
5. A public page could accidentally reuse Console login patterns and require `sessionStorage.jwt_access`.
6. Incident automation could pull in backend health endpoints, databases, or vendor tooling before OP8 is decided.
7. A marketing-style hero would weaken the intended Trust-Forward operational surface.

Revisions applied:

- Added explicit out-of-scope for Webhook delivery, HMAC signing, Postmortem pages, external vendors, backend services, and deployment/domain work.
- Added ACs proving no auth/storage/login redirect.
- Scoped Webhook to public discovery copy that points to the follow-up authenticated subscription flow.
- Added UI direction and copy constraints for an operational, non-marketing page.

### Round 2 - Drift, Data Consistency, And Public Truth Review

Findings:

1. Overall status could drift from component statuses if hardcoded separately.
2. Page and RSS could disagree if they use separate fixtures.
3. Incident ordering could be inconsistent between page and RSS.
4. Static status data could falsely imply live monitoring if labels are not careful.
5. Timestamps could be relative or locale-only, making incident history hard to audit.
6. RSS XML could break or become unsafe if user-visible incident strings are not escaped.
7. Empty incident states need defined behavior to avoid fake incidents or blank sections.

Revisions applied:

- Required a shared typed status model for page and RSS.
- Required derived overall status and reverse chronological incident ordering.
- Added explicit timestamp, public read-model, and "do not imply automatic monitoring" semantics.
- Added RSS XML escaping and empty-history AC/test guidance.

### Round 3 - Dependency, Test Closure, And Implementation Risk Review

Findings:

1. Adding a status-page vendor SDK or date/formatting library would create unnecessary dependency drift.
2. A client component would introduce avoidable storage/browser risk for a public SSR page.
3. Tests could pass page rendering but miss the critical no-auth/no-storage guarantee.
4. RSS route tests might only assert body substrings and miss content type.
5. Navigation could be omitted, leaving the page undiscoverable.
6. Story completion could be marked done before GitHub merge/sync, violating the user's process.
7. The local gate list must include both focused tests and full web gates.

Revisions applied:

- Added no-new-dependency AC and package check task.
- Required server/static implementation unless a specific interaction needs client behavior.
- Added tests for no storage reads/writes, RSS content type, and escaping.
- Added navigation discoverability AC.
- Added GitHub merge/sync as a Definition of Done gate before marking `done`.
