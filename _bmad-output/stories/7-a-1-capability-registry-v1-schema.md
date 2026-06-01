---
story_key: 7-a-1-capability-registry-v1-schema
baseline_commit: a9c0d4c
epic_num: 7
story_num: A.1
epic_name: Provider Interface Reservation + capability-registry v1
status: code-review
priority: High
type: capability registry schema and contract foundation
created_by: bmad-create-story
created_at: 2026-06-01
sources:
  - _bmad-output/planning/epics.md (Epic 7.A / Story 7.A.1 / TT2)
  - _bmad-output/planning/architecture.md (Capability Registry backbone, Redis prefixes, service catalog)
  - _bmad-output/planning/prd.md (Provider transparency, R4/R7 v2 boundary, Provider FR P1-P8 v2)
  - _bmad-output/stories/2-6-multi-provider-routing.md
  - _bmad-output/stories/2-8-unaudited-block.md
  - _bmad-output/stories/6-b-7-bitwise-reproducibility-test.md
  - apps/solver-orchestrator/src/solver_orchestrator/catalog.py
  - apps/solver-orchestrator/src/solver_orchestrator/provider_routing.py
  - apps/solver-orchestrator/src/solver_orchestrator/schemas.py
  - scripts/generate_openapi.py
  - .github/workflows/ci.yml
---

# Story 7.A.1 - capability-registry v1 schema

Status: code-review

## Story

**As** the OptiCloud platform team,
**I want** a minimal capability-registry service with Postgres schema, Redis-backed read cache, and provider contract stubs,
**so that** v1 solver/repro/provider code has a stable future-compatible contract without implementing v2 marketplace, auto-migration, or revenue-share logic early.

## Context

Epic 7.A is explicitly "v1 必上 / strict minimal": it reserves provider integration interfaces so v2 work does not hit schema or contract walls. It does not implement Provider Marketplace, shadow validation, traffic promotion, provider console, payout, or automatic voucher migration.

Current solver routing is implemented in `apps/solver-orchestrator/src/solver_orchestrator/catalog.py` as an M1-M2 static catalog. Architecture B1 says M3 introduces `capability-registry` as a service with minimal CRUD and Redis SWR cache, while M5+ adds state machines and prompt-store. This story starts that service but does not make solver-orchestrator depend on it yet.

TT2 adds three required reservations to 7.A.1: multi-tenant schema, OpenAPI/cosign contract fields, and Provider OAuth flow stubs. For this story those are schema and API contract fields only. No real OAuth exchange, cosign verification, Provider admission workflow, revenue computation, or external Provider runtime calls are implemented.

## Scope

1. Add `apps/capability-registry` as a FastAPI service in the uv workspace.
2. Add `infra/local-init/14-capability-registry.sql` with idempotent Postgres schema for providers, capabilities, capability tags, and Provider OAuth flow stubs.
3. Add SQLAlchemy models and Pydantic schemas that preserve the existing public `model_version` shape: `provider_id`, `kind`, `version`, and `provider_url`.
4. Add minimal CRUD/read APIs for providers, capabilities, and OAuth flow stubs.
5. Add Redis read-through cache using the architecture prefix `capability_cache:` with deterministic keys and cache invalidation after writes.
6. Add OpenAPI generation support and checked-in `packages/shared-ts/openapi/capability-registry.json`.
7. Add focused unit/API/schema tests and a CI job for `capability-registry`.
8. Preserve solver-orchestrator static routing behavior; no production caller switches to the new service in this story.
9. Add concrete route contracts:
   - `GET /v1/providers`, `GET /v1/providers/{provider_id}`, `PUT /v1/providers/{provider_id}` with optional `tenant_id` query/body scope
   - `GET /v1/capabilities`, `GET /v1/capabilities/{k_algo}`, `PUT /v1/capabilities/{k_algo}` with optional `tenant_id` query/body scope
   - `GET /v1/providers/{provider_id}/oauth-flow`, `PUT /v1/providers/{provider_id}/oauth-flow`, `POST /v1/providers/{provider_id}/oauth-flow/execute`

## Out Of Scope

- Auto-migration to equivalent Provider, 30-day provider exit notification, equivalent matching, or voucher rerun behavior from Epic 6.C.
- Provider Marketplace v2 features: provider application workflow, shadow validation, traffic ramp, provider console, provider KPIs, provider payouts, provider version submission, or provider public API.
- Revenue-share table or computation. Story 7.A.2 owns the v2 revenue-share hook.
- Prompt-store, provider health dashboard, status page automation, or incident fallback automation.
- Real OAuth authorization-code exchange, token storage, refresh, or user consent screens.
- Real cosign signature verification, Docker image pull, SBOM attestation, or registry access.
- Replacing `solver_orchestrator.catalog.CATALOG`, changing `select_provider_route(...)`, or changing `/v1/algorithms` behavior.
- Browser UI, Storybook work, or packages/ui components.

