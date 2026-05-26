---
status: internal_ready
claim_status: source_supported
evidence_status: hypothesis
owner: Marketing / Product
---

# Pricing Page Optimization Plan

## Scope

This asset binds M4.5 pricing copy to the existing `/pricing` route. It defines buyer-safe hypotheses and measurement plans only. Runtime billing enforcement remains in billing stories.

## Canonical Plans

| Plan | Source status | Buyer framing |
|---|---|---|
| Free | current_runtime | Signup and trial exploration; exact Credits grants follow current product behavior. |
| Starter | commercial_hypothesis | First paid package for repeat lightweight optimization and forecasting. |
| Pro | commercial_hypothesis | Individual professional plan for higher monthly usage and academic trial conversion. |
| Team | commercial_hypothesis | Shared team buying motion with support and invoice readiness. |
| Enterprise | commercial_hypothesis | Procurement-led evaluation, legal review, and custom operating requirements. |

## Target Segments

- Logistics operations teams validating route optimization.
- Energy or manufacturing teams validating forecasting and scheduling workflows.
- Academic teams converting from free education usage to collaboration or Pro usage.
- Enterprise technical evaluators who need security and data-retention answers before pilot approval.

## Hypotheses

- Free-to-Starter conversion improves when the page explains Credits in task terms instead of only account terms.
- Team buyers need procurement readiness signals before they ask for a pilot.
- Enterprise buyers should see "custom review required" rather than unsupported production SLA promises.

## Event Taxonomy

These are proposed event names for future analytics. M4.5 does not add analytics code.

| Event | Intent |
|---|---|
| pricing_plan_view | User saw plan cards. |
| pricing_signup_click | User clicked signup from pricing. |
| pricing_docs_click | User opened quickstart/docs from pricing. |
| pricing_enterprise_question | User showed intent to evaluate Enterprise. |

## A/B Candidates

- Credits-first copy vs plan-first copy.
- Logistics example vs forecasting example in the supporting text.
- Signup primary CTA vs quickstart primary CTA.

## Guardrails

- Keep buyer-safe caveat visible: commercial packaging is under legal and billing review.
- Do not claim SOC 2, ISO 27001, AIGC approval, customer logos, or production SLA.
- Do not add analytics scripts, cookies, CRM forms, or external embeds in this story.
- Do not present API task prices as runtime-enforced unless billing code supports them.

## Rollback Criteria

- Pricing page typecheck fails.
- Validator detects missing plan labels or missing buyer-safe caveat.
- Copy creates a legal, SLA, certification, logo, or benchmark claim without evidence.

## Route Binding

- Route: `apps/web/src/app/pricing/page.tsx`
- Messages: `apps/web/src/i18n/messages/zh-CN.json`, `apps/web/src/i18n/messages/en-US.json`
- Current status: static public route, no auth, no billing API, no analytics.
