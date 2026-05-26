# Chat Incident Fallback Drill Runbook

## Purpose

M3.6c defines the internal SRE drill for a simulated DeepSeek incident and manual Qwen-Max fallback. CI validates the plan and evidence structure only. A real pass requires an operator-run drill with redacted evidence under `reports/chat-incident-fallback/<run_id>/`.

This drill does not change customer-facing v1 SLO language. Qwen-Max remains an incident fallback path, not the normal Chat SLO path.

## Preconditions

- Staging Chat endpoint is reachable from the drill runner.
- Provider Health surface can show DeepSeek failure and Qwen-Max fallback state.
- Operator has permission to trigger the manual emergency fallback control.
- Prompt fixture is `tools/chat_load/prompts_v1.json`.
- Drill plan is `tools/chat_load/incident_fallback_plan.json`.
- Locust is installed in the operator environment.

Required environment variables:

```bash
CHAT_LOAD_ENDPOINT=/v1/chat/stream
CHAT_LOAD_BASE_URL=https://staging.example.invalid
CHAT_INCIDENT_PROVIDER=deepseek-v3.5
CHAT_FALLBACK_PROVIDER=qwen-max
CHAT_INCIDENT_RUN_ID=<run_id>
```

Do not commit real provider keys, bearer tokens, cookies, credentialed URLs, tenant IDs, provider payloads, or raw customer prompts.

## Drill Steps

1. Start the simulated DeepSeek incident through the staging fault-injection control.
2. Record `incident_started_utc`.
3. Observe Provider Health until DeepSeek is marked failed.
4. Record `provider_health_failed_utc`.
5. Use the internal SRE control to manually switch Chat routing to Qwen-Max.
6. Record `operator_decision_utc`.
7. Send a small post-switch probe to confirm Qwen-Max routing.
8. Record `fallback_confirmed_utc`.
9. Start the post-switch measurement window and run Locust against the Chat endpoint.

Example measurement command:

```bash
locust \
  -f tools/chat_load/locustfile.py \
  --host "$CHAT_LOAD_BASE_URL" \
  --users 20 \
  --spawn-rate 5 \
  --run-time 600s \
  --headless \
  --html reports/chat-incident-fallback/<run_id>/incident-fallback-locust.html
```

## Evidence Archive

Archive under `reports/chat-incident-fallback/<run_id>/` in a future operator evidence PR:

- `incident-fallback-locust.html`
- `provider-health-snapshot.json`
- `fallback-decision-log.json`
- `operator-timeline.json`
- `latency-snapshot.json`
- `evidence_manifest.json`

Before committing artifacts, redact provider request/response payloads, internal hostnames with credentials, cookies, bearer tokens, share tokens, tenant identifiers, and raw user data.

Validate real evidence explicitly:

```bash
uv run python scripts/validate_chat_load_plan.py \
  --incident-fallback-evidence reports/chat-incident-fallback/<run_id>/evidence_manifest.json
```

## Pass Criteria

- `switch_duration_seconds <= 300`.
- `fallback_first_token_p95_ms < 5000`.
- `fallback_route_ratio = 1.0` in the post-switch measurement window.
- `schema_parity_pass_count = schema_parity_total_count`, with at least one schema parity sample.
- `fallback_provider_error_count = 0`.

`switch_duration_seconds` is measured from `operator_decision_utc` to `fallback_confirmed_utc`. Provider-health detection time is recorded separately as `detection_window_seconds`.

## Rollback

After the drill:

1. Switch routing back to DeepSeek after the simulated incident is cleared.
2. Confirm Provider Health shows DeepSeek healthy and active.
3. Run a small probe against the Chat endpoint.
4. Record rollback evidence in the operator timeline.

If Qwen-Max fallback fails, keep Chat in the safest available degraded mode, page SRE, open an incident, and file follow-up work for provider health detection, manual switch controls, schema parity, and provider capacity.
