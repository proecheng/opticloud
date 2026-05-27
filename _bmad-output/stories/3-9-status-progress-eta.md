# Story 3.9: Status / progress / eta / model_version

Status: done

## Story

As an authenticated async optimization API user,
I want `GET /v1/optimizations/{optimization_id}` to return a stable status, progress, ETA, and model version contract,
so that SDKs and Console polling can track long-running optimization work without guessing from private persistence details.

## Acceptance Criteria

1. `GET /v1/optimizations/{optimization_id}` keeps the current API-key authentication path and owner isolation: caller-owned rows return `200 OK`; missing or cross-tenant rows return Story 3.7 Problem Details `404 Not Found` without revealing status, progress, billing metadata, idempotency keys, or ownership.
2. Every successful owner-visible `GET` response includes `optimization_id`, `status`, `model_version`, `created_at`, `completed_at`, `progress_pct`, and `eta_seconds`.
3. Public `model_version` always uses the Story 3.1 / A-S1 shape. Within `model_version`, expose the provider transparency fields `provider_id`, `kind`, `version`, and `provider_url`; do not serialize the internal `provider_kind` alias or provider-route metadata inside public `model_version`.
4. For `queued` optimizations, the endpoint returns the compact async status shape with `mode="async"`, `progress_pct=0` by default, `eta_seconds=null` when no ETA is known, and the existing async queue message.
5. For `in_progress` optimizations, the endpoint reads progress metadata from `input_payload._system.progress` when present and returns normalized `progress_pct` and `eta_seconds`; if metadata is absent, it returns `progress_pct=0` and `eta_seconds=null` rather than fabricating progress. `in_progress` must not report public completion, so metadata values at or above 100 are clamped to `99`.
6. For terminal statuses, the endpoint remains compatible with existing response semantics: completed rows still include solution/objective/citation/IP/reproducibility/top-k metadata, while failed/timeout/cancelled rows keep their compact status/error shape. Terminal rows must still include `progress_pct` and `eta_seconds`; completed rows return `100/0`, and non-completed terminal rows return `eta_seconds=null`.
7. `progress_pct` is a public integer percentage in the inclusive range `0..100`; finite numeric persisted values are converted with `int(value)` then clamped. `eta_seconds` is either a non-negative integer number of seconds or `null`. Invalid or out-of-range persisted progress metadata must not cause a 500 response or leak `_system`.
   If a historical row has missing or malformed `model_version`, GET must not raise a 500 merely because progress fields were added. Return the persisted value only when it is a dict with the required public fields; otherwise return `null` or the existing safe compact behavior already used by that status path.
8. `GET` is side-effect-limited: it must not call billing, run solvers, record cost attribution, create idempotency rows, or issue new vouchers. The existing `attach_existing_voucher_id()` lookup for completed reproducible rows may still attach an already-issued voucher id to the response object, but Story 3.9 must not create voucher rows or introduce new writes.
9. Existing Story 3.3 and Story 3.8 behavior is preserved: async `POST` continues returning `202 Accepted` with `Location`, idempotency replay of queued/in-progress rows reuses the same status builder, cancellation status remains idempotent, and billing/cancel metadata stays redacted.
10. Regression coverage includes queued default progress, seeded `in_progress` progress/ETA, invalid metadata fallback, completed GET progress closure, failed/timeout compact status, cancelled GET after Story 3.8, cross-tenant 404 no-leak behavior, model_version provider fields, and side-effect guards.

## Tasks / Subtasks

- [x] Task 1: Define status progress response helpers (AC: 2, 3, 4, 5, 6, 7)
  - [x] Add small route-level helpers in `apps/solver-orchestrator/src/solver_orchestrator/routes.py` to read `input_payload._system.progress`, normalize `progress_pct`, normalize `eta_seconds`, and build a public `model_version`.
  - [x] Keep helpers side-effect-free and deterministic; they must return safe defaults for missing or malformed JSONB metadata.
  - [x] Ensure the public `model_version` uses `kind`, not `provider_kind`, and includes `provider_url`.
  - [x] Do not change `OptimizationResponse.status` literals unless implementation proves the response model is actually used for the modified GET path; current route responses are explicit `JSONResponse` bodies.
