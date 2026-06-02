---
story_key: 7-b-9-provider-console-tier3
baseline_commit: 61abd7cdfb2d75188d6d4bd6ac0fde94209fe08e
epic_num: 7
story_num: B.9
epic_name: Provider Marketplace v2
status: code-review
priority: High
type: Provider Console Tier 3 read-only aggregate surface
created_by: bmad-create-story
created_at: 2026-06-02
sources:
  - _bmad-output/planning/epics.md (Epic 7.B / Provider Marketplace v2; Story 7.B.9-13 v2 Console UX)
  - _bmad-output/planning/prd.md (FR P4-P8; Provider Console excluded from v1)
  - _bmad-output/planning/architecture.md (Console frontend stack; capability-registry service)
  - _bmad-output/planning/ux-design-specification.md (Provider Console UX; Tier 3 ProviderRoutingHistory)
  - _bmad-output/stories/7-b-4-route-share-dashboard.md
  - _bmad-output/stories/7-b-5-provider-kpi-dashboard.md
  - _bmad-output/stories/7-b-6-revenue-payout.md
  - _bmad-output/stories/7-b-7-version-management.md
  - _bmad-output/stories/7-b-8-monthly-revenue-share.md
  - apps/web/src/lib/api.ts
  - apps/web/src/app/console/billing/invoices/page.tsx
  - apps/web/src/app/console/data-exports/page.tsx
  - apps/capability-registry/src/capability_registry/routes.py
  - apps/capability-registry/src/capability_registry/schemas.py
---

# Story 7.B.9 - Provider Console Tier 3

Status: code-review

## Story

**作为** 外部 Provider 或内部 Provider 运营人员，
**我希望** 在 Console 中用一个只读页面聚合 Provider application、route-share、KPI、revenue/payout、version update 和 monthly revenue-share batch 状态，
**从而** 在不引入 public Provider auth、真实结算、路由变更或新后台服务的前提下，能用已有 7.B.4-7.B.8 合同完成 Provider Marketplace v2 的可视化闭环。

## Context

7.B.4-7.B.8 已经在 `apps/capability-registry` 中建立了 Provider Marketplace v2 的安全只读合同：route-share dashboard、KPI dashboard、revenue/pending payout dashboard、version update request list、monthly revenue-share batch list。规划文档没有为 7.B.9 展开详细 AC，只说明 Story 7.B.9-13 属于 "v2 Console UX + Revenue-Share Service + 学界 onboarding tier 1-3"。

本 story 的最小闭环是 `apps/web` 的 Provider Console 聚合页面。它消费现有 capability-registry GET 合同，不新增后端端点，不调用任何 internal write route，不创建 `apps/revenue-share-service`，也不声称已经完成公开 Provider 自助身份/所有权体系。8.C.6 仍保留为后续 Observability/Provider routing history 的更完整 Tier 3 扩展，不在本 story 重复实现。

## Scope

1. 在 `apps/web/src/lib/api.ts` 增加 `NEXT_PUBLIC_CAPABILITY_REGISTRY_URL` 和 Provider Console 只读 client。
2. 新增 `/console/providers` 页面：
   - 使用当前 Console JWT 作为登录门槛。
   - 用户显式输入 `provider_id`；可选输入 `tenant_id`, `application_id`, `period_month`。
   - 聚合 application、route-share、KPI、revenue payout、version updates、monthly batches。
3. 页面采用密集、克制、工作台式布局，复用 `StatusCard` / `EmptyState` / `LoadingShimmer`，不引入新状态库、图表库或 UI 依赖。
4. 增加 web Vitest 覆盖 API client 和页面状态。
5. 更新至少一个现有 Console 导航入口，使 Provider Console 可发现。

## Out Of Scope

