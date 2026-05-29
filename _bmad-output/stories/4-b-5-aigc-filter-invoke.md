# Story 4.B.5: AIGC 水印调用 (调用 Story M3.4 module)

Status: done

owner: Chat Platform / AI Safety / Compliance

## Story

作为 internal beta Chat Platform 负责人和 AI Safety owner，
我希望 Chat internal beta 的用户可见 NL 输出在返回前调用既有 `packages/shared-py/aigc_filter` 出口过滤和水印模块，
以便 `language_preview.summary` 携带 AIGC 可访问标识与 zero-width metadata，并且在不新增公开 Chat、SSE、4.C UI 或重复实现过滤规则的前提下，闭合 Story M3.4 在 4.B 链路中的调用点。

## Acceptance Criteria

1. 只调用既有 M3.4 shared AIGC module，不重写过滤器。
   - 必须复用 `packages/shared-py/aigc_filter/__init__.py` 的公开 API：`aigc_filter.filter(text, tier="strict", context=None)`、`detect_watermark(...)`、`AIGC_ARIA_LABEL`、`AIGC_VISIBLE_MARKER`、`PROVIDER_MARKER`。
   - 不得在 `chat-service`、`critic-service`、`apps/web` 或 service-local utility 中复制敏感词规则、水印编码、zero-width detector 或 provider marker。
   - 不新增 runtime dependency；`chat-service` 已依赖 workspace `opticloud-shared`，测试通过 `packages/shared-py` import path 使用现有模块。
   - 不修改 M3.4/M3.4b 模块 contract、snapshot、filter 规则、watermark encoding 或 red-team/benign 数据集。

2. `language_preview.summary` 必须成为 AIGC-filtered 用户可见 NL 出口。
   - `LanguagePreview.summary` 必须是 `aigc_filter.filter(...).text` 的结果，而不是未过滤 summary。
   - 允许 generated 和 fallback language preview 都经过同一个出口过滤步骤；不能只过滤 fallback 或只过滤 LLM completion。
   - filter tier 必须固定为 `strict`，除非未来 story 明确引入 plan/tier policy；本 story 不引入动态策略。
   - blocked output 必须使用 shared module 的安全替换文本，不得返回原始 unsafe summary。
   - 过滤发生在 `parse_language_response_completion(...)` / `heuristic_language_preview(...)` 生成 bounded safe summary 之后；不得将 raw user message、prompt、provider payload、完整 code、sandbox output 或 validation error raw text 传入 filter。

3. Response schema 暴露 bounded watermark preview。
   - `LanguagePreview` 必须新增单一字段 `aigc_watermark`（或等价但只能一个字段），用于 UI/调用方读取 filter/watermark 结果。
   - preview 至少包含：`aria_label`、`visible_marker`、`trace_id`、`provider`、`module_version`、`tier`、`blocked`、`reason_codes`、`metadata`。
   - `aria_label` 必须等于 shared module 的 `AIGC_ARIA_LABEL`，`visible_marker` 必须等于 shared module 的 `AIGC_VISIBLE_MARKER`，`provider` 必须等于 `opticloud-aigc-filter`。
   - `trace_id` 必须匹配 `^trc_[0-9a-f]{16}$`，且必须能通过 `aigc_filter.detect_watermark(language_preview.summary)` 识别并一致。
   - `reason_codes` 必须 bounded，不能包含 raw summary、raw user message、prompt、provider payload、secret-like text、traceback、host path 或 queue payload。
   - `metadata` 只允许 auditable bounded keys，例如 `self_loop_bypass`；不得泄漏 token、headers、request body、provider raw data、internal prompt 或 filing status。

