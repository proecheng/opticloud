# Story 4.C.4: What-if follow-up 进入 Chat internal beta preview/diff

Status: done

owner: Chat Platform / Chat UX Workflow / AIGC Safety

## Story

作为 internal beta Chat 用户和 Chat Platform owner，
我希望用户在已有模型预览或解的 bounded context 上提出 what-if 问题，
以便 Chat 可以把安全的上一轮模型上下文与本轮问题一起重新进入 Coder preview pipeline，并返回可比较的 bounded diff，同时不开放 public Chat、conversation persistence、真实 Solver submission 或 Billing side effects。

## Acceptance Criteria

1. What-if request contract 是 bounded、显式、可测试的。
   - `POST /v1/chat/internal-beta/messages` 和 `POST /v1/chat/internal-beta/messages/stream` JSON body 新增 optional `what_if_context`；字段可省略，默认 `null`。
   - `what_if_context` 代表客户端提交的上一轮 bounded model preview context；本 story 不读取服务端 conversation history、DB、Redis、outbox 或 browser storage。
   - 每个请求最多接受一个 what-if context；不得接受数组、conversation transcript、raw user messages、raw solver result、raw code、raw file rows、provider payload、prompt、sandbox output 或 host path。
   - Contract source 必须为 `chat_model_preview_context_v1`。
   - Required bounded fields：`base_message_id`、`base_model_preview_id`、`task_type`、`variables`、`objective`、`constraints`、`sandbox_status`、`summary`。
   - Optional bounded `base_solution_preview` 可表达源 AC 的“历史含解”，字段仅允许 `status in {"solved","previewed","unknown"}`、`objective_value`、`objective_unit`、`summary`；不得包含 raw solver response、route rows、assignment table、full time series、optimization/prediction id、cost/billing id 或 result file path。
   - Caps：`base_message_id` 格式 `msg_[0-9a-f]{24}`；`base_model_preview_id` 格式 `mpv_[0-9a-f]{16}`；`variables` 最多 40 keys；`constraints` 最多 40 keys；`objective` 最多 20 keys；嵌套 dict/list 最大深度 4、单层最多 40 items；字符串值最多 120 chars；`summary` 最多 360 chars；`base_solution_preview.summary` 最多 240 chars；`objective_value` 只能是有限数值或 `null`。
   - 任何 key/value 命中 secret/internal no-leak pattern 时必须 fail closed 为 422；授权失败仍必须在 body validation 前 sparse 404。

2. What-if context 进入 Chat internal beta 共用 pipeline，但只产生预览级 re-solve。
   - Backend 必须从 sanitized `what_if_context` 构造 safe what-if prompt summary，并与用户本轮 `message`、已有 `file_contexts` summary 一起进入同一条 Router -> Formulator -> Coder -> Critic -> HumanReview -> ConfidenceDisplay -> Sandbox -> ModelPreview -> Language pipeline。
   - Sanitized context snapshot 必须是 digest、prompt summary、diff preview 和 SSE done preview 的唯一来源；不得在 route、schema、helper、streaming 四处分别清洗后产生漂移。
   - 源 AC 中的 “re-solve” 在本 story 中解释为“在 what-if-adjusted bounded context 上重跑 internal beta Coder/Sandbox/ModelPreview preview pipeline，并返回相对上一轮 bounded context/solution preview 的差异”；不得提交 solver-orchestrator，不得创建 optimization/prediction job，不得扣费或 reserve/finalize credits。
   - 同一 tenant/user/client_request_id/message/file_contexts 但 `what_if_context` 不同时，`message_id` 必须稳定地区分；无 context 时保持现有 no-what-if 行为。
   - `what_if_context` canonical digest 必须基于 sanitized snapshot 的 canonical JSON：`json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"))` 后 SHA-256；dict key order 变化不得改变 digest，value/summary/base_solution_preview 变化必须改变 digest。
   - JSON route 和 stream route 必须复用 `_validate_internal_beta_request(...)` 与 `_build_internal_beta_response(...)`，不得复制业务 pipeline。
   - 顶层 side-effect flags 保持：`provider_request_sent=false`、`solver_invoked=false`；`sandbox_invoked` 只反映现有 sandbox preview helper，不因 what-if 改成真实求解。