## Acceptance Criteria

1. `apps/capability-registry` is a uv workspace member with FastAPI app, config, DB session, routes, schemas, models, and tests.
2. The service exposes `/healthz`, `/readyz`, `/metrics`, `/`, and `/openapi.json` consistently with existing Python services.
3. `infra/local-init/14-capability-registry.sql` is idempotent and creates provider/capability tables without requiring data from solver-orchestrator.
4. Provider schema includes `provider_id`, `kind` (`self`, `open_source`, `external`, `commercial`), `display_name`, `provider_url`, status, optional `tenant_id`, OpenAPI URL/SHA-256 fields, image digest, and cosign verification stub fields.
5. Provider OpenAPI SHA-256, image digest, and cosign bundle fields are validation-safe strings: malformed hashes/digests return 422 rather than being accepted silently.
6. Capability schema includes `k_algo`, `task_type`, `tier`, status, `provider_id`, `model_version`, `supported_solvers`, descriptions, examples, metadata, optional `tenant_id`, and timestamps.
7. Capability `model_version` is derived consistently from capability/provider columns (`provider_id`, provider `kind`, capability `model_version`, provider `provider_url`) in responses; request bodies must not be able to persist a conflicting `model_version` object.
8. Capability rows must reference an existing provider in the same tenant scope or the global scope. A tenant-scoped capability may use either a same-tenant provider or a global provider; tests must cover both.
9. Capability tag schema supports future R4/R7 matching vocabulary without implementing matching: tags are normalized to lowercase slug-like strings and unique per capability.
10. Multi-tenant reservation is explicit: `tenant_id = NULL` means global catalog, non-null `tenant_id` means tenant-scoped override; Postgres uniqueness must use partial unique indexes or an equivalent strategy that actually prevents duplicate global rows.
11. Provider OAuth flow stub schema stores only non-secret contract references: authorization URL, token URL, scopes, status, client id reference, and Vault secret reference. Raw client secrets or tokens must not be stored or returned.
12. CRUD APIs support provider upsert/read/list and capability upsert/read/list with deterministic `PUT` semantics: path IDs are authoritative, body IDs may be omitted or must match the path, and mismatches return 422.
13. Read APIs resolve scope deterministically: absent `tenant_id` reads only the global row; present `tenant_id` first reads the tenant row and may fall back to the global row only when explicitly documented by response field `scope_source="global_fallback"`.
14. OAuth stub API can create/read provider flow metadata, but `POST /v1/providers/{provider_id}/oauth-flow/execute` returns `501 Not Implemented`.
15. OAuth stub request/response field names must be reference-oriented (`client_id_ref`, `client_secret_ref`, `vault_secret_ref`) and must not contain raw-token field names such as `client_secret`, `access_token`, `refresh_token`, or `authorization_code`.
16. Read APIs use Redis read-through cache with prefix `capability_cache:` when Redis is reachable and degrade to DB-only reads when Redis is unavailable.
17. Write APIs invalidate affected cache keys and never serve stale data after an upsert in the same process/test.
18. Cache invalidation is allowed to be coarse in v1 (`capability_cache:*` deletion/scan) as long as tests prove stale provider, capability, and list reads are not served after writes.
19. Cache payloads must be JSON serializable and must not include SQLAlchemy internals, raw OAuth secrets, API keys, JWTs, or Provider tokens.
20. Write APIs are protected by `X-Internal-Service-Auth` when `CAPABILITY_REGISTRY_INTERNAL_SECRET` is configured; dev mode with an empty secret remains usable for tests.
21. Internal-secret comparison uses constant-time comparison and returns `401` for missing/mismatched headers when a secret is configured.
22. API errors are intentionally simple FastAPI/HTTPException responses for this v1 internal service, but tests must cover 404 for missing resources, 422 for path/body ID mismatch, and 501 for OAuth execution.
23. API responses use the existing public model version key names (`provider_id`, `kind`, `version`, `provider_url`) and do not reintroduce the older `provider_kind` response spelling.
24. The service does not import from `apps/solver-orchestrator` or any other service package; dependency direction remains service-local plus shared packages only.
25. `scripts/generate_openapi.py` can generate `capability-registry.json` alongside existing specs without breaking auth-service generation.
26. `scripts/check_openapi_drift.py` detects drift for the checked-in capability-registry spec.
27. `.github/workflows/ci.yml` path filters run a capability-registry test job for `apps/capability-registry/**` and `infra/local-init/14-capability-registry.sql`.
28. The capability-registry CI job applies `infra/local-init/14-capability-registry.sql`, starts Postgres and Redis services, and runs `uv run pytest apps/capability-registry/tests/ -v`.
29. Root `pyproject.toml` includes `apps/capability-registry` in the uv workspace.
30. Tests cover schema constraints, idempotent schema re-application, API upsert/list/read, tenant/global uniqueness, tenant read fallback semantics, OAuth secret redaction, Redis cache hit/invalidation behavior, Redis-unavailable fallback, and internal-secret write protection.
31. Local gates pass: capability-registry tests, mypy over apps/packages, `scripts/generate_openapi.py`, `scripts/check_openapi_drift.py`, `git diff --check`, and relevant pre-commit hooks.
32. Implementation record includes post-implementation code review findings and fixes.
33. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done`.

## Tasks / Subtasks

- [x] T1: Add capability-registry service skeleton (AC: 1-2, 20)
  - [x] Add `apps/capability-registry/pyproject.toml` and package skeleton.
  - [x] Add FastAPI app, health/ready/metrics, settings, and async DB dependency.
  - [x] Register the app in the root uv workspace.

- [x] T2: Add Postgres schema and service models (AC: 3-11, 18-19)
  - [x] Add idempotent SQL schema under `infra/local-init/14-capability-registry.sql`.
  - [x] Add partial unique indexes for global-vs-tenant provider/capability uniqueness.
  - [x] Add SQLAlchemy models for providers, capabilities, tags, and OAuth flow stubs.
  - [x] Add Pydantic request/response schemas with secret redaction and `model_version` parity.

- [x] T3: Add CRUD APIs and cache behavior (AC: 12-22, 30)
  - [x] Add provider and capability list/read/upsert routes.
  - [x] Add OAuth flow stub read/upsert route and explicit execution `501`.
  - [x] Implement Redis read-through cache with deterministic prefix keys and write invalidation.
  - [x] Add API tests for tenant/global uniqueness, cache hit/invalidation, Redis fallback, and write protection.

- [x] T4: Add OpenAPI and CI integration (AC: 25-29, 31)
  - [x] Extend OpenAPI generation/check scripts for capability-registry.
  - [x] Commit generated `packages/shared-ts/openapi/capability-registry.json`.
  - [x] Add CI job and schema path trigger for capability-registry tests.
  - [x] Run focused tests/static gates.

- [ ] T5: Review, gates, and GitHub sync (AC: 23-24)
  - [x] Run post-implementation code review and fix findings.
  - [x] Run local gates after fixes.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [ ] Mark story and sprint status `done` only after merge/sync.

## Dev Notes

### Service Boundary

- This story creates the service contract and storage foundation only. `solver-orchestrator` must continue using its current static catalog and provider routing helpers.
- `apps/capability-registry` must not import from `apps/solver-orchestrator`, `apps/web`, billing, auth, or chat. If shared logic is needed, prefer package-local types for this story.
- Do not add a new deployable `revenue-share-service`; architecture explicitly defers that to v2 and Story 7.A.2.

### Data Model Guidance

- Preserve the public model version shape already shipped in solver responses: `provider_id`, `kind`, `version`, `provider_url`.
- Use nullable `tenant_id` for the v1 reservation: global rows have `tenant_id NULL`; tenant overrides use a UUID. Tests must prove global and tenant rows with the same `k_algo` can coexist while duplicate rows in the same scope cannot.
- Because Postgres treats `NULL` values as distinct in ordinary unique indexes, use explicit partial unique indexes for global rows (`tenant_id IS NULL`) and tenant rows (`tenant_id IS NOT NULL`). Do not rely on a plain `(tenant_id, k_algo)` unique index for global uniqueness.
- Use `PUT` for upsert. The path identifier is authoritative; body identifiers are optional for ergonomics but must match if provided.
- `tenant_id` is not in the path. Use an optional query parameter for reads and an optional body field for writes. A request with no tenant is global-only. A tenant read may return a global fallback only with explicit `scope_source`.
- Provider existence across "same tenant or global" is difficult to express with a simple foreign key. Enforce this in service-layer validation and tests; DB constraints still own row shape, uniqueness, enum checks, and cascade/delete basics.
- Validate SHA-256 values as lowercase/uppercase hex strings of 64 characters, and validate image digest references as digest-like strings containing `sha256:<64 hex>`.
- Use JSONB for future-flexible fields such as examples, metadata, scopes, and cosign bundle metadata, but keep known contract fields as typed columns.
- OAuth rows store references only. `client_secret_ref` may point to Vault, but no raw `client_secret`, access token, refresh token, or authorization code may appear in DB rows or API responses.
- Avoid raw-secret field names in public Pydantic schemas. Use `*_ref` names and document that values are references such as Vault paths, not secret material.
- Internal service auth should use `secrets.compare_digest(...)` or equivalent constant-time comparison.
- The SQL file must be safe to apply repeatedly to an already-initialized local database. Use `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, `DROP CONSTRAINT IF EXISTS`/guarded constraint blocks where needed, and `CREATE INDEX IF NOT EXISTS`.

