# Story 6.B.1: Mark `reproducible: true` (R1)

Status: done

## Story

As a user submitting an optimization task,
I want to mark the run as reproducible,
so that the system locks the exact execution context and prepares the reproducibility handoff needed for voucher issuance and later rerun workflows.

## Acceptance Criteria

1. `options.reproducible` is treated as an explicit opt-in on the optimization request path.
   - The field remains boolean and defaults to `false`.
   - `POST /v1/optimizations` and `POST /v1/optimizations/demo` preserve the flag in request handling instead of dropping it.
   - `false` keeps the current behavior unchanged.

2. When `options.reproducible: true`, the solve path locks the execution context before the solver result is finalized.
   - The exact catalog row selected for the task is pinned for the whole run.
   - The locked `model_version` and solver choice used for the run are recorded as reproducibility metadata.
   - The response / persisted payload cannot silently re-resolve to a different provider or version after execution starts.

3. When `options.reproducible: true`, the system produces a reproducibility handoff object for downstream voucher minting.
   - The handoff contains the locked version metadata, canonical request fingerprint, and an explicit seed-lock decision.
   - For current deterministic LP flows, the seed value may be `null`, but the lock decision must still be explicit.
   - The canonical request fingerprint is computed from the original request body before the handoff is attached; it must not include the handoff itself.
   - This story does not assign the permanent voucher ID, does not write the `reproduction_vouchers` table, and does not add rerun endpoints.

4. Successful responses keep existing fields intact and add reproducibility metadata only when requested.
   - `status`, `solution`, `objective`, `model_version`, `solve_seconds`, `citation`, and `ip_attribution` keep their current shape.
   - The opt-in path returns a nested `reproducibility` object in the success response.
   - The non-opt-in path omits the `reproducibility` key entirely; do not add `null` to existing responses.
   - Build the normal success payload first, then append `reproducibility` only for opt-in runs so existing nullable fields such as `citation` and `ip_attribution` keep their current serialization behavior.
   - The demo route mirrors the same reproducibility behavior for LP success responses.

5. Non-reproducible runs remain byte-for-byte consistent with the current workflow contract.
   - Existing citation, attribution, billing, and error behavior must not regress.
   - `options.reproducible: false` must not change solver selection or response semantics.

6. Backend tests cover the new reproducibility contract.
   - Tests assert the opt-in path records locked context metadata.
   - Tests assert the non-opt-in path stays unchanged.
   - Tests assert non-opt-in responses do not contain the `reproducibility` key.
   - Tests cover both the authenticated optimization route and the demo route.
   - Tests assert `GET /v1/optimizations/{optimization_id}` returns the persisted opt-in metadata for a completed reproducible run.

7. Sprint tracking and this story record are updated in the same PR.
   - `_bmad-output/stories/sprint-status.yaml` moves `6-b-1-mark-reproducible` through `ready-for-dev`, `in-progress`, `review`, and `done` only after the workflow gates pass.
   - This story file records the three story review rounds, implementation notes, file list, change log, and post-implementation code review.

## Tasks / Subtasks

- [x] Add reproducibility metadata plumbing to the solver orchestration path. (AC: 1, 2, 3, 4)
  - [x] Keep `options.reproducible` explicit in the request contract and preserve it through request handling.
  - [x] Capture a reproducibility handoff object that includes locked version metadata, canonical request fingerprint, and seed-lock decision.
  - [x] Persist the handoff under a namespaced system key in the existing optimization JSON payload so `GET /v1/optimizations/{optimization_id}` can return the same opt-in metadata without a migration.
  - [x] Mirror the same behavior in `/v1/optimizations/demo` for the LP success path.
  - [x] Do not add voucher ID formatting, voucher persistence, or rerun routing in this story.
- [x] Extend backend tests for reproducibility behavior. (AC: 1, 2, 3, 4, 5, 6)
  - [x] Add coverage for `options.reproducible: true`.
  - [x] Add coverage for `options.reproducible: false`.
  - [x] Add coverage for both authenticated solve and demo solve happy paths.
  - [x] Add coverage for completed `GET /v1/optimizations/{optimization_id}` on a reproducible authenticated run.
  - [x] Assert that existing response fields keep their current shape.
- [x] Update story tracking and Dev Agent Record after implementation. (AC: 7)
  - [x] Move sprint status through the lifecycle.
  - [x] Append completion notes, file list, change log, and post-implementation review result.

## Dev Notes

### Context

