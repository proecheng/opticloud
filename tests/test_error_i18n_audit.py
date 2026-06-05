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
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_error_i18n_audit.py"
CONTRACT_PATH = REPO_ROOT / "tools" / "error_i18n_audit" / "error_i18n_audit_contract.json"
SCHEMA_PATH = REPO_ROOT / "tools" / "error_i18n_audit" / "error_i18n_audit_manifest.schema.json"
EXAMPLE_MANIFEST_PATH = (
    REPO_ROOT / "tools" / "error_i18n_audit" / "error_i18n_audit_manifest.example.json"
)
RUNBOOK_PATH = REPO_ROOT / "docs" / "runbooks" / "error-i18n-audit.md"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_error_i18n_audit", VALIDATOR_PATH)
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
    manifest["run_id"] = "test-error-i18n-audit-20260605"
    manifest["example_only"] = False
    manifest["generated_by"] = "redacted error i18n quarterly audit evidence"
    manifest["commit_sha"] = "a698b7e"
    manifest["redaction_reviewed"] = True
    manifest["real_quarterly_audit_completed"] = True
    manifest["release_approved"] = True
    for result in manifest["scan_results"]:
        result["status"] = "passed"
        result["hardcoded_error_string_count"] = 0
        result["finding_ids"] = []
    legacy = next(
        item
        for item in manifest["scan_results"]
        if item["scan_class"] == "legacy_http_exception_register"
    )
    legacy["status"] = "missing_with_ticket"
    legacy["legacy_public_http_exception_count"] = 170
    legacy["finding_ids"] = ["error-i18n-p3-legacy-register"]
    manifest["findings"] = [
        {
            "finding_id": "error-i18n-p3-legacy-register",
            "source": "legacy_http_exception_register",
            "severity": "P3",
            "status": "open",
            "summary": "Legacy public HTTPException detail literals remain registered for later migration.",
            "ticket_refs": [
                {
                    "ticket_id": "ERR-I18N-170",
                    "owner": "Platform",
                    "severity": "P3",
                    "due_date": "2026-09-30",
                    "status": "open",
                }
            ],
        }
    ]
    return manifest


def test_committed_error_i18n_audit_assets_validate_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "error i18n audit OK" in result.stdout


def test_contract_pins_scope_scan_classes_and_observed_state() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)

    assert validator.validate_contract(contract) == []
    assert contract["source_story"] == "9.6"
    assert contract["audit_version"] == "error_i18n_quarterly_audit_v1"
    assert contract["rule_id"] == "error-message-i18n-single-source"
    assert [item["scan_class"] for item in contract["scan_classes"]] == list(
        validator.SCAN_CLASSES
    )
    assert contract["observed_repo_state"] == validator.discover_repo_state()
    assert (
        contract["observed_repo_state"]["legacy_http_exception_register"]["total_count"]
        == 170
    )


def test_contract_rejects_scan_class_and_observed_state_drift() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    contract["scan_classes"].pop()
    contract["observed_repo_state"]["solver_error_catalog"]["remediation_hint_keys"].pop()

    errors = validator.validate_contract(contract)

    _assert_invalid(errors, "scan_classes must match Story 9.6")
    _assert_invalid(errors, "observed_repo_state drifted")


def test_schema_pins_manifest_root_and_scan_class_enum() -> None:
    validator = _load_validator()
    schema = _load_json(SCHEMA_PATH)

    assert validator.validate_schema(schema) == []
    assert set(schema["required"]) == validator.MANIFEST_ROOT_REQUIRED
    assert schema["$defs"]["scanClass"]["enum"] == list(validator.SCAN_CLASSES)


def test_example_manifest_is_static_only_and_not_real_evidence() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)

    assert (
        validator.validate_manifest(
            manifest,
            contract,
            source="error-i18n-example",
            real_evidence=False,
        )
        == []
    )
    errors = validator.validate_manifest(
        manifest,
        contract,
        source="error-i18n-example",
        real_evidence=True,
    )

    _assert_invalid(errors, "example_only must be false")
    _assert_invalid(errors, "real evidence redaction_reviewed must be true")
    _assert_invalid(errors, "real evidence real_quarterly_audit_completed must be true")


