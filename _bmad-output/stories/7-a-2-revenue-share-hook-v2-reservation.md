---
story_key: 7-a-2-revenue-share-hook-v2-reservation
baseline_commit: 12b94ea088ac307a87fe7f01acd2d3e9be92fe5d
epic_num: 7
story_num: A.2
epic_name: Provider Interface Reservation + revenue-share v2 hook
status: code-review
priority: High
type: revenue-share schema and contract reservation
created_by: bmad-create-story
created_at: 2026-06-01
sources:
  - _bmad-output/planning/epics.md (Epic 7.A / Story 7.A.2)
  - _bmad-output/planning/architecture.md (C4, service catalog, v2 revenue-share boundary)
  - _bmad-output/planning/prd.md (Provider P6/P8 v2, cost redline, v1 non-goals)
  - _bmad-output/stories/7-a-1-capability-registry-v1-schema.md
  - apps/capability-registry/src/capability_registry/models.py
  - apps/capability-registry/src/capability_registry/schemas.py
  - apps/capability-registry/src/capability_registry/routes.py
  - infra/local-init/14-capability-registry.sql
  - apps/billing-service/src/billing_service/models.py
  - infra/local-init/03-billing-schema.sql
---

# Story 7.A.2 - Revenue-Share Service v2 hook reservation

Status: code-review

## Story

**As** the OptiCloud platform team,
**I want** a strict-minimal revenue-share hook reserved in the capability-registry contract,
**so that** v2 can enable monthly provider revenue share without changing v1 provider/capability identifiers, billing references, or database shape.

## Context

Epic 7.A is a v1 interface reservation epic, not a Provider Marketplace implementation. The source AC for 7.A.2 is explicit: "Given v1 仅 schema + DB foreign key 预留 / When v2 启用时 / Then `revenue_share` 表 schema 不变直接用." Architecture C4 reserves a future Revenue-Share Service for v2, while the service catalog says `revenue-share-service` is not a v1 deployable unit.

Story 7.A.1 created `apps/capability-registry` with provider, capability, OAuth stub, multi-tenant scope semantics, internal write auth, Redis cache, OpenAPI generation, and CI. This story extends that existing service as a hook reservation only. It must not create a new service, not compute payouts, and not alter live billing charge semantics.

Billing's current ledger is owned by `apps/billing-service`. `saga_instances.payload_ref` stores pointers only, while monetary amounts live in `credit_transactions`. 7.A.2 may reserve references to future billing/ledger rows or external charge IDs, but it must not write billing rows, derive monthly payout amounts, or couple billing-service to capability-registry.

## Scope

1. Extend `infra/local-init/14-capability-registry.sql` with idempotent revenue-share hook tables.
2. Add SQLAlchemy models and Pydantic schemas under `apps/capability-registry`.
3. Add internal-only API routes for future v2 usage:
   - `PUT /v1/revenue-share/policies/{policy_id}`
   - `GET /v1/revenue-share/policies/{policy_id}`
   - `GET /v1/revenue-share/policies?tenant_id=&provider_kind=`
   - `POST /v1/revenue-share/hooks`
   - `GET /v1/revenue-share/hooks/{hook_id}`
   - `GET /v1/revenue-share/hooks?tenant_id=&provider_id=&k_algo=&period_month=`
4. Add OpenAPI generation/drift coverage through the existing capability-registry spec.
5. Add focused tests for schema idempotence, FK integrity, API behavior, security, and drift-sensitive field names.
6. Preserve all 7.A.1 provider/capability/OAuth behavior and existing tests.

## Out Of Scope

- Creating `apps/revenue-share-service`, deployment config, worker jobs, cron, queues, or payout processors.
- Computing monthly revenue share, provider revenue, pending payout, invoices, tax forms, or settlement files.
- Implementing Provider Console views, provider KPI dashboards, route share dashboards, or marketplace onboarding.
- Changing billing-service charge/reserve/finalize/refund behavior, credit ledger semantics, pricing, invoices, or cost attribution.
- Adding FK constraints into billing-service tables from capability-registry.
- Reading or storing raw payment provider data, bank details, tax IDs, API keys, OAuth tokens, or payout credentials.
- Implementing 7.B P1-P8, 6.C auto-migration/provider exit notification, or any traffic routing/shadow validation logic.
- Caching revenue-share rows unless a future story explicitly needs it; correctness and contract stability matter more than cache speed here.

