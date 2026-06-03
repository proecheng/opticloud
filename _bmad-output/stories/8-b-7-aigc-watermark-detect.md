---
story_key: 8-b-7-aigc-watermark-detect
epic_num: 8
story_num: B.7
epic_name: AIGC Filter + Rate Limit + Error Codes RFC 7807
status: code-review
baseline_commit: d23bed38edbd56541328410e68274dc8cccaae89
priority: High
type: G12 AIGC zero-width watermark detector closure
created_by: bmad-create-story
created_at: 2026-06-03
sources:
  - _bmad-output/planning/epics.md (Epic 8.B / Story 8.B.7)
  - _bmad-output/planning/epics.md (Story M3.4 / G12 source AC)
  - _bmad-output/planning/architecture.md (M3.4 AIGC watermark module)
  - _bmad-output/planning/ux-design-specification.md (AIGC watermark a11y + zero-width metadata)
  - _bmad-output/stories/m3-4-aigc-watermark-module.md
  - _bmad-output/stories/m3-4b-aigc-filter-contract-test.md
  - _bmad-output/stories/4-b-5-aigc-filter-invoke.md
  - _bmad-output/stories/8-b-1-aigc-filter-invoke.md
  - packages/shared-py/aigc_filter/__init__.py
  - tests/aigc/test_watermark.py
  - tests/aigc/test_filter.py
  - tests/contract/test_aigc_filter_module_contract.py
  - .github/workflows/ci.yml
---

# Story 8.B.7 - AIGC 水印 zero-width metadata 检测

Status: code-review

## Story

**作为** AIGC 合规与 shared module owner，
**我希望** `aigc_filter.detect_watermark(...)` 对模块生成的 zero-width Unicode metadata 做 100% 可识别、可回归、可审计的检测，
**从而** G12 的 hidden metadata 水印不会因为文本包装、重复处理、损坏尾部 payload、blocked 输出或 CI path filter 漂移而静默失效。

## Context

Epic 8.B.7 的原始 AC 是：Given AIGC 输出 / When watermark detector / Then 100% 识别 zero-width Unicode metadata。

Story M3.4 已经建立唯一 shared Python AIGC filter/watermark module：`packages/shared-py/aigc_filter/__init__.py`，包含 `filter(...)`、`add_watermark(...)`、`detect_watermark(...)`、visible marker、aria label、zero-width metadata、red-team/benign tests 和 CI job。Story M3.4b 已锁定模块 contract；Story 4.B.5 和 8.B.1 已把 Chat/backend/frontend 调用与展示链路闭合。

当前缺口不是新增 AIGC filter 或前端展示，而是把 detector 的覆盖从“少量 happy path”提升为 G12 可审计门禁：

- 当前 `tests/aigc/test_watermark.py` 只对 100 个良性输出和基础 tamper 做断言；没有覆盖 200 red-team blocked 输出、`add_watermark(...)` 直接生成的自定义 trace、visible marker 被移除但 zero-width metadata 保留、前后包装文本、多个 payload 中尾部损坏但前面仍有合法模块 payload、provider/metadata 字段漂移等边界。
- 当前 detector 只抽取最后一组 zero-width sentinel payload。若合法模块 watermark 后面又被拼上损坏 zero-width payload，detector 可能漏掉前面的合法模块 metadata。
- CI 已有 AIGC validation job，但本 story 必须明确确认 `tests/aigc/**`、`packages/shared-py/aigc_filter/**`、metrics script 和 CI 修改能触发 fail-closed validation。

## Scope

1. 扩展 `tests/aigc/test_watermark.py`，把 detector 100% 识别覆盖扩大到所有模块生成路径：
   - `filter(...)` 生成的 100 benign outputs。
   - `filter(...)` 生成的 200 red-team blocked safe outputs。
   - `add_watermark(...)` 直接生成的 outputs，包括调用方传入 trace id。
   - strict/loose tier、blocked/allowed、CJK/英文/emoji/换行/长文本样例。
2. 加固 `detect_watermark(...)` 的 zero-width payload 扫描：
   - 不依赖 visible marker。
   - 可以在文本前后包装、visible marker 被移除、或存在其他非模块 zero-width noise 时识别合法模块 payload。
   - 当文本包含多个 zero-width payload，且其中至少一个是模块生成的合法 payload 时，从右向左扫描并返回最右侧合法模块 payload；尾部损坏 payload 不应掩盖前面合法 payload。
   - 对损坏、缺字段、字段类型错误、provider 不匹配、非 JSON、bit length 错误、base64 错误和空 payload 返回 `present=False`，不得抛二次异常。
