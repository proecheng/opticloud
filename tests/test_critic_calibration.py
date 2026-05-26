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
    assert result["sample_count"] == 30
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
    assert config["target_stage"] == "M3"
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
