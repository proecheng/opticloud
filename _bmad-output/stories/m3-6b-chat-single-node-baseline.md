# Story M3.6b: Chat 延迟预算 single-node 单点压测 baseline

Status: done

owner: SRE / NFR-P owner

## Story

As a NFR-P owner / SRE,
I want a repeatable single-node dev Chat latency baseline harness, evidence contract, validator, and runbook,
so that P58 sandbox/chat tuning has a deterministic local reference before full 5-node staging evidence is produced.

## Acceptance Criteria

1. Single-node baseline profile is explicit and separate from staging hard-gate profiles.
   - Add `tools/chat_load/single_node_profiles.json` as the source of truth for the single-node dev baseline.
   - The profile file must use `dataset_version=chat_single_node_profiles_v1`, `source_story=M3.6b`, and a single `profiles.single_node_baseline` object.
   - The profile must model exactly 1 node, 20 users, 300 seconds, target 2 RPS, and effective pacing of 6 requests/minute/user so `users * effective_requests_per_user_per_minute / 60 = target_rps`.
   - The profile object must include `name=single_node_baseline`, `node_count=1`, `users=20`, `run_time_seconds=300`, `target_rps=2`, and `effective_requests_per_user_per_minute=6`.
   - The profile must include advisory P57/P58 thresholds: first-token P50 < 1500 ms, first-token P95 < 3000 ms, streaming >= 20 token/s, E2E solve P95 <= 90000 ms, sandbox startup P95 <= 100 ms, capability lookup P95 < 20 ms, and chat internal hop P95 <= 200 ms.
   - The profile must mark those thresholds as `advisory_only=true` and `hard_gate_candidate=false`; single-node results must not unlock the G6 staging hard-gate.
   - The profile must include the canonical SHA-256 hash of `tools/chat_load/prompts_v1.json`.
   - The profile must not contain live URLs, bearer tokens, cookies, API keys, tenant IDs, production hostnames, or provider payloads.

2. Single-node Locust entrypoint reuses M3.6a helpers without changing staging semantics.
   - Add `tools/chat_load/single_node_locustfile.py` as the canonical single-node entrypoint.
   - The single-node locustfile must import and reuse the existing prompt loading, SSE parsing, token-unit extraction, first-token latency, total-response latency, and streaming-throughput helper behavior from `tools/chat_load/locustfile.py`.
   - The single-node locustfile must select `single_node_baseline` only and must reject unknown `CHAT_SINGLE_NODE_PROFILE` values.
   - The single-node locustfile must use `CHAT_LOAD_ENDPOINT` or an equivalent endpoint path variable defaulting to `/v1/chat/stream`.
   - It must rely on Locust `--host` or `CHAT_LOAD_BASE_URL` for the base URL; no committed base URL is allowed.
   - It must expose pure helper functions for loading the single-node profile, selecting the profile from env, calculating request interval, and returning the endpoint so CI/static validation can run without Locust or a live endpoint.
   - It must use the existing M3.6a `calculate_stream_metrics()` helper for first-token, total-response, and streaming throughput so metric formulas do not drift between staging and single-node paths.
   - It must not change `tools/chat_load/locustfile.py` staging profile names, staging thresholds, or staging evidence semantics except for shared helper-compatible imports if required.

