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
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_image_archival_pipeline.py"
ARCHIVE_PLAN_PATH = REPO_ROOT / "infra" / "image-archival" / "archive-plan.json"
PIPELINE_PLAN_PATH = REPO_ROOT / "infra" / "image-archival" / "pipeline-plan.json"
PIPELINE_SCHEMA_PATH = REPO_ROOT / "infra" / "image-archival" / "pipeline-plan.schema.json"
EVIDENCE_EXAMPLE_PATH = REPO_ROOT / "tools" / "image_archival" / "evidence_manifest.example.json"
EVIDENCE_SCHEMA_PATH = REPO_ROOT / "tools" / "image_archival" / "evidence_manifest.schema.json"
RUNBOOK_PATH = REPO_ROOT / "docs" / "runbooks" / "image-5y-archival-pipeline.md"
RESTORE_RUNBOOK_PATH = REPO_ROOT / "docs" / "runbooks" / "repro-image-restore.md"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "validate_image_archival_pipeline", VALIDATOR_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _assert_invalid(errors: list[str], expected: str) -> None:
    assert any(expected in error for error in errors), errors


def _real_evidence_from_example() -> dict[str, Any]:
    evidence = _load_json(EVIDENCE_EXAMPLE_PATH)
    evidence["example_only"] = False
    evidence["environment"] = "staging-restore-drill"
    evidence["redaction_reviewed"] = True
    return evidence


def test_committed_image_archival_pipeline_validates_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "image archival pipeline OK" in result.stdout


def test_pipeline_plan_binds_archive_plan_and_stage_order() -> None:
    validator = _load_validator()
    plan = _load_json(PIPELINE_PLAN_PATH)
    archive_plan = _load_json(ARCHIVE_PLAN_PATH)

    assert validator.validate_pipeline_plan(plan, archive_plan) == []
    assert plan["archive_plan_sha256"] == validator.canonical_sha256(archive_plan)
    assert [stage["stage_id"] for stage in plan["stages"]] == list(validator.EXPECTED_STAGES)
    assert [(tier["name"], tier["day_start"], tier["day_end"]) for tier in plan["tiers"]] == [
        ("hot_acr_ee", 0, 90),
        ("warm_s3_standard_ia", 91, 365),
        ("cold_s3_glacier", 366, 1826),
    ]


def test_pipeline_plan_rejects_hash_tier_stage_and_object_age_drift() -> None:
    validator = _load_validator()
    plan = _load_json(PIPELINE_PLAN_PATH)
    archive_plan = _load_json(ARCHIVE_PLAN_PATH)
    plan["archive_plan_sha256"] = "0" * 64
    plan["tiers"][1]["day_start"] = 92
    plan["stages"] = plan["stages"][:-1]
    plan["transition_policy"]["voucher_clock_required"] = False
    plan["transition_policy"]["allows_object_age_only_lifecycle"] = True

    errors = validator.validate_pipeline_plan(plan, archive_plan)

    _assert_invalid(errors, "archive_plan_sha256 does not match")
    _assert_invalid(errors, "warm_s3_standard_ia must cover days 91-365")
    _assert_invalid(errors, "stage order must be")
    _assert_invalid(errors, "voucher_clock_required must be true")
    _assert_invalid(errors, "object-age-only lifecycle is forbidden")


def test_pipeline_plan_rejects_missing_image_signing_and_kms_fields() -> None:
    validator = _load_validator()
    plan = _load_json(PIPELINE_PLAN_PATH)
    archive_plan = _load_json(ARCHIVE_PLAN_PATH)
    plan["required_image_fields"].remove("image_digest")
    plan["required_image_fields"].remove("cosign_signature_ref")
    plan["required_image_fields"].remove("sbom_ref")
    plan["kms_backup_requirements"]["minimum_metadata"].remove("kms_key_backup_ref")

    errors = validator.validate_pipeline_plan(plan, archive_plan)

    _assert_invalid(errors, "required_image_fields missing: cosign_signature_ref")
    _assert_invalid(errors, "required_image_fields missing: image_digest")
    _assert_invalid(errors, "required_image_fields missing: sbom_ref")
    _assert_invalid(errors, "kms_backup_requirements.minimum_metadata missing")


def test_pipeline_plan_rejects_cold_restore_five_minute_overclaim_and_tag_only_lookup() -> None:
    validator = _load_validator()
    plan = _load_json(PIPELINE_PLAN_PATH)
    archive_plan = _load_json(ARCHIVE_PLAN_PATH)
    plan["restore_targets"]["cold_s3_glacier"]["target_minutes"] = 5
    plan["restore_targets"]["cold_s3_glacier"]["allows_five_minute_claim"] = True
    plan["identity_policy"]["digest_required"] = False
    plan["identity_policy"]["allows_tag_only_reference"] = True

    errors = validator.validate_pipeline_plan(plan, archive_plan)

    _assert_invalid(errors, "cold_s3_glacier target_minutes must be 1440")
    _assert_invalid(errors, "cold_s3_glacier must not allow five-minute claims")
    _assert_invalid(errors, "digest_required must be true")
    _assert_invalid(errors, "tag-only references are forbidden")


