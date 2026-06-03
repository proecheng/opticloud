---
story_key: 8-b-1-aigc-filter-invoke
epic_num: 8
story_num: B.1
epic_name: AIGC Filter + Rate Limit + Error Codes RFC 7807
status: done
baseline_commit: 32ff75a2894d561b9e9a50fc71beda15e2442e8a
priority: High
type: compliance evidence closure
created_by: bmad-create-story
created_at: 2026-06-03
sources:
  - _bmad-output/planning/epics.md (Epic 8.B / Story 8.B.1)
  - _bmad-output/planning/prd.md (FR O5)
  - _bmad-output/planning/architecture.md (Q2 / P34 / C11)
  - _bmad-output/planning/ux-design-specification.md (AIGC watermark aria-label)
  - _bmad-output/stories/m3-4-aigc-watermark-module.md
  - _bmad-output/stories/m3-4b-aigc-filter-contract-test.md
  - _bmad-output/stories/4-b-5-aigc-filter-invoke.md
  - apps/web/src/lib/chat.ts
  - packages/ui/src/components/ChatInterface/index.tsx
---

# Story 8.B.1 - AIGC Filter 调用证据闭环

Status: done

## Story

**作为** Chat internal beta 合规与前端契约 owner，
**我希望** Web adapter、Console Chat 页面和 `ChatInterface` UI 保留并展示后端 `language_preview.aigc_watermark` / SSE `aigc_watermark_trace_id` 证据，
**从而** Story M3.4/4.B.5 已完成的 AIGC filter 调用不会在用户可见 NL 前端出口被丢弃，并且 FR O5 的 aria-label 水印链路在 JSON 与 SSE fallback 中闭环。

## Context

Story M3.4 已实现唯一 AIGC filter/watermark 模块 `packages/shared-py/aigc_filter`；Story M3.4b 已锁定模块 contract；Story 4.B.5 已在 `chat-service` 的 `language_preview.summary` 上调用 `aigc_filter.filter(..., tier="strict")`，并通过 `LanguagePreview.aigc_watermark` 暴露 bounded preview。当前缺口不在后端过滤器，而在前端 TypeScript/UI 消费链路：

- `apps/web/src/lib/chat.ts` 将 `language_preview.summary` 映射为 `ChatInterfaceResponse.content`，但丢弃 `language_preview.aigc_watermark`。
- SSE `done` payload 已包含 `aigc_watermark_trace_id`，但 `normalizeStreamDone(...)` 未保留。
- `packages/ui/src/components/ChatInterface/index.tsx` 的 response/message 类型没有 AIGC watermark 字段，UI 不渲染后端提供的 visible marker、aria label 或 trace evidence。

因此 8.B.1 是 Epic 8.B 的横切合规证据闭环：消费并展示既有后端证据，不重新实现 AIGC 规则，也不声称 AIGC 备案完成或 public Chat 已开放。

## Scope

1. 扩展 `ChatInterfaceResponse` / `ChatInterfaceMessage`，携带 bounded AIGC watermark evidence。
2. 扩展 `apps/web/src/lib/chat.ts`：
   - JSON response 从 `language_preview.aigc_watermark` 映射完整证据。
   - SSE done 从 `aigc_watermark_trace_id` 映射 trace-only 证据。
   - `safeText(...)` 仍过滤 secret/provider/prompt 等敏感文本，但不得过滤正常 AIGC visible marker。
3. 扩展 `ChatInterface` assistant message 渲染：
   - 使用后端 `visibleMarker` 作为可见标识。
   - 使用后端 `ariaLabel` 作为 A11y label。
   - 展示 bounded trace/provider/module/tier evidence；SSE trace-only 时只展示 trace，不伪造 provider/module/tier。
4. 扩展 Console Chat 流式与 JSON fallback 测试，证明证据不会在 fallback 中丢失，且 token 仍不写 storage。
5. 增加静态/单元漂移 guard，防止在 web/UI 中复制 AIGC filter 规则或本地生成 watermark metadata。

## Out Of Scope

