---
story_key: 9-7-governance-dashboard
epic_num: 9
story_num: 7
epic_name: NFR Governance
status: code-review
baseline_commit: b2fe321dadeff8afba30a3bf4fd313c3b1e5eb79
priority: High
type: Cross-cutting governance dashboard contract
created_by: bmad-create-story
created_at: 2026-06-05
owner: PM / SRE / Security / UX / Compliance
sources:
  - _bmad-output/planning/epics.md (Epic 9 / Story 9.7)
  - _bmad-output/stories/9-1-axe-core-quarterly-audit.md
  - _bmad-output/stories/9-2-prometheus-metric-audit.md
  - _bmad-output/stories/9-3-nfr-cost-alerts.md
  - _bmad-output/stories/9-4-nfr-s-p0-drills.md
  - _bmad-output/stories/9-5-wcag-2-2-upgrade-path.md
  - _bmad-output/stories/9-6-error-i18n-audit.md
  - tools/a11y_audit/quarterly_a11y_contract.json
  - tools/prometheus_metric_audit/business_metric_audit_contract.json
  - tools/nfr_cost_alerts/nfr_cost_alert_contract.json
  - tools/nfr_security_p0_drills/nfr_security_p0_drill_contract.json
  - tools/wcag_2_2_upgrade/wcag_2_2_upgrade_contract.json
  - tools/error_i18n_audit/error_i18n_audit_contract.json
  - .github/workflows/ci.yml
---

# Story 9.7 - Cross-cutting Governance Dashboard

Status: code-review

## Story

**作为** PM / Security / UX / SRE / Compliance governance owner，
**我希望** 9.1-9.6 的 NFR governance signals 被统一成 Grafana-ready dashboard contract、panel catalog、evidence manifest、runbook 和 CI hard gate，
**从而** PM/Sec/UX/SRE 查看统一 dashboard 时能看到 a11y、cost、compliance、observability、security drill 和 error-i18n KPIs 的同一口径状态，而不是每个治理 story 各自散落、漂移或在静态示例里伪造真实 Grafana 发布。

## Context

Epic 9.7 原始 AC：Given Grafana / When PM/Sec/UX/SRE 看 / Then 统一 dashboard 含 a11y / cost / compliance / observability KPIs。

Story 9.1-9.6 已交付一组静态 governance contracts、validators、runbooks、CI gates 和 optional real evidence modes：

- 9.1：quarterly a11y audit，UI axe gate，6 a11y profiles，4 sub-persona sampling。
- 9.2：Prometheus business metric completeness audit，NFR-O1 metric catalog，Grafana/PromQL review evidence。
- 9.3：NFR-COST red-line alert governance，five redlines，DingTalk-ready / Linear-ready payloads。
- 9.4：NFR-S P0 drill governance，three P0 drill scenarios，24h postmortem timeline。
- 9.5：WCAG 2.2 P78 upgrade path，4 project criteria and full-WCAG boundary.
- 9.6：FG1.3 error i18n quarterly audit，scan classes, dictionary/catalog parity, legacy backlog register.

当前仓库仍没有真实 Grafana deployment、dashboard JSON provisioning、Prometheus datasource token、Grafana API token、dashboard screenshot capture automation、PM/Sec/UX/SRE real review session 或外部 ticket creation。因此本 story 的闭环是 **Grafana-ready unified dashboard governance specification**，不是伪造一个已经发布的真实 Grafana dashboard。

## Scope

1. Add static governance dashboard assets under `tools/governance_dashboard/`.
   - Contract pins `source_story=9.7`, `dashboard_version=governance_dashboard_v1`, `epic=9`, `standard_cadence=quarterly`, `dashboard_intent=grafana_ready_governance_overview`.
   - Contract aggregates exactly six upstream governance sources: 9.1 a11y audit, 9.2 observability metric audit, 9.3 NFR-COST redlines, 9.4 NFR-S P0 drills, 9.5 WCAG 2.2 upgrade path, 9.6 error i18n audit.
   - Contract defines viewer roles: PM, Security, UX, SRE, Compliance.
   - Contract defines KPI groups: `a11y`, `cost`, `compliance`, `observability`, `security`, and `error_i18n`.
   - Contract defines Grafana-ready dashboard metadata, panel catalog, source manifest links, freshness rules, stop-ship rollup rules, and fake-completion boundaries.
