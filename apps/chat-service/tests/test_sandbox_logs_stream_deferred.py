from __future__ import annotations

from chat_service.critic import _passing_checks
from chat_service.main import app
from chat_service.sandbox import generate_sandbox_preview
from chat_service.schemas import CoderCodeArtifact, CoderPreview, CriticPreview
from fastapi.testclient import TestClient

SUPPORTED_TASK_TYPES = ["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"]
client = TestClient(app)


def test_chat_sandbox_logs_stream_request_maps_to_deferred_policy_block() -> None:
    result = generate_sandbox_preview(
        coder_preview=_generated_coder_preview(
            code="stdout:secret stream line\nstderr:Traceback /tmp/secret\nexit:0"
        ),
        critic_preview=_validated_critic_preview(),
        allow_logs_stream=True,
    )

    assert result.sandbox_invoked is True
    assert result.preview.status == "policy_blocked"
    assert result.preview.error_code == "logs_stream_deferred"
    assert result.preview.exit_code is None
    assert result.preview.stdout_excerpt == ""
    assert result.preview.result_files == []
    assert result.preview.validation_errors[0].field_path == "sandbox_runner.policy"
    assert "v1.5" in result.preview.validation_errors[0].message
    assert "secret stream line" not in result.preview.stderr_excerpt
    assert "Traceback" not in result.preview.stderr_excerpt
    host_path = "/" + "tmp/secret"
    assert host_path not in result.preview.stderr_excerpt


def test_chat_sandbox_default_does_not_request_logs_stream() -> None:
    result = generate_sandbox_preview(
        coder_preview=_generated_coder_preview(code="stdout:hello\nexit:0"),
        critic_preview=_validated_critic_preview(),
    )

    assert result.sandbox_invoked is True
    assert result.preview.status == "succeeded"
    assert result.preview.error_code is None
    assert result.preview.stdout_excerpt == "hello\n"


def test_chat_stream_route_remains_absent() -> None:
    response = client.post(
        "/v1/chat/stream",
        json={"message": "stream sandbox logs", "allow_logs_stream": True},
    )

    assert response.status_code == 404


def _generated_coder_preview(*, code: str) -> CoderPreview:
    return CoderPreview(
        status="generated",
        source="template_coder_internal_beta",
        task_type="lp",
        artifact=CoderCodeArtifact(
            language="python",
            code=code,
            entrypoint="build_payload",
            input_model="TaskInput",
            output_model="TaskPayload",
            imports=["pydantic"],
        ),
        validation_errors=[],
        supported_task_types=SUPPORTED_TASK_TYPES,
    )


def _validated_critic_preview() -> CriticPreview:
    return CriticPreview(
        status="validated",
        source="llm_critic_internal_beta",
        task_type="lp",
        confidence=0.86,
        reasoning="Critic validated schema, safety, and business-logic consistency.",
        checks=_passing_checks(),
        validation_errors=[],
        supported_task_types=SUPPORTED_TASK_TYPES,
        calibration_threshold=0.6,
        threshold_source="apps/critic-service/config/critic-calibration.json",
    )
