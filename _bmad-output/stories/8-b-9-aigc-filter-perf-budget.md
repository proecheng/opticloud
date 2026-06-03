---
story_key: 8-b-9-aigc-filter-perf-budget
epic_num: 8
story_num: B.9
epic_name: AIGC Filter + Rate Limit + Error Codes RFC 7807
status: done
baseline_commit: adad5d55702c5b15e4b301993cc12e8874200a39
priority: High
type: G12/NFR-P AIGC filter performance budget
created_by: bmad-create-story
created_at: 2026-06-03
sources:
  - _bmad-output/planning/epics.md (Epic 8.B / Story 8.B.9)
  - _bmad-output/stories/m3-4-aigc-watermark-module.md
  - _bmad-output/stories/m3-4b-aigc-filter-contract-test.md
  - _bmad-output/stories/8-b-1-aigc-filter-invoke.md
  - _bmad-output/stories/8-b-7-aigc-watermark-detect.md
  - _bmad-output/stories/8-b-8-redteam-tests-m5-200.md
  - packages/shared-py/aigc_filter/__init__.py
  - tests/aigc/datasets.py
  - tests/aigc/test_filter.py
  - tests/aigc/test_watermark.py
  - scripts/report_aigc_filter_metrics.py
  - docs/runbooks/chat-staging-load-test.md
  - scripts/validate_chat_load_plan.py
  - .github/workflows/ci.yml
---

# Story 8.B.9 - AIGC filter performance budget

Status: done

## Story

**作为** AIGC 合规与 Chat latency owner，
**我希望** `aigc_filter.filter(...)` 在 canonical AIGC red-team/benign corpus 上具备可执行的 P95 <100ms 性能预算门禁，
**从而** AIGC filter 的本地开销不会吃掉 Chat first-token P95 <3s 的硬预算，并且后续规则、水印、detector 或合同测试变更不会让性能漂移静默进入 CI。

## Context

Epic 8.B.9 的原始 AC 是：Given filter 调用 / When 单次延迟 P95 / Then <100ms（不阻塞 Chat first-token <3s）。

当前仓库状态：

- `packages/shared-py/aigc_filter/__init__.py` 是唯一 AIGC filter/watermark 实现位置；M3.4 明确禁止 Chat/Critic/Web 复制 service-local filter。
- M3.4b 已锁定 public contract：`filter(text, tier="strict", context=None)`、`FilterResult` fields、watermark fields、`contract_metadata()` 和 183 天 deprecation policy。
- 8.B.7 已加固 zero-width detector；8.B.8 则是 Critic calibration story，不应把 Critic 数据或 gate 混到 AIGC filter performance。
- `tests/aigc/datasets.py` 当前有 exactly 200 red-team prompts 和 exactly 100 benign prompts，是 AIGC filter 质量和性能预算的 canonical corpus。
- `scripts/report_aigc_filter_metrics.py` 只输出 deterministic quality metrics，不测 latency。
- Chat G6 runbook 明确 first-token hard gate 为 P95 <3000ms，但真实 Chat pass 需要 operator-run staging evidence；本 story 只能证明 filter-only overhead，不得伪称端到端 Chat first-token pass。

## Scope

1. 增加 filter-only performance budget report/benchmark。
   - 使用 canonical AIGC corpus：200 red-team + 100 benign prompts。
   - Primary 单次 operation 定义为 `aigc_filter.filter(prompt, tier="strict")`，输入为未加水印 canonical prompt。
   - Secondary regression path 覆盖 already-watermarked input：先对固定小样本生成 watermark，再测一次 `filter(watermarked_text, tier="strict")`，防止 detector/idempotency path 完全漏测；secondary path 作为 report evidence，不取代 primary P95 gate。
   - 使用 `time.perf_counter_ns()`，先 warm up，再按固定 repeat count 测量；repeat count 应导出为脚本常量，测试断言 call count 与 repeat count 一致。
   - 输出 JSON report，包含 corpus counts/hash、sample count、p50/p95/p99/max、budget、pass/fail、Chat first-token budget relation。
   - 输出 JSON 必须包含 `evidence_scope="filter_only_overhead"`、`end_to_end_chat_first_token_passed=false` 和 `requires_staging_chat_evidence=true`，测试必须断言这些字段。
   - 输出 JSON 中的 measured latency 仅用于当前 run 的 pass/fail，不要求与 committed manifest 数值 parity。
   - Report 不得包含 raw prompt、tenant、provider payload、secret、timestamp、absolute local path 或机器身份。

