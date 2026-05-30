---
story_key: 5-a-0-saga-implementation
epic_num: 5
story_num: A.0
epic_name: Billing — Credits & Saga
status: done
priority: 🔴 Critical (standard Saga production closure after 5.A.0a/b/c)
type: production hardening + cross-service contract closure
created_by: bmad-create-story
created_at: 2026-05-30
sources:
  - _bmad-output/planning/epics.md (Story 5.A.0 legacy Saga requirement)
  - _bmad-output/stories/5-a-0a-saga-implementation.md
  - _bmad-output/stories/5-a-0b-saga-contract-fixtures.md
  - _bmad-output/stories/5-a-0c-saga-cross-epic-dryrun.md
  - docs/adr/0001-saga-pattern.md
  - packages/shared-py/opticloud_shared/saga/state_machine.py
  - packages/shared-py/opticloud_shared/saga/contract_fixtures.py
  - apps/billing-service/src/billing_service/saga_orchestrator.py
  - apps/billing-service/src/billing_service/routes.py
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py
---

# Story 5.A.0 — Saga 标准路径生产闭环

## Story

**As** Billing Lead + Solver Lead + SRE,
**I want** the already delivered 7-state Saga path hardened at runtime and proven across billing/solver/cost attribution boundaries,
**so that** 5.A billing can proceed without state-machine drift, unsafe payload persistence, or unverified finalize-failure reconciliation gaps.

## Scope Decision

The original epics text mentions a 5-state reserve/charge/commit/refund/rollback design. Current accepted reality is different: 5.A.0a delivered the ADR-0001 **7-state** DB-backed `SagaOrchestrator`, 5.A.0b delivered contract fixtures, and 5.A.0c locked `standard_first_simplified_fallback`.

Therefore this story does **not** rebuild Saga. It closes the standard path by enforcing existing contracts and filling test gaps.

## Acceptance Criteria

1. Runtime `payload_ref` safety is enforced before a Saga is persisted.
   - Shared validation rejects monetary keys, balances, prices, raw prompts/input/payloads, PII, secrets, API keys, bearer tokens, and non-string payload values.
   - Billing `SagaOrchestrator.start()` uses the shared validator and raises a typed billing exception on unsafe payload refs.
   - Empty payload refs remain allowed for legacy/internal Saga tests; unsafe keys/values do not.

2. Billing charge routes stop writing non-pointer billing parameters into `saga_instances.payload_ref`.
   - New `/v1/billing/charges` rows must not persist `amount`, `max_solve_seconds`, `rate_per_second`, raw request body, prompt/input payload, balance, credit, email, phone, token, or API key data in `payload_ref`.
   - Finalization remains backward compatible with legacy rows that already contain `max_solve_seconds`.
   - New rows derive the finalization cap from reserved amount and configured rate when no legacy `max_solve_seconds` exists.
   - Pre-charge explicit confirmation is recorded as a pointer-safe string marker, not a timestamp, boolean, or raw modal payload.

3. The 5.A.0b fixture validator and runtime validator share one public payload-ref validation contract.
   - `opticloud_shared.saga` exports the public validation helper.
   - Fixture manifest validation continues to pass.
   - Contract tests prove runtime/fixture parity without importing billing-service.

4. Solver finalize-failure reconciliation is DB-asserted.
   - The existing finalize-5xx integration test must assert `optimizations.error.billing_finalize_failed=true` in Postgres, not only that GET succeeds.
   - The persisted error must include `billing_charge_id`, `billing_status`, `billing_elapsed_seconds`, and `billing_retry_count=0` for reconciler replay.
   - Response JSON must continue to avoid exposing internal billing retry context.

5. Cost attribution metadata safety is tightened.
   - `CostTelemetryEvent` rejects nested metadata keys for secrets, bearer/auth material, raw prompt/input/payload text, phone/email, payment/bank/ID-card data, and monetary/balance/credit fields.
   - Existing solver cost attribution behavior remains best-effort and non-blocking.

6. Quality gates pass for the touched surfaces.
   - Billing Saga payload safety tests.
   - Billing route pointer-safety tests.
   - Shared Saga fixture/contract tests.
   - Solver billing integration test with DB assertion.
   - Shared cost telemetry tests.
   - Ruff and mypy on touched packages where configured.

## Tasks / Subtasks

- [x] T1: Add shared Saga payload-ref validator (AC: 1, 3)
  - [x] Add public validator in `packages/shared-py/opticloud_shared/saga/contract_fixtures.py`.
  - [x] Export it from `opticloud_shared.saga.__init__`.
  - [x] Add shared-py negative tests for unsafe keys, unsafe values, and non-string values.