## Acceptance Criteria

1. `infra/local-init/14-capability-registry.sql` idempotently creates `revenue_share_policies` and `revenue_share_hooks` without requiring any billing-service migrations.
2. `revenue_share_policies` stores v2 policy templates with columns: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `tenant_id UUID NULL`, `policy_id VARCHAR(64) NOT NULL`, `provider_kind VARCHAR(32) NOT NULL`, `platform_share_ratio NUMERIC(7,6) NOT NULL`, `provider_share_ratio NUMERIC(7,6) NOT NULL`, `status VARCHAR(32) NOT NULL DEFAULT 'reserved'`, `effective_from TIMESTAMPTZ NULL`, `effective_until TIMESTAMPTZ NULL`, `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`, `created_at`, `updated_at`.
3. `revenue_share_policies.provider_kind` is constrained to the 7.A.1 provider kinds: `self`, `open_source`, `external`, `commercial`.
4. Policy ratio constraints require both ratios between `0` and `1`, and require `platform_share_ratio + provider_share_ratio = 1.000000`.
5. The default global policy reservations match PRD P8 semantics: `self = 1.000000/0.000000`, `open_source = 1.000000/0.000000`, `external = 0.600000/0.400000`, `commercial = 0.500000/0.500000`. These may be seed rows or test fixtures, but the API must be able to persist them exactly.
6. Policy uniqueness handles `tenant_id NULL` correctly using partial unique indexes or equivalent: one global active/reserved policy per `(policy_id)` and one tenant policy per `(tenant_id, policy_id)`.
7. Policy time validity is guarded: if both effective fields are present, `effective_until > effective_from`.
8. `revenue_share_hooks` stores immutable event-like hook rows with columns: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `tenant_id UUID NULL`, `provider_id VARCHAR(64) NOT NULL`, `k_algo VARCHAR(64) NOT NULL`, `policy_id VARCHAR(64) NOT NULL`, `source_service VARCHAR(64) NOT NULL`, `source_event_id UUID NOT NULL`, `billing_saga_id UUID NULL`, `billing_ledger_id UUID NULL`, `period_month CHAR(7) NOT NULL`, `gross_amount_ref VARCHAR(128) NULL`, `currency CHAR(3) NOT NULL DEFAULT 'CNY'`, `status VARCHAR(32) NOT NULL DEFAULT 'reserved'`, `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`, `created_at`.
9. Hook rows reference provider and capability identity through existing capability-registry tables. Service validation must ensure the `provider_id` exists in the requested tenant scope or global scope, and `k_algo` exists and resolves to the same provider.
10. The database reserves FK relationships where local-table constraints are safe: hook `provider_id/k_algo` integrity may be service-layer enforced because existing provider/capability uniqueness is partial by tenant scope, but source-event idempotency must be database-enforced.
11. `source_event_id` is idempotent per `source_service`: duplicate `(source_service, source_event_id)` submissions return the original hook and do not create another row.
12. `period_month` is strict `YYYY-MM` and must reject invalid months such as `2026-00`, `2026-13`, `2026-1`, or free text.
13. Hook and policy status values are reservation-only: policies allow `reserved`, `active`, `deprecated`; hooks allow `reserved`, `captured`, `voided`. No status transition side effects are implemented.
14. API request bodies must not accept computed payout fields such as `provider_amount`, `platform_amount`, `payout_status`, `paid_at`, `settlement_id`, or bank/tax/payment credential fields.
15. API responses expose only references and ratios; they must not expose raw billing payloads, payment references, user PII, API keys, JWTs, OAuth tokens, provider secrets, bank details, or tax IDs.
16. `POST /v1/revenue-share/hooks` is write-protected by the same `X-Internal-Service-Auth` mechanism as other capability-registry writes when `CAPABILITY_REGISTRY_INTERNAL_SECRET` is configured.
17. Policy `PUT` routes are also internal-write protected; reads may remain internal-service routes but do not require auth in dev mode, matching 7.A.1 behavior.
18. Path/body ID mismatch returns 422 for `policy_id`; invalid path IDs and invalid provider/capability IDs return 422 before database errors.
19. Missing provider, missing capability, provider/capability mismatch, or missing policy returns 422 with a deterministic error detail; missing read resources return 404.
20. The new routes are included in `packages/shared-ts/openapi/capability-registry.json`, and `scripts/check_openapi_drift.py` detects drift.
21. Capability-registry tests cover: schema repeated application, policy ratio constraints, partial unique behavior for global vs tenant policies, default PRD P8 policy ratios, hook creation, hook idempotency replay, tenant/global resolution, provider/capability mismatch, invalid period month, forbidden computed payout fields, internal write auth, OpenAPI unsafe-field absence, and existing 7.A.1 regressions.
22. `.github/workflows/ci.yml` continues to run `capability-registry-test` for `apps/capability-registry/**` and `infra/local-init/14-capability-registry.sql`; no new CI service job is added.
23. Local gates pass: `uv run pytest apps/capability-registry/tests/ -v`, `uv run mypy apps packages`, `uv run ruff check apps/capability-registry`, `uv run ruff format --check apps/capability-registry`, `uv run python scripts/generate_openapi.py`, `uv run python scripts/check_openapi_drift.py`, and `git diff --check`.
24. Implementation record includes post-implementation code review findings and fixes.
25. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done`.

## Tasks / Subtasks

- [x] T1: Extend schema and models for revenue-share reservation (AC: 1-13)
  - [x] Add idempotent policy and hook table DDL to `infra/local-init/14-capability-registry.sql`.
  - [x] Add SQLAlchemy models for `RevenueSharePolicy` and `RevenueShareHook`.
  - [x] Keep schema local to capability-registry; do not modify billing-service schema.

- [x] T2: Add request/response schemas and validation (AC: 2-19)
  - [x] Add Pydantic policy and hook schemas with strict ID, ratio, period, and forbidden-field validation.
  - [x] Ensure computed payout/payment/credential fields are rejected by `extra="forbid"` and explicit validators.
  - [x] Keep response payloads reference-only.

- [x] T3: Add internal API routes (AC: 9-19)
  - [x] Add policy upsert/read/list routes.
  - [x] Add hook create/read/list routes.
  - [x] Reuse existing internal write auth and provider/capability scope helpers.
  - [x] Implement hook idempotency replay by `(source_service, source_event_id)`.

- [x] T4: Add tests and OpenAPI contract coverage (AC: 20-23)
  - [x] Extend capability-registry API/schema tests for policy and hook behavior.
  - [x] Add OpenAPI unsafe-field absence assertions.
  - [x] Regenerate checked-in capability-registry OpenAPI.
  - [x] Run focused gates and preserve existing 7.A.1 tests.

- [ ] T5: Review, gates, and GitHub sync (AC: 24-25)
  - [x] Run post-implementation code review and fix findings.
  - [x] Run local gates after fixes.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [ ] Mark story and sprint status `done` only after merge/sync.

## Dev Notes

### Service Boundary

- The implementation belongs in `apps/capability-registry`, extending the service created in 7.A.1.
- Do not add `apps/revenue-share-service`; Architecture v2.1 drift fix D1 explicitly removed premature revenue-share deployable entries from the v1 service tree.
- Do not import billing-service code into capability-registry. Billing references in this story are opaque UUID/string pointers.
- Do not switch solver-orchestrator or billing-service to call the new hook. This story only creates the future-compatible receiving contract.

### Data Model Guidance

- Use the same tenant semantics as 7.A.1: `tenant_id NULL` is global, non-null is tenant-scoped. Global and tenant rows with the same ID may coexist.
- Use partial unique indexes for nullable tenant uniqueness. A plain `(tenant_id, policy_id)` unique index is insufficient for global uniqueness.
- Policy ratios are decimal fixed precision, not floats. Use Pydantic `Decimal` and SQL `NUMERIC(7,6)`.
- Treat hook rows as append-only/idempotent records. Do not add mutable payout lifecycle fields.
- `source_service` should be a short producer name such as `billing-service` or `solver-orchestrator`; `source_event_id` is the producer's idempotency/event pointer.
- `billing_saga_id` and `billing_ledger_id` are nullable UUID pointers only. They do not create cross-service DB ownership.
- `gross_amount_ref` is a pointer/reference label only; do not store actual gross amount, net amount, payout amount, or ledger body in this table.
- `period_month` is a UTC accounting bucket string (`YYYY-MM`) and not a timestamp. Month validity must be tested.

### API Guidance

- Follow existing route style in `capability_registry.routes`: FastAPI router, `Path(pattern=...)`, `Query`, service-layer validation, `HTTPException` for deterministic 404/422/401 behavior.
- `PUT /v1/revenue-share/policies/{policy_id}` should be deterministic upsert. Path ID is authoritative; body `policy_id` may be omitted or must match.
- `POST /v1/revenue-share/hooks` should return the existing hook for duplicate `(source_service, source_event_id)` submissions even if the duplicate payload repeats the same event. Do not create a second hook.
- If a duplicate source event arrives with conflicting reference fields, return the original hook rather than mutating it. This story reserves idempotency, not reconciliation.
- List routes should support narrow filters but do not need pagination in v1 reservation.

### Previous Story Intelligence

- 7.A.1 established strict path validation after review found invalid path IDs could fall through to DB constraints. Apply `Path(pattern=...)` from the start.
- 7.A.1 intentionally split request and response schemas when response shape differs from request shape. Do the same if hook responses include derived `policy` or scope fields.
- 7.A.1 OpenAPI and Windows console fixes mean generation scripts should stay ASCII in terminal output.
- Existing capability-registry tests already apply `14-capability-registry.sql` twice. Extend that pattern rather than creating a separate migration test harness.

### Testing Guidance

- The first implementation task should add failing tests for the DDL/API behavior before code changes.
- Keep tests in `apps/capability-registry/tests/test_api.py` unless size forces a new focused file.
- Preserve `FakeCache` behavior; revenue-share routes do not need Redis cache tests.
- Tests should explicitly query DB constraints for ratio and uniqueness, not only API validation.
- Include OpenAPI JSON assertions that forbidden terms are not schema properties: `provider_amount`, `platform_amount`, `payout_status`, `paid_at`, `settlement_id`, `bank_account`, `tax_id`, `access_token`, `refresh_token`, `client_secret`.

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
- Implementation satisfies every Acceptance Criterion without implementing 7.B Provider Marketplace or v2 payout computation early.
- Existing provider/capability/OAuth behavior from 7.A.1 remains compatible.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/7-a-2-revenue-share-hook-v2-reservation`.
- Baseline commit: `12b94ea088ac307a87fe7f01acd2d3e9be92fe5d`.
- Focused capability-registry tests: `uv run pytest apps/capability-registry/tests/ -v` -> 13 passed.
- Type gate: `uv run mypy apps packages` -> passed.
- Lint/format gates: `uv run ruff check apps/capability-registry` and `uv run ruff format --check apps/capability-registry` -> passed.
- OpenAPI gates: `uv run python scripts/generate_openapi.py` and `uv run python scripts/check_openapi_drift.py` -> passed.
- Whitespace gate: `git diff --check` -> passed.

