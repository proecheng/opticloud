"""Deterministic Critic annotation batch and monthly report generator.

This tool is deliberately offline and credential-free. It creates Linear-compatible
ticket payloads and monthly aggregate reports from committed calibration artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from calibrate import CalibrationError, calibrate_dataset, load_dataset

REPO_ROOT = Path(__file__).resolve().parents[2]
EPIC_KEY = "OPTI-CRITIC-ANNOT"
ANNOTATION_UI_BASE = "/console/critic-annotation"
M5_TARGET_SAMPLE_COUNT = 200


def _relative_to_repo(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _write_json(payload: dict[str, Any], output_path: Path | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output_path is None:
        sys.stdout.write(text)
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.open("w", encoding="utf-8", newline="\n").write(text)


def _parse_monday(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise CalibrationError("week_start must be a valid ISO date") from exc
    if parsed.weekday() != 0:
        raise CalibrationError("week_start must be a Monday")
    return parsed


def _sample_number(sample: dict[str, Any]) -> int:
    sample_id = str(sample["id"])
    return int(sample_id.rsplit("-", 1)[1])


def create_batch_payload(dataset_path: Path, week_start: str, count: int) -> dict[str, Any]:
    if count <= 0:
        raise CalibrationError("count must be positive")

    dataset = load_dataset(dataset_path)
    start = _parse_monday(week_start)
    due = start + timedelta(days=7)
    samples = sorted(dataset["samples"], key=_sample_number)
    if len(samples) < count:
        raise CalibrationError("dataset does not contain enough samples for requested count")

    batch_samples = samples[-count:]
    if any(sample.get("source_story") != "M3.5b" for sample in batch_samples):
        raise CalibrationError("newest batch samples must all have source_story=M3.5b")

    ticket_prefix = f"{EPIC_KEY}-{start:%Y%m%d}"
    tickets: list[dict[str, Any]] = []
    for index, sample in enumerate(batch_samples, start=1):
        sample_id = str(sample["id"])
        tickets.append(
            {
                "annotation_ui_path": f"{ANNOTATION_UI_BASE}?sample={sample_id}",
                "category": sample["category"],
                "critic_confidence": sample["critic_confidence"],
                "due_date": due.isoformat(),
                "expected_escalate": sample["expected_escalate"],
                "key": f"{ticket_prefix}-{index:03d}",
                "llm_output_excerpt": sample["llm_output_excerpt"],
                "prompt": sample["prompt"],
                "sample_id": sample_id,
                "status": "todo",
            }
        )

    return {
        "dataset_version": dataset["dataset_version"],
        "due_date": due.isoformat(),
        "epic_key": EPIC_KEY,
        "sample_count": len(tickets),
        "ticket_prefix": ticket_prefix,
        "tickets": tickets,
        "week_start": start.isoformat(),
    }


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise CalibrationError(f"{label} file does not exist: {_relative_to_repo(path)}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CalibrationError(f"{label} file must contain a JSON object")
    return data


def create_monthly_report_payload(
    dataset_path: Path,
    batch_path: Path,
    config_path: Path,
    month: str,
) -> dict[str, Any]:
    dataset = load_dataset(dataset_path)
    batch = _load_json_object(batch_path, "batch")
    config = _load_json_object(config_path, "config")
    calibration = calibrate_dataset(dataset, dataset_path=dataset_path)
    if calibration != config:
        raise CalibrationError("config does not match calibration output")

    tickets = batch.get("tickets")
    if not isinstance(tickets, list):
        raise CalibrationError("batch tickets must be a list")
    batch_count = batch.get("sample_count")
    if batch_count != len(tickets):
        raise CalibrationError("batch sample_count must match ticket count")
    batch_sample_ids: list[str] = []
    for ticket in tickets:
        if not isinstance(ticket, dict) or not isinstance(ticket.get("sample_id"), str):
            raise CalibrationError("batch tickets must include sample_id strings")
        batch_sample_ids.append(ticket["sample_id"])
    if len(batch_sample_ids) != len(set(batch_sample_ids)):
        raise CalibrationError("batch contains duplicate sample IDs")

    dataset_ids = {str(sample["id"]) for sample in dataset["samples"]}
    missing = sorted(set(batch_sample_ids) - dataset_ids)
    if missing:
        raise CalibrationError(
            "batch references sample IDs not present in dataset: " + ", ".join(missing)
        )
    expected_samples = sorted(dataset["samples"], key=_sample_number)[-len(batch_sample_ids) :]
    if any(sample.get("source_story") != "M3.5b" for sample in expected_samples):
        raise CalibrationError("expected monthly batch samples must all have source_story=M3.5b")
    expected_sample_ids = [str(sample["id"]) for sample in expected_samples]
    if batch_sample_ids != expected_sample_ids:
        raise CalibrationError("batch sample IDs must match newest M3.5b samples in order")

    sample_count = int(calibration["sample_count"])
    return {
        "batch_file": _relative_to_repo(batch_path),
        "batch_sample_ids": batch_sample_ids,
        "config_file": _relative_to_repo(config_path),
        "dataset_version": calibration["dataset_version"],
        "decision": "pass",
        "generated_from": _relative_to_repo(dataset_path),
        "m5_target_sample_count": M5_TARGET_SAMPLE_COUNT,
        "metrics": calibration["metrics"],
        "month": month,
        "recommended_threshold": calibration["recommended_threshold"],
        "remaining_to_m5": M5_TARGET_SAMPLE_COUNT - sample_count,
        "sample_count": sample_count,
        "target_stage": calibration["target_stage"],
        "threshold_note": (
            "threshold remains 0.60"
            if calibration["recommended_threshold"] == 0.6
            else "threshold follows calibration recommendation"
        ),
    }


def _run_batch(args: argparse.Namespace) -> None:
    payload = create_batch_payload(args.dataset, args.week_start, args.count)
    _write_json(payload, args.output)


def _run_monthly_report(args: argparse.Namespace) -> None:
    payload = create_monthly_report_payload(args.dataset, args.batch, args.config, args.month)
    _write_json(payload, args.output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create Critic annotation artifacts")
    subparsers = parser.add_subparsers(dest="command", required=True)

    batch_parser = subparsers.add_parser("batch", help="create weekly annotation batch payload")
    batch_parser.add_argument("--dataset", required=True, type=Path)
    batch_parser.add_argument("--week-start", required=True)
    batch_parser.add_argument("--count", default=20, type=int)
    batch_parser.add_argument("--output", type=Path)
    batch_parser.set_defaults(func=_run_batch)

    report_parser = subparsers.add_parser(
        "monthly-report", help="create monthly calibration report"
    )
    report_parser.add_argument("--dataset", required=True, type=Path)
    report_parser.add_argument("--batch", required=True, type=Path)
    report_parser.add_argument("--config", required=True, type=Path)
    report_parser.add_argument("--month", required=True)
    report_parser.add_argument("--output", type=Path)
    report_parser.set_defaults(func=_run_monthly_report)

    args = parser.parse_args()
    try:
        args.func(args)
    except (CalibrationError, OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