- [x] T2: Enforce validator in billing runtime (AC: 1)
  - [x] Add typed `UnsafeSagaPayloadRefError`.
  - [x] Call validator from `SagaOrchestrator.start()` before DB writes.
  - [x] Add billing-service tests for accepted safe refs and rejected unsafe refs.
- [x] T3: Make billing routes pointer-safe (AC: 2)
  - [x] Remove new-route writes of `max_solve_seconds`, `rate_per_second`, and boolean confirmation from `payload_ref`.
  - [x] Keep legacy `max_solve_seconds` read path.
  - [x] Derive new-row finalization cap from `saga.amount / settings.lp_rate_per_second`.
  - [x] Update route tests to assert no unsafe persisted payload fields.
- [x] T4: Close solver finalize-failure DB assertion (AC: 4)
  - [x] Strengthen `test_billing_header_finalize_5xx_records_failure_flag`.
  - [x] Assert persisted reconciler retry context directly from `optimizations.error`.
- [x] T5: Harden cost attribution metadata guard (AC: 5)
  - [x] Expand blocked nested metadata keys.
  - [x] Add shared-py tests for nested raw payload/monetary/secret metadata rejection.
- [x] T6: Run quality gates and update story tracking (AC: 6)
  - [x] Run focused pytest commands.
  - [x] Run ruff/mypy on touched surfaces.
  - [x] Update Dev Agent Record, File List, Change Log, and status.

### Review Findings

- [x] [Review][Patch] Runtime payload value scan missed bare 11+ digit phone-like strings while trying to avoid UUID false positives. Fixed with UUID-aware bare-phone detection and shared-py regression coverage.
- [x] [Review][Patch] Cost telemetry metadata guard used exact key matching, so variants such as `billing_amount_cny` could leak monetary data. Fixed with blocked-fragment matching and regression coverage.
- [x] [Review][Patch] `ChargeCreateRequest.max_solve_seconds` comment still claimed finalize reads it from Saga payload. Updated schema comment to describe the new pointer-only derivation path.

## Dev Notes

### Hard Boundaries

- Do not edit `packages/shared-py/opticloud_shared/saga/state_machine.py`.
- Do not change the 7 states, transition matrix, or 5.A.0c decision.
- Do not implement simplified fallback; it remains v1.5+ only.
- Do not add new services, DB tables, queues, schedulers, UI, or external dependencies.
- Do not change billing ledger signs: orchestrator `service_success=-amount`, `user_cancel=+amount`, `downstream_reject_late=+amount`; route-level partial/reversal rows remain route-owned.

### Existing Patterns To Reuse

- `SagaOrchestrator.start()` already separates `amount` from `payload_ref`; keep money in `saga_instances.amount` and ledger rows.
- 5.A.0b fixture validation already bans dangerous payload keys and values; make that rule public and reuse it.
- Solver finalize failures already call `_merge_optimization_error`; the missing piece is DB-level test evidence.
- `CostTelemetryEvent` already recursively scans metadata keys; extend that guard instead of adding a new ACL layer in this story.

### Test Commands

```powershell
$env:PYTHONPATH='packages/shared-py'
uv run pytest packages/shared-py/tests/test_saga_contract_fixtures.py packages/shared-py/tests/test_cost_telemetry.py -q

$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'
uv run pytest apps/billing-service/tests/test_saga_payload_ref_safety.py apps/billing-service/tests/test_charge_routes.py apps/billing-service/tests/test_saga_contract_fixtures.py -q

$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/billing-service/src'
uv run pytest tests/contract/test_saga_contract_fixtures_contract.py -q

$env:PYTHONPATH='packages/shared-py;apps/solver-orchestrator/src'
uv run pytest apps/solver-orchestrator/tests/test_billing_integration.py -q

uv run ruff check packages/shared-py apps/billing-service apps/solver-orchestrator tests/contract
uv run ruff format --check packages/shared-py apps/billing-service apps/solver-orchestrator tests/contract
uv run mypy packages/shared-py
```

## Three-Round Pre-Implementation Adversarial Review

### Round 1 — Boundary / Ownership

Findings:
- Risk: implementing 5.A.0 from old epics text could duplicate 5.A.0a or regress ADR-0001 from 7 states to the obsolete 5-state wording.
- Risk: dry-run decision could be ignored and simplified fallback accidentally implemented now.
- Risk: route-level ledger compensation could be moved into orchestrator and break existing fixture semantics.