### Completion Notes List

- Added revenue-share v2 reservation tables, models, schemas, and internal API routes inside capability-registry only.
- Added decimal ratio validation, tenant/global policy uniqueness, source-event hook idempotency, reference-only hook payloads, and forbidden payout/payment field rejection.
- Extended capability-registry tests to preserve 7.A.1 behavior and cover 7.A.2 schema/API/security/OpenAPI expectations.
- Fixed OpenAPI drift tooling so it can compare generated specs from a temporary output directory without mutating checked-in files.
- Post-implementation review findings fixed: recursive metadata sensitive-key rejection and concurrent source-event idempotency replay after unique-index races.

### File List

- `_bmad-output/stories/7-a-2-revenue-share-hook-v2-reservation.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/capability-registry/src/capability_registry/models.py`
- `apps/capability-registry/src/capability_registry/routes.py`
- `apps/capability-registry/src/capability_registry/schemas.py`
- `apps/capability-registry/tests/test_api.py`
- `infra/local-init/14-capability-registry.sql`
- `packages/shared-ts/openapi/capability-registry.json`
- `scripts/generate_openapi.py`
- `scripts/check_openapi_drift.py`

## Change Log

- 2026-06-01 - Story created for revenue-share v2 hook reservation.
- 2026-06-01 - Implemented revenue-share hook reservation schema/API/tests/OpenAPI draft; story moved to code-review.
- 2026-06-01 - Completed post-implementation review fixes and local quality gates; awaiting GitHub sync.

