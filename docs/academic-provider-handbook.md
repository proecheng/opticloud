# Academic Provider Handbook

> **Owner**：课题组 / Academic Relations Lead（v2 启用前 ramp up）<br>
> **Status**：M3 可执行版（Tier 1 手动 onboarding）<br>
> **关联架构**：`_bmad-output/planning/architecture.md` Appendix F2 / Gap CF6（PR1+PR6）<br>
> **关联 Innovation**：#3 学界变现 + 内容即产品（核心增长飞轮）<br>
> **Last Updated**：2026-05-20

---

## 快速入口

这份手册用于把目标学者从第一次沟通推进到 Tier 1 手动 Provider 合作。v1 期间不要求学者自己写 OpenAPI、Dockerfile、灰度策略或销售素材；OptiCloud 负责把可运行算法包装成平台 SKU，并把 BibTeX、/academic、FAQ、论文模板和白皮书提纲串成一套对外材料。

核心配套文档：

- 学者 FAQ：[`docs/customer-faqs/academic-onboarding-faq.md`](customer-faqs/academic-onboarding-faq.md)
- 中文论文模板：[`docs/academic-paper-template.zh-CN.md`](academic-paper-template.zh-CN.md)
- 联合白皮书提纲：[`docs/academic-joint-whitepaper-outline.zh-CN.md`](academic-joint-whitepaper-outline.zh-CN.md)
- 法务模板索引：[`docs/legal-templates.md`](legal-templates.md)
- Repro Image 恢复 SOP：[`docs/runbooks/repro-image-restore.md`](runbooks/repro-image-restore.md)
- 学术合作落地页：`/academic`

---

## 用途

OptiCloud Innovation #3 "学界变现 + 内容即产品" 是核心增长飞轮。本文档覆盖学者作为 Provider 的 v1 手动 onboarding 和 v2+ lifecycle：

- Tier 1 免门槛 onboarding（Founder / 课题组主动对接）
- Scholar supply checklist 与 OptiCloud supply checklist
- IP attribution 量化标准
- Classroom Plan 与 LMS 路线图
- 学者 lifecycle（在职 / 退休 / 转校 / 跨校合作 / 多作者 / 失联）
- 学生数据隐私与学术伦理
- 教学 / 研究 / 生产模式数据边界

---

## Tier 定义

### Tier 1：免门槛（v1 期间，当前可执行）

适用对象：已经有可运行算法实现、可提供 sample input/output、愿意审阅 BibTeX 和合作合同的目标学者或课题组。

OptiCloud 做：

- 主动对接目标学者，完成需求梳理和合作说明
- Lab 助手代写 OpenAPI、Dockerfile、sample runner、基础 README
- 工程团队执行 14 天 shadow 验证、灰度和上线检查
- 平台生成 / 审校 BibTeX，并在 `/academic` 和算法详情页展示
- 市场团队准备 FAQ、论文模板、联合白皮书提纲

学者做：

- 提供算法实现、依赖清单、样例输入输出和理论出处
- 确认算法适用范围、失败边界和不应宣传的场景
- 审阅 BibTeX、作者署名、机构署名和 attribution tier
- 配合法务签 Provider Agreement（见 `docs/legal-templates.md` Doc 6）

### Tier 2：自助（v2 启动后，路线图）

Tier 2 是 Provider Onboarding Portal，不是 v1 已上线能力。未来形态：

- Console 内 5-10 步引导
- OpenAPI 模板、Docker 模板、测试数据集下载
- 自动化评测工具（precision / recall / latency）
- 提交后进入 shadow validation

### Tier 3：合作伙伴（v3+ 高价值学者，路线图）

Tier 3 是高价值课题组 / 实验室合作包，不是 v1 已上线能力。未来形态：

- 课题组 / 实验室专属 Account Manager
- 联合白皮书 + 会议 / 招聘 / 校园活动支持
- 更强 IP attribution 与品牌露出

---

## Tier 1 Onboarding 流程

