---
story_key: 3-e-1-excel-drop-zone
epic_num: 3.E
story_num: 3.E.1
epic_name: Console Excel Upload-Download UX
status: ready-for-dev
priority: 🔴 Critical (FG1.2 老张 sub-persona; UX-DR1 Tier 1; opens new domain Epic 3.E pivot)
sizing: M (~3-4 hours; component already exists in packages/ui — story scope is the Console page wire-up + UX polish + tests)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L1469-1474 (Story 3.E.1 spec + CRG13 actionable hint AC)
  - _bmad-output/planning/epics.md L1467 (Epic 3.E goal — 老张 Excel ≤5MB / 50K rows)
  - _bmad-output/planning/epics.md L76 (FR E11 — Excel upload-download v1 末 必上)
  - _bmad-output/planning/epics.md L817-818 (老张-1 chart embedding / 老张-2 Brand Voice "友好版")
  - packages/ui/src/components/ExcelDropZone/index.tsx (existing component — 0.9 Tier 1 stub)
  - packages/ui/src/components/FilePicker/index.tsx (shared, S3 fix)
  - apps/web/src/app/algorithms/page.tsx (Console page pattern reference from 2.2)
dependencies:
  upstream:
    - 0-9-ui-tier1-stubs (done) — ExcelDropZone + FilePicker stubs in packages/ui
    - 0-12-a11y-hook-axe-core (done) — useA11y hook used by both components
    - 0-13-playwright-e2e (done) — E2E harness pattern
  downstream:
    - 3-e-2-excel-task-type-detect — parses .xlsx headers/sheets to recommend task_type (this story exposes the File via onFile callback; .2 owns the parser)
    - 3-e-3-vrptw-template + 3-e-4-schedule-template + 3-e-5-inventory-template — templates that 3.E.2 routes to
    - 3-e-6-excel-result-download — return path
    - 3-e-9-laozhang-vertical-slice-e2e — end-to-end (will use this Console page as entry)
---

# Story 3.E.1 — ExcelDropZone Console Page (FG1.2 / FR E11 v1 entry)

## User Story

**As** 老张（制造业工艺工程师，不写代码，每天打开 Excel 排班/调度），
**I want** 一个公开的 Console 页面，把 .xlsx 拖到大方框里，2 秒看到「✅ 已收到您的 Excel 文件 — <filename> (<sizeMB>MB)」+ 进度条，
**so that** 我立刻知道文件被接住了、不用怕传了一半丢了 — 即使最终求解还没接通（3.E.2-6 在路上），我也愿意把这个工具推荐给我的同事，因为「这玩意儿至少没把我吓跑」。

## Why this story

OptiCloud 当前所有 surface 都是开发者向（cURL / Postman / SDK / 算法目录）。**老张是 v1 必拿的非开发者 persona**（FG1.2 Critical），他买不买单决定 OptiCloud 能否打入制造业 / 排班 / VRPTW 这些「应用方都是 Excel 用户」的细分市场。

UX 调研结论（PMR6 + 老张-2）：老张这类用户对 SaaS 的第一印象决定生死 — 上传文件后如果**任何**地方让他怀疑「我是不是传错了 / 我的数据丢了 / 我现在该干啥」，他就关闭浏览器并告诉同事「这玩意儿不行」。具体怕的事：

1. **alert() 弹窗** — 老张以为系统坏了，关页面
2. **无反馈** — 老张以为没传上去，刷新页面（实际上确实传了，但他自己删掉了）
3. **英文报错** — 老张直接放弃
4. **没法看「文件被接住的样子」** — 安全感缺失

所以这一 story 干 4 件事：

