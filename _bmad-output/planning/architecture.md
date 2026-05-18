---
stepsCompleted:
  - step-01-init
  - step-02-context
  - step-03-starter
  - step-04-decisions
  - step-05-patterns
  - step-06-structure
  - step-07-validation
  - step-08-complete
status: complete
completedAt: 2026-05-17
lastStep: 8
inputDocuments:
  - D:\优化预测网站\_bmad-output\planning\prd.md
  - D:\优化预测网站\_bmad-output\planning\implementation-readiness-report-2026-05-17.md
  - D:\优化预测网站\_bmad-output\planning\SESSION-HANDOVER.md
  - D:\优化预测网站\网站方案.md
  - D:\优化预测网站\papers\ITADN\README.md
  - D:\优化预测网站\papers\ITADN\ITADN-对接问题回答.zh-CN.md
  - D:\优化预测网站\papers\optimize\README.md
  - D:\优化预测网站\papers\safety\README.md
documentCounts:
  prdCount: 1
  uxDesignCount: 0
  researchCount: 0
  projectDocsCount: 5
  readinessReportCount: 1
  handoverCount: 1
workflowType: architecture
project_name: OptiCloud（通用优化与预测服务网站）
user_name: 课题组
date: 2026-05-17
sourceDocument: prd.md（基于 网站方案.md v0.5.1）
elicitationHistory:
  - step-02-context party_mode_15 (5 agents: Winston/Amelia/Murat/Mary/Sally, applied W1-5 + A1-3 + M1-4 + My1-4 + S1-3, 17 enhancements all accepted)
  - step-03-starter party_mode_16 (5 agents: Indie/Amelia/Winston/Murat/Bob, applied I1-3 + A1-3 + W1-3 + M1-3 + B1-2, 12 enhancements all accepted, Option B → Option B-Lite)
  - step-04-decisions party_mode_17 (5 agents: Winston/Amelia/Murat/Indie/Mary, applied W1-5 + A1-3 + M1-4 + I1-5 + My1-3, 18 enhancements all accepted: ★5 major + 9 medium changes + R11 Risk + 8 Constraints C8-C15)
  - step-05-patterns party_mode_18 (5 agents: Winston/Amelia/Murat/Sally/Bob, applied W1-6 + A1-4 + M1-5 + S1-3 + B1-3, 20 new patterns P36-P55 + C16 all accepted)
  - step-06-structure party_mode_19 (5 agents: Indie/Winston/Amelia/Murat/Bob, applied I1-5 + W1-5 + A1-3 + M1-5 + B1-3, 24 enhancements all accepted: ★6 service-count changes + 6 new Patterns P56-P61 + 2 Constraints C17-C18; 14 services reduced to 10 deployable units)
  - step-07-validation party_mode_20 (5 agents: Murat/Mary/Indie/Winston/Amelia, applied M1-6 + My1-4 + I1-3 + W1-3 + A1-2, 22 enhancements all accepted: 3 Critical Gaps G3 escalated + G6 + G7, 9 Important Gaps G8-G15, 3 new Patterns P62-P64, 2 Constraints C19-C20, P59 upgraded to 4-tier fallback, C18 revised; readiness HIGH → HIGH-conditional)
---

# Architecture Decision Document — OptiCloud

> 本文档通过分步发现协作构建。章节随每个架构决策按追加方式生成。

---

## Project Context Analysis

### Requirements Overview

**Functional Requirements**：77 FR 跨 8 能力域（Capability Contract 锁定）

| 能力域 | FR # | v1 必上 | v1 末 | v2 | v3 |
|---|:---:|:---:|:---:|:---:|:---:|
| A. Account & Identity | 10 | 10 | — | — | — |
| C. Algorithm Catalog & Solver Selection | 8 | 8 | — | — | — |
| E. Optimization & Prediction Execution | 10 | 9 | — | 1 | — |
| N. Chat & Natural Language Modeling（AIGC gated）| 12 | — | 12 | — | — |
| B. Credits, Billing & Subscription | 13 | 13 | — | — | — |
| R. Reproducibility & Academic Integrity | 7 | 1 | 4 | 2 | — |
| P. Provider Integration & Marketplace | 8 | — | — | 8 | — |
| O. Observability, Risk & Compliance | 11 | 4 | 4 | 3 | — |
| **合计** | **77** | **45*** | **20** | **14** | **0** |

\* v1 必上口径含 1 项 Reproducibility（FR R5 BibTeX）；其余 R 域 v1 末交付。

**Non-Functional Requirements**：11 大类
1. Performance（API/Chat/求解分级 SLO + 沙箱性能）
2. Security（加密 / 认证 / 风控 / P0 零容忍）
3. Scalability（用户规模阶段 / DB / Vector / GPU / LLM 容量）
4. Reliability & Availability（SLA / 灾备 / 漏洞响应 / 计费可靠性）
5. Compliance（国内法定 / 学术复现）
6. Provider Integration（Shadow / 灰度 / 许可白名单）
7. Accessibility（WCAG 2.1 AA）
8. Localization & i18n
9. Browser & Platform Support
10. Observability & Monitoring
11. Cost & Unit Economics

### Scale & Complexity

| 维度 | 评级 / 值 |
|---|---|
| 项目复杂度 | **High**（标准档），enterprise-leaning at v2+ |
| 外部复杂度 | Medium（29 端点 v1 + 2 v2，REST 主，Chat 副，SSE）|
| 内部复杂度 | **High**（多 Agent + 沙箱 + Provider 路由 + 复现 + 多租户 + AIGC 合规）|
| 主技术域 | `api_backend`（主）+ `web_app`（Next.js SSR/CSR 混合）|
| 架构组件估算 | **~15-18 顶层服务/模块**（Step 6 服务拆分时定稿；含 Capability Registry / Revenue-Share 等占位）|
| 多租户 | ✅ Postgres schema-per-tenant + S3 namespace |
| 实时特性 | SSE 流式（Chat + 长任务进度通知）；不上 WebSocket |
| 合规要求 | ICP + 公安 + AIGC + 等保 2.0 二级（v1）/ 三级（v2-v3 按需）+ PIPL + 国密预留 |
| 集成复杂度 | DeepSeek + Qwen-Max + 7 类求解器 + 4 类时序模型 + Stripe/微信/支付宝 + gVisor + Vault + pgvector |

### Unique Technical Challenges

1. **AIGC 合规作为工程 hard-gate**（M3 末备案号未到 → API-only fallback；M5 暂停 Chat；M7 评估走向）
2. **Critic Agent 置信度 < 0.6 自动转人工**（红队测试集 M3 ≥30 / M5 ≥200 / v2 众包）
3. **Provider 自动迁移**（基于 capability 词表匹配 → 失败时人工复现 SLA）
4. **沙箱性能损耗 30-50% 已计入 SLO**
5. **算法许可白名单 PR 自动检查**（MIT/Apache 2.0/BSD 自由；EPL 仅调用不 fork；GPL/AGPL/SCIP/商业禁用）
6. **Idempotency-Key + Credits 不重复扣**（POST 必带，24h 缓存窗口）
7. **结果交付双轨**：同步 ≤5s 直接返；异步 202 + Location，SSE + 邮件 + 站内信三件套兜底
8. **Repro 5 年 Image 归档 + 等价 Provider 自动迁移**（业界首创，无对标）

### Technical Constraints & Dependencies

**PRD frontmatter 强制约束**（来自 `internal_high_constraint`）：
- M1 至多 1 个 high-risk 技术组件
- Vector DB → pgvector 起步（不上 Qdrant）
- LLM Router → 单一 DeepSeek，无切换（Qwen-Max 仅 incident 应急）
- i18n → 仅 zh + 关键页 en 兜底
- Provider Console → 月报邮件代替
- M1 季末未达成 80% 完成度，强制砍范围

**Architecture-Level Constraints**（party_mode_15 新增 4 项）：
- **C1**：v1 自研算法（AQGS-ACOPF / Trust-Tech / CPSOTJUTT / TT-KMeans / ITADN-AIGC）= **Python 直调**（pip install + Apache 2.0），**v2 起标准化为 Provider API 协议**（OpenAPI + Docker + 灰度）
- **C2**：测试环境必须有 **LLM mock + 算法 mock 抽象层**（DeepSeek 付费 API / HiGHS CPU 重负载 / Chronos 需 GPU；CI 不可每次跑真实算力）
- **C3**：**v1 Audit = Postgres `audit_log` 表 + 异步入库**；v2 末拆分独立 audit 库
- **C4**：v2 接口预留 **Revenue-Share Service**（自研 100/0 / 合作 60/40 / 商业 50/50；FR P8 v2 启用）

**外部依赖**：
- 阿里云 RDS Postgres + Redis + OSS（主）/ AWS（备份）
- DeepSeek-V3.5 API + Qwen-Max API（incident 应急 fallback）
- 微信支付 / 支付宝 / Stripe
- gVisor / Vault / GrowthBook / pgvector / Resend|Mailgun
- 求解器：HiGHS / OR-Tools / IPOPT / Bonmin / Couenne / CVXPY / SCS
- 时序基础模型：Chronos / TimesFM / Lag-Llama / Moirai

### Cross-Cutting Concerns Identified（19 项）

> 11 项原有 + 8 项 party_mode_15 新增（标 ⭐）

| # | Concern | 影响范围 |
|---|---|---|
| 1 | **多租户隔离** | DB / S3 / 审计 / Credits / Rate limit / Sandbox 全栈 |
| 2 | **同 / 异步混合** | 所有计算端点 + SSE + 邮件 + 站内信 |
| 3 | **i18n / 双语** | Accept-Language → 错误码 / NL Summary / Critic reasoning |
| 4 | **可观测** | 业务 metrics + 系统 metrics + Status Page + Postmortem |
| 5 | **幂等性** | 所有 POST + Credits 双写 + Provider fallback |
| 6 | **API 版本化** | URL `/v1/` + X-API-Version + 12 月 deprecation + X-API-Date v2 |
| 7 | **沙箱执行** | LLM Coder 输出 + 等价 Provider 离线评测 |
| 8 | **Provider 路由** | capability 词表 + fallback chain + shadow + 5%→50%→100% 灰度 |
| 9 | **复现保证** | voucher + Image 归档 + 自动迁移 + 5y SLA |
| 10 | **合规底盘** | AIGC filter + 等保 + PIPL 删除 + 国密预留 |
| 11 | **License hard rule** | PR 自动 license 检查 + EPL 不 fork 守门 |
| 12 ⭐ | **Capability Registry** | Repro 自动迁移 / Solver 选择 / Provider 路由 共用的能力词表；独立服务 |
| 13 ⭐ | **Distributed Billing Transaction** | 双写账本 + Idempotency + 退款 saga + 加油包永不过期；跨 5 端点 3 表的事务边界（决定 outbox/saga/2PC 选型）|
| 14 ⭐ | **Image Supply Chain** | 自研算法 Docker build → 签名 → 推送 → Repro 5y S3 Glacier 归档；R7 自动迁移工程前提 |
| 15 ⭐ | **Streaming Connection Lifecycle** | SSE keep-alive heartbeat / 断线 cursor 续传 / proxy 30s timeout 兼容 / chunk buffer 策略 |
| 16 ⭐ | **Worker Topology 分层** | real-time（求解 < 90s）/ batch（归档 / 月度对账）/ retry（Provider fallback）/ scheduled（红队跑批 / shadow validation） |
| 17 ⭐ | **Human-in-the-Loop Review Queue** | Critic 置信度 < 0.6 样本：入队 / 审 / 回写 / 时长 SLA |
| 18 ⭐ | **Internal SLA Telemetry Dashboard** | v1 内部埋 `monthly_uptime` / 求解成功率 / Chat 成功率；v1.5 起作为对外 SLA 升级承诺依据 |
| 19 ⭐ | **Console Frontend Stack** | 前端状态管理（Zustand/Jotai/RTK Query 选型）+ 表格虚拟化 + 图表库（ECharts/Recharts）+ SSE 客户端订阅 + Docs OpenAPI 渲染 + SEO structured data |

### Open Questions（Step 4-6 必决项）

| # | 问题 | 决策点 |
|---|---|---|
| Q1 | **Critic Agent 部署形态** | 流水线一环（与 Coder 同进程）vs 独立 SaaS 服务（独立扩缩 + 可被外部调用）→ Step 6 服务拆分时定 |
| Q2 | **AIGC Filter 拦截点** | NL 生成后 buffer 再 filter / 流式中断 / Critic agent 内嵌 → Step 5 模式决策 |
| Q3 | **API Docs Renderer** | Redoc / Stoplight Elements / 自建 → Step 4 技术栈决策 |

### FR Module Ownership 待补（Step 6 必须显式归属）

| FR | 待归属模块 | 备注 |
|---|---|---|
| **A4** 教育版 .edu/.ac.cn 自动激活 | Auth Service vs Compliance Service vs Marketing | 邮箱白名单逻辑归属 |
| **B10** PIPL 数据导出 JSON/CSV | Data Export Aggregator（新增）| 跨 Optimization / Prediction / Chat / Billing 4 个 store 聚合 |
| **O3** 用户审计日志查询 | Audit Service（v1 PG 表 / v2 分库）| 见 Constraint C3 |
| **P8** Provider 月度分润 | Revenue-Share Service（v2 启用）| 见 Constraint C4，v1 接口预留 |

### Journey-Architecture Mapping

| Journey | 涉及 FR | 跨切关注（# from above）|
|---|---|---|
| J1 李工 happy path | A1/A2/A9/C1/E1/E7/B1/B2 | 1,2,3,4,5,15,19 |
| J2 Lina 错误恢复 | E2/E7/B1/B2/B6/B12 | 1,2,3,4,13,15 |
| J3 王哲 incident | O1/O2/B5 | 4,7,8,13,16,18 |
| J4 吕教授+小赵 | A4/B8/R1-7/P1-8/O8/O11 | 1,8,9,12,14,17 |
| J5 陈架构师 | A2/C1/E1/B1/O10 | 1,2,5,10,19 |
| J7 风控冻结 | A5/A7/A8 | 1,10,17 |
| J8 AIGC 巡查 | O5/N5/N9 | 7,10,17 |
| J9 白帽 | O4 | 4,10 |

### Architecture-Driving Summary

总结上述分析后，**驱动 Step 3-7 决策的 7 大架构主线**（按优先级）：

1. **Multi-Agent NL→Model Pipeline + Sandbox**（Innovation #1 + #7 实现核心；Q1 + Q2 + 概念 #7 + #15 + #17）
2. **Capability Registry as Backbone**（Repro / Solver / Provider 三处共用；新增 #12）
3. **Distributed Billing Transaction**（双写 + 幂等 + 退款；新增 #13；C2 测试 mock 配套）
4. **Provider Routing & Shadow Validation**（FR P1-3 + 概念 #8 + #14 + C4 v2 接口预留）
5. **Reproducibility 5y SLA Engineering**（Image Supply Chain + Auto-Migration；新增 #14 + 概念 #9）
6. **Multi-tenancy + Compliance（AIGC + 等保 + PIPL）**（概念 #1 + #10；Q2 拦截点）
7. **Streaming + Async Worker Topology**（SSE + 队列分层；新增 #15 + #16）

---

---

## Starter Template Evaluation

### Primary Technology Domain

`api_backend`（Python/FastAPI 主）+ `web_app`（Next.js 副）+ **Monorepo**
预估 v1 末 ~15-18 services；M1 起步 3-4 services（gateway / solver / billing / auth）

### Starter Options Considered

| Option | 适合 | 状态 |
|---|---|:---:|
| A. Two-Starter Polyrepo | 1 人 demo 速度 | ❌ Rejected（手工 OpenAPI 同步成本 ≥ Turbo 配置 × 5）|
| B. Monorepo + Full Tooling（Turbo + Poetry workspace + pnpm）| 标准档原案 | ❌ Rejected（过度工程，1 周纯配置）|
| **B-Lite. Monorepo + Minimal Tooling**（pnpm + uv + 渐进 Turbo）| **✅ 标准档 + 精简档共用** | ✅ **Selected** |
| C. Polyrepo Microservices | v3+（团队 ≥10）| 🔜 v3+ 才考虑 |

### Selected Starter: Option B-Lite — Monorepo with Minimal Tooling

**Rationale for Selection**：

1. **OpenAPI 单源是 PRD 硬约束（§1092）** → Monorepo 自动同步代价最低，polyrepo 手工同步 6 月后变 bug 温床
2. **License 白名单 PR 自动检查（Hard Rule #2）** → Monorepo 一处工具配置生效全栈
3. **自研算法 Python 直调（Constraint C1）** → 同语言 workspace 共享方便
4. **15-18 个 FastAPI service 同构** → 共用 scaffold 模板减少漂移
5. **shared-types 包** → Python/Node/Go SDK 都可基于同一 OpenAPI 生成（FR §1187 SDK 表）
6. **极简工具链原则**：先 pnpm workspaces + uv workspace（5 分钟搞定）；Turborepo / Bazel 推迟到 M3 末看构建时长决定
7. **精简档共用**：1-2 人走 Option B-Lite minimal（2 service 骨架）而非 Option A 双仓库，避免 OpenAPI 同步 bug

### Monorepo Structure

> ⚠️ **此结构已经过 party_mode_19 修订**：14 services → **10 deployable**。Step 3 草稿曾列 audit-service / revenue-share-service / data-export-aggregator 等独立 service，**已合并 / 推迟，不再独立部署**。下方为权威版。详 Step 6 Service Catalog。

```
opticloud/
├── apps/                     # 10 deployable services（含 web）
│   ├── web/                  # Next.js 15 + App Router + Tailwind + Turbopack
│   ├── api-gateway/          # FastAPI 0.136 + Pydantic v2（M1 起；含 data-export Dramatiq actor / audit query endpoint）
│   ├── auth-service/         # FastAPI（M1 起，API Key + JWT + 风控 + 教育版邮箱）
│   ├── solver-orchestrator/  # FastAPI（M1 起，HiGHS / OR-Tools 路由 + capability lookup）
│   ├── billing-service/      # FastAPI（M2 起，Credits 双写账本）
│   ├── chat-service/         # FastAPI（M3 起，4-Agent + SSE 流式）
│   ├── critic-service/       # FastAPI（M3 起，Innovation #1 SaaS 化）
│   ├── sandbox-runner/       # FastAPI + gVisor（M3 起，FR N11）
│   ├── capability-registry/  # FastAPI（M3 起极简 CRUD + Redis cache；M5+ 加状态机和 prompt-store）
│   └── repro-service/        # FastAPI（M5 起，voucher + Image archive + Auto-migration）
│   # v2 启用：audit-service（v1 = shared-py/audit_log + api-gateway 端点）、revenue-share-service
├── packages/
│   ├── shared-types/         # OpenAPI codegen → TypeScript types
│   ├── shared-py/            # 共享 Pydantic models / utilities
│   └── ui/                   # 共享 React 组件库（Console / Docs / Landing）
├── tools/
│   ├── openapi-codegen/      # Pydantic → openapi.json → TS types
│   ├── license-check/        # PR 自动 license 白名单检查（Hard Rule #2）
│   └── sbom-gen/             # SBOM 生成（Image Supply Chain Concern #14）
├── infra/                    # Terraform / Pulumi（Step 6 决定）
├── docker-compose.yml        # 本地开发：PG + Redis + Vault + gVisor stub
├── pnpm-workspace.yaml
├── pyproject.toml            # uv workspace root
├── .python-version           # 3.12 锁定（Constraint C6）
└── .github/workflows/        # CI with path-based filtering（Constraint C5）
```

### Initialization Command

```bash
# 1. 仓库 + monorepo 骨架
mkdir opticloud && cd opticloud
git init && pnpm init
cat > pnpm-workspace.yaml <<'EOF'
packages:
  - 'apps/*'
  - 'packages/*'
EOF

# 2. uv workspace（替换 Poetry，2025 后社区主流）
pip install uv  # 或 brew install uv
echo '3.12' > .python-version
cat > pyproject.toml <<'EOF'
[tool.uv.workspace]
members = ["apps/*", "packages/*"]

[tool.uv]
required-version = ">=0.4.0"
EOF

# 3. Frontend - Next.js 15
pnpm create next-app@latest apps/web \
  --typescript --tailwind --eslint --app --turbopack --yes

# 4. Backend service scaffold（每个 service 重复，M1 限 3-4 个）
cd apps && uv init api-gateway --python 3.12 --package
cd api-gateway && uv add \
  fastapi 'uvicorn[standard]' pydantic \
  sqlalchemy asyncpg alembic \
  structlog opentelemetry-api opentelemetry-instrumentation-fastapi \
  httpx pytest pytest-asyncio factory-boy

# 5. Pre-commit hooks（py + ts 统一）
cat > .pre-commit-config.yaml <<'EOF'
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks: [{id: ruff, args: ['--fix']}, {id: ruff-format}]
  - repo: https://github.com/pre-commit/mirrors-mypy
    hooks: [{id: mypy}]
  - repo: https://github.com/PyCQA/bandit
    hooks: [{id: bandit, args: ['-c', 'pyproject.toml']}]
  - repo: local
    hooks:
      - id: license-check
        name: License Whitelist Check（Hard Rule #2）
        entry: pnpm tools:license-check
        language: system
EOF
pre-commit install

# 6. CI path-filter（Constraint C5 必上）
mkdir -p .github/workflows
# .github/workflows/ci.yml 配 dorny/paths-filter
# 按 apps/*/path 触发 service-specific test job
```

### Architectural Decisions Provided by Option B-Lite

**Language & Runtime**：
- Backend：**Python 3.12** locked（`.python-version`；Constraint C6 升级须 RFC）
- Frontend：**TypeScript 5+** + **Node.js 20 LTS**

**Frontend Stack**（已固化）：
- **Next.js 15 + App Router**（PRD 14 升 15+；当前稳定版）
- **Tailwind CSS v3**（v4 待评测，CSS-first 配置成熟后升）
- **Turbopack**（Next 15 默认）
- **next-intl**（i18n，PRD §1220）
- **SSE 客户端 + EventSource polyfill**（Cross-Cutting #15）

**Backend Stack**（已固化）：
- **FastAPI 0.136 + Uvicorn[standard] + Gunicorn**（生产 multi-worker）
- **Pydantic v2**（OpenAPI 单源 + 数据校验）
- **SQLAlchemy 2.0 async + asyncpg + Alembic**
- **structlog + OpenTelemetry**（Concern #4 可观测）
- **httpx**（外部 HTTP；Provider 调用统一客户端）

**Build Tooling**：
- **pnpm workspaces**（5 分钟配置；workspace root 锁定）
- **uv workspace**（Python；替换 Poetry workspace）
- **Turborepo M3 末决定**（看构建时长 ≥ 阈值再加）
- **Docker multi-stage build + 签名**（Image Supply Chain Concern #14）

**Testing Framework**：
- 后端：**pytest + pytest-asyncio + httpx + factory_boy**
- 前端：**Vitest + React Testing Library + Playwright**（Playwright 已在 MCP 中可用）
- 测试 mock：**LLM mock + 算法 mock 抽象层**（Constraint C2）

**Linting / Formatting**：
- Python：**ruff + mypy + bandit**（pre-commit）
- TypeScript：**ESLint + Prettier**（Next.js 默认）
- Markdown：**markdownlint**（PR check）

**Code Organization**：
- `apps/` = 部署单元（service / app）
- `packages/` = 共享库（types / models / ui）
- `tools/` = 工程工具（codegen / license-check / sbom）
- `infra/` = IaC（Step 6 决定 Terraform / Pulumi）

**Development Experience**：
- 本地：`docker-compose up` 启 PG + Redis + Vault + gVisor stub
- HMR：Next.js Turbopack（前端）+ uvicorn `--reload`（后端）
- API Docs：FastAPI 自带 `/docs` + `/redoc`（开发期）；生产 Redoc/Stoplight 选型见 Step 4 Q3
- VS Code 默认配置：`.vscode/settings.json` 含 ruff / mypy / ESLint 集成

### Constraints Updates（C5-C7 新增）

| # | 约束 |
|---|---|
| **C5** | CI 必须 **path-based filtering**（GitHub Actions + `dorny/paths-filter`）；**M3 末按构建时长决定是否加 Turborepo** |
| **C6** | Python 版本 monorepo 内**统一锁定**（`.python-version`）；升级须 RFC |
| **C7** | **精简档（1-2 人）走 Option B-Lite minimal**：仅 2 service 骨架（gateway + solver）+ shared-types OpenAPI 同步保留 |

### Sprint 0 / Epic 0 Foundation Anchor（修订版 v2.1）

