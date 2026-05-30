# Story 4.C.6: ChatInterface Tier 2 Component (UX-DR1)

Status: done

owner: Chat Platform / Chat UX Workflow / UI Platform

## Story

作为 internal beta Chat 用户和 Chat Platform owner，
我希望 `packages/ui` 提供一个完整但无业务副作用的 Tier 2 `ChatInterface`，并在 web console 内用安全 adapter 接入现有 internal beta Chat JSON/SSE/file/what-if 合同，
以便 Epic 4 可以复用同一个聊天界面完成 history、streaming、file picker、partial upload recovery、model preview、what-if follow-up 和 a11y，而不提前开放 public Chat、conversation persistence、Solver submission 或 Billing。

## Acceptance Criteria

1. `packages/ui` 新增并导出 adapter-driven `ChatInterface` Tier 2 component。
   - 新增 `packages/ui/src/components/ChatInterface/index.tsx`、focused tests 和 Storybook story，并从 `packages/ui/src/index.ts` 导出 component 与 public types。
   - Component 必须是 presentation/state-orchestration component，不直接 import `apps/web`、Next.js、`fetch`、`process.env`、chat-service code、API keys、internal beta tokens、localStorage/sessionStorage 或 backend route 常量。
   - Component 通过 props 接收 `onSendMessage(request)`、`onSelectFile(file)`、`onReplaceFailedRows(recoveryId, replacementCsv)`、可选 `buildWhatIfContext(message)` 等 adapter callbacks；父应用负责实际 API 调用、headers 和环境。
   - `onSendMessage` 的返回值必须是 discriminated union：`{mode:"complete", response}` 或 `{mode:"stream", events}`；`events` 是 `AsyncIterable<ChatInterfaceStreamEvent>`。Component 不接收任意 callback controls，避免 adapter 在组件内部写入不可追踪状态。
   - Component 必须支持 in-memory UI history：用户消息、assistant streaming/complete/error messages、attached bounded file context preview、model preview summary/actions、what-if preview summary。不得写 DB、Redis、URL、local/session storage 或 service worker。
   - Public prop types 必须使用 bounded UI contracts，而不是直接暴露 backend raw response shape 全量对象。允许镜像必要字段：message id、locale、language summary/chunks、`model_preview.preview_id/status/actions/task_type/critic_confidence/sandbox_status/validation_errors`、`file_context_preview`、`what_if_preview`、AIGC gate。
   - `ChatInterface` 不得接受或存储 internal beta tenant/user/token、request headers、service URL、raw backend response、raw SSE text、raw file `File` object 或 recovery session object；这些只能存在于 web adapter/page 的短生命周期局部变量中。
   - Component 必须可在没有 backend adapter 的 Storybook/test 中以 mock callback 工作，不需要 network。

2. ChatInterface 完整覆盖 UX-DR1 的核心交互。
   - 首屏显示历史列表、空态、composer、send button、file picker 入口和流式状态区域；不要做营销 landing page。
   - 用户输入 2..2000 trimmed chars 才能发送；发送中禁止重复提交同一 draft，但不能锁死文件选择和取消/重置类本地动作。
   - `Enter` 发送、`Shift+Enter` 换行；发送后清空 draft 并把焦点恢复到 composer。
   - 发送时立即 append 用户消息和 assistant pending message；streaming `content_delta` 到达时增量渲染 assistant 内容；done 后显示 bounded model/file/what-if previews。
   - 非 streaming adapter 返回完整响应时也必须更新同一套 message/history UI，避免 JSON 和 SSE UI 分叉。
   - API/adapter error 必须变成 assistant error message 或 status panel；不得 throw 到 React tree 或泄漏 raw request/header/token/provider payload/stack trace。
   - 若 streaming iterator 抛错、提前结束且没有 `done`、或返回未知 event，assistant message 必须进入 bounded error / incomplete state；不得永久保持 loading。
   - Assistant message 的 lifecycle 必须固定：`pending -> streaming -> complete` 或 `pending/streaming -> error/incomplete`；同一 request 不得产生多个 assistant message 或遗留 orphan pending message。
   - 提供清空当前 in-memory history 的本地动作；不得调用 backend delete。

