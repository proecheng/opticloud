"""Entrypoint — runs poll loop + LISTEN listener + health HTTP server in one event loop.

DR5: invoked via `python -m outbox_relayer.main`.
"""

from __future__ import annotations

import asyncio
import signal
import sys

import structlog
import uvicorn

from outbox_relayer.config import settings
from outbox_relayer.health import make_app
from outbox_relayer.relayer import RelayerState, _listener_loop, run_poll_loop

logger = structlog.get_logger("outbox_relayer.main")


async def _run() -> None:
    state = RelayerState()
    app = make_app(state)
    config = uvicorn.Config(
        app,
        host="0.0.0.0",  # noqa: S104 — sidecar binds 0.0.0.0; K8s service exposes selectively
        port=settings.health_port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    def _stop(*_args: object) -> None:
        logger.info("shutdown.signal")
        state.stop_event.set()
        server.should_exit = True

    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _stop)

    try:
        await asyncio.gather(
            run_poll_loop(state),
            _listener_loop(state),
            server.serve(),
        )
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass
