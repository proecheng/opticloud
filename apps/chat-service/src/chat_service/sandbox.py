from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from sandbox_runner.executor import execute_local_contract
from sandbox_runner.policy import validate_request_policy
from sandbox_runner.schemas import (
    SandboxErrorCode,
    SandboxExecutionRequest,
    SandboxLimits,
    SandboxPolicyError,
    SandboxStatus,
)

from chat_service.schemas import (
    CoderPreview,
    CriticPreview,
    SandboxLimitsPreview,
    SandboxPreview,
    SandboxResultFilePreview,
    SandboxValidationError,
    TaskType,
)

SANDBOX_CONTRACT_VERSION: Literal["sandbox-runner-p58-p62-local-v1"] = (
    "sandbox-runner-p58-p62-local-v1"
)
SANDBOX_RESULT_FILE_BUDGET_BYTES: Literal[104857600] = 104857600
SANDBOX_STDIO_EXCERPT_MAX_CHARS = 512

_SECRET_OR_RAW_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{4,}|api[_-]?key|bearer\s+[A-Za-z0-9._-]+|authorization|"
    r"cookie|password|token|raw_response|raw_request|provider_request|provider_response|"
    r"deterministic_digest)",
    re.IGNORECASE,
)
_TRACEBACK_PATTERN = re.compile(r"traceback\s*\(most recent call last\):.*", re.IGNORECASE)
_HOST_PATH_PATTERN = re.compile(
    r"([A-Za-z]:\\[^\s]+|/(?:tmp|var|etc|home|root|mnt|proc|sys|dev)/[^\s]+)"
)


@dataclass(frozen=True)
class SandboxRouteResult:
    preview: SandboxPreview
    sandbox_invoked: bool


def generate_sandbox_preview(
    *,
    coder_preview: CoderPreview,
    critic_preview: CriticPreview,
) -> SandboxRouteResult:
    limits = _sandbox_limits_preview()
    skip_error = _skip_reason(coder_preview, critic_preview)
    if skip_error is not None:
        return SandboxRouteResult(
            preview=_skipped_preview(
                coder_preview.task_type,
                limits=limits,
                error=skip_error,
            ),
            sandbox_invoked=False,
        )

    artifact = coder_preview.artifact
    if artifact is None:
        return SandboxRouteResult(
            preview=_skipped_preview(
                coder_preview.task_type,
                limits=limits,
                error=SandboxValidationError(
                    field_path="coder_preview.artifact",
                    message="generated code artifact is required before sandbox execution",
                    remediation_hint_key="chat.sandbox.artifact_required",
                ),
            ),
            sandbox_invoked=False,
        )
    request = SandboxExecutionRequest(
        code=artifact.code,
        stdin="",
        input_files=[],
        limits=SandboxLimits(),
    )

    try:
        validate_request_policy(request)
    except SandboxPolicyError as exc:
        return SandboxRouteResult(
            preview=_policy_blocked_preview(
                coder_preview.task_type,
                limits=limits,
                error_code=exc.error_code,
                message=exc.message,
            ),
            sandbox_invoked=True,
        )

    try:
        response = execute_local_contract(request)
    except SandboxPolicyError as exc:
        return SandboxRouteResult(
            preview=_policy_blocked_preview(
                coder_preview.task_type,
                limits=limits,
                error_code=exc.error_code,
                message=exc.message,
            ),
            sandbox_invoked=True,
        )

    return SandboxRouteResult(
        preview=SandboxPreview(
            status="succeeded" if response.status == SandboxStatus.SUCCEEDED else "failed",
            source="sandbox_runner_local_contract_internal_beta",
            task_type=coder_preview.task_type,
            stdout_excerpt=_safe_stdio_excerpt(response.stdout),
            stderr_excerpt=_safe_stdio_excerpt(response.stderr),
            exit_code=response.exit_code,
            result_files=[
                SandboxResultFilePreview(
                    path=result_file.path,
                    size_bytes=result_file.size_bytes,
                    sha256=result_file.sha256,
                )
                for result_file in response.result_files
            ],
            error_code=None,
            limits=limits,
            validation_errors=[],
            contract_version=SANDBOX_CONTRACT_VERSION,
        ),
        sandbox_invoked=True,
    )


def _skip_reason(
    coder_preview: CoderPreview,
    critic_preview: CriticPreview,
) -> SandboxValidationError | None:
    if coder_preview.task_type == "unknown":
        return SandboxValidationError(
            field_path="coder_preview.task_type",
            message="known task_type is required before sandbox execution",
            remediation_hint_key="chat.sandbox.task_type_required",
        )
    if coder_preview.status != "generated" or coder_preview.artifact is None:
        return SandboxValidationError(
            field_path="coder_preview.artifact",
            message="generated code artifact is required before sandbox execution",
            remediation_hint_key="chat.sandbox.artifact_required",
        )
    if critic_preview.status != "validated":
        return SandboxValidationError(
            field_path="critic_preview.status",
            message="validated critic preview is required before sandbox execution",
            remediation_hint_key="chat.sandbox.critic_validated_required",
        )
    if not all(check.passed for check in critic_preview.checks.values()):
        return SandboxValidationError(
            field_path="critic_preview.checks",
            message="all critic checks must pass before sandbox execution",
            remediation_hint_key="chat.sandbox.critic_checks_required",
        )
    return None


def _skipped_preview(
    task_type: TaskType,
    *,
    limits: SandboxLimitsPreview,
    error: SandboxValidationError,
) -> SandboxPreview:
    return SandboxPreview(
        status="skipped",
        source="heuristic_sandbox_internal_beta",
        task_type=task_type,
        stdout_excerpt="",
        stderr_excerpt="",
        exit_code=None,
        result_files=[],
        error_code=None,
        limits=limits,
        validation_errors=[error],
        contract_version=SANDBOX_CONTRACT_VERSION,
    )


def _policy_blocked_preview(
    task_type: TaskType,
    *,
    limits: SandboxLimitsPreview,
    error_code: SandboxErrorCode,
    message: str,
) -> SandboxPreview:
    return SandboxPreview(
        status="policy_blocked",
        source="sandbox_runner_local_contract_internal_beta",
        task_type=task_type,
        stdout_excerpt="",
        stderr_excerpt=_safe_stdio_excerpt(message),
        exit_code=None,
        result_files=[],
        error_code=error_code.value,
        limits=limits,
        validation_errors=[
            SandboxValidationError(
                field_path="sandbox_runner.policy",
                message=_bounded_message(message),
                remediation_hint_key=f"chat.sandbox.{error_code.value}",
            )
        ],
        contract_version=SANDBOX_CONTRACT_VERSION,
    )


def _sandbox_limits_preview() -> SandboxLimitsPreview:
    return SandboxLimitsPreview(
        cpu_vcpu=1,
        memory_mb=1024,
        soft_timeout_seconds=30,
        hard_timeout_seconds=90,
        network_disabled=True,
        read_only_filesystem=True,
        result_file_budget_bytes=SANDBOX_RESULT_FILE_BUDGET_BYTES,
    )


def _safe_stdio_excerpt(value: str) -> str:
    excerpt = value[:SANDBOX_STDIO_EXCERPT_MAX_CHARS]
    excerpt = _TRACEBACK_PATTERN.sub("[redacted]", excerpt)
    excerpt = _HOST_PATH_PATTERN.sub("[redacted-path]", excerpt)
    excerpt = _SECRET_OR_RAW_PATTERN.sub("[redacted]", excerpt)
    return excerpt[:SANDBOX_STDIO_EXCERPT_MAX_CHARS]


def _bounded_message(value: str) -> str:
    sanitized = _safe_stdio_excerpt(value).strip()
    return sanitized[:160] or "sandbox policy blocked execution"
