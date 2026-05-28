# Story 3.11: J2 Vertical Slice — Lina CSV 错误恢复

Status: done

## Story

作为零售数据分析师 Lina，
我希望在 Console 中上传 1000 行 CSV 并在第 847 行 schema 校验失败时看到可定位、可恢复的错误流程，
以便我能选择“仅替换失败行 / 全部重试 / 取消”，修正数据后继续调用现有预测 API，而不需要看 cURL 或手写 JSON。

## Acceptance Criteria

1. 新增 Lina 专用 Console CSV 预测入口，路径为 `apps/web/src/app/console/predictions/page.tsx`，首屏是可用的 CSV 上传/选择体验，不是营销页；入口文案面向 Console form-first 分析师，不展示 cURL、API key 教程或 Postman 说明。
2. 入口复用 `packages/ui` 现有 Tier 1 组件：`FilePicker` 负责 `.csv` 选择和大小拒绝，`ConfirmationModal` 承载 partial-upload-recovery 选择，`RFC7807Panel` 或等价 Problem Details 渲染承载 API 422/409/401 等响应；不得复制这些组件到 app 内部。
3. CSV 解析在浏览器侧完成，原始 CSV 文件不得上传到后端。支持 UTF-8 和 GBK/GB18030 解码探测；若 GBK 无法可靠用内置 `TextDecoder("gb18030")` 支持，则必须 fail closed 并给出“请另存为 UTF-8 CSV 后重试”的可操作提示，不得静默乱码。
4. CSV 合同为单文件、最多 10 MB、最多 10,000 条数据行；本 story 的验收 fixture 必须包含 1000 条数据行。表头至少支持中英混杂别名：`sku/SKU/商品/商品编号`、`month/date/月份/日期`、`value/sales/销量/销售额/需求`。解析输出按 CSV 行号保留来源位置，数据行行号从文件真实行号计算。
5. 当 1000 行 CSV 中第 847 条数据行的数值字段无效时，页面必须标记该行和字段，显示错误摘要和错误明细，并打开 recovery modal。Modal 选项必须是三个明确动作：`仅替换失败行`、`全部重试`、`取消`。选择 `取消` 不提交预测、不保留部分上传状态为成功。
6. `仅替换失败行` 路径必须允许用户提供替换 CSV 或修正后的文本片段，只替换同一 `sku+month/date` 或同一源行号的失败记录；替换成功后重新校验全量 canonical dataset，错误清零才允许继续预测。不能简单跳过失败行并声称成功。
7. `全部重试` 路径必须清空当前解析/错误/替换状态并回到 idle 上传态；再次上传合法 CSV 后能正常进入预测确认/提交路径。
8. 成功校验后的 CSV 映射到现有 `POST /v1/predictions` 合同：`family` 默认为 `chronos`，`data` 是按日期排序后聚合的数值序列，`horizon` 默认 `3`，可在 Console 表单中调整为 `1..90`。本 story 不新增 `/v1/predictions/csv`、不新增文件上传后端、不新增 batch API、不新增数据库表。
9. 页面提交预测时新增/复用 `apps/web/src/lib/api.ts::postPrediction()`，保持 `OptiCloudClientError` 对 RFC 7807 `errors[]`、`next_action_url`、`request_id`、`trace_id` 的透传；API 返回 422/409/401 时页面要展示结构化错误，不丢失 `errors[].field_path`。
10. 成功预测后页面展示 P10/P50/P90、`drift_score`、`model_version.provider_id/kind/version/provider_url`、`disclaimer` 和 Lina 可读的简短文字解读；不得把 `_system`、API key、billing charge id、原始文件 bytes 或内部 provider route metadata 暴露到 UI。
11. 现有 `/v1/predictions` 后端合同保持不变：不接受 `X-Billing-Charge-Id`、不新增 `PredictionRequest` 字段、不改变 prediction idempotency/hash/failed-row 语义、不改变 Story 3.6 compact failed-row 200 语义。
12. 回归覆盖包括：CSV parser UTF-8/GBK 或 GBK fail-closed、1000 行第 847 行失败定位、partial modal 三动作、仅替换失败行成功闭环、全部重试清空状态、成功 CSV 调用 `postPrediction` 且不上传文件、API RFC7807 错误渲染保留 `field_path`、成功结果展示 quantiles/model_version/disclaimer、Playwright J2 vertical slice 端到端。

