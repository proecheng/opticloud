from __future__ import annotations

import hashlib

import pytest
from chat_service.critic import _passing_checks
from chat_service.model_preview import generate_model_preview
from chat_service.schemas import (
    CoderCodeArtifact,
    CoderPreview,
    CriticPreview,
    FormulatorPreview,
    HumanReviewPreview,
    ModelPreview,
    SandboxPreview,
)
from pydantic import ValidationError

SUPPORTED_TASK_TYPES = ["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"]


def test_model_preview_ready_to_confirm_uses_upstream_previews() -> None:
    coder_preview = _generated_coder_preview()
    result = generate_model_preview(
        prompt_id="msg_ready",
        formulator_preview=_extracted_formulator_preview(),
        coder_preview=coder_preview,
        critic_preview=_validated_critic_preview(),
        sandbox_preview=_succeeded_sandbox_preview(),
        human_review=_not_escalated_human_review(),
        sandbox_invoked=True,
    )

    assert result.status == "ready_to_confirm"
    assert result.preview_id.startswith("mpv_")
    assert len(result.preview_id) == 20
    assert result.variables == {"decision_variables": ["x", "y"]}
    assert result.objective == {"sense": "minimize", "coefficients": {"x": 2, "y": 3}}
    assert result.constraints == {"linear": [{"expression": "x + y <= 10"}]}
    assert result.code_artifact == coder_preview.artifact
    assert result.requires_human_review is False
    assert result.critic_confidence == 0.86
    assert result.sandbox_status == "succeeded"
    assert result.validation_errors == []
    assert [(action.kind, action.enabled, action.disabled_reason_code) for action in result.actions] == [
        ("confirm", True, None),
        ("edit", True, None),
        ("cancel", True, None),
    ]

    same_result = generate_model_preview(
        prompt_id="msg_ready",
        formulator_preview=_extracted_formulator_preview(),
        coder_preview=coder_preview,
        critic_preview=_validated_critic_preview(),
        sandbox_preview=_succeeded_sandbox_preview(),
        human_review=_not_escalated_human_review(),
        sandbox_invoked=True,
    )
    assert same_result.preview_id == result.preview_id


def test_model_preview_human_review_blocks_before_clarification() -> None:
    result = generate_model_preview(
        prompt_id="msg_human_review",
        formulator_preview=_needs_clarification_formulator_preview(),
        coder_preview=CoderPreview(
            status="needs_clarification",
            source="heuristic_coder_internal_beta",
            task_type="lp",
            artifact=None,
            validation_errors=[],
            supported_task_types=SUPPORTED_TASK_TYPES,
        ),
        critic_preview=_skipped_critic_preview(task_type="lp"),
        sandbox_preview=_skipped_sandbox_preview(task_type="lp"),
        human_review=_escalated_human_review(confidence=0.0),
        sandbox_invoked=False,
    )

    assert result.status == "blocked"
    assert result.code_artifact is None
    assert result.actions[0].kind == "confirm"
    assert result.actions[0].enabled is False
    assert result.actions[0].disabled_reason_code == "human_review_required"
    assert result.actions[1].enabled is True
    assert result.actions[2].enabled is True
    assert result.validation_errors[0].field_path.startswith("formulator_preview")


def test_model_preview_clarification_disables_confirm_when_no_safety_block() -> None:
    result = generate_model_preview(
        prompt_id="msg_needs_clarification",
        formulator_preview=_needs_clarification_formulator_preview(),
        coder_preview=CoderPreview(
            status="needs_clarification",
            source="heuristic_coder_internal_beta",
            task_type="lp",
            artifact=None,
            validation_errors=[],
            supported_task_types=SUPPORTED_TASK_TYPES,
        ),
        critic_preview=_validated_critic_preview(),
        sandbox_preview=_succeeded_sandbox_preview(),
        human_review=_not_escalated_human_review(),
        sandbox_invoked=True,
    )

    assert result.status == "needs_clarification"
    assert result.actions[0].enabled is False
    assert result.actions[0].disabled_reason_code == "needs_clarification"
    assert result.actions[1].enabled is True
    assert result.actions[2].enabled is True