## Post-Implementation Code Review

### Findings

- [x] [Review][Patch] Revenue-share request schemas rejected forbidden payout/payment fields only at the top level. A caller could put `payment_ref`, `api_key`, `email`, or similar sensitive keys inside `metadata` and receive them back in responses. Fixed by recursively rejecting forbidden revenue-share keys in nested dict/list metadata, with regression coverage.
- [x] [Review][Patch] Hook idempotency checked for an existing `(source_service, source_event_id)` before insert, but a concurrent duplicate could still hit the database unique index and surface an `IntegrityError`. Fixed hook creation with a nested transaction and post-conflict readback so duplicate source events replay the original hook, with regression coverage.

### Outcome

Changes requested internally; all findings fixed and local gates passed.

## Pre-Implementation Adversarial Review

### Round 1 - Boundary, Data Consistency, And Executability

Findings:

1. Initial scope could be misread as permission to create `apps/revenue-share-service`, but architecture v2.1 says the service is v2-only and absent from v1 deployables.
2. A plain unique index on nullable `tenant_id` would not prevent duplicate global policy IDs.
3. Ratio semantics could drift if stored as floats or if only one side of the split is stored.
4. Hook references to billing could become cross-service coupling if FKs point into billing tables.
5. The source AC says "schema + DB foreign key reservation", but existing provider/capability partial uniqueness makes some local FKs unsafe or overcomplicated.

