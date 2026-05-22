# Story 6.B.4: Anonymous voucher (R6)

Status: done

## Story

As a user issuing a reproducible voucher for blind review,
I want to mark the voucher as anonymous,
so that I can share the voucher and rerun evidence without exposing owner-identifying details.

## Acceptance Criteria

1. Anonymous mode is an explicit opt-in on the reproducible LP voucher path.
   - Add `options.anonymous` to `OptimizationOptions`; it defaults to `false`.
   - `options.anonymous` is only accepted when `options.reproducible: true` on request paths that parse `OptimizationRequest`; otherwise return 422 RFC 7807.
   - The authenticated POST success response, completed GET, and rerun responses expose `reproducibility.anonymous: true` when requested.
   - The LP demo preview path mirrors the same `reproducibility.anonymous` field for preview parity.
   - The canonical request fingerprint and Idempotency-Key body hash must treat `options.anonymous` as part of the request body so anonymous and non-anonymous runs stay distinct.
   - Standard non-anonymous responses must not emit `anonymous: false`, `anonymous: null`, or any top-level anonymous field; omit it entirely unless requested.

2. Anonymous voucher metadata is persisted durably and inherited.
   - Add `anonymous BOOLEAN NOT NULL DEFAULT FALSE` to `reproduction_vouchers` and the matching ORM / raw SQL schema.
   - Treat `reproduction_vouchers.anonymous` as authoritative for authenticated voucher flows; mirror the same value into `Optimization.input_payload._system.reproducibility` so completed GET/idempotency replay stays compatible.
   - Anonymous status is inherited by child rerun vouchers and cannot be turned off by rerun requests.
   - Keep `parent_voucher_id` and `rerun_depth` semantics from Story 6.B.3 unchanged.

3. Anonymous vouchers remain blind-review safe.
   - Anonymous mode does not suppress voucher IDs or rerun lineage fields; it suppresses owner-identifying details only.
   - Voucher-facing responses and helpers must not surface owner profile data, auth secrets, or raw request bodies.
   - Externally shareable payloads must not introduce `email`, `phone`, `id_card`, `bank_account`, or similar owner profile fields.
   - P30 logging rules still apply; do not add extra PII to logs or outbox-like payloads.

4. API and shared types stay aligned.
   - Update backend response serialization so anonymous reproducible runs carry the flag through the existing reproducibility object only.
   - Update `apps/web/src/lib/api.ts` to include the optional anonymous field in the `Reproducibility` contract if the solver client models these responses.
   - Keep standard non-anonymous optimization/demo response shapes unchanged.

5. Regression tests prove the contract.
   - Add tests for anonymous reproducible LP success on authenticated POST.
   - Add tests for persisted anonymous flag on completed GET and idempotency replay.
   - Add tests that rerun of an anonymous voucher preserves anonymity.
   - Add tests for demo LP preview parity.
   - Add tests that anonymous responses omit owner-identifying fields and do not emit `anonymous: null` or `anonymous: false`.
   - Add tests for invalid `options.anonymous: true` without `options.reproducible: true`.

6. Scope remains within solver-orchestrator.
   - Do not add a new repro-service, public lookup endpoint, UI card, or archive job in this story.
   - Do not change voucher ID format or rerun 5-year logic in this story.
   - Do not widen the anonymous contract into unrelated billing, provider, or citation flows.

## Tasks / Subtasks

- [x] Add anonymous request/schema plumbing. (AC: 1, 2, 4)
  - [x] Extend `OptimizationOptions` and the nested reproducibility schema so anonymous opt-in can be represented explicitly as an optional field.
  - [x] Add `anonymous` column to `infra/local-init/02-solver-schema.sql` and `ReproductionVoucher`.
  - [x] Keep anonymous metadata conditional in responses so non-anonymous payloads do not gain a new key.
  - [x] Make `_build_reproducibility_payload` accept an anonymous flag and only include it when true.
- [x] Persist anonymous voucher lineage. (AC: 2, 3)
  - [x] Thread anonymous mode through `issue_reproduction_voucher` and the rerun issuance path.
  - [x] Persist anonymous in the durable voucher row and mirror it into `_system.reproducibility` for compatibility.
  - [x] Preserve inheritance across `parent_voucher_id` / `rerun_depth` without altering Story 6.B.3 behavior.
  - [x] Prefer the durable voucher row when reconstructing anonymous state for completed GET/idempotency replay if the JSON mirror is missing.
- [x] Harden response and redaction behavior. (AC: 1, 3, 4)
  - [x] Make POST, GET, demo, and rerun response shaping keep anonymous metadata only on opt-in voucher flows.
  - [x] Ensure the anonymous path does not leak owner-identifying fields in shareable payloads.
  - [x] Keep the normal non-anonymous response contract byte-compatible except for the new opt-in anonymous shape.
