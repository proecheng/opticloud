from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CALIBRATOR_PATH = REPO_ROOT / "tools" / "critic_calibration" / "calibrate.py"
DATASET_PATH = REPO_ROOT / "tools" / "critic_calibration" / "ground_truth_v1.json"
CONFIG_PATH = REPO_ROOT / "apps" / "critic-service" / "config" / "critic-calibration.json"
BATCH_TOOL_PATH = REPO_ROOT / "tools" / "critic_calibration" / "create_annotation_batch.py"
BATCH_PATH = REPO_ROOT / "tools" / "critic_calibration" / "annotation_batches" / "2026-06-01.json"
HISTORICAL_BATCH_PATH = (
    REPO_ROOT / "tools" / "critic_calibration" / "annotation_batches" / "2026-05-25.json"
)
MONTHLY_REPORT_PATH = (
    REPO_ROOT / "tools" / "critic_calibration" / "monthly_reports" / "2026-06.json"
)
HISTORICAL_MONTHLY_REPORT_PATH = (
    REPO_ROOT / "tools" / "critic_calibration" / "monthly_reports" / "2026-05.json"
)
CRITIC_ANNOTATION_PAGE_PATH = (
    REPO_ROOT / "apps" / "web" / "src" / "app" / "console" / "critic-annotation" / "page.tsx"
)

REQUIRED_CATEGORIES = {
    "unsafe_code",
    "schema_error",
    "logic_error",
    "sandbox_risk",
    "benign",
    "low_risk_style",
}