2. 增加 committed performance budget manifest。
   - 放在 `reports/aigc-filter/performance-budget.json`。
   - Manifest 描述 scope/methodology/budget，不保存易漂移 wall-clock 实测值。
   - Manifest 必须明确 `filter_only_overhead=true` 和 `not_end_to_end_chat_evidence=true`。
   - Manifest 必须把 `filter_p95_budget_ms=100` 与 `chat_first_token_hard_gate_ms=3000` 的关系写清楚：filter 预算最多占 Chat hard gate 3.34%。

3. 增加 tests/CI gate。
   - 新增 `tests/aigc/test_performance_budget.py`。
   - Tests 至少验证 manifest 语义、script report shape、canonical corpus counts/hash、no raw prompt leak、P95 <100ms 和 budget relation。
   - Tests 不得断言小于 1ms/5ms 之类微阈值；唯一 latency hard gate 是 P95 <100ms。
   - Tests 必须能 monkeypatch/单元验证 percentile 与 pass/fail 逻辑，不只依赖一条 live benchmark。
   - `.github/workflows/ci.yml` 的 `aigc_filter` path filter 必须覆盖新 performance script、manifest、`tests/aigc/**`。
   - `aigc-filter-validation` job 必须 hard fail，并运行 performance budget script；不得 `continue-on-error`。
   - Performance script 必须只使用 stdlib + 已存在的 `aigc_filter` / `tests.aigc.datasets`，不得新增 Python/package dependency。

4. 保持边界稳定。
   - 不修改 AIGC filter public API、contract snapshot、visible marker、aria label、provider marker、blocked text、strict/loose 语义或 prompt datasets。
   - 不新增 runtime dependency、HTTP/LLM call、DB、Redis、Docker、Locust 或 staging Chat 调用。
   - 不把本 story 当作 G6 端到端 Chat latency evidence；Chat G6 仍由 `docs/runbooks/chat-staging-load-test.md` 和 operator evidence 闭合。
   - 若实现过程中发现 `aigc_filter` 本身需要性能优化，必须先证明 public contract tests 仍通过；不要通过放宽 filter/detector/security behavior 来达成性能预算。

## Out Of Scope

- 不做真实 Chat SSE/load test、Locust run、staging evidence、Grafana artifact 或 G6 pass claim。
- 不修改 Chat service runtime、API gateway、LLM router、Critic service、sandbox runner、frontend 或 SDK。
- 不扩展 AIGC policy rules、red-team/benign prompt sets、watermark contract、detector contract 或 AIGC filing 状态。
- 不引入第三方 benchmark dependency；不把 CI 性能结果和本地机器结果做精确数值 parity。
- 不把 raw prompts、user content、provider payload、tenant identifiers 或 credentials 写入 performance report/manifest。

## Acceptance Criteria

