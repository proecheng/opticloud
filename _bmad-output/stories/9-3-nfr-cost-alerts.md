---
story_key: 9-3-nfr-cost-alerts
epic_num: 9
story_num: 3
epic_name: NFR Governance
status: code-review
baseline_commit: ac51f2509932c84c8c821935154ad1902a798d10
priority: High
type: NFR-COST red-line alert governance
created_by: bmad-create-story
created_at: 2026-06-04
sources:
  - _bmad-output/planning/epics.md (Epic 9 / Story 9.3 / NFR-COST)
  - _bmad-output/planning/prd.md (§11.2 cost red lines)
  - _bmad-output/planning/implementation-readiness-report-2026-05-17-v2.md (NFR-COST1/2/3)
  - _bmad-output/stories/m2-3-cost-attribution.md
  - _bmad-output/stories/5-a-8-cost-telemetry-hook.md
  - _bmad-output/stories/9-2-prometheus-metric-audit.md
  - packages/shared-py/opticloud_shared/cost_telemetry/__init__.py
  - infra/local-init/10-cost-attribution.sql
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py
  - apps/billing-service/src/billing_service/routes.py
  - .github/workflows/ci.yml
---

# Story 9.3 - NFR-COST Red-Line Alert Governance

Status: code-review

## Story

**作为** NFR-COST owner / 财务，
**我希望** NFR-COST §11.2 五条成本红线形成 Prometheus alert、钉钉机器人通知 payload、Linear-ready ticket payload 和 evidence 验证闭环，
**从而** LLM/营收、GPU 闲置、Provider 分润、退款率和现金跑道任一 breach 都能被可复核地路由到 owner，而不会靠人工口头巡检或在静态示例里伪造真实外部通知。

## Context

Epic 9.3 原始 AC：Given Story M2.3 G3 完整版 / When 任一红线 breach / Then Prometheus alert + 钉钉机器人 + Linear ticket。M2.3 已交付 `cost_attribution` 表和 shared `opticloud_shared.cost_telemetry`，并在 solver-orchestrator 记录 terminal solve `solver_second`。5.A.8 已补 Billing Saga successful finalize cost hook。9.2 已交付 Prometheus 业务埋点审计治理，并明确 alert automation 属于 9.3。

当前仓库仍没有真实 Prometheus deployment、Alertmanager、钉钉 webhook secret、Linear relayer worker、Grafana dashboard JSON、finance data warehouse、GPU service 或 external ticket scheduler。因此本 story 的最小闭环是静态治理与 evidence gate：

- canonical contract 定义五条 NFR-COST 红线、PromQL 表达式、阈值、severity、owner、所需输入信号和停发条件。
- DingTalk / Linear 输出为 deterministic ready payload，不调用真实外部 API，不存 webhook token，不声称 external delivery。
- evidence schema 支持真实演练或 production evidence，但 committed example 必须是 example-only。
- validator 检查 contract/schema/example、当前 cost telemetry substrate、CI wiring、fake completion、redaction、ticket closure、alert route closure 和 release approval stop-ship。

## Scope

1. Add static NFR-COST alert governance assets under `tools/nfr_cost_alerts/`.
   - Contract pins `source_story=9.3`, `alert_version=nfr_cost_redline_alerts_v1`, `nfr=NFR-COST`, five canonical redlines, Prometheus alert rule metadata, DingTalk-ready payload requirements, Linear-ready ticket requirements, evidence path, and observed cost telemetry state.
   - Contract includes exactly five redline ids: `llm_revenue_ratio`, `gpu_idle_rate`, `provider_share_revenue_ratio`, `refund_issued_rate`, and `runway_months`.
   - Contract distinguishes `required`, `planned`, `missing_with_ticket`, and `not_applicable` input-signal states.
2. Add an evidence schema and static example manifest.
   - Example manifest is static and `example_only=true`.
   - Real evidence, when supplied via validator flag, must live under `reports/nfr-cost-alerts/<run_id>/alert_manifest.json`.
   - Real evidence requires redaction review, all five redlines, alert evaluations, DingTalk-ready payloads, Linear-ready payloads, routing decisions, findings, ticket refs, and source snapshot metadata.
   - Evidence must be public-safe: no tenant/user/customer ids, API keys, bearer tokens, cookies, passwords, webhook tokens, Linear tokens, production hostnames, absolute paths, raw logs, raw Prometheus labels, raw finance exports, prompts, provider payloads, or credentialed URLs.
