---
story_key: 7-b-3-gradient-rollout
baseline_commit: 3b12eab2917fe0ebda924ab906d8fbc1063d6fc9
epic_num: 7
story_num: B.3
epic_name: Provider Marketplace v2
status: done
priority: High
type: provider gradient rollout contract and staged promotion gate
created_by: bmad-create-story
created_at: 2026-06-01
sources:
  - _bmad-output/planning/epics.md (Epic 7.B / Provider Marketplace v2)
  - _bmad-output/planning/prd.md (FR P3 / NFR Provider Integration 6.1)
  - _bmad-output/planning/architecture.md (Provider Routing & Shadow Validation, C17 capability-registry M5+ path)
  - _bmad-output/stories/7-b-1-provider-apply-v2.md
  - _bmad-output/stories/7-b-2-shadow-validation.md
  - apps/capability-registry/src/capability_registry/models.py
  - apps/capability-registry/src/capability_registry/schemas.py
  - apps/capability-registry/src/capability_registry/routes.py
  - infra/local-init/14-capability-registry.sql
---

# Story 7.B.3 - Gradient Rollout

Status: done

## Story

**As** a marketplace operator,
**I want** OptiCloud to record and gate provider rollout stages from 5% to 50% to 100% after shadow validation passes,
**so that** later routing services can consume an auditable promotion decision without bypassing the shadow gate.

## Context

Epic 7.B moves provider applications from intake to marketplace readiness. Story 7.B.1 created provider application and evaluation request intake records. Story 7.B.2 created shadow validation runs, samples, and deterministic pass/fail summaries that enforce the NFR Provider Integration thresholds: 14 days, 500 samples, all four coverage classes, success rate at least 98%, average deviation at most 2%, and P95 latency ratio at most 1.5.

FR P3 requires gradual promotion of provider traffic from 5% to 50% to 100%. This story creates the rollout contract and staged promotion state inside `apps/capability-registry`. It must consume a `passed` shadow run and expose a deterministic, auditable rollout state for later solver-orchestrator routing work. It must not send real traffic, mutate solver routing, create runtime feature flags, publish dashboards, calculate route share, or compute revenue.

## Scope

1. Extend `infra/local-init/14-capability-registry.sql` with idempotent provider gradient rollout storage.
2. Add SQLAlchemy model(s) and Pydantic schemas for rollout records and stage advancement.
3. Add internal API routes:
   - `PUT /v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}/shadow-runs/{run_id}/rollouts/{rollout_id}`
   - `GET /v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}/shadow-runs/{run_id}/rollouts/{rollout_id}`
   - `GET /v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}/shadow-runs/{run_id}/rollouts?tenant_id=&status=&stage_percent=`
   - `POST /v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}/shadow-runs/{run_id}/rollouts/{rollout_id}/advance`
   - `POST /v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}/shadow-runs/{run_id}/rollouts/{rollout_id}/pause`
   - `POST /v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}/shadow-runs/{run_id}/rollouts/{rollout_id}/cancel`
4. Add tests for schema idempotency, passed-shadow prerequisite, staged 5/50/100 advancement, rollback-safe pause/cancel behavior, tenant/global scope, no side effects, OpenAPI drift, and existing 7.A/7.B.1/7.B.2 regressions.
5. Regenerate `packages/shared-ts/openapi/capability-registry.json`.

## Out Of Scope

- Actual traffic routing, weighted load balancing, route table mutation, feature flag backend integration, solver-orchestrator changes, or API gateway changes.
- Route-share dashboard, provider KPI dashboard, provider revenue payout, monthly revenue-share calculation, or provider version lifecycle.
- Creating, updating, or deleting live `capability_providers`, `capabilities`, `provider_oauth_flows`, `revenue_share_policies`, or `revenue_share_hooks`.
- Running provider calls, shadow workers, Docker image execution, benchmark comparison, or queue scheduling.
- Storing raw request/response payloads, raw benchmark datasets, raw provider outputs, credentials, OAuth tokens, registry auth, bank/tax data, user PII, or customer routing payloads.
- Public Provider Console UX or public provider self-service flows.

## Acceptance Criteria

