# Story 3.8: Cancel async + refund

Status: done

## Story

As an authenticated optimization API user,
I want to cancel an async optimization and have any reserved Credits closed through the refund policy,
so that abandoned queued or running work cannot later execute or leave billing Saga state unresolved.

## Acceptance Criteria

1. `DELETE /v1/optimizations/{optimization_id}` requires the same API-key authentication path as `POST /v1/optimizations`, requires `optimize:write`, and returns Story 3.7 Problem Details (`application/problem+json` with `errors[]` and `next_action_url`) for auth, not-found, and invalid-state failures.
2. For a caller-owned optimization with status `queued` or `in_progress`, `DELETE` transitions the row to `cancelled`, sets `completed_at`, preserves `model_version`, does not create solution/objective/cost/voucher side effects, and returns `200 OK` with the compact optimization status shape including `status`, `mode`, `created_at`, `completed_at`, `error`, `refund_status`, and `message`.
3. Repeating `DELETE` for an already `cancelled` optimization is idempotent: it returns `200 OK` with the same cancelled status shape and does not call billing finalize again.
4. `DELETE` for terminal non-cancellable statuses (`completed`, `failed`, `timeout`) returns `409 Cancellation Not Allowed` as Problem Details, with no row mutation and no billing call.
5. Async optimization submission with `X-Billing-Charge-Id` is now supported: the route validates the UUID, calls `billing_client.reserve()` once before returning 202, stores internal billing metadata in `input_payload._system.billing` including the raw `charge_id` required for later finalize, and redacts that value from responses, logs, and error details. If reserve fails, the optimization row is rolled back. Existing sync billing behavior remains unchanged.
6. Cancelling a billing-backed async optimization calls `billing_client.finalize(charge_id, user_id, elapsed_seconds=float(opt.solve_seconds or 0.0), status="failure", failure_reason="user_cancelled")` exactly once. On success, response metadata reports `refund_status="refunded"` when billing returns `current_state=refunded`, otherwise `refund_status="finalized"`.
7. If billing finalize fails during cancellation, the optimization still transitions to `cancelled` to prevent later execution, `error.billing_cancel_finalize_failed=true` and retry context are persisted, response reports `refund_status="pending_reconciliation"`, and repeated `DELETE` does not duplicate the failed finalize attempt.
8. Cross-tenant access to another user's optimization returns `404 Not Found` and does not reveal ownership, current status, billing charge id, or idempotency key.
9. Existing Story 3.3/3.7 behavior is preserved except where AC5 intentionally supersedes the old "billing not supported for async" rule. For billing-backed async submissions, the normalized `X-Billing-Charge-Id` participates in the idempotency identity so the same `Idempotency-Key` cannot be replayed with a different charge id. POST idempotency replay for a cancelled async optimization returns `200 OK` with the cancelled status content, not a new 202 job or a completed sync result.
10. Regression coverage includes solver-orchestrator async cancel/refund tests, billing-client call-count tests, status GET after cancel, terminal-state 409 tests, cross-tenant 404 tests, and unchanged billing-service Saga/refund tests.

## Tasks / Subtasks

- [x] Task 1: Extend solver-orchestrator cancellation contract (AC: 1, 2, 3, 4, 8)
  - [x] Add `DELETE /v1/optimizations/{optimization_id}` in `apps/solver-orchestrator/src/solver_orchestrator/routes.py`.
  - [x] Reuse `verify_api_key`, `require_scope("optimize:write", scopes)`, and owner check pattern from `get_optimization`.
  - [x] Lock the target optimization row before mutation (`select(...).with_for_update()`), then mutate only caller-owned `queued` / `in_progress` rows.
  - [x] Add `cancelled` status response support to `_build_optimization_status_response_content`.
  - [x] Make repeated cancellation idempotent without duplicate billing calls.
- [x] Task 2: Support async billing reserve metadata (AC: 5, 9)
  - [x] Replace the Story 3.3 rejection path for async `X-Billing-Charge-Id` with UUID validation + `billing_client.reserve`.
  - [x] Include the normalized billing charge id in the async idempotency hash only for effective async submissions; preserve existing sync billing idempotency behavior.
  - [x] Call `billing_client.reserve` only after the optimization row and idempotency row, when present, have flushed successfully; if flush fails, no billing call is allowed.
  - [x] Store billing metadata under `input_payload._system.billing` rather than adding a DB column.
  - [x] Add small route-level helper functions to read/write `_system.billing` and derive `refund_status`; do not scatter ad hoc JSONB mutation in endpoint branches.
  - [x] Preserve existing sync billing reserve/finalize behavior.
  - [x] Update Story 3.3 tests that asserted async billing was rejected; the new contract supersedes those expectations.