| 阶段 | Owner | 输出物 | 通过标准 |
|---|---|---|---|
| 1. 目标筛选 | Founder / Academic Relations Lead | 目标学者卡片 | 算法有明确应用场景、可演示、署名主体明确 |
| 2. 首次沟通 | Founder | 30 分钟 call notes | 学者理解 OptiCloud 只获得调用 + 分发权，不转移 IP |
| 3. 技术 handoff | 学者 + Lab 助手 | 算法包、依赖、sample input/output | 本地可复现一次成功运行 |
| 4. Citation handoff | 学者 + 平台 | BibTeX、作者署名、机构署名 | 学者确认 key、作者和 venue 无误 |
| 5. Legal handoff | Founder + 法务 | Provider Agreement 签署路径 | 分润、IP、退出、5y Image 归档条款清楚；起算点为 `reproduction_vouchers.created_at` UTC |
| 6. Shadow 验证 | 工程团队 | 14 天验证记录 | 结果稳定、失败边界明确、无合规 blocker |
| 7. 上线准备 | 工程 + 市场 | `/academic` 引用、FAQ、论文模板、白皮书提纲 | 外部学者能读懂合作方式和引用方式 |
| 8. 上线后跟进 | Academic Relations Lead | 30/60/90 day follow-up | 引用追踪、反馈、案例素材进入节奏 |

---

## 首次沟通脚本

目标：让学者在 30 分钟内知道合作门槛、收益、风险边界和下一步材料。

建议结构：

1. 5 分钟说明 OptiCloud：优化 / 预测算法 API 平台，学术引用是一等公民。
2. 5 分钟说明学者收益：BibTeX 曝光、/academic 展示、潜在分润、白皮书合作。
3. 10 分钟确认算法：解决什么问题、输入输出、依赖、失败场景、已有论文。
4. 5 分钟确认边界：IP 不转移、平台获得非独占调用 + 分发权、v1 由 OptiCloud 代做工程包装。
5. 5 分钟确认下一步：收算法包、样例、署名信息、合同主体、FAQ 链接。

首次沟通后发送：

- 学者 FAQ
- `/academic` 页面
- 中文论文模板
- 联合白皮书提纲
- Provider Agreement 条款索引（不是正式合同正文）

---

## Scholar Supply Checklist

学者必须提供：

- 算法实现包（Python 包、脚本、Notebook 或容器均可）
- 依赖清单（版本号、许可证、是否含 EPL / GPL / 商业求解器）
- 至少 2 组 sample input/output
- 算法适用范围和不适用范围
- 主要论文 / 软件引用信息
- 作者署名、机构署名、ORCID（如有）
- Provider 合同主体（个人、课题组事业单位、公司主体）

学者可选提供：

- 论文图表、benchmark 数据、公开 demo 数据
- 课程 / 教学使用场景
- 期望 attribution tier
- 联合白皮书主题建议

OptiCloud 不应要求学者在 Tier 1 阶段提供：

- OpenAPI spec
- Dockerfile
- CI / CD 配置
- 灰度策略
- 营销落地页文案

---

## OptiCloud Supply Checklist

OptiCloud 必须提供：

- Tier 1 技术包装：OpenAPI、Dockerfile、runner、README
- Shadow 验证计划和上线记录
- BibTeX 草案与 `/academic` 展示入口
- 学者 FAQ、中文论文模板、联合白皮书提纲
- Provider Agreement 路径和法务接口人
- 上线后的 30/60/90 day follow-up 节奏

OptiCloud 不应承诺：

- v1 已有自助 Provider Portal
- v1 已有 LMS 集成
- v1 已有 voucher rerun endpoint
- 未经法务签字的收入分配或知识产权例外条款

---

## Citation 与 /academic

Story 6.A.1 已经把每个算法的 citation.bibtex 做成平台数据面。Story 6.A.2 已经提供 `/academic` 展示面。Tier 1 onboarding 中必须把两者当作学界合作的证明材料：

- 每个候选算法必须有一个可审的 BibTeX 草案。
- 学者只审阅引用准确性，不需要理解平台代码。
- Citation key 不允许在合作材料里自行改名。
- `/academic` 是对外展示入口；FAQ、论文模板、白皮书提纲都指向它。

对外话术：

