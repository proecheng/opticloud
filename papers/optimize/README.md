# Optimization papers index

更新日期：2026-05-04
用途：MicroGrid 优化技术底座研究资料。优先围绕 Hsiao-Dong Chiang / 江晓东、Trust-Tech、SuperOPF、OPF/SOR，以及天津大学合作线索。

## 已下载全文或公开 PDF

| 文件 | 主题 | 与 MicroGrid 的关系 | 来源 |
| --- | --- | --- | --- |
| `wang-2013-extended-trust-tech-methodology-dissertation.pdf` | Bin Wang Cornell 博士论文，Extended Trust-Tech、可行性恢复、TT-IPM、MINLP、OPF 应用 | 优化底座的核心方法来源：用稳定域/邻域搜索跳出局部最优，并把可行性恢复作为求解器前置能力 | Cornell eCommons public API |
| `reddy-2007-trust-tech-methods-optimization-learning-thesis.pdf` | Chandan Reddy Cornell 博士论文，Trust-Tech for optimization and learning | 解释 Trust-Tech 的两阶段思想：local optimizer + stability-region neighborhood search | arXiv |
| `wang-chiang-2011-trust-tech-minlp.pdf` | Trust-Tech based methodology for MINLP | 对应 MicroGrid 中电池开停、充放电状态、削峰/保电等连续+离散约束 | J-STAGE NOLTA open PDF |
| `chiang-superopf-framework-summary-2012.pdf` | SuperOPF Phase 2 项目摘要，安全约束 AC OPF、contingency、AVC、load shedding | 长期方向：从本地 dispatch schedule 升级到安全约束 OPF / co-optimization | U.S. DOE project summary |
| `chiang-2013-superopf-review-slides.pdf` | SuperOPF Phase 3 review slides | 说明商业级 OPF solver 的多阶段、同伦、随机安全约束和大系统经验 | U.S. DOE review slides |
| `chiang-2017-trust-tech-nonlinear-optimization-opf-seminar.pdf` | Chiang Trust-Tech + OPF seminar abstract | 证明 Trust-Tech 已被 Chiang 团队明确用于 OPF、machine learning、network partition 等 | TAMU Smart Grid Center seminar |
| `su-chiang-zeng-2021-electricity-heat-secure-operation-region.pdf` | 天津大学 Jia Su、Yuan Zeng 与 Chiang 的电-热综合能源 secure operation region | 给 MicroGrid 安全可行域/灵活性评估提供方法：不仅算最优，还评估运行点是否在安全区域内 | Semantic Scholar PDF cache / IET ESI |
| `wang-et-al-robust-efficient-ac-opf-augmented-qgs.pdf` | 天津大学/Chiang 合作，基于增广商梯度系统 AQGS 的鲁棒高效 AC OPF | 与 Trust-Tech 同源的动力系统思路，适合长期 solver 升级和可行性/收敛性研究 | Proceedings of the CSEE open PDF |
| `reddy-chiang-rajaratnam-2008-trust-tech-em.pdf` | Trust-Tech based EM for mixture models | 不是电力优化主线，但说明 Trust-Tech 的通用局部极值邻域搜索机制 | Chiang publication page |

## 未下载全文但需要跟踪

| 论文/线索 | 为什么重要 | 处理 |
| --- | --- | --- |
| Dan Wang, Yadan Li, Hsiao-Dong Chiang, Miao Wang, Yuting Zhou, Pengju Cong, “Hierarchical energy management system for multi-source multi-product microgrids”, Renewable Energy, 2018 | 天津大学/Chiang 合作，题目直接对应多源多产物微网分层 EMS；很可能是 MicroGrid 优化底座最贴近产品的一篇 | 已检索到 ScienceDirect / Queen's University Belfast 摘要和天津大学王丹主页记录；未发现合法公开 PDF，暂不下载 |
| Y.-F. Zhang et al., “A Novel TRUST-TECH-Enabled Trajectory-Unified Methodology for Computing Multiple Optimal Solutions of Constrained Nonlinear Optimization”, IEEE Transactions on Cybernetics, 2022 | Source-Point Method / trajectory-unified TRUST-TECH，可为多候选 schedule 生成提供理论路线 | 已检索到 DOI/摘要，未发现公开 PDF |
| Chiang 团队关于 OPF feasibility restoration / TT-IPM 的期刊论文 | 可把 MicroGrid solver 从规则型 min-cost 升级到可行性恢复 + 约束优化 | 先以 Bin Wang dissertation 和 SuperOPF 公开报告为依据 |

## 使用原则

- 这些论文用于技术底座方案设计，不代表当前 MicroGrid 已具备真实 Trust-Tech solver。
- 当前系统仍保持 `commandIssued=false` 和 `controlCommandIssued=false`。
- 真实 VPP、生产 MQTT、真实控制继续后置。
