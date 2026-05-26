# Story M3.0: Image Archival Basic Infrastructure Prep

Status: done

## Story

As a DevOps / Repro platform owner,
I want image archival basic infrastructure prepared for ACR EE, warm object storage, cold Glacier-class storage, and KMS backup metadata,
so that Story M3.9 can implement the full 5-year image archival pipeline without ambiguous tier rules, missing restore metadata, or false SLA claims.

## Acceptance Criteria

1. `infra/image-archival/` contains a versioned archive plan.
   - Add a machine-readable archive plan and schema/reference file under `infra/image-archival/`.
   - The plan defines exactly three tiers: hot ACR EE for days 0-90, warm S3 Standard-IA for days 91-365, and cold S3 Glacier Flexible Retrieval or equivalent for days 366-1826.
   - Tier boundaries must be contiguous, non-overlapping, and based on `reproduction_vouchers.created_at` in UTC, not image push time, provider exit time, restore request time, or local time.
   - The plan records required identifiers for downstream lookup: voucher ID, image digest, cosign signature reference, SBOM reference, provider ID, solver, model version, storage tier, object key / registry reference, and KMS key backup reference.
   - The plan documents quarterly restore drill evidence fields and unavailable-restore exception fields.

2. A local validation script can reject malformed archival plans without cloud access.
   - Add `scripts/validate_image_archival_plan.py`.
   - The script validates tier ordering, day boundaries, exact tier names, minimum required metadata fields, KMS backup requirements, restore drill fields, and exception fields.
   - The script must not call Alibaba Cloud, AWS, Vault, Docker, cosign, syft, or any network API.
   - The script exits `0` for the committed plan and non-zero for malformed fixtures.
   - The script prints one concise success line on pass and actionable error lines on failure.

3. Tests cover the prep contract and failure modes.
   - Add pytest coverage for the committed plan.
   - Tests must cover at least: missing required tier, non-contiguous boundary, missing voucher clock source, missing image digest, missing KMS backup reference, and missing restore drill evidence field.
   - Tests should use temporary fixtures and must not require cloud credentials or local Docker.

4. Runbook and docs are aligned with the prep scope.
   - Update `docs/runbooks/repro-image-restore.md` to link to the new `infra/image-archival/` plan.
   - The runbook must still say the full G7 archival pipeline has not shipped yet.
   - The runbook must distinguish M3.0 prep validation from M3.9 cloud pipeline execution.
   - Do not claim real ACR EE retention rules, S3 lifecycle policies, Glacier restore jobs, Vault key backup automation, or ≤5 minute voucher rerun restore are implemented in this story.

5. CI can validate archival prep changes.
   - Update `.github/workflows/ci.yml` path filtering so changes to `infra/image-archival/**`, the validation script, or its tests run a lightweight archival-plan validation job.
   - The job runs the validation script and the targeted pytest file.
   - Existing service test jobs must not be broadened by this prep-only story.

6. Scope boundaries are explicit and downstream work remains deferred.
   - Do not add `apps/repro-service`.
   - Do not add or change database migrations, voucher issuance, rerun routes, billing, provider migration, Docker build/sign scripts, SBOM diff behavior, or user-facing UI.
   - Do not implement Alibaba Cloud ACR EE API calls, AWS S3 / Glacier API calls, Vault writes, Kubernetes CronJobs, GitHub scheduled workflows, or real archive migration workers.
   - Story M3.9 remains the owner for the full hot / warm / cold pipeline, automatic migration, KMS backup automation, quarterly restore drill execution, and voucher rerun cold-restore behavior.

7. Story workflow tracking is updated.
   - This story records three pre-implementation story review rounds and the fixes made after each round.
   - `_bmad-output/stories/sprint-status.yaml` moves `m3-0-image-archival-prep` to `ready-for-dev` only after the three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when the corresponding gates pass.

## Tasks / Subtasks

- [x] Create the archival prep plan. (AC: 1, 6)
  - [x] Add `infra/image-archival/archive-plan.json`.
  - [x] Add `infra/image-archival/archive-plan.schema.json` as the documented contract for downstream implementation.
  - [x] Add `infra/image-archival/README.md` describing the prep-only scope, tier model, voucher clock, metadata contract, and M3.9 handoff.
- [x] Add local validation tooling. (AC: 2, 3)
  - [x] Add `scripts/validate_image_archival_plan.py`.
  - [x] Validate exact three-tier shape and day boundaries.
  - [x] Validate required metadata, KMS backup, restore evidence, and exception fields.
  - [x] Add targeted pytest coverage in `tests/test_image_archival_plan.py`.
- [x] Wire lightweight CI validation. (AC: 5)
  - [x] Add an `image_archival` path-filter output to `.github/workflows/ci.yml`.
  - [x] Add a job that runs the validation script and targeted pytest file.
  - [x] Keep existing service jobs unchanged unless already triggered by root / shared changes.
- [x] Align the restore runbook. (AC: 4, 6)
  - [x] Link `docs/runbooks/repro-image-restore.md` to `infra/image-archival/README.md` and `archive-plan.json`.
  - [x] Add wording that M3.0 validates the prep contract only.
  - [x] Preserve the explicit dependency on the future G7 / M3.9 pipeline.
