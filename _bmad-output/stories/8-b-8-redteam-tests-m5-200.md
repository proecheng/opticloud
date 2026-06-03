---
story_key: 8-b-8-redteam-tests-m5-200
epic_num: 8
story_num: B.8
epic_name: AIGC Filter + Rate Limit + Error Codes RFC 7807
status: code-review
baseline_commit: e47cf3814ae972630b343da837cb80b86500a314
priority: High
type: NFR-S7 Critic red-team M5 calibration gate
created_by: bmad-create-story
created_at: 2026-06-03
sources:
  - _bmad-output/planning/epics.md (Epic 8.B / Story 8.B.8)
  - _bmad-output/planning/epics.md (Story M3.5a / M3.5b)
  - _bmad-output/planning/prd.md (NFR-S Critic red-team M3>=30 / M5>=200)
  - _bmad-output/planning/architecture.md (G9 / M3.5b foundation continuation)
  - _bmad-output/stories/m3-5a-critic-calibration.md
  - _bmad-output/stories/m3-5b-critic-ground-truth-annotation.md
  - _bmad-output/stories/4-b-7-critic-redteam-tests.md
  - tools/critic_calibration/calibrate.py
  - tools/critic_calibration/create_annotation_batch.py
  - tools/critic_calibration/ground_truth_v1.json
  - tests/test_critic_calibration.py
  - apps/critic-service/config/critic-calibration.json
  - docs/critic-annotation-sop.md
  - .github/workflows/ci.yml
---

# Story 8.B.8 - Critic 红队测试集 >=200 (M5 升级)

Status: code-review

## Story

**作为** Critic Safety / NFR-S owner，
**我希望** Story M3.5b 的 Critic ground-truth 标注闭环从 50 条推进到 M5 至少 200 条，并把 red-team 拦截/升级率 >=98% 作为可执行 CI 门禁，
**从而** NFR-S7 的 Critic 红队测试集不只是 SOP 目标，而是在 committed dataset、calibration config、monthly report 和 CI 中形成可审计的 M5 证据。

## Context

Epic 8.B.8 的原始 AC 是：Given Story M3.5b 持续标注 / When M5 末 / Then 红队测试集 >=200 + 拦截率 >=98%。

当前仓库状态：

- M3.5a 已建立 stdlib-only offline calibration CLI、30 条 M3 seed dataset、`critic-calibration.json`、SOP、tests 和 CI gate。
- M3.5b 已将 `tools/critic_calibration/ground_truth_v1.json` 扩展到 50 条，`target_stage=M3.5b`，新增 weekly annotation batch、monthly report、Console annotation page 和 CI smoke commands。
- `tools/critic_calibration/monthly_reports/2026-05.json` 仍显示 `m5_target_sample_count=200`、`remaining_to_m5=150`。
- 4.B.7 已覆盖 AIGC filter adapter red-team gate；它不是本 story 的实现面。8.B.8 聚焦 Critic calibration ground truth / red-team escalation gate。

本 story 的正确方向是把 Critic calibration artifacts 升级为 M5 200-sample gate：扩展 dataset、更新 validator 支持 `target_stage=M5`、生成 M5 weekly batch + evidence report、更新 config、增强 tests/CI。不要新增真实 Linear API、生产 Critic service、模型训练、Chat runtime 或 AIGC filter 规则。

## Scope

1. 扩展 Critic ground truth 至 M5。
   - 将 `tools/critic_calibration/ground_truth_v1.json` 从 50 条扩展到 **exactly 200 total samples**，与现有 `M5_TARGET_SAMPLE_COUNT=200` 和 monthly report remaining-to-M5 语义一致。
   - 沿用 M3.5a/M3.5b 的 ground-truth calibration-set 语义：M5 200 是 total adjudicated samples，包含 expected-escalate red-team/high-risk samples 和 expected-non-escalate controls；recall 衡量 red-team/高风险拦截率，false-positive rate 衡量 control 误升级率。
   - 更新 `target_stage` 为 `M5`，保留 `dataset_version=ground_truth_v1`。
   - 保留并不重编号 `critic-cal-v1-001` 到 `critic-cal-v1-050`。
   - 新增稳定 ID `critic-cal-v1-051` 到 `critic-cal-v1-200`。
   - M5 新样本必须全部 synthetic/redacted；不得包含 raw user secret、credential、private dataset、production tenant ID、PII 或 full provider payload。

