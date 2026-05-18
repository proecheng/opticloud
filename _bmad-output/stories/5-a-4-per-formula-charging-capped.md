---
story_key: 5-a-4-per-formula-charging-capped
epic_num: 5
story_num: A.4
epic_name: Billing — Credits & Saga
status: ready-for-dev
priority: 🟢 High (production-readiness — splits the 5.A.1 confirm shortcut into proper 2-phase Saga; closes the cross-service gap noted in 5.A.1 §"Out of scope")
sizing: M-L (6-8 hours; billing finalize endpoint + per-second pricing + solver-side HTTP callback)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-18
sources:
  - _bmad-output/planning/epics.md (Story 5.A.4 — Per-formula charging capped, B4)
  - _bmad-output/planning/prd.md v1.1 (FR B4 per-formula charging; NFR-R4 对账误差=0)
  - docs/adr/0001-saga-pattern.md (Hybrid Saga 7-state machine; transition matrix)
  - apps/billing-service/src/billing_service/saga_orchestrator.py (apply() — already supports reserve / service_success / user_cancel triggers)
  - apps/billing-service/src/billing_service/routes.py (5.A.1 simplified /confirm — to be split here)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py:128 (post_optimization — solver entry to wire billing callback into)
  - apps/solver-orchestrator/src/solver_orchestrator/solvers.py:53 (solve_lp returns LPSolveResult.solve_seconds — actual elapsed time)
  - packages/shared-py/opticloud_shared/saga/state_machine.py (State + Transition matrix — service_success / user_cancel triggers)
