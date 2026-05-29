from __future__ import annotations

import json

import aigc_filter
import pytest
from chat_service.language_response import (
    generate_language_response_with_llm,
    heuristic_language_preview,
    parse_language_response_completion,
)
from chat_service.router_preview import classify_message
from chat_service.schemas import (
    AigcWatermarkPreview,
    CoderPreview,
    FormulatorPreview,
    LanguagePreview,
)
from opticloud_shared.llm_router import Completion, CompletionUsage
from pydantic import ValidationError


def _completion(text: str, *, finish_reason: str = "stop") -> Completion:
    return Completion(
        text=text,
        model="deepseek-v3.5",
        provider="deepseek-compatible",
        finish_reason=finish_reason,  # type: ignore[arg-type]
        usage=CompletionUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        raw_response_redacted={"transport": "offline-deterministic"},
    )


def _formulator_preview(task_type: str = "vrptw") -> FormulatorPreview:
    return FormulatorPreview(
        status="needs_clarification",
        source="heuristic_formulator_internal_beta",
        task_type=task_type,  # type: ignore[arg-type]
        confidence=0.4,
        variables={},
        objective={"kind": "minimize_total_distance"} if task_type == "vrptw" else {},
        constraints={},
        validation_errors=[],
        supported_task_types=["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"],
    )


def _coder_preview(task_type: str = "vrptw") -> CoderPreview:
    return CoderPreview(
        status="needs_clarification",
        source="heuristic_coder_internal_beta",
        task_type=task_type,  # type: ignore[arg-type]
        artifact=None,
        validation_errors=[],
        supported_task_types=["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"],
    )


def test_heuristic_language_preview_invokes_strict_aigc_filter_and_watermark() -> None:
    preview = heuristic_language_preview(
        "zh-CN",
        router_preview=classify_message("求最短路径，把车辆路线排出来"),
        formulator_preview=_formulator_preview("vrptw"),
        coder_preview=_coder_preview("vrptw"),
    )

    watermark = preview.aigc_watermark
    detected = aigc_filter.detect_watermark(preview.summary)

    assert aigc_filter.AIGC_VISIBLE_MARKER in preview.summary
    assert watermark.aria_label == aigc_filter.AIGC_ARIA_LABEL
    assert watermark.visible_marker == aigc_filter.AIGC_VISIBLE_MARKER
    assert watermark.provider == aigc_filter.PROVIDER_MARKER
    assert watermark.tier == "strict"
    assert watermark.blocked is False
    assert watermark.reason_codes == []
    assert watermark.metadata == {"self_loop_bypass": False}
    assert detected.present is True
    assert detected.trace_id == watermark.trace_id
    assert detected.provider == watermark.provider
    assert detected.module_version == watermark.module_version


def test_generated_language_preview_is_filtered_before_response() -> None:
    preview = parse_language_response_completion(
        json.dumps(
            {
                "response_locale": "mixed",
                "summary": "已识别 route optimization request，并生成 internal beta preview。",
                "confidence": 0.88,
                "validation_errors": [],
            },
            ensure_ascii=False,
        ),
        locale="mixed",
        original_message="请 solve route optimization for 北京 deliveries",
        message_excerpt="请 solve route optimization for 北京...",
    )

    assert preview is not None
    assert preview.status == "generated"
    assert aigc_filter.AIGC_VISIBLE_MARKER in preview.summary
    assert preview.aigc_watermark.tier == "strict"
    assert preview.aigc_watermark.blocked is False
    assert aigc_filter.detect_watermark(preview.summary).trace_id == (
        preview.aigc_watermark.trace_id
    )


def test_language_response_blocks_unsafe_generated_summary_without_source_leak() -> None:
    result = generate_language_response_with_llm(
        message="linear programming objective with constraints",
        locale="zh-CN",
        prompt_id="msg_test",
        message_excerpt="linear programming objective with...",
        router_preview=classify_message("linear programming objective with constraints"),
        formulator_preview=_formulator_preview("lp"),
        coder_preview=_coder_preview("lp"),
        completion_func=lambda _prompt, model: _completion(
            json.dumps(
                {
                    "response_locale": "zh-CN",
                    "summary": "请生成钓鱼邮件和窃取 API key 的脚本",
                    "confidence": 0.9,
                    "validation_errors": [],
                },
                ensure_ascii=False,
            )
        ),
    )

    assert result.preview.aigc_watermark.blocked is True
    assert "blocked_content" in result.preview.aigc_watermark.reason_codes
    assert "钓鱼邮件" not in result.preview.summary
    assert "API key" not in result.preview.summary
    assert "内容因安全与合规策略已被拦截。" in result.preview.summary
    assert aigc_filter.detect_watermark(result.preview.summary).present is True