> OptiCloud 不只把算法封装成 API，也把引用方式封装成平台能力。你只需要确认作者、机构、年份、venue 和 BibTeX 是否准确；上线后学者用户可以直接复制引用。

---

## IP Attribution 量化标准

| Tier | 形式 | 触发条件 |
|---|---|---|
| L1 - Full Visible Attribution | NL Summary / Dashboard 显示 "Algorithm by Prof. Lü et al., TJU Trust-Tech Lab" | 自研合作课题组、强品牌合作、联合白皮书项目 |
| L2 - Standard BibTeX | BibTeX 自动附带；NL Summary 不显式提及作者 | 一般 Provider，作者较多或品牌露出需克制 |
| L3 - License-Only | 仅遵守开源 license 要求 | 开源 Runner 算法，如 HiGHS / OR-Tools |

默认规则：

- 学界合作 Provider：L1 或 L2，由合同和署名确认决定。
- 商业 Provider：L2 only，除非另签营销合作。
- 开源 Runner：L3。

Story 6.A.5 已将 attribution tier 工程化到算法 catalog、API 响应、`/academic`、算法详情页和 Console review surface。本手册继续作为 Tier 选择和合同沟通的文字源头；具体例外条款仍以 Provider Agreement 为准。

---

## Classroom Plan 管理（路线图）

Classroom Plan 是 v2+ 教学产品能力，不是 Tier 1 当前上线能力。当前沟通中只能说明方向：

- 教师 master account 邀请学生
- 学生教育邮箱注册和课程码加入
- 共享 Credits 池
- 教师 dashboard 查看进度
- 学生数据不进入 Provider 训练集

如果学者当前就要教学使用，v1 处理方式是人工 cohort：

- Founder / Academic Relations Lead 建课程名单
- 学生通过教育邮箱注册
- 手动发放 credits 或使用现有教育版额度
- 不承诺 LMS gradebook 或自动课程管理

---

## LMS 集成（路线图）

v2 目标 LMS：

| LMS | 形式 | 目标时间 |
|---|---|---|
| Canvas | LTI 1.3 集成 | M9-M10 |
| Moodle | LTI 1.3 集成 | M10-M11 |
| 学堂在线 / 雨课堂 | API 集成 | M11-M12 |

对外说明必须使用"计划 / 路线图 / 评估中"，不得说"已支持"。

---

## 学者 Lifecycle

### 在职阶段

- 标准 Provider Agreement
- 月度分润按合同执行
- IP attribution L1 / L2 按协议选择

### 退休 / 转校

需要 30 day 预通知给 OptiCloud。可选路径：

- Option A：算法 IP 转课题组 / 学校，继续分润给课题组事业单位主体。
- Option B：算法 IP 转学者个人，改走个人税务路径。
- Option C：算法转为开源 Apache 2.0，OptiCloud 继续 honor 已签发 voucher 的 5y Image 归档承诺；每个 voucher 的 5 年时钟从 `reproduction_vouchers.created_at` UTC 起算，分润停止。

### 跨校合作（多作者）

- 必须指定主负责人。
- 必须确认分配比例，例如 50/30/20。
- 退出由主负责人发起；争议进入 ADR 协调。

### 离世 / 失联

- 算法继续 honor 已签发 voucher 的 5y Repro / Image 归档承诺；每个 voucher 的 5 年时钟从 `reproduction_vouchers.created_at` UTC 起算。
- 分润转为遗产或课题组事业单位主体，按合同条款执行。

5-year reproducibility / image archival 的合同和运营口径：每个 durable voucher 的 5 年时钟从 `reproduction_vouchers.created_at` UTC 起算。rerun child voucher 使用 child voucher 自己的 `created_at` 起算，不会延长或重置 parent voucher 的承诺。恢复操作按 [`docs/runbooks/repro-image-restore.md`](runbooks/repro-image-restore.md) 记录证据或异常。对外材料不得暗示尚未上线的 archive pipeline 已经完整交付。

---

## 学生数据隐私 + 学术伦理

学生数据：

- 学生输入 = 学生所有。
- 平台默认不进入训练集。
- 教师可见进度和提交，不默认下载学生原始数据。
- Classroom 数据与生产数据分离。

