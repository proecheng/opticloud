# Story 4.C.3: 文件上传 CSV/Excel/JSON 进入 Chat 上下文

Status: done

owner: Chat Platform / Chat UX Workflow / AIGC Safety

## Story

作为 internal beta Chat 用户和 Chat Platform owner，
我希望用户选择或拖入 CSV、Excel 或 JSON 后，前端先在浏览器侧完成 <=5MB 校验和结构化解析，
再把 bounded file context 传入 Chat internal beta pipeline，
以便 Chat 可以利用文件 schema、sheet/header、行数和 JSON key 等上下文生成更准确的模型预览，同时不开放 public Chat、完整 ChatInterface、大文件上传、S3 预签名、conversation persistence、Solver submission 或 raw file storage。

## Acceptance Criteria

1. Chat file context contract 是 bounded、显式、可测试的。
   - 新增 `file_contexts` 到 `POST /v1/chat/internal-beta/messages` 和 `POST /v1/chat/internal-beta/messages/stream` JSON body；字段可省略，默认空数组。
   - `file_contexts` 必须随 existing JSON body 提交；不得新增 `multipart/form-data` endpoint、`POST /v1/chat/files`、`POST /v1/files` 或 public upload route。
   - `file_contexts` 只接受前端浏览器侧解析后的结构化 metadata，不接受 multipart、base64、raw bytes、完整 CSV 行、完整 Excel rows、完整 JSON payload 或文件路径。
   - 单请求最多 3 个文件上下文；每个文件 `size_bytes <= 5 * 1024 * 1024`。
   - 支持 `kind in {"csv","excel","json"}`，并要求 `source="parsed_browser_file_context_v1"`。
   - 文件名必须是 basename，不能包含 `/`、`\`、drive letter、`..` 或控制字符；后端必须 fail closed。
   - `row_count`、`sheet_count`、headers、sheet names、JSON top-level keys、summary 等字段必须有固定上限：filename <=120 chars、mime_type <=100 chars、summary <=240 chars、sheet_count <=12、row_count <=50000、每个 sheet headers <=20、全文件 detected fields/top-level keys <=30、单个 field/header/key <=64 chars。

2. 前端新增 Chat 文件解析 helper，复用 `packages/ui` 的 `FilePicker` 单源边界。
   - 新增 `apps/web/src/lib/chat-file-context.ts`，导出 `parseChatFileContext(file)` 和相关 payload types。
   - 本 story 不创建完整 ChatInterface 页面；helper 必须是 `FilePicker.onFile` / `FilePicker.onReject` 可直接调用的 adapter，实际拖拽/聊天 UI 编排留给 4.C.6。
   - helper 接受 `.csv`、`.xlsx`、`.json`；其他扩展名或 MIME 必须拒绝，不能只依赖 `<input accept>`。
   - helper 实施 5MB 上限；超出时返回/抛出 typed reject reason，文案可用于 FilePicker `onReject` UI。
   - CSV 在浏览器侧解析，只提取第一行 headers、数据行数和 bounded summary；不得把完整 CSV 行或 raw bytes 放进 payload。
   - Excel 复用现有 `apps/web/src/lib/excel.ts::parseExcel(file)`，只传 sheet names、headers、row counts、total rows；不得新增第二套 Excel parser。
   - JSON 在浏览器侧 `JSON.parse`，只传 top-level keys、array length/object shape 和 bounded summary；不得传完整 JSON payload。
   - helper 输出字段使用 snake_case，能直接作为 Chat API body 的 `file_contexts`。

3. 文件上下文进入 Chat internal beta pipeline，但响应不泄漏原始文件内容。
   - Chat route 必须把 `file_contexts` 组合成 safe context summary 后传给同一条 Router -> Formulator -> Coder -> Critic -> HumanReview -> ConfidenceDisplay -> Sandbox -> ModelPreview -> Language pipeline。
   - 同一 message/client_request_id 但 file_contexts 不同，`message_id` 必须稳定地区分，避免不同文件上下文复用同一 deterministic id。
   - JSON route 和 stream route 必须复用同一个 request validation 与 response builder，避免 file-context 数据漂移。
   - Response 新增 optional bounded `file_context_preview`，字段固定为 `file_count`、`kinds`、`total_rows`、`filenames`、`detected_fields`；无文件上下文时为 `null`。`kinds` 和 `detected_fields` 必须去重并按字典序排序，`filenames` 必须是 sanitized basename 列表且保持请求顺序。不得回显 raw rows、raw JSON values、full file contents、host path、API key、Bearer token、cookie、authorization、password、provider payload、prompt、traceback、generated code、sandbox output、charge/optimization/prediction id 或 callback URL。
   - `language_preview.summary` 可以提到“已读取上传文件上下文”，但不得包含原始行值、完整 JSON values 或未清洗文件路径。
   - `file_context` canonical digest 必须基于 sanitized context 的 canonical JSON：`json.dumps(..., sort_keys=True, separators=(",", ":"))` 后 SHA-256；输入顺序变化不得影响 digest，需按 `(kind, filename, size_bytes, summary)` 排序后计算。
   - Safe prompt summary 只能由 sanitized filename、kind、row_count、sheet_count、sheet names、headers/top-level keys 构成，最大 700 chars；不得把 `summary` 作为唯一可信输入直接拼入 prompt，必须再次 sanitize/truncate。

4. 安全、AIGC 和边界 fail closed。
   - 未授权、internal beta disabled、signoff 不满足或 user/tenant/token 不匹配时，必须仍在 body validation 前返回 sparse `404 {"detail":"Not found"}`，不得泄漏 `file_contexts` schema、AIGC gate、watermark、stream event 或 ModelPreview 信息。
   - 授权通过后，非法 `file_contexts` 返回 422 JSON；stream route 不得开始 SSE 后再报 body validation error。
   - 任何 file context metadata 命中 secret/internal no-leak pattern 时，后端必须拒绝或安全替换；不得进入 response 或 SSE data。
   - 不新增 public `/v1/chat`、public `/v1/chat/stream`、conversation API、ChatInterface UI、api-gateway proxy、WebSocket、S3 预签名、大文件上传、DB/Redis/outbox persistence、notification、Solver/Prediction submission、Billing/Credits charge、AIGC filing mutation、live provider network call 或 sandbox stdout/stderr stream。
   - 本 story 不实现 4.C.5 partial-upload-recovery；解析失败或非法文件只返回明确 reject/error，不提供“仅替换失败行”恢复流。

5. SSE 与 JSON 行为保持一致。
   - Stream route 接受同样的 `file_contexts` body 并复用 JSON route pipeline builder。
   - 同一 tenant/user/client_request_id/message/file_contexts 下，stream route 的 `message_id`、`locale`、`model_preview_id/status`、`aigc_gate`、`aigc_watermark_trace_id` 和 `file_context_preview` 必须与 JSON route 一致。
   - Stream events 不新增 raw file event；`message_start` 或 `done` 中如包含 file context，只能包含 bounded preview/counts。
   - 既有 `Last-Event-ID` resume、invalid cursor bounded error、chunk <=100 token-unit 和 AIGC/no-leak 约束不得回退。

6. Tests 必须先红后绿，覆盖 parser、contract、安全和边界。
   - 新增 web focused tests 覆盖 `parseChatFileContext`：CSV、Excel、JSON happy path，>5MB reject，wrong type reject，filename sanitization/no path，no raw rows/raw JSON values in payload。
   - 新增 chat-service focused tests 覆盖：authorized JSON route with `file_contexts` returns bounded preview and uses deterministic distinct `message_id`; stream route matches JSON preview/id; unauthorized invalid body still 404 before body validation; invalid file context returns 422 before SSE; no raw file values or secret-like metadata leaks。
   - 新增 digest stability tests：相同 file contexts 不同数组顺序得到同一 `message_id`；file headers/keys 改变时 `message_id` 改变。
   - 保留 existing `test_internal_beta.py`、`test_sse_streaming.py`、`test_model_preview.py`、`test_aigc_filter_invoke.py` 回归。
   - Tests 不得需要 live LLM provider、外部网络、真实 DB/Redis/outbox、S3、Solver、Billing、K8s、api-gateway、browser/EventSource、AIGC filing 或 GitHub token。

7. Workflow tracking 和闭环清晰。
   - 本 story 记录三轮 pre-implementation adversarial review，并在每轮后应用修正后才能进入 implementation。
   - dev-story 开始时将 sprint status 置为 `in-progress`；实现完成且测试通过后置为 `code-review`。
   - post-implementation code review 必须覆盖边界问题、漂移问题、数据一致性、依赖一致性、是否闭环、file parser privacy、Chat pipeline consistency、SSE consistency、AIGC/no-leak、side-effect flags 和测试证据。
   - code review 修正与完整验证通过后，story 与 sprint status 才能置为 `done`，随后 commit、push、创建 PR、等待 CI、merge/sync GitHub。

## Tasks / Subtasks

- [x] Task 1: 建立 Chat file context schema/helper contract。 (AC: 1, 3, 4)
  - [x] 在 `apps/chat-service/src/chat_service/schemas.py` 增加 `ChatFileContext` / preview schema，并把 `file_contexts` 加入 `ChatInternalBetaMessageRequest`。
  - [x] 在 `ChatInternalBetaMessageResponse` 增加 `file_context_preview`；更新所有直接构造 response 的测试/fixtures（例如 sandbox tests），无上下文时显式为 `None`。
  - [x] 新增 `apps/chat-service/src/chat_service/file_context.py`，负责 context digest、safe prompt summary、bounded response preview 和 no-leak guard。
  - [x] 确保非法 basename、过大 size、过多 contexts、过长 headers/keys、secret-like metadata fail closed 或安全替换。
- [x] Task 2: 将 file context 接入 Chat JSON/SSE 共用 pipeline。 (AC: 3, 5)
  - [x] 修改 `_build_internal_beta_response(...)`，用 safe file context summary 参与 Router/Formulator/Coder/Language 输入。
  - [x] `message_id` digest 纳入 file context canonical digest。
  - [x] JSON response 和 SSE `done` 或 bounded data 中暴露同一个 `file_context_preview`，不得回显 raw rows/values。
  - [x] 保持 public routes absent，保持 provider/solver/billing/db side-effect flags 不变。
- [x] Task 3: 新增前端 Chat file context parser helper。 (AC: 2)
  - [x] 新增 `apps/web/src/lib/chat-file-context.ts`，实现 `.csv/.xlsx/.json` typed parse + reject。
  - [x] CSV 只提取 headers/row count；Excel 复用 `parseExcel`；JSON 只提取 object keys/array length/shape。
  - [x] 输出 snake_case payload，供未来 4.C.6 ChatInterface + `FilePicker` 直接提交给 Chat internal beta API。
- [x] Task 4: RED/GREEN tests。 (AC: 4, 5, 6)
  - [x] 先写 focused tests 并确认 RED：web helper 缺失、chat-service `file_contexts` 不被接受。
  - [x] 实现最小代码转 GREEN。
  - [x] 覆盖 JSON route、stream route、invalid contexts、unauthorized fail-closed、no-leak、message_id digest 区分、helper parser 行为，以及既有 no-file response 仍返回 `file_context_preview: null`。
- [x] Task 5: 验证、审查与关闭。 (AC: 7)
  - [x] 跑 focused 与 full validation。
  - [x] 执行 post-implementation code review 并修复 findings。
  - [x] 更新 Dev Agent Record、File List、Change Log 和 sprint-status。
  - [x] commit、push、创建 PR、等待 CI、merge/sync GitHub。

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:1581` 定义 Story 4.C.3：文件上传 CSV/Excel/JSON (N8)，共用 Epic 3.E FilePicker。
- `_bmad-output/planning/prd.md:1493` 定义 FR N8：用户 can upload files (CSV/Excel/JSON)。
- `_bmad-output/planning/architecture.md:1133` 与 `1134` 将 >1MB/大文件上传放在 multipart/S3 预签名架构；本 story 的 N8 internal beta 范围先采用浏览器侧解析后的 bounded metadata，不做 S3。
- `_bmad-output/planning/architecture.md:3283` 和 `3284` 将 Lina CSV / 老张 Excel surface 映射到 `packages/ui FilePicker` / `ExcelDropZone`；4.C.3 必须复用单源组件和已有 parser，不复制。
- `packages/ui/src/components/FilePicker/index.tsx` 当前默认 accept `.csv,.xlsx,.json`，默认 5MB，并通过 `onReject` 暴露 too_large；但 HTML `accept` 不是安全边界，4.C.3 helper 仍需做 extension/MIME validation。
- `apps/web/src/lib/excel.ts` 已有 browser-side `parseExcel(file, {includeRows?})`，3.E.2 起用于隐私保护的客户端 Excel 解析。
- `apps/web/src/lib/csv-prediction.ts` 已有 Lina CSV parser/recovery，但它是 prediction vertical slice 的业务 mapper；4.C.3 不应复用其 prediction-specific aggregation 语义，只可借鉴 browser-side privacy boundary。
- `apps/chat-service/src/chat_service/main.py` 当前 JSON 和 SSE routes 共用 `_validate_internal_beta_request(...)` 与 `_build_internal_beta_response(...)`。
- `apps/chat-service/src/chat_service/streaming.py` 当前已实现 deterministic event ids、Last-Event-ID、chunk <=100 token-unit、AIGC/no-leak 和 bounded invalid-cursor event。