- Provider public authentication、OAuth flow、provider ownership enforcement、API gateway policy、SSO、workspace ownership。
- 修改 `apps/capability-registry` 后端、OpenAPI schema、数据库表、CI job、solver-orchestrator、billing-service、revenue-share-service。
- 调用任何 write/internal endpoint：provider application submit、evaluation create、shadow sample write、rollout advance/pause/cancel、payout upsert、monthly batch upsert/status patch、version update PUT/PATCH。
- 银行/税务/发票/支付/结算文件、付款重试、争议处理、真实月结导出、账本读取。
- 暴露 raw metadata、cosign bundle、raw hook/payout metadata、raw billing payload、credentials、API keys、OAuth tokens、bank/tax/payment fields、customer routing payloads、raw sample/dataset/request/response bodies。
- 用 7.B.9 实现 8.C.6 Provider routing history、完整 ProviderRoutingHistory 组件、Grafana dashboard、Command Palette、ConsoleSearch。

## Acceptance Criteria

1. `apps/web/src/lib/api.ts` defines `CAPABILITY_REGISTRY_URL = process.env.NEXT_PUBLIC_CAPABILITY_REGISTRY_URL ?? "http://localhost:8006"`。
2. Provider Console API client functions are read-only and use only GET endpoints:
   - `listProviderApplications`
   - `getProviderRouteShareDashboard`
   - `getProviderKpiDashboard`
   - `getProviderRevenuePayoutDashboard`
   - `listProviderVersionUpdates`
   - `listProviderMonthlyRevenueShareBatches`
