from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from chat_service.schemas import (
    CriticPreview,
    HumanReviewNotice,
    HumanReviewPreview,
    HumanReviewReasonCode,
)

HUMAN_REVIEW_QUEUE: Literal["events.critic"] = "events.critic"
HUMAN_REVIEW_EVENT_TYPE: Literal["critic.review.escalated"] = "critic.review.escalated"


@dataclass(frozen=True)
class HumanReviewRouteResult:
    preview: HumanReviewPreview


def generate_human_review_preview(
    *,
    message_id: str,
    critic_preview: CriticPreview,
) -> HumanReviewRouteResult:
    escalated = critic_preview.confidence < critic_preview.calibration_threshold
    reason_code = _reason_code(critic_preview, escalated=escalated)
    preview = HumanReviewPreview(
        escalated=escalated,
        source=(
            "critic_threshold_internal_beta"
            if escalated
            else "heuristic_human_review_internal_beta"
        ),
        queue=HUMAN_REVIEW_QUEUE,
        event_type=HUMAN_REVIEW_EVENT_TYPE,
        review_id=_review_id(message_id=message_id, critic_preview=critic_preview),
        reason_code=reason_code,
        critic_confidence=critic_preview.confidence,
        calibration_threshold=critic_preview.calibration_threshold,
        threshold_source=critic_preview.threshold_source,
        user_notice=_user_notice() if escalated else None,
        validation_errors=[],
    )
    return HumanReviewRouteResult(preview=preview)


def _reason_code(
    critic_preview: CriticPreview,
    *,
    escalated: bool,
) -> HumanReviewReasonCode:
    if not escalated:
        return "not_escalated"
    if critic_preview.status == "validated":
        return "critic_confidence_below_threshold"
    if critic_preview.status == "skipped":
        return "critic_skipped_below_threshold"
    return "critic_not_validated_below_threshold"


def _review_id(*, message_id: str, critic_preview: CriticPreview) -> str:
    digest_input = "\n".join(
        [
            message_id,
            critic_preview.task_type,
            critic_preview.status,
            f"{critic_preview.confidence:.12g}",
            f"{critic_preview.calibration_threshold:.12g}",
            critic_preview.threshold_source,
        ]
    )
    digest = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
    return f"hrv_{digest[:24]}"


def _user_notice() -> HumanReviewNotice:
    return HumanReviewNotice(
        zh="AI 不确定，已转人工复核。",
        en="AI is uncertain; this has been routed for human review.",
    )
