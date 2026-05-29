from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

from sandbox_runner.schemas import (
    SandboxErrorCode,
    SandboxExecutionRequest,
    SandboxPolicyError,
)

NETWORK_PATTERNS = (
    "import requests",
    "from requests",
    "urllib.",
    "import urllib",
    "from urllib",
    "import httpx",
    "from httpx",
    "socket.",
    "import socket",
    "from socket",
)

LLM_SELF_LOOP_PATTERNS = (
    "api.openai.com",
    "openai",
    "anthropic",
    "deepseek",
    "qwen",
    "dashscope",
    "call an llm",
    "call llm",
    "ask the llm",
    "invoke llm",
    "language model",
)


def validate_request_policy(request: SandboxExecutionRequest) -> None:
    if request.allow_logs_stream:
        raise SandboxPolicyError(
            SandboxErrorCode.LOGS_STREAM_DEFERRED,
            (
                "Sandbox logs streaming is reserved for v1.5+ and is not available in "
                "the current internal beta contract."
            ),
            executor_invoked=False,
        )

    validate_input_paths(request)
    combined = f"{request.code}\n{request.stdin}".lower()

    if any(pattern in combined for pattern in NETWORK_PATTERNS):
        raise SandboxPolicyError(
            SandboxErrorCode.NETWORK_DISABLED,
            "Sandbox network access is disabled by policy.",
            executor_invoked=False,
        )

    if any(pattern in combined for pattern in LLM_SELF_LOOP_PATTERNS):
        raise SandboxPolicyError(
            SandboxErrorCode.LLM_SELF_LOOP_BLOCKED,
            "Sandbox input must not instruct execution to call an LLM.",
            executor_invoked=False,
        )


def validate_input_paths(request: SandboxExecutionRequest) -> None:
    for input_file in request.input_files:
        if _unsafe_path(input_file.path):
            raise SandboxPolicyError(
                SandboxErrorCode.INVALID_INPUT_PATH,
                "Input file paths must be relative and stay within the sandbox input root.",
                executor_invoked=False,
            )


def validate_result_file(path: str, content: str, budget_bytes: int) -> None:
    if _unsafe_path(path):
        raise SandboxPolicyError(
            SandboxErrorCode.INVALID_INPUT_PATH,
            "Result file paths must be relative and stay within the sandbox result root.",
            executor_invoked=True,
        )
    if len(content.encode("utf-8")) > budget_bytes:
        raise SandboxPolicyError(
            SandboxErrorCode.RESULT_BUDGET_EXCEEDED,
            "Result file exceeds the configured sandbox result-file budget.",
            executor_invoked=True,
        )


def _unsafe_path(path: str) -> bool:
    posix_path = PurePosixPath(path)
    windows_path = PureWindowsPath(path)
    parts = posix_path.parts
    return (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or ".." in parts
        or path.strip() == ""
    )
