---
story_key: 3-e-9-laozhang-vertical-slice-e2e
epic_num: 3.E
story_num: 3.E.9
epic_name: Console Excel Upload-Download UX
status: done
priority: 🔴 Critical (FG1.2 老张 Excel surface acceptance gate; proves registration → Excel upload → detect → solve/demo → download as one journey)
sizing: M (~3-5 hours; mostly Playwright E2E + one small navigation bridge if still missing; no backend/schema/new dependency)
type: e2e + regression hardening + minimal UX integration
created_by: bmad-create-story
created_at: 2026-05-24
sources:
  - _bmad-output/planning/epics.md:76 (FR E11: .xlsx ≤5 MB / 50K rows via Console → task_type → result Excel)
  - _bmad-output/planning/epics.md:228 (UX-DR7: 5 critical Mermaid flows + 22 Chaos Monkey hardenings)
  - _bmad-output/planning/epics.md:382 (Epic 3.E goal for 老张)
  - _bmad-output/planning/epics.md:1467 (Epic 3.E story list)
  - _bmad-output/planning/epics.md:1504 (Story 3.E.9 AC)
  - _bmad-output/planning/prd.md:1292 (Console Excel upload-download v1 end)
  - _bmad-output/planning/prd.md:1425 (老张 Excel surface maps to E11/E7/B1)
  - _bmad-output/planning/prd.md:1478 (E11 capability contract)
  - _bmad-output/planning/ux-design-specification.md:88 (老张 persona)
  - _bmad-output/planning/ux-design-specification.md:23 (22 hardenings: password Excel / formulas / multi-sheet / shared device etc.)
  - _bmad-output/planning/ux-design-specification.md:3128 (Console voice: 实证克制 + M3 友好不滥情)
  - _bmad-output/planning/ux-design-specification.md:3213 (Loading a11y: aria-busy + aria-live)
  - _bmad-output/planning/architecture.md:332 (Next.js 15 + App Router + Tailwind v3)
  - _bmad-output/planning/architecture.md:351 (Vitest + React Testing Library + Playwright)
  - _bmad-output/planning/architecture.md:3284 (老张 surface mapping: web/api-gateway + ExcelDropZone + LoadingShimmer + StatusCard)
  - _bmad-output/stories/1-8-onboarding-wizard-5steps.md (signup/welcome onboarding route handoff and sessionStorage behavior)
  - _bmad-output/stories/3-e-6-excel-result-download.md (download workbook contract and SheetJS dynamic import)
  - _bmad-output/stories/3-e-8-zh-ux-friendly-voice.md (final copy/loading expectations for /console/excel)
  - apps/web/src/app/page.tsx (landing signup CTA and Excel value proposition)
  - apps/web/src/app/auth/signup/page.tsx (UI signup path)
  - apps/web/src/app/welcome/page.tsx (post-signup API key / onboarding surface)
  - apps/web/src/app/console/excel/page.tsx (current Excel state machine)
  - apps/web/src/lib/excel.ts (browser-side parser with includeRows option)
  - apps/web/src/lib/excel-export.ts (result workbook export contract)
  - e2e/tests/j1-happy-path.spec.ts (registration/onboarding E2E pattern)
  - e2e/tests/console-excel.spec.ts (Excel upload/detect/submit/download E2E pattern)
  - e2e/fixtures/auth.ts (random phone/email helpers)
  - e2e/playwright.config.ts (local service webServer startup)
dependencies:
  upstream:
    - 1-8-onboarding-wizard-5steps (done) - `/auth/signup` → `/welcome` flow, sessionStorage JWT, SignupWizard
    - 3-e-1-excel-drop-zone (done) - `/console/excel` entry, file validation, retry/help path
    - 3-e-2-excel-task-type-detect (done) - browser parse + detect + confirmation modal
    - 3-e-3-vrptw-template (done) - VRPTW preview + demo submit
    - 3-e-4-schedule-template (done) - Schedule preview + demo submit
    - 3-e-5-inventory-template (done) - Inventory preview + demo submit
    - 3-e-6-excel-result-download (done) - result workbook download
    - 3-e-8-zh-ux-friendly-voice (done) - polished Chinese copy/loading/download states
  related_not_blocking:
    - 3-e-7-excel-chart-embedding (backlog) - chart embedding remains out of scope for this vertical E2E
---

