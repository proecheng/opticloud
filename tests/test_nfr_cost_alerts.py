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
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_nfr_cost_alerts.py"
CONTRACT_PATH = REPO_ROOT / "tools" / "nfr_cost_alerts" / "nfr_cost_alert_contract.json"
SCHEMA_PATH = REPO_ROOT / "tools" / "nfr_cost_alerts" / "nfr_cost_alert_manifest.schema.json"
EXAMPLE_MANIFEST_PATH = (
    REPO_ROOT / "tools" / "nfr_cost_alerts" / "nfr_cost_alert_manifest.example.json"
)
RUNBOOK_PATH = REPO_ROOT / "docs" / "runbooks" / "nfr-cost-alerts.md"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_nfr_cost_alerts", VALIDATOR_PATH)
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
    manifest["run_id"] = "test-nfr-cost-alerts-20260604"
    manifest["example_only"] = False
    manifest["generated_by"] = "redacted NFR-COST alert evidence"
    manifest["commit_sha"] = "ac51f25"
    manifest["cadence_mode"] = "breach_drill"
    manifest["redaction_reviewed"] = True
    manifest["release_approved"] = True
    manifest["real_alert_fired"] = True
    manifest["real_dingtalk_delivered"] = False
    manifest["real_linear_created"] = False
    for evaluation in manifest["redline_evaluations"]:
        evaluation["status"] = "passed"
        evaluation["observed_value"] = 0.01
    runway = next(
        item for item in manifest["redline_evaluations"] if item["redline_id"] == "runway_months"
    )
    runway["observed_value"] = 12
    for snapshot in manifest["source_snapshots"]:
        snapshot["status"] = "passed"
        snapshot["artifact_path"] = snapshot["artifact_path"].replace(
            "example-nfr-cost-alerts-20260604",
            "test-nfr-cost-alerts-20260604",
        )
    for alert in manifest["prometheus_alerts"]:
        alert["status"] = "passed"
        alert["artifact_path"] = alert["artifact_path"].replace(
            "example-nfr-cost-alerts-20260604",
            "test-nfr-cost-alerts-20260604",
        )
    for payload in manifest["dingtalk_payloads"]:
        payload["status"] = "payload_ready"
        payload["evidence_pointer"] = payload["evidence_pointer"].replace(
            "example-nfr-cost-alerts-20260604",
            "test-nfr-cost-alerts-20260604",
        )
    for payload in manifest["linear_payloads"]:
        payload["status"] = "payload_ready"
        payload["evidence_pointer"] = payload["evidence_pointer"].replace(
            "example-nfr-cost-alerts-20260604",
            "test-nfr-cost-alerts-20260604",
        )
    for outcome in manifest["routing_outcomes"]:
        outcome["dingtalk_status"] = "payload_ready"
        outcome["linear_status"] = "payload_ready"
        outcome["owner_ack_status"] = "acked"
    return manifest


def test_committed_nfr_cost_alert_assets_validate_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "nfr cost alerts OK" in result.stdout


def test_contract_pins_redlines_thresholds_and_observed_state() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)

    assert validator.validate_contract(contract) == []
    assert contract["source_story"] == "9.3"
    assert contract["alert_version"] == "nfr_cost_redline_alerts_v1"
    assert [item["redline_id"] for item in contract["redline_catalog"]] == list(
        validator.REDLINE_IDS
    )
    assert validator._threshold_map(contract) == validator.REDLINE_THRESHOLDS
    assert contract["observed_cost_telemetry_state"] == validator.discover_cost_telemetry_state()


def test_contract_rejects_redline_and_observed_state_drift() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    contract["redline_catalog"].pop()
    contract["observed_cost_telemetry_state"]["shared_cost_unit_enum"]["values"].pop()

    errors = validator.validate_contract(contract)

    _assert_invalid(errors, "redline_catalog ids must match NFR-COST")
    _assert_invalid(errors, "observed_cost_telemetry_state drifted")


def test_schema_pins_manifest_root_and_redline_enums() -> None:
    validator = _load_validator()
    schema = _load_json(SCHEMA_PATH)

    assert validator.validate_schema(schema) == []
    assert set(schema["required"]) == validator.MANIFEST_ROOT_REQUIRED
    assert schema["$defs"]["redlineId"]["enum"] == list(validator.REDLINE_IDS)


