---
story_key: 9-4-nfr-s-p0-drills
epic_num: 9
story_num: 4
epic_name: NFR Governance
status: done
baseline_commit: a82010578fdde4ba83eafc9d330bc3e72ff2922e
priority: High
type: NFR-S quarterly P0 security drill governance
created_by: bmad-create-story
created_at: 2026-06-05
owner: Security / NFR-S
sources:
  - _bmad-output/planning/epics.md (Epic 9 / Story 9.4 / NFR-S P0 drills)
  - _bmad-output/planning/prd.md (§2.4 P0 security zero tolerance; O2 24h Postmortem)
  - _bmad-output/stories/m3-7-sandbox-security-audit.md
  - _bmad-output/stories/8-a-3-24h-postmortem.md
  - _bmad-output/stories/m2-2a-billing-critical-tests.md
  - _bmad-output/stories/5-a-7-reconciliation-cron.md
  - infra/sandbox-security/audit_plan.json
  - tools/incidents/j3_sre_incident_contract.json
  - infra/local-init/03-billing-schema.sql
  - apps/billing-service/src/billing_service/models.py
  - apps/billing-service/src/billing_service/saga_orchestrator.py
  - apps/billing-service/src/billing_service/routes.py
  - .github/workflows/ci.yml
---

# Story 9.4 - NFR-S P0 Quarterly Drills

Status: done

## Story

**作为** Security / NFR-S owner，
**我希望** 沙箱越权、数据外泄、资金账本错三类 P0 安全事件形成季度演练合同、SOP、24h Postmortem 时间线和 evidence 验证闭环，
**从而** 三类零容忍风险不会只停留在 PRD 口号里，而是在不伪造真实生产事故、不运行危险 exploit、不暴露敏感数据的前提下，持续留下可审计的演练证据和未闭环票据。

## Context

Epic 9.4 原始 AC：Given 沙箱越权 / 数据外泄 / 资金账本错三类 / When quarterly drill / Then SOP 执行 + Postmortem template + 24h timeline。

PRD §2.4 将三类 P0 安全事件定义为：沙箱越权、数据外泄、资金账本错，目标是重大 P0 安全事件 0 起/季度；P0 发生时必须 24h 内公开 Postmortem。已有上游资产：

- M3.7 已交付 sandbox security audit 静态合同、15 个 attack scenario、未来 pentest evidence schema 和 CI gate，但不证明真实 gVisor/AppArmor/seccomp/K8s runtime enforcement。
- 8.A.3 已交付公开 P0 Postmortem 页面和 24h SLA helper，但不提供季度演练治理。
- Billing 侧已有 `saga_instances`、`credit_transactions`、reconciler、critical audit tests 和 refund/rollback flows，但没有三类 P0 演练的统一证据合同。

当前仓库仍没有真实生产 incident commander 工具、on-call paging、DingTalk/Linear relayer、漏洞扫描平台、SIEM、生产演练 runner、外部审计签字或真实客户影响数据。因此本 story 的最小闭环是静态治理与 evidence gate：

- canonical contract 定义三类 P0 drill、SOP gates、24h timeline、postmortem template、owner、closure policy 和 observed repo state。
- committed example 必须是 `example_only=true`，不得声称真实 P0、真实演练、真实公开 postmortem、真实客户影响、真实外部通知、真实退款或真实 release approval。
- optional real evidence 只允许放在 `reports/nfr-security-p0-drills/<run_id>/drill_manifest.json`，必须 redacted、三类场景全覆盖、失败项带 ticket refs、24h timeline 可验证。
- CI 只做静态验证，不运行 exploit、容器逃逸、Docker/K8s/gVisor、生产网络或外部通知。

## Scope

1. Add static NFR-S P0 drill governance assets under `tools/nfr_security_p0_drills/`.
   - Contract pins `source_story=9.4`, `drill_version=nfr_security_p0_drills_v1`, `nfr=NFR-S`, quarterly cadence, lite annual cadence, three canonical P0 classes, SOP gates, 24h postmortem SLA, evidence path, and observed repo state.
   - Contract includes exactly three scenario ids in order: `sandbox_privilege_escape`, `data_exfiltration`, and `billing_ledger_corruption`.
   - Contract links each scenario to existing repo substrates without claiming those substrates prove a real quarterly drill.