# Story 3.E.9 - 老张 Excel Surface Vertical Slice E2E

## User Story

**As** 老张（制造排程工程师，Excel 是主工具，不熟 cURL），
**I want** 从注册开始，能通过一个自动化覆盖的浏览器路径进入 Excel 上传页、上传真实 `.xlsx`、自动识别业务类型、试跑、并下载结果 Excel，
**so that** 团队可以确认 FG1.2 老张 Excel surface 不是一组分散 demo，而是一条端到端可回归的无代码业务路径。

## Why This Story

3.E.1-6 已经做通 Excel 上传、检测、三类模板、试跑 501/demo、下载结果；3.E.8 已把中文 copy 和 loading 状态统一。当前缺口是：这些能力主要在 `console-excel.spec.ts` 里分段验证，还没有把 PRD/UX-DR7 要求的“注册 → 上传 .xlsx → 自动 detect → 求解 → 下载结果”作为一个垂直故事锁住。

这条 story 的核心产物应是一个新的老张 vertical slice E2E，以及必要的最小导航补缝。它不是重做 Excel 页面，也不是实现 chart embedding 或真实求解器。

## Out of Scope

- 不实现 3.E.7 chart embedding，不引入 `xlsx-style` 或图表库。
- 不新增真实 VRPTW/Schedule/Inventory 求解器；当前 `/v1/optimizations/demo` 对非 LP 返回演示/501 路径仍可接受。
- 不把 `/console/excel` 强制改成鉴权页；当前 demo endpoint 是 no-auth，3.E.9 只证明注册后能进入并完成 Excel arc。
- 不重写 `ExcelDropZone`、`parseExcel`、`detectTaskType`、三类 mapper、`buildResultWorkbook`。
- 不添加静态 `.xlsx` fixture 文件；继续用 Playwright 内存构造 workbook。
- 不新增后端接口、数据库表、环境变量或运行时依赖。
- 不把 22 个 Chaos Monkey hardenings 全部一次性产品化；本 story 只自动化最贴近老张 Excel vertical slice 的高风险分支，并把余项列为后续风险。

## Acceptance Criteria

### AC1: 新增独立老张 vertical slice Playwright spec

新增 `e2e/tests/laozhang-excel-vertical-slice.spec.ts`。

要求：

- 使用 `test.step()` 明确分段：注册、进入 Excel surface、上传、自动识别、确认、试跑、下载、校验结果 workbook。
- 使用 `e2e/fixtures/auth.ts` 里的 `randomPhone()` / `randomEmail()` 生成 UI 注册输入；不要硬编码账号。
- 复用 `console-excel.spec.ts` 的内存 `xlsx` 构造模式，可抽一个本地 helper，但不要引入外部 fixture 文件。
- 该 spec 可以 `test.describe.serial` 或单用一个长测试；若和服务端端口/下载事件冲突，运行命令使用 `--workers=1`。
- 文件名、测试名、step 名都应包含“老张”或 `laozhang`，方便 CI 失败时定位 FG1.2。

### AC2: 注册后有可点击路径进入 Excel surface

当前 `/console/excel` 可直接访问，但 vertical slice 不能只靠 `page.goto("/console/excel")` 跳过用户路径。

实现要求：

- 在注册成功后的 `/welcome` 页面增加一个克制的二级入口，指向 `/console/excel`。
- 入口应实现为显式 `Link href="/console/excel"`，并带 `data-testid="welcome-excel-upload-link"`，便于 E2E 和人工回归定位。
- 建议链接文案：`上传 Excel`
- 放置位置应不打断 J1 API Key / Postman / LP onboarding 主路径；它是老张 alternative surface，不是替代 Hello World。
- 如果欢迎页初始 `ConfirmationModal` 挡住入口，E2E 需要先用 `Escape` 或关闭按钮回到页面，再点击该入口。
- 如果实现时发现已有等价入口，可复用并在 E2E 中点击它；不要新增重复 CTA。
- 必须保持 `e2e/tests/j1-happy-path.spec.ts` 原有注册/LP happy path 通过。

### AC3: E2E 走真实 UI 注册，不绕过 auth API fixture

Vertical slice 的注册段应复用 J1 的 UI pattern：

