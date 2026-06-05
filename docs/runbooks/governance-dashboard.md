# Governance Dashboard Runbook

Story 9.7 owns the Grafana-ready cross-cutting governance dashboard contract. It does not publish a real Grafana dashboard, connect a datasource, create external tickets, or approve a production release by itself.

## Local Commands

```powershell
uv run python scripts/validate_governance_dashboard.py
uv run pytest tests/test_governance_dashboard.py -q
git diff --check
```

Validate committed real evidence only when a redacted quarterly manifest exists:

```powershell
uv run python scripts/validate_governance_dashboard.py --evidence reports/governance-dashboard/<run_id>/dashboard_manifest.json
```

## Quarterly Flow

1. Run the upstream validators for Stories 9.1-9.6.
2. Collect only redacted source snapshots from the upstream evidence manifests.
3. Populate `reports/governance-dashboard/<run_id>/dashboard_manifest.json`.
4. Review the Grafana-ready panel catalog with PM, Security, UX, SRE, and Compliance.
5. Record role review outcomes and findings.
6. Block release approval on unresolved P0/P1/P2 findings.

## Source Contracts

- 9.1 a11y: `tools/a11y_audit/quarterly_a11y_contract.json`
- 9.2 observability: `tools/prometheus_metric_audit/business_metric_audit_contract.json`
- 9.3 cost: `tools/nfr_cost_alerts/nfr_cost_alert_contract.json`
- 9.4 security: `tools/nfr_security_p0_drills/nfr_security_p0_drill_contract.json`
- 9.5 WCAG readiness: `tools/wcag_2_2_upgrade/wcag_2_2_upgrade_contract.json`
- 9.6 error i18n: `tools/error_i18n_audit/error_i18n_audit_contract.json`

## Grafana-Ready Handoff

The contract records panel ids, viewer roles, data-source mode, and transform text so a later Grafana provisioning task can convert it to dashboard JSON. Until that task exists, use `contract_static`, `evidence_manifest`, or `manual_review` only. Do not use production-live, Grafana API, or external network modes.

## Redaction

Do not commit tenant/user/customer ids, emails, phone numbers, API keys, bearer tokens, cookies, passwords, secrets, Grafana tokens, Prometheus datasource credentials, dashboard share tokens, credentialed URLs, production hostnames, absolute local paths, raw logs, raw screenshots with embedded secrets, prompt/provider payloads, raw metric labels, or raw customer-identifying dimensions.

## Ticket Policy

Every missing, stale, failed, red, or yellow dashboard item must reference a finding. Every required finding must include ticket refs with owner, severity, due date, and status.

## Stop-Ship Rules

Unresolved P0/P1/P2 findings force the dashboard rollup to red and block release approval. Stale required source evidence forces at least yellow. Missing required source evidence forces red.

## Rollback

If dashboard evidence is unsafe or incorrect, remove the unsafe `reports/governance-dashboard/<run_id>/` directory from the change, rerun the validator, and keep the static contract as the source of truth. Revert only the dashboard evidence or dashboard-governance files involved in the failed release.

## Handoff

Story 9.8 owns graded protection evidence. This dashboard keeps Story 9.8 slots visible but does not complete graded-protection evidence.
