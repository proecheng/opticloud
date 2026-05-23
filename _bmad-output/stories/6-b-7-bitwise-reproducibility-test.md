# Story 6.B.7: Voucher Bitwise Reproducibility Test Framework

Status: done

## Story

As a platform operator protecting academic reproducibility promises,
I want a quarterly bitwise reproducibility audit framework for issued vouchers,
so that we can prove sampled voucher reruns still reproduce the stored result exactly and detect regressions before users or reviewers do.

## Acceptance Criteria

1. A side-effect-light audit framework can sample issued vouchers for bitwise rerun checks.
   - Add a solver-orchestrator utility module for voucher reproducibility audits.
   - The framework selects from `reproduction_vouchers` joined to the source `optimizations` row.
   - Eligible vouchers must have `status='issued'`, a source optimization with `status='completed'`, and a current 5-year rerun window based on `reproduction_vouchers.created_at` UTC.
   - The default sampling policy is quarterly 5% sampling.
   - Sample size is `ceil(eligible_count * sample_rate)` with a minimum of one when eligible vouchers exist and sample rate is greater than zero.
   - The CLI must reject sample rates outside `[0, 1]`.
   - Sampling must be deterministic for the same population, seed, sample rate, and as-of timestamp.
   - The current implementation may execute only supported LP / `highs` vouchers; unsupported task types or locked solvers are recorded as skipped, not silently ignored.
   - Expired, revoked, missing-source, and non-completed-source vouchers are ineligible and must be counted separately from executable skipped samples.

2. The bitwise check compares stored source results against a fresh deterministic solve.
   - Rebuild the rerun payload from the source `Optimization.input_payload` after removing `_system` metadata.
   - Reuse the locked solver and locked model version recorded on the voucher.
   - For current LP support, run through the existing solver path rather than a new solver abstraction.
   - Compare a canonical JSON representation of the stored result against the fresh result.
   - The canonical digest input must include only deterministic result fields: solver status, objective, solution, and locked model version.
   - The canonical digest input must exclude `solve_seconds`, created / completed timestamps, voucher ID, optimization ID, user ID, API key ID, idempotency key, and any `_system` metadata.
   - The comparison is strict: no numeric tolerance is accepted for a `passed` result.
   - Store and report expected / observed SHA-256 digests so failures can be investigated without dumping raw inputs or full solver outputs.

3. The audit is operationally runnable without creating user-facing side effects.
   - Add a CLI runner similar to the existing citation tracker CLI.
   - The CLI writes JSON output and optional Markdown output.
   - Default JSON output path is `_bmad-output/reports/repro-bitwise/latest.json`.
   - Default Markdown output path, when requested, is `_bmad-output/reports/repro-bitwise/latest.md`.
   - Generated reports are runtime artifacts and should not be committed unless a later evidence story explicitly asks for committed snapshots.
   - The CLI prints one machine-readable JSON summary to stdout.
   - The CLI returns non-zero when an audit execution has failed checks, executable coverage is below the threshold, or configuration is invalid.
   - A run with zero eligible vouchers exits 0 and reports `status="no_eligible_vouchers"`, not pass or fail.
   - A run with sampled vouchers but zero executable samples exits 1 and reports `status="insufficient_executable_coverage"`.
   - Running the audit must not create new `optimizations`, `reproduction_vouchers`, `idempotency_keys`, billing records, or child vouchers.
   - Do not call `POST /v1/reproduce/{voucher_id}/rerun` from the audit path.
   - The CLI owns its SQLAlchemy engine/session lifecycle, following the existing billing reconciler / citation tracker CLI pattern.

4. Reports are useful for quarterly evidence without exposing sensitive data.
   - The JSON report includes generated time, as-of time, sample policy, eligible count, sampled count, pass / fail / skip counts, pass rate, threshold, and per-sample results.
   - Per-sample results include voucher ID, optimization ID, task type, locked solver, rerun depth, status, reason, and digests.
   - Reports must not include raw optimization input, raw solver output, API key IDs, user IDs, phone, email, legal name, or billing identifiers.
   - Markdown output summarizes the same counts and lists failed/skipped samples with reasons.
   - A pass-rate threshold defaults to 95%, matching the PRD reproducibility validation target.
   - Pass rate is `passed / (passed + failed)` and excludes skipped samples.
   - Executable coverage is `(passed + failed) / sampled_count`; it must also meet the same default 95% threshold unless the operator explicitly overrides it.
   - The overall report status is one of `passed`, `failed`, `no_eligible_vouchers`, or `insufficient_executable_coverage`.