- 不修改 `packages/shared-py/aigc_filter`、contract snapshot、filter 规则、watermark encoding、detector 或 red-team/benign 数据集。
- 不在 web、UI、chat-service 或 critic-service 复制敏感词规则、水印编码、zero-width detector 或 provider marker 逻辑。
- 不新增 runtime dependency、环境变量、LLM moderation/provider call、备案状态读取/更新或备案号字段。
- 不新增 public `/v1/chat`、public Chat UI、公开 AIGC 合规页面、真实 AIGC 备案 surface、DB/Redis/outbox/notification/billing/Solver side effect。
- 不改变 internal beta gate：`aigc_gate.status` 仍为 `filing_pending`，`public_surface` 仍为 `hidden`。
- 不让 SSE content delta 携带 zero-width metadata；streaming 已由后端剥离 zero-width，前端只保留 done trace evidence。

## Acceptance Criteria

1. 前端类型保留 AIGC watermark evidence。
   - `ChatInterfaceResponse` 增加 `aigcWatermark?: ChatInterfaceAigcWatermarkEvidence`。
   - `ChatInterfaceMessage` 在 assistant complete/stream done 后保存同一 evidence。
   - Evidence 至少支持完整 JSON 字段：`ariaLabel`、`visibleMarker`、`traceId`、`provider`、`moduleVersion`、`tier`、`blocked`、`reasonCodes`、`metadata`。
   - Evidence 支持 SSE trace-only 字段：`traceId`，不得伪造缺失的 provider/module/tier。

2. JSON response normalization 不丢失后端证据。
   - `normalizeInternalBetaChatResponse(...)` 从 `payload.language_preview.aigc_watermark` 映射 `aigcWatermark`。
   - `content` 继续来自 `language_preview.summary`，正常 `"本回答由 AI 生成，仅供参考"` marker 不得被 `safeText` 误判为泄漏。
   - `reasonCodes`、`metadata` 必须 bounded；遇到 secret-like/provider payload/prompt/traceback/host path 时过滤或丢弃，不传入 UI。
   - `aigcGate` 仍原样表示 filing pending/hidden，不塞入 watermark evidence。

3. SSE done normalization 不丢失 trace evidence。
   - `normalizeStreamDone(...)` 读取 `aigc_watermark_trace_id` 并映射为 `aigcWatermark.traceId`。
   - SSE done 如果没有完整 `language_preview.aigc_watermark`，只保留 trace-only evidence。
   - `content_delta` 继续只拼接用户可见文本，不恢复或构造 zero-width metadata。
   - `message_start` locale 传递到 done 的既有行为不回退。

4. UI 渲染 AIGC evidence 且保持 A11y。
   - Assistant message complete 后展示后端 visible marker。
   - Evidence 区域带 `aria-label`，完整 JSON path 使用后端 `ariaLabel`；trace-only path 使用 bounded fallback aria label。
   - 完整 evidence 显示 trace id、provider、module version、tier、blocked 状态；trace-only path 只显示 trace id。
   - 证据区域不能遮挡 message content、model preview、file preview、what-if preview；移动端文本必须可换行。

5. Console Chat JSON fallback 与 streaming path 闭环。
   - 流式成功时，UI 保存并显示 `aigc_watermark_trace_id`。
   - 流式失败转 JSON fallback 时，UI 保存并显示完整 `aigcWatermark`。
   - internal beta token 仍不得写入 local/session storage。

6. Drift guard 防止重复实现 filter。
   - Web/UI 代码不得出现 `aigc_filter.filter` 行为复刻、中文危险词规则集、zero-width encoder/decoder、`opticloud-aigc-filter` 本地常量生成或本地 trace id 生成。
   - 允许 adapter 仅消费后端给出的 `provider` 字符串并作为 bounded text 显示。
   - 测试需覆盖 web adapter 不生成 provider/module/tier 默认值。

7. Regression coverage 和质量门禁。
   - RED tests 先写并确认失败：adapter 丢失 JSON watermark、SSE trace、UI 不显示 evidence。
   - Focused tests 覆盖 `apps/web/src/lib/chat.test.ts`、`packages/ui/src/components/ChatInterface/index.test.tsx`、`apps/web/src/app/console/chat/page.test.tsx`。
   - 跑 `pnpm --filter @opticloud/web test -- chat`、`pnpm --filter @opticloud/ui test -- ChatInterface`、`pnpm --filter @opticloud/web typecheck`、`pnpm --filter @opticloud/ui typecheck`、相关 package tests、`git diff --check`。

