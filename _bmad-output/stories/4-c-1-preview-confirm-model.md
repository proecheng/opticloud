# Story 4.C.1: Preview + confirm AI 模型 before solve

Status: done

owner: Chat Platform / Chat UX Workflow / AI Safety

## Story

作为 internal beta Chat 用户和 Chat Platform owner，
我希望在 Formulator + Coder + Critic + Sandbox 链路之后看到一个稳定的 AI 模型确认预览，
以便用户在任何求解、计费、SSE 或公开 Chat 之前，可以核对变量、目标、约束和代码，并看到 confirm/edit/cancel 三个明确动作。

## Acceptance Criteria

1. Chat internal beta response 新增 `model_preview`，聚合既有 Formulator/Coder safety chain。
   - 当前唯一 Chat 业务端点仍是 `POST /v1/chat/internal-beta/messages`；不得新增公开 `/v1/chat`、`/v1/chat/stream`、SSE、conversation persistence、ChatInterface UI、file upload、what-if follow-up、Solver submission、Billing、DB/Redis/outbox 或 public Chat route。
   - internal beta 授权失败或禁用时必须继续在 body validation 前返回 sparse 404，不泄漏 `model_preview`、actions、schema、AIGC watermark、Critic/Sandbox/HumanReview 或 provider 信息。
   - 成功响应必须包含 `model_preview`，并继续保持 `mode="internal_beta"`、`public_access=false`、`provider_request_sent=false`、`solver_invoked=false`、`aigc_gate.public_surface=hidden`。
   - `model_preview` 是 response-only preview contract；本 story 不实现 confirm/edit/cancel mutation endpoint，不创建 solve task，不提交 Optimization/Prediction。

2. `model_preview` 数据契约稳定、可由 Pydantic 严格校验。
   - 字段固定为：`preview_id`、`status`、`source`、`task_type`、`variables`、`objective`、`constraints`、`code_artifact`、`actions`、`requires_human_review`、`critic_confidence`、`sandbox_status`、`validation_errors`。
   - `preview_id` 必须匹配 `^mpv_[0-9a-f]{16}$`，由 message id + bounded model digest deterministic 生成；digest input 只允许 `task_type`、Formulator variables/objective/constraints 的 canonical JSON、Coder artifact sha256、Critic confidence、Sandbox status 和 action enabled flags，不得包含用户原文、tenant、user、provider payload、raw completion、完整 code 或 secret-like text。
   - `status` 只能为 `ready_to_confirm | needs_clarification | blocked`；`source` 固定为 `chat_model_preview_internal_beta`。
   - `variables`、`objective`、`constraints` 必须来自 `formulator_preview`，不得重新解析用户消息、不得填充假变量、假约束或假目标。
   - `code_artifact` 必须复用现有 `CoderCodeArtifact` schema 并来自 `coder_preview.artifact`；当 Coder 非 `generated` 或 artifact 为 null 时必须为 `null`。
   - `critic_confidence` 必须等于 `critic_preview.confidence`；`requires_human_review` 必须等于 `human_review.escalated`；`sandbox_status` 必须等于 `sandbox_preview.status`。
   - `validation_errors` 使用 bounded `{field_path, message, remediation_hint_key?}`，最多 10 条；`field_path` 必须以 `formulator_preview`、`coder_preview`、`critic_preview`、`sandbox_preview`、`human_review` 或 `model_preview` 开头，方便客户端定位来源。
   - `validation_errors` 不得包含 prompt、raw response、provider payload、完整 generated code、用户原文、secret、traceback、host path 或 queue payload。