3. Add `scripts/validate_nfr_cost_alerts.py` using stdlib only.
   - Validate contract/schema/example and optional real evidence path mode.
   - Discover current committed cost telemetry substrate from `infra/local-init/10-cost-attribution.sql`, shared CostUnit enum, solver hook, billing hook, and 9.2 handoff.
   - Fail when contract observed state drifts, any canonical redline is removed, fake completion appears in static examples, unresolved P0/P1/P2 findings coexist with `release_approved=true`, or external delivery is claimed without evidence.
4. Add `tests/test_nfr_cost_alerts.py`.
   - Cover validator happy path, redline drift, observed-state drift, fake completion, unsafe evidence path, leak rejection, missing alert evaluation, missing DingTalk/Linear payloads, missing-ticket enforcement, release blocking, and CI wiring.
5. Add `docs/runbooks/nfr-cost-alerts.md`.
   - Document local/CI commands, redline definitions, standard quarterly drill, breach simulation, real evidence path, Prometheus/Alertmanager capture, DingTalk/Linear-ready handoff, redaction rules, ticket policy, stop-ship policy, rollback, and handoff to Story 9.7 dashboard.
6. Update `.github/workflows/ci.yml`.
   - Add `nfr_cost_alerts` path filter and `nfr-cost-alerts-validation` job.
   - Job hard-gates static validator, optional committed real evidence validation, and Python tests.
7. Do not add new Python/npm dependencies.
8. Do not implement production Alertmanager, real DingTalk webhook calls, real Linear GraphQL mutation, Grafana dashboards, finance warehouse jobs, GPU service, revenue aggregation service, Kubernetes manifests, database migrations, OpenAPI changes, or billing/solver business logic.

## Out Of Scope

- Calling DingTalk, Linear, Prometheus, Alertmanager, Grafana, cloud APIs, or production networks in CI.
- Claiming a real alert fired, a real DingTalk message was delivered, a real Linear issue was created, or a real release was approved through committed examples.
- Adding a live cost analytics service, cron scheduler, worker, queue, webhook secret, OAuth app, SaaS SDK, or token storage.
- Implementing missing upstream metrics such as real LLM cost/revenue joins, GPU idle telemetry, provider payout aggregation, refund/issued-credit feed, or runway calculation.
- Changing `cost_attribution`, cost telemetry helper behavior, solver/billing hooks, credit ledger semantics, provider payout logic, or customer-facing billing behavior.
- Building the unified governance dashboard; Story 9.7 owns that.

## Acceptance Criteria

