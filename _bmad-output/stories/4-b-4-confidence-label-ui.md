# Story 4.B.4: Confidence Score + 中英 reasoning 显示 (N12 + CRG14 visual brackets)

Status: done

owner: Chat Platform / Frontend Platform / AI Safety

## Story

作为 internal beta Chat 用户与 Chat Platform 负责人，
我希望 Critic 置信度能通过既有 `packages/ui` 的 `ConfidenceLabel` 以稳定红黄绿视觉分级、可访问 `aria-label` 和中英双语 reasoning preview 呈现，
以便用户在不进入公开 Chat、SSE、4.C 用户确认模型流程或真实 Console review queue 的前提下，能清楚看到 Critic confidence score、视觉等级和中英解释，并且低置信状态与 4.B.3 human-review escalation contract 保持一致。

## Acceptance Criteria

1. `ConfidenceLabel` 组件强化但不重建。
   - 必须复用并修改现有 `packages/ui/src/components/ConfidenceLabel/index.tsx`；不得创建第二个 confidence component、不得迁移到 `apps/web` 本地组件、不得改变 `packages/ui` 单源导出路径。
   - 组件必须继续通过 `packages/ui/src/index.ts` 导出 `ConfidenceLabel` 和 `ConfidenceLabelProps`。
   - 组件 props 必须支持 Critic confidence score `[0.0, 1.0]`、中英 labels、中英 reasoning，以及 compact/inline 场景。
   - 无效 score（`NaN`、`Infinity`、小于 0、大于 1）必须 fail closed 到 bounded UI 状态；不得渲染 `NaN`、`Infinity` 或导致 React 抛错。
   - 不新增 runtime dependency；继续使用 React、现有 `useA11y`、`cn`、Tailwind token 和 `jest-axe` 测试栈。

2. CRG14 visual brackets 必须精确且可测试。
   - `score >= 0.85` 显示 high tier：绿色 token、中文 label `高置信`、英文 label `High confidence`。
   - `0.6 <= score < 0.85` 显示 mid tier：黄色 token、中文 label `中置信`、英文 label `Medium confidence`。
   - `score < 0.6` 显示 low tier：红色 token、中文 label `低置信请人工 review`、英文 label `Low confidence; human review recommended`。
   - 边界值必须明确：`0.85` 是 high，`0.8499` 是 mid，`0.6` 是 mid，`0.5999` 是 low。
   - 组件必须暴露 stable `data-tier="high|mid|low"` 和 score text 两位小数，供测试和下游 UI 稳定使用。
   - 不改变 M3.5a/4.B.3 阈值语义：human-review escalation 仍只由 `critic_preview.confidence < critic_preview.calibration_threshold` 决定；visual tier 不重新计算或触发 queue。

3. 可访问性与双语 reasoning 必须稳定。
   - 可访问名称必须包含精确 score，格式至少满足 `aria-label="Confidence: 0.85"`；允许在后面追加英文 label，但不得缺少该前缀。
   - 中英双语 reasoning 必须在 DOM 中可见或通过 `aria-describedby` 关联，且不能仅存在于 tooltip、title 或 Storybook args。
   - `aria-describedby` 指向的元素 id 必须真实存在，避免当前 `useA11y` 只生成 describedby 但组件未提供 matching id 的漂移。
   - compact 模式也必须保留可访问 reasoning，不得因为隐藏视觉说明而丢失 `aria-describedby` 内容。
   - 视觉文本必须不溢出固定标签：长 reasoning 不得塞进小 badge；badge 只显示 score + label，reasoning 放在相邻描述区域或 screen-reader-safe 区域。

4. Chat internal beta response 提供 UI 可直接消费的 confidence display preview。
   - `ChatInternalBetaMessageResponse` 必须新增 `critic_confidence_display`（或等价命名，但只能有一个字段）作为 bounded preview object，供 `ConfidenceLabel` 显示。
   - 该 preview 必须从 `critic_preview.confidence`、`critic_preview.reasoning`、`critic_preview.calibration_threshold`、`human_review.escalated` 派生；不得重新读取校准配置，不得调用 LLM/provider，不得调用 AIGC filter。
   - preview 至少包含：`score`、`tier`、`label_zh`、`label_en`、`reasoning_zh`、`reasoning_en`、`aria_label`、`calibration_threshold`、`human_review_escalated`、`validation_errors`。
   - `score` 和 `calibration_threshold` 必须在 `[0.0, 1.0]`；`tier` 必须与 CRG14 visual brackets 一致。
   - `reasoning_zh`/`reasoning_en` 必须 bounded，不包含 raw user message、provider payload、prompt、raw response、完整 generated code、sandbox output、secret-like text、traceback、host path 或 queue payload。
   - low tier 且 `human_review.escalated=true` 时，`reasoning_zh` 可以提及 `已转人工复核`；但不得替代或改变 4.B.3 的 `human_review.user_notice` contract。

