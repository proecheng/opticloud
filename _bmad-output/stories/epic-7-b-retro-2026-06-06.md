# Epic 7.B Retrospective - Provider Marketplace v2

Date: 2026-06-06
Project: 通用优化与预测服务网站
Epic: Epic 7.B - Provider Marketplace v2
Status: complete

## Summary

Epic 7.B closed with nine completed stories:

- 7.B.1 Provider Apply v2
- 7.B.2 Shadow Validation
- 7.B.3 Gradient Rollout
- 7.B.4 Route Share Dashboard
- 7.B.5 Provider KPI Dashboard
- 7.B.6 Provider Revenue + Pending Payout
- 7.B.7 Provider Version Management
- 7.B.8 Monthly Revenue Share
- 7.B.9 Provider Console Tier 3

Together these stories cover Provider FR P1-P8: application intake, shadow validation, staged rollout, route-share view, KPI dashboard, revenue/payout view, version updates, and monthly revenue-share calculation.

## Outcome

Epic 7.B established a complete Provider Marketplace v2 contract chain without over-claiming runtime production integration:

- Provider application and evaluation intake records.
- Shadow validation run/sample storage and deterministic pass/fail gate.
- Gradient rollout records constrained to 0 -> 5 -> 50 -> 100.
- Provider-facing read projections for route share, KPI, revenue/payout, version updates, and monthly batches.
- Monthly revenue-share calculation snapshots with deterministic checksums.
- A Provider Console Tier 3 read-only page that aggregates existing GET contracts without calling internal write routes.

The implementation kept capability-registry as the owner of Provider Marketplace contracts and avoided introducing `apps/revenue-share-service`, public provider auth, live routing mutation, payment settlement, or provider runtime execution before those areas have dedicated stories.

## What Worked

The sequence was coherent. Each story consumed the prior story's contract:

- 7.B.1 created applications and evaluation requests.
- 7.B.2 added shadow validation over submitted evaluations.
- 7.B.3 added rollout only after a passed shadow run.
- 7.B.4 and 7.B.5 projected rollout and shadow state into dashboard-ready reads.
- 7.B.6 through 7.B.8 added financial projections and monthly batch snapshots without settlement side effects.
- 7.B.9 connected the read surfaces into the web Console.

Exact tenant-scope behavior became a strong recurring rule for provider-owned dashboards. Later stories correctly avoided global fallback mixing for provider-facing data.

The stories repeatedly separated contracts from real external execution. That prevented false completion around provider auth, shadow workers, live routing, Grafana, bank settlement, tax, invoicing, and Provider Console ownership enforcement.

## Issues Found

Planning drift exists: `_bmad-output/planning/epics.md` still says Epic 7.B has "13 stories" and groups "Story 7.B.9-13: v2 Console UX + Revenue-Share Service + 学界 onboarding tier 1-3". The implemented state closed that grouped scope through 7.B.9 as a narrow Provider Console aggregate over 7.B.4-7.B.8, with Revenue-Share Service and academic onboarding kept out of scope.

The sprint status has no 7.B.10-13 keys, and no matching story files exist. Creating 7.B.10-13 now would duplicate or over-scope work unless product explicitly reopens the Provider Handbook / academic onboarding / standalone Revenue-Share Service tracks as new stories.

Several 7.B stories intentionally ship service-side contracts, not external operations. That is correct for this repo state, but it must stay visible:

- Shadow validation records and computes gates; it does not run provider containers.
- Rollout records staged decisions; it does not route traffic.
- Revenue/payout and monthly batches compute projections; they do not settle funds.
- Provider Console is an internal read-only adapter; it does not establish public provider ownership or self-service auth.

## Repeated Review Themes

- Boundary issues: do not imply public Provider Console, provider ownership, real routing, live provider execution, or financial settlement when only contracts are present.
- Drift issues: OpenAPI specs, nullable-tenant uniqueness, status enums, ETag/version fields, and exact query aliases must remain synchronized.
- Data consistency: stage histories, checksums, ratios, denormalized hook/policy fields, sample summaries, and status transitions need fail-closed drift checks.
- Dependency consistency: avoid introducing new services, queue workers, billing-service reads, solver-orchestrator mutations, or payment integrations inside capability-registry stories.
- Privacy: raw samples, datasets, provider payloads, billing payloads, payout metadata, bank/tax/payment fields, credentials, API keys, OAuth tokens, user PII, and customer routing payloads must not leak into Provider-facing surfaces.
- Closure: each story preserved the full story lifecycle and post-merge `done` status sync.

## Residual Risks

Epic 7.B does not prove real external Provider Marketplace operations end to end. The following remain intentionally out of scope:

- Public provider authentication and ownership enforcement.
- Provider OAuth execution beyond stubs.
- Real provider application review workflow and legal/commercial approvals.
- Docker pulls, sandbox execution, OpenAPI contract execution, SBOM/cosign verification jobs.
- Real shadow traffic and production route telemetry.
- Live weighted routing or API gateway route mutation.
- Real payment settlement, tax handling, invoices, payout retries, and dispute workflows.
- Standalone Revenue-Share Service deployment.
- Academic Provider Handbook / onboarding tier 1-3 if product wants it as a separate workstream.

## Follow-Through From Epic 6.C Retro

Epic 6.C recommended reconciling Provider planning/status drift before creating a new story. This retrospective resolves that question for 7.B: the implemented 7.B.1-9 chain covers P1-P8 and treats the planned 7.B.9-13 group as consolidated into 7.B.9 for the current repo scope.

No new 7.B.10-13 story should be created unless product explicitly adds a new requirement beyond P1-P8 or reopens academic onboarding / standalone revenue-share service as separate work.

## Action Items

- Owner: BMAD status maintainer. Mark `epic-7-b` as `done` now that 7.B.1-9 are complete and the grouped 7.B.9-13 scope is reconciled.
- Owner: Planning maintainer. Later update planning docs to clarify that current implementation closed Epic 7.B as 9 stories, not 13 standalone stories.
- Owner: Product/architecture. If academic Provider onboarding or standalone Revenue-Share Service becomes required, create explicit new stories with their own three-round adversarial review instead of extending 7.B retroactively.
- Owner: Dev/QA. Keep exact tenant scope, no-global-fallback provider dashboards, ETag/If-Match, and privacy no-leak assertions as default requirements for future provider-owned surfaces.

## Recommended Next Step

After this retrospective and `epic-7-b` status update are committed, continue scanning sprint status for the next genuinely incomplete non-blocked story. Do not create 7.B.10-13 by default; the current Provider Marketplace v2 implementation is closed for P1-P8.
