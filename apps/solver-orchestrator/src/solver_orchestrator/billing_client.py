"""Cross-service billing client — Story 5.A.4 (B4 + 5.A.1 §"Out of scope" §51).

Solver-orchestrator → billing-service HTTP calls for the 2-phase Saga:
  1. reserve(charge_id, user_id) — PENDING → RESERVED
  2. finalize(charge_id, user_id, body) — RESERVED → CHARGED / REFUNDED

Auth: X-Internal-Service-Auth shared secret + X-Internal-User-Id (R1.2).
Reliability: single attempt, 2s timeout, no inline retry (Q4 — solve response
P95 must stay < 200ms warm; a billing outage MUST NOT slow the solver path).
On failure, caller logs + marks optimization.error.billing_finalize_failed=true.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal

import httpx
import structlog

from solver_orchestrator.config import settings

logger: Any = structlog.get_logger("solver_orchestrator.billing_client")


@dataclass(frozen=True)
class BillingResult:
    """Outcome of a single billing call — caller branches on `ok`."""

    ok: bool
    status_code: int
    body: dict[str, Any] | None
    error_message: str | None


def _headers(user_id: uuid.UUID) -> dict[str, str]:
    return {
        "X-Internal-Service-Auth": settings.billing_service_shared_secret,
        "X-Internal-User-Id": str(user_id),
        "Content-Type": "application/json",
    }


async def reserve(
    charge_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    client: httpx.AsyncClient | None = None,
) -> BillingResult:
    """POST /v1/billing/charges/{id}/reserve. Single attempt; 2s timeout."""
    url = f"{settings.billing_base_url}/v1/billing/charges/{charge_id}/reserve"
    return await _call(method="POST", url=url, json_body=None, user_id=user_id, client=client)


async def finalize(
    charge_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    elapsed_seconds: float,
    status: Literal["success", "failure"],
    failure_reason: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> BillingResult:
    """POST /v1/billing/charges/{id}/finalize."""
    url = f"{settings.billing_base_url}/v1/billing/charges/{charge_id}/finalize"
    body = {
        "elapsed_seconds": elapsed_seconds,
        "status": status,
        "failure_reason": failure_reason,
    }
    return await _call(method="POST", url=url, json_body=body, user_id=user_id, client=client)


async def _call(
    *,
    method: str,
    url: str,
    json_body: dict[str, Any] | None,
    user_id: uuid.UUID,
    client: httpx.AsyncClient | None,
) -> BillingResult:
    """Single-attempt HTTP call with the shared-secret headers (R1.2 + Q4)."""
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=settings.billing_callback_timeout_seconds)
    try:
        try:
            resp = await client.request(method, url, json=json_body, headers=_headers(user_id))
        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.warning(
                "billing.call.failed",
                url=url,
                exception_type=type(e).__name__,
                message=str(e),
            )
            return BillingResult(ok=False, status_code=0, body=None, error_message=str(e))

        body: dict[str, Any] | None = None
        try:
            body = resp.json()
        except ValueError:
            body = None

        if 200 <= resp.status_code < 300:
            return BillingResult(
                ok=True, status_code=resp.status_code, body=body, error_message=None
            )

        logger.warning(
            "billing.call.non_2xx",
            url=url,
            status_code=resp.status_code,
            body=body,
        )
        return BillingResult(
            ok=False,
            status_code=resp.status_code,
            body=body,
            error_message=f"HTTP {resp.status_code}",
        )
    finally:
        if owns_client:
            await client.aclose()


__all__ = ["BillingResult", "finalize", "reserve"]
