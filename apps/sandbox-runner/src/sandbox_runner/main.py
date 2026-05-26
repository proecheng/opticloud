from __future__ import annotations

from fastapi import FastAPI, HTTPException

from sandbox_runner.executor import execute_local_contract
from sandbox_runner.policy import validate_request_policy
from sandbox_runner.schemas import (
    SandboxExecutionRequest,
    SandboxExecutionResponse,
    SandboxPolicyError,
)

app = FastAPI(title="OptiCloud Sandbox Runner", version="0.0.1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "sandbox-runner"}


@app.post("/v1/sandbox/execute", response_model=SandboxExecutionResponse)
def execute(request: SandboxExecutionRequest) -> SandboxExecutionResponse:
    try:
        validate_request_policy(request)
        return execute_local_contract(request)
    except SandboxPolicyError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": exc.error_code.value,
                "message": exc.message,
                "executor_invoked": exc.executor_invoked,
            },
        ) from exc