- Epic 6.B is the first live reproducibility slice in the voucher / rerun / anonymous chain.
- PRD and architecture both treat `repro-service` as the long-term owner of voucher lifecycle, but this story stays focused on the opt-in reproducibility trigger and the handoff metadata needed by later stories.
- `apps/repro-service/` currently exists only as a placeholder. Do not build the full voucher service, ID format, or rerun API here.

### What this story must do

- Respect the existing `OptimizationOptions.reproducible` field already present in `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`.
- Lock the exact algorithm / model version selected for the run before execution result finalization.
- Record a reproducibility envelope that later stories can turn into a permanent voucher record.
- Include that envelope in opt-in success responses as `reproducibility`, while omitting the key for non-opt-in responses.
- Keep the current non-reproducible solve path unchanged.

### What this story must not do

- Do not implement the permanent voucher ID format `repro-{YYYY}-{6 位 base32}`.
- Do not insert into `reproduction_vouchers`.
- Do not add any `reproduce`, `repro`, or `reproduction_vouchers` HTTP route.
- Do not add anonymous redaction logic.
- Do not add UI surfaces or docs for the voucher lifecycle yet.

### Relevant source anchors

- Epic 6.B sequence and story split: `_bmad-output/planning/epics.md` around the `Epic 6.B` section
- Epic goal and R1 AC: `_bmad-output/planning/epics.md` at `Story 6.B.1`
- Reproibility contract and voucher format: `_bmad-output/planning/prd.md` section `5.2 学术 / 复现`
- Repro service architecture: `_bmad-output/planning/architecture.md` sections `Repro 层（M5+）`, `Database Topology`, and `Service Map`
- Existing request contract: `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`
- Current solve path: `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- LP solver wrapper: `apps/solver-orchestrator/src/solver_orchestrator/solvers.py`
- Existing backend test patterns: `apps/solver-orchestrator/tests/test_citation.py` and `apps/solver-orchestrator/tests/test_algorithm_details.py`

### Project Structure Notes

- Keep the implementation inside `apps/solver-orchestrator/` for this story unless a small shared reproducibility helper becomes necessary.
- Reuse the existing API schema / response pattern instead of inventing a second parallel contract.
- Keep the canonical request fingerprint logic local and deterministic; do not add a new dependency for it.
- Reuse the existing `_hash_body` canonical JSON helper if possible. If it needs to be generalized, keep the behavior stable: `json.dumps(..., sort_keys=True, separators=(",", ":"))` followed by SHA-256.
- Add a small nested reproducibility schema instead of scattered ad hoc keys.
- Avoid using a global `exclude_none=True` dump to hide `reproducibility`; that would also alter existing nullable fields. Append the new key conditionally after the existing success payload is built.
- Because there is no `reproduction_vouchers` table implementation in this story, persist the handoff in the existing `Optimization.input_payload` JSONB under `"_system.reproducibility"` or another clearly namespaced system key. Do not add a migration.
- Keep the user's original request fields intact. The fingerprint must be based on the original request payload, not on a mutated payload that already contains `_system`.

### Testing / Validation Notes

- Run the targeted solver-orchestrator tests that cover the changed solve path.
- Add a reproducibility-specific regression test file only if the existing citation / algorithm detail tests become too crowded.
- Validate that the demo route mirrors the authenticated route for reproducible LP success responses.
- Run `git diff --check` before marking the story complete.

### Risks / Decisions

- The seed lock is a contract decision, not a claim that the current LP solver is stochastic.
- This story should expose the reproducibility envelope needed by 6.B.2, but it should not claim the permanent voucher lifecycle is already shipped.
- The most likely failure mode is over-scoping into 6.B.2; keep the permanent voucher ID and DB write out of this story.

## Story Review Log

### Round 1: Requirements Completeness Review

Findings fixed:
- Made the response contract testable: opt-in success responses must include `reproducibility`; non-opt-in responses must omit the key, not emit `null`.
- Added explicit persistence guidance using the existing `Optimization.input_payload` JSONB so completed `GET /v1/optimizations/{id}` can return the same handoff without a schema migration.
- Kept 6.B.2 ownership intact by continuing to exclude permanent voucher IDs and `reproduction_vouchers` writes.

Status: PASS after fixes.

### Round 2: Architecture / Testability Review

Findings fixed:
- Namespaced the persisted handoff under an internal system key so derived reproducibility metadata does not masquerade as user input.
- Required the canonical fingerprint to be computed from the original request before system metadata is attached, preventing recursive fingerprint drift.
- Tightened route scope: no `reproduce`, `repro`, or `reproduction_vouchers` HTTP endpoints are allowed in 6.B.1.

Status: PASS after fixes.

### Round 3: Acceptance / Scope Audit

Findings fixed:
- Added a serialization guard so implementation cannot satisfy the opt-in response by adding `reproducibility: null` to every success response.
- Required a completed `GET /v1/optimizations/{optimization_id}` regression test so persisted handoff metadata is proven, not only the initial POST response.
- Explicitly warned against global `exclude_none=True` because it would alter existing nullable response fields.

Status: PASS after fixes. Story is ready for implementation.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

1. Add RED tests for demo and authenticated reproducible LP responses.
2. Add a small reproducibility envelope schema and helper functions in solver-orchestrator.
3. Persist opt-in handoff metadata under `_system.reproducibility` in `Optimization.input_payload`.
4. Append `reproducibility` only for opt-in success responses, preserving non-opt-in payload shape.
5. Run targeted solver tests, update story checkboxes, then move to code review.

### Debug Log References

- 2026-05-21 — Initial RED test run failed during collection because the fresh worktree `.venv` lacked `opentelemetry`; ran `uv sync --all-packages --extra dev`.
- 2026-05-21 — Windows local test command needs `PYTHONPATH` to include `apps/solver-orchestrator/src` and flat-layout `packages/shared-py`, not `packages/shared-py/src`.

### Completion Notes List

- AC1 / AC5 satisfied: `options.reproducible` remains boolean/default false; non-opt-in success responses omit `reproducibility`.
- AC2 / AC3 satisfied: opt-in runs build a handoff with locked `model_version`, locked solver, SHA-256 canonical request fingerprint, and explicit seed lock (`seed: null` for deterministic LP).
- AC4 satisfied: POST and completed GET authenticated success responses append `reproducibility` only when requested; demo LP success mirrors the same behavior.
- AC6 satisfied: demo and authenticated tests cover opt-in, non-opt-in, completed GET persistence, and existing response-shape regression.
- AC7 satisfied: sprint status moved to `done` after post-implementation review patch and verification.

Verification:
- `uv run pytest apps/solver-orchestrator/tests/test_demo_optimizations.py apps/solver-orchestrator/tests/test_citation.py -q` with explicit local `PYTHONPATH` — 18 passed, 2 existing FastAPI deprecation warnings.
- `uv run pytest apps/solver-orchestrator/tests/test_billing_integration.py -q` with explicit local `PYTHONPATH` — 7 passed, 2 existing FastAPI deprecation warnings.
- `uv run pytest apps/solver-orchestrator/tests/ -q` with explicit local `PYTHONPATH` — 82 passed, 5 existing FastAPI deprecation warnings.
- `uv run mypy apps packages` — pass after CI follow-up type narrowing patch.
- `pnpm --filter @opticloud/web typecheck` — pass after installing Node workspace dependencies with `pnpm install --frozen-lockfile`.
- `git diff --check` — pass.

### File List

Created:
- `_bmad-output/stories/6-b-1-mark-reproducible.md`

Modified:
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`
- `apps/solver-orchestrator/tests/test_billing_integration.py`
- `apps/solver-orchestrator/tests/test_demo_optimizations.py`
- `apps/web/src/lib/api.ts`

### Change Log

- 2026-05-21 — Created Story 6.B.1 context and completed 3 story-review rounds before implementation.
- 2026-05-21 — Implemented opt-in reproducibility handoff metadata for authenticated and demo LP success paths.
- 2026-05-21 — Added regression coverage for opt-in response, non-opt-in omission, and completed GET persistence.
- 2026-05-21 — Post-implementation review patched web API response types for the new optional `reproducibility` field.
- 2026-05-21 — CI follow-up narrowed helper return types and applied ruff formatting for `routes.py`.

### Post-Implementation Code Review

Result: PASS after one API type-sync patch.

Findings fixed:
- P2 — `apps/web/src/lib/api.ts` exposed `OptimizationResponse` and `DemoOptimizationResponse` but did not include the new optional `reproducibility` field, so frontend consumers would not see the 6.B.1 response contract in TypeScript. Added a shared `Reproducibility` interface and optional response fields.

Verification:
- `uv run pytest apps/solver-orchestrator/tests/ -q` with explicit local `PYTHONPATH` — 82 passed, 5 existing FastAPI deprecation warnings.
- `uv run mypy apps packages` — pass.
- `pnpm --filter @opticloud/web typecheck` — pass.
- `git diff --check` — pass.
