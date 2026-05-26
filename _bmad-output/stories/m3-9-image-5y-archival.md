# Story M3.9: Image 5y Layered Archival Pipeline

Status: done

owner: DevOps / SRE + Repro Platform

## Story

As an NFR-C / Repro owner,
I want a verifiable Image 5y layered archival pipeline contract for signed provider images, hot ACR EE retention, warm S3 Standard-IA copies, cold Glacier-class archive, KMS key backup, and quarterly restore drill evidence,
so that NFR-C11 Image 5y archival, Innovation #2 Repro 5y SLA trust, and the G7 critical gap have an auditable implementation path without false cloud-operation or cold-restore claims.

## Acceptance Criteria

1. The M3.9 pipeline plan extends the M3.0 archive contract without changing its canonical tier semantics.
   - Add `infra/image-archival/pipeline-plan.json`.
   - Add `infra/image-archival/pipeline-plan.schema.json` as a schema-style reference for the M3.9 pipeline plan.
   - The plan must bind to `infra/image-archival/archive-plan.json` by canonical SHA-256.
   - The plan must keep the exact clock source `reproduction_vouchers.created_at` in UTC.
   - The plan must keep the exact tier names and voucher-age boundaries from M3.0: `hot_acr_ee` days 0-90, `warm_s3_standard_ia` days 91-365, `cold_s3_glacier` days 366-1826.
   - The plan must include deterministic stage IDs in order: `provider_image_push`, `cosign_sign_and_index`, `hot_acr_ee_retention`, `warm_s3_standard_ia_transition`, `cold_s3_glacier_transition`, `vault_kms_backup`, and `quarterly_restore_drill`.
   - The plan must distinguish voucher-age transition due dates from object-age-only bucket lifecycle rules. Bucket lifecycle can be an implementation mechanism only if evidence also records the voucher clock, transition due time, and observed transition time.
   - The plan must keep M3.0 required archive fields: voucher ID, voucher-created UTC, provider ID, solver, model version, image digest, cosign signature reference, SBOM reference, storage tier, registry/object reference, and KMS backup reference.

2. Signed image and archive index contracts are machine-checkable.
   - The plan must require image digest, cosign signature reference, SBOM reference, source commit SHA, build timestamp UTC, provider ID, solver, model version, and repository reference for each archived provider image.
   - The plan must define an archive index row shape keyed by voucher ID plus image digest.
   - The archive index row must include `transition_due_utc`, `transition_observed_utc`, `storage_tier`, `registry_or_object_ref`, `artifact_checksum`, `cosign_verified`, `sbom_verified`, and `kms_key_backup_ref`.
   - The plan must reject mutable tag-only lookup as sufficient evidence; tags can appear only as diagnostic metadata alongside digest-pinned references.
   - No provider image, SBOM, signature, or archive index row may contain API keys, bearer tokens, cookies, customer prompts, user PII, or credentialed URLs.

3. Hot / warm / cold archive transition requirements are explicit and do not overclaim live cloud provisioning.
   - Hot tier evidence must prove the image is available in ACR EE or an equivalent registry reference for voucher ages 0-90.
   - Warm tier evidence must prove a copy has moved to S3 Standard-IA or equivalent warm object storage at voucher age day 91.
   - Cold tier evidence must prove a copy has moved to S3 Glacier Flexible Retrieval or equivalent cold archive at voucher age day 366.
   - Evidence must record provider, region, bucket/registry alias, storage class, object key or registry reference, artifact checksum, and transition timestamp.
   - CI must not call Alibaba Cloud, AWS, Vault, Docker, cosign, syft, a registry, or any network API.
   - Real operator evidence, when produced later, must be supplied as manifests under `reports/image-archival/<run_id>/` and validated structurally in CI.
   - The story must not commit real cloud credentials, live bucket names if sensitive, registry secrets, Vault tokens, customer data, or raw provider artifacts.

4. KMS backup requirements are closed and verifiable.
   - The plan must include a KMS backup stage using Vault Transit backup/restore semantics or an equivalent HSM-backed process.
   - The contract must require `kms_key_id`, `kms_key_backup_ref`, `backup_created_at_utc`, `backup_checksum`, `restore_tested_at_utc`, and `restore_test_result`.
   - The validator must reject a pipeline/evidence file where archive records reference a KMS backup without corresponding backup metadata.
   - The plan/runbook must state that backup payloads and Vault tokens are not committed; only opaque references, timestamps, and checksums are allowed.
   - The plan must not require Vault to run in CI.

