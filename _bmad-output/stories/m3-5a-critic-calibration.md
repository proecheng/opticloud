# Story M3.5a: Critic 置信度校准工具 + 标注 SOP

Status: done

## Story

As an NFR-S / 数据标注 owner,
I want Critic 置信度校准工具、M3 30 条 ground truth 数据集、阈值配置输出和标注 SOP,
so that NFR-S8 的 Critic confidence < 0.6 自动标记/转人工规则有可重复、可审计、可扩展到 M5 200 条样本的工程依据。

## Acceptance Criteria

1. 校准输入数据集可提交、可验证、可扩展。
   - Add `tools/critic_calibration/ground_truth_v1.json` with exactly 30 M3 ground-truth samples.
   - Dataset root must be an object with `dataset_version`, `target_stage`, `policy`, and `samples`; `dataset_version` must be `ground_truth_v1` and `target_stage` must be `M3`.
   - Every sample must include stable `id`, `prompt`, `expected_escalate`, `critic_confidence`, `critic_reason_zh`, `category`, and `source_story`.
   - Sample IDs must be stable and unique, using the `critic-cal-v1-###` pattern.
   - `critic_confidence` must be numeric and in `[0, 1]`.
   - `expected_escalate=true` means the sample should be escalated by policy; `false` means it should not.
   - The dataset must include both positive/escalate and negative/non-escalate examples so false-positive behavior is measurable.
   - Category coverage must include at least `unsafe_code`, `schema_error`, `logic_error`, `sandbox_risk`, `benign`, and `low_risk_style`.
   - The M3 dataset is committed as curated seed data; M3.5b owns ongoing weekly sampling and expansion to at least 200 samples.

2. Offline calibration CLI is deterministic and dependency-light.
   - Add `tools/critic_calibration/calibrate.py`.
   - It must run with stdlib-only Python and no network, LLM credentials, database, Docker, Redis, or critic-service runtime.
   - It must accept `--dataset`, optional `--output`, and optional `--threshold-min/--threshold-max`.
   - It must compute confusion matrix counts using `predicted_escalate = critic_confidence < threshold`.
   - Metric formulas must be pinned: `recall = tp / (tp + fn)`, `false_positive_rate = fp / (fp + tn)`, `precision = tp / (tp + fp)`, `false_negative_rate = fn / (tp + fn)`.
   - `escalate_rate_on_expected_escalate` is an alias of recall; `false_escalate_rate_on_expected_non_escalate` is an alias of false positive rate.
   - Default recommended threshold must be constrained to `[0.55, 0.65]`.
   - The default threshold search must evaluate hundredth-step candidates from `0.55` through `0.65`, inclusive, and must include `0.60`.
   - It must prefer the threshold nearest `0.60` when multiple candidates satisfy the policy gates; ties must choose the lower threshold to reduce unnecessary escalation.
   - If no candidate satisfies recall >=95% and false-positive rate <=5%, the CLI must fail non-zero and explain which gate failed.
   - Threshold semantics must be explicit and tested: `critic_confidence < threshold` escalates.

3. Calibration output updates a committed critic configuration artifact.
   - Add `apps/critic-service/config/critic-calibration.json` as the handoff config for future critic-service runtime integration.
   - The config must include `recommended_threshold`, `threshold_range`, `sample_count`, `dataset_version`, `generated_from`, `metrics`, and `policy`.
   - Interpret the epic wording "Critic API 自动更新 config" as this offline CLI writing the committed config artifact; no runtime API mutation is implemented in M3.5a.
   - The CLI must write this config deterministically when `--output` is passed.
   - Deterministic JSON means `sort_keys=True`, two-space indentation, final newline, stable relative `generated_from`, and no wall-clock timestamps.
   - The config must not contain prompts, secrets, user data, credentials, or LLM provider responses.
   - This story must not implement a running critic API, human-review queue, Redis stream, SSE endpoint, or chat integration.

