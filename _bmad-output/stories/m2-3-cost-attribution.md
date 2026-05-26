---
story_key: m2-3-cost-attribution
epic_num: 0
story_num: M2.3
epic_name: Foundation - NFR-COST
status: done
priority: Critical (G3 Critical Gap; M2 minimum viable cost attribution unlocks M3 cost red-line automation)
sizing: M-L (~8-10 hours; shared package + DB table + solver hook + tests + CI schema wiring)
type: implementation + observability + test
created_by: bmad-create-story
created_at: 2026-05-26
sources:
  - [Source: D:/优化预测网站/_bmad-output/planning/epics.md:177-183]
  - [Source: D:/优化预测网站/_bmad-output/planning/epics.md:334-336]
  - [Source: D:/优化预测网站/_bmad-output/planning/epics.md:765-768]
  - [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1047-1065]
  - [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1601-1606]
  - [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1653-1656]
  - [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1821-1835]
  - [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:408]
  - [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:1992]
  - [Source: D:/优化预测网站/_bmad-output/stories/5-a-4-per-formula-charging-capped.md]
  - [Source: D:/优化预测网站/_bmad-output/stories/m2-2c-billing-reconciler-job.md]
  - [Source: D:/优化预测网站/apps/solver-orchestrator/src/solver_orchestrator/routes.py]
  - [Source: D:/优化预测网站/apps/solver-orchestrator/src/solver_orchestrator/models.py]
  - [Source: D:/优化预测网站/apps/billing-service/src/billing_service/routes.py]
  - [Source: D:/优化预测网站/.github/workflows/ci.yml]
dependencies:
  upstream:
    - 5-a-4-per-formula-charging-capped (done) - solver has actual `result.solve_seconds`, `X-Billing-Charge-Id`, and billing finalize context
    - m2-2c-billing-reconciler-job (done) - failed finalize retry context already stores billing elapsed seconds/status
    - m2-1-outbox-relayer (done) - eventing foundation exists but is not required for M2 minimum
  contextual:
    - 5-a-8-cost-telemetry-hook (backlog) - full Saga charge cost hook remains downstream
    - 9-3-nfr-cost-alerts (backlog) - NFR-COST red-line alert automation remains downstream
    - 4-a-1-nl-chat-input-internal-beta (backlog) - chat-service does not exist yet; this story must not invent it
  downstream:
    - M3 G3 full: Grafana dashboard, monthly alert rules, DingTalk/Linear red-line automation
---

# Story M2.3 - Cost-attribution middleware

Status: done

## User Story

**As** the NFR-COST owner / finance operator,
**I want** a shared `cost_telemetry` package and durable `cost_attribution` table that can record per-tenant usage for LLM tokens, GPU seconds, and solver seconds,
**so that** M2 has real per-tenant cost evidence and M3 can build NFR-COST red-line alerts without redesigning instrumentation.

## Why

G3 is a critical gap: without per-tenant and per-service cost attribution, the product is commercially blind against PRD §11.2 red lines such as LLM/monthly revenue >= 30%, GPU idle >= 50%, provider share >= 50%, and refund/issued credits >= 5%.

The epics text mentions `chat-service` LLM token recording, but this repository does not yet have `apps/chat-service`. The M2 minimum must therefore ship the durable substrate and wire it into the service that exists today: `solver-orchestrator`, where `result.solve_seconds` is already measured for authenticated optimization calls. The same shared API must also support future `chat-service` LLM token and GPU second records, with tests proving the call shape before those services exist.

This story deliberately separates M2 minimum from M3 full red-line automation:

- M2 minimum: `packages/shared-py/opticloud_shared/cost_telemetry`, `cost_attribution` table, solver hook for `solver_seconds`, unit/integration tests, CI schema wiring.
- M3 full: Prometheus alert rules, Grafana investor dashboard, DingTalk robot, Linear ticket automation, revenue joins, GPU idle-rate computation.

## Out of Scope

