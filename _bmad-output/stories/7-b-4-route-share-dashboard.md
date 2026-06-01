---
story_key: 7-b-4-route-share-dashboard
baseline_commit: 28f947cc52ff0bd68ffcc32e946c2962afe9c087
epic_num: 7
story_num: B.4
epic_name: Provider Marketplace v2
status: done
priority: High
type: provider route-share dashboard read projection
created_by: bmad-create-story
created_at: 2026-06-01
sources:
  - _bmad-output/planning/epics.md (Epic 7.B / Provider Marketplace v2)
  - _bmad-output/planning/prd.md (FR P4 / Provider route share over time)
  - _bmad-output/planning/architecture.md (Provider Integration: capability-registry shadow + grey rollout)
  - _bmad-output/stories/7-b-1-provider-apply-v2.md
  - _bmad-output/stories/7-b-2-shadow-validation.md
  - _bmad-output/stories/7-b-3-gradient-rollout.md
  - apps/capability-registry/src/capability_registry/models.py
  - apps/capability-registry/src/capability_registry/schemas.py
  - apps/capability-registry/src/capability_registry/routes.py
  - apps/capability-registry/tests/test_api.py
  - packages/shared-ts/openapi/capability-registry.json
---

# Story 7.B.4 - Route Share Dashboard

Status: done

## Story

**作为** 外部 Provider，
**我希望** 能查看自己已通过 shadow 与灰度 gate 的 route-share 阶段随时间变化，
**从而** 在 Provider Console 或 Grafana 展示层接入前，先拥有一个可审计、只读、不会绕过灰度 gate 的数据契约。

## Context

Epic 7.B 把 Provider Marketplace v2 从申请、shadow validation 推进到灰度发布与可视化。7.B.1 已创建 provider application/evaluation intake；7.B.2 已创建 shadow validation gate；7.B.3 已创建 `provider_gradient_rollouts`，只记录 `0 -> 5 -> 50 -> 100` 的 staged promotion contract，不发送真实流量。

PRD FR P4 要求 Provider can view own route share over time。当前系统还没有 Provider Console v2、Provider 身份/所有权校验、Grafana dashboard 资产或真实 solver route telemetry。因此本 story 的最小闭环是 capability-registry 暴露 dashboard-ready 的服务侧只读 route-share projection：它只从 7.B.3 的 rollout rows 与 service-owned `stage_history` 派生时间线和当前状态。它不计算真实请求占比、不读取 solver-orchestrator 运行日志、不写入任何路由配置，也不声称已经完成可公网暴露的 Provider Console。

## Scope

1. 在 `apps/capability-registry` 中新增 route-share dashboard response schemas。
2. 新增服务侧只读 API：
   - `GET /v1/providers/{provider_id}/route-share-dashboard?tenant_id=&from=&to=&status=&stage_percent=`
3. 该 API 仅从 `provider_gradient_rollouts` 中读取指定 provider 的 rollout 当前阶段与历史阶段，输出 dashboard-ready 的摘要、当前 rollout 列表和时间线。
4. 添加 capability-registry API tests，覆盖时间线、过滤、租户隔离、漂移保护、无副作用和 OpenAPI unsafe-field 检查。
5. Regenerate `packages/shared-ts/openapi/capability-registry.json`。

## Out Of Scope

- 真实流量路由、weighted load balancing、route table mutation、feature flag backend、GrowthBook rollout、API gateway 或 solver-orchestrator 改动。
- 从 solver request log、optimization result、billing event、customer routing payload 或 telemetry span 计算真实 traffic share。
- Provider Console v2 页面、Grafana dashboard JSON、provider auth/ownership enforcement、public self-service UX、API gateway policy。
- Provider KPI dashboard、success-rate dashboard、latency dashboard、revenue、pending payout、monthly revenue-share、version management。
- 创建、更新或删除 live `capability_providers`, `capabilities`, `provider_oauth_flows`, `revenue_share_policies`, `revenue_share_hooks`。
- 暴露 raw evidence bodies、shadow summary snapshots、stage action metadata、reason refs、credentials、PII、customer routing payloads。

## Acceptance Criteria