1. `tools/nfr_cost_alerts/nfr_cost_alert_contract.json` exists and validates as the canonical Story 9.3 NFR-COST contract.
2. Contract pins `source_story=9.3`, `alert_version=nfr_cost_redline_alerts_v1`, `nfr=NFR-COST`, `standard_cadence=quarterly`, and `breach_drill_required=true`.
3. Contract defines exactly five redline ids in this order: `llm_revenue_ratio`, `gpu_idle_rate`, `provider_share_revenue_ratio`, `refund_issued_rate`, `runway_months`.
4. Redline thresholds are pinned: LLM/revenue `>=0.30`, GPU idle `>=0.50`, provider share/revenue `>=0.50`, refund/issued credits `>=0.05`, runway months `<6`.
5. Each redline defines Prometheus alert metadata: alert name, PromQL expression, `for` duration, labels, annotations, severity, owner, and runbook path.
6. Contract defines required input signals per redline, including source system, expected metric name, unit, aggregation window, and current implementation state.
7. Contract defines DingTalk-ready payload requirements: markdown title, markdown text, redline id, severity, summary, runbook URL/path, evidence pointer, and no webhook token.
8. Contract defines Linear-ready ticket requirements: title, description, team key, label set, severity, owner, due date policy, evidence pointer, and no external issue id in static examples.
9. Contract defines observed cost telemetry state for `cost_attribution` SQL units, shared CostUnit enum, solver hook, billing hook, and Story 9.2 handoff.
10. Contract explicitly states it does not prove live Prometheus rule loading, real Alertmanager firing, real DingTalk delivery, real Linear issue creation, real production breach, real finance approval, or release approval.
11. Evidence schema and static example manifest exist under `tools/nfr_cost_alerts/`.
12. Static example manifest has `example_only=true`, `real_alert_fired=false`, `real_dingtalk_delivered=false`, `real_linear_created=false`, `release_approved=false`, and cannot claim real production breach, real external delivery, real issue creation, or real finance approval.
13. Optional real evidence path mode accepts only `reports/nfr-cost-alerts/<run_id>/alert_manifest.json` where directory name equals `run_id`.
14. Optional real evidence requires `example_only=false`, `redaction_reviewed=true`, valid `cadence_mode` (`quarterly` or `breach_drill`), all five redline evaluations, source snapshots, Prometheus alert evidence, DingTalk-ready payloads, Linear-ready payloads, and routing outcomes.
15. Every breached redline, failed alert evaluation, failed DingTalk-ready payload, failed Linear-ready payload, or missing required input signal must reference at least one finding with ticket refs.
16. Real evidence cannot mark `release_approved=true` while unresolved P0/P1/P2 NFR-COST findings remain open, in progress, or deferred.
17. Validator rejects tenant/user/customer ids, API keys, bearer tokens, cookies, passwords, webhook tokens, Linear tokens, credentialed URLs, production hostnames, absolute paths, directory traversal, raw logs, raw Prometheus labels, raw finance exports, prompts, provider payloads, and raw customer-identifying dimensions.
18. Validator discovers current committed cost telemetry substrate and fails if contract `observed_cost_telemetry_state` is stale.
19. Validator fails if any canonical redline is absent from the contract or evidence.
20. Validator fails if static examples claim real alert firing, real external delivery, real Linear issue creation, real finance approval, or production release approval.
21. Tests cover validator happy path, redline drift, observed-state drift, fake completion, unsafe evidence paths, leak rejection, missing alert evaluation, missing notification/ticket payloads, missing-ticket enforcement, release approval blocking, and CI workflow wiring.
22. Runbook documents local commands, quarterly flow, breach drill flow, redline thresholds, evidence path, Prometheus/Alertmanager capture, DingTalk/Linear-ready handoff, redaction rules, ticket policy, stop-ship rules, rollback, and Story 9.7 handoff.
23. `.github/workflows/ci.yml` exposes `nfr_cost_alerts` from `changes` outputs.
24. CI path filter `nfr_cost_alerts` covers `tools/nfr_cost_alerts/**`, `scripts/validate_nfr_cost_alerts.py`, `tests/test_nfr_cost_alerts.py`, `docs/runbooks/nfr-cost-alerts.md`, `reports/nfr-cost-alerts/**`, `.github/workflows/ci.yml`, `infra/local-init/10-cost-attribution.sql`, `packages/shared-py/opticloud_shared/cost_telemetry/**`, solver/billing route/model files that own current cost hooks, and Story 9.2 governance assets.
25. CI job `nfr-cost-alerts-validation` runs without `continue-on-error`.
26. CI job runs static validator, optional committed real evidence validation for every `reports/nfr-cost-alerts/**/alert_manifest.json`, and Python tests.
27. No new package dependency is added to root, services, or Python workspace.
28. No production Alertmanager, real DingTalk/Linear integration, Grafana dashboard, finance warehouse, GPU service, revenue aggregation service, Kubernetes manifest, database migration, OpenAPI, billing/solver business logic, provider payout logic, or customer-facing billing file is modified.
29. Local gates pass: `uv run python scripts/validate_nfr_cost_alerts.py`, `uv run pytest tests/test_nfr_cost_alerts.py -q`, and `git diff --check`.
30. Post-implementation code review covers boundary issues, drift issues, data consistency, dependency consistency, fake-completion risk, CI closure, no-leak guarantees, and test adequacy; findings are fixed or explicitly documented.
31. Story status flow is `ready-for-dev -> in-progress -> code-review -> done`; `done` is forbidden before GitHub CI passes, PR merges, remote branch is deleted, and local `main` is synced.
32. After merge/sync, story and sprint status are marked `done` only through a separate status-sync commit.

## Tasks / Subtasks

- [x] T1: Add NFR-COST alert contract and evidence schema (AC: 1-17)
  - [x] Create `tools/nfr_cost_alerts/nfr_cost_alert_contract.json`.
  - [x] Create `tools/nfr_cost_alerts/nfr_cost_alert_manifest.schema.json`.
  - [x] Create `tools/nfr_cost_alerts/nfr_cost_alert_manifest.example.json`.
  - [x] Encode five redlines, Prometheus alert metadata, DingTalk-ready and Linear-ready payload requirements, observed cost telemetry state, and non-completion boundaries.
  - [x] Encode public-safe evidence and missing/breached/failing ticket requirements.

- [x] T2: Add validator and unit tests (AC: 13-21)
  - [x] Implement `scripts/validate_nfr_cost_alerts.py` using only stdlib.
  - [x] Validate contract/schema/example and optional real evidence path mode.
  - [x] Discover committed cost telemetry substrate and compare it to contract `observed_cost_telemetry_state`.
  - [x] Add `tests/test_nfr_cost_alerts.py` with drift, leak, fake-completion, coverage, payload, ticket, release-blocking, and CI coverage tests.

- [x] T3: Add NFR-COST alert runbook (AC: 22)
  - [x] Document local/CI commands.
  - [x] Document quarterly and breach-drill flows.
  - [x] Document Prometheus/Alertmanager capture, evidence redaction, DingTalk/Linear-ready handoff, ticket policy, stop-ship rules, rollback, and Story 9.7 handoff.

- [x] T4: Add CI closure (AC: 23-28)
  - [x] Add `nfr_cost_alerts` output and path filter to `.github/workflows/ci.yml`.
  - [x] Add `nfr-cost-alerts-validation` job.
  - [x] Ensure current cost telemetry substrate changes trigger the validator.
  - [x] Confirm no new dependencies or out-of-scope implementation files are modified.

- [x] T5: Gates, review, and GitHub sync (AC: 29-32)
  - [x] Run local validation gates.
  - [x] Run post-implementation code review and fix/document findings.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [ ] Mark story and sprint status `done` only after merge/sync through a separate status-sync commit.

## Dev Notes

### Current Cost Telemetry Substrate

