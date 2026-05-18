# Billing Critical Scenarios Inventory (Story M2.2a + 5.A.4)

58 hand-written scenarios covering the Saga orchestrator. NFR-R4 v1.5 hard-gate evidence.

Verification: `pytest apps/billing-service/tests/test_critical_*.py --collect-only -q | tail -1`

## Summary

| File | Scenarios | Focus |
|---|---:|---|
| test_critical_transitions.py | 23 | Transition matrix coverage |
| test_critical_idempotency.py | 10 | P23 edge cases |
| test_critical_concurrency.py | 8 | Race conditions |
| test_critical_invariants.py | 8 | DB-level invariants |
| test_critical_audit.py | 6 | Outbox structure verification |
| test_critical_pricing.py | 3 | Per-formula amount math (5.A.4) |
| **Total** | **58** | |

### test_critical_pricing.py (3) — Story 5.A.4

| # | Test | AC | Traceability |
|---:|---|---|---|
| T-PRICING-001 | test_pricing_001_elapsed_zero_floors_to_min | 5.A.4 AC3+AC4 | floor to 0.01 + partial refund row |
| T-PRICING-002 | test_pricing_002_elapsed_at_cap_no_refund_partial | 5.A.4 AC3 | exact at-cap no partial refund |
| T-PRICING-003 | test_pricing_003_elapsed_over_cap_clamped_to_reserved | 5.A.4 AC3 | over-cap defensive clamp |

## Detailed inventory

### test_critical_transitions.py (23)

| # | Test | AC | Traceability |
|---:|---|---|---|
| 1-7 | test_happy_transition[7 parametrized] | AC2 | ADR-0001 §"Transition matrix" — each of 7 rows |
| 8-14 | test_wrong_state_raises[7 parametrized] | AC2 | State machine invariant: invalid transitions raise |
| 15-18 | test_terminal_state_rejects_any_trigger[4 parametrized] | AC2 | I3 terminal stickiness |
| 19 | test_amount_equal_to_balance_succeeds | AC6 | NFR-R4 boundary |
| 20 | test_amount_at_max_numeric_precision | AC6 | NUMERIC(12,4) max value |
| 21 | test_amount_minimum_positive | AC6 | Decimal(0.0001) accepted |
| 22 | test_idempotent_replay_reserved_reserve_is_noop | AC2-D + AC10 | Story 5.A.0a AC10 |
| 23 | test_saga_created_at_less_than_updated_at | AC6 | Timestamp monotonicity |

### test_critical_idempotency.py (10)

| # | Test | AC | Traceability |
|---:|---|---|---|
| 24 | test_same_key_same_body_returns_same_saga | AC3 | P23 idempotency |
| 25 | test_same_key_different_body_raises | AC3 | P23 conflict detection |
| 26 | test_diff_keys_same_body_creates_distinct_sagas | AC3 | Key scoping |
| 27 | test_ttl_expired_key_creates_new_saga | AC3 | 24h TTL boundary |
| 28 | test_concurrent_start_same_key_yields_one_saga | AC3 + AC4 | UNIQUE constraint |
| 29 | test_key_reuse_after_terminal_returns_existing | AC3 | Terminal saga retrieval |
| 30 | test_idempotency_includes_saga_type | AC3 | Hash includes saga_type |
| 31 | test_body_hash_key_order_independence | AC3 | JSON canonical ordering |
| 32 | test_body_hash_decimal_string_form_matters | AC6 (D1) | Known limitation — Decimal("6.00") ≠ Decimal("6.0") |
| 33 | **test_cross_tenant_key_reuse_blocked** | **AC11 (S1 SECURITY FIX)** | M2.2a security fix |

### test_critical_concurrency.py (8)

| # | Test | AC | Traceability |
|---:|---|---|---|
| 34 | test_concurrent_apply_same_trigger_yields_one_transition | AC4 | Idempotent replay under race |
| 35 | test_concurrent_conflicting_triggers_one_wins | AC4 | SELECT FOR UPDATE serialization |
| 36 | test_concurrent_start_different_keys | AC4 | Independent sagas don't interfere |
| 37 | test_concurrent_charge_and_refund | AC4 + AC7 | NFR-R4 reconciliation under concurrency |
| 38 | test_concurrent_confirm_vs_cancel | AC4 | One-winner property |
| 39 | test_skip_locked_prevents_race | AC4 | 10-way race serialized |
| 40 | test_ledger_sum_monotonic_per_saga | AC7 | NFR-R4 per-saga |
| 41 | test_ledger_sum_across_5_concurrent_sagas | AC4 + AC7 | NFR-R4 multi-saga |

### test_critical_invariants.py (8)

| # | Test | AC | Traceability |
|---:|---|---|---|
| 42 | test_invariant_created_at_le_updated_at | AC6 | Timestamp ordering |
| 43 | test_invariant_refund_le_charge | AC5 | I2 (M2.0 prop) extended to DB |
| 44 | test_invariant_no_stuck_state | AC5 | Pure data — state machine completeness |
| 45 | test_invariant_outbox_aggregate_and_version | AC5 | P33 schema invariants |
| 46 | test_invariant_transition_matrix_covers_every_trigger_unique | AC5 | (from_state, trigger) uniqueness |
| 47 | test_nfr_r4_reconciliation_after_each_apply | AC7 | NFR-R4 ledger sum |
| 48 | test_outbox_payload_shape | AC5 + S3 | Required fields + no PII |
| 49 | test_outbox_headers_carry_compensation | AC5 | Compensation routing |

### test_critical_audit.py (6)

| # | Test | AC | Traceability |
|---:|---|---|---|
| 50 | test_each_apply_produces_one_outbox_row | AC5 | 1 transition = 1 outbox row |
| 51 | test_happy_path_produces_three_outbox_rows_in_order | AC5 | Multi-step ordering |
| 52 | test_refund_produces_user_cancel_outbox | AC5 | Compensation outbox |
| 53 | test_outbox_payload_no_pii | AC5 + S3 | NFR-A1 PIPL alignment |
| 54 | test_outbox_headers_compensation_enum_value | AC5 | Header schema |
| 55 | test_outbox_event_type_starts_with_billing_saga | AC5 | M2.1 relayer channel compat (A1 loose-match) |

## Coverage map

- **All 7 transitions × happy/wrong-state**: rows 1-14 (transitions matrix)
- **All 4 terminal states reject apply()**: rows 15-18 (terminal stickiness)
- **NFR-R4 reconciliation invariant** (对账误差=0): rows 37, 40, 41, 43, 47
- **S1 security fix** (cross-tenant key leak): row 33 + AC11 implementation
- **P33 Outbox loop end-to-end**: rows 45, 48, 49, 50-55
- **Concurrency safety** (SELECT FOR UPDATE + idempotent replay): rows 28, 34-39

## Open tech-debt (out of scope for M2.2a)

- **D1**: hash_body normalizes Decimal string form → row 32 documents current limitation
- **TTL row 27**: orchestrator does not currently "garbage collect" expired idempotency rows — out of scope for M2.2a
- **M2.2b**: Hypothesis property tests for random transition sequences
- **M2.2c**: 500+ scenarios for full coverage at M5

## How to verify (audit)

```bash
cd apps/billing-service
PYTHONPATH=.../packages/shared-py:.../apps/billing-service/src \
  DATABASE_URL=postgresql+asyncpg://... \
  pytest tests/test_critical_*.py --collect-only -q | tail -1
# Should output: 55 tests collected
```
