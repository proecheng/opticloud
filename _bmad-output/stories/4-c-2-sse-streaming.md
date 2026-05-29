# Story 4.C.2: SSE 流式 <=100 token/chunk

Status: done

owner: Chat Platform / Chat UX Workflow / AIGC Safety

## Story

作为 internal beta Chat 用户和 Chat Platform owner，
我希望 Chat 可以通过稳定的 server-sent event stream 逐步返回用户可见语言结果，
以便在不开放 public Chat、conversation persistence、文件上传、what-if 或完整 ChatInterface 的前提下，先验证 N7 的流式合同、chunk 边界、AIGC 出口屏障和断线续传语义。

## Acceptance Criteria

1. Chat internal beta 新增受保护的 SSE runtime surface。
   - 新增唯一流式业务端点：`POST /v1/chat/internal-beta/messages/stream`。
   - 端点必须复用 `POST /v1/chat/internal-beta/messages` 的 internal beta headers：`X-Internal-Beta-Tenant`、`X-Internal-Beta-User`、`X-Internal-Beta-Token`。
   - 授权失败、internal beta disabled、signoff 不满足或 user/tenant/token 不匹配时，必须在 body validation 前返回 sparse `404 {"detail":"Not found"}`，不得开始 SSE，不得泄漏 schema、AIGC gate、watermark、stream event、provider、Critic、Sandbox、HumanReview 或 ModelPreview 信息。
   - 授权通过后复用现有 `ChatInternalBetaMessageRequest` body validation；bad body 继续返回 422 JSON，不返回 SSE error event。
   - 成功响应必须是 `text/event-stream`，使用 FastAPI `StreamingResponse`，并设置 `Cache-Control: no-cache`、`X-Accel-Buffering: no`、`Connection: keep-alive`。
   - 公开 `/v1/chat`、公开 `/v1/chat/stream`、`/v1/chat/conversations`、`/v1/chat/conversations/{id}/messages` 仍不存在；本 story 不实现 public Chat 或 conversation API。
   - 由于 native browser `EventSource` 不能发送 POST body，本 story 只交付 backend SSE wire contract；4.C.6 ChatInterface / api-gateway 可在已有 message/session contract 之上决定 GET subscription adapter，不在本 story 实现。

2. SSE event contract 稳定且可测试。
   - 每个 SSE event 必须由 UTF-8 文本块组成，并用空行结束；字段只允许 `id:`、`event:`、`retry:`、`data:` 或 heartbeat comment `:heartbeat`。
   - 流开始必须先发送一次 `:heartbeat\n\n`，防止代理和客户端把空首包当成失败。
   - 第一个 event 为 `message_start`，payload 固定包含：`message_id`、`mode="internal_beta"`、`public_access=false`、`locale`、`max_chunk_token_units=100`、`token_count_method="content_unit_approximation"`。
   - 中间 event 为一个或多个 `content_delta`，payload 固定包含：`message_id`、`chunk_index`、`chunk`、`token_units`。
   - 最后 event 为 `done`，payload 固定包含：`message_id`、`done=true`、`content_event_count`、`model_preview_id`、`model_preview_status`、`aigc_watermark_trace_id`、`aigc_gate`。
   - 可选错误 event 仅用于已授权、body valid、stream cursor invalid 等流内错误；格式为 `event: error` + bounded JSON payload，并在发送后关闭。
   - `id` 必须单调递增、确定性、无 PII，格式为 `sse_[0-9a-f]{16}_[0-9]{6}`；不新增 ULID 依赖。未来 production 可在兼容客户端语义下替换为真正 ULID。
   - 每个非 heartbeat event 必须包含 JSON object `data`；不得发送裸字符串、provider raw payload、stack trace 或 Python repr。