1. `page.goto("/")`
2. 从 nav 点击 `立即注册`
3. 填 `手机号` 和 `邮箱`
4. 点击 `立即注册`
5. 等待跳转 `/welcome`
6. 看到 `signup-wizard` 和 API Key/welcome 关键状态
7. 关闭可能阻挡页面的 `ConfirmationModal`，再点击 `welcome-excel-upload-link`

要求：

- 不使用 `signupRandomUser()` 直接建用户；该 helper适合 API 预置，不适合这条 UI vertical slice。
- 不读取或断言完整 API key secret；只断言页面进入已登录/已注册状态即可。
- 不改变当前 `sessionStorage` JWT 存储策略；这是现有 demo 实现，不在 3.E.9 扩展。

### AC4: 上传 workbook 必须自然触发 Inventory 自动识别

使用 Inventory 作为主 vertical slice，因为它覆盖 3 张 sheets、历史行和下载 workbook 的最大面。

Workbook 要求：

- sheets：`SKU`、`历史出货`、`季节性`
- 对应表头要沿用现有 detector / mapper 信号集；优先复用 3.E.5 当前 fixture 形状：`SKU` sheet 用 `sku / 名称 / 类别 / 期初库存`，`历史出货` sheet 用 `sku / 日期 / 销量`（或等价的 `date / qty` accepted headers），`季节性` sheet 用 `sku / 季节 / 系数`
- 至少 2 个 SKU、至少 3 条历史出货行
- 总体积远低于 5 MB，总数据行远低于 50K
- 由 `xlsx` 在测试内构造 `Buffer`

E2E 要求：

- 使用 `page.locator('input[type="file"]').setInputFiles(...)`，沿用既有稳定模式；不要在 Playwright 里手写 drag/drop `DataTransfer`。
- 上传后断言 `excel-received-card` 出现并包含 `已收到您的 Excel 文件`。
- 断言检测 modal 自然显示 `系统判断：库存预测` 或等价用户可见库存文案。
- 本条路径不允许先手动 override 到 inventory；如果 detector 未自然命中，应调整 fixture 或修 detector，而不是在 vertical slice 里掩盖问题。
- 保留 `detection-override-select` 的存在断言即可，不在 happy path 使用它。

### AC5: 试跑与 demo/501 状态必须被验证

确认 Inventory 后：

- 断言 `inventory-preview-card` 可见。
- 断言 preview 包含 SKU / 历史行等关键计数文案。
- 点击 `inventory-submit-button`。
- 等待 `inventory-501-card` 或当前等价 demo-result card。
- 断言文案诚实包含 `M2-M3` 或“当前版本返回演示结果”；当前实现分支锁定 demo/501，不要在本 story 中同时兼容另一个未实现分支。
- 不新增 mock route；使用现有 `submitOptimizationDemo()` → `/v1/optimizations/demo` 路径。

### AC6: 下载结果 Excel 必须被解析验证，不只看 download event

下载段要求：

- 点击 `inventory-download-button`。
- 等待 download event。
- 断言 suggested filename 匹配 `^opticloud_inventory_\d{8}T\d{6}Z\.xlsx$`。
- 将 download 保存到 `testInfo.outputPath(...)`。
- 用测试中的 `xlsx` 读取保存后的文件，至少断言：
  - SheetNames 包含一个或多个 `输入 — ...` sheet。
  - SheetNames 包含 `Results`。
  - SheetNames 包含 `Summary`。
  - `Results` header 含 `forecast_p10` / `forecast_p50` / `forecast_p90` / `demo_marker`。
  - Results 至少有 2 个 SKU 数据行。
- `Summary` 中 `status` 为 `demo (M2-M3 待上线)`。
- `Summary` 中 `source_filename` 等于上传的 `inventory.xlsx`。
- `Summary` 中 `source_total_rows` 等于 6（2 SKU + 3 历史出货 + 1 季节性数据行）。
- `Summary` 中 `generated_by` 包含 `/console/excel`。

这会补足 3.E.6 现有 E2E 只验证 filename/download event 的盲区。

### AC7: 老张 Chaos Monkey hardening 覆盖矩阵落地

在 story 实现中新增或更新一个简短覆盖矩阵，推荐放在新 spec 顶部注释或 `Dev Agent Record`。

最低自动化覆盖：

