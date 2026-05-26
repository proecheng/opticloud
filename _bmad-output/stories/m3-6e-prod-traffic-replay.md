# Story M3.6e: Production Traffic Replay Infrastructure

Status: done

owner: SRE / NFR-P owner

## Story

As a SRE / NFR-P owner,
I want a production-traffic replay infrastructure contract with sanitized capture fixtures, replay plans, validation, CI hooks, and operator runbooks,
so that G6/M3 performance and contract confidence can be strengthened with representative production traffic patterns later without committing real customer data, credentials, or fabricated pass evidence.

## Acceptance Criteria

1. Production traffic replay plan is explicit and scoped to sanitized replay infrastructure.
   - Add `tools/traffic_replay/replay_plan.json` as the M3.6e source of truth.
   - The plan must use `dataset_version=prod_traffic_replay_plan_v1` and `source_story=M3.6e`.
   - The plan must define `source_gap=G6`, `source_decision=RE2-7`, and `evidence_directory=reports/prod-traffic-replay`.
   - The plan must define replay mode `sanitized_contract_replay`, not live production mirroring.
   - The plan must define exactly three replay lanes:
     - `api_gateway_public`: representative sanitized public API requests, target service class `api-gateway`, baseline threshold family `M3.6d`.
     - `chat_streaming`: representative sanitized Chat streaming requests, target service class `chat-service`, baseline threshold family `M3.6a`.
     - `contract_fuzz`: Schemathesis-compatible contract replay seed cases, target service class `contract-tests`, baseline threshold family `M3.2`.
   - The plan must define `capture_source=production_logs_redacted_export`, `redaction_required=true`, `sampling_strategy=deterministic_hash_bucket`, and `replay_environment=staging`.
   - The plan must not contain production URLs, real request bodies, real response bodies, Authorization headers, API keys, JWTs, cookies, tenant IDs, user IDs, phone numbers, emails, IP addresses, or customer prompts.

2. Sanitized capture fixture and schema prevent PII and credential drift.
   - Add `tools/traffic_replay/capture_fixture.schema.json`.
   - Add `tools/traffic_replay/capture_fixture.example.json` as deterministic non-production sample data.
   - The fixture schema must require `dataset_version=prod_traffic_replay_capture_v1`, `source_story=M3.6e`, `example_only`, `capture_id`, `redaction_profile`, `generated_by`, `captured_window`, and `requests`.
   - Each request must include `request_id`, `lane`, `method`, `path_template`, `query_shape`, `body_shape`, `header_shape`, `expected_status_family`, and `weight`.
   - The example fixture must set `example_only=true` and `redaction_profile=synthetic-example-no-production-data`.
   - Real sanitized capture fixtures, when produced later, must set `example_only=false`, use a non-example redaction profile, and live under `reports/prod-traffic-replay/<run_id>/capture_fixture.json`.
   - The validator must reject secret-like keys/values, raw emails, phone numbers, IP addresses, bearer tokens, API keys, cookies, tenant/user IDs, and prompt-like free-text values in fixtures.
   - The validator must reject raw URL hosts; fixtures may store only path templates and shape metadata.

3. Replay evidence manifest is structurally validated and cannot be mistaken for a real G6 or M3.6d pass.
   - Add `tools/traffic_replay/evidence_manifest.schema.json`.
   - Add `tools/traffic_replay/evidence_manifest.example.json` as deterministic non-production example evidence.
   - The manifest schema must require `source_story=M3.6e`, `example_only`, `run_id`, `commit_sha`, `environment=staging-traffic-replay`, `plan_sha256`, `capture_fixture_sha256`, `capture_id`, `redaction_profile`, `started_utc`, `ended_utc`, `duration_seconds`, `lane_results`, and `artifacts`.
   - Artifact fields must be exactly `replay_report`, `redaction_audit`, `contract_seed_report`, and `latency_summary`.
   - Artifact paths must be repository-relative and under `reports/prod-traffic-replay/<run_id>/`, where `<run_id>` exactly matches the manifest `run_id`.
   - `replay_report` may be `.html` or `.json`; all other artifacts must be `.json`.
   - The example manifest must set `example_only=true` and must not be accepted as real replay evidence.
   - Real replay evidence validation must reject manifests whose `plan_sha256` or `capture_fixture_sha256` does not match the supplied committed/reported input.
   - Real replay evidence validation must reject `capture_id` or `redaction_profile` drift between the manifest and the capture fixture.
   - Real replay evidence must not claim `g6_hard_gate_pass`, `api_gateway_perf_pass`, `chat_load_pass`, `hard_gate_pass`, or `staging_pass`.

