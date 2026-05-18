# ADR-0002 — Outbox Relayer Deployment Mode

- **Status**: accepted
- **Date**: 2026-05-18
- **Deciders**: SRE (proposed); Architect / Billing Lead (signoff pending — v1.5 hard-gate)
- **Story**: [M2.0 Architectural Spike](../../_bmad-output/stories/m2-0-saga-spike.md)
- **Depends on**: [ADR-0001 — Saga Pattern](0001-saga-pattern.md)

## Context

Per **ADR-0001**, our Hybrid Saga orchestrator writes business state + outbox events in the **same DB transaction** (P33 Outbox Pattern). A separate process must then read the `outbox` table and publish to the message broker (Redis pub/sub v1; v2+ Kafka).

Architecture v2.2 constraints:
- **P33** Outbox Pattern (transactional dual-write to outbox + business tables)
- **P56** Outbox Relayer **Sidecar** — relayer co-deployed with business service
- **C12** Outbox Relayer **separate from business Dramatiq actor** (relayer != business worker)
- **B2** M1: fire-and-forget pub/sub; **M2+: outbox sidecar**
- **C9** Postgres TDE + Vault dev mode (event payload may contain sensitive metadata)
- **P60** Three-domain K8s namespace single-direction flow (prod-core → prod-ai → prod-data)

We need to choose the **deployment mode** and the **implementation technology** for the relayer.

## Decision

Adopt **K8s sidecar container** model, implemented as **Dramatiq-actor-based polling loop**, deployed per business service pod.

- Each business service that emits outbox events (initially: `billing-service`, later: `auth-service`, `chat-service`, `repro-service`) ships **one sidecar container per pod**.
- Sidecar polls its **own service's** `outbox` table (same DB, same schema) via `LISTEN/NOTIFY` + fallback periodic `SELECT ... WHERE sent_at IS NULL FOR UPDATE SKIP LOCKED LIMIT 100`.
- Publishes to Redis pub/sub (v1) / future Kafka topic (v2+).
- Marks `outbox.sent_at = NOW()` on success.

This satisfies **P56** (sidecar) and **C12** (separate process from business Dramatiq actor); reconciles their apparent contradiction by being "co-located but separate process".

## Status

`accepted` — implementation in [Story M2.1](../../_bmad-output/stories/) Outbox Relayer Sidecar.

## Consequences

### Positive

- **Co-located** → low latency (DB on same network path; LISTEN/NOTIFY pushes within ms)
- **Per-service isolation** → one service's outbox failures can't poison another's pipeline
- **Same pod lifecycle** → relayer scales with service automatically; one pod down = one slice of outbox load down (graceful)
- **Implementation simplicity** → Dramatiq + Postgres LISTEN bindings exist; ~200 LOC per relayer
- **Schema migration**: P63 dual-publish handled at orchestrator (event versioning) — relayer is schema-agnostic

### Negative

- **Replication cost** — N services × N sidecars = N relayer instances. For 5-10 services (v1) this is fine; v2+ might benefit from a shared relayer service
- **Pod-level fate sharing** — pod crash takes sidecar; recovered together (acceptable — events stay in DB until sent_at written)
- **Schema migration discipline** — multiple relayer instances must roll deploy in compatible order

### Mitigations

| Risk | Mitigation |
|---|---|
| Sidecar lag during peak load | Poll interval **100ms** + LISTEN/NOTIFY push; observed lag < 500ms P95 |
| Duplicate publishing under restart | UPDATE `sent_at` only after broker ACK; consumer-side dedup via `event_id` |
| Cross-namespace traffic blocked by P60 | All relayers run in **same namespace as their service** (prod-core for billing, etc.); Redis broker accessible from each service namespace per P60 single-direction flow rules |
| TDE + Vault key access | Sidecar uses service's Vault sidecar mount; no separate auth (C9 alignment) |

## Network: cross-namespace traffic

Per P60 three-domain (prod-core / prod-ai / prod-data):