3. FilePicker 和 4.C.3/4.C.5 文件上下文闭环接入。
   - Component 必须复用 `packages/ui` 现有 `FilePicker`，默认 accept `.csv,.xlsx,.json`，默认 5MB；不得复制 file input。
   - `ChatInterface` 的 `onSelectFile(file)` adapter 负责调用 `apps/web/src/lib/chat-file-context.ts::parseChatFileContext(file)` 或 `parseChatCsvWithRecovery(file)`；UI component 只消费 adapter 返回的 bounded result。
   - 支持显示最多 3 个待发送 `file_contexts` 的 bounded preview：kind、filename、row_count/sheet_count/detected_fields；不得显示 raw rows、raw JSON values、raw bytes、host path、API key/token 或 file object serialization。
   - CSV partial failure 时，Component 必须显示 modal-ready recovery UI，动作固定为 `replace_failed_rows` / `仅替换失败行`、`retry_all` / `全部重试`、`cancel` / `取消`；UI 只保存 `recoveryId`、filename、invalid row count 和 bounded invalid row摘要，不保存 recovery session object。
   - `replace_failed_rows` 必须通过 adapter 提交 `recoveryId + replacementCsv` 并只在 adapter 返回 success context 后加入 pending file contexts；`retry_all` 清空 recovery state 并等待重新选择；`cancel` 关闭 modal 且不产生 context。
   - Web adapter 可以在 module-local `Map<recoveryId, ChatCsvRecoverySession>` 中暂存 session；成功、retry、cancel、组件 unmount 或清空 history 后必须删除对应 entry。不得序列化、导出或写入 storage。
   - File parsing/recovery failure 必须 fail closed：不发送 Chat request、不保留半成品 context、不把 raw row/cell/secret 放入 UI state 或测试 snapshot。

4. Web console 集成只暴露 internal beta dogfood surface。
   - 新增 `apps/web/src/lib/chat.ts` 或同等 helper，封装 `sendInternalBetaChatMessage(...)`、`streamInternalBetaChatMessage(...)`、SSE parser、response normalization 和 request types。
   - 新增 `apps/web/src/app/console/chat/page.tsx`，作为 internal beta console 页面使用 `ChatInterface` + web adapter。
   - Web helper 默认使用 `NEXT_PUBLIC_CHAT_SERVICE_URL ?? "http://localhost:8004"`；internal beta headers 从用户在页面输入的 tenant/user/token 或调用方显式参数读取，绝不硬编码真实 token，绝不保存到 localStorage/sessionStorage/cookie。
   - 页面必须清楚处于 internal beta：所有请求仍发往 `/v1/chat/internal-beta/messages` 或 `/v1/chat/internal-beta/messages/stream`；不得新增 public `/v1/chat`、public stream route、conversation API、api-gateway proxy、WebSocket 或 server action。
   - Native `EventSource` 不可用于发送 POST body；streaming helper 必须使用 `fetch` + `ReadableStream` 解析 SSE 文本块，或在不支持 stream body 时 fallback 到 JSON route。
   - Unauthorized/disabled internal beta 返回 sparse 404 时，UI 只显示通用 unavailable/error，不暴露 headers、schema、AIGC、ModelPreview、FileContext 或 WhatIf internals。

