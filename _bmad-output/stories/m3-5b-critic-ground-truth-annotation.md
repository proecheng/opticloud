# Story M3.5b: Critic ground truth 持续标注

Status: done

## Story

As a 数据标注 lead,
I want 每周约 20 条 Critic ground truth 持续标注流程、Linear ticket payload 跟踪、内部标注页面和月度 calibration 重跑证据,
so that Critic 红队测试集能从 M3 的 30 条持续扩展到 M5 至少 200 条，并形成可审计的 G9 闭环。

## Acceptance Criteria

1. 持续标注数据集可扩展、可审计、可校准。
   - Extend `tools/critic_calibration/ground_truth_v1.json` from 30 to exactly 50 samples for this story, representing one weekly batch of 20 adjudicated samples.
   - Preserve the existing root object shape: `dataset_version`, `target_stage`, `policy`, and `samples`.
   - Keep `dataset_version=ground_truth_v1` and update `target_stage` to `M3.5b`.
   - Preserve all existing IDs `critic-cal-v1-001` through `critic-cal-v1-030` without renumbering or semantic rewrites.
   - Add new stable IDs `critic-cal-v1-031` through `critic-cal-v1-050`.
   - Every new sample must keep the M3.5a fields: `id`, `prompt`, `expected_escalate`, `critic_confidence`, `critic_reason_zh`, `category`, and `source_story`.
   - Every new M3.5b sample must also include `llm_output_excerpt`, a short synthetic or redacted model-output excerpt used only for annotation tickets. Existing M3 samples may omit this field for backward compatibility.
   - New sample `source_story` values must be `M3.5b`.
   - All samples, prompts, and `llm_output_excerpt` values must remain synthetic or redacted and must not contain raw user secrets, credentials, private datasets, production tenant identifiers, unredacted PII, or full provider response payloads.
   - Category coverage must still include at least `unsafe_code`, `schema_error`, `logic_error`, `sandbox_risk`, `benign`, and `low_risk_style`, with at least two new samples in each existing category so weekly intake is not one-class biased.

2. Calibration CLI supports the M3.5b expanded dataset without weakening G9 policy gates.
   - Update `tools/critic_calibration/calibrate.py` so validation accepts both M3 30-sample and M3.5b 50-sample targets while still rejecting unexpected sample counts.
   - Validation must explicitly bind target stage to count: `target_stage=M3` requires exactly 30 samples; `target_stage=M3.5b` requires exactly 50 samples.
   - Validation must require `llm_output_excerpt` only for samples whose `source_story` is `M3.5b`; older M3 rows remain valid without that field.
   - Validation must reject `llm_output_excerpt` values that are empty, too long for review, or contain obvious credential/token markers.
   - Keep threshold semantics unchanged: `predicted_escalate = critic_confidence < threshold`.
   - Keep metric formulas and policy gates unchanged: recall >=95%, false-positive rate <=5%, recommended threshold in `[0.55, 0.65]`, hundredth-step grid, nearest-to-0.60 then lower tie-break.
   - Regenerate `apps/critic-service/config/critic-calibration.json` from the expanded dataset.
   - The committed config must show `sample_count=50`, `target_stage=M3.5b`, and only aggregate metadata; it must not include prompt text or `critic_reason_zh`.
   - Existing M3.5a drift checks must keep comparing committed config with runtime calibration output.

