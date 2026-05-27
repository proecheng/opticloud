"""Request-local error response context for Story 3.7."""

from __future__ import annotations

import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass

from starlette.requests import Request


@dataclass(frozen=True)
class ErrorRequestContext:
    accept_language: str | None = None
    instance: str | None = None
    request_id: str | None = None
    trace_id: str | None = None


_ERROR_REQUEST_CONTEXT: ContextVar[ErrorRequestContext] = ContextVar(
    "solver_orchestrator_error_request_context",
    default=ErrorRequestContext(),
)


def set_error_request_context(context: ErrorRequestContext) -> Token[ErrorRequestContext]:
    return _ERROR_REQUEST_CONTEXT.set(context)


def reset_error_request_context(token: Token[ErrorRequestContext]) -> None:
    _ERROR_REQUEST_CONTEXT.reset(token)


def get_error_request_context() -> ErrorRequestContext:
    return _ERROR_REQUEST_CONTEXT.get()


def context_from_request(request: Request) -> ErrorRequestContext:
    return ErrorRequestContext(
        accept_language=request.headers.get("accept-language"),
        instance=request.url.path,
        request_id=request.headers.get("x-request-id") or str(uuid.uuid4()),
        trace_id=request.headers.get("x-trace-id"),
    )
