# Story 6.B.2: Voucher unique ID (R2)

Status: done

## Story

As a user who submitted an authenticated reproducible optimization run,
I want the system to issue a permanent reproduction voucher ID,
so that the locked run context from Story 6.B.1 can be referenced, audited, and used by later rerun workflows.

## Acceptance Criteria

1. Successful authenticated reproducible runs issue exactly one permanent voucher.
   - `POST /v1/optimizations` mints a voucher only after a run with `options.reproducible: true` completes successfully.
   - The voucher is linked to the completed `Optimization.id`.
   - Non-reproducible runs do not create a voucher and do not add `reproducibility`.
   - Failed, infeasible, timeout, and not-implemented runs do not create a voucher.
   - `POST /v1/optimizations/demo` remains stateless: it may return the Story 6.B.1 handoff, but it must not insert a permanent voucher or return `voucher_id`.

2. Voucher IDs follow the required permanent format.
   - Format is exactly `repro-{YYYY}-{6 位 uppercase base32}`, for example `repro-2026-K7X9P2`.
   - `YYYY` is derived from the voucher creation timestamp in UTC.
   - The suffix uses the uppercase Crockford / ULID-style base32 alphabet `0123456789ABCDEFGHJKMNPQRSTVWXYZ`; this matches the PRD / architecture example containing digit `9`.
   - The suffix must not contain lowercase characters, padding, extra separators, or ambiguous letters `I`, `L`, `O`, `U`.
   - The implementation uses cryptographic randomness or an equivalent non-predictable source; do not use `random.random()` / timestamps as entropy.
   - Collisions are handled by retrying under a database uniqueness constraint, with a bounded max-attempt guard instead of an infinite loop.

3. Voucher metadata is persisted in `reproduction_vouchers`.
   - Add the raw SQL schema to `infra/local-init/02-solver-schema.sql` and an SQLAlchemy ORM mapping in solver-orchestrator.
   - Required columns: `id`, `voucher_id`, `optimization_id`, `user_id`, `api_key_id`, `request_fingerprint`, `locked_model_version`, `locked_solver`, `seed_locked`, `seed`, `status`, `created_at`.
   - `voucher_id` is unique; `optimization_id` is unique and references `optimizations(id)`.
   - Database constraints enforce the voucher ID shape and allowed `status` values.
   - `status` starts as `issued`.
   - Do not store the raw request body in this table.
   - Persist only the locked context already produced by Story 6.B.1 plus pointer IDs needed for audit and future rerun.
   - The optimization completion update, voucher insert, `_system.reproducibility.voucher_id` persistence, idempotency row, and optional outbox row are committed atomically in one database transaction.

4. Authenticated success responses expose the voucher without changing non-opt-in response shape.
   - `POST /v1/optimizations` success with `options.reproducible: true` returns `reproducibility.voucher_id`.
   - `GET /v1/optimizations/{optimization_id}` returns the same persisted `reproducibility.voucher_id` for the owner.
   - Idempotency replay of a completed reproducible optimization returns the same voucher ID and does not insert a second voucher row.
   - Do not add `voucher_id: null` to demo or non-voucher responses.
   - Existing success fields remain unchanged: `status`, `solution`, `objective`, `model_version`, `solve_seconds`, `citation`, and `ip_attribution`.
   - Existing non-opt-in responses still omit the `reproducibility` key entirely.

5. Voucher issuance emits only minimal audit/event metadata if an outbox row is added.
   - If implementation writes `outbox`, it must do so transactionally with the voucher insert.
   - Event type must be `repro.voucher.issued`, matching architecture P24.
   - Payload must contain pointer IDs and locked metadata references only; no raw optimization input and no user PII.
   - No consumer, notification, dashboard, or SLA job is required in this story.