3. `content_delta` chunk 必须满足 <=100 token-unit 且 AIGC/no-leak 安全。
   - `content_delta.token_units` 必须为 1..100；chunking 使用 deterministic `content_unit_approximation`，英文按 whitespace/punctuation 近似，CJK 字符按单字近似。
   - chunking 输入只能来自现有 `language_preview.summary` 的安全用户可见文本；不得直接读取 raw user message、message excerpt、prompt、provider completion、raw response 或 hidden reasoning。
   - 零宽 AIGC metadata 不作为 `content_delta.chunk` 流式内容发送，避免被切断；`content_delta` 必须包含可见 AIGC marker，`done.aigc_watermark_trace_id` 必须等于 `language_preview.aigc_watermark.trace_id`。
   - 若 AIGC filter 产生 blocked summary，stream 只能发送 blocked 安全文案，不得发送被拦截原文。
   - `content_delta.chunk` 和所有 SSE `data` 字段不得包含 API key、Bearer token、cookie、authorization、password、provider request/response、raw prompt、raw user message、完整 generated code、sandbox output、traceback、host path、queue payload、charge/optimization/prediction id 或 callback URL。
   - 本 story 不对 provider tokenization 计数作真实承诺；`<=100` 仅约束本服务的 deterministic token-unit approximation。真实 provider token 计数和成本预算属于后续 token-budget/observability story。

4. Stream 与既有 Chat internal beta JSON contract 保持数据一致。
   - Stream route 必须复用同一条 Router -> Formulator -> Coder -> Critic -> HumanReview -> ConfidenceDisplay -> Sandbox -> ModelPreview -> Language pipeline，避免复制业务判断。
   - 同一 tenant/user/client_request_id/message 下，stream route 的 `message_id`、`locale`、`model_preview_id`、`model_preview_status`、`aigc_gate`、`aigc_watermark_trace_id` 必须与 JSON route 结果一致。
   - Stream route 不返回完整 `model_preview.code_artifact`、variables、constraints 或 generated code；只返回 bounded `model_preview_id` 和 `model_preview_status`，完整 preview 仍由 JSON route 合同负责。
   - `provider_request_sent`、`solver_invoked`、`sandbox_invoked`、`critic_invoked` 等顶层语义不得为了 streaming 改变；stream route 不新增 side-effect flags。
   - 不得新增 Solver submission、Billing/Credits estimate or charge、DB/Redis/outbox/conversation persistence、notification、human review queue write、AIGC filing service mutation 或 live provider network call。

5. Cursor resume 和 stream closure fail closed。
   - 端点接受 optional `Last-Event-ID` header；若该 id 属于本次 deterministic event list，则从下一 event 继续发送，已发送过的 event 不重复。
   - 如果 `Last-Event-ID` 正好是最后一个 event，响应可以只发送 heartbeat 后正常结束，不得伪造新内容。
   - 若 `Last-Event-ID` 格式错误或不属于本次 event list，必须返回 SSE `error` event，`error_code="invalid_cursor"`，不得回显 header 原值、raw message 或 internals。
   - Stream generator 必须在可取消点让出控制，避免客户端断开后继续长时间运行；短 deterministic stream 可用 `await anyio.sleep(0)`。
   - 不实现 Redis stream、pub/sub、server-side persisted cursor、multi-tab broadcast、frontend AbortController、重连 UI 或 api-gateway streaming proxy；这些属于 4.C.6 / api-gateway 后续工作。

6. Tests 必须先红后绿，覆盖 runtime、格式、chunk、安全和边界。
   - 新增 focused tests（建议 `apps/chat-service/tests/test_sse_streaming.py`）先断言 stream route 不存在或没有 `text/event-stream` 为 RED。
   - 覆盖 authorized stream：status 200、media type `text/event-stream`、headers no-cache/no-buffer、heartbeat、`message_start`、至少一个 `content_delta`、`done`。
   - 覆盖所有 `content_delta.token_units <= 100`，chunk 非空，event id 单调，event payload 可 JSON parse。
   - 覆盖 JSON route 与 stream route 的 `message_id`、`locale`、`model_preview.preview_id/status`、`aigc_gate`、watermark trace 一致。
   - 覆盖 unauthorized invalid body 仍先 404 且不返回 SSE。
   - 覆盖 public `/v1/chat/stream` 仍 404。
   - 覆盖 `Last-Event-ID` resume：从下一 event 继续；invalid cursor 返回 bounded error event 且不泄漏 header/raw message。
   - 覆盖 no-leak：stream body 不包含 raw user message、message excerpt、provider/raw/prompt、API key、traceback、host path、完整 generated code、charge/optimization/prediction id。
   - 覆盖 pure helper：SSE formatting、token-unit approximation、chunk split、zero-width metadata stripping、event id generation。
   - 测试不得需要 live LLM provider、外部网络、真实 DB/Redis/outbox、Solver、Billing、K8s、api-gateway、browser、EventSource、AIGC filing 或 GitHub token。