3. Weekly Linear ticket payload generation is deterministic and credential-free.
   - Add `tools/critic_calibration/create_annotation_batch.py`.
   - It must run stdlib-only, offline, and without Linear credentials, network, database, Docker, Redis, or critic-service runtime.
   - It must accept `batch --dataset`, `--week-start`, optional `--count` defaulting to 20, and optional `--output` if implemented as a multi-command CLI; if implemented as a single-purpose `create_annotation_batch.py`, it must accept `--dataset`, `--week-start`, optional `--count`, and optional `--output`.
   - It must import or reuse validation/constants from `calibrate.py` instead of reimplementing dataset schema rules.
   - `--week-start` must be a Monday in ISO `YYYY-MM-DD` format; reject non-Monday dates and invalid dates.
   - It must select the newest `count` samples by numeric sample ID, fail if there are fewer than `count` samples for the requested batch, and generate deterministic ticket payloads for Linear epic `OPTI-CRITIC-ANNOT`.
   - It must fail closed when the newest `count` samples are not all from `source_story=M3.5b`.
   - Output JSON must include batch metadata: `epic_key`, `week_start`, `due_date` exactly 7 calendar days later, `sample_count`, `ticket_prefix`, and `tickets`.
   - The committed batch must contain exactly the new weekly sample IDs `critic-cal-v1-031` through `critic-cal-v1-050`, with no duplicates and no references to missing dataset rows.
   - Each ticket must include a deterministic key like `OPTI-CRITIC-ANNOT-20260525-001`, sample ID, prompt, `llm_output_excerpt`, category, expected label, critic confidence, annotation UI path `/console/critic-annotation?sample=<id>`, due date, and status `todo`.
   - The generated file path for the committed batch must be `tools/critic_calibration/annotation_batches/2026-05-25.json`.
   - Generated JSON must use sorted keys, two-space indentation, final LF newline, and no wall-clock timestamp.
   - If `--output` is omitted, it must write the JSON payload to stdout and exit zero without creating files.

4. Internal Console annotation page closes the human review loop without adding backend dependencies.
   - Add a client-side internal page at `apps/web/src/app/console/critic-annotation/page.tsx`.
   - The page may import the committed dataset JSON directly and must not call external services.
   - It must support loading a sample from query param `sample=<id>`; unknown sample IDs show a clear not-found state.
   - If no `sample` query param is provided, it must default to the first ticket in the committed 2026-05-25 batch, not the first historical M3 seed sample.
   - It must display prompt, category, expected label, critic confidence, escalation decision using the current threshold, source story, and Chinese critic reason.
   - For M3.5b samples it must also display the `llm_output_excerpt`; for older M3 samples without that field it must render a stable fallback rather than crash.
   - It must offer pass / escalate / auto-block review controls, an adjudication note field, and a deterministic local summary of the current decision.
   - It must show batch progress from the committed 2026-05-25 ticket payload: total 20, todo/reviewed counts, due date, and Linear epic key.
   - It must not persist labels, send network requests, store API keys, or imply production auth/authorization exists.
   - It must not use `localStorage`, `sessionStorage`, cookies, IndexedDB, server actions, API routes, or fetch/XHR.
   - It must include a navigation link from the Repro console header or equivalent Console nav to the Critic annotation page.

5. Monthly calibration rerun evidence is committed and validated.
   - Add monthly report generation to `tools/critic_calibration/create_annotation_batch.py` via a `monthly-report` subcommand, or add `tools/critic_calibration/create_monthly_report.py` if the implementation stays simpler.
   - Add a deterministic monthly report artifact at `tools/critic_calibration/monthly_reports/2026-05.json`.
   - The report must be generated from the same 50-sample dataset and current committed config.
   - It must include dataset version, target stage, sample count, recommended threshold, recall, false-positive rate, false-negative rate, precision, `tp/fp/tn/fn`, batch file path, batch sample IDs, generated config path, M5 target sample count `200`, remaining-to-M5 count `150`, and decision `pass`.
   - It must not include prompt text, raw critic reasons, secrets, PII, credentials, or wall-clock timestamps.
   - The report must document that threshold remains `0.60` unless the calibration output recommends a different value.
   - Report generation must reuse `calibrate_dataset()` so metric formulas cannot drift from the committed config.
   - Report generation must fail if the referenced batch file does not exist or its sample IDs do not match dataset rows.