2. 让 calibration validator 支持 M5，但不放宽旧阶段。
   - `target_stage=M3` 仍必须 exactly 30 samples。
   - `target_stage=M3.5b` 仍必须 exactly 50 samples。
   - `target_stage=M5` 必须 exactly 200 samples。
   - `source_story=M3.5b` 和 `source_story=M5` 样本必须包含 sanitized `llm_output_excerpt`。
   - 阈值语义继续固定为 `critic_confidence < threshold`。

3. 把“拦截率 >=98%”定义为 M5 red-team escalation recall gate。
   - 对 `expected_escalate=true` 的 red-team/高风险样本，`predicted_escalate` 比例必须 >=98%。
   - 继续保留 expected non-escalate 控制样本，false-positive rate 必须 <=5%。
   - `calibrate_dataset(...)` / tests / config 必须把 recall 和 false-positive rate 作为 gate，不得只验证 sample count。

4. 更新 M5 artifacts。
   - Regenerate `apps/critic-service/config/critic-calibration.json`，必须显示 `sample_count=200`、`target_stage=M5`，且只包含 aggregate metrics/policy metadata。
   - Add deterministic M5 weekly batch artifact，例如 `tools/critic_calibration/annotation_batches/2026-06-01.json`，引用最新 20 条 M5 样本。
   - Add deterministic M5 monthly/evidence report，例如 `tools/critic_calibration/monthly_reports/2026-06.json`。
   - Report 必须包含 M5 target `200`、remaining-to-M5 `0`、decision `pass`、metrics、config path、dataset path 和 sample count；不得包含 prompt/reason text。
   - Preserve existing `2026-05` batch/report as historical M3.5b evidence; current-generation parity tests should target the M5 `2026-06` batch/report.

5. CI and tests close the loop.
   - Extend `tests/test_critic_calibration.py` for M5 stage/count binding, ID continuity 001-200, category distribution, M5 recall >=98%, committed config parity, M5 report parity and no prompt/reason leak.
   - Ensure CI `critic-calibration-validation` generates M5 config/report smoke artifacts and runs pytest.
   - Ensure CI path filter already or newly covers dataset/config/report/tool/test/SOP changes.

## Out Of Scope

- 不新增真实 Linear API mutation、cron scheduler、production auth/authorization、DB persistence、active learning、model training、LLM calls、Chat integration、SSE、Redis streams 或 critic-service runtime endpoints。
- 不修改 AIGC filter red-team dataset、AIGC watermark/detector、4.B.7 adapter gate 或 AIGC filing 状态。
- 不新增前端 UI，除非 M5 tests 发现现有 Console annotation page 因 200 样本数据 shape 失败；若需要也只做兼容修复。
- 不把 prompt、critic_reason_zh、llm_output_excerpt 或 private annotation payload 写入 `critic-calibration.json` / monthly M5 report。
- 不改变 `ground_truth_v1` dataset_version，避免破坏现有 consumer contract。

## Acceptance Criteria

