"""RFC 7807 problem+json response builder (D2 fix — extracted for reuse).

Used by billing-service (5.A.1) and any future service that needs structured
error responses. solver-orchestrator's inline helper is unchanged (DR1 — refactor
deferred as tech-debt).

Spec: https://datatracker.ietf.org/doc/html/rfc7807
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Individual field-level error detail (FG1.3 SDK error.locate() input)."""

    field_path: str
    value: Any | None = None
    constraint: str
    remediation_hint_key: str | None = None


def rfc7807_error(
    title: str,
    status_code: int,
    detail: str,
    errors: list[ErrorDetail] | None = None,
    next_action: str | None = None,
    request_id: str | None = None,
    type_uri: str = "about:blank",
) -> JSONResponse:
    """Build a FastAPI JSONResponse following RFC 7807 problem+json shape.

    Args:
        title: short human-readable summary
        status_code: HTTP status
        detail: longer human-readable explanation
        errors: optional per-field error list
        next_action: optional URL for user remediation (FR O7)
        request_id: optional trace correlation id
        type_uri: optional URI identifying the error class
    """
    body: dict[str, Any] = {
        "type": type_uri,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if errors:
        body["errors"] = [e.model_dump(exclude_none=True) for e in errors]
    if next_action:
        body["next_action"] = next_action
    if request_id:
        body["request_id"] = request_id

    return JSONResponse(
        status_code=status_code, content=body, media_type="application/problem+json"
    )
