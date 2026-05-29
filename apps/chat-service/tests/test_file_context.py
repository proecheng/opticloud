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


def csv_context(
    *,
    filename: str = "demand.csv",
    headers: list[str] | None = None,
    summary: str = "csv rows=24 headers=sku,month,demand",
) -> dict[str, object]:
    return {
        "source": "parsed_browser_file_context_v1",
        "kind": "csv",
        "filename": filename,
        "size_bytes": 1024,
        "mime_type": "text/csv",
        "row_count": 24,
        "sheet_count": 0,
        "sheets": [],
        "top_level_keys": [],
        "detected_fields": headers or ["sku", "month", "demand"],
        "summary": summary,
    }


def excel_context() -> dict[str, object]:
    return {
        "source": "parsed_browser_file_context_v1",
        "kind": "excel",
        "filename": "schedule.xlsx",
        "size_bytes": 2048,
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "row_count": 12,
        "sheet_count": 2,
        "sheets": [
            {"name": "任务", "headers": ["任务", "工期"], "row_count": 8},
            {"name": "资源", "headers": ["资源", "数量"], "row_count": 4},
        ],
        "top_level_keys": [],
        "detected_fields": ["任务", "工期", "资源", "数量"],
        "summary": "workbook sheets=任务,资源",
    }


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


def test_json_route_accepts_bounded_file_context_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)
    payload = {
        "message": "用上传文件判断是库存预测还是排程",
        "client_request_id": "file-context-json-001",
        "file_contexts": [csv_context(), excel_context()],
    }

    response = post_json(payload)

    assert response.status_code == 200
    body = response.json()
    assert body["file_context_preview"] == {
        "file_count": 2,
        "kinds": ["csv", "excel"],
        "total_rows": 36,
        "filenames": ["demand.csv", "schedule.xlsx"],
        "detected_fields": ["demand", "month", "sku", "任务", "工期", "数量", "资源"],
    }
    assert body["message_id"].startswith("msg_")
    assert body["file_context_preview"]["filenames"][0] == "demand.csv"
    assert "已读取上传文件上下文" in body["language_preview"]["summary"]
    serialized = json.dumps(body, ensure_ascii=False).lower()
    assert "raw" not in serialized
    assert "sk-test-secret" not in serialized
    assert "c:\\tmp" not in serialized


def test_no_file_context_returns_explicit_null_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)

    response = post_json(
        {
            "message": "linear programming objective with constraints",
            "client_request_id": "file-context-none-001",
        }
    )

    assert response.status_code == 200
    assert response.json()["file_context_preview"] is None


def test_file_context_changes_message_id_but_order_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)
    base = {
        "message": "用上传文件判断模型",
        "client_request_id": "file-context-digest-001",
    }
    first = post_json({**base, "file_contexts": [csv_context(), excel_context()]}).json()
    reordered = post_json({**base, "file_contexts": [excel_context(), csv_context()]}).json()
    changed = post_json(
        {
            **base,
            "file_contexts": [
                csv_context(headers=["sku", "month", "sales"], summary="csv rows=24 headers=sales")
            ],
        }
    ).json()

    assert first["message_id"] == reordered["message_id"]
    assert first["message_id"] != changed["message_id"]


def test_digest_order_is_stable_for_same_filename_and_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)
    base = {
        "message": "比较同名文件的两个 sheet context",
        "client_request_id": "file-context-digest-tie-001",
    }
    first_context = csv_context(headers=["sku", "month"], summary="csv rows=24 headers=sku,month")
    second_context = csv_context(
        headers=["sku", "demand"], summary="csv rows=24 headers=sku,demand"
    )

    first = post_json({**base, "file_contexts": [first_context, second_context]}).json()
    reordered = post_json({**base, "file_contexts": [second_context, first_context]}).json()

    assert first["message_id"] == reordered["message_id"]


def test_stream_route_matches_json_file_context_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)
    payload = {
        "message": "use uploaded file headers to infer inventory task",
        "client_request_id": "file-context-stream-001",
        "file_contexts": [csv_context()],
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
    assert done["file_context_preview"] == body["file_context_preview"]
    assert done["model_preview_id"] == body["model_preview"]["preview_id"]


def test_invalid_file_context_fails_before_sse_starts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)
    payload = {
        "message": "use uploaded file",
        "file_contexts": [{**csv_context(filename="C:\\tmp\\secret.csv")}],
    }

    response = post_stream(payload)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")
    assert "text/event-stream" not in response.headers["content-type"]
    assert "model_preview" not in response.text


def test_unauthorized_invalid_file_context_fails_closed_before_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)
    response = post_json(
        {
            "message": "x",
            "file_contexts": [{**csv_context(filename="C:\\tmp\\secret.csv")}],
        },
        headers={**VALID_HEADERS, "X-Internal-Beta-Token": "wrong-token"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}
    assert "file_contexts" not in response.text


def test_secret_like_file_context_metadata_does_not_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)
    payload = {
        "message": "use uploaded file",
        "client_request_id": "file-context-secret-001",
        "file_contexts": [
            csv_context(
                headers=["sku", "api_key", "demand"],
                summary="csv rows=2 secret sk-test-secret C:\\tmp\\traceback",
            )
        ],
    }

    response = post_json(payload)

    assert response.status_code == 422
    serialized = response.text.lower()
    assert "model_preview" not in serialized
    assert "input" not in serialized
    assert "api_key" not in serialized
    assert "sk-test-secret" not in serialized
    assert "traceback" not in serialized
    assert not re.search(r"[a-z]:\\", serialized)
