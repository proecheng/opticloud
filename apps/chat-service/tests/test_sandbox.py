from __future__ import annotations

from chat_service.critic import _passing_checks
import pytest
from pydantic import ValidationError

from chat_service.schemas import (
    ChatInternalBetaMessageResponse,
    ChatDisclaimer,
    LanguagePreview,
    CoderCodeArtifact,
    CoderPreview,
    CriticPreview,
    SandboxPreview,
    RouterPreview,
    FormulatorPreview,
    AigcGate,
)
from chat_service.sandbox import generate_sandbox_preview


SUPPORTED_TASK_TYPES = ["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"]


def test_sandbox_preview_contract_requires_all_limit_fields() -> None:
    preview = SandboxPreview(
        status="skipped",
        source="heuristic_sandbox_internal_beta",
        task_type="lp",
        stdout_excerpt="",
        stderr_excerpt="",
        exit_code=None,
        result_files=[],
        error_code=None,
        limits={
            "cpu_vcpu": 1,
            "memory_mb": 1024,
            "soft_timeout_seconds": 30,
            "hard_timeout_seconds": 90,
            "network_disabled": True,
            "read_only_filesystem": True,
            "result_file_budget_bytes": 104857600,
        },
        validation_errors=[],
        contract_version="sandbox-runner-p58-p62-local-v1",
    )

    assert preview.limits.cpu_vcpu == 1
    assert preview.limits.network_disabled is True
    assert preview.limits.read_only_filesystem is True


def test_sandbox_preview_contract_rejects_non_executed_payload_drift() -> None:
    with pytest.raises(ValidationError):
        SandboxPreview(
            status="skipped",
            source="heuristic_sandbox_internal_beta",
            task_type="lp",
            stdout_excerpt="",
            stderr_excerpt="",
            exit_code=0,
            result_files=[],
            error_code=None,
            limits=_sandbox_limits(),
            validation_errors=[],
            contract_version="sandbox-runner-p58-p62-local-v1",
        )

    with pytest.raises(ValidationError):
        SandboxPreview(
            status="policy_blocked",
            source="sandbox_runner_local_contract_internal_beta",
            task_type="lp",
            stdout_excerpt="",
            stderr_excerpt="blocked",
            exit_code=1,
            result_files=[],
            error_code="network_disabled",
            limits=_sandbox_limits(),
            validation_errors=[],
            contract_version="sandbox-runner-p58-p62-local-v1",
        )

    with pytest.raises(ValidationError):
        SandboxPreview(
            status="succeeded",
            source="sandbox_runner_local_contract_internal_beta",
            task_type="lp",
            stdout_excerpt="",
            stderr_excerpt="",
            exit_code=0,
            result_files=[{"path": " ", "size_bytes": 0, "sha256": "0" * 64}],
            error_code=None,
            limits=_sandbox_limits(),
            validation_errors=[],
            contract_version="sandbox-runner-p58-p62-local-v1",
        )


def test_internal_beta_response_contract_rejects_sandbox_invocation_drift() -> None:
    with pytest.raises(ValidationError):
        ChatInternalBetaMessageResponse(
            mode="internal_beta",
            public_access=False,
            message_id="msg_contract",
            message_excerpt="linear programming objective",
            locale="en-US",
            router_preview=RouterPreview(
                task_type="lp",
                confidence=0.9,
                reasoning="matched",
                source="heuristic_internal_beta",
                supported_task_types=SUPPORTED_TASK_TYPES,
            ),
            formulator_preview=FormulatorPreview(
                status="needs_clarification",
                source="heuristic_formulator_internal_beta",
                task_type="lp",
                confidence=0.4,
                variables={},
                objective={},
                constraints={},
                validation_errors=[],
                supported_task_types=SUPPORTED_TASK_TYPES,
            ),
            coder_preview=CoderPreview(
                status="needs_clarification",
                source="heuristic_coder_internal_beta",
                task_type="lp",
                artifact=None,
                validation_errors=[],
                supported_task_types=SUPPORTED_TASK_TYPES,
            ),
            critic_preview=_validated_critic_preview(),
            sandbox_preview=SandboxPreview(
                status="skipped",
                source="heuristic_sandbox_internal_beta",
                task_type="lp",
                stdout_excerpt="",
                stderr_excerpt="",
                exit_code=None,
                result_files=[],
                error_code=None,
                limits=_sandbox_limits(),
                validation_errors=[],
                contract_version="sandbox-runner-p58-p62-local-v1",
            ),
            language_preview=LanguagePreview(
                status="fallback",
                source="heuristic_language_internal_beta",
                response_locale="en-US",
                summary="Detected LP request and generated an internal beta preview.",
                disclaimer=ChatDisclaimer(
                    zh="AI 生成内容仅供参考，请在提交求解前核对。",
                    en="AI-generated content is for reference only. Review it before submitting a solve.",
                    bilingual=(
                        "AI 生成内容仅供参考，请在提交求解前核对。 / "
                        "AI-generated content is for reference only. Review it before submitting a solve."
                    ),
                ),
                validation_errors=[],
                supported_locales=["zh-CN", "en-US", "mixed"],
            ),
            aigc_gate=AigcGate(status="filing_pending", public_surface="hidden"),
            llm_invoked=True,
            critic_invoked=True,
            critic_llm_invoked=False,
            provider_request_sent=False,
            solver_invoked=False,
            sandbox_invoked=True,
        )