- `outbox` table lives in business service's Postgres (e.g. `billing-service` → prod-core DB cluster). Sidecar reads via local TCP within prod-core. ✅ no cross-namespace.
- Redis broker: deployed in **prod-core** (NOT prod-data) because billing critical traffic must avoid prod-data egress per P60. Each service-namespace publishes via direct Redis URL within prod-core. ✅ matches single-direction flow rules.

### Direction matrix (CR6 fix from M2.0 design review)

| Direction | Allowed? | Notes |
|---|:-:|---|
| prod-core → prod-core (intra-zone) | ✅ | Billing publish to Redis broker — same namespace |
| prod-ai → prod-core (consumer subscribe) | ✅ | Chat / Critic / Sandbox subscribe to events; P60 explicitly permits **read-only** event subscription cross-zone in this direction |
| prod-data → prod-core | ❌ | P60 single-direction flow rule (prod-data is sink, never originates) |
| prod-core → prod-ai | ✅ | Push notifications (e.g. Chat needs Billing event) |
| prod-core → prod-data | ✅ | Audit log writes to prod-data (write-only) |
| prod-ai → prod-data | ✅ | Sandbox writes results to prod-data |

**Implementation gate**: M3.3a K8s NetworkPolicy enforces these directions; relayer sidecar verified to comply at deploy time.

## Implementation technology selection (R1-2 fix from Round 1)

| Option | Pros | Cons | Decision |
|---|---|---|:-:|
| **Dramatiq actor (chosen)** | Already in use for async tasks; mature; Postgres + Redis bindings | Couples relayer to Dramatiq version | ✅ |
| Cron loop (Python script + apscheduler) | Simple, no deps | Poll-only (no LISTEN/NOTIFY); higher lag | ❌ |
| Debezium (Postgres CDC) | Excellent CDC; multi-broker | JVM overhead; ops complexity; overkill v1 | ❌ Reconsider v2+ |
| Custom asyncio loop | Tight control; minimal deps | More code to maintain; reinvent backoff/dedup | ❌ |

## Poll frequency / lag budget

- **LISTEN/NOTIFY** push: best-effort < 50ms
- **Fallback polling**: every **100ms** (P95 lag < 500ms expected)
- **Lag SLO**: P95 < 1 second from `outbox.created_at` to broker ACK (M2 target); P99 < 5s
- **Alert thresholds**: P95 > 2s for 5 min → page SRE

## Alternatives Considered

| Mode | Failure isolation | Resource overhead | Deployment complexity | Schema migration | Poll frequency tolerance | Eval |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| **In-process** (relayer inside business service) | 🔴 service crash kills relayer | 🟢 minimal | 🟢 zero | 🟢 trivial | 🟡 must share thread budget | ❌ M1 only |
| **Sidecar (chosen)** | 🟡 pod fate-sharing | 🟡 +N replicas | 🟡 +1 container per pod | 🟢 same-pod rollouts | 🟢 dedicated process | ✅ M2+ |
| **Separate service** | 🟢 fully independent | 🔴 1-2 always-on pods | 🔴 separate deploy + scaling | 🔴 multi-service migration coord | 🟢 dedicated cluster | ❌ Reconsider v2+ |

**Per-service replicated sidecar** chosen over single-service-shared because: (a) per-service blast radius isolation; (b) DB locality (no cross-service DB query); (c) Architecture v2.2 P56 + C12 explicitly suggests this.

## References

- **Architecture v2.2**: P33 Outbox / P56 Sidecar / C12 separate from business actor / B2 M1-M2 boundary / C9 TDE / P60 namespace flow / P63 event versioning
- **Down-stream**: [Story M2.1 Outbox Relayer Sidecar Implementation](../../_bmad-output/stories/)
- **Companion**: [ADR-0001 — Saga Pattern](0001-saga-pattern.md)
- **External**:
  - Postgres LISTEN/NOTIFY: https://www.postgresql.org/docs/current/sql-notify.html
  - Dramatiq + Postgres broker: https://dramatiq.io/

## Sign-off (v1.5 hard-gate, pending)

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| SRE | TBA | ☐ | — |
| Architect | TBA | ☐ | — |
| Billing Lead | TBA | ☐ | — |

> Pending team formation. ADR is **accepted** for dev work; signatures collected before v1.5 商用 hard-gate.