3. confirm/edit/cancel 是稳定的一键 action descriptors，不触发副作用。
   - `actions` 必须按固定顺序返回 `confirm`、`edit`、`cancel` 三项；不得缺项、重复或换序。
   - 每项字段固定：`kind`、`label_zh`、`label_en`、`enabled`、`client_action`、`disabled_reason_code`。
   - `client_action` 只能是 `chat.model_preview.confirm`、`chat.model_preview.edit`、`chat.model_preview.cancel`，用于未来 4.C.6 ChatInterface 本地交互绑定，不是 HTTP endpoint；不得被 route handler、OpenAPI path、SDK API 或 server mutation 消费。
   - `disabled_reason_code` 只能为 `null` 或固定枚举：`model_not_ready`、`needs_clarification`、`safety_gate_blocked`、`human_review_required`、`sandbox_not_succeeded`、`task_type_unknown`、`dependency_drift`。
   - `confirm` 只在 `status="ready_to_confirm"` 时 enabled 且 `disabled_reason_code=null`；否则 disabled 且必须有非空枚举 reason。
   - `edit` 和 `cancel` 必须 enabled，使用户能改模型或退出流程；二者不得触发求解、计费或持久化。
   - 不得新增 `confirm_url`、`edit_url`、`cancel_url`、`solve_url`、`charge_id`、`optimization_id`、`prediction_id`、`conversation_id`、queue id、idempotency key 或外部 callback。

4. 状态判定必须闭合且与 4.A/4.B 数据一致。
   - `ready_to_confirm` 仅当：
     - `formulator_preview.status=="extracted"`；
     - `coder_preview.status=="generated"` 且 artifact 非 null；
     - `critic_preview.status=="validated"` 且三项 checks 全部 passed；
     - `human_review.escalated==false`；
     - `sandbox_preview.status=="succeeded"` 且 `sandbox_invoked==true`；
     - `task_type!="unknown"`。
   - 状态优先级固定：dependency drift / safety block > needs clarification > ready。任何跨字段不一致先 `blocked`，不得被 clarification 覆盖。
   - Formulator/Coder 缺字段、unknown task、needs clarification 或 skipped 时，`status="needs_clarification"`，confirm disabled，validation errors 必须指向对应上游字段；其中 `task_type=="unknown"` 的 confirm reason 必须是 `task_type_unknown`。
   - Critic 未 validated、confidence below threshold 导致 human review、Sandbox `failed`/`policy_blocked`/`skipped` 或 safety gate 不满足时，`status="blocked"`，confirm disabled，validation errors 必须指向 Critic/HumanReview/Sandbox 字段。
   - `model_preview.task_type` 必须与 Formulator/Coder/Critic/Sandbox 的非 unknown task_type 保持一致；检测到 drift 时必须 fail closed 为 `blocked`，confirm reason 为 `dependency_drift`。
   - 如果多个 gate 同时失败，`validation_errors` 最多保留 10 条，按 Formulator -> Coder -> Critic -> HumanReview -> Sandbox -> ModelPreview 顺序输出，保证客户端显示稳定。

5. 边界不漂移到 4.C.2-4.C.6 或 Billing/Solver。
   - 不新增 SSE、stream chunk、logs stream、FilePicker、CSV/Excel/JSON upload、what-if follow-up、partial upload recovery 或 full `ChatInterface`。
   - 可引用 `packages/ui/ConfirmationModal` 作为未来 UI consumer，但本 story 不改 packages/ui 或 apps/web；backend contract 必须通过 chat-service tests 闭合，不能为了测试引入 UI scope。
   - 不调用 Solver、Sandbox 以外的新 executor、Billing、Credits estimate、DB/Redis/outbox、notification、human review queue write、AIGC filing service 或 live provider。
   - 不改变 `language_preview.aigc_watermark`、`aigc_gate.status=filing_pending`、`public_surface=hidden`、`llm_invoked`、`critic_invoked`、`critic_llm_invoked` 或 `sandbox_invoked` 语义。