6. Tests and CI enforce the ongoing annotation loop.
   - Extend `tests/test_critic_calibration.py` or add focused tests covering:
     - 50-sample dataset validation and committed config parity.
     - Preservation of existing 30 sample IDs and the new 031-050 weekly batch IDs.
     - New weekly samples include at least two rows per required category.
     - Batch generation success for `--week-start 2026-05-25 --count 20`.
     - Batch sample IDs exactly match `critic-cal-v1-031` through `critic-cal-v1-050` and all reference dataset rows.
     - Batch generator rejects non-Monday dates, invalid counts, and insufficient samples.
     - Batch generator stdout mode produces the same JSON object as file-output mode.
     - Batch payload ticket keys, due date, UI path, and Linear epic key are deterministic.
     - Batch payload includes sanitized `llm_output_excerpt` but no full provider payloads, credentials, tenant identifiers, or PII.
     - Monthly report matches calibration output, references the batch sample IDs, and contains no prompt/reason text.
     - M3 compatibility remains intact: a 30-sample `target_stage=M3` dataset without `llm_output_excerpt` still validates, while a 50-sample dataset mislabeled as M3 or a 30-sample dataset mislabeled as M3.5b is rejected.
     - Console page source remains client-only/offline by rejecting `fetch(`, `localStorage`, `sessionStorage`, server actions, and API route additions for this story.
   - Add Vitest coverage for `/console/critic-annotation` rendering known sample, not-found state, decision controls, and batch progress.
   - Extend `.github/workflows/ci.yml` `critic_calibration` paths to include annotation batch artifacts, monthly reports, and the new batch script.
   - Ensure CI still runs the calibration CLI smoke generation to `/tmp/critic-calibration.json`, batch generation to `/tmp/critic-annotation-batch.json`, monthly report generation to `/tmp/critic-monthly-report.json`, and pytest.
   - Ensure web changes trigger the existing `ts-typecheck` path filter; no separate runtime service job is required.

7. Workflow tracking and boundaries are explicit.
   - This story records three pre-implementation story review rounds and fixes after each round before implementation.
   - `_bmad-output/stories/sprint-status.yaml` moves `m3-5b-critic-ground-truth-annotation` to `ready-for-dev` only after the three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.
   - This story must not implement real Linear API mutation, production auth/authorization, database persistence, active learning, model training, LLM calls, chat integration, SSE, Redis streams, or critic-service runtime endpoints.

## Tasks / Subtasks

- [x] Expand the Critic ground-truth dataset. (AC: 1, 2)
  - [x] Add 20 adjudicated M3.5b samples with IDs `critic-cal-v1-031` through `critic-cal-v1-050`.
  - [x] Add sanitized `llm_output_excerpt` to every new M3.5b sample.
  - [x] Preserve the first 30 sample IDs and meanings.
  - [x] Update `target_stage` to `M3.5b` and keep root schema stable.
  - [x] Ensure synthetic/redacted prompts and at least two new rows per required category.
- [x] Extend calibration validation and regenerate config. (AC: 2, 5)
  - [x] Update dataset validation to accept the M3.5b 50-sample target without accepting arbitrary sizes.
  - [x] Bind accepted sample counts to `target_stage` and reject mislabeled stage/count pairs.
  - [x] Validate M3.5b-only `llm_output_excerpt` without requiring it for M3 rows.
  - [x] Keep threshold and metric behavior unchanged.
  - [x] Regenerate `apps/critic-service/config/critic-calibration.json`.
  - [x] Add deterministic monthly report artifact.
- [x] Build offline annotation batch generator. (AC: 3)
  - [x] Add `tools/critic_calibration/create_annotation_batch.py`.
  - [x] Reuse validation/constants from `calibrate.py`.
  - [x] Validate Monday `week_start`, count, and sufficient samples.
  - [x] Support both stdout and file-output modes.
  - [x] Generate `tools/critic_calibration/annotation_batches/2026-05-25.json`.
  - [x] Ensure the generated batch references exactly `critic-cal-v1-031` through `critic-cal-v1-050` and includes `llm_output_excerpt`.
  - [x] Keep generated JSON deterministic and LF-normalized.
- [x] Add internal Console annotation page. (AC: 4)
  - [x] Add `/console/critic-annotation` page using committed dataset and batch JSON.
  - [x] Implement default-to-first-batch-ticket behavior, sample query lookup, LLM output display, not-found state, decision controls, note field, and local summary.
  - [x] Show batch progress, due date, and Linear epic key.
  - [x] Add nav link from an existing Console page.
- [x] Add tests and CI coverage. (AC: 1-6)
  - [x] Add/extend Python tests for dataset, config, batch generator, and monthly report.
  - [x] Add regression tests for M3/M3.5b stage-count compatibility.
  - [x] Add Vitest tests for the annotation page.
  - [x] Add static guard tests proving this story did not add network/persistence/runtime API behavior to the annotation page.
  - [x] Extend CI path filters for new calibration artifacts.
  - [x] Run focused Python tests, web Vitest, web typecheck, ruff, pre-commit, and `git diff --check`.
