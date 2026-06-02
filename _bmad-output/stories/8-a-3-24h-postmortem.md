---
story_key: 8-a-3-24h-postmortem
baseline_commit: 58555637f9eb10bae71f431b37e1c9932827afc2
epic_num: 8
story_num: A.3
epic_name: Public Status + Audit + Vuln Response
status: code-review
priority: High
type: Public P0 postmortem detail page
created_by: bmad-create-story
created_at: 2026-06-02
sources:
  - _bmad-output/planning/epics.md (Epic 8.A / Story 8.A.3)
  - _bmad-output/planning/prd.md (FR O2; P0 security incident 24h public postmortem)
  - _bmad-output/planning/architecture.md (O2 Postmortem = docs/runbooks; OP8 Status Page automation deferred)
  - _bmad-output/stories/3-12-j3-sre-incident-tier3.md
  - _bmad-output/stories/8-a-1-public-status-page.md
  - _bmad-output/stories/8-a-2-incident-subscribe.md
  - tools/incidents/j3_sre_incident.example.json
  - docs/runbooks/j3-sre-incident-tier3.md
  - apps/web/src/lib/status-page.ts
  - apps/web/src/app/status/StatusPageView.tsx
---

# Story 8.A.3 - 24h Postmortem

Status: code-review

## Story

**作为** 任何未登录访客、客户 SRE 或受影响客户，
**我希望** 可以在 P0 incident 发生后的 24 小时内打开公开 `/status/incidents/{id}` Postmortem，并看到同一事故记录派生出的原因说明、影响范围、缓解动作、后续事项和 Mermaid 时间线，
**从而** 不需要登录 Console 或依赖私下沟通，也能验证 OptiCloud 对 P0 事件的公开复盘 SLA 是否闭环。

## Context

Story 8.A.1 已交付公开 `/status`、RSS 和 typed public status model。Story 8.A.2 已交付登录用户 incident 订阅偏好与内部 fan-out 请求合同。Story 3.12 已交付 J3 静态 incident contract、Postmortem skeleton 和 runbook，但明确不是生产公开 Status Page/Postmortem 页面。

本 story 将 8.A.3 的生产公开表面收敛到 `apps/web`：扩展现有 public status read model，新增公开 `/status/incidents/[incidentId]` 详情页，并从同一 incident/postmortem 数据派生 Mermaid timeline 源码和可读时间线。它不新增数据库、管理员 CRUD、监控自动化、DingTalk、Statuspage SaaS、退款/补偿执行、Webhook delivery 或后台发布系统；Architecture 已将 O2 标为 docs/runbooks 风格，OP8 自动化工具决策延后。

## Scope

1. 扩展 `apps/web/src/lib/status-page.ts` 的 public incident model，支持 P0/critical postmortem metadata、sections、follow-up items、SLA timestamps 和 timeline events。
2. 新增公开 `/status/incidents/[incidentId]` App Router 页面，无鉴权、无浏览器 storage、无 render-time network fetch。
3. 只对 `critical` 且存在 published postmortem 的 incident 渲染公开 postmortem；非 P0、缺失 postmortem 或未知 ID 返回 `notFound()`。
4. `/status` incident history 中对已发布的 P0 postmortem 提供详情链接；非 P0 incident 不显示 fake postmortem 链接。
5. Mermaid timeline 由 canonical timeline events 生成，页面同时展示 Mermaid 源码块和可读时间线列表，避免新增 Mermaid runtime dependency。
6. Postmortem 页面展示公开安全字段：what happened、impact、detection、mitigation、root cause、follow-ups、SLA due/published evidence、affected components。
7. Tests 覆盖 model lookup、24h SLA 计算、Mermaid generation/escaping, page public/no-auth rendering, unknown/non-P0 behavior, `/status` link discoverability, and no package dependency drift。

## Out Of Scope