1. **建一个 Console 页面**（`/console/excel`，公开可达）作为老张 surface 入口 — 大方框居中，文字「拖 .xlsx 到这里」
2. **重构 ExcelDropZone**：把 `alert()` 换成可控的 `onReject(reason)` 回调，让父页面用 StatusCard 渲染**actionable hint**（CRG13），避免 alert 弹窗体验
3. **加成功态 UI**：拖入合法文件后，组件本身保持中性（只触发 onFile），但父页面立刻渲染「✅ 已收到您的 Excel 文件 — <filename> (X.XMB)」+ LoadingShimmer 进度条（老张-2 Brand Voice "实证克制 友好版"）
4. **加教程链接**（CRG13 一键跳教程）：拒绝态 hint 里挂 "📖 看教程：如何拆分大 Excel" 链接到 `/docs/excel-upload-faq`（这一目标先 stub 成 `<a>` 占位，真实文档随 3.E.6 / 3.E.9 落地）

**关键：3.E.1 不做 .xlsx 解析、不做行数校验、不做 task_type detect、不做求解**。这些是 3.E.2-6 的事。本 story 只解决「老张第一眼安全感」+「我能上传」的入口。

## Out of scope

- **行数 ≤50K 校验** — 需要解析 .xlsx workbook（client-side 需 `exceljs` / `xlsx` lib）。3.E.2 拥有 parser；3.E.1 仅做 size ≤5MB（component 已实现）+ 文件名/MIME sanity 检查。Epic spec 提及 50K rows 但作为 Epic 全局目标，单 story 拆分由各 sub-story 共同覆盖
- **task_type 自动 detect** — 3.E.2
- **业务模板（VRPTW / Schedule / Inventory）** — 3.E.3 / 3.E.4 / 3.E.5
- **求解 + 结果下载** — 3.E.6 / 3.E.7
- **后端 upload 端点** — 3.E.2 会引入 `POST /v1/excel/parse` 或类似端点；3.E.1 不上传任何字节到后端，纯前端接收（onFile 后存于 React state 供后续 story 消费）
- **chart embedding** — 老张-1，3.E.7
- **端到端 vertical slice** — 3.E.9
- **多文件上传** — FR E11 未要求；FilePicker `multiple={false}` 保持
- **JWT 鉴权** — 老张 Console 入口公开可达（与 `/algorithms` 同保守开放策略；后续 Console 内"求解触发"按钮再加 signup gate，本 story 不做）
- **后端 antivirus / sandbox 扫描** — M3 sandbox-io 工作流（M3.1）；本 story 仅在浏览器内接收 File 对象

## Acceptance Criteria

### AC1: ExcelDropZone API 调整 — 加 onReject 回调，去掉 alert()

修改 `packages/ui/src/components/ExcelDropZone/index.tsx`:

1. 新增可选 prop:
   ```ts
   onReject?: (reason: { code: "too_large" | "wrong_type"; message: string; sizeMB?: string; maxMB?: string }) => void;
   ```
2. 删除组件内 `alert(...)` 调用；改为：
   - 如果 `onReject` 提供 → 调用 `onReject({ code: "too_large", ... })`
   - 如果 `onReject` 未提供 → fallback 到 `console.warn`（保留组件作为孤立可用的 stub，但不再弹 alert）
3. 新增 wrong_type 分支：drop 进来的文件如果不是 `.xlsx` 后缀（大小写不敏感）→ 调用 `onReject({ code: "wrong_type", ... })`。理由：以前组件只接 `dataTransfer.files[0]` 不校验后缀，如果老张拖了个 .pdf 就静默把 File 传给父页面，父页面再拒绝又显得"系统两次报错"
4. JSDoc 头注释更新，反映新的 API + 兼容性说明（onReject 是可选 — 既有 0.9 stub 的旧用法不破）

### AC2: 同步更新 FilePicker — 加 onReject 回调，去掉 alert()

同样在 `packages/ui/src/components/FilePicker/index.tsx`:

1. 新增 `onReject?: (reason: { code: "too_large"; sizeMB: string; maxMB: string; message: string }) => void;`
2. 删除 `alert(...)` 调用；改为同 AC1 的 onReject / console.warn fallback
3. FilePicker 也支持 accept 后缀过滤（HTML input 原生），所以 wrong_type 分支在 FilePicker 由浏览器原生 dialog 拦掉 — 仅 too_large 走 onReject

