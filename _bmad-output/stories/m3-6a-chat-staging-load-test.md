# Story M3.6a: Chat 延迟预算 staging 压测

Status: done

owner: SRE / NFR-P owner

## Story

As a NFR-P owner / SRE,
I want 5 节点 K8s staging 真实环境 Chat 延迟预算分级压测的可重复执行 harness、prompt fixture、报告契约和 CI 校验,
so that G6 Critical Gap 可以用真实 operator evidence 解锁，并且不会用伪造结果误判 M3/M5 hard-gate。

## Acceptance Criteria

1. Locust 压测 harness 明确覆盖 M3.6a 三档负载。
   - Add `tools/chat_load/locustfile.py` as the canonical Chat staging load-test entrypoint.
   - The locustfile must define scenarios for `baseline`, `stress`, and `soak`, and must refuse unknown profile names.
   - Baseline profile must model **5 RPS** with 100 users. Because the epic text also says "100 user × 1 req/min" which only yields about 1.67 RPS, the implementation must record that source note separately and use an effective pacing of 3 requests/minute/user to reach 5 RPS.
   - Stress profile must model **100 RPS** as 100 concurrent users for 30 minutes, with effective pacing of about 1 request/second/user.
   - Soak profile must model **12h × 10 RPS** for long-run stability and memory/deadlock evidence; if 100 users are used, effective pacing is 6 requests/minute/user.
   - The harness must select profiles through `CHAT_LOAD_PROFILE` or an equivalent explicit option and default to `baseline`.
   - The harness must target a configurable Chat SSE endpoint through `CHAT_LOAD_ENDPOINT`, defaulting to a non-production placeholder such as `/v1/chat/stream`.
   - The harness must rely on the Locust `--host` value or `CHAT_LOAD_BASE_URL` for the staging base URL; no base URL may be committed.
   - The harness must run without embedded credentials, API keys, tenant IDs, or production URLs.
   - The harness must capture first-token latency, total response latency, streaming token throughput, HTTP status, stream completion, request count, completed stream count, and per-prompt metadata.
   - The harness must treat first-token latency as time from request start until the first non-empty SSE/data token chunk, not total response time.
   - The harness must compute streaming throughput only after first token and only from streamed token/content chunks.
   - The harness must record the token-count method. If an SSE chunk includes provider token usage, use it; otherwise use a documented deterministic token-unit approximation and label it as `content_unit_approximation`.
   - `locustfile.py` must expose pure helper functions for profile loading, SSE event parsing, token-unit extraction, and metric calculation so tests/validator can inspect behavior without a live staging endpoint.
   - CI must not require Locust to be installed or import a live Locust runtime; validator/tests may use AST/static checks or helper functions that do not start a Locust swarm.
   - The harness must not call real external LLM APIs in CI.

2. Prompt fixture is deterministic, redacted, and sufficient for staging execution.
   - Add `tools/chat_load/prompts_v1.json` with root metadata plus exactly 100 prompt records under `prompts`.
   - Root metadata must include `dataset_version=chat_load_prompts_v1`, `source_story=M3.6a`, and `prompt_count=100`.
   - Each prompt must have stable `id`, `locale`, `category`, `difficulty`, `expected_path`, and `prompt` fields.
   - IDs must be contiguous and stable, `chat-load-v1-001` through `chat-load-v1-100`.
   - The fixture must include Chinese, English, and mixed zh/en prompts.
   - The fixture must cover optimization, prediction, explanation, file-analysis, what-if, and benign support-chat categories, with at least 10 prompts in each category.
   - `expected_path` must be one of `chat_only` or `solve_expected`, with at least 30 `solve_expected` prompts so E2E solve metrics cannot be claimed from non-solve chat prompts.
   - Prompt text must be synthetic or redacted and must not include credentials, private datasets, raw customer content, production tenant identifiers, unredacted PII, provider payloads, or legal/compliance secrets.
   - Prompt ordering must be deterministic and must not depend on wall-clock time or random shuffling.