- 管理员 Postmortem CRUD、审核工作流、数据库表、migration、OpenAPI、后端 admin route、CMS、外部 Statuspage/Uptime Kuma/Grafana/Prometheus 接入。
- 真实 incident automation、Provider Health polling、DingTalk webhook、on-call paging、自动 Status Page 发布。
- 修改 8.A.2 的 incident subscription fan-out、email/Webhook delivery、HMAC signing、retry、secret rotation。
- 退款/补偿执行、billing transaction、customer-success case management；页面只能公开 follow-up/compensation placeholder。
- 暴露内部 root-cause notes、operator private notes、raw provider payload、customer prompt、tenant ID、Webhook URL、email、JWT、API key、internal hostnames。
- 新 npm/runtime dependency 或 Mermaid client renderer；本 story 只提供 Mermaid-safe source contract and accessible timeline.

## Acceptance Criteria

1. `/status/incidents/{id}` is public and renders without reading `sessionStorage`, `localStorage`, cookies, JWT, API keys, or account state.
2. `/status/incidents/{id}` must not redirect unauthenticated visitors to `/auth/login`.
3. The page data is derived from the same typed public status model as `/status` and `/status/rss.xml`; no second incident fixture is introduced.
4. The public status model supports postmortem fields for exactly the data needed by the page: title, summary, published_at, publish_due_at, p0_declared_at, sections, timeline events, follow-ups, affected components, and Mermaid source.
5. A P0 public postmortem is represented by `severity="critical"` plus a published postmortem object.
6. Unknown incident IDs return `notFound()`.
7. Known non-critical incidents return `notFound()` and do not render fake postmortem content.
8. Critical incidents without a published postmortem return `notFound()` and do not overclaim completion.
9. The page displays incident ID, severity, status, started/resolved timestamps, affected component labels, postmortem due time, and published time.
10. The model exposes a deterministic helper proving `published_at <= publish_due_at` for published P0 postmortems.
11. Tests cover the 24h SLA boundary, including an overdue postmortem negative case.
12. The page displays sections for what happened, impact, detection, mitigation, root cause, and follow-up actions.
13. Follow-up actions include stable owner and status labels and do not imply compensation/refund execution unless explicitly represented as a public follow-up.
14. Mermaid timeline source is generated from canonical timeline events sorted by `occurred_at`.
15. Mermaid timeline labels are escaped/sanitized so quotes, brackets, pipes, angle brackets, or newlines cannot break the Mermaid source.
16. The page displays the Mermaid source in a `<pre>`/`<code>` block and an accessible text timeline list.
17. No Mermaid runtime/client dependency is added.
18. `/status` incident history links only published P0 postmortems to `/status/incidents/{id}`.
19. `/status` RSS item links may remain existing incident anchors; RSS behavior is not expanded in this story.
20. The public postmortem copy is operational and Trust-Forward, not a marketing landing page.
21. The page must not render raw Webhook URLs, emails, JWTs, API keys, tenant IDs, internal hostnames, provider payloads, or private operator notes.
22. No network fetch is required for initial postmortem render.
23. No new environment variable is required for local tests or development.
24. No npm/package dependency is added.
25. Focused tests pass before broader gates.
26. Local gates pass: focused web tests, `pnpm --filter @opticloud/web test`, `pnpm --filter @opticloud/web typecheck`, and `git diff --check`.
27. Implementation record includes post-implementation code review findings and fixes.
28. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done`.

## Tasks / Subtasks

- [x] T1: Extend public status/postmortem model (AC: 3-5, 10-15, 21, 24)
  - [x] Add typed postmortem, timeline, and follow-up contracts to `apps/web/src/lib/status-page.ts`.
  - [x] Add helpers for published P0 lookup, postmortem SLA compliance, sorted timeline events, and Mermaid source generation.
  - [x] Add model tests for lookup, non-P0 exclusion, missing postmortem exclusion, SLA boundary, ordering, and Mermaid escaping.

- [x] T2: Add public `/status/incidents/[incidentId]` page (AC: 1-2, 6-17, 20-23)
  - [x] Add a dynamic route page and injectable view component.
  - [x] Use `notFound()` for unknown, non-P0, and unpublished postmortem cases.
  - [x] Render public-safe postmortem sections, SLA metadata, Mermaid source, accessible timeline, and follow-up actions.
  - [x] Add page tests for public/no-auth/no-storage/no-fetch rendering and notFound cases.

- [x] T3: Link postmortems from `/status` (AC: 18-19)
  - [x] Add a Postmortem link only for incidents returned by published P0 lookup.
  - [x] Preserve RSS route behavior except for shared model type compatibility.
  - [x] Add status page tests for P0 link discoverability and non-P0 no-link behavior.

- [ ] T4: Review, gates, and GitHub sync (AC: 24-28)
  - [x] Confirm `apps/web/package.json` has no dependency change.
  - [x] Run focused tests before broader gates.
  - [x] Run post-implementation code review and fix findings.
  - [x] Record review findings and fixes in this story.
  - [x] Run local gates.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [ ] Mark story and sprint status `done` only after merge/sync.

## Dev Notes

### Service Boundary

- Implement only in `apps/web`, this story file, and `sprint-status.yaml` unless a test fixture requires a narrowly scoped update.
- Keep `apps/web/src/lib/status-page.ts` as the single source for public status, incidents, postmortem lookup, and Mermaid generation.
- The dynamic route should be `apps/web/src/app/status/incidents/[incidentId]/page.tsx`.
- Prefer an adjacent `PostmortemPageView.tsx` for testability, following the Story 8.A.1 `StatusPageView.tsx` pattern and avoiding non-Next exports from `page.tsx`.
- Use `notFound()` from `next/navigation` in the route layer, not in pure model helpers.

### Existing Patterns To Reuse

- Reuse `StatusPageView` layout language and public header/nav patterns.
- Use simple bordered sections and responsive grids; do not introduce nested cards or a marketing hero.
- Keep timestamps as explicit UTC strings rendered as absolute UTC times.
- Use existing `StatusCard`, `EmptyState`, and plain Tailwind classes; do not add a UI package dependency.

### Data Semantics

- Existing `PublicIncidentSeverity` values are `minor | major | critical`; map P0 to `critical` for this story instead of adding a parallel severity vocabulary.
- A published postmortem must have `published_at <= publish_due_at`; the helper should make overdue cases testable.
- `publish_due_at` should be exactly 24h after `p0_declared_at` for the included P0 fixture.
- Timeline events should include stable IDs and ISO UTC `occurred_at` values.
- Mermaid output should be generated only from canonical timeline events, not hand-authored separately.
- Public root cause may be "confirmed" or "pending", but must be public-safe and not expose private operator notes.

### Cross-Story Boundaries

- Story 3.12 owns static J3 incident contract validation and runbook skeletons.
- Story 8.A.1 owns `/status` and RSS.
- Story 8.A.2 owns authenticated incident notification preferences and fan-out request generation.
- Story 8.A.3 owns public P0 postmortem detail pages and Mermaid timeline source.
- Epic 9 owns quarterly P0 drills and broader observability governance.
- OP8 Status Page automation vendor/tooling remains deferred to v1.5; do not decide it here.

### Suggested Commands

```powershell
pnpm --filter @opticloud/web test -- status-page status/page.test.tsx postmortem
pnpm --filter @opticloud/web test
pnpm --filter @opticloud/web typecheck
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Public P0 Postmortem page satisfies FR O2 without authentication and without overclaiming automation, refunds, or delivery provider behavior.
- Mermaid timeline source is deterministic and generated from the same typed postmortem events rendered as the accessible text timeline.
- Unknown, non-P0, and unpublished postmortem cases do not render fake completion.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-a-3-24h-postmortem`.
- Baseline commit: `58555637f9eb10bae71f431b37e1c9932827afc2`.
- Story creation used Epic 8.A / PRD O2, Architecture O2 docs/runbooks boundary, Story 3.12 J3 static contract, Story 8.A.1 public status page, Story 8.A.2 incident subscription fan-out, current `apps/web` status model/page/tests, and `tools/incidents/j3_sre_incident.example.json`.
- Customization resolver script was absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base `bmad-create-story/customize.toml`, found no team/user overrides, and loaded no `project-context.md` files.
- Implementation started; story and sprint status moved to in-progress.
- RED confirmed before implementation: focused web tests failed because postmortem model helpers, `/status/incidents/[incidentId]`, and `/status` postmortem links did not exist.
- Focused web tests after implementation: `pnpm --filter @opticloud/web test -- status-page status/page.test.tsx "src/app/status/incidents/[incidentId]/page.test.tsx"` -> 12 passed.
- Type gate after implementation: `pnpm --filter @opticloud/web typecheck` -> passed.
- Web regression before review fix: `pnpm --filter @opticloud/web test` -> 185 passed.
- Diff-check before review fix: `git diff --check` -> passed.
- Next build after implementation: `pnpm -C apps/web build` -> passed.
- Post-implementation code review found 1 patch finding: SLA helper accepted drifted `publish_due_at` values later than exactly 24h after P0 declaration. Fixed with exact 24h due validation and regression tests.
- Focused web tests after review fix: `pnpm --filter @opticloud/web test -- status-page status/page.test.tsx "src/app/status/incidents/[incidentId]/page.test.tsx"` -> 12 passed.
- Type gate after review fix: `pnpm --filter @opticloud/web typecheck` -> passed.
- Final focused web tests: `pnpm --filter @opticloud/web test -- status-page status/page.test.tsx "src/app/status/incidents/[incidentId]/page.test.tsx"` -> 12 passed.
- Final web regression: `pnpm --filter @opticloud/web test` -> 185 passed.
- Final Next build: `pnpm -C apps/web build` -> passed.
- Final type gate: `pnpm --filter @opticloud/web typecheck` -> passed after rerun. One parallel attempt failed because `next build` concurrently regenerated `.next/types`; rerunning typecheck after build completed passed.
- Final diff-check: `git diff --check` -> passed.
- Story and sprint status moved to `code-review` after local gates; final `done` remains gated on GitHub CI, PR merge, remote branch cleanup, and local `main` sync.

### Completion Notes List

- Story created for public P0 24h Postmortem detail page.
- Completed 3 pre-implementation adversarial review rounds and revised the story after each round.
- Implemented shared public P0 postmortem model, SLA and Mermaid helpers, public dynamic postmortem page, accessible timeline, follow-up actions, and `/status` link gating.
- Post-implementation code review completed; patched exact 24h SLA due validation.

### File List

- `_bmad-output/stories/8-a-3-24h-postmortem.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/src/lib/status-page.ts`
- `apps/web/src/lib/status-page.test.ts`
- `apps/web/src/app/status/StatusPageView.tsx`
- `apps/web/src/app/status/page.test.tsx`
- `apps/web/src/app/status/incidents/[incidentId]/page.tsx`
- `apps/web/src/app/status/incidents/[incidentId]/PostmortemPageView.tsx`
- `apps/web/src/app/status/incidents/[incidentId]/page.test.tsx`

## Change Log

- 2026-06-02 - Story created for public P0 24h Postmortem page.
- 2026-06-02 - Completed 3 pre-implementation adversarial review rounds; story marked ready for development.
- 2026-06-02 - Implementation started; story and sprint status moved to in-progress.
- 2026-06-02 - Implemented public P0 postmortem model, `/status/incidents/[incidentId]`, Mermaid source generation, accessible timeline, status-page postmortem links, focused tests, and typecheck.
- 2026-06-02 - Completed post-implementation code review; fixed exact 24h SLA due validation and reran focused tests/typecheck.
- 2026-06-02 - Final focused tests, full web tests, Next build, typecheck, and diff-check passed; story moved to code-review pending GitHub sync.

## Post-Implementation Code Review

### Review Layers

- Blind Hunter: reviewed raw diff for public route behavior, data exposure, dependency drift, and link gating.
- Edge Case Hunter: reviewed unknown/non-P0/unpublished paths, SLA boundary, Mermaid label safety, and Next build behavior.
- Acceptance Auditor: checked implementation against AC 1-28 in this story.

### Findings And Fixes

1. [Review][Patch][Fixed] `isPostmortemPublishedWithinSla` only checked `published_at <= publish_due_at`; if future data drifted `publish_due_at` beyond exactly 24h after `p0_declared_at`, the helper could falsely report a compliant 24h postmortem.
   - Fix: added `isPostmortemDueExactly24h`, required it inside `isPostmortemPublishedWithinSla`, and added negative regression coverage for drifted `publish_due_at`.

### Review Result

- Decision-needed: 0
- Patch findings: 1 fixed
- Deferred: 0
- Dismissed: 0

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary, Product Scope, And Automation Drift

Findings:

1. FR O2 says administrators can publish 24h Postmortem, but adding admin CRUD/database/workflow now would exceed the current web/static status architecture and OP8 deferred automation boundary.
2. Story 3.12 already owns the static J3 skeleton; copying its validator/manifest into web would create two sources of truth.
3. The story can accidentally re-open 8.A.2 scope by notifying subscribers or claiming Webhook delivery.
4. PRD Journey 3 mentions refunds/compensation, but billing/customer-success execution is not part of public postmortem rendering.
5. The page must stay public and not inherit Console auth/session behavior.

Revisions applied:

- Scoped implementation to `apps/web` typed public model and public dynamic route only.
- Added explicit out-of-scope for admin CRUD, DB, monitoring automation, delivery providers, and compensation execution.
- Required public/no-auth/no-storage/no-fetch tests.
- Defined Story 3.12 as static contract input only, not a runtime dependency.

### Round 2 - Data Consistency, SLA, And Mermaid Drift

Findings:

1. `/status`, RSS, and postmortem pages could drift if postmortem data is added as a separate fixture.
2. P0 vs existing `minor|major|critical` severity vocabulary needs a single mapping.
3. 24h SLA can become marketing copy unless `published_at <= publish_due_at` is testable.
4. Mermaid timeline can drift from the human-readable timeline if authored separately.
5. Mermaid labels can break rendering if incident text contains quotes, brackets, pipes, angle brackets, or newlines.

Revisions applied:

- Required one shared typed public status model and published-P0 lookup helpers.
- Mapped P0 to existing `severity="critical"` plus a published postmortem object.
- Added deterministic SLA helper and overdue negative test requirement.
- Required Mermaid source and accessible timeline to be generated from the same sorted timeline events.
- Added Mermaid label sanitization/escaping AC.

### Round 3 - Edge Cases, Dependency Consistency, And Closure

Findings:

1. Unknown IDs, non-P0 incidents, and critical incidents without published postmortems must not render fake postmortem completion.
2. Adding a Mermaid renderer package would violate the narrow story and create dependency drift.
3. Next `page.tsx` cannot export arbitrary testing helpers without risking build failure, as seen in Story 8.A.1.
4. `/status` should link to postmortems only when a real published P0 postmortem exists.
5. Story completion must not be marked `done` before post-review, local gates, GitHub CI, merge, remote branch deletion, and local main sync.

Revisions applied:

- Added `notFound()` behavior for unknown, non-P0, and unpublished cases.
- Required no new package dependency and Mermaid source-only rendering.
- Required adjacent injectable view component instead of extra `page.tsx` exports.
- Added `/status` link gating AC and tests.
- Added Definition of Done and task gates matching the user's required lifecycle.
