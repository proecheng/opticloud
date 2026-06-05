---
story_key: 9-8-graded-protection-evidence
epic_num: 9
story_num: 8
epic_name: NFR Governance
status: code-review
baseline_commit: 5b35ff3e4d6dd4f533c953d803df378bd13d857c
priority: High
type: Compliance evidence aggregation contract
created_by: bmad-create-story
created_at: 2026-06-05
owner: Compliance / Security / SRE / Legal
sources:
  - _bmad-output/planning/epics.md (TT7 / E8 / Epic 9)
  - _bmad-output/planning/prd.md (Compliance & Regulatory / MLPS 2.0 Level 2)
  - _bmad-output/planning/architecture.md (compliance requirements / budget / simplified vs standard)
  - _bmad-output/planning/SESSION-HANDOVER.md (graded protection M3 start / M5 target)
  - _bmad-output/stories/9-7-governance-dashboard.md
  - tools/governance_dashboard/governance_dashboard_contract.json
  - docs/runbooks/governance-dashboard.md
  - .github/workflows/ci.yml
---

# Story 9.8 - Graded Protection Evidence Auto-Aggregation Pipeline

Status: code-review

## Story

**作为** Compliance / Security / SRE / Legal governance owner，
**我希望** 等保 2.0 二级（MLPS Level 2）的工程证据、季度法务签字、TSA 时间戳准备、区块链存证准备、整改票据和 9.7 governance dashboard handoff 被统一为可验证的静态 evidence aggregation contract、manifest、validator、runbook 和 CI hard gate，
**从而** M3 启动评测、M5 末取证目标不会依赖口头状态，也不会把静态示例伪造成真实测评机构报告、公安备案、真实 TSA、真实上链或真实法务签字。

## Context

Epic TT7 新增 Story 9.8：等保 2.0 二级 evidence 自动归集 pipeline（NFR-C7 evidence trail M3 起持续）。Expert Panel E8 追加要求：TSA 时间戳 + 区块链存证（蚂蚁链 / 腾讯至信链）+ quarterly 法务签字。

PRD 合规要求明确：等保 2.0 二级 M3 启动评测、M5 末取证；标准档 M5 末取证，精简档可推迟到 v1.5。Architecture 明确 v1 合规要求包括 ICP、公安、AIGC、等保 2.0 二级、PIPL、国密预留，并记录等保二级测评预算与 M5 末节点。

当前仓库没有真实测评机构交付物、公安备案回执、TSA 服务凭据、蚂蚁链/腾讯至信链 API 凭据、真实区块链交易回执、法务电子签章、证据保全平台、合规 data room 或外部工单系统。因此本 story 的闭环是 **offline/static graded-protection evidence aggregation contract**，不是证明已经取得等保二级证书或已经完成真实存证。

外部标准背景只用于边界约束：

- GB/T 22239-2019 是网络安全等级保护基本要求的标准参考。
- RFC 3161 定义 Time-Stamp Protocol / TSA token 的协议参考。
- 最高人民法院互联网法院规则承认电子签名、可信时间戳、哈希校验、区块链等技术可用于证明电子数据真实性，但仍需要真实性证明和审查。

## Scope

1. Add static graded-protection evidence assets under `tools/graded_protection_evidence/`.
   - Contract pins `source_story=9.8`, `evidence_version=graded_protection_evidence_v1`, `epic=9`, `target_level=mlps_level_2`, `cadence=quarterly`, `pipeline_intent=offline_evidence_aggregation`.
   - Contract records `assessment_start_target=M3`, `certification_target=M5`, `simplified_track_target=v1.5`, `standard_track_target=M5`, and track-specific certification gates.
   - Contract references GB/T 22239-2019, RFC 3161, and the Supreme People's Court internet-court evidence rule as reference-only legal/technical context, with source URLs and retrieval dates captured as metadata only.
   - Contract defines required evidence domains, required artifact classes, preservation provider options, selected preservation lanes, legal review roles, release gate rules, redaction rules, finding/ticket policy, and 9.7 dashboard handoff.