### Previous Story Intelligence

- 4.C.1 建立 `model_preview` response-only contract，明确不得新增 Solver/Billing/DB/public Chat。
- 4.C.2 建立 protected `POST /v1/chat/internal-beta/messages/stream`，并把 JSON/SSE 共用 pipeline 作为防漂移规则；4.C.3 必须延续这一 helper，不复制业务 pipeline。
- 4.C.2 的 CI lint follow-up 说明安全扫描会误判带 `TOKEN` 的常量名；新增 file context 代码避免把非密钥常量命名成 `*_TOKEN_*`。
- 3.11 Lina CSV 经验：浏览器侧解析保护隐私；原始文件 bytes、完整 raw rows 和 API keys 不应进入 UI state、URL、localStorage、sessionStorage、日志或测试快照。
- 3.E.2-3.E.7 Excel 经验：`parseExcel` 是当前单源读取 helper；写 Excel 使用动态 import，不应影响本 story。

### Implementation Guidance

- 建议新增 `apps/chat-service/src/chat_service/file_context.py`：
  - `canonical_file_context_digest(contexts: Sequence[ChatFileContext]) -> str`
  - `build_file_context_prompt_summary(contexts: Sequence[ChatFileContext]) -> str`
  - `build_file_context_preview(contexts: Sequence[ChatFileContext]) -> ChatFileContextPreview | None`
  - `build_message_with_file_context(message: str, contexts: Sequence[ChatFileContext]) -> str`
  - no-leak pattern 与 `streaming.py` / `schemas.py` 保持同等保守。
