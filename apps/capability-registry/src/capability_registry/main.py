"""Capability-registry FastAPI entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opticloud_shared import otel_setup

from capability_registry import __version__
from capability_registry.routes import health_router, router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    otel_setup.init(service_name="capability-registry")
    yield


app = FastAPI(
    title="OptiCloud Capability Registry",
    version=__version__,
    description=(
        "Story 7.A.1 — strict-minimal provider/capability schema reservation. "
        "Does not execute provider marketplace, OAuth, revenue-share, or auto-migration flows."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "PUT", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Internal-Service-Auth"],
)

FastAPIInstrumentor.instrument_app(app)

app.include_router(health_router)
app.include_router(router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": "capability-registry",
        "version": __version__,
        "docs": "/docs",
    }