- [x] Task 3: Close refund policy through existing Billing Saga finalize (AC: 6, 7)
  - [x] Reuse `billing_client.finalize(... status="failure", failure_reason="user_cancelled")`; do not add a new billing endpoint.
  - [x] Persist cancellation billing outcome in `Optimization.error`, including `billing_charge_id`, `billing_cancel_finalize_failed`, `billing_finalize_failed`, `billing_elapsed_seconds`, `billing_retry_count`, `billing_status`, and `billing_failure_reason`, so the existing billing reconciler can pick up failed cancel finalizes.
  - [x] Ensure no solver execution, cost attribution, top-k, or voucher issuance occurs on cancellation.
- [x] Task 4: Extend Story 3.7 error catalog and response coverage (AC: 1, 4, 8)
  - [x] Add catalog entries/remediation keys for `cancellation_not_allowed`; do not let 409 cancellation failures fall back to `idempotency_conflict`.
  - [x] Keep the old async-billing-not-supported catalog entry only for backward compatibility if referenced elsewhere; `POST /v1/optimizations?mode=async` must no longer emit it after AC5.
  - [x] Ensure errors redact `X-Billing-Charge-Id`, `Authorization`, and `Idempotency-Key`.
  - [x] Keep `next_action_url` field name; never serialize `next_action`.
- [x] Task 5: Add focused tests and run regression (AC: 1-10)
  - [x] Add `apps/solver-orchestrator/tests/test_cancel_refund.py`.
  - [x] Cover async queue cancel without billing, async billing reserve then cancel/finalize failure, idempotent repeat DELETE, terminal 409, cross-tenant 404, GET after cancel, and POST idempotency replay after cancel.
  - [x] Update `apps/solver-orchestrator/tests/test_sync_async_mode.py` for AC5.
  - [x] Run `uv run pytest apps/solver-orchestrator/tests -q`, `uv run pytest apps/billing-service/tests -q`, `uv run mypy apps packages`, `uv tool run pre-commit run --all-files --show-diff-on-failure`, and `git diff --check`.
- [x] Task 6: BMAD bookkeeping (AC: 10)
  - [x] Update this story's Dev Agent Record, File List, Change Log, and sprint status.
  - [x] After implementation, perform code review and patch findings before merge.

## Dev Notes

### Current Implementation Reality

- Story 3.3 async mode currently persists an `Optimization` row with `status="queued"` and returns `202 Accepted` with `Location: /v1/optimizations/{id}`. Background execution is explicitly not enabled yet; the status message is `Task queued; background execution is not enabled in Story 3.3`.
- Current async path rejects `X-Billing-Charge-Id` before row creation. Story 3.8 intentionally supersedes that rule so a cancellation can close the billing Saga refund path.
- There is no running worker/process handle to interrupt in this story. Implement cancellation as durable state transition for `queued` / persisted `in_progress` optimizations. Do not attempt to interrupt synchronous in-process LP solving.
- `optimizations.status` has no DB check constraint, so `cancelled` can be introduced without migration. The partial index only tracks `queued` / `in_progress`; cancelled rows naturally leave the runnable index.

### Existing Code to Reuse

- Auth and scope: `verify_api_key` and `require_scope` in `apps/solver-orchestrator/src/solver_orchestrator/auth.py`, already used by `post_optimization` and `get_optimization`.
- Status response: `_build_optimization_status_response_content` and `_build_async_accepted_response` in `apps/solver-orchestrator/src/solver_orchestrator/routes.py`.
- Billing client: `apps/solver-orchestrator/src/solver_orchestrator/billing_client.py` already exposes `reserve()` and `finalize()` with shared internal auth headers.
- Billing Saga route: `apps/billing-service/src/billing_service/routes.py::finalize_charge` maps `status="failure"` to `user_cancel`, terminal `refunded`, and audit ledger rows (`refund` + `refund_reversal`) for net-zero reservation closure.
- Shared Saga single source of truth: `packages/shared-py/opticloud_shared/saga/state_machine.py` has `RESERVED -> REFUNDED` trigger `user_cancel`.
- Error responses: Story 3.7 added `error_catalog.py`, `error_responses.py`, and `_rfc7807_error` delegation. Extend these instead of creating a second error builder.
- FastAPI route placement: define `DELETE /v1/optimizations/{optimization_id}` beside the existing `GET /v1/optimizations/{optimization_id}` in `routes.py` so path parameter behavior and OpenAPI grouping remain consistent.