2. Add evidence schema and static example manifest.
   - Example manifest is static and `example_only=true`.
   - Real evidence, when supplied via validator flag, must live under `reports/nfr-security-p0-drills/<run_id>/drill_manifest.json`.
   - Real evidence requires all three scenarios, SOP execution status, containment decisions, timeline records, postmortem templates, findings, ticket refs, source snapshot metadata, and redaction review.
   - Evidence must be public-safe: no tenant/user/customer ids, emails, phone numbers, API keys, bearer tokens, cookies, passwords, webhook tokens, Linear tokens, production hostnames, absolute paths, raw logs, raw SQL dumps, raw ledger rows, raw customer prompts/files, exploit payloads, provider payloads, or credentialed URLs.
3. Add `scripts/validate_nfr_security_p0_drills.py` using stdlib only.
   - Validate contract/schema/example and optional real evidence path mode.
   - Discover current committed security substrates from M3.7 sandbox plan, J3 incident contract, public postmortem model, billing SQL/model/orchestrator/routes, and current CI wiring.
   - Fail when observed repo state drifts, any canonical scenario is removed, fake completion appears in static examples, unresolved P0/P1/P2 findings coexist with `release_approved=true`, or external delivery/public postmortem is claimed without evidence.
4. Add `tests/test_nfr_security_p0_drills.py`.
   - Cover validator happy path, scenario drift, observed-state drift, fake completion, unsafe evidence path, leak rejection, missing scenario evidence, missing timeline/postmortem, missing-ticket enforcement, release blocking, exploit payload rejection, and CI wiring.
5. Add `docs/runbooks/nfr-security-p0-drills.md`.
   - Document local/CI commands, quarterly and annual-lite flow, the three P0 scenarios, SOP execution, containment evidence, 24h timeline, postmortem template, redaction rules, ticket policy, stop-ship policy, rollback, and handoff to Story 9.7 dashboard.
6. Update `.github/workflows/ci.yml`.
   - Add `nfr_security_p0_drills` path filter and `nfr-security-p0-drills-validation` job.
   - Job hard-gates static validator, optional committed real evidence validation, and Python tests.
7. Do not add new Python/npm dependencies.
8. Do not implement production incident automation, exploit runners, real sandbox escape tests, real data exfiltration tests, real ledger mutation drills, DingTalk/Linear calls, public Status Page publication, admin CRUD, DB migrations, OpenAPI changes, or service business logic.

## Out Of Scope

- Running fork bombs, namespace probes, Docker socket probes, mount commands, privilege escalation attempts, malware samples, credential probes, real exfiltration, or ledger-corrupting writes.
- Calling production/staging services, Prometheus, Grafana, DingTalk, Linear, Status Page delivery, paging, SIEM, cloud APIs, or external networks in CI.
- Claiming a real P0 happened, a real quarterly drill passed, a real public Postmortem was published, a real customer was affected, a real refund/compensation was executed, or a real release was approved through committed examples.
- Adding a live incident command system, ticket relayer, scheduler, queue, webhook secret, OAuth app, SaaS SDK, storage of operator notes, or token storage.
- Modifying sandbox-runner runtime behavior, billing ledger behavior, public status page implementation, database schemas, migrations, OpenAPI, user-facing billing, auth, provider, or solver logic.
- Building the unified governance dashboard; Story 9.7 owns that.

## Acceptance Criteria

