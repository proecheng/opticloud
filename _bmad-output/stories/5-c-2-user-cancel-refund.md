---
story_key: 5-c-2-user-cancel-refund
epic_num: 5
story_num: C.2
epic_name: Billing - Refunds + PIPL Export
status: ready-for-dev
baseline_commit: 95605ccb8b6df2d52d268b404e0a32621487df31
priority: Critical
type: user initiated async cancel refund
created_by: bmad-create-story
created_at: 2026-05-30
sources:
  - _bmad-output/planning/epics.md (FR B5 / Epic 5.C / Story 5.C.2)
  - _bmad-output/planning/prd.md (FR E8 async cancel + refund; FR B5 refunds)
  - _bmad-output/stories/3-8-cancel-refund.md
  - _bmad-output/stories/5-c-1-refund-failed-cancelled.md
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py
  - apps/solver-orchestrator/src/solver_orchestrator/billing_client.py
  - apps/solver-orchestrator/src/solver_orchestrator/billing_reconciler.py
  - apps/billing-service/src/billing_service/routes.py
  - apps/billing-service/src/billing_service/auth_dep.py
  - packages/shared-py/opticloud_shared/saga/state_machine.py
---

# Story 5.C.2 - 用户主动 cancel refund

Status: done

## Story

**As** an authenticated async optimization user,
**I want** a user-initiated cancellation to refund any Credits already charged for the unfinished task,
**so that** cancelling queued, running, or already-partially-billed work does not leave me paying for undelivered compute.

## Context

Story 3.8 already created the user-facing cancellation entry point: `DELETE /v1/optimizations/{optimization_id}`. It authenticates with the existing API-key path, enforces `optimize:write`, checks optimization ownership, marks `queued` / `in_progress` rows as `cancelled`, and closes reserved billing by calling billing-service `/finalize` with `status="failure"`.

That is correct while the billing Saga is still `reserved`: no debit has occurred, so billing writes a net-zero `refund` plus `refund_reversal`. The remaining gap is the Story 5.C.2 case from Epic 5.C: "按已扣 Credits prorated refund (Saga rollback)". If an async worker or reconciliation path has already finalized the charge successfully, the Saga may be `charged` with a `charge` row and possibly a prior `refund_partial` row. Calling `/finalize status=failure` on that charged Saga only rebuilds a terminal finalize response; it does not roll back the charged ledger.

Story 5.C.1 added the exact ledger math needed for charged rollback: apply `downstream_reject_late`, then reverse any prior `refund_partial` so the Saga ledger nets to zero and the user receives only the actual amount previously paid. Story 5.C.2 must expose that math for **user-initiated cancellation**, while keeping the public authorization boundary in solver-orchestrator where task ownership is known.

## Scope

1. Add an internal billing-service user-cancel refund operation for charge Sagas.
2. Require trusted internal service auth plus the acting user id; user JWT alone must not be sufficient for this billing endpoint.
3. Verify the charge belongs to the acting user before any state-specific response or mutation.
4. For `reserved` charges, close as net-zero refund using existing `user_cancel` plus `refund_reversal`.
5. For `charged` charges, perform prorated rollback using the already-paid amount: `charge + refund_partial + refund + refund_reversal` must net to zero.
6. Emit pointer-safe user-cancel audit evidence in the same DB transaction as ledger mutation.
7. Update solver-orchestrator cancellation to call the new user-cancel refund operation instead of `/finalize status=failure`.
8. Update billing reconciliation retry so failed user-cancel refund attempts retry the same operation, not the old finalize path.

## Out of Scope

- New public billing refund-by-charge endpoint.
- Cancelling another user's task or charge.
- Cancelling `completed`, `failed`, or `timeout` optimizations.
- Refunding already delivered `completed` billing Sagas.
- Payment gateway refunds, invoices, taxes, cash movement, or provider payment refs.
- New Saga states or broad transition-matrix redesign.
- UI work, Console refund pages, notifications, or PIPL export.
- Background worker execution or in-process sync solver interruption.

