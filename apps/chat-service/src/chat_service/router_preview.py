from __future__ import annotations

import re

from chat_service.schemas import ChatLocale, RouterPreview, TaskType

SUPPORTED_TASK_TYPES: tuple[TaskType, ...] = (
    "lp",
    "vrptw",
    "prediction",
    "schedule",
    "inventory",
    "unknown",
)

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_ASCII_ALPHA_RE = re.compile(r"[A-Za-z]")

_KEYWORD_RULES: tuple[tuple[TaskType, float, tuple[str, ...], str], ...] = (
    (
        "vrptw",
        0.86,
        (
            "最短路径",
            "车辆",
            "路线",
            "路径",
            "配送",
            "时间窗",
            "vrptw",
            "vehicle routing",
            "route",
            "routing",
        ),
        "matched route or vehicle-routing keywords",
    ),
    (
        "lp",
        0.82,
        (
            "线性规划",
            "目标函数",
            "约束",
            "linear programming",
            " lp ",
            "objective",
            "constraint",
        ),
        "matched linear-programming keywords",
    ),
    (
        "prediction",
        0.8,
        (
            "预测",
            "时间序列",
            "销量",
            "需求",
            "forecast",
            "prediction",
            "time series",
        ),
        "matched prediction keywords",
    ),
    (
        "schedule",
        0.78,
        (
            "排程",
            "排班",
            "工序",
            "班次",
            "schedule",
            "scheduling",
            "shift",
        ),
        "matched scheduling keywords",
    ),
    (
        "inventory",
        0.78,
        (
            "库存",
            "补货",
            "sku",
            "inventory",
            "stock",
            "replenishment",
        ),
        "matched inventory keywords",
    ),
)


def detect_locale(message: str) -> ChatLocale:
    has_cjk = _CJK_RE.search(message) is not None
    has_ascii = _ASCII_ALPHA_RE.search(message) is not None
    if has_cjk and has_ascii:
        return "mixed"
    if has_cjk:
        return "zh-CN"
    return "en-US"


def build_message_excerpt(message: str, *, max_chars: int = 64) -> str:
    trimmed = message.strip()
    if len(trimmed) <= 4:
        return f"{trimmed[:1]}..."
    excerpt_body = trimmed[: max(1, min(max_chars - 3, len(trimmed) - 1))]
    return f"{excerpt_body}..."


def classify_message(message: str) -> RouterPreview:
    normalized = f" {message.lower()} "
    for task_type, confidence, keywords, reasoning in _KEYWORD_RULES:
        if any(keyword in normalized for keyword in keywords):
            return RouterPreview(
                task_type=task_type,
                confidence=confidence,
                reasoning=reasoning,
                source="heuristic_internal_beta",
                supported_task_types=list(SUPPORTED_TASK_TYPES),
            )
    return RouterPreview(
        task_type="unknown",
        confidence=0.35,
        reasoning="no supported task-type keyword matched",
        source="heuristic_internal_beta",
        supported_task_types=list(SUPPORTED_TASK_TYPES),
    )