4. Replay metrics prove lane-specific replay integrity instead of generic request success.
   - The manifest must include exactly one result for each replay lane: `api_gateway_public`, `chat_streaming`, and `contract_fuzz`.
   - Every lane result must include `lane`, `request_count`, `success_count`, `http_error_rate`, `p95_ms`, `replay_drift_rate`, `redaction_violation_count`, and `threshold_reference`.
   - Real evidence validation must reject `duration_seconds <= 0`.
   - Real evidence validation must reject `success_count > request_count`.
   - Real evidence validation must reject any lane with `request_count <= 0`.
   - Real evidence validation must reject `redaction_violation_count > 0`.
   - Real evidence validation must reject `replay_drift_rate > 0.02`.
   - Real evidence validation must reject `http_error_rate > 0.01` for `api_gateway_public` and `contract_fuzz`.
   - Real evidence validation must reject `http_error_rate > 0.02` for `chat_streaming`, because provider/runtime variance is tolerated only within a narrow replay-infra threshold.
   - All latency fields must use milliseconds; the only seconds field is `duration_seconds`.

5. Validator and tests close data/function drift for replay assets.
   - Add `scripts/validate_traffic_replay_plan.py`.
   - The validator must validate committed replay plan, capture schema/example, evidence schema/example, and artifact path rules by default.
   - Add `--capture-fixture reports/prod-traffic-replay/<run_id>/capture_fixture.json` and `--evidence reports/prod-traffic-replay/<run_id>/evidence_manifest.json` modes for future operator evidence PRs.
   - When `--evidence` is supplied, the validator must require the matching `capture_fixture.json` from the same run directory unless `--capture-fixture` explicitly points to an in-repo fixture path.
   - The validator must check plan metadata, lane definitions, redaction rules, capture fixture shape, evidence shape, example-vs-real boundaries, artifact paths, metric units, hash binding, forbidden pass claims, and forbidden secret/PII-like content.
   - Add `tests/test_traffic_replay_plan.py` covering successful validation and negative cases for lane drift, threshold-family drift, example fixture as real fixture, PII/secret rejection, raw host rejection, artifact path traversal, wrong artifact extension, example evidence as real evidence, evidence hash mismatch, capture/evidence metadata mismatch, drift/error-rate failures, redaction violation failures, and path mode separation from M3.6a-d reports.

6. Runbook documents the exact operator workflow without credentials or customer data.
   - Add `docs/runbooks/production-traffic-replay.md`.
   - The runbook must explain capture export, deterministic sampling, redaction, fixture validation, staging replay, artifact capture, and evidence PR submission.
   - The runbook must list required environment variables without providing values or secrets.
   - The runbook must state that CI validates structure only and does not prove a real production traffic replay passed.
   - The runbook must require redaction audit review before committing artifacts.
   - The runbook must define failure follow-up: redaction violation means stop and delete artifacts; replay drift or latency failure means open performance/contract investigation before retry.
   - The runbook must state that M3.6e replay evidence informs G6/M3 tuning but does not replace M3.6a staging Chat hard-gate evidence or M3.6d API gateway baseline evidence.

7. CI enforces the replay contract without live production or staging services.
   - Extend `.github/workflows/ci.yml` with a traffic replay path filter for `tools/traffic_replay/**`, `scripts/validate_traffic_replay_plan.py`, `tests/test_traffic_replay_plan.py`, `docs/runbooks/production-traffic-replay.md`, and `reports/prod-traffic-replay/**`.
   - Add a focused CI job that runs the traffic replay validator and tests when those paths change.
   - CI must validate real capture fixtures and replay evidence manifests only when present under `reports/prod-traffic-replay/**`.
   - CI must not require production logs, staging services, Kubernetes, Grafana, Prometheus, Locust, Schemathesis live network runs, cloud credentials, JWTs, API keys, or database access.

