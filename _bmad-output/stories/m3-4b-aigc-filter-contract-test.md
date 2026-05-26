# Story M3.4b: AIGC Filter Contract Test 框架

Status: done

## Story

As an Architect,
I want the shared `aigc_filter` module API contract, major-version deprecation policy, and PR contract tests locked in one place,
so that future Chat, Critic, and NL-summary callers detect M3.4 signature or result-shape drift before integration work breaks.

## Acceptance Criteria

1. AIGC filter module contract is explicit and versioned.
   - Add stable contract metadata to `aigc_filter`, including contract version, deprecation notice window, and public export list.
   - The contract version must expose a major version that callers can compare.
   - The deprecation notice window must be at least 6 months / 183 days.
   - Add a compatibility alias or documented result type so the epic wording `filter(...) -> Filtered` maps to the implemented M3.4 result object without ambiguity.

2. `filter` callable signature is locked.
   - Contract tests assert `aigc_filter.filter` has parameters `text`, `tier`, and `context` in the current order.
   - `text` is required.
   - `tier` defaults to `strict` and accepts `strict` or `loose`.
   - `context` remains optional.
   - Invalid tier behavior remains fail-fast.

3. Result shape is locked for future callers.
   - Contract tests assert the result object exposes at least: `text`, `blocked`, `reason_codes`, `tier`, `trace_id`, `aria_label`, `watermark`, and `metadata`.
   - Contract tests assert watermark metadata exposes `trace_id`, `module_version`, and `provider`.
   - Contract tests assert blocked results do not return the unsafe source text.
   - Contract tests assert top-level `import aigc_filter` and `from opticloud_shared import aigc_filter` resolve to the same module.

4. Contract snapshot prevents silent drift.
   - Add a committed contract snapshot file under `tests/contract/`.
   - Add tests that compare the runtime module contract to the committed snapshot.
   - The snapshot must include function signature, result fields, watermark fields, public exports, contract version, and deprecation notice days.
   - If the module signature, required fields, public exports, or major version changes, CI must fail until the snapshot and story/consumer ACs are consciously updated.

5. Deprecation policy is testable.
   - Add tests proving the deprecation notice window is >=183 days.
   - Add tests proving major-version changes are detected by comparing runtime contract metadata against the snapshot.
   - Do not implement a release-notification service, email workflow, changelog bot, package publishing, or real consumer migration in this story.

6. Contract tests run in CI.
   - Extend the existing `contract-test` job or add an equivalent lightweight PR gate.
   - CI must run without network, external LLM credentials, database, Docker daemon, or AIGC filing secrets.
   - Path filters must trigger the contract gate when `aigc_filter`, its snapshot, contract tests, or contract helper scripts change.

7. Scope boundaries are explicit.
   - Do not change the M3.4 filtering semantics except for additive contract metadata or compatibility aliases.
   - Do not wire Chat/Critic service callers.
   - Do not add real Layer 2 LLM moderation calls.
   - Do not replace the existing API OpenAPI contract tests; module contract tests must coexist with `tests/contract`.

8. Story workflow tracking is updated.
   - This story records three pre-implementation story review rounds and fixes after each round.
   - `_bmad-output/stories/sprint-status.yaml` moves `m3-4b-aigc-filter-contract-test` to `ready-for-dev` only after the three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.

## Tasks / Subtasks

- [x] Add AIGC contract metadata. (AC: 1, 5, 7)
  - [x] Add module-level contract version and deprecation notice constants.
  - [x] Add a `Filtered` compatibility alias to the implemented result type.
  - [x] Add a helper that returns runtime contract metadata for tests and future callers.
  - [x] Preserve existing M3.4 filter/watermark behavior.
- [x] Add committed contract snapshot. (AC: 2, 3, 4, 5)
  - [x] Add `tests/contract/aigc_filter_contract.json`.
  - [x] Include expected signature, required result fields, watermark fields, public exports, version metadata, and deprecation days.
  - [x] Keep the snapshot deterministic and manually reviewable.
- [x] Add AIGC module contract tests. (AC: 1-5, 7)
  - [x] Add `tests/contract/test_aigc_filter_module_contract.py`.
  - [x] Assert imports, signature, default values, invalid tier behavior, result fields, watermark fields, and blocked-text replacement.
  - [x] Assert runtime metadata matches the committed snapshot.
  - [x] Assert major-version drift and deprecation-window violations fail in unit-level checks.
- [x] Wire CI contract gate. (AC: 6, 7)
  - [x] Update `.github/workflows/ci.yml` path filters so contract tests run on `packages/shared-py/aigc_filter/**` and the snapshot/tests.
  - [x] Ensure the existing `contract-test` job has enough `PYTHONPATH` to import `aigc_filter`.
  - [x] Keep `aigc-filter-validation` and API OpenAPI contract tests separate.
