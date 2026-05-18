# Safety papers index

更新日期：2026-05-04
用途：MicroGrid Safety Edge / EdgeSentry 技术底座研究资料。重点关注微网保护、逆变器型资源、保护协调、动态状态估计、ML 故障识别、网络安全和 fail closed。

## 已下载全文或公开 PDF

| 文件 | 主题 | 与 MicroGrid 的关系 | 来源 |
| --- | --- | --- | --- |
| `comparative-framework-ac-microgrid-protection-2023.pdf` | AC microgrid protection schemes review：挑战、方案、真实应用和趋势 | 安全底座总体框架：短路电流变化、双向潮流、孤岛/并网模式、保护失配 | Protection and Control of Modern Power Systems open access |
| `singh-2017-protection-coordination-with-without-der-review.pdf` | 有/无 DER 的保护协调 review | 说明 DER 介入后保护协调和故障电流口径改变，适合做安全规则基线 | Protection and Control of Modern Power Systems open access |
| `adaptive-protection-communications-review-2020.pdf` | 微网通信辅助/自适应保护 review | 对应 EdgeSentry 的策略包版本、拓扑模式、并网/孤岛模式切换 | arXiv |
| `chalmers-review-challenges-solutions-microgrid-protection.pdf` | Microgrid protection challenges and solutions review | 补充低故障电流、保护盲区、选择性和通信依赖问题 | Chalmers open full text |
| `dynamic-state-estimation-radial-microgrid-protection-2021.pdf` | Dynamic State Estimation for radial microgrid protection | 可作为 Safety Edge 后续高级检测模块：用状态估计区分正常/故障参数 | IEEE/IAS public PDF |
| `ml-based-protection-fault-identification-100-percent-inverter-microgrids-2024.pdf` | 100% inverter-based microgrid 的 ML fault detection/type identification | 给逆变器型微网的本地故障识别提供候选路线，但需要严格 shadow 验证 | arXiv |
| `protection-and-cybersecurity-in-inverter-based-microgrids-vt-thesis.pdf` | Inverter-based microgrid protection + cybersecurity dissertation | 将保护、FDI attack、分布式控制和 fault-tolerant control 连接起来 | Virginia Tech open dissertation |
| `abdul-rahim-2019-protection-coordination-network-reconfiguration-dg-sizing.pdf` | 网络重构/DG 定容中的保护协调约束 | 对项目包/资源拓扑变更后的保护约束检查有参考价值 | open PDF mirror |

## 未下载但保留线索

| 论文/线索 | 状态 |
| --- | --- |
| MDPI Energies 2023 green distributed generation protection schemes review | 原站 403，大学仓储超时；后续可人工下载 |
| OSTI adaptive microgrid protection review | 网络超时；后续可人工下载 |
| Texas A&M TPEC DER protection review | 403；后续可人工下载 |

## 使用原则

- 这些论文用于设计 Safety Edge 技术底座，不表示当前 MicroGrid 已具备真实继电保护或真实控制能力。
- 当前 Safety Edge 只能做 readiness、strategy version、fail closed 和 dry-run gating。
- 真实控制下发必须等独立安全验收，不因本研究自动启用。