5. JSON/SSE、model preview、what-if 和 history 数据一致。
   - `ChatInterface` 发给 adapter 的 request 必须只包含：trimmed `message`、optional `locale`、generated bounded `client_request_id`、当前 pending `file_contexts`、optional bounded UI what-if intent。
   - 实际 backend request body 由 web helper 构造，字段只能是 trimmed `message`、optional `locale`、`client_request_id`、current `file_contexts`、optional bounded `what_if_context`。
   - `client_request_id` 必须由 web helper 生成，格式建议 `chat-ui-${Date.now()}-${random}` 或 `crypto.randomUUID()` 派生，无 PII；不得使用 API key、tenant、user、raw message、filename 或 file content 作为 id。
   - SSE parser 必须支持 heartbeat、`message_start`、`content_delta`、`done`、`error`；未知 event 忽略或安全记录为 bounded debug string，不破坏 UI。
   - SSE `done` 中的 `file_context_preview` / `what_if_preview` / `model_preview_id/status` 必须更新同一个 assistant message；JSON response normalization 也必须落到同一 message model。
   - `model_preview.actions` 只作为本地 UI action descriptors：confirm/edit/cancel 不调用 Solver/Billing/Optimization/Prediction，不创建 charge/id/job，不新增 backend mutation。confirm 可将当前 assistant message 标记为 locally confirmed；edit 把 bounded model summary/context 送回 composer；cancel 清理 local pending confirm state。
   - What-if follow-up 只能由最近一个 complete assistant message 的 bounded `message_id`、`model_preview`、`what_if_preview`/`file_context_preview` 派生；不得读取 pending/error message、server-side conversation、完整 raw transcript、generated code 或 raw solver result。
   - `ChatInterface` 的 what-if affordance 只能把 bounded message metadata 交给 `buildWhatIfContext`；真正的 `ChatWhatIfContext` shape 在 web helper 中构造和验证，避免 UI package 依赖 chat-service schema。
   - 发送成功后 pending file contexts 默认清空；发送失败时 pending file contexts 可保留供用户重试，但 history 中只保留 bounded preview，不保留 File objects 或 recovery session。
   - Clear history 必须同时清理 pending file contexts、recovery modal state、draft what-if context 和 local confirmation state，避免下一轮请求继承旧上下文。

6. A11y / i18n / visual behavior 达到 Tier 2 baseline。
   - Component 必须调用 `useA11y` 或等价 local patterns，提供 `aria-label`、`aria-live` streaming status、keyboard reachable controls、visible focus ring、button disabled states 和 form labels。
   - Recovery modal 必须使用现有 `ConfirmationModal` 或等价 Radix/Dialog pattern；不得嵌套 modal；ESC/焦点陷阱保持可用。
   - `jest-axe` 对 `ChatInterface` happy path、streaming path、recovery modal path 0 violations。
   - 所有用户可见默认文案先用简体中文，关键状态允许中英混合但不得把 i18n key 直接显示给用户；aria label 可使用稳定 key 风格。
   - UI 使用现有 Tailwind tokens、8px radius 内的 cards/panels、lucide icons（有合适图标时）和紧凑 console layout；不得引入新 runtime UI dependency、单色大面积主题、hero/landing 或装饰背景。
   - Text 在窄屏下必须换行/截断合理；message bubble、preview panel、buttons 不得因为长 filename/model id 溢出。

7. Tests 必须先红后绿，覆盖 component、adapter、page 和 regressions。
   - RED 先新增 focused tests，确认 `ChatInterface` export、component behavior、web chat helper 或 console page 缺失导致失败。
   - `packages/ui` tests 覆盖：send flow、streaming delta rendering、file context preview、partial recovery modal三动作、replace/retry/cancel、model preview actions local-only、keyboard submit/focus restore、error message、安全 no raw leak。
   - `packages/ui` a11y tests 覆盖 happy/streaming/recovery modal 0 axe violations，并将 ChatInterface 纳入合适的 Tier 2 a11y suite。
   - `apps/web` tests 覆盖：SSE parser heartbeat/delta/done/error、POST headers/body、JSON fallback/normalization、404 fail-closed、console page不保存 token、不使用 EventSource；page tests 必须加 `// @vitest-environment happy-dom`。
   - 保留并运行既有 `chat-file-context`、`chat-file-context-recovery` tests，确认 parser/recovery 行为不回退。
   - 验证命令至少包括：`pnpm --filter @opticloud/ui exec vitest run src/components/ChatInterface`、`pnpm --filter @opticloud/ui exec vitest run src/components/ChatInterface/index.a11y.test.tsx`、`pnpm --filter @opticloud/ui typecheck`、`pnpm --filter @opticloud/web exec vitest run chat`、`pnpm --filter @opticloud/web typecheck`、`git diff --check`。
   - 若修改 chat-service，必须 rerun related chat-service tests；默认本 story 不修改 backend。

