# Repro Bitwise Audit SOP

> **Owner**: Solver Lead + SRE
> **Status**: M5 quarterly audit draft
> **Source**: Story 6.B.7 / Expert Panel E11
> **Last Updated**: 2026-05-22

---

## Purpose

This runbook defines the quarterly voucher bitwise reproducibility audit. The audit samples issued durable vouchers, reruns the locked source payload through the current supported solver path, and compares deterministic result digests with strict equality.

The current implementation covers live LP / `highs` vouchers only. Unsupported task types or locked solvers are reported as skipped coverage gaps.

---

## Command

Run from the repository root with solver-orchestrator dependencies available:

```powershell
$env:PYTHONPATH="$PWD\apps\solver-orchestrator\src;$PWD\packages\shared-py"
uv run python -m solver_orchestrator.repro_bitwise_audit_cli --markdown
```

Default outputs:

- JSON: `_bmad-output/reports/repro-bitwise/latest.json`
- Markdown: `_bmad-output/reports/repro-bitwise/latest.md`

Generated reports are runtime artifacts. Do not commit them unless a later evidence story explicitly requests committed snapshots.

---

## Sampling Policy

- Default cadence: quarterly.
- Default sample rate: 5%.
- Sample size: `ceil(eligible_count * sample_rate)`, minimum one when eligible vouchers exist and sample rate is greater than zero.
- Default pass-rate threshold: 95%.
- Default executable-coverage threshold: 95%.

Eligible vouchers:

- `reproduction_vouchers.status = 'issued'`
- source `optimizations.status = 'completed'`
- within the 5-year rerun window from `reproduction_vouchers.created_at` UTC

Ineligible vouchers are counted separately when revoked, expired, missing source optimization, or tied to a non-completed source optimization.

---

## Result Interpretation

Report statuses:

| Status | Meaning | Exit |
|---|---|---:|
| `passed` | Executable samples met pass-rate and coverage thresholds | 0 |
| `failed` | At least one executable sample failed and pass rate is below threshold | 1 |
| `insufficient_executable_coverage` | Sampled vouchers existed, but too many were skipped or none executable | 1 |
| `no_eligible_vouchers` | No eligible issued vouchers existed at audit time | 0 |

Pass rate is `passed / (passed + failed)`.

Executable coverage is `(passed + failed) / sampled_count`.

Skipped samples do not count as passes. They are coverage gaps that should be reviewed by Solver Lead.

---

## Evidence Handling

The report stores only pointer IDs, status, reason strings, and SHA-256 digests. It must not contain raw optimization payloads, full solver outputs, user IDs, API key IDs, billing identifiers, email, phone, or legal names.

Store quarterly reports in the operational evidence store selected by SRE. Link the report from the quarterly review ticket or audit record.

---

## Failure Triage

1. Confirm the voucher row and source optimization still exist.
2. Compare `expected_digest` and `observed_digest`.
3. Re-run the audit for the single voucher in a staging database snapshot when possible.
4. If the failure depends on a missing archived solver image or future provider image restore path, follow [`repro-image-restore.md`](repro-image-restore.md).
5. If the digest mismatch reproduces on the live solver path, open a P1 solver regression ticket.
6. Escalate to P0 only when broad voucher corruption, data loss, or security exposure is suspected.

---

## Related Docs

- Runbooks index: [`README.md`](README.md)
- Image restore SOP: [`repro-image-restore.md`](repro-image-restore.md)
- Story 6.B.7: [`../../_bmad-output/stories/6-b-7-bitwise-reproducibility-test.md`](../../_bmad-output/stories/6-b-7-bitwise-reproducibility-test.md)