4. Chat internal beta 边界和既有 contract 不漂移。
   - 当前唯一 Chat 业务端点仍是 `POST /v1/chat/internal-beta/messages`；不得新增公开 `/v1/chat`、`/v1/chat/stream`、SSE、Console queue page、public Chat UI、file upload、what-if follow-up 或 4.C preview-confirm flow。
   - internal beta 授权失败或禁用时必须继续在 body validation 前返回 sparse 404，不泄漏 `language_preview`、`aigc_watermark`、AIGC filter schema、Critic/Sandbox/HumanReview schema 或 UI contract。
   - 成功响应必须继续保持 `public_access=false`、`provider_request_sent=false`、`solver_invoked=false`、`aigc_gate.public_surface=hidden`。
   - 顶层 `llm_invoked`、`critic_invoked`、`critic_llm_invoked`、`sandbox_invoked` 不得因 filter/watermark 语义被篡改。
   - 不新增 DB/Redis/outbox/notification/billing/cost telemetry、真实 human review queue write、LLM moderation/provider call、Solver invocation 或 Sandbox gate change。

5. AIGC gate 语义保持 internal beta，不冒充备案放行。
   - `aigc_gate.status` 仍为 `filing_pending`，`public_surface` 仍为 `hidden`；调用 filter/watermark 不代表 public Chat 可开放。
   - 本 story 不读取或更新 AIGC 备案状态，不新增备案号字段，不实现 M0.AIGC-status tracking 或 8.B public compliance surface。
   - `aigc_watermark` 可作为 internal beta evidence，但不得替代 `language_preview.disclaimer` 或改变已有 disclaimer 文案。

6. Tests 必须先红后绿，覆盖 filter 调用、schema、watermark detector 和漂移场景。
   - 新增 focused tests（建议 `apps/chat-service/tests/test_aigc_filter_invoke.py`），先断言当前 response 缺少 `language_preview.aigc_watermark` 和 summary 未 watermark 为 RED。
   - 覆盖 generated 和 fallback `LanguagePreview` 都包含 visible marker、aria label、trace id、provider、module version、tier=`strict`、blocked flag 和 bounded reason codes。
   - 覆盖 `aigc_filter.detect_watermark(language_preview.summary)` 能识别 zero-width metadata，且 trace id 与 preview 一致。
   - 覆盖 unsafe generated summary 被 blocked replacement 替代，不返回 unsafe 原文。
   - 扩展 `test_internal_beta.py`，覆盖 successful response 包含 `language_preview.aigc_watermark`，unauthorized invalid body 仍先 404 且不泄漏 `aigc_watermark`。
   - 扩展 schema negative tests，覆盖 `LanguagePreview` 拒绝 summary 和 `aigc_watermark.trace_id` 不一致、provider drift、missing marker/metadata drift。
   - 测试不得需要 live LLM provider、外部网络、真实 Redis/DB/outbox/notification/Sandbox runtime、AIGC 备案、Grafana、K8s、Chromatic token 或 GitHub token。

7. Workflow tracking 和闭环清晰。
   - 本 story 记录三轮 pre-implementation story review，并在每轮后应用修正后才能进入 `ready-for-dev`。
   - dev-story 开始时将 sprint status 置为 `in-progress`；实现完成且测试通过后置为 `code-review`。
   - post-implementation code review 必须覆盖边界问题、漂移问题、数据一致性、依赖一致性、是否闭环、AIGC module contract、watermark detector、schema no-leak、human-review/Sandbox/Chat gate 语义一致性和测试证据。
   - code review 修正与完整验证通过后，story 与 sprint status 才能置为 `done`，随后 commit、push、创建 PR、CI 全绿后 merge/sync GitHub。

## Tasks / Subtasks

- [x] Task 1: 建立 Chat language AIGC watermark 数据契约。 (AC: 3, 4, 5)
  - [x] 在 `apps/chat-service/src/chat_service/schemas.py` 增加 `AigcWatermarkPreview` 与 validation error/schema guards。
  - [x] 将 `aigc_watermark` 加入 `LanguagePreview`。
  - [x] 锁定 `aria_label`、visible marker、trace id、provider、module version、tier、blocked、reason codes、metadata、extra forbid 和 no-leak validation。
