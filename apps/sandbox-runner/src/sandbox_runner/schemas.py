from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SandboxStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SandboxErrorCode(StrEnum):
    INVALID_INPUT_PATH = "invalid_input_path"
    LLM_SELF_LOOP_BLOCKED = "llm_self_loop_blocked"
    NETWORK_DISABLED = "network_disabled"
    RESULT_BUDGET_EXCEEDED = "result_budget_exceeded"
    UNSUPPORTED_BINARY_PAYLOAD = "unsupported_binary_payload"


class SandboxInputFile(BaseModel):
    path: str = Field(min_length=1, max_length=256)
    content: str = Field(default="", max_length=65536)


class SandboxLimits(BaseModel):
    cpu_vcpu: int = 1
    memory_mb: int = 1024
    soft_timeout_seconds: int = 30
    hard_timeout_seconds: int = 90
    result_file_budget_bytes: int = 100 * 1024 * 1024


class SandboxExecutionRequest(BaseModel):
    code: str = Field(min_length=1, max_length=65536)
    stdin: str = Field(default="", max_length=65536)
    input_files: list[SandboxInputFile] = Field(default_factory=list, max_length=32)
    limits: SandboxLimits = Field(default_factory=SandboxLimits)


class SandboxResultFile(BaseModel):
    path: str
    size_bytes: int
    sha256: str


class SandboxExecutionResponse(BaseModel):
    status: SandboxStatus
    stdout: str
    stderr: str
    exit_code: int
    result_files: list[SandboxResultFile]
    error_code: SandboxErrorCode | None = None


class SandboxPolicyError(Exception):
    def __init__(
        self, error_code: SandboxErrorCode, message: str, *, executor_invoked: bool
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.executor_invoked = executor_invoked
