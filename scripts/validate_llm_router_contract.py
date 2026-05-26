from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "packages" / "shared-py"))

from opticloud_shared.llm_router.parity import (  # noqa: E402
    PARITY_THRESHOLD,
    compute_behavior_parity_report,
)
from opticloud_shared.llm_router.registry import (  # noqa: E402
    CANONICAL_IMPLEMENTATION_IDS,
    CANONICAL_MODEL_ALIASES,
    CANONICAL_PROVIDER_IDS,
    default_model_registry,
    default_provider_configs,
)
from opticloud_shared.llm_router.schemas import Prompt  # noqa: E402

DEFAULT_REFERENCE_PROMPTS = REPO_ROOT / "tools" / "llm_router" / "reference_prompts_v1.json"
DEFAULT_PARITY_REPORT = REPO_ROOT / "tools" / "llm_router" / "parity_report.example.json"
FORBIDDEN_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{6,}|bearer\s+[A-Za-z0-9._-]+|api[_-]?key|customer_prompt|"
    r"user_prompt|raw provider|provider_response|provider_request|live provider|reports/)",
    re.IGNORECASE,
)
TASK_COUNTS = {
    "router_intent": 20,
    "formulator_extraction": 20,
    "coder_generation": 20,
    "critic_validation": 20,
    "mixed_language_summary": 20,
}


class ValidationError(RuntimeError):
    pass


def validate_registry() -> None:
    providers = default_provider_configs()
    registry = default_model_registry()
    if tuple(providers) != CANONICAL_PROVIDER_IDS:
        raise ValidationError("canonical provider IDs drifted")
    if tuple(item.implementation_id for item in providers.values()) != CANONICAL_IMPLEMENTATION_IDS:
        raise ValidationError("canonical implementation IDs drifted")
    if tuple(registry) != CANONICAL_MODEL_ALIASES:
        raise ValidationError("canonical model aliases drifted")
    expected_aliases = {
        "deepseek-v3.5": "deepseek-compatible",
        "qwen-max": "qwen-compatible",
        "mock-deterministic": "mock",
    }
    for alias, provider_id in expected_aliases.items():
        item = registry[alias]
        if item.provider_id != provider_id:
            raise ValidationError(f"alias mapping drifted for {alias}")
        if item.provider_id not in providers:
            raise ValidationError(f"alias {alias} references missing provider")
        if item.provider_model == item.alias and alias == "deepseek-v3.5":
            raise ValidationError("deepseek logical alias must remain separate from provider model")


def validate_reference_prompts(path: Path) -> dict[str, Any]:
    fixture = _load_json(path)
    if fixture.get("dataset_version") != "llm_router_reference_prompts_v1":
        raise ValidationError("reference prompt dataset_version drifted")
    if fixture.get("source_story") != "M3.8":
        raise ValidationError("reference prompt source_story drifted")
    prompts = fixture.get("prompts")
    if fixture.get("prompt_count") != 100 or not isinstance(prompts, list) or len(prompts) != 100:
        raise ValidationError("expected exactly 100 reference prompts")
    expected_ids = [f"llm-router-ref-{index:03d}" for index in range(1, 101)]
    actual_ids = [prompt.get("prompt_id") for prompt in prompts]
    if actual_ids != expected_ids:
        raise ValidationError("reference prompt IDs must be sorted llm-router-ref-001..100")
    counts: dict[str, int] = {}
    for item in prompts:
        Prompt.model_validate(item)
        task = item["task"]
        counts[task] = counts.get(task, 0) + 1
        _reject_forbidden_text(json.dumps(item, ensure_ascii=False), "reference prompt")
    if counts != TASK_COUNTS:
        raise ValidationError("reference prompt task distribution drifted")
    return fixture


def validate_parity_report(report_path: Path, reference_prompts_path: Path) -> None:
    report = _load_json(report_path)
    computed = compute_behavior_parity_report(reference_prompts_path)
    if report.get("example_only") is not True:
        raise ValidationError("parity report must be example_only=true")
    if str(report.get("evidence_type", "")).lower() != "offline deterministic parity":
        raise ValidationError("parity report must be offline deterministic parity evidence")
    if report.get("prompt_count") != 100:
        raise ValidationError("parity report prompt_count drifted")
    if report.get("threshold") != PARITY_THRESHOLD:
        raise ValidationError("parity threshold drifted")
    if report.get("minimum_similarity", 0) < PARITY_THRESHOLD or report.get("passed") is not True:
        raise ValidationError("below behavior parity threshold")
    deviations = report.get("deviations")
    if not isinstance(deviations, list) or len(deviations) != 100:
        raise ValidationError("parity report must include 100 deviations")
    expected_ids = [f"llm-router-ref-{index:03d}" for index in range(1, 101)]
    actual_ids = [item.get("prompt_id") for item in deviations]
    if actual_ids != expected_ids:
        raise ValidationError("parity report deviation order drifted")
    primary_summaries = {item.get("primary_summary") for item in deviations}
    fallback_summaries = {item.get("fallback_summary") for item in deviations}
    if len(primary_summaries) <= 90 or len(fallback_summaries) <= 90:
        raise ValidationError("global canned-output parity detected")
    for item in deviations:
        if item.get("similarity", 0) < PARITY_THRESHOLD:
            raise ValidationError("below behavior parity threshold")
        _reject_forbidden_text(json.dumps(item, ensure_ascii=False), "parity deviation")
    _reject_forbidden_text(json.dumps(report, ensure_ascii=False), "parity report")
    if report != computed:
        raise ValidationError("committed parity report does not match computed report")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing required file: {path}") from exc
    if not isinstance(data, dict):
        raise ValidationError(f"expected JSON object: {path}")
    return data


def _reject_forbidden_text(text: str, location: str) -> None:
    match = FORBIDDEN_PATTERN.search(text)
    if match:
        raise ValidationError(f"{location} contains forbidden material: {match.group(0)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate M3.8 LLM router contract assets.")
    parser.add_argument("--reference-prompts", type=Path, default=DEFAULT_REFERENCE_PROMPTS)
    parser.add_argument("--parity-report", type=Path, default=DEFAULT_PARITY_REPORT)
    args = parser.parse_args()

    try:
        validate_registry()
        validate_reference_prompts(args.reference_prompts)
        validate_parity_report(args.parity_report, args.reference_prompts)
    except ValidationError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    sys.stdout.write("llm router contract OK\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
