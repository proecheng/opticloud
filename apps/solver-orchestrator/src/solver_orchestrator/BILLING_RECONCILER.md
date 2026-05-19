# Billing Finalize Retry Reconciler (Story M2.2c)

Auto-remediation counterpart to **5.A.7's** drift detection. Scans
`optimizations.error.billing_finalize_failed=true` rows and retries the
finalize call against billing-service. Successful retries clear the flag.
Persistent failures after `max_retries` get tagged `billing_given_up_at`
for ops review.

## Why this exists

5.A.4 chose **single-attempt** for solver-side billing calls (Q4 decision)
so a billing outage can't slow the solver response P95. The cost: rows
accumulate with `error.billing_finalize_failed=true`. **5.A.7 detects**
the resulting ledger drift; **M2.2c heals it**.

## Local run

```bash
# Default — max 5 retries, batch of 100 rows per cycle
uv run python -m solver_orchestrator.billing_reconciler_cli

# Tune both parameters
uv run python -m solver_orchestrator.billing_reconciler_cli \
    --max-retries 3 --batch-limit 50
```

Reads `DATABASE_URL` + `BILLING_BASE_URL` + `BILLING_SERVICE_SHARED_SECRET`
from env (same as the solver-orchestrator app).

## Output

stdout: one JSON line:

```json
{
  "event": "billing.reconciler.report",
  "pending": 12,
  "succeeded": 10,
  "failed": 1,
  "exhausted": 1,
  "results": [
    {"optimization_id": "...", "user_id": "...", "billing_charge_id": "...",
     "attempt_number": 1, "succeeded": true, "error_message": null},
    ...
  ]
}
```

stderr: human summary `[billing-reconciler] pending=12 succeeded=10 failed=1 exhausted=1`

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | pending == 0 OR all retries succeeded — healthy |
| `1` | At least one transient failure — will retry next cycle, no alert |
| `2` | At least one row hit `max_retries` (gave up) — **page on-call** |

## Per-row outcome semantics

After the reconciler processes an optimization row, its `error` JSON looks like:

| Outcome | error fields |
|---|---|
| Success — cleared | `billing_finalize_succeeded_at` set; `billing_finalize_failed` + retry counters removed |
| Transient — will retry | `billing_retry_count` incremented; `billing_finalize_last_error` updated; flag still true |
| Given up | `billing_given_up_at` set; `billing_retry_count == max_retries`; flag still true; ops investigates |

## Interaction with 5.A.7 reconciler

| Job | Service | Frequency | Action |
|---|---|---|---|
| **5.A.7** (`billing-reconciler-daily`) | billing-service | daily 03:00 UTC | **Detects** ledger drift; reports only |
| **M2.2c** (this job — `billing-finalize-retry`) | solver-orchestrator | every minute / few minutes | **Heals** missed finalizes by retrying |

A row that fails finalize once → solver writes flag. M2.2c retries on next cycle. If billing is reachable now, succeeds → flag cleared → 5.A.7 doesn't see drift. If billing is still down after `max_retries` → M2.2c gives up → 5.A.7 will eventually flag this row's drift in its daily report.

## M3 scheduling integration

### Option A: K8s CronJob (recommended)

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: billing-finalize-retry
spec:
  schedule: "*/5 * * * *"   # every 5 minutes
  concurrencyPolicy: Forbid  # don't pile up if a run is slow
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: reconciler
              image: opticloud/solver-orchestrator:latest
              command:
                - python
                - -m
                - solver_orchestrator.billing_reconciler_cli
                - --max-retries
                - "5"
              env:
                - name: DATABASE_URL
                  valueFrom:
                    secretKeyRef: { name: solver-db, key: url }
                - name: BILLING_BASE_URL
                  value: "http://billing-service:8003"
                - name: BILLING_SERVICE_SHARED_SECRET
                  valueFrom:
                    secretKeyRef: { name: billing-internal-auth, key: secret }
              resources:
                requests: { cpu: "100m", memory: "128Mi" }
                limits:   { cpu: "500m", memory: "512Mi" }
```

### Option B: Dramatiq `@cron` (in-process scheduler)

Add Dramatiq dep to solver-orchestrator; schedule:

```python
import dramatiq
from dramatiq.middleware.cron import Cron

@dramatiq.actor(cron="*/5 * * * *")
async def run_billing_reconciler():
    # ... call retry_pending_finalizes(...)
```

### Option C: systemd timer (single-host)

Standard `.timer` + `.service` unit pair — same shape as 5.A.7's RECONCILER.md.

## Alerting

Pipe exit codes to your alerting layer:

```bash
#!/bin/sh
output=$(python -m solver_orchestrator.billing_reconciler_cli)
rc=$?
echo "$output"
if [ $rc -eq 2 ]; then
    curl -X POST $SLACK_WEBHOOK \
        -d "{\"text\": \":rotating_light: Billing reconciler gave up on $output\"}"
fi
```

For Prometheus: parse JSON line and emit `billing_reconciler_*` gauges.

## Testing locally

```bash
$env:PYTHONPATH = "apps/solver-orchestrator/src;apps/auth-service/src;apps/billing-service/src;packages/shared-py"
uv run pytest apps/solver-orchestrator/tests/test_billing_reconciler.py -v
```

6 tests cover: empty DB, success-clears-flag, failure-increments, exhausted-after-max,
batch-limit, ignore-already-succeeded. Tests use monkeypatch to stub `billing_client.finalize`
so no live billing-service needed.