6. Tests 必须先红后绿，覆盖 contract、状态机和无副作用边界。
   - 新增 focused tests（建议 `apps/chat-service/tests/test_model_preview.py`）先断言 `chat_service.model_preview` / response `model_preview` 缺失为 RED。
   - 覆盖 ready preview：变量、目标、约束来自 Formulator；code 来自 Coder；confirm/edit/cancel 三动作齐全；confirm enabled；preview_id deterministic。
   - 覆盖 clarification preview：Formulator/Coder 不满足时 confirm disabled，edit/cancel enabled，validation errors bounded 且指向上游字段。
   - 覆盖 blocked preview：Critic/HumanReview/Sandbox gate 不满足时 confirm disabled，不返回 solve/charge/conversation identifiers。
   - 覆盖 drift preview：Formulator/Coder/Critic/Sandbox task_type 不一致时 `status="blocked"`、confirm reason `dependency_drift`。
   - 覆盖 unknown preview：unknown task_type 时 `status="needs_clarification"`、confirm reason `task_type_unknown`、edit/cancel enabled。
   - 扩展 `test_internal_beta.py`，确认 successful internal beta response 包含 `model_preview`，unauthorized invalid body 仍先 404 且不泄漏 `model_preview`。
   - 扩展 schema negative tests，覆盖 actions 缺项/换序、ready 状态无 code、confirm disabled reason drift、cross-field drift。
   - 测试不得需要 live LLM provider、外部网络、真实 DB/Redis/outbox、Solver、Billing、SSE、AIGC 备案、K8s 或 GitHub token。

7. Workflow tracking 和闭环清晰。
   - 本 story 记录三轮 pre-implementation adversarial review，并在每轮后应用修正后才能进入 implementation。
   - dev-story 开始时将 sprint status 置为 `in-progress`；实现完成且测试通过后置为 `code-review`。
   - post-implementation code review 必须覆盖边界问题、漂移问题、数据一致性、依赖一致性、是否闭环、action descriptors、preview/source consistency、no-side-effect flags 和测试证据。
   - code review 修正与完整验证通过后，story 与 sprint status 才能置为 `done`，随后 commit、push、创建 PR、等待 CI、merge/sync GitHub。

## Tasks / Subtasks

- [x] Task 1: 建立 `model_preview` schema 和 action descriptor contract。 (AC: 2, 3, 4)
  - [x] 在 `apps/chat-service/src/chat_service/schemas.py` 增加 ModelPreview schema、action schema、validation error schema 和相关 literals；复用 `TaskType` 与 `CoderCodeArtifact`，不得复制 code artifact 模型。
  - [x] 锁定 preview_id pattern、status/source/action enum、disabled_reason_code enum、action 顺序、confirm enabled/disabled consistency、extra forbid。
  - [x] 将 `model_preview` 加入 `ChatInternalBetaMessageResponse`，并用 model validator 锁定与上游字段的一致性。
- [x] Task 2: 实现 pure model-preview builder。 (AC: 1, 2, 3, 4, 5)
  - [x] 新增 `apps/chat-service/src/chat_service/model_preview.py`，只读取 Formulator/Coder/Critic/Sandbox/HumanReview previews。
  - [x] deterministic 生成 `preview_id`，只使用 bounded model digest，不纳入 raw message、tenant/user、provider payload、完整 code 或 secret-like text。
  - [x] 实现固定优先级的 `ready_to_confirm`、`needs_clarification`、`blocked` 判定与 bounded validation errors。
  - [x] 确保不调用 Solver/Billing/DB/Redis/outbox/SSE/provider，不执行任何 mutation，不新增 route 或 OpenAPI path。
- [x] Task 3: Wire Chat internal beta response。 (AC: 1, 3, 4, 5)
  - [x] 在 `apps/chat-service/src/chat_service/main.py` Sandbox/HumanReview 结果之后生成 `model_preview`。
  - [x] 保持 gate-before-body-validation、AIGC hidden、provider_request_sent=false、solver_invoked=false。
  - [x] 确认 response 不出现 solve/charge/conversation/action URL 等执行字段。
- [x] Task 4: RED/GREEN tests。 (AC: 1-6)
  - [x] 先写失败 tests 并确认缺少 `chat_service.model_preview` / `model_preview` response 为 RED。
  - [x] 实现最小代码转 GREEN。
  - [x] 加 schema negative tests 覆盖 action/order/status drift、ready-without-code、cross-field mismatch、unknown task 和 dependency drift。
- [x] Task 5: 验证、审查与关闭。 (AC: 7)
  - [x] 跑 focused 与 full validation。
  - [x] 执行 post-implementation code review 并修复 findings。
  - [x] 更新 Dev Agent Record、File List、Change Log 和 sprint-status。
  - [ ] commit、push、创建 PR、等待 CI、merge/sync GitHub。

