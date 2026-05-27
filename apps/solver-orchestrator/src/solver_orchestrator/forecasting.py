"""Deterministic lightweight forecasting helpers for Story 3.2.

This is an algorithm mock abstraction, not a real ARIMA/Chronos runtime. It is
small, deterministic, and CI-safe while preserving the public prediction shape.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ForecastResult:
    p10: list[float]
    p50: list[float]
    p90: list[float]
    drift_score: float
    predict_seconds: float


def predict_quantiles(data: list[float], horizon: int) -> ForecastResult:
    """Return deterministic P10/P50/P90 forecasts and a bounded drift score."""
    if len(data) < 2:
        raise ValueError("data must contain at least 2 points")
    if horizon < 1:
        raise ValueError("horizon must be >= 1")

    tail = data[-min(len(data), 12) :]
    deltas = [tail[i] - tail[i - 1] for i in range(1, len(tail))]
    trend = sum(deltas) / len(deltas) if deltas else 0.0
    abs_deltas = [abs(delta) for delta in deltas]
    mean_abs_delta = sum(abs_deltas) / len(abs_deltas) if abs_deltas else 0.0
    level = max(abs(data[-1]), 1.0)
    spread_base = max(mean_abs_delta, _population_std(tail), level * 0.02)
    drift_score = _clamp(mean_abs_delta / (mean_abs_delta + level), 0.0, 1.0)

    p50: list[float] = []
    p10: list[float] = []
    p90: list[float] = []
    last_value = data[-1]
    for step in range(1, horizon + 1):
        median = last_value + trend * step
        spread = spread_base * math.sqrt(step)
        lower = median - spread
        upper = median + spread
        p10.append(_stable_float(lower))
        p50.append(_stable_float(median))
        p90.append(_stable_float(upper))

    return ForecastResult(
        p10=p10,
        p50=p50,
        p90=p90,
        drift_score=_stable_float(drift_score),
        predict_seconds=0.0,
    )


def _population_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _stable_float(value: float) -> float:
    return round(float(value), 6)
