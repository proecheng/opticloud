---
story_key: 7-b-1-provider-apply-v2
baseline_commit: 425a7e7c7ffd32ce3c9673c410e2c6dee4a58b4a
epic_num: 7
story_num: B.1
epic_name: Provider Marketplace v2
status: done
priority: High
type: provider application contract and evaluation intake
created_by: bmad-create-story
created_at: 2026-06-01
sources:
  - _bmad-output/planning/epics.md (Epic 7.B / Story 7.B.1-8 brief)
  - _bmad-output/planning/prd.md (Provider Integration P1-P8, Provider Public v2 endpoint group, Provider shadow NFR)
  - _bmad-output/planning/architecture.md (FR to service mapping, C17 capability-registry M5+ state machine path)
  - _bmad-output/planning/ux-design-specification.md (Provider Console v2 and provider transparency notes)
  - _bmad-output/stories/7-a-1-capability-registry-v1-schema.md
  - _bmad-output/stories/7-a-2-revenue-share-hook-v2-reservation.md
  - apps/capability-registry/src/capability_registry/models.py
  - apps/capability-registry/src/capability_registry/schemas.py
  - apps/capability-registry/src/capability_registry/routes.py
  - infra/local-init/14-capability-registry.sql
---

# Story 7.B.1 - Provider Apply v2

Status: done

## Story

**As** an external algorithm provider,
**I want** to submit an application with OpenAPI and Docker image contract references plus an evaluation intake request,
**so that** OptiCloud can review the provider for later shadow validation without changing the v1 provider/capability contracts.

## Context

Epic 7.B starts the v2 Provider Marketplace. PRD P1 is the first Provider FR: external providers can apply via OpenAPI + Docker + evaluation. Architecture maps P1-P3 to `capability-registry`, while P4-P7 later cross into `solver-orchestrator` routing and dashboards, and P8 later uses revenue-share. Stories 7.A.1 and 7.A.2 already reserved provider/capability/OAuth/revenue-share contracts inside `apps/capability-registry`.

This story creates the provider application intake contract only. It must not run benchmark jobs, perform shadow validation, promote traffic, create provider dashboard UX, compute revenue, mutate solver routing, or insert an approved provider into the live `capability_providers` catalog. Later 7.B stories can consume the application and evaluation-request records.

## Scope

1. Extend `infra/local-init/14-capability-registry.sql` with idempotent provider application and evaluation intake tables.
2. Add SQLAlchemy models and Pydantic schemas in `apps/capability-registry`.
3. Add internal API routes:
   - `PUT /v1/provider-applications/{application_id}`
   - `GET /v1/provider-applications/{application_id}`
   - `GET /v1/provider-applications?tenant_id=&requested_provider_id=&status=`
   - `POST /v1/provider-applications/{application_id}/submit`
   - `PUT /v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}`
   - `GET /v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}`
   - `GET /v1/provider-applications/{application_id}/evaluation-requests?tenant_id=&status=`
4. Add focused API/schema/OpenAPI tests while preserving all 7.A behavior.
5. Regenerate `packages/shared-ts/openapi/capability-registry.json` and keep OpenAPI drift checks green.

## Out Of Scope

- Provider Console UI, public marketing/provider pages, provider self-service auth, or API Gateway proxy work.
- Running actual evaluation, benchmark workers, sandbox jobs, Docker pulls, cosign verification, SBOM parsing, or OpenAPI contract execution.
- Shadow validation thresholds, 14 day / 500 sample / 98% success gating, health checks, or promotion.
- Traffic rollout, route-share dashboard, KPI dashboard, provider payout, monthly revenue share, or version update lifecycle.
- Creating or mutating `capability_providers` rows as a side effect of application submission.
- Reading, storing, or returning registry passwords, OAuth tokens, API keys, bank/tax details, raw Docker credentials, or raw benchmark datasets.
- Changing solver-orchestrator static routing, fallback behavior, billing, revenue-share hooks, or reproducibility auto-migration.

## Acceptance Criteria

