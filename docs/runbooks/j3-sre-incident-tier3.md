# J3 SRE Incident Tier 3 Runbook

## Purpose

Story 3.12 defines a static Tier 3 incident contract for the J3 SRE journey:

Alert -> DingTalk page -> Console Provider Health -> manual Qwen-Max fallback -> Status Page `Investigating` -> repair -> 24h public Postmortem.

This runbook produces public-safe payloads and review skeletons only. It is not the Epic 8.A production status page, subscription system, Postmortem CRUD workflow, DingTalk integration, or refund automation.

## Inputs

- Contract: `tools/incidents/j3_sre_incident_contract.json`
- Example manifest: `tools/incidents/j3_sre_incident.example.json`
- Validator: `scripts/validate_j3_incident_contract.py`
- Existing fallback drill runbook: `docs/runbooks/chat-incident-fallback.md`
- Existing M3.6c fallback plan: `tools/chat_load/incident_fallback_plan.json`

## Operator Flow

1. Confirm Provider Health shows DeepSeek degradation.
2. Declare P0 when the incident meets the contract threshold.
3. Record the canonical UTC timeline fields from the contract.
4. Manually trigger the Qwen-Max incident fallback path following `docs/runbooks/chat-incident-fallback.md`.
5. Generate the Status Page `Investigating` payload from the manifest shape.
6. Generate the 24h Postmortem review skeleton.
7. Attach only redacted evidence under `reports/j3-sre-incident/<incident_id>/`.
8. Validate the manifest before submitting an operator evidence PR.

Example validation:

```bash
uv run python scripts/validate_j3_incident_contract.py \
  --evidence reports/j3-sre-incident/<incident_id>/incident_manifest.json
```

## Evidence Archive

Future operator evidence may include:

- `incident_manifest.json`
- `provider-health-snapshot.json`
- `status-page-announcement.json`
- `postmortem-skeleton.json`
- redacted fallback drill evidence references from M3.6c

Do not commit values containing API keys, bearer tokens, cookies, DingTalk webhook tokens, customer prompts, provider request or response payloads, tenant identifiers, internal hostnames, credentialed URLs, or raw production logs.

## Boundaries

- The validator proves static consistency only.
- The runbook does not call DingTalk.
- The runbook does not publish to `status.opticloud.cn`.
- The runbook does not send RSS, email, or Webhook subscriptions.
- The runbook does not execute billing refunds.
- The compensation placeholder is a handoff note for future billing and customer-success review.

## Rollback

After the fallback window:

1. Confirm DeepSeek Provider Health has recovered.
2. Switch traffic back according to the fallback drill rollback steps.
3. Continue monitoring until the status can move from `monitoring` to `resolved`.
4. Keep the incident record open until Postmortem review is complete.

## Postmortem Review

Postmortem review must verify:

- timeline fields match the manifest
- Status Page announcement used public-safe wording
- root cause is either confirmed or clearly marked as pending
- follow-up action items have owners
- compensation placeholder is not represented as completed refund evidence