### Review Findings

- [x] [Review][Patch] Human review / safety gate priority was weaker than AC4 status priority [`apps/chat-service/src/chat_service/model_preview.py`] — Fixed by making human review, Critic safety failure and Sandbox non-success block before clarification, and by adding focused coverage for human-review-before-clarification priority.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:422` 定义 Epic 4.C 目标：用户可 preview+confirm 模型 before solve、SSE、上传文件、what-if follow-up。
- `_bmad-output/planning/epics.md:1573` 定义 Story 4.C.1：Preview + confirm AI 模型 before solve (N6)。
- `_bmad-output/planning/epics.md:1575` 源 AC：Given Formulator + Coder 输出 / When 用户看 preview 含变量 + 约束 + 代码 / Then 一键 confirm/edit/cancel。
- `_bmad-output/planning/prd.md:1491` 将 FR N6 定义为用户 can preview+confirm AI 模型 before solve。
- `_bmad-output/planning/epics.md:1593` 将 full `ChatInterface` 放到 4.C.6；4.C.1 不应提前实现完整 Chat UI。
- `_bmad-output/planning/epics.md:1577` 将 SSE 放到 4.C.2；4.C.1 不应新增 stream route。
- `_bmad-output/planning/epics.md:1581`、`1585`、`1589` 分别将 file upload、what-if follow-up、partial upload recovery 放到 4.C.3-4.C.5。

### Current Repository Reality

- `apps/chat-service/src/chat_service/main.py` 当前唯一业务端点是 `POST /v1/chat/internal-beta/messages`。
- 当前 internal beta 链路为 Router -> Formulator -> Coder -> Critic -> HumanReview -> ConfidenceDisplay -> Sandbox -> Language。
- `apps/chat-service/src/chat_service/schemas.py` 已有 `FormulatorPreview`、`CoderPreview`、`CriticPreview`、`SandboxPreview`、`HumanReviewPreview`、`LanguagePreview` 和 response flags。
- `apps/chat-service/src/chat_service/formulator.py` 负责结构化 variables/objective/constraints preview。
- `apps/chat-service/src/chat_service/coder.py` 负责 Python `CoderCodeArtifact` preview 与 AST/Pydantic safety validation。
- `apps/chat-service/src/chat_service/critic.py` 负责 Critic static readiness 和 calibration threshold。
- `apps/chat-service/src/chat_service/sandbox.py` 负责 M3.1 deterministic local Sandbox contract preview。
- `packages/ui/src/components/ConfirmationModal/index.tsx` 已存在 Tier 1 modal，可作为未来 UI consumer；但 4.C.6 才实现 full ChatInterface。

### Previous Story Intelligence

- 4.A.3/4.A.4 已建立 Formulator/Coder preview 数据边界：不调用 Solver/Sandbox/Billing，不暴露 provider raw payload。
- 4.B.1-4.B.2 已建立 Critic/Sandbox gate；4.C.1 的 confirm 必须尊重这些 gates，不能绕过 safety chain。
- 4.B.3/4.B.4 已建立 HumanReview 和 confidence display；`model_preview.requires_human_review` 必须与 `human_review.escalated` 一致，不重复创建 queue。
- 4.B.5/4.B.7 已锁定 AIGC watermark 和 red-team gate；4.C.1 不改变 `language_preview` filter/watermark。
- 4.B.6 已明确 logs/SSE streaming deferred；4.C.1 不实现 stream/logs。

### Implementation Guidance

- 建议新增 `chat_service/model_preview.py`，保持 pure builder 风格：
  - `generate_model_preview(prompt_id, formulator_preview, coder_preview, critic_preview, sandbox_preview, human_review) -> ModelPreview`
  - 小 helper：`_preview_id(...)`、`_status(...)`、`_actions(...)`、`_collect_validation_errors(...)`。
- `preview_id` 可用 SHA-256 over `{prompt_id, task_type, variables, objective, constraints, code_sha256, critic_confidence, sandbox_status, action_enabled}` 的 canonical JSON，取前 16 hex。
- `model_preview` 应复用现有 `CoderCodeArtifact` schema，而不是复制 code artifact shape；如果需要在 schema 中声明类型，直接引用 `CoderCodeArtifact | None`。
- 对上游 validation errors 的转换只保留 safe field_path/message/remediation key；发现 secret/raw/provider/path 等内容时使用通用安全错误消息。
- 不要把 `confirm` 映射成 HTTP route；本 story 只是让客户端知道可本地一键 confirm/edit/cancel。真正 ChatInterface 和状态管理属于 4.C.6。

### Boundary Rules

- No public Chat route.
- No SSE / stream chunks / logs stream.
- No file upload / FilePicker.
- No what-if follow-up.
- No partial upload recovery.
- No full ChatInterface implementation.
- No Solver or Prediction submission.
- No Billing/Credits estimate or charge.
- No DB/Redis/outbox/conversation persistence.
- No new provider SDK or live network call.
- No AIGC filing status read/update.
- No human review queue write beyond existing preview.
- No changes to packages/ui or apps/web unless a test-proven contract gap requires it.
- No raw provider payload、raw user message、full generated code duplicate outside `code_artifact.code`、secret-like text、traceback、host path、sandbox output 或 queue payload in validation/action fields。

## Story Review Rounds

### Round 1 - Boundary / Data Consistency Review (2026-05-29)

Findings applied:
- `preview_id` 原要求可能把完整 code 放入 hash input，造成不必要的敏感数据处理面；story 已改为使用 code sha256 和 bounded model digest。
- `disabled_reason_code` 原本只是 bounded string，客户端无法稳定分支；story 已固定 reason enum，并要求 enabled confirm 时 reason 为 null。
- `ready_to_confirm` 原本只看 Sandbox status，可能在 drifted object 中把 skipped/succeeded 混淆；story 已要求 `sandbox_status=="succeeded"` 且 `sandbox_invoked==true`。
- validation errors 原本没有来源前缀，客户端可能猜错修复位置；story 已要求 field_path 以前序 preview/source 开头。

Status: PASS after fixes.

### Round 2 - Dependency / Function Consistency Review (2026-05-29)

Findings applied:
- `code_artifact` 原本可能复制 Coder artifact shape，造成 schema drift；story 已要求复用 `CoderCodeArtifact`。
- `client_action` 原本可能被误实现成 server endpoint 或 SDK mutation；story 已明确它只是一段客户端本地动作 descriptor，不得新增 route/OpenAPI path。
- UI 依赖边界原本留有“contract 无法测试就改 UI”的逃逸口；story 已改为 backend contract 必须由 chat-service tests 闭合，不引入 packages/ui/apps/web scope。
- 顶层 invocation flags 原本只提 provider/solver，未显式保护 Critic/Sandbox 语义；story 已要求不改变 `llm_invoked`、`critic_invoked`、`critic_llm_invoked`、`sandbox_invoked`。

Status: PASS after fixes.

### Round 3 - Drift / Closure Review (2026-05-29)

Findings applied:
- 多个 gate 同时失败时原 story 没有状态优先级，容易出现一会儿 blocked 一会儿 clarification；story 已固定 drift/safety block > clarification > ready。
- `unknown` task 原本只被笼统放入 clarification，客户端无法给出稳定 CTA；story 已要求 confirm reason 为 `task_type_unknown`。
- 跨上游 preview task_type drift 原本只说 fail closed，未固定 action reason；story 已要求 `dependency_drift`。
- validation errors 多来源时原 story 未规定顺序；story 已固定 Formulator -> Coder -> Critic -> HumanReview -> Sandbox -> ModelPreview，最多 10 条。
- Test plan 已补 unknown 和 dependency drift focused coverage，保证闭环。

Status: PASS after fixes. Story is ready for development.

## Test / Validation Notes

Expected commands:

```bash
$env:PYTHONPATH='apps/chat-service/src;apps/sandbox-runner/src;packages/shared-py'; uv run pytest apps/chat-service/tests/test_model_preview.py -q
$env:PYTHONPATH='apps/chat-service/src;apps/sandbox-runner/src;packages/shared-py'; uv run pytest apps/chat-service/tests/test_internal_beta.py -q
$env:PYTHONPATH='apps/chat-service/src;apps/sandbox-runner/src;packages/shared-py'; uv run pytest apps/chat-service/tests -q
uv run mypy apps packages
uv tool run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

