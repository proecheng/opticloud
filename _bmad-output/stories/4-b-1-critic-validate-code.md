# Story 4.B.1: Critic 验证生成代码 (N5)

Status: done

owner: Chat Platform / AI Safety / Critic Lead

## Story

作为 Chat Platform 与 Critic 负责人，
我希望 internal beta Chat 在 Coder 生成代码后增加 Critic 静态执行就绪验证预览，
以便在进入 Sandbox、用户确认、人工升级或公开 Chat 之前，先对生成代码的 schema、安全性和业务逻辑给出可审计的 confidence 与 reasoning，而不实际执行代码。

## Acceptance Criteria

1. Chat internal beta response 增加 `critic_preview`，并保持 4.A 既有边界。
   - 当前唯一 Chat 业务端点仍是 `POST /v1/chat/internal-beta/messages`；不得新增公开 `/v1/chat`、`/v1/chat/stream`、Critic public API、SSE、conversation persistence、Console UI、DB/Redis/outbox/billing/cost telemetry、Solver、Sandbox 或 AIGC filter runtime。
   - internal beta 授权失败或禁用时必须继续在 body validation 前返回 sparse 404，不泄漏 `critic_preview`、schema 或 AIGC 信息。
   - 成功响应必须包含 `critic_preview`、`critic_invoked` 和 `critic_llm_invoked`，同时继续保持 `public_access=false`、`provider_request_sent=false`、`solver_invoked=false`、`sandbox_invoked=false`、`aigc_gate.public_surface=hidden`。
   - `critic_invoked` 表示 Critic stage 已运行并产出 preview；`critic_llm_invoked` 仅表示 Critic stage 尝试调用 M3.8 LLM router。Coder 非 generated 时 `critic_invoked=true`、`critic_llm_invoked=false`，用于证明 Critic stage 没有被跳过但未越权调用 LLM。
   - 顶层 `llm_invoked` 必须纳入 `critic_llm_invoked`，但顶层 `provider_request_sent` 必须仍为 `Literal[False]`，不得由 Critic 引入 provider request 语义。
   - 响应不得新增或泄漏 `provider`、`raw_response`、`raw_response_redacted`、`provider_request`、`provider_response`、`sandbox_result`、`execution_log`、`human_review_queue`、`aigc_filter` 或真实用户原文。

2. Critic 只在 Coder 产生可验证代码 artifact 后执行静态验证。
   - 当 `coder_preview.status=="generated"` 且 `coder_preview.artifact` 非空时，Critic 通过 M3.8 `llm_router` task `critic_validation` 构造 prompt，并调用默认模型别名 `deepseek-v3.5`。
   - 当 Coder 为 `needs_clarification`、`skipped`、`artifact=None` 或 task_type 为 `unknown` 时，Critic 不调用 LLM，返回 `status="skipped"` 或 `status="needs_clarification"` 的安全预览，并记录 bounded validation error。
   - Critic 不执行代码，不导入生成 artifact，不调用 Sandbox、Solver、网络、文件系统、数据库、Redis、队列或任何外部 provider SDK。
   - LLMRouterError、未知 model alias、prompt validation failure、非 `stop` finish_reason、不可解析 completion 或安全检查失败时，Critic fail closed 为 heuristic preview，`critic_invoked` 与是否已尝试调用保持可解释。

3. `critic_preview` 数据契约可由 Pydantic 严格校验。
   - `CriticPreview` 字段至少包含：`status`、`source`、`task_type`、`confidence`、`reasoning`、`checks`、`validation_errors`、`supported_task_types`、`calibration_threshold`、`threshold_source`。
   - `status` 只能为 `validated | needs_clarification | skipped`；`source` 只能为 `llm_critic_internal_beta | heuristic_critic_internal_beta`。
   - `confidence` 必须在 `[0.0, 1.0]`；`reasoning` 必须非空、长度受限、不能包含原始用户消息、provider payload、secret-like text、raw response、dangerous code snippet 或 traceback。
   - `checks` 必须覆盖 `schema`、`safety`、`business_logic` 三项，每项给出 `passed`、bounded `message` 和可选 `field_path`；三项均为静态执行就绪判断，不代表 Sandbox 已运行或业务结果已求解。
   - `validation_errors` 必须 bounded，使用与 Coder/Formulator 一致的 `field_path`、`message`、`remediation_hint_key` 结构。

