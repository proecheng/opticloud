---
story_key: 5-a-9-charge-idempotency
epic_num: 5
story_num: A.9
epic_name: Billing — Charge Idempotency
status: done
priority: Critical
type: billing idempotency + cached response contract
created_by: bmad-create-story
created_at: 2026-05-30
sources:
  - _bmad-output/planning/epics.md (Story 5.A.9)
  - _bmad-output/planning/prd.md (Idempotency-Key POST contract)
  - _bmad-output/stories/5-a-4-per-formula-charging-capped.md
  - _bmad-output/stories/5-a-6-topup-never-expire.md
  - _bmad-output/stories/5-a-8-cost-telemetry-hook.md
  - apps/billing-service/src/billing_service/saga_orchestrator.py
  - apps/billing-service/src/billing_service/routes.py
  - apps/billing-service/src/billing_service/models.py
  - infra/local-init/03-billing-schema.sql
---

# Story 5.A.9 — Charge idempotency

Status: done

## Story

**As** an API client that may retry `POST /v1/billing/charges` after a network timeout,
**I want** the same `Idempotency-Key` and same request body to return the original cached charge creation response,
**so that** retries do not double-charge, do not create a second Saga, and do not drift response fields after later reserve/finalize transitions.

## Context

The current billing implementation already has partial P23 idempotency:

- `billing_idempotency_keys` stores `request_body_hash`, `saga_id`, `expires_at`, and an unused `response_body`.
- `SagaOrchestrator.start()` returns the existing Saga for same key/body and rejects same key/different body.
- `/v1/billing/charges` requires a UUID `Idempotency-Key`.

The missing part for Story 5.A.9 is the PRD contract: "24h 内同 key 同 body 返缓存 + 不重复扣 Credits；同 key 不同 body 返 409". Today a replay rebuilds the response from the current Saga and current balance. If the charge has since been reserved/finalized, a retry can return a different `current_state` or `balance_after` than the original creation response. That is not a cached result.

This story closes the charge creation endpoint only. `/reserve`, `/finalize`, topup confirmation, refunds, subscriptions, and external payment gateway idempotency remain separate contracts.

## Scope

1. Persist the successful `POST /v1/billing/charges` creation response into `billing_idempotency_keys.response_body`.
2. On same user + same key + same body replay, return that cached response body verbatim with `201`.
3. Preserve existing conflict behavior: same key + different body returns 409 and does not mutate Saga/ledger.
4. Preserve cross-tenant protection: same key from a different user returns 403 and does not leak cached response data.
5. Preserve lazy seed semantics: a replay does not seed again, create another Saga, write another ledger row, or recompute balance from current state.
6. Add tests proving response stability after reserve/finalize, conflict behavior, cross-tenant isolation, no duplicate seed/Saga, and legacy rows with missing `response_body` still degrade safely.

## Out of Scope

- Changing the existing Saga state machine.
- Changing `/charges/{id}/reserve`, `/charges/{id}/finalize`, deprecated `/confirm`, topup initiation, or topup confirmation idempotency.
- Introducing a separate idempotency table or new DB migration; `billing_idempotency_keys.response_body` already exists.
- Changing the existing `hash_body()` canonicalization, including its documented Decimal string-form limitation.
- Caching failed validation, insufficient-balance, warning-required, 401/403/409, or 5xx responses.
- Extending TTL cleanup or garbage collection for expired idempotency rows.

## Acceptance Criteria

1. On first successful `POST /v1/billing/charges`, billing-service stores a JSON-safe `ChargeResponse` body in the existing `billing_idempotency_keys.response_body` row before commit.
2. Replaying the exact same `Idempotency-Key` and request body within TTL returns the stored `response_body` verbatim:
   - same `charge_id`;
   - same `current_state`;
   - same `amount`;
   - same `balance_before`;
   - same `balance_after`;
   - same `currency`.
3. Replay after the Saga has moved to `reserved` or `charged` still returns the original cached creation response, not a response rebuilt from current Saga state or current balance.
4. Replay does not create a second Saga, does not write another signup seed row, does not write any charge/refund ledger rows, and does not create another idempotency row.
5. Same key with different body still returns 409 RFC 7807 and leaves the original cached response untouched.
6. Same key from a different user still returns 403 and never returns the owner user's cached response.
7. Existing idempotency rows with `response_body IS NULL` remain compatible: same key/body returns an equivalent current `ChargeResponse` and backfills `response_body` once, without creating a new Saga.
8. Only successful `/charges` creation responses are cached. Insufficient balance and explicit-confirmation-required responses are not stored as successful cached bodies.
9. `response_body` stores only response fields that are already returned to the caller; no raw request body, JWT, phone/email, payment ref, credit ledger internals, or payload_ref is stored there.
10. Quality gates pass:
    - focused charge idempotency tests;
    - existing charge route, topup route, property idempotency, and billing regression tests;
    - `uv run ruff check apps/billing-service`;
    - `uv run ruff format --check apps/billing-service`;
    - `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run mypy apps/billing-service`;
    - `git diff --check`.