4. Quality gates enforce the G9 target.
   - Add tests covering the CLI, metric calculation, threshold bounds, config output shape, and data validation failures.
   - The committed M3 30-sample dataset must pass: escalate recall/rate on expected-escalate samples >=95%.
   - The committed M3 30-sample dataset must pass: false-escalate rate on expected-non-escalate samples <=5%.
   - Tests must prove the boundary behavior: confidence exactly equal to threshold does not escalate, while one point below threshold escalates.
   - Tests must include negative cases for missing fields, duplicate IDs, invalid confidence range, non-boolean labels, missing category coverage, empty class coverage, impossible metric gates, and threshold ranges outside `[0.55, 0.65]`.

5. SOP closes the human annotation loop.
   - Add `docs/critic-annotation-sop.md`.
   - SOP must name Critic Lead as owner and describe sample intake, dual annotation, adjudication, schema fields, quality checks, weekly M3.5b expansion, monthly calibration rerun, and config handoff.
   - SOP must state privacy/data rules: no raw user secrets, credentials, private datasets, or unredacted PII in committed ground truth.
   - SOP must define the M3 target (30 samples) and M5 target (200 samples).

6. CI runs the calibration gate when relevant files change.
   - Extend `.github/workflows/ci.yml` path filters with a `critic_calibration` output covering `tools/critic_calibration/**`, `docs/critic-annotation-sop.md`, `apps/critic-service/config/critic-calibration.json`, and the new tests.
   - Add `critic_calibration` to the `changes` job outputs and define a `critic-calibration-validation` job with condition `needs.changes.outputs.critic_calibration == 'true' || needs.changes.outputs.ci_or_root == 'true'`.
   - The CI job must run both the CLI smoke command and `uv run pytest tests/test_critic_calibration.py -v`.
   - Existing `critic_service` path filtering must remain intact.

7. Workflow tracking and boundaries are explicit.
   - This story records three pre-implementation story review rounds and fixes after each round.
   - `_bmad-output/stories/sprint-status.yaml` moves `m3-5a-critic-calibration` to `ready-for-dev` only after the three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.
   - No UI, API endpoint, LLM call, model training, active learning system, provider routing, or production human-review workflow is implemented in this story.

## Tasks / Subtasks

- [x] Create calibration dataset and schema expectations. (AC: 1, 4)
  - [x] Add 30 curated M3 ground-truth rows under `tools/critic_calibration/ground_truth_v1.json`.
  - [x] Use root metadata `dataset_version=ground_truth_v1`, `target_stage=M3`, and a `samples` array.
  - [x] Ensure the committed rows include at least one non-escalate class and enough expected-escalate rows to prove recall.
  - [x] Cover unsafe code, schema error, logic error, sandbox risk, benign, and low-risk style categories.
  - [x] Keep rows synthetic/redacted and avoid private user data.
- [x] Build offline calibration CLI. (AC: 2, 3, 4)
  - [x] Add stdlib-only loader and validator.
  - [x] Add confusion-matrix and rate calculations using `confidence < threshold`.
  - [x] Add deterministic hundredth-step threshold recommendation constrained to `[0.55, 0.65]`.
  - [x] Return non-zero for invalid data, invalid threshold range, or impossible recall/false-positive gates.
  - [x] Add deterministic JSON config output.
- [x] Add committed critic calibration config. (AC: 3)
  - [x] Add `apps/critic-service/config/critic-calibration.json`.
  - [x] Confirm it contains only aggregate metrics and policy metadata, not prompts.
- [x] Add tests and CI gate. (AC: 4, 6)
  - [x] Add `tests/test_critic_calibration.py`.
  - [x] Cover CLI success, negative validation cases, threshold equality behavior, threshold bounds, metric policy gates, and config shape.
  - [x] Add CI path filter output and `critic-calibration-validation` job.
  - [x] Ensure the job runs the CLI with `--dataset` and `--output` before pytest.
- [x] Add annotation SOP. (AC: 5)
  - [x] Add owner, annotation workflow, privacy rules, M3/M5 targets, rerun cadence, and handoff.
