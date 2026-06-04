---
story_key: 8-c-6-provider-console-tier3
epic_num: 8
story_num: C.6
epic_name: Teaching + Provider Routing + Legal + Algorithm Library
status: code-review
baseline_commit: b1766cdce0f213ad3be6d7f5400c0d5a3185d119
priority: High
type: Provider Console Tier 3 operational closure
created_by: bmad-create-story
created_at: 2026-06-04
sources:
  - _bmad-output/planning/epics.md (Epic 8.C / Story 8.C.6 brief)
  - _bmad-output/planning/prd.md (Provider Console complete version excluded from v1; O9 provider routing history)
  - _bmad-output/planning/architecture.md (Console frontend stack; Provider routing/audit table context)
  - _bmad-output/planning/ux-design-specification.md (O4 Provider Console UX; UX-DR1 ProviderRoutingHistory)
  - _bmad-output/stories/7-b-9-provider-console-tier3.md
  - _bmad-output/stories/8-c-2-provider-routing-history.md
  - apps/web/src/app/console/providers/page.tsx
  - apps/web/src/app/console/providers/page.test.tsx
  - apps/web/src/app/console/routing-history/page.tsx
  - apps/web/src/app/console/routing-history/page.test.tsx
  - apps/web/src/lib/api.ts
  - apps/web/src/lib/provider-console.test.ts
  - apps/web/src/lib/api-optimization.test.ts
---

# Story 8.C.6 - Provider Console Tier 3

Status: code-review

## Story

**作为** Provider 运营人员或内部 Provider success/SRE 人员，  
**我希望** 现有 `/console/providers` 在只读聚合数据之上给出 Tier 3 operational overview、跨 section 风险提示和安全的 Routing History handoff，  
**从而** 在不新增 Provider ownership、凭据桥接、后端聚合、写操作或敏感数据展示的前提下，能从 Provider Marketplace 面板闭环到单次 optimization routing history 排查。

## Context

Story 7.B.9 已交付 `/console/providers`：它是 Provider Marketplace v2 的只读聚合页面，消费 capability-registry 现有 GET 合同，要求显式 `provider_id`，可选 `tenant_id`、`application_id`、`period_month`，并展示 application、route-share、KPI、revenue/payout、version updates 和 monthly revenue-share batches。它明确排除了完整 8.C.6 Provider Console Tier 3、Provider ownership/auth、Command Palette、ConsoleSearch、Grafana dashboard 和后端改动。

Story 8.C.2 已交付 `/console/routing-history`：它通过用户手动输入 solver API key 和 optimization ID 查询 public-safe `routing_history`，展示 primary route、executed route 和 fallback attempts。它明确不消费 capability-registry Provider Console 数据，也不把 auth-service JWT 当 solver API credential。

规划源对 8.C.6 只有 brief："Provider Console Tier 3 (v2)，详细 ACs 待展开"。因此本 story 的最小闭环必须建立在已交付页面之上：为 Provider Console 增加 Tier 3 operational closure，而不是重做 7.B.9 或 8.C.2，也不是开启完整公开 Provider 自助系统。

## Scope

1. 扩展现有 `/console/providers` 页面。
   - 增加 Tier 3 operational overview，基于已加载的安全 summary 数据派生 application、route-share、shadow KPI、revenue/payout、version updates、monthly batch 六个状态 band。
   - 增加 cross-section issue list，用于解释 partial failure、empty data 和 needs-attention 状态；当没有 open issue 时也显示明确的闭环状态，不隐藏已经成功加载的 section。
   - 增加 Routing History handoff，只把用户本次提交的显式 Provider context filters 作为 URL query context 传到 `/console/routing-history`；不传 API key、JWT、optimization ID、dashboard JSON、derived first-application fallback 或 raw metadata。
2. 扩展现有 `/console/routing-history` 页面。
   - 可读取 `provider_id` 等 handoff query context 并显示只读提示。
   - 不自动填充 API key 或 optimization ID，不自动调用 solver GET，不把 query context 写入 browser storage。
3. 保持所有数据源和凭据边界。
   - Provider Console 继续只使用 `sessionStorage.jwt_access` 调 capability-registry GET。
   - Routing History 继续要求用户手动输入 `sk-...` API key 和 optimization ID。
   - 不桥接 JWT/API key，不推断 provider ownership。
