# Chat Staging Load Test Runbook

## Purpose

M3.6a provides the repeatable harness for G6 Chat latency validation. CI validates the plan and evidence structure only. Real pass/fail evidence must come from an operator-run test against the 5-node staging cluster.

## Preconditions

- 5-node K8s staging cluster is deployed and healthy.
- Chat SSE endpoint is reachable from the load-test runner.
- Grafana dashboard for Chat/API/cluster metrics is available.
- Locust is installed in the operator environment.
- Prompt fixture is `tools/chat_load/prompts_v1.json`.
- Profile config is `tools/chat_load/staging_profiles.json`.

Required environment variables:

```bash
CHAT_LOAD_PROFILE=baseline
CHAT_LOAD_ENDPOINT=/v1/chat/stream
CHAT_LOAD_BASE_URL=https://staging.example.invalid
```

Do not commit real URLs, cookies, bearer tokens, API keys, provider payloads, tenant IDs, or raw user prompts.

## Run Profiles

Baseline:

```bash
CHAT_LOAD_PROFILE=baseline locust \
  -f tools/chat_load/locustfile.py \
  --host "$CHAT_LOAD_BASE_URL" \
  --users 100 \
  --spawn-rate 10 \
  --run-time 600s \
  --headless \
  --html reports/chat-load/<run_id>/baseline-locust.html
```

Stress:

```bash
CHAT_LOAD_PROFILE=stress locust \
  -f tools/chat_load/locustfile.py \
  --host "$CHAT_LOAD_BASE_URL" \
  --users 100 \
  --spawn-rate 10 \
  --run-time 1800s \
  --headless \
  --html reports/chat-load/<run_id>/stress-locust.html
```

Soak:

```bash
CHAT_LOAD_PROFILE=soak locust \
  -f tools/chat_load/locustfile.py \
  --host "$CHAT_LOAD_BASE_URL" \
  --users 100 \
  --spawn-rate 5 \
  --run-time 43200s \
  --headless \
  --html reports/chat-load/<run_id>/soak-locust.html
```

## Evidence Archive

Archive under `reports/chat-load/<run_id>/`:

- `baseline-locust.html`
- `baseline-grafana.png`
- `stress-locust.html`
- `stress-grafana.png`
- `soak-locust.html`
- `soak-grafana.png`
- `evidence_manifest.json`

Before committing artifacts, redact:

- cookies and bearer tokens
- Grafana share tokens
- credentialed URLs
- provider request/response payloads
- internal credentials
- tenant identifiers and raw customer content

Validate real evidence explicitly:

```bash
uv run python scripts/validate_chat_load_plan.py \
  --evidence reports/chat-load/<run_id>/evidence_manifest.json
```

## Pass Criteria

- Baseline: first-token P95 < 2000 ms.
- Stress: first-token P50 < 1500 ms and P95 < 3000 ms.
- Stress/Soak streaming: >= 20 token/s or documented content-unit approximation.
- Soak: 0 OOM and 0 deadlock.
- G6 hard gate: first-token P95 < 3000 ms, streaming >= 20 token/s, E2E solve P95 <= 90000 ms.

## Failure Handling

If G6 fails, do not mark the hard-gate passed. Open follow-up architecture work for the relevant cause:

- critic async/deferred execution
- AIGC Layer 2 offline or paragraph-deferred mode
- provider fallback or provider latency investigation
- Chat service capacity tuning
- sandbox warm pool tuning
- API gateway or network bottleneck isolation
