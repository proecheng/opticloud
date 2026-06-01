---
story_key: 5-d-4-job-templates-version
baseline_commit: 1be4c79629145cf5a130112b4f24ea24f9620ee5
epic_num: 5
story_num: D.4
epic_name: Billing - Invoices + Templates + Budget + Notifications
status: done
priority: High
type: solver job template reuse and version history
created_by: bmad-create-story
created_at: 2026-06-01
sources:
  - _bmad-output/planning/epics.md (Epic 5.D / Story 5.D.4 / FR B11)
  - _bmad-output/planning/prd.md (FR B11 v1 required, simplified profile can cut)
  - _bmad-output/planning/architecture.md (solver-orchestrator execution owner; billing-service billing owner; Next.js Console)
  - _bmad-output/stories/5-d-3-job-templates-save.md
  - infra/local-init/02-solver-schema.sql
  - apps/solver-orchestrator/src/solver_orchestrator/job_templates.py
  - apps/solver-orchestrator/src/solver_orchestrator/models.py
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py
  - apps/solver-orchestrator/src/solver_orchestrator/schemas.py
  - apps/solver-orchestrator/tests/test_job_templates.py
  - apps/web/src/lib/api.ts
  - apps/web/src/lib/job-templates.test.ts
  - apps/web/src/app/console/predictions/page.tsx
  - apps/web/src/app/console/predictions/page.test.tsx
---

# Story 5.D.4 - Job templates reuse + version

Status: done

## Story

**As** an authenticated OptiCloud execution user,
**I want** to reuse a saved job template by changing one request parameter and saving that changed request as a new version,
**so that** I can keep a durable, owner-scoped version history of template-based work without rebuilding requests from scratch.

## Context

Story 5.D.3 shipped the save foundation: `job_templates` rows persist owner-scoped sanitized request payloads with `version=1`, `root_template_id=id`, and `parent_template_id=null`. Story 5.D.4 completes the FR B11 version/reuse slice by adding controlled parameter edits, new version creation, and version history lookup.

This story deliberately keeps execution ownership in `solver-orchestrator`. Template versions store execution request payloads, not billing records. For the frontend vertical slice, the prediction Console may create a new prediction from a newly created prediction template version by calling the existing prediction submission API with the returned version payload. The template-version endpoint itself must not create executions, idempotency rows, billing charges, vouchers, outbox rows, or ledger entries.

## Scope

1. Upgrade `job_templates` local schema and ORM metadata so version chains can have multiple active rows for the same original source/name while preserving duplicate initial-save replay semantics from 5.D.3.
2. Add a version creation endpoint that takes exactly one allowed parameter path plus a value, merges it into the parent template payload, validates the full resulting request, and persists the next version in the same root lineage.
3. Add a version history endpoint that returns the caller's non-deleted versions for the selected template lineage in version order.
4. Keep all template version routes API-key authenticated with `optimize:write`, owner-scoped, and free of client-provided `user_id`.
5. Add typed web API helpers for version create/list.
6. Extend the prediction Console save-template success state with a small reuse flow: change prediction `horizon`, create a new template version, submit a new prediction using that returned version payload, and display version history/result without hiding the original prediction.
7. Add focused backend and web tests, then run post-implementation code review, fix findings, pass gates, and sync GitHub.

## Out Of Scope

- A full standalone template management product surface.
- Executing optimization templates from the frontend or charging optimization reuse in this story.
- Multi-parameter edits in one version request.
- Arbitrary raw `payload_json` replacement from clients.
- Editing template `user_id`, `source_kind`, `source_id`, `task_type`, `payload_schema_version`, `payload_sha256`, `version`, `root_template_id`, `parent_template_id`, `created_at`, `updated_at`, or `deleted_at` from clients.
- Branch comparison, diff visualization, revert/restore, hard delete, undelete, rename chains, or bulk operations.
- Billing, budget alerts, notification preferences, invoices, credits, ledger mutations, vouchers, or outbox events.
- Storing API keys, JWTs, billing charge IDs, result payloads, solver solutions, forecast outputs, raw file bytes, emails, phones, or raw `_system` metadata inside template version payloads.

## Acceptance Criteria

1. Local schema is idempotently upgraded for version chains:
   - the 5.D.3 unique index on active `(user_id, source_kind, source_id, name)` is replaced with a root-only duplicate-save index applying only to active root templates (`parent_template_id IS NULL`);
   - the DB enforces at most one active row per `(user_id, root_template_id, version)`;
   - existing 5.D.3 `version=1` rows remain valid.