1. 不新增数据库表；route-share dashboard 完全派生自现有 `provider_gradient_rollouts`。
2. 新增 Pydantic schemas：`ProviderRouteShareTimelinePoint`, `ProviderRouteShareCurrentRollout`, `ProviderRouteShareDashboardResponse`。
3. `ProviderRouteShareTimelinePoint` 至少包含 `application_id`, `evaluation_id`, `run_id`, `rollout_id`, `provider_id`, `baseline_provider_id`, `benchmark_suite`, `action`, `stage_percent`, `from_status`, `to_status`, `observed_at`, and `scope_source`。`from_status` may be null only for synthetic `created` points; `to_status` is always present.
4. `ProviderRouteShareCurrentRollout` 至少包含 `application_id`, `evaluation_id`, `run_id`, `rollout_id`, `status`, `current_stage_percent`, `started_at`, `completed_at`, `paused_at`, `cancelled_at`, `updated_at`, and `scope_source`。
5. `ProviderRouteShareDashboardResponse` 至少包含 `provider_id`, `tenant_id`, `from_at`, `to_at`, status counts, `total_rollouts`, `highest_current_stage_percent`, `current_rollouts`, and `timeline`。
6. Dashboard schemas must not expose `stage_history` raw objects, `shadow_summary_snapshot`, `evidence_refs`, `metadata`, `reason_ref`, raw request/response/dataset fields, credentials, bank/tax fields, or customer routing payloads.
7. Endpoint path `provider_id` uses existing provider ID pattern `^[a-z0-9][a-z0-9-]{0,63}$`.
8. Query params:
   - `tenant_id` optional UUID.
   - `from` and `to` optional timezone-aware datetimes; if both present, `from <= to` or 422.
   - `status` optional current rollout status enum: `draft`, `active`, `paused`, `completed`, `cancelled`.
   - `stage_percent` optional closed enum `0`, `5`, `50`, `100`; arbitrary values return 422.
