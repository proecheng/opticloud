# Story M3.6c: Chat 延迟预算 incident-fallback 测试

Status: done

owner: SRE / NFR-P owner

## Story

As a NFR-P owner / SRE,
I want a repeatable DeepSeek incident simulation and Qwen-Max fallback drill contract, evidence manifest, validator, CI hook, and operator runbook,
so that the team can prove emergency Chat fallback switches within 5 minutes and degraded fallback latency stays under P95 5s without confusing this drill with normal G6 staging pass evidence.

## Acceptance Criteria

1. Incident fallback drill plan is explicit and separate from M3.6a/M3.6b load profiles.
   - Add `tools/chat_load/incident_fallback_plan.json` as the source of truth for M3.6c.
   - The plan must use `dataset_version=chat_incident_fallback_plan_v1` and `source_story=M3.6c`.
   - The plan must define `primary_provider=deepseek-v3.5` and `fallback_provider=qwen-max`.
   - The plan must define a simulated incident trigger based on DeepSeek Provider Health failure and a manual Qwen-Max fallback operation.
   - The plan must reference the existing prompt fixture `tools/chat_load/prompts_v1.json` and include its canonical SHA-256 hash.
   - The plan must encode `switch_budget_seconds=300` and `fallback_first_token_p95_max_ms=5000`.
   - The plan must encode `fallback_route_ratio_min=1.0`, `schema_parity_required=true`, and `drill_only=true`.
   - The plan must define `evidence_directory=reports/chat-incident-fallback` and the exact artifact field names later required by the manifest.
   - The plan must keep M3.6a staging hard-gate thresholds separate; passing this drill must not mark M3.6a staging evidence as passed.
   - The plan must not contain production URLs, API keys, bearer tokens, cookies, tenant IDs, provider request/response payloads, or real customer prompts.

2. Incident fallback evidence manifest is structurally validated and cannot be mistaken for real production evidence.
   - Add `tools/chat_load/incident_fallback_evidence_manifest.schema.json`.
   - Add `tools/chat_load/incident_fallback_evidence_manifest.example.json` as deterministic non-production example evidence.
   - The manifest schema must require `source_story=M3.6c`, `example_only`, `run_id`, `commit_sha`, `environment=staging-incident-drill`, `endpoint_path`, `primary_provider`, `fallback_provider`, `prompt_fixture`, `prompt_fixture_sha256`, `prompt_count`, `drill_plan_sha256`, artifacts, timeline, and metrics.
   - Artifact paths must be repository-relative and under `reports/chat-incident-fallback/<run_id>/`, where `<run_id>` exactly matches the manifest `run_id`.
   - Required artifact fields must be exactly `locust_report`, `provider_health_snapshot`, `fallback_decision_log`, `operator_timeline`, and `latency_snapshot`.
   - `locust_report` must be `.html` or `.json`; `provider_health_snapshot`, `fallback_decision_log`, `operator_timeline`, and `latency_snapshot` must be `.json`.
   - The example manifest must set `example_only=true` and must not be accepted as real incident fallback evidence.
   - Real incident fallback evidence, when produced later, must live at `reports/chat-incident-fallback/<run_id>/evidence_manifest.json` with `example_only=false`.
   - Real evidence validation must reject a manifest whose `drill_plan_sha256` does not match the committed canonical hash of `tools/chat_load/incident_fallback_plan.json`.

3. Evidence metrics prove the fallback drill instead of merely proving request success.
   - The manifest metrics must include request count, completed stream count, HTTP error rate, fallback route ratio, switch duration, fallback first-token P95, fallback total response P95, fallback streaming throughput, schema parity pass count, schema parity total count, and fallback provider error count.
   - The manifest timeline must include `incident_started_utc`, `provider_health_failed_utc`, `operator_decision_utc`, `fallback_confirmed_utc`, `measurement_started_utc`, and `measurement_ended_utc`.
   - `switch_duration_seconds` must be measured from `operator_decision_utc` to `fallback_confirmed_utc`, so it is not inflated or hidden by provider-health detection delay.
   - `detection_window_seconds` must be measured from `incident_started_utc` to `provider_health_failed_utc` and must be recorded separately from switch duration.
   - Real evidence validation must reject `switch_duration_seconds > 300`.
   - Real evidence validation must reject `fallback_first_token_p95_ms >= 5000`.
   - Real evidence validation must reject a fallback route ratio below 1.0 for the post-switch measurement window.
   - Real evidence validation must reject schema parity pass counts that do not equal total counts.
   - Real evidence validation must reject `schema_parity_total_count=0`.
   - Real evidence validation must reject `fallback_provider_error_count > 0`.
   - Real evidence validation must reject completed stream counts greater than request counts.
   - Real evidence validation must reject `measurement_ended_utc` that is not after `measurement_started_utc`.
   - Real evidence validation must reject `fallback_confirmed_utc` that is before `operator_decision_utc`.
   - All latency fields must be milliseconds except explicit `*_seconds` timeline and switch-duration fields.

