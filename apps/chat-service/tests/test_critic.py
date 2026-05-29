from __future__ import annotations

import json

from chat_service.critic import (
    build_critic_prompt,
    generate_critic_validation_with_llm,
    load_critic_calibration_threshold,
)
from chat_service.schemas import CoderCodeArtifact, CoderPreview, CoderValidationError
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


def _lp_code() -> str:
    return """
from pydantic import BaseModel


class LpInput(BaseModel):
    coefficients: dict[str, float]
    constraints: list[str]


class LpPayload(BaseModel):
    task_type: str
    objective: dict[str, object]
    constraints: dict[str, object]


def build_payload(data: LpInput) -> LpPayload:
    return LpPayload(
        task_type="lp",
        objective={"sense": "minimize", "coefficients": data.coefficients},
        constraints={"linear": data.constraints},
    )
""".strip()


def _safe_coder_preview() -> CoderPreview:
    return CoderPreview(
        status="generated",
        source="llm_coder_internal_beta",
        task_type="lp",
        artifact=CoderCodeArtifact(
            language="python",
            code=_lp_code(),
            entrypoint="build_payload",
            input_model="LpInput",
            output_model="LpPayload",
            imports=["pydantic"],
        ),
        validation_errors=[],
        supported_task_types=["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"],
    )


def test_build_critic_prompt_uses_m3_8_contract_without_metadata_leak() -> None:
    coder_preview = _safe_coder_preview()

    prompt = build_critic_prompt(
        locale="en-US",
        prompt_id="msg_test",
        coder_preview=coder_preview,
        calibration_threshold=0.6,
    )

    assert prompt.prompt_id == "msg_test"
    assert prompt.task == "critic_validation"
    assert prompt.locale == "en-US"
    assert [message.role for message in prompt.messages] == ["system", "user"]
    assert prompt.response_schema is not None
    assert prompt.metadata == {
        "coder_status": "generated",
        "coder_source": "llm_coder_internal_beta",
        "task_type": "lp",
        "calibration_threshold": 0.6,
    }
    assert "from pydantic" in prompt.messages[1].content
    assert "from pydantic" not in json.dumps(prompt.metadata)
    assert "linear programming objective" not in prompt.messages[1].content


def test_load_critic_calibration_threshold_uses_committed_config() -> None:
    threshold = load_critic_calibration_threshold()

    assert threshold.value == 0.6
    assert threshold.source == "apps/critic-service/config/critic-calibration.json"


def test_generate_critic_validation_accepts_safe_generated_artifact() -> None:
    result = generate_critic_validation_with_llm(
        locale="en-US",
        prompt_id="msg_test",
        coder_preview=_safe_coder_preview(),
        completion_func=lambda _prompt, model: _completion(
            "critic validation schema logic safety confidence calibrated review"
        ),
    )

    assert result.critic_invoked is True
    assert result.critic_llm_invoked is True
    assert result.provider_request_sent is False
    assert result.preview.status == "validated"
    assert result.preview.source == "llm_critic_internal_beta"
    assert result.preview.task_type == "lp"
    assert result.preview.confidence >= 0.6
    assert result.preview.calibration_threshold == 0.6
    assert result.preview.threshold_source == "apps/critic-service/config/critic-calibration.json"
    assert set(result.preview.checks) == {"schema", "safety", "business_logic"}
    assert all(check.passed for check in result.preview.checks.values())
    assert result.preview.validation_errors == []
    assert "from pydantic" not in result.preview.reasoning
    assert "deterministic_digest" not in result.preview.reasoning


def test_generate_critic_validation_accepts_m3_8_deterministic_digest_text() -> None:
    result = generate_critic_validation_with_llm(
        locale="en-US",
        prompt_id="msg_test",
        coder_preview=_safe_coder_preview(),
        completion_func=lambda _prompt, model: _completion(
            "critic validation schema logic safety confidence calibrated review "
            "deterministic_digest=abc123 provider_variant=deepseek alias=deepseek-v3.5"
        ),
    )

    assert result.critic_llm_invoked is True
    assert result.preview.status == "validated"
    assert result.preview.source == "llm_critic_internal_beta"
    assert "deterministic_digest" not in result.preview.reasoning


def test_generate_critic_validation_rejects_unstructured_safe_completion_text() -> None:
    result = generate_critic_validation_with_llm(
        locale="en-US",
        prompt_id="msg_test",
        coder_preview=_safe_coder_preview(),
        completion_func=lambda _prompt, model: _completion("looks reasonable to me"),
    )

    assert result.critic_llm_invoked is True
    assert result.preview.status == "needs_clarification"
    assert result.preview.source == "heuristic_critic_internal_beta"
    assert result.preview.validation_errors[0].field_path == "critic.completion"


def test_generate_critic_validation_skips_without_llm_when_coder_needs_clarification() -> None:
    called = False
    coder_preview = CoderPreview(
        status="needs_clarification",
        source="heuristic_coder_internal_beta",
        task_type="lp",
        artifact=None,
        validation_errors=[
            CoderValidationError(
                field_path="formulator_preview.variables",
                message="structured formulation is required before code generation",
            )
        ],
        supported_task_types=["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"],
    )

    def complete_unexpected(_prompt: object, model: str) -> Completion:
        nonlocal called
        called = True
        return _completion("critic validation")

    result = generate_critic_validation_with_llm(
        locale="en-US",
        prompt_id="msg_test",
        coder_preview=coder_preview,
        completion_func=complete_unexpected,
    )

    assert called is False
    assert result.critic_invoked is True
    assert result.critic_llm_invoked is False
    assert result.preview.status == "skipped"
    assert result.preview.source == "heuristic_critic_internal_beta"
    assert result.preview.confidence == 0.0
    assert result.preview.validation_errors[0].field_path == "coder_preview.artifact"