- `ChatFileContext` schema 应只存 bounded metadata：
  - `source`, `kind`, `filename`, `size_bytes`, `mime_type`
  - `row_count`, `sheet_count`
  - `sheets: [{name, headers, row_count}]`
  - `top_level_keys`
  - `summary`
- `file_context_preview` response 不应包含 sample rows。若需要 headers/keys，限制总数并先 sanitize/redact。
- `_message_id(...)` 需要纳入 file-context digest；无 file_contexts 时保持现有 id 兼容。
- Prompt summary、response preview、canonical digest 必须由同一个 `sanitize_file_contexts(...)` 结果派生，不能三处各自清洗，防止数据漂移。
- 现有 `test_internal_beta.py` 对大 response 有整对象断言；新增 `file_context_preview` 后必须更新这些断言，避免测试以为响应漂移。
- `apps/chat-service/tests/test_sandbox.py` 直接构造 `ChatInternalBetaMessageResponse`；新增 required response 字段时必须同步 fixture，或者把字段定义为 optional default `None` 以保持兼容。优先显式 default `None`，并加 no-file route 断言。
- `apps/web/src/lib/chat-file-context.ts` 可复用现有 `parseExcel`，并实现轻量 CSV parser。不要新增 PapaParse、ExcelJS、backend API route 或 service worker。
- Web helper 输出 snake_case，避免每个调用点再做 camelCase -> snake_case 转换。