## Tasks / Subtasks

- [x] Task 1: 构建 CSV parser 与 mapper（AC: 3, 4, 6, 8）
  - [x] 新增 `apps/web/src/lib/csv-prediction.ts`，实现浏览器侧 decode、CSV 行解析、header alias 识别、行号保留和 typed validation。
  - [x] 输出 canonical 结构：有效 records、invalid rows、aggregate series、default horizon、源文件摘要；不得保存原始 file bytes。
  - [x] 对第 847 条数据行无效值返回稳定 `row_number`、`field_path`、`constraint` 和原始 compact value。
  - [x] 实现只替换失败记录的纯函数，替换后重新校验全量 dataset，并拒绝 key/行号不匹配的替换片段。
  - [x] 不引入 PapaParse、iconv-lite 或服务端解析依赖；若必须新增依赖，先停下说明理由。
- [x] Task 2: 扩展 Web API client（AC: 8, 9, 11）
  - [x] 在 `apps/web/src/lib/api.ts` 增加 `PredictionRequest`、`PredictionResponse` 类型和 `postPrediction(apiKey, body, idempotencyKey?)`。
  - [x] 复用现有 `request()` 和 `OptiCloudClientError`，确保 `errors[]` / `next_action_url` 不重命名、不丢失。
  - [x] 不发送 `X-Billing-Charge-Id`；不改变 `postOptimization()`、billing helper 或后端 prediction schema。
- [x] Task 3: 新增 Lina Console CSV 页面（AC: 1, 2, 5, 6, 7, 8, 10）
  - [x] 新增 `apps/web/src/app/console/predictions/page.tsx`，状态机覆盖 idle → parsing → invalid_partial → recovery_modal → ready → submitting → solved / api_error。
  - [x] 使用 `FilePicker accept=".csv,text/csv"`，CSV 上限 10 MB；拒绝态给出拆分/转 UTF-8/下载模板的 actionable hint。
  - [x] 页面内提供 base64/data URL 或客户端生成的 CSV 模板下载，不依赖后端文件。
  - [x] invalid_partial 显示失败行/字段/约束，自动打开 `ConfirmationModal`，三个 CTA 分别执行仅替换失败行、全部重试、取消。
  - [x] ready 状态显示 SKU 数、数据行数、日期范围、聚合后序列长度、family/horizon 控件和提交按钮。
  - [x] solved 状态展示 quantile 简表、drift_score、model_version、disclaimer 和简短 NL summary 文案。
  - [x] api_error 状态用 `RFC7807Panel` 或同等结构保留 `errors[].field_path`、constraint 和 next action。
- [x] Task 4: 聚焦测试与 E2E（AC: 3-12）
  - [x] 新增 `apps/web/src/lib/csv-prediction.test.ts` 覆盖 parser、header alias、GBK/UTF-8、1000 行第 847 行失败、replacement、aggregate series。
  - [x] 新增 `apps/web/src/app/console/predictions/page.test.tsx` 覆盖状态机、modal 三动作、API success/error 渲染和“不上传文件 bytes”。
  - [x] 新增 `e2e/tests/lina-csv-error-recovery.spec.ts`，走上传 1000 行 CSV → 第 847 行失败 → 仅替换失败行 → 提交预测 → 展示 P10/P50/P90。
  - [x] 若 E2E 需要 mock API，使用现有 Playwright route mock；不要依赖真实外部服务。
