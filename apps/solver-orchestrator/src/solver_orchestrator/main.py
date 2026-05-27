"""Solver orchestrator FastAPI entry point.

Run:
    PYTHONPATH=... uvicorn solver_orchestrator.main:app --port 8002

CRG2: HiGHS pre-warm on startup → cold-start subsequent call P95 < 200ms.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opticloud_shared import otel_setup
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from solver_orchestrator import __version__, solvers
from solver_orchestrator.error_context import (
    context_from_request,
    reset_error_request_context,
    set_error_request_context,
)
from solver_orchestrator.error_responses import (
    http_exception_response,
    request_validation_error_response,
)
from solver_orchestrator.routes import health_router, router


class UTF8JSONResponse(JSONResponse):
    """JSON response that preserves non-ASCII characters (Chinese)."""

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content, ensure_ascii=False, allow_nan=False, indent=None, separators=(",", ":")
        ).encode("utf-8")


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Init OTel + pre-warm HiGHS solver (CRG2)."""
    otel_setup.init(service_name="solver-orchestrator")
    try:
        solvers.prewarm()
        logger.info("HiGHS solver pre-warmed (CRG2 — cold-start ready)")
    except Exception as e:
        logger.warning(f"HiGHS pre-warm failed (will warm on first call): {e}")
    yield


app = FastAPI(
    title="OptiCloud Solver Orchestrator",
    version=__version__,
    description=(
        "FR C1-C8 (algorithm catalog) + FR E1-E10 (optimization execution) — "
        "Sprint 0 subset: Story 2.1 (algorithms) + Story 3.1 (LP solve with HiGHS)."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    default_response_class=UTF8JSONResponse,  # NFR-I: Chinese support in JSON
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3100",
        "http://127.0.0.1:3100",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept-Language",
        "Idempotency-Key",
        "X-Billing-Charge-Id",
    ],
)

FastAPIInstrumentor.instrument_app(app)


@app.middleware("http")
async def error_context_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    token = set_error_request_context(context_from_request(request))
    try:
        return await call_next(request)
    finally:
        reset_error_request_context(token)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return request_validation_error_response(request, exc)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return http_exception_response(request, exc)


app.include_router(health_router)
app.include_router(router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": "solver-orchestrator",
        "version": __version__,
        "docs": "/docs",
    }


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