dependencies:
  upstream:
    - 5-a-0a-saga-implementation (done) — SagaOrchestrator already supports the 2-phase apply
    - 5-a-1-j1-credits-charge-modal (done) — billing HTTP API + ChargeModal foundation
    - m2-1-outbox-relayer (done) — outbox relayer running (we DON'T use it here; v1 uses direct HTTP)
    - 3-1-j1-lp-solve (done) — solver-orchestrator + LPSolveResult.solve_seconds
  downstream:
    - 5-a-5-p5-warning-modal — pre-charge guard rule (separate)
    - 5-a-6-topup-flow — topup payment integration
    - 5-a-7-billing-reconciliation — daily reconciliation; uses ledger this story produces
    - 5-b-1-five-plans — per-plan pricing replaces the hardcoded LP rate from this story
---

# Story 5.A.4 — Per-formula charging capped (B4)

## User Story

**As** a paying user submitting an LP problem with `max_solve_seconds=60`
**I want** to be charged only for the actual solver time used (e.g. 5s → ¥0.50, not the full 60s × rate cap)
**so that** I am not over-billed when solves finish faster than my safety cap, and I am protected from runaway costs when solves hit the cap.

## Why this story

Two coupled gaps from the J1 vertical slice that this story closes together:

1. **Per-formula billing fairness (epics 5.A.4 AC)** — Today 5.A.1 charges a flat hardcoded ¥6 regardless of solve time. Users running 100 fast solves pay 100×¥6=¥600 even if each solve takes 0.1s; the math is unfair and the unit economics make no sense.

2. **5.A.1 architectural debt (5.A.1 §"Out of scope" line 51)** — Today the web app calls `POST /v1/billing/charges/{id}/confirm` which does BOTH `reserve` AND `service_success` transitions in one server call. This shortcut bypasses the proper Saga 2-phase commit and means there's no checkpoint where billing knows "downstream actually succeeded with N seconds of work." Without the split, per-formula charging is impossible.

This story splits the 5.A.1 shortcut into proper 2-phase **and** wires solver-orchestrator to call back into billing with the actual `elapsed_seconds`, atomically committing the correct amount.

**Why not event-driven via outbox-relayer?** — Architecturally cleaner; deferred to M3 (production hardening). For v1 the sync HTTP callback is +50ms P95 and simpler to reason about. The same flow can be migrated to outbox later without changing the Saga state contract — only the transport changes.

## Out of scope

- **Per-task-type pricing** (LP vs MILP vs VRPTW different ¥/sec) → 5.B.1 plan-based pricing
- **Event-driven cross-service Saga** (outbox-relayer transport instead of direct HTTP) → M3 hardening
- **Pre-charge guard** (balance < monthly budget, etc.) → 5.A.5
- **Async-mode optimizations** — this story handles sync mode only; async (`mode="async"`) wiring to billing comes with 3.3 sync/async mode separation
- **Solver outbox table** — solver-orchestrator does NOT get its own outbox in this story (would require a second relayer); deferred to M3
- **Property tests for random elapsed_seconds** — covered by M2.2b Hypothesis layer; here we do hand-written boundary tests
- **Billing reconciler job** (retries finalize for rows with `billing_finalize_failed=true`) → new sprint-status backlog item `m2-2c-billing-reconciler-job`

## Acceptance Criteria

### AC1: Billing exposes split 2-phase API (replaces 5.A.1 `/confirm`)

`POST /v1/billing/charges/{id}/reserve` (NEW)
- Applies only the `reserve` trigger: PENDING → RESERVED
- Body: empty
- Response: `{ charge_id, current_state: "reserved", amount_reserved: "6.00", balance_after_reserve: "44.00" }` (no debit yet — `amount_reserved` is informational, balance is unchanged)
- 404 if saga not found, 403 if user_id mismatch, 409 if already past PENDING

`POST /v1/billing/charges/{id}/finalize` (NEW)
- Body:
  ```json
  {
    "elapsed_seconds": 5.0,        // float, ≥ 0; from solver-orchestrator LPSolveResult.solve_seconds
    "status": "success" | "failure",
    "failure_reason": "string|null"  // populated when status="failure"; null otherwise
  }
  ```
- Behavior when `status="success"`:
  - **DR1**: `max_solve_seconds` is read from `saga.payload_ref["max_solve_seconds"]`. For legacy sagas (5.A.1 path) where the key is absent, fall back to `settings.charge_max_solve_seconds_default` (60.0). Log a `INFO` line `billing.finalize.legacy_saga_default_max` when fallback fires (so we can count migration progress).
  - **Compute actual_amount** (AC3 below): `actual_amount = min(elapsed_seconds, max_solve_seconds_from_saga) × rate_per_second`, **rounded to 2 decimals using ROUND_HALF_UP** (banker rounding NOT used — RD2 fix: user-friendly, predictable)
  - **Cap**: actual_amount cannot exceed the originally reserved amount (defense-in-depth — even if elapsed somehow exceeds max, billing won't over-charge)
  - **Floor**: actual_amount ≥ Decimal("0.01") so a sub-cent solve still charges a minimum cent (prevents zero-charge abuse)
  - Apply `service_success` trigger: RESERVED → CHARGED
  - Write a `kind="charge"` ledger row of `-actual_amount`
  - If `actual_amount < reserved_amount`: write an additional `kind="refund_partial"` ledger row of `+(reserved - actual)` in the SAME transaction
  - Final balance change: `balance_after = balance_before - actual_amount` (reserved minus partial refund = actual)
- Behavior when `status="failure"`:
  - Apply `user_cancel` trigger: RESERVED → REFUNDED
  - **R1.1 fix**: The orchestrator's `_CHARGE_TRIGGERS[user_cancel] = ("refund", +1)` writes a `+amount` refund row. But the RESERVED state had no preceding debit (5.A.1 simplified confirm wrote debit during service_success, not reserve). To keep the ledger net-zero, the finalize route writes a **compensating** `kind="refund_reversal"` row of `-amount` AFTER `apply("user_cancel")`, in the same DB transaction. Net effect: ledger has both `+amount/refund` and `-amount/refund_reversal` rows, sum = 0, balance unchanged. This is auditable (both rows visible in reconciliation) and additive (no orchestrator change).
  - `failure_reason` recorded in saga.last_error + outbox event payload
- Idempotency: re-calling finalize with the same body when state is already CHARGED or REFUNDED returns the **rebuilt** response (200 OK, not 409 — uses Saga `_is_idempotent_replay` path). **R1.3 fix — rebuild logic**: No response is persisted. On replay, the route queries the saga + its associated `credit_transactions` rows by `saga_id` (sum of `kind=charge` rows = actual; sum of `kind=refund_partial` rows = refund_partial); then re-derives `reserved_amount` from `saga.amount` and re-computes `balance_before` as `balance_now + actual_amount - refund_partial_amount`. This rebuild is deterministic because ledger is append-only. Verified by AC7 row #14.
- Re-calling finalize from RESERVED with a different body (different elapsed_seconds) → 409 conflict (RD4: state already finalized once, can't redo)
- Headers: `Authorization: Bearer <JWT>` required (re-uses billing `require_user` from 5.A.1)

`POST /v1/billing/charges/{id}/confirm` (DEPRECATED — kept for back-compat)
- Marked deprecated in OpenAPI docstring with `deprecated=True`
- Still works identically to 5.A.1 (reserve + service_success in one call) for the /demo/charge page
- Returns deprecation header: `Deprecation: true` and `Link: </v1/billing/charges/{id}/reserve>; rel="successor-version"`
- Slated for removal in M3

### AC2: Pricing constants in billing config

New `settings.lp_rate_per_second: Decimal = Decimal("0.10")` (CNY per second, LP-only for v1)
New `settings.charge_min_amount: Decimal = Decimal("0.01")` (floor — prevents zero-charge from sub-cent solves)
New `settings.charge_max_solve_seconds_default: float = 60.0` (used when saga.payload_ref doesn't carry max — defense default)

Reasoning (recorded in story so future readers don't ask):
- 0.10 ¥/sec × 60s = ¥6.00 — matches the 5.A.1 demo hardcoded amount exactly, so existing /demo/charge keeps working with no UI change
- 0.10 ¥/sec for LP is the "M2 starter price"; M3 retail pricing will be per-plan and per-formula (5.B.1)

### AC3: Amount computation — deterministic + Decimal-safe

In a new module `apps/billing-service/src/billing_service/pricing.py`:

```python
from decimal import Decimal, ROUND_HALF_UP

def compute_charge_amount(
    elapsed_seconds: float,
    max_solve_seconds: float,
    rate_per_second: Decimal,
    min_amount: Decimal,
    reserved_amount: Decimal,
) -> Decimal:
    """Per-formula charge amount, capped + floored.

    Returns:
        Decimal quantized to 0.01 CNY, in range [min_amount, reserved_amount].

    Behavior:
        - elapsed_seconds is clamped to [0, max_solve_seconds]
        - amount = elapsed_clamped × rate_per_second, quantized HALF_UP to 2 decimals
        - if amount < min_amount → return min_amount
        - if amount > reserved_amount → return reserved_amount (defensive cap)
    """
```

Pure function — no DB, no side effects, no logging. Easy to unit test deterministically. 9 hand-written boundary tests in AC7.

### AC4: Ledger semantics — auditable + reconciliation-safe (NFR-R4)

The credit_transactions ledger is the source of truth for NFR-R4 (对账误差 = 0). For a per-formula charge with partial refund:

**Today (5.A.1):**
```
INSERT credit_transactions(amount=-6.00, kind=charge)         -- only row
```

**5.A.4 success path with actual < reserved (e.g. elapsed=5s, max=60s):**
```
INSERT credit_transactions(amount=-0.50, kind=charge)            -- AC1 service_success
INSERT credit_transactions(amount=+5.50, kind=refund_partial)    -- (reserved - actual)
                                                                  -- BOTH in same DB tx
```

**5.A.4 success path with actual == reserved (elapsed clamped to max):**
```
INSERT credit_transactions(amount=-6.00, kind=charge)         -- no refund row needed
```

**5.A.4 failure path (status="failure" or user_cancel) — R1.1 fix:**
```
INSERT credit_transactions(amount=+6.00, kind=refund)              -- from apply("user_cancel")
INSERT credit_transactions(amount=-6.00, kind=refund_reversal)     -- compensating row, written by route
                                                                    -- BOTH in same DB tx; net effect = 0
```
Both rows are present in the audit trail (reconciliation can see "refund issued + reversed because reservation was never debited"). Balance is unchanged. This is verified by AC7 row #13.

The orchestrator's existing `apply()` writes the `kind=charge` row automatically for `service_success`. The `refund_partial` row is written by the new finalize route AFTER calling `apply()`, within the same session — committed atomically. **No new outbox event for the partial refund** (RD3: it's part of the same Saga transition; the existing `billing.saga.service_success` outbox event payload includes both amounts).

Outbox event payload extension (additive — safe for M2.1 relayer subscribers):
```json
{
  "saga_id": "...",
  "trigger": "service_success",
  "from_state": "reserved",
  "to_state": "charged",
  // NEW in 5.A.4:
  "reserved_amount": "6.0000",
  "actual_amount": "0.5000",
  "refund_partial_amount": "5.5000",
  "elapsed_seconds": 5.0
}
```

### AC5: Solver-orchestrator callback into billing

Solver-orchestrator gets a billing-aware code path. **Opt-in via header** so existing 5.A.1 /demo/charge flow stays untouched.

When `POST /v1/optimizations` is called with header `X-Billing-Charge-Id: <UUID>`:
1. Before solving: solver calls `POST /v1/billing/charges/{X-Billing-Charge-Id}/reserve` (sync HTTP); if it returns 4xx, solver returns 422 with `errors[].field_path="header.X-Billing-Charge-Id"` and does NOT solve
2. Solve runs as today; `result.solve_seconds` captures actual elapsed
3. After solve completes (success OR failure):
   - On success: solver calls `POST .../finalize` with `{elapsed_seconds: result.solve_seconds, status: "success"}`
   - On failure (infeasible/unbounded/timeout/error): solver calls `POST .../finalize` with `{elapsed_seconds: result.solve_seconds, status: "failure", failure_reason: "<short>"}`
4. If the finalize call fails (5xx, timeout, network) — **Q4 fix: single attempt, no inline retry**:
   - 1 attempt with 2s timeout
   - On failure: log structured `WARNING` `billing.finalize.failed` with `{saga_id, status, elapsed_seconds, exception_type}` + write `opt.error.billing_finalize_failed=true` to the optimization row, and STILL return the solve result to the caller
   - Rationale: solve response P95 must stay < 200ms warm. Inline retry would push P95 into 6s territory on billing outage. A separate reconciler job (M3 scope; tracked as new tech-debt `m2-2c-billing-reconciler-job`) re-drives finalize for `billing_finalize_failed=true` rows. The `reserve` call uses the same single-attempt policy (failure surface = 422 to caller, "billing temporarily unavailable").
5. The HTTP call uses `httpx.AsyncClient` with timeout=2s per attempt. **R1.2 fix — auth model**: Solver receives caller's `Authorization: Bearer sk-...` API-Key header. Billing's `require_user` only accepts JWT. To bridge: billing's `auth_dep.py` is extended to ALSO accept a **shared service-secret header** `X-Internal-Service-Auth: <secret>` + `X-Internal-User-Id: <UUID>`. Solver, after verifying the caller's API-Key, calls billing with `X-Internal-Service-Auth=<env BILLING_SERVICE_SHARED_SECRET>` + `X-Internal-User-Id=<user_id from API-Key>`. The shared secret is a 64-char hex env var. Billing's `auth_dep.require_user` checks the secret first; if present and valid, returns user_id from `X-Internal-User-Id`; otherwise falls through to JWT verify. M3 replaces this with proper service-account JWTs or mTLS.

When the header is NOT present (today's J1 flow + /demo/charge): solver behaves exactly as today (no billing call). This preserves 5.A.1 back-compat.

### AC6: Saga payload_ref extension

When billing's `POST /v1/billing/charges` is called by a downstream that will use the 2-phase flow, the payload includes max_solve_seconds so finalize can validate/cap:

```python
# 5.A.4: payload_ref additions on POST /charges
payload = {
    "reference_id": body.reference_id,
    "purpose": body.purpose,
    "max_solve_seconds": body.max_solve_seconds,  # NEW; float; required when purpose="solve"; defaults to settings.charge_max_solve_seconds_default
    "rate_per_second": str(settings.lp_rate_per_second),  # NEW; string for Decimal precision
}
```

`ChargeCreateRequest` schema additions:
```python
class ChargeCreateRequest(BaseModel):
    amount: Decimal              # existing — for v1 still required; equals max_solve_seconds × rate
    # NEW (optional for back-compat — defaults make 5.A.1 demo still work):
    max_solve_seconds: float = 60.0
    # (rate_per_second stays server-side — clients don't set it)
```

This way, today's 5.A.1 demo continues to send just `amount=6.00` and gets `max_solve_seconds=60.0` defaulted (which × 0.10/sec = 6.00, consistent).

### AC7: Billing tests

**New: `apps/billing-service/tests/test_pricing.py`** (pure function tests — 9 cases)
1. `compute_charge_amount(5.0, 60, 0.10, 0.01, 6.00) == Decimal("0.50")` — typical case
2. `compute_charge_amount(60.0, 60, 0.10, 0.01, 6.00) == Decimal("6.00")` — at-cap
3. `compute_charge_amount(70.0, 60, 0.10, 0.01, 6.00) == Decimal("6.00")` — over-cap clamped
4. `compute_charge_amount(0.0, 60, 0.10, 0.01, 6.00) == Decimal("0.01")` — zero elapsed → floor
5. `compute_charge_amount(0.05, 60, 0.10, 0.01, 6.00) == Decimal("0.01")` — sub-cent → floor (0.05 × 0.10 = 0.005 → rounds to 0.01)
6. `compute_charge_amount(0.04, 60, 0.10, 0.01, 6.00) == Decimal("0.01")` — sub-cent → floor (0.04 × 0.10 = 0.004 → would round to 0.00; floor lifts to 0.01)
7. `compute_charge_amount(7.5, 60, 0.10, 0.01, 6.00) == Decimal("0.75")` — half-cent rounds HALF_UP (0.75 stays exact)
8. `compute_charge_amount(2.45, 60, 0.10, 0.01, 6.00) == Decimal("0.25")` — 0.245 HALF_UP → 0.25
9. `compute_charge_amount(2.44, 60, 0.10, 0.01, 6.00) == Decimal("0.24")` — 0.244 HALF_UP → 0.24

**Extend: `apps/billing-service/tests/test_charge_routes.py`** (5 new cases on top of existing 9)
10. `POST /charges/{id}/reserve` happy path → 200, state="reserved", balance unchanged
11. `POST /charges/{id}/reserve` on non-existent charge → 404 RFC 7807
12. `POST /charges/{id}/finalize` success elapsed=5s → state="charged", ledger has -0.50 + +5.50 rows, balance changes by -0.50
13. `POST /charges/{id}/finalize` failure → state="refunded", ledger has BOTH `+amount kind=refund` (from `apply`) AND `-amount kind=refund_reversal` rows; balance unchanged. **Assert**: `SUM(credit_transactions WHERE saga_id=X) == 0` (R1.1 net-zero invariant).
14. `POST /charges/{id}/finalize` idempotent replay (same body, state already CHARGED) → 200 with cached response (no duplicate ledger rows)

**New: `apps/billing-service/tests/test_critical_pricing.py`** (3 cases — adds a 6th file to the critical_* split; total 58 critical scenarios after this story)
15. T-PRICING-001: reserved with max=60, elapsed=0 → charge floors to 0.01; ledger has `-0.01 charge` + `+5.99 refund_partial`
16. T-PRICING-002: reserved with max=60, elapsed=60 → charge exactly equals reserved (no refund_partial row); single ledger row `-6.00 charge`
17. T-PRICING-003: reserved with max=60, elapsed=100 → charge capped at reserved (6.00); no refund_partial row; outbox event has `actual_amount=6.00, elapsed_seconds=100.0` (capped value passed through, not clamped — preserves audit trail)

### AC8: Solver tests

**New: `apps/solver-orchestrator/tests/test_billing_integration.py`** (5 cases — uses `httpx.MockTransport` to mock billing HTTP; no new dep)
18. No `X-Billing-Charge-Id` header → solver runs as today, NO billing calls (back-compat)
19. With header + reserve success + solve success → solver calls reserve then finalize(success) exactly once each
20. With header + reserve returns 404 → solver returns 422 + does NOT solve + does NOT call finalize
21. With header + reserve success + solve infeasible → solver calls finalize(failure, reason="infeasible") + returns LP infeasible 422 to caller
22. With header + reserve success + solve success + finalize 5xx → solver returns success result; `opt.error.billing_finalize_failed=true` is persisted (single-attempt failure mode verified)

### AC9: Web demo path unchanged

`/demo/charge` continues to use the deprecated `/confirm` endpoint — no UI changes. (When 5.A.5 introduces the proper 2-phase pre-charge guard, the demo migrates then.)

### AC10: Quality gates (per `feedback_full_quality_gates`)
Run BEFORE committing:
- `uv run ruff check .` → 0 errors
- `uv run ruff format --check .` → 0 changes needed
- `uv run mypy apps packages` → 0 errors
- `uv tool run pre-commit run --all-files` → 0 failures
- `pnpm -C apps/web build` → 0 errors (no FE changes but verify regression)
- ALL Python regression tests pass (every suite, not just billing/solver) + new tests pass

### AC11a: Prometheus metrics (SRE1)

Billing-service exports (add to existing `prometheus_client` registry):
- `billing_finalize_total{outcome="success"|"failure"|"already_finalized"}` Counter
- `billing_finalize_amount_actual_total` Counter — float, monotonic, sum of CNY charged via finalize
- `billing_finalize_amount_refund_partial_total` Counter — float, monotonic, sum of partial refund amounts

Solver-orchestrator exports:
- `solver_billing_callback_total{op="reserve"|"finalize", result="ok"|"failed"}` Counter

These flow into the existing Prometheus scrape (auth-service and outbox-relayer already export). No new dashboards in this story; M3.6d adds them.

### AC11: NFR alignment
- **NFR-R4 (对账误差 = 0)**: Partial refund row in same DB transaction as the charge row ensures `SUM(credit_transactions) = balance_after_charge` is provably exact (extends M2.2a invariant)
- **NFR-P1 (HTTP P95 < 300ms)**: `/reserve` < 100ms (1 SELECT FOR UPDATE + 1 UPDATE + 1 OUTBOX); `/finalize` < 200ms (same + 2 ledger inserts); solver-side **happy-path** overhead from billing callback < 150ms additional P95 (2 sync HTTP calls within same VPC, no retries needed). **Failure-path** worst-case 6s (3 retries × 2s timeout) is acceptable because the solve result is still returned regardless — the slowdown only affects whether `billing_finalize_failed=true` shows up earlier or later in logs. Documented as "billing-callback degraded mode" — does not violate NFR-P1 for the solver's own response P95.
- **NFR-S1**: All endpoints behind Bearer JWT; cross-service call uses caller-forwarded JWT (v1) — service-account JWT in M3
- **FR B4 epics 5.A.4 AC text** verified by AC7 row #1 (elapsed=5 / max=60 → 0.50) + AC7 row #2 (elapsed=60 → 6.00 capped)

## Tasks

### T1: Pricing module (0.5h)
1. Create `apps/billing-service/src/billing_service/pricing.py` with `compute_charge_amount()` per AC3
2. Add `lp_rate_per_second`, `charge_min_amount`, `charge_max_solve_seconds_default` to `config.py` Settings
3. Re-export `compute_charge_amount` from `__init__.py` for test import

### T2: Schema extensions (0.5h)
1. `schemas.py`: extend `ChargeCreateRequest` with `max_solve_seconds: float = 60.0` (with `gt=0, le=600.0` validators matching solver)
2. New `FinalizeChargeRequest`: `elapsed_seconds: float (ge=0)`, `status: Literal["success", "failure"]`, `failure_reason: str | None = None`
3. New `ReserveChargeResponse`: `charge_id, current_state, amount_reserved (str), balance_after_reserve (str)`
4. New `FinalizeChargeResponse`: `charge_id, current_state, reserved_amount, actual_amount, refund_partial_amount, balance_before, balance_after`
5. mypy strict pass

### T3: Billing routes — split confirm + new endpoints (1.5h)
1. Modify `POST /charges` to persist `max_solve_seconds` + `rate_per_second` in `payload_ref` (AC6)
2. ADD `POST /charges/{id}/reserve` per AC1 — single `apply("reserve")` + commit + return ReserveChargeResponse
3. ADD `POST /charges/{id}/finalize` per AC1 + AC4:
   - Success branch: compute amount via pricing module, call `apply("service_success")`, if `actual < reserved` add `kind="refund_partial"` ledger row of `+(reserved - actual)`, commit
   - Failure branch: call `apply("user_cancel")` (writes `+amount kind=refund`), then add compensating `kind="refund_reversal"` ledger row of `-amount` (R1.1 net-zero), commit
   - Idempotent-replay branch (state already CHARGED/REFUNDED): rebuild response from `saga.amount` + `SELECT * FROM credit_transactions WHERE saga_id=X`, return 200 (R1.3)
4. Keep existing `POST /charges/{id}/confirm` but add `deprecated=True` in route decorator + add `Deprecation: true` header in response
5. For finalize: extend outbox event payload with the 4 new fields per AC4 — done by writing them into `context` dict passed to `apply()` (which the orchestrator merges into payload)
6. **R1.2 fix — Internal service auth bridge**: extend `auth_dep.require_user` to check `X-Internal-Service-Auth` header first; if matches `settings.internal_service_secret` via `hmac.compare_digest` (constant-time, S1), return `UUID(X-Internal-User-Id)`; else fall through to JWT verify. Add `internal_service_secret` to `config.Settings` (required if `internal_service_auth_enabled=True`; 64-char hex). **S1 — log scrub**: the secret value MUST NEVER appear in log lines, exception messages, or `repr()` output. Use `secret_value: SecretStr` from pydantic if needed. Add an explicit test that constructs the Settings instance and asserts the secret is not in the `__repr__`.
7. mypy strict pass; RFC 7807 errors for 404/403/409

### T4: Billing tests (1.5h)
1. New `test_pricing.py` with 9 boundary cases per AC7
2. Extend `test_charge_routes.py` with 5 new cases per AC7 (rows 10-14)
3. Create new `test_critical_pricing.py` (6th file in critical_* split) with 3 scenario rows per AC7 (rows 15-17 → 58 total)
4. Update `CRITICAL_SCENARIOS.md` table: bump total from 55 → 58, add row "test_critical_pricing.py | 3 | Per-formula amount math", add T-PRICING-001/002/003 to detailed inventory

### T5: Solver-orchestrator billing client (1.5h)
1. New module `apps/solver-orchestrator/src/solver_orchestrator/billing_client.py` with async functions `reserve(charge_id, user_id)` + `finalize(charge_id, body, user_id)` using `httpx.AsyncClient` with `X-Internal-Service-Auth` + `X-Internal-User-Id` headers per R1.2
2. **Q4 fix**: Single attempt, 2s timeout, no inline retry. Returns a result tuple `(ok: bool, status_code: int, body: dict | None, error_message: str | None)` — caller decides what to do.
3. New solver config settings: `BILLING_BASE_URL` (default `http://localhost:8003`), `BILLING_SERVICE_SHARED_SECRET` (no default — fail-fast at startup if missing AND billing-integration feature is enabled)
4. Wire into `routes.post_optimization`: detect `X-Billing-Charge-Id` header, branch into billing-aware code path per AC5
5. Persist `opt.error.billing_finalize_failed=true` on single-attempt failure
6. mypy strict pass

### T6: Solver tests (1h)
1. New `test_billing_integration.py` with `httpx.MockTransport` per AC8 (rows 18-22). The billing client accepts an optional `client: httpx.AsyncClient | None = None` arg so tests can inject a client with `MockTransport(handler)`.
2. NO new dependency needed (`httpx.MockTransport` is built-in)
3. Make sure existing `test_routes.py` regressions still pass with the new header optionally absent

### T7: docker-compose + env (0.5h)
1. `docker-compose.yml`: add `BILLING_BASE_URL=http://billing-service:8003` to solver-orchestrator service env
2. `docker-compose.yml`: add `BILLING_SERVICE_SHARED_SECRET=<dev-secret-64hex>` to BOTH billing-service AND solver-orchestrator service env (R1.2)
3. `.env.example`: document `BILLING_BASE_URL` + `BILLING_SERVICE_SHARED_SECRET` (mark as required for cross-service Saga)
4. Verify `docker compose up` brings both services up and solver can reach billing's `/healthz`

### T8: Quality gates + sprint sync + PR (1h)
1. Run full quality gate sequence per AC10
2. Update `sprint-status.yaml`: `5-a-4-per-formula-charging-capped: done` + `last_updated: 2026-05-18`
3. Update memory file `opticloud-project-status.md` with new test counts + main commit
4. Commit + push branch + open PR
5. Wait CI green; merge with squash

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| **A1**: Concurrent reservations by same user — between reserve and finalize the same user could spend reserved balance on another charge | **Accepted for v1**: no "soft reservation" tracking. Two reserves with combined > balance: one finalize succeeds, one finalize fails the in-route balance check at service_success time and falls into compensating refund path. Documented; M3 introduces `reserved_amount` column on user_accounts that subtracts from effective balance for new reserves. |
| solver calls billing and billing is down → solve still completes but ledger inconsistent | AC5 retry 3× + write `billing_finalize_failed=true` to optimization row + ops alert via structured log; M3 will replace HTTP with outbox-relayer |
| Partial refund row + charge row should be atomic, but writing 2 rows means longer transaction → lock contention on user_id index | Both INSERTs happen inside the same `session.commit()` call already used by `apply()`; the existing `SELECT FOR UPDATE` on saga_instances serializes per-Saga, not per-user — negligible contention for normal load |
| Decimal precision: float `elapsed_seconds` from solver could be `5.000000000001` and screw up rounding | `pricing.compute_charge_amount` converts to Decimal IMMEDIATELY using `Decimal(str(float))` (not `Decimal(float)` which has bin-rep noise); ROUND_HALF_UP makes the output deterministic |
| `X-Billing-Charge-Id` is an opt-in header — what stops a caller from omitting it but still wanting to be charged? | Today (5.A.1 flow) the web app calls billing directly for /confirm. With 5.A.4 in place, the proper J1 v2 flow (sequenced by 5.A.5) will require the header on every paid call; for v1 the header stays optional so the demo path doesn't break. Documented in PRD addendum. |
| Caller forwards their own JWT to billing instead of using service-account → JWT could be expired by the time finalize runs | 2-second timeout per finalize attempt + 3 attempts = max 3s total; the JWT has at minimum 5-min lifetime, so timing is fine for v1. Service-account JWT in M3. |
| The deprecated `/confirm` endpoint is still actively used by /demo/charge — accidentally removing it breaks the demo | Marked `deprecated=True` in OpenAPI but functionally unchanged; removal explicitly out of scope; will be removed in M3 after /demo/charge migrates to 2-phase |
| Finalize-idempotent replay returning "cached" — what does cached actually mean when we don't persist responses? | We use the Saga's terminal state as the source of truth: when finalize is called on a CHARGED saga, we re-build the same response from `saga.amount` + the partial-refund ledger row (single SELECT). No response cache needed. Tested by AC7 row #14. |

## Non-Functional Requirements Mapping

- **NFR-R4 (对账误差 = 0)**: AC4 (atomic charge + partial-refund rows); extended by 3 new scenarios in AC7
- **NFR-P1 (HTTP P95 < 300ms)**: AC11 — both new endpoints budget < 200ms
- **NFR-S1 (TLS + Bearer)**: AC1 — all new endpoints require JWT
- **NFR-A1 (PIPL)**: no PII added to outbox event payload (only amounts + saga IDs)
- **FR B4 (Per-formula charging capped)**: AC1 + AC2 + AC3 + AC7 cases 1-3 directly verify the epics 5.A.4 AC text

## Definition of Ready

- ✅ SagaOrchestrator from 5.A.0a supports reserve / service_success / user_cancel triggers (all three needed by this story already implemented)
- ✅ M2.1 outbox-relayer running so the new outbox event payload is published end-to-end
- ✅ Solver-orchestrator has `result.solve_seconds` to send to billing
- ✅ Auth-service JWT verifier shared with billing — solver already verifies the same JWT
- ✅ All 3 review rounds applied (next step)

## Definition of Done

- All 11 ACs pass
- Test counts: billing +8 (5 routes + 3 critical scenarios), solver +5, pricing +9 → +22 tests total → 154 active tests
- CI green on PR
- Sprint-status.yaml updated
- Memory updated with new commit + test counts
- /demo/charge page in browser still works end-to-end (regression check before merge)
- Code review with full quality gates documented in commit body

## Sign-off (story-level)

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Architect | proposed by AI | ☐ | — |
| Billing Lead | TBA | ☐ | — |
| Solver Lead | TBA | ☐ | — |

> Owner committee deferred per M0 skip.