- [x] Task 5: 验证与 BMAD bookkeeping（AC: 12）
  - [x] 运行 `pnpm --filter @opticloud/web test`。
  - [x] 运行 `pnpm --filter @opticloud/web typecheck`。
  - [x] 运行 `pnpm --dir e2e exec playwright test tests/lina-csv-error-recovery.spec.ts`。
  - [x] 运行 `uv run pytest apps/solver-orchestrator/tests/test_prediction_submission.py apps/solver-orchestrator/tests/test_rfc7807_errors_detail.py -q` 确认后端 prediction/error 合同未漂移。
  - [x] 运行 `uv run mypy apps packages`、`uv tool run pre-commit run --all-files --show-diff-on-failure`、`git diff --check`。
  - [x] 更新本 story 的 Dev Agent Record、File List、Change Log 和 sprint status。
  - [x] 实施完成后运行代码审查，修复审查发现，再同步 GitHub。

## Dev Notes

### Current Implementation Reality

- 当前后端已有 `POST /v1/predictions`，请求合同是 `{family, data, horizon}`，成功返回 P10/P50/P90、`drift_score`、`disclaimer` 和 `model_version`。它不接受 `X-Billing-Charge-Id`，且 Story 3.10 明确不改变 prediction billing header 拒绝规则。
- `PredictionRequest` 当前没有 CSV/file 字段。Story 3.11 必须在前端把 CSV 转成数值序列后调用现有 API，不能把文件上传后端。
- `apps/web/src/lib/api.ts` 已有 `request()`、`OptiCloudClientError`、`postOptimization()`、billing helpers 和 RFC7807 字段透传模式；新增 prediction helper 应沿用它。
- `packages/ui` 已导出 `FilePicker`、`ConfirmationModal`、`RFC7807Panel`、`StatusCard`、`LoadingShimmer`。Lina 页面应复用这些组件，不要复制 modal/error panel。
- `apps/web/src/app/console/excel/page.tsx` 是可复用的状态机和客户端文件解析参考：文件留在浏览器、状态显式、错误卡和 reset 路径清楚。不要把 Lina CSV 流硬塞进 Excel 页面；新增 `/console/predictions` 更符合 UX 的 Console New Prediction。
- `apps/web` 当前没有通用 CSV parser 依赖。浏览器可用 `File.text()` / `Blob.text()` 和 `TextDecoder`；CSV 语法可实现最小 RFC4180 支持：逗号、CRLF/LF、双引号转义、空行跳过。
- `apps/solver-orchestrator/src/solver_orchestrator/error_responses.py` 和 `error_catalog.py` 已提供 RFC7807 Problem Details；UI 应消费这些字段，不要新造错误 shape。

### CSV Contract for This Story

- 单文件 `.csv`，`FilePicker` 上限 10 MB。
- 行数上限对“数据行”计算，不含 header，最大 10,000；验收 fixture 为 1000 数据行。
- 必需逻辑字段：
  - sku: `sku`, `SKU`, `商品`, `商品编号`
  - date/month: `month`, `date`, `月份`, `日期`
  - value: `value`, `sales`, `销量`, `销售额`, `需求`
- `date/month` 可按 ISO `YYYY-MM` / `YYYY-MM-DD` 或 Excel 导出的普通字符串排序；story 实施不要求复杂日期库。排序 key 必须稳定，不能按原始行顺序误判趋势。
- 聚合规则：按 date/month 分组，对同一月份/日期的所有 SKU 数值求和，生成 `data: number[]`；少于 3 个聚合点时阻止提交并显示 `data length must be at least 3` 类错误。
- 默认 `family="chronos"`，因为 UX J2 明确“跑 Chronos”；用户可切到 `arima` 作为现有 API 支持的 fallback。
- 默认 `horizon=3`，控件允许 `1..90`。
- 第 847 条数据行失败定位应显示真实 CSV 行号。如果 header 是第 1 行，则第 847 条数据行对应文件第 848 行；测试应明确断言，避免 off-by-one。

### Partial-Upload-Recovery Semantics