- [x] Add regression coverage and type sync. (AC: 1, 2, 4, 5)
  - [x] Test anonymous opt-in validation, durable persistence, GET replay, demo parity, rerun inheritance, and omission of false/null.
  - [x] Test same `Idempotency-Key` with different `options.anonymous` values returns 409 rather than replaying the wrong voucher.
  - [x] Update `apps/web/src/lib/api.ts` only if solver client types need the anonymous field.

## Dev Notes

### Context

- Story 6.B.1 already added the reproducibility handoff under `_system.reproducibility`.
- Story 6.B.2 added permanent durable vouchers and voucher IDs.
- Story 6.B.3 added rerun lineage and 5-year voucher reuse.
- Story 6.B.4 is the blind-review / privacy layer for the same voucher chain; it should not create a separate public service or new endpoint family.

### Scope Decision

- Anonymous is a durable voucher property, not just a response decoration.
- Treat the durable voucher row as authoritative for `anonymous`; keep `_system.reproducibility` as the compatibility mirror used by response replay.
- Keep implementation in solver-orchestrator for now; `repro-service` is still only a future architecture target.
- The accepted opt-in shape is `options.anonymous: true` alongside `options.reproducible: true`.
- The anonymous bit is part of the request identity; it must flow into canonical request fingerprints and idempotency deduping instead of being treated as cosmetic metadata.
- Standard non-anonymous voucher behavior must remain unchanged except for the new optional anonymous field when explicitly requested.

### What this story must do

- Extend the existing reproducibility / voucher flow rather than forking a separate anonymous path.
- Keep anonymous mode compatible with the current `reproducibility.voucher_id` contract, rerun lineage, and idempotency replay.
- Preserve internal audit ownership (`user_id`, `api_key_id`) while keeping shareable payloads blind-review safe.
- Keep response serialization discipline so the new field does not turn into `anonymous: false` on every response.

### What this story must not do

- Do not add a new lookup endpoint for vouchers.
- Do not add a new `repro-service` or move ownership out of solver-orchestrator yet.
- Do not change voucher ID format, rerun expiry logic, or billing behavior.
- Do not add UI surface area in this story.
- Do not expose owner profile data in any externally shared voucher payload.

### Relevant Source Anchors

