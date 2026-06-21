# OptiCloud — 通用优化与预测云

> 让懂业务的工程师 / 数据分析师 5 分钟用上 Gurobi / TimeGPT 级算法。

## 当前状态

**阶段:** v1 BMAD 工程账本已收口，进入 v2 产品化 / 部署验证准备。

**截至 2026-06-21:**

- `sprint-status.yaml` 跟踪 203 个 concrete stories。
- 199 个 stories 已完成。
- 4 个 Epic 0 外部流程项保持 `blocked`，owner / 法务 / PM 已决定 `KEEP_BLOCKED`。
- 当前没有已立项的 actionable backlog / ready-for-dev / in-progress / review 工程 story。
- UX evolution 已通过 PR #182-#185 收口，`main` 已同步。

仍保持 `blocked` 的外部项：

- `0-0-sprint0-calibration-week`
- `m0-legal-1-license-deliverable`
- `m0-legal-status-tracking`
- `m0-aigc-status-tracking`

这些不是代码缺口。除非后续提供外部证据或正式豁免，否则不应标记为 `done`。

## 仓库结构

```text
opticloud/
├── apps/
│   ├── api-gateway/            # API gateway placeholder / future ingress
│   ├── auth-service/           # 注册 / 登录 / API Key / 风控
│   ├── billing-service/        # Credits / 订阅 / 发票 / 对账
│   ├── capability-registry/    # Provider catalog / 能力注册
│   ├── chat-service/           # Chat / NL -> model / sandbox handoff
│   ├── critic-service/         # Critic calibration config / future service
│   ├── outbox-relayer/         # Outbox sidecar relay
│   ├── repro-service/          # Repro service placeholder / voucher roadmap
│   ├── sandbox-runner/         # 沙箱执行边界
│   ├── solver-orchestrator/    # 优化 / 预测 / provider routing
│   └── web/                    # Next.js 15 public site + console
├── packages/
│   ├── i18n/                   # Error message single-source catalogs
│   ├── node-sdk/               # Node SDK package scaffold
│   ├── python-sdk/             # Python SDK alpha client
│   ├── shared-py/              # Python shared libs
│   ├── shared-ts/              # TypeScript shared contracts
│   └── ui/                     # Shared UI components
├── infra/
│   ├── docker/                 # Docker build docs
│   ├── k8s/production/         # Production namespace / NetworkPolicy manifests
│   └── local-init/             # Local Postgres init schema
├── docs/                       # Runbooks, ADRs, academic/commercial docs
├── e2e/                        # Playwright tests
├── tests/                      # Python repo-level governance tests
└── _bmad-output/               # Planning, stories, sprint ledger, reviews
```

## 快速开始

### 前置

- Node.js 18+
- pnpm 9+
- Python 3.12
- uv
- Docker + Docker Compose

### 安装依赖

```powershell
cd D:\优化预测网站
uv sync
pnpm install
```

### 启动本地基础设施

```powershell
Copy-Item .env.example .env
docker-compose up -d
docker-compose ps
```

本地基础设施包括 Postgres、Redis、Vault dev、MinIO、LocalStack 和 outbox-relayer。

### 启动 Web

```powershell
pnpm --dir apps/web dev
```

打开 http://localhost:3000。

关键页面：

- `/` — 公开首页
- `/docs` — 文档入口
- `/docs/user-guide` — 网站操作说明
- `/algorithms` — 算法目录
- `/console/excel` — Excel 工作流
- `/status` — 状态页
- `/security` — 安全披露

### 启动后端服务示例

```powershell
uv run --directory apps/auth-service uvicorn auth_service.main:app --reload --port 8001
uv run --directory apps/solver-orchestrator uvicorn solver_orchestrator.main:app --reload --port 8002
```

OpenAPI:

- Auth service: http://localhost:8001/docs
- Solver orchestrator: http://localhost:8002/docs

更多面向非工程师的本地演示说明见 [HOWTO-local-demo.md](HOWTO-local-demo.md)。

## 常用验证命令

```powershell
# Web typecheck
pnpm --dir apps/web typecheck

# Web tests
pnpm --dir apps/web test

# Public / console mobile overflow regression
pnpm --dir e2e exec playwright test tests/public-mobile-overflow.spec.ts --project=chromium --workers=1

# Python governance / service tests
uv run pytest

# Diff whitespace gate
git diff --check
```

## 关键文档

| 文档 | 用途 |
|---|---|
| [_bmad-output/stories/sprint-status.yaml](_bmad-output/stories/sprint-status.yaml) | 当前 story / epic 账本 |
| [_bmad-output/stories/m0-blocked-items-owner-decision-2026-06-21.md](_bmad-output/stories/m0-blocked-items-owner-decision-2026-06-21.md) | 4 个外部 blocked 项的 owner 决策记录 |
| [_bmad-output/stories/evo-5-console-data-pages-user-guide.md](_bmad-output/stories/evo-5-console-data-pages-user-guide.md) | UX evolution 收口记录 |
| [_bmad-output/planning/prd.md](_bmad-output/planning/prd.md) | PRD / capability contract |
| [_bmad-output/planning/architecture.md](_bmad-output/planning/architecture.md) | 架构决策与约束 |
| [_bmad-output/planning/ux-design-specification.md](_bmad-output/planning/ux-design-specification.md) | UX / component / a11y 规格 |
| [_bmad-output/planning/epics.md](_bmad-output/planning/epics.md) | 原始 epic / story 拆解 |
| [docs/adr/README.md](docs/adr/README.md) | ADR 索引 |
| [docs/runbooks/](docs/runbooks/) | 运维、治理和审计 runbook |

## 合规与许可证状态

当前工程约束仍以 BMAD 账本为准：

- Python 运行时锁定为 3.12。
- v1 允许 MIT / Apache 2.0 / BSD；EPL 仅调用不修改。
- GPL / ECOS / Apache 2.0 自研算法签字仍属外部法务 blocked 项。
- AIGC filing 状态追踪仍属外部 blocked 项。

仓库内代码和文档不能替代法务意见、备案证明或外部流程证据。

## 下一步建议

1. 真实部署验证：把当前 docker-compose / k8s / service health 从静态资产推进到可复跑的 staging verification 清单。
2. v2 产品化：选择 Excel、预测、Classroom、Provider 或 billing 其中一条，把现有 stub / demo 能力升级为真实闭环。
3. 商业化材料：整理试点客户 onboarding、采购包、价格说明和白皮书材料。