3. All Provider Console client functions accept the current JWT and send `Authorization: Bearer <jwt>` plus existing Accept-Language behavior, even though capability-registry GET routes are service-side read contracts today.
4. Query building preserves exact backend parameter names: `tenant_id`, `requested_provider_id`, `application_id` path segment where needed, `period_month`, `status`, `currency`, `from`, `to`。
5. Client request bodies are never sent for Provider Console GET calls, and no `X-Internal-Service-Auth`, `If-Match`, or idempotency key is sent by this page.
6. `/console/providers` redirects to `/auth/login` when `sessionStorage.jwt_access` is missing.
7. Page does not store provider IDs, tenant IDs, application IDs, API keys, internal secrets, downloaded payloads, or dashboard responses in `localStorage` or `sessionStorage`; it only reads the existing JWT.
8. Page requires a non-empty explicit `provider_id` before loading. It must not guess "my provider" from login identity because no provider ownership service exists.
9. With optional `tenant_id`, every Provider Console client call includes the same exact tenant filter; there is no client-side global fallback merge.
10. With optional `period_month`, revenue payout and monthly batch calls include the same period filter; other calls are unaffected.
11. If `application_id` is omitted, the page selects the first matching application returned by `listProviderApplications` only for version-update listing. If no matching application exists, version updates show an empty state rather than an error.
12. The page displays application summary using safe fields only: application ID, requested provider ID, display name, organization, provider kind, status, submitted/updated dates, and scope source.
13. The page displays route-share summary using `status_counts`, `total_rollouts`, `highest_current_stage_percent`, current rollout rows, and timeline count; it must not show raw `stage_history` or raw evidence.
14. The page displays KPI summary using aggregate counts/rates, p95 latency ratio, threshold violations, run status counts, and timeline count; it must not show raw samples, datasets, metadata, or evidence refs.
15. The page displays revenue/payout summary using status counts, currency totals, period summaries, and stable entry IDs; it must not show raw payout metadata, hook metadata, raw billing refs beyond stable identifiers, payment refs, paid-at timestamps, bank/tax fields, or PII.
16. The page displays version update rows using stable fields only: version update ID, current/proposed version, change kind, status, submitted/reviewed dates, and review notes reference. It must not render `cosign_bundle` or `metadata`.
17. The page displays monthly batch rows using batch ID, period, status, entry/provider counts, checksum suffix, totals, and lifecycle refs. It must not render metadata, raw snapshot JSON, payment refs, or settlement fields.
18. Dashboard sections load independently enough that one failed read (for example revenue payout) does not hide successfully loaded route/KPI/application data.
19. Empty results render explicit empty states for route-share, KPI, revenue payout, version updates, and monthly batches.
20. Loading states are visible and stable; dynamic content must not resize form controls or overlap on desktop/mobile.
21. Existing `/console/billing/invoices` navigation includes a discoverable link to `/console/providers`.
22. The implementation introduces no new npm dependency and no new shared UI package dependency.
23. Tests cover Provider Console API client URL/query/auth behavior and confirm no request body/internal write headers are sent.
24. Tests cover `/console/providers` redirect, successful aggregate rendering, omitted-application version empty state, partial failure rendering, and no storage writes.
25. Existing web tests continue to pass.
26. Local gates pass: `pnpm --filter @opticloud/web test`, `pnpm --filter @opticloud/web typecheck`, and `git diff --check`.
27. Implementation record includes post-implementation code review findings and fixes.
28. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done`.

## Tasks / Subtasks

- [x] T1: Add Provider Console API client (AC: 1-5, 23)
  - [x] Add typed response interfaces for the consumed capability-registry contracts.
  - [x] Add query builder and read-only client functions.
  - [x] Add API client tests for URL/query/auth/no-body/no-internal-write headers.

- [x] T2: Add `/console/providers` page (AC: 6-20, 24)
  - [x] Add login gate and explicit provider/tenant/application/period filters.
  - [x] Load Provider Console sections with partial-failure handling.
  - [x] Render safe summary tables and empty/loading/error states.
  - [x] Add page tests for redirect, success, empty version updates, partial failure, and no storage writes.

- [x] T3: Console discoverability and polish (AC: 20-22)
  - [x] Add `/console/providers` link to existing Console navigation.
  - [x] Verify no new dependencies and layout stays utilitarian/dense.

- [ ] T4: Review, gates, and GitHub sync (AC: 25-28)
  - [x] Run post-implementation code review and fix findings.
  - [x] Record code review findings and fixes in `Post-Implementation Code Review`.
  - [x] Run local gates after fixes.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [ ] Mark story and sprint status `done` only after merge/sync.

## Dev Notes

### Service Boundary

- Implement in `apps/web`, story/status files, and possibly existing Console nav pages only.
- Do not edit `apps/capability-registry` or regenerate capability-registry OpenAPI in this story.
- Treat capability-registry GET routes as existing contracts; this page is a Console adapter, not a backend capability expansion.
- Provider ownership is unresolved. Therefore the page must present explicit provider filters and avoid "my provider" wording.

### Existing Patterns To Reuse

- Use `apps/web/src/lib/api.ts` typed request patterns and `OptiCloudClientError`.
- Use `sessionStorage.getItem("jwt_access")` + `router.push("/auth/login")` like billing invoices and data export pages.
- Use local component state, not Zustand/Jotai/RTK Query.
- Use existing `StatusCard`, `EmptyState`, `LoadingShimmer`, and simple tables. Do not add chart libraries.
- Keep Console layout consistent with `/console/billing/invoices`: header/nav, muted band title, constrained max width, dense panels.

### Data Semantics

- Route share is declared rollout stage share, not observed production traffic.
- KPI success rate is shadow validation success rate, not production success rate.
- Pending payout is a read-model projection from payout entries, not bank settlement.
- Monthly batch `approved`/`exported` means calculation lifecycle only, not paid/taxed/invoiced.
- Version update approval means review approval only, not deployment or live catalog mutation.

### Previous Story Intelligence

- 7.B.4-7.B.8 repeatedly fixed exact tenant scope/no global fallback for provider-owned dashboards.
- 7.B.4-7.B.6 repeatedly removed raw metadata/evidence exposure from Provider-facing surfaces.
- 7.B.6-7.B.8 established financial projections must remain reference-only and not imply settlement.
- 7.B.7 established version approvals do not mutate live catalog.
- 7.B.8 clarified Provider Console was out of scope for monthly batch; this story is the first narrow Console adapter over the existing contracts.

### Suggested Commands

```powershell
pnpm --filter @opticloud/web test
pnpm --filter @opticloud/web typecheck
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Provider Console page satisfies FR P4-P8 as a safe read-only frontend aggregate over existing capability-registry contracts.
- Existing backend Provider Marketplace behavior remains unchanged.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/7-b-9-provider-console-tier3`.
- Baseline commit: `61abd7cdfb2d75188d6d4bd6ac0fde94209fe08e`.
- Story creation used local context from PRD/Architecture/UX docs, 7.B.4-7.B.8 completed stories, `apps/web` Console pages/tests, and capability-registry route/schema contracts.
- Implementation started; story and sprint status moved to in-progress.
- RED confirmed before implementation: focused Provider Console tests failed because the API client functions and `/console/providers` page did not exist.
- Focused Provider Console tests after implementation/review fixes: `pnpm --filter @opticloud/web test -- provider-console.test.ts providers/page.test.tsx billing/invoices/page.test.tsx` -> 17 passed.
- Full web regression gate after review fixes: `pnpm --filter @opticloud/web test` -> 172 passed.
- Type gate after review fixes: `pnpm --filter @opticloud/web typecheck` -> passed.
- Whitespace gate after review fixes: `git diff --check` -> passed.
- Post-implementation code review found 3 patch findings: implicit CNY filtering from period-only UI input, missing revenue `period_summaries` display, and monthly checksum prefix display instead of suffix.
- Story and sprint status moved to `code-review` after local review and gates; final `done` remains gated on GitHub CI, PR merge, remote branch cleanup, and local `main` sync.

### Completion Notes List

- Story created for Provider Console Tier 3 read-only aggregate surface.
- Completed 3 pre-implementation adversarial review rounds and revised the story after each round.
- Added Provider Console read-only capability-registry API client functions and tests for exact URL/query/auth/no-body/no-internal-write headers.
- Added `/console/providers` read-only aggregate page with explicit provider/tenant/application/month filters, JWT login gate, safe field rendering, partial-failure handling, and empty/loading/error states.
- Added Provider Console discoverability from the existing billing invoices Console navigation.
- Post-review fixes removed implicit CNY filtering, added revenue period-summary rendering, and changed monthly checksum display to a suffix.
- Local web tests, typecheck, and diff check pass; GitHub sync remains pending.

### File List

- `_bmad-output/stories/7-b-9-provider-console-tier3.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/provider-console.test.ts`
- `apps/web/src/app/console/providers/page.tsx`
- `apps/web/src/app/console/providers/page.test.tsx`
- `apps/web/src/app/console/billing/invoices/page.tsx`

## Change Log

- 2026-06-02 - Story created for Provider Console Tier 3 read-only aggregate surface.
- 2026-06-02 - Completed 3 pre-implementation adversarial review rounds; story marked ready for development.
- 2026-06-02 - Implementation started; story and sprint status moved to in-progress.
- 2026-06-02 - Implemented Provider Console API client, `/console/providers` page, navigation entry, and focused tests.
- 2026-06-02 - Completed post-implementation code review, fixed 3 patch findings, and reran local gates; story moved to code-review pending GitHub sync.

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary, Ownership, And Product Fit Review

Findings:

1. "Provider Console" could be misread as public Provider login, OAuth, ownership enforcement, or API gateway policy.
2. "Tier 3" could invite large UX scope such as Command Palette, ConsoleSearch, ProviderRoutingHistory, or full 8.C.6 implementation.
3. The story key overlaps with 8.C.6 Provider Console Tier 3, so scope needs to avoid duplication.
4. Rendering "own provider" could falsely imply identity-bound ownership in the current architecture.
5. Console actions could drift into rollout advance, version update status PATCH, monthly batch approve/export, or payout mutation.
6. A Provider Console could accidentally show raw evidence, metadata, cosign bundles, payment fields, or raw billing refs.
7. Financial terms could imply real settlement, tax, invoice, or transfer completion.
8. Adding a new state/chart library would be unnecessary dependency drift.
9. Backend endpoints already exist; adding new backend aggregation would duplicate 7.B.4-7.B.8 contracts.
10. Provider Console was excluded from v1; the page must stay v2-only and not alter public landing/docs claims.

Revisions applied:

- Scoped this story to a read-only `apps/web` adapter over existing capability-registry contracts.
- Added explicit out-of-scope boundaries for public auth/ownership, 8.C.6, write routes, backend changes, payment/tax/invoice, and new dependencies.
- Changed language from "own provider" to explicit provider filters.

### Round 2 - Drift, Data Consistency, And Contract Review

Findings:

1. Client query parameters could drift from backend names, especially `from`/`to`, `tenant_id`, and `requested_provider_id`.
2. Tenant filtering must be consistent across all sections; mixing exact-tenant dashboard calls with application global fallback would confuse users.
3. If `application_id` is omitted, version update listing needs deterministic behavior and not a failed request.
4. One failing endpoint should not hide other valid dashboard sections.
5. The page might serialize raw `metadata`, `cosign_bundle`, monthly snapshot arrays, or payout metadata through debug JSON.
6. Financial summaries must distinguish pending/held/paid/voided and avoid implying settlement.
7. Route-share percentage must be labeled as staged rollout share, not real traffic.
8. KPI success rate must be labeled as shadow-validation KPI, not production KPI.
9. Client functions must not send request bodies for GET calls; this can regress silently.
10. Internal write headers (`X-Internal-Service-Auth`, `If-Match`) must never leave the browser Console.

Revisions applied:

- Added exact client function list and query/auth/no-body/no-internal-header ACs.
- Added deterministic application fallback for version update listing.
- Added partial-failure and safe-field rendering ACs.
- Added semantic disclaimers for route/KPI/financial/version/monthly lifecycle data.

### Round 3 - Dependencies, Tests, Closure, And GitHub Sync Review

Findings:

1. The story needed concrete frontend gates instead of capability-registry Python gates.
2. Tests must cover no storage writes because Provider IDs and dashboard responses can become sensitive workflow hints.
3. Navigation discoverability should be explicit; otherwise the page can exist but be orphaned.
4. Empty result handling must be verified separately from loading and error states.
5. The page can be implemented without new shared UI package components; adding a ProviderRoutingHistory component would expand scope.
6. No OpenAPI regeneration is needed because backend contracts remain unchanged.
7. Existing Console pages should not regress auth/session behavior.
8. The story status should move to ready-for-dev only after all three review rounds.
9. Done must remain gated on PR merge, remote branch deletion, local main sync, and then status sync.
10. Post-implementation code review findings must be written back into the story.

Revisions applied:

- Added frontend-specific test/typecheck/diff gates.
- Added no-storage, nav, empty-state, no-new-dependency, and no-OpenAPI-regeneration constraints.
- Moved story to `ready-for-dev` and kept final `done` gated on full GitHub sync.

## Post-Implementation Code Review

### Review Scope

- Uncommitted branch diff for Story 7.B.9 against baseline `61abd7cdfb2d75188d6d4bd6ac0fde94209fe08e`.
- Layers covered manually in one pass: Blind Hunter, Edge Case Hunter, and Acceptance Auditor.
- Checked boundaries: read-only GET-only client behavior, no internal/write headers, exact query names, tenant/period consistency, safe-field rendering, no browser storage writes beyond existing JWT read, no backend/OpenAPI/dependency drift, and AC closure.

### Findings

- [x] [Review][Patch] Period-only UI input was adding an implicit `currency: "CNY"` filter to revenue payout and monthly batch reads, which narrowed data beyond AC 10 and could hide non-CNY Provider revenue. Fixed by removing the default currency filters and adding page assertions that only `periodMonth` and `tenantId` are sent from the UI.
- [x] [Review][Patch] Revenue/payout rendering did not display `period_summaries`, leaving AC 15 only partially satisfied. Fixed by adding a safe period-summary table with period, entry count, provider revenue, pending, and held amounts.
- [x] [Review][Patch] Monthly batch rendering used the checksum prefix, while AC 17 requires a checksum suffix. Fixed by rendering `calculation_checksum.slice(-10)` and adding regression coverage for the suffix.

### Outcome

Approved after fixes. Focused tests, full web regression tests, typecheck, and whitespace gate all pass. Final story completion remains pending GitHub CI, PR merge, remote branch deletion, and local `main` sync.
