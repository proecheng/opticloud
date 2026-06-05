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
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_wcag_2_2_upgrade_path.py"
CONTRACT_PATH = REPO_ROOT / "tools" / "wcag_2_2_upgrade" / "wcag_2_2_upgrade_contract.json"
SCHEMA_PATH = REPO_ROOT / "tools" / "wcag_2_2_upgrade" / "wcag_2_2_upgrade_manifest.schema.json"
EXAMPLE_MANIFEST_PATH = (
    REPO_ROOT / "tools" / "wcag_2_2_upgrade" / "wcag_2_2_upgrade_manifest.example.json"
)
RUNBOOK_PATH = REPO_ROOT / "docs" / "runbooks" / "wcag-2-2-upgrade-path.md"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_wcag_2_2_upgrade_path", VALIDATOR_PATH)
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


def _real_manifest_from_example() -> dict[str, Any]:
    manifest = copy.deepcopy(_load_json(EXAMPLE_MANIFEST_PATH))
    manifest["run_id"] = "test-wcag-2-2-upgrade-20260605"
    manifest["example_only"] = False
    manifest["generated_by"] = "redacted WCAG 2.2 upgrade path evidence"
    manifest["commit_sha"] = "1e9d346"
    manifest["redaction_reviewed"] = True
    manifest["release_approved"] = True
    manifest["real_component_refactor_completed"] = True
    manifest["real_third_party_audit_completed"] = False
    manifest["real_wcag_2_2_conformance_claimed"] = False
    for evaluation in manifest["criteria_evaluations"]:
        evaluation["status"] = "passed"
    for check in manifest["hook_v2_checks"]:
        check["status"] = "passed"
    for check in manifest["component_refactor_checks"]:
        check["status"] = "passed"
    for snapshot in manifest["source_snapshots"]:
        snapshot["status"] = "current"
    return manifest


def test_committed_wcag_2_2_upgrade_assets_validate_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "WCAG 2.2 upgrade path OK" in result.stdout


def test_contract_pins_p78_scope_w3c_metadata_and_repo_state() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)

    assert validator.validate_contract(contract) == []
    assert contract["source_story"] == "9.5"
    assert contract["upgrade_version"] == "wcag_2_2_upgrade_path_v1"
    assert contract["w3c_wcag_2_2"]["recommendation_date"] == "2023-10-05"
    assert contract["w3c_wcag_2_2"]["total_new_success_criteria"] == 9
    assert [item["criterion_id"] for item in contract["project_p78_criteria"]] == list(
        validator.PROJECT_CRITERIA_IDS
    )
    assert [item["level"] for item in contract["project_p78_criteria"]] == [
        "AA",
        "AAA",
        "AA",
        "A",
    ]
    assert contract["deferred_wcag_2_2_criteria"] == list(validator.DEFERRED_CRITERIA_IDS)
    assert contract["observed_ui_state"] == validator.discover_ui_state()


def test_contract_rejects_scope_confusion_deferred_loss_and_ui_drift() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    contract["w3c_wcag_2_2"]["total_new_success_criteria"] = 4
    contract["project_p78_criteria"][1]["level"] = "AA"
    contract["deferred_wcag_2_2_criteria"].remove("3.3.8")
    contract["observed_ui_state"]["use_a11y"]["has_focus_not_obscured_option"] = False

    errors = validator.validate_contract(contract)

    _assert_invalid(errors, "total_new_success_criteria must be 9")
    _assert_invalid(errors, "project P78 criterion levels drifted")
    _assert_invalid(errors, "deferred criteria must preserve full-AA blockers")
    _assert_invalid(errors, "observed_ui_state drifted")


def test_schema_pins_manifest_root_and_criteria_enums() -> None:
    validator = _load_validator()
    schema = _load_json(SCHEMA_PATH)

    assert validator.validate_schema(schema) == []
    assert set(schema["required"]) == validator.MANIFEST_ROOT_REQUIRED
    assert schema["$defs"]["projectCriterionId"]["enum"] == list(validator.PROJECT_CRITERIA_IDS)


def test_static_example_is_static_only_and_rejects_fake_completion_claims() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)

    assert (
        validator.validate_manifest(
            manifest,
            contract,
            source="wcag-2-2-example",
            real_evidence=False,
        )
        == []
    )
    manifest["real_wcag_2_2_conformance_claimed"] = True
    manifest["real_third_party_audit_completed"] = True
    manifest["real_component_refactor_completed"] = True
    manifest["release_approved"] = True
    manifest["external_ticket_created"] = True

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="wcag-2-2-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "static example cannot claim real_wcag_2_2_conformance_claimed")
    _assert_invalid(errors, "static example cannot claim real_third_party_audit_completed")
    _assert_invalid(errors, "static example cannot claim real_component_refactor_completed")
    _assert_invalid(errors, "static example cannot claim release_approved")
    _assert_invalid(errors, "static example cannot claim external_ticket_created")


def test_real_evidence_path_mode_accepts_redacted_manifest() -> None:
    manifest = _real_manifest_from_example()
    run_dir = REPO_ROOT / "reports" / "wcag-2-2-upgrade" / manifest["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "upgrade_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "--evidence", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )

    try:
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        path.unlink(missing_ok=True)
        run_dir.rmdir()


def test_real_evidence_path_mode_rejects_wrong_directory_and_run_id_mismatch() -> None:
    validator = _load_validator()

    assert (
        validator.validate_evidence_path_mode(
            Path("reports/wcag-2-2-upgrade/run-123/upgrade_manifest.json"),
            "run-123",
        )
        == []
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/a11y-quarterly/run-123/upgrade_manifest.json"),
            "run-123",
        ),
        "WCAG 2.2 upgrade evidence path must be",
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/wcag-2-2-upgrade/other/upgrade_manifest.json"),
            "run-123",
        ),
        "WCAG 2.2 upgrade evidence path must be",
    )


