from __future__ import annotations

import json

import pytest
from chat_service.coder import (
    build_coder_prompt,
    generate_code_with_llm,
    parse_coder_completion,
    validate_code_artifact,
)
from chat_service.formulator import parse_formulator_completion
from chat_service.router_preview import classify_message
from chat_service.schemas import CoderCodeArtifact, FormulatorPreview
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


def _lp_formulator_preview():
    router_preview = classify_message("linear programming objective with constraints")
    preview = parse_formulator_completion(
        json.dumps(
            {
                "task_type": "lp",
                "confidence": 0.84,
                "variables": {"decision_variables": ["x", "y"]},
                "objective": {"sense": "minimize", "coefficients": {"x": 2, "y": 3}},
                "constraints": {"linear": [{"expression": "x + y <= 10"}]},
                "validation_errors": [],
            }
        ),
        router_preview=router_preview,
    )
    assert preview is not None
    return preview


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


def test_build_coder_prompt_uses_m3_8_contract() -> None:
    formulator_preview = _lp_formulator_preview()

    prompt = build_coder_prompt(
        message="minimize 2 x plus 3 y subject to x plus y <= 10",
        locale="en-US",
        prompt_id="msg_test",
        formulator_preview=formulator_preview,
    )

    assert prompt.prompt_id == "msg_test"
    assert prompt.task == "coder_generation"
    assert prompt.locale == "en-US"
    assert [message.role for message in prompt.messages] == ["system", "user"]
    assert prompt.response_schema is not None
    assert prompt.response_schema["required"] == ["task_type", "artifact"]
    assert prompt.metadata == {"formulator_task_type": "lp"}
    assert "minimize 2 x plus 3 y" not in prompt.messages[1].content
    assert "formulator_preview" in prompt.messages[1].content


def test_parse_coder_completion_accepts_safe_lp_json_artifact() -> None:
    formulator_preview = _lp_formulator_preview()

    preview = parse_coder_completion(
        json.dumps(
            {
                "task_type": "lp",
                "confidence": 0.91,
                "artifact": {
                    "language": "python",
                    "code": _lp_code(),
                    "entrypoint": "build_payload",
                    "input_model": "LpInput",
                    "output_model": "LpPayload",
                    "imports": ["pydantic"],
                },
                "validation_errors": [],
            }
        ),
        formulator_preview=formulator_preview,
    )

    assert preview is not None
    assert preview.status == "generated"
    assert preview.source == "llm_coder_internal_beta"
    assert preview.task_type == "lp"
    assert preview.artifact is not None
    assert preview.artifact.entrypoint == "build_payload"
    assert preview.validation_errors == []


def test_parse_coder_completion_returns_sanitized_reported_validation_errors() -> None:
    formulator_preview = _lp_formulator_preview()

    preview = parse_coder_completion(
        json.dumps(
            {
                "task_type": "lp",
                "artifact": {
                    "language": "python",
                    "code": _lp_code(),
                    "entrypoint": "build_payload",
                    "input_model": "LpInput",
                    "output_model": "LpPayload",
                    "imports": ["pydantic"],
                },
                "validation_errors": [
                    {
                        "field_path": "artifact.code",
                        "message": "objective terms need clarification",
                        "remediation_hint_key": "chat.coder.objective_required",
                    }
                ],
            }
        ),
        formulator_preview=formulator_preview,
    )

    assert preview is not None
    assert preview.status == "needs_clarification"
    assert preview.artifact is None
    assert preview.validation_errors[0].field_path == "artifact.code"
    assert preview.validation_errors[0].message == "objective terms need clarification"


def test_parse_coder_completion_rejects_unsafe_reported_validation_errors() -> None:
    formulator_preview = _lp_formulator_preview()

    preview = parse_coder_completion(
        json.dumps(
            {
                "task_type": "lp",
                "artifact": {
                    "language": "python",
                    "code": _lp_code(),
                    "entrypoint": "build_payload",
                    "input_model": "LpInput",
                    "output_model": "LpPayload",
                    "imports": ["pydantic"],
                },
                "validation_errors": [
                    {
                        "field_path": "artifact.code",
                        "message": "provider_response included token",
                    }
                ],
            }
        ),
        formulator_preview=formulator_preview,
    )

    assert preview is None


