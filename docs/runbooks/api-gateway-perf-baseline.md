# API Gateway Performance Baseline Runbook

Owner: SRE / NFR-P owner

Status: M3.6d contract ready; real evidence is produced by operator PRs only.

## Purpose

Validate the M3 NFR-P1 API gateway latency baseline with a 30-minute Locust run at 100 concurrent users and archived Locust, Grafana, and Prometheus evidence.

CI validates the contract shape only. It does not prove the real API gateway baseline passed.

## Scope

Measured endpoint classes:

| Endpoint class | Request | Auth | Pass threshold |
|---|---|---|---|
| `algorithms_public` | `GET /v1/algorithms` | none | P95 < 200 ms |
| `auth_api_keys` | `GET /v1/auth/api_keys` | runtime JWT | P95 < 200 ms |
| `business_demo` | `POST /v1/optimizations/demo` | none | P95 < 500 ms |

All endpoint names, paths, auth modes, and thresholds must match `tools/api_gateway_perf/perf_baseline_plan.json`.

## Required Environment

Set these on the operator workstation or CI runner used for the real staging run. Do not commit values.

```bash
export API_GATEWAY_PERF_BASE_URL="<staging-api-gateway-origin>"
export API_GATEWAY_PERF_JWT="<redacted-staging-user-jwt>"
export API_GATEWAY_PERF_ENDPOINT_CLASSES="algorithms_public,auth_api_keys,business_demo"
```

`API_GATEWAY_PERF_JWT` is required only for `auth_api_keys`. It must be a short-lived staging JWT for a non-production test user.

## Run

1. Confirm staging is healthy and points through the API gateway, not directly to backend services.
2. Confirm Prometheus is scraping gateway latency histograms and Grafana can render the gateway dashboard.
3. Start Locust for the committed profile:

```bash
uv run locust \
  -f tools/api_gateway_perf/locustfile.py \
  --headless \
  --host "$API_GATEWAY_PERF_BASE_URL" \
  --users 100 \
  --spawn-rate 10 \
  --run-time 30m \
  --html /tmp/api-gateway-locust-report.html
```

4. Export the Grafana dashboard screenshot for the same time window.
5. Export a Prometheus JSON snapshot containing `histogram_quantile(0.95)` for each endpoint class.
6. Generate `latency-summary.json` from the Locust and Prometheus outputs.

## Evidence Layout

Create a new run directory:

```text
reports/api-gateway-perf/<run_id>/
  evidence_manifest.json
  locust-report.html
  gateway-grafana.png
  prometheus-snapshot.json
  latency-summary.json
```

The manifest must set `example_only=false`, use `environment=staging-api-gateway`, and include the canonical `plan_sha256` for `tools/api_gateway_perf/perf_baseline_plan.json`.

Validate before opening the operator evidence PR:

```bash
uv run python scripts/validate_api_gateway_perf_plan.py \
  --evidence reports/api-gateway-perf/<run_id>/evidence_manifest.json
```

## Pass / Fail

Pass only if all conditions are true:

- Duration is at least 1800 seconds.
- HTTP error rate is <= 1% for every endpoint class.
- `algorithms_public` Locust P95 and Prometheus P95 are both < 200 ms.
- `auth_api_keys` Locust P95 and Prometheus P95 are both < 200 ms.
- `business_demo` Locust P95 and Prometheus P95 are both < 500 ms.
- Artifacts are redacted and stored under `reports/api-gateway-perf/<run_id>/`.

If any condition fails, create or update a performance investigation issue before retrying. Include endpoint class, failed threshold, artifact links, suspected cause, rollback or mitigation notes, and owner.

## Redaction

Before committing artifacts:

- Remove hostnames that expose private infrastructure.
- Remove JWTs, API keys, cookies, user IDs, tenant IDs, headers, and request bodies.
- Keep only aggregate latency, count, and error-rate data.
- Do not include real customer payloads or solver results.

## Notes

M3.6d is internal SRE/NFR evidence. It does not change customer-facing SLA language and does not mark M3.6a, M3.6b, or M3.6c Chat evidence as passed.