5. 既有 Chat / Sandbox / Human Review 边界不变。
   - 当前唯一 Chat 业务端点仍是 `POST /v1/chat/internal-beta/messages`；不得新增公开 `/v1/chat`、`/v1/chat/stream`、SSE、Console queue page、public Chat UI、file upload、what-if follow-up 或 4.C preview-confirm flow。
   - internal beta 授权失败或禁用时必须继续在 body validation 前返回 sparse 404，不泄漏 `critic_confidence_display`、Critic/Sandbox/HumanReview schema 或 UI contract。
   - 成功响应必须继续保持 `public_access=false`、`provider_request_sent=false`、`solver_invoked=false`、`aigc_gate.public_surface=hidden`。
   - 顶层 `llm_invoked`、`critic_invoked`、`critic_llm_invoked`、`sandbox_invoked` 不得因 display preview 语义被篡改。
   - 不新增 DB/Redis/outbox/notification/billing/cost telemetry、真实 human review queue write、AIGC runtime invocation 或 Sandbox gate change。

6. Tests 必须先红后绿，覆盖 UI、contract 和漂移场景。
   - 新增 `packages/ui/src/components/ConfidenceLabel/index.test.tsx`，覆盖 5 visual states × 3 i18n/locale display cases、边界值、invalid score fallback、compact 可访问 reasoning、DOM 不渲染 `NaN/Infinity`。
   - 新增或扩展 a11y tests，确保 `ConfidenceLabel` high/mid/low/compact/long-reasoning 状态 axe-core 0 violations。
   - 扩展 `apps/chat-service/tests/test_internal_beta.py` 或新增 focused tests，覆盖 response 包含 `critic_confidence_display`、tier 与 score/threshold 对齐、low confidence 与 `human_review.escalated` 一致、unauthorized invalid body 仍先 404。
   - negative tests 必须覆盖 queue/event/human-review 语义不被 UI preview 改写，旧顶层 `escalated` 或 `human_review_queue` 仍不出现。
   - 测试不得需要 live LLM provider、外部网络、真实 Redis/DB/outbox/notification/Sandbox runtime、AIGC 备案、Grafana、K8s、Chromatic token 或 GitHub token。

7. Workflow tracking 和闭环清晰。
   - 本 story 记录三轮 pre-implementation story review，并在每轮后应用修正后才能进入 `ready-for-dev`。
   - dev-story 开始时将 sprint status 置为 `in-progress`；实现完成且测试通过后置为 `code-review`。
   - post-implementation code review 必须覆盖边界问题、漂移问题、数据一致性、依赖一致性、是否闭环、visual tier 边界、aria linkage、i18n 文案、human-review 语义一致性、no-leak 和测试证据。
   - code review 修正与完整验证通过后，story 与 sprint status 才能置为 `done`，随后 commit、push、创建 PR、CI 全绿后 merge/sync GitHub。

## Tasks / Subtasks

- [x] Task 1: 建立 Chat confidence display 数据契约。 (AC: 4, 5)
  - [x] 在 `apps/chat-service/src/chat_service/schemas.py` 增加 `CriticConfidenceDisplayPreview` 与 validation error schema。
  - [x] 将 `critic_confidence_display` 加入 `ChatInternalBetaMessageResponse`。
  - [x] 锁定 `score`、`tier`、labels、reasoning、`aria_label`、threshold、human-review 标记、extra forbid 和 bounded validation errors。
- [x] Task 2: 实现 confidence display adapter。 (AC: 2, 4, 5)
  - [x] 新增 `apps/chat-service/src/chat_service/confidence_display.py`。
  - [x] 从 `critic_preview` 与 `human_review` 生成 display preview，不调用 LLM/provider，不读取配置。
  - [x] 实现 high/mid/low visual bracket 与边界值：`>=0.85` high、`>=0.6` mid、其余 low。
  - [x] 清洗/限制 reasoning，避免 raw/provider/prompt/code/sandbox/secret 泄漏。
- [x] Task 3: 强化 `ConfidenceLabel` UI 组件。 (AC: 1, 2, 3)
  - [x] 修改 `packages/ui/src/components/ConfidenceLabel/index.tsx`，支持中英 labels/reasoning 和 invalid score fail closed。
  - [x] 保持 `data-tier`、score 两位小数、compact 模式和 `packages/ui` 导出不破坏。
  - [x] 修复或确认 `aria-describedby` 指向真实描述节点。