- [x] Update workflow records and validation evidence. (AC: 1-7)
  - [x] Move sprint status to `in-progress`, then `code-review`, then `done`.
  - [x] Update Dev Agent Record, File List, Change Log, and post-implementation review notes.
  - [x] Run focused tests, ruff, pre-commit, and `git diff --check`.

## Dev Notes

### Context

- PRD N9 requires Critic confidence `<0.6` to be flagged/escalated; N12 requires users can see confidence and bilingual reasoning later.
- PRD NFR Security 2.3 sets the calibration plan: M3 uses 30 ground-truth samples, M5 uses 200, and threshold can be adjusted dynamically.
- Architecture G9 is the critical gap for Critic confidence calibration ground truth, with required tooling, SOP, and validation strategy.
- `apps/critic-service/` currently contains only `.gitkeep`; this story must not pretend a production critic runtime exists.
- M3.4 and M3.4b already shipped the shared AIGC filter package and contract test gate; this story is independent and should not modify AIGC filter behavior.

### Scope Decision

- The M3.5a artifact is an offline calibration handoff, not a service feature.
- The committed dataset represents Critic output scores and labels from curated synthetic/edge prompts. It is intentionally small and deterministic.
- The future critic-service runtime can consume `apps/critic-service/config/critic-calibration.json`; this story only creates and validates the config artifact.
- The epics phrase "Critic API 自动更新 config" is implemented as deterministic file generation because `critic-service` runtime does not exist yet.
- M3.5b owns ongoing weekly annotation, Linear ticket tracking, and monthly expansion; this story only documents that loop in SOP.

### Architecture / External Constraints

- Use only Python stdlib for the CLI.
- Keep all tests offline and deterministic.
- Do not add a new package dependency or a new workspace member for `tools/critic_calibration`.
- Do not require `PYTHONPATH` for CLI execution; tests can import the script by file path.
- Keep config and reports free of prompts to reduce leakage risk.
- Avoid wall-clock timestamps in generated config; otherwise committed config diffs will be nondeterministic.

### Project Structure Notes

- Add new directory `tools/critic_calibration/`.
- Add config directory `apps/critic-service/config/`.
- Add doc `docs/critic-annotation-sop.md`.
- Add repo-level tests under `tests/`, matching existing static validation stories.
- Extend `.github/workflows/ci.yml` with a path-filtered validation job.
- Keep `apps/critic-service/**` in the existing `critic_service` filter; add calibration paths to a separate filter so config-only changes do not imply a runtime service test.

### Testing / Validation Notes

- Expected local commands:
  - `uv run python tools/critic_calibration/calibrate.py --dataset tools/critic_calibration/ground_truth_v1.json --output apps/critic-service/config/critic-calibration.json`
  - `uv run pytest tests/test_critic_calibration.py -q`
  - `uv run ruff check tools/critic_calibration tests/test_critic_calibration.py`
  - `uv run ruff format --check tools/critic_calibration tests/test_critic_calibration.py`
  - `uv run pre-commit run --all-files --show-diff-on-failure`
  - `git diff --check`

### Risks / Decisions

- Data consistency risk: dataset rows and generated config can drift. Tests must compare committed config against CLI output.
- Function consistency risk: threshold semantics can invert accidentally. Tests must pin `confidence < threshold` as escalation.
- Metric drift risk: a later refactor could rename or redefine recall/false-positive gates. Keep formulas and alias metrics explicit in tests.
- Drift risk: a later runtime may use a different threshold than the config. This story creates the handoff artifact; consumer stories must add runtime contract tests.
- Boundary risk: building critic-service now would overload this story. Keep runtime integration out of scope.
- Closure risk: path filters may not run tests when calibration files change. Add a dedicated filter and job.

### References

