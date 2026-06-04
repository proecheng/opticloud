---
story_key: 9-2-prometheus-metric-audit
epic_num: 9
story_num: 2
epic_name: NFR Governance
status: code-review
baseline_commit: 3eb894b36e67a8b0c2ce5dae265aae943ad0149f
priority: High
type: NFR-O Prometheus business metric audit governance
created_by: bmad-create-story
created_at: 2026-06-04
sources:
  - _bmad-output/planning/epics.md (Epic 9 / Story 9.2 / NFR-O)
  - _bmad-output/planning/implementation-readiness-report-2026-05-17-v2.md (NFR-O1/O2/O3)
  - _bmad-output/planning/architecture.md (Observability stack / Prometheus / Grafana / OpenTelemetry)
  - packages/shared-py/opticloud_shared/otel_setup.py
  - apps/auth-service/src/auth_service/main.py
  - apps/solver-orchestrator/src/solver_orchestrator/main.py
  - apps/capability-registry/src/capability_registry/routes.py
  - apps/billing-service/src/billing_service/routes.py
  - apps/outbox-relayer/src/outbox_relayer/relayer.py
  - tools/api_gateway_perf/perf_baseline_plan.json
  - scripts/validate_api_gateway_perf_plan.py
  - _bmad-output/stories/9-1-axe-core-quarterly-audit.md
  - .github/workflows/ci.yml
---

# Story 9.2 - Prometheus Business Metric Completeness Audit

Status: code-review

## Story

**作为** NFR-O observability owner，
**我希望** NFR-O1 业务埋点清单、Grafana 仪表盘审计、缺失埋点工单和 evidence schema 形成季度治理闭环，
**从而** 每个季度都能用可复核、无敏感数据、可追踪票据的方式确认 request_count / success_rate / latency / credit / chat / provider / reproducibility / sandbox / uptime 等业务信号是否被 Prometheus/Grafana 覆盖，而不是靠口头声明可观测性完整。

## Context

Epic 9.2 原始 AC 要求：Given NFR-O1 业务埋点 / When quarterly / Then Grafana 仪表盘审计 + 缺失埋点工单，精简档 annual。NFR-O1 在 readiness report 中定义为 request_count / success_rate / latency_p50/p95/p99 按 SKU x Provider；credit_burn/refund rate；chat_session/turn/conversion；provider_route/failure；repro_voucher；sandbox_violation/timeout；monthly_uptime。NFR-O2 定义 Prometheus + Grafana + Loki + OpenTelemetry，标准档自建，精简档 Grafana Cloud free tier。

当前仓库已有基础 observability 片段：`packages/shared-py/opticloud_shared/otel_setup.py` 初始化 OTel metrics/traces，`auth-service`、`solver-orchestrator`、`capability-registry`、`outbox-relayer` 暴露 `/metrics`，`billing-service` 已有 `billing_estimate_total` counter，`outbox-relayer` 已有 lag/published/fail/batch metrics。此前 `m3-6d-api-gateway-perf-baseline` 已建立 Locust + Prometheus + Grafana evidence 模式，但没有 NFR-O1 业务指标完整度的 canonical catalog、审计 evidence schema、缺失指标 ticket policy、Grafana dashboard review SOP 或 CI drift gate。

本 story 只建立 NFR-O 业务埋点审计闭环：

- 静态 contract/catalog 定义必须审计的业务指标域、服务所有者、PromQL/dashboard expectation 和 allowed missing reasons。
- Evidence schema 支持季度标准档和精简档 annual cadence，但 committed example 不得声称真实 Grafana review 已完成。
- Validator 检查 contract/schema/example、可选真实 evidence、现有代码中的 `/metrics` 和 Prometheus metric references、CI wiring、敏感数据和伪完成声明。
- Runbook 明确季度执行、Grafana 截图/Prometheus 快照 redaction、缺失指标工单、stop-ship 规则和精简档 annual 降级。

## Scope

