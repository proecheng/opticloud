# Story 6.B.3: Rerun within 5y (R3)

Status: done

## Story

As an authenticated user who owns a durable reproduction voucher,
I want to rerun the original locked optimization context within the 5-year reproducibility window,
so that a later paper, audit, or customer verification can produce a new run and voucher linked back to the original evidence chain.

## Acceptance Criteria

1. Authenticated owners can rerun a valid issued voucher.
   - Add `POST /v1/reproduce/{voucher_id}/rerun` under the solver-orchestrator FastAPI `/v1` router.
   - The endpoint requires API-key authentication and `optimize:write` scope for this v1 implementation because it creates a new optimization run.
   - The endpoint accepts a valid Story 6.B.2 voucher ID format only.
   - The caller must own the voucher (`reproduction_vouchers.user_id` matches the authenticated user).
   - Unknown voucher IDs return 404 RFC 7807.
   - Vouchers owned by another user return 404 RFC 7807, not 403, to avoid disclosing voucher existence.
   - Non-`issued` voucher statuses are not rerunnable and return 409 RFC 7807.
   - For this story, the allowed durable statuses are `issued` and `revoked`; expiration is still computed from `created_at`, not stored by flipping status to `expired`.

2. Rerun is constrained to the 5-year reproducibility window.
   - The 5-year window is calculated from the original voucher `created_at` timestamp in UTC.
   - Calculate expiry by adding 5 calendar years to the UTC voucher timestamp, not by adding a fixed number of days.
   - A voucher created at `2026-05-21T00:00:00Z` remains eligible through `2031-05-21T00:00:00Z` exclusive.
   - Leap-day vouchers use the same calendar-year helper; a voucher created at `2024-02-29T12:00:00Z` expires at `2029-02-28T12:00:00Z`.
   - Expired vouchers return 410 RFC 7807 with a clear `next_action_url` or remediation hint.
   - Boundary tests cover just-before-expiry, at-expiry, and leap-day behavior.
   - Do not implement Story 6.B.6 SLA tracking jobs in this story.

3. Rerun uses the original locked run context, not caller-supplied model choices.
   - The rerun endpoint accepts no request body. An empty JSON object may be tolerated as equivalent to no body, but any non-empty JSON body must return 422 RFC 7807.
   - The original `Optimization.input_payload` is the source of truth for the rerun payload.
   - The source optimization must still exist, belong to the same user as the voucher, and have `status='completed'`; otherwise return a deterministic 409 RFC 7807 before creating new records.
   - Strip all `_system` metadata from the user payload before recomputing the Story 6.B.1 reproducibility handoff for the rerun.
   - Reuse the original locked solver from `reproduction_vouchers.locked_solver`.
   - Reuse the original locked model version from `reproduction_vouchers.locked_model_version` in the new optimization response.
   - Do not let the caller override `task_type`, solver, fallback chain, objective, constraints, seed, or model version in this story.
   - The v1 rerun implementation supports completed LP vouchers only; unsupported task types return 501/422 RFC 7807 without creating a new voucher.

4. Successful rerun creates a new optimization and a new voucher linked to the source voucher.
   - A successful rerun inserts a new `optimizations` row with `status='completed'`, copied original payload, fresh `_system.reproducibility`, and current run timestamps.
   - A successful rerun issues exactly one new Story 6.B.2-format voucher for the rerun optimization.
   - The new voucher links back to the original voucher in durable storage.
   - Add nullable linkage columns to `reproduction_vouchers` rather than creating a separate service/table:
     - `parent_voucher_id UUID NULL REFERENCES reproduction_vouchers(id)`
     - `rerun_depth INTEGER NOT NULL DEFAULT 0`
   - Original vouchers have `parent_voucher_id IS NULL` and `rerun_depth = 0`.
   - A rerun voucher has `parent_voucher_id` set to the source voucher row ID and `rerun_depth = source.rerun_depth + 1`.
   - Update the existing status `CHECK` constraint to allow `issued` and `revoked`.
   - Add a `CHECK (rerun_depth >= 0)` database constraint.
   - Add an index on `parent_voucher_id` for lineage traversal.
   - The rerun optimization insert, new voucher insert, voucher linkage, and optional idempotency row commit atomically in one transaction.
   - Preflight failures and unsupported task types must not create new `optimizations`, `reproduction_vouchers`, or `idempotency_keys` rows.
   - If the LP rerun solver returns non-success unexpectedly, return an RFC 7807 error without issuing a voucher or idempotency mapping.