8. Workflow tracking 和 GitHub 闭环。
   - 本 story 必须记录三轮 pre-implementation adversarial review，并在每轮后应用修正后才能进入 implementation。
   - 三轮审查至少覆盖：边界/ownership、漂移/数据一致性/privacy、依赖/a11y/test closure。
   - dev-story 开始时将 sprint status 置为 `in-progress`；实现完成且测试通过后置为 `code-review`。
   - post-implementation code review 必须覆盖边界问题、漂移问题、数据一致性、依赖一致性、是否闭环、a11y、history lifecycle、SSE parser、file recovery、what-if derivation、no-leak 和测试证据。
   - code review 修正与完整验证通过后，story 与 sprint status 才能置为 `done`，随后 commit、push、创建 PR、等待 CI、merge/sync GitHub。

## Tasks / Subtasks

- [x] Task 1: 建立 ChatInterface public API 和 RED component tests。 (AC: 1, 2, 6, 7)
  - [x] 新增 `packages/ui/src/components/ChatInterface/index.test.tsx`，先断言 export/发送/streaming/recovery/model actions 缺失为 RED。
  - [x] 定义 bounded public types：message、send request、stream events、file context preview、recovery state、model preview summary、what-if preview summary。
  - [x] 新增 `packages/ui/src/components/ChatInterface/index.tsx` 最小 skeleton 并从 `packages/ui/src/index.ts` 导出。
- [x] Task 2: 实现 ChatInterface UI state machine。 (AC: 1, 2, 3, 5, 6)
  - [x] 实现 in-memory history、composer、keyboard submit、focus restore、pending/streaming/complete/error assistant message。
  - [x] 接入 `FilePicker`、bounded file context preview、partial CSV recovery modal 三动作和 fail-closed parse state。
  - [x] 实现 model preview actions local-only、what-if follow-up affordance 和 pending context clearing。
  - [x] 加 Storybook story 覆盖 default、streaming、with file context、recovery modal、error/model preview states。
- [x] Task 3: 增加 ChatInterface a11y/no-leak coverage。 (AC: 6, 7)
  - [x] 新增 `packages/ui/src/components/ChatInterface/index.a11y.test.tsx` 或纳入 Tier2 a11y suite。
  - [x] 不把 ChatInterface 塞进现有 `Tier1.a11y.test.tsx` 的 Tier 1 描述；如需共享覆盖，新增 Tier 2/ChatInterface 专用 a11y test。
  - [x] 覆盖 aria-live、labels、keyboard reachable、modal focus/ESC、long filename wrapping/no raw leak。
- [x] Task 4: 新增 web internal beta chat adapter/helper。 (AC: 4, 5, 7)
  - [x] 新增 `apps/web/src/lib/chat.ts` 和 focused tests，先 RED 后实现 `sendInternalBetaChatMessage`、`streamInternalBetaChatMessage`、SSE parser、normalization、bounded id generation。
  - [x] 使用 `fetch` + POST body 解析 SSE；不得使用 `EventSource`。
  - [x] 接入 `parseChatFileContext`、`parseChatCsvWithRecovery`、replace/retry/cancel helpers，保持 raw file/recovery internals 不进 serialized UI state。
  - [x] 用 module-local Map 管理 `recoveryId -> ChatCsvRecoverySession`，在 success/retry/cancel/unmount/clear 后清理。
- [x] Task 5: 新增 `/console/chat` internal beta page。 (AC: 4, 5, 6, 7)
  - [x] 页面组合 `ChatInterface`、internal beta tenant/user/token inputs 和 web adapter；token 只存在 React state/ref，不写 storage。
  - [x] 加 focused page test 覆盖 headers/body、404 fail-closed、不保存 token、JSON fallback 或 stream done rendering。
  - [x] 在 console nav 如有现有模式可加入口；不要改 public landing 为 Chat 主入口。
- [x] Task 6: 验证、代码审查与关闭。 (AC: 7, 8)
  - [x] 跑 focused RED/GREEN 和 full relevant validation。
  - [x] 执行 post-implementation code review 并修复 findings。
  - [x] 更新 Dev Agent Record、File List、Change Log、story status 和 sprint-status。
  - [x] commit、push、创建 PR、等待 CI、merge/sync GitHub。

### Review Findings

