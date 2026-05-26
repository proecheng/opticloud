# Repro Image Restore SOP

> **Owner**: DevOps / SRE + Solver Lead
> **Status**: M3-M5 operational contract draft; depends on G7 image archival pipeline
> **Source**: Story 6.B.6 / G7 Image 5y archival
> **Last Updated**: 2026-05-22

---

## Purpose

This runbook defines how OptiCloud treats image archival recovery for reproducibility vouchers. The 5-year reproducibility / image archival clock starts at `reproduction_vouchers.created_at` in UTC.

This document is the operational reference for the archive path. It does not claim that the full G7 hot / warm / cold archive pipeline has already shipped.

Story M3.0 adds the local prep contract for that future pipeline: [`../../infra/image-archival/README.md`](../../infra/image-archival/README.md) and [`../../infra/image-archival/archive-plan.json`](../../infra/image-archival/archive-plan.json). The contract validates tier boundaries and required restore metadata only. It does not provision ACR EE, create S3 lifecycle policies, submit Glacier restore jobs, write Vault / KMS backups, or prove the M3.9 cloud pipeline is live.

---

## Scope

Use this SOP when a voucher-backed rerun or audit needs the archived solver image, model artifact, or execution image referenced by the original voucher.

In scope:

- Voucher-backed image lookup and recovery.
- Archive availability checks across hot ACR EE, warm object storage, and cold Glacier-class storage.
- Restore evidence records and exception records.
- Quarterly drill checklist.
- M3.0 prep validation for the local archive plan contract.

Out of scope:

- Changing voucher issuance, rerun, billing, or provider migration code.
- Legal advice or contract drafting.
- Creating the G7 archival pipeline itself.
- Treating M3.0 prep validation as evidence that real ACR EE retention, S3 lifecycle transition, Glacier restore, Vault / KMS backup automation, or ≤5 minute cold restore has shipped.

---

## Clock Source

The only SLA start point is the durable voucher row timestamp:

- Source field: `reproduction_vouchers.created_at`
- Timezone: UTC
- Original voucher: use the original voucher row's `created_at`
- Rerun child voucher: use the child voucher row's own `created_at`
- Parent clock: a child rerun does not extend or reset the parent voucher's archival promise

Do not use optimization completion time, rerun request time, archive transition time, provider exit time, or legal handover time as the SLA start point.

---

## Required Inputs

Before restore, collect:

| Input | Source |
|---|---|
| Voucher ID | User request / audit request |
| `reproduction_vouchers.created_at` | Durable voucher row |
| Optimization ID | `reproduction_vouchers.optimization_id` |
| Algorithm SKU / task type | Source optimization metadata |
| Locked solver | `reproduction_vouchers.locked_solver` |
| Locked model version | `reproduction_vouchers.locked_model_version` |
| Request fingerprint | `reproduction_vouchers.request_fingerprint` |
| Archived image ID / digest | G7 image archival index once available |
| Archive tier | Hot ACR EE / warm object storage / cold Glacier-class storage |

If the G7 archival index is not available yet, record the request as an archive-path readiness gap, not as a completed restore.

---

## Decision Tree

1. Confirm the voucher exists and the requester is allowed to use it.
2. Read `reproduction_vouchers.created_at` and calculate whether the 5-year clock is still within scope.
3. Confirm the requested image digest matches the voucher's locked solver / model version context.
4. Choose restore tier:
   - Hot: ACR EE image available within the hot retention window.
   - Warm: object storage copy available after hot expiry.
   - Cold: Glacier-class archive restore required.
   - Prep validation: the desired tier boundaries are documented in [`../../infra/image-archival/archive-plan.json`](../../infra/image-archival/archive-plan.json), but M3.9 must still implement the real cloud lifecycle and restore operations.
5. If no matching archived image exists, create an unavailable-restore exception record.
6. If the image restores, verify digest, signature, and locked metadata before rerun or audit use.

---

## Restore Steps

### Hot Tier

1. Locate image by digest in ACR EE.
2. Verify image signature and digest.
3. Confirm locked solver / model version match the voucher metadata.
4. Record restore evidence.

### Warm Tier

1. Locate object storage copy by voucher / image digest.
2. Copy image artifact to the recovery staging area.
3. Verify checksum, signature, and metadata.
4. Promote to the execution registry only after verification.
5. Record restore evidence.

### Cold Tier

1. Submit Glacier-class restore request for the image artifact.
2. Record restore request ID and expected retrieval window.
3. After retrieval, copy the artifact to recovery staging.
4. Verify checksum, signature, and metadata.
5. Promote to execution registry only after verification.
6. Record restore evidence.

---

## Restore Evidence

For every successful restore, record:

- Voucher ID
- `reproduction_vouchers.created_at` in UTC
- Restore request timestamp in UTC
- Archive tier used
- Image digest before and after restore
- Signature / checksum verification result
- Locked solver and locked model version
- Operator
- Outcome: `restored`

Store the evidence with the incident or audit record that triggered the restore.

---

## Unavailable-Restore Exception

If the image cannot be restored, record:

- Voucher ID
- `reproduction_vouchers.created_at` in UTC
- Archive tier attempted
- Missing or corrupt artifact identifier
- Whether the 5-year clock was still within scope
- User-visible remediation owner
- Engineering owner
- Outcome: `unavailable`

Escalate as a P1 unless user data loss, security leakage, or broad archive corruption is suspected; then escalate as P0.

---

## Quarterly Drill Checklist

- [ ] Select at least one voucher-like staging record per archive tier.
- [ ] Confirm each selected record has `reproduction_vouchers.created_at` or a staging-equivalent timestamp.
- [ ] Restore hot-tier artifact and verify digest / signature.
- [ ] Restore warm-tier artifact and verify digest / signature.
- [ ] Restore cold-tier artifact or run a documented cold-restore simulation if Glacier retrieval cost is explicitly waived by SRE.
- [ ] Record evidence for every restored artifact.
- [ ] Record exception tickets for missing metadata, missing archive index rows, or unverifiable signatures.
- [ ] Review drill output with SRE, Solver Lead, and Founder.

---

## Escalation

| Condition | Severity | Escalate To |
|---|---|---|
| Single voucher restore unavailable, no data loss | P1 | SRE + Solver Lead |
| Archive index missing for multiple vouchers | P1 | SRE + Architect |
| Signature / digest mismatch | P0 | SRE + Security + Founder |
| Broad archive corruption or deletion | P0 | Founder + SRE + Legal |

---

## Related Docs

- Runbooks index: [`README.md`](README.md)
- Academic provider handbook: [`../academic-provider-handbook.md`](../academic-provider-handbook.md)
- Academic onboarding FAQ: [`../customer-faqs/academic-onboarding-faq.md`](../customer-faqs/academic-onboarding-faq.md)
- Legal templates index: [`../legal-templates.md`](../legal-templates.md)
- Story 6.B.6: [`../../_bmad-output/stories/6-b-6-voucher-5y-sla-tracking.md`](../../_bmad-output/stories/6-b-6-voucher-5y-sla-tracking.md)
