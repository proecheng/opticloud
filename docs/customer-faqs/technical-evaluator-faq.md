---
status: internal_ready
claim_status: source_supported
evidence_status: source_supported
owner: Customer Success / Engineering
---

# Technical Evaluator FAQ

## What should technical evaluators test first?

Start with a small optimization or forecasting workflow that already has historical expected output. Compare output structure, reproducibility metadata, error handling, and operational fit.

## How is security handled?

Technical controls are documented across runbooks and service stories. This FAQ does not claim external certification. Security buyers should treat certification status as pending until a future evidence artifact exists.

## What data retention should we assume?

Do not assume one retention rule for every data class. Reproducibility voucher assets, image archival evidence, audit records, billing records, and uploaded inputs have different retention obligations.

## How are Credits and billing validated?

Billing behavior is implemented in billing-service stories. M4.5 pricing assets explain buyer packaging and commercial hypotheses; they do not change runtime billing code.

## What is the refund or failed-run boundary?

Refund and failed-run behavior must be verified against billing APIs and legal terms. GTM copy should avoid promising automatic compensation beyond implemented behavior.

## How does reproducibility work?

Reproducibility is tied to voucher and archival workflows. Technical evaluators can ask for evidence references and runbook links, but M4.5 does not change rerun behavior.

## How should we evaluate Gurobi migration?

Use a dual-run evaluation plan with customer-provided historical instances and pre-agreed metrics. This FAQ does not include comparative result tables or superiority claims.

## What is the support path for pilots?

Pilot support is founder-led and Customer Success tracked. Enterprise support levels require legal and commercial approval before they become commitments.
