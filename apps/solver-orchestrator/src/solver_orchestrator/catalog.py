"""Static algorithm catalog — Story 2.1 (FR C1-C8).

M1-M2: shared-py/capabilities static config (Architecture C1, B1 boundary).
M3+: replaced by capability-registry service.

Each entry includes provider_url (A-S1 fix) for transparency.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Literal, NotRequired, TypedDict


class ModelVersion(TypedDict):
    provider_id: str
    kind: Literal["self", "open_source", "external", "commercial"]
    version: str
    provider_url: str


class Citation(TypedDict):
    """Story 6.A.1 — FR R5 academic citation for an algorithm.

    `bibtex` is the canonical copy-paste artifact (single-source-of-truth);
    structured fields are UI hints.
    """

    bibtex: str
    authors_label_zh: str
    year: int
    venue: str
    doi: str | None
    url: str | None


class IPAttribution(TypedDict):
    """Story 6.A.5 — scholar / license IP attribution display contract."""

    tier: Literal["L1", "L2", "L3"]
    label_zh: str
    display_name_zh: str
    summary_zh: str
    visibility: Literal["full_visible", "bibtex", "license_only"]
    contract_anchor: str


AlgorithmProvenanceParameterSource = Literal[
    "catalog_field", "request_schema", "runtime_policy", "documentation"
]


class AlgorithmProvenanceParameter(TypedDict):
    """Story 8.C.8 — catalog-facing configuration parameter explanation."""

    name: str
    value_zh: str
    description_zh: str
    source: AlgorithmProvenanceParameterSource


class AlgorithmProvenance(TypedDict):
    """Story 8.C.8 — algorithm provenance detail metadata.

    Citation data remains single-sourced through `citation`; provenance only
    declares that relationship via `citation_source`.
    """

    theory_zh: str
    theory_en: str
    configuration_parameters: list[AlgorithmProvenanceParameter]
    applicable_scenarios_zh: list[str]
    limitations_zh: list[str]
    citation_source: Literal["catalog_citation"]


class SelfAuditStatus(TypedDict):
    """Internal §4.5 self-developed algorithm audit state.

    This field is intentionally not part of the public AlgorithmSchema.
    """

    package_or_runnable: bool
    license_approved: bool
    minimal_example_30m: bool
    readme_schema: bool
    paper_reproduction_result: bool


class Algorithm(TypedDict):
    k_algo: str
    task_type: str
    tier: Literal["T1", "T2", "T3", "T4", "T5", "T6", "P1", "P2", "P3", "P4", "P5"]
    status: Literal["v1", "v1_late", "v2", "audited", "shadow"]
    model_version: ModelVersion
    description_zh: str
    description_en: str
    examples: list[dict[str, object]]
    supported_solvers: list[
        str
    ]  # Story 2.4 — FR C4 (enum of solver names valid for this algorithm)
    citation: Citation | None  # Story 6.A.1 — FR R5 (None reserved for future commercial-only SKUs)
    ip_attribution: IPAttribution  # Story 6.A.5 — L1/L2/L3 academic IP attribution
    provenance: AlgorithmProvenance  # Story 8.C.8 — theory / parameters / scenarios
    self_audit: NotRequired[SelfAuditStatus]  # Story 2.8 — internal FR C8 publish/route gate


SELF_AUDIT_RULES: tuple[str, ...] = (
    "package_or_runnable",
    "license_approved",
    "minimal_example_30m",
    "readme_schema",
    "paper_reproduction_result",
)


OPEN_SOURCE_LICENSE_ANCHOR = "docs/legal-templates.md Doc 1 / open-source license review"
PROVIDER_AGREEMENT_ANCHOR = "docs/legal-templates.md Doc 6 / Provider Agreement"

ATTR_HIGHS: IPAttribution = {
    "tier": "L3",
    "label_zh": "L3 · License-Only",
    "display_name_zh": "HiGHS open-source project",
    "summary_zh": "开源 Runner：遵守 MIT license 与论文引用，不声明学界 Provider 合作。",
    "visibility": "license_only",
    "contract_anchor": OPEN_SOURCE_LICENSE_ANCHOR,
}

ATTR_OR_TOOLS: IPAttribution = {
    "tier": "L3",
    "label_zh": "L3 · License-Only",
    "display_name_zh": "Google OR-Tools open-source project",
    "summary_zh": "开源 Runner：遵守 Apache 2.0 license 与软件引用，不声明学界 Provider 合作。",
    "visibility": "license_only",
    "contract_anchor": OPEN_SOURCE_LICENSE_ANCHOR,
}

ATTR_CHRONOS: IPAttribution = {
    "tier": "L3",
    "label_zh": "L3 · License-Only",
    "display_name_zh": "Chronos authors / Amazon Science",
    "summary_zh": "文献与开源模型引用：展示 BibTeX / DOI，不声明 OptiCloud Provider 合作。",
    "visibility": "license_only",
    "contract_anchor": OPEN_SOURCE_LICENSE_ANCHOR,
}

ATTR_ARIMA: IPAttribution = {
    "tier": "L3",
    "label_zh": "L3 · License-Only",
    "display_name_zh": "Box & Jenkins ARIMA literature",
    "summary_zh": "经典文献引用：展示 BibTeX，不声明学界 Provider 合作。",
    "visibility": "license_only",
    "contract_anchor": OPEN_SOURCE_LICENSE_ANCHOR,
}

ATTR_LSTM: IPAttribution = {
    "tier": "L3",
    "label_zh": "L3 · License-Only",
    "display_name_zh": "Hochreiter & Schmidhuber LSTM literature",
    "summary_zh": "经典文献引用：展示 DOI / BibTeX，不声明学界 Provider 合作。",
    "visibility": "license_only",
    "contract_anchor": OPEN_SOURCE_LICENSE_ANCHOR,
}

ATTR_AQGS: IPAttribution = {
    "tier": "L1",
    "label_zh": "L1 · Full Visible Attribution",
    "display_name_zh": "OptiCloud / Trust-Tech 团队",
    "summary_zh": "Full visible attribution：自研学术品牌锚点，可在公开学术页面显示 Algorithm by。",
    "visibility": "full_visible",
    "contract_anchor": PROVIDER_AGREEMENT_ANCHOR,
}


PROVENANCE_HIGHS_LP: AlgorithmProvenance = {
    "theory_zh": (
        "线性规划把目标函数和约束都表达为线性关系，使用单纯形、对偶单纯形"
        "或内点法在凸多面体上寻找全局最优解。"
    ),
    "theory_en": (
        "Linear programming models both the objective and constraints as linear "
        "relations, then searches a convex polytope with simplex, dual simplex, "
        "or interior-point methods."
    ),
    "configuration_parameters": [
        {
            "name": "建模形式",
            "value_zh": "线性目标与线性不等式约束",
            "description_zh": "公开请求体需要给出目标向量、约束矩阵和右端项。",
            "source": "request_schema",
        },
        {
            "name": "执行策略",
            "value_zh": "同步求解优先，超时预算由请求选项限制",
            "description_zh": "目录页只解释可见策略，不暴露底层算法切换开关。",
            "source": "runtime_policy",
        },
        {
            "name": "可解释输出",
            "value_zh": "最优目标值、解向量和求解耗时",
            "description_zh": "结果字段面向复现实验和教学演示，可与引用信息一起归档。",
            "source": "documentation",
        },
    ],
    "applicable_scenarios_zh": [
        "生产、运输或库存中的连续资源分配。",
        "课堂演示线性约束建模与影子价格概念。",
        "作为更复杂整数、鲁棒或随机模型的松弛基线。",
    ],
    "limitations_zh": [
        "不能直接表达整数决策、非线性目标或逻辑约束。",
        "公开页面不承诺暴露底层求解器的全部调参选项。",
    ],
    "citation_source": "catalog_citation",
}

PROVENANCE_HIGHS_MILP: AlgorithmProvenance = {
    "theory_zh": (
        "混合整数线性优化在线性模型中加入离散变量，通常通过分支定界、割平面"
        "和启发式搜索组合来证明可行解与界限。"
    ),
    "theory_en": (
        "Mixed-integer linear optimization augments a linear model with discrete "
        "variables, combining branch-and-bound, cutting planes, and heuristics "
        "to manage feasible solutions and bounds."
    ),
    "configuration_parameters": [
        {
            "name": "变量语义",
            "value_zh": "连续变量与离散决策可以共同建模",
            "description_zh": "目录说明离散建模能力，具体变量声明仍由请求 schema 承载。",
            "source": "request_schema",
        },
        {
            "name": "搜索边界",
            "value_zh": "求解时间受公共请求预算限制",
            "description_zh": "长尾证明过程可能被预算截断，页面不展示内部节点策略。",
            "source": "runtime_policy",
        },
        {
            "name": "证明口径",
            "value_zh": "返回状态需要与目标值和解向量一起解释",
            "description_zh": "教学和评估场景应区分最优、可行、超时和失败状态。",
            "source": "documentation",
        },
    ],
    "applicable_scenarios_zh": [
        "选址、排产、装箱和开关决策。",
        "需要同时考虑连续资源与离散选择的企业优化。",
        "从线性松弛推进到整数决策的教学案例。",
    ],
    "limitations_zh": [
        "离散变量会显著增加搜索复杂度，最坏情况不可按线性模型估算。",
        "公开详情页不提供底层分支策略、割平面族或启发式开关。",
    ],
    "citation_source": "catalog_citation",
}

PROVENANCE_OR_TOOLS_VRPTW: AlgorithmProvenance = {
    "theory_zh": (
        "带时间窗车辆路径问题在图上分配车辆访问客户，并同时满足容量、服务时间"
        "和时间窗约束，通常依赖约束搜索和局部搜索组合。"
    ),
    "theory_en": (
        "Vehicle routing with time windows assigns visits on a graph while "
        "respecting capacity, service time, and time-window constraints, usually "
        "with constraint search and local-search neighborhoods."
    ),
    "configuration_parameters": [
        {
            "name": "核心约束族",
            "value_zh": "车辆容量、访问顺序、服务时间与时间窗",
            "description_zh": "这些是建模概念说明，不表示页面可直接编辑所有原生维度。",
            "source": "documentation",
        },
        {
            "name": "输入形态",
            "value_zh": "节点、距离或时间矩阵、需求和窗口数据",
            "description_zh": "实际请求格式由具体模板或后续 API 能力决定。",
            "source": "request_schema",
        },
        {
            "name": "求解策略",
            "value_zh": "约束搜索结合邻域改进",
            "description_zh": "目录解释算法族，不开放底层局部搜索算子选择。",
            "source": "documentation",
        },
    ],
    "applicable_scenarios_zh": [
        "配送线路规划、上门服务排程和校车路径。",
        "需要尊重客户时间窗或服务时段的物流问题。",
        "教学中展示路由约束、时间窗和启发式改进。",
    ],
    "limitations_zh": [
        "大规模实例可能需要业务专用预处理和启发式调参。",
        "当前详情页不代表已连接外部车队系统或实时地图服务。",
    ],
    "citation_source": "catalog_citation",
}

PROVENANCE_OR_TOOLS_CP_SAT: AlgorithmProvenance = {
    "theory_zh": (
        "约束规划把排班、分配和逻辑条件表达为变量域与约束传播问题，"
        "并结合布尔可满足性搜索处理复杂组合结构。"
    ),
    "theory_en": (
        "Constraint programming represents scheduling, assignment, and logical "
        "conditions as variable domains with propagation, combined with Boolean "
        "satisfiability search for combinatorial structure."
    ),
    "configuration_parameters": [
        {
            "name": "约束表达",
            "value_zh": "变量域、互斥关系、时间区间和布尔逻辑",
            "description_zh": "页面描述建模能力，不提供原生约束编辑器。",
            "source": "documentation",
        },
        {
            "name": "任务边界",
            "value_zh": "适合离散排班和组合分配",
            "description_zh": "连续非线性数值优化不属于该算法族的主要用途。",
            "source": "catalog_field",
        },
        {
            "name": "搜索策略",
            "value_zh": "约束传播、冲突学习和分支搜索",
            "description_zh": "公开目录只解释算法理论，不暴露内部搜索参数。",
            "source": "documentation",
        },
    ],
    "applicable_scenarios_zh": [
        "员工排班、课程安排和机器作业调度。",
        "带互斥、先后顺序或资源容量的组合问题。",
        "教学中展示约束传播与可满足性搜索思想。",
    ],
    "limitations_zh": [
        "不适合以连续光滑函数为核心的数值优化。",
        "公开页面不保证展示所有原生约束类型或搜索日志。",
    ],
    "citation_source": "catalog_citation",
}

PROVENANCE_CHRONOS_T5: AlgorithmProvenance = {
    "theory_zh": (
        "时序基础模型把历史数值序列离散化为 token 序列，通过序列到序列模型学习跨领域预测模式。"
    ),
    "theory_en": (
        "A time-series foundation model tokenizes historical numerical sequences "
        "and learns cross-domain predictive patterns with a sequence-to-sequence "
        "architecture."
    ),
    "configuration_parameters": [
        {
            "name": "历史窗口",
            "value_zh": "输入序列长度由预测请求提供",
            "description_zh": "目录不持久化用户数据，也不展示训练语料细节。",
            "source": "request_schema",
        },
        {
            "name": "预测步长",
            "value_zh": "输出期数由请求中的 horizon 决定",
            "description_zh": "较长预测期应结合回测和业务约束解释。",
            "source": "request_schema",
        },
        {
            "name": "模型使用方式",
            "value_zh": "公开页面说明模型族和推理用途",
            "description_zh": "不声明针对用户数据的在线训练或再训练。",
            "source": "runtime_policy",
        },
    ],
    "applicable_scenarios_zh": [
        "销售、流量、能耗或供需曲线的短中期预测。",
        "缺少专门建模团队时的基础预测起点。",
        "教学中比较基础模型与经典统计模型的差异。",
    ],
    "limitations_zh": [
        "预测结果仅供参考，需要结合漂移监控和业务校验。",
        "公开详情页不表示用户数据进入模型训练集。",
    ],
    "citation_source": "catalog_citation",
}

PROVENANCE_ARIMA: AlgorithmProvenance = {
    "theory_zh": (
        "自回归积分滑动平均模型用差分处理非平稳序列，并用自回归项和滑动平均项刻画线性时间依赖。"
    ),
    "theory_en": (
        "Autoregressive integrated moving-average modeling differences a "
        "non-stationary series, then uses autoregressive and moving-average terms "
        "to capture linear temporal dependence."
    ),
    "configuration_parameters": [
        {
            "name": "序列假设",
            "value_zh": "主要面向单变量、近似线性的时间依赖",
            "description_zh": "强季节性或结构突变需要额外建模判断。",
            "source": "documentation",
        },
        {
            "name": "历史数据",
            "value_zh": "请求数据提供观测序列",
            "description_zh": "平台不在 provenance 中保存或回显用户原始数据。",
            "source": "request_schema",
        },
        {
            "name": "输出口径",
            "value_zh": "返回预测区间或分位数时需标注参考用途",
            "description_zh": "预测免责声明仍由预测响应合同负责。",
            "source": "runtime_policy",
        },
    ],
    "applicable_scenarios_zh": [
        "稳定业务指标的短期趋势外推。",
        "作为复杂预测模型的可解释基线。",
        "课堂讲解差分、残差和自相关诊断。",
    ],
    "limitations_zh": [
        "难以捕捉强非线性、多变量交互或长程复杂模式。",
        "参数阶数选择需要统计诊断，公开页面不自动证明最优阶数。",
    ],
    "citation_source": "catalog_citation",
}

PROVENANCE_LSTM: AlgorithmProvenance = {
    "theory_zh": ("长短期记忆网络通过门控状态保留和遗忘序列信息，用于学习非线性和较长时间依赖。"),
    "theory_en": (
        "Long short-term memory networks use gated state updates to retain and "
        "forget sequential information, learning nonlinear and longer-range "
        "temporal dependencies."
    ),
    "configuration_parameters": [
        {
            "name": "序列建模",
            "value_zh": "面向多步时间依赖和非线性模式",
            "description_zh": "实际窗口、特征和训练策略由后续模型服务能力决定。",
            "source": "documentation",
        },
        {
            "name": "推理用途",
            "value_zh": "公开目录说明算法族，不声明在线训练",
            "description_zh": "用户请求不会因为浏览 provenance 而触发训练或数据存储。",
            "source": "runtime_policy",
        },
        {
            "name": "评估口径",
            "value_zh": "需要结合回测、漂移和误差分析",
            "description_zh": "页面不展示 benchmark 排名或生产 SLO 证明。",
            "source": "documentation",
        },
    ],
    "applicable_scenarios_zh": [
        "存在非线性模式的流量、需求或传感器序列。",
        "多变量特征对未来走势有影响的预测任务。",
        "教学中展示门控循环网络和经典统计模型的对比。",
    ],
    "limitations_zh": [
        "需要充足数据和验证流程，不能仅凭模型族保证精度。",
        "公开详情页不提供训练超参数、权重文件或实时再训练能力。",
    ],
    "citation_source": "catalog_citation",
}

PROVENANCE_AQGS_ACOPF: AlgorithmProvenance = {
    "theory_zh": (
        "交流最优潮流把电网潮流方程、发电约束和运行目标组合为非线性约束优化，"
        "自研方法尝试用增强商梯度系统改进求解路径。"
    ),
    "theory_en": (
        "AC optimal power-flow combines network equations, generation constraints, "
        "and operating objectives into a nonlinear constrained optimization problem; "
        "the in-house method explores augmented quotient-gradient dynamics."
    ),
    "configuration_parameters": [
        {
            "name": "电网模型",
            "value_zh": "节点、支路、发电机和运行边界",
            "description_zh": "当前公开发布仍受自研审核门槛约束。",
            "source": "documentation",
        },
        {
            "name": "非线性结构",
            "value_zh": "潮流方程和运行目标共同决定可行域",
            "description_zh": "页面只记录理论来源，不开放生产求解入口。",
            "source": "catalog_field",
        },
        {
            "name": "审核状态",
            "value_zh": "需要通过包可运行、许可、示例、文档和复现实验检查",
            "description_zh": "未完成审核前不会出现在公开 API 或公开详情页。",
            "source": "runtime_policy",
        },
    ],
    "applicable_scenarios_zh": [
        "电网运行和潮流约束研究。",
        "非线性优化方法的内部验证和论文复现实验。",
        "自研算法审核流程中的证据归档。",
    ],
    "limitations_zh": [
        "该条目未通过公开发布审核，不应作为可用生产 SKU 展示。",
        "provenance 存在于内部 catalog，不代表 API 路由已开放。",
    ],
    "citation_source": "catalog_citation",
}


CATALOG: list[Algorithm] = [
    {
        "k_algo": "highs-lp",
        "task_type": "lp",
        "tier": "T1",
        "status": "v1",
        "model_version": {
            "provider_id": "highs",
            "kind": "open_source",
            "version": "1.7.0",
            "provider_url": "https://highs.dev/",
        },
        "description_zh": "HiGHS 线性规划 (Linear Programming) — 全球最快开源 LP 求解器 (2024 MIT)",
        "description_en": "HiGHS Linear Programming — fastest open-source LP solver",
        "examples": [
            {
                "name": "Hello World LP",
                "input": {
                    "task_type": "lp",
                    "minimize": {"c": [1, 1]},
                    "st": {"A": [[1, 1]], "b": [10]},
                },
                "description": "最小化 x₁+x₂ 满足 x₁+x₂ ≤ 10, x ≥ 0",
            }
        ],
        "supported_solvers": ["highs"],
        "citation": {
            "bibtex": (
                "@article{huangfu2018parallelizing,\n"
                "  author = {Huangfu, Q. and Hall, J. A. J.},\n"
                "  title = {Parallelizing the dual revised simplex method},\n"
                "  journal = {Mathematical Programming Computation},\n"
                "  volume = {10},\n"
                "  number = {1},\n"
                "  pages = {119--142},\n"
                "  year = {2018},\n"
                "  doi = {10.1007/s12532-017-0130-5}\n"
                "}"
            ),
            "authors_label_zh": "Huangfu & Hall (2018)",
            "year": 2018,
            "venue": "Mathematical Programming Computation",
            "doi": "10.1007/s12532-017-0130-5",
            "url": "https://doi.org/10.1007/s12532-017-0130-5",
        },
        "ip_attribution": ATTR_HIGHS,
        "provenance": PROVENANCE_HIGHS_LP,
    },
    {
        "k_algo": "highs-milp",
        "task_type": "milp",
        "tier": "T2",
        "status": "v1",
        "model_version": {
            "provider_id": "highs",
            "kind": "open_source",
            "version": "1.7.0",
            "provider_url": "https://highs.dev/",
        },
        "description_zh": "HiGHS 混合整数线性规划 (MILP) — 整数变量约束",
        "description_en": "HiGHS Mixed Integer Linear Programming",
        "examples": [],
        "supported_solvers": ["highs"],
        "citation": {
            "bibtex": (
                "@article{huangfu2018parallelizing,\n"
                "  author = {Huangfu, Q. and Hall, J. A. J.},\n"
                "  title = {Parallelizing the dual revised simplex method},\n"
                "  journal = {Mathematical Programming Computation},\n"
                "  volume = {10},\n"
                "  number = {1},\n"
                "  pages = {119--142},\n"
                "  year = {2018},\n"
                "  doi = {10.1007/s12532-017-0130-5}\n"
                "}"
            ),
            "authors_label_zh": "Huangfu & Hall (2018)",
            "year": 2018,
            "venue": "Mathematical Programming Computation",
            "doi": "10.1007/s12532-017-0130-5",
            "url": "https://doi.org/10.1007/s12532-017-0130-5",
        },
        "ip_attribution": ATTR_HIGHS,
        "provenance": PROVENANCE_HIGHS_MILP,
    },
    {
        "k_algo": "or-tools-vrptw",
        "task_type": "vrptw",
        "tier": "T4",
        "status": "v1",
        "model_version": {
            "provider_id": "or-tools",
            "kind": "open_source",
            "version": "9.10.0",
            "provider_url": "https://developers.google.com/optimization/routing",
        },
        "description_zh": "OR-Tools 带时间窗的车辆路径规划 (VRPTW)",
        "description_en": "OR-Tools Vehicle Routing with Time Windows",
        "examples": [],
        "supported_solvers": ["or-tools"],
        "citation": {
            "bibtex": (
                "@software{perron2024ortools,\n"
                "  author = {Perron, Laurent and Furnon, Vincent},\n"
                "  title = {OR-Tools},\n"
                "  organization = {Google},\n"
                "  year = {2024},\n"
                "  version = {9.10.0},\n"
                "  url = {https://developers.google.com/optimization}\n"
                "}"
            ),
            "authors_label_zh": "Perron & Furnon · Google (2024)",
            "year": 2024,
            "venue": "Software",
            "doi": None,
            "url": "https://developers.google.com/optimization",
        },
        "ip_attribution": ATTR_OR_TOOLS,
        "provenance": PROVENANCE_OR_TOOLS_VRPTW,
    },
    {
        "k_algo": "or-tools-cp-sat",
        "task_type": "schedule",
        "tier": "T3",
        "status": "v1",
        "model_version": {
            "provider_id": "or-tools-cp-sat",
            "kind": "open_source",
            "version": "9.10.0",
            "provider_url": "https://developers.google.com/optimization/cp/cp_solver",
        },
        "description_zh": "OR-Tools CP-SAT — 约束规划求解器 (排班 / 调度)",
        "description_en": "OR-Tools CP-SAT — Constraint Programming",
        "examples": [],
        "supported_solvers": ["or-tools-cp-sat", "or-tools"],
        "citation": {
            "bibtex": (
                "@inproceedings{perron2011constraint,\n"
                "  author = {Perron, Laurent},\n"
                "  title = {Operations Research and Constraint Programming at Google},\n"
                "  booktitle = {Principles and Practice of Constraint Programming (CP 2011)},\n"
                "  series = {Lecture Notes in Computer Science},\n"
                "  volume = {6876},\n"
                "  pages = {2},\n"
                "  year = {2011},\n"
                "  doi = {10.1007/978-3-642-23786-7_2}\n"
                "}"
            ),
            "authors_label_zh": "Perron · Google (2011)",
            "year": 2011,
            "venue": "Principles and Practice of Constraint Programming (CP)",
            "doi": "10.1007/978-3-642-23786-7_2",
            "url": "https://doi.org/10.1007/978-3-642-23786-7_2",
        },
        "ip_attribution": ATTR_OR_TOOLS,
        "provenance": PROVENANCE_OR_TOOLS_CP_SAT,
    },
    {
        "k_algo": "chronos-t5-forecast",
        "task_type": "forecast",
        "tier": "P2",
        "status": "v1_late",
        "model_version": {
            "provider_id": "chronos-t5",
            "kind": "open_source",
            "version": "small-v1",
            "provider_url": "https://github.com/amazon-science/chronos-forecasting",
        },
        "description_zh": "Chronos-T5 时序基础模型 — 销量 / 流量 / 风光出力预测",
        "description_en": "Chronos-T5 time-series foundation model",
        "examples": [],
        "supported_solvers": ["chronos-t5"],
        "citation": {
            "bibtex": (
                "@article{ansari2024chronos,\n"
                "  author = {Ansari, Abdul Fatir and Stella, Lorenzo and Turkmen, Caner and "
                "Zhang, Xiyuan and Mercado, Pedro and Shen, Huibin and Shchur, Oleksandr and "
                "Rangapuram, Syama Sundar and Pineda Arango, Sebastian and Kapoor, Shubham "
                "and Zschiegner, Jasper and Maddix, Danielle C. and Mahoney, Michael W. and "
                "Torkkola, Kari and Wilson, Andrew Gordon and Bohlke-Schneider, Michael and "
                "Wang, Yuyang},\n"
                "  title = {Chronos: Learning the Language of Time Series},\n"
                "  journal = {arXiv preprint},\n"
                "  year = {2024},\n"
                "  doi = {10.48550/arXiv.2403.07815}\n"
                "}"
            ),
            "authors_label_zh": "Ansari et al. · Amazon Science (2024)",
            "year": 2024,
            "venue": "arXiv preprint",
            "doi": "10.48550/arXiv.2403.07815",
            "url": "https://doi.org/10.48550/arXiv.2403.07815",
        },
        "ip_attribution": ATTR_CHRONOS,
        "provenance": PROVENANCE_CHRONOS_T5,
    },
    {
        "k_algo": "arima-forecast",
        "task_type": "forecast",
        "tier": "P1",
        "status": "v1",
        "model_version": {
            "provider_id": "statsmodels-arima",
            "kind": "open_source",
            "version": "0.14.4",
            "provider_url": "https://www.statsmodels.org/",
        },
        "description_zh": "ARIMA 时序预测 — 经典 P/D/Q 模型",
        "description_en": "ARIMA classical time-series forecasting",
        "examples": [],
        "supported_solvers": ["statsmodels-arima", "arima"],
        "citation": {
            "bibtex": (
                "@book{box1976time,\n"
                "  author = {Box, George E. P. and Jenkins, Gwilym M.},\n"
                "  title = {Time Series Analysis: Forecasting and Control},\n"
                "  publisher = {Holden-Day},\n"
                "  address = {San Francisco},\n"
                "  year = {1976},\n"
                "  edition = {Revised}\n"
                "}"
            ),
            "authors_label_zh": "Box & Jenkins (1976)",
            "year": 1976,
            "venue": "Holden-Day",
            "doi": None,
            "url": None,
        },
        "ip_attribution": ATTR_ARIMA,
        "provenance": PROVENANCE_ARIMA,
    },
    {
        "k_algo": "lstm-forecast",
        "task_type": "forecast",
        "tier": "P3",
        "status": "v1_late",
        "model_version": {
            "provider_id": "tensorflow-lstm",
            "kind": "open_source",
            "version": "2.18.0",
            "provider_url": "https://www.tensorflow.org/",
        },
        "description_zh": "LSTM 神经网络 — 长序列 / 多变量预测",
        "description_en": "LSTM neural network — long-sequence / multivariate forecasting",
        "examples": [],
        "supported_solvers": ["tensorflow-lstm", "lstm"],
        "citation": {
            "bibtex": (
                "@article{hochreiter1997long,\n"
                '  author = {Hochreiter, Sepp and Schmidhuber, J\\"{u}rgen},\n'
                "  title = {Long Short-Term Memory},\n"
                "  journal = {Neural Computation},\n"
                "  volume = {9},\n"
                "  number = {8},\n"
                "  pages = {1735--1780},\n"
                "  year = {1997},\n"
                "  doi = {10.1162/neco.1997.9.8.1735}\n"
                "}"
            ),
            "authors_label_zh": "Hochreiter & Schmidhuber (1997)",
            "year": 1997,
            "venue": "Neural Computation",
            "doi": "10.1162/neco.1997.9.8.1735",
            "url": "https://doi.org/10.1162/neco.1997.9.8.1735",
        },
        "ip_attribution": ATTR_LSTM,
        "provenance": PROVENANCE_LSTM,
    },
    {
        "k_algo": "aqgs-acopf",
        "task_type": "nlp",
        "tier": "T5",
        "status": "v1",
        "model_version": {
            "provider_id": "aqgs",
            "kind": "self",
            "version": "0.1.0",
            "provider_url": "https://github.com/opticloud/aqgs",
        },
        "description_zh": "自研 AQGS-ACOPF — 交流最优潮流求解 (Innovation #6, Apache 2.0)",
        "description_en": "AQGS-ACOPF — proprietary AC Optimal Power Flow (Innovation #6)",
        "examples": [],
        "supported_solvers": ["aqgs"],
        "self_audit": {
            "package_or_runnable": False,
            "license_approved": False,
            "minimal_example_30m": False,
            "readme_schema": False,
            "paper_reproduction_result": False,
        },
        "citation": {
            "bibtex": (
                "@software{aqgs2025opticloud,\n"
                "  author = {{OptiCloud Team}},\n"
                "  title = {AQGS-ACOPF: Augmented Quotient-Gradient System for AC Optimal Power Flow},\n"
                "  year = {2025},\n"
                "  version = {0.1.0},\n"
                "  license = {Apache-2.0},\n"
                "  url = {https://github.com/opticloud/aqgs}\n"
                "}"
            ),
            "authors_label_zh": "OptiCloud / Trust-Tech 团队 (2025)",
            "year": 2025,
            "venue": "Software (Apache 2.0)",
            "doi": None,
            "url": "https://github.com/opticloud/aqgs",
        },
        "ip_attribution": ATTR_AQGS,
        "provenance": PROVENANCE_AQGS_ACOPF,
    },
]


def is_self_algorithm(algo: Algorithm) -> bool:
    """Return true for self-developed provider rows."""
    return algo["model_version"]["kind"] == "self"


def self_audit_missing_rules(algo: Algorithm) -> list[str]:
    """Return missing §4.5 rules in canonical order.

    Non-self algorithms do not require self-audit. Self rows fail closed when
    metadata is absent or malformed.
    """
    if not is_self_algorithm(algo):
        return []
    audit = algo.get("self_audit")
    if not isinstance(audit, dict):
        return list(SELF_AUDIT_RULES)
    if set(audit) != set(SELF_AUDIT_RULES):
        return list(SELF_AUDIT_RULES)
    missing: list[str] = []
    for rule in SELF_AUDIT_RULES:
        if audit.get(rule) is not True:
            missing.append(rule)
    return missing


def self_audit_passed(algo: Algorithm) -> bool:
    """Return true when an algorithm is publishable by the FR C8 self-audit gate."""
    return not self_audit_missing_rules(algo)


def publishable_catalog_items(items: list[Algorithm] | None = None) -> list[Algorithm]:
    """Return public catalog rows, excluding unaudited self algorithms."""
    source = CATALOG if items is None else items
    return [deepcopy(algo) for algo in source if self_audit_passed(algo)]


def self_audit_ticket_id(k_algo: str, provider_id: str) -> str:
    """Return deterministic non-sensitive admin ticket id for a blocked self algorithm."""

    def _slug(value: str) -> str:
        slug = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
        return slug or "unknown"

    return f"self-audit-{_slug(k_algo)}-{_slug(provider_id)}"


def find_by_task_type(task_type: str) -> Algorithm | None:
    """Return first algorithm matching task_type (M1-M2 fallback to first match)."""
    for algo in CATALOG:
        if algo["task_type"] == task_type:
            return algo
    return None


def find_by_k_algo(k_algo: str) -> Algorithm | None:
    for algo in CATALOG:
        if algo["k_algo"] == k_algo:
            return algo
    return None


def find_by_task_type_and_solver(
    task_type: str, solver: str | None
) -> tuple[Algorithm | None, list[str]]:
    """Story 2.4 — FR C4 solver-aware algorithm lookup.

    Returns (matching_algo, all_supported_solvers_for_this_task_type).

    - When `solver is None`: returns (first algorithm matching task_type, its supported_solvers)
    - When `solver` is provided: scans ALL algorithms with matching task_type and
      returns the first whose supported_solvers contains `solver`. If none match
      but task_type exists, returns (None, union_of_all_supported_for_this_task_type)
      so the caller can render a useful 400 error.
    - When `task_type` itself is unknown: returns (None, []).

    This handles the forecast case (3 algorithms share task_type=forecast: chronos / arima / lstm).
    """
    matches = [a for a in CATALOG if a["task_type"] == task_type]
    if not matches:
        return None, []

    union_supported: list[str] = []
    for a in matches:
        for s in a["supported_solvers"]:
            if s not in union_supported:
                union_supported.append(s)

    if solver is None:
        return matches[0], union_supported

    for a in matches:
        if solver in a["supported_solvers"]:
            return a, union_supported

    return None, union_supported