1. 新增 performance report command，例如 `scripts/report_aigc_filter_performance.py`，可离线运行并输出 JSON。
2. Report 使用 canonical `tests.aigc.datasets.RED_TEAM_PROMPTS` 和 `BENIGN_PROMPTS`；assert red-team exactly 200、benign exactly 100，不复制 prompt 数据集。
3. Report primary operation 明确定义为 `aigc_filter.filter(prompt, tier="strict")`，scope 为 `filter_only_overhead`；secondary operation 明确为 already-watermarked input regression path。
4. Report 使用 warmup + fixed repeat count；measured call count 必须等于 `(200+100) * repeat_count`。
5. Report 使用 nearest-rank P95 或等价稳定 percentile 方法，且 `measurement.p95_ms < 100.0` 才 pass；tests 必须覆盖 exact-threshold 100.0ms fail case。
6. Report 包含 `chat_first_token_hard_gate_ms=3000.0`，并证明 `100ms / 3000ms <= 0.0334`；必须显式输出 `end_to_end_chat_first_token_passed=false` 和 `requires_staging_chat_evidence=true`，不得声明 Chat end-to-end first-token passed。
7. Report 不含 raw prompt 文本、tenant/provider payload、secret-like keys、timestamp、hostname、username 或 absolute local path。
8. Committed manifest `reports/aigc-filter/performance-budget.json` 存在，内容为 deterministic methodology/budget manifest，不含易漂移 wall-clock measurements。
9. Manifest 明确 `filter_only_overhead=true`、`not_end_to_end_chat_evidence=true`、`filter_p95_budget_ms=100.0`、`chat_first_token_hard_gate_ms=3000.0` 和 source story `8.B.9`。
10. 新增 `tests/aigc/test_performance_budget.py` 覆盖 report shape、budget pass/fail semantics、manifest no-leak、canonical corpus counts/hash、primary P95 <100ms live gate、secondary already-watermarked path evidence 和 Chat no-pass-claim fields。
11. Performance report 的 `corpus_sha256` 必须由 canonical corpus 的 stable JSON representation 计算；tests 必须证明 manifest/script 使用同一 corpus hash，不因数据集顺序或复制文本漂移。
12. 现有 AIGC quality/watermark tests 仍通过；`scripts/report_aigc_filter_metrics.py` 继续输出 deterministic quality metrics。
13. Public contract 不漂移：`tests/contract/test_aigc_filter_module_contract.py` 仍通过；本 story 不修改 `AIGC_CONTRACT_VERSION`。
14. CI `aigc-filter-validation` hard-gated 运行 `tests/aigc`、quality metrics report 和 performance budget report；无 `continue-on-error`。
15. CI `aigc_filter` path filter 覆盖 `packages/shared-py/aigc_filter/**`、`tests/aigc/**`、`scripts/report_aigc_filter_metrics.py`、new performance script 和 `reports/aigc-filter/**`。
16. 本地验证至少运行：`uv run pytest tests/aigc -q`、`uv run python scripts/report_aigc_filter_metrics.py`、`uv run python scripts/report_aigc_filter_performance.py`、contract module test、ruff、mypy、full pre-commit 和 `git diff --check`。
17. 实施后代码审查覆盖边界问题、漂移问题、数据一致性、依赖一致性、CI 闭环、flaky perf risk、no-leak、Chat SLO claim boundary 和测试充分性；发现必须修复或记录。
18. PR 通过 GitHub CI、合并到 `main`、远程分支删除、本地 `main` 同步后，才能把 story 与 sprint status 标记为 `done` 并推送 status-sync commit。
19. Story/sprint status flow 必须为 `ready-for-dev -> in-progress -> code-review -> done`；`done` 只能在 PR merge/sync 后通过单独 status-sync commit 推送。

## Tasks / Subtasks

- [x] T1: 增加 performance budget report command（AC: 1-7）
  - [x] 使用 canonical AIGC red-team/benign corpus，不复制 prompts。
  - [x] 设计 warmup、repeat count、nearest-rank percentile 和 P95 <100ms gate。
  - [x] 将 repeat count、warmup count、budget constants 暴露为脚本常量供 tests 校验。
  - [x] 覆盖 primary unwatermarked corpus path 和 secondary already-watermarked regression path。
  - [x] 输出 JSON report，含 corpus hash/count、sample count、latency stats、budget pass/fail、Chat budget relation。
  - [x] 输出 Chat no-pass-claim fields：`end_to_end_chat_first_token_passed=false`、`requires_staging_chat_evidence=true`。
  - [x] Report 不输出 prompt text、timestamp、hostname、username、absolute path 或 secret-like fields。

- [x] T2: 增加 committed methodology manifest（AC: 8-9）
  - [x] 创建 `reports/aigc-filter/performance-budget.json`。
  - [x] Manifest 只保存 deterministic budget/methodology，不保存 wall-clock measurements。
  - [x] 明确 filter-only scope 与 non-Chat-evidence boundary。

- [x] T3: 增加 tests（AC: 10-12）
  - [x] 增加 `tests/aigc/test_performance_budget.py`。
  - [x] 验证 corpus count/hash、report shape、P95 gate、exact-threshold fail case、percentile helper、secondary path evidence、manifest no-leak、budget relation、Chat no-pass-claim fields 和 no raw prompt leak。
  - [x] 保持 `tests/aigc/test_filter.py`、`tests/aigc/test_watermark.py` 和 module contract test 通过。

