# Billing Reconciler (Story 5.A.7)

Read-only scan of terminal Sagas + their ledger rows. Reports any drift
between expected and actual `SUM(credit_transactions.amount)` per Saga.
**NEVER writes compensation rows** — humans review and adjust.

## Local run

```bash
# Last 24h (default)
uv run python -m billing_service.reconciler_cli --window 24h

# Custom window
uv run python -m billing_service.reconciler_cli --window 7d
uv run python -m billing_service.reconciler_cli \
    --since 2026-05-19T00:00:00+00:00 \
    --until 2026-05-20T00:00:00+00:00
```

Reads `DATABASE_URL` from env (same as the billing-service app).

## Output

stdout: one JSON line (structured-log friendly):

```json
{
  "event": "billing.reconcile.report",
  "window_start": "2026-05-18T03:00:00+00:00",
  "window_end": "2026-05-19T03:00:00+00:00",
  "sagas_examined": 142,
  "diffs_found": 0,
  "total_drift_magnitude": "0.00",
  "results": []
}
```

stderr: human summary `[reconcile] window=... examined=... diffs=... magnitude=...`

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | All OK — no drift above 1 cent. Cron should be green. |
| `1` | At least one MINOR drift (0.01 ≤ \|drift\| < 1.00). Investigate within 24h. |
| `2` | At least one MAJOR drift (\|drift\| ≥ 1.00). **Page on-call.** |

## Per-state expected bounds

Per the orchestrator's known semantics + 5.A.4 route-layer compensations:

| Terminal state | Expected ledger SUM |
|---|---|
| `failed` | exactly 0 |
| `refunded` | exactly 0 (R1.1 net-zero) |
| `rolled_back` | exactly 0 |
| `charged` / `completed` | in `[-A, -charge_min_amount]` where A = saga.amount |

The bounds for charged/completed accept any partial-finalize result (5.A.4
per-formula charging). The reconciler can't see the original elapsed_seconds
(it's in the OutboxEvent payload, not the Saga's `payload_ref`), so it accepts
the range and flags only out-of-range values.

## M3 scheduling integration (deferred)

The reconciler is a runnable Python module. M3 wraps it in one of:

### Option A: K8s CronJob (recommended for cloud)

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: billing-reconciler-daily
spec:
  schedule: "0 3 * * *"   # 03:00 UTC daily
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: reconciler
              image: opticloud/billing-service:latest
              command: ["python", "-m", "billing_service.reconciler_cli", "--window", "24h"]
              env:
                - name: DATABASE_URL
                  valueFrom:
                    secretKeyRef: { name: billing-db, key: url }
              resources:
                requests: { cpu: "100m", memory: "128Mi" }
                limits:   { cpu: "500m", memory: "512Mi" }
```

### Option B: systemd timer (single-host or VM)

```ini
# /etc/systemd/system/billing-reconciler.timer
[Unit]
Description=Daily billing reconciliation

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target

# /etc/systemd/system/billing-reconciler.service
[Unit]
Description=Run billing reconciliation
After=network.target

[Service]
Type=oneshot
EnvironmentFile=/etc/opticloud/billing.env
ExecStart=/opt/opticloud/.venv/bin/python -m billing_service.reconciler_cli --window 24h
```

### Option C: Dramatiq `@cron` (if using in-process scheduler)

Adds Dramatiq dependency to billing-service; defers actual `pip install` and
configuration to M3.

## Alerting integration

The CLI exits with codes 0/1/2 — the simplest integration is a cron wrapper:

```bash
#!/bin/sh
output=$(python -m billing_service.reconciler_cli --window 24h)
rc=$?
echo "$output"
if [ $rc -eq 2 ]; then
    curl -X POST https://hooks.slack.com/services/... \
        -d "{\"text\": \":rotating_light: MAJOR drift detected. Output: $output\"}"
elif [ $rc -eq 1 ]; then
    curl -X POST https://hooks.slack.com/services/... \
        -d "{\"text\": \":warning: MINOR drift detected. Output: $output\"}"
fi
```

For Prometheus integration: parse the JSON line and emit metrics via
`prometheus_pushgateway` or `node_exporter` text-file collector.

## Testing locally

```bash
$env:PYTHONPATH = "apps/billing-service/src;apps/auth-service/src;apps/solver-orchestrator/src;apps/outbox-relayer/src;packages/shared-py;packages/python-sdk/src"
uv run pytest apps/billing-service/tests/test_reconciler.py -v
```

8 tests cover: drift classification, per-state expected-bounds, empty window,
clean completed saga, clean refunded saga, injected drift (MAJOR), partial
finalize within bounds.