- [x] Task 2: 实现 language preview 出口过滤 adapter。 (AC: 1, 2, 3, 5)
  - [x] 新增或局部实现 `chat_service` adapter，只调用 `aigc_filter.filter`，不复制 filter 规则。
  - [x] 对 generated 和 fallback summary 统一使用 strict tier。
  - [x] 确保 blocked summary 返回 shared module replacement text + watermark，不返回 unsafe 原文。
  - [x] 确保 `detect_watermark(summary)` 与 schema preview trace_id 一致。
- [x] Task 3: Wire language response path。 (AC: 2, 4, 5)
  - [x] 在 `parse_language_response_completion(...)` 和 `heuristic_language_preview(...)` 生成 `LanguagePreview` 前后接入统一 filtering path。
  - [x] 保持 `language_preview.disclaimer` 不变。
  - [x] 保持 internal beta gate、provider_request_sent、llm_invoked、Sandbox/HumanReview/ConfidenceDisplay 语义不变。
- [x] Task 4: RED/GREEN tests。 (AC: 1-6)
  - [x] 先写失败测试并确认 `aigc_watermark` 或 watermark summary 缺失为 RED。
  - [x] 实现最小代码让测试转绿。
  - [x] 加 negative tests 覆盖 watermark trace/provider drift、blocked unsafe summary、unauthorized no-leak、no public route/no SSE/no filter rule duplication。
