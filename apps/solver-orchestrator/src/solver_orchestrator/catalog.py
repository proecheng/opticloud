"""Static algorithm catalog — Story 2.1 (FR C1-C8).

M1-M2: shared-py/capabilities static config (Architecture C1, B1 boundary).
M3+: replaced by capability-registry service.

Each entry includes provider_url (A-S1 fix) for transparency.
"""

from __future__ import annotations

from typing import Literal, TypedDict


class ModelVersion(TypedDict):
    provider_id: str
    kind: Literal["self", "open_source", "external", "commercial"]
    version: str
    provider_url: str


class Algorithm(TypedDict):
    k_algo: str
    task_type: str
    tier: Literal["T1", "T2", "T3", "T4", "T5", "T6", "P1", "P2", "P3", "P4", "P5"]
    status: Literal["v1", "v1_late", "v2", "audited", "shadow"]
    model_version: ModelVersion
    description_zh: str
    description_en: str
    examples: list[dict[str, object]]


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
    },
]


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