3. Single-node evidence manifest is structurally validated and cannot be mistaken for staging evidence.
   - Add `tools/chat_load/single_node_evidence_manifest.schema.json`.
   - Add `tools/chat_load/single_node_evidence_manifest.example.json` as deterministic non-production example evidence.
   - The manifest schema must require `source_story=M3.6b`, `example_only`, `run_id`, `commit_sha`, `environment=single-node-dev`, `node_count=1`, `endpoint_path`, `prompt_fixture`, `prompt_fixture_sha256`, `prompt_count=100`, one `single_node_baseline` profile entry, and summary metrics.
   - The single profile entry must require `locust_report`, `metrics_snapshot`, `start_utc`, `end_utc`, and metrics.
   - Artifact paths must be repository-relative and under `reports/chat-single-node/<run_id>/`, where `<run_id>` exactly matches the manifest `run_id`.
   - Locust reports must be `.html` or `.json`; metrics snapshots must be `.json`.
   - The schema must require metrics for request count, completed stream count, first-token P50/P95 in ms, total response P95 in ms, streaming token/s, token-count method, HTTP error rate, solve prompt count, E2E solve P95 in ms, OOM count, deadlock count, sandbox startup P95 in ms, capability lookup P95 in ms, and chat internal hop P95 in ms.
   - Locust-derived metrics and operator metrics must be separated by source in the example/runbook: Locust report supplies request/stream latency and throughput, while the metrics snapshot supplies sandbox startup, capability lookup, internal hop, OOM, and deadlock observations.
   - The example manifest must set `example_only=true` and must not be accepted as real single-node evidence.
   - Real single-node evidence, when produced later, must live at `reports/chat-single-node/<run_id>/evidence_manifest.json`, must set `example_only=false`, and must use the same `<run_id>` in every artifact path.
   - This story must not commit real single-node evidence artifacts. It may commit only the deterministic example manifest; real evidence belongs in a future operator evidence PR.
   - Single-node evidence must be validated as tuning/reference data only and must not satisfy M3.6a staging evidence requirements.

4. Validator and tests close data/function drift for both staging and single-node paths.
   - Extend `scripts/validate_chat_load_plan.py` to validate committed single-node plan assets by default.
   - Add explicit `--single-node-evidence reports/chat-single-node/<run_id>/evidence_manifest.json` mode for future operator evidence PRs.
   - The validator must keep existing M3.6a validation behavior unchanged.
   - The validator must check single-node profile metadata, exact single profile set, node count, RPS math, prompt hash, advisory threshold fields, non-hard-gate flags, locust helper reuse, evidence schema/example shape, artifact path constraints, forbidden secret-like values, and metric unit fields.
   - The validator must reject profile-name drift, any extra single-node profiles, node count other than 1, environment drift away from `single-node-dev`, missing or absolute artifact paths, Windows drive paths, URL artifact paths, directory traversal, wrong artifact extensions, wrong run_id path prefixes, example evidence presented as real evidence, and any attempt to mark single-node evidence as hard-gate pass evidence.
   - Add/extend `tests/test_chat_load_plan.py` to cover successful single-node validation and negative cases for RPS drift, prompt hash drift, artifact paths, wrong node count, fake hard-gate semantics, and `--single-node-evidence` mode.

5. Runbook documents exact local/dev operator flow without credentials.
   - Add `docs/runbooks/chat-single-node-baseline.md`.
   - The runbook must explain how an operator runs the single-node baseline against a local/dev single-node stack.
   - The runbook must list required environment variables without providing real values or secrets.
   - The runbook must show where to archive one Locust report and one metrics snapshot under `reports/chat-single-node/<run_id>/`.
   - The runbook must define interpretation as advisory tuning evidence, not G6 pass evidence.
   - The runbook must document P58/P57 follow-up: sandbox warm-pool tuning, capability lookup cache, chat-service internal hop isolation, provider first-token investigation, and whether to proceed to M3.6a staging.

6. CI enforces the single-node contract without requiring a live single-node stack.
   - Extend `.github/workflows/ci.yml` `chat_load_plan` path filters to include `docs/runbooks/chat-single-node-baseline.md` and `reports/chat-single-node/**`.
   - Update the chat load validation job to validate real single-node evidence manifests only when present under `reports/chat-single-node/**`.
   - The CI loop must call `uv run python scripts/validate_chat_load_plan.py --single-node-evidence "$manifest"` for each `reports/chat-single-node/**/evidence_manifest.json`.
   - CI must not require Kubernetes, Grafana, Locust runtime against a live service, cloud credentials, external network, or LLM provider keys.

7. Workflow tracking and boundaries are explicit.
   - This story records three pre-implementation story review rounds and fixes after each round before implementation.
   - `_bmad-output/stories/sprint-status.yaml` moves `m3-6b-chat-single-node-baseline` to `ready-for-dev` only after all three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.
   - This story must not implement production Chat runtime, real provider integration, 5-node staging evidence, incident fallback, API gateway baseline, Kubernetes cluster creation, Grafana dashboard creation, or real pass reports.
   - M3.6a remains the 5-node staging hard-gate story; M3.6c remains incident fallback; M3.6d remains API gateway performance baseline.