def test_model_preview_unknown_task_uses_stable_disabled_reason() -> None:
    result = generate_model_preview(
        prompt_id="msg_unknown",
        formulator_preview=FormulatorPreview(
            status="skipped",
            source="heuristic_formulator_internal_beta",
            task_type="unknown",
            confidence=0.0,
            variables={},
            objective={},
            constraints={},
            validation_errors=[],
            supported_task_types=SUPPORTED_TASK_TYPES,
        ),
        coder_preview=CoderPreview(
            status="skipped",
            source="heuristic_coder_internal_beta",
            task_type="unknown",
            artifact=None,
            validation_errors=[],
            supported_task_types=SUPPORTED_TASK_TYPES,
        ),
        critic_preview=_skipped_critic_preview(task_type="unknown"),
        sandbox_preview=_skipped_sandbox_preview(task_type="unknown"),
        human_review=_escalated_human_review(confidence=0.0),
        sandbox_invoked=False,
    )

    assert result.status == "needs_clarification"
    assert result.task_type == "unknown"
    assert result.actions[0].enabled is False
    assert result.actions[0].disabled_reason_code == "task_type_unknown"
    assert result.actions[1].enabled is True
    assert result.actions[2].enabled is True


def test_model_preview_blocks_safety_gate_and_does_not_emit_execution_ids() -> None:
    result = generate_model_preview(
        prompt_id="msg_blocked",
        formulator_preview=_extracted_formulator_preview(),
        coder_preview=_generated_coder_preview(),
        critic_preview=_validated_critic_preview(),
        sandbox_preview=_policy_blocked_sandbox_preview(),
        human_review=_not_escalated_human_review(),
        sandbox_invoked=True,
    )

    dumped = result.model_dump(mode="json")
    assert result.status == "blocked"
    assert result.actions[0].enabled is False
    assert result.actions[0].disabled_reason_code == "sandbox_not_succeeded"
    assert "confirm_url" not in dumped
    assert "solve_url" not in dumped
    assert "charge_id" not in dumped
    assert "optimization_id" not in dumped
    assert "prediction_id" not in dumped
    assert "conversation_id" not in dumped


def test_model_preview_blocks_task_type_drift_before_clarification() -> None:
    result = generate_model_preview(
        prompt_id="msg_drift",
        formulator_preview=_extracted_formulator_preview(),
        coder_preview=_generated_coder_preview(task_type="vrptw"),
        critic_preview=_validated_critic_preview(task_type="vrptw"),
        sandbox_preview=_succeeded_sandbox_preview(task_type="vrptw"),
        human_review=_not_escalated_human_review(task_type="vrptw"),
        sandbox_invoked=True,
    )

    assert result.status == "blocked"
    assert result.actions[0].enabled is False
    assert result.actions[0].disabled_reason_code == "dependency_drift"
    assert any(error.field_path == "model_preview.task_type" for error in result.validation_errors)


def test_model_preview_schema_rejects_action_order_and_status_drift() -> None:
    action_payloads = [
        _action_payload("edit", enabled=True, disabled_reason_code=None),
        _action_payload("confirm", enabled=True, disabled_reason_code=None),
        _action_payload("cancel", enabled=True, disabled_reason_code=None),
    ]
    with pytest.raises(ValidationError):
        ModelPreview(
            preview_id="mpv_0123456789abcdef",
            status="ready_to_confirm",
            source="chat_model_preview_internal_beta",
            task_type="lp",
            variables={"decision_variables": ["x"]},
            objective={"sense": "minimize"},
            constraints={"linear": []},
            code_artifact=_generated_coder_preview().artifact,
            actions=action_payloads,
            requires_human_review=False,
            critic_confidence=0.86,
            sandbox_status="succeeded",
            validation_errors=[],
        )

    with pytest.raises(ValidationError):
        ModelPreview(
            preview_id="mpv_0123456789abcdef",
            status="ready_to_confirm",
            source="chat_model_preview_internal_beta",
            task_type="lp",
            variables={"decision_variables": ["x"]},
            objective={"sense": "minimize"},
            constraints={"linear": []},
            code_artifact=None,
            actions=[
                _action_payload("confirm", enabled=True, disabled_reason_code=None),
                _action_payload("edit", enabled=True, disabled_reason_code=None),
                _action_payload("cancel", enabled=True, disabled_reason_code=None),
            ],
            requires_human_review=False,
            critic_confidence=0.86,
            sandbox_status="succeeded",
            validation_errors=[],
        )