- [x] Task 4: Wire Chat internal beta response。 (AC: 4, 5)
  - [x] 在 `apps/chat-service/src/chat_service/main.py` Critic/HumanReview 后接入 confidence display preview。
  - [x] 保持 gate-before-body-validation、AIGC hidden、provider_request_sent=false、solver=false、Sandbox gate 不变。
  - [x] 确认 display preview 不注入 `language_preview.summary`，也不改 `human_review.user_notice`。
- [x] Task 5: RED/GREEN tests。 (AC: 1, 2, 3, 4, 5, 6)
  - [x] 先写失败测试并确认 `critic_confidence_display` 或新 UI behavior 缺失为 RED。
  - [x] 实现最小代码让测试转绿。
  - [x] 加 negative tests 覆盖 visual bracket 边界、aria linkage、i18n 文案、invalid score、raw leak、no queue semantics drift。
- [x] Task 6: 验证、审查与关闭。 (AC: 7)
  - [x] 跑 focused 与 full validation。
  - [x] 执行 post-implementation code review 并修复 findings。
  - [x] 更新 Dev Agent Record、File List、Change Log 和 sprint-status。
  - [x] commit、push、创建 PR、等待 CI、merge/sync GitHub。

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:411` 定义 Epic 4.B goal：用户可查看 confidence + 中英 reasoning。
- `_bmad-output/planning/epics.md:1552` 定义 Story 4.B.4：Confidence Score + 中英 reasoning 显示 (N12 + CRG14 visual brackets)。
- `_bmad-output/planning/epics.md:1554` 的源 AC：Given Story 4.B.3 + packages/ui ConfidenceLabel / When 用户查看 / Then aria-label "Confidence: 0.85" + 中英双语 reasoning + 视觉化 EP4。
- `_bmad-output/planning/epics.md:1555` 明确 CRG14 visual brackets：`>=0.85` 绿、`0.6-0.85` 黄、`<0.6` 红 + 中文 label + 5 visual states × 3 i18n × axe-core 0 violations。
- `_bmad-output/planning/prd.md:1497` 将 FR N12 定义为用户 can view Critic Agent confidence score + 中英文 reasoning。
- `_bmad-output/planning/architecture.md:1623` 将 N1-N12 归属 chat-service + critic-service + sandbox-runner，全 AIGC-gated M3+。
- `_bmad-output/stories/4-b-1-critic-validate-code.md` 已暴露 `critic_preview.confidence` 与 bounded `critic_preview.reasoning`。
- `_bmad-output/stories/4-b-3-critic-confidence-escalate.md` 已实现 `human_review.escalated` 和 user notice；4.B.4 只能读取该状态，不重写 escalation。

### Current Repository Reality

- `packages/ui/src/components/ConfidenceLabel/index.tsx` 已存在初步 component，包含 score、中文/英文 label override、单一 `reasoning`、compact、`data-tier` 和 Tailwind confidence token。
- 当前 `ConfidenceLabel` 没有 dedicated unit test；只有 `packages/ui/src/components/Tier1.a11y.test.tsx` 对 3 个 score 做通用 axe test。
- 当前 `ConfidenceLabel` 通过 `useA11y({ ariaDescription: reasoning })` 设置 `aria-describedby`，但视觉 reasoning 的 id 只在非 compact 且 reasoning 存在时渲染；compact 模式存在 aria linkage 漂移风险。
- `packages/ui/src/tokens.css` 和 `packages/ui/tailwind.config.ts` 已有 `confidence.high/mid/low` token；不得新增一套颜色系统。
- `packages/ui/package.json` 已有 `test`、`test:a11y`、`typecheck`；测试环境是 Vitest + happy-dom + Testing Library + jest-axe。
- `apps/chat-service/src/chat_service/schemas.py` 当前有 `CriticPreview`、`HumanReviewPreview`、`LanguagePreview` 等 schema，但没有 UI-facing confidence display preview。
- `apps/chat-service/src/chat_service/main.py` 当前链路是 Router -> Formulator -> Coder -> Critic -> HumanReview -> Sandbox -> Language；4.B.4 display preview 应在 Critic/HumanReview 后生成。

### Previous Story Intelligence

- 4.B.1 禁止 UI/visual bracket；现在 4.B.4 是该 UI contract 的落点，但不能改变 Critic confidence 计算。
- 4.B.2 Sandbox gate 依赖 Critic validated；display preview 不得影响 Sandbox gate 或 `sandbox_invoked`。
- 4.B.3 low confidence escalation 使用 `critic_preview.confidence < critic_preview.calibration_threshold`；display low tier 的颜色不能作为 queue 触发源。
- 4.B.3 禁止旧顶层 `escalated` / `human_review_queue`；4.B.4 仍必须保持这些旧字段不出现。
- `packages/ui` 是 Tier 1 component 单源；历史 UI stories 倾向于 component-local tests + a11y tests + storybook stories，不把 component 复制进 `apps/web`。

### Implementation Guidance

- 建议新增 `chat_service/confidence_display.py`，采用 dataclass route result，与 `critic.py`、`human_review.py`、`sandbox.py` 风格一致。
- `critic_confidence_display.reasoning_zh` 不要机器翻译原始英文长文本；可使用 bounded deterministic mapping：
  - validated/high：`Critic 已验证 schema、安全性和业务一致性。`
  - mid：`Critic 置信度中等，建议提交前复核关键约束。`
  - low + human_review.escalated：`Critic 置信度低，已转人工复核。`
  - low without escalation：`Critic 置信度低，请人工复核。`
- `reasoning_en` 可复用 sanitized `critic_preview.reasoning` 或 deterministic bounded English fallback；不要包含 generated code 或 raw payload。
- `aria_label` 建议统一为 `Confidence: {score.toFixed(2)} - {label_en}`，确保包含源 AC 的 `Confidence: 0.85` 前缀。
- `ConfidenceLabel` props 可向后兼容：保留 `reasoning?: string`，新增 `reasoningZh?: string`、`reasoningEn?: string`、`locale?: "zh-CN" | "en-US" | "mixed"` 或等价 API；避免破坏 Storybook 和 Tier1 a11y 测试。
- invalid score fail closed 可 clamp 到 `[0,1]` 并设置 low tier 或显示 `0.00`；测试必须锁定不渲染 `NaN/Infinity`。
- 不需要新页面也不需要 dev server；4.B.4 的 UI 验证以 component tests/a11y tests 为主。

### Boundary Rules

- No public Chat route。
- No SSE。
- No Console queue page or public Chat UI。
- No 4.C preview-confirm model flow。
- No file upload / what-if follow-up。
- No Critic confidence recalibration or dynamic threshold update。
- No human-review queue/event write beyond 4.B.3 preview contract。
- No Solver invocation。
- No AIGC filter invocation。
- No Sandbox gate changes or forced execution。
- No DB/Redis/outbox/notification/billing/cost telemetry writes。
- No new runtime dependency。
- No raw provider payload、raw user message、full generated code、secret-like text、traceback、host path、sandbox output 或 queue payload in response/UI text。

### Story Review Rounds

### Round 1 - Data Consistency Review (2026-05-29)

Findings applied:
- N12 “用户查看”容易被误解为必须创建 public Chat UI；story 已限定为 internal beta response display preview + `packages/ui` component contract，不新增公开页面或 4.C flow。
- CRG14 `0.6-0.85` 容易在 `0.85` 边界歧义；story 已锁定 `score >= 0.85` high、`0.6 <= score < 0.85` mid、`score < 0.6` low。
- UI low tier 与 4.B.3 escalation 可能双重触发；story 已规定 display tier 只读 Critic/HumanReview 状态，不创建 queue、不重写 `human_review`.
- bilingual reasoning 可能泄漏 Critic raw/code/prompt；story 已要求 bounded deterministic/sanitized reasoning 和 no-leak tests。

Status: PASS after fixes.

### Round 2 - Function / Dependency Consistency Review (2026-05-29)

Findings applied:
- 当前已有 `packages/ui/src/components/ConfidenceLabel/index.tsx`；story 已要求强化现有组件，不重建、不复制到 `apps/web`。
- 当前 Tailwind tokens 已有 confidence colors；story 已禁止新增颜色系统或 runtime dependency。
- 当前 `useA11y` 会生成 `aria-describedby`；story 已要求组件真实渲染 matching id，特别覆盖 compact 模式。
- Chat service 当前没有 display schema；story 已要求新增独立 adapter，避免把 UI 文案塞进 `language_preview.summary` 或改变 `human_review.user_notice`。

Status: PASS after fixes.

### Round 3 - Drift / Boundary / Closure Review (2026-05-29)

Findings applied:
- Story 容易漂移到 4.B.5 AIGC filter、水印和 zero-width metadata；Boundary Rules 已明确不调用 AIGC runtime、不做水印。
- Story 容易漂移到 4.C public Chat confirmation UI、SSE、file upload、what-if；AC 与 Boundary Rules 已明确全部排除。
- Tests 源 AC “5 visual states × 3 i18n”容易只测 3 tiers；story 已要求 5 states 包含边界/invalid/compact，3 i18n/locale cases，并加 axe-core 0 violations。
- Closure 已加入 post-implementation review 要求：visual tier 边界、aria linkage、i18n 文案、human-review 语义一致性、no-leak 和测试证据。

Status: PASS after fixes. Story is ready for development.

### Test / Validation Notes

Expected commands:

```bash
pnpm -C packages/ui test -- --run src/components/ConfidenceLabel/index.test.tsx
pnpm -C packages/ui test:a11y
pnpm -C packages/ui typecheck
$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests/test_internal_beta.py -q
$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests -q
uv run mypy apps packages
uv tool run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

