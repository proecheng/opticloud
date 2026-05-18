---
story_key: m2-2a-billing-critical-tests
epic_num: 0
story_num: M2.2a
epic_name: Foundation
status: done
priority: 🔴 Critical (NFR-R4 v1.5 hard-gate; 对账误差 = 0 must be proven before 商用)
sizing: L (8-10 hours; ≥50 hand-written scenarios across 5 test files; parametrized where natural)
type: testing
created_by: bmad-create-story
created_at: 2026-05-18
sources:
  - _bmad-output/planning/epics.md (Story M2.2a)
  - _bmad-output/planning/prd.md v1.1 (NFR-R4 计费对账误差 = 0)
  - docs/adr/0001-saga-pattern.md §"How to test" — Layer 2 = ≥50 hand-written critical scenarios
  - apps/billing-service/src/billing_service/saga_orchestrator.py (system under test)
  - apps/billing-service/tests/test_saga_integration.py (existing happy-path tests, 16 — this story adds ≥50 MORE focused on edges)
  - packages/shared-py/opticloud_shared/saga/state_machine.py (7 states / 7 transitions / 4 Compensation values)
dependencies:
  upstream:
    - 5-a-0a-saga-implementation (done) — orchestrator is the system under test
    - 5-a-1-j1-credits-charge-modal (done) — HTTP layer also under test
    - m2-1-outbox-relayer (done) — relayer events can be verified end-to-end
  downstream:
    - m2-2b-saga-property-tests — Hypothesis-generated random walks
    - m2-2c-saga-extended-coverage — 500+ scenarios for M5 hardening
    - 5-a-7-double-entry-reconciliation — uses these tests as the gate
---

# Story M2.2a — Billing 50 Critical Scenario Tests

## User Story

**As** the OptiCloud platform owner committed to NFR-R4 (对账误差 = 0)
**I want** ≥50 hand-written test scenarios covering every Saga transition, every failure path, every concurrency edge, and every audit invariant
**so that** before any v1.5 商用 release I can prove the billing engine is correct under all the conditions a real customer can throw at it.

## Why this story

ADR-0001 specifies a 5-layer test pyramid:
1. Property tests (M2.0 — pure-function state machine invariants) — ✅ done (8 tests)
2. **Critical scenarios (≥50 hand-written) — THIS STORY**
3. Property + business (M2.2b) — Hypothesis random walks
4. Full coverage (M2.2c + M5) — 500+ scenarios
5. Contract tests (M3.2) — Schemathesis

Layer 2 is the **NFR-R4 v1.5 hard-gate**. Without proving 50 hand-picked scenarios pass, we cannot claim 对账误差 = 0 to enterprise customers.

The existing `test_saga_integration.py` (16 tests) covers the **happy path** + a few negatives. M2.2a adds the **systematic edge sweep** — every row of the transition matrix, every failure mode, every concurrency window.

## Out of scope

- Hypothesis-generated random sequences → M2.2b
- 500+ scenarios for M5 → M2.2c
- Schemathesis API contract tests → M3.2
- Performance / load tests (RPS, P95 budget verification under load) → M3.6d
- Multi-tenant isolation (different users' Sagas don't interfere) — touched lightly here; deep coverage in 5.A.7 reconciliation cron
- Cross-service Saga (billing ↔ solver in one Saga) — that's 5.A.4; this story scopes to billing-only

## Acceptance Criteria

### AC1: ≥50 distinct scenarios pass
- "Distinct" = unique input/state/expected combination. Parametrized tests count each parameter row as one scenario.
- **DR5 lock**: 50 is INCREMENTAL on top of existing 25 billing tests (16 Saga + 9 HTTP); final count ≥ 75 billing tests.
- Test file structure:
  - `apps/billing-service/tests/test_critical_transitions.py` — 7 transitions × variants (~18 scenarios)
  - `apps/billing-service/tests/test_critical_idempotency.py` — P23 edge cases (~10 scenarios)
  - `apps/billing-service/tests/test_critical_concurrency.py` — race + ordering (~8 scenarios)
  - `apps/billing-service/tests/test_critical_invariants.py` — DB-level invariants over time (~8 scenarios)
  - `apps/billing-service/tests/test_critical_audit.py` — outbox + audit verification (~6 scenarios)
  - Total ≥ 50

