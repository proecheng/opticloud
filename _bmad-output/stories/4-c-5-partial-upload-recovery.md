# Story 4.C.5: Partial-upload-recovery contract for Chat CSV context

Status: done

## Story

作为使用 Chat 上传 CSV 的业务用户，
我希望当 CSV 只有部分行无法解析时，可以选择“仅替换失败行 / 全部重试 / 取消”，
以便修正失败记录后继续把安全、有限的文件上下文交给 Chat，而不是上传原始文件或跳过坏行。

## Acceptance Criteria

1. 新增 Chat CSV partial-upload-recovery 前端契约，限定在浏览器侧完成。
   - 只覆盖 CSV partial row recovery；Excel/JSON 继续走 4.C.3 的 metadata parser，不在本 story 增加恢复流。
   - 不新增 public Chat route、完整 ChatInterface、后端上传 endpoint、multipart/base64、S3、DB/Redis/outbox persistence、Solver/Prediction submission 或 Billing coupling。
   - 成功结果必须仍是 4.C.3 的 `ChatFileContextPayload`，可直接作为 Chat API body 的 `file_contexts[]`。
2. CSV 部分失败必须 fail closed，并返回 bounded、modal-ready 的恢复状态。
   - Chat 通用 CSV 只做结构性校验：header 必须存在；每个非空数据行解析后的 cell 数必须与 header cell 数一致；本 story 不把任意业务字段（例如销量、日期）强制解释为数值或日期。
   - 行级错误必须包含 `row_number`、`data_row_number`、`field_path`、`constraint`、`remediation_hint_key`，不得包含 raw cell value、raw row、raw bytes、API key、token、host path、prompt、provider payload、generated code、sandbox output、charge/optimization/prediction id。
   - 恢复状态必须暴露三个动作及中文标签：`replace_failed_rows` / `仅替换失败行`、`retry_all` / `全部重试`、`cancel` / `取消`。
   - invalid row 列表最多暴露 20 条；同时保留 `invalid_row_count` 总数摘要，不能把大文件错误逐行无限放入 React state 或测试快照。
3. “仅替换失败行”必须维护源行身份并重新校验全量 canonical dataset。
   - replacement 可是 CSV 行片段或带 header 的 CSV；replacement 数据行数必须等于当前失败行总数（不是只等于前 20 条摘要）。
   - replacement 可以带 `row_number`/`rowNumber`/`source_row`/`源行号`；带行号时必须匹配原失败源行，重复或未知源行号必须 fail closed。
   - 多个失败行时，若任一 replacement 不带源行号则 fail closed；单个失败行可按当前失败顺序替换。
   - replacement 行必须满足原始 header 列数；如果带 header，业务列必须与原始 header 兼容，额外只允许源行号列。
   - 替换后必须重新校验全量 CSV；仍有任何错误时不得产生 `file_contexts`，也不得静默跳过坏行并声称成功。
4. “全部重试”和“取消”必须闭环。
   - `retry_all` 返回 idle/reset 语义：清空失败摘要、replacement、modal 和解析状态，等待用户重新选择文件。
   - `cancel` 返回 canceled/no-context 语义：不产生 `file_contexts`，不进入成功态，不触发 Chat API。
5. 与现有代码保持一致并可被 4.C.6 直接接入。
   - 复用 `apps/web/src/lib/chat-file-context.ts` 的 filename/type/size/no-leak 边界和 metadata payload 形状。
   - 可被 `packages/ui` 的 `FilePicker.onFile/onReject` 与 `ConfirmationModal` body/confirm/cancel 直接组合；本 story 不创建完整 Chat 页面。
   - 不新增运行时依赖。
6. 回归覆盖必须证明边界闭环。
   - RED 先写 focused Vitest，覆盖：1000 行 CSV 第 847 条数据行失败定位、三动作 label、仅替换失败行成功、replacement 行号不匹配 fail closed、全部重试清空、取消不产出 context、JSON.stringify 不泄漏 raw row/cell/secret。
   - 保留并运行既有 `chat-file-context` 测试，确认 4.C.3 CSV/Excel/JSON metadata 行为不回退。

## Tasks / Subtasks

