# Story 4.B.6: Sandbox `--allow-logs-stream` flag (v1.5 future)

Status: done

owner: Chat Platform / Sandbox Runner / SDK Integration

## Story

作为陈架构师类型的 SDK 集成方，
我希望 Sandbox v1.5+ 的 `--allow-logs-stream=true` 能被当前服务合同识别并安全拒绝，
以便未来 M7-M8 实现 stdout/stderr SSE 时已有稳定 feature flag、错误码、handoff ticket 和 no-leak guard，同时当前 v1/internal beta 不误开放 Chat SSE、public stream route 或未审计 sandbox logs。

## Acceptance Criteria

1. `allow_logs_stream` flag 被显式建模但当前阶段 fail closed。
   - `apps/sandbox-runner` 的 `SandboxExecutionRequest` 必须新增 `allow_logs_stream: bool = False`。
   - 当请求设置 `allow_logs_stream=true` 时，sandbox-runner 必须在 executor 运行前拒绝，返回稳定错误码 `logs_stream_deferred`。
   - 拒绝响应不得回显 `code`、`stdin`、stdout/stderr 内容、host path、traceback、secret、token、provider payload 或 queue payload。
   - 默认 `allow_logs_stream=false` 的同步 `/v1/sandbox/execute` 行为必须保持不变。

2. Chat internal beta Sandbox preview 必须保留当前非 streaming contract。
   - `generate_sandbox_preview(..., allow_logs_stream=True)` 必须返回 bounded `SandboxPreview`，`status="policy_blocked"`、`error_code="logs_stream_deferred"`，且不执行 sandbox executor。
   - preview 不得包含 streamed chunks、event id、cursor、SSE URL、full stdout/stderr、raw generated code、request body、host path、traceback 或 secret-like text。
   - 默认 internal beta Chat path 不得设置 `allow_logs_stream=true`，不得改变现有 `sandbox_invoked`、`provider_request_sent`、`solver_invoked`、`aigc_gate`、HumanReview 或 ConfidenceDisplay 语义。

3. 不新增当前公开 streaming surface。
   - 不新增 `/v1/chat/stream`、`/v1/sandbox/stream`、`/v1/sandbox/logs`、SSE `StreamingResponse`、EventSource frontend client、api-gateway streaming proxy、SDK streaming method 或 Console logs UI。
   - `POST /v1/chat/internal-beta/messages` 仍是当前唯一 Chat 业务端点；`POST /v1/chat/stream` 继续 404。
   - sandbox-runner 当前唯一业务端点仍是 `POST /v1/sandbox/execute`；stream/logs route 必须不存在。

4. v1.5 handoff 清晰。
   - 新增 Linear-ready handoff 文档，记录 ticket title、scope、prerequisites、owner、stage=M7-M8/v1.5+、acceptance checklist 和安全边界。
   - handoff 必须说明未来真实实现需要 4.C.2/architecture P28/P58/P60：SSE lifecycle、api-gateway streaming proxy、heartbeat/cursor、AIGC/filter chunk boundary、stdout/stderr redaction 和 operator evidence。
   - handoff 不得声称当前已实现 SSE 或 SDK streaming；不得包含真实 Linear API token、issue id、customer data 或 production evidence。

5. Tests 必须先红后绿，覆盖 feature flag、拒绝语义、边界漂移和 no-leak。
   - 新增 focused tests 先断言当前 schema 不支持 `allow_logs_stream` 或缺少 `logs_stream_deferred` 为 RED。
   - 覆盖 sandbox-runner `allow_logs_stream=true` 返回 422、`error_code=logs_stream_deferred`、`executor_invoked=false`，且不泄漏 code/stdout/stderr。
   - 覆盖默认 `allow_logs_stream=false` 同步执行仍返回 P58 stdout/stderr/result metadata。
   - 覆盖 Chat adapter 的 `allow_logs_stream=True` 映射为 policy-blocked preview 且不执行 stdout directive。
   - 覆盖 stream/logs routes 仍不存在。

