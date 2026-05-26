from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CALIBRATOR_PATH = REPO_ROOT / "tools" / "critic_calibration" / "calibrate.py"
DATASET_PATH = REPO_ROOT / "tools" / "critic_calibration" / "ground_truth_v1.json"
CONFIG_PATH = REPO_ROOT / "apps" / "critic-service" / "config" / "critic-calibration.json"
BATCH_TOOL_PATH = REPO_ROOT / "tools" / "critic_calibration" / "create_annotation_batch.py"
BATCH_PATH = REPO_ROOT / "tools" / "critic_calibration" / "annotation_batches" / "2026-05-25.json"
MONTHLY_REPORT_PATH = (
    REPO_ROOT / "tools" / "critic_calibration" / "monthly_reports" / "2026-05.json"
)
CRITIC_ANNOTATION_PAGE_PATH = (
    REPO_ROOT / "apps" / "web" / "src" / "app" / "console" / "critic-annotation" / "page.tsx"
)


def _load_calibrator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("critic_calibration", CALIBRATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_dataset() -> dict[str, Any]:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


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


def test_committed_dataset_metrics_satisfy_g9_policy() -> None:
    calibrator = _load_calibrator()
    dataset = calibrator.load_dataset(DATASET_PATH)
    result = calibrator.calibrate_dataset(dataset)

    assert result["recommended_threshold"] == 0.6
    assert result["sample_count"] == 50
    assert result["target_stage"] == "M3.5b"
    assert result["metrics"]["recall"] >= 0.95
    assert result["metrics"]["escalate_rate_on_expected_escalate"] == result["metrics"]["recall"]
    assert result["metrics"]["false_positive_rate"] <= 0.05
    assert (
        result["metrics"]["false_escalate_rate_on_expected_non_escalate"]
        == result["metrics"]["false_positive_rate"]
    )


def test_threshold_boundary_is_strictly_less_than() -> None:
    calibrator = _load_calibrator()

    assert calibrator.predicted_escalate(0.59, 0.6) is True
    assert calibrator.predicted_escalate(0.6, 0.6) is False


def test_config_contains_no_prompt_text_or_wall_clock_timestamp() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config_text = CONFIG_PATH.read_text(encoding="utf-8")

    assert config["dataset_version"] == "ground_truth_v1"
    assert config["target_stage"] == "M3.5b"
    assert config["sample_count"] == 50
    assert config["generated_from"] == "tools/critic_calibration/ground_truth_v1.json"
    assert "prompt" not in config_text
    assert "critic_reason_zh" not in config_text
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
            if positives_changed == 2:
                break

    with pytest.raises(calibrator.CalibrationError, match="no threshold satisfies"):
        calibrator.calibrate_dataset(broken)


def test_m3_5b_dataset_preserves_seed_ids_and_adds_weekly_batch() -> None:
    dataset = _load_dataset()
    sample_ids = [sample["id"] for sample in dataset["samples"]]

    assert dataset["target_stage"] == "M3.5b"
    assert len(sample_ids) == 50
    assert sample_ids[:30] == [f"critic-cal-v1-{index:03d}" for index in range(1, 31)]
    assert sample_ids[30:] == [f"critic-cal-v1-{index:03d}" for index in range(31, 51)]

    new_samples = dataset["samples"][30:]
    for sample in new_samples:
        assert sample["source_story"] == "M3.5b"
        assert isinstance(sample["llm_output_excerpt"], str)
        assert sample["llm_output_excerpt"].strip()
        assert len(sample["llm_output_excerpt"]) <= 280

    required_categories = {
        "unsafe_code",
        "schema_error",
        "logic_error",
        "sandbox_risk",
        "benign",
        "low_risk_style",
    }
    for category in required_categories:
        assert sum(sample["category"] == category for sample in new_samples) >= 2


def test_stage_count_binding_and_m3_compatibility() -> None:
    calibrator = _load_calibrator()
    dataset = _load_dataset()
    m3_dataset = copy.deepcopy(dataset)
    m3_dataset["target_stage"] = "M3"
    m3_dataset["samples"] = [
        {key: value for key, value in sample.items() if key != "llm_output_excerpt"}
        for sample in m3_dataset["samples"][:30]
    ]

    calibrator.validate_dataset(m3_dataset)

    mislabeled_m3 = copy.deepcopy(dataset)
    mislabeled_m3["target_stage"] = "M3"
    with pytest.raises(calibrator.CalibrationError, match="M3 datasets must contain exactly 30"):
        calibrator.validate_dataset(mislabeled_m3)

    mislabeled_m3_5b = copy.deepcopy(m3_dataset)
    mislabeled_m3_5b["target_stage"] = "M3.5b"
    with pytest.raises(calibrator.CalibrationError, match="M3.5b datasets must contain exactly 50"):
        calibrator.validate_dataset(mislabeled_m3_5b)


def test_m3_5b_requires_sanitized_llm_output_excerpt() -> None:
    calibrator = _load_calibrator()
    dataset = _load_dataset()
    del dataset["samples"][30]["llm_output_excerpt"]

    with pytest.raises(calibrator.CalibrationError, match="llm_output_excerpt"):
        calibrator.validate_dataset(dataset)

    dataset = _load_dataset()
    dataset["samples"][30]["llm_output_excerpt"] = "API_KEY=sk-live-secret"
    with pytest.raises(calibrator.CalibrationError, match="llm_output_excerpt"):
        calibrator.validate_dataset(dataset)


def _run_batch_tool(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BATCH_TOOL_PATH), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_annotation_batch_generation_matches_committed_payload(tmp_path: Path) -> None:
    output_path = tmp_path / "batch.json"
    result = _run_batch_tool(
        "batch",
        "--dataset",
        str(DATASET_PATH),
        "--week-start",
        "2026-05-25",
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
    assert committed["week_start"] == "2026-05-25"
    assert committed["due_date"] == "2026-06-01"
    assert committed["sample_count"] == 20

    sample_ids = [ticket["sample_id"] for ticket in committed["tickets"]]
    assert sample_ids == [f"critic-cal-v1-{index:03d}" for index in range(31, 51)]
    assert committed["tickets"][0]["key"] == "OPTI-CRITIC-ANNOT-20260525-001"
    assert committed["tickets"][0]["annotation_ui_path"] == (
        "/console/critic-annotation?sample=critic-cal-v1-031"
    )
    assert committed["tickets"][0]["status"] == "todo"
    assert "llm_output_excerpt" in committed["tickets"][0]


def test_annotation_batch_stdout_matches_file_output() -> None:
    result = _run_batch_tool(
        "batch",
        "--dataset",
        str(DATASET_PATH),
        "--week-start",
        "2026-05-25",
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
        "2026-05-26",
    )
    assert non_monday.returncode == 1
    assert "week_start must be a Monday" in non_monday.stderr

    invalid_count = _run_batch_tool(
        "batch",
        "--dataset",
        str(DATASET_PATH),
        "--week-start",
        "2026-05-25",
        "--count",
        "0",
    )
    assert invalid_count.returncode == 1
    assert "count must be positive" in invalid_count.stderr

    dataset = _load_dataset()
    dataset["samples"] = dataset["samples"][:35]
    short_dataset = tmp_path / "short.json"
    short_dataset.write_text(json.dumps(dataset), encoding="utf-8")
    insufficient = _run_batch_tool(
        "batch",
        "--dataset",
        str(short_dataset),
        "--week-start",
        "2026-05-25",
        "--count",
        "20",
    )
    assert insufficient.returncode == 1
    assert "M3.5b datasets must contain exactly 50" in insufficient.stderr


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
        "2026-05",
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
    assert committed["sample_count"] == 50
    assert committed["target_stage"] == "M3.5b"
    assert committed["recommended_threshold"] == config["recommended_threshold"]
    assert committed["metrics"] == config["metrics"]
    assert committed["batch_sample_ids"] == [
        f"critic-cal-v1-{index:03d}" for index in range(31, 51)
    ]
    assert committed["m5_target_sample_count"] == 200
    assert committed["remaining_to_m5"] == 150
    assert "prompt" not in report_text
    assert "critic_reason_zh" not in report_text


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
        "2026-05",
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
        "2026-05",
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
        "2026-05",
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
        "2026-05",
    )
    assert reordered.returncode == 1
    assert "batch sample IDs must match newest M3.5b samples in order" in reordered.stderr


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
