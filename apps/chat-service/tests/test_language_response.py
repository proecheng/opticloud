from __future__ import annotations

import json

import pytest
from chat_service.language_response import (
    build_language_response_prompt,
    generate_language_response_with_llm,
    heuristic_language_preview,
    parse_language_response_completion,
)
from chat_service.router_preview import classify_message
from chat_service.schemas import CoderPreview, FormulatorPreview, LanguagePreview
from opticloud_shared.llm_router import Completion, CompletionUsage, LLMRouterError


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


def test_build_language_response_prompt_uses_m3_8_contract_without_payload_leak() -> None:
    message = "请 solve route optimization for 北京 deliveries"
    router_preview = classify_message(message)

    prompt = build_language_response_prompt(
        message=message,
        locale="mixed",
        prompt_id="msg_test",
        message_excerpt="请 solve route optimization for 北京...",
        router_preview=router_preview,
        formulator_preview=_formulator_preview("vrptw"),
        coder_preview=_coder_preview("vrptw"),
    )

    assert prompt.prompt_id == "msg_test"
    assert prompt.task == "mixed_language_summary"
    assert prompt.locale == "mixed"
    assert [part.role for part in prompt.messages] == ["system", "user"]
    assert prompt.response_schema is not None
    assert prompt.response_schema["required"] == ["response_locale", "summary"]
    assert prompt.metadata == {
        "response_locale": "mixed",
        "router_task_type": "vrptw",
        "formulator_status": "needs_clarification",
        "coder_status": "needs_clarification",
    }
    assert message not in prompt.messages[1].content
    assert "variables" not in prompt.messages[1].content
    assert "objective" not in prompt.messages[1].content
    assert "artifact" not in prompt.messages[1].content
    assert "def " not in prompt.messages[1].content


def test_parse_language_response_completion_accepts_safe_mixed_json_summary() -> None:
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
    assert preview.source == "llm_language_internal_beta"
    assert preview.response_locale == "mixed"
    assert "route" in preview.summary
    assert "已识别" in preview.summary
    assert preview.disclaimer.bilingual == (
        "AI 生成内容仅供参考，请在提交求解前核对。 / "
        "AI-generated content is for reference only. Review it before submitting a solve."
    )
    assert preview.supported_locales == ["zh-CN", "en-US", "mixed"]


@pytest.mark.parametrize(
    "payload",
    [
        {"response_locale": "zh-CN", "summary": "Detected a route request."},
        {"response_locale": "mixed", "summary": "```json\n{}\n```"},
        {"response_locale": "mixed", "summary": "deterministic_digest=abc123"},
        {"response_locale": "mixed", "summary": "请 solve route optimization for 北京 deliveries"},
        {"response_locale": "mixed", "summary": "请 solve route optimization for 北京..."},
        {"response_locale": "mixed", "summary": "provider raw_response leaked"},
        {"response_locale": "mixed", "summary": "valid", "raw_response": {}},
        {"response_locale": "mixed", "summary": "valid", "debug": "provider payload"},
        {"response_locale": "mixed", "summary": "valid", "confidence": 1.2},
    ],
)
def test_parse_language_response_completion_rejects_unsafe_or_mismatched_output(
    payload: dict[str, object],
) -> None:
    preview = parse_language_response_completion(
        json.dumps(payload, ensure_ascii=False),
        locale="mixed",
        original_message="请 solve route optimization for 北京 deliveries",
        message_excerpt="请 solve route optimization for 北京...",
    )

    assert preview is None


def test_language_preview_schema_rejects_supported_locale_order_drift() -> None:
    with pytest.raises(ValueError):
        LanguagePreview(
            status="fallback",
            source="heuristic_language_internal_beta",
            response_locale="zh-CN",
            summary="已识别为 VRPTW 请求，并生成 internal beta 预览。",
            disclaimer={
                "zh": "AI 生成内容仅供参考，请在提交求解前核对。",
                "en": (
                    "AI-generated content is for reference only. Review it before "
                    "submitting a solve."
                ),
                "bilingual": (
                    "AI 生成内容仅供参考，请在提交求解前核对。 / "
                    "AI-generated content is for reference only. Review it before "
                    "submitting a solve."
                ),
            },
            validation_errors=[],
            supported_locales=["mixed", "zh-CN", "en-US"],
        )


