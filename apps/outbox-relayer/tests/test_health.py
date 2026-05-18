"""Health endpoint tests (T5 + AC4)."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient
from outbox_relayer.health import make_app
from outbox_relayer.relayer import RelayerState


async def test_healthz_returns_200() -> None:
    state = RelayerState()
    app = make_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_readyz_returns_503_when_not_ready() -> None:
    state = RelayerState()  # ready=False by default
    app = make_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/readyz")
    assert r.status_code == 503


async def test_readyz_returns_200_when_ready() -> None:
    state = RelayerState()
    state.ready = True
    state.last_db_check_ok = True
    state.last_redis_check_ok = True
    app = make_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/readyz")
    assert r.status_code == 200


async def test_metrics_endpoint_returns_prometheus_format() -> None:
    state = RelayerState()
    app = make_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/metrics")
    assert r.status_code == 200
    # Prometheus exposition format header
    assert "text/plain" in r.headers["content-type"]
