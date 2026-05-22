# Citation Tracker Runbook

Story 6.A.3 ships citation tracking as a pure Python module plus CLI. Production
scheduling can wrap this command with a CronJob, systemd timer, or Dramatiq task.

## Local Dry Run

Run without network by importing a Google Scholar-derived CSV or JSON file:

```bash
uv run python -m solver_orchestrator.citation_tracker_cli \
  --state .cache/citation-tracking/state.json \
  --out _bmad-output/reports/citation-tracking/latest.json \
  --markdown _bmad-output/reports/citation-tracking/latest.md \
  --google-scholar-import data/google-scholar-weekly.csv
```

## Weekly Run

Enable Semantic Scholar explicitly and pass one or more import files:

```bash
uv run python -m solver_orchestrator.citation_tracker_cli \
  --state .cache/citation-tracking/state.json \
  --out _bmad-output/reports/citation-tracking/latest.json \
  --markdown _bmad-output/reports/citation-tracking/latest.md \
  --semantic-scholar \
  --google-scholar-import data/google-scholar-weekly.csv
```

Semantic Scholar uses `SEMANTIC_SCHOLAR_API_KEY` when configured. Request an API
key through the official Semantic Scholar API process and provide it only via the
environment. The tracker also reads `SEMANTIC_SCHOLAR_MIN_INTERVAL_SECONDS` and
`SEMANTIC_SCHOLAR_TIMEOUT_SECONDS`.

## Google Scholar Import-Only Rule

The v1 Google Scholar path is CSV/JSON import only. Do not add direct Google
Scholar HTML scraping. Use Google Scholar alerts, manual exports, or approved
third-party exports, then pass those files with `--google-scholar-import`.

## Linear Creation

By default the tracker emits deterministic Linear-ready payloads in the JSON and
Markdown reports. To create issues, set both env vars and pass `--create-linear`:

```bash
$env:LINEAR_API_KEY = "..."
$env:LINEAR_TEAM_KEY = "..."
uv run python -m solver_orchestrator.citation_tracker_cli --create-linear
```

Secrets must stay in environment variables only. Never put API keys in CLI
flags, reports, Markdown files, logs, or screenshots.

## Future CronJob Wiring

A future Kubernetes CronJob can mount the state path on persistent storage,
mount the weekly import file, and run the same CLI. Keep report artifacts as CI
artifacts or object storage outputs; do not commit generated reports unless a
human explicitly chooses to archive one.

## Exit Codes

- `0`: report generated and optional Linear calls succeeded.
- `1`: report generated, but a source failed or malformed imports were found.
- `2`: invalid configuration or Linear creation failed.