3. Response 返回 bounded `what_if_preview`，无 context 时显式为 `null`。
   - `ChatInternalBetaMessageResponse` 新增 optional `what_if_preview`；无 `what_if_context` 时必须为 `null`，保持向后兼容且便于客户端分支。
   - 有 `what_if_context` 时字段固定为：
     - `source="chat_what_if_preview_internal_beta"`
     - `base_message_id`
     - `base_model_preview_id`
     - `status in {"previewed","needs_clarification","blocked"}`
     - `task_type`
     - `change_summary`
     - `changed_fields`
     - `diff`
   - `changed_fields` 最多 12 个 dotted paths；`diff` 最多 12 items，每项只包含 `field_path`、`before`、`after`、`change_type`。
   - `before`/`after` 必须是 scalar/list/dict 的 bounded preview，不得包含 full generated code、raw solver result、raw file values、sandbox stdout/stderr、provider payload、prompt、traceback、secret-like text、host path、charge/optimization/prediction id 或 callback URL。
   - `change_summary` 必须由 sanitized context 和当前 message 派生；最多 240 chars，不得回显完整 raw message。
   - Diff field paths 只能位于 `variables.*`、`objective.*`、`constraints.*` 或 `base_solution_preview.*`；path segments 必须是 safe terms，禁止 `/`、`\`、`:`、`..`、控制字符和 secret-like text。
   - 当当前 pipeline 没有产生可比较的 model fields 时，helper 可基于当前 message 中安全、有限的 what-if delta（例如 `+1`、`increase by 1`、`车辆数`/`vehicles`）生成 preview diff；无法安全解析时 status 必须是 `needs_clarification`，不能伪造数值结果。

4. SSE 与 JSON 行为保持一致。
   - Stream route 接受同样的 `what_if_context` body，并在授权通过后、开始 SSE 前完成 validation。
   - 同一 tenant/user/client_request_id/message/file_contexts/what_if_context 下，stream route 的 `message_id`、`locale`、`model_preview_id/status`、`aigc_gate`、`aigc_watermark_trace_id`、`file_context_preview` 和 `what_if_preview` 必须与 JSON route 一致。
   - SSE `done` event 可以包含 `what_if_preview`，但只能包含 bounded preview；不得新增 raw what-if event 或完整 diff stream。
   - 既有 `Last-Event-ID` resume、invalid cursor bounded error、chunk <=100 token-unit、AIGC/no-leak 和 recursive event-data sanitizer 不得回退。

5. 安全、AIGC、边界和依赖 fail closed。
   - 未授权、internal beta disabled、signoff 不满足或 user/tenant/token 不匹配时，必须仍在 body validation 前返回 sparse `404 {"detail":"Not found"}`，不得泄漏 `what_if_context` schema、AIGC gate、watermark、stream event、ModelPreview 或 WhatIfPreview 信息。
   - 授权通过后，非法 `what_if_context` 返回 sanitized 422 JSON；不得回显 `detail.input`、raw message、unsafe key/value 或 context payload。
   - 不新增 public `/v1/chat`、public `/v1/chat/stream`、conversation API、ChatInterface UI、api-gateway proxy、WebSocket、DB/Redis/outbox persistence、notification、Solver/Prediction submission、Billing/Credits charge、AIGC filing mutation、live provider network call 或 sandbox stdout/stderr stream。
   - 不新增 provider SDK、diff library、state machine、database migration 或 frontend dependency；使用标准库、Pydantic 和现有 helper。

6. Tests 必须先红后绿，覆盖 contract、安全、一致性和边界。
   - 新增 focused chat-service tests（建议 `apps/chat-service/tests/test_what_if_context.py`）先断言 `what_if_context` 被拒绝或 `what_if_preview` 缺失为 RED。
   - 覆盖 authorized JSON route with valid `what_if_context` returns bounded `what_if_preview` and distinct stable `message_id`。
   - 覆盖 no-context JSON route returns `what_if_preview: null`。
   - 覆盖 stream route matches JSON `what_if_preview`、`message_id`、`model_preview_id/status` 和 existing file_context_preview 行为。
   - 覆盖 invalid/unsafe context 422 且 response 不包含 `input`、secret-like value、host path、prompt、provider/raw、traceback。
   - 覆盖 unauthorized invalid context 404 before validation。
   - 覆盖 digest stability：相同 context 不同 key order 得到同一 `message_id`；变量/约束/summary 改变时 `message_id` 改变。
   - 覆盖 diff helper：changed variables/objective/constraints 产生 bounded changed_fields/diff；无变化或无法解析时 status `needs_clarification`。
   - 保留 existing `test_internal_beta.py`、`test_file_context.py`、`test_sse_streaming.py`、`test_model_preview.py`、`test_aigc_filter_invoke.py` 回归。
   - Tests 不得需要 live LLM provider、外部网络、真实 DB/Redis/outbox、Solver、Billing、K8s、api-gateway、browser/EventSource、AIGC filing 或 GitHub token。

7. Workflow tracking 和闭环清晰。
   - 本 story 必须记录三轮 pre-implementation adversarial review，并在每轮后应用修正后才能进入 implementation。
   - dev-story 开始时将 sprint status 置为 `in-progress`；实现完成且测试通过后置为 `code-review`。
   - post-implementation code review 必须覆盖边界问题、漂移问题、数据一致性、依赖一致性、是否闭环、what-if context privacy、diff boundedness、JSON/SSE consistency、AIGC/no-leak、side-effect flags 和测试证据。
   - code review 修正与完整验证通过后，story 与 sprint status 才能置为 `done`，随后 commit、push、创建 PR、等待 CI、merge/sync GitHub。

## Tasks / Subtasks

- [x] Task 1: 建立 Chat what-if context schema/helper contract。 (AC: 1, 3, 5)
  - [x] 在 `apps/chat-service/src/chat_service/schemas.py` 增加 `ChatWhatIfContext` / `ChatWhatIfPreview` schema，并把 `what_if_context` 加入 `ChatInternalBetaMessageRequest`。
  - [x] 在 `ChatInternalBetaMessageResponse` 增加 `what_if_preview: ChatWhatIfPreview | None = None`；现有 no-context response 必须显式为 `null`。
  - [x] 新增 `apps/chat-service/src/chat_service/what_if_context.py`，负责 sanitize、canonical digest、safe prompt summary、bounded diff/preview 和 no-leak guard。
  - [x] 更新所有 strict response assertions 和直接构造 `ChatInternalBetaMessageResponse` 的 fixtures，确保新增 `what_if_preview` 默认 `None` 不破坏既有测试。
  - [x] 确保非法 ids、过大 object、过深 nesting、secret-like metadata、raw/prompt/provider/code/sandbox/host-path 文本 fail closed。
- [x] Task 2: 将 what-if context 接入 Chat JSON/SSE 共用 pipeline。 (AC: 2, 4, 5)
  - [x] 修改 `_build_internal_beta_response(...)`，用 safe what-if summary 参与 Router/Formulator/Coder/Language 输入。
  - [x] `_message_id(...)` 纳入 what-if canonical digest；无 context 时保持现有 deterministic id。
  - [x] JSON response 和 SSE `done` 暴露同一个 bounded `what_if_preview`。
  - [x] `build_stream_events(...)` 新增 `what_if_preview` 参数必须有 default `None`，避免现有 helper tests/调用方全部硬失败。
  - [x] 保持 public routes absent，保持 provider/solver/billing/db side-effect flags 不变。
- [x] Task 3: RED/GREEN tests。 (AC: 1-6)
  - [x] 先写 focused RED tests：`what_if_context` schema/preview/digest/SSE done 尚未支持。
  - [x] 实现最小代码转 GREEN。
  - [x] 覆盖 JSON route、stream route、invalid contexts、unauthorized fail-closed、no-leak、message_id digest 区分、diff boundedness，以及既有 no-context response 仍返回 `what_if_preview: null`。
- [ ] Task 4: 验证、审查与关闭。 (AC: 7)
  - [x] 跑 focused 与 full chat-service validation。
  - [x] 执行 post-implementation code review 并修复 findings。
  - [x] 更新 Dev Agent Record、File List、Change Log 和 sprint-status。
  - [x] commit、push、创建 PR、等待 CI、merge/sync GitHub。

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:420` Epic 4.C 目标包括 preview+confirm、SSE、上传 CSV/Excel/JSON 和 what-if follow-up。
- `_bmad-output/planning/epics.md:1585` 定义 Story 4.C.4：What-if follow-up (N10)。
- `_bmad-output/planning/epics.md:1587` 源 AC：Given Chat 历史含解 / When 用户问 “如果车辆数 +1?” / Then Chat 调 Coder + re-solve + 返回 diff。
- `_bmad-output/planning/prd.md:1495` 定义 FR N10：用户 can perform "what-if" follow-ups。
- 当前 repo 没有 conversation persistence、public Chat API、完整 ChatInterface、真实 Chat-to-Solver submission 或 Billing coupling；本 story 必须用客户端提交的 bounded previous model context 表达“Chat 历史含解”。