3. Staging profile config and threshold contract are machine-checkable.
   - Add `tools/chat_load/staging_profiles.json` as the source of truth for profile names, users, spawn rate, run time, target RPS, and threshold budgets.
   - The profile file must encode:
     - `baseline`: 100 users, source note `100 user × 1 req/min`, effective 3 requests/minute/user, target 5 RPS, P95 first-token < 2000 ms.
     - `stress`: 100 concurrent users, 1800 seconds, effective 60 requests/minute/user, target 100 RPS, P50 first-token < 1500 ms, P95 first-token < 3000 ms, streaming >= 20 token/s.
     - `soak`: 43200 seconds, target 10 RPS, recommended 100 users, effective 6 requests/minute/user, 0 OOM, 0 deadlock, streaming >= 20 token/s.
   - The profile file must include the architecture hard-gate thresholds in numeric ms fields: first-token P95 < 3000 ms, streaming >= 20 token/s, E2E solve <= 90000 ms.
   - The profile file must include a deterministic prompt fixture hash field computed as SHA-256 over canonical JSON bytes for `tools/chat_load/prompts_v1.json`.
   - The profile file must distinguish first-token latency, total response latency, and E2E solve duration; these metrics must not be collapsed into one field.
   - The profile file must make RPS math explicit enough for validation: `users * effective_requests_per_user_per_minute / 60` must equal target RPS within a small deterministic tolerance.
   - Config values must be numeric where they are later compared by validators.
   - The config must not contain live cluster URLs, bearer tokens, cookies, or secrets.

4. Evidence manifest schema prevents fake or incomplete staging results.
   - Add `tools/chat_load/evidence_manifest.schema.json` describing required operator-provided evidence for each profile.
   - Add `tools/chat_load/evidence_manifest.example.json` as a deterministic, clearly non-production example manifest.
   - The schema must require exactly three profile evidence entries: `baseline`, `stress`, and `soak`.
   - Each profile entry must require one Locust report artifact, one Grafana dashboard screenshot artifact, start/end timestamps, git commit SHA, cluster descriptor, node count, endpoint path, prompt fixture hash, prompt count, and summary metrics.
   - Artifact paths must be repository-relative and point under `reports/chat-load/<run_id>/`, where `<run_id>` exactly matches the manifest `run_id`.
   - Grafana screenshots must be `.png`; Locust reports must be `.html` or `.json`.
   - The manifest must require staging cluster `node_count=5` for real M3.6a evidence.
   - The manifest must require metrics for request count, first-token P50/P95 in ms, total response P95 in ms, streaming token/s, token-count method, HTTP error rate, completed streams, prompt count, solve prompt count, OOM count, deadlock count, and E2E solve P95 in ms.
   - Pass/fail evaluation must compare ms metrics to ms thresholds; no validator or report may mix seconds and milliseconds.
   - The example manifest must be marked `example_only: true` and must not be accepted as real pass evidence.
   - CI may validate schema and example shape only; it must not claim the staging run passed.
   - Real operator evidence manifests, when produced later, must live at `reports/chat-load/<run_id>/evidence_manifest.json` and must set `example_only=false`.
   - Real report HTML/JSON and screenshot artifacts must be redacted before archive; no cookies, bearer tokens, internal hostnames with credentials, Grafana share tokens, or provider request/response payloads may be committed.

5. Static validator and tests close data/function drift before real staging runs.
   - Add `scripts/validate_chat_load_plan.py`.
   - By default the validator must validate the committed plan assets and example manifest only.
   - The validator must also support an explicit `--evidence reports/chat-load/<run_id>/evidence_manifest.json` mode for future operator evidence PRs.
   - The validator must check prompt root metadata, prompt count/IDs, category coverage, `expected_path` coverage, profile config consistency, baseline pacing math, scenario/profile alignment, prompt fixture hash consistency, metric unit fields, evidence schema/example shape, artifact path constraints, and forbidden secret-like values.
   - The validator must reject missing profiles, profile-name drift, target/threshold drift, non-5-node real evidence, missing screenshot/report entries, unsafe artifact paths, and example manifests presented as pass evidence.
   - The validator must reject metric formula drift signals such as using total response latency as first-token latency, omitting streaming throughput, omitting token-count method, omitting request/completed counts, mixing seconds/ms threshold fields, or accepting E2E solve P95 when `solve_prompt_count=0`.
   - The validator must run stdlib-only plus already available repository dependencies; do not add new Python dependencies unless existing lock/config already contains them.
   - Add `tests/test_chat_load_plan.py` covering success and failure cases for prompts, profiles, evidence manifests, artifact constraints, secret scanning, and formula guardrails.

