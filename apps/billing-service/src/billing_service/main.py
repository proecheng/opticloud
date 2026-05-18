"""Billing service FastAPI app — Story 5.A.0a placeholder.

No routes yet (HTTP API is Story 5.A.1 J1 charge modal).
This file exists so `uv run uvicorn billing_service.main:app` works for
local smoke-testing later.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from billing_service import __version__
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


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
