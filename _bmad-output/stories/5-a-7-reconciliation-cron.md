---
story_key: 5-a-7-reconciliation-cron
epic_num: 5
story_num: A.7
epic_name: Billing — Credits & Saga
status: ready-for-dev
priority: 🟢 High (NFR-R4 hardening — first scheduled background job; provides daily proof that 对账误差 = 0)
sizing: M (~4-5 hours; pure-Python reconciler + CLI runner + tests; no schema migration, no new HTTP endpoint)
type: implementation + observability
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L1649 (Story 5.A.7 — 计费对账双写 + 每日扫差)
  - _bmad-output/planning/prd.md (NFR-R4 对账误差 = 0)
  - apps/billing-service/src/billing_service/saga_orchestrator.py (terminal state semantics)
  - apps/billing-service/src/billing_service/routes.py (finalize route's net-zero R1.1 compensation pattern)
  - docs/adr/0001-saga-pattern.md (state machine — terminal states)
dependencies:
  upstream:
    - 5-a-0a-saga-implementation (done) — saga_instances + credit_transactions
    - 5-a-2-credits-balance-buckets (done) — bucket column for per-bucket diffs
    - 5-a-4-per-formula-charging-capped (done) — refund_partial + refund_reversal kinds the reconciler must understand
    - 5-a-5-p5-warning-modal (done) — payload_ref.user_explicitly_confirmed flag (audit trail orthogonal to reconciliation)
    - m2-2b-saga-property-tests (done) — discovered orchestrator quirks the reconciler must accept
  downstream:
    - M3 scheduling integration (K8s CronJob / systemd timer / Dramatiq scheduler) — out of scope; v1 ships the reconciler as a runnable script
---

# Story 5.A.7 — Billing Reconciliation Cron

## User Story

**As** the billing operator on call
**I want** a daily-runnable script that scans every terminal Saga from a 24h window and verifies that the credit_transactions ledger nets to the **expected** amount (per the Saga's final state and amount), reporting any drift with structured logging
**so that** I have **provable evidence** that NFR-R4 (对账误差 = 0) holds in production, and any silent drift surfaces within 24h instead of being discovered by an angry customer.

## Why this story

ADR-0001 declares NFR-R4 as a hard gate. M2.2a's 55 critical scenarios prove pointwise correctness *at write time*; M2.2b's property tests prove correctness *under random walks*. But neither runs against **production data over time** — a future bug could insert a stray ledger row, a manual SQL adjustment could go unrecorded, or a partial DB failure could leave a saga in a state where ledger ≠ expected.

5.A.7 adds the **continuous-observation layer**: a script that runs daily (M3 will wrap it in K8s CronJob), scans terminal Sagas, and emits a structured report. In dev/CI, the script runs as a one-shot to verify the invariant on a known-good DB; in prod, it'll fire at 03:00 daily, log to the central log aggregator, and page on-call if drift > ¥0.01.

The scope here is the **reconciler core + CLI + tests**. Actual scheduling integration (K8s CronJob YAML, systemd timer, or Dramatiq @cron) is M3 — different concern, different PR.

## Out of scope

- **Scheduling integration** (K8s CronJob / systemd / Dramatiq) → M3.3a/b
- **Slack / PagerDuty webhook** for on-call alert → M3.6c incident playbook
- **Auto-remediation** (writing compensation rows on detected drift) → never; reconciliation is read-only; humans review and adjust
- **Cross-service reconciliation** (billing ↔ solver elapsed_seconds match) → 5.A.4 already verifies inline; this story is billing-only
- **Per-bucket usage analytics** (how much was charged from each bucket over a window) → 5.D.1 invoices
- **Historical replay** (reconcile last 30 days) → CLI accepts `--window` flag for ad-hoc, but the daily cron only does 24h
- **NFR-R4 v2 hardening** (signed audit log, third-party witness) → M5+

## Acceptance Criteria

### AC1: New module `apps/billing-service/src/billing_service/reconciler.py`

**Pure-Python module** with:

```python
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

class DriftSeverity(StrEnum):
    OK = "ok"            # |drift| < 0.01
    MINOR = "minor"      # 0.01 <= |drift| < 1.00
    MAJOR = "major"      # |drift| >= 1.00

@dataclass(frozen=True)
class SagaReconciliationResult:
    saga_id: UUID
    user_id: UUID
    saga_type: str
    terminal_state: str
    reserved_amount: Decimal
    expected_ledger_sum: Decimal
    actual_ledger_sum: Decimal
    drift: Decimal              # actual - expected (positive = bank lost money; negative = bank kept money)
    severity: DriftSeverity

@dataclass(frozen=True)
class ReconciliationReport:
    window_start: datetime
    window_end: datetime
    sagas_examined: int
    diffs_found: int
    total_drift_magnitude: Decimal      # sum of abs(drift) across all examined sagas
    results: list[SagaReconciliationResult]  # only includes non-OK rows by default
```

### AC2: Per-state ledger invariants (bounds, not exact values)

**R2 D1 discovery**: `actual_amount` from /finalize is written to **OutboxEvent.payload**, NOT to `saga.payload_ref`. So the reconciler can't predict the exact ledger sum for finalize-partial sagas — instead it checks **bounds** per state.

Let `A = saga.amount` (the reserved amount).

| Terminal state | Expected ledger sum |
|---|---|
| `FAILED` | **= 0** (exact — no ledger row written for either failure trigger) |
| `REFUNDED` | **= 0** (R1.1: orchestrator's +A refund + route's -A refund_reversal nets to zero) |
| `CHARGED` mid-walk (only `service_success` applied, no finalize route called) | **= -A** (exact — only the orchestrator's -A charge row exists) |
| `CHARGED` after /finalize (no partial refund) | **= -A** (exact — single -A charge row) |
| `CHARGED` after /finalize (with partial refund) | **bounds: `-A ≤ sum ≤ -charge_min_amount`** (∈ [-A, -¥0.01]) — reconciler can't know exact actual without elapsed_seconds, but ANY out-of-bounds value is drift |
| `COMPLETED` | same bounds as CHARGED (outbox_delivered doesn't write ledger) |
| `ROLLED_BACK` | **= 0** (orchestrator's -A charge + +A refund net to zero) |

For terminal CHARGED/COMPLETED, the reconciler classifies:
- sum < -A → **MAJOR drift** (over-charge: bank kept more than reserved)
- -A ≤ sum ≤ -¥0.01 → **OK** (within partial-refund range)
- -¥0.01 < sum < 0 → **MINOR drift** (charged less than minimum floor — suspicious but small)
- sum ≥ 0 → **MAJOR drift** (no debit on a charged saga = bank lost money)

### AC3: Drift detection threshold + severity

```python
_DRIFT_OK_THRESHOLD = Decimal("0.01")      # < 1 cent considered noise (rounding)
_DRIFT_MAJOR_THRESHOLD = Decimal("1.00")   # >= ¥1 is a real bug

def classify_drift(drift: Decimal) -> DriftSeverity:
    abs_drift = abs(drift)
    if abs_drift < _DRIFT_OK_THRESHOLD:
        return DriftSeverity.OK
    if abs_drift < _DRIFT_MAJOR_THRESHOLD:
        return DriftSeverity.MINOR
    return DriftSeverity.MAJOR
```

The 1-cent OK threshold prevents alert spam from legitimate sub-cent rounding (already verified can't actually happen via 5.A.3 properties, but defensive).

### AC4: Main entry point — async function `reconcile_window`

```python
async def reconcile_window(
    session: AsyncSession,
    window_start: datetime,
    window_end: datetime,
) -> ReconciliationReport:
    """Scan terminal sagas in [window_start, window_end] and report drift.

    Steps:
    1. SELECT * FROM saga_instances
         WHERE current_state IN ('completed', 'failed', 'refunded', 'rolled_back')
           AND updated_at BETWEEN window_start AND window_end
    2. For each saga:
       a. Compute expected_ledger_sum per AC2 table
       b. SUM(amount) FROM credit_transactions WHERE saga_id = X
       c. drift = actual - expected
       d. severity = classify_drift(drift)
    3. Return ReconciliationReport with non-OK results
    """
```

Pure-async; no internal session creation (caller passes one). Uses existing CreditTransaction + SagaInstance ORM models.

### AC5: CLI runner — `apps/billing-service/src/billing_service/reconciler_cli.py`

```python
"""CLI: python -m billing_service.reconciler_cli --window 24h
or:    python -m billing_service.reconciler_cli --since 2026-05-19T00:00:00 --until 2026-05-20T00:00:00
"""

if __name__ == "__main__":
    import argparse, asyncio, sys
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", type=str, default="24h", help="e.g. 24h, 7d (default 24h)")
    parser.add_argument("--since", type=str, default=None, help="ISO 8601 window start")
    parser.add_argument("--until", type=str, default=None, help="ISO 8601 window end")
    args = parser.parse_args()

    # Resolve window: --since/--until override --window
    # Default: --window 24h → since = now - 24h, until = now
    ...

    async def _main():
        # Create engine + session, call reconcile_window, print report
        ...

    asyncio.run(_main())
    # Exit code: 0 if all OK, 1 if any MINOR drift, 2 if any MAJOR drift
```

Output format (structured JSON via structlog) so cron-wrapper can pipe to log aggregator:
```json
{"event": "billing.reconcile.report", "window_start": "...", "window_end": "...",
 "sagas_examined": 42, "diffs_found": 0, "total_drift_magnitude": "0.00",
 "results": []}
```

Plus a human-readable summary stderr line.

### AC6: Tests — `apps/billing-service/tests/test_reconciler.py`

**6 cases**:

1. `test_classify_drift_thresholds` — pure function: 0.005 → OK, 0.50 → MINOR, 1.50 → MAJOR, -2.00 → MAJOR (abs)
2. `test_reconcile_empty_window_returns_zero_diffs` — no sagas in window → ReconciliationReport with 0/0
3. `test_reconcile_clean_completed_saga` — drive a saga through service_success → COMPLETED; reconciler reports OK with drift=0
4. `test_reconcile_clean_refunded_saga` — drive RESERVED → user_cancel → REFUNDED; the +A refund + -A refund_reversal nets to 0; reconciler reports OK
5. `test_reconcile_detects_injected_drift` — manually INSERT a stray `+5.00` ledger row tied to a terminal saga; reconciler reports the saga in results with `drift ≈ +5.00` and severity=MAJOR
6. `test_reconcile_partial_finalize_within_bounds` (D1 fix) — finalize with elapsed=5s (actual=¥0.50 from a ¥6 reservation); ledger sum = -¥0.50, which is in [-¥6, -¥0.01] bound → reconciler reports OK with no drift

### AC7: Quality gates

- `uv run ruff check apps packages` → 0 errors
- `uv run ruff format --check apps packages` → 0 changes needed
- `uv run mypy apps packages` → 0 errors
- `pnpm -C apps/web build` → 0 errors (no FE changes, regression guard)
- All Python regression tests pass; billing 127 → 133 (+6)

### AC8: NFR alignment

- **NFR-R4** (对账误差 = 0): AC6 #5 proves the reconciler *catches* drift; M3 will wire it to run daily and gate releases
- **NFR-O3** (audit): structured log line per AC5 is the audit trail
- **NFR-P1** (HTTP P95): N/A — this is a batch job, not a request-path
- **CI cost**: tests use the same conftest as billing-service-test; adds < 2s wall-time

### AC9: M3 scheduling readme

Add `apps/billing-service/src/billing_service/RECONCILER.md` documenting:
- How to run the CLI locally (`uv run python -m billing_service.reconciler_cli --window 24h`)
- Expected output format
- M3 scheduling options (K8s CronJob YAML stub / systemd timer / Dramatiq @cron) — pick at deploy time
- Alerting integration points (where to plug in PagerDuty/Slack webhook)

Plain markdown; ~50 lines. Saves operators from having to read code.

## Tasks

### T1: Reconciler module + dataclasses (1.5h)
1. Create `apps/billing-service/src/billing_service/reconciler.py` per AC1 + AC2 + AC3 + AC4
2. Pure logic — no DB session creation; caller provides
3. mypy strict pass

### T2: CLI runner (0.5h)
1. Create `apps/billing-service/src/billing_service/reconciler_cli.py` per AC5
2. argparse + asyncio.run wrapper + JSON-to-stdout structured output
3. Exit codes: 0 OK / 1 MINOR / 2 MAJOR

### T3: Tests (1.5h)
1. New `apps/billing-service/tests/test_reconciler.py` per AC6 (6 cases)
2. Use existing `session` + `test_user_id` fixtures from `conftest.py`
3. Drive sagas through orchestrator triggers, then inject drift via direct INSERT (case #5)

### T4: README (0.5h)
1. Create `apps/billing-service/src/billing_service/RECONCILER.md` per AC9
2. Cover: local run, expected output, M3 scheduling options, alerting integration points

### T5: Quality gates + PR (0.5h)
1. Run AC7 gates
2. Sprint-status update (`5-a-7-billing-reconciliation: done`)
3. Memory update
4. Commit + push + PR + merge

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Reconciler reads CHARGED sagas where finalize hasn't run yet (mid-walk) — would report "expected -A but got 0" false positive | AC4 step 1 filters by `current_state` only; if the saga is CHARGED but mid-walk (no /finalize called), the ledger DOES have the -A row from `apply("service_success")`. So actual = -A, expected = -A, drift = 0. ✓ |
| Decimal comparison with very small values (rounding) → noise | AC3 `_DRIFT_OK_THRESHOLD = 0.01` absorbs sub-cent noise without alerting |
| Long window (--window 7d) on production database — query timeout | Defaults to 24h; --since/--until are advisory. Index already exists on `saga_instances.updated_at` (via PK + automatic indices). Future M3 may add explicit composite index `(current_state, updated_at)` for huge tables. |
| Test #5 "inject drift" requires raw SQL INSERT — fragile to schema changes | Uses ORM `CreditTransaction(...)` not raw SQL; auto-tracks model changes. |
| Saga payload_ref schema drift over time (5.A.5 added user_explicitly_confirmed flag; future stories may add more) | Reconciler reads via `.get()` with default → unknown keys safely ignored. Documented. |
| M3 will need to call this from K8s CronJob — Python script must be importable | Implemented as both module (`reconciler.py`) AND CLI (`reconciler_cli.py`). K8s CronJob calls `python -m billing_service.reconciler_cli`. Test verifies the module-style invocation works. |

## Non-Functional Requirements Mapping

- **NFR-R4** ✅ AC4 + AC5 + AC6 — daily proof of 对账误差 = 0
- **NFR-O3** ✅ structured log line in AC5
- **NFR-P1** ✅ batch job, off-path; no impact on HTTP latency
- **ADR-0001** ✅ test pyramid layer 4 (continuous observation, not point-in-time)

## Definition of Ready

- ✅ saga_instances + credit_transactions tables stable from 5.A.0a
- ✅ All Saga terminal-state semantics documented from 5.A.4 + 5.A.5 + M2.2b discoveries
- ✅ structlog + asyncpg already in billing-service dependencies
- ✅ All 3 review rounds applied (next step)

## Definition of Done

- All 8 ACs pass
- Test counts: billing 127 → 133 (+6)
- CI green on PR
- sprint-status.yaml: `5-a-7-reconciliation-cron: done`
- Memory updated
- Manual smoke: `uv run python -m billing_service.reconciler_cli --window 24h` returns 0 + empty results on clean local DB
- Code review with full quality gates documented in commit body

## Sign-off

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Billing Lead | TBA | ☐ | — |
| SRE | TBA | ☐ | — |
| Compliance / Audit | TBA | ☐ | — |

> Owner committee deferred per M0 skip.
