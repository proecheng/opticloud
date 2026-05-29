from __future__ import annotations

import aigc_filter

from chat_service.schemas import AigcWatermarkPreview


def apply_aigc_filter_to_summary(summary: str) -> tuple[str, AigcWatermarkPreview]:
    filtered = aigc_filter.filter(summary, tier="strict")
    preview = AigcWatermarkPreview(
        aria_label=filtered.aria_label,
        visible_marker=aigc_filter.AIGC_VISIBLE_MARKER,
        trace_id=filtered.trace_id,
        provider=filtered.watermark.provider,
        module_version=filtered.watermark.module_version,
        tier=filtered.tier,
        blocked=filtered.blocked,
        reason_codes=list(filtered.reason_codes),
        metadata=filtered.metadata,
    )
    return filtered.text, preview