- [x] Task 2: Wire helpers into existing status responses (AC: 2, 4, 5, 6, 8, 9)
  - [x] Extend `_build_optimization_status_response_content` so queued, in_progress, failed, timeout, and cancelled responses all include normalized `progress_pct` and `eta_seconds`.
  - [x] Extend `_build_response_content` so completed `GET` and idempotent completed POST replay include progress closure without duplicating solution/objective/citation/reproducibility/top-k logic.
  - [x] Keep `_build_async_accepted_response` using the same compact status builder so POST async and GET async remain byte-shape compatible where already tested.
- [x] Task 3: Preserve tenant/security and redaction boundaries (AC: 1, 7, 8, 9)
  - [x] Keep cross-tenant/missing checks before status/progress/model metadata extraction.
  - [x] Do not expose `_system`, billing charge ids, idempotency keys, provider route internals, or raw invalid metadata in any response.
  - [x] Prove `GET` does not call billing, solver, voucher issuance, cost attribution, or idempotency persistence helpers.
  - [x] Preserve existing `attach_existing_voucher_id()` response enrichment for already-issued completed vouchers; do not assert zero invocation of that lookup helper.
- [x] Task 4: Add focused tests and run regression (AC: 1-10)
  - [x] Add `apps/solver-orchestrator/tests/test_status_progress_eta.py`.
  - [x] Cover queued default progress, in_progress seeded progress metadata, invalid metadata fallback, completed progress closure, failed/timeout compact status, cancelled status, cross-tenant 404 no leak, and model_version fields.
  - [x] Run `uv run pytest apps/solver-orchestrator/tests/test_status_progress_eta.py -q`, `uv run pytest apps/solver-orchestrator/tests -q`, `uv run mypy apps packages`, `uv tool run pre-commit run --all-files --show-diff-on-failure`, and `git diff --check`.
- [x] Task 5: BMAD bookkeeping (AC: 10)
  - [x] Update this story's Dev Agent Record, File List, Change Log, and sprint status.
  - [x] After implementation, perform code review and patch findings before merge.

## Dev Notes

### Current Implementation Reality

- Story 3.3 already added `GET /v1/optimizations/{optimization_id}` and `_build_optimization_status_response_content` in `apps/solver-orchestrator/src/solver_orchestrator/routes.py`.
- Existing async `POST` and queued `GET` already return `progress_pct=0` and `eta_seconds=null`, but only for `queued` / `in_progress` compact status responses.
- Existing completed `GET` delegates to `_build_success_response`, which returns the completed optimization body without `progress_pct` or `eta_seconds`.
- There is still no background worker in this repo slice. Story 3.9 must not invent SSE, worker execution, polling jobs, or DB columns. It should expose a durable public response contract and read future-worker progress from JSONB metadata.
- Story 3.8 added `cancelled` status, redacted billing metadata, and idempotent DELETE behavior. Keep cancellation response semantics intact while adding public progress/ETA fields.

### Progress Metadata Contract

Future workers may persist progress under `input_payload._system.progress`:

```json
{
  "progress_pct": 45,
  "eta_seconds": 23,
  "updated_at": "2026-05-27T00:00:00Z",
  "source": "worker"
}
```

Only `progress_pct` and `eta_seconds` are public. Do not serialize `updated_at`, `source`, or the `_system.progress` object unless a later story explicitly adds those public fields.

Default behavior:

- `queued`: `progress_pct=0`, `eta_seconds=null`.
- `in_progress`: read `_system.progress`; fallback to `0/null`; clamp public `progress_pct` to `0..99`.
- `completed`: `progress_pct=100`, `eta_seconds=0`.
- `failed`, `timeout`, `cancelled`: preserve valid recorded `progress_pct` when present; otherwise `progress_pct=0`; always return `eta_seconds=null` to avoid stale ETA after work has stopped.

### Existing Code to Reuse

- Auth and owner isolation: `get_optimization` in `apps/solver-orchestrator/src/solver_orchestrator/routes.py`.
- Compact status builder: `_build_optimization_status_response_content`.
- Completed response content: `_build_response_content`; avoid duplicating solution/objective/citation/reproducibility/top-k logic.
- Idempotency replay for completed rows also uses `_build_success_response` / `_build_response_content`; adding completed progress fields there intentionally makes replay and GET consistent.
- Model version source: `route.model_version` from `select_provider_route()` and catalog entries in `apps/solver-orchestrator/src/solver_orchestrator/catalog.py`.
- Error contract: Story 3.7 `error_responses.py` and `_rfc7807_error`; do not add ad hoc FastAPI error bodies.

