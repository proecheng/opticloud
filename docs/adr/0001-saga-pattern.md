# ADR-0001 — Saga Pattern for Distributed Billing Transaction

- **Status**: accepted
- **Date**: 2026-05-18
- **Deciders**: Architect (proposed); Billing Lead / Solver Lead / SRE (signoff pending — v1.5 hard-gate)
- **Story**: [M2.0 Architectural Spike](../../_bmad-output/stories/m2-0-saga-spike.md)

## Context

OptiCloud Billing requires **double-entry credit ledger + idempotent charge + refund + audit trail** across at least 3 services:

- `auth-service` issues API Keys (caller identity)
- `solver-orchestrator` consumes Credits per solve
- `billing-service` (Story 5.A) owns the ledger

Per Architecture v2.2:
- **Concern #13** Distributed Billing Transaction
- **PRD NFR-R4**: 计费对账误差 = 0
- **P33** Outbox Pattern (transactional dual-write)
- **P63** Event Versioning (dual publish, N=3 month)
- **B2** boundary: M1 fire-and-forget pub/sub; M2+ outbox sidecar

We need a coordination pattern for the multi-step transaction (reserve → charge → commit / refund / rollback) that is **observable, testable, and recoverable** under partial failures.

## Decision

Adopt **Hybrid Saga**:
- **Orchestration** for the core financial state machine (Credits ledger writes) — centralized in `billing-service`. Single explicit state machine, easy to reason about correctness + audit.
- **Choreography** for non-financial fan-out (audit log writes, notification emails, user-facing webhooks). Loose coupling, no single point of failure for non-critical paths.

The orchestrator lives in `billing-service`; consumers (`solver-orchestrator`, `web`) call `billing-service` synchronously for charge intent, then receive event-driven status updates via Outbox (ADR-0002).

**Hybrid split (≥3 examples)**:

| Event | Mode | Reason |
|---|---|---|
| `billing.charge.intent` → reserve → charge | **Orchestration** | Money — must guarantee no double charge / no lost charge |
| `billing.refund` | **Orchestration** | Same; financial reversal |
| `audit.log.write` (post-charge) | Choreography | Best-effort, eventual consistency OK |
| `notification.email.send` (receipt) | Choreography | Tolerates failure; retry separately |
| `webhook.delivery` (Provider integration v2) | Choreography | Owner = Provider, not billing-critical |

## Status

`accepted` — proposed 2026-05-18 in M2.0 spike. Implementation stories: 5.A.0a/b/c + M2.1 + M2.2a.

## Consequences

### Positive