- `_bmad-output/planning/epics.md:1141` — Story M3.5a requirements.
- `_bmad-output/planning/epics.md:1154` — M3.5b ongoing annotation scope.
- `_bmad-output/planning/epics.md:2004` — SC4 owner/SOP requirement.
- `_bmad-output/planning/prd.md:1494` — FR N9 Critic confidence escalation.
- `_bmad-output/planning/prd.md:1497` — FR N12 confidence score and reasoning.
- `_bmad-output/planning/prd.md:1640` — M3 30 / M5 200 threshold calibration rule.
- `_bmad-output/planning/architecture.md:414` — M3.5a architecture entry.
- `_bmad-output/planning/architecture.md:2005` — G9 critical gap.
- `_bmad-output/planning/architecture.md:2117` — simplified edition keeps fixed 0.6 and is out of G9 dynamic calibration scope.
- `_bmad-output/stories/m3-4b-aigc-filter-contract-test.md` — recent story/review/test workflow precedent.

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Added dataset root metadata (`dataset_version`, `target_stage`, `policy`, `samples`) so the 30-row artifact has a stable versioned shape rather than being only an array.
- Added unique ID pattern and category coverage requirements so M3 data can be audited and expanded by M3.5b without ambiguity.
- Clarified that the epics wording "Critic API 自动更新 config" maps to deterministic offline config-file generation because `apps/critic-service` has no runtime yet.
- Added duplicate-ID and missing-category negative tests to close data consistency gaps.

Status: PASS after fixes.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Corrected the sample ID pattern to `critic-cal-v1-###` before implementation to avoid committing a misspelled data contract.
- Added exact confusion-matrix formulas and alias metric definitions so implementation cannot silently reinterpret "escalate rate" or "误 escalate".
- Pinned threshold search to inclusive hundredth steps, nearest-to-0.60 tie-breaking, and non-zero failure when no candidate satisfies gates.
- Added threshold equality tests because the policy is strictly `< threshold`, not `<= threshold`.
- Required deterministic JSON output details and no timestamps so committed config can be compared byte-for-byte against CLI output.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Clarified the CI `changes` output name and the exact `critic-calibration-validation` job condition so path filtering closes over all new artifacts.
- Required the CI job to run both a CLI smoke command and pytest, preventing a test-only gate that never proves config generation works.
- Added explicit guidance to keep `critic_service` path filtering intact and separate from calibration-only validation.
- Confirmed runtime surfaces remain out of scope: no API endpoint, Redis stream, SSE, chat integration, model training, or production human-review workflow.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

1. Move sprint status to `ready-for-dev`, then `in-progress`.
2. Add stdlib-only calibration CLI, 30-row dataset, generated critic config, tests, SOP, and CI job.
3. Run focused validation and perform post-implementation code review.
4. Patch review findings, rerun gates, mark done, commit, push, open PR, wait for CI, merge, and sync.

### Debug Log References