- [x] [Review][Patch] Streaming `done` with empty content overwrote accumulated deltas [`packages/ui/src/components/ChatInterface/index.tsx`] — fixed by preserving existing assistant content when final response content is empty and adding regression coverage.
- [x] [Review][Patch] Recovery cleanup could discard active sessions during state transitions [`packages/ui/src/components/ChatInterface/index.tsx`] — fixed by moving cleanup to explicit recovery lifecycle paths plus unmount-only ref cleanup.
- [x] [Review][Patch] SSE `message_start` and malformed JSON handling were incomplete [`apps/web/src/lib/chat.ts`] — fixed parser support for `message_start`, locale carry-forward, and bounded error events for invalid stream data.
- [x] [Review][Patch] Excel/JSON file context mapping drifted from backend schema [`apps/web/src/lib/chat.ts`] — fixed `sheets`, `sheet_count`, and `top_level_keys` mapping with regression tests.
- [x] [Review][Patch] Stream terminal state could turn `error` into `incomplete` [`packages/ui/src/components/ChatInterface/index.tsx`] — fixed terminal-state handling so error and complete remain final.
- [x] [Review][Patch] Pending file and what-if lifecycle had drift risk [`packages/ui/src/components/ChatInterface/index.tsx`] — fixed per-request file clearing, explicit what-if selection, clear-history cleanup, and focused tests.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:1593` 定义 Story 4.C.6：`ChatInterface Tier 2 Component (UX-DR1)`。
- `_bmad-output/planning/epics.md:1595` 源 AC：Given `packages/ui ChatInterface` stub Sprint 0 / When 业务 Epic 4 使用 / Then full implementation 含 history / streaming / file picker / a11y。
- `_bmad-output/planning/epics.md:191` 将 `ChatInterface` 列为 Tier 2 component。
- `_bmad-output/planning/epics.md:425` 定义 Epic 4.C UX-DR：`ChatInterface / FilePicker / WhatIfPrompt` 与 real-time updates。
- `_bmad-output/planning/architecture.md:3349` 起定义 WCAG 2.1 AA、Standard a11y Hook Wrapper 与 axe-core CI baseline。
- `packages/ui/src/index.ts` 目前声明 Tier 2/Tier 3 components 在 business Epic stories 中实现；当前没有 `ChatInterface` 文件。
- Source AC 提到 Sprint 0 stub，但当前仓库 reality 是没有 `ChatInterface` stub；本 story 要新增而不是填充既有文件。

### Current Repository Reality

- `packages/ui` 是 React 18 + Tailwind v3 + lucide + Radix Dialog 单源 UI 包，测试环境为 Vitest + happy-dom + jest-axe。
- `packages/ui` 已安装 `@testing-library/user-event`，ChatInterface 的 keyboard/focus tests 可优先用 user-event 而不是低层 `fireEvent`。
- `packages/ui/src/components/FilePicker/index.tsx` 已有 5MB 默认、`.csv,.xlsx,.json` 默认 accept、`onFile`、`onReject` 和 `useA11y`。
- `packages/ui/src/components/ConfirmationModal/index.tsx` 已提供 Radix Dialog、focus trap、ESC close、custom body/confirm/cancel labels。
- `packages/ui/src/components/ConfidenceLabel/index.tsx` 已可展示 Critic confidence；ChatInterface 可复用或用相同 labels/tokens。
- `apps/web/src/lib/chat-file-context.ts` 已输出 bounded `ChatFileContextPayload`，字段使用 snake_case，可直接进 Chat API `file_contexts[]`。
- `apps/web/src/lib/chat-file-context-recovery.ts` 已输出 partial recovery actions/session/result；session raw rows 在 private fields，`toJSON()` 仅安全摘要。
- `apps/chat-service/src/chat_service/main.py` 已有受保护 JSON route `POST /v1/chat/internal-beta/messages` 和 SSE route `POST /v1/chat/internal-beta/messages/stream`。
- Internal beta headers 为 `X-Internal-Beta-Tenant`、`X-Internal-Beta-User`、`X-Internal-Beta-Token`；授权失败在 body validation 前返回 sparse 404。
- SSE events 当前为 heartbeat、`message_start`、`content_delta`、`done`，invalid cursor 可返回 bounded `error` event。
- `apps/web/src/lib/api.ts` 尚无 Chat client；现有 API helper pattern 使用 `NEXT_PUBLIC_*_SERVICE_URL` + fetch + typed error。
- `apps/web` component tests 可通过 `// @vitest-environment happy-dom` 覆盖 page UI，lib tests 默认 node。
- `apps/web` 没有 `@testing-library/user-event` 依赖；web page tests 若不新增 dev dependency，应使用现有 `fireEvent`。

