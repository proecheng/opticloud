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
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_nfr_security_p0_drills.py"
DRILL_DIR = REPO_ROOT / "tools" / "nfr_security_p0_drills"
CONTRACT_PATH = DRILL_DIR / "nfr_security_p0_drill_contract.json"
SCHEMA_PATH = DRILL_DIR / "nfr_security_p0_drill_manifest.schema.json"
EXAMPLE_MANIFEST_PATH = DRILL_DIR / "nfr_security_p0_drill_manifest.example.json"
RUNBOOK_PATH = REPO_ROOT / "docs" / "runbooks" / "nfr-security-p0-drills.md"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_nfr_security_p0_drills", VALIDATOR_PATH)
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


def _ticket(ticket_id: str = "NFR-S-101", status: str = "resolved") -> dict[str, str]:
    return {
        "ticket_id": ticket_id,
        "owner": "Security",
        "severity": "P2",
        "due_date": "2026-06-12",
        "status": status,
    }


def _real_manifest_from_example() -> dict[str, Any]:
    manifest = copy.deepcopy(_load_json(EXAMPLE_MANIFEST_PATH))
    manifest["run_id"] = "test-nfr-security-p0-drills-20260605"
    manifest["example_only"] = False
    manifest["generated_by"] = "redacted NFR-S P0 drill evidence"
    manifest["commit_sha"] = "a820105"
    manifest["redaction_reviewed"] = True
    manifest["release_approved"] = True
    manifest["real_drill_executed"] = True
    for key in (
        "real_incident_occurred",
        "real_public_postmortem_published",
        "real_external_notification_sent",
        "real_customer_impact",
    ):
        manifest[key] = False
    for result in manifest["scenario_results"]:
        result["status"] = "passed"
        result["allowed_drill_mode"] = "tabletop"
        result["finding_ids"] = []
    for snapshot in manifest["source_snapshots"]:
        snapshot["status"] = "passed"
        snapshot["artifact_path"] = snapshot["artifact_path"].replace(
            "example-nfr-security-p0-drills-20260605",
            "test-nfr-security-p0-drills-20260605",
        )
        snapshot["finding_ids"] = []
    for sop in manifest["sop_executions"]:
        sop["status"] = "passed"
        sop["artifact_path"] = sop["artifact_path"].replace(
            "example-nfr-security-p0-drills-20260605",
            "test-nfr-security-p0-drills-20260605",
        )
        sop["finding_ids"] = []
    for action in manifest["containment_actions"]:
        action["status"] = "passed"
        action["artifact_path"] = action["artifact_path"].replace(
            "example-nfr-security-p0-drills-20260605",
            "test-nfr-security-p0-drills-20260605",
        )
        action["finding_ids"] = []
    for timeline in manifest["timeline_records"]:
        timeline["status"] = "passed"
        timeline["artifact_path"] = timeline["artifact_path"].replace(
            "example-nfr-security-p0-drills-20260605",
            "test-nfr-security-p0-drills-20260605",
        )
        timeline["finding_ids"] = []
    for postmortem in manifest["postmortem_templates"]:
        postmortem["status"] = "passed"
        postmortem["artifact_path"] = postmortem["artifact_path"].replace(
            "example-nfr-security-p0-drills-20260605",
            "test-nfr-security-p0-drills-20260605",
        )
        postmortem["finding_ids"] = []
    manifest["findings"] = []
    return manifest


def test_committed_nfr_security_p0_drill_assets_validate_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "nfr security p0 drills OK" in result.stdout


def test_contract_pins_nfr_s_scope_scenarios_and_observed_repo_state() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)

    assert validator.validate_contract(contract) == []
    assert contract["source_story"] == "9.4"
    assert contract["drill_version"] == "nfr_security_p0_drills_v1"
    assert contract["nfr"] == "NFR-S"
    assert contract["postmortem_sla_hours"] == 24
    assert [item["scenario_id"] for item in contract["scenario_catalog"]] == list(
        validator.SCENARIO_IDS
    )
    assert contract["observed_repo_state"] == validator.discover_repo_state()


def test_contract_rejects_scenario_and_observed_state_drift() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    contract["scenario_catalog"].pop()
    contract["observed_repo_state"]["billing"]["ledger_schema_sha256"] = "0" * 64

    errors = validator.validate_contract(contract)

    _assert_invalid(errors, "scenario_catalog ids must match canonical NFR-S P0 scenarios")
    _assert_invalid(errors, "observed_repo_state.billing drifted")