- [x] T4: CI/path filter 闭环（AC: 13-15）
  - [x] 更新 `.github/workflows/ci.yml` path filter 覆盖 performance script/report。
  - [x] `aigc-filter-validation` 增加 performance budget command。
  - [x] 确认 implementation 不新增依赖，不触发 DB/Redis/Docker/Locust/staging Chat。
  - [x] 跑本地 validation commands 并记录。

- [x] T5: Review and GitHub sync（AC: 16-19）
  - [x] 完成 post-implementation code review 并修复 findings。
  - [x] Commit、push、创建 PR、等待 CI、merge、删除远端分支、同步 local main。
  - [x] 合并同步后更新 story/sprint status 为 done 并推送 status-sync commit。

## Dev Notes

### Existing Files And Current State

- `packages/shared-py/aigc_filter/__init__.py`
  - 当前 filter 是 stdlib/offline deterministic implementation；主要成本来自 regex matching、SHA256 trace、JSON/base64 zero-width watermark encode/decode。
  - 本 story 不应修改 public API 或 contract metadata，除非后续 review 发现无法避免；目前无此必要。

- `tests/aigc/datasets.py`
  - Canonical AIGC corpus: `RED_TEAM_PROMPTS` exactly 200，`BENIGN_PROMPTS` exactly 100。
  - Performance script/tests 应 import 这里，不复制数据。

- `scripts/report_aigc_filter_metrics.py`
  - 只输出 quality metrics。Performance report 应新增脚本，不把 latency 混入 quality-only report，避免 dashboard contract 漂移。
  - New performance script may share canonical corpus/hash helpers internally if useful, but must not change quality report output contract.

- `.github/workflows/ci.yml`
  - 当前 `aigc-filter-validation` 运行 `uv run pytest tests/aigc -v` 和 `scripts/report_aigc_filter_metrics.py`。
  - 需要加入 performance command，并把 new script/report 加到 `aigc_filter` path filter。
  - 修改 workflow 本身会通过 `ci_or_root` 触发全部 validation；本 story 不应使用 `continue-on-error` 或 soft gate。

- `docs/runbooks/chat-staging-load-test.md`
  - G6 hard gate: first-token P95 <3000ms。
  - 本 story 只证明 filter overhead budget；真实 Chat pass 仍依赖 operator evidence manifest。

### Implementation Guardrails

- Performance gate 用 P95，不用 max，避免 CI 偶发调度尖峰造成不必要 flake；max 只作为 report 信息输出。
- Threshold 是 `<100ms`，不是 `<=100ms`。
- Repeat count 不应过大；目标是 lightweight CI gate，不是 full load test。
- 不在 committed manifest 中保存当前机器测量值，避免后续 CI 与本地数值漂移。
- Corpus hash 可用于证明数据一致性，但 report 不得输出 raw prompt text。
- Script 失败时应 exit non-zero，CI hard fail。
- The primary P95 budget gate is for unwatermarked filter calls over the full canonical corpus; the secondary already-watermarked path exists to prevent detector/idempotency regressions from being invisible, but it must not be used to dilute the primary gate or to claim Chat latency success.
- Avoid statistical overfitting: do not calibrate thresholds against local microsecond values. The only hard perf threshold is the product AC's 100ms P95 budget.
- Dependency closure is part of the story: use stdlib timing/stat logic and existing repo modules only. Do not add pyperf, pytest-benchmark, Locust, numpy/pandas or any network/staging dependency.
- Lifecycle closure is part of the story: local `code-review` is allowed before GitHub sync, but `done` is forbidden until PR CI passes, branch is merged, remote branch deleted, and local `main` is synced.

### Suggested Commands