1. `tools/nfr_security_p0_drills/nfr_security_p0_drill_contract.json` exists and validates as the canonical Story 9.4 NFR-S P0 drill contract.
2. Contract pins `source_story=9.4`, `drill_version=nfr_security_p0_drills_v1`, `nfr=NFR-S`, `standard_cadence=quarterly`, `lite_cadence=annual`, `postmortem_sla_hours=24`, and `p0_zero_tolerance=true`.
3. Contract defines exactly three scenario ids in this order: `sandbox_privilege_escape`, `data_exfiltration`, and `billing_ledger_corruption`.
4. Each scenario defines P0 class, trigger hypothesis, owner, primary substrate, required SOP gates, containment decision fields, 24h timeline fields, postmortem section requirements, stop-ship rule, and allowed drill mode.
5. Scenario `sandbox_privilege_escape` references M3.7 sandbox security audit assets and explicitly states static CI does not prove real gVisor/AppArmor/seccomp/K8s enforcement.
6. Scenario `data_exfiltration` references PIPL/user-data/audit-log/security disclosure surfaces and requires no raw customer data, raw uploaded file, prompt, provider payload, or production hostname in evidence.
7. Scenario `billing_ledger_corruption` references billing Saga/ledger/reconciler substrates and requires no raw ledger rows or customer-identifying dimensions in evidence.
8. Contract defines observed repo state for sandbox audit, incident/postmortem contract, billing ledger schema/model/orchestrator/routes, and CI wiring.
9. Contract explicitly states it does not prove a real P0 incident, real exploit execution, real data breach, real ledger corruption, real customer impact, real public Postmortem publication, real external ticket/notification creation, real refund/compensation, or release approval.
10. Evidence schema and static example manifest exist under `tools/nfr_security_p0_drills/`.
11. Static example manifest has `example_only=true`, `real_incident_occurred=false`, `real_drill_executed=false`, `real_public_postmortem_published=false`, `real_external_notification_sent=false`, `real_customer_impact=false`, and `release_approved=false`.
12. Static example cannot claim real P0, real drill pass, real external delivery, real public postmortem, real customer impact, real refund/compensation, real security signoff, or production release approval.
13. Optional real evidence path mode accepts only `reports/nfr-security-p0-drills/<run_id>/drill_manifest.json` where directory name equals `run_id`.
14. Optional real evidence requires `example_only=false`, `redaction_reviewed=true`, valid cadence mode (`quarterly` or `annual_lite`), all three scenario results, source snapshots, SOP execution records, containment actions, timeline records, postmortem templates, and findings.
15. Optional real evidence requires each scenario timeline to set `postmortem_due_utc` exactly 24h after `p0_declared_utc`.
16. Every failed scenario, failed SOP gate, missing containment action, failed timeline check, missing postmortem section, or missing required source snapshot must reference at least one finding with ticket refs.
17. Real evidence cannot mark `release_approved=true` while unresolved P0/P1/P2 NFR-S findings remain open, in progress, or deferred.
18. Validator rejects tenant/user/customer ids, emails, phone numbers, API keys, bearer tokens, cookies, passwords, secrets, webhook tokens, Linear tokens, credentialed URLs, production hostnames, absolute paths, directory traversal, raw logs, raw SQL dumps, raw ledger rows, raw prompts/files, provider payloads, exploit payloads, and customer-identifying dimensions.
19. Validator discovers current committed security substrates and fails if contract `observed_repo_state` is stale.
20. Validator fails if any canonical P0 scenario is absent from the contract or evidence.
21. Tests cover validator happy path, scenario drift, observed-state drift, fake completion, unsafe evidence paths, leak/exploit rejection, missing scenario evidence, missing timeline/postmortem, missing-ticket enforcement, release approval blocking, and CI workflow wiring.
22. Runbook documents local commands, quarterly flow, annual-lite flow, three P0 scenarios, SOP execution, containment evidence, 24h timeline, postmortem template, evidence path, redaction rules, ticket policy, stop-ship rules, rollback, and Story 9.7 handoff.
23. `.github/workflows/ci.yml` exposes `nfr_security_p0_drills` from `changes` outputs.
24. CI path filter `nfr_security_p0_drills` covers `tools/nfr_security_p0_drills/**`, `scripts/validate_nfr_security_p0_drills.py`, `tests/test_nfr_security_p0_drills.py`, `docs/runbooks/nfr-security-p0-drills.md`, `reports/nfr-security-p0-drills/**`, `.github/workflows/ci.yml`, `infra/sandbox-security/**`, `tools/incidents/**`, `scripts/validate_j3_incident_contract.py`, `apps/web/src/lib/status-page.ts`, `infra/local-init/03-billing-schema.sql`, and relevant billing service source files.
25. CI job `nfr-security-p0-drills-validation` runs without `continue-on-error`.
26. CI job runs static validator, optional committed real evidence validation for every `reports/nfr-security-p0-drills/**/drill_manifest.json`, and Python tests.
27. No new package dependency is added to root, services, web, or Python workspace.
28. No sandbox runtime behavior, billing ledger behavior, public status page implementation, database migration, OpenAPI, auth/provider/solver business logic, or customer-facing billing file is modified.
29. Local gates pass: `uv run python scripts/validate_nfr_security_p0_drills.py`, `uv run pytest tests/test_nfr_security_p0_drills.py -q`, and `git diff --check`.
30. Post-implementation code review covers boundary issues, drift issues, data consistency, dependency consistency, fake-completion risk, CI closure, no-leak guarantees, exploit safety, ticket closure, and test adequacy; findings are fixed or explicitly documented.
31. Story status flow is `ready-for-dev -> in-progress -> code-review -> done`; `done` is forbidden before GitHub CI passes, PR merges, remote branch is deleted, and local `main` is synced.
32. After merge/sync, story and sprint status are marked `done` only through a separate status-sync commit.

