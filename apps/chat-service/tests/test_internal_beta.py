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
    assert body["formulator_preview"] == {
        "status": "needs_clarification",
        "source": "heuristic_formulator_internal_beta",
        "task_type": "vrptw",
        "confidence": 0.4,
        "variables": {},
        "objective": {"kind": "minimize_total_distance"},
        "constraints": {},
        "validation_errors": [
            {
                "field_path": "variables",
                "message": "structured variables missing from deterministic completion",
                "remediation_hint_key": "chat.formulator.variables_required",
            }
        ],
        "supported_task_types": ["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"],
    }
    assert body["coder_preview"] == {
        "status": "needs_clarification",
        "source": "heuristic_coder_internal_beta",
        "task_type": "vrptw",
        "artifact": None,
        "validation_errors": [
            {
                "field_path": "formulator_preview.variables",
                "message": "structured formulation is required before code generation",
                "remediation_hint_key": "chat.coder.formulator_extracted_required",
            }
        ],
        "supported_task_types": ["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"],
    }
    assert body["critic_preview"] == {
        "status": "skipped",
        "source": "heuristic_critic_internal_beta",
        "task_type": "vrptw",
        "confidence": 0.0,
        "reasoning": "Critic skipped because no generated code artifact is available.",
        "checks": {
            "schema": {
                "passed": False,
                "message": "generated code artifact is required before critic validation",
                "field_path": "coder_preview.artifact",
            },
            "safety": {
                "passed": False,
                "message": "generated code artifact is required before safety validation",
                "field_path": "coder_preview.artifact",
            },
            "business_logic": {
                "passed": False,
                "message": "generated code artifact is required before business validation",
                "field_path": "coder_preview.artifact",
            },
        },
        "validation_errors": [
            {
                "field_path": "coder_preview.artifact",
                "message": "generated code artifact is required before critic validation",
                "remediation_hint_key": "chat.critic.artifact_required",
            }
        ],
        "supported_task_types": ["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"],
        "calibration_threshold": 0.6,
        "threshold_source": "apps/critic-service/config/critic-calibration.json",
    }
    assert body["sandbox_preview"] == {
        "status": "skipped",
        "source": "heuristic_sandbox_internal_beta",
        "task_type": "vrptw",
        "stdout_excerpt": "",
        "stderr_excerpt": "",
        "exit_code": None,
        "result_files": [],
        "error_code": None,
        "limits": {
            "cpu_vcpu": 1,
            "memory_mb": 1024,
            "soft_timeout_seconds": 30,
            "hard_timeout_seconds": 90,
            "network_disabled": True,
            "read_only_filesystem": True,
            "result_file_budget_bytes": 104857600,
        },
        "validation_errors": [
            {
                "field_path": "coder_preview.artifact",
                "message": "generated code artifact is required before sandbox execution",
                "remediation_hint_key": "chat.sandbox.artifact_required",
            }
        ],
        "contract_version": "sandbox-runner-p58-p62-local-v1",
    }
    assert body["language_preview"] == {
        "status": "fallback",
        "source": "heuristic_language_internal_beta",
        "response_locale": "zh-CN",
        "summary": "已识别为 VRPTW 请求，并生成 internal beta 预览。",
        "disclaimer": {
            "zh": "AI 生成内容仅供参考，请在提交求解前核对。",
            "en": "AI-generated content is for reference only. Review it before submitting a solve.",
            "bilingual": (
                "AI 生成内容仅供参考，请在提交求解前核对。 / "
                "AI-generated content is for reference only. Review it before submitting a solve."
            ),
        },
        "validation_errors": [
            {
                "field_path": "language.completion",
                "message": "language completion used deterministic fallback",
                "remediation_hint_key": "chat.language.fallback_used",
            }
        ],
        "supported_locales": ["zh-CN", "en-US", "mixed"],
    }
    assert body["aigc_gate"] == {"status": "filing_pending", "public_surface": "hidden"}
    assert body["llm_invoked"] is True
    assert body["critic_invoked"] is True
    assert body["critic_llm_invoked"] is False
    assert body["provider_request_sent"] is False
    assert body["formulator_preview"]["source"] != "provider_response"
    assert body["coder_preview"]["source"] != "provider_response"
    assert body["critic_preview"]["source"] != "provider_response"
    assert body["language_preview"]["source"] != "provider_response"
    assert body["solver_invoked"] is False
    assert body["sandbox_invoked"] is False
    assert "human_review_queue" not in body
    assert "aigc_filter" not in body
    assert "sandbox_result" not in body
    assert "execution_log" not in body


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
    assert body["formulator_preview"]["task_type"] == "prediction"
    assert body["formulator_preview"]["status"] == "needs_clarification"
    assert body["coder_preview"]["task_type"] == "prediction"
    assert body["coder_preview"]["status"] == "needs_clarification"
    assert body["coder_preview"]["artifact"] is None
    assert body["critic_invoked"] is True
    assert body["critic_llm_invoked"] is False
    assert body["critic_preview"]["status"] == "skipped"
    assert body["sandbox_preview"]["status"] == "skipped"
    assert body["sandbox_invoked"] is False
    assert body["critic_preview"]["confidence"] < body["critic_preview"]["calibration_threshold"]
    assert "human_review_queue" not in body
    assert "escalated" not in body
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
        assert body["formulator_preview"]["status"] == "skipped"
        assert body["formulator_preview"]["task_type"] == "unknown"
        assert body["coder_preview"]["status"] == "skipped"
        assert body["coder_preview"]["task_type"] == "unknown"
        assert body["coder_preview"]["artifact"] is None
        assert body["critic_preview"]["status"] == "skipped"
        assert body["critic_llm_invoked"] is False
    else:
        assert body["formulator_preview"]["task_type"] == expected_task_type
        assert body["coder_preview"]["task_type"] == expected_task_type
        assert body["critic_preview"]["task_type"] == expected_task_type
    assert body["language_preview"]["response_locale"] == expected_locale
    assert body["language_preview"]["supported_locales"] == ["zh-CN", "en-US", "mixed"]


