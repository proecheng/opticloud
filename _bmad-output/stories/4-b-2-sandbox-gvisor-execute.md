# Story 4.B.2: Sandbox gVisor 隔离执行 (N11，调 Story M3.1)

Status: done

owner: Chat Platform / Sandbox / AI Safety

## Story

作为 Chat Platform 与 Sandbox 负责人，
我希望 internal beta Chat 在 Coder 生成代码且 Critic 静态验证通过后，通过既有 `apps/sandbox-runner` P58/P62 本地契约执行一次受控 Sandbox preview，
以便在进入用户确认、低置信升级、公开 Chat、SSE 日志或 Solver 之前，先证明代码执行路径只通过 sandbox-runner 边界，并返回可审计的 stdout/stderr/exit_code/result-file 元数据，而不在 chat-service 内直接 spawn 容器或实现真实 gVisor/K8s runtime。

## Acceptance Criteria

1. Chat internal beta response 增加 `sandbox_preview`，并保持 4.A/4.B.1 既有边界。
   - 当前唯一 Chat 业务端点仍是 `POST /v1/chat/internal-beta/messages`；不得新增公开 `/v1/chat`、`/v1/chat/stream`、Sandbox public API、SSE、conversation persistence、Console UI、DB/Redis/outbox/billing/cost telemetry、Solver 或 AIGC filter runtime。
   - internal beta 授权失败或禁用时必须继续在 body validation 前返回 sparse 404，不泄漏 `sandbox_preview`、schema、error code、AIGC 或 sandbox 信息。
   - 成功响应必须包含 `sandbox_preview` 和 `sandbox_invoked`，同时继续保持 `public_access=false`、`provider_request_sent=false`、`solver_invoked=false`、`aigc_gate.public_surface=hidden`。
   - `sandbox_invoked` 仅表示 sandbox-runner 合同执行器或合同 policy stage 被调用并产出 preview；当 gate 未满足时必须为 `false`。
   - 顶层 `llm_invoked` 不得因 Sandbox 增加而改变语义；Sandbox 不能调用 LLM router、provider SDK、Solver、网络、DB、Redis 或队列。
   - 响应不得新增或泄漏 `provider`、`raw_response`、`raw_response_redacted`、`provider_request`、`provider_response`、`sandbox_result`、`execution_log`、`human_review_queue`、`aigc_filter`、真实用户原文或完整 generated code。

2. Sandbox 只在 Coder 与 Critic 双 gate 通过后执行。
   - 仅当 `coder_preview.status=="generated"`、`coder_preview.artifact` 非空、`critic_preview.status=="validated"` 且三项 Critic checks 全部 `passed=true` 时，才构造 `SandboxExecutionRequest` 并调用 sandbox-runner 合同。
   - 当 Coder 为 `needs_clarification`、`skipped`、`artifact=None`，Critic 为 `needs_clarification`、`skipped`、低置信但未 validated，或 task_type 为 `unknown` 时，Sandbox 返回 `status="skipped"` preview，且 `sandbox_invoked=false`。
   - Sandbox 调用必须发生在 Critic 之后、Language preview 之前或之后均可，但不得影响 Critic、Language、AIGC hidden 或 provider_request_sent=false 语义。
   - Sandbox 不触发 4.B.3 human escalation；即使 Sandbox failed 或 policy-blocked，也只能在 preview 中呈现内部错误摘要，不创建 queue、notification、ticket、UI label 或用户可见红黄绿分级。

3. `sandbox_preview` 数据契约可由 Pydantic 严格校验。
   - `SandboxPreview` 字段至少包含：`status`、`source`、`task_type`、`stdout_excerpt`、`stderr_excerpt`、`exit_code`、`result_files`、`error_code`、`limits`、`validation_errors`、`contract_version`。
   - `status` 只能为 `succeeded | failed | policy_blocked | skipped`；`source` 只能为 `sandbox_runner_local_contract_internal_beta` 或 `heuristic_sandbox_internal_beta`。
   - `stdout_excerpt`、`stderr_excerpt` 必须 bounded 且不能包含原始用户消息、完整 generated code、provider payload、secret-like text、traceback 或绝对/宿主路径。
   - `result_files` 只能暴露相对 path、size_bytes、sha256，不暴露文件内容；列表长度和字段长度必须 bounded。
   - `limits` 必须暴露并锁定 M3.1/PRD N11 合同限制：`cpu_vcpu=1`、`memory_mb=1024`、`soft_timeout_seconds=30`、`hard_timeout_seconds=90`、`network_disabled=true`、`read_only_filesystem=true`、`result_file_budget_bytes=104857600`。
   - `validation_errors` 必须 bounded，使用与 Coder/Formulator/Critic 一致的 `field_path`、`message`、`remediation_hint_key` 结构。