1. Add a static Prometheus business metric audit contract under `tools/prometheus_metric_audit/`.
   - Contract pins source story `9.2`, audit version, NFR-O1/O2 scope, standard quarterly cadence, lite annual cadence, report directory, required business metric domains, service owners, and dashboard review requirements.
   - Contract must explicitly distinguish `required`, `planned`, `existing`, and `missing_with_ticket` coverage states.
   - Contract must not claim live production scraping, real Grafana dashboard publication, real quarterly review completion, real ticket creation, uptime SLA approval, or external incident subscription coverage.
2. Add a business metric audit evidence schema and example manifest.
   - Example manifest is static and `example_only=true`.
   - Real evidence, when supplied via validator flag, must live under `reports/prometheus-metric-audit/<run_id>/audit_manifest.json`.
   - Evidence supports coverage per metric, PromQL query snapshots, Grafana dashboard panels, scrape target observations, findings, ticket references, redaction review, and cadence mode.
   - Evidence must be public-safe: no tenant/user/customer ids, API keys, bearer tokens, cookies, credentials, credentialed URLs, production hostnames, dashboard share tokens, absolute local paths, raw logs, prompt/provider payloads, or raw metric labels that identify customers.
3. Add `scripts/validate_prometheus_metric_audit.py`.
   - Validator checks contract, schema, static example, optional real evidence, observed service `/metrics` endpoint references, observed Prometheus metric declarations, and CI workflow wiring.
   - Validator discovers current repo evidence from source text, including `/metrics` endpoints and Prometheus metric declarations, and fails if contract `observed_repo_state` drifts.
   - Validator fails if required NFR-O1 metric domains are removed from the contract or example coverage.
   - Validator fails on fake completion claims in static examples.
4. Add `tests/test_prometheus_metric_audit.py`.
   - Tests cover happy-path CLI validation, contract NFR-O1 domain completeness, repo-state drift, fake completion, unsafe evidence path, PII/secret leakage, missing required metric coverage, failed/missing metric ticket requirements, release approval blocking, and CI wiring.
5. Add `docs/runbooks/prometheus-metric-audit.md`.
   - Documents standard quarterly and lite annual operator flow, local/CI commands, Grafana/Prometheus evidence capture, redaction rules, missing metric ticket policy, stop-ship rules, rollback, and handoff to Story 9.3 for alert automation and Story 9.7 for unified dashboard.
6. Update `.github/workflows/ci.yml`.
   - Add a dedicated `prometheus_metric_audit` path filter and `prometheus-metric-audit-validation` job.
   - Job hard-gates the static validator, optional committed real evidence manifests, Python tests, and does not use `continue-on-error`.
7. Do not add new npm or Python dependencies.
8. Do not modify service runtime instrumentation, Prometheus deployment, Grafana dashboard JSON, Loki/Tempo deployment, database migrations, OpenAPI contracts, billing/auth/provider business logic, or status page implementation.

## Out Of Scope

- Adding new live Prometheus metrics to business services.
- Creating or publishing real Grafana dashboards.
- Running Prometheus, Grafana, Loki, Tempo, Kubernetes, staging load tests, cloud scrapes, or production network calls in CI.
- Proving a real quarterly/annual audit has happened through committed examples.
- Creating real GitHub/Linear/DingTalk tickets automatically.
- Implementing alert rules, DingTalk notification, Linear automation, or NFR-COST redline automation; those belong to Story 9.3.
- Building the cross-cutting Grafana governance dashboard; that belongs to Story 9.7.
- Claiming monthly uptime SLA, production incident subscription coverage, or public status page status.
- Adding dependencies such as `jsonschema`, Prometheus/Grafana clients, pytest plugins, or YAML parsers.

## Acceptance Criteria

