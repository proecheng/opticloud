"""Billing-service RFC 7807 problem response helpers."""

from __future__ import annotations

from typing import cast

from fastapi import status
from opticloud_shared.errors import ErrorDetail, rfc7807_error
from starlette.responses import Response

TOPUP_NEXT_ACTION_URL = "https://console.opticloud.cn/topup?suggested_amount=10"
BILLING_HELP_URL = "https://docs.opticloud.cn/errors/billing"
BILLING_AUTH_URL = "https://docs.opticloud.cn/errors/billing-auth"
BILLING_IDEMPOTENCY_URL = "https://docs.opticloud.cn/errors/idempotency_conflict"
BILLING_BUDGET_URL = "https://console.opticloud.cn/billing/budget"
BILLING_PLANS_URL = "https://console.opticloud.cn/billing/plans"
BILLING_NOT_FOUND_URL = "https://docs.opticloud.cn/errors/not_found"
BILLING_VALIDATION_URL = "https://docs.opticloud.cn/errors/billing-validation"

_BILLING_4XX_NEXT_ACTION_URLS = {
    status.HTTP_400_BAD_REQUEST: BILLING_VALIDATION_URL,
    status.HTTP_401_UNAUTHORIZED: BILLING_AUTH_URL,
    status.HTTP_402_PAYMENT_REQUIRED: TOPUP_NEXT_ACTION_URL,
    status.HTTP_403_FORBIDDEN: BILLING_PLANS_URL,
    status.HTTP_404_NOT_FOUND: BILLING_NOT_FOUND_URL,
    status.HTTP_409_CONFLICT: BILLING_IDEMPOTENCY_URL,
    status.HTTP_422_UNPROCESSABLE_ENTITY: BILLING_VALIDATION_URL,
}


def billing_problem_response(
    *,
    title: str,
    status_code: int,
    detail: str,
    errors: list[ErrorDetail] | None = None,
    next_action_url: str | None = None,
    type_uri: str = "about:blank",
) -> Response:
    """Build a billing RFC 7807 response with O7 next-action defaults for 4xx."""
    resolved_next_action_url = next_action_url
    if resolved_next_action_url is None and 400 <= status_code < 500:
        resolved_next_action_url = _BILLING_4XX_NEXT_ACTION_URLS.get(status_code, BILLING_HELP_URL)
    return cast(
        Response,
        rfc7807_error(
            title=title,
            status_code=status_code,
            detail=detail,
            errors=errors,
            next_action_url=resolved_next_action_url,
            type_uri=type_uri,
        ),
    )