- Epic 6.B sequence and story split: `_bmad-output/planning/epics.md` around `Epic 6.B` and Story `6.B.4`
- PRD FR R6: `_bmad-output/planning/prd.md` section `6. Reproducibility & Academic Integrity`
- Architecture naming / privacy / reproducibility anchors: `_bmad-output/planning/architecture.md` sections `P23`, `P30`, `repro-service`, and `Database Topology`
- Previous implementation: `_bmad-output/stories/6-b-1-mark-reproducible.md`
- Voucher issuance and rerun helpers: `apps/solver-orchestrator/src/solver_orchestrator/repro.py`
- Rerun route and response shaping: `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- ORM models: `apps/solver-orchestrator/src/solver_orchestrator/models.py`
- Request / response schemas: `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`
- Shared frontend API client: `apps/web/src/lib/api.ts`
- Raw schema bootstrap: `infra/local-init/02-solver-schema.sql`

### Project Structure Notes

- Prefer extending the existing `repro.py` helper flow instead of scattering anonymous-specific logic across routes.
- Keep `Optimization.input_payload` JSONB writes assignment-based, not nested in-place mutation, so SQLAlchemy reliably flushes the anonymous flag update.
- Use the same response-building pattern already established in 6.B.1/6.B.2/6.B.3 so standard optimization responses stay stable.
- Preserve the existing owner-visible voucher lookup and rerun flow; anonymous mode should only refine what is persisted and exposed, not introduce a new route.

### Testing / Validation Notes

- Run the solver-orchestrator regression tests that touch voucher issuance, rerun, demo, and GET flows.
- Run `uv run mypy apps packages`.
- Run `pnpm --filter @opticloud/web typecheck` if the shared API client types change.
- Run `git diff --check` before marking the story complete.

### Risks / Decisions

- The biggest risk is making anonymous a response-only flag; that would leave later rerun/UI work without authoritative durable state.
- The second risk is leaking `anonymous: false` into the existing reproducibility contract and widening the response shape unnecessarily.
- A third risk is accidentally treating anonymous as a new public owner-lookup feature; this story is not that.
- Another risk is conflating internal audit IDs with externally shareable identity data; keep the distinction explicit.

## Story Review Log

### Round 1: Requirements Completeness Review

Findings fixed:
- Made anonymous an explicit opt-in field with request-path validation.
- Added durable state + inheritance requirements so downstream rerun/UI work has canonical data.
- Added an explicit no-PII and no-`anonymous: false/null` contract.
- Clarified that anonymous does not suppress voucher IDs or rerun lineage fields.

Status: PASS after fixes.

### Round 2: Architecture / Testability Review

Findings fixed:
- Bound anonymous to the existing reproducibility flow rather than a separate service.
- Defined the durable voucher row as authoritative, with `_system.reproducibility` kept as the compatibility mirror for response replay.
- Kept demo parity limited to LP preview, not a new issuance mode.

Status: PASS after fixes.

### Round 3: Acceptance / Scope Audit

Findings fixed:
- Tightened shape stability and conditional serialization to keep standard responses byte-compatible.
- Added tests for idempotency replay, rerun inheritance, and omission of `false` / `null`.
- Explicitly tied the anonymous flag into request identity so idempotency cannot replay the wrong voucher across anonymity modes.
- Explicitly excluded unrelated billing, provider, and citation work.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

1. Add schema / ORM plumbing for `options.anonymous` and durable voucher anonymity.
2. Thread the anonymous flag through voucher issuance, rerun lineage, and response shaping.
3. Add backend regressions for validation, persistence, demo parity, rerun inheritance, and shape stability.
4. Update shared API types only if the frontend solver client needs the anonymous field.

### Debug Log References

- 2026-05-21 — Created the 6.B.4 story from Epic 6.B, PRD R6, architecture P23/P30, and the existing 6.B.1/6.B.2/6.B.3 implementation chain.
- 2026-05-21 — Fresh clean worktree needed `uv sync --all-packages --extra dev` before tests because `.venv` was not populated.
- 2026-05-21 — Local DB had the pre-6.B.4 schema; applied `ALTER TABLE reproduction_vouchers ADD COLUMN IF NOT EXISTS anonymous BOOLEAN NOT NULL DEFAULT FALSE` before running DB-backed tests.
- 2026-05-21 — Initial target test run caught `seed: null` being dropped by `model_dump_json(exclude_none=True)`; fixed by preserving nulls and removing only `anonymous` when false.

### Completion Notes List

- Story definition now treats anonymous mode as a durable voucher property, not a response-only decoration.
- Story definition keeps non-anonymous response shapes stable and avoids `anonymous: false` leakage.
- Story definition preserves rerun inheritance and blind-review safety as first-class acceptance criteria.
- Story definition makes anonymous part of request identity so replay and audit remain deterministic.
- Implemented `options.anonymous` for reproducible LP runs, with RFC 7807 validation when used without `options.reproducible: true`.
- Added durable `reproduction_vouchers.anonymous` persistence and mirrored `reproducibility.anonymous: true` into the optimization JSON only for anonymous vouchers.
- Rerun child vouchers inherit anonymous mode from their parent voucher, while existing rerun lineage and 5-year expiry behavior remain unchanged.
- Added API type support for optional `Reproducibility.anonymous`.
- Validation completed on 2026-05-21: target reproduction/billing/demo/rerun tests `36 passed`; solver suite `105 passed`; mypy passed; web typecheck passed; `git diff --check` passed.
- Post-code-review validation completed on 2026-05-21: target reproduction/billing/demo/rerun tests `37 passed`; solver suite `106 passed`; mypy passed; web typecheck passed; `git diff --check` passed.

### File List

Created:
- `_bmad-output/stories/6-b-4-anonymous-voucher.md`

Modified:
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/models.py`
- `apps/solver-orchestrator/src/solver_orchestrator/repro.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`
- `apps/solver-orchestrator/tests/test_billing_integration.py`
- `apps/solver-orchestrator/tests/test_demo_optimizations.py`
- `apps/solver-orchestrator/tests/test_reproduction_rerun.py`
- `apps/solver-orchestrator/tests/test_reproduction_vouchers.py`
- `apps/web/src/lib/api.ts`
- `infra/local-init/02-solver-schema.sql`

### Change Log

- 2026-05-21 — Created Story 6.B.4 context and completed 3 story-review rounds before implementation.
- 2026-05-21 — Implemented anonymous reproducible voucher persistence, response mirroring, validation, and rerun inheritance.
- 2026-05-21 — Added regression coverage for anonymous POST/GET/idempotency replay, demo preview, rerun inheritance, no-PII response checks, and omission of false/null anonymous fields.
- 2026-05-21 — Updated web API types for `reproducibility.anonymous`.
- 2026-05-21 — Code review patched legacy voucher attachment to preserve an existing anonymous mirror and added a regression test.

### Post-Implementation Code Review

Result: PASS after one compatibility patch.

Findings fixed:
- Medium — the legacy `attach_voucher_id_to_optimization()` wrapper defaulted to `anonymous=False`, so a future caller could clear an existing anonymous mirror while only trying to attach a voucher ID. Updated the wrapper to preserve existing `reproducibility.anonymous` and added regression coverage.

Verification after review patch:
- `uv run pytest apps/solver-orchestrator/tests/test_reproduction_vouchers.py apps/solver-orchestrator/tests/test_billing_integration.py apps/solver-orchestrator/tests/test_demo_optimizations.py apps/solver-orchestrator/tests/test_reproduction_rerun.py -q` — 37 passed.
- `uv run pytest apps/solver-orchestrator/tests/ -q` — 106 passed.
- `uv run mypy apps packages` — pass.
- `pnpm --filter @opticloud/web typecheck` — pass.
- `git diff --check` — pass.