1. `tools/critic_calibration/ground_truth_v1.json` root 保持 `dataset_version=ground_truth_v1`，`target_stage=M5`，`samples` exactly 200。
2. Existing IDs `critic-cal-v1-001` through `critic-cal-v1-050` are preserved in order; new IDs `critic-cal-v1-051` through `critic-cal-v1-200` are added in order with no duplicates or gaps.
3. All M5 new samples have required fields: `id`, `prompt`, `expected_escalate`, `critic_confidence`, `critic_reason_zh`, `category`, `source_story`, `llm_output_excerpt`; `source_story` must be `M5`.
4. Dataset remains synthetic/redacted: tests reject forbidden secret markers in prompts and `llm_output_excerpt`; config/report artifacts must not contain prompt text, critic reasons, provider payload, tenant IDs or credentials.
5. Category coverage remains balanced enough for M5: every required category (`unsafe_code`, `schema_error`, `logic_error`, `sandbox_risk`, `benign`, `low_risk_style`) has at least 20 total samples, and each required category has at least 10 new M5 samples.
6. M5 calibration set keeps both classes: at least 100 expected-escalate red-team/high-risk samples and at least 40 expected-non-escalate control samples; both class counts are reported or asserted in tests.
7. Calibration validator accepts exactly `M3=30`, `M3.5b=50`, `M5=200`, and rejects mismatched stage/count pairs.
8. `source_story in {"M3.5b", "M5"}` requires non-empty sanitized `llm_output_excerpt`; M3 seed rows remain valid without it.
9. M5 red-team escalation recall gate passes: `metrics.recall >= 0.98` and `metrics.escalate_rate_on_expected_escalate == metrics.recall`.
10. M5 false-positive gate remains bounded: `metrics.false_positive_rate <= 0.05` and `metrics.false_escalate_rate_on_expected_non_escalate == metrics.false_positive_rate`.
11. `apps/critic-service/config/critic-calibration.json` is regenerated from the M5 dataset and equals runtime `calibrate_dataset(...)` output; it contains `sample_count=200`, `target_stage=M5`, `recommended_threshold` within `[0.55, 0.65]`, and no prompt/reason text.
12. A deterministic M5 weekly batch exists at `tools/critic_calibration/annotation_batches/2026-06-01.json`, references exactly newest sample IDs `critic-cal-v1-181` through `critic-cal-v1-200`, and has no duplicate/missing IDs.
13. A deterministic M5 report exists at `tools/critic_calibration/monthly_reports/2026-06.json`; it references the M5 dataset/config and `2026-06-01` batch, has `m5_target_sample_count=200`, `remaining_to_m5=0`, `decision=pass`, and no prompt/reason text.
14. Existing batch/monthly tooling remains compatible: `create_annotation_batch.py batch` can generate the M5 batch from the M5 dataset, and `monthly-report` can generate the M5 report from the M5 dataset/config/M5 batch while preserving historical 2026-05 artifacts.
15. CI `critic-calibration-validation` remains hard-gated, has no `continue-on-error`, and runs smoke commands for calibration, M5 annotation batch/monthly report generation, plus `uv run pytest tests/test_critic_calibration.py -v`.
16. 本地验证至少运行：calibration config generation, M5 batch/report generation, `uv run pytest tests/test_critic_calibration.py -q`, ruff check/format, mypy for critic calibration tools, full pre-commit, and `git diff --check`.
17. 实施后代码审查覆盖边界问题、漂移问题、数据一致性、依赖一致性、CI 闭环、M5 recall/false-positive gate、artifact no-leak、stage/count compatibility 和测试充分性；发现必须修复或记录。
18. PR 通过 GitHub CI、合并到 `main`、远程分支删除、本地 `main` 同步后，才能把 story 与 sprint status 标记为 `done` 并推送 status-sync commit。

## Tasks / Subtasks

- [x] T1: Expand Critic dataset to M5 200 samples (AC: 1-5)
  - [x] Preserve existing 001-050 IDs and semantics.
  - [x] Add 051-200 synthetic/redacted M5 samples with `source_story=M5`.
  - [x] Ensure all M5 rows include sanitized `llm_output_excerpt`.
  - [x] Keep category coverage balanced and avoid secret/provider/tenant/PII markers.
  - [x] Preserve expected-escalate and expected-non-escalate class coverage for recall and false-positive measurement.

- [x] T2: Harden calibration validation for M5 (AC: 6-10)
  - [x] Add `M5: 200` stage/count binding.
  - [x] Require excerpt for M3.5b/M5 rows only.
  - [x] Preserve strict `< threshold` semantics.
  - [x] Make M5 recall >=98% and false-positive <=5% executable tests.

- [x] T3: Regenerate config and M5 evidence report (AC: 11-14)
  - [x] Regenerate `apps/critic-service/config/critic-calibration.json`.
  - [x] Add `tools/critic_calibration/annotation_batches/2026-06-01.json`.
  - [x] Add `tools/critic_calibration/monthly_reports/2026-06.json`.
  - [x] Extend or reuse `create_annotation_batch.py` to generate the M5 report deterministically.
  - [x] Keep report/config prompt-free and reason-free.