- multi-sheet handling：Inventory 三 sheet happy path。
- formula/cached-value tolerance：如果 `read-excel-file` 能读取 SheetJS 写入的 cached formula value，则在 vertical spec 或 web unit test 加一个小 case；若不可稳定实现，记录为 deferred risk，不伪造通过。
- corrupt workbook recovery：复用或扩展现有 parse-error 测试，确保错误卡仍可见且可重试。
- password-protected workbook：当前仓库没有稳定生成器与支持路径，明确标记为未覆盖 / future follow-up，不要在本 story 中假装已验证。
- oversize recovery：现有 `console-excel.spec.ts` 已覆盖，矩阵标为 existing coverage，不重复。
- shared-device/session leakage：vertical spec 不应依赖前一个测试的 sessionStorage；新测试开新 page/context，使用随机账号。
- route recovery：注册完成后必须能从 `/welcome` 进入 `/console/excel`，不要求用户记 URL；如果 welcome 的 `ConfirmationModal` 仍默认打开，测试要先关闭它再点击 Excel 入口。

明确不在本 story 自动化的 hardenings，例如 S3 预签、CSV >100MB、SSE reconnect、申诉 flow、PGP/HackerOne，应列为 “not applicable to 老张 Excel v1 path” 或 future epic，而不是假装覆盖。

### AC8: 保留既有 selectors 和分段 E2E

不得破坏这些已有 selectors：

- `signup-wizard`
- `confirmation-modal`
- `excel-drop-zone`
- `excel-received-card`
- `detection-confidence`
- `detection-override-select`
- `inventory-preview-card`
- `inventory-submit-button`
- `inventory-501-card`
- `inventory-download-button`
- `excel-parse-error-card`
- `excel-reset-button`

`e2e/tests/console-excel.spec.ts` 仍保留为分段 regression suite；3.E.9 新 spec 是跨域 vertical slice，不要把原 spec 全部搬走。

### AC9: 测试运行命令和质量门

必须运行并记录：

- `pnpm --filter @opticloud/web test`
- `pnpm --filter @opticloud/web typecheck`
- `pnpm --filter @opticloud/ui test`
- `pnpm --filter @opticloud/ui typecheck`
- `pnpm --dir e2e exec playwright test tests/j1-happy-path.spec.ts --project=chromium --workers=1`
- `pnpm --dir e2e exec playwright test tests/console-excel.spec.ts --project=chromium --workers=1`
- `pnpm --dir e2e exec playwright test tests/laozhang-excel-vertical-slice.spec.ts --project=chromium --workers=1`
- `git diff --check`

如果实现只新增 E2E 和 welcome 链接，Python service tests 不必单独运行；Playwright webServer 会启动 auth-service 和 solver-orchestrator。

### AC10: Sprint tracking bundled

- 创建 story 后，`_bmad-output/stories/sprint-status.yaml` 中 `3-e-9-laozhang-vertical-slice-e2e` 必须为 `ready-for-dev`。
- dev-story 开始后可置 `in-progress`。
- 实现、review、所有质量门通过后才可置 `done`。
- sprint-status 修改必须和 story/implementation 一起提交，不做后续补丁。

## Tasks / Subtasks

- [x] Task 1: 导航补缝（AC: 2, 3, 8）
  - [x] 检查 `/welcome` 是否已有 Excel surface 入口。
  - [x] 如无，添加 `welcome-excel-upload-link` 指向 `/console/excel`。
  - [x] 确保该入口不遮挡 API Key / Postman / LP 主 onboarding。
  - [x] 跑或更新 J1 E2E，确认原路径不回退。

- [x] Task 2: 新增老张 vertical slice E2E spec（AC: 1, 3, 4, 5）
  - [x] 创建 `e2e/tests/laozhang-excel-vertical-slice.spec.ts`。
  - [x] 复用 `randomPhone()` / `randomEmail()`。
  - [x] 在测试内构造 Inventory `.xlsx` Buffer。
  - [x] UI 注册 → `/welcome` → 点击 Excel 入口 → 上传 workbook。
  - [x] 断言自动识别库存预测，确认后进入 Inventory preview。
  - [x] 试跑并断言 demo/501 诚实状态。

- [x] Task 3: 下载 workbook 深度校验（AC: 6）
  - [x] 保存 download 到 `testInfo.outputPath(...)`。
  - [x] 用 `xlsx` 读回下载文件。
  - [x] 校验输入 sheets、Results、Summary、forecast columns、demo status、generated_by。
  - [x] 保持 3.E.6 的动态 import 行为，不改 `buildResultWorkbook` 除非测试发现真实 bug。

