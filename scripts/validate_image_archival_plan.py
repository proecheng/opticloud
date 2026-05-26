"""Validate the M3.0 image archival prep contract.

This script intentionally uses only the Python standard library and performs no
cloud, Docker, signing, SBOM, Vault, or network operations.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


EXPECTED_CLOCK = {"source": "reproduction_vouchers.created_at", "timezone": "UTC"}
EXPECTED_TIERS = [
    ("hot_acr_ee", 0, 90),
    ("warm_s3_standard_ia", 91, 365),
    ("cold_s3_glacier", 366, 1826),
]
REQUIRED_ARCHIVE_RECORD_FIELDS = {
    "voucher_id",
    "voucher_created_at_utc",
    "provider_id",
    "solver",
    "model_version",
    "image_digest",
    "cosign_signature_ref",
    "sbom_ref",
    "storage_tier",
    "registry_or_object_ref",
    "kms_key_backup_ref",
}
REQUIRED_KMS_METADATA = {
    "kms_key_id",
    "backup_location_ref",
    "backup_created_at_utc",
    "backup_checksum",
}
REQUIRED_RESTORE_DRILL_FIELDS = {
    "drill_id",
    "drill_started_at_utc",
    "voucher_id",
    "voucher_created_at_utc",
    "storage_tier",
    "registry_or_object_ref",
    "image_digest",
    "cosign_signature_ref",
    "sbom_ref",
    "kms_key_backup_ref",
    "operator",
    "outcome",
}
REQUIRED_EXCEPTION_FIELDS = {
    "exception_id",
    "detected_at_utc",
    "voucher_id",
    "voucher_created_at_utc",
    "storage_tier",
    "missing_or_corrupt_ref",
    "within_5y_clock",
    "user_visible_remediation_owner",
    "engineering_owner",
    "severity",
    "outcome",
}


def _missing(actual: object, expected: set[str]) -> list[str]:
    if not isinstance(actual, list):
        return sorted(expected)
    return sorted(expected - set(actual))


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if plan.get("scope") != "prep-only":
        errors.append("scope must be prep-only")

    clock = plan.get("clock")
    if not isinstance(clock, dict):
        errors.append("clock must be an object")
    else:
        if clock.get("source") != EXPECTED_CLOCK["source"]:
            errors.append("clock.source must be reproduction_vouchers.created_at")
        if clock.get("timezone") != EXPECTED_CLOCK["timezone"]:
            errors.append("clock.timezone must be UTC")

    tiers = plan.get("tiers")
    if not isinstance(tiers, list):
        errors.append("tiers must be a list")
    elif len(tiers) != len(EXPECTED_TIERS):
        errors.append("tiers must contain exactly three entries")
    else:
        for index, (expected_name, expected_start, expected_end) in enumerate(EXPECTED_TIERS):
            tier = tiers[index]
            if not isinstance(tier, dict):
                errors.append(f"tier {index} must be an object")
                continue
            if tier.get("name") != expected_name:
                errors.append(f"tier {index} name must be {expected_name}")
            if tier.get("day_start") != expected_start or tier.get("day_end") != expected_end:
                errors.append(
                    f"{expected_name} must cover days {expected_start}-{expected_end}"
                )

    missing_archive = _missing(
        plan.get("required_archive_record_fields"), REQUIRED_ARCHIVE_RECORD_FIELDS
    )
    if missing_archive:
        errors.append(f"required_archive_record_fields missing: {', '.join(missing_archive)}")

    kms = plan.get("kms_backup_requirements")
    if not isinstance(kms, dict):
        errors.append("kms_backup_requirements must be an object")
    else:
        if kms.get("required") is not True:
            errors.append("kms_backup_requirements.required must be true")
        if kms.get("reference_field") != "kms_key_backup_ref":
            errors.append("kms_backup_requirements.reference_field must be kms_key_backup_ref")
        missing_kms = _missing(kms.get("minimum_metadata"), REQUIRED_KMS_METADATA)
        if missing_kms:
            errors.append(f"kms_backup_requirements.minimum_metadata missing: {', '.join(missing_kms)}")

    missing_drill = _missing(plan.get("restore_drill_evidence_fields"), REQUIRED_RESTORE_DRILL_FIELDS)
    if missing_drill:
        errors.append(f"restore_drill_evidence_fields missing: {', '.join(missing_drill)}")

    missing_exception = _missing(
        plan.get("unavailable_restore_exception_fields"), REQUIRED_EXCEPTION_FIELDS
    )
    if missing_exception:
        errors.append(
            "unavailable_restore_exception_fields missing: " + ", ".join(missing_exception)
        )

    if plan.get("downstream_story") != "M3.9 Image 5y layered archival pipeline":
        errors.append("downstream_story must remain M3.9 Image 5y layered archival pipeline")

    return errors


def load_plan(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("archive plan root must be a JSON object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate OptiCloud image archival plan")
    parser.add_argument("plan", type=Path, help="Path to infra/image-archival/archive-plan.json")
    args = parser.parse_args()

    try:
        plan = load_plan(args.plan)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: unable to load archive plan: {exc}", file=sys.stderr)
        return 1

    errors = validate_plan(plan)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"image archival plan OK: {args.plan}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
