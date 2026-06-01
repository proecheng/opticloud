---
story_key: 7-b-2-shadow-validation
baseline_commit: 3344539b661193adea945137c4cc5fdc78189838
epic_num: 7
story_num: B.2
epic_name: Provider Marketplace v2
status: done
priority: High
type: provider shadow validation contract and promotion gate
created_by: bmad-create-story
created_at: 2026-06-01
sources:
  - _bmad-output/planning/epics.md (Epic 7.B / Provider Marketplace v2)
  - _bmad-output/planning/prd.md (FR P2 / NFR Provider Integration 6.1)
  - _bmad-output/planning/architecture.md (Provider Routing & Shadow Validation, C17 capability-registry M5+ path)
  - _bmad-output/stories/7-b-1-provider-apply-v2.md
  - apps/capability-registry/src/capability_registry/models.py
  - apps/capability-registry/src/capability_registry/schemas.py
  - apps/capability-registry/src/capability_registry/routes.py
  - infra/local-init/14-capability-registry.sql
---

# Story 7.B.2 - Shadow Validation

Status: done

## Story

**As** a marketplace operator,
**I want** OptiCloud to record, summarize, and gate provider shadow validation runs before promotion,
**so that** a provider can only move toward later gradient rollout after meeting the PRD/NFR shadow validation thresholds.

## Context

Epic 7.B moves from provider application intake to marketplace readiness. Story 7.B.1 already created provider applications and evaluation intake requests in `apps/capability-registry`. PRD FR P2 requires shadow validation before promotion, and NFR Provider Integration 6.1 defines the gate: at least 14 days, at least 500 samples, four coverage classes, success rate at least 98%, average deviation at most 2%, and P95 latency at most 1.5x the platform baseline.

This story creates the shadow validation contract and deterministic gate calculation. It does not run real provider calls, enqueue workers, compare solver outputs, promote traffic, publish dashboards, or create live provider catalog rows. A later scheduled worker can feed sample rows into this API; this story owns the state model and pass/fail calculation that 7.B.3 gradient rollout must consume.

## Scope

1. Extend `infra/local-init/14-capability-registry.sql` with idempotent shadow validation run and sample tables.
2. Add SQLAlchemy models and Pydantic schemas in `apps/capability-registry`.
3. Add internal API routes:
   - `PUT /v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}/shadow-runs/{run_id}`
   - `GET /v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}/shadow-runs/{run_id}`
   - `GET /v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}/shadow-runs?tenant_id=&status=`
   - `PUT /v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}/shadow-runs/{run_id}/samples/{sample_id}`
   - `GET /v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}/shadow-runs/{run_id}/samples/{sample_id}`
   - `GET /v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}/shadow-runs/{run_id}/samples?tenant_id=&coverage_class=&passed=`
   - `POST /v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}/shadow-runs/{run_id}/finalize`
4. Add tests for schema idempotency, state transitions, threshold calculations, tenant/global scope, no side effects, OpenAPI drift, and existing 7.A/7.B.1 regressions.
5. Regenerate `packages/shared-ts/openapi/capability-registry.json`.

## Out Of Scope

- Running actual shadow traffic, calling provider containers, pulling Docker images, executing benchmarks, comparing solver outputs, or scheduling Dramatiq/Celery jobs.
- Gradient rollout, 5%/50%/100% routing, solver-orchestrator routing changes, route-share dashboard, KPI dashboard, revenue payout, version update lifecycle, or monthly revenue share.
- Creating, updating, or deleting `capability_providers`, `capabilities`, `provider_oauth_flows`, `revenue_share_policies`, or `revenue_share_hooks`.
- Storing raw request/response payloads, raw solver inputs, raw benchmark datasets, raw provider outputs, credentials, OAuth tokens, registry auth, bank/tax data, or user PII.
- Provider Console UX or public provider self-service flows.

## Acceptance Criteria