4. Sandbox 复用 M3.1 sandbox-runner P58/P62 合同，不重复造轮子。
   - 必须复用 `apps/sandbox-runner/src/sandbox_runner/schemas.py` 的 `SandboxExecutionRequest`、`SandboxLimits` 和 `SandboxExecutionResponse` 契约语义。
   - 必须复用 `validate_request_policy(...)` 与 `execute_local_contract(...)`，或通过一个 thin adapter 调用同等本地合同；不得在 chat-service 中重写 network/self-loop/path/result-budget policy。
   - policy block 必须映射为稳定 `sandbox_preview.status="policy_blocked"` 与 `error_code`，并保持 `sandbox_invoked=true` 以说明 sandbox boundary 被触达但执行器未越权运行。
   - 成功与失败必须映射 stdout/stderr/exit_code/result-file 元数据；exit code 非 0 映射 `status="failed"`，exit code 0 映射 `status="succeeded"`。
   - 本 story 只集成 M3.1 的 deterministic local contract；不得在 chat-service 实现真实 gVisor/K8s pod、RuntimeClass、NetworkPolicy、seccomp、AppArmor、capability drop、warm pool、Docker/runsc 或 K8s API 调用。
   - M3.7 已负责静态安全审计与 hardening manifest；本 story 不重复创建 `tests/sandbox/security/`、audit plan、AppArmor profile 或 K8s hardening manifest。

5. Tests 必须先红后绿，覆盖 Sandbox 边界和漂移场景。
   - 新增 `apps/chat-service/tests/test_sandbox.py` 覆盖：validated Coder/Critic 才调用、Coder 非 generated 不调用、Critic 非 validated 不调用、policy block 映射、exit code failure 映射、result file metadata 映射、stdout/stderr bounded sanitization、limits contract。
   - 扩展 `apps/chat-service/tests/test_internal_beta.py` 覆盖 successful internal beta response 包含 `sandbox_preview`，同时确认 provider/solver/AIGC/queue/raw fields 不存在。
   - 测试必须断言 Sandbox 不触发 4.B.3 escalation 字段或队列副作用。
   - 保留 unauthorized invalid body 先 404 的回归测试，不因新增 `sandbox_preview` 触发 request validation 或响应泄漏。
   - 测试不得需要 live LLM provider、外部网络、真实 gVisor、Docker、K8s、Solver、DB、Redis、AIGC 备案、Grafana 或 GitHub token。

6. Workflow tracking 和闭环清晰。
   - 本 story 记录三轮 pre-implementation story review，并在每轮后应用修正后才能进入 `ready-for-dev`。
   - dev-story 开始时将 sprint status 置为 `in-progress`；实现完成且测试通过后置为 `code-review`。
   - post-implementation code review 必须覆盖边界问题、漂移问题、数据一致性、依赖一致性、是否闭环、policy-block 映射、sandbox-runner import 边界、fallback 语义和测试证据。
   - code review 修正与完整验证通过后，story 与 sprint status 才能置为 `done`，随后 commit、push 并创建/同步 GitHub PR。

## Tasks / Subtasks

- [x] Task 1: 建立 Sandbox preview 数据契约与 limits 暴露。 (AC: 3)
  - [x] 在 `apps/chat-service/src/chat_service/schemas.py` 增加 Sandbox preview/result-file/limits/error schema，并将 `sandbox_invoked` 改为成功响应中的动态布尔字段。
  - [x] 锁定字段长度、枚举、extra forbid、limits 默认值和 result_files 元数据 contract。
  - [x] 确保 `provider_request_sent`、`solver_invoked` 仍为 `Literal[False]`。
