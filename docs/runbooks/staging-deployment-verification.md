# Staging Deployment Verification

This runbook defines the repeatable verification path for turning the current repository from static deploy assets into a staging-ready operational checklist.

It is intentionally scoped to **staging verification readiness**. It does not claim that production is deployed, that Kubernetes NetworkPolicy is live-enforced, or that blue/green traffic has been switched in a real environment.

## Verification Lanes

### 1. Local dependency smoke

Purpose: prove local infrastructure and service health endpoints can be exercised from a clean checkout.

Commands:

```powershell
Copy-Item .env.example .env
docker-compose up -d
docker-compose ps
python scripts/validate_deployment_verification.py
```

Expected evidence:

- `docker-compose ps` shows the local dependency stack is running.
- `scripts/validate_deployment_verification.py` prints `deployment verification assets OK`.

### 2. Blue/green static verification

Purpose: prove the lean blue/green compose assets and deployment script preserve the required safety order.

Commands:

```powershell
uv run python scripts/validate_blue_green_deploy.py
uv run pytest tests/test_blue_green_deploy.py -q
```

If local `uv run` has not synced the workspace dependencies yet, run the pytest command first or run this lane in CI. The direct validator imports PyYAML through the repository's Python environment.

Required safety properties:

- Deploy starts the inactive slot first.
- Health checks pass before traffic switch.
- State is written after health and switch.
- Previous active slot is stopped only after successful switch.
- Rollback fails closed if no previous image tag exists.

### 3. Kubernetes manifest static verification

Purpose: prove committed production namespace and NetworkPolicy manifests still match the standard-tier domain model.

Commands:

```powershell
uv run python scripts/validate_k8s_network_policies.py infra/k8s/production
uv run pytest tests/test_k8s_network_policies.py -q
```

If the direct validator cannot import PyYAML locally, use the pytest command or CI after the workspace dependencies are synced.

Boundary:

- This is static manifest validation only.
- Live enforcement requires a NetworkPolicy-capable CNI and a real cluster test.

### 4. Optional live staging smoke

Purpose: run only after staging URLs exist.

Required environment variables:

- `OPTICLOUD_STAGING_WEB_URL`
- `OPTICLOUD_STAGING_AUTH_URL`
- `OPTICLOUD_STAGING_SOLVER_URL`

Suggested checks:

```powershell
curl.exe --fail "$env:OPTICLOUD_STAGING_WEB_URL/healthz"
curl.exe --fail "$env:OPTICLOUD_STAGING_AUTH_URL/healthz"
curl.exe --fail "$env:OPTICLOUD_STAGING_SOLVER_URL/healthz"
```

Do not commit staging URLs, tokens, cookies, tenant identifiers, or live logs.

## Evidence Rules

- Keep local smoke output out of git unless it is intentionally redacted and referenced by a later evidence manifest.
- Do not call static validation "production verified".
- Do not claim ACK / Kubernetes enforcement until server-side dry-run and live pod connectivity checks have been run in a prepared cluster.
- Do not claim blue/green switch success until `BLUE_GREEN_SWITCH_CMD` has run against the staging traffic layer.

## Failure Handling

- Local dependency smoke failure: inspect Docker Desktop, occupied ports, and `.env` drift.
- Blue/green static failure: fix compose/script drift before any deploy attempt.
- Kubernetes static failure: fix namespace labels, default-deny policies, or allowed flow drift before applying manifests.
- Live staging smoke failure: stop promotion, keep the previous slot active, and open a deployment incident or follow-up story.