4. 增加 focused web tests 覆盖 Tier 3 overview、handoff、partial failure/empty closure、no-storage/no-sensitive rendering、routing-history query context。
5. 运行 post-implementation code review、local gates、GitHub sync，并且只在 CI/merge/branch cleanup/local main sync 后用单独状态同步提交标记 `done`。

## Out Of Scope

- 新后端 endpoint、capability-registry/solver-orchestrator schema 改动、OpenAPI regeneration、DB migration、worker、queue、Grafana/Prometheus/DataDog 集成。
- Provider public authentication、OAuth/SSO、provider ownership enforcement、workspace/provider binding、API gateway policy、permission model。
- Command Palette、ConsoleSearch、DataTable virtualization、TanStack Query/Zustand/RHF/Zod adoption、chart library、new npm dependency。
- 基于 `Date.now()` 的 freshness/SLA/stale 判定、生产流量健康分、自动 remediation、告警订阅或 incident workflow。
- 任何 write/internal route：rollout advance/pause/cancel、version review/update mutation、payout/monthly batch mutation、application submit/update。
- 把 Provider Console JWT 用作 solver API key，或把 solver API key/optimization ID/JWT 存入 localStorage/sessionStorage/query string。
- 展示 raw metadata、cosign bundle、evaluation_profile、raw stage history、raw KPI samples/datasets/evidence、raw payout/hook/billing payload、payment refs、bank/tax fields、API key/prefix/hash、internal headers、raw `_system` 或 customer request/solution payload。
- 声称 route-share 是生产流量、KPI 是生产成功率、revenue/payout 是银行打款、monthly batch 是已支付/开票/纳税、version approval 是 live catalog deployment。

## Acceptance Criteria