- [x] Update SOP for the ongoing annotation artifacts. (AC: 1, 3, 5)
  - [x] Document `llm_output_excerpt`, weekly batch payloads, monthly report fields, and M5 progress accounting in `docs/critic-annotation-sop.md`.
- [ ] Update workflow records and validation evidence. (AC: 7)
  - [ ] Record implementation notes, file list, and change log.
  - [ ] Move sprint status through `in-progress`, `code-review`, and `done` only after gates pass.
  - [ ] Run post-implementation code review and apply fixes.

## Dev Notes

### Context

- M3.5a shipped the deterministic offline calibration gate, 30-sample seed dataset, aggregate config, SOP, tests, and CI job.
- The existing `apps/critic-service/` directory is only a future handoff location; no running critic-service runtime exists.
- The committed config currently reflects 30 samples, `target_stage=M3`, and threshold `0.60`.
- `docs/critic-annotation-sop.md` says M3.5b owns weekly expansion by roughly 20 samples and monthly calibration reruns.
- Architecture G9 defines Critic confidence calibration ground truth as an important gap requiring annotation tooling, SOP, validation strategy, and 200-300 person-hours of labeling work.
- The epic names Linear `OPTI-CRITIC-ANNOT`, weekly Monday 09:00 ticket creation, seven-day deadline, and an internal Console annotation UI. Since this repo has no Linear client, scheduler, authz, or backend review queue, this story implements deterministic Linear-compatible payloads and a client-only internal UI surface.

### Scope Decisions

- Treat "自动 ticket 创建 cron" as a deterministic offline batch generator plus committed payload evidence for this story; a future scheduler/Linear integration story may consume the payload format.
- Treat "标注页面（Console 内部工具）" as a client-only internal Console page with local state; it demonstrates the workflow without adding persistence or production authorization.
- Treat "月度 calibration script 重跑 + 阈值微调" as committed calibration config plus monthly aggregate report; threshold changes only when the existing calibration algorithm recommends them.
- Keep `ground_truth_v1` as the dataset version so config consumers are not forced to change version contracts; use `target_stage=M3.5b` and `sample_count=50` to distinguish the expanded dataset.
- Do not weaken M3.5a policy gates to make the 50-sample dataset pass. Adjust sample confidence values only through plausible adjudicated synthetic samples.
- If implementation cannot make the 50-sample dataset satisfy policy gates at threshold 0.60, do not change the policy; add or adjust synthetic adjudicated M3.5b samples within the documented categories and explain the calibration result in the Dev Agent Record.

### Architecture / External Constraints

- Python tools under `tools/critic_calibration/` must remain stdlib-only and offline.
- Reuse `calibrate.py` functions for dataset validation and metric calculation in any new Python tool. Do not duplicate schema constants, threshold logic, or metric formulas.
- Do not add Python dependencies or add `tools/critic_calibration` as a uv workspace member.
- TypeScript code must follow current Next.js App Router patterns in `apps/web/src/app/console/*`.
- Vitest component tests can use `// @vitest-environment happy-dom`, as existing Console page tests do.
- The web page may import JSON because `apps/web/tsconfig.json` has `resolveJsonModule=true`.
- Because `page.tsx` will need `useSearchParams`, wrap the query-reading component in `Suspense` if Next.js build requires it.
- Use existing `@opticloud/ui` components where useful, especially `StatusCard`; avoid adding a shared UI component unless duplication becomes meaningful.
- Keep generated config and monthly report prompt-free; batch payloads necessarily contain synthetic prompts and sanitized `llm_output_excerpt` values for annotation but must not contain secrets, full provider payloads, or production identifiers.
- JSON generation must force LF line endings, matching the M3.5a Windows CI lint fix.

### Project Structure Notes

- Existing files likely modified:
  - `tools/critic_calibration/calibrate.py`
  - `tools/critic_calibration/ground_truth_v1.json`
  - `apps/critic-service/config/critic-calibration.json`
  - `tests/test_critic_calibration.py`
  - `.github/workflows/ci.yml`
  - `docs/critic-annotation-sop.md`
  - `_bmad-output/stories/sprint-status.yaml`
