---
story_key: 5-a-0a-saga-implementation
epic_num: 5
story_num: A.0a
epic_name: Billing — Credits & Saga
status: done
priority: 🔴 Critical (N5 unlock — gates 5.A.1 J1 charge modal + 5.A.0b contract tests + M2.2a 50 scenarios)
sizing: L (5-8 hours; bootstrap billing-service + 3 tables + orchestrator + compensation handlers + tests)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-18
sources:
  - _bmad-output/planning/epics.md (Story 5.A.0a — RE6 fix)
  - docs/adr/0001-saga-pattern.md (Hybrid Saga; 7 states / 7 transitions; 4 invariants; 4 Compensation values)
  - docs/adr/0002-outbox-relayer-deployment.md (sidecar relayer — orchestrator only writes outbox row, relayer publishes)
  - _bmad-output/planning/architecture.md v2.2 (Concern #13 + P33 Outbox + P23 Idempotency-Key + P36 Repository Pattern)
  - _bmad-output/planning/prd.md v1.1 (NFR-R4 计费对账误差 = 0 / FR B1-B13)
  - packages/shared-py/opticloud_shared/saga/state_machine.py (M2.0 skeleton — single source of truth for State/Transition/Compensation)
  - infra/local-init/01-schema.sql (existing outbox table — reuse)
dependencies:
  upstream:
    - m2-0-saga-spike (done) — ADR-0001 + state machine skeleton
    - 0-1-monorepo-scaffold (done) — uv workspace pattern
    - 0-2-docker-compose (done) — Postgres available locally
    - 0-6-auth-scaffold (done) — sqlalchemy 2.0 async pattern + Base
  downstream:
    - 5-a-0b-saga-contract-fixtures — exercises orchestrator via fixtures
    - 5-a-0c-saga-cross-epic-dryrun — uses orchestrator from chat/solver
    - 5-a-1-j1-credits-charge-modal — HTTP API + UI on top of orchestrator
    - m2-1-outbox-relayer — relayer consumes outbox rows orchestrator writes
    - m2-2a-billing-critical-tests — 50 scenarios target this orchestrator
---

# Story 5.A.0a — Saga Orchestrator Implementation

## User Story

**As** the billing platform owner
**I want** a DB-backed Saga orchestrator that drives Credits charge / refund / compensation through the 7-state machine
**so that** every solve / chat / repro call produces a deterministic, audited financial state transition with NFR-R4 (对账误差 = 0) guaranteed.

## Why this story

M2.0 produced the **specification** (ADR-0001 + state enum + transition matrix + 4 invariants). Story 5.A.0a produces the **engine** that actually applies transitions, writes to the credit ledger, persists Saga state, and emits outbox events — all in a single DB transaction (P33).

Without 5.A.0a:
- 5.A.1 J1 charge modal has nothing to call → J1 vertical slice incomplete
- M2.1 outbox relayer has no producer → sidecar can't be tested end-to-end
- M2.2a 50 critical scenarios have no system-under-test
- 5.A.0b contract fixtures have nothing to validate

## Out of scope

- **HTTP API endpoints** (POST /v1/charge etc.) — Story 5.A.1
- **Topup flow** (FR B11 余额永不过期) — Story 5.A.6
- **Refund UI** — Story 5.C.2
- **Pre-charge guard rules** (FR B5 P5 warning modal) — Story 5.A.5
- **Outbox relayer process** itself — Story M2.1

## Acceptance Criteria

### AC1: billing-service skeleton exists
- `apps/billing-service/pyproject.toml` declares workspace member
- `apps/billing-service/src/billing_service/__init__.py` + `main.py` (placeholder FastAPI app; no routes yet)
- Workspace `pyproject.toml` includes billing-service in `[tool.uv.workspace].members`
- `uv sync --all-packages --extra dev` succeeds with no errors

### AC2: schema migration adds 3 tables
- `infra/local-init/03-billing-schema.sql` creates:
  - `saga_instances` (id UUID v7, saga_type VARCHAR, current_state VARCHAR (State enum value), user_id UUID, idempotency_key VARCHAR, retries INT, last_error TEXT NULL, payload_ref JSONB, created_at, updated_at)
  - `credit_transactions` (id UUID, user_id UUID FK, saga_id UUID FK, amount NUMERIC(12,4), kind VARCHAR (charge/refund/topup/adjustment), currency VARCHAR(3) default 'CNY', metadata JSONB, created_at)
  - `idempotency_keys` (key VARCHAR PK, user_id UUID, request_body_hash CHAR(64), response_body JSONB NULL, saga_id UUID NULL, expires_at TIMESTAMPTZ, created_at)
- **A2 fix** (ADR-0001 §Security): `saga_instances.payload_ref` MUST contain only POINTERS (e.g., `{"optimization_id": "uuid", "task_type": "lp"}`) — NEVER amounts, never raw payload. Money lives in `credit_transactions` exclusively. Schema comment enforces this convention.
- Indexes:
  - `saga_instances(user_id, current_state)` — admin lookups
  - `saga_instances(idempotency_key)` UNIQUE WHERE NOT NULL — dedup
  - `credit_transactions(user_id, kind, created_at DESC)` — ledger queries
  - `credit_transactions(saga_id)` — saga → tx fan-out
  - `idempotency_keys(expires_at)` — cleanup cron (R1.1 fix from round 1)
- Schema applied successfully against docker-compose Postgres
- E2E CI workflow includes the new SQL file in its schema-apply step

### AC3: SagaOrchestrator class implemented
- Located: `apps/billing-service/src/billing_service/saga_orchestrator.py`
- Public surface:
  ```python
  class SagaOrchestrator:
      def __init__(self, session: AsyncSession) -> None: ...
      async def start(self, saga_type: str, user_id: UUID, idempotency_key: str, payload: dict) -> SagaInstance: ...
      async def apply(self, saga_id: UUID, trigger: str, context: dict | None = None) -> SagaInstance: ...
      async def get(self, saga_id: UUID) -> SagaInstance: ...
  ```
- Uses `opticloud_shared.saga` (no duplicate State / Transition definitions)
- Constructor takes only `session` for now; clock / logger / metrics DI deferred to Story 5.A.0c per minimum-skeleton principle (R1.2 fix)
- `apply()` checks current State, finds valid Transition matching `trigger`, applies in a single SQL transaction:
  1. Update `saga_instances.current_state`, `updated_at`
  2. Insert `credit_transactions` row when transition triggers a charge or refund
  3. Insert `outbox` row with event payload (P33 transactional dual-write)
- Invalid transitions raise `InvalidSagaTransition` (typed exception with from/to/trigger)
- Terminal-state Sagas reject all further `apply()` calls (raises `SagaTerminal`)

### AC4: Idempotency enforced (P23) — start() de-duplication
- `start()` checks `idempotency_keys` table first
  - Same key + same body hash → returns existing SagaInstance (no new charge)
  - Same key + different body hash → raises `IdempotencyConflict` with 409 semantics
  - New key → inserts row with `saga_id` pointer, proceeds
- TTL 24h enforced via `expires_at`; expired rows treated as new
- **Body never persisted** (S2): only SHA-256 hash stored in `request_body_hash`
- **Concurrency-safe (Q2 fix)**: idempotency_keys has UNIQUE constraint on (key); 2 concurrent start() with same key — Postgres serialization → one INSERT succeeds, the other gets IntegrityError → orchestrator catches, re-SELECTs, returns existing saga. Test: `asyncio.gather(start(K), start(K))` must yield only 1 row in saga_instances.
- **Distinct from AC10** (R1.3 + R1.6 fix): AC4 dedups creation; AC10 dedups transitions on existing Saga

### AC5: Compensation handlers implemented (caller-context driven)
- **Dispatch rule (DR3 lock)**: orchestrator's `apply(saga_id, trigger, context=None)` does NOT auto-invoke compensation on side-effect failure. Caller (HTTP layer, 5.A.1) is responsible for deciding "this transition failed; please run compensation X" and explicitly calling `apply(saga_id, "user_cancel")` or `apply(saga_id, "downstream_reject_late")`. Each compensation has a dedicated trigger in the transition matrix — calling those triggers IS the compensation invocation.
- This keeps the orchestrator pure: no hidden retries, no automatic state changes, no timer-based compensation in 5.A.0a (timer-based deferred to v1.5 + M2.1 sidecar with proper background worker).
- 4 handlers matching `opticloud_shared.saga.Compensation` enum:
  - `MARK_FAILED`: on `PENDING → RESERVED` timeout → transition to FAILED, no credit movement
  - `REFUND_AUTO`: on `RESERVED → CHARGED` fail → emit refund credit_transaction (+amount), transition to REFUNDED
  - `RETRY_OUTBOX`: orchestrator-side only flags `saga.retries++` + writes outbox row (idempotent ON CONFLICT DO NOTHING via event_id). **Sidecar (M2.1) owns the actual delivery retry** — out of scope here (R1.4 fix)
  - `ESCALATE_OPS`: on `CHARGED → ROLLED_BACK` downstream late reject → emit refund + audit log + flag for manual SRE review
- Each handler is a pure function: `(saga, transition, db) → side_effects`; no hidden state

**5.A.0a stop-point**: Saga can reach **CHARGED** terminal-equivalent. The `CHARGED → COMPLETED` transition (triggered by outbox-delivered event) is implemented but only callable from M2.1 sidecar in production; 5.A.0a integration tests manually trigger it to validate the pathway (R1.4 fix).

### AC6: 4 ADR-0001 invariants verified by DB-backed tests
- M2.0 already has pure-function property tests in `packages/shared-py/tests/test_saga_state_machine.py` — those stay.
- This story adds DB-backed orchestrator-level invariant tests in `apps/billing-service/tests/test_invariants.py` that import the *same invariant names* and assert them against the live orchestrator (R1.5 fix):
  - I1 no-dangling-state: random sequence of `apply()` calls ends with `saga.current_state ∈ State` enum
  - I2 refund ≤ charge: `SUM(amount WHERE kind='refund' AND saga_id=S)` ≤ `SUM(amount WHERE kind='charge' AND saga_id=S)`. **Edge case (Q3 fix)**: if no charge occurred (e.g., PENDING → FAILED via balance_insufficient), refund must also = 0; invariant trivially holds (0 ≤ 0).
  - I3 terminal stickiness: any `apply()` after terminal raises SagaTerminal (DB-backed; ensures the SELECT before transition sees terminal)
  - I4 idempotency: `start(key, body)` twice returns identical saga_id, identical credit_transactions count
- All 4 pass with `@settings(max_examples=20, deadline=2000)` to keep CI fast

### AC7: Integration test full happy-path + negative cases
- Test fixture spins real Postgres (docker-compose) — already running in CI's `services: postgres`
- **Happy path**: `start(saga_type="solve_charge", user_id=U, idem_key=K, payload={...})` → returns PENDING
- `apply(saga_id, "reserve")` → RESERVED
- `apply(saga_id, "service_success")` → CHARGED + 1 row in credit_transactions (kind=charge)
- `apply(saga_id, "outbox_delivered")` → COMPLETED + 1 row in outbox
- **Negative cases** (Q1 fix):
  - `apply(saga_id, "nonexistent_trigger")` → `InvalidSagaTransition`
  - `apply(saga_id, "service_success")` on PENDING (not RESERVED) → `InvalidSagaTransition`
  - `apply(completed_saga_id, "reserve")` → `SagaTerminal`
- All in 1 DB session; rollback on assertion failure

### AC8: Integration test failure compensation
- Same setup as AC7, but trigger `RESERVED → REFUNDED` (user_cancel)
- Assert: credit_transactions has refund row matching original charge (amount equal, kind=refund)
- Assert: outbox has refund event
- Assert: saga state = REFUNDED (terminal)

### AC9: Audit log entries (FR O3)
- Every `apply()` writes 1 `audit_logs` row: actor=system, action=`billing.saga.{transition.trigger}`, resource_type=saga_instance, resource_id=saga_id, metadata={from_state, to_state, retries}
- No PII in audit_logs metadata (only state + IDs per ADR-0001 §Security)

### AC10: apply() is transition-idempotent (R1.6 fix)
- `apply()` is idempotent within a single transition. Concrete example:
  ```python
  await orch.apply(saga_id, "reserve")  # PENDING → RESERVED, debits hold
  await orch.apply(saga_id, "reserve")  # NO-OP — already RESERVED, no second debit
  ```
- Mechanism: orchestrator computes the unique "expected next state" from current state + trigger; if current_state == expected_next_state, return SagaInstance unchanged
- Concurrency: SELECT ... FOR UPDATE on saga_instances row before reading current_state to prevent TOCTOU

### AC11: Full quality gates green (NEW — per `feedback_full_quality_gates`)
Run BEFORE committing:
- `uv run ruff check .` → 0 errors
- `uv run ruff format --check .` → 0 changes needed
- `uv run mypy apps packages` → 0 errors
- `uv tool run pre-commit run --all-files` → 0 failures
- `pnpm -C apps/web build` → 0 errors (we don't touch frontend, but verify no regression)
- All Python tests pass (no regression)

## Tasks

### T1: billing-service bootstrap (1.5 hour)
1. Create `apps/billing-service/pyproject.toml` — workspace member, DR1 lock (exact deps):
   ```toml
   [project]
   name = "opticloud-billing-service"
   version = "0.0.1"
   requires-python = ">=3.11,<3.13"
   dependencies = [
     "opticloud-shared",
     "sqlalchemy[asyncio]>=2.0.30",
     "asyncpg>=0.29",
     "fastapi>=0.115",
     "pydantic>=2.7",
     "pydantic-settings>=2.5",
     "uvicorn[standard]>=0.30",
   ]
   [project.optional-dependencies]
   dev = ["pytest>=8.3", "pytest-asyncio>=0.24", "httpx>=0.27"]
   [tool.uv.sources]
   opticloud-shared = { workspace = true }
   ```
2. Create `apps/billing-service/src/billing_service/{__init__.py, main.py, config.py, db.py, models.py, exceptions.py}` — minimal FastAPI app + sqlalchemy Base + DI plumbing
3. Add to workspace root `pyproject.toml` `[tool.uv.workspace].members`
4. Run `uv sync --all-packages --extra dev` — verify success

### T2: schema migration (1 hour)
1. Create `infra/local-init/03-billing-schema.sql` with 3 tables + indexes
2. Add `SET LOCAL statement_timeout = '1000ms';` to functions that use SELECT FOR UPDATE (SR3 fix)
3. Add to docker-compose volumes (auto-loads on Postgres init)
4. Update CI `.github/workflows/ci.yml :: auth-service-test` schema-apply step to include 03-billing
5. Update `.github/workflows/e2e.yml :: Apply schema` step
6. Test locally: docker-compose down && up → schema applied

### T3: SQLAlchemy models (1 hour)
1. `billing_service/models.py`: SagaInstance, CreditTransaction, IdempotencyKey (mirror schema)
2. Per-service Base (R1.7 decision — matches auth-service `models.py:28 class Base(DeclarativeBase)` pattern). Each service migrates schema independently via raw SQL files; SQLAlchemy models map to existing tables.
3. Wire async_session_maker pattern (copy from auth-service/db.py)
4. mypy clean

### T4: SagaOrchestrator core (2 hours)
1. `billing_service/saga_orchestrator.py` — class + public API per AC3
2. Import State/Transition/Compensation from opticloud_shared.saga
3. Transactional dual-write pattern: 1 session, multiple INSERT/UPDATE, 1 commit
4. Use `select(SagaInstance).where(id=X).with_for_update()` before transition decisions (D3 fix)
5. `billing_service/exceptions.py`: `InvalidSagaTransition(from_state, to_state, trigger)` / `SagaTerminal(saga_id, current_state)` / `IdempotencyConflict(key, hash_a, hash_b)` (D4 fix)
6. Manual OTel span: `with trace.get_tracer(__name__).start_as_current_span("saga.apply") as span: span.set_attribute("saga.from", from_state); ...` (SR1 fix)
7. mypy clean strict

### T5: Compensation handlers (1 hour)
1. `billing_service/compensations.py` — 4 handler functions
2. Dispatch table: `Compensation → handler` mapping
3. Called from orchestrator on transition failure
4. Each handler unit-tested in isolation

### T6: Tests (1.5 hour)
1. Unit: state_machine property tests already in shared-py (reuse) + orchestrator function tests against real session (DR4 lock — no mock; use nested-transaction rollback)
2. **conftest fixture pattern (DR4 lock)**: each test runs in a savepoint that auto-rolls-back on teardown — no DB pollution between tests:
   ```python
   @pytest_asyncio.fixture
   async def session(engine):
       async with engine.connect() as conn:
           trans = await conn.begin()
           async with AsyncSession(bind=conn, expire_on_commit=False) as s:
               nested = await conn.begin_nested()
               yield s
               await trans.rollback()
   ```
3. Integration: `apps/billing-service/tests/test_saga_integration.py` — 6+ scenarios (AC7 happy + 3 negatives, AC8 refund, AC4 idempotency, AC10 retry-safe)
4. Invariants: `apps/billing-service/tests/test_invariants.py` — 4 Hypothesis property tests per AC6
5. All Hypothesis tests pass with `--hypothesis-show-statistics`

### T7: Full quality gates + sprint sync (0.5 hour)
1. Run all gates from AC11
2. Fix everything
3. Update sprint-status.yaml: **rename key** `5-a-0a-saga-state-diagram` → `5-a-0a-saga-implementation` + mark `done` (DR7 fix)
4. Commit + push + PR

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Schema migration breaks E2E run (auth-service uses schema too) | 03-billing only adds NEW tables; 01-schema unchanged; auth tests unaffected |
| Two declarative bases conflict (auth-service Base + billing Base) | Use ONE Base in `opticloud_shared.db_base` (added in T1); both services import |
| Hypothesis tests slow CI | `@settings(max_examples=20, deadline=2000)` in integration tests; unit prop tests use defaults |
| Orchestrator + outbox dual-write race under concurrency | Use `SELECT ... FOR UPDATE` on saga_instances row before apply(); rely on Postgres serializable isolation |
| Compensation handlers introduce side effects mid-transaction | Strict contract: handlers receive `session: AsyncSession`, MUST NOT commit; orchestrator commits once at end |

## Non-Functional Requirements Mapping

- **NFR-R4** (对账误差 = 0): credit_transactions table is double-entry source-of-truth; sum(charge) - sum(refund) per user must equal current Credits balance
- **NFR-S1** (TLS+TDE+AES-256 GCM): payload_ref column may contain sensitive metadata → keep behind TDE; saga_instances PII redaction (ADR-0001 §Security)
- **NFR-P1** (HTTP P95 < 300ms): apply() must complete in < 50ms median (5+10ms transition latencies; 30ms DB roundtrip budget)
- **NFR-A1** (PIPL): no raw PII in saga_instances.payload_ref; audit_logs metadata limited to state + IDs

## Definition of Ready (verified for dev start)

- ✅ ADR-0001 (Saga pattern) exists + accepted
- ✅ M2.0 state machine skeleton in `opticloud_shared.saga`
- ✅ docker-compose Postgres + 01-schema.sql works locally
- ✅ auth-service pattern (sqlalchemy 2.0 async + DeclarativeBase) to copy
- ✅ shared-py Hypothesis strategies (`monetary_amounts`, `uuids`) available from Story 0.5b
- ✅ All 4 review rounds applied + locked

## Definition of Done

- All 11 ACs pass
- CI green on PR
- Sprint-status.yaml updated to `done`
- ADR-0001 marked as referenced (no changes to ADR itself)
- Code-review with FULL quality gates documented in commit body

## Sign-off (story-level)

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Architect | proposed by AI | ☐ | — |
| Billing Lead | TBA | ☐ | — |
| SRE | TBA | ☐ | — |

> Owner committee deferred per M0 skip; story ready for dev now.