1. `infra/local-init/14-capability-registry.sql` idempotently creates `provider_shadow_validation_runs` and `provider_shadow_validation_samples`.
2. `provider_shadow_validation_runs` has columns: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `tenant_id UUID NULL`, `application_row_id UUID NOT NULL REFERENCES provider_applications(id) ON DELETE CASCADE`, `evaluation_row_id UUID NOT NULL REFERENCES provider_application_evaluation_requests(id) ON DELETE CASCADE`, `application_id VARCHAR(64) NOT NULL`, `evaluation_id VARCHAR(64) NOT NULL`, `run_id VARCHAR(64) NOT NULL`, `requested_provider_id VARCHAR(64) NOT NULL`, `benchmark_suite VARCHAR(64) NOT NULL`, `evaluation_sample_count INTEGER NOT NULL`, `baseline_provider_id VARCHAR(64) NOT NULL`, `status VARCHAR(32) NOT NULL DEFAULT 'draft'`, `started_at TIMESTAMPTZ NULL`, `ended_at TIMESTAMPTZ NULL`, `summary JSONB NOT NULL DEFAULT '{}'::jsonb`, `evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb`, `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`, `created_at`, and `updated_at`.
3. `provider_shadow_validation_samples` has columns: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `tenant_id UUID NULL`, `run_row_id UUID NOT NULL REFERENCES provider_shadow_validation_runs(id) ON DELETE CASCADE`, `sample_id VARCHAR(64) NOT NULL`, `coverage_class VARCHAR(32) NOT NULL`, `dataset_ref TEXT NOT NULL`, `case_ref TEXT NOT NULL`, `observed_at TIMESTAMPTZ NOT NULL`, `provider_status_code INTEGER NOT NULL`, `provider_latency_ms INTEGER NOT NULL`, `baseline_latency_ms INTEGER NOT NULL`, `deviation_ratio NUMERIC(9,6) NOT NULL`, `timed_out BOOLEAN NOT NULL DEFAULT false`, `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`, `created_at`, and `updated_at`.
4. `run_id`, `sample_id`, `application_id`, `evaluation_id`, `requested_provider_id`, and `baseline_provider_id` use the existing provider ID pattern `^[a-z0-9][a-z0-9-]{0,63}$`; `benchmark_suite` keeps the 7.B.1 pattern `^[a-z0-9][a-z0-9_-]{0,63}$`.
5. Allowed run statuses are `draft`, `running`, `passed`, `failed`, and `cancelled`. Run upsert may create `draft` or `running`, may transition `draft -> running`, and may transition `draft|running -> cancelled`. `passed` and `failed` can only be produced by finalize, not by run upsert.
6. Allowed sample coverage classes are exactly `platform_standard`, `provider_supplied`, `adversarial`, and `desensitized_real`.
7. Shadow runs require an existing submitted provider application and an existing non-cancelled evaluation request in the same tenant/effective scope. Missing application/evaluation returns 404; draft application or cancelled evaluation returns 422.
8. Run upsert stores `application_row_id`, `evaluation_row_id`, `requested_provider_id`, `benchmark_suite`, `application_id`, `evaluation_id`, and the effective evaluation `sample_count` from resolved 7.B.1 rows, not from request bodies. Because 7.B.1 caps evaluation `sample_count` at 500 and NFR P2 requires at least 500 samples, a run can pass only when its evaluation request has `sample_count=500`.
9. Path `application_id`, `evaluation_id`, `run_id`, and `sample_id` are authoritative; matching body fields may be omitted or must match. Mismatches return 422.
10. Nullable `tenant_id` uniqueness is correct: one global run per `(evaluation_row_id, run_id)`, one tenant run per `(tenant_id, evaluation_row_id, run_id)`, one global sample per `(run_row_id, sample_id)`, and one tenant sample per `(tenant_id, run_row_id, sample_id)`.
11. Run `evidence_refs` must be a list of non-empty reference strings with allowed prefixes `s3://`, `oss://`, `fixture://`, `benchmark://`, or `repro://`; it must not contain raw evidence bodies.
12. Sample `dataset_ref` and `case_ref` must be non-empty reference strings with the same allowed prefixes. Raw rows or embedded benchmark payloads are rejected.
13. Run/sample `metadata` must be JSON objects. Run `summary` is service-computed and response-only; run upsert request bodies must not accept a `summary` field. Request payloads must reject nested sensitive or raw-payload keys recursively, including `api_key`, `password`, `client_secret`, `access_token`, `refresh_token`, `registry_password`, `docker_password`, `bank_account`, `tax_id`, `email`, `phone`, `raw_dataset`, `raw_request`, `raw_response`, `provider_request`, and `provider_response`.
14. Sample validation requires `provider_status_code` between 100 and 599, positive `provider_latency_ms`, positive `baseline_latency_ms`, and `deviation_ratio` between 0 and 999.999999.
15. Sample pass/fail is derived by the service: pass means HTTP 2xx, `timed_out=false`, and `deviation_ratio <= 0.020000`. The request body must not accept a caller-provided `passed` field.
16. `PUT shadow-runs/{run_id}` is deterministic. Draft runs may be updated and may enter `running`; `running` runs may only preserve material fields, add evidence refs/metadata, or become `cancelled`; passed/failed/cancelled runs are immutable except idempotent re-upsert with identical material fields.
17. Material run fields include `baseline_provider_id`; changing it after the run leaves `draft` returns 422.
18. `PUT samples/{sample_id}` is deterministic. Samples may be created or updated only while the run is `running`; draft, passed, failed, or cancelled runs reject sample writes with 422. Sample `tenant_id` must equal the resolved run `tenant_id`; callers cannot write tenant-scoped samples under a global run or global samples under a tenant run.
19. Sample upsert does not allow cross-run leakage. Reads/lists are always scoped through the resolved application, evaluation request, and shadow run.
20. A shadow run may never contain more distinct samples than its resolved evaluation `sample_count`; attempts to create an additional distinct sample beyond that cap return 422. Updating an existing sample does not count as an additional sample.
21. `GET shadow-runs` supports filters by `tenant_id` and `status`, returns only runs for the resolved evaluation, and sorts deterministically by `run_id`.
22. `GET samples` supports filters by `tenant_id`, `coverage_class`, and derived `passed`, returns only samples for the resolved run, and sorts deterministically by `sample_id`.
23. `POST shadow-runs/{run_id}/finalize` can finalize only a running run. Draft/cancelled runs return 422; already passed/failed runs return their persisted summary idempotently.
24. Finalize computes, stores, and returns summary fields: `sample_count`, `evaluation_sample_count`, `observed_day_span`, `coverage_classes`, `coverage_class_counts`, `success_count`, `success_rate`, `average_deviation_ratio`, `provider_p95_latency_ms`, `baseline_p95_latency_ms`, `p95_latency_ratio`, `thresholds`, and `failed_reasons`.
25. Finalize passes only when all NFR P2 thresholds are met: evaluation sample count exactly 500, observed samples exactly 500, observed span at least 14 days, all four coverage classes present with at least one sample each, success rate at least 0.980000, average deviation ratio at most 0.020000, and P95 latency ratio at most 1.500000.
26. Finalize sets run status to `passed` when all thresholds pass and `failed` otherwise; it sets `ended_at` once and preserves it on idempotent finalize replays.
27. Threshold values are service-owned constants and exposed in responses/summary. Request bodies must not be able to lower threshold values.
28. Shadow validation does not create, update, or delete live provider/capability/OAuth/revenue-share records as a side effect.
29. All shadow write routes use the existing `X-Internal-Service-Auth` mechanism when `CAPABILITY_REGISTRY_INTERNAL_SECRET` is configured; empty dev secret remains usable for tests.
30. Tenant/global scope follows 7.B.1 behavior. A tenant-scoped run may be created against a global fallback application only when the resolved evaluation request row is tenant-scoped. A global evaluation row cannot be mutated through a tenant-scoped shadow run. Response `scope_source` documents `tenant`, `global`, or `global_fallback` consistently.
31. Existing 7.A provider/capability/OAuth/revenue-share tests and 7.B.1 application/evaluation tests continue to pass.
32. The new schemas and routes are included in `packages/shared-ts/openapi/capability-registry.json`; `scripts/check_openapi_drift.py` detects drift.
33. OpenAPI schemas for shadow validation do not expose unsafe fields such as credentials, raw request/response, raw dataset, bank/tax fields, or a caller-controlled sample `passed`.
34. `.github/workflows/ci.yml` keeps the existing `capability-registry-test` job; no new CI service job is added.
35. Local gates pass: `uv run pytest apps/capability-registry/tests/ -v`, `uv run mypy apps packages`, `uv run ruff check apps/capability-registry`, `uv run ruff format --check apps/capability-registry`, `uv run python scripts/generate_openapi.py`, `uv run python scripts/check_openapi_drift.py`, and `git diff --check`.
36. Implementation record includes post-implementation code review findings and fixes.
37. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done`.

## Tasks / Subtasks

- [x] T1: Add shadow validation data model (AC: 1-14, 27)
  - [x] Extend `infra/local-init/14-capability-registry.sql` idempotently.
  - [x] Add SQLAlchemy models for shadow runs and samples.
  - [x] Preserve existing application/evaluation intake tables.

- [x] T2: Add request/response schemas and validation (AC: 4-16, 24-27, 33)
  - [x] Add Pydantic schemas for run upsert, sample upsert, responses, and computed summary.
  - [x] Reuse existing ID/reference/sensitive-key validation patterns.
  - [x] Ensure pass/fail and threshold values are service-derived.

- [x] T3: Add API routes and gate calculation (AC: 7-30)
  - [x] Add run upsert/read/list/finalize routes under existing provider application evaluation routes.
  - [x] Add sample upsert/read/list routes under a shadow run.
  - [x] Implement deterministic scope resolution and no side effects.
  - [x] Implement finalize calculation for NFR P2 thresholds.

- [x] T4: Add tests and OpenAPI coverage (AC: 31-35)
  - [x] Extend capability-registry tests for schema idempotency, state transitions, pass/fail summary, tenant/global scope, side effects, and write auth.
  - [x] Add OpenAPI unsafe-field absence assertions.
  - [x] Regenerate checked-in OpenAPI and run drift check.

- [ ] T5: Review, gates, and GitHub sync (AC: 36-37)
  - [x] Run post-implementation code review and fix findings.
  - [x] Run local gates after fixes.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [x] Mark story and sprint status `done` only after merge/sync.

## Dev Notes

### Service Boundary

- Implement only in `apps/capability-registry`, `infra/local-init/14-capability-registry.sql`, the checked-in capability-registry OpenAPI, tests, and story/status files.
- Do not introduce a new service, queue worker, scheduler, Docker executor, provider runtime, or solver-orchestrator dependency.
- Treat capability-registry as the owner of P1-P3 marketplace state. 7.B.2 only creates the shadow validation gate that 7.B.3 can later read.

### Existing Patterns To Reuse

- Follow 7.B.1 provider application/evaluation route nesting and tenant/global fallback semantics.
- Reuse `_PATH_ID_PATTERN`, `_assert_path_id(...)`, `_require_write_auth(...)`, `_scope_source(...)`, `_validate_reference(...)`, and `_reject_forbidden_reference_fields(...)` patterns.
- Use partial unique indexes for nullable-tenant uniqueness. Do not use plain unique indexes that include nullable `tenant_id`.
- Use `Path(pattern=...)` and `Query(pattern=...)` for invalid IDs and filters so FastAPI returns 422 before DB constraints.
- Existing tests apply `infra/local-init/14-capability-registry.sql` twice. Extend that harness.

### Gate Calculation Guidance

- Service-owned constants:
  - `min_observed_days = 14`
  - `min_sample_count = 500`
  - `required_coverage_classes = ["platform_standard", "provider_supplied", "adversarial", "desensitized_real"]`
  - `min_samples_per_coverage_class = 1`
  - `min_success_rate = 0.980000`
  - `max_average_deviation_ratio = 0.020000`
  - `max_p95_latency_ratio = 1.500000`
- Success is per-sample and derived from status/deviation/timeout, not provided by clients.
- Average deviation is computed across all stored samples, including timeout/non-2xx samples, because each sample must carry a numeric reference deviation. Do not cherry-pick only passing samples.
- Use `observed_at` span from samples for the 14 day threshold. Do not trust `started_at`/`ended_at` alone.
- P95 latency is the nearest-rank percentile: sort latencies ascending and take `ceil(0.95 * n) - 1`. Compute provider and baseline P95 from the same sample set. If baseline P95 is zero or unavailable, fail closed.
- Finalize must fail closed if sample count is not exactly aligned with the 7.B.1 evaluation request budget. With the current 7.B.1 cap, a passing run requires exactly 500 distinct samples.
- Summary must include failed reasons so a later Console/dashboard story can display why a run failed without recomputing.

### Previous Story Intelligence

- 7.A.1 found path IDs must be constrained at the FastAPI route boundary.
- 7.A.2 and 7.B.1 found sensitive-key rejection must recurse through nested metadata/list structures and catch camelCase variants.
- 7.B.1 deliberately made evaluation requests intake-only; `queued` must still not enqueue work in this story.
- OpenAPI generation and drift scripts already include capability-registry.

### Suggested Commands

```powershell
uv sync --all-packages --extra dev
uv run pytest apps/capability-registry/tests/ -v
uv run mypy apps packages
uv run ruff check apps/capability-registry
uv run ruff format --check apps/capability-registry
uv run python scripts/generate_openapi.py
uv run python scripts/check_openapi_drift.py
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Shadow validation records and gate calculation satisfy FR P2/NFR Provider Integration 6.1 without implementing real workers or 7.B.3 rollout.
- Existing provider/capability/OAuth/revenue-share/application/evaluation behavior remains compatible.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/7-b-2-shadow-validation`.
- Baseline commit: `3344539b661193adea945137c4cc5fdc78189838`.
- Focused capability-registry tests: `uv run pytest apps/capability-registry/tests/ -v` -> 29 passed.
- Type gate: `uv run mypy apps packages` -> passed.
- Lint/format gates: `uv run ruff check apps/capability-registry` and `uv run ruff format --check apps/capability-registry` -> passed.
- OpenAPI gates: `uv run python scripts/generate_openapi.py` and `uv run python scripts/check_openapi_drift.py` -> passed.
- Whitespace gate: `git diff --check` -> passed.
- GitHub sync: PR #137 passed CI, squash-merged to `main` at `bfadbb1`, remote branch `codex/7-b-2-shadow-validation` was deleted, and local `main` synced with `origin/main`.

### Completion Notes List

- Added provider shadow validation run/sample storage, schemas, and nested API routes in capability-registry.
- Implemented submitted-application/non-cancelled-evaluation preconditions, tenant/evaluation scoping, run state transitions, sample cap enforcement, derived sample pass/fail, and finalize-only `passed|failed` outcomes.
- Implemented deterministic NFR P2 gate summary: 500-sample/evaluation alignment, 14-day observed span, four coverage classes, success rate, average deviation, nearest-rank P95 latency ratio, thresholds, and failed reasons.
- Preserved existing 7.A and 7.B.1 behavior and proved shadow validation has no live provider catalog side effects.
- Post-implementation review fixes applied: upsert OpenAPI no longer exposes `passed|failed`, finalized-run idempotency uses omitted status, and run row locking serializes sample cap/finalize state.
- PR #137 passed GitHub CI, merged to `main`, branch cleanup completed, local `main` synced, and this story is now marked done.

### File List

- `_bmad-output/stories/7-b-2-shadow-validation.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/capability-registry/src/capability_registry/models.py`
- `apps/capability-registry/src/capability_registry/routes.py`
- `apps/capability-registry/src/capability_registry/schemas.py`
- `apps/capability-registry/tests/test_api.py`
- `infra/local-init/14-capability-registry.sql`
- `packages/shared-ts/openapi/capability-registry.json`

## Change Log

- 2026-06-01 - Story created for Provider Shadow Validation contract and gate.
- 2026-06-01 - Pre-implementation review round 1 tightened state transitions, summary ownership, tenant/sample scope, and P95 calculation.
- 2026-06-01 - Pre-implementation review round 2 aligned shadow evidence with 7.B.1 evaluation sample budget and average-deviation semantics.
- 2026-06-01 - Pre-implementation review round 3 added persisted evaluation sample count, coverage counts, exact 500-sample pass rule, and explicit per-coverage threshold.
- 2026-06-01 - Implemented Provider Shadow Validation schema/API/tests/OpenAPI; post-implementation review fixes applied; story moved to code-review pending final local gates and GitHub sync.
- 2026-06-01 - PR #137 passed CI, merged to `main`, branch cleanup and local sync completed; story status moved to `done`.

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary, State, And Closure Review

Findings:

1. The initial story allowed `running` but did not define which endpoint could create or transition it, leaving sample-write preconditions ambiguous.
2. The initial sample scope rule did not explicitly prevent tenant samples from being attached to global runs or vice versa.
3. `summary` existed as a DB column but the story did not explicitly make it service-computed and response-only.
4. P95 latency calculation was under-specified, which could create local/CI drift or a later implementation mismatch.
5. Tenant/global fallback wording could be read as allowing a tenant shadow run over a global evaluation row, which would blur ownership of later rollout gates.

Revisions applied:

- Tightened allowed run transitions, including `draft -> running`, cancellation, and finalize-only `passed|failed`.
- Made `summary` response-only and service-computed.
- Added sample/run tenant equality requirements.
- Defined nearest-rank P95 calculation and fail-closed baseline handling.
- Clarified that tenant shadow runs require a tenant-scoped evaluation row, even when the application is global fallback.

### Round 2 - Drift And Data Consistency Review

Findings:

1. The story did not reconcile 7.B.1 evaluation `sample_count` with the NFR P2 `>=500` gate. Because 7.B.1 caps evaluations at 500, an implementation could pass a run that exceeded the original evaluation budget or pass an under-budget evaluation.
2. The first draft did not explicitly forbid adding more shadow samples than the resolved evaluation request budget, which would let shadow evidence drift away from the reviewed intake.
3. Average deviation could be miscomputed over passing samples only, which would hide failures from the NFR average-deviation gate.
4. The summary lacked `evaluation_sample_count`, making it hard for later rollout code to prove the pass was tied to the original evaluation contract.

Revisions applied:

- Required run responses/finalize summaries to include `evaluation_sample_count`.
- Required passing runs to have evaluation `sample_count=500` and at least 500 observed samples.
- Added a hard cap preventing distinct shadow samples from exceeding the resolved evaluation request budget.
- Clarified average deviation must include all stored samples, not only passing samples.

### Round 3 - Dependency, Implementability, And Testability Review

Findings:

1. The AC required `evaluation_sample_count` in responses and summaries, but the run table did not persist it. Relying on a live join forever would make historical gate evidence vulnerable to future evaluation row changes.
2. The coverage threshold only required all classes to be present and did not ask for `coverage_class_counts`, making the summary less auditable.
3. The pass rule said observed samples "at least 500" while the sample cap prevented more than the evaluation budget. This was logically equivalent but less precise and easier to misimplement.
4. The service-owned constants did not include a minimum per coverage class, leaving the "all four coverage classes present" requirement implicit.

Revisions applied:

- Added `evaluation_sample_count INTEGER NOT NULL` to the run table.
- Added `coverage_class_counts` to the computed summary.
- Changed passing sample count to exactly 500 for the current 7.B.1 budget.
- Added `min_samples_per_coverage_class = 1` as an explicit threshold constant.

## Post-Implementation Code Review

### Findings

- [x] [Review][Patch] `ProviderShadowRunUpsertRequest.status` originally exposed `passed` and `failed` in OpenAPI even though routes rejected forged pass/fail outcomes. This could mislead clients and weaken the finalize-only contract. Fixed by making request status optional and limiting request enum to `draft|running|cancelled`; finalized-run idempotent upsert now omits status.
- [x] [Review][Patch] Shadow sample writes, run cancellation, and finalize did not serialize on the run row. Concurrent sample creation could race the evaluation `sample_count` cap or finalize an unstable sample set. Fixed by locking the shadow run row with `FOR UPDATE` before mutable sample/run/finalize operations and adding a cap recheck regression.

### Outcome

Changes requested during review were patched. Focused tests, local gates, GitHub CI, merge, branch cleanup, and local sync are complete.
