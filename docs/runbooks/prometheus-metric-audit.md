# Prometheus Business Metric Audit Runbook

## Purpose

Story 9.2 turns NFR-O1 business metrics into an auditable governance loop. The static CI gate proves the contract, evidence shape, repo-state drift checks, and redaction rules; it does not prove that a real Prometheus scrape or Grafana review has already happened.

Static validation:

```bash
uv run python scripts/validate_prometheus_metric_audit.py
uv run pytest tests/test_prometheus_metric_audit.py -v
```

Real evidence validation, when a redacted operator manifest exists:

```bash
uv run python scripts/validate_prometheus_metric_audit.py \
  --evidence reports/prometheus-metric-audit/<run_id>/audit_manifest.json
```

## Operator Flow

1. Pick cadence:
   - `quarterly` for standard tier.
   - `annual_lite` for lite tier.
2. Confirm the contract still matches committed `/metrics` endpoints and Prometheus metric declarations.
3. For every NFR-O1 metric id, classify coverage as `covered`, `missing_with_ticket`, `planned`, or `not_applicable`.
4. Export redacted Prometheus query snapshots for every metric id.
5. Review the Grafana dashboard panels for every metric id and capture redacted screenshots.
6. Record only public-safe metadata in `reports/prometheus-metric-audit/<run_id>/audit_manifest.json`.
7. Validate the evidence manifest before opening the evidence PR.

## Evidence Rules

Do not commit tenant IDs, user IDs, customer IDs, account IDs, emails, phone numbers, API keys, bearer tokens, cookies, passwords, dashboard share tokens, credentialed URLs, production hostnames, absolute local paths, raw logs, raw metric labels, prompts, provider payloads, or unredacted Grafana/Prometheus exports.

Allowed evidence is limited to:

- `audit_manifest.json`
- redacted PromQL snapshot JSON files
- redacted Grafana screenshots
- public-safe finding summaries
- ticket references with owner, severity, due date, and status

## Ticket Policy

Every `missing_with_ticket` metric and every failed PromQL or Grafana check must reference at least one ticket. A valid ticket reference includes:

- ticket ID
- owner
- severity
- due date
- status

P0/P1/P2 NFR-O findings are stop-ship until resolved. The manifest must not mark release approval while unresolved P0/P1/P2 observability findings remain open, in progress, or deferred.

## Rollback

If the CI gate or evidence validator fails:

1. Stop release approval for the affected change.
2. Fix the contract, source drift, manifest, or redaction issue.
3. Rerun `uv run python scripts/validate_prometheus_metric_audit.py`.
4. Rerun `uv run pytest tests/test_prometheus_metric_audit.py -v`.
5. Keep the evidence PR open until missing or failed metrics have ticket references and stop-ship findings are resolved.

## Boundaries

- This runbook does not run Prometheus, Grafana, Loki, Tempo, Kubernetes, staging load tests, or production network calls in CI.
- This runbook does not add live service instrumentation.
- This runbook does not create real tickets automatically.
- Alert automation and DingTalk/Linear routing belong to Story 9.3.
- The unified governance dashboard belongs to Story 9.7.