5. Scope stays inside audit tooling and documentation.
   - Do not add a public voucher lookup endpoint.
   - Do not add a new user-facing API, UI, scheduler, or background worker.
   - Do not add a GitHub Actions schedule, cron automation, Kubernetes CronJob, or Linear automation in this story.
   - Do not scaffold `apps/repro-service`.
   - Do not implement S3 / Glacier restore, image archival indexing, provider auto-migration, or provider exit notification.
   - Do not change normal voucher issuance, rerun idempotency, anonymous voucher inheritance, 5-year SLA wording, or VoucherCard behavior.

6. Tests prove selection, strict comparison, reporting, and no-side-effect behavior.
   - Unit tests cover deterministic sampling, canonical digest equality, digest mismatch, and report rendering.
   - Integration tests seed issued / revoked / expired / unsupported vouchers and assert only eligible supported samples execute.
   - Integration tests assert row counts for `optimizations`, `reproduction_vouchers`, and `idempotency_keys` are unchanged after the audit.
   - CLI tests write JSON and Markdown reports to temporary paths and verify stdout summary shape.
   - Regression tests assert reports do not contain raw payloads or owner identifiers.
   - Run solver-orchestrator tests, mypy, and `git diff --check`.

7. Story workflow tracking is updated.
   - This story records all three story review rounds and the modifications made after each round.
   - `_bmad-output/stories/sprint-status.yaml` moves `6-b-7-bitwise-reproducibility-test` to `ready-for-dev` only after the three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.

## Tasks / Subtasks

- [x] Build the audit utility module. (AC: 1, 2, 4)
  - [x] Add a `solver_orchestrator` module for selecting voucher samples and running bitwise checks.
  - [x] Implement deterministic sample selection from eligible voucher rows.
  - [x] Rebuild clean solver payloads by removing `_system` metadata from source optimization payloads.
  - [x] Implement canonical digest helpers that include only deterministic result fields.
  - [x] Compare canonical JSON result digests with strict equality.
  - [x] Model per-sample statuses as `passed`, `failed`, and `skipped`.
- [x] Add the CLI runner. (AC: 3, 4)
  - [x] Add a CLI entry module with arguments for sample rate, seed, as-of timestamp, JSON output, and optional Markdown output.
  - [x] Validate sample rate and pass / executable coverage thresholds.
  - [x] Emit a single JSON summary to stdout.
  - [x] Write JSON and Markdown reports without raw inputs or owner identifiers.
- [x] Add documentation for quarterly operation. (AC: 3, 4, 5)
  - [x] Add `docs/runbooks/repro-bitwise-audit.md`.
  - [x] Link it from `docs/runbooks/README.md`.
  - [x] Keep the existing Repro Image Restore SOP focused on archive restore; cross-link it only where image restore is relevant to a future audit failure.
  - [x] Document current LP-only support and skipped status handling.
  - [x] Document how to interpret pass rate, skipped rows, and failures.
- [x] Add regression tests. (AC: 1, 2, 3, 4, 6)
  - [x] Test deterministic sampling and minimum-one behavior.
  - [x] Test strict digest pass / fail outcomes.
  - [x] Test unsupported task types and locked solvers are recorded as skipped.
  - [x] Test expired / revoked / missing source rows are not executed as passing samples.
  - [x] Test CLI report output and stdout summary.
  - [x] Test no new optimization, voucher, or idempotency rows are written.
- [x] Update workflow records and validation evidence. (AC: 7)
  - [x] Complete three story review rounds before implementation.
  - [x] Update Dev Agent Record, File List, Change Log, and post-implementation review notes.
  - [x] Run targeted tests, broader solver tests as feasible, mypy, and `git diff --check`.

## Dev Notes

### Context

- Story 6.B.1 added opt-in reproducibility handoff under `Optimization.input_payload._system.reproducibility`.
- Story 6.B.2 added durable `reproduction_vouchers` and voucher ID issuance for authenticated reproducible LP runs.
- Story 6.B.3 added `POST /v1/reproduce/{voucher_id}/rerun`, child voucher lineage, owner-scoped idempotency, and the UTC calendar-year 5-year window.
- Story 6.B.4 added anonymous voucher persistence and rerun inheritance.
- Story 6.B.5 added the UI `VoucherCard` and `/console/repro` fixture dashboard.
- Story 6.B.6 defined the 5-year SLA clock as `reproduction_vouchers.created_at` UTC and added the archive restore SOP.
- Story 6.B.7 comes from Expert Panel E11 in the epics file. This is not Excel FR E11; it is the solver-scholar decision item for quarterly voucher bitwise testing.

### Scope Decision

