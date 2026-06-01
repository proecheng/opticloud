---
story_key: 5-d-3-job-templates-save
baseline_commit: 5242285bff12836b71c145c95c05240ab26a51a5
epic_num: 5
story_num: D.3
epic_name: Billing - Invoices + Templates + Budget + Notifications
status: done
priority: High
type: solver job template save foundation
created_by: bmad-create-story
created_at: 2026-06-01
sources:
  - _bmad-output/planning/epics.md (Epic 5.D / Story 5.D.3 / FR B11)
  - _bmad-output/planning/prd.md (FR B11 v1 required, simplified profile can cut)
  - _bmad-output/planning/architecture.md (solver-orchestrator execution owner; billing-service billing owner; Next.js Console)
  - _bmad-output/stories/5-d-2-7d-30d-sparkline-trends.md
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py
  - apps/solver-orchestrator/src/solver_orchestrator/models.py
  - apps/solver-orchestrator/src/solver_orchestrator/schemas.py
  - infra/local-init/02-solver-schema.sql
  - apps/web/src/lib/api.ts
  - apps/web/src/app/console/predictions/page.tsx
---

# Story 5.D.3 - Job templates save

Status: done

## Story

**As** an authenticated OptiCloud execution user,
**I want** to save a successful optimization or prediction request as a reusable job template record,
**so that** I have a durable, owner-scoped starting point for template reuse and version history in Story 5.D.4.

## Context

FR B11 requires users to save job templates, reuse them, and version them. Epic 5.D deliberately splits that requirement: 5.D.3 owns the save foundation, while 5.D.4 owns reuse plus version creation. The epics seed says "template 入 DB + reuse + version"; for this story, "reuse + version" means the saved record exposes a stable payload and `version=1` metadata that 5.D.4 can build on. It does not mean executing from a template, editing parameters, or creating version chains.

Execution payloads belong to `solver-orchestrator` because it owns optimization/prediction validation, persistence, task ownership, and request payload shapes. `billing-service` remains out of scope; it must not store raw execution payloads.

## Scope

1. Add a `job_templates` table and ORM model in `solver-orchestrator`.
2. Save a template from an owner-scoped successful source task: completed optimization or completed prediction.
3. Persist a sanitized public request payload with deterministic SHA-256 fingerprint and stable payload schema version metadata.
4. Persist version metadata for the initial template version only: `version=1`, `root_template_id=id`, and nullable `parent_template_id`.
5. Add authenticated API-key endpoints to create, list, read, and soft-delete the current user's templates; all template routes reuse the existing `optimize:write` scope because solver API keys do not yet define a read-only execution scope.
6. Add typed web API helpers.
7. Add a small save-template flow after successful Console prediction submission and show saved template confirmation/list state on that page.
8. Add focused backend and web tests.
9. Run post-implementation code review, fix findings, pass gates, and sync GitHub.

## Out Of Scope

- Executing a task from a template.
- Editing template parameters.
- Creating a new version from an existing template.
- Version history UI beyond exposing `version=1` and lineage fields.
- Billing, budget alerts, notification preferences, invoices, credits, or ledger mutations.
- Accepting arbitrary raw payloads not tied to a successful persisted task.
- JWT Console task history. Existing solver execution routes use API keys; this story follows the same auth boundary.
- Saving failed, timed-out, cancelled, queued, in-progress, demo, anonymous-only, or cross-user source tasks.
- Storing API keys, JWTs, billing charge IDs, result payloads, solver solutions, forecast outputs, raw file bytes, emails, phone numbers, or raw `_system` metadata inside template payloads.

## Acceptance Criteria