def test_mixed_language_message_returns_same_locale_language_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)
    message = "请 solve route optimization for 北京 deliveries"

    response = post_message(payload={"message": message})

    assert response.status_code == 200
    body = response.json()
    assert body["locale"] == "mixed"
    assert body["language_preview"]["response_locale"] == "mixed"
    assert "已识别" in body["language_preview"]["summary"]
    assert "request" in body["language_preview"]["summary"]
    assert message not in body["language_preview"]["summary"]
    assert body["message_excerpt"] not in body["language_preview"]["summary"]
    assert body["language_preview"]["disclaimer"]["zh"]
    assert body["language_preview"]["disclaimer"]["en"]
    assert body["provider_request_sent"] is False


def test_internal_beta_response_keeps_g6_latency_validation_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)

    response = post_message(payload={"message": "linear programming objective with constraints"})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "internal_beta"
    assert body["public_access"] is False
    assert body["aigc_gate"] == {"status": "filing_pending", "public_surface": "hidden"}
    assert body["provider_request_sent"] is False
    assert body["solver_invoked"] is False
    assert body["sandbox_invoked"] is False
    assert body["critic_invoked"] is True
    assert body["critic_llm_invoked"] is False
    assert body["critic_preview"]["status"] == "skipped"
    assert body["critic_preview"]["calibration_threshold"] == 0.6
    assert body["critic_preview"]["threshold_source"] == (
        "apps/critic-service/config/critic-calibration.json"
    )
    assert set(body["critic_preview"]["checks"]) == {"schema", "safety", "business_logic"}
    assert body["sandbox_preview"]["status"] == "skipped"
    assert body["sandbox_preview"]["limits"] == {
        "cpu_vcpu": 1,
        "memory_mb": 1024,
        "soft_timeout_seconds": 30,
        "hard_timeout_seconds": 90,
        "network_disabled": True,
        "read_only_filesystem": True,
        "result_file_budget_bytes": 104857600,
    }
    assert "human_review_queue" not in body
    assert "escalated" not in body
    assert "hard_gate_pass" not in body
    assert "staging_pass" not in body
    assert "evidence_manifest" not in body
    assert "locust_report" not in body
    assert "grafana_screenshot" not in body
    assert "provider" not in body
    assert "raw_response" not in body
    assert "raw_response_redacted" not in body


def test_explicit_locale_override_drives_language_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_internal_beta(monkeypatch)

    response = post_message(
        payload={
            "message": "求最短路径，把车辆路线排出来",
            "locale": "en-US",
        }
    )

    assert response.status_code == 200
    body = response.json()
    assert body["locale"] == "en-US"
    assert body["language_preview"]["response_locale"] == "en-US"
    assert body["language_preview"]["summary"].startswith("Detected")
    assert "已识别" not in body["language_preview"]["summary"]


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
