# Academic Provider Handbook

> **Owner**：课题组 / Academic Relations Lead（v2 启用前 ramp up）
> **Status**：🚧 骨架 / Skeleton（v2 启用前 ready）
> **关联架构**：`_bmad-output/planning/architecture.md` Appendix F2（未来拆出）/ Gap CF6（PR1+PR6）
> **关联 Innovation**：#3 学界变现 + 内容即产品（核心增长飞轮）
> **Last Updated**：2026-05-17

---

## 📋 用途

OptiCloud Innovation #3 "学界变现 + 内容即产品" 是核心增长飞轮（70-80% 估值贡献之一）。本文档覆盖**学者作为 Provider 的全 lifecycle**：

- Onboarding 扶持流程（降低 OpenAPI + Docker 门槛）
- IP attribution 量化标准
- Classroom Plan 管理工具
- LMS（Canvas / Moodle / 雨课堂 / 学堂在线）集成
- 学者 lifecycle 全设计（在职 / 退休 / 转校 / 跨校合作 / 多作者）
- 学生数据隐私与学术伦理
- 教学 vs 研究 vs 生产模式三种数据隔离

---

## 🎯 学者 Onboarding 扶持流程

### Tier 1：免门槛（v1 期间）

- 创始人 + 课题组成员**主动对接**目标学者
- **Lab 助手代写 OpenAPI + Dockerfile**（学者只提供 Python 包 + sample input）
- 14 天 shadow 验证 + 灰度（FR P2/P3）由 OptiCloud 工程团队执行
- 学者只需：签 Provider 合同 + 提供算法实现 + 审 BibTeX

### Tier 2：自助（v2 启动后）

- Provider Onboarding Portal（Console 内）
- Step-by-step 引导（5-10 步）
- OpenAPI 模板 + Docker 模板下载
- 测试数据集 + sample 输入输出
- 自动化评测工具（precision / recall / latency）

### Tier 3：合作伙伴（v3+ 高价值学者）

- 课题组 / 实验室专属 Account Manager
- 联合白皮书 + 营销支持
- 会议 / 招聘合作

---

## 🏷️ IP Attribution 量化标准

### 三种 Attribution Tier

| Tier | 形式 | 触发条件 |
|---|---|---|
| **L1 - Full Visible Attribution** | 每次调用 NL Summary / Dashboard 显示 "Algorithm by Prof. Lü et al., TJU Trust-Tech Lab" | 自研合作课题组（Innovation #6 AQGS / Trust-Tech 等）|
| **L2 - Standard BibTeX** | BibTeX 自动附带；NL Summary 不显式提及作者 | 一般 Provider（≥3 名作者，难全列）|
| **L3 - License-Only** | 仅遵守开源 license 要求（MIT / Apache / BSD）| 开源 Runner 算法（HiGHS / OR-Tools 等）|

### 学者协议默认 Tier

- 学界合作 Provider（≥1 学者主创）：**L1 或 L2 用户可选**
- 商业 Provider：**L2 only**（不强制 visible attribution）
- 开源 Runner：L3

---

## 📚 Classroom Plan 管理

### 学生账户管理

- **教师持有 master account** + 邀请学生（最多 200 学生 / 5 学期 lifecycle）
- 学生 self-service 注册（教育版邮箱 + 加入课程码）
- 共享 Credits 池（教师配额，学生消耗）+ 教师 dashboard 实时查看

### 助教权限

- 教师可指定 ≤ 5 名助教
- 助教权限：管理学生账户 / 查看进度 / 审核作业（但不能管 billing）

### Classroom 模式数据隔离

- Classroom 内学生数据 **不进入** Provider 训练集
- 学生提交作业作为 **教学专用数据**（与生产 separate）
- 课程结束自动归档（学生 Credits 转个人账户）

---

## 🔗 LMS（学习管理系统）集成

### v2 启用：3 个主要 LMS

| LMS | 形式 | v2 月份 |
|---|---|:---:|
| **Canvas** | LTI 1.3 集成 | M9-M10 |
| **Moodle** | LTI 1.3 集成 | M10-M11 |
| **学堂在线 / 雨课堂** | API 集成（自有标准）| M11-M12 |

### 集成功能

- **SSO（Single Sign-On）**：学生用学校账号登录 OptiCloud
- **成绩回传**：OptiCloud 作业结果 → LMS gradebook
- **作业分发**：教师在 LMS 创建作业 → OptiCloud 自动创建对应 SKU template
- **资源链接**：LMS 课程页面嵌入 OptiCloud Notebook Colab 链接

---

## 👤 学者 Lifecycle 全设计

### 在职阶段

- 标准 Provider 合同 + 月度分润
- IP attribution L1 / L2 用户可选

### 退休 / 转校