6. Backend and type tests cover the voucher contract.
   - Unit tests cover voucher ID generation format and collision retry behavior.
   - Integration tests cover authenticated reproducible success insert + response.
   - Integration tests cover completed GET returns the same voucher ID.
   - Integration tests cover idempotency replay does not duplicate voucher rows.
   - Regression tests cover non-reproducible authenticated success and reproducible demo success remain voucher-free.
   - Type/API surface is updated where frontend TypeScript already models solver responses.
   - CI path filtering triggers solver-orchestrator tests when `infra/local-init/02-solver-schema.sql` changes.

7. Scope is limited to voucher issuance.
   - Do not add `GET /v1/reproduce/{voucher_id}`.
   - Do not add `POST /v1/repro/{voucher_id}/rerun`.
   - Do not implement 5-year image restore, cold archive lookup, or SLA tracking.
   - Do not implement anonymous/blind-review redaction.
   - Do not add UI voucher cards or public voucher detail pages.

8. Story tracking is updated with the implementation.
   - `_bmad-output/stories/sprint-status.yaml` moves `6-b-2-voucher-unique-id` through the workflow statuses only after the corresponding gates pass.
   - This story records all three story review rounds, implementation notes, file list, change log, and post-implementation code review.

## Tasks / Subtasks

- [x] Add voucher ID generation and persistence primitives. (AC: 2, 3)
  - [x] Add `reproduction_vouchers` schema and indexes to `infra/local-init/02-solver-schema.sql`.
  - [x] Add database `CHECK` constraints for voucher ID format and allowed `status` values.
  - [x] Update `.github/workflows/ci.yml` so solver-orchestrator tests run when `infra/local-init/02-solver-schema.sql` changes.
  - [x] Add SQLAlchemy models for `ReproductionVoucher` and, if used, solver-side `OutboxEvent`.
  - [x] Implement a small voucher ID generator that returns `repro-{UTC_YEAR}-{6 Crockford / ULID-style uppercase base32 chars}`.
  - [x] Implement collision-safe insert logic that retries under a unique database constraint.
- [x] Wire voucher issuance into the authenticated success path. (AC: 1, 3, 4, 5)
  - [x] Mint the voucher only after a reproducible LP solve reaches `completed`.
  - [x] Persist the voucher row with the Story 6.B.1 handoff fields.
  - [x] Reassign `Optimization.input_payload` so `_system.reproducibility.voucher_id` is persisted and visible through GET/idempotency replay.
  - [x] Keep optimization completion, voucher insert, input_payload voucher update, idempotency insert, and optional outbox insert inside one transaction.
  - [x] Preserve demo route stateless behavior and failure-path behavior.
  - [x] If adding outbox, insert `repro.voucher.issued` in the same DB transaction with no raw input payload.
- [x] Update response/API types. (AC: 4, 6)
  - [x] Ensure authenticated opt-in POST/GET responses include `reproducibility.voucher_id`.
  - [x] Ensure non-opt-in responses still omit `reproducibility`.
  - [x] Update `apps/web/src/lib/api.ts` response typing for the new optional voucher field.
- [x] Add regression tests. (AC: 1, 2, 3, 4, 5, 6, 7)
  - [x] Test voucher ID format, allowed alphabet, and year derivation.
  - [x] Test collision retry with deterministic test doubles or controlled DB pre-insert.
  - [x] Test authenticated reproducible success inserts exactly one voucher row.
  - [x] Test completed GET returns the same voucher ID.
  - [x] Test idempotency replay returns the same voucher and leaves one voucher row.
  - [x] Test non-reproducible success creates no voucher and omits `reproducibility`.
  - [x] Test reproducible demo success returns no `voucher_id` and inserts no voucher.
- [x] Update workflow records and validation evidence. (AC: 8)
  - [x] Move sprint status to `in-progress` during implementation, then `code-review`, then `done` after review passes.
  - [x] Update Dev Agent Record, File List, Change Log, and post-implementation review notes.
  - [x] Run solver tests, mypy, web typecheck, and `git diff --check`.