8. Workflow tracking and boundaries are explicit.
   - This story records three pre-implementation story review rounds and fixes after each round before implementation.
   - `_bmad-output/stories/sprint-status.yaml` moves `m3-6e-prod-traffic-replay` to `ready-for-dev` only after all three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.
   - This story must not implement live production traffic capture, production mirroring, customer-data export jobs, runtime replay against live services, Chat runtime, API gateway runtime, or real pass reports.
   - Future real sanitized replay artifacts must be introduced through a separate operator evidence PR; this implementation commits only deterministic example fixture/evidence.
   - This story must not commit generated files under `reports/prod-traffic-replay/**`, Python `__pycache__`, `.hypothesis`, Locust outputs, or Schemathesis output caches.
   - Final completion must update the story's Dev Agent Record, file list, validation evidence, post-implementation review findings/fixes, and sprint status so the work is auditable end to end.

## Tasks / Subtasks

- [x] Build traffic replay plan assets. (AC: 1)
  - [x] Add `tools/traffic_replay/replay_plan.json`.
  - [x] Define the three replay lanes and threshold-family references without production data.
- [x] Build sanitized capture contract. (AC: 2)
  - [x] Add `tools/traffic_replay/capture_fixture.schema.json`.
  - [x] Add `tools/traffic_replay/capture_fixture.example.json`.
  - [x] Ensure real fixtures cannot contain raw PII, secrets, hosts, tenant/user IDs, or prompts.
- [x] Build replay evidence contract. (AC: 3, 4)
  - [x] Add `tools/traffic_replay/evidence_manifest.schema.json`.
  - [x] Add `tools/traffic_replay/evidence_manifest.example.json`.
  - [x] Ensure replay evidence cannot be mistaken for M3.6a/M3.6d pass evidence.
- [x] Add validator and regression tests. (AC: 5)
  - [x] Add `scripts/validate_traffic_replay_plan.py`.
  - [x] Add `tests/test_traffic_replay_plan.py`.
  - [x] Cover lane drift, redaction boundaries, evidence failures, and report path separation.
- [x] Add operator runbook. (AC: 6)
  - [x] Add `docs/runbooks/production-traffic-replay.md`.
  - [x] Document capture, redaction, replay, artifact archive, failure handling, and evidence PR rules.
- [x] Wire CI. (AC: 7)
  - [x] Add traffic replay path filter and validation job.
  - [x] Add optional real capture/evidence validation loops.
