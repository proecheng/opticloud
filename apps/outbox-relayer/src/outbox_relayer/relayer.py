"""Polling loop orchestration (T3) + LISTEN/NOTIFY low-latency path (T4).

Two asyncpg connections:
1. `main_conn` — runs SELECT FOR UPDATE inside a transaction, then UPDATE
2. `listen_conn` — separate connection for LISTEN/NOTIFY (asyncpg constraint)

Per iteration:
- Open transaction → fetch_unsent → publish each → mark_sent → commit
- Sleep `poll_interval` OR wake up on NOTIFY (whichever first)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

import asyncpg
import structlog
from opentelemetry import trace
from prometheus_client import Counter, Gauge, Histogram

from outbox_relayer import broker, db
from outbox_relayer.config import settings

logger: Any = structlog.get_logger("outbox_relayer.relayer")
_tracer = trace.get_tracer(__name__)

# Prometheus metrics (SR3)
LAG_SECONDS: Gauge = Gauge(
    "outbox_relayer_lag_seconds", "Age of oldest unsent outbox row (seconds)"
)
PUBLISHED_TOTAL: Counter = Counter(
    "outbox_relayer_published_total", "Total outbox rows successfully published"
)
PUBLISH_FAIL_TOTAL: Counter = Counter(
    "outbox_relayer_publish_fail_total", "Per-row publish failures"
)
BATCH_SIZE: Histogram = Histogram(
    "outbox_relayer_batch_size", "Rows per batch", buckets=[0, 1, 5, 10, 50, 100]
)


class RelayerState:
    """Shared mutable state — stop event, ready flag for /readyz."""

    def __init__(self) -> None:
        self.stop_event: asyncio.Event = asyncio.Event()
        self.notify_event: asyncio.Event = asyncio.Event()
        self.ready: bool = False
        self.last_db_check_ok: bool = False
        self.last_redis_check_ok: bool = False


async def _listener_loop(state: RelayerState) -> None:
    """Subscribe to Postgres NOTIFY; signal the main loop on each notification."""
    while not state.stop_event.is_set():
        listen_conn: asyncpg.Connection | None = None
        try:
            listen_conn = await db.connect()

            def on_notify(_conn: object, _pid: int, _channel: str, _payload: str) -> None:
                state.notify_event.set()

            await listen_conn.add_listener(settings.listen_channel, on_notify)
            logger.info("listen.connected", channel=settings.listen_channel)

            # Keep the connection alive — listener fires in background
            while not state.stop_event.is_set():
                await asyncio.sleep(30)
                # Heartbeat: cheap query keeps the connection from idling out
                await listen_conn.fetchval("SELECT 1")
        except Exception as e:  # noqa: BLE001
            logger.warning("listen.reconnect", error=str(e))
            await asyncio.sleep(2)
        finally:
            if listen_conn is not None:
                try:
                    await listen_conn.close()
                except Exception:  # noqa: BLE001, S110
                    pass


async def _process_batch(
    main_conn: asyncpg.Connection,
    redis_client: object,
    state: RelayerState,
) -> int:
    """Fetch a batch, publish to Redis, mark sent. Returns rows handled."""
    with _tracer.start_as_current_span("relayer.batch") as span:
        async with main_conn.transaction():
            rows = await db.fetch_unsent(main_conn, settings.batch_size)
            span.set_attribute("batch.size", len(rows))
            BATCH_SIZE.observe(len(rows))

            if not rows:
                return 0

            published_ids: list[UUID] = []
            for row in rows:
                try:
                    with _tracer.start_as_current_span("relayer.publish") as pub_span:
                        pub_span.set_attribute("event.id", str(row.id))
                        pub_span.set_attribute("event.type", row.event_type)
                        await broker.publish(redis_client, row)  # type: ignore[arg-type]
                        published_ids.append(row.id)
                        PUBLISHED_TOTAL.inc()
                except Exception as e:  # noqa: BLE001
                    logger.warning("publish.failed", event_id=str(row.id), error=str(e))
                    PUBLISH_FAIL_TOTAL.inc()

            await db.mark_sent(main_conn, published_ids)

        # After commit, refresh lag gauge
        age = await db.get_oldest_unsent_age_seconds(main_conn)
        LAG_SECONDS.set(0.0 if age is None else age)
        state.last_db_check_ok = True

        return len(published_ids)


async def run_poll_loop(state: RelayerState) -> None:
    """Main polling loop. Reconnects on failure."""
    while not state.stop_event.is_set():
        main_conn: asyncpg.Connection | None = None
        redis_client: object | None = None
        try:
            main_conn = await db.connect()
            redis_client = await broker.connect()
            if not await broker.ping(redis_client):  # type: ignore[arg-type]
                raise RuntimeError("redis ping failed")
            state.last_redis_check_ok = True
            state.ready = True
            logger.info("relayer.started", channel=settings.listen_channel)

            while not state.stop_event.is_set():
                count = await _process_batch(main_conn, redis_client, state)
                if count == 0:
                    # Sleep until poll timeout OR a NOTIFY arrives — whichever first
                    state.notify_event.clear()
                    try:
                        await asyncio.wait_for(
                            state.notify_event.wait(),
                            timeout=settings.poll_interval_seconds,
                        )
                    except TimeoutError:
                        pass
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            state.ready = False
            logger.warning("relayer.reconnect", error=str(e))
            await asyncio.sleep(2)
        finally:
            if main_conn is not None:
                try:
                    await main_conn.close()
                except Exception:  # noqa: BLE001, S110
                    pass
            if redis_client is not None:
                try:
                    await redis_client.aclose()  # type: ignore[attr-defined]
                except Exception:  # noqa: BLE001, S110
                    pass


__all__ = ["RelayerState", "run_poll_loop", "_listener_loop", "_process_batch"]


# pyjwt+structlog quiet — only used to satisfy mypy "logger: Any"
logging.getLogger(__name__).addHandler(logging.NullHandler())
