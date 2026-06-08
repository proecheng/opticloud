# Story EVO.4: CI Python version lock hardening

Status: review

## Story

As a maintainer,
I want CI and repository Python version declarations to consistently use the locked Python 3.12 runtime,
so that `uv sync` does not drift to Python 3.11 or trigger transient hosted Python downloads during GitHub Actions validation.

## Problem Context

PR #184 for EVO.3 is blocked by `error-i18n-audit-validation`.
The job failed twice at `uv sync --all-packages --extra dev` while downloading `python-build-standalone` for CPython 3.11.10 from GitHub, returning `504 Gateway Timeout`.

Evidence:

- `.github/workflows/ci.yml` sets `PYTHON_VERSION: "3.12"`.
- `.github/workflows/e2e.yml` sets `PYTHON_VERSION: "3.12"`.
- `_bmad-output/planning/architecture.md` and `_bmad-output/planning/epics.md` define C6 as Python 3.12 locked through `.python-version`.
- Current root `.python-version` contains `3.11`.
- The failing log shows `actions/setup-python@v5` successfully installed CPython 3.12.13 before `uv sync` attempted to download CPython 3.11.10.

## Acceptance Criteria

1. Root `.python-version` matches the documented C6 lock: `3.12`.
2. GitHub Actions CI uses the already provisioned Python 3.12 interpreter for `uv` operations.
3. GitHub Actions CI does not auto-download a hosted Python interpreter during `uv sync`.
4. E2E workflow receives the same Python lock hardening as the main CI workflow.
5. Existing path filtering behavior remains unchanged except that root Python lock changes continue to trigger Python-related jobs.
6. EVO.3 web layout implementation is not changed by this hotfix.
7. Root Python lock changes trigger root/CI-level validation rather than only the `shared_py` filter.

## Scope

In scope:

- `.python-version`
- `.github/workflows/ci.yml`
- `.github/workflows/e2e.yml`
- BMAD story and sprint-status bookkeeping

Out of scope:

- Changing application behavior
- Changing Python dependency versions
- Changing `uv.lock`
- Broad CI refactors or job deduplication
- Altering EVO.3 frontend code

## Tasks / Subtasks

- [x] Create story and record root-cause evidence.
- [x] Run adversarial review round 1 for boundary and blast-radius issues, then revise.
- [x] Run adversarial review round 2 for drift and dependency consistency, then revise.
- [x] Run adversarial review round 3 for data consistency and closure, then revise.
- [x] Implement minimal CI/runtime lock changes.
- [x] Run local validation for changed files.
- [x] Perform post-implementation code review.
- [ ] Commit, push, and let GitHub CI re-run.

## Dev Notes

Use `UV_PYTHON=3.12` to make uv select the same interpreter family as `actions/setup-python`.
Use `UV_PYTHON_DOWNLOADS=never` to prevent uv from resolving a missing interpreter by downloading hosted Python in CI.

Do not rely only on `.python-version`; CI should be explicit because a future accidental edit to `.python-version` must fail fast instead of silently downloading another runtime.

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary and Blast Radius

Findings:

- A `.python-version`-only fix would be too weak because CI should fail fast if the runtime is missing instead of letting uv download another Python.
- Main CI and e2e both call `uv sync`; hardening only `.github/workflows/ci.yml` would leave the e2e workflow vulnerable to the same runtime drift.
- The e2e workflow push filter includes `.github/workflows/e2e.yml`, but the pull_request filter currently does not. Future PRs that only change the e2e workflow would not self-test the e2e workflow.
- The e2e workflow pull_request filter also omits `.python-version`; future Python lock changes could bypass e2e even though e2e installs Python dependencies.
- Application code must remain untouched; this story exists only to unblock CI/runtime consistency for PR #184.

Revision after round 1:

- Include `.github/workflows/e2e.yml` and `.python-version` in the e2e pull_request path filter.
- Keep implementation limited to workflow/runtime lock files and BMAD bookkeeping.
- Do not change EVO.3 frontend files.

### Round 2 - Drift and Dependency Consistency

Findings:

- `.python-version` currently contains `3.11`, directly contradicting C6 documentation and the CI `PYTHON_VERSION: "3.12"` environment.
- Because `requires-python = ">=3.11,<3.13"` allows both 3.11 and 3.12, dependency resolution alone will not catch this drift; the explicit version lock must be corrected.
- `.python-version` is currently included under the `shared_py` path filter, but not under `ci_or_root`. A future PR that changes only `.python-version` may skip governance validation jobs that still run Python and `uv sync`.
- `UV_PYTHON=3.12` without `UV_PYTHON_DOWNLOADS=never` would still permit uv to download a missing 3.12 interpreter if runner setup changes or fails.
- `UV_PYTHON_DOWNLOADS=never` without `UV_PYTHON=3.12` would fail fast, but the selected interpreter could still be ambiguous if a stale `.python-version` is reintroduced.
- Current uv documentation states that uv can download Python when a matching interpreter is missing, and that this can be disabled with `--no-python-downloads` / `UV_PYTHON_DOWNLOADS=never`.

Revision after round 2:

- Change root `.python-version` from `3.11` to `3.12`.
- Add `UV_PYTHON: "3.12"` and `UV_PYTHON_DOWNLOADS: "never"` to CI and e2e workflow env blocks.
- Add `.python-version` to the main CI `ci_or_root` filter so runtime lock changes exercise the full root/CI validation surface.

### Round 3 - Data Consistency and Closure

Findings:

- The root cause evidence must stay attached to the story, otherwise the 504 could be misclassified as a flaky external outage with no repository fix.
- The implementation must update both runtime data (`.python-version`) and workflow data (`env` plus filters); updating only one creates another future inconsistency.
- Local validation cannot fully reproduce GitHub Actions runner state, but it can verify the changed files parse, the lock value is `3.12`, and no frontend/application files are touched.
- CI closure requires pushing the hotfix to PR #184 and observing `error-i18n-audit-validation` rerun without the CPython 3.11.10 download failure.
- If CI still fails after this change, the next investigation must inspect the fresh log rather than assuming the old 504 cause.

Revision after round 3:

- Add local validation steps for workflow YAML parse, `.python-version` value, `git diff --check`, and PR check monitoring after push.
- Treat GitHub CI rerun as the final closure gate before merging PR #184.

## Dev Agent Record

### Debug Log

- Identified repeated CI failure in `error-i18n-audit-validation` as GitHub 504 during uv-managed CPython 3.11.10 download.
- Confirmed repository root `.python-version` currently contains `3.11` while CI and architecture specify Python 3.12.
- Updated root `.python-version` to `3.12`.
- Added `UV_PYTHON=3.12` and `UV_PYTHON_DOWNLOADS=never` to `.github/workflows/ci.yml` and `.github/workflows/e2e.yml`.
- Implementation review rejected `UV_NO_MANAGED_PYTHON=1` because the CI pin is `uv==0.5.4` and that environment variable is not supported until later uv versions.
- Added `.python-version` to the CI `ci_or_root` filter and to e2e PR/push path filters.
- Local validation passed: workflow YAML parsed via PyYAML, sprint status YAML parsed via PyYAML, `.python-version` value verified as `3.12`, and `git diff --check` passed.

### Completion Notes

- The CI runtime lock now aligns with C6: repository lock, main CI env, and e2e env all point at Python 3.12.
- uv automatic Python downloads are disabled in CI, so a future interpreter drift should fail fast instead of reaching GitHub-hosted CPython artifacts during `uv sync`.
- No application or EVO.3 frontend files were changed.

### File List

- `.github/workflows/ci.yml`
- `.github/workflows/e2e.yml`
- `.python-version`
- `_bmad-output/stories/evo-4-ci-python-version-lock.md`
- `_bmad-output/stories/sprint-status.yaml`

## Post-Implementation Code Review

Review date: 2026-06-08

Scope reviewed:

- `.python-version` lock value
- Main CI workflow global env and path filter changes
- E2E workflow global env and PR/push path filter changes
- BMAD story and sprint status consistency

Findings:

- Medium: `UV_NO_MANAGED_PYTHON=1` was initially added as a hardening variable, but current CI pins `uv==0.5.4`; that variable is not reliable for this pinned uv version. Fixed by removing it and relying on `UV_PYTHON=3.12` plus `UV_PYTHON_DOWNLOADS=never`.

Result:

- Approved after patch.
- Remaining risk: local Windows environment cannot fully reproduce GitHub-hosted runner Python discovery. GitHub Actions rerun remains the closure gate.

## Change Log

- 2026-06-08 - Initial story created for CI Python version lock hardening.
- 2026-06-08 - Implemented CI Python 3.12 runtime lock hardening and local static validation.
- 2026-06-08 - Completed post-implementation code review; removed unsupported uv hardening variable and approved the patch.