def test_schema_pins_manifest_root_and_scenario_enum() -> None:
    validator = _load_validator()
    schema = _load_json(SCHEMA_PATH)

    assert validator.validate_schema(schema) == []
    assert set(schema["required"]) == validator.MANIFEST_ROOT_REQUIRED
    assert schema["$defs"]["scenarioId"]["enum"] == list(validator.SCENARIO_IDS)


def test_example_manifest_is_static_only_and_not_real_evidence() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)

    assert (
        validator.validate_manifest(
            manifest,
            contract,
            source="nfr-s-example",
            real_evidence=False,
        )
        == []
    )
    errors = validator.validate_manifest(
        manifest,
        contract,
        source="nfr-s-example",
        real_evidence=True,
    )
    _assert_invalid(errors, "real evidence must set example_only=false")
    _assert_invalid(errors, "real evidence redaction_reviewed must be true")
    _assert_invalid(errors, "real evidence real_drill_executed must be true")


def test_static_example_rejects_fake_completion_claims() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["real_incident_occurred"] = True
    manifest["real_drill_executed"] = True
    manifest["real_public_postmortem_published"] = True
    manifest["real_external_notification_sent"] = True
    manifest["real_customer_impact"] = True
    manifest["release_approved"] = True
    manifest["real_refund_or_compensation_executed"] = True

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="nfr-s-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "static example cannot claim real_incident_occurred")
    _assert_invalid(errors, "static example cannot claim real_drill_executed")
    _assert_invalid(errors, "static example cannot claim real_public_postmortem_published")
    _assert_invalid(errors, "static example cannot claim real_external_notification_sent")
    _assert_invalid(errors, "static example cannot claim real_customer_impact")
    _assert_invalid(errors, "static example cannot claim release_approved")
    _assert_invalid(errors, "static example cannot claim real_refund_or_compensation_executed")


def test_real_evidence_path_mode_accepts_redacted_manifest() -> None:
    manifest = _real_manifest_from_example()
    run_dir = REPO_ROOT / "reports" / "nfr-security-p0-drills" / manifest["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "drill_manifest.json"
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
            Path("reports/nfr-security-p0-drills/run-123/drill_manifest.json"),
            "run-123",
        )
        == []
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/nfr-cost-alerts/run-123/drill_manifest.json"),
            "run-123",
        ),
        "NFR-S P0 drill evidence path must be",
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/nfr-security-p0-drills/other/drill_manifest.json"),
            "run-123",
        ),
        "directory must match run_id",
    )


def test_real_evidence_requires_all_scenarios_and_source_snapshots() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["scenario_results"] = [
        item
        for item in manifest["scenario_results"]
        if item["scenario_id"] != "billing_ledger_corruption"
    ]
    manifest["source_snapshots"] = [
        item for item in manifest["source_snapshots"] if item["scenario_id"] != "data_exfiltration"
    ]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="nfr-s-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "scenario_results missing scenario billing_ledger_corruption")
    _assert_invalid(errors, "source_snapshots missing scenario data_exfiltration")


def test_real_evidence_rejects_example_status_period_drift_and_duplicate_sop_gate() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["period"]["start_date"] = "2026/04/01"
    manifest["scenario_results"][0]["status"] = "not_run_example"
    manifest["sop_executions"].append(copy.deepcopy(manifest["sop_executions"][0]))
    manifest["timeline_records"].append(copy.deepcopy(manifest["timeline_records"][0]))

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="nfr-s-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "period.start_date must be YYYY-MM-DD")
    _assert_invalid(
        errors, "real scenario_results sandbox_privilege_escape must not be not_run_example"
    )
    _assert_invalid(errors, "duplicate gate declare_p0 for sandbox_privilege_escape")
    _assert_invalid(errors, "timeline_records duplicate scenario sandbox_privilege_escape")


def test_real_evidence_rejects_real_incident_customer_delivery_and_compensation_claims() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["real_incident_occurred"] = True
    manifest["real_public_postmortem_published"] = True
    manifest["real_external_notification_sent"] = True
    manifest["real_customer_impact"] = True
    manifest["real_refund_or_compensation_executed"] = True

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="nfr-s-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "real evidence cannot claim real_incident_occurred")
    _assert_invalid(errors, "real evidence cannot claim real_public_postmortem_published")
    _assert_invalid(errors, "real evidence cannot claim real_external_notification_sent")
    _assert_invalid(errors, "real evidence cannot claim real_customer_impact")
    _assert_invalid(errors, "real evidence cannot claim real_refund_or_compensation_executed")


def test_timeline_requires_exact_24h_postmortem_due() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["timeline_records"][0]["postmortem_due_utc"] = "2026-06-06T02:00:00Z"

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="nfr-s-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "postmortem_due_utc must be exactly 24h after p0_declared_utc")