## Tasks / Subtasks

- [x] Build single-node load-test assets. (AC: 1, 2)
  - [x] Add `tools/chat_load/single_node_profiles.json`.
  - [x] Add `tools/chat_load/single_node_locustfile.py`.
  - [x] Preserve existing M3.6a staging profile semantics.
- [x] Build single-node evidence contract. (AC: 3)
  - [x] Add `tools/chat_load/single_node_evidence_manifest.schema.json`.
  - [x] Add `tools/chat_load/single_node_evidence_manifest.example.json`.
  - [x] Ensure example and real single-node evidence cannot be mistaken for staging hard-gate evidence.
- [x] Extend validator and regression tests. (AC: 4)
  - [x] Extend `scripts/validate_chat_load_plan.py`.
  - [x] Extend `tests/test_chat_load_plan.py`.
  - [x] Cover single-node success, drift, artifact, metric-unit, and hard-gate-boundary cases.
- [x] Add operator runbook. (AC: 5)
  - [x] Add `docs/runbooks/chat-single-node-baseline.md`.
  - [x] Document local/dev run command, evidence archive, advisory interpretation, and P58/P57 follow-up.
- [x] Wire CI. (AC: 6)
  - [x] Add single-node paths to `chat_load_plan` path filter.
  - [x] Add optional real single-node evidence validation loop.
- [x] Update workflow records and validation evidence. (AC: 7)
  - [x] Record implementation notes, file list, and change log.
  - [x] Move sprint status through `ready-for-dev`, `in-progress`, `code-review`, and `done` only after gates pass.
  - [x] Run post-implementation code review and apply fixes.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:1183` defines M3.6b as Chat latency budget single-node baseline.
- `_bmad-output/planning/epics.md:1185` says this is a single-node dev pressure-test baseline, P58 tuning reference, and should be runnable before M3.6a.
- `_bmad-output/planning/architecture.md:1681` defines P57 Chat Path latency budgets.
- `_bmad-output/planning/architecture.md:1692` sets total SLO: first token P50 < 1.5s, P95 < 3s, E2E solve <= 90s.
- `_bmad-output/planning/architecture.md:1694` through `1707` define P58 sandbox I/O and SSE flow constraints.
- `_bmad-output/planning/architecture.md:2437` defines G6 staging hard-gate; this story produces advisory single-node evidence only.
- `_bmad-output/planning/prd.md:1594` through `1599` define Chat first-token and streaming measurement expectations.

### Previous Story Intelligence

- M3.6a added `tools/chat_load/prompts_v1.json`, `tools/chat_load/locustfile.py`, `tools/chat_load/staging_profiles.json`, staging evidence schema/example, `scripts/validate_chat_load_plan.py`, `tests/test_chat_load_plan.py`, and `docs/runbooks/chat-staging-load-test.md`.
- Reuse M3.6a prompt fixture and helper behavior instead of creating another prompt dataset or duplicating SSE metric formulas.
- Preserve the M3.6a validator behavior because staging evidence is the G6 hard-gate path.
- M3.6a post-review fixes that must carry forward: validate artifact extensions by manifest field, threshold-check real evidence, apply hard-gate checks only to real staging profiles, and keep example evidence non-pass.
- `.pre-commit-config.yaml` already excludes the public prompt fixture SHA-256 from detect-secrets; if the same hash appears in new single-node JSON examples, do not add broader secret-scan exclusions.

### Repository Context

- Existing static validation patterns use stdlib Python validators and pytest tests under `tests/test_*`.
- Existing CI uses `dorny/paths-filter`; keep chat load validation focused under the existing `chat-load-plan-validation` job.
- `apps/chat-service/` does not yet provide a production Chat runtime for CI to exercise. CI must stay static/helper based.
- Real evidence artifact directories under `reports/` are future operator inputs; do not fabricate real pass evidence.

### Metric Definitions

- `first_token_latency_ms`: elapsed milliseconds from request start to first non-empty streamed token/content chunk.
- `total_response_latency_ms`: elapsed milliseconds from request start to stream completion.
- `streaming_tokens_per_second`: streamed token/content units after first token divided by post-first-token streaming duration.
- `e2e_solve_p95_ms`: advisory single-node P95 for Chat-to-solve prompts; cannot claim hard-gate pass.
- `sandbox_startup_p95_ms`: advisory P58 startup metric for warm-pool tuning.
- `capability_lookup_p95_ms`: advisory P57 capability lookup metric; target reference is < 20 ms.
- `chat_internal_hop_p95_ms`: advisory cumulative chat-service internal hop metric; target reference is <= 200 ms.
- `token_count_method`: `provider_usage` when provider emits token counts, otherwise `content_unit_approximation`.

### Architecture / External Constraints

- Single-node results are advisory tuning data only. Do not mark `hard_gate_candidate=true`, do not alter M3.6a staging manifest semantics, and do not let single-node evidence satisfy `--evidence` staging validation.
- Artifact paths must be repository-relative, normalized, and under `reports/chat-single-node/<run_id>/`.
- Reject traversal, absolute paths, URL schemes, and Windows drive prefixes.
- No secrets in committed assets: reject keys matching token/password/secret/private-key/access-key/cookie/session/bearer and known provider key shapes.
- Use JSON for machine-readable profiles and evidence. Use Markdown only for the operator runbook and story.

### Testing / Validation Notes

Expected local commands after implementation:

```bash
uv run python scripts/validate_chat_load_plan.py
uv run pytest tests/test_chat_load_plan.py -q
uv run ruff check scripts/validate_chat_load_plan.py tests/test_chat_load_plan.py tools/chat_load/single_node_locustfile.py
uv run ruff format --check scripts/validate_chat_load_plan.py tests/test_chat_load_plan.py tools/chat_load/single_node_locustfile.py
uv run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

