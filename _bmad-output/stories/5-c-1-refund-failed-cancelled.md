---
story_key: 5-c-1-refund-failed-cancelled
epic_num: 5
story_num: C.1
epic_name: Billing - Refunds + PIPL Export
status: done
baseline_commit: cb0e9221d9ffe3856190fa66f91977302875a489
priority: Critical
type: billing automatic refund + audit trail
created_by: bmad-create-story
created_at: 2026-05-30
sources:
  - _bmad-output/planning/epics.md (FR B5 / Epic 5.C / Story 5.C.1)
  - _bmad-output/planning/prd.md (FR B5 refunds for failed/cancelled/infeasible)
  - _bmad-output/planning/architecture.md (Distributed Billing Transaction / ledger source of truth / outbox)
  - _bmad-output/stories/5-a-4-per-formula-charging-capped.md
  - _bmad-output/stories/5-a-7-reconciliation-cron.md
  - apps/billing-service/src/billing_service/routes.py
  - apps/billing-service/src/billing_service/saga_orchestrator.py
  - packages/shared-py/opticloud_shared/saga/state_machine.py
  - apps/billing-service/tests/test_charge_routes.py
  - apps/billing-service/tests/test_reconciler.py
---

# Story 5.C.1 - failed/cancelled/infeasible 自动退款

Status: done

## Story

**As** a billing operator and downstream task monitor,
**I want** billing-service to accept a trusted automatic refund signal when a charged task is detected as failed, cancelled, or infeasible,
**so that** users do not pay for tasks that did not deliver a usable result, and every refund decision is visible in the ledger and outbox audit trail.

## Context

Epic 5.C opens FR B5. The planning AC is compact: "Given task failed / When 自动检测 / Then Credits 自动 refund + audit log." Existing billing work already provides most low-level mechanics:

- `SagaOrchestrator.apply("user_cancel")` supports `RESERVED -> REFUNDED` and writes a positive `kind="refund"` ledger row.
- `/v1/billing/charges/{id}/finalize` failure path writes a compensating negative `kind="refund_reversal"` because reserve never debits. Net effect is zero balance change with an auditable refund attempt.
- `SagaOrchestrator.apply("downstream_reject_late")` supports `CHARGED -> ROLLED_BACK` and writes a positive `kind="refund"` ledger row.
- `reconciler.expected_bounds()` expects `refunded` and `rolled_back` solve-charge sagas to net to zero.

The gap is the trusted automatic detection surface. Today there is no billing-owned internal API that a task monitor can call after detecting failed/cancelled/infeasible task status. Also, the direct `downstream_reject_late` Saga trigger refunds the reserved amount. That is correct only when the user was charged the full reservation. If the successful finalize path already wrote `refund_partial`, a later automatic rollback must reverse that prior partial refund so the net ledger is exactly zero, not a credit windfall.

## Scope

1. Add an internal-only endpoint that accepts automatic refund signals for existing charge Sagas.
2. Support reason kinds `failed`, `cancelled`, and `infeasible`.
3. For `RESERVED` charges, reuse the route-level net-zero pattern from finalize failure: `+reserved refund` plus `-reserved refund_reversal`.
4. For `CHARGED` charges, apply `downstream_reject_late`; if any prior `refund_partial` rows exist, add a negative `refund_reversal` equal to that partial amount. Net ledger for the Saga must become exactly zero.
5. Return idempotent responses for already `refunded` and `rolled_back` Sagas without writing duplicate ledger or outbox rows.
6. Emit pointer-safe outbox audit payloads for automatic refund decisions. No email, phone, JWT, payment reference, or raw request body may be stored.
7. Preserve the public `/finalize` API and existing user-authenticated behavior.

## Out of Scope

- User-initiated async cancellation and prorated user-cancel refund. That is Story 5.C.2.
- PIPL data export JSON/CSV or self-service portal. Those are Stories 5.C.3, 5.C.4, and 5.C.5.
- Payment gateway refunds, invoices, taxes, payment provider IDs, or external cash movement.
- New mutable balance table, new credit account table, or a second ledger source of truth.
- New public UI or Console refund page.
- New Saga states or a broad Saga transition-matrix redesign unless implementation proves unavoidable.
- Automatic refund for `completed` terminal Sagas. `COMPLETED` means delivery has been acknowledged by the Saga; post-completion disputes need a later ops/legal flow.

## Acceptance Criteria

