# Story M3.6d: API 网关性能基线压测

Status: done

owner: SRE / NFR-P owner

## Story

As a SRE / NFR-P owner,
I want a repeatable API gateway performance baseline plan, Locust entrypoint, evidence contract, validator, CI hook, and operator runbook,
so that NFR-P1 API gateway P95 < 200 ms can be engineered and later proven by real 30-minute staging evidence without fabricating pass results in CI.

## Acceptance Criteria

1. API gateway performance baseline plan is explicit and separate from Chat load-test evidence.
   - Add `tools/api_gateway_perf/perf_baseline_plan.json` as the source of truth for M3.6d.
   - The plan must use `dataset_version=api_gateway_perf_baseline_v1` and `source_story=M3.6d`.
   - The plan must define one baseline profile named `gateway_baseline` with `users=100`, `spawn_rate_per_second=10`, `run_time_seconds=1800`, and `evidence_directory=reports/api-gateway-perf`.
   - The plan must define exactly three endpoint classes:
     - `algorithms_public`: `GET /v1/algorithms`, auth mode `none`, P95 threshold `< 200 ms`.
     - `auth_api_keys`: `GET /v1/auth/api_keys`, auth mode `jwt_bearer_env`, P95 threshold `< 200 ms`.
     - `business_demo`: `POST /v1/optimizations/demo`, auth mode `none`, P95 threshold `< 500 ms`.
   - The plan must define `grafana_dashboard_required=true`, `prometheus_histogram_quantile=0.95`, and `threshold_operator=strict_less_than`.
   - The plan must not contain production URLs, API keys, JWTs, cookies, tenant IDs, user IDs, real customer payloads, or real solver results.
   - The plan must explicitly state that M3.6d does not mark M3.6a/M3.6b/M3.6c Chat evidence as passed.

2. Locust entrypoint is CI-importable and operator-ready without live credentials.
   - Add `tools/api_gateway_perf/locustfile.py`.
   - The module must expose pure helpers for loading the plan, selecting endpoint classes, building request specs, validating auth headers from environment variables, and computing request interval.
   - CI must be able to import the module without the `locust` package installed.
   - Runtime auth for `/v1/auth/api_keys` must come only from an operator-provided environment variable such as `API_GATEWAY_PERF_JWT`; committed files must never include a real token.
   - Missing `API_GATEWAY_PERF_JWT` must fail only when an operator selects or executes the `auth_api_keys` endpoint class; importing the module and running static validation must not require credentials.
   - The business demo request body must be deterministic, small, and safe: an LP demo payload with no customer data and no billing headers.
   - The Locust task names must preserve endpoint class names so later Locust/Grafana aggregation maps unambiguously to the plan thresholds.
   - Request pacing must derive from the plan's `users` and target endpoint mix, not from hardcoded sleep values in the Locust class.

3. Evidence manifest is structurally validated and cannot be mistaken for real pass evidence.
   - Add `tools/api_gateway_perf/evidence_manifest.schema.json`.
   - Add `tools/api_gateway_perf/evidence_manifest.example.json` as deterministic non-production example evidence.
   - The manifest schema must require `source_story=M3.6d`, `example_only`, `run_id`, `commit_sha`, `environment=staging-api-gateway`, `plan_sha256`, `profile`, `started_utc`, `ended_utc`, `duration_seconds`, `endpoint_results`, and `artifacts`.
   - Artifact fields must be exactly `locust_report`, `grafana_dashboard`, `prometheus_snapshot`, and `latency_summary`.
   - Artifact paths must be repository-relative and under `reports/api-gateway-perf/<run_id>/`, where `<run_id>` exactly matches the manifest `run_id`.
   - `locust_report` must be `.html` or `.json`; `grafana_dashboard` must be `.png`; `prometheus_snapshot` and `latency_summary` must be `.json`.
   - The example manifest must set `example_only=true` and must not be accepted as real API gateway performance evidence.
   - Real evidence, when produced later, must live at `reports/api-gateway-perf/<run_id>/evidence_manifest.json` with `example_only=false`.
   - Real evidence validation must reject a manifest whose `plan_sha256` does not match the committed canonical hash of `tools/api_gateway_perf/perf_baseline_plan.json`.
   - The repository must not commit generated real artifacts under `reports/api-gateway-perf/**` in this story; only the deterministic example manifest under `tools/api_gateway_perf/` is committed.