2. SQLAlchemy model/index metadata matches the upgraded local init schema.
3. Existing `POST /v1/job-templates` duplicate initial-save behavior is preserved: same owner/source/name returns the active root version with HTTP 200 and does not create a second root.
4. New route `POST /v1/job-templates/{template_id}/versions` requires `Authorization: Bearer sk-...` with `optimize:write`.
5. Version create request accepts only `parameter_path`, `value`, and optional `description`; it forbids arbitrary `payload_json`, lineage fields, source fields, schema fields, timestamps, and `user_id`.
6. `parameter_path` must be exactly one allowed whole-field path. Supported prediction paths are `family`, `data`, and `horizon`. Supported optimization paths are `solver`, `fallback_chain`, `minimize.c`, `maximize.c`, `st.A`, `st.b`, `st.x_lower`, `st.x_upper`, and `options.max_solve_seconds`, `options.top_k_alternatives`, `options.reproducible`, `options.anonymous`, `options.backtest`.
7. Path edits are applied to a deep copy of the parent template payload. The implementation must not mutate the loaded parent payload in memory.
8. `_system`, result fields, solver outputs, forecast outputs, billing metadata, idempotency keys, API keys, JWTs, emails, phones, and raw file bytes are never accepted as editable paths and never appear in saved version payloads.
9. Prediction version payloads are revalidated with the same public prediction constraints used for execution: supported family, numeric finite data length 3-10000, and horizon 1-90.
10. Optimization version payloads are revalidated with the public `OptimizationRequest` schema and the existing provider/fallback support checks. Version creation must not call solvers or billing.
11. A successful version create persists a new `job_templates` row with:
    - new UUID `id`;
    - same `user_id`, `name`, `source_kind`, `source_id`, `task_type`, and `payload_schema_version` as the parent lineage;
    - `version = max(existing lineage version) + 1`, not reusing deleted version numbers;
    - `root_template_id` equal to the root template id;
    - `parent_template_id` equal to the requested parent `template_id`;
    - sanitized `payload_json`;
    - deterministic `payload_sha256` over the same canonical envelope contract from 5.D.3;
    - fresh `created_at` and `updated_at`, `deleted_at=null`.
12. Concurrent version creation for the same lineage cannot create duplicate active version numbers; conflicts retry or deterministically return a valid newly created version.
13. Creating a version from a missing, cross-user, or deleted template returns 404 without leaking existence.
14. Invalid parameter path, invalid value, malformed resulting request, or unsupported solver/fallback returns RFC 7807 422/400 with field-specific errors and no template row created.
15. New route `GET /v1/job-templates/{template_id}/versions` requires API-key auth, is owner-scoped, and returns the caller's non-deleted versions in the selected template's lineage ordered by `version ASC`.
16. Version history response includes compact metadata and `payload_sha256`; it does not need to include full `payload_json` for every row. The create response includes the new version's full sanitized `payload_json`.
17. Existing `GET /v1/job-templates/{template_id}` can read any non-deleted version by id and includes its sanitized payload.
18. Existing `DELETE /v1/job-templates/{template_id}` soft-deletes only that selected version, updates `deleted_at` and `updated_at`, and does not hard-delete or renumber history.
19. Template version routes do not create optimization/prediction executions, idempotency rows, billing charges, vouchers, outbox rows, or ledger rows.
20. Web API helpers in `apps/web/src/lib/api.ts` expose typed create-version/list-versions helpers against `SOLVER_SERVICE_URL` with API-key bearer auth and existing RFC 7807 error handling.
21. Prediction Console, after saving a completed prediction as a template, can change `horizon`, create a new prediction template version, submit the returned prediction payload with the existing prediction API, and show the new prediction result plus version metadata/history.
22. Prediction Console reuse/version flow does not store API keys, template payloads, source data, or prediction results in `sessionStorage`/`localStorage`.
23. Prediction Console reuse/version errors do not hide the original prediction result and do not re-submit the original prediction unless the user explicitly triggers the reuse action.
24. Tests cover schema/index contract, root duplicate replay after schema upgrade, version creation for prediction and optimization, owner scoping, deleted/missing templates, invalid paths/values, full payload validation, deterministic hash, no side effects outside `job_templates` for version creation, version history ordering, web helper URL/auth/error behavior, Console version create + prediction reuse success/error states, and storage hygiene.
25. Quality gates pass:
    - focused solver job template tests;
    - relevant solver regression for prediction/optimization submission/status routes;
    - ruff/format/mypy for touched Python files;
    - focused web API/page tests;
    - web test/typecheck for touched frontend files;
    - `git diff --check`;
    - GitHub CI.