def test_parse_coder_completion_rejects_top_level_provider_payload_fields() -> None:
    formulator_preview = _lp_formulator_preview()

    preview = parse_coder_completion(
        json.dumps(
            {
                "task_type": "lp",
                "raw_response": {"choices": []},
                "artifact": {
                    "language": "python",
                    "code": _lp_code(),
                    "entrypoint": "build_payload",
                    "input_model": "LpInput",
                    "output_model": "LpPayload",
                    "imports": ["pydantic"],
                },
                "validation_errors": [],
            }
        ),
        formulator_preview=formulator_preview,
    )

    assert preview is None


def test_parse_coder_completion_turns_deterministic_text_into_template_artifact() -> None:
    formulator_preview = _lp_formulator_preview()

    preview = parse_coder_completion(
        "coder generation python function validation deterministic implementation "
        "deterministic_digest=abc123 provider_variant=deepseek",
        formulator_preview=formulator_preview,
    )

    assert preview is not None
    assert preview.status == "generated"
    assert preview.source == "template_coder_internal_beta"
    assert preview.artifact is not None
    assert preview.artifact.language == "python"
    assert preview.artifact.entrypoint == "build_payload"
    assert preview.artifact.input_model == "TaskInput"
    assert '"lp"' in preview.artifact.code
    assert "deterministic_digest" not in preview.artifact.code


def test_generate_code_with_llm_does_not_invoke_when_formulator_needs_clarification() -> None:
    router_preview = classify_message("linear programming objective with constraints")
    formulator_preview = parse_formulator_completion(
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
                        "message": "structured variables are required",
                    }
                ],
            }
        ),
        router_preview=router_preview,
    )
    assert formulator_preview is not None
    assert formulator_preview.status == "needs_clarification"
    called = False

    def complete_unexpected(_prompt: object, model: str) -> Completion:
        nonlocal called
        called = True
        return _completion("{}")

    result = generate_code_with_llm(
        message="linear programming objective with constraints",
        locale="en-US",
        prompt_id="msg_test",
        formulator_preview=formulator_preview,
        completion_func=complete_unexpected,
    )

    assert called is False
    assert result.coder_invoked is False
    assert result.preview.status == "needs_clarification"
    assert result.preview.artifact is None
    assert result.preview.validation_errors[0].field_path.startswith("formulator_preview")


def test_generate_code_with_llm_skips_unknown_without_invocation() -> None:
    router_preview = classify_message("帮我看一下这个业务问题")
    formulator_preview = parse_formulator_completion(
        "formulator extraction variables constraints objective deterministic_digest=abc123",
        router_preview=router_preview,
    )
    assert formulator_preview is not None
    assert formulator_preview.status == "needs_clarification"
    called = False

    def complete_unexpected(_prompt: object, model: str) -> Completion:
        nonlocal called
        called = True
        return _completion("{}")

    result = generate_code_with_llm(
        message="帮我看一下这个业务问题",
        locale="zh-CN",
        prompt_id="msg_test",
        formulator_preview=formulator_preview,
        completion_func=complete_unexpected,
    )

    assert called is False
    assert result.coder_invoked is False
    assert result.preview.status in {"needs_clarification", "skipped"}
    assert result.preview.artifact is None


def test_generate_code_with_llm_prompt_validation_failure_falls_back_before_invocation() -> None:
    formulator_preview = FormulatorPreview(
        status="extracted",
        source="llm_formulator_internal_beta",
        task_type="lp",
        confidence=0.9,
        variables={"api_key": "sk-live-secret"},
        objective={"sense": "minimize"},
        constraints={"linear": ["x <= 10"]},
        validation_errors=[],
        supported_task_types=["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"],
    )
    called = False

    def complete_unexpected(_prompt: object, model: str) -> Completion:
        nonlocal called
        called = True
        return _completion("{}")

    result = generate_code_with_llm(
        message="linear programming objective with constraints",
        locale="en-US",
        prompt_id="msg_test",
        formulator_preview=formulator_preview,
        completion_func=complete_unexpected,
    )

    assert called is False
    assert result.coder_invoked is False
    assert result.preview.status == "needs_clarification"
    assert result.preview.artifact is None
    assert result.preview.validation_errors[0].field_path == "coder.prompt"


