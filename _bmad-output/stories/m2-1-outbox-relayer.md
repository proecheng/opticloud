---
story_key: m2-1-outbox-relayer
epic_num: 0
story_num: M2.1
epic_name: Foundation
status: done
priority: 🔴 Critical (closes the P33 Outbox loop — 5.A.0a/5.A.1 write outbox rows but no one publishes; current system has dangling events)
sizing: M (5-7 hours; new service + LISTEN/NOTIFY + Redis pub + tests)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-18
sources:
  - _bmad-output/planning/epics.md (Story M2.1)
  - docs/adr/0002-outbox-relayer-deployment.md (locks: K8s sidecar; Dramatiq actor; 100ms poll + LISTEN/NOTIFY; P95 lag < 1s)
  - docs/adr/0001-saga-pattern.md (Hybrid Saga; orchestrator writes outbox row)
  - _bmad-output/planning/architecture.md v2.2 (P33 Outbox / P56 Sidecar / C12 separate-from-business / B2 M1-M2 boundary)
  - apps/billing-service/src/billing_service/saga_orchestrator.py (the producer — writes outbox rows in apply())
  - infra/local-init/01-schema.sql (outbox table schema — `outbox` with `sent_at IS NULL` index)
  - docker-compose.yml (Redis already running on :6379)
dependencies:
  upstream:
    - m2-0-saga-spike (done) — ADR-0002 locks design
    - 5-a-0a-saga-implementation (done) — producer writing outbox rows
    - 0-2-docker-compose (done) — Redis + Postgres running
  downstream:
    - 5-a-4-per-formula-charging — cross-service Saga relies on relayer
    - 4-a-1-nl-chat-input-internal-beta — chat subscribes to billing events
    - m2-2a-billing-critical-tests — end-to-end Saga tests need broker
    - 8-a-3-24h-postmortem — audit events flow through relayer
---

# Story M2.1 — Outbox Relayer Sidecar

## User Story

**As** the OptiCloud platform owner
**I want** outbox events written by billing-service (and future services) to be **published to a message broker reliably**
**so that** consumers (chat, repro, audit) can react asynchronously to Saga transitions without polling the source DB.

## Why this story

After 5.A.0a + 5.A.1, every charge writes one or more rows to the `outbox` table — but **no one consumes them**. The rows accumulate indefinitely. The "transactional dual-write" pattern (P33) is half-implemented.

M2.1 ships the **relayer** process that drains `outbox.sent_at IS NULL` rows, publishes payload+headers to Redis pub/sub, and marks each row `sent_at = NOW()`. This closes the Outbox loop.

Per ADR-0002, the production deployment is a **per-service sidecar container**. For M2.1 v1, we ship a **standalone process** that can be deployed either as sidecar (K8s) OR as a single dev/staging instance pointed at the same Postgres. The architecture stays compatible with future K8s sidecar deploy.

## Out of scope

- K8s sidecar **deployment manifests** → deferred to M3.3a (production K8s rollout)
- Kafka broker (v2+; Redis pub/sub only for v1)
- Consumer-side dedup logic → each consumer responsibility; relayer is at-least-once
- Schema evolution dual-publish (P63) → v2+
- Outbox table partitioning → v2+ (after row count > 10M)
- Cross-namespace network policies (ADR-0002 documented; enforced at deploy in M3.3a)
- **A2 v1 scope**: single relayer instance pointed at billing-service's DB only. Multi-producer (auth/repro/etc.) deferred — each producer gets own relayer in M3.3a sidecar deploy. Multi-replica scaling works by design (FOR UPDATE SKIP LOCKED) but not exercised in v1.
- DLQ table for retry-exhausted rows → v2+
- **DR4 — Consumer side**: M2.1 only PUBLISHES to Redis. No subscriber exists yet — events go into the void. Consumers added in future stories:
  - Story 4.A.* — chat-service subscribes to `opticloud.saga_instance.billing.saga.*` for usage tracking
  - Story 5.A.4 — solver-orchestrator subscribes for cross-service Saga
  - Story 8.a.4 — audit-log service subscribes for compliance trail

## Acceptance Criteria