1. A new `job_templates` table exists in solver schema with UUID `id`, `user_id`, `name`, optional `description`, `source_kind`, `source_id`, `task_type`, `payload_schema_version`, sanitized `payload_json`, `payload_sha256`, `version`, `root_template_id`, nullable `parent_template_id`, `created_at`, `updated_at`, and nullable `deleted_at`.
2. The DB enforces `source_kind IN ('optimization','prediction')`, `payload_schema_version IN ('optimization_request_v1','prediction_request_v1')`, `version >= 1`, self-referential lineage integrity, and at most one non-deleted template per `(user_id, source_kind, source_id, name)`.
3. SQLAlchemy model metadata matches the local init schema, and the schema change is idempotent for developer databases that already ran older `02-solver-schema.sql` versions.
4. Every `/v1/job-templates` route requires `Authorization: Bearer sk-...` with `optimize:write`; no route accepts client-provided `user_id`.
5. The create request accepts `name`, optional `description`, `source_kind`, and `source_id`; it does not accept arbitrary `payload_json`, `version`, `root_template_id`, or `parent_template_id`.
6. Names are trimmed, length-limited, and non-empty after trimming. Descriptions are trimmed and length-limited.
7. Source lookup is owner-scoped. Cross-user source IDs return 404 and do not reveal existence.
8. Optimization sources must have `status='completed'`; prediction sources must have `status='completed'`. Other statuses return 422 RFC 7807 with a field-specific error.
9. Saved payloads are derived from the source row's public request payload after removing `_system` metadata.
10. Optimization templates use `payload_schema_version="optimization_request_v1"` and include the request fields needed to submit the same optimization later, including `task_type`, exactly one objective (`minimize` or `maximize`), constraints `st` with alias-compatible matrix key `A`, `options`, `solver` when present, and `fallback_chain` when present.
11. Prediction templates use `payload_schema_version="prediction_request_v1"` and include normalized `family`, numeric `data`, and integer `horizon`.
12. Template payloads never include results, solutions, objectives, predictions, errors, billing metadata, idempotency keys, API keys, JWTs, emails, phones, or raw file bytes.
13. `payload_sha256` is deterministic over canonical JSON with sorted keys and compact separators, computed from an envelope containing `source_kind`, `payload_schema_version`, and `payload_json`.
14. Initial saves always return `version=1`, `root_template_id` equal to the template `id`, and `parent_template_id=null`; implementation should generate the template UUID in application code before insert so the self-root can be persisted atomically.
15. New saves return 201. Duplicate save with the same owner, source, and name returns 200 with the existing non-deleted template rather than creating a second active row.
16. `GET /v1/job-templates` returns only the caller's non-deleted templates, newest first, with compact metadata and sanitized payload fingerprint.
17. `GET /v1/job-templates/{template_id}` returns only owner-scoped non-deleted templates and includes the sanitized payload plus payload schema version.
18. `DELETE /v1/job-templates/{template_id}` soft-deletes only owner-scoped non-deleted templates, updates `deleted_at` and `updated_at`, and returns 204. A second delete or cross-user delete returns 404.
19. Template routes do not create optimization/prediction executions, idempotency rows, billing charges, vouchers, outbox rows, or ledger rows.
20. Web API helpers in `apps/web/src/lib/api.ts` expose typed create/list/get/delete template functions against `SOLVER_SERVICE_URL` with API-key bearer auth and existing RFC 7807 error handling.
21. The prediction Console page can save a successfully completed prediction as a template using the entered API key, a user-supplied template name, and the returned `prediction_id`.
22. The prediction Console save flow does not store API keys, template payloads, or source data in `sessionStorage`/`localStorage`.
23. The UI handles save success, duplicate replay, validation error, auth error, and retry without hiding the prediction result or re-submitting the prediction.
24. Tests cover owner scoping, completed-only source validation, payload sanitization, deterministic fingerprint, duplicate idempotent save, list/read/delete ownership, no side effects outside `job_templates`, API helper URL/auth/error behavior, Console save success/error states, and storage hygiene.
25. Quality gates pass:
    - focused solver job template tests;
    - focused web API/page tests;
    - relevant solver regression for prediction/optimization status routes;
    - ruff/format/mypy for touched Python files;
    - web test/typecheck for touched frontend files;
    - `git diff --check`.

## Tasks / Subtasks

- [x] T1: Add job template persistence model and schema (AC: 1-3)
  - [x] Extend `infra/local-init/02-solver-schema.sql` with idempotent table/index/constraint DDL.
  - [x] Include `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`/constraint-safe patterns where needed so existing local DBs can be upgraded.
  - [x] Add `JobTemplate` ORM model in `apps/solver-orchestrator/src/solver_orchestrator/models.py`.
  - [x] Generate template UUIDs in application code so `root_template_id=id` is atomic for initial saves.
  - [x] Use application-assigned `updated_at` on create/delete unless adding a trigger is already an established local pattern.

- [x] T2: Add template payload canonicalization and schemas (AC: 5-14)
  - [x] Add Pydantic create/list/detail response models in `schemas.py`.
  - [x] Add a focused helper module for source validation, `_system` stripping, payload schema version selection, canonical JSON envelope creation, and SHA-256.
  - [x] Keep helper code pure and testable without HTTP concerns.