1. `tools/prometheus_metric_audit/business_metric_audit_contract.json` exists and validates as the canonical Story 9.2 NFR-O contract.
2. Contract pins `source_story=9.2`, `audit_version=prometheus_business_metric_audit_v1`, `nfr=NFR-O`, `nfr_o1_scope=true`, `standard_cadence=quarterly`, and `lite_cadence=annual`.
3. Contract defines exactly ten NFR-O1 metric ids: request_count, success_rate, latency, credit_burn, refund_rate, chat, provider_route, reproducibility, sandbox, and uptime. `request_count`, `success_rate`, and `latency` share the `api_gateway` domain group but must remain separate metric ids.
4. Contract defines required dimensions for API metrics: `sku`, `provider`, `service`, `endpoint_class`, and `tenant_tier` without allowing customer-identifying labels.
5. Contract requires latency percentile coverage for p50, p95, and p99.
6. Contract defines Grafana dashboard review requirements: dashboard id, panel ids, data source, time range, screenshot artifact path, reviewer role, and review outcome.
7. Contract defines allowed metric coverage states: `covered`, `missing_with_ticket`, `planned`, and `not_applicable`.
8. Contract defines observed repo state for existing `/metrics` surfaces and Prometheus metric declarations, including `auth-service`, `solver-orchestrator`, `capability-registry`, `outbox-relayer`, `billing_estimate_total`, and outbox relayer metrics.
9. Contract explicitly states it does not prove live production scraping, real dashboard publication, real quarterly review completion, real ticket creation, or uptime SLA approval.
10. Evidence schema and static example manifest exist under `tools/prometheus_metric_audit/`.
11. Static example manifest has `example_only=true`, `real_grafana_review_completed=false`, `real_prometheus_scrape_completed=false`, `release_approved=false`, and cannot claim real audit pass, real dashboard publication, real external ticket creation, or production uptime approval.
12. Optional real evidence path mode accepts only `reports/prometheus-metric-audit/<run_id>/audit_manifest.json` where directory name equals `run_id`.
13. Optional real evidence requires `example_only=false`, `redaction_reviewed=true`, valid cadence mode (`quarterly` or `annual_lite`), full metric-domain coverage, scrape target summary, Grafana review records, and PromQL snapshot metadata.
14. Every metric with status `missing_with_ticket` or failed Grafana/PromQL check must have at least one ticket reference with owner, severity, due date, and status.
15. Real evidence cannot mark `release_approved=true` while unresolved P0/P1/P2 NFR-O findings remain open, in progress, or deferred.
16. Validator rejects tenant/user/customer ids, API keys, bearer tokens, cookies, passwords, secrets, dashboard share tokens, credentialed URLs, production hostnames, absolute paths, directory traversal, prompt/provider payload fields, raw logs, and raw metric labels containing customer-identifying dimensions.
17. Validator discovers current committed `/metrics` endpoint references and Prometheus metric declarations and fails if contract `observed_repo_state` is stale.
18. Validator fails if any canonical NFR-O1 metric domain is absent from the contract or evidence coverage.
19. Validator fails if static examples claim real completion or real production approval.
20. Tests cover validator happy path, NFR-O1 domain drift, repo-state drift, fake completion, unsafe evidence paths, leak rejection, missing metric coverage, missing-ticket enforcement, release approval blocking, and CI workflow wiring.
21. Runbook documents local commands, quarterly standard flow, annual lite flow, Grafana/Prometheus capture, evidence path, redaction rules, ticket policy, stop-ship policy, rollback, and handoffs to Stories 9.3 and 9.7.
22. `.github/workflows/ci.yml` exposes `prometheus_metric_audit` from `changes` outputs.
23. CI path filter `prometheus_metric_audit` covers `tools/prometheus_metric_audit/**`, `scripts/validate_prometheus_metric_audit.py`, `tests/test_prometheus_metric_audit.py`, `docs/runbooks/prometheus-metric-audit.md`, `reports/prometheus-metric-audit/**`, `.github/workflows/ci.yml`, and source files that currently define `/metrics` or Prometheus declarations.
24. CI job `prometheus-metric-audit-validation` runs without `continue-on-error`.
25. CI job runs static validator, optional committed real evidence validation for every `reports/prometheus-metric-audit/**/audit_manifest.json`, and Python tests.
26. No new package dependency is added to root, services, or Python workspace.
27. No service runtime instrumentation, Prometheus deployment, Grafana JSON, Loki/Tempo deployment, database migration, OpenAPI, billing/auth/provider business logic, or status page implementation file is modified.
28. Local gates pass: `uv run python scripts/validate_prometheus_metric_audit.py`, `uv run pytest tests/test_prometheus_metric_audit.py -q`, and `git diff --check`.
29. Post-implementation code review covers boundary issues, drift issues, data consistency, dependency consistency, fake-completion risk, CI closure, no-leak guarantees, and test adequacy; findings are fixed or explicitly documented.
30. Story status flow is `ready-for-dev -> in-progress -> code-review -> done`; `done` is forbidden before GitHub CI passes, PR merges, remote branch is deleted, and local `main` is synced.
31. After merge/sync, story and sprint status are marked `done` only through a separate status-sync commit.