9. Provider filtering is authoritative: only rows where `requested_provider_id == provider_id` are included. Baseline provider rows must not leak into the requested provider's dashboard.
10. Tenant filtering is exact. With no `tenant_id`, only global rollout rows are returned. With `tenant_id`, only rows for that tenant are returned; no global fallback is mixed into tenant dashboards.
11. The endpoint does not require a matching live `capability_providers` row. A provider with no rollout rows returns the empty dashboard shape rather than 404.
12. Timeline includes one synthetic `created` point at stage `0` for each rollout plus service-owned stage history events. For synthetic `created`, `from_status=null` and `to_status` equals the rollout's current status only when the rollout is still `draft`; otherwise `to_status="draft"` so the point represents the initial state.
13. Timeline action values are exactly `created`, `advance`, `pause`, or `cancel`; malformed manual DB drift returns 409 instead of silently fabricating route-share data.
14. Timeline `stage_percent` values are restricted to `0`, `5`, `50`, and `100`; malformed manual DB drift returns 409 instead of silently fabricating route-share data.
15. Rollout row `status` must be one of `draft`, `active`, `paused`, `completed`, `cancelled` and `current_stage_percent` must be one of `0`, `5`, `50`, `100`; malformed manual DB drift returns 409.
16. Each non-synthetic stage history entry must be a JSON object containing parseable `action`, `stage_percent`, `changed_at`, `from_status`, and `to_status`. Missing fields, non-object entries, invalid statuses, invalid stages, or non-timezone-aware/unparseable `changed_at` return 409.
17. Timeline `observed_at` is derived from rollout `created_at` for synthetic points and from each stage history entry `changed_at` for rollout actions.
18. Time filters are inclusive and apply only to timeline points after provider/scope/current-rollout filters are applied. They do not hide `current_rollouts` or change current status counts.
19. Current rollout filters (`status`, `stage_percent`) filter the rollout set before summary and timeline construction.
20. Query aliases are exactly `from` and `to`; implementation may use Python names such as `from_at` and `to_at`, but OpenAPI must expose the aliases.
21. Sorting is deterministic: `current_rollouts` by `application_id`, `evaluation_id`, `run_id`, `rollout_id`; `timeline` by `observed_at`, `application_id`, `evaluation_id`, `run_id`, `rollout_id`, `action`, `stage_percent`.
22. Status counts include all rollout statuses with integer keys `draft`, `active`, `paused`, `completed`, and `cancelled`, even when the count is zero.
23. `highest_current_stage_percent` is the maximum current stage among returned rollouts, not the sum. The API must not imply real observed traffic share or aggregate multiple rollouts into a global traffic percentage.
24. Empty result sets return 200 with zero counts, `highest_current_stage_percent=0`, empty `current_rollouts`, and empty `timeline`.
25. Completed, cancelled, paused, active, and draft rollouts all render without mutation; draft rollouts show only the synthetic `created` point unless stage history exists.
26. GET route requires no `X-Internal-Service-Auth` because it is read-only and internal/service-side, but it must not expose unsafe internal evidence fields and must not be documented as a public provider-authenticated endpoint.
27. The route-share dashboard read does not insert, update, delete, lock, or mutate `provider_gradient_rollouts`, shadow rows, application/evaluation rows, provider/capability rows, OAuth rows, or revenue-share rows.
28. Existing provider/capability/OAuth/revenue-share/application/evaluation/shadow/rollout tests continue to pass.
29. The new schemas/routes are included in `packages/shared-ts/openapi/capability-registry.json`; `scripts/check_openapi_drift.py` detects drift.
30. `.github/workflows/ci.yml` keeps the existing `capability-registry-test` job; no new CI service job is added.
31. Local gates pass: `uv run pytest apps/capability-registry/tests/ -v`, `uv run mypy apps packages`, `uv run ruff check apps/capability-registry`, `uv run ruff format --check apps/capability-registry`, `uv run python scripts/generate_openapi.py`, `uv run python scripts/check_openapi_drift.py`, and `git diff --check`.
32. Implementation record includes post-implementation code review findings and fixes.
33. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done`.

## Tasks / Subtasks

- [x] T1: Add route-share dashboard schemas (AC: 2-8)
  - [x] Define current-rollout, timeline-point, and dashboard response schemas.
  - [x] Keep unsafe source fields out of dashboard schemas.

- [x] T2: Add route-share dashboard route (AC: 1, 7-27)
  - [x] Add `GET /v1/providers/{provider_id}/route-share-dashboard`.
  - [x] Derive summary/current rows/timeline from `ProviderGradientRollout`.
  - [x] Validate filters, stage history, tenant exact scope, and deterministic sorting.

- [x] T3: Add tests and OpenAPI coverage (AC: 28-31)
  - [x] Cover timeline generation and current summary from draft/active/paused/completed/cancelled rollouts.
  - [x] Cover provider filter, tenant exact scope, from/to/status/stage filters, empty state, drift 409, and no side effects.
  - [x] Add OpenAPI unsafe-field absence assertions.
  - [x] Regenerate checked-in OpenAPI and run drift check.

- [ ] T4: Review, gates, and GitHub sync (AC: 32-33)
  - [x] Run post-implementation code review and fix findings.
  - [x] Record code review findings and fixes in `Post-Implementation Code Review`.
  - [x] Run local gates after fixes.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [x] Mark story and sprint status `done` only after merge/sync.

## Dev Notes

### Service Boundary

- Implement only in `apps/capability-registry`, checked-in capability-registry OpenAPI, tests, and story/status files.
- No DB migration is expected unless implementation discovers an unavoidable read-performance/index need; if so, add only an idempotent index and document why it is necessary.
- This story creates a read projection contract. It does not create real routing, public Provider Console UI, Grafana assets, API gateway ownership policy, or telemetry ingestion.

### Existing Patterns To Reuse

- Reuse `_PATH_ID_PATTERN`, `_scope_source(...)`, `ProviderRolloutStatus`, `ProviderRolloutStage`, `_ROLLOUT_STAGES`, and existing FastAPI/Pydantic style.
- Follow 7.B.3 tenant exact-scope behavior for rollout reads rather than global fallback merging.
- Use `Path(pattern=...)` and typed `Query(...)` where possible so invalid ids and enum-like filters return 422.
- Existing OpenAPI generation and drift scripts already include capability-registry.

### Data Semantics

- Treat `current_stage_percent` as declared rollout stage share, not observed production traffic.
- Do not sum route-share percentages across multiple rollouts. Multiple rollouts can represent different applications/evaluations/runs and must remain separate in `current_rollouts`.
- Treat `stage_history` as service-owned evidence. If manual DB drift removes required fields or creates invalid stage percentages, fail closed with 409.
- Do not expose `reason_ref` or action metadata in dashboard schemas; those remain internal audit evidence.
- Treat Provider identity/ownership as a later Provider Console/API gateway concern; this API remains a service-side read projection.
- Normalize all datetime comparisons to aware datetimes. Reject naive query datetimes or naive/manual-drift `changed_at` values with 422 for query input and 409 for stored drift.

### Previous Story Intelligence

- 7.B.2 and 7.B.3 deliberately made provider marketplace gates contract-only and did not run real traffic.
- 7.B.3 post-review fixed shadow-summary drift by validating clean stored evidence. This story must also fail closed on contradictory or malformed stored rollout history.
- 7.B.3 route list already filters rollouts under a single shadow run; this story aggregates across rollouts for one provider and must keep tenant scope exact to avoid cross-tenant leakage.

### Suggested Commands

```powershell
uv sync --all-packages --extra dev
uv run pytest apps/capability-registry/tests/ -v
uv run mypy apps packages
uv run ruff check apps/capability-registry
uv run ruff format --check apps/capability-registry
uv run python scripts/generate_openapi.py
uv run python scripts/check_openapi_drift.py
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Route-share dashboard API satisfies FR P4 as a safe, dashboard-ready read projection without implementing real routing or Provider Console UX.
- Existing provider marketplace behavior remains compatible.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/7-b-4-route-share-dashboard`.
- Baseline commit: `28f947cc52ff0bd68ffcc32e946c2962afe9c087`.
- Focused route-share tests: `uv run pytest apps/capability-registry/tests/test_api.py -k "route_share_dashboard" -v` -> 4 passed.
- Full capability-registry tests: `uv run pytest apps/capability-registry/tests/ -v` -> 37 passed.
- Type gate: `uv run mypy apps packages` -> passed.
- Lint/format gates: `uv run ruff check apps/capability-registry` and `uv run ruff format --check apps/capability-registry` -> passed.
- OpenAPI gates: `uv run python scripts/generate_openapi.py` and `uv run python scripts/check_openapi_drift.py` -> passed.
- Whitespace gate: `git diff --check` -> passed.
- GitHub PR: #139 (`https://github.com/proecheng/opticloud/pull/139`) passed CI and merged to `main`.
- Merge commit: `1de9557e2f180a64cd847bdcf806380ee60051cd`.
- Remote branch cleanup: `codex/7-b-4-route-share-dashboard` deleted after merge.
- Local main sync: `git pull --ff-only origin main` -> already up to date.