- [x] Task 1: 增加 Chat CSV recovery 契约与测试（AC: 1, 2, 3, 4, 6）
  - [x] 新增 `apps/web/src/lib/chat-file-context-recovery.test.ts`，先写 RED tests：row 847 partial failure、modal actions、replace success、replace mismatch fail、retry/cancel/no-leak。
  - [x] 明确测试 payload 只断言 bounded metadata，不断言或 snapshot raw CSV rows。
- [x] Task 2: 复用 Chat file context parser 生成成功 metadata（AC: 1, 5）
  - [x] 在 `apps/web/src/lib/chat-file-context.ts` 中只抽出必要的 CSV row parser / context builder helper，保持 `parseChatFileContext(file)` 现有 public 行为不变。
  - [x] 新 helper 输出的成功 `context` 必须与 4.C.3 `ChatFileContextPayload` 字段、snake_case 和 no-leak 规则一致。
- [x] Task 3: 实现 partial recovery state machine 纯函数（AC: 2, 3, 4, 5）
  - [x] 新增 `apps/web/src/lib/chat-file-context-recovery.ts`，导出 FilePicker-compatible parse adapter、replacement 函数、retry/cancel 决策、typed recovery actions。
  - [x] recovery session 内部可持有替换所需的 canonical draft rows，但不得通过 enumerable public fields、`toJSON()`、context payload、URL/storage/log/test snapshot 泄漏 raw rows/cells。
  - [x] replacement 后重新跑全量结构校验与 metadata 构建，错误清零才返回 `ok: true`。
- [x] Task 4: 验证、记录和回归（AC: 5, 6）
  - [x] 运行 focused tests 并确认 RED，再实现 GREEN。
  - [x] 运行 `pnpm --filter @opticloud/web exec vitest run chat-file-context`。
  - [x] 运行 `pnpm --filter @opticloud/web typecheck`。
  - [x] 更新 story Dev Agent Record、File List、Change Log；story 文件状态推进到 `review`，sprint status 推进到 `code-review`。

## Dev Notes

### Scope and Architecture Guardrails

- Source AC：`_bmad-output/planning/epics.md:1589` 定义 Story 4.C.5 “Partial-upload-recovery UX flow（Lina-fix）”，AC 为 CSV 部分行 fail 时 Modal 三选项：仅替换 fail 行 / 全部重试 / 取消。
- 4.C.6 才负责 `ChatInterface` 完整 UI：`_bmad-output/planning/epics.md:1593`。本 story 只产出可接入 `FilePicker` + `ConfirmationModal` 的 helper/state contract。
- 4.C.3 已建立 Chat `file_contexts` metadata 形状、5MB 上限、no raw file boundary 和 internal beta Chat backend 合同：`_bmad-output/stories/4-c-3-file-upload-csv-excel-json.md`。
- 4.C.4 已证明 Chat JSON/SSE pipeline 应通过 bounded client-supplied context 扩展，不新增 persistence/public route：`_bmad-output/stories/4-c-4-what-if-followup.md`。
- `apps/web/src/lib/chat-file-context.ts` 当前负责 CSV/Excel/JSON metadata 解析，输出 `source="parsed_browser_file_context_v1"` 的 `ChatFileContextPayload`；4.C.5 不改变后端 schema。

### Previous Story Intelligence

- 3.11 Lina CSV 恢复已经实现 prediction-specific parser/page：`apps/web/src/lib/csv-prediction.ts`、`apps/web/src/app/console/predictions/page.tsx`。
- 3.11 的可复用经验：浏览器侧解析；失败行必须保留源行身份；“仅替换失败行”后必须重新校验全量 dataset；“全部重试”清空状态；“取消”不能提交；不要复制 `FilePicker` / `ConfirmationModal`。
- 3.11 的不可复用边界：`csv-prediction.ts` 聚合 prediction series、`PredictionRequestBody`、API key、`postPrediction()` 和 `/console/predictions` 页面都属于预测垂直切片，不能塞进 Chat helper。

### Data and Privacy Rules

- Public recovery result、`ChatFileContextPayload`、测试快照和 JSON serialization 都不得包含 raw CSV row/cell。
- 如实现需要临时保存 canonical rows 以便 replacement，必须封装在不可 JSON 序列化的 session 内部字段，并提供 `toJSON()` 安全摘要。
- 错误值统一使用 `"[omitted]"` 或不暴露 `value` 字段；不得把失败行中的实际文本、数字、secret-like 字段或路径写入错误对象。
- Prompt/response/backend `file_context_preview` 无需改动；4.C.5 只保证前端成功时提交既有 metadata payload，失败/取消时没有 payload。
- `row_count` 和最终 `summary` 必须基于修复后的全量非空 CSV 数据行数，不能基于 replacement 行数或只基于 valid rows。