- “仅替换失败行”不是“跳过 invalid 继续”。它必须用用户提供的替换行修复失败 record，然后重新校验全量 canonical dataset。
- 替换匹配策略优先 `sku + date/month`，如果 replacement 缺少 key 或 key 不匹配，再允许按原始 source row number 匹配；无法确定时 fail closed。
- 替换成功后 invalid rows 必须为 0 才能进入 ready/submit。若 replacement 仍无效，继续停留在 invalid_partial 并更新错误明细。
- “全部重试”必须清空 file summary、records、errors、replacement state、API result/error 和 modal state。
- “取消”必须关闭 modal 并留在错误详情态或回 idle，但不能进入 ready/submit，也不能调用 `postPrediction()`。

### Boundary Rules

- 不新增 `/v1/predictions/csv`、`POST /v1/files`、S3 预签名、大文件上传、后台 worker、batch endpoint 或数据库表。大于 10 MB / 10,000 行只给 actionable hint；S3/large upload 属于后续 4.C/3.13 边界。
- 不改变 `PredictionRequest`、`PredictionResponse`、后端 prediction idempotency、billing header 拒绝、model_version 或 compact failed-row 语义。
- 不新增真实 Chronos/GPU 依赖。现有 deterministic forecasting helper 继续作为后端实现。
- 不把原始 CSV bytes、完整失败文件、Authorization、API key、billing IDs 或 `_system` 写入 UI state、URL、localStorage、sessionStorage、日志或测试快照。
- 不做全站导航重构。可以在已有页面放少量链接，但本 story 的核心是 `/console/predictions` 可直接访问并完成 J2。
- 不引入服务端 Actions/API routes 解析 CSV；隐私边界是浏览器内解析。

### Previous Story Intelligence

- Story 3.7：J2 依赖精确 `errors[].field_path/value/constraint/remediation_hint_key`。页面必须保留这些字段，不要只显示 `detail` 字符串。
- Story 3.10：prediction billing header 仍被拒绝；前端不要为 predictions 创建 charge 或发送 `X-Billing-Charge-Id`。
- Story 3.E.1-3.E.6：文件解析应保持浏览器侧隐私；Excel 页面状态机、`FilePicker` reject handling、`StatusCard`、`ConfirmationModal` 和 Playwright file input 模式可复用。
- Story 0.13：Playwright J2 critical journey 是既定目标；E2E 可以通过 `setInputFiles` 而不是真实 drag/drop，drag/drop 细节可由 component/unit tests 覆盖。

### Testing Standards

- Web unit tests用 Vitest + Testing Library / happy-dom；纯 parser tests 不需要 React。
- E2E fixture 应在 test 内构造 CSV buffer，避免提交大二进制；1000 行文本 fixture可以动态生成。
- API success/error 可用 Playwright route mock；页面测试也应 mock `postPrediction()` 或 fetch，断言提交 body 不包含文件 bytes。
- 后端只跑 regression，除非实现中确实需要修改 solver-orchestrator。

### References

- `_bmad-output/planning/epics.md` Story 3.11: J2 Lina CSV 错误恢复 AC。
- `_bmad-output/planning/architecture.md` P75 Persona-Surface Mapping: Lina → FilePicker + RFC7807ErrorPanel + ConfirmationModal。
- `_bmad-output/planning/ux-design-specification.md` J2 Mermaid flow and Lina Console Form-first defining experience。
- `_bmad-output/planning/prd.md` Journey 2: Lina error recovery and Credits warning context。
- `_bmad-output/stories/3-7-rfc7807-errors-detail.md` downstream dependency on Story 3.11 and error contract.
- `_bmad-output/stories/3-10-backtest-discount.md` prediction billing boundary.
- `apps/web/src/lib/api.ts` existing web API helper and `OptiCloudClientError`.
- `packages/ui/src/components/FilePicker/index.tsx`
- `packages/ui/src/components/ConfirmationModal/index.tsx`
- `packages/ui/src/components/ErrorBoundary/index.tsx`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py::post_prediction`
- `apps/solver-orchestrator/tests/test_prediction_submission.py`

## Story Review Rounds

### Round 1 - Data Consistency (2026-05-28)

Findings applied:

- The initial story could have let "1000 rows + row 847" drift between file line numbers and data row numbers. The CSV contract now states header row handling explicitly: data row 847 maps to file line 848 when the header is line 1.
- The story now defines one canonical aggregation rule from per-SKU rows to the existing `PredictionRequest.data`: group by date/month, sum values, then sort by date key. This prevents UI display, API payload, and tests from using different series.
- The replacement flow now requires full dataset revalidation after replacing failed records, preventing "partial success" state from diverging from the payload actually submitted.

Result: CSV row identity, validation errors, replacement state, and prediction payload are data-consistent.

### Round 2 - Function / Dependency Consistency and Drift (2026-05-28)

Findings applied:

- The UX source says "CSV upload", but current backend has no CSV upload endpoint and Story 3.13 owns batch endpoint work. The story now explicitly scopes parsing to the browser and calls existing `/v1/predictions`.
- Component dependencies are pinned to existing `packages/ui` exports: `FilePicker`, `ConfirmationModal`, `RFC7807Panel`, `StatusCard`, and `LoadingShimmer`. The story forbids copying modal/error components into app code.
- The API helper work is additive: add `postPrediction()` to `apps/web/src/lib/api.ts` while preserving existing `request()` and `OptiCloudClientError` behavior.

Result: implementation aligns with current code boundaries and avoids dependency drift or duplicated UI primitives.

### Round 3 - Boundary / Edge Cases / Closure (2026-05-28)

Findings applied:

- Large CSV/S3 handling is explicitly out of scope and fail-closed with actionable hints, because architecture puts S3 presign and large upload in later file-upload stories.
- GBK/GB18030 support is constrained: use built-in browser decoding if available, otherwise show a UTF-8 conversion prompt rather than silently corrupting data.
- Prediction billing, idempotency, compact failed-row semantics, and `_system` privacy boundaries are explicitly preserved.
- E2E closure now includes the full J2 happy recovery: upload invalid 1000-row CSV, repair row 847, submit prediction, and render quantiles.

Result: encoding, size, privacy, backend contract, and end-to-end recovery boundaries are closed before implementation.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-28 - Initial Story 3.11 draft created from sprint status, Epics/PRD/Architecture/UX, Story 3.7/3.10/3.E learnings, current web API client, packages/ui components, and prediction backend route/tests.
- 2026-05-28 - Story review Round 1 completed and applied: data consistency for CSV row numbering, aggregation rule, and replacement revalidation.
- 2026-05-28 - Story review Round 2 completed and applied: function/dependency consistency for browser-side parsing, existing prediction API, UI component reuse, and additive API helper.
- 2026-05-28 - Story review Round 3 completed and applied: boundary closure for GBK fallback, large upload/S3, billing/idempotency privacy, and E2E recovery path.
- 2026-05-28 - Dev implementation started; sprint/story status moved to in-progress.
- 2026-05-28 - RED phase confirmed for CSV parser and prediction API helper: parser module and `postPrediction()` missing as expected.
- 2026-05-28 - Implemented browser-side CSV parser/mapper, canonical aggregation, invalid row identity, GB18030 fallback, and failed-row replacement revalidation.
- 2026-05-28 - Implemented additive `postPrediction()` API helper and RFC7807 `request_id` / `trace_id` client passthrough.
- 2026-05-28 - Implemented `/console/predictions` Lina flow using `FilePicker`, `ConfirmationModal`, `RFC7807Panel`, `StatusCard`, and `LoadingShimmer`.
- 2026-05-28 - Added Vitest parser/API/page coverage and Playwright J2 recovery E2E.
- 2026-05-28 - Post-implementation code review completed; patched API key persistence/state privacy and parser raw CSV retention boundary.
- 2026-05-28 - Final validation passed after code-review fixes: web tests 87 passed; web typecheck passed; J2 Playwright 1 passed; prediction/RFC7807 backend tests 42 passed; mypy/pre-commit/diff-check passed.

### Completion Notes List

- Story scopes J2 to a frontend Console CSV recovery vertical slice using the existing `/v1/predictions` API.
- Story explicitly excludes backend CSV upload, S3 presign, batch endpoint, prediction billing, and prediction schema changes.
- Three story review rounds completed and reflected directly in ACs, tasks, Dev Notes, boundary rules, and test requirements.
- Implemented CSV parsing fully in the browser with UTF-8/GB18030 detection, 10,000-row cap, header aliases, stable source row identity, and sorted period aggregation.
- Implemented failed-row replacement as full-dataset revalidation, matching by `sku+period` or source row number and refusing mismatched replacement snippets.
- Implemented Lina Console page at `/console/predictions` with three recovery actions, ready/submit/result/error states, local template download, quantile/model/disclaimer result rendering, and RFC7807 detail preservation.
- Added `postPrediction()` without billing headers and without backend prediction schema changes.
- Resolved post-implementation review findings: API key is read from an uncontrolled input only at submit time and is not persisted in state/sessionStorage; parser invalid state stores canonical draft rows rather than full raw CSV rows.
- Story 3.11 is complete after final regression, typecheck, E2E, mypy, pre-commit, diff-check, and code-review fix validation.

### File List

- `_bmad-output/stories/3-11-j2-lina-csv-vertical-slice.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/src/lib/csv-prediction.ts`
- `apps/web/src/lib/csv-prediction.test.ts`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/api-prediction.test.ts`
- `apps/web/src/app/console/predictions/page.tsx`
- `apps/web/src/app/console/predictions/page.test.tsx`
- `e2e/tests/lina-csv-error-recovery.spec.ts`