```powershell
$env:PYTHONPATH='packages/shared-py'; uv run pytest tests/aigc -q
$env:PYTHONPATH='packages/shared-py'; uv run python scripts/report_aigc_filter_metrics.py
$env:PYTHONPATH='packages/shared-py'; uv run python scripts/report_aigc_filter_performance.py
$env:PYTHONPATH='apps/auth-service/src;packages/shared-py'; uv run pytest tests/contract/test_aigc_filter_module_contract.py -q
uv run ruff check packages/shared-py/aigc_filter tests/aigc scripts/report_aigc_filter_metrics.py scripts/report_aigc_filter_performance.py
uv run mypy packages/shared-py
uv tool run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

## Definition Of Done

- Story has passed exactly 3 pre-implementation adversarial review rounds with revisions recorded after each round.
- AIGC filter performance budget report exists and enforces P95 <100ms over canonical corpus.
- Committed manifest documents deterministic methodology and Chat first-token budget relation without claiming end-to-end Chat pass.
- Tests and CI close performance drift, dataset consistency, no-leak and dependency boundaries.
- Local gates and GitHub CI pass.
- Post-implementation code review completed and findings fixed or explicitly documented.
- Story and sprint status become `done` only after PR CI green, merge, remote branch deletion, local main sync and a separate status-sync commit.

## Story Review Log

### Round 1: Boundary Semantics Review

Findings fixed:
- The initial story defined only `filter(prompt)` as the measured operation, which could miss the already-watermarked idempotency/detector path introduced by earlier watermark stories. Added secondary already-watermarked regression evidence while keeping the primary full-corpus P95 gate unchanged.
- The initial story said not to claim Chat end-to-end pass, but did not require machine-checkable no-pass-claim fields. Added `end_to_end_chat_first_token_passed=false` and `requires_staging_chat_evidence=true` to report requirements and tests.
- Clarified that secondary path evidence cannot dilute the primary P95 gate or substitute for staging Chat evidence.

Status: PASS after fixes.

### Round 2: Performance Determinism / Drift Review

Findings fixed:
- The initial story allowed a live benchmark but did not forbid tiny environment-sensitive thresholds. Added a rule that the only latency hard gate is P95 <100ms and tests must not assert micro-thresholds.
- The initial story did not require unit coverage for percentile/pass-fail logic. Added exact-threshold 100.0ms fail case and percentile helper coverage so correctness does not depend only on current machine speed.
- The initial story did not pin repeat/warmup constants as test-visible values. Added constant exposure and call-count assertions to reduce benchmark drift.
- The initial story mentioned corpus hash but did not require parity between manifest and script. Added stable corpus hash parity requirements.

Status: PASS after fixes.

### Round 3: Dependency / Closure Review

Findings fixed:
- The story did not explicitly ban benchmark dependencies such as pyperf/pytest-benchmark or staging load-test tools. Added a stdlib-only dependency closure requirement and banned DB/Redis/Docker/Locust/staging Chat dependencies.
- The story allowed implementation to optimize the filter but did not state security/contract behavior cannot be weakened to hit the budget. Added contract-preservation and no behavior-relaxation guardrails.
- CI closure mentioned the new command but did not explicitly forbid soft gates. Added no `continue-on-error` / hard-fail wording for the performance gate.
- Lifecycle closure existed in ACs but not as a distinct status-flow invariant. Added explicit `ready-for-dev -> in-progress -> code-review -> done` flow and separate status-sync commit requirement after merge.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-b-9-aigc-filter-perf-budget`.
- Baseline commit: `adad5d55702c5b15e4b301993cc12e8874200a39`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base skill instructions and project config.
- Story creation analyzed Epic 8.B.9 source AC, M3.4/M3.4b/8.B.7 AIGC module history, 8.B.1 Chat invocation boundary, 8.B.8 non-AIGC calibration boundary, current AIGC datasets/tests/scripts, Chat G6 runbook and CI validation job.
- 2026-06-03 - Completed exactly three pre-implementation adversarial review rounds with story revisions after each round; moved story to `in-progress` before implementation.
- 2026-06-03 - Implemented `scripts/report_aigc_filter_performance.py` with stdlib `perf_counter_ns`, warmup/repeat constants, canonical corpus hash, nearest-rank percentile, primary full-corpus P95 budget gate, secondary already-watermarked regression evidence and Chat no-pass-claim fields.
- 2026-06-03 - Added deterministic methodology manifest `reports/aigc-filter/performance-budget.json` without wall-clock measurements.
- 2026-06-03 - Added `tests/aigc/test_performance_budget.py` covering manifest semantics, corpus hash, percentile/exact-threshold fail logic, live P95 gate, no raw prompt leak, budget relation and Chat no-pass-claim fields.
- 2026-06-03 - Updated CI `aigc_filter` path filter and `aigc-filter-validation` job to run the performance budget command as a hard gate.
- 2026-06-03 - Local validation passed: AIGC tests (45 passed), quality metrics report, performance budget report (primary P95 observed below 1ms in final run), module contract test (9 passed), ruff, mypy, full pre-commit, and `git diff --check`.
- 2026-06-03 - Post-implementation adversarial code review completed; one decision-closure finding fixed by making report `decision` depend on both primary P95 and budget-to-Chat relation, with regression test added.
- 2026-06-03 - GitHub PR #160 first CI run passed all jobs except lint. Lint findings were CI ruff-format drift in `tests/aigc/test_performance_budget.py` and detect-secrets false positives on the public AIGC corpus SHA-256 in the test and manifest. Fixed by applying ruff-format output and adding the public corpus SHA-256 to `.pre-commit-config.yaml` `--exclude-secrets`; full local pre-commit passed afterward.
- 2026-06-03 - GitHub PR #160 second CI run passed all checks, including `aigc-filter-validation`, `lint`, `mypy`, `contract-test`, `chat-service-test` and `shared-py-test`.
- 2026-06-03 - PR #160 was squash-merged to `main` at `c644b740e544da46b0c431c76045a0392883d9ec`; remote branch `codex/8-b-9-aigc-filter-perf-budget` was deleted; local `main` synced with `origin/main`.

