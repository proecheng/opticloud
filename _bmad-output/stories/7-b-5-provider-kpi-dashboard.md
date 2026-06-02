---
story_key: 7-b-5-provider-kpi-dashboard
baseline_commit: d348126b4cbb80a8b4fef91b148ce606426a6ef3
epic_num: 7
story_num: B.5
epic_name: Provider Marketplace v2
status: done
priority: High
type: provider KPI dashboard read projection
created_by: bmad-create-story
created_at: 2026-06-02
sources:
  - _bmad-output/planning/epics.md (Epic 7.B / Provider Marketplace v2)
  - _bmad-output/planning/prd.md (FR P5 / Provider success rate + KPI dashboards)
  - _bmad-output/planning/architecture.md (Provider Integration: capability-registry shadow + grey rollout)
  - _bmad-output/stories/7-b-2-shadow-validation.md
  - _bmad-output/stories/7-b-3-gradient-rollout.md
  - _bmad-output/stories/7-b-4-route-share-dashboard.md
  - apps/capability-registry/src/capability_registry/models.py
  - apps/capability-registry/src/capability_registry/schemas.py
  - apps/capability-registry/src/capability_registry/routes.py
  - apps/capability-registry/tests/test_api.py
  - packages/shared-ts/openapi/capability-registry.json
---

# Story 7.B.5 - Provider KPI Dashboard

Status: done

## Story

**作为** 外部 Provider，
**我希望** 能查看自己在 shadow validation 与灰度准备阶段的成功率、延迟、偏差、覆盖和当前 rollout 状态 KPI，
**从而** 在 Provider Console 或 Grafana 展示层接入前，先拥有一个可审计、只读、不会暴露原始样本或营收数据的 KPI 数据契约。

## Context

Epic 7.B 已完成 Provider application/evaluation intake、shadow validation gate、gradient rollout gate，以及 route-share dashboard read projection。PRD FR P5 要求 Provider can view own success rate + KPI dashboards。当前系统仍没有 Provider Console v2、Provider 身份/所有权校验、Grafana dashboard JSON、真实生产路由 telemetry、revenue payout 或 monthly revenue share。

本 story 的最小闭环是在 `apps/capability-registry` 暴露服务侧只读 KPI projection：它只从 `provider_shadow_validation_runs`, `provider_shadow_validation_samples`, and `provider_gradient_rollouts` 派生 dashboard-ready KPI。它不读取 solver-orchestrator request logs，不读取 billing/revenue-share rows，不计算真实生产成功率，不暴露 raw sample payloads，也不声称完成 public provider-authenticated UX。

## Scope

1. 在 `apps/capability-registry` 中新增 Provider KPI dashboard response schemas。
2. 新增服务侧只读 API：
   - `GET /v1/providers/{provider_id}/kpi-dashboard?tenant_id=&from=&to=&run_status=&benchmark_suite=`
3. 该 API 从指定 provider 的 shadow validation runs/samples 派生 success-rate, latency, deviation, coverage, and threshold-violation KPI，并从 matching rollouts 派生当前 rollout context。
4. 添加 capability-registry API tests，覆盖 KPI 汇总、per-run metrics、daily timeline、过滤、租户隔离、漂移保护、无副作用和 OpenAPI unsafe-field 检查。
5. Regenerate `packages/shared-ts/openapi/capability-registry.json`。

## Out Of Scope

- Provider Console v2 页面、Grafana dashboard JSON、public provider authentication/ownership enforcement、API gateway policy。
- 真实生产请求成功率、真实 route telemetry、weighted routing、solver-orchestrator/API gateway 修改、feature flag backend。
- Revenue, pending payout, monthly revenue share, billing ledger, `revenue_share_hooks`, payout status, settlement amount。
- Provider version update lifecycle, equivalent provider matching, voucher migration, provider exit notification。
- 创建新数据库表或迁移；不写入 KPI snapshot/cache/materialized view。
- 暴露 raw dataset/case bodies、sample metadata、run metadata、evidence refs、stage history、shadow summary snapshots、reason refs、credentials、PII、customer routing payloads。

## Acceptance Criteria