- [x] Task 2: 实现 Sandbox local contract adapter。 (AC: 2, 4)
  - [x] 新增 `apps/chat-service/src/chat_service/sandbox.py`。
  - [x] 在 gate 未满足时返回 skipped preview，且 `sandbox_invoked=false`。
  - [x] 在 gate 满足时构造 `SandboxExecutionRequest`，调用 `validate_request_policy(...)` 和 `execute_local_contract(...)`。
  - [x] 将 `SandboxPolicyError` 映射为 `policy_blocked` preview，并保留 stable error_code。
  - [x] 对 stdout/stderr 做 bounded excerpt 与安全清洗，不暴露完整 generated code、raw prompt、secret 或 traceback。
- [x] Task 3: Wire Chat internal beta response。 (AC: 1, 2)
  - [x] 在 `apps/chat-service/src/chat_service/main.py` Critic 之后接入 Sandbox preview。
  - [x] 保持 gate-before-body-validation、AIGC hidden、provider_request_sent=false、solver=false、无 public/SSE/UI。
  - [x] 确认 `llm_invoked` 不纳入 sandbox 阶段。
- [x] Task 4: RED/GREEN tests。 (AC: 1, 2, 3, 4, 5)
  - [x] 先写失败测试并确认新增 Sandbox contract/internal beta expectation 为 RED。
  - [x] 实现最小代码让测试转绿。
  - [x] 加 negative tests 覆盖 policy block、non-zero exit、gate skipped、sanitization、limits contract 和 no escalation。
- [x] Task 5: 验证、审查与关闭。 (AC: 6)
  - [x] 跑 focused 与 full validation。
  - [x] 执行 post-implementation code review 并修复 findings。
  - [x] 更新 Dev Agent Record、File List、Change Log 和 sprint-status。
  - [x] commit、push、创建或同步 GitHub PR。

### Review Findings