### AC1: New service `apps/outbox-relayer`
- Workspace member with own pyproject.toml
- Entry: `apps/outbox-relayer/src/outbox_relayer/main.py` with `python -m outbox_relayer.main` runnable
- Long-lived asyncio process (not a CLI command); graceful shutdown on SIGTERM
- **R1.2 lock**: One asyncio event loop runs BOTH the polling loop AND the uvicorn healthz server via `asyncio.gather(poll_loop(), serve_health())`
- Logs structured JSON via shared logger
- **R1.6: OTel spans** — each batch publishes a `relayer.batch` span; each individual publish is a `relayer.publish` child span with `event.id`, `event.type` attributes

### AC2: Reads outbox rows + publishes to Redis
- Connects to Postgres via async DSN (same `DATABASE_URL` as billing)
- Connects to Redis via `REDIS_URL` (default `redis://localhost:6379`)
- Per iteration:
  - `SELECT id, aggregate_type, aggregate_id, event_type, event_version, payload, headers, occurred_at FROM outbox WHERE sent_at IS NULL ORDER BY occurred_at FOR UPDATE SKIP LOCKED LIMIT 100`
  - For each row: publish to Redis channel `opticloud.{aggregate_type}.{event_type}` with JSON-serialized envelope
  - `UPDATE outbox SET sent_at = NOW() WHERE id = ANY(:ids)` — batch update for the rows successfully published
- Failure on a single row → skip that row; do NOT block others; log warning; row stays for next iteration
- **S3 assumption**: payload + headers MUST be pre-validated as PII-free by producer (ADR-0001 §Security). Relayer does NOT inspect contents — it's a pure pipe. Producer breach → relayer breach.
- **SR3 lock — observability**: emit Prometheus metric `outbox_relayer_lag_seconds` (Gauge) = oldest unsent row's `(NOW() - occurred_at)` after each batch; `outbox_relayer_published_total` (Counter); `outbox_relayer_batch_size` (Histogram). Exposed at `/metrics` on the health port. Prometheus scrape config out of scope (v1.5).

### AC3: LISTEN/NOTIFY push (low-latency path)
- Subscribes to Postgres channel `outbox_new` (defined in schema migration)
- Trigger on `outbox` INSERT: `pg_notify('outbox_new', NEW.id::text)`
- On NOTIFY received → triggers an immediate poll (interrupts the 100ms sleep)
- Fall-back: 100ms polling continues regardless of notifies (for safety on missed events)