def test_static_example_rejects_fake_completion_claims() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["real_quarterly_audit_completed"] = True
    manifest["real_full_codebase_migration_completed"] = True
    manifest["real_external_ticket_created"] = True
    manifest["release_approved"] = True

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="error-i18n-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "static example cannot claim real_quarterly_audit_completed")
    _assert_invalid(errors, "static example cannot claim real_full_codebase_migration_completed")
    _assert_invalid(errors, "static example cannot claim real_external_ticket_created")
    _assert_invalid(errors, "static example cannot claim release_approved")


def test_real_evidence_path_mode_accepts_redacted_manifest() -> None:
    manifest = _real_manifest_from_example()
    run_dir = REPO_ROOT / "reports" / "error-i18n-audit" / manifest["run_id"]
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
            Path("reports/error-i18n-audit/run-123/audit_manifest.json"),
            "run-123",
        )
        == []
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/prometheus-metric-audit/run-123/audit_manifest.json"),
            "run-123",
        ),
        "Error i18n audit evidence path must be",
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/error-i18n-audit/other/audit_manifest.json"),
            "run-123",
        ),
        "Error i18n audit evidence path must be",
    )


def test_dictionary_catalog_sdk_and_billing_key_parity() -> None:
    validator = _load_validator()

    assert validator.validate_committed_i18n_state() == []
    dictionary_keys = validator.dictionary_key_set()
    for key in validator.discover_solver_catalog_keys():
        assert key in dictionary_keys
    for key in validator.discover_sdk_fixture_keys():
        assert key in dictionary_keys
    for key in validator.BILLING_SHARED_REQUIRED_KEYS:
        assert key in dictionary_keys


def test_production_remediation_key_register_is_discovered_and_pinned() -> None:
    validator = _load_validator()
    discovered = validator.discover_production_remediation_keys()

    assert "errors.auth_frozen.appeal" in discovered["static_keys"]
    assert "errors.chat_coder.formulator_extracted_required" in discovered["static_keys"]
    assert "errors.chat_language.fallback_used" in discovered["static_keys"]
    assert "errors.chat_sandbox.{error_code.value}" in discovered["dynamic_templates"]
    assert "errors.422.{result.status}" in discovered["dynamic_templates"]
    assert "errors.{status_code}.billing_http_error" in discovered["dynamic_templates"]
    assert validator.validate_production_remediation_keys(
        validator.dictionary_key_set(),
        discovered=discovered,
    ) == []


def test_production_remediation_key_validation_rejects_non_errors_namespace() -> None:
    validator = _load_validator()

    errors = validator.validate_production_remediation_keys(
        validator.dictionary_key_set(),
        discovered={"static_keys": {"chat.coder.old_key": ["apps/chat-service/src/x.py:1"]}},
    )

    _assert_invalid(errors, "must start with errors.")


def test_production_remediation_key_validation_rejects_missing_dictionary_key() -> None:
    validator = _load_validator()

    errors = validator.validate_production_remediation_keys(
        validator.dictionary_key_set(),
        discovered={"static_keys": {"errors.chat_coder.missing": ["apps/chat-service/src/x.py:1"]}},
    )

    _assert_invalid(errors, "missing from dictionaries")


def test_production_remediation_key_validation_rejects_unbounded_dynamic_template() -> None:
    validator = _load_validator()

    errors = validator.validate_production_remediation_keys(
        validator.dictionary_key_set(),
        discovered={
            "static_keys": {},
            "dynamic_templates": {"errors.chat_unknown.{kind}": ["apps/chat-service/src/x.py:1"]},
        },
    )

    _assert_invalid(errors, "is not an approved bounded template")


def test_dictionary_parity_rejects_missing_solver_catalog_key() -> None:
    validator = _load_validator()
    keys = validator.dictionary_key_set()
    keys.remove("errors.400.invalid_json")

    errors = validator.validate_key_sets(keys)

    _assert_invalid(errors, "solver catalog key errors.400.invalid_json missing")