### Previous Story Intelligence

- 4.C.1 `model_preview` 是 response-only；confirm/edit/cancel 是 client descriptors，不是 backend mutation，不可触发 Solver/Billing。
- 4.C.2 SSE 是 protected POST route；browser native `EventSource` 不能发送 POST body，前端必须用 fetch stream parser 或 JSON fallback。
- 4.C.3 文件上下文是 browser-side bounded metadata；不允许 multipart/base64/raw rows/S3/upload endpoint。
- 4.C.4 what-if 使用 client-submitted bounded `what_if_context`；没有 server-side conversation persistence。
- 4.C.5 CSV partial recovery 是 helper/state contract；4.C.6 才负责把它接进 visible Chat UI。
- 3.11/4.C.5 的 privacy lesson：raw rows/cells/File objects/recovery session 不应进入 serialized UI state、URL、storage、logs 或 snapshots。

### Implementation Guidance

- 推荐 `ChatInterface` props 形状：
  - `ariaLabel: string`
  - `messages?: ChatInterfaceMessage[]`
  - `onSendMessage(request) => Promise<{mode:"complete"; response: ChatInterfaceResponse} | {mode:"stream"; events: AsyncIterable<ChatInterfaceStreamEvent>}>`
  - `onSelectFile(file) => Promise<ChatInterfaceFileSelectionResult>`
  - `onReplaceFailedRows?(recoveryId, replacementCsv) => Promise<ChatInterfaceFileSelectionResult>`
  - `buildWhatIfContext?(message) => ChatInterfaceWhatIfContext | null`
  - optional `initialMessages`, `locale`, `disabled`, `className`
- 让 component 内部持有 uncontrolled history 即可；如果实现 controlled props，必须避免双状态漂移。
- Streaming adapter 返回 `AsyncIterable<ChatInterfaceStreamEvent>`；避免 callback controls 在 component 内部绕过 React state machine。
- Web helper 可以把 backend JSON response normalize 为 `ChatInterfaceResponse`，把 SSE `content_delta/done/error` normalize 为 `ChatInterfaceStreamEvent`。
- SSE parser 应按空行分块，支持 `data:` 多行拼接；heartbeat comment 忽略；JSON parse error 转 bounded error event。
- Web helper 应生成 `client_request_id`，不要让 UI component 用 draft message/filename 拼 id。
- Normalization 必须把 JSON full response 和 SSE done 都落到同一 `ChatInterfaceResponse` shape；SSE 中缺少完整 model actions 时，UI 只能显示 `preview_id/status` 和“完整模型动作不可用”类 bounded fallback，不伪造 actions。
- Model preview panel只显示 bounded fields：status、task type、confidence、sandbox status、actions、最多 10 条 validation errors；不要显示 full generated code。
- What-if affordance 可作为 assistant message 上的按钮，将 bounded context带入下一次 request；没有 ready/usable model preview 时禁用或隐藏。
- Console page token input 用 password field + React state/ref；不要使用 `sessionStorage` pattern，因为 internal beta token 不是 user JWT。

### Boundary Rules

- No public Chat route.
- No public `/v1/chat/stream`.
- No backend route/schema changes by default.
- No Solver/Prediction submission.
- No Billing/Credits estimate, reserve or charge.
- No DB/Redis/outbox/conversation persistence.
- No localStorage/sessionStorage/cookie persistence for internal beta token, messages, files or recovery sessions.
- No multipart/base64/raw file upload endpoint.
- No S3/object storage.
- No api-gateway streaming proxy.
- No WebSocket.
- No native EventSource for POST Chat.
- No service worker/background sync.
- No live provider SDK in web.
- No new runtime dependency unless an existing test-proven capability gap blocks implementation.
- No new dev dependency unless focused tests prove existing Testing Library + happy-dom cannot cover the behavior.
- No raw user transcript outside in-memory UI history, no raw file rows/cells/bytes, no recovery session serialization, no provider payload, prompt, hidden reasoning, full generated code, sandbox output, traceback, host path, queue payload, charge/optimization/prediction id or callback URL in UI state snapshots, response rendering or tests.