2. Add dashboard evidence schema and static example manifest.
   - Static example must be `example_only=true`.
   - Static example cannot claim real Grafana publication, real datasource connection, real PM/Sec/UX/SRE review, real release approval, real external ticket creation, or real evidence aggregation completion.
   - Real evidence path is only `reports/governance-dashboard/<run_id>/dashboard_manifest.json`, directory name must equal `run_id`.
   - Real evidence must include all six KPI groups, all required panels, source snapshot references, Grafana review records, role review records, findings, ticket refs, redaction review, and release gate.
3. Add `scripts/validate_governance_dashboard.py` using stdlib only.
   - Validate contract/schema/example, optional real evidence path mode, upstream contract presence, observed upstream source state, and CI wiring.
   - Discover upstream contract metadata from committed JSON and fail when 9.1-9.6 source paths, source stories, versions, evidence paths, or boundaries drift from the dashboard contract.
   - Validate each required KPI group maps to at least one panel, each panel maps to an upstream source, and PM/Sec/UX/SRE/Compliance role coverage remains complete.
4. Add `tests/test_governance_dashboard.py`.
   - Cover validator happy path, upstream-source drift, missing KPI group, missing panel, role coverage drift, fake completion, unsafe evidence path, sensitive-value rejection, real evidence completeness, ticket requirements, release blocking, and CI wiring.
5. Add `docs/runbooks/governance-dashboard.md`.
   - Document local/CI commands, quarterly dashboard update flow, Grafana-ready import/provisioning handoff, source contracts, panel ownership, freshness thresholds, redaction rules, ticket policy, stop-ship rules, rollback, and handoff to Story 9.8 graded protection evidence.
6. Update `.github/workflows/ci.yml`.
   - Add `governance_dashboard` output and path filter.
   - Add `governance-dashboard-validation` job without `continue-on-error`.
   - Job runs static validator, optional committed real evidence validation, focused pytest, and no external Grafana/Prometheus calls.
7. Do not add new npm/Python dependencies.
8. Do not implement real Grafana dashboard JSON provisioning, Grafana API calls, Prometheus datasource secrets, browser screenshot capture, backend services, database migrations, OpenAPI, web UI, billing/auth/provider/solver business logic, or external ticket integration.

## Out Of Scope

- Publishing a real Grafana dashboard or committing real Grafana API tokens/datasource credentials.
- Running Prometheus, Grafana, Loki, Tempo, browser screenshot tools, Kubernetes, cloud APIs, or production/staging network calls in CI.
- Claiming a real PM/Sec/UX/SRE review happened through static examples.
- Creating real GitHub/Linear/DingTalk tickets automatically.
- Replacing the underlying 9.1-9.6 validators or changing their evidence schemas.
- Building an in-app governance dashboard in `apps/web`; Epic 9.7 is Grafana-ready governance closure.
- Completing Story 9.8 graded protection evidence; this story only provides dashboard handoff slots.

## Acceptance Criteria