- [x] Update workflow records and validation evidence. (AC: 1-7)
  - [x] Move sprint status to `in-progress` during implementation and `code-review` after implementation validation.
  - [x] Update Dev Agent Record, File List, Change Log, and post-implementation review notes.
  - [x] Run targeted tests, CI-equivalent validation, and `git diff --check`.
  - [x] Address post-implementation code review findings and re-run validation.

## Dev Notes

### Context

- SC8 added this story as `m3-0-image-archival-prep`, explicitly described as "Image archival basic infrastructure（Sprint 0 准备 ACR EE + Glacier vault prep）".
- Story M3.9 remains the full G7 implementation: M3 docker signing, hot ACR EE 90d, warm S3 Standard-IA 1y, cold Glacier 5y, KMS key backup, and quarterly restore drill execution.
- Architecture G7 warns that normal Glacier retrieval can conflict with the 24h rerun budget; the mitigation is tiered archival: hot ACR EE 90d / warm S3 Standard-IA 1y / cold S3 Glacier 5y.
- Story 6.B.6 already made `reproduction_vouchers.created_at` UTC the only documented 5-year image archival SLA clock and created `docs/runbooks/repro-image-restore.md`.
- Story 6.B.7 explicitly excluded S3 / Glacier restore, image archival indexing, provider auto-migration, and provider exit notification.

### Scope Decision

- Treat M3.0 as prep infrastructure: repository structure, machine-readable contract, validation, runbook alignment, and CI gate.
- Do not create runtime archive jobs, provider image lookup, real cloud resources, or service code.
- Use JSON for the committed plan to avoid adding a YAML parser dependency.
- The validation script should use only Python standard library modules.
- The archive plan is a readiness contract for downstream M3.9 and should be strict enough that drift is caught before any cloud automation is written.

### Architecture / External Constraints

- Existing image supply-chain work lives in `infra/docker/`, `scripts/build_and_sign.sh`, `scripts/sbom_diff.py`, and `.github/workflows/ci.yml`.
- Do not alter `scripts/build_and_sign.sh` or `scripts/sbom_diff.py`; M3.0 depends on image digest / signature / SBOM references but does not change build or signing behavior.
- The future data-plane owner is `prod-data` / `repro-service`, but `apps/repro-service` does not exist yet and must not be scaffolded in this story.
- AWS S3 archived objects are not real-time accessible; Glacier-class restore requires a restore request and temporary restored copy. Expedited restore may be 1-5 minutes only for supported classes and conditions, so M3.0 must not promise ≤5 minute restores.
- S3 Lifecycle supports transition actions to Standard-IA and Glacier-class storage, but M3.0 should only describe desired tier boundaries and validate the local contract.
- ACR EE retention policy details are cloud-provider operational configuration and remain M3.9 work; this story should not hardcode live instance IDs, credentials, regions, or registry API calls.

### Project Structure Notes

- Place archive prep files under `infra/image-archival/`.
- Place the validator under `scripts/` to match existing operator tooling.
- Place tests under root `tests/` because this story is repository-level infrastructure, not a service package.
- Generated archive evidence, restore drill records, or cloud manifests should not be added in this story.

### Testing / Validation Notes

- Targeted validation:
  - `uv run python scripts/validate_image_archival_plan.py infra/image-archival/archive-plan.json`
  - `uv run pytest tests/test_image_archival_plan.py -q`
  - `git diff --check`
- The CI job should run the same validation script and targeted pytest file.
- Because `scripts/` is excluded from mypy and ruff in root `pyproject.toml`, keep the script simple and explicitly tested.

### Risks / Decisions

- The main data consistency risk is using image push time or local time instead of `reproduction_vouchers.created_at` UTC. The validator must check the clock source literally.
- The main function drift risk is accidentally implementing part of M3.9 and then implying the G7 pipeline shipped. Keep all cloud operations out.
- The main boundary risk is accepting a plan that lacks digest, signature, SBOM, or KMS backup references; downstream restore would then be unverifiable.
- The main closure risk is creating docs without a validation gate. CI should run the validator for archival prep changes.

### References

- `_bmad-output/planning/epics.md` — SC8 adds Story M3.0.
- `_bmad-output/planning/epics.md` — Story M3.9 defines the full Image 5y layered archive pipeline.
- `_bmad-output/planning/architecture.md` — G7 critical gap and tiered archival mitigation.
- `_bmad-output/planning/prd.md` — Image 5-year archival, KMS key backup, retention, quarterly restore drill.
- `_bmad-output/stories/6-b-6-voucher-5y-sla-tracking.md` — voucher clock and restore SOP contract.
- `_bmad-output/stories/6-b-7-bitwise-reproducibility-test.md` — explicit out-of-scope items for archive restore/indexing.
- `docs/runbooks/repro-image-restore.md` — existing restore SOP draft.
- `infra/docker/README.md`, `scripts/build_and_sign.sh`, `scripts/sbom_diff.py` — current image supply-chain context.
- `.github/workflows/ci.yml` — existing path-filtered CI pattern.

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Added the literal clock source requirement: all tier age calculations are based on `reproduction_vouchers.created_at` UTC.
- Made tier day ranges contiguous and explicit: 0-90, 91-365, 366-1826.
- Added required restore lookup metadata: voucher ID, image digest, cosign signature reference, SBOM reference, provider ID, solver, model version, storage tier, object key / registry reference, and KMS key backup reference.
- Added restore drill evidence and unavailable-restore exception fields so future M3.9 evidence has a closed data contract.