1. `POST /v1/billing/charges/{charge_id}/refund-auto` exists and is protected by `require_internal_service`. It must not accept user JWTs as sufficient authorization.
2. Request body validates:
   - `reason`: one of `failed`, `cancelled`, `infeasible`;
   - `source`: bounded pointer label, default `solver_orchestrator`;
   - `source_ref`: bounded pointer string for the downstream task/status event;
   - optional `elapsed_seconds >= 0`.
3. Missing charge returns 404 RFC 7807. Non-charge Saga types, including `topup`, return 409 and do not mutate ledger, Saga state, or outbox.
4. `PENDING` charges return 409 `Refund Not Applicable` with no ledger mutation. A pending charge has not been reserved or charged, so there is no refund to issue in this story.
5. `RESERVED` charge + automatic `failed|cancelled|infeasible` signal transitions to `refunded`, writes one positive `kind="refund"` row and one negative `kind="refund_reversal"` row in the same DB transaction, and leaves user balance unchanged.
6. `CHARGED` charge with no prior partial refund transitions to `rolled_back`, writes one positive `kind="refund"` row equal to the reserved amount, and leaves the Saga ledger sum exactly zero.
7. `CHARGED` charge with prior `refund_partial` rows transitions to `rolled_back`, writes the normal positive `kind="refund"` row and an additional negative `kind="refund_reversal"` equal to the prior partial refund sum. The net ledger sum for that Saga is exactly zero and the balance is restored only by the actual amount the user paid.
8. Already `refunded` or `rolled_back` charges return 200 with a rebuilt response and do not add ledger rows or outbox rows.
9. `completed` and `failed` terminal charges return 409 without mutation. `completed` is outside this automatic refund story; `failed` means no money moved.
10. Every successful mutation emits pointer-safe audit evidence:
    - the Saga transition outbox event from `SagaOrchestrator.apply()`;
    - a dedicated `billing.refund_auto.detected` outbox event containing `saga_id`, `charge_id`, `from_state`, `to_state`, `reason`, `source`, `source_ref`, `refunded_amount`, and optional `elapsed_seconds`.
11. Audit payloads and ledger metadata do not contain raw amount requests, email, phone, JWT, API keys, payment refs, or raw downstream payloads. Amounts derived from ledger state are allowed.
12. Existing `/finalize` success, `/finalize` failure, charge idempotency replay, reconciler, topup, subscription, and education billing behavior remain unchanged.
13. Quality gates pass:
    - focused auto-refund route tests;
    - existing `test_charge_routes.py` regressions;
    - existing billing-service test suite;
    - `uv run ruff check apps/billing-service apps/auth-service`;
    - `uv run ruff format --check apps/billing-service apps/auth-service`;
    - `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run mypy apps/billing-service apps/auth-service`;
    - `git diff --check`.

## Tasks / Subtasks

- [x] T1: Add schemas for automatic refund request/response (AC: 1-3, 8-11)
  - [x] Add `AutoRefundRequest` with strict reason/source/source_ref/elapsed validation.
  - [x] Add `AutoRefundResponse` with charge id, state, refund mode, reserved amount, refunded amount, balance before/after, and currency.
  - [x] Export the new schemas from `billing_service.schemas`.

- [x] T2: Add route helpers for refund ledger math (AC: 5-8, 10-11)
  - [x] Reuse `_ledger_rows_for_saga()` and `_balance_for()`.
  - [x] Add a helper to sum prior `refund_partial` rows.
  - [x] Add a helper to rebuild idempotent auto-refund responses for already terminal `refunded`/`rolled_back` Sagas.
  - [x] Add a helper to write `billing.refund_auto.detected` with pointer-safe payload.

- [x] T3: Implement `POST /charges/{charge_id}/refund-auto` (AC: 1-12)
  - [x] Require internal service auth.
  - [x] Reject missing charges and non-charge Saga types.
  - [x] Reject `pending`, `failed`, and `completed` without mutation.
  - [x] For `reserved`, apply `user_cancel`, add route-level `refund_reversal`, write audit event, commit.
  - [x] For `charged`, apply `downstream_reject_late`, reverse prior partial refund if needed, write audit event, commit.
  - [x] For `refunded`/`rolled_back`, return rebuilt response with no new rows/events.

