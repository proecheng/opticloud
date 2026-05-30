---
story_key: 5-a-0b-saga-contract-fixtures
epic_num: 5
story_num: A.0b
epic_name: Billing — Credits & Saga
status: done
priority: 🔴 Critical (N5 unlock continuation; blocks 5.A.0c cross-epic dry-run and hardens Epic 0/3/5.A ownership boundary)
sizing: M (4-6 hours; shared fixture catalog + validators + cross-epic contract tests)
type: testing + contract fixtures
created_by: bmad-create-story
created_at: 2026-05-30
sources:
  - _bmad-output/planning/epics.md (Story 5.A.0b; Story M2.2a dependency on 5.A.0b fixtures)
  - _bmad-output/stories/5-a-0a-saga-implementation.md (DB-backed SagaOrchestrator and 7-state stop point)
  - docs/adr/0001-saga-pattern.md (Hybrid Saga; transition matrix; test pyramid)
  - _bmad-output/planning/architecture.md (P31/P47 idempotency; P33/P56 outbox; Concern #13 distributed billing transaction)
  - _bmad-output/planning/prd.md (FR B1/B2/B4/B6/B9; POST Idempotency-Key 24h contract)
  - _bmad-output/stories/m2-2a-billing-critical-tests.md (55 critical scenarios; S1 cross-tenant key fix)
  - _bmad-output/stories/m2-2b-saga-property-tests.md (Hypothesis random walks; orchestrator-only ledger semantics)
  - apps/billing-service/src/billing_service/saga_orchestrator.py
  - packages/shared-py/opticloud_shared/saga/state_machine.py
dependencies:
  upstream:
    - 5-a-0a-saga-implementation (done) — SagaOrchestrator exists and imports shared state machine
    - m2-2a-billing-critical-tests (done) — critical scenario taxonomy and security fix
    - m2-2b-saga-property-tests (done) — DB-backed random walk pattern
    - m3-2-contract-test-framework (done) — contract test folder and module snapshot pattern
  downstream:
    - 5-a-0c-saga-cross-epic-dryrun — consumes these fixtures for owner alignment
    - 5-a-0-saga-implementation — uses fixture catalog as acceptance guardrail
    - m2-2a/m2-2b/m2-2c successors — reuse fixture categories instead of duplicating cases
    - Epic 3 solver billing integration — reserves/finalizes against canonical fixture semantics
---

# Story 5.A.0b — Saga Contract Fixtures

## User Story

**As** Billing Architect + Solver Lead + Foundation Test Owner  
**I want** a shared, deterministic Saga contract fixture catalog covering Epic 0/3/5.A boundaries  
**so that** downstream Saga implementation and cross-epic dry-runs cannot split ownership, drift state semantics, or silently create billing ledger inconsistencies.

## Why This Story

5.A.0a delivered a DB-backed Saga engine, and M2.2a/M2.2b added critical/property coverage. What is still missing is a reusable fixture contract that all future Epic 0/3/5.A tests can import. Without it, billing-service, solver-orchestrator, and generic contract tests can each invent their own scenario shapes, which reopens drift around idempotency, ledger sign, outbox payloads, and cost telemetry placeholders.

This story creates the canonical fixtures only. It does not change production Saga behavior.

## Out of Scope

- Adding or changing Saga states/transitions in `opticloud_shared.saga.state_machine`.
- Changing billing-service routes, charge/reserve/finalize behavior, ledger writes, reconciler behavior, solver billing calls, or database schema.
- Adding a new external dependency or making Hypothesis a runtime dependency.
- Adding live network, Redis, Docker, K8s, or scheduler behavior.
- Implementing `paused_by_budget`; this story records it as an explicit gap/stub contract for 5.D.5/5.A follow-up because current 5.A.0a shipped the 7-state ADR-0001 machine.

## Acceptance Criteria

### AC1: Shared Saga fixture module

- Add `packages/shared-py/opticloud_shared/saga/contract_fixtures.py`.
- Public exports include:
  - `SAGA_CONTRACT_VERSION`
  - `SagaFixtureStep`
  - `SagaContractFixture`
  - `SagaFixtureManifest`
  - `CONTRACT_FIXTURE_MANIFEST`
  - `build_saga_contract_fixtures()`
  - `canonical_body_hash()`
  - `validate_contract_fixture_manifest()`
- The module imports the existing `State`, `Transition`, `Compensation`, and `TRANSITIONS` definitions from `opticloud_shared.saga`; it must not duplicate the transition matrix.
- Runtime code must use stdlib + existing runtime dependencies only. Hypothesis may appear only in tests.

### AC2: 50+ deterministic fixtures

- `CONTRACT_FIXTURE_MANIFEST.fixtures` contains at least 50 fixtures.
- Minimum category coverage:
  - `charge`: at least 10 fixtures
  - `refund`: at least 8 fixtures
  - `rollback`: at least 8 fixtures
  - `idempotency`: at least 8 fixtures
  - `timeout`: at least 8 fixtures
  - `cost_telemetry`: at least 8 fixtures
  - `budget_pause_stub`: at least 2 fixtures documenting the current `paused_by_budget` gap without executing unsupported transitions
- Every executable fixture uses only transitions present in `TRANSITIONS`.
- Every fixture ID, UUID, idempotency key, timestamp, amount, and payload pointer is deterministic across processes and platforms.

### AC3: Schema validation and data-safety rules

- `validate_contract_fixture_manifest()` raises `ValueError` with actionable messages if:
  - fixture IDs are duplicated
  - category minimums are not met
  - an executable step does not match the shared transition matrix
  - expected outbox count or ledger delta is inconsistent with the executable steps
  - payload refs include money, PII, secrets, auth tokens, API keys, raw prompt/input payloads, or non-pointer data
  - idempotency fixtures fail to encode same-key/same-body replay or same-key/different-body conflict semantics
- `canonical_body_hash()` follows the 5.A.0a `hash_body()` shape: stable JSON with sorted keys and compact separators over `{saga_type, payload, amount}`.
- The fixture manifest must not contain real phone numbers, emails, names, addresses, API keys, bearer tokens, bank data, or ID-card-like values.

### AC4: Billing-service consumes executable fixtures

- Add `apps/billing-service/tests/test_saga_contract_fixtures.py`.
- Parametrize over executable fixtures from `CONTRACT_FIXTURE_MANIFEST`.
- For each executable fixture:
  - start a Saga through `SagaOrchestrator.start()`
  - apply fixture steps in order
  - assert final state, ledger delta, and outbox event count
- Test keys may be runtime-namespaced to avoid stale DB collisions, but fixture payloads, amounts, expected states, and transitions must be used unchanged.

### AC5: Cross-epic contract snapshot/stub

- Add a module-level contract test under `tests/contract/` proving the fixture manifest is importable without billing-service imports, DB, Redis, network, or secrets.
- The contract test locks:
  - public export names
  - contract version
  - minimum total count
  - required category minimums
  - deterministic validation result
- This is a stub for 5.A.0c; it must not start services or call HTTP endpoints.

### AC6: Package export and backward compatibility

- Re-export fixture helpers from `packages/shared-py/opticloud_shared/saga/__init__.py`.
- Existing imports from `opticloud_shared.saga` must remain backward compatible.
- No existing production route, model, migration, pricing function, reconciler, solver billing client, or UI file may change.

### AC7: Quality gates

Run before commit:

```powershell
$env:PYTHONPATH='packages/shared-py'
uv run pytest packages/shared-py/tests/test_saga_contract_fixtures.py -q

$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'
uv run pytest apps/billing-service/tests/test_saga_contract_fixtures.py -q

$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/billing-service/src'
uv run pytest tests/contract/test_saga_contract_fixtures_contract.py -q

uv run ruff check packages/shared-py apps/billing-service tests/contract
uv run ruff format --check packages/shared-py apps/billing-service tests/contract
uv run mypy packages/shared-py
```

## Tasks / Subtasks

- [x] T1: Add shared fixture models and deterministic fixture builder
  - [x] Define Pydantic models for manifest, fixture, and step schema.
  - [x] Build 50+ fixtures from deterministic category specs.
  - [x] Implement canonical hash and validation helpers.
- [x] T2: Add shared-py tests
  - [x] Verify count/category coverage.
  - [x] Verify transition matrix parity and no duplicated IDs.
  - [x] Verify canonical hash determinism and no PII/secrets/amounts in payload refs.
  - [x] Verify ledger/outbox expectations.
- [x] T3: Add billing-service executable fixture tests
  - [x] Parametrize executable fixtures.
  - [x] Run through SagaOrchestrator and assert final state, ledger delta, outbox count.
  - [x] Exclude `budget_pause_stub` from execution and assert it remains documented as a gap.
- [x] T4: Add cross-epic contract stub
  - [x] Add `tests/contract/test_saga_contract_fixtures_contract.py`.
  - [x] Lock version, exports, category minimums, and validation result.
- [x] T5: Export helpers and run quality gates
  - [x] Update `opticloud_shared.saga.__init__`.
  - [x] Run focused tests and quality gates from AC7.
  - [x] Update sprint/story status and Dev Agent Record.

## Developer Notes

### Existing patterns to reuse

- `packages/shared-py/opticloud_shared/saga/state_machine.py` is the single source of truth for Saga states and transitions.
- `billing_service.saga_orchestrator.hash_body()` uses sorted, compact JSON. `canonical_body_hash()` must match that shape without importing billing-service.
- Billing-service tests use a session-scoped Postgres engine and a shared `test_user_id`; runtime idempotency keys should be made unique in DB tests to avoid collisions across repeated local runs.
- `tests/contract/` already has module-contract precedent from the AIGC filter snapshot. Keep this story's contract test static and offline.

### Fixture semantics

- Orchestrator-level ledger signs:
  - `service_success`: `-amount`
  - `user_cancel`: `+amount`
  - `downstream_reject_late`: `+amount`
  - all other current triggers: `0`
- Therefore `reserve -> service_success -> downstream_reject_late` nets to `0`.
- HTTP route-level `refund_partial` and `refund_reversal` are outside this fixture module; do not encode route-only compensation rows as orchestrator steps.
- `cost_telemetry` fixtures must include a schema-only placeholder object, not import or call the cost telemetry package.

### Boundary rules

- Do not edit `state_machine.py` in this story.
- Do not edit `saga_orchestrator.py` except if a fixture test reveals a direct contract bug that must be fixed to make an existing accepted transition executable. If that happens, record the bug and keep the fix minimal.
- Do not add DB migrations.
- Do not add CI workflow jobs unless an existing required test cannot run through current gates.

## Three-Round Pre-Implementation Adversarial Review

### Round 1 — Boundary / Ownership

Findings:
- Risk: fixture story could drift into implementing missing Saga states or changing billing runtime behavior.
- Risk: cross-epic fixture ownership could land in billing-service only, making solver/dry-run consumers copy scenarios later.
- Risk: deterministic fixture IDs may collide with stale test DB rows if used directly.

Revisions applied:
- Added explicit out-of-scope rule forbidding state-machine, route, schema, solver-client, and UI changes.
- Moved canonical fixtures to `packages/shared-py`, with billing-service only consuming them in tests.
- AC4 allows runtime-namespaced idempotency keys in DB tests while keeping fixture payload/amount/state immutable.

### Round 2 — Drift / Data Consistency / Privacy

Findings:
- Risk: payload refs may accidentally include amounts or raw optimization input, violating 5.A.0a pointer-only contract.
- Risk: idempotency fixtures may encode same-key replay too vaguely to catch same-key/different-body conflicts.
- Risk: `paused_by_budget` appears in planning but not in current 7-state implementation, creating hidden drift.

Revisions applied:
- AC3 now rejects money, PII, secrets, auth tokens, raw payloads, and non-pointer payload fields.
- AC3 requires explicit same-key/same-body replay and same-key/different-body conflict semantics.
- AC2 adds `budget_pause_stub` fixtures that document the missing `paused_by_budget` contract without executing unsupported transitions.

### Round 3 — Dependency / Test Closure

Findings:
- Risk: adding Hypothesis to runtime would bloat `opticloud-shared` production dependencies.
- Risk: contract fixtures could require Postgres or billing-service import, making Epic 0/3 consumers brittle.
- Risk: future 5.A.0c dry-run may not know which public API is locked.

Revisions applied:
- AC1 forbids new runtime dependencies; Hypothesis is test-only.
- AC5 requires an offline `tests/contract` stub with no DB, Redis, network, secrets, or billing-service imports.
- AC6 requires re-export from `opticloud_shared.saga.__init__` and backward compatibility.

## Definition of Ready

- ✅ 5.A.0a implementation exists and is done.
- ✅ Shared state machine and transition matrix exist.
- ✅ M2.2a/M2.2b scenario semantics are available.
- ✅ Three adversarial review rounds completed and incorporated.

## Definition of Done

- All ACs pass.
- All tasks/subtasks are checked.
- Story status is `code-review` after implementation and `done` after review fixes.
- `sprint-status.yaml` is synchronized.
- Code review findings are resolved or explicitly documented.
- Branch is pushed and PR is synced to GitHub.

## Dev Agent Record

### Implementation Plan

- Add a service-agnostic shared fixture catalog in `opticloud_shared.saga.contract_fixtures`.
- Keep fixtures deterministic with UUIDv5, fixed UTC timestamps, fixed category minimums, and pointer-only payload refs.
- Validate the manifest both statically in shared-py and dynamically against billing-service's DB-backed `SagaOrchestrator`.
- Add an offline contract test so 5.A.0c can consume the fixture API without DB/service dependencies.

### Debug Log

- 2026-05-30: Started dev-story implementation; story moved to in-progress.
- 2026-05-30: Red phase confirmed missing `opticloud_shared.saga.contract_fixtures` module.
- 2026-05-30: Implemented fixture module, exports, shared tests, billing executable tests, and offline contract stub.
- 2026-05-30: Fixed ruff import ordering/type-shape issues and mypy transition lookup typing.
- 2026-05-30: Post-implementation code review found validator drift gaps; added negative tests and stricter validation for canonical category minimums, step `from_state`, and budget stub side-effect expectations.

### Completion Notes

- Added 52 total fixtures: 50 executable cross-epic Saga fixtures plus 2 non-executable `paused_by_budget` stubs.
- Billing-service now executes all 50 non-stub category fixtures plus one executable idempotency-empty-step fixture set, with 51 parametrized DB-backed checks.
- Contract stub locks the shared fixture API surface for 5.A.0c without importing billing-service or requiring DB/network/secrets.
- Validation run:
  - `uv run pytest packages/shared-py/tests/test_saga_contract_fixtures.py -q` → 11 passed
  - `uv run pytest apps/billing-service/tests/test_saga_contract_fixtures.py -q` → 51 passed
  - `uv run pytest tests/contract/test_saga_contract_fixtures_contract.py -q` → 2 passed
  - `uv run ruff check packages/shared-py apps/billing-service tests/contract` → passed
  - `uv run ruff format --check packages/shared-py apps/billing-service tests/contract` → passed
  - `uv run mypy packages/shared-py` → passed

### File List

- `_bmad-output/stories/5-a-0b-saga-contract-fixtures.md`
- `_bmad-output/stories/sprint-status.yaml`
- `packages/shared-py/opticloud_shared/saga/contract_fixtures.py`
- `packages/shared-py/opticloud_shared/saga/__init__.py`
- `packages/shared-py/tests/test_saga_contract_fixtures.py`
- `apps/billing-service/tests/test_saga_contract_fixtures.py`
- `tests/contract/test_saga_contract_fixtures_contract.py`

### Change Log

- 2026-05-30: Story created with three pre-implementation adversarial review rounds applied.
- 2026-05-30: Implementation started.
- 2026-05-30: Implementation completed and moved to code-review.
- 2026-05-30: Post-review validator hardening completed; story marked done.

## Senior Developer Review (AI)

Outcome: Approved after fixes.

Findings:
- [x] Medium — `validate_contract_fixture_manifest()` trusted caller-supplied `category_minimums`, so a custom manifest could weaken required category coverage and still pass. Fixed by checking against canonical `_CATEGORY_MINIMUMS` and adding `test_validation_rejects_relaxed_category_minimums`.
- [x] Medium — step validation checked trigger and target but not explicit `step.from_state`, allowing a drifted fixture step to misrepresent the transition source. Fixed by validating derived and matrix `from_state`, with `test_validation_rejects_step_from_state_drift`.
- [x] Low — non-executable `budget_pause_stub` fixtures did not explicitly prove zero side-effect expectations. Fixed by validating pending final state, zero ledger delta, zero outbox count, and adding `test_validation_rejects_budget_stub_side_effect_expectations`.

Review layers:
- Blind Hunter: no production runtime mutation found; focused concern was static validator robustness.
- Edge Case Hunter: identified forged manifest and from-state drift risks.
- Acceptance Auditor: AC3 validation requirements now satisfied by negative tests and stricter checks.

Final verification:
- `uv run pytest packages/shared-py/tests/test_saga_contract_fixtures.py -q` → 11 passed
- `uv run pytest apps/billing-service/tests/test_saga_contract_fixtures.py -q` → 51 passed
- `uv run pytest tests/contract/test_saga_contract_fixtures_contract.py -q` → 2 passed
- `uv run ruff check packages/shared-py apps/billing-service tests/contract` → passed
- `uv run ruff format --check packages/shared-py apps/billing-service tests/contract` → passed
- `uv run mypy packages/shared-py` → passed