2. Add evidence manifest schema and static example.
   - Static example must be `example_only=true`.
   - Static example cannot claim real MLPS Level 2 certificate, real assessment institution engagement, real public-security filing, real TSA timestamp, real blockchain preservation, real legal signoff, real external ticket creation, or release approval.
   - Optional real evidence path is only `reports/graded-protection-evidence/<run_id>/evidence_manifest.json`, directory name must equal `run_id`.
   - Optional real evidence must be public-safe, redacted, hash-addressed, and complete across required domains before it can pass.
3. Add `scripts/validate_graded_protection_evidence.py` using stdlib only.
   - Validate contract/schema/example and optional real evidence path mode.
   - Validate committed dependency state for 9.7 dashboard assets so 9.8 handoff cannot drift, including dashboard report directory, manifest filename, dashboard version, source story, and fake-completion boundary flags.
   - Validate evidence domains, artifact classes, hash manifest references, artifact status rollups, selected preservation-lane receipts, legal review records, findings, ticket refs, gate decisions, redaction, and CI wiring.
4. Add `tests/test_graded_protection_evidence.py`.
   - Cover validator happy path, dependency drift, missing domains, missing artifacts, unsafe evidence path, fake completion, release blocking, timestamp/blockchain receipt gaps, legal signoff gaps, sensitive-data rejection, ticket requirements, and CI closure.
5. Add `docs/runbooks/graded-protection-evidence.md`.
   - Document local/CI commands, quarterly evidence collection flow, MLPS Level 2 boundary, TSA request/receipt expectations, blockchain preservation provider handoff, legal signoff workflow, redaction, tickets, release gates, rollback, and 9.7 dashboard update handoff.
6. Update `.github/workflows/ci.yml`.
   - Add `graded_protection_evidence` output and path filter.
   - Add `graded-protection-evidence-validation` job without `continue-on-error`.
   - Job runs static validator, optional committed real evidence validation, focused pytest, and no external TSA/blockchain/legal/vendor calls.
7. Do not add new npm/Python dependencies.
8. Do not implement real TSA calls, real blockchain calls, legal e-signature integration, assessment institution integration, public-security filing integration, data room, backend service, database migration, OpenAPI, web UI, billing/auth/provider/solver business logic, or external ticket integration.

## Out Of Scope

- Proving a real MLPS Level 2 certificate was obtained.
- Proving a real public-security filing was accepted.
- Calling a TSA service or validating real X.509 chains against external trust stores in CI.
- Calling AntChain, Tencent Zhixin Chain, or any other blockchain/evidence-preservation service.
- Creating real legal signatures, real third-party assessment artifacts, or real external tickets.
- Storing raw logs, raw screenshots, raw customer data, raw vulnerability output, raw network topology with production details, credentials, production hostnames, or tenant/user/customer identifiers.
- Replacing Story 9.7 dashboard evidence; 9.8 only hands a redacted compliance-evidence rollup back to 9.7.

## Acceptance Criteria