7. Workflow tracking 和闭环清晰。
   - 本 story 记录三轮 pre-implementation adversarial review，并在每轮后应用修正后才能进入 implementation。
   - dev-story 开始时将 sprint status 置为 `in-progress`；实现完成且测试通过后置为 `code-review`。
   - post-implementation code review 必须覆盖边界问题、漂移问题、数据一致性、依赖一致性、是否闭环、SSE wire format、chunk limit、cursor resume、AIGC/no-leak、side-effect flags 和测试证据。
   - code review 修正与完整验证通过后，story 与 sprint status 才能置为 `done`，随后 commit、push、创建 PR、等待 CI、merge/sync GitHub。

## Tasks / Subtasks

- [x] Task 1: 建立 SSE stream helper contract。 (AC: 2, 3, 5)
  - [x] 新增 `apps/chat-service/src/chat_service/streaming.py`，包含 SSE event model/helper、formatting、event id、token-unit approximation、chunk split、zero-width metadata stripping、cursor resume。
  - [x] helper 必须是 pure/deterministic，便于单元测试；不得调用 FastAPI route、LLM provider、Solver、Billing、DB/Redis/outbox。
  - [x] 对 event data 做 bounded no-leak guard，发现不安全文本时 fail closed 为 error event 或 safe fallback。
- [x] Task 2: 复用 internal beta pipeline 并新增 stream route。 (AC: 1, 4, 5)
  - [x] 将 `main.py` 中 JSON route 的业务 pipeline 抽出为内部 helper，JSON route 和 stream route 共用，避免数据漂移。
  - [x] 新增 `POST /v1/chat/internal-beta/messages/stream`，复用 internal beta gate-before-body-validation。
  - [x] 返回 `StreamingResponse`，media type `text/event-stream`，设置 no-cache/no-buffer/keep-alive headers。
  - [x] 支持 optional `Last-Event-ID` header。
- [x] Task 3: RED/GREEN tests。 (AC: 1-6)
  - [x] 先写 focused streaming tests 并确认 RED。
  - [x] 实现最小代码转 GREEN。
  - [x] 覆盖 authorized stream、unauthorized fail-closed、public route absence、chunk <=100、cursor resume、invalid cursor、JSON/stream consistency、no-leak 和 helper behavior。
