# Story M3.1: Sandbox I/O Pattern + Self-Loop Prevention

Status: done

## Story

As a backend / security engineer,
I want a sandbox-runner service skeleton that enforces the P58 stdin/stdout/stderr/result-file I/O contract and rejects P62 LLM self-loop instructions,
so that later Chat / Coder execution can integrate with a controlled sandbox boundary without external network calls, writable host filesystem access, or recursive LLM invocation.

## Acceptance Criteria

1. `apps/sandbox-runner/` becomes a workspace Python service with a local testable execution contract.
   - Add `apps/sandbox-runner/pyproject.toml`, `src/sandbox_runner/`, and `tests/`.
   - Add the service to the root `uv` workspace.
   - Keep the service local/stubbed: do not require real gVisor, K8s, Docker, or cloud infrastructure to run tests.
   - Provide a FastAPI app with health endpoint and a sandbox execution endpoint suitable for future `chat-service` integration.

2. P58 I/O contract is explicit and enforced.
   - Define request / response schemas for code execution.
   - Inputs enter through a bounded stdin payload and optional read-only named input files.
   - Outputs return through stdout, stderr, exit code, status, and result-file metadata.
   - Result files are limited to 100 MB by contract; local test implementation should use a much smaller configurable byte budget for deterministic tests.
   - Direct host-path writes, absolute input file paths, parent-directory traversal, and unsupported binary payloads are rejected before execution.
   - The response must map policy violations to stable machine-readable error codes.

3. P62 self-loop prevention rejects LLM-calling instructions before execution.
   - Reject code or stdin that contains obvious external LLM call intent, including OpenAI / Anthropic / DeepSeek / Qwen endpoint names, common SDK imports, and prompt patterns instructing the sandbox to call an LLM.
   - Return a stable `llm_self_loop_blocked` error.
   - The blocked path must not invoke the execution backend.

4. Network-disabled policy is represented and tested.
   - Code that attempts to import or use common networking modules such as `requests`, `urllib`, `httpx`, or sockets must be rejected with `network_disabled`.
   - The local implementation must not perform real network calls.
   - This story covers pre-execution policy enforcement only; Kubernetes `NetworkPolicy egress: deny all` and real gVisor runtime enforcement remain downstream deployment work.

5. Execution timeout / resource limits are captured without overclaiming real gVisor.
   - Expose policy constants or config for 1 vCPU, 1 GB memory, 30s soft timeout, 90s hard timeout, read-only filesystem, and writable result budget.
   - Local tests may use shorter timeouts and lower byte budgets.
   - Do not claim real CPU, memory, RuntimeClass, seccomp, AppArmor, capability drop, fork-bomb containment, or container-escape prevention is shipped by this story.

6. Tests and CI validate the contract.
   - Add sandbox-runner unit/API tests covering success, stdout/stderr/exit-code mapping, result-file metadata, network block, LLM self-loop block, path traversal rejection, absolute path rejection, and result budget rejection.
   - Add a CI path filter and lightweight `sandbox-runner-test` job that runs the targeted service tests when `apps/sandbox-runner/**` changes.
   - Existing unrelated service jobs must not be broadened except through existing root/shared triggers.

7. Scope boundaries are explicit and downstream work remains deferred.
   - Do not implement Story M3.7 full sandbox security audit.
   - Do not add `tests/sandbox/security/` 12 or 15 attack scenarios.
   - Do not add AppArmor profile, capability-drop manifest, seccomp profile, K8s RuntimeClass, K8s NetworkPolicy, warm pool controller, SSE log streaming, chat-service integration, SDK flags, billing, provider calls, or user-facing UI.
   - Story M3.7 remains owner for gVisor escape/capability/AppArmor/supply-chain audit; Story 4.B.2 remains owner for full Coder execution integration; Story 4.B.6 remains owner for `--allow-logs-stream`.

8. Story workflow tracking is updated.
   - This story records three pre-implementation story review rounds and the fixes made after each round.
   - `_bmad-output/stories/sprint-status.yaml` moves `m3-1-sandbox-io-pattern` to `ready-for-dev` only after the three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.

## Tasks / Subtasks

- [x] Scaffold sandbox-runner service. (AC: 1, 5)
  - [x] Add `apps/sandbox-runner/pyproject.toml` and include it in the root workspace.
  - [x] Add `src/sandbox_runner/__init__.py`, `schemas.py`, `policy.py`, `executor.py`, `main.py`.
  - [x] Add health endpoint and execution endpoint.
- [x] Implement P58 I/O contract. (AC: 2, 5)
  - [x] Validate bounded stdin and optional named input files.
  - [x] Reject absolute paths, parent-directory traversal, and oversized result files.
  - [x] Return stdout, stderr, exit code, status, and result-file metadata.
  - [x] Encode stable error codes for policy violations.
- [x] Implement P62 self-loop and network-disabled preflight. (AC: 3, 4)
  - [x] Reject LLM provider / SDK / prompt-loop patterns in code or stdin.
  - [x] Reject obvious networking module usage.
  - [x] Ensure blocked requests do not call the executor.
