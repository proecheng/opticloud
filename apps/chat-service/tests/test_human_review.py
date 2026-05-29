from __future__ import annotations

import json

import pytest
from chat_service.human_review import generate_human_review_preview
from chat_service.schemas import (
    CriticCheck,
    CriticPreview,
    HumanReviewNotice,
    HumanReviewPreview,
)
from pydantic import ValidationError


def _critic_preview(
    *,
    status: str = "validated",
    confidence: float = 0.59,
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
            "schema": CriticCheck(
                passed=status == "validated",
                message="schema check completed",
                field_path="artifact",
            ),
            "safety": CriticCheck(
                passed=status == "validated",
                message="safety check completed",
                field_path="artifact.code",
            ),
            "business_logic": CriticCheck(
                passed=status == "validated",
                message="business check completed",
                field_path="artifact.entrypoint",
            ),
        },
        validation_errors=[],
        supported_task_types=["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"],
        calibration_threshold=threshold,
        threshold_source="apps/critic-service/config/critic-calibration.json",
    )


def _valid_notice() -> HumanReviewNotice:
    return HumanReviewNotice(
        zh="AI 不确定，已转人工复核。",
        en="AI is uncertain; this has been routed for human review.",
    )


def _valid_human_review_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "escalated": True,
        "source": "critic_threshold_internal_beta",
        "queue": "events.critic",
        "event_type": "critic.review.escalated",
        "review_id": "hrv_0123456789abcdef01234567",
        "reason_code": "critic_confidence_below_threshold",
        "critic_confidence": 0.59,
        "calibration_threshold": 0.6,
        "threshold_source": "apps/critic-service/config/critic-calibration.json",
        "user_notice": {
            "zh": "AI 不确定，已转人工复核。",
            "en": "AI is uncertain; this has been routed for human review.",
        },
        "validation_errors": [],
    }
    payload.update(overrides)
    return payload


def test_low_confidence_below_threshold_escalates_with_contract_envelope() -> None:
    result = generate_human_review_preview(
        message_id="msg_abcdef1234567890abcdef12",
        critic_preview=_critic_preview(confidence=0.59, threshold=0.6),
    )

    preview = result.preview
    assert preview.escalated is True
    assert preview.source == "critic_threshold_internal_beta"
    assert preview.queue == "events.critic"
    assert preview.event_type == "critic.review.escalated"
    assert preview.reason_code == "critic_confidence_below_threshold"
    assert preview.critic_confidence == 0.59
    assert preview.calibration_threshold == 0.6
    assert preview.threshold_source == "apps/critic-service/config/critic-calibration.json"
    assert preview.user_notice == _valid_notice()
    assert preview.validation_errors == []
    assert preview.review_id.startswith("hrv_")
    assert len(preview.review_id) == 28


@pytest.mark.parametrize("confidence", [0.6, 0.61])
def test_confidence_equal_or_above_threshold_does_not_escalate(confidence: float) -> None:
    result = generate_human_review_preview(
        message_id="msg_abcdef1234567890abcdef12",
        critic_preview=_critic_preview(confidence=confidence, threshold=0.6),
    )

    preview = result.preview
    assert preview.escalated is False
    assert preview.source == "heuristic_human_review_internal_beta"
    assert preview.reason_code == "not_escalated"
    assert preview.queue == "events.critic"
    assert preview.event_type == "critic.review.escalated"
    assert preview.user_notice is None


@pytest.mark.parametrize(
    ("status", "reason_code"),
    [
        ("needs_clarification", "critic_not_validated_below_threshold"),
        ("skipped", "critic_skipped_below_threshold"),
    ],
)
def test_low_confidence_non_validated_critic_statuses_escalate(
    status: str,
    reason_code: str,
) -> None:
    result = generate_human_review_preview(
        message_id="msg_abcdef1234567890abcdef12",
        critic_preview=_critic_preview(status=status, confidence=0.4, threshold=0.6),
    )

    preview = result.preview
    assert preview.escalated is True
    assert preview.reason_code == reason_code
    assert preview.user_notice == _valid_notice()


def test_review_id_is_deterministic_bounded_and_not_raw_content_derived() -> None:
    critic_preview = _critic_preview(
        confidence=0.4,
        threshold=0.6,
        reasoning="raw_user_message=secret prompt; generated code print('secret')",
    )

    first = generate_human_review_preview(
        message_id="msg_abcdef1234567890abcdef12",
        critic_preview=critic_preview,
    ).preview
    second = generate_human_review_preview(
        message_id="msg_abcdef1234567890abcdef12",
        critic_preview=critic_preview,
    ).preview
    changed = generate_human_review_preview(
        message_id="msg_abcdef1234567890abcdef12",
        critic_preview=_critic_preview(confidence=0.5, threshold=0.6),
    ).preview

    assert first.review_id == second.review_id
    assert first.review_id != changed.review_id
    assert len(first.review_id) == 28
    assert "msg_abcdef1234567890abcdef12" not in first.review_id
    assert "secret" not in first.review_id
    assert "print" not in first.review_id


@pytest.mark.parametrize(
    "overrides",
    [
        {"queue": "events.human_review"},
        {"event_type": "human_review.escalated"},
        {"escalated": True, "critic_confidence": 0.6, "calibration_threshold": 0.6},
        {
            "escalated": False,
            "source": "heuristic_human_review_internal_beta",
            "reason_code": "not_escalated",
            "critic_confidence": 0.59,
            "calibration_threshold": 0.6,
            "user_notice": None,
        },
        {"escalated": True, "user_notice": None},
        {
            "escalated": False,
            "source": "heuristic_human_review_internal_beta",
            "reason_code": "not_escalated",
            "critic_confidence": 0.6,
            "calibration_threshold": 0.6,
        },
        {
            "user_notice": {
                "zh": "AI 不确定 / 转人工",
                "en": "AI is uncertain; routed for review.",
            }
        },
    ],
)
def test_human_review_schema_rejects_contract_drift(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        HumanReviewPreview.model_validate(_valid_human_review_payload(**overrides))


def test_human_review_preview_contains_no_raw_or_runtime_leak_fields() -> None:
    preview = generate_human_review_preview(
        message_id="msg_abcdef1234567890abcdef12",
        critic_preview=_critic_preview(confidence=0.0, threshold=0.6),
    ).preview

    serialized = json.dumps(preview.model_dump(mode="json"), ensure_ascii=False)
    blocked_fragments = [
        "provider",
        "raw_response",
        "raw_user_message",
        "prompt",
        "generated code",
        "sandbox_result",
        "execution_log",
        "redis",
        "notification",
        "outbox",
    ]
    for fragment in blocked_fragments:
        assert fragment not in serialized