4. Critic 复用已有静态代码验证和校准配置，不重复造轮子。
   - Critic 必须复用 `chat_service.coder.validate_code_artifact(...)` 的 Pydantic + AST 安全检查结果作为 schema/safety 输入。
   - Critic 必须读取或绑定 `apps/critic-service/config/critic-calibration.json` 中的 `recommended_threshold=0.6`，并在 response 中暴露 `calibration_threshold=0.6` 与 `threshold_source="apps/critic-service/config/critic-calibration.json"`。
   - Calibration loader 必须从当前文件向 repo root 解析该配置路径；测试不得依赖当前工作目录。
   - 本 story 只暴露阈值上下文，不实现 `<0.6` human escalation，不创建 queue，不发送通知；该闭环归属 4.B.3。
   - 即使 `critic_preview.confidence < 0.6`，4.B.1 也只能在 preview 中呈现 confidence/reasoning，不能出现 `escalated=true`、`human_review_queue`、notification、UI label 或用户可见红黄绿分级。
   - 不创建 `apps/critic-service` Python package 或 runtime service；当前目录只作为校准配置来源。

5. Tests 必须先红后绿，覆盖 Critic 边界和漂移场景。
   - 新增 `apps/chat-service/tests/test_critic.py` 覆盖 prompt 构造、deterministic M3.8 completion、schema/safety/business_logic checks、Coder 非 generated 时不调用、LLMRouterError fallback、非 stop fallback、未知 alias fallback、sanitization 和 calibration threshold。
   - 扩展 `apps/chat-service/tests/test_internal_beta.py` 覆盖 successful internal beta response 包含 `critic_preview`，同时确认 provider/solver/sandbox/AIGC/queue/raw fields 不存在。
   - 测试必须断言 low-confidence preview 不触发 4.B.3 escalation 字段或队列副作用。
   - 保留 unauthorized invalid body 先 404 的回归测试，不因新增 `critic_preview` 触发 request validation 或响应泄漏。
   - 测试不得需要 live LLM provider、外部网络、Sandbox、Solver、DB、Redis、AIGC 备案、Grafana、K8s 或 GitHub token。

6. Workflow tracking 和闭环清晰。
   - 本 story 记录三轮 pre-implementation story review，并在每轮后应用修正后才能进入 `ready-for-dev`。
   - dev-story 开始时将 sprint status 置为 `in-progress`；实现完成且测试通过后置为 `code-review`。
   - post-implementation code review 必须覆盖边界问题、漂移问题、数据一致性、依赖一致性、是否闭环、prompt 泄漏、fallback 语义和测试证据。
   - code review 修正与完整验证通过后，story 与 sprint status 才能置为 `done`，随后 commit、push 并创建/同步 GitHub PR。

## Tasks / Subtasks

- [x] Task 1: 建立 Critic 数据契约与校准读取。 (AC: 3, 4)
  - [x] 在 `apps/chat-service/src/chat_service/schemas.py` 增加 Critic preview/check/error schema 和 `critic_invoked`、`critic_llm_invoked` response 字段。
  - [x] 新增 Critic calibration loader，读取 `apps/critic-service/config/critic-calibration.json` 并 fail closed 到固定 0.6。
  - [x] 锁定字段长度、枚举、extra forbid、confidence range 和 supported task types 顺序。
- [x] Task 2: 实现 Critic 静态验证流程。 (AC: 2, 4)
  - [x] 新增 `apps/chat-service/src/chat_service/critic.py`，构造 M3.8 `Prompt(task="critic_validation")`。
  - [x] 复用 `validate_code_artifact(...)`，生成 schema/safety/business_logic 三类 checks。
  - [x] 实现 generated artifact 调用路径、非 generated no-invocation 路径、LLM/alias/finish/parse fallback。
  - [x] Critic prompt metadata 只允许 `coder_status`、`coder_source`、`task_type`、`calibration_threshold`，不得包含 raw code 或 raw user message。
  - [x] 确保不执行代码、不调用 Sandbox/Solver/DB/Redis/network/filesystem。
- [x] Task 3: Wire Chat internal beta response。 (AC: 1, 2)
  - [x] 在 `apps/chat-service/src/chat_service/main.py` Coder 之后、Language preview 之前或之后接入 Critic preview。
  - [x] 保持 gate-before-body-validation、AIGC hidden、provider_request_sent=false、solver/sandbox=false。
  - [x] 确认响应不暴露 raw provider、queue、sandbox、AIGC filter 或原始 prompt。
- [x] Task 4: RED/GREEN tests。 (AC: 1, 2, 3, 4, 5)
  - [x] 先写失败测试并确认至少新增 Critic contract/internal beta expectation 为 RED。
  - [x] 实现最小代码让测试转绿。
  - [x] 加 negative tests 覆盖 unsafe artifact、reported unsafe reasoning、unknown alias、router error、non-stop finish_reason、Coder needs_clarification。
