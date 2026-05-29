# Story 4.B.3: Critic 置信度 <0.6 escalate (N9)

Status: done

owner: Chat Platform / AI Safety / Critic Lead

## Story

作为 Chat Platform 与 AI Safety 负责人，
我希望 internal beta Chat 在 Critic 置信度低于校准阈值时生成可审计的转人工升级预览与稳定事件信封，
以便在不开放公开 Chat、不引入真实 Redis/DB/通知服务、也不做 UI 视觉分级的前提下，先闭合 N9 的核心规则：`critic_preview.confidence < critic_preview.calibration_threshold` 必须进入人工 review queue contract，并向 internal beta response 暴露受限的用户通知文案“AI 不确定 / 转人工”。

## Acceptance Criteria

1. Chat internal beta response 增加 `human_review` 预览，并保持 4.A/4.B.1/4.B.2 既有边界。
   - 当前唯一 Chat 业务端点仍是 `POST /v1/chat/internal-beta/messages`；不得新增公开 `/v1/chat`、`/v1/chat/stream`、Critic public API、SSE、Console UI、真实 notification service、DB/Redis/outbox/billing/cost telemetry、Solver、AIGC filter runtime 或 Sandbox logs streaming。
   - internal beta 授权失败或禁用时必须继续在 body validation 前返回 sparse 404，不泄漏 `human_review`、queue/event schema、Critic/Sandbox/AIGC 信息。
   - 成功响应必须包含 `human_review`，同时继续保持 `public_access=false`、`provider_request_sent=false`、`solver_invoked=false`、`aigc_gate.public_surface=hidden`。
   - `human_review.escalated=true` 表示本次 internal beta response 根据 Critic 阈值生成了确定性人工 review queue preview；本 story 不声称真实 Redis stream/DB queue/通知已投递。
   - 顶层 `llm_invoked`、`critic_invoked`、`critic_llm_invoked`、`sandbox_invoked` 不得因 human-review preview 语义被篡改。
   - 响应不得新增或泄漏 `provider`、`raw_response`、`raw_response_redacted`、`provider_request`、`provider_response`、`raw_user_message`、`prompt`、完整 generated code、`sandbox_result`、`execution_log`、真实 queue payload、真实 notification payload 或 AIGC filter runtime 信息。

2. Escalation 规则严格复用 Critic 校准阈值。
   - 仅当 `critic_preview.confidence < critic_preview.calibration_threshold` 时，`human_review.escalated=true`。
   - 当 `critic_preview.confidence == critic_preview.calibration_threshold` 或更高时，`human_review.escalated=false`。
   - 规则必须适用于 `validated`、`needs_clarification`、`skipped` 三类 Critic status；低置信 fallback/skipped 也必须进入 preview queue contract，避免低置信被静默吞掉。
   - `threshold_source` 必须来自 `critic_preview.threshold_source`，不得重新读取或硬编码另一个阈值来源。
   - 本 story 不改变 4.B.1 Critic confidence 计算、不改 M3.5a 校准数据、不实现动态阈值更新。

3. `human_review` 数据契约可由 Pydantic 严格校验。
   - `HumanReviewPreview` 字段至少包含：`escalated`、`source`、`queue`、`event_type`、`review_id`、`reason_code`、`critic_confidence`、`calibration_threshold`、`threshold_source`、`user_notice`、`validation_errors`。
   - `source` 只能为 `critic_threshold_internal_beta` 或 `heuristic_human_review_internal_beta`。
   - `queue` 必须固定为 `events.critic`，`event_type` 必须固定为 `critic.review.escalated`，与 architecture Concern #17 保持一致；未升级时这两个字段仍可作为 contract target 暴露，但不得声称已投递。
   - `review_id` 必须 deterministic、bounded，基于 `message_id`、Critic task/status/confidence/threshold 生成，不包含原始用户消息或 generated code。
   - `reason_code` 至少区分 `critic_confidence_below_threshold`、`critic_not_validated_below_threshold`、`critic_skipped_below_threshold`、`not_escalated`。
   - `critic_confidence`、`calibration_threshold` 必须在 `[0.0, 1.0]`；`escalated=true` 必须满足 confidence < threshold，`escalated=false` 必须满足 confidence >= threshold。
   - `user_notice` 必须是受限双语 object：`zh="AI 不确定，已转人工复核。"`、`en="AI is uncertain; this has been routed for human review."`；未升级时 `user_notice=None`。
   - `validation_errors` 必须 bounded，使用与 Coder/Formulator/Critic/Sandbox 一致的 `field_path`、`message`、`remediation_hint_key` 结构。