5. Rerun responses expose lineage without changing existing optimization response shape.
   - The success response uses the existing `OptimizationResponse` payload plus `reproducibility.voucher_id`.
   - Add a top-level `rerun_of_voucher_id` field only on rerun responses.
   - Add a top-level `source_optimization_id` field only on rerun responses.
   - If included, `archive_restore` is also rerun-only and must not appear on standard optimization/demo responses.
   - Existing `POST /v1/optimizations`, `GET /v1/optimizations/{id}`, and `/demo` responses must not gain `rerun_of_voucher_id` or `source_optimization_id`.
   - Existing non-opt-in response shapes remain unchanged.

6. Idempotency works for rerun requests.
   - If `Idempotency-Key` is present, the endpoint deduplicates by `(user_id, key, request_body_hash)` using the existing `idempotency_keys` table.
   - Because the rerun request body is empty or minimal, the request hash must include the target `voucher_id` so the same key cannot be reused for a different voucher.
   - Persist idempotency through the existing `idempotency_keys.optimization_id` replay flow, where the stored optimization is the newly created rerun optimization.
   - Same key + same voucher returns the original rerun optimization response and voucher.
   - Same key + different voucher returns 409 RFC 7807.
   - Idempotency replay must not create a second optimization or second voucher.

7. Cold archive / provider migration dependencies are represented but not over-implemented.
   - Do not implement S3/Glacier restore, image archival, KMS restore, provider auto-migration, capability matching, or a real `repro-service`.
   - The endpoint may return a deterministic `archive_restore` metadata object in the rerun response, but it must state that live solver image reuse was used for current LP support.
   - `archive_restore`, if present, is top-level rerun response metadata only; do not persist it into standard optimization payloads or expose it via `GET /v1/optimizations/{id}`.
   - If archive restore is represented in code, it must be a pure in-process status object, not a network call or background job.
   - No `GET /v1/reproduce/{voucher_id}` voucher lookup endpoint is required in this story.
   - No anonymous/blind-review redaction is required in this story.

8. Billing and credits are not changed by this story.
   - The rerun endpoint must not accept or process `X-Billing-Charge-Id`.
   - The rerun endpoint must not call billing reserve/finalize helpers in this story.
   - No credit reservation, refund, or balance mutation is added for reruns in Story 6.B.3.

9. Backend and frontend API contracts are updated.
   - Add backend tests for successful owner rerun, lineage persistence, and new voucher issuance.
   - Add backend tests for unknown voucher, cross-user voucher, expired voucher, non-issued voucher, unsupported task type, and idempotency replay.
   - Add backend tests for same `Idempotency-Key` + different voucher returning 409.
   - Add backend tests that rerun does not call billing reserve/finalize even when billing helpers are monkeypatched to fail on use.
   - Add raw SQL schema updates to `infra/local-init/02-solver-schema.sql` and ORM updates in `models.py`.
   - Update `apps/web/src/lib/api.ts` with a rerun response type and helper only if the frontend API client already models solver calls.
   - Keep solver CI path filtering from Story 6.B.2 intact.

10. Story workflow tracking is updated.
   - This story records all three story review rounds and the modifications made after each round.
   - `_bmad-output/stories/sprint-status.yaml` moves `6-b-3-rerun-within-5y` to `ready-for-dev` only after the three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.

## Tasks / Subtasks

- [x] Add rerun lineage persistence primitives. (AC: 4)
  - [x] Update `infra/local-init/02-solver-schema.sql` with `parent_voucher_id`, `rerun_depth`, an index on `parent_voucher_id`, `rerun_depth >= 0`, and `status IN ('issued', 'revoked')` constraints.
  - [x] Update `ReproductionVoucher` ORM mapping with the same nullable lineage fields.
  - [x] Extend voucher issuance helper to accept optional parent voucher metadata without changing Story 6.B.2 issuance behavior.
- [x] Add rerun request helpers. (AC: 1, 2, 3, 6, 7)
  - [x] Add helper to load an owner-visible voucher by `voucher_id`.
  - [x] Add helper to validate the 5-year UTC calendar-year window, including leap-day behavior.
  - [x] Add helper to validate the source optimization exists, is owned by the caller, and is completed.
  - [x] Add helper to rebuild a clean `OptimizationRequest` from the original optimization payload after stripping `_system`.
  - [x] Add helper to reject non-empty rerun request bodies.
  - [x] Add helper to compute rerun idempotency hash that includes `voucher_id`.
  - [x] Add pure metadata object for current live-image rerun behavior, if response metadata is included.