### Boundary Rules

- No public Chat route.
- No full ChatInterface UI.
- No Chat page or drag/drop UI wiring in this story; 4.C.6 owns visual ChatInterface composition.
- No native EventSource frontend client changes.
- No api-gateway streaming proxy.
- No WebSocket.
- No multipart endpoint, S3 presigned URL, object storage, file persistence or upload-complete webhook.
- No DB/Redis/outbox/conversation persistence.
- No partial-upload-recovery.
- No Solver or Prediction submission.
- No Billing / Credits estimate or charge.
- No notification / email / station message.
- No human review queue write beyond existing preview contract.
- No sandbox stdout/stderr logs streaming.
- No live provider network call.
- No AIGC filing status read/update.
- No raw file bytes, raw rows, full JSON values, raw user message, provider payload, prompt, hidden reasoning, full generated code, sandbox output, secret-like text, traceback, host path, queue payload, charge/optimization/prediction id or callback URL in Chat response or SSE data.

## Story Review Rounds

### Round 1 - Boundary / Endpoint Review (2026-05-29)

Findings applied:
- Source AC says users drag files, but the current repo has no ChatInterface yet and 4.C.6 owns full UI composition; story now scopes this to a `FilePicker`-compatible parser adapter plus internal beta JSON metadata contract.
- The initial wording could be misread as adding `multipart/form-data` or public upload endpoints; AC now forbids `POST /v1/chat/files`, `POST /v1/files`, public upload routes, and multipart payloads.
- Response preview shape was under-specified and could drift across JSON/SSE; story now fixes `file_context_preview` fields and says absent contexts return `null`.
- Boundary rules now explicitly defer Chat page drag/drop wiring to 4.C.6 so implementation cannot sprawl into frontend composition.