def test_heuristic_language_preview_is_same_language_and_bilingual_disclaimer() -> None:
    zh = heuristic_language_preview(
        "zh-CN",
        router_preview=classify_message("求最短路径，把车辆路线排出来"),
        formulator_preview=_formulator_preview("vrptw"),
        coder_preview=_coder_preview("vrptw"),
    )
    en = heuristic_language_preview(
        "en-US",
        router_preview=classify_message("schedule the shifts for tomorrow"),
        formulator_preview=_formulator_preview("schedule"),
        coder_preview=_coder_preview("schedule"),
    )
    mixed = heuristic_language_preview(
        "mixed",
        router_preview=classify_message("库存补货策略 for sku"),
        formulator_preview=_formulator_preview("inventory"),
        coder_preview=_coder_preview("inventory"),
    )

    assert zh.status == "fallback"
    assert zh.source == "heuristic_language_internal_beta"
    assert "已识别" in zh.summary
    assert "Detected" not in zh.summary
    assert en.summary.startswith("Detected")
    assert "已识别" not in en.summary
    assert "已识别" in mixed.summary
    assert "request" in mixed.summary
    assert zh.disclaimer == en.disclaimer == mixed.disclaimer


def test_generate_language_response_with_llm_turns_deterministic_text_into_fallback() -> None:
    result = generate_language_response_with_llm(
        message="请 solve route optimization for 北京 deliveries",
        locale="mixed",
        prompt_id="msg_test",
        message_excerpt="请 solve route optimization for 北京...",
        router_preview=classify_message("请 solve route optimization for 北京 deliveries"),
        formulator_preview=_formulator_preview("vrptw"),
        coder_preview=_coder_preview("vrptw"),
        completion_func=lambda _prompt, model: _completion(
            "mixed language summary 中文 English concise business result "
            "deterministic_digest=abc123 provider_variant=deepseek"
        ),
    )

    assert result.language_invoked is True
    assert result.provider_request_sent is False
    assert result.preview.status == "fallback"
    assert result.preview.source == "heuristic_language_internal_beta"
    assert "deterministic_digest" not in result.preview.summary


@pytest.mark.parametrize("finish_reason", ["length", "content_filter", "error"])
def test_generate_language_response_with_llm_falls_back_on_non_stop_finish_reason(
    finish_reason: str,
) -> None:
    result = generate_language_response_with_llm(
        message="linear programming objective with constraints",
        locale="en-US",
        prompt_id="msg_test",
        message_excerpt="linear programming objective with...",
        router_preview=classify_message("linear programming objective with constraints"),
        formulator_preview=_formulator_preview("lp"),
        coder_preview=_coder_preview("lp"),
        completion_func=lambda _prompt, model: _completion(
            json.dumps({"response_locale": "en-US", "summary": "Detected an LP request."}),
            finish_reason=finish_reason,
        ),
    )

    assert result.language_invoked is True
    assert result.preview.status == "fallback"
    assert result.preview.response_locale == "en-US"


def test_generate_language_response_with_llm_falls_back_after_router_error() -> None:
    def fail(_prompt: object, model: str) -> Completion:
        raise LLMRouterError("offline language completion failed")

    result = generate_language_response_with_llm(
        message="求最短路径，把车辆路线排出来",
        locale="zh-CN",
        prompt_id="msg_test",
        message_excerpt="求最短路径，把车辆路线排...",
        router_preview=classify_message("求最短路径，把车辆路线排出来"),
        formulator_preview=_formulator_preview("vrptw"),
        coder_preview=_coder_preview("vrptw"),
        completion_func=fail,
    )

    assert result.language_invoked is True
    assert result.provider_request_sent is False
    assert result.preview.status == "fallback"
    assert result.preview.response_locale == "zh-CN"