### Cache Guidance

- Architecture requires the Redis prefix `capability_cache:`. Do not use a generic `cache:` key for this service.
- Cache keys must include route type and sorted filter parameters to avoid cross-tenant or cross-filter collisions.
- Reads should work without Redis so unit/API tests do not need a live Redis service; that fallback should be visible in tests.
- Writes must invalidate list/detail cache entries that could contain the updated row.
- Coarse invalidation of all `capability_cache:*` keys is acceptable for v1. Prefer correctness and testability over clever per-key dependency tracking.

### OpenAPI / CI Guidance

- `packages/shared-ts/openapi/` may not exist yet; create it as part of this story.
- Keep `generate_openapi.py` backward-compatible for auth-service. Capability generation should add to it, not replace it.
- CI already has a `capability_registry` path-filter output but no dedicated job. Add the job and include `infra/local-init/14-capability-registry.sql` in the filter.
- The capability-registry CI job should mirror existing Python service jobs: setup Python/uv, `uv sync --all-packages --extra dev`, apply schema, run focused tests. It also needs a Redis service because cache behavior is in scope.

### Suggested Commands

```powershell
uv sync --all-packages --extra dev
uv run pytest apps/capability-registry/tests/ -v
uv run mypy apps packages
uv run python scripts/generate_openapi.py
uv run python scripts/check_openapi_drift.py
uv tool run pre-commit run ruff ruff-format --all-files
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Implementation satisfies every Acceptance Criterion without implementing 6.C, 7.A.2, 7.B, or v2 marketplace scope early.
- Existing solver-orchestrator routing and public algorithm catalog behavior remain compatible.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/7-a-1-capability-registry-v1-schema`.
- Baseline commit: `a9c0d4c`.
- Focused capability-registry tests: `uv run pytest apps/capability-registry/tests/ -v` -> 7 passed.
- Type gate: `uv run mypy apps packages` -> passed.
- Lint/format gates: `uv run ruff check apps/capability-registry` and `uv run ruff format --check apps/capability-registry` -> passed.
- OpenAPI gates: `uv run python scripts/generate_openapi.py` and `uv run python scripts/check_openapi_drift.py` -> passed.
- Safety scans: capability-registry OpenAPI has no raw `client_secret`, `access_token`, `refresh_token`, `authorization_code`, or `provider_kind` properties.
- Whitespace gate: `git diff --check` -> passed.