- [x] Add tests. (AC: 2, 3, 4, 5, 6)
  - [x] Add API tests under `apps/sandbox-runner/tests/`.
  - [x] Cover success, stdout/stderr/exit-code mapping, result-file metadata, network block, LLM self-loop block, path traversal rejection, absolute path rejection, and result budget rejection.
- [x] Wire CI. (AC: 6)
  - [x] Add `sandbox_runner` path filter to `.github/workflows/ci.yml` if needed.
  - [x] Add a lightweight `sandbox-runner-test` job.
  - [x] Do not broaden unrelated service jobs.
- [x] Update workflow records and validation evidence. (AC: 1-8)
  - [x] Move sprint status to `in-progress` during implementation and `code-review` after implementation validation.
  - [x] Update Dev Agent Record, File List, Change Log, and post-implementation review notes.
  - [x] Run targeted tests, relevant lint/type checks, and `git diff --check`.
  - [x] Address post-implementation code review findings and re-run validation.

## Dev Notes

### Context

- M3.1 comes from Epic 0 Foundation Continuation and implements P58 Sandbox I/O Pattern plus P62 self-loop prevention.
- Architecture P58 allows only stdin, stdout, exit code, and emptyDir result files. It forbids external network access, cross-container IPC except inside sandbox-runner pod, and filesystem modification except emptyDir tmpfs.
- PRD sandbox performance sets 1 vCPU / 1 GB, network disabled, read-only filesystem, 30s soft timeout, and 90s hard timeout.
- `apps/sandbox-runner/` exists today only as `.gitkeep`; this story should create the minimal Python service package instead of duplicating another location.
- `apps/chat-service/`, `apps/critic-service/`, and `apps/capability-registry/` are still placeholders. Do not integrate them in this story.

### Scope Decision

- Build a deterministic local execution contract, not real gVisor/K8s isolation.
- Use pre-execution policy checks to block obvious network and self-loop patterns. This is a contract guard, not a substitute for M3.7 runtime security controls.
- Prefer FastAPI + Pydantic patterns used by existing services.
- Keep the local executor deliberately narrow and test-focused. It may execute only a safe subset of local behavior needed to prove stdout/stderr/exit-code/result-file contract.
- Do not add new database schema, migrations, billing flows, UI, Docker build changes, or cloud resources.

### Architecture / External Constraints

- Future production deployment must use `RuntimeClass: gvisor`, deny-all egress, read-only filesystem, emptyDir tmpfs, and 90s hard kill. M3.1 documents/configures the contract but does not prove runtime isolation.
- P60 namespace single-direction flow and prod-ai sandbox-runner placement remain downstream deployment concerns.
- M3.7 owns AppArmor, capability drop, seccomp, container escape, Docker socket, SYS_PTRACE, mount namespace escape, fork bomb, and CRG6 supply-chain attack scenarios.
- Story 4.B.6 owns SSE stdout/stderr log streaming; M3.1 response can expose captured stdout/stderr synchronously for tests.

### Project Structure Notes

- Use `apps/sandbox-runner/src/sandbox_runner/` for service code.
- Use `apps/sandbox-runner/tests/` for service tests.
- Update root `pyproject.toml` workspace members.
- Update `.github/workflows/ci.yml` with a dedicated sandbox-runner job and path filter.

### Testing / Validation Notes

- Expected local commands:
  - `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/sandbox-runner/tests -q`
  - `uv run ruff check apps/sandbox-runner`
  - `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run mypy apps/sandbox-runner/src/sandbox_runner`
  - `git diff --check`
- Tests should not require Docker, gVisor, K8s, network, database, Redis, or cloud credentials.
- Use small test-configurable limits for result-file byte budget and timeout so boundary tests are fast and deterministic.

### Risks / Decisions

- Main data consistency risk: accepting unsafe file names or returning ambiguous result metadata. Reject absolute / traversal paths and return stable result-file records.
- Main function drift risk: claiming real sandbox isolation when only preflight/local contract exists. Keep all gVisor/K8s runtime claims out of completion notes.
- Main boundary risk: accidentally starting M3.7 audit work. Do not add `tests/sandbox/security/` or runtime hardening manifests here.
- Main closure risk: creating a service without CI. Add a path-filtered sandbox-runner test job.

### References

- `_bmad-output/planning/epics.md` — Story M3.1, Story M3.7, Story 4.B.2, Story 4.B.6.
- `_bmad-output/planning/architecture.md` — P58 Sandbox I/O Pattern, Sandbox special isolation, service topology.
- `_bmad-output/planning/prd.md` — FR N11 sandbox resource and timeout constraints.
- `apps/sandbox-runner/.gitkeep` — current placeholder service location.
- `.github/workflows/ci.yml` — existing path-filtered CI pattern.
- `pyproject.toml` — existing uv workspace membership pattern.

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Added a strict distinction between allowed P58 channels and returned response fields.
- Added path validation requirements for absolute paths and parent-directory traversal.
- Added result-file metadata and byte-budget constraints so downstream chat/coder consumers have a stable contract.
- Added stable machine-readable error codes for policy violations.