5. Quarterly restore drill evidence is defined and validates all three tiers.
   - Add `tools/image_archival/evidence_manifest.schema.json`.
   - Add `tools/image_archival/evidence_manifest.example.json`.
   - Example evidence must be clearly marked `example_only=true` and must not claim a real production drill.
   - Evidence must include `run_id`, `commit_sha`, `archive_plan_sha256`, `pipeline_plan_sha256`, `environment`, `started_utc`, `ended_utc`, `tier_results`, `kms_backup_results`, `artifacts`, `redaction_reviewed`, and `operator`.
   - A real evidence manifest must set `example_only=false`, be under `reports/image-archival/<run_id>/evidence_manifest.json`, and include at least one successful or explicitly failed drill row per storage tier.
   - Each tier result must include voucher ID, voucher-created UTC, storage tier, image digest, registry/object reference, cosign verification, SBOM verification, KMS backup verification, restore status, restore requested UTC, restore completed UTC when available, and outcome.
   - Evidence artifact paths must be repository-relative, stay under the matching run directory, reject `..`, reject absolute paths, and reject URLs.

6. Restore SLA language is corrected to avoid the M3.9 / PRD conflict.
   - The plan and runbook must not promise that every cold Glacier-class restore completes within 5 minutes.
   - Cold restore evidence must use a conservative `restore_target_minutes` of 1440 unless a later operator evidence story explicitly documents provisioned expedited capacity and approves a tighter target.
   - Hot-tier lookup may target 5 minutes; warm/cold archive recovery must be described as restore workflow evidence, not instant rerun availability.
   - The runbook must explain the source conflict: epics requested cold rerun image restore `<=5 min`, while PRD Core Innovation #2 says image archive retrieval `<=24h` and M3.0 warned Glacier-class restores are not real-time.
   - Story M3.9 may validate a restored image evidence path, but it must not change `POST /v1/reproduce/{voucher_id}/rerun` behavior or claim user-facing automatic rerun from cold storage is complete unless live evidence exists.

7. A standalone validator closes data consistency, function drift, boundary, and evidence gaps.
   - Add `scripts/validate_image_archival_pipeline.py`.
   - The validator must use only the Python standard library.
   - By default, the validator must validate the M3.9 pipeline plan, schema-style reference, example evidence manifest, M3.0 archive-plan binding, exact tier boundaries, stage order, metadata fields, KMS requirements, restore target policy, redaction, and no-live-cloud boundary.
   - The validator must support optional `--evidence reports/image-archival/<run_id>/evidence_manifest.json` for real operator evidence.
   - The validator must reject wrong archive-plan hash, changed tier boundaries, missing stage IDs, object-age-only lifecycle without voucher-clock due dates, mutable tag-only lookup, missing cosign/SBOM/KMS fields, fake `example_only=false` example evidence, false `cold_restore_5m_pass` style claims, secret-like keys/values, raw URLs in artifact paths, and evidence outside `reports/image-archival/`.
   - The validator must print one concise success line on pass and actionable error lines on failure.

8. Tests cover the pipeline contract and malformed evidence.
   - Add `tests/test_image_archival_pipeline.py`.
   - Tests must cover committed plan validation, archive-plan hash binding, exact tier/stage order, schema/validator field parity, example evidence validation, evidence path mode, and runbook/CI wiring.
   - Negative tests must cover at least: archive-plan hash mismatch, tier boundary drift, missing stage, object-age-only transition, missing image digest, missing cosign reference, missing SBOM reference, missing KMS backup reference, cold restore five-minute overclaim, mutable tag-only evidence, artifact path traversal, credentialed URL, bearer token, and real evidence missing a tier.
   - Tests must create any temporary real-evidence fixture under `reports/image-archival/<run_id>/` and delete it before finishing.
   - Tests must not require cloud credentials, Docker, cosign, syft, Vault, network access, database, Redis, or `apps/repro-service`.

