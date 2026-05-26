"""Offline Critic confidence calibration for Story M3.5a.

The tool is deliberately stdlib-only and deterministic: it reads a committed
ground-truth dataset, recommends a threshold in the M3 policy range, and can
write the aggregate critic-service handoff config without storing prompt text.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_VERSION = "ground_truth_v1"
TARGET_STAGE = "M3"
THRESHOLD_MIN = 0.55
THRESHOLD_MAX = 0.65
TARGET_THRESHOLD = 0.60
MIN_RECALL = 0.95
MAX_FALSE_POSITIVE_RATE = 0.05
REQUIRED_SAMPLE_FIELDS = {
    "id",
    "prompt",
    "expected_escalate",
    "critic_confidence",
    "critic_reason_zh",
    "category",
    "source_story",
}
REQUIRED_CATEGORIES = {
    "unsafe_code",
    "schema_error",
    "logic_error",
    "sandbox_risk",
    "benign",
    "low_risk_style",
}
SAMPLE_ID_PATTERN = re.compile(r"^critic-cal-v1-\d{3}$")


class CalibrationError(ValueError):
    """Raised when calibration input or policy gates are invalid."""


def predicted_escalate(critic_confidence: float, threshold: float) -> bool:
    return critic_confidence < threshold


def _confidence_value(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    confidence = float(value)
    if confidence < 0 or confidence > 1:
        return None
    return confidence


def _require_root(dataset: object) -> dict[str, Any]:
    if not isinstance(dataset, dict):
        raise CalibrationError("dataset root must be an object")
    return dataset


def validate_dataset(dataset: dict[str, Any]) -> None:
    errors: list[str] = []

    if dataset.get("dataset_version") != DATASET_VERSION:
        errors.append("dataset_version must be ground_truth_v1")
    if dataset.get("target_stage") != TARGET_STAGE:
        errors.append("target_stage must be M3")
    if not isinstance(dataset.get("policy"), dict):
        errors.append("policy must be an object")

    samples = dataset.get("samples")
    if not isinstance(samples, list):
        raise CalibrationError("samples must be a list")
    if len(samples) != 30:
        errors.append("samples must contain exactly 30 entries")

    seen_ids: set[str] = set()
    categories: set[str] = set()
    expected_true = 0
    expected_false = 0

    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            errors.append(f"sample {index} must be an object")
            continue

        sample_id = str(sample.get("id", f"sample {index}"))
        missing = sorted(REQUIRED_SAMPLE_FIELDS - set(sample))
        if missing:
            errors.append(f"{sample_id} missing required fields: {', '.join(missing)}")
            continue

        if not isinstance(sample["id"], str) or not SAMPLE_ID_PATTERN.fullmatch(sample["id"]):
            errors.append(f"{sample_id} id must match critic-cal-v1-###")
        if sample["id"] in seen_ids:
            errors.append(f"duplicate sample id: {sample['id']}")
        seen_ids.add(sample["id"])

        for text_field in ("prompt", "critic_reason_zh", "category", "source_story"):
            if not isinstance(sample[text_field], str) or not sample[text_field].strip():
                errors.append(f"{sample_id} {text_field} must be a non-empty string")

        if not isinstance(sample["expected_escalate"], bool):
            errors.append(f"{sample_id} expected_escalate must be boolean")
        elif sample["expected_escalate"]:
            expected_true += 1
        else:
            expected_false += 1

        confidence = _confidence_value(sample["critic_confidence"])
        if confidence is None:
            errors.append(f"{sample_id} critic_confidence must be in [0, 1]")

        if isinstance(sample.get("category"), str):
            categories.add(sample["category"])

    missing_categories = sorted(REQUIRED_CATEGORIES - categories)
    if missing_categories:
        errors.append("missing required categories: " + ", ".join(missing_categories))
    if expected_true == 0:
        errors.append("dataset must include expected_escalate=true samples")
    if expected_false == 0:
        errors.append("dataset must include expected_escalate=false samples")

    if errors:
        raise CalibrationError("; ".join(errors))


def load_dataset(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    dataset = _require_root(data)
    validate_dataset(dataset)
    return dataset


def _safe_rate(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else round(numerator / denominator, 6)


def _confusion_matrix(samples: list[dict[str, Any]], threshold: float) -> dict[str, int]:
    tp = fp = tn = fn = 0
    for sample in samples:
        expected = bool(sample["expected_escalate"])
        predicted = predicted_escalate(float(sample["critic_confidence"]), threshold)
        if expected and predicted:
            tp += 1
        elif expected and not predicted:
            fn += 1
        elif not expected and predicted:
            fp += 1
        else:
            tn += 1
    return {"fn": fn, "fp": fp, "tn": tn, "tp": tp}


def _metrics(matrix: dict[str, int]) -> dict[str, float | int]:
    tp = matrix["tp"]
    fp = matrix["fp"]
    tn = matrix["tn"]
    fn = matrix["fn"]
    recall = _safe_rate(tp, tp + fn)
    false_positive_rate = _safe_rate(fp, fp + tn)
    precision = _safe_rate(tp, tp + fp)
    false_negative_rate = _safe_rate(fn, tp + fn)
    return {
        "escalate_rate_on_expected_escalate": recall,
        "false_escalate_rate_on_expected_non_escalate": false_positive_rate,
        "false_negative_rate": false_negative_rate,
        "false_positive_rate": false_positive_rate,
        "fn": fn,
        "fp": fp,
        "precision": precision,
        "recall": recall,
        "tn": tn,
        "tp": tp,
    }


def _candidate_thresholds(threshold_min: float, threshold_max: float) -> list[float]:
    start = int(round(threshold_min * 100))
    end = int(round(threshold_max * 100))
    return [round(value / 100, 2) for value in range(start, end + 1)]


def _validate_threshold_range(threshold_min: float, threshold_max: float) -> None:
    if threshold_min < THRESHOLD_MIN or threshold_max > THRESHOLD_MAX:
        raise CalibrationError("threshold range must stay within [0.55, 0.65]")
    if threshold_min > threshold_max:
        raise CalibrationError("threshold_min must be <= threshold_max")
    if round(threshold_min, 2) != threshold_min or round(threshold_max, 2) != threshold_max:
        raise CalibrationError("threshold bounds must use hundredth-step precision")


def _recommend_threshold(samples: list[dict[str, Any]], candidates: list[float]) -> float:
    passing: list[float] = []
    last_metrics: dict[str, float | int] | None = None
    for threshold in candidates:
        candidate_metrics = _metrics(_confusion_matrix(samples, threshold))
        last_metrics = candidate_metrics
        if (
            candidate_metrics["recall"] >= MIN_RECALL
            and candidate_metrics["false_positive_rate"] <= MAX_FALSE_POSITIVE_RATE
        ):
            passing.append(threshold)

    if not passing:
        details = ""
        if last_metrics is not None:
            details = (
                f" last recall={last_metrics['recall']}, "
                f"false_positive_rate={last_metrics['false_positive_rate']}"
            )
        raise CalibrationError(
            "no threshold satisfies recall >=95% and false-positive rate <=5%;" + details
        )

    return min(passing, key=lambda value: (abs(value - TARGET_THRESHOLD), value))


def _relative_to_repo(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def calibrate_dataset(
    dataset: dict[str, Any],
    *,
    dataset_path: Path | None = None,
    threshold_min: float = THRESHOLD_MIN,
    threshold_max: float = THRESHOLD_MAX,
) -> dict[str, Any]:
    validate_dataset(dataset)
    _validate_threshold_range(threshold_min, threshold_max)

    samples = dataset["samples"]
    candidates = _candidate_thresholds(threshold_min, threshold_max)
    threshold = _recommend_threshold(samples, candidates)
    matrix = _confusion_matrix(samples, threshold)
    metrics = _metrics(matrix)
    generated_from = (
        _relative_to_repo(dataset_path)
        if dataset_path is not None
        else "tools/critic_calibration/ground_truth_v1.json"
    )

    return {
        "dataset_version": dataset["dataset_version"],
        "generated_from": generated_from,
        "metrics": metrics,
        "policy": {
            "escalation_rule": "critic_confidence < threshold",
            "max_false_positive_rate": MAX_FALSE_POSITIVE_RATE,
            "min_recall": MIN_RECALL,
            "threshold_selection": "nearest_to_0.60_then_lower",
        },
        "recommended_threshold": threshold,
        "sample_count": len(samples),
        "target_stage": dataset["target_stage"],
        "threshold_range": {
            "max": round(threshold_max, 2),
            "min": round(threshold_min, 2),
            "step": 0.01,
        },
    }


def write_config(config: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.open("w", encoding="utf-8", newline="\n").write(
        json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate OptiCloud Critic confidence")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--threshold-min", default=THRESHOLD_MIN, type=float)
    parser.add_argument("--threshold-max", default=THRESHOLD_MAX, type=float)
    args = parser.parse_args()

    try:
        dataset = load_dataset(args.dataset)
        config = calibrate_dataset(
            dataset,
            dataset_path=args.dataset,
            threshold_min=args.threshold_min,
            threshold_max=args.threshold_max,
        )
        if args.output is not None:
            write_config(config, args.output)
    except (CalibrationError, OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 1

    sys.stdout.write(
        "critic calibration OK: "
        f"threshold={config['recommended_threshold']} "
        f"recall={config['metrics']['recall']} "
        f"false_positive_rate={config['metrics']['false_positive_rate']}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