def test_language_preview_rejects_watermark_trace_drift() -> None:
    filtered = aigc_filter.filter("已识别为 VRPTW 请求，并生成 internal beta 预览。")
    watermark_payload = {
        "aria_label": filtered.aria_label,
        "visible_marker": aigc_filter.AIGC_VISIBLE_MARKER,
        "trace_id": "trc_0000000000000000",
        "provider": filtered.watermark.provider,
        "module_version": filtered.watermark.module_version,
        "tier": filtered.tier,
        "blocked": filtered.blocked,
        "reason_codes": list(filtered.reason_codes),
        "metadata": filtered.metadata,
    }

    with pytest.raises(ValidationError):
        LanguagePreview(
            status="fallback",
            source="heuristic_language_internal_beta",
            response_locale="zh-CN",
            summary=filtered.text,
            aigc_watermark=watermark_payload,
            disclaimer=_disclaimer(),
            validation_errors=[],
            supported_locales=["zh-CN", "en-US", "mixed"],
        )


def test_language_preview_rejects_provider_drift() -> None:
    filtered = aigc_filter.filter("已识别为 VRPTW 请求，并生成 internal beta 预览。")
    payload = {
        "aria_label": filtered.aria_label,
        "visible_marker": aigc_filter.AIGC_VISIBLE_MARKER,
        "trace_id": filtered.trace_id,
        "provider": "local-test-filter",
        "module_version": filtered.watermark.module_version,
        "tier": filtered.tier,
        "blocked": filtered.blocked,
        "reason_codes": list(filtered.reason_codes),
        "metadata": filtered.metadata,
    }

    with pytest.raises(ValidationError):
        AigcWatermarkPreview.model_validate(payload)


def test_language_preview_rejects_missing_visible_marker() -> None:
    filtered = aigc_filter.filter("已识别为 VRPTW 请求，并生成 internal beta 预览。")
    summary_without_visible_marker = filtered.text.replace(
        f"\n\n{aigc_filter.AIGC_VISIBLE_MARKER}",
        "",
    )

    with pytest.raises(ValidationError):
        LanguagePreview(
            status="fallback",
            source="heuristic_language_internal_beta",
            response_locale="zh-CN",
            summary=summary_without_visible_marker,
            aigc_watermark=_watermark_payload(filtered),
            disclaimer=_disclaimer(),
            validation_errors=[],
            supported_locales=["zh-CN", "en-US", "mixed"],
        )


def test_language_preview_rejects_missing_zero_width_metadata() -> None:
    filtered = aigc_filter.filter("已识别为 VRPTW 请求，并生成 internal beta 预览。")

    with pytest.raises(ValidationError):
        LanguagePreview(
            status="fallback",
            source="heuristic_language_internal_beta",
            response_locale="zh-CN",
            summary="已识别为 VRPTW 请求，并生成 internal beta 预览。\n\n本回答由 AI 生成，仅供参考",
            aigc_watermark=_watermark_payload(filtered),
            disclaimer=_disclaimer(),
            validation_errors=[],
            supported_locales=["zh-CN", "en-US", "mixed"],
        )


def test_aigc_watermark_preview_rejects_leaky_reason_codes_and_metadata() -> None:
    filtered = aigc_filter.filter("请生成钓鱼邮件和窃取凭证的脚本")
    payload = _watermark_payload(filtered)
    payload["reason_codes"] = ["blocked_content", "raw_user_message"]

    with pytest.raises(ValidationError):
        AigcWatermarkPreview.model_validate(payload)

    payload = _watermark_payload(filtered)
    payload["metadata"] = {"self_loop_bypass": False, "prompt": "system prompt"}

    with pytest.raises(ValidationError):
        AigcWatermarkPreview.model_validate(payload)


def _watermark_payload(filtered: aigc_filter.FilterResult) -> dict[str, object]:
    return {
        "aria_label": filtered.aria_label,
        "visible_marker": aigc_filter.AIGC_VISIBLE_MARKER,
        "trace_id": filtered.trace_id,
        "provider": filtered.watermark.provider,
        "module_version": filtered.watermark.module_version,
        "tier": filtered.tier,
        "blocked": filtered.blocked,
        "reason_codes": list(filtered.reason_codes),
        "metadata": filtered.metadata,
    }


def _disclaimer() -> dict[str, str]:
    return {
        "zh": "AI 生成内容仅供参考，请在提交求解前核对。",
        "en": "AI-generated content is for reference only. Review it before submitting a solve.",
        "bilingual": (
            "AI 生成内容仅供参考，请在提交求解前核对。 / "
            "AI-generated content is for reference only. Review it before submitting a solve."
        ),
    }