- **30 day 预通知**给 OptiCloud
- **Handover 流程**：
  - **Option A**：算法 IP 转课题组 / 学校（继续分润给课题组事业单位主体）
  - **Option B**：算法 IP 转学者个人（个人税务路径）
  - **Option C**：算法转为开源 Apache 2.0（OptiCloud 继续 honor 5y SLA，分润停止）
- **Repro 5y SLA 继续 honor**（无论 handover 后归属）

### 跨校合作（多作者）

- **主负责人**指定（Provider 协议必填）+ 分配比例（如 50/30/20 三作者）
- 月度分润按比例自动分到不同账户
- 退出由主负责人决策（其他作者反对 → ADR 协调）

### 离世 / 失联

- 算法**继续 honor 5y Repro**
- 分润转为**遗产 / 课题组事业单位主体**（依合同条款）

---

## 🔐 学生数据隐私 + 学术伦理

### 学生数据隐私（PIPL 兼容）

- 学生输入 = 学生所有
- 平台**默认不进训练集**（与一般用户一致）
- 教师可见学生进度 + 提交，**不可下载学生原始数据**（除非学生同意）

### 学术伦理（IRB / 校内审查）

- 涉及**真实人类数据**（如医疗 / 心理实验）的算法必须：
  - 学者提供 IRB approval 证明
  - 学生使用时签 informed consent
  - OptiCloud 平台不存储原始敏感数据（仅 hash + 元数据）
- 涉及**真实企业数据**（学生实习项目）：
  - 学校 + 企业 + 学生三方协议
  - 数据脱敏后才能进入 OptiCloud

---

## 🎓 教学 vs 研究 vs 生产模式三种数据隔离

| 模式 | 数据隔离 | 算例规模 | 计费 |
|---|---|---|:---:|
| **教学模式**（mode=teaching）| 学生数据 / 教学专用 sandbox | 6-bus 简化 / 小规模 | 50% 折扣（FR O8）|
| **研究模式**（mode=research）| 学位论文研究数据 / IRB 验证 | 论文级（9-bus / 118-bus 等）| 教育版 Credits |
| **生产模式**（mode=production）| 企业实习项目数据 / 三方协议 | 真实生产规模 | 标准计费（不享教育版折扣）|

技术实现：在 capability-registry 内增加 mode metadata + 计费 differentiator。

---

## 💰 跨校合作分润主体（法务联动）

### 分润主体类型

| 主体类型 | 适用 | 税务路径 |
|---|---|---|
| **课题组事业单位**（学校托管账户）| 学校体制内合作 | 学校财务接收，按 service fee |
| **学者个人**（自然人）| 灵活合作 | 个税申报 |
| **学者注册公司**（如 lab spinoff）| 商业化路径 | 增值税开票 + 公司账户 |

### 合作协议关键条款（法务联动 → `docs/legal-templates.md` Doc 6）

- 分润主体明示
- 跨校 / 多作者分配比例
- 退休 / 转校 / 离世 handover
- IP 归属（不转移 OptiCloud）

---

## 📈 学界 KPI（与商业 KPI 平行）

### M5 前

- 签约 ≥ 2 所高校
- 学生用户 ≥ 50（持续 ≥ 3 月）

### M7 前

- 签约 ≥ 3 所高校
- 累计师生用户 ≥ 50 持续 ≥ 3 月

### M9+

- BibTeX 自动追踪 ≥ 5 篇论文引用
- Classroom Plan 使用 ≥ 5 门课程

---

## 📅 实施 Timeline

| 阶段 | 必须完成 |
|---|---|
| **M0 wk2** | 吕老师等签 Apache 2.0 + 学界合作合同 v1（Tier 1 手动模式）|
| **M3 起** | Tier 1 Onboarding 上线（创始人主动对接 2-3 学者）|
| **M5 前** | 累计签约 ≥ 2 高校 + 50 师生用户持续 ≥ 3 月 |
| **v2 启动（M9+）** | Provider Onboarding Portal + LMS 集成 + Classroom Plan 完整 |
| **v3+** | Tier 3 合作伙伴 + 学界品牌建设 |

---

## 🤝 责任清单

| 角色 | 责任 |
|---|---|
| **课题组创始人** | 学者关系 + 战略合作签约 |
| **Academic Relations Lead**（v2 招聘）| Provider Onboarding + 日常运营 |
| **法务律师** | 合作合同 + IP 归属审定 |
| **工程团队** | Provider Onboarding Portal + LMS 集成开发 |
| **市场** | 学界 PR + 会议 sponsor + 校园活动 |

---

## 🔗 关联文档

- 架构 学界 锚点：`_bmad-output/planning/architecture.md` § Innovation #3 / FR R5-R7 / FR P1-P8 / FR O8 / FR O11
- 法律合作合同：`docs/legal-templates.md` Doc 6
- Runbooks 应急：`docs/runbooks/`
- PRD 学界规划：`_bmad-output/planning/prd.md` § Innovation Ranking + Journey 4
