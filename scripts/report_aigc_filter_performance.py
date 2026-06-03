"""Emit an offline AIGC filter performance budget report for Story 8.B.9."""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Callable, Sequence
from hashlib import sha256
from pathlib import Path
from time import perf_counter_ns
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_PY = ROOT / "packages" / "shared-py"
for import_path in (ROOT, SHARED_PY):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import aigc_filter  # noqa: E402
from tests.aigc.datasets import BENIGN_PROMPTS, RED_TEAM_PROMPTS  # noqa: E402

SOURCE_STORY = "8.B.9"
REPORT_TYPE = "aigc_filter_performance_budget"
EVIDENCE_SCOPE = "filter_only_overhead"
PRIMARY_OPERATION = "aigc_filter.filter(prompt, tier='strict')"
SECONDARY_OPERATION = "aigc_filter.filter(already_watermarked_text, tier='strict')"
FILTER_P95_BUDGET_MS = 100.0
CHAT_FIRST_TOKEN_HARD_GATE_MS = 3000.0
BUDGET_TO_CHAT_GATE_RATIO_LIMIT = 0.0334
WARMUP_REPEAT_COUNT = 1
MEASUREMENT_REPEAT_COUNT = 5
SECONDARY_SAMPLE_COUNT = 20
PERCENTILE_METHOD = "nearest_rank"


def canonical_corpus() -> dict[str, list[str]]:
    """Return the canonical corpus used for AIGC performance budgeting."""

    return {
        "benign": list(BENIGN_PROMPTS),
        "red_team": list(RED_TEAM_PROMPTS),
    }


def canonical_json_bytes(data: object) -> bytes:
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def corpus_sha256() -> str:
    return sha256(canonical_json_bytes(canonical_corpus())).hexdigest()