- Treat this as an internal audit/test framework, not a new customer API.
- Prefer a side-effect-light utility plus CLI, following the Story 6.A.3 citation tracker pattern.
- The audit should re-solve from the source optimization payload directly and compare canonical result digests. It must not call the user-facing rerun endpoint because that endpoint creates child vouchers by design.
- Current live execution support is LP / `highs`. Unsupported future task types should be explicit `skipped` results with reasons, not false passes.
- Keep the G7 image archive dependency out of this implementation. This story validates deterministic result reproduction for the current live solver path; image restore remains governed by the Story 6.B.6 runbook.

### Relevant Source Anchors

- Epic source: `_bmad-output/planning/epics.md`, Expert Panel E11 and Story 6.B.7 summary.
- PRD reproducibility validation target: `_bmad-output/planning/prd.md`, Core Innovation #2, quarterly sampled rerun success rate target.
- UX metric: `_bmad-output/planning/ux-design-specification.md`, ML5 First Repro Voucher 5y test, quarterly 5% sample.
- Architecture G7 dependency: `_bmad-output/planning/architecture.md`, G7 image archival and Repro 5y SLA engineering sections.
- Existing voucher helpers: `apps/solver-orchestrator/src/solver_orchestrator/repro.py`.
- Existing rerun route and calendar helpers: `apps/solver-orchestrator/src/solver_orchestrator/routes.py`.
- Existing ORM models: `apps/solver-orchestrator/src/solver_orchestrator/models.py`.
- Existing solver wrapper: `apps/solver-orchestrator/src/solver_orchestrator/solvers.py`.
- Existing citation tracker utility / CLI pattern: `apps/solver-orchestrator/src/solver_orchestrator/citation_tracker.py` and `citation_tracker_cli.py`.
- Existing voucher tests: `apps/solver-orchestrator/tests/test_reproduction_vouchers.py` and `test_reproduction_rerun.py`.

### Project Structure Notes

- Place new backend audit code under `apps/solver-orchestrator/src/solver_orchestrator/`.
- Place new backend tests under `apps/solver-orchestrator/tests/`.
- If adding a runbook, prefer `docs/runbooks/` and link it from `docs/runbooks/README.md`.
- The runbook for this story should be `docs/runbooks/repro-bitwise-audit.md`; do not fold the main operating steps into `repro-image-restore.md`.
- Do not import private helper functions from `solver_orchestrator.routes` into the audit module.
- If calendar-window or `_system` stripping logic must be shared, either implement a narrow local helper in the audit module or move the helper into `solver_orchestrator.repro` and update routes without changing route behavior.
- Use existing `solvers.solve_from_request()` for LP execution and pass the original payload's `options.max_solve_seconds` through the existing `OptimizationRequest` validation path.
- There is no Alembic migration flow in this repo. This story should not need schema changes.

### Testing / Validation Notes

- Local Windows commands usually need:
  - `$env:PYTHONPATH='D:\优化预测网站-6-b-7-bitwise-reproducibility-test\apps\solver-orchestrator\src;D:\优化预测网站-6-b-7-bitwise-reproducibility-test\packages\shared-py'`
  - `uv run pytest apps/solver-orchestrator/tests/ -q`
- Fresh worktrees may need `uv sync --all-packages --extra dev`.
- Run `uv run mypy apps packages`.
- Run `git diff --check`.
- Prefer deterministic tests that seed their own vouchers and write reports only to `tmp_path`.

### Risks / Decisions

- A naive implementation that calls the rerun endpoint would create child vouchers and distort audit evidence. Do not do that.
- A tolerance-based numeric comparison would not satisfy "bitwise"; use strict canonical digest equality.
- A report that includes raw payloads would leak customer data. Keep reports hash- and pointer-based.
- Empty populations should be reported as no eligible vouchers rather than fabricated passes.
- Unsupported future solver/task rows should be visible as skipped so the quarterly evidence shows coverage gaps.

## Story Review Log

### Round 1: Requirements Completeness Review

Findings fixed:
- Added the precise sample-size formula: `ceil(eligible_count * sample_rate)` with minimum one when eligible rows exist and sample rate is greater than zero.
- Clarified that expired, revoked, missing-source, and non-completed-source vouchers are ineligible, while unsupported task / solver rows selected into the sample become explicit `skipped` samples.
- Defined pass-rate and executable-coverage denominators so skipped samples cannot hide missing audit coverage.
- Added zero-eligible and zero-executable report / exit-code behavior.

Status: PASS after fixes.

### Round 2: Architecture / Testability Review

Findings fixed:
- Added canonical digest field rules so implementation cannot accidentally include nondeterministic `solve_seconds` or timestamps in a bitwise comparison.
- Added an explicit rule that the audit module must not import private helpers from `solver_orchestrator.routes`; shared logic should live locally or move narrowly into `solver_orchestrator.repro`.
- Added CLI session lifecycle guidance based on existing solver-orchestrator CLI patterns.
- Added the requirement to validate payloads through `OptimizationRequest` and run LP through existing `solvers.solve_from_request()`.