6. Runbook documents exact operator handoff without credentials.
   - Add `docs/runbooks/chat-staging-load-test.md`.
   - The runbook must explain how an operator runs baseline, stress, and soak profiles against the 5-node staging cluster.
   - The runbook must list required environment variables without providing real values or secrets.
   - The runbook must describe how to archive three Grafana screenshots and three Locust reports under `reports/chat-load/<run_id>/`.
   - The runbook must define pass/fail interpretation for Baseline P95 < 2s, Stress P50 < 1.5s / P95 < 3s, streaming >= 20 token/s, Soak 0 OOM / 0 deadlock, and E2E <= 90s.
   - The runbook must document failure follow-up: if G6 fails, open architecture work for critic async, AIGC Layer 2 offline/deferred, provider fallback, or capacity tuning.
   - The runbook must state that CI artifacts are only structural validation, not real staging proof.

7. CI enforces the harness contract without requiring staging access.
   - Extend `.github/workflows/ci.yml` path filters with a `chat_load_plan` output.
   - Add a CI job that runs `uv run python scripts/validate_chat_load_plan.py` and `uv run pytest tests/test_chat_load_plan.py -v`.
   - The CI job must trigger on changes to `tools/chat_load/**`, `scripts/validate_chat_load_plan.py`, `tests/test_chat_load_plan.py`, `docs/runbooks/chat-staging-load-test.md`, and `reports/chat-load/**`.
   - CI must validate real evidence manifests only when they are present under `reports/chat-load/**`; otherwise it must validate the committed plan/example only.
   - The CI job must not require Kubernetes, Grafana, Locust runtime against a live cluster, cloud credentials, external network, or LLM provider keys.

8. Workflow tracking and boundaries are explicit.
   - This story records three pre-implementation story review rounds and fixes after each round before implementation.
   - `_bmad-output/stories/sprint-status.yaml` moves `m3-6a-chat-staging-load-test` to `ready-for-dev` only after all three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.
   - This story must not implement a production Chat runtime, real LLM provider integration, K8s cluster creation, Grafana dashboard creation, real staging execution, uploaded screenshots, real Locust pass reports, incident fallback, single-node baseline ownership, or API gateway baseline ownership.
   - M3.6b remains the single-node baseline story; M3.6c remains incident fallback; M3.6d remains API gateway performance baseline.

## Tasks / Subtasks

- [x] Build Chat load-test assets. (AC: 1, 2, 3)
  - [x] Add `tools/chat_load/locustfile.py`.
  - [x] Add exactly 100 sanitized prompt records in `tools/chat_load/prompts_v1.json`.
  - [x] Add `tools/chat_load/staging_profiles.json` with baseline/stress/soak definitions and thresholds.
- [x] Build evidence contract. (AC: 4)
  - [x] Add `tools/chat_load/evidence_manifest.schema.json`.
  - [x] Add `tools/chat_load/evidence_manifest.example.json`.
  - [x] Ensure example evidence cannot be mistaken for real pass evidence.
- [x] Add validator and regression tests. (AC: 5)
  - [x] Add `scripts/validate_chat_load_plan.py`.
  - [x] Add `tests/test_chat_load_plan.py`.
  - [x] Cover prompt root metadata, prompt count, ID sequence, categories, `expected_path` coverage, profile thresholds, baseline pacing math, metric units, prompt fixture hash, Locust profile references, manifest shape, `--evidence` mode, artifact paths, secret scans, and negative drift cases.