### Risks / Decisions

- Data consistency risk: single-node profile, locust profile name, schema, example manifest, tests, and runbook can drift. Validator must compare all of them.
- Function consistency risk: single-node profile could accidentally be treated as staging evidence. Validator and schema must separate `reports/chat-single-node/**` from `reports/chat-load/**`.
- Function drift risk: first-token latency and total response latency can be collapsed. Tests must keep required metric names distinct.
- Function drift risk: single-node locust code could duplicate M3.6a stream metric formulas. Require import/reuse of `calculate_stream_metrics()` and static tests for the reference.
- Function drift risk: internal P57/P58 metrics are not produced by Locust itself. Runbook and example manifest must label them as metrics-snapshot/operator observations, not stream response measurements.
- Boundary risk: advisory P57 thresholds can be misread as hard-gate pass. Store `advisory_only=true` and `hard_gate_candidate=false` and validate both.
- Boundary risk: adding optional real evidence loops could fail branches with no evidence. CI must treat absence of `reports/chat-single-node/**/evidence_manifest.json` as normal.
- Closure risk: implementation could fabricate real evidence to satisfy the story. This story may commit only plan assets and deterministic example evidence; real artifacts must arrive later through operator evidence PRs.
- Closure risk: sprint status could move to `ready-for-dev` before review closure. Only update sprint status after the Round 3 review log says PASS.
- Scope risk: this story should not implement a production Chat path or incident fallback.

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Made the single-node profile structure explicit as `profiles.single_node_baseline` instead of an ambiguous flat `profile` field.
- Added required `node_count=1` and exact profile numeric fields so the 20 users x 6 req/min = 2 RPS math is machine-checkable.
- Added advisory thresholds for P58/P57 internal metrics that were already required in evidence metrics: sandbox startup, capability lookup, and chat internal hop.
- Pinned real evidence environment to `single-node-dev` and required artifact paths to reuse the manifest `run_id`.
- Expanded validator expectations to reject extra profiles, environment drift, node-count drift, and run_id path drift.

