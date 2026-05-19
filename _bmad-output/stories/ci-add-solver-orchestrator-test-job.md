---
story_key: ci-add-solver-orchestrator-test-job
epic_num: 0
story_num: ci-debt-1
epic_name: Tech-debt — CI hardening
status: ready-for-dev
priority: 🟡 Medium (small CI gap; unblocks future solver-orchestrator stories from running tests automatically)
sizing: XS (~30 min; one YAML job + apply schema files)
type: tech-debt
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - .github/workflows/ci.yml L185 (billing-service-test job — shape to mirror)
  - apps/solver-orchestrator/tests/ (12 existing local tests not run in CI)
  - apps/solver-orchestrator/pyproject.toml (pytest config; httpx + asyncio + hypothesis deps)
dependencies:
  upstream:
    - 1.3 (done — discovered the gap)
---

# CI: Add solver-orchestrator-test job

## User Story

**As** an engineer landing solver-orchestrator changes
**I want** CI to run the solver-orchestrator pytest suite on every PR
**so that** future solver changes (auth bridge mods, billing client tweaks, LP wrapper updates) are verified in PRs instead of only locally.

## Why

Discovered during Story 1.3 review: `.github/workflows/ci.yml` has the path filter wired for `solver_orchestrator` but no actual job consumes it. The 13 local solver tests (LP solve, billing integration, last_used_at update) only run via local `pytest` invocations. Any future PR touching `apps/solver-orchestrator/**` ships untested at the CI layer.

This is small enough to be a single PR — no design needed.

## Acceptance Criteria

### AC1: New CI job `solver-orchestrator-test`

In `.github/workflows/ci.yml`, add a job mirroring `billing-service-test`:

```yaml
solver-orchestrator-test:
  needs: changes
  if: needs.changes.outputs.solver_orchestrator == 'true' || needs.changes.outputs.shared_py == 'true' || needs.changes.outputs.ci_or_root == 'true'
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:16-alpine
      env:
        POSTGRES_USER: opticloud
        POSTGRES_PASSWORD: opticloud_dev
        POSTGRES_DB: opticloud_dev
      options: >-
        --health-cmd "pg_isready -U opticloud -d opticloud_dev"
        --health-interval 5s
        --health-timeout 3s
        --health-retries 5
      ports:
        - 5432:5432
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: ${{ env.PYTHON_VERSION }}
    - run: pip install uv==${{ env.UV_VERSION }}
    - run: uv sync --all-packages --extra dev
    - name: Apply schema
      env:
        PGPASSWORD: opticloud_dev
      run: |
        psql -h localhost -U opticloud -d opticloud_dev -f infra/local-init/01-schema.sql
        psql -h localhost -U opticloud -d opticloud_dev -f infra/local-init/02-solver-schema.sql
        psql -h localhost -U opticloud -d opticloud_dev -f infra/local-init/03-billing-schema.sql
    - name: Run tests
      env:
        DATABASE_URL: postgresql+asyncpg://opticloud:opticloud_dev@localhost:5432/opticloud_dev
      run: uv run pytest apps/solver-orchestrator/tests/ -v
```

Schema files needed:
- `01-schema.sql` — users + api_keys (referenced by solver auth tests)
- `02-solver-schema.sql` — optimizations + idempotency_keys (solver's own tables)
- `03-billing-schema.sql` — billing tables (test_billing_integration uses them for mocked billing)

### AC2: Job triggers correctly

Path filter `solver_orchestrator` already exists at line 31 + 68 of ci.yml — no changes needed there. The new job's `if:` clause references this output, plus `shared_py` (for shared module changes) and `ci_or_root` (for workflow edits).

### AC3: Verify on this PR

The PR itself modifies `.github/workflows/ci.yml`, which triggers `ci_or_root == 'true'`, which means the new `solver-orchestrator-test` job WILL run on this PR (alongside other CI jobs that also pick up workflow changes). Expect 13/13 solver tests pass.

## Tasks

### T1: Add the job to ci.yml (10 min)
1. Open `.github/workflows/ci.yml`; locate the `billing-service-test` job (line 185)
2. After it ends, insert `solver-orchestrator-test` per AC1
3. Verify YAML syntax by running `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` locally

### T2: Sprint-status + PR (20 min)
1. Add `ci-add-solver-orchestrator-test-job: done` to sprint-status (NEW entry — wasn't there)
2. Commit + push + PR
3. Wait CI green; verify the NEW job actually runs (not skipped); merge

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `02-solver-schema.sql` doesn't apply cleanly in CI's fresh Postgres | This SQL has been running in dev (docker-compose) since Sprint 0; CI just needs to apply it explicitly per AC1 |
| Solver tests depend on JWT keys auto-generated at startup but CI doesn't run uvicorn | Solver tests don't need JWT — they use API-Key auth via HMAC + the pepper-dev env. ✓ already working locally without uvicorn |
| respx-style mocks need network deps | `httpx.MockTransport` (used by test_billing_integration) is built into httpx; no extra dep |
| Adds ~30s to CI total wall time | Acceptable; runs in parallel with billing/auth/outbox jobs |

## Definition of Done

- New job `solver-orchestrator-test` defined in ci.yml
- On this PR's CI run: the job actually executes (status != "skipping"), passes 13/13 tests
- Sprint-status updated
- Memory updated to remove `ci-add-solver-orchestrator-test-job` from backlog

## Sign-off

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Tech Lead | proposed by AI | ☐ | — |

> Owner committee deferred per M0 skip.
