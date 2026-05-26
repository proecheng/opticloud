from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = REPO_ROOT / "infra" / "image-archival" / "archive-plan.json"
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_image_archival_plan.py"
SCHEMA_PATH = REPO_ROOT / "infra" / "image-archival" / "archive-plan.schema.json"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_image_archival_plan", VALIDATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_plan() -> dict[str, Any]:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _assert_invalid(plan: dict[str, Any], expected: str) -> None:
    validator = _load_validator()
    errors = validator.validate_plan(plan)
    assert any(expected in error for error in errors), errors


def test_committed_archive_plan_validates_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), str(PLAN_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "image archival plan OK" in result.stdout


def test_missing_required_tier_is_rejected() -> None:
    plan = _load_plan()
    plan["tiers"] = plan["tiers"][:-1]

    _assert_invalid(plan, "tiers must contain exactly three entries")


def test_non_contiguous_tier_boundary_is_rejected() -> None:
    plan = _load_plan()
    plan["tiers"][1]["day_start"] = 92

    _assert_invalid(plan, "warm_s3_standard_ia must cover days 91-365")


def test_missing_voucher_clock_source_is_rejected() -> None:
    plan = _load_plan()
    plan["clock"]["source"] = "image_pushed_at"

    _assert_invalid(plan, "clock.source must be reproduction_vouchers.created_at")


def test_missing_image_digest_metadata_is_rejected() -> None:
    plan = _load_plan()
    fields = copy.copy(plan["required_archive_record_fields"])
    fields.remove("image_digest")
    plan["required_archive_record_fields"] = fields

    _assert_invalid(plan, "required_archive_record_fields missing: image_digest")


def test_missing_kms_backup_reference_is_rejected() -> None:
    plan = _load_plan()
    fields = copy.copy(plan["required_archive_record_fields"])
    fields.remove("kms_key_backup_ref")
    plan["required_archive_record_fields"] = fields

    _assert_invalid(plan, "required_archive_record_fields missing: kms_key_backup_ref")


def test_missing_restore_drill_evidence_field_is_rejected() -> None:
    plan = _load_plan()
    fields = copy.copy(plan["restore_drill_evidence_fields"])
    fields.remove("kms_key_backup_ref")
    plan["restore_drill_evidence_fields"] = fields

    _assert_invalid(plan, "restore_drill_evidence_fields missing: kms_key_backup_ref")


def test_schema_reference_pins_validator_field_sets() -> None:
    validator = _load_validator()
    schema = _load_schema()

    archive_field_enum = set(
        schema["properties"]["required_archive_record_fields"]["items"]["enum"]
    )
    kms_field_enum = set(
        schema["properties"]["kms_backup_requirements"]["properties"]["minimum_metadata"][
            "items"
        ]["enum"]
    )
    drill_field_enum = set(
        schema["properties"]["restore_drill_evidence_fields"]["items"]["enum"]
    )
    exception_field_enum = set(
        schema["properties"]["unavailable_restore_exception_fields"]["items"]["enum"]
    )

    assert archive_field_enum == validator.REQUIRED_ARCHIVE_RECORD_FIELDS
    assert kms_field_enum == validator.REQUIRED_KMS_METADATA
    assert drill_field_enum == validator.REQUIRED_RESTORE_DRILL_FIELDS
    assert exception_field_enum == validator.REQUIRED_EXCEPTION_FIELDS