### AC3: 新建 Console Excel 页面 `/console/excel`

在 `apps/web/src/app/console/excel/page.tsx` 新建客户端组件页面：

1. 页面布局：
   - Header 同 `/algorithms` 风格（OptiCloud logo + 返回首页 + 注册按钮）
   - Hero 区："上传 Excel，自动求解" + 一行说明 "适合 VRPTW / 排班 / 库存 — 不写代码"
   - 主区：居中的 `<ExcelDropZone>` (max-w-2xl)
2. State 机:
   ```
   idle → file_received (onFile triggered) → [其他 story 接管]
   idle → file_rejected (onReject triggered) — 显示 actionable hint
   ```
3. **成功态** (file_received)：
   - 替换 DropZone 为一张 `StatusCard variant="success"` (data-testid="excel-received-card")，title "✅ 已收到您的 Excel 文件"，description = `${file.name} · ${(file.size/1024/1024).toFixed(2)} MB`
   - 文件名渲染加 `className="truncate max-w-md"` — 极端长文件名安全
   - 紧跟一段 `LoadingShimmer` + 文字 "解析中..."（这里**纯模拟**进度条 — 3.E.2 才接 parser；本 story 用 `useEffect` + `setTimeout 2000ms` 后切换到 "📋 下一步：3.E.2 将自动识别 task_type" 占位说明）
   - **useEffect cleanup 必要**：return `() => clearTimeout(timerId)` 防止 unmount 后 setState warning
   - 显示一个 "重新选择文件" 按钮 (data-testid="excel-reset-button") — 恢复 idle 态
4. **拒绝态** (file_rejected)：
   - 显示 `StatusCard variant="warning"` (or "error" for wrong_type)，data-testid="excel-rejected-card"
   - title = 根据 code: `"文件过大"` / `"不支持的文件类型"`
   - description = reason.message
   - actionable hint 内联 `<ul>` 列出 CRG13 三步建议（仅 too_large 时显示），并附 "📖 看教程：如何拆分大 Excel" 链接 → `/docs/excel-upload-faq`（AC4 stub 保证非 404）
   - 显示 "重试" 按钮 (data-testid="excel-reset-button" — 与成功态复用 testid，因为两态互斥) — 恢复 idle 态

### AC4: 文档 stub `/docs/excel-upload-faq`

为了让 CRG13 链接不 404，在 `apps/web/src/app/docs/excel-upload-faq/page.tsx` 加一个**最小** static page (10 行)：

- h1 "Excel 上传常见问题"
- 三段：
  1. ".xlsx 文件超过 5MB 怎么办" — 三步建议（删 sheet / 拆分 / 转 CSV）
  2. ".xls (老格式) 不支持怎么办" — 在 Excel "另存为 .xlsx"
  3. "我的文件有图表 / 公式怎么办" — "OptiCloud 只读取单元格值；图表/公式不影响"

这个 stub 是 3.E.9 vertical slice 落地时会扩展的；3.E.1 只保证链接不 404。

### AC5: Vitest — 覆盖新行为

扩展 `packages/ui/src/components/ExcelDropZone/__tests__/index.test.tsx`（新建测试文件 — 当前 ExcelDropZone 仅有 stories + a11y test）：

1. `test("triggers onFile when valid .xlsx is dropped")` — 用 `File` 构造一个 `.xlsx` (size < 5MB)，fireEvent drop → onFile called with the File
2. `test("triggers onReject with code=too_large when > 5MB")` — File size = 6MB → onReject called, code=too_large, sizeMB="6.0", maxMB="5"; onFile NOT called
3. `test("triggers onReject with code=wrong_type when .pdf is dropped")` — File name ends in `.pdf` → onReject called, code=wrong_type; onFile NOT called
4. `test("falls back to console.warn when onReject not provided and rejected")` — 不传 onReject、拖 6MB → spy on console.warn called once, no throw
5. `test("does NOT call alert() under any path")` — spy on `window.alert`, assert never called across all 4 scenarios above