9. Runbook and CI make M3.9 operational without fabricating cloud proof.
   - Add `docs/runbooks/image-5y-archival-pipeline.md`.
   - Update `docs/runbooks/repro-image-restore.md` so it points from the existing SOP to the M3.9 pipeline contract and keeps its voucher-clock language.
   - The runbook must document operator commands, evidence directory layout, redaction rules, cloud prerequisites, restore drill procedure, failure handling, and the corrected 24h cold-restore target.
   - The runbook must state that CI validates structure only and does not prove ACR EE, S3, Glacier, Vault, Docker signing, cosign verification, or real restore execution.
   - Extend `.github/workflows/ci.yml` so `infra/image-archival/**`, `tools/image_archival/**`, `scripts/validate_image_archival_pipeline.py`, `tests/test_image_archival_pipeline.py`, `docs/runbooks/image-5y-archival-pipeline.md`, `docs/runbooks/repro-image-restore.md`, or `reports/image-archival/**` run a focused validation job.
   - CI must run the validator, validate any real evidence manifests when present, and run `pytest tests/test_image_archival_pipeline.py`.

10. Workflow tracking and boundaries are explicit.
   - This story records three pre-implementation story review rounds and the fixes made after each round.
   - `_bmad-output/stories/sprint-status.yaml` moves `m3-9-image-5y-archival` to `ready-for-dev` only after all three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.
   - Do not scaffold `apps/repro-service`.
   - Do not add database migrations or modify voucher issuance, rerun endpoint behavior, billing, provider migration, solver execution, UI, or public APIs.
   - Do not commit generated real reports unless they are redacted operator evidence under `reports/image-archival/<run_id>/` and pass the validator.
   - Final completion must update the Dev Agent Record, file list, validation evidence, post-implementation code review findings/fixes, and sprint status.

## Tasks / Subtasks

- [x] Build the M3.9 pipeline contract. (AC: 1, 2, 3, 4, 6)
  - [x] Add `infra/image-archival/pipeline-plan.json`.
  - [x] Add `infra/image-archival/pipeline-plan.schema.json`.
  - [x] Bind M3.9 to the canonical M3.0 archive plan hash.
  - [x] Define stage order, voucher-clock transitions, image signing/index fields, KMS backup fields, restore target policy, and non-goals.
- [x] Add evidence manifest assets. (AC: 5, 6)
  - [x] Add `tools/image_archival/evidence_manifest.schema.json`.
  - [x] Add `tools/image_archival/evidence_manifest.example.json`.
  - [x] Include example-only tier drill rows for hot, warm, and cold.
  - [x] Keep example evidence synthetic, redacted, and hash-bound to the committed plans.
- [x] Add validator and regression tests. (AC: 7, 8)
  - [x] Add `scripts/validate_image_archival_pipeline.py`.
  - [x] Validate plan, schema, example evidence, and optional real evidence manifests.
  - [x] Add `tests/test_image_archival_pipeline.py` with positive and negative coverage.
- [x] Wire runbooks and CI. (AC: 9)
  - [x] Add `docs/runbooks/image-5y-archival-pipeline.md`.
  - [x] Update `docs/runbooks/repro-image-restore.md` to link the M3.9 pipeline contract and corrected restore target.
  - [x] Update `.github/workflows/ci.yml` path filters and validation job.