- [ ] Task 5: 验证、审查与关闭。 (AC: 6)
  - [x] 跑 focused 与 full validation。
  - [x] 执行 post-implementation code review 并修复 findings。
  - [x] 更新 Dev Agent Record、File List、Change Log 和 sprint-status。
  - [x] commit、push、创建或同步 GitHub PR。

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:409` 定义 Epic 4.B 目标：Critic 验证生成代码、低置信升级、Sandbox 隔离执行、用户可见 confidence/reasoning。
- `_bmad-output/planning/epics.md:1540` 定义 Story 4.B.1：Critic 验证生成代码 (N5)。
- `_bmad-output/planning/epics.md:1542` 的源 AC：Given Coder 输出 / When Critic 验证 schema + 安全 + 业务逻辑 / Then 输出 confidence + reasoning。
- `_bmad-output/planning/prd.md:1490` 将 FR N5 定义为 Critic validates generated code execution；4.B.1 将其落实为 Sandbox 前的静态执行就绪验证，不把“execution”解释为实际运行代码。
- `_bmad-output/planning/prd.md:1494` 将 FR N9 定义为 confidence `<0.6` escalate；本 story 只提供阈值上下文，不做升级闭环。
- `_bmad-output/planning/architecture.md:551` 长期目标是 independent Critic service；当前 repo 中 `apps/critic-service` 还不是 Python package。
- `_bmad-output/planning/architecture.md:2115` 附近提到 simplified inline critic fallback 与固定 0.6 threshold；这与本 story 的 internal beta inline preview 相匹配。
- `_bmad-output/planning/architecture.md:2437` 将 Critic async/deferred 作为 G6 latency failure 的 future mitigation；本 story 不改变同步 internal beta JSON 端点的公开延迟 hard-gate。

### Current Repository Reality

- `apps/chat-service/src/chat_service/main.py` 当前只有 `POST /v1/chat/internal-beta/messages` 和 `GET /health`。
- Chat internal beta 当前链路是 Router -> Formulator -> Coder -> Language preview。
- Gate-before-body-validation 是硬边界：disabled/unauthorized internal beta 请求必须在 body/schema validation 前返回 sparse 404。
- `apps/chat-service/src/chat_service/schemas.py` 已有 `RouterPreview`、`FormulatorPreview`、`CoderPreview`、`LanguagePreview` 和 response flags。
- `apps/chat-service/src/chat_service/coder.py` 已有 `validate_code_artifact(...)`，通过 Pydantic + AST 拒绝 unsafe imports/calls、markdown fences、raw/provider/secret-like text、dangerous runtime access。
- `packages/shared-py/opticloud_shared/llm_router/providers.py` 已支持 deterministic `critic_validation` task 文本，开头包含 `critic validation schema logic safety confidence calibrated review ...`。
- `apps/critic-service/config/critic-calibration.json` 已存在，`recommended_threshold=0.6`、`sample_count=50`、`target_stage=M3.5b`。
- `tools/critic_calibration/ground_truth_v1.json` 与 `tests/test_critic_calibration.py` 已验证 G9/M3.5b 校准数据；4.B.1 不改该数据集。
- Python import 边界：`apps/critic-service` 不是 Python package；Chat service 不得 import `apps.critic-service`，只能读取 JSON 配置或 fail closed 到固定阈值。

### Previous Story Intelligence

- 4.A.1 建立 internal beta fail-closed、≤5 trusted users、founder/legal signoff 和 sparse 404 行为。
- 4.A.2 建立 M3.8 LLM router 注入式 wrapper 与 offline deterministic 测试路径。
- 4.A.3/4.A.4 建立 Formulator/Coder 安全 preview：不调用 Solver/Sandbox，不暴露 provider raw payload。
- 4.A.5 增加 Language preview 并保持 `provider_request_sent=false`、无 frontend、无 public Chat、无 SSE、无 AIGC filter。
- 4.A.6 强化 G6 边界：internal beta JSON preview 不是 staging SSE hard-gate evidence，不能引入 false-pass evidence。

### Implementation Guidance

- 优先新增 `chat_service/critic.py`，保持和 `coder.py` 风格一致：dataclass route result、`build_*_prompt`、`parse_*_completion`、`generate_*_with_llm`、小的 helper 函数。
- Critic prompt 的 metadata 只允许安全小字段：`coder_status`、`coder_source`、`task_type`、`calibration_threshold`；不得放 raw user message、raw code、provider diagnostics 或 secret-like text。
- 如果需要将生成代码交给 LLM 评审，只能放在 user role content 中，且 completion 输出必须再次 sanitize；response reasoning 不得回显代码片段。metadata 不能包含代码。
- deterministic provider 返回自然语言时，可以将其作为 invocation evidence，然后由本地静态 checks 生成结构化 preview；不要要求 provider 在本 story 返回 JSON。
- `business_logic` check 在 4.B.1 先做静态一致性：artifact task_type、entrypoint/input/output model、基本 formulation presence，不求解、不执行、不验证数学最优性。
- `critic_invoked` 和 `critic_llm_invoked` 必须分开：前者用于说明 Critic stage 每次成功 internal beta response 都运行；后者用于说明是否实际尝试 M3.8 LLM router 调用。
- `confidence` 建议由本地 checks 决定：三项全 pass 且 LLM stop -> 高置信；schema/safety fail 或 fallback -> 降低置信；非 generated -> 低置信或 skipped。
- 对 `<0.6` 只暴露数值，不触发 human escalation；4.B.3 再实现 queue/notification。

### Boundary Rules

- No public Critic API。
- No new public Chat route。
- No SSE。
- No Sandbox execution。
- No Solver invocation。
- No AIGC filter invocation。
- No human review queue。
- No confidence label / UI visual bracket。
- No DB/Redis/outbox/billing/cost telemetry writes。
- No frontend/UI/ConfidenceLabel work。
- No new runtime dependency。
- No raw provider payload、raw user message、secret-like text、traceback 或 generated unsafe code snippet in response/log-like fields。

### Story Review Rounds

### Round 1 - Data Consistency Review (2026-05-29)

Findings applied:
- N5 源文档使用 "generated code execution" 容易被误读为实际执行代码；story 已改为 "静态执行就绪验证"，并在 Story、AC、Dev Notes 中明确不运行代码、不求解、不等同 Sandbox evidence。
- `critic_invoked` 原语义会混淆 Critic stage 运行与 LLM 调用；story 已新增 `critic_llm_invoked`，并规定 Coder 非 generated 时 `critic_invoked=true`、`critic_llm_invoked=false`。
- `checks.business_logic` 原本可能被理解为验证数学最优性；story 已限定为 task/artifact/formulation 静态一致性，不验证求解结果。

Status: PASS after fixes.

### Round 2 - Function / Dependency Consistency Review (2026-05-29)

Findings applied:
- `llm_invoked` 顶层汇总原先未明确纳入 Critic；story 已要求顶层 `llm_invoked` OR 入 `critic_llm_invoked`，同时 `provider_request_sent` 仍固定 false。
- Calibration 配置位于 `apps/critic-service/config`，但 `apps/critic-service` 不是 Python package；story 已禁止 package import，并要求从 repo root 读取 JSON 或 fail closed 到固定 0.6。
- Critic prompt metadata 原描述仍可能误放 raw code；story 已锁定 metadata allowlist，代码只能在 user role content 中进入 LLM，且 response reasoning 必须 sanitize。
- 依赖边界复核后确认无需新 runtime dependency、无需 provider SDK、无需 DB/Redis/Sandbox/Solver/AIGC module。

Status: PASS after fixes.

### Round 3 - Drift / Boundary / Closure Review (2026-05-29)

Findings applied:
- Story 容易漂移到 4.B.3/4.B.4/4.B.5；AC 已明确即使 confidence `<0.6` 也不做 escalation、queue、notification、ConfidenceLabel 或红黄绿 UI 分级。
- Tests 已补充 low-confidence 不触发 escalation 字段或队列副作用的要求，防止 N9 早落地。
- Boundary Rules 已补充 no confidence label / UI visual bracket，避免侵入 4.B.4。
- 三轮 story review 均已记录 PASS；Status 从 `story-review` 改为 `ready-for-dev`，可进入 dev-story。

Status: PASS after fixes. Story is ready for development.

### Test / Validation Notes

Expected commands:

```bash
uv run pytest apps/chat-service/tests/test_critic.py -q
uv run pytest apps/chat-service/tests/test_internal_beta.py -q
uv run pytest apps/chat-service/tests -q
uv run python scripts/validate_llm_router_contract.py
uv run pytest tests/llm_router/test_implementations_parity.py -q
uv run pytest tests/test_critic_calibration.py -q
uv run mypy apps packages
uv tool run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