1. `infra/local-init/14-capability-registry.sql` idempotently creates `provider_applications` and `provider_application_evaluation_requests`.
2. `provider_applications` has columns: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `tenant_id UUID NULL`, `application_id VARCHAR(64) NOT NULL`, `requested_provider_id VARCHAR(64) NOT NULL`, `provider_kind VARCHAR(32) NOT NULL`, `display_name VARCHAR(120) NOT NULL`, `organization_name VARCHAR(160) NOT NULL`, `contact_email VARCHAR(254) NOT NULL`, `homepage_url TEXT NULL`, `openapi_url TEXT NOT NULL`, `openapi_sha256 VARCHAR(64) NOT NULL`, `image_digest TEXT NOT NULL`, `cosign_bundle JSONB NOT NULL DEFAULT '{}'::jsonb`, `evaluation_profile JSONB NOT NULL DEFAULT '{}'::jsonb`, `status VARCHAR(32) NOT NULL DEFAULT 'draft'`, `submitted_at TIMESTAMPTZ NULL`, `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`, `created_at`, and `updated_at`.
3. `provider_kind` accepts only marketplace applicant kinds `external` and `commercial`; `self` and `open_source` applications are rejected.
4. `application_id`, `evaluation_id`, and `requested_provider_id` use the existing provider ID pattern `^[a-z0-9][a-z0-9-]{0,63}$`. `benchmark_suite` uses `^[a-z0-9][a-z0-9_-]{0,63}$`.
5. Nullable `tenant_id` uniqueness is correct: one global row per `application_id`, one tenant row per `(tenant_id, application_id)`, one global row per `requested_provider_id`, and one tenant row per `(tenant_id, requested_provider_id)`.
6. `openapi_sha256` must be exactly 64 hex characters and `image_digest` must contain `sha256:<64 hex>`; malformed values return 422 before database errors.
7. `cosign_bundle`, `evaluation_profile`, and `metadata` must be JSON objects. Nested sensitive keys such as `api_key`, `password`, `client_secret`, `access_token`, `refresh_token`, `registry_password`, `docker_password`, `bank_account`, `tax_id`, `email`, `phone`, `email_body`, or `raw_dataset` are rejected recursively. The top-level `contact_email` field is the only allowed email/PII field in this story.
8. `homepage_url` is optional but, when provided, must be an `http://` or `https://` URL. `openapi_url` must also be `http://` or `https://`; non-HTTP schemes are rejected.
9. Application request/response payloads expose references only. They must not expose raw credentials, raw Docker auth, payment details, tax data, OAuth tokens, JWTs, API keys, or raw benchmark datasets.
10. `PUT /v1/provider-applications/{application_id}` is deterministic upsert. Path `application_id` is authoritative; body `application_id` may be omitted or must match the path. Mismatches return 422.
11. Application upsert is write-protected by the existing `X-Internal-Service-Auth` mechanism when `CAPABILITY_REGISTRY_INTERNAL_SECRET` is configured; empty dev secret remains usable for tests.
12. A new application may be `draft` or `submitted`. `submitted` sets `submitted_at` when missing. Updating a submitted application must not silently clear `submitted_at` or move the application back to `draft`.
13. `POST /v1/provider-applications/{application_id}/submit` transitions `draft` to `submitted`, sets `submitted_at` once, is idempotent for already-submitted applications, and returns 404 for unknown applications.
14. After submission, material application fields are immutable: `requested_provider_id`, `provider_kind`, `openapi_url`, `openapi_sha256`, `image_digest`, `cosign_bundle`, and `evaluation_profile`. Attempts to change them return 422.
15. Draft updates may modify non-identity fields, but they must not change `tenant_id` for an existing application. If a caller needs tenant-scope movement, it must create a distinct application row.
16. Duplicate `requested_provider_id` or `application_id` collisions return deterministic 422 API errors rather than surfacing database integrity exceptions.
17. Reads resolve tenant scope consistently with 7.A: no `tenant_id` reads only global rows; a tenant read may fall back to global only if response `scope_source="global_fallback"` documents it.
18. List applications supports filters by `tenant_id`, `requested_provider_id`, and `status`, returns global + tenant override semantics when tenant is provided, and sorts deterministically by `application_id`.
19. `provider_application_evaluation_requests` has columns: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `tenant_id UUID NULL`, `application_row_id UUID NOT NULL REFERENCES provider_applications(id) ON DELETE CASCADE`, `application_id VARCHAR(64) NOT NULL`, `evaluation_id VARCHAR(64) NOT NULL`, `requested_provider_id VARCHAR(64) NOT NULL`, `benchmark_suite VARCHAR(64) NOT NULL`, `sample_count INTEGER NOT NULL`, `timeout_seconds INTEGER NOT NULL`, `status VARCHAR(32) NOT NULL DEFAULT 'requested'`, `dataset_refs JSONB NOT NULL DEFAULT '[]'::jsonb`, `report_ref TEXT NULL`, `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`, `created_at`, and `updated_at`.
20. Evaluation status is intake-only: allowed values are `requested`, `queued`, `cancelled`; no completed/failed metrics are stored in this story and no queue/job/event is emitted when status is `queued`.
21. Evaluation requests require a submitted application. Draft applications return 422 for evaluation upsert.
22. Evaluation `sample_count` must be between 1 and 500 inclusive. `timeout_seconds` must be between 1 and 60 inclusive, matching the PRD sandbox-outside Provider soft-timeout boundary.
23. Evaluation `dataset_refs` must be a non-empty list of reference strings, not raw data rows or embedded benchmark payloads. Each ref must be non-empty, at most 256 chars, and start with `s3://`, `oss://`, `fixture://`, `benchmark://`, or `repro://`.
24. `report_ref`, when present, must be a reference string with the same allowed prefixes as `dataset_refs`; it must not contain raw report bodies.
25. Evaluation request upsert stores `requested_provider_id` from the application row, not from the request body, so callers cannot create application/evaluation provider drift.
26. `PUT /v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}` is deterministic upsert. Path IDs are authoritative; body IDs may be omitted or must match. Mismatches return 422.
27. Creating an evaluation request requires an existing submitted application in the same tenant scope or global fallback. Missing applications return 404; draft applications return 422.
28. Updating an existing evaluation request may change intake fields while status is `requested`; a `queued` or `cancelled` evaluation request may only be read or idempotently re-upserted with identical material fields. Material-field changes after `queued` or `cancelled` return 422.
29. Evaluation requests are unique per application scope and `evaluation_id`; nullable tenant uniqueness must be enforced with partial unique indexes or an equivalent safe strategy.
30. Evaluation request reads and lists must be scoped to the requested application; cross-application leakage is not allowed.
31. No route in this story creates, updates, or deletes `capability_providers`, `capabilities`, `provider_oauth_flows`, `revenue_share_policies`, or `revenue_share_hooks` as a side effect.
32. The new routes are included in `packages/shared-ts/openapi/capability-registry.json`, and `scripts/check_openapi_drift.py` detects drift.
33. Tests cover schema repeated application, ID and digest validation, tenant/global uniqueness, application upsert/read/list/submit, submitted timestamp preservation, submitted-field immutability, tenant immutability, deterministic duplicate handling, forbidden sensitive keys, evaluation request upsert/read/list, submitted-only evaluation creation, dataset reference validation, queued/cancelled evaluation immutability, write auth, OpenAPI unsafe-field absence, no catalog side effects, and existing 7.A regressions.
34. `.github/workflows/ci.yml` keeps the existing `capability-registry-test` job; no new CI service job is added.
35. Local gates pass: `uv run pytest apps/capability-registry/tests/ -v`, `uv run mypy apps packages`, `uv run ruff check apps/capability-registry`, `uv run ruff format --check apps/capability-registry`, `uv run python scripts/generate_openapi.py`, `uv run python scripts/check_openapi_drift.py`, and `git diff --check`.
36. Implementation record includes post-implementation code review findings and fixes.
37. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done`.

## Tasks / Subtasks

- [x] T1: Add provider application schema and models (AC: 1-9, 19-25, 29)
  - [x] Extend `infra/local-init/14-capability-registry.sql` idempotently.
  - [x] Add SQLAlchemy models for provider applications and evaluation requests.
  - [x] Preserve existing 7.A tables and tests.

- [x] T2: Add request/response schemas and validation (AC: 3-16, 19-28)
  - [x] Add Pydantic schemas with path/body ID parity, digest/hash validation, recursive secret-key rejection, status constraints, and reference-only dataset validation.
  - [x] Ensure applicant kinds are limited to `external` and `commercial`.
  - [x] Ensure submitted timestamp behavior is explicit and tested.

- [x] T3: Add API routes (AC: 10-18, 26-31)
  - [x] Add application upsert/read/list/submit routes under `/v1/provider-applications`.
  - [x] Add evaluation request upsert/read/list routes nested under the application.
  - [x] Reuse existing internal write auth and tenant/global scope helper patterns.
  - [x] Prove application submission has no side effects on live provider/capability catalog tables.

- [x] T4: Add tests and OpenAPI coverage (AC: 32-35)
  - [x] Extend capability-registry tests for application and evaluation behavior.
  - [x] Add OpenAPI unsafe-field absence assertions for provider application schemas.
  - [x] Regenerate checked-in OpenAPI.
  - [x] Run focused local gates.

- [ ] T5: Review, gates, and GitHub sync (AC: 36-37)
  - [x] Run post-implementation code review and fix findings.
  - [x] Run local gates after fixes.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [x] Mark story and sprint status `done` only after merge/sync.

## Dev Notes

### Service Boundary

- Implement only in `apps/capability-registry` plus the existing capability-registry SQL, OpenAPI, tests, and story/status files.
- Do not create `apps/provider-service`, `apps/revenue-share-service`, background workers, new queues, frontend pages, or solver-orchestrator caller changes.
- Treat capability-registry as the owner of P1-P3 state records, but not as the executor of evaluation or traffic routing.
- The current FastAPI service already exposes `/healthz`, `/readyz`, `/metrics`, `/`, and `/openapi.json`; preserve those surfaces.

### Existing Patterns To Reuse

- Follow `CapabilityProvider`, `Capability`, `ProviderOAuthFlow`, `RevenueSharePolicy`, and `RevenueShareHook` model/schema/route style.
- Reuse `_PATH_ID_PATTERN`, `_assert_path_id(...)`, `_require_write_auth(...)`, `_scope_source(...)`, and provider/capability tenant lookup semantics where applicable.
- Use partial unique indexes for every nullable-tenant uniqueness rule. Do not rely on a plain unique index that includes `tenant_id`.
- Use `Path(pattern=...)` and `Query(pattern=...)` so invalid path/filter IDs return 422 before database constraints.
- Keep JSONB fields serializable and free of SQLAlchemy internals or sensitive payloads.
- Existing tests apply `infra/local-init/14-capability-registry.sql` twice. Extend that harness instead of creating a new migration harness.

### Data Model Guidance

- `application_id`, `evaluation_id`, and `requested_provider_id` should use the same lowercase hyphen ID pattern as existing provider IDs.
- `benchmark_suite` is not a provider ID. Allow underscores for stable internal suite keys such as `lp_standard_500`.
- `application_id` is an intake resource ID, not a live `provider_id`. `requested_provider_id` is the desired future provider ID, but this story must not reserve it by creating a `capability_providers` row.
- `tenant_id` is part of application scope and should be immutable for an existing application row.
- Provider applications are for external marketplace applicants. Reject `self` and `open_source` to avoid internal/catalog rows entering the marketplace intake path.
- Do not add a new dependency for email validation. Use a conservative service-local validation rule unless an existing dependency is already present.
- Store artifact references only:
  - `openapi_url` + `openapi_sha256`
  - `image_digest`
  - `cosign_bundle` references or metadata, not private keys or registry auth
  - `dataset_refs` list of references, not raw dataset rows
- `contact_email` is allowed as the application contact field. Do not allow email bodies, message dumps, identity documents, or unrelated PII inside metadata.
- `submitted_at` is a lifecycle timestamp. Once set, it must not be cleared by a later upsert.
- Submitted applications must freeze artifact identity fields so later evaluation requests cannot drift away from reviewed material.
- Evaluation rows should copy `requested_provider_id` from the resolved application row. Do not accept a body-level `requested_provider_id` for evaluation upserts.
- Once an evaluation request leaves `requested`, keep its material fields immutable. This story is intake-only, so `queued` is only a recorded state and must not enqueue work.

### API Guidance

- `PUT /v1/provider-applications/{application_id}` should be deterministic and safe for retries.
- `POST /v1/provider-applications/{application_id}/submit` is the explicit lifecycle operation. It must be idempotent and should not mutate artifact fields.
- `PUT /v1/provider-applications/{application_id}/evaluation-requests/{evaluation_id}` reserves an evaluation request contract. It does not enqueue, run, or mark evaluation complete.
- Evaluation requests must be created only for submitted applications. This prevents later draft edits from changing what the evaluation intake was meant to test.
- Reads may remain internal service reads in this story, consistent with 7.A capability-registry dev-mode behavior.
- Keep API errors simple FastAPI `HTTPException`, but tests must pin 404 for missing applications and 422 for validation/path mismatches.

### Previous Story Intelligence

- 7.A.1 review found path IDs must be constrained at FastAPI route boundaries, not left to database constraints.
- 7.A.2 review found sensitive-key rejection must recurse into nested metadata/list structures.
- 7.A.2 fixed idempotency races for duplicate hook inserts. This story uses deterministic `PUT` for evaluation requests to avoid POST race semantics.
- OpenAPI generation and drift scripts already include `capability-registry`; only regenerate the spec after route/schema changes.

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
- Implementation satisfies every Acceptance Criterion without implementing 7.B.2+ shadow validation, traffic promotion, dashboards, provider payouts, version lifecycle, or monthly revenue share early.
- Existing provider/capability/OAuth/revenue-share behavior from 7.A.1 and 7.A.2 remains compatible.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/7-b-1-provider-apply-v2`.
- Baseline commit: `425a7e7c7ffd32ce3c9673c410e2c6dee4a58b4a`.
- Focused capability-registry tests: `uv run pytest apps/capability-registry/tests/ -v` -> 20 passed.
- Type gate: `uv run mypy apps packages` -> passed.
- Lint/format gates: `uv run ruff check apps/capability-registry` and `uv run ruff format --check apps/capability-registry` -> passed.
- OpenAPI gates: `uv run python scripts/generate_openapi.py` and `uv run python scripts/check_openapi_drift.py` -> passed.
- Whitespace gate: `git diff --check` -> passed.
- GitHub sync: PR #136 passed CI, squash-merged to `main` at `e646f69`, remote branch `codex/7-b-1-provider-apply-v2` was deleted, and local `main` synced with `origin/main`.

