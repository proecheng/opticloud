"""Static classic benchmark library catalog for Story 8.C.4.

The entries are pointer-only templates. They do not mirror, download, or embed
external benchmark datasets.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal, TypedDict


class BenchmarkDiscount(TypedDict):
    kind: Literal["benchmark_library"]
    label_zh: str
    discount_multiplier: float
    billing_supported: bool


class BenchmarkLibraryItem(TypedDict):
    benchmark_id: str
    suite: Literal["ieee", "cvrplib", "or-lib", "m5", "uci", "nab"]
    domain: str
    task_type: str
    title_zh: str
    title_en: str
    source_name: str
    source_url: str
    license_note_zh: str
    import_kind: Literal["optimization_request", "prediction_request"]
    target_endpoint: Literal["/v1/optimizations", "/v1/predictions"]
    discount: BenchmarkDiscount
    dataset_ref: str
    sample_payload: dict[str, Any]


BENCHMARK_LIBRARY_DISCOUNT_KIND: Literal["benchmark_library"] = "benchmark_library"
BENCHMARK_LIBRARY_DISCOUNT_MULTIPLIER = 0.5


def _discount(*, billing_supported: bool) -> BenchmarkDiscount:
    return {
        "kind": BENCHMARK_LIBRARY_DISCOUNT_KIND,
        "label_zh": "50% Credits 折扣",
        "discount_multiplier": BENCHMARK_LIBRARY_DISCOUNT_MULTIPLIER,
        "billing_supported": billing_supported,
    }


BENCHMARK_LIBRARY: list[BenchmarkLibraryItem] = [
    {
        "benchmark_id": "ieee-14-dc-opf-lp",
        "suite": "ieee",
        "domain": "power",
        "task_type": "lp",
        "title_zh": "IEEE 14 节点 DC-OPF 教学模板",
        "title_en": "IEEE 14-bus DC-OPF teaching template",
        "source_name": "IEEE PES Power Systems Test Case Archive",
        "source_url": "https://labs.ece.uw.edu/pstca/",
        "license_note_zh": "仅引用公开算例来源；import payload 是最小教学模板，不是 IEEE 原始数据镜像。",
        "import_kind": "optimization_request",
        "target_endpoint": "/v1/optimizations",
        "discount": _discount(billing_supported=True),
        "dataset_ref": "benchmark://ieee/pstca/ieee-14",
        "sample_payload": {
            "task_type": "lp",
            "minimize": {"c": [12.0, 18.0]},
            "st": {"A": [[1.0, 1.0], [-1.0, 0.0], [0.0, -1.0]], "b": [100.0, 0.0, 0.0]},
            "options": {"max_solve_seconds": 30.0},
        },
    },
    {
        "benchmark_id": "cvrplib-a-n32-k5-vrptw",
        "suite": "cvrplib",
        "domain": "routing",
        "task_type": "lp",
        "title_zh": "CVRPLIB A-n32-k5 容量松弛 LP 模板",
        "title_en": "CVRPLIB A-n32-k5 capacity-relaxation LP template",
        "source_name": "CVRPLIB",
        "source_url": "http://vrp.galgos.inf.puc-rio.br/index.php/en/",
        "license_note_zh": "仅引用 CVRPLIB 来源；模板使用小型 synthetic 容量松弛 LP，不是 VRP 原始实例。",
        "import_kind": "optimization_request",
        "target_endpoint": "/v1/optimizations",
        "discount": _discount(billing_supported=True),
        "dataset_ref": "benchmark://cvrplib/a-n32-k5",
        "sample_payload": {
            "task_type": "lp",
            "minimize": {"c": [4.0, 6.0]},
            "st": {"A": [[2.0, 3.0], [1.0, 0.0], [0.0, 1.0]], "b": [9.0, 3.0, 3.0]},
            "options": {"max_solve_seconds": 30.0},
        },
    },
    {
        "benchmark_id": "or-lib-afiro-lp",
        "suite": "or-lib",
        "domain": "linear-programming",
        "task_type": "lp",
        "title_zh": "OR-Library AFIRO 线性规划模板",
        "title_en": "OR-Library AFIRO linear programming template",
        "source_name": "OR-Library",
        "source_url": "http://people.brunel.ac.uk/~mastjjb/jeb/orlib/orlib.html",
        "license_note_zh": "仅引用 OR-Library 来源；模板为小型 LP 结构，不包含原始 MPS 文件。",
        "import_kind": "optimization_request",
        "target_endpoint": "/v1/optimizations",
        "discount": _discount(billing_supported=True),
        "dataset_ref": "benchmark://or-lib/afiro",
        "sample_payload": {
            "task_type": "lp",
            "minimize": {"c": [1.0, 1.0]},
            "st": {"A": [[1.0, 1.0]], "b": [10.0]},
            "options": {"max_solve_seconds": 30.0},
        },
    },
    {
        "benchmark_id": "m5-walmart-forecast",
        "suite": "m5",
        "domain": "forecast",
        "task_type": "forecast",
        "title_zh": "M5 零售销量预测模板",
        "title_en": "M5 retail sales forecasting template",
        "source_name": "M5 Forecasting Accuracy Competition",
        "source_url": "https://www.kaggle.com/competitions/m5-forecasting-accuracy",
        "license_note_zh": "仅引用 M5 竞赛来源；模板是短序列示例，不包含竞赛原始销量表。",
        "import_kind": "prediction_request",
        "target_endpoint": "/v1/predictions",
        "discount": _discount(billing_supported=False),
        "dataset_ref": "benchmark://m5/forecasting-accuracy",
        "sample_payload": {"family": "arima", "data": [12.0, 14.0, 13.0, 16.0], "horizon": 2},
    },
    {
        "benchmark_id": "uci-energy-forecast",
        "suite": "uci",
        "domain": "forecast",
        "task_type": "forecast",
        "title_zh": "UCI Appliances Energy 能耗预测模板",
        "title_en": "UCI Appliances Energy forecasting template",
        "source_name": "UCI Machine Learning Repository",
        "source_url": "https://archive.ics.uci.edu/dataset/374/appliances+energy+prediction",
        "license_note_zh": "仅引用 UCI 来源；模板是小型序列示例，不包含原始能耗数据。",
        "import_kind": "prediction_request",
        "target_endpoint": "/v1/predictions",
        "discount": _discount(billing_supported=False),
        "dataset_ref": "benchmark://uci/appliances-energy-prediction",
        "sample_payload": {"family": "arima", "data": [42.0, 40.0, 43.0, 45.0], "horizon": 2},
    },
    {
        "benchmark_id": "nab-real-known-cause",
        "suite": "nab",
        "domain": "forecast",
        "task_type": "forecast",
        "title_zh": "NAB realKnownCause 异常检测预测模板",
        "title_en": "NAB realKnownCause forecasting template",
        "source_name": "Numenta Anomaly Benchmark",
        "source_url": "https://github.com/numenta/NAB",
        "license_note_zh": "仅引用 NAB 来源；模板是短序列预测示例，不包含原始异常检测数据。",
        "import_kind": "prediction_request",
        "target_endpoint": "/v1/predictions",
        "discount": _discount(billing_supported=False),
        "dataset_ref": "benchmark://nab/real-known-cause",
        "sample_payload": {"family": "arima", "data": [1.0, 1.1, 1.0, 8.0], "horizon": 1},
    },
]


def list_benchmark_library(
    *,
    suite: str | None = None,
    domain: str | None = None,
    task_type: str | None = None,
) -> list[BenchmarkLibraryItem]:
    items = BENCHMARK_LIBRARY
    if suite:
        items = [item for item in items if item["suite"] == suite]
    if domain:
        items = [item for item in items if item["domain"] == domain]
    if task_type:
        items = [item for item in items if item["task_type"] == task_type]
    return deepcopy(items)


def find_benchmark_library_item(benchmark_id: str) -> BenchmarkLibraryItem | None:
    for item in BENCHMARK_LIBRARY:
        if item["benchmark_id"] == benchmark_id:
            return deepcopy(item)
    return None


def build_import_response(benchmark_id: str) -> dict[str, Any] | None:
    item = find_benchmark_library_item(benchmark_id)
    if item is None:
        return None
    request_payload = deepcopy(item["sample_payload"])
    if item["import_kind"] == "optimization_request":
        options = dict(request_payload.get("options") or {})
        options["benchmark_library"] = True
        options["benchmark_id"] = benchmark_id
        request_payload["options"] = options
    prediction_billing_note = ""
    if item["import_kind"] == "prediction_request":
        prediction_billing_note = " prediction billing discount is not implemented in this story."
    return {
        "benchmark_id": item["benchmark_id"],
        "import_kind": item["import_kind"],
        "target_endpoint": item["target_endpoint"],
        "request_payload": request_payload,
        "discount": deepcopy(item["discount"]),
        "dataset_ref": item["dataset_ref"],
        "disclaimer_zh": (
            "该 import payload 是最小模板，不是完整数据集镜像；真实 benchmark "
            "数据请按来源许可自行获取。"
        ),
        "disclaimer_en": (
            "This import payload is a minimal template, not a full dataset mirror;"
            f"{prediction_billing_note}"
        ),
    }