1. 不新增数据库表；KPI dashboard 完全派生自现有 `provider_shadow_validation_runs`, `provider_shadow_validation_samples`, and `provider_gradient_rollouts`。
2. 新增 Pydantic schemas：`ProviderKpiAggregateMetrics`, `ProviderKpiRunMetric`, `ProviderKpiTimelinePoint`, `ProviderKpiRolloutSummary`, `ProviderKpiRunStatusCounts`, and `ProviderKpiDashboardResponse`。
3. `ProviderKpiDashboardResponse` 至少包含 `provider_id`, `tenant_id`, `from_at`, `to_at`, `run_status_counts`, `total_runs`, `aggregate`, `rollout_summary`, `run_metrics`, and `timeline`。
4. `ProviderKpiAggregateMetrics` 至少包含 `sample_count`, `success_count`, `failed_count`, `timeout_count`, `provider_error_count`, `success_rate`, `average_deviation_ratio`, `provider_p95_latency_ms`, `baseline_p95_latency_ms`, and `p95_latency_ratio`。
5. `ProviderKpiRunMetric` 至少包含 `application_id`, `evaluation_id`, `run_id`, `provider_id`, `baseline_provider_id`, `benchmark_suite`, `status`, `started_at`, `ended_at`, `updated_at`, `observed_from`, `observed_to`, `coverage_classes`, `coverage_class_counts`, `threshold_violations`, `metrics`, and `scope_source`。
6. `ProviderKpiTimelinePoint` 至少包含 `application_id`, `evaluation_id`, `run_id`, `provider_id`, `benchmark_suite`, `bucket_start`, `metrics`, and `scope_source`。
7. `ProviderKpiRolloutSummary` 至少包含 complete rollout status counts for `draft`, `active`, `paused`, `completed`, and `cancelled`, plus `total_rollouts` and `highest_current_stage_percent`。
8. Dashboard schemas must not expose `summary` raw objects, `stage_history`, `shadow_summary_snapshot`, `evidence_refs`, `metadata`, `reason_ref`, raw dataset/case/request/response fields, credentials, bank/tax fields, payout fields, or customer routing payloads.
9. Endpoint path `provider_id` uses existing provider ID pattern `^[a-z0-9][a-z0-9-]{0,63}$`。
10. Query params:
    - `tenant_id` optional UUID。
    - `from` and `to` optional timezone-aware datetimes; if both present, `from <= to` or 422。
    - `run_status` optional shadow run status enum: `draft`, `running`, `passed`, `failed`, `cancelled`。
    - `benchmark_suite` optional pattern `^[a-z0-9][a-z0-9_-]{0,63}$`。
