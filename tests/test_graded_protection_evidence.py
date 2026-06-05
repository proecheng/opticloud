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
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_graded_protection_evidence.py"
EVIDENCE_DIR = REPO_ROOT / "tools" / "graded_protection_evidence"
CONTRACT_PATH = EVIDENCE_DIR / "graded_protection_evidence_contract.json"
SCHEMA_PATH = EVIDENCE_DIR / "graded_protection_evidence_manifest.schema.json"
EXAMPLE_MANIFEST_PATH = EVIDENCE_DIR / "graded_protection_evidence_manifest.example.json"
RUNBOOK_PATH = REPO_ROOT / "docs" / "runbooks" / "graded-protection-evidence.md"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "validate_graded_protection_evidence", VALIDATOR_PATH
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


def _real_manifest_from_example() -> dict[str, Any]:
    manifest = copy.deepcopy(_load_json(EXAMPLE_MANIFEST_PATH))
    manifest["run_id"] = "test-graded-protection-evidence-20260605"
    manifest["example_only"] = False
    manifest["generated_by"] = "redacted graded protection evidence"
    manifest["commit_sha"] = "5b35ff3"
    manifest["redaction_reviewed"] = True
    manifest["release_approved"] = True
    manifest["real_assessment_institution_engaged"] = True
    manifest["real_public_security_filing_completed"] = True
    manifest["real_mlps_level_2_certificate_obtained"] = True
    manifest["real_tsa_timestamp_issued"] = True
    manifest["real_blockchain_preservation_completed"] = True
    manifest["real_legal_signoff_completed"] = True
    manifest["real_evidence_aggregation_completed"] = True
    manifest["overall_gate_status"] = "green"
    for domain in manifest["domain_results"]:
        domain["status"] = "green"
        domain["finding_ids"] = []
    for artifact in manifest["artifact_results"]:
        artifact["status"] = "present"
        artifact["artifact_path"] = artifact["artifact_path"].replace(
            "example-graded-protection-evidence-20260605",
            "test-graded-protection-evidence-20260605",
        )
        artifact["finding_ids"] = []
    for entry in manifest["hash_manifest"]:
        entry["artifact_path"] = entry["artifact_path"].replace(
            "example-graded-protection-evidence-20260605",
            "test-graded-protection-evidence-20260605",
        )
    for review in manifest["legal_reviews"]:
        review["status"] = "passed"
        review["artifact_path"] = review["artifact_path"].replace(
            "example-graded-protection-evidence-20260605",
            "test-graded-protection-evidence-20260605",
        )
        review["finding_ids"] = []
    for receipt in manifest["preservation_receipts"]:
        receipt["verification_status"] = "passed"
        receipt["receipt_artifact_path"] = receipt["receipt_artifact_path"].replace(
            "example-graded-protection-evidence-20260605",
            "test-graded-protection-evidence-20260605",
        )
        receipt["finding_ids"] = []
    manifest["dashboard_handoff"]["status"] = "green"
    manifest["dashboard_handoff"]["manifest_path"] = (
        "reports/governance-dashboard/test-governance-dashboard-20260605/dashboard_manifest.json"
    )
    manifest["dashboard_handoff"]["graded_protection_handoff_complete"] = True
    manifest["dashboard_handoff"]["finding_ids"] = []
    manifest["certificate_artifact_id"] = "artifact-third-party-assessment-tracker"
    manifest["findings"] = []
    return manifest


def test_committed_graded_protection_assets_validate_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "graded protection evidence OK" in result.stdout


def test_contract_pins_scope_domains_artifacts_and_dashboard_state() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)

    assert validator.validate_contract(contract) == []
    assert contract["source_story"] == "9.8"
    assert contract["evidence_version"] == "graded_protection_evidence_v1"
    assert contract["target_level"] == "mlps_level_2"
    assert contract["required_domains"] == list(validator.REQUIRED_DOMAINS)
    assert contract["required_artifact_classes"] == list(validator.REQUIRED_ARTIFACT_CLASSES)
    assert contract["observed_dashboard_state"] == validator.discover_dashboard_state()