def test_failed_or_missing_closure_requires_ticket_refs() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["scenario_results"][0]["status"] = "failed"
    manifest["scenario_results"][0]["finding_ids"] = ["nfr-s-p2-sandbox"]
    manifest["sop_executions"][0]["status"] = "failed"
    manifest["sop_executions"][0]["finding_ids"] = ["nfr-s-p2-sop"]
    manifest["postmortem_templates"][0]["status"] = "failed"
    manifest["postmortem_templates"][0]["finding_ids"] = ["nfr-s-p2-postmortem"]
    manifest["findings"] = [
        {
            "finding_id": "nfr-s-p2-sandbox",
            "source": "scenario_result",
            "severity": "P2",
            "status": "open",
            "summary": "Redacted sandbox drill finding.",
            "ticket_refs": [],
        },
        {
            "finding_id": "nfr-s-p2-sop",
            "source": "sop_execution",
            "severity": "P2",
            "status": "open",
            "summary": "Redacted SOP finding.",
            "ticket_refs": [],
        },
        {
            "finding_id": "nfr-s-p2-postmortem",
            "source": "postmortem_template",
            "severity": "P2",
            "status": "open",
            "summary": "Redacted postmortem finding.",
            "ticket_refs": [],
        },
    ]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="nfr-s-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "finding nfr-s-p2-sandbox must include ticket_refs")
    _assert_invalid(errors, "finding nfr-s-p2-sop must include ticket_refs")
    _assert_invalid(errors, "finding nfr-s-p2-postmortem must include ticket_refs")


def test_release_approval_blocks_unresolved_stop_ship_findings() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["findings"] = [
        {
            "finding_id": "nfr-s-p1-data",
            "source": "scenario_result",
            "severity": "P1",
            "status": "open",
            "summary": "Redacted stop-ship finding.",
            "ticket_refs": [_ticket(status="open")],
        }
    ]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="nfr-s-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "release_approved cannot be true with unresolved P1 finding")


def test_manifest_rejects_sensitive_values_paths_raw_ledger_and_exploit_payloads() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["tenant_id"] = "tenant-123"
    manifest["source_snapshots"][0]["summary"] = "Bearer abcdef1234567890"
    manifest["source_snapshots"][0]["artifact_path"] = "/tmp/raw-p0-drill.json"
    manifest["containment_actions"][0]["summary"] = (
        "raw_ledger_rows: SELECT * FROM credit_transactions"
    )
    manifest["timeline_records"][0]["artifact_path"] = (
        "reports/nfr-security-p0-drills/test-nfr-security-p0-drills-20260605/../leak.json"
    )
    manifest["postmortem_templates"][0]["sections"]["root_cause"] = (
        "payload: :(){ :|:& }; mount -t proc proc /host"
    )
    manifest["findings"] = [
        {
            "finding_id": "nfr-s-p3-leak",
            "source": "postmortem_template",
            "severity": "P3",
            "status": "open",
            "summary": "customer@example.com",
            "ticket_refs": [_ticket("NFR-S-202")],
        }
    ]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="nfr-s-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "forbidden sensitive key")
    _assert_invalid(errors, "forbidden bearer token")
    _assert_invalid(errors, "forbidden POSIX absolute path")
    _assert_invalid(errors, "artifact path must not traverse directories")
    _assert_invalid(errors, "forbidden raw ledger")
    _assert_invalid(errors, "forbidden exploit payload")
    _assert_invalid(errors, "forbidden email address")


def test_ci_workflow_wires_nfr_security_p0_drills_job_without_soft_gate() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert validator.validate_ci_workflow(workflow) == []
    job = validator._job_block(workflow, "nfr-security-p0-drills-validation")
    assert "continue-on-error" not in job


def test_ci_workflow_validation_rejects_filter_block_drift() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    mutated = workflow.replace(
        "            nfr_security_p0_drills:\n              - 'tools/nfr_security_p0_drills/**'\n",
        "            nfr_security_p0_drills:\n",
    )

    errors = validator.validate_ci_workflow(mutated)

    _assert_invalid(
        errors,
        "nfr_security_p0_drills filter missing 'tools/nfr_security_p0_drills/**'",
    )


def test_runbook_documents_flows_redaction_tickets_and_handoffs() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    for expected in (
        "uv run python scripts/validate_nfr_security_p0_drills.py",
        "reports/nfr-security-p0-drills/<run_id>/drill_manifest.json",
        "sandbox_privilege_escape",
        "data_exfiltration",
        "billing_ledger_corruption",
        "quarterly",
        "annual_lite",
        "24h",
        "Do not commit",
        "P0/P1/P2",
        "release approval",
        "Rollback",
        "Story 9.7",
    ):
        assert expected in runbook