Revision after Round 1:

- Locked implementation to capability-registry only, required partial unique indexes, required exact decimal platform/provider ratios summing to `1.000000`, kept billing references as opaque pointers, and clarified service-layer integrity where tenant-aware FK constraints are not safe.

### Round 2 - Scope Drift, Dependency Consistency, And Closure

Findings:

1. Hook creation could accidentally become revenue computation by storing `provider_amount`, `platform_amount`, or payout lifecycle fields.
2. Duplicate source events need idempotency; otherwise future billing retries could double-capture hooks.
3. Tenant/global resolution must match 7.A.1 or the hook can attach to the wrong provider/capability.
4. Policy defaults for PRD P8 could drift from self/open-source/cooperation/commercial semantics.
5. List/read routes and OpenAPI expectations were needed for v2 service codegen readiness.

Revision after Round 2:

- Added forbidden computed payout/payment fields, `(source_service, source_event_id)` idempotency replay, provider/capability tenant-scope validation, explicit PRD P8 default ratio coverage, read/list route contracts, and OpenAPI drift requirements.

### Round 3 - Security, Idempotence, Testability, And GitHub Closure

Findings:

1. Internal write protection must cover both policy upsert and hook creation, not only hook creation.
2. Invalid `period_month` values are easy to accept with a regex-only `YYYY-MM` check unless month bounds are tested.
3. OpenAPI could expose forbidden payout/payment fields even if runtime validators reject them.
4. Existing 7.A.1 tests must remain in the same suite to prevent provider/OAuth regressions.
5. Story completion could be marked too early unless GitHub CI, merge, branch deletion, and local main sync are explicit gates.

Revision after Round 3:

- Added policy write auth, strict month validation examples, unsafe-field OpenAPI assertions, existing-regression preservation in test ACs, and GitHub merge/sync as the final done gate.