- [x] Task 5: 验证、审查与关闭。 (AC: 7)
  - [x] 跑 focused 与 full validation。
  - [x] 执行 post-implementation code review 并修复 findings。
  - [x] 更新 Dev Agent Record、File List、Change Log 和 sprint-status。
  - [x] commit、push、创建 PR、等待 CI、merge/sync GitHub。

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:1557` 定义 Story 4.B.5：AIGC 水印调用，调用 Story M3.4 module。
- `_bmad-output/planning/epics.md:1559` 的源 AC：Given Story M3.4 packages/shared-py/aigc-filter / When Critic 输出 user-visible NL / Then 调 filter + 加 aria-label 水印 + zero-width metadata。
- `_bmad-output/planning/epics.md:416` 明确 Epic 4.B 只调用 M3.4 module，G12 AIGC 水印物理位置在 Epic 0 M3.4。
- `_bmad-output/planning/architecture.md:552` 明确 Q2：`packages/shared-py/aigc-filter` 是 chat-service 和 critic-service 对所有用户可见 NL 输出的单点封装。
- `_bmad-output/planning/architecture.md:413` 定义 M3.4：AIGC 水印 module + zero-width Unicode + trace_id。
- `_bmad-output/planning/ux-design-specification.md:3406` 要求 AIGC watermark aria-label + zero-width metadata。
- `_bmad-output/stories/m3-4-aigc-watermark-module.md` 已实现 shared module、visible marker、aria label、zero-width metadata、detector、self-loop metadata。
- `_bmad-output/stories/m3-4b-aigc-filter-contract-test.md` 已锁定 shared module contract、signature、result fields、watermark fields 和 deprecation policy。

### Current Repository Reality

- `packages/shared-py/aigc_filter/__init__.py` 已提供 `filter(...)`、`detect_watermark(...)`、`AIGC_ARIA_LABEL`、`AIGC_VISIBLE_MARKER`、`PROVIDER_MARKER`、`FilterResult`、`WatermarkMetadata`。
- `aigc_filter.filter` 已是离线 deterministic；不会调用 LLM、网络、DB 或备案服务。
- `apps/chat-service/pyproject.toml` 已依赖 workspace `opticloud-shared`，pytest pythonpath 已包含 `../../packages/shared-py`。
- `apps/chat-service/src/chat_service/language_response.py` 是当前 user-visible NL summary 的唯一生成点：`parse_language_response_completion(...)` 和 `heuristic_language_preview(...)` 都构造 `LanguagePreview`。
- `LanguagePreview` 当前包含 `status`、`source`、`response_locale`、`summary`、`disclaimer`、`validation_errors`、`supported_locales`，尚无 AIGC watermark preview。
- `apps/chat-service/src/chat_service/main.py` 当前链路是 Router -> Formulator -> Coder -> Critic -> HumanReview -> ConfidenceDisplay -> Sandbox -> Language；4.B.5 应只改变 Language output，不改变前序 gates。
- `apps/chat-service/tests/test_internal_beta.py` 对完整 response 做精确断言，新增 `aigc_watermark` 需同步。
- `apps/chat-service/tests/test_sandbox.py` 手工构造 `LanguagePreview`，新增 required field 需同步。

### Previous Story Intelligence

- 4.A.5 只做 internal beta `language_preview`，显式不调用 AIGC filter；4.B.5 是该调用点。
- 4.B.1-4.B.4 均保持 `provider_request_sent=false`、无 public Chat、无 SSE、无 DB/Redis/Billing/Solver side effect；4.B.5 必须延续。
- 4.B.4 在 post-review 中加入跨字段 drift validation；4.B.5 也应对 `summary` watermark detector 与 schema preview trace_id 做一致性校验。
- 4.B.3/4.B.4 明确旧顶层 `escalated`、`human_review_queue` 不应出现；4.B.5 不应引入新的顶层 queue/filter payload。
- M3.4 post-review 修复过“already-watermarked unsafe input 不能保留 unsafe text”；4.B.5 blocked tests 应覆盖 unsafe summary 不回传。

### Implementation Guidance

- 建议在 `schemas.py` 中增加 `AigcWatermarkPreview`，字段可用：
  - `aria_label: Literal["本回答由 AI 生成，仅供参考"]`
  - `visible_marker: Literal["本回答由 AI 生成，仅供参考"]`
  - `trace_id: str` pattern `^trc_[0-9a-f]{16}$`
  - `provider: Literal["opticloud-aigc-filter"]`
  - `module_version: str`
  - `tier: Literal["strict", "loose"]`
  - `blocked: bool`
  - `reason_codes: list[str]`
  - `metadata: dict[str, object]`
- 建议新增 `chat_service/aigc_watermark.py`，提供 `apply_aigc_filter_to_summary(summary: str) -> tuple[str, AigcWatermarkPreview]` 或 dataclass route result，内部只 import/call `aigc_filter`。
- `LanguagePreview` model validator 可调用 `aigc_filter.detect_watermark(self.summary)` 验证 summary 中的 zero-width metadata 与 `aigc_watermark.trace_id/provider/module_version` 一致。
- 对 `summary` 长度限制要重新评估：加上 visible marker + zero-width metadata 后可能超过原 `max_length=360`。建议把 schema max_length 提高到能容纳原 360 字 summary + marker + zero-width payload，例如 1200，并在 filter 前仍保持原始 summary bounded。
- 不要把 filter metadata 放到顶层 `aigc_gate`；`aigc_gate` 仍表示 public surface hidden / filing pending。
- 不要新增 frontend UI；本 story 的用户可见输出仍是 internal beta JSON contract。

### Boundary Rules

- No duplicate AIGC filter implementation.
- No modifications to `packages/shared-py/aigc_filter` unless a test uncovers a genuine contract bug and the story/review explicitly justifies it.
- No public Chat route.
- No SSE.
- No Console queue page or public Chat UI.
- No 4.C preview-confirm model flow.
- No file upload / what-if follow-up.
- No AIGC filing status read/update.
- No LLM moderation/provider call.
- No DB/Redis/outbox/notification/billing/cost telemetry writes.
- No Solver invocation.
- No Sandbox gate changes or forced execution.
- No human-review queue/event write beyond 4.B.3 preview contract.
- No raw provider payload、raw user message、prompt、full generated code、secret-like text、traceback、host path、sandbox output 或 queue payload in response/UI text。

### Story Review Rounds

### Round 1 - Data Consistency Review (2026-05-29)

Findings applied:
- 源 AC 写“Critic 输出 user-visible NL”，但当前代码的用户可见 NL 出口是 `language_preview.summary`；story 已明确 4.B.5 作用于 Chat internal beta 的 `LanguagePreview.summary`，不把 Critic reasoning/confidence display 当作 NL response filter target。
- AIGC watermark 可能被误写进 `aigc_gate` 或顶层字段；story 已要求 `LanguagePreview.aigc_watermark` 作为单一 bounded preview，`aigc_gate` 保持 filing_pending/hidden。
- 过滤后 visible marker + zero-width metadata 会增加 summary 长度；story 已要求提高 `summary` schema bound，但 filter 前保持原始 summary bounded。
- `aigc_watermark` 可能泄漏 raw summary 或 request；story 已要求只暴露 bounded marker、trace、provider、module version、tier、blocked、reason codes 和 safe metadata。

Status: PASS after fixes.

### Round 2 - Function / Dependency Consistency Review (2026-05-29)

Findings applied:
- M3.4/M3.4b 已锁定 shared module contract；story 已禁止修改/复制 filter 规则、watermark encoding、detector 或 contract snapshot。
- `chat-service` 已有 `opticloud-shared` workspace dependency；story 已禁止新增 runtime dependency，并要求通过 existing import path 使用 `aigc_filter`。
- 仅在 fallback path 过滤会遗漏 generated LLM completion；story 已要求 generated 与 fallback 都统一走同一个 strict filter adapter。
- `LanguagePreview` 手工构造测试会因 required field 破裂；story 已点名同步 `test_sandbox.py` 和 schema negative tests。

Status: PASS after fixes.

### Round 3 - Drift / Boundary / Closure Review (2026-05-29)

Findings applied:
- 调用 AIGC filter 容易被误解为备案完成或 public Chat 可开放；story 已要求 `aigc_gate` 语义不变，不读取备案状态，不新增备案号或 public surface。
- Story 容易漂移到 8.B public compliance/i18n 单源或 4.C SSE/UI；Boundary Rules 已明确排除。
- Self-loop metadata 可能被误用为 bypass；story 已要求不传入 internal self-loop context，metadata 只允许 bounded audited keys。
- Closure 已加入 post-implementation review 要求：module contract、detector consistency、schema no-leak、Chat/HumanReview/Sandbox gate 语义和完整测试证据。

Status: PASS after fixes. Story is ready for development.

## Test / Validation Notes

Expected commands:

```bash
$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests/test_aigc_filter_invoke.py -q
$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests/test_language_response.py apps/chat-service/tests/test_internal_beta.py apps/chat-service/tests/test_sandbox.py -q
$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests -q
uv run pytest tests/aigc -q
uv run pytest tests/contract/test_aigc_filter_module_contract.py -q
uv run mypy apps packages
uv tool run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