RED expectation: add Critic tests first; they should fail because `chat_service.critic` and response `critic_preview` do not exist yet.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-29 - Story draft created from Epic 4.B source AC, PRD N5/N9 split, architecture inline Critic fallback, M3.8 LLM router contract, M3.5b calibration config, current Chat/Coder implementation, and 4.A.1-4.A.6 learnings.
- 2026-05-29 - Story review round 1 applied data consistency fixes: N5 execution wording narrowed to static execution-readiness, Critic stage/LLM invocation fields split, and business_logic scope constrained.
- 2026-05-29 - Story review round 2 applied function/dependency fixes: llm_invoked aggregation, calibration JSON path boundary, metadata allowlist, and no new runtime dependency.
- 2026-05-29 - Story review round 3 applied drift/boundary/closure fixes: blocked 4.B.3/4.B.4/4.B.5 scope creep, added low-confidence non-escalation test requirement, and moved story to ready-for-dev.
- 2026-05-29 - Dev-story started after three story review rounds; moving sprint status to in-progress and starting RED Critic tests.
- 2026-05-29 - RED confirmed: `uv run pytest apps/chat-service/tests/test_critic.py -q` failed because `chat_service.critic` did not exist; `uv run pytest apps/chat-service/tests/test_internal_beta.py -q` failed because `critic_preview` and Critic invocation flags were absent.
- 2026-05-29 - Added Critic schemas, `chat_service.critic`, calibration threshold loader, static checks, LLM fallback handling, and Chat internal beta wiring.
- 2026-05-29 - Added business-logic drift guard so task_type/code mismatch fails closed before LLM invocation.
- 2026-05-29 - Focused validation passed: `uv run pytest apps/chat-service/tests/test_critic.py -q`, `uv run pytest apps/chat-service/tests/test_internal_beta.py -q`, `uv run pytest apps/chat-service/tests -q`, `uv run python scripts/validate_llm_router_contract.py`, `uv run pytest tests/llm_router/test_implementations_parity.py -q`, and `uv run pytest tests/test_critic_calibration.py -q`.
- 2026-05-29 - Post-implementation code review found and fixed one Critic completion validation issue: deterministic M3.8 text with `deterministic_digest` must be accepted without leaking the digest, while arbitrary safe prose must not be treated as validated Critic output.
- 2026-05-29 - Review fix validation passed: `uv run pytest apps/chat-service/tests/test_critic.py -q`, `uv run pytest apps/chat-service/tests/test_internal_beta.py -q`, and `uv run mypy apps packages`.
- 2026-05-29 - Full closure validation passed: `uv run pytest apps/chat-service/tests -q`, `uv run python scripts/validate_llm_router_contract.py`, `uv run pytest tests/llm_router/test_implementations_parity.py -q`, `uv run pytest tests/test_critic_calibration.py -q`, `uv run mypy apps packages`, `uv tool run pre-commit run --all-files --show-diff-on-failure`, and `git diff --check`.
- 2026-05-29 - Story and sprint status moved to done after review fixes and full validation.
- 2026-05-29 - GitHub synchronized: committed, pushed `codex/4-b-1-critic-validate-code`, and opened PR #99.