Status: PASS after fixes.

### Round 3 - Dependency / Test Closure Review (2026-05-29)

Findings applied:
- Adding `file_context_preview` can break existing strict response assertions and direct Pydantic fixture construction; tasks now explicitly require updating existing chat-service tests and making the no-file response path explicit.
- Web changes trigger the `web` CI path, but the first validation list only had focused web tests; validation now includes full `pnpm -C apps/web test` plus `pnpm -C apps/web typecheck`.
- Existing Chat JSON/SSE contract tests must prove no-file requests continue returning a stable `file_context_preview: null`, not silently omit or vary the field.
- Story now calls out direct `ChatInternalBetaMessageResponse` construction in sandbox tests so implementation cannot pass focused tests while breaking broader chat-service suite.

Status: PASS after fixes. Story is ready for development.

### Round 2 - Data Consistency / Privacy / No-Leak Review (2026-05-29)

Findings applied:
- Original story did not pin caps for headers, sheet names, JSON keys, summary, row counts or filenames, so implementation could pass tests while still allowing prompt/context blowup; AC now defines exact per-field limits.
- `file_context_preview` fields were named but not ordered; story now fixes sorting/ordering semantics so JSON route, SSE route, tests and clients see stable data.
- `message_id` distinctness was required, but canonicalization was underspecified; story now requires a sanitized canonical JSON digest with order-independent context sorting.
- Prompt summary could have used browser-provided `summary` verbatim, reintroducing raw values; story now requires prompt summary, response preview and digest to derive from one sanitized context pass, with a 700-character prompt cap and repeated sanitization.
- Tests now include digest stability and digest-change coverage to prevent accidental ID collisions or drift.