def test_real_evidence_requires_all_criteria_hook_component_and_snapshot_rows() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["criteria_evaluations"].pop()
    manifest["hook_v2_checks"].pop()
    manifest["component_refactor_checks"].pop()
    manifest["source_snapshots"].pop()

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="wcag-2-2-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "criteria_evaluations missing criterion")
    _assert_invalid(errors, "hook_v2_checks missing check")
    _assert_invalid(errors, "component_refactor_checks missing component")
    _assert_invalid(errors, "source_snapshots missing snapshot")


def test_real_evidence_rejects_invalid_statuses_and_duplicate_rows() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["criteria_evaluations"][0]["status"] = "current"
    manifest["hook_v2_checks"][0]["status"] = "stale"
    manifest["component_refactor_checks"][0]["status"] = "current"
    manifest["source_snapshots"].append(copy.deepcopy(manifest["source_snapshots"][0]))

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="wcag-2-2-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "real criteria_evaluations status invalid")
    _assert_invalid(errors, "real hook_v2_checks status invalid")
    _assert_invalid(errors, "real component_refactor_checks status invalid")
    _assert_invalid(errors, "source_snapshots duplicate snapshot_id")


def test_failures_and_stale_snapshots_require_ticket_refs() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["criteria_evaluations"][0]["status"] = "failed"
    manifest["hook_v2_checks"][0]["status"] = "failed"
    manifest["component_refactor_checks"][0]["status"] = "failed"
    manifest["source_snapshots"][0]["status"] = "stale"
    manifest["findings"] = []

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="wcag-2-2-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "failed criterion")
    _assert_invalid(errors, "failed hook check")
    _assert_invalid(errors, "failed component check")
    _assert_invalid(errors, "stale source snapshot")


def test_release_approval_blocks_unresolved_stop_ship_findings_and_full_claims() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["real_wcag_2_2_conformance_claimed"] = True
    manifest["findings"] = [
        {
            "finding_id": "nfr-a-open-p1",
            "severity": "P1",
            "status": "open",
            "summary": "Focus is obscured in modal stack.",
            "ticket_refs": [
                {
                    "ticket_id": "A11Y-123",
                    "owner": "Frontend",
                    "severity": "P1",
                    "due_date": "2026-06-30",
                    "status": "open",
                }
            ],
        }
    ]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="wcag-2-2-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "cannot claim full WCAG 2.2 conformance")
    _assert_invalid(errors, "release_approved cannot be true")


def test_sensitive_values_and_conformance_language_are_rejected() -> None:
    validator = _load_validator()
    manifest = _real_manifest_from_example()
    manifest["notes"] = "Full WCAG 2.2 AA conformance achieved for production."
    manifest["source_snapshots"][0]["artifact_path"] = "C:/Users/admin/raw-browser.log"
    manifest["criteria_evaluations"][0]["notes"] = "Contact user@example.com for raw logs."

    errors = validator.validate_no_sensitive_values(manifest, "wcag-2-2-real")

    _assert_invalid(errors, "forbidden full WCAG conformance claim")
    _assert_invalid(errors, "forbidden Windows absolute path")
    _assert_invalid(errors, "forbidden email address")


def test_runbook_documents_boundary_commands_and_evidence_policy() -> None:
    text = RUNBOOK_PATH.read_text(encoding="utf-8")

    for expected in [
        "uv run python scripts/validate_wcag_2_2_upgrade_path.py",
        "WCAG 2.2 adds 9 success criteria",
        "P78 4-criteria engineering gate",
        "reports/wcag-2-2-upgrade/<run_id>/upgrade_manifest.json",
        "does not prove full WCAG 2.2 AA conformance",
        "Story 9.1",
    ]:
        assert expected in text


def test_ci_workflow_wires_wcag_upgrade_path_filter_and_job() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert validator.validate_ci_workflow(workflow) == []
    assert "wcag_2_2_upgrade_path" in workflow
    assert "wcag-2-2-upgrade-path-validation" in workflow
    assert "scripts/validate_wcag_2_2_upgrade_path.py" in workflow
    assert "tests/test_wcag_2_2_upgrade_path.py" in workflow
    assert "docs/runbooks/wcag-2-2-upgrade-path.md" in workflow
    assert "reports/wcag-2-2-upgrade/**" in workflow
    assert "pnpm --filter @opticloud/ui test:a11y" in workflow
    assert "pnpm --filter @opticloud/ui typecheck" in workflow


def test_ci_filter_validation_is_block_scoped() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    workflow = workflow.replace(
        "            wcag_2_2_upgrade_path:\n"
        "              - 'packages/ui/**'\n"
        "              - 'tools/wcag_2_2_upgrade/**'\n"
        "              - 'scripts/validate_wcag_2_2_upgrade_path.py'\n"
        "              - 'tests/test_wcag_2_2_upgrade_path.py'\n"
        "              - 'docs/runbooks/wcag-2-2-upgrade-path.md'\n"
        "              - 'reports/wcag-2-2-upgrade/**'\n"
        "              - 'tools/a11y_audit/**'\n"
        "              - 'scripts/validate_a11y_quarterly_audit.py'\n"
        "              - '.github/workflows/ci.yml'\n",
        "            wcag_2_2_upgrade_path:\n"
        "              - 'packages/ui/**'\n"
        "              - 'tools/wcag_2_2_upgrade/**'\n"
        "              - 'scripts/validate_wcag_2_2_upgrade_path.py'\n",
    )

    errors = validator.validate_ci_workflow(workflow)

    _assert_invalid(errors, "wcag_2_2_upgrade_path filter missing")