### Completion Notes List

- Story created for Provider Apply v2 intake contract.
- Added provider application and evaluation intake tables, SQLAlchemy models, Pydantic schemas, and API routes in capability-registry.
- Implemented draft/submitted application lifecycle, submitted artifact immutability, tenant/global scope reads, requested-provider duplicate handling, submitted-only evaluation intake, and queued/cancelled evaluation immutability.
- Preserved 7.A provider/capability/OAuth/revenue-share behavior and proved application submission has no live catalog side effects.
- Regenerated capability-registry OpenAPI and extended tests for unsafe-field absence, reference-only payloads, write auth, and tenant/global scope behavior.
- Post-implementation review findings fixed: broader sensitive-key detection for metadata/cosign/evaluation payloads and status immutability for locked evaluation requests.
- PR #136 passed GitHub CI, merged to `main`, branch cleanup completed, local `main` synced, and this story is now marked done.

### File List

- `_bmad-output/stories/7-b-1-provider-apply-v2.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/capability-registry/src/capability_registry/models.py`
- `apps/capability-registry/src/capability_registry/routes.py`
- `apps/capability-registry/src/capability_registry/schemas.py`
- `apps/capability-registry/tests/test_api.py`
- `infra/local-init/14-capability-registry.sql`
- `packages/shared-ts/openapi/capability-registry.json`