> 写入 Step 7-8 输入备忘。Sprint 0 严格限定 8 stories（~20 person-week, 2-4 周 5 人团队可达）；M1-M3 各阶段含 Foundation 后续 stories。

**Epic 0 = Monorepo Foundation**（Sprint 0，**8 stories**，预估 2-4 周）：

| Story | 描述 | 依赖 | Pattern |
|---|---|---|---|
| **0.1** | Monorepo 骨架（pnpm workspaces + uv workspace + 目录结构）| — | P14-P15 |
| **0.2** | docker-compose 本地栈（PG + Redis + Vault + gVisor stub）| 0.1 | P15 |
| **0.5** | Pre-commit + ruff + mypy + bandit + **license-check tool**（Hard Rule #2）| 0.1 | P35 + P54 |
| **0.6** | Auth scaffold（FR A1-A2：API Key + JWT + OpenAPI spec）| 0.1, 0.5 | P40 + D7-D8 |
| **0.7** | Health/Readiness 端点 + OpenTelemetry 接入 | 0.6 | P46 + P48 |
| **0.4** | shared-types OpenAPI codegen pipeline + drift check | 0.6 | P17 + P54 + P64 |
| **0.3** | CI path-filter + per-service test pipeline | 0.6 | C5 |
| **0.8** | Docker multi-stage build + image 签名（SBOM 生成）| 0.5, 0.6 | Concern #14 |

> ⚠️ **依赖顺序已纠正**（原 0.3/0.4/0.7 列在 0.6 之前，依赖错乱）。

---

**Foundation Continuation（移出 Sprint 0，归入 M1-M3 sprint）**：

| Story | 描述 | M | Pattern | 关联 Gap |
|---|---|:---:|---|---|
| **M2.1** | Outbox Relayer Sidecar 集成（per service 部署）| M2 | P56 | — |
| **M2.2** | Billing 双写一致性测试（chaos + property-based）| M2 | P33 + D15 | — |
| **M2.3** | **Cost-attribution middleware（shared-py/cost_telemetry）**| M2-M3 | — | **G3** |
| **M3.1** | Sandbox I/O Pattern 实现（+ P62 self-loop prevention）| M3 | P58 + P62 | G12 部分 |
| **M3.2** | Contract Test 框架（Schemathesis）| M3 | P61 | — |
| **M3.3a** | K8s Namespace 三域 + NetworkPolicy（**标准档**）| M3 | P60 | — |
| **M3.3b** | docker-compose 蓝绿 deploy script（**精简档**）| M3 | C19 | — |
| **M3.4** | **AIGC 水印 module + 双测试集**（文本尾标 + zero-width Unicode + trace_id）| M3 | P34 + P62 | **G12** |
| **M3.5a** | **Critic 置信度校准工具 + 标注 SOP 文档** | M3 | — | **G9** |
| **M3.5b** | **(Epic) Critic ground truth 持续标注**（每周 ~20 样本，M0-M3 跨多 sprint）| M0-M3 持续 | — | **G9** |

> Epic 0 不属于任何业务 Epic，是 Foundation Sprint，必须先于 Epic 1-8（业务）启动。
> 上述 Continuation Stories 与业务 Epic（A/E/B/N 等 FR）并行 sprint，**不阻塞业务**。

### 关键升级 vs PRD 决策

| 项 | PRD 写法 | 架构修订 | 理由 |
|---|---|---|---|
| Next.js 版本 | 14 | **15+**（latest stable）| PRD 写作 2026-05，今 15 稳定 |
| Python 包管理 | （未明示）| **uv workspace**（非 Poetry workspace）| Poetry workspace 不成熟，uv 2025 后主流 |
| Python 版本 | 3.10+ | **3.12 locked** | 3.12 LTS + 新性能特性 + 锁版本（C6）|
| Monorepo build cache | （未明示）| **M3 末决定**（先不上 Turborepo）| 极简工具链原则 |

**Note**：Project initialization using this command should be the first implementation story (Story 0.1 in Epic 0 Foundation).

---

---

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions（Block Implementation；M0-M1 必决）**：
- D1 ORM 风格 / D2 多租户隔离 / D3 Migration / D6 Message Bus / D14 异步任务框架 / D15 分布式事务 / D21 容器编排 / Q1 Critic 部署形态 / Q2 AIGC Filter 拦截点

**Important Decisions（Shape Architecture；M1-M3 期间细化）**：
- D4 连接池 / D5 Redis 使用 / D7 API Key Hash / D8 JWT 签名 / D9 Rate Limit / D10 落盘加密 / D12 API 风格 / D13 服务间通信 / D16-D20 前端栈 / D22 IaC / D23 ACR+Tempo+Rollouts / Q3 Docs Renderer

**Deferred Decisions（Post-MVP）**：
- gRPC 内部服务通信全面铺开（v2 末按吞吐评估）
- Qdrant 迁移（v2 末，触发：月活付费 ≥500 AND ≥500K embeddings）
- 自托管 GPU 集群（v3+，4 重 AND 触发）
- Kafka 替换 Redis Streams（v2 末按吞吐）
- Temporal 替换 Dramatiq（v2+ 复杂工作流需求评估）

---

### Pre-Decided（PRD + Step 3 锁定，不再讨论）

**Languages**：Python 3.12 / TypeScript 5+ / Node.js 20 LTS
**Backend Stack**：FastAPI 0.136 + Pydantic v2 + SQLAlchemy 2.0 async + Alembic + asyncpg + structlog + OpenTelemetry
**Frontend Stack**：Next.js 15 + App Router + Tailwind v3 + Turbopack
**Data**：PostgreSQL + pgvector（v1 起）→ Qdrant（v2 末迁移）；Redis
**Auth Tokens**：JWT（Web Console）+ API Key（主路径）
**Sandbox**：gVisor（v1 起）→ Firecracker（v2+ 重资源场景）
**Secret**：HashiCorp Vault self-hosted
**Feature Flag**：GrowthBook self-hosted
**Observability**：Grafana + Prometheus + Loki + OpenTelemetry
**LLM**：DeepSeek-V3.5（主）+ Qwen-Max API（incident 应急 fallback）
**Solvers**：HiGHS / OR-Tools / IPOPT / Bonmin / Couenne / CVXPY / SCS
**Time-Series Foundation Models**：Chronos / TimesFM / Lag-Llama / Moirai
**Pay**：微信支付 + 支付宝 + Stripe
**Email**：Resend / Mailgun
**Cloud**：阿里云（主，RDS Postgres + Redis + OSS）+ AWS（备份）
**Monorepo**：pnpm workspaces + uv workspace

---

### Data Architecture（D1-D6）

| # | 决策 | 选型 | Version | Rationale |
|---|---|---|---|---|
| **D1** | ORM 风格 | **SQLAlchemy 2.0 Core + ORM 混合**（Core 跑查询 / ORM 做模型）| 2.0+ | Core 性能 + ORM 表达力；不上 SQLModel（过早抽象层）|
| **D2** | 多租户隔离 | **Postgres schema-per-tenant**（PRD §744 已锁）| — | `set search_path` per-request；S3 + namespace 配套 |
| **D3** | Migration 策略 | **Alembic auto-gen + 强制人审 + 含数据回填脚本**；migration PR 必双人审 | Alembic 1.13+ | 防破坏性变更；data backfill 显式 step |
| **D4** | 连接池 | **PgBouncer（transaction mode）+ asyncpg 内置 pool** 双层 | PgBouncer 1.22+ | transaction mode 与 SQLAlchemy 兼容（避 session mode 坑）|
| **D5** | Redis 使用 | **统一前缀分桶**：`session:` / `ratelimit:` / `cache:` / `pubsub:` / `stream:` / `idempotency:` / `outbox:` / **`llm_cache:`**（P69）/ **`capability_cache:`**（capability-registry SWR）/ **`prompt_cache:`**（P68 prompt store 缓存，M5+ 启用）| Redis 7+ | 单 Redis 多用途 v1；v2 末按吞吐拆 |
| **D6** | Message Bus | **v1: Redis Streams + 消费组**（事件 = domain event）；**v2 末按吞吐评估 Kafka** | Redis 7+ | 不引第二组件；Streams 支持 ack/重投/批量；与 D14 职责分工见 ⬇️ |

**🟡 D6 / D14 职责分工明示**（party_mode_17 / W1）：
- **Dramatiq = 命令（task / RPC-style）**：执行业务任务，需要返回值或重试，e.g. `process_optimization(task_id)`、`charge_credits(user_id, amount)`、`generate_critic_review(chat_id)`
- **Redis Streams = 事件（domain event / fire-and-forget broadcast）**：业务侧已成事实的状态变化，e.g. `optimization.completed`、`credits.charged`、`provider.health_changed`、`audit.event_logged`
- 命令有 sender 期望 receiver 执行；事件无 sender 期待，订阅者按需消费。

---

### Authentication & Security（D7-D11）

| # | 决策 | 选型 | Version | Rationale |
|---|---|---|---|---|
| **D7** ★ | **API Key Hash** | **HMAC-SHA256 with Vault pepper**（不可猜 token 模型）；密码使用场景才用 **Argon2id**（memlimit 64MB / time=2 / parallelism=1）| Vault 1.18+ | API Key = unguessable token，HMAC O(1) 验证；高频请求路径不能跑 Argon2（A1）|
| **D8** | JWT 签名 | **EdDSA (Ed25519)** 非对称 | pyjwt 2.10+ | 比 RS256 快 + 密钥更短；service-to-service 服务端自验证；密钥轮换见 C10 |
| **D9** | Rate Limiting | **Redis sliding-window-counter + Lua 脚本** | Redis 7+ | 原子操作；比 token bucket 更准 |
| **D10** | 落盘加密 | **PostgreSQL TDE (pg_tde) + 应用层 KMS 包裹敏感字段** | pg_tde 1.0+ | TDE 全盘 + 字段级双重；Vault HSM 管 KMS；测试环境策略见 C9 |
| **D11** | CSRF（Console）| **SameSite=Strict + httpOnly cookie + double-submit token** | Next.js 15 | API Bearer 不受影响；Server Actions 原生支持 |

**JWT 密钥轮换（C10）**：Vault 推送新 key + service 每 5 min 拉新 **JWKS endpoint**；保留旧 key grace period 15 min。

---

### API & Communication Patterns（D12-D15）

| # | 决策 | 选型 | Version | Rationale |
|---|---|---|---|---|
| **D12** | API Style | **REST + OpenAPI 3.1**（v1 外部）；**gRPC 内部 service-to-service v2 末按吞吐评估** | FastAPI 0.136 | REST 外部一等；gRPC 仅内部 v2+ |
| **D13** | Service-to-Service v1 | **HTTP/JSON + httpx**（统一客户端）；可靠性栈见下 | httpx 0.27+ | Mesh 留 v2；ADR 占位补在 Step 5 |
| **D14** ★ | 异步任务框架 | **Dramatiq + Redis broker**（命令）+ **dramatiq-crontab**（cron 调度）+ **独立 Outbox Relayer service** | Dramatiq 1.17+ | 反 Celery 包袱；async-native；message reliability 强（金融/合规 worker）|
| **D15** ★ | 分布式事务 | **Outbox pattern**（Postgres `outbox` 表 + **独立 Outbox Relayer service** poll + push 到 Dramatiq broker + ack 后 mark sent）；**Billing saga 通过 Dramatiq message chain** | — | 计费对账误差=0 工程实现；2PC 不上；Relayer 独立（W2）|

**🟡 D13 HTTP Client Reliability Stack（ADR 占位，Step 5 细化）**：
- 库选型：**httpx + httpx-retries + 自写 async-circuit-breaker 中间件**（避 pybreaker 锁竞争）
- 策略：retry (exponential backoff, max 3) + timeout (connect 5s, read 30s) + circuit breaker (half-open after 60s)
- 与 OpenTelemetry span 集成 + 失败计入 `provider_failure_rate` 业务 metric

---

### Frontend Architecture（D16-D20）

| # | 决策 | 选型 | Version | Rationale |
|---|---|---|---|---|
| **D16** | State 管理（Concern #19）| **TanStack Query**（server state）+ **Zustand**（client state） | TQ 5+ / Zustand 5+ | 2026 主流；服务端/客户端状态明确分离 |
| **D17** | Form | **React Hook Form + Zod**；后端 Pydantic → Zod 通过 codegen 自动生成 | RHF 7+ / Zod 3+ | 类型安全；端到端 schema 一致 |
| **D18** | 图表 | **Apache ECharts**（中文社区强 + Grafana 生态可复用）| 5.5+ | Recharts 太简，Visx 学习陡 |
| **D19** | 表格 | **TanStack Table + TanStack Virtual** | 8+ / 3+ | 长列表虚拟化必需（Audit/Usage/Provider routing）|
| **D20** | 组件库 | **Radix UI primitives + shadcn/ui**（CLI 生成入仓库）；**升级策略见 C13** | Radix 1+ / shadcn latest | Headless + 完全可控样式 |

**🟡 D20 升级策略（C13）**：shadcn/ui 升级 = 锁版本（commit SHA）+ 季度统一 re-pull + git diff 人工审。

---

### Infrastructure & Deployment（D21-D23）

| # | 决策 | 选型 | Version | Rationale |
|---|---|---|---|---|
| **D21** | Container Orchestration | **阿里云 ACK 托管版 + ACK One GitOps**（内置 ArgoCD）| K8s 1.30+ / ArgoCD 2.13+ | 托管省运维；GitOps 一站式；多集群可扩展 |
| **D22** | IaC | **Terraform + 阿里云 provider**（避免 Pulumi）| Terraform 1.9+ | 生态成熟；HCL 学习曲线低；module 复用 |
| **D23** | Image Registry / Tracing / Canary | **阿里云 ACR EE**（签名+SBOM+漏洞扫描）/ **Grafana Tempo** / **Argo Rollouts** | ACR EE / Tempo 2.6+ / Rollouts 1.7+ | 一站式阿里云生态；Concern #14 Image Supply Chain 工程承载；Grafana 栈一致 |

---

### Open Questions 解决（Q1-Q3）

| Q | 决策 | Rationale |
|---|---|---|
| **Q1** | **Critic Agent = 独立 service**（`apps/critic-service`）| Innovation #1 SaaS 化；独立扩缩；红队跑批独立调度；v3+ 可对外暴露 API |
| **Q2** | **AIGC Filter 单点封装**（`packages/shared-py/aigc-filter`），chat-service 和 critic-service 各自调用过滤所有"用户可见 NL 输出" | Buffered streaming 用户体验最佳；filter 可独立升级 prompt；出口屏障避免漏过（C11）|
| **Q3** | **Stoplight Elements**（自托管）| 比 Redoc 交互强；比 SwaggerUI 现代；MIT 许可可商用 |

---

### Cascading Implications（决策连锁）

| 决策 | 引出的次级决策 | 落地位置 |
|---|---|---|
| D6 Redis Streams | 消费组 schema + dead-letter handling + Stream key 命名 | Step 5 |
| D14 Dramatiq | Worker 镜像构建 + 健康检查 + 扩缩策略 + dramatiq-crontab 任务声明 | Step 6 |
| D15 Outbox | `outbox` 表 DDL + cleanup job + Relayer 状态机 + 幂等消费 | Step 5 |
| Q1 Critic 独立 | `critic-service` 增计入 service 列表（M3 起共 8 service）| Step 6 |
| Q2 AIGC Filter | shared-py/aigc-filter 包结构 + 出口屏障注入点 | Step 5 + Step 6 |
| D21 ACK | K8s namespace 切分 = service 拆分边界 | Step 6 |

---

### 精简档替代决策表（C8）

| 决策 | 标准档（默认）| 精简档（1-2 人）| 触发升级标准档 |
|---|---|---|---|
| **D14** 异步任务 | Dramatiq + Outbox Relayer + dramatiq-crontab | **FastAPI BackgroundTasks**（同进程）+ **Redis simple list**（10 行自写）+ **APScheduler in web process** | M5 单元素监控不满足 / Outbox 一致性需求 |
| **D20** 组件库 | Radix + shadcn/ui | **DaisyUI**（免费 Tailwind 组件）+ Radix 仅核心交互 | M5+ 设计强需求时升 |
| **D21** 编排 | ACK 托管版 + ArgoCD | **单 ECS + docker-compose + GitHub Actions push**（无 K8s）| M7+ 量起来再上 K8s |
| **D22** IaC | Terraform + 阿里云 provider | **README + bash script + 阿里云控制台** | M5 商用前 acceptable |
| **D23** Tracing | Grafana Tempo | **Grafana Cloud free tier** 含基础 trace | 标准档 self-hosted 时 |

---

### License Check Tool Stack（C14）

- **Python**：`pip-licenses --format=json` + 自定义 `tools/license-check/allowlist.yaml`
- **Node**：`license-checker-rseidelsohn` + 同一 allowlist 共享
- **PR Gate**：GitHub Actions 检测命中黑名单 → fail；允许 EPL 仅调用（自动验证不 import 修改）
- **Hard Rule #2 工程落地**

---

### GPU 调度 Adapter 层（C15）

- 统一 `packages/shared-py/gpu_provider/` adapter 层
- 实现：`RunPodAdapter`（v1 主）/ `AutoDLAdapter`（v1 备）/ `SelfHostedAdapter`（v3+ 启用）
- 统一接口：`async def acquire(spec) → instance` / `async def release(instance)` / `async def execute(instance, container_spec)`
- 计费 metric：每 instance lifetime 写入 `gpu_seconds_used` for billing
- 测试：精简档可全 mock；标准档 RunPod sandbox API 跑 e2e

---

### 测试与环境约束（来自 party_mode_17）

- **C9** TDE 测试环境策略：所有环境启用 pg_tde；CI Vault 用 dev mode（in-memory token）+ 启动时自动注入 KMS key
- **AIGC Filter 双测试集**：对抗集（应拒）≥100 + 良性集（应通过）≥100，CI 全跑
- **Billing 双写一致性测试套件**（Story 0.x）：chaos 注入（数据库 commit + relayer 挂 / relayer 发送 + mark sent 之间挂）+ property-based test

---

### 新增 Risk（写入 Step 5/6/7 影响）

| # | Risk | 缓解 |
|---|---|---|
| **R11** | **Cloud Lock-in（W3）**：D21+D22+D23 五项绑定阿里云；M9+ 海外节点撞壁 | ① OpenTelemetry 业务层抽象 ② Terraform module 抽象 ③ 关键 service 走 K8s manifest 而非阿里云原生 CRD ④ AWS backup 同步实时（非冷备） |

---

### 新增 Story 占位（写入 Epic 0 Foundation / 业务 Epic）

| Story | 描述 | Epic |
|---|---|---|
| **0.9** Outbox Relayer Service | 独立进程 poll outbox + push to Dramatiq broker + ack 后 mark sent（M2 起，Billing #13）| Epic 0 |
| **0.10** Billing 双写一致性测试套件 | chaos 注入 + property-based test | Epic 0 |
| **业务 Epic 内** AIGC Filter 双测试集 | 对抗 + 良性各 ≥100 样本 | Epic 8 Observability/Compliance |
| **业务 Epic 内** GPU Provider Adapter 层 | RunPod + AutoDL 双 backend | Epic 3 Execution |

---

### Constraints 累积（C1-C15）

| # | Constraint |
|---|---|
| C1 | v1 自研算法 = Python 直调（pip install + Apache 2.0），v2 起标准化为 Provider API 协议 |
| C2 | 测试环境必须有 LLM mock + 算法 mock 抽象层 |
| C3 | v1 Audit = Postgres `audit_log` 表 + 异步入库；v2 末拆库 |
| C4 | v2 接口预留 Revenue-Share Service（自研 100/0 / 合作 60/40 / 商业 50/50）|
| C5 | CI 必须 path-based filtering（dorny/paths-filter）；M3 末按构建时长决定是否加 Turborepo |
| C6 | Python 版本 monorepo 内统一锁定，升级须 RFC |
| C7 | 精简档走 Option B-Lite minimal（2 service 骨架 + OpenAPI 同步保留）|
| **C8** | 精简档替代决策表（D14/D20/D21/D22/D23 各列简化版）|
| **C9** | TDE 全环境启用 + CI Vault dev mode（in-memory token + 启动注入 KMS key）|
| **C10** | JWT 密钥轮换 = Vault 推送 + service 每 5 min 拉 JWKS endpoint + grace 15 min |
| **C11** | AIGC Filter 出口屏障：所有用户可见 NL 必经统一 filter package（chat-service + critic-service 共用）|
| **C12** | Outbox Relayer 独立 service（不混业务 Dramatiq actor）|
| **C13** | shadcn/ui 升级策略 = 锁版本 commit SHA + 季度统一 re-pull + git diff 人审 |
| **C14** | License Check Tool Stack = pip-licenses + license-checker-rseidelsohn + allowlist YAML |
| **C15** | GPU 调度统一 `gpu-provider` adapter 层（v1 RunPod 主 / AutoDL 备 / 自建 v3+）|

---

### Implementation Sequence（依赖排序）

1. **Epic 0 Foundation**（Sprint 0，2-4 周）：D1/D3/D5/D7/D8/D11/D16-D20/D22/D23 + Story 0.1-0.8（含 license-check 0.5）
2. **M1 起步**：D2/D4/D9/D10/D12/D13 + auth-service + api-gateway + solver-orchestrator
3. **M2 起步**：D14/D15 + Outbox Relayer + billing-service + Story 0.9-0.10
4. **M3 起步**：Q1 critic-service + Q2 AIGC Filter package + chat-service + sandbox-runner
5. **M5 起步**：Q3 Stoplight Elements 上线 / Repro Service / Capability Registry / 测试集 ≥200
6. **v2 末**：D6 评估 Kafka / D12 评估 gRPC 内部 / Qdrant 迁移 / Marketplace API

---

---

## Implementation Patterns & Consistency Rules

> 55 项 pattern 覆盖 Naming / Structure / Format / Communication / Process / Critical 6 大类，旨在防止多 AI agent 写出不兼容代码。所有 service / feature 实现必须遵守。

### Pre-Locked Patterns（PRD 已定，列出索引便于查阅）

| 项 | 规范 | PRD 来源 |
|---|---|---|
| JSON 字段命名 | snake_case | §1089 |
| 时间字段 | ISO 8601 UTC + `_at` 后缀 | §1090 |
| 错误格式 | RFC 7807（type/title/status/detail/instance/request_id/trace_id/next_action_url）| §1126 |
| HTTP 状态码 | 400/401/402/403/404/409/422/429/500/502/503/504 | §1140 |
| Idempotency-Key | 所有 POST 必带；24h 缓存窗口；同 key+同 body 返缓存；异 body→409 | §1090 |
| 分页 | Cursor-based（`?cursor=xxx&limit=50` + `next_cursor`）| §1091 |
| 嵌套深度 / 数组上限 | 嵌套 ≤ 3 / 数组 ≤ 10K（超出走 multipart / S3 预签名）| §1089 |
| i18n | Accept-Language（zh-CN / en-US 单字段） | §1138 |
| API 版本化 | URL `/v1/` + `X-API-Version` + `X-API-Date`（v2） | §1180 |
| API Key 格式 | 前缀 `sk-`，仅 hash 入库，前缀 6 位可见 | §1079 |
| Voucher | `repro-{YYYY}-{6 位 base32}` | §1681 |
| Provider 透明 | `model_version.provider_id/kind/version` | §1156 |

---

### 1. Naming Patterns（P1-P14）

#### Database

| # | 项 | 规范 | 例子 |
|---|---|---|---|
| **P1** | Table 名 | 复数 snake_case | `users`、`api_keys`、`audit_logs`、`outbox`、`reproduction_vouchers` |
| **P2** | Column 名 | snake_case；时间 `_at` 后缀；FK `<table>_id` | `created_at`、`updated_at`、`user_id`、`tenant_id` |
| **P3** | Primary Key | 全部 **`id` (UUID v7)**（按时间排序的 UUID）| `id UUID PRIMARY KEY DEFAULT uuidv7()` |
| **P4** | Index 名 | `idx_<table>_<columns>` / `uq_<table>_<columns>`（unique）| `idx_audit_logs_tenant_id_created_at` |
| **P5** | Schema（多租户）| `tenant_<short_id>.<table>` | `tenant_a3f7k2.users` |

#### API

| # | 项 | 规范 | 例子 |
|---|---|---|---|
| **P6** | Endpoint 路径 | 复数 + snake_case | `/v1/optimizations`、`/v1/credits/balance`、`/v1/reproduction_vouchers` |
| **P7** | Path 参数 | `{snake_case}` 不用 `:id` | `/v1/optimizations/{optimization_id}` |
| **P8** | 自定义 header | `X-OptiCloud-<PascalCase-Hyphen>` | `X-OptiCloud-Signature`、`X-OptiCloud-Trace-Id` |
| **P9** | Query 参数 | snake_case；布尔显式 `true`/`false` | `?include_traces=true&max_results=50` |

