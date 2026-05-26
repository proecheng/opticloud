---
status: draft
claim_status: hypothesis
evidence_status: operator_evidence_required
consent_status: consent_required
owner: Marketing / Founder
---

# Logistics Dispatch Spotlight Draft

## Metadata

- Persona: logistics operations lead
- Industry: logistics
- Asset type: early customer story draft
- Publishability: internal draft until interview consent and operator evidence exist
- Follow-up owner: founder-led sales
- Source references: `docs/industry-use-cases.md`, `_bmad-output/planning/epics.md:2062`

## Customer Context

Mid-market city logistics teams often schedule vehicle routing and dispatch exceptions in spreadsheets. The buyer problem is not a lack of dispatch intuition; it is that the experienced dispatcher becomes a throughput bottleneck when order volume spikes.

## Baseline Pain

- Manual route planning takes hours when order count and time windows increase.
- Late deliveries and empty mileage create measurable cost pressure.
- Dispatch knowledge is concentrated in one or two senior operators.

## OptiCloud Intervention

OptiCloud positions the first workflow as a structured VRPTW optimization request, followed by reviewable JSON output, route alternatives, and plain-language reasoning. The draft should present the workflow as an evaluation path, not as validated customer proof.

## Expected Outcome

- Shorter planning cycle for daily dispatch scenarios.
- Clearer comparison between manual plans and API-generated route candidates.
- Early signal on whether per-task Credits pricing is understandable for logistics buyers.

## Pricing / ROI Assumptions

- Assumption: logistics buyers evaluate value by saved dispatcher time, reduced late penalties, and reduced empty mileage.
- Assumption: daily batch optimization is easier to price than per-order calls.
- Source-supported: PRD and industry-use-case materials frame logistics as a primary GTM segment.

## Assumptions

- No production deployment is claimed.
- Savings estimates must stay in draft status until interview evidence and customer consent are available.
- The story does not use a real customer name, logo, phone number, or private contract value.

## Source-Supported Facts

- OptiCloud already exposes optimization workflows and public onboarding surfaces in the repository.
- Existing planning docs identify logistics as a key early buyer segment.
- Reproducibility and transparent solver metadata are established trust themes in prior implementation stories.

## Observed Evidence

No observed customer evidence is committed in this story. Future evidence must be redacted and validated under a separate evidence workflow.

## Follow-Up

- Recruit one logistics lighthouse candidate.
- Run an interview within one week after qualification.
- Draft a publishable story within two weeks after interview if consent exists.