11. Query aliases are exactly `from` and `to`; implementation may use Python names such as `from_at` and `to_at`, but OpenAPI must expose aliases。
12. Provider filtering is authoritative: only shadow runs where `requested_provider_id == provider_id` are included. Baseline provider rows must not leak into the requested provider dashboard。
13. Tenant filtering is exact. With no `tenant_id`, only global run/sample/rollout rows are returned. With `tenant_id`, only rows for that tenant are returned; no global fallback is mixed into tenant dashboards。
14. The endpoint does not require a matching live `capability_providers` row. A provider with no shadow runs returns the empty dashboard shape rather than 404。
15. Time filters are inclusive and apply to sample-derived KPI metrics and daily timeline after provider/scope/run filters are applied. They do not hide run rows, do not change run status counts, and do not hide current rollout context。
16. `aggregate` is computed across all selected runs' samples within the time window; if there are no samples in the window, all count metrics are zero and ratio metrics serialize as `"0.000000"` except `p95_latency_ratio`, which is `"0.000000"` when no baseline latency exists in the selected sample set。
17. `success_count` uses the same pass semantics as shadow validation samples: provider HTTP status 2xx, `timed_out=false`, and `deviation_ratio <= 0.020000`。
18. `failed_count = sample_count - success_count`; `timeout_count` counts timed-out samples; `provider_error_count` counts samples with provider status outside 2xx. `timeout_count` and `provider_error_count` may overlap with `failed_count` and must not be summed as independent totals。
19. P95 latency uses the existing nearest-rank p95 helper. `p95_latency_ratio = provider_p95_latency_ms / baseline_p95_latency_ms`, quantized to six decimals when baseline p95 is positive。
20. `coverage_classes` and `coverage_class_counts` are derived from selected samples in the same window and include all required shadow coverage classes with zero counts when absent。
21. `threshold_violations` uses the established Provider Integration thresholds: min sample count 500, min observed day span 14, required coverage classes, min success rate 0.980000, max average deviation 0.020000, and max p95 latency ratio 1.500000。
22. `timeline` is bucketed by UTC calendar day from sample `observed_at`, uses timezone-aware UTC `bucket_start`, and is sorted by `bucket_start`, `application_id`, `evaluation_id`, `run_id`。
23. `run_metrics` sorting is deterministic by `application_id`, `evaluation_id`, `run_id`。
24. `run_status_counts` includes all shadow run statuses with integer keys `draft`, `running`, `passed`, `failed`, and `cancelled`, even when zero。
25. `rollout_summary` is derived from `provider_gradient_rollouts` matching the selected provider, exact tenant scope, and selected run row ids. It validates rollout status/stage with the same closed sets as 7.B.4 and fails closed on malformed row drift。
26. Run row `status` must be one of `draft`, `running`, `passed`, `failed`, `cancelled`; malformed manual DB drift returns 409。
27. Sample row `coverage_class` must be one of the four required coverage classes; malformed manual DB drift returns 409。
28. Sample row `observed_at` must be timezone-aware; malformed manual DB drift returns 409。
29. Sample row `provider_status_code` must be 100-599, `provider_latency_ms` and `baseline_latency_ms` must be positive, and `deviation_ratio` must be non-negative; malformed manual DB drift returns 409。
30. Sample rows attached to a selected run must have the same exact tenant scope as the run; mismatched tenant drift returns 409 instead of silently mixing or dropping evidence。
31. The endpoint is read-only and must not insert, update, delete, lock, or mutate provider applications, evaluations, shadow runs, shadow samples, gradient rollouts, provider/capability rows, OAuth rows, revenue-share rows, or billing rows。
32. Existing provider/capability/OAuth/revenue-share/application/evaluation/shadow/rollout/route-share tests continue to pass。
33. The new schemas/routes are included in `packages/shared-ts/openapi/capability-registry.json`; `scripts/check_openapi_drift.py` detects drift。
34. `.github/workflows/ci.yml` keeps the existing `capability-registry-test` job; no new CI service job is added。
35. Local gates pass: `uv run pytest apps/capability-registry/tests/ -v`, `uv run mypy apps packages`, `uv run ruff check apps/capability-registry`, `uv run ruff format --check apps/capability-registry`, `uv run python scripts/generate_openapi.py`, `uv run python scripts/check_openapi_drift.py`, and `git diff --check`。
36. Implementation record includes post-implementation code review findings and fixes。
37. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done`。

## Tasks / Subtasks

- [x] T1: Add Provider KPI dashboard schemas (AC: 2-8)
  - [x] Define aggregate metrics, per-run metrics, timeline point, rollout summary, status counts, and response schemas。
  - [x] Keep unsafe raw evidence, metadata, payout, and routing fields out of dashboard schemas。

- [x] T2: Add Provider KPI dashboard route (AC: 1, 9-31)
  - [x] Add `GET /v1/providers/{provider_id}/kpi-dashboard`。
  - [x] Derive KPI metrics from shadow runs/samples and rollout context from gradient rollouts。
  - [x] Validate provider filter, exact tenant scope, time-window behavior, deterministic sorting, and fail-closed drift cases。

- [x] T3: Add tests and OpenAPI coverage (AC: 32-35)
  - [x] Cover aggregate metrics, per-run metrics, daily timeline, empty state, query filters, and no side effects。
  - [x] Cover provider filter, tenant exact scope, baseline provider non-leakage, and sample tenant mismatch drift 409。
  - [x] Cover malformed run/sample/rollout drift 409 cases。
  - [x] Add OpenAPI unsafe-field absence and query alias assertions。
  - [x] Regenerate checked-in OpenAPI and run drift check。

- [x] T4: Review, gates, and GitHub sync (AC: 36-37)
  - [x] Run post-implementation code review and fix findings。
  - [x] Record code review findings and fixes in `Post-Implementation Code Review`。
  - [x] Run local gates after fixes。
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`。
  - [x] Mark story and sprint status `done` only after merge/sync。

## Dev Notes

### Service Boundary

- Implement only in `apps/capability-registry`, checked-in capability-registry OpenAPI, tests, and story/status files。
- Do not add DB migrations, tables, materialized views, background jobs, or scheduled KPI snapshots。
- This story creates a service-side read projection contract. It does not create public Provider Console UX, Grafana assets, API gateway provider-auth ownership policy, real production routing, billing/revenue settlement, or telemetry ingestion。

### Existing Patterns To Reuse

- Reuse `_PATH_ID_PATTERN`, `_BENCHMARK_SUITE_PATTERN`, `_scope_source(...)`, `ProviderShadowRunStatus`, `ProviderShadowCoverageClass`, `ProviderRolloutStatus`, `ProviderRolloutStage`, `_ROLLOUT_STAGES`, `_SHADOW_REQUIRED_COVERAGE_CLASSES`, `_SHADOW_MIN_*`, `_SHADOW_MAX_*`, `_nearest_rank_p95(...)`, `_decimal_ratio(...)`, and existing FastAPI/Pydantic style。
- Reuse 7.B.4's exact tenant-scope behavior for provider dashboards: no global fallback in provider-owned dashboards。
- Reuse 7.B.4's fail-closed approach for malformed stored drift; do not silently fabricate dashboard data from invalid rows。
- Use `Path(pattern=...)` and typed/validated `Query(...)` so invalid ids/statuses/windows return 422 where input is invalid。
- Existing OpenAPI generation and drift scripts already include capability-registry。