- [ ] Update workflow records and validation evidence. (AC: 10)
  - [x] Move sprint status to `in-progress` during implementation and `code-review` after implementation validation.
  - [x] Update Dev Agent Record, File List, Change Log, and post-implementation review notes.
  - [x] Run targeted validation, lint/format where relevant, pre-commit, and `git diff --check`.
  - [x] Address post-implementation code review findings and re-run validation.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:337` maps G7 Image 5y layered archival to Story M3.9 in Epic 0, M3 start, not M5.
- `_bmad-output/planning/epics.md:1223` through `1235` define M3.9: signed Docker images, hot ACR EE 90d, warm S3 Standard-IA 1y, cold Glacier 5y, KMS backup, and quarterly restore drill evidence.
- `_bmad-output/planning/epics.md:1763` links voucher rerun to M3.9 image archive, but live rerun endpoint changes remain out of scope for this contract story.
- `_bmad-output/planning/prd.md:542` states Image archive retrieval is `<=24h`; `_bmad-output/planning/epics.md:1234` says cold rerun image restore `<=5 min`. M3.9 resolves this by using a conservative 24h cold-restore target unless future operator evidence proves provisioned expedited capacity.
- `_bmad-output/planning/prd.md:1735` requires S3 Glacier, encrypted KMS key backup, 5-year retention, and quarterly restore drills.
- `_bmad-output/planning/architecture.md:151` identifies Image Supply Chain as Docker build, signing, push, and Repro 5y S3 Glacier archive.
- `_bmad-output/planning/architecture.md:543` chooses Alibaba Cloud ACR EE for registry/signing/SBOM/scanning.
- `_bmad-output/planning/architecture.md:2497` lists OSS / S3 / S3 Glacier for image archive storage.
- Story M3.0 added `infra/image-archival/archive-plan.json`, `archive-plan.schema.json`, `scripts/validate_image_archival_plan.py`, `tests/test_image_archival_plan.py`, and CI validation as the prep contract.
- Story 6.B.6 made `reproduction_vouchers.created_at` UTC the only 5-year SLA clock and created `docs/runbooks/repro-image-restore.md`.
- Story 6.B.7 explicitly excluded S3 / Glacier restore, image archival indexing, provider auto-migration, and provider exit notification from bitwise audit tooling.

### Latest Technical Specifics

- AWS S3 Lifecycle supports transitions from S3 Standard to Standard-IA and Glacier-class storage, and encrypted objects remain encrypted during transitions. It also applies object-age constraints such as the 128 KB small-object default and minimum storage duration considerations, so M3.9 must not equate bucket object age with voucher age without explicit evidence. Source: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-transition-general-considerations.html>.
- AWS S3 Glacier Flexible Retrieval / Deep Archive objects are not accessible in real time; a restore request creates a temporary copy for a specified duration before normal access. Source: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/restoring-objects.html>.
- Alibaba Cloud ACR EE tag retention policies keep matching tags and delete others; deleted tag data may still require garbage collection / OSS storage cleanup. Therefore M3.9 must use digest-pinned evidence and cannot rely on mutable tags as restore proof. Sources: <https://www.alibabacloud.com/help/en/acr/user-guide/delete-image-tags> and <https://www.alibabacloud.com/help/en/acr/user-guide/release-the-storage-space-of-oss>.
- ACR EE stores artifacts in OSS-backed storage and the storage-management docs warn against direct bucket configuration changes beyond documented settings, so M3.9 should model object storage transitions as separate archive copies / evidence, not direct mutation of the ACR backing bucket. Source: <https://www.alibabacloud.com/help/doc-detail/2921924.html>.
- Vault Transit exposes key backup and restore endpoints; M3.9 should validate backup references and restore-test metadata, not commit backup payloads or tokens. Source: <https://developer.hashicorp.com/vault/api-docs/secret/transit>.

### Previous Story Intelligence

- M3.0 established the strict prep contract and validation pattern. M3.9 should extend that contract instead of changing the tier names or required metadata.
- M3.6e, M3.7, and M3.8 established the current M3 pattern: static plan/assets, example-only evidence, optional real-evidence validation under `reports/**`, runbook, path-filtered CI, then post-implementation review.
- M3.8 CI follow-up showed high-entropy hashes can trip secret scanning. Keep only plan/file SHA fields that are necessary and avoid per-artifact random digests in committed examples where a structured summary or short checksum is sufficient.
- 6.B.6 and M3.0 both warn not to claim the full G7 pipeline has shipped before evidence exists. M3.9 must clearly say what is structurally validated versus what requires real operator evidence.

### Architecture / External Constraints

- Keep repository-level archival assets under `infra/image-archival/`.
- Keep synthetic evidence contracts under `tools/image_archival/`.
- Keep generated real evidence under `reports/image-archival/<run_id>/` and validate it only when present.
- Use standard-library Python for validators; do not add dependencies.
- Do not call cloud APIs, Docker, cosign, syft, Vault, registries, or networks in tests/CI.
- Do not scaffold `apps/repro-service` even though architecture lists it as future M5 owner.
- Do not modify voucher/rerun runtime code in this story.
- Treat ACR EE, S3/Glacier, Vault, and cosign as operator systems whose evidence must be redacted and structurally validated.

### File Structure Requirements

- `infra/image-archival/pipeline-plan.json`
- `infra/image-archival/pipeline-plan.schema.json`
- `tools/image_archival/evidence_manifest.schema.json`
- `tools/image_archival/evidence_manifest.example.json`
- `scripts/validate_image_archival_pipeline.py`
- `tests/test_image_archival_pipeline.py`
- `docs/runbooks/image-5y-archival-pipeline.md`
- Update `.github/workflows/ci.yml`.
- Update `docs/runbooks/repro-image-restore.md`.

### Testing / Validation Notes

Expected local commands after implementation:

```bash
uv run python scripts/validate_image_archival_plan.py infra/image-archival/archive-plan.json
uv run python scripts/validate_image_archival_pipeline.py
uv run pytest tests/test_image_archival_plan.py tests/test_image_archival_pipeline.py -q
uv run ruff check scripts/validate_image_archival_pipeline.py tests/test_image_archival_pipeline.py
uv run ruff format --check scripts/validate_image_archival_pipeline.py tests/test_image_archival_pipeline.py
uv run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

If `uv run pytest -q` is attempted and fails on existing monorepo collection/import issues, record that separately from the M3.9 scoped gates.

### Risks / Decisions

- Data consistency risk: S3 lifecycle object age can drift from the voucher SLA clock. The plan/evidence must pin `reproduction_vouchers.created_at` and transition due timestamps.
- Function consistency risk: mutable tags or registry paths could be accepted instead of digest-pinned image references. Validator must reject tag-only proof.
- Drift risk: M3.0 archive-plan and M3.9 pipeline-plan can diverge. Bind M3.9 to the M3.0 plan SHA and test schema/validator parity.
- Boundary risk: committed examples might look like real production evidence. Keep `example_only=true`, synthetic IDs, and no live cloud/pass claims.
- SLA risk: cold Glacier-class archive is not real-time. Use 24h cold-restore target unless a future story provides provisioned expedited evidence and legal/product signoff.
- Security risk: evidence manifests can leak cloud paths, tokens, PII, or credentials. Validator must scan keys and values and restrict artifact paths.
- Closure risk: docs-only pipeline claims would not close G7. The validator and CI job must be the gate, and optional real evidence must have a checked schema.

### References

- `_bmad-output/planning/epics.md` - M3.9 and G7 ownership.
- `_bmad-output/planning/prd.md` - Image archive retrieval and NFR-C11 KMS/quarterly drill.
- `_bmad-output/planning/architecture.md` - Image Supply Chain, ACR EE, S3/Glacier, Repro service future owner.
- `_bmad-output/stories/m3-0-image-archival-prep.md` - M3.0 prep contract and story review findings.
- `_bmad-output/stories/6-b-6-voucher-5y-sla-tracking.md` - voucher clock and restore SOP.
- `_bmad-output/stories/6-b-7-bitwise-reproducibility-test.md` - audit scope and image archive exclusions.
- `infra/image-archival/archive-plan.json`
- `scripts/validate_image_archival_plan.py`
- `tests/test_image_archival_plan.py`
- `docs/runbooks/repro-image-restore.md`

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Resolved the SLA conflict between epics `<=5 min` cold restore and PRD `<=24h` image retrieval by making cold restore target 1440 minutes unless future provisioned expedited evidence exists.
- Added the strict `reproduction_vouchers.created_at` UTC clock source to all plan/evidence requirements and prohibited object-age-only lifecycle proof.
- Added canonical tier names and day ranges from M3.0 plus mandatory M3.0 archive-plan SHA binding.
- Added archive index fields tying voucher ID, image digest, storage tier, transition due/observed timestamps, KMS backup, cosign, and SBOM into one data vocabulary.

Status: PASS after fixes.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Narrowed CI behavior to structural validation only; no cloud, Docker, cosign, syft, Vault, registry, or network calls are allowed.
- Required optional real operator evidence under `reports/image-archival/<run_id>/` rather than fabricated committed production proof.
- Added the exact stage order so implementation cannot drift into a generic backup plan without signing, hot/warm/cold transitions, KMS backup, and quarterly drill.
- Added mutable tag-only rejection because ACR tag retention and cleanup behavior cannot prove durable restore identity without digest-pinned metadata.
- Added explicit no runtime changes to `apps/repro-service`, voucher issuance, rerun endpoint, billing, provider migration, solver execution, UI, and public APIs.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Added standalone validator and targeted tests with negative cases for boundary drift, missing fields, false pass claims, secret leakage, and path traversal.
- Added runbook and CI requirements so M3.9 is not a docs-only claim.
- Added example evidence schema/manifest requirements and `example_only=true` guard.
- Added final workflow tracking requirements for story status, sprint status, validation evidence, file list, change log, and post-implementation review fixes.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Notes

- Added the M3.9 pipeline plan and schema-style reference, bound to the M3.0 archive-plan canonical SHA-256.
- Added stage, tier, signed-image, archive-index, KMS backup, restore target, identity, and voucher-clock policies.
- Added synthetic example evidence and schema under `tools/image_archival/` with all three tier drill rows.
- Added a standard-library validator that validates committed static assets and optional real evidence under `reports/image-archival/<run_id>/`.
- Added regression coverage for hash binding, tier/stage drift, object-age-only lifecycle, tag-only lookup, missing cosign/SBOM/KMS fields, cold five-minute overclaim, evidence redaction, path restrictions, and CI/runbook wiring.
- Post-implementation review tightened schema/validator parity so evidence root fields and artifact fields cannot drift between JSON schema and validator constants.
- Added the operator runbook and linked it from the existing repro image restore SOP.
- Wired a focused CI job for image archival pipeline validation.

### File List

Created:
- `_bmad-output/stories/m3-9-image-5y-archival.md`
- `infra/image-archival/pipeline-plan.json`
- `infra/image-archival/pipeline-plan.schema.json`
- `scripts/validate_image_archival_pipeline.py`
- `tests/test_image_archival_pipeline.py`
- `tools/image_archival/evidence_manifest.schema.json`
- `tools/image_archival/evidence_manifest.example.json`
- `docs/runbooks/image-5y-archival-pipeline.md`

Modified:
- `.pre-commit-config.yaml`
- `.github/workflows/ci.yml`
- `_bmad-output/stories/sprint-status.yaml`
- `docs/runbooks/repro-image-restore.md`

### Validation Evidence

- `uv run pytest tests/test_image_archival_pipeline.py -q` -> RED before implementation: 11 failed because validator, plan, evidence, and runbook did not exist.
- `uv run python scripts/validate_image_archival_pipeline.py` -> PASS (`image archival pipeline OK`).
- `uv run python scripts/validate_image_archival_plan.py infra/image-archival/archive-plan.json` -> PASS.
- `uv run pytest tests/test_image_archival_pipeline.py -q` -> PASS (`11 passed`).
- `uv run ruff check scripts/validate_image_archival_pipeline.py tests/test_image_archival_pipeline.py` -> PASS after code review fix.
- `uv run ruff format --check scripts/validate_image_archival_pipeline.py tests/test_image_archival_pipeline.py` -> PASS after code review fix.
- `uv run pytest tests/test_image_archival_pipeline.py -q` -> PASS (`11 passed`) after code review fix.
- `uv run python scripts/validate_image_archival_pipeline.py` -> PASS after code review fix.
- `uv run python scripts/validate_image_archival_plan.py infra/image-archival/archive-plan.json` -> PASS final.
- `uv run python scripts/validate_image_archival_pipeline.py` -> PASS final.
- `uv run pytest tests/test_image_archival_plan.py tests/test_image_archival_pipeline.py -q` -> PASS (`19 passed`).
- `uv run ruff check scripts/validate_image_archival_pipeline.py tests/test_image_archival_pipeline.py` -> PASS final.
- `uv run ruff format --check scripts/validate_image_archival_pipeline.py tests/test_image_archival_pipeline.py` -> PASS final.
- `git diff --check` -> PASS.
- `uv run pre-commit run --all-files --show-diff-on-failure` -> PASS.
- GitHub PR #71 initial `lint` -> FAIL: detect-secrets flagged public M3.9 plan SHA-256 values as high-entropy strings.

## Senior Developer Review (AI)

Review date: 2026-05-26

Outcome: Approved after fix

Findings fixed:
- Python formatting was not stable under `ruff format --check`; ran formatter and rechecked.
- Validator/schema parity was incomplete. The validator checked selected field enums but did not pin evidence root required fields or artifact required fields, so a schema-only edit could drift from runtime validation. Added parity checks and regression assertions.
- CI lint flagged public M3.9 plan SHA-256 fields in committed JSON as high-entropy strings. Added narrow detect-secrets exclusions for the public archive-plan and pipeline-plan SHA-256 values.

Residual risk:
- M3.9 remains a structural contract and evidence gate. It does not prove live ACR EE, S3, Glacier, Vault, Docker signing, cosign, SBOM, or restore execution until a redacted real evidence manifest is produced by operators.

### Change Log

- 2026-05-26: Created Story M3.9 and completed three pre-implementation story review rounds before implementation.
- 2026-05-26: Started implementation and moved story to in-progress.
- 2026-05-26: Implemented image archival pipeline plan, evidence manifest contract, validator, tests, runbook, and CI job; moved story to code-review.
- 2026-05-26: Completed post-implementation code review, fixed formatting and schema parity coverage, and prepared story for done status after final validation.
- 2026-05-26: Final validation passed and story moved to done.
- 2026-05-26: Fixed PR CI lint false positive by allowlisting public M3.9 plan SHA-256 values.
