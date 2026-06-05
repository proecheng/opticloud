---
baseline_commit: c6d17c0ee337c366e8f747992bddd813d8a0be6c
---

# Story 6.C.1: Auto-migrate to Equivalent Provider

Status: code-review

## Story

As a voucher holder affected by Provider exit,
I want voucher rerun to migrate automatically to an equivalent active Provider when the locked Provider is no longer usable,
so that the 5-year reproducibility promise continues without manual provider selection during Provider retirement.

## Acceptance Criteria

1. Rerun performs a deterministic provider-migration preflight before any durable writes.
   - `POST /v1/reproduce/{voucher_id}/rerun` keeps all existing Story 6.B.3/6.B.4 gates first: API-key owner check, issued status, 5-year UTC expiry, source optimization ownership/completion, empty body, no billing header, LP-only support, and executable locked solver.
   - After those gates and before creating `optimizations`, `reproduction_vouchers`, or `idempotency_keys` rows, the rerun path resolves the locked provider from `reproduction_vouchers.locked_model_version`.
   - If the locked provider is active in the current provider/capability snapshot, the rerun behavior remains byte-compatible with the current normal LP/highs rerun: original locked model version is reused and no provider-migration response field is added.
   - If the locked provider is `deprecated`, `inactive`, `exiting`, `retired`, `unavailable`, or absent from the snapshot, the rerun path must attempt equivalent-provider resolution before solve execution.
   - Migration resolution must run before the nested transaction that inserts the rerun optimization.

2. Equivalent-provider matching is pure, deterministic, and capability-bound.
   - Add a small pure resolver under `apps/solver-orchestrator/src/solver_orchestrator/`; do not add a new service, scheduler, UI, public API, network call to capability-registry, or cross-service import.
   - The resolver consumes a provider/capability snapshot derived from the existing solver catalog, with tests allowed to pass explicit snapshots for exit/equivalent cases.
   - Matching requires the same `task_type`, the same executable `locked_solver`, and the same normalized capability tags as the source provider.
   - The resolver must not select a candidate with a weaker/unrelated capability tag set, different task family, unsupported locked solver, unaudited self algorithm, or non-active provider lifecycle status.
   - Ranking must be stable for the same voucher, locked model version, task type, solver, and snapshot. Tie-break order: same provider kind first, closest semantic version when parseable, then lexicographic `provider_id`, `version`, and `k_algo`.
   - The resolver must expose explicit statuses for `not_required`, `migrated`, and `no_equivalent`; it must not throw for ordinary no-match cases.

3. Successful migrated rerun preserves lineage while locking the child voucher to the selected provider.
   - When migration succeeds, the rerun solve still uses the existing LP/highs execution path; this story migrates Provider metadata, not solver execution infrastructure.
   - The new rerun optimization's `model_version` and `_system.reproducibility.locked_model_version` must use the selected equivalent provider's public model version.
   - The new child `reproduction_vouchers.locked_model_version` must persist the selected equivalent provider, while `parent_voucher_id` and `rerun_depth` continue to link to the source voucher.
   - The source optimization, source voucher, and source voucher locked model version must remain unchanged.
   - Anonymous voucher inheritance, idempotency replay, no-billing behavior, and top-k rerun behavior remain unchanged.

4. Migration decisions are auditable without leaking into standard optimization responses.
   - Migrated rerun responses include a top-level rerun-only `provider_migration` object.
   - `provider_migration` includes only non-sensitive fields: status, reason, ranking version, task type, locked solver, normalized capability tags, source provider public model version/status, selected provider public model version/status, and candidates considered count.
   - Normal rerun responses where no migration was required must not include `provider_migration`.
   - Standard `POST /v1/optimizations`, `/demo`, and `GET /v1/optimizations/{id}` responses must not gain a top-level `provider_migration` field.
   - It is acceptable to persist migration metadata inside the rerun optimization `_system` payload so idempotency replay can reproduce the same rerun response.

5. Safe failure is explicit and atomic.
   - If the locked provider requires migration and no equivalent active provider exists, rerun returns deterministic RFC7807 `409` with title `Provider Migration Required`.
   - The error must identify the locked provider ID, task type, locked solver, and the matching constraint, but must not expose raw user payloads, API keys, billing IDs, owner identifiers, or provider secrets.
   - No-equivalent failure must not create `optimizations`, `reproduction_vouchers`, or `idempotency_keys` rows.
   - No-equivalent failure must not call billing reserve/finalize, provider HTTP, capability-registry HTTP, or the LP solver.