- [x] T4: Tests and CI closure (AC: 15-16)
  - [x] Extend `tests/test_critic_calibration.py` for M5 dataset, config, report, no-leak and stage/count compatibility.
  - [x] Update CI smoke commands only if needed for M5 report generation.
  - [x] Run local gates and record results.

- [ ] T5: Review and GitHub sync (AC: 17-18)
  - [x] Complete post-implementation code review and fix findings.
  - [ ] Commit, push, create PR, wait CI, merge, delete remote branch, sync local main.
  - [ ] After merge/sync, mark story and sprint status `done` and push status-sync commit.

## Dev Notes

### Existing Files And Current State

- `tools/critic_calibration/ground_truth_v1.json`
  - Current state: `target_stage=M3.5b`, exactly 50 samples, IDs 001-050.
  - This story changes: expand to exactly 200 samples and `target_stage=M5`.

- `tools/critic_calibration/calibrate.py`
  - Current state: `TARGET_SAMPLE_COUNTS={"M3":30, "M3.5b":50}`, policy gates recall >=95%, false-positive <=5%.
  - This story changes: add M5 200 support and executable recall >=98% test for M5 AC. Avoid changing public metric formulas or threshold semantics.

- `tools/critic_calibration/create_annotation_batch.py`
  - Current state: can create weekly batch and monthly report; `M5_TARGET_SAMPLE_COUNT=200`.
  - This story changes: may need M5 report support when remaining-to-M5 is zero and latest committed batch still represents M3.5b weekly evidence.

- `tests/test_critic_calibration.py`
  - Current state: 23 tests cover M3.5b 50-sample dataset, config drift, batch generation, monthly report, offline Console page boundary.
  - This story changes: add M5 tests while preserving M3/M3.5b compatibility tests.

- `.github/workflows/ci.yml`
  - Current state: `critic_calibration` path filter and validation job already exist; CI generates `/tmp/critic-calibration.json`, `/tmp/critic-annotation-batch.json`, `/tmp/critic-monthly-report.json`, then runs pytest.
  - This story changes: ensure smoke commands still reflect current M5 report path/month if necessary.

### Implementation Guardrails

- Keep Python tools stdlib-only and offline.
- Prefer extending existing `calibrate.py` and `create_annotation_batch.py`; do not create duplicate metric or schema logic.
- Treat `recall` as the Critic red-team interception/escalation rate for this story.
- Do not weaken false-positive gate to make M5 pass.
- Preserve LF-normalized deterministic JSON output.
- Keep generated config and M5 report free of prompt/reason/excerpt text.
- If using synthetic M5 rows, keep them plausible and category-diverse; no private data.

### Suggested Commands

```powershell
uv run python tools/critic_calibration/calibrate.py --dataset tools/critic_calibration/ground_truth_v1.json --output apps/critic-service/config/critic-calibration.json
uv run python tools/critic_calibration/create_annotation_batch.py batch --dataset tools/critic_calibration/ground_truth_v1.json --week-start 2026-06-01 --count 20 --output tools/critic_calibration/annotation_batches/2026-06-01.json
uv run python tools/critic_calibration/create_annotation_batch.py monthly-report --dataset tools/critic_calibration/ground_truth_v1.json --batch tools/critic_calibration/annotation_batches/2026-06-01.json --config apps/critic-service/config/critic-calibration.json --month 2026-06 --output tools/critic_calibration/monthly_reports/2026-06.json
uv run pytest tests/test_critic_calibration.py -q
uv run ruff check tools/critic_calibration tests/test_critic_calibration.py
uv run ruff format --check tools/critic_calibration tests/test_critic_calibration.py
uv run mypy tools/critic_calibration/calibrate.py tools/critic_calibration/create_annotation_batch.py
uv tool run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

## Definition Of Done

- Story has passed 3 pre-implementation adversarial review rounds with revisions recorded.
- Critic calibration dataset reaches M5 exactly 200 samples with stable IDs 001-200.
- M5 recall/interception gate is executable and passes at >=98%; false-positive remains <=5%.
- Config and M5 report are regenerated, deterministic, prompt-free and reason-free.
- Stage/count compatibility for M3 and M3.5b remains tested.
- Local gates and GitHub CI pass.
- Post-implementation code review completed and findings fixed or explicitly documented.
- Story and sprint status become `done` only after PR CI green, merge, remote branch deletion, local main sync and separate status-sync commit.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-b-8-redteam-tests-m5-200`.
- Baseline commit: `e47cf3814ae972630b343da837cb80b86500a314`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback used skill base instructions and project config.
- Story creation analyzed Epic 8.B.8, M3.5a/M3.5b calibration stories, 4.B.7 AIGC adapter boundary, current Critic calibration tools, dataset, config, monthly report, tests, SOP and CI.
- Implementation expanded current Critic calibration dataset to M5 200 samples, regenerated config, `2026-06-01` batch and `2026-06` monthly report.
- A parallel local generation attempt produced a transient JSON parse error because monthly report generation read artifacts while config/batch were being rewritten. Commands were rerun sequentially; CI uses sequential steps.
- Local validation completed: calibration config generation, M5 batch generation, M5 monthly report generation, `uv run pytest tests/test_critic_calibration.py -q`, ruff check, ruff format check, mypy, full pre-commit, and `git diff --check`.

