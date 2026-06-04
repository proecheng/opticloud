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
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_a11y_quarterly_audit.py"
CONTRACT_PATH = REPO_ROOT / "tools" / "a11y_audit" / "quarterly_a11y_contract.json"
SCHEMA_PATH = REPO_ROOT / "tools" / "a11y_audit" / "quarterly_a11y_manifest.schema.json"
EXAMPLE_MANIFEST_PATH = REPO_ROOT / "tools" / "a11y_audit" / "quarterly_a11y_manifest.example.json"
RUNBOOK_PATH = REPO_ROOT / "docs" / "runbooks" / "quarterly-a11y-audit.md"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_a11y_quarterly_audit", VALIDATOR_PATH)
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
    validator = _load_validator()
    manifest = copy.deepcopy(_load_json(EXAMPLE_MANIFEST_PATH))
    manifest["run_id"] = "test-a11y-quarterly-20260604"
    manifest["example_only"] = False
    manifest["generated_by"] = "redacted quarterly accessibility evidence"
    manifest["commit_sha"] = "26a90ae"
    manifest["redaction_reviewed"] = True
    manifest["release_approved"] = True
    manifest["real_panel_completed"] = True
    manifest["automated_axe"]["executed"] = True
    manifest["automated_axe"]["status"] = "passed"
    manifest["automated_axe"]["violation_count"] = 0
    manifest["automated_axe"]["test_files"] = validator.discover_component_a11y_tests()
    for cell in manifest["manual_sampling"]["matrix"]:
        cell["status"] = "passed"
        cell["notes"] = "Redacted quarterly operator evidence."
    return manifest


def test_committed_a11y_audit_assets_validate_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "quarterly a11y audit OK" in result.stdout


def test_contract_pins_story_scope_profiles_personas_and_panel_sop() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)

    assert validator.validate_contract(contract) == []
    assert contract["audit_version"] == "quarterly_a11y_audit_v1"
    assert contract["source_story"] == "9.1"
    assert contract["wcag_scope"] == "WCAG 2.1 AA"
    assert contract["wcag_2_2_upgrade_story"] == "9.5"
    assert contract["automated_gate"]["command"] == "pnpm --filter @opticloud/ui test:a11y"
    assert [item["profile_id"] for item in contract["a11y_profiles"]] == list(validator.PROFILE_IDS)
    assert [item["persona_id"] for item in contract["sub_personas"]] == list(validator.PERSONA_IDS)
    assert contract["panel_sop"]["recruitment_lead_weeks"] == 6
    assert contract["panel_sop"]["participants_per_sub_persona_target"] == 5
    assert contract["panel_sop"]["backup_pool_multiplier"] == 3
    assert contract["boundaries"]["wcag_2_2_in_scope"] is False


def test_schema_pins_manifest_root_and_matrix_enums() -> None:
    validator = _load_validator()
    schema = _load_json(SCHEMA_PATH)

    assert validator.validate_schema(schema) == []
    assert set(schema["required"]) == validator.MANIFEST_ROOT_REQUIRED
    assert schema["$defs"]["profileId"]["enum"] == list(validator.PROFILE_IDS)
    assert schema["$defs"]["personaId"]["enum"] == list(validator.PERSONA_IDS)


def test_ui_package_a11y_script_covers_every_committed_component_a11y_test() -> None:
    validator = _load_validator()
    package_json = _load_json(REPO_ROOT / "packages" / "ui" / "package.json")
    discovered = validator.discover_component_a11y_tests()

    assert "src/components/Tier1.a11y.test.tsx" in discovered
    assert validator.validate_ui_a11y_script(package_json, discovered) == []


def test_ui_package_a11y_script_rejects_missing_test_and_runner_drift() -> None:
    validator = _load_validator()
    package_json = _load_json(REPO_ROOT / "packages" / "ui" / "package.json")
    script = package_json["scripts"]["test:a11y"]
    package_json["scripts"]["test:a11y"] = script.replace(
        "src/components/CapabilityCard/index.a11y.test.tsx",
        "",
    ).replace("vitest run", "vitest")

    errors = validator.validate_ui_a11y_script(
        package_json, validator.discover_component_a11y_tests()
    )

    _assert_invalid(errors, "must use vitest run")
    _assert_invalid(errors, "missing committed a11y test src/components/CapabilityCard")


def test_example_manifest_is_static_only_and_not_real_evidence() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)

    assert (
        validator.validate_manifest(
            manifest,
            contract,
            source="a11y-example",
            real_evidence=False,
        )
        == []
    )
    errors = validator.validate_manifest(
        manifest,
        contract,
        source="a11y-example",
        real_evidence=True,
    )
    _assert_invalid(errors, "example_only must be false")
    _assert_invalid(errors, "real evidence redaction_reviewed must be true")
    _assert_invalid(errors, "real evidence real_panel_completed must be true")