4. Validator and tests close data/function drift for staging, single-node, and incident fallback paths.
   - Extend `scripts/validate_chat_load_plan.py` to validate committed incident fallback plan assets by default.
   - Add explicit `--incident-fallback-evidence reports/chat-incident-fallback/<run_id>/evidence_manifest.json` mode for future operator evidence PRs.
   - The validator must keep existing M3.6a and M3.6b validation behavior unchanged.
   - The validator must check incident plan metadata, provider IDs, switch budget, fallback latency threshold, prompt hash, evidence schema/example shape, artifact path constraints, example-vs-real evidence boundaries, metric unit fields, and forbidden secret-like values.
   - The validator must expose dedicated functions for incident plan, incident schema, incident manifest, and incident artifact-path validation rather than overloading the M3.6a staging manifest functions.
   - The validator must reject `hard_gate_candidate`, `hard_gate_pass`, or `staging_pass` claims anywhere in incident fallback evidence.
   - Extend `tests/test_chat_load_plan.py` to cover successful incident fallback validation and negative cases for provider drift, switch budget drift, fallback latency threshold drift, artifact path traversal, example evidence presented as real evidence, failed switch duration, failed latency threshold, route-ratio drift, and schema parity mismatch.
   - Tests must include a regression proving M3.6a `--evidence`, M3.6b `--single-node-evidence`, and M3.6c `--incident-fallback-evidence` remain separate path modes.

5. Runbook documents the exact operator drill without credentials.
   - Add `docs/runbooks/chat-incident-fallback.md`.
   - The runbook must explain how an operator simulates a DeepSeek incident, observes Provider Health, manually switches to Qwen-Max, captures fallback evidence, and rolls back after the drill.
   - The runbook must list required environment variables without providing real values or secrets.
   - The runbook must define pass/fail interpretation: switch <= 5 minutes and fallback first-token P95 < 5000 ms.
   - The runbook must state that CI validates structure only and does not prove the incident fallback drill passed.
   - The runbook must require redaction before committing artifacts.
   - The runbook must state that the drill is internal SRE evidence and does not change customer-facing v1 SLO language.
   - The runbook must document rollback to DeepSeek after the drill and follow-up actions if Qwen-Max fallback itself fails.

6. CI enforces the incident fallback contract without requiring live providers.
   - Extend `.github/workflows/ci.yml` `chat_load_plan` path filters to include `docs/runbooks/chat-incident-fallback.md` and `reports/chat-incident-fallback/**`.
   - Update the chat load validation job to validate real incident fallback evidence manifests only when present under `reports/chat-incident-fallback/**`.
   - The CI loop must call `uv run python scripts/validate_chat_load_plan.py --incident-fallback-evidence "$manifest"` for each `reports/chat-incident-fallback/**/evidence_manifest.json`.
   - CI must not require Kubernetes, Grafana, Locust runtime against a live service, cloud credentials, external network, DeepSeek API keys, or Qwen-Max API keys.

7. Workflow tracking and boundaries are explicit.
   - This story records three pre-implementation story review rounds and fixes after each round before implementation.
   - `_bmad-output/stories/sprint-status.yaml` moves `m3-6c-chat-incident-fallback` to `ready-for-dev` only after all three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.
   - This story must not implement production Chat runtime, real LLM provider integration, M3.8 LLM provider abstraction, API gateway baseline, real incident execution, or real pass reports.
   - This story must not edit `tools/chat_load/staging_profiles.json`, `tools/chat_load/single_node_profiles.json`, M3.6a staging evidence schema, or M3.6b single-node evidence schema except if a shared validator refactor is strictly required and covered by regression tests.
   - Future real incident drill artifacts must be introduced through a separate operator evidence PR; this implementation commits only deterministic example evidence.

## Tasks / Subtasks

- [x] Build incident fallback plan assets. (AC: 1)
  - [x] Add `tools/chat_load/incident_fallback_plan.json`.
  - [x] Keep incident drill plan separate from `staging_profiles.json` and `single_node_profiles.json`.