4. Evidence metrics prove the endpoint-specific NFR-P1 baseline instead of generic request success.
   - The manifest must include exactly one endpoint result for each plan endpoint class.
   - Every endpoint result must include `endpoint_class`, `method`, `path`, `auth_mode`, `request_count`, `success_count`, `http_error_rate`, `locust_p50_ms`, `locust_p95_ms`, `locust_p99_ms`, `prometheus_histogram_quantile_p95_ms`, and `threshold_p95_ms`.
   - The committed plan, manifest schema, example manifest, validator, tests, and runbook must use the same endpoint class names: `algorithms_public`, `auth_api_keys`, and `business_demo`.
   - Real evidence validation must reject `duration_seconds < 1800`.
   - Real evidence validation must reject `success_count > request_count`.
   - Real evidence validation must reject any endpoint with `request_count <= 0`.
   - Real evidence validation must reject any endpoint with `http_error_rate > 0.01`.
   - Real evidence validation must reject any endpoint whose `locust_p95_ms >= threshold_p95_ms`.
   - Real evidence validation must reject any endpoint whose `prometheus_histogram_quantile_p95_ms >= threshold_p95_ms`.
   - Real evidence validation must reject endpoint drift: method/path/auth/threshold must exactly match the committed plan.
   - Real evidence validation must reject missing endpoint classes, duplicate endpoint classes, and extra endpoint classes.
   - Real evidence validation must reject mismatched `duration_seconds` if it does not equal `ended_utc - started_utc`.
   - All latency fields must use milliseconds; the only seconds field is `duration_seconds`.

5. Validator and tests close data/function drift for API gateway performance assets.
   - Add `scripts/validate_api_gateway_perf_plan.py`.
   - The validator must validate committed plan, schema, example manifest, and Locust helper contract by default.
   - Add explicit `--evidence reports/api-gateway-perf/<run_id>/evidence_manifest.json` mode for future operator evidence PRs.
   - The validator must check plan metadata, endpoint classes, methods, paths, auth modes, thresholds, duration, Grafana/Prometheus requirements, schema shape, example-vs-real boundaries, artifact path constraints, metric units, plan hash, endpoint drift, and forbidden secret-like values.
   - The validator must reject `chat_load_pass`, `incident_fallback_pass`, `hard_gate_pass`, or `staging_pass` claims anywhere in API gateway evidence.
   - The validator must reject production hostnames, full URLs in artifact paths, absolute paths, Windows drive prefixes, traversal segments, bearer tokens, API keys, cookies, and secret-like key names in committed plan/example evidence.
   - Add `tests/test_api_gateway_perf_plan.py` covering successful validation and negative cases for endpoint drift, threshold drift, duration drift, artifact path traversal, wrong artifact extension, example evidence presented as real evidence, p95 threshold failure, HTTP error rate failure, success count overflow, endpoint path mode separation, and forbidden secret-like values.
   - Tests must prove API gateway evidence mode is separate from Chat evidence directories.

6. Runbook documents the exact operator workflow without credentials.
   - Add `docs/runbooks/api-gateway-perf-baseline.md`.
   - The runbook must explain how an operator prepares staging, supplies runtime-only credentials, runs Locust at 100 concurrent users for 30 minutes, captures Locust/Grafana/Prometheus artifacts, and submits evidence.
   - The runbook must list required environment variables without providing real values or secrets.
   - The runbook must define pass/fail interpretation: `/v1/algorithms` P95 < 200 ms, `/v1/auth/api_keys` P95 < 200 ms, `/v1/optimizations/demo` P95 < 500 ms, duration >= 1800 s, and HTTP error rate <= 1%.
   - The runbook must state that CI validates structure only and does not prove the real API gateway baseline passed.
   - The runbook must require redaction before committing artifacts.
   - The runbook must state that M3.6d is internal SRE/NFR evidence and does not change customer-facing SLA language.
   - The runbook must define failure follow-up: create or update a performance investigation issue with endpoint class, threshold failure, artifact links, and rollback/mitigation notes before any retry is accepted.

7. CI enforces the API gateway performance contract without requiring live services.
   - Extend `.github/workflows/ci.yml` with an API gateway performance path filter for `tools/api_gateway_perf/**`, `scripts/validate_api_gateway_perf_plan.py`, `tests/test_api_gateway_perf_plan.py`, `docs/runbooks/api-gateway-perf-baseline.md`, and `reports/api-gateway-perf/**`.
   - Add a focused CI job that runs the API gateway performance validator and tests when those paths change.
   - CI must validate real API gateway evidence manifests only when present under `reports/api-gateway-perf/**`.
   - CI must not require Kubernetes, Grafana, Prometheus, Locust runtime against a live service, cloud credentials, external network, JWTs, API keys, or database access.

