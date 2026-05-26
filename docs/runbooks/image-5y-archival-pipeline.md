# Image 5y Archival Pipeline Runbook

## Purpose

This runbook operationalizes Story M3.9: signed provider images, ACR EE hot retention, warm object-storage copies, cold Glacier-class archive, Vault/KMS backup references, and quarterly restore drill evidence.

The canonical SLA clock is `reproduction_vouchers.created_at` in UTC. Bucket lifecycle age and image push time are not enough evidence by themselves.

## CI Boundary

CI validates structure only. It does not prove ACR EE, S3 Standard-IA, S3 Glacier, Vault, Docker signing, cosign verification, SBOM generation, registry access, or real restore execution.

Run locally:

```bash
uv run python scripts/validate_image_archival_pipeline.py
uv run pytest tests/test_image_archival_pipeline.py -q
```

Real operator evidence belongs at:

```text
reports/image-archival/<run_id>/evidence_manifest.json
```

Validate a real manifest:

```bash
uv run python scripts/validate_image_archival_pipeline.py --evidence reports/image-archival/<run_id>/evidence_manifest.json
```

## Restore Target

The cold restore target is 24 hours. Epics previously requested cold image restore within five minutes, but PRD Core Innovation #2 states archive retrieval within 24 hours and M3.0 documented that Glacier-class restores are not real-time.

Hot ACR EE lookup can target five minutes. Warm and cold restore evidence must be treated as archive recovery workflow evidence, not proof of instant voucher rerun from cold storage.

## Required Evidence

Each quarterly drill manifest must include one result per tier:

- `hot_acr_ee`
- `warm_s3_standard_ia`
- `cold_s3_glacier`

Each tier row must include digest-pinned image identity, cosign verification, SBOM verification, KMS backup verification, restore timing, and outcome. Mutable tags alone are not valid evidence.

## Redaction

Operator rule: do not commit credentials, bearer tokens, cookies, customer prompts, user PII, Vault tokens, registry credentials, raw provider artifacts, or credentialed URLs.

Artifact paths must be repository-relative and stay under the matching `reports/image-archival/<run_id>/` directory.

## Failure Handling

- Schema or validator failure blocks the PR.
- Missing tier evidence means the quarterly drill is incomplete.
- KMS restore-test failure blocks archival readiness.
- Digest, cosign, or SBOM mismatch is a P0 investigation.
- Cold restore exceeding 24 hours is a P1 unless broader corruption or user data loss is suspected.