- [x] Build incident fallback evidence contract. (AC: 2, 3)
  - [x] Add `tools/chat_load/incident_fallback_evidence_manifest.schema.json`.
  - [x] Add `tools/chat_load/incident_fallback_evidence_manifest.example.json`.
  - [x] Ensure example and real drill evidence cannot be mistaken for M3.6a staging hard-gate evidence.
- [x] Extend validator and regression tests. (AC: 4)
  - [x] Extend `scripts/validate_chat_load_plan.py`.
  - [x] Extend `tests/test_chat_load_plan.py`.
  - [x] Cover incident fallback success and negative drift cases.
- [x] Add operator runbook. (AC: 5)
  - [x] Add `docs/runbooks/chat-incident-fallback.md`.
  - [x] Document simulation, manual switch, evidence archive, pass/fail rules, redaction, and rollback.
- [x] Wire CI. (AC: 6)
  - [x] Add incident fallback paths to `chat_load_plan` path filter.
  - [x] Add optional real incident fallback evidence validation loop.
- [x] Update workflow records and validation evidence. (AC: 7)
  - [x] Record implementation notes, file list, and change log.
  - [x] Move sprint status through `ready-for-dev`, `in-progress`, `code-review`, and `done` only after gates pass.
  - [x] Run post-implementation code review and apply fixes.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:1187` defines M3.6c as Chat latency budget incident-fallback testing.
- `_bmad-output/planning/epics.md:1189` requires DeepSeek API simulated incident to Qwen-Max fallback, switch <= 5 minutes, degraded latency P95 < 5s.
- `_bmad-output/planning/prd.md:514` states v1 normal LLM path is DeepSeek and Qwen-Max is incident emergency fallback, not normal SLO.
- `_bmad-output/planning/prd.md:518` through `520` describe the J3 scenario: Provider Health DeepSeek failure alert, manual emergency fallback, and 3 minute switch target.
- `_bmad-output/planning/prd.md:866` requires monthly fault-injection drill tooling for DeepSeek API unavailability.
- `_bmad-output/planning/prd.md:1678` through `1680` define DeepSeek-V3.5 primary path, Qwen-Max incident fallback, and v2+ multi-LLM router later.
- `_bmad-output/planning/ux-design-specification.md:2576` defines the SRE incident flow: alert, Provider Health Console, manual Qwen-Max fallback, Status Page, fix, 24h postmortem.
- `_bmad-output/planning/architecture.md:1681` defines P57 Chat Path latency budgets.
- `_bmad-output/planning/architecture.md:1993` defines G6 as Chat latency budget risk and says architecture changes are required if staging full-stack tests fail.
- `_bmad-output/planning/architecture.md:2437` states the G6 staging hard-gate is first-token P95 < 3s, streaming >= 20 Token/s, and E2E <= 90s.

### Previous Story Intelligence

- M3.6a added the shared prompt fixture `tools/chat_load/prompts_v1.json`, staging load profiles, staging evidence schema/example, validator, tests, runbook, and CI job.
- M3.6b reused M3.6a prompt and helper patterns for a single-node advisory baseline and extended the same validator/test file instead of creating a separate validation island.
- Reuse the existing prompt fixture and hash strategy; do not create a new prompt dataset for incident fallback.
- Preserve M3.6a staging validation and M3.6b single-node validation exactly; M3.6c adds a third optional real-evidence mode.
- Existing post-review fixes to preserve: artifact extension checks by semantic field, example evidence cannot be accepted as real evidence, real evidence gets threshold-checked, and advisory/drill evidence cannot satisfy staging hard-gate semantics.

### Repository Context

- Existing static validation lives in `scripts/validate_chat_load_plan.py` with tests in `tests/test_chat_load_plan.py`.
- Existing CI has a focused `chat-load-plan-validation` job triggered by `chat_load_plan` paths.
- `apps/chat-service/` does not yet provide a production Chat runtime or LLM router for CI to exercise. CI must remain static/evidence-contract based.
- Real evidence under `reports/` is future operator input; this story must not fabricate a real incident pass.

### Metric Definitions

- `detection_window_seconds`: simulated Provider Health failure observation window before operator action.
- `switch_duration_seconds`: elapsed seconds from operator fallback decision timestamp to first confirmed Qwen-Max routed Chat response.
- `fallback_first_token_p95_ms`: first-token P95 during the post-switch fallback measurement window.
- `fallback_total_response_p95_ms`: total response P95 during the post-switch fallback measurement window.
- `fallback_route_ratio`: share of post-switch measured Chat requests routed to Qwen-Max; real evidence must be 1.0.
- `schema_parity_pass_count` and `schema_parity_total_count`: count of sampled fallback responses that match the committed Chat response contract expected by the drill.

### Architecture / External Constraints

- This story validates an incident drill contract, not production router behavior.
- Do not add live DeepSeek/Qwen credentials, production URLs, provider payloads, or user data.
- Artifact paths must be repository-relative, normalized, and under `reports/chat-incident-fallback/<run_id>/`.
- Reject traversal, absolute paths, URL schemes, and Windows drive prefixes.
- Use JSON for machine-readable plans and evidence. Use Markdown only for the operator runbook and story.

### Testing / Validation Notes

Expected local commands after implementation:

```bash
uv run python scripts/validate_chat_load_plan.py
uv run pytest tests/test_chat_load_plan.py -q
uv run ruff check scripts/validate_chat_load_plan.py tests/test_chat_load_plan.py
uv run ruff format --check scripts/validate_chat_load_plan.py tests/test_chat_load_plan.py
uv run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