RED expectation: add tests first; they should fail because current `LanguagePreview` lacks `aigc_watermark` and `language_preview.summary` does not contain M3.4 visible marker or zero-width metadata.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-29 - Story draft created from Epic 4.B.5 source AC, M3.4/M3.4b module contract, architecture Q2/P34/P62, UX AIGC watermark requirement, and 4.A.5/4.B.1-4.B.4 boundary learnings.
- 2026-05-29 - Story review round 1 applied data consistency fixes: scoped target to `LanguagePreview.summary`, kept `aigc_gate` semantics unchanged, accounted for watermark length, and bounded `aigc_watermark` fields.
- 2026-05-29 - Story review round 2 applied function/dependency fixes: reuse existing `aigc_filter`, no dependency changes, filter generated and fallback outputs, and synchronize hand-built `LanguagePreview` tests.
- 2026-05-29 - Story review round 3 applied drift/boundary/closure fixes: blocked public Chat/8.B/4.C/备案 drift, banned self-loop bypass misuse, and made post-implementation review gates explicit.
- 2026-05-29 - Dev story implementation started; sprint status moved from ready-for-dev to in-progress.
- 2026-05-29 - RED confirmed: `apps/chat-service/tests/test_aigc_filter_invoke.py` failed during collection because `AigcWatermarkPreview` and `LanguagePreview.aigc_watermark` did not exist.
- 2026-05-29 - GREEN implementation added `AigcWatermarkPreview`, `LanguagePreview.aigc_watermark`, strict `aigc_filter.filter` adapter, generated/fallback language response wiring, detector consistency validation, and no-leak schema guards.
- 2026-05-29 - Post-implementation code review completed across boundary drift, schema no-leak, shared module contract, detector consistency, Chat/HumanReview/Sandbox gate semantics, and validation evidence.

