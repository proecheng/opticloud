# NFR-COST Red-Line Alerts Runbook

## Purpose

Story 9.3 turns the NFR-COST red lines into an auditable governance loop. The static CI gate proves the contract, evidence shape, current cost telemetry drift checks, DingTalk-ready payloads, Linear-ready payloads, and redaction rules. It does not prove that a real Prometheus alert fired, a DingTalk message was delivered, or a Linear issue was created.

Static validation:

```bash
uv run python scripts/validate_nfr_cost_alerts.py
uv run pytest tests/test_nfr_cost_alerts.py -v
```

Real evidence validation, when a redacted operator manifest exists:

```bash
uv run python scripts/validate_nfr_cost_alerts.py \
  --evidence reports/nfr-cost-alerts/<run_id>/alert_manifest.json
```

## Red Lines

| Redline | Threshold | Owner | Severity |
| --- | --- | --- | --- |
| LLM cost / revenue | `>= 0.30` | NFR-COST | P1 |
| GPU idle rate | `>= 0.50` | SRE | P2 |
| Provider share / revenue | `>= 0.50` | Provider | P1 |
| Refund / issued credits | `>= 0.05` | Billing | P1 |
| Cash runway months | `< 6` | Finance | P0 |

## Operator Flow

1. Pick cadence:
   - `quarterly` for standard governance review.
   - `breach_drill` for a simulated breach or incident exercise.
2. Confirm the contract still matches the committed cost telemetry substrate: `cost_attribution`, shared `CostUnit`, solver hook, billing hook, and Story 9.2 handoff.
3. For every redline, capture source snapshots for each required signal.
4. Evaluate each Prometheus alert expression or breach-drill equivalent.
5. Generate DingTalk-ready payloads. Do not send from this repo or commit webhook material.
6. Generate Linear-ready ticket payloads. Do not commit external issue IDs from static examples.
7. Record routing outcomes and owner acknowledgement state.
8. Save only public-safe evidence in `reports/nfr-cost-alerts/<run_id>/alert_manifest.json`.
9. Validate the evidence manifest before opening the evidence PR.

## Prometheus And Alertmanager Capture

For real evidence, export redacted Prometheus or Alertmanager snapshots per redline:

- source metric availability
- alert expression result
- alert labels and annotations after removing customer-identifying labels
- alert firing or breach-drill status
- timestamp window and run id

Do not commit raw Prometheus labels, raw Alertmanager payloads, production hostnames, credentialed URLs, tenant identifiers, user identifiers, customer identifiers, or finance exports.

## DingTalk-Ready Handoff

The manifest stores a deterministic DingTalk-ready markdown payload per redline. It must include:

- redline id
- severity
- markdown title and text
- summary
- `docs/runbooks/nfr-cost-alerts.md`
- evidence pointer

Do not commit DingTalk webhook URLs, signing secrets, access tokens, bot tokens, or delivery receipts that expose private channel data.

## Linear-Ready Handoff

The manifest stores a deterministic Linear-ready ticket payload per redline. It must include:

- title and description
- `team_key=NFR-COST`
- labels `nfr-cost`, `redline`, and `governance`
- severity and owner
- due date
- evidence pointer

Static examples keep `external_issue_id=null`. Real external Linear creation belongs to a future relayer story unless the operator separately validates and redacts the integration evidence.

## Evidence Rules

Do not commit tenant IDs, user IDs, customer IDs, account IDs, emails, phone numbers, API keys, bearer tokens, cookies, passwords, webhook tokens, Linear tokens, DingTalk secrets, credentialed URLs, production hostnames, absolute local paths, raw logs, raw Prometheus labels, raw metric labels, raw finance exports, prompts, provider payloads, or customer-identifying dimensions.

Allowed evidence is limited to:

- `alert_manifest.json`
- redacted source snapshot JSON files
- redacted alert evaluation JSON files
- public-safe DingTalk-ready and Linear-ready payloads
- public-safe finding summaries
- ticket references with owner, severity, due date, and status

## Ticket Policy

Every breached redline, failed alert evaluation, failed DingTalk-ready payload, failed Linear-ready payload, failed routing outcome, or missing required input signal must reference at least one ticket. A valid ticket reference includes:

- ticket ID
- owner
- severity
- due date
- status

P0/P1/P2 NFR-COST findings are stop-ship until resolved. The manifest must not mark release approval while unresolved P0/P1/P2 findings remain open, in progress, or deferred.

## Rollback

If the CI gate or evidence validator fails:

1. Stop release approval for the affected change.
2. Fix the contract, cost telemetry drift, manifest, redaction issue, or missing ticket reference.
3. Rerun `uv run python scripts/validate_nfr_cost_alerts.py`.
4. Rerun `uv run pytest tests/test_nfr_cost_alerts.py -v`.
5. Keep the evidence PR open until stop-ship findings are resolved or explicitly marked as non-release-blocking by the governance owner in a later story.

## Boundaries

- This runbook does not deploy Prometheus alert rules or Alertmanager routes.
- This runbook does not call DingTalk, Linear, Grafana, cloud APIs, or production networks in CI.
- This runbook does not add live finance aggregation, GPU telemetry, provider payout aggregation, or runway computation.
- This runbook does not change cost attribution, billing, solver, provider payout, or customer-facing billing behavior.
- The unified governance dashboard belongs to Story 9.7.
