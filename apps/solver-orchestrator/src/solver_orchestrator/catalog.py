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