1. `tools/governance_dashboard/governance_dashboard_contract.json` exists and validates as canonical Story 9.7 contract.
2. Contract pins `source_story=9.7`, `dashboard_version=governance_dashboard_v1`, `epic=9`, `standard_cadence=quarterly`, and `dashboard_intent=grafana_ready_governance_overview`.
3. Contract defines exactly six upstream source ids in order: `a11y_quarterly_audit`, `prometheus_metric_audit`, `nfr_cost_alerts`, `nfr_security_p0_drills`, `wcag_2_2_upgrade_path`, and `error_i18n_audit`.
4. Each upstream source records story id, owner, contract path, validator path, runbook path, evidence report directory, manifest filename, CI job name, and dashboard handoff boundary.
5. Contract observed upstream source state is discovered from committed 9.1-9.6 contracts and fails on source story, version, evidence path, or boundary drift.
6. Contract defines viewer roles exactly as `PM`, `Security`, `UX`, `SRE`, and `Compliance`.
7. Contract defines KPI groups exactly as `a11y`, `cost`, `compliance`, `observability`, `security`, and `error_i18n`.
8. Contract defines at least one Grafana-ready panel per KPI group, and every panel references a valid upstream source id.
9. Required panels include quarterly axe violation status, WCAG 2.2 upgrade readiness, Prometheus metric coverage, NFR-COST redline state, NFR-S P0 drill state, and error i18n audit state.
10. Panel metadata includes `panel_id`, `title`, `kpi_group`, `viewer_roles`, `upstream_source_id`, `freshness_sla_days`, `data_source_mode`, `query_or_transform`, `stop_ship_severities`, and `runbook_path`.
11. Contract defines rollup statuses: `green`, `yellow`, `red`, `unknown`, and `not_run`.
12. Contract defines stop-ship rollup rules: unresolved P0/P1/P2 findings from any source force dashboard status `red`; stale required source evidence forces at least `yellow`; missing required source evidence forces `red`.
13. Contract explicitly states it does not prove real Grafana publication, real datasource connection, real PM/Sec/UX/SRE review, real production release approval, real external ticket creation, or completed quarterly evidence aggregation.
14. Evidence schema and static example manifest exist under `tools/governance_dashboard/`.
15. Static example has `example_only=true`, `real_grafana_dashboard_published=false`, `real_datasource_connected=false`, `real_role_review_completed=false`, `real_evidence_aggregation_completed=false`, and `release_approved=false`.
16. Static example cannot claim real Grafana publication, real datasource connection, real role review, real quarterly aggregation, real external ticket creation, production release approval, or all source findings resolved.
17. Optional real evidence path mode accepts only `reports/governance-dashboard/<run_id>/dashboard_manifest.json`.
18. Optional real evidence requires `example_only=false`, `redaction_reviewed=true`, all six KPI groups, all required panels, source snapshots for all six upstream sources, Grafana review records, role review records for all viewer roles, findings, and ticket refs.
19. Every missing/stale/failed panel, missing role review, missing source snapshot, failed Grafana review, or red/yellow rollup must reference at least one finding with ticket refs.
20. Real evidence cannot mark `release_approved=true` while unresolved P0/P1/P2 dashboard findings remain open, in progress, or deferred.
21. Validator rejects tenant/user/customer ids, emails, phone numbers, API keys, bearer tokens, cookies, passwords, secrets, Grafana tokens, Prometheus datasource credentials, dashboard share tokens, credentialed URLs, production hostnames, absolute paths, directory traversal, raw logs, raw screenshots with embedded secrets, prompt/provider payloads, raw metric labels, and raw customer-identifying dimensions.
22. Validator rejects dashboard panels that use `production_live`, `grafana_api`, or `external_network` data source modes in static validation; allowed modes are `contract_static`, `evidence_manifest`, and `manual_review`.
23. `.github/workflows/ci.yml` exposes `governance_dashboard` from `changes` outputs.
24. CI path filter `governance_dashboard` covers `tools/governance_dashboard/**`, `scripts/validate_governance_dashboard.py`, `tests/test_governance_dashboard.py`, `docs/runbooks/governance-dashboard.md`, `reports/governance-dashboard/**`, `.github/workflows/ci.yml`, and all 9.1-9.6 governance contract/schema/example/validator/test/runbook/evidence paths.
25. CI job `governance-dashboard-validation` runs without `continue-on-error`.
26. CI job runs static validator, optional committed real evidence validation for every `reports/governance-dashboard/**/dashboard_manifest.json`, and focused Python tests.
27. No new npm/Python dependency is added and lockfiles remain unchanged.
28. No real Grafana dashboard provisioning, datasource secret, browser screenshot tooling, backend service, database migration, OpenAPI, web UI, billing/auth/provider/solver business logic, or external ticket integration file is modified.
29. Local gates pass: `uv run python scripts/validate_governance_dashboard.py`, `uv run pytest tests/test_governance_dashboard.py -q`, and `git diff --check`.
30. Post-implementation code review covers boundary issues, drift issues, data consistency, dependency consistency, fake-completion risk, CI closure, no-leak guarantees, KPI source completeness, rollup correctness, and test adequacy; findings are fixed or explicitly documented.
31. Story status flow is `ready-for-dev -> in-progress -> code-review -> done`.
32. `done` is forbidden before GitHub CI passes, PR merges, remote branch is deleted, and local `main` is synced.
33. After merge/sync, story and sprint status are marked `done` only through a separate status-sync commit.