def test_schema_references_pin_validator_field_sets() -> None:
    validator = _load_validator()
    pipeline_schema = _load_json(PIPELINE_SCHEMA_PATH)
    evidence_schema = _load_json(EVIDENCE_SCHEMA_PATH)

    assert (
        set(pipeline_schema["properties"]["required_image_fields"]["items"]["enum"])
        == validator.REQUIRED_IMAGE_FIELDS
    )
    assert (
        set(pipeline_schema["properties"]["archive_index_required_fields"]["items"]["enum"])
        == validator.REQUIRED_ARCHIVE_INDEX_FIELDS
    )
    assert (
        set(
            pipeline_schema["properties"]["kms_backup_requirements"]["properties"][
                "minimum_metadata"
            ]["items"]["enum"]
        )
        == validator.REQUIRED_KMS_METADATA
    )
    assert (
        set(evidence_schema["properties"]["tier_results"]["items"]["required"])
        == validator.TIER_RESULT_REQUIRED
    )
    assert set(evidence_schema["required"]) == validator.EVIDENCE_ROOT_REQUIRED
    assert set(evidence_schema["properties"]["artifacts"]["required"]) == validator.ARTIFACT_FIELDS


def test_evidence_example_validates_and_real_path_mode_accepts_redacted_drill() -> None:
    validator = _load_validator()
    plan = _load_json(PIPELINE_PLAN_PATH)
    archive_plan = _load_json(ARCHIVE_PLAN_PATH)
    evidence = _load_json(EVIDENCE_EXAMPLE_PATH)

    assert (
        validator.validate_evidence_manifest(
            evidence,
            plan,
            archive_plan,
            source="evidence-example",
            real_evidence=False,
        )
        == []
    )

    real_evidence = _real_evidence_from_example()
    run_id = "test-image-archival-20260526"
    run_dir = REPO_ROOT / "reports" / "image-archival" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = run_dir / "evidence_manifest.json"
    real_evidence["run_id"] = run_id
    for key, value in real_evidence["artifacts"].items():
        real_evidence["artifacts"][key] = value.replace("example-image-archival-20260526", run_id)
    evidence_path.write_text(
        json.dumps(real_evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    try:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR_PATH), "--evidence", str(evidence_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        evidence_path.unlink(missing_ok=True)
        run_dir.rmdir()


def test_evidence_rejects_example_as_real_missing_tier_and_unverified_kms() -> None:
    validator = _load_validator()
    plan = _load_json(PIPELINE_PLAN_PATH)
    archive_plan = _load_json(ARCHIVE_PLAN_PATH)
    evidence = _load_json(EVIDENCE_EXAMPLE_PATH)

    errors = validator.validate_evidence_manifest(
        evidence,
        plan,
        archive_plan,
        source="evidence-example",
        real_evidence=True,
    )
    _assert_invalid(errors, "real evidence must set example_only=false")

    real_evidence = _real_evidence_from_example()
    real_evidence["tier_results"] = real_evidence["tier_results"][:2]
    real_evidence["tier_results"][0]["kms_backup_verified"] = False

    errors = validator.validate_evidence_manifest(
        real_evidence,
        plan,
        archive_plan,
        source="evidence-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "real evidence must include all storage tiers")
    _assert_invalid(errors, "kms_backup_verified must be true")


def test_evidence_rejects_artifact_traversal_urls_credentials_and_bearer_tokens() -> None:
    validator = _load_validator()
    plan = _load_json(PIPELINE_PLAN_PATH)
    archive_plan = _load_json(ARCHIVE_PLAN_PATH)
    evidence = copy.deepcopy(_real_evidence_from_example())
    evidence["artifacts"]["restore_report"] = (
        "reports/image-archival/example-image-archival-20260526/../restore.txt"
    )
    evidence["artifacts"]["redaction_audit"] = "https://example.com/redaction.json"
    evidence["tier_results"][0]["registry_or_object_ref"] = (
        "https://user:password@example.com/repo/image"
    )
    evidence["tier_results"][1]["notes"] = "Authorization: Bearer abcdef1234567890"

    errors = validator.validate_evidence_manifest(
        evidence,
        plan,
        archive_plan,
        source="evidence-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "artifact path must not traverse")
    _assert_invalid(errors, "artifact path must not be a URL")
    _assert_invalid(errors, "forbidden credentialed url")
    _assert_invalid(errors, "forbidden bearer token")


def test_evidence_path_mode_rejects_wrong_report_directory() -> None:
    validator = _load_validator()

    assert (
        validator.validate_evidence_path_mode(
            Path("reports/image-archival/run-123/evidence_manifest.json")
        )
        == []
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/prod-traffic-replay/run-123/evidence_manifest.json")
        ),
        "image archival evidence path must be",
    )


def test_runbooks_and_ci_wire_m3_9_boundaries() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")
    restore_runbook = RESTORE_RUNBOOK_PATH.read_text(encoding="utf-8")
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    for expected in (
        "CI validates structure only",
        "does not prove ACR EE",
        "cold restore target is 24 hours",
        "reports/image-archival/<run_id>/evidence_manifest.json",
        "do not commit credentials",
        "reproduction_vouchers.created_at",
    ):
        assert expected in runbook
    assert "image-5y-archival-pipeline.md" in restore_runbook
    for expected in (
        "image_archival_pipeline: ${{ steps.filter.outputs.image_archival_pipeline }}",
        "image-archival-pipeline-validation:",
        "'tools/image_archival/**'",
        "'scripts/validate_image_archival_pipeline.py'",
        "'tests/test_image_archival_pipeline.py'",
        "'docs/runbooks/image-5y-archival-pipeline.md'",
        "'reports/image-archival/**'",
        "uv run python scripts/validate_image_archival_pipeline.py --evidence",
        "uv run pytest tests/test_image_archival_pipeline.py -v",
    ):
        assert expected in workflow