- [x] Add operator runbook. (AC: 6)
  - [x] Add `docs/runbooks/chat-staging-load-test.md`.
  - [x] Document operator commands, env vars, evidence archive, pass/fail criteria, and failure follow-up.
- [x] Wire CI. (AC: 7)
  - [x] Add `chat_load_plan` path filter output and filter paths in `.github/workflows/ci.yml`.
  - [x] Add `chat-load-plan-validation` CI job.
  - [x] Include `reports/chat-load/**` in the path filter for future operator evidence PRs.
- [x] Update workflow records and validation evidence. (AC: 8)
  - [x] Record implementation notes, file list, and change log.
  - [x] Move sprint status through `ready-for-dev`, `in-progress`, `code-review`, and `done` only after gates pass.
  - [x] Run post-implementation code review and apply fixes.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:1167` defines M3.6a as G6 Critical Gap for 5-node K8s staging Chat latency load testing.
- `_bmad-output/planning/epics.md:1175` requires staging 5 nodes, Locust script, 100 real test prompts, three load levels, and three Grafana screenshots plus three Locust reports.
- `_bmad-output/planning/architecture.md:1681` defines P57 Chat Path latency budget.
- `_bmad-output/planning/architecture.md:1692` sets total SLO: first token P50 < 1.5s, P95 < 3s, E2E solve <= 90s.
- `_bmad-output/planning/architecture.md:2437` defines the G6 hard-gate: staging full-stack load test must hit first-token P95 < 3s, streaming >= 20 Token/s, E2E <= 90s.
- `_bmad-output/planning/prd.md:1594` states API/Chat latency tests use Locust, SSE first-token timestamps, and streaming load tests.
- `_bmad-output/planning/prd.md:1599` says M3 starts instrumentation and monitoring, while M5 is the KPI attainment gate.

### Repository Context

- `apps/chat-service/` and `apps/api-gateway/` currently do not contain a production Chat runtime implementation for this story to exercise locally.
- Existing static validation patterns live in `scripts/validate_blue_green_deploy.py`, `scripts/validate_image_archival_plan.py`, and matching `tests/test_*` files.
- Existing CI uses `dorny/paths-filter` and focused validation jobs; mirror that pattern instead of adding a broad always-on job.
- `reports/` is not currently a committed evidence directory. Real staging artifacts should be archived there by operators in a future evidence PR or release artifact bundle, not fabricated by this implementation.

### Scope Decisions

- This story creates the deterministic load-test harness and evidence contract required to run M3.6a; it does not claim that a 5-node staging run has already passed.
- Treat "100 真实测试 prompt" as 100 realistic, synthetic/redacted staging prompts committed to the repo. Do not use raw customer data or production prompt logs.
- Preserve the epic's inconsistent baseline source note (`100 user × 1 req/min`) as metadata only; do not encode it as the effective 5 RPS load profile because it yields about 1.67 RPS.
- Treat "3 Grafana dashboard screenshots + 3 Locust reports archived" as an evidence manifest/schema contract and runbook handoff. The real screenshots and reports must be produced by an operator against staging.
- CI validates structure, thresholds, and drift guards only. CI must not require live staging, Locust swarm runtime, Grafana, Kubernetes, external LLM APIs, or credentials.
- If future real evidence is committed, it must be under `reports/chat-load/<run_id>/` with a real `evidence_manifest.json`; this story only supplies the validator path and redaction rules.
- Do not add runtime Chat, LLM router, provider fallback, or API gateway performance code in this story; those belong to M3.6b/M3.6c/M3.6d or Epic 4.A/B/C.

### Metric Definitions

- `first_token_latency_ms`: elapsed milliseconds from request start to the first non-empty streamed token/content chunk.
- `total_response_latency_ms`: elapsed milliseconds from request start to stream completion.
- `streaming_tokens_per_second`: streamed token/content units after first token divided by post-first-token streaming duration.
- `e2e_solve_latency_ms`: elapsed milliseconds for the whole Chat-to-solve workflow when the staged prompt triggers a solve path; non-solve prompts must not be used to claim E2E solve pass.
- `oom_count` and `deadlock_count`: operator-provided cluster/runtime observations for soak; zero is required for pass.
- `token_count_method`: `provider_usage` when provider emits token counts, otherwise `content_unit_approximation`; evidence must disclose which method was used.

### Architecture / External Constraints

- No secrets in committed assets: reject keys matching token/password/secret/private-key/access-key/cookie/session/bearer and known provider key shapes.
- Real evidence must name the cluster as staging and require `node_count=5`; examples may use fake/example cluster names and `example_only=true`.
- Evidence artifact paths must be repository-relative, normalized, and under `reports/chat-load/<run_id>/`.
- Real evidence artifact paths must resolve inside the same `run_id` directory as the real manifest and must not traverse with `..`, absolute paths, URL schemes, or Windows drive prefixes.
- Use JSON for machine-readable plans and evidence. Use Markdown only for the operator runbook.
- Keep generated examples deterministic, LF-normalized, and without wall-clock timestamps.

### Testing / Validation Notes

Expected local commands after implementation:

```bash
uv run python scripts/validate_chat_load_plan.py
uv run pytest tests/test_chat_load_plan.py -v
uv run ruff check scripts/validate_chat_load_plan.py tests/test_chat_load_plan.py
uv run ruff format --check scripts/validate_chat_load_plan.py tests/test_chat_load_plan.py
uv run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