## Tasks / Subtasks

- [x] T1: Add governance dashboard contract/schema/example (AC: 1-22)
  - [x] Create `tools/governance_dashboard/governance_dashboard_contract.json`.
  - [x] Create `tools/governance_dashboard/governance_dashboard_manifest.schema.json`.
  - [x] Create `tools/governance_dashboard/governance_dashboard_manifest.example.json`.
  - [x] Encode six upstream source contracts, viewer roles, KPI groups, panel catalog, rollup rules, freshness rules, and fake-completion boundaries.
  - [x] Encode public-safe evidence and ticket-backed closure rules.

- [x] T2: Add validator and focused tests (AC: 17-26)
  - [x] Implement `scripts/validate_governance_dashboard.py` using stdlib only.
  - [x] Validate contract/schema/example and optional real evidence path mode.
  - [x] Discover committed 9.1-9.6 upstream source metadata and compare it to contract observed state.
  - [x] Add `tests/test_governance_dashboard.py` with drift, leak, fake-completion, completeness, ticket, release-blocking, data-source-mode, and CI coverage tests.

- [x] T3: Add runbook and CI closure (AC: 23-29)
  - [x] Add `docs/runbooks/governance-dashboard.md`.
  - [x] Add `governance_dashboard` output/path filter and `governance-dashboard-validation` job to `.github/workflows/ci.yml`.
  - [x] Ensure upstream 9.1-9.6 governance asset changes trigger the dashboard validator.
  - [x] Confirm no new dependencies or out-of-scope implementation files are modified.

- [ ] T4: Gates, review, and GitHub sync (AC: 29-33)
  - [x] Run local validation gates.
  - [x] Run post-implementation code review and fix/document findings.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [ ] Mark story and sprint status `done` only after merge/sync through a separate status-sync commit.

## Dev Notes

### Existing Governance Sources To Reuse

- `tools/a11y_audit/quarterly_a11y_contract.json` is the 9.1 NFR-A quarterly audit source.
- `tools/prometheus_metric_audit/business_metric_audit_contract.json` is the 9.2 NFR-O metric source and already includes Grafana/PromQL review fields.
- `tools/nfr_cost_alerts/nfr_cost_alert_contract.json` is the 9.3 NFR-COST redline source and includes Story 9.7 handoff boundaries.
- `tools/nfr_security_p0_drills/nfr_security_p0_drill_contract.json` is the 9.4 NFR-S P0 drill source and includes Story 9.7 handoff boundaries.
- `tools/wcag_2_2_upgrade/wcag_2_2_upgrade_contract.json` is the 9.5 WCAG 2.2 upgrade readiness source.
- `tools/error_i18n_audit/error_i18n_audit_contract.json` is the 9.6 FG1.3 / NFR-COMPLIANCE source and includes Story 9.7 handoff.

### Implementation Pattern To Reuse

- Follow Story 9.1-9.6 static governance pattern:
  - contract + schema + static example under `tools/<topic>/`
  - stdlib validator under `scripts/`
  - focused pytest module under `tests/`
  - runbook under `docs/runbooks/`
  - dedicated CI path filter and hard gate
