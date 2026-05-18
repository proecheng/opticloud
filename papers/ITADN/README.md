# ITADN 资料与论文索引

更新日期：2026-05-04  
用途：记录本目录内 ITADN/TJU/Trust-Tech 相关材料、公开论文和对 MicroGrid 的可用性判断。

## 一句话结论

当前资料能证明 ITADN/TJU 团队有 AIGC、模型训练、Trust-Tech/TJU 优化和电力系统应用研究基础，但还不能证明它已经是一个成熟的 MicroGrid AI 预测产品。MicroGrid 侧应先把 ITADN 当作可 Docker 化的外部 AI/知识底座候选，通过 adapter、shadow validation 和离线预测评测逐步接入。

## 本目录已有材料

| 文件 | 类型 | 主要内容 | 对 MicroGrid 的判断 |
| --- | --- | --- | --- |
| `ITADN-对接问题回答.zh-CN.md` | 对接说明 | 已梳理 ITADN AIGC 脚本、adapter 建议、secret/fallback/DB 边界 | 可作为接口沟通底稿 |
| `ITADN架构设计.pptx` | 本地 PPT | 数据中台、AIGC、推荐、弹性后端、Kafka/Hadoop/Spark/Flink/DataX/ES/Milvus/Feast/MLflow 等 | 说明平台愿景，不等于已交付 forecast runtime |
| `ITADN实验室介绍 - 技术创新与竞赛成就展示(2).pptx` | 本地 PPT | ITADN 技术社区、AIGC、TJU 训练方法、算力与数据资源介绍 | 说明团队和资源，缺少 MicroGrid 预测接口证据 |
| `基于TJU-强化学习的通用大语言思考模型(1).pptx` | 本地 PPT | LoRA/GRPO、通用大语言思考模型、文章/论文处理 | 可用于解释/知识处理，不可直接当 EMS 优化或安全控制器 |
| `项目汇报PPT.pptx` | 本地 PPT | 边缘数据管理、隔离、安全认证、边云同步、标注和威胁检测 | 与 Safety/edge 概念相关，但未形成 MicroGrid runtime |

## 已保存的公开全文

| 文件 | 论文 | 公开来源 | 为什么保留 |
| --- | --- | --- | --- |
| `2022-Chiang-Xu-Lv-Dong-Hierarchical-Trust-Tech-KMeans-Power-Grids.pdf` | Hsiao-Dong Chiang, Tian-Shi Xu, Xian-Long Lv, Na Dong, 2022, Hierarchical Trust-Tech-Enhanced K-Means Methods and Their Applications to Power Grids | IEEE Open Access Journal of Power and Energy, DOI: `10.1109/OAJPE.2022.3230385` | 说明 Trust-Tech 可用于智能电表/负荷模式聚类，对 tariff、异常检测、负荷画像有参考价值 |
| `2023-Lv-Chiang-Dong-CPSOTJUTT-DNN-architecture-power-system-inspection.pdf` | Xian-Long Lv, Hsiao-Dong Chiang, Na Dong, 2023, Automatic DNN architecture design using CPSOTJUTT for power system inspection | Journal of Big Data, DOI: `10.1186/s40537-023-00828-y` | 说明 CPSOTJUTT 更像 DNN 架构/训练方法，可用于训练阶段，不是现成在线预测 API |
| `2026-Wang-Li-Lv-et-al-AQGS-ACOPF-CSEE.pdf` | 王志远、李腾木、吕宪龙等，2026，基于增广商梯度系统的鲁棒高效交流最优潮流算法 | 中国电机工程学报，DOI: `10.13334/j.0258-8013.pcsee.241621` | 与 AC OPF、潮流优化、鲁棒收敛相关，更适合纳入 Optimization 技术底座研究，而不是 ITADN 预测 runtime |

## 已检索但未保存全文的重点论文

