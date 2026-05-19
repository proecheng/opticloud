"""Auth service FastAPI app entry point.

Run locally:
    cd apps/auth-service
    uv run uvicorn auth_service.main:app --reload --port 8001

OpenAPI docs: http://localhost:8001/docs
Postman import: http://localhost:8001/openapi.json
Prometheus metrics: http://localhost:8001/metrics
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opticloud_shared import otel_setup
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from auth_service import __version__
from auth_service.admin_routes import admin_router
from auth_service.routes import health_router, router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize OpenTelemetry on startup."""
    otel_setup.init(service_name="auth-service")
    yield


app = FastAPI(
    title="OptiCloud Auth Service",
    version=__version__,
    description=(
        "Sprint 0 Story 0.6 — 注册 / API Key / JWT. "
        "FR A1-A10 (10 FR) coverage; AC: signup P95 < 800ms, api_keys.create P95 < 300ms (CRG1)."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS — allow local web app (Story 1.1a). Production lock to specific origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept-Language", "Idempotency-Key"],
)

# OTel auto-instrumentation (Story 0.7)
FastAPIInstrumentor.instrument_app(app)

app.include_router(health_router)
app.include_router(router)
app.include_router(admin_router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": "auth-service",
        "version": __version__,
        "docs": "/docs",
    }


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus scrape endpoint (Story 0.7 + NFR-O1)."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