- [x] Update workflow records and validation evidence. (AC: 1-8)
  - [x] Move sprint status to `in-progress`, then `code-review`, then `done`.
  - [x] Update Dev Agent Record, File List, Change Log, and post-implementation review notes.
  - [x] Run focused contract tests, AIGC tests, shared-py tests, ruff, mypy, pre-commit, and `git diff --check`.

## Dev Notes

### Context

- M3.4 shipped `aigc_filter` as the physical single implementation location for AIGC filter/watermark behavior.
- M3.4b is A-S2: it prevents future Chat/Critic/NL callers from discovering signature or result-shape drift only during integration.
- M3.2 created repo-level `tests/contract` for OpenAPI/Schemathesis service contracts and explicitly excluded M3.4b. This story adds module-contract tests beside those tests; it does not replace API contract tests.
- Existing `aigc_filter.filter(text, tier="strict", context=None)` returns `FilterResult`; the epic text says `-> Filtered`, so this story should add an additive alias rather than rename the existing class.

### Scope Decision

- Use Python introspection and a committed JSON snapshot for the module contract. Schemathesis remains the service/OpenAPI contract tool; a pure Python module does not have an OpenAPI surface.
- The contract snapshot is the PR gate for conscious drift review. Future consumer stories can update the snapshot and consumer ACs together when a contract change is intentional.
- Deprecation notification is represented as machine-checkable metadata and policy tests in this story. Real release notification automation is out of scope.

### Architecture / External Constraints

- Keep tests offline and deterministic.
- Avoid new dependencies; use stdlib introspection, JSON, and pytest.
- Contract metadata must not include secrets, sample prompts, or AIGC filing information.
- Do not reduce M3.4 gates: `tests/aigc` must continue to pass.

### Project Structure Notes

- Extend `packages/shared-py/aigc_filter/__init__.py` only additively.
- Place snapshot and tests under `tests/contract/`.
- Update `tests/contract/README.md` to mention module contracts versus service OpenAPI contracts.
- Update `.github/workflows/ci.yml` path filters for contract tests.

### Testing / Validation Notes

- Expected local commands:
  - `$env:PYTHONPATH='apps/auth-service/src;packages/shared-py'; uv run pytest tests/contract -q`
  - `uv run pytest tests/aigc -q`
  - `uv run pytest packages/shared-py/tests/ -q`
  - `uv run ruff check packages/shared-py/aigc_filter tests/contract tests/aigc`
  - `uv run mypy packages/shared-py`
  - `uv run pre-commit run --all-files --show-diff-on-failure`
  - `git diff --check`

### Risks / Decisions

- Data consistency risk: runtime metadata and snapshot can diverge silently if tests only inspect one side. Contract tests must compare both.
- Function consistency risk: adding `Filtered` could accidentally create a second result type. Use an alias to `FilterResult`.
- Drift risk: broad public export snapshots can be too brittle. Snapshot only the module-owned public contract listed in `__all__`.
- Boundary risk: trying to force Schemathesis onto a non-HTTP module would create fake infrastructure. Keep module contract tests introspection-based and document why.
- Closure risk: CI path filters may not run contract tests on `aigc_filter` changes. Update filters explicitly.

### References

- `_bmad-output/planning/epics.md:1120` — Story M3.4b AIGC Filter Contract Test framework.
- `_bmad-output/planning/epics.md:1935` — A-S2 adds Story M3.4b.
- `_bmad-output/planning/architecture.md:963` — unified `packages/shared-py/aigc_filter/` package.
- `_bmad-output/stories/m3-4-aigc-watermark-module.md` — implemented M3.4 module and review findings.
- `_bmad-output/stories/m3-2-contract-test-framework.md` — existing repo contract-test harness and boundaries.
- `tests/contract/README.md` — current contract-test commands and scope.

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Added exact M3.4b target story key and scoped it to `tests/contract` rather than creating a separate competing contract hierarchy.
- Added the required snapshot fields so the contract file is not a vague checklist.
- Added explicit mapping from epic `Filtered` wording to current `FilterResult` implementation through an alias.
- Added PYTHONPATH and CI trigger requirements so contract tests can import both auth-service and shared-py.

Status: PASS after fixes.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Clarified that module contracts use Python introspection and JSON snapshot, while Schemathesis remains for service/OpenAPI surfaces.
- Added fail-fast invalid tier, blocked text replacement, and import identity assertions to catch real caller breakage.
- Added major-version and deprecation-window assertions as executable policy checks.
- Required additive-only changes to avoid changing M3.4 runtime semantics.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Explicitly excluded Chat/Critic caller wiring, real Layer 2 moderation, notification services, publishing, and consumer migration.
- Added `tests/contract/README.md` update so future maintainers know service contracts and module contracts coexist.
- Added path-filter requirement for `aigc_filter` changes to trigger the contract gate.
- Added full validation commands and workflow status gates.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