### Completion Notes List

- Initial story created.
- Exactly three pre-implementation adversarial review rounds completed; implementation started.
- Performance budget report script, manifest, tests and CI gate implemented.
- Local gates passed after post-review fix.
- GitHub lint fix applied for CI ruff-format parity and public corpus SHA-256 detect-secrets allowlist.
- PR #160 passed GitHub CI, merged to `main`, remote branch deleted, and local `main` synced.
- Story and sprint status marked `done` in separate status-sync step after merge/sync.

### File List

- `_bmad-output/stories/8-b-9-aigc-filter-perf-budget.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.pre-commit-config.yaml`
- `.github/workflows/ci.yml`
- `reports/aigc-filter/performance-budget.json`
- `scripts/report_aigc_filter_performance.py`
- `tests/aigc/test_performance_budget.py`

## Post-Implementation Code Review

### Blind Hunter - Boundary And Regression Review

Findings:

- No remaining issue found in scope boundary: implementation adds a standalone offline report script and does not modify `packages/shared-py/aigc_filter`, contract metadata, public exports, filter semantics, datasets, Chat service, LLM router or staging load-test assets.
- No remaining issue found in no-leak handling: committed manifest has no prompt text or live measurement data; report/tests assert no canonical raw prompt, secret-like key, timestamp, hostname, username or absolute local path leaks.

### Edge Case Hunter - Performance And Drift Review

Findings:

- P2 fixed: initial implementation set `decision="pass"` from primary P95 only. If the budget-to-Chat relation drifted, a report could have `decision=pass` while `passes_budget_relation=false`. Fixed by making `decision` depend on both primary P95 and budget relation, and added a relation-fail regression test.
- No remaining issue found in percentile semantics: nearest-rank P95 is unit-tested, and exact-threshold `100.0ms` fails because the gate is strict `<100ms`.
- No remaining issue found in CI flake profile: tests avoid micro-thresholds and only hard-gate the product AC threshold.

### Acceptance Auditor - AC Closure Review

Findings:

- No remaining issue found against AC 1-15: report command, canonical corpus, primary/secondary operations, warmup/repeat count, P95 gate, Chat no-pass-claim fields, deterministic manifest, tests and CI path filter/job are present.
- No remaining issue found against AC 16: local validation commands passed and are recorded above.
- CI lint follow-up fixed: ruff-format parity is committed, and the public corpus SHA-256 is allowlisted in detect-secrets using the repo's existing public-hash pattern.
- AC 18-19 closed: PR #160 passed GitHub CI, was squash-merged to `main`, remote branch was deleted, local `main` was synced, and this status-sync step marks story/sprint `done`.

Outcome: PASS after fixes.

## Change Log

- 2026-06-03 - Story created for 8.B.9 AIGC filter P95 <100ms performance budget.
- 2026-06-03 - Completed three pre-implementation adversarial review rounds; story status moved to in-progress for implementation.
- 2026-06-03 - Implemented performance budget script/manifest/tests/CI; post-implementation review completed and story moved to code-review pending GitHub sync.
- 2026-06-03 - Fixed PR #160 lint findings: ruff-format parity and public corpus SHA-256 detect-secrets allowlist.
- 2026-06-03 - PR #160 passed CI, merged to main, remote branch deleted, local main synced; story moved to done.
