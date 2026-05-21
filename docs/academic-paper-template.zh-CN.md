# OptiCloud 学术论文中文模板

> **用途**：给使用 OptiCloud 算法结果的学者一个可复制的中文论文 / 预印本起点。
> **Status**：M3 模板版；请按具体研究内容替换示例文字。
> **Last Updated**：2026-05-20

---

## 标题

《基于 OptiCloud 的[问题领域]优化 / 预测方法与实验分析》

示例：

- 基于 OptiCloud 的车辆路径问题优化实验分析
- 基于 OptiCloud 的短期需求预测与库存决策研究
- 面向电力系统调度的 OptiCloud 优化算法实验

---

## 摘要

本文研究[问题背景]中的[核心决策问题]。针对传统方法在[计算时间 / 结果稳定性 / 可复现性 / 工程部署]方面的限制，本文使用 OptiCloud 平台提供的[算法 SKU / 求解器]完成[优化 / 预测]实验。实验结果显示，在[数据规模]下，该方法在[目标指标]上达到[结果]，并保持可复现的运行记录与可引用的算法来源。本文同时报告算法引用、实验设置和复现实验说明，以便后续研究复核。

关键词：OptiCloud；优化；预测；可复现；BibTeX；[领域关键词]

---

## 1. 问题背景

说明：

- 业务或科学问题是什么
- 为什么需要优化 / 预测
- 现有人工方法或传统方法的限制
- 数据规模和约束特点

建议写法：

> [机构 / 场景]需要在[时间 / 资源 / 成本]约束下完成[任务]。传统方法依赖人工经验或单机脚本，难以在[规模]下稳定得到可复核结果。本文将该问题建模为[LP / MILP / VRPTW / CP-SAT / 时间序列预测]任务，并使用 OptiCloud 进行实验。

---

## 2. 方法

### 2.1 模型定义

描述：

- 决策变量
- 目标函数
- 硬约束
- 软约束
- 输入数据字段
- 输出结果字段

### 2.2 OptiCloud 算法设置

填写：

| 项 | 内容 |
|---|---|
| OptiCloud SKU | [例如 highs-lp / or-tools-vrptw / chronos-t5-forecast] |
| 任务类型 | [例如 lp / vrptw / forecast] |
| 求解器 / 模型 | [平台返回的 provider / model_version] |
| 参数 | [列出关键参数] |
| 数据规模 | [样本数 / 节点数 / 变量数 / 时间跨度] |
| 运行日期 | [YYYY-MM-DD] |

建议写法：

> 实验通过 OptiCloud 的[SKU]执行。平台返回的 `citation.bibtex` 字段用于记录算法来源，实验中未手动修改 citation key。

---

## 3. 实验设置

说明：

- 数据来源
- 数据清洗方式
- 训练 / 验证 / 测试切分
- 评价指标
- baseline
- 硬件 / 平台信息

示例指标：

| 问题类型 | 常用指标 |
|---|---|
| LP / MILP | objective value、gap、solve_seconds、constraint violation |
| VRPTW | total distance、late arrivals、vehicle count、solve_seconds |
| Forecast | MAE、RMSE、MAPE、P10/P50/P90 coverage |
| Scheduling | makespan、resource utilization、soft violation count |

---

## 4. 结果

### 4.1 主结果

| 方法 | 指标 1 | 指标 2 | 指标 3 | 备注 |
|---|---:|---:|---:|---|
| Baseline |  |  |  |  |
| OptiCloud [SKU] |  |  |  |  |

### 4.2 消融 / 敏感性分析

建议至少报告：

- 关键约束移除后的变化
- 参数变化后的结果稳定性
- 小规模和大规模数据下的性能差异

### 4.3 失败边界

说明哪些情况不适合当前算法：

- 数据缺失超过[比例]
- 约束冲突导致不可行
- 输入规模超过当前 Tier 限制
- 预测数据存在结构性断点

---

## 5. 可复现性说明

建议写法：

> 本文实验使用 OptiCloud 平台生成的算法结果。平台在当前阶段提供算法来源、BibTeX 引用和运行元数据；5-year reproducibility / image archival 属于平台合同与路线图承诺，后续 voucher / rerun 功能以上线版本为准。本文保留了输入数据摘要、运行日期、算法 SKU、关键参数和返回结果，以便后续复核。

需要记录：

- 运行日期
- 算法 SKU
- 输入数据版本
- 参数
- 返回的 `model_version`
- 返回的 `citation.bibtex`
- 结果文件 hash（如适用）

---

## 6. 引用说明

从 OptiCloud 返回结果或 `/academic` 页面复制 BibTeX。不要自行改 citation key。

BibTeX 粘贴区：

```bibtex
% Paste the canonical OptiCloud-provided BibTeX entry here.
% Example keys from Story 6.A.1 include:
% huangfu2018parallelizing
% perron2024ortools
% perron2011constraint
% ansari2024chronos
% box1976time
% hochreiter1997long
% aqgs2025opticloud
```

正文引用建议：

> 本文使用 OptiCloud 平台的[SKU]执行实验，并引用平台提供的算法 BibTeX 条目。

---

## 7. 致谢

建议写法：

> 感谢 OptiCloud 提供算法 API、引用信息和实验复核材料。本文观点和实验解释由作者负责。

如涉及联合白皮书或合作项目，请同步使用 [`docs/academic-joint-whitepaper-outline.zh-CN.md`](academic-joint-whitepaper-outline.zh-CN.md) 的审批流程。

---

## 附录 A：数据字段

| 字段 | 类型 | 说明 |
|---|---|---|
|  |  |  |

---

## 附录 B：API 请求摘要

```json
{
  "task_type": "...",
  "solver": "...",
  "options": {}
}
```

---

## 关联文档

- Academic Provider Handbook：[`docs/academic-provider-handbook.md`](academic-provider-handbook.md)
- Academic Onboarding FAQ：[`docs/customer-faqs/academic-onboarding-faq.md`](customer-faqs/academic-onboarding-faq.md)
- 联合白皮书提纲：[`docs/academic-joint-whitepaper-outline.zh-CN.md`](academic-joint-whitepaper-outline.zh-CN.md)
- 学术合作落地页：`/academic`