Same for FilePicker — extend `packages/ui/src/components/FilePicker/__tests__/index.test.tsx` (also new file):

6. `test("triggers onFile on valid pick")` — File size < 5MB → onFile called
7. `test("triggers onReject with code=too_large on oversize pick")` — 6MB → onReject called
8. `test("falls back to console.warn when onReject not provided")` — no throw
9. `test("does NOT call alert() under any path")`

Vitest count: packages/ui 12 → **21** (+9 new tests). The 12 pre-existing Tier1.a11y failures unchanged.

### AC6: Playwright E2E — `/console/excel` 流程

Add `e2e/tests/console-excel.spec.ts`:

1. `test("访客可看到 /console/excel 入口 + DropZone 居中可见")` — goto `/console/excel`; assert h1 "上传 Excel" 可见; assert `getByTestId("excel-drop-zone")` 可见
2. `test("选择合法 .xlsx 显示成功态 + 文件名 + 模拟进度")` — Playwright drag-and-drop with File payload is brittle; **use `setInputFiles` on the underlying FilePicker `<input type='file'>`** (which is `sr-only` inside ExcelDropZone's fallback). Path verified: assert `getByTestId("excel-received-card")` 可见, contains the filename `small.xlsx`, contains `"MB"` (and 2s 后 contains 占位 "📋 下一步")
3. `test("选择过大文件触发拒绝态 + actionable hint + 教程链接")` — `setInputFiles` with the 6MB `oversized.xlsx` fixture; assert `getByTestId("excel-rejected-card")` warning StatusCard with "文件过大"; assert `<ul>` 列出 3 条 remediation; assert `getByRole("link", { name: /看教程/ })` `href` 包含 `/docs/excel-upload-faq`
4. `test("教程链接落地页存在且非 404")` — goto `/docs/excel-upload-faq`; assert h1 "Excel 上传常见问题" 可见
5. `test("点击重新选择 / 重试按钮恢复 idle 态")` — 触发成功态后点 `getByTestId("excel-reset-button")` → `getByTestId("excel-drop-zone")` 重新可见; 同样测拒绝态的 "重试" 按钮（同一 testid `excel-reset-button` 复用）

**注**: AC6 #2/#3 走 FilePicker fallback `<input>` 路径（公开 API），不直接测组件的 drop handler — drop 路径由 Vitest AC5 #1 覆盖。

**Fixture files**: create `e2e/fixtures/excel/small.xlsx` (~10 KB stub — 用 `node-xlsx` 写 OR 一个手工准备的小文件 OR 简单 Buffer 写到 binary `.xlsx` 内容的占位) + `e2e/fixtures/excel/oversized.xlsx`（6 MB binary blob — 不需要是有效 .xlsx，因为我们只测 size 校验）。

Playwright count: 7 → **12** (+5).

### AC7: Storybook story 更新

更新 `packages/ui/src/components/ExcelDropZone/index.stories.tsx`：

- 加 `ZhangLao老张Surface_AcceptOnly` (现有, onFile only — 兼容旧 stub)
- 加 `ZhangLao老张Surface_WithReject` (passes onReject + onFile — 演示新拒绝回调)

不强求 Chromatic visual snapshot 更新（Story 0.11 提供 Storybook 但 Chromatic visual gating 是 v1.5+）。

### AC8: 类型导出更新

`packages/ui/src/index.ts` — 重新导出新增的 `ExcelDropZoneRejectReason` 和 `FilePickerRejectReason` 类型（如果显式 export），方便 apps/web 引用。

### AC9: 质量门 (per `feedback_full_quality_gates`)

- `uv run ruff check apps packages` → 0
- `uv run ruff format --check apps packages` → 0
- `uv run mypy apps packages` → 0 (no Python changes — 回归保护)
- All Python regression — 214 Python tests via CI
- `pnpm -C apps/web build` → 0
- `pnpm -C packages/ui test` → 21 pass + 12 pre-existing a11y failures (unchanged)
- `pnpm -r typecheck` → 0
- E2E via CI

### AC10: NFR alignment

- **FR E11** — surface 入口落地（解析/求解/下载在后续 story；E11 的 size cap 5MB 在 component 实现，行数 50K 在 3.E.2）
- **CRG13** ✅ AC3 拒绝态 + 教程链接
- **老张-2** ✅ AC3 中文文案 + LoadingShimmer 进度（Brand Voice "实证克制 友好版"）
- **S3 fix** ✅ FilePicker 仍为单源；ExcelDropZone 复用 FilePicker fallback
- **NFR-A1 (a11y P0)** ✅ ExcelDropZone 已用 useA11y hook；新成功/拒绝态 StatusCard 已 a11y-audited (Story 0.12)
- **NFR-S** N/A 本 story 不上传到后端；File 对象仅在浏览器内存
- **NFR-P1** N/A 客户端纯 UI 渲染

## Tasks

### T1 — 组件 API 重构 (0.5h)
1. 修改 `packages/ui/src/components/ExcelDropZone/index.tsx`：加 `onReject` prop + wrong_type 分支 + 去 alert
2. 修改 `packages/ui/src/components/FilePicker/index.tsx`：加 `onReject` prop + 去 alert
3. `packages/ui/src/index.ts`：导出新增类型（如果独立 export）

### T2 — Vitest 测试 (0.75h)
1. 新建 `packages/ui/src/components/ExcelDropZone/__tests__/index.test.tsx`（注意：现有 a11y test 在 `Tier1.a11y.test.tsx` 顶层，不要污染那个文件）— 5 个 case (AC5 #1-5)
2. 新建 `packages/ui/src/components/FilePicker/__tests__/index.test.tsx` — 4 个 case (AC5 #6-9)
3. Run `pnpm -C packages/ui test` → 21 pass

**注**: Vitest 测试可能因 jsdom 不支持完整 DragEvent 而需要构造 mock `dataTransfer`。如不直接走 dataTransfer，可以直接调用组件内部 handler（不可行，handler 是私有的）— 折中方案：用 `fireEvent.drop(element, { dataTransfer: { files: [file] } })`。

### T3 — Console 页面 (1h)
1. 新建 `apps/web/src/app/console/excel/page.tsx` (use client) per AC3
2. State 机：`{kind: "idle"} | {kind: "received", file: File} | {kind: "rejected", reason: ExcelDropZoneRejectReason}`
3. 渲染 ExcelDropZone + 三态切换
4. data-testid 安排：`excel-drop-zone`（来自组件本身）, `excel-received-card`, `excel-rejected-card`, `excel-reset-button`

### T4 — 教程 stub 页 (0.1h)
1. 新建 `apps/web/src/app/docs/excel-upload-faq/page.tsx` — 静态最小内容

### T5 — Playwright E2E + 测试 fixture 文件 (0.75h)
1. 准备 fixture：
   - `e2e/fixtures/excel/small.xlsx` — 创建一个 ~10KB 的有效 .xlsx（最简单：在 Excel/LibreOffice 里 New → Save As → checkin；或者用 Node 脚本 `xlsx` lib 生成；或者复制一个 npm 包内置的 .xlsx 样本）
   - `e2e/fixtures/excel/oversized.xlsx` — 6MB 任意 binary blob（用 `Buffer.alloc(6 * 1024 * 1024, 'a')` 写 .xlsx 后缀即可，size 校验不查内容）
2. 新建 `e2e/tests/console-excel.spec.ts` — 5 个 test per AC6
3. 注意：Playwright 拖放 with File payload 不易 — 用 `setInputFiles` 走 FilePicker 内部 `<input>` 路径

### T6 — Storybook + 类型导出 (0.15h)
1. 扩展 `index.stories.tsx` per AC7
2. 检查 `packages/ui/src/index.ts` per AC8

### T7 — 质量门 + sprint sync + PR (0.5h)
1. 跑 AC9 全部
2. 更新 `_bmad-output/stories/sprint-status.yaml`
3. 提交 + PR + 等 CI + 合并

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Vitest jsdom 不完整支持 DragEvent / dataTransfer，drop 测试可能不能直接 fireEvent | 用 `fireEvent.drop(zone, { dataTransfer: { files: [file] } })` — testing-library 已支持构造 minimal mock dataTransfer。如确实不行，降级走 `<FilePicker>` 内部 input 路径（dispatch change event with files），不测 drag 路径 |
| 修改 ExcelDropZone API 破坏其他调用方 | 仅一处调用 — Storybook story (T6 一起更新)。`grep -r ExcelDropZone apps packages` 已扫，没有别的引用。`onReject` 是**可选**，旧用法不破 |
| Playwright fixture .xlsx 创建：手工或脚本 | 用最简方法 — 把一个已有的 npm 包内置 .xlsx 复制过来；或写一个 50 行 Node 脚本 `e2e/fixtures/excel/build.mjs` 用 `xlsx` lib 生成。优先复制以保 PR 小 |
| /docs/excel-upload-faq 是 stub — 内容不准 / 不规范 | AC4 明确这是 stub；3.E.6/3.E.9 会重写。在文件顶部加 `{/* Stub — 3.E.1 only ensures the route exists for CRG13 link */}` HTML 注释 |
| Console 页面与 /algorithms 风格不一致 | 复用相同 Header / Tailwind tokens / StatusCard / LoadingShimmer — 风格自动一致 |
| onReject 类型 (discriminated union) 可能在 strict TS 模式下让父组件需要 narrow check — 写出 `if (reason.code === "too_large")` 守卫 | 在 AC3 实现样例代码里展示守卫；不增加复杂度 |
| 老张-2 "进度条" 是模拟的（不是真 parsing 进度） | AC3 文案 "解析中..." 后切 "📋 下一步：3.E.2 将自动识别 task_type" 明确告知用户后续阶段；不假装做了 3.E.2 的事 |
| 老张拖了空文件 (`size = 0`) | 不在 5MB 上限内，不触发 too_large；但传给父页面后会显示文件名 + "0.00 MB"。可接受 — 真实问题在 3.E.2 parse 阶段会爆 |
| Setting `setInputFiles` in Playwright with a 6MB file may slow test | 6MB 是 Buffer.alloc，本地写入瞬间；Playwright 上传 6MB 到浏览器 input 也 < 200ms。可接受 |

## Non-Functional Requirements Mapping

- **FR E11** (Excel surface) — 入口 ✅；行数/解析/求解/下载在 3.E.2-7
- **FG1.2** (老张 Critical sub-persona) ✅ Console surface 落地
- **CRG13** ✅ AC1/AC3 — actionable hint + 教程链接
- **老张-2** ✅ AC3 — "已收到您的 Excel 文件" + LoadingShimmer + Brand Voice
- **UX-DR1 Tier 1** ✅ ExcelDropZone + FilePicker 演化为产品级（脱离 stub）
- **NFR-A1** ✅ useA11y + StatusCard a11y
- **NFR-S** N/A
- **NFR-P1** N/A

## Definition of Ready

- ✅ ExcelDropZone + FilePicker stub 在 packages/ui
- ✅ StatusCard + LoadingShimmer 在 packages/ui（成功/拒绝态依赖）
- ✅ Playwright 测试基建 + fixtures 目录在 e2e/
- ✅ 3 pass review 已做

## Definition of Done

- 10 ACs 全过
- Vitest packages/ui 12 → 21 (+9)
- Playwright E2E 7 → 12 (+5)
- CI 全绿（ts-typecheck + lint + ui-tests + web-build + e2e）
- sprint-status.yaml: `3-e-1-excel-drop-zone: done`
- Memory `opticloud-project-status.md` 更新 PR ref + 测试 count
- 手动 smoke：local dev → goto `/console/excel` → 拖一个 .xlsx → 看到 ✅ + 文件名 + 进度

## Sign-off

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| UX (老张 sub-persona) | TBA | ☐ | — |
| FE Lead | TBA | ☐ | — |
| Console PM | TBA | ☐ | — |

> Owner committee deferred per M0 skip.