- [x] [Review][Patch] Sanitized stdout/stderr excerpts could exceed the 512-character schema bound after redaction expansion. Fixed by truncating again after redaction and adding `test_sandbox_sanitized_excerpts_remain_bounded_after_redaction`.
- [x] [Review][Patch] Sandbox response contract did not reject skipped or policy-blocked previews carrying execution outputs. Fixed with stricter `SandboxPreview` model validation, result path empty-string rejection, `ChatInternalBetaMessageResponse` sandbox flag consistency validation, and negative contract tests.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:409` 定义 Epic 4.B 目标：Critic 验证生成代码、低置信升级、Sandbox 隔离执行、用户可见 confidence/reasoning。
- `_bmad-output/planning/epics.md:1544` 定义 Story 4.B.2：Sandbox gVisor 隔离执行 (N11，调 Story M3.1)。
- `_bmad-output/planning/epics.md:1546` 的源 AC：Given M3.1 sandbox-runner + AIGC filter / When 执行 Coder 代码 / Then 1 vCPU / 1 GB / 禁外网 / 只读 FS / <=30s 软超时。
- `_bmad-output/planning/prd.md:1496` 将 FR N11 定义为系统 can execute code in isolated sandbox。
- `_bmad-output/planning/prd.md:1610` 将 N11 配套限制定义为 1 vCPU、1 GB、禁外网、只读 FS、30s soft timeout、90s hard kill。
- `_bmad-output/planning/architecture.md:1693` 定义 P58 Sandbox I/O Pattern：stdin、stdout、exit_code、emptyDir result files。
- `_bmad-output/planning/architecture.md:1744` 规定仅 `sandbox-runner` 可调 gVisor，其他服务禁止直接 spawn 容器。
- `_bmad-output/stories/m3-1-sandbox-io-pattern.md` 已实现 deterministic local P58/P62 contract，并明确真实 gVisor/K8s runtime enforcement 下游处理。
- `_bmad-output/stories/m3-7-sandbox-security-audit.md` 已实现静态 sandbox security audit/hardening contract；4.B.2 不重复该范围。
- `_bmad-output/stories/4-b-1-critic-validate-code.md` 已提供 `critic_preview`、`critic_invoked`、`critic_llm_invoked`，但仍保持 `sandbox_invoked=false`。

### Current Repository Reality

- `apps/chat-service/src/chat_service/main.py` 当前只有 `POST /v1/chat/internal-beta/messages` 和 `GET /health`。
- Chat internal beta 当前链路是 Router -> Formulator -> Coder -> Critic -> Language preview。
- Gate-before-body-validation 是硬边界：disabled/unauthorized internal beta 请求必须在 body/schema validation 前返回 sparse 404。
- `apps/chat-service/src/chat_service/schemas.py` 已有 Router/Formulator/Coder/Critic/Language preview schema 与 response flags。
- `apps/chat-service/src/chat_service/coder.py` 已有 `validate_code_artifact(...)`，拒绝 unsafe imports/calls、markdown fences、raw/provider/secret-like text、dangerous runtime access。
- `apps/chat-service/src/chat_service/critic.py` 已有 Critic static readiness preview；只有 `status="validated"` 与三项 checks 全 pass 才允许进入 Sandbox。
- `apps/sandbox-runner/src/sandbox_runner/schemas.py` 定义 `SandboxExecutionRequest`、`SandboxExecutionResponse`、`SandboxLimits` 与 stable `SandboxErrorCode`。
- `apps/sandbox-runner/src/sandbox_runner/policy.py` 定义 P62 LLM self-loop、network-disabled、unsafe path 和 result budget policy。
- `apps/sandbox-runner/src/sandbox_runner/executor.py` 定义 deterministic local contract executor，支持 `stdout:`、`stderr:`、`exit:`、`result:` 指令。
- `apps/sandbox-runner/src/sandbox_runner/main.py` 仅是 FastAPI wrapper；chat-service tests 可直接调用 modules，避免引入 HTTP/network。

### Previous Story Intelligence

- 4.A.1 建立 internal beta fail-closed、<=5 trusted users、founder/legal signoff 和 sparse 404 行为。
- 4.A.2 建立 M3.8 LLM router 注入式 wrapper 与 offline deterministic 测试路径。
- 4.A.3/4.A.4 建立 Formulator/Coder 安全 preview：不调用 Solver/Sandbox，不暴露 provider raw payload。
- 4.A.5 增加 Language preview 并保持 `provider_request_sent=false`、无 frontend、无 public Chat、无 SSE、无 AIGC filter。
- 4.A.6 强化 G6 边界：internal beta JSON preview 不是 staging SSE hard-gate evidence，不能引入 false-pass evidence。
- 4.B.1 增加 Critic 静态执行就绪验证，并明确不执行代码、不调用 Sandbox；4.B.2 是第一个 Sandbox contract integration。

### Implementation Guidance

- 优先新增 `chat_service/sandbox.py`，保持和 `coder.py`、`critic.py` 风格一致：dataclass route result、小 helper、fail closed preview、无 runtime side effect。
- `chat_service/sandbox.py` 需要能导入 `sandbox_runner`。测试可通过 pyproject/uv workspace 或 `PYTHONPATH=apps/sandbox-runner/src`；如果直接导入在 chat-service job 中不可用，应使用明确 adapter import 并在验证命令中覆盖。
- 不要通过 HTTP 调用 `sandbox-runner`，避免在 internal beta 单元测试中引入网络或服务启动依赖。
- Sandbox stdin 建议先为空字符串；4.C 上传文件与 follow-up 数据输入不在本 story 范围。
- Sandbox local executor 当前只识别 deterministic directive；Coder 生成的 Python artifact 大概率不会产生业务 stdout。Preview 可返回 succeeded/empty stdout，重点证明 contract path、limits 与 policy gate。
- 如果测试需要 policy block 或 non-zero exit，可直接构造 Coder/Critic preview 调用 `generate_sandbox_preview(...)`，不要让 Coder 生成 unsafe artifact 通过 Pydantic/Critic gate。
- response 中只暴露 bounded excerpts 和 result-file metadata，不暴露 result file content 或 full code。

### Boundary Rules

- No public Sandbox API from chat-service。
- No new public Chat route。
- No SSE / `--allow-logs-stream`。
- No real gVisor/K8s/Docker/runsc integration inside chat-service。
- No Solver invocation。
- No AIGC filter invocation。
- No human review queue。
- No confidence label / UI visual bracket。
- No DB/Redis/outbox/billing/cost telemetry writes。
- No frontend/UI/SandboxConsole work。
- No new runtime dependency。
- No raw provider payload、raw user message、full generated code、secret-like text、traceback、host path 或 result file contents in response/log-like fields。

### Story Review Rounds

### Round 1 - Data Consistency Review (2026-05-29)

Findings applied:
- `sandbox_invoked` 原语义可能混淆“gate 通过后执行器运行”和“policy stage 被触达”；story 已规定 gate 未满足为 false，gate 满足后 policy-block 也为 true，因为 sandbox boundary 被调用但 executor 未越权运行。
- `sandbox_preview.result_files` 原本可能泄漏内容；story 已限定只返回 path、size_bytes、sha256，不暴露文件内容。
- `stdout/stderr` 原本可能泄漏完整代码、用户原文或 traceback；story 已改为 bounded excerpt 并增加 sanitizer 要求。
- `limits` 原本未明确 read-only/network flags；story 已要求 response 暴露 `network_disabled=true` 与 `read_only_filesystem=true`，并锁定 M3.1/PRD 数值。

Status: PASS after fixes.

### Round 2 - Function / Dependency Consistency Review (2026-05-29)

Findings applied:
- Story 标题含 gVisor，容易漂移到真实 K8s/runtime；story 已明确 4.B.2 只集成 M3.1 deterministic local contract，真实 runtime 与 M3.7 hardening 不在 chat-service 内实现。
- 依赖边界原本可能促使 chat-service 通过 HTTP 调 sandbox-runner；story 已建议直接复用 module/adapter，避免测试依赖网络或服务启动。
- AIGC filter 在 Epic 源 AC 中出现，但 4.B.5 才负责调用；story 已明确本 story 保持 `aigc_gate.public_surface=hidden` 且不调用 AIGC filter runtime。
- `llm_invoked` 原本可能纳入 sandbox；story 已明确 Sandbox 不改变 LLM/provider 语义。

Status: PASS after fixes.

### Round 3 - Drift / Boundary / Closure Review (2026-05-29)

Findings applied:
- Story 容易漂移到 4.B.3/4.B.4/4.B.6/4.C；AC 与 Boundary Rules 已明确不做 escalation、ConfidenceLabel/UI、SSE logs、public Chat、file upload 或 follow-up。
- M3.7 审计资产可能被重复创建；story 已明确不得创建 `tests/sandbox/security/`、audit plan、AppArmor 或 K8s hardening manifest。
- Closure 原本缺少 post-implementation code review 的具体验收；AC6 已要求 review 覆盖 boundary、drift、data/dependency consistency、policy-block 映射、import 边界、fallback 语义和测试证据。
- 三轮 story review 均已记录 PASS；Status 从 `story-review` 改为 `ready-for-dev`，可进入 dev-story。

Status: PASS after fixes. Story is ready for development.

### Test / Validation Notes

Expected commands:

```bash
$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests/test_sandbox.py -q
$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests/test_internal_beta.py -q
$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests -q
$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/sandbox-runner/tests -q
uv run mypy apps packages
uv tool run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