RED expectation: add ConfidenceLabel and Chat display tests first; they should fail because current component lacks complete bilingual/compact aria behavior and response lacks `critic_confidence_display`.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-29 - Story draft created from Epic 4.B source AC, PRD N12, architecture N Chat ownership, existing `ConfidenceLabel`, existing `useA11y`/tokens/test stack, Chat Critic/HumanReview contracts, and 4.B.1-4.B.3 learnings.
- 2026-05-29 - Story review round 1 applied data consistency fixes: scoped “用户查看” to internal beta display preview + UI component, pinned bracket boundaries, separated display tier from escalation, and required no-leak bilingual reasoning.
- 2026-05-29 - Story review round 2 applied function/dependency fixes: reuse existing ConfidenceLabel/tokens, no new dependency, fix aria-describedby linkage, and add Chat display adapter instead of mutating language/human-review text.
- 2026-05-29 - Story review round 3 applied drift/boundary/closure fixes: blocked 4.B.5/4.C/SSE/public UI drift and made test/review gates explicit.
- 2026-05-29 - Dev story implementation started; sprint status moved from ready-for-dev to in-progress.
- 2026-05-29 - RED tests added for `ConfidenceLabel`, chat confidence display adapter, and internal beta response contract; failures confirmed missing `chat_service.confidence_display` and `critic_confidence_display`.
- 2026-05-29 - Implemented `CriticConfidenceDisplayPreview`, deterministic confidence display adapter, internal beta response wiring, and `ConfidenceLabel` bilingual/locale/compact aria hardening.
- 2026-05-29 - Focused validation passed: ConfidenceLabel Vitest, UI a11y, chat confidence display tests, and internal beta contract tests.
- 2026-05-29 - Full validation passed: `packages/ui` tests/typecheck, chat-service test suite, `mypy apps packages`, `git diff --check`, and pre-commit.
- 2026-05-29 - Post-implementation adversarial review applied fixes for response cross-field drift validation, a11y script coverage, and sandbox negative-test masking.

