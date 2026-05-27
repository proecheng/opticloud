"""RFC 7807 response builder for solver-orchestrator."""

from __future__ import annotations

import json
import math
import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from opticloud_shared.schemas.errors import ErrorDetail, ErrorResponse
from starlette.requests import Request

from solver_orchestrator.error_catalog import (
    ERROR_CATALOG,
    error_key_for_remediation,
    error_key_for_title,
    resolve_error_locale,
)
from solver_orchestrator.error_context import ErrorRequestContext, get_error_request_context

PROBLEM_JSON = "application/problem+json"
MAX_ERROR_VALUE_STRING_LENGTH = 160
SENSITIVE_ERROR_FIELDS = {
    "header.Authorization",
    "header.Idempotency-Key",
    "header.X-Billing-Charge-Id",
}


def json_safe_error_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool | int | str):
        if isinstance(value, str) and len(value) > MAX_ERROR_VALUE_STRING_LENGTH:
            return "[omitted]"
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else "[non-finite]"
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, list | tuple):
        if len(value) > 8:
            return "[omitted]"
        return [json_safe_error_value(item) for item in value]
    if isinstance(value, dict):
        return "[omitted]"
    try:
        json.dumps(value, allow_nan=False)
        return value
    except (TypeError, ValueError):
        return str(value)[:MAX_ERROR_VALUE_STRING_LENGTH]


def _format_template(template: str, detail: str) -> str:
    try:
        return template.format(detail=detail)
    except (KeyError, ValueError):
        return template


def _context_with_request(request: Request | None) -> ErrorRequestContext:
    context = get_error_request_context()
    if request is None:
        return context
    return ErrorRequestContext(
        accept_language=request.headers.get("accept-language") or context.accept_language,
        instance=request.url.path,
        request_id=request.headers.get("x-request-id") or context.request_id or str(uuid.uuid4()),
        trace_id=request.headers.get("x-trace-id") or context.trace_id,
    )


def _default_error_detail(
    *,
    key: str,
    value: Any | None,
    constraint: str | None,
    field_path: str | None,
) -> ErrorDetail:
    entry = ERROR_CATALOG[key]
    return ErrorDetail(
        field_path=field_path or entry.default_field_path,
        value=json_safe_error_value(value if value is not None else entry.default_value),
        constraint=constraint or entry.constraint,
        remediation_hint_key=entry.remediation_hint_key,
    )


def _normalize_error_detail(detail: ErrorDetail) -> ErrorDetail:
    value = "[redacted]" if detail.field_path in SENSITIVE_ERROR_FIELDS else detail.value
    return ErrorDetail(
        field_path=detail.field_path,
        value=json_safe_error_value(value),
        constraint=detail.constraint,
        remediation_hint_key=detail.remediation_hint_key,
    )


def _error_key_from_details(errors: list[ErrorDetail] | None) -> str | None:
    if not errors:
        return None
    return error_key_for_remediation(errors[0].remediation_hint_key)


def build_problem_response(
    *,
    title: str | None = None,
    status_code: int | None = None,
    detail: str,
    errors: list[ErrorDetail] | None = None,
    next_action: str | None = None,
    request_id: str | None = None,
    request: Request | None = None,
    error_key: str | None = None,
    field_path: str | None = None,
    value: Any | None = None,
    constraint: str | None = None,
) -> JSONResponse:
    resolved_key = (
        error_key
        or _error_key_from_details(errors)
        or error_key_for_title(title or "", status_code or 422)
    )
    entry = ERROR_CATALOG[resolved_key]
    resolved_status = status_code or entry.status
    context = _context_with_request(request)
    locale = resolve_error_locale(context.accept_language)
    response_errors = (
        [_normalize_error_detail(item) for item in errors]
        if errors
        else [
            _default_error_detail(
                key=resolved_key,
                value=value,
                constraint=constraint,
                field_path=field_path,
            )
        ]
    )
    localized_detail = _format_template(entry.detail[locale], detail)
    body = ErrorResponse(
        type=f"https://api.opticloud.cn/errors/{entry.slug}",
        title=entry.title[locale],
        status=resolved_status,
        detail=localized_detail,
        errors=response_errors,
        instance=context.instance,
        request_id=request_id or context.request_id or str(uuid.uuid4()),
        trace_id=context.trace_id,
        next_action_url=next_action if next_action is not None else entry.next_action_url,
    )
    return JSONResponse(
        content=json.loads(body.model_dump_json()),
        status_code=resolved_status,
        media_type=PROBLEM_JSON,
    )


def pydantic_loc_to_field_path(loc: Sequence[Any]) -> str:
    parts = list(loc)
    if parts and parts[0] in {"body", "query", "path", "header"}:
        prefix = parts.pop(0)
    else:
        prefix = "body"
    rendered = ""
    for part in parts:
        if isinstance(part, int):
            rendered += f"[{part}]"
        else:
            if rendered:
                rendered += "."
            rendered += str(part)
    if not rendered:
        rendered = "$"
    if prefix == "body":
        return rendered
    return f"{prefix}.{rendered}"


def _value_from_validation_error(error: dict[str, Any]) -> Any:
    value = error.get("input")
    return json_safe_error_value(value)


def request_validation_error_response(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details: list[ErrorDetail] = []
    for item in exc.errors():
        field_path = pydantic_loc_to_field_path(tuple(item.get("loc", ())))
        message = str(item.get("msg") or item.get("type") or "invalid request")
        details.append(
            ErrorDetail(
                field_path=field_path,
                value=_value_from_validation_error(item),
                constraint=message,
                remediation_hint_key="errors.422.invalid_request_body",
            )
        )
    if not details:
        details.append(
            _default_error_detail(
                key="invalid_request_body",
                value=None,
                constraint=None,
                field_path="$",
            )
        )
    return build_problem_response(
        request=request,
        error_key="invalid_request_body",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="request body failed schema validation",
        errors=details,
    )


def http_exception_response(request: Request, exc: HTTPException) -> JSONResponse:
    detail = str(exc.detail)
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        key = "missing_authorization"
        field_path = "header.Authorization"
        value = "[redacted]"
        detail = "Authorization header is missing or invalid"
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        key = "forbidden_scope"
        field_path = "scope"
        value = "[redacted]"
    elif exc.status_code == status.HTTP_404_NOT_FOUND:
        key = "not_found"
        field_path = "path.resource"
        value = "[redacted]"
    else:
        key = "invalid_json" if exc.status_code == 400 else "validation_error"
        field_path = "$"
        value = None
    return build_problem_response(
        request=request,
        error_key=key,
        status_code=exc.status_code,
        detail=detail,
        field_path=field_path,
        value=value,
    )