6. Workflow tracking 和闭环清晰。
   - story 记录三轮 pre-implementation adversarial review，并在每轮后应用修正后才进入 implementation。
   - 实施后 code review 必须覆盖边界问题、漂移问题、数据一致性、依赖一致性、是否闭环、Sandbox contract、no-leak、future handoff 和测试证据。
   - code review 修正与完整验证通过后，story 与 sprint status 才能置为 `done`，随后 commit、push、创建 PR、CI 全绿后 merge/sync GitHub。

## Tasks / Subtasks

- [x] Task 1: 建立 Sandbox logs stream v1.5 flag contract。 (AC: 1, 4)
  - [x] 在 sandbox-runner schema 中增加 `allow_logs_stream` 默认 false。
  - [x] 增加稳定错误码 `logs_stream_deferred`。
  - [x] 增加 Linear-ready v1.5 handoff 文档。
- [x] Task 2: 实现 fail-closed policy 与 Chat preview 映射。 (AC: 1, 2, 3)
  - [x] `allow_logs_stream=true` 在 executor 前被 policy 拒绝。
  - [x] Chat adapter 支持显式 `allow_logs_stream` 参数，但 internal beta 默认 false。
  - [x] `logs_stream_deferred` 映射为 bounded policy-blocked preview，不包含 execution output。
- [x] Task 3: RED/GREEN tests。 (AC: 1-5)
  - [x] 先写失败测试并确认 RED。
  - [x] 实现最小代码转 GREEN。
  - [x] 覆盖 no-leak、默认同步行为不变、Chat/Sandbox stream routes 不存在。
- [x] Task 4: 验证、审查与关闭。 (AC: 6)
  - [x] 跑 focused 与 full validation。
  - [x] 执行 post-implementation code review 并修复 findings。
  - [x] 更新 Dev Agent Record、File List、Change Log 和 sprint-status。
  - [x] commit、push、创建 PR、等待 CI、merge/sync GitHub。

### Review Findings