## Tasks / Subtasks

- [x] T1: Add response-cache helpers (AC: 1, 2, 7, 9)
  - [x] Add a helper to serialize `ChargeResponse` to a plain JSON-safe dict.
  - [x] Add a helper to read the current `IdempotencyKeyRow` by key and user.
  - [x] Add a helper to persist/backfill `response_body` for a successful charge response.

- [x] T2: Integrate `/charges` replay behavior (AC: 2, 3, 4)
  - [x] Before performing seeding or balance computation, detect valid same-key/same-body cached replay.
  - [x] Return cached response directly when `response_body` exists.
  - [x] Avoid recomputing response fields from mutated Saga state on replay.

- [x] T3: Preserve conflict and security boundaries (AC: 5, 6, 8, 9)
  - [x] Keep cross-tenant key reuse as 403.
  - [x] Keep same-key/different-body as 409.
  - [x] Do not cache warning-required, insufficient-balance, auth failure, or conflict responses.
  - [x] Ensure no raw request body or sensitive fields are stored in `response_body`.

- [x] T4: Legacy compatibility (AC: 7)
  - [x] Handle same-key/same-body rows where `response_body` is null.
  - [x] Return an equivalent response using current Saga and balance, then backfill the row.
  - [x] Do not create a new Saga or idempotency row.

- [x] T5: Tests and gates (AC: 1-10)
  - [x] Add focused `test_charge_idempotency_routes.py`.
  - [x] Cover replay after reserve/finalize, no duplicate seed/Saga/idempotency rows, conflict, cross-tenant, null-response backfill, and no cache on failed business responses.
  - [x] Run focused and full billing gates.
  - [x] Update Dev Agent Record, File List, Change Log, and sprint status.

## Pre-Implementation Adversarial Review

### Round 1 — Boundary And Response Semantics Review

Findings:

1. Existing same-key replay returns the same Saga, but not the same response if the Saga state or user balance changed later.
2. If replay detection happens after lazy seeding, a retry can write a second signup seed row before discovering it is a replay.
3. Caching non-successful responses would freeze transient insufficient-balance or warning-required outcomes, which is not required by this story and could block recovery.
4. `response_body` must not become a raw request cache; it should store only the public response body.

Revision after Round 1:

- Replay detection must run before lazy seeding and before balance computation.
- Cache only successful `/charges` creation responses.
- Store only `ChargeResponse` fields that are already returned to the caller.
- Add tests for replay after finalize and no duplicate seed.

### Round 2 — Drift, Hash, And Tenant Consistency Review

Findings:

1. Recomputing the request hash differently in the route could drift from `SagaOrchestrator.start()` and cause false conflicts.
2. The existing `hash_body()` includes `saga_type`, `payload`, and `amount`; the route must use the same body shape.
3. Cross-tenant key reuse must check owner before returning cached response.
4. Existing critical scenario row 32 documents Decimal string-form sensitivity; changing hash canonicalization would widen the story unexpectedly.

Revision after Round 2:

- Reuse `hash_body()` and the exact same canonical body shape as `SagaOrchestrator.start()`.
- Keep Decimal string-form behavior unchanged.
- Check `IdempotencyKeyRow.user_id` before body hash and cached response access.
- Add cross-tenant cached replay test.

### Round 3 — Transaction, Crash, And Legacy Compatibility Review

Findings:

1. If Saga creation commits but `response_body` is not set, future replays would still have legacy/null rows.
2. If `response_body` is set after commit, a crash can leave a successful Saga with no cached response.
3. If `response_body` update happens before the response is constructed, route code can store a different shape from what it returns.
4. Backfilling legacy null rows must not mutate Saga state or write ledger rows.

Revision after Round 3:

- Build the `ChargeResponse` object first, store its `model_dump(mode='json')`, then commit in the same transaction.
- On null `response_body` replay, rebuild from existing Saga and current balance as compatibility fallback, backfill once, and return that body.
- Do not add migrations or uniqueness changes.
- Add a null-response backfill test.

## Dev Notes

### Existing Patterns To Reuse

- `validate_idempotency_key()` in `schemas.py`.
- `hash_body()` and `IdempotencyKeyRow` in `saga_orchestrator.py` / `models.py`.
- Existing `CrossTenantKeyError` and `IdempotencyConflictError` error handling.
- Existing `ChargeResponse` formatting in `routes.py`.
- Existing route-test fixtures from `test_charge_routes.py`.

### Hard Boundaries

- Do not change Saga state transitions.
- Do not change `billing_idempotency_keys` schema.
- Do not cache request bodies.
- Do not cache topup or finalize responses in this story.
- Do not change hash canonicalization.