- [x] Update workflow records and validation evidence. (AC: 8)
  - [x] Record implementation notes, file list, and change log.
  - [x] Move sprint status through `ready-for-dev`, `in-progress`, `code-review`, and `done` only after gates pass.
  - [x] Run post-implementation code review and apply fixes.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:2065` adds RE2-7: Story M3.6e Production Traffic Replay Infrastructure, Epic 0, M3 start.
- `_bmad-output/planning/epics.md:2100` lists Story M3.6e as a new M3 story from RE2-7.
- `_bmad-output/planning/implementation-readiness-report-2026-05-17-v3.md:114` treats G6 Chat latency staging pressure as Story M3.6a/b/c/d/e, including Production Traffic Replay RE2-7.
- `_bmad-output/planning/implementation-readiness-report-2026-05-17-v3.md:287` states M3.6a-e G6 must close via 5-node K8s plus replay.
- `_bmad-output/stories/m2-2b-saga-property-tests.md:60` says M3.6e adds Schemathesis-based contract fuzzing; this connects replay seeds to the M3.2 contract framework.
- `_bmad-output/stories/m3-2-contract-test-framework.md` establishes the current Schemathesis PR-gate pattern and separates static OpenAPI drift from live/in-process contract tests.

### Previous Story Intelligence

- M3.6a added Chat staging load plan/schema/example/runbook/validator/CI for real operator evidence.
- M3.6b added advisory single-node baseline while explicitly not unlocking G6 staging pass.
- M3.6c added incident fallback drill evidence while keeping it separate from Chat hard-gate pass evidence.
- M3.6d added API gateway performance baseline contract under `tools/api_gateway_perf/`, with real evidence reserved for future operator PRs.
- M3.6e must remain a separate replay lane under `tools/traffic_replay/` and `reports/prod-traffic-replay/`, not a modification of M3.6a-d evidence semantics.

### Repository Context

- `tools/chat_load/` and `tools/api_gateway_perf/` already provide patterns for deterministic JSON plan/schema/example assets and standalone validators.
- `tests/contract/` provides current Schemathesis contract test scaffolding; this story should emit replay seed contracts, not run live Schemathesis against production or staging in CI.
- Real production logs and customer data are not available in the repo and must not be introduced.

### Metric Definitions

- `replay_drift_rate`: share of replayed requests whose sanitized shape, expected status family, or response contract differs from expected replay classification.
- `redaction_violation_count`: number of detected PII/secret/raw-data violations in the replay fixture or artifacts. Real evidence must be zero.
- `p95_ms`: replay lane latency P95 in milliseconds. It is advisory for replay infrastructure and does not replace M3.6a or M3.6d pass thresholds.
- `threshold_reference`: label tying a lane to its baseline family, e.g. `M3.6d`, `M3.6a`, or `M3.2`.

### Architecture / External Constraints

- Artifact paths must be repository-relative, normalized, and under `reports/prod-traffic-replay/<run_id>/`.
- Reject traversal, absolute paths, URL schemes, and Windows drive prefixes.
- Use JSON for machine-readable plans, capture fixtures, and evidence. Use Markdown only for the operator runbook and story.
- Redaction must occur before any fixture or artifact reaches git.

### Testing / Validation Notes

Expected local commands after implementation:

```bash
uv run python scripts/validate_traffic_replay_plan.py
uv run pytest tests/test_traffic_replay_plan.py -q
uv run ruff check scripts/validate_traffic_replay_plan.py tests/test_traffic_replay_plan.py
uv run ruff format --check scripts/validate_traffic_replay_plan.py tests/test_traffic_replay_plan.py
uv run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

The implementation should run the focused validator/test commands immediately after each validator change while developing:

```bash
uv run python scripts/validate_traffic_replay_plan.py
uv run pytest tests/test_traffic_replay_plan.py -q
```

### Risks / Decisions

- Data consistency risk: replay lanes, threshold-family labels, fixture schema, evidence schema, tests, and runbook can drift.
- Function consistency risk: traffic replay could become a generic success-count report. Require lane-specific replay drift, redaction, and error-rate checks.
- Boundary risk: replay evidence could be misread as M3.6a Chat staging hard-gate or M3.6d API gateway pass evidence. Reject pass claims and keep report directories separate.
- Boundary risk: fixtures could accidentally commit production PII or secrets. Validator must aggressively reject PII/secret-like keys and values.
- Closure risk: static CI could be misread as real replay pass. CI validates structure only; real sanitized capture/replay evidence belongs in a future operator PR.
- Scope risk: implementing live production capture, service mirroring, or runtime replay orchestration here would exceed M3.6e. Keep this story to contract, fixture/evidence validation, CI, and runbook.

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Added `capture_id` and `redaction_profile` to the replay evidence manifest requirement so replay evidence can be traced back to the exact sanitized capture fixture.
- Required real evidence validation to reject `capture_id` and `redaction_profile` drift between evidence and capture fixture.

Status: PASS after fixes.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Required `--evidence` validation to bind to a matching capture fixture from the same run directory by default, preventing a manifest from being validated without its source replay input.
- Added an explicit test requirement for capture/evidence metadata mismatch so `capture_id`, `redaction_profile`, and fixture hash cannot drift silently.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Explicitly forbade committing generated real `reports/prod-traffic-replay/**` artifacts and local cache/output directories in this implementation.
- Added final completion bookkeeping requirements for Dev Agent Record, file list, validation evidence, post-implementation review fixes, and sprint status.
- Reaffirmed that future real sanitized replay artifacts must arrive through a separate operator evidence PR.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Implementation Notes