## Change Log

- 2026-06-01 - Story created for Provider Apply v2 intake contract.
- 2026-06-01 - Pre-implementation review round 1 tightened lifecycle boundaries, submitted-field immutability, duplicate handling, PII metadata rejection, and evaluation reference constraints.
- 2026-06-01 - Pre-implementation review round 2 tightened drift controls, URL schemes, benchmark naming, and evaluation/application provider consistency.
- 2026-06-01 - Pre-implementation review round 3 tightened closure conditions, tenant immutability, queued/cancelled evaluation immutability, and no-queue side effects.
- 2026-06-01 - Implemented Provider Apply v2 intake schema/API/tests/OpenAPI; post-implementation review fixes applied; story moved to code-review pending GitHub sync.
- 2026-06-01 - PR #136 passed CI, merged to `main`, branch cleanup and local sync completed; story status moved to `done`.

## Post-Implementation Code Review

### Findings

- [x] [Review][Patch] Evaluation requests marked `queued` or `cancelled` could still change status without changing other material fields. This violated the story's locked-state immutability requirement and could let an already queued intake be silently cancelled or toggled. Fixed by including `status` in locked material comparison, with regression coverage.
- [x] [Review][Patch] Sensitive-key rejection used exact lowercase key matching. Variants such as `contact_email` or `registryPassword` inside metadata/cosign payloads were not rejected, weakening the reference-only contract. Fixed by normalizing keys and rejecting compact/camel/snake variants, with regression coverage.

