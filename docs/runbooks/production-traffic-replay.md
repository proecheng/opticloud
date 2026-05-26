# Production Traffic Replay Runbook

Owner: SRE / NFR-P owner

Status: M3.6e contract ready; real sanitized replay evidence is produced by operator PRs only.

## Purpose

M3.6e defines the infrastructure contract for replaying sanitized production traffic shapes against staging. It strengthens G6/M3 performance and contract confidence, but CI validates structure only. CI does not prove that a real production traffic replay passed.

M3.6e replay evidence informs G6/M3 tuning. It does not replace M3.6a Chat staging hard-gate evidence or M3.6d API gateway baseline evidence.

## Scope

Replay lanes must match `tools/traffic_replay/replay_plan.json`:

| Lane | Source shape | Target service class | Threshold family |
|---|---|---|---|
| `api_gateway_public` | Sanitized public API requests | `api-gateway` | `M3.6d` |
| `chat_streaming` | Sanitized Chat streaming request shapes | `chat-service` | `M3.6a` |
| `contract_fuzz` | Schemathesis-compatible contract seed cases | `contract-tests` | `M3.2` |

The replay mode is `sanitized_contract_replay`. Do not mirror live production traffic, export raw customer data, or replay against production.

## Required Environment

Set these only on the operator workstation or controlled runner used for the real staging replay. Do not commit values.

```bash
export TRAFFIC_REPLAY_EXPORT_SOURCE="<redacted-production-log-export-source>"
export TRAFFIC_REPLAY_REDACTION_PROFILE="<approved-redaction-profile>"
export TRAFFIC_REPLAY_RUN_ID="<run-id>"
export TRAFFIC_REPLAY_STAGING_BASE_URL="<staging-origin>"
export TRAFFIC_REPLAY_OPERATOR="<operator-id>"
```

If the replay harness needs credentials, use short-lived staging credentials only. Never commit bearer tokens, cookies, API keys, JWTs, production URLs, customer prompts, tenant IDs, user IDs, emails, phone numbers, IP addresses, request bodies, or response bodies.

## Operator Flow

1. Export production log records into a secure temporary location approved for redaction work.
2. Apply deterministic sampling with the committed strategy: `deterministic_hash_bucket`.
3. Redact before any file enters the repository. Keep only path templates, query/body/header shape metadata, expected status families, lane labels, and weights.
4. Write the capture fixture:

```text
reports/prod-traffic-replay/<run_id>/capture_fixture.json
```

5. Validate the fixture before replay:

```bash
uv run python scripts/validate_traffic_replay_plan.py \
  --capture-fixture reports/prod-traffic-replay/<run_id>/capture_fixture.json
```

6. Run the replay against staging only. Keep generated artifacts under:

```text
reports/prod-traffic-replay/<run_id>/
  capture_fixture.json
  evidence_manifest.json
  replay-report.html
  redaction-audit.json
  contract-seed-report.json
  latency-summary.json
```

7. Review `redaction-audit.json` before committing artifacts. A human operator must confirm there are zero redaction violations.
8. Generate `evidence_manifest.json` with `example_only=false`, `environment=staging-traffic-replay`, matching `capture_id`, matching `redaction_profile`, the canonical plan SHA-256, and the canonical capture fixture SHA-256.
9. Validate the evidence. When `--evidence` is supplied, the validator binds it to the matching sibling `capture_fixture.json`.

```bash
uv run python scripts/validate_traffic_replay_plan.py \
  --evidence reports/prod-traffic-replay/<run_id>/evidence_manifest.json
```

10. Open an operator evidence PR containing only sanitized fixture/evidence artifacts and the manifest. State that the PR is replay evidence, not a G6 hard-gate pass.

## Pass / Fail

Real evidence is acceptable only when all conditions are true:

- `duration_seconds > 0`.
- Every lane has `request_count > 0`.
- `success_count <= request_count` for every lane.
- `redaction_violation_count == 0` for every lane.
- `replay_drift_rate <= 0.02` for every lane.
- `http_error_rate <= 0.01` for `api_gateway_public` and `contract_fuzz`.
- `http_error_rate <= 0.02` for `chat_streaming`.
- Artifact paths are repository-relative and under `reports/prod-traffic-replay/<run_id>/`.
- No manifest claims `g6_hard_gate_pass`, `api_gateway_perf_pass`, `chat_load_pass`, `hard_gate_pass`, or `staging_pass`.

## Failure Handling

If redaction audit finds any violation, stop immediately, delete generated artifacts from the working tree, rotate any exposed credential if applicable, and open a security/privacy follow-up before retrying.

If replay drift, latency, or HTTP error thresholds fail, do not mark the replay as passed. Open a performance or contract investigation with the failed lane, failed threshold, run ID, sanitized artifact references, suspected cause, and proposed owner before retrying.

If the validator fails, fix the fixture/evidence contract issue first. Do not bypass validation by moving files to another reports directory.

## CI Behavior

CI runs `scripts/validate_traffic_replay_plan.py` and `tests/test_traffic_replay_plan.py` for traffic replay path changes. It also validates real capture fixtures and replay evidence manifests only when they are present under `reports/prod-traffic-replay/**`.

CI must not require production logs, staging services, Kubernetes, Grafana, Prometheus, Locust, Schemathesis live network runs, cloud credentials, JWTs, API keys, or database access.
