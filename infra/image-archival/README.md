# Image Archival Prep

Story M3.0 creates the repository contract for the future image archival pipeline. It does not provision cloud resources, migrate images, write Vault secrets, or implement voucher rerun restore behavior.

## Files

- `archive-plan.json` - committed prep contract for image archive tiers and required restore metadata.
- `archive-plan.schema.json` - schema-style reference for downstream tooling.

## Tier Contract

All tier age calculations use `reproduction_vouchers.created_at` in UTC.

| Tier | Days | Target storage |
|---|---:|---|
| `hot_acr_ee` | 0-90 | Alibaba Cloud ACR Enterprise Edition |
| `warm_s3_standard_ia` | 91-365 | S3 Standard-IA or equivalent warm object storage |
| `cold_s3_glacier` | 366-1826 | S3 Glacier Flexible Retrieval or equivalent |

The boundaries are contiguous and non-overlapping. Do not substitute image push time, provider exit time, restore request time, or local time for the voucher clock.

## Required Restore Metadata

Every future archive index row must carry enough metadata to verify the restored artifact:

- Voucher ID and `reproduction_vouchers.created_at` UTC.
- Provider, solver, and model version.
- Image digest, cosign signature reference, and SBOM reference.
- Storage tier and registry/object reference.
- KMS key backup reference.

## M3.9 Handoff

Story M3.9 owns the live implementation:

- ACR EE retention and registry lookup.
- Warm object-storage lifecycle transition.
- Cold Glacier-class archive and restore request handling.
- Encrypted KMS key backup automation.
- Quarterly restore drill execution and evidence archival.
- Voucher rerun integration for restored images.

M3.0 only validates that the local prep contract is internally consistent.

## Local Validation

```bash
uv run python scripts/validate_image_archival_plan.py infra/image-archival/archive-plan.json
uv run pytest tests/test_image_archival_plan.py -q
```
