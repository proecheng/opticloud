from __future__ import annotations

import json

import pytest
from chat_service.formulator import (
    build_formulator_prompt,
    extract_formulation_with_llm,
    parse_formulator_completion,
)
from chat_service.router_preview import classify_message
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


def test_build_formulator_prompt_uses_m3_8_contract() -> None:
    router_preview = classify_message("linear programming objective with constraints")

    prompt = build_formulator_prompt(
        message="minimize 2 x plus 3 y subject to x plus y <= 10",
        locale="en-US",
        prompt_id="msg_test",
        router_preview=router_preview,
    )

    assert prompt.prompt_id == "msg_test"
    assert prompt.task == "formulator_extraction"
    assert prompt.locale == "en-US"
    assert [message.role for message in prompt.messages] == ["system", "user"]
    assert prompt.response_schema is not None
    assert prompt.response_schema["required"] == [
        "task_type",
        "confidence",
        "variables",
        "objective",
        "constraints",
    ]
    assert prompt.metadata == {"router_task_type": "lp"}


def test_parse_formulator_completion_accepts_lp_json_object() -> None:
    router_preview = classify_message("linear programming objective with constraints")

    preview = parse_formulator_completion(
        """
        {
          "task_type": "lp",
          "confidence": 0.84,
          "variables": {"decision_variables": ["x", "y"]},
          "objective": {"sense": "minimize", "coefficients": {"x": 2, "y": 3}},
          "constraints": {"linear": [{"expression": "x + y <= 10"}]},
          "validation_errors": []
        }
        """,
        router_preview=router_preview,
    )

    assert preview is not None
    assert preview.status == "extracted"
    assert preview.source == "llm_formulator_internal_beta"
    assert preview.task_type == "lp"
    assert preview.confidence == 0.84
    assert preview.variables == {"decision_variables": ["x", "y"]}
    assert preview.objective == {"sense": "minimize", "coefficients": {"x": 2, "y": 3}}
    assert preview.constraints == {"linear": [{"expression": "x + y <= 10"}]}
    assert preview.validation_errors == []


def test_parse_formulator_completion_turns_deterministic_text_into_clarification() -> None:
    router_preview = classify_message("求最短路径，把车辆路线排出来")

    preview = parse_formulator_completion(
        "formulator extraction variables constraints objective normalized_model=route "
        "deterministic_digest=abc123 provider_variant=deepseek",
        router_preview=router_preview,
    )

    assert preview is not None
    assert preview.status == "needs_clarification"
    assert preview.source == "heuristic_formulator_internal_beta"
    assert preview.task_type == "vrptw"
    assert preview.confidence == 0.4
    assert preview.variables == {}
    assert "deterministic_digest" not in str(preview.model_dump())
    assert preview.validation_errors[0].field_path == "variables"


def test_parse_formulator_completion_rejects_task_type_conflict() -> None:
    router_preview = classify_message("库存补货策略 for sku")

    preview = parse_formulator_completion(
        '{"task_type":"vrptw","confidence":0.9,"variables":{},"objective":{},'
        '"constraints":{},"validation_errors":[]}',
        router_preview=router_preview,
    )

    assert preview is None


def test_parse_formulator_completion_rejects_nested_oversized_payload() -> None:
    router_preview = classify_message("linear programming objective with constraints")
    oversized_variables = {"decision_variables": [f"x{i}" for i in range(51)]}

    preview = parse_formulator_completion(
        json.dumps(
            {
                "task_type": "lp",
                "confidence": 0.9,
                "variables": oversized_variables,
                "objective": {"sense": "minimize"},
                "constraints": {},
                "validation_errors": [],
            }
        ),
        router_preview=router_preview,
    )

    assert preview is None


def test_parse_formulator_completion_rejects_validation_error_original_message_echo() -> None:
    router_preview = classify_message("linear programming objective with constraints")
    original = "linear programming objective with constraints"

    preview = parse_formulator_completion(
        json.dumps(
            {
                "task_type": "lp",
                "confidence": 0.3,
                "variables": {},
                "objective": {},
                "constraints": {},
                "validation_errors": [
                    {
                        "field_path": "variables",
                        "message": original,
                    }
                ],
            }
        ),
        router_preview=router_preview,
        original_message=original,
    )

    assert preview is None


def test_extract_formulation_with_llm_skips_unknown_router_without_invocation() -> None:
    router_preview = classify_message("帮我看一下这个业务问题")
    called = False

    def complete_unexpected(_prompt: object, model: str) -> Completion:
        nonlocal called
        called = True
        return _completion("{}")

    result = extract_formulation_with_llm(
        message="帮我看一下这个业务问题",
        locale="zh-CN",
        prompt_id="msg_test",
        router_preview=router_preview,
        completion_func=complete_unexpected,
    )

    assert called is False
    assert result.formulator_invoked is False
    assert result.preview.status == "skipped"
    assert result.preview.task_type == "unknown"


def test_extract_formulation_with_llm_falls_back_after_router_error() -> None:
    router_preview = classify_message("请预测下个月 SKU 销量")

    def fail(_prompt: object, model: str) -> Completion:
        raise LLMRouterError("offline formulator failed")

    result = extract_formulation_with_llm(
        message="请预测下个月 SKU 销量",
        locale="mixed",
        prompt_id="msg_test",
        router_preview=router_preview,
        completion_func=fail,
    )

    assert result.formulator_invoked is True
    assert result.provider_request_sent is False
    assert result.preview.status == "needs_clarification"
    assert result.preview.source == "heuristic_formulator_internal_beta"
    assert result.preview.task_type == "prediction"


def test_extract_formulation_with_llm_unknown_model_falls_back_before_invocation() -> None:
    router_preview = classify_message("linear programming objective with constraints")
    called = False

    def complete_unexpected(_prompt: object, model: str) -> Completion:
        nonlocal called
        called = True
        return _completion("{}")

    result = extract_formulation_with_llm(
        message="linear programming objective with constraints",
        locale="en-US",
        prompt_id="msg_test",
        router_preview=router_preview,
        model_alias="unsupported-model",
        completion_func=complete_unexpected,
    )

    assert called is False
    assert result.formulator_invoked is False
    assert result.preview.status == "needs_clarification"


def test_extract_formulation_with_llm_prompt_validation_failure_falls_back_before_invocation() -> (
    None
):
    router_preview = classify_message("请做库存优化，api_key=sk-live-secret")
    called = False

    def complete_unexpected(_prompt: object, model: str) -> Completion:
        nonlocal called
        called = True
        return _completion("{}")

    result = extract_formulation_with_llm(
        message="请做库存优化，api_key=sk-live-secret",
        locale="mixed",
        prompt_id="msg_test",
        router_preview=router_preview,
        completion_func=complete_unexpected,
    )

    assert called is False
    assert result.formulator_invoked is False
    assert result.preview.task_type == "inventory"
    assert result.preview.status == "needs_clarification"


@pytest.mark.parametrize("finish_reason", ["length", "content_filter", "error"])
def test_extract_formulation_with_llm_falls_back_on_non_stop_finish_reason(
    finish_reason: str,
) -> None:
    router_preview = classify_message("linear programming objective with constraints")

    result = extract_formulation_with_llm(
        message="linear programming objective with constraints",
        locale="en-US",
        prompt_id="msg_test",
        router_preview=router_preview,
        completion_func=lambda _prompt, model: _completion(
            '{"task_type":"lp","confidence":0.9,"variables":{},"objective":{},'
            '"constraints":{},"validation_errors":[]}',
            finish_reason=finish_reason,
        ),
    )

    assert result.formulator_invoked is True
    assert result.preview.status == "needs_clarification"