## Acceptance Criteria

1. User cancellation remains mediated by `DELETE /v1/optimizations/{optimization_id}` with API-key auth, `optimize:write`, row ownership checks, row locking, and existing cross-tenant `404` behavior.
2. A new billing-service internal user-cancel refund operation exists for charge Sagas and is not callable with user JWT alone. It requires `X-Internal-Service-Auth` plus `X-Internal-User-Id`.
3. Billing rejects missing charges with 404, non-charge Sagas with 409, wrong acting user with 403, and `pending` / `failed` / `completed` charges with 409 without mutating ledger, Saga state, or outbox.
4. `reserved` charge + user cancel transitions to `refunded`, writes `refund` plus `refund_reversal`, leaves balance unchanged, and records pointer-safe metadata distinguishing `user_cancel_refund` from automatic refund detection.
5. `charged` charge with no prior partial refund transitions to `rolled_back`, writes a positive `refund` equal to the reservation, returns the full paid amount as refunded, and leaves the Saga ledger sum exactly zero.
6. `charged` charge with prior `refund_partial` transitions to `rolled_back`, writes the normal positive `refund` plus a negative `refund_reversal` equal to prior partial refunds, returns only the actual paid amount, and leaves the Saga ledger sum exactly zero.
7. Already `refunded` or `rolled_back` charges return 200 with a rebuilt response and no duplicate ledger or outbox rows.
8. Successful mutations emit both the Saga transition outbox event and a dedicated pointer-safe `billing.refund_user_cancel.accepted` event containing `saga_id`, `charge_id`, `from_state`, `to_state`, `source`, `source_ref`, `refunded_amount`, and optional `elapsed_seconds`.
9. Audit payloads and ledger metadata do not contain raw request bodies, email, phone, JWT, API keys, payment refs, or arbitrary downstream payloads.
10. Solver cancellation sends `source_ref=<optimization_id>` and `elapsed_seconds=float(opt.solve_seconds or 0.0)` to the user-cancel refund operation. A `refunded` or `rolled_back` billing response maps to public `refund_status="refunded"`.
11. If the user-cancel refund call fails, the optimization still transitions to `cancelled`, response `refund_status` is `pending_reconciliation`, and persisted retry context includes a stable operation marker so the reconciler replays the user-cancel refund operation exactly once per retry cycle.
12. Repeated `DELETE` after successful refund or pending reconciliation is idempotent and does not duplicate billing calls.
13. Existing automatic refund endpoint from Story 5.C.1, sync billing finalize, async reserve, cancellation without billing, idempotency replay, batch billing rejection, reconciler finalize retries, subscription/topup/education behavior, and billing-service route regressions remain unchanged.
14. Quality gates pass:
    - focused billing route tests for user-cancel refund;
    - focused solver cancellation/reconciler tests;
    - existing solver-orchestrator test suite;
    - existing billing-service test suite;
    - ruff check / format check;
    - mypy for changed Python apps;
    - `git diff --check`.

## Tasks / Subtasks

- [x] T1: Add billing-service user-cancel refund schemas and auth boundary (AC: 2, 3, 8-9)
  - [x] Add request/response schemas for internal user-cancel refund.
  - [x] Add an internal-user dependency that requires the shared secret and parses `X-Internal-User-Id`.
  - [x] Ensure user JWT alone cannot call the new operation.

- [x] T2: Implement billing user-cancel refund ledger behavior (AC: 3-9)
  - [x] Reuse `_ledger_rows_for_saga`, `_charged_actual_paid`, `_refund_partial_total`, and existing Saga triggers.
  - [x] Reserved path: `user_cancel` plus net-zero `refund_reversal`.
  - [x] Charged path: `downstream_reject_late` plus prior `refund_partial` reversal.
  - [x] Add pointer-safe `billing.refund_user_cancel.accepted` outbox event.
  - [x] Rebuild terminal replay responses without duplicate rows/events.

