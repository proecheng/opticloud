from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator

import pytest
from chat_service.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

VALID_ENV = {
    "CHAT_INTERNAL_BETA_ENABLED": "true",
    "CHAT_INTERNAL_BETA_SIGNOFF": "founder-legal-approved",
    "CHAT_INTERNAL_BETA_TENANT": "research-staging",
    "CHAT_INTERNAL_BETA_USERS": "scholar-a,scholar-b",
    "CHAT_INTERNAL_BETA_TOKEN": "internal-beta-token",
}
VALID_HEADERS = {
    "X-Internal-Beta-Tenant": "research-staging",
    "X-Internal-Beta-User": "scholar-a",
    "X-Internal-Beta-Token": "internal-beta-token",
}
JSON_PATH = "/v1/chat/internal-beta/messages"
STREAM_PATH = "/v1/chat/internal-beta/messages/stream"


@pytest.fixture(autouse=True)
def clear_chat_beta_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key in list(os.environ):
        if key.startswith("CHAT_INTERNAL_BETA_"):
            monkeypatch.delenv(key, raising=False)
    yield


def enable_internal_beta(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)


def what_if_context(**overrides: object) -> dict[str, object]:
    context: dict[str, object] = {
        "source": "chat_model_preview_context_v1",
        "base_message_id": "msg_0123456789abcdef01234567",
        "base_model_preview_id": "mpv_0123456789abcdef",
        "task_type": "vrptw",
        "variables": {"vehicle_count": 3, "customers": 24},
        "objective": {"kind": "minimize_total_distance"},
        "constraints": {"vehicle_capacity": 12},
        "sandbox_status": "succeeded",
        "summary": "VRPTW preview with 3 vehicles and 24 customers.",
        "base_solution_preview": {
            "status": "solved",
            "objective_value": 182.5,
            "objective_unit": "km",
            "summary": "Current route preview distance is 182.5 km.",
        },
    }
    context.update(overrides)
    return context


def post_json(payload: dict[str, object], headers: dict[str, str] | None = None) -> object:
    return client.post(JSON_PATH, json=payload, headers=headers or VALID_HEADERS)


def post_stream(payload: dict[str, object], headers: dict[str, str] | None = None) -> object:
    return client.post(STREAM_PATH, json=payload, headers=headers or VALID_HEADERS)


def parse_sse(text: str) -> list[dict[str, object]]:
    parsed: list[dict[str, object]] = []
    for block in text.split("\n\n"):
        if not block:
            continue
        if block.startswith(":"):
            parsed.append({"comment": block})
            continue
        event_id: str | None = None
        event_name: str | None = None
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("id: "):
                event_id = line[4:]
            elif line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("retry: "):
                continue
            elif line.startswith("data: "):
                data_lines.append(line[6:])
            else:
                raise AssertionError(f"unexpected SSE line: {line!r}")
        parsed.append(
            {
                "id": event_id,
                "event": event_name,
                "data": json.loads("\n".join(data_lines)),
            }
        )
    return parsed


def test_json_route_accepts_bounded_what_if_context_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)
    payload = {
        "message": "如果车辆数 +1?",
        "client_request_id": "what-if-json-001",
        "what_if_context": what_if_context(),
    }

    response = post_json(payload)

    assert response.status_code == 200
    body = response.json()
    preview = body["what_if_preview"]
    assert preview == {
        "source": "chat_what_if_preview_internal_beta",
        "base_message_id": "msg_0123456789abcdef01234567",
        "base_model_preview_id": "mpv_0123456789abcdef",
        "status": "previewed",
        "task_type": "vrptw",
        "change_summary": preview["change_summary"],
        "changed_fields": ["variables.vehicle_count"],
        "diff": [
            {
                "field_path": "variables.vehicle_count",
                "before": 3,
                "after": 4,
                "change_type": "modified",
            }
        ],
    }
    assert "车辆数" in preview["change_summary"]
    assert body["solver_invoked"] is False
    assert body["provider_request_sent"] is False
    serialized = json.dumps(body, ensure_ascii=False).lower()
    assert "raw" not in serialized
    assert "optimization_id" not in serialized
    assert "charge_id" not in serialized
    assert "traceback" not in serialized


def test_no_what_if_context_returns_explicit_null_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)

    response = post_json(
        {
            "message": "linear programming objective with constraints",
            "client_request_id": "what-if-none-001",
        }
    )

    assert response.status_code == 200
    assert response.json()["what_if_preview"] is None