8. Workflow 和 GitHub 闭环。
   - 本 story 记录三轮 pre-implementation adversarial review，并在每轮后修订。
   - 实现开始后 sprint status 置为 `in-progress`；本地实现完成和初步门禁通过后置为 `code-review`。
   - Post-implementation code review 必须覆盖边界问题、漂移问题、数据一致性、依赖一致性、是否闭环、A11y、SSE/JSON fallback、no-leak、no duplicate filter 和测试证据。
   - PR merge、远端分支删除、本地 `main` 同步完成后，才把 story 与 sprint status 置为 `done` 并提交/推送状态同步。

## Tasks / Subtasks

- [x] T1: 扩展 UI 类型与渲染 (AC: 1, 4)
  - [x] 增加 `ChatInterfaceAigcWatermarkEvidence` 类型。
  - [x] `ChatInterfaceMessage` 和 `applyResponse(...)` 保存 `aigcWatermark`。
  - [x] Assistant message 渲染 visible marker、aria label、trace/provider/module/tier/blocked evidence。

- [x] T2: 扩展 web adapter normalization (AC: 2, 3, 6)
  - [x] JSON path 映射 `language_preview.aigc_watermark`。
  - [x] SSE done path 映射 `aigc_watermark_trace_id` 为 trace-only evidence。
  - [x] 添加 bounded text/list/metadata helpers，避免 secret/provider payload/prompt 泄漏。
  - [x] 确认 `safeText` 不过滤正常 AIGC visible marker。

- [x] T3: RED/GREEN tests (AC: 2-7)
  - [x] 更新 `apps/web/src/lib/chat.test.ts`。
  - [x] 更新 `packages/ui/src/components/ChatInterface/index.test.tsx`。
  - [x] 更新 `apps/web/src/app/console/chat/page.test.tsx`。
  - [x] 增加 no duplicate filter/static drift guard。

- [x] T4: 审查、门禁和 GitHub 同步 (AC: 7, 8)
  - [x] 执行 post-implementation code review 并修复 findings。
  - [x] 跑 focused 与必要 package gates。
  - [x] Commit、push、创建 PR、等待 CI、merge、删除远端分支、同步 local main。
  - [x] 合并同步后更新 story/sprint status 为 done 并推送状态同步。

## Dev Notes

### Current Repository Reality

- `packages/shared-py/aigc_filter/__init__.py` 已提供唯一 filter/watermark 实现：`filter(...)`、`detect_watermark(...)`、`AIGC_ARIA_LABEL`、`AIGC_VISIBLE_MARKER`、`PROVIDER_MARKER`。
- `apps/chat-service/src/chat_service/aigc_watermark.py` 已只调用 `aigc_filter.filter(summary, tier="strict")` 并生成 `AigcWatermarkPreview`。
- `apps/chat-service/src/chat_service/schemas.py` 已要求 `LanguagePreview.summary` 含 visible marker 与 detectable zero-width metadata，且 `aigc_watermark.trace_id/provider/module_version` 与 detector 一致。
- `apps/chat-service/src/chat_service/streaming.py` 已在 `build_stream_events(...)` 中剥离 content delta 的 zero-width metadata，并在 done 事件输出 `aigc_watermark_trace_id`。
- `apps/web/src/lib/chat.ts` 当前丢弃 `language_preview.aigc_watermark` 和 SSE `aigc_watermark_trace_id`。
- `packages/ui/src/components/ChatInterface/index.tsx` 当前 response/message 类型没有 `aigcWatermark` 字段，assistant bubble 不展示 AIGC evidence。

### Implementation Guidance

- 建议 evidence 类型保持前端语义，不直接暴露 backend snake_case：
  - `ariaLabel?: string`
  - `visibleMarker?: string`
  - `traceId: string`
  - `provider?: string`
  - `moduleVersion?: string`
  - `tier?: "strict" | "loose"`
  - `blocked?: boolean`
  - `reasonCodes?: string[]`
  - `metadata?: Record<string, boolean | string | number | null>`