def test_example_manifest_is_static_only_and_not_real_evidence() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)

    assert (
        validator.validate_manifest(
            manifest, contract, source="nfr-cost-example", real_evidence=False
        )
        == []
    )
    errors = validator.validate_manifest(
        manifest,
        contract,
        source="nfr-cost-example",
        real_evidence=True,
    )
    _assert_invalid(errors, "example_only must be false")
    _assert_invalid(errors, "real evidence redaction_reviewed must be true")
    _assert_invalid(errors, "real evidence real_alert_fired must be true")


def test_static_example_rejects_fake_completion_claims() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _load_json(EXAMPLE_MANIFEST_PATH)
    manifest["real_alert_fired"] = True
    manifest["real_dingtalk_delivered"] = True
    manifest["real_linear_created"] = True
    manifest["release_approved"] = True
    manifest["finance_approval_completed"] = True

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="nfr-cost-example",
        real_evidence=False,
    )

    _assert_invalid(errors, "static example cannot claim real_alert_fired")
    _assert_invalid(errors, "static example cannot claim real_dingtalk_delivered")
    _assert_invalid(errors, "static example cannot claim real_linear_created")
    _assert_invalid(errors, "static example cannot claim release_approved")
    _assert_invalid(errors, "static example cannot claim finance_approval_completed")


def test_real_evidence_path_mode_accepts_redacted_manifest() -> None:
    manifest = _real_manifest_from_example()
    run_dir = REPO_ROOT / "reports" / "nfr-cost-alerts" / manifest["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "alert_manifest.json"
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
            Path("reports/nfr-cost-alerts/run-123/alert_manifest.json"),
            "run-123",
        )
        == []
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/prometheus-metric-audit/run-123/alert_manifest.json"),
            "run-123",
        ),
        "NFR-COST alert evidence path must be",
    )
    _assert_invalid(
        validator.validate_evidence_path_mode(
            Path("reports/nfr-cost-alerts/other/alert_manifest.json"),
            "run-123",
        ),
        "NFR-COST alert evidence path must be",
    )


def test_manifest_requires_all_redline_evaluations_and_payloads() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["redline_evaluations"] = [
        item for item in manifest["redline_evaluations"] if item["redline_id"] != "runway_months"
    ]
    manifest["dingtalk_payloads"] = [
        item for item in manifest["dingtalk_payloads"] if item["redline_id"] != "gpu_idle_rate"
    ]
    manifest["linear_payloads"] = [
        item for item in manifest["linear_payloads"] if item["redline_id"] != "refund_issued_rate"
    ]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="nfr-cost-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "redline_evaluations missing redline runway_months")
    _assert_invalid(errors, "dingtalk_payloads missing redline gpu_idle_rate")
    _assert_invalid(errors, "linear_payloads missing redline refund_issued_rate")


def test_breaches_failures_and_missing_signals_require_ticket_refs() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["redline_evaluations"][0]["status"] = "breached"
    manifest["redline_evaluations"][0]["finding_ids"] = ["nfr-cost-p1-llm"]
    manifest["source_snapshots"][0]["status"] = "failed"
    manifest["source_snapshots"][0]["finding_ids"] = ["nfr-cost-p2-source"]
    manifest["prometheus_alerts"][0]["status"] = "failed"
    manifest["prometheus_alerts"][0]["finding_ids"] = ["nfr-cost-p2-alert"]
    manifest["dingtalk_payloads"][0]["status"] = "failed"
    manifest["dingtalk_payloads"][0]["finding_ids"] = ["nfr-cost-p2-dingtalk"]
    manifest["linear_payloads"][0]["status"] = "failed"
    manifest["linear_payloads"][0]["finding_ids"] = ["nfr-cost-p2-linear"]
    manifest["findings"] = [
        {
            "finding_id": "nfr-cost-p1-llm",
            "source": "redline_evaluation",
            "severity": "P1",
            "status": "open",
            "summary": "Redacted breached cost redline.",
            "ticket_refs": [],
        },
        {
            "finding_id": "nfr-cost-p2-source",
            "source": "source_snapshot",
            "severity": "P2",
            "status": "open",
            "summary": "Redacted source snapshot failure.",
            "ticket_refs": [],
        },
        {
            "finding_id": "nfr-cost-p2-alert",
            "source": "prometheus_alert",
            "severity": "P2",
            "status": "open",
            "summary": "Redacted alert failure.",
            "ticket_refs": [],
        },
        {
            "finding_id": "nfr-cost-p2-dingtalk",
            "source": "dingtalk_payload",
            "severity": "P2",
            "status": "open",
            "summary": "Redacted DingTalk payload failure.",
            "ticket_refs": [],
        },
        {
            "finding_id": "nfr-cost-p2-linear",
            "source": "linear_payload",
            "severity": "P2",
            "status": "open",
            "summary": "Redacted Linear payload failure.",
            "ticket_refs": [],
        },
    ]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="nfr-cost-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "finding nfr-cost-p1-llm must include ticket_refs")
    _assert_invalid(errors, "finding nfr-cost-p2-source must include ticket_refs")
    _assert_invalid(errors, "finding nfr-cost-p2-alert must include ticket_refs")
    _assert_invalid(errors, "finding nfr-cost-p2-dingtalk must include ticket_refs")
    _assert_invalid(errors, "finding nfr-cost-p2-linear must include ticket_refs")