### Completion Notes

- Implemented 4.B.1 as an inline internal beta Critic preview after Coder, without public Critic API, Sandbox, Solver, queue, UI, AIGC filter, DB/Redis, or provider payload exposure.
- Added strict Pydantic response contract for `critic_preview`, plus `critic_invoked` and `critic_llm_invoked` to separate stage execution from LLM router invocation.
- Reused existing Coder static artifact validation and committed Critic calibration config threshold `0.6`.
- Low-confidence/fallback states remain preview-only and do not trigger 4.B.3 escalation.
- Post-review hardened completion acceptance so validated Critic output is only produced from deterministic `critic_validation` evidence or strict safe JSON.
- Closure validation is green and 4.B.1 is ready for commit/push/PR.
- GitHub PR #99 created for 4.B.1.

### File List

- `apps/chat-service/src/chat_service/critic.py`
- `apps/chat-service/src/chat_service/main.py`
- `apps/chat-service/src/chat_service/schemas.py`
- `apps/chat-service/tests/test_critic.py`
- `apps/chat-service/tests/test_internal_beta.py`
- `_bmad-output/stories/4-b-1-critic-validate-code.md`
- `_bmad-output/stories/sprint-status.yaml`

### Change Log

- Created initial 4.B.1 story draft for adversarial review.
- Applied Round 1 data consistency review fixes.
- Applied Round 2 function/dependency consistency review fixes.
- Applied Round 3 drift/boundary/closure review fixes; story ready for development.
- Added inline Critic preview contract, implementation, Chat wiring, and tests.
- Post-review hardened Critic completion validation and moved sprint/story status to code-review.