Status: PASS after fixes.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Required explicit pure helpers in `single_node_locustfile.py` for profile loading, env selection, request interval, and endpoint resolution.
- Required single-node Locust to reuse M3.6a `calculate_stream_metrics()` so first-token, total-response, and streaming formulas cannot drift.
- Clarified that Locust supplies stream/request metrics while `metrics_snapshot` supplies sandbox startup, capability lookup, internal hop, OOM, and deadlock observations.
- Added exact CI command requirement for `--single-node-evidence` evidence validation.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Explicitly forbade committing real single-node evidence artifacts in this story; only deterministic example evidence is in scope.
- Clarified that future real single-node evidence must arrive through `reports/chat-single-node/<run_id>/evidence_manifest.json` in a later operator evidence PR.
- Added closure risk controls so sprint status moves to `ready-for-dev` only after all three story review rounds are recorded as PASS.
- Reaffirmed that single-node advisory evidence cannot satisfy M3.6a staging hard-gate evidence.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Implementation Notes

- Implemented M3.6b as a single-node advisory baseline plan and evidence contract, not as real pass evidence.
- Added a single-node Locust entrypoint that reuses M3.6a stream metric helpers to avoid first-token/throughput formula drift.
- Added machine-checkable single-node profile config with 1 node, 20 users, 300 seconds, 2 RPS, advisory P57/P58 thresholds, and non-hard-gate flags.
- Added single-node evidence schema/example under `reports/chat-single-node/<run_id>/` semantics with metrics snapshot separation.
- Extended the existing chat load validator and test suite while preserving M3.6a staging validation behavior.
- Added CI path filters and optional future real single-node evidence validation loop.
- Post-implementation review fixes applied: JSON Schema now separates Locust report and metrics snapshot artifact extension contracts, and validator rejects nested single-node hard-gate candidate/pass claims.

### File List

- `.github/workflows/ci.yml`
- `docs/runbooks/chat-single-node-baseline.md`
- `scripts/validate_chat_load_plan.py`
- `tests/test_chat_load_plan.py`
- `tools/chat_load/single_node_evidence_manifest.example.json`
- `tools/chat_load/single_node_evidence_manifest.schema.json`
- `tools/chat_load/single_node_locustfile.py`
- `tools/chat_load/single_node_profiles.json`
- `_bmad-output/stories/m3-6b-chat-single-node-baseline.md`
- `_bmad-output/stories/sprint-status.yaml`

### Validation Evidence

- `uv run python scripts/validate_chat_load_plan.py` — PASS
- `uv run pytest tests/test_chat_load_plan.py -q` — PASS, 26 tests
- `uv run ruff check scripts/validate_chat_load_plan.py tests/test_chat_load_plan.py tools/chat_load/single_node_locustfile.py` — PASS
- `uv run ruff format --check scripts/validate_chat_load_plan.py tests/test_chat_load_plan.py tools/chat_load/single_node_locustfile.py` — PASS
- `uv run pytest tests/test_chat_load_plan.py -q` — PASS, 27 tests after code review fixes
- `uv run python scripts/validate_chat_load_plan.py` — PASS after code review fixes
- `uv run pre-commit run --all-files --show-diff-on-failure` — PASS
- `git diff --check` — PASS

## Senior Developer Review (AI)

Outcome: PASS after fixes

Findings fixed:
- Single-node evidence JSON Schema used one generic artifact path for both Locust reports and metrics snapshots. Split it into `locustReportPath` and `metricsSnapshotPath` so metrics snapshots are JSON-only at schema level as well as validator level.
- Single-node hard-gate boundary checks only covered a root-level `hard_gate_candidate`. Extended manifest validation to reject nested `hard_gate_candidate` and `hard_gate_pass` claims anywhere in single-node evidence.

Residual risk:
- This story still does not produce real single-node evidence by design; operator evidence must be generated later using `--single-node-evidence`.

### Change Log

- 2026-05-26: Initial draft created for M3.6b story context and review workflow.
- 2026-05-26: Completed three pre-implementation review rounds and moved story to ready-for-dev.
- 2026-05-26: Started implementation and moved story to in-progress.
- 2026-05-26: Added single-node profile, Locust entrypoint, evidence contract, validator/tests, runbook, and CI wiring.
- 2026-05-26: Moved story to code-review after implementation validation passed.
- 2026-05-26: Completed post-implementation code review and applied schema/hard-gate boundary fixes.
- 2026-05-26: Final validation passed and story moved to done.