## Dev Notes

### Context

- Epic 6.B is the voucher / rerun / anonymous reproducibility chain.
- Story 6.B.1 already implemented the opt-in handoff in solver-orchestrator:
  - `options.reproducible=true`
  - locked `model_version`
  - locked solver
  - canonical SHA-256 request fingerprint
  - explicit seed lock (`seed: null` for deterministic LP)
  - persistence under `Optimization.input_payload._system.reproducibility`
  - opt-in-only `reproducibility` response on authenticated POST/GET and demo LP success.
- Story 6.B.2 turns that handoff into a permanent database-backed voucher ID for authenticated persisted optimizations only.

### What this story must do

- Extend `apps/solver-orchestrator/src/solver_orchestrator/routes.py` where the authenticated success response is already built.
- Use the existing `_system.reproducibility` handoff as the source of truth; do not recompute a different request fingerprint or model lock.
- Create `reproduction_vouchers` in the solver schema because the current deployed writable owner is solver-orchestrator; `apps/repro-service/` is still only `.gitkeep`.
- Keep the implementation small enough that a later real `repro-service` can move ownership without changing the voucher ID contract.
- Preserve response serialization discipline from Story 6.B.1: add voucher data only to opt-in authenticated success payloads; do not use a broad `exclude_none=True` dump that changes unrelated nullable fields.
- Avoid adding `voucher_id` as a default-null field to the shared handoff emitted by `_build_reproducibility_payload`; that helper is also used by `/v1/optimizations/demo`. Add `voucher_id` only after authenticated voucher persistence succeeds.

### What this story must not do

- No rerun endpoint.
- No public voucher lookup endpoint.
- No anonymous voucher mode.
- No image archive restore or 5-year SLA calculation.
- No UI component or dashboard.
- No raw request body in `reproduction_vouchers` or outbox payload.

### Relevant source anchors