- [x] T3: Wire solver-orchestrator cancellation to user-cancel refund (AC: 1, 10-13)
  - [x] Add `billing_client.refund_user_cancel`.
  - [x] Replace cancel-time `/finalize status=failure` call with the new operation.
  - [x] Map `refunded` and `rolled_back` billing states to public `refund_status="refunded"`.
  - [x] Persist operation-specific retry context on failure while preserving existing reconciler scan compatibility.

- [x] T4: Update billing reconciler retry path (AC: 11-13)
  - [x] Detect user-cancel refund retry context and call `billing_client.refund_user_cancel`.
  - [x] Preserve existing sync finalize retry behavior and backtest discount retry behavior.
  - [x] Clear user-cancel refund failure flags and update persisted refund status on success.

- [x] T5: Add focused tests and run quality gates (AC: 1-14)
  - [x] Billing tests: auth boundary, wrong-user rejection, reserved net-zero, charged full rollback, charged partial rollback, terminal replay idempotency, pointer-safe audit payload.
  - [x] Solver tests: cancel calls user-cancel refund, maps `rolled_back` to `refunded`, failure persists operation retry context, repeat delete does not duplicate calls.
  - [x] Reconciler tests: user-cancel refund retry uses the new client call and closes persisted refund status.
  - [x] Run full solver and billing regression suites plus static checks.

## Pre-Implementation Adversarial Review

### Round 1 - Boundary And Scope Review

Findings:

1. The story title can be misread as a public billing refund endpoint. That would bypass task ownership because billing only knows charge ownership, not optimization status.
2. Story 3.8 already owns the user-visible `DELETE` API. Adding another user-facing API would create two cancellation sources of truth.
3. Story 5.C.1 already handles automatic detection. Reusing its reason `cancelled` without a separate user-cancel audit marker would make user action indistinguishable from downstream monitor action.
4. Cancelling `completed` optimizations or `completed` billing Sagas is not defined as self-service refund. That would become a dispute workflow, not async cancellation.
5. `pending` charge refund would create money because no reserve or debit has occurred.
6. Payment provider refunds and invoices are outside Credits ledger refund and would import unsettled tax/payment requirements.
7. Batch cancellation is not part of Story 5.C.2; Story 3.13 explicitly left batch cancel out of scope.
8. Sync in-process solver interruption is not feasible in the current route model and must not be claimed.
9. A raw `charge_id` user endpoint would allow users to probe state details for charges disconnected from cancellable tasks.
10. PIPL data export is in Epic 5.C but unrelated to refund mechanics.

Revision after Round 1:

- User action remains through solver-orchestrator `DELETE /v1/optimizations/{id}` only.
- Billing receives only a trusted internal user-cancel refund signal with an acting user id.
- Completed, pending, failed, non-charge, payment gateway, UI, batch cancel, and PIPL work are explicit out of scope.
- Audit event name and metadata distinguish user-cancel refund from automatic refund detection.

### Round 2 - Drift, Data Consistency, And Idempotency Review

Findings:

1. Existing Story 3.8 calls `/finalize status=failure`; on `charged` Sagas this only replays a finalize response and does not refund already-paid Credits.
2. Direct `downstream_reject_late` over-refunds after a partial finalize unless prior `refund_partial` is reversed.
3. A retrying DELETE must not call billing again once cancellation metadata says refund was attempted.
4. If billing refund fails after marking optimization `cancelled`, the retry context must identify the exact operation; otherwise the existing reconciler will replay the old finalize call and preserve the bug.
5. Reusing only `billing_finalize_failed=true` is useful for scan compatibility but ambiguous without an operation marker.
6. `rolled_back` is a successful refund state, but solver's public `refund_status` vocabulary should remain user-facing and say `refunded`.
7. Terminal replay for `refunded` / `rolled_back` needs rebuilt responses because there is no response cache for this endpoint.
8. Ledger closure must assert exact Saga sum zero, not just balance changed by an expected amount.
9. Existing auto-refund endpoint tests do not prove user-cancel audit payloads or internal acting-user enforcement.
10. A source reference can become a raw payload leak unless it is bounded and pointer-shaped.

