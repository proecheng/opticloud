# Story M3.3b: docker-compose 蓝绿 deploy script（精简档）

Status: done

## Story

As a DevOps engineer on the lean deployment path,
I want a docker-compose blue/green deployment script and matching compose manifests,
so that a 1-2 person team can perform low-downtime deploy and fast rollback without Kubernetes.

## Acceptance Criteria

1. Lean blue/green deployment assets exist.
   - Add `scripts/deploy/blue-green.sh`.
   - Add `docker-compose.blue.yml` and `docker-compose.green.yml`.
   - Blue and green compose files define the same application-facing services with distinct project/container names and host ports.
   - The files are clearly scoped to the lean deployment path and do not replace the existing local-development `docker-compose.yml`.

2. Deployment script has deterministic command surface.
   - Supports `deploy <image_tag>` and `rollback`.
   - Supports `status` for operator visibility.
   - Validates required arguments and prints safe usage on invalid input.
   - Uses configurable environment variables for active slot state, health URL, proxy reload command, compose command, and timeout.
   - Does not embed production secrets.

3. Deploy flow is safe and bounded.
   - Determines current active slot from a state file or defaults safely when no state exists.
   - Starts the inactive slot with the provided image tag.
   - Waits for health before switching traffic.
   - Writes active slot state only after health succeeds and proxy switch command succeeds.
   - Stops the old slot only after the new slot is healthy and marked active.
   - Does not stop the currently active slot if the new slot health check fails.

4. Rollback flow is safe and bounded.
   - Determines previous slot from state.
   - Starts the previous slot before switching traffic back.
   - Waits for previous slot health before switching.
   - Targets 30-second rollback by default through configurable timeout/interval values.
   - Does not require Kubernetes, Helm, Terraform, ArgoCD, ACK, or cloud credentials.

5. Static validation gate exists.
   - Add a local validator script for the blue/green script and compose manifests.
   - Add pytest coverage for success and negative cases.
   - Wire a lightweight CI job triggered by `scripts/deploy/**`, `docker-compose.blue.yml`, `docker-compose.green.yml`, validator/tests, or CI root changes.
   - CI must not run real docker-compose deployment or require Docker daemon access.

6. Scope boundaries are explicit.
   - Do not change M3.3a K8s manifests or validators.
   - Do not add real nginx config, live traffic switching, certificates, DNS, SLB, SSH, cloud deploy, or production secrets in this story.
   - Do not change application runtime behavior.
   - Do not claim 0 downtime from local static checks; document that true downtime validation requires an operator environment.

7. Story workflow tracking is updated.
   - This story records three pre-implementation story review rounds and fixes after each round.
   - `_bmad-output/stories/sprint-status.yaml` moves `m3-3b-docker-compose-blue-green` to `ready-for-dev` only after the three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.

## Tasks / Subtasks

- [x] Add lean blue/green compose assets. (AC: 1, 6)
  - [x] Add `docker-compose.blue.yml`.
  - [x] Add `docker-compose.green.yml`.
  - [x] Use distinct project/container names and host ports.
  - [x] Keep the existing local-development `docker-compose.yml` unchanged.
- [x] Add deploy script. (AC: 2, 3, 4, 6)
  - [x] Add `scripts/deploy/blue-green.sh`.
  - [x] Implement `deploy <image_tag>`, `rollback`, and `status`.
  - [x] Add safe defaults and configurable operator environment variables.
  - [x] Ensure failed health check does not stop the active slot.
- [x] Add static validator. (AC: 1-6)
  - [x] Add `scripts/validate_blue_green_deploy.py`.
  - [x] Validate command surface and safety markers in `blue-green.sh`.
  - [x] Validate blue/green compose service parity, port separation, and health checks.
  - [x] Reject production secrets or Kubernetes/ACK/Helm/Terraform scope drift.
- [x] Add regression tests. (AC: 5)
  - [x] Add `tests/test_blue_green_deploy.py`.
  - [x] Cover committed assets success path.
  - [x] Cover missing rollback command, mismatched services, duplicate ports, and forbidden secret/scope drift negative cases.
- [x] Wire CI. (AC: 5)
  - [x] Add a `blue_green_deploy` path-filter output.
  - [x] Add a lightweight CI job that runs the validator and pytest tests.
  - [x] Keep unrelated service jobs unchanged.