## Tasks / Subtasks

- [x] T1: Upgrade template lineage persistence (AC: 1-3, 11-12, 18)
  - [x] Update `infra/local-init/02-solver-schema.sql` to drop/replace the 5.D.3 active source/name unique index with a root-only duplicate-save index.
  - [x] Add an active `(user_id, root_template_id, version)` unique index and lineage/version lookup index.
  - [x] Align `JobTemplate.__table_args__` with the upgraded indexes.
  - [x] Update root duplicate lookup/insert logic in `routes.py` so initial duplicate saves still return the active root version.

- [x] T2: Add version payload merge/validation helpers and schemas (AC: 5-12, 14, 16)
  - [x] Add Pydantic request/response models for version create/history in `schemas.py`.
  - [x] Add pure helper functions for deep-copy path override, allowed path validation, payload revalidation, canonical hash recomputation, and no-internal-field enforcement.
  - [x] Keep helper code testable without HTTP concerns.

- [x] T3: Add solver job template version routes (AC: 4, 11-19)
  - [x] Add `POST /v1/job-templates/{template_id}/versions`.
  - [x] Add `GET /v1/job-templates/{template_id}/versions`.
  - [x] Reuse existing API-key verification, owner scoping, and RFC 7807 error patterns.
  - [x] Ensure no execution, idempotency, billing, voucher, outbox, or ledger side effects.

- [x] T4: Add backend tests (AC: 1-19, 24-25)
  - [x] Test initial save duplicate replay still works after index migration.
  - [x] Test prediction version create with changed `horizon` and deterministic hash.
  - [x] Test optimization version create with one allowed parameter change and submit-compatible payload.
  - [x] Test cross-user/deleted/missing template rejection.
  - [x] Test invalid paths and invalid values return RFC 7807 and create no rows.
  - [x] Test version history ordering and soft-delete behavior.
  - [x] Test no unrelated side effects in execution/idempotency/billing/voucher/outbox tables where present.

- [x] T5: Add web API helpers and tests (AC: 20, 24-25)
  - [x] Add TypeScript request/response interfaces and helper functions in `api.ts`.
  - [x] Assert URL, Authorization header, body shape, version history behavior, and RFC 7807 preservation.

- [x] T6: Add prediction Console reuse/version vertical slice (AC: 21-24)
  - [x] Extend save-template success state with a horizon edit control and create-version action.
  - [x] Use the returned version payload to call `postPrediction` with a fresh idempotency key.
  - [x] Show new version metadata/history and new prediction result without hiding the original prediction result.
  - [x] Keep API key, template payloads, source data, and prediction outputs out of browser storage.
  - [x] Add focused page tests for success, version error, prediction error, no original resubmit, and storage hygiene.

- [x] T7: Review, gates, and GitHub sync (AC: 24-25)
  - [x] Run focused backend/web tests.
  - [x] Run static gates for touched Python/TypeScript files.
  - [x] Run post-implementation code review and fix findings.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.

## Dev Notes

### Backend Patterns To Reuse

- Template route owner remains `apps/solver-orchestrator/src/solver_orchestrator/routes.py` under `router = APIRouter(prefix="/v1")`.
- Existing template helpers are in `apps/solver-orchestrator/src/solver_orchestrator/job_templates.py`; extend there instead of scattering merge/hash logic in route handlers.
- Auth remains API-key based: `verify_api_key(authorization, session, client_ip=...)` then `require_scope("optimize:write", scopes)`.
- Owner scoping should mirror 5.D.3: missing/cross-user/deleted templates return 404.
- Use `_rfc7807_error(...)` and `ErrorDetail` for field-specific validation errors.
- Use app-generated UUIDs for new version rows.
- Use PostgreSQL `ON CONFLICT DO NOTHING ... RETURNING` or equivalent retry logic for race-safe root saves/version numbers; avoid broad transaction rollback after auth side effects.
- Prediction validation should reuse the public constraints currently enforced around `_validate_prediction_payload`.
- Optimization validation should reuse `OptimizationRequest.model_validate(...)`, provider route checks, and fallback checks without executing solver or billing calls.

### Schema Notes