def test_model_preview_schema_rejects_ready_confirm_with_disabled_reason() -> None:
    with pytest.raises(ValidationError):
        ModelPreview(
            preview_id="mpv_0123456789abcdef",
            status="ready_to_confirm",
            source="chat_model_preview_internal_beta",
            task_type="lp",
            variables={"decision_variables": ["x"]},
            objective={"sense": "minimize"},
            constraints={"linear": []},
            code_artifact=_generated_coder_preview().artifact,
            actions=[
                _action_payload("confirm", enabled=True, disabled_reason_code="model_not_ready"),
                _action_payload("edit", enabled=True, disabled_reason_code=None),
                _action_payload("cancel", enabled=True, disabled_reason_code=None),
            ],
            requires_human_review=False,
            critic_confidence=0.86,
            sandbox_status="succeeded",
            validation_errors=[],
        )


def _action_payload(
    kind: str,
    *,
    enabled: bool,
    disabled_reason_code: str | None,
) -> dict[str, object]:
    labels = {
        "confirm": ("确认模型", "Confirm model", "chat.model_preview.confirm"),
        "edit": ("编辑模型", "Edit model", "chat.model_preview.edit"),
        "cancel": ("取消", "Cancel", "chat.model_preview.cancel"),
    }[kind]
    return {
        "kind": kind,
        "label_zh": labels[0],
        "label_en": labels[1],
        "enabled": enabled,
        "client_action": labels[2],
        "disabled_reason_code": disabled_reason_code,
    }


def _extracted_formulator_preview() -> FormulatorPreview:
    return FormulatorPreview(
        status="extracted",
        source="llm_formulator_internal_beta",
        task_type="lp",
        confidence=0.84,
        variables={"decision_variables": ["x", "y"]},
        objective={"sense": "minimize", "coefficients": {"x": 2, "y": 3}},
        constraints={"linear": [{"expression": "x + y <= 10"}]},
        validation_errors=[],
        supported_task_types=SUPPORTED_TASK_TYPES,
    )


def _needs_clarification_formulator_preview() -> FormulatorPreview:
    return FormulatorPreview(
        status="needs_clarification",
        source="heuristic_formulator_internal_beta",
        task_type="lp",
        confidence=0.35,
        variables={},
        objective={},
        constraints={},
        validation_errors=[
            {
                "field_path": "variables",
                "message": "structured variables are required",
                "remediation_hint_key": "chat.formulator.variables_required",
            }
        ],
        supported_task_types=SUPPORTED_TASK_TYPES,
    )


def _generated_coder_preview(*, task_type: str = "lp") -> CoderPreview:
    return CoderPreview(
        status="generated",
        source="llm_coder_internal_beta",
        task_type=task_type,  # type: ignore[arg-type]
        artifact=CoderCodeArtifact(
            language="python",
            code=_lp_code(task_type=task_type),
            entrypoint="build_payload",
            input_model="LpInput",
            output_model="LpPayload",
            imports=["pydantic"],
        ),
        validation_errors=[],
        supported_task_types=SUPPORTED_TASK_TYPES,
    )


def _lp_code(*, task_type: str = "lp") -> str:
    return f"""
from pydantic import BaseModel


class LpInput(BaseModel):
    coefficients: dict[str, float]
    constraints: list[str]


class LpPayload(BaseModel):
    task_type: str


def build_payload(data: LpInput) -> LpPayload:
    return LpPayload(task_type="{task_type}")
""".strip()