def test_legacy_http_exception_register_is_discovered_and_pinned() -> None:
    validator = _load_validator()
    register = validator.discover_legacy_http_exception_register()

    assert register["total_count"] == 170
    assert register["by_file"]["apps/auth-service/src/auth_service/routes.py"] == 38
    assert register["by_file"]["apps/capability-registry/src/capability_registry/routes.py"] == 89


def test_real_evidence_requires_tickets_for_legacy_or_failed_scan() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["findings"][0]["ticket_refs"] = []
    manifest["scan_results"][0]["status"] = "failed"
    manifest["scan_results"][0]["finding_ids"] = ["error-i18n-p2-ts"]
    manifest["findings"].append(
        {
            "finding_id": "error-i18n-p2-ts",
            "source": "typescript_problem_detail",
            "severity": "P2",
            "status": "open",
            "summary": "Redacted hard-coded TypeScript problem detail finding.",
            "ticket_refs": [],
        }
    )

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="error-i18n-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "finding error-i18n-p3-legacy-register must include ticket_refs")
    _assert_invalid(errors, "finding error-i18n-p2-ts must include ticket_refs")


def test_release_approval_blocks_unresolved_stop_ship_findings() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["findings"].append(
        {
            "finding_id": "error-i18n-p1-catalog",
            "source": "solver_error_catalog",
            "severity": "P1",
            "status": "open",
            "summary": "Redacted solver catalog drift.",
            "ticket_refs": [
                {
                    "ticket_id": "ERR-I18N-101",
                    "owner": "Platform",
                    "severity": "P1",
                    "due_date": "2026-06-12",
                    "status": "open",
                }
            ],
        }
    )

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="error-i18n-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "release_approved cannot be true with unresolved P1 finding")


def test_manifest_rejects_sensitive_values_paths_and_raw_payloads() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["tenant_id"] = "tenant-123"
    manifest["scan_results"][0]["artifact_path"] = "/tmp/raw-error-audit.json"
    manifest["scan_results"][1]["notes"] = "Bearer abcdef1234567890"
    manifest["scan_results"][2]["raw_log"] = "customer@example.com"
    manifest["findings"][0]["summary"] = "https://api.opticloud.cn/internal"

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="error-i18n-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "forbidden sensitive key")
    _assert_invalid(errors, "forbidden POSIX absolute path")
    _assert_invalid(errors, "forbidden bearer token")
    _assert_invalid(errors, "forbidden email address")
    _assert_invalid(errors, "forbidden production hostname")


def test_ci_workflow_wires_error_i18n_audit_job_without_soft_gate() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert validator.validate_ci_workflow(workflow) == []
    job = validator._job_block(workflow, "error-i18n-audit-validation")
    assert "continue-on-error" not in job


def test_ci_workflow_validation_rejects_filter_block_drift() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    mutated = workflow.replace(
        "            error_i18n_audit:\n              - 'tools/error_i18n_audit/**'\n",
        "            error_i18n_audit:\n",
    )

    errors = validator.validate_ci_workflow(mutated)

    _assert_invalid(errors, "error_i18n_audit filter missing 'tools/error_i18n_audit/**'")


def test_ci_workflow_validation_rejects_python_app_source_filter_drift() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    mutated = workflow.replace("              - 'apps/*/src/**/*.py'\n", "")

    errors = validator.validate_ci_workflow(mutated)

    _assert_invalid(errors, "error_i18n_audit filter missing 'apps/*/src/**/*.py'")


def test_ci_workflow_validation_rejects_package_source_filter_drift() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    mutated = workflow.replace("              - 'packages/shared-py/**/*.py'\n", "")

    errors = validator.validate_ci_workflow(mutated)

    _assert_invalid(errors, "error_i18n_audit filter missing 'packages/shared-py/**/*.py'")


def test_runbook_documents_flow_redaction_legacy_register_and_handoffs() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    for expected in (
        "uv run python scripts/validate_error_i18n_audit.py",
        "reports/error-i18n-audit/<run_id>/audit_manifest.json",
        "quarterly",
        "error-message-i18n-single-source",
        "hardcoded error string count = 0",
        "legacy_http_exception_register",
        "Do not commit",
        "P0/P1/P2",
        "release approval",
        "Rollback",
        "Story 8.B.5",
        "Story 9.7",
    ):
        assert expected in runbook