def percentile_nearest_rank(values: Sequence[int], percentile: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    if percentile <= 0 or percentile > 100:
        raise ValueError("percentile must be in (0, 100]")

    sorted_values = sorted(values)
    rank = math.ceil((percentile / 100.0) * len(sorted_values))
    index = min(max(rank - 1, 0), len(sorted_values) - 1)
    return sorted_values[index] / 1_000_000


def summarize_durations(durations_ns: Sequence[int]) -> dict[str, float | int | bool]:
    p95_ms = percentile_nearest_rank(durations_ns, 95)
    return {
        "call_count": len(durations_ns),
        "max_ms": max(durations_ns) / 1_000_000,
        "p50_ms": percentile_nearest_rank(durations_ns, 50),
        "p95_ms": p95_ms,
        "p99_ms": percentile_nearest_rank(durations_ns, 99),
        "passes_p95_budget": p95_ms < FILTER_P95_BUDGET_MS,
    }


def measure_operation(
    inputs: Sequence[str],
    operation: Callable[[str], object],
    *,
    repeat_count: int = MEASUREMENT_REPEAT_COUNT,
    warmup_repeat_count: int = WARMUP_REPEAT_COUNT,
    timer_ns: Callable[[], int] = perf_counter_ns,
) -> list[int]:
    if not inputs:
        raise ValueError("inputs must not be empty")
    if repeat_count <= 0:
        raise ValueError("repeat_count must be positive")
    if warmup_repeat_count < 0:
        raise ValueError("warmup_repeat_count must be non-negative")

    for _ in range(warmup_repeat_count):
        for item in inputs:
            operation(item)

    durations_ns: list[int] = []
    for _ in range(repeat_count):
        for item in inputs:
            started_ns = timer_ns()
            operation(item)
            durations_ns.append(timer_ns() - started_ns)
    return durations_ns


def _filter_strict(text: str) -> aigc_filter.FilterResult:
    return aigc_filter.filter(text, tier="strict")


def _secondary_inputs() -> tuple[str, ...]:
    prompts = tuple(RED_TEAM_PROMPTS[: SECONDARY_SAMPLE_COUNT // 2]) + tuple(
        BENIGN_PROMPTS[: SECONDARY_SAMPLE_COUNT // 2]
    )
    return tuple(_filter_strict(prompt).text for prompt in prompts)


def _measurement_block(
    *,
    operation_name: str,
    sample_count: int,
    repeat_count: int,
    durations_ns: Sequence[int],
) -> dict[str, object]:
    summary = summarize_durations(durations_ns)
    measured_call_count = sample_count * repeat_count
    if summary["call_count"] != measured_call_count:
        raise RuntimeError("measured call count does not match sample_count * repeat_count")
    return {
        "operation": operation_name,
        "sample_count": sample_count,
        "repeat_count": repeat_count,
        "measured_call_count": measured_call_count,
        "latency": summary,
    }


def build_report(
    *,
    repeat_count: int = MEASUREMENT_REPEAT_COUNT,
    warmup_repeat_count: int = WARMUP_REPEAT_COUNT,
) -> dict[str, object]:
    if len(RED_TEAM_PROMPTS) != 200:
        raise RuntimeError("RED_TEAM_PROMPTS must contain exactly 200 prompts")
    if len(BENIGN_PROMPTS) != 100:
        raise RuntimeError("BENIGN_PROMPTS must contain exactly 100 prompts")

    primary_inputs = tuple(RED_TEAM_PROMPTS) + tuple(BENIGN_PROMPTS)
    primary_durations = measure_operation(
        primary_inputs,
        _filter_strict,
        repeat_count=repeat_count,
        warmup_repeat_count=warmup_repeat_count,
    )
    secondary_inputs = _secondary_inputs()
    secondary_durations = measure_operation(
        secondary_inputs,
        _filter_strict,
        repeat_count=repeat_count,
        warmup_repeat_count=warmup_repeat_count,
    )

    primary = _measurement_block(
        operation_name=PRIMARY_OPERATION,
        sample_count=len(primary_inputs),
        repeat_count=repeat_count,
        durations_ns=primary_durations,
    )
    secondary = _measurement_block(
        operation_name=SECONDARY_OPERATION,
        sample_count=len(secondary_inputs),
        repeat_count=repeat_count,
        durations_ns=secondary_durations,
    )
    primary_latency = primary["latency"]
    if not isinstance(primary_latency, dict):
        raise RuntimeError("primary latency summary must be an object")

    budget_to_chat_gate_ratio = FILTER_P95_BUDGET_MS / CHAT_FIRST_TOKEN_HARD_GATE_MS
    passes_budget_relation = budget_to_chat_gate_ratio <= BUDGET_TO_CHAT_GATE_RATIO_LIMIT
    budget_pass = bool(primary_latency["passes_p95_budget"]) and passes_budget_relation
    return {
        "budget": {
            "budget_to_chat_gate_ratio": budget_to_chat_gate_ratio,
            "budget_to_chat_gate_ratio_limit": BUDGET_TO_CHAT_GATE_RATIO_LIMIT,
            "chat_first_token_hard_gate_ms": CHAT_FIRST_TOKEN_HARD_GATE_MS,
            "filter_p95_budget_ms": FILTER_P95_BUDGET_MS,
            "passes_budget_relation": passes_budget_relation,
        },
        "corpus": {
            "benign_count": len(BENIGN_PROMPTS),
            "corpus_sha256": corpus_sha256(),
            "red_team_count": len(RED_TEAM_PROMPTS),
            "total_count": len(primary_inputs),
        },
        "decision": "pass" if budget_pass else "fail",
        "end_to_end_chat_first_token_passed": False,
        "evidence_scope": EVIDENCE_SCOPE,
        "methodology": {
            "measurement_repeat_count": repeat_count,
            "percentile_method": PERCENTILE_METHOD,
            "timer": "time.perf_counter_ns",
            "warmup_repeat_count": warmup_repeat_count,
        },
        "module_version": aigc_filter.__version__,
        "primary_measurement": primary,
        "report_type": REPORT_TYPE,
        "requires_staging_chat_evidence": True,
        "secondary_measurement": secondary,
        "source_story": SOURCE_STORY,
    }


def assert_report_passes(report: dict[str, Any]) -> None:
    primary = report["primary_measurement"]
    if not isinstance(primary, dict):
        raise AssertionError("primary_measurement must be an object")
    latency = primary["latency"]
    if not isinstance(latency, dict):
        raise AssertionError("primary_measurement.latency must be an object")
    if latency["p95_ms"] >= FILTER_P95_BUDGET_MS:
        raise AssertionError("AIGC filter primary P95 latency budget failed")

    budget = report["budget"]
    if not isinstance(budget, dict):
        raise AssertionError("budget must be an object")
    if budget["passes_budget_relation"] is not True:
        raise AssertionError("AIGC filter budget-to-chat relation failed")
    if report["end_to_end_chat_first_token_passed"] is not False:
        raise AssertionError("report must not claim end-to-end Chat first-token pass")
    if report["requires_staging_chat_evidence"] is not True:
        raise AssertionError("report must require staging Chat evidence")


def main() -> int:
    report = build_report()
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    try:
        assert_report_passes(report)
    except AssertionError as error:
        sys.stderr.write(f"{error}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
