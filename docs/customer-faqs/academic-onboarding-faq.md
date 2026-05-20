# Academic Onboarding FAQ

> **Audience**：高校教师 / 研究员 / 博士后 / 课题组技术负责人  
> **Status**：M3 可发送版  
> **Last Updated**：2026-05-20

---

## 1. OptiCloud 想和学者合作什么？

OptiCloud 把优化与预测算法包装成可调用 API。学者提供算法思想、实现、样例和署名信息；OptiCloud 负责工程包装、上线验证、引用展示和后续运营。v1 期间走 Tier 1 手动 onboarding，不要求学者自己写 OpenAPI、Dockerfile 或灰度策略。

完整流程见 [`docs/academic-provider-handbook.md`](../academic-provider-handbook.md)。

## 2. 我需要先把算法做成产品吗？

不需要。Tier 1 只要求你提供可运行实现、依赖清单、sample input/output、适用范围和主要论文引用。OptiCloud 的 Lab 助手会把这些材料包装成平台 runner、OpenAPI 和 Dockerfile。

## 3. 我必须公开源代码吗？

不一定。是否开源由 Provider Agreement 和算法许可决定。默认原则是算法 IP 归原作者；OptiCloud 获得非独占调用和分发权，不转移你的 IP。若你选择 Apache 2.0 等开源方式，合同中会单独写明。

## 4. 分润怎么定？

正式比例以 Provider Agreement 为准。现有法律模板索引中的参考结构包括自研、合作课题组和商业 Provider 等不同分配模型，见 [`docs/legal-templates.md`](../legal-templates.md) Doc 6。FAQ 不替代合同。

## 5. 我的名字会出现在产品里吗？

可能。OptiCloud 使用三档 attribution：

| Tier | 展示方式 | 常见场景 |
|---|---|---|
| L1 | 明确显示 "Algorithm by ..." | 自研合作课题组、强品牌合作 |
| L2 | 自动附带 BibTeX | 一般学界 Provider |
| L3 | 仅遵守开源 license | 开源 Runner 算法 |

具体 tier 在合作时确认。Story 6.A.5 会把 attribution tier 工程化；当前 v1 先以文档和 BibTeX 方式落地。

## 6. BibTeX 怎么处理？

OptiCloud 会为上线算法准备可复制 BibTeX，并在 `/academic` 和算法详情页展示。你只需要审阅作者、机构、年份、venue、DOI / URL 和 citation key 是否准确。citation key 不应在论文或合作材料中自行改名。

可先访问 `/academic` 看现有引用展示方式。

## 7. 我能把 OptiCloud 结果写进论文吗？

可以。建议在方法或实验设置中说明使用了 OptiCloud 的对应算法 SKU，并粘贴平台提供的 BibTeX。中文写作起点见 [`docs/academic-paper-template.zh-CN.md`](../academic-paper-template.zh-CN.md)。

## 8. 5 年可复现是什么意思？

当前 FAQ 只能按现有 handbook 和法律模板语言说明：平台计划通过 image 归档和后续 reproducibility stories 继续 honor 5-year reproducibility / image archival 承诺。它不是说 v1 已经有 voucher rerun endpoint；Story 6.B 的 voucher / rerun 能力上线前，对外只能表述为合同和路线图承诺。

## 9. 学生数据会进入训练集吗？

默认不会。教学 / Classroom 场景下，学生输入属于学生，平台默认不进 Provider 训练集。教师可见进度和提交，但不默认下载学生原始数据。真实人类数据、医疗数据、心理测评数据等敏感场景需要 IRB 或校内伦理审批路径。

## 10. 我可以用于课堂教学吗？

可以讨论 v1 人工 cohort：学生用教育邮箱注册，平台手动发放 credits 或使用现有教育版额度。完整 Classroom Plan、LMS gradebook、课程码和自动作业管理是 v2+ 路线图，不应理解为当前已上线能力。

## 11. 支持 Canvas、Moodle、雨课堂或学堂在线吗？

这是 v2+ 路线图。当前可以在课程材料中放 `/academic`、算法页面或 Notebook 链接，但不承诺 LTI 1.3、gradebook 回传或 LMS SSO 已上线。

## 12. 什么时候可以上线？

Tier 1 的目标节奏是：

1. 首次沟通后收算法包和样例。
2. 本地复现成功后进入工程包装。
3. 完成 BibTeX、合同主体和 attribution 确认。
4. 工程团队做 14 天 shadow 验证和灰度。
5. 验证通过后进入 `/academic` 和算法目录的对外叙事。

具体时间取决于依赖复杂度、许可证和算法稳定性。

## 13. 如果算法失败或结果被误用怎么办？

上线前要明确适用范围、失败边界和不应宣传的场景。FAQ 不构成法律承诺；正式责任边界由 Provider Agreement、EULA、隐私政策和产品页面共同约束。

## 14. 联合白皮书是什么？

联合白皮书是合作课题组和 OptiCloud 对一个问题、算法和结果的共同叙事材料，可用于招生、会议交流、商业 BD 或案例展示。当前提供的是提纲，不是自动发表承诺。提纲见 [`docs/academic-joint-whitepaper-outline.zh-CN.md`](../academic-joint-whitepaper-outline.zh-CN.md)。

## 15. 下一步我要发什么给 OptiCloud？

请准备：

- 算法实现包
- 依赖清单和许可证信息
- 至少 2 组 sample input/output
- 主要论文 / 软件引用
- 作者和机构署名
- 适用范围和失败边界
- 合同主体信息

内部执行 checklist 见 [`docs/academic-provider-handbook.md`](../academic-provider-handbook.md)。