## Tasks / Subtasks

- [x] T1: Add static metric audit contract and evidence schema (AC: 1-16)
  - [x] Create `tools/prometheus_metric_audit/business_metric_audit_contract.json`.
  - [x] Create `tools/prometheus_metric_audit/business_metric_audit_manifest.schema.json`.
  - [x] Create `tools/prometheus_metric_audit/business_metric_audit_manifest.example.json`.
  - [x] Encode NFR-O1 metric domains, dimensions, Grafana review fields, coverage states, observed repo state, and non-completion boundaries.
  - [x] Encode public-safe evidence and missing/failing metric ticket requirements.

- [x] T2: Add validator and unit tests (AC: 12-20)
  - [x] Implement `scripts/validate_prometheus_metric_audit.py` using only stdlib.
  - [x] Validate contract/schema/example and optional real evidence path mode.
  - [x] Discover committed `/metrics` endpoint references and Prometheus declarations and compare them to contract `observed_repo_state`.
  - [x] Add `tests/test_prometheus_metric_audit.py` with drift, leak, fake-completion, coverage, ticket, release-blocking, and CI coverage tests.

- [x] T3: Add metric audit runbook (AC: 21)
  - [x] Document local/CI commands.
  - [x] Document standard quarterly and lite annual audit flows.
  - [x] Document Grafana/Prometheus capture, evidence redaction, missing metric tickets, stop-ship rules, rollback, and 9.3/9.7 handoffs.

- [x] T4: Add CI closure (AC: 22-27)
  - [x] Add `prometheus_metric_audit` output and path filter to `.github/workflows/ci.yml`.
  - [x] Add `prometheus-metric-audit-validation` job.
  - [x] Ensure relevant observability source files trigger the audit validator.
  - [x] Confirm no new dependencies or out-of-scope implementation files are modified.

- [ ] T5: Gates, review, and GitHub sync (AC: 28-31)
  - [x] Run local validation gates.
  - [x] Run post-implementation code review and fix/document findings.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [ ] Mark story and sprint status `done` only after merge/sync through a separate status-sync commit.

## Dev Notes

### Current Observability Infrastructure

- `packages/shared-py/opticloud_shared/otel_setup.py` initializes OTel tracing and metrics via OTLP exporter.
- `apps/auth-service/src/auth_service/main.py` exposes `/metrics` with `generate_latest()`.
- `apps/solver-orchestrator/src/solver_orchestrator/main.py` exposes `/metrics` with `generate_latest()`.
- `apps/capability-registry/src/capability_registry/routes.py` exposes `/metrics` with `generate_latest()`.
- `apps/outbox-relayer/src/outbox_relayer/health.py` exposes `/metrics` with `generate_latest()`.
- `apps/billing-service/src/billing_service/routes.py` declares `billing_estimate_total`.
- `apps/outbox-relayer/src/outbox_relayer/relayer.py` declares `outbox_relayer_lag_seconds`, `outbox_relayer_published_total`, `outbox_relayer_publish_fail_total`, and `outbox_relayer_batch_size`.
- Current implementation does not include a canonical NFR-O1 business metric completeness catalog or governance validator.

### Implementation Pattern To Reuse

- Follow Story 9.1 static governance pattern:
  - contract + schema + static example under `tools/...`
  - stdlib validator under `scripts/...`
  - focused pytest module under `tests/...`
  - runbook under `docs/runbooks/...`
  - dedicated CI path filter and hard gate
- Follow `scripts/validate_api_gateway_perf_plan.py` for Prometheus/Grafana evidence boundaries and real evidence opt-in.
- Keep optional real evidence validation opt-in via `--evidence`.
- Use explicit semantic validators over generic JSON schema libraries.