RED expectation: add Sandbox tests first; they should fail because `chat_service.sandbox` and response `sandbox_preview` do not exist yet.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-29 - Story draft created from Epic 4.B source AC, PRD N11 sandbox limits, architecture P58/P60 sandbox boundary, M3.1 sandbox-runner local contract, M3.7 security audit boundary, current Chat/Coder/Critic implementation, and 4.B.1 learnings.
- 2026-05-29 - Story review round 1 applied data consistency fixes: clarified `sandbox_invoked`, result metadata, stdout/stderr sanitization, and limits contract fields.
- 2026-05-29 - Story review round 2 applied function/dependency fixes: scoped gVisor title to local contract integration, avoided HTTP/network test dependency, kept AIGC runtime out, and kept LLM/provider flags unchanged.
- 2026-05-29 - Story review round 3 applied drift/boundary/closure fixes: blocked 4.B.3/4.B.4/4.B.6/4.C/M3.7 scope creep and made post-implementation review gates explicit.
- 2026-05-29 - Dev-story started after three story review rounds; sprint status moved to in-progress and starting RED Sandbox tests.
- 2026-05-29 - RED confirmed: `uv run pytest apps/chat-service/tests/test_sandbox.py -q` failed because `SandboxPreview` / `chat_service.sandbox` did not exist, and `test_internal_beta.py` failed because response lacked `sandbox_preview`.
- 2026-05-29 - Added Sandbox preview schemas, `chat_service.sandbox` local contract adapter, workspace dependency on `opticloud-sandbox-runner`, Chat internal beta wiring, and CI chat-service PYTHONPATH/path-filter updates.
- 2026-05-29 - GREEN validation passed: `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests/test_sandbox.py -q` (`7 passed`), `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests/test_internal_beta.py -q` (`25 passed`), `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests -q` (`104 passed`), `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/sandbox-runner/tests -q` (`9 passed`), and `uv run mypy apps packages` passed.
- 2026-05-29 - Post-implementation code review found and fixed two contract issues: redaction expansion could exceed bounded stdout/stderr fields, and schema validation did not reject non-executed preview output drift.
- 2026-05-29 - Review-fix validation passed: `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests/test_sandbox.py -q` (`10 passed`), `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests/test_internal_beta.py -q` (`25 passed`), and `uv run mypy apps packages`.
- 2026-05-29 - Full closure validation passed: `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests -q` (`107 passed`), `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/sandbox-runner/tests -q` (`9 passed`), `uv run mypy apps packages`, `uv tool run pre-commit run --all-files --show-diff-on-failure`, `git diff --check`, and focused combined regression (`35 passed`).
- 2026-05-29 - GitHub synchronized: committed, pushed `codex/4-b-2-sandbox-gvisor-execute`, and opened PR #100.
- 2026-05-29 - Story and sprint status moved to done after PR sync.