### Data Semantics

- Treat KPI success rate as shadow-validation/sample success rate, not observed production success rate。
- Do not read solver-orchestrator request logs, optimization results, billing events, revenue hooks, or customer routing payloads。
- Do not expose raw sample/run/rollout evidence. Dashboard schemas should contain stable derived fields only。
- Time filters define the sample observation window for KPI math and timeline points; run selection is provider/scope/status/benchmark based and remains visible even when no samples fall in the window。
- Normalize timeline bucket starts to UTC daily boundaries。
- Treat Provider identity/ownership as a later Provider Console/API gateway concern; this API remains a service-side read projection。

### Previous Story Intelligence

- 7.B.2 established shadow sample pass semantics and Provider Integration thresholds。
- 7.B.3 and 7.B.4 deliberately kept provider marketplace gates contract-only and did not run real traffic。
- 7.B.4 proved provider dashboards should not expose `global_fallback` scope or raw `stage_history`/`shadow_summary_snapshot`。
- 7.B.4 post-review fixed OpenAPI enum metadata for query compatibility; use the same caution for enum-like query params。

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

- Story file has passed 3 pre-implementation adversarial review rounds and revisions。
- Provider KPI dashboard API satisfies FR P5 as a safe, dashboard-ready read projection without implementing real production KPI telemetry or Provider Console UX。
- Existing provider marketplace behavior remains compatible。
- Post-implementation code review is completed and findings are fixed or explicitly documented。
- Local quality gates and GitHub CI pass。
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync。

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/7-b-5-provider-kpi-dashboard`。
- Baseline commit: `d348126b4cbb80a8b4fef91b148ce606426a6ef3`。
- Story creation used local context from 7.B planning docs, 7.B.2 shadow validation, 7.B.3 gradient rollout, and 7.B.4 route-share dashboard。
- Focused KPI tests: `uv run pytest apps/capability-registry/tests/test_api.py -k "provider_kpi_dashboard" -v` -> 4 passed。
- Full capability-registry tests: `uv run pytest apps/capability-registry/tests/ -v` -> 41 passed。
- Type gate: `uv run mypy apps packages` -> passed。
- Lint/format gates: `uv run ruff check apps/capability-registry` and `uv run ruff format --check apps/capability-registry` -> passed。
- OpenAPI gates: `uv run python scripts/generate_openapi.py` and `uv run python scripts/check_openapi_drift.py` -> passed。
- Whitespace gate: `git diff --check` -> passed。
- Post-review focused KPI tests: `uv run pytest apps/capability-registry/tests/test_api.py -k "provider_kpi_dashboard" -v` -> 4 passed。
- Post-review full capability-registry tests: `uv run pytest apps/capability-registry/tests/ -v` -> 41 passed。
- Post-review type/lint/OpenAPI/whitespace gates passed。

### Completion Notes List

- Story created for Provider KPI Dashboard read projection。
- Completed 3 pre-implementation adversarial review rounds and revised the story after each round。
- Added KPI dashboard schemas and `GET /v1/providers/{provider_id}/kpi-dashboard`。
- Implemented shadow-sample KPI aggregation, per-run metrics, UTC daily timeline, rollout context summary, exact tenant scope, provider filter, and fail-closed 409 behavior for stored drift。
- Added tests for metrics, time windows, empty states, tenant isolation, baseline-provider non-leakage, no side effects, drift handling, and OpenAPI unsafe-field protection。
- Post-implementation review findings fixed: sample loading no longer uses N+1 queries, and rollout summary scope validation now uses the endpoint requested tenant scope。
- GitHub sync completed: PR #140 passed CI including `ci`, `e2e`, and `image-build`; merged to `main` at `12ee512f46e4a059f20eec3afd23378aa76263dc`; remote branch `codex/7-b-5-provider-kpi-dashboard` was deleted; local `main` is synced with `origin/main`。

### File List

- `_bmad-output/stories/7-b-5-provider-kpi-dashboard.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/capability-registry/src/capability_registry/schemas.py`
- `apps/capability-registry/src/capability_registry/routes.py`
- `apps/capability-registry/tests/test_api.py`
- `packages/shared-ts/openapi/capability-registry.json`

## Change Log

- 2026-06-02 - Story created for Provider KPI Dashboard read projection。
- 2026-06-02 - Completed 3 pre-implementation adversarial review rounds; story marked ready for development。
- 2026-06-02 - Implementation started; story and sprint status moved to in-progress。
- 2026-06-02 - Implemented Provider KPI Dashboard read projection, tests, and OpenAPI update; story moved to review pending post-implementation code review。
- 2026-06-02 - Post-implementation code review completed; review findings fixed and local gates passed。
- 2026-06-02 - PR #140 passed GitHub CI, merged to `main`, remote branch deleted, local `main` synced, and story marked done。

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary, Ownership, And Product Fit Review

Findings:

1. "Provider can view own" could imply this story implements public Provider authentication and ownership enforcement。
2. "KPI dashboards" could be mistaken for a Provider Console page or Grafana dashboard asset。
3. "Success rate" could be misread as real production traffic success rate rather than shadow validation sample success rate。
4. KPI scope could accidentally include revenue, payout, or monthly revenue share, which belongs to later P6/P8 stories。
5. The story initially needed to clarify whether a live `capability_providers` row is required。
6. A read endpoint without `X-Internal-Service-Auth` could be mistaken for public provider-authenticated access。
7. Rollout context could accidentally duplicate route-share dashboard semantics or imply real route share。
8. Unsafe raw sample, evidence, metadata, and routing payload fields needed explicit exclusion。
9. The story needed a clear empty dashboard shape。
10. API gateway policy was not explicit enough in out-of-scope。

Revisions applied:

- Clarified this is a service-side read projection, not Provider Console, Grafana, or public provider-auth。
- Defined success rate as shadow-validation sample success rate only。
- Excluded revenue/payout/monthly revenue share and real production telemetry。
- Added no-live-provider-row requirement and unsafe-field exclusions。
- Limited rollout usage to current context summary, not route-share timeline duplication。

### Round 2 - Drift, Data Consistency, And Tenant Scope Review

Findings:

1. KPI math needed exact pass semantics aligned with shadow validation。
2. Time-filter behavior could hide run rows or change status counts unpredictably。
3. Tenant exact-scope behavior needed to cover runs, samples, and rollouts。
4. Sample rows attached to a run with mismatched tenant scope could be silently ignored。
5. Stored run status drift was not explicitly fail-closed。
6. Stored sample coverage class, status code, latency, deviation, and observed_at drift needed exact behavior。
7. Empty sample windows needed deterministic ratio semantics。
8. `timeout_count` and `provider_error_count` can overlap with `failed_count`; summing them would double-count failures。
9. Timeline bucketing needed a timezone rule。
10. Rollout context needed closed status/stage validation like 7.B.4。

Revisions applied:

- Added exact pass semantics and metric formulas。
- Clarified time filters apply only to sample-derived metrics/timeline, not run rows/status counts/rollout context。
- Added fail-closed ACs for run/sample/rollout drift and tenant mismatch。
- Defined zero-sample ratio behavior and UTC daily timeline buckets。
- Clarified failure-count overlap semantics。

### Round 3 - Dependencies, Tests, And Closure Review

Findings:

1. The story needed to transition to `ready-for-dev` only after the three required review rounds。
2. Sprint status must move from `backlog` to `ready-for-dev` after story creation and review completion。
3. T4 needed explicit post-implementation review recording and GitHub sync steps。
4. OpenAPI alias and unsafe-field checks must be explicit。
5. Local gates must include OpenAPI generation before drift check。
6. Tests must prove no mutation side effects, not only happy-path KPI output。
7. Tests must cover empty dashboards and empty sample windows separately。
8. Tests must cover provider filter, tenant exact scope, and baseline-provider non-leakage。
9. The story must not add new CI jobs or services。
10. Final completion must include PR, CI, merge, remote branch deletion, and local main sync details before marking done。

Revisions applied:

- Moved story status to `ready-for-dev`。
- Added explicit T4 review/gates/GitHub sync tasks。
- Added OpenAPI and no-side-effect test requirements。
- Kept the `done` transition gated on PR merge and local `main` sync。

## Post-Implementation Code Review

- [x] [Review][Patch] Initial KPI sample loading queried samples once per selected shadow run, which would become an N+1 query pattern for providers with many historical runs. Fixed by batching selected-run sample loading with `run_row_id IN (...)`, grouping samples by run id, and preserving per-run validation/window filtering semantics。
- [x] [Review][Patch] Initial rollout summary validation passed each row's own `tenant_id` as the requested scope, weakening the same no-global-fallback guard used by 7.B.4. Fixed by passing the endpoint's requested `tenant_id` into the rollout summary helper so scope validation remains external-request based。