Revisions applied:
- Added Scope Decision clarifying 5.A.0 is standard-path hardening, not Saga rebuild.
- Added hard boundaries forbidding state-machine edits and simplified fallback implementation.
- AC2 and Dev Notes preserve route-owned `refund_partial` / `refund_reversal` semantics.

### Round 2 — Drift / Data Consistency / Privacy

Findings:
- Risk: `payload_ref` currently carries operational values (`max_solve_seconds`, `rate_per_second`, boolean confirmation), drifting from 5.A.0b pointer-only/data-safety contract.
- Risk: a runtime-only validator could drift from fixture validation.
- Risk: cost telemetry metadata blocks some PII/secrets but not all raw payload or monetary leakage keys.

Revisions applied:
- AC1-AC3 require one shared public payload-ref validator used by fixtures and billing runtime.
- AC2 requires new charge rows to exclude non-pointer billing parameters while preserving legacy reads.
- AC5 adds explicit cost metadata safety tightening.

### Round 3 — Dependency / Test Closure

Findings:
- Risk: solver finalize-failure behavior is described but not DB-asserted, so reconciler handoff could silently regress.
- Risk: adding schema changes for billing terms would expand scope and complicate CI.
- Risk: broad full-suite execution may be impractical; focused touched-surface gates must still be explicit.

Revisions applied:
- AC4 closes the solver DB assertion gap.
- AC2 derives new-row finalization cap from existing reserved amount and configured rate, avoiding schema changes.
- AC6 lists focused pytest/ruff/mypy gates for touched surfaces.

## Definition of Ready

- ✅ 5.A.0a, 5.A.0b, and 5.A.0c are done.
- ✅ Three pre-implementation adversarial review rounds completed and incorporated.
- ✅ Scope is limited to runtime contract hardening and tests.

## Definition of Done

- All ACs pass.
- All tasks/subtasks are checked.
- Story status is `code-review` after implementation and `done` after post-review fixes.
- `sprint-status.yaml` is synchronized.
- Post-implementation code review findings are resolved or documented.
- Branch is committed, pushed, and synced to GitHub.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-30: Started dev-story implementation; story moved to in-progress.
- 2026-05-30: Red phase added shared payload-ref safety, billing runtime, route pointer-safety, solver DB assertion, and cost telemetry negative tests.
- 2026-05-30: Implemented shared `validate_payload_ref_safety()`, billing runtime enforcement, route pointer-safe payload refs, solver DB assertion, and cost metadata guard expansion.
- 2026-05-30: Fixed property-test payload refs and UUID false positive in payload value detection.
- 2026-05-30: Focused gates, ruff, format check, and mypy passed; story moved to code-review.
- 2026-05-30: Post-implementation code review found 3 patch findings; applied payload phone detection, cost metadata fragment guard, and schema comment fixes.
- 2026-05-30: Final focused gates and extra billing Saga regression suite passed; story marked done.

### Completion Notes List

- Shared Saga fixture validation and billing runtime now use the same pointer-only payload-ref safety helper.
- New billing charge rows no longer persist `max_solve_seconds`, `rate_per_second`, or boolean confirmation flags in `payload_ref`; finalization remains compatible with legacy rows and derives new-row caps from amount/rate.
- Solver finalize 5xx integration now proves reconciler retry context is persisted in `optimizations.error` while success response stays clean.
- Cost telemetry metadata validation now rejects nested raw payload, monetary, PII, secret, and auth-bearing metadata keys.
- Post-review fixes applied:
  - UUID-aware bare 11+ digit payload-ref value rejection.
  - Fragment-based cost metadata key blocking.
  - Updated `ChargeCreateRequest.max_solve_seconds` documentation.
- Validation run:
  - `$env:PYTHONPATH='packages/shared-py'; uv run pytest packages/shared-py/tests/test_saga_contract_fixtures.py packages/shared-py/tests/test_cost_telemetry.py -q` → 42 passed
  - `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_saga_payload_ref_safety.py apps/billing-service/tests/test_charge_routes.py apps/billing-service/tests/test_saga_contract_fixtures.py -q` → 77 passed
  - `$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/billing-service/src'; uv run pytest tests/contract/test_saga_contract_fixtures_contract.py -q` → 2 passed
  - `$env:PYTHONPATH='packages/shared-py;apps/solver-orchestrator/src'; uv run pytest apps/solver-orchestrator/tests/test_billing_integration.py -q` → 13 passed
  - `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_critical_invariants.py apps/billing-service/tests/test_critical_transitions.py apps/billing-service/tests/test_critical_concurrency.py apps/billing-service/tests/test_critical_audit.py apps/billing-service/tests/test_invariants.py apps/billing-service/tests/test_property_saga_walks.py apps/billing-service/tests/test_reconciler.py -q` → 65 passed
  - `uv run ruff check packages/shared-py apps/billing-service apps/solver-orchestrator tests/contract` → passed
  - `uv run ruff format --check packages/shared-py apps/billing-service apps/solver-orchestrator tests/contract` → passed
  - `uv run mypy packages/shared-py` → passed