- Creating `apps/chat-service`, `apps/gpu-service`, or any LLM provider integration.
- NFR-COST red-line breach evaluation, Prometheus alert rules, Grafana dashboard JSON, DingTalk/Linear integrations, or monthly investor reporting.
- Revenue, invoice, subscription, provider-share, refund-rate, or runway computations.
- Changing charge amounts, credit ledger semantics, or Saga transitions.
- Recording raw prompts, model outputs, API keys, JWTs, phone/email, solver input matrices, or user PII inside cost attribution metadata.
- Backfilling historical rows from existing optimizations.
- Requiring billing to succeed before cost attribution is recorded; solver attribution should be best-effort and must not block successful solve responses.

## Acceptance Criteria

1. `infra/local-init/10-cost-attribution.sql` idempotently creates `cost_attribution` with columns: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `tenant_id UUID NOT NULL`, `service VARCHAR(64) NOT NULL`, `cost_unit VARCHAR(32) NOT NULL`, `value NUMERIC(18, 6) NOT NULL CHECK (value >= 0)`, `source_id UUID NULL`, `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`, `recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`. It adds `CHECK (cost_unit IN ('llm_token','gpu_second','solver_second'))`, index `(tenant_id, service, cost_unit, recorded_at DESC)`, and index `(source_id)` where `source_id IS NOT NULL`.
2. SQLAlchemy models expose `CostAttribution` in both `apps/solver-orchestrator/src/solver_orchestrator/models.py` and, if needed for billing tests or future use, `apps/billing-service/src/billing_service/models.py` without creating a second table name or mismatched column names.
3. Shared package `packages/shared-py/opticloud_shared/cost_telemetry/` provides:
   - `CostUnit` enum with values `llm_token`, `gpu_second`, `solver_second`.
   - `CostTelemetryEvent` dataclass/Pydantic model with `tenant_id`, `service`, `cost_unit`, `value`, optional `source_id`, `metadata`, optional `recorded_at`.
   - `validate_cost_event(event)` or equivalent constructor validation that rejects negative value, unsupported unit, empty service, non-object metadata, and metadata keys likely to contain PII/secrets (`prompt`, `completion`, `api_key`, `authorization`, `jwt`, `phone`, `email`, `password`, `token`).
   - `record_cost_event(session, model_cls, event)` async helper that inserts one row using the caller service's ORM model and flushes, but does not commit.
4. The shared helper is service-agnostic: it must not import `solver_orchestrator`, `billing_service`, FastAPI app objects, or service settings. Services pass their local `CostAttribution` ORM class explicitly.
5. `solver-orchestrator` records one `solver_second` attribution row for each authenticated `POST /v1/optimizations` LP request after solving reaches a terminal result (`optimal`, `infeasible`, `unbounded`, `timeout`, or validation `error`) and an `Optimization` row exists. The row uses `tenant_id=user_id`, `service='solver-orchestrator'`, `cost_unit='solver_second'`, `value=result.solve_seconds`, `source_id=optimization.id`, and metadata containing only safe low-cardinality fields such as `task_type`, `solver`, `status`, and `model_provider`.
6. Cost attribution failures are best-effort. If insert/validation fails after the solve result is available, solver logs a structured warning and still returns the original response. It must not hide the solve result, mutate billing state, or convert success into 5xx.
7. Idempotency behavior is closed: replaying an existing successful `Idempotency-Key` result must not insert an additional cost row. New first-run successful requests insert exactly one row. Failed/infeasible first-run requests that persist an optimization row also insert exactly one row.
8. `POST /v1/optimizations/demo` remains stateless and never writes `cost_attribution`, because it has no tenant identity and currently does not persist an `Optimization`.
9. The M2 minimum API supports future chat and GPU instrumentation without those services existing. Shared-package tests must create valid events for `service='chat'` + `cost_unit='llm_token'` and `service='sandbox-runner'` + `cost_unit='gpu_second'`, and assert they validate/serialize without service imports.
10. CI and local schema setup are wired: `.github/workflows/ci.yml` path filters include `infra/local-init/10-cost-attribution.sql`; solver test schema applies it; shared-py changes trigger solver tests through existing shared-py cascade.
11. Tests cover:
    - SQL model insert/query for `cost_attribution`.
    - Shared validation happy paths for all 3 units.
    - Shared validation rejects negative values, unsupported service/unit, non-object metadata, and blocked metadata keys.
    - Authenticated solver success inserts exactly one row with correct tenant/service/unit/value/source_id.
    - Solver infeasible or validation-result path inserts one row when an `Optimization` row exists.
    - Idempotency replay does not duplicate rows.
    - Demo route writes zero rows.
    - Cost insert failure is non-blocking and original solve response still returns.