1. `/console/providers` remains the only Provider Console route touched by this story; no new Provider Console route is added.
2. `/console/providers` still redirects to `/auth/login` when `sessionStorage.jwt_access` is missing.
3. `/console/providers` still requires a non-empty explicit `Provider ID` before loading and does not infer "my provider" from login identity.
4. Existing Provider Console API calls remain read-only and unchanged: `listProviderApplications`, `getProviderRouteShareDashboard`, `getProviderKpiDashboard`, `getProviderRevenuePayoutDashboard`, `listProviderVersionUpdates`, `listProviderMonthlyRevenueShareBatches`.
5. No Provider Console request body, `X-Internal-Service-Auth`, `If-Match`, `Idempotency-Key`, billing header, solver API key, or optimization ID is sent by `/console/providers`.
6. Provider Console continues to store no provider filters, dashboard data, API keys, JWT copies, routing context, optimization IDs, or raw payloads in `localStorage` or `sessionStorage`; it only reads the existing JWT.
7. Provider Console tracks the last submitted valid provider context separately from unsent form edits, so Tier 3 overview and handoff describe the data that was actually requested.
8. Tier 3 operational overview renders six status bands: Application, Route Share, Shadow KPI, Revenue/Payout, Version Updates, Monthly Batches.
9. Each status band is derived only from safe fields already rendered or permitted by 7.B.9: status counts, totals, aggregate metrics, threshold violation counts, stable IDs, lifecycle status, period/month, and safe timestamps.
10. Status bands use explicit text labels and not color alone; labels must distinguish exactly these state families: `ready`, `watch`, `blocked/error`, `empty`, and `not loaded`.
11. Application band treats accepted/submitted/under_review/rejected/missing/error distinctly and does not imply identity-bound ownership.
12. Route Share band labels staged rollout data as declared rollout stage/share, not observed production traffic.
13. Shadow KPI band labels metrics as shadow validation and surfaces threshold violations or failed/cancelled runs as watch/blocking signals without showing raw samples/datasets/evidence.
14. Revenue/Payout band labels the data as read-model projection and surfaces pending/held/paid/voided counts without implying bank settlement, invoice, tax or payment completion.
15. Version Updates band labels review lifecycle and does not imply deployment/live catalog mutation.
16. Monthly Batches band labels calculation lifecycle and does not imply payment, invoice, tax or settlement completion.
17. Cross-section issue list appears after a load, includes partial failure entries when one or more section reads fail, and shows an explicit no-open-issues state when no issue is derived.
18. Cross-section issue list includes empty-state entries when all data for a section is absent after a successful load, without treating every empty section as a fatal page error.
19. Cross-section issue list never includes raw backend payload JSON, stack traces, internal headers, raw metadata, cosign bundles, API keys, JWTs, optimization IDs, payment refs, bank/tax fields, or raw `_system`.
20. A failed section must not hide successful sections, the Tier 3 overview, or the Routing History handoff.
21. Routing History handoff appears only after a Provider Console load attempt with a non-empty submitted provider ID.
22. Handoff link target is `/console/routing-history` with URL query context containing `provider_id` and optional submitted `tenant_id`, `application_id`, and `period_month` only, encoded through `URLSearchParams`.
23. Handoff URL never contains JWT, API key, API-key prefix/hash, optimization ID, raw dashboard JSON, raw metadata, payment refs, billing refs, customer identifiers beyond explicitly loaded filters, or internal auth headers.
24. Handoff copy states that Routing History still requires manual solver API key and optimization ID entry.
25. `/console/routing-history` reads handoff query context and displays it as a read-only context hint.
26. `/console/routing-history` does not auto-fill API key or optimization ID from query context.
27. `/console/routing-history` does not call `getOptimization()` merely because handoff query context exists.
28. `/console/routing-history` does not write handoff query context to `localStorage` or `sessionStorage`.
29. Existing routing history behavior from 8.C.2 remains unchanged: manual API key + optimization ID query, no storage writes, public-safe fields only, completed and non-completed status support.
30. Layout remains dense Console UI with stable controls/tables on desktop/mobile; dynamic status labels and issue text must wrap without overlapping.
31. Implementation introduces no new npm dependency and no new shared UI dependency.
32. No files under `apps/capability-registry/**`, `apps/solver-orchestrator/**`, backend services, migrations, OpenAPI generated artifacts, or infra manifests are modified.
33. Provider Console page tests cover operational overview success state, handoff URL/context, partial failure issue list, empty/no-data issue list, no storage writes, no sensitive rendering, and last-loaded-context stability.
34. Routing History page tests cover provider handoff context rendering, no auto-query, no input autofill, no storage writes, and existing manual query behavior.
35. Existing Provider Console API client tests remain valid and continue to prove read-only URL/query/auth/no-body behavior.
36. Tests or review evidence confirm no `package.json`, lockfile, backend, migration, OpenAPI generated artifact, or infra manifest changes were introduced.
37. Local gates pass: focused Provider Console/Routing History page tests, Provider Console API client tests, optimization API client tests, web typecheck, and `git diff --check`.
38. Post-implementation code review is completed and findings are fixed or explicitly documented in this story.
39. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done` through a separate status-sync commit.

## Tasks / Subtasks

- [x] T1: Add Provider Console Tier 3 operational overview (AC: 1-20, 30-33)
  - [x] Track last submitted valid provider context independently from draft form fields.
  - [x] Derive six safe status bands from already-loaded Provider Console data/errors using the story-defined state rules.
  - [x] Render cross-section issues for partial failures and successful empty sections.
  - [x] Preserve all existing read-only, auth, partial-failure, empty-state and no-storage behavior.

- [x] T2: Add safe Routing History handoff (AC: 21-29, 34)
  - [x] Add `/console/providers` handoff link using only explicit submitted Provider context query fields.
  - [x] Add `/console/routing-history` read-only handoff context hint.
  - [x] Ensure query context does not auto-fill API key/optimization ID, trigger solver calls, or write storage.

- [x] T3: Add/update focused tests (AC: 33-37)
  - [x] Update Provider Console page tests for overview, issue list, handoff, sensitive-field and last-loaded-context behavior.
  - [x] Update Routing History page tests for handoff context and preserved manual query behavior, including `useSearchParams` mocking.
  - [x] Keep API client tests unchanged or strengthen them if needed.
  - [x] Verify no dependency, backend, migration, OpenAPI generated artifact, or infra manifest diff exists.

- [ ] T4: Review, gates, and GitHub sync (AC: 37-39)
  - [x] Run local quality gates and fix failures.
  - [x] Run post-implementation code review and fix/document findings.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [ ] Mark story and sprint status `done` only after merge/sync through a separate status-sync commit.

## Dev Notes

### Existing Frontend Facts

- `/console/providers` is a client component that currently reads only `sessionStorage.jwt_access`, redirects unauthenticated users to `/auth/login`, and uses local React state.
- The existing page loads five independent capability-registry reads with `Promise.allSettled()` and then loads version updates only when an application anchor exists.
- The existing page already renders safe summaries and explicitly avoids raw metadata/cosign/evaluation/payout/monthly internals.
- `/console/routing-history` is a client component that uses local React state for API key and optimization ID and only calls `getOptimization(apiKey, optimizationId)` after user action.
- `getOptimization()` uses solver API-key bearer auth, URL-encodes optimization ID, sends GET only, and sends no `Content-Type`, body, billing, internal auth or idempotency headers.

### Implementation Guardrails

- Keep the implementation in `apps/web/src/app/console/providers/page.tsx`, `apps/web/src/app/console/providers/page.test.tsx`, `apps/web/src/app/console/routing-history/page.tsx`, and `apps/web/src/app/console/routing-history/page.test.tsx` unless tests prove a narrower helper extraction is needed.
- Do not edit `apps/web/src/lib/api.ts` unless a test reveals a direct type gap; no new API client is expected.
- Use local helper functions for derived operational state. They must consume existing typed response shapes and not fetch.
- Derive overview from the last submitted valid context, not current unsent form draft, to avoid drift when a user edits filters after a load.
- Prefer table/list semantics for overview and issues so the layout stays dense and avoids decorative nested cards.
- The handoff URL may include only `provider_id`, `tenant_id`, `application_id`, and `period_month` when those values came from the submitted filter form. Do not include the first application selected as the version-update fallback unless the user explicitly typed that application ID.
- Build the handoff URL with `URLSearchParams` and trimmed submitted values. Empty optional values must be omitted rather than serialized as empty strings.
- The routing-history context hint must be informational only. It is not an auth bridge and cannot reduce the need for user-entered API key/optimization ID.
- If `useSearchParams()` is used in `/console/routing-history`, update its Vitest mock without weakening the existing `next/link` and manual-query tests.
- Do not modify root `package.json`, `pnpm-lock.yaml`, any service `package.json`, backend directories, migrations, generated OpenAPI files, or infra manifests.

### Operational State Rules

- Before any submitted load, every band is `not loaded`.
- If a section request rejects, that band is `blocked/error` and the issue list uses the same safe normalized user-facing error already used by the section error card.
- Application band: `ready` for `accepted`; `watch` for `submitted` or `under_review`; `blocked/error` for `rejected`; `empty` when no application row is returned and no application error exists.
- Route Share band: `ready` when `total_rollouts > 0` and at least one current rollout is active/completed; `watch` when rollouts exist but none are active/completed; `empty` when `total_rollouts === 0`.
- Shadow KPI band: `blocked/error` when any run status count for failed/cancelled is greater than 0 or any run metric has threshold violations; `ready` when total runs and samples are both greater than 0 with no violations; `empty` when total runs or samples are zero.
- Revenue/Payout band: `watch` when pending or held counts are greater than 0; `ready` when total entries are greater than 0 and all entries are paid; `empty` when total entries is zero; `blocked/error` when voided count is greater than 0.
- Version Updates band: `watch` when submitted/under_review/rejected rows exist; `ready` when at least one row exists and all visible rows are approved/cancelled/draft; `empty` when no rows exist and no version error exists.
- Monthly Batches band: `watch` when reviewed or draft batches exist; `ready` when approved/exported batches exist and no draft/reviewed/cancelled batches exist; `blocked/error` when cancelled batches exist; `empty` when no monthly batches exist.
- Status derivation must not use current wall-clock time, hidden metadata, raw timelines, raw payload counts, or fields not listed in this story.

### Data Semantics

- Route Share is declared rollout stage/share from Provider Marketplace rollout records, not live production traffic.
- Shadow KPI is shadow validation quality/performance, not production SLA.
- Revenue/Payout is a read-model projection, not settlement, payment, invoice or tax state.
- Version Updates are review lifecycle records, not deployment/live catalog mutation.
- Monthly Revenue Share Batches are calculation lifecycle records, not payment/export-to-bank/tax completion.
- Provider Console context is explicitly user-entered filter context, not identity-bound provider ownership.

### Review Constraints

- This story must pass exactly 3 pre-implementation adversarial review rounds before implementation.
- Each round must produce findings and story revisions before the next round starts.
- Do not move story or sprint status to `in-progress` until all 3 rounds pass.
- Do not mark story/sprint `done` before PR CI, merge, remote branch deletion, local main sync, and separate status-sync commit.

### Suggested Commands

```powershell
pnpm --filter @opticloud/web test -- src/app/console/providers/page.test.tsx src/app/console/routing-history/page.test.tsx src/lib/provider-console.test.ts src/lib/api-optimization.test.ts
pnpm --filter @opticloud/web typecheck
git diff --check
```

## Definition Of Done

- Story file has passed exactly 3 pre-implementation adversarial review rounds and revisions.
- Provider Console Tier 3 operational overview is present, safe, read-only and derived only from existing summary data.
- Routing History handoff is discoverable but does not bridge credentials, auto-query, store context or leak sensitive data.
- Existing 7.B.9 Provider Console and 8.C.2 Routing History behaviors remain compatible.
- No backend/API/dependency drift is introduced.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, local `main` sync, and separate status-sync closure.

## Story Review Log

### Round 1: Boundary, Ownership, And Closure Review

Findings fixed:

- Initial scope allowed "stale" handling without a source-of-truth threshold. That could lead to arbitrary `Date.now()` freshness logic and false operational alarms. Revised scope and out-of-scope boundaries to exclude time-based freshness/SLA/stale scoring in this story.
- Initial handoff wording allowed implementers to include the derived first application fallback in the Routing History URL. That would move registry-derived application identifiers into query context without explicit user intent. Revised scope, ACs, tasks, and Dev Notes so handoff uses only submitted form filters.
- Initial issue-list ACs covered failures and empty states but did not define the healthy/no-issue closure. Revised AC 17 to require an explicit no-open-issues state after a load.
- Initial context wording used "loaded" ambiguously, which could drift between loaded backend data and unsent form edits. Revised to "last submitted valid provider context" across ACs and Dev Notes.

Status: PASS after fixes.

### Round 2: Data Consistency, Drift, And Determinism Review

Findings fixed:

- Initial ACs required state bands but did not define deterministic state rules. That would allow inconsistent labels across implementation and tests. Added explicit state-family definitions and section-specific derivation rules.
- AC 21 still used "loaded provider ID" after Round 1 changed context semantics. Revised to "submitted provider ID" so handoff visibility matches the last submitted context.
- T1 still asked for "last loaded provider context", which contradicted AC 7. Revised the task to track the last submitted valid context.
- Handoff query serialization did not require structured encoding. Added `URLSearchParams` and trimmed/omit-empty requirements to avoid malformed URLs or empty query drift.
- Version, revenue and monthly state semantics could have implied production deployment or payment health. Added rules that keep these as lifecycle/projection signals only.

Status: PASS after fixes.

### Round 3: Dependency, Test, And Closure Review

Findings fixed:

- Initial closure relied on broad "no new dependency" wording but did not require evidence that package files stayed untouched. Added AC 36 and T3 verification for package/lockfile no-diff.
- Initial no-backend boundary was present, but test/review closure did not require checking backend, migration, OpenAPI or infra diffs. Added explicit no-diff evidence to AC 36 and T3.
- Routing History context rendering will likely use `useSearchParams()`, but the existing routing-history page test only mocks `next/link`. Added a task and guardrail to mock `useSearchParams` without weakening existing manual-query coverage.
- The story remained `draft` after all review rounds, which would block the dev-story workflow and create status drift. Revised frontmatter and visible Status to `ready-for-dev`.
- T4 AC references lagged after adding the no-diff closure AC. Updated T3/T4 AC mappings.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-c-6-provider-console-tier3`.
- Baseline commit: `b1766cdce0f213ad3be6d7f5400c0d5a3185d119`.
- Story creation analyzed 7.B.9 Provider Console boundary, 8.C.2 Routing History credential boundary, Epic 8.C.6 brief, UX O4/ProviderRoutingHistory references, and existing `apps/web` page/API tests.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base skill instructions and project config.
- 2026-06-04 - Moved story to in-progress after exactly three pre-implementation adversarial review rounds.
- 2026-06-04 - RED confirmed before implementation: focused Provider Console/Routing History tests failed because Tier 3 operational overview, handoff link and routing-history context hint did not exist.
- 2026-06-04 - Implemented Provider Console operational status bands, open-issue list, submitted-context handoff URL, Routing History read-only handoff context hint, and focused tests.
- 2026-06-04 - Focused web gates passed: `pnpm --filter @opticloud/web test -- src/app/console/providers/page.test.tsx src/app/console/routing-history/page.test.tsx src/lib/provider-console.test.ts src/lib/api-optimization.test.ts` -> 18 passed.
- 2026-06-04 - Web typecheck passed: `pnpm --filter @opticloud/web typecheck`.
- 2026-06-04 - Whitespace gate passed: `git diff --check`.
- 2026-06-04 - Diff scope checked: no package/lockfile, backend, migration, OpenAPI generated artifact, or infra manifest changes.
- 2026-06-04 - Full web regression passed before review fixes: `pnpm --filter @opticloud/web test` -> 234 passed.
- 2026-06-04 - Post-implementation code review found 3 patch findings: story frontmatter status drift, `useSearchParams()` Suspense boundary risk, and stale Provider Console data during new submitted loads.
- 2026-06-04 - Review fixes applied: frontmatter set to in-progress, Routing History content wrapped in Suspense, Provider Console clears prior data on new submitted context with regression coverage.
- 2026-06-04 - Final local gates after review fixes passed: focused web tests 19 passed, full web regression 235 passed, web typecheck passed, `git diff --check` passed.
- 2026-06-04 - Story and sprint status moved to code-review pending GitHub sync.