### Outcome

Changes requested internally; all findings fixed and local gates passed.

## Pre-Implementation Adversarial Review

### Round 1 - Boundary, Data Consistency, And Executability

Findings:

1. Draft applications could receive evaluation requests, allowing the artifact under evaluation to change later.
2. Submitted applications only preserved `submitted_at`; OpenAPI/image/cosign material could still drift after submission.
3. Metadata secret rejection named email bodies but did not explicitly make top-level `contact_email` the only allowed PII field.
4. Duplicate `requested_provider_id` could fall through to database unique indexes and surface as 500 without an API guard.
5. `dataset_refs` allowed arbitrary strings and did not prevent inline raw payloads.
6. `report_ref` existed in the table contract but lacked reference-only validation.
7. Applicant provider kind could drift back to the broader 7.A `ProviderKind` and accidentally admit `self`/`open_source`.
8. The story did not state whether submitted applications can move back to draft.
9. Evaluation scope behavior depended on tenant fallback but did not require a submitted source application.
10. The story did not explicitly say no new email-validation dependency is required.

Revisions applied:

- Added submitted-only evaluation creation, submitted timestamp preservation, and immutable submitted artifact fields.
- Added deterministic 422 handling for duplicate application/provider identity collisions.
- Added recursive PII/secret rejection with `contact_email` as the only allowed email field.
- Added dataset/report reference prefix and length constraints.
- Added explicit applicant-kind, dependency, and no-draft-regression guidance.