1. `tools/graded_protection_evidence/graded_protection_evidence_contract.json` exists and validates as canonical Story 9.8 contract.
2. Contract pins `source_story=9.8`, `evidence_version=graded_protection_evidence_v1`, `epic=9`, `target_level=mlps_level_2`, `cadence=quarterly`, and `pipeline_intent=offline_evidence_aggregation`.
3. Contract records `assessment_start_target=M3`, `certification_target=M5`, `standard_track_target=M5`, `simplified_track_target=v1.5`, and track-specific certification gates for `standard_m5` and `simplified_v1_5`.
4. Contract references GB/T 22239-2019, RFC 3161, and Supreme People's Court internet-court electronic evidence rules as reference-only context and does not claim legal advice or certification.
5. Contract reference metadata includes `source_name`, `reference_type`, `url`, `retrieved_at`, `scope_note`, and `not_legal_advice=true` for each external reference.
6. Contract defines required evidence domains exactly as `system_scope`, `asset_and_network_boundary`, `identity_and_access_control`, `security_audit_and_logging`, `data_protection_and_backup`, `vulnerability_and_incident_response`, `operations_and_change_management`, `legal_and_third_party_review`, `timestamp_and_blockchain_preservation`, and `governance_dashboard_handoff`.
7. Contract defines required artifact classes exactly as `scope_statement`, `asset_inventory_snapshot`, `network_boundary_diagram_redacted`, `access_control_matrix`, `audit_log_retention_statement`, `backup_restore_evidence`, `vulnerability_scan_summary`, `incident_drill_summary`, `change_management_sample`, `third_party_assessment_tracker`, `legal_signoff_record`, `tsa_timestamp_receipt`, `blockchain_preservation_receipt`, `finding_register`, and `dashboard_handoff_record`.
8. Each required domain maps to at least one artifact class, and every artifact class maps to a valid domain.
9. Contract defines preservation provider options exactly as `tsa_rfc3161`, `antchain`, and `tencent_zhixin_chain`, with all provider integrations marked `external_call_in_scope=false`.
10. Contract defines legal review roles exactly as `Legal`, `Compliance`, `Security`, and `SRE`.
11. Contract defines gate statuses exactly as `green`, `yellow`, `red`, `unknown`, and `not_run`.
12. Contract defines stop-ship rules: missing required domain evidence forces `red`; failed redaction forces `red`; missing legal review after a real run forces `red`; missing TSA receipt or missing selected blockchain-provider receipt after a real preservation run forces at least `yellow`; unresolved P0/P1/P2 findings force `red`; M5 standard-track release approval is blocked if `mlps_level_2_certificate_obtained=false`.
13. Contract defines artifact statuses exactly as `not_run_example`, `present`, `missing`, `stale`, `failed`, and `deferred`.
14. Contract defines track modes exactly as `standard_m5` and `simplified_v1_5`; evidence manifests must choose one track and apply that track's certification gate.
15. Contract explicitly states it does not prove real MLPS Level 2 certification, real assessment institution engagement, real public-security filing, real TSA timestamp issuance, real blockchain preservation, real legal signature, real external ticket creation, or production release approval.
16. Contract contains observed 9.7 dashboard dependency state discovered from committed `tools/governance_dashboard/governance_dashboard_contract.json`, and validation fails if source story, dashboard version, dashboard evidence path, manifest filename, dashboard boundary flags, or 9.8 dashboard handoff fields drift.
17. Evidence schema and static example manifest exist under `tools/graded_protection_evidence/`.
18. Static example has `example_only=true`, `track_mode=standard_m5`, `real_assessment_institution_engaged=false`, `real_public_security_filing_completed=false`, `real_mlps_level_2_certificate_obtained=false`, `real_tsa_timestamp_issued=false`, `real_blockchain_preservation_completed=false`, `real_legal_signoff_completed=false`, and `release_approved=false`.
19. Static example cannot claim real assessment, filing, certification, TSA, blockchain preservation, legal signoff, external ticket creation, all findings resolved, or release approval.
20. Optional real evidence path mode accepts only `reports/graded-protection-evidence/<run_id>/evidence_manifest.json`.
21. Optional real evidence requires `example_only=false`, `redaction_reviewed=true`, `real_evidence_aggregation_completed=true`, all required domains, all required artifact classes, a hash manifest entry for every artifact, legal review records for all legal review roles, a TSA preservation receipt when `real_tsa_timestamp_issued=true`, at least one selected blockchain provider receipt when `real_blockchain_preservation_completed=true`, findings, ticket refs when required, and a 9.7 dashboard handoff record.
22. Real evidence cannot mark `release_approved=true` while unresolved P0/P1/P2 findings remain open, in progress, deferred, or missing ticket refs.
23. Real `standard_m5` evidence cannot mark `release_approved=true` unless `real_mlps_level_2_certificate_obtained=true` and certificate artifact metadata is present; `simplified_v1_5` evidence cannot claim M5 certification and must record a deferral finding when the certificate is absent.
24. Hash manifest entries must include artifact id, artifact class, redacted artifact path, sha256, generated date, retention class, and evidence mode; every non-deferred required artifact must have exactly one hash manifest entry.
25. Every missing, stale, failed, red, yellow, or deferred domain/artifact/selected-preservation/legal-review item must reference at least one finding with ticket refs.
26. TSA receipt entries must include `provider=tsa_rfc3161`, `artifact_id`, `hash_sha256`, `timestamp_utc`, `policy_oid_or_profile`, `tsa_certificate_ref`, `receipt_artifact_path`, and `verification_status`.
27. Blockchain preservation entries must include `provider in {antchain,tencent_zhixin_chain}`, `artifact_id`, `hash_sha256`, `chain_receipt_id`, `preserved_at_utc`, `receipt_artifact_path`, and `verification_status`; real evidence must select at least one blockchain provider but must not require both providers to have live receipts.
28. Dashboard handoff records must include Story 9.7 dashboard version, dashboard manifest path, rollup status, finding ids, and `graded_protection_handoff_complete`; static examples must keep this flag false.
29. Validator rejects tenant/user/customer ids, emails, phone numbers, API keys, bearer tokens, cookies, passwords, secrets, private keys, TSA credentials, blockchain API credentials, legal signature private material, credentialed URLs, production hostnames, absolute paths, directory traversal, raw logs, raw screenshots, raw vulnerability payloads, raw network maps, raw metric labels, prompt/provider payloads, and raw customer-identifying dimensions.
30. Validator rejects static or CI evidence using `external_network`, `tsa_api`, `blockchain_api`, `assessment_vendor_api`, or `legal_esign_api` modes; allowed modes are `contract_static`, `redacted_manifest`, and `manual_review`.
31. `.github/workflows/ci.yml` exposes `graded_protection_evidence` from `changes` outputs.
32. CI path filter `graded_protection_evidence` covers `tools/graded_protection_evidence/**`, `scripts/validate_graded_protection_evidence.py`, `tests/test_graded_protection_evidence.py`, `docs/runbooks/graded-protection-evidence.md`, `reports/graded-protection-evidence/**`, `.github/workflows/ci.yml`, and Story 9.7 dashboard contract/schema/example/validator/test/runbook/evidence paths.
33. CI job `graded-protection-evidence-validation` runs without `continue-on-error`.
34. CI job runs static validator, optional committed real evidence validation for every `reports/graded-protection-evidence/**/evidence_manifest.json`, and focused Python tests.
35. No new npm/Python dependency is added and lockfiles remain unchanged.
36. No real TSA/blockchain/legal/vendor integration, backend service, database migration, OpenAPI, web UI, billing/auth/provider/solver business logic, or external ticket integration file is modified.
37. Local gates pass: `uv run python scripts/validate_graded_protection_evidence.py`, `uv run pytest tests/test_graded_protection_evidence.py -q`, `uv run ruff check scripts/validate_graded_protection_evidence.py tests/test_graded_protection_evidence.py`, and `git diff --check`.
38. Post-implementation code review covers boundary issues, drift issues, data consistency, dependency consistency, fake-completion risk, CI closure, no-leak guarantees, evidence-domain completeness, preservation receipt correctness, legal signoff closure, release-gate correctness, and test adequacy; findings are fixed or explicitly documented.
39. Story status flow is `ready-for-dev -> in-progress -> code-review -> done`.
40. `done` is forbidden before GitHub CI passes, PR merges, remote branch is deleted, and local `main` is synced.
41. After merge/sync, story and sprint status are marked `done` only through a separate status-sync commit.