6. Scope stays narrow and does not pre-implement adjacent stories.
   - Do not implement Story 6.C.2 provider exit 30-day notification, email,站内信,status-page automation, or notification preferences.
   - Do not implement Story 6.C.3 capability vocabulary authoring/governance workflows beyond deriving normalized tags needed by this resolver.
   - Do not implement Story 6.C.4 broader equivalent-matching service, ML scoring, manual review queues, or cross-task equivalence.
   - Do not modify capability-registry schema/API, provider application/shadow/rollout workflows, provider KPI dashboards, or revenue-share flows.
   - Do not change voucher ID format, 5-year expiry semantics, normal voucher issuance, or public optimization request schemas.

7. Tests prove migration correctness, boundaries, and regressions.
   - Add pure resolver tests for active source `not_required`, deprecated/exit source `migrated`, no-equivalent, unrelated tag rejection, unsupported solver rejection, non-active candidate rejection, same-kind preference, semantic-version distance, and lexicographic deterministic tie-breaks.
   - Add rerun integration tests for migrated LP/highs rerun creating exactly one child voucher locked to the selected provider, preserving source rows, and returning rerun-only `provider_migration`.
   - Add rerun integration tests for no-equivalent failure with unchanged `optimizations`, `reproduction_vouchers`, and `idempotency_keys` counts.
   - Add regressions that normal LP/highs rerun without migration remains unchanged, idempotency replay includes the same migration metadata, anonymous migrated rerun preserves anonymity, no billing helper is called, and standard optimization/demo/GET responses do not expose top-level `provider_migration`.
   - Run focused provider-migration/rerun tests, the solver-orchestrator test suite as feasible, `uv run mypy apps packages`, and `git diff --check`.

8. Workflow and GitHub closure are enforced.
   - This story records exactly three pre-implementation adversarial review rounds and the modifications made after each round.
   - Implementation moves the story through `in-progress` and `code-review` only when corresponding gates pass.
   - Post-implementation code review findings are fixed or explicitly documented before GitHub sync.
   - GitHub PR CI must pass, PR must be merged, remote branch deleted, and local `main` synced before this story or sprint status is marked `done`.
   - The final `done` status update must be a separate status-sync commit after merge/sync.

## Tasks / Subtasks

- [x] Build pure provider migration resolver. (AC: 1, 2, 5)
  - [x] Add provider/capability snapshot types and normalized tag derivation from the existing solver catalog.
  - [x] Model provider lifecycle statuses and migration result statuses without adding DB schema or service calls.
  - [x] Implement deterministic equivalent filtering and ranking.
  - [x] Return JSON-safe audit metadata for migrated and no-equivalent outcomes.

- [x] Wire migration preflight into rerun. (AC: 1, 3, 4, 5)
  - [x] Invoke migration preflight after existing rerun eligibility checks and before rerun row insertion.
  - [x] Use the selected provider model version for rerun reproducibility payload, rerun optimization `model_version`, and child voucher lock.
  - [x] Persist migration metadata only inside the rerun optimization `_system` payload.
  - [x] Expose top-level `provider_migration` only in rerun responses for migrated reruns and idempotency replay.
  - [x] Return RFC7807 `409 Provider Migration Required` for no-equivalent without creating rows or calling solver/billing/provider services.

- [x] Add resolver and rerun regression tests. (AC: 2, 3, 4, 5, 7)
  - [x] Cover pure resolver match, no-match, tag/solver/status rejection, and deterministic ranking.
  - [x] Cover migrated rerun success, source preservation, child voucher lock, anonymous inheritance, idempotency replay, and no-billing behavior.
  - [x] Cover no-equivalent failure with row-count assertions and no solver execution.
  - [x] Cover normal rerun and standard optimization/demo/GET response shape regressions.

- [x] Validate and update workflow records. (AC: 7, 8)
  - [x] Run focused tests for provider migration and rerun.
  - [x] Run broader solver tests as feasible.
  - [x] Run `uv run mypy apps packages`.
  - [x] Run `git diff --check`.
  - [x] Update Dev Agent Record, File List, Change Log, and post-implementation review notes.

## Dev Notes

### Context