Status: PASS after fixes.

## Test / Validation Notes

Expected commands:

```powershell
pnpm -C apps/web test -- chat-file-context
pnpm -C apps/web test
$env:PYTHONPATH='apps/chat-service/src;apps/sandbox-runner/src;packages/shared-py'; uv run pytest apps/chat-service/tests/test_file_context.py apps/chat-service/tests/test_internal_beta.py apps/chat-service/tests/test_sse_streaming.py apps/chat-service/tests/test_model_preview.py apps/chat-service/tests/test_aigc_filter_invoke.py -q
$env:PYTHONPATH='apps/chat-service/src;apps/sandbox-runner/src;packages/shared-py'; uv run pytest apps/chat-service/tests -q
pnpm -C apps/web typecheck
uv run mypy apps packages
uv tool run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

RED expectation: focused tests should fail because `apps/web/src/lib/chat-file-context.ts`, `chat_service.file_context`, and `ChatInternalBetaMessageRequest.file_contexts` do not exist yet.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-29 - Story created from Epic 4.C.3 source AC, PRD N8, architecture file upload/S3 boundaries, existing FilePicker, existing browser-side Excel parser, 3.11 CSV privacy lessons, and 4.C.2 JSON/SSE shared-pipeline contract.
- 2026-05-29 - Story review round 1 applied boundary/endpoint fixes: FilePicker-compatible helper only, no public/multipart upload route, fixed preview field shape, and ChatInterface wiring deferred to 4.C.6.
- 2026-05-29 - Story review round 2 applied data/privacy/no-leak fixes: exact field caps, deterministic preview ordering, order-independent sanitized canonical digest, single sanitize pass for digest/prompt/preview, and digest stability tests.
- 2026-05-29 - Story review round 3 applied dependency/test-closure fixes: response fixture compatibility, no-file preview null contract, full web validation, and chat-service full-suite guardrails.
- 2026-05-29 - Dev implementation started after three story review rounds; sprint status moved from ready-for-dev to in-progress and starting RED tests.
- 2026-05-29 - RED confirmed: web focused test failed because `apps/web/src/lib/chat-file-context.ts` does not exist; chat-service focused tests failed because `file_contexts` is rejected as extra input and `file_context_preview` is absent.
- 2026-05-29 - GREEN implemented: added chat-service file context schemas/helper, safe prompt summary, canonical digest, bounded response/SSE preview, language fallback context marker, and web `parseChatFileContext` helper.
- 2026-05-29 - Focused validation passed: `pnpm -C apps/web test -- chat-file-context` 6 passed; related chat tests 58 passed.
- 2026-05-29 - Post-implementation code review found two patch issues: Pydantic 422 bodies echoed unsafe `input` values for rejected file metadata, and SSE formatter did not recursively filter secret-like strings inside lists.
- 2026-05-29 - Review fixes applied: internal beta validation now returns sanitized 422 errors without input echo, and SSE `_safe_data` recursively filters list values; regression tests added.
- 2026-05-29 - Additional closure review fixed two edge findings: web helper now requires supported extension and MIME pairing, and file context digest now sorts complete sanitized canonical JSON entries to avoid tie-order drift.
- 2026-05-29 - Final validation passed: focused web parser, focused chat file/SSE, full chat-service suite, full web suite, web typecheck, mypy, pre-commit, and diff-check.

### Completion Notes List

- Story scopes 4.C.3 to parsed browser-side file context metadata entering internal beta Chat pipeline.
- Story explicitly excludes public Chat, full ChatInterface UI, raw uploads, S3, persistence, partial upload recovery, Solver, Billing, provider calls, and file bytes storage.
- Round 1 clarified that this story delivers the upload-to-context contract and parser adapter; visible Chat drag/drop composition remains in 4.C.6.
- Round 2 fixed deterministic data semantics so safe prompt summary, response preview and message id digest cannot drift.
- Round 3 closed compatibility and validation gaps for existing strict chat-service tests and web CI-triggered changes.
- Dev implementation has started; RED tests will first prove missing web helper and chat-service file context contract.
- RED phase complete with the expected missing-module and missing-schema failures.
- GREEN phase complete for focused parser, JSON route, SSE route, digest, no-leak and fail-closed tests.
- Post-review fixes close validation-error echo leakage and nested SSE list filtering gaps.
- Additional closure fixes close MIME-only acceptance drift and canonical digest tie-order drift.
- Story implementation, post-review fixes, full validation, story record update and sprint status update are complete.

### Review Findings

- [x] [Story Review][Boundary] Source AC could pull implementation into full ChatInterface or public upload endpoints — fixed by scoping to a FilePicker-compatible helper and internal beta JSON body metadata only.
- [x] [Story Review][Data/Privacy] File context caps, digest canonicalization and preview ordering were underspecified — fixed with exact limits, sanitized canonical JSON digest rules and stability tests.
- [x] [Story Review][Dependencies/Closure] New response fields and web helper changes could break existing full-suite tests outside focused coverage — fixed by requiring no-file `file_context_preview: null`, fixture updates, full web tests and chat-service full-suite validation.
- [x] [Review][Patch] Rejected file context metadata leaked unsafe user input through Pydantic 422 `detail.input` — fixed by emitting sanitized validation errors with only type/loc/msg.
- [x] [Review][Patch] SSE event data sanitizer did not recurse through list values — fixed by adding recursive `_safe_value(...)` handling for strings, dicts and lists with regression coverage.
- [x] [Review][Patch] Web parser accepted MIME-only CSV/JSON/Excel classification despite wrong extension — fixed by requiring supported extension and MIME pairing.
- [x] [Review][Patch] File context digest order stability could drift when sort keys tied for same kind/filename/size/summary — fixed by sorting complete sanitized canonical JSON entries.

### File List

- `_bmad-output/stories/4-c-3-file-upload-csv-excel-json.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/chat-service/src/chat_service/file_context.py`
- `apps/chat-service/src/chat_service/language_response.py`
- `apps/chat-service/src/chat_service/main.py`
- `apps/chat-service/src/chat_service/schemas.py`
- `apps/chat-service/src/chat_service/streaming.py`
- `apps/chat-service/tests/test_file_context.py`
- `apps/web/src/lib/chat-file-context.ts`
- `apps/web/src/lib/chat-file-context.test.ts`

### Change Log

- 2026-05-29 - Created 4.C.3 story and moved sprint status from backlog to ready-for-dev.
- 2026-05-29 - Applied Story Review Round 1 boundary/endpoint fixes.
- 2026-05-29 - Applied Story Review Round 2 data/privacy/no-leak fixes.
- 2026-05-29 - Applied Story Review Round 3 dependency/test-closure fixes.
- 2026-05-29 - Started implementation and moved story/sprint status to in-progress.
- 2026-05-29 - Added focused RED tests for web parser and chat-service file context contract.
- 2026-05-29 - Implemented focused GREEN for Chat file context parser and internal beta JSON/SSE contract.
- 2026-05-29 - Completed post-implementation code review fixes for sanitized 422 errors and recursive SSE list filtering.
- 2026-05-29 - Completed closure review fixes for extension/MIME pairing and canonical digest tie-order stability.
- 2026-05-29 - Completed full validation and moved story/sprint status to done.