8. Workflow tracking and boundaries are explicit.
   - This story records three pre-implementation story review rounds and fixes after each round before implementation.
   - `_bmad-output/stories/sprint-status.yaml` moves `m3-6d-api-gateway-perf-baseline` to `ready-for-dev` only after all three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.
   - This story must not implement production API gateway runtime, service mesh, live Prometheus metrics instrumentation, real Grafana dashboards, runtime rate limiting, business endpoint changes, or real pass reports.
   - Future real 30-minute API gateway performance artifacts must be introduced through a separate operator evidence PR; this implementation commits only deterministic example evidence.
   - Final completion must update the story's Dev Agent Record, file list, validation evidence, post-implementation review findings/fixes, and sprint status so the work is auditable end to end.

## Tasks / Subtasks

- [x] Build API gateway performance plan assets. (AC: 1)
  - [x] Add `tools/api_gateway_perf/perf_baseline_plan.json`.
  - [x] Define the three endpoint classes and thresholds without credentials or production URLs.
- [x] Build Locust entrypoint. (AC: 2)
  - [x] Add `tools/api_gateway_perf/locustfile.py`.
  - [x] Keep CI import safe when Locust is not installed.
  - [x] Require runtime-only JWT environment variable for `auth_api_keys`.
- [x] Build evidence contract. (AC: 3, 4)
  - [x] Add `tools/api_gateway_perf/evidence_manifest.schema.json`.
  - [x] Add `tools/api_gateway_perf/evidence_manifest.example.json`.
  - [x] Ensure example and real evidence cannot be mistaken for Chat load evidence.
- [x] Add validator and regression tests. (AC: 5)
  - [x] Add `scripts/validate_api_gateway_perf_plan.py`.
  - [x] Add `tests/test_api_gateway_perf_plan.py`.
  - [x] Cover endpoint/threshold drift, boundary failures, and evidence path separation.
- [x] Add operator runbook. (AC: 6)
  - [x] Add `docs/runbooks/api-gateway-perf-baseline.md`.
  - [x] Document setup, execution, evidence archive, redaction, and pass/fail rules.
- [x] Wire CI. (AC: 7)
  - [x] Add API gateway performance paths to CI filters.
  - [x] Add static validation, optional real evidence validation, and tests.
- [x] Update workflow records and validation evidence. (AC: 8)
  - [x] Record implementation notes, file list, and change log.
  - [x] Move sprint status through `ready-for-dev`, `in-progress`, `code-review`, and `done` only after gates pass.
  - [x] Run post-implementation code review and apply fixes.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:1191` defines M3.6d as API 网关性能基线压测 for Q-T3 / NFR-P1.
- `_bmad-output/planning/epics.md:1195` requires Locust 100 concurrent for 30 minutes, `/v1/algorithms` P95 < 200 ms, `/v1/auth/api_keys` P95 < 200 ms, business endpoint P95 < 500 ms, and Grafana dashboard archival.
- `_bmad-output/planning/prd.md:326` and `_bmad-output/planning/prd.md:760` define API gateway P95 < 200 ms from M3.
- `_bmad-output/planning/prd.md:1594` defines the test method as Locust continuous load plus Prometheus `histogram_quantile(0.95)`.
- `_bmad-output/planning/architecture.md:2881` defines `api-gateway` `latency_p95: 200ms`.
- `_bmad-output/planning/architecture.md:2914` through `2916` define latency baseline checks and the `api-gateway` initial trigger at P95 > 400 ms.

### Endpoint Scope

- `/v1/algorithms` exists in `apps/solver-orchestrator/src/solver_orchestrator/routes.py` as a public `GET` route.
- `/v1/auth/api_keys` exists in `apps/auth-service/src/auth_service/routes.py` as an authenticated `GET` route that requires a Bearer JWT.
- `/v1/optimizations/demo` exists in `apps/solver-orchestrator/src/solver_orchestrator/routes.py` as an unauthenticated demo business route. It is the representative M3.6d business endpoint because it avoids committing JWT/API key material and exercises a real business path.
- The future deployed API gateway may route these paths to multiple services; this story validates the baseline contract and operator evidence shape, not the gateway implementation.

### Previous Story Intelligence

- M3.6a/M3.6b/M3.6c established the repository pattern: deterministic plan/schema/example assets, static validator, focused pytest coverage, optional real evidence validation mode, runbook, and CI path filter.
- Preserve the important post-review fixes from M3.6a-c: artifact path traversal rejection, semantic artifact extension checks, example evidence cannot be accepted as real evidence, real evidence gets threshold-checked, and advisory/drill evidence cannot claim unrelated hard-gate semantics.
- Do not extend `tools/chat_load/` or `scripts/validate_chat_load_plan.py` for M3.6d unless a shared helper is truly required. API gateway performance evidence is a separate NFR-P1 lane.

### Repository Context

- `apps/api-gateway/` is not yet populated with a production runtime in this branch. CI must stay static/evidence-contract based.
- Existing service-level Prometheus `/metrics` endpoints exist in auth-service and solver-orchestrator, but this story does not add live histogram instrumentation.
- Real evidence under `reports/` is future operator input; this story must not fabricate a real 30-minute pass.

### Metric Definitions

- `locust_p95_ms`: Locust endpoint-class request latency P95 in milliseconds.
- `prometheus_histogram_quantile_p95_ms`: Prometheus `histogram_quantile(0.95)` value for the same endpoint class and measurement window.
- `threshold_p95_ms`: committed threshold for the endpoint class from `perf_baseline_plan.json`.
- `http_error_rate`: failed HTTP responses divided by total request count for the endpoint class; real evidence threshold is <= 0.01.
- `duration_seconds`: elapsed measurement duration from `started_utc` to `ended_utc`; real evidence must be >= 1800.

### Architecture / External Constraints

- Artifact paths must be repository-relative, normalized, and under `reports/api-gateway-perf/<run_id>/`.
- Reject traversal, absolute paths, URL schemes, and Windows drive prefixes.
- Use JSON for machine-readable plans and evidence. Use Markdown only for the operator runbook and story.
- Runtime secrets must be passed only through environment variables on the operator machine and must never appear in committed JSON, Markdown, tests, or examples.

### Testing / Validation Notes

Expected local commands after implementation:

```bash
uv run python scripts/validate_api_gateway_perf_plan.py
uv run pytest tests/test_api_gateway_perf_plan.py -q
uv run ruff check scripts/validate_api_gateway_perf_plan.py tests/test_api_gateway_perf_plan.py tools/api_gateway_perf/locustfile.py
uv run ruff format --check scripts/validate_api_gateway_perf_plan.py tests/test_api_gateway_perf_plan.py tools/api_gateway_perf/locustfile.py
uv run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

