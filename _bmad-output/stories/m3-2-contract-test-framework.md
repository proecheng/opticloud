# Story M3.2: Contract Test Framework

Status: done

## Story

As a QA engineer,
I want a Schemathesis-backed contract test framework wired into CI for currently available FastAPI services,
so that OpenAPI specs and actual endpoint behavior stay aligned without requiring each PR to boot a full external stack.

## Acceptance Criteria

1. A repository-level contract test harness exists.
   - Add `tests/contract/` with shared fixtures / configuration for Schemathesis contract tests.
   - Reuse `opticloud_shared.property_test_base.fixtures` from Story 0.5b rather than reimplementing Schemathesis loaders.
   - Provide a service registry that maps service names to ASGI app import paths and OpenAPI paths for services that are ready for contract testing.
   - The initial required service is `auth-service`; optional downstream services may be listed as future targets but must not be marked required until their tests are reliable.

2. Auth-service has a deterministic local contract gate.
   - Contract tests load the auth-service FastAPI app in-process via ASGI/TestClient or equivalent.
   - Tests cover `/healthz` with Schemathesis-generated cases.
   - `/readyz` is documented as a future contract target because it depends on a database session today.
   - Tests validate response status codes and response schemas through Schemathesis.
   - Tests do not require Postgres, Redis, Docker, Kubernetes, or network access.
   - Tests must not mutate durable service state, create users, create API keys, send OTPs, or rely on external secrets.

3. Static OpenAPI drift remains separate but is connected.
   - Keep `scripts/generate_openapi.py` and `scripts/check_openapi_drift.py` as the static spec generation/drift gate.
   - Do not replace the OpenAPI drift job with Schemathesis.
   - Add documentation or helper metadata explaining the difference: drift check compares generated spec files; contract tests validate live/in-process behavior against the app spec.

4. CI runs a lightweight contract-test job.
   - Update `.github/workflows/ci.yml` with a `contract_tests` path filter.
   - Add a `contract-test` job that installs Python deps and runs the targeted contract pytest command.
   - Trigger the job when contract tests, shared property-test fixtures, auth-service OpenAPI-affecting code, OpenAPI scripts, or root CI config change.
   - Do not broaden unrelated service test jobs.

5. The framework is bounded and extensible.
   - Provide `tests/contract/README.md` documenting how to add a service, how to choose ASGI vs URL/CLI mode, and how to keep generated case count bounded for PR speed.
   - Set deterministic Hypothesis / Schemathesis limits suitable for PR gate speed; the story should not require 100+ generated cases locally.
   - Include a future/nightly command note for broader `schemathesis run ... --checks all` coverage without making it a PR blocker.

6. Scope boundaries are explicit.
   - Do not add full contract coverage for billing-service, solver-orchestrator, sandbox-runner, chat-service, critic-service, or capability-registry in this story.
   - Do not change auth-service, billing, solver, sandbox, or web runtime behavior.
   - Do not require a running localhost service in CI.
   - Do not add Postman sync, SDK codegen, Playwright E2E, or M3.4b AIGC filter contract tests.

7. Story workflow tracking is updated.
   - This story records three pre-implementation story review rounds and the fixes made after each round.
   - `_bmad-output/stories/sprint-status.yaml` moves `m3-2-contract-test-framework` to `ready-for-dev` only after the three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.

## Tasks / Subtasks

- [x] Build contract test harness. (AC: 1, 5)
  - [x] Add `tests/contract/conftest.py` with service registry and shared test settings.
  - [x] Add `tests/contract/README.md` with service onboarding and PR/nightly guidance.
  - [x] Reuse `opticloud_shared.property_test_base.fixtures`.
  - [x] Add an ASGI-app Schemathesis helper to the shared fixture module if needed for in-process tests.
- [x] Add auth-service contract tests. (AC: 2)
  - [x] Add `tests/contract/test_auth_service_contract.py`.
  - [x] Cover `/healthz` via Schemathesis.
  - [x] Document `/readyz` as a future DB-backed contract target.
  - [x] Ensure tests run in-process and need no database/network.
- [x] Document OpenAPI drift vs contract test responsibilities. (AC: 3, 5)
  - [x] Reference `scripts/generate_openapi.py` and `scripts/check_openapi_drift.py`.
  - [x] Keep static spec drift and contract behavior checks separate.