- [x] Task 4: 验证、审查与关闭。 (AC: 7)
  - [x] 跑 focused 与 chat-service/full validation。
  - [x] 执行 post-implementation code review 并修复 findings。
  - [x] 更新 Dev Agent Record、File List、Change Log 和 sprint-status。
  - [ ] commit、push、创建 PR、等待 CI、merge/sync GitHub。

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:1577` 定义 Story 4.C.2：SSE 流式 <=100 token/chunk (N7)。
- `_bmad-output/planning/epics.md:1579` 源 AC：Given Chat 调 LLM / When 流式 / Then chunk size <=100 token + 用户感受流畅。
- `_bmad-output/planning/prd.md:1492` 定义 FR N7：系统 can stream Chat (每 chunk <=100 token) via SSE。
- `_bmad-output/planning/prd.md:1595` 定义 Chat 首 Token 延迟测量来自 SSE 客户端首 token timestamp。
- `_bmad-output/planning/prd.md:1596` 定义 Chat 流式吞吐 >=20 Token/s；M5 末作为 KPI gate，不是本 story 本地单测承诺。
- `_bmad-output/planning/architecture.md:851` P28 定义 SSE lifecycle：heartbeat、event id、error event、Last-Event-ID。
- `_bmad-output/planning/architecture.md:974` P34/C16 定义 user-visible NL stream 必须经过 AIGC Layer 1/Layer 2；当前 repo 的 deterministic `language_preview` 已通过 shared AIGC filter。
- `_bmad-output/planning/architecture.md:1748` 说明 production SSE 反代应通过 api-gateway streaming proxy；本 story 不实现 api-gateway。
- FastAPI 官方文档说明 `StreamingResponse` 接受 async generator 或 iterator 并流式返回 response body；本 story 使用该现有依赖，不新增 SSE 库。[Source: FastAPI Custom Response / StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/)
- MDN 说明 SSE 服务端应使用 `text/event-stream`，event blocks 由空行分隔，字段包括 `event`、`data`、`id`、`retry`，冒号开头的行可作 comment/heartbeat。[Source: MDN Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)

### Current Repository Reality

- `apps/chat-service/src/chat_service/main.py` 当前唯一 Chat 业务端点是 `POST /v1/chat/internal-beta/messages`。
- 当前 JSON route 已串起 Router -> Formulator -> Coder -> Critic -> HumanReview -> ConfidenceDisplay -> Sandbox -> ModelPreview -> Language。
- `apps/chat-service/src/chat_service/language_response.py` 已通过 `apply_aigc_filter_to_summary(...)` 生成 `language_preview.summary` 与 `aigc_watermark`。
- `apps/chat-service/src/chat_service/model_preview.py` 已提供 4.C.1 response-only model preview contract。
- `tools/chat_load/locustfile.py` 已有可复用的 SSE parsing/metric 概念，但该工具属于 staging load harness，不应被 chat-service runtime 依赖。
- `apps/sandbox-runner` 的 logs stream 已在 4.B.6 明确 fail-closed；4.C.2 不改变 sandbox stdout/stderr logs streaming。

### Previous Story Intelligence

- 4.C.1 已建立 `model_preview`，并明确 4.C.2 才能新增 stream route；本 story 是第一个允许 Chat SSE 的 story。
- 4.B.6 已保留 sandbox logs stream future flag，但当前 sandbox logs route 仍不存在；不要把 Chat language SSE 与 sandbox stdout/stderr SSE 混在一起。
- 4.B.5/4.B.7 已锁定 AIGC watermark/filter/redteam 边界；streaming 必须复用现有 language preview 输出，不重复实现 filter rule。
- M3.6a/M3.6b 已建立 SSE load-test helper 和 first-token/throughput definitions；本 story 只实现 runtime surface，不声称 staging G6 hard-gate passed。

### Implementation Guidance

- 建议新增 `chat_service/streaming.py`：
  - `build_stream_events(response: ChatInternalBetaMessageResponse) -> list[ChatStreamEvent]`
  - `format_sse_event(event: ChatStreamEvent) -> str`
  - `iter_sse_payload(events, last_event_id=None) -> AsyncIterator[str]`
  - `_content_token_units(text: str) -> int`
  - `_split_content_chunks(text: str, max_units=100) -> list[str]`
  - `_strip_zero_width_metadata(text: str) -> str`
- `main.py` 建议抽出 `_build_internal_beta_response(...) -> ChatInternalBetaMessageResponse`，JSON route 直接 return，stream route 用同一对象生成 SSE events。
- `content_delta` 不发送 zero-width metadata；done event 发送 `aigc_watermark_trace_id`。这样既避免切坏不可见 payload，又保留可审计水印 trace。
- 如果 `language_preview.aigc_watermark.blocked=true`，chunking 仍基于 blocked safe summary。
- SSE event data 使用 `json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"))`，确保 deterministic test output。
- TestClient 可以用 `client.stream("POST", "/v1/chat/internal-beta/messages/stream", ...)` 读取 body；不需要 browser/EventSource。

### Boundary Rules