### Test / Validation Notes

Expected commands:

```powershell
pnpm --filter @opticloud/ui exec vitest run src/components/ChatInterface
pnpm --filter @opticloud/ui test:a11y
pnpm --filter @opticloud/ui typecheck
pnpm --filter @opticloud/web exec vitest run chat
pnpm --filter @opticloud/web exec vitest run chat-file-context
pnpm --filter @opticloud/web typecheck
git diff --check
```

RED expectation: focused tests should fail before implementation because `packages/ui` does not export `ChatInterface`, `apps/web/src/lib/chat.ts` does not exist, and `/console/chat` does not exist.

## Story Review Rounds

### Round 1 - Boundary / Ownership Review (2026-05-30)

Findings applied:
- 初稿允许 `onSendMessage(request, controls)` 这类 callback-control API，会让 adapter 在组件内部直接 push 状态，导致 streaming 状态机不可审计。已改为 `complete | stream` discriminated union，其中 stream 只暴露 `AsyncIterable<ChatInterfaceStreamEvent>`。
- 初稿没有明确 `ChatInterface` 不得接触 tenant/user/token/header/service URL/raw SSE text。AC1 现已将这些限制在 web adapter/page 的短生命周期局部变量中。
- CSV recovery 初稿说 UI 通过 adapter 提交 replacement，但未禁止保存 recovery session object。AC3 现要求 UI 只保存 `recoveryId` 和 bounded invalid-row 摘要。
- What-if 初稿容易让 UI package 依赖 chat-service schema。AC5 和 Implementation Guidance 现要求 UI 只把 bounded message metadata 交给 `buildWhatIfContext`，真实 request shape 由 web helper 构造。
- Source AC 提到 Sprint 0 stub，但仓库没有 stub。Dev Notes 现明确本 story 是新增 `ChatInterface`。

Status: PASS after fixes.

### Round 2 - Data Consistency / Privacy Review (2026-05-30)

Findings applied:
- Assistant lifecycle 原本只描述 pending/streaming/done，未要求异常路径收敛；AC2 现固定 `pending -> streaming -> complete` 或 `pending/streaming -> error/incomplete`，避免 orphan loading message。
- `client_request_id` 原本可由 component 生成，容易用 draft/raw message/filename 派生。AC5 现要求 web helper 生成无 PII id，component 只传 bounded request。
- CSV recovery session 的存放位置未闭合。AC3 和 Task 4 现要求 web adapter 用 module-local Map 暂存，并在 success/retry/cancel/unmount/clear 后删除，UI 只持有 `recoveryId`。
- What-if 原本允许最近 assistant message，未排除 pending/error。AC5 现要求只能来自最近 complete assistant message。
- 发送失败和 clear history 的上下文规则未闭合。AC5 现明确失败可保留 pending files 供重试，clear 必须清理 pending files、recovery modal、draft what-if 和 local confirmation state。
- SSE done 不含完整 `model_preview.actions`，初稿可能让 UI 伪造 actions。Implementation Guidance 现要求 normalization 同一 shape，但 SSE 只有 id/status 时只能显示 bounded fallback，不伪造 actions。

Status: PASS after fixes.

### Round 3 - Dependency / A11y / Test Closure Review (2026-05-30)