| 论文 | 来源 | 未保存原因 | 后续处理 |
| --- | --- | --- | --- |
| Xian-Long Lv, Hsiao-Dong Chiang, Bin Wang, Yong-Feng Zhang, 2023, TJU-DNN: A trajectory-unified framework for training deep neural networks and its applications | Neurocomputing, DOI: `10.1016/j.neucom.2022.11.052` | ScienceDirect 页面可查，未发现可直接合法保存的开放 PDF | 作为 TJU 方法核心论文记录；需要全文时走学校/图书馆/作者授权 |
| Xian-Long Lv, Hsiao-Dong Chiang, Yong-Feng Zhang, 2023, A novel consensus PSO-assisted trajectory unified and trust-tech methodology for DNN training and its applications | Neural Computing and Applications, DOI: `10.1007/s00521-023-08893-3` | 下载链接返回 HTML，不保存伪 PDF | 作为 CPSOTJUTT 方法论文记录 |
| Xian-Long Lv, Shikai Tang, Jia Su, 2022, A Novel Energy Planning Scheme Based on PGA Algorithm and Its Application | Computational Intelligence and Neuroscience, DOI: `10.1155/2022/1722848` | 公开 PDF 下载失败 | 与长期能源规划相关；不直接证明 15 分钟 MicroGrid forecast |
| Yong-Feng Zhang, Hsiao-Dong Chiang, 2019, Enhanced ELITE-load: a novel CMPSOATT methodology constructing short-term load forecasting model for industrial applications | IEEE Transactions on Industrial Informatics, DOI: `10.1109/TII.2019.2930064` | IEEE 访问受限，且不是吕宪龙第一作者论文 | 对短期负荷预测有参考价值，可作为 ITADN forecast 能力询证方向 |
| Zhi-Yuan Wang, Hsiao-Dong Chiang, Tengmu Li, Xian-Long Lv, 2026, A Novel Robust Augmented Quotient Gradient System Method for AC Optimal Power Flow Part I/II | IEEE Transactions on Power Systems, DOI: `10.1109/TPWRS.2025.3616147`、`10.1109/TPWRS.2025.3616167` | IEEE 作者版链接返回 HTML，不保存伪 PDF | 与 Optimization/OPF 底座强相关，后续纳入优化算法路线 |

## 面向 MicroGrid 的能力判断

| 能力 | 证据强度 | 当前判断 |
| --- | --- | --- |
| AIGC 文章/论文处理 | 强 | 本地材料和对接文档能支持，可先做独立 ITADN AIGC adapter |
| 知识库/检索/推荐/数据中台 | 中 | PPT 有架构描述，但需要运行包、API、数据治理和权限证据 |
| TJU/Trust-Tech/DNN 训练方法 | 强 | 公开论文支持，但它主要是训练/搜索方法，不等同于上线预测服务 |
| 电力巡检视觉模型 | 强 | 多篇论文支持，但不是 MicroGrid EMS 预测主线 |
| 负荷/光伏/电价 15 分钟预测 runtime | 弱 | 当前本地资料未提供 `POST /api/ai/forecast`、特征 schema、模型版本、评测报告 |
| EMS 优化/安全控制 | 弱 | LLM/TJU 不能直接替代确定性优化器或 Safety Edge；只能提供解释、辅助和离线训练 |

## 推荐使用方式

1. 短期：ITADN 只做 shadow/advisory，不写 MicroGrid 业务库，不调用 VPP/MQTT，不发真实控制。
2. 工程边界：新增或替换 `ai-inference-py` 镜像时，对外仍保持 `POST /api/ai/forecast`；ITADN AIGC 能力另走 `/api/itadn/*`。
3. 成熟度门槛：只有当 ITADN 提供 Docker 镜像、健康检查、预测特征、模型版本、离线评测和 fallback 证据后，才允许进入真实 AI 影子验证。
4. 算法归属：TJU/Trust-Tech/AQGS 优化论文更适合沉淀到 Optimization 技术底座；ITADN 侧不要把“LLM 思考模型”包装成调度控制器。

## 外部来源

- 济南大学吕宪龙主页：`https://faculty.ujn.edu.cn/lvxianlong/zh_CN/index.htm`
- Journal of Big Data CPSOTJUTT 论文：`https://link.springer.com/article/10.1186/s40537-023-00828-y`
- ScienceDirect TJU-DNN 论文：`https://www.sciencedirect.com/science/article/pii/S0925231222014369`
- 中国电机工程学报 AQGS-ACOPF 论文：`https://epjournal.csee.org.cn/zh/article/doi/10.13334/j.0258-8013.pcsee.241621/`
- IEEE Open Access Journal of Power and Energy Trust-Tech K-Means 论文 DOI：`https://doi.org/10.1109/OAJPE.2022.3230385`
