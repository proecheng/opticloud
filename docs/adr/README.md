# OptiCloud Architecture Decision Records (ADR)

> **Format**: Nygard simplified (Context / Decision / Status / Consequences / Alternatives / References)
> **When to write an ADR**: any architectural choice that needs cross-team alignment + is not cheap to reverse
> **Numbering**: monotonic 4-digit (`NNNN-kebab-title.md`)

## Index

| # | Title | Status | Owners | Related |
|:-:|---|:-:|---|---|
| **[0001](0001-saga-pattern.md)** | Saga Pattern for Distributed Billing Transaction | accepted | Billing Lead / Solver Lead / SRE | Concern #13 / Story 5.A.0 / M2.2a |
| **[0002](0002-outbox-relayer-deployment.md)** | Outbox Relayer Deployment Mode | accepted | SRE / Architect / Billing Lead | P33 / P56 / C12 / Story M2.1 |

## ADR-0001 ↔ ADR-0002 Relationship

```
ADR-0001 (Saga 选 Hybrid Orchestration)
        ↓ defines: event types + transition matrix
ADR-0002 (Outbox 选 Sidecar)
        ↓ defines: how those events leave the service
↓
Story 5.A.0 + M2.1 + M2.2a (implementation)
```

**Why a Saga ADR before an Outbox ADR**: the Saga decision determines what events flow (e.g. `billing.reserved` / `billing.charged` / `billing.refunded`). The Outbox just delivers them. If we picked Choreography (event-driven), Outbox would need different durability semantics.

## Lifecycle

- `proposed`: under discussion, not yet implementable
- `accepted`: implementation may rely on it; changes require new ADR superseding
- `superseded by NNNN`: history record only

## v1.5 商用前 hard-gate

All accepted ADRs touching financial / safety semantics (0001 / 0002 / future cost-attribution) require **3-owner signoff** (Billing Lead / Solver Lead / SRE) before M5 商用. Pending signoffs do **not** block dev work but **do** block 商用 hard-gate.