- [x] T3: Add solver job template routes (AC: 4-19)
  - [x] Add `POST /v1/job-templates`.
  - [x] Add `GET /v1/job-templates`.
  - [x] Add `GET /v1/job-templates/{template_id}`.
  - [x] Add `DELETE /v1/job-templates/{template_id}`.
  - [x] Reuse existing API-key verification and RFC 7807 error patterns.

- [x] T4: Add backend tests (AC: 1-19, 24-25)
  - [x] Test successful save from completed prediction and completed optimization.
  - [x] Test queued/failed/timeout/cancelled/non-owner source rejection.
  - [x] Test `_system`, result, billing, idempotency, and credential fields are absent from template payloads.
  - [x] Test deterministic fingerprint and duplicate save replay.
  - [x] Test list/read/delete owner scoping and soft delete.
  - [x] Test row counts proving no unrelated side effects in `optimizations`, `predictions`, idempotency tables, vouchers, and billing/outbox tables when present.

- [x] T5: Add web API helpers and tests (AC: 20, 24-25)
  - [x] Add TypeScript interfaces and helper functions in `api.ts`.
  - [x] Assert URL, Authorization header, body shape, 204 delete behavior, and RFC 7807 preservation.

- [x] T6: Add prediction Console save-template flow (AC: 21-24)
  - [x] Add template name/description controls after successful prediction.
  - [x] Call the new create helper with `source_kind='prediction'` and returned `prediction_id`.
  - [x] Show success/error/retry states independent from prediction result state and without triggering another prediction submit.
  - [x] Keep API key and source payload out of browser storage.
  - [x] Add focused page tests.

- [x] T7: Review, gates, and GitHub sync (AC: 24-25)
  - [x] Run focused backend/web tests.
  - [x] Run static gates for touched Python/TypeScript files.
  - [x] Run post-implementation code review and fix findings.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.

### Review Findings

- [x] [Review][Patch] Duplicate active template saves could race between pre-check and insert [apps/solver-orchestrator/src/solver_orchestrator/routes.py] — fixed with PostgreSQL `ON CONFLICT DO NOTHING ... RETURNING` plus conflict replay lookup and concurrent duplicate-save regression coverage.
- [x] [Review][Patch] Optimization template payload copied unexpected top-level source fields after `_system` stripping [apps/solver-orchestrator/src/solver_orchestrator/job_templates.py] — fixed by rebuilding payloads from an explicit request-field whitelist and adding pollution regression coverage.
- [x] [Review][Patch] Create request schema accepted forbidden caller-supplied payload, version, and lineage fields [apps/solver-orchestrator/src/solver_orchestrator/schemas.py] — fixed with `extra="forbid"` and route coverage for rejected `payload_json`, `version`, `root_template_id`, and `parent_template_id`.
- [x] [Review][Patch] Prediction Console save silently ignored missing API key [apps/web/src/app/console/predictions/page.tsx] — fixed with a visible save error state while keeping the prediction result visible and avoiding prediction resubmission.

## Dev Notes

### Backend Patterns To Reuse

- Router owner: `apps/solver-orchestrator/src/solver_orchestrator/routes.py` under `router = APIRouter(prefix="/v1")`.
- Auth: existing solver execution routes call `verify_api_key(authorization, session, client_ip=...)` then `require_scope("optimize:write", scopes)`.
- Owner scoping: existing `GET /v1/predictions/{prediction_id}` and `GET /v1/optimizations/{optimization_id}` return 404 for non-owner or missing rows.
- Error pattern: use `_rfc7807_error(...)` with `ErrorDetail` for 422 and 409/400-style validation.
- Source rows:
  - `Optimization.input_payload` contains public request plus `_system` metadata; completed row response is built separately.
  - `Prediction.input_payload` contains normalized public request plus `_system` metadata.
- Local DB setup is append-only SQL in `infra/local-init`; there is no service-local Alembic flow to update.
- Do not reuse billing-service. Job templates are execution artifacts.

### Template Contract Rules

- Public route prefix: `/v1/job-templates`.
- Contract name is implicit in endpoint and schemas; do not add a billing trend/invoice contract field.
- Supported `source_kind`: `optimization`, `prediction`.
- `payload_json` must be public source request payload after recursively dropping `_system`; never trust caller-provided payload fields because create does not accept them.
- Payload schema versions:
  - `optimization_request_v1`
  - `prediction_request_v1`
- Hash envelope:
  - `{"source_kind": source_kind, "payload_schema_version": payload_schema_version, "payload_json": payload_json}`
- Hash function: `sha256(json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))`.
- Initial version fields:
  - `version=1`
  - `root_template_id=id`
  - `parent_template_id=null`
