from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_saga_cross_epic_dryrun.py"
DRYRUN_DIR = REPO_ROOT / "tools" / "saga_cross_epic_dryrun"
PLAN_PATH = DRYRUN_DIR / "dryrun_plan.json"
SIGNOFF_PATH = DRYRUN_DIR / "owner_signoff.example.json"
RUNBOOK_PATH = REPO_ROOT / "docs" / "runbooks" / "saga-cross-epic-dryrun.md"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_saga_cross_epic_dryrun", VALIDATOR_PATH)
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


def test_committed_saga_cross_epic_dryrun_validates_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "saga cross-epic dry-run OK" in result.stdout


def test_plan_pins_fixture_manifest_owner_roles_and_i_s3_decision() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    signoff = _load_json(SIGNOFF_PATH)
    expected_summary = validator.build_fixture_manifest_summary()

    assert validator.validate_plan(plan, expected_summary) == []
    assert validator.validate_signoff_example(signoff, plan) == []
    assert plan["story_key"] == "5-a-0c-saga-cross-epic-dryrun"
    assert plan["fixture_manifest"]["version"] == "2026-05-30.saga-fixtures.v1"
    assert plan["fixture_manifest"]["total_fixtures"] == 52
    assert plan["fixture_manifest"]["executable_fixtures"] == 50
    assert plan["required_blocking_signoff_roles"] == ["Billing Lead", "Solver Lead", "SRE"]
    assert plan["decision_record"]["decision"] == "standard_first_simplified_fallback"
    assert signoff["example_only"] is True
    assert signoff["fixture_manifest_sha256"] == plan["fixture_manifest"]["sha256"]


def test_fixture_manifest_version_hash_and_count_drift_is_rejected() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    expected_summary = validator.build_fixture_manifest_summary()
    plan["fixture_manifest"]["version"] = "drifted"
    plan["fixture_manifest"]["sha256"] = "0" * 64
    plan["fixture_manifest"]["total_fixtures"] = 51
    plan["fixture_manifest"]["category_counts"]["charge"] = 9

    errors = validator.validate_plan(plan, expected_summary)

    _assert_invalid(errors, "fixture manifest version does not match")
    _assert_invalid(errors, "fixture manifest sha256 does not match")
    _assert_invalid(errors, "fixture total_fixtures does not match")
    _assert_invalid(errors, "fixture category_counts do not match")


def test_plan_signoff_fixture_hash_mismatch_is_rejected() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    signoff = _load_json(SIGNOFF_PATH)
    signoff["fixture_manifest_sha256"] = "1" * 64

    errors = validator.validate_signoff_example(signoff, plan)

    _assert_invalid(errors, "fixture_manifest_sha256 must match dryrun plan")


def test_required_owner_role_drift_is_rejected() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    expected_summary = validator.build_fixture_manifest_summary()
    plan["required_blocking_signoff_roles"] = ["Billing Lead", "Solver Lead"]
    plan["owner_review_map"][0]["blocking"] = False
    plan["owner_review_map"][1]["role"] = "alice@example.com"
    plan["owner_review_map"][2]["review_focus"] = ["timeout_and_retry_contract_is_visible"]

    errors = validator.validate_plan(plan, expected_summary)

    _assert_invalid(
        errors, "required_blocking_signoff_roles must be Billing Lead, Solver Lead, SRE"
    )
    _assert_invalid(errors, "Billing Lead owner entry must be blocking")
    _assert_invalid(errors, "contains forbidden email")
    _assert_invalid(errors, "SRE review_focus must include outbox")


def test_i_s3_decision_drift_is_rejected() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    expected_summary = validator.build_fixture_manifest_summary()
    plan["decision_record"]["decision"] = "simplified_now"
    plan["decision_record"]["current_implementation_target"] = "simplified_fallback"

    errors = validator.validate_plan(plan, expected_summary)

    _assert_invalid(errors, "decision must be standard_first_simplified_fallback")
    _assert_invalid(errors, "current implementation target must be standard_path")


def test_fake_completion_signoff_ci_and_live_run_claims_are_rejected() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    signoff = _load_json(SIGNOFF_PATH)
    expected_summary = validator.build_fixture_manifest_summary()
    plan["claims"]["ci_passed"] = True
    plan["claims"]["live_services_executed"] = True
    signoff["status"] = "approved"
    signoff["meeting_started_at"] = "2026-05-30T10:00:00Z"
    signoff["ci_status"] = "passed"
    signoff["open_risks"] = ["CI passed and approved by committee"]

    plan_errors = validator.validate_plan(plan, expected_summary)
    signoff_errors = validator.validate_signoff_example(signoff, plan)

    _assert_invalid(plan_errors, "ci_passed must be false")
    _assert_invalid(plan_errors, "live_services_executed must be false")
    _assert_invalid(signoff_errors, "status must be not_a_real_signoff")
    _assert_invalid(signoff_errors, "meeting_started_at must be placeholder")
    _assert_invalid(signoff_errors, "ci_status must be not_run")
    _assert_invalid(signoff_errors, "forbidden fake completion claim")


def test_privacy_secrets_pii_raw_payloads_and_raw_hosts_are_rejected() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    expected_summary = validator.build_fixture_manifest_summary()
    plan["owner_review_map"][0]["notes"] = "Bearer abcdef1234567890"
    plan["owner_review_map"][1]["notes"] = "raw prompt: solve customer input"
    plan["owner_review_map"][2]["notes"] = "https://billing.internal.example.com"
    plan["owner_review_map"][3]["notes"] = "tenant_id=tenant-123 user_id=user-123"

    errors = validator.validate_plan(plan, expected_summary)

    _assert_invalid(errors, "forbidden bearer token")
    _assert_invalid(errors, "forbidden prompt-like value")
    _assert_invalid(errors, "forbidden raw URL host")
    _assert_invalid(errors, "forbidden tenant/user identifier")


def test_repository_path_boundaries_are_rejected() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    expected_summary = validator.build_fixture_manifest_summary()
    plan["artifact_paths"].append("../outside.json")
    plan["artifact_paths"].append("/absolute/path.json")
    plan["artifact_paths"].append("tools/other/dryrun.json")

    errors = validator.validate_plan(plan, expected_summary)

    _assert_invalid(errors, "artifact path must not traverse")
    _assert_invalid(errors, "artifact path must be repository-relative")
    _assert_invalid(errors, "artifact path must stay under tools/saga_cross_epic_dryrun")


def test_signoff_open_risks_structure_is_required() -> None:
    validator = _load_validator()
    plan = _load_json(PLAN_PATH)
    signoff = _load_json(SIGNOFF_PATH)
    signoff["open_risks"] = []

    errors = validator.validate_signoff_example(signoff, plan)

    _assert_invalid(errors, "open_risks must be a non-empty list of strings")


def test_runbook_sensitive_values_are_rejected() -> None:
    validator = _load_validator()
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")
    runbook += (
        "\nContact alice@example.com with Bearer abcdef1234567890 at https://internal.example"
    )

    errors = validator.validate_runbook_text(runbook)

    _assert_invalid(errors, "contains forbidden email")
    _assert_invalid(errors, "contains forbidden bearer token")
    _assert_invalid(errors, "contains forbidden raw URL host")


def test_runbook_documents_offline_boundaries_and_owner_process() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    for expected in (
        "offline only",
        "does not run billing-service or solver-orchestrator",
        "does not prove real committee approval",
        "standard_first_simplified_fallback",
        "Billing Lead",
        "Solver Lead",
        "SRE",
        "Provider Interface Lead",
        "not_a_real_signoff",
    ):
        assert expected in runbook