### Change Log

- 2026-05-28 - Initial Story 3.11 draft created and sprint status moved from backlog to ready-for-dev.
- 2026-05-28 - Applied Story Review Round 1 data consistency fixes.
- 2026-05-28 - Applied Story Review Round 2 function/dependency consistency fixes.
- 2026-05-28 - Applied Story Review Round 3 boundary/closure fixes.
- 2026-05-28 - Dev implementation started and status moved to in-progress.
- 2026-05-28 - Implemented Story 3.11 Lina CSV browser-side recovery vertical slice with parser, API helper, Console page, unit tests, and E2E coverage.
- 2026-05-28 - Completed post-implementation code review; fixed API key persistence/state privacy and parser raw CSV retention boundary; marked story done after final validation.

## Senior Developer Review (AI) - Post-Implementation (2026-05-28)

### Review Scope

- Uncommitted branch diff against Story 3.11 spec.
- Layers covered manually in one pass: Blind Hunter, Edge Case Hunter, Acceptance Auditor.

### Findings

- [x] [Review][Patch] The first implementation kept the API key in React state and `sessionStorage`, which conflicted with the story privacy boundary forbidding API key persistence in UI state/storage. Patched by using an uncontrolled input read through a ref only at submit time and adding a regression assertion that `sessionStorage.api_key` remains unset.
- [x] [Review][Patch] The first parser invalid result kept complete parsed `sourceRows`, which was broader than needed for recovery and could drift toward retaining the full failed file. Patched by storing only canonical draft rows (`sku`, `period`, compact raw value, source row numbers) needed for replacement and full-dataset revalidation.

### Fixes Applied

- Reworked `/console/predictions` API key handling so the value is not stored in React state, URL, localStorage, sessionStorage, logs, or snapshots.
- Reworked `csv-prediction.ts` invalid-state data from raw row arrays to canonical draft rows; replacement still supports `sku+period` and optional source row number matching, followed by full revalidation.
- Re-ran focused tests after both patches, then reran the full validation list.

### Result

Approved after patch. `pnpm --filter @opticloud/web test`, `pnpm --filter @opticloud/web typecheck`, `pnpm --dir e2e exec playwright test tests/lina-csv-error-recovery.spec.ts`, backend prediction/RFC7807 regression, `uv run mypy apps packages`, pre-commit, and `git diff --check` all passed.
