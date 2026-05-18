---
story_key: 0-13-playwright-e2e
epic_num: 0
story_num: 0.13
epic_name: Foundation
status: in-review
priority: 🟠 High (J1-J9 vertical slice E2E gate)
sizing: L (5-7 hours; R3 D1 refined — 9 tasks × 3-5 subtasks)
created_by: bmad-create-story
created_at: 2026-05-18
sources:
  - _bmad-output/planning/epics.md (Story 0.13 — Q-T2 added by AE-1+2)
  - _bmad-output/planning/ux-design-specification.md (UX-DR7 5 Critical Mermaid Flows)
  - _bmad-output/planning/architecture.md v2.2 (P74 Cross-Service Storybook Visual Regression)
  - apps/web/src/app/* (existing pages: /, /auth/signup, /welcome, /algorithms)
  - apps/auth-service/src/auth_service/routes.py (signup endpoint contract)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py (algorithms + optimizations)
dependencies:
  upstream:
    - 0-1-monorepo-scaffold (done)
    - 0-2-docker-compose (done)
    - 0-6-auth-scaffold (done)
    - 0-9-ui-tier1-stubs (done)
    - 1-1a-j1-signup-api-key (done) — J1 vertical slice
    - 1-1b-j1-confirmation-modal-postman (done)
    - 2-1-j1-algorithms-public-list (done)
    - 3-1-j1-lp-solve (done)
  downstream:
    - 1-12-j7-fraud-freeze-vertical-slice — J7 E2E target
    - 3-11-j2-lina-csv-vertical-slice — J2 E2E target
    - 3-e-9-laozhang-vertical-slice-e2e — 老张 Excel E2E target
    - 8-a-7-j9-whitehat-vertical-slice — J9 E2E target
---

# Story 0.13: Playwright E2E Test Framework

Status: **done**

## Story

As a **QA / 全栈开发者**,
I want **Playwright E2E 测试框架 + 1 J1 happy-path vertical slice E2E test 跑通**,
so that **未来 5 个 critical journey（J1 cURL / J2 CSV / 老张 Excel / J7 风控 / J9 白帽）都有自动化 E2E 测试基础设施，且 PR-level 可 trace 整条端到端流程**.

## Acceptance Criteria

1. **AC1 — Playwright 装好可跑 + service startup gating（R1-4 fix）**：
   - 新增 `e2e/` 目录在 repo root
   - `e2e/package.json` 含 `@playwright/test`、TypeScript 配置、`test` / `test:ui` / `test:headed` 脚本
   - `e2e/playwright.config.ts` 配置 3 浏览器（Chromium / Firefox / WebKit）+ baseURL `http://localhost:3000` + retries=2 (CI) + screenshot=on-failure + video=retain-on-failure
   - 跑 `pnpm install` + `pnpm -C e2e exec playwright install chromium` 成功
   - **playwright.config.ts 含 `webServer` config 或 `globalSetup`：跑测试前 wait-on `http://localhost:3000` + `:8001/healthz` + `:8002/healthz` 90 秒超时 → 不 ready 测试**不跑**而不是 flaky fail**

2. **AC2 — J1 Happy Path E2E test 跑通**：
   - 文件 `e2e/tests/j1-happy-path.spec.ts`
   - 步骤覆盖完整 J1 vertical slice：
     a. 访客打开 http://localhost:3000 → 看到 "让算法走出实验室" Landing
     b. 点 "立即注册" → 跳到 `/auth/signup`
     c. 填随机 phone + **prefix=`e2e-${runId}-`** 邮箱（R1-5 cleanup fix）→ 点提交
     d. 自动跳转 `/welcome` → 看到 API Key Modal
     e. 关 Modal → 看到 APIKeyManager 卡片 + masked sk-XXX_••• prefix
     f. 点 "🧪 试跑 LP 求解" → 等结果出现
     g. 验证显示 `objective` + `solution.x` + `provider_url: https://highs.dev/`
   - **assert 用范围而非精确值 (Q2 fix — LP 可能多 optimal)**：
     - `expect(objective).toBeCloseTo(15.0, 1)` (Hello World 案例 1 物流题精度 1 decimal)
     - `solution.x` 长度 = 6，每元素 ∈ [0, 1]
     - 不 assert 具体哪辆车选哪客户（可能多解）
   - 跑 `pnpm -C e2e exec playwright test j1-happy-path --project=chromium` → **exit code 0 + 0 failed + 0 flaky + 1+ test passed**（R1-7 fix）
   - **Cross-browser policy (Q1 fix)**：CI 默认仅 chromium（速度）；nightly cron + main branch 增 firefox + webkit；**PR 阶段不阻塞跨浏览器**

3. **AC3 — Helpers + fixtures 复用基础**：
   - `e2e/fixtures/auth.ts` 含 `signupRandomUser()` helper（避免每个 test 重写注册逻辑）
   - `e2e/fixtures/api.ts` 含 `apiClient()` helper（直接 POST 到 auth-service / solver-orchestrator）
   - 后续 J2 / 老张 / J7 / J9 测试可复用

4. **AC4 — Algorithms public catalog smoke test**：
   - 文件 `e2e/tests/algorithms-catalog.spec.ts`
   - 不需登录访问 http://localhost:3000/algorithms
   - 验证 ≥8 个算法卡片渲染（Q3 fix — `count >= 8` 因 catalog 可扩）
   - 卡片含 k_algo / tier / provider_url 链接可点击
   - 测试 tab filter "优化 (T1-T6)" → 仅 T-prefix 显示
   - 跑通：**exit code 0 + 0 failed + ≥1 test passed** (R1-7 fix)

5. **AC5 — CI 集成（headless Chromium only） — R1-6 细化**：
   - 新增 `.github/workflows/e2e.yml`
   - 触发条件：PR / push to main 改动 apps/web/** 或 apps/auth-service/** 或 apps/solver-orchestrator/** 或 e2e/**
   - 步骤明细：
     1. checkout + setup-node + setup-python + uv install
     2. `docker-compose -p opticloud up -d postgres redis vault minio localstack`（含 Postgres init schema）
     3. `uv sync --all-packages --extra dev` + 启 auth-service `uvicorn ... --port 8001 &` + 启 solver-orchestrator `... --port 8002 &`
     4. `pnpm install` + `pnpm -C apps/web build` + `pnpm -C apps/web start &`
     5. `npx wait-on http://localhost:8001/healthz http://localhost:8002/healthz http://localhost:3000 --timeout 90000`
     6. `pnpm -C e2e exec playwright install chromium --with-deps`
     7. `pnpm -C e2e exec playwright test --project=chromium`
     8. on failure: `upload-artifact` Playwright `test-results/` + `playwright-report/` **with `retention-days: 7`** (S3 fix — 短 retention 减小 secret 泄露窗口)
     9. **预处理 trace/video：S2 fix — 上传前跑 `scripts/redact-secrets.sh` 把 trace/video/screenshots 内 `sk-[A-Za-z0-9_-]{30,}` 替换为 `sk-REDACTED`**（防止 reveal Modal 截图含真 key 公开）
     10. **D4 fix — 缓存**：`actions/cache@v4` 缓存 `~/.cache/ms-playwright` + `node_modules/.pnpm` + `~/.cache/uv` （key = `os + lockfile hash`）—— 减半构建时间
   - 注：CI 中 Vault unhealthy 不影响 demo (auth-service 用 env var fallback)，CI 标 `continue-on-error: true` 限定 vault container

6. **AC6 — Test data cleanup（R1-5 新增）**：
   - 所有 E2E 创建的用户 email 含 prefix `e2e-${runId}-`
   - 新增 `e2e/scripts/cleanup.sh` 跑 SQL：`DELETE FROM users WHERE email LIKE 'e2e-%';` (CASCADE 删 api_keys + audit_logs + optimizations)
   - CI 在 test job 最后（不论成败）跑 cleanup
   - 本地 dev 跑 `pnpm -C e2e cleanup` 触发

7. **AC7 — README + 跑测命令清晰**（原 AC6 重编号）：
   - `e2e/README.md` 含：
     - 本地开发前置（docker-compose + 3 services running）
     - `pnpm -C e2e exec playwright test` 命令
     - `pnpm -C e2e exec playwright test --ui` 交互模式
     - 如何加新 journey test 步骤（≤10 行模板）
     - **cleanup 命令** (R1-5 fix)
     - **failure 截图 / video / trace 在哪看**（U2 fix — `e2e/test-results/{test-name}/` + `playwright show-report`）
     - **VS Code Playwright extension 推荐**（U1 fix — `--ui` flag + 断点调试）

8. **AC8 — webServer config 统一本地 + CI（A2 fix）**：
   - playwright.config.ts `webServer` 数组 3 entries（auth + solver + web）
   - 用 `command` + `port` + `reuseExistingServer: !process.env.CI`
   - **本地**：Playwright 自动 spawn services（如未启动则启动）
   - **CI**：CI workflow 已外部启动 → `reuseExistingServer: true` 直接复用
   - baseURL 用 env var `PLAYWRIGHT_BASE_URL ?? "http://localhost:3000"`（A3 fix）


## Tasks / Subtasks

- [ ] **Task 1 (AC1) — Playwright 安装 + 配置**
  - [ ] 1.1 创建 `e2e/` 目录 + `package.json` + tsconfig
  - [ ] 1.2 写 `playwright.config.ts` 3 browser + baseURL + retries + traces
  - [ ] 1.3 装 deps: `pnpm install` + `playwright install chromium`
  - [ ] 1.4 跑 `playwright test --list` 验证发现机制

- [ ] **Task 2 (AC3) — Helpers + fixtures**
  - [ ] 2.1 写 `e2e/fixtures/auth.ts` — signupRandomUser() 返回 {jwt, apiKey, email, phone}
  - [ ] 2.2 写 `e2e/fixtures/api.ts` — apiClient() 直调 service
  - [ ] 2.3 写 `e2e/fixtures/index.ts` 统一 export + extend Playwright `test` fixture

- [ ] **Task 3 (AC2) — J1 Happy Path E2E test**
  - [ ] 3.1 写 `e2e/tests/j1-happy-path.spec.ts` — 7 步流程
  - [ ] 3.2 含 mock-real divergence assert（验证 highs `provider_url` 出现）
  - [ ] 3.3 跑通：`pnpm -C e2e exec playwright test j1-happy-path`

- [ ] **Task 4 (AC4) — Algorithms catalog smoke test**
  - [ ] 4.1 写 `e2e/tests/algorithms-catalog.spec.ts`
  - [ ] 4.2 含 tier filter 测试 + provider_url 链接 assert
  - [ ] 4.3 跑通

- [ ] **Task 5 (AC5) — CI workflow** (R1-6 细化)
  - [ ] 5.1 写 `.github/workflows/e2e.yml` 含 8 步明细
  - [ ] 5.2 docker-compose up Postgres+Redis+Vault+MinIO+LocalStack
  - [ ] 5.3 启动 3 services (background processes) + wait-on 90s timeout
  - [ ] 5.4 `playwright install --with-deps chromium`
  - [ ] 5.5 跑 test + upload-artifact on-failure (screenshots / videos / traces)

- [ ] **Task 6 (AC6) — Test data cleanup（R1-5 新增）**
  - [ ] 6.1 写 `e2e/scripts/cleanup.sh` (SQL DELETE WHERE email LIKE 'e2e-%')
  - [ ] 6.2 e2e/package.json 加 `cleanup` script
  - [ ] 6.3 CI workflow 最后 step 跑 cleanup（不论 test 成败）

- [ ] **Task 7 (AC7) — 文档**
  - [ ] 7.1 写 `e2e/README.md`（前置 / 命令 / 加新 test 模板 + cleanup + failure 调试 + VS Code 推荐）

- [ ] **Task 8 (AC8) — webServer config 统一**（A2/A3 新增）
  - [ ] 8.1 playwright.config.ts `webServer` 数组配 3 services
  - [ ] 8.2 `reuseExistingServer: !process.env.CI` 本地自动 spawn / CI 复用
  - [ ] 8.3 baseURL 用 PLAYWRIGHT_BASE_URL env var

- [ ] **Task 9 (S2 — 安全)** — Secret redaction script for CI artifacts
  - [ ] 9.1 写 `e2e/scripts/redact-secrets.sh` regex 替 `sk-[A-Za-z0-9_-]{30,}` → `sk-REDACTED`
  - [ ] 9.2 CI workflow upload 前调用

## Dev Notes

### 为什么 Q-T2 加这个 story

Code Review Gauntlet AE Round 1+2 发现：J1/J2/老张/J7/J9 5 vertical slice 都需 E2E 验证，但没有共用框架 → 每条 vertical slice 自己写 → carries forward inconsistency + maintenance burden. Q-T2 把基础设施统一提到 Sprint 0。

### 🚨 CI artifact secret redaction (Round 2 S2)

Playwright 在 test fail 时会自动截 screenshot + 录 video + 存 trace —— 这些**可能含 ConfirmationModal "Reveal" 按钮点击后的真 `sk-xxx` API Key**。直接 upload-artifact 到 GitHub Actions = public repo 任何人能下载查看。

**Mitigation**：CI workflow upload-artifact 前跑 `e2e/scripts/redact-secrets.sh`：
```bash
# Regex replace in screenshots/videos/traces
find test-results/ -type f \( -name '*.png' -o -name '*.webm' -o -name '*.zip' \) -exec ... # png/webm 不能简单文本替换
find test-results/ -type f -name '*.json' -exec sed -i 's/sk-[A-Za-z0-9_-]\{30,\}/sk-REDACTED/g' {} \;
```

**长期改进** (post-Sprint 0)：Playwright `page.addInitScript(() => Object.defineProperty(window, '__playwright_e2e__', { value: true }))` + Modal 内 `if (window.__playwright_e2e__) showFakeKey()`。但本 story 范围内 redaction 够用。

### Boundary vs Story 0.5b Schemathesis / Story 0.11 Storybook+Chromatic（R1-1 fix）

| 工具 | 测什么 | 范围 |
|---|---|---|
| **Storybook + Chromatic** (Story 0.11) | packages/ui 单 Component 渲染 | 隔离，无后端 |
| **Schemathesis** (Story 0.5b foundation, Story M3.2 full) | API contract — 单 HTTP endpoint 的 schema 边界 | 无 UI 参与 |
| **Playwright E2E** (本 story) | 完整 journey：browser → web → auth-service → solver-orchestrator → DB | 真浏览器 + 真后端 |

不重叠 — 各自看不同切面。Storybook 关心"按钮长啥样"，Schemathesis 关心"HTTP 接口合 spec 不合"，Playwright 关心"用户从注册到求解能不能跑完"。

### Web app selector 实例参考（R3 D3 fix — dev 抄即用）

apps/web/ 已有以下 selectors，写 E2E 测试可直接用：

| Page | Element | Selector |
|---|---|---|
| `/` Landing | "立即注册" CTA | `getByRole('link', { name: '立即注册' }).first()` |
| `/` Landing | Hero H1 | `getByText('让算法走出实验室')` |
| `/auth/signup` | 手机号 input | `getByLabel('手机号')` 或 `getByPlaceholder('+8613800138000')` |
| `/auth/signup` | 邮箱 input | `getByLabel('邮箱')` |
| `/auth/signup` | Submit | `getByRole('button', { name: /立即注册/ })` |
| `/welcome` | ConfirmationModal | `getByTestId('confirmation-modal')` |
| `/welcome` | APIKeyManager | `getByTestId('api-key-manager')` |
| `/welcome` | 复制 cURL | `getByRole('button', { name: /复制 cURL/ })` |
| `/welcome` | 导入 Postman | `getByRole('button', { name: /导入 Postman/ })` |
| `/welcome` | 🧪 试跑 LP | `getByRole('button', { name: /试跑 LP 求解/ })` |
| `/welcome` | LP 结果面板 | `getByText('求解完成')` (出现 = LP done) |
| `/algorithms` | 算法卡 | `getByTestId('algorithm-card')` (有多张) |

### Selector strategy（R1-2 fix）

Playwright 推荐 selector 优先级：
1. `getByRole('button', { name: '立即注册' })` — Role-based（无障碍 + 最稳）
2. `getByLabel('手机号')` — Label-based（表单）
3. `getByTestId('confirmation-modal')` — data-testid 兜底（Tier 1 Components 都有）
4. CSS class — **最后选**，因 className 重构频繁会脆

每个 spec 文件**先用 role/label 找**；找不到再 fallback testid。

### 为什么 `e2e/` 在 repo root 而不是 `apps/e2e/`（R1-3 fix）

- E2E 测试**跨多个 apps**（web + auth-service + solver-orchestrator）— 不属于任何单 app
- 与 `infra/`、`scripts/`、`docs/` 同级 — repo-wide concern
- pnpm-workspace 已支持 root-level workspace member

### Playwright vs 其他选择

- **Cypress**: 单浏览器（仅 Chromium-based）+ proprietary protocol — Playwright 多浏览器更适合 OptiCloud 跨浏览器 SLA (PRD NFR-B Chrome+Edge+Safari+Firefox latest 2)
- **Selenium**: 老 stack，慢，flaky — 不选
- **Puppeteer**: 只 Chromium，但 Playwright 由原 Puppeteer 团队做、API 兼容、功能更全 — 选 Playwright

### 与 packages/ui Storybook + Chromatic 的边界

- **Storybook + Chromatic** (Story 0.11, done): packages/ui Component 单元 visual regression — 隔离 component
- **Playwright E2E** (本 story): apps/web + 后端 services 端到端集成 — 完整 journey
- 不重叠 — Storybook 关心 "Component 渲染对不对"，Playwright 关心 "用户点完整流程能不能跑通"

### 依赖 services running

本 story 测试前提：
- docker-compose 5 容器 healthy (postgres + redis 主要；vault unhealthy 不影响)
- auth-service :8001 healthy
- solver-orchestrator :8002 healthy
- web :3000 ready

CI workflow（Task 5）会自动启动这些。本地开发跑 `HOWTO-local-demo.md` 启动方式即可。

### 不要做的事

- ❌ E2E 测试**不**复用 web app 内部组件 import — 走真实浏览器
- ❌ E2E test **不**直 mock fetch — 用 Playwright 的 `page.route()` 拦截（如果需要的话），但 J1 happy path 不需要
- ❌ 不在 E2E spec 里写复杂业务逻辑 — fixture 抽出复用
- ❌ 不依赖 hardcoded user — `signupRandomUser()` 每次跑用随机手机+邮箱

### 已知 limitation

- Playwright Chromium 在 Windows 上偶尔需要 admin 权限装。
- 中文路径 `D:\优化预测网站` 在 Playwright trace viewer 偶尔显示乱码 — 不影响 test result。
- CI 中 ARM Mac runner 较慢，建议 ubuntu-latest（已选）。

### Project Structure Notes

```
opticloud/
├── e2e/                                  ← 本 story 新增
│   ├── package.json
│   ├── tsconfig.json
│   ├── playwright.config.ts
│   ├── fixtures/
│   │   ├── index.ts                      (extend Playwright test)
│   │   ├── auth.ts                       (signupRandomUser)
│   │   └── api.ts                        (apiClient)
│   ├── tests/
│   │   ├── j1-happy-path.spec.ts
│   │   └── algorithms-catalog.spec.ts
│   ├── playwright-report/                (gitignored)
│   ├── test-results/                     (gitignored)
│   └── README.md
└── .github/workflows/e2e.yml             ← 本 story 新增
```

更新 `.gitignore` 加 `e2e/playwright-report/`, `e2e/test-results/`, `e2e/node_modules/`.

更新 `pnpm-workspace.yaml` 加 `"e2e"` workspace member.

### 本地 reproduce CI failure（R3 D5 fix）

如果 CI 跑挂、本地跑通：

1. 看 CI artifact `playwright-report/index.html`（download from Actions tab）
2. 本地 clone artifact 跑 `pnpm -C e2e exec playwright show-trace test-results/.../trace.zip`
3. 验本地版本 lock：
   - Playwright 版本：`pnpm -C e2e exec playwright --version`
   - Chromium 版本：`pnpm -C e2e exec playwright install --dry-run chromium`
4. 如版本 mismatch → 跑 `pnpm -C e2e install --frozen-lockfile && pnpm -C e2e exec playwright install chromium`

### Testing Standards

- Playwright Test Runner（不用 jest / vitest 直接对 e2e）
- TypeScript strict
- Each test independent — `test.describe.configure({ mode: 'parallel' })`
- Use `test.step()` for readable step output
- No hard-coded data — random fixtures only

### References

- [Source: epics.md Story 0.13 — Q-T2 AE-1+2 Round]
- [Source: epics.md Story 1.1a/1.1b/2.1/3.1 — J1 vertical slice already done]
- [Source: ux-design-specification.md UX-DR7 5 Critical Mermaid Flows]
- [Source: architecture.md v2.2 P74 Cross-Service Visual Regression — Playwright E2E 互补]
- [Source: apps/web/src/app/welcome/page.tsx — "🧪 试跑 LP" button selector]
- [Source: HOWTO-local-demo.md — services startup procedure]

## Dev Agent Record

### Agent Model Used

(populated by /bmad-dev-story after implementation)

### Debug Log References

### Completion Notes List

### File List

预计新增（≥ 10 files）：
- `e2e/package.json`
- `e2e/tsconfig.json`
- `e2e/playwright.config.ts`
- `e2e/fixtures/index.ts`
- `e2e/fixtures/auth.ts`
- `e2e/fixtures/api.ts`
- `e2e/tests/j1-happy-path.spec.ts`
- `e2e/tests/algorithms-catalog.spec.ts`
- `e2e/README.md`
- `.github/workflows/e2e.yml`

预计修改：
- `.gitignore` (+ e2e/playwright-report/ + e2e/test-results/)
- `pnpm-workspace.yaml` (+ e2e workspace member)

## Validated Outcome (R3 D2 fix)

跑通的可验证命令：

```bash
# 1. 装 deps
cd D:\优化预测网站
pnpm install
pnpm -C e2e exec playwright install chromium

# 2. 启 services（如未启动）
docker-compose -p opticloud up -d
uv sync --all-packages --extra dev
# Terminal 1: auth-service
PYTHONPATH="..." .venv/Scripts/python.exe -m uvicorn auth_service.main:app --port 8001 &
# Terminal 2: solver
PYTHONPATH="..." .venv/Scripts/python.exe -m uvicorn solver_orchestrator.main:app --port 8002 &
# Terminal 3: web
pnpm -C apps/web dev &

# 3. 跑 E2E
pnpm -C e2e exec playwright test --project=chromium

# 期望（exit 0）:
# Running 2 tests using 1 worker
#   ✓  algorithms-catalog.spec.ts (X.Xs)
#   ✓  j1-happy-path.spec.ts (Y.Ys)
# 2 passed (Z.Zs)

# 4. UI mode 调试
pnpm -C e2e exec playwright test --ui

# 5. 清理 E2E 测试数据
pnpm -C e2e cleanup
```

## Definition of Done

- [ ] All 9 tasks marked complete
- [ ] All 8 ACs satisfied
- [ ] ≥2 E2E tests passing (chromium, exit 0)
- [ ] `webServer` config 本地自动 spawn services 工作正常
- [ ] CI workflow 跑通 + retention=7d artifact + redact-secrets 应用
- [ ] cleanup script 清掉本次 E2E 创建的所有 users (DB SELECT 验证 `email LIKE 'e2e-%'` count = 0)
- [ ] No regressions in other test suites
- [ ] File List complete
- [ ] README 含 5 sections (前置/命令/加新 test/cleanup/debug)