- New files likely added:
  - `tools/critic_calibration/create_annotation_batch.py`
  - `tools/critic_calibration/annotation_batches/2026-05-25.json`
  - `tools/critic_calibration/monthly_reports/2026-05.json`
  - `apps/web/src/app/console/critic-annotation/page.tsx`
  - `apps/web/src/app/console/critic-annotation/page.test.tsx`

### Testing / Validation Notes

- Expected local commands:
  - `uv run python tools/critic_calibration/calibrate.py --dataset tools/critic_calibration/ground_truth_v1.json --output apps/critic-service/config/critic-calibration.json`
  - `uv run python tools/critic_calibration/create_annotation_batch.py --dataset tools/critic_calibration/ground_truth_v1.json --week-start 2026-05-25 --count 20 --output tools/critic_calibration/annotation_batches/2026-05-25.json`
  - `uv run pytest tests/test_critic_calibration.py -q`
  - `uv run ruff check tools/critic_calibration tests/test_critic_calibration.py`
  - `uv run ruff format --check tools/critic_calibration tests/test_critic_calibration.py`
  - `pnpm --filter @opticloud/web test -- src/app/console/critic-annotation/page.test.tsx`
  - `pnpm --filter @opticloud/web typecheck`
  - `uv run pre-commit run --all-files --show-diff-on-failure`
  - `git diff --check`

### Risks / Decisions

- Data consistency risk: config, batch payload, monthly report, and dataset can drift. Tests must compare generated artifacts with committed files.
- Function consistency risk: M3.5b could accidentally invert or loosen M3.5a threshold semantics. Tests must keep strict `< threshold` and policy gates pinned.
- Function drift risk: adding M3.5b count support could let arbitrary sample counts pass. Validation must bind accepted counts to `target_stage`.
- Schema drift risk: adding `llm_output_excerpt` could break M3 compatibility. Make it required only for `source_story=M3.5b`.
- Workflow drift risk: "Linear ticket tracking" could be mistaken for real Linear API integration. Story scope is deterministic payload generation only.
- Boundary risk: client-only UI can be mistaken for production annotation persistence. UI copy and tests must keep it local/session-only.
- Closure risk: web changes may pass while Python artifacts drift, or vice versa. CI filters must include both calibration and web paths.
- Closure risk: create-story status can jump ahead of review. Keep story `Status: draft` until all three story review rounds are recorded, then update story and sprint status to `ready-for-dev`.
- Boundary risk: query-parameter handling in Next.js can fail build if `useSearchParams` is not isolated. Add Vitest coverage and run typecheck/build-level checks where practical.

### References

- `_bmad-output/planning/epics.md:1154` — Story M3.5b scope and acceptance.
- `_bmad-output/planning/architecture.md:2005` — G9 critical gap.
- `_bmad-output/planning/architecture.md:2261` — M3.5b foundation continuation entry.
- `_bmad-output/stories/m3-5a-critic-calibration.md` — previous calibration story, review findings, implementation notes, and CI drift fix.
- `docs/critic-annotation-sop.md` — current SOP for weekly M3.5b expansion and monthly calibration handoff.
- `tools/critic_calibration/calibrate.py` — existing calibration semantics and deterministic config writer.
- `tests/test_critic_calibration.py` — existing parity, policy, and validation tests.
- `.github/workflows/ci.yml` — existing `critic_calibration` path filter and validation job.

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Added `llm_output_excerpt` for new M3.5b samples and batch tickets because the epic requires each ticket to contain both prompt and LLM output. Existing 30 M3 seed rows remain backward compatible.
- Required the committed weekly batch to reference exactly `critic-cal-v1-031` through `critic-cal-v1-050`, with no duplicate or missing dataset references.
- Added monthly report fields for batch sample IDs, M5 target `200`, and remaining-to-M5 `150` so dataset progress is auditable.
- Added SOP update requirements for the new batch/report artifacts and the M3.5b-only output excerpt field.