### Completion Notes

Implemented the 4.B.4 confidence display contract end-to-end without adding public Chat routes, SSE, Console queue UI, AIGC runtime invocation, provider calls, DB/Redis/outbox writes, or Sandbox gate changes. `critic_confidence_display` is derived only from Critic and HumanReview previews, and `ConfidenceLabel` now supports CRG14 brackets, bilingual reasoning, locale display modes, invalid-score fail closed behavior, and real `aria-describedby` linkage in compact and non-compact modes.

Post-implementation review result: PASS after fixes. Review covered boundary values, drift risks, data consistency, dependency consistency, no-leak behavior, human-review semantic consistency, aria linkage, i18n copy, test masking, and closure evidence.

### File List

- `_bmad-output/stories/4-b-4-confidence-label-ui.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/chat-service/src/chat_service/confidence_display.py`
- `apps/chat-service/src/chat_service/main.py`
- `apps/chat-service/src/chat_service/schemas.py`
- `apps/chat-service/tests/test_confidence_display.py`
- `apps/chat-service/tests/test_internal_beta.py`
- `apps/chat-service/tests/test_sandbox.py`
- `packages/ui/package.json`
- `packages/ui/src/components/ConfidenceLabel/index.test.tsx`
- `packages/ui/src/components/ConfidenceLabel/index.tsx`

### Change Log

- 2026-05-29 - Created 4.B.4 story, completed three adversarial story review rounds, and marked ready-for-dev.
- 2026-05-29 - Started implementation and moved story/sprint status to in-progress.
- 2026-05-29 - Added backend confidence display schema/adapter/wiring and hardened `ConfidenceLabel` for bilingual display, CRG14 brackets, invalid score fallback, and aria reasoning.
- 2026-05-29 - Added RED/GREEN tests for UI, adapter, internal beta response, unauthorized no-leak behavior, drift boundaries, and negative schema contracts.
- 2026-05-29 - Completed post-implementation code review, applied fixes, passed full validation, and marked story done.