### Round 2 - Drift, Dependency Consistency, And Contract Specificity

Findings:

1. `evaluation_profile` remained mutable after submission even though it can influence later evaluation intake.
2. Evaluation request bodies could drift `requested_provider_id` away from the application if the field were accepted from callers.
3. `homepage_url` and `openapi_url` lacked scheme constraints; local paths or unsupported schemes could enter the contract.
4. `benchmark_suite` reused no explicit pattern and could be confused with provider IDs.
5. AC numbering drifted after round 1 and task mappings needed alignment.
6. Dataset refs had prefixes but no equivalent rule was pinned for `report_ref`.
7. The story allowed global fallback for evaluation source applications but did not explicitly say the copied application provider ID must be used.
8. OpenAPI unsafe-field coverage needed to include provider-application schemas, not only revenue-share schemas.
9. The story left a path for implementation to add a validator dependency even though existing project patterns favor local Pydantic validators.
10. Scope boundaries did not explicitly rule out emitting queued jobs when status becomes `queued`.

Revisions applied:

- Added URL scheme validation, `evaluation_profile` immutability, and benchmark-suite naming.
- Required evaluation rows to copy `requested_provider_id` from the resolved application row.
- Re-aligned AC task mappings and clarified OpenAPI unsafe-field coverage.
- Preserved no-new-dependency guidance and intake-only behavior.

### Round 3 - Closure, Side Effects, And Status Invariants

Findings:

1. Existing application rows could be moved across tenant scope by upsert if tenant immutability was not specified.
2. Evaluation request status allowed `queued`, but the story did not explicitly forbid actual queue/event side effects.
3. Evaluation requests could be edited after being marked `queued` or `cancelled`, weakening auditability before later worker stories.
4. Test coverage did not explicitly include tenant immutability or queued/cancelled material immutability.
5. AC numbering and task coverage needed one more alignment pass after new closure requirements.
6. The story did not explicitly state `queued` is only recorded state in this story.
7. "No side effects" covered catalog/revenue tables but not worker queue side effects.
8. The story did not state whether global fallback application reads can be used to create tenant-scoped evaluation rows. The intended behavior is allowed but must copy the resolved application identity.
9. A future implementation might mark the story done before merge/sync unless the final status rule remains explicit.
10. Existing 7.A regression preservation still needed to remain part of gates.

Revisions applied:

- Added tenant immutability for application rows.
- Added no queue/job/event side-effect rule for `queued`.
- Added queued/cancelled evaluation material immutability and tests.
- Re-aligned task mappings and retained post-merge-only done rule.
