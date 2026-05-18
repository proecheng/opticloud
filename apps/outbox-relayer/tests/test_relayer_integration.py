"""Integration tests against real Postgres + Redis (Story M2.1 AC7)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

import asyncpg
import pytest_asyncio
import redis.asyncio as redis_async
from outbox_relayer import broker, db
from outbox_relayer.relayer import RelayerState, run_poll_loop


async def _insert_outbox(
    pg: asyncpg.Connection,
    *,
    aggregate_type: str = "saga_instance",
    event_type: str = "billing.saga.test",
    payload: dict | None = None,
) -> uuid.UUID:
    """Insert a single outbox row; return its id."""
    row_id = uuid.uuid4()
    await pg.execute(
        """
        INSERT INTO outbox (id, aggregate_type, aggregate_id, event_type,
                            event_version, payload, headers, occurred_at)
        VALUES ($1, $2, $3, $4, 1, $5, '{}'::jsonb, NOW())
        """,
        row_id,
        aggregate_type,
        uuid.uuid4(),
        event_type,
        json.dumps(payload or {"test": "hello"}),
    )
    return row_id


@pytest_asyncio.fixture
async def subscriber(
    redis_client: redis_async.Redis,
) -> tuple[redis_async.client.PubSub, list[dict]]:
    """A Redis SUBSCRIBE that captures messages received during the test."""
    received: list[dict] = []
    pubsub = redis_client.pubsub()
    await pubsub.psubscribe("opticloud.*")

    async def _collect() -> None:
        async for msg in pubsub.listen():
            if msg["type"] in ("pmessage", "message"):
                data = msg.get("data")
                if isinstance(data, str):
                    received.append(json.loads(data))

    task = asyncio.create_task(_collect())
    # Yield the subscriber control and the live list
    yield pubsub, received
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await pubsub.aclose()


async def test_happy_path_5_rows_reach_subscriber(
    pg: asyncpg.Connection,
    subscriber: tuple[redis_async.client.PubSub, list[dict]],
) -> None:
    """5 rows written → all reach Redis SUBSCRIBE within 2s."""
    _, received = subscriber

    # Pre-insert rows BEFORE starting relayer
    ids = [await _insert_outbox(pg) for _ in range(5)]

    # Start relayer in background; cancel after 2s
    state = RelayerState()
    relayer_task = asyncio.create_task(run_poll_loop(state))
    try:
        # Wait up to 2s for all 5 to arrive
        deadline = asyncio.get_event_loop().time() + 2.0
        while len(received) < 5 and asyncio.get_event_loop().time() < deadline:  # noqa: ASYNC110
            await asyncio.sleep(0.05)

        assert len(received) >= 5, f"expected 5 messages, got {len(received)}"
        received_ids = {r["event_id"] for r in received[:5]}
        assert received_ids == {str(i) for i in ids}

        # All rows must now have sent_at set
        unsent = await pg.fetchval("SELECT COUNT(*) FROM outbox WHERE sent_at IS NULL")
        assert unsent == 0
    finally:
        state.stop_event.set()
        relayer_task.cancel()
        with __import__("contextlib").suppress(asyncio.CancelledError):
            await relayer_task


async def test_listen_notify_low_latency(
    pg: asyncpg.Connection,
    subscriber: tuple[redis_async.client.PubSub, list[dict]],
) -> None:
    """Insert AFTER relayer starts → NOTIFY wakes it up; received within 500ms."""
    _, received = subscriber

    state = RelayerState()
    relayer_task = asyncio.create_task(run_poll_loop(state))
    try:
        # Give the relayer a moment to set up its initial state
        await asyncio.sleep(0.3)

        sent_at = datetime.now(UTC)
        await _insert_outbox(pg)

        deadline = asyncio.get_event_loop().time() + 0.5
        while not received and asyncio.get_event_loop().time() < deadline:  # noqa: ASYNC110
            await asyncio.sleep(0.02)

        assert received, "no message received within 500ms of NOTIFY"
        latency_ms = (datetime.now(UTC) - sent_at).total_seconds() * 1000
        # Loose bound — 500ms covers Postgres NOTIFY + poll wake + publish
        assert latency_ms < 500, f"latency too high: {latency_ms:.0f}ms"
    finally:
        state.stop_event.set()
        relayer_task.cancel()
        with __import__("contextlib").suppress(asyncio.CancelledError):
            await relayer_task


async def test_unsent_rows_visible_to_relayer(
    pg: asyncpg.Connection,
) -> None:
    """fetch_unsent returns the rows we inserted."""
    ids = [await _insert_outbox(pg) for _ in range(3)]
    async with pg.transaction():
        rows = await db.fetch_unsent(pg, limit=100)
        assert {r.id for r in rows} >= set(ids)


async def test_channel_naming(pg: asyncpg.Connection) -> None:
    """broker.channel_for follows opticloud.{agg}.{event} convention."""
    row_id = await _insert_outbox(
        pg, aggregate_type="saga_instance", event_type="billing.saga.user_cancel"
    )
    async with pg.transaction():
        rows = await db.fetch_unsent(pg, limit=1)
    matching = [r for r in rows if r.id == row_id]
    assert matching
    assert broker.channel_for(matching[0]) == "opticloud.saga_instance.billing.saga.user_cancel"