- [x] Task 4: Hardening matrix 和必要补测（AC: 7）
  - [x] 在新 spec 注释或 story Dev Agent Record 记录覆盖矩阵。
  - [x] 将 existing coverage 指向 `console-excel.spec.ts` 现有 parse-error / oversize / retry 测试。
  - [x] 仅在稳定可测时加 formula cached-value case；否则记录 deferred risk。
  - [x] 不为不适用的 22 hardening 项造假覆盖。

- [x] Task 5: 回归和质量门（AC: 8, 9, 10）
  - [x] 运行 AC9 全部命令。
  - [x] 修复因 welcome link 或 E2E 新增引起的 type/test failures。
  - [x] 更新 Dev Agent Record 的 File List、Completion Notes、Verification。
  - [x] implementation 完成后进入 code-review，而不是自行标 done。

## Dev Notes

### Current Code Shape

- `/console/excel` 是 client page，状态机为 `idle → received → detected → confirmed → preview/submit/download`。
- `ReceivedCard` 首次 `parseExcel(file)` 只做 summary + detect；三类 preview card 会再用 `parseExcel(file, { includeRows: true })` 生成 mapper payload 和下载 source。
- `submitOptimizationDemo()` 调 `/v1/optimizations/demo`，当前非 LP 模板会走 demo/501 友好路径。
- `DownloadResultCard` 调 `buildResultWorkbook()`，后者在函数内 `await import("xlsx")`，不要改成顶层 import。
- `/auth/signup` UI 成功后把 JWT/user_id 放入 `sessionStorage` 并跳 `/welcome`。
- `/welcome` 会自动 create API key，并显示 SignupWizard / APIKeyManager / Postman / LP demo。

### Implementation Guidance

- 新 E2E 需要跨两个既有故事域：J1 onboarding 和 3.E Excel。优先复用现有 selectors 和 helper，避免复制业务逻辑。
- 如果 `/welcome` 的 API key modal 挡住新 Excel 链接，在测试中按 `Escape` 关闭，沿用 `j1-happy-path.spec.ts` 的做法。
- Inventory workbook 应设计成 detector 明确命中 inventory。若需要稳定性，可增加 sheet/header 信号，而不是在 happy path override。
- 下载解析建议使用：

```ts
const target = testInfo.outputPath(download.suggestedFilename());
await download.saveAs(target);
const wb = xlsxReadFile(target);
```

- 若 `download.path()` 在某环境不可用，优先用 `saveAs` 到 `testInfo.outputPath`。
- Playwright 的 file upload 继续用 `setInputFiles({ name, mimeType, buffer })`。
- 不要使用硬等待；等待用户可见状态或 download event。
- 新 welcome link 若需 styling，使用现有 Tailwind token 和 utilitarian layout，不做 hero/marketing block。

### Previous Story Intelligence

From 1.8:

- Onboarding shell 是 route composition，不是新 backend flow。
- `sessionStorage` 是当前 demo 登录状态来源，测试不要把它升级为 cookie/auth redesign。
- Existing J1 E2E closes API key modal with `Escape` before continuing; reuse this when needed.

From 3.E.6:

- Download workbook contract already exists: input sheets prefixed with `输入 — `, plus `Results` and `Summary`.
- `xlsx` is already a runtime dep for web and a dev dep in e2e; no new dep needed.
- Dynamic import of SheetJS is intentional for bundle size.

From 3.E.8:

- Copy expectations now use `已收到您的 Excel 文件`, `系统判断：库存预测`, `确认并继续`, `下载 Excel 结果`, `正在生成 Excel...` style.
- Do not reintroduce raw `task_type` in primary visible labels.
- Existing `console-excel.spec.ts` already delays the SheetJS chunk to assert generating state; keep that test.

### Project Structure Notes

- Expected new file: `e2e/tests/laozhang-excel-vertical-slice.spec.ts`
- Likely touched file: `apps/web/src/app/welcome/page.tsx`
- Only touch `apps/web/src/app/console/excel/page.tsx` if E2E exposes a real product bug.
- Keep workbook construction local to the spec unless duplication becomes clear. If extracting, prefer a small helper under `e2e/fixtures/` and keep it test-only.
- Do not create a new route; `/console/excel` already exists.
- Do not move existing `console-excel.spec.ts`; add cross-flow coverage beside it.