### Completion Notes List

- Story created for Provider Route Share Dashboard read projection.
- Completed 3 pre-implementation adversarial review rounds and revised the story after each round.
- Added route-share dashboard schemas and `GET /v1/providers/{provider_id}/route-share-dashboard`.
- Implemented provider/tenant/status/stage filters, timeline construction, fixed status counts, empty response shape, and fail-closed 409 behavior for malformed rollout history.
- Post-implementation review findings fixed: route-share scope schema no longer exposes `global_fallback`, and OpenAPI marks `stage_percent` as the closed rollout stage enum while retaining HTTP query compatibility.
- Local implementation gates passed; PR #139 passed GitHub CI, merged to `main`, remote branch was deleted, local `main` was synced, and story closure is complete.

### File List

- `_bmad-output/stories/7-b-4-route-share-dashboard.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/capability-registry/src/capability_registry/schemas.py`
- `apps/capability-registry/src/capability_registry/routes.py`
- `apps/capability-registry/tests/test_api.py`
- `packages/shared-ts/openapi/capability-registry.json`

## Change Log

- 2026-06-01 - Story created for Provider Route Share Dashboard read projection.
- 2026-06-01 - Completed 3 pre-implementation adversarial review rounds; story marked ready for development.
- 2026-06-01 - Implemented route-share dashboard read projection, post-review fixes, tests, and OpenAPI update; story moved to review pending GitHub sync.
- 2026-06-01 - PR #139 passed CI, merged to `main` at `1de9557e2f180a64cd847bdcf806380ee60051cd`, remote branch was deleted, local `main` synced, and story marked done.

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary, Ownership, And Product Fit Review

Findings:

1. The phrase "Provider can view own" could imply this story completes Provider authentication and ownership enforcement.
2. "Dashboard" could be mistaken for a Provider Console page or Grafana JSON deliverable rather than a service-side projection.
3. A read endpoint without `X-Internal-Service-Auth` could be mistaken for a public provider-authenticated API.
4. Returning route-share values from rollout stage records could be read as actual observed traffic share.
5. The story did not explicitly say whether a provider must already exist in live `capability_providers`.
6. Status counts were underspecified and could drift between sparse and complete shapes.
7. Timeline action values were not closed, leaving room for accidental raw action leakage.
8. Time-filter semantics could accidentally hide current rollout state and make the dashboard misleading.
9. The route could accidentally mix baseline provider rows into the requested provider's dashboard.
10. The out-of-scope list did not explicitly mention API gateway policy.

Revisions applied:

- Clarified that this is a service-side read projection, not public Provider Console or provider ownership enforcement.
- Explicitly excluded API gateway policy, Provider Console v2, and Grafana assets.
- Added ACs for no live provider-row requirement, closed timeline action values, complete status counts, and time-filter semantics.
- Strengthened wording that route share is declared rollout stage share, not observed production traffic.

### Round 2 - Drift, Data Consistency, And Tenant Scope Review

Findings:

1. The first revised story did not define synthetic `created` point status semantics for already-active/completed rollouts.
2. Stored rollout row drift in `status` or `current_stage_percent` was not explicitly covered.
3. Stage history drift was too broad; implementers needed exact required fields for 409 behavior.
4. `changed_at` parsing and timezone requirements were underspecified.
5. Query datetime aliases could accidentally surface as `from_at`/`to_at` instead of `from`/`to` in OpenAPI.
6. Time filters could be implemented against SQL rows instead of timeline points, which would lose action-level precision.
7. Naive datetimes could compare incorrectly across local/UTC boundaries.
8. Status count shape needed a complete fixed key set to avoid dashboard client conditionals.
9. Current rollout summary and timeline filtering order needed to be fixed.
10. Tenant exact-scope behavior remained correct, but tests must cover no global fallback mixing.

Revisions applied:

- Added exact synthetic `created` point status semantics.
- Added fail-closed ACs for row status/stage drift and malformed stage history entries.
- Added timezone-aware datetime requirements for query input and stored `changed_at`.
- Added OpenAPI alias requirement for `from` and `to`.
- Clarified time filters apply to constructed timeline points, not current rollout rows.

### Round 3 - Dependencies, Tests, And Closure Review

Findings:

1. The story had not yet transitioned from `draft` to `ready-for-dev` after the required pre-implementation reviews.
2. Sprint status still needed to move from `backlog` to `ready-for-dev` after story creation and review completion.
3. T4 did not explicitly require writing post-implementation code review findings back into the story.
4. The local gates were complete, but implementation must still run OpenAPI generation before drift check.
5. The GitHub closure rule was present, but story status must remain below `done` until PR merge and local `main` sync.
6. The implementation scope correctly avoided new CI jobs, but review must verify CI workflow remains unchanged unless required.
7. The tests must cover both empty dashboards and populated dashboards to prove the read projection is stable.
8. The tests must include drift 409 cases, not only happy-path rendering.
9. The story must not add broad web UI work under the "dashboard" label.
10. The final completion note must include PR, CI, merge, remote branch deletion, and local main sync details.

Revisions applied:

- Moved story status to `ready-for-dev`.
- Added explicit post-implementation review recording task.
- Added completion/change-log notes for the 3 pre-implementation review rounds.
- Kept the `done` transition gated on PR merge and local `main` sync.

## Post-Implementation Code Review

- [x] [Review][Patch] Route-share response schemas initially reused the generic `ScopeSource`, so OpenAPI allowed `global_fallback` even though the endpoint intentionally never mixes global fallback into tenant dashboards. Fixed by adding `ProviderRouteShareScopeSource = Literal["global", "tenant"]` only for dashboard current/timeline schemas while preserving generic `ScopeSource` for existing provider/capability/shadow/rollout responses.
- [x] [Review][Patch] Tightening `stage_percent` query to `ProviderRolloutStage` produced a strict OpenAPI enum but rejected normal HTTP query strings such as `stage_percent=100`. Fixed by keeping runtime parsing as `int | None`, retaining explicit 0/5/50/100 validation, and adding OpenAPI enum metadata for the query parameter.