### Completion Notes

- Implemented 4.B.2 as an internal beta Sandbox preview that only runs after Coder generated an artifact and Critic validated all checks.
- Added strict Pydantic response contract for `sandbox_preview`, including bounded stdout/stderr excerpts, result-file metadata only, stable error codes, and fixed M3.1/PRD N11 limits.
- Reused M3.1 `sandbox_runner` schemas/policy/local executor through a thin chat-service adapter; no HTTP sandbox call, public Chat route, SSE, Solver, AIGC runtime, DB/Redis/outbox/billing, UI, real gVisor/K8s/Docker/runsc, M3.7 security assets, or escalation queue was added.
- Policy blocks now surface as `status="policy_blocked"` with stable `error_code`; gate misses surface as `status="skipped"` with `sandbox_invoked=false`.
- Focused and service-level validation is green; story is ready for post-implementation code review.
- Post-implementation review hardened bounded excerpt handling and response contract invariants so skipped/policy-blocked previews cannot carry execution output drift and `sandbox_invoked` cannot contradict preview status.
- Closure validation is green and 4.B.2 is ready for commit/push/PR.
- GitHub PR #100 created for 4.B.2.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/stories/4-b-2-sandbox-gvisor-execute.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/chat-service/pyproject.toml`
- `apps/chat-service/src/chat_service/main.py`
- `apps/chat-service/src/chat_service/sandbox.py`
- `apps/chat-service/src/chat_service/schemas.py`
- `apps/chat-service/tests/test_internal_beta.py`
- `apps/chat-service/tests/test_sandbox.py`

### Change Log

- 2026-05-29 - Created 4.B.2 story, completed three adversarial story review rounds, and marked ready-for-dev.
- 2026-05-29 - Started implementation and moved story/sprint status to in-progress.
- 2026-05-29 - Added Sandbox preview contract, local sandbox-runner adapter, Chat response wiring, tests, and CI dependency/path updates; moved story/sprint status to code-review.
- 2026-05-29 - Completed post-implementation code review and fixed two contract findings; ready for final validation and GitHub sync.
- 2026-05-29 - Final validation passed; ready for GitHub sync.
- 2026-05-29 - GitHub PR #100 created and story/sprint status moved to done.
