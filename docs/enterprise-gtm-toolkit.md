---
owner: Marketing / Sales / Customer Success + Founder
status: internal_ready
claim_status: source_supported
evidence_status: hypothesis
story: M4.5 GTM Toolkit Implementation
last_updated: 2026-05-26
---

# Enterprise GTM Toolkit

## Purpose

This is the live entry point for M4.5 GTM assets. The toolkit supports buyer conversations before M5 commercial readiness while keeping legal, SLA, certification, benchmark, logo, and customer-proof claims explicit and review-gated.

## Asset Index

| Asset | Status | Purpose |
|---|---|---|
| [`tools/gtm_toolkit/gtm_toolkit_manifest.json`](../tools/gtm_toolkit/gtm_toolkit_manifest.json) | internal_ready | Canonical GTM asset manifest and validation source |
| [`docs/gtm/pricing-page-optimization.md`](gtm/pricing-page-optimization.md) | internal_ready | Pricing hypotheses and route binding |
| [`docs/gtm/customer-stories/logistics-dispatch-spotlight.md`](gtm/customer-stories/logistics-dispatch-spotlight.md) | draft | Logistics customer story draft |
| [`docs/gtm/customer-stories/energy-forecasting-spotlight.md`](gtm/customer-stories/energy-forecasting-spotlight.md) | draft | Energy forecasting customer story draft |
| [`docs/customer-faqs/commercial-buyer-faq.md`](customer-faqs/commercial-buyer-faq.md) | internal_ready | Buyer FAQ for pricing, security, support, and commercial packaging |
| [`docs/customer-faqs/technical-evaluator-faq.md`](customer-faqs/technical-evaluator-faq.md) | internal_ready | Technical evaluator FAQ |
| [`docs/gtm/po-checklist.md`](gtm/po-checklist.md) | legal_review_required | Purchase-order checklist |
| [`docs/gtm/sow-template.md`](gtm/sow-template.md) | legal_review_required | Pilot SOW template |
| [`docs/gtm/msa-checklist.md`](gtm/msa-checklist.md) | legal_review_required | Master agreement review checklist |
| [`docs/gtm/sales-one-pager.md`](gtm/sales-one-pager.md) | internal_ready | Buyer-safe one-pager |
| [`docs/gtm/customer-success-onboarding.md`](gtm/customer-success-onboarding.md) | internal_ready | Founder-led onboarding workflow |
| [`docs/gtm/lighthouse-customer-slo.md`](gtm/lighthouse-customer-slo.md) | internal_ready | Monthly lighthouse recruitment process SLO |

## Controlled Status Values

- `draft`: content exists but is not externally publishable.
- `internal_ready`: usable for internal GTM preparation.
- `legal_review_required`: legal or finance approval required before external use.
- `evidence_required`: claim requires future operator/customer evidence.
- `published`: externally publishable and backed by evidence/approval.

## Boundaries

- This toolkit does not create legal terms. Legal ownership remains in [`docs/legal-templates.md`](legal-templates.md).
- This toolkit does not claim SOC 2, ISO 27001, AIGC filing approval, production SLA, approved public customer references, or production customer case studies.
- Gurobi comparison content is limited to buyer questions and evaluation planning. The 30 LP benchmark whitepaper is Story `m4-5b-gurobi-benchmark-whitepaper` and remains out of scope.
- Do not commit CRM exports, contact lists, interview transcripts, screenshots, private prospect lists, signed contracts, or binary sales decks.

## Validation

Run:

```bash
uv run python scripts/validate_gtm_toolkit.py
uv run pytest tests/test_gtm_toolkit.py -q
```

The CI job `gtm-toolkit-validation` runs the same focused checks when GTM, FAQ, manifest, pricing, or validator files change.