3. 保持 public contract 稳定：
   - 不新增 public API 或 `__all__` export，除非 contract snapshot 和 M3.4b tests 同步更新并有明确理由。
   - 不改变 `filter(...)` signature、`FilterResult` fields、`WatermarkMetadata` fields、visible marker、aria label、provider marker 或 contract metadata。
4. 保持过滤策略边界：
   - 不修改 red-team/benign prompt dataset、block rules、strict/loose 语义、blocked safe text、LLM moderation/provider call、AIGC filing 状态或 Chat/Web/UI 调用链路。
5. 闭合 CI：
   - 确认 `.github/workflows/ci.yml` 的 `aigc_filter` path filter 覆盖 shared module、`tests/aigc/**` 和 metrics helper；workflow 本身通过 `ci_or_root` 触发全部 validation。
   - AIGC validation job 必须 hard fail，不能 `continue-on-error`。
   - Metrics report must continue to emit deterministic red-team/benign counts and rates; this story must not make metrics depend on detector success as a substitute for explicit detector tests.

## Out Of Scope

- 不重写 AIGC filter policy、red-team/benign 数据集、false-positive gate、blocked 文案或 AIGC filing 流程。
- 不新增 public AIGC 合规页面、dashboard UI、Chat route、SSE 行为、frontend zero-width decoder 或 SDK detector。
- 不新增 runtime dependency、网络调用、LLM moderation client、数据库、Redis、Docker 或外部凭证。
- 不把 zero-width metadata 内容扩展为包含 prompt、用户、tenant、provider payload、secret 或审计私密数据。
- 不改变 M3.4b public contract，除非本 story 明确同步 contract snapshot 和 contract tests。

## Acceptance Criteria

1. `detect_watermark(...)` 对 `aigc_filter.filter(prompt, tier="strict").text` 生成的 200 个 red-team blocked outputs 达到 100% `present=True`，且返回的 `trace_id`、`module_version`、`provider` 与 `FilterResult.watermark` 一致。
2. `detect_watermark(...)` 对 `aigc_filter.filter(prompt, tier="strict").text` 生成的 100 个 benign outputs 达到 100% `present=True`，且 metadata 与 result 一致。
3. `detect_watermark(...)` 对 `aigc_filter.add_watermark(...)` 直接生成的 outputs 达到 100% `present=True`，包括调用方传入的 custom trace id；idempotent 再过滤后 trace id 不变。
4. Detector 不依赖 visible marker：从模块输出中移除 `"本回答由 AI 生成，仅供参考"` 后，只要 zero-width metadata 仍存在，detector 仍能识别并提取同一 trace/provider/module version。
5. Detector 能处理文本包装：前缀/后缀普通文本、换行、CJK、英文、emoji、Markdown-like 内容不影响合法 zero-width payload 识别。
6. Detector 能处理多个 payload：如果一个文本里存在合法模块 payload，同时尾部或其他位置存在损坏/非模块 zero-width payload，detector 从右向左扫描并返回最右侧合法模块 metadata；如果尾部 payload 损坏，则继续回退到前一个合法模块 payload；如果没有任何合法模块 payload，则返回 `present=False`。
7. Tamper handling deterministic：缺失 `trace_id`、缺失 `module_version`、缺失 `provider`、字段类型错误、provider 不匹配、非 JSON、bad base64、bit length 错误、空 payload、sentinel 顺序错误都返回 `WatermarkDetection(present=False, trace_id=None, module_version=None, provider=None)`，且不抛异常。
8. Trace/module validation 保持兼容但不放宽到任意 object：detector 接受当前模块生成的 `trc_[0-9a-f]{16}` trace id，也继续接受既有测试和调用方通过 `add_watermark(..., trace_id="trc_...")` 传入的 bounded custom trace；`trace_id`、`module_version`、`provider` 必须都是非空 string。
9. Public contract 不漂移：`tests/contract/test_aigc_filter_module_contract.py` 仍通过；`contract_metadata()`、`__all__`、filter signature、result fields 和 watermark fields 不因本 story 改变。
10. CI 闭环：`.github/workflows/ci.yml` 的 `aigc_filter` filter 覆盖 `packages/shared-py/aigc_filter/**`、`tests/aigc/**` 和 `scripts/report_aigc_filter_metrics.py`；workflow 本身通过 `ci_or_root` 触发全部 validation；`aigc-filter-validation` job 无 `continue-on-error`。
11. Metrics helper 不漂移：`scripts/report_aigc_filter_metrics.py` 继续从 `tests.aigc.datasets` 读取 canonical red-team/benign 数据集，并输出 deterministic count/rate；detector 100% 识别由 tests 显式断言，不以 metrics report 代替。
12. Workflow 状态必须按顺序推进：story 创建和 3 轮 pre-implementation review 完成后保持 `ready-for-dev`；开始代码实现前再把 story/sprint status 改为 `in-progress`；本地实现和初步门禁后改为 `code-review`；GitHub merge/sync 后才改为 `done`。
13. 本地验证至少运行：`uv run pytest tests/aigc -q`、`$env:PYTHONPATH='apps/auth-service/src;packages/shared-py'; uv run pytest tests/contract/test_aigc_filter_module_contract.py -q`、`uv run ruff check packages/shared-py/aigc_filter tests/aigc scripts/report_aigc_filter_metrics.py`、`uv run mypy packages/shared-py`、`git diff --check`。
14. 实施后代码审查覆盖边界问题、漂移问题、数据一致性、依赖一致性、CI 闭环、contract stability、detector false positive/false negative 和测试充分性；发现必须修复或记录。
15. PR 通过 GitHub CI、合并到 `main`、远程分支删除、本地 `main` 同步后，才能把 story 与 sprint status 标记为 `done` 并推送状态同步 commit。