## Tasks / Subtasks

- [x] T1: Add static NFR-S P0 drill contract and evidence schema (AC: 1-18)
  - [x] Create `tools/nfr_security_p0_drills/nfr_security_p0_drill_contract.json`.
  - [x] Create `tools/nfr_security_p0_drills/nfr_security_p0_drill_manifest.schema.json`.
  - [x] Create `tools/nfr_security_p0_drills/nfr_security_p0_drill_manifest.example.json`.
  - [x] Encode three canonical P0 scenarios, SOP gates, containment actions, 24h timeline, postmortem sections, observed repo state, and non-completion boundaries.
  - [x] Encode public-safe evidence and failed/missing ticket requirements.

- [x] T2: Add validator and unit tests (AC: 13-21)
  - [x] Implement `scripts/validate_nfr_security_p0_drills.py` using only stdlib.
  - [x] Validate contract/schema/example and optional real evidence path mode.
  - [x] Discover committed security substrates and compare them to contract `observed_repo_state`.
  - [x] Add `tests/test_nfr_security_p0_drills.py` with drift, leak, exploit, fake-completion, coverage, timeline, ticket, release-blocking, and CI coverage tests.

- [x] T3: Add P0 drill runbook (AC: 22)
  - [x] Document local/CI commands.
  - [x] Document quarterly and annual-lite flows.
  - [x] Document each P0 drill SOP, containment evidence, 24h timeline, postmortem template, redaction, tickets, stop-ship, rollback, and Story 9.7 handoff.

- [x] T4: Add CI closure (AC: 23-28)
  - [x] Add `nfr_security_p0_drills` output and path filter to `.github/workflows/ci.yml`.
  - [x] Add `nfr-security-p0-drills-validation` job.
  - [x] Ensure sandbox, incident/postmortem, and billing substrate changes trigger the validator.
  - [x] Confirm no new dependencies or out-of-scope implementation files are modified.

- [x] T5: Gates, review, and GitHub sync (AC: 29-32)
  - [x] Run local validation gates.
  - [x] Run post-implementation code review and fix/document findings.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [x] Mark story and sprint status `done` only after merge/sync through a separate status-sync commit.

## Dev Notes

### Current Security Substrates

- M3.7 static sandbox governance exists under `infra/sandbox-security/`, including `audit_plan.json`, `attack_scenarios.json`, K8s hardening fragments, AppArmor, and `scripts/validate_sandbox_security_audit.py`.
- 8.A.3 public P0 postmortem model exists in `apps/web/src/lib/status-page.ts`; J3 incident contract exists under `tools/incidents/`.
- Billing ledger source of truth starts at `infra/local-init/03-billing-schema.sql` and maps through `apps/billing-service/src/billing_service/models.py`, `saga_orchestrator.py`, and `routes.py`.
- Existing assets are necessary substrates for drill governance, but none proves a real quarterly P0 drill has run.

### Implementation Pattern To Reuse

- Follow Story 9.1/9.2/9.3 static governance pattern:
  - contract + schema + static example under `tools/...`
  - stdlib validator under `scripts/...`
  - focused pytest module under `tests/...`
  - runbook under `docs/runbooks/...`
  - dedicated CI path filter and hard gate
- Reuse 9.2/9.3 validator concepts: explicit semantic validation, no `jsonschema` dependency, optional `--evidence`, repo-state drift detection, fake-completion rejection, redaction checks, release approval blocking.
- Reuse M3.7 boundary language: CI is static/structural and must not run real exploit behavior.

### Boundary Rules

- This story does not prove a real P0 happened.
- This story does not run real exploit, exfiltration, or ledger-corruption drills.
- This story does not publish a real public postmortem or notify real customers.
- This story does prove:
  - three canonical NFR-S P0 drill scenarios have a single governance contract;
  - static examples cannot fake completion;
  - future evidence must include SOP execution, containment, 24h timeline, postmortem template, redaction, and ticket-backed closure;
  - CI detects drift in governance assets and current security substrates.

### Suggested Commands

