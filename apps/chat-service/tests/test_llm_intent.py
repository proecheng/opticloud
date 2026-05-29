from __future__ import annotations

import pytest
from chat_service.llm_intent import (
    build_router_prompt,
    parse_router_completion,
    route_intent_with_llm,
)
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


def test_build_router_prompt_uses_m3_8_router_intent_contract() -> None:
    prompt = build_router_prompt(
        message="求最短路径，把车辆路线排出来",
        locale="zh-CN",
        prompt_id="msg_test",
    )

    assert prompt.prompt_id == "msg_test"
    assert prompt.task == "router_intent"
    assert prompt.locale == "zh-CN"
    assert [message.role for message in prompt.messages] == ["system", "user"]
    assert prompt.response_schema is not None
    assert prompt.response_schema["required"] == ["task_type", "confidence", "reasoning"]
    assert prompt.response_schema["properties"]["task_type"]["enum"] == [
        "lp",
        "vrptw",
        "prediction",
        "schedule",
        "inventory",
        "unknown",
    ]
    assert prompt.metadata == {}


def test_parse_router_completion_accepts_json_object() -> None:
    preview = parse_router_completion(
        '{"task_type":"inventory","confidence":0.88,"reasoning":"matched stock pattern"}'
    )

    assert preview.task_type == "inventory"
    assert preview.confidence == 0.88
    assert preview.reasoning == "matched stock pattern"
    assert preview.source == "llm_router_internal_beta"


def test_parse_router_completion_accepts_m3_8_deterministic_text() -> None:
    preview = parse_router_completion(
        "router decision task_type=vrptw confidence=0.92 reasoning="
        "route_keywords deterministic_digest=abc123"
    )

    assert preview.task_type == "vrptw"
    assert preview.confidence == 0.92
    assert preview.source == "llm_router_internal_beta"
    assert "deterministic_digest" not in preview.reasoning


@pytest.mark.parametrize(
    "text",
    [
        "{}",
        '{"task_type":"bad","confidence":0.9,"reasoning":"x"}',
        '{"task_type":"vrptw","confidence":1.5,"reasoning":"x"}',
        '{"task_type":"vrptw","confidence":0.9,"reasoning":"求最短路径，把车辆路线排出来"}',
    ],
)
def test_parse_router_completion_rejects_malformed_or_unsafe_output(text: str) -> None:
    assert parse_router_completion(text, original_message="求最短路径，把车辆路线排出来") is None


def test_route_intent_with_llm_uses_completion_and_reports_invocation() -> None:
    result = route_intent_with_llm(
        message="求最短路径，把车辆路线排出来",
        locale="zh-CN",
        prompt_id="msg_test",
        completion_func=lambda _prompt, model: _completion(
            '{"task_type":"vrptw","confidence":0.92,"reasoning":"matched routing intent"}'
        ),
    )

    assert result.preview.task_type == "vrptw"
    assert result.preview.confidence == 0.92
    assert result.preview.source == "llm_router_internal_beta"
    assert result.llm_invoked is True
    assert result.provider_request_sent is False


def test_route_intent_with_llm_falls_back_on_router_error_after_invocation() -> None:
    def fail(_prompt: object, model: str) -> Completion:
        raise LLMRouterError("offline router failed")

    result = route_intent_with_llm(
        message="库存补货策略 for sku",
        locale="mixed",
        prompt_id="msg_test",
        completion_func=fail,
    )

    assert result.preview.task_type == "inventory"
    assert result.preview.source == "heuristic_internal_beta"
    assert result.llm_invoked is True
    assert result.provider_request_sent is False


def test_route_intent_with_llm_unknown_model_falls_back_before_invocation() -> None:
    called = False

    def complete_unexpected(_prompt: object, model: str) -> Completion:
        nonlocal called
        called = True
        return _completion("{}")

    result = route_intent_with_llm(
        message="linear programming objective with constraints",
        locale="en-US",
        prompt_id="msg_test",
        model_alias="unsupported-model",
        completion_func=complete_unexpected,
    )

    assert called is False
    assert result.preview.task_type == "lp"
    assert result.preview.source == "heuristic_internal_beta"
    assert result.llm_invoked is False


def test_route_intent_with_llm_prompt_validation_failure_falls_back_before_invocation() -> None:
    called = False

    def complete_unexpected(_prompt: object, model: str) -> Completion:
        nonlocal called
        called = True
        return _completion("{}")

    result = route_intent_with_llm(
        message="请做库存优化，api_key=sk-live-secret",
        locale="mixed",
        prompt_id="msg_test",
        completion_func=complete_unexpected,
    )

    assert called is False
    assert result.preview.task_type == "inventory"
    assert result.preview.source == "heuristic_internal_beta"
    assert result.llm_invoked is False


def test_route_intent_with_llm_conflict_guardrail_preserves_heuristic() -> None:
    result = route_intent_with_llm(
        message="请预测下个月 SKU 销量",
        locale="mixed",
        prompt_id="msg_test",
        completion_func=lambda _prompt, model: _completion(
            "router decision task_type=vrptw confidence=0.92 reasoning=fixture"
        ),
    )

    assert result.preview.task_type == "prediction"
    assert result.preview.source == "heuristic_internal_beta"
    assert result.llm_invoked is True