### Completion Notes List

- Initial story created.
- Three pre-implementation adversarial review rounds completed and revisions applied before implementation.
- M5 implementation completed: dataset exactly 200 samples, 150 M5 rows, ID continuity 001-200, config/report regenerated with recall 1.0 and false-positive rate 0.0.
- Post-implementation adversarial code review completed; data quality finding fixed before GitHub sync.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/stories/8-b-8-redteam-tests-m5-200.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/critic-service/config/critic-calibration.json`
- `docs/critic-annotation-sop.md`
- `tests/test_critic_calibration.py`
- `tools/critic_calibration/annotation_batches/2026-06-01.json`
- `tools/critic_calibration/calibrate.py`
- `tools/critic_calibration/create_annotation_batch.py`
- `tools/critic_calibration/ground_truth_v1.json`
- `tools/critic_calibration/monthly_reports/2026-06.json`

## Change Log

- 2026-06-03 - Story created for 8.B.8 Critic red-team M5 200-sample calibration gate.
- 2026-06-03 - Pre-implementation adversarial reviews completed; story moved to in-progress.
- 2026-06-03 - M5 dataset/config/report/tests/CI/SOP implemented; local gates and post-implementation review completed; story moved to code-review pending GitHub sync.

## Post-Implementation Code Review

### Blind Hunter - Boundary And Regression Review

Findings:

- P1 fixed: Initial M5 generation had 150 rows but only 30 unique prompt/excerpt combinations and the newest 20-sample batch was control-heavy. That met count gates but weakened red-team evidence quality and batch representativeness.
- No remaining issue found in threshold semantics: `critic_confidence < threshold` remains unchanged and is still tested at the equality boundary.
- No remaining issue found in old-stage compatibility: constructed M3 and M3.5b datasets still validate with exact 30/50 count binding, and M5 rejects 50-row mislabeled data.

Fixes Applied:

- Regenerated M5 rows so all 150 new M5 prompts and excerpts are unique.
- Reordered M5 additions in category rotation so `critic-cal-v1-181` through `critic-cal-v1-200` include all required categories and both expected-escalate and expected-non-escalate classes.
- Added tests for M5 prompt/excerpt uniqueness and batch category/class coverage.

### Edge Case Hunter - Drift, Data, Artifact And No-Leak Review

Findings:

- No remaining issue found in ID continuity: validator now rejects gaps/out-of-order IDs and tests assert 001-200 exact sequence.
- No remaining issue found in M5 artifact parity: committed config equals runtime calibration output; committed `2026-06` report equals generator output and references the M5 batch.
- No remaining issue found in prompt/reason leakage: config and monthly report tests reject prompt, `critic_reason_zh`, and `llm_output_excerpt` text.
- Historical 2026-05 artifacts are intentionally preserved and tested as M3.5b history, not compared against current M5 config.

### Acceptance Auditor - AC Closure

Result: PASS for local implementation review.

- AC 1-14 covered by dataset/config/batch/report implementation and `tests/test_critic_calibration.py`.
- AC 15 covered by CI smoke command updates for `2026-06-01` batch and `2026-06` report; the job has no `continue-on-error`.
- AC 16 local gates passed:
  - `uv run python tools/critic_calibration/calibrate.py --dataset tools/critic_calibration/ground_truth_v1.json --output apps/critic-service/config/critic-calibration.json`
  - `uv run python tools/critic_calibration/create_annotation_batch.py batch --dataset tools/critic_calibration/ground_truth_v1.json --week-start 2026-06-01 --count 20 --output tools/critic_calibration/annotation_batches/2026-06-01.json`
  - `uv run python tools/critic_calibration/create_annotation_batch.py monthly-report --dataset tools/critic_calibration/ground_truth_v1.json --batch tools/critic_calibration/annotation_batches/2026-06-01.json --config apps/critic-service/config/critic-calibration.json --month 2026-06 --output tools/critic_calibration/monthly_reports/2026-06.json`
  - `uv run pytest tests/test_critic_calibration.py -q` -> 25 passed
  - `uv run ruff check tools/critic_calibration tests/test_critic_calibration.py`
  - `uv run ruff format --check tools/critic_calibration tests/test_critic_calibration.py`
  - `uv run mypy tools/critic_calibration/calibrate.py tools/critic_calibration/create_annotation_batch.py`
  - `uv tool run pre-commit run --all-files --show-diff-on-failure`
  - `git diff --check`
- AC 18 remains pending by design until PR CI green, merge, remote branch deletion, local main sync, and separate status-sync commit.

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary, Dataset Semantics, Data Consistency

Findings:

- M5 `>=200` can be misread as 200 red-team positive prompts only. That would destroy false-positive measurement and weaken the existing calibration semantics.
- Existing M3.5b artifacts are 50 total adjudicated samples; M5 must continue that meaning as 200 total samples, not a separate AIGC adapter red-team corpus.
- The 2026-05 batch/report are historical M3.5b evidence. Reusing them as current M5 evidence would leave `remaining_to_m5=150` and fail the M5 closure claim.

Revisions Applied:

- Scope and AC now define M5 as exactly 200 total adjudicated samples containing expected-escalate and expected-non-escalate controls.
- AC require at least 100 expected-escalate samples and at least 40 expected-non-escalate controls.
- Scope requires a new M5 batch at `tools/critic_calibration/annotation_batches/2026-06-01.json` and M5 report at `tools/critic_calibration/monthly_reports/2026-06.json`, while preserving 2026-05 artifacts as historical M3.5b evidence.

### Round 2 - Drift, Artifact History, Report Parity, CI Closure

Findings:

- Config/report parity tests can drift if they compare the current M5 dataset against the historical 2026-05 report.
- CI smoke commands still pointing at 2026-05 would prove only M3.5b generation, not M5 closure.
- Monthly report generation must fail closed when batch sample IDs do not match the newest current-stage samples.

Revisions Applied:

- AC now target 2026-06 M5 artifacts for current parity and explicitly preserve 2026-05 as historical evidence.
- Suggested commands were revised to generate calibration config, `2026-06-01` batch, and `2026-06` report.
- Test scope requires M5 report parity, newest sample IDs `critic-cal-v1-181` through `critic-cal-v1-200`, and CI smoke coverage for M5 generation.

### Round 3 - Dependency, Scope, Gate Semantics, Done-State Closure

Findings:

- Adding 150 rows by hand is high-risk: ID gaps, class imbalance, category undercoverage, forbidden marker leakage, or excerpt omissions could silently pass if tests only check sample count.
- The existing calibration policy has strict `critic_confidence < threshold` semantics. Any implementation that changes the inequality or loosens false-positive policy to pass M5 would invalidate prior stories.
- Marking story status `done` before PR merge and local main sync would break the user's required lifecycle.

Revisions Applied:

- AC now require ID continuity 001-200, required category minimums, class counts, secret-marker rejection, sanitized excerpts, config/report no-leak assertions, and explicit M5 recall >=98% plus false-positive <=5%.
- Implementation guardrails prohibit duplicate metric/schema logic and require preserving threshold semantics.
- Definition of Done and AC require post-implementation code review, GitHub CI green, PR merge, remote branch deletion, local main sync, and separate status-sync commit before story/sprint status can become `done`.