- [x] Implement `POST /v1/reproduce/{voucher_id}/rerun`. (AC: 1, 2, 3, 4, 5, 6, 7)
  - [x] Require API key auth and `optimize:write`.
  - [x] Validate voucher format, ownership, status, and expiry.
  - [x] Validate source optimization ownership and completed status before creating any rerun rows.
  - [x] Support completed LP vouchers by rerunning the locked payload through the existing LP solver path.
  - [x] Persist a new completed optimization.
  - [x] Issue a new voucher linked to the source voucher.
  - [x] Return existing optimization success payload plus rerun-only lineage fields via a JSON-safe helper.
  - [x] Avoid billing reserve/finalize and credit mutations.
  - [x] Keep unsupported task types/failure paths from creating new vouchers.
- [x] Update API typing. (AC: 5, 8)
  - [x] Add TypeScript rerun response type and `rerunReproductionVoucher` API helper if useful to the existing web client.
  - [x] Do not add rerun lineage fields to standard optimization/demo response types.
- [x] Add regression tests. (AC: 1, 2, 3, 4, 5, 6, 7, 8)
  - [x] Test successful owner rerun creates a new optimization and linked voucher.
  - [x] Test rerun response includes new `voucher_id`, `rerun_of_voucher_id`, and `source_optimization_id`.
  - [x] Test original voucher and original optimization remain unchanged.
  - [x] Test unknown and cross-user vouchers return 404.
  - [x] Test expired vouchers return 410.
  - [x] Test leap-day 5-year expiry behavior.
  - [x] Test a seeded `revoked` voucher returns 409.
  - [x] Test unsupported task type returns error without new optimization, voucher, or idempotency row.
  - [x] Test non-completed source optimization returns 409 without new rows.
  - [x] Test idempotency replay returns the same rerun voucher and does not duplicate rows.
  - [x] Test same `Idempotency-Key` with a different voucher returns 409.
  - [x] Test non-empty rerun JSON body returns 422.
  - [x] Test rerun does not call billing helpers.
- [x] Update workflow records and validation evidence. (AC: 9)
  - [x] Complete three story review rounds before implementation.
  - [x] Update Dev Agent Record, File List, Change Log, and post-implementation review notes.
  - [x] Run solver tests, mypy, web typecheck, and `git diff --check`.

### Review Findings

- [x] [Review][Patch] Story workflow record still says implementation is pending — updated tasks, completion notes, file list, change log, and review notes in this story file.
- [x] [Review][Patch] Rerun idempotency is keyed globally, not by `(user_id, key, request_body_hash)` — changed solver idempotency lookup and schema primary key to `(user_id, key)`; added cross-user same-key rerun regression.
- [x] [Review][Patch] Locked solver is not enforced during rerun execution — added preflight rejection for LP vouchers whose locked solver is not the current executable `highs` solver; added no-row-write regression.

## Dev Notes

### Context

- Story 6.B.1 added opt-in reproducibility handoff under `Optimization.input_payload._system.reproducibility`.
- Story 6.B.2 added durable `reproduction_vouchers` and voucher ID issuance for authenticated successful reproducible LP runs.
- Story 6.B.3 is the first rerun surface. It should create a new run and new voucher linked to the original voucher.
- Full cold image restore is not available because Story M3.9 is still backlog. This story must not pretend S3/Glacier restore exists.

### Scope Decision

- Implement the PRD endpoint spelling: `POST /v1/reproduce/{voucher_id}/rerun`.
- Do not also add `/v1/repro/{voucher_id}/rerun` unless a later review explicitly finds compatibility risk high enough to justify an alias.
- Keep implementation in solver-orchestrator for now; `apps/repro-service/` is still not scaffolded and would exceed this story.
- Require `optimize:write`, not `reproduce:read`, because this endpoint creates a new optimization. PRD lists `reproduce:read`, but the current auth-service and tests already use `optimize:write` for solve creation.
- Use an empty-body POST contract. Do not model a rerun request schema until a future story introduces user-supplied restore/provider options.

### Relevant Source Anchors