12. Quality gates pass:
    - `uv run ruff check packages/shared-py apps/solver-orchestrator`
    - `uv run mypy packages/shared-py apps/solver-orchestrator/src/solver_orchestrator`
    - `uv run pytest packages/shared-py/tests apps/solver-orchestrator/tests -q`
    - `git diff --check`

## Tasks / Subtasks

- [x] Task 1: Persistence and schema wiring (AC: 1, 2, 10)
  - [x] Add `infra/local-init/10-cost-attribution.sql`
  - [x] Add `CostAttribution` ORM model in solver-orchestrator
  - [x] Add billing model only if implementation needs it; otherwise keep billing untouched and document future reuse
  - [x] Update CI path filters and solver schema apply step

- [x] Task 2: Shared `cost_telemetry` package (AC: 3, 4, 9)
  - [x] Create `packages/shared-py/opticloud_shared/cost_telemetry/__init__.py`
  - [x] Add enum/model/helper with no service imports
  - [x] Add shared-py tests for validation and future chat/GPU event shape

- [x] Task 3: Solver hook (AC: 5, 6, 7, 8)
  - [x] Import shared helper and local `CostAttribution` model
  - [x] Record after `result.solve_seconds` is known and before returning terminal response
  - [x] Skip cached idempotency replay and `/optimizations/demo`
  - [x] Wrap attribution insert in non-blocking error handling that preserves original route behavior

- [x] Task 4: Solver tests (AC: 7, 8, 11)
  - [x] Extend authenticated optimization tests to assert one row on success
  - [x] Add infeasible/failed terminal row assertion
  - [x] Add idempotency replay no-duplicate assertion
  - [x] Add demo zero-row assertion
  - [x] Add non-blocking insert failure test via monkeypatch

- [x] Task 5: Quality gates and story tracking (AC: 12)
  - [x] Run focused ruff/mypy/pytest/diff-check
  - [x] Complete Dev Agent Record and File List
  - [x] Move story/sprint through `in-progress`, `code-review`, and `done`
  - [ ] Commit, push, and sync GitHub

## Dev Notes

- Place shared code under `packages/shared-py/opticloud_shared/cost_telemetry`, matching the architecture requirement `shared-py/cost_telemetry` while respecting the actual package root.
- Do not create a new standalone `shared_py` import path. Existing shared imports use `opticloud_shared.*`.
- Use SQLAlchemy async sessions already passed through solver routes. The helper should call `session.add(row)` and `await session.flush()`, not `commit()`.
- For non-blocking attribution errors, prefer `await session.rollback()` only if the insert failed before the route's final commit and the session transaction is poisoned; then preserve the ability to return the original response. If rollback would discard the just-created `Optimization`, isolate attribution in a nested transaction (`begin_nested`) or insert after the primary route state is flushed in a way tests prove safe.
- Do not store high-cardinality or sensitive payloads in `metadata`. Keep it to `task_type`, `solver`, `status`, `model_provider`, maybe `model_kind`.
- The existing `Optimization` schema has no FK to users; `cost_attribution.tenant_id` should be a UUID without FK for cross-service portability.
- `value` for `solver_second` should be Decimal-safe. Convert via `Decimal(str(result.solve_seconds))`, not `Decimal(float)`.
- Existing route currently returns early for non-LP before solving and before terminal shared cleanup. If non-LP returns 501 after an `Optimization` row is created, either record `solver_second=0` with status `not_implemented` or explicitly exclude it in implementation and tests. Preferred M2 scope: record only when a solver result object exists.
- Existing idempotency replay returns cached completed optimizations before creating a new `Optimization`; that path must remain attribution-free.
- Keep billing-service ledger and price computation untouched. This story is observability/cost evidence, not user-visible billing.
- CI currently applies `01`, `02`, `03`, `05`, `07`, `08` for solver. Add `10-cost-attribution.sql` to solver CI. Billing CI only needs it if billing model/tests touch the table.