### Boundary Rules

- This story does not prove a real quarterly Grafana review has happened.
- This story does not prove production Prometheus is scraping any target.
- This story does not prove all required NFR-O1 metrics are already implemented.
- This story does prove:
  - NFR-O1 metric domains and dimensions have a canonical audit contract;
  - static examples cannot fake completion;
  - future evidence must provide full coverage, Grafana/PromQL review records, redaction, and tickets for missing/failing metrics;
  - CI detects drift in known repo observability surfaces and governance assets.

### Suggested Commands

```powershell
uv run python scripts/validate_prometheus_metric_audit.py
uv run pytest tests/test_prometheus_metric_audit.py -q
git diff --check
```

## Definition Of Done

- Story has passed exactly 3 pre-implementation adversarial review rounds with revisions recorded after each round.
- Static NFR-O Prometheus metric audit contract, schema, example, validator, tests, runbook, and CI job exist.
- Validator catches fake completion, repo-state drift, missing canonical metric domains, unsafe evidence paths, unresolved stop-ship findings, and sensitive data leakage.
- Local gates and GitHub CI pass.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Story and sprint status become `done` only after PR CI green, merge, remote branch deletion, local main sync, and a separate status-sync commit.

## Story Review Log

### Round 1: Boundary And Fake-Completion Review

Findings fixed:

- Initial scope could be misread as implementing missing Prometheus business metrics or publishing real Grafana dashboards. Revised scope and out-of-scope sections to make the deliverable a static governance/evidence loop only.
- Initial evidence wording could allow committed examples to imply a real quarterly Grafana review. Added `example_only=true`, `real_grafana_review_completed=false`, `real_prometheus_scrape_completed=false`, and fake-completion rejection requirements.
- Initial NFR-O wording could overclaim uptime/SLA coverage. Added explicit boundaries that this story does not approve uptime SLA, incident subscription coverage, or production status page status.

Status: PASS after fixes.

### Round 2: Drift And Data Consistency Review

Findings fixed:

- Initial contract could drift from actual repo observability surfaces. Added validator requirements to discover committed `/metrics` endpoint references and Prometheus declarations, then compare them to `observed_repo_state`.
- Initial metric coverage list treated API metrics as one broad item. Split request_count, success_rate, and latency into separate canonical metric ids and required p50/p95/p99 latency coverage.
- Initial missing-metric handling allowed gaps without closure. Added ticket references for every `missing_with_ticket` or failed Grafana/PromQL check and release approval blocking for unresolved P0/P1/P2 findings.

Status: PASS after fixes.

### Round 3: Dependency, CI, And Closure Review

Findings fixed:

- Initial story did not explicitly ban Prometheus/Grafana/jsonschema dependencies. Added no-new-dependency constraints and banned runtime clients or schema libraries for this governance-only story.
- Initial CI closure did not include observability source files that define `/metrics` or Prometheus declarations. Added required CI path-filter coverage for those files plus governance assets and evidence reports.
- Initial closure rule mentioned GitHub sync but not separate post-merge status sync. Added explicit status flow and post-merge-only `done` update requirement.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/9-2-prometheus-metric-audit`.
- Baseline commit: `3eb894b36e67a8b0c2ce5dae265aae943ad0149f`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base skill instructions and project config.
- Story creation analyzed Epic 9.2, NFR-O1/O2/O3, current OTel setup, current `/metrics` endpoints, Prometheus metric declarations, Story 9.1 governance pattern, API gateway Prometheus/Grafana evidence pattern, and current CI workflow.
- 2026-06-04 - Completed pre-implementation adversarial review round 1 and revised fake-completion, production scraping/dashboard, and uptime/SLA boundaries.
- 2026-06-04 - Completed pre-implementation adversarial review round 2 and revised repo-state drift detection, canonical metric coverage, latency percentile coverage, and missing metric ticket closure.
- 2026-06-04 - Completed pre-implementation adversarial review round 3 and revised dependency, CI trigger, and GitHub/status-sync closure requirements.
- 2026-06-04 - Story moved to in-progress after exactly three pre-implementation review rounds.
- 2026-06-04 - Corrected AC3 count from nine to ten metric ids and aligned `request_count` naming with NFR-O1 before implementation.
- 2026-06-04 - Implemented static Prometheus metric audit contract/schema/example, stdlib validator, runbook, tests, and CI `prometheus-metric-audit-validation` hard gate.
- 2026-06-04 - Local gates passed: `uv run python scripts/validate_prometheus_metric_audit.py`, `uv run pytest tests/test_prometheus_metric_audit.py -q` (17 passed), and `git diff --check`.
- 2026-06-04 - Post-implementation code review completed; fixed real-evidence planned/not-applicable bypass and broad Prometheus source drift detection, then reran all local gates successfully.

### Completion Notes List

- Initial story created.
- Exactly three pre-implementation adversarial review rounds completed; story is ready for implementation.
- Story moved to in-progress after exactly three pre-implementation review rounds.
- Static contract/schema/example, validator, tests, runbook, and CI hard gate implemented.
- Post-implementation code review completed; findings fixed and gates rerun.

### File List

- `_bmad-output/stories/9-2-prometheus-metric-audit.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `docs/runbooks/prometheus-metric-audit.md`
- `scripts/validate_prometheus_metric_audit.py`
- `tests/test_prometheus_metric_audit.py`
- `tools/prometheus_metric_audit/business_metric_audit_contract.json`
- `tools/prometheus_metric_audit/business_metric_audit_manifest.schema.json`
- `tools/prometheus_metric_audit/business_metric_audit_manifest.example.json`

## Post-Implementation Code Review

### Blind Hunter - Boundary And Fake-Completion Review

Findings:

- No remaining issue found in static example boundaries: committed example remains `example_only=true`, `real_grafana_review_completed=false`, `real_prometheus_scrape_completed=false`, and `release_approved=false`.
- No remaining issue found in out-of-scope boundaries: implementation does not add live service metrics, Prometheus/Grafana deployment assets, alert automation, database migrations, OpenAPI changes, service business logic, or dependencies.

### Edge Case Hunter - Drift And Data Review

Findings:

- [x] P2 fixed: real evidence could previously leave a required metric as `planned` or `not_applicable` while still setting `release_approved=true`, bypassing the missing-metric ticket loop. Validator now rejects real evidence unless every canonical metric is `covered` or `missing_with_ticket`, and tests cover the bypass.
- [x] P2 fixed: repo-state discovery and CI path filtering were initially limited to a fixed list of current files, so a future Prometheus metric added in a new app source file might not trigger the audit. Validator now scans `apps/*/src/**/*.py` for `prometheus_client` usage, and CI triggers on `apps/*/src/**/*.py`.

### Acceptance Auditor - AC Closure Review

Findings:

- No remaining issue found against AC 1-25: static assets, validator, tests, runbook, and CI job are present and locally validated.
- No remaining issue found against AC 26-27: no dependencies or out-of-scope implementation files changed.
- AC 28-29 closed locally: validation gates pass and post-implementation review findings are fixed.
- AC 30-31 remain pending GitHub sync and post-merge status-sync commit, as required.

Outcome: PASS after fixes; awaiting GitHub sync.

## Change Log

- 2026-06-04 - Initial Story 9.2 created.
- 2026-06-04 - Round 1 pre-implementation review revised fake-completion, production scraping/dashboard, and uptime/SLA boundaries.
- 2026-06-04 - Round 2 pre-implementation review revised repo-state drift detection, canonical metric coverage, latency percentile coverage, and missing metric ticket closure.
- 2026-06-04 - Round 3 pre-implementation review revised dependency, CI trigger, and status-sync closure.
- 2026-06-04 - Story status moved to in-progress after exactly three pre-implementation review rounds.
- 2026-06-04 - Corrected AC3 count from nine to ten metric ids and aligned `request_count` naming with NFR-O1 before implementation.
- 2026-06-04 - Implemented Prometheus metric audit contract, evidence schema/example, validator, tests, runbook, and CI hard gate.
- 2026-06-04 - Post-implementation code review fixed real-evidence coverage bypass and broad Prometheus source drift detection; story moved to `code-review` pending GitHub sync.