- Epic 6.B sequence and R2 AC: `_bmad-output/planning/epics.md` section `Epic 6.B`
- PRD FR R2: `_bmad-output/planning/prd.md` section `Reproducibility & Academic Integrity`
- Architecture naming patterns P1/P6/P21/P23/P24: `_bmad-output/planning/architecture.md` sections `Naming Patterns` and `Communication Patterns`
- Repro layer architecture: `_bmad-output/planning/architecture.md` section `Repro 层（M5+）`
- Database topology mentions `reproduction_vouchers`: `_bmad-output/planning/architecture.md` section `Database Topology`
- Previous implementation: `_bmad-output/stories/6-b-1-mark-reproducible.md`
- Current solve path: `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- Current ORM models: `apps/solver-orchestrator/src/solver_orchestrator/models.py`
- Current solver schema SQL: `infra/local-init/02-solver-schema.sql`
- Existing authenticated DB test pattern: `apps/solver-orchestrator/tests/test_billing_integration.py`
- Existing demo route tests: `apps/solver-orchestrator/tests/test_demo_optimizations.py`
- Frontend API types: `apps/web/src/lib/api.ts`

### Project Structure Notes

- Do not scaffold a full `apps/repro-service` in this story. The architecture says repro-service owns voucher lifecycle long term, but there is no service package, DB dependency, CI job, or runtime wiring yet. Creating that service now would expand beyond the R2 ID + DB insert requirement.
- Keep reusable voucher helpers inside solver-orchestrator for now, preferably near route helpers or in a small module if the route file would become noisy.
- Database migrations in this repo are currently raw SQL under `infra/local-init/`; there is no active Alembic migration flow in service tests.
- CI currently applies `infra/local-init/02-solver-schema.sql` for solver tests, but the path filter does not yet include that SQL file under `solver_orchestrator`; update the filter in this story so schema-only solver changes do not skip CI.
- Outbox is already defined in `infra/local-init/01-schema.sql`; do not create a second outbox table.
- SQLAlchemy JSONB nested mutation is easy to lose. When adding `voucher_id` under `_system.reproducibility`, build a new dict and reassign `opt.input_payload = updated_payload`; do not rely on in-place nested mutation being detected.
- Prefer querying `reproduction_vouchers` by `optimization_id` when building authenticated completed responses if `_system.reproducibility.voucher_id` is missing on older rows; this keeps GET/idempotency response construction anchored to the durable table.

### Testing / Validation Notes

- Local Windows test command usually needs:
  - `$env:PYTHONPATH='D:\优化预测网站-6-b-2-voucher-unique-id\apps\solver-orchestrator\src;D:\优化预测网站-6-b-2-voucher-unique-id\packages\shared-py'`
  - `uv run pytest apps/solver-orchestrator/tests/ -q`
- Fresh worktrees may need `uv sync --all-packages --extra dev`.
- If local Postgres has an old schema, apply `infra/local-init/02-solver-schema.sql` before DB-backed tests or use the CI job as the authoritative schema application.
- Run `uv run mypy apps packages`.
- Run `pnpm --filter @opticloud/web typecheck` after installing Node dependencies if needed.
- Run `git diff --check`.

### Risks / Decisions

- Collision handling must be real, not only probabilistic; a database unique constraint is required.
- Demo cannot issue permanent vouchers because it has no authenticated user, API key, or persisted optimization.
- Persisting `voucher_id` only in the response is insufficient; completed GET and idempotency replay must read the persisted value.
- Adding a full repro-service now would create more infrastructure than the story needs and make the PR harder to review.

## Story Review Log

### Round 1: Requirements Completeness Review

Findings fixed:
- Reconciled the voucher suffix alphabet with PRD / architecture examples. The initial draft said RFC 4648 `A-Z2-7`, but the documented example `repro-2026-K7X9P2` contains digit `9`; the story now requires uppercase Crockford / ULID-style base32.
- Added an explicit bounded max-attempt guard for collision retry so implementation cannot accidentally loop forever if the generator or database is unhealthy.
- Tightened the test requirement to verify the allowed alphabet, not only the broad string shape.

Status: PASS after fixes.

### Round 2: Architecture / Testability Review

Findings fixed:
- Added a CI path-filter requirement because solver tests apply `infra/local-init/02-solver-schema.sql`, but the current filter only watches `apps/solver-orchestrator/**`. Without this, future schema-only solver changes could skip the solver CI job.
- Added an explicit SQLAlchemy JSONB persistence guard: update `_system.reproducibility.voucher_id` by assigning a fresh `opt.input_payload` dict, not by mutating a nested dict in place.
- Kept `repro-service` out of scope but documented why the solver schema is the current writable owner.

Status: PASS after fixes.

### Round 3: Acceptance / Scope Audit

Findings fixed:
- Added an explicit serialization guard: `voucher_id` must not appear as `null` on demo or other non-voucher responses. This prevents a naive shared-schema change from leaking a permanent-voucher field into the stateless demo route.
- Added transaction atomicity requirements for optimization completion, voucher insert, `_system.reproducibility.voucher_id`, idempotency, and optional outbox writes.
- Added database `CHECK` constraint requirements for voucher ID shape and allowed status values so the table itself enforces the R2 contract.

Status: PASS after fixes. Story is ready for implementation.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

1. Add failing tests for voucher ID format, collision retry, authenticated POST/GET persistence, idempotency replay, and demo non-issuance.
2. Add `reproduction_vouchers` raw SQL schema and SQLAlchemy model.
3. Add a small `solver_orchestrator.repro` helper module for ID generation, durable issuance, collision retry, and JSONB voucher attachment.
4. Wire authenticated successful reproducible LP runs to issue one voucher after completion and before idempotency persistence.
5. Update TypeScript API response typing and CI path filters, then run backend/type/static validations.

### Debug Log References

- 2026-05-21 — Fresh worktree `.venv` lacked OTEL dependencies; ran `uv sync --all-packages --extra dev`.
- 2026-05-21 — Local machine has no `psql`; applied updated `infra/local-init/02-solver-schema.sql` to the local test database using `asyncpg.execute()` for verification only.
- 2026-05-21 — Initial collision test reused a fixed voucher ID left by a previous local run; changed test data to generate unique valid IDs per run.

### Completion Notes List

- AC1 satisfied: authenticated `options.reproducible: true` completed LP runs issue exactly one durable voucher; non-reproducible, demo, and failure paths do not issue vouchers.
- AC2 satisfied: voucher IDs use `repro-{UTC_YEAR}-{6 Crockford base32 chars}` with cryptographic randomness and bounded collision retry under DB uniqueness.
- AC3 satisfied: `reproduction_vouchers` persists pointer IDs and locked Story 6.B.1 metadata; raw request bodies are not copied into the voucher table.
- AC4 satisfied: authenticated POST/GET/idempotency replay expose `reproducibility.voucher_id`; demo and non-opt-in responses do not emit `voucher_id: null`.
- AC5 satisfied by scope decision: no outbox row was added in this story, so no new event payload or consumer surface exists.
- AC6 satisfied: unit/integration/regression tests added; frontend API types updated; CI path filter now watches solver schema SQL.
- AC7 satisfied: no rerun endpoint, public voucher lookup, anonymous mode, image restore, SLA tracking, or UI component was added.
- ✅ Resolved review finding [Low]: Added direct regression coverage proving database `CHECK` constraints reject invalid voucher IDs and unsupported statuses.

Verification:
- `uv run pytest apps/solver-orchestrator/tests/ -q` with explicit local `PYTHONPATH` — 87 passed, 5 existing FastAPI deprecation warnings.
- `uv run mypy apps packages` — pass.
- `pnpm --filter @opticloud/web typecheck` — pass.
- `uv run ruff check ... --fix` and `uv run ruff format ...` applied; follow-up solver tests passed.
- `git diff --check` — pass.

### File List

Created:
- `_bmad-output/stories/6-b-2-voucher-unique-id.md`
- `apps/solver-orchestrator/src/solver_orchestrator/repro.py`
- `apps/solver-orchestrator/tests/test_reproduction_vouchers.py`

Modified:
- `.github/workflows/ci.yml`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/models.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/test_billing_integration.py`
- `apps/solver-orchestrator/tests/test_demo_optimizations.py`
- `apps/web/src/lib/api.ts`
- `infra/local-init/02-solver-schema.sql`

### Change Log

- 2026-05-21 — Created Story 6.B.2 context from Epic 6.B, PRD FR R2, architecture naming/repro-service guidance, and Story 6.B.1 implementation notes.
- 2026-05-21 — Completed three story review rounds and applied fixes before implementation.
- 2026-05-21 — Implemented durable reproduction voucher issuance for authenticated reproducible LP successes.
- 2026-05-21 — Added voucher ID generation/collision tests, authenticated POST/GET/idempotency integration tests, and demo non-issuance regression.
- 2026-05-21 — Updated web API types and CI path filters for solver schema changes.
- 2026-05-21 — Post-implementation review added DB constraint rejection tests for malformed voucher IDs and invalid statuses.

### Post-Implementation Code Review

Result: PASS after one low-risk test coverage patch.

Findings fixed:
- Low — AC3 required database constraints to enforce voucher ID shape and allowed status values, but the first implementation only tested the happy path through those constraints. Added direct DB regression coverage that rejects malformed voucher IDs and unsupported statuses.

Verification after review patch:
- `uv run pytest apps/solver-orchestrator/tests/ -q` with explicit local `PYTHONPATH` — 87 passed, 5 existing FastAPI deprecation warnings.
- `uv run mypy apps packages` — pass.
- `pnpm --filter @opticloud/web typecheck` — pass.
- `git diff --check` — pass.