## Tasks / Subtasks

- [x] T1: Add graded-protection evidence contract/schema/example (AC: 1-30)
  - [x] Create `tools/graded_protection_evidence/graded_protection_evidence_contract.json`.
  - [x] Create `tools/graded_protection_evidence/graded_protection_evidence_manifest.schema.json`.
  - [x] Create `tools/graded_protection_evidence/graded_protection_evidence_manifest.example.json`.
  - [x] Encode required domains, artifact classes, artifact statuses, track modes, preservation provider options, selected preservation lanes, external reference metadata, legal review roles, gate rules, fake-completion boundaries, and 9.7 dashboard dependency state.
  - [x] Encode public-safe evidence, hash manifest, ticket-backed closure, TSA receipt, selected blockchain receipt, track-specific release rules, and deferred-evidence rules.

- [x] T2: Add validator and focused tests (AC: 15-34)
  - [x] Implement `scripts/validate_graded_protection_evidence.py` using stdlib only.
  - [x] Validate contract/schema/example and optional real evidence path mode.
  - [x] Discover committed 9.7 dashboard metadata and compare it to contract observed dependency state.
  - [x] Add `tests/test_graded_protection_evidence.py` with drift, external-reference metadata, leak, fake-completion, completeness, hash manifest parity, selected preservation receipt, legal signoff, ticket, track-specific release-blocking, dashboard handoff, data-source-mode, and CI coverage tests.