### Risks / Decisions

- Data consistency risk: prompts, profiles, locust scenario names, evidence schema, example manifests, and tests can drift. Validator must compare all of them.
- Data consistency risk: the epic's baseline source line mixes 5 RPS with 100 users at 1 req/min. Validator must require effective pacing that reaches 5 RPS and keep the inconsistent source phrase as a note only.
- Function consistency risk: first-token latency can be accidentally replaced by total response latency. Locust code, schema, and tests must name and validate both separately.
- Function drift risk: streaming throughput can be computed over the whole request instead of post-first-token streaming. Tests should guard naming and required fields.
- Function drift risk: evidence may mix seconds and milliseconds. Store and compare latency thresholds in numeric `*_ms` fields.
- Function drift risk: Locust may not be installed in CI. Validation must be static/helper based and must not require a live Locust runtime.
- Boundary risk: CI could be misread as proving staging passed. Example manifest must be rejected as pass evidence and runbook must state CI is structural only.
- Closure risk: story status can jump before reviews. `Status: ready-for-dev` is allowed only after three review rounds are recorded as pass.
- Evidence risk: real staging artifacts may include URLs or tokens in report HTML. Runbook must require redaction before archive.
- Boundary risk: adding `reports/chat-load/**` to CI could make empty/no-evidence branches noisy. CI must treat the absence of real evidence as normal and validate only plan assets.

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Corrected the impossible baseline math from the source epic. `100 users × 1 req/min` is about 1.67 RPS, so the story now requires effective pacing of 3 req/min/user for the 5 RPS baseline while preserving the source phrase as metadata.
- Added root metadata requirements for `prompts_v1.json` so `prompt_count=100`, dataset version, and source story cannot drift from the prompt records.
- Added minimum category coverage for the 100 prompt fixture so a nominally complete fixture cannot be one-class biased.
- Added canonical prompt fixture SHA-256 requirements and evidence `prompt_count` so reports can be tied back to the committed fixture.
- Tightened evidence artifact paths to require `reports/chat-load/<run_id>/` to match the manifest `run_id`.
- Added solve prompt count to evidence metrics so E2E solve P95 is not claimed from non-solve prompts.

