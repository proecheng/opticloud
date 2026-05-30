---
story_key: 5-a-0c-saga-cross-epic-dryrun
epic_num: 5
story_num: A.0c
epic_name: Billing — Credits & Saga
status: done
priority: 🔴 Critical (N5 unlock; gates 5.A.0 distributed Saga implementation)
sizing: S (1 day; static dry-run package + validator + tests + decision/sign-off example)
type: cross-epic dry-run + static contract validation
created_by: bmad-create-story
created_at: 2026-05-30
owner: Cross-Epic Owner Committee
sources:
  - _bmad-output/planning/epics.md (Story 5.A.0c; Cross-Epic Owner Committee; I-S3 decision)
  - _bmad-output/stories/5-a-0a-saga-implementation.md (DB-backed SagaOrchestrator and 7-state stop point)
  - _bmad-output/stories/5-a-0b-saga-contract-fixtures.md (52 deterministic fixtures; public fixture API)
  - docs/adr/0001-saga-pattern.md (Hybrid Saga; transition matrix; test pyramid)
  - _bmad-output/planning/architecture.md (P31/P47 idempotency; P56 outbox; Concern #13 distributed billing transaction)
  - _bmad-output/planning/prd.md (FR B1/B2/B4/B6/B9; POST Idempotency-Key 24h contract)
  - packages/shared-py/opticloud_shared/saga/contract_fixtures.py
  - packages/shared-py/opticloud_shared/saga/state_machine.py
  - apps/solver-orchestrator/tests/test_billing_integration.py
dependencies:
  upstream:
    - 5-a-0a-saga-implementation (done) — Saga runtime exists and imports shared state machine
    - 5-a-0b-saga-contract-fixtures (done) — dry-run must consume fixture manifest/version/hash
    - M2.0/M2.1/M2.2a/M2.2b/M2.2c (done) — Saga/outbox/consistency context
    - Epic 3 solver billing integration tests (done) — reserve/finalize call semantics are already locked
  downstream:
    - 5-a-0-saga-implementation — must use this dry-run decision as the implementation gate
    - 5.A.1-5.A.9 — depend on a non-drifted billing/solver/SRE ownership boundary
---

# Story 5.A.0c — Cross-Epic Saga 集成 Dry-Run

## User Story

**As** Billing Architect + Solver Lead + SRE
**I want** a static, reproducible cross-epic Saga dry-run package after 5.A.0a/b
**so that** Epic 0/3/5.A owners align on Saga design, fixture coverage, and standard-vs-simplified decision before 5.A.0 implementation starts.

## Why This Story

5.A.0a delivered the DB-backed Saga engine and 5.A.0b delivered shared contract fixtures. The remaining N5 unlock risk is not code execution; it is cross-epic alignment drift: Billing can assume ledger/outbox semantics, Solver can assume reserve/finalize semantics, and SRE can assume observability/reconciler semantics without one explicit shared dry-run record.

This story creates an offline dry-run artifact set and validator. It must prove that the committee review package references the real 5.A.0b fixture manifest, maps each fixture category to accountable owners, records the I-S3 standard-first/simplified-fallback decision, and refuses fake completion or real-world sign-off claims.

## Out of Scope

- Changing `packages/shared-py/opticloud_shared/saga/state_machine.py`.
- Changing `apps/billing-service/src/billing_service/saga_orchestrator.py`, billing routes, solver routes, `billing_client.py`, pricing, ledger writes, outbox runtime, reconciler runtime, DB migrations, or UI.
- Starting services, calling HTTP endpoints, using Postgres/Redis/Docker/K8s/network, or executing live billing/solver workflows.
- Claiming a real committee meeting, real production dry-run, CI pass, release approval, or customer/prod evidence.
- Implementing simplified Saga behavior. This story records the decision only: standard path first; simplified fallback v1.5+ if auto-degrade triggers.

## Acceptance Criteria

### AC1: Static dry-run package

- Add `tools/saga_cross_epic_dryrun/dryrun_plan.json`.
- Add `tools/saga_cross_epic_dryrun/owner_signoff.example.json`.
- Add a short operator runbook at `docs/runbooks/saga-cross-epic-dryrun.md`.
- Artifacts must be static JSON/Markdown and repository-local. No live endpoints, secrets, service URLs, tenant IDs, user IDs, raw prompts, raw optimization payloads, or production data.
- Story-scoped implementation files are limited to `tools/saga_cross_epic_dryrun/**`, `scripts/validate_saga_cross_epic_dryrun.py`, `tests/test_saga_cross_epic_dryrun.py`, this story file, and `sprint-status.yaml`.

### AC2: Fixture-manifest anchoring

- `dryrun_plan.json` must reference:
  - `story_key = 5-a-0c-saga-cross-epic-dryrun`
  - upstream stories `5-a-0a-saga-implementation` and `5-a-0b-saga-contract-fixtures`
  - `SAGA_CONTRACT_VERSION = 2026-05-30.saga-fixtures.v1`
  - total fixture count, executable fixture count, category counts, and a deterministic fixture manifest SHA-256 computed from 5.A.0b public API.
- The fixture manifest SHA-256 must be computed from canonical JSON with sorted keys and compact separators. The canonical payload must include only stable public fixture fields needed for dry-run alignment: version, generated_at, category_minimums, fixture IDs/categories/executable flags, expected final states, ledger deltas, outbox counts, idempotency cases, unsupported states, and expected body hashes.
- The validator must fail if the committed plan drifts from the current `CONTRACT_FIXTURE_MANIFEST`.
- `owner_signoff.example.json` must repeat the same fixture version/hash from `dryrun_plan.json`; mismatch must fail validation.

### AC3: Owner responsibility mapping

- `dryrun_plan.json` must map fixture categories to owner roles:
  - Billing Lead: `charge`, `refund`, `rollback`, `idempotency`
  - Solver Lead: solver reserve/finalize success and failure semantics, including no-billing-header, reserve-fail, solve-fail, and finalize-fail behaviors from Epic 3 tests
  - SRE: `timeout`, outbox/reconciler/rollback observability, incident path, and no-live-run evidence boundary
  - Billing Lead + SRE: `budget_pause_stub` remains a non-executable gap record for `paused_by_budget`
  - Provider Interface Lead: consulted/non-blocking for future SC9 provider interface compatibility
- Required blocking sign-off roles are Billing Lead, Solver Lead, and SRE. Provider Interface Lead is consulted but non-blocking for this story.
- Owner role entries must use role names only, not personal names, emails, phone numbers, tenant IDs, account IDs, or calendar metadata.

### AC4: I-S3 decision record

- `dryrun_plan.json` must encode decision `standard_first_simplified_fallback`.
- Standard path means full Saga state machine + idempotency + outbox + compensation semantics continue into 5.A.0.
- Simplified fallback means v1.5+ only, auto-degrade path only, idempotency + outbox only, no compensation transactions, and no full Saga state machine.
- The validator must reject unknown decisions and any plan that treats simplified fallback as the current implementation target.

### AC5: Sign-off example is explicitly non-real

- `owner_signoff.example.json` must set `example_only: true`.
- It must set a placeholder status such as `not_a_real_signoff`; it must not use `approved`, `signed`, `complete`, `passed`, or equivalent real approval language.
- It must not claim real approval, real attendee identities, real meeting time, production dry-run, service execution, or CI pass.
- It must show the required structure for a future real sign-off: required roles, decision reference, fixture version/hash, review duration, open risks, and sign-off outcome placeholders.

### AC6: Validator and negative drift tests

- Add `scripts/validate_saga_cross_epic_dryrun.py`.
- Add `tests/test_saga_cross_epic_dryrun.py`.
- Tests must cover:
  - committed plan/sign-off validate from CLI
  - fixture version/hash/count/category drift rejection
  - plan/sign-off fixture hash mismatch rejection
  - required owner role drift rejection
  - I-S3 decision drift rejection
  - fake completion/sign-off/CI/live-run claim rejection
  - privacy/secrets/PII/raw-payload/raw-host rejection
  - repository path boundary rejection

### AC7: Quality gates

Run before commit:

```powershell
$env:PYTHONPATH='packages/shared-py'
uv run pytest tests/test_saga_cross_epic_dryrun.py -q

$env:PYTHONPATH='packages/shared-py'
uv run python scripts/validate_saga_cross_epic_dryrun.py

uv run ruff check scripts/validate_saga_cross_epic_dryrun.py tests/test_saga_cross_epic_dryrun.py
uv run ruff format --check scripts/validate_saga_cross_epic_dryrun.py tests/test_saga_cross_epic_dryrun.py
```

No DB-backed billing-service tests, solver-orchestrator integration tests, Docker, Redis, Postgres, or network checks are required for this static story. CI workflow changes are explicitly out of scope unless these local gates cannot run.

## Tasks / Subtasks

- [x] T1: Create static dry-run artifacts
  - [x] Add dry-run plan JSON with upstream story, fixture manifest, owner mapping, and I-S3 decision fields.
  - [x] Add non-real owner sign-off example JSON.
  - [x] Add operator runbook explaining offline use and forbidden claims.
- [x] T2: Add validator
  - [x] Validate committed plan and sign-off example.
  - [x] Compute fixture manifest summary/hash from 5.A.0b API.
  - [x] Enforce owner, decision, fixture hash parity, privacy, fake-completion, and path-boundary rules.
- [x] T3: Add tests
  - [x] Add CLI happy-path test.
  - [x] Add drift/privacy/fake-claim/path-boundary negative tests.
  - [x] Keep tests offline with no DB/network/service dependency.
- [x] T4: Run quality gates and update tracking
  - [x] Run AC7 commands.
  - [x] Update story Dev Agent Record, File List, Change Log, and status.

## Developer Notes

### Existing patterns to reuse

- Static validation pattern: `scripts/validate_traffic_replay_plan.py` + `tests/test_traffic_replay_plan.py`.
- 5.A.0b public API: `CONTRACT_FIXTURE_MANIFEST`, `SAGA_CONTRACT_VERSION`, `validate_contract_fixture_manifest()`.
- Use stdlib `json`, `hashlib`, `pathlib`, `re`, `argparse`; do not add dependencies.
- Import shared fixtures using `PYTHONPATH=packages/shared-py`.
- Serialize `Decimal`, `datetime`, and enum values explicitly when hashing the fixture summary. Do not hash Pydantic model internals directly.
- `pyproject.toml` excludes `scripts` from default ruff source discovery, but explicit file-path ruff checks are supported and required by AC7.

### Fixture and owner semantics

- `CONTRACT_FIXTURE_MANIFEST` currently has 52 fixtures: 50 executable and 2 `budget_pause_stub` non-executable fixtures.
- Fixture categories are the contract taxonomy; do not duplicate scenario data manually.
- Solver semantics are locked in `apps/solver-orchestrator/tests/test_billing_integration.py`:
  - no billing header → no reserve/finalize calls
  - reserve OK + solve OK → finalize success
  - reserve failure → 422 and no solve/finalize
  - infeasible solve → finalize failure
  - finalize 5xx → solve result still returns and billing failure is recorded
- SRE ownership is about outbox/reconciler/rollback observability and incident path, not running live infra in this story.

### Boundary rules

- This story must be docs/tools/tests only.
- Do not alter production behavior to make the dry-run pass.
- Any future real sign-off/evidence must be committed under a separate explicit story or operator process. The example in this story remains synthetic.
- CI wiring is optional and not required for this story unless existing CI cannot cover the new test.
- Public SHA-256 values committed in JSON artifacts must be allowlisted in `.pre-commit-config.yaml` under `detect-secrets --exclude-secrets`, following the existing M3.6/M3.7/M3.9 static contract pattern.

### Sprint tracking

- After create-story completes: set `5-a-0c-saga-cross-epic-dryrun: ready-for-dev`.
- During dev-story: move the story to `in-progress`, then `code-review` after implementation gates pass.
- After post-implementation code review fixes and final verification: move the story to `done`.

## Three-Round Pre-Implementation Adversarial Review

### Round 1 — Boundary / Ownership

Findings:
- Risk: a developer could treat the dry-run as permission to touch Saga runtime, billing routes, solver client, DB migrations, UI, or CI wiring.
- Risk: `owner_signoff.example.json` could look like real committee approval if it uses approved/signed/pass language.
- Risk: `budget_pause_stub` fixtures could fall through the owner map because they are non-executable.
- Risk: owner metadata could leak real people/calendar/account details into a static artifact.

Revisions applied:
- AC1 now limits allowed implementation files to static dry-run assets, validator, tests, story tracking, and sprint status.
- AC5 requires a non-real placeholder sign-off status and forbids real approval/pass language.
- AC3 maps `budget_pause_stub` to Billing Lead + SRE as a non-executable `paused_by_budget` gap.
- AC3 requires role-name-only owner entries with no personal or tenant/account metadata.

_Round 2 and Round 3 pending._

### Round 2 — Drift / Data Consistency / Privacy

Findings:
- Risk: dry-run plan fixture counts and hash could be hand-maintained and silently drift from 5.A.0b.
- Risk: sign-off example could reference a different fixture hash than the plan, making later real sign-off evidence unverifiable.
- Risk: hashing whole Pydantic internals could be unstable across dependency versions or include irrelevant field-order details.
- Risk: static artifacts could leak raw host URLs, emails, phone numbers, bearer/API tokens, tenant/user IDs, or prompt/input payload text.

Revisions applied:
- AC2 now requires canonical JSON hashing over a stable public fixture summary derived from `CONTRACT_FIXTURE_MANIFEST`.
- AC2 requires sign-off example fixture version/hash parity with the dry-run plan.
- Developer Notes require explicit serialization for `Decimal`, `datetime`, and enum values instead of hashing Pydantic internals.
- AC6 expands negative tests to cover plan/sign-off hash mismatch and raw-host/privacy leakage.

### Round 3 — Dependency / Test Closure / Workflow

Findings:
- Risk: dev-story could run heavy DB/service tests or start local infra despite this being a static contract story.
- Risk: CI workflow edits could expand scope and create unrelated pipeline churn.
- Risk: ruff invocation could be skipped because `scripts` is excluded from default source discovery in `pyproject.toml`.
- Risk: story/sprint statuses could drift if create-story/dev-story/code-review transitions are not explicit.

Revisions applied:
- AC7 states that only the static pytest, validator CLI, and explicit ruff checks are required; DB/service/network tests are out of scope.
- AC7 keeps CI workflow changes out of scope unless local gates cannot run.
- Developer Notes clarify explicit-path ruff checks for the new script.
- Added sprint tracking rules for ready-for-dev, in-progress, code-review, and done transitions.

## Definition of Ready

- ✅ 5.A.0a implementation is done.
- ✅ 5.A.0b fixture manifest is done and importable offline.
- ✅ Story scope is limited to static dry-run artifacts, validator, tests, and runbook.
- ✅ Three pre-implementation adversarial review rounds completed and incorporated.

## Definition of Done

- All ACs pass.
- All tasks/subtasks are checked.
- Story status is `code-review` after implementation and `done` after review fixes.
- `sprint-status.yaml` is synchronized.
- Post-implementation code review findings are resolved or explicitly documented.
- Branch is pushed and PR is synced to GitHub.

## Dev Agent Record

### Implementation Plan

- Build an offline dry-run package under `tools/saga_cross_epic_dryrun/`.
- Add a stdlib validator that imports the 5.A.0b fixture manifest, computes a stable public summary/hash, and validates plan/sign-off parity.
- Add static tests that exercise the validator directly and through the CLI, including drift/privacy/fake-claim/path-boundary negatives.
- Keep implementation scoped to docs/tools/tests/story tracking; no runtime Saga, billing, solver, DB, service, or CI workflow changes.

### Debug Log

- 2026-05-30: Started dev-story implementation; story moved to in-progress.
- 2026-05-30: Red phase confirmed missing validator, dry-run JSON assets, and runbook.
- 2026-05-30: Implemented static dry-run package, owner sign-off example, runbook, validator, and focused tests.
- 2026-05-30: Fixed Windows absolute-path detection for artifact path validation.
- 2026-05-30: AC7 focused tests, validator CLI, ruff check, and ruff format check passed.
- 2026-05-30: Post-implementation code review found validator coverage gaps; hardened owner review focus, sign-off open risks, runbook sensitive-value checks, and fake completion claim checks.
- 2026-05-30: Final post-review validation passed; story marked done.
- 2026-05-30: CI lint failed on `detect-secrets` false positive for the public fixture manifest SHA-256; added the hash to `.pre-commit-config.yaml` allowlist using existing static-contract pattern.

### Completion Notes

- Added offline 5.A.0c dry-run plan anchored to 5.A.0b fixture manifest version/hash/counts.
- Added non-real owner sign-off example with `not_a_real_signoff` status and no live approval claims.
- Added validator coverage for fixture drift, owner role drift, owner review focus drift, I-S3 decision drift, fake completion claims, privacy leaks, runbook sensitive values, sign-off risk structure, and artifact path boundaries.
- Validation run:
  - `$env:PYTHONPATH='packages/shared-py'; uv run pytest tests/test_saga_cross_epic_dryrun.py -q` → 12 passed
  - `$env:PYTHONPATH='packages/shared-py'; uv run python scripts/validate_saga_cross_epic_dryrun.py` → passed
  - `uv run ruff check scripts/validate_saga_cross_epic_dryrun.py tests/test_saga_cross_epic_dryrun.py` → passed
  - `uv run ruff format --check scripts/validate_saga_cross_epic_dryrun.py tests/test_saga_cross_epic_dryrun.py` → passed

### File List

- `_bmad-output/stories/5-a-0c-saga-cross-epic-dryrun.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.pre-commit-config.yaml`
- `docs/runbooks/saga-cross-epic-dryrun.md`
- `scripts/validate_saga_cross_epic_dryrun.py`
- `tests/test_saga_cross_epic_dryrun.py`
- `tools/saga_cross_epic_dryrun/dryrun_plan.json`
- `tools/saga_cross_epic_dryrun/owner_signoff.example.json`

### Change Log

- 2026-05-30: Initial story draft created.
- 2026-05-30: Pre-implementation adversarial review Round 1 applied.
- 2026-05-30: Pre-implementation adversarial review Round 2 applied.
- 2026-05-30: Pre-implementation adversarial review Round 3 applied; story marked ready-for-dev.
- 2026-05-30: Implementation started.
- 2026-05-30: Implementation completed and moved to code-review.
- 2026-05-30: Post-review hardening completed and story marked done.

## Senior Developer Review (AI)

Outcome: Approved after fixes.

Findings:
- [x] Medium — Owner role validation checked role presence and blocking status but did not lock each role's required review focus. A drifted SRE entry could omit outbox/reconciler incident review while still passing AC3. Fixed by adding `REQUIRED_OWNER_FOCUS` validation and `test_required_owner_role_drift_is_rejected` coverage.
- [x] Medium — Runbook content was only checked for existence, so a later edit could introduce personal data, bearer tokens, raw hosts, or prompt/input details while validator still passed AC1/AC6. Fixed by adding `validate_runbook_text()` and `test_runbook_sensitive_values_are_rejected`.
- [x] Low — Sign-off `open_risks` accepted any shape and could contain real approval/CI pass language. Fixed by requiring a non-empty list of strings and adding fake-completion claim validation with `test_signoff_open_risks_structure_is_required`.

Review layers:
- Blind Hunter: identified static artifact guard gaps around untracked new files and fake completion claims.
- Edge Case Hunter: identified owner review focus drift and runbook sensitive-value drift.
- Acceptance Auditor: verified AC1-AC7 after fixes and confirmed no runtime Saga/billing/solver code was changed.

Final verification:
- `$env:PYTHONPATH='packages/shared-py'; uv run pytest tests/test_saga_cross_epic_dryrun.py -q` → 12 passed
- `$env:PYTHONPATH='packages/shared-py'; uv run python scripts/validate_saga_cross_epic_dryrun.py` → passed
- `uv run ruff check scripts/validate_saga_cross_epic_dryrun.py tests/test_saga_cross_epic_dryrun.py` → passed
- `uv run ruff format --check scripts/validate_saga_cross_epic_dryrun.py tests/test_saga_cross_epic_dryrun.py` → passed
