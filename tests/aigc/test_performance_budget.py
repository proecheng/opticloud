from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import scripts.report_aigc_filter_performance as performance

from tests.aigc.datasets import BENIGN_PROMPTS, RED_TEAM_PROMPTS

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "reports" / "aigc-filter" / "performance-budget.json"
EXPECTED_CORPUS_SHA256 = "7e9b075f677f0ac66b26ff3e4b5a1ef68bca5241e1db1a3dab78e1c2d91a4023"
FORBIDDEN_KEY_FRAGMENTS = (
    "absolute_path",
    "api_key",
    "bearer",
    "cookie",
    "hostname",
    "password",
    "provider_payload",
    "secret",
    "tenant",
    "timestamp",
    "username",
)


@pytest.fixture(scope="module")
def performance_report() -> dict[str, object]:
    return performance.build_report()


def _load_manifest() -> dict[str, Any]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _walk(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    values = [(path, value)]
    if isinstance(value, dict):
        for key, nested in value.items():
            values.extend(_walk(nested, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            values.extend(_walk(nested, f"{path}[{index}]"))
    return values


def _assert_no_raw_prompt_leak(data: object) -> None:
    serialized = json.dumps(data, ensure_ascii=False, sort_keys=True)
    for prompt in tuple(RED_TEAM_PROMPTS) + tuple(BENIGN_PROMPTS):
        assert prompt not in serialized


def _assert_no_forbidden_metadata(data: object) -> None:
    for path, value in _walk(data):
        if isinstance(value, dict):
            for key in value:
                normalized_key = str(key).lower().replace("-", "_")
                assert not any(
                    fragment in normalized_key for fragment in FORBIDDEN_KEY_FRAGMENTS
                ), (
                    path,
                    key,
                )
        if isinstance(value, str):
            assert "D:\\" not in value
            assert "C:\\" not in value
            assert "bearer " not in value.lower()
            assert "sk-" not in value.lower()


def test_manifest_is_deterministic_methodology_not_live_measurement() -> None:
    manifest = _load_manifest()

    assert manifest["source_story"] == performance.SOURCE_STORY
    assert manifest["filter_only_overhead"] is True
    assert manifest["not_end_to_end_chat_evidence"] is True
    assert manifest["requires_staging_chat_evidence"] is True
    assert manifest["evidence_scope"] == performance.EVIDENCE_SCOPE
    assert manifest["budget"]["filter_p95_budget_ms"] == performance.FILTER_P95_BUDGET_MS
    assert (
        manifest["budget"]["chat_first_token_hard_gate_ms"]
        == performance.CHAT_FIRST_TOKEN_HARD_GATE_MS
    )
    assert manifest["budget"]["budget_to_chat_gate_ratio"] <= 0.0334
    assert manifest["corpus"]["corpus_sha256"] == EXPECTED_CORPUS_SHA256
    assert "primary_measurement" not in manifest
    assert "secondary_measurement" not in manifest
    assert "decision" not in manifest
    _assert_no_raw_prompt_leak(manifest)
    _assert_no_forbidden_metadata(manifest)


def test_canonical_corpus_counts_and_hash_are_pinned() -> None:
    assert len(RED_TEAM_PROMPTS) == 200
    assert len(BENIGN_PROMPTS) == 100
    assert performance.corpus_sha256() == EXPECTED_CORPUS_SHA256
    assert _load_manifest()["corpus"]["corpus_sha256"] == performance.corpus_sha256()


def test_nearest_rank_percentile_and_exact_threshold_fail() -> None:
    assert performance.percentile_nearest_rank([1_000_000, 2_000_000, 3_000_000], 50) == 2.0
    assert performance.percentile_nearest_rank([1_000_000] * 19 + [100_000_000], 95) == 1.0
    assert (
        performance.percentile_nearest_rank([1_000_000] * 18 + [99_000_000, 100_000_000], 95)
        == 99.0
    )

    summary = performance.summarize_durations([100_000_000] * 20)

    assert summary["p95_ms"] == 100.0
    assert summary["passes_p95_budget"] is False
    with pytest.raises(ValueError, match="empty"):
        performance.percentile_nearest_rank([], 95)
    with pytest.raises(ValueError, match="percentile"):
        performance.percentile_nearest_rank([1], 0)


def test_measurement_repeat_count_and_call_count_are_stable() -> None:
    values = iter(range(0, 20_000, 1_000))

    durations = performance.measure_operation(
        ["a", "b"],
        lambda value: value.upper(),
        repeat_count=3,
        warmup_repeat_count=1,
        timer_ns=lambda: next(values),
    )

    assert durations == [1_000] * 6
    assert len(durations) == 2 * 3


def test_performance_report_shape_budget_and_no_chat_pass_claim(
    performance_report: dict[str, object],
) -> None:
    primary = performance_report["primary_measurement"]
    secondary = performance_report["secondary_measurement"]
    assert isinstance(primary, dict)
    assert isinstance(secondary, dict)

    assert performance_report["report_type"] == performance.REPORT_TYPE
    assert performance_report["source_story"] == performance.SOURCE_STORY
    assert performance_report["evidence_scope"] == performance.EVIDENCE_SCOPE
    assert performance_report["end_to_end_chat_first_token_passed"] is False
    assert performance_report["requires_staging_chat_evidence"] is True
    assert performance_report["decision"] == "pass"
    assert performance_report["corpus"]["red_team_count"] == 200  # type: ignore[index]
    assert performance_report["corpus"]["benign_count"] == 100  # type: ignore[index]
    assert performance_report["corpus"]["total_count"] == 300  # type: ignore[index]
    assert performance_report["corpus"]["corpus_sha256"] == EXPECTED_CORPUS_SHA256  # type: ignore[index]

    assert primary["operation"] == performance.PRIMARY_OPERATION
    assert primary["sample_count"] == 300
    assert primary["repeat_count"] == performance.MEASUREMENT_REPEAT_COUNT
    assert primary["measured_call_count"] == 300 * performance.MEASUREMENT_REPEAT_COUNT
    assert primary["latency"]["p95_ms"] < performance.FILTER_P95_BUDGET_MS  # type: ignore[index]
    assert primary["latency"]["passes_p95_budget"] is True  # type: ignore[index]

    assert secondary["operation"] == performance.SECONDARY_OPERATION
    assert secondary["sample_count"] == performance.SECONDARY_SAMPLE_COUNT
    assert (
        secondary["measured_call_count"]
        == performance.SECONDARY_SAMPLE_COUNT * performance.MEASUREMENT_REPEAT_COUNT
    )

    budget = performance_report["budget"]
    assert budget["filter_p95_budget_ms"] == performance.FILTER_P95_BUDGET_MS  # type: ignore[index]
    assert budget["chat_first_token_hard_gate_ms"] == performance.CHAT_FIRST_TOKEN_HARD_GATE_MS  # type: ignore[index]
    assert budget["budget_to_chat_gate_ratio"] <= performance.BUDGET_TO_CHAT_GATE_RATIO_LIMIT  # type: ignore[index]
    assert budget["passes_budget_relation"] is True  # type: ignore[index]

    performance.assert_report_passes(performance_report)
    _assert_no_raw_prompt_leak(performance_report)
    _assert_no_forbidden_metadata(performance_report)


def test_assert_report_passes_rejects_failed_budget(
    performance_report: dict[str, object],
) -> None:
    failed_report = json.loads(json.dumps(performance_report))
    failed_report["primary_measurement"]["latency"]["p95_ms"] = performance.FILTER_P95_BUDGET_MS
    failed_report["primary_measurement"]["latency"]["passes_p95_budget"] = False

    with pytest.raises(AssertionError, match="P95"):
        performance.assert_report_passes(failed_report)


def test_assert_report_passes_rejects_failed_budget_relation(
    performance_report: dict[str, object],
) -> None:
    failed_report = json.loads(json.dumps(performance_report))
    failed_report["budget"]["passes_budget_relation"] = False

    with pytest.raises(AssertionError, match="relation"):
        performance.assert_report_passes(failed_report)


def test_assert_report_passes_rejects_chat_pass_claim(
    performance_report: dict[str, object],
) -> None:
    bad_report = json.loads(json.dumps(performance_report))
    bad_report["end_to_end_chat_first_token_passed"] = True

    with pytest.raises(AssertionError, match="Chat"):
        performance.assert_report_passes(bad_report)