- [x] Update workflow records and validation evidence. (AC: 1-7)
  - [x] Move sprint status to `in-progress` during implementation, then through code review to `done`.
  - [x] Update Dev Agent Record, File List, Change Log, and post-implementation review notes.
  - [x] Run validator, pytest, ruff where applicable, shell syntax check if available, and `git diff --check`.

## Dev Notes

### Context

- Epic M3.3b is the lean-path deployment counterpart to M3.3a. It exists because PI3 split Kubernetes standard-tier namespace isolation from docker-compose lean deployment.
- Architecture D21 standard tier is ACK + ArgoCD; lean tier is single ECS + docker-compose + GitHub Actions push.
- Architecture A.9 explicitly lists first deployment as docker-compose blue/green start for web + api-gateway + solver in the lean path.
- Architecture A.10 says lean GitOps is docker-compose blue/green, while standard tier is ArgoCD + Argo Rollouts canary.
- Existing `docker-compose.yml` is the local development dependency stack and must remain intact.

### Scope Decision

- This story ships an operator script and static compose assets that are reviewable and testable without a Docker daemon.
- The PR gate validates structure and safety semantics but does not run a live deploy.
- Real zero-downtime / 30-second rollback evidence is an operator environment validation item, not a local CI guarantee.
- Start with app-facing placeholder services suitable for lean deploy assets; avoid pulling local dev dependencies into blue/green runtime.

### Architecture / External Constraints

- Docker Compose command should be configurable via `COMPOSE_CMD` so operators can use either `docker compose` or `docker-compose`.
- Active slot state should be configurable via `BLUE_GREEN_STATE_FILE` and default to a local deploy state path.
- Proxy switching should be represented by a configurable `BLUE_GREEN_SWITCH_CMD`; default can be a no-op for dry-run/local validation.
- Health checks should use `curl` against a configurable URL and timeout. Do not require nginx/SLB in CI.
- Scripts should avoid Bash arrays or features that make static validation hard unless justified; keep the operator surface simple.

### Project Structure Notes

- Place deploy script under `scripts/deploy/`.
- Place static validator under `scripts/` to match existing validators.
- Place tests under repo-level `tests/`.
- Update `.github/workflows/ci.yml` only for path filter and new validation job.

### Testing / Validation Notes

- Expected local commands:
  - `uv run python scripts/validate_blue_green_deploy.py`
  - `uv run pytest tests/test_blue_green_deploy.py -q`
  - `uv run ruff check scripts/validate_blue_green_deploy.py tests/test_blue_green_deploy.py`
  - `bash -n scripts/deploy/blue-green.sh` if Bash is available
  - `git diff --check`

### Risks / Decisions

- Main data consistency risk: blue/green manifests drift in services or ports. Validator must check parity and port separation.
- Main function drift risk: script stops active slot before replacement is healthy. Validator/tests must check ordering markers.
- Main boundary risk: accidentally mixing K8s/Helm/Terraform/ACK into lean deploy story. Validator must reject those scope drifts.
- Main closure risk: shipping scripts without CI. Add a dedicated static validation job.
- Operational truth risk: static checks cannot prove 0 downtime. README/script comments must state real validation is operator-run.

### References

- `_bmad-output/planning/epics.md` — Story M3.3b docker-compose blue-green deploy script.
- `_bmad-output/planning/architecture.md` — D21 lean alternative, A.9, A.10, PI3.
- `_bmad-output/stories/m3-3a-k8s-namespace-prod.md` — previous M3.3a standard-tier split and validation pattern.
- `docker-compose.yml` — existing local development stack to preserve.

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Added explicit distinction between local-development `docker-compose.yml` and lean blue/green deploy compose files.
- Added exact file names from the epic and required blue/green service parity.
- Added state-file and configurable command requirements so deploy/rollback have deterministic data flow.
- Added explicit prohibition on embedded production secrets.

Status: PASS after fixes.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Clarified deploy ordering: start inactive slot, wait health, switch traffic, write active state, then stop old slot.
- Clarified rollback ordering and 30-second default target without claiming CI can prove downtime.
- Excluded K8s/ACK/Helm/Terraform/Argo scope that belongs to standard tier or future stories.
- Added validator requirements for command surface, compose parity, ports, health checks, and scope drift.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Added CI path-filter and lightweight validation job requirements.
- Added negative tests for missing rollback command, mismatched services, duplicate ports, and forbidden secret/scope drift.
- Added shell syntax check as optional/local validation when Bash is available.
- Confirmed no application runtime behavior changes are needed.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