- [x] T4: Add focused tests (AC: 1-12)
  - [x] Internal auth required and missing/invalid secret rejected.
  - [x] Reserved infeasible auto-refund writes refund plus refund_reversal and preserves balance.
  - [x] Charged full-amount failed auto-refund rolls back to net-zero ledger.
  - [x] Charged partial-refund failed auto-refund reverses prior partial refund and restores only actual paid amount.
  - [x] Replay on already rolled_back/refunded is idempotent with unchanged ledger/outbox counts.
  - [x] Pending/completed/topup paths reject without mutation.
  - [x] Audit outbox payload is pointer-safe and reason/source/source_ref are present.

- [x] T5: Run verification gates and update story record (AC: 13)
  - [x] Run focused billing route tests.
  - [x] Run full billing-service tests.
  - [x] Run ruff, format check, mypy, and diff check.
  - [x] Update Dev Agent Record, File List, Change Log, and sprint status.

## Pre-Implementation Adversarial Review

### Round 1 - Boundary And Story-Scope Review

Findings:

1. The phrase "cancelled" can be misread as user-initiated cancellation. That belongs to Story 5.C.2, not this story.
2. The planning text says "用户 can request refunds", but this story's AC says "自动检测". Mixing user request forms with automatic detection would create an unreviewed public refund surface.
3. Refund after `completed` is tempting but unsafe. Existing Saga semantics make `completed` terminal after outbox delivery; changing that would be a state-machine redesign.
4. Pending charges have no reservation and no debit. Writing refund ledger rows for pending charges would create money.
5. Payment provider refunds are not Credits refunds. Introducing provider refs or gateway calls would leak into invoice/tax/payment stories.
6. PIPL export is in the same Epic but unrelated to B5 refund mechanics.
7. Adding a new audit table would duplicate the existing ledger/outbox audit pattern and create a migration without a clear need.
8. Solver-orchestrator integration is already partially handled by 5.A.4 callbacks. This story should expose the billing surface and tests, not redesign solver workflows.

Revision after Round 1:

- Scope narrowed to internal automatic refund signals only.
- User cancellation, public refund request UI, payment gateways, invoices, and PIPL exports are explicit out of scope.
- Pending and completed Sagas are rejected without mutation.
- Audit log maps to `credit_transactions` plus pointer-safe `outbox` events.

### Round 2 - Drift, Data Consistency, And Idempotency Review

Findings:

1. Directly applying `downstream_reject_late` after a partial finalize over-refunds the user because `refund_partial` already returned part of the reservation.
2. Reusing `/finalize status=failure` for `CHARGED` Sagas is invalid; `/finalize` replay returns terminal responses and does not roll back charges.
3. A retrying task monitor can duplicate audit rows if terminal replay does not short-circuit before writing `billing.refund_auto.detected`.
4. `refunded` and `rolled_back` both need rebuilt responses because no response cache exists for this new endpoint.
5. Reconciler expects rolled_back net zero. Any auto-refund implementation must prove ledger sum exactly zero after rollback.
6. Ledger metadata must distinguish automatic detection from user cancel, or Story 5.C.2 will be hard to audit later.
7. `source_ref` is an attack surface. It must be a bounded pointer string, not a raw downstream payload.
8. Existing topup Sagas can also be `completed`; blindly operating by id would corrupt topup accounting.

Revision after Round 2:

- `CHARGED` rollback now reverses prior `refund_partial` with a negative `refund_reversal` row.
- Terminal `refunded`/`rolled_back` replay returns 200 with no new ledger or outbox rows.
- Non-charge Saga types are rejected.
- Tests must assert exact Saga ledger sum zero and no duplicate row/event counts on replay.
- `source`, `source_ref`, and reason are pointer-safe and bounded.

### Round 3 - Dependency, Closure, And Audit Review

Findings:

1. The story depends on existing `require_internal_service`; enabling user JWT auth here would bypass the intended trusted-service boundary.
2. State-machine transition names are imperfect (`user_cancel` for automatic reserved refund), but changing transition names would break property tests and contract fixtures.
3. `failed` terminal Sagas can mean pre-charge guard or balance failure with no money moved; auto-refund should not try to "refund" them.
4. Outbox audit event should be in the same transaction as ledger mutation, or audit and money movement can diverge.
5. Tests must include the partial-refund rollback case because existing invariant tests only cover full-reservation rollback.
6. `refund_reversal` is already used for net-zero route compensation, so reusing it for partial-overrefund correction is consistent if metadata explains the reason.
7. Response fields should be additive and local to the new endpoint; existing finalize schemas must not change.
8. Closure requires GitHub sync after code review and fixes, not just local tests.