- **Single source of truth** for Credits state — `billing-service` owns the orchestrator. Bug fixes in one place.
- **Observable** — state transitions auditable from `billing.saga_state` table; replayable via Repro 5y vouchers (Innovation #2).
- **Testable** — orchestrator is a pure state machine + side effects; Hypothesis property tests cover invariants.
- **Loose coupling for non-critical paths** — adding new notification channels doesn't touch billing core.
- **NFR-R4 compliance** — double-entry + Saga compensations → 计费对账误差 = 0 achievable.

### Negative

- **Orchestrator is a single point of failure** — `billing-service` outage halts all charges. Mitigation: P59 4-tier resilience + active-active deploy v1.5+.
- **State persistence cost** — every transition writes to `saga_state` table → DB load. Mitigation: P5 Redis cache for in-flight Sagas; archive completed Sagas to cold storage after 90 day.
- **Complexity vs simpler choreography** — for a tiny startup, choreography is "free". We accept orchestration overhead for audit / compliance benefits.

### Mitigations

| Risk | Mitigation |
|---|---|
| Orchestrator deadlock under partial failure | **Saga timeouts**: each transition has explicit timeout (table below); on exceed → compensating action |
| Retry storms | Exponential backoff: `2^n` seconds capped at 60s; **max retries = 5**, then DLQ |
| DLQ pile-up | Daily SRE on-call scans DLQ; alert via Prometheus rule `saga_dlq_size > 100` |
| PII in saga state | `saga_state.payload` redacts amount / customer details into separate audited table; only state + transition references persist |

## Saga State Machine (spec for Story 5.A.0a implementation)

```
            ┌─────────┐
            │ pending │
            └────┬────┘
       │ reserve │
       ↓ (≤500ms, 5 retry, exp backoff)
            ┌─────────┐
            │reserved │──────────┐
            └────┬────┘          │
       │ charge │              │ cancel (user)
       ↓ (≤2s, 3 retry)       ↓
            ┌─────────┐    ┌──────────┐
            │ charged │    │ refunded │ (terminal)
            └────┬────┘    └──────────┘
       │ emit-outbox │
       ↓ (≤500ms, infinite retry — outbox sidecar)
            ┌───────────┐
            │ completed │ (terminal)
            └───────────┘

failure escapes: charged → rolled_back (if downstream rejects + we already charged)
                 reserved → failed (if reserve OK but pre-charge check fails)
```

### Transition matrix

| From → To | Trigger | Timeout | Retry | Compensation | Cost (median latency) |
|---|---|:-:|:-:|---|:-:|
| `pending → reserved` | API entry + Idempotency-Key | 500ms | 5 / exp backoff | mark `failed` | ~5ms |
| `pending → failed` | balance < required | — | — | none | ~2ms |
| `reserved → charged` | solver/service success | 2s | 3 / exp backoff | `refunded` (auto) | ~10ms |
| `reserved → refunded` | user cancel | 500ms | 3 | none | ~5ms |
| `reserved → failed` | pre-charge guard reject | — | — | none | ~3ms |
| `charged → completed` | outbox event delivered | 500ms | ∞ (DLQ at 5) | retry; alert SRE | ~3ms |
| `charged → rolled_back` | downstream rejects late | 1s | 1 | escalate to ops | ~10ms |

**Invariants** (≥3, used by Hypothesis property tests):
1. Any sequence of valid transitions ends at a state ∈ `State` enum (no dangling)
2. After `refunded` / `rolled_back`, recorded refund_amount ≤ original charge_amount
3. Terminal states (`completed` / `failed` / `refunded` / `rolled_back`) reject all further transitions
4. **Idempotency**: same Idempotency-Key + identical request body → identical final state (Q1 fix from Round 2)

## Security: Saga state PII redaction

`saga_state` table holds:
- `saga_id` (UUID) — no PII
- `current_state` (enum) — no PII
- `user_id` (UUID) — pseudonymous link
- `idempotency_key` (string) — not sensitive (random uuid)
- `created_at / updated_at` — not sensitive

**Sensitive fields kept in `billing.credit_transactions` (separate table)**:
- `amount` (decimal)
- `currency`
- `metadata` (JSONB; may contain task_type + payload hash, NOT raw payload)

Audit log queries against `saga_state` are non-PII; queries against `credit_transactions` require Team+ scope (NFR-A1 + NFR-C6 PIPL alignment).

## How to test (M2.2a story input)

The orchestrator is testable as a **pure function** of `(current_state, event, body)` → `(new_state, side_effects)`. Test layers:

1. **Property** (`packages/shared-py/tests/test_saga_state_machine.py`, this story): 4 invariants via Hypothesis (no dangling state / refund ≤ charge / terminal stickiness / idempotency)
2. **Critical scenarios** (Story M2.2a, ≥50 cases): hand-written tests for the exact transition matrix rows + failure paths
3. **Property + business** (Story M2.2b): Hypothesis-generated random transition sequences run against a reference oracle implementation
4. **Full coverage** (Story M2.2c, M5): 500+ scenarios including all DLQ paths, schema migrations, multi-tenant isolation
5. **Contract** (Story M3.2 Schemathesis): API-level contract over `POST /v1/optimizations` charge intent → response

## Alternatives Considered

| Dimension | Orchestration (chosen) | Choreography | Hybrid (chosen for non-critical) |
|---|:-:|:-:|:-:|
| **Observability** | 🟢 single state in one place | 🔴 distributed; need eventing tracing | 🟢 orchestrator core + event tail |
| **Debugging difficulty** | 🟢 inspect state table | 🔴 follow event chains across services | 🟢 follow orchestrator log |
| **State centralization** | 🟢 strong consistency in orchestrator | 🔴 eventual / fragmented | 🟢 critical centralized |
| **Failure handling** | 🟢 explicit compensations | 🟡 each service decides; complex coord | 🟢 same as orchestration for critical |
| **Cross-service change cost** | 🟡 orchestrator + participant update | 🟢 minimal — participant local | 🟢 financial fixed; non-critical loose |
| **Retry + DLQ strategy** | 🟢 centralized; easy to tune | 🔴 per-service; inconsistent | 🟢 centralized for financial |

**Pure Choreography rejected** because: (a) credit reconciliation requires single linearization point; (b) audit trail per Saga is essential for PIPL data export (FR B10) + Repro 5y vouchers (FR R3); (c) debugging multi-service event chains under 1-2 person team (精简档) is too costly.

**Pure Orchestration rejected** because: notification / audit-log fan-out doesn't benefit from centralization and bottlenecks orchestrator.

**Workflow engine** (Temporal, Camunda) considered + rejected: vendor lock-in (R11), operational overhead, 5-9 person team needed for ops. **Reconsider at v2.5+** when team grows.

## References

- **Architecture v2.2**: Concern #13 Distributed Billing Transaction / P33 Outbox / P63 Event Versioning / B2 boundary
- **PRD v1.1**: NFR-R4 (计费对账误差 = 0) / FR B1-B13 / FR R3 (Repro 5y rerun)
- **Down-stream stories**:
  - [Story 5.A.0a](../../_bmad-output/stories/) Saga State Diagram (implementation)
  - [Story 5.A.0b] Saga Contract Test Fixtures
  - [Story 5.A.0c] Cross-Epic Saga Dry-Run
  - [Story M2.2a](../../_bmad-output/stories/) Billing 50 Critical Scenarios
- **Companion**: [ADR-0002 — Outbox Relayer Deployment](0002-outbox-relayer-deployment.md)

## Sign-off (v1.5 hard-gate, pending)

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Billing Lead | TBA (post team formation) | ☐ | — |
| Solver Lead | TBA | ☐ | — |
| SRE | TBA | ☐ | — |

> User has previously deferred M0 team formation. ADR is **accepted** for dev work; signatures collected before v1.5 商用 hard-gate.