### Completion Notes List

- Initial story created.
- Round 1 pre-implementation review completed and story revised.
- Round 2 pre-implementation review completed and story revised.
- Round 3 pre-implementation review completed and story revised; story is ready for development.
- Story moved to in-progress after exactly three pre-implementation adversarial review rounds.
- Provider Console Tier 3 operational overview and safe Routing History handoff implemented.
- Routing History page now displays Provider Console query context as read-only guidance without auto-querying or filling credentials.
- Post-implementation code review completed; all patch findings fixed.
- Focused and full local gates passed; GitHub sync remains.

### File List

- _bmad-output/stories/8-c-6-provider-console-tier3.md
- _bmad-output/stories/sprint-status.yaml
- apps/web/src/app/console/providers/page.tsx
- apps/web/src/app/console/providers/page.test.tsx
- apps/web/src/app/console/routing-history/page.tsx
- apps/web/src/app/console/routing-history/page.test.tsx

## Change Log

- 2026-06-04 - Initial story created for Provider Console Tier 3 operational closure.
- 2026-06-04 - Completed 3 pre-implementation adversarial review rounds; story marked ready for development.
- 2026-06-04 - Story status moved to in-progress for implementation.
- 2026-06-04 - Implemented Provider Console Tier 3 operational overview, safe Routing History handoff, routing-history context hint, and focused tests.
- 2026-06-04 - Completed post-implementation code review, fixed 3 patch findings, and moved story to code-review pending GitHub sync.

## Post-Implementation Code Review (AI)

Outcome: Changes requested, then fixed.

Findings fixed:

- [x] Story frontmatter remained `status: ready-for-dev` while visible story status and sprint status were in-progress/code-review. Fixed frontmatter to follow the active story lifecycle through `code-review`.
- [x] `/console/routing-history` introduced `useSearchParams()` directly in the page component. Next.js App Router search-param hooks can require a Suspense boundary for static/CSR bailout behavior. Fixed by wrapping the content component in `Suspense` with a lightweight loading fallback, preserving existing manual query behavior and tests.
- [x] `/console/providers` updated the submitted Provider context before clearing old dashboard data, so a new load could temporarily show a new handoff context beside stale prior Provider data. Fixed by clearing `data` to `emptyData` at the start of each valid submitted load and added regression coverage.

Status: PASS after fixes.