### Suggested Test Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_charge_idempotency_routes.py apps/billing-service/tests/test_charge_routes.py apps/billing-service/tests/test_topup_routes.py -q
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_property_saga_walks.py apps/billing-service/tests/test_critical_idempotency.py -q
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/ -q
uv run ruff check apps/billing-service
uv run ruff format --check apps/billing-service
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run mypy apps/billing-service
git diff --check
```

## Dev Agent Record

### Implementation Plan

1. Add charge-specific idempotency helpers that reuse `hash_body()` with the same canonical input shape as `SagaOrchestrator.start()`.
2. Read an existing `billing_idempotency_keys` row before lazy seeding and balance computation.
3. Return persisted `response_body` for same user/key/body replay, reject cross-tenant reuse before exposing cached data, and preserve 409 on body hash mismatch.
4. Persist the first successful `ChargeResponse.model_dump(mode="json")` in the same transaction as Saga creation.
5. Backfill legacy `response_body IS NULL` rows from the existing Saga without creating a new Saga or idempotency row.
6. Add focused route tests for replay stability, conflict immutability, tenant isolation, legacy null backfill, and non-successful response non-caching.

### Debug Log

- Red phase: `test_charge_idempotency_routes.py` initially failed 4/6 because `/charges` replay rebuilt response from current Saga/balance, did not persist `response_body`, did not backfill legacy null rows, and the cross-tenant test needed an inserted second user row.
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_charge_idempotency_routes.py -q` — 6 passed, 1 warning.
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_charge_idempotency_routes.py apps/billing-service/tests/test_charge_routes.py apps/billing-service/tests/test_topup_routes.py -q` — 39 passed, 3 warnings.
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_property_saga_walks.py apps/billing-service/tests/test_critical_idempotency.py -q` — 18 passed.
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/ -q` — 215 passed, 3 warnings.
- `uv run ruff check apps/billing-service` — passed.
- `uv run ruff format --check apps/billing-service` — passed after formatting routes/test file.
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run mypy apps/billing-service` — passed.
- `git diff --check` — passed.

### Completion Notes

- Successful `/v1/billing/charges` creation now stores the public `ChargeResponse` JSON in `billing_idempotency_keys.response_body` before commit.
- Same user/key/body replay now returns the cached creation response before seeding or balance computation, so later reserve/finalize transitions cannot drift `current_state` or balances.
- Same-key/different-body and cross-tenant replay are rejected before cached response access; failed business responses still do not create or cache successful response bodies.
- Legacy same-key/body rows with `response_body IS NULL` are rebuilt once from the existing Saga and backfilled without creating a new Saga or idempotency row.

### File List

- `_bmad-output/stories/5-a-9-charge-idempotency.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/billing-service/src/billing_service/routes.py`
- `apps/billing-service/tests/test_charge_idempotency_routes.py`

## Change Log

- 2026-05-30 — Story created and revised through three pre-implementation adversarial review rounds.
- 2026-05-30 — Implemented charge creation response caching, replay short-circuit, legacy null backfill, focused tests, and quality gates; status set to code-review.
- 2026-05-30 — Completed post-implementation code review; fixed legacy missing-Saga rollback detail safety and strengthened AC4/AC8 tests; status set to done.

## Senior Developer Review (AI)

Outcome: Approved after patch.

Review layers:

- Blind Hunter: diff-level correctness, transaction ordering, and likely integration failures.
- Edge Case Hunter: replay boundaries, malformed/legacy idempotency rows, tenant isolation, and ledger mutation risk.
- Acceptance Auditor: checked implementation against AC1-AC10 and story hard boundaries.

Findings and resolution:

- [x] [Low] `_legacy_charge_response_from_idempotency_row()` built the missing-Saga error detail from `row.saga_id` after `session.rollback()`, which could trigger SQLAlchemy async expired-attribute loading on a damaged legacy row. Fixed by copying `saga_id` before rollback.
- [x] [Low] AC4 and AC8 test evidence could be stronger. Added focused assertions that `/charges` replay after finalize does not add charge/refund ledger rows and that explicit-confirmation-required responses do not populate `response_body`.

Residual risk:

- Legacy `response_body IS NULL` rows can only be reconstructed from the current Saga state and current balance; this is intentionally a compatibility fallback, not a guarantee that pre-story historical creation responses can be recovered exactly after later transitions.

## Verification

- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_charge_idempotency_routes.py apps/billing-service/tests/test_charge_routes.py apps/billing-service/tests/test_topup_routes.py -q` — 39 passed, 4 warnings.
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_property_saga_walks.py apps/billing-service/tests/test_critical_idempotency.py -q` — 18 passed.
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/ -q` — 215 passed, 4 warnings.
- `uv run ruff check apps/billing-service` — passed.
- `uv run ruff format --check apps/billing-service` — passed.
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run mypy apps/billing-service` — passed.
- `git diff --check` — passed.