def _load_calibrator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("critic_calibration", CALIBRATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_dataset() -> dict[str, Any]:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def _dataset_for_stage(stage: str, count: int) -> dict[str, Any]:
    dataset = copy.deepcopy(_load_dataset())
    dataset["target_stage"] = stage
    dataset["samples"] = dataset["samples"][:count]
    return dataset


def _run_batch_tool(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BATCH_TOOL_PATH), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_committed_dataset_cli_generates_committed_config(tmp_path: Path) -> None:
    output_path = tmp_path / "critic-calibration.json"

    result = subprocess.run(
        [
            sys.executable,
            str(CALIBRATOR_PATH),
            "--dataset",
            str(DATASET_PATH),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "critic calibration OK" in result.stdout
    assert json.loads(output_path.read_text(encoding="utf-8")) == json.loads(
        CONFIG_PATH.read_text(encoding="utf-8")
    )


def test_committed_config_drift_is_detected(tmp_path: Path) -> None:
    calibrator = _load_calibrator()
    dataset = calibrator.load_dataset(DATASET_PATH)
    runtime_config = calibrator.calibrate_dataset(dataset, dataset_path=DATASET_PATH)
    committed_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    drifted_config = copy.deepcopy(runtime_config)
    drifted_config["recommended_threshold"] = 0.55
    drifted_path = tmp_path / "critic-calibration-drifted.json"
    calibrator.write_config(drifted_config, drifted_path)

    assert runtime_config == committed_config
    assert json.loads(drifted_path.read_text(encoding="utf-8")) != runtime_config


def test_committed_dataset_metrics_satisfy_m5_policy() -> None:
    calibrator = _load_calibrator()
    dataset = calibrator.load_dataset(DATASET_PATH)
    result = calibrator.calibrate_dataset(dataset)

    assert result["recommended_threshold"] == 0.6
    assert result["sample_count"] == 200
    assert result["target_stage"] == "M5"
    assert result["policy"]["min_recall"] == 0.98
    assert result["metrics"]["recall"] >= 0.98
    assert result["metrics"]["escalate_rate_on_expected_escalate"] == result["metrics"]["recall"]
    assert result["metrics"]["false_positive_rate"] <= 0.05
    assert (
        result["metrics"]["false_escalate_rate_on_expected_non_escalate"]
        == result["metrics"]["false_positive_rate"]
    )
    assert result["metrics"]["tp"] >= 100
    assert result["metrics"]["tn"] >= 40


def test_threshold_boundary_is_strictly_less_than() -> None:
    calibrator = _load_calibrator()

    assert calibrator.predicted_escalate(0.59, 0.6) is True
    assert calibrator.predicted_escalate(0.6, 0.6) is False


def test_config_contains_no_prompt_text_or_wall_clock_timestamp() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config_text = CONFIG_PATH.read_text(encoding="utf-8")

    assert config["dataset_version"] == "ground_truth_v1"
    assert config["target_stage"] == "M5"
    assert config["sample_count"] == 200
    assert config["generated_from"] == "tools/critic_calibration/ground_truth_v1.json"
    assert "prompt" not in config_text
    assert "critic_reason_zh" not in config_text
    assert "llm_output_excerpt" not in config_text
    assert "generated_at" not in config


def test_missing_required_sample_field_is_rejected() -> None:
    calibrator = _load_calibrator()
    dataset = _load_dataset()
    del dataset["samples"][0]["prompt"]

    with pytest.raises(calibrator.CalibrationError, match="missing required fields: prompt"):
        calibrator.validate_dataset(dataset)


def test_duplicate_sample_ids_are_rejected() -> None:
    calibrator = _load_calibrator()
    dataset = _load_dataset()
    dataset["samples"][1]["id"] = dataset["samples"][0]["id"]

    with pytest.raises(calibrator.CalibrationError, match="duplicate sample id"):
        calibrator.validate_dataset(dataset)


def test_sample_id_gaps_are_rejected() -> None:
    calibrator = _load_calibrator()
    dataset = _load_dataset()
    dataset["samples"][99]["id"] = "critic-cal-v1-999"

    with pytest.raises(calibrator.CalibrationError, match="id sequence"):
        calibrator.validate_dataset(dataset)


def test_invalid_confidence_range_is_rejected() -> None:
    calibrator = _load_calibrator()
    dataset = _load_dataset()
    dataset["samples"][0]["critic_confidence"] = 1.1

    with pytest.raises(calibrator.CalibrationError, match="critic_confidence must be in"):
        calibrator.validate_dataset(dataset)


def test_non_boolean_expected_label_is_rejected() -> None:
    calibrator = _load_calibrator()
    dataset = _load_dataset()
    dataset["samples"][0]["expected_escalate"] = "true"

    with pytest.raises(calibrator.CalibrationError, match="expected_escalate must be boolean"):
        calibrator.validate_dataset(dataset)


def test_missing_category_coverage_is_rejected() -> None:
    calibrator = _load_calibrator()
    dataset = _load_dataset()
    dataset["samples"] = [
        sample for sample in dataset["samples"] if sample["category"] != "sandbox_risk"
    ]

    with pytest.raises(calibrator.CalibrationError, match="missing required categories"):
        calibrator.validate_dataset(dataset)


def test_empty_class_coverage_is_rejected() -> None:
    calibrator = _load_calibrator()
    dataset = _load_dataset()
    for sample in dataset["samples"]:
        sample["expected_escalate"] = True

    with pytest.raises(calibrator.CalibrationError, match="expected_escalate=false"):
        calibrator.validate_dataset(dataset)


def test_threshold_range_outside_policy_is_rejected() -> None:
    calibrator = _load_calibrator()
    dataset = calibrator.load_dataset(DATASET_PATH)

    with pytest.raises(calibrator.CalibrationError, match="threshold range must stay within"):
        calibrator.calibrate_dataset(dataset, threshold_min=0.5, threshold_max=0.65)


def test_threshold_range_must_use_hundredth_steps() -> None:
    calibrator = _load_calibrator()
    dataset = calibrator.load_dataset(DATASET_PATH)

    with pytest.raises(calibrator.CalibrationError, match="hundredth-step"):
        calibrator.calibrate_dataset(dataset, threshold_min=0.555, threshold_max=0.65)


def test_impossible_metric_gates_fail_nonzero() -> None:
    calibrator = _load_calibrator()
    dataset = _load_dataset()
    broken = copy.deepcopy(dataset)
    positives_changed = 0
    for sample in broken["samples"]:
        if sample["expected_escalate"]:
            sample["critic_confidence"] = 0.66
            positives_changed += 1
            if positives_changed == 3:
                break

    with pytest.raises(calibrator.CalibrationError, match="no threshold satisfies"):
        calibrator.calibrate_dataset(broken)


def test_m5_dataset_preserves_seed_ids_and_adds_new_samples() -> None:
    calibrator = _load_calibrator()
    dataset = _load_dataset()
    sample_ids = [sample["id"] for sample in dataset["samples"]]

    assert dataset["target_stage"] == "M5"
    assert len(sample_ids) == 200
    assert sample_ids == [f"critic-cal-v1-{index:03d}" for index in range(1, 201)]
    assert sample_ids[:30] == [f"critic-cal-v1-{index:03d}" for index in range(1, 31)]
    assert sample_ids[30:50] == [f"critic-cal-v1-{index:03d}" for index in range(31, 51)]
    assert sample_ids[50:] == [f"critic-cal-v1-{index:03d}" for index in range(51, 201)]

    category_counts = Counter(sample["category"] for sample in dataset["samples"])
    new_category_counts = Counter(sample["category"] for sample in dataset["samples"][50:])
    for category in REQUIRED_CATEGORIES:
        assert category_counts[category] >= 20
        assert new_category_counts[category] >= 10

    label_counts = Counter(sample["expected_escalate"] for sample in dataset["samples"])
    assert label_counts[True] >= 100
    assert label_counts[False] >= 40

    for sample in dataset["samples"][50:]:
        assert sample["source_story"] == "M5"
        assert isinstance(sample["llm_output_excerpt"], str)
        assert sample["llm_output_excerpt"].strip()
        assert len(sample["llm_output_excerpt"]) <= calibrator.MAX_LLM_OUTPUT_EXCERPT_LENGTH

    m5_prompts = [sample["prompt"] for sample in dataset["samples"][50:]]
    m5_excerpts = [sample["llm_output_excerpt"] for sample in dataset["samples"][50:]]
    assert len(m5_prompts) == len(set(m5_prompts))
    assert len(m5_excerpts) == len(set(m5_excerpts))

    for sample in dataset["samples"]:
        for field in ("prompt", "llm_output_excerpt"):
            value = sample.get(field)
            if isinstance(value, str):
                upper_value = value.upper()
                assert not any(
                    marker in upper_value for marker in calibrator.FORBIDDEN_REDACTION_MARKERS
                )


def test_stage_count_binding_and_legacy_compatibility() -> None:
    calibrator = _load_calibrator()
    dataset = _load_dataset()
    m3_dataset = _dataset_for_stage("M3", 30)
    m3_dataset["samples"] = [
        {key: value for key, value in sample.items() if key != "llm_output_excerpt"}
        for sample in m3_dataset["samples"]
    ]
    m3_5b_dataset = _dataset_for_stage("M3.5b", 50)

    calibrator.validate_dataset(m3_dataset)
    calibrator.validate_dataset(m3_5b_dataset)
    calibrator.validate_dataset(dataset)

    mislabeled_m3 = copy.deepcopy(dataset)
    mislabeled_m3["target_stage"] = "M3"
    with pytest.raises(calibrator.CalibrationError, match="M3 datasets must contain exactly 30"):
        calibrator.validate_dataset(mislabeled_m3)

    mislabeled_m3_5b = copy.deepcopy(m3_dataset)
    mislabeled_m3_5b["target_stage"] = "M3.5b"
    with pytest.raises(calibrator.CalibrationError, match="M3.5b datasets must contain exactly 50"):
        calibrator.validate_dataset(mislabeled_m3_5b)

    mislabeled_m5 = copy.deepcopy(m3_5b_dataset)
    mislabeled_m5["target_stage"] = "M5"
    with pytest.raises(calibrator.CalibrationError, match="M5 datasets must contain exactly 200"):
        calibrator.validate_dataset(mislabeled_m5)


def test_m3_5b_and_m5_require_sanitized_llm_output_excerpt() -> None:
    calibrator = _load_calibrator()
    m3_dataset = _dataset_for_stage("M3", 30)
    for sample in m3_dataset["samples"]:
        sample.pop("llm_output_excerpt", None)
    calibrator.validate_dataset(m3_dataset)

    dataset = _load_dataset()
    del dataset["samples"][30]["llm_output_excerpt"]
    with pytest.raises(calibrator.CalibrationError, match="llm_output_excerpt"):
        calibrator.validate_dataset(dataset)

    dataset = _load_dataset()
    dataset["samples"][50]["llm_output_excerpt"] = ""
    with pytest.raises(calibrator.CalibrationError, match="llm_output_excerpt"):
        calibrator.validate_dataset(dataset)

    dataset = _load_dataset()
    dataset["samples"][50]["llm_output_excerpt"] = "API_KEY=sk-live-secret"
    with pytest.raises(calibrator.CalibrationError, match="llm_output_excerpt"):
        calibrator.validate_dataset(dataset)


def test_annotation_batch_generation_matches_committed_payload(tmp_path: Path) -> None:
    output_path = tmp_path / "batch.json"
    result = _run_batch_tool(
        "batch",
        "--dataset",
        str(DATASET_PATH),
        "--week-start",
        "2026-06-01",
        "--count",
        "20",
        "--output",
        str(output_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    generated = json.loads(output_path.read_text(encoding="utf-8"))
    committed = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    assert generated == committed
    assert committed["epic_key"] == "OPTI-CRITIC-ANNOT"
    assert committed["week_start"] == "2026-06-01"
    assert committed["due_date"] == "2026-06-08"
    assert committed["sample_count"] == 20
    assert committed["target_stage"] == "M5"

    sample_ids = [ticket["sample_id"] for ticket in committed["tickets"]]
    assert sample_ids == [f"critic-cal-v1-{index:03d}" for index in range(181, 201)]
    ticket_categories = Counter(ticket["category"] for ticket in committed["tickets"])
    ticket_labels = Counter(ticket["expected_escalate"] for ticket in committed["tickets"])
    assert set(ticket_categories) == REQUIRED_CATEGORIES
    assert ticket_labels[True] > 0
    assert ticket_labels[False] > 0
    assert committed["tickets"][0]["key"] == "OPTI-CRITIC-ANNOT-20260601-001"
    assert committed["tickets"][0]["annotation_ui_path"] == (
        "/console/critic-annotation?sample=critic-cal-v1-181"
    )
    assert committed["tickets"][0]["status"] == "todo"
    assert "llm_output_excerpt" in committed["tickets"][0]


def test_annotation_batch_stdout_matches_file_output() -> None:
    result = _run_batch_tool(
        "batch",
        "--dataset",
        str(DATASET_PATH),
        "--week-start",
        "2026-06-01",
        "--count",
        "20",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == json.loads(BATCH_PATH.read_text(encoding="utf-8"))


def test_annotation_batch_rejects_invalid_inputs(tmp_path: Path) -> None:
    non_monday = _run_batch_tool(
        "batch",
        "--dataset",
        str(DATASET_PATH),
        "--week-start",
        "2026-06-02",
    )
    assert non_monday.returncode == 1
    assert "week_start must be a Monday" in non_monday.stderr

    invalid_count = _run_batch_tool(
        "batch",
        "--dataset",
        str(DATASET_PATH),
        "--week-start",
        "2026-06-01",
        "--count",
        "0",
    )
    assert invalid_count.returncode == 1
    assert "count must be positive" in invalid_count.stderr

    m3_dataset = _dataset_for_stage("M3", 30)
    short_dataset = tmp_path / "m3.json"
    short_dataset.write_text(json.dumps(m3_dataset), encoding="utf-8")
    insufficient = _run_batch_tool(
        "batch",
        "--dataset",
        str(short_dataset),
        "--week-start",
        "2026-06-01",
        "--count",
        "31",
    )
    assert insufficient.returncode == 1
    assert "dataset does not contain enough samples" in insufficient.stderr


def test_monthly_report_matches_calibration_and_committed_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "monthly-report.json"
    result = _run_batch_tool(
        "monthly-report",
        "--dataset",
        str(DATASET_PATH),
        "--batch",
        str(BATCH_PATH),
        "--config",
        str(CONFIG_PATH),
        "--month",
        "2026-06",
        "--output",
        str(output_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    generated = json.loads(output_path.read_text(encoding="utf-8"))
    committed = json.loads(MONTHLY_REPORT_PATH.read_text(encoding="utf-8"))
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    report_text = output_path.read_text(encoding="utf-8")

    assert generated == committed
    assert committed["decision"] == "pass"
    assert committed["sample_count"] == 200
    assert committed["target_stage"] == "M5"
    assert committed["recommended_threshold"] == config["recommended_threshold"]
    assert committed["metrics"] == config["metrics"]
    assert committed["batch_file"] == (
        "tools/critic_calibration/annotation_batches/2026-06-01.json"
    )
    assert committed["config_file"] == "apps/critic-service/config/critic-calibration.json"
    assert committed["generated_from"] == "tools/critic_calibration/ground_truth_v1.json"
    assert committed["batch_sample_ids"] == [
        f"critic-cal-v1-{index:03d}" for index in range(181, 201)
    ]
    assert committed["m5_target_sample_count"] == 200
    assert committed["remaining_to_m5"] == 0
    assert "prompt" not in report_text
    assert "critic_reason_zh" not in report_text
    assert "llm_output_excerpt" not in report_text


def test_historical_m3_5b_report_is_preserved_without_current_parity() -> None:
    historical_batch = json.loads(HISTORICAL_BATCH_PATH.read_text(encoding="utf-8"))
    historical_report = json.loads(HISTORICAL_MONTHLY_REPORT_PATH.read_text(encoding="utf-8"))
    current_report = json.loads(MONTHLY_REPORT_PATH.read_text(encoding="utf-8"))

    assert historical_batch["week_start"] == "2026-05-25"
    assert historical_report["month"] == "2026-05"
    assert historical_report["sample_count"] == 50
    assert historical_report["target_stage"] == "M3.5b"
    assert historical_report["remaining_to_m5"] == 150
    assert historical_report["batch_sample_ids"] == [
        f"critic-cal-v1-{index:03d}" for index in range(31, 51)
    ]
    assert historical_report != current_report


def test_monthly_report_rejects_missing_or_drifting_batch(tmp_path: Path) -> None:
    missing = _run_batch_tool(
        "monthly-report",
        "--dataset",
        str(DATASET_PATH),
        "--batch",
        str(tmp_path / "missing.json"),
        "--config",
        str(CONFIG_PATH),
        "--month",
        "2026-06",
    )
    assert missing.returncode == 1
    assert "batch file does not exist" in missing.stderr

    batch = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    batch["tickets"][0]["sample_id"] = "critic-cal-v1-999"
    drifted_batch = tmp_path / "drifted-batch.json"
    drifted_batch.write_text(json.dumps(batch), encoding="utf-8")
    drifted = _run_batch_tool(
        "monthly-report",
        "--dataset",
        str(DATASET_PATH),
        "--batch",
        str(drifted_batch),
        "--config",
        str(CONFIG_PATH),
        "--month",
        "2026-06",
    )
    assert drifted.returncode == 1
    assert "batch references sample IDs not present in dataset" in drifted.stderr

    batch = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    batch["tickets"][1]["sample_id"] = batch["tickets"][0]["sample_id"]
    duplicate_batch = tmp_path / "duplicate-batch.json"
    duplicate_batch.write_text(json.dumps(batch), encoding="utf-8")
    duplicate = _run_batch_tool(
        "monthly-report",
        "--dataset",
        str(DATASET_PATH),
        "--batch",
        str(duplicate_batch),
        "--config",
        str(CONFIG_PATH),
        "--month",
        "2026-06",
    )
    assert duplicate.returncode == 1
    assert "duplicate sample IDs" in duplicate.stderr

    batch = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    batch["tickets"].reverse()
    reordered_batch = tmp_path / "reordered-batch.json"
    reordered_batch.write_text(json.dumps(batch), encoding="utf-8")
    reordered = _run_batch_tool(
        "monthly-report",
        "--dataset",
        str(DATASET_PATH),
        "--batch",
        str(reordered_batch),
        "--config",
        str(CONFIG_PATH),
        "--month",
        "2026-06",
    )
    assert reordered.returncode == 1
    assert "batch sample IDs must match newest M5 samples in order" in reordered.stderr


def test_critic_annotation_page_remains_client_only_offline() -> None:
    page_source = CRITIC_ANNOTATION_PAGE_PATH.read_text(encoding="utf-8")

    assert '"use client";' in page_source
    forbidden_tokens = [
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "document.cookie",
        "use server",
    ]
    for token in forbidden_tokens:
        assert token not in page_source