#### Code

| # | 项 | Python | TypeScript |
|---|---|---|---|
| **P10** | 函数 / 变量 | `snake_case` | `camelCase` |
| **P11** | 类 / 类型 | `PascalCase` | `PascalCase` |
| **P12** | 常量 | `SCREAMING_SNAKE_CASE` | `SCREAMING_SNAKE_CASE` |
| **P13** | 文件名 | `snake_case.py`；测试 `test_<name>.py` | Component `PascalCase.tsx`；hook `useXxx.ts`；client `Xxx.client.tsx`；其他 `kebab-case.ts`；测试 `<name>.test.ts(x)` |
| **P14** | 模块 / 包 | `snake_case`（avoid hyphens） | `kebab-case`（npm package） |

---

### 2. Structure Patterns（P15-P19）

#### P15 — Backend Service 标准结构（每个 FastAPI service 复刻；新建走 P55 CLI）

```
apps/<service-name>/
├── src/<service_module>/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app + middleware 装配
│   ├── api/                     # 路由层
│   │   ├── v1/                  # 版本化路由
│   │   │   ├── routes.py
│   │   │   └── schemas.py       # Pydantic request/response
│   │   └── deps.py              # FastAPI Depends（auth/tenant/db_session）
│   ├── services/                # 业务逻辑（无 HTTP / 无 ORM）
│   ├── repositories/            # DB 访问层（SQLAlchemy）
│   ├── models/                  # SQLAlchemy ORM
│   ├── clients/                 # 外部 HTTP / SDK 包装（httpx）
│   ├── tasks/                   # Dramatiq actors
│   ├── events/                  # Redis Streams producer/consumer
│   ├── middleware/              # ASGI middleware
│   ├── config.py                # pydantic-settings
│   ├── logging.py               # structlog 配置
│   └── exceptions.py            # OptiCloudError 异常树
├── alembic/                     # migrations
├── tests/{unit,integration,e2e}/
├── pyproject.toml
├── Dockerfile                   # multi-stage + signed
└── README.md
```

#### P16 — Frontend Feature-Based Organization（含 Server Component / Client Component 划界）

```
apps/web/src/
├── app/                         # Next.js App Router
│   ├── (marketing)/             # Landing/Pricing/Docs
│   ├── (console)/               # Console 受保护页
│   └── api/                     # Route Handler（rare）
├── features/                    # 按业务 feature 组织
│   ├── auth/{components,hooks,queries,stores,types.ts}
│   ├── optimization/
│   ├── credits/
│   └── chat/
├── lib/{api-client,sse-client,utils}.ts
├── components/                  # 跨 feature 共享 UI（少量）
└── styles/
```

| # | 项 | 规则 |
|---|---|---|
| **P17** | 测试位置 | `tests/unit/` / `integration/` / `e2e/`（不 inline 在 source）|
| **P18** | 配置文件 | pydantic-settings（py）/ process.env + zod（ts）；**绝不硬编码 secret/host** |
| **P19** | 静态资产 | Next.js `public/` 用于纯静态；动态生成放 `src/assets/` |

---

### 3. Format Patterns（P20-P23）

| # | 项 | 规范 | 例子 |
|---|---|---|---|
| **P20** | 成功响应 | **裸对象**（无 `{data: ...}` 包装）；list 端点 `{items: [...], next_cursor: "..."}` | `{"optimization_id": "opt_xyz", ...}` |
| **P21** | Boolean | 显式 `true`/`false`，不用 1/0 | `{"is_reproducible": true}` |
| **P22** | Null 处理 | **显式 `null` 不省略** key | `{"deleted_at": null}` |
| **P23** | ID 前缀 | 资源类型缩写 + `_` + ULID（base32 表示）；**API Key 例外为 `sk-`（连字符，PRD §1079 强约束）**；voucher 例外为 `repro-{YYYY}-{6 位 base32}`（PRD §1681）| `opt_xyz`、`req_abc`、`trc_def`、`evt_ghi`、`tnt_xxx`、`usr_yyy`、`cnv_xxx`（chat conversation）、`msg_xxx`（chat message）、`pol_xxx`（policy / capability）、`prv_xxx`（provider）、`sub_xxx`（subscription）、`sk-abc...`（API Key 连字符）、`repro-2026-K7X9P2`（voucher）|

---

### 4. Communication Patterns（P24-P28）

#### P24 — Domain Event Naming（D6 Redis Streams）

- **Convention**：`<domain>.<aggregate>.<past_tense_event>`
  - `optimization.task.completed`、`billing.credits.charged`、`provider.health.changed`、`audit.event.logged`、`repro.voucher.issued`
- **Stream key**：`events.<domain>`（`events.billing`、`events.optimization`）
- **Consumer group**：`<service-name>-<purpose>`（`api-gateway-audit-logger`、`billing-service-credits-listener`、`critic-service-escalation-listener`）
- **注**：v1 audit 由 `shared-py/audit_log` 写入 + `api-gateway` 提供查询（无独立 audit-service v1）；v2 末 audit-service 拆出后 consumer group 名改 `audit-service-event-logger`

#### P25 — Event Payload Schema（v1 JSON；v2 评估 protobuf + schema registry）

```json
{
  "event_id": "evt_<ulid>",
  "event_type": "billing.credits.charged",
  "event_version": "1.0",
  "occurred_at": "2026-05-17T08:30:00Z",
  "tenant_id": "tnt_xxx",
  "actor": {"type": "user|system|provider", "id": "usr_yyy"},
  "data": {/* domain-specific */},
  "metadata": {
    "trace_id": "trc_def",
    "correlation_id": "<parent_event_id_or_request_id>",
    "schema_version": "1.0",
    "traceparent": "<W3C trace context>",
    "tracestate": "<W3C trace state>"
  }
}
```

> 事件版本变更必须 bump `event_version`；v2 起 schema registry。

#### P26 — Dramatiq Task Naming（D14）

- **Convention**：`<service>.<verb_in_imperative>`
  - `billing.charge_credits`、`optimization.execute_solver`、`critic.review_solution`
- **Actor 装饰参数标准**：
  ```python
  @dramatiq.actor(
      queue_name="<service>",
      max_retries=3,
      time_limit=90_000,
      store_results=False,
      middleware=[CallbacksMiddleware(), AgeLimit(max_age=300_000)],
  )
  ```

#### P27 — Frontend State Management

**TanStack Query keys**（hierarchical）：
```ts
['optimizations', 'list', { status: 'queued' }]
['optimizations', 'detail', optimizationId]
['credits', 'balance']
['credits', 'transactions', { from, to, cursor }]
```

**Zustand store 拆分**（per-feature）：
- `useAuthStore`、`useUIStore`、`useChatStore`（不一坨）
- 仅放 UI / client-only 状态；服务端数据交给 TanStack Query

**Mutation 后必须 invalidate** 相关 query keys。

#### P28 — SSE Connection Lifecycle（Concern #15）

**Server**：
- 心跳：每 30s 发送 `:heartbeat\n\n`（comment line）
- 客户端无活动 5 min 关闭
- 每个 event 含 `id:`（顺序 ulid）
- 错误：`event: error\ndata: {...}\n\n` 后关闭

**Client**：
- 用 native `EventSource`
- 重连：指数 backoff（1s→2s→4s→8s→max 30s）
- 用 `Last-Event-ID` 断线续传
- Tab hidden → 关闭；resume → 重连

---

### 5. Process Patterns（P29-P32）

#### P29 — Error Handling

**Python 异常树**（per service `src/<svc>/exceptions.py`）：
```python
class OptiCloudError(Exception):
    type: str                    # RFC 7807 type URI
    title: str
    status: int
    detail_template: str         # 含 i18n key
    next_action_url_template: str | None = None

class BusinessError(OptiCloudError): ...       # 4xx
class InsufficientCreditsError(BusinessError):
    type = "https://api.opticloud.cn/errors/insufficient_credits"
    status = 402

class SystemError(OptiCloudError): ...         # 5xx
class ProviderUnavailableError(SystemError):
    type = "https://api.opticloud.cn/errors/provider_unavailable"
    status = 502
```

**API middleware 顶层**：`OptiCloudError` → RFC 7807 响应；未识别 → 500 + Sentry。**禁止业务层 catch broad `Exception`**。

**TypeScript**：API client 抛 `ApiError`（含 RFC 7807 字段）；TanStack Query 直接消费；React Error Boundary 仅捕获 render 错误。

#### P30 — Logging（structlog 统一）

**Mandatory 字段**：`timestamp`、`level`、`service`、`request_id`、`trace_id`、`tenant_id`、`user_id`

**Levels**：ERROR（alert）/ WARN（degraded）/ INFO（state change）/ DEBUG（dev only）

**PII 过滤 middleware**：黑名单字段（`email`、`phone`、`id_card`、`bank_account`）自动 mask；property-based test 验证。

#### P31 — Idempotency 实现

```python
@idempotent
async def post_handler(request, idempotency_key, body):
    cache_key = f"idempotency:{tenant_id}:{idempotency_key}"
    body_hash = canonical_sha256(body)        # 见 P47
    cached = await redis.get(cache_key)
    if cached:
        if cached.body_hash != body_hash:
            raise HTTPException(409, "Idempotency conflict")
        return cached.response
    response = await actual_handler(request, body)
    await redis.setex(cache_key, 24*3600, {"body_hash": body_hash, "response": response})
    return response
```

#### P32 — Multi-Tenancy Enforcement（Concern #1）

**SQLAlchemy Event Hook**：从 `ContextVar` 提取 `tenant_id` 自动注入 `WHERE tenant_id = ?`。

**ASGI middleware**：从 JWT/API Key 提取 → ContextVar → SQLAlchemy hook。

**Sandbox**：容器 namespace 含 `tnt_<short_id>` 前缀。

---

### 6. Critical Cross-Service Patterns（P33-P35）

#### P33 — Outbox Pattern Implementation（D15 + Concern #13）

```sql
CREATE TABLE outbox (
    id UUID PRIMARY KEY DEFAULT uuidv7(),
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_version TEXT NOT NULL DEFAULT '1.0',
    payload JSONB NOT NULL,
    metadata JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ,
    attempts INT NOT NULL DEFAULT 0,
    last_error TEXT
);
CREATE INDEX idx_outbox_unsent ON outbox (created_at) WHERE sent_at IS NULL;
```

**写入规则**：业务逻辑在**同一事务**内 INSERT 业务表 + outbox；**禁止跨事务**。

**Outbox Relayer**（独立 service，C12）：
- Poll 周期 100 ms（v1）；v2 起改 LISTEN/NOTIFY
- 每批 ≤100；按 `created_at` 顺序
- Push 到 Redis Streams（P24/P25 schema）
- 成功 → `UPDATE outbox SET sent_at = now()`
- 失败 → `attempts += 1`；≥5 移到 `outbox_dead_letter`
- 监控：`outbox_lag_seconds`、`outbox_relayer_throughput`、`outbox_dead_letter_count`

#### P34 — AIGC Filter 出口屏障（Q2 / C11 / C16）

**统一 package**：`packages/shared-py/aigc_filter/`
```python
from aigc_filter import filter_nl_output, FilterResult
result: FilterResult = await filter_nl_output(
    text=text_chunk_or_full,
    context={"tenant_id": ..., "source": "critic"|"chat"|"nl_summary"},
    mode="stream"|"batch",
)
```

**实现层次（双层）**：
- **Layer 1（per-chunk 即时正则）**：硬编码敏感词正则；每 SSE chunk 通过即转发，命中立即中断 + 替换
- **Layer 2（按段落批量 LLM 调用，C16）**：完整段落累积（句号 OR 500ms 超时触发）→ DeepSeek API + 政策模板审查 → 通过则放行整段
- **Layer 3**：内容标识水印自动追加（FR §1672）

**使用强制**：所有"用户可见 NL 输出"必须 call before transmit
- chat-service SSE → 每 chunk 经 Layer 1 + 段落累积经 Layer 2
- critic-service reasoning → 完整生成后经 Layer 1 + Layer 2
- nl-summary 生成 → 流式但每段必 filter

**测试套件**：
- `tests/aigc/adversarial/` ≥100（M3）→ ≥200（M5）
- `tests/aigc/benign/` ≥100（持续维护）
- CI 全跑，失败 fail PR

#### P35 — License Whitelist Enforcement（Hard Rule #2 / C14）

**`tools/license-check/allowlist.yaml`**：
```yaml
allowed: [MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, Python-2.0, PSF-2.0]
allowed_with_review: [EPL-1.0, EPL-2.0, LGPL-3.0]  # EPL 仅调用不 fork
denied: [GPL-2.0, GPL-3.0, AGPL-3.0, SCIP-Academic, Commercial]
```

**CI Job**：
```yaml
- name: License Check
  run: |
    pnpm exec license-checker-rseidelsohn --json > node-licenses.json
    uv run pip-licenses --format=json > py-licenses.json
    python tools/license-check/verify.py
```

---

### 7. Database & Schema Patterns（P36-P39, P45）— party_mode_18 新增

#### P36 — Datetime Handling

- 所有时间列：**`TIMESTAMPTZ`**（不用 `TIMESTAMP` without timezone）
- Python：`datetime` 必须 timezone-aware（`tzinfo=UTC`）；用 `datetime.now(tz=UTC)`，禁 `datetime.utcnow()`（不带 tz）
- 前端展示：从 UTC 转用户 timezone（Intl.DateTimeFormat）

#### P37 — API Deprecation Headers

```
Sunset: Wed, 31 Dec 2027 23:59:59 GMT
Deprecation: true
Link: <https://api.opticloud.cn/v2/optimizations>; rel="successor-version"
```

**公告渠道**：Console banner + 邮件 + Changelog（三同步）。

#### P38 — Dramatiq Dead Letter Queue

- `attempts >= max_retries` → 自动 enqueue 到 `<service>.dead_letter` 队列
- 监控 metric：`dlq_size`、`dlq_oldest_age_seconds`
- 告警：`dlq_size > 100` OR `dlq_oldest_age_seconds > 1h`
- 处理：每日扫批 + 人工 review + manual replay 或 discard

#### P39 — Optimistic Locking via ETag

- 所有 UI 可编辑资源加 `version` 列（INT，每次更新 +1）
- 响应含 `ETag: "<resource_id>:<version>"`
- 客户端 PUT/PATCH 必带 `If-Match: "<etag>"` → 服务端比对版本，不匹配返 412 Precondition Failed
- 不带 If-Match → 服务端拒绝 428 Precondition Required

#### P45 — Migration Rollback / Destructive Changes

**Destructive migration 必双步**：
- **Drop column**：① add nullable → backfill → enforce not-null → 保留旧列 ≥ 2 月 → drop
- **Change type**：① add new column → dual-write → backfill → cut over → drop old
- 所有 migration 必须实现 `downgrade()`（即使 `pass` 也要明示）
- Schema 变更 PR 必加 `[migration]` 标签 + 双人审

---

### 8. Service-to-Service & Auth Patterns（P40, P46-P48）— party_mode_18 新增

#### P40 — Service-to-Service Auth

- **传输**：mTLS（K8s service mesh 自动；v1 内网信任先简化为 mTLS off + Service Account JWT）
- **Service Account JWT**：每 service 启动从 Vault 拉短期 token（1h TTL）+ 通过 JWKS 自验证
- **业务用户透传**：调用方将 user JWT 通过 `X-OptiCloud-Forward-User` header 传递（chain-of-trust）
- **审计**：所有 service-to-service 调用记录 caller_service + caller_user

#### P41 — Server vs Client Component 划界（Next.js 15 App Router）

- 默认 Server Component（无 `"use client"`）
- 仅需交互（useState/useEffect/onClick/动画/浏览器 API）才标 `"use client"`
- Client 组件文件命名 **`<Xxx>.client.tsx`** 后缀（lint 强制）
- 数据获取在 Server Component（直接调用 service）；Client Component 仅消费 props

#### P46 — Health Check Standardization

| 端点 | 路径 | 用途 | 返回 |
|---|---|---|---|
| Liveness | `GET /healthz` | K8s liveness probe；仅检测 process alive | 200 `{"status": "alive"}` |
| Readiness | `GET /readyz` | K8s readiness probe；检测 DB/Redis/deps | 200 或 503 `{"ready": false, "issues": [...]}` |
| Deep（内网）| `GET /v1/system/health` | Status Page / oncall | 详尽 JSON（含上游 latency / pool / queue depth）|

#### P47 — Canonical JSON for Idempotency Hash

```python
def canonical_sha256(obj: dict) -> str:
    canonical = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:16]  # 16-hex 截断
```

#### P48 — Trace Context Propagation

- HTTP：OpenTelemetry 自动注入 `traceparent` / `tracestate`
- Dramatiq message：actor middleware 自动注入 + 提取（写在 payload metadata）
- Redis Streams event：P25 schema 已含 `traceparent` / `tracestate`
- Outbox：P33 metadata 含 W3C trace context；Relayer 透传

---

### 9. Frontend UX Patterns（P50-P52）— party_mode_18 新增

#### P50 — Loading State 4 种 UI 状态

| 状态 | UI 组件 | TanStack Query 映射 |
|---|---|---|
| **Skeleton** | `<SkeletonCard />` | 首次加载 `isLoading && !data` |
| **Spinner** | `<InlineSpinner />` | `isFetching && data`（已有数据，mutating）|
| **Progress** | `<ProgressBar value=... />` | 长任务 SSE eta_seconds |
| **Optimistic** | `<OptimisticGhost />` | `useMutation` 中 `isPending` + `variables` |

所有组件在 `packages/ui/loading/`；TanStack Query hook 各自显式映射。

#### P51 — Notification 四通道

| 通道 | 库 | 场景 |
|---|---|---|
| Toast | `sonner` | 临时（3s）操作反馈（"已保存" / "失败"）|
| Modal | Radix Dialog | 阻塞性确认（P5 警示、Credits 不足、退款确认）|
| Inline | 表单内 | 字段级错误（与 P52 联动）|
| Banner | 自建（顶部固定）| 全局公告（Status / Deprecation / Maintenance）|

#### P52 — Form Validation Timing

- 字段级：**on blur**（避免输入中骚扰）
- 表单级：**on submit**
- 异步校验（如 API key 名重复）：**debounce 500ms + 显式 spinner**
- Server error：on response 落回字段（Zod schema 与后端 Pydantic 一致）

---

### 10. Process Patterns 补强（P42-P44, P49）— party_mode_18 新增

#### P42 — File Upload Pattern

| 文件大小 | 方式 |
|---|---|
| ≤ 1 MB | multipart POST 直传 |
| 1 MB - 100 MB | **S3 预签名 URL**（推荐统一走）：client 请求 → 后端签 URL → client → S3 直传 → upload-complete webhook |
| ≥ 100 MB | **tus.io 断点续传协议** |

#### P43 — Graceful Shutdown（SIGTERM 处理）

| Service 类型 | 处理 |
|---|---|
| FastAPI（HTTP）| 停 accept 新请求；等已有请求完成 30s；强杀 |
| Dramatiq worker | 停 prefetch；等当前任务完成 60s；强杀（任务自动 retry）|
| Event producer | flush 5s |
| Event consumer | 处理完当前 batch，pause 拉取，30s 优雅退出 |

#### P44 — Configuration Hierarchy

| 类型 | 存储 | 例子 |
|---|---|---|
| **非敏感运行时配置** | ENV | `LOG_LEVEL`、`API_BASE_URL`、`TENANT_ID_LENGTH` |
| **Secret** | **Vault**（绝不入 ENV / Git） | API key、JWT 私钥、DB password、KMS |
| **Feature Flag** | **GrowthBook** | A/B 实验、rollout %、gradual launch |
| **业务配置** | **DB**（管理后台维护） | 计费 k_algo 系数、Critic 置信阈值、风控规则 |

#### P49 — Test Data Builder Pattern

- 后端：`factory_boy` per-aggregate + `pytest fixture`
- 前端：`fishery` + `MSW`（mock service worker）
- 每个 service 提供 `tests/factories/` 公共 fixture 给 integration test

---

### 11. Governance Patterns（P53-P55）— party_mode_18 新增

#### P53 — Architecture Decision Records (ADR)

**模板**：`docs/adr/<NNNN>-<title>.md`

```markdown
# ADR-NNNN: <Title>
**Status**: Proposed | Accepted | Superseded by ADR-MMMM
**Date**: YYYY-MM-DD
**Author**: 课题组

## Context
<问题背景与约束>

## Decision
<决策内容>

## Consequences
<正负后果>

## Alternatives Considered
<未选方案及理由>
```

**规则**：编号递增；不允许修改 Accepted ADR（要变就发 Superseded ADR）；所有架构变更须经 ADR。

#### P54 — Linter / Pre-commit Full Config

- `pyproject.toml [tool.ruff]` 锁定规则集（含命名 P10-P14 检查）
- `eslint.config.js` 锁定规则集 + custom plugin（P16 `.client.tsx` 强制）
- 全仓库统一 `.pre-commit-config.yaml`（service 不允许各自配）
- Pre-commit hooks：ruff format + ruff check + mypy + bandit + license-check + markdownlint + commitlint

#### P55 — `tools/scaffold-service/` New Service Bootstrap CLI

```bash
pnpm tools:scaffold-service \
  --name billing-service \
  --port 8001 \
  --features "dramatiq,outbox,streams"
```

自动生成：
- `apps/billing-service/` 目录结构（P15 模板）
- `pyproject.toml` 依赖 + uv workspace 注册
- `alembic.ini` + `env.py`
- `Dockerfile` multi-stage + 签名 hook
- 健康端点（P46）
- OpenTelemetry 初始化代码
- `pydantic-settings` config schema
- 默认 logging 配置（structlog + P30）

新增 service PR 必经此 CLI 输出（避免 boilerplate 漂移）。

---

### Enforcement Guidelines

#### 所有 AI Agent MUST：

1. 遵循 P1-P55 全部规范；不允许偏离
2. 新 service 必须通过 P55 CLI 生成（不允许从空目录起步）
3. 新业务必须先建 Pydantic schema → OpenAPI codegen → Zod
4. 所有 POST 端点必须实现 P31 幂等性 + P47 canonical hash
5. 所有 NL 输出必须经 P34 AIGC Filter
6. 所有跨服务状态变化必须走 P33 Outbox + P24/P25 事件 + P48 trace context
7. 所有依赖必须经 P35 license check
8. 所有 service-to-service 调用必须 P40 Service Account JWT + chain-of-trust
9. 所有时间字段必须 P36 TIMESTAMPTZ + tz-aware
10. 所有 UI 可编辑资源必须 P39 ETag + If-Match

#### Pattern Enforcement Tools

- **静态检查**：ruff custom rules（py）+ ESLint custom plugin（ts）
- **架构边界**：`grimp`（py）/ `dependency-cruiser`（ts）检测 layer violation
- **CI 必跑**：license-check / aigc-filter test / openapi-codegen drift check / migration smoke test / health endpoint contract test
- **Code Review Bot**：检测 P1-P14 命名违反、P15-P19 结构违反、P36 timezone 违反、P41 client 后缀违反

#### Pattern Update Process

- 修订须发 P53 ADR
- ADR 审通过后更新 `architecture.md` + 通知全员
- 旧代码不强制立即重构；新增代码必符合最新规范

---

### ✅ Good vs ❌ Anti-Pattern 速查

| 类别 | ✅ Good | ❌ Anti-Pattern |
|---|---|---|
| Table | `audit_logs` | `AuditLog`、`auditlog`、`audit_log`（单数）|
| Endpoint | `POST /v1/optimizations` | `POST /v1/optimize`、`/v1/Optimization` |
| Error | RFC 7807 + next_action_url | `{"error": "Failed"}`、`{"msg": "..."}` |
| Event | `optimization.task.completed` | `OptimizationCompleted`、`optimization_complete` |
| Datetime | `TIMESTAMPTZ` + `datetime.now(tz=UTC)` | `TIMESTAMP` + `datetime.utcnow()` |
| Idempotency | 业务表 + outbox 同事务 | 业务表 commit 后再写 outbox |
| Tenant | SQLAlchemy hook 自动注入 | 业务代码每处 `WHERE tenant_id = ?` |
| AIGC Filter | 所有 NL 经 shared-py/aigc_filter Layer 1+2 | chat-service 自实现 filter |
| Logging | `logger.info("task_completed", task_id=..., duration_ms=...)` | `logger.info(f"Task {task_id} done")` |
| Server Component | 默认 Server；交互组件 `.client.tsx` | 全 `"use client"` 不分层 |
| Service-to-Service | mTLS + Service Account JWT + user chain | 直接 HTTP + 无 auth |
| Loading | TanStack 状态明确映射 Skeleton/Spinner/Progress/Optimistic | 各处自定义 spinner 风格不一 |
| Notification | Toast/Modal/Inline/Banner 四通道 | 全 alert / 全 toast |