- 5.D.3 created `uq_job_templates_active_source_name` across all active rows. That blocks multi-version chains if versions preserve source/name. This story must replace that index, not merely add a new index.
- Initial root rows are identified by `parent_template_id IS NULL` and `version=1`.
- Version rows use `parent_template_id IS NOT NULL` and inherit `root_template_id` from the selected template lineage.
- Version numbers should monotonically increase per root lineage and should not be renumbered after soft delete.

### Frontend Patterns To Reuse

- `apps/web/src/lib/api.ts` owns `SOLVER_SERVICE_URL`, `request<T>()`, `OptiCloudClientError`, `postPrediction`, and 5.D.3 template helpers.
- `apps/web/src/app/console/predictions/page.tsx` keeps API key in an input ref and already asserts storage hygiene.
- The reuse/version UI should appear only after a successful template save in the prediction Console for this story's vertical slice.
- Do not add a marketing landing page. Keep the UI dense, operational, and close to the existing Console pattern.
- Do not store template payloads or prediction results in browser storage.

### Suggested Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/solver-orchestrator/src;apps/billing-service/src'; uv run pytest apps/solver-orchestrator/tests/test_job_templates.py -q
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/solver-orchestrator/src;apps/billing-service/src'; uv run pytest apps/solver-orchestrator/tests/test_prediction_submission.py apps/solver-orchestrator/tests/test_status_progress_eta.py apps/solver-orchestrator/tests/test_job_templates.py -q
uv run ruff check apps/solver-orchestrator/src/solver_orchestrator apps/solver-orchestrator/tests/test_job_templates.py
uv run ruff format --check apps/solver-orchestrator/src/solver_orchestrator apps/solver-orchestrator/tests/test_job_templates.py
uv run mypy apps/solver-orchestrator/src/solver_orchestrator
pnpm vitest run src/lib/job-templates.test.ts src/app/console/predictions/page.test.tsx src/lib/api-prediction.test.ts
pnpm typecheck
pnpm test
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Implementation satisfies every Acceptance Criterion without implementing 5.D.5-5.D.7 scope early.
- Existing 5.D.3 save/list/read/delete behavior remains compatible.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review and gates.
- Branch is pushed, PR is created, merged to `main`, remote branch is deleted, and local `main` is synced.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/5-d-4-job-templates-version`.
- Baseline commit: `1be4c79629145cf5a130112b4f24ea24f9620ee5`.
- Focused backend gate: `uv run pytest apps/solver-orchestrator/tests/test_job_templates.py -q` -> 18 passed.
- Focused web gate: `pnpm vitest run src/lib/job-templates.test.ts src/app/console/predictions/page.test.tsx src/lib/api-prediction.test.ts` -> 19 passed.
- Backend regression gate: `uv run pytest apps/solver-orchestrator/tests/test_job_templates.py apps/solver-orchestrator/tests/test_prediction_submission.py apps/solver-orchestrator/tests/test_status_progress_eta.py -q` -> 60 passed.
- Static gates: `ruff check`, `ruff format --check`, `mypy`, `pnpm typecheck`, `pnpm test`, and `git diff --check` all passed locally.
- GitHub PR #130 first CI pass: `changes`, `lint`, `mypy`, `solver-orchestrator-test`, `ts-typecheck`, `e2e`, `matrix-detect`, `build-and-sbom (auth-service)`, and `gtm-toolkit-validation` passed.

### Completion Notes List

- Upgraded `job_templates` lineage persistence so active root duplicate-save replay remains unique while active lineage versions are unique by `(user_id, root_template_id, version)`.
- Added strict version create/list schemas and solver-orchestrator routes for `POST/GET /v1/job-templates/{template_id}/versions`.
- Added one-parameter whole-field merge helpers with deep-copy behavior, explicit editable paths, internal-field rejection, canonical hash recomputation, and prediction/optimization request revalidation.
- Added transaction-scoped advisory locking around lineage version allocation plus unique index conflict protection; concurrent version creation now returns unique monotonically increasing versions.
- Extended the web API client with typed version create/list helpers and RFC 7807 preservation.
- Added the prediction Console vertical slice: save prediction as template, edit horizon, create a new template version, submit the returned version payload with a fresh idempotency key, and show version history/result while preserving the original prediction result.
- Post-implementation review found and fixed two patch items: missing concurrent version allocation regression coverage, and loss of created-version metadata when downstream prediction submission failed.
- GitHub PR #130 was created from `codex/5-d-4-job-templates-version`, passed CI, and was used for final sync.

### File List

- `_bmad-output/stories/5-d-4-job-templates-version.md`
- `_bmad-output/stories/sprint-status.yaml`
- `infra/local-init/02-solver-schema.sql`
- `apps/solver-orchestrator/src/solver_orchestrator/job_templates.py`
- `apps/solver-orchestrator/src/solver_orchestrator/models.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`
- `apps/solver-orchestrator/tests/test_job_templates.py`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/job-templates.test.ts`
- `apps/web/src/app/console/predictions/page.tsx`
- `apps/web/src/app/console/predictions/page.test.tsx`

