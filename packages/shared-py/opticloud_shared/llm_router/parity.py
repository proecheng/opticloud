"""Deterministic behavior parity utilities for Story M3.8."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from opticloud_shared.llm_router.registry import default_model_registry
from opticloud_shared.llm_router.router import build_default_router
from opticloud_shared.llm_router.schemas import Prompt

PARITY_THRESHOLD = 0.85


def token_vector(text: str) -> Counter[str]:
    """Convert text into a deterministic token vector."""
    normalized = []
    current = []
    for char in text.lower():
        if char.isalnum() or "\u4e00" <= char <= "\u9fff":
            current.append(char)
        elif current:
            normalized.append("".join(current))
            current = []
    if current:
        normalized.append("".join(current))
    return Counter(normalized)


def cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    """Return cosine similarity for two sparse token vectors."""
    if not left or not right:
        return 0.0
    shared = set(left) & set(right)
    dot = sum(left[token] * right[token] for token in shared)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def compute_behavior_parity_report(reference_prompts_path: Path | str) -> dict[str, Any]:
    """Run deterministic offline parity over the committed reference prompts."""
    path = Path(reference_prompts_path)
    fixture = json.loads(path.read_text(encoding="utf-8"))
    prompts = [Prompt.model_validate(item) for item in fixture["prompts"]]
    router = build_default_router()
    registry = default_model_registry()
    primary_alias = "deepseek-v3.5"
    fallback_alias = "qwen-max"
    deviations: list[dict[str, Any]] = []
    similarities: list[float] = []

    for prompt in prompts:
        primary = router.complete(prompt, primary_alias)
        fallback = router.complete(prompt, fallback_alias)
        similarity = cosine_similarity(token_vector(primary.text), token_vector(fallback.text))
        rounded_similarity = round(similarity, 6)
        similarities.append(rounded_similarity)
        deviations.append(
            {
                "prompt_id": prompt.prompt_id,
                "task": prompt.task,
                "similarity": rounded_similarity,
                "primary_summary": _redacted_summary(primary.text, prompt.prompt_id),
                "fallback_summary": _redacted_summary(fallback.text, prompt.prompt_id),
            }
        )

    minimum = min(similarities)
    average = round(sum(similarities) / len(similarities), 6)
    maximum = max(similarities)
    return {
        "report_version": "llm_router_behavior_parity_v1",
        "source_story": "M3.8",
        "example_only": True,
        "evidence_type": "offline deterministic parity",
        "reference_prompts_sha256": _sha256_file(path),
        "primary_alias": primary_alias,
        "primary_provider": registry[primary_alias].provider_id,
        "fallback_alias": fallback_alias,
        "fallback_provider": registry[fallback_alias].provider_id,
        "prompt_count": len(prompts),
        "threshold": PARITY_THRESHOLD,
        "minimum_similarity": minimum,
        "average_similarity": average,
        "maximum_similarity": maximum,
        "passed": all(value >= PARITY_THRESHOLD for value in similarities),
        "deviations": deviations,
    }


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _redacted_summary(text: str, prompt_id: str | None) -> str:
    tokens = list(token_vector(text).keys())
    prefix = prompt_id or "prompt-unknown"
    return f"{prefix} " + " ".join(tokens[:16])


__all__ = [
    "PARITY_THRESHOLD",
    "compute_behavior_parity_report",
    "cosine_similarity",
    "token_vector",
]