- [x] [Review][Patch] `allow_logs_stream` must return stable deferred error before other policy errors [apps/sandbox-runner/src/sandbox_runner/policy.py:39] — fixed by checking `allow_logs_stream` before input path/network/LLM policy checks and adding a precedence no-leak test.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:1561` 定义 Story 4.B.6：Sandbox `--allow-logs-stream` flag。
- `_bmad-output/planning/epics.md:2021` TT5 明确 4.B.6 stage = v1.5+ / M7-M8 + Linear ticket。
- `_bmad-output/planning/architecture.md:1698` P58 定义 stdout 流式输出最终应由 sandbox-runner 抓 pod logs API + SSE 透传给 chat-service。
- `_bmad-output/planning/architecture.md:1707` 说明未来链路是 sandbox-runner SSE -> chat-service SSE -> api-gateway streaming proxy -> web SSE client。
- `_bmad-output/planning/architecture.md:851` P28 定义 SSE lifecycle：heartbeat、断线 cursor、proxy timeout、buffer 策略。
- `_bmad-output/stories/m3-1-sandbox-io-pattern.md` 明确 4.B.6 owns SSE stdout/stderr log streaming，M3.1 只提供同步 captured stdout/stderr。
- `_bmad-output/stories/4-b-2-sandbox-gvisor-execute.md` 明确 4.B.2 不做 SSE / `--allow-logs-stream`，但建立了当前 `sandbox_preview` bounded excerpt contract。

### Current Repository Reality

- `apps/sandbox-runner/src/sandbox_runner/main.py` 当前只有 `POST /v1/sandbox/execute`，没有 stream/logs route。
- `apps/sandbox-runner/src/sandbox_runner/schemas.py` 当前 `SandboxExecutionRequest` 只有 `code`、`stdin`、`input_files`、`limits`，没有 `allow_logs_stream`。
- `apps/sandbox-runner/src/sandbox_runner/policy.py` 当前只拦 network、LLM self-loop、unsafe paths、result budget。
- `apps/sandbox-runner/src/sandbox_runner/executor.py` 是 deterministic local contract executor，识别 `stdout:`、`stderr:`、`exit:`、`result:` directives。
- `apps/chat-service/src/chat_service/sandbox.py` 当前同步调用 local contract executor，并只返回 bounded stdout/stderr excerpts。
- `apps/chat-service/src/chat_service/main.py` 当前 internal beta 默认调用 `generate_sandbox_preview(...)`，不得设置 logs streaming。
- `packages/python-sdk` 当前只有 alpha `list_algorithms()` stub，没有 sandbox execution or streaming method。

### Boundary Rules

- No current SSE implementation.
- No `/v1/chat/stream` route.
- No `/v1/sandbox/stream` or `/v1/sandbox/logs` route.
- No `StreamingResponse`, EventSource, frontend client, api-gateway streaming proxy, SDK streaming method, or Console logs UI.
- No real gVisor/K8s pod logs API integration.
- No DB/Redis/outbox/notification/billing/cost telemetry writes.
- No Solver invocation.
- No AIGC filter policy changes.
- No human-review queue/event changes.
- No full stdout/stderr/code/stdin/request echo, traceback, host path, token, provider payload, queue payload, or result file contents in responses.

## Story Review Rounds

### Round 1 - Boundary / Stage Review (2026-05-29)

Findings applied:
- 原 AC 可被误读为“现在上线 SSE stdout/stderr”。Story 已改为 v1.5+ fail-closed feature flag 与 Linear-ready handoff，不实现 streaming runtime。
- TT5 明确 M7-M8 future；Story 已要求 `logs_stream_deferred` 且 executor 前拒绝。
- 4.C.2 才是 Chat SSE 用户体验；Story 已禁止 `/v1/chat/stream`、`StreamingResponse`、EventSource 和 api-gateway streaming proxy。
- sandbox-runner stream/logs route 容易被误加；Story 已要求当前唯一业务端点仍为 `/v1/sandbox/execute`。

Status: PASS after fixes.

### Round 2 - Data Consistency / No-Leak Review (2026-05-29)

Findings applied:
- 如果 `allow_logs_stream=true` 后再执行 directive，可能泄漏 stdout/stderr；Story 已要求 executor 前拒绝并测试 `executor_invoked=false`。
- 拒绝响应可能回显 request body/code；Story 已要求 no echo and no-leak tests。
- Chat preview 的 policy-blocked stderr_excerpt 可包含安全错误文案，但不得包含 sandbox output；Story 已要求 no stdout directive execution and bounded preview。
- `sandbox_invoked` 语义可能漂移；Story 已沿用 4.B.2：policy boundary 被触达可为 true，但 executor 不运行。

Status: PASS after fixes.

### Round 3 - Dependency / Closure Review (2026-05-29)

Findings applied:
- 当前 Python SDK 没有 sandbox streaming method；Story 已禁止新增 SDK streaming method，仅提交 Linear-ready handoff。
- 真实日志流依赖 P28/P58/P60、api-gateway、K8s pod logs 和 AIGC/filter chunk policy；Story 已将其列入 handoff prerequisites。
- 新错误码需要同步 chat-service schema；Story 已要求 Chat preview 支持 `logs_stream_deferred` 映射。
- Closure 已加入 post-implementation code review 范围：boundary、drift、data/dependency consistency、Sandbox contract、no-leak、future handoff、测试证据。

Status: PASS after fixes. Story is ready for development.

## Test / Validation Notes

Expected commands:

```bash
$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/sandbox-runner/tests/test_logs_stream_deferred.py -q
$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/chat-service/tests/test_sandbox_logs_stream_deferred.py -q
$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/sandbox-runner/tests apps/chat-service/tests -q
uv run mypy apps packages
uv tool run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

