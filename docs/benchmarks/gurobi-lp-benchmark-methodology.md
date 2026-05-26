---
owner: Marketing / Solver Owner
status: internal_ready
claim_status: methodology_ready
evidence_status: operator_evidence_required
story_key: m4-5b-gurobi-benchmark-whitepaper
source_gap: E3
last_updated: 2026-05-27
---

# Gurobi LP Benchmark Methodology

## Purpose

This methodology defines how to compare OptiCloud's committed LP path with a BYO-license Gurobi reference path across the 30 synthetic LP fixtures in `tools/gurobi_benchmark/lp_fixture_suite.json`.

It is methodology-ready only. It does not contain verified Gurobi results, customer data, or publication approval.

## Solver identities

- OptiCloud path: the existing solver-orchestrator LP implementation using HiGHS through `highspy`.
- Gurobi reference path: an operator-provided commercial Gurobi installation and license.
- The Gurobi path is not part of committed CI and is not added as a product dependency in this story.

## BYO Gurobi license boundary

The operator supplies and manages any Gurobi license outside the repository. Do not commit license files, token values, license server locations, hostnames, usernames, or raw solver logs.

## Fixture suite

The fixture suite contains 30 synthetic LPs with stable IDs `lp-001` through `lp-030`. Categories cover small bounded LP, resource allocation, blending, transportation-style, scheduling-style, and stress-scale synthetic LPs.

## Environment capture

Evidence should record OS family, CPU class, memory size, whether the run is containerized, solver versions, warm-up count, timed-run count, timeout seconds, and objective tolerance. Do not include machine hostnames or user names.

## Warm-up policy

Run one non-timed warm-up pass before timed measurements. Record timed runs separately for each solver. The committed validator checks evidence shape and redaction only; it does not execute solvers.

## Timeout policy

Use the same timeout for both solver paths. The default policy is 30 seconds per fixture per timed run unless a future evidence manifest states otherwise and passes validation.

## Metric definitions

- Solver status parity: both solvers return the same normalized status for a fixture.
- Objective delta: absolute difference between OptiCloud/HiGHS and Gurobi objectives when both objectives are available.
- Primal feasibility residual: max residual reported by the benchmark runner for the submitted LP constraints.
- Runtime seconds: elapsed timed-run duration for each solver path.
- Timeout/error rate: count of fixtures ending in timeout or error status.
- Unsupported-case notes: explanation for any fixture where one solver path is not comparable.

## Tolerances

The default objective tolerance is `1e-7`. Future evidence must state the tolerance used and report comparable-count separately from fixture count.

## Result schema

Real evidence must use `tools/gurobi_benchmark/evidence_manifest.schema.json` and must be written to `reports/gurobi-benchmark/<run_id>/evidence_manifest.json`.

## Pass/fail interpretation

Passing validation means the evidence is structurally complete and redacted. It does not by itself approve public publication or imply performance superiority.

## Publication gate

Public use requires verified evidence, redaction review, legal/marketing approval, and explicit approval status. Until then, all whitepaper result cells remain `pending_verified_evidence`.