1. `infra/local-init/14-capability-registry.sql` idempotently creates `provider_gradient_rollouts`.
2. `provider_gradient_rollouts` has columns: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `tenant_id UUID NULL`, `application_row_id UUID NOT NULL REFERENCES provider_applications(id) ON DELETE CASCADE`, `evaluation_row_id UUID NOT NULL REFERENCES provider_application_evaluation_requests(id) ON DELETE CASCADE`, `shadow_run_row_id UUID NOT NULL REFERENCES provider_shadow_validation_runs(id) ON DELETE CASCADE`, `application_id VARCHAR(64) NOT NULL`, `evaluation_id VARCHAR(64) NOT NULL`, `run_id VARCHAR(64) NOT NULL`, `rollout_id VARCHAR(64) NOT NULL`, `requested_provider_id VARCHAR(64) NOT NULL`, `baseline_provider_id VARCHAR(64) NOT NULL`, `benchmark_suite VARCHAR(64) NOT NULL`, `status VARCHAR(32) NOT NULL DEFAULT 'draft'`, `current_stage_percent INTEGER NOT NULL DEFAULT 0`, `stage_history JSONB NOT NULL DEFAULT '[]'::jsonb`, `shadow_summary_snapshot JSONB NOT NULL`, `started_at TIMESTAMPTZ NULL`, `completed_at TIMESTAMPTZ NULL`, `paused_at TIMESTAMPTZ NULL`, `cancelled_at TIMESTAMPTZ NULL`, `evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb`, `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`, `created_at`, and `updated_at`.
3. `rollout_id`, `application_id`, `evaluation_id`, `run_id`, `requested_provider_id`, and `baseline_provider_id` use the existing provider ID pattern `^[a-z0-9][a-z0-9-]{0,63}$`; `benchmark_suite` keeps the 7.B.1 pattern `^[a-z0-9][a-z0-9_-]{0,63}$`.
4. Allowed rollout statuses are exactly `draft`, `active`, `paused`, `completed`, and `cancelled`.
5. Allowed stage percentages are exactly `0`, `5`, `50`, and `100`; no request can create or advance to arbitrary weights such as `1`, `10`, `25`, or `75`.
6. Rollout upsert requires an existing submitted provider application, non-cancelled evaluation request, and existing shadow run in the same effective scope. Missing rows return 404; draft application or cancelled evaluation returns 422.
7. Rollout upsert requires the resolved shadow run status to be `passed`. Draft, running, failed, or cancelled shadow runs return 422. This check uses the persisted shadow run status and stored summary; clients cannot pass by supplying a body field.
8. Rollout upsert stores `application_row_id`, `evaluation_row_id`, `shadow_run_row_id`, `requested_provider_id`, `baseline_provider_id`, `benchmark_suite`, `application_id`, `evaluation_id`, `run_id`, and `shadow_summary_snapshot` from resolved rows, not from request bodies.
9. `shadow_summary_snapshot` is copied from the passed shadow run at rollout creation and is immutable. Later shadow summary changes must not silently rewrite historical rollout evidence.
10. Path `application_id`, `evaluation_id`, `run_id`, and `rollout_id` are authoritative; matching body fields may be omitted or must match. Mismatches return 422.
11. Nullable `tenant_id` uniqueness is correct: one global rollout per `(shadow_run_row_id, rollout_id)` and one tenant rollout per `(tenant_id, shadow_run_row_id, rollout_id)`.
12. Run/sample/rollout tenant scope is consistent. A tenant rollout can be created only against a tenant-scoped shadow run. A global shadow run cannot be mutated through a tenant-scoped rollout. Response `scope_source` documents `tenant`, `global`, or `global_fallback` consistently with 7.B.1/7.B.2 behavior.
13. Rollout `evidence_refs` must be a list of non-empty reference strings with allowed prefixes `s3://`, `oss://`, `fixture://`, `benchmark://`, or `repro://`; it must not contain raw evidence bodies.
14. Rollout `metadata` must be a JSON object and request payloads must reject nested sensitive or raw-payload keys recursively, including `api_key`, `password`, `client_secret`, `access_token`, `refresh_token`, `registry_password`, `docker_password`, `bank_account`, `tax_id`, `email`, `phone`, `raw_dataset`, `raw_request`, `raw_response`, `provider_request`, `provider_response`, `routing_payload`, and `customer_payload`.
15. Upsert creates a rollout in `draft` with `current_stage_percent=0`. Existing `draft` rollouts may update `evidence_refs` and `metadata` only. The upsert endpoint must not activate or advance stages.
16. `POST .../advance` is the only operation that changes rollout stage. It accepts an optional `target_stage_percent` that must equal the next allowed stage; if omitted, the service advances to the next stage automatically.
17. Stage progression is strictly `0 -> 5 -> 50 -> 100`. Skipping from `0` to `50`, `5` to `100`, or reversing to a lower stage returns 422.
18. First advance from `0` to `5` sets status to `active` and sets `started_at` once. Advancing to `50` keeps status `active`. Advancing to `100` sets status to `completed` and sets `completed_at` once.
19. `stage_history` is service-owned and append-only. Each successful advance appends an object containing at least `stage_percent`, `changed_at`, `from_status`, `to_status`, and `reason_ref`.
20. Advance requests require `reason_ref` as a non-empty allowed reference string. Optional advance `metadata` must pass the same sensitive/raw-payload rejection as rollout metadata.
21. `POST .../pause` may pause only an `active` rollout at stage `5` or `50`; it sets status `paused`, `paused_at` once, and appends a service-owned history entry. Pausing draft, completed, cancelled, or stage 100 rollouts returns 422.
22. A paused rollout may only be resumed by `advance` to the next allowed stage. Resuming from stage `5` to `50` or stage `50` to `100` sets status to `active` or `completed` as appropriate and preserves the original `started_at`.
23. `POST .../cancel` may cancel `draft`, `active`, or `paused` rollouts; it sets status `cancelled`, `cancelled_at` once, and appends a service-owned history entry. Completed rollouts cannot be cancelled.
24. Completed and cancelled rollouts are immutable except idempotent replays of the same terminal action returning the persisted response without changing timestamps/history.
25. `GET rollouts` supports filters by `tenant_id`, `status`, and `stage_percent`, returns only rollouts for the resolved shadow run, and sorts deterministically by `rollout_id`.
26. All rollout write routes use the existing `X-Internal-Service-Auth` mechanism when `CAPABILITY_REGISTRY_INTERNAL_SECRET` is configured; empty dev secret remains usable for tests.
27. Gradient rollout does not create, update, or delete live provider/capability/OAuth/revenue-share records and does not update shadow validation rows as a side effect.
28. Existing 7.A provider/capability/OAuth/revenue-share tests, 7.B.1 application/evaluation tests, and 7.B.2 shadow validation tests continue to pass.
29. The new schemas and routes are included in `packages/shared-ts/openapi/capability-registry.json`; `scripts/check_openapi_drift.py` detects drift.
30. OpenAPI schemas for gradient rollout do not expose unsafe fields such as credentials, raw request/response, raw dataset, customer routing payloads, bank/tax fields, or caller-controlled `stage_history` / `shadow_summary_snapshot`.
31. `.github/workflows/ci.yml` keeps the existing `capability-registry-test` job; no new CI service job is added.
32. Local gates pass: `uv run pytest apps/capability-registry/tests/ -v`, `uv run mypy apps packages`, `uv run ruff check apps/capability-registry`, `uv run ruff format --check apps/capability-registry`, `uv run python scripts/generate_openapi.py`, `uv run python scripts/check_openapi_drift.py`, and `git diff --check`.
33. Implementation record includes post-implementation code review findings and fixes.
34. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done`.

## Tasks / Subtasks

- [x] T1: Add gradient rollout data model (AC: 1-14)
  - [x] Extend `infra/local-init/14-capability-registry.sql` idempotently.
  - [x] Add SQLAlchemy model for provider gradient rollouts.
  - [x] Preserve existing application/evaluation/shadow validation tables and behavior.

- [x] T2: Add request/response schemas and validation (AC: 3-5, 10, 13-20, 30)
  - [x] Add Pydantic schemas for rollout upsert, rollout response, and rollout action request.
  - [x] Reuse existing ID/reference/sensitive-key validation patterns.
  - [x] Ensure stage history and shadow summary snapshot are service-derived.

- [x] T3: Add rollout API routes and state machine (AC: 6-27)
  - [x] Add rollout upsert/read/list routes under existing shadow run routes.
  - [x] Add advance/pause/cancel action routes.
  - [x] Implement passed-shadow prerequisite, tenant/effective-scope resolution, and append-only stage history.
  - [x] Lock rollout rows before mutable state transitions.

- [x] T4: Add tests and OpenAPI coverage (AC: 28-32)
  - [x] Extend capability-registry tests for schema idempotency, passed-shadow prerequisite, stage progression, pause/cancel semantics, tenant/global scope, no side effects, and write auth.
  - [x] Add OpenAPI unsafe-field absence assertions.
  - [x] Regenerate checked-in OpenAPI and run drift check.

- [x] T5: Review, gates, and GitHub sync (AC: 33-34)
  - [x] Run post-implementation code review and fix findings.
  - [x] Run local gates after fixes.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [x] Mark story and sprint status `done` only after merge/sync.

## Dev Notes

### Service Boundary

- Implement only in `apps/capability-registry`, `infra/local-init/14-capability-registry.sql`, checked-in capability-registry OpenAPI, tests, and story/status files.
- Do not introduce a new service, queue worker, scheduler, feature flag backend, solver-orchestrator dependency, API gateway dependency, or provider runtime.
- Treat capability-registry as the owner of P1-P3 marketplace state. 7.B.3 creates the staged rollout decision record that a later routing story can consume.

### Existing Patterns To Reuse

- Follow 7.B.2 route nesting under provider application → evaluation request → shadow run.
- Reuse `_PATH_ID_PATTERN`, `_assert_path_id(...)`, `_require_write_auth(...)`, `_scope_source(...)`, `_validate_reference(...)`, and `_reject_forbidden_reference_fields(...)`.
- Use partial unique indexes for nullable-tenant uniqueness. Do not use plain unique indexes that include nullable `tenant_id`.
- Use `Path(pattern=...)` and `Query(pattern=...)` for invalid IDs and filters so FastAPI returns 422 before DB constraints.
- Existing tests apply `infra/local-init/14-capability-registry.sql` twice. Extend that harness.

### Gate And State Machine Guidance

- The rollout gate is a passed `ProviderShadowValidationRun`; do not recompute shadow thresholds in this story.
- Copy the shadow summary into `shadow_summary_snapshot` at creation to preserve historical evidence.
- Service-owned stage sequence: `[0, 5, 50, 100]`.
- Terminal statuses: `completed`, `cancelled`.
- Mutable statuses: `draft`, `active`, `paused`.
- Do not allow upsert to activate rollout; activation is only via `advance`.
- Use row locking for action routes so concurrent advances cannot duplicate or skip stage history.

### Previous Story Intelligence

- 7.A.1 found path IDs must be constrained at the FastAPI route boundary.
- 7.A.2, 7.B.1, and 7.B.2 found sensitive-key rejection must recurse through nested metadata/list structures and catch camelCase variants.
- 7.B.1 deliberately made evaluation requests intake-only.
- 7.B.2 deliberately made shadow validation evidence contract-only and does not run real traffic.
- 7.B.2 post-review fixed concurrency by locking shadow run rows before sample/finalize mutations; apply the same discipline to rollout action routes.
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
- Gradient rollout records and state transitions satisfy FR P3/NFR Provider Integration without implementing real routing.
- Existing provider/capability/OAuth/revenue-share/application/evaluation/shadow validation behavior remains compatible.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/7-b-3-gradient-rollout`.
- Baseline commit: `3b12eab2917fe0ebda924ab906d8fbc1063d6fc9`.
- Focused capability-registry tests: `uv run pytest apps/capability-registry/tests/ -v` -> 33 passed.
- Type gate: `uv run mypy apps packages` -> passed.
- Lint/format gates: `uv run ruff check apps/capability-registry` and `uv run ruff format --check apps/capability-registry` -> passed.
- OpenAPI gates: `uv run python scripts/generate_openapi.py` and `uv run python scripts/check_openapi_drift.py` -> passed.
- Whitespace gate: `git diff --check` -> passed.
- Post-review gates repeated after patch: capability-registry tests 33 passed; mypy, ruff, format, OpenAPI generation/drift, and diff-check passed.