## Tasks / Subtasks

- [x] T1: 扩展 detector RED tests（AC: 1-7）
  - [x] 覆盖 200 red-team blocked outputs 的 detector 100% 识别与 metadata 一致性。
  - [x] 覆盖 100 benign outputs 的 detector 100% 识别与 metadata 一致性。
  - [x] 覆盖 `add_watermark(...)` custom trace、idempotent filter trace preservation。
  - [x] 覆盖 visible marker removal、文本包装、多语言/emoji/换行。
  - [x] 覆盖多 payload 场景：多个合法 payload 时选择最右侧合法 payload；合法 payload + 尾部损坏 payload 时仍回退识别前一个合法 metadata。
  - [x] 覆盖缺字段/provider drift/non-json/bad bits/empty payload/sentinel ordering。

- [x] T2: 加固 detector 实现（AC: 4-9）
  - [x] 将 extraction 从“只看最后一组 sentinel”改为从右向左扫描候选 zero-width payload。
  - [x] 对每个候选 payload 做 decode + JSON + provider/field validation，返回最右侧合法模块 payload。
  - [x] 要求 `trace_id`、`module_version`、`provider` 为非空 string；拒绝缺字段、`None`、list/dict/number 类型和非模块 provider。
  - [x] 保持 `WatermarkDetection` public shape 和 public exports 不变。
  - [x] 保持 `add_watermark(...)` idempotency 和 blocked existing watermark replacement 行为不回退。

- [x] T3: CI/path filter 闭环（AC: 10-13）
  - [x] 检查并必要时补齐 `aigc_filter` path filter。
  - [x] 确认 `aigc-filter-validation` hard fail，无 `continue-on-error`。
  - [x] 确认 metrics helper 仍引用 canonical datasets，不复制数据集。
  - [x] 开始实现前把 story/sprint status 从 `ready-for-dev` 改为 `in-progress`；实现门禁后改为 `code-review`。
  - [x] 跑 focused gates 并记录结果。

- [ ] T4: Review and GitHub sync（AC: 14-15）
  - [x] 完成 post-implementation code review 并修复 findings。
  - [ ] Commit、push、创建 PR、等待 CI、merge、删除远端分支、同步 local main。
  - [ ] 合并同步后更新 story/sprint status 为 done 并推送 status-sync commit。

## Dev Notes

### Existing Files And Current State

- `packages/shared-py/aigc_filter/__init__.py`
  - 当前 detector 使用 `_extract_zero_width_payload(text)` 从最后一组 zero-width sentinel 中抽取 payload。
  - 当前 `detect_watermark(...)` 只验证 `provider == PROVIDER_MARKER` 且 `trace_id` 是 string。
  - 本 story 可修改内部 extraction/decode/validation helper，但不应改变 public API、constants、result fields 或 provider marker。