RED expectation: add focused tests first; they should fail because `chat_service.model_preview` and response `model_preview` do not exist yet.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-29 - Story draft created from Epic 4.C.1 source AC, PRD N6, current 4.A/4.B Chat internal beta chain, and 4.C.2-4.C.6 boundary split.
- 2026-05-29 - Story review round 1 applied boundary/data fixes: bounded preview digest, disabled reason enum, sandbox_invoked consistency, and validation field_path source prefixes.
- 2026-05-29 - Story review round 2 applied dependency/function fixes: reuse CoderCodeArtifact, keep client_action non-server, no UI scope, and preserve invocation flag semantics.
- 2026-05-29 - Story review round 3 applied drift/closure fixes: fixed status priority, unknown/dependency drift reasons, validation error ordering, and focused test coverage.
- 2026-05-29 - Dev-story started after three review rounds; sprint status moved from ready-for-dev to in-progress and starting RED model preview tests.
- 2026-05-29 - RED confirmed: focused model-preview test failed because `chat_service.model_preview` did not exist; internal beta contract failed because response lacked `model_preview`.
- 2026-05-29 - GREEN implemented: added strict `ModelPreview` schemas, pure `generate_model_preview(...)` builder, internal beta wiring, focused tests, and synchronized existing sandbox response contract fixture.
- 2026-05-29 - Focused validation passed: `test_model_preview.py` 7 passed, `test_internal_beta.py` 26 passed, chat-service suite 152 passed.
- 2026-05-29 - Post-implementation code review found and fixed one priority issue: human review / safety / sandbox gates now block before clarification per AC4.
- 2026-05-29 - Final validation passed: focused model-preview/internal-beta 34 passed; chat-service suite 153 passed; `uv run mypy apps packages`; `uv tool run pre-commit run --all-files --show-diff-on-failure`; `git diff --check`.