- `normalizeAigcWatermark(...)` 只能做 shape mapping 和 bounded/no-leak 过滤；不要生成 trace id、provider、module version 或 visible marker。
- UI 渲染可用一个小型 `<div data-testid="chat-aigc-watermark">` 放在 message content 后、model preview 前。
- 对 SSE trace-only，建议显示 `trace trc_xxx`，并使用 `aria-label="本回答由 AI 生成，仅供参考"` 的 fallback；不要显示 provider/module/tier。
- 若 `response.content` 已包含 visible marker，UI evidence 区域仍可显示同一 marker 作为结构化合规证据；避免为了去重而修改后端 summary。

### Boundary Rules

- No duplicate filter implementation.
- No shared module mutation.
- No backend AIGC filter rewrite.
- No public Chat route or public compliance claim.
- No AIGC filing status read/update.
- No new dependency or env var.
- No token/header/prompt/provider payload/traceback/host path leakage in UI.
- No local zero-width metadata generation or decoding in web/UI.

### Suggested Commands

```powershell
pnpm --filter @opticloud/web test -- chat
pnpm --filter @opticloud/ui test -- ChatInterface
pnpm --filter @opticloud/web typecheck
pnpm --filter @opticloud/ui typecheck
git diff --check
```

## Definition Of Done