def test_contract_rejects_domain_artifact_reference_and_dashboard_drift() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    contract["required_domains"].pop()
    contract["required_artifact_classes"].remove("dashboard_handoff_record")
    contract["domain_artifact_map"][0]["artifact_classes"] = ["unknown_artifact"]
    contract["observed_dashboard_state"]["dashboard_version"] = "wrong"

    errors = validator.validate_contract(contract)

    _assert_invalid(errors, "required domains drifted")
    _assert_invalid(errors, "required artifact classes drifted")
    _assert_invalid(errors, "maps invalid artifact class")
    _assert_invalid(errors, "observed_dashboard_state drifted")


def test_contract_requires_external_reference_metadata_and_no_legal_advice() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    contract["external_references"][0].pop("retrieved_at")
    contract["external_references"][1]["not_legal_advice"] = False

    errors = validator.validate_contract(contract)

    _assert_invalid(errors, "external reference missing retrieved_at")
    _assert_invalid(errors, "external reference must set not_legal_advice=true")


def test_schema_pins_manifest_root_and_enums() -> None:
    validator = _load_validator()
    schema = _load_json(SCHEMA_PATH)

    assert validator.validate_schema(schema) == []
    assert set(schema["required"]) == validator.MANIFEST_ROOT_REQUIRED
    assert schema["$defs"]["domainId"]["enum"] == list(validator.REQUIRED_DOMAINS)
    assert schema["$defs"]["artifactClass"]["enum"] == list(validator.REQUIRED_ARTIFACT_CLASSES)
    assert schema["$defs"]["legalRole"]["enum"] == list(validator.LEGAL_REVIEW_ROLES)


def test_example_manifest_is_static_only_and_not_real_evidence() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)

    assert (
        validator.validate_manifest(
            manifest,
            contract,
            source="graded-protection-example",
            real_evidence=False,
        )
        == []
    )
    errors = validator.validate_manifest(
        manifest,
        contract,
        source="graded-protection-example",
        real_evidence=True,
    )

    _assert_invalid(errors, "example_only must be false")
    _assert_invalid(errors, "real evidence redaction_reviewed must be true")
    _assert_invalid(errors, "real evidence real_evidence_aggregation_completed must be true")


def test_static_example_rejects_fake_completion_claims() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["real_mlps_level_2_certificate_obtained"] = True
    manifest["real_tsa_timestamp_issued"] = True
    manifest["real_blockchain_preservation_completed"] = True
    manifest["real_legal_signoff_completed"] = True
    manifest["release_approved"] = True

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="graded-protection-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "static example cannot claim real_mlps_level_2_certificate_obtained")
    _assert_invalid(errors, "static example cannot claim real_tsa_timestamp_issued")
    _assert_invalid(errors, "static example cannot claim real_blockchain_preservation_completed")
    _assert_invalid(errors, "static example cannot claim real_legal_signoff_completed")
    _assert_invalid(errors, "static example cannot claim release_approved")


def test_manifest_requires_all_domains_artifacts_roles_and_dashboard_handoff() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["domain_results"].pop()
    manifest["artifact_results"] = [
        item
        for item in manifest["artifact_results"]
        if item["artifact_class"] != "dashboard_handoff_record"
    ]
    manifest["legal_reviews"] = [
        item for item in manifest["legal_reviews"] if item["role"] != "Legal"
    ]
    manifest["dashboard_handoff"]["dashboard_version"] = "wrong"

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="graded-protection-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "domain_results ids must match")
    _assert_invalid(errors, "artifact_results classes must match")
    _assert_invalid(errors, "legal_reviews roles must match")
    _assert_invalid(errors, "dashboard_handoff dashboard_version must match")


def test_manifest_requires_hash_manifest_parity_for_non_deferred_artifacts() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["hash_manifest"] = manifest["hash_manifest"][:-1]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="graded-protection-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "hash_manifest artifact ids must match non-deferred artifacts")