### Implementation Plan

- Reuse existing Formulator/Coder/Critic/Sandbox/HumanReview previews as the only source of model-preview data.
- Add response-only action descriptors for confirm/edit/cancel; do not add mutation routes or UI.
- Keep `preview_id` deterministic with bounded digest inputs and no raw message/provider/code payload.
- Fail closed to `blocked` for dependency drift or safety gates, and to `needs_clarification` for missing model data.

### Completion Notes

- Added `model_preview` to Chat internal beta response as a response-only model confirmation contract.
- `confirm` is enabled only for fully ready previews; `edit` and `cancel` remain enabled for user recovery.
- `model_preview` reuses `CoderCodeArtifact`, mirrors upstream confidence/human-review/sandbox state, and does not introduce solve, billing, conversation, route, SSE, DB/Redis/outbox, or UI side effects.
- Added focused coverage for ready, clarification, blocked, unknown, dependency drift, action order, and schema drift.
- Post-review fix added explicit coverage that human-review/safety gates take priority over clarification in the aggregated `model_preview`.

### File List

- `_bmad-output/stories/4-c-1-preview-confirm-model.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/chat-service/src/chat_service/main.py`
- `apps/chat-service/src/chat_service/model_preview.py`
- `apps/chat-service/src/chat_service/schemas.py`
- `apps/chat-service/tests/test_internal_beta.py`
- `apps/chat-service/tests/test_model_preview.py`
- `apps/chat-service/tests/test_sandbox.py`

### Change Log

- 2026-05-29 - Created initial 4.C.1 story draft for pre-implementation adversarial review.
- 2026-05-29 - Completed three pre-implementation adversarial review rounds and moved story to ready-for-dev.
- 2026-05-29 - Started implementation and moved story/sprint status to in-progress.
- 2026-05-29 - Implemented Chat internal beta model preview contract and passed focused/chat-service validation.
- 2026-05-29 - Addressed post-implementation review finding, completed final validation, and moved story/sprint status to done.