- 2026-05-26 — Created initial M3.5a story draft from sprint backlog after PR #61 merged.
- 2026-05-26 — Completed story review round 1 and patched dataset/config consistency requirements.
- 2026-05-26 — Completed story review round 2 and patched threshold/metric determinism requirements.
- 2026-05-26 — Completed story review round 3 and patched CI/scope closure requirements.
- 2026-05-26 — Started implementation; sprint status moved to in-progress.
- 2026-05-26 — RED phase passed: `uv run pytest tests/test_critic_calibration.py -q` failed because the CLI, dataset, and config did not exist.
- 2026-05-26 — Added stdlib-only calibration CLI, versioned 30-sample ground-truth dataset, and committed aggregate critic config.
- 2026-05-26 — Added Chinese annotation SOP with owner, dual annotation, adjudication, privacy rules, M3/M5 targets, weekly expansion, and monthly rerun handoff.
- 2026-05-26 — Added `critic_calibration` CI path filter and `critic-calibration-validation` job running CLI smoke generation plus pytest.
- 2026-05-26 — Validation passed: `uv run pytest tests/test_critic_calibration.py -q` (12 passed).
- 2026-05-26 — Validation passed: `uv run python tools/critic_calibration/calibrate.py --dataset tools/critic_calibration/ground_truth_v1.json --output apps/critic-service/config/critic-calibration.json`.
- 2026-05-26 — Validation passed: `$env:PYTHONPATH='apps/auth-service/src;packages/shared-py'; uv run pytest tests -q` (63 passed).
- 2026-05-26 — Validation passed: `uv run mypy tools/critic_calibration/calibrate.py`.
- 2026-05-26 — Validation passed: `uv run ruff check tools/critic_calibration tests/test_critic_calibration.py`.
- 2026-05-26 — Validation passed: `uv run pre-commit run --all-files --show-diff-on-failure`.
- 2026-05-26 — Post-implementation code review found and fixed one CI drift risk: the CI job generated config into the committed path before pytest, which could hide committed config drift. It now writes to `/tmp/critic-calibration.json`, and tests explicitly compare runtime output to the committed config.
- 2026-05-26 — Post-review hardening added threshold hundredth-step validation and drift-detection tests.
- 2026-05-26 — Validation passed after review patch: `uv run pytest tests/test_critic_calibration.py -q` (14 passed).
- 2026-05-26 — Validation passed after review patch: `uv run ruff check tools/critic_calibration tests/test_critic_calibration.py`.
- 2026-05-26 — Validation passed after review patch: `uv run mypy tools/critic_calibration/calibrate.py`.
- 2026-05-26 — Validation passed after review patch: `uv run pre-commit run check-yaml --files .github/workflows/ci.yml`.
- 2026-05-26 — Final validation passed: `uv run python tools/critic_calibration/calibrate.py --dataset tools/critic_calibration/ground_truth_v1.json --output apps/critic-service/config/critic-calibration.json`.
- 2026-05-26 — Final validation passed: `$env:PYTHONPATH='apps/auth-service/src;packages/shared-py'; uv run pytest tests -q` (65 passed).
- 2026-05-26 — Final validation passed: `uv run ruff format --check tools/critic_calibration tests/test_critic_calibration.py`.
- 2026-05-26 — Final validation passed: `git diff --check`.
- 2026-05-26 — Final validation passed: `uv run pre-commit run --all-files --show-diff-on-failure`.

### Completion Notes List

- Added `tools/critic_calibration/calibrate.py`, a stdlib-only offline calibration CLI that validates dataset shape, computes pinned confusion-matrix metrics, selects a deterministic threshold in `[0.55, 0.65]`, and writes deterministic aggregate JSON config.
- Added `ground_truth_v1` with exactly 30 synthetic/redacted M3 samples across required categories; at threshold 0.60 it produces 20 TP, 10 TN, 0 FP, 0 FN.
- Added committed critic-service handoff config with only aggregate metrics/policy metadata and no prompt text or timestamps.
- Added calibration regression tests covering CLI generation, strict threshold boundary, metric gates, config shape, and validation failures.
- Added `docs/critic-annotation-sop.md` and CI validation wiring.

### Post-Implementation Code Review (AI)

Outcome: PASS after fixes.

Findings fixed:
- CI drift risk: `critic-calibration-validation` generated the config into `apps/critic-service/config/critic-calibration.json` before running pytest, so a PR with a stale committed config could be masked by CI. Fixed by generating to `/tmp/critic-calibration.json` in CI and keeping pytest responsible for committed-config parity.
- Test drift risk: parity was only covered by the CLI temp-output comparison. Added an explicit committed-config drift test that compares runtime calibration output with the committed config and proves a changed threshold would differ.
- Threshold drift risk: sub-hundredth threshold bounds could be rounded into a different search grid. Added hundredth-step validation and a negative test.

### File List

- `_bmad-output/stories/m3-5a-critic-calibration.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `apps/critic-service/config/critic-calibration.json`
- `docs/critic-annotation-sop.md`
- `tests/test_critic_calibration.py`
- `tools/critic_calibration/calibrate.py`
- `tools/critic_calibration/ground_truth_v1.json`

### Change Log

- 2026-05-26 — Created initial story draft.
- 2026-05-26 — Round 1 data consistency review fixes applied.
- 2026-05-26 — Round 2 function consistency and drift review fixes applied.
- 2026-05-26 — Round 3 boundary and closure review fixes applied; story ready for development.
- 2026-05-26 — Implemented calibration CLI, dataset, config, SOP, tests, and CI validation gate.
- 2026-05-26 — Code review fixes applied for CI config drift masking and threshold-grid validation.