Revision after Round 2:

- Solver cancellation uses a new billing operation rather than `/finalize status=failure`.
- Charged rollback reuses Story 5.C.1 partial-refund reversal math.
- Retry context includes `billing_operation="user_cancel_refund"` while retaining scan compatibility.
- `rolled_back` maps to public `refund_status="refunded"`.
- Tests must assert no duplicate billing calls, no duplicate rows/events, exact ledger sum zero, and pointer-safe payloads.

### Round 3 - Dependency, Closure, And Audit Review

Findings:

1. Billing must not trust only the internal shared secret; it also needs the acting user id to enforce charge ownership.
2. `require_user` accepts JWT fallback, so using it directly would accidentally make the billing endpoint public. A stricter internal-user dependency is needed.
3. Existing Saga trigger names are imperfect but stable; adding new triggers would require property/contract fixture updates outside the story's need.
4. Outbox audit must be in the same DB transaction as ledger mutation.
5. Solver-orchestrator must not import billing-service models or Saga classes; cross-service coupling stays in `billing_client.py`.
6. Existing reconciler success cleanup must remove both legacy cancel-finalize flags and new user-cancel refund flags so status responses do not stay stuck in pending reconciliation.
7. Backtest discount retry behavior is adjacent and must not regress when reconciler branching is added.
8. Existing `refund-auto` behavior must remain unchanged; Story 5.C.2 should share helpers, not reinterpret automatic refund reasons.
9. Closure requires code review and GitHub sync, not just local tests.
10. Sprint status must not move to done before post-implementation review and regression gates pass.

Revision after Round 3:

- Billing endpoint uses a strict internal-user dependency: shared secret plus `X-Internal-User-Id`, no JWT fallback.
- Existing Saga triggers remain unchanged.
- Billing outbox event is written inside the refund transaction.
- Solver only calls billing through `billing_client.py`.
- Reconciler supports the new operation while preserving old finalize retries and backtest discount retry.
- Definition of Done includes post-implementation code review, fixes, full gates, commit, PR, CI, merge, and main sync.

## Dev Notes

### Existing Patterns To Reuse

- Solver user boundary: `verify_api_key`, `require_scope("optimize:write", scopes)`, row ownership check, and `with_for_update()` in `delete_optimization`.
- Solver billing metadata helpers: `_optimization_billing_metadata`, `_set_optimization_billing_metadata`, `_merge_optimization_error`, and `_refund_status_from_optimization`.
- Solver cross-service boundary: `apps/solver-orchestrator/src/solver_orchestrator/billing_client.py`.
- Billing auth: `require_internal_service`; add stricter internal-user wrapper rather than using JWT fallback.
- Billing ledger math: `_ledger_rows_for_saga`, `_refund_partial_total`, `_charged_actual_paid`, `SagaOrchestrator.apply("user_cancel")`, and `SagaOrchestrator.apply("downstream_reject_late")`.
- Billing audit: `OutboxEvent` in the same transaction as Saga and ledger rows.
- Reconciler scan: `error.billing_finalize_failed=true` remains the broad retry filter.

### Architecture Compliance

- Credits ledger remains the source of truth; no mutable balance table.
- Saga transitions, ledger rows, and outbox audit commit atomically.
- Solver owns task state and task ownership; billing owns charge state and ledger.
- Service-to-service calls stay HTTP client calls; no direct imports across service model boundaries.
- Pointer-safe persisted metadata is allowed; raw request bodies and secrets are not.

### Implementation Guardrails

- Do not add a public billing refund endpoint.
- Do not remove or repurpose `POST /v1/billing/charges/{id}/refund-auto`.
- Do not change `FinalizeChargeRequest` or existing finalize replay semantics.
- Do not add new Saga states or transition names.
- Do not expose raw `charge_id` in solver cancellation responses; existing redaction must hold.
- Do not duplicate refund rows on repeated cancellation or reconciliation retries.
- Do not make `rolled_back` user-visible as a failure; for cancellation it is a successful refund state.