### Current Repository Reality

- `apps/chat-service/src/chat_service/main.py` 当前有受保护 JSON route `POST /v1/chat/internal-beta/messages` 和 SSE route `POST /v1/chat/internal-beta/messages/stream`。
- JSON/SSE 已共用 `_validate_internal_beta_request(...)` 与 `_build_internal_beta_response(...)`。
- `_validate_internal_beta_request(...)` 先执行 internal beta auth gate，再做 Pydantic body validation；这是 unauthorized-before-validation 的硬边界。
- `apps/chat-service/src/chat_service/schemas.py` 中 `ChatInternalBetaMessageRequest` 当前字段为 `message`、`locale`、`client_request_id`、`file_contexts`。
- `ChatInternalBetaMessageResponse` 当前包括 Router/Formulator/Coder/Critic/Sandbox/HumanReview/ConfidenceDisplay/ModelPreview/Language、`file_context_preview` 和 side-effect flags。
- `apps/chat-service/src/chat_service/file_context.py` 已建立 bounded client-supplied context 的 sanitize/digest/prompt-summary/preview 模式；what-if helper 应复用同类结构，不把逻辑塞进 route。
- `apps/chat-service/src/chat_service/streaming.py` 已支持 deterministic SSE events、`Last-Event-ID`、recursive no-leak sanitizer 和 `done.file_context_preview`。
- 现有 `apps/chat-service/tests/test_internal_beta.py` 对 response shape 有严格断言；新增 response 字段后必须同步 no-context `what_if_preview: null` 预期。
- 现有 `apps/chat-service/tests/test_sse_streaming.py` 直接调用 `build_stream_events(...)`；新增参数必须保持可选默认值。

