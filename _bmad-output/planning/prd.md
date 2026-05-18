---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
inputDocuments:
  - D:\优化预测网站\网站方案.md
  - D:\优化预测网站\papers\ITADN\README.md
  - D:\优化预测网站\papers\ITADN\ITADN-对接问题回答.zh-CN.md
  - D:\优化预测网站\papers\optimize\README.md
  - D:\优化预测网站\papers\safety\README.md
documentCounts:
  briefCount: 0
  researchCount: 0
  brainstormingCount: 0
  projectDocsCount: 5
workflowType: prd
sourceDocument: 网站方案.md v0.5.1
classification:
  projectType: api_backend
  secondaryType: web_app
  evolutionPath:
    - "M1: api_backend + web_app(simplified)"
    - "M3: web_app(full Chat) gated by AIGC备案"
    - "M4: +saas_b2b"
    - "M5+: +marketplace"
  domain: scientific
  domainSubtype: decision_intelligence
  domainVerticals:
    - energy
    - logistics
    - fintech
    - manufacturing
    - retail
    - healthcare
    - govtech
    - scientific-research
  complexity:
    external: medium
    internal: high
    internal_high_constraint:
      - "M1 至多 1 个 high-risk 技术组件"
      - "Vector DB → pgvector 起步（不上 Qdrant）"
      - "LLM Router → 单一 DeepSeek，无切换"
      - "i18n → 仅 zh + 关键页 en 兜底"
      - "Provider Console → 月报邮件代替"
      - "M1 季末未达成 80% 完成度，强制砍范围"
  projectContext: greenfield
  specialFlags:
    - aigc_filing_hard_gate
    - compliance_parallel_to_pmf
    - level_2_security
    - multi_tenant_isolation
    - reproducibility_required
    - sandbox_execution_critical
    - bilingual_i18n
    - two_sided_marketplace
  elicitationHistory:
    - step-02-discovery party_mode (4 agents: Mary/John/Winston/Sally/Victor)
    - step-02-discovery advanced_elicitation method_1 pre_mortem (applied changes 1,3,5 of 6)
    - step-02b-vision party_mode (5 agents: Sophia/Carson/Caravaggio/Victor/Mary)
    - step-02b-vision advanced_elicitation method_1 shark_tank (5 sharks, applied all 5 fixes)
    - step-02b-vision advanced_elicitation method_3 hindsight_2030 (7 TPs + 4 Anti-TPs, applied all 10)
    - step-02c-executive-summary party_mode (5 agents: Paige/Quinn/Mary/Sally/John, applied E1-E12)
    - step-02c-executive-summary advanced_elicitation method_2 comparative_matrix (applied #1+#2, score 79.3%→86.7%)
    - step-02c-executive-summary advanced_elicitation method_3 expand_contract_audience (applied all 5, score 86.7%→95.3%)
    - step-03-success party_mode (5 agents: Murat/Quinn/Mary/Bob/Winston, applied F1-F17 all 17 fixes)
    - step-03-success advanced_elicitation methods 1+2 comparative_matrix+pre_mortem_kpis (applied G1-G8 all 8, score 87.1%→95.7%)
    - step-04-journeys party_mode_5 (5 agents: Sally/Maya/Sophia/Quinn/Bob, applied U1-U13 except U10)
    - step-04-journeys advanced_elicitation methods 2+1 customer_support_theater+comparative_matrix (applied F1-F5, score 86.4%→91.4%)
    - step-04-journeys party_mode_6 (4 agents: Amelia/Murat/Carson/Indie, applied V1-V12 all 12, score 91.4%→95%)
    - step-05-domain party_mode_7 (5 agents: Mary/Winston/Quinn/Murat/John, applied D1-D16 all 16)
    - step-06-innovation party_mode_8 (5 agents: Victor/Carson/Sophia/Mary/Dr.Quinn, applied I1-I9 all 9)
    - step-06-innovation advanced_elicitation methods 1+3 comparative_matrix+reverse_engineering (applied J1-J5, score 85.4%→91.7%)
    - step-07-project-type party_mode_9 (5 agents: Amelia/Winston/Murat/Paige/Mary, applied P1-P14 all 14)
    - step-07-project-type party_mode_10 (5 agents: Bob/Carson/Caravaggio/Indie/Sally, applied Q1-Q12 all 12)
    - step-09-functional party_mode_11 (5 agents: Carson/Bob/Quinn/Amelia/John, applied F1-F7 all 25 changes)
    - step-09-functional advanced_elicitation methods 3+1 pre_mortem+matrix (applied K1-K7, score 90.7%→93.7%)
    - step-09-functional party_mode_12 (5 agents: Dr.Quinn/Indie/Sophia/Maya/Paige, applied L1-L12 all 12, total 77 FR with new numbering A1-A10/C1-C8/E1-E10/N1-N12/B1-B13/R1-R7/P1-P8/O1-O11)
    - step-10-nonfunctional party_mode_13 (5 agents: Murat/Winston/Mary/Bob/Sally, applied M1-M15 all 15)
    - step-11-polish party_mode_14 (5 agents: Paige/John/Sophia/Mary/Murat, applied P0+P1 9 of 18 changes: ¥4 万 unified, frontmatter sync, Product Scope compressed, AIGC M3 末 unified, Glossary added, transitions added, Stage tag unified, 76% Gartner unified, 决策协议层 unified)
    - "edit-2026-05-17 v1.1 from /bmad-edit-prd: 77→78 FR (new E11 Console Excel upload-download v1 末 Critical, FG1.2), Postman Collection M1 Critical added to SDK Table + Onboarding 一键导入 Postman (FG1.1), Error Codes RFC 7807 errors[] detail object schema + i18n single-source ESLint enforced (FG1.3), 4 Forward References to Architecture v2.2 documented (FR1 IA / FR2 Emotional / FR3 Tailwind v4 / FR7 WCAG 2.2), 6 a11y profile + Standard a11y Hook + Tablet 768-1023px Tier 1 noted in §7 Accessibility"
vision_v4_notes:
  hero:
    h1: 让算法走出实验室
    h2: 让懂业务的工程师 / 数据分析师 5 分钟用上 Gurobi/TimeGPT 级算法
    subtitle: |
      76% 中型企业的工程师手里只有 Excel——算法用不起、用不动。
      我们让他们用上。面向中文工程师的本地化体验。
      （业务人员的无代码入口将在 M3 后开放）
  value_prop_D:
    - 76% 的中型企业里，工程师手里只有 Excel
    - 我们让他们用一行 API 跑通过去只有 Gurobi / DataRobot 能做的事
    - 免费试用，分钱级调用，3 分钟上手
  dual_vision:
    tactical_public: "2 周工程项目 → 30 分钟 API 调用"
    strategic_internal: "中文世界的决策智能协议层（2026-2030 窗口）"
  primary_persona_v1:
    role: 中型企业的优化 / 数据科学 / 算法工程师
    salary_range: ¥5K-50K 月薪（个人贡献者）
    technical: Python + cURL + OpenAPI
    monthly_need: 5-50 次决策计算
    market_size: 中国 ≈ 30-50 万人（IDC 中国数字化转型报告口径估算）
  why_now:
    - LLM 解析建模 (OptiMUS-0.3 学术 89% / 生产 60-70%)
    - 开源求解器 HiGHS MIT 2024 反超 SCIP
    - 时序基础模型 Chronos/TimesFM/Lag-Llama Apache 开源
    - LLM 价格 DeepSeek = GPT-5.1 的 1/30
    - 合规 AIGC 备案 6-12 月成为事实壁垒
    - 课题组算法积累待变现
  moat_four_layers:
    short_M1_M2: 中文本地化
    mid_M3_M6: AIGC 备案壁垒 + 课题组学术联盟
    long_M6_M9: 数据飞轮 + Provider 双边网络
    mindshare: 课题组血统 + 中文一手品牌
  hard_rules:
    - 公司主体 M0 第 1 周注册
    - 算法许可白名单 hard rule
    - 排他融资条款一律拒绝
    - 2027-29 拒绝中等估值 exit
    - Marketplace 启用 ≥ 月营收 ¥40 万
    - P0 安全事故 24h 内公开 Postmortem
  anti_tp_lessons:
    - 复现凭证 Hero 删除，移到 /academic
    - 教育版下调（永久 2K/月，不是 5K/月）
    - 不把"中文一手"当长期壁垒
    - 双语 v1 取消，仅中文起步
---

# Product Requirements Document — 通用优化与预测服务网站

**Author:** 课题组
**Date:** 2026-05-16（v1）/ 2026-05-17（v1.1 /bmad-edit-prd 回写）
**Status:** ✅ **COMPLETE (Step 12 / 12 — PRD v1 finalized 2026-05-17) + v1.1 edit applied 2026-05-17**
**Version:** **v1.1**（77 → 78 FR；新增 E11 Console Excel + FG1.1/1.2/1.3 Critical 升级）
**Source:** 基于 `网站方案.md` v0.5.1（22 章 + 5 附录）转 BMad PRD 标准结构

---

> **TLDR**（30 秒）：OptiCloud 把 Gurobi / TimeGPT / OptiMUS 三件事合一，让中国 50 万优化工程师月成本从 ¥5,000 砍到 ¥6。v1 团队 5 人 / 52 周 / 标准档 ¥248 万；M5 月营收 ¥4 万触发商用、v2 月营收 ¥40 万触发 marketplace。三大风险：NL 准确率 / AIGC 备案 / 自研算法自查。

## Executive Summary

**OptiCloud（项目代号，品牌名 M0 内定）** 让中型企业的优化 / 数据科学 / 算法工程师，把 2 周的工程项目变成 30 秒的 API 调用。

**60 秒画面**：你昨晚还在用 Python 调 OR-Tools 求 500 客户 VRPTW，今晚用 cURL 一行调 `POST /v1/optimize/vrptw`，5 秒后拿到带置信带的最优路径与 NL 解读。月成本 ¥6 起，比 Gurobi 一年许可少一个数量级。

**真问题**：30 年优化与预测学术成果累积，但据 [Gartner 2023](https://www.gartner.com/) **76% 供应链规划仍以 Excel 为主**——算法用不起（Gurobi 商业许可 ≥¥5,000/月）、用不动（自部署 + 求解器配置门槛）。

**目标用户**：v1 主力为国内规上 + 限上企业（约 150 万家）的优化 / 数据科学 / 算法工程师（IDC 中国数字化转型报告口径估 30-50 万人，月薪 ¥5K-50K，能写 Python、调 cURL、读 OpenAPI）。预估月需求 5-50 次决策计算。M2 起扩学者 + 学生；M3 起经分析师授权扩业务人员。

**Hero 主张**："让算法走出实验室"（Landing 页 / 营销文案详见 §UX）。

### Goals

- **Primary（M5 商用退出条件，详 Epic 拆分见 Step 6）**：
   1. ≥1 SKU 端到端跑通（M1 `opt.lp.solve` via HiGHS）
   2. Chat MVP + gVisor 沙箱（M2）
   3. Credits 计费 + 订阅支付（M2）
   4. 中文 UI（M1）
   5. 商业 KPI：M5 月营收 ≥¥4 万 + 月活付费 ≥50

- **KPI 占位**（详见 § Success Criteria）：
   - 注册→首次成功 ≤ 24h
   - 月留存 ≥ 35%
   - NPS ≥ +20
   - AIGC 备案完成日（hard gate）
   - free-to-paid 转化 ≥ 2%

- **Secondary**：M3 前完成 AIGC 备案，M5 前接入 ≥1 个外部 Provider、≥2 所高校合作。

- **Non-Goals (v1)**：不自托管 LLM、不做全 7 种结果形态、不做私有部署、不开 Marketplace 双边市场（月营收 ¥40 万后 M9+ 启用）。

### What Makes This Special

**国内首个**把 NL→Model + 多源 Provider + 订阅市场三件事合一的产品。四个能力（LLM 建模 / 开源求解器 / 开源时序基础模型 / 廉价中文 LLM）2025-2026 **同时成熟**首次让此组合具备商业可行性（详见 §3 Why Now & Moat）。

**护城河**：短期中文本地化、中期 AIGC 备案壁垒 + 课题组学术联盟、长期数据飞轮 + Provider 双边网络。

## Glossary（关键术语）

| 术语 | 定义 |
|---|---|
| **Capability Contract** | § Functional Requirements 锁定声明 — 未列入任何 stage 的能力 v1-v3 路线图不实现 |
| **Critic Agent** | Innovation #1 核心 AI 层；二次校验 SaaS 化；置信度 < 0.6 自动标记 + 转人工 |
| **Hard Rule** | 6 条融资 + 工程合规约束（M0 主体 / 算法许可 / 排他 / Exit / Marketplace / Postmortem）|
| **Reproducibility Voucher** | 学术复现凭证；格式 `repro-{YYYY}-{6 位 base32}`；5 年 SLA + 自动迁移 |
| **Provider** | 算法接入方（自研 / 合作课题组 / 商业 / 开源 Runner 4 类）|
| **Stage** | v1 必上 / v1 末 / v2 / v3 路线图标签（详 § Functional Requirements）|
| **§22 精简档** | v0.5.1 §22 预算 3 档之一（精简档 ¥114 万 / 标准档 ¥248 万 / 扩展档 ¥400 万；12 月预算）|
| **AIGC 备案 hard-gate** | 国家网信办备案号官网可查；M3 末截止，含三级 fallback（M3/M5/M7）|
| **决策智能协议层** | 战略愿景：2026-2030 窗口内成为中文世界的决策智能协议层 |
| **76% Gartner 数据** | Gartner 2023 报告"76% 供应链规划仍以 Excel 为主"（统一表述）|
| **ITADN / AQGS / Trust-Tech / CPSOTJUTT** | 课题组论文算法（详 `papers/` 三个 README）|
| **DeepSeek-V3.5 / Qwen-Max** | v1 主路径 LLM（DeepSeek）+ incident 应急 fallback（Qwen-Max）|
| **HiGHS / OR-Tools / Chronos / TimesFM / Lag-Llama** | v1 开源求解器 + 时序基础模型（MIT / Apache 2.0）|
| **gVisor 沙箱** | LLM Coder 输出隔离执行环境（CPU/Mem/Net/FS 限制 + 90s 硬超时）|

---

## Project Classification

> 工程级分类，在 § Executive Summary 战略层之后固化；下游 § Success Criteria 把分类项转为可测 KPI。

| 维度 | 值 |
|---|---|
| 项目类型 | `api_backend` 主，`web_app` 副 |
| 演进路径 | M1: api+web(简) → M3: +web(Chat, AIGC-gated) → M4: +saas_b2b → M5+: +marketplace |
| 业务领域 | `scientific` × `decision_intelligence`；8 个横向 vertical |
| 复杂度 | 外部 medium / 内部 high（6 条强制约束）|
| 项目上下文 | greenfield；v0.5.1 22 章 + 5 附录已就位 |

**关键 specialFlags**：`aigc_filing_hard_gate`、`compliance_parallel_to_pmf`、`level_2_security`、`multi_tenant_isolation`、`reproducibility_required`、`sandbox_execution_critical`、`bilingual_i18n(v1 仅中文)`、`two_sided_marketplace(M5+)`

### Constraints & Status

**Hard Rules 6 条**（融资 deck + 工程合规）：
1. 公司主体 M0 第 1 周注册
2. 算法许可白名单 hard rule（MIT/Apache/BSD/EPL；PR 自动检查）
3. 排他融资条款一律拒绝
4. 2027-2029 拒绝中等估值 exit
5. Marketplace 启用 ≥ 月营收 ¥40 万
6. P0 安全事故 24h 内公开 Postmortem

**自研算法 License**：Apache 2.0（课题组已接受）；5 个自研算法须通过附录 E.4 自查 5 项才能 v1 上线。

**项目状态**：M0 立项阶段；v0.5.1 §22 提供 ¥114-400 万 3 档预算路径。

### Top Risks

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| R1 | NL→Model 生产准确率 | 目标 60-70%（v1 实证），低于学术 89% | Critic agent + 低置信转人工 + M1-M2 Chat 仅辅助 |
| R2 | AIGC 备案延期 | 阻塞 Chat 主入口公开访问 | M0 第 1 周启动、中介加速、API 入口先行 |
| R3 | 自研算法代码自查未通过 | v1 SKU 退化为开源等价物 | v0.5.1 §4.5 5 项门槛 + Apache 2.0 + v2 替换路径 |

### For LLM Agents（结构化引用块）

```yaml
project:
  codename: OptiCloud
  stage: M0
  product_types: [api_backend, web_app]
  primary_persona: optimization_engineer_at_midsize_co
  market_size_estimate: 30000-500000
primary_goals_M5:
  - sku_end_to_end: opt.lp.solve_via_HiGHS
  - chat_mvp_with_gvisor_sandbox
  - credits_billing_and_subscription
  - chinese_ui
  - monthly_revenue_40k_cny
  - paying_mau_50
kpi_anchors_for_step3:
  - first_success_within_24h
  - monthly_retention: ">=35%"
  - nps: ">=20"
  - aigc_filing_complete_date
  - free_to_paid_conversion: ">=2%"
hard_rules:
  - m0_entity_register_wk1
  - license_whitelist
  - no_exclusive_funding
  - no_mid_valuation_exit_2027_29
  - marketplace_gate_400k_arr
  - p0_postmortem_24h
top_risks:
  - {id: nl_accuracy, mitigation: critic_agent_plus_human_review}
  - {id: aigc_delay, mitigation: m0_kickoff_plus_intermediary}
  - {id: in_house_algo_audit_fail, mitigation: open_source_fallback_plus_v2_replace}
```

## Success Criteria

> 把 § Executive Summary 的 Goals 转为可测试 KPI；为 § Project Scoping & Phased Development 提供 hard-gate 阈值。

### User Success（用户成功，"worth it" 时刻）

| 指标 | 阈值 | 反博弈定义 |
|---|---|---|
| **注册 → 首次成功** | ≤ 24 h | 用户**自助完成**，无人工介入 |
| **24h 留存率** | ≥ 60% | = 24h 内第二次调用用户 / 首次成功用户 |
| **结果可解释率** | ≥ 80% | = NL Summary 调用 / API 成功调用（SQL 可查）|
| **月留存**（注册第 30 天）| ≥ 35% | DAU/MAU 类口径 |
| **NPS** | ≥ +20 | 公测后 60 天，**随机采样 + 回收 ≥ 30%** |

> ⚡ **M3 末 hard-gate**：**24h 留存 ≥ 60% AND NL Summary 调用率 ≥ 80%**；未达成则**不进入 M4 公测**，团队回炉迭代。

**主要受众**（v1 工程师 / 数据分析师）：
- "5 分钟从注册到第一次 API 成功" — 与 Stripe/Twilio onboarding 时间持平
- "调用一次的成本 < 一杯咖啡（¥6）" — 心理免门槛
- "结果直接可粘到 Slack / 钉钉给同事看" — NL Summary 即开即用

### Business Success（商业成功）

| 时间 | 付费 MAU | 月营收 | LTV/CAC | 重复付费率 |
|---|:---:|:---:|:---:|:---:|
| M3 末 | — | — | **≥ 1.5** | — |
| M4 末（公测）| ≥ 20 | ≥ ¥5K | ≥ 1.5 | ≥ 50% |
| **M5 末（商用）** | **≥ 50** | **≥ ¥4 万** | ≥ 1.8 | **≥ 60%** |
| M7 末 | ≥ 200 | ≥ ¥18 万 | ≥ 2.2 | ≥ 65% |
| **v2 末（M13）** | ≥ 500 | **≥ ¥40 万** | **≥ 3.0** | ≥ 70% |

**核心商业指标**：
- **Free → Paid 转化 ≥ 2%（90 日窗口）**
- **付费用户定义**：当月累计扣费 ≥ ¥10（过滤试探性支付）
- **重复付费率 ≥ 60%（M5 hard-gate）** — 防灌水
- **LTV/CAC ≥ 1.5（M3 起）→ 3.0（v2 末）** — DD 必备
- **毛利率（双口径）**：Variable 99%（仅算 LLM/GPU/带宽 + 算法核心）/ Fully-loaded 30-40%（含人力 + 固定基础设施分摊）
- **Burn Multiple ≤ 1.5（v2 末）**
- **高校合作定义**：师生用户 ≥ 50 且持续 ≥ 3 个月（M5 前 ≥ 2 所；M7 前 ≥ 3 所）

### Technical Success（技术成功，SLO + SLA）

**API 延迟**：
- API 网关 P95 < 200 ms（M3 起）
- Chat 首 Token：**P50 < 1.5 s，P95 < 3 s**（M3 起，受 DeepSeek API 上限约束）
- Chat 流式吞吐 ≥ 20 Token/s（M3 起）

**求解 SLO（分级）**：
- LP/QP < 100 vars: P95 < 1s
- LP/QP < 10K vars: P95 < 5s
- VRPTW < 100 客户: P95 < 30s
- VRPTW ≥ 500 客户 或 MINLP: **自动转异步**，结果通过站内消息回传

**异步任务**：排队 P95 < 30 s（M3 起）

**SLA**（**v1 期间尽力而为，M7+ 正式承诺**）：

| 计划 | v1（M1-M6）| v1.5（M7+）|
|---|---|---|
| Free | 尽力而为 | 尽力而为 |
| Starter | 尽力而为 | 99.0% |
| Pro | 尽力而为 | 99.5% |
| Team | 尽力而为 | 99.9% |

> v1 上限受单云区 + 单 LLM（DeepSeek，SLA 99.5%）依赖，理论可用性 ≤ 99.2%；M7+ 多 LLM 多云后升级承诺。

**DR 与安全（M3 起生效）**：

| 指标 | 目标 |
|---|---|
| **RTO（恢复时间目标）** | ≤ 4h（单 region 故障后服务恢复）|
| **RPO（数据丢失目标）** | ≤ 15 min（Postgres WAL + 跨区复制）|
| **关键漏洞响应**（CVSS ≥ 7.0）| ≤ 24h 补丁部署 |
| **次要漏洞响应**（CVSS 4-6.9）| ≤ 7 day |
| **数据删除 SLA**（PIPL）| ≤ 7 day（软删 + 硬删）|
| **依赖库扫描** | 周扫 + 高危 24h 修 |

**AIGC 备案 progressive milestones + fallback**：

| Milestone | 截止 | 行动 |
|---|---|---|
| 受理回执 | ≤ M1 末 | 中介签约 + 材料提交 |
| 中段反馈 / 整改完成 | ≤ M2 末 | 整改 + 复审 |
| 备案号官网可查 | **≤ M3 末** | Hard gate |
| **⚠️ Fallback** | M3 末未拿到 | 启用 **API-only 公测**，Chat 内部 dogfood，按月评估 |

**合规与安全**：
- **P0 安全事件**：≤ 1 起/季度，且 24h 内公开 Postmortem 履约 100%
- **0 重大 P0 安全事件**（沙箱泄漏 / 数据外泄 / 资金账本错误）
- **计费对账误差**：0（双写账本 + 每日扫差，M2 起）

**自研算法代码自查（v0.5.1 §4.5 / 附录 E.4）**：

| 自研算法 | 自查 5 项 | M1 KPI |
|---|---|---|
| AQGS-ACOPF / Trust-Tech / CPSOTJUTT / TT-KMeans / ITADN-AIGC | Python 包 / pip install / Apache 2.0 / 最小示例 / 复现结果 | **M1 末 ≥ 3 个自查通过**（其余走 v2 替换路径）|

**团队 KPI（内部，不对外）**：

| 指标 | 目标 | 监控周期 |
|---|---|---|
| 团队月留存 | ≥ 95%（不含主动调岗）| 每月 |
| Sprint Velocity | ≥ 80% baseline（M1 末 baseline 锁定）| 每 Sprint |
| 加班指数 | ≤ 20%（周末/晚 9 后工时占比）| 每 Sprint |

### Measurable Outcomes（时间盒里程碑总览，含 hard-gates）

| 时间 | 必达 | 备注 |
|---|---|---|
| **M0 wk1** | 公司主体注册启动 + AIGC 备案中介签约 | Hard Rule #1 |
| M1 末 | 自研代码 ≥ 3 个自查通过 / AIGC 受理回执 | G2/G8 双 KPI |
| M2 末 | 4 个 SKU + Chat MVP + Credits 基础 + 沙箱 + 中文 UI / AIGC 中段反馈 | 进入内测 |
| **M3 末 hard-gate** | **24h 留存 ≥ 60% + NL Summary ≥ 80%** **AND** **AIGC 备案号官网可查**（或启 fallback）| G1 + G2 |
| M4 末 | 公测付费 ≥ 20 / 月营收 ≥ ¥5K / 重复付费率 ≥ 50% / LTV/CAC ≥ 1.5 | M5 商用准入 |
| **M4.5** | **GTM 准备**（详见 Step 11 Roadmap）| 占位 |
| **M5 末** | 付费 ≥ 50 / 月营收 ≥ ¥4 万 / NPS ≥ +20 / **重复付费 ≥ 60%** / LTV/CAC ≥ 1.8 / 加油包+退款+对账齐 | 正式订阅开启 |
| M7 末 | 付费 ≥ 200 / 月营收 ≥ ¥18 万 / 高校 ≥ 2 / SLA 升级 99.0-99.9% | Pro+ 完整 |
| **v2 末** | 月营收 ≥ ¥40 万 → marketplace 启用 / Burn Multiple ≤ 1.5 / LTV/CAC ≥ 3.0 / 重复付费 ≥ 70% | 双边市场上线 |

---

## Product Scope

> ⚠️ **本节内容已迁移到 § Project Scoping & Phased Development**（含 MVP Strategy / Resource 三档 / Phase 1-3 / Risk Mitigation）。
>
> 此处保留简表索引：
> - **MVP**（M0-M5）：4 SKU + Chat MVP（AIGC gated）+ 29 端点 / 13 精简端点 + 中文 UI + Credits 三件套 + 合规底盘
> - **Growth**（M5-M9）：Webhook + 教学模式 + Classroom + Provider 接入 + Pro+ SLA
> - **Vision**（M9+）：自托管 LLM + Marketplace + 多语种 + 私有部署 + 行业模板扩展

### MVP — M1-M5 必交付（详 § Project Scoping）

**核心闭环（must-have）**：

1. **SKU 端到端**：M1 `opt.lp.solve` via HiGHS；M2 扩 `opt.vrptw` / `pred.ts.arima` / `pred.ts.lstm`（共 4 个）
2. **Chat MVP**：SSE 流式 + DeepSeek API + 4-Agent (Formulator/Planner/Coder/Critic) + gVisor 沙箱
3. **Credits 计费（拆为两阶段）**：
   - **M2 基础**：注册 / API Key / Credits 余额 / 订阅支付
   - **M5 完整**：加油包 / 退款 / 月度对账
4. **中文 UI**：Landing / Console / Docs / Pricing / Billing
5. **结果交付（仅 3 种）**：JSON + Dashboard + NL Summary
6. **合规底盘**：ICP、等保二级；**AIGC 备案为外部依赖时间盒，不算工程 deliverables**
7. **公司主体**：M0 wk1 注册
8. **安全沙箱**：gVisor 隔离 LLM Coder 输出
9. **运维基础**：双写账本 + 24h Postmortem 流程 + Vault Secret + pgvector
10. **M4.5 GTM 准备**：定价页 / 案例 / 销售素材 / 客服话术

**明确不做 v1**：自托管 LLM / PDF/Webhook/Widget / 私有部署 / Marketplace / Provider Console 完整版 / 无代码工作流 / 新手模式 / 全栈英文

### Growth — M5-M7+ 竞争壁垒

**post-MVP 扩展**：
- 第 5-8 个 SKU（含 1 个深度行业模板：**物流**或能源任选）
- Webhook 回调 / PDF & Word 报告
- 教学模式 + 经典算例库（IEEE 9-bus / CVRPLIB / OR-Library 各 ≥ 5 个）
- Classroom Plan（5-200 学生账号 / 共享 Credits）
- Provider 接入扩展（≥ 3 外部 Provider）
- 公开 AI 评估面板 + 复现凭证 GA
- Pro+ SLA 99.5% 对外承诺生效

### Vision — v2-v3 未来形态

**长期愿景**（不在 v1 范围）：
- 自托管 N1-N3 本地 LLM（GPU 集群启动条件：月活付费 ≥ 500）
- 完整 7 种结果形态（+ Embed Widget + 完整 Chat 追问）
- 全栈双语（中英文）+ 海外节点
- 私有部署 / On-Prem / 学校机房
- **Marketplace 双边市场启用**（月营收 ≥ ¥40 万 hard-gate）
- Provider 完整 Console + 路由透明 + 自动 BibTeX 引用追踪
- 数据飞轮回训 + Critic agent 智能进化
- 第二、第三个深度垂直行业模板
- "决策智能协议层" 战略愿景兑现（B-D 阶段融资支撑）

## User Journeys

> 11 个故事覆盖关键用户角色；为 § Domain Requirements / § Functional Requirements / § Non-Functional Requirements 提供能力锚点。每个 Journey 标注 `stage`（v1 必上 / v1 末 / v2 / v3）+ 双栏（系统行为 vs 用户感受）。

### Journey 1（v1 主场景）：物流主管李工，从 Excel 到 cURL

**画像**：李工，28 岁，江苏中型电商物流主管，月薪 ¥22K，计算机本科毕业 5 年。
副线 persona：直属老板 **刘总，50 岁**，懂业务不懂算法。
`stage: v1 主场景`

| 阶段 | 系统行为（可测）| 用户感受（不可测）|
|---|---|---|
| 开场 | — | 周一晨会被点名油费同比涨 8% |
| 铺垫 | 公众号 → Landing → 注册 3 min → API Key + inline cURL/Python/Node 示例 → Onboarding Wizard 5 步引导 → 复制 cURL → 粘 200 单 JSON | *Think*: "Gurobi 太贵自己不会装，万一不灵让我背锅" *Say*（钉钉）: "刘总，我下午跑个试" |
| 高潮 t=5s | HTTP 5 秒返回 raw JSON 路径 + 置信带（API SLO ✅）| — |
| 高潮 t=5-7s | Dashboard 渲染完成，路径图可视化 | — |
| 高潮 t=7-10s | NL Summary 流式贴回："建议派 18 辆车，瓶颈在仓库 C" | 心跳加速："这玩意儿真的工作" |
| 次日 | 跑全天 200 单 → 月底油费降 ¥8.4K | 刘总："你这玩意儿能省钱我加大支持" |
| 收尾 | 第 14 天 Starter ¥39，第 60 天 Pro ¥299 | 推荐 3 名同事 |

**关键摩擦点保险**：注册后 30 min 未跑通 → 自动弹主动客服 Modal。

**揭示能力**：注册 / API Key / Onboarding Wizard / inline 代码示例 / 主动客服 Modal / SKU 端到端 / Dashboard / NL Summary 流式 / 订阅升级。

---

### Journey 2（v1 主场景）：数据分析师 Lina 的错误恢复

**画像**：Lina 张分析师，28 岁，某零售连锁数据分析师。
`stage: v1 主场景`

| 阶段 | 系统行为 | 用户感受 |
|---|---|---|
| 开场 | 上传 30 SKU × 24 月 CSV（表头中英混杂）| 想试 Foundation Model 预测 |
| 铺垫 | 3 秒内友好错误 + 模板下载 → 改正重试 → 跑 Chronos | *Feel*: 从挫败到惊喜 |
| 高潮 | Modal: "调用 P5（k=12×）高单价层，预估 200 Credits = ¥2。继续？[继续][切换 P3 LSTM 30 Credits]" | "原来这是高单价层" |
| 高潮续 | Free 1K 告罄 → Modal "¥10 加油包 + 永不过期" → Stripe 3 秒完成 | — |
| 收尾 | 预测对比 baseline 减 15% 误差 | *Say*（Notion）："月降库存 ¥45K" |

**Credits 分桶 Dashboard**（v1 上线即有）：
```
┌─ 月度赠送 700 / 1,000（30 天到期）
├─ 注册一次性 4,800 / 5,000（永不过期）
├─ 教育版 — / —
└─ 加油包 — / —
```

**Credits 竞态测试 5 case**：余额 1000/100/50/10/0~负值，Modal/警示/阻止行为各异。

**揭示能力**：数据校验 + 友好错误 / 模板下载 / P5 调用前警示 / Credits 分桶 / 一键加油包 / Top-K 单价表。

---

### Journey 3（v1 末，M5+ 真实流量触发）：王哲 SRE 的午夜 incident

**画像**：王哲，27 岁，OptiCloud 团队 SRE。
`stage: v1 末（M5+ 才有真实流量触发）`

> ⚠️ LLM 路径明示：**v1 主路径 = DeepSeek 单一**；Qwen-Max API 仅作 **incident 应急通道**（≥30 分钟不可用触发手动切换），**不计入正常 SLO**。

| 阶段 | 系统行为 | 用户感受 |
|---|---|---|
| 开场 03:12 | 钉钉报警："Provider Health → DeepSeek 探活失败 5min" | *Think*: "妈的又来 ... Postmortem SOP 是我自己写的" |
| 开场续 | Grafana `chat_success_rate` 99.2% → 76% | *Say*（爱人）: "工作 30 分钟，别等我" |
| 铺垫 | SSH → log → DeepSeek 限流确认 → **手动触发紧急 fallback** → 3 min 切 Qwen-Max | — |
| 高潮 | 12 min / 87 用户受影响 → status.opticloud.cn "Investigating" 公告 → 4h 后 Postmortem 草稿 → **24h 内公开发布** | — |
| 收尾 | 3 工单按补偿处理 → V2EX 80 人赞 → 30 天 NPS +3 | — |

**Incident 自动化 SLA**：
- Provider 探活失败 → 主动告警 ≤ 30s
- P0 触发 → Postmortem 模板自动生成（含时间线骨架）
- 状态页公告自动发布 ≤ 1min

**揭示能力**：监控告警 / Provider Health / 路由 fallback（incident 应急）/ Status Page / 24h Postmortem / 自动 Credits 退款 + 20% 补偿。

---

### Journey 4（v1 部分 / v2-v3 大部分）：吕教授 + 小赵的算法变现

**画像**：吕教授（某高校能源系，课题组成员）；**小赵研一**。
`stage: v1 部分（自查 + Classroom 占位）；v2-v3 大部分`

- **铺垫 v1**：M1 末小赵教育邮箱注册 → Starter 永久免费 2K Credits/月 + Pro 30 天体验。
- **铺垫 v2**：吕教授签 Provider 合约 → OpenAPI + Docker + 离线评测 → 14 天 shadow 验证 → 灰度 5%→50%→100%。
- **高潮（v2-v3）**：AQGS SKU 上线 → 小赵跑 `opt.energy.acopf.aqgs` mode=teaching → **本科入门用 6-bus，研一期末用 9-bus** → 自动 BibTeX + Notebook（Colab 一键）+ 复现凭证 `repro-2027-A3F7K2`。
- **副线（M9 后预埋）**：1 年后小赵投另一篇 paper 引用 `repro-2027-A3F7K2`，发现 Provider 已退出 → 触发 **5 年 Repro SLA**：
  - Image 归档自动取回（≤24h）
  - 失败时**自动迁移到等价 Provider**（基于 capability 词表匹配）
  - 若无等价物则**人工复现**（≤14 天，Team+ 免费 / 免费用户 ¥500/次）
  - Provider 退出 **30 天预通知 SLA**（邮件 + 站内信 + 站点公告）
- **收尾**：吕教授月度分润 ¥820 → 课题组招到 2 名研究生 → 2 篇论文成功引用。

**揭示能力（按 stage 分层 + Auto/Manual + 团队规模）**：

| 能力 | v1 | v2 | v3 | Auto/Manual | 团队 ≥3 / =2 / =1 |
|---|:---:|:---:|:---:|:---:|:---:|
| 自研代码自查 §4.5 | ✅ M1 | | | M | 必做 |
| Classroom Plan 占位 | ⚠️ 设计 | ✅ 落地 | | M | 必做 |
| Provider 接入（合约/shadow/灰度）| | ✅ Manual | ✅ Auto | M→A | ≥3 必 / ≤2 跳过或同行评审 |
| 教学模式 + Notebook + Colab | | ✅ | | A | 全规模 |
| BibTeX 强制 / 复现凭证 | ✅ M5 | ✅ 完整 | | A | 全规模 |
| 经典算例库 IEEE 9/30/118 等 | | ✅ M5+ | | A | 全规模 |
| Provider 分润月结 | | ✅ | | A | 全规模 |
| **Repro 5 年 SLA + 自动迁移** | | ✅ | ✅ | A | 全规模 |

---

### Journey 5（v2 主场景）：陈架构师的 2 天集成

**画像**：陈架构师，某零售 SaaS 公司，月薪 ¥50K。
`stage: v2 主场景`

- **开场**：客户问"动态定价啥时候上"。市场部承诺 Q3 上线，工程评估 **8 周**。
- **铺垫**：3 家求解器供应商 ≥¥50K/年；PyPSA 开源试跑 5 天，不支持业务场景。崩溃。
- **高潮**：周五凌晨 **V2EX** 刷到 OptiCloud → 注册 → 复制 cURL → ¥6/次起 → **周末 2 天集成** → 周一演示。
- **副线（M3 末实际发生）**：法务质问 PIPL → 陈在 Docs 找到：
  - **法务问答库**（PIPL / GDPR / 等保 2.0 / 数据出境 pre-built FAQ）
  - **数据流图模板**（一键下载）
  - **数据出境承诺函**（盖章版 PDF 一键生成）
  - **Team+ 计划 24h 法务问询 SLA**（人工回邮 + 必要时 Zoom）
  - 法务 24h 内通过，集成方案保住
- **收尾**：客户上线即用 → 月调用 5K 次 → 陈月支付 ¥3K，向客户收 ¥30K，毛利 90%。

**揭示能力**：OpenAPI 3.0 / Python SDK / Webhook（v2）/ 速率限制 / Team plan / 法务问答库 / 数据流图模板 / 出境承诺函 / 24h 法务 SLA / customer story 营销。

---

### Journey 6（流失复盘 — 1 预填 + 4 TBD）

**预填 #1（来自 Customer Support Theater 揭示）**：
> **D0 流失最大单因素 = onboarding 30 分钟未跑通**
> - 信号：注册→首次成功 > 30 min 的用户 90 日内复购率 < 0.5%
> - 缓解：Onboarding Wizard + inline cURL + 主动客服 Modal（5min 卡住即弹）
> - 评估指标：M3 末数据回填后，验证此假设

**TBD #2-#5**（M3 末公测后真实访谈填入）：D7 流失原因 / D30 流失原因 / 付费 1 月流失原因 / 注册后未调用 API 跳出原因。

---

### Journey 7（v1 必上）：风控冻结申诉

**画像**：小张，用同一手机号注册了 3 个 Free 账号。
`stage: v1 必上（第 1 天可能触发）`

**风控冻结条件**（任 2 项成立）：
- 设备指纹相似度 ≥ 0.9
- IP 同 /24 段
- 24h 内调用 ≥ 20 次
- 支付方式重复使用
- 手机号已注册 ≥ 1 账号

- **开场**：第 4 次注册被风控拦截 → 友好提示
- **铺垫**：申诉"我帮室友注册" → 触发**人工复核**（48h SLA，团队 ≥3 时）/ 自动评分复审（团队 ≤2 时）
- **高潮**：复审维持原判 → 给小张**账号合并提议**（保留 1 个）
- **收尾**：小张接受合并 → 升 Starter ¥39

**揭示能力**：风控规则文档 / 申诉表单 / 48h 复审 SLA / 自动评分复审 / 账号合并工具。

---

### Journey 8（v1 必上）：AIGC / 网信办首次巡查

`stage: v1 必上（合规应急 Runbook 锚点）`

- **触发**：M5 末某日，网信办抽查 Chat → 发现某 SKU NL Summary 含违规营销话术。
- **铺垫**：合规团队 4h 内召集（团队 ≥3）/ 主创 + 中介合规顾问 24h 响应（团队 ≤2）→ 导出涉嫌 sample → 自查发现 Critic agent 未拦截。
- **高潮**：24h 内整改：① Critic prompt 加强 ② 敏感词二级过滤 ③ 暂停涉嫌 SKU 2 周复核 → status 公告。
- **收尾**：整改通过 → 备案号未受影响 → 累积 SOP。

**Critic Red Team 测试集**：
- M3 前 ≥ 30 个边界 prompt
- M5 前 ≥ 200 个
- v2 起众包扩展（白帽奖励 ¥10/prompt）

**揭示能力**：合规函调流程 / Critic prompt 管理 / 敏感词过滤 / SKU 暂停+复核 / 状态页公告 / 累积合规 SOP / Critic Red Team 测试集。

---

### Journey 9（v1 必上，第 1 天可能触发）：白帽研究者的负责任披露

**画像**：阿七，自由安全研究者。
`stage: v1 必上`

- **开场**：扫到 `/api/v1/*` 端点，看到 `security.txt`
- **铺垫**：发现 endpoint 漏洞 → 邮件 `security@opticloud.cn`
- **高潮**：48h 内回信 → 7 天内修复 → ¥500-2,000 奖励（按 CVSS）→ 公开致谢页
- **收尾**：阿七博客评测"安全响应满分"→ 间接 GTM

**揭示能力**：security.txt / 漏洞披露邮箱 / 48h 响应 SLA / 7 天修复 SLA / 白帽奖励 / 致谢页 / 自动 CVE 跟踪。

---

### Journey 10（v1 末填）：媒体记者评测 — placeholder

**预设维度**：Press Kit / 1 句话定义 / Logo & 品牌资产下载 / 60s Demo 视频 / customer story 链接 / 创始团队访谈 SLA。

---

### Journey 11（v1 末填）：投资人 DD 数据访问 — placeholder

**预设维度**：Data room 入口 / 公开 evaluation report（NL→Model 准确率 / SLO 履约 / Burn Multiple）/ 团队访谈 SLA（48h 内安排）/ SLA 履约记录历史。

---

### Journey Requirements Summary（按 v1 / v2 / v3 + Auto/Manual + 团队规模）

| 能力组 | v1 | v2 | v3 | A/M | 团队 ≥3 / =2 / =1 |
|---|:---:|:---:|:---:|:---:|:---:|
| 注册 / API Key / 双因素 | ✅ | | | A | 全 |
| **Onboarding Wizard / inline cURL / 主动客服 Modal** | ✅ | | | A | 全 |
| Credits / 订阅 / 加油包 | ✅ | | | A | 全 |
| **Credits 分桶 Dashboard / P5 警示 / Top-K 单价表** | ✅ | | | A | 全 |
| SKU（LP/VRPTW/TS/Pricing 共 4 个）| ✅ | + 4-6 | + 行业模板 | A | 全 |
| Chat NL→Model（M3+，DeepSeek 主路径 + Qwen-Max 应急 fallback）| ✅ | 完整 | | A | 全 |
| Dashboard / NL Summary 流式 | ✅ | | | A | 全 |
| 数据校验 / 友好错误 / 模板 | ✅ | | | A | 全 |
| 监控 / Provider Health / Status Page | ✅ | | | A | 全 |
| 24h Postmortem 流程 | ✅ M5 | | | M | ≥3 必 / ≤2 用模板 |
| 自动 Credits 退款 + 20% 补偿 | ✅ M5 | | | A | 全 |
| Provider 接入（合约/shadow/灰度）| | ✅ Manual | ✅ Auto | M→A | ≥3 必 / ≤2 跳过 |
| 教学模式 / Notebook / Colab | | ✅ | | A | 全 |
| BibTeX / 复现凭证 / **Repro 5 年 SLA + 自动迁移** | ✅ M5 部分 | ✅ 完整 | | A | 全 |
| 经典算例库 | | ✅ M5+ | | A | 全 |
| Provider 分润月结 | | ✅ | | A | 全 |
| Classroom Plan | ⚠️ 设计 | ✅ 落地 | | M | 全 |
| Webhook 回调 | | ✅ | | A | 全 |
| 多语言 SDK | ✅ Python | + Node/Go | | A | 全 |
| Customer story 营销 | | ✅ M5+ | | M | 全 |
| 风控（指纹 / IP / 申诉 / 复审 / 合并）| ✅ | | ✅ Auto v3 | M→A | ≥3 必 / ≤2 自动评分 |
| **法务问答库 / 数据流图 / 出境承诺函 / 24h 法务 SLA** | | ✅ Team+ | | M | ≥3 必 / ≤2 中介 |
| 合规应急（Critic 红队 / 敏感词 / SKU 暂停 / SOP）| ✅ | | | M | ≥3 必 / ≤2 中介合规顾问 |
| **白帽：security.txt / 48h 响应 / 7d 修复 / 致谢页 / 奖励** | ✅ | | | M | 全 |
| **Press Kit / Demo 视频 / DD Data room**（M1 末 placeholder）| ✅ M5 末 | | | M | 全 |

## Domain-Specific Requirements

> 行业 / 合规 / 技术约束 / 集成需求 / 8 个垂直行业模板；为 § Functional Requirements / § Non-Functional Requirements 提供约束条件。

### Compliance & Regulatory（合规与法规）

#### 国内合规（v1 必上）

| 项 | 范围 | 截止 | hard-gate？ |
|---|---|---|:---:|
| **公司主体** | 有限责任公司（高校事业单位不可作 AIGC 备案主体）| M0 wk1 | ✅ Hard Rule #1 |
| **ICP 备案** | 工信部 | M1 末 | ✅ |
| **公安备案** | 网监 30 日内 | M1 末 | ✅ |
| **AIGC 备案**（《生成式人工智能服务管理暂行办法》）| Chat / NL Summary 受此约束；首批备案平均 4-6 月 | M3 末 + **三级 fallback**（见下）| ✅ Chat 主入口 |
| **PIPL 合规** | 法定"及时删除"+ **行业自律 7 day**（不是法定数字）| M2 起 | ✅ |
| **AIGC 内容标识** | 输出加水印 / 标识 | M3 起 | ✅ |
| **等保 2.0 二级** | 网络安全等级保护 | M5 末取证 | ✅ Pro+ |
| **等保 2.0 三级** | Enterprise / Gov / Fintech 客户要求 | **v2 启动评测 / v3 末取证**（测评周期 3-6 月，不可跨级）| 协商 |
| **数据出境安全评估** | **仅当用户主动选 N4 远程国际 LLM（GPT/Claude）时触发**；DeepSeek/Qwen 境内不触发 | 按需 | 按触发 |

#### AIGC 备案三级 fallback

| 阶段 | 触发条件 | 行动 |
|---|---|---|
| Level 1 | M3 末未拿到备案号 | M4 起 **API-only 公测**，Chat 内部 dogfood，不对公众开放 Chat 入口 |
| Level 2 | M5 末仍未拿到 | 暂停所有 Chat / NL Summary 用户可见功能，仅 API 入口，Status 页公告 |
| Level 3 | M7 末仍未拿到 | 严重项目风险，触发课题组会议评估走向（融资 / 转 to-B / 转售）|

#### 海外合规（v2+ 海外站点启用）

- **GDPR**：数据导出 / 可携带性 / 被遗忘权接口
- **CCPA**（加州）：消费者数据权利

#### 行业垂直额外合规（按 vertical 触发）

| Vertical | 额外合规 | 触发条件 |
|---|---|---|
| 能源 / 电力 | NERC CIP 类 + 国网技术规范 | 接入真实 SCADA / VPP |
| 金融 | 银保监 / PCI DSS（如涉支付）/ **国密 SM2/SM3/SM4**（人行手机银行密码学指引）| v3 处理真实金融交易 |
| 医疗 | 卫健委医疗数据保密 + 类 HIPAA | 处理真实患者数据 |
| 政府 | 政采资质 + **国密 SM2/SM3/SM4** + 等保三级 | 政府客户合同 |
| 科研 | 学术 IP / 论文复现性 | 学术联盟客户 |

> v1 **NOT 接入任何上述行业的真实生产数据**，保持 sandbox / advisory only。

### Technical Constraints（技术约束）

#### 安全（v1 必上）

- **🔒 代码执行沙箱**：LLM Coder 输出强制 gVisor 隔离
  - CPU 1 vCPU / Mem 1 GB / Net 禁外网 / FS 只读
  - **沙箱内执行 ≤ 30s 软超时，90s 硬超时强杀**
  - **沙箱外 Provider 调用 ≤ 60s 软超时**
  - **Chat 求解 E2E ≤ 90s 用户感受范围**
  - **gVisor CPU 性能下降 30-50% 已计入 SLO 计算**
- **多租户隔离**：Postgres schema-per-tenant；S3 bucket 命名空间隔离
- **数据加密**：传输 TLS 1.3 / 落盘 AES-256 / 客户端可选客户端加密（Pro+）
- **Secret 管理**：Vault HSM + 双人审批轮换
- **API Key 安全**：仅 hash 入库 / 前缀可见 / 可一键吊销 / 异常地理跨越触发风险评分

#### 隐私（PIPL 落地）

- 用户上传**默认私有**，仅自己可见
- **默认不进训练集**；显式同意可换 Credits 奖励（二次确认）
- 调用日志默认不含原始数据（hash + 元数据）
- 软删 ≤ 7 日（行业自律）→ 硬删（含备份）；PIPL 法定"及时"
- 14 岁以下不可注册；14-18 岁需监护人确认

#### 性能（M3 起生效）

- API 网关 P95 < 200 ms
- Chat 首 Token：P50 < 1.5 s / P95 < 3 s
- 同步求解 P95 分级（详 §13 SLA）
- 异步任务排队 P95 < 30 s
- 计费对账误差 = 0

#### 可用性 / 灾备（M3-M5 起生效）

- RTO ≤ 4h / RPO ≤ 15 min
- 备份：Postgres 实时 WAL + 每日全量 / S3 跨区复制 / Vault HSM
- 关键漏洞 ≤ 24h 补丁 / 次要 ≤ 7 day
- **v1 经验估算 99.2%**（DeepSeek 不发布 SLA，此为估算）；**v1.5 起多供应商后正式 SLA 承诺**

#### 算法许可白名单（hard rule）

仅采用：**MIT / Apache 2.0 / BSD / EPL**（仅调用不 fork 修改）

| License | 状态 | 限制 |
|---|---|---|
| MIT | ✅ 自由 | 无 |
| Apache 2.0 | ✅ 自由 | 自研算法**统一签发** |
| BSD | ✅ 自由 | 无 |
| **EPL**（IPOPT/Bonmin/Couenne）| ⚠️ **仅调用不 fork**；若修改源 → 触发 file-based copyleft，必须开源同许可 | 禁止 fork 修改 |
| **GPL/AGPL** | ❌ 禁用（含 GLPK / ECOS-3+）| AGPL 触发网络使用条款 |
| **ECOS GPLv3** | ⚠️ **v1 备选，需法务确认 SaaS 后端"网络使用"条款**（理论可调用，但谨慎） | 优先用 SCS |
| **SCIP** | ❌ 商用付费 | 学术免费，商用许可需付费购买 |
| 商业（Gurobi / Hexaly / MOSEK）| ❌ 仅用户自带 license | 不直接采用 |

参见 **§4.4 v1 开源库 license + 法务复核状态全表**（待 M1 内补全）。

### Integration Requirements（集成需求）

#### 算法生态依赖

| 类别 | v1 默认 | v1 备用 | v2+ 扩展 |
|---|---|---|---|
| **LLM** | DeepSeek-V3.5（主路径）| **Qwen-Max（incident 应急 fallback，≥30 min 不可用触发手动切换，不计 SLO）** | GPT-5.1 / Claude / 自托管 Qwen-235B |
| **LP/MILP/QP** | HiGHS（MIT）+ OSQP | CBC | Gurobi（用户自带 license）|
| **CP-SAT / VRP / Scheduling** | OR-Tools（Apache）| - | - |
| **凸 NLP / SOCP** | CVXPY + SCS | - | MOSEK（用户自带）|
| **MINLP** | Bonmin + Couenne | - | - |
| **非凸 NLP / 全局** | IPOPT + multi-start | CMA-ES / Optuna | **AQGS（自研）** |
| **元启发式** | PyGAD / pyswarms | DEAP | - |
| **时序统计** | Nixtla statsforecast + statsmodels + Prophet | - | - |
| **经典 ML** | scikit-learn + XGBoost + LightGBM | - | - |
| **DL** | PyTorch | TensorFlow | - |
| **时序基础模型** | Chronos / TimesFM / Lag-Llama / Moirai（开源自托管）| - | TimeGPT（Pro+ 可选透传付费）|
| **异常 / 聚类** | PyOD / ADTK + scikit-learn | - | **TT-KMeans（自研）** |
| **建模框架** | Pyomo + PuLP + CVXPY | - | - |

#### 基础设施依赖

- **云**：阿里云 RDS Postgres + Redis + OSS（主）/ AWS（备份）
- **GPU**：RunPod / AutoDL 按秒计费（v1）→ 自建集群（v2-v3，月活付费 ≥ 500 触发）
- **支付**：微信支付 + 支付宝（国内）+ Stripe（海外）
- **CDN**：阿里云 + Cloudflare 双备
- **邮件**：Resend / Mailgun
- **监控**：Grafana + Prometheus + Loki + OpenTelemetry
- **沙箱**：gVisor（v1 起步）/ Firecracker（v2+ 重资源场景）
- **Vector DB**：**pgvector（v1 起步）→ Qdrant（v2 末迁移）**（容量阈值：月活付费 ≥ 500 + 月度 500K embeddings 触发）
- **Secret**：HashiCorp Vault 自托管
- **Feature Flag**：GrowthBook 自托管

#### Provider 接入协议（v1 仅 2 类，v2+ 扩展）

| 协议 | 适合 | v1 / v2 / v3 |
|---|---|---|
| **同步 HTTP** | 轻量 SKU（求解 ≤ 30s）| ✅ v1 |
| **Python 模块直调** | 自研 + 紧密集成 | ✅ v1 |
| 异步回调 | 长任务（OPF / MINLP）| v2 |
| gRPC | 高吞吐场景 | v2 |
| Docker exec | 离线 / 学术 Provider | v3（沙箱机制成熟后开启）|

#### 法务 / 客服 SLA（v1 必上）

- **法务问询 24h SLA**（Team+ 计划，与 Step 4 J5 法务副线一致）：人工回邮 + 必要时 Zoom
- 法务问答库（PIPL / GDPR / 等保 / 数据出境 pre-built FAQ）
- 数据流图模板（一键下载）
- 数据出境承诺函（盖章版 PDF 一键生成）

### Domain Patterns（选型理由 —— 详细架构见 Step 7）

#### 为什么 4-Agent NL→Model（vs 单 prompt）

- 学术对比：[OptiMUS-0.3](https://arxiv.org/abs/2407.19633) / [OptimAI](https://arxiv.org/abs/2504.16918) 显示单 prompt 准确率 < 60%，4-Agent 在 LP 学术子集达 89%、生产 60-70%
- 关键收益：Critic agent 标低置信样本转人工，避免单 prompt 黑盒错误

#### 为什么 Top-K 候选解（vs 单一最优）

- 基于 Trust-Tech 理论（v0.5.1 §8 优化分层 + 课题组研究背景）
- 业务价值：让用户挑选而非接受单一"数学最优"，应对未建模约束

#### 为什么 P10/P50/P90 置信带（vs 单点估计）

- 行业最佳实践：Nixtla / GluonTS / Chronos 等开源时序模型默认输出
- 商业价值：用户能给老板汇报"最坏情况"和"乐观情况"

> **Architectural detail**：4-Agent 流水线 + 沙箱细节见 **Step 7 System Architecture**；结果交付模式（JSON/Dashboard/NL Summary/PDF/Webhook 等）见 **Step 9 Data Contracts**。

### Risk Mitigations（含测试方法 + 监控状态）

| # | 风险 | 影响 | 缓解 | 触发 | 测试方法 / 监控状态 |
|---|---|---|---|---|---|
| R1 | AIGC 备案延期 | Chat 主入口锁死 | M0 wk1 启动 + 中介加速 + 三级 fallback | M3 末未拿到 | M3 模拟演练 / **待建工具** |
| R2 | NL→Model 生产准确率低于学术 | 用户失败重试 / 流失 | Critic agent + 低置信转人工 + M1-M2 Chat 仅辅助 | 生产 < 60% | M3-M5 每月红队 prompt 测 / **待建工具** |
| R3 | 自研代码自查未通过 | v1 SKU 退化为开源等价物 | §4.5 5 项门槛 + Apache 2.0 + v2 替换路径 | M1 末自查未通过 | PR license 检查 + 自查清单提交 / **已可监控** |
| R4 | DeepSeek API 不可用 | Chat 入口宕机 | Qwen-Max **incident 应急 fallback**（非常态）| 探活失败 ≥ 30 min | 每月故障注入演练 / **待建工具** |
| R5 | 数据合规 / PIPL 违规 | 监管处罚 + 品牌损 | 默认不进训练集 + 7 day 删除 + 加密 + 沙箱 | 用户投诉 / 监管巡查 | 每月 SQL 验证 user_id 在主+备+日志均不可查 / **待建工具** |
| R6 | 算法许可纠纷（如误用 SCIP）| 法务费 + 退款 | 白名单 hard rule + PR 自动 license 检查 + EPL 不 fork | 法务问询 | 每 SKU PR license 检查 / **已可监控** |
| R7 | Provider 退出造成 Repro 失效 | 学术用户论文撤稿 | Repro 5 年 SLA + 自动迁移 | Provider 30 天预通知 | 季度 repro voucher 抽样测试 / **待建工具** |
| R8 | 沙箱泄漏 | P0 安全事故 | gVisor + Postmortem 24h SLA + 全额退款 + 20% 补偿 | 任何沙箱越权 | 季度红队渗透 + Critic 红队 prompts / **待建工具** |
| R9 | 排他融资条款 | 战略愿景被绑死 | Hard Rule #3 拒排他 | 任何融资邀约 | 合同模板 lint + 法律顾问审 / **流程依赖人审** |
| R10 | 过早自托管 LLM 烧钱 | 现金流耗尽 | GPU 集群启动条件 = 月活付费 ≥ 500 + LLM API 月成本 ≥ ¥5 万 | v2 末评估 | 月度财务数据 vs 阈值 / **已可监控** |

监控状态分布：**3 项已可监控 / 6 项待建工具 / 1 项流程依赖人审**。"待建工具" 项已列入 Step 6 Epic 候选。

### 行业垂直模板（8 个 vertical，v1 仅做 1 主 + 1 副深度）

**v1 主推**：
- **通用 SKU**（LP / VRPTW / TS / Pricing）→ 工程师主受众跨行业适用
- **能源行业模板**（OPF/EMS via AQGS/Trust-Tech，课题组论文支撑）→ 副受众

**科研属性**：副受众（学生 + 教授），**不作为 vertical**；通过教学模式 / 算例库 / 复现凭证 / Classroom Plan 服务。

**第二行业模板（物流）**：M4 末上线。

| Vertical | v1 优先级 | 行业特殊点 | 关键合规 / 集成 |
|---|:---:|---|---|
| **物流 / 供应链** | **v1 副**（M3 起准备）| 时间窗 / 容量 / 车型异构 / 多回程 | 与 TMS / WMS 集成（v2+）|
| **能源 / 电力** | **v1 主**（课题组主场）| N-1 安全约束 / 网损模型 / SCADA 数据 | 国网技术规范（不接真实生产）|
| 金融 / 投资 | v3 | 风控 / 反洗钱 / 出境 | 银保监 + PCI DSS + 国密 |
| 制造 | v2 | 工艺约束 / 排程 | MES 集成（v3）|
| 零售 | v2 | SKU / POS / 促销规则 | POS / ERP 接入（v3）|
| 医疗 | v3 | 医疗数据保密 | 类 HIPAA（不接真实患者数据）|
| 政府 | v3 | 政采资质 + 国密 SM2/3/4 + 等保三级 | 政采招标 |
| 科研 | **副受众**（不是 vertical）| 复现性 / 论文 IP / 教学模式 | 学术联盟合作（≥3 所高校）|

## Innovation & Novel Patterns

> 7 项创新 + Execution Excellence + 8 项 Strategic Non-Goals；为 § Functional Requirements 提供能力优先级（3 Core / 4 Important）。

### Innovation Ranking 速览

🌟 **Core Innovations**（2030 估值贡献 70-80%）：
- **#1 Critic Agent SaaS 化** — 核心 AI 层
- **#2 Repro 5 年 SLA + Provider 自动迁移** — 核心信誉护城河
- **#3 学界变现 + 内容即产品** — 核心增长飞轮

⭐ **Important Innovations**（2030 估值贡献 20-30%）：
- **#4 行业模板垂直深度可插拔**
- **#5 Credits 跨层统一定价**
- **#6 Trust-Tech / AQGS Apache 2.0 开放**（M0 wk2 吕老师等签发；未签发降 v2）
- **#7 NL→Model + 多源 Provider + 订阅市场 三合一**（first-mover）

> 优先级用于 Step 7-11 EpicCreator 资源分配：Core 3 项 v1 必上深度，Important 4 项 v1-v2 渐进。

### Core Innovation #1: Critic Agent SaaS 化（核心 AI 层）

业界首次把"运筹咨询师二次校验"做成自动 SaaS。

- **替代价值**：等价于 ¥200/小时咨询师，每次调用 ≤¥0.5 自动校验
- **客户视角**：「让 AI 帮你检查求解结果是否靠谱，等价咨询师二次复核 100× 便宜」
- **2030 贡献**：NPS +12 分（48% 总提升驱动）/ 复购率核心驱动 / 拒绝 200 万次潜在错误调用
- **验证**：M3-M5 Critic Red Team Prompt 测试集（M3 ≥ 30 / M5 ≥ 200）+ 低置信样本占比 < 30% + 用户接受率 ≥ 70%
- **风险**：误判 → 多模型集成 + 人工兜底（R8 Step 5）

### Core Innovation #2: Repro 5 年 SLA + Provider 自动迁移（核心信誉护城河）

业界对比：Gurobi / TimeGPT / DataRobot 等**均无此 SLA**；学术 SaaS（CodeOcean / Whole Tale）有复现但无商业 Provider 迁移机制。

- **客户视角**：「5 年后再跑你的实验，结果一字不差」
- **2030 贡献**：第一批 vouchers 真到期 → 唯一履约者 → 300+ 论文引用 → 学术忠诚
- **机制**：凭证 ID `repro-YYYY-XXXXXX` + git commit/Docker tag/Seed 锁定 + SHA-256 输入/结果 hash + 5 年 Image 归档 + Provider 30 天退出预通知 + 自动迁移到等价 capability + 失败时人工复现（Team+ 免费 / 免费用户 ¥500）
- **验证**：季度抽样重跑 ≥ 95% 成功率 + M9+ 1 年回溯测试
- **风险**：Provider 退出无 capability 等价 → 自动迁移 + Team+ 免费人工复现 SLA（R7 Step 5）

### Core Innovation #3: 学界变现 + 内容即产品（核心增长飞轮）

**国内 OptiCloud 之前未见同类**：以 SaaS 订阅形式让课题组算法变现 + 提供完整学术友好基础设施（BibTeX 强制 + 复现凭证 + 教学模式 + Notebook Colab 一键 + 经典算例库 + 月度分润月结 + Classroom Plan）。

- **客户视角（学者）**：「你的算法上架我们这，每月收到分润账单」
- **客户视角（学生）**：「调用 SKU 同时看懂背后算法的原理」
- **2030 贡献**：学术联盟扩到 200+ 所高校 / 每年新毕业生 ≥10 万天然认知 / **70% 新用户来自高校渠道**
- **验证**：M5 前签约 ≥ 2 所；M7 前 ≥ 3 所 + 累计 ≥ 50 师生持续 ≥ 3 月；M9+ 监控 BibTeX 自动追踪 ≥ 5 篇论文引用
- **风险**：内容质量 → 课题组成员审核 + 社区贡献

### Important Innovation #4: 行业模板垂直深度可插拔

Console 一键切 vertical 模板。Nextmv 一客户一项目，OptiCloud 多模板共账户。

- **客户视角**：「今天用能源模板，明天一键切物流，账户数据不丢」
- **2030 贡献**：25+ vertical 模板 / 跨 vertical 留存
- **验证**：用户切换次数 / 跨 vertical 比例
- **风险**：v1 仅 2 模板（通用 + 能源），v2 起扩

### Important Innovation #5: Credits 跨层统一定价（计费层）

跨"优化 × 预测 × LLM"三类算法用单一 Credits 体系定价（业界首个三维统一）：

- **公式**：`Credits = ⌈ k_algo × scale × t_solve + k_overhead ⌉ + NL_credits`
- **封顶计费**：用户预扣 `max_solve_seconds`，事后多退少补
- **反博弈定义**：付费 ≥ ¥10 / 重复付费率 ≥ 60% / 90 日 Free→Paid ≥ 2%
- **客户视角**：「调一次还是一年，账单清清楚楚，永不超支」
- **2030 贡献**："OptiCloud 是我账单最透明的 SaaS" 客户声誉
- **验证**：A/B 不同 k_algo 系数（公测期）+ 监控重复付费率 ≥ 60% + 毛利率 ≥ 99% variable
- **风险**：用户混淆 / 被博弈 → 封顶 modal + 反博弈定义 + 教育版分桶

### Important Innovation #6: Trust-Tech / AQGS Apache 2.0 开放（算法层）

**紧急执行计划**：M0 wk2 课题组吕老师等作者**正式签发** Apache 2.0；若 M0 末未签发，**#6 降级为 v2 Innovation**。

- **客户视角**：「业界第一次能在生产环境用上 Trust-Tech 算法」
- **2030 贡献**：50+ 公司用 AQGS / Trust-Tech 生产 / OptiCloud 作为原产地享受品牌红利
- **验证**：吕老师等作者正式签发 Apache 2.0 协议
- **风险**：Apache fork 是协议代价 → OptiCloud 护城河 = 国内合规 + 渠道 + Brand moat；Apache 注册商标 OptiCloud

### Important Innovation #7: NL→Model + 多源 Provider + 订阅市场 三合一（first-mover）

2025-2026 4 能力（LLM 解析建模 / 开源求解器 / 开源时序基础模型 / 廉价中文 LLM API）**同时成熟**首次让此组合具备技术与经济可行性。

- **客户视角**：「1 行 cURL 跑通 Gurobi 级算法，月成本 ¥6」
- **2030 贡献**：6-12 月先发窗口已消化，但 first-mover 品牌留存
- **验证**：M4 公测访谈 + M5 NPS ≥ +20 + Free→Paid ≥ 2% + 重复付费 ≥ 60%
- **风险**：后入者复制（特别阿里云市场跟进）→ AIGC 备案壁垒 + 学术联盟 + 数据飞轮 + 课题组血统时间换空间

### Market Context & Competitive Landscape

| 类别 | 代表 | 单一能力 | 缺哪一块 |
|---|---|---|---|
| 求解器云 | Gurobi Cloud / AMPL / Frontline | 卖求解器算力 | 无 NL 入口、无多源、起价 $5K+/年 |
| DecisionOps | Nextmv | 优化模型部署成 API | 无 NL 入口、无订阅市场 |
| 预测基础模型 | Nixtla TimeGPT / Amazon Forecast | 时序预测 API | 无优化、无 NL |
| AutoML | DataRobot / RapidMiner | 拖拽预测 | 优化弱、私有部署贵 |
| NL→Model 学术 | OptiMUS / OptimAI / LEAN-LLM-OPT | 学术原型 | 无商业产品化、无中文 SaaS |
| API 市场 | RapidAPI / 阿里云市场 / 魔搭社区 | 通用聚合 | 优化预测垂直稀薄、无 NL 入口 |

**国内 OptiCloud 之前未见同类**（2026-05 时点）。

**Why Now 4 能力窗口（2025-2026）**：
- LLM 解析建模：OptiMUS-0.3 在 NL4Opt 学术 89% / 生产 60-70%
- 开源求解器：HiGHS (MIT) 2024 反超 SCIP
- 开源时序基础模型：Chronos / TimesFM / Lag-Llama Apache
- 廉价中文 LLM API：DeepSeek-V3.5 = GPT-5.1 的 1/30

**先发窗口 6-12 个月**。后入者壁垒：AIGC 备案（6-12 月）+ 课题组学术联盟（≥3 所先签）+ 数据飞轮（v2 起累积）+ 课题组血统品牌。

### Execution Excellence（非 Innovation，但产品差异化）

**LLM Coder + 沙箱 + Critic 三段式：把学术原型工业化**

这是把 [OptiMUS-0.3](https://arxiv.org/abs/2407.19633) / [OptimAI](https://arxiv.org/abs/2504.16918) 学术范式产品化的工程能力——**不是发明，是优秀执行**。

流水线：Router LLM → Formulator → Planner → Coder → **gVisor 沙箱**强制隔离 → Critic 标低置信样本转人工。

业界第一次商用级落地（含计费 / 沙箱 / 监控 / SLA），但学术原型已存在。客户感知不到具体技术，但**间接保证质量**。

### Strategic Non-Goals（v1 故意不做的差异化）

护城河不仅来自"做什么"，也来自"**坚决不做什么**"。v1 故意 Non-Goals：

| 不做 | 为什么 |
|---|---|
| 自托管 LLM | 烧 GPU 钱，月活付费 ≥ 500 才启动 |
| 私有部署 | 单客户 6-12 周服务，分散精力 |
| 自研 MILP/QP 内核 | HiGHS/OR-Tools 已强，重复造轮子 |
| 全 8 vertical 行业模板 | 1 主 + 1 副深度 > 8 浅 |
| Marketplace 双边市场 | 月营收 ¥40 万 hard-gate 触发 |
| 全栈双语 | 中文首发；M9+ 海外 BD 启动再做 |
| 多 LLM 切换 | v1 DeepSeek 单一 + 应急 fallback |
| PDF/Webhook/Embed 报告 | v1 仅 JSON+Dashboard+NL Summary |

**这些 Non-Goals 让 v1 团队 5 人 1 年完成 7 项 Innovation 真正深度**。

## API Backend Specific Requirements

> 实现层细节（30 端点 + DX + 错误码 + 限速）；为 § Functional Requirements 提供端点设计基础。

### Project-Type Overview

OptiCloud 主交付形态 = **REST API + OpenAPI 3.0 + 多语言 SDK**。M1 起 API 即生产可用；Chat / 控制台是基于 API 的薄壳。所有 Innovation（特别 Core #1 Critic / Core #2 Repro / Important #5 Credits）通过 API 一等公民暴露。

### Endpoint Groups（按团队规模兼容 §22 预算档）

| 分组 | v1 标准档 | v1 精简档 | 代表端点 | 备注 |
|---|:---:|:---:|---|---|
| 优化求解 | 3 | 2 | `POST /v1/optimizations` `GET /v1/optimizations/{id}` | DELETE 仅 Console |
| 预测推理 | 3 | 2 | `POST /v1/predictions` `GET /v1/predictions/{id}` | DELETE 仅 Console |
| Chat & NL→Model（M3+, AIGC gated）| 4 | 1 | `POST /v1/chat/conversations` `POST /v1/chat/conversations/{id}/messages` | SSE 流式 |
| Account & Auth | 4 | 2 | `POST /v1/auth/login` `POST /v1/api-keys` | refresh + list api-keys 砍 |
| Billing & Credits | 4 | 3 | `GET /v1/credits/balance` `POST /v1/credits/topup` | 精简档退款手工 |
| Reproducibility | 3 | 0 (v2) | `GET /v1/reproduce/{voucher_id}` `POST /v1/reproduce/{voucher_id}/rerun` | rerun 生成**新 voucher** 链接原 |
| Health & Meta | 3 | 2 | `GET /healthz` `GET /readyz` `GET /v1/openapi.json` | K8s 标准 |
| **Usage & Audit & Algorithms** | 3 | 1 | `GET /v1/algorithms`（**公开免鉴权**）`GET /v1/usage` `GET /v1/audit-logs` | 营销 + 合规 |
| Provider Public（v2）| 1 v2 | 0 | `GET /v1/providers/public` | 用户视角 |
| Feature Flag（v2）| 1 v2 | 0 | `POST /v1/features/{name}/opt-in` | A/B 自助 |
| **合计** | **29 + 2 v2** | **13** | — | — |

> 详细 schema / 错误码 / 示例 → **`api.opticloud.cn/v1/openapi.json`** 动态文档（M1 末发布）。PRD 不冻结具体字段，避免每次调整都改 PRD。

### Developer Hello World 三件套

```bash
# Hello #1 — LP 求解（30 秒到结果）
curl -X POST https://api.opticloud.cn/v1/optimizations \
  -H "Authorization: Bearer sk-xxx" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Accept-Language: zh-CN" \
  -d '{"task_type":"lp","minimize":{"c":[1,1]},"st":{"A":[[1,1]],"b":[10]}}'

# Hello #2 — 查 Credits 余额（1 秒）
curl https://api.opticloud.cn/v1/credits/balance \
  -H "Authorization: Bearer sk-xxx"

# Hello #3 — 公开算法列表（免鉴权，营销 + 透明）
curl https://api.opticloud.cn/v1/algorithms
```

### Authentication Model

| 类型 | v1 | v2+ | 用途 |
|---|:---:|:---:|---|
| **API Key（Bearer Token）** `sk-xxx` | ✅ | ✅ | 主路径；仅 hash 入库；前缀 6 位可见；可一键吊销；异常地理触发风险评分 |
| **JWT**（refresh + access 15 min）| ✅ | ✅ | Web Console |
| **OAuth 2.0** | — | ✅ | 第三方 SaaS 接入 |
| **Scope**（`optimize:read/write`, `predict:read/write`, `chat:read/write`, `billing:read`, `reproduce:read`）| ✅ | ✅ | API Key 创建时指定 |

### Data Schemas

- `Content-Type: application/json; charset=utf-8` 统一
- 嵌套 ≤ 3 层；数组元素 ≤ 10,000（超出走 multipart / S3 预签名 URL）
- 时间字段统一 ISO 8601 UTC + `_at` 后缀
- 字段命名：snake_case JSON
- **Idempotency-Key**（所有 POST 必带）：24h 内同 key 同 body 返缓存 + 不重复扣 Credits；同 key 不同 body 返 409；缺失则不去重
- **Cursor-based pagination**（统一 list 端点）：`?cursor=xxx&limit=50`，响应含 `next_cursor`
- **OpenAPI 3.0** 单一来源：Pydantic 后端 + TypeScript types 前端

### Sync vs Async

**默认异步**：
```
HTTP/1.1 202 Accepted
Location: /v1/optimizations/opt_xyz
{ "optimization_id": "opt_xyz", "status": "queued" }
```

**`?mode=sync` 强制同步**：仅 ≤ 5s 规模允许；服务端判断超 5s 自动转异步并返回 `optimization_id`。

**进度通知（v1 三件套）**：
- ① **SSE stream**（客户端长连接拿状态）
- ② **邮件兜底**（> 5 min 任务完成后含结果链接）
- ③ **站内信**（Console 用户）

**Webhook**（v2）：`POST` 到用户配置 URL + **HMAC-SHA256 `X-OptiCloud-Signature`** 签名（与 Stripe 一致）。

### Solver Selection

```json
{
  "task_type": "vrptw",
  "solver": "or-tools",          // 枚举：or-tools / aqgs / bonmin / ipopt / ...
  "fallback_chain": ["or-tools", "tt_minlp", "ipopt"],
  "options": { "max_solve_seconds": 60, "reproducible": true }
}
```

### Error Codes（RFC 7807 + i18n 单字段 + Actionable + 🔴 Critical M1 detail schema）

```json
{
  "type": "https://api.opticloud.cn/errors/insufficient_credits",
  "title": "Insufficient Credits",
  "status": 402,
  "detail": "余额不足。当前 50 Credits，本次预估消耗 605 Credits。",
  "errors": [
    {
      "field_path": "options.max_solve_seconds",
      "value": 600,
      "constraint": "max_solve_seconds × estimated_credit_per_second > balance",
      "remediation_hint_key": "errors.402.topup"
    }
  ],
  "instance": "/v1/optimizations",
  "request_id": "req_xyz789",
  "trace_id": "trc_abc456",
  "next_action_url": "https://console.opticloud.cn/topup?suggested_amount=10"
}
```

**🔴 FG1.3 Critical M1 — `errors[]` Detail Object Schema**（UX workflow 反向回写）：

| 字段 | 类型 | 必含 | 用途 |
|---|---|:-:|---|
| `field_path` | string（dot/bracket notation）| ✅ | 精确定位违规字段（如 `st.A[2][1]` / `options.max_solve_seconds`）|
| `value` | any | ✅ | 实际传入值（敏感字段可 redact）|
| `constraint` | string | ✅ | 违反的具体约束（机器可解析；SDK 用于客户端 hint）|
| `remediation_hint_key` | string（i18n key）| ✅ | 指向 `errors.<status>.<rule>` 单源 i18n 字典 |

**🔴 i18n 单源约束（M1 ESLint）**：
- 所有 `detail` / `title` / `remediation_hint_key` 字符串**必须**来自 `packages/i18n/errors.<lang>.yaml` 单源字典
- **ESLint 规则 `error-message-i18n-single-source`** 拒绝 hard-coded strings；CI 必跑
- `Accept-Language` header 控制 `detail` 字段语种（`zh-CN` / `en-US`，不双字段并存）
- **SDK contract**：所有 SDK（Python / Node / Go）必须**保留 `errors[]` 原结构**给客户端 inspect，不丢字段

**HTTP 状态码语义**：
- 400 数据校验失败 / 401 未鉴权 / **402 Credits 不足**
- 403 Scope/计划不允许 / 404 资源不存在 / **409 Idempotency 冲突**
- 422 业务校验失败（如 VRPTW 不可行）/ 429 限速
- 500 平台错误 / **502 Provider 失败（fallback 已触发）** / 503 服务降级 / **504 求解超时**

**4xx / 402 / 429 错误响应必带 `next_action_url`**。
**4xx / 422 错误响应必带 `errors[]`**（≥ 1 detail object）。

### Long-Running Task Response

```json
{
  "optimization_id": "opt_xyz",
  "status": "in_progress",
  "progress_pct": 45,
  "eta_seconds": 23,
  "model_version": {
    "provider_id": "or-tools",
    "provider_kind": "open_source",
    "version": "9.10.0"
  }
}
```

`model_version` 三字段（provider_id / provider_kind ∈ {`self`, `external`, `open_source`} / version）让客户**知道后端用了 HiGHS / AQGS / OR-Tools 哪一个**——Provider 透明 = Customer Trust。

### Rate Limits

| 计划 | RPS | 每分 | 并发求解 | T5/T6/P5 |
|---|:---:|:---:|:---:|---|
| **Free** | **3** | 30 | 1 | 单次小规模 |
| Starter | 5 | 200 | 3 | 日 10 次 |
| Pro | 20 | 1000 | 10 | 不限 |
| Team | 100 | 5000 | 30 | 不限 |
| Enterprise | 自定义 | 自定义 | 自定义 | 不限 |

**429 响应**：含 `X-RateLimit-Limit` / `X-RateLimit-Remaining` / `X-RateLimit-Reset` / `Retry-After` headers。**429 不扣 Credits**。

### Versioning

- **主版本**：URL path `/v1/`、`/v2/`
- **次版本**：响应头 `X-API-Version: 1.5.3`
- **Deprecation 政策**：破坏性变更必须新主版本；旧版本服务 ≥ **12 个月**（M5 商用起算）；Sunset 公告通过 response header + 邮件 + Console 通知
- **Date-based versioning**（v2 起）：可选 `X-API-Date: 2026-05-17` 锁定行为快照

### SDK & Client Libraries

| 工具 / 语言 | 版本 | M1 | M5 | v2+ |
|---|---|:---:|:---:|:---:|
| **🔴 Postman Collection** | OpenAPI 3.0 → Postman 2.1 | ✅ **Critical M1**（与 OpenAPI spec 同期发布；公开 `https://postman.opticloud.cn/`）| — | — |
| **Python** | 3.10+ | ✅ 主推（PyPI alpha 末）| — | — |
| Node.js / TypeScript | 18+ | — | ✅ | — |
| Go | 1.21+ | — | ✅ | — |
| Java/Kotlin/.NET | — | — | — | v2 |
| Rust | — | — | — | v3 |

OpenAPI Generator 自动生成 Node/Go SDK 骨架；关键路径手工优化。

**Postman Collection M1 升 Critical 理由**（FG1.1，UX workflow 反向回写）：
- 4 sub-persona 之一（李工 物流/cURL）的 zero-config 路径
- 集成测试时**前端 + Provider 团队**共享 Postman workspace（共用 Mock Server）
- M5 商用前 **Hello World 三件套 cURL** 同步生成 Postman variants（覆盖 5 个 Plan + RFC 7807 错误响应样例）

### Developer Experience（DX）

**Onboarding 3 步**：
1. 注册（手机号 + 邮箱双验证，3 分钟）
2. 注册成功页**直接生成首个 API Key + 含完整 cURL with key 的 modal + 一键导入 Postman 按钮**（M1 必上）
3. 复制粘贴 cURL OR Postman 导入 → 跑通（≤ 3 分钟到 200 OK）

**Hello World 三件套**：3 个 cURL 覆盖核心场景（详见上）。

**Postman Workspace（M1 必上，FG1.1 Critical）**：
- 公开 workspace `https://postman.opticloud.cn/`（无需登录预览）
- Collection 含：3 Hello World + 5 Plan 限流 variants + RFC 7807 错误响应样例 + Idempotency-Key/X-OptiCloud-Signature header 演示
- 每次 OpenAPI spec 发布触发 **Postman 自动同步**（GitHub Action）
- M1 必发 Postman badge 至 Landing + Docs

**错误恢复 Actionable**：4xx / 402 / 429 必带 `next_action_url`；402 引导加油包；429 引导升级计划；422 引导问题不可行排查。

**Provider 透明**：`model_version.provider_id/provider_kind/version` 三字段让客户知道用了哪个后端。

**主动客服 Modal**：注册后 5 min 未跑通自动弹出（Step 4 J1 已写）。

### Web App Specific（副类型）

继承 api_backend 全部要求，**额外**：
- **形态**：Next.js 15 + App Router + Turbopack；SSR + CSR 混合（Landing/Docs SSR，Console CSR）
- **浏览器支持**：Chrome / Edge / Safari / Firefox **latest 2 versions**；iOS Safari latest 2 / Chrome Android latest 2；不支持 IE
- **Tablet 支持**（v1）：768-1023px Tier 1（详 UX Spec Step 13）；详细 rendering capability 见 Architecture v2.2 plan
- **SEO**：Landing / Docs / Blog SSR 全开 + sitemap.xml + structured data
- **Real-time**：Chat SSE（不上 WebSocket，省运维）
- **Accessibility**：**WCAG 2.1 AA v1** → **WCAG 2.2 v1.5+（FR7 UX 升级路径）**（M5 评测，M7 修补）
- **国际化**：next-intl 框架，**v1 仅 zh-CN**（Hindsight 后取消双语，i18n key 框架预留）
- **Excel 能力（M2-M3 v1 末，FR E11 必上）**：xlsx-style + ExcelJS 处理；老张 sub-persona surface 落地

#### 🟠 Forward References to Architecture v2.2（UX workflow 反向回写，HI-1）

UX Design Spec 累积 4 项 cross-doc 锚点，待 Architecture v2.2 升级 / `/bmad-edit-architecture`：

| # | UX Spec Step | 待 Architecture v2.2 同步 | 当前 PRD 行为 |
|:-:|---|---|---|
| **FR1** | Step 2 IA / Page Direction Map（10 page tree）| 加 §IA Architecture + P75 Persona-Surface Mapping | PRD 此章仅记 reference；详细 IA 见 UX Spec |
| **FR2** | Step 4 Emotional Response（4 sub-persona surface map）| 加 P75 Persona-Surface Mapping | Brand Voice "实证克制" + 13 EPs 已记 UX Spec |
| **FR3** | Step 6 Tailwind v3 → v4 升级 | 加 C22 升级窗口（v1.5+）| PRD 此章 Tailwind 不锁版本 |
| **FR7** | Step 13 WCAG 2.2 v1.5+ upgrade path | 加 NFR-A5 v1.5+ WCAG 2.2 升级 | §Accessibility 已含 v1.5+ 升级路径标注 |

### Implementation Considerations

#### M1 必交付（基础设施 + Auth + 第 1 SKU）

- FastAPI 网关 + Uvicorn 多实例 + Nginx LB
- `POST /v1/optimizations` 端到端（HiGHS LP）
- API Key 认证 + Credits 余额扣费 + 错误码框架（含 next_action_url + **errors[] detail object schema**）
- OpenAPI 3.0 spec 发布
- **Postman Collection 发布**（🔴 FG1.1 Critical M1）
- Python SDK alpha PyPI
- gVisor 沙箱基础设施
- Health + Algorithms 公开端点

#### M2-M5 渐进

- 扩 SKU 至 4 个（VRPTW / ARIMA / LSTM）
- Credits 加油包 / 退款 / 月度对账（拆 M2 基础 + M5 完整）
- 异步任务 + SSE 流 + 邮件兜底
- Chat MVP（SSE + DeepSeek + 4-Agent + 沙箱）— **M3 AIGC 备案 gated**
- Usage + Audit Log 端点
- Reproducibility 凭证机制（M5 ≥ 部分 / v2 完整）
- **Console Excel upload-download v1 末**（🔴 FG1.2 Critical FR E11；老张 sub-persona）— M2-M3 落地

#### M5+ 扩展

- Node / Go SDK
- Webhook 回调 + HMAC 签名
- Provider Public API
- Feature Flag 自助
- v2 Marketplace API（月营收 ≥ ¥40 万 hard-gate 触发）

## Project Scoping & Phased Development

> 战略综合 + 资源 + 风险；为 § Functional Requirements / § Non-Functional Requirements / Step 12 完成提供路线图。覆盖 MVP 哲学 + 3 档资源 + Phase 1/2/3 + Top 3 项目级风险。

### MVP Strategy & Philosophy

**MVP 哲学**：**Validated Learning + 92% Cost Win 承诺**

- **不是** Feature MVP / Platform MVP
- **是 Validated Learning MVP**：M5 末验证 ≥ 50 付费 + Free→Paid ≥ 2% 即视 PMF 触达；不达成则 Pivot
- 同时是 **92% Cost Win**：对工程师客户硬承诺"月成本从 ¥5,000+/月 降到 ¥6+/月"（≥ 99% 节省）

### MVP Resource Requirements（v0.5.1 §22）

| 档位 | 团队规模 | 12 月预算 | API 端点 | SKU 数 | LLM 路径 | 触发条件 |
|---|:---:|:---:|:---:|:---:|---|---|
| **精简档** | 3 人（1 全职 + 2 学生兼职）| ¥114 万 | 13 | 2-3 | DeepSeek 单一 | 启动资金 ≤ ¥40 万 |
| **标准档**（推荐）| 5 人全职 | ¥248 万 | 29 + 2 v2 | 4 | DeepSeek + Qwen 应急 | 启动资金 ¥100 万 |
| **扩展档** | 8-10 人全职 | ¥400 万 | 29 + 6 v2 | 6 | + 多 LLM | 启动资金 ¥150 万+ |

### Phase 1 — MVP（M0-M5，22 周）

**Must-Have（11 类）**：基础设施 / 核心 SKU（M1 `opt.lp.solve` HiGHS + M2 扩 vrptw/arima/lstm 共 4 个）/ Chat MVP（M3+ AIGC gated）/ Credits 计费拆两阶段 / 中文 UI / 3 种结果交付 / 合规底盘 / 公司主体 / 沙箱 / 运维基础 / M4.5 GTM + API 29 端点

**v1 必上 Innovation**：🌟 Critic Agent (M3-M5) + Repro 5y SLA 部分 + 学界变现部分 + Credits 跨层完整 + 三合一商用

**Trust-Tech / AQGS Apache 2.0**：M0 wk2 吕老师等签发；未签发降 v2

### Phase 2 — Growth（M5-M9）

- 扩 SKU 至 8-10 个（含 1 个深度行业模板：物流 / 能源任选）
- Webhook 回调 + HMAC 签名 / PDF & Word 报告
- 教学模式完整 + 经典算例库（IEEE / CVRPLIB / OR-Library / M5 / UCI / NAB）
- Classroom Plan（5-200 学生账号）
- Provider 接入扩展（≥ 3 外部 Provider）
- 公开 AI 评估面板 + 复现凭证 GA
- Pro+ SLA 99.5% 对外承诺生效
- Node / Go SDK
- v2 端点：Provider Public + Feature Flag + Webhook
- pgvector → Qdrant 迁移

### Phase 3 — Expansion（M9+，弹性触发）

- 自托管 N1-N3 本地 LLM（触发：月活付费 ≥ 500 + LLM API 月成本 ≥ ¥5 万）
- 完整 7 种结果形态（+ Embed Widget）
- 全栈双语 + 海外节点
- 私有部署 / On-Prem / 学校机房
- **Marketplace 双边市场**（hard-gate：月营收 ≥ ¥40 万）
- Provider 完整 Console + 路由透明 + 自动 BibTeX 引用追踪
- 数据飞轮回训 + Critic agent 智能进化
- 第二、第三个深度行业模板（金融 / 制造 / 零售 / 医疗 / 政府）
- "决策智能协议层" 战略愿景

### Risk Mitigation — Top 3 项目级风险

| # | 风险 | 概率 | 影响 | 主缓解 | 兜底 |
|---|---|:---:|:---:|---|---|
| **R1** | NL→Model 生产准确率 < 60% | 中 | 致命 | Critic agent + 低置信转人工 + Chat 仅辅助至 M3 | API 入口先行；Chat 降级到模板表单 |
| **R2** | AIGC 备案延期超 M5 末 | 中 | 致命 | M0 wk1 启动 + 中介加速 + 三级 fallback | M3 失败 → API-only；M5 失败 → 暂停 Chat；M7 失败 → 课题组评估走向 |
| **R3** | M5 末付费 < 50 / 月营收 < ¥4 万（PMF 失败）| 中 | 致命 | M3 末 hard-gate（24h 留存 ≥60% + NL Summary ≥80%）验证 | M5 PMF 失败 → Pivot 评估（转 to-B / 转售 / Plan B）|

**资源风险**：≥3 人 = 标准档可执行 / =1-2 人 = 精简档 / 1 人独立不推荐启动

**财务风险**：跑道 < 6 个月触发 §22 紧急动作（砍成本 / 融资 / 转售）

**详细 10 项 Risk 见 Step 5 / Domain Requirements Risk Mitigations 表**

### Scoping Decision Summary

✅ **MVP**：4 SKU + Chat MVP（AIGC gated）+ 29 端点（标准）/ 13 端点（精简）+ 中文 UI + Credits 三件套 + 合规底盘
❌ **v1 不做**：自托管 LLM / PDF & Webhook / 私有部署 / Marketplace / 全栈英文 / 多 LLM 切换 / 完整 Provider Console / 全 7 种结果形态
🔄 **演进**：v1 (M0-M5) → v2 Growth (M5-M9) → v3 Expansion (M9+) 弹性触发

## Functional Requirements

> **Capability Contract** — 锁定 v1-v3 路线图全部用户可见 / 系统能力。本章 **78 FR**（v1.1，新增 E11）跨 8 能力域；为 § Non-Functional Requirements 提供 capability hook（具体数字 / 阈值则在 NFR）。

### 🔒 Capability Contract 锁定声明

> 一旦本章节通过评审：
> - `[v1 必上]` = M5 商用前必须实现，否则 hard-gate 阻断商用
> - `[v1 末]` = M5-M7 实现
> - `[v2]` / `[v3]` = 后续 Phase
> - **未列入任何 stage 的 capability = v1-v3 路线图不包含；需 PR 修改 PRD 并 re-review**

### FR 与 UX 决策边界

- **FR 必含**（业务级阈值）：Onboarding ≤ 5 步骤 / 5 min 未跑通触发主动客服 / P5 调用前必弹警示 / 余额 < 预估弹 Modal
- **FR 不含**（交 Step 10 UX）：Modal 按钮颜色 / 字体 / 路径深度 / 错误页面布局

### 阅读路径

| 角色 | 关注子集 |
|---|---|
| PRD 评审者 | v1 必上 38 + v1 末 20 = 58 FR |
| UX 设计师 | A + E + B + N（约 52 FR）|
| Provider 团队 | P + 部分 R（约 15 FR）|
| 学术用户 | R + N(教学) + B8(教育) + O8/O11 |
| 安全 / 运维 | O 全部 + A5/A6/A7（风控）|

### Stage 分布（77 FR）

| Stage | ≥3 人团队 | =1-2 人精简档 |
|---|:---:|:---:|
| **v1 必上**（M0-M5）| **38** | ~25（11 项可砍简化）|
| **v1 末**（M5-M7）| 20 | 10 |
| **v2**（M5-M9）| 14 | 5 |
| **v3**（M9+）| 5 | 0 |
| **合计** | **77** | ~40 |

### Journey-FR Mapping

| Journey | 涉及 FR |
|---|---|
| **J1 李工 happy path** | A1, A2, A9（Onboarding）, C1, E1, E7, B1, B2 + **Postman M1 (FG1.1)** |
| **J2 Lina 错误恢复** | E2, E7（含新 errors[] schema FG1.3）, B1, B2, B6, B12（预算）|
| **J3 王哲 incident** | O1, O2, B5（退款）|
| **J4 吕教授+小赵** | A4, B8（教育版）, R1-R7, P1-P8, O8, O11（算例库）|
| **J5 陈架构师** | A2, C1, E1, B1, O10（法务）+ **errors[] schema (FG1.3 SDK contract)** |
| **J6 流失** | A6 |
| **J7 风控冻结** | A5, A7, A8 |
| **J8 AIGC 巡查** | O5, N5/N9（Critic）|
| **J9 白帽** | O4 |
| **老张 Excel surface（新增 UX sub-persona）** | **E11（FG1.2 Critical Console Excel upload-download v1 末）**, E7, B1 |
| **J10/J11** | placeholder TBD |

---

### 1. Account & Identity Management（10 FR）

**Why**：每个 Journey 从注册开始；账户安全 + 风控 + 隐私 = SaaS 信任基础。覆盖 J1/J5/J7。

| # | FR | Stage | 精简档 | Source / KPI |
|---|---|:---:|:---:|---|
| **A1** | 任何访客 can register via 手机号+邮箱双因素验证 | v1 必上 | ✅ | J1, J2 / 24h 留存 ≥60% |
| **A2** | 用户 can create/list/revoke API keys with scoped permissions, **label / description / optional expiration** | v1 必上 | ✅ | J1, J5 |
| **A3** | 用户 can configure preferred language（v1 仅 zh-CN）| v1 必上 | 可砍 | §15 |
| **A4** | 教育用户 can verify via .edu/.ac.cn 邮箱自动激活教育版 | v1 必上 | 可砍（手审）| J4 / 高校 ≥2 |
| **A5** | 系统 can detect+reject Free 注册 when 指纹 ≥0.9 OR IP/24 OR 24h ≥20 调用 OR 支付重复（任 2 项）| v1 必上 | ✅ | J7, §21 |
| **A6** | 用户 can request 账户删除 + 系统 7 day 内 hard-delete (PIPL) | v1 必上 | ✅ | §14 PIPL |
| **A7** | 系统 can offer account merge proposal + 工作日 48h 复审（≥3 人）OR auto-score（=1-2 人）| v1 必上 | ✅（简化）| J7 |
| **A8** | 用户 can resume access via account merge | v1 必上 | 可砍（手处理）| J7 |
| **A9** | 用户 can complete Onboarding Wizard ≤ 5 步骤 | v1 必上 | ✅ | J1, DX |
| **A10** | 系统 can prevent < 14 岁注册；14-18 岁须监护人确认 | v1 必上 | ✅ | §14 |

### 2. Algorithm Catalog & Solver Selection（8 FR）

**Why**：30 端点 API 入口；让客户看到我们支持什么。

| # | FR | Stage | 精简档 |
|---|---|:---:|:---:|
| **C1** | 任何访客 can list algorithms via `GET /v1/algorithms` **公开免鉴权** | v1 必上 | ✅ |
| **C2** | 用户 can view algorithm details (k_algo / schema / examples) | v1 必上 | ✅ |
| **C3** | 用户 can browse by tier (T1-T6 / P1-P5) | v1 必上 | ✅ |
| **C4** | 用户 can specify `solver` (枚举) | v1 必上 | ✅ |
| **C5** | 用户 can specify `fallback_chain` | v1 必上 | 可砍（v2）|
| **C6** | 系统 can route to multiple providers (self/open-source/external/commercial) | v1 必上 | ✅ |
| **C7** | 系统 can execute fallback chain after ≤3 retries | v1 必上 | ✅ |
| **C8** | 系统 can prevent unaudited 自研 algorithms until §4.5 self-audit 全 ✅ | v1 必上 | ✅ |

### 3. Optimization & Prediction Execution（11 FR）

**Why**：所有计算的核心引擎；M5 商用门槛 = 4 SKU 端到端。

| # | FR | Stage | 精简档 |
|---|---|:---:|:---:|
| **E1** | 用户 can submit optimization `task_type ∈ {lp, milp, qp, socp, sdp, nlp, minlp, vrptw, schedule, cp_sat}` | v1 必上 | ✅（2 类）|
| **E2** | 用户 can submit prediction `family/{algo}` 路径 | v1 必上 | ✅（2 类）|
| **E3** | 系统 can execute sync (?mode=sync ≤5s) 或 async | v1 必上 | ✅ |
| **E4** | 用户 can specify `max_solve_seconds` 封顶 | v1 必上 | ✅ |
| **E5** | 用户 can request `top_k_alternatives` | v1 必上 | 可砍（v2）|
| **E6** | 系统 can return predictions **强制 P10/P50/P90 + drift_score + bilingual disclaimer** | v1 必上 | ✅ |
| **E7** | 系统 can validate schema + return **RFC 7807 + next_action_url + 模板** | v1 必上 | ✅ |
| **E8** | 用户 can cancel async + refund per policy | v1 必上 | 可砍（手处理）|
| **E9** | 用户 can retrieve `status/progress_pct/eta_seconds/model_version (provider_id, kind, version)` | v1 必上 | ✅ |
| **E10** | 用户 can backtest predictions at 50% Credits 折扣 | v2 | — |
| **E11** | 用户 can upload **Excel (.xlsx ≤ 5 MB / 50K rows)** via Console 直接转 task_type，求解后 can download 结果 Excel（保留输入 sheet + 新增 results sheet + chart preview）| v1 末 | ✅ |

### 4. Chat & Natural Language Modeling（12 FR，M3+ AIGC gated）

**Why**：Innovation #1 Critic Agent + 4-Agent + 沙箱核心 AI 层。

| # | FR | Stage | 精简档 |
|---|---|:---:|:---:|
| **N1** | 用户 can converse in NL (中/英/中英混) | v1 末 | ✅ |
| **N2** | Router LLM can classify intent | v1 末 | ✅ |
| **N3** | Formulator can extract variables/objective/constraints | v1 末 | ✅ |
| **N4** | Coder can generate executable code | v1 末 | ✅ |
| **N5** | Critic can validate generated code execution | v1 末 | ✅ |
| **N6** | 用户 can preview+confirm AI 模型 before solve | v1 末 | ✅ |
| **N7** | 系统 can stream Chat (每 chunk ≤100 token) via SSE | v1 末 | ✅ |
| **N8** | 用户 can upload files (CSV/Excel/JSON) | v1 末 | ✅ |
| **N9** | Critic Agent can flag confidence < 0.6 + escalate to human review | v1 末 | ✅ |
| **N10** | 用户 can perform "what-if" follow-ups | v1 末 | ✅ |
| **N11** | 系统 can execute code in isolated sandbox（具体限制 → NFR）| v1 末 | ✅ |
| **N12** | 用户 can view Critic Agent confidence score + 中英文 reasoning | v1 末 | ✅ |

### 5. Credits, Billing & Subscription（13 FR）

**Why**：Innovation #5 Credits 跨层定价 + 反博弈 + 教育版（学界飞轮 #3）。

| # | FR | Stage | 精简档 |
|---|---|:---:|:---:|
| **B1** | 用户 can view Credits 余额按桶（月度/注册/教育/加油包）| v1 必上 | ✅ |
| **B2** | 用户 can preview max Credits (**封顶值 ≥ 实际**) before confirm | v1 必上 | ✅ |
| **B3** | 用户 can subscribe (Free/Starter/Pro/Team/Enterprise) | v1 必上 | ✅ |
| **B4** | 系统 can charge per formula capped by `max_solve_seconds` | v1 必上 | ✅ |
| **B5** | 用户 can request refunds for failed/cancelled/infeasible | v1 必上 | ✅ |
| **B6** | 系统 can warn via Modal when **P5 调用 OR 余额 < 预估** | v1 必上 | ✅（简化）|
| **B7** | 用户 can view 双语 invoices + 7d/30d usage trends | v1 必上 | ✅ |
| **B8** | 教育用户 can access 永久免费 Starter (2K/月) + Pro 30d trial | v1 必上 | ✅ |
| **B9** | 用户 can purchase top-up 永不过期 | v1 必上 | ✅ |
| **B10** | 用户 can export all data + history (JSON/CSV) | v1 必上 | 可砍（手邮）**PIPL 法定** |
| **B11** | 用户 can save job templates + reuse + version | v1 必上 | 可砍（v2）|
| **B12** | 用户 can set monthly budget alert + 自动暂停 | v1 必上 | 可砍（仅余额告警）|
| **B13** | 用户 can configure notification preferences | v1 必上 | 可砍（v2）|

### 6. Reproducibility & Academic Integrity（7 FR）

**Why**：Innovation #2 Repro 5 年 SLA 核心信誉护城河。

| # | FR | Stage | 精简档 |
|---|---|:---:|:---:|
| **R1** | 用户 can mark `reproducible: true` to lock version/seed | v1 末 | ✅ |
| **R2** | 系统 can generate permanent voucher with unique ID（格式 → NFR）| v1 末 | ✅ |
| **R3** | 用户 can rerun within 5y; new voucher links original | v1 末 / v2 完整 | ✅ |
| **R4** | 系统 can auto-migrate to equivalent Provider (capability 词表) | v2 | — |
| **R5** | 系统 can attach `citation.bibtex` for academic SKUs | v1 必上 | ✅ |
| **R6** | 用户 can enable `anonymous: true` for blind review | v1 末 | ✅ |
| **R7** | 系统 can notify voucher holders ≥30d before Provider 退出 | v2 | — |

### 7. Provider Integration & Marketplace（8 FR，主要 v2-v3）

**Why**：Innovation #5 学界变现 SaaS 化的实现。

| # | FR | Stage | 精简档 |
|---|---|:---:|:---:|
| **P1** | 外部 Provider can apply via OpenAPI + Docker + 评测 | v2 | — |
| **P2** | 系统 can run shadow validation before promotion（数字 → NFR）| v2 | — |
| **P3** | 系统 can gradually promote 5%→50%→100% traffic | v2 | — |
| **P4** | Provider can view own route share over time | v2 | — |
| **P5** | Provider can view own success rate + KPI dashboards | v2 | — |
| **P6** | Provider can view own revenue + pending payout | v2 | — |
| **P7** | Provider can submit version updates (patch/minor/major) | v2 | — |
| **P8** | 系统 can compute monthly revenue share (自研 100% / 合作 60/40 / 商业 50/50) | v2 | — |

### 8. Observability, Risk & Compliance（11 FR）

**Why**：信任与合规底盘；J3/J7/J8/J9 应急 SOP。

| # | FR | Stage | 精简档 |
|---|---|:---:|:---:|
| **O1** | 任何访客 can view status page **without authentication**；用户 can subscribe via email/Webhook | v1 末 | ✅ |
| **O2** | 管理员 can publish 24h Postmortem for P0 incidents | v1 末 | ✅ |
| **O3** | 用户 can view audit logs of own activity | v1 末 | ✅ |
| **O4** | 安全研究者 can submit vuln via `security@` + ≤48h response + ≤7d patch | v1 必上 | ✅（SLA 拉长）|
| **O5** | 系统 can apply AIGC content filtering before user-visible NL output | v1 末 | ✅ |
| **O6** | 系统 can enforce rate limits per plan + return 429 with headers | v1 必上 | ✅ |
| **O7** | 系统 can return errors with `next_action_url` for 4xx/402/429 | v1 必上 | ✅（静态 URL）|
| **O8** | 用户 can request `mode=teaching` + 原理讲解 + Notebook Colab | v1 末 | 可砍（v2）|
| **O9** | 用户 can view Provider routing history in Console | v2 | — |
| **O10** | Team+ 用户 can submit 法务问询 + ≤24h SLA | v1 末 | 可砍（中介）|
| **O11** | 用户 can browse 经典算例库 (IEEE/CVRPLIB/OR-Lib/M5/UCI/NAB) at 50% Credits 折扣 | v2 | — |

---

### Capability Contract 总计：**78 FR**（v1.1 / 2026-05-17：新增 E11 Console Excel upload-download）

| 能力域 | 数量 | v1 必上 | v1 末 | v2 | v3 |
|---|:---:|:---:|:---:|:---:|:---:|
| Account & Identity | 10 | 10 | — | — | — |
| Algorithm Catalog | 8 | 8 | — | — | — |
| Execution | **11** | 9 | **1** | 1 | — |
| Chat & NL（AIGC gated）| 12 | — | 12 | — | — |
| Billing & Subscription | 13 | 13 | — | — | — |
| Reproducibility | 7 | 1 | 4 | 2 | — |
| Provider | 8 | — | — | 8 | — |
| Observability & Compliance | 11 | 4 | 4 | 3 | — |
| **合计** | **78** | **38** | **21** | **14** | **0** |

> ⚠️ **Capability Contract 锁定**：未列入任何 stage 的 capability v1-v3 路线图不包含。如需增删 FR 须 PR 修改 PRD 并 re-review 前 8 章影响。

## Non-Functional Requirements

> 收纳前序章节移出的所有数字 / 阈值 / 测试方法；与 § Functional Requirements 协同（FR 定义 WHAT，NFR 定义 HOW WELL）。本节 95% 内容来自前 10 章数字汇总。

### 1. Performance（性能）

#### 1.1 API 延迟 SLO

| 指标 | 目标 | 测试方法 |
|---|---|---|
| API 网关 P95 延迟 | < 200 ms | **Locust 持续压测 + Prometheus `histogram_quantile(0.95)`** |
| Chat 首 Token 延迟 | P50 < 1.5 s，**P95 < 3 s** | SSE 客户端首 token 时间戳 |
| Chat 流式吞吐 | ≥ 20 Token/s | 流式压测 |
| 异步任务排队 P95 | < 30 s | Celery metrics |

> **M3 起埋点监控；M5 末作为 KPI 达标**（不是上线即达标）。

#### 1.2 求解 SLO（分级，调用前自动按 `task_type + scale` 归类）

| 类型 | 规模 | 目标 |
|---|---|---|
| LP/QP | < 100 vars | P95 < 1 s |
| LP/QP | < 10K vars | P95 < 5 s |
| VRPTW | < 100 客户 | P95 < 30 s |
| VRPTW / MINLP | ≥ 500 客户 | **自动转异步** |

#### 1.3 沙箱性能（FR N11 配套）

- gVisor: **CPU 1 vCPU / Mem 1 GB / Net 禁外网 / FS 只读**
- 沙箱内执行 ≤ 30 s 软超时 / 90 s 硬超时强杀
- 沙箱外 Provider 调用 ≤ 60 s 软超时
- Chat E2E ≤ 90 s 用户感受范围
- gVisor CPU 性能下降 30-50% 已计入 SLO 计算

### 2. Security（安全）

#### 2.1 加密

- 传输 TLS 1.3 / 落盘 AES-256
- 客户端可选客户端加密（Pro+ 计划）
- **Vault HSM + 双人审批轮换**

#### 2.2 认证与授权

- API Key 仅 hash 入库，前缀 6 位可见 / 异常地理触发风险评分 / 一键吊销
- JWT access 15 min / refresh 7 day（Web Console）

#### 2.3 内容安全 / 风控（FR A5/A7/N9/O5 配套）

- **风控冻结条件**（任 2 项触发）：
  - 设备指纹相似度 ≥ 0.9
  - IP /24 同段
  - 24h 内调用 ≥ 20 次
  - 支付方式重复使用
  - 手机号已注册 ≥ 1 账号
- **Critic 红队测试集**：M3 前 ≥ 30 个边界 prompt / M5 前 ≥ 200 / v2 起众包扩展（白帽奖励 ¥10/prompt）
- **Critic 置信度阈值**：**< 0.6 自动标记 + 转人工**（M3 用 30 个 ground truth 校准 / M5 用 200 个 / 阈值可动态调整）
- **AIGC 内容过滤**：Critic prompt 强化 + 敏感词二级过滤 + AIGC 标识水印

#### 2.4 P0 安全事件零容忍

**三类 P0 事件 ≤ 0 起/季度**：
1. 沙箱越权（任何容器逃逸）
2. 数据外泄（任何用户数据被未授权访问）
3. 资金账本错（Credits / 退款 / 订阅金额不一致）

P0 发生时 **24 h 内公开 Postmortem**（FR O2）。

### 3. Scalability（可扩展性）

#### 3.1 用户规模阶段

| 时间 | 月活付费 | 月活总量 | 数据库压力 |
|---|:---:|:---:|---|
| M5 末（商用）| ≥ 50 | ~500 | 单 Postgres 4C8G 够用 |
| M7 末 | ≥ 200 | ~2,000 | 主从复制 |
| v2 末 | ≥ 500 | ~5,000 | 分库（core/billing/chat/audit）|
| v3+ | ≥ 5,000 | ~50,000 | + 自建 GPU + 多区 |

#### 3.2 数据库扩展触发

- **Postgres**：v1 单实例 4C8G + 跨区备份 → v2 主从读写分离 → v2 末分 4 库（core / billing / chat / audit）
- **Vector DB**：v1 起 pgvector → **触发迁移 Qdrant**：月活付费 ≥ 500 **AND** 月度 embeddings ≥ 500K
- **Redis**：v1 单实例 + RDB+AOF → v2 起 Sentinel HA

#### 3.3 GPU 自建集群触发（**AND 必须同时满足**）

- 月活付费 ≥ 500
- **AND** LLM API 月成本 ≥ ¥5 万持续 ≥ 2 个月
- **AND** 团队 ≥ 6 人（有 1 名 GPU 运维工程师）
- **AND** 资金跑道 ≥ 12 个月

#### 3.4 LLM 容量与 fallback

- 主路径：DeepSeek-V3.5（v1 单一供应商）
- Incident 应急 fallback：Qwen-Max API（≥ 30 min 不可用触发手动切换，**不计入正常 SLO**）
- v2+：多 LLM Router（DeepSeek / Qwen / GLM / GPT / Claude）

### 4. Reliability & Availability

#### 4.1 SLA

| 计划 | v1（M1-M6）| v1.5（M7+ 正式承诺）|
|---|:---:|:---:|
| Free | 尽力而为 | 尽力而为 |
| Starter | 尽力而为 | 99.0% |
| Pro | 尽力而为 | 99.5% |
| Team | 尽力而为 | 99.9% |
| Enterprise | 协商 | 协商（最高 99.99%）|

> v1 对外不承诺；**内部仍埋点采集 `monthly_uptime`** 以验证 v1 经验上限估算 99.2%（DeepSeek 99.5% × 自己 99.7%）。v1.5 起多供应商 + 多云后正式承诺。

#### 4.2 灾备（分阶段）

| 阶段 | RTO | RPO | 部署 |
|---|:---:|:---:|---|
| **v1 (M3-M6)** | **≤ 24 h（冷备）** | **≤ 1 h** | 单云区 + 跨区备份 |
| **v2 末** | ≤ 4 h（热备） | ≤ 15 min | 多区部署 |

备份策略：Postgres 实时 WAL + 每日全量 / S3 跨区复制 / Vault HSM 季度演练。

#### 4.3 漏洞响应

- CVSS ≥ 7.0：**≤ 24 h 补丁部署**
- CVSS 4-6.9：≤ 7 day
- 依赖库扫描：周扫 + 高危 24 h 修

#### 4.4 计费可靠性

- 计费对账误差 = **0**（双写账本 + 每日扫差）

### 5. Compliance（合规）

#### 5.1 国内法定

| 项 | 阈值 / 截止 | 备注 |
|---|---|---|
| **公司主体注册** | M0 wk1 完成 | Hard Rule #1 |
| **ICP 备案** | M1 末完成 | — |
| **公安备案** | 网监 30 日内 | — |
| **AIGC 备案** | **M3 末 hard-gate**（三级 fallback）| 网信办平均 4-6 月，需 M0 wk1 启动 |
| **AIGC 备案中介费** | **¥3-8 万必出预算**（精简档不可砍）| — |
| **AIGC 内容标识水印** | M3 起 | — |
| **PIPL 删除 SLA 7 day** | M2 起 | ⚠️ **行业自律**，PIPL 法定"及时" |
| **等保 2.0 二级** | **评测启动 M3 / 取证 M5 末** | 测评周期 4-6 月 |
| **等保 2.0 三级** | v2 启动评测 / v3 末取证 | Enterprise / Gov / Fintech 客户要求时 |
| **数据出境安全评估** | 仅当用户主动选 N4 远程国际 LLM 时触发 | DeepSeek / Qwen 境内不触发 |

#### 5.2 学术 / 复现

- **Reproducibility Voucher 格式**：`repro-{YYYY}-{6 位 base32}`（如 `repro-2026-K7X9P2`）
- **Image 5 年归档**：S3 Glacier（¥0.0036/GB·月）+ **加密 KMS key 同步备份 + 5 年保留** + 季度恢复演练
- **Provider 退出预通知**：≥ 30 day 邮件 + 站内信 + 状态页

### 6. Provider Integration

#### 6.1 Shadow Validation 阈值（FR P2 配套）

- **时长 ≥ 14 day**
- **样本 ≥ 500 个**
- 算例覆盖 4 类（平台标准集 / Provider 自带 / 对抗集 / 脱敏真实）
- KPI 通过：
  - **成功率 ≥ 98%**（失败定义：返回非 2xx HTTP OR 偏差 > 2% OR 超时）
  - **平均偏差 ≤ 2%** vs reference impl
  - **P95 延迟 ≤ 平台基线 ×1.5**

#### 6.2 灰度发布

- 5% → 50% → 100% traffic 三阶段
- 任一 KPI 跌破阈值自动降级

#### 6.3 算法许可白名单

| License | 状态 | 限制 |
|---|---|---|
| MIT / Apache 2.0 / BSD | ✅ 自由 | — |
| EPL（IPOPT / Bonmin / Couenne）| ⚠️ 仅调用 | **禁止 fork 修改**（file-based copyleft）|
| **ECOS（GPLv3）** | ⚠️ **v1 备用，需法务签字后 v2 启用**（优先用 SCS MIT）| SaaS 网络使用风险 |
| **SCIP** | ❌ 商用付费 | 学术免费 |
| GPL / AGPL / 商业 | ❌ 禁用 | — |

**自研算法**：统一 Apache 2.0 签发（M0 wk2 吕老师等正式签发；§4.5 自查 5 项 hard rule）。

### 7. Accessibility（无障碍）

- **目标**：**WCAG 2.1 AA v1** → **WCAG 2.2 AA v1.5+**（🟠 FR7 UX 升级路径，待 Architecture v2.2 加 NFR-A5）
- **方法**：**设计时实现**（不是评测后修补）—— color contrast ≥ 4.5:1 / keyboard navigation / aria labels / focus visible
- **验证**：M5 起 **axe-core + jest-axe 自动扫**（PR 流水线集成）+ **季度人工审**（标准档）/ 精简档仅 axe-core 扫
- **修补**：M7 完整修补遗留
- **范围**：Landing / Console / Docs（核心可见页面）；移动端 v1 桌面优先；**Tablet 768-1023px v1 Tier 1**（详 UX Spec Step 13）
- **6 a11y profile**（v1 起按 profile 测；详 UX Spec Step 13）：屏幕阅读器 / 键盘 / 高对比度 / 视觉低视力 / 运动障碍 / **Cognitive**（新增 v1）
- **Standard a11y Hook Wrapper**：`packages/ui` 统一封装 a11y hook + ARIA i18n consistency ESLint（详 UX Spec Step 13 AA6/AA12）

### 8. Localization & i18n

| 阶段 | 内容 |
|---|---|
| **v1（M1-M5）** | i18n 框架（next-intl + Accept-Language 中间件）**必上**；zh-CN 翻译完整；**en-US 关键页**（Landing / Pricing / 错误码 / 法律页）兜底 |
| v1.5（M6）| 全栈 en-US 翻译 |
| M9+ | 日 / 韩 / 西 / 阿（按海外 BD 启动决定）|

- **字符集**：UTF-8 / Unicode 14+
- **数字 / 日期 / 货币**：Intl 标准库（zh-CN ¥ / en-US $）
- **混合输入**：Chat 允许中英文混合，LLM 同语种回应

### 9. Browser & Platform Support

| 类型 | 支持范围 |
|---|---|
| 桌面浏览器 | Chrome / Edge / Safari / Firefox **latest 2 versions** |
| **移动端** | **iOS Safari latest 2** / Chrome Android latest 2 |
| **不支持** | IE / 老旧 Android < 8 |
| 桌面 OS | Windows / macOS / Linux（Console SSR + CSR）|

### 10. Observability & Monitoring（M3 起生效）

#### 10.1 必埋点业务指标

- `request_count` / `success_rate` / `latency_p50/p95/p99` 按 SKU × Provider 切分
- `credit_burn_rate` / `credit_refund_rate` 按用户 × 计划
- `chat_session_length` / `chat_turn_count` / `chat_solve_conversion_rate`
- `provider_route_distribution` / `provider_failure_rate`
- `repro_voucher_request_rate`
- `sandbox_violation_count` / `sandbox_timeout_count`
- `monthly_uptime`（v1 内部采集，v1.5 起对外）

#### 10.2 系统侧

- Prometheus + Grafana + Loki + OpenTelemetry
- 日志 30 天保留
- 标准档自建 / 精简档用 **Grafana Cloud free tier**

#### 10.3 状态页

- 公开 `status.opticloud.cn` **without authentication**（FR O1 配套）
- 用户可订阅 incident 邮件 / Webhook（FR O1 配套）

### 11. Cost & Unit Economics

#### 11.1 单 SKU 毛利约束

- **Variable 毛利率 ≥ 99%**（仅算 LLM / GPU / 带宽 + 算法核心）
- **Fully-loaded 毛利率 30-40%**（含人力 + 固定基础设施分摊）

#### 11.2 成本红线（v0.5.1 §22.9 配套）

| 红线 | 阈值 | 触发动作 |
|---|---|---|
| LLM API 月成本 / 月营收 | ≥ 30% | 调高 Chat 倍率或降级 LLM |
| GPU 闲置率 | ≥ 50% | 缩容 GPU 池 |
| Provider 分润 / 月营收 | ≥ 50% | 重谈分润比例 |
| 退款 Credits / 发行 Credits | ≥ 5% | 加强风控 |
| 现金流跑道 | < 6 个月 | 启动融资或砍成本 |

### 12. NFR 精简档兼容性

| 类别 | 标准档 | 精简档（=1-2 人）|
|---|:---:|:---:|
| §1 性能 SLO | ✅ M5 末达标 | ⚠️ M5 单元素监控 |
| §2.3 Critic 红队 | ✅ M3 ≥30 / M5 ≥200 | ✅ M3 ≥30 / M5 简化 100 |
| §4.2 灾备 | RTO 4h v2 | RTO 24h v1 + RPO 1h |
| §5.1 AIGC 备案中介 | ¥3-8 万 | ¥3-8 万（**必出预算**）|
| §5.1 等保二级 | ✅ M5 末取证 | ⚠️ 推迟 v1.5 取证 |
| §6 Provider Shadow | ✅ 完整 v2 | — |
| §7 WCAG | 设计时 + 季度人审 | **仅 axe-core 自动扫** |
| §10 可观测 | Grafana 自建 | Grafana Cloud free tier |
| §11 成本红线 | 全部监控 | ✅（更紧）|
