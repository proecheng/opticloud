---
story_key: m2-2b-saga-property-tests
epic_num: 0
story_num: M2.2b
epic_name: Foundation — Test Pyramid Layer 3
status: ready-for-dev
priority: 🟢 High (NFR-R4 confidence boost before scale-up; layer 3 of ADR-0001 test pyramid)
sizing: M (~4-6 hours; 5-7 new property tests + strategies + DB fixture re-use)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/stories/m2-2a-billing-critical-tests.md (line 41-44 — references M2.2b as "layer 3 of the test pyramid")
  - docs/adr/0001-saga-pattern.md (5-layer test pyramid: property → critical → property+business → full coverage → contract)
  - packages/shared-py/opticloud_shared/property_test_base/strategies.py (existing Hypothesis strategies — extend, don't duplicate)
  - packages/shared-py/tests/test_saga_state_machine.py (M2.0 — pure-function Saga property tests; M2.2b adds DB-backed)
  - apps/billing-service/tests/test_invariants.py (5.A.0a — already mixes @given with DB session; pattern to mirror)
  - apps/billing-service/src/billing_service/saga_orchestrator.py (target under test)
dependencies:
  upstream:
    - m2-0-saga-spike (done) — pure-function State machine + Transition matrix (target invariants)
    - 5-a-0a-saga-implementation (done) — SagaOrchestrator DB-backed (target system)
    - m2-2a-billing-critical-tests (done) — 55 hand-written scenarios (this story finds what those miss)
    - 0-5b-property-test-framework (done) — shared Hypothesis strategies + fixtures
    - 5-a-4-per-formula-charging-capped (done) — adds refund_partial / refund_reversal ledger kinds the property tests must understand
    - 5-a-5-p5-warning-modal (done) — adds confirmed flag + warning gate; property tests over /charges path can ignore it (set confirmed=True)
  downstream:
    - m2-2c-saga-extended-coverage — 500+ scenarios for M5 hardening (M2.2b is N≈100 random walks; M2.2c expands)
    - 3-1-4-mock-real-divergence — uses Saga property invariants for mock vs real solver comparison
---

# Story M2.2b — Saga Property Tests (Hypothesis random walks)

## User Story

**As** the on-call engineer about to scale OptiCloud Billing to enterprise customers
**I want** Hypothesis-driven property tests that random-walk the Saga state machine through arbitrary trigger sequences against the live SagaOrchestrator + DB
**so that** any combination of (start, apply×N) my code CAN execute won't silently violate the 4 cross-cutting invariants (terminal stickiness, net-zero ledger consistency, idempotency, amount immutability) that M2.2a's 55 hand-written scenarios verify pointwise — closing the "what if a customer hits some sequence we didn't think of?" gap.

## Why this story

ADR-0001 §"Test pyramid":

| Layer | Done? | Counts |
|---|:-:|---:|
| 1. Property tests — pure state machine | ✅ M2.0 | 8 tests |
| 2. Critical scenarios — hand-written | ✅ M2.2a | 55 + 3 (M2.2a+5.A.4) |
| 3. **Property tests + business — Hypothesis random walks against DB** | 🔵 THIS STORY | +5-7 |
| 4. Full coverage — 500+ scenarios | ⏳ M2.2c (M5) | — |
| 5. Contract tests — Schemathesis | ⏳ M3.2 | — |

Layer 2 (M2.2a) caught a real cross-tenant security bug (S1 fix). Layer 3 catches bugs that humans don't enumerate — typically state-machine races, ledger arithmetic edge cases, and idempotency-replay holes. The investment is small (~5h for 5-7 tests) but the safety net widens significantly before we open the gate to non-demo customers.

## Out of scope

- **Full RuleBasedStateMachine** — stateful testing with async + DB fixtures has known pytest-asyncio / sqlalchemy ergonomics issues. M2.2b uses `@given(sequences=...)` for explicit-walk property tests (simpler, still finds bugs). RuleBasedStateMachine is M2.2c material.
- **High example counts** (1000+) — runs in CI on every PR; budget < 30s total for the new tests. `max_examples=20-50` per test, `deadline=3000ms`.
- **5.A.5 `confirmed` flag testing** — covered by M2.2a + dedicated 5.A.5 tests; M2.2b sets `confirmed=True` so it can drive transitions freely
- **Cross-service Saga property tests** — billing↔solver coordination is M2.2c; M2.2b is billing-only
- **Outbox relayer property tests** — separate; M2.1 has its own 8 integration tests; M3.6e adds Schemathesis-based contract fuzzing
- **Shrinking + minimal failure repros** — Hypothesis does this automatically; no special handling in story
- **Stateful concurrency tests** — actual race conditions (concurrent apply()) are M3 scope; M2.2b is sequential

## Acceptance Criteria

### AC1: New test file `apps/billing-service/tests/test_property_saga_walks.py`

- 5-7 distinct property tests, each marked with `@given` + `@settings(max_examples=N, deadline=Y)`
- File uses the same `session` + `test_user_id` fixtures as existing `test_invariants.py` (DR1 — reuse, don't duplicate fixture scaffolding)
- All tests must complete in < 30 seconds total locally (faster in CI)
- **A2 scope clarification**: tests drive `SagaOrchestrator` directly via `apply(trigger, ...)`; they do NOT go through HTTP routes. Consequence: `refund_partial` and `refund_reversal` ledger kinds (which the 5.A.4 `/finalize` route adds OUTSIDE `apply()`) are NOT exercised here. Those are M2.2a coverage. M2.2b's scope is "what the orchestrator does on its own."

### AC2: Trigger-sequence strategy

A new Hypothesis strategy in `apps/billing-service/tests/test_property_saga_walks.py` (kept local to billing — only billing-service knows the trigger names):

```python
_TRIGGERS_FROM_PENDING = ["reserve", "balance_insufficient"]
_TRIGGERS_FROM_RESERVED = ["service_success", "user_cancel", "pre_charge_guard_reject"]
_TRIGGERS_FROM_CHARGED = ["outbox_delivered", "downstream_reject_late"]

def valid_walks() -> st.SearchStrategy[list[str]]:
    """Generate a list of triggers that COULD form a valid path from PENDING.

    Length 1-4; each step is a trigger valid from the previous to_state.
    Hypothesis can also shrink to minimal failing walks.
    """
```

Properties: walks always start at PENDING and end at a terminal state OR `RESERVED` (mid-path) OR `CHARGED` (mid-path).

**R1.3 fix — meta-test**: A test `test_trigger_lists_cover_all_transitions` asserts that `set(_TRIGGERS_FROM_PENDING ∪ _TRIGGERS_FROM_RESERVED ∪ _TRIGGERS_FROM_CHARGED) == {t.trigger for t in TRANSITIONS}`. If anyone adds a new transition to the matrix without updating M2.2b's trigger lists, this meta-test fails loudly with `set difference: {missing_trigger}`. Cheap insurance.

### AC3: Property P1 — Ledger magnitude bounded by amount (no overshoot)

**Discovery during implementation**: The tight "no money created from thin air" property holds only at the HTTP route layer (5.A.4 R1.1 adds compensating `refund_reversal` rows). The **orchestrator alone** produces these ledger shapes:
- `service_success`: `-A` (debit)
- `user_cancel` after `reserve`: `+A` (refund WITHOUT a preceding debit — this is what 5.A.4 route-level compensates)
- `downstream_reject_late` after `service_success`: `+A` (compensates the prior debit, net = 0)

So orchestrator-only walks produce ledger sum ∈ {-A, 0, +A}.

**Property tested**: `|sum(credit_transactions WHERE saga_id = X)| <= A` for any walk. This still catches:
- 10× row bugs (would produce |sum| = 10A)
- Out-of-band ledger writes (would produce |sum| > A)
- Ledger row leaks (would produce |sum| != {0, A})

The TIGHT NFR-R4 ("no money created, ever") invariant is enforced by M2.2a's 55 hand-written scenarios AT THE ROUTE LAYER. M2.2b adds defense-in-depth at orchestrator scope.

### AC4: Property P2 — Terminal absorption

For any walk that reaches a terminal state at step N, applying any trigger at step N+1 raises `SagaTerminalError`.

Test: pick a terminal state at random, drive a saga there via the appropriate walk, then `@given` a random trigger from any state's trigger list, expect `pytest.raises(SagaTerminalError)`.

### AC5: Property P3 — saga.amount is immutable through any walk

Start a saga with `amount = A`; apply any valid walk; assert `saga.amount == A` at every step.

This catches bugs like "what if a transition handler accidentally mutates the amount column" — relevant to ensure ledger derivations stay deterministic.

### AC6: Property P4 — Idempotent re-application is a no-op

For any walk that ends at state S, calling `apply(trigger)` where `trigger` is the trigger that brought saga to S (per the transition matrix) returns the saga unchanged AND does NOT add new ledger rows OR outbox events.

This exercises `SagaOrchestrator._is_idempotent_replay` directly with random target states.

### AC7: Property P5 — Cross-tenant idempotency-key collision always raises

`@given(amount=monetary_amounts(), key=uuids())` for two distinct users:
- User A calls `start(saga_type="x", user_id=A, idempotency_key=K, payload=P, amount=amt)` → succeeds
- User B calls `start(saga_type="x", user_id=B, idempotency_key=K, payload=P, amount=amt)` → raises `CrossTenantKeyError`

Regression-locks the M2.2a S1 security fix against any random-input regression.

### AC8: Property P6 — Outbox event count matches transition count

For any walk that successfully applies N transitions, exactly N rows exist in `outbox` table for that saga_id. No more, no less.

This catches bugs like "transition writes to wrong table" or "transition writes 2 events instead of 1" or "idempotent replay leaks an event".

### AC9: Property P7 — Body-hash idempotency holds across N **sequential** retries

Repeat `start(...)` with the **same** `(idempotency_key, body)` N times (N=1-10), **awaited sequentially in one event loop** (R1.1 — concurrent retry storm is M3 scope). Assert all calls return the same `saga_id` AND only ONE row exists in `billing_idempotency_keys` table for that key.

Catches: race condition in P23 implementation that might insert duplicate idempotency rows under retry.

### AC10: Settings tuning — keep CI fast

All property tests use:
```python
_FAST = settings(
    max_examples=20,            # enough to find 95%+ of bugs; 100+ for M2.2c
    deadline=3000,              # 3s per example wall-time
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    derandomize=True,           # CI determinism — same seed every run unless --hypothesis-seed
)
```

derandomize=True locks the CI surface: tests pass deterministically and never gain new flakiness from random seed shifts.

### AC11: Quality gates (per `feedback_full_quality_gates`)

Run BEFORE committing:
- `uv run ruff check apps packages` → 0 errors
- `uv run ruff format --check apps packages` → 0 changes needed
- `uv run mypy apps packages` → 0 errors
- `pnpm -C apps/web build` → 0 errors (no FE changes but regression guard)
- ALL Python tests pass (109 billing existing + 7 new = 116 billing + others unchanged)

### AC12: NFR alignment

- **NFR-R4 (对账误差 = 0)**: P1 + P6 strengthen the invariant from "55 points proven" to "any walk of length 1-4 in our trigger graph proven"
- **NFR-S1 (cross-tenant separation)**: P5 regression-locks M2.2a S1 fix
- **NFR-Q1 (CI time)**: all property tests budget < 30s total → AC10 settings

## Tasks

### T1: Strategies + walk generator (1h)
1. Create `apps/billing-service/tests/test_property_saga_walks.py` skeleton
2. Inline (local) `valid_walks()` strategy generator per AC2
3. Import shared `monetary_amounts` + `uuids` from `opticloud_shared.property_test_base.strategies`
4. Set up `_FAST` settings preset per AC10

### T2: P1 + P2 + P3 — single-saga walk invariants (1.5h)
1. P1 no-money-creation test: drive saga through a generated walk; sum ledger; assert in [-amount, 0]
2. P2 terminal absorption test: drive to terminal; assert any apply raises SagaTerminalError
3. P3 amount immutability test: assert `saga.amount == initial` after every step

### T3: P4 + P6 — idempotency + outbox count (1h)
1. P4 idempotent replay: walk to state S; re-apply S's incoming trigger; assert saga unchanged + no new ledger/outbox rows
2. P6 outbox count: walk N steps; assert `count(outbox WHERE aggregate_id = saga.id) == N`

### T4: P5 + P7 — multi-saga cross-tenant + idempotency (1h)
1. P5 cross-tenant collision: two user_ids same key → CrossTenantKeyError
2. P7 retry storm: same (key, body) repeated 1-10 times → single saga_id + single idempotency_keys row

### T5: Sprint sync + Quality gates + PR (0.5h)
1. Update `sprint-status.yaml` add `m2-2b-saga-property-tests: done` row near m2-2a (and add `m2-2c-billing-reconciler-job` as a NEW backlog row for the tech-debt from 5.A.4)
2. Update memory file `opticloud-project-status.md` (test counts + main commit)
3. Run AC11 quality gates
4. Commit + push + PR

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Hypothesis finds a real bug (story scope balloons) | Acceptable — story budget includes 1-2h for "found bug, fixed it" overhead. If >2h, split into M2.2b-fix and stop M2.2b at "test infrastructure complete + N findings cataloged" — better to land tests than to land tests + every fix in one PR. |
| Function-scoped fixtures + @given is a known Hypothesis health-check warning | `suppress_health_check=[HealthCheck.function_scoped_fixture]` per AC10; this pattern is already used in `test_invariants.py` so it's project-blessed. |
| Async test runs with @given are slow | `derandomize=True` + `max_examples=20` keeps total wall-time under 30s. CI has tolerance for 30s of new tests. |
| Property tests depend on DB state from previous test → flaky | Each property test creates fresh sagas with `uuid.uuid4()` idempotency keys; no shared mutable state. Same fixture pattern as M2.2a (which is stable across 6+ PRs). |
| `valid_walks()` strategy is biased (over-samples short walks) | Use `st.lists(...).filter(...)` with explicit length range and `st.composite` if needed; documented + asserted via a "smoke" test that counts walk lengths across N runs. |
| Hypothesis-generated test names collide with M2.2a parametrize IDs (debugging confusion) | Property test fns prefixed `test_property_*` (separate naming convention); pytest will list both prefixes clearly. |

## Non-Functional Requirements Mapping

- **NFR-R4 (对账误差 = 0)**: P1 + P6 + P7 broaden the invariant from "pointwise proven" to "all-paths proven"
- **NFR-S1 (cross-tenant)**: P5 regression-locks M2.2a S1 fix
- **NFR-Q1 (CI green time)**: AC10 settings budget < 30s wall-time
- **ADR-0001 §Test Pyramid Layer 3**: this story = layer 3

## Definition of Ready

- ✅ SagaOrchestrator is stable (no behavior change since 5.A.4 PR #6)
- ✅ Hypothesis strategies module exists in `opticloud_shared.property_test_base` from Story 0.5b
- ✅ `test_invariants.py` demonstrates the `@given` + DB session pattern; we mirror that
- ✅ All 3 review rounds applied (next step)

## Definition of Done

- All 12 ACs pass
- 5-7 new property tests in `test_property_saga_walks.py` (count exact at implement time)
- billing-service total: 109 → 116 (or higher if a property test reveals a bug needing a regression test)
- Hypothesis examples database NOT checked in (`.hypothesis/` should already be in `.gitignore`; verify)
- CI green on PR
- Sprint-status.yaml updated (+ m2-2c-billing-reconciler-job NEW backlog entry from 5.A.4 tech-debt)
- Memory updated
- Code review with full quality gates documented in commit body

## Sign-off (story-level)

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Test Architect | proposed by AI | ☐ | — |
| Billing Lead | TBA | ☐ | — |

> Owner committee deferred per M0 skip.