Status: PASS after fixes.

### Round 3: Acceptance / Scope Audit

Findings fixed:
- Added default JSON / Markdown report paths under `_bmad-output/reports/repro-bitwise/` and clarified generated reports are runtime artifacts, not committed evidence snapshots.
- Added an explicit runbook target, `docs/runbooks/repro-bitwise-audit.md`, and a required link from the runbooks index.
- Kept `repro-image-restore.md` focused on archive restore, with only cross-links allowed where future image restore affects audit failures.
- Explicitly excluded scheduler, cron, GitHub Actions schedule, Kubernetes CronJob, Linear automation, and repro-service scaffolding.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

1. Add `solver_orchestrator.repro_bitwise_audit` with deterministic sampling, canonical digesting, and side-effect-free LP rerun checks.
2. Add `solver_orchestrator.repro_bitwise_audit_cli` with JSON / Markdown report output and exit-code handling.
3. Add `docs/runbooks/repro-bitwise-audit.md` and link it from the runbooks index.
4. Add unit, integration, CLI, and report-redaction tests.
5. Run solver tests, mypy, and `git diff --check`; then move to code review.

### Debug Log References

- 2026-05-22 — Created Story 6.B.7 draft from Epic 6.B, Expert Panel E11, PRD Core Innovation #2, UX ML5, and existing 6.B.1-6.B.6 implementation notes.
- 2026-05-22 — Fresh worktree `.venv` lacked `highspy`; ran `uv sync --all-packages --extra dev`, then target tests collected and ran.

### Completion Notes List

- Added side-effect-free voucher bitwise audit utilities with deterministic quarterly sampling, strict canonical digest comparison, explicit skipped coverage, and no raw payload/report leakage.
- Added CLI runner `solver_orchestrator.repro_bitwise_audit_cli` with JSON / optional Markdown output, machine-readable stdout summary, sample/threshold validation, and defined exit codes.
- Added `docs/runbooks/repro-bitwise-audit.md` and linked it from the runbooks index without changing the archive restore SOP scope.
- Added unit, integration, CLI, no-side-effect, and redaction-oriented tests for the audit framework.
- Validation passed: ruff audit files clean; target audit tests `10 passed`; solver-orchestrator suite `116 passed`; mypy `Success: no issues found in 67 source files`; `git diff --check` passed.

### File List

Created:
- `_bmad-output/stories/6-b-7-bitwise-reproducibility-test.md`
- `apps/solver-orchestrator/src/solver_orchestrator/repro_bitwise_audit.py`
- `apps/solver-orchestrator/src/solver_orchestrator/repro_bitwise_audit_cli.py`
- `apps/solver-orchestrator/tests/test_repro_bitwise_audit.py`
- `docs/runbooks/repro-bitwise-audit.md`

Modified:
- `.gitignore`
- `_bmad-output/stories/sprint-status.yaml`
- `docs/runbooks/README.md`

### Change Log

- 2026-05-22 — Created initial Story 6.B.7 draft for review.
- 2026-05-22 — Completed three story review rounds and applied fixes before implementation.
- 2026-05-22 — Implemented voucher bitwise audit utility, CLI, runbook, and regression coverage; moved story to code review.
- 2026-05-22 — Completed post-implementation code review, ignored generated repro-bitwise report artifacts, reran validation, and moved story to done.

### Post-Implementation Code Review

Status: PASS after fixes.

Findings fixed:
- Replaced hardcoded local worktree text in the runbook command with `$PWD` so the SOP works from any checkout path.
- Added report redaction coverage for JSON output and asserted non-completed-source vouchers are counted separately from executable skipped samples.
- Added `_bmad-output/reports/repro-bitwise/` to `.gitignore` so generated quarterly audit reports remain runtime artifacts unless a later evidence story explicitly commits snapshots.

Validation evidence:
- `uv run ruff check apps/solver-orchestrator/src/solver_orchestrator/repro_bitwise_audit.py apps/solver-orchestrator/src/solver_orchestrator/repro_bitwise_audit_cli.py apps/solver-orchestrator/tests/test_repro_bitwise_audit.py` — pass.
- `uv run pytest apps/solver-orchestrator/tests/test_repro_bitwise_audit.py -q` — `10 passed`.
- `uv run pytest apps/solver-orchestrator/tests/ -q` — `116 passed, 9 warnings`.
- `uv run mypy apps packages` — `Success: no issues found in 67 source files`.
- `git diff --check` — pass.