- Previous voucher implementation: `_bmad-output/stories/6-b-2-voucher-unique-id.md`
- Current voucher helpers: `apps/solver-orchestrator/src/solver_orchestrator/repro.py`
- Current authenticated solve route and response builder: `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- Current ORM: `apps/solver-orchestrator/src/solver_orchestrator/models.py`
- Current schema SQL: `infra/local-init/02-solver-schema.sql`
- Current backend tests: `apps/solver-orchestrator/tests/test_reproduction_vouchers.py`, `apps/solver-orchestrator/tests/test_billing_integration.py`
- Frontend API types: `apps/web/src/lib/api.ts`
- Epic story source: `_bmad-output/planning/epics.md` lines around Epic 6.B / Story 6.B.3
- PRD R3 source: `_bmad-output/planning/prd.md` Reproducibility & Academic Integrity table
- Architecture patterns: `_bmad-output/planning/architecture.md` P1/P6/P20/P23/P24 and Repro service notes

### Architecture / Data Notes

- `reproduction_vouchers.optimization_id` is unique and points to the optimization that produced that voucher.
- For lineage, use `parent_voucher_id` referencing the source voucher row. This is more stable than storing only the source voucher string and keeps joins local to the table.
- Do not mutate nested JSONB in place. Follow Story 6.B.2 pattern: assign a fresh `Optimization.input_payload` dict.
- `issue_reproduction_voucher` should remain backward compatible for normal optimization issuance. Parent linkage should be optional.
- Standard optimization responses should remain unchanged. Add rerun lineage fields only in the rerun endpoint response content after `_build_success_response` is created or through a dedicated helper.
- Do not add a revoke endpoint in this story. `revoked` exists so the rerun endpoint and durable constraint can represent a non-rerunnable voucher state and be tested.
- Use a small calendar-year helper for 5-year expiry. Do not approximate 5 years as 1,825 days because leap years would reject valid vouchers early or late.
- Strip the old `_system` object before creating the rerun optimization so the new run gets a fresh reproducibility handoff and fresh voucher ID.
- Reuse the existing `idempotency_keys.optimization_id` replay design; the rerun-specific request hash differentiates voucher targets while the stored optimization ID points to the rerun result.
- Keep billing out of this endpoint for Story 6.B.3. The route should not accept `X-Billing-Charge-Id` and should not reuse `post_optimization` wholesale if that would trigger billing side effects.
- Perform all validation before adding rerun rows. The only rows created in this story should correspond to a successful rerun.

### Testing / Validation Notes

- Local Windows test command usually needs:
  - `$env:PYTHONPATH='D:\优化预测网站-6-b-3-reproduction-rerun\apps\solver-orchestrator\src;D:\优化预测网站-6-b-3-reproduction-rerun\packages\shared-py'`
  - `uv run pytest apps/solver-orchestrator/tests/ -q`
- Fresh local DBs may need `infra/local-init/02-solver-schema.sql` applied before DB-backed tests.
- Run `uv run mypy apps packages`.
- Run `pnpm --filter @opticloud/web typecheck`.
- Run `git diff --check`.
- Use `git -c core.autocrlf=false ...` in this Windows worktree to avoid global CRLF noise.
- Add a same-key/different-voucher idempotency regression because the existing idempotency key is globally unique and the rerun body is intentionally empty.
- Add a no-billing regression by monkeypatching `billing_client.reserve` and `billing_client.finalize` to raise if called.
- Add row-count assertions around preflight failures and unsupported task types so the route cannot silently persist partial rerun state.

### Risks / Decisions

- If the original voucher was created for a non-LP task after future stories, this story must not create partial/invalid reruns. Return a deterministic error.
- Rerun idempotency must include `voucher_id`; otherwise the same key could replay the wrong voucher.
- Rerun must not copy old `_system.reproducibility.voucher_id` into the new optimization payload.
- Creating a full repro-service now would hide important transaction behavior behind unbuilt infrastructure and make tests brittle.

## Story Review Log

### Round 1: Requirements Completeness Review

Findings fixed:
- Clarified the durable voucher status model. The initial draft required a non-`issued` 409 path, but Story 6.B.2's table only allowed `issued`. The story now requires the status constraint to allow `issued` and `revoked`, with expiration still computed from `created_at`.
- Added an explicit lineage index on `parent_voucher_id` so the parent-child voucher link is not only structurally correct but queryable.
- Tightened the non-issued test requirement to seed a `revoked` voucher and assert 409.

Status: PASS after fixes.

### Round 2: API Contract and Side-Effect Review

Findings fixed:
- Clarified the empty-body rerun contract. The initial draft blocked caller overrides but did not explicitly say how request bodies are handled, so it now requires no body or an empty object only.
- Tightened rerun-only response metadata. `archive_restore`, `rerun_of_voucher_id`, and `source_optimization_id` must not leak into standard optimization, GET, or demo responses.
- Added a no-billing constraint. Rerun creates an optimization but Story 6.B.3 does not define billing, so the route must not accept `X-Billing-Charge-Id` or call billing reserve/finalize.
- Clarified idempotency persistence through the existing `idempotency_keys.optimization_id` flow and added same-key/different-voucher regression coverage.
- Added implementation guidance to strip old `_system` metadata before creating the rerun optimization and to use a JSON-safe helper for augmenting rerun responses.

Status: PASS after fixes.

### Round 3: Acceptance Boundary and Atomicity Review

Findings fixed:
- Made the 5-year window precise as a UTC calendar-year calculation, including explicit leap-day behavior and tests.
- Added source optimization validity requirements: the optimization behind the voucher must still exist, belong to the same user, and be completed.
- Tightened failure-path atomicity. Preflight failures, unsupported task types, and unexpected solver failures must not create rerun optimizations, vouchers, or idempotency rows.
- Added row-count regression requirements so implementation cannot pass by returning the right error while leaving partial durable state.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

1. Add voucher lineage columns/constraints to SQL and ORM, keeping normal voucher issuance backward compatible.
2. Add rerun helper functions for voucher lookup, UTC calendar expiry, clean payload rebuild, idempotency hashing, and rerun response shaping.
3. Implement `POST /v1/reproduce/{voucher_id}/rerun` with preflight validation before any inserts, then atomic optimization/voucher/idempotency persistence on success.
4. Add backend regression coverage for success, lineage, 5-year boundaries, ownership/status failures, idempotency, body rejection, unsupported task types, and no-billing side effects.
5. Add the frontend API rerun response/helper without changing standard optimization response types.

### Debug Log References

- 2026-05-21 — Created new worktree `D:\优化预测网站-6-b-3-reproduction-rerun` from `origin/main` after PR #37 merge.
- 2026-05-21 — Initial Windows checkout showed CRLF status noise due global `core.autocrlf=true`; refreshed with `git -c core.autocrlf=false update-index --refresh` and will use that config for Git commands.

### Completion Notes List

- Implemented `POST /v1/reproduce/{voucher_id}/rerun` with API-key auth, `optimize:write` scope, owner-visible 404 behavior, issued-status enforcement, UTC 5-calendar-year expiry, empty-body enforcement, and billing-header rejection.
- Added rerun lineage persistence via `reproduction_vouchers.parent_voucher_id` and `rerun_depth`, including raw SQL migration, ORM mapping, constraints, parent index, and backward-compatible voucher issuance helper parameters.
- Rebuilt rerun payloads from the source optimization after stripping `_system`, generated fresh reproducibility handoff/voucher metadata, and kept rerun-only fields out of standard optimization/demo/GET response shapes.
- Implemented rerun idempotency with voucher-aware request hashing and user-scoped `(user_id, key)` storage, including same-key/same-voucher replay, same-user/different-voucher conflict, and cross-user same-key independence.
- Completed code review follow-ups for workflow records, user-scoped idempotency, and locked-solver preflight enforcement.
- Validation completed on 2026-05-21: target rerun/voucher tests `13 passed`; solver suite `97 passed`; mypy `Success: no issues found in 65 source files`; web typecheck passed; `git diff --check` passed.

### File List

Created:
- `_bmad-output/stories/6-b-3-rerun-within-5y.md`
- `apps/solver-orchestrator/tests/test_reproduction_rerun.py`

Modified:
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/models.py`
- `apps/solver-orchestrator/src/solver_orchestrator/repro.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/test_reproduction_vouchers.py`
- `apps/web/src/lib/api.ts`
- `infra/local-init/02-solver-schema.sql`

### Change Log

- 2026-05-21 — Created initial Story 6.B.3 draft from Epic 6.B, PRD R3, architecture Repro notes, and Story 6.B.2 implementation.
- 2026-05-21 — Story review round 1 clarified voucher status lifecycle and lineage indexing before implementation.
- 2026-05-21 — Story review round 2 tightened rerun API/body/idempotency contracts and explicitly excluded billing side effects.
- 2026-05-21 — Story review round 3 clarified 5-year calendar expiry, source optimization preconditions, and no-partial-row failure behavior.
- 2026-05-21 — Implemented Story 6.B.3 rerun endpoint, lineage schema, API client helper, and backend regression tests.
- 2026-05-21 — Code review findings resolved: story workflow record updated, rerun idempotency scoped by `(user_id, key)`, and locked-solver preflight enforcement added.