4. Human-review preview 只创建 deterministic queue/event envelope，不创建真实基础设施。
   - 新增 `apps/chat-service/src/chat_service/human_review.py`，通过 Critic preview 和 message_id 生成 `HumanReviewRouteResult`。
   - 该 adapter 不得 import Redis、数据库 client、outbox、billing、notification provider、web Console、AIGC filter 或任何外部 SDK。
   - `human_review.event_type` 与 `queue` 是 future Redis Stream / critic-service queue 的稳定合同，不得写入真实 stream。
   - 不创建 `apps/critic-service` Python package 或 runtime service；当前 `apps/critic-service/config/critic-calibration.json` 仍只作为 Critic 阈值来源。
   - 不新增 migration、队列表、Redis stream producer、background worker、email/SMS/webhook、Linear/Jira ticket、Console review UI 或 admin endpoint。

5. Escalation 与 Sandbox/Language 边界清晰。
   - Human-review preview 必须在 Critic 之后生成；可以在 Sandbox 前或后生成，但低置信 Critic 已会让 Sandbox skipped，不能绕过 4.B.2 gate 去执行 Sandbox。
   - 低置信升级不能改变 `sandbox_preview` 的 contract：Critic 非 validated 时 Sandbox 必须仍为 `skipped`、`sandbox_invoked=false`。
   - Language preview 可以保持现有通用 disclaimer；本 story 只新增 `human_review.user_notice`，不把通知文案注入 `language_preview.summary`，避免漂移到 4.B.4/4.C UX。
   - 不做 ConfidenceLabel、红黄绿视觉分级、aria label、Console queue 页面、公开 Chat 状态展示或用户确认模型流程。

6. Tests 必须先红后绿，覆盖阈值边界和漂移场景。
   - 新增 `apps/chat-service/tests/test_human_review.py` 覆盖低于阈值升级、等于阈值不升级、高于阈值不升级、skipped/needs_clarification 低置信升级、deterministic review_id、event/queue contract、bounded notice、schema invariant、无 raw prompt/code/provider/sandbox 泄漏。
   - 扩展 `apps/chat-service/tests/test_internal_beta.py` 覆盖 successful internal beta response 包含 `human_review`，当前常见 skipped Critic 会产生 escalated preview，同时 provider/solver/AIGC/raw fields 不存在。
   - 保留 unauthorized invalid body 先 404 的回归测试，不因新增 `human_review` 触发 request validation 或响应泄漏。
   - 测试不得需要 live LLM provider、外部网络、真实 Redis、DB、outbox、notification provider、Sandbox runtime、Solver、AIGC 备案、Grafana、K8s 或 GitHub token。

7. Workflow tracking 和闭环清晰。
   - 本 story 记录三轮 pre-implementation story review，并在每轮后应用修正后才能进入 `ready-for-dev`。
   - dev-story 开始时将 sprint status 置为 `in-progress`；实现完成且测试通过后置为 `code-review`。
   - post-implementation code review 必须覆盖边界问题、漂移问题、数据一致性、依赖一致性、阈值边界、是否闭环、queue/event 命名、通知语义、sandbox gate 和测试证据。
   - code review 修正与完整验证通过后，story 与 sprint status 才能置为 `done`，随后 commit、push、创建 PR、CI 全绿后 merge/sync GitHub。

## Tasks / Subtasks

- [x] Task 1: 建立 Human Review 数据契约。 (AC: 3)
  - [x] 在 `apps/chat-service/src/chat_service/schemas.py` 增加 `HumanReviewPreview`、`HumanReviewNotice`、`HumanReviewValidationError` schema。
  - [x] 将 `human_review` 加入 `ChatInternalBetaMessageResponse`。
  - [x] 锁定 extra forbid、字段长度、queue/event_type literal、阈值 invariant、notice literal 和 reason_code 枚举。