The implementation should also run the focused validator/test commands immediately after each validator change while developing:

```bash
uv run python scripts/validate_chat_load_plan.py
uv run pytest tests/test_chat_load_plan.py -q
```

### Risks / Decisions

- Data consistency risk: plan provider IDs, prompt fixture hash, schema provider fields, example manifest, tests, and runbook can drift.
- Function consistency risk: detection window, operator decision time, and actual switch duration can be collapsed. The manifest must store them separately.
- Function drift risk: fallback first-token P95 can be confused with total response P95. Store both fields and threshold only the first-token P95 for M3.6c acceptance.
- Function drift risk: a generic evidence helper could accidentally apply staging hard-gate semantics to incident evidence or vice versa. Use dedicated incident validation functions and explicit path prefixes.
- Boundary risk: M3.6c passing could be misread as M3.6a G6 hard-gate pass. Store incident fallback as drill evidence only.
- Closure risk: implementation could fake real incident evidence. This story commits only plan/schema/example/runbook/validator/test assets.
- Closure risk: runbook could omit rollback and leave the operator in fallback mode after a drill. Include rollback and failure follow-up steps.
- Scope risk: implementing a provider abstraction or runtime router here would duplicate M3.8/Epic 4 work. Keep M3.6c to contract, evidence validation, CI, and runbook.

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Added prompt fixture hash binding to the drill plan so plan, manifest, and existing M3.6a prompt data cannot drift independently.
- Added `evidence_directory=reports/chat-incident-fallback` and exact artifact field names so JSON schema, example manifest, validator, tests, and runbook share one vocabulary.
- Added artifact extension rules by semantic field: Locust report can be `.html`/`.json`, all other drill artifacts are `.json`.
- Required real evidence `drill_plan_sha256` to match canonical committed `incident_fallback_plan.json`.
- Split timeline fields and clarified that `switch_duration_seconds` starts at `operator_decision_utc`, while provider-health detection delay is tracked separately.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Added internal-only SRE evidence wording so the drill does not change customer-facing v1 SLO language.
- Added rollback and Qwen-Max-failure follow-up requirements to close the operator workflow.
- Explicitly forbade editing M3.6a/M3.6b profile and schema assets except for tightly tested shared validator refactors.
- Clarified that future real incident drill artifacts belong in a separate operator evidence PR and are not committed by this implementation.
- Added focused validation commands to run during implementation, not only at the end.
- Reaffirmed that provider abstraction/runtime router work belongs to M3.8/Epic 4, not this story.

Status: PASS after fixes. Story is ready for development.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Added `fallback_route_ratio_min=1.0`, `schema_parity_required=true`, and `drill_only=true` to the plan so the drill cannot degrade into generic request-success validation.
- Added real-evidence failure rules for zero schema-parity samples, fallback provider errors, invalid measurement ordering, and fallback confirmation before operator decision.
- Required dedicated incident validator functions rather than reusing M3.6a staging manifest validation, preventing hard-gate threshold leakage between evidence modes.
- Added explicit rejection of `hard_gate_candidate`, `hard_gate_pass`, and `staging_pass` claims anywhere in incident fallback evidence.
- Added a test requirement proving `--evidence`, `--single-node-evidence`, and `--incident-fallback-evidence` stay separate path modes.

Status: PASS after fixes.

## Dev Agent Record

### Implementation Notes

