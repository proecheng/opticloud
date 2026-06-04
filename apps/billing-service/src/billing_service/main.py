"""Billing service FastAPI app — Story 5.A.0a placeholder.

No routes yet (HTTP API is Story 5.A.1 J1 charge modal).
This file exists so `uv run uvicorn billing_service.main:app` works for
local smoke-testing later.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from opticloud_shared.errors import ErrorDetail
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from billing_service import __version__
from billing_service.legal_routes import legal_router
from billing_service.problem_details import billing_problem_response
from billing_service.routes import billing_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown hook."""
    yield


app = FastAPI(
    title="OptiCloud Billing Service",
    version=__version__,
    description="Story 5.A.0a — Saga orchestrator + Credits ledger (no public HTTP API yet)",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


app.include_router(billing_router)
app.include_router(legal_router)


def _field_path_from_validation_loc(loc: Any) -> str:
    if not isinstance(loc, (list, tuple)) or not loc:
        return "$"
    return ".".join(str(part) for part in loc)


@app.exception_handler(StarletteHTTPException)
async def http_exception_problem_details(
    _request: Request, exc: StarletteHTTPException
) -> Response:
    """Return billing HTTPExceptions as RFC 7807 problem+json with O7 next actions."""
    detail = str(exc.detail)
    status_code = exc.status_code
    return billing_problem_response(
        title="Billing HTTP Error",
        status_code=status_code,
        detail=detail,
        errors=[
            ErrorDetail(
                field_path="$",
                value=None,
                constraint=detail,
                remediation_hint_key=f"errors.{status_code}.billing_http_error",
            )
        ],
    )


@app.exception_handler(RequestValidationError)
async def request_validation_problem_details(
    _request: Request, exc: RequestValidationError
) -> Response:
    """Return FastAPI request validation errors in the shared errors[] shape."""
    errors = [
        ErrorDetail(
            field_path=_field_path_from_validation_loc(error.get("loc")),
            value=None,
            constraint=str(error.get("msg", "request validation failed")),
            remediation_hint_key="errors.422.request_validation",
        )
        for error in exc.errors()
    ]
    return billing_problem_response(
        title="Request Validation Error",
        status_code=422,
        detail="request validation failed",
        errors=errors,
    )


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