- [x] Task 2: 实现 Critic 阈值升级 adapter。 (AC: 2, 4, 5)
  - [x] 新增 `apps/chat-service/src/chat_service/human_review.py`。
  - [x] 复用 `critic_preview.confidence`、`calibration_threshold`、`threshold_source`，实现 `< threshold` 升级与 `== threshold` 不升级。
  - [x] 生成 deterministic `review_id`，不包含用户原文、generated code 或 provider payload。
  - [x] 输出 `queue="events.critic"` 与 `event_type="critic.review.escalated"` 的 contract envelope，但不写 Redis/DB/outbox。
- [x] Task 3: Wire Chat internal beta response。 (AC: 1, 5)
  - [x] 在 `apps/chat-service/src/chat_service/main.py` Critic 后接入 human-review preview。
  - [x] 保持 gate-before-body-validation、AIGC hidden、provider_request_sent=false、solver=false、Sandbox gate 不变。
  - [x] 确认 Language preview 不承载新通知文案。
- [x] Task 4: RED/GREEN tests。 (AC: 1, 2, 3, 4, 5, 6)
  - [x] 先写失败测试并确认 `chat_service.human_review` / response `human_review` 缺失为 RED。
  - [x] 实现最小代码让测试转绿。
  - [x] 加 negative tests 覆盖 threshold equality、queue/event drift、notice drift、raw leak、sandbox gate 不绕过。
