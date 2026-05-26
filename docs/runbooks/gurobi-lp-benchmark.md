---
owner: Solver Owner
status: internal_ready
claim_status: methodology_ready
evidence_status: operator_evidence_required
story_key: m4-5b-gurobi-benchmark-whitepaper
source_gap: E3
last_updated: 2026-05-27
---

# Gurobi LP Benchmark Runbook

## Scope

This runbook describes an offline operator procedure for producing redacted M4.5b benchmark evidence. It does not create a production API, hosted solver workflow, background job, scheduler, container image, or Gurobi integration.

## Inputs

- `tools/gurobi_benchmark/lp_fixture_suite.json`
- Operator-managed OptiCloud/HiGHS run environment
- Operator-managed Gurobi environment with BYO commercial license

## Output Path

Write redacted evidence to:

```text
reports/gurobi-benchmark/<run_id>/evidence_manifest.json
```

Supporting artifact paths must stay under the same `reports/gurobi-benchmark/<run_id>/` directory.

## Operator Steps

1. Create a run id such as `gurobi-benchmark-YYYYMMDD-operator`.
2. Run one warm-up pass for each solver path.
3. Run the 30 fixtures with the same timeout and tolerance policy for each solver path.
4. Normalize statuses and calculate objective deltas and feasibility residuals.
5. Write aggregate metrics derived from per-fixture results.
6. Redact environment details and artifact references.
7. Run `uv run python scripts/validate_gurobi_benchmark.py --evidence reports/gurobi-benchmark/<run_id>/evidence_manifest.json`.
8. Move approval status only after redaction, solver-owner review, and legal/marketing review.

## Do not commit

Do not commit license files, token values, license server locations, hostnames, usernames, private customer models, contact data, raw solver logs with secrets, screenshots, unredacted environment dumps, CRM exports, or customer datasets.

## Redaction Checklist

- `redaction_reviewed=true` only after manual review.
- Artifact paths are relative, not URLs.
- Artifact paths do not traverse directories.
- No secret-like keys or values are present.
- No publication claim is made from an operator draft.

## Validation

```bash
uv run python scripts/validate_gurobi_benchmark.py
uv run pytest tests/test_gurobi_benchmark.py -q
```