def test_parse_coder_completion_rejects_task_type_conflict() -> None:
    formulator_preview = _lp_formulator_preview()

    preview = parse_coder_completion(
        json.dumps(
            {
                "task_type": "vrptw",
                "artifact": {
                    "language": "python",
                    "code": _lp_code(),
                    "entrypoint": "build_payload",
                    "input_model": "LpInput",
                    "output_model": "LpPayload",
                    "imports": ["pydantic"],
                },
                "validation_errors": [],
            }
        ),
        formulator_preview=formulator_preview,
    )

    assert preview is None


def test_validate_code_artifact_rejects_dangerous_imports_and_calls() -> None:
    artifact = CoderCodeArtifact(
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
    )

    errors = validate_code_artifact(artifact)

    assert [error.field_path for error in errors] == ["artifact.imports", "artifact.code"]
    assert "requests" not in errors[0].message
    assert "eval" not in errors[1].message


def test_validate_code_artifact_rejects_blocked_runtime_symbol_calls_without_imports() -> None:
    artifact = CoderCodeArtifact(
        language="python",
        code="""
from pydantic import BaseModel


class LpInput(BaseModel):
    x: int


class LpPayload(BaseModel):
    task_type: str


def build_payload(data: LpInput) -> LpPayload:
    requests.post("https://example.test")
    return LpPayload(task_type="lp")
""".strip(),
        entrypoint="build_payload",
        input_model="LpInput",
        output_model="LpPayload",
        imports=["pydantic"],
    )

    errors = validate_code_artifact(artifact)

    assert [error.field_path for error in errors] == ["artifact.code"]
    assert "requests" not in errors[0].message


def test_validate_code_artifact_rejects_unannotated_generator_entrypoint() -> None:
    artifact = CoderCodeArtifact(
        language="python",
        code="""
from pydantic import BaseModel


class LpInput(BaseModel):
    x: int


class LpPayload(BaseModel):
    task_type: str


def build_payload(data):
    yield LpPayload(task_type="lp")
""".strip(),
        entrypoint="build_payload",
        input_model="LpInput",
        output_model="LpPayload",
        imports=["pydantic"],
    )

    errors = validate_code_artifact(artifact)

    assert [error.field_path for error in errors] == [
        "artifact.entrypoint",
        "artifact.entrypoint",
    ]


@pytest.mark.parametrize("finish_reason", ["length", "content_filter", "error"])
def test_generate_code_with_llm_falls_back_on_non_stop_finish_reason(finish_reason: str) -> None:
    formulator_preview = _lp_formulator_preview()

    result = generate_code_with_llm(
        message="linear programming objective with constraints",
        locale="en-US",
        prompt_id="msg_test",
        formulator_preview=formulator_preview,
        completion_func=lambda _prompt, model: _completion(
            json.dumps(
                {
                    "task_type": "lp",
                    "artifact": {
                        "language": "python",
                        "code": _lp_code(),
                        "entrypoint": "build_payload",
                        "input_model": "LpInput",
                        "output_model": "LpPayload",
                        "imports": ["pydantic"],
                    },
                }
            ),
            finish_reason=finish_reason,
        ),
    )

    assert result.coder_invoked is True
    assert result.preview.status == "needs_clarification"
    assert result.preview.artifact is None


def test_generate_code_with_llm_falls_back_after_router_error() -> None:
    formulator_preview = _lp_formulator_preview()

    def fail(_prompt: object, model: str) -> Completion:
        raise LLMRouterError("offline coder failed")

    result = generate_code_with_llm(
        message="linear programming objective with constraints",
        locale="en-US",
        prompt_id="msg_test",
        formulator_preview=formulator_preview,
        completion_func=fail,
    )

    assert result.coder_invoked is True
    assert result.provider_request_sent is False
    assert result.preview.status == "needs_clarification"
    assert result.preview.artifact is None