- [x] T3: Add runbook and CI closure (AC: 31-37)
  - [x] Add `docs/runbooks/graded-protection-evidence.md`.
  - [x] Add `graded_protection_evidence` output/path filter and `graded-protection-evidence-validation` job to `.github/workflows/ci.yml`.
  - [x] Ensure Story 9.7 dashboard asset changes trigger the 9.8 validator.
  - [x] Confirm no new dependencies or out-of-scope implementation files are modified.

- [ ] T4: Gates, review, and GitHub sync (AC: 37-41)
  - [x] Run local validation gates.
  - [x] Run post-implementation code review and fix/document findings.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [ ] Mark story and sprint status `done` only after merge/sync through a separate status-sync commit.

## Dev Notes

### Existing Governance Sources To Reuse

- `tools/governance_dashboard/governance_dashboard_contract.json` is the Story 9.7 handoff source and must remain the only dashboard dependency for 9.8.
- `scripts/validate_governance_dashboard.py` provides the closest validator pattern for static contract/schema/example, optional real evidence path validation, no-leak detection, CI wiring checks, and upstream dependency drift checks.
- `scripts/validate_nfr_security_p0_drills.py` provides a pattern for evidence manifests with findings, ticket refs, release blocking, redaction, and fake-completion boundaries.
- `scripts/validate_image_archival_pipeline.py` provides a pattern for hash-addressed evidence, artifact checksums, static example rejection, and explicit real-evidence mode.
- `.github/workflows/ci.yml` already contains 9.1-9.7 hard gates; 9.8 should follow that pattern with a dedicated path filter and job.

### Implementation Pattern To Reuse

- Follow Story 9.1-9.7 static governance pattern:
  - contract + schema + static example under `tools/<topic>/`
  - stdlib validator under `scripts/`
  - focused pytest module under `tests/`
  - runbook under `docs/runbooks/`
  - dedicated CI path filter and hard gate
- Use semantic validation instead of adding `jsonschema`.
- Keep optional real evidence validation opt-in via `--evidence`.
- Keep all static examples fake-completion-safe.
- Keep dashboard dependency state derived from 9.7 contract JSON, not manually trusted.
- Keep external legal/technical references as metadata only. Do not encode legal conclusions beyond fake-completion and evidence-quality boundaries.

### Boundary Rules

- This story does not prove MLPS Level 2 certification, public-security filing, real assessment institution engagement, real TSA issuance, real blockchain preservation, real legal e-signature, real external ticket creation, or real release approval.
- This story does not call external networks in validator, tests, or CI.
- This story proves:
  - required evidence domains and artifact classes are pinned;
  - evidence bundles are hash-addressed and redaction-gated;
  - TSA, selected blockchain, and legal review receipts have explicit fields and ticket-backed gaps;
  - static examples cannot fake certification, timestamping, preservation, legal signoff, or release approval;
  - CI catches drift in 9.8 assets and Story 9.7 dashboard handoff.