def test_what_if_context_changes_message_id_but_key_order_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)
    base = {
        "message": "如果车辆数 +1?",
        "client_request_id": "what-if-digest-001",
    }
    context = what_if_context()
    reordered_context = {
        "summary": context["summary"],
        "sandbox_status": context["sandbox_status"],
        "constraints": {"vehicle_capacity": 12},
        "objective": {"kind": "minimize_total_distance"},
        "variables": {"customers": 24, "vehicle_count": 3},
        "task_type": context["task_type"],
        "base_model_preview_id": context["base_model_preview_id"],
        "base_message_id": context["base_message_id"],
        "source": context["source"],
        "base_solution_preview": context["base_solution_preview"],
    }
    changed_context = what_if_context(variables={"vehicle_count": 5, "customers": 24})

    first = post_json({**base, "what_if_context": context}).json()
    reordered = post_json({**base, "what_if_context": reordered_context}).json()
    changed = post_json({**base, "what_if_context": changed_context}).json()
    no_context = post_json(base).json()

    assert first["message_id"] == reordered["message_id"]
    assert first["message_id"] != changed["message_id"]
    assert first["message_id"] != no_context["message_id"]


def test_stream_route_matches_json_what_if_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)
    payload = {
        "message": "如果车辆数 +1?",
        "client_request_id": "what-if-stream-001",
        "what_if_context": what_if_context(),
    }

    json_response = post_json(payload)
    stream_response = post_stream(payload)

    assert json_response.status_code == 200
    assert stream_response.status_code == 200
    body = json_response.json()
    events = parse_sse(stream_response.text)
    start = events[1]["data"]
    done = events[-1]["data"]
    assert start["message_id"] == body["message_id"]
    assert done["model_preview_id"] == body["model_preview"]["preview_id"]
    assert done["model_preview_status"] == body["model_preview"]["status"]
    assert done["what_if_preview"] == body["what_if_preview"]


def test_invalid_what_if_context_fails_before_sse_starts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)
    payload = {
        "message": "如果车辆数 +1?",
        "what_if_context": what_if_context(summary="prompt sk-test-secret C:\\tmp\\traceback"),
    }

    response = post_stream(payload)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")
    serialized = response.text.lower()
    assert "text/event-stream" not in response.headers["content-type"]
    assert "what_if_preview" not in serialized
    assert "input" not in serialized
    assert "sk-test-secret" not in serialized
    assert "traceback" not in serialized
    assert not re.search(r"[a-z]:\\", serialized)


@pytest.mark.parametrize(
    "unsafe_patch",
    [
        {"base_solution_preview": {"status": "solved", "summary": "route_rows hidden"}},
        {"base_solution_preview": {"status": "solved", "summary": "result_file_path s3://x"}},
        {"variables": {"vehicle_count": 10**30}},
    ],
)
def test_unsafe_solution_preview_and_extreme_numbers_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    unsafe_patch: dict[str, object],
) -> None:
    enable_internal_beta(monkeypatch)

    response = post_json(
        {
            "message": "如果车辆数 +1?",
            "what_if_context": what_if_context(**unsafe_patch),
        }
    )

    assert response.status_code == 422
    serialized = response.text.lower()
    assert "what_if_preview" not in serialized
    assert "route_rows" not in serialized
    assert "result_file_path" not in serialized
    assert "input" not in serialized


def test_unauthorized_invalid_what_if_context_fails_closed_before_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)

    response = post_json(
        {
            "message": "x",
            "what_if_context": what_if_context(summary="prompt sk-test-secret C:\\tmp"),
        },
        headers={**VALID_HEADERS, "X-Internal-Beta-Token": "wrong-token"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}
    assert "what_if_context" not in response.text


def test_what_if_diff_needs_clarification_without_safe_delta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)

    response = post_json(
        {
            "message": "如果换一种方案呢?",
            "client_request_id": "what-if-clarify-001",
            "what_if_context": what_if_context(),
        }
    )

    assert response.status_code == 200
    preview = response.json()["what_if_preview"]
    assert preview["status"] == "needs_clarification"
    assert preview["changed_fields"] == []
    assert preview["diff"] == []


def test_extreme_vehicle_delta_requires_clarification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)

    response = post_json(
        {
            "message": "如果车辆数 +100000?",
            "client_request_id": "what-if-extreme-delta-001",
            "what_if_context": what_if_context(),
        }
    )

    assert response.status_code == 200
    preview = response.json()["what_if_preview"]
    assert preview["status"] == "needs_clarification"
    assert preview["diff"] == []