Status: PASS after fixes.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Bound accepted sample counts to `target_stage` so M3 remains exactly 30 samples and M3.5b is exactly 50, preventing arbitrary dataset sizes from passing.
- Required new tools to reuse `calibrate.py` validation and metric functions instead of copying threshold or schema logic.
- Added M3 compatibility requirements so `llm_output_excerpt` is mandatory only for M3.5b rows and does not break existing M3 rows.
- Added stdout/file parity for the batch generator and required monthly report generation to reuse `calibrate_dataset()`.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Added fail-closed batch selection: the newest weekly batch must all be `source_story=M3.5b`, preventing historical seed rows from being re-ticketed.
- Added UI boundary constraints: no fetch/XHR, browser storage, cookies, server actions, API routes, or persistence; missing query defaults to the first committed batch ticket.
- Added monthly report closure: report generation must fail when the referenced batch is missing or does not match dataset rows.
- Expanded CI smoke commands to cover calibration config, annotation batch generation, monthly report generation, and pytest.
- Added Next.js boundary guidance for `useSearchParams` and story-status closure guidance.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

1. Move sprint status to `ready-for-dev`, then `in-progress`.
2. Expand the dataset to 50 samples and harden calibration validation for M3/M3.5b stage-count compatibility.
3. Add deterministic annotation batch and monthly report generation, committed artifacts, tests, and CI smoke commands.
4. Add the client-only Console annotation page and Vitest coverage.
5. Run focused validation, perform post-implementation code review, patch findings, and complete the story.

### Debug Log References

- 2026-05-26 — Created initial M3.5b story draft from sprint backlog after M3.5a merged.
- 2026-05-26 — Completed story review round 1 and patched data consistency requirements for LLM output excerpts, batch sample IDs, monthly progress accounting, and SOP updates.
- 2026-05-26 — Completed story review round 2 and patched function consistency requirements for stage-count binding, M3 compatibility, shared validation, and report metric reuse.
- 2026-05-26 — Completed story review round 3 and patched boundary/closure requirements for client-only UI, fail-closed batch selection, report batch matching, CI smoke coverage, and status sequencing.
- 2026-05-26 — Started implementation; sprint status moved to in-progress.
- 2026-05-26 — RED phase passed: `uv run pytest tests/test_critic_calibration.py -q` failed on expected missing M3.5b dataset, batch tool, monthly report, and Console page.
- 2026-05-26 — Expanded ground truth to 50 samples, added M3.5b `llm_output_excerpt` rows, and updated calibration validation for stage-count compatibility.
- 2026-05-26 — Added offline annotation batch/monthly-report CLI and generated committed `2026-05-25` batch plus `2026-05` monthly report.
- 2026-05-26 — Added client-only `/console/critic-annotation` page, Repro console nav link, and Vitest coverage.
- 2026-05-26 — Validation passed: `uv run pytest tests/test_critic_calibration.py -q` (23 passed).
- 2026-05-26 — Validation passed: `pnpm --filter @opticloud/web test -- src/app/console/critic-annotation/page.test.tsx` (4 passed).
- 2026-05-26 — Validation passed: `pnpm --filter @opticloud/web typecheck`.
- 2026-05-26 — Validation passed: `uv run ruff check tools/critic_calibration tests/test_critic_calibration.py`.
- 2026-05-26 — Validation passed: `uv run ruff format --check tools/critic_calibration tests/test_critic_calibration.py`.
- 2026-05-26 — Validation passed: `uv run mypy tools/critic_calibration/calibrate.py tools/critic_calibration/create_annotation_batch.py`.
- 2026-05-26 — Validation passed: `$env:PYTHONPATH='apps/auth-service/src;packages/shared-py'; uv run pytest tests -q` (74 passed).
- 2026-05-26 — Validation passed: `uv run pre-commit run --all-files --show-diff-on-failure`.
- 2026-05-26 — Validation passed: `git diff --check`.
- 2026-05-26 — Implementation complete; story moved to code-review.
- 2026-05-26 — Post-implementation code review found and fixed two closure risks: monthly report accepted duplicate/reordered batch sample IDs, and Console progress could imply local decisions were persisted as reviewed batch tickets.
- 2026-05-26 — Validation passed after review fixes: `uv run pytest tests/test_critic_calibration.py -q` (23 passed), `pnpm --filter @opticloud/web test -- src/app/console/critic-annotation/page.test.tsx` (4 passed), `pnpm --filter @opticloud/web typecheck`, `uv run ruff check tools/critic_calibration tests/test_critic_calibration.py`, and `uv run ruff format --check tools/critic_calibration tests/test_critic_calibration.py`.
- 2026-05-26 — Final validation passed: regenerated calibration config, annotation batch, and monthly report from source data.
- 2026-05-26 — Final validation passed: `uv run pytest tests/test_critic_calibration.py -q` (23 passed).
- 2026-05-26 — Final validation passed: `pnpm --filter @opticloud/web test -- src/app/console/critic-annotation/page.test.tsx` (4 passed).
- 2026-05-26 — Final validation passed: `pnpm --filter @opticloud/web typecheck`.
- 2026-05-26 — Final validation passed: `uv run mypy tools/critic_calibration/calibrate.py tools/critic_calibration/create_annotation_batch.py`.
- 2026-05-26 — Final validation passed: `uv run ruff check tools/critic_calibration tests/test_critic_calibration.py`.
- 2026-05-26 — Final validation passed: `uv run ruff format --check tools/critic_calibration tests/test_critic_calibration.py`.
- 2026-05-26 — Final validation passed: `$env:PYTHONPATH='apps/auth-service/src;packages/shared-py'; uv run pytest tests -q` (74 passed).
- 2026-05-26 — Final validation passed: `pnpm --filter @opticloud/web build`.
- 2026-05-26 — Final validation passed: `uv run pre-commit run --all-files --show-diff-on-failure`.
- 2026-05-26 — Final validation passed: `git diff --check`.