- Epic 6.C is the v2 auto-migration + Provider Exit slice. Story 6.C.1 owns the automatic rerun migration decision; Story 6.C.2 owns 30-day notification; Story 6.C.3 owns full vocabulary design; Story 6.C.4 owns broader equivalent matching.
- PRD R4 requires auto-migration to an equivalent Provider using a capability vocabulary. PRD R7 separately requires 30-day provider-exit notification.
- Story 6.B.3 already implemented `POST /v1/reproduce/{voucher_id}/rerun`, owner-visible 404 behavior, 5-year UTC calendar expiry, LP/highs-only rerun, child voucher lineage, user-scoped idempotency, no billing, and no partial-row failure behavior.
- Story 6.B.4 added anonymous voucher persistence and rerun inheritance.
- Story 6.B.7 added side-effect-free reproducibility audit tooling and explicitly excluded provider auto-migration.
- Story 7.A.1 created `apps/capability-registry` as a separate FastAPI service with provider/capability/tags and Redis cache, but solver-orchestrator still uses static routing. This story must not make solver-orchestrator import capability-registry code or perform live network lookups.
- Current production execution support for rerun remains LP/highs. Provider migration can change locked provider metadata to an equivalent active provider that still supports the same executable solver; it must not invent a new solver runtime.

### Relevant Source Anchors

- Epic 6.C source: `_bmad-output/planning/epics.md` Story 6.C.1 and Epic 6.C.
- PRD R4/R7 source: `_bmad-output/planning/prd.md` Reproducibility & Academic Integrity table and Core Innovation #2.
- Architecture source: `_bmad-output/planning/architecture.md` Capability Registry backbone, Provider routing, Repro 5y SLA Engineering, C17 service boundary.
- Existing rerun route: `apps/solver-orchestrator/src/solver_orchestrator/routes.py` `rerun_reproduction`.
- Existing rerun helpers: `apps/solver-orchestrator/src/solver_orchestrator/routes.py` `_hash_rerun_request`, `_voucher_expiry_utc`, `_strip_system_metadata`, `_load_owner_visible_voucher`, `_load_source_optimization_for_voucher`, `_build_rerun_response_content`.
- Existing voucher helpers: `apps/solver-orchestrator/src/solver_orchestrator/repro.py` `issue_reproduction_voucher`, `build_rerun_lineage_payload`, `attach_existing_voucher_id`.
- Existing provider route contract: `apps/solver-orchestrator/src/solver_orchestrator/provider_routing.py`.
- Existing static catalog: `apps/solver-orchestrator/src/solver_orchestrator/catalog.py`.
- Existing rerun tests: `apps/solver-orchestrator/tests/test_reproduction_rerun.py`.
- Existing provider routing tests: `apps/solver-orchestrator/tests/test_provider_routing.py`.
- Existing routing history response behavior: `apps/solver-orchestrator/src/solver_orchestrator/routes.py` `_routing_history_metadata` and `apps/solver-orchestrator/tests/test_routing_history.py`.
- Existing capability-registry tag normalization model for reference only: `apps/capability-registry/src/capability_registry/schemas.py` `normalize_tag`; do not import it into solver-orchestrator.

### Implementation Guidance

- Prefer a new local module such as `solver_orchestrator.provider_migration` for pure resolver logic. Keep it dependency-local to solver-orchestrator plus existing catalog types.
- Do not mutate `CATALOG` in production code. Snapshot builders should return copied immutable-ish data structures.
- If adding optional static catalog fields for future compatibility, keep them optional and backward compatible. Existing public catalog schemas must not start exposing provider lifecycle internals unless tests already require that surface.
- Keep migration metadata JSON-safe and non-sensitive. Do not include raw optimization input, source payload, API key IDs, user IDs, billing IDs, provider request/response bodies, or secrets.
- Use `_attach_system_metadata` / `_attach_reproducibility_metadata` patterns because SQLAlchemy does not detect nested JSONB mutation reliably.
- On migrated success, pass the selected model version into `_build_reproducibility_payload`; `issue_reproduction_voucher` will persist the selected locked model version from `_system.reproducibility`.
- On no-equivalent, return before `session.begin_nested()` and before `solvers.solve_from_request(...)`.
- Keep `locked_solver` unchanged. A Provider equivalent that does not support the locked solver is not equivalent for this story.
- Keep idempotency request hash unchanged: it remains voucher-aware via `_hash_rerun_request(voucher_id)`. The replayed optimization should already carry persisted migration metadata.

### Project Structure Notes

- New backend module, if needed: `apps/solver-orchestrator/src/solver_orchestrator/provider_migration.py`.
- Pure resolver tests can live in `apps/solver-orchestrator/tests/test_provider_migration.py`.
- Rerun integration regressions should extend `apps/solver-orchestrator/tests/test_reproduction_rerun.py` unless a separate focused test file is clearer.
- Type additions to `apps/web/src/lib/api.ts` are only required if the existing rerun response type rejects the new optional rerun-only `provider_migration` field.
- No SQL migration should be needed for this story.

