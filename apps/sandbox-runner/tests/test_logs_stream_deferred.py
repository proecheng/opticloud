from __future__ import annotations

from fastapi.testclient import TestClient
from sandbox_runner.main import app
from sandbox_runner.policy import validate_request_policy
from sandbox_runner.schemas import (
    SandboxErrorCode,
    SandboxExecutionRequest,
    SandboxInputFile,
    SandboxPolicyError,
)

client = TestClient(app)


def test_allow_logs_stream_true_is_rejected_before_executor() -> None:
    request = SandboxExecutionRequest(
        code="stdout:secret log line\nstderr:Traceback /tmp/secret\nexit:0",
        allow_logs_stream=True,
    )

    try:
        validate_request_policy(request)
    except SandboxPolicyError as exc:
        assert exc.error_code == SandboxErrorCode.LOGS_STREAM_DEFERRED
        assert exc.executor_invoked is False
        assert "v1.5" in exc.message
        assert "secret log line" not in exc.message
        assert "Traceback" not in exc.message
    else:  # pragma: no cover - RED guard
        raise AssertionError("allow_logs_stream=true must be rejected")


def test_execute_allow_logs_stream_true_returns_stable_no_leak_422() -> None:
    response = client.post(
        "/v1/sandbox/execute",
        json={
            "code": "stdout:secret log line\nstderr:Traceback /tmp/secret\nexit:0",
            "stdin": "token=sk-test-secret",
            "allow_logs_stream": True,
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == {
        "error_code": "logs_stream_deferred",
        "message": (
            "Sandbox logs streaming is reserved for v1.5+ and is not available in "
            "the current internal beta contract."
        ),
        "executor_invoked": False,
    }
    assert "secret log line" not in str(body)
    assert "Traceback" not in str(body)
    assert "sk-test-secret" not in str(body)


def test_allow_logs_stream_error_takes_precedence_over_other_policy_errors() -> None:
    request = SandboxExecutionRequest(
        code="import requests\nstdout:secret log line",
        input_files=[SandboxInputFile(path="../host-secret.txt", content="token=secret")],
        allow_logs_stream=True,
    )

    try:
        validate_request_policy(request)
    except SandboxPolicyError as exc:
        assert exc.error_code == SandboxErrorCode.LOGS_STREAM_DEFERRED
        assert exc.executor_invoked is False
        assert "host-secret" not in exc.message
        assert "token=secret" not in exc.message
    else:  # pragma: no cover - RED guard
        raise AssertionError("allow_logs_stream=true must keep a stable deferred error")


def test_execute_default_logs_stream_false_keeps_sync_stdout_contract() -> None:
    response = client.post(
        "/v1/sandbox/execute",
        json={"code": "stdout:hello\nstderr:diagnostic\nexit:0"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["stdout"] == "hello\n"
    assert body["stderr"] == "diagnostic\n"
    assert body["exit_code"] == 0


def test_sandbox_stream_routes_remain_absent() -> None:
    stream_response = client.post(
        "/v1/sandbox/stream",
        json={"code": "stdout:hello", "allow_logs_stream": True},
    )
    logs_response = client.post(
        "/v1/sandbox/logs",
        json={"code": "stdout:hello", "allow_logs_stream": True},
    )

    assert stream_response.status_code == 404
    assert logs_response.status_code == 404