- Story has passed 3 pre-implementation adversarial review rounds with revisions recorded.
- Web adapter preserves JSON `language_preview.aigc_watermark` and SSE `aigc_watermark_trace_id`.
- ChatInterface stores and renders AIGC watermark evidence with bounded visible text and a11y label.
- Console Chat streaming and JSON fallback preserve evidence and keep token storage boundary.
- No duplicate AIGC filter or watermark implementation exists in web/UI.
- Post-implementation code review completed and findings fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after PR merge, remote branch deletion, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-b-1-aigc-filter-invoke`.
- Baseline commit: `32ff75a2894d561b9e9a50fc71beda15e2442e8a`.
- Story creation used Epic 8.B / FR O5 / Architecture Q2-P34-C11 / UX AIGC watermark a11y / M3.4 / M3.4b / 4.B.5 implementation reality.
- Customization resolver script was absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base skill customization files, found no project-level overrides, and found no `project-context.md`.
- Pre-implementation story review rounds completed before development; story and sprint status moved to `ready-for-dev`.
- 2026-06-03 - Implementation started; story and sprint status moved to `in-progress`.
- 2026-06-03 - RED confirmed: focused web/ui tests failed because adapter/UI did not preserve or render `aigcWatermark`.
- 2026-06-03 - GREEN implementation added frontend AIGC watermark evidence types, JSON/SSE normalization, assistant-message evidence rendering, and Console Chat fallback preservation.
- 2026-06-03 - Post-implementation review completed manually without subagents per user constraint; patched trace-only UI to avoid fabricated marker/provider/module/tier, and added UI-side static drift guard.
- 2026-06-03 - Local validation passed: `pnpm --filter @opticloud/web test -- chat` (26 tests), `pnpm --filter @opticloud/ui test -- ChatInterface` (15 tests), `pnpm --filter @opticloud/web typecheck`, `pnpm --filter @opticloud/ui typecheck`, `pnpm --filter @opticloud/web test` (43 files / 209 tests), `pnpm --filter @opticloud/ui test` (18 files / 106 tests), and `git diff --check`.
- 2026-06-03 - GitHub sync completed: PR #152 passed CI (`changes`, `lint`, `ts-typecheck`, `e2e`, `chromatic`, `matrix-detect`, `build-and-sbom (auth-service)`, `gtm-toolkit-validation`), merged to `main` at `e774394f0c83f2f6f34011996eb0353512d21fad`, remote branch `codex/8-b-1-aigc-filter-invoke` deleted, and local `main` synced before marking story done.

### Completion Notes List

 - Added `ChatInterfaceAigcWatermarkEvidence` and exported it from `@opticloud/ui`.
 - `ChatInterface` now stores `response.aigcWatermark` on assistant messages and renders bounded evidence with an accessible AIGC label.
 - `apps/web/src/lib/chat.ts` now maps JSON `language_preview.aigc_watermark` into full frontend evidence and maps SSE `aigc_watermark_trace_id` into trace-only evidence.
 - Trace-only streaming evidence intentionally displays only the trace id and fallback aria label; it does not fabricate provider, module version, tier, or visible marker.
 - Added tests covering JSON preservation, SSE trace-only preservation, Console Chat stream/fallback display, token storage non-regression, and static no-duplicate-filter guards for both web adapter and UI source.

### Post-Implementation Code Review

Outcome: Approved after patch.

Findings fixed:
- [x] [Review][Patch] UI-side drift guard was missing; AC6 covers both Web and UI. Added a static test for `packages/ui/src/components/ChatInterface/index.tsx` to prevent local AIGC filter, provider marker constant, zero-width, or encoder/decoder logic.
- [x] [Review][Patch] Trace-only SSE evidence initially rendered a generic AIGC evidence label, which could imply complete metadata. Updated UI to omit visible marker when absent and added tests that trace-only evidence does not show provider/module/tier.

Residual risk: frontend only displays backend-provided evidence and cannot verify zero-width metadata itself by design; backend detector consistency remains covered by Story 4.B.5 and M3.4/M3.4b tests.

### File List

- `_bmad-output/stories/8-b-1-aigc-filter-invoke.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/src/app/console/chat/page.test.tsx`
- `apps/web/src/lib/chat.test.ts`
- `apps/web/src/lib/chat.ts`
- `packages/ui/src/components/ChatInterface/index.test.tsx`
- `packages/ui/src/components/ChatInterface/index.tsx`
- `packages/ui/src/index.ts`

## Change Log

- 2026-06-03 - Story created for 8.B.1 AIGC filter evidence closure.
- 2026-06-03 - Completed 3 pre-implementation adversarial review rounds; story marked ready for development.
- 2026-06-03 - Implementation started; story and sprint status moved to in-progress.
- 2026-06-03 - Implemented web/UI AIGC watermark evidence closure, completed post-implementation review patches, passed local gates, and moved story/sprint status to code-review pending GitHub sync.
- 2026-06-03 - PR #152 passed GitHub CI, merged to main, remote branch deleted, local main synced; story and sprint status marked done.

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary And Duplicate-Implementation Review

Findings:

1. Story 4.B.5 already implemented backend Chat AIGC filter invocation; reimplementing it in 8.B.1 would duplicate scope and risk drift.
2. M3.4/M3.4b define `packages/shared-py/aigc_filter` as the physical single implementation and contract owner; web/UI must not copy rules or detector logic.
3. Epic 8.B wording says "user-visible NL output"; the current uncovered user-visible exit is the front-end consumer path, not a new backend route.
4. AIGC watermark evidence could be confused with AIGC filing completion; the internal beta gate must remain hidden/pending.

Revision after Round 1:

- Re-scoped story to "frontend/UI evidence closure" instead of backend filter implementation.
- Added explicit out-of-scope for shared module mutation, backend rewrite, public Chat,备案状态, dependencies, and public compliance claims.
- Added AC6 no-duplicate-filter drift guard.

### Round 2 - Drift, Data Consistency, And SSE/JSON Review

Findings:

1. JSON response carries full `language_preview.aigc_watermark`; SSE done only carries `aigc_watermark_trace_id`. Treating both as identical would fabricate missing metadata.
2. `safeText(...)` could accidentally filter the normal AIGC visible marker if the leak pattern is too broad.
3. SSE content deltas intentionally strip zero-width metadata; the frontend should not reconstruct it.
4. `aigc_gate` and `aigc_watermark` represent different concepts and must not be merged.

Revision after Round 2:

- Added separate full JSON evidence and SSE trace-only evidence requirements.
- Required `safeText` marker-preservation test.
- Added "no local zero-width generation/decoding" boundary and explicit `aigcGate` non-merging rule.
- Added tests for locale propagation and stream done evidence preservation.

### Round 3 - Dependency, A11y, Closure, And GitHub Lifecycle Review

Findings:

1. A new Mermaid/tooltip/a11y package is unnecessary; UI can render bounded text using existing components and styles.
2. Evidence UI can become inaccessible if the visible marker is only visual text without an aria label.
3. Console Chat fallback could pass tests for content while silently dropping watermark evidence.
4. The user-required lifecycle forbids marking story done before code review, GitHub CI, PR merge, remote branch deletion, and local main sync.

Revision after Round 3:

- Required no new dependency/env var.
- Added explicit aria-label and mobile wrapping requirements.
- Added Console Chat JSON fallback evidence test and token-storage non-regression.
- Added workflow AC8 and DoD gating final `done` on GitHub merge/sync.
