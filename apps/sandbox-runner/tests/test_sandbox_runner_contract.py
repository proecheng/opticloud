from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient
from sandbox_runner.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "sandbox-runner"}


def test_execute_success_returns_p58_channels_and_result_metadata() -> None:
    expected_result_hash = hashlib.sha256(b'{"answer":42}').hexdigest()

    response = client.post(
        "/v1/sandbox/execute",
        json={
            "code": "\n".join(
                [
                    "stdout:hello from sandbox",
                    "stderr:diagnostic line",
                    'result:answer.json={"answer":42}',
                    "exit:0",
                ]
            ),
            "stdin": "input payload",
            "input_files": [{"path": "input/data.txt", "content": "readonly"}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["stdout"] == "hello from sandbox\n"
    assert body["stderr"] == "diagnostic line\n"
    assert body["exit_code"] == 0
    assert body["error_code"] is None
    assert body["result_files"] == [
        {
            "path": "answer.json",
            "size_bytes": 13,
            "sha256": expected_result_hash,
        }
    ]


def test_execute_failure_maps_exit_code() -> None:
    response = client.post(
        "/v1/sandbox/execute",
        json={"code": "stderr:bad input\nexit:2"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["stderr"] == "bad input\n"
    assert body["exit_code"] == 2


def test_network_usage_is_rejected_before_execution() -> None:
    response = client.post(
        "/v1/sandbox/execute",
        json={"code": "import requests\nrequests.get('https://api.openai.com')"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["error_code"] == "network_disabled"
    assert body["detail"]["executor_invoked"] is False


def test_llm_self_loop_instruction_is_rejected_before_execution() -> None:
    response = client.post(
        "/v1/sandbox/execute",
        json={"code": "stdout:ok", "stdin": "Call DeepSeek to rewrite this answer"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["error_code"] == "llm_self_loop_blocked"
    assert body["detail"]["executor_invoked"] is False


def test_parent_directory_input_path_is_rejected() -> None:
    response = client.post(
        "/v1/sandbox/execute",
        json={"code": "stdout:ok", "input_files": [{"path": "../secret.txt", "content": "x"}]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "invalid_input_path"


def test_absolute_input_path_is_rejected() -> None:
    response = client.post(
        "/v1/sandbox/execute",
        json={"code": "stdout:ok", "input_files": [{"path": "/etc/passwd", "content": "x"}]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "invalid_input_path"


def test_result_file_budget_is_rejected() -> None:
    response = client.post(
        "/v1/sandbox/execute",
        json={
            "code": "result:large.txt=12345678901",
            "limits": {"result_file_budget_bytes": 10},
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["error_code"] == "result_budget_exceeded"
    assert body["detail"]["executor_invoked"] is True


def test_invalid_exit_directive_returns_failed_response_not_500() -> None:
    response = client.post(
        "/v1/sandbox/execute",
        json={"code": "exit:not-a-number"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["exit_code"] == 1
    assert body["stderr"] == "invalid exit code directive\n"