---

### Patterns 累积总览（55 项）

| 类别 | Pattern # | 数量 |
|---|---|:---:|
| Naming | P1-P14 | 14 |
| Structure | P15-P19 | 5 |
| Format | P20-P23 | 4 |
| Communication | P24-P28 | 5 |
| Process | P29-P32 | 4 |
| Critical Cross-Service | P33-P35 | 3 |
| Database & Schema 补强 | P36-P39, P45 | 5 |
| Service-to-Service & Auth | P40, P46-P48 | 4 |
| Frontend UX 补强 | P50-P52 | 3 |
| Process 补强 | P42-P44, P49 | 4 |
| Governance | P53-P55 | 3 |
| Server/Client 划界 | P41 | 1 |
| **合计** | **P1-P55** | **55** |

### Constraints 累积更新（C1-C16）

| # | Constraint |
|---|---|
| C1 | v1 自研算法 = Python 直调，v2 起 Provider API |
| C2 | 测试环境 LLM mock + 算法 mock 抽象层 |
| C3 | v1 Audit = Postgres `audit_log` 异步入库，v2 末拆库 |
| C4 | v2 接口预留 Revenue-Share Service |
| C5 | CI path-based filtering；M3 末按构建时长决定 Turborepo |
| C6 | Python 版本 monorepo 统一锁定 |
| C7 | 精简档走 Option B-Lite minimal |
| C8 | 精简档替代决策表（D14/D20/D21/D22/D23）|
| C9 | TDE 全环境启用 + CI Vault dev mode |
| C10 | JWT 密钥轮换 = Vault + JWKS endpoint pull 5min |
| C11 | AIGC Filter 出口屏障：所有用户可见 NL 必经统一 filter |
| C12 | Outbox Relayer 独立 service |
| C13 | shadcn/ui 升级策略 = 锁版本 SHA + 季度 re-pull + diff 人审 |
| C14 | License Check Stack = pip-licenses + license-checker-rseidelsohn + allowlist YAML |
| C15 | GPU 调度统一 `gpu-provider` adapter 层 |
| **C16** | AIGC Filter Layer 2 LLM 按段落批量调用（非 per-chunk）；缓冲触发 = 句号 OR 500ms 超时切割 |

---

---

## Project Structure & Boundaries

> v1 末 = **10 deployable services + outbox-relayer sidecars + shared packages**；精简档 = **5 services**。Service 数量已通过 party_mode_19 从原 14 削减至 10。

### Service Catalog（v1 末 = 10 deployable units）

| # | Service | Online | Purpose | 关联 FR / Concern | 端口 | Sidecar | Dependencies |
|---|---|:---:|---|---|:---:|:---:|---|
| 1 | **web** | M1 | Next.js 15 前端（Landing/Docs/Console）| 全部用户可见 | 3000 | — | api-gateway |
| 2 | **api-gateway** | M1 | 公网入口 / 认证 middleware / 限流 / Routing / Idempotency / **data-export Dramatiq actor (FR B10)** / **audit log 查询端点 (FR O3)** | 全部 API / Concern #1/5/6 | 8000 | outbox-relayer (M2+) | auth, solver, billing |
| 3 | **auth-service** | M1 | 注册 / API Key / JWT / 风控 / 教育版 | A1-A10（10）| 8001 | — | Redis / Vault / 短信 |
| 4 | **solver-orchestrator** | M1 | 优化 / 预测算法执行；Provider 路由；Capability lookup（**M1-M2 = `shared-py/capabilities` 静态 8 SKU**；**M3+ 从 capability-registry service 拉 + Redis cache**）| C1-C8 / E1-E10（18）| 8002 | outbox-relayer (M2+) | **M1-M2：static config（shared-py/capabilities）**+ gpu-adapter；**M3+：+ capability-registry + Provider HTTP** |
| 5 | **billing-service** | M2 | Credits 双写账本 / 订阅 / 加油包 / 退款 | B1-B13（13）/ Concern #13 | 8003 | outbox-relayer | Stripe / 微信 / 支付宝 |
| 6 | **chat-service** | M3 | Chat / NL→Model / SSE 流式 / 4-Agent 编排 | N1-N12（12）/ Concern #15 | 8004 | outbox-relayer | LLM API / critic / sandbox |
| 7 | **critic-service** | M3 | Innovation #1 Critic Agent SaaS | N5/N9/N12 / Q1 | 8005 | — | LLM API / capability-registry |
| 8 | **sandbox-runner** | M3 | gVisor 隔离执行 LLM Coder 输出 | N11 / Concern #7 | 8006 | — | gVisor / K8s pod API |
| 9 | **capability-registry** | M3 | 能力词表（极简 CRUD v1；状态机 M5+）| Concern #12 / Q1 / C17 | 8007 | — | Postgres |
| 10 | **repro-service** | M5 | Voucher / Image archive / Auto-migration | R1-R7（7）/ Concern #14 | 8008 | — | S3 Glacier / capability-registry |

**v2 启动时新增**：
- **audit-service**（v1 = `shared-py/audit_log` 异步入库 + api-gateway 查询端点；v2 按数据量拆 service）
- **revenue-share-service**（v1 完全删除；v2 启动时新增 + OpenAPI 一发即 codegen 同步）

**不作 service 的 = shared packages**（per P15/P16）：
- `shared-py/aigc_filter`（P34 / C11 / C16）
- `shared-py/gpu_provider`（C15）
- `shared-py/notification`（v2 拆 service）
- `shared-py/idempotency`（P31/P47）
- `shared-py/auth_client`（P40 Service Account JWT）
- `shared-py/audit_log`（v1 异步入库）
- `shared-py/outbox_relayer`（P56 sidecar 实现）
- `shared-py/openapi_codegen`、`shared-py/otel_setup`、`shared-py/exceptions`、`shared-py/logging`、`shared-py/canonical_json`、`shared-py/trace_context`
- `shared-types`（OpenAPI → TS types + Zod）
- `packages/ui`

**不作 service 的 = infra**：Prometheus / Grafana / Loki / Tempo / Vault / GrowthBook / pgvector / Redis / Postgres / ACR EE / ArgoCD。

---

### Complete Monorepo Tree

```
opticloud/
├── README.md / ARCHITECTURE.md
├── pnpm-workspace.yaml / pyproject.toml / .python-version (3.12)
├── .pre-commit-config.yaml          # P54 锁仓库
├── docker-compose.yml               # 本地 PG + Redis + Vault + gVisor stub
├── docker-compose.test.yml          # 集成测试栈
├── Makefile
│
├── .github/workflows/
│   ├── ci.yml                       # path-filter (C5)
│   ├── service-test.yml
│   ├── license-check.yml            # P35 / C14
│   ├── openapi-drift-check.yml
│   └── deploy.yml                   # ArgoCD 触发
│
├── apps/                            # 部署单元（10 services）
│   ├── web/                         # Next.js 15
│   │   ├── src/{app,features,lib,components,styles}/
│   │   ├── public/
│   │   └── next.config.ts
│   ├── api-gateway/                 # FastAPI (M1)
│   ├── auth-service/                # FastAPI (M1)
│   ├── solver-orchestrator/         # FastAPI (M1)
│   ├── billing-service/             # FastAPI (M2)
│   ├── chat-service/                # FastAPI (M3)
│   ├── critic-service/              # FastAPI (M3)
│   ├── sandbox-runner/              # FastAPI (M3) + gVisor wrapper
│   ├── capability-registry/         # FastAPI (M3, 极简版 v1)
│   └── repro-service/               # FastAPI (M5)
│
├── packages/                        # 共享库
│   ├── shared-types/                # OpenAPI codegen → TS types + Zod
│   ├── shared-py/                   # 共享 Python 库（uv workspace）
│   │   ├── aigc_filter/             # P34 / C11 / C16
│   │   ├── gpu_provider/            # C15
│   │   ├── notification/            # 邮件 + 站内信
│   │   ├── idempotency/             # P31 / P47
│   │   ├── auth_client/             # P40
│   │   ├── audit_log/               # v1 异步入库（替代 audit-service v1）
│   │   ├── outbox_relayer/          # P56 sidecar 实现
│   │   ├── openapi_codegen/ / otel_setup/ / exceptions/ / logging/
│   │   ├── canonical_json/          # P47
│   │   └── trace_context/           # P48
│   ├── shared-py-test/              # factory_boy fixtures (P49)
│   └── ui/                          # React 共享组件（Radix + shadcn）
│       └── src/{primitives,charts,loading,notification}/
│
├── tools/                           # 工程工具（不部署）
│   ├── scaffold-service/            # P55 New Service CLI
│   ├── openapi-codegen/             # Pydantic → openapi.json → TS + Zod
│   ├── license-check/               # P35 / C14
│   │   ├── allowlist.yaml
│   │   └── verify.py
│   └── sbom-gen/                    # Image Supply Chain (Concern #14)
│
├── infra/
│   ├── terraform/
│   │   ├── modules/{ack-cluster,rds-postgres,redis,oss-bucket,vault}/
│   │   └── environments/{dev,staging,prod}/
│   └── argocd/
│       ├── apps/                    # 每 service 一份 manifest
│       └── application-sets/        # ApplicationSet patterns
│
├── docs/
│   ├── adr/                         # P53 ADR
│   ├── runbooks/                    # 应急 SOP
│   ├── onboarding/                  # 新人指南
│   └── customer-faqs/               # 法务问答库 (FR O10)
│
└── _bmad-output/planning/           # 本架构文档存放
```

---

### Service Topology & Boundaries

#### 公网入口层（M1+）

```
                Public Internet
                       │
                       │ HTTPS (TLS 1.3)
                       ↓
              ┌────────────────┐
              │ 阿里云 SLB (L7)   │
              └──────┬─────────┘
                     │
        ┌────────────┴────────────┐
        ↓                         ↓
   ┌─────────┐              ┌──────────────┐
   │   web   │              │ api-gateway  │
   │(Next.js)│              │  (FastAPI)   │
   └─────────┘              │  统一入口     │
                            └──────┬───────┘
                                   │
       ┌───────────────────────────┼───────────────────────────┐
       ↓                           ↓                           ↓
  ┌─────────┐               ┌──────────┐                ┌──────────┐
  │  auth   │               │  solver  │                │ billing  │
  │ service │               │ orchstr. │                │ service  │
  └────┬────┘               └─────┬────┘                └─────┬────┘
       │                          │                           │
       ↓                          ↓                           ↓
   [Postgres]                 [Postgres]                  [Postgres]
   [Redis] [Vault]            [Capability cache]          [Outbox]
                                                          [Stripe/微信]
```

#### Chat + AI 层（M3+，AIGC-gated）

```
                api-gateway (SSE 反代)
                       │
                       ↓
              ┌────────────────┐
              │  chat-service  │
              │   SSE 流式      │
              └───────┬────────┘
                      │
        ┌─────────────┼─────────────┬──────────────┐
        ↓             ↓             ↓              ↓
   ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐
   │ critic- │  │ sandbox- │  │ DeepSeek │  │ capability- │
   │ service │  │  runner  │  │/Qwen API │  │  registry   │
   └────┬────┘  └────┬─────┘  └──────────┘  └─────────────┘
        │            │
        ↓            ↓
  [DeepSeek API] [gVisor 容器]（P58 stdin/stdout/exit_code/emptyDir 通信）
                     │
                     ↓
              [Sandbox 内执行]
              CPU 1 vCPU / Mem 1 GB / 90s hard kill / 禁外网

【所有 NL 输出统一经 shared-py/aigc_filter 双层 (P34)】：
chat / critic / nl-summary → Layer 1 正则 per-chunk + Layer 2 LLM 按段批量
```

#### 异步任务 / 事件层（M2+）

```
┌──────────────────────────────────────────┐
│   Business Service (任一)                  │
│   ┌─────────────────────────────────┐    │
│   │  outbox-relayer sidecar (P56)   │    │ ← 同 pod 不同 container
│   └─────────────────────────────────┘    │
└──────────────────────┬───────────────────┘
                       │
                       │ 同事务 INSERT
       ┌───────────────┼───────────────┐
       ↓                               ↓
   ┌──────────────┐               ┌──────────────┐
   │  业务表        │               │  outbox 表     │
   └──────────────┘               └──────┬───────┘
                                         │ sidecar poll 100ms
                                         ↓
                                  ┌──────────────────────┐
                                  │   Redis Streams      │
                                  │   events.<domain>    │
                                  │   (P24/P25 schema)   │
                                  └──────────┬───────────┘
                                             │
            ┌────────────────────────────────┼────────────────┐
            ↓                                ↓                ↓
   ┌───────────────────┐              ┌──────────────┐  ┌──────────────┐
   │ shared-py/audit_  │              │ notification │  │ api-gateway  │
   │ log 异步入库       │              │ (shared-py)  │  │ data-export  │
   │                   │              │              │  │ Dramatiq actor│
   └───────────────────┘              └──────────────┘  └──────────────┘

并行命令任务（Dramatiq actor invocation）：
  Service → Redis broker (D14/D5) → Dramatiq Workers (per service queue)
```

#### Repro 层（M5+）

```
solver-orchestrator (reproducible=true)
    │
    ↓
┌──────────────────┐
│  repro-service   │
└─────────┬────────┘
          │
          ├──→ 签发 voucher_id (repro-{YYYY}-{6 base32})
          ├──→ Image 签名 → ACR EE → 复制到 S3 Glacier (5y)
          └──→ outbox: repro.voucher.issued
```

---

### Database Topology

#### v1：单 Postgres + Schema 分租户（P5）

```
[ 阿里云 RDS Postgres 4C8G（主）+ 跨区备份 ]
    │
    ├─ schema: public                 # 平台元数据
    │     ├─ algorithms / capabilities
    │     └─ pgvector embeddings
    │
    ├─ schema: tenant_a3f7k2          # 租户 A 数据
    │     ├─ users / api_keys
    │     ├─ optimizations / predictions
    │     ├─ chat_conversations / chat_messages
    │     ├─ credits_ledger / orders / subscriptions
    │     ├─ audit_logs（v1 同库；v2 末拆）
    │     ├─ reproduction_vouchers
    │     ├─ outbox
    │     └─ ...
    └─ schema: tenant_b9k1m5 / ...
```

#### v2 末：分 4 库（C3 + PRD §1612）

```
[ db-core ]    auth / api_keys / tenants / capabilities
[ db-billing ] credits / orders / subscriptions / outbox (billing)
[ db-chat ]    chat_conversations / chat_messages / nl_summaries
[ db-audit ]   audit_logs（独立库 + 7y 归档）  ← audit-service 拆出
```

#### Vector DB 迁移：pgvector → Qdrant（v2 末，触发：月活付费 ≥500 AND 月度 ≥500K embeddings）

---

### K8s Namespace 划分（P60 三域单向流）

```
namespace: prod-core
  ├── api-gateway / auth-service / solver-orchestrator / billing-service
  └── 所有 outbox-relayer sidecar

namespace: prod-ai
  ├── chat-service / critic-service / sandbox-runner / capability-registry

namespace: prod-data
  └── repro-service (含 ACR EE / S3 Glacier 集成)

namespace: prod-shared          # 共享 Tempo / Grafana / Vault / GrowthBook / Prometheus / Loki
namespace: prod-build           # CI/CD 构建临时容器
namespace: staging              # 镜像与 prod 一致
```

**NetworkPolicy 单向流（P60）**：
- `prod-core` → 可调 `prod-ai` ✓
- `prod-ai` → 可调 `prod-data` ✓
- `prod-data` → 不可反向调 `prod-ai` / `prod-core` ❌
- 所有 namespace → 可调 `prod-shared` ✓
- 跨 namespace 调用必须经 mesh + Service Account JWT (P40)

#### Sandbox 特殊隔离

- **sandbox-runner** pods 用 `RuntimeClass: gvisor`
- NetworkPolicy `egress: deny all`（仅允许 capability-lookup 走 metadata service）
- PodSecurityPolicy + seccomp profile
- 资源 limit：1 vCPU / 1 GB / FS RO + emptyDir tmpfs / 90s hard kill via timeout
- **Topology Spread Constraint**：`topologyKey: zone, maxSkew: 1`（M4 容灾）

---

### FR → Service Mapping（77 FR 全覆盖；含 service 合并修订）

| FR 域 | FR 区间 | Owner Service | 备注 |
|---|---|---|---|
| **A** Account & Identity | A1-A10 | **auth-service**（含 A4 教育版邮箱白名单 EduEmailVerifier 模块）| — |
| **C** Algorithm Catalog | C1-C8 | **capability-registry**（数据）+ **api-gateway**（C1 公开端点 + Redis cache）/ **solver-orchestrator**（C4-C7 路由）| C1 免鉴权 = api-gateway 读 capability cache |
| **E** Execution | E1-E10 | **solver-orchestrator**（主）+ **billing-service**（E4 max_solve_seconds 联动 / E8 cancel refund）| E10 backtest v2 |
| **N** Chat & NL | N1-N12 | **chat-service**（编排）+ **critic-service**（N5/N9/N12）+ **sandbox-runner**（N11）| 全 AIGC-gated M3+ |
| **B** Billing | B1-B13 | **billing-service**（主）+ **api-gateway Dramatiq actor**（B10 PIPL 数据导出）| B10 跨域聚合走 api-gateway read-only 跨库账号（W4）|
| **R** Reproducibility | R1-R7 | **repro-service**（主）+ **capability-registry**（R4 capability 匹配 + R7 退出预通知）| R5 BibTeX v1 必上；其他 v1 末/v2 |
| **P** Provider | P1-P8 | **capability-registry**（P1-P3 注册/shadow/灰度 v2）+ **solver-orchestrator**（P4-P7 路由）+ **revenue-share-service v2**（P8）| 主要 v2 |
| **O** Observability | O1-O11 | **shared-py/audit_log**（O3 异步入库）+ **api-gateway**（O3 查询 / O6 限流 / O7 next_action_url）+ **chat-service / critic-service**（O5 aigc_filter）+ **capability-registry**（O8 mode=teaching / O11 算例库）| O2 Postmortem = docs/runbooks |

---

### Cross-Cutting Concerns → Locations

| # | Concern | 实现位置 |
|---|---|---|
| 1 | 多租户隔离 | `shared-py/middleware/tenant_context.py` + SQLAlchemy hook（全 service）|
| 2 | 同 / 异步混合 | `api-gateway` 自动 sync→async + Dramatiq + Streams |
| 3 | i18n / 双语 | `shared-py/i18n` + Next.js `next-intl` + Pydantic `Accept-Language` |
| 4 | 可观测 | `shared-py/otel_setup/` + infra Prometheus/Grafana/Loki/Tempo |
| 5 | 幂等性 | `shared-py/idempotency/` decorator |
| 6 | API 版本化 | `apps/<svc>/src/<svc>/api/v1/` + `X-API-Version` middleware |
| 7 | 沙箱执行 | `sandbox-runner` service |
| 8 | Provider 路由 | `solver-orchestrator` + `capability-registry` |
| 9 | 复现保证 | `repro-service` + `capability-registry` |
| 10 | 合规底盘 | `shared-py/aigc_filter` + `shared-py/audit_log` + `api-gateway data-export actor` |
| 11 | License 守门 | `tools/license-check/` + CI Job |
| 12 | Capability Registry | **M1-M2**：`shared-py/capabilities/` 静态配置（8 SKU 硬编码 YAML）；**M3 起**：`capability-registry` service 接管 + Redis SWR cache；**M5+**：加状态机（shadow/灰度）+ prompt-store sub-module |
| 13 | Distributed Billing Transaction | `billing-service` + `outbox-relayer sidecar` + `shared-py/idempotency` |
| 14 | Image Supply Chain | `tools/sbom-gen/` + `infra/argocd/`（签名 hook）+ `repro-service`（5y 归档）|
| 15 | Streaming Connection Lifecycle | `chat-service` SSE handler + `apps/web/src/lib/sse-client.ts` + `api-gateway` streaming proxy |
| 16 | Worker Topology 分层 | Dramatiq queues by purpose（real-time / batch / retry / scheduled）|
| 17 | Human-in-the-Loop Review Queue | `critic-service` 转人工队列（Redis Stream **`events.critic`**，event_type **`critic.review.escalated`**，per P24/P25）+ Console review UI |
| 18 | Internal SLA Telemetry Dashboard | Grafana dashboard JSON（`infra/grafana/dashboards/`）|
| 19 | Console Frontend Stack | `apps/web` + `packages/ui` |

---

### New Patterns Added in party_mode_19（P56-P61）

#### P56 — Outbox Relayer Sidecar Pattern（替代 outbox-relayer 独立 service）

```
┌─────────────────────────────────────────┐
│  Pod: billing-service                   │
│   ┌─────────────────────────────────┐   │
│   │ Container: billing-service       │   │
│   │   FastAPI 主进程                 │   │
│   └─────────────────────────────────┘   │
│   ┌─────────────────────────────────┐   │
│   │ Container: outbox-relayer        │   │
│   │   shared-py/outbox_relayer 运行  │   │
│   │   poll local PG + push to broker│   │
│   └─────────────────────────────────┘   │
│   Shared: localhost loopback / shutdown │
└─────────────────────────────────────────┘
```

- 同 pod 不同 container；同 lifecycle；同 SA 凭证
- 监控 metric：`outbox_lag_seconds`（per service）
- 失败 ≥ 5 → 移到 `outbox_dead_letter` 表 + 告警

#### P57 — Chat Path 延迟预算

| 节点 | 延迟预算（P95）|
|---|---|
| api-gateway middleware | < 50 ms |
| chat-service ↔ critic-service / sandbox / capability cumulative | ≤ 200 ms |
| gVisor warm pool startup（pre-warmed 1-2 容器 standby）| ≤ 100 ms（vs cold 1500 ms）|
| DeepSeek 首 Token | ≤ 1500 ms（P50；外部依赖）|
| AIGC Filter Layer 2 | **段后置**（不阻塞 first token；段完成 + 500 ms 触发）|
| capability-registry lookup | < 20 ms（Redis cache + 内存 LRU）|

**总 SLO**：首 Token P50 < 1.5 s / P95 < 3 s / E2E 解算 ≤ 90 s。

#### P58 — Sandbox I/O Pattern

容器内**仅能**通过：
- `stdin` 接受输入数据（沙箱启动时挂载 emptyDir 文件 + 容器读）
- `stdout` 流式输出（sandbox-runner 抓 K8s pod logs API + SSE 透传给 chat-service）
- `exit_code` 表示成功 / 失败 / OOM
- `emptyDir` mount 写结果文件（最多 100 MB）

**禁止**：
- 外网访问（NetworkPolicy egress: deny all）
- 跨容器 IPC（除 sandbox-runner pod 内）
- 修改 FS（除 emptyDir tmpfs）

**SSE 进度流**：sandbox-runner SSE → chat-service SSE → api-gateway streaming proxy → web SSE client。

#### P59 — Critical Service Resilience

适用于 **capability-registry / auth-service / billing-service**（critical path）：

- Redis cache TTL 30 min + **stale-while-revalidate** 模式（cache 过期仍返回 + 后台异步刷新）
- 多副本（standard ≥ 3 replicas / minimum ≥ 2）+ readiness probe
- **Last-known-good snapshot**：每日打 snapshot 到 S3；cache miss + service 不可达 → 调用方 fallback to snapshot
- HTTP client（shared-py/auth_client 等）：内置 circuit breaker（half-open after 60s）+ 自动 fallback to snapshot

#### P60 — K8s Namespace 三域 + NetworkPolicy 单向流

（详 K8s Namespace 划分章节）

#### P61 — Contract Test + Critical Journey E2E

**Contract Test**（Schemathesis OpenAPI-driven）：
- 每个 service 的 `openapi.json` → Schemathesis 自动生成 property-based tests
- 验证：schema 一致性、错误响应格式、boundary case、安全性（fuzz）
- CI 必跑；service 间 contract 通过即可

**Critical Journey E2E**（Playwright）：仅 J1 物流主管 / J2 数据分析师错误恢复 / J8 AIGC 巡查
- 跨 service 启动完整栈
- 完整用户路径
- CI 每日 nightly 跑（不入 PR gate）

---

### Boundary Rules（多 agent 实现强制约束）