Revision after Round 3:

- Endpoint uses only `require_internal_service`.
- Existing state-machine triggers are reused; no new Saga states or transitions are introduced.
- Audit outbox is written in the same DB transaction as the refund mutation.
- Tests explicitly cover prior `refund_partial` reversal.
- Existing schemas and endpoints stay backward compatible.
- Definition of Done includes implementation review, fixes, tests, and GitHub sync.

## Dev Notes

### Existing Patterns To Reuse

- `require_internal_service()` from `apps/billing-service/src/billing_service/auth_dep.py`.
- `_problem_response()` for RFC 7807-like errors in `routes.py`.
- `_ledger_rows_for_saga()` and `_rebuild_finalize_response()` patterns for terminal replay.
- `SagaOrchestrator.apply()` for `user_cancel` and `downstream_reject_late`; do not write Saga state by hand.
- `CreditTransaction` as the Credits source of truth.
- `OutboxEvent` as the pointer-safe audit log.
- Topup and subscription route tests show how to monkeypatch `settings.internal_service_secret`.

### Architecture Compliance

- Billing-service owns Credits ledger and refund decisions.
- No mutable balance table; balances remain derived from `credit_transactions`.
- Saga transition plus ledger rows plus outbox audit must commit atomically in one DB transaction.
- Audit payloads are pointer-safe and bounded.
- The endpoint is internal service-to-service API, not user-facing API.

### Implementation Guardrails

- Do not implement Story 5.C.2 user-cancel semantics.
- Do not add public refund request endpoints.
- Do not mutate `completed`, `failed`, or `pending` charge Sagas.
- Do not operate on `topup` or subscription Sagas.
- Do not change existing `/finalize` response behavior.
- Do not add a new audit table.
- Do not include raw downstream payloads, emails, phones, JWTs, API keys, or payment refs in metadata/outbox.
- For `CHARGED` with prior `refund_partial`, refund actual paid amount only: `+reserved refund` plus `-sum(refund_partial) refund_reversal`.

### Suggested Test Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/test_charge_routes.py -q
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/ -q
uv run ruff check apps/billing-service apps/auth-service
uv run ruff format --check apps/billing-service apps/auth-service
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run mypy apps/billing-service apps/auth-service
git diff --check
```

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline commit: `cb0e9221d9ffe3856190fa66f91977302875a489`.
- Red phase: `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/test_charge_routes.py -q -k 'refund_auto_reserved_infeasible'` failed with 404 because `/refund-auto` did not exist.
- Green phase: focused automatic refund tests passed with 6 tests.
- Route regression: `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/test_charge_routes.py -q` passed with 30 tests and 2 existing FastAPI deprecation warnings.
- Full billing regression: `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src;apps/auth-service/src'; uv run pytest apps/billing-service/tests/ -q` passed with 266 tests and 5 existing FastAPI deprecation warnings.
- Static gates passed: ruff check, ruff format --check, mypy, and `git diff --check`.

### Completion Notes List

- Added internal-only `POST /v1/billing/charges/{charge_id}/refund-auto` for trusted failed/cancelled/infeasible detection.
- Reserved automatic refunds now reuse the existing net-zero refund plus refund_reversal audit pattern.
- Charged automatic refunds roll back via `downstream_reject_late`; prior partial refunds are reversed so the Saga ledger nets to exactly zero.
- Added pointer-safe `billing.refund_auto.detected` outbox event and focused tests for auth, net-zero ledger, partial-refund rollback, terminal replay, and rejected states.

### File List

- `_bmad-output/stories/5-c-1-refund-failed-cancelled.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/billing-service/src/billing_service/routes.py`
- `apps/billing-service/src/billing_service/schemas.py`
- `apps/billing-service/tests/test_charge_routes.py`

## Change Log

- 2026-05-30 - Story created and revised through three pre-implementation adversarial review rounds; status set to ready-for-dev.
- 2026-05-30 - Implemented internal automatic refund endpoint, audit outbox event, partial-refund rollback correction, and focused regression tests; status set to code-review.
- 2026-05-30 - Completed post-implementation code review; no patch findings, final verification passed, and story marked done.

## Senior Developer Review (AI)

Findings:

- No blocking or patch-required findings. Reviewed internal-auth boundary, non-charge rejection, pending/failed/completed rejection, terminal replay idempotency, net-zero ledger behavior, partial-refund rollback correction, and pointer-safe audit payloads.

Decision: Approved.