### File Structure

- Expected new file: `apps/web/src/lib/chat-file-context-recovery.ts`
- Expected new tests: `apps/web/src/lib/chat-file-context-recovery.test.ts`
- Expected small refactor: `apps/web/src/lib/chat-file-context.ts` export/reuse CSV parser/context builder without changing existing tests.
- Do not edit `packages/ui` unless existing component API blocks the story. Current `ConfirmationModal` already supports `body`, custom confirm/cancel labels, and `FilePicker` already supports 5MB default/onReject.

### Testing Requirements

- Focused command: `pnpm --filter @opticloud/web exec vitest run chat-file-context`
- Typecheck command: `pnpm --filter @opticloud/web typecheck`
- Existing chat-service tests are not expected to change because backend `file_contexts` schema remains unchanged. If backend files change, rerun `apps/chat-service/tests/test_file_context.py` and related JSON/SSE suites.

### References

- `_bmad-output/planning/epics.md:816` — Lina partial-upload-recovery UX flow as Epic 3 + Epic 4.C AC enhancement.
- `_bmad-output/planning/epics.md:1451` — Story 3.11 J2 modal options and row 847 scenario.
- `_bmad-output/planning/epics.md:1589` — Story 4.C.5 source AC.
- `_bmad-output/planning/architecture.md:3283` — Lina maps to `FilePicker + RFC7807ErrorPanel + ConfirmationModal`.
- `_bmad-output/stories/3-11-j2-lina-csv-vertical-slice.md` — previous implementation and privacy/revalidation lessons.
- `_bmad-output/stories/4-c-3-file-upload-csv-excel-json.md` — Chat file context metadata contract and explicit 4.C.5 exclusion.
- `_bmad-output/stories/4-c-4-what-if-followup.md` — bounded context extension pattern for Chat.
- `apps/web/src/lib/chat-file-context.ts` — current Chat file metadata parser.
- `packages/ui/src/components/FilePicker/index.tsx` and `packages/ui/src/components/ConfirmationModal/index.tsx` — UI integration targets.

## Story Review Rounds

### Round 1 — Boundary / UI Ownership

- Finding: implementation scope could drift into full ChatInterface or a new upload endpoint because source AC uses modal wording.
- Fix applied: AC and Dev Notes keep this story to a browser-side helper/state contract under `apps/web/src/lib`; 4.C.6 owns visual ChatInterface composition, and no backend upload/public route/persistence is allowed.
- Finding: status wording could drift between BMad story status (`review`) and sprint status (`code-review`).
- Fix applied: Task 4 now states story file status becomes `review` while sprint status becomes `code-review`.

### Round 2 — Data Consistency / Privacy

- Finding: Chat generic CSV has no domain schema, so reusing 3.11's prediction numeric validation would be a hidden scope leak and could reject valid Chat CSVs.
- Fix applied: AC2 now defines partial failure as structural CSV schema failure only: missing header or data row cell-count mismatch against header.
- Finding: replacement rules were under-specified for multiple failures and could accidentally repair only the first 20 summarized errors.
- Fix applied: AC3 now requires replacement row count to match total `invalid_row_count`, row-number matching for multi-row recovery, no duplicate/unknown source rows, compatible headers, and full-dataset revalidation.
- Finding: bounded error display needed a concrete cap and final metadata row-count rule.
- Fix applied: AC2 caps public invalid row details at 20 while preserving total count; Data Rules require final `row_count`/`summary` to come from the repaired full dataset.

### Round 3 — Dependency / Closure

- Finding: focused test command relied on pnpm script argument forwarding, which is easy to misrun on Windows.
- Fix applied: Task 4 and Testing Requirements now use direct `pnpm --filter @opticloud/web exec vitest run chat-file-context`.
- Finding: no dependency gap found. Existing `FilePicker`, `ConfirmationModal`, and local CSV parser are sufficient; adding PapaParse or a modal wrapper would increase scope.
- Fix applied: story keeps "no runtime dependency" and only allows `packages/ui` edits if the existing API blocks implementation.
- Finding: backend closure is explicit: 4.C.5 produces the same frontend `ChatFileContextPayload`, so chat-service schema/tests only need rerun if backend files are touched.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-30 - RED: `pnpm --filter @opticloud/web exec vitest run chat-file-context` failed because `./chat-file-context-recovery` did not exist; existing `chat-file-context.test.ts` 6 tests passed.
- 2026-05-30 - GREEN: `pnpm --filter @opticloud/web exec vitest run chat-file-context` passed 13 tests after adding recovery helper and parser refactor.
- 2026-05-30 - Typecheck: `pnpm --filter @opticloud/web typecheck` passed.
- 2026-05-30 - Code review fix validation: `pnpm --filter @opticloud/web exec vitest run chat-file-context` passed 14 tests after adding multi-failure source-row coverage; `pnpm --filter @opticloud/web typecheck` passed.
- 2026-05-30 - Final validation: `pnpm --filter @opticloud/web exec vitest run chat-file-context` passed 15 tests; `pnpm --filter @opticloud/web test` passed 105 tests; `pnpm --filter @opticloud/web typecheck` passed.

### Completion Notes List

- Added Chat CSV partial-upload-recovery pure helper with modal-ready actions, bounded invalid row summary, retry/cancel terminal decisions, source-row-preserving replacement, and full-dataset revalidation.
- Refactored Chat file context CSV parsing into reusable row parser/context builder while preserving existing `parseChatFileContext` behavior and tests.
- Kept recovery session raw/canonical rows behind private fields; public JSON serialization returns only a safe session summary.
- Code review added regression coverage for multi-failure replacement: unordered source-row replacements succeed, replacement without source row numbers fails closed.
- Final review hardened recovery action immutability: each invalid result now receives fresh modal action objects so caller mutation cannot pollute later parses.
- No backend, `packages/ui`, ChatInterface, route, persistence, upload, or runtime dependency changes.

### File List

- `_bmad-output/stories/4-c-5-partial-upload-recovery.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/src/lib/chat-file-context.ts`
- `apps/web/src/lib/chat-file-context-recovery.ts`
- `apps/web/src/lib/chat-file-context-recovery.test.ts`

## Change Log

- 2026-05-30 - Initial 4.C.5 story created from Epic AC, 3.11 Lina recovery implementation, 4.C.3 Chat file metadata contract, 4.C.4 bounded Chat context pattern, and current UI/parser code.
- 2026-05-30 - Story review round 1 applied boundary/status fixes: helper-only scope, no ChatInterface/backend upload, and explicit story-vs-sprint review status semantics.
- 2026-05-30 - Story review round 2 applied data/privacy fixes: structural CSV validation scope, invalid-row cap, total failure count, replacement row-count/row-number rules, and repaired full-dataset metadata rule.
- 2026-05-30 - Story review round 3 applied dependency/closure fixes: direct Vitest command, no new dependency, no packages/ui change unless blocked, and backend rerun boundary.
- 2026-05-30 - Implemented Chat CSV partial-upload-recovery helper, parser refactor, focused tests, and validation; story status moved to review.
- 2026-05-30 - Post-implementation code review fixed multi-failure source-row coverage gap and revalidated focused tests/typecheck.
- 2026-05-30 - Final review hardened modal action return semantics and revalidated focused tests, full web tests, and typecheck.
- 2026-05-30 - Code review approved after patches; story status moved to done.

## Senior Developer Review (AI)

### Review Date

2026-05-30

### Review Outcome

Approve after patch.

### Findings

- [x] [Medium] Multi-failure replacement had implementation logic for required source row numbers, but lacked a focused regression proving unordered row-number replacements succeed and row-number-less multi-row replacements fail closed. Fixed in `apps/web/src/lib/chat-file-context-recovery.test.ts`.
- [x] [Low] Invalid recovery results reused the exported action array by reference, allowing caller mutation to pollute subsequent parses. Fixed by returning fresh action objects and adding a regression test.

### Review Notes

- Boundary check: no ChatInterface, backend route, upload endpoint, persistence, `packages/ui`, or dependency changes were introduced.
- Privacy check: raw/canonical rows are held behind private class fields; public invalid rows omit raw cell values; `toJSON()` returns only safe session summary; tests assert no raw row/cell/secret leakage.
- Data consistency check: replacement re-runs full structural validation and final metadata is built from the repaired full dataset.