- [x] Wire CI contract-test job. (AC: 4)
  - [x] Add `contract_tests` path-filter output.
  - [x] Add a `contract-test` job with `PYTHONPATH` matching auth-service/shared imports.
  - [x] Keep unrelated service jobs unchanged.
- [x] Update workflow records and validation evidence. (AC: 1-7)
  - [x] Move sprint status to `in-progress` during implementation and `code-review` after implementation validation.
  - [x] Update Dev Agent Record, File List, Change Log, and post-implementation review notes.
  - [x] Run contract tests, relevant shared tests, lint/type checks as applicable, and `git diff --check`.

### Review Findings

- [x] [Review][Patch] Avoid importing contract registry from pytest `conftest.py` [tests/contract/test_auth_service_contract.py] — fixed by moving reusable registry definitions to `tests/contract/registry.py` and leaving `conftest.py` as pytest configuration/export surface only.
- [x] [Review][Patch] Centralize deterministic PR-gate case limits [tests/contract/test_auth_service_contract.py] — fixed by adding `CONTRACT_MAX_EXAMPLES` and `derandomize=True` for bounded, repeatable Schemathesis generation.

## Dev Notes

### Context

- Story 0.5b already installed Hypothesis + Schemathesis infrastructure and added `opticloud_shared.property_test_base.fixtures`.
- Story 0.5b explicitly left the full contract test CI gate to M3.2.
- Architecture P61 defines Schemathesis OpenAPI-driven tests for schema consistency, error responses, boundary cases, and fuzzing.
- Current static OpenAPI generation only covers auth-service through `scripts/generate_openapi.py`; `check_openapi_drift.py` is already wired in CI as a separate drift check.
- `auth-service` exposes `/healthz` and `/readyz` through its health router. `/healthz` is no-DB; `/readyz` currently depends on `get_session` and should not be in the first no-infra PR gate.

### Scope Decision

- Start with a narrow but real PR gate: auth-service `/healthz` contract tests in-process.
- Do not require `schemathesis run http://localhost:8000/openapi.json --checks all` in PR CI because it needs live service orchestration and can be promoted to nightly later.
- Use bounded generated examples for speed. The "100+ generated test cases" target from epics becomes a later/nightly maturity target, not a blocker for this first PR gate.
- Keep service registry declarative so billing/solver/sandbox can be added in future stories without changing the harness shape.

### Architecture / External Constraints

- Schemathesis version in the current lockfile is 4.x; use `schemathesis.openapi.*` APIs already used by Story 0.5b helpers.
- In-process ASGI contract tests avoid ports, Docker, and network and are appropriate for PR CI.
- Auth-service imports require `apps/auth-service/src` and `packages/shared-py` on `PYTHONPATH`.
- Do not start database-dependent auth routes in this story; `/healthz` is the safe initial contract surface.

### Project Structure Notes

- Place harness and tests under `tests/contract/`.
- Keep `packages/shared-py/opticloud_shared/property_test_base/` as the shared helper home; do not duplicate helper APIs under `tests/contract/`.
- Update `.github/workflows/ci.yml` only for path filter and new contract job.

### Testing / Validation Notes

- Expected local commands:
  - `$env:PYTHONPATH='apps/auth-service/src;packages/shared-py'; uv run pytest tests/contract -q`
  - `uv run pytest packages/shared-py/tests/test_property_base_schemathesis_sample.py -q`
  - `git diff --check`
- If linting new tests is useful, run `uv run ruff check tests/contract`.
- Do not run DB-backed auth-service suite unless implementation touches auth runtime behavior, which this story should not do.

### Risks / Decisions

- Main data consistency risk: testing a static spec without validating actual app behavior. Use in-process app calls for auth-service.
- Main function drift risk: replacing OpenAPI drift check with contract tests. Keep both gates separate.
- Main boundary risk: attempting all service coverage before services are contract-ready. Start with auth-service health/readiness and document future additions.
- Main closure risk: adding local tests without CI. Add a dedicated contract-test job.

### References