def test_static_example_rejects_fake_completion_claims() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["real_panel_completed"] = True
    manifest["release_approved"] = True
    manifest["third_party_audit_completed"] = True
    manifest["external_ticket_created"] = True
    manifest["recruitment_completed"] = True

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="a11y-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "static example cannot claim real_panel_completed")
    _assert_invalid(errors, "static example cannot claim release_approved")
    _assert_invalid(errors, "third_party_audit_completed must be false")
    _assert_invalid(errors, "static example cannot claim external_ticket_created")
    _assert_invalid(errors, "static example cannot claim recruitment_completed")


def test_real_evidence_path_mode_accepts_redacted_manifest() -> None:
    manifest = _real_manifest_from_example()
    run_dir = REPO_ROOT / "reports" / "a11y-quarterly" / manifest["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "audit_manifest.json"
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
            Path("reports/a11y-quarterly/run-123/audit_manifest.json"),
            "run-123",
        )
        == []
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/j3-sre-incident/run-123/audit_manifest.json"),
            "run-123",
        ),
        "quarterly a11y evidence path must be",
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/a11y-quarterly/other/audit_manifest.json"),
            "run-123",
        ),
        "quarterly a11y evidence path must be",
    )


def test_real_evidence_rejects_missing_manual_matrix_cell() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["manual_sampling"]["matrix"].pop()

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="a11y-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "manual_sampling missing matrix cell cognitive/chen_architect_sdk")


def test_failed_automated_and_manual_checks_require_ticket_refs() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["automated_axe"]["status"] = "failed"
    manifest["automated_axe"]["violation_count"] = 1
    manifest["automated_axe"]["finding_ids"] = ["a11y-p2-axe"]
    manifest["manual_sampling"]["matrix"][0]["status"] = "failed"
    manifest["manual_sampling"]["matrix"][0]["finding_ids"] = ["a11y-p2-manual"]
    manifest["findings"] = [
        {
            "finding_id": "a11y-p2-axe",
            "source": "automated_axe",
            "severity": "P2",
            "status": "open",
            "summary": "Redacted automated axe finding.",
            "ticket_refs": [],
        },
        {
            "finding_id": "a11y-p2-manual",
            "source": "manual_sampling",
            "severity": "P2",
            "status": "open",
            "summary": "Redacted manual finding.",
            "ticket_refs": [],
        },
    ]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="a11y-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "failed finding a11y-p2-axe must include ticket_refs")
    _assert_invalid(errors, "failed finding a11y-p2-manual must include ticket_refs")


def test_release_approval_blocks_unresolved_stop_ship_findings() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["findings"] = [
        {
            "finding_id": "a11y-p1-keyboard",
            "source": "manual_sampling",
            "severity": "P1",
            "status": "open",
            "summary": "Redacted stop-ship finding.",
            "ticket_refs": [
                {
                    "ticket_id": "A11Y-101",
                    "owner": "UX",
                    "severity": "P1",
                    "due_date": "2026-06-10",
                    "status": "open",
                }
            ],
        }
    ]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="a11y-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "release_approved cannot be true with unresolved P1 finding")


def test_manifest_rejects_sensitive_values_and_keys() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["participant_email"] = "person@example.com"
    manifest["manual_sampling"]["matrix"][0]["notes"] = "Call +1 415 555 0101"
    manifest["manual_sampling"]["matrix"][1]["notes"] = "/tmp/raw-a11y-browser.log"
    manifest["findings"] = [
        {
            "finding_id": "a11y-p3-leak",
            "source": "manual_sampling",
            "severity": "P3",
            "status": "open",
            "summary": "Authorization: Bearer abcdef1234567890",
            "ticket_refs": [
                {
                    "ticket_id": "A11Y-202",
                    "owner": "UX",
                    "severity": "P3",
                    "due_date": "2026-06-11",
                    "status": "open",
                }
            ],
        }
    ]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="a11y-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "forbidden sensitive key")
    _assert_invalid(errors, "forbidden email address")
    _assert_invalid(errors, "forbidden phone number")
    _assert_invalid(errors, "forbidden bearer token")
    _assert_invalid(errors, "forbidden POSIX absolute path")


def test_ci_workflow_wires_ui_a11y_audit_job_without_soft_gate() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert validator.validate_ci_workflow(workflow) == []
    job = validator._job_block(workflow, "ui-a11y-audit-validation")
    assert "continue-on-error" not in job


def test_ci_workflow_validation_rejects_filter_block_drift() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    mutated = workflow.replace(
        "            ui_a11y_audit:\n              - 'packages/ui/**'\n",
        "            ui_a11y_audit:\n",
    )

    errors = validator.validate_ci_workflow(mutated)

    _assert_invalid(errors, "ui_a11y_audit filter missing 'packages/ui/**'")


def test_runbook_documents_quarterly_flow_redaction_stop_ship_and_wcag_handoff() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    for expected in (
        "pnpm --filter @opticloud/ui test:a11y",
        "reports/a11y-quarterly/<run_id>/audit_manifest.json",
        "six-profile x four-sub-persona",
        "6 weeks",
        "Do not commit",
        "P0/P1/P2",
        "release approval",
        "Rollback",
        "Story 9.5",
        "WCAG 2.2",
    ):
        assert expected in runbook