### File List

- `_bmad-output/stories/5-a-0-saga-implementation.md`
- `_bmad-output/stories/sprint-status.yaml`
- `packages/shared-py/opticloud_shared/saga/contract_fixtures.py`
- `packages/shared-py/opticloud_shared/saga/__init__.py`
- `packages/shared-py/opticloud_shared/cost_telemetry/__init__.py`
- `packages/shared-py/tests/test_saga_contract_fixtures.py`
- `packages/shared-py/tests/test_cost_telemetry.py`
- `apps/billing-service/src/billing_service/exceptions.py`
- `apps/billing-service/src/billing_service/saga_orchestrator.py`
- `apps/billing-service/src/billing_service/routes.py`
- `apps/billing-service/src/billing_service/schemas.py`
- `apps/billing-service/tests/test_saga_payload_ref_safety.py`
- `apps/billing-service/tests/test_charge_routes.py`
- `apps/billing-service/tests/test_critical_idempotency.py`
- `apps/billing-service/tests/test_invariants.py`
- `apps/billing-service/tests/test_property_saga_walks.py`
- `apps/billing-service/tests/test_saga_integration.py`
- `apps/billing-service/tests/test_reconciler.py`
- `apps/solver-orchestrator/tests/test_billing_integration.py`

### Change Log

- 2026-05-30: Story created with three pre-implementation adversarial review rounds applied.
- 2026-05-30: Implementation started.
- 2026-05-30: Implementation completed and moved to code-review.
- 2026-05-30: Post-review patch findings fixed.
- 2026-05-30: Final validation passed; story marked done.

## Senior Developer Review (AI)

Outcome: Changes requested; all findings fixed.

Findings:
- [x] Medium — Payload value safety only rejected `+`-prefixed phone-like values after UUID false-positive tuning; bare 11+ digit phone values could persist in `payload_ref`. Fixed with UUID-aware bare-number detection and shared-py regression coverage.
- [x] Medium — Cost telemetry blocked exact metadata keys only; compound keys such as `billing_amount_cny` could leak monetary data. Fixed by matching blocked fragments in metadata key names and adding regression coverage.
- [x] Low — `ChargeCreateRequest.max_solve_seconds` docstring still said finalize reads it from Saga payload, contradicting the 5.A.0 pointer-only route change. Fixed documentation to match derived-cap behavior.

Review layers:
- Blind Hunter: flagged overly narrow sensitive-value/key matching.
- Edge Case Hunter: identified UUID-vs-phone false-positive risk and compound metadata key leakage.
- Acceptance Auditor: verified 5.A.0 AC1/AC2/AC5 after fixes.

Final verification:
- `$env:PYTHONPATH='packages/shared-py'; uv run pytest packages/shared-py/tests/test_saga_contract_fixtures.py packages/shared-py/tests/test_cost_telemetry.py -q` → 42 passed
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_saga_payload_ref_safety.py apps/billing-service/tests/test_charge_routes.py apps/billing-service/tests/test_saga_contract_fixtures.py -q` → 77 passed
- `$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/billing-service/src'; uv run pytest tests/contract/test_saga_contract_fixtures_contract.py -q` → 2 passed
- `$env:PYTHONPATH='packages/shared-py;apps/solver-orchestrator/src'; uv run pytest apps/solver-orchestrator/tests/test_billing_integration.py -q` → 13 passed
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_critical_invariants.py apps/billing-service/tests/test_critical_transitions.py apps/billing-service/tests/test_critical_concurrency.py apps/billing-service/tests/test_critical_audit.py apps/billing-service/tests/test_invariants.py apps/billing-service/tests/test_property_saga_walks.py apps/billing-service/tests/test_reconciler.py -q` → 65 passed
- `uv run ruff check packages/shared-py apps/billing-service apps/solver-orchestrator tests/contract` → passed
- `uv run ruff format --check packages/shared-py apps/billing-service apps/solver-orchestrator tests/contract` → passed
- `uv run mypy packages/shared-py` → passed