RED expectation: focused tests should fail because `SandboxExecutionRequest` lacks `allow_logs_stream`, `SandboxErrorCode` lacks `logs_stream_deferred`, and `generate_sandbox_preview` lacks an `allow_logs_stream` parameter.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-29 - Story created from Epic 4.B.6, TT5 v1.5+ staging note, architecture P28/P58/P60, M3.1 and 4.B.2 sandbox boundaries, and current sandbox-runner/chat-service code.
- 2026-05-29 - Story review round 1 applied boundary/stage fixes: fail-closed current scope, no Chat/Sandbox SSE routes, no StreamingResponse/EventSource/api-gateway work.
- 2026-05-29 - Story review round 2 applied data/no-leak fixes: executor-before-reject blocked, no request/output echo, bounded Chat preview mapping, sandbox_invoked semantics clarified.
- 2026-05-29 - Story review round 3 applied dependency/closure fixes: no SDK streaming method, future prerequisites captured, chat-service error-code mapping required, review gates explicit.
- 2026-05-29 - Dev story implementation started; sprint status moved from backlog to in-progress.
- 2026-05-29 - RED confirmed: focused sandbox-runner test failed because `allow_logs_stream=true` executed instead of rejecting; focused chat-service test failed because `generate_sandbox_preview` lacked `allow_logs_stream`.
- 2026-05-29 - GREEN implemented: sandbox schema/error code, fail-closed policy, chat preview mapping, route absence guards, and v1.5 handoff static contract.
- 2026-05-29 - Post-implementation code review found one patch issue: `allow_logs_stream` was checked after input path validation, allowing a non-stable error code for mixed invalid requests.
- 2026-05-29 - Review fix applied: moved `allow_logs_stream` policy check ahead of other sandbox policy checks and added precedence/no-leak coverage.
- 2026-05-29 - Final validation passed: sandbox-runner tests 14 passed; chat-service tests 141 passed; handoff static tests 2 passed; `uv run mypy apps packages`; `uv tool run pre-commit run --all-files --show-diff-on-failure`; `git diff --check`.

### Completion Notes

- `allow_logs_stream: bool = False` is now explicitly modeled on `SandboxExecutionRequest`.
- `allow_logs_stream=true` fails closed with stable `logs_stream_deferred` before executor invocation and before other policy classifications can leak unstable details.
- Chat sandbox preview accepts an explicit `allow_logs_stream` parameter for test/adapter coverage, while the internal beta route keeps the default false non-streaming contract.
- No Chat/Sandbox streaming route, `StreamingResponse`, EventSource client, api-gateway proxy, SDK streaming method, Console UI, DB/queue/billing/Solver/AIGC policy surface, or real pod logs integration was added.
- v1.5+ handoff is documented with Linear-ready scope, prerequisites, acceptance checklist, and security boundaries without claiming current SSE or SDK streaming implementation.

### File List

- `_bmad-output/stories/4-b-6-sandbox-logs-stream-v1-5.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/sandbox-runner/src/sandbox_runner/schemas.py`
- `apps/sandbox-runner/src/sandbox_runner/policy.py`
- `apps/sandbox-runner/tests/test_logs_stream_deferred.py`
- `apps/chat-service/src/chat_service/schemas.py`
- `apps/chat-service/src/chat_service/sandbox.py`
- `apps/chat-service/tests/test_sandbox_logs_stream_deferred.py`
- `docs/runbooks/sandbox-logs-stream-v1-5-handoff.md`
- `tests/test_sandbox_logs_stream_handoff.py`

### Change Log

- 2026-05-29 - Created 4.B.6 story, completed three adversarial story review rounds, and started implementation.
- 2026-05-29 - Added fail-closed sandbox logs stream flag reservation, chat preview mapping, v1.5 handoff documentation, tests, post-implementation review fix, and final validation evidence.