def _validated_critic_preview(*, task_type: str = "lp") -> CriticPreview:
    return CriticPreview(
        status="validated",
        source="llm_critic_internal_beta",
        task_type=task_type,  # type: ignore[arg-type]
        confidence=0.86,
        reasoning="Critic validated schema, safety, and business-logic consistency.",
        checks=_passing_checks(),
        validation_errors=[],
        supported_task_types=SUPPORTED_TASK_TYPES,
        calibration_threshold=0.6,
        threshold_source="apps/critic-service/config/critic-calibration.json",
    )


def _skipped_critic_preview(*, task_type: str) -> CriticPreview:
    return CriticPreview(
        status="skipped",
        source="heuristic_critic_internal_beta",
        task_type=task_type,  # type: ignore[arg-type]
        confidence=0.0,
        reasoning="Critic skipped because no generated code artifact is available.",
        checks={
            "schema": {
                "passed": False,
                "message": "generated code artifact is required before critic validation",
                "field_path": "coder_preview.artifact",
            },
            "safety": {
                "passed": False,
                "message": "generated code artifact is required before safety validation",
                "field_path": "coder_preview.artifact",
            },
            "business_logic": {
                "passed": False,
                "message": "generated code artifact is required before business validation",
                "field_path": "coder_preview.artifact",
            },
        },
        validation_errors=[],
        supported_task_types=SUPPORTED_TASK_TYPES,
        calibration_threshold=0.6,
        threshold_source="apps/critic-service/config/critic-calibration.json",
    )


def _succeeded_sandbox_preview(*, task_type: str = "lp") -> SandboxPreview:
    return SandboxPreview(
        status="succeeded",
        source="sandbox_runner_local_contract_internal_beta",
        task_type=task_type,  # type: ignore[arg-type]
        stdout_excerpt="ready\n",
        stderr_excerpt="",
        exit_code=0,
        result_files=[
            {
                "path": "reports/output.json",
                "size_bytes": 2,
                "sha256": hashlib.sha256(b"{}").hexdigest(),
            }
        ],
        error_code=None,
        limits=_sandbox_limits(),
        validation_errors=[],
        contract_version="sandbox-runner-p58-p62-local-v1",
    )


def _skipped_sandbox_preview(*, task_type: str) -> SandboxPreview:
    return SandboxPreview(
        status="skipped",
        source="heuristic_sandbox_internal_beta",
        task_type=task_type,  # type: ignore[arg-type]
        stdout_excerpt="",
        stderr_excerpt="",
        exit_code=None,
        result_files=[],
        error_code=None,
        limits=_sandbox_limits(),
        validation_errors=[],
        contract_version="sandbox-runner-p58-p62-local-v1",
    )


def _policy_blocked_sandbox_preview() -> SandboxPreview:
    return SandboxPreview(
        status="policy_blocked",
        source="sandbox_runner_local_contract_internal_beta",
        task_type="lp",
        stdout_excerpt="",
        stderr_excerpt="network disabled",
        exit_code=None,
        result_files=[],
        error_code="network_disabled",
        limits=_sandbox_limits(),
        validation_errors=[],
        contract_version="sandbox-runner-p58-p62-local-v1",
    )


def _not_escalated_human_review(*, task_type: str = "lp") -> HumanReviewPreview:
    return HumanReviewPreview(
        escalated=False,
        source="heuristic_human_review_internal_beta",
        queue="events.critic",
        event_type="critic.review.escalated",
        review_id="hrv_0123456789abcdef01234567",
        reason_code="not_escalated",
        critic_confidence=0.86,
        calibration_threshold=0.6,
        threshold_source="apps/critic-service/config/critic-calibration.json",
        user_notice=None,
        validation_errors=[],
    )


def _escalated_human_review(*, confidence: float) -> HumanReviewPreview:
    return HumanReviewPreview(
        escalated=True,
        source="critic_threshold_internal_beta",
        queue="events.critic",
        event_type="critic.review.escalated",
        review_id="hrv_0123456789abcdef01234567",
        reason_code="critic_skipped_below_threshold",
        critic_confidence=confidence,
        calibration_threshold=0.6,
        threshold_source="apps/critic-service/config/critic-calibration.json",
        user_notice={
            "zh": "AI 不确定，已转人工复核。",
            "en": "AI is uncertain; this has been routed for human review.",
        },
        validation_errors=[],
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
