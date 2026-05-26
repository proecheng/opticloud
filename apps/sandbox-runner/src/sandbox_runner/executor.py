from __future__ import annotations

import hashlib

from sandbox_runner.policy import validate_result_file
from sandbox_runner.schemas import (
    SandboxExecutionRequest,
    SandboxExecutionResponse,
    SandboxResultFile,
    SandboxStatus,
)


def execute_local_contract(request: SandboxExecutionRequest) -> SandboxExecutionResponse:
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    exit_code = 0
    result_files: list[SandboxResultFile] = []

    for raw_line in request.code.splitlines():
        line = raw_line.strip()
        if line.startswith("stdout:"):
            stdout_parts.append(line.removeprefix("stdout:") + "\n")
        elif line.startswith("stderr:"):
            stderr_parts.append(line.removeprefix("stderr:") + "\n")
        elif line.startswith("exit:"):
            exit_code = _parse_exit_code(line.removeprefix("exit:"))
            if exit_code == 1 and line.removeprefix("exit:") != "1":
                stderr_parts.append("invalid exit code directive\n")
        elif line.startswith("result:"):
            result_files.append(_parse_result_file(line, request.limits.result_file_budget_bytes))

    return SandboxExecutionResponse(
        status=SandboxStatus.SUCCEEDED if exit_code == 0 else SandboxStatus.FAILED,
        stdout="".join(stdout_parts),
        stderr="".join(stderr_parts),
        exit_code=exit_code,
        result_files=result_files,
    )


def _parse_exit_code(raw_exit_code: str) -> int:
    try:
        parsed = int(raw_exit_code)
    except ValueError:
        return 1
    if parsed < 0 or parsed > 255:
        return 1
    return parsed


def _parse_result_file(line: str, budget_bytes: int) -> SandboxResultFile:
    payload = line.removeprefix("result:")
    path, separator, content = payload.partition("=")
    if separator != "=":
        content = ""
    validate_result_file(path, content, budget_bytes)
    content_bytes = content.encode("utf-8")
    return SandboxResultFile(
        path=path,
        size_bytes=len(content_bytes),
        sha256=hashlib.sha256(content_bytes).hexdigest(),
    )