Status: PASS after fixes.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Narrowed the story to local execution contract and preflight policy checks; real gVisor/K8s enforcement remains downstream.
- Added explicit out-of-scope exclusions for M3.7, Story 4.B.2, and Story 4.B.6.
- Added a requirement that blocked P62 / network-disabled requests do not invoke the executor.
- Kept chat-service, critic-service, SDK flags, SSE streaming, and UI out of scope.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Added CI path-filter and sandbox-runner test job requirements.
- Added root workspace membership requirement so the service is installable and testable.
- Added validation commands for pytest, ruff, mypy, and diff check.
- Added workflow state requirements for ready-for-dev, in-progress, code-review, and done.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

1. Scaffold `apps/sandbox-runner` as a Python workspace service.
2. Implement P58 schemas, policy checks, local executor, and FastAPI endpoints.
3. Add tests for success and policy boundary failures.
4. Wire CI path filtering and sandbox-runner test job.
5. Run validation, perform post-implementation code review, patch findings, and move the story through workflow states.

### Debug Log References

- 2026-05-26 — Created Story M3.1 from Epic M3.1, architecture P58/P60 sandbox isolation, PRD FR N11 resource limits, and current placeholder `apps/sandbox-runner/.gitkeep`.
- 2026-05-26 — Started implementation after three story review rounds passed; sprint status moved to in-progress.
- 2026-05-26 — RED phase: `uv run pytest apps/sandbox-runner/tests -q` failed because `sandbox_runner` package did not exist yet.
- 2026-05-26 — GREEN phase: scaffolded sandbox-runner service, implemented P58/P62 local contract, added tests and CI; validation passed.
- 2026-05-26 — Code review found malformed `exit:` directives could raise a 500; patched local executor to return a stable failed response and added regression coverage.
- 2026-05-26 — Final validation after review fixes passed; story moved to done.

### Completion Notes List

- Created `apps/sandbox-runner` as a Python workspace service with FastAPI health and `/v1/sandbox/execute` endpoints.
- Implemented P58 local contract: bounded request schemas, stdout/stderr/exit-code/status response, result-file metadata, relative path enforcement, and result budget enforcement.
- Implemented P62 and network-disabled preflight checks with stable error codes `llm_self_loop_blocked`, `network_disabled`, `invalid_input_path`, and `result_budget_exceeded`.
- Kept scope local and deterministic: no Docker, gVisor, K8s, AppArmor, capability-drop, NetworkPolicy, chat integration, SSE streaming, or user-facing UI was added.
- Added targeted API tests and a path-filtered `sandbox-runner-test` CI job.
- Post-implementation code review patched malformed `exit:` handling so local contract execution returns `status="failed"` / `exit_code=1` instead of an unhandled 500.
- Validation passed: `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/sandbox-runner/tests -q` (`9 passed`); `uv run ruff check apps/sandbox-runner`; `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run mypy apps/sandbox-runner/src/sandbox_runner`; `git diff --check`.

### File List

Created:
- `_bmad-output/stories/m3-1-sandbox-io-pattern.md`
- `apps/sandbox-runner/pyproject.toml`
- `apps/sandbox-runner/src/sandbox_runner/__init__.py`
- `apps/sandbox-runner/src/sandbox_runner/executor.py`
- `apps/sandbox-runner/src/sandbox_runner/main.py`
- `apps/sandbox-runner/src/sandbox_runner/policy.py`
- `apps/sandbox-runner/src/sandbox_runner/schemas.py`
- `apps/sandbox-runner/tests/test_sandbox_runner_contract.py`

Modified:
- `.github/workflows/ci.yml`
- `_bmad-output/stories/sprint-status.yaml`
- `pyproject.toml`
- `uv.lock`

### Change Log

- 2026-05-26 — Created Story M3.1 and completed three story review rounds before implementation.
- 2026-05-26 — Started implementation and moved story to in-progress.
- 2026-05-26 — Implemented sandbox-runner local P58/P62 contract, tests, CI job, and workspace membership; moved story to code-review.
- 2026-05-26 — Code review patched malformed exit directive handling and prepared story for final done status after validation.
- 2026-05-26 — Final validation passed and story moved to done.

### Post-Implementation Code Review

Status: PASS after fixes.

Findings fixed:
- Medium — malformed `exit:` directives raised an unhandled `ValueError`, producing a 500 instead of a stable sandbox contract response. Patched `_parse_exit_code()` to map invalid or out-of-range values to `exit_code=1` with stderr, and added regression coverage.

Final validation:
- `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/sandbox-runner/tests -q` — `9 passed`.
- `uv run ruff check apps/sandbox-runner` — pass.
- `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run mypy apps/sandbox-runner/src/sandbox_runner` — pass.
- `git diff --check` — pass.
