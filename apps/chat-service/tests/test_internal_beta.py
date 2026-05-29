from __future__ import annotations

import os
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


def post_message(
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> object:
    return client.post(
        "/v1/chat/internal-beta/messages",
        json=payload or {"message": "求最短路径，把车辆路线排出来"},
        headers=headers or VALID_HEADERS,
    )


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "chat-service"}


def test_internal_beta_defaults_fail_closed_without_leaking_aigc_gate() -> None:
    response = post_message()

    assert response.status_code == 404
    body = response.json()
    assert body == {"detail": "Not found"}
    assert "aigc_gate" not in body


def test_internal_beta_disabled_rejects_invalid_body_without_schema_leak() -> None:
    response = post_message(payload={"message": " ", "unexpected": True})

    assert response.status_code == 404
    body = response.json()
    assert body == {"detail": "Not found"}
    assert "aigc_gate" not in body


def test_internal_beta_requires_founder_legal_signoff(monkeypatch: pytest.MonkeyPatch) -> None:
    enable_internal_beta(monkeypatch, CHAT_INTERNAL_BETA_SIGNOFF="pending")

    response = post_message()

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}


def test_internal_beta_rejects_more_than_five_named_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(
        monkeypatch,
        CHAT_INTERNAL_BETA_USERS="u1,u2,u3,u4,u5,u6",
    )

    response = post_message(headers={**VALID_HEADERS, "X-Internal-Beta-User": "u1"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}


@pytest.mark.parametrize(
    "header_patch",
    [
        {"X-Internal-Beta-Tenant": "public-tenant"},
        {"X-Internal-Beta-User": "unknown-user"},
        {"X-Internal-Beta-Token": "wrong-token"},
    ],
)
def test_internal_beta_rejects_invalid_tenant_user_or_token(
    monkeypatch: pytest.MonkeyPatch,
    header_patch: dict[str, str],
) -> None:
    enable_internal_beta(monkeypatch)

    response = post_message(headers={**VALID_HEADERS, **header_patch})

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}


def test_internal_beta_rejects_unauthorized_headers_before_body_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)

    response = post_message(
        payload={"message": " ", "unexpected": True},
        headers={**VALID_HEADERS, "X-Internal-Beta-Token": "wrong-token"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}


def test_vrptw_message_returns_internal_beta_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    enable_internal_beta(monkeypatch)
    message = "求最短路径，把车辆路线排出来"

    response = post_message(payload={"message": message, "client_request_id": "req-chat-beta-001"})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "internal_beta"
    assert body["public_access"] is False
    assert body["message_id"].startswith("msg_")
    assert body["message_excerpt"] != message
    assert len(body["message_excerpt"]) <= 64
    assert body["locale"] == "zh-CN"
    assert body["router_preview"] == {
        "task_type": "vrptw",
        "confidence": 0.92,
        "reasoning": "matched LLM router intent output",
        "source": "llm_router_internal_beta",
        "supported_task_types": ["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"],
    }
    assert body["aigc_gate"] == {"status": "filing_pending", "public_surface": "hidden"}
    assert body["llm_invoked"] is True
    assert body["provider_request_sent"] is False
    assert body["solver_invoked"] is False
    assert body["sandbox_invoked"] is False


def test_vrptw_message_uses_llm_router_intent_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)
    message = "求最短路径，把车辆路线排出来"

    response = post_message(payload={"message": message, "client_request_id": "req-chat-beta-002"})

    assert response.status_code == 200
    body = response.json()
    assert body["router_preview"]["task_type"] == "vrptw"
    assert body["router_preview"]["confidence"] == 0.92
    assert body["router_preview"]["source"] == "llm_router_internal_beta"
    assert message not in body["router_preview"]["reasoning"]
    assert body["llm_invoked"] is True
    assert body["provider_request_sent"] is False
    assert "provider" not in body
    assert "raw_response_redacted" not in body


def test_llm_router_guardrail_preserves_supported_non_route_task_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)

    response = post_message(payload={"message": "请预测下个月 SKU 销量"})

    assert response.status_code == 200
    body = response.json()
    assert body["router_preview"]["task_type"] == "prediction"
    assert body["router_preview"]["source"] == "heuristic_internal_beta"
    assert body["llm_invoked"] is True
    assert body["provider_request_sent"] is False


@pytest.mark.parametrize(
    ("message", "expected_task_type", "expected_locale"),
    [
        ("linear programming objective with constraints", "lp", "en-US"),
        ("请预测下个月 SKU 销量", "prediction", "mixed"),
        ("schedule the shifts for tomorrow", "schedule", "en-US"),
        ("库存补货策略 for sku", "inventory", "mixed"),
        ("帮我看一下这个业务问题", "unknown", "zh-CN"),
    ],
)
def test_router_preview_is_deterministic_for_supported_task_types(
    monkeypatch: pytest.MonkeyPatch,
    message: str,
    expected_task_type: str,
    expected_locale: str,
) -> None:
    enable_internal_beta(monkeypatch)

    response = post_message(payload={"message": message})

    assert response.status_code == 200
    body = response.json()
    assert body["router_preview"]["task_type"] == expected_task_type
    assert body["router_preview"]["source"] == "heuristic_internal_beta"
    assert body["locale"] == expected_locale
    if expected_task_type == "unknown":
        assert body["router_preview"]["confidence"] <= 0.4


@pytest.mark.parametrize(
    "payload",
    [
        {"message": " "},
        {"message": "a"},
        {"message": "x" * 2001},
        {"message": "valid", "locale": "fr-FR"},
        {"message": "valid", "unexpected": True},
    ],
)
def test_request_validation_rejects_bad_input(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
) -> None:
    enable_internal_beta(monkeypatch)

    response = post_message(payload=payload)

    assert response.status_code == 422