### Completion Notes List

- Story created for Provider Gradient Rollout contract and staged promotion gate.
- Added provider gradient rollout storage, schema, routes, OpenAPI, and regression tests in capability-registry.
- Implemented passed-shadow prerequisite with immutable shadow summary snapshots.
- Implemented strict `0 -> 5 -> 50 -> 100` stage advancement, pause/cancel actions, terminal idempotency, row locking, tenant scope, write auth, and no live catalog/routing side effects.
- Post-implementation review fix applied: rollout creation now validates a clean passed shadow summary and snapshots the normalized summary.
- Local implementation gates passed; GitHub CI passed; PR #138 merged to `main`; remote branch deleted; local `main` synced to merge commit `7d990ba22ff00185136c9e067d797fbce510c47c`.

### File List

- `_bmad-output/stories/7-b-3-gradient-rollout.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/capability-registry/src/capability_registry/models.py`
- `apps/capability-registry/src/capability_registry/routes.py`
- `apps/capability-registry/src/capability_registry/schemas.py`
- `apps/capability-registry/tests/test_api.py`
- `infra/local-init/14-capability-registry.sql`
- `packages/shared-ts/openapi/capability-registry.json`

## Change Log

- 2026-06-01 - Story created for Provider Gradient Rollout contract and staged promotion gate.
- 2026-06-01 - Implemented Provider Gradient Rollout schema/API/tests/OpenAPI; story moved to review pending post-implementation code review.
- 2026-06-01 - Post-implementation code review found shadow-summary drift risk; fix applied and local gates passed.
- 2026-06-01 - PR #138 passed CI, merged to main, remote branch deleted, local main synced, and story marked done.

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary, State, And Closure Review