### Previous Story Intelligence

- 4.C.2 建立 SSE route 后的核心经验：JSON/SSE 必须复用同一 pipeline builder，stream 只返回 bounded preview，不返回完整 code artifact 或 raw execution data。
- 4.C.2 的 no-leak 经验：stream data 不得包含 raw user message、message excerpt、provider payload、prompt、full generated code、sandbox output、traceback、host path、charge/optimization/prediction id。
- 4.C.3 建立 file context 的经验：客户端提交的 bounded context 是当前可接受替代 persistence 的方式；prompt summary、response preview 和 digest 必须来自同一个 sanitized pass。
- 4.C.3 的 post-review 修正：Pydantic 422 不能回显 `detail.input`；SSE sanitizer 必须递归处理 list/dict；digest sorting 不能依赖不完整 sort key。

### Implementation Guidance

- 建议新增 `apps/chat-service/src/chat_service/what_if_context.py`：
  - `sanitize_what_if_context(context: ChatWhatIfContext | None) -> ChatWhatIfContext | None`
  - `canonical_what_if_context_digest(context: ChatWhatIfContext | None) -> str`
  - `build_what_if_prompt_summary(context: ChatWhatIfContext | None) -> str`
  - `build_message_with_what_if_context(message: str, context: ChatWhatIfContext | None) -> str`
  - `build_what_if_preview(context: ChatWhatIfContext | None, message: str, model_preview: ModelPreview) -> ChatWhatIfPreview | None`
- Prompt summary、response preview、canonical digest 必须由同一个 sanitize 结果派生，防止数据漂移。
- `build_message_with_file_context(...)` 已存在；pipeline 中应先附加 file context，再附加 what-if summary，或通过小 helper 明确顺序。两者均不得回显 raw context。
- Diff 可以先比较 sanitized base `variables/objective/constraints` 与当前 `model_preview.variables/objective/constraints`；本 story 不需要真实 solver numerical delta。
- 对 “如果车辆数 +1?” 这类当前 AC 示例，可用 bounded heuristic 把 `vehicles` / `vehicle_count` / `车辆数` / `车数量` 等 safe key 增加 1，只返回 preview diff，不声称求解最优路线变化。
- 如果当前 model preview blocked/needs clarification 或没有可比较字段，`what_if_preview.status` 可为 `needs_clarification`，但仍返回 bounded base ids/change_summary。
- `language_response.heuristic_language_preview(...)` 可新增 `what_if_attached` boolean，让 fallback summary 提到 what-if preview；不得包含 raw question。
- `build_stream_events(...)` 需要新增 optional `what_if_preview` 参数并放入 `done.data`，默认 `None`。