1. Add blue/green docker-compose manifests and lean deployment script.
2. Add static validator for script safety markers and compose parity.
3. Add pytest coverage for valid and invalid deploy assets.
4. Wire CI path filter and a lightweight validation job.
5. Run validation, perform post-implementation code review, patch findings, and move the story through workflow states.

### Debug Log References

- 2026-05-26 — Created Story M3.3b after PR #57 was mergeable and confirmed stacked PR CI does not run against feature-branch base.
- 2026-05-26 — Completed three pre-implementation story review rounds before implementation; sprint status moved to ready-for-dev.
- 2026-05-26 — Started implementation; sprint status moved to in-progress.
- 2026-05-26 — Implemented blue/green compose manifests and deploy script with slot-specific health checks and stateful rollback tags.
- 2026-05-26 — Added static validator, pytest negative coverage, and CI path-filter job.
- 2026-05-26 — Validation passed: `uv run python scripts/validate_blue_green_deploy.py`.
- 2026-05-26 — Validation passed: `uv run pytest tests/test_blue_green_deploy.py -q` (8 passed).
- 2026-05-26 — Validation passed: `uv run ruff check scripts/validate_blue_green_deploy.py tests/test_blue_green_deploy.py`.
- 2026-05-26 — Validation passed: `git diff --check`.
- 2026-05-26 — Shell syntax check attempted with `bash -n scripts/deploy/blue-green.sh`; local Windows WSL shim failed because `/bin/bash` is not installed. CI job includes `bash -n` on Ubuntu.

### Completion Notes List

- Added lean-only blue/green compose manifests for `web`, `api-gateway`, and `solver-orchestrator`, with distinct project names, container names, host ports, and `/healthz` healthchecks.
- Added `scripts/deploy/blue-green.sh` with deterministic `deploy <image_tag>`, `rollback`, and `status` commands; state is written only after health and switch success, and rollback uses previous image tag state or an explicit operator override instead of silently using `latest`.
- Added `scripts/validate_blue_green_deploy.py` and `tests/test_blue_green_deploy.py` to statically enforce command surface, deploy/rollback ordering, service parity, host port uniqueness, health checks, secret avoidance, and K8s/Helm/Terraform/ACK/cloud scope boundaries.
- Wired `.github/workflows/ci.yml` with `blue_green_deploy` path filtering and a lightweight validation job that does not require Docker daemon access or live deployment.
- Existing local-development `docker-compose.yml`, M3.3a K8s manifests, validators, and application runtime behavior were not changed.

### Post-Implementation Code Review (AI)

Outcome: PASS after fixes.

Findings fixed:
- The first script draft used one shared health URL, which could check blue while deploying green. Fixed by adding `BLUE_GREEN_BLUE_HEALTH_URL` and `BLUE_GREEN_GREEN_HEALTH_URL`, selected by target slot.
- The first rollback draft could fall back to `latest`, which is unsafe for deterministic rollback. Fixed by persisting active/previous image tags in the state file and requiring an explicit `OPTICLOUD_ROLLBACK_IMAGE_TAG` only when prior state is unavailable.
- The first validator only detected blue-vs-green duplicate host ports. Fixed by rejecting duplicate host ports across all services and adding a same-manifest duplicate-port regression.
- Compose file comments had unnecessary leading whitespace. Fixed for cleaner YAML readability.

Residual risk:
- Static checks prove structure and safety ordering only. Real low-downtime and 30-second rollback evidence still requires an operator environment with the real proxy switch command and deployed images.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/stories/m3-3b-docker-compose-blue-green.md`
- `_bmad-output/stories/sprint-status.yaml`
- `docker-compose.blue.yml`
- `docker-compose.green.yml`
- `scripts/deploy/blue-green.sh`
- `scripts/validate_blue_green_deploy.py`
- `tests/test_blue_green_deploy.py`

### Change Log

- 2026-05-26 — Created Story M3.3b and completed three story review rounds before implementation.
- 2026-05-26 — Started implementation and moved story to in-progress.
- 2026-05-26 — Added lean blue/green compose manifests, deploy script, static validator, regression tests, and CI validation job.
- 2026-05-26 — Completed post-implementation code review and patched slot-specific health checks, rollback tag safety, host-port duplicate coverage, and compose comment formatting.
- 2026-05-26 — Marked story done after validator, pytest, ruff, and diff-check passed; local Bash syntax check blocked by missing `/bin/bash`, covered by Ubuntu CI job.
