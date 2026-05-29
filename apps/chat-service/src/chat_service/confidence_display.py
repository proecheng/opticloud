from __future__ import annotations

import re
from dataclasses import dataclass

from chat_service.schemas import (
    CriticConfidenceDisplayPreview,
    CriticConfidenceDisplayTier,
    CriticPreview,
)

_TIER_LABELS: dict[CriticConfidenceDisplayTier, tuple[str, str]] = {
    "high": ("高置信", "High confidence"),
    "mid": ("中置信", "Medium confidence"),
    "low": ("低置信请人工 review", "Low confidence; human review recommended"),
}
_LEAK_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]+|api[_-]?key|bearer\s+[A-Za-z0-9._-]+|authorization|"
    r"cookie|password|token|raw[_ -]?(?:user[_ -]?)?message|raw[_ -]?response|"
    r"raw[_ -]?request|provider[_ -]?(?:request|response|payload)?|prompt|"
    r"generated code|sandbox[_ -]?(?:result|output)?|execution[_ -]?log|traceback|"
    r"[A-Za-z]:\\[^\s]+|/(?:tmp|var|home|Users|workspace)/[^\s]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ConfidenceDisplayRouteResult:
    preview: CriticConfidenceDisplayPreview


def generate_confidence_display_preview(
    *,
    critic_preview: CriticPreview,
    human_review_escalated: bool,
) -> ConfidenceDisplayRouteResult:
    score = critic_preview.confidence
    tier = _tier_from_score(score)
    label_zh, label_en = _TIER_LABELS[tier]
    preview = CriticConfidenceDisplayPreview(
        score=score,
        tier=tier,
        label_zh=label_zh,
        label_en=label_en,
        reasoning_zh=_reasoning_zh(
            tier=tier,
            critic_status=critic_preview.status,
            human_review_escalated=human_review_escalated,
        ),
        reasoning_en=_reasoning_en(
            tier=tier,
            critic_reasoning=critic_preview.reasoning,
            human_review_escalated=human_review_escalated,
        ),
        aria_label=f"Confidence: {score:.2f} - {label_en}",
        calibration_threshold=critic_preview.calibration_threshold,
        human_review_escalated=human_review_escalated,
        validation_errors=[],
    )
    return ConfidenceDisplayRouteResult(preview=preview)


def _tier_from_score(score: float) -> CriticConfidenceDisplayTier:
    if score >= 0.85:
        return "high"
    if score >= 0.6:
        return "mid"
    return "low"


def _reasoning_zh(
    *,
    tier: CriticConfidenceDisplayTier,
    critic_status: str,
    human_review_escalated: bool,
) -> str:
    if tier == "high" and critic_status == "validated":
        return "Critic 已验证 schema、安全性和业务一致性。"
    if tier == "mid":
        return "Critic 置信度中等，建议提交前复核关键约束。"
    if human_review_escalated:
        return "Critic 置信度低，已转人工复核。"
    return "Critic 置信度低，请人工复核。"


def _reasoning_en(
    *,
    tier: CriticConfidenceDisplayTier,
    critic_reasoning: str,
    human_review_escalated: bool,
) -> str:
    if tier == "low":
        if human_review_escalated:
            return "Critic confidence is low; this has been routed for human review."
        return "Critic confidence is low; human review is recommended."
    if tier == "mid":
        return "Critic confidence is medium; review key constraints before submitting."
    sanitized = _sanitize_reasoning(critic_reasoning)
    return sanitized or "Critic validated schema, safety, and business consistency."


def _sanitize_reasoning(reasoning: str) -> str:
    normalized = " ".join(reasoning.split())
    if not normalized or _LEAK_PATTERN.search(normalized):
        return "Critic validated schema, safety, and business consistency."
    return normalized[:240]