- Use semantic validation instead of adding `jsonschema`.
- Keep optional real evidence validation opt-in via `--evidence`.
- Reuse block-scoped CI filter/job validation helpers from 9.2-9.6 validators.
- Keep dashboard source state derived from upstream contract JSON, not duplicated manually without validator checks.

### Boundary Rules

- This story does not prove a real Grafana dashboard was published.
- This story does not connect to Prometheus/Grafana or any external network.
- This story does not prove PM/Sec/UX/SRE actually reviewed a dashboard.
- This story does not replace upstream 9.1-9.6 validators or evidence schemas.
- This story proves:
  - every 9.1-9.6 governance source has a single dashboard handoff record;
  - KPI panels and rollup rules are pinned and testable;
  - static examples cannot fake real publication/review/aggregation;
  - CI catches drift in dashboard assets and upstream governance source contracts.

### Suggested Commands

```powershell
uv run python scripts/validate_governance_dashboard.py
uv run pytest tests/test_governance_dashboard.py -q
git diff --check
```

## Definition Of Done

- Story has passed exactly 3 pre-implementation adversarial review rounds with revisions recorded after each round.
- Governance dashboard contract/schema/example, validator, tests, runbook, and CI hard gate exist.
- Validator catches fake completion, upstream-source drift, missing KPI groups, missing required panels, missing role reviews, unsafe evidence paths, unresolved stop-ship findings, sensitive data leakage, invalid data source modes, ticket gaps, and CI closure drift.
- Local gates and GitHub CI pass.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Story and sprint status become `done` only after PR CI green, merge, remote branch deletion, local main sync, and a separate status-sync commit.

## Story Review Log

### Round 1: Boundary And Fake-Completion Review

Findings fixed:

- Initial Epic wording could be read as shipping a real Grafana dashboard. Revised scope to a Grafana-ready dashboard contract and evidence gate, with real publication explicitly out of scope.
- Initial dashboard evidence could allow static examples to imply real PM/Sec/UX/SRE review or real data source connection. Added fake-completion flags and static rejection requirements.
- Initial implementation boundary could drift into app UI or real Grafana provisioning. Added out-of-scope constraints for web UI, Grafana API calls, datasource secrets, screenshot tooling, and external network calls.

Status: PASS after fixes.

### Round 2: Drift, Data Consistency, And Rollup Review

Findings fixed:

- Initial source list could drift from 9.1-9.6 contracts. Added validator requirements to discover upstream contract metadata and compare source stories, versions, evidence paths, and boundaries to dashboard contract observed state.
- Initial KPI grouping could omit compliance or double-count a11y/WCAG. Added exact six KPI groups and required panels, including separate quarterly axe and WCAG 2.2 readiness panels.
- Initial dashboard status rollup could hide stop-ship findings. Added rules that unresolved P0/P1/P2 source findings force red, stale required evidence forces at least yellow, and missing required source evidence forces red.

Status: PASS after fixes.

### Round 3: Dependency, CI, And Closure Review

Findings fixed:

- Initial story did not explicitly ban dashboard/runtime dependencies. Added no-new-dependency and no Grafana/Prometheus/browser tooling constraints.
- Initial CI closure did not guarantee upstream 9.1-9.6 governance drift would trigger the dashboard validator. Added required path-filter coverage for all upstream contract/schema/example/validator/test/runbook/evidence paths.
- Initial lifecycle did not restate the user's strict GitHub/status-sync ordering. Added status flow and post-merge-only separate `done` status-sync requirement.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/9-7-governance-dashboard`.
- Baseline commit: `b2fe321dadeff8afba30a3bf4fd313c3b1e5eb79`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base skill instructions and project config.
- Story creation analyzed Epic 9.7, Story 9.1-9.6 governance contracts, existing 9.x validator/test/runbook/CI patterns, and current CI workflow.
- 2026-06-05 - Completed pre-implementation adversarial review round 1 and revised real Grafana publication, fake-completion, and implementation boundaries.
- 2026-06-05 - Completed pre-implementation adversarial review round 2 and revised upstream-source drift detection, KPI grouping, required panels, and rollup rules.
- 2026-06-05 - Completed pre-implementation adversarial review round 3 and revised dependency, CI trigger, and GitHub/status-sync closure requirements.
- 2026-06-05 - Story moved to in-progress after exactly three pre-implementation review rounds.
- 2026-06-05 - RED confirmed: `uv run pytest tests/test_governance_dashboard.py -q` failed with 17 expected failures before validator/assets/runbook/CI existed.
- 2026-06-05 - Implemented governance dashboard contract/schema/example, stdlib validator, focused tests, runbook, and CI hard gate.
- 2026-06-05 - Local gates passed: `uv run python scripts/validate_governance_dashboard.py`, `uv run pytest tests/test_governance_dashboard.py -q` (17 passed), and `git diff --check`.
- 2026-06-05 - Post-implementation code review fixed real-evidence boundary so real evidence does not require or imply real Grafana publication/datasource connection; focused test count is now 18.
- 2026-06-05 - Post-review gates passed: `uv run python scripts/validate_governance_dashboard.py`, `uv run pytest tests/test_governance_dashboard.py -q` (18 passed), `uv run ruff check scripts/validate_governance_dashboard.py tests/test_governance_dashboard.py`, and `git diff --check`.

### Completion Notes List

- Initial story created.
- Exactly three pre-implementation adversarial review rounds completed; story is ready for implementation.
- Story moved to in-progress after exactly three pre-implementation review rounds.
- Added Story 9.7 cross-cutting governance dashboard assets, validator, tests, runbook, and CI hard gate.
- Post-implementation code review completed. Fixed real-evidence boundary so dashboard evidence can prove redacted aggregation/role review without falsely requiring real Grafana publication or datasource connection.
- Story moved to code-review after local gates passed; `done` remains blocked until PR CI, merge, remote branch deletion, local main sync, and separate status-sync commit.

## Post-Implementation Code Review

Outcome: Changes requested, then fixed.

Findings fixed:

- Real-evidence boundary gap: validator initially required `real_grafana_dashboard_published=true` and `real_datasource_connected=true` for real dashboard evidence. That contradicted Story 9.7's Grafana-ready boundary and could force fake-publication claims. Fixed by requiring only redaction review, real role review, and real evidence aggregation for real evidence; added regression coverage that real evidence passes with Grafana publication and datasource connection still false.

Residual risk:

- Real Grafana dashboard provisioning remains intentionally out of scope. A later provisioning story must convert the pinned panel catalog into Grafana JSON and handle real datasource credentials outside this static CI gate.

### File List

- `_bmad-output/stories/9-7-governance-dashboard.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `docs/runbooks/governance-dashboard.md`
- `scripts/validate_governance_dashboard.py`
- `tests/test_governance_dashboard.py`
- `tools/governance_dashboard/governance_dashboard_contract.json`
- `tools/governance_dashboard/governance_dashboard_manifest.schema.json`
- `tools/governance_dashboard/governance_dashboard_manifest.example.json`

## Change Log

- 2026-06-05 - Initial Story 9.7 created.
- 2026-06-05 - Round 1 pre-implementation review revised real Grafana publication, fake-completion, and implementation boundaries.
- 2026-06-05 - Round 2 pre-implementation review revised upstream-source drift detection, KPI grouping, required panels, and rollup rules.
- 2026-06-05 - Round 3 pre-implementation review revised dependency, CI trigger, and status-sync closure.
- 2026-06-05 - Story status moved to in-progress after exactly three pre-implementation review rounds.
- 2026-06-05 - Implemented governance dashboard contract, manifest schema/example, validator, tests, runbook, and CI hard gate.
- 2026-06-05 - Post-implementation review fixed real-evidence Grafana publication/datasource fake-completion boundary; story moved to `code-review` pending GitHub sync.