### Testing Notes

- `e2e/playwright.config.ts` already starts auth-service, solver-orchestrator, and web locally through `scripts/start_service.py`.
- Use Chromium for PR-speed verification; cross-browser remains nightly-only per config.
- Because this story crosses signup, welcome, solver demo, and browser download, run with `--workers=1` for deterministic local verification.
- Keep J1 and console-excel specs in the verification set because 3.E.9 touches both surfaces.

### Latest Technical Research

No external latest-version research is required for this story. It introduces no new library and relies on local locked versions/patterns:

- Next.js 15 App Router in `apps/web`
- Playwright in `e2e`
- SheetJS `xlsx ^0.18.5`, already present in `apps/web` and `e2e`

If implementation proposes a new library, stop and justify it; default answer should be no new dependency.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| The vertical spec becomes flaky by depending on exact animation/loading timing | Assert durable user-visible states, not transient shimmer timing. |
| The test cheats by using direct API signup or direct `/console/excel` navigation | AC3 requires UI signup and AC2 requires clicking an app link into Excel. |
| Inventory auto-detect is hidden by manual override | AC4 forbids override in happy path; fix fixture/detector instead. |
| Download event passes but workbook is malformed | AC6 parses the downloaded file and checks sheets/columns/status. |
| Welcome link disrupts J1 onboarding | Link is secondary; J1 spec must still pass. |
| 22 hardenings are overclaimed | AC7 requires a coverage matrix with existing/new/deferred/not-applicable status. |
| Chart embedding expectation leaks into 3.E.9 | Explicitly out of scope; 3.E.7 owns charts. |
| Parallel Playwright tests collide on service ports/session/download paths | Run vertical checks with `--workers=1`; use `testInfo.outputPath` for files. |

## Definition of Ready

- 1.8 onboarding is done and provides UI signup → welcome path.
- 3.E.1-6 are done and provide upload/detect/template/demo/download.
- 3.E.8 is done and provides final Chinese UX copy expectations.
- Existing Playwright fixtures can generate random users and in-memory workbooks.
- `/console/excel` route exists and is covered by current `console-excel.spec.ts`.

## Definition of Done

- AC1-AC10 pass.
- A registered UI user can click into `/console/excel` from the app, not only by direct URL.
- New 老张 vertical slice E2E passes locally in Chromium.
- Downloaded Inventory workbook is parsed and validated for input/results/summary sheets.
- Existing J1 and Console Excel E2E specs still pass.
- Dev Agent Record lists changed files and exact verification outcomes.
- Story moves to code-review after implementation, and to done only after review and gates pass.

## References

- [Source: _bmad-output/planning/epics.md:1504]
- [Source: _bmad-output/planning/prd.md:1478]
- [Source: _bmad-output/planning/ux-design-specification.md:23]
- [Source: _bmad-output/planning/architecture.md:3284]
- [Source: _bmad-output/stories/1-8-onboarding-wizard-5steps.md]
- [Source: _bmad-output/stories/3-e-6-excel-result-download.md]
- [Source: _bmad-output/stories/3-e-8-zh-ux-friendly-voice.md]
- [Source: apps/web/src/app/welcome/page.tsx]
- [Source: apps/web/src/app/console/excel/page.tsx]
- [Source: apps/web/src/lib/excel-export.ts]
- [Source: e2e/tests/j1-happy-path.spec.ts]
- [Source: e2e/tests/console-excel.spec.ts]

## Three-Round Story Review

### Round 1: Data Consistency Review

Scope: workbook fixture data, row counts, downloaded workbook assertions, and summary metadata.

Findings:

- [x] Inventory workbook data matches AC4: three sheets, 2 SKU rows, 3 history rows, 1 seasonality row, and total source rows = 6.
- [x] Download assertions parse the saved workbook instead of only relying on a browser download event.
- [x] Summary assertions check `status`, `source_filename`, `source_total_rows`, and `generated_by`.

Round 1 result: PASS; no story or code change required in this round.

### Round 2: Function Consistency / Drift Review

Scope: vertical path fidelity versus existing J1 and Excel functions.

Findings:

- [x] The vertical spec uses UI signup and the `/welcome` Excel link; it does not call auth fixtures or direct-goto `/console/excel` to bypass the product path.
- [x] Inventory detection is natural from workbook content; the happy path does not use manual override.
- [x] The test reuses the existing `/v1/optimizations/demo` and workbook export path; no mocks or new backend routes were added.

Round 2 result: PASS; no story or code change required in this round.

### Round 3: Boundary / Closure Review

Scope: route recovery, modal blocking, hardening matrix honesty, and regression closure.

Findings:

- [x] `/welcome` modal blocking is handled by closing the modal before clicking the Excel link.
- [x] Hardening matrix distinguishes new coverage, existing coverage, deferred risks, and non-applicable items instead of overclaiming.
- [x] J1 and console Excel regression specs remain required gates alongside the new vertical spec.
- [x] Final verification remains the AC9 gate set listed below and must be rerun after final bundle patches.

Round 3 result: PASS; proceed to final code review rerun.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-24 - Initial parallel Playwright run caused local port collisions; reran required E2E specs serially with `--workers=1`.
- 2026-05-24 - New vertical spec first exposed a test import/readback bug (`xlsxUtils` undefined, then `XLSX.readFile` unavailable under ESM); fixed the spec to use `XLSX.utils` and `readFileSync` + `XLSX.read`.
- 2026-05-24 - Code review follow-up added an explicit `api-key-manager` assertion before entering Excel surface.

### Completion Notes List

- Added a secondary `/welcome` entry to `/console/excel` using `Link href="/console/excel"` with `data-testid="welcome-excel-upload-link"`.
- Added `e2e/tests/laozhang-excel-vertical-slice.spec.ts`, covering UI signup, welcome handoff, Inventory workbook upload, natural inventory detection, preview, demo/501 state, result download, and workbook parsing.
- Locked downloaded workbook assertions for input sheets, `Results`, `Summary`, forecast columns, demo status, source filename, source row count, and `/console/excel` generated_by metadata.
- Added hardening coverage matrix in the new spec and explicitly deferred/marked non-applicable items rather than overclaiming coverage.
- Ran local code review after implementation; one acceptance gap was found and fixed: welcome registered-state assertion now checks `api-key-manager` before clicking the Excel entry.

### File List

- `_bmad-output/stories/3-e-9-laozhang-vertical-slice-e2e.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/src/app/welcome/page.tsx`
- `e2e/tests/laozhang-excel-vertical-slice.spec.ts`

### Change Log

- 2026-05-24 - Story created and marked ready-for-dev.
- 2026-05-24 - Implemented `/welcome` Excel entry and 老张 Inventory vertical slice E2E.
- 2026-05-24 - Completed implementation code review, fixed API Key state assertion gap, and marked story done.

### Verification

- PASS - `pnpm --filter @opticloud/web test`
- PASS - `pnpm --filter @opticloud/web typecheck`
- PASS - `pnpm --filter @opticloud/ui test`
- PASS - `pnpm --filter @opticloud/ui typecheck`
- PASS - `pnpm --dir e2e exec playwright test tests/j1-happy-path.spec.ts --project=chromium --workers=1`
- PASS - `pnpm --dir e2e exec playwright test tests/console-excel.spec.ts --project=chromium --workers=1`
- PASS - `pnpm --dir e2e exec playwright test tests/laozhang-excel-vertical-slice.spec.ts --project=chromium --workers=1`
- PASS - `pnpm --dir e2e typecheck`
- PASS - `git diff --check`

---

## Create-Story Checklist Review

| Item | Status | Note |
|---|:-:|---|
| User story has As/I want/so that | ✅ | 老张 persona and vertical slice value stated. |
| ACs are testable | ✅ | ACs specify files, selectors, steps, workbook assertions, and commands. |
| Scope explicit | ✅ | Chart embedding, real solver, auth redesign, new deps, backend work excluded. |
| Dependencies declared | ✅ | 1.8 and 3.E.1-6/8 are listed. |
| Previous story learnings included | ✅ | Onboarding, download, and voice learnings included. |
| Architecture/test guardrails included | ✅ | Next/Playwright/SheetJS/local service constraints included. |
| Regression prevention included | ✅ | J1 + console-excel specs remain required gates. |
| LLM dev ambiguity reduced | ✅ | Direct navigation cheating, override cheating, and overclaimed hardenings are forbidden. |

Result: PASS - ready for dev-story.
