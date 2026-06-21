# Deferred Work

## 2026-06-21 - Staging Deployment Verification

Source intent: after README / project status cleanup, continue with real deployment validation.

Status: completed by `_bmad-output/stories/spec-staging-deployment-verification.md`.

Deferred goal:

- Create a lightweight, repeatable staging deployment verification path for the current repository.
- Start from existing `docker-compose.yml`, `docker-compose.blue.yml`, `docker-compose.green.yml`, `infra/k8s/production/`, and service health endpoints.
- Produce documentation and/or scripts that distinguish local smoke verification from production/staging claims.

Reason deferred:

- README / project status cleanup is an independently shippable documentation correction.
- Deployment verification is a separate operational deliverable with different validation risks.
