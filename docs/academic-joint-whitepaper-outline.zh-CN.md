# OptiCloud 学界联合白皮书提纲

> **用途**：给合作课题组、市场和 Founder 一份联合白皮书 / 案例研究的结构化起点。
> **Status**：M3 提纲版；不是 finished publication。
> **Last Updated**：2026-05-20

---

## 1. 白皮书定位

白皮书用于把学术算法、OptiCloud 工程化能力和真实应用场景合成一份对外叙事材料。它可以服务于：

- 学者招生 / 学术影响力展示
- OptiCloud 商业 BD
- 会议交流
- 课程案例
- 媒体或投资人说明

它不是论文替代品，也不自动承诺发表。正式论文请使用 [`docs/academic-paper-template.zh-CN.md`](academic-paper-template.zh-CN.md) 作为起点。

---

## 2. 目标读者

选择一个主读者，不要同时讨好所有人：

| 主读者 | 关注点 | 推荐语气 |
|---|---|---|
| 高校教师 / 研究员 | 方法可信、引用准确、可复现 | 学术严谨 |
| 企业算法 / 数据团队 | ROI、迁移成本、接口稳定性 | 工程务实 |
| 投资人 / 合作方 | 增长飞轮、差异化、可规模化 | 商业简洁 |
| 学生 / 课程参与者 | 学习路径、实验复核、样例数据 | 教学友好 |

---

## 3. 标题模板

可选：

- 《从论文算法到可调用 API：[课题组] × OptiCloud 的[领域]优化实践》
- 《让[算法名称]服务真实[行业]问题：OptiCloud 联合白皮书》
- 《可复现、可引用、可上线：[问题领域]算法工程化案例》

---

## 4. 一页摘要

必须回答：

- 解决什么问题
- 为什么现在值得解决
- 学者贡献是什么
- OptiCloud 贡献是什么
- 实验或业务结果是什么
- 读者下一步可以做什么

建议格式：

> 本白皮书介绍[课题组 / 学者]与 OptiCloud 在[问题领域]的合作。课题组提供[算法 / 理论 / benchmark]，OptiCloud 提供工程包装、API 服务、引用展示和后续追踪。初步结果显示，在[数据规模]下，该方案实现[指标提升]，并通过 `/academic` 和平台 BibTeX 机制保留算法引用路径。

---

## 5. 问题与场景

说明：

- 行业或科研问题
- 决策变量和约束
- 传统方式的痛点
- 为什么不能只靠人工经验或单机脚本
- 为什么这个问题适合 OptiCloud

产出物：

- 场景图或流程图
- 输入 / 输出表
- 约束清单
- 读者能理解的例子

---

## 6. 方法与协作分工

| 工作项 | 学者 / 课题组 | OptiCloud |
|---|---|---|
| 算法理论 | 提供核心方法、适用范围、论文引用 | 转成平台可读说明 |
| 算法实现 | 提供代码、依赖、样例 | 包装 runner、OpenAPI、Dockerfile |
| 实验设计 | 提供 benchmark 和评价指标 | 执行平台实验和结果记录 |
| 引用展示 | 审 BibTeX、作者、机构 | 在 `/academic` 和算法页面展示 |
| 风险边界 | 确认失败场景和伦理边界 | 写入 FAQ / 白皮书限制说明 |
| 对外发布 | 审学术准确性 | 审品牌、产品和合规措辞 |

---

## 7. 实验与结果

至少包含：

- 数据规模
- baseline
- OptiCloud SKU / solver
- 关键参数
- 结果指标
- 解读
- 失败边界

表格模板：

| 方法 | 指标 1 | 指标 2 | 指标 3 | 备注 |
|---|---:|---:|---:|---|
| Baseline |  |  |  |  |
| 学者算法 + OptiCloud |  |  |  |  |

不要只写"效果显著"。必须写可复核数字或明确说明目前只是 qualitative result。

---

## 8. 引用与 Attribution

必须写清：

- Citation key 来自 OptiCloud 提供的 canonical BibTeX。
- 不自行改名 citation key。
- Attribution tier 由合作协议确认。
- `/academic` 是外部读者查看引用和学术合作说明的入口。

推荐文案：

> 本白皮书中涉及的算法引用以 OptiCloud `/academic` 和 API 返回的 `citation.bibtex` 为准。作者、机构、年份和 citation key 已由合作课题组审阅。

---

## 9. 可复现性与限制

说明：

- 当前记录了哪些运行元数据
- 哪些数据可公开，哪些不能公开
- 5-year reproducibility / image archival 是合同和路线图承诺
- Story 6.B voucher / rerun endpoint 未上线前，不写成已可自助重跑
- 学生数据、企业数据、人类受试者数据的边界

---

## 10. 发布审批流程

| 阶段 | Owner | 通过标准 |
|---|---|---|
| 1. 提纲确认 | Founder + 学者 PI | 主题、读者、目标明确 |
| 2. 技术事实审查 | 学者 / 工程团队 | 算法、结果、限制准确 |
| 3. 引用审查 | 学者 / Academic Relations Lead | BibTeX、作者、机构无误 |
| 4. 法务 / 合规审查 | 法务 | IP、学生数据、伦理、合同边界无冲突 |
| 5. 品牌审查 | 市场 / Founder | 标题、摘要、CTA、/academic 链接正确 |
| 6. 发布决策 | Founder + 学者 PI | publish / hold / internal-only |

---

## 11. Publish / Hold 决策点

可以发布：

- 数据可公开或已脱敏
- 作者和机构署名已确认
- Citation key 已确认
- 没有未签字的 IP 或分润争议
- 结果可复核，不夸大

必须暂停：

- 涉及未审批的人类受试者数据
- 企业真实数据未获得授权
- 算法许可不清楚
- 结果无法复现
- 学者、学校或合作方未批准公开

---

## 12. CTA

白皮书末尾只放 1-2 个动作：

- 访问 `/academic` 查看 OptiCloud 学术引用和合作方式。
- 联系 Academic Relations Lead 提交算法合作意向。

不要放过多销售 CTA；学界材料优先保持可信。

---

## 关联文档

- Academic Provider Handbook：[`docs/academic-provider-handbook.md`](academic-provider-handbook.md)
- Academic Onboarding FAQ：[`docs/customer-faqs/academic-onboarding-faq.md`](customer-faqs/academic-onboarding-faq.md)
- 中文论文模板：[`docs/academic-paper-template.zh-CN.md`](academic-paper-template.zh-CN.md)
- 法务模板索引：[`docs/legal-templates.md`](legal-templates.md)
- 学术合作落地页：`/academic`
