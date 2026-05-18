"""Health + metrics HTTP endpoints (T5)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from outbox_relayer.relayer import RelayerState


def make_app(state: RelayerState) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield

    app = FastAPI(title="outbox-relayer-health", version="0.0.1", lifespan=lifespan)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        """Liveness — process alive."""
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz() -> Response:
        """Readiness — Postgres + Redis reachable on last poll."""
        if state.ready and state.last_db_check_ok and state.last_redis_check_ok:
            return Response(content='{"status":"ready"}', media_type="application/json")
        return Response(
            content='{"status":"not_ready"}',
            media_type="application/json",
            status_code=503,
        )

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


__all__ = ["make_app"]