- `infra/local-init/10-cost-attribution.sql` creates `cost_attribution` with canonical units `llm_token`, `gpu_second`, and `solver_second`.
- `packages/shared-py/opticloud_shared/cost_telemetry/__init__.py` exposes `CostUnit`, `CostTelemetryEvent`, `validate_cost_event`, and `record_cost_event`.
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py::_record_solver_cost_attribution` writes best-effort `solver-orchestrator` `solver_second` rows for persisted terminal LP solve results.
- `apps/billing-service/src/billing_service/routes.py::_record_billing_cost_attribution` writes best-effort `billing-service` `solver_second` rows for successful first-run billing finalize.
- There is still no live source for LLM API cost/revenue ratio, GPU idle ratio, provider share/revenue ratio, refund/issued-credit ratio, or runway months. Contract must mark those input signals truthfully and route missing inputs to ticket-backed closure.

### Implementation Pattern To Reuse

- Follow Story 9.1/9.2 static governance pattern:
  - contract + schema + static example under `tools/...`
  - stdlib validator under `scripts/...`
  - focused pytest module under `tests/...`
  - runbook under `docs/runbooks/...`
  - dedicated CI path filter and hard gate
- Reuse 9.2 validator concepts: explicit semantic validation, no `jsonschema` dependency, optional `--evidence`, repo-state drift detection, fake-completion rejection, redaction checks, release approval blocking.
- Reuse 8.C.3 and 6.A.3 wording pattern for Linear-ready payloads: deterministic payloads are valid; real external mutation is not claimed unless a later story adds a relayer.

### Boundary Rules

- This story does not prove a real cost breach happened.
- This story does not prove Prometheus/Alertmanager loaded or fired production rules.
- This story does not send DingTalk messages or create Linear issues.
- This story does prove:
  - NFR-COST redlines, alert metadata and routing payloads have a canonical contract;
  - static examples cannot fake completion;
  - future evidence must include full redline coverage, source snapshots, alert/routing evidence, redaction and tickets;
  - CI detects drift in current cost telemetry substrate and governance assets.

### Suggested Commands

```powershell
uv run python scripts/validate_nfr_cost_alerts.py
uv run pytest tests/test_nfr_cost_alerts.py -q
git diff --check
```

## Definition Of Done

- Story has passed exactly 3 pre-implementation adversarial review rounds with revisions recorded after each round.
- Static NFR-COST alert contract, schema, example, validator, tests, runbook, and CI job exist.
- Validator catches fake completion, cost telemetry substrate drift, missing canonical redlines, missing alert/routing payloads, unsafe evidence paths, unresolved stop-ship findings, and sensitive data leakage.
- Local gates and GitHub CI pass.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Story and sprint status become `done` only after PR CI green, merge, remote branch deletion, local main sync, and a separate status-sync commit.

## Story Review Log

### Round 1: Boundary And Fake-Completion Review

Findings fixed:

- Initial Epic wording could be interpreted as shipping real Alertmanager, DingTalk webhook, and Linear API automation. Revised scope to static governance, deterministic ready payloads, optional real evidence validation, and no external calls or secret handling.
- Initial example evidence could fake a production breach or external delivery. Added `example_only=true`, `real_alert_fired=false`, `real_dingtalk_delivered=false`, `real_linear_created=false`, and static fake-completion rejection requirements.
- Initial cost alert wording could imply the missing upstream finance/GPU/LLM signals already exist. Added input-signal states and ticket-backed closure for missing signals.

Status: PASS after fixes.

### Round 2: Drift And Data Consistency Review

Findings fixed:

- Initial contract could drift from the current cost telemetry substrate. Added validator requirements to discover SQL units, shared CostUnit enum, solver hook, billing hook, and 9.2 handoff.
- Initial redline set omitted cash runway from the Epic summary. Added exactly five canonical redline ids and pinned threshold comparators/values.
- Initial breach handling allowed alerts without closure. Added ticket requirements for every breached redline, failed alert evaluation, failed DingTalk/Linear-ready payload, or missing required input signal, plus release approval blocking for unresolved P0/P1/P2 findings.

Status: PASS after fixes.

### Round 3: Dependency, CI, And Closure Review

Findings fixed:

- Initial story did not explicitly ban `jsonschema`, Prometheus clients, DingTalk SDKs, Linear SDKs, cloud clients, workers, schedulers or new dependencies. Added no-new-dependency and no external-integration constraints.
- Initial CI closure did not include cost telemetry substrate files and Story 9.2 governance handoff. Added path-filter coverage for cost SQL, shared cost telemetry, solver/billing hook files, and 9.2 governance assets.
- Initial lifecycle mentioned code review but not the user's strict GitHub/status-sync ordering. Added status flow and post-merge-only separate `done` status-sync requirement.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/9-3-nfr-cost-alerts`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base skill instructions and project config.
- Story creation analyzed Epic 9.3, PRD/readiness NFR-COST definitions, Story M2.3 cost attribution substrate, Story 5.A.8 billing cost hook, Story 9.2 Prometheus metric audit handoff, current CI workflow, and current cost telemetry code paths.
- 2026-06-04 - Completed pre-implementation adversarial review round 1 and revised external-integration, fake-completion, and missing-signal boundaries.
- 2026-06-04 - Completed pre-implementation adversarial review round 2 and revised cost telemetry drift detection, canonical redline coverage, ticket closure, and stop-ship rules.
- 2026-06-04 - Completed pre-implementation adversarial review round 3 and revised dependency, CI trigger, and GitHub/status-sync closure requirements.
- 2026-06-04 - Story moved to in-progress after exactly three pre-implementation review rounds.
- 2026-06-04 - Red phase: `uv run pytest tests/test_nfr_cost_alerts.py -q` failed because validator, runbook, and CI wiring did not exist yet.
- 2026-06-04 - Implemented NFR-COST alert contract/schema/example, stdlib validator, runbook, tests, and CI `nfr-cost-alerts-validation` hard gate.
- 2026-06-04 - Focused gates passed: `uv run python scripts/validate_nfr_cost_alerts.py`, `uv run pytest tests/test_nfr_cost_alerts.py -q` (15 passed), and `git diff --check`.
- 2026-06-04 - Post-implementation code review completed; fixed Story 9.2 handoff filter gap by adding Prometheus validator/tests/reports to `nfr_cost_alerts` CI triggers and validator coverage, then reran all local gates successfully.