```powershell
uv run python scripts/validate_nfr_security_p0_drills.py
uv run pytest tests/test_nfr_security_p0_drills.py -q
git diff --check
```

## Definition Of Done

- Story has passed exactly 3 pre-implementation adversarial review rounds with revisions recorded after each round.
- Static NFR-S P0 drill contract, schema, example, validator, tests, runbook, and CI job exist.
- Validator catches fake completion, security substrate drift, missing canonical scenarios, unsafe evidence paths, unresolved stop-ship findings, sensitive data leakage, exploit payload leakage, missing timeline/postmortem closure, and missing tickets.
- Local gates and GitHub CI pass.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Story and sprint status become `done` only after PR CI green, merge, remote branch deletion, local main sync, and a separate status-sync commit.

## Review Findings

- [x] [Review][Patch] Real evidence could retain `not_run_example` statuses — fixed by rejecting `not_run_example` for real evidence collections and adding regression coverage.
- [x] [Review][Patch] Manifest `period` dates were not enforced by the stdlib validator — fixed by validating `period.start_date` and `period.end_date` as `YYYY-MM-DD`.
- [x] [Review][Patch] Duplicate SOP gate rows could mask data consistency drift — fixed by rejecting duplicate `scenario_id` + `gate_id` pairs in `sop_executions`.
- [x] [Review][Patch] Real evidence could claim real incident/customer/external-delivery/refund facts outside static governance scope — fixed by rejecting those claims in real evidence mode.
- [x] [Review][Patch] Duplicate per-scenario evidence records could mask data consistency drift — fixed by rejecting duplicate scenario rows for scenario/source/containment/timeline/postmortem collections.

## Story Review Log

### Round 1: Boundary And Fake-Completion Review

Findings fixed:

- Initial Epic wording could be read as running real P0 drills or publishing real postmortems. Revised scope to static governance, deterministic evidence requirements, and optional real evidence validation only.
- Initial scenario wording could allow committed examples to claim real incidents, customer impact, refunds, notifications, or release approval. Added static fake-completion flags and rejection requirements.
- Initial sandbox scenario could drift into dangerous exploit execution. Added explicit out-of-scope for fork bombs, Docker socket probes, namespace probes, mount commands, credential probes, real exfiltration, and ledger-corrupting writes.

Status: PASS after fixes.

### Round 2: Drift And Data Consistency Review

Findings fixed:

- Initial contract could drift from M3.7 sandbox audit, 8.A.3 postmortem, or billing ledger substrates. Added validator requirements to discover committed security substrates and compare them to contract `observed_repo_state`.
- Initial drill evidence did not force all three P0 classes. Added exactly three canonical scenario ids and evidence completeness requirements.
- Initial 24h timeline could be hand-waved. Added exact `postmortem_due_utc = p0_declared_utc + 24h` validation requirement.
- Initial failure handling allowed failed drills without closure. Added ticket references for every failed/missing scenario, SOP gate, timeline check, containment action, or postmortem section, plus release approval blocking for unresolved P0/P1/P2 findings.

Status: PASS after fixes.

### Round 3: Dependency, CI, And Closure Review

Findings fixed:

- Initial story did not explicitly ban new incident/ticket/security SDKs or schema libraries. Added no-new-dependency constraints and no external integration constraints.
- Initial CI closure did not include all relevant upstream substrate files. Added path-filter coverage for sandbox audit, incident contracts, status-page model, billing SQL/model/orchestrator/routes, governance assets, and evidence reports.
- Initial lifecycle did not restate the user's strict GitHub/status-sync ordering. Added status flow and post-merge-only separate `done` status-sync requirement.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/9-4-nfr-s-p0-drills`.
- Baseline commit: `a82010578fdde4ba83eafc9d330bc3e72ff2922e`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base skill instructions and project config.
- Story creation analyzed Epic 9.4, PRD P0 security zero tolerance, M3.7 sandbox audit, 8.A.3 public P0 postmortem, billing ledger/Saga substrates, and existing 9.x static governance validator/runbook patterns.
- 2026-06-05 - Completed pre-implementation adversarial review round 1 and revised fake-completion, real-drill, and exploit-execution boundaries.
- 2026-06-05 - Completed pre-implementation adversarial review round 2 and revised repo-state drift detection, canonical scenario completeness, exact 24h timeline, ticket closure, and stop-ship rules.
- 2026-06-05 - Completed pre-implementation adversarial review round 3 and revised dependency, CI trigger, and GitHub/status-sync closure requirements.
- 2026-06-05 - Story moved to in-progress after exactly three pre-implementation review rounds.
- 2026-06-05 - Red phase: `uv run pytest tests/test_nfr_security_p0_drills.py -q` produced 16 expected failures before validator/assets/runbook/CI existed.
- 2026-06-05 - Implemented static contract, manifest schema, example manifest, stdlib validator, tests, runbook, and CI path-filter/job.
- 2026-06-05 - Green phase: fixed example SOP completeness so real evidence derived from the example covers all three scenarios and all six required SOP gates.
- 2026-06-05 - Local gates passed: `uv run python scripts/validate_nfr_security_p0_drills.py`, `uv run pytest tests/test_nfr_security_p0_drills.py -q`, and `git diff --check`.
- 2026-06-05 - Post-implementation code review found real-evidence status, manifest period, duplicate SOP-gate, real-claim boundary, and duplicate scenario-record validation gaps; patched validator and added regression coverage.
- 2026-06-05 - Post-review gates passed: `uv run python scripts/validate_nfr_security_p0_drills.py`, `uv run pytest tests/test_nfr_security_p0_drills.py -q`, and `git diff --check`.
- 2026-06-05 - CI lint follow-up: grouped observed SHA-256 fingerprints to avoid detect-secrets false positives while preserving drift checks; accepted ruff-format output.
- 2026-06-05 - Local follow-up gates passed: validator, focused tests, `git diff --check`, and targeted detect-secrets over all Story 9.4 files. Full local pre-commit was blocked by Windows pagefile exhaustion after non-secret hooks passed.
- 2026-06-05 - PR #173 passed GitHub CI, merged to `main`, remote branch `codex/9-4-nfr-s-p0-drills` was deleted, and local `main` was synced to `origin/main`.
- 2026-06-05 - Separate status-sync commit prepared after merge/sync to mark Story 9.4 and sprint status `done`.

### Completion Notes List

- Initial story created.
- Exactly three pre-implementation adversarial review rounds completed; story is ready for implementation.
- Story moved to in-progress after exactly three pre-implementation review rounds.
- Added Story 9.4 NFR-S P0 drill governance assets and validator without new dependencies or runtime/business-logic changes.
- CI now hard-gates the static validator, optional committed real evidence manifests, and focused Python tests.
- Story moved to code-review after local implementation gates passed; `done` remains blocked until post-review, PR CI, merge, remote branch deletion, local main sync, and separate status-sync commit.
- Post-implementation review patches completed; focused test count is now 18.
- CI lint follow-up keeps `observed_repo_state` exact by comparing grouped SHA-256 fingerprints instead of continuous high-entropy hex strings.
- PR #173 passed CI and merged. Story and sprint status now marked `done` in this separate post-merge status-sync.

### File List

- `_bmad-output/stories/9-4-nfr-s-p0-drills.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `docs/runbooks/nfr-security-p0-drills.md`
- `scripts/validate_nfr_security_p0_drills.py`
- `tests/test_nfr_security_p0_drills.py`
- `tools/nfr_security_p0_drills/nfr_security_p0_drill_contract.json`
- `tools/nfr_security_p0_drills/nfr_security_p0_drill_manifest.schema.json`
- `tools/nfr_security_p0_drills/nfr_security_p0_drill_manifest.example.json`

## Change Log

- 2026-06-05 - Initial Story 9.4 created.
- 2026-06-05 - Round 1 pre-implementation review revised fake-completion and exploit boundaries.
- 2026-06-05 - Round 2 pre-implementation review revised drift detection, scenario completeness, timeline, ticket, and stop-ship closure.
- 2026-06-05 - Round 3 pre-implementation review revised dependency, CI trigger, and status-sync closure.
- 2026-06-05 - Story status moved to in-progress after exactly three pre-implementation review rounds.
- 2026-06-05 - Implemented NFR-S P0 drill contract, schema, example, validator, tests, runbook, and CI hard gate.
- 2026-06-05 - Story status moved to code-review after local implementation gates passed.
- 2026-06-05 - Post-implementation review tightened real-evidence status, period-date, duplicate SOP-gate, real-claim boundary, and duplicate scenario-record validation.
- 2026-06-05 - CI lint follow-up grouped repo-state SHA-256 values and applied ruff-format output.
- 2026-06-05 - Status-sync after PR #173 merge marked Story 9.4 done.