### Testing Notes

- Use explicit test snapshots rather than changing global production catalog state where possible.
- For rerun integration tests, monkeypatch the provider-migration snapshot/resolver boundary in `solver_orchestrator.routes` or `solver_orchestrator.provider_migration` so tests can simulate source provider exit and an active equivalent provider deterministically.
- Use row-count assertions around no-equivalent and body/header failures: `optimizations`, `reproduction_vouchers`, and `idempotency_keys` must remain unchanged.
- Use monkeypatch to make billing helpers raise in rerun tests; migration must not call them.
- Use monkeypatch to make solver execution raise in no-equivalent tests; migration failure must return before solver execution.
- Suggested commands:
  - `$env:PYTHONPATH='D:\优化预测网站-6-c-1-auto-migrate-provider\apps\solver-orchestrator\src;D:\优化预测网站-6-c-1-auto-migrate-provider\packages\shared-py'`
  - `uv run pytest apps/solver-orchestrator/tests/test_provider_migration.py apps/solver-orchestrator/tests/test_reproduction_rerun.py -q`
  - `uv run pytest apps/solver-orchestrator/tests/ -q`
  - `uv run mypy apps packages`
  - `git diff --check`

## Story Review Log

### Round 1: Boundary / Scope / Fake-Completion Review

Findings:

1. The initial draft did not define exactly when migration runs relative to rerun validation and row insertion, leaving room for partial child vouchers or idempotency rows.
2. Provider-exit state was described abstractly, but the current code has no provider-exit service. Without a local lifecycle model, implementation could fake completion by always returning the locked provider.
3. The story did not preserve the existing LP/highs execution boundary and could be misread as requiring a new provider runtime.
4. It did not state whether normal active-provider reruns must remain response-compatible.

Revision after Round 1:

- Added migration preflight ordering after existing rerun gates and before durable writes.
- Defined active vs migration-required lifecycle states, including absent snapshot rows.
- Explicitly scoped migration to Provider metadata with unchanged LP/highs execution.
- Added normal rerun byte-compatible behavior and no `provider_migration` field when migration is not required.

Status: PASS after revision.

### Round 2: Drift / Data Consistency / Matching Review

Findings:

1. "Equivalent" was underspecified and could drift into selecting unrelated providers with the same task label.
2. Ranking was not deterministic enough for idempotency, audit replay, and reproducibility evidence.
3. The child voucher lock target was unclear: source locked model version vs selected equivalent model version.
4. Migration metadata could leak into standard optimization responses or include sensitive source payload fields.

Revision after Round 2:

- Required same task type, same locked solver, and identical normalized capability tags.
- Added deterministic ranking order: same kind, semantic-version distance, then lexical provider/version/k_algo.
- Required rerun optimization, reproducibility handoff, and child voucher to lock the selected equivalent provider while source rows remain unchanged.
- Added rerun-only top-level `provider_migration` rules and a non-sensitive metadata field allowlist.

Status: PASS after revision.

### Round 3: Dependency / CI / Closure Review

Findings:

1. Story 7.A.1 created capability-registry, but importing it from solver-orchestrator would violate the service boundary and make tests depend on another service.
2. No-equivalent failure needed explicit closure: no DB rows, no solver call, no billing call, no provider/capability HTTP.
3. Adjacent Epic 6.C stories could be accidentally pulled in: 30-day notification, full vocabulary governance, broader matching service.
4. The workflow could mark `done` before GitHub merge/sync unless the story restated the required ordering.

Revision after Round 3:

- Required a local pure resolver and static/explicit snapshot input with no cross-service imports or network calls.
- Added atomic no-equivalent failure requirements and test guidance for row counts plus no solver/billing side effects.
- Added explicit out-of-scope list for 6.C.2, 6.C.3, 6.C.4, provider dashboards, registry schema changes, and public API/schema changes.
- Added GitHub closure rule: PR CI, merge, remote branch delete, local `main` sync, then separate status-sync commit for `done`.

Status: PASS after revision. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

1. Add a pure provider-migration resolver with catalog snapshot derivation, normalized capability tags, lifecycle states, deterministic matching, and JSON-safe metadata.
2. Wire rerun migration preflight after existing voucher/source/solver checks and before nested transaction creation.
3. Use the selected equivalent provider model version for migrated rerun reproducibility and child voucher issuance.
4. Add resolver and rerun integration regressions for success, safe failure, idempotency, anonymity, no billing, and response shape boundaries.
5. Run local validation, perform post-implementation code review, fix/document findings, then complete GitHub sync before separate status-done commit.