Findings:

1. Initial scope could be mistaken for real traffic routing because FR P3 says "traffic"; the story must state the output is an auditable contract only.
2. Upsert and advance were initially easy to conflate, which could let a caller create an already-active rollout and bypass explicit stage-history evidence.
3. The passed shadow run dependency needed to be tied to persisted status and summary, not caller-provided proof.
4. Stage percentages needed a closed enum to prevent hidden partial rollout stages.

Revisions applied:

- Out-of-scope and service boundary now explicitly forbid solver routing, feature flags, API gateway changes, and actual traffic mutation.
- Upsert is constrained to `draft` only; `advance` is the only operation that changes stages.
- ACs require resolved persisted shadow run status `passed` and immutable `shadow_summary_snapshot`.
- Stage percentages are closed to `0`, `5`, `50`, and `100`.

### Round 2 - Drift And Data Consistency Review

Findings:

1. Rollout evidence could drift if it always joined to the mutable shadow summary instead of snapshotting at rollout creation.
2. Tenant/global scope needed to be consistent with 7.B.2, especially preventing tenant rollout creation over global shadow runs.
3. `stage_history` could become caller-controlled unless the request schemas explicitly reject it.
4. List filters needed deterministic sorting and scoping so later dashboards do not infer route share from mixed-scope rows.