- Implemented M3.6c as a deterministic incident fallback drill contract, not as production provider routing.
- Added a machine-checkable incident plan with DeepSeek primary, Qwen-Max fallback, switch <= 300s, fallback first-token P95 < 5000 ms, fallback route ratio 1.0, and schema parity required.
- Added incident evidence schema/example under `reports/chat-incident-fallback/<run_id>/` semantics with separate artifacts, timeline, and metrics.
- Extended the existing chat load validator with dedicated M3.6c plan/schema/manifest/path-mode functions while preserving M3.6a staging and M3.6b single-node validation.
- Added regression coverage for provider/threshold drift, artifact path boundaries, example-vs-real evidence, real evidence thresholds, timeline ordering, hard-gate claim rejection, and separate evidence path modes.
- Added operator runbook covering simulation, manual switch, evidence archive, redaction, pass/fail interpretation, rollback, and Qwen-Max failure follow-up.
- Post-implementation review fixes applied: timeline-derived metric consistency is now checked, and incident artifact schema patterns now reject traversal segments.

### File List

- `.github/workflows/ci.yml`
- `.pre-commit-config.yaml`
- `docs/runbooks/chat-incident-fallback.md`
- `scripts/validate_chat_load_plan.py`
- `tests/test_chat_load_plan.py`
- `tools/chat_load/incident_fallback_evidence_manifest.example.json`
- `tools/chat_load/incident_fallback_evidence_manifest.schema.json`
- `tools/chat_load/incident_fallback_plan.json`
- `_bmad-output/stories/m3-6c-chat-incident-fallback.md`
- `_bmad-output/stories/sprint-status.yaml`

### Validation Evidence

- `uv run pytest tests/test_chat_load_plan.py -q` — RED confirmed 9 expected failures before implementation.
- `uv run python scripts/validate_chat_load_plan.py` — PASS
- `uv run pytest tests/test_chat_load_plan.py -q` — PASS, 36 tests
- `uv run ruff check scripts/validate_chat_load_plan.py tests/test_chat_load_plan.py` — PASS
- `uv run ruff format --check scripts/validate_chat_load_plan.py tests/test_chat_load_plan.py` — PASS
- `uv run python scripts/validate_chat_load_plan.py` — PASS after code review fixes
- `uv run pytest tests/test_chat_load_plan.py -q` — PASS, 37 tests after code review fixes
- `uv run ruff check scripts/validate_chat_load_plan.py tests/test_chat_load_plan.py` — PASS after code review fixes
- `uv run ruff format --check scripts/validate_chat_load_plan.py tests/test_chat_load_plan.py` — PASS after code review fixes
- `git diff --check` — PASS
- `uv run pre-commit run --all-files --show-diff-on-failure` — PASS
- `uv run pre-commit run --all-files --show-diff-on-failure` — PASS after PR CI lint follow-up
- `uv run python scripts/validate_chat_load_plan.py` — PASS after PR CI lint follow-up
- `uv run pytest tests/test_chat_load_plan.py -q` — PASS, 37 tests after PR CI lint follow-up
- `git diff --check` — PASS after PR CI lint follow-up

## Senior Developer Review (AI)

Outcome: PASS after fixes

Findings fixed:
- Incident evidence accepted self-contradictory timeline metrics. Added validation that `switch_duration_seconds` equals `fallback_confirmed_utc - operator_decision_utc`, and `detection_window_seconds` equals `provider_health_failed_utc - incident_started_utc`, with regression coverage.
- Incident evidence JSON Schema artifact patterns did not reject `..` traversal segments directly. Tightened both Locust and JSON artifact path patterns and added schema guard coverage.
- PR CI lint flagged the public incident drill plan SHA-256 as a high-entropy string. Added a narrow detect-secrets exclusion for that exact public hash.

Residual risk:
- This story still does not produce real incident fallback evidence by design; operator evidence must be generated later with `--incident-fallback-evidence`.

### Change Log

- 2026-05-26: Initial draft created for M3.6c story context.
- 2026-05-26: Completed three pre-implementation story review rounds and moved story to ready-for-dev.
- 2026-05-26: Started implementation and moved story to in-progress.
- 2026-05-26: Added incident fallback plan, evidence schema/example, validator/tests, runbook, and CI wiring.
- 2026-05-26: Moved story to code-review after implementation validation passed.
- 2026-05-26: Completed post-implementation code review and applied timeline/schema boundary fixes.
- 2026-05-26: Final validation passed and story moved to done.
- 2026-05-26: Fixed PR CI lint false positive for public incident drill plan SHA-256.