### Billing Metadata Contract

Store billing metadata under `input_payload._system.billing`:

```json
{
  "charge_id": "raw UUID string, internal DB metadata only",
  "reserved": true,
  "reserve_status_code": 200,
  "cancel_finalize_attempted": false,
  "cancel_finalize_status": null,
  "refund_status": null
}
```

Response bodies, logs, and Problem Details must not expose raw sensitive headers or idempotency values. The raw `charge_id` is allowed only in internal persisted metadata because cancellation cannot close the Saga without it. Do not return `billing_charge_id` in the cancellation response unless an existing owning-user billing response already exposes that exact identifier; prefer `refund_status` and redacted internal metadata.

### Cancellation Response Shape

Use the compact status shape already returned by `GET /v1/optimizations/{id}` for non-completed rows. Add these fields for cancelled rows:

```json
{
  "optimization_id": "...",
  "status": "cancelled",
  "mode": "async",
  "model_version": {"provider_id": "highs", "kind": "solver", "version": "...", "provider_url": "..."},
  "created_at": "...",
  "completed_at": "...",
  "error": {
    "title": "Optimization Cancelled",
    "detail": "cancelled by user request",
    "billing_status": "failure",
    "billing_failure_reason": "user_cancelled"
  },
  "refund_status": "not_applicable|refunded|finalized|pending_reconciliation",
  "message": "Optimization cancelled"
}
```

### Boundary Rules

- No billing header: cancellation sets `refund_status="not_applicable"` and must not call billing.
- Billing reserve failed during async submit: return `422 Billing Reserve Failed`; rollback the pending optimization/idempotency transaction so no optimization row or idempotency key persists.
- Billing reserve ordering: all local validation, provider-route checks, idempotency lookup, optimization row flush, and idempotency row flush must happen before the external reserve call. This prevents a reserve from succeeding when a predictable local uniqueness/constraint error would later reject the request.
- Billing finalize failed during cancel: set `status="cancelled"` anyway to prevent future execution; persist retry context in `error` using the existing M2.2c reconciler keys plus the cancel-specific flag; return `200 OK` with `refund_status="pending_reconciliation"`.
- Repeat DELETE after a pending reconciliation must not call finalize again; it returns stored cancellation state.
- Cross-tenant or missing optimization must be indistinguishable `404`.
- Cross-tenant/missing lookup must complete before any status-specific branching, terminal-state detail, billing metadata extraction, or idempotency detail can be observed.
- Completed/failed/timeout rows are terminal and return `409`; they must not be mutated.
- Sync in-flight interruption is out of scope because current route executes synchronously in request scope with no persisted cancellation token.
- PRD trimmed-mode/manual refund language is a fallback operating model. Story 3.8 implements the standard automated v1 path for async cancellation; manual reconciliation remains an operational fallback only when persisted retry context reports `pending_reconciliation`.

## Story Review Rounds

### Round 1 - Data Consistency (2026-05-27)

Findings applied:

- AC5 mixed internal persistence and external redaction. The story now requires raw `charge_id` only in internal JSONB metadata and redaction in responses, logs, and Problem Details.
- AC6 used an ambiguous `elapsed_seconds=0 or persisted solve_seconds` phrase. The story now requires deterministic `float(opt.solve_seconds or 0.0)`.
- AC9 did not state the HTTP status for POST idempotency replay after cancellation. The story now requires `200 OK`.
- PRD manual-refund fallback could be misread as the primary implementation. Boundary rules now state Story 3.8 implements the automated v1 cancellation path, with manual reconciliation only as an operational fallback.