Findings applied:
- 验证命令原写成 `pnpm --filter @opticloud/ui test -- ChatInterface`，在当前 package script 下 filter 语义不够明确。已改为 direct `pnpm --filter @opticloud/ui exec vitest run src/components/ChatInterface`。
- ChatInterface 是 Tier 2，不应塞进 `Tier1.a11y.test.tsx` 并污染 Tier 1 描述。Task 3 现要求新增 ChatInterface/Tier 2 专用 a11y test。
- `apps/web` page tests 默认 node 环境，若忘记注释会访问 DOM 失败。AC7 现要求 page tests 加 `// @vitest-environment happy-dom`。
- UI 包已有 `@testing-library/user-event`，web 包没有。Dev Notes 现要求 packages/ui keyboard/focus tests 优先用 user-event，web page tests 不新增依赖时用 fireEvent。
- 依赖闭环原本只禁止 runtime dependency，未限制 dev dependency。Boundary Rules 现要求没有 test-proven gap 不新增 dev dependency。

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-30 - Initial draft story created from Epic 4.C.6 source AC, existing `packages/ui` component/test patterns, 4.C.1-4.C.5 backend/frontend contracts, and current sprint status.
- 2026-05-30 - Story review round 1 applied boundary/ownership fixes: typed stream union, no secret/header/service URL in UI package, recoveryId-only UI state, web-owned what-if shape, and no-stub repo reality.
- 2026-05-30 - Story review round 2 applied data/privacy fixes: assistant lifecycle closure, web-owned client_request_id, module-local recovery session map cleanup, complete-message-only what-if derivation, clear-history context cleanup, and no fake model actions for SSE-only done.
- 2026-05-30 - Story review round 3 applied dependency/a11y/test closure fixes: direct Vitest commands, Tier 2 a11y isolation, happy-dom page tests, existing test dependency boundaries, and no unproven new deps.
- 2026-05-30 - Implemented RED/GREEN ChatInterface public API, bounded UI types, state machine, FilePicker/recovery UI, local model actions, explicit what-if selection, and Storybook states.
- 2026-05-30 - Implemented web internal beta Chat adapter with JSON/SSE helpers, fetch POST stream parser, file context/recovery adapters, request normalization, and `/console/chat` dogfood page.
- 2026-05-30 - Post-implementation code review fixed six findings: stream done empty content, recovery cleanup lifecycle, SSE message_start/malformed data, Excel/JSON backend context mapping, stream terminal-state closure, and pending file/what-if lifecycle drift.
- 2026-05-30 - Verification passed: `pnpm --filter @opticloud/ui exec vitest run src/components/ChatInterface`; `pnpm --filter @opticloud/web exec vitest run chat`; `pnpm --filter @opticloud/ui test:a11y`; `pnpm --filter @opticloud/ui typecheck`; `pnpm --filter @opticloud/web typecheck`; `pnpm --filter @opticloud/ui test`; `pnpm --filter @opticloud/web test`; `git diff --check`.

### Completion Notes List

- Added adapter-driven `ChatInterface` Tier 2 component with bounded public contracts and no direct web/backend/secret ownership in `packages/ui`.
- Added in-memory chat history, composer, streaming lifecycle, bounded error/incomplete handling, FilePicker integration, CSV partial recovery modal, local-only model preview actions, and explicit what-if context selection.
- Added web internal beta adapter/helper and `/console/chat` dogfood page using POST JSON/SSE endpoints, transient credentials, fetch stream parsing, JSON fallback, and file context/recovery adapters.
- Added focused UI/web/page/a11y coverage, updated `test:a11y` to include ChatInterface, and ran full relevant UI/web validation.

### File List

- `_bmad-output/stories/4-c-6-chat-interface-tier2.md`
- `_bmad-output/stories/sprint-status.yaml`
- `packages/ui/package.json`
- `packages/ui/src/index.ts`
- `packages/ui/src/components/ChatInterface/index.tsx`
- `packages/ui/src/components/ChatInterface/index.test.tsx`
- `packages/ui/src/components/ChatInterface/index.a11y.test.tsx`
- `packages/ui/src/components/ChatInterface/index.stories.tsx`
- `apps/web/src/lib/chat.ts`
- `apps/web/src/lib/chat.test.ts`
- `apps/web/src/app/console/chat/page.tsx`
- `apps/web/src/app/console/chat/page.test.tsx`

## Change Log

- 2026-05-30 - Created initial draft story for required three-round pre-implementation adversarial review.
- 2026-05-30 - Story review round 1 tightened UI/web/backend ownership boundaries.
- 2026-05-30 - Story review round 2 tightened history/context/privacy data consistency.
- 2026-05-30 - Story review round 3 closed dependency, a11y and validation-command gaps; story moved to ready-for-dev.
- 2026-05-30 - Implemented ChatInterface Tier 2 UI package component, web internal beta adapter, and `/console/chat` integration.
- 2026-05-30 - Completed post-implementation adversarial code review, applied six fixes, passed focused and full relevant validation, and moved story to done.