| 边界 | 规则 |
|---|---|
| 跨 service DB 访问 | ❌ 禁直接读对方 DB 表；✅ HTTP/event 调用 |
| 公网入口 | ✅ 唯一通过 `api-gateway` 暴露 |
| Service-to-Service Auth | ✅ Service Account JWT + user chain；❌ 禁 service 直接 trust 调用方 |
| Side Effects | ✅ 任何状态变化走 outbox（同事务）；❌ 禁业务表 commit 后再发 event |
| Sandbox 调用 | ✅ 仅 `sandbox-runner` 可调 gVisor；其他禁直接 spawn 容器 |
| AIGC Filter | ✅ 所有 NL 输出经 `shared-py/aigc_filter`；❌ 禁 service 自实现 |
| 跨服务批处理读取 | ✅ 通过 `api-gateway data-export actor` 或事件溯源；❌ 业务 service 禁拉对方数据 |
| 跨 namespace 调用 | ✅ 仅按 prod-core → prod-ai → prod-data 单向流；❌ 反向调用须 ADR 审批 |
| SSE 反代 | ✅ 经 api-gateway streaming proxy（FastAPI StreamingResponse + uvicorn h11）；❌ 禁 Nginx proxy buffering |

---

### Service 依赖图（v1 末 = M5）

```
                          web ───→ api-gateway
                                       │
        ┌──────────┬────────────┬──────┼──────┬──────────────┐
        ↓          ↓            ↓      ↓      ↓              ↓
      auth     solver       billing  chat   critic       capability
                              │       │       │             registry
                              │       ↓       │                ↑
                              │   sandbox     │                │
                              │   runner      │                │
                              │       ↑       ↓                │
                              │       └────chat-service        │
                              │                                │
                              ↓                                │
                       outbox-relayer ───→ Redis Streams       │
                            (sidecar)              │           │
                                                   ↓           │
                                        shared-py/audit_log    │
                                                   ↓           │
                                              repro-service ───┘
                                                   ↓
                                        ACR EE + S3 Glacier
```

---

### Updated Constraints C17-C18

| # | Constraint |
|---|---|
| **C17** | capability-registry 演进路径：**M1-M2 = `shared-py/capabilities/` 静态 YAML 配置（8 SKU 硬编码）**；**M3 起**独立 service 极简 CRUD + Redis SWR cache；**M5+** 加状态机（shadow validation / 灰度发布）+ **prompt-store sub-module**（P68 prompts 入库 + 版本化）；**v1.5 评估**是否拆 prompt-store 为独立 service |
| **C18** | 精简档 service 列表 = **5 services**（web + api-gateway（含 auth + billing）+ solver-orchestrator + chat-with-critic + sandbox-runner）；audit / data-export / capability 全合 api-gateway / shared-py |

### Updated Story Occupancy

| Story | 状态 | 描述 |
|---|:---:|---|
| 0.1-0.8 | ✅ 保留 | Monorepo Foundation 8 stories（详 Step 3）|
| **0.9** | ❌ 删 | Outbox Relayer Service（改 sidecar）|
| **0.9a** | ✅ 新增 | Outbox Relayer Sidecar 集成（每 service 部署）|
| 0.10 | ✅ 保留 | Billing 双写一致性测试 |
| **0.11** | ✅ 新增 | Sandbox I/O Pattern 实现（P58）|
| **0.12** | ✅ 新增 | Contract Test 框架（P61 Schemathesis）|
| **0.13** | ✅ 新增 | K8s Namespace 三域拆分 + NetworkPolicy（P60）|

---

### Development Workflow Integration

#### 本地开发

```bash
# 启动基础设施
docker compose up -d
# → PG + Redis + Vault dev + gVisor stub + GrowthBook dev + ElasticMQ for S3 stub

# 启动 monorepo
pnpm install && uv sync

# Frontend
cd apps/web && pnpm dev

# Backend service（每个类似）
cd apps/api-gateway && uv run uvicorn src.api_gateway.main:app --reload --port 8000

# Outbox sidecar（local mode）
cd apps/billing-service && uv run python -m shared_py.outbox_relayer.runner --service billing

# 单 service 测试
cd apps/<svc> && uv run pytest
cd apps/web && pnpm test

# Contract test 全栈
pnpm test:contract  # Schemathesis 跑所有 OpenAPI

# E2E（仅 nightly）
pnpm test:e2e
```

#### Build Process

- **Frontend**：Next.js 15 Turbopack → `apps/web/.next/`
- **Backend**：Docker multi-stage + 签名 hook → ACR EE → ACK rolling deploy via ArgoCD
- **Shared packages**：`tsup`（ts）/ `uv build`（py）
- **OpenAPI codegen**：CI 触发 → `packages/shared-types/src/openapi/*.ts` + Zod schemas

#### Deployment

- **GitOps**：所有 K8s manifest 在 `infra/argocd/`；ACK One GitOps 监听 main branch
- **Canary**：Argo Rollouts 5% → 25% → 50% → 100%
- **Rollback**：ArgoCD UI 一键回滚 + Argo Rollouts 自动 abort（KPI 跌破阈值 → P59 fallback to last-known-good snapshot）

---

### Constraints 累积总览（C1-C18）

| # | Constraint | 章节 |
|---|---|---|
| C1 | v1 自研算法 = Python 直调，v2 起 Provider API | Step 2 |
| C2 | 测试环境 LLM mock + 算法 mock 抽象层 | Step 2 |
| C3 | v1 Audit = Postgres `audit_log` 异步入库，v2 末拆库 | Step 2 |
| C4 | v2 接口预留 Revenue-Share Service | Step 2 |
| C5 | CI path-based filtering；M3 末按构建时长决定 Turborepo | Step 3 |
| C6 | Python 版本 monorepo 统一锁定 | Step 3 |
| C7 | 精简档走 Option B-Lite minimal | Step 3 |
| C8 | 精简档替代决策表 | Step 4 |
| C9 | TDE 全环境启用 + CI Vault dev mode | Step 4 |
| C10 | JWT 密钥轮换 = Vault + JWKS endpoint pull 5min | Step 4 |
| C11 | AIGC Filter 出口屏障：所有用户可见 NL 必经统一 filter | Step 4 |
| C12 | Outbox Relayer 独立 service → P56 修订为 sidecar | Step 4 → P56 |
| C13 | shadcn/ui 升级策略 | Step 4 |
| C14 | License Check Stack | Step 4 |
| C15 | GPU 调度统一 `gpu-provider` adapter 层 | Step 4 |
| C16 | AIGC Filter Layer 2 LLM 按段批量调用 | Step 5 |
| **C17** | capability-registry 启动形态 = M3 极简 CRUD + Redis cache | Step 6 |
| **C18** | 精简档 = 5 services | Step 6 |

### Patterns 累积总览（61 项）

| 类别 | Pattern # | 数量 |
|---|---|:---:|
| Naming | P1-P14 | 14 |
| Structure | P15-P19 | 5 |
| Format | P20-P23 | 4 |
| Communication | P24-P28 | 5 |
| Process | P29-P32 | 4 |
| Critical Cross-Service | P33-P35 | 3 |
| DB & Schema 补强 | P36-P39, P45 | 5 |
| S2S & Auth | P40, P46-P48 | 4 |
| Frontend UX | P50-P52 | 3 |
| Process 补强 | P42-P44, P49 | 4 |
| Governance | P53-P55 | 3 |
| Server/Client 划界 | P41 | 1 |
| **Step 6 新增** | **P56-P61** | **6** |
| **合计** | **P1-P61** | **61** |

---

---

## Architecture Validation Results

> 经 party_mode_20 对抗式审查修订后；3 Critical Gaps 必须在 Sprint 0-M3 期间解决；总体 readiness HIGH-conditional。

### Coherence Validation ✅ PASS

**Decision Compatibility**：
- ✅ FastAPI 0.136 + Pydantic v2 + SQLAlchemy 2.0 + Next.js 15 + Python 3.12 全 stable 互兼容
- ✅ LLM 路径：DeepSeek + Qwen-Max + aigc_filter + Critic 协同
- ✅ 求解器栈 Apache/MIT/EPL 全通过 P35 license check
- ✅ Dramatiq（命令）+ Redis Streams（事件）+ P56 sidecar Outbox 三层职责分明
- ✅ Monorepo 工具链（pnpm + uv + Turbo deferred + GitHub Actions）一致
- ✅ 无矛盾决策（经 6 轮 party_mode 消解）

**Pattern Consistency**：
- ✅ P1-P14 命名规则跨技术栈一致
- ✅ P24/P26/P6 共用 "domain.aggregate.verb" 风格
- ✅ P31 幂等 + P47 canonical + P33 Outbox 完整事务链
- ✅ P34 AIGC Filter + P57 Chat 路径 + P58 Sandbox I/O 完整 NL 出口屏障
- ✅ P40 + P48 + P60 完整跨 service 通信约束
- ✅ P59 + P43 + P38 完整可靠性栈

**Structure Alignment**：
- ✅ 10 services × P15 模板一致
- ✅ apps/packages/tools/infra/docs 5 层清晰
- ✅ P60 K8s namespace 三域 完全对应 service catalog
- ✅ Boundary Rules 与拓扑一致

---

### Requirements Coverage Validation ✅ 100%

**Functional Requirements 77 FR → Service Mapping**：

| FR 域 | 数量 | Owner Service | 完整性 |
|---|:---:|---|:---:|
| A. Account & Identity | 10 | auth-service（含 EduEmailVerifier）| ✅ |
| C. Algorithm Catalog | 8 | capability-registry + api-gateway + solver | ✅ |
| E. Execution | 10 | solver-orchestrator + billing | ✅ |
| N. Chat & NL | 12 | chat + critic + sandbox-runner | ✅ |
| B. Billing | 13 | billing + api-gateway data-export actor | ✅ |
| R. Reproducibility | 7 | repro-service + capability-registry | ✅ |
| P. Provider | 8 | capability + solver + revenue-share v2 | ✅ |
| O. Observability | 11 | shared-py/audit_log + api-gateway + chat + critic | ✅ |
| **合计** | **77** | — | **✅ 77/77** |

**Non-Functional Requirements 11 类 → 架构支持**：

| NFR 类别 | 架构支持 | 关键 Patterns/Decisions |
|---|---|---|
| 1. Performance | ✅⚠️ | P57 + D4 + D5 + 求解 SLO 分级；**⚠️ Critical Gap G6 需压测验证** |
| 2. Security | ✅ | D7 HMAC + Vault / D8 EdDSA / D10 TDE + Vault KMS / D11 SameSite / P40 / P58 |
| 3. Scalability | ✅ | D21 ACK / D6 → Kafka v2 末 / D5 / C15 / Qdrant / 4-DB v2 末 |
| 4. Reliability | ✅ | P38 DLQ / P43 / P59（升级 4-tier）/ D15 / RTO v1 24h → v2 4h |
| 5. Compliance | ✅⚠️ | P34 + P62 自循环防护 / P35 / C9 / C11 / B10 + G8 删除 actor / FR O1；**⚠️ G12 水印细节待补** |
| 6. Provider Integration | ✅ | capability-registry shadow + 灰度 / D13 circuit breaker / R7 30d 预通知 |
| 7. Accessibility | ✅ | P19 + axe-core / shadcn/ui 内建 a11y |
| 8. Localization & i18n | ✅ | shared-py/i18n + next-intl + Accept-Language + Pydantic-Zod sync |
| 9. Browser & Platform | ✅ | Next.js 15 + latest 2 versions / 不支持 IE |
| 10. Observability | ✅ | P30 + P48 + P59 + shared-py/otel_setup |
| 11. Cost & Unit Economics | ✅⚠️ | C15 + P57 + D14；**⚠️ Critical Gap G3 Per-tenant cost-attribution 必上** |

**Innovations 7 项 → 架构兑现** ✅ 7/7

**Hard Rules 6 条 → 工程实施**：3 工程支持（License + Marketplace gate + Postmortem）+ 3 非工程范畴（治理 / 融资）

**Risks 11 项 → 缓解工程**：10/11（R9 非工程范畴）

---

### Implementation Readiness Validation

**Decision Completeness**：
- ✅ 23 Core Decisions D1-D23 + Q1-Q3
- ✅ 20 Constraints C1-C20（含精简档替代表）
- ⚠️ 3 Critical Gaps 必须 Sprint 0-M3 期间解决

**Structure Completeness**：
- ✅ 10 services × P15 模板
- ✅ 完整 monorepo 树（apps + packages + tools + infra + docs）
- ✅ K8s 5 namespaces（P60 三域单向流 + shared + build）
- ✅ Database 多租户 schema + v2 末 4-DB 路径