- Duplicate rule: same active `(user_id, source_kind, source_id, name)` returns existing row. If a row was soft-deleted, a new save may create a new active row.
- `updated_at` should change on soft delete; do not add a global trigger unless the existing project schema already uses one.

### Frontend Patterns To Reuse

- `apps/web/src/lib/api.ts` already owns `SOLVER_SERVICE_URL`, `request<T>()`, `OptiCloudClientError`, and `postPrediction`.
- `apps/web/src/app/console/predictions/page.tsx` already keeps API key in an input ref and asserts storage hygiene.
- Save controls should appear only for `state.kind === "solved"` and must not block the prediction result table.
- This UI must not execute from a template, edit template parameters, or create versions. 5.D.4 owns those flows.
- Avoid a new Console route unless needed for testability; 5.D.4 can introduce full template management/reuse UI.

### Suggested Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/solver-orchestrator/src;apps/billing-service/src'; uv run pytest apps/solver-orchestrator/tests/test_job_templates.py -q
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/solver-orchestrator/src;apps/billing-service/src'; uv run pytest apps/solver-orchestrator/tests/test_prediction_submission.py apps/solver-orchestrator/tests/test_status_progress_eta.py apps/solver-orchestrator/tests/test_job_templates.py -q
uv run ruff check apps/solver-orchestrator/src/solver_orchestrator apps/solver-orchestrator/tests/test_job_templates.py
uv run ruff format --check apps/solver-orchestrator/src/solver_orchestrator apps/solver-orchestrator/tests/test_job_templates.py
uv run mypy apps/solver-orchestrator/src/solver_orchestrator
pnpm --dir apps/web vitest run src/lib/job-templates.test.ts src/app/console/predictions/page.test.tsx
pnpm --dir apps/web typecheck
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Implementation satisfies every Acceptance Criterion without implementing 5.D.4-5.D.7 scope early.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review and gates.
- Branch is pushed, PR is created, merged to `main`, remote branch is deleted, and local `main` is synced.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/5-d-3-job-templates-save`.
- Baseline commit: `5242285bff12836b71c145c95c05240ab26a51a5`.
- Red phase confirmed: `uv run pytest apps/solver-orchestrator/tests/test_job_templates.py -q` failed before implementation with missing schema and `/v1/job-templates` 404s.
- Focused backend job template tests passed: `uv run pytest apps/solver-orchestrator/tests/test_job_templates.py -q` (10 tests, 5 FastAPI deprecation warnings for existing `HTTP_422_UNPROCESSABLE_ENTITY` constant usage).
- Frontend red phase confirmed: `pnpm vitest run src/lib/job-templates.test.ts src/app/console/predictions/page.test.tsx` failed before implementation with missing API helpers and missing save-template controls.
- Focused web job template/API/page tests passed: `pnpm vitest run src/lib/job-templates.test.ts src/app/console/predictions/page.test.tsx` (10 tests).
- Post-implementation review triage: 0 decision-needed, 4 patch findings fixed, 0 deferred, 0 dismissed.
- Final focused solver job template tests passed: `uv run pytest apps/solver-orchestrator/tests/test_job_templates.py -q` (13 tests; FastAPI 422 deprecation warnings only).
- Final relevant solver regression passed: `uv run pytest apps/solver-orchestrator/tests/test_job_templates.py apps/solver-orchestrator/tests/test_prediction_submission.py apps/solver-orchestrator/tests/test_status_progress_eta.py -q` (55 tests; FastAPI 422 deprecation warnings only).
- Final Python static gates passed: `uv run ruff check apps/solver-orchestrator/src/solver_orchestrator apps/solver-orchestrator/tests/test_job_templates.py`; `uv run ruff format --check apps/solver-orchestrator/src/solver_orchestrator apps/solver-orchestrator/tests/test_job_templates.py`; `uv run mypy apps/solver-orchestrator/src/solver_orchestrator` (existing unused `tests.*` mypy config note only).
- Final focused web tests passed: `pnpm vitest run src/lib/job-templates.test.ts src/app/console/predictions/page.test.tsx src/lib/api-prediction.test.ts` (13 tests).
- Final web gates passed: `pnpm typecheck`; `pnpm test` (29 files, 144 tests).
- Final whitespace gate passed: `git diff --check`.

### Completion Notes List

- Added solver-owned `job_templates` persistence with idempotent local schema, ORM model, API-key routes, sanitized payload helpers, deterministic payload hash envelope, and focused backend tests.
- Added typed web API helpers and a prediction Console save-template flow that reuses the entered API key without writing secrets or template payloads to browser storage.
- Post-review fixes made duplicate saves race-safe, rebuilt optimization template payloads from an explicit request whitelist, rejected caller-supplied template internals, and surfaced missing API-key save errors without hiding the prediction result.

### File List

- `_bmad-output/stories/5-d-3-job-templates-save.md`
- `_bmad-output/stories/sprint-status.yaml`
- `infra/local-init/02-solver-schema.sql`
- `apps/solver-orchestrator/src/solver_orchestrator/error_catalog.py`
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

- 2026-06-01 - Story created for solver-owned job template save foundation, with version metadata reserved for 5.D.4.
- 2026-06-01 - Round 1 adversarial review tightened route scope, create status codes, self-root UUID generation, and 5.D.4 UI boundaries.
- 2026-06-01 - Round 2 adversarial review added payload schema versions, canonical hash envelope, and explicit optimization/prediction payload field requirements.
- 2026-06-01 - Round 3 adversarial review tightened idempotent schema upgrade, soft-delete timestamp behavior, no-resubmit UI closure, and side-effect tests.

## Pre-Implementation Adversarial Review

### Round 1 - Boundary, Scope Creep, Auth Isolation, And Version Split

Findings:

1. The original FR text says save + reuse + version, which could cause 5.D.3 to implement 5.D.4 early.
2. Template route scopes were only explicit for create; list/read/delete could drift into inconsistent authorization.
3. `root_template_id=id` can become non-atomic if the implementation relies only on a DB-generated UUID.
4. Duplicate create behavior lacked an explicit HTTP status split.
5. A prediction Console save button could become a full template management/reuse UI.
6. Storing execution payloads in billing-service would violate service ownership and increase raw payload exposure.

Revision after Round 1:

- Reconfirmed that 5.D.3 only saves initial templates and exposes `version=1` metadata; template execution, parameter edits, and version creation remain 5.D.4.
- Required all template routes to use API-key auth with existing `optimize:write` scope and no client-provided `user_id`.
- Required application-generated template UUIDs for atomic self-root lineage.
- Fixed create status behavior: 201 for new rows, 200 for duplicate replay.
- Kept the UI to a post-success prediction save flow and explicitly forbade reuse/version editing.
- Kept solver-orchestrator as the template owner and excluded billing-service payload storage.

### Round 2 - Drift, Data Consistency, Payload Canonicalization, And Source Semantics

Findings:

1. A plain `payload_sha256` over raw payload can drift if optimization and prediction payloads evolve differently.
2. Future 5.D.4 reuse needs to know which request schema the saved payload follows.
3. Optimization payloads can be serialized with `st.a` or `st.A`; template save must preserve the submit-compatible alias shape.
4. Prediction source rows store normalized payloads, while Console submits user-entered values; the story needed to specify normalized persisted values as the source of truth.
5. Hashing only `payload_json` makes cross-kind collisions theoretically ambiguous.
6. Recursive `_system` stripping needed to be explicit because source payloads already contain provider route, billing, reproducibility, and other internal metadata.

Revision after Round 2:

- Added `payload_schema_version` to the DB/API contract.
- Required `optimization_request_v1` and `prediction_request_v1`.
- Required optimization payloads to keep submit-compatible `st.A` shape and exactly one objective.
- Required prediction payloads to use normalized family/data/horizon from the persisted source row.
- Required SHA-256 over a canonical envelope containing source kind, schema version, and payload JSON.
- Clarified that create never accepts caller-provided payloads.

### Round 3 - Dependency Consistency, Migration Closure, UI Closure, And Test Closure

Findings:

1. The repo uses append-only local init SQL, not an Alembic migration path; story needed an idempotent upgrade requirement for existing dev DBs.
2. `payload_schema_version` also needs a DB-level check constraint, not just application code.
3. Soft delete without updating `updated_at` would make list ordering and auditability ambiguous.
4. A save-template retry could accidentally re-submit the prediction if UI state is coupled to the existing submit button.
5. Side-effect tests should include idempotency, voucher, billing, and outbox tables when present, not only optimization/prediction row counts.
6. Adding DB triggers for `updated_at` would be new schema machinery unless already established.

Revision after Round 3:

- Required idempotent local schema upgrade DDL.
- Added DB-level `payload_schema_version` constraint.
- Required soft delete to update both `deleted_at` and `updated_at`.
- Required save retry state to avoid prediction resubmission.
- Expanded side-effect tests to cover execution, idempotency, voucher, billing, and outbox tables where present.
- Kept `updated_at` application-assigned unless an existing trigger pattern is found.