### Project Structure Notes

- Migration: `infra/local-init/10-cost-attribution.sql`
- Shared package: `packages/shared-py/opticloud_shared/cost_telemetry/__init__.py`
- Shared tests: `packages/shared-py/tests/test_cost_telemetry.py`
- Solver model/hook: `apps/solver-orchestrator/src/solver_orchestrator/models.py`, `routes.py`
- Solver tests: `apps/solver-orchestrator/tests/test_billing_integration.py` or new `test_cost_attribution.py`
- CI: `.github/workflows/ci.yml`

### References

- [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1047-1065]
- [Source: D:/优化预测网站/_bmad-output/planning/epics.md:765-768]
- [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1821-1835]
- [Source: D:/优化预测网站/_bmad-output/planning/architecture.md:1992]
- [Source: D:/优化预测网站/apps/solver-orchestrator/src/solver_orchestrator/routes.py]
- [Source: D:/优化预测网站/.github/workflows/ci.yml]

## Three-Round Story Review

### Round 1: Data Consistency Review

Scope: `cost_attribution` schema, units, tenant identity, metadata, numeric precision, and source linkage.

Findings and fixes:

- [x] Unit naming drift risk: epics use `LLM token / GPU sec / 求解 sec`, while code needs stable enum strings. Fixed by locking `cost_unit` values to `llm_token`, `gpu_second`, and `solver_second` in SQL and shared enum.
- [x] Tenant identity ambiguity: epics say per-tenant but current services use `user_id` as tenant surrogate. Fixed by defining `tenant_id=user_id` for M2 and avoiding a FK so future org/team tenancy can migrate without schema coupling.
- [x] Numeric precision risk: seconds and token counts could be stored as float strings inconsistently. Fixed by requiring `NUMERIC(18,6)` and Decimal conversion via `Decimal(str(...))`.
- [x] Source closure gap: rows need to tie back to the event that generated cost. Fixed by adding optional `source_id` and requiring solver to use `optimization.id`.
- [x] Sensitive metadata risk: cost metadata could accidentally store prompts, API keys, phone/email, or solver payloads. Fixed by blocking known sensitive keys and limiting solver metadata to safe low-cardinality fields.

Round 1 result: PASS after story corrections.

### Round 2: Function Consistency / Drift Review

Scope: shared package boundaries, existing solver route flow, idempotency, billing Saga, and CI wiring.

Findings and fixes:

- [x] Nonexistent `chat-service` drift: original AC names chat-service, but repo has no chat-service. Fixed by not creating chat-service and instead testing shared API compatibility for future chat/LLM events.
- [x] Package path drift: architecture says `shared-py/cost_telemetry`, but actual import root is `opticloud_shared`. Fixed by requiring `packages/shared-py/opticloud_shared/cost_telemetry`.
- [x] Billing semantics drift: cost attribution must not alter credits ledger or Saga states. Fixed by making billing changes out of scope and solver hook best-effort.
- [x] Idempotency duplication risk: cached replay path could double-count usage if hook is placed too early. Fixed by requiring no attribution on existing idempotency replay and one row only on first-run terminal result.
- [x] CI schema drift: new table would be missing in solver CI. Fixed by requiring path filter and solver schema apply update.

Round 2 result: PASS after story corrections.

### Round 3: Boundary / Closure Review

Scope: terminal solve paths, demo route, attribution insert failure, transaction safety, and M3 handoff.

Findings and fixes:

- [x] Demo route ambiguity: demo solve has no tenant and is stateless. Fixed by explicitly requiring zero cost rows for `/optimizations/demo`.
- [x] Insert failure could poison the active DB transaction and lose the optimization row. Fixed by requiring nested transaction or equivalent test-proven isolation and non-blocking behavior.
- [x] Failed solve coverage gap: infeasible/unbounded paths return early after persisting an `Optimization`; cost row could be skipped. Fixed by requiring one row for persisted terminal solver-result failures.
- [x] Non-LP 501 scope gap: current route creates an `Optimization` then returns 501 without solver result. Fixed by preferring attribution only when a solver result exists and calling out non-LP behavior explicitly.
- [x] M3 alert closure risk: story could be mistaken as full G3 completion. Fixed by marking M3 red-line alerting, Grafana, DingTalk, Linear, revenue joins, and GPU idle computation as downstream.

Round 3 result: PASS after story corrections.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- `uv run ruff check packages/shared-py apps/solver-orchestrator` - passed
- `uv run mypy packages/shared-py apps/solver-orchestrator/src/solver_orchestrator` - passed
- `uv run pytest packages/shared-py/tests/test_cost_telemetry.py -q` - 15 passed
- `PYTHONPATH=packages/shared-py;apps/solver-orchestrator/src;packages/python-sdk/src uv run pytest apps/solver-orchestrator/tests/test_cost_attribution.py -q` - 5 passed
- `PYTHONPATH=packages/shared-py;apps/solver-orchestrator/src;packages/python-sdk/src uv run pytest apps/solver-orchestrator/tests -q` - 125 passed
- `uv run pytest packages/shared-py/tests -q` - 32 passed
- `git diff --check` - passed

### Completion Notes List

- Story created and reviewed in three rounds before implementation, per user-required process.
- Implemented idempotent `cost_attribution` schema and solver ORM mapping.
- Added service-agnostic `opticloud_shared.cost_telemetry` validation/insert helper with sensitive metadata key blocking.
- Wired authenticated solver terminal LP results to best-effort `solver_second` attribution using a nested transaction.
- Kept demo route stateless and idempotency replay attribution-free.
- Left billing-service model untouched because this M2 minimum implementation does not need billing-side writes.
- Post-implementation code review found 1 patch item and it was fixed: solver ORM `CostAttribution.source_id` index now matches SQL partial index semantics.

### File List

- `_bmad-output/stories/m2-3-cost-attribution.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `infra/local-init/10-cost-attribution.sql`
- `packages/shared-py/opticloud_shared/__init__.py`
- `packages/shared-py/opticloud_shared/cost_telemetry/__init__.py`
- `packages/shared-py/tests/test_cost_telemetry.py`
- `apps/solver-orchestrator/src/solver_orchestrator/geo_risk.py`
- `apps/solver-orchestrator/src/solver_orchestrator/models.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/test_cost_attribution.py`

### Change Log

- 2026-05-26 - Created story, completed three review rounds, and moved sprint status to in-progress.
- 2026-05-26 - Added M2 minimum cost telemetry schema, shared helper, solver hook, and tests.
- 2026-05-26 - Completed post-implementation code review; fixed ORM partial-index drift; all focused gates pass.

## Senior Developer Review (AI)

Outcome: Approved after patch

Review date: 2026-05-26

Review layers:

- Blind Hunter: checked diff-level correctness, imports, schema/model drift, and likely integration failures.
- Edge Case Hunter: checked idempotency replay, demo zero-write behavior, nested transaction safety, insert-failure behavior, and metadata leakage.
- Acceptance Auditor: checked implementation against AC1-AC12.

Findings:

- [x] [Review][Patch] ORM/source_id index drift - `CostAttribution` originally declared a full `idx_cost_attr_source_id`, while SQL created a partial index `WHERE source_id IS NOT NULL`. Fixed by adding `postgresql_where=text("source_id IS NOT NULL")` to the ORM index.

Residual risk:

- M3 red-line alerting remains intentionally downstream (`9-3-nfr-cost-alerts` / full G3); this story only ships the M2 attribution substrate and solver hook.