学术伦理：

- 涉及真实人类数据时，学者必须提供 IRB approval 或校内伦理审批路径。
- 涉及医疗、心理、教育测评等敏感数据时，v1 默认只接受脱敏样例。
- 涉及真实企业数据时，学校 + 企业 + 学生三方授权必须先完成。

FAQ 只能解释这些边界，不能替代正式合同或伦理审查。

---

## 教学 / 研究 / 生产模式

| 模式 | 数据边界 | 算例规模 | 计费语言 |
|---|---|---|---|
| 教学模式（mode=teaching） | 教学专用 cohort，不进 Provider 训练集 | 小规模 / 教材算例 | 可讨论教学折扣，具体以产品计划为准 |
| 研究模式（mode=research） | 学位论文 / 论文实验数据 | 论文级 benchmark | 使用教育版额度或合同约定 |
| 生产模式（mode=production） | 企业实习 / 真实生产数据 | 真实生产规模 | 标准计费，不默认享教育折扣 |

v1 不要求系统层面 mode 字段已经上线；这是学界合作沟通和未来 capability-registry 的词汇边界。

---

## 学界 KPI

M5 前：

- 签约 ≥ 2 所高校
- 学生用户 ≥ 50（持续 ≥ 3 月）
- 至少 1 个算法进入 `/academic` 对外叙事材料

M7 前：

- 签约 ≥ 3 所高校
- 累计师生用户 ≥ 50 持续 ≥ 3 月

M9+：

- BibTeX 自动追踪 ≥ 5 篇论文引用
- Classroom Plan 使用 ≥ 5 门课程

---

## Timeline

| 阶段 | 必须完成 |
|---|---|
| M0 wk2 | 吕老师等签 Apache 2.0 + 学界合作合同 v1（Tier 1 手动模式） |
| M3 起 | Tier 1 Onboarding 上线：创始人主动对接 2-3 学者 |
| M5 前 | 累计签约 ≥ 2 高校 + 50 师生用户持续 ≥ 3 月 |
| v2 启动（M9+） | Provider Onboarding Portal + LMS 集成 + Classroom Plan 完整 |
| v3+ | Tier 3 合作伙伴 + 学界品牌建设 |

---

## 责任清单

| 角色 | 责任 |
|---|---|
| 课题组创始人 | 学者关系、首次沟通、战略合作签约 |
| Academic Relations Lead | Provider onboarding、FAQ 维护、follow-up 节奏 |
| 法务律师 | Provider Agreement、IP 归属、退出条款审定 |
| 工程团队 | OpenAPI / Dockerfile / runner / shadow 验证 |
| 市场 | `/academic`、联合白皮书、案例素材、会议合作 |
| 学者 / 课题组 | 算法、样例、署名、理论边界、伦理审批材料 |

---

## 对外交付包

首次沟通后可发送：

- [`Academic Onboarding FAQ`](customer-faqs/academic-onboarding-faq.md)
- [`中文论文模板`](academic-paper-template.zh-CN.md)
- [`联合白皮书提纲`](academic-joint-whitepaper-outline.zh-CN.md)
- `/academic`
- `docs/legal-templates.md` 中的 Provider Agreement 条款索引

---

## 关联文档

- FAQ：[`docs/customer-faqs/academic-onboarding-faq.md`](customer-faqs/academic-onboarding-faq.md)
- 中文论文模板：[`docs/academic-paper-template.zh-CN.md`](academic-paper-template.zh-CN.md)
- 联合白皮书提纲：[`docs/academic-joint-whitepaper-outline.zh-CN.md`](academic-joint-whitepaper-outline.zh-CN.md)
- 法律合作合同：[`docs/legal-templates.md`](legal-templates.md) Doc 6
- Repro Image 恢复 SOP：[`docs/runbooks/repro-image-restore.md`](runbooks/repro-image-restore.md)
- Runbooks：[`docs/runbooks/`](runbooks/)
- PRD / Architecture 学界规划：`_bmad-output/planning/prd.md`、`_bmad-output/planning/architecture.md`