def test_release_approval_blocks_unresolved_stop_ship_findings() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["findings"] = [
        {
            "finding_id": "nfr-cost-p0-runway",
            "source": "redline_evaluation",
            "severity": "P0",
            "status": "open",
            "summary": "Redacted runway finding.",
            "ticket_refs": [
                {
                    "ticket_id": "NFR-COST-101",
                    "owner": "Finance",
                    "severity": "P0",
                    "due_date": "2026-06-12",
                    "status": "open",
                }
            ],
        }
    ]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="nfr-cost-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "release_approved cannot be true with unresolved P0 finding")


def test_manifest_rejects_sensitive_values_paths_raw_labels_and_external_ids() -> None:
    validator = _load_validator()
    contract = _load_json(CONTRACT_PATH)
    manifest = _real_manifest_from_example()
    manifest["tenant_id"] = "tenant-123"
    manifest["source_snapshots"][0]["artifact_path"] = "/tmp/raw-finance-export.json"
    manifest["source_snapshots"][0]["raw_prometheus_labels"] = {"tenant_id": "tenant-123"}
    manifest["dingtalk_payloads"][0]["markdown_text"] = "Bearer abcdef1234567890"
    manifest["linear_payloads"][0]["external_issue_id"] = "LIN-123"
    manifest["findings"] = [
        {
            "finding_id": "nfr-cost-p3-leak",
            "source": "source_snapshot",
            "severity": "P3",
            "status": "open",
            "summary": "customer@example.com",
            "ticket_refs": [
                {
                    "ticket_id": "NFR-COST-202",
                    "owner": "Finance",
                    "severity": "P3",
                    "due_date": "2026-06-13",
                    "status": "open",
                }
            ],
        }
    ]

    errors = validator.validate_manifest(
        manifest,
        contract,
        source="nfr-cost-real",
        real_evidence=True,
    )

    _assert_invalid(errors, "forbidden sensitive key")
    _assert_invalid(errors, "forbidden POSIX absolute path")
    _assert_invalid(errors, "forbidden bearer token")
    _assert_invalid(errors, "forbidden email address")
    _assert_invalid(errors, "external_issue_id must stay null")


def test_ci_workflow_wires_nfr_cost_alert_job_without_soft_gate() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert validator.validate_ci_workflow(workflow) == []
    job = validator._job_block(workflow, "nfr-cost-alerts-validation")
    assert "continue-on-error" not in job


def test_ci_workflow_validation_rejects_filter_block_drift() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    mutated = workflow.replace(
        "            nfr_cost_alerts:\n              - 'tools/nfr_cost_alerts/**'\n",
        "            nfr_cost_alerts:\n",
    )

    errors = validator.validate_ci_workflow(mutated)

    _assert_invalid(errors, "nfr_cost_alerts filter missing 'tools/nfr_cost_alerts/**'")


def test_ci_workflow_validation_rejects_prometheus_handoff_filter_drift() -> None:
    validator = _load_validator()
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    mutated = workflow.replace(
        "              - 'scripts/validate_prometheus_metric_audit.py'\n", ""
    )

    errors = validator.validate_ci_workflow(mutated)

    _assert_invalid(
        errors,
        "nfr_cost_alerts filter missing 'scripts/validate_prometheus_metric_audit.py'",
    )


def test_runbook_documents_flows_redaction_tickets_and_handoffs() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    for expected in (
        "uv run python scripts/validate_nfr_cost_alerts.py",
        "reports/nfr-cost-alerts/<run_id>/alert_manifest.json",
        "quarterly",
        "breach_drill",
        "Prometheus",
        "Alertmanager",
        "DingTalk-ready",
        "Linear-ready",
        "Do not commit",
        "P0/P1/P2",
        "release approval",
        "Rollback",
        "Story 9.7",
    ):
        assert expected in runbook