### Boundary Rules

- `GET` must remain side-effect-limited and must not trigger side effects that belong to POST/DELETE.
- Missing and cross-tenant optimization ids must be indistinguishable `404`.
- Cross-tenant check must happen before reading or branching on status/progress/billing metadata.
- Invalid persisted progress metadata must degrade to safe defaults, not a 500.
- Do not add migrations. JSONB `_system.progress` is sufficient for this story.
- Do not implement SSE stream, email fallback, station-message notification, or actual worker progress updates here; those are separate PRD progress-notification surfaces.
- Do not expose internal `provider_route.provider_kind`; public `model_version.kind` is the contract.
- Do not add new Pydantic response models or dependencies unless needed by tests. Existing response paths return `JSONResponse` dictionaries, and this story can remain helper-level.
- Preserve existing status handling for unknown historical statuses as safe compact status responses with normalized progress fields; do not add 500s for unrecognized status strings.

### Previous Story Intelligence

- Story 3.7 centralized Problem Details and sensitive-value redaction. Reuse it for not-found/auth errors.
- Story 3.8 established cancellation status redacts billing charge ids and stores internal billing metadata under `_system.billing`. Do not leak that object when adding progress fields.
- Story 3.8 also showed JSONB mutation needs fresh assignment to persist. This story should not mutate JSONB in GET at all.
- Recent solver stories keep tests focused in a new story test file first, then run the full solver-orchestrator suite, mypy, pre-commit, and diff-check.

### Testing Standards

- Use existing async HTTP test style from `apps/solver-orchestrator/tests/test_sync_async_mode.py` and `apps/solver-orchestrator/tests/test_cancel_refund.py`.
- Seed `in_progress` rows directly through SQLAlchemy for progress metadata cases; there is no worker to produce them yet.
- Stub or monkeypatch billing/solver/voucher/cost helpers in read-only tests so accidental side effects fail loudly.
- Include one completed row path created through real POST to prove completed GET preserves existing success content while adding progress closure.

### References

