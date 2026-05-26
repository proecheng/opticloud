# Chat Single-Node Baseline Runbook

## Purpose

M3.6b provides a repeatable single-node dev baseline for Chat latency tuning. It is advisory P57/P58 evidence only. It does not prove or unlock the M3.6a 5-node staging G6 hard-gate.

## Preconditions

- A local/dev single-node Chat stack is running.
- Chat SSE endpoint is reachable from the load-test runner.
- Locust is installed in the operator environment.
- Prompt fixture is `tools/chat_load/prompts_v1.json`.
- Profile config is `tools/chat_load/single_node_profiles.json`.
- Operator can export a redacted metrics snapshot for sandbox startup, capability lookup, chat internal hop, OOM, and deadlock observations.

Required environment variables:

```bash
CHAT_SINGLE_NODE_PROFILE=single_node_baseline
CHAT_LOAD_ENDPOINT=/v1/chat/stream
CHAT_LOAD_BASE_URL=http://localhost:8000
```

Do not commit real URLs with credentials, cookies, bearer tokens, API keys, provider payloads, tenant IDs, or raw user prompts.

## Run Profile

Single-node baseline:

```bash
CHAT_SINGLE_NODE_PROFILE=single_node_baseline locust \
  -f tools/chat_load/single_node_locustfile.py \
  --host "$CHAT_LOAD_BASE_URL" \
  --users 20 \
  --spawn-rate 5 \
  --run-time 300s \
  --headless \
  --html reports/chat-single-node/<run_id>/single-node-locust.html
```

## Evidence Archive

Archive under `reports/chat-single-node/<run_id>/` in a future operator evidence PR:

- `single-node-locust.html`
- `single-node-metrics.json`
- `evidence_manifest.json`

The Locust report supplies request count, completed streams, first-token latency, total response latency, streaming throughput, token-count method, and HTTP error rate. The metrics snapshot supplies sandbox startup P95, capability lookup P95, chat internal hop P95, OOM count, and deadlock count.

Validate real single-node evidence explicitly:

```bash
uv run python scripts/validate_chat_load_plan.py \
  --single-node-evidence reports/chat-single-node/<run_id>/evidence_manifest.json
```

## Advisory Criteria

- First-token P50 < 1500 ms.
- First-token P95 < 3000 ms.
- Streaming >= 20 token/s or documented content-unit approximation.
- E2E solve P95 <= 90000 ms.
- Sandbox startup P95 <= 100 ms.
- Capability lookup P95 < 20 ms.
- Chat internal hop P95 <= 200 ms.
- OOM count = 0 and deadlock count = 0.

These are tuning thresholds. Passing them on one node is not G6 staging pass evidence.

## Follow-Up

If the single-node baseline misses advisory thresholds, isolate before running 5-node staging:

- sandbox warm-pool startup and image readiness
- capability lookup cache behavior
- chat-service internal hop latency
- provider first-token latency
- SSE proxy buffering or flush behavior
- prompt mix and solve-path share

Proceed to M3.6a staging only after the single-node path is structurally healthy or after the deviation is explicitly accepted as a known staging-risk item.