1. Add additive contract metadata and `Filtered` alias to `aigc_filter`.
2. Add committed JSON contract snapshot and module-contract tests.
3. Update contract README and CI path filters.
4. Run validation, perform post-implementation code review, patch findings, and move the story through workflow states.

### Debug Log References

- 2026-05-26 — Created Story M3.4b after M3.4 was merged to `main` and open PR list was empty.
- 2026-05-26 — Completed three pre-implementation story review rounds before implementation; sprint status moved to ready-for-dev.
- 2026-05-26 — Started implementation; sprint status moved to in-progress.
- 2026-05-26 — Added AIGC filter contract constants, 183-day deprecation policy metadata, `Filtered` alias, and runtime `contract_metadata()`.
- 2026-05-26 — Added committed JSON contract snapshot and module contract tests for imports, signature, result fields, watermark fields, exports, major-version drift, deprecation policy, invalid tier, and blocked-text replacement.
- 2026-05-26 — Updated contract README and CI path filter so `aigc_filter` changes trigger the existing contract-test job.
- 2026-05-26 — Validation passed: `$env:PYTHONPATH='apps/auth-service/src;packages/shared-py'; uv run pytest tests/contract/test_aigc_filter_module_contract.py -q` (9 passed).
- 2026-05-26 — Validation passed: `$env:PYTHONPATH='apps/auth-service/src;packages/shared-py'; uv run pytest tests/contract -q` (13 passed).
- 2026-05-26 — Validation passed: `uv run pytest tests/aigc -q` (13 passed).
- 2026-05-26 — Validation passed: `uv run pytest packages/shared-py/tests/ -q` (32 passed).
- 2026-05-26 — Validation passed: `uv run ruff check packages/shared-py/aigc_filter tests/contract tests/aigc`.
- 2026-05-26 — Validation passed: `uv run mypy packages/shared-py`.
- 2026-05-26 — Post-implementation code review found and fixed one test-quality issue: negative version/deprecation tests now reuse the same policy assertion helper as the positive path.
- 2026-05-26 — Validation passed after review patch: `$env:PYTHONPATH='apps/auth-service/src;packages/shared-py'; uv run pytest tests/contract/test_aigc_filter_module_contract.py -q` (9 passed).
- 2026-05-26 — Validation passed: `uv run pre-commit run check-yaml --files .github/workflows/ci.yml`.
- 2026-05-26 — Validation passed: `git diff --check`.
- 2026-05-26 — Validation passed: `uv run pre-commit run --all-files --show-diff-on-failure`.

### Completion Notes List

- Added `AIGC_CONTRACT_NAME`, `AIGC_CONTRACT_VERSION`, and `AIGC_DEPRECATION_NOTICE_DAYS=183` as machine-checkable contract metadata.
- Added `Filtered = FilterResult` to align M3.4b epic wording with the M3.4 implementation without creating a second result type.
- Added `contract_metadata()` so tests and future callers can compare runtime contract shape against `tests/contract/aigc_filter_contract.json`.
- Added module contract tests under `tests/contract` while preserving the existing Schemathesis service-contract tests.
- Updated CI path filters so `packages/shared-py/aigc_filter/**` triggers both AIGC validation and the broader contract-test job.

### Post-Implementation Code Review (AI)

Outcome: PASS after fixes.

Findings fixed:
- The first negative tests for major-version drift and short deprecation windows only compared hand-built dictionaries, so they did not prove the actual contract policy assertion would fail. Fixed by extracting `_assert_version_policy(...)` and using it in both the positive runtime test and negative drift-window tests.

Residual risk:
- This is a module-level introspection contract, not a consumer integration test. Chat/Critic caller stories still need their own import/use-path tests once those services exist.

### File List

- `_bmad-output/stories/m3-4b-aigc-filter-contract-test.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `packages/shared-py/aigc_filter/__init__.py`
- `tests/contract/README.md`
- `tests/contract/aigc_filter_contract.json`
- `tests/contract/test_aigc_filter_module_contract.py`

### Change Log

- 2026-05-26 — Created Story M3.4b and completed three story review rounds before implementation.
- 2026-05-26 — Started implementation and moved story to in-progress.
- 2026-05-26 — Added AIGC module contract metadata, snapshot, contract tests, README notes, and CI path-filter wiring.
- 2026-05-26 — Completed post-implementation code review and patched negative contract-policy tests to use the same assertion helper as the positive path.
- 2026-05-26 — Marked story done after contract tests, AIGC tests, shared-py tests, ruff, mypy, YAML check, pre-commit, and diff-check passed.