- No public Chat route.
- No native EventSource frontend client.
- No ChatInterface implementation.
- No api-gateway streaming proxy.
- No WebSocket.
- No file upload / FilePicker / CSV / Excel / JSON upload.
- No what-if follow-up.
- No partial upload recovery.
- No Solver or Prediction submission.
- No Billing / Credits estimate or charge.
- No DB/Redis/outbox/conversation persistence.
- No notification / email / station message.
- No human review queue write beyond existing preview contract.
- No sandbox stdout/stderr logs streaming.
- No live provider network call.
- No AIGC filing status read/update.
- No generated-code execution beyond existing Sandbox preview path.
- No raw user message、message excerpt、provider payload、prompt、hidden reasoning、full generated code、sandbox output、secret-like text、traceback、host path、queue payload、charge/optimization/prediction id or callback URL in SSE data.

## Story Review Rounds

### Round 1 - Boundary / Endpoint Review (2026-05-29)

Findings applied:
- Native browser `EventSource` cannot send POST body, while Chat message creation requires a body; story now scopes this to backend SSE wire contract on protected POST and defers GET subscription adapter to 4.C.6/api-gateway.
- Original N7 wording could be misread as public `/v1/chat/stream`; story now keeps public route absent and only adds internal beta stream route.
- Stream work could drift into ChatInterface/frontend/AbortController; story now explicitly excludes frontend and browser client.
- Stream route could duplicate JSON pipeline and drift; story now requires shared internal helper for JSON and stream routes.

Status: PASS after fixes.

### Round 2 - Data Consistency / AIGC / No-Leak Review (2026-05-29)

Findings applied:
- Streaming full `model_preview` would leak generated code and exceed chunk semantics; story now streams only `model_preview_id/status` and keeps full preview in JSON route.
- Zero-width AIGC metadata can be split incorrectly across chunks; story now strips zero-width metadata from content chunks and carries watermark trace in `done`.
- `<=100 token` was underspecified without provider tokenizer; story now defines deterministic `content_unit_approximation` and names the limitation.
- Stream payloads could accidentally include raw message or message excerpt; story now forbids both and requires no-leak tests.

Status: PASS after fixes.

### Round 3 - Cursor / Dependency / Closure Review (2026-05-29)

Findings applied:
- P28 `Last-Event-ID` needs a behavior without Redis persistence; story now uses deterministic event list replay and starts after matched id.
- Invalid cursor could leak supplied header or internals; story now requires bounded `invalid_cursor` error event and no echo.
- FastAPI streaming cancellation can keep generators alive if no await occurs; story now requires `await anyio.sleep(0)` or equivalent cancellation yield.
- Workflow closure now includes post-implementation review gates for wire format, chunk limit, cursor, AIGC/no-leak and side-effect flags.

Status: PASS after fixes. Story is ready for development.

## Test / Validation Notes

Expected commands:

```powershell
$env:PYTHONPATH='apps/chat-service/src;apps/sandbox-runner/src;packages/shared-py'; uv run pytest apps/chat-service/tests/test_sse_streaming.py -q
$env:PYTHONPATH='apps/chat-service/src;apps/sandbox-runner/src;packages/shared-py'; uv run pytest apps/chat-service/tests/test_internal_beta.py apps/chat-service/tests/test_model_preview.py apps/chat-service/tests/test_aigc_filter_invoke.py -q
$env:PYTHONPATH='apps/chat-service/src;apps/sandbox-runner/src;packages/shared-py'; uv run pytest apps/chat-service/tests -q
uv run mypy apps packages
uv tool run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

RED expectation: focused tests should fail because `POST /v1/chat/internal-beta/messages/stream` and `chat_service.streaming` do not exist yet.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-29 - Story created from Epic 4.C.2 source AC, PRD N7, architecture P28/P34/C16, current 4.C.1 model preview contract, 4.B.6 sandbox logs-stream boundary, and FastAPI/MDN SSE docs.
- 2026-05-29 - Story review round 1 applied boundary/endpoint fixes: protected POST SSE route, public route absent, no frontend/EventSource adapter, and shared JSON/stream pipeline.
- 2026-05-29 - Story review round 2 applied data/AIGC/no-leak fixes: no full model preview streaming, zero-width metadata handling, deterministic token-unit approximation, and raw message/excerpt leak bans.
- 2026-05-29 - Story review round 3 applied cursor/dependency/closure fixes: deterministic Last-Event-ID replay, bounded invalid cursor error, cancellable generator, and post-review gates.
- 2026-05-29 - RED confirmed: focused streaming test failed because `chat_service.streaming` did not exist.
- 2026-05-29 - GREEN implemented: added pure streaming helpers, protected internal beta stream route, shared JSON/stream pipeline helper, deterministic SSE events, cursor resume, and focused tests.
- 2026-05-29 - Validation before code review passed: focused streaming 8 passed; related chat tests 50 passed; chat-service suite 161 passed; `uv run mypy apps packages`; `git diff --check`.
- 2026-05-29 - Post-implementation code review found one patch issue: filtered chunks reported token_units from the pre-filter text and invalid-cursor event id used a second derived prefix.
- 2026-05-29 - Review fixes applied: safe stream content is filtered before token splitting, `[filtered]` is preserved as an atomic chunk, emitted token_units match emitted chunk, and invalid-cursor event ids keep the stream prefix.
- 2026-05-29 - Final validation passed: focused streaming/related tests 51 passed; chat-service suite 162 passed; `uv run mypy apps packages`; `uv tool run pre-commit run --all-files --show-diff-on-failure`; `git diff --check`.
- 2026-05-29 - Dev-story started after three review rounds; sprint status moved from ready-for-dev to in-progress and starting RED streaming tests.
- 2026-05-29 - CI lint follow-up reproduced locally: ruff/bandit flagged `TOKEN_COUNT_METHOD` as hardcoded-password false positive; accepted formatter checkpoint changes and renamed the constant to avoid security-scanner drift while preserving the `token_count_method` SSE payload key.

### Completion Notes List

- Added protected `POST /v1/chat/internal-beta/messages/stream` using `StreamingResponse` and `text/event-stream`.
- JSON and stream routes now share the same internal beta pipeline builder, keeping `message_id`, locale, `model_preview`, AIGC gate and watermark trace consistent.
- Stream chunks are deterministic, bounded by `content_unit_approximation <=100`, strip zero-width metadata, and carry watermark trace in `done`.
- Public `/v1/chat/stream` remains absent; no frontend/EventSource, api-gateway proxy, WebSocket, file upload, what-if, Solver, Billing, DB/Redis/outbox, conversation persistence, notification, provider call, or sandbox logs stream was added.
- Post-review fixes ensure filtered content is chunked as emitted and cursor error events stay in the same deterministic stream id namespace.
- CI lint follow-up keeps the SSE payload contract unchanged while avoiding scanner false positives around token-count terminology.

### Review Findings

- [x] [Review][Patch] Filtered `content_delta` chunks must report token units for the emitted chunk, not the pre-filter input [`apps/chat-service/src/chat_service/streaming.py`] — fixed by computing `safe_chunk` first and deriving `token_units` from the emitted text; added regression coverage.
- [x] [Review][Patch] Invalid-cursor error event id should stay under the current stream prefix [`apps/chat-service/src/chat_service/streaming.py`] — fixed by extracting the prefix from existing event ids instead of hashing the first event id again.
- [x] [Review][CI] Ruff/Bandit hardcoded-password heuristics flagged `TOKEN_COUNT_METHOD` even though it is not secret material — fixed by renaming the implementation constant to `COUNT_UNIT_METHOD` and importing it in tests, preserving the wire key `token_count_method`.

### File List

- `_bmad-output/stories/4-c-2-sse-streaming.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/chat-service/src/chat_service/main.py`
- `apps/chat-service/src/chat_service/streaming.py`
- `apps/chat-service/tests/test_sse_streaming.py`

### Change Log

- 2026-05-29 - Created 4.C.2 story and completed three pre-implementation adversarial review rounds; story moved to ready-for-dev.
- 2026-05-29 - Started implementation and moved story/sprint status to in-progress.
- 2026-05-29 - Implemented internal beta SSE streaming contract and moved story/sprint status to code-review.
- 2026-05-29 - Completed post-implementation code review fixes, final validation, and moved story/sprint status to done.
- 2026-05-29 - Applied CI lint follow-up for ruff/bandit scanner compatibility without changing the SSE contract.