Status: PASS after fixes.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Narrowed M3.0 to prep-only repository infrastructure and validation; real ACR EE, S3, Glacier, Vault, and restore operations remain deferred.
- Added explicit "do not change" boundaries for `build_and_sign.sh`, `sbom_diff.py`, voucher code, migrations, billing, rerun routes, and UI.
- Added the rule that M3.0 must not claim the G7 pipeline has shipped or promise ≤5 minute cold restore.
- Chose JSON over YAML to avoid adding dependencies and drifting away from existing lightweight scripts.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Added a dedicated validation script and pytest target so the story is not docs-only.
- Added CI path-filter and job requirements so archival prep drift is caught on pull requests.
- Added runbook alignment requirements that preserve the M3.9 dependency and link the new prep plan.
- Added workflow tracking requirements for `ready-for-dev`, `in-progress`, `code-review`, and `done`.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

1. Add the `infra/image-archival/` archive plan, schema/reference file, and README.
2. Add a standard-library validation script and targeted pytest coverage.
3. Add the CI path filter and lightweight validation job.
4. Align the restore runbook without claiming cloud pipeline implementation.
5. Run validation, perform post-implementation code review, patch findings, and move the story through workflow states.

### Debug Log References

- 2026-05-26 — Created Story M3.0 from SC8, M3.9, G7, PRD image archival, Story 6.B.6, Story 6.B.7, and current image supply-chain files.
- 2026-05-26 — Started implementation after three story review rounds passed; sprint status moved to in-progress.
- 2026-05-26 — RED phase: `uv run pytest tests/test_image_archival_plan.py -q` failed because validator and plan files did not exist yet.
- 2026-05-26 — GREEN phase: added archive plan, schema, README, validator, tests, CI job, and runbook alignment; target validation passed.
- 2026-05-26 — Code review found the schema reference was weaker than the validator; tightened schema constraints and added schema/validator parity coverage.
- 2026-05-26 — Final validation after review fixes passed; story moved to done.

### Completion Notes List

- Added `infra/image-archival/` prep contract with exact hot / warm / cold tier boundaries, UTC voucher clock source, restore lookup metadata, KMS backup reference requirements, restore drill evidence fields, and unavailable-restore exception fields.
- Added a standard-library validator that performs local contract validation without cloud, Docker, signing, SBOM, Vault, or network operations.
- Added targeted pytest coverage for the committed plan and six malformed-plan failure modes required by the story.
- Added a lightweight CI job triggered by archival prep paths only; existing service jobs were not broadened.
- Updated the restore SOP to link the prep contract while preserving the statement that the full G7 / M3.9 cloud pipeline has not shipped.
- Post-implementation code review patched schema drift risk: `archive-plan.schema.json` now pins tier order / boundaries and key field enums, with test coverage tying schema field sets to validator constants.
- Validation passed: `uv run python scripts/validate_image_archival_plan.py infra/image-archival/archive-plan.json`; `uv run pytest tests/test_image_archival_plan.py -q` (`8 passed`); `git diff --check`.

### File List

Created:
- `_bmad-output/stories/m3-0-image-archival-prep.md`
- `infra/image-archival/archive-plan.json`
- `infra/image-archival/archive-plan.schema.json`
- `infra/image-archival/README.md`
- `scripts/validate_image_archival_plan.py`
- `tests/test_image_archival_plan.py`

Modified:
- `.github/workflows/ci.yml`
- `_bmad-output/stories/sprint-status.yaml`
- `docs/runbooks/repro-image-restore.md`

### Change Log

- 2026-05-26 — Created Story M3.0 and completed three story review rounds before implementation.
- 2026-05-26 — Started implementation and moved story to in-progress.
- 2026-05-26 — Implemented image archival prep contract, validator, tests, CI validation, and runbook alignment; moved story to code-review.
- 2026-05-26 — Code review tightened schema constraints, added schema parity regression coverage, and prepared story for final done status after validation.
- 2026-05-26 — Final validation passed and story moved to done.

### Post-Implementation Code Review

Status: PASS after fixes.

Findings fixed:
- Medium — `archive-plan.schema.json` was materially weaker than the validator and could allow future schema-only checks to miss required archive / KMS / drill / exception fields or tier boundary drift. Tightened the schema and added regression coverage that pins schema field enums to validator constants.

Dismissed:
- Ordinary `git diff --stat` output omits untracked files before staging. This is a review-context limitation, not a product defect; full file reads covered the untracked files.

Final validation:
- `uv run python scripts/validate_image_archival_plan.py infra/image-archival/archive-plan.json` — pass.
- `uv run pytest tests/test_image_archival_plan.py -q` — `8 passed`.
- `git diff --check` — pass.