def test_sandbox_executes_only_after_coder_and_critic_gate() -> None:
    result = generate_sandbox_preview(
        coder_preview=_generated_coder_preview(
            code="\n".join(
                [
                    "stdout:ready",
                    "stderr:warn",
                    "result:reports/output.json={}",
                ]
            )
        ),
        critic_preview=_validated_critic_preview(),
    )

    assert result.sandbox_invoked is True
    assert result.preview.status == "succeeded"
    assert result.preview.source == "sandbox_runner_local_contract_internal_beta"
    assert result.preview.stdout_excerpt == "ready\n"
    assert result.preview.stderr_excerpt == "warn\n"
    assert result.preview.exit_code == 0
    assert [result_file.model_dump() for result_file in result.preview.result_files] == [
        {
            "path": "reports/output.json",
            "size_bytes": 2,
            "sha256": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        }
    ]
    assert result.preview.error_code is None


def test_sandbox_skips_when_coder_is_not_generated() -> None:
    result = generate_sandbox_preview(
        coder_preview=CoderPreview(
            status="needs_clarification",
            source="heuristic_coder_internal_beta",
            task_type="lp",
            artifact=None,
            validation_errors=[],
            supported_task_types=SUPPORTED_TASK_TYPES,
        ),
        critic_preview=_validated_critic_preview(),
    )

    assert result.sandbox_invoked is False
    assert result.preview.status == "skipped"
    assert result.preview.source == "heuristic_sandbox_internal_beta"
    assert result.preview.validation_errors[0].field_path == "coder_preview.artifact"


def test_sandbox_skips_when_critic_is_not_validated() -> None:
    result = generate_sandbox_preview(
        coder_preview=_generated_coder_preview(code="stdout:ready"),
        critic_preview=CriticPreview(
            status="needs_clarification",
            source="heuristic_critic_internal_beta",
            task_type="lp",
            confidence=0.4,
            reasoning="Critic validation is unavailable; keep the code in internal beta preview.",
            checks=_passing_checks(),
            validation_errors=[],
            supported_task_types=SUPPORTED_TASK_TYPES,
            calibration_threshold=0.6,
            threshold_source="apps/critic-service/config/critic-calibration.json",
        ),
    )

    assert result.sandbox_invoked is False
    assert result.preview.status == "skipped"
    assert result.preview.validation_errors[0].field_path == "critic_preview.status"


def test_sandbox_maps_policy_block_without_running_executor() -> None:
    result = generate_sandbox_preview(
        coder_preview=_generated_coder_preview(code="import requests\nstdout:should-not-run"),
        critic_preview=_validated_critic_preview(),
    )

    assert result.sandbox_invoked is True
    assert result.preview.status == "policy_blocked"
    assert result.preview.error_code == "network_disabled"
    assert result.preview.stdout_excerpt == ""
    assert result.preview.exit_code is None
    assert result.preview.validation_errors[0].field_path == "sandbox_runner.policy"


def test_sandbox_maps_nonzero_exit_to_failed_preview() -> None:
    result = generate_sandbox_preview(
        coder_preview=_generated_coder_preview(code="stdout:started\nexit:7"),
        critic_preview=_validated_critic_preview(),
    )

    assert result.sandbox_invoked is True
    assert result.preview.status == "failed"
    assert result.preview.exit_code == 7
    assert result.preview.stdout_excerpt == "started\n"


def test_sandbox_sanitizes_stdout_stderr_excerpts() -> None:
    result = generate_sandbox_preview(
        coder_preview=_generated_coder_preview(
            code=(
                "stdout:bearer abc.def.ghi\n"
                "stderr:Traceback (most recent call last): /tmp/host/path\n"
            )
        ),
        critic_preview=_validated_critic_preview(),
    )

    assert result.preview.stdout_excerpt == "[redacted]\n"
    assert "Traceback" not in result.preview.stderr_excerpt
    assert "/tmp/host/path" not in result.preview.stderr_excerpt


def test_sandbox_sanitized_excerpts_remain_bounded_after_redaction() -> None:
    result = generate_sandbox_preview(
        coder_preview=_generated_coder_preview(code="stdout:" + "token " * 140),
        critic_preview=_validated_critic_preview(),
    )

    assert len(result.preview.stdout_excerpt) <= 512
    assert "token" not in result.preview.stdout_excerpt.lower()


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


def _sandbox_limits() -> dict[str, object]:
    return {
        "cpu_vcpu": 1,
        "memory_mb": 1024,
        "soft_timeout_seconds": 30,
        "hard_timeout_seconds": 90,
        "network_disabled": True,
        "read_only_filesystem": True,
        "result_file_budget_bytes": 104857600,
    }