## Change Log

- 2026-06-01 - Story created for job template version creation, lineage history, and prediction Console reuse vertical slice.
- 2026-06-01 - Implemented backend template versioning, web API helpers, prediction Console reuse flow, post-review fixes, and local gates.
- 2026-06-01 - Marked story done after local gates and GitHub PR #130 CI pass.

## Post-Implementation Code Review

### Findings

- [x] [Review][Patch] Add explicit concurrent version allocation coverage. AC12 requires concurrent creates to avoid duplicate active versions; fixed with a transaction-scoped advisory lineage lock and a four-way concurrent API regression test.
- [x] [Review][Patch] Preserve created-version metadata if downstream prediction submission fails. AC21/23 require version metadata/history and original result visibility; fixed by splitting version creation from prediction submission and adding a focused UI regression.

### Outcome

Changes requested internally; all findings fixed and local gates rerun successfully.

## Pre-Implementation Adversarial Review

### Round 1 - Lineage Schema, Duplicate Replay, And Version Number Integrity

Findings:

1. The 5.D.3 unique index on active `(user_id, source_kind, source_id, name)` blocks additional versions if versions preserve the root source/name.
2. Dropping that unique index without a replacement would break 5.D.3 duplicate initial-save replay.
3. Computing `max(version)+1` without a DB uniqueness guard creates duplicate version numbers under concurrent version creation.
4. Soft-deleted versions could cause version number reuse if the implementation computes max only over active rows.

Revision after Round 1:

- Required replacing the 5.D.3 unique index with a root-only initial-save index.
- Required a separate active `(user_id, root_template_id, version)` unique index.
- Required initial save lookup/insert logic to target active root templates only.
- Required version numbers to use max over the full lineage, not only non-deleted rows.
- Required conflict-safe retry/insert behavior for concurrent version creation.

### Round 2 - Payload Drift, One-Parameter Boundary, And Execution Side Effects

Findings:

1. Accepting arbitrary `payload_json` would undo 5.D.3's sanitized payload boundary.
2. JSON pointer edits into array elements can turn "one parameter" into unbounded partial mutation and hard-to-review drift.
3. Version creation could accidentally execute tasks or create billing/idempotency rows if it reuses submission code too directly.
4. Prediction and optimization payload constraints differ; generic JSON merge without schema-specific validation could persist non-executable templates.

Revision after Round 2:

- Version create accepts one allowed whole-field `parameter_path` plus `value`, not arbitrary payloads.
- Allowed paths are explicit and schema-specific.
- Version endpoint must validate the full merged payload but must not execute solvers, predictions, billing, or idempotency paths.
- Prediction validation must use public execution constraints; optimization validation must use the public `OptimizationRequest` contract plus provider/fallback checks.

### Round 3 - UI Closure, History Visibility, Auth/Storage Hygiene, And Regression Coverage

Findings:

1. A broad template management UI would be too large for this story and could drift into 5.D.5-5.D.7 budget/notification scope.
2. A reuse button could accidentally resubmit the original prediction instead of the returned version payload.
3. Version history could leak deleted or cross-user versions if the lookup is rooted only by `root_template_id` without owner/deleted filters.
4. Web storage hygiene needs to cover template payloads and version payloads, not just API keys.
5. Regression tests need to prove 5.D.3 duplicate saves still work after the index change.

Revision after Round 3:

- Frontend scope is limited to a prediction Console post-save vertical slice: edit `horizon`, create a version, submit the returned version payload, show result/history.
- Required original prediction result to remain visible and original prediction not to be resubmitted by version actions.
- Required owner-scoped, non-deleted version history.
- Expanded storage hygiene to API keys, template payloads, source data, and prediction outputs.
- Added explicit backend regression coverage for 5.D.3 duplicate initial-save replay after schema/index upgrade.