def test_real_manifest_allows_one_selected_blockchain_provider() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["preservation_receipts"] = [
        receipt
        for receipt in manifest["preservation_receipts"]
        if receipt["provider"] in {"tsa_rfc3161", "antchain"}
    ]

    assert (
        validator.validate_manifest(
            manifest,
            contract,
            source="graded-protection-real",
            real_evidence=True,
        )
        == []
    )


def test_real_manifest_requires_tsa_and_selected_blockchain_when_claimed() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["preservation_receipts"] = []

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="graded-protection-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "real TSA timestamp claim requires tsa_rfc3161 receipt")
    _assert_invalid(
        errors,
        "real blockchain preservation claim requires at least one selected blockchain receipt",
    )


def test_manifest_rejects_unknown_review_and_receipt_statuses() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["legal_reviews"][0]["status"] = "signed"
    manifest["preservation_receipts"][0]["verification_status"] = "verified"

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="graded-protection-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "legal review Legal status invalid")
    _assert_invalid(errors, "preservation receipt tsa_rfc3161 verification_status invalid")


def test_standard_m5_release_requires_certificate_artifact() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["real_mlps_level_2_certificate_obtained"] = False
    manifest["certificate_artifact_id"] = ""

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="graded-protection-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "standard_m5 release requires MLPS Level 2 certificate")


def test_simplified_track_requires_deferral_finding_when_certificate_absent() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["track_mode"] = "simplified_v1_5"
    manifest["real_mlps_level_2_certificate_obtained"] = False
    manifest["certificate_artifact_id"] = ""
    manifest["release_approved"] = False
    manifest["findings"] = []

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="graded-protection-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "simplified_v1_5 certificate deferral requires a finding")


def test_unresolved_stop_ship_findings_block_release() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["findings"] = [
        {
            "finding_id": "GPE-001",
            "severity": "P1",
            "status": "open",
            "owner": "Compliance",
            "summary": "Certificate package incomplete.",
            "ticket_refs": [
                {
                    "ticket_id": "GPE-001",
                    "owner": "Compliance",
                    "severity": "P1",
                    "due_date": "2026-06-12",
                    "status": "open",
                }
            ],
        }
    ]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="graded-protection-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "release_approved cannot be true with unresolved P0/P1/P2 findings")


def test_gap_status_requires_finding_with_ticket_refs() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["domain_results"][0]["status"] = "red"
    manifest["domain_results"][0]["finding_ids"] = []

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="graded-protection-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "domain system_scope status red requires finding_ids")


def test_manifest_rejects_sensitive_values_and_forbidden_modes() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["artifact_results"][0]["operator_email"] = "owner@example.com"
    manifest["artifact_results"][1]["evidence_mode"] = "external_network"

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="graded-protection-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "forbidden sensitive key")
    _assert_invalid(errors, "invalid evidence_mode")


def test_real_evidence_path_must_match_run_id(tmp_path: Path) -> None:
    validator = _load_validator()
    manifest = _real_manifest_from_example()
    bad_root = tmp_path / "reports" / "graded-protection-evidence" / "wrong-run"
    bad_root.mkdir(parents=True)
    bad_path = bad_root / "evidence_manifest.json"
    bad_path.write_text(json.dumps(manifest), encoding="utf-8")

    errors = validator.validate_evidence_path(bad_path)

    _assert_invalid(
        errors,
        "evidence path must be reports/graded-protection-evidence/<run_id>/evidence_manifest.json",
    )


def test_ci_workflow_and_runbook_cover_graded_protection_gate() -> None:
    validator = _load_validator()
    ci_text = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    runbook_text = RUNBOOK_PATH.read_text(encoding="utf-8")

    assert validator.validate_ci_workflow(ci_text) == []
    assert "graded_protection_evidence" in ci_text
    assert "graded-protection-evidence-validation" in ci_text
    assert "validate_graded_protection_evidence.py --evidence" in ci_text
    assert "governance_dashboard" in ci_text
    assert "TSA" in runbook_text
    assert "Story 9.7" in runbook_text
