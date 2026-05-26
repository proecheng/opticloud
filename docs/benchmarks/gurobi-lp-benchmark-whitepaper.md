---
owner: Marketing / Founder
status: evidence_required
claim_status: operator_evidence_required
evidence_status: operator_evidence_required
story_key: m4-5b-gurobi-benchmark-whitepaper
source_gap: E3
intended_audience: Commercial buyers evaluating migration from self-managed optimization tooling
approvals_required: Solver Owner, Legal, Marketing
last_updated: 2026-05-27
---

# Gurobi LP Benchmark Whitepaper Draft

## Summary

This draft defines the structure for a future 30-LP comparison between OptiCloud's LP workflow and a BYO-license Gurobi reference path.

Current status: `evidence_required`. No verified Gurobi result is committed in this repository.

## Problem

Commercial buyers often ask how to evaluate migration from self-managed optimization tooling to an API-based workflow. A useful answer needs reproducible fixtures, explicit solver identities, comparable metrics, and a publication gate.

## Comparison Methodology

The methodology is defined in `docs/benchmarks/gurobi-lp-benchmark-methodology.md`. It uses the synthetic fixture suite in `tools/gurobi_benchmark/lp_fixture_suite.json`.

## Fixture Composition

| Category | Fixture Count | Status |
|---|---:|---|
| small_bounded | 5 | pending_verified_evidence |
| resource_allocation | 5 | pending_verified_evidence |
| blending | 5 | pending_verified_evidence |
| transportation_style | 5 | pending_verified_evidence |
| scheduling_style | 5 | pending_verified_evidence |
| stress_scale_synthetic | 5 | pending_verified_evidence |

## Metrics

The future evidence package must report status parity, objective delta, primal feasibility residual, runtime seconds, timeout/error count, and unsupported-case notes.

## Result Table Structure

| Fixture | OptiCloud / HiGHS Status | Gurobi Status | Objective Delta | Runtime Notes |
|---|---|---|---|---|
| lp-001 through lp-030 | pending_verified_evidence | pending_verified_evidence | pending_verified_evidence | pending_verified_evidence |

## Interpretation Rules

- A valid evidence manifest means structure and redaction passed.
- Public claims require evidence status `verified` plus legal and marketing approval.
- Pending evidence must not be treated as proof.
- This draft does not make production equivalence, speed, cost, or superiority claims.

## Publication Gate

The whitepaper can move toward publication only after an operator produces `reports/gurobi-benchmark/<run_id>/evidence_manifest.json`, the validator accepts it in real-evidence mode, redaction review passes, and approval status is advanced through the required review flow.