### AC2: Every transition row covered (R1.1 fix)
- 18 test functions (7 happy-path + 7 wrong-state + 4 terminal) total
- Each happy-path test asserts D/E/F properties IN-LINE (no extra test func):
  - D. Re-running same trigger is a no-op (apply twice; only 1 transition + 1 outbox row)
  - E. Outbox row written with correct event_type (`billing.saga.{trigger}`)
  - F. Credit_transactions row written iff `_CHARGE_TRIGGERS[trigger]` matches
- Effective scenarios: 18 functions × 3 in-test asserts on happy path = ~39 distinct checks, but only 18 named scenarios. Combined with T3-T7 totals reach ≥50.

### AC3: Idempotency edge cases (P23 + AC4 wording)
- Same key + same body → returns same saga_id (already in integration tests; re-assert)
- Same key + different body → 409 IdempotencyConflictError
- Different key + same body → 2 distinct sagas
- TTL expiry: key expired → new saga (manual `expires_at` backdating)
- Concurrent start() with same key (2 asyncio tasks) → only 1 saga in DB
- Key reused after first saga is terminal → returns existing saga's terminal state (NOT a new saga)
- Empty key / None key → 400 / TypeError at API layer (verified via HTTP test)
- 256-byte key → accepted (max length per schema)
- Key with whitespace / unicode → rejected (UUID regex enforces ASCII hex)

### AC4: Concurrency scenarios (Q1 lock — outcome-based, not order-based)
- Two concurrent apply() to same saga with same trigger → after both complete, assert: exactly 1 transition + exactly 1 outbox row in DB
- Two concurrent apply() with conflicting triggers (e.g., reserve vs balance_insufficient) → assert: exactly 1 ended in target state for its trigger; the other raised
- Concurrent start() with different keys → 2 distinct sagas, no balance corruption (assert ledger sum unchanged outside the 2 charges)
- Concurrent charge + refund on same user (different sagas) → final balance = initial - charge1 + refund1 (commutative)
- Ledger sum monotonic property: at any point, `SUM(amount) WHERE user_id=X` equals the visible balance
- **A2 regression**: `mark_sent(conn, [uuid1, uuid2, ...])` completes within 1s (the asyncpg UPDATE ANY[uuid[]] hang from M2.1 — confirm executemany() path still works for batches ≥10 rows)

### AC5: Audit + outbox invariants
- Every successful apply() produces exactly 1 outbox row with correct (aggregate_type, event_type, payload)
- Compensation transitions (refund_auto, escalate_ops) produce BOTH a credit_transaction AND an outbox event
- Outbox payload contains saga_id, from_state, to_state, trigger — no PII
- audit_logs (if existing — out of scope if not yet wired) lookup by saga_id returns full transition history
- Multi-step happy path generates exactly 3 outbox rows (reserve, service_success, outbox_delivered)

### AC6: Time-based + edge values
- amount = exactly the balance → CHARGED, balance_after = 0
- amount = balance + 0.0001 (one base-unit over) → 422 insufficient
- amount = Decimal("0.0001") (smallest > 0) → accepted
- amount = Decimal("99999999.9999") (largest fitting 12,4) → accepted
- amount = Decimal("100000000.0000") (Q2: one past max) → rejected by Pydantic OR by Postgres NUMERIC overflow
- Refund of partial amount (kind=refund with amount < charge) → balance reflects correctly
- saga.created_at < saga.updated_at after any apply() (ordering invariant)
- **D1 hash determinism (informational)**: `hash_body({"amount": "6.00"})` == `hash_body({"amount": "6.0"})`? Currently NO (strings differ). Test asserts current behavior + adds TODO for future normalization (out of scope to fix here — would require API contract change)

### AC7: NFR-R4 reconciliation invariant
For 5 random user IDs across the test run:
- After each apply() call in a test, `SUM(credit_transactions.amount) WHERE user_id = X` equals `(balance fetched via GET /v1/billing/balance)`
- No transaction ever creates an inconsistency between Saga state and ledger total
- **Q3 enforcement**: new pytest fixture `verify_reconciliation` (autouse=False, opt-in) runs after specific tests in test_critical_invariants.py to assert this