### Debug Log References

- 2026-06-05 - Rebased existing local 6.C.1 draft branch onto `origin/main` after preserving the draft in a local commit.
- 2026-06-05 - Rewrote story from current Epic 6.C, PRD R4/R7, Story 6.B.3/6.B.4/6.B.7 rerun context, Story 7.A.1 capability-registry boundary, and current solver-orchestrator routing code.
- 2026-06-05 - Red phase: `test_provider_migration.py` failed because `solver_orchestrator.provider_migration` did not exist.
- 2026-06-05 - Green phase: implemented local provider migration resolver and rerun preflight, then fixed tag normalization and RFC7807 error-key behavior.
- 2026-06-05 - Validation: focused provider-migration/rerun tests, ruff, mypy, `git diff --check`, and full solver-orchestrator tests passed.

### Completion Notes List

- Story context created for equivalent-provider auto-migration within the existing solver-orchestrator rerun boundary.
- Exactly three pre-implementation adversarial review rounds completed and revisions reflected in the document before implementation.
- Added `solver_orchestrator.provider_migration` with local catalog snapshot derivation, normalized capability tags, lifecycle states, deterministic equivalent filtering/ranking, and JSON-safe migration metadata.
- Wired provider migration into `POST /v1/reproduce/{voucher_id}/rerun` after existing eligibility checks and before rerun row insertion; no-equivalent failures return `409 Provider Migration Required` without durable writes or solver execution.
- Migrated reruns lock the child optimization/voucher reproducibility metadata to the selected equivalent provider while preserving source optimization/voucher rows and normal active-provider rerun response shape.
- Added resolver and rerun regressions for migration success, no-equivalent atomic failure, idempotency replay, normal rerun omission of migration metadata, ranking, and catalog snapshot behavior.
- Validation passed: focused tests `22 passed`; solver-orchestrator suite `369 passed`; ruff passed; mypy passed; `git diff --check` passed.

### File List

Created:
- `_bmad-output/stories/6-c-1-auto-migrate-provider.md`
- `apps/solver-orchestrator/src/solver_orchestrator/provider_migration.py`
- `apps/solver-orchestrator/tests/test_provider_migration.py`

Modified:
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/error_catalog.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/test_reproduction_rerun.py`

### Change Log

- 2026-06-05 - Created Story 6.C.1 implementation-ready context and completed three pre-implementation adversarial review rounds.
- 2026-06-05 - Implemented provider auto-migration resolver, rerun preflight integration, RFC7807 provider-migration error catalog entry, and regression coverage; story moved to code-review.

## Post-Implementation Code Review

### Scope

- Reviewed provider migration resolver, rerun route integration, RFC7807 catalog mapping, and provider-migration/rerun regression coverage against AC 1-8.
- Checked boundary risks: service boundary to capability-registry, durable-write ordering, no-equivalent atomicity, normal-rerun response drift, standard optimization response leakage, source/child voucher consistency, and deterministic ranking.

### Findings

1. Finding: default capability tags initially included `k_algo`, which made absent-source-provider migrations too strict and could block valid task-equivalent active providers when the retired provider no longer appears in the local snapshot.
   - Risk: AC 1/2 failure for absent snapshot rows; no-equivalent false negatives during provider exit.
   - Resolution: default tag derivation now uses task-level tags only, with LP normalized to `lp` + `linear_programming`; added `test_missing_source_provider_uses_task_capability_tags_for_equivalent_match` and updated the current HiGHS catalog snapshot regression.

2. Finding: RFC7807 title normalization needed a dedicated `provider_migration_required` catalog key.
   - Risk: `409 Provider Migration Required` could drift into a generic/idempotency conflict shape.
   - Resolution: added `provider_migration_required` to `ERROR_CATALOG` and `TITLE_TO_KEY`.

### Review Result

- No remaining blocking findings after fixes.
- Validation evidence: focused provider-migration/rerun tests `22 passed`; full solver-orchestrator suite `369 passed`; targeted ruff passed; `uv run mypy apps packages` passed; `git diff --check` passed.
- Story intentionally remains `code-review` until GitHub PR CI passes, PR is merged, remote branch is deleted, and local `main` is synced. Final `done` status will be a separate status-sync commit.