- `_bmad-output/planning/epics.md` Story 3.9 lines near `Status / progress / eta / model_version`.
- `_bmad-output/planning/prd.md` FR E9 and Long-Running Task Response.
- `_bmad-output/planning/architecture.md` P50 Loading State progress mapping.
- `_bmad-output/stories/3-8-cancel-refund.md` cancellation status/redaction patterns.
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py` status builders and `GET /v1/optimizations/{optimization_id}`.
- `apps/solver-orchestrator/tests/test_sync_async_mode.py` existing queued async status tests.

## Story Review Rounds

### Round 1 - Data Consistency (2026-05-27)

Findings applied:

- AC3 could be read as replacing the entire response with exactly four model fields. It now scopes the requirement to fields inside `model_version` and explicitly excludes internal provider-route metadata.
- The PRD long-running example used `provider_kind`, while existing schema and Epics A-S1 fix use `kind`. The story now locks public output to `kind` and forbids leaking the internal alias.
- `in_progress` could otherwise report `progress_pct=100` while still not terminal. The story now clamps in-progress public progress to `0..99`.
- Terminal ETA semantics were ambiguous. Completed rows now return `eta_seconds=0`; failed, timeout, and cancelled rows include `eta_seconds=null` so stale worker estimates are not shown after work stops.
- Numeric normalization was under-specified. The story now requires finite numeric persisted values to be converted with `int(value)` and clamped.

Result: public field semantics, status/progress closure, and model_version naming are now data-consistent.

### Round 2 - Function / Dependency Consistency and Drift (2026-05-27)

Findings applied:

- Completed GET uses `_build_success_response` through `_build_response_content`, and idempotent completed POST replay uses the same path. Task 2 now explicitly extends `_build_response_content` instead of adding a parallel completed-status response builder.
- The draft could prompt unnecessary `OptimizationResponse` schema changes. Task 1 now states not to change response-model literals unless the modified route path actually uses them.
- Idempotency replay consistency was implicit. Dev Notes now call out that adding completed progress fields to `_build_response_content` intentionally keeps completed GET and replay aligned.
- New dependencies/Pydantic models are unnecessary for this story. Boundary rules now require helper-level changes unless tests prove otherwise.

Result: implementation should reuse existing response builders, avoid duplicate completed response logic, and avoid dependency/schema drift.

### Round 3 - Boundary / Edge Cases / Closure (2026-05-27)

Findings applied:

- AC8 said GET must be fully read-only, but current completed GET may call `attach_existing_voucher_id()` to enrich a response with an already-issued voucher id. AC8 and Task 3 now narrow the rule to no new side effects, no voucher issuance, and no billing/solver/cost/idempotency writes while preserving existing voucher lookup behavior.
- Failed and timeout compact status coverage was missing from tests even though AC6 requires terminal rows to include progress fields. AC10 and Task 4 now explicitly include failed/timeout coverage.
- Historical malformed `model_version` rows could become a new 500 risk if the story validated too aggressively. AC7 now requires safe behavior for missing/malformed model_version.
- Unknown historical status strings were not addressed. Boundary rules now require safe compact responses with normalized progress fields instead of introducing 500s.

Result: side-effect limits, terminal coverage, malformed metadata, and historical-status closure are explicit before implementation.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-27 - Initial Story 3.9 draft created from sprint status, Epics/PRD/Architecture/UX, Story 3.8 learnings, current solver-orchestrator status route, and existing async/cancel tests.
- 2026-05-27 - Three story review rounds completed before implementation: data consistency, function/dependency consistency, and boundary/closure.
- 2026-05-27 - Dev implementation started; sprint/story status moved to in-progress.
- 2026-05-27 - RED phase confirmed: Story 3.9 tests failed on missing progress metadata reads, missing terminal progress fields, and completed GET lacking progress closure.
- 2026-05-27 - Implemented normalized progress/ETA helpers, public model_version shaping, completed/compact response wiring, and historical malformed model_version fallback.
- 2026-05-27 - Focused Story 3.9 tests passed: `uv run pytest apps/solver-orchestrator/tests/test_status_progress_eta.py -q` -> 8 passed.
- 2026-05-27 - Adjacent Story 3.3/3.8 regressions passed: sync/async tests 16 passed; cancel/refund tests 8 passed.
- 2026-05-27 - Full solver-orchestrator suite passed: 252 passed.
- 2026-05-27 - Post-implementation code review found one patch: `_public_model_version()` needed to validate the `kind` enum, not just required field presence, so malformed historical rows cannot trigger Pydantic 500s. Patched by reusing `ModelVersionSchema`.
- 2026-05-27 - Final validation passed after review patch: Story 3.9 tests 9 passed; full solver-orchestrator suite 253 passed; mypy, pre-commit, and diff-check passed.

### Completion Notes List

- Story draft scopes FR E9 to the existing owner-authenticated `GET /v1/optimizations/{id}` response contract.
- Story draft intentionally excludes SSE, notification channels, worker execution, and database migrations.
- Implemented shared route helpers for `_system.progress` reads, progress clamping, ETA normalization, and public `model_version` shaping.
- Completed, queued, in-progress, failed, timeout, cancelled, and historical malformed model_version GET paths now include the Story 3.9 progress/ETA contract without leaking `_system`.
- Added read-only side-effect guard tests for GET status.
- Post-review patch now validates public model_version through `ModelVersionSchema`, including the `kind` enum, and safely returns `model_version=null` for malformed historical rows.

### File List

- `_bmad-output/stories/3-9-status-progress-eta.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/test_status_progress_eta.py`

### Change Log

- 2026-05-27 - Initial Story 3.9 draft created and sprint status moved from backlog to ready-for-dev.
- 2026-05-27 - Applied three pre-implementation story review rounds and moved story to in-progress.
- 2026-05-27 - Implemented Story 3.9 status/progress/ETA contract and focused regression tests.
- 2026-05-27 - Addressed post-implementation code review finding for model_version enum validation and marked story done after final validation.

## Senior Developer Review (AI) - Post-Implementation (2026-05-27)

### Review Findings

- [x] [Review][Patch] Public model_version validation accepted any string `kind`, so historical rows with a malformed provider kind could still reach `OptimizationResponse` and raise a 500. Patched `_public_model_version()` to validate through `ModelVersionSchema` and added regression coverage for invalid `kind`.

### Result

All review findings were patched. Re-ran Story 3.9 focused tests, full solver-orchestrator suite, mypy, pre-commit, and diff-check successfully. Review outcome: approved / done.
