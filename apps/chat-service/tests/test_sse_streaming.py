from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator

import pytest
from chat_service.main import app
from chat_service.streaming import (
    COUNT_UNIT_METHOD,
    build_stream_events,
    content_token_units,
    format_sse_event,
    split_content_chunks,
    strip_zero_width_metadata,
)
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
STREAM_PATH = "/v1/chat/internal-beta/messages/stream"
JSON_PATH = "/v1/chat/internal-beta/messages"
SSE_ID_PATTERN = re.compile(r"^sse_[0-9a-f]{16}_[0-9]{6}$")


@pytest.fixture(autouse=True)
def clear_chat_beta_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key in list(os.environ):
        if key.startswith("CHAT_INTERNAL_BETA_"):
            monkeypatch.delenv(key, raising=False)
    yield


def enable_internal_beta(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    values = {**VALID_ENV, **overrides}
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def post_stream(
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> object:
    return client.post(
        STREAM_PATH,
        json=payload or {"message": "求最短路径，把车辆路线排出来"},
        headers=headers or VALID_HEADERS,
    )


def post_json(payload: dict[str, object] | None = None) -> object:
    return client.post(
        JSON_PATH,
        json=payload or {"message": "求最短路径，把车辆路线排出来"},
        headers=VALID_HEADERS,
    )


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
        retry: int | None = None
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("id: "):
                event_id = line[4:]
            elif line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("retry: "):
                retry = int(line[7:])
            elif line.startswith("data: "):
                data_lines.append(line[6:])
            else:
                raise AssertionError(f"unexpected SSE line: {line!r}")
        payload = json.loads("\n".join(data_lines))
        parsed.append({"id": event_id, "event": event_name, "retry": retry, "data": payload})
    return parsed


def test_authorized_stream_returns_sse_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    enable_internal_beta(monkeypatch)

    response = post_stream({"message": "求最短路径，把车辆路线排出来"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    events = parse_sse(response.text)
    assert events[0] == {"comment": ":heartbeat"}
    assert [event.get("event") for event in events[1:]] == [
        "message_start",
        "content_delta",
        "done",
    ]
    for event in events[1:]:
        assert isinstance(event["id"], str)
        assert SSE_ID_PATTERN.fullmatch(event["id"])
        assert event["retry"] == 3000

    start = events[1]["data"]
    assert start["mode"] == "internal_beta"
    assert start["public_access"] is False
    assert start["max_chunk_token_units"] == 100
    assert start["token_count_method"] == COUNT_UNIT_METHOD

    delta = events[2]["data"]
    assert delta["chunk"]
    assert 1 <= delta["token_units"] <= 100
    assert delta["message_id"] == start["message_id"]

    done = events[3]["data"]
    assert done["done"] is True
    assert done["content_event_count"] == 1
    assert done["message_id"] == start["message_id"]
    assert done["aigc_gate"] == {"status": "filing_pending", "public_surface": "hidden"}


def test_stream_matches_json_contract_for_stable_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    enable_internal_beta(monkeypatch)
    payload = {
        "message": "linear programming objective with constraints",
        "client_request_id": "stream-match-001",
    }

    json_response = post_json(payload)
    stream_response = post_stream(payload)

    assert json_response.status_code == 200
    assert stream_response.status_code == 200
    body = json_response.json()
    sse_events = parse_sse(stream_response.text)
    start = sse_events[1]["data"]
    done = sse_events[-1]["data"]
    assert start["message_id"] == body["message_id"]
    assert start["locale"] == body["locale"]
    assert done["model_preview_id"] == body["model_preview"]["preview_id"]
    assert done["model_preview_status"] == body["model_preview"]["status"]
    assert done["aigc_watermark_trace_id"] == body["language_preview"]["aigc_watermark"]["trace_id"]
    assert done["aigc_gate"] == body["aigc_gate"]


def test_unauthorized_invalid_body_fails_before_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    enable_internal_beta(monkeypatch)

    response = post_stream(
        payload={"message": " ", "unexpected": True},
        headers={**VALID_HEADERS, "X-Internal-Beta-Token": "wrong-token"},
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Not found"}
    assert "text/event-stream" not in response.headers["content-type"]
    assert "model_preview" not in response.text
    assert "aigc_watermark" not in response.text


def test_public_chat_stream_route_stays_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    enable_internal_beta(monkeypatch)

    response = client.post(
        "/v1/chat/stream",
        json={"message": "求最短路径，把车辆路线排出来"},
        headers=VALID_HEADERS,
    )

    assert response.status_code == 404
    assert "aigc_watermark" not in response.text


def test_last_event_id_resume_starts_after_matched_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)
    payload = {
        "message": "linear programming objective with constraints",
        "client_request_id": "stream-resume-001",
    }
    first_response = post_stream(payload)
    first_events = parse_sse(first_response.text)
    start_event_id = first_events[1]["id"]

    resumed = post_stream(payload, headers={**VALID_HEADERS, "Last-Event-ID": str(start_event_id)})

    assert resumed.status_code == 200
    resumed_events = parse_sse(resumed.text)
    assert resumed_events[0] == {"comment": ":heartbeat"}
    assert [event.get("event") for event in resumed_events[1:]] == ["content_delta", "done"]
    assert resumed_events[1]["id"] == first_events[2]["id"]


def test_invalid_last_event_id_returns_bounded_error_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)
    raw_cursor = "bad-cursor sk-test-secret C:\\tmp\\traceback"

    response = post_stream(
        {"message": "linear programming objective with constraints"},
        headers={**VALID_HEADERS, "Last-Event-ID": raw_cursor},
    )

    assert response.status_code == 200
    events = parse_sse(response.text)
    assert events[0] == {"comment": ":heartbeat"}
    assert [event.get("event") for event in events[1:]] == ["error"]
    payload = events[1]["data"]
    assert events[1]["id"].startswith("sse_")
    assert payload == {
        "error_code": "invalid_cursor",
        "message": "stream cursor is invalid for this response",
    }
    assert raw_cursor not in response.text
    assert "sk-test-secret" not in response.text
    assert "traceback" not in response.text.lower()


def test_stream_body_does_not_leak_raw_inputs_or_execution_identifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)
    message = "linear programming objective with constraints sk-test-secret"

    response = post_stream({"message": message, "client_request_id": "stream-leak-001"})

    assert response.status_code == 200
    body = response.text.lower()
    assert message.lower() not in body
    assert "sk-test-secret" not in body
    assert "raw_response" not in body
    assert "provider_request" not in body
    assert "prompt" not in body
    assert "traceback" not in body
    assert "class lpinput" not in body
    assert "charge_id" not in body
    assert "optimization_id" not in body
    assert "prediction_id" not in body


def test_streaming_filtered_chunk_reports_filtered_token_units() -> None:
    events = build_stream_events(
        message_id="msg_0123456789abcdef01234567",
        locale="en-US",
        content="sk-test-secret",
        model_preview_id="mpv_0123456789abcdef",
        model_preview_status="blocked",
        aigc_watermark_trace_id="trc_0123456789abcdef",
        aigc_gate={"status": "filing_pending", "public_surface": "hidden"},
    )

    delta = events[1]
    assert delta.data["chunk"] == "[filtered]"
    assert delta.data["token_units"] == content_token_units("[filtered]")


def test_streaming_helpers_format_chunk_and_strip_zero_width_metadata() -> None:
    text = "第一段内容。" + "\u200b\u200c\u200d\u2060"
    clean = strip_zero_width_metadata(text)
    chunks = split_content_chunks(" ".join(f"token{i}" for i in range(205)), max_units=100)

    assert clean == "第一段内容。"
    assert len(chunks) == 3
    assert all(1 <= content_token_units(chunk) <= 100 for chunk in chunks)
    event = build_stream_events(
        message_id="msg_0123456789abcdef01234567",
        locale="zh-CN",
        content="hello world",
        model_preview_id="mpv_0123456789abcdef",
        model_preview_status="blocked",
        aigc_watermark_trace_id="trc_0123456789abcdef",
        aigc_gate={"status": "filing_pending", "public_surface": "hidden"},
    )[1]
    formatted = format_sse_event(event)
    assert formatted.startswith("id: ")
    assert "\nevent: content_delta\n" in formatted
    assert formatted.endswith("\n\n")


def test_sse_formatter_filters_secret_like_values_inside_lists() -> None:
    formatted = format_sse_event(
        build_stream_events(
            message_id="msg_0123456789abcdef01234567",
            locale="en-US",
            content="hello world",
            model_preview_id="mpv_0123456789abcdef",
            model_preview_status="blocked",
            aigc_watermark_trace_id="trc_0123456789abcdef",
            aigc_gate={"status": "filing_pending", "public_surface": "hidden"},
            file_context_preview={
                "filenames": ["safe.csv"],
                "detected_fields": ["sku", "api_key", "demand"],
            },
        )[-1]
    )

    assert "api_key" not in formatted
    assert "[filtered]" in formatted