Revisions applied:

- Added immutable `shadow_summary_snapshot` copied from the resolved passed shadow run.
- Added tenant/scope ACs requiring tenant rollout only against tenant shadow run and global rollout only against global shadow run.
- Added OpenAPI/schema ACs forbidding caller-controlled `stage_history` and `shadow_summary_snapshot`.
- Added list filtering and deterministic sorting requirements.

### Round 3 - Dependency, Implementability, And Testability Review

Findings:

1. Pause/resume behavior was under-specified and could create a dead-end paused state.
2. Terminal action idempotency was needed for retry-safe internal clients.
3. Concurrent advance calls could duplicate stage history or skip stages without row locking.
4. The sensitive-key list did not include routing/customer payload terms specific to rollout.

Revisions applied:

- Paused rollout resumes via `advance` to the next stage, preserving `started_at`.
- Terminal completed/cancelled action replay is idempotent and must preserve timestamps/history.
- Action routes must lock rollout rows before state transitions.
- Rollout metadata rejection includes `routing_payload` and `customer_payload`.

## Post-Implementation Code Review

### Findings

- [x] [Review][Patch] Rollout creation trusted `run.status == "passed"` and non-empty `run.summary`, but did not validate that the stored summary itself had no `failed_reasons`. Normal application flow keeps these consistent, but DB/manual drift could create a rollout from contradictory evidence. Fixed by validating `ProviderShadowRunSummary` and requiring an empty `failed_reasons` list before rollout creation; the stored snapshot now uses the normalized summary dump.

### Outcome

Changes requested during review were patched. Focused tests and all local gates pass after the patch.
