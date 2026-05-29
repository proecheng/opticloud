# Story 4.B.7: Critic 红队测试集运行

Status: done

owner: Chat Platform / Critic Safety / AI Compliance

## Story

作为 Chat Platform / Critic Safety owner，
我希望 CI 在 4.B 集成层复用 Story M3.4 的 200 条 red-team prompt 和 100 条 benign prompt，
以便 Critic/Chat 用户可见 NL 出口的 AIGC filter 调用路径持续证明拦截率 >=98%、误拦率 <=2%，且不复制过滤规则、不漂移 M3.4 数据集、不误开放 public Chat 或 4.C 能力。

## Acceptance Criteria

1. 复用 M3.4 canonical 数据集和 filter contract。
   - 必须从 `tests/aigc/datasets.py` 导入 `RED_TEAM_PROMPTS` 和 `BENIGN_PROMPTS`，不得复制 prompt 数据集。
   - 必须通过 4.B.5 的 service adapter `chat_service.aigc_watermark.apply_aigc_filter_to_summary(...)` 运行测试，而不是在 test 中直接重写过滤逻辑。
   - 不得修改 `packages/shared-py/aigc_filter` 的规则、watermark encoding、contract snapshot 或 M3.4 prompt 内容，除非 post-review 明确发现真实 contract bug。
   - 继续要求 red-team prompt 数量 >=200，benign prompt 数量 >=100。

2. 4.B 集成路径红队门禁可执行。
   - 新增 focused test 覆盖 200 条 red-team prompt 经 `apply_aigc_filter_to_summary(...)` 后 `blocked=True` 的比例 >=98%。
   - 新增 focused test 覆盖 100 条 benign prompt 经同一 adapter 后 `blocked=True` 的比例 <=2%。
   - 每个 filtered summary 必须包含 shared visible marker，并可被 `aigc_filter.detect_watermark(...)` 识别。
   - 测试必须证明 adapter 输出的 `aigc_watermark.trace_id/provider/module_version` 与 summary 中 zero-width metadata 一致。

3. CI 必须运行该 4.B gate。
   - `chat-service-test` 已覆盖 `apps/chat-service/tests/`；新增测试必须位于该 suite，保证 chat-service path change 时运行。
   - CI path filter 必须在 M3.4 数据集或 AIGC filter 模块变化时触发 chat-service-test，从而同时跑 4.B integration red-team gate。
   - 保留现有 `aigc-filter-validation` 模块级 gate；4.B.7 不取代 M3.4 tests。

4. No-leak 和边界不漂移。
   - blocked red-team output 不得包含原 prompt、prompt 片段、API key、凭证、Traceback、host path、provider payload、queue payload、raw request/response 或 generated code。
   - benign output 不得被替换成 blocked 文案，且仍带 AIGC watermark。
   - 不新增 public `/v1/chat`、`/v1/chat/stream`、SSE、Console UI、4.C preview-confirm、file upload、what-if follow-up、real LLM moderation call、DB/Redis/outbox/billing/Solver/Sandbox side effect。
   - 不改变 `aigc_gate.status=filing_pending` / `public_surface=hidden` 语义；本 story 只增加测试/CI guard。

5. Workflow tracking 和闭环清晰。
   - story 记录三轮 pre-implementation adversarial review，并在每轮后修正 story 才进入 implementation。
   - 实施必须 RED/GREEN：先添加 failing integration test，确认当前 CI/path-filter 或 gate 缺失失败，再补最小实现。
   - 实施后 code review 必须覆盖边界问题、漂移问题、数据一致性、依赖一致性、是否闭环、M3.4 dataset reuse、4.B adapter path、CI trigger、no-leak 和测试证据。
   - code review 修正与完整验证通过后，story 与 sprint status 才能置为 `done`，随后 commit、push、创建 PR、CI 全绿后 merge/sync GitHub。

## Tasks / Subtasks

- [x] Task 1: 建立 4.B red-team integration gate。 (AC: 1, 2)
  - [x] 新增 chat-service focused test，复用 M3.4 `RED_TEAM_PROMPTS` / `BENIGN_PROMPTS`。
  - [x] 通过 `apply_aigc_filter_to_summary(...)` 运行全部 prompt，不直接复制 filter 规则。
  - [x] 断言 red-team block rate >=98%、benign false positive <=2%。