Status: PASS after fixes.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Converted threshold requirements to explicit millisecond fields so first-token, total response, and E2E solve metrics cannot mix seconds and milliseconds.
- Required explicit RPS math in profile config so users, pacing, and target RPS stay functionally consistent across baseline/stress/soak.
- Added `expected_path` to prompts and minimum solve-prompt coverage so E2E solve P95 cannot be claimed from pure chat prompts.
- Added token-count method disclosure and fallback semantics because SSE streams may not expose provider token usage.
- Required pure helper functions/static validation paths so CI does not need Locust installed or a live staging endpoint.
- Expanded validator drift checks for total-response-vs-first-token confusion, missing request/completed counts, missing token-count method, and `solve_prompt_count=0`.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Added an explicit split between default plan/example validation and future `--evidence reports/chat-load/<run_id>/evidence_manifest.json` validation.
- Required future real evidence manifests to live under `reports/chat-load/<run_id>/` with `example_only=false`, while the committed example remains non-pass evidence.
- Added report/screenshot redaction boundaries for cookies, bearer tokens, Grafana share tokens, credentialed URLs, provider payloads, and internal credentials.
- Added `reports/chat-load/**` to CI trigger requirements for future operator evidence PRs, with the guard that absence of real evidence is not a CI failure.
- Tightened artifact path boundaries against traversal, absolute paths, URL schemes, and Windows drive prefixes.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Implementation Notes

- Implemented M3.6a as a deterministic staging load-test harness and evidence contract rather than fake staging results.
- Added Locust-compatible helpers that CI can inspect without requiring Locust runtime or a live staging endpoint.
- Preserved the epic's inconsistent baseline note as metadata while enforcing effective 5 RPS pacing.
- Bound profile config to the committed 100-prompt fixture through canonical SHA-256.
- Added default plan/example validation plus explicit future `--evidence reports/chat-load/<run_id>/evidence_manifest.json` validation mode.
- Post-implementation review fixes applied: artifact extensions are now checked by manifest field, real evidence is threshold-checked, and hard-gate thresholds apply across all real evidence profiles.

### File List

- `.github/workflows/ci.yml`
- `docs/runbooks/chat-staging-load-test.md`
- `scripts/validate_chat_load_plan.py`
- `tests/test_chat_load_plan.py`
- `tools/chat_load/evidence_manifest.example.json`
- `tools/chat_load/evidence_manifest.schema.json`
- `tools/chat_load/locustfile.py`
- `tools/chat_load/prompts_v1.json`
- `tools/chat_load/staging_profiles.json`
- `_bmad-output/stories/m3-6a-chat-staging-load-test.md`
- `_bmad-output/stories/sprint-status.yaml`

### Validation Evidence

- `uv run python scripts/validate_chat_load_plan.py` — PASS
- `uv run pytest tests/test_chat_load_plan.py -q` — PASS, 16 tests
- `uv run ruff check scripts/validate_chat_load_plan.py tests/test_chat_load_plan.py` — PASS
- `uv run ruff format --check scripts/validate_chat_load_plan.py tests/test_chat_load_plan.py` — PASS
- `git diff --check` — PASS
- `uv run pre-commit run --all-files --show-diff-on-failure` — PASS

## Senior Developer Review (AI)

Outcome: PASS after fixes

Findings fixed:
- Artifact extension validation was tied to filename substrings rather than the semantic manifest field. Fixed `_artifact_path_errors()` to validate `.png` for `grafana_screenshot` and `.html`/`.json` for `locust_report` regardless of filename text, with regression coverage.
- Real `--evidence` manifests initially validated structure but did not reject failed metrics. Added profile-threshold checks for first-token, streaming, OOM, and deadlock metrics.
- Real evidence threshold checks did not apply the architecture G6 hard-gate uniformly across all profiles. Added hard-gate checks for first-token P95, streaming throughput, and E2E solve P95, with regression coverage.

Residual risk:
- This story does not produce real 5-node staging evidence by design; operator evidence must be generated and validated later using `--evidence`.

### Change Log

- 2026-05-26: Initial draft created for M3.6a story context and review workflow.
- 2026-05-26: Completed three pre-implementation review rounds and moved story to ready-for-dev.
- 2026-05-26: Started implementation and moved story to in-progress.
- 2026-05-26: Added Chat staging load-test harness, prompt fixture, profiles, evidence contract, validator, tests, runbook, and CI job.
- 2026-05-26: Completed post-implementation code review and applied validator threshold/path fixes.
- 2026-05-26: Moved story to code-review after implementation and review fixes.
- 2026-05-26: Final validation passed and story moved to done.