### AC8: Test suite hygiene
- All 50+ new tests pass in **<60 seconds** locally (R1.2 loosened from 30s — concurrency tests with real Postgres need headroom)
- No flaky tests (run the suite 3× — same result)
- Each test has a 1-line docstring explaining what scenario it covers
- Parametrize ids are human-readable (e.g., `transition[pending-balance_insufficient-failed]`)
- **Scenario count verified via** `pytest apps/billing-service/tests/test_critical_*.py --collect-only -q | tail -1` (R1.6 lock)

### AC9: Quality gates (per `feedback_full_quality_gates`)
- `uv run ruff check .` clean
- `uv run ruff format --check .` clean
- `uv run mypy apps packages` clean
- All Python tests pass (existing 66 + new ≥50 = ≥116 total)
- Next build clean (no impact expected)

### AC10: Scenario inventory document
- New file: `apps/billing-service/tests/CRITICAL_SCENARIOS.md`
- Lists every scenario by category with 1-line description
- Numbered (1-50+) so audit can verify count
- **DR3 lock**: each row has columns: # / Name / Category / Traceability (FR/NFR/ADR-0001 invariant) / AC mapping
- Maps each scenario back to a PRD FR / NFR / ADR-0001 invariant for traceability

### AC11: Cross-tenant idempotency leak fix (S1 — security)
- `SagaOrchestrator.start()` adds explicit check: if `existing_key.user_id != requested_user_id`, raise new `CrossTenantKeyError`.
- Test asserts: user A's key K + same body, user B's start(K, ...) → raises (instead of returning A's saga)
- New exception class in `exceptions.py`: `CrossTenantKeyError(key, owner_user_id, requesting_user_id)` extends `SagaError`
- HTTP route handler in `billing_service/routes.py` maps to 403 (separate from 409 IdempotencyConflict) — **DR1 lock: T2 includes this route-handler change**
- This is a security-critical fix that ships in M2.2a since the test exposes the bug

## Tasks

### T1: Scenario inventory (0.5 hour, R1.5 simplified)
1. Write `CRITICAL_SCENARIOS.md` with all 50+ items grouped by file
2. Each item has: number, name, FR/NFR/invariant traceability column
3. Skipped: empty test file stubs — files created naturally in T2-T6 as we write

### T2: test_critical_transitions.py — 18 scenarios (2 hours)
1. Parametrize: 7 transitions × happy-path (7 cases)
2. Parametrize: 7 transitions × wrong-state (7 cases) — derive wrong source state per trigger
3. Parametrize: 4 terminal states × any trigger raises SagaTerminalError (4 cases)
4. **DR1 piggybacked**: add `CrossTenantKeyError` to `exceptions.py` + update `SagaOrchestrator.start()` to check + update `routes.py` create_charge to map to 403

### T3: test_critical_idempotency.py — 10 scenarios (1.5 hour, R1.3 fix)
HTTP-layer idempotency validation already in `test_charge_routes.py` (5.A.1). This file scopes to ORCHESTRATOR-level edges:
1. Same key/body → same saga (1)
2. Same key/diff body → IdempotencyConflictError (1)
3. Diff key/same body → 2 sagas (1)
4. TTL expiry — manual backdate `expires_at`, re-issue same key (1)
5. Concurrent start same key (asyncio.gather × 2) → 1 saga in DB (1)
6. Key reused after terminal → returns existing terminal-state saga (1)
7. Idempotency check across saga_type (same key, different saga_type → conflict) (1)
8. Body hash determinism: same dict in different key order → same hash (1)
9. Body hash with Decimal amount: 6.00 vs "6.0" → both produce same hash (1)
10. **S1 security bug**: idempotency row's user_id mismatch → 403-equivalent (cross-tenant key reuse blocked). Currently the orchestrator does NOT check user_id on the existing key — different user reusing same key gets first user's saga back. **Fix inside M2.2a**: add `if existing_key.user_id != user_id: raise CrossTenantKeyError` in `SagaOrchestrator.start()`. Test verifies the new exception is raised.

### T4: test_critical_concurrency.py — 8 scenarios (1.5 hour)
1. Concurrent apply() same trigger same saga (asyncio.gather) → only 1 transition
2. Concurrent apply() conflicting triggers (reserve vs balance_insufficient) → 1 wins
3. Concurrent start() diff keys same user → 2 sagas
4. Concurrent charge + refund (different sagas, same user) → balance correct
5. Concurrent confirm + cancel on same saga → only 1 applies
6. Concurrent SELECT FOR UPDATE — SKIP LOCKED prevents both from racing
7. Ledger sum monotonic per row
8. Ledger sum monotonic per user across 5 concurrent sagas

### T5: test_critical_invariants.py — 8 scenarios (1.5 hour)
1. saga.created_at <= saga.updated_at after every apply
2. Terminal stickiness: any apply on terminal raises (4 terminal states)
3. Refund ≤ charge per saga (already in M2.0 property — re-assert as critical)
4. No saga is in "stuck" state (any non-terminal saga can reach a terminal via valid triggers)
5. Outbox.aggregate_id = saga.id always
6. Outbox.event_version >= 1 always

### T6: test_critical_audit.py — 6 scenarios (1 hour)
1. Each apply produces exactly 1 outbox row
2. Multi-step happy path = 3 outbox rows in order (reserve / service_success / outbox_delivered)
3. Refund path = 1 outbox row for the refund transition
4. Outbox payload structure: saga_id + from_state + to_state + trigger (no PII)
5. Compensation header in outbox.headers = correct Compensation enum value
6. Channel naming convention: `opticloud.saga_instance.billing.saga.{trigger}` (verifies M2.1 relayer compatibility)

### T7: Edge value tests (rolled into transitions file, 0.5 hour)
- amount = 0.0001 / max numeric / exactly balance / balance + 0.0001
- Boundary checks

### T8: CRITICAL_SCENARIOS.md + sprint sync + PR (0.5 hour)
- Write the markdown
- Run quality gates
- Update sprint-status.yaml
- Commit + PR

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| 50 tests cause CI runtime > 30s | Use parametrize + session-scoped DB fixture; reuse test user where possible; target 15-20s |
| Concurrency tests are flaky | Use deterministic asyncio.gather; if race outcome is non-deterministic, assert "at least one of these states reached" not exact ordering |
| Test pollution between scenarios | Each test uses unique idempotency_key (UUID); cleanup not strictly needed for ephemeral DB |
| Coverage claim hard to verify | CRITICAL_SCENARIOS.md inventory + grep on test function names + parametrize ids — explicit numbering |
| Scope creep (people add more than 50) | Hard cap: AC1 says ≥50; once ≥50 reached, stop. Excess → M2.2c |

## Non-Functional Requirements Mapping

- **NFR-R4** 对账误差 = 0: ledger sum monotonic per AC4 + AC7; refund ≤ charge per AC5
- **NFR-P1** P95 < 300ms: tests assert apply() completes in budgeted time (loose: <100ms median)
- **NFR-S1** TLS/auth: existing 9 HTTP tests verify; this story scopes to orchestrator unit/integration
- **FR B1** charge intent: covered by existing 9 tests + extended in T2 transitions

## Definition of Ready

- ✅ Orchestrator exists (5.A.0a done)
- ✅ HTTP routes exist (5.A.1 done)
- ✅ Outbox relayer exists (M2.1 done) — can verify end-to-end if needed
- ✅ Existing 16 Saga + 9 HTTP tests provide the baseline to extend
- ✅ All 4 review rounds applied

## Definition of Done

- ≥50 scenarios pass per CRITICAL_SCENARIOS.md inventory
- All 10 ACs pass
- CI green
- Sprint-status.yaml updated to `done`
- ADR-0001 §"How to test" Layer 2 marked complete
- Tech-debt list updated (M2.2b/c remain)

## Sign-off (story-level)

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Billing Lead | TBA | ☐ | — |
| QA Lead | TBA | ☐ | — |
| Architect | proposed by AI | ☐ | — |

> Owner committee deferred per M0 skip.