- `tests/aigc/test_watermark.py`
  - 当前覆盖基础 extraction、100 benign outputs、idempotency、missing/tampered、visible marker/aria label。
  - 本 story 主要扩展此文件，加入 red-team blocked、multi payload、visible marker removal 和 deterministic tamper matrix。

- `tests/aigc/test_filter.py`
  - 当前覆盖 200 red-team block rate、100 benign false-positive rate、strict/loose、invalid tier、blocked unsafe text、existing unsafe watermark replacement 和 self-loop metadata。
  - 本 story 不应改 prompt dataset 或 filter policy；只可引用数据集生成 detector coverage。

- `tests/contract/test_aigc_filter_module_contract.py`
  - 当前锁定 public contract metadata、signature、fields、exports 和 version/deprecation policy。
  - 本 story 本地 gate 必须保持该 contract test 通过。

- `.github/workflows/ci.yml`
  - 当前已有 `aigc-filter-validation` job，运行 `uv run pytest tests/aigc -v` 和 metrics report。
  - 本 story 需要检查 path filter 是否包含 metrics helper 和 workflow 本身，避免 detector 变更不触发 gate。

### Implementation Guardrails

- Treat zero-width metadata as the detector source of truth; visible marker is an accessibility/user-visible redundancy, not detector dependency.
- The detector should scan candidates from right to left, matching the existing "last watermark wins" behavior when the last payload is valid while still recovering from corrupted trailing noise.
- Validation should be strict enough to reject non-module payloads and malformed field types, while staying compatible with existing `add_watermark(..., trace_id="trc_...")` custom traces.
- Avoid exposing private decoder helpers publicly. Internal helpers may change freely if contract tests remain green.
- Do not remove or rename current `_ZERO_WIDTH_*` sentinels; existing persisted outputs depend on them.
- Keep decode deterministic and offline; stdlib only.

### Suggested Commands

```powershell
$env:PYTHONPATH='packages/shared-py'; uv run pytest tests/aigc -q
$env:PYTHONPATH='apps/auth-service/src;packages/shared-py'; uv run pytest tests/contract/test_aigc_filter_module_contract.py -q
uv run ruff check packages/shared-py/aigc_filter tests/aigc scripts/report_aigc_filter_metrics.py
uv run mypy packages/shared-py
git diff --check
```

## Definition Of Done