### Completion Notes List

- Added `apps/capability-registry` FastAPI service skeleton with health/readiness/metrics, DB session, models, schemas, routes, and cache helpers.
- Added idempotent capability-registry SQL schema with global/tenant partial unique indexes and OAuth reference-only stub tables.
- Added provider/capability/OAuth API tests covering tenant fallback, cache invalidation, Redis fallback, write auth, ID mismatch, missing resources, schema idempotence, and secret redaction.
- Added OpenAPI generation/drift coverage for capability-registry and checked in generated auth-service/capability-registry OpenAPI specs.
- Added capability-registry CI job with Postgres, Redis, repeated schema application, and focused pytest execution.
- Post-implementation review found and fixed path parameter validation drift: invalid `provider_id`/`k_algo` path values now return 422 before database constraints, with regression coverage.

### File List

- `_bmad-output/stories/7-a-1-capability-registry-v1-schema.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `pyproject.toml`
- `scripts/generate_openapi.py`
- `scripts/check_openapi_drift.py`
- `infra/local-init/14-capability-registry.sql`
- `apps/capability-registry/pyproject.toml`
- `apps/capability-registry/src/capability_registry/__init__.py`
- `apps/capability-registry/src/capability_registry/cache.py`
- `apps/capability-registry/src/capability_registry/config.py`
- `apps/capability-registry/src/capability_registry/db.py`
- `apps/capability-registry/src/capability_registry/main.py`
- `apps/capability-registry/src/capability_registry/models.py`
- `apps/capability-registry/src/capability_registry/routes.py`
- `apps/capability-registry/src/capability_registry/schemas.py`
- `apps/capability-registry/tests/conftest.py`
- `apps/capability-registry/tests/test_api.py`
- `packages/shared-ts/openapi/auth-service.json`
- `packages/shared-ts/openapi/capability-registry.json`
- `uv.lock`

## Change Log

- 2026-06-01 - Story created for capability-registry v1 schema and provider contract reservation.
- 2026-06-01 - Implemented service skeleton, schema, APIs, cache behavior, tests, and CI/OpenAPI integration draft.
- 2026-06-01 - Completed OpenAPI/CI integration, post-implementation review, path validation fix, and local gates; story moved to `code-review` pending GitHub CI/merge/sync.

## Post-Implementation Code Review

### Findings

- [x] [Review][Patch] Path parameters for `provider_id` and `k_algo` were not constrained at the FastAPI layer. Invalid path IDs could reach Postgres CHECK constraints and surface as server errors rather than the story-required 422 validation response. Fixed by adding `Path(pattern=...)` validation to provider, capability, and OAuth routes plus regression assertions for invalid provider/capability paths.
- [x] [Review][Patch] `CapabilityResponse` inherited from `CapabilityUpsertRequest` while overriding `model_version` from a request string to a derived response object. This satisfied runtime shape but failed strict mypy. Fixed by splitting the response schema from the request schema while preserving the public response contract.
- [x] [Review][Patch] OpenAPI drift/check script console output still contained Unicode status symbols that fail on the Windows GBK console. Fixed by replacing those script status messages with ASCII output.

### Outcome

Changes requested internally; all findings fixed and local gates rerun successfully. GitHub sync remains pending, so story status is `code-review`, not `done`.

## Pre-Implementation Adversarial Review

### Round 1 - Boundary, Data Consistency, And Executability

Findings:

1. A plain unique index on `(tenant_id, k_algo)` or `(tenant_id, provider_id)` would not prevent duplicate global rows because Postgres treats `NULL` as distinct.
2. The story named "CRUD/upsert" but did not define route paths or whether path IDs or body IDs were authoritative.
3. Capability `model_version` could drift from provider rows if request bodies persisted a free-form `model_version` object.
4. CI integration was underspecified: the path filter existed, but there was no explicit test job behavior, schema application, or Redis service requirement.
5. OpenAPI/cosign fields were named only as "stub fields"; malformed SHA/digest data could be silently accepted.

Revision after Round 1:

- Added concrete route contracts, deterministic `PUT` semantics, partial unique index guidance for `NULL` tenant scope, response-derived `model_version`, provider reference rules, hash/digest validation requirements, and explicit CI job requirements.

### Round 2 - Scope Drift, Tenant Reads, And Cache Closure

Findings:

1. The read API was ambiguous once global and tenant-scoped rows can share the same `provider_id` or `k_algo`.
2. A DB-only foreign key cannot naturally express "same-tenant provider or global provider" without overcomplicating the v1 schema.
3. Cache invalidation said "affected keys" but did not specify a tractable v1 strategy, inviting stale list/detail reads or overengineering.
4. The API contract did not state whether tenant reads can fall back to global rows, which could produce surprising cross-tenant behavior.
5. Tests did not explicitly require tenant/global fallback coverage.

Revision after Round 2:

- Added `tenant_id` query/body scope semantics, explicit `scope_source` for global fallback, service-layer provider validation, coarse `capability_cache:*` invalidation as acceptable v1 behavior, and tenant fallback test requirements.

### Round 3 - Security, Idempotence, And Closure

Findings:

1. Write protection said "shared secret" but did not require constant-time comparison or specify missing-header behavior.
2. OAuth stub fields could accidentally invite raw secret/token storage if named like real OAuth token fields.
3. Error response expectations were not testable; 404/422/501 needed explicit coverage.
4. The SQL file was called idempotent, but the story did not require testing repeated schema application.
5. Generated OpenAPI could expose unsafe OAuth field names unless the naming rule was explicit.

Revision after Round 3:

- Added constant-time internal secret comparison, `401` behavior, reference-only OAuth field names, explicit 404/422/501 test expectations, repeated schema-application coverage, and SQL idempotence guidance.
