"""RFC 7807 helper response-shape contract tests."""

from __future__ import annotations

from opticloud_shared.errors import ErrorDetail, rfc7807_error


def test_rfc7807_helper_serializes_next_action_url_without_legacy_key() -> None:
    response = rfc7807_error(
        title="Insufficient Credits",
        status_code=402,
        detail="balance is too low",
        errors=[
            ErrorDetail(
                field_path="body.amount",
                value="9999.00",
                constraint="amount > balance",
                remediation_hint_key="errors.402.topup",
            )
        ],
        next_action="https://console.opticloud.cn/topup?suggested_amount=10",
        type_uri="https://api.opticloud.cn/errors/insufficient_credits",
    )

    assert response.media_type == "application/problem+json"
    assert response.status_code == 402
    body = response.body.decode("utf-8")
    assert '"next_action_url":"https://console.opticloud.cn/topup?suggested_amount=10"' in body
    assert '"next_action"' not in body


def test_rfc7807_helper_accepts_next_action_url_alias() -> None:
    response = rfc7807_error(
        title="Rate Limit Exceeded",
        status_code=429,
        detail="too many requests",
        next_action_url="https://console.opticloud.cn/billing/plans",
    )

    body = response.body.decode("utf-8")
    assert '"next_action_url":"https://console.opticloud.cn/billing/plans"' in body
    assert '"next_action"' not in body


def test_rfc7807_helper_prefers_next_action_url_over_deprecated_alias() -> None:
    response = rfc7807_error(
        title="Validation Error",
        status_code=400,
        detail="bad request",
        next_action="https://legacy.example.test/action",
        next_action_url="https://docs.opticloud.cn/errors/billing-validation",
    )

    body = response.body.decode("utf-8")
    assert '"next_action_url":"https://docs.opticloud.cn/errors/billing-validation"' in body
    assert "legacy.example.test" not in body