### Completion Notes List

- Initial story created.
- Exactly three pre-implementation adversarial review rounds completed; story is ready for implementation.
- Story moved to in-progress after exactly three pre-implementation review rounds.
- Static contract/schema/example, validator, tests, runbook, and CI hard gate implemented.
- Local validation gates passed before post-implementation review.
- Post-implementation code review completed; CI handoff filter gap fixed and gates rerun.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/stories/9-3-nfr-cost-alerts.md`
- `_bmad-output/stories/sprint-status.yaml`
- `docs/runbooks/nfr-cost-alerts.md`
- `scripts/validate_nfr_cost_alerts.py`
- `tests/test_nfr_cost_alerts.py`
- `tools/nfr_cost_alerts/nfr_cost_alert_contract.json`
- `tools/nfr_cost_alerts/nfr_cost_alert_manifest.schema.json`
- `tools/nfr_cost_alerts/nfr_cost_alert_manifest.example.json`

## Change Log

- 2026-06-04 - Initial Story 9.3 created.
- 2026-06-04 - Round 1 pre-implementation review revised external-integration, fake-completion, and missing-signal boundaries.
- 2026-06-04 - Round 2 pre-implementation review revised drift detection, canonical redline coverage, ticket closure, and stop-ship rules.
- 2026-06-04 - Round 3 pre-implementation review revised dependency, CI trigger, and status-sync closure.
- 2026-06-04 - Story status moved to in-progress after exactly three pre-implementation review rounds.
- 2026-06-04 - Implemented NFR-COST alert contract, evidence schema/example, validator, tests, runbook, and CI hard gate.
- 2026-06-04 - Post-implementation code review fixed Story 9.2 handoff CI filter coverage; story moved to `code-review` pending GitHub sync.

## Post-Implementation Code Review

### Blind Hunter - Boundary And Fake-Completion Review

Findings:

- No remaining issue found in static example boundaries: committed example remains `example_only=true`, `real_alert_fired=false`, `real_dingtalk_delivered=false`, `real_linear_created=false`, and `release_approved=false`.
- No remaining issue found in out-of-scope boundaries: implementation does not add production Alertmanager, real DingTalk/Linear integration, Grafana dashboard, finance warehouse, GPU service, database migration, OpenAPI change, billing/solver business logic, or dependencies.

### Edge Case Hunter - Drift And Data Review

Findings:

- [x] P2 fixed: `nfr_cost_alerts` CI path filter originally covered Story 9.2 `tools/prometheus_metric_audit/**` and runbook, but missed the 9.2 validator, tests, and evidence report path. This could let Prometheus audit governance drift without rerunning the NFR-COST alert validator. Added `scripts/validate_prometheus_metric_audit.py`, `tests/test_prometheus_metric_audit.py`, and `reports/prometheus-metric-audit/**` to the path filter and validator assertions, with regression coverage.

### Acceptance Auditor - AC Closure Review

Findings:

- No remaining issue found against AC 1-28: static assets, validator, tests, runbook, and CI job are present and locally validated; no new dependencies or out-of-scope runtime files changed.
- AC 29-30 closed locally: validation gates pass and post-implementation review findings are fixed.
- AC 31-32 remain pending GitHub sync by design: story is `code-review`, not `done`.

Outcome: PASS after fixes; awaiting GitHub sync.