### Boundary Rules

- No public Chat route.
- No full ChatInterface UI or WhatIfPrompt component.
- No server-side conversation history.
- No conversation/session API.
- No DB/Redis/outbox persistence.
- No Solver or Prediction submission.
- No Billing / Credits estimate, reserve or charge.
- No provider network call beyond existing offline LLM router abstraction.
- No live solver re-run, no optimization job id, no prediction id.
- No api-gateway streaming proxy.
- No WebSocket.
- No notification / email / station message.
- No human review queue write beyond existing preview contract.
- No sandbox stdout/stderr logs streaming.
- No AIGC filing status read/update.
- No raw user message, conversation transcript, raw solver result, raw file rows, provider payload, prompt, hidden reasoning, full generated code, sandbox output, secret-like text, traceback, host path, queue payload, charge/optimization/prediction id or callback URL in response or SSE data.

## Story Review Rounds

### Round 1 - Boundary / Conversation / Solver Review (2026-05-30)

Findings applied:
- Source AC says “Chat 历史含解”; initial story represented history only as previous model preview context. Story now adds optional bounded `base_solution_preview` so a prior solved result can be represented without raw solver response, job ids, result files or persistence.
- “re-solve” could still be misread as solver-orchestrator submission. AC now states this means rerunning the internal beta preview pipeline against what-if-adjusted context and returning a bounded diff, not creating jobs or charging credits.
- Boundary text already excludes public Chat, conversation APIs, DB/Redis/outbox, Solver/Prediction submission and Billing; these remain hard exclusions for implementation.

Status: PASS after fixes.

### Round 2 - Data Consistency / Digest / Diff Review (2026-05-30)

Findings applied:
- Initial story allowed digest、prompt summary、preview diff and SSE preview to derive from independently sanitized values. AC now requires one sanitized snapshot as the only source for all downstream artifacts.
- Digest stability was not pinned tightly enough. Story now requires canonical JSON with sorted keys and compact separators, order-independent for dict keys but sensitive to actual value/summary/solution changes.
- Diff path shape was under-specified and could leak arbitrary nested keys or raw solver fields. Story now limits diff paths to `variables.*`、`objective.*`、`constraints.*` and `base_solution_preview.*` with safe path segments.
- Source example “如果车辆数 +1?” needs a bounded interpretation even when the deterministic formulator cannot extract a full new model. Story now permits a narrow vehicle-count heuristic that produces preview diff only and forbids claiming numerical optimal-route changes.

Status: PASS after fixes.

### Round 3 - Dependency / SSE / Test Closure Review (2026-05-30)

Findings applied:
- New response field can break strict internal beta assertions and direct response fixtures outside focused tests. Tasks now require updating all strict response assertions/fixtures and proving no-context `what_if_preview: null`.
- `build_stream_events(...)` is directly imported by tests and may be used by future callers. Tasks now require the new `what_if_preview` parameter to default to `None`.
- Full closure could pass focused tests while breaking existing Chat regressions. Validation notes already include focused tests, related chat tests, full chat-service suite, mypy, pre-commit and diff-check; these are mandatory before marking done.
- Dependency creep risk remains high because diffing could tempt a library or state machine. AC keeps the implementation on standard library/Pydantic/existing helpers only.

Status: PASS after fixes. Story is ready for development.

## Test / Validation Notes

Expected commands:

```powershell
$env:PYTHONPATH='apps/chat-service/src;apps/sandbox-runner/src;packages/shared-py'; uv run pytest apps/chat-service/tests/test_what_if_context.py -q
$env:PYTHONPATH='apps/chat-service/src;apps/sandbox-runner/src;packages/shared-py'; uv run pytest apps/chat-service/tests/test_what_if_context.py apps/chat-service/tests/test_file_context.py apps/chat-service/tests/test_sse_streaming.py apps/chat-service/tests/test_internal_beta.py apps/chat-service/tests/test_model_preview.py apps/chat-service/tests/test_aigc_filter_invoke.py -q
$env:PYTHONPATH='apps/chat-service/src;apps/sandbox-runner/src;packages/shared-py'; uv run pytest apps/chat-service/tests -q
uv run mypy apps packages
uv tool run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

RED expectation: focused tests should fail because `what_if_context`, `what_if_preview`, `chat_service.what_if_context`, what-if digest and SSE `done.what_if_preview` do not exist yet.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-30 - Story created from Epic 4.C.4 source AC, PRD N10, current internal beta JSON/SSE shared-pipeline contract, 4.C.2 SSE no-leak lessons, and 4.C.3 bounded context/digest lessons.
- 2026-05-30 - Story review round 1 applied boundary fixes for bounded `base_solution_preview` and preview-only re-solve semantics.
- 2026-05-30 - Story review round 2 applied data consistency fixes for single sanitized snapshot, canonical digest and bounded diff paths.
- 2026-05-30 - Story review round 3 applied dependency/test closure fixes for strict response assertions, `build_stream_events` default compatibility and full validation gates.
- 2026-05-30 - Dev implementation started after three story review rounds; sprint status moved from ready-for-dev to in-progress and starting RED tests.
- 2026-05-30 - RED confirmed: focused what-if tests failed because `what_if_context` was rejected as extra input and `what_if_preview` was absent.
- 2026-05-30 - GREEN implemented: added what-if schemas/helper, canonical digest, bounded vehicle-count diff preview, shared JSON/SSE pipeline integration, and SSE done preview.
- 2026-05-30 - Validation before code review passed: focused what-if tests 7 passed; related chat tests 67 passed; full chat-service suite 178 passed; `uv run mypy apps packages`; `git diff --check`.
- 2026-05-30 - Post-implementation code review found three patch issues: solver/result forbidden terms were missing from what-if no-leak patterns, numeric values only checked finite-ness without a magnitude cap, and vehicle-count delta had no bounded maximum.
- 2026-05-30 - Review fixes applied: no-leak patterns now block solver/result file/route row terms, what-if numbers are capped to finite absolute values <= 1e12, vehicle deltas above 1000 require clarification, and regressions were added.
- 2026-05-30 - Validation after review fixes passed: focused what-if tests 11 passed; related chat tests 71 passed; full chat-service suite 182 passed; `uv run mypy apps packages`; `git diff --check`.
- 2026-05-30 - Final local validation passed: full chat-service suite 182 passed; `uv run mypy apps packages`; `uv tool run pre-commit run --all-files --show-diff-on-failure`; `git diff --check`.

### Completion Notes List

- Story scopes 4.C.4 to bounded client-submitted what-if context plus preview-level diff through the internal beta Chat pipeline.
- Source AC “Chat 历史含解” is represented as client-submitted `what_if_context`; no server-side conversation persistence is introduced.
- Source AC “re-solve” is interpreted as preview pipeline rerun, not real solver submission or billing.
- Three pre-implementation adversarial review rounds are complete; implementation may start.
- RED/GREEN implementation is complete for bounded what-if JSON/SSE contract and preview diff.
- Full chat-service regression suite and mypy pass before post-implementation code review.
- Post-implementation code review fixes close forbidden solver/result text leakage, extreme numeric payload and extreme delta risks.
- Story implementation, review fixes, final validation, story record update and sprint status update are complete.

### Review Findings

- [x] [Review][Patch] What-if no-leak patterns did not cover story-forbidden solver/result terms such as `solver_result`, `route_rows`, `assignment_table`, `full_time_series`, or `result_file_path` — fixed in schemas/helper patterns with regression coverage.
- [x] [Review][Patch] What-if numeric values were only checked for finite-ness, allowing impractically large integers/floats into digest/prompt/diff — fixed with finite absolute value cap and regression coverage.
- [x] [Review][Patch] Vehicle-count delta parsing accepted unbounded `+N` changes, letting a prompt create huge preview diffs — fixed by requiring clarification for deltas above 1000.

### File List

- `_bmad-output/stories/4-c-4-what-if-followup.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/chat-service/src/chat_service/main.py`
- `apps/chat-service/src/chat_service/schemas.py`
- `apps/chat-service/src/chat_service/streaming.py`
- `apps/chat-service/src/chat_service/what_if_context.py`
- `apps/chat-service/tests/test_what_if_context.py`

### Change Log

- 2026-05-30 - Created 4.C.4 story and moved sprint status from backlog to ready-for-dev.
- 2026-05-30 - Completed three pre-implementation adversarial review rounds and started implementation; story moved to in-progress.
- 2026-05-30 - Implemented what-if context preview contract and moved story/sprint status to code-review.
- 2026-05-30 - Completed post-implementation code review fixes for no-leak term coverage, numeric caps and delta caps.
- 2026-05-30 - Completed final validation and moved story/sprint status to done.
