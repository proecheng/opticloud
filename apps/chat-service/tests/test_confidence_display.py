from __future__ import annotations

import json

import pytest
from chat_service.confidence_display import generate_confidence_display_preview
from chat_service.schemas import CriticCheck, CriticPreview
from pydantic import ValidationError


def _critic_preview(
    *,
    status: str = "validated",
    confidence: float = 0.86,
    threshold: float = 0.6,
    reasoning: str = "Critic validated schema, safety, and business-logic consistency.",
) -> CriticPreview:
    source = (
        "llm_critic_internal_beta" if status == "validated" else "heuristic_critic_internal_beta"
    )
    return CriticPreview(
        status=status,
        source=source,
        task_type="lp",
        confidence=confidence,
        reasoning=reasoning,
        checks={
            "schema": CriticCheck(passed=True, message="schema ok", field_path="artifact"),
            "safety": CriticCheck(passed=True, message="safety ok", field_path="artifact.code"),
            "business_logic": CriticCheck(
                passed=True,
                message="business ok",
                field_path="artifact.entrypoint",
            ),
        },
        validation_errors=[],
        supported_task_types=["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"],
        calibration_threshold=threshold,
        threshold_source="apps/critic-service/config/critic-calibration.json",
    )


@pytest.mark.parametrize(
    ("confidence", "expected_tier", "label_zh", "label_en"),
    [
        (0.95, "high", "高置信", "High confidence"),
        (0.85, "high", "高置信", "High confidence"),
        (0.8499, "mid", "中置信", "Medium confidence"),
        (0.6, "mid", "中置信", "Medium confidence"),
        (0.5999, "low", "低置信请人工 review", "Low confidence; human review recommended"),
    ],
)
def test_confidence_display_tier_boundaries(
    confidence: float,
    expected_tier: str,
    label_zh: str,
    label_en: str,
) -> None:
    result = generate_confidence_display_preview(
        critic_preview=_critic_preview(confidence=confidence),
        human_review_escalated=confidence < 0.6,
    )

    preview = result.preview
    assert preview.score == confidence
    assert preview.tier == expected_tier
    assert preview.label_zh == label_zh
    assert preview.label_en == label_en
    assert preview.aria_label == f"Confidence: {confidence:.2f} - {label_en}"
    assert preview.calibration_threshold == 0.6
    assert preview.human_review_escalated is (confidence < 0.6)
    assert preview.validation_errors == []


def test_low_confidence_display_uses_human_review_state_without_rewriting_contract() -> None:
    preview = generate_confidence_display_preview(
        critic_preview=_critic_preview(status="skipped", confidence=0.0),
        human_review_escalated=True,
    ).preview

    assert preview.tier == "low"
    assert preview.human_review_escalated is True
    assert "已转人工复核" in preview.reasoning_zh
    assert "routed for human review" in preview.reasoning_en


def test_confidence_display_sanitizes_raw_or_runtime_leak_fragments() -> None:
    preview = generate_confidence_display_preview(
        critic_preview=_critic_preview(
            confidence=0.4,
            reasoning=(
                "provider_response raw_user_message prompt generated code "
                "sandbox_result execution_log traceback C:\\secret\\path sk-test-token"
            ),
        ),
        human_review_escalated=True,
    ).preview

    serialized = json.dumps(preview.model_dump(mode="json"), ensure_ascii=False)
    for fragment in [
        "provider_response",
        "raw_user_message",
        "prompt",
        "generated code",
        "sandbox_result",
        "execution_log",
        "traceback",
        "C:\\secret\\path",
        "sk-test-token",
    ]:
        assert fragment not in serialized


def test_confidence_display_schema_rejects_contract_drift() -> None:
    preview = generate_confidence_display_preview(
        critic_preview=_critic_preview(confidence=0.86),
        human_review_escalated=False,
    ).preview

    payload = preview.model_dump(mode="json")
    payload["tier"] = "low"
    with pytest.raises(ValidationError):
        type(preview).model_validate(payload)