- [x] Task 5: 验证、审查与关闭。 (AC: 7)
  - [x] 跑 focused 与 full validation。
  - [x] 执行 post-implementation code review 并修复 findings。
  - [x] 更新 Dev Agent Record、File List、Change Log 和 sprint-status。
  - [x] commit、push、创建 PR、等待 CI、merge/sync GitHub。

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:411` 定义 Epic 4.B goal：Critic 置信度 `<0.6` 自动 escalate human review。
- `_bmad-output/planning/epics.md:1548` 定义 Story 4.B.3：Critic 置信度 `<0.6` escalate (N9)。
- `_bmad-output/planning/epics.md:1550` 的源 AC：Given Critic score `<0.6` / When escalate / Then 人工 review queue + 用户通知 "AI 不确定 / 转人工"。
- `_bmad-output/planning/prd.md:1494` 将 FR N9 定义为 Critic Agent can flag confidence `<0.6` + escalate to human review。
- `_bmad-output/planning/prd.md:1640` 明确 Critic 置信度阈值 `<0.6` 自动标记 + 转人工。
- `_bmad-output/planning/architecture.md:1651` 定义 Human-in-the-Loop Review Queue：`critic-service` 转人工队列（Redis Stream `events.critic`，event_type `critic.review.escalated`）+ Console review UI。
- `_bmad-output/planning/architecture.md:3207` 修正 `events.human_review` 命名为 `events.critic` + `critic.review.escalated`，本 story 必须遵守该命名。
- `_bmad-output/stories/m3-5a-critic-calibration.md` 已校准并测试阈值语义：`critic_confidence < threshold` escalates，`== threshold` 不 escalates。
- `_bmad-output/stories/4-b-1-critic-validate-code.md` 已暴露 `critic_preview.confidence`、`calibration_threshold` 和 `threshold_source`，但明确不做 escalation。
- `_bmad-output/stories/4-b-2-sandbox-gvisor-execute.md` 已确保 Critic 非 validated 时 Sandbox skipped；4.B.3 不得绕过该 gate。

### Current Repository Reality

- `apps/chat-service/src/chat_service/main.py` 当前链路是 Router -> Formulator -> Coder -> Critic -> Sandbox -> Language preview。
- `apps/chat-service/src/chat_service/schemas.py` 当前没有 `HumanReviewPreview`。
- `apps/chat-service/src/chat_service/critic.py` fallback/skipped confidence 分别为 0.4/0.0，低于 threshold 0.6，应触发 4.B.3 escalation preview。
- `apps/chat-service/src/chat_service/sandbox.py` 只在 Critic validated + checks pass 时执行；低置信 fallback/skipped 会保持 Sandbox skipped。
- `apps/chat-service/tests/test_internal_beta.py` 当前断言 `human_review_queue` 和 `escalated` 不存在；4.B.3 需要更新为新的 `human_review` contract，同时仍禁止旧字段名泄漏。
- 当前 repo 没有 Redis stream producer、DB queue 表、notification provider、critic-service Python package 或 Console queue backend。

### Previous Story Intelligence

- 4.B.1 的低置信/fallback 状态原本只 preview、不触发 queue；4.B.3 正是补齐该闭环。
- 4.B.2 的 Sandbox gate 依赖 Critic validated，因此低置信升级不能导致 Sandbox 执行。
- M3.5a/M3.5b 已经建立校准数据、threshold config 和 annotation review UI 的离线/Console素材；4.B.3 不改 ground truth，不创建新 UI。
- Architecture 允许最终 Redis Stream `events.critic`，但本 repo 当前缺乏运行时基础设施；本 story 采用 deterministic event envelope 先锁定 contract，避免假称真实投递。

### Implementation Guidance

- 优先新增 `chat_service/human_review.py`，保持和 `critic.py`、`sandbox.py` 风格一致：dataclass route result、小 helper、fail closed preview、无 runtime side effect。
- `review_id` 建议使用 `hrv_` + sha256(message_id/status/task/confidence/threshold/threshold_source) 前 24 位；不得 hash 原始 message。
- `reason_code` 建议：
  - `critic_confidence_below_threshold`：Critic validated 但 confidence < threshold。
  - `critic_not_validated_below_threshold`：Critic needs_clarification 且 confidence < threshold。
  - `critic_skipped_below_threshold`：Critic skipped 且 confidence < threshold。
  - `not_escalated`：confidence >= threshold。
- `source` 建议：升级时 `critic_threshold_internal_beta`；未升级时 `heuristic_human_review_internal_beta`。
- `user_notice` 只在 escalated=true 时出现，不要注入 `language_preview.summary`。
- 不要新增顶层 `escalated` 或旧式 `human_review_queue` 字段；统一使用 `human_review.escalated`。

### Boundary Rules

- No public Critic API。
- No new public Chat route。
- No SSE。
- No real Redis Stream / DB / outbox write。
- No notification provider / email / SMS / webhook / Linear / Jira ticket。
- No Console UI / ConfidenceLabel / red-yellow-green visual bracket。
- No Solver invocation。
- No AIGC filter invocation。
- No Sandbox gate changes or forced execution。
- No billing/cost telemetry writes。
- No new runtime dependency。
- No raw provider payload、raw user message、full generated code、secret-like text、traceback、host path 或 result file contents in response/log-like fields。

### Story Review Rounds

### Round 1 - Data Consistency Review (2026-05-29)

Findings applied:
- 原 AC “人工 review queue + 用户通知”容易被误解为真实 Redis/DB/通知已经投递；story 已改为 deterministic queue/event preview contract，并明确不声称真实投递。
- Queue 命名存在历史漂移风险；story 已锁定 `queue="events.critic"` 与 `event_type="critic.review.escalated"`，禁止旧 `events.human_review`。
- 阈值边界容易写成 `<=`；story 已明确 `confidence < threshold` 升级、`confidence == threshold` 不升级，并要求 schema/test 锁定 invariant。
- `review_id` 可能泄漏原文或代码；story 已规定只基于 message_id 与 bounded Critic metadata 生成。

Status: PASS after fixes.

### Round 2 - Function / Dependency Consistency Review (2026-05-29)

Findings applied:
- Architecture 长期目标是 critic-service + Redis Stream + Console UI，但当前仓库没有这些 runtime；story 已限定不创建 Redis/DB/outbox/notification/Console backend，仅创建 stable envelope。
- 4.B.3 容易误改 Critic 阈值读取；story 已规定复用 `critic_preview.calibration_threshold` 和 `threshold_source`，不重新读取配置、不改 M3.5a 数据。
- 低置信升级可能绕过 Sandbox gate；story 已要求 low-confidence/fallback/skipped 进入 human review preview 时，Sandbox 仍保持 skipped。
- 依赖边界复核后确认无需新 runtime dependency、无需 provider SDK、无需 Redis/DB client、无需 AIGC/Solver/Sandbox runtime 改动。

Status: PASS after fixes.

### Round 3 - Drift / Boundary / Closure Review (2026-05-29)

Findings applied:
- Story 容易漂移到 4.B.4 ConfidenceLabel / visual brackets；AC 与 Boundary Rules 已明确不做红黄绿、aria label、UI 或 Console queue 页面。
- Story 容易漂移到 4.C public Chat / SSE / confirmation model；AC 已明确不新增 public route、SSE、file upload、what-if 或用户确认模型流程。
- 旧测试断言 `human_review_queue`/`escalated` 不存在会与新 contract 冲突；story 已明确禁止旧顶层字段，只允许 `human_review.escalated`。
- Closure 已加入 post-implementation review 要求：阈值边界、queue/event 命名、通知语义、sandbox gate、依赖一致性和测试证据。

Status: PASS after fixes. Story is ready for development.

### Test / Validation Notes

Expected commands:

```bash
$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests/test_human_review.py -q
$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests/test_internal_beta.py -q
$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests -q
uv run pytest tests/test_critic_calibration.py -q
uv run mypy apps packages
uv tool run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