Result: data contracts for billing metadata, elapsed time, replay response, and refund-mode scope are now internally consistent.

### Round 2 - Function / Dependency Consistency and Drift (2026-05-27)

Findings applied:

- 409 cancellation failures need their own Story 3.7 catalog entry. The story now requires `cancellation_not_allowed` instead of relying on the existing 409 `idempotency_conflict` fallback.
- AC5 intentionally supersedes async-billing rejection. The task list now says the old catalog entry may stay only for backward compatibility, but the async optimization path must stop emitting it.
- Billing metadata JSONB mutation would drift if implemented inline in multiple endpoint branches. The story now requires helper functions for read/write/refund-status derivation.
- Dependency boundaries were clarified: solver-orchestrator must keep using `billing_client.py` only and must not import billing-service route/models/Saga code.
- Route placement was clarified so `DELETE /v1/optimizations/{optimization_id}` sits beside the existing GET route.

Result: function boundaries, error catalog ownership, and cross-service dependency rules are now explicit.

### Round 3 - Boundary / Closure Review (2026-05-27)

Findings applied:

- Reserve could become an orphan if called before predictable local DB/idempotency failures are known. The story now requires optimization/idempotency flush before external reserve and rollback on reserve failure.
- Async billing idempotency was under-specified. The story now requires the normalized billing charge id to participate in the effective-async idempotency hash, while preserving existing sync billing behavior.
- Cancellation finalize failures would not be picked up by the existing M2.2c reconciler if only a cancel-specific flag were written. The story now requires both `billing_cancel_finalize_failed` and the existing `billing_finalize_failed` retry keys.
- Cross-tenant handling now explicitly precedes status branching and metadata extraction, preventing leaks through terminal-state or billing-specific responses.
- Repeat cancellation after pending reconciliation is closed as a read-only replay of persisted state, not another finalize attempt.

Result: transaction order, idempotency identity, reconciler pickup, tenant isolation, and repeat-call closure are now specified.

### Project Structure Notes

- Keep the implementation inside `apps/solver-orchestrator/src/solver_orchestrator/` and existing tests under `apps/solver-orchestrator/tests/`.
- Do not add a billing-service endpoint for this story; cancellation uses existing `POST /v1/billing/charges/{id}/finalize` failure path.
- Do not add a migration unless a review proves JSONB metadata is insufficient. The current schema supports `cancelled` as a status string.
- Preserve local dependency boundaries: solver-orchestrator calls billing-service only through `billing_client.py`; it must not import billing-service models or Saga orchestrator classes directly.
- Do not import billing-service modules, Saga ORM classes, or shared transition internals into solver-orchestrator cancellation code. The only Saga signal consumed by solver-orchestrator is the `BillingResult.body["current_state"]` returned by `billing_client.finalize`.

### Previous Story Intelligence

- Story 3.7 centralized RFC 7807 error response generation. Use catalog-backed Problem Details and avoid raw `{"detail": ...}` FastAPI responses.
- Story 3.7 post-review added redaction for caller-supplied `ErrorDetail`; still pass sensitive fields (`Authorization`, `Idempotency-Key`, `X-Billing-Charge-Id`) through the shared builder so redaction stays centralized.
- Story 3.7 CI lint failed on mutable `ContextVar` defaults and import ordering. Keep new tests lint-clean without local `sys.path` surgery in test files.

### Testing Standards

- Use existing async HTTP test style from `test_sync_async_mode.py` and `test_billing_integration.py`.
- Stub `billing_client.reserve` / `billing_client.finalize` for solver-orchestrator tests; do not require a live billing-service process.
- Billing-service Saga behavior is already tested in `apps/billing-service/tests/test_charge_routes.py`, `test_critical_*`, and property tests. Run the suite to prove Story 3.8 did not drift the refund contract.
- Include at least one DB-level assertion for optimization row status/error metadata after cancellation.

### References