### Suggested Commands

```powershell
uv run python scripts/validate_graded_protection_evidence.py
uv run pytest tests/test_graded_protection_evidence.py -q
uv run ruff check scripts/validate_graded_protection_evidence.py tests/test_graded_protection_evidence.py
git diff --check
```

## Definition Of Done

- Story has passed exactly 3 pre-implementation adversarial review rounds with revisions recorded after each round.
- Graded-protection evidence contract/schema/example, validator, tests, runbook, and CI hard gate exist.
- Validator catches fake completion, 9.7 dependency drift, missing evidence domains, missing required artifacts, unsafe evidence paths, sensitive data leakage, invalid evidence modes, timestamp receipt gaps, selected blockchain receipt gaps, missing legal review, ticket gaps, and release-gate violations.
- Local gates and GitHub CI pass.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Story and sprint status become `done` only after PR CI green, merge, remote branch deletion, local main sync, and a separate status-sync commit.

## Story Review Log

### Round 1: Boundary And Fake-Completion Review

Findings fixed:

- Initial preservation wording could force real evidence to include both AntChain and Tencent Zhixin Chain receipts. That overstates E8's provider choice and could incentivize fake dual-chain receipts. Revised scope and ACs so the contract supports exactly three provider options, requires TSA only when the real TSA lane is claimed, and requires at least one selected blockchain provider receipt only when real blockchain preservation is claimed.
- Initial preservation language did not distinguish provider options from selected evidence lanes. Revised tasks and DoD language to make selected-lane validation explicit.

Status: PASS after fixes.

### Round 2: Drift, Data Consistency, And Release-Gate Review

Findings fixed:

- Initial ACs did not pin artifact statuses or track modes, making it possible for evidence manifests to mix M5 standard-track release claims with simplified-track deferral. Added exact `standard_m5` and `simplified_v1_5` track modes and track-specific release gates.
- Initial hash-manifest requirements said artifacts must be hash-addressed but did not define one-to-one parity. Added required hash manifest fields and exactly-one entry for every non-deferred required artifact.
- Initial stop-ship language did not mention deferred artifacts. Added deferred status and ticket-backed finding requirements for deferred evidence, including simplified-track certificate deferral.

Status: PASS after fixes.

### Round 3: Dependency, CI, And Closure Review

Findings fixed:

- Initial 9.7 dependency check was too broad and did not specify dashboard version, evidence path, manifest filename, boundary flags, or dashboard handoff fields. Added explicit drift checks and dashboard handoff record requirements.
- Initial external reference language did not require source URL/retrieval metadata or `not_legal_advice=true`, which could blur engineering evidence with legal advice. Added reference metadata requirements.
- Initial CI closure was sufficient for new assets but did not restate that Story 9.7 dashboard evidence paths must trigger 9.8 validation. AC 32 now explicitly covers 9.7 dashboard contract/schema/example/validator/test/runbook/evidence paths.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/9-8-graded-protection-evidence`.
- Baseline commit: `5b35ff3e4d6dd4f533c953d803df378bd13d857c`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base skill instructions and project config.
- Story creation analyzed Epic TT7/E8, PRD MLPS Level 2 timing, Architecture compliance requirements, Story 9.7 governance dashboard handoff, existing 9.x static validator/test/runbook/CI patterns, and current CI workflow.
- Story moved to in-progress after exactly three pre-implementation review rounds.
- RED confirmed: `uv run pytest tests/test_graded_protection_evidence.py -q` failed with 18 expected failures before validator/assets/runbook/CI existed.
- Implemented graded-protection evidence contract/schema/example, stdlib validator, focused tests, runbook, and CI hard gate.
- Local gates passed: `uv run python scripts/validate_graded_protection_evidence.py`, `uv run pytest tests/test_graded_protection_evidence.py -q` (18 passed), `uv run ruff check scripts/validate_graded_protection_evidence.py tests/test_graded_protection_evidence.py`, `uv run ruff format --check scripts/validate_graded_protection_evidence.py tests/test_graded_protection_evidence.py`, and `git diff --check`.
- Post-implementation code review fixed status-enum gaps for legal review and preservation receipt verification statuses; focused test count is now 19.
- Post-review gates passed: `uv run python scripts/validate_graded_protection_evidence.py`, `uv run pytest tests/test_graded_protection_evidence.py -q` (19 passed), `uv run ruff check scripts/validate_graded_protection_evidence.py tests/test_graded_protection_evidence.py`, and `uv run ruff format --check scripts/validate_graded_protection_evidence.py tests/test_graded_protection_evidence.py`.

### Completion Notes List

- Initial story created.
- Completed pre-implementation adversarial review round 1 and revised preservation provider boundaries.
- Completed pre-implementation adversarial review round 2 and revised artifact status, track-mode, hash-manifest parity, and release-gate consistency.
- Completed pre-implementation adversarial review round 3 and revised 9.7 dependency drift checks, external reference metadata, dashboard handoff, and CI closure.
- Story moved to in-progress after exactly three pre-implementation review rounds.
- Added Story 9.8 graded-protection evidence assets, validator, tests, runbook, and CI hard gate.
- Post-implementation code review completed. Fixed legal-review and preservation-receipt status enum gaps so misspelled static or real evidence statuses cannot bypass validation.
- Story moved to code-review after local gates passed; `done` remains blocked until PR CI, merge, remote branch deletion, local main sync, and separate status-sync commit.

## Post-Implementation Code Review

Outcome: Changes requested, then fixed.

Findings fixed:

- Status enum gap: validator accepted unknown `legal_reviews.status` values in static evidence and unknown `preservation_receipts.verification_status` values unless they happened to match a gap status. That could let typo statuses such as `signed` or `verified` bypass static validation. Fixed by adding explicit legal-review and receipt-verification enums and regression coverage.
- Story AC mapping drift: pre-implementation review added ACs but task headings still referenced the old AC ranges. Fixed T1-T4 AC range labels so implementation traceability remains coherent.

Residual risk:

- Real MLPS assessment, TSA issuance, blockchain preservation, and legal signoff remain intentionally out of scope. A later operator process must collect real redacted artifacts and receipts before `--evidence` can prove those lanes.

### File List

- `_bmad-output/stories/9-8-graded-protection-evidence.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `docs/runbooks/graded-protection-evidence.md`
- `scripts/validate_graded_protection_evidence.py`
- `tests/test_graded_protection_evidence.py`
- `tools/graded_protection_evidence/graded_protection_evidence_contract.json`
- `tools/graded_protection_evidence/graded_protection_evidence_manifest.schema.json`
- `tools/graded_protection_evidence/graded_protection_evidence_manifest.example.json`

## Change Log

- 2026-06-05 - Initial Story 9.8 created.
- 2026-06-05 - Round 1 pre-implementation review revised TSA/blockchain provider boundary and selected preservation lane rules.
- 2026-06-05 - Round 2 pre-implementation review revised artifact status, track-mode, hash-manifest parity, and release-gate consistency.
- 2026-06-05 - Round 3 pre-implementation review revised 9.7 dependency drift checks, external reference metadata, dashboard handoff, and CI closure.
- 2026-06-05 - Story status moved to in-progress after exactly three pre-implementation review rounds.
- 2026-06-05 - Implemented graded-protection evidence contract, manifest schema/example, validator, tests, runbook, and CI hard gate.
- 2026-06-05 - Post-implementation review fixed legal-review and preservation-receipt status enum gaps; story moved to `code-review` pending GitHub sync.