The implementation should run the focused validator/test commands immediately after each validator change while developing:

```bash
uv run python scripts/validate_api_gateway_perf_plan.py
uv run pytest tests/test_api_gateway_perf_plan.py -q
```

### Risks / Decisions

- Data consistency risk: endpoint classes, methods, auth modes, thresholds, schema, example manifest, tests, and runbook can drift.
- Function consistency risk: `/v1/auth/api_keys` could accidentally use a committed JWT or API key. Require `API_GATEWAY_PERF_JWT` runtime env only.
- Function drift risk: gateway P95 < 200 ms can be incorrectly applied to the representative business demo endpoint. Keep `business_demo` threshold at 500 ms and require endpoint-class matching.
- Boundary risk: API gateway evidence could be confused with M3.6a/b/c Chat evidence. Use separate `tools/api_gateway_perf/`, `scripts/validate_api_gateway_perf_plan.py`, and `reports/api-gateway-perf/`.
- Closure risk: static CI could be misread as a real 30-minute performance pass. CI validates structure only; real evidence must come later via operator PR.
- Scope risk: implementing production gateway runtime, service mesh, Prometheus histograms, or rate limiting here would exceed M3.6d. Keep this story to contract, evidence validation, CI, Locust entrypoint, and runbook.

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Split endpoint latency fields into `locust_p50_ms`, `locust_p95_ms`, `locust_p99_ms`, and `prometheus_histogram_quantile_p95_ms` so PRD's Locust + Prometheus evidence method is represented without ambiguity.
- Required real evidence threshold validation against both Locust P95 and Prometheus histogram P95.
- Added an explicit endpoint-class vocabulary lock for `algorithms_public`, `auth_api_keys`, and `business_demo` across plan, schema, example manifest, validator, tests, and runbook.

Status: PASS after fixes.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Clarified that missing `API_GATEWAY_PERF_JWT` must not break CI import/static validation and only fails when the authenticated endpoint class is selected or executed.
- Required request pacing to derive from the committed plan instead of hardcoded Locust sleeps, keeping implementation behavior tied to the evidence contract.
- Added real-evidence rejection for missing, duplicate, or extra endpoint classes so endpoint aggregation cannot silently drift.
- Added a timestamp-derived `duration_seconds` consistency check so a manifest cannot claim a 30-minute run while recording a shorter measurement window.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Explicitly forbade committing generated real `reports/api-gateway-perf/**` artifacts in this implementation, preventing fake pass evidence.
- Added forbidden secret/value and path boundary checks to the validator requirements for committed API gateway plan/example evidence.
- Added runbook failure follow-up requirements so a failed baseline creates an investigation record before retry.
- Added final completion bookkeeping requirements for Dev Agent Record, file list, validation evidence, post-implementation review fixes, and sprint status.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Implementation Notes