- [x] Task 2: 锁定 watermark 和 no-leak contract。 (AC: 2, 4)
  - [x] 对每个 adapter 输出验证 visible marker、zero-width detector、trace/provider/module_version 一致。
  - [x] 对 blocked 输出验证不回显原 red-team prompt 或 secret-like/raw/internal payload。
  - [x] 对 benign 输出验证未被 blocked replacement 替代。
- [x] Task 3: CI trigger 闭环。 (AC: 3)
  - [x] 更新 CI path filter，使 `tests/aigc/**` 和 `packages/shared-py/aigc_filter/**` 变化触发 `chat-service-test`。
  - [x] 保留 `aigc-filter-validation` 既有模块级 gate。
- [x] Task 4: RED/GREEN、验证、审查与关闭。 (AC: 5)
  - [x] 先写失败测试并确认 RED。
  - [x] 实现最小变更转 GREEN。
  - [x] 跑 focused、chat-service、AIGC/contract 和 full validation。
  - [x] 执行 post-implementation code review 并修复 findings。
  - [x] 更新 Dev Agent Record、File List、Change Log 和 sprint-status。
  - [x] commit、push、创建 PR、等待 CI、merge/sync GitHub。

### Review Findings

- No unresolved findings. Post-implementation review approved the scoped test/CI-only implementation.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:1565` 定义 Story 4.B.7：Critic 红队测试集运行，调用 Story M3.4 200 prompt。
- `_bmad-output/planning/epics.md:1567` 源 AC：Given Story M3.4 红队 prompt 集 / When CI 跑 / Then 拦截率 >=98% + 误拦 <=2%。
- `_bmad-output/planning/epics.md:1134` 到 `1139` 定义 M3.4 canonical filter API、200 red-team、100 benign、>=98% / <=2% gate、watermark detector。
- `_bmad-output/planning/architecture.md:551` Q1 说明 Critic Agent 独立 service 的长期方向，但当前精简档 `chat-with-critic` 是 chat-service 内嵌 inline critic。
- `_bmad-output/planning/architecture.md:552` Q2 指定 `packages/shared-py/aigc-filter` 是 Chat/Critic 用户可见 NL 输出的单点封装。
- `_bmad-output/planning/architecture.md:2970` P68 prompt 变更流程要求红队 + 良性测试集必须通过。
- `_bmad-output/planning/prd.md:625` 到 `630` 定义 Critic Red Team 测试集作为合规应急能力。

### Current Repository Reality

- M3.4 已在 `tests/aigc/datasets.py` 提供 `RED_TEAM_PROMPTS` 200 条与 `BENIGN_PROMPTS` 100 条。
- M3.4 已有模块级测试 `tests/aigc/test_filter.py` 和 `tests/aigc/test_watermark.py`，但它们直接测 shared module，不证明 4.B service adapter path 没被绕过。
- 4.B.5 已新增 `apps/chat-service/src/chat_service/aigc_watermark.py`，其 `apply_aigc_filter_to_summary(summary)` 调用 `aigc_filter.filter(..., tier="strict")` 并返回 `LanguagePreview` 需要的 bounded watermark preview。
- `apps/chat-service/tests/test_aigc_filter_invoke.py` 已覆盖少量 generated/fallback filter 调用、blocked unsafe summary 和 schema drift；尚未用 M3.4 200/100 dataset 跑 4.B integration gate。
- `.github/workflows/ci.yml` 当前 `chat_service` path filter 包含 `apps/chat-service/**`、`apps/sandbox-runner/**`、部分 llm_router/shared-py 文件，但不包含 `tests/aigc/**` 或 `packages/shared-py/aigc_filter/**`；这意味着 M3.4 dataset/filter drift 不会触发 chat-service integration gate。

### Previous Story Intelligence

- M3.4 post-review 曾修复 already-watermarked unsafe input 保留 unsafe text；4.B.7 blocked tests 要确保 adapter output 不回显 red-team prompt。
- M3.4b 锁定 `aigc_filter` signature/result/watermark contract；4.B.7 不应修改 snapshot，除非实际 contract bug。
- 4.B.5 post-review 已避免 test-side duplicate watermark preview assembly；4.B.7 测试应调用 production adapter，而不是重建 preview payload。
- 4.B.6 明确 no public stream surface；4.B.7 也不得借 CI story 引入 runtime endpoint/UI。

### Implementation Guidance

- 建议新增 `apps/chat-service/tests/test_critic_redteam_aigc_gate.py`。
- 测试辅助函数可批量调用：
  - `summary, watermark = apply_aigc_filter_to_summary(prompt)`
  - `detected = aigc_filter.detect_watermark(summary)`
  - 验证 `detected.present`、`detected.trace_id == watermark.trace_id`、`detected.provider == watermark.provider`、`detected.module_version == watermark.module_version`。
- 对 red-team prompt，建议断言：
  - `watermark.blocked is True`
  - `blocked_content in watermark.reason_codes`
  - `prompt not in summary`
  - prompt 中关键危险片段不在 summary，例如 `钓鱼邮件`、`API key`、`爆炸物`、`仇恨攻击`、`绕过平台审查`。
- 对 benign prompt，建议断言：
  - `watermark.blocked is False`
  - `watermark.reason_codes == []`
  - `内容因安全与合规策略已被拦截。` 不在 summary。
- 为避免测试过慢，可一次遍历 300 条 prompt；当前 deterministic filter 是 regex/std-lib，预计很快。
- CI 最小改动是在 `.github/workflows/ci.yml` 的 `chat_service` filter 下加入：
  - `packages/shared-py/aigc_filter/**`
  - `tests/aigc/**`

### Boundary Rules

- No duplicate AIGC filter implementation.
- No copied red-team/benign prompt dataset.
- No changes to `packages/shared-py/aigc_filter` rules, watermark encoding, contract snapshot, or dataset content unless a post-review finding proves a real bug.
- No public Chat route.
- No SSE.
- No Console UI or 4.C preview-confirm flow.
- No file upload / what-if follow-up.
- No AIGC filing status read/update.
- No LLM moderation/provider call.
- No DB/Redis/outbox/notification/billing/cost telemetry writes.
- No Solver invocation.
- No Sandbox gate changes or forced execution.
- No raw provider payload、raw user message、prompt、generated code、secret-like text、traceback、host path、sandbox output 或 queue payload in response/UI text。

## Story Review Rounds

### Round 1 - Data Consistency Review (2026-05-29)

Findings applied:
- 源 AC 容易与 M3.4 模块级 tests 重复；story 已明确 4.B.7 锁的是 service adapter path，不重跑/重写模块实现本身。
- prompt 数据集复制会造成漂移；story 已要求从 `tests/aigc/datasets.py` 导入 canonical 数据集。
- 只测 red-team 会漏掉 CRG5 false positive gate；story 已加入 benign false positive <=2%。
- 只看 blocked flag 不足以证明 watermark contract；story 已要求 detector 与 preview trace/provider/module_version 一致。

Status: PASS after fixes.

### Round 2 - Dependency / Function Consistency Review (2026-05-29)

Findings applied:
- 直接调用 `aigc_filter.filter` 会绕开 4.B.5 adapter；story 已要求通过 `apply_aigc_filter_to_summary(...)`。
- 当前 CI `chat_service` path filter 不会被 M3.4 dataset/filter drift 触发；story 已加入 CI path filter closure。
- `critic-service` 目前不是实际 4.B runtime；story 已基于 architecture C18 将当前 scope 放在 chat-service inline critic/Chat path，并保留未来独立 critic-service 不做。
- 测试不应引入 live LLM moderation；story 已禁止 provider/network/DB 依赖。

Status: PASS after fixes.

### Round 3 - Boundary / Closure Review (2026-05-29)

Findings applied:
- 红队 story 容易漂移成规则增强；story 已禁止改 shared filter 规则，除非 post-review 证明 contract bug。
- 合规红队容易被误读为 AIGC 备案已通过；story 已要求 `aigc_gate` 保持 filing_pending/hidden，且本 story 只增加测试/CI guard。
- blocked output 可能泄漏原 prompt；story 已加入 no-leak assertions。
- Closure 已加入 post-implementation review 范围：dataset reuse、adapter path、CI trigger、no-leak、边界和测试证据。

Status: PASS after fixes. Story is ready for development.

## Test / Validation Notes

Expected commands:

```bash
$env:PYTHONPATH='apps/chat-service/src;apps/sandbox-runner/src;packages/shared-py'; uv run pytest apps/chat-service/tests/test_critic_redteam_aigc_gate.py -q
$env:PYTHONPATH='apps/chat-service/src;apps/sandbox-runner/src;packages/shared-py'; uv run pytest apps/chat-service/tests -q
$env:PYTHONPATH='packages/shared-py'; uv run pytest tests/aigc -q
$env:PYTHONPATH='apps/auth-service/src;packages/shared-py'; uv run pytest tests/contract/test_aigc_filter_module_contract.py -q
uv run mypy apps packages
uv tool run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

RED expectation: focused 4.B.7 test should fail before implementation because `apps/chat-service/tests/test_critic_redteam_aigc_gate.py` does not exist, and CI path filter does not trigger chat-service-test on `tests/aigc/**` / `packages/shared-py/aigc_filter/**` drift.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-29 - Story created from Epic 4.B.7 source AC, M3.4/M3.4b module/data contracts, 4.B.5 adapter path, architecture Q1/Q2/C18/P68, and current CI path filters.
- 2026-05-29 - Story review round 1 applied data consistency fixes: service adapter scope, canonical dataset reuse, red-team plus benign gates, and detector consistency.
- 2026-05-29 - Story review round 2 applied dependency/function fixes: use production adapter, close CI path filter, avoid premature critic-service/runtime dependencies, no live moderation.
- 2026-05-29 - Story review round 3 applied boundary/closure fixes: no filter-rule changes, no AIGC filing/public Chat drift, no-leak assertions, explicit post-review scope.
- 2026-05-29 - Dev story implementation started; sprint status moved from ready-for-dev to in-progress.
- 2026-05-29 - RED confirmed: new focused chat-service dataset gate initially failed because the canonical `tests/aigc` dataset import was unavailable from the service test path; CI static test failed because `chat_service` filter did not include `tests/aigc/**` or `packages/shared-py/aigc_filter/**`.
- 2026-05-29 - GREEN implemented: 4.B adapter red-team/benign gate loads the canonical dataset file, runs all prompts through `apply_aigc_filter_to_summary(...)`, verifies watermark detector consistency and no-leak behavior, and CI path filter now triggers chat-service-test on AIGC dataset/module drift.
- 2026-05-29 - Post-implementation code review completed across dataset reuse, adapter path, CI trigger, no-leak, boundary drift, dependency consistency, and closure evidence. No code fixes required.
- 2026-05-29 - Final validation passed: focused 4.B.7 tests 4 passed; chat-service tests 145 passed; AIGC tests 13 passed; AIGC contract tests 9 passed; `uv run mypy apps packages`; `uv tool run pre-commit run --all-files --show-diff-on-failure`; `git diff --check`.

### Completion Notes

- Added chat-service integration tests that run all 200 M3.4 red-team prompts and all 100 benign prompts through the 4.B.5 production AIGC adapter.
- Locked the 4.B adapter gate at red-team block rate >=98% and benign false positive rate <=2%, with detector consistency checks for visible marker and zero-width metadata.
- Added no-leak assertions for blocked red-team outputs and benign-not-blocked assertions for safe prompts.
- Updated CI path filters so `tests/aigc/**` and `packages/shared-py/aigc_filter/**` changes trigger `chat-service-test`, while preserving the separate `aigc-filter-validation` module gate.
- No shared filter rules, prompt datasets, contract snapshot, runtime endpoints, public Chat/SSE/UI, filing state, DB/Redis/outbox/billing/Solver/Sandbox behavior, or live provider calls were changed.

### Post-Implementation Code Review (AI)

Outcome: Approved.

Findings:
- No patch findings. Implementation is test/CI scoped, reuses canonical M3.4 datasets, runs through the 4.B.5 adapter, and closes the CI trigger gap without changing runtime behavior.

Residual risk:
- This gate covers the current chat-service inline Critic/Chat path. A future standalone `critic-service` runtime will still need its own equivalent integration gate when it becomes active.

### File List

- `_bmad-output/stories/4-b-7-critic-redteam-tests.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `apps/chat-service/tests/test_aigc_redteam_ci_filter.py`
- `apps/chat-service/tests/test_critic_redteam_aigc_gate.py`

### Change Log

- 2026-05-29 - Created 4.B.7 story and completed three adversarial story review rounds.
- 2026-05-29 - Started implementation and moved story/sprint status to in-progress.
- 2026-05-29 - Added 4.B adapter red-team/benign gate, CI trigger coverage, post-implementation review notes, and final validation evidence; story/sprint status moved to done.