- `_bmad-output/planning/epics.md` — Story M3.2 Contract Test Framework.
- `_bmad-output/planning/architecture.md` — P61 Contract Test + Critical Journey E2E.
- `_bmad-output/stories/0-5b-property-test-framework.md` — Schemathesis foundation and lessons.
- `packages/shared-py/opticloud_shared/property_test_base/fixtures.py` — shared Schemathesis loaders.
- `packages/shared-py/tests/test_property_base_schemathesis_sample.py` — existing sample.
- `scripts/generate_openapi.py` and `scripts/check_openapi_drift.py` — static OpenAPI generation/drift.
- `.github/workflows/ci.yml` — existing path-filtered CI pattern.

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Added a service registry requirement so service names, app import paths, and OpenAPI paths are single-sourced for contract tests.
- Added explicit auth-service safe endpoint `/healthz` to avoid mutating durable state.
- Documented `/readyz` as a future DB-backed target rather than putting it in the no-infra PR gate.
- Added PYTHONPATH requirements for auth-service and shared-py imports.
- Added separation between static generated OpenAPI files and app-derived contract tests.

Status: PASS after fixes.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Reused Story 0.5b helpers instead of inventing a second Schemathesis loader.
- Reframed the epics' `schemathesis run http://localhost:8000/openapi.json --checks all` as nightly/future guidance, not PR CI for this story.
- Excluded full service coverage, Postman sync, SDK codegen, Playwright E2E, and M3.4b AIGC filter contract tests.
- Added deterministic generated-case limits for PR speed.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Added a dedicated `contract-test` CI job and path-filter requirements.
- Added README/onboarding docs so future services can join without changing harness design.
- Added validation commands and workflow state requirements.
- Confirmed no runtime behavior changes are needed for auth-service or other services.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

1. Add `tests/contract` registry, conftest, auth-service contract tests, and README.
2. Reuse `opticloud_shared.property_test_base.fixtures` for Schemathesis loading.
3. Add bounded settings for PR-speed contract tests.
4. Wire CI path filter and contract-test job.
5. Run validation, perform post-implementation code review, patch findings, and move the story through workflow states.

### Debug Log References

- 2026-05-26 — Created Story M3.2 from Epic M3.2, architecture P61, Story 0.5b Schemathesis foundation, and current OpenAPI drift scripts.
- 2026-05-26 — Started implementation after three story review rounds passed; sprint status moved to in-progress.
- 2026-05-26 — Added repo-level contract harness and auth-service in-process `/healthz` Schemathesis gate.
- 2026-05-26 — Initial validation found import-order/unused-import issues and CRLF diff-check failures in shared fixture; fixed with ruff and LF normalization.
- 2026-05-26 — Validation passed: `uv run pytest tests/contract -q` (4 passed), `uv run pytest packages/shared-py/tests/test_property_base_schemathesis_sample.py -q` (2 passed), `uv run ruff check tests/contract packages/shared-py/opticloud_shared/property_test_base/fixtures.py`, and `git diff --check`.
- 2026-05-26 — Post-implementation code review found and fixed two patch findings: `conftest.py` registry coupling and non-centralized deterministic case bounds.
- 2026-05-26 — Post-review validation passed: contract tests (4 passed), shared Schemathesis sample (2 passed), ruff, `git diff --check`, and explicit no-index whitespace checks for new contract-test files.

### Completion Notes List

- Added `tests/contract` as the repository-level Schemathesis contract test harness.
- Added a declarative contract service registry with `auth-service` as the only required PR-gated service.
- Added `schemathesis_from_asgi_app()` to the shared property-test fixture module so PR contract tests validate in-process app behavior without network or Docker.
- Added auth-service `/healthz` contract coverage with bounded Hypothesis examples and a stable payload regression test.
- Documented `/readyz` as a future DB-backed contract target and documented static OpenAPI drift versus live/in-process contract responsibilities.
- Added a path-filtered `contract-test` CI job without broadening unrelated service jobs.
- Post-implementation code review completed; all patch findings were fixed and revalidated.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/stories/m3-2-contract-test-framework.md`
- `_bmad-output/stories/sprint-status.yaml`
- `packages/shared-py/opticloud_shared/property_test_base/fixtures.py`
- `tests/__init__.py`
- `tests/contract/__init__.py`
- `tests/contract/README.md`
- `tests/contract/conftest.py`
- `tests/contract/registry.py`
- `tests/contract/test_auth_service_contract.py`

### Change Log

- 2026-05-26 — Created Story M3.2 and completed three story review rounds before implementation.
- 2026-05-26 — Started implementation and moved story to in-progress.
- 2026-05-26 — Implemented contract test harness, auth-service `/healthz` contract tests, shared ASGI Schemathesis helper, README guidance, and CI `contract-test` job.
- 2026-05-26 — Completed implementation validation and moved story to code-review.
- 2026-05-26 — Addressed post-implementation code review findings and moved story to done.
