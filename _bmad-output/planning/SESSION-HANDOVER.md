# OptiCloud — Session Handover（2026-05-17）

> 项目代号：**OptiCloud**（品牌名 M0 内定）
> 课题组：ITADN / TJU / Trust-Tech 方向
> 仓库：`D:\优化预测网站\`

---

## 📍 当前位置

**BMad 工作流阶段**：✅ **PRD + Implementation Readiness Assessment 已完成**

| 已完成 | 文件 | 状态 |
|---|---|:---:|
| 网站方案 v0.5.1（22 章 + 5 附录）| `网站方案.md` | ✅ |
| PRD（12 章 / ~1800 行 / 77 FR / Capability Contract 锁定）| `_bmad-output/planning/prd.md` | ✅ |
| Implementation Readiness Report（92.5% 优秀级，PRD-only mode）| `_bmad-output/planning/implementation-readiness-report-2026-05-17.md` | ✅ |
| BMad 配置（core + bmm）| `_bmad/core/config.yaml` + `_bmad/bmm/config.yaml` | ✅ |

---

## 🎯 已固化的关键决策（不要再讨论 / 已锁定）

### 战略层

- **产品代号**：OptiCloud（品牌名 M0 内定）
- **定位**："让算法走出实验室" — 工程师 / 数据分析师 5 分钟用上 Gurobi/TimeGPT 级算法
- **主受众**：中型企业的优化 / 数据科学 / 算法工程师（中国 ≈ 30-50 万人）
- **战略愿景**：2026-2030 窗口成为中文世界的决策智能协议层
- **项目类型**：api_backend（主）+ web_app（副）
- **演进路径**：M1: api+web(简) → M3: +Chat(AIGC-gated) → M4: +saas_b2b → M5+: +marketplace

### 技术层

- **v1 LLM**：DeepSeek-V3.5 API 主路径 + Qwen-Max incident 应急 fallback
- **v1 求解器**：HiGHS (MIT) + OR-Tools (Apache) + IPOPT/Bonmin/Couenne (EPL 仅调用)
- **v1 时序基础模型**：Chronos / TimesFM / Lag-Llama / Moirai（Apache 开源自托管）
- **沙箱**：gVisor（CPU 1 vCPU / Mem 1GB / Net 禁外网 / FS 只读 / 90s 强杀）
- **Vector DB**：v1 pgvector → v2 末 Qdrant 迁移
- **数据库**：v1 单 Postgres → v2 拆 4 库（core / billing / chat / audit）
- **GPU**：v1 RunPod/AutoDL 按秒云 → v3 自建集群（触发：月活付费 ≥500 AND LLM 月成本 ≥¥5 万 AND 团队 ≥6 人 AND 跑道 ≥12 月）

### 计费层

- **Credits 单位**：1 ¥ = 100 Credits
- **公式**：`Credits = ⌈k_algo × scale × t_solve + k_overhead⌉ + NL_credits` 封顶计费
- **算法分层**：T1-T6 优化（1×-18×）/ P1-P5 预测（1×-12×）/ N1-N4 LLM（0.1×-15×）
- **订阅**：Free 1K + 注册一次性 5K / Starter ¥39 / Pro ¥299 / Team ¥999 / Enterprise 询价
- **教育版**：Pro 30d trial + 永久 2K/月（学生）
- **Provider 分润**：自研 100/0 / 合作课题组 60/40 / 商业 50/50

### 资源 / 预算

- **精简档**：3 人（1 全职 + 2 兼职）/ ¥114 万 / 13 端点 / 2-3 SKU
- **标准档（推荐）**：5 人全职 / ¥248 万 / 29 端点 / 4 SKU
- **扩展档**：8-10 人全职 / ¥400 万 / 29+6 v2 端点 / 6 SKU
- **资金红线**：现金流跑道 < 6 月触发紧急动作

### 商业层

- **MVP 哲学**：Validated Learning + 92% Cost Win 承诺
- **M5 PMF 门槛**：付费 ≥50 / 月营收 ≥¥4 万 / Free→Paid ≥2%（90d）
- **v2 末**：月营收 ≥¥40 万 触发 Marketplace
- **Marketplace 启用 hard-gate**：≥¥40 万 月营收

### 合规层

- **公司主体**：M0 wk1 注册（高校事业单位不能备案 AIGC）
- **ICP 备案**：M1 末
- **AIGC 备案**：M3 末 hard-gate + 三级 fallback（M3 失败 → API-only / M5 失败 → 暂停 Chat / M7 失败 → 评估走向）
- **等保 2.0 二级**：评测启动 M3 / 取证 M5 末
- **PIPL 删除 SLA**：7 day（行业自律，非法定）

### 创新层（PRD § Innovation Ranking）

🌟 **3 Core Innovations**（70-80% 估值贡献）：
- #1 Critic Agent SaaS 化（核心 AI 层）
- #2 Repro 5 年 SLA + Provider 自动迁移
- #3 学界变现 + 内容即产品

⭐ **4 Important Innovations**（20-30%）：
- #4 行业模板可插拔
- #5 Credits 跨层统一定价
- #6 Trust-Tech / AQGS Apache 2.0 开放（M0 wk2 吕老师等签发）
- #7 三合一 first-mover

### 6 条 Hard Rules

1. 公司主体 M0 wk1 注册
2. 算法许可白名单（MIT / Apache 2.0 / BSD / EPL；PR 自动检查）
3. 排他融资条款一律拒绝
4. 2027-2029 拒绝中等估值 exit
5. Marketplace 启用 ≥ 月营收 ¥40 万
6. P0 安全事故 24h 内公开 Postmortem

---

## 🚨 5 项 M0 必做（启动前 P0，不解决继续走 BMad 流程 = 白做）

1. 🔴 **公司主体 M0 wk1 注册** — 有限责任公司（注册资本 ≥¥100 万）；4-8 周拿证
2. 🔴 **AIGC 备案中介签约 M0 wk1** — 6-12 月路径必立即启动（费用 ¥3-8 万必出预算）
3. 🟠 **§22 启动问卷填表 ≥80% 通过**（v0.5.1 附录 E）
   - E.1 团队（≥5 人全职 / 或 1 全职 + 2 学生兼职精简档）
   - E.2 资金（标准档 ¥248 万 12 月 / 精简档 ¥114 万）
   - E.3 公司主体（见 #1）
   - E.4 自研代码自查（5 个算法 5 项 hard rule）
   - E.5-E.7 战略 / 合规 / 风险
4. 🟠 **课题组吕老师等 M0 wk2 签发 Apache 2.0** — 5 个自研算法 license
5. 🟡 **第二个行业模板选定**（建议物流）

---

## ⏭️ 下一步选择（新 session 启动时使用）

### Path A：先解决 M0 blocker 再继续（强烈推荐）

不开 BMad，先做 5 项 M0 必做。**1-2 周后**再回来跑：

```
/bmad-help              ← 重新评估推荐路径
```

### Path B：继续 BMad 工作流（如果 M0 已启动）

任选其一进入：

| 命令 | 用途 | 时长 |
|---|---|:---:|
| `/bmad-create-architecture` | 创建技术架构正式文档 | 1-2 session |
| `/bmad-create-ux-design` | 创建 UX 规格（Chat / Console / 新手向导）| 1-2 session |
| `/bmad-create-epics-and-stories` | 77 FR → 8 Epic → 91-137 Story | 2-3 session |
| `/bmad-check-implementation-readiness` | 4 文档齐套后回归完整 traceability check | 1 session |
| `/bmad-create-story` + `/bmad-dev-story` | 单 Story 实现循环 | 持续 |
| `/bmad-quick-dev` | 跳过文档直接出代码（精简档加速）| 持续 |

### Path C：快速路径（精简档 1 全职）

```
/bmad-agent-quick-flow-solo-dev   ← 召唤 Barry 单人开发者，跳过 Architecture/UX/Epics 文档
```

---

## 📁 关键文件清单

```
D:\优化预测网站\
├── 网站方案.md                                    ← 源文档 v0.5.1（22 章 + 5 附录）
├── papers/                                       ← 算法依据（ITADN / optimize / safety）
├── _bmad/
│   ├── core/config.yaml                          ← 用户=课题组 / 简体中文
│   └── bmm/config.yaml                           ← project_name=OptiCloud / planning_artifacts
└── _bmad-output/planning/
    ├── prd.md                                    ← ✅ PRD COMPLETE（12 章 / 77 FR）
    ├── implementation-readiness-report-2026-05-17.md  ← ✅ Readiness 92.5%
    └── SESSION-HANDOVER.md                       ← 本文档（新 session 入口）
```

---

## 📊 PRD 质量与构建谱系

| 维度 | 值 |
|---|:---:|
| 总行数 | ~1800 |
| Level-2 章节 | 12 个（含 Glossary）|
| FR 总数 | 77（8 能力域）|
| NFR 类别 | 11 |
| User Journey | 11 个（9 实战 + 2 placeholder）|
| Innovation | 7（3 Core + 4 Important）|
| Hard Rules | 6 |
| Risk | Top 3 + Top 10 |
| 强化总数 | **150+ 处修订** |
| Party Mode 轮次 | **14 轮**（54 个 agent 视角参与）|
| Advanced Elicitation 轮次 | **7 轮**（11 种方法）|
| Readiness 评分 | **92.5%（74/80）** 优秀级 |

---

## 🔄 新 Session 入口提示词

复制以下文本给新 session 的 Claude：

```
继续 OptiCloud 项目工作。请先阅读：
1. D:\优化预测网站\_bmad-output\planning\SESSION-HANDOVER.md（本文档，了解全部进度 + 决策）
2. D:\优化预测网站\_bmad-output\planning\prd.md（PRD，77 FR Capability Contract）
3. D:\优化预测网站\_bmad-output\planning\implementation-readiness-report-2026-05-17.md（Readiness 92.5%）

然后告诉我下一步选项（Path A 暂停推进 M0 / Path B 继续 BMad / Path C 快速路径）。

当前 M0 进度：[填入当前 5 项必做事项进度]
本次想做：[填入想做的事]
```

---

**Handover 时间**：2026-05-17
**总会话时长**：2 sessions（2026-05-16 + 2026-05-17）
**总用户消息数**：~150+
