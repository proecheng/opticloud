# OptiCloud — 通用优化与预测云

> 让懂业务的工程师 / 数据分析师 5 分钟用上 Gurobi/TimeGPT 级算法

**Status:** 🚧 **Sprint 0 — Foundation building (M0 W0-10)**
**Path:** B Balanced — 5 unlock node 序列
**Readiness:** 97.5% READY FOR SPRINT 0 EXECUTION ([v3 report](_bmad-output/planning/implementation-readiness-report-2026-05-17-v3.md))

---

## 🏗️ Monorepo 结构

```
opticloud/
├── apps/
│   ├── api-gateway/            # FastAPI 网关 (M1)
│   ├── auth-service/           # 注册 / API Key / JWT (M1, Story 0.6)
│   ├── solver-orchestrator/    # 优化求解 (M1)
│   ├── billing-service/        # Credits 双写 (M2)
│   ├── chat-service/           # Chat / NL→Model (M3, AIGC gated)
│   ├── critic-service/         # Critic Agent SaaS (M3)
│   ├── sandbox-runner/         # gVisor 隔离 (M3)
│   ├── capability-registry/    # Provider catalog (M3+)
│   ├── repro-service/          # Voucher / 5y SLA (M5)
│   └── web/                    # Next.js 15 (M1+)
├── packages/
│   ├── shared-py/              # Python 共享 (cost_telemetry, aigc_filter, otel_setup)
│   ├── shared-ts/              # TS types (OpenAPI codegen)
│   └── ui/                     # Radix + shadcn/ui Components
├── infra/
│   └── local-init/             # Postgres init schema
├── docs/
│   ├── runbooks/               # Day-2 ops SOPs
│   ├── legal-templates.md      # 合同模板索引
│   └── ...
└── _bmad-output/planning/      # BMad workflow 输出（PRD + Arch + UX + Epics + Readiness）
```

---

## 🚀 Quickstart

### 前置

- **pnpm** 9+ (`npm install -g pnpm`)
- **uv** (`curl -LsSf https://astral.sh/uv/install.sh | sh` or [uv docs](https://docs.astral.sh/uv/))
- **Python** 3.12 (`uv python install 3.12`)
- **Docker** + Docker Compose
- **Node.js** 18+

### 启动本地栈

```bash
# 1. Install Python + Node 依赖
uv sync                          # Python (uv workspace)
pnpm install                     # Node (pnpm workspace)

# 2. 起本地 infra（Postgres + Redis + Vault + MinIO + LocalStack）
cp .env.example .env             # 编辑 .env 设置开发密钥
docker-compose up -d

# 3. 跑 auth-service
cd apps/auth-service
uv run uvicorn main:app --reload --port 8001

# 4. 测试 signup endpoint
curl -X POST http://localhost:8001/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"phone":"+8613800138000","email":"test@example.com"}'

# 5. OpenAPI docs at http://localhost:8001/docs
```

---

## 📚 关键文档

| 文档 | 用途 |
|---|---|
| [`_bmad-output/planning/epics.md`](_bmad-output/planning/epics.md) | 21 Epics / 192 Stories backlog（v1 主 entry doc）|
| [`_bmad-output/planning/prd.md`](_bmad-output/planning/prd.md) | 78 FR Capability Contract (v1.1) |
| [`_bmad-output/planning/architecture.md`](_bmad-output/planning/architecture.md) | 74 Patterns / 22 Constraints (v2.2) |
| [`_bmad-output/planning/ux-design-specification.md`](_bmad-output/planning/ux-design-specification.md) | 29 Components / 6 a11y profile (v1) |
| [`_bmad-output/planning/implementation-readiness-report-2026-05-17-v3.md`](_bmad-output/planning/implementation-readiness-report-2026-05-17-v3.md) | Final Readiness 97.5% |
| [`网站方案.md`](网站方案.md) | 源文档 v0.5.1（22 章 + 5 附录）|

---

## 🛡️ 合规

- **License (v1)**: MIT / Apache 2.0 / BSD 自由调用；EPL 仅调用不修改；GPL-3.0 limited-to ECOS（v2 法务签字后启用）
- **C6**: Python 3.12 locked monorepo 内
- **C9**: Postgres TDE 全环境启用 + Vault dev mode (CI)
- **AIGC**: M3 备案 hard-gate（M0 启动中介 ¥3-8 万）

详 [`docs/legal-templates.md`](docs/legal-templates.md) + [`docs/runbooks/`](docs/runbooks/).

---

## 📝 License

**MVP**: 待定（M0 wk1-2 法务签字 — Apache 2.0 主 / 自研算法）