### Suggested Test Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/solver-orchestrator/src;apps/auth-service/src'; uv run pytest apps/solver-orchestrator/tests/test_cancel_refund.py apps/solver-orchestrator/tests/test_billing_reconciler.py -q
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/test_charge_routes.py -q
$env:PYTHONPATH='packages/shared-py;apps/solver-orchestrator/src;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/solver-orchestrator/tests/ apps/billing-service/tests/ -q
uv run ruff check apps/solver-orchestrator apps/billing-service apps/auth-service
uv run ruff format --check apps/solver-orchestrator apps/billing-service apps/auth-service
$env:PYTHONPATH='packages/shared-py;apps/solver-orchestrator/src;apps/billing-service/src;apps/auth-service/src'; uv run mypy apps/solver-orchestrator apps/billing-service apps/auth-service
git diff --check
```

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline commit: `95605ccb8b6df2d52d268b404e0a32621487df31`.
- Dev implementation started; sprint/story status moved to in-progress.
- Red phase: focused billing user-cancel refund tests failed with 404 because `/refund-user-cancel` did not exist; solver/reconciler tests failed because `billing_client.refund_user_cancel` did not exist.
- Green phase: focused billing user-cancel refund tests passed with 5 tests; focused solver/reconciler user-cancel tests passed with 3 tests.
- Route regression passed: `test_charge_routes.py` 35 tests passed.
- Related solver cancellation/reconciler regression passed: 17 tests passed.
- Full billing-service regression passed: 271 tests passed.
- Full solver-orchestrator regression passed: 283 tests passed.
- Static gates passed: ruff check, ruff format --check, mypy, and `git diff --check`.

### Completion Notes List

- Added strict internal-user billing auth so user-cancel refunds require shared service auth plus `X-Internal-User-Id`, with no JWT fallback.
- Added internal `POST /v1/billing/charges/{charge_id}/refund-user-cancel` for user-initiated async cancellation refunds.
- Reserved user cancels now close as net-zero refund plus refund_reversal; charged user cancels roll back via `downstream_reject_late` and reverse prior partial refunds so the Saga ledger nets to zero.
- Solver cancellation now calls `billing_client.refund_user_cancel`, maps `rolled_back` to user-facing `refund_status="refunded"`, and persists operation-specific retry context on failure.
- Billing reconciler now retries `billing_operation="user_cancel_refund"` with the new client call while preserving existing finalize and backtest retry behavior.
- Post-implementation review found one concurrency/idempotency boundary: the billing user-cancel refund route must lock the Saga before state branching. Patched with initial `FOR UPDATE` load.

### File List

- `_bmad-output/stories/5-c-2-user-cancel-refund.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/billing-service/src/billing_service/auth_dep.py`
- `apps/billing-service/src/billing_service/routes.py`
- `apps/billing-service/src/billing_service/schemas.py`
- `apps/billing-service/tests/test_charge_routes.py`
- `apps/solver-orchestrator/src/solver_orchestrator/billing_client.py`
- `apps/solver-orchestrator/src/solver_orchestrator/billing_reconciler.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/test_billing_reconciler.py`
- `apps/solver-orchestrator/tests/test_cancel_refund.py`

## Change Log

- 2026-05-30 - Story created and revised through three pre-implementation adversarial review rounds; status set to ready-for-dev.
- 2026-05-30 - Implemented internal user-cancel refund endpoint, solver cancellation wiring, reconciler retry branch, and focused regression tests; status set to code-review.
- 2026-05-30 - Completed post-implementation code review and patched Saga locking/idempotency boundary; validation gates passed.

## Senior Developer Review (AI)

Findings:

- [x] [Review][Patch] `refund-user-cancel` read the Saga before branching and only locked inside `SagaOrchestrator.apply()`. A concurrent retry could branch on stale `reserved` or `charged` state and then add route-level compensation/audit after `apply()` returned idempotently. Patched the route to load the Saga with `FOR UPDATE` before any state-specific branch, so concurrent retries observe terminal state and use no-mutation replay.

Decision: Approved after patch.