**Pattern Completeness**：
- ✅ **64 Patterns**（P1-P64）覆盖 Naming/Structure/Format/Communication/Process/Critical/DB/Auth/UX/Governance/Server-Client/Step6 新增/**Step7 新增**
- ✅ Enforcement 工具：ruff custom rules + ESLint plugin + grimp + dependency-cruiser + 7 CI 必跑
- ✅ Good vs Anti-Pattern 速查

**Cross-Cutting Concerns 19 项 → 实现位置**：✅ 19/19 全归属

---

### Gap Analysis（修订后）

#### 🔴 Critical Gaps（3 项，必须 Sprint 0 - M3 期间解决）

| # | Gap | 来源 | 补救路径 | 截止 |
|---|---|---|---|:---:|
| **G3** | **Per-tenant / Per-service 成本监控**（NFR §11.2 5 项红线无实施 = 商业指标失明）| Mary My2 | shared-py/cost_telemetry middleware + Grafana dashboard + monthly alert rules | M3 末 |
| **G6** | **Chat 延迟预算未经端到端压测**（DeepSeek P95 3-5s + service hop variance 大概率突破 3s SLO）| Murat M1 | M3 末 staging 全栈 k6/Locust 压测 + 主观体验测试；不达标须 critic 异步化 / aigc_filter Layer 2 离线化 | M3 末 hard-gate |
| **G7** | **S3 Glacier 检索 5-12h 与 Repro 5y SLA 冲突**（24h rerun 预算紧）| Murat M2 | Image 分层归档：**热 ACR EE 90d / 温 S3 Standard-IA 1y / 冷 S3 Glacier 5y**；按需检索 | M5 起步设计 |

#### 🟠 Important Gaps（9 项，Story 0 - M5 期间补齐）

| # | Gap | 来源 | 补救路径 |
|---|---|---|---|
| **G1** | Sandbox Image Build Pipeline 工具链具体 | Step 7 | Story 0.8 + 0.11 cosign + Notation + ACR EE |
| **G2** | OAuth 2.0 v2 第三方授权流详细设计 | Step 7 | v2 启动时新 ADR；v1 仅 API Key + JWT |
| **G4** | v1 → v2 4-DB 拆库 migration 具体步骤 | Step 7 | M9 单独 ADR 设计 dual-write → cutover |
| **G5** | gVisor warm pool 池大小动态调整算法 | Step 7 | KEDA + HPA + warm pool controller，M5+ 调整 |
| **G8** | **PIPL 数据删除 actor 设计**（dry-run + soft + 7d hard + 4 store cascade）| Murat M5 | api-gateway Dramatiq actor + soft delete 期可恢复 |
| **G9** | **Critic 置信度校准 ground truth 标注**（M0-M1 启动）| Murat M6 | 标注工具 + SOP + 验证策略；标注成本 200-300 人时 |
| **G10** | **GPU 自建触发器**（monthly job + 4 重 AND 越界告警）| Mary My1 | jobs/ namespace Dramatiq scheduled task |
| **G11** | **audit_log 查询 SLA + 索引 + 分区 + 物化视图**（7d <500ms / 30d <2s / 90d+ 异步导出）| Mary My3 | M5 起 audit_log 表设计强化 |
| **G12** | **AIGC 水印实施细节**（文本尾标 + zero-width Unicode + trace_id + 测试集）| Mary My4 | Story 0.x 加入水印 module，含测试 |
| **G13** | **精简档 sandbox-runner 替代**（docker-compose + gVisor on Docker / runsc runtime）| Indie I2 | 精简档 ADR 独立设计；warm pool = keep-alive container |

#### 🟡 Nice-to-Have Gaps（v1.5+ / v2 补，含 Step 6 + Step 7 新增）

| # | Gap | 优先级 |
|---|---|---|
| N1 | 具体 K8s manifest 内容（resource limits / probes / RBAC）| Story 0.13 |
| N2 | 具体 ArgoCD ApplicationSet 模板 | Story 0.13 |
| N3 | 详细 Grafana dashboard JSON | M3 末 |
| N4 | 详细告警路由（Sentry / PagerDuty / 钉钉机器人）| M3 末 |
| N5 | Provider 接入开发者文档 | v2 启用前 |
| **G14** | GPU 资源配额（per-tenant 并发限制）+ fair scheduling | Winston W3 → v2 |
| **G15** | Pydantic-Zod 双向同步（基础自动 + 复杂规则手动 + 双侧测试）| Amelia A2 → 持续维护 |

---

### Validation Issues Addressed（累积 91+22=113 处修订）

| Round | 问题 → 解决 |
|---|---|
| party_mode_15 | Step 2 17 处遗漏（Capability Registry / Billing Transaction / Image Supply Chain）→ Concerns #12-19 |
| party_mode_16 | Step 3 12 处过度工程 → Option B → Option B-Lite |
| party_mode_17 | Step 4 18 处决策细节 → HMAC + Dramatiq + Outbox 独立 service |
| party_mode_18 | Step 5 20 处 pattern 遗漏 → P36-P55 |
| party_mode_19 | Step 6 24 处 service 数量过度 → 14 → 10 + P56-P61 + C17-C18 |
| **party_mode_20** | **Step 7 22 处验证乐观断言** → 3 Critical Gaps + G8-G15 + P62-P64 + C19-C20 + P59 4-tier fallback + C18 revised |
| **合计** | **113 处累积修订** |

---

### New Patterns Added in party_mode_20（P62-P64）

#### P62 — AIGC Filter Self-Loop Prevention

防止 aigc_filter Layer 2 LLM call 递归触发自己。

```python
# aigc_filter 内部 LLM 调用
async def call_filter_llm(prompt: str) -> FilterResult:
    headers = {
        "Authorization": f"Bearer {INTERNAL_FILTER_TOKEN}",  # 特殊 scope
        "X-OptiCloud-Internal-Scope": "aigc-filter-self-loop",
    }
    # 此调用绕过出口 filter（标识为内部审计）+ 完整日志
    return await deepseek_client.post(prompt, headers=headers)
```

**约束**：
- 绕过 token 仅 aigc_filter pod 内 Service Account 可用
- 100% 审计日志（即使绕过 filter，调用本身仍记录）
- 测试集含 prompt injection 试图伪装 filter 的对抗用例

#### P63 — Event Versioning Compatibility

事件 schema 演进规则：

- **新增字段 only**（向后兼容）：直接 bump minor version（1.0 → 1.1）
- **重命名 / 移除字段**（破坏）：发布者必须**双发新旧版本**（dual publish），持续 N=3 months minor 周期，确认所有消费者升级后才停旧版本
- 消费者必须实现 schema-tolerant parse（unknown field 容忍）
- v2 起引入 schema registry（Confluent 或自建）+ 自动适配 layer

#### P64 — OpenAPI Codegen Workflow

monorepo 多 service 类型同步流水线：

```
per-service /openapi.json endpoint
    ↓
CI 触发（PR / main push）
    ↓
fetch + 校验（Pydantic2Zod + TypeScript codegen）
    ↓
写入 packages/shared-types/<service>/index.ts + zod.ts
    ↓
commit hash 比对（drift check）→ 不一致 fail PR
```

**约束**：
- 每个 service 必有 `/v1/openapi.json` endpoint
- CI 上线后禁手工修改 `packages/shared-types/`（覆盖式生成）
- drift check 在 PR gate 必跑

---

### New Constraints Added in party_mode_20（C19-C20）

| # | Constraint |
|---|---|
| **C19** | 精简档 deployment = GitHub Actions + docker-compose 蓝绿（替代 K8s + ArgoCD canary） |
| **C20** | 业务 service rolling deploy `maxUnavailable=1` + `minReadySeconds=15` + sidecar readiness 前置主 container 健康标记 |

---

### Modified Patterns / Constraints in party_mode_20

#### P59 升级为 4-Tier Fallback

| Tier | Fallback | 触发 |
|---|---|---|
| 1 | **Redis cache**（30 min TTL + stale-while-revalidate）| 命中即返 |
| 2 | **S3 daily snapshot** | Redis miss + service 不可达 |
| 3 | **Postgres readonly replica（cross-region）** | S3 不可达（如阿里云 OSS 故障）|
| 4 | **本地 emptyDir snapshot（pod 启动时 sidecar 预下载）** | 全外部依赖不可达 |

#### C18 修订：精简档 chat-with-critic 明示

- `chat-with-critic` = chat-service **内嵌 inline critic**
- 不独立部署 / 不红队跑批 / 不对外暴露 critic API
- 精简档 critic 阈值**固定 0.6**（不动态校准；G9 不适用精简档）

---

### Architecture Completeness Checklist

#### ✅ Requirements Analysis
- [x] Project context thoroughly analyzed
- [x] Scale & complexity assessed
- [x] Technical constraints identified（20 C1-C20）
- [x] Cross-cutting concerns mapped（19 项 with locations）

#### ✅ Architectural Decisions
- [x] Critical decisions documented with versions（D1-D23 + Q1-Q3）
- [x] Technology stack fully specified（2026-05 web 验证）
- [x] Integration patterns defined（D12-D15）
- [x] Performance considerations addressed（P57 + G6 待压测）

#### ✅ Implementation Patterns
- [x] **64 Patterns**（P1-P64）覆盖全维度
- [x] Naming / Structure / Communication / Process / Critical / DB / Auth / UX / Governance
- [x] Step 7 新增 P62 自循环防护 / P63 事件版本兼容 / P64 OpenAPI codegen workflow

#### ✅ Project Structure
- [x] Complete monorepo tree
- [x] 10 services + sidecar pattern + shared packages 完整
- [x] K8s namespace 三域单向流
- [x] FR → Service mapping 完整

#### ✅ Governance & Operations
- [x] ADR Template + 编号规则（P53）
- [x] Linter / Pre-commit 锁定（P54）
- [x] Scaffold-service CLI（P55）
- [x] License Check Stack（P35 / C14）
- [x] Epic 0 Foundation Stories 0.1-0.13 完整

#### ⚠️ Pending（Critical Gaps）
- [ ] G3 Per-tenant 成本监控（M3 末必须）
- [ ] G6 Chat 延迟预算压测（M3 末 hard-gate 验证）
- [ ] G7 Image 分层归档（M5 起步）

---

### Architecture Readiness Assessment

**Overall Status**：**READY FOR IMPLEMENTATION** ✅

**Confidence Level**：**HIGH-conditional**

- ✅ Architecture decisions complete
- ✅ FR/NFR coverage 100%
- ⚠️ 3 Critical Gaps 必须在 M3 末前解决才能进入 M5 商用路径
- ⚠️ AIGC Filter 自循环（P62）必须 Story 0 期间设计 + 实现

**Key Strengths**：

1. **Service 数量优化**（14 → 10 deployable）— 团队规模匹配
2. **精简档完整 fallback**（C7 + C8 + C18 + C19）— 1-2 人也可启动
3. **AIGC 合规深度设计**（P34 + P62 自循环防护 + C11 + C16 + 双测试集 + G12 水印）
4. **Repro 5y SLA 工程化升级**（repro-service + 分层归档 G7 + Provider 退出预通知）
5. **多 Agent NL Pipeline + Sandbox 隔离深度**（critic-service + sandbox-runner + P58 + P57 延迟预算）
6. **Cloud Lock-in 风险缓解**（R11 + P60 + Terraform module 抽象 + AWS backup）
7. **完整 ADR 治理**（P53 + Patterns Enforcement 工具链）
8. **4-Tier Critical Service Resilience**（Redis → S3 → PG replica → 本地 emptyDir）
9. **Event Versioning 兼容性**（P63 dual publish + schema-tolerant parse）
10. **OpenAPI Codegen Workflow**（P64 自动同步 + drift check 防漂移）

**Areas for Future Enhancement**（v1.5+ / v2+）：

1. v2 末 4-DB 拆库 migration playbook（G4）
2. OAuth 2.0 v2 详细设计（G2）
3. GPU 资源配额 + fair scheduling（G14，v2 起）
4. Pydantic-Zod 复杂规则同步策略（G15，持续维护）
5. KEDA + HPA + warm pool controller 动态调整（G5）
6. Provider 接入开发者文档（v2 启用前）（N5）

---

### Implementation Handoff

#### AI Agent Guidelines

- **遵循全部 64 Patterns + 20 Constraints**；任何偏离须经 P53 ADR 审批
- **新 service 必通过 P55 CLI 生成**（不允许从空目录起步）
- **新业务 schema 必经 Pydantic → OpenAPI codegen → Zod**（P64 workflow）
- **所有 POST 必实现 P31 幂等性 + P47 canonical hash**
- **所有 NL 输出必经 P34 AIGC Filter（Layer 1 + Layer 2 + P62 防自循环）**
- **所有跨服务状态变化必经 P33 Outbox + P48 Trace Context + P56 sidecar Relayer**
- **Service-to-Service 必用 P40 Service Account JWT + user chain-of-trust**
- **跨 namespace 必遵 P60 单向流（prod-core → prod-ai → prod-data）**
- **事件 schema 演进必遵 P63 dual publish + N=3 月**

#### First Implementation Priority

**Epic 0 Foundation Sprint 0**（2-4 周）：

```bash
# 1. 初始化 monorepo
mkdir opticloud && cd opticloud
git init && pnpm init
echo "packages:\n  - 'apps/*'\n  - 'packages/*'" > pnpm-workspace.yaml
pip install uv && echo '3.12' > .python-version

# 2. 启动初始 service（M1）
pnpm tools:scaffold-service --name api-gateway --port 8000
pnpm tools:scaffold-service --name auth-service --port 8001
pnpm tools:scaffold-service --name solver-orchestrator --port 8002
pnpm create next-app@latest apps/web --typescript --tailwind --eslint --app --turbopack --yes

# 3. 配置 pre-commit + license-check + CI path-filter
cp .pre-commit-config.yaml docker-compose.yml ...
pre-commit install
```

#### Epic 0 Stories 总览（Sprint 0 = 8 stories，2-4 周）

> ⚠️ **修订 v2.1**：原 16 stories 严重超载（~45 person-week vs Sprint 0 容量 20 person-week）。Sprint 0 严格限定 8；其余 8 stories 分到 M2-M3 sprint，与业务 Epic 并行。

**Sprint 0 Foundation（依赖顺序已纠正）**：

| Story | 描述 | 依赖 | Pattern | 关联 Gap |
|---|---|---|---|---|
| 0.1 | Monorepo 骨架 | — | P14-P15 | — |
| 0.2 | docker-compose 本地栈 | 0.1 | P15 | — |
| 0.5 | Pre-commit + ruff + mypy + bandit + license-check | 0.1 | P35 + P54 | — |
| 0.6 | Auth scaffold（FR A1-A2 + OpenAPI spec）| 0.1, 0.5 | P40 + D7-D8 | — |
| 0.7 | Health/Readiness 端点 + OpenTelemetry | 0.6 | P46 + P48 | — |
| 0.4 | **shared-types OpenAPI codegen pipeline + drift check** | 0.6 | P17 + P54 + **P64** | — |
| 0.3 | CI path-filter + per-service test | 0.6 | C5 | — |
| 0.8 | Docker multi-stage + image 签名（SBOM）| 0.5, 0.6 | Concern #14 | G1 |

**Foundation Continuation（M2-M3 sprint，与业务 Epic 并行）**：

| Story | 描述 | M | Pattern | 关联 Gap |
|---|---|:---:|---|---|
| **M2.1** | Outbox Relayer Sidecar 集成（per service 部署）| M2 | P56 | — |
| **M2.2** | Billing 双写一致性测试 | M2 | P33 + D15 | — |
| **M2.3** | Cost-attribution middleware（shared-py/cost_telemetry）| M2-M3 | — | **G3** |
| **M3.1** | Sandbox I/O Pattern 实现（+ P62 self-loop prevention）| M3 | P58 + **P62** | G12 部分 |
| **M3.2** | Contract Test 框架（Schemathesis）| M3 | P61 | — |
| **M3.3a** | K8s Namespace 三域 + NetworkPolicy（**标准档**）| M3 | P60 | — |
| **M3.3b** | docker-compose 蓝绿 deploy script（**精简档**）| M3 | C19 | — |
| **M3.4** | AIGC 水印 module + 双测试集 | M3 | P34 + P62 | **G12** |
| **M3.5a** | Critic 置信度校准工具 + 标注 SOP 文档 | M3 | — | **G9** |
| **M3.5b** | **(Epic) Critic ground truth 持续标注**（每周 ~20 样本）| M0-M3 持续 | — | **G9** |

#### 业务 Epic 1-8 映射

| Epic | FR 区间 | M 起 |
|---|---|:---:|
| Epic 1 Account & Identity | A1-A10 | M1 |
| Epic 2 Algorithm Catalog | C1-C8 | M1-M3 |
| Epic 3 Execution | E1-E10 | M1-M5 |
| Epic 4 Chat & NL | N1-N12 | M3 |
| Epic 5 Billing | B1-B13 | M2-M5 |
| Epic 6 Reproducibility | R1-R7 | M5-v2 |
| Epic 7 Provider | P1-P8 | v2 |
| Epic 8 Observability & Compliance | O1-O11 | M3-M5 |

---

### 📊 最终验证结果汇总

| 维度 | 评分 |
|---|:---:|
| Coherence | ✅ 100% |
| FR Coverage | ✅ 77/77 |
| NFR Coverage | ✅ 11/11 |
| Innovation 兑现 | ✅ 7/7 |
| Hard Rule 工程支持 | ✅ 3/3（3 非工程）|
| Risk 缓解 | ✅ 10/10（1 非工程）|
| Concerns 实现位置 | ✅ 19/19 |
| Patterns 完整性 | ✅ **64 项** |
| Constraints 完整性 | ✅ **20 项** |
| **Critical Gaps** | 🔴 **3**（G3 / G6 / G7）|
| Important Gaps | 🟠 9（G1/G2/G4/G5/G8-G13）|
| Nice-to-have Gaps | 🟡 7（N1-N5 + G14-G15）|
| 累积修订次数 | 113 处（6 轮 party_mode）|
| **总体就绪度** | ✅ **READY FOR IMPLEMENTATION（HIGH-conditional）** |

> ⚠️ **Conditional 含义**：3 Critical Gaps（G3/G6/G7）必须在 M3 末前解决；不达成 → M5 商用 hard-gate 阻断。

---

### Patterns 累积总览（64 项）

| 类别 | Pattern # | 数量 |
|---|---|:---:|
| Naming | P1-P14 | 14 |
| Structure | P15-P19 | 5 |
| Format | P20-P23 | 4 |
| Communication | P24-P28 | 5 |
| Process | P29-P32 | 4 |
| Critical Cross-Service | P33-P35 | 3 |
| DB & Schema 补强 | P36-P39, P45 | 5 |
| S2S & Auth | P40, P46-P48 | 4 |
| Frontend UX | P50-P52 | 3 |
| Process 补强 | P42-P44, P49 | 4 |
| Governance | P53-P55 | 3 |
| Server/Client 划界 | P41 | 1 |
| Step 6 新增 | P56-P61 | 6 |
| **Step 7 新增** | **P62-P64** | **3** |
| **合计** | **P1-P64** | **64** |

> 🆕 **UX workflow Step 6 进一步新增 3 patterns（P72-P74）**——UI Component Single-Source Discipline / Status Text i18n Single-Source / Cross-Service Storybook Visual Regression。本文档主体仍记为 64 patterns（Step 7 时点）；UX 期间新增的 P65-P74 在 Post-Validation Updates 章节累积。本架构文档 v2.1 内含 70 patterns（含 P65-P70 来自 7-Role Review）+ 4 UX patterns（P72-P74 + 此处指向） = **73 patterns 实质累积**。

### Constraints 累积总览（20 项）

| # | Constraint |
|---|---|
| C1-C7 | Step 2-3 决策（v1 自研 / mock / Audit / Revenue / CI / Python / 精简档）|
| C8-C15 | Step 4 决策细节（替代表 / TDE / JWT / Filter / Outbox / shadcn / License / GPU）|
| C16 | Step 5 AIGC Filter 段批量 |
| C17 | Step 6 capability-registry 形态 |
| C18 | Step 6 精简档 5 services（修订含 chat-with-critic inline）|
| **C19** | Step 7 精简档 deployment = docker-compose 蓝绿 |
| **C20** | Step 7 rolling deploy maxUnavailable=1 + minReadySeconds=15 + sidecar 前置 |

---

---

## 🎉 Architecture Workflow Complete

**Date**：2026-05-17
**Author**：课题组 + Claude（OptiCloud Architecture Workflow）
**Status**：✅ **COMPLETE**

### 📊 工作流总览

| 阶段 | 内容 | 产出 |
|---|---|---|
| Step 1 Init | 输入文档发现 + 仓建立 | 8 份输入文档锚定 |
| Step 2 Context | 项目上下文分析 | 19 Cross-Cutting Concerns + 4 Constraints + 3 Open Questions |
| Step 3 Starter | Monorepo 决策 | Option B-Lite（pnpm + uv + 渐进 Turbo + 极简工具链）|
| Step 4 Decisions | 23 核心技术决策 + 3 Open Q 解决 | D1-D23 全 stack + Q1-Q3 |
| Step 5 Patterns | 实现模式 / 一致性规则 | 55 patterns（P1-P55）|
| Step 6 Structure | Service 拓扑 + 监修目录树 + 边界 | 10 deployable services + 完整 monorepo tree + 19 Concern → Location |
| Step 7 Validation | 一致性 + 覆盖 + 就绪验证 | 77 FR / 11 NFR / 7 Innovation 全覆盖 + 3 Critical Gaps 显式 |
| Step 8 Complete | Handoff | 本节 |

### 📐 最终架构指标

| 维度 | 数值 |
|---|:---:|
| 总章节 | 8 章（含本节）|
| Patterns | **64 项** |
| Constraints | **20 项** |
| Services（v1 末）| **10 deployable**（精简档 5）|
| Cross-Cutting Concerns | 19 项（全归属）|
| 累积修订 | **113 处**（6 轮 party_mode）|
| 待解决 Critical Gaps | 3（G3/G6/G7，M3 末前必决）|
| 待解决 Important Gaps | 9（G1/G2/G4/G5/G8-G13）|
| 待解决 Nice-to-have | 7（N1-N5/G14/G15）|
| 输入文档 | 8 份 |
| 总行数 | ~3000+ |

### 🏆 Key Achievements

- **PRD → Architecture 完整闭环**：77 FR Capability Contract → 10 service ownership 全映射
- **7 项 Innovation 全部架构兑现**（Critic / Repro 5y / 学界变现 / 模板可插拔 / Credits 跨层 / Apache 2.0 / 三合一）
- **AIGC 合规深度设计**（双层 filter + 自循环防护 P62 + 双测试集 + 出口屏障 + 水印实施 G12）
- **精简档 / 标准档双 fallback 体系**（C7 + C8 + C18 + C19 + chat-with-critic inline）
- **Repro 5y SLA 完整工程化**（repro-service + Image 分层归档 G7 + capability auto-migration + 30d 预通知）
- **多 Agent NL Pipeline 完整设计**（chat + critic + sandbox-runner + P57 延迟预算 + P58 I/O Pattern）
- **Cloud Lock-in 风险显式缓解**（R11 + P60 namespace + Terraform module + shared-py/otel_setup + AWS backup）
- **4-Tier Critical Service Resilience**（Redis SWR → S3 snapshot → PG replica → 本地 emptyDir）
- **Event Versioning 演进兼容性策略**（P63 dual publish + N=3 月）
- **OpenAPI 单源 + Drift Check**（P64 自动同步 + CI gate）

### 📁 关键文件清单

```
D:\优化预测网站\_bmad-output\planning\
├── prd.md                                              ✅ PRD COMPLETE
├── architecture.md                                     ✅ 本文档 COMPLETE
├── implementation-readiness-report-2026-05-17.md       ✅ Readiness 92.5%
└── SESSION-HANDOVER.md                                 ✅ Session 入口（旧版）
```

### 🚦 Next Steps（用户实际行动）

#### Path 1：继续 BMad 工作流（推荐顺序）

1. **`/bmad-create-ux-design`** — 创建 UX 设计规格
   - 与本架构对接（Console / Docs / Chat 等已固化技术栈）
   - 输入：本架构 + PRD + Journey 1-11
   - 输出：`ux-design.md`
2. **`/bmad-create-epics-and-stories`** — 把 77 FR + Epic 0 Foundation 拆为 Stories
   - 输入：PRD + 本架构 + Epic 0 Foundation Story 0.1-0.16 + 业务 Epic 1-8 映射
   - 输出：Epic 列表 + Story backlog
3. **`/bmad-check-implementation-readiness`** — 完整 traceability 复检
   - 输入：4 份文档齐套
   - 输出：升级版 Readiness Report
4. **`/bmad-create-story` + `/bmad-dev-story`** — 进入开发循环
   - 推荐先开 Epic 0 Foundation（Sprint 0，2-4 周）

#### Path 2：M0 同步推进（与 BMad 平行）

1. 🔴 **公司主体注册启动**（M0 wk1）
2. 🔴 **AIGC 备案中介签约**（M0 wk1）
3. 🟠 **课题组算法 Apache 2.0 签发**（M0 wk2）
4. 🟡 **第二个行业模板选定**（建议物流）

> 用户已声明 M0 进度由用户负责，不操心。

#### Path 3：精简档单人快速路径（如团队 1-2 人）

- 直接进 `/bmad-agent-quick-flow-solo-dev`（召唤 Barry）
- 用 C7 + C8 + C18 + C19 精简档替代决策表
- 走 5 services + docker-compose 蓝绿
- 跳过 UX 文档（用 packages/ui 默认 + shadcn/ui CLI 生成）

### ⚠️ M3 末 Hard-Gate 提醒

**3 项 Critical Gaps（G3/G6/G7）必须 M3 末前解决**：

| Gap | 验证 |
|---|---|
| **G3** Per-tenant 成本监控 | `shared-py/cost_telemetry` 上线 + Grafana dashboard live + 月度 alert 配置完成 |
| **G6** Chat 延迟预算 | Staging k6 全栈压测达标：首 Token P95 < 3s / 流式 ≥ 20 Token/s / E2E ≤ 90s；不达需架构层调整（critic 异步化 / aigc Layer 2 离线化）|
| **G7** Image 分层归档 | 热 ACR EE 90d + 温 S3 Standard-IA 1y + 冷 S3 Glacier 5y 三层就位 + 自动迁移规则 |

**未达成则 M5 商用 hard-gate 阻断**。

### 🤝 实施 Handoff Contract

凡参与 OptiCloud 实施的 AI agent / 人类开发者必须签订此 contract：

> "我已阅读并理解本架构文档（`_bmad-output/planning/architecture.md`）；
> 在实施过程中遵守全部 **64 Patterns + 20 Constraints + Boundary Rules**；
> 任何偏离须经 **P53 ADR** 审批；
> 新 service 必通过 **P55 CLI** 生成；
> 所有 NL 输出经 **P34 AIGC Filter（含 P62 防自循环）**；
> 所有跨服务状态变化经 **P33 Outbox + P48 Trace Context + P56 sidecar Relayer**；
> Service-to-Service 必用 **P40 Service Account JWT + user chain-of-trust**；
> 事件 schema 演进必遵 **P63 dual publish + N=3 月**。"

### 💬 致谢

本架构由课题组与 Claude 协作，经历 **6 轮 Party Mode + 20+ BMad agent 视角参与 + 113 处累积修订** 强化。

每一项 Pattern / Constraint / Gap 都来自实战考量 —— 不是纸上谈兵，而是为 5 人团队 / 12 月跑道 / ¥248 万预算 / M5 ¥4 万营收 hard-gate 量身设计。

接下来交给开发循环：**`/bmad-create-ux-design` → `/bmad-create-epics-and-stories` → `/bmad-create-story` → `/bmad-dev-story`** 逐渐落地。

---

---

## 📦 Appendix A — Deployment Sizing & Day-1 Setup

> 本附录把 Step 4 + Step 6 + PRD §22 综合反算为可执行的硬件 sizing + 月度成本 + Day-1 启动清单。**所有数字 = 基于已固化的 service 拓扑（10/5 deployable）+ Sandbox 资源约束 + Postgres 4C8G 推荐（PRD §1605）+ 阿里云 2026-05 现价反算**。

### A.1 Service 资源分配（per service baseline）

| Service | vCPU | RAM | 备注 |
|---|:---:|:---:|---|
| web（Next.js 15）| 2 | 2 GB | SSR + Server Component；负载高时水平扩 |
| api-gateway | 2 | 2 GB | 含 auth middleware + data-export Dramatiq actor + audit query；精简档含 billing + auth 全合并 |
| auth-service | 1 | 1 GB | Argon2 密码 hash 偶尔高峰 |
| solver-orchestrator | 2 | 2 GB | 求解任务调度；CPU 密集型实际跑在 worker pod / RunPod GPU |
| billing-service | 1 | 1 GB | I/O 密集；double-write ledger |
| chat-service | 2 | 2 GB | SSE 长连接；多并发 chat |
| critic-service | 2 | 2 GB | Critic 推理 + 红队跑批 |
| sandbox-runner | 2 + 预热 | 2 GB + 预热 | 主进程 1+1；warm pool 每 container 1 vCPU / 1 GB |
| capability-registry | 1 | 512 MB | 极简版（M3 起）；M5+ 加状态机后升 1.5 vCPU / 1 GB |
| repro-service | 1 | 1 GB | I/O 密集（S3 Glacier 操作）；M5 起 |

> 上述 = pod request；K8s limits 一般设 request × 2。

### A.2 Infra Components（共享，自托管或托管）

| 组件 | 形态 | vCPU | RAM | 存储 |
|---|---|:---:|:---:|:---:|
| **Postgres 15+ with pgvector + pg_tde** | 阿里云 RDS（推荐）/ 自托管 | 4 | 8 GB | 100 GB SSD（v1 末）→ 500 GB（v2 末）|
| **PgBouncer 1.22+** | 自托管 sidecar 或独立 pod | 0.5 | 256 MB | — |
| **Redis 7+** | 阿里云 Redis 或自托管 | 1 | 2 GB | — |
| **Vault** | self-hosted standalone（v1）/ HA cluster（v2+）| 1 | 1 GB | 10 GB |
| **GrowthBook** | self-hosted | 0.5 | 512 MB | — |
| **OSS / S3 / S3 Glacier** | 阿里云 OSS + AWS S3 备份 | — | — | 50 GB 起（含 image archive）|
| **SLB / 公网 IP** | 阿里云 SLB | 1 | 512 MB | — |
| **Grafana + Prometheus + Loki + Tempo** | self-hosted（标准档）/ Grafana Cloud free tier（精简档）| 2 | 4 GB | 100 GB（日志 30d）|

### A.3 总硬件需求（按 milestone 演进）

#### 精简档（C7 + C18 + C19）

| 阶段 | Services Running | 总 vCPU | 总 RAM | 总存储 | 推荐云配置 |
|---|---|:---:|:---:|:---:|---|
| **M1-M2 起步** | web + api-gateway + solver | **6** | **6 GB** | 100 GB | **1 台 ECS 8C16G + RDS 4C8G + Redis 2 GB** |
| **M3 起（含 Chat + Sandbox）** | + chat-with-critic + sandbox-runner | **10** | **10 GB** | 100 GB | **2 台 ECS 8C16G + RDS 4C8G + Redis 2 GB** |
| **M5 商用准入** | 全 5 services + 监控 | **14** | **14 GB** | 200 GB | **2 台 ECS 8C16G + RDS 4C8G + Redis 4 GB + 1 台 ECS 4C8G 监控** |

#### 标准档（5 人全职 / ¥248 万）

| 阶段 | Services Running | 总 vCPU | 总 RAM | 推荐云配置 |
|---|---|:---:|:---:|---|
| **M1-M2** | web + api-gateway + auth + solver | **8** | **8 GB** | **ACK 3 节点（4C8G）+ RDS 4C8G HA + Redis 4 GB** |
| **M3 起** | + billing + chat + critic + sandbox + capability | **18** | **18 GB** | **ACK 4-6 节点（4C8G/8C16G mix）+ RDS HA + Redis HA** |
| **M5 商用** | + repro + monitoring 完整 | **24** | **24 GB** | **ACK 6-8 节点 + RDS 8C16G HA + Redis HA + 监控 cluster** |

### A.4 月度云成本估算（阿里云华北/华东，2026-05 现价）

#### 精简档稳态（M5 商用后）

| 项 | 规格 | 月费（¥）|
|---|---|---:|
| ECS（包年优惠）| 8C16G × 2 + 4C8G × 1（监控）| ¥1,200-2,000 |
| RDS Postgres | 4C8G HA | ¥800-1,200 |
| Redis | 4 GB 实例 | ¥200-400 |
| OSS + S3 Glacier 跨区 | 200 GB + 流量 + 归档 | ¥100-200 |
| SLB + 公网 IP | 标准 + 5-10 Mbps | ¥200-400 |
| CDN | 1-2 TB 流量 | ¥150-300 |
| 域名 + SSL（续费）| .cn + 通配证 | ¥50-100 |
| **基础设施小计** | — | **¥2,700-4,600/月** |
| DeepSeek API | M3+ 实际负载 | ¥1,000-5,000 |
| Qwen-Max（incident）| 偶尔触发 | ¥0-500 |
| 短信验证（双因素）| ¥0.04/条 × ~5K | ¥200 |
| Resend / Mailgun | 通知邮件 | ¥30-100 |
| **总月费（稳态）** | — | **¥3,900-10,400/月** |

> 12 月预算 ¥114 万 / 12 = ¥9.5 万/月，**云费占 4-11%**。

#### 标准档稳态

| 项 | 规格 | 月费（¥）|
|---|---|---:|
| ACK 托管版 | 6-8 节点 + 控制面 | ¥4,000-6,000 |
| RDS Postgres HA | 8C16G | ¥2,000-3,000 |
| Redis HA | 8 GB Sentinel | ¥500-800 |
| OSS + S3 Glacier | 500 GB + 流量 | ¥300-500 |
| SLB + 公网 | 高带宽 | ¥500-800 |
| CDN | 5 TB+ 流量 | ¥500-1,000 |
| ACR EE | 镜像签名 + SBOM | ¥500-800 |
| **基础设施小计** | — | **¥8,300-12,900/月** |
| DeepSeek API | M5 商用规模 | ¥3,000-10,000 |
| Qwen-Max | 应急 + 部分负载 | ¥500-2,000 |
| 短信 + 邮件 | 用户规模 | ¥500-1,000 |
| **总月费（稳态）** | — | **¥12,300-25,900/月** |

> 12 月预算 ¥248 万 / 12 = ¥20.7 万/月，**云费占 6-12%**。

### A.5 一次性 / 启动成本

| 项 | 范围 | 何时 |
|---|---|:---:|
| **AIGC 备案中介费** | ¥3-8 万 | M0 wk1（**必出，精简档不可砍**）|
| **公司主体注册** | ¥1-5 万 | M0 wk1 |
| **ICP 备案 + 公安备案** | ¥0-1 千（多免费）| M1 末 |
| **等保 2.0 二级测评** | ¥3-10 万 | M5 末（精简档可推迟 v1.5）|
| **等保 2.0 三级**（v2+）| ¥10-30 万 | v3 末 |
| **域名注册** | ¥100-500/年 | M0 |
| **企业 SSL 通配证书** | ¥1-5 千/年 | M1 |

### A.6 外部 SaaS / API 依赖（必须）

| 依赖 | 用途 | 计费模式 | 必要性 |
|---|---|---|:---:|
| **DeepSeek API** | LLM 主路径 | 按 token | ✅ 必须 |
| **Qwen-Max API** | LLM incident fallback | 按 token | ✅ 必须（M3 起）|
| **微信支付** | 国内支付 | 0.6% 费率 | ✅ 必须 |
| **支付宝** | 国内支付 | 0.6% 费率 | ✅ 必须 |
| **Stripe** | 海外支付 | 2.9% + $0.30 | 🟡 v2 启用 |
| **Resend / Mailgun** | 事务邮件 | 免费层 → ¥30+ | ✅ 必须 |
| **短信网关** | 双因素验证 | ¥0.04/条 | ✅ 必须 |
| **阿里云 ICP 备案 + 公安备案** | 合规 | 一次性免费 | ✅ 必须 |
| **AIGC 备案中介** | M0 启动 | ¥3-8 万 | ✅ 必须 |
| **RunPod / AutoDL** | GPU 按秒（v1）| 按 GPU 秒 | ✅ M2+（C15）|
| **GitHub** | 代码仓库 + CI | Team ¥40/seat/月 | ✅ 必须 |

### A.7 软件栈完整 Version Catalog（2026-05 验证）

#### Runtime

| 工具 | Version | 来源 |
|---|---|---|
| **Linux**（OS）| Ubuntu 22.04 LTS / 阿里云 Linux 3 | 推荐 |
| **Docker**（容器）| 27+ | 必须 |
| **Docker Compose** | v2+ | 必须 |
| **gVisor (runsc)** | latest stable | 沙箱必须 |
| **Python** | **3.12**（C6 锁定）| 必须 |
| **Node.js** | 20 LTS | 必须 |
| **uv**（Python pkg）| 0.4+ | 替代 Poetry |
| **pnpm**（Node pkg）| 9+ | monorepo |

#### Backend Stack

| 库 | Version |
|---|---|
| FastAPI | **0.136.1** |
| Pydantic | **v2** |
| SQLAlchemy | **2.0** async |
| Alembic | 1.13+ |
| asyncpg | 0.30+ |
| Uvicorn[standard] | latest |
| Gunicorn | latest |
| structlog | 24+ |
| OpenTelemetry API | 1.27+ |
| httpx | 0.27+ |
| Dramatiq | 1.17+ |
| dramatiq-crontab | latest |
| pyjwt（含 EdDSA）| 2.10+ |
| pytest + pytest-asyncio | latest |
| factory_boy | 3.3+ |
| Schemathesis | latest |
| ruff | latest |
| mypy | latest |
| bandit | latest |

#### Frontend Stack

| 库 | Version |
|---|---|
| **Next.js** | **15.x** |
| TypeScript | 5+ |
| Tailwind CSS | **v3**（v4 待评测）|
| **Turbopack** | Next 15 内建 |
| **TanStack Query** | 5+ |
| **Zustand** | 5+ |
| React Hook Form | 7+ |
| Zod | 3+ |
| Apache ECharts | 5.5+ |
| TanStack Table | 8+ |
| TanStack Virtual | 3+ |
| Radix UI | 1+ |
| shadcn/ui CLI | latest |
| next-intl | latest |
| Vitest | latest |
| Playwright | latest |
| ESLint + Prettier | latest |

#### Infrastructure

| 工具 | Version |
|---|---|
| **PostgreSQL** | 15+（with pgvector + pg_tde）|
| pgvector | 0.7+ |
| pg_tde | 1.0+ |
| **PgBouncer** | 1.22+ |
| **Redis** | 7+ |
| **HashiCorp Vault** | 1.18+ |
| **GrowthBook** | 自托管 latest |

#### Solvers & TS Models（pip install 按需）

| 库 | License | Version |
|---|---|---|
| HiGHS | MIT | 1.7+ |
| OR-Tools | Apache | 9.10+ |
| CVXPY | Apache | 1.5+ |
| SCS | MIT | 3.2+ |
| IPOPT | EPL（仅调用）| 3.14+ |
| Bonmin | EPL | 1.8+ |
| Couenne | EPL | 0.5+ |
| Pyomo | BSD | 6.7+ |
| PuLP | MIT | 2.8+ |
| Chronos | Apache | 1.0+ |
| TimesFM | Apache | latest |
| Lag-Llama | Apache | latest |
| Moirai | Apache | latest |
| Nixtla statsforecast | Apache | latest |
| scikit-learn | BSD | 1.5+ |
| XGBoost | Apache | 2.1+ |
| LightGBM | MIT | 4.5+ |
| PyTorch | BSD | 2.5+ |
| Prophet | MIT | 1.1+ |

#### Cloud / Infra

| 工具 | Version |
|---|---|
| 阿里云 ACK（K8s）| 1.30+ |
| ArgoCD（ACK One 内置）| 2.13+ |
| Argo Rollouts | 1.7+ |
| Terraform | 1.9+ |
| Terraform 阿里云 provider | latest |
| ACR EE（Image Registry）| latest |
| Grafana | 11+ |
| Prometheus | 2.55+ |
| Loki | 3.2+ |
| Tempo | 2.6+ |

#### Tools

| 工具 | Version |
|---|---|
| pre-commit | 4+ |
| pip-licenses | latest |
| license-checker-rseidelsohn | latest |
| dorny/paths-filter | v3 |
| cosign（image 签名）| 2.4+ |
| Notation | 1.2+ |

### A.8 网络要求

| 项 | 精简档 | 标准档 |
|---|---|---|
| 公网带宽 | 5-10 Mbps | 50-100 Mbps |
| 内网带宽 | 千兆 | 万兆 |
| 域名 | `api.opticloud.cn` + `console.opticloud.cn` + `status.opticloud.cn` + 主站 | 同 + `docs.opticloud.cn` + `cdn.opticloud.cn` |
| SSL 证书 | Let's Encrypt 免费 / 阿里云 SSL | 阿里云 EV 通配证书 |
| CDN | 阿里云 CDN | 阿里云 CDN + Cloudflare 双备 |
| ICP 备案 | M1 末必须 | 同 |
| 公安备案 | M1 末必须 | 同 |
| AIGC 备案 | M3 末 hard-gate | 同 |
| 数据出境评估 | 触发时（用户主动选 N4 远程 LLM）| 同 |

### A.9 Day-1 启动清单（精简档）

```bash
# === 一次性（M0 wk1-wk2）===
✅ 公司主体注册（有限责任公司，注册资本 ≥¥100 万）
✅ AIGC 备案中介签约（¥3-8 万一次性）
✅ 阿里云账号 + 实名 + 备案 entity 绑定
✅ 申请 ICP 备案（提交 M0；M1 末完成）
✅ 申请公安备案（网监 30 日内）
✅ 域名 opticloud.cn 注册（¥100/年）
✅ 申请 SSL 通配证书（Let's Encrypt 免费或阿里云 ¥1-5K/年）
✅ DeepSeek API 申请 + ¥1K 充值
✅ Qwen-Max API 申请 + ¥500 充值（应急用）
✅ 微信商户号 + 支付宝商家申请
✅ Resend / Mailgun 账号 + 域名验证
✅ GitHub 私有仓库 + Team 套餐
✅ 课题组成员邮箱 + GitHub 邀请

# === 硬件资源（M0 wk2 - M1 wk1）===
✅ 阿里云 ECS 8C16G × 1（华北/华东，月付优惠）
✅ 阿里云 RDS Postgres 4C8G（带 SSD + 跨区备份）
✅ 阿里云 Redis 2GB 实例
✅ 阿里云 OSS bucket（dev + prod 分桶）
✅ 阿里云 SLB（标准型，绑公网 IP）

# === 软件初始化（M1 wk1-wk2）===
✅ ECS 安装 Docker 27 + Docker Compose v2
✅ ECS 启用 gVisor（runsc runtime）
✅ Clone OpticCloud monorepo
✅ docker compose up（启 5 services 骨架）
✅ Postgres 跑 init migration（创建 schema + audit_log + outbox）
✅ Vault dev mode 启动 + 写入初始 secret
✅ GrowthBook dev 实例启动 + 创建第一个 flag
✅ Stoplight Elements 配置 docs.opticloud.cn 子域

# === 第一次部署（M1 wk2-wk3）===
✅ docker-compose 蓝绿启动 web + api-gateway + solver
✅ SLB 配置 80/443 → 容器端口
✅ Let's Encrypt SSL 申请 + Nginx 配置
✅ Hello World API 跑通（FR A1 注册 + A2 API Key）
✅ Stripe / 微信 测试支付通道
✅ 第一个 customer journey: Hello World cURL 跑通

# === 监控就位（M3 wk1）===
✅ Grafana Cloud free tier 创建实例
✅ Prometheus scrape config 配置
✅ Loki agent 部署
✅ Sentry 自托管 / 或 Sentry SaaS 试用
✅ 状态页 status.opticloud.cn（Uptime Kuma / Statuspage）
✅ 钉钉机器人 + 报警路由配置
```

### A.10 精简档 vs 标准档对比速查

| 维度 | 精简档（最小）| 标准档（推荐）|
|---|---|---|
| 团队 | 1-2 人 | 5 人全职 |
| Services 数 | **5** | **10** |
| 容器编排 | docker-compose | ACK K8s |
| GitOps | docker-compose 蓝绿 | ArgoCD + Argo Rollouts canary |
| IaC | bash + 控制台 | Terraform + ACK |
| Sandbox | gVisor on Docker | gVisor on K8s + warm pool（KEDA + HPA）|
| 监控 | Grafana Cloud free | self-hosted Prometheus + Loki + Tempo + Sentry |
| Capability Registry | shared-py 库 + 表（M3+）| 独立 service（M3+，状态机 M5+）|
| Audit | shared-py + api-gateway 端点 | v2 拆 service |
| Outbox Relayer | sidecar（per service）| sidecar（per service）|
| 月云费稳态 | **¥4-10K** | **¥12-26K** |
| 12 月预算 | **¥114 万** | **¥248 万** |
| Critic 红队 | M3 ≥30 / M5 简化 100 | M3 ≥30 / M5 ≥200 |
| 等保 2.0 二级 | 推迟 v1.5 取证 | M5 末取证 |
| WCAG | 仅 axe-core 自动扫 | 设计时 + 季度人审 |
| SLA | best-effort v1 全程 | best-effort v1 / v1.5 起 99.0-99.9% |
| AIGC 备案中介 | ¥3-8 万（必出）| ¥3-8 万（必出）|

### A.11 不可砍的最小项（与团队规模无关）

无论精简档还是 1 人开发，以下**绝不能砍**（C7 + 其他 Hard Rule 锁定）：

1. **AIGC 备案中介 ¥3-8 万**（精简档必出预算）
2. **gVisor 沙箱**（P58 / 安全 hard rule）
3. **License 白名单 CI 检查**（Hard Rule #2 / P35）
4. **shared-py/aigc_filter 双层**（P34 / C11 / C16）
5. **Postgres TDE + Vault**（C9 / PIPL 合规）
6. **OpenAPI 单源 + drift check**（P64）
7. **每月计费对账**（计费可靠性 = 0 误差）
8. **24h Postmortem 流程**（Hard Rule #6）
9. **Idempotency-Key 全 POST**（P31）
10. **Multi-tenant SQLAlchemy hook 隔离**（P32）

### A.12 触发升级标准档的条件

精简档可持续到以下任一触发：

- 付费用户 ≥ 50（M5 商用准入）
- 月营收 ≥ ¥4 万
- Critical Gaps G3/G6/G7 工程化需求超 1-2 人容量
- 团队招到 ≥3 人全职
- 启动 v1.5 SLA 对外承诺
- 接入 ≥1 个外部 Provider（v2 启动 P1-P8）

触发后渐进迁移：
1. **Step 1**：docker-compose → ACK 单节点（保留 docker-compose 作为本地开发）
2. **Step 2**：单 service 拆分（auth / billing 从 api-gateway 拆出）
3. **Step 3**：Audit / Revenue-Share / Data-Export Service 独立化
4. **Step 4**：bash + 控制台 → Terraform 接管所有 infra
5. **Step 5**：监控自托管化（Prometheus + Loki + Tempo + Sentry）

---

---

## 🔍 Post-Validation 7-Role Review Update (2026-05-17)

> 7 角色独立审查（系统架构师 / AI 分析师 / 网站管理员 / 大学研究生 / 潜在行业用户 / 大学教师 / 法律顾问）加权评分 **74.7/100**。
>
> 本节固化跨视角共识：**6 Patterns + 1 Constraint + 4 Important Gaps + 5 Appendix 引用**。

### 评分概要

| 视角 | 评分 | 主要风险 |
|---|:---:|---|
| 🏗️ 系统架构师 | 87/100 | Service Mesh / SLO / Backpressure 缺 |
| 🤖 AI 分析师 | 75/100 | Prompt Management / Caching / Drift 盲点 |
| ⚖️ 法律顾问 | 72/100 | EULA/ToS/隐私/合作合同模板缺；EPL/ECOS 法务风险 |
| 🖥️ 网站管理员 | 78/100 | Runbook / On-call / 告警阈值 / 容灾演练 SOP 缺 |
| 🎓 大学教师 | 70/100 | Provider Onboarding 学者门槛 / Lifecycle / LMS 集成 |
| 🎒 大学研究生 | 73/100 | .edu 失效 / Colab 国内 / Repro 5y 学位太短 |
| 💼 行业用户 | 68/100 | 企业 GTM 工具缺 / SLA 不对外 / 集成 connector 缺 |
| **加权平均** | **74.7/100** | — |

> 详细 Findings 见 **Appendix F（7-Role Review Detailed Findings）**

---

### New Patterns（P65-P70）— 从 7-Role Review 提炼为架构 Pattern

#### P65 — Service Mesh Evolution Path（系统架构师 SA1 + SA3）

| 阶段 | mTLS | Service Discovery | Mesh Layer |
|---|:---:|---|---|
| **v1**（M1-M5）| ❌ off（C20）| K8s DNS（`<service>.<namespace>.svc.cluster.local`）| 无；Service Account JWT 单防线（P40）|
| **v1.5**（M7+）| ✅ on | K8s DNS + Service Account JWT | **Envoy sidecar mTLS**（per-pod sidecar，渐进启用）|
| **v2**（M9+）| ✅ on | mesh-aware discovery | **Full Istio / Linkerd**（traffic management + observability + canary）|

**触发 v1.5 升级**：付费 ≥200 / 月营收 ≥¥18 万 OR 内部 service ≥ 8。

**触发 v2 升级**：多 region 启用 OR 团队 ≥10 人 OR 合规要求 zero-trust 内网。

#### P66 — SLO + Error Budget Policy

每个 service 定义 monthly SLO + Error Budget 政策：

```yaml
service: api-gateway
slo:
  availability: 99.5%        # error budget = 0.5% × 30day = 216 min
  latency_p95: 200ms
error_budget_policy:
  remaining > 50%: normal     # release 不受限
  remaining 25-50%: warning   # 加强 PR 审；feature 灰度更慢
  remaining < 25%: freeze     # 仅 bug fix / 安全补丁；feature freeze
  burned > 100%: postmortem   # P53 ADR + retrospective
```

**Burn rate alerts**（Google SRE 标准 multi-window multi-burn-rate）：
- 1h burn rate ≥ 14.4 → 1% budget/h 消耗 → page oncall
- 6h burn rate ≥ 6 → 0.4% budget/h → ticket
- 24h burn rate ≥ 1 → trend alert

每月 SLO review + ADR 调整。

#### P67 — Backpressure Pattern

三态决策树（**每个入口 service 必实现**）：

```
incoming request
    │
    ↓
[1] rate limit check (P9 Redis sliding window)
    │
    ├─ over limit → 429 + Retry-After + X-RateLimit-*（O6 配套）
    │
    ↓
[2] queue depth check
    │
    ├─ Dramatiq queue depth > N（per-service threshold）→ 503 Service Unavailable + Retry-After
    │
    ↓
[3] latency baseline check
    │
    ├─ P95 latency > 2× baseline → 转 async（202 Accepted + Location）
    │
    ↓
[4] downstream circuit breaker（D13 httpx + tenacity）
    │
    └─ open circuit → 502 Bad Gateway + fallback to P59 4-tier
```

**Per-service Backpressure Threshold（建议初始值）**：

| Service | Rate Limit | Queue Depth Cap | Latency Trigger |
|---|:---:|:---:|:---:|
| api-gateway | 500 RPS | — | P95 > 400ms |
| auth-service | 100 RPS | — | P95 > 100ms |
| solver-orchestrator | 30 RPS | 100 | P95 > 5s（异步转换）|
| chat-service | 50 concurrent SSE | — | first token P95 > 5s（降级 critic）|
| billing-service | 200 RPS | 50（outbox + dramatiq）| P95 > 500ms |

#### P68 — Prompt Management as First-Class Citizen（AI 分析师 AI1）

**Prompt 是产品组件，非代码文字**——必须独立 store + 版本化。

**Prompt Store 时间线**（修订 C17 一致）：

- **M1-M2**：4-Agent prompts 暂入 `apps/chat-service/prompts/`（service 内代码常量，可硬编码灰度变量）—— 因 Chat M3 才上线，M1-M2 prompts 仅准备阶段
- **M3 起**：prompts 入 `apps/chat-service/prompts/` + 配合 GrowthBook flag（基础 A/B test）
- **M5+**：**`capability-registry` 加入 prompt-store sub-module**（与状态机一起上线）—— 集中管理 prompts + 版本化 + A/B 灰度
- **v1.5 评估**：根据 prompt 变更频率决定是否拆 prompt-store 为独立 service

**`capability-registry` 的 `prompt-store` sub-module schema**（M5+ 启用）：

```sql
CREATE TABLE prompts (
    id UUID PRIMARY KEY DEFAULT uuidv7(),
    scope TEXT NOT NULL,         -- 'router' / 'formulator' / 'planner' / 'coder' / 'critic' / 'nl_summary' / 'aigc_filter'
    version INT NOT NULL,        -- monotonic per scope
    content TEXT NOT NULL,
    few_shot_examples JSONB,
    expected_inputs JSONB,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT NOT NULL,
    activated_at TIMESTAMPTZ,
    deprecated_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX uq_prompts_scope_version ON prompts (scope, version);
```

**A/B Test 框架**：GrowthBook flag `prompt_critic_v3_rollout` 控制 5%→50%→100% 灰度。

**Rollback**：deprecate current → 重 activate 旧 version + 30 min 内生效（cache invalidation）。

**Change Process**：
- Prompt 变更 = P53 ADR 必须
- 红队 + 良性测试集（P34 双套）必须通过
- Critic 置信度回归测试（与 G9 标注的 ground truth 对照）

#### P69 — LLM Output Caching

**Cache Key**：
```python
cache_key = f"llm_cache:{tenant_id}:{scope}:{sha256(canonical_prompt + few_shots + temperature_seed)}"
```

**Policy**：
- TTL 1 hour（语义等价性 1 小时内可接受）
- Bypass：query param `?no_cache=true`（强一致性场景）
- Per-tenant 隔离（不跨租户）
- 不缓存：creative tasks（temperature > 0.5）、user-personalized（含用户私有数据）

**Cost 节约效果预估**：~30-50% 重复 prompt 命中 cache → DeepSeek API 月成本下降 30-50%。

**Cache Warming**：常用 prompt（Hello World 三件套示例）首次部署时预热。

#### P70 — Prompt Injection Defense（输入侧加固）

P34 AIGC Filter 主管输出；P70 管输入。**四层防护**：

| Layer | 机制 | 实施 |
|---|---|---|
| L1 | **System Prompt 隔离** | 用户输入永远不进 system role；用 `{user_input}` placeholder 严格隔离 |
| L2 | **Role Tagging** | Prompt 内显式 `<|user|>...<|/user|>` 标签；LLM 训练时识别越界尝试 |
| L3 | **Pre-LLM Input Filter** | 正则黑名单 + 关键词（"ignore previous", "system:", "you are now", "</s>", "\n\n# system", "DAN" 等）|
| L4 | **Honeypot + 审计** | 嵌入 honeypot string（"INTERNAL_TOKEN_DO_NOT_REVEAL"）→ 检测试探；命中 → 写 audit_log + Critic 高优先 review |

**Critic 角色升级**：除了置信度检测，**新增**"prompt injection 检测"维度（M5 起）。

---

### New Constraint（C21）— EPL + ECOS 法务签字 Hard Rule（法律顾问 L6+L7）

| # | Constraint |
|---|---|
| **C21** | **M0 wk1-2 必须法务正式签字确认 EPL（IPOPT/Bonmin/Couenne）SaaS 后端使用合规 + ECOS GPLv3 v1 使用决策**；签字结论入 `docs/adr/0003-epl-ecos-license-decision.md`；**未签字 contingency plan**：① IPOPT/Bonmin/Couenne 禁用 → 非线性 SKU 用 **CVXPY + SCS（MIT）**替代（功能损失：MINLP 全局解; 接受 local solver via IPOPT 替代损失）② ECOS 禁用 → 凸 SOCP 仅用 SCS（无功能损失）③ 任何 EPL/ECOS 在生产代码 import 必经 CI license-check 二次拦截；v1 SKU 列表中 `opt.nlp.*` 标 ⚠️ 待签字 |

---

### New Important Gaps（G16-G19）

| # | Gap | 优先级 | 截止 | 来源 |
|---|---|:---:|:---:|---|
| **G16** | **法律合同模板缺**（EULA / ToS / Privacy Policy / DPA / 学界合作 / NL Summary 免责）→ Appendix C | 🟠 | EULA/ToS/Privacy M1 末；合作 M5 前；NL免责 M5 前 | L1+L2+L3+L5+L11+IU7 |
| **G17** | **EPL + ECOS 法务签字未确认**（C21 触发）→ M0 ADR | 🔴 escalated | **M0 wk1-2 必须** | L6+L7 |
| **G18** | **Backup Restoration Runbook + On-Call Rotation Policy + 告警阈值 + 容灾演练 SOP**（精简档 + 标准档双份）→ Appendix D | 🟠 | M3 末 | OP1+OP2+OP3+OP5 |
| **G19** | **企业采购 GTM Toolkit**（SOC 2 启动 / SOW 模板 / Gurobi 迁移 wizard / industry connector POC）→ Appendix E | 🟠 | M5 商用前 | IU1+IU2+IU3+IU4+IU5 |

> G17 升为 **Critical**（M0 时间窗硬约束）；其他 3 项 Important。

---

### New Appendix References

| Appendix | 文件 | 用途 |
|---|---|---|
| **B** | （本节）— Post-Validation Patterns P65-P70 | — |
| **C** | `docs/legal-templates.md` | EULA / ToS / Privacy / DPA / 合作合同模板清单（含 G16）|
| **D** | `docs/runbooks/README.md` | Day-2 Operations Runbooks（含 G18）|
| **E** | `docs/enterprise-gtm-toolkit.md` | 企业销售工具包（含 G19）|
| **F** | （本文档末）— 7-Role Review Detailed Findings | 详细审查纪录 |

> Academic Provider Handbook 暂未拆出独立文件；现有 `docs/customer-faqs/` 目录将扩展容纳（学者 onboarding / classroom plan / IP attribution / lifecycle 等内容）。后续可拆 Appendix F2 → `docs/academic-provider-handbook.md`。

---

### 累积更新

| 维度 | 修订前 | 修订后 |
|---|:---:|:---:|
| Patterns | 64 项（P1-P64）| **70 项**（P1-P70）|
| Constraints | 20 项（C1-C20）| **21 项**（C1-C21）|
| Critical Gaps | 3（G3 / G6 / G7）| **4**（+ G17 EPL/ECOS 法务签字）|
| Important Gaps | 9 | **12**（+ G16 / G18 / G19）|
| Appendix | A | **A + B + C + D + E + F**（B 本节 / C-E 引用 / F 详细 findings）|

---

## 📎 Appendix F — 7-Role Review Detailed Findings

> 完整 7-Role 评审纪录（2026-05-17）。每个视角 ✅ Strengths + ⚠️ Critical Findings + 💡 Asks + 评分。

### F.1 系统架构师视角（评分 87/100）

**✅ Strengths**：64 patterns 系统性 + 4-tier resilience + Outbox sidecar + 6 轮 party_mode 91 处修订
**⚠️ Critical**：
- **SA1** Service Mesh 缺失（mTLS off / 单防线）→ P65
- **SA2** SLO/Error Budget 未明文 → P66
- **SA3** Service Discovery 机制隐藏 → P65 含 K8s DNS 明示
- **SA4** Backpressure 缺设计 → P67
- **SA5** Capacity Planning per QPS 缺 → P67 含建议初始值
- **SA6** DB Read Replica 策略（v2 起按需）
- **SA7** Webhook Secret Rotation（v2 实施）

### F.2 AI 分析师视角（评分 75/100）

**✅ Strengths**：Critic Agent SaaS / 4-Agent NL Pipeline / AIGC Filter 双层 + P62
**⚠️ Critical**：
- **AI1** Prompt Management 不是一等公民 → P68
- **AI2** LLM Output Caching 缺失 → P69
- **AI3** Embedding Pipeline 缺设计（v1.5 起 ADR）
- **AI4** Critic 训练数据 / Active Learning 缺（G9 校准延伸）
- **AI5** Model Drift 监控缺（v2 起）
- **AI6** Per-Chat Token Budget Model（A.14 待补 v1.5）
- **AI7** Few-shot Examples Management（v1.5 起，P68 schema 已留位）
- **AI8** Prompt Injection Defense（输入侧）→ P70
- **AI9** Innovation #1 Critic 调用成本独立计费（v2 起）

### F.3 法律顾问视角（评分 72/100）

**✅ Strengths**：AIGC 备案 3 级 fallback / PIPL 7 day / License 白名单 / P0 24h Postmortem
**⚠️ Critical**：
- **L1** EULA / ToS / Privacy 模板 → G16 + Appendix C
- **L2** AI 生成内容责任归属 → G16
- **L3** Critic 误判免责 → G16
- **L4** Repro 5y SLA 法律性质（合同 vs best-effort）→ G16
- **L5** 学界合作合同模板 → G16
- **L6** EPL 库 SaaS 后端使用法务签字 → C21 + G17
- **L7** ECOS GPLv3 v1 用 vs 备用法务签字 → C21 + G17
- **L8** 数据出境用户协议条款 → G16
- **L9** AIGC 水印作为合规证据保存策略（与 G12 联动）
- **L10** 白帽奖励反诈骗 SOP（v1.5+ 补）
- **L11** 教育版滥用法律边界（v1.5+ 补）

### F.4 网站管理员视角（评分 78/100）

**✅ Strengths**：A.9 Day-1 清单 / P43 Graceful Shutdown / P46 Health 三端点 / P59 4-tier
**⚠️ Critical**：
- **OP1** Backup Restoration Runbook → G18 + Appendix D
- **OP2** On-Call Rotation 未设计 → G18 + Appendix D
- **OP3** 告警阈值未量化 → G18 + Appendix D
- **OP4** 日志保留分级 → G18
- **OP5** 数据库备份恢复演练 SOP → G18
- **OP6** gVisor 容器 GC（v1.5 起补充）
- **OP7** 密钥轮换 Cadence 表（G18 衍生）
- **OP8** Status Page 自动化工具（v1.5 起决策）
- **OP9** 容量自动扩缩（精简档 vs 标准档差异，v1.5 起）
- **OP10** Cost Anomaly Detection（与 G3 cost-attribution 联动）

### F.5 大学教师视角（评分 70/100）

**✅ Strengths**：Innovation #3 学界变现 + Apache 2.0 / 教学模式 + Notebook Colab + BibTeX / 月度分润 / Repro 5y
**⚠️ Critical**：
- **PR1** Provider Onboarding 学者门槛（v2 启动前补设计）
- **PR2** 学术声誉风险条款（G16 / 学界合作合同覆盖）
- **PR3** IP Attribution 量化标准（v1 末决策）
- **PR4** Classroom Plan 管理负担（v2 落地时 UX 强化）
- **PR5** LMS 集成（Canvas / Moodle / 雨课堂 / 学堂在线，v2 启用 ADR）
- **PR6** 学者 lifecycle handover（v2 启用前 ADR）
- **PR7** 跨校合作分润主体（G16）
- **PR8** 学生数据隐私 + 学术伦理（G16 + IRB 流程文档）
- **PR9** 教学 vs 研究 vs 生产模式数据隔离（v2 实施时强化）

### F.6 大学研究生视角（评分 73/100）

**✅ Strengths**：教育版永久 2K/月 + Pro 30d trial / 经典算例库 / Notebook Colab / 复现凭证 5y
**⚠️ Critical**：
- **GS1** .edu 邮箱失效后账号 lifecycle（v1.5 起 ADR）
- **GS2** Notebook Colab 国内访问替代（v1.5 起：阿里云 PAI / 自营 Notebook）
- **GS3** Repro 5y 对博士 + PostDoc 不够（学术 voucher 延 10y 评估）
- **GS4** 跨实验室协作账户共享（v2 起 ADR）
- **GS5** 学生 side project 灰色地带（合同条款 + 检测，v1.5+）
- **GS6** 学习曲线 onboarding tutorial（M4.5 GTM 准备时强化）
- **GS7** 学校网络限制 mirror / proxy（v1.5+ 补 FAQ）
- **GS8** 学校 Gurobi license 已购 value prop（M4.5 GTM 营销文案重点）

### F.7 潜在行业用户视角（评分 68/100）

**✅ Strengths**：Hello World 三件套 / NL Summary / Modal P5 警示 / Team plan 24h 法务 SLA / ¥6/次 起 vs Gurobi
**⚠️ Critical**：
- **IU1** 企业采购流程友好度（PO / SOW / 招标 / 框架协议模板）→ G19 + Appendix E
- **IU2** SOC 2 / ISO 27001 缺失 → G19（v1.5 启动 SOC 2 评估）
- **IU3** Gurobi 迁移工具 / 双跑对比 → G19
- **IU4** ERP / TMS / WMS connector v1 缺 → G19（v2 启动 3-5 个 POC）
- **IU5** API SLA best-effort = 大客户不接受 → enterprise 个案签约能力（v1.5 启动）
- **IU6** Algorithm Selection Wizard 缺 → P68 prompt store + UX 集成（v1.5+）
- **IU7** NL Summary 错时责任 → G16
- **IU8** 企业级 audit trail 结构化导出 → audit-service v2 拆出时强化
- **IU9** Customer Success 流程缺（5 人团队 dedicate 1 人，v1.5+ 启动）
- **IU10** 试用决策成本（landing → 试用步数优化，M4.5 GTM 时 A/B）
- **IU11** 跨国企业中文 only 障碍 → v1.5 起全栈 en-US（PRD §1727）

---

### 跨视角共识 7 项 Critical（CF1-CF7 全处理状态）

| # | Finding | 处理方式 |
|---|---|---|
| **CF1** | 法律合同模板 0 | ✅ G16 + Appendix C |
| **CF2** | EPL + ECOS 法务签字未确认 | ✅ C21 + G17（升 Critical）|
| **CF3** | Backup Restoration Runbook 缺 | ✅ G18 + Appendix D |
| **CF4** | On-Call Rotation Policy 缺 | ✅ G18 + Appendix D |
| **CF5** | Prompt Management 不是一等公民 | ✅ P68 |
| **CF6** | 学者 Provider Onboarding Lifecycle 缺 | ⚠️ 部分（PR1/PR6 → v2 启用前 ADR；后续可拆 docs/academic-provider-handbook.md）|
| **CF7** | 企业 GTM Toolkit 缺 | ✅ G19 + Appendix E |

---

## 📊 最终累积总览（v2.0 — 7-Role Review 强化后）

| 维度 | 数值 |
|---|:---:|
| 总章节 | 8 章 + 6 Appendix（A-F）|
| **Patterns** | **70 项**（P1-P70）|
| **Constraints** | **21 项**（C1-C21）|
| Services（v1 末）| 10 deployable（精简档 5）|
| Cross-Cutting Concerns | 19 项 |
| **Critical Gaps** | **4**（G3 / G6 / G7 / **G17 新**）|
| **Important Gaps** | **12**（G1/2/4/5/8-13 + **G16/18/19 新**）|
| Nice-to-have Gaps | 7（N1-N5 + G14/G15）|
| 累积修订 | **135 处**（6 轮 BMad party_mode + 1 轮 7-Role Review）|
| Reviewer 视角数 | **27**（20+ BMad agents + 7 stakeholder roles）|
| 输入文档 | 8 份 |
| 总行数 | ~3,500+ |
| **总体就绪度** | ✅ **READY FOR IMPLEMENTATION（HIGH-conditional）** |

> ⚠️ **Conditional 升级**：**4 Critical Gaps（G3/G6/G7/G17）必须在 M3 末前解决，G17 必须 M0 wk1-2 解决**；不达成 → M5 商用 hard-gate 阻断 或 v1 SKU 退化。

---

---

## 📝 Architecture v2.1 — Internal Consistency Fixes Changelog（2026-05-17）

> 经内部 grep-based 漂移审计（自审 + 7-Role Review 后），13 项 Critical Findings 修复入库。

### 修复总览

| # | 类型 | Finding | Fix 位置 | 影响 |
|---|:---:|---|---|---|
| **D1** | 漂移 | Step 3 Monorepo Tree 列了 13 apps（已删除 audit/revenue-share/data-export 仍在）| Step 3 § Monorepo Structure | 防止误建 services |
| **D2** | 漂移 | P24 consumer group example `audit-service-event-logger` | P24（line 774）| 示例改 `api-gateway-audit-logger` |
| **F1** | 一致性 | API Key 前缀 `sk-` (PRD) vs `sk_` (P23 架构) | P23 | 统一 `sk-`（PRD §1079）|
| **F3** | 一致性 | `events.human_review` 违反 P24 命名 | Concern #17 | 改 `events.critic` + event_type `critic.review.escalated` |
| **F4** | 一致性 | P5 Redis 前缀缺 `llm_cache:` `capability_cache:` `prompt_cache:` | D5 | 补 3 个前缀 |
| **B1** | 边界 | solver M1 vs capability-registry M3 依赖矛盾 | Service Catalog + Concern #12 | 明示 M1-M2 `shared-py/capabilities` static config + M3 起 service |
| **B2** | 边界 | outbox-relayer sidecar 部署时机 | C20 + Service Catalog | M1 fire-and-forget pub/sub；M2+ outbox sidecar（业务 service）|
| **B3** | 边界 | prompt-store 位置（capability-registry 子模块 vs 独立 service）+ 时机（M3 vs v1.5）| C17 + P68 | M1-M3 chat-service 内 prompts；**M5+ capability-registry 加 prompt-store sub-module**；v1.5 评估独立 |
| **PI1** | 落地 | Sprint 0 16 stories 严重超载（~45 person-week vs 容量 20）| Sprint 0 Anchor + Story Overview | **Sprint 0 限 8 stories**（0.1-0.8）；其余 M2/M3 sprint |
| **PI2** | 落地 | Story 0.x 依赖顺序错误（0.3/0.4/0.7 列在 0.6 前）| Sprint 0 Anchor + Story Overview | 重排：0.1→0.2→0.5→0.6→0.7→0.4→0.3→0.8 |
| **PI3** | 落地 | Story 0.13 K8s Namespace 仅适用标准档 | Foundation Continuation | 拆 M3.3a（标准档 K8s）+ M3.3b（精简档 docker-compose 蓝绿）|
| **PI4** | 落地 | Story 0.16 Critic 标注 SOP 跨多月持续工作 | Foundation Continuation | 拆 M3.5a（工具 + SOP）+ M3.5b（持续 epic）|
| **PI5** | 落地 | C21 EPL/ECOS contingency plan 未明示 | C21 | 加 contingency：SCS 替代 EPL/ECOS；`opt.nlp.*` SKU 标 ⚠️ 待签字 |

### 一致性增强（P23 ID 前缀清单扩展）

P23 现 ID 前缀涵盖 11 类：`opt_` `req_` `trc_` `evt_` `tnt_` `usr_` `cnv_` `msg_` `pol_` `prv_` `sub_` + 例外 `sk-` `repro-{YYYY}-{...}`。

### 一致性增强（Redis 前缀分桶扩展）

P5 现含 10 类前缀：`session:` `ratelimit:` `cache:` `pubsub:` `stream:` `idempotency:` `outbox:` **`llm_cache:`** **`capability_cache:`** **`prompt_cache:`**。

### 边界澄清矩阵（B1-B3）

| 组件 | M1-M2 形态 | M3 形态 | M5+ 形态 | v1.5 评估 |
|---|---|---|---|---|
| Capability lookup | `shared-py/capabilities/` 静态 YAML（8 SKU 硬编码）| `capability-registry` service 极简 CRUD + Redis SWR | 加状态机（shadow + 灰度）+ prompt-store sub-module | — |
| Outbox eventing | fire-and-forget Redis pub/sub（auth-service M1 注册事件等）| 同 M1 | `outbox-relayer sidecar` 业务 service 启用（billing M2 起）| — |
| Prompts | `apps/chat-service/prompts/` 代码常量（Chat M3 前不需要）| 同 chat-service 内 + GrowthBook flag A/B | capability-registry `prompt-store` sub-module 集中管理 | 评估拆独立 service |

### Sprint 0 缩减后实际工作量验证

| 阶段 | Stories | 估算 person-week | 容量验证 |
|---|:---:|:---:|:---:|
| **Sprint 0**（2-4 周）| 8 | ~20 | ✅ 5 人 × 4 周 |
| **M1 Sprint 1-4** | 业务 Epic A1-A10 + E1 first SKU + M2.1 准备 | ~30 | ✅ 5 人 × 6-8 周 |
| **M2 Sprint 5-8** | Epic B1-B13 + M2.1-M2.3 | ~35 | ✅ 5 人 × 8 周 |
| **M3 Sprint 9-12** | Epic N1-N12 + M3.1-M3.5a + 业务 chat 集成 | ~50 | ✅ 5 人 × 10 周 |

---

### 📊 累积总览 v2.1

| 维度 | v2.0 | v2.1 |
|---|:---:|:---:|
| Patterns | 70 | **70**（unchanged，但 P5/P23 内容扩展）|
| Constraints | 21 | **21**（unchanged，但 C17/C21 内容扩展含 contingency + 时间线）|
| Critical Gaps | 4 | **4**（unchanged）|
| Important Gaps | 12 | **12**（unchanged）|
| Services（v1 末）| 10 | **10**（unchanged，Step 3 Monorepo 漂移已修）|
| Story 0.x | 16（超载）| **8 Sprint 0** + **10 M2/M3 Continuation**（拆分 PI3/PI4 后总 18）|
| 累积修订 | 135 | **148**（+13 Critical Drift Fixes）|
| Reviewer 视角 | 27 | 27 + 1 内部一致性审计 |
| 总行数 | 3,156 | ~3,280 |

---

**OptiCloud Architecture Document — Final Version v2.1**
**`_bmad-output/planning/architecture.md`**
**🎯 READY FOR IMPLEMENTATION (HIGH-conditional)**
**Last Updated: 2026-05-17（v2.0 含 7-Role Review；v2.1 含 13 项 Drift Fixes）**

---

# Architecture v2.2 — UX Forward Refs Sync（2026-05-17）

> **触发原因**：Implementation Readiness Report (v2 / 95.5% READY) 识别 **4 项 UX Spec → Architecture Forward References** 待同步：FR1 IA / FR2 Emotional Response / FR3 Tailwind v4 / FR7 WCAG 2.2。本 v2.2 升级新增 **P75-P78 (4 Patterns)** + **C22 (1 Constraint)** + **NFR-A5 (1 NFR)**。

## v2.2 升级内容

### 新增 Pattern P75 — Persona-Surface Mapping（FR2 同步）

**触发**：UX Spec Step 4 Emotional Response 锁定 4 sub-persona surface-specific defining experiences（李工 物流 cURL / Lina 零售 CSV / 老张 制造 Excel / 陈架构师 SaaS SDK）。Architecture 需显式 mapping 此 4 surface 到 service/component。

**Pattern**：

| Persona | Surface | 关联 Service | 关联 packages/ui Component | 关联 Story |
|---|---|---|---|---|
| **李工** 物流 / cURL | `POST /v1/optimizations` cURL + Postman | api-gateway / solver-orchestrator | packages/ui SignupWizard + ConfirmationModal + APIKeyManager | Story 1.1a/1.1b / 2.1 / 3.1（J1 Vertical Slice） |
| **Lina** 零售 / CSV | CSV upload + 错误恢复 | api-gateway / solver-orchestrator | packages/ui FilePicker + RFC7807ErrorPanel + ConfirmationModal (partial-upload-recovery) | Story 3.11 J2 vertical slice / 3.7 errors[] |
| **老张** 制造 / Excel | Console .xlsx upload + 自动 detect + download chart | web / api-gateway | packages/ui ExcelDropZone（共用 FilePicker P74）+ LoadingShimmer + StatusCard | Story 3.E.1-9（含 PMR6 业务垂直模板 + 老张-2 友好版 Brand Voice） |
| **陈架构师** SaaS / SDK | Python/Node/Go SDK + errors[] detail + Provider 接口 | api-gateway / solver-orchestrator / capability-registry | packages/ui RFC7807ErrorPanel + provider_url 字段 + Sandbox console | Story 0.4 三语言 SDK error.locate() + 7.A.1 Provider 接口 |

**Implementation**：Service Catalog 每 service AC 含 "Persona surface coverage" 字段；packages/ui Component PR-gate 必含 "4 persona surface compatibility test"（避免某 Persona surface 漂移）。

### 新增 Pattern P76 — Information Architecture (IA) / Page Direction Map（FR1 同步）

**触发**：UX Spec Step 9 Page Direction Map 锁定 10 Pages × 8 Design Directions 完整 mapping。Architecture 需 IA 层抽象（不只 service / endpoint）。

**Pattern**：

```
10 Pages（Page Direction Map / UX Spec Step 9）：
├── Landing                 → web / SSR / Direction "Engineer-First / 实证克制"
├── Pricing                 → web / SSR / Direction "Pragmatic"
├── Docs                    → web / SSR / Direction "Engineer-First"
├── Console-Dashboard       → web / CSR + api-gateway / Direction "Insight-First"
├── Console-Run             → web / CSR + solver-orchestrator + chat-service / Direction "Defining-Experience"
├── Console-History         → web / CSR + audit-log + repro-service / Direction "Trust-Forward"
├── Console-Settings        → web / CSR + auth-service + billing-service / Direction "Pragmatic"
├── Status-Page             → web / SSR / 无鉴权 / Direction "Trust-Forward"
├── Auth-Pages              → web / CSR + auth-service / Direction "Defining-Experience"
└── Error-Pages             → web / CSR + api-gateway / Direction "Recovery-Forward"
```

**Implementation**：
- **`apps/web/src/pages/`** 目录结构对齐 10 Page Direction Map
- 每 page route 含 frontmatter metadata `{ direction: '...', persona_surface: [...], design_principles: [...] }`
- packages/ui Component 引用必含 "page direction tag"，CI 验证 page-direction mismatch

### 新增 Pattern P77 — Tailwind v4 Migration Window（FR3 同步 + C22 联动）

**触发**：UX Spec Step 6 Design System Tailwind v3 + v4 升级 v1.5+。Architecture 需锁升级窗口 + breaking change 处理。

**Pattern**：

- **v1 起 - v1.5 末**：Tailwind v3.4+ locked（不变升级）
- **v1.5 起（M7+）**：Tailwind v4 evaluation gate
  - v4 引入新 OKLCH color space + Vite native + new `@theme` directive
  - **Migration checklist**：
    - 所有 packages/ui 70 tokens 转 OKLCH（保持 hex hex equivalent fallback for old browser）
    - tailwind.config.ts 转 `@theme` directive
    - Chromatic visual regression 100% pass after migration（每 Component 必跑）
    - PostCSS plugin 兼容验证（Storybook + Next.js）
- **v2 起（M9+）**：Tailwind v4 mainline + v3 deprecated
- **Breaking change 缓冲**：v1.5 中 2 quarter dual support；any production app 同时支持 v3 / v4 token resolution

**Implementation**：
- Story (v1.5+) 加 **0.10b: Tailwind v4 Migration Story**（packages/ui + 10 page routes + Chromatic 全量 visual regression）
- C22 Constraint 锁定升级窗口

### 新增 Pattern P78 — WCAG 2.2 AA Upgrade Path（FR7 + NFR-A5 同步）

**触发**：UX Spec Step 13 a11y WCAG 2.1 AA v1 + WCAG 2.2 AA v1.5+ upgrade。Architecture 需 a11y 升级路径 + 4 new WCAG 2.2 criteria 工程化。

**Pattern**：WCAG 2.1 → 2.2 新增 4 criteria 升级：

| WCAG 2.2 新 criterion | UX Spec Reference | packages/ui 影响 | Implementation Story |
|---|---|---|---|
| **2.4.11 Focus Not Obscured (Minimum)** | UX Spec AA8 | Modal / Dropdown overlay layer | Story 9.5 升级 + packages/ui 全 stub refactor |
| **2.4.12 Focus Not Obscured (Enhanced)** | UX Spec AA8 (Tier 1.5+) | Modal stack management | Story 9.5 v1.5+ |
| **2.5.7 Dragging Movements** | UX Spec ExcelDropZone | ExcelDropZone + 老张 surface drag-drop fallback | Story 3.E.1 v1.5+ enhance |
| **3.2.6 Consistent Help** | UX Spec EP4 Help & Documentation | 全 Console 一致 help icon location | Story 9.5 + UX Spec audit |

**Implementation**：
- **v1**：WCAG 2.1 AA + Standard a11y Hook Wrapper（UX-DR5）+ axe-core CI（Story 0.12）
- **v1.5+**：WCAG 2.2 AA evaluation gate + 4 criteria audit + Story 9.5 落地
- **v2+**：WCAG 2.2 AA mainline + Standard a11y Hook Wrapper v2（含 2.2 hooks）+ axe-core CI rules 升级到 2.2 ruleset

### 新增 Constraint C22 — Tailwind v4 升级窗口锁定 v1.5+

> **Constraint**：Tailwind v3.4+ 锁定 v1 期间；v4 升级仅在 v1.5 (M7+) 经评估后启动；不允许 dev branch 提前用 v4 directives。任何 PR 含 `@theme` 或 OKLCH `oklch()` color literal 在 v1 期间自动 CI 拒绝。**Owner**：Frontend Lead + Architect。

### 新增 NFR-A5 — WCAG 2.2 AA v1.5+ 升级

> **NFR-A5 (Accessibility 升级)**：
> - **v1 (M1-M5)**：WCAG 2.1 AA + Standard a11y Hook Wrapper + axe-core CI 100% violation 0 + 6 a11y profile (含 Cognitive, 不含残障 panel)
> - **v1.5+ (M7-M8)**：WCAG 2.2 AA evaluation + 4 new criteria audit（Focus Not Obscured Min/Enhanced + Dragging Movements + Consistent Help）+ packages/ui Standard a11y Hook v2 升级
> - **v2+ (M9+)**：WCAG 2.2 AA mainline + axe-core CI ruleset 升级 + Tablet 768-1023px Tier 1 a11y 完整支持 + 4 sub-persona panel quarterly 抽样（不含残障 panel，用户已声明剔除）
>
> **Test methodology**：v1 axe-core + jest-axe CI + 季度 4 sub-persona panel；v1.5+ + WCAG 2.2 ruleset；v2+ + 第三方 a11y audit annual。

### Forward References to UX Spec 同步状态（v2.2 完成）

| # | UX Spec Step | Forward Ref | v2.1 状态 | v2.2 状态 | 应用 |
|:-:|---|---|:-:|:-:|---|
| FR1 | Step 2 | IA / Page Direction Map | 待 v2.2 | ✅ **同步**（P76 IA / Page Direction Map）| apps/web/src/pages/ 结构 + frontmatter metadata |
| FR2 | Step 4 | Emotional Response architecture（4 sub-persona surface） | 待 v2.2 | ✅ **同步**（P75 Persona-Surface Mapping）| Service Catalog + packages/ui Component PR-gate 含 4 persona surface compatibility test |
| FR3 | Step 6 | Tailwind v3→v4 升级（v1.5+） | 待 v2.2 | ✅ **同步**（P77 Tailwind v4 Migration + C22 升级窗口锁定）| Story 0.10b（v1.5+）+ Chromatic visual regression |
| FR4 | Step 6 | Design System tokens + packages/ui 单源 | ✅ 已同步（P72）| ✅ 维持 | — |
| FR5 | Step 6 | Status 文本 i18n 单源 | ✅ 已同步（P73）| ✅ 维持 | — |
| FR6 | Step 6 | Cross-Service Storybook Visual Regression | ✅ 已同步（P74）| ✅ 维持 | — |
| FR7 | Step 13 | WCAG 2.2 v1.5+ upgrade path | 待 v2.2 | ✅ **同步**（P78 + NFR-A5）| Story 9.5 v1.5+ + WCAG 2.2 4 criteria 工程化 |

**✅ 7 / 7 UX Forward References 全部同步**

## v2.2 累积总览

| 维度 | v2.1 | v2.2 |
|---|:---:|:---:|
| Patterns | 70 | **74**（+P75-P78）|
| Constraints | 21 | **22**（+C22）|
| NFR items | 12 类 ~50 items | 12 类 ~51 items（+NFR-A5）|
| Critical Gaps | 4 | 4（unchanged）|
| Important Gaps | 12 | 12（unchanged）|
| Services | 10 | 10（unchanged）|
| Forward References to UX 同步 | 3/7 | **7/7** ✅ |
| 累积修订 | 148 | **155**（+7 v2.2 同步项）|
| 总行数 | ~3,280 | ~3,400 |

---

**OptiCloud Architecture Document — Final Version v2.2**
**`_bmad-output/planning/architecture.md`**
**🎯 READY FOR IMPLEMENTATION (HIGH-conditional)**
**Last Updated: 2026-05-17（v2.0 含 7-Role Review；v2.1 含 13 项 Drift Fixes；v2.2 含 UX Forward Refs 7/7 同步 + P75-P78 + C22 + NFR-A5）**