### AC4: Graceful shutdown + health endpoints
- SIGTERM / SIGINT → finishes current batch (don't lose work), then closes connections
- Health endpoints on port 9001 (D2 lock — match auth-service pattern):
  - `GET /healthz` — liveness: always 200 if the process is up (returns `{"status": "ok"}`)
  - `GET /readyz` — readiness: 200 if Postgres + Redis both reachable; 503 otherwise
- Liveness probe = healthz; Readiness probe = readyz (K8s convention)

### AC5: Idempotency at consumer side
- Each Redis message has an `event_id` header (the `outbox.id` UUID)
- Consumer dedup is their responsibility (relayer is at-least-once, not exactly-once)
- Relayer never publishes the same row twice unless `sent_at` is NULL → safe to retry crash recovery
- **R1.3 lock**: persistent-failure rows (e.g., malformed payload) — `outbox.retries` increments on each failure; after `retries >= 10`, row is logged + skipped (left for ops/SRE). DLQ table is v2 tech-debt.
- **R1.7 lock**: v1 uses Redis **pub/sub** (not Streams). The `outbox` table IS the persistence layer; Redis is just the wakeup mechanism. v2+ migrates to Streams or Kafka for consumer groups + replay.
- Test: kill relayer mid-batch via `task.cancel()` AFTER publish-batch but BEFORE update-batch (R1.5 lock) → next start re-publishes those rows → consumer dedup must handle

### AC6: Lag SLO (NFR-P)
- P95 lag from `outbox.occurred_at` to broker ACK < **1 second** under no load
- **Q1 lock — test methodology**: pytest fixture starts a Redis SUBSCRIBE on `opticloud.*` BEFORE writing outbox rows. Test writes N rows tagged with `_test_started_at` timestamp. SUBSCRIBE handler records `(received_at - occurred_at)` latencies. After all N received, assert P95 < 1000ms.
- Alert thresholds documented in story body for SRE handoff

### AC7: Tests
- **Unit**: mock Redis + mock Postgres connection → verify SELECT → publish → UPDATE flow
- **Integration**:
  - Start relayer + write 5 rows to outbox → assert all reach Redis subscriber within 2s
  - Write row + relayer publishes → kill before UPDATE → restart → row re-published (at-least-once)
  - LISTEN/NOTIFY: write row → assert published within 200ms (not waiting full 100ms poll)
- **Health endpoint test**: 200 when both deps up; 503 when Redis down

### AC8: Schema migration adds `outbox_new` trigger
- New file: `infra/local-init/04-outbox-trigger.sql`
- Creates `pg_notify('outbox_new', NEW.id::text)` AFTER INSERT trigger
- Idempotent (CREATE OR REPLACE FUNCTION + DROP IF EXISTS trigger then CREATE)
- Applied to docker-compose + CI

### AC9: Docker-compose integration
- Add `outbox-relayer` service to `docker-compose.yml`
  - Depends on postgres + redis
  - Env: DATABASE_URL, REDIS_URL
  - Restart: always
- **R1.4 lock**: Dockerfile at `apps/outbox-relayer/Dockerfile` — python:3.11-slim base + uv copy from workspace (mirror `apps/auth-service/Dockerfile` pattern if it exists, else create minimal: uv sync → CMD python -m outbox_relayer.main)
- Local dev: `docker-compose up` brings relayer alongside billing-service automatically
- Healthcheck wired in compose

### AC10: Quality gates (per `feedback_full_quality_gates`)
- `uv run ruff check .` clean
- `uv run ruff format --check .` clean
- `uv run mypy apps packages` clean
- All Python tests pass + no regression
- Docker build succeeds for outbox-relayer image (if Dockerfile)

## Tasks

### T1: outbox-relayer service bootstrap (1 hour)
1. `apps/outbox-relayer/pyproject.toml` (workspace member; deps: opticloud-shared, asyncpg>=0.29, redis>=5.0 (D3 lock), fastapi>=0.115 for health, prometheus-client>=0.21, uvicorn[standard]>=0.30)
- **DR1 lock**: Dockerfile mirrors `apps/auth-service/Dockerfile` pattern (python:3.12-slim-bookworm two-stage builder + tini; PORT=9001; CMD `python -m outbox_relayer.main`). The relayer is python:3.12 to match auth-service (not 3.11; uv workspace handles both).
- **DR5 lock**: `main.py` ends with `if __name__ == "__main__": asyncio.run(_run())` so `python -m outbox_relayer.main` works.
- **DR6 lock**: LISTEN channel name hardcoded as `"outbox_new"` (PostgreSQL identifier; no env var).
2. **D4 lock — file split**:
   - `src/outbox_relayer/__init__.py`
   - `src/outbox_relayer/main.py` — entrypoint, signal handling, asyncio.gather
   - `src/outbox_relayer/config.py` — settings
   - `src/outbox_relayer/db.py` — asyncpg connection + LISTEN setup
   - `src/outbox_relayer/broker.py` — Redis client + publish helper
   - `src/outbox_relayer/relayer.py` — orchestration loop (the polling logic)
   - `src/outbox_relayer/health.py` — FastAPI app with /healthz, /readyz, /metrics
3. Workspace pyproject.toml add member
4. `uv sync --all-packages --extra dev` succeeds

### T2: Postgres + Redis clients (0.5 hour)
1. `relayer.py`: use raw asyncpg.connect (no SQLAlchemy needed — raw SQL is faster for this batch-oriented workload)
2. `redis.asyncio` client; channel naming util: `f"opticloud.{aggregate_type}.{event_type}"`
3. Connection retry/backoff on startup

### T3: Core polling loop (1.5 hour)
1. `relayer.py:run_poll_loop()`:
   - Outer loop: forever (until stop signal)
   - Each iteration: SELECT batch → publish each → UPDATE sent_at
   - Sleep 100ms (interruptible by NOTIFY)
2. Batch SELECT with FOR UPDATE SKIP LOCKED LIMIT 100
3. Per-row try/except: publish failure → log + don't mark sent (will retry next iteration)
4. Batch UPDATE all successful sent_at

### T4: LISTEN/NOTIFY (1 hour)
1. Separate asyncpg connection for LISTEN (can't share with regular queries)
2. asyncio.Event triggered on notification
3. Main loop awaits `asyncio.wait_for(event.wait(), timeout=0.1)` — early exit on NOTIFY or timeout
4. Trigger in 04-outbox-trigger.sql: `AFTER INSERT ON outbox FOR EACH ROW EXECUTE FUNCTION notify_outbox_new();`

### T5: Graceful shutdown + health (0.5 hour)
1. `health.py`: FastAPI app with `/healthz` checking both deps
2. Run uvicorn alongside the poll loop via `asyncio.gather`
3. SIGTERM handler: set stop_event; loop checks it after each batch

### T6: Tests (1.5 hour)
1. `tests/test_relayer_unit.py`: mock asyncpg + redis; verify polling logic
2. `tests/test_relayer_integration.py`: real Postgres + Redis (docker-compose):
   - 5-row happy path (write 5 → all reach Redis within 2s)
   - Kill-mid-batch recovery (**DR2 concrete outline**): monkey-patch `broker.update_sent` to raise CancelledError on first call AFTER `broker.publish_many` has succeeded; verify those rows STILL have `sent_at IS NULL` post-cancel; restart relayer; verify they're republished to a fresh subscriber
   - LISTEN/NOTIFY latency: write row → subscriber sees within 200ms (not the full 100ms poll window)
   - Lag P95 < 1s test per Q1 lock
3. `tests/test_health.py`: TestClient for /healthz + /readyz

### T7: Docker-compose + CI + Sprint sync (0.5 hour)
1. Add outbox-relayer service to docker-compose.yml
2. CI: new `outbox-relayer-test` job in ci.yml (Postgres + Redis services + tests)
3. Run full quality gates locally
4. Update sprint-status.yaml
5. Commit + PR

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Postgres LISTEN connection drops silently | Heartbeat ping every 30s; reconnect with exponential backoff |
| Redis publish fails for half the batch | Per-row try/except + log + leave sent_at NULL; row retried next iteration |
| Relayer crash mid-batch (after publish, before UPDATE) | Outcome: at-least-once delivery; documented in AC5; consumer dedup |
| Postgres FOR UPDATE SKIP LOCKED contention with multiple relayer instances | Acceptable for v1 single instance; v2+ multi-replica safe by design (SKIP LOCKED prevents double-claim) |
| Outbox table grows unbounded | M2.3 cron archival (separate story; runs daily delete WHERE sent_at < NOW() - 30d) |
| docker-compose restart loop spam | Healthcheck + restart-on-failure (not always); structured log makes diagnosis fast |

## Non-Functional Requirements Mapping

- **NFR-R4** (对账误差 = 0): outbox events are audit-grade; this story ensures they're DELIVERED, not just written
- **NFR-P1** (P95 < 300ms HTTP): relayer is async/background; no HTTP path
- **NFR-A1** (PIPL): outbox payloads contain pointers + state names only (per ADR-0001 §Security); no PII published
- **NFR-S1** (TLS): Redis URL supports TLS in prod (`rediss://`)
- **P33** Outbox / **P56** Sidecar / **C12** separate-from-business: this is the implementation

## Definition of Ready

- ✅ ADR-0002 locks design (poll + LISTEN/NOTIFY + Redis)
- ✅ 5.A.0a/5.A.1 are writing outbox rows
- ✅ docker-compose has Postgres + Redis running
- ✅ All 4 review rounds applied + locked

## Definition of Done

- All 10 ACs pass
- CI green on PR
- Local docker-compose: charge confirm → see Redis SUBSCRIBE catch the event
- Sprint-status.yaml updated to `done`

## Sign-off (story-level)

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| SRE | TBA | ☐ | — |
| Architect | proposed by AI | ☐ | — |
| Billing Lead | TBA | ☐ | — |

> Owner committee deferred per M0 skip.