- Added a static M3.6e traffic replay contract under `tools/traffic_replay/` with a replay plan, sanitized capture fixture schema/example, and replay evidence schema/example.
- Implemented `scripts/validate_traffic_replay_plan.py` as an offline validator. Default mode validates committed plan/schema/examples; optional modes validate future real sanitized fixtures/evidence under `reports/prod-traffic-replay/<run_id>/`.
- Bound evidence manifests to the canonical plan hash, canonical capture fixture hash, matching `capture_id`, and matching `redaction_profile`.
- Added PII/secret/raw-host/prompt-like rejection for capture and evidence content, while allowing JSON Schema metadata URLs.
- Added lane-specific replay integrity checks for drift, redaction violations, HTTP error-rate limits, request/success counts, and millisecond latency units.
- Added operator runbook and CI path filter/job. CI remains structure-only and validates real replay artifacts only when they are present in an operator evidence PR.
- Post-review fixes added explicit object closure checks for capture/evidence root fields and lane/request fields, JWT detection, and camelCase secret-key normalization.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/stories/m3-6e-prod-traffic-replay.md`
- `_bmad-output/stories/sprint-status.yaml`
- `docs/runbooks/production-traffic-replay.md`
- `scripts/validate_traffic_replay_plan.py`
- `tests/test_traffic_replay_plan.py`
- `tools/traffic_replay/capture_fixture.example.json`
- `tools/traffic_replay/capture_fixture.schema.json`
- `tools/traffic_replay/evidence_manifest.example.json`
- `tools/traffic_replay/evidence_manifest.schema.json`
- `tools/traffic_replay/replay_plan.json`

### Validation Evidence

- PASS: `uv run python scripts/validate_traffic_replay_plan.py`
- PASS: `uv run pytest tests/test_traffic_replay_plan.py -q` (20 passed)
- PASS: `uv run ruff check scripts/validate_traffic_replay_plan.py tests/test_traffic_replay_plan.py`
- PASS: `uv run ruff format --check scripts/validate_traffic_replay_plan.py tests/test_traffic_replay_plan.py`
- PASS: `uv run pre-commit run --all-files --show-diff-on-failure`
- PASS: `git diff --check`
- PASS after post-review fixes: `uv run python scripts/validate_traffic_replay_plan.py`
- PASS after post-review fixes: `uv run pytest tests/test_traffic_replay_plan.py -q` (20 passed)
- PASS after post-review fixes: `uv run ruff check scripts/validate_traffic_replay_plan.py tests/test_traffic_replay_plan.py`
- PASS after post-review fixes: `uv run ruff format --check scripts/validate_traffic_replay_plan.py tests/test_traffic_replay_plan.py`
- PASS after post-review fixes: `git diff --check`
- ATTEMPTED: `uv run pytest -q` failed during collection on existing monorepo packaging/PYTHONPATH issues unrelated to M3.6e, including duplicate `tests.conftest` import mismatch across service test packages and missing import roots for service/package tests.

## Senior Developer Review (AI)

Outcome: Approved after fixes.

Review date: 2026-05-26

Review layers:
- Blind Hunter: local equivalent review completed.
- Edge Case Hunter: local equivalent review completed.
- Acceptance Auditor: local equivalent review completed against this story's ACs.

Findings fixed:
- [Medium] Capture/evidence validators did not explicitly reject missing required fields or unexpected extra fields in future real fixtures/manifests. Fixed with root/request/lane object closure checks and regression tests.
- [Medium] AC2 forbids JWTs, but the first implementation only rejected Bearer/API-key-like values. Fixed with a JWT value detector and regression test.
- [Low] Secret-like key detection missed camelCase forms such as `accessToken`. Fixed with camelCase-to-snake key normalization before exact-key checks.

Residual risk:
- Full repository `uv run pytest -q` still fails during collection because of existing monorepo test package/PYTHONPATH issues. M3.6e focused validator/tests and configured quality gates pass.

### Change Log

- 2026-05-26: Initial draft created for M3.6e story context.
- 2026-05-26: Completed three pre-implementation story review rounds and moved story to ready-for-dev.
- 2026-05-26: Started implementation and moved story to in-progress.
- 2026-05-26: Implemented traffic replay plan/schema/examples, validator, tests, runbook, and CI gate; moved story to code-review.
- 2026-05-26: Completed post-implementation review and fixed validator closure/JWT/camelCase secret-key gaps.
- 2026-05-26: Final validation passed and story moved to done.