RED expectation: add Human Review tests first; they should fail because `chat_service.human_review` and response `human_review` do not exist yet.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-29 - Story draft created from Epic 4.B source AC, PRD N9 threshold requirement, architecture Human-in-the-Loop Review Queue naming, M3.5a calibration threshold semantics, current Chat/Critic/Sandbox implementation, and 4.B.1/4.B.2 learnings.
- 2026-05-29 - Story review round 1 applied data consistency fixes: clarified preview contract vs real queue delivery, locked queue/event names, pinned `< threshold` semantics, and bounded review_id inputs.
- 2026-05-29 - Story review round 2 applied function/dependency fixes: no Redis/DB/outbox/notification/Console runtime, reuse Critic preview threshold, preserve Sandbox gate, no new dependencies.
- 2026-05-29 - Story review round 3 applied drift/boundary/closure fixes: blocked 4.B.4/4.C/UI/SSE drift, allowed only `human_review.escalated`, and made post-implementation review gates explicit.
- 2026-05-29 - Dev story implementation started; sprint status moved from ready-for-dev to in-progress.
- 2026-05-29 - RED tests added and confirmed failing: `test_human_review.py` failed on missing `chat_service.human_review`; `test_internal_beta.py` failed on missing response `human_review`.
- 2026-05-29 - Implemented human-review schema, deterministic threshold adapter, and internal-beta response wiring; focused tests passed.
- 2026-05-29 - Focused and full validation passed: `test_human_review.py` (`14 passed`), `test_internal_beta.py` (`25 passed`), `apps/chat-service/tests` (`121 passed`), `tests/test_critic_calibration.py` (`23 passed`), `uv run mypy apps packages`, `uv tool run pre-commit run --all-files --show-diff-on-failure`, and `git diff --check`.
- 2026-05-29 - Post-implementation code review completed: no patch findings after checking threshold boundary, queue/event naming, schema invariants, no-infrastructure side effects, notice placement, Sandbox gate preservation, and leak boundaries.

### Completion Notes

Implemented internal beta `human_review` preview contract with strict Pydantic invariants, deterministic bounded review IDs, Critic threshold `<` escalation semantics, and queue/event contract envelope only. Language preview, Sandbox gate, AIGC hidden boundary, provider/solver flags, and unauthorized sparse 404 behavior remain unchanged.
Post-implementation review found no required code patches. Focused, service-level, calibration, type, pre-commit, and diff validations are green.

### File List

- `_bmad-output/stories/4-b-3-critic-confidence-escalate.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/chat-service/src/chat_service/human_review.py`
- `apps/chat-service/src/chat_service/main.py`
- `apps/chat-service/src/chat_service/schemas.py`
- `apps/chat-service/tests/test_human_review.py`
- `apps/chat-service/tests/test_internal_beta.py`

### Change Log

- 2026-05-29 - Created 4.B.3 story, completed three adversarial story review rounds, and marked ready-for-dev.
- 2026-05-29 - Added human-review preview implementation and RED/GREEN tests for escalation contract.
- 2026-05-29 - Completed post-implementation code review and final validation; story/sprint status moved to done for GitHub sync.