- Story has passed 3 pre-implementation adversarial review rounds with revisions recorded.
- Detector identifies 100% of module-generated zero-width metadata across filter/add_watermark, benign/red-team, allowed/blocked and custom trace paths.
- Detector handles visible marker removal, text wrapping, multiple payloads and deterministic tamper cases without exceptions.
- AIGC public module contract remains stable and contract tests pass.
- CI path filters close the AIGC detector validation loop.
- Local gates listed above pass.
- Post-implementation code review completed and findings fixed or explicitly documented.
- Story and sprint status become `done` only after PR CI green, merge, remote branch deletion, local main sync and a separate status-sync commit.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-b-7-aigc-watermark-detect`.
- Baseline commit: `d23bed38edbd56541328410e68274dc8cccaae89`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base `bmad-create-story/customize.toml`, found no project/user overrides.
- Story creation analyzed Epic 8.B.7 source AC, M3.4 G12 source AC, M3.4/M3.4b story history, 4.B.5/8.B.1 AIGC call/display boundaries, current detector implementation, AIGC tests, contract tests and CI validation job.
- 2026-06-03 - Completed three pre-implementation adversarial review rounds and moved story to `in-progress` before code changes.
- 2026-06-03 - RED confirmed: extended detector tests failed on corrupted trailing payload recovery and malformed metadata acceptance.
- 2026-06-03 - GREEN implementation changed detector extraction to right-to-left candidate scanning, strict module metadata validation, and `trc_` trace prefix validation without changing public exports.
- 2026-06-03 - Local validation passed: `uv run pytest tests/aigc -q` (37 passed), contract module test (9 passed), ruff, mypy, and `git diff --check`.

### Completion Notes List

- Initial story created; pending three pre-implementation adversarial review rounds before implementation.
- Pre-implementation adversarial reviews completed; implementation started.
- Detector now identifies 100% of module-generated benign/red-team/custom-trace outputs covered by tests.
- Detector now recovers from corrupted trailing payloads by scanning right-to-left and returning the rightmost valid module payload.
- Detector now rejects missing/empty/type-wrong metadata fields, non-module provider values, broken payloads and non-`trc_` trace IDs without raising.
- Post-implementation review found and fixed one trace-validation gap; local gates passed after the patch.

### File List

- `_bmad-output/stories/8-b-7-aigc-watermark-detect.md`
- `_bmad-output/stories/sprint-status.yaml`
- `packages/shared-py/aigc_filter/__init__.py`
- `tests/aigc/test_watermark.py`

## Change Log

- 2026-06-03 - Story created for 8.B.7 AIGC zero-width watermark detector coverage and CI closure.
- 2026-06-03 - Completed three pre-implementation adversarial review rounds; story status moved to in-progress for implementation.
- 2026-06-03 - Implemented detector scanning/validation hardening, expanded AIGC watermark tests, completed post-implementation review patch, passed local gates, and moved story to code-review pending GitHub sync.

## Post-Implementation Code Review

Outcome: Approved after patch.

Findings fixed:

- [x] [Review][Patch] Detector accepted any non-empty string `trace_id` when provider/module fields were otherwise valid, while the story required compatibility with bounded `trc_...` traces rather than arbitrary strings. Added a malformed metadata test for `trace_id="not_trc"` and required `trace_id.startswith("trc_")`.

Residual risk:

- Detector validation intentionally accepts existing bounded custom traces such as `trc_custom_trace_001`; it does not enforce only module-generated `trc_[0-9a-f]{16}` because `add_watermark(..., trace_id=...)` is already part of the public behavior covered by tests.

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary And Duplicate-Implementation Review

Findings:

1. Initial story did not define which payload wins when multiple valid module payloads are present; implementation could choose first, last, or arbitrary valid metadata and still pass vague tests.
2. CI wording incorrectly implied `.github/workflows/ci.yml` itself should be added to the `aigc_filter` path filter, but the existing CI architecture intentionally routes workflow/root changes through `ci_or_root`.
3. Story scope could still be read as permission to change `filter(...)` metadata generation; the real target is detector extraction/validation and tests.

Revision after Round 1:

- Added deterministic right-to-left candidate scanning and "rightmost valid module payload wins" semantics, including recovery from corrupted trailing payloads.
- Corrected CI closure wording: `aigc_filter` covers module/tests/metrics helper, while workflow changes trigger via `ci_or_root`.
- Reaffirmed public contract and filter policy boundaries in Scope, Out of Scope, AC8 and T2.

### Round 2 - Drift, Data Consistency, And False-Positive Review

Findings:

1. Existing detector converts `module_version` through `str(raw.get(...))`, which would turn missing metadata into `"None"` and let malformed payloads look valid.
2. Story did not explicitly reject non-string JSON field values; a list/dict/number trace or provider could leak through if only provider equality was checked in one branch.
3. Trace validation needed to avoid two extremes: accepting arbitrary objects or breaking existing `add_watermark(..., trace_id="trc_...")` custom-trace use.

Revision after Round 2:

- Required `trace_id`, `module_version` and `provider` to be non-empty strings; missing/typed-wrong fields now fail closed.
- Added explicit tamper cases for missing provider/module version, field type errors and non-module providers.
- Clarified trace validation compatibility: module-generated `trc_[0-9a-f]{16}` and bounded existing custom `trc_...` traces remain accepted.

### Round 3 - CI Closure, Metrics, And Workflow Review

Findings:

1. AIGC metrics report imports canonical datasets today; without an explicit guard, a later edit could duplicate datasets and recreate the M3.4 post-review drift issue.
2. Detector 100% recognition should be proven by focused tests, not inferred from the metrics report that currently measures block/false-positive rates only.
3. Story lifecycle needed an explicit status-order rule so implementation does not start while records still imply only `ready-for-dev`, and final `done` remains gated on GitHub sync.

Revision after Round 3:

- Added metrics helper non-drift AC and task requirement to keep importing `tests.aigc.datasets`.
- Stated metrics report is not a substitute for detector recognition tests.
- Added workflow-state sequencing AC: `ready-for-dev` after reviews, `in-progress` before implementation, `code-review` after local gates, `done` only after PR merge/sync/status commit.