- `_bmad-output/planning/epics.md` Story 3.8 lines near `DELETE /v1/optimizations/{id}` and Story 5.C.2 cancel refund.
- `_bmad-output/planning/prd.md` FR E8 and B5 tables.
- `_bmad-output/planning/architecture.md` Concern #13 Distributed Billing Transaction and Pattern P23 idempotency.
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py` async submit, status response, billing sync integration, and Story 3.7 error builder.
- `apps/solver-orchestrator/src/solver_orchestrator/billing_client.py` reserve/finalize client.
- `apps/billing-service/src/billing_service/routes.py` reserve/finalize routes.
- `packages/shared-py/opticloud_shared/saga/state_machine.py` Saga transitions.
- `_bmad-output/stories/3-7-rfc7807-errors-detail.md` previous story learnings.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-27 - Initial Story 3.8 draft created from sprint status, Epics/PRD/Architecture/UX, Story 3.7 learnings, solver async/billing code, billing Saga routes, shared Saga state machine, and existing test patterns.
- 2026-05-27 - Three story review rounds completed before implementation: data consistency, function/dependency consistency, and boundary/closure.
- 2026-05-27 - Dev implementation started; sprint/story status moved to in-progress.
- 2026-05-27 - Implemented async cancellation endpoint, async billing reserve metadata, cancel refund finalize, cancellation error catalog, and focused tests.
- 2026-05-27 - Validation passed: `uv run pytest apps/solver-orchestrator/tests -q` -> 243 passed; billing-service Saga suite with explicit local PYTHONPATH -> 135 passed; `uv run mypy apps packages` -> passed; pre-commit -> passed; `git diff --check` -> passed.
- 2026-05-27 - Post-implementation code review found one closure patch: cancel-finalize reconciliation success needed to clear cancel-specific retry flags and advance persisted refund status. Patched `billing_reconciler` and added regression coverage.
- 2026-05-27 - Final validation passed after review patch: solver-orchestrator suite 244 passed; billing-service suite 135 passed; mypy, pre-commit, and diff-check passed.

### Completion Notes List

- Story draft scopes cancellation to persisted async `queued` / `in_progress` optimization rows and explicitly excludes synchronous in-process solver interruption.
- Story draft reuses existing billing `finalize(status="failure")` refund path rather than adding a new billing endpoint.
- Implemented `DELETE /v1/optimizations/{optimization_id}` with row locking, owner isolation, idempotent repeated cancellation, terminal 409 Problem Details, and compact cancelled status responses.
- Async optimization now accepts `X-Billing-Charge-Id`, reserves billing after local row/idempotency flush, stores internal `_system.billing` metadata, and rolls back on reserve failure.
- Cancellation closes billing-backed async jobs via existing `billing_client.finalize(status="failure", failure_reason="user_cancelled")`; failures persist both cancel-specific and existing reconciler retry keys.
- Existing billing reconciler now closes the cancel-refund loop on retry success by clearing cancel-specific failure flags and updating persisted `refund_status`.
- Added focused cancellation/refund regression coverage and updated Story 3.3 async billing tests to the new Story 3.8 contract.

### File List

- `_bmad-output/stories/3-8-cancel-refund.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/error_catalog.py`
- `apps/solver-orchestrator/src/solver_orchestrator/billing_reconciler.py`
- `apps/solver-orchestrator/src/solver_orchestrator/main.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/test_billing_reconciler.py`
- `apps/solver-orchestrator/tests/test_cancel_refund.py`
- `apps/solver-orchestrator/tests/test_sync_async_mode.py`

### Change Log

- 2026-05-27 - Initial Story 3.8 draft created and sprint status moved from backlog to ready-for-dev.
- 2026-05-27 - Applied three pre-implementation story review rounds and moved story to in-progress.
- 2026-05-27 - Implemented Story 3.8 cancellation/refund contract and moved story to code review.
- 2026-05-27 - Addressed post-implementation code review finding for cancel-refund reconciler closure; all validation gates pass; story marked done.

## Senior Developer Review (AI) - Post-Implementation (2026-05-27)

### Review Findings

- [x] [Review][Patch] Cancel-finalize retry success did not fully close the refund loop. The implementation wrote `billing_cancel_finalize_failed=true` so the existing reconciler could retry, but the reconciler success path only cleared generic finalize fields and did not advance persisted cancel `refund_status`. Patched `billing_reconciler` to clear cancel-specific flags and update `_system.billing.refund_status` to `refunded|finalized` on retry success.

### Result

All review findings were patched. Re-ran focused cancel/reconciler tests, full solver-orchestrator suite, billing-service Saga suite, mypy, pre-commit, and diff-check successfully. Review outcome: approved / done.