### Completion Notes

- Implemented Chat language AIGC watermark contract by adding bounded `LanguagePreview.aigc_watermark` metadata and requiring `summary` to contain the shared visible marker plus detectable zero-width metadata.
- Added `chat_service.aigc_watermark.apply_aigc_filter_to_summary(...)`, which only calls `aigc_filter.filter(..., tier="strict")` and maps the shared module result into the response schema.
- Wired both generated LLM language summaries and heuristic fallback summaries through the same filter path after existing summary safety/bounding.
- Preserved internal beta boundaries: no public `/v1/chat`, no `/v1/chat/stream`, no SSE/UI changes, no DB/Redis/outbox/billing/Solver/Sandbox gate side effects, and `aigc_gate` remains `filing_pending` / `hidden`.
- Post-review fixes added missing marker/metadata negative tests, bounded reason/metadata leak guards, public route/SSE no-leak tests, and removed duplicated test-side watermark preview assembly.
- Validation passed:
  - `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests/test_aigc_filter_invoke.py -q` -> 8 passed.
  - `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests/test_language_response.py apps/chat-service/tests/test_internal_beta.py apps/chat-service/tests/test_sandbox.py -q` -> 54 passed.
  - `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests -q` -> 138 passed.
  - `uv run pytest tests/aigc -q` -> 13 passed.
  - `$env:PYTHONPATH='packages/shared-py'; uv run pytest tests/contract/test_aigc_filter_module_contract.py -q` -> 9 passed.
  - `uv run mypy apps packages` -> success.
  - `uv tool run pre-commit run --all-files --show-diff-on-failure` -> passed after ruff format applied.
  - `git diff --check` -> passed.

### Post-Implementation Code Review (AI)

Outcome: Approved after fixes.

Findings fixed:
- [x] [Review][Patch] Missing explicit negative coverage for visible-marker and zero-width metadata drift. Added `LanguagePreview` tests for missing visible marker and missing zero-width metadata.
- [x] [Review][Patch] Bounded no-leak guards did not explicitly name raw summary, raw user message, generated code, and sandbox output. Expanded schema guard pattern and added leaky reason/metadata tests.
- [x] [Review][Patch] Test-side watermark preview assembly duplicated production mapping. Replaced duplicated helper with `apply_aigc_filter_to_summary(...)` in sandbox contract test.

Residual risk: zero-width metadata length is bounded by `summary` schema max length and shared module contract; future M3.4 watermark encoding changes should remain covered by `detect_watermark` and contract tests.

### File List

- `_bmad-output/stories/4-b-5-aigc-filter-invoke.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/chat-service/src/chat_service/aigc_watermark.py`
- `apps/chat-service/src/chat_service/language_response.py`
- `apps/chat-service/src/chat_service/schemas.py`
- `apps/chat-service/tests/test_aigc_filter_invoke.py`
- `apps/chat-service/tests/test_internal_beta.py`
- `apps/chat-service/tests/test_sandbox.py`

### Change Log

- 2026-05-29 - Created 4.B.5 story, completed three adversarial story review rounds, and marked ready-for-dev.
- 2026-05-29 - Started implementation and moved story/sprint status to in-progress.
- 2026-05-29 - Implemented AIGC strict filter invocation for generated and fallback language summaries, added bounded watermark preview schema, and updated internal beta/sandbox tests.
- 2026-05-29 - Completed post-implementation code review fixes and full validation; story/sprint status moved to done.