def test_generate_critic_validation_falls_back_after_router_error() -> None:
    def fail(_prompt: object, model: str) -> Completion:
        raise LLMRouterError("offline critic failed")

    result = generate_critic_validation_with_llm(
        locale="en-US",
        prompt_id="msg_test",
        coder_preview=_safe_coder_preview(),
        completion_func=fail,
    )

    assert result.critic_invoked is True
    assert result.critic_llm_invoked is True
    assert result.preview.status == "needs_clarification"
    assert result.preview.source == "heuristic_critic_internal_beta"
    assert result.preview.confidence < 0.6
    assert result.preview.validation_errors[0].field_path == "critic.completion"
    dumped = result.preview.model_dump()
    assert "human_review_queue" not in dumped
    assert "escalated" not in dumped


def test_generate_critic_validation_falls_back_on_non_stop_finish_reason() -> None:
    result = generate_critic_validation_with_llm(
        locale="en-US",
        prompt_id="msg_test",
        coder_preview=_safe_coder_preview(),
        completion_func=lambda _prompt, model: _completion(
            "critic validation schema logic safety confidence calibrated review",
            finish_reason="length",
        ),
    )

    assert result.critic_llm_invoked is True
    assert result.preview.status == "needs_clarification"
    assert result.preview.source == "heuristic_critic_internal_beta"
    assert result.preview.validation_errors[0].field_path == "critic.completion"


def test_generate_critic_validation_unknown_alias_falls_back_before_invocation() -> None:
    called = False

    def complete_unexpected(_prompt: object, model: str) -> Completion:
        nonlocal called
        called = True
        return _completion("critic validation")

    result = generate_critic_validation_with_llm(
        locale="en-US",
        prompt_id="msg_test",
        coder_preview=_safe_coder_preview(),
        completion_func=complete_unexpected,
        model_alias="unknown-model",
    )

    assert called is False
    assert result.critic_llm_invoked is False
    assert result.preview.status == "needs_clarification"
    assert result.preview.validation_errors[0].field_path == "critic.model"


def test_generate_critic_validation_rejects_unsafe_artifact_without_leaking_snippet() -> None:
    unsafe_preview = CoderPreview(
        status="generated",
        source="llm_coder_internal_beta",
        task_type="lp",
        artifact=CoderCodeArtifact(
            language="python",
            code="""
import requests
from pydantic import BaseModel


class LpInput(BaseModel):
    x: int


class LpPayload(BaseModel):
    task_type: str


def build_payload(data: LpInput) -> LpPayload:
    eval("1 + 1")
    return LpPayload(task_type="lp")
""".strip(),
            entrypoint="build_payload",
            input_model="LpInput",
            output_model="LpPayload",
            imports=["requests", "pydantic"],
        ),
        validation_errors=[],
        supported_task_types=["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"],
    )
    called = False

    def complete_unexpected(_prompt: object, model: str) -> Completion:
        nonlocal called
        called = True
        return _completion("critic validation")

    result = generate_critic_validation_with_llm(
        locale="en-US",
        prompt_id="msg_test",
        coder_preview=unsafe_preview,
        completion_func=complete_unexpected,
    )

    assert called is False
    assert result.critic_llm_invoked is False
    assert result.preview.status == "needs_clarification"
    assert result.preview.confidence < 0.6
    assert result.preview.checks["safety"].passed is False
    assert "requests" not in result.preview.reasoning
    assert "eval" not in result.preview.reasoning
    assert all("requests" not in error.message for error in result.preview.validation_errors)
    assert all("eval" not in error.message for error in result.preview.validation_errors)


def test_generate_critic_validation_rejects_task_type_drift_before_llm() -> None:
    drifted_preview = _safe_coder_preview().model_copy(update={"task_type": "vrptw"})
    called = False

    def complete_unexpected(_prompt: object, model: str) -> Completion:
        nonlocal called
        called = True
        return _completion("critic validation")

    result = generate_critic_validation_with_llm(
        locale="en-US",
        prompt_id="msg_test",
        coder_preview=drifted_preview,
        completion_func=complete_unexpected,
    )

    assert called is False
    assert result.critic_llm_invoked is False
    assert result.preview.status == "needs_clarification"
    assert result.preview.checks["business_logic"].passed is False
    assert result.preview.validation_errors[0].field_path == "artifact.code"
    assert result.preview.confidence < result.preview.calibration_threshold


def test_generate_critic_validation_sanitizes_unsafe_completion_text() -> None:
    result = generate_critic_validation_with_llm(
        locale="en-US",
        prompt_id="msg_test",
        coder_preview=_safe_coder_preview(),
        completion_func=lambda _prompt, model: _completion(
            "critic validation raw_response provider_response token traceback"
        ),
    )

    assert result.critic_llm_invoked is True
    assert result.preview.status == "needs_clarification"
    assert result.preview.source == "heuristic_critic_internal_beta"
    assert "raw_response" not in result.preview.reasoning
    assert "provider_response" not in result.preview.reasoning
    assert "token" not in result.preview.reasoning.lower()