- Implemented M3.6d as an API gateway performance baseline contract, not as production API gateway runtime or fabricated evidence.
- Added a machine-checkable plan for 100 concurrent users, 30 minutes, three endpoint classes, endpoint-specific P95 thresholds, Grafana requirement, and Prometheus histogram P95 evidence.
- Added CI-importable Locust helpers and runtime-only JWT handling for `auth_api_keys`.
- Added evidence schema/example with separate Locust, Grafana, Prometheus, and latency summary artifacts under `reports/api-gateway-perf/<run_id>/`.
- Added a dedicated validator and tests for endpoint drift, threshold drift, real-evidence threshold checks, artifact paths, example-vs-real evidence, path-mode separation, and secret-like value rejection.
- Added an operator runbook covering staging setup, runtime credentials, Locust execution, evidence archive, redaction, pass/fail rules, and failure follow-up.

### File List

- `.github/workflows/ci.yml`
- `.pre-commit-config.yaml`
- `docs/runbooks/api-gateway-perf-baseline.md`
- `scripts/validate_api_gateway_perf_plan.py`
- `tests/test_api_gateway_perf_plan.py`
- `tools/api_gateway_perf/evidence_manifest.example.json`
- `tools/api_gateway_perf/evidence_manifest.schema.json`
- `tools/api_gateway_perf/locustfile.py`
- `tools/api_gateway_perf/perf_baseline_plan.json`
- `_bmad-output/stories/m3-6d-api-gateway-perf-baseline.md`
- `_bmad-output/stories/sprint-status.yaml`

### Validation Evidence

- `uv run pytest tests/test_api_gateway_perf_plan.py -q` — RED confirmed 14 expected failures before implementation.
- `uv run python scripts/validate_api_gateway_perf_plan.py` — PASS
- `uv run pytest tests/test_api_gateway_perf_plan.py -q` — PASS, 14 tests
- `uv run ruff check scripts/validate_api_gateway_perf_plan.py tests/test_api_gateway_perf_plan.py tools/api_gateway_perf/locustfile.py` — PASS
- `uv run ruff format --check scripts/validate_api_gateway_perf_plan.py tests/test_api_gateway_perf_plan.py tools/api_gateway_perf/locustfile.py` — PASS
- `uv run python scripts/validate_api_gateway_perf_plan.py` — PASS after code review fixes
- `uv run pytest tests/test_api_gateway_perf_plan.py -q` — PASS, 14 tests after code review fixes
- `uv run ruff check scripts/validate_api_gateway_perf_plan.py tests/test_api_gateway_perf_plan.py tools/api_gateway_perf/locustfile.py` — PASS after code review fixes
- `uv run ruff format --check scripts/validate_api_gateway_perf_plan.py tests/test_api_gateway_perf_plan.py tools/api_gateway_perf/locustfile.py` — PASS after code review fixes
- `uv run pre-commit run --all-files --show-diff-on-failure` — PASS
- `git diff --check` — PASS

## Senior Developer Review (AI)

Outcome: Changes requested; fixes applied.

Findings fixed:
- `tools/api_gateway_perf/locustfile.py` selected all endpoints at class import time, which would require `API_GATEWAY_PERF_JWT` before runtime and violate the no-credential static import boundary. Deferred endpoint selection to task execution and added a regression assertion that `ApiGatewayPerfUser` does not hold prebuilt endpoint specs.
- `.pre-commit-config.yaml` did not exclude the public M3.6d plan SHA-256 used by the example manifest, creating the same high-entropy false-positive risk previously seen in M3.6c. Added a narrow detect-secrets exclusion for that exact public hash.

### Change Log

- 2026-05-26: Initial draft created for M3.6d story context.
- 2026-05-26: Completed three pre-implementation story review rounds and moved story to ready-for-dev.
- 2026-05-26: Started implementation and moved story to in-progress.
- 2026-05-26: Added API gateway performance plan, Locust entrypoint, evidence schema/example, validator/tests, runbook, and CI wiring.
- 2026-05-26: Moved story to code-review after focused implementation validation passed.
- 2026-05-26: Completed post-implementation code review and applied Locust import-boundary and detect-secrets false-positive fixes.
- 2026-05-26: Final validation passed and story moved to done.