### Completion Notes List

- Expanded `ground_truth_v1` from 30 to 50 samples while preserving the original 30 stable IDs and adding M3.5b rows 031-050 with sanitized LLM output excerpts.
- Hardened calibration validation so M3 remains exactly 30 samples, M3.5b is exactly 50 samples, and M3.5b output excerpts are required and sanitized.
- Added deterministic offline generation for Linear-compatible annotation batches and monthly calibration reports.
- Added a client-only Console annotation page with query-driven sample lookup, local adjudication controls, batch progress, and no network or persistence behavior.
- Added Python and Vitest guardrails plus CI smoke commands for config, batch, monthly report, and page behavior.
- Post-review hardening now rejects duplicate or reordered monthly batch sample IDs and keeps Console batch status separate from local adjudication state.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/stories/m3-5b-critic-ground-truth-annotation.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/critic-service/config/critic-calibration.json`
- `apps/web/src/app/console/critic-annotation/page.test.tsx`
- `apps/web/src/app/console/critic-annotation/page.tsx`
- `apps/web/src/app/console/repro/page.tsx`
- `docs/critic-annotation-sop.md`
- `tests/test_critic_calibration.py`
- `tools/critic_calibration/annotation_batches/2026-05-25.json`
- `tools/critic_calibration/calibrate.py`
- `tools/critic_calibration/create_annotation_batch.py`
- `tools/critic_calibration/ground_truth_v1.json`
- `tools/critic_calibration/monthly_reports/2026-05.json`

### Change Log

- 2026-05-26 — Created initial story draft.
- 2026-05-26 — Round 1 data consistency review fixes applied.
- 2026-05-26 — Round 2 function consistency and drift review fixes applied.
- 2026-05-26 — Round 3 boundary and closure review fixes applied; story ready for development.
- 2026-05-26 — Implemented M3.5b dataset expansion, batch/monthly report tooling, Console annotation page, tests, SOP update, and CI smoke coverage.
- 2026-05-26 — Code review fixes applied for strict monthly batch matching and non-persistent Console progress wording.
- 2026-05-26 — Final validation passed; story marked done.

### Post-Implementation Code Review (AI)

Outcome: PASS after fixes.

Findings fixed:
- Monthly report closure risk: report generation verified batch IDs existed in the dataset but did not reject duplicate or reordered batch IDs. Fixed by requiring `sample_count` parity, unique IDs, and exact newest-M3.5b sample ID order.
- Console workflow risk: batch progress changed from `0/20` to `1/20` after a local click, which could imply persisted review progress. Fixed by showing committed batch status as `20 todo` and local decision as a separate non-persistent field.
